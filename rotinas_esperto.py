"""Descobre tuas rotinas (leva 06/11 "painel mais esperto", frente 7 - docs/briefings/2026-11-06-painel-esperto.md).

1. Padrao de 3 semanas -> card UMA vez propondo virar rotina (card `rotina_proposta`):
   - pelas visitas do iPhone: o mesmo lugar (apelido salvo, menos casa) no mesmo dia da semana e hora parecida
     (+-45 min da mediana) em 3 das ultimas 4 semanas, a ultima nos ultimos 8 dias. Dias do mesmo lugar com hora
     parecida viram uma proposta so ("Academia toda terca e quinta / 18:00 · ja faz 3 semanas");
   - pelas tarefas: o mesmo titulo (sem acento/maiuscula) no mesmo dia da semana em 3 semanas diferentes das
     ultimas 5, sem ser rotina ja.
   "Virar rotina" cria a tarefa recorrente (semanal:<dias>, com a hora) com 1 toque e Desfazer (entidade `tarefa`
   do desfazer de sempre, que apaga o modelo e as instancias). "Nao" = nunca mais pergunta daquele padrao.
2. Tarefa adiada 3 vezes (contador que ja existe: `tarefas_adiadas`, dia_ruim.registrar_adiamento) -> card
   `tarefa_adiada` com Quebrar em passos (a quebra da IA que ja existe, POST /api/tasks/<id>/breakdown), Mudar o
   dia (aqui: o dia menos corrido dos proximos 7, sem chuva se tiver previsao, sem voo; mesma hora se tiver e
   estiver livre) e Apagar (DELETE /api/tasks/<id>, com Desfazer). Pergunta uma vez por tarefa e marca a tarefa
   como "ja perguntada" tambem pro "Por que travou?" (Lab v4), pra mesma tarefa nao ganhar dois cards.

Um card de cada por dia, das 9h as 21h. Cada card sai com um aviso (fila de hora_certa.py: push e app).
"""
from __future__ import annotations

import json
import logging
import statistics
from datetime import date, datetime, time, timedelta

import cards
import db

log = logging.getLogger(__name__)

TIPO_ROTINA = "rotina_descoberta"
TIPO_ADIADA = "tarefa_adiada"
JANELA = (time(9, 0), time(21, 0))
SEMANAS_JANELA_LUGAR = 4
SEMANAS_JANELA_TAREFA = 5
MIN_SEMANAS = 3
RECENTE_DIAS = 8
TOLERANCIA_MIN = 45
JUNTAR_DIAS_MIN = 30
ARREDONDA_MIN = 15
LIMITE_ADIADA = 3
DIAS_MUDAR = 7
PROPOSTAS = "rotinas_propostas"  # {chave: {"dados": {...}, "em": iso, "resposta": None|"sim"|"nao"}}
DIAS = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")
DIAS_CURTO = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")


def _na_janela(agora: datetime) -> bool:
    return JANELA[0] <= agora.time() <= JANELA[1]


def _propostas(conn) -> dict:
    try:
        p = json.loads(db.obter_configuracao(conn, PROPOSTAS) or "{}")
    except ValueError:
        return {}
    return p if isinstance(p, dict) else {}


def _salvar_propostas(conn, p: dict) -> None:
    db.definir_configuracao(conn, PROPOSTAS, json.dumps(p, ensure_ascii=False))


def _hm(minutos: float) -> str:
    m = int(round(minutos / ARREDONDA_MIN) * ARREDONDA_MIN) % (24 * 60)
    return f"{m // 60:02d}:{m % 60:02d}"


def _min_do_dt(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute


def dias_texto(dias: list[int]) -> str:
    """[1, 3] -> 'toda terça e quinta'; [5] -> 'todo sábado'; [1, 5] -> 'toda terça e todo sábado'."""
    def artigo(d):
        return "todo" if d >= 5 else "toda"

    dias = sorted(dias)
    if all(artigo(d) == artigo(dias[0]) for d in dias):
        nomes = [DIAS[d] for d in dias]
        corpo = nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " e " + nomes[-1]
        return f"{artigo(dias[0])} {corpo}"
    partes = [f"{artigo(d)} {DIAS[d]}" for d in dias]
    return ", ".join(partes[:-1]) + " e " + partes[-1]


def _ja_e_rotina(conn, nome_norm: str) -> bool:
    import vida

    for r in conn.execute("SELECT title FROM tasks WHERE recorrencia IS NOT NULL AND due_date IS NULL").fetchall():
        t = vida.normalizar_nome(r["title"])
        if t == nome_norm or (nome_norm and nome_norm in t.split()):
            return True
    return False


def _cluster(minutos: list[int]) -> list[int]:
    """Os horarios que ficam a +-45 min da mediana."""
    if not minutos:
        return []
    med = statistics.median(minutos)
    return [m for m in minutos if abs(m - med) <= TOLERANCIA_MIN]


def _juntar(grupos: dict, chave_base: str) -> list[dict]:
    """{dia: [(data, minuto)]} de um mesmo lugar/titulo -> propostas (dias com hora parecida juntos)."""
    validos = []
    for dia, ocorr in grupos.items():
        mins = _cluster([m for _, m in ocorr])
        datas = sorted({d for d, m in ocorr if m in mins})
        if len(datas) < MIN_SEMANAS:
            continue
        validos.append({"dia": dia, "med": statistics.median(mins), "datas": datas})
    propostas = []
    for v in sorted(validos, key=lambda x: x["med"]):
        alvo = next((p for p in propostas if abs(p["med"] - v["med"]) <= JUNTAR_DIAS_MIN), None)
        if alvo:
            alvo["dias"].append(v["dia"])
            alvo["datas"] += v["datas"]
            alvo["meds"].append(v["med"])
            alvo["med"] = statistics.median(alvo["meds"])
        else:
            propostas.append({"dias": [v["dia"]], "datas": list(v["datas"]), "meds": [v["med"]], "med": v["med"]})
    saida = []
    for p in propostas:
        semanas = len({date.fromisoformat(d).isocalendar()[:2] for d in p["datas"]})
        dias = sorted(p["dias"])
        saida.append({"chave": f"{chave_base}:{','.join(map(str, dias))}", "dias": dias, "hora": _hm(p["med"]),
                      "semanas": semanas})
    return saida


def padroes_lugar(conn, agora: datetime) -> list[dict]:
    try:
        linhas = conn.execute(
            "SELECT lugar, chegada FROM visitas WHERE lugar IS NOT NULL AND lugar != 'casa' AND chegada IS NOT NULL "
            "AND chegada >= ? AND chegada < ?",
            ((agora - timedelta(weeks=SEMANAS_JANELA_LUGAR)).isoformat(timespec="seconds"),
             agora.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")),
        ).fetchall()
    except Exception:  # noqa: BLE001 - banco sem visitas
        return []
    por_lugar: dict[str, dict[int, list]] = {}
    for r in linhas:
        try:
            dt = datetime.fromisoformat(r["chegada"])
        except ValueError:
            continue
        lista = por_lugar.setdefault(r["lugar"], {}).setdefault(dt.weekday(), [])
        if not any(d == dt.date().isoformat() for d, _ in lista):  # uma por dia
            lista.append((dt.date().isoformat(), _min_do_dt(dt)))
    saida = []
    recente = (agora.date() - timedelta(days=RECENTE_DIAS)).isoformat()
    for lugar, grupos in por_lugar.items():
        nome, _ = _nome_lugar(conn, lugar)
        for p in _juntar(grupos, f"lugar:{lugar}"):
            ultimas = [d for dia in p["dias"] for d, _ in grupos[dia]]
            if max(ultimas) < recente or _ja_e_rotina(conn, _norm(nome)):
                continue
            saida.append({**p, "fonte": "lugar", "lugar": lugar, "tarefa_titulo": nome[:1].upper() + nome[1:],
                          "titulo": f"{nome[:1].upper() + nome[1:]} {dias_texto(p['dias'])}",
                          "texto": f"Vi tu chegar {_em_lugar(conn, lugar)} nesses dias. Viro rotina? Aí eu já lembro "
                                   "e conto a semana."})
    return saida


def _norm(t: str) -> str:
    import vida

    return vida.normalizar_nome(t)


def _nome_lugar(conn, apelido: str) -> tuple[str, str]:
    try:
        import onde_estou

        titulos = [r["title"] for r in conn.execute("SELECT title FROM tasks ORDER BY id DESC LIMIT 200").fetchall()]
        return onde_estou.nome_e_genero(apelido, titulos)
    except Exception:  # noqa: BLE001
        return apelido, "m"


def _em_lugar(conn, apelido: str) -> str:
    try:
        import onde_estou

        nome, genero = _nome_lugar(conn, apelido)
        return onde_estou._em(nome, genero)
    except Exception:  # noqa: BLE001
        return f"em {apelido}"


def padroes_tarefa(conn, agora: datetime) -> list[dict]:
    desde = (agora.date() - timedelta(weeks=SEMANAS_JANELA_TAREFA)).isoformat()
    linhas = conn.execute(
        "SELECT title, due_date, hora FROM tasks WHERE recorrencia IS NULL AND recorrente_origem_id IS NULL "
        "AND due_date IS NOT NULL AND due_date >= ? AND due_date <= ? ORDER BY due_date",
        (desde, agora.date().isoformat()),
    ).fetchall()
    por_titulo: dict[str, dict] = {}
    for r in linhas:
        n = _norm(r["title"])
        if not n:
            continue
        try:
            d = date.fromisoformat(r["due_date"])
        except ValueError:
            continue
        hora = r["hora"] or ""
        try:
            h, m = hora.split(":")
            minuto = int(h) * 60 + int(m)
        except ValueError:
            minuto = None
        g = por_titulo.setdefault(n, {"titulo": r["title"], "dias": {}, "horas": {}})
        g["titulo"] = r["title"]
        lista = g["dias"].setdefault(d.weekday(), [])
        if not any(x == d.isoformat() for x, _ in lista):
            lista.append((d.isoformat(), minuto if minuto is not None else 0))
            g["horas"].setdefault(d.weekday(), []).append(minuto)
    saida = []
    recente = (agora.date() - timedelta(days=RECENTE_DIAS)).isoformat()
    for n, g in por_titulo.items():
        if _ja_e_rotina(conn, n):
            continue
        for p in _juntar(g["dias"], f"tarefa:{n}"):
            ultimas = [d for dia in p["dias"] for d, _ in g["dias"][dia]]
            if max(ultimas) < recente:
                continue
            horas = [h for dia in p["dias"] for h in g["horas"].get(dia, [])]
            com_hora = [h for h in horas if h is not None]
            hora = p["hora"] if len(com_hora) >= MIN_SEMANAS else None
            titulo = g["titulo"].strip()
            saida.append({**p, "hora": hora, "fonte": "tarefa", "tarefa_titulo": titulo,
                          "titulo": f"“{titulo}” {dias_texto(p['dias'])}",
                          "texto": "Tu marcou isso nesses dias. Viro rotina? Aí ela já aparece sozinha."})
    return saida


def propostas_novas(conn, agora: datetime) -> list[dict]:
    feitas = _propostas(conn)
    return [p for p in padroes_lugar(conn, agora) + padroes_tarefa(conn, agora) if p["chave"] not in feitas]


def card_rotina(p: dict) -> dict:
    sub = f"{p['hora']} · já faz {p['semanas']} semanas" if p.get("hora") else f"já faz {p['semanas']} semanas"
    return cards.novo_card("rotina_proposta", {
        "chave": p["chave"], "titulo": p["titulo"], "sub": sub, "texto": p["texto"], "dias": p["dias"],
        "hora": p.get("hora"), "semanas": p["semanas"], "fonte": p["fonte"], "tarefa_titulo": p["tarefa_titulo"],
    })


def responder_rotina(conn, chave: str, resposta: str, agora: datetime) -> dict | None:
    """"sim" cria a rotina (com o dado que o SERVIDOR guardou na proposta, nunca o do cliente); "nao" nunca mais
    pergunta. None = proposta desconhecida ou ja respondida."""
    props = _propostas(conn)
    p = props.get(chave)
    if not isinstance(p, dict) or p.get("resposta") or resposta not in ("sim", "nao"):
        return None
    d = p.get("dados") or {}
    p["resposta"] = resposta
    p["respondida_em"] = agora.isoformat(timespec="minutes")
    if resposta == "nao":
        _salvar_propostas(conn, props)
        return {"ok": True, "texto": "Ok, não pergunto mais desse."}
    dias = [x for x in d.get("dias") or [] if isinstance(x, int) and 0 <= x <= 6]
    titulo = str(d.get("tarefa_titulo") or "").strip()[:120]
    if not dias or not titulo:
        return None
    padrao = "semanal:" + ",".join(str(x) for x in sorted(set(dias)))
    cur = conn.execute("INSERT INTO tasks (title, recorrencia, hora) VALUES (?, ?, ?)", (titulo, padrao, d.get("hora")))
    tid = cur.lastrowid
    conn.commit()
    _salvar_propostas(conn, props)
    token = db.criar_acao_desfazer(conn, [{"entidade": "tarefa", "id": tid}])
    nomes = " e ".join([", ".join(DIAS[x] for x in sorted(dias)[:-1]), DIAS[sorted(dias)[-1]]]) if len(dias) > 1 else DIAS[dias[0]]
    hora = f", {d['hora']}" if d.get("hora") else ""
    return {"ok": True, "id": tid, "token": token, "texto": f"Virou rotina: {nomes}{hora}."}


# ------------------------------------------------------------------ adiada 3 vezes

def adiadas(conn) -> list[dict]:
    saida = []
    for r in conn.execute(
        """SELECT t.id, t.title, t.extras, COUNT(*) AS n FROM tarefas_adiadas a JOIN tasks t ON t.id = a.task_id
           WHERE t.completed_at IS NULL AND t.arquivada_em IS NULL AND t.recorrencia IS NULL
           GROUP BY t.id HAVING COUNT(*) >= ? ORDER BY COUNT(*) DESC, t.id""", (LIMITE_ADIADA,)).fetchall():
        try:
            ex = json.loads(r["extras"]) if r["extras"] else {}
        except (TypeError, ValueError):
            ex = {}
        if not isinstance(ex, dict) or ex.get("adiada3") or ex.get("travou"):
            continue
        saida.append({"id": r["id"], "titulo": r["title"], "adiadas": r["n"]})
    return saida


def card_adiada(t: dict) -> dict:
    return cards.novo_card("tarefa_adiada", {"task_id": t["id"], "titulo": t["titulo"], "adiadas": t["adiadas"]})


def _marcar_perguntada(conn, task_id: int, agora: datetime) -> None:
    ex = db.extras_tarefa(conn, task_id)
    ex["adiada3"] = {"em": agora.date().isoformat()}
    ex.setdefault("travou", {"motivo": None})  # o "Por que travou?" nao pergunta da mesma tarefa
    db.salvar_extras_tarefa(conn, task_id, ex)


def _carga(conn, dias: list[date]) -> dict[str, int]:
    carga = {d.isoformat(): 0 for d in dias}
    for r in conn.execute(
        "SELECT due_date, COUNT(*) n FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL "
        "AND due_date BETWEEN ? AND ? GROUP BY due_date", (dias[0].isoformat(), dias[-1].isoformat())).fetchall():
        carga[r["due_date"]] = r["n"]
    return carga


def _previsao(cidade: str | None, dias: int):
    """[{data, chuva_pct}] da cidade padrao, ou None sem cidade/rede."""
    import os

    import clima

    cidade = (cidade if cidade is not None else os.environ.get("CIDADE_PADRAO", "")).strip()
    if not cidade:
        return None
    try:
        g = clima.geocodificar_cidade(cidade)
        if not g:
            return None
        return clima.previsao_proximos_dias(g["latitude"], g["longitude"], dias)
    except Exception:  # noqa: BLE001
        return None


def escolher_dia(conn, task_id: int, agora: datetime, previsao=None) -> dict | None:
    """O dia menos corrido dos proximos 7 (empate: o mais perto), sem voo e sem chuva quando tem previsao.
    Hora: a mesma se tinha e estiver livre (nenhuma tarefa a menos de 1 h); tinha hora e nao ta livre: a proxima
    hora cheia livre entre 8h e 20h; sem hora continua sem."""
    import agenda
    import clima

    t = conn.execute("SELECT id, title, due_date, hora FROM tasks WHERE id = ? AND completed_at IS NULL", (task_id,)).fetchone()
    if not t:
        return None
    dias = [agora.date() + timedelta(days=i) for i in range(1, DIAS_MUDAR + 1)]
    com_voo = {r["data"] for r in conn.execute("SELECT data FROM voos WHERE data BETWEEN ? AND ?",
                                               (dias[0].isoformat(), dias[-1].isoformat())).fetchall()}
    prev = previsao if previsao is not None else _previsao(None, DIAS_MUDAR + 1)
    chuva = {p["data"]: p.get("chuva_pct") for p in (prev or []) if isinstance(p, dict)}
    secos = [d for d in dias if d.isoformat() not in com_voo
             and not (isinstance(chuva.get(d.isoformat()), (int, float)) and chuva[d.isoformat()] >= clima.LIMITE_ALERTA_CHUVA)]
    candidatos = secos or [d for d in dias if d.isoformat() not in com_voo] or dias
    escolha = agenda.sugerir_dia_menos_corrido(_carga(conn, candidatos), candidatos)
    data = escolha["data"]
    hora = t["hora"]
    if hora:
        ocupadas = []
        for r in conn.execute("SELECT hora FROM tasks WHERE due_date = ? AND hora IS NOT NULL AND id != ? "
                              "AND completed_at IS NULL", (data, task_id)).fetchall():
            try:
                h, m = r["hora"].split(":")
                ocupadas.append(int(h) * 60 + int(m))
            except ValueError:
                continue

        def livre(minuto):
            return all(abs(minuto - o) >= 60 for o in ocupadas)

        h, m = (int(x) for x in hora.split(":"))
        if not livre(h * 60 + m):
            achada = next((x for x in range(8 * 60, 20 * 60 + 1, 60) if livre(x)), None)
            hora = f"{achada // 60:02d}:00" if achada is not None else hora
    sem_chuva = bool(chuva) and data in chuva and isinstance(chuva[data], (int, float))
    return {"data": data, "hora": hora, "dia_semana": DIAS[date.fromisoformat(data).weekday()],
            "sem_chuva": sem_chuva, "carga": escolha.get("carga", 0)}


def mudar_dia(conn, task_id: int, agora: datetime, previsao=None) -> dict | None:
    """Aplica o dia escolhido, com Desfazer (edicao em tasks). Nao conta como adiamento (foi escolha dele)."""
    t = conn.execute("SELECT id, title, due_date, hora FROM tasks WHERE id = ? AND completed_at IS NULL", (task_id,)).fetchone()
    if not t:
        return None
    e = escolher_dia(conn, task_id, agora, previsao)
    if not e:
        return None
    antes = {"due_date": t["due_date"], "hora": t["hora"]}
    conn.execute("UPDATE tasks SET due_date = ?, hora = ? WHERE id = ?", (e["data"], e["hora"], task_id))
    conn.commit()
    token = db.criar_acao_desfazer(conn, [{"entidade": "edicao", "tabela": "tasks", "id": task_id, "antes": antes}])
    d = date.fromisoformat(e["data"])
    quando = f"{e['dia_semana']} ({d:%d/%m})" + (f" às {e['hora']}" if e["hora"] else "")
    porque = []
    if e["carga"] == 0:
        porque.append("tu tá livre")
    else:
        porque.append("é o dia mais leve da semana")
    if e["sem_chuva"]:
        porque.append("sem chuva")
    return {"ok": True, "token": token, "data": e["data"], "hora": e["hora"],
            "texto": f"Passei pra {quando}, que {' e '.join(porque)}."}


# ------------------------------------------------------------------ o passo

def verificar(conn, agora: datetime) -> list:
    """Passo de conversa_proativa.verificar: no maximo 1 rotina e 1 adiada por dia, das 9h as 21h. O push sai
    pela fila de hora_certa (devolve [])."""
    import hora_certa

    if not _na_janela(agora):
        return []
    ate = agora.replace(hour=21, minute=30, second=0, microsecond=0)
    if not db.ja_notificou_hoje(conn, "rotina_descoberta_chat"):
        try:
            novas = propostas_novas(conn, agora)
        except Exception:
            log.exception("rotinas_esperto: padroes falhou")
            novas = []
        if novas:
            p = novas[0]
            props = _propostas(conn)
            props[p["chave"]] = {"dados": {k: p[k] for k in ("dias", "hora", "tarefa_titulo", "fonte", "semanas")},
                                 "em": agora.isoformat(timespec="minutes"), "resposta": None}
            _salvar_propostas(conn, props)
            c = card_rotina(p)
            texto = f"{p['titulo']}, {c['data']['sub']}. Viro rotina?"
            env = cards.envelope([c], texto, [])
            db.salvar_mensagem_chat(conn, "assistant", texto, env["cards"])
            db.marcar_notificado(conn, "rotina_descoberta_chat")
            hora_certa.enfileirar(conn, TIPO_ROTINA, hora_certa.proximo_ref(conn), f"{p['titulo']}?",
                                  "Viro rotina? Um toque no chat.", agora, ate, chave=f"rotina:{p['chave']}")
    if not db.ja_notificou_hoje(conn, "tarefa_adiada_chat"):
        lista = adiadas(conn)
        if lista:
            t = lista[0]
            _marcar_perguntada(conn, t["id"], agora)
            texto = f"“{t['titulo']}” já foi adiada {t['adiadas']} vezes. O que eu faço com ela?"
            env = cards.envelope([card_adiada(t)], texto, [])
            db.salvar_mensagem_chat(conn, "assistant", texto, env["cards"])
            db.marcar_notificado(conn, "tarefa_adiada_chat")
            titulo = f"“{hora_certa.titulo_frase(t['titulo'])}” já foi adiada {t['adiadas']} vezes"
            hora_certa.enfileirar(conn, TIPO_ADIADA, hora_certa.proximo_ref(conn), titulo,
                                  "Quebro em passos, mudo o dia ou apago? Um toque no chat.", agora, ate,
                                  chave=f"adiada:{t['id']}")
    return []
