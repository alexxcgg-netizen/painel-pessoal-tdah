"""Quiz de aviacao com repeticao espacada (2026-10-13) - o "professor" do chat.

Perguntas no estilo da banca ANAC (enunciado + 4 alternativas, uma certa), SEMPRE dentro
dos temas fixos que o Alex escolheu (estudo.TEMAS) - a IA escreve a pergunta na chamada
da ferramenta, este modulo so guarda, corrige e agenda a revisao. Nenhuma chamada extra
de IA.

Repeticao espacada no esquema de caixas de Leitner, por pergunta:
  - errou -> volta pra caixa 0 e reaparece AMANHA;
  - acertou -> sobe uma caixa e o intervalo cresce: 3, 7, 14, 30, 60 dias.
A pergunta que ele errou e a que mais volta - e a revisao (revisar_pendente) puxa
primeiro a mais atrasada.

Responder de novo uma pergunta que ja foi respondida e ainda nao venceu (ex: clicar num
card antigo do historico) devolve o resultado guardado sem mexer na agenda - senao dava
pra "farmar" acerto relendo a explicacao.
"""

import json
import unicodedata
from datetime import date, datetime, timedelta

import estudo

INTERVALOS_ACERTO = (3, 7, 14, 30, 60)  # dias, pela caixa nova (1..5)
CAIXA_MAX = len(INTERVALOS_ACERTO)
LETRAS = "ABCD"
LIMITE_ENUNCIADO = 600
LIMITE_ALTERNATIVA = 220
LIMITE_EXPLICACAO = 900


def criar_tabela(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS estudo_perguntas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tema TEXT NOT NULL,
            enunciado TEXT NOT NULL,
            alternativas TEXT NOT NULL,
            correta INTEGER NOT NULL,
            explicacao TEXT NOT NULL,
            caixa INTEGER NOT NULL DEFAULT 0,
            proxima_revisao TEXT,
            acertos INTEGER NOT NULL DEFAULT 0,
            erros INTEGER NOT NULL DEFAULT 0,
            ultima_escolha INTEGER,
            ultimo_acerto INTEGER,
            respondida_em TEXT,
            perguntada_em TEXT NOT NULL DEFAULT (datetime('now')),
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def agendar(caixa: int, acertou: bool, hoje: date) -> tuple[int, date]:
    """(caixa nova, proxima revisao) - Leitner puro, testavel."""
    if not acertou:
        return 0, hoje + timedelta(days=1)
    nova = min(max(0, int(caixa)) + 1, CAIXA_MAX)
    return nova, hoje + timedelta(days=INTERVALOS_ACERTO[nova - 1])


def _agora() -> str:
    # mesmo formato em perguntada_em e respondida_em (as duas sao comparadas como texto)
    return datetime.now().isoformat(timespec="seconds")


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _tema_valido(tema) -> str | None:
    """Aceita o nome exato, sem acento ou so a primeira palavra ('Regulamentação' ->
    'Regulamentacao (RBAC/RBHA)', 'meteorologia' -> 'Meteorologia aeronautica')."""
    t = _sem_acento(str(tema or "").strip().lower())
    if not t:
        return None
    for nome in estudo.TEMAS:
        n = _sem_acento(nome.lower())
        primeira = n.split(" ")[0]
        if n == t or n.startswith(t) or t.startswith(primeira):
            return nome
    return None


def letra_pra_indice(valor) -> int | None:
    """'b', 'B', 'letra b', 1 -> 1. None se nao der pra entender."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor if 0 <= valor < 4 else None
    s = str(valor or "").strip().upper()
    s = s.replace("LETRA", "").replace("ALTERNATIVA", "").strip(" .:)-(")
    if len(s) == 1 and s in LETRAS:
        return LETRAS.index(s)
    if s.isdigit() and 0 <= int(s) < 4:
        return int(s)
    return None


def validar_pergunta(entrada: dict) -> tuple[dict | None, str | None]:
    tema = _tema_valido(entrada.get("tema"))
    if not tema:
        return None, f"tema tem que ser um destes: {', '.join(estudo.TEMAS)}"
    enunciado = str(entrada.get("enunciado") or "").strip()
    if len(enunciado) < 10:
        return None, "enunciado vazio ou curto demais"
    alts = entrada.get("alternativas")
    if not isinstance(alts, list) or len(alts) != 4:
        return None, "precisa de exatamente 4 alternativas"
    alts = [str(a or "").strip()[:LIMITE_ALTERNATIVA] for a in alts]
    if any(not a for a in alts) or len({a.lower() for a in alts}) != 4:
        return None, "as 4 alternativas precisam ser preenchidas e diferentes"
    correta = letra_pra_indice(entrada.get("correta"))
    if correta is None:
        return None, "correta tem que ser 0-3 (ou A-D)"
    explicacao = str(entrada.get("explicacao") or "").strip()
    if len(explicacao) < 10:
        return None, "falta a explicacao da resposta certa"
    return {
        "tema": tema,
        "enunciado": enunciado[:LIMITE_ENUNCIADO],
        "alternativas": alts,
        "correta": correta,
        "explicacao": explicacao[:LIMITE_EXPLICACAO],
    }, None


def criar(conn, entrada: dict) -> dict:
    criar_tabela(conn)
    p, erro = validar_pergunta(entrada)
    if erro:
        return {"erro": erro}
    cur = conn.execute(
        "INSERT INTO estudo_perguntas (tema, enunciado, alternativas, correta, explicacao, perguntada_em) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (p["tema"], p["enunciado"], json.dumps(p["alternativas"], ensure_ascii=False), p["correta"], p["explicacao"],
         _agora()),
    )
    conn.commit()
    return {"id": cur.lastrowid, **p}


def _linha(conn, pergunta_id) -> dict | None:
    criar_tabela(conn)
    try:
        r = conn.execute("SELECT * FROM estudo_perguntas WHERE id = ?", (int(pergunta_id),)).fetchone()
    except (TypeError, ValueError):
        return None
    if not r:
        return None
    d = dict(r)
    try:
        d["alternativas"] = json.loads(d["alternativas"])
    except (TypeError, ValueError):
        d["alternativas"] = []
    return d


def dados_card(p: dict, revisao: bool = False, resultado: dict | None = None) -> dict:
    """O que vai pro card. Sem a resposta certa enquanto ele nao respondeu."""
    data = {
        "id": p["id"],
        "tema": p["tema"],
        "enunciado": p["enunciado"],
        "alternativas": p["alternativas"],
        "caixa": p.get("caixa") or 0,
        "caixa_max": CAIXA_MAX,
        "revisao": bool(revisao),
    }
    if resultado:
        data["resposta"] = resultado
    return data


def ultima_aberta(conn) -> dict | None:
    """A pergunta mais recente ainda sem resposta (pra 'e a B' por voz sem id)."""
    criar_tabela(conn)
    r = conn.execute(
        "SELECT id FROM estudo_perguntas WHERE respondida_em IS NULL OR respondida_em < perguntada_em "
        "ORDER BY perguntada_em DESC, id DESC LIMIT 1"
    ).fetchone()
    return _linha(conn, r["id"]) if r else None


def responder(conn, pergunta_id, escolha, hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    p = _linha(conn, pergunta_id) if pergunta_id not in (None, "") else ultima_aberta(conn)
    if not p:
        return {"erro": "não achei essa pergunta"}
    idx = letra_pra_indice(escolha)
    if idx is None:
        return {"erro": "resposta tem que ser A, B, C ou D"}
    respondida = p.get("respondida_em") and p["respondida_em"] >= p["perguntada_em"]
    ainda_nao_venceu = p.get("proxima_revisao") and p["proxima_revisao"] > hoje.isoformat()
    base = {
        "id": p["id"],
        "escolhida": idx,
        "correta": p["correta"],
        "correta_letra": LETRAS[p["correta"]],
        "explicacao": p["explicacao"],
    }
    if respondida and ainda_nao_venceu:
        return {**base, "acertou": idx == p["correta"], "caixa": p["caixa"],
                "proxima_revisao": p["proxima_revisao"], "repetida": True}
    acertou = idx == p["correta"]
    caixa, proxima = agendar(p["caixa"], acertou, hoje)
    conn.execute(
        "UPDATE estudo_perguntas SET caixa = ?, proxima_revisao = ?, acertos = acertos + ?, erros = erros + ?, "
        "ultima_escolha = ?, ultimo_acerto = ?, respondida_em = ? WHERE id = ?",
        (caixa, proxima.isoformat(), int(acertou), int(not acertou), idx, int(acertou),
         _agora(), p["id"]),
    )
    conn.commit()
    return {**base, "acertou": acertou, "caixa": caixa, "proxima_revisao": proxima.isoformat(), "repetida": False}


def revisar_pendente(conn, hoje: date | None = None, tema=None) -> dict | None:
    """A revisao mais atrasada (vencida ate hoje), ja marcada como perguntada agora."""
    hoje = hoje or date.today()
    criar_tabela(conn)
    filtro, args = "", [hoje.isoformat()]
    t = _tema_valido(tema)
    if t:
        filtro, args = " AND tema = ?", [hoje.isoformat(), t]
    r = conn.execute(
        "SELECT id FROM estudo_perguntas WHERE proxima_revisao IS NOT NULL AND proxima_revisao <= ?" + filtro +
        " ORDER BY proxima_revisao, caixa, id LIMIT 1",
        args,
    ).fetchone()
    if not r:
        return None
    conn.execute("UPDATE estudo_perguntas SET perguntada_em = ? WHERE id = ?",
                 (_agora(), r["id"]))
    conn.commit()
    return _linha(conn, r["id"])


def panorama(conn, hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    criar_tabela(conn)
    vencidas = conn.execute(
        "SELECT tema, COUNT(*) n FROM estudo_perguntas WHERE proxima_revisao IS NOT NULL AND proxima_revisao <= ? "
        "GROUP BY tema ORDER BY n DESC", (hoje.isoformat(),)
    ).fetchall()
    semana = conn.execute(
        "SELECT COALESCE(SUM(ultimo_acerto), 0) a, COUNT(*) n FROM estudo_perguntas "
        "WHERE respondida_em >= ?", ((hoje - timedelta(days=7)).isoformat(),)
    ).fetchone()
    por_tema = conn.execute(
        "SELECT tema, SUM(acertos) a, SUM(erros) e FROM estudo_perguntas GROUP BY tema"
    ).fetchall()
    return {
        "vencidas": {r["tema"]: r["n"] for r in vencidas},
        "semana": {"acertos": semana["a"], "respondidas": semana["n"]},
        "por_tema": {r["tema"]: {"acertos": r["a"] or 0, "erros": r["e"] or 0} for r in por_tema},
    }


def linha_contexto(conn, hoje: date | None = None) -> str | None:
    """Pro system prompt: revisoes vencidas e o aproveitamento da semana (so se ele ja usa)."""
    try:
        pan = panorama(conn, hoje)
    except Exception:
        return None
    if not pan["vencidas"] and not pan["semana"]["respondidas"]:
        return None
    partes = []
    if pan["vencidas"]:
        total = sum(pan["vencidas"].values())
        temas = ", ".join(f"{t} {n}" for t, n in pan["vencidas"].items())
        partes.append(f"{total} pergunta(s) de revisão vencida(s) ({temas})")
    if pan["semana"]["respondidas"]:
        partes.append(f"acertou {pan['semana']['acertos']} de {pan['semana']['respondidas']} nos últimos 7 dias")
    return "Quiz de aviação: " + "; ".join(partes)
