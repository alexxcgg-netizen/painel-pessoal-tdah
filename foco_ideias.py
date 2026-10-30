"""Grupo A (Foco) das ideias do Laboratorio v4 (30/10/2026) - docs/briefings/2026-10-30-lab-v4-foco.md.

  - E AGORA? (`e_agora`): um botao, UMA coisa. Pontua as tarefas abertas (prazo, cadeado, quantas vezes foi
    empurrada, se cabe no tempo livre ate o proximo compromisso, energia do check-in) e devolve ate 3, a primeira
    com o porque numa linha. "Outra" troca; "Bora" abre o Parceiro de foco (foco.py) ja com o relogio correndo.
    Tudo em Python puro: nao gasta chamada de IA.
  - POR QUE TRAVOU? (`travou`): tarefa empurrada 3+ vezes -> pergunta UMA vez, sem bronca, com 4 respostas de
    1 toque; cada uma leva a um remedio (chato = juntar com prêmio, dificil = passo de 2 min, medo = roteiro,
    sem rumo = primeiro passo/passos). Roteiro e passos vem da IA (modelo barato); sem IA cai num texto padrao.
  - PACOTE DE TENTACAO (`pacote`): `tasks.extras.pacote = {premio}`. Marcou a tarefa como feita -> o premio sai
    "liberado" (a rota /complete devolve o premio).
  - UM SEGUNDO ANTES (`segundo_antes`): tela do Atalhos ("quando abrir o app X") que respira 5 s com a tarefa do
    momento; so conta quantas vezes ele voltou na semana (configuracoes.segundo_antes_log). Nunca bloqueia.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta

import db
import foco

LIMITE_TRAVOU = 3  # adiamentos pra perguntar
MOTIVOS = ("chato", "dificil", "medo", "sem_rumo")
PREMIOS_SUGERIDOS = ("Podcast de aviação", "Episódio da série", "Playlist nova")
MINUTOS_ESFORCO = {"baixa": 5, "media": 12, "alta": 25}
NIVEL_ENERGIA = {1: "baixa", 2: "media", 3: "alta"}
_NUM_ESFORCO = {"baixa": 1, "media": 2, "alta": 3}
PASSO_BORA = "Abre e faz só a primeira parte. 2 minutos. Mais nada."
LIVRE_MAXIMO_MIN = 180  # mais que isso nao e "folga ate o compromisso", e dia vazio: nao mostra
LOG_MAX = 200


def _limpo(texto, limite: int) -> str:
    return re.sub(r"\s+", " ", str(texto or "")).strip()[:limite]


def _extras(valor) -> dict:
    try:
        e = json.loads(valor) if valor else {}
    except (TypeError, ValueError):
        e = {}
    return e if isinstance(e, dict) else {}


# ============================================================ E agora?

def _livre_ate_proximo(agora: datetime, eventos) -> tuple[int | None, str | None]:
    """Minutos livres ate o proximo compromisso de hoje (agenda + tarefa com hora) e o nome dele."""
    prox = None
    for e in eventos or []:
        if not isinstance(e, dict) or e.get("dia_inteiro"):
            continue
        try:
            ini = datetime.fromisoformat(str(e.get("inicio"))[:19]).replace(tzinfo=None)
        except ValueError:
            continue
        if ini.date() == agora.date() and ini > agora and (prox is None or ini < prox[0]):
            prox = (ini, _limpo(e.get("titulo"), 40))
    if not prox:
        return None, None
    minutos = int((prox[0] - agora).total_seconds() // 60)
    return (minutos, prox[1]) if 0 < minutos <= LIVRE_MAXIMO_MIN else (None, None)


def _energia_de_hoje(conn, hoje: date) -> str | None:
    c = db.get_checkin(conn, hoje.isoformat())
    return NIVEL_ENERGIA.get((c or {}).get("energia"))


def _estimar_min(esforco, n_subtarefas_abertas: int) -> int:
    base = MINUTOS_ESFORCO.get(esforco or "media", 12)
    return min(base, max(4, 4 * n_subtarefas_abertas)) if n_subtarefas_abertas else base


def _pontuar(t, hoje: date, livre: int | None, energia: str | None) -> tuple[float, int]:
    score = 5.0
    if t["due_date"]:
        try:
            dias = (date.fromisoformat(t["due_date"]) - hoje).days
        except ValueError:
            dias = None
        if dias is not None:
            if dias < 0:
                score = 50 + min(-dias, 10)
            elif dias == 0:
                score = 40
            elif dias == 1:
                score = 20
            elif dias <= 7:
                score = 10
    if t["inegociavel"]:
        score += 15
    score += min(t["adiadas"], 5) * 4
    minutos = _estimar_min(t["esforco"], t["abertas"])
    if livre is not None:
        score += 10 if minutos <= livre else -30
    if energia and _NUM_ESFORCO.get(t["esforco"] or "media", 2) > _NUM_ESFORCO[energia]:
        score -= 25
    return score, minutos


def _porque(t, hoje: date, minutos: int, livre: int | None, proximo: str | None, energia: str | None) -> str:
    partes = []
    dias = None
    if t["due_date"]:
        try:
            dias = (date.fromisoformat(t["due_date"]) - hoje).days
        except ValueError:
            pass
    if dias is not None and dias < 0:
        partes.append(f"Tá atrasada há {-dias} {'dia' if dias == -1 else 'dias'}.")
    elif dias == 0:
        partes.append("Vence hoje.")
    elif dias == 1:
        partes.append("Vence amanhã.")
    elif t["adiadas"] >= 2:
        partes.append(f"Já foi empurrada {t['adiadas']} vezes.")
    if t["inegociavel"]:
        partes.append("É inegociável.")
    if livre is not None and minutos <= livre:
        partes.append(f"Cabe nos {livre} min até {proximo or 'o próximo compromisso'}.")
    elif energia == "baixa" and (t["esforco"] or "media") == "baixa":
        partes.append("Energia baixa resolve.")
    if not partes:
        partes.append("É rápida e já tira ela da cabeça." if minutos <= 8 else "Dá pra começar agora.")
    return " ".join(partes[:2])


def e_agora(conn, agora: datetime, eventos=None, limite: int = 3) -> dict:
    """Dado do card `e_agora`. `eventos`: lista de compromissos de hoje (app._eventos_de_hoje_com_seguranca)."""
    hoje = agora.date()
    livre, proximo = _livre_ate_proximo(agora, eventos)
    energia = _energia_de_hoje(conn, hoje)
    linhas = conn.execute(
        """SELECT t.id, t.title, t.due_date, t.hora, t.inegociavel, t.esforco, t.extras,
                  (SELECT COUNT(*) FROM tarefas_adiadas a WHERE a.task_id = t.id) AS adiadas,
                  (SELECT COUNT(*) FROM subtasks s WHERE s.task_id = t.id AND s.completed_at IS NULL) AS abertas
           FROM tasks t WHERE t.completed_at IS NULL AND t.recorrencia IS NULL AND t.arquivada_em IS NULL"""
    ).fetchall()
    ranque = []
    for r in linhas:
        t = dict(r)
        if t["hora"] and t["due_date"] and t["due_date"] >= hoje.isoformat():
            continue  # ja tem a hora dela na agenda
        score, minutos = _pontuar(t, hoje, livre, energia)
        ranque.append((score, -t["id"], t, minutos))
    ranque.sort(key=lambda x: (x[0], x[1]), reverse=True)
    sugestoes = []
    for _, _, t, minutos in ranque[:limite]:
        premio = (_extras(t["extras"]).get("pacote") or {}).get("premio")
        sugestoes.append({
            "id": t["id"], "titulo": t["title"], "min": minutos,
            "porque": _porque(t, hoje, minutos, livre, proximo, energia),
            **({"premio": premio} if premio else {}),
        })
    return {"quando": agora.strftime("%H:%M"), "livre_min": livre, "livre_ate": proximo, "sugestoes": sugestoes}


def bora(conn, agora: datetime, task_id: int) -> dict | None:
    """"Bora": abre o Parceiro de foco nessa tarefa e ja liga o relogio."""
    t = conn.execute("SELECT id, title FROM tasks WHERE id = ? AND completed_at IS NULL AND arquivada_em IS NULL",
                     (task_id,)).fetchone()
    if not t:
        return None
    e = foco.abrir(conn, agora, t["title"], PASSO_BORA, None, foco.PADRAO_MIN, t["id"])
    return foco.comecar(conn, agora, e["id"]) or e


# ============================================================ Pacote de tentacao

def juntar(conn, task_id: int, premio: str) -> dict | None:
    premio = _limpo(premio, 60)
    t = conn.execute("SELECT id, title, extras FROM tasks WHERE id = ? AND completed_at IS NULL", (task_id,)).fetchone()
    if not t or not premio:
        return None
    extras = _extras(t["extras"])
    extras["pacote"] = {"premio": premio}
    db.salvar_extras_tarefa(conn, task_id, extras)
    return {"id": t["id"], "titulo": t["title"], "premio": premio}


def desfazer_pacote(conn, task_id: int) -> bool:
    t = conn.execute("SELECT extras FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not t:
        return False
    extras = _extras(t["extras"])
    if "pacote" not in extras:
        return False
    extras.pop("pacote")
    db.salvar_extras_tarefa(conn, task_id, extras)
    return True


def premio_da_tarefa(conn, task_id: int) -> str | None:
    """Premio guardado na tarefa (depois do /complete ele continua la)."""
    p = db.extras_tarefa(conn, task_id).get("pacote")
    return _limpo(p.get("premio"), 60) if isinstance(p, dict) and p.get("premio") else None


def pacote(conn) -> dict:
    """Dado do card `pacote`: tarefas pra escolher (as mais empurradas primeiro), premios sugeridos e os pacotes ativos."""
    chatas, ativos = [], []
    for r in conn.execute(
        """SELECT t.id, t.title, t.extras,
                  (SELECT COUNT(*) FROM tarefas_adiadas a WHERE a.task_id = t.id) AS adiadas
           FROM tasks t WHERE t.completed_at IS NULL AND t.recorrencia IS NULL AND t.arquivada_em IS NULL
           ORDER BY adiadas DESC, (t.due_date IS NULL), t.due_date, t.id LIMIT 40"""
    ).fetchall():
        premio = (_extras(r["extras"]).get("pacote") or {}).get("premio")
        if premio:
            ativos.append({"id": r["id"], "titulo": r["title"], "premio": premio})
        elif len(chatas) < 5:
            chatas.append({"id": r["id"], "titulo": r["title"], "adiadas": r["adiadas"]})
    return {"chatas": chatas, "premios": list(PREMIOS_SUGERIDOS), "ativos": ativos[:5]}


# ============================================================ Por que travou?

def _adiadas(conn, task_id: int) -> int:
    return conn.execute("SELECT COUNT(*) n FROM tarefas_adiadas WHERE task_id = ?", (task_id,)).fetchone()["n"]


def pendentes_travou(conn) -> list[dict]:
    """Abertas, empurradas LIMITE_TRAVOU+ vezes, que ele ainda nao respondeu (nem foi perguntado). Mais empurrada primeiro."""
    out = []
    for r in conn.execute(
        """SELECT t.id, t.title, t.extras, COUNT(*) AS n FROM tarefas_adiadas a JOIN tasks t ON t.id = a.task_id
           WHERE t.completed_at IS NULL AND t.arquivada_em IS NULL GROUP BY t.id HAVING COUNT(*) >= ?
           ORDER BY COUNT(*) DESC, t.id""", (LIMITE_TRAVOU,)).fetchall():
        if not _extras(r["extras"]).get("travou"):
            out.append({"id": r["id"], "titulo": r["title"], "adiadas": r["n"]})
    return out


def dados_travou(conn, task_id: int) -> dict | None:
    t = conn.execute("SELECT id, title, extras FROM tasks WHERE id = ? AND completed_at IS NULL", (task_id,)).fetchone()
    if not t:
        return None
    tr = _extras(t["extras"]).get("travou") or {}
    return {"task_id": t["id"], "titulo": t["title"], "adiadas": max(_adiadas(conn, task_id), LIMITE_TRAVOU),
            "motivo": tr.get("motivo")}


def marcar_perguntada(conn, task_id: int) -> None:
    """Pergunta so uma vez: guarda que o card saiu (mesmo sem resposta)."""
    extras = db.extras_tarefa(conn, task_id)
    extras.setdefault("travou", {"motivo": None})
    db.salvar_extras_tarefa(conn, task_id, extras)


def _remedio_padrao(titulo: str, motivo: str) -> dict:
    if motivo == "dificil":
        return {"texto": f"Só abre o que precisa pra \"{titulo}\" e faz a primeira parte. Dois minutos, mais nada.", "roteiro": [], "passos": []}
    if motivo == "medo":
        return {"texto": "", "passos": [], "roteiro": [
            "Oi, tudo bem? Preciso resolver isto: " + titulo + ".",
            "Pode me dizer o que falta e qual o prazo?",
            "Perfeito, obrigado. Eu cuido do resto hoje."]}
    return {"texto": "Escreve numa linha o que seria \"pronto\" pra essa tarefa. Só isso.", "roteiro": [],
            "passos": ["Escrever numa linha o que é \"pronto\"", "Separar o que precisa pra fazer", "Fazer a primeira parte por 2 minutos"]}


def _remedio_ia(titulo: str, motivo: str) -> dict:
    """IA (modelo barato, ia/config.d/remedio_travou.json). Qualquer falha cai no texto padrao."""
    padrao = _remedio_padrao(titulo, motivo)
    try:
        from ia.funcoes import planejamento

        r, _ = planejamento.remedio_travou(titulo, motivo)
    except Exception:
        return padrao
    texto = _limpo(r.get("texto"), 240)
    lista = [_limpo(x, 160) for x in (r.get("lista") or []) if _limpo(x, 160)][:4]
    if motivo == "medo":
        return {"texto": "", "passos": [], "roteiro": lista or padrao["roteiro"]}
    if motivo == "sem_rumo":
        return {"texto": texto or padrao["texto"], "roteiro": [], "passos": lista or padrao["passos"]}
    return {"texto": texto or padrao["texto"], "roteiro": [], "passos": []}


def responder_travou(conn, task_id: int, motivo: str, agora: datetime | None = None) -> dict | None:
    """Um toque num dos 4 motivos. Devolve o remedio (cacheado em extras: tocar de novo nao gasta IA)."""
    if motivo not in MOTIVOS:
        return None
    t = conn.execute("SELECT id, title, extras FROM tasks WHERE id = ? AND completed_at IS NULL", (task_id,)).fetchone()
    if not t:
        return None
    extras = _extras(t["extras"])
    tr = extras.get("travou") if isinstance(extras.get("travou"), dict) else {}
    cache = tr.get("remedios") if isinstance(tr.get("remedios"), dict) else {}
    if motivo == "chato":
        remedio = {"acao": "juntar", "titulo": "Junta com algo bom",
                   "texto": "Escolhe uma coisa que tu curte e que só vale junto com essa tarefa.",
                   "premios": list(PREMIOS_SUGERIDOS), "roteiro": [], "passos": [], "botao": "Juntar com o prêmio"}
    else:
        dados = cache.get(motivo) or _remedio_ia(t["title"], motivo)
        cache[motivo] = dados
        remedio = {
            "acao": "passos" if motivo == "sem_rumo" else "comecar",
            "titulo": {"dificil": "Passo de 2 minutos", "medo": "Roteiro pronto", "sem_rumo": "O primeiro passo é"}[motivo],
            "texto": dados.get("texto") or "", "roteiro": dados.get("roteiro") or [], "passos": dados.get("passos") or [],
            "premios": [],
            "botao": {"dificil": "Começar 2 min", "medo": "Começar com o roteiro", "sem_rumo": "Virar passos da tarefa"}[motivo],
        }
    extras["travou"] = {"motivo": motivo, "em": (agora or datetime.now()).date().isoformat(), "remedios": cache}
    db.salvar_extras_tarefa(conn, task_id, extras)
    return {"motivo": motivo, **remedio}


def aplicar_remedio(conn, agora: datetime, task_id: int, acao: str, premio: str | None = None) -> dict | None:
    t = conn.execute("SELECT id, title, extras FROM tasks WHERE id = ? AND completed_at IS NULL", (task_id,)).fetchone()
    if not t:
        return None
    tr = _extras(t["extras"]).get("travou") or {}
    motivo = tr.get("motivo")
    dados = (tr.get("remedios") or {}).get(motivo) or {}
    if acao == "juntar":
        r = juntar(conn, task_id, premio or "")
        return {"ok": True, "premio": r["premio"]} if r else None
    if acao == "comecar" and motivo in ("dificil", "medo"):
        if motivo == "medo" and dados.get("roteiro"):
            passo = "Tem roteiro: começa dizendo \"" + dados["roteiro"][0] + "\""
        else:
            passo = dados.get("texto") or _remedio_padrao(t["title"], "dificil")["texto"]
        e = foco.abrir(conn, agora, t["title"], passo[:200], None, foco.PADRAO_MIN, t["id"])
        return {"ok": True, "sessao": foco.comecar(conn, agora, e["id"]) or e}
    if acao == "passos" and motivo == "sem_rumo":
        passos = [_limpo(p, 120) for p in dados.get("passos") or [] if _limpo(p, 120)][:4]
        if not passos:
            return None
        antigos = {r["title"] for r in conn.execute("SELECT title FROM subtasks WHERE task_id = ?", (task_id,)).fetchall()}
        pos = conn.execute("SELECT COALESCE(MAX(position), 0) p FROM subtasks WHERE task_id = ?", (task_id,)).fetchone()["p"]
        novos = [p for p in passos if p not in antigos]
        for p in novos:
            pos += 1
            conn.execute("INSERT INTO subtasks (task_id, title, position) VALUES (?, ?, ?)", (task_id, p, pos))
        conn.commit()
        return {"ok": True, "passos": len(novos)}
    return None


# ============================================================ Um segundo antes

def _log(conn) -> list[dict]:
    try:
        v = json.loads(db.obter_configuracao(conn, "segundo_antes_log") or "[]")
    except ValueError:
        v = []
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def voltou_na_semana(conn, agora: datetime) -> int:
    corte = (agora - timedelta(days=7)).isoformat(timespec="seconds")
    return sum(1 for x in _log(conn) if x.get("escolha") == "voltou" and str(x.get("em", "")) >= corte)


def tarefa_do_momento(conn, agora: datetime, eventos=None) -> str | None:
    s = foco.estado(conn, agora)
    if s and s["fase"] not in ("feito", "largado", "encerrada"):
        return s["titulo"]
    sug = e_agora(conn, agora, eventos, limite=1)["sugestoes"]
    return sug[0]["titulo"] if sug else None


def tela_segundo_antes(conn, agora: datetime, app_nome: str = "", eventos=None) -> dict:
    nome = _limpo(app_nome, 30)
    return {"pergunta": "Ia fazer o quê?", "tarefa": tarefa_do_momento(conn, agora, eventos),
            "app": nome or None, "voltou_semana": voltou_na_semana(conn, agora)}


def registrar_escolha(conn, agora: datetime, escolha: str, app_nome: str = "") -> dict | None:
    if escolha not in ("voltou", "seguiu"):
        return None
    log = _log(conn)
    log.append({"em": agora.isoformat(timespec="seconds"), "escolha": escolha, "app": _limpo(app_nome, 30)})
    db.definir_configuracao(conn, "segundo_antes_log", json.dumps(log[-LOG_MAX:], ensure_ascii=False))
    n = voltou_na_semana(conn, agora)
    return {"voltou_semana": n,
            "mensagem": f"Boa. Voltou pra tarefa ({n}× na semana)" if escolha == "voltou" else "Tudo bem. Pode abrir."}
