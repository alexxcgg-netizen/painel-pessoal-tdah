"""Fechamento do dia (lab v4, 2026-10-30, Grupo G): "Placar do feito" e "Pouso do dia".

PLACAR DO FEITO (card `placar_feito`): o que ele fez hoje, nao o que falta. Junta o que o painel ja
sabe (tarefa concluida, treino, voo) com o que ele conta que fez FORA do plano ("lavei a louca"),
tabela `feito_extra`. Vem sempre ANTES de qualquer pendencia.

POUSO DO DIA (card `pouso_dia`, 21h no lugar do antigo `fechar_dia`): ritual curto como checklist
pos-voo. Ate 3 passos, so os que existem de verdade: (1) o que ficou aberto, com 1 toque pra
empurrar pra amanha; (2) a primeira coisa de amanha; (3) a mochila (so se amanha tem voo, o mesmo
estado do card da vespera). No fim, "Dia pousado." e acabou: nada mais pra rolar.

Texto por template (zero IA). Tudo e fato calculado aqui.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

import cards
import conversa_proativa as cp
import db

MAX_ITENS_PLACAR = 40
MAX_TEXTO_EXTRA = 80
SUGESTOES_PADRAO = ("Lavei a louça", "Fiz uma ligação", "Arrumei a casa", "Resolvi um pepino")
LIMITE_PENDENTES = 8

# completed_at e UTC (datetime('now')); o dia dele e o de Brasilia
_DIA_CONCLUSAO = "date(completed_at, '-3 hours')"


# ------------------------------------------------------------------ placar do feito


def limpar_texto(texto) -> str:
    t = re.sub(r"\s+", " ", str(texto or "")).strip(" .,;-")
    return (t[:1].upper() + t[1:])[:MAX_TEXTO_EXTRA] if t else ""


def adicionar_extra(conn, texto, dia: date) -> dict | None:
    """Anota algo feito fora do plano. Idempotente no dia (mesmo texto, sem diferenciar caixa)."""
    t = limpar_texto(texto)
    if not t:
        return None
    # casefold em Python: o lower() do SQLite so conhece ASCII ("LOUÇA" x "louça")
    for ja in conn.execute("SELECT id, texto FROM feito_extra WHERE data = ?", (dia.isoformat(),)):
        if ja["texto"].casefold() == t.casefold():
            return {"id": ja["id"], "texto": ja["texto"], "novo": False}
    cur = conn.execute("INSERT INTO feito_extra (data, texto) VALUES (?, ?)", (dia.isoformat(), t))
    conn.commit()
    return {"id": cur.lastrowid, "texto": t, "novo": True}


def remover_extra(conn, extra_id: int) -> bool:
    cur = conn.execute("DELETE FROM feito_extra WHERE id = ?", (extra_id,))
    conn.commit()
    return cur.rowcount > 0


def feitos_do_dia(conn, dia: date) -> list[dict]:
    """[{texto, origem, rotulo, id?}] na ordem em que aconteceu: tarefas, treino, voo, extras."""
    d = dia.isoformat()
    itens: list[dict] = []
    for r in conn.execute(
        f"SELECT title FROM tasks WHERE completed_at IS NOT NULL AND {_DIA_CONCLUSAO} = ? ORDER BY completed_at", (d,)
    ):
        itens.append({"texto": r["title"], "origem": "tarefa", "rotulo": "planejado"})
    for r in conn.execute("SELECT grupo FROM treinos WHERE data = ? ORDER BY id", (d,)):
        itens.append({"texto": f"Treino de {r['grupo']}" if r["grupo"] else "Treino", "origem": "treino", "rotulo": "planejado"})
    for r in conn.execute("SELECT origem, destino FROM voos WHERE data = ? AND horas > 0 ORDER BY id", (d,)):
        rota = f"{r['origem']} → {r['destino']}" if r["origem"] else r["destino"]
        itens.append({"texto": f"Voo {rota}", "origem": "voo", "rotulo": "planejado"})
    for r in conn.execute("SELECT id, texto FROM feito_extra WHERE data = ? ORDER BY id", (d,)):
        itens.append({"texto": r["texto"], "origem": "extra", "rotulo": "fora do plano", "id": r["id"]})
    return itens[:MAX_ITENS_PLACAR]


def sugestoes_extra(conn, dia: date) -> list[str]:
    """Chips de 1 toque: o que ele mais anotou nos ultimos 60 dias, completado com os padroes.
    Sem o que ja anotou hoje."""
    desde = (dia - timedelta(days=60)).isoformat()
    ja = {r["texto"].casefold() for r in conn.execute("SELECT texto FROM feito_extra WHERE data = ?", (dia.isoformat(),))}
    contagem: dict[str, list] = {}  # casefold -> [texto, vezes, ultimo id]
    for r in conn.execute("SELECT id, texto FROM feito_extra WHERE data >= ? AND data < ? ORDER BY id", (desde, dia.isoformat())):
        c = contagem.setdefault(r["texto"].casefold(), [r["texto"], 0, 0])
        c[1] += 1
        c[2] = r["id"]
        c[0] = r["texto"]
    freq = [c[0] for c in sorted(contagem.values(), key=lambda c: (-c[1], -c[2]))]
    saida: list[str] = []
    for t in [*freq, *SUGESTOES_PADRAO]:
        if t.casefold() not in ja and t.casefold() not in {s.casefold() for s in saida}:
            saida.append(t)
    return saida[:4]


def dados_placar(conn, dia: date, hora: str | None = None) -> dict:
    itens = feitos_do_dia(conn, dia)
    return {"dia": dia.isoformat(), "hora": hora, "itens": itens, "total": len(itens),
            "sugestoes": sugestoes_extra(conn, dia)}


def card_placar(conn, dia: date, hora: str | None = None) -> dict:
    return cards.novo_card("placar_feito", dados_placar(conn, dia, hora))


def acertar_placar_feito(conn, cards_msg: list) -> None:
    """Historico: o card guardado nasce com o placar da hora; volta com o de agora (o que ele
    anotou depois tambem entra). Muda os dicts no lugar."""
    for c in cards_msg:
        if not isinstance(c, dict) or c.get("type") != "placar_feito":
            continue
        try:
            dia = date.fromisoformat(str((c.get("data") or {}).get("dia")))
        except ValueError:
            continue
        c["data"] = {**c["data"], **dados_placar(conn, dia, (c.get("data") or {}).get("hora"))}


# ------------------------------------------------------------------ pouso do dia


def _chave_pousado(dia: date) -> str:
    return f"pouso_dia_{dia.isoformat()}"


def marcar_pousado(conn, dia: date) -> None:
    db.definir_configuracao(conn, _chave_pousado(dia), "1")


def ja_pousou(conn, dia: date) -> bool:
    return db.obter_configuracao(conn, _chave_pousado(dia)) == "1"


def primeira_de_amanha(conn, hoje: date) -> dict | None:
    """O que abre o dia de amanha: o que tem horario mais cedo (voo ou tarefa); sem horario nenhum,
    a primeira tarefa da lista. {texto, hora, tipo} ou None (amanha vazio)."""
    amanha = hoje + timedelta(days=1)
    candidatos: list[tuple[str, dict]] = []
    for r in conn.execute(
        "SELECT origem, destino, hora FROM voos WHERE data = ? AND hora IS NOT NULL AND hora != '' ORDER BY hora",
        (amanha.isoformat(),),
    ):
        rota = f"{r['origem']} → {r['destino']}" if r["origem"] else r["destino"]
        candidatos.append((r["hora"], {"texto": f"Voo {rota}", "hora": r["hora"], "tipo": "voo"}))
    tarefas = conn.execute(
        "SELECT title, hora FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL AND due_date = ? "
        "ORDER BY (hora IS NULL OR hora = ''), hora, id",
        (amanha.isoformat(),),
    ).fetchall()
    for r in tarefas:
        if r["hora"]:
            candidatos.append((r["hora"], {"texto": r["title"], "hora": r["hora"], "tipo": "tarefa"}))
    if candidatos:
        return min(candidatos, key=lambda c: c[0])[1]
    if tarefas:
        return {"texto": tarefas[0]["title"], "hora": None, "tipo": "tarefa"}
    return None


def mochila_de_amanha(conn, hoje: date) -> dict | None:
    """Mochila do voo de amanha (o MESMO estado do card da vespera: /api/voos/<id>/mochila)."""
    v = conn.execute(
        "SELECT id, hora, origem, destino FROM voos WHERE data = ? AND hora IS NOT NULL AND hora != '' "
        "ORDER BY hora LIMIT 1",
        ((hoje + timedelta(days=1)).isoformat(),),
    ).fetchone()
    if not v:
        return None
    feitos = cards.mochila_feita(conn, v["id"])
    return {"voo_id": v["id"], "hora": v["hora"],
            "itens": [{"texto": t, "feito": f} for t, f in zip(cards.MOCHILA_VOO, feitos)]}


def dados_pouso(conn, hoje: date) -> dict:
    pendentes = cp.pendentes_ate(conn, hoje)
    return {
        "dia": hoje.isoformat(),
        "amanha": (hoje + timedelta(days=1)).isoformat(),
        "pendentes": pendentes[:LIMITE_PENDENTES],
        "mais": max(0, len(pendentes) - LIMITE_PENDENTES),
        "ids_adiar": [p["id"] for p in pendentes],
        "primeira": primeira_de_amanha(conn, hoje),
        "mochila": mochila_de_amanha(conn, hoje),
        "pousado": ja_pousou(conn, hoje),
    }


def card_pouso(conn, hoje: date) -> dict:
    return cards.novo_card("pouso_dia", dados_pouso(conn, hoje))


def acertar_pouso_dia(conn, cards_msg: list) -> None:
    """Historico: o card volta com o que ainda esta aberto agora e se o dia ja pousou."""
    for c in cards_msg:
        if not isinstance(c, dict) or c.get("type") != "pouso_dia":
            continue
        try:
            dia = date.fromisoformat(str((c.get("data") or {}).get("dia")))
        except ValueError:
            continue
        c["data"] = {**c["data"], **dados_pouso(conn, dia)}


_ABERTURAS = ("Hora de pousar o dia.", "Pousando o dia:", "Fim de dia, vem pousar.", "Bora pousar o dia.")


def pouso_do_dia(conn, hoje: date, hora: str | None = None) -> tuple[str, list[dict]] | None:
    """(texto, [placar_feito, pouso_dia]) pro chat - None quando o dia nao teve nada pra fechar.
    O placar vem primeiro: primeiro o que ele fez, depois o que falta."""
    placar = card_placar(conn, hoje, hora)
    pouso = card_pouso(conn, hoje)
    n = placar["data"]["total"]
    abertas = len(pouso["data"]["ids_adiar"])
    if not n and not abertas:
        return None
    abertura = _ABERTURAS[hoje.toordinal() % len(_ABERTURAS)]
    if n:
        frases = [f"{abertura} Primeiro o que tu fez: {n} {'coisa' if n == 1 else 'coisas'} hoje."]
    else:
        frases = [f"{abertura} Se fez algo fora do plano (louça, ligação), anota no card: conta."]
    if abertas:
        frases.append(f"{'Ficou' if abertas == 1 else 'Ficaram'} {abertas} em aberto: um toque empurra pra amanhã.")
    else:
        frases.append("Nada pendurado. Pode desligar a cabeça.")
    return " ".join(frases), [placar, pouso]


def resumo_push_pouso(placar: dict, pouso: dict) -> str:
    n, abertas = placar["data"]["total"], len(pouso["data"]["ids_adiar"])
    feitas = f"{n} {'coisa feita' if n == 1 else 'coisas feitas'} hoje. " if n else ""
    if abertas:
        return f"{feitas}{'Vem' if n else 'Hora de'} pousar o dia: {abertas} em aberto."
    return f"{feitas}Nada em aberto: vem pousar o dia."
