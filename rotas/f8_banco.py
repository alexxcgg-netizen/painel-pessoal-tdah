"""Fase 8, Faixa F1: sincronizacao automatica do Nubank via Pluggy (item ja
autorizado, sem passar pelo Connect) + lista unificada de gastos com selo de
origem (Nubank/manual) na tela de Financeiro > Gastos.

So usa o item_id de PLUGGY_ITEM_ID_NUBANK (.env) - nunca inventa nem aceita
item_id vindo do corpo da requisicao pra essa rota (evita que qualquer um
sincronize um item alheio). O fluxo de Connect (usuario escolhe o banco na
hora) continua em app.py, sem mudanca.
"""

import os

import requests
from flask import Blueprint, jsonify

import db
import pluggy_client
from rotas._base import app_modulo

bp = Blueprint("f8_banco", __name__)


def _erro_amigavel_pluggy(exc: Exception) -> tuple[str, int]:
    """Converte qualquer erro de rede/HTTP da Pluggy numa mensagem que pode
    ir pra tela sem vazar corpo cru de resposta nem cabecalho com chave."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status == 404:
        return "conexao Nubank nao encontrada nessa conta Pluggy - reconectar", 404
    if status == 401:
        return "credenciais da Pluggy invalidas ou expiradas - reconectar", 401
    return "nao consegui falar com a Pluggy agora, tenta de novo mais tarde", 502


@bp.route("/api/bancos/sincronizar-nubank", methods=["POST"])
def sincronizar_nubank():
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa

    if not pluggy_client.configurado():
        return jsonify({"error": "sincronizacao automatica nao configurada"}), 400

    item_id = os.environ.get("PLUGGY_ITEM_ID_NUBANK")
    if not item_id:
        return jsonify({"error": "PLUGGY_ITEM_ID_NUBANK nao configurado"}), 400

    try:
        item = pluggy_client.get_item(item_id)
        contas_pluggy = pluggy_client.get_accounts(item_id)
    except requests.RequestException as exc:
        mensagem, status = _erro_amigavel_pluggy(exc)
        return jsonify({"error": mensagem}), status

    conn = db.get_db()
    try:
        resumo = []
        for conta_pluggy in contas_pluggy:
            tipo = "cartao" if conta_pluggy.get("type") == "CREDIT" else "conta"
            conta_id = db.get_or_create_bank_account(conn, "nubank", tipo)
            saldo_pluggy = conta_pluggy.get("balance")
            if saldo_pluggy is not None:
                db.atualizar_saldo_conta(conn, conta_id, saldo_pluggy)
            try:
                transacoes_pluggy = pluggy_client.get_transactions(conta_pluggy["id"])
            except requests.RequestException as exc:
                mensagem, status = _erro_amigavel_pluggy(exc)
                return jsonify({"error": mensagem}), status
            transacoes = pluggy_client.normalizar_transacoes(transacoes_pluggy)
            transacoes = app._categorizar_transacoes_importadas(conn, transacoes)
            novas = db.insert_bank_transactions(conn, conta_id, transacoes)
            resumo.append({"conta_id": conta_id, "tipo": tipo, "novas": novas})
        conn.commit()
    finally:
        conn.close()

    return jsonify({"banco": "nubank", "item_status": item.get("status"), "contas": resumo})


@bp.route("/api/gastos/unificados", methods=["GET"])
def gastos_unificados():
    """Gastos manuais (expenses) + gastos automaticos (bank_transactions),
    numa lista so, cada item com 'origem' ('manual' ou o nome do banco,
    ex: 'Nubank'). Nao apaga nem altera nada - so leitura."""
    app = app_modulo()
    conn = db.get_db()
    try:
        expenses_reais = conn.execute(
            "SELECT amount, category, description, source_text, created_at "
            "FROM expenses WHERE tipo = 'real' ORDER BY created_at DESC"
        ).fetchall()
        unificado = []
        for r in expenses_reais:
            item = dict(r)
            item["origem"] = "manual"
            unificado.append(item)

        contas_por_id = {c["id"]: c for c in db.list_bank_accounts(conn)}
        for r in db.list_all_bank_transactions(conn):
            if r["valor"] is None or r["valor"] >= 0:
                continue
            conta = contas_por_id.get(r["bank_account_id"])
            banco = (conta["banco"] if conta else "banco").strip()
            unificado.append(
                {
                    "amount": -r["valor"],
                    "category": r["categoria"] or "outros",
                    "description": r["descricao"],
                    "source_text": None,
                    "created_at": r["data"],
                    "origem": banco.capitalize() if banco else "banco",
                }
            )
        unificado.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    finally:
        conn.close()
    return jsonify(unificado)
