"""Foto do prato -> o que tem, gramas, kcal e macros (2026-10-13, pedido do Alex: "mandar uma foto
de um prato de comida e ela ver o que tem ali e dar uma media em gramas, carboidratos, proteinas...
facil e pratico").

Fluxo: o chat manda a foto (POST /api/chat/foto) -> ia.funcoes.visao.analisar_prato estima cada
item -> aqui a refeicao e gravada (Desfazer no card tira) e soma no dia, contra a meta do perfil
(vida_assistente.metas_comida - ganho de massa). Numero de cada item vem da IA (estimativa por
foto, sempre "~"); a SOMA e o confronto com a meta sao feitos aqui, em codigo.
A foto em si nao e guardada.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

import diario

MACROS = ("kcal", "proteina_g", "carbo_g", "gordura_g")
NOMES_REFEICAO = {
    "cafe_da_manha": "café da manhã",
    "almoco": "almoço",
    "lanche": "lanche",
    "janta": "janta",
    "ceia": "ceia",
}


def criar_tabela(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS refeicoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dia TEXT NOT NULL,
            hora TEXT,
            refeicao TEXT,
            itens_json TEXT NOT NULL,
            kcal REAL NOT NULL DEFAULT 0,
            proteina_g REAL NOT NULL DEFAULT 0,
            carbo_g REAL NOT NULL DEFAULT 0,
            gordura_g REAL NOT NULL DEFAULT 0,
            fonte TEXT NOT NULL DEFAULT 'foto',
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def refeicao_pela_hora(hora: int) -> str:
    if 5 <= hora < 10:
        return "cafe_da_manha"
    if 10 <= hora < 15:
        return "almoco"
    if 15 <= hora < 18:
        return "lanche"
    if 18 <= hora < 22:
        return "janta"
    return "ceia"


def _num(v, maximo: float) -> float:
    try:
        n = float(v)
    except (TypeError, ValueError):
        return 0.0
    return round(min(max(n, 0.0), maximo), 1)


def itens_limpos(itens) -> list[dict]:
    """So o que da pra confiar no formato: nome + numeros dentro de faixa de gente."""
    saida = []
    for it in itens or []:
        if not isinstance(it, dict) or not str(it.get("nome") or "").strip():
            continue
        saida.append({
            "nome": str(it["nome"]).strip()[:60],
            "gramas": _num(it.get("gramas"), 2000),
            "kcal": _num(it.get("kcal"), 3000),
            "proteina_g": _num(it.get("proteina_g"), 300),
            "carbo_g": _num(it.get("carbo_g"), 500),
            "gordura_g": _num(it.get("gordura_g"), 300),
        })
    return saida[:15]


def somar(itens: list[dict]) -> dict:
    return {m: round(sum(i[m] for i in itens), 1) for m in MACROS} | {"gramas": round(sum(i["gramas"] for i in itens))}


def registrar(conn, itens: list[dict], refeicao: str | None, agora: datetime) -> int:
    criar_tabela(conn)
    tot = somar(itens)
    if refeicao not in NOMES_REFEICAO:
        refeicao = refeicao_pela_hora(agora.hour)
    cur = conn.execute(
        "INSERT INTO refeicoes (dia, hora, refeicao, itens_json, kcal, proteina_g, carbo_g, gordura_g) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (agora.date().isoformat(), f"{agora:%H:%M}", refeicao, json.dumps(itens, ensure_ascii=False),
         tot["kcal"], tot["proteina_g"], tot["carbo_g"], tot["gordura_g"]),
    )
    conn.commit()
    return cur.lastrowid


def do_dia(conn, dia: date) -> dict:
    """{refeicoes: n, kcal, proteina_g, carbo_g, gordura_g}"""
    criar_tabela(conn)
    r = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(kcal),0) AS kcal, COALESCE(SUM(proteina_g),0) AS proteina_g, "
        "COALESCE(SUM(carbo_g),0) AS carbo_g, COALESCE(SUM(gordura_g),0) AS gordura_g FROM refeicoes WHERE dia = ?",
        (dia.isoformat(),),
    ).fetchone()
    return {"refeicoes": r["n"], **{m: round(r[m], 1) for m in MACROS}}


def ler(conn, id_: int) -> dict | None:
    criar_tabela(conn)
    r = conn.execute("SELECT * FROM refeicoes WHERE id = ?", (id_,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["itens"] = json.loads(d.pop("itens_json") or "[]")
    return d


def meta_do_dia(conn, dia: date) -> dict | None:
    import vida_assistente

    p = vida_assistente.perfil(conn, dia)
    if not p.get("peso_kg"):
        return None
    return vida_assistente.metas_comida(p["peso_kg"], p.get("altura_cm"), p.get("idade"), p.get("objetivo"))


def linha_contexto(conn, dia: date) -> str | None:
    """Pro system prompt do chat: o que ele ja comeu hoje (das fotos), contra a meta."""
    tot = do_dia(conn, dia)
    if not tot["refeicoes"]:
        return None
    meta = meta_do_dia(conn, dia)
    txt = (f"Comida de hoje (pelas fotos, estimativa): {tot['refeicoes']} refeição(ões), ~{tot['kcal']:.0f} kcal, "
           f"proteína ~{tot['proteina_g']:.0f} g, carbo ~{tot['carbo_g']:.0f} g, gordura ~{tot['gordura_g']:.0f} g")
    if meta:
        txt += f" (meta do dia: {meta['kcal']} kcal, {meta['proteina_g']} g de proteína)"
    return txt


def fatos_do_dia(conn, dia: date) -> str | None:
    """Pro diario: 'almoco ~650 kcal, janta ~800 kcal (total ~1450 kcal, P ~95 g)'."""
    criar_tabela(conn)
    linhas = conn.execute("SELECT refeicao, kcal FROM refeicoes WHERE dia = ? ORDER BY hora", (dia.isoformat(),)).fetchall()
    if not linhas:
        return None
    tot = do_dia(conn, dia)
    partes = ", ".join(f"{NOMES_REFEICAO.get(r['refeicao'], r['refeicao'])} ~{r['kcal']:.0f} kcal" for r in linhas)
    return f"{partes} (total ~{tot['kcal']:.0f} kcal, proteína ~{tot['proteina_g']:.0f} g)"


def dados_card(conn, id_: int) -> dict | None:
    """Data do card `refeicao`: itens, totais da refeicao, total do dia e meta."""
    r = ler(conn, id_)
    if not r:
        return None
    dia = date.fromisoformat(r["dia"])
    meta = meta_do_dia(conn, dia)
    return {
        "refeicao": NOMES_REFEICAO.get(r["refeicao"], r["refeicao"] or "refeição"),
        "hora": r["hora"],
        "itens": r["itens"],
        "total": {m: r[m] for m in MACROS},
        "dia": do_dia(conn, dia),
        "meta": {"kcal": meta["kcal"], "proteina_g": meta["proteina_g"]} if meta else None,
        "hoje": dia == diario.hoje_local() or dia == date.today(),
    }


def ultimos_dias(conn, hoje: date, dias: int = 7) -> list[dict]:
    criar_tabela(conn)
    ini = (hoje - timedelta(days=dias - 1)).isoformat()
    return [dict(r) for r in conn.execute(
        "SELECT dia, COUNT(*) AS refeicoes, ROUND(SUM(kcal)) AS kcal, ROUND(SUM(proteina_g)) AS proteina_g "
        "FROM refeicoes WHERE dia >= ? GROUP BY dia ORDER BY dia", (ini,)
    )]
