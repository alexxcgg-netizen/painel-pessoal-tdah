"""Blueprint bancos - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import atualizar_saldo_conta, estatisticas_conta, gasto_mes_conta, get_db, get_or_create_bank_account, insert_bank_transactions, list_bank_accounts, list_bank_transactions, obter_configuracao
import criptografia
import pluggy_client
import requests
import rotas
import vida

bp = Blueprint("bancos", __name__)

@bp.route("/api/bancos", methods=["GET"])
def listar_bancos():
    app = app_modulo()
    _modo_visitante_ativo = app._modo_visitante_ativo
    date = app.date
    if _modo_visitante_ativo():
        return jsonify([])
    conn = get_db()
    # saldo/valor sao criptografados em repouso - list_bank_accounts e
    # estatisticas_conta ja descriptografam e somam em Python (ver db.py).
    contas = list_bank_accounts(conn)
    ano_mes_atual = date.today().strftime("%Y-%m")
    resultado = []
    for c in contas:
        stats = estatisticas_conta(conn, c["id"])
        item = {
            **c,
            "total_transacoes": stats["total"],
            "ultima_transacao": stats["ultima"],
            "total_gasto": stats["total_gasto"],
        }
        # Fase 6 (US-E15): limite manual do cartao - so calcula fracao/sobra
        # quando o proprio Alex digitou um limite (Open Finance nao manda
        # isso); "ciclo" aqui e simplificado pro mes-calendario, ver
        # gasto_mes_conta em db.py.
        if c["tipo"] == "cartao":
            gasto_ciclo = gasto_mes_conta(conn, c["id"], ano_mes_atual)
            item["gasto_ciclo"] = round(gasto_ciclo, 2)
            item["limite_info"] = vida.fracao_limite_cartao(gasto_ciclo, c.get("limite"))
        resultado.append(item)
    conn.close()
    return jsonify(resultado)

@bp.route("/api/bancos/<int:conta_id>/limite", methods=["POST"])
def definir_limite_cartao_rota(conta_id):
    app = app_modulo()
    _corpo_json = app._corpo_json
    _definir_limite_cartao = app._definir_limite_cartao
    _modo_visitante_ativo = app._modo_visitante_ativo
    if _modo_visitante_ativo():
        return jsonify({"error": "indisponivel no modo visitante"}), 403
    body = _corpo_json()
    conn = get_db()
    resultado = _definir_limite_cartao(conn, conta_id, body.get("limite"))
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado)

@bp.route("/api/bancos/<int:conta_id>/transacoes", methods=["GET"])
def transacoes_banco(conta_id):
    app = app_modulo()
    _modo_visitante_ativo = app._modo_visitante_ativo
    if _modo_visitante_ativo():
        return jsonify([])
    conn = get_db()
    transacoes = list_bank_transactions(conn, conta_id, limite=100)
    conn.close()
    return jsonify(transacoes)

@bp.route("/api/bancos/sync-status", methods=["GET"])
def bancos_sync_status():
    configurado = pluggy_client.configurado()
    info = (
        "Conecte um banco automaticamente pra sincronizar sem precisar exportar OFX."
        if configurado
        else "Sincronizacao automatica ainda nao configurada - veja o README (integracao com Pluggy)."
    )
    # uso/m2-sync: carimbo do ultimo sync bom (manual OU automatico de
    # madrugada, ver rodar_sincronizacao_nubank_automatica/iniciar_scheduler
    # abaixo - os dois gravam com a mesma chave em rotas/f8_banco.py) - so
    # acrescenta na mesma frase, sem lugar novo na tela.
    ultimo_sync = None
    if configurado:
        import rotas.f8_banco

        conn = get_db()
        try:
            ultimo_sync = obter_configuracao(conn, rotas.f8_banco.CHAVE_ULTIMO_SYNC_NUBANK_OK)
        finally:
            conn.close()
        if ultimo_sync:
            info += f" Ultima sincronizacao: {ultimo_sync[:16].replace('T', ' as ')}."
    return jsonify(
        {
            "sincronizacao_automatica": configurado,
            "info": info,
            "ultimo_sync_nubank_ok": ultimo_sync,
            "criptografia_ativa": criptografia.configurada(),
        }
    )

@bp.route("/api/bancos/conectar/token", methods=["POST"])
def bancos_conectar_token():
    if not pluggy_client.configurado():
        return jsonify({"error": "sincronizacao automatica nao configurada"}), 400
    try:
        token = pluggy_client.create_connect_token()
    except requests.RequestException:
        return jsonify({"error": "nao consegui falar com a Pluggy agora"}), 502
    return jsonify({"connect_token": token})

@bp.route("/api/bancos/conectar/finalizar", methods=["POST"])
def bancos_conectar_finalizar():
    app = app_modulo()
    _categorizar_transacoes_importadas = app._categorizar_transacoes_importadas
    _corpo_json = app._corpo_json
    if not pluggy_client.configurado():
        return jsonify({"error": "sincronizacao automatica nao configurada"}), 400

    item_id = _corpo_json().get("item_id")
    if not item_id:
        return jsonify({"error": "item_id obrigatorio"}), 400

    try:
        item = pluggy_client.get_item(item_id)
        contas_pluggy = pluggy_client.get_accounts(item_id)
    except requests.RequestException:
        return jsonify({"error": "nao consegui buscar os dados na Pluggy agora"}), 502

    banco = item.get("connector", {}).get("name", "banco").lower()

    conn = get_db()
    resumo = []
    for conta_pluggy in contas_pluggy:
        tipo = "cartao" if conta_pluggy.get("type") == "CREDIT" else "conta"
        conta_id = get_or_create_bank_account(conn, banco, tipo)
        saldo_pluggy = conta_pluggy.get("balance")
        if saldo_pluggy is not None:
            atualizar_saldo_conta(conn, conta_id, saldo_pluggy)
        try:
            # (Connect: primeira importacao do item, sem reconciliacao de
            # remocao - isso e so na sincronizacao recorrente do Nubank em
            # rotas/f8_banco.py.) `truncado` nao muda esse fluxo hoje.
            transacoes_pluggy, _truncado = pluggy_client.get_transactions(conta_pluggy["id"])
        except requests.RequestException:
            conn.close()
            return jsonify({"error": "nao consegui buscar as transacoes na Pluggy agora"}), 502
        transacoes = pluggy_client.normalizar_transacoes(transacoes_pluggy)
        transacoes = _categorizar_transacoes_importadas(conn, transacoes)
        novas = insert_bank_transactions(conn, conta_id, transacoes)
        resumo.append({"conta_id": conta_id, "tipo": tipo, "novas": novas})
    conn.close()

    return jsonify({"banco": banco, "contas": resumo})
