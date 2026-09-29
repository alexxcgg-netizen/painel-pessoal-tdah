"""Fase 9, Faixa F9-api: API financeira consumida pela tela de Financeiro >
Gastos (extrato paginado + resumo do topo) - contrato implementado em
paralelo com a UI (faixa f9-ui, static/js/secoes/gastos/gastos.js) e a sync
Pluggy (faixa f9-sync, rotas/f8_banco.py). So leitura, nunca grava nada.

Regra de sinal (medida com dados reais do Pluggy - ver AGENTS.md da
faixa): `tipo_operacao` manda - DEBIT e sempre saida, CREDIT e sempre
entrada, INDEPENDENTE do sinal cru que `valor` guarda (no cartao a compra
chega com amount POSITIVO + DEBIT). Linha antiga sem `tipo_operacao` (pre
Fase 9 f9-sync) usa o sinal de `valor` como esta - nunca inverte.

"Nao e gasto" pra fins de /api/financas/resumo (gasto_mes/por_categoria):
pagamento de fatura e transferencia entre contas proprias - identificado
por `categoria_pluggy` contendo "Transfer"/"Credit card payment" ou pela
descricao contendo "pagamento de fatura"/"pagamento recebido". O extrato
(GET /api/financas/extrato) e um extrato de verdade: mostra TUDO que
aconteceu na janela de dias, inclusive esses movimentos - so o resumo do
mes filtra."""

from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, jsonify, request

import db
import financas_descricao
from rotas._base import app_modulo

bp = Blueprint("f9_financas", __name__)

_DIAS_PADRAO = 15
_DIAS_MIN = 1
_DIAS_MAX = 90


def _valor_com_sinal(tipo_operacao, valor) -> float:
    """DEBIT -> sempre saida (negativo); CREDIT -> sempre entrada
    (positivo); sem tipo_operacao (linha antiga) -> sinal de `valor` como
    esta gravado."""
    if valor is None:
        return 0.0
    if tipo_operacao == "DEBIT":
        return -abs(valor)
    if tipo_operacao == "CREDIT":
        return abs(valor)
    return float(valor)


def _eh_transferencia_ou_pagamento_fatura(categoria_pluggy, descricao_original, descricao) -> bool:
    cat = (categoria_pluggy or "").lower()
    if "transfer" in cat or "credit card payment" in cat:
        return True
    texto = f"{descricao_original or ''} {descricao or ''}".lower()
    if "pagamento de fatura" in texto or "pagamento recebido" in texto:
        return True
    return False


def _parse_data(texto: str) -> date | None:
    try:
        return date.fromisoformat(texto)
    except (TypeError, ValueError):
        return None


def _linhas_banco(conn, de: date, ate: date) -> list[dict]:
    """Transacoes de banco (todas as contas) dentro de [de, ate], ja
    descriptografadas, com descricao/categoria/estorno resolvidos por
    financas_descricao e o sinal corrigido pela regra tipo_operacao."""
    todas = db.list_all_bank_transactions(conn)
    por_external_id = {t["external_id"]: t for t in todas if t.get("external_id")}
    contas_por_id = {c["id"]: c for c in db.list_bank_accounts(conn)}
    de_s, ate_s = de.isoformat(), ate.isoformat()

    linhas = []
    for t in todas:
        data_tx = (t.get("data") or "")[:10]
        if not data_tx or not (de_s <= data_tx <= ate_s):
            continue
        info = financas_descricao.descrever({**t, "categoria": t.get("categoria_pluggy")}, por_external_id)
        conta = contas_por_id.get(t.get("bank_account_id"))
        valor = _valor_com_sinal(t.get("tipo_operacao"), t.get("valor"))
        transferencia_ou_fatura = _eh_transferencia_ou_pagamento_fatura(
            t.get("categoria_pluggy"), t.get("descricao_original"), t.get("descricao")
        )
        linhas.append(
            {
                "id": f"bt-{t['id']}",
                "data": data_tx,
                "descricao": info.get("descricao") or "Sem descrição",
                "categoria": info.get("categoria") or t.get("categoria") or "Outros",
                "valor": round(valor, 2),
                "origem": (conta["banco"].capitalize() if conta and conta.get("banco") else "Banco"),
                "tipo_conta": conta["tipo"] if conta else None,
                "estorno_de": info.get("estorno_de"),
                "eh_saida": valor < 0,
                "transferencia_ou_fatura": transferencia_ou_fatura,
            }
        )
    return linhas


def _linhas_manuais(conn, de: date, ate: date) -> list[dict]:
    rows = conn.execute(
        "SELECT id, amount, category, description, created_at FROM expenses WHERE tipo = 'real'"
    ).fetchall()
    de_s, ate_s = de.isoformat(), ate.isoformat()

    linhas = []
    for r in rows:
        data_txt = (r["created_at"] or "")[:10]
        if not data_txt or not (de_s <= data_txt <= ate_s):
            continue
        amount = r["amount"]
        valor = -abs(amount) if amount is not None else 0.0
        linhas.append(
            {
                "id": f"exp-{r['id']}",
                "data": data_txt,
                "descricao": r["description"] or "Sem descrição",
                "categoria": financas_descricao.rotulo_categoria_manual(r["category"]),
                "valor": round(valor, 2),
                "origem": "manual",
                "tipo_conta": None,
                "estorno_de": None,
                "eh_saida": True,
                "transferencia_ou_fatura": False,
            }
        )
    return linhas


def _existe_lancamento_antes_de(conn, de: date) -> bool:
    de_s = de.isoformat()
    achou_banco = conn.execute(
        "SELECT 1 FROM bank_transactions WHERE substr(data, 1, 10) < ? LIMIT 1", (de_s,)
    ).fetchone()
    if achou_banco is not None:
        return True
    achou_manual = conn.execute(
        "SELECT 1 FROM expenses WHERE tipo = 'real' AND substr(created_at, 1, 10) < ? LIMIT 1",
        (de_s,),
    ).fetchone()
    return achou_manual is not None


def _item_extrato(linha: dict) -> dict:
    return {
        "id": linha["id"],
        "data": linha["data"],
        "descricao": linha["descricao"],
        "categoria": linha["categoria"],
        "valor": linha["valor"],
        "origem": linha["origem"],
        "tipo_conta": linha["tipo_conta"],
        "estorno_de": linha["estorno_de"],
    }


@bp.route("/api/financas/extrato", methods=["GET"])
def extrato():
    app = app_modulo()
    if app._modo_visitante_ativo():
        return jsonify({"itens": [], "de": None, "ate": None, "proximo_antes": None, "oculto": True})

    hoje = date.today()

    antes_str = request.args.get("antes")
    if antes_str:
        antes = _parse_data(antes_str)
        if antes is None:
            return jsonify({"error": "data inválida em 'antes' - use o formato AAAA-MM-DD"}), 400
    else:
        antes = hoje

    dias_str = request.args.get("dias")
    try:
        dias = int(dias_str) if dias_str is not None else _DIAS_PADRAO
    except (TypeError, ValueError):
        dias = _DIAS_PADRAO
    if dias < _DIAS_MIN or dias > _DIAS_MAX:
        dias = _DIAS_PADRAO

    ate = min(antes, hoje)
    de = ate - timedelta(days=dias - 1)

    conn = db.get_db()
    try:
        linhas = _linhas_banco(conn, de, ate) + _linhas_manuais(conn, de, ate)
        existe_mais_antigo = _existe_lancamento_antes_de(conn, de)
    finally:
        conn.close()

    linhas.sort(key=lambda linha: (linha["data"], linha["id"]), reverse=True)
    proximo_antes = (de - timedelta(days=1)).isoformat() if existe_mais_antigo else None

    return jsonify(
        {
            "itens": [_item_extrato(linha) for linha in linhas],
            "de": de.isoformat(),
            "ate": ate.isoformat(),
            "proximo_antes": proximo_antes,
        }
    )


def linhas_saida_real(conn, de: date, ate: date) -> list[dict]:
    """Gasto real de [de, ate]: manual + banco, so saida, sem pagamento de
    fatura/transferencia. Fonte unica do resumo de Financas e do chat
    (chat_consultas.consultar_gastos)."""
    return [
        linha
        for linha in _linhas_banco(conn, de, ate) + _linhas_manuais(conn, de, ate)
        if linha["eh_saida"] and not linha["transferencia_ou_fatura"]
    ]


def _gasto_periodo(conn, de: date, ate: date) -> tuple[float, list[dict]]:
    linhas = linhas_saida_real(conn, de, ate)
    total = sum(-linha["valor"] for linha in linhas)

    por_categoria: dict[str, float] = {}
    for linha in linhas:
        por_categoria[linha["categoria"]] = por_categoria.get(linha["categoria"], 0.0) + (-linha["valor"])
    top_categorias = sorted(
        ({"categoria": cat, "valor": round(valor, 2)} for cat, valor in por_categoria.items()),
        key=lambda item: item["valor"],
        reverse=True,
    )[:8]

    return total, top_categorias


def _acumulado_por_dia(conn, de: date, ate: date) -> list[dict]:
    """Gasto acumulado dia a dia de `de` ate `ate` (mesmas regras de
    _gasto_periodo: saida real, sem transferencia/pagamento de fatura). Usado
    pelo card "Evolucao do mes" (Fase 9, faixa C3) - o ultimo item sempre bate
    com o total que _gasto_periodo(de, ate) devolveria."""
    linhas = linhas_saida_real(conn, de, ate)
    por_data: dict[str, float] = {}
    for linha in linhas:
        por_data[linha["data"]] = por_data.get(linha["data"], 0.0) + (-linha["valor"])

    resultado = []
    acumulado = 0.0
    dia_atual = de
    while dia_atual <= ate:
        acumulado += por_data.get(dia_atual.isoformat(), 0.0)
        resultado.append({"dia": dia_atual.day, "acumulado": round(acumulado, 2)})
        dia_atual += timedelta(days=1)
    return resultado


@bp.route("/api/financas/resumo", methods=["GET"])
def resumo():
    app = app_modulo()
    if app._modo_visitante_ativo():
        return jsonify(
            {
                "mes": None,
                "gasto_mes": 0,
                "gasto_mes_anterior": 0,
                "por_categoria": [],
                "por_dia_mes": [],
                "por_dia_mes_anterior": [],
                "fatura_atual": 0,
                "saldo_conta": 0,
                "patrimonio": 0,
                "oculto": True,
            }
        )

    hoje = date.today()
    mes_atual = hoje.strftime("%Y-%m")
    primeiro_dia_mes = hoje.replace(day=1)
    ultimo_dia_mes_anterior = primeiro_dia_mes - timedelta(days=1)
    primeiro_dia_mes_anterior = ultimo_dia_mes_anterior.replace(day=1)

    conn = db.get_db()
    try:
        gasto_mes, por_categoria = _gasto_periodo(conn, primeiro_dia_mes, hoje)
        gasto_mes_anterior, _ = _gasto_periodo(conn, primeiro_dia_mes_anterior, ultimo_dia_mes_anterior)
        por_dia_mes = _acumulado_por_dia(conn, primeiro_dia_mes, hoje)
        por_dia_mes_anterior = _acumulado_por_dia(conn, primeiro_dia_mes_anterior, ultimo_dia_mes_anterior)

        contas = db.list_bank_accounts(conn)
        fatura_atual = round(sum((c["saldo"] or 0) for c in contas if c["tipo"] == "cartao"), 2)
        saldo_conta = round(sum((c["saldo"] or 0) for c in contas if c["tipo"] == "conta"), 2)
        metas = db.list_goals(conn)
        valor_guardado_metas = sum((g["valor_guardado"] or 0) for g in metas)
        patrimonio = round(saldo_conta + valor_guardado_metas - fatura_atual, 2)
    finally:
        conn.close()

    return jsonify(
        {
            "mes": mes_atual,
            "gasto_mes": round(gasto_mes, 2),
            "gasto_mes_anterior": round(gasto_mes_anterior, 2),
            "por_categoria": por_categoria,
            "por_dia_mes": por_dia_mes,
            "por_dia_mes_anterior": por_dia_mes_anterior,
            "fatura_atual": fatura_atual,
            "saldo_conta": saldo_conta,
            "patrimonio": patrimonio,
        }
    )
