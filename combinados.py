"""Quadro dos combinados (leva 22/10, ideia 5 do prototipo aprovado "Ideias do Painel" -
docs/briefings/2026-10-22-leva-ideias-v3.md).

Pessoas: o que prometeram pra ele (`esperas`) e o que ele deve responder (`responder`), com ha quantos dias e um
rascunho pronto pra cobrar/responder - o painel nunca manda mensagem sozinho, so prepara (ele copia e manda).
Empresa: contas atrasadas da construtora pela API so leitura (`_buscar_contas_a_vencer_construtora`), mostradas
como chegaram. Sem total: somar os valores seria refazer conta da empresa aqui (regra do CLAUDE.md).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

LIMITE_PESSOAS = 8
LIMITE_EMPRESA = 6


def _dias(criado_em: str | None, hoje: date) -> int:
    """`criado_em` vem do datetime('now') do SQLite (UTC): -3 h antes de pegar o dia (a noite virava amanha)."""
    try:
        return max(0, (hoje - (datetime.fromisoformat(criado_em) - timedelta(hours=3)).date()).days)
    except (TypeError, ValueError):
        return 0


def _rascunho(tipo: str, quem: str, sobre: str) -> str:
    if tipo == "espera":
        return f"Oi, {quem}! Tudo bem? Conseguiu ver {sobre}? Preciso fechar isso essa semana." if sobre else \
            f"Oi, {quem}! Tudo bem? Conseguiu ver aquilo que a gente combinou?"
    return f"Oi, {quem}! Desculpa a demora. Sobre {sobre}: " if sobre else f"Oi, {quem}! Desculpa a demora pra responder."


def pessoas(conn, hoje: date) -> list[dict]:
    itens = []
    for r in conn.execute("SELECT id, quem, sobre, criado_em FROM esperas WHERE resolvido_em IS NULL").fetchall():
        itens.append({"tipo": "espera", "id": r["id"], "quem": r["quem"], "sobre": r["sobre"] or "",
                      "dias": _dias(r["criado_em"], hoje)})
    for r in conn.execute("SELECT id, quem, sobre, criado_em FROM responder WHERE respondido_em IS NULL").fetchall():
        itens.append({"tipo": "responder", "id": r["id"], "quem": r["quem"], "sobre": r["sobre"] or "",
                      "dias": _dias(r["criado_em"], hoje)})
    itens.sort(key=lambda i: -i["dias"])
    for i in itens:
        i["rascunho"] = _rascunho(i["tipo"], i["quem"], i["sobre"])
    return itens[:LIMITE_PESSOAS]


def empresa(contas: dict | None) -> dict:
    """`contas` = retorno de _buscar_contas_a_vencer_construtora (None = fora do ar / nao configurado)."""
    if not isinstance(contas, dict):
        return {"disponivel": False, "atrasadas": []}
    atrasadas = [
        {"nome": c.get("fornecedor") or c.get("descricao") or "Conta", "descricao": c.get("descricao") or "",
         "valor": c.get("valor"), "dias": abs(int(c["dias_ate_vencer"]))}
        for c in contas.get("contas") or []
        if isinstance(c.get("dias_ate_vencer"), (int, float)) and c["dias_ate_vencer"] < 0
    ]
    atrasadas.sort(key=lambda c: -c["dias"])
    return {"disponivel": True, "atrasadas": atrasadas[:LIMITE_EMPRESA], "mais": max(0, len(atrasadas) - LIMITE_EMPRESA)}


def card(conn, hoje: date, contas: dict | None) -> dict:
    import cards

    return cards.novo_card("combinados", {"pessoas": pessoas(conn, hoje), "empresa": empresa(contas)})
