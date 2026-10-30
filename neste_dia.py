"""Neste dia (Laboratorio v4, Grupo D, 2026-10-30): "Há 1 ano: primeiro voo de instrução. Há 1 mês:
supino 75 kg (hoje 85)." Puxa do historico que o painel ja guarda, so o que e PROGRESSO: voos
(o primeiro registrado ganha destaque) e carga de treino que subiu. Dia comum, sem nada bom, nao
devolve nada (e o card nao aparece). Zero IA: tudo calculado aqui.

Janela de +-2 dias em volta da data exata (voo nao e diario) e cada linha mostra a data real, pra
nunca dizer "há 1 ano" de um dia que nao foi.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta

import cards
import db

MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro")
# (meses atras, rotulo) - do mais antigo pro mais novo, como na demo
DISTANCIAS = ((24, "Há 2 anos"), (12, "Há 1 ano"), (6, "Há 6 meses"), (3, "Há 3 meses"), (1, "Há 1 mês"))
JANELA_DIAS = 2
MAX_MARCOS = 4

JANELA_MANHA = (time(7, 30), time(11, 0))
ESPACO_DIAS = 3  # no maximo uma vez a cada 3 dias: "as vezes", nao todo dia


def _menos_meses(d: date, n: int) -> date:
    m = d.year * 12 + (d.month - 1) - n
    ano, mes = divmod(m, 12)
    mes += 1
    return date(ano, mes, min(d.day, calendar.monthrange(ano, mes)[1]))


def _kg(v: float) -> str:
    return (f"{v:.1f}".rstrip("0").rstrip(".") if v != int(v) else str(int(v))).replace(".", ",") + " kg"


def _horas(h) -> str:
    try:
        return f"{float(h):.1f}".replace(".", ",") + " h"
    except (TypeError, ValueError):
        return ""


def rotulo_data(d: date) -> str:
    return f"{d.day} de {MESES[d.month - 1]}"


def _curto(d: date) -> str:
    return f"{d:%d/%m/%Y}"


def _voos(conn, de: date, ate: date, primeiro: str | None) -> list[dict]:
    saida = []
    for r in conn.execute(
        "SELECT data, origem, destino, horas, observacao FROM voos WHERE data >= ? AND data <= ? ORDER BY data",
        (de.isoformat(), ate.isoformat()),
    ):
        rota = f"{r['origem']} → {r['destino']}" if r["origem"] else str(r["destino"])
        h = _horas(r["horas"])
        if primeiro and r["data"] == primeiro:
            texto = f"Primeiro voo registrado: {rota}" + (f", {h}" if h else "") + "."
        else:
            texto = f"Voo {rota}" + (f", {h}" if h else "") + "."
        obs = " ".join(str(r["observacao"] or "").split())
        if obs and len(obs) <= 60:
            texto += f" \"{obs}\"."
        saida.append({"data": r["data"], "texto": texto, "icone": "voo"})
    return saida


def _cargas(conn, de: date, ate: date) -> list[dict]:
    """Exercicios cuja carga naquela janela era menor que a de hoje: 'Supino 75 kg. Hoje: 85 kg.'"""
    saida = []
    maior: dict[str, dict] = {}
    for r in conn.execute(
        "SELECT exercicio, nome, carga_num, data FROM treino_cargas WHERE data >= ? AND data <= ? ORDER BY data, id",
        (de.isoformat(), ate.isoformat()),
    ):
        atual = maior.get(r["exercicio"])
        if not atual or r["carga_num"] >= atual["kg"]:
            maior[r["exercicio"]] = {"nome": r["nome"], "kg": r["carga_num"], "data": r["data"]}
    for chave, antes in maior.items():
        hoje_ = conn.execute(
            "SELECT carga_num FROM treino_cargas WHERE exercicio = ? ORDER BY data DESC, id DESC LIMIT 1", (chave,)
        ).fetchone()
        if hoje_ and hoje_["carga_num"] > antes["kg"]:
            saida.append({
                "data": antes["data"], "icone": "saude",
                "texto": f"{str(antes['nome']).strip().capitalize()} {_kg(antes['kg'])}. Hoje: {_kg(hoje_['carga_num'])}.",
            })
    return saida


def marcos(conn, hoje: date) -> list[dict]:
    """[{rotulo, data, texto, icone}] - do mais antigo pro mais novo, no maximo MAX_MARCOS."""
    primeiro = conn.execute("SELECT MIN(data) d FROM voos").fetchone()["d"]
    saida: list[dict] = []
    for meses, rotulo in DISTANCIAS:
        alvo = _menos_meses(hoje, meses)
        de, ate = alvo - timedelta(days=JANELA_DIAS), alvo + timedelta(days=JANELA_DIAS)
        if ate >= hoje:
            continue
        itens = _voos(conn, de, ate, primeiro) + _cargas(conn, de, ate)
        for it in itens[:2]:
            try:
                d = date.fromisoformat(it["data"])
            except ValueError:
                continue
            saida.append({"rotulo": rotulo, "data": it["data"], "quando": _curto(d), "texto": it["texto"], "icone": it["icone"]})
    return saida[:MAX_MARCOS]


def dados(conn, hoje: date) -> dict | None:
    itens = marcos(conn, hoje)
    if not itens:
        return None
    return {"dia": hoje.isoformat(), "rotulo": rotulo_data(hoje), "itens": itens}


def card(conn, hoje: date | None = None):
    hoje = hoje or date.today()
    d = dados(conn, hoje)
    return cards.novo_card("neste_dia", d) if d else None


# ------------------------------------------------------------------ chat proativo

FRASES = (
    "Olha o caminho que tu já andou.",
    "Dia de olhar pra trás um segundo.",
    "Tu andou mais do que parece. Olha só.",
)


def na_manha(conn, agora: datetime):
    """De manha, so se a data tem algo bom e nao saiu nos ultimos dias: publica o card no chat
    (sem push - e um agrado, nao um aviso). Devolve [] sempre (nada pro push)."""
    if not (JANELA_MANHA[0] <= agora.time() <= JANELA_MANHA[1]):
        return []
    if db.ja_notificou_hoje(conn, "neste_dia_tentou"):
        return []
    db.marcar_notificado(conn, "neste_dia_tentou")
    hoje = agora.date()
    recente = conn.execute(
        "SELECT 1 FROM notificacoes_enviadas WHERE tipo = 'neste_dia_chat' AND data >= ?",
        ((hoje - timedelta(days=ESPACO_DIAS - 1)).isoformat(),),
    ).fetchone()
    if recente:
        return []
    c = card(conn, hoje)
    if not c:
        return []
    import conversa_proativa

    conversa_proativa.publicar(conn, "neste_dia_chat", FRASES[hoje.toordinal() % len(FRASES)], [c])
    return []


def executar_consulta(conn, hoje: date) -> dict:
    """Resultado da ferramenta do chat: o que aconteceu nesta data em meses/anos anteriores."""
    itens = marcos(conn, hoje)
    if not itens:
        return {"dia": hoje.isoformat(), "marcos": [], "obs": "nada de marcante nesta data nos registros; diga isso sem inventar"}
    return {
        "dia": hoje.isoformat(),
        "marcos": [{"rotulo": m["rotulo"], "data": m["quando"], "texto": m["texto"]} for m in itens],
        "_efeito": {"entidade": "neste_dia", "consulta": True},
    }
