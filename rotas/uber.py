"""Blueprint uber - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify, redirect, request

from rotas._base import app_modulo
from datetime import timedelta
from db import atualizar_uber_pedido, definir_configuracao, get_db, uber_pedido, uber_pedidos_aguardando_confirmacao
import requests
import uber_client

bp = Blueprint("uber", __name__)

@bp.route("/uber/conectar", methods=["GET"])
def uber_conectar():
    """Passo 1 do OAuth - so o Alex, ja logado no painel, clica nisso pra
    autorizar o app com a propria conta Uber dele."""
    if not uber_client.configurado():
        return "Uber ainda não configurado - defina UBER_CLIENT_ID e UBER_CLIENT_SECRET no .env.", 400
    redirect_uri = request.host_url.rstrip("/") + "/uber/callback"
    return redirect(uber_client.url_autorizacao(redirect_uri))

@bp.route("/uber/callback", methods=["GET"])
def uber_callback():
    """Passo 2 do OAuth - a Uber manda o Alex de volta pra ca com um codigo,
    trocado aqui por um token de verdade (guardado na tabela configuracoes)."""
    app = app_modulo()
    datetime = app.datetime
    erro = request.args.get("error")
    if erro:
        return f"Autorizacao da Uber cancelada ou negada ({erro}).", 400
    codigo = request.args.get("code")
    if not codigo:
        return "Código de autorizacao não recebido.", 400

    redirect_uri = request.host_url.rstrip("/") + "/uber/callback"
    try:
        dados = uber_client.trocar_codigo_por_token(codigo, redirect_uri)
    except requests.RequestException:
        return "Não consegui trocar o código por um token - tenta de novo.", 502

    conn = get_db()
    definir_configuracao(conn, "uber_access_token", dados["access_token"])
    definir_configuracao(conn, "uber_refresh_token", dados.get("refresh_token", ""))
    expira_em = datetime.now() + timedelta(seconds=dados.get("expires_in", 2592000))
    definir_configuracao(conn, "uber_token_expira_em", expira_em.isoformat())
    conn.close()
    return "Uber conectado! Pode fechar essa aba e voltar pro painel."

@bp.route("/api/uber/pedidos", methods=["GET"])
def uber_pedidos_pendentes():
    conn = get_db()
    pedidos = uber_pedidos_aguardando_confirmacao(conn)
    conn.close()
    return jsonify(pedidos)

@bp.route("/api/uber/pedidos/<int:pedido_id>/confirmar", methods=["POST"])
def uber_confirmar(pedido_id):
    app = app_modulo()
    _uber_token_valido = app._uber_token_valido
    conn = get_db()
    pedido = uber_pedido(conn, pedido_id)
    if not pedido or pedido["status"] != "aguardando_confirmacao":
        conn.close()
        return jsonify({"error": "pedido não encontrado ou já tratado"}), 404

    access_token = _uber_token_valido(conn)
    if not access_token:
        conn.close()
        return jsonify({"error": "Uber não conectado"}), 400

    try:
        resultado = uber_client.pedir_corrida(
            pedido["origem_lat"],
            pedido["origem_lng"],
            pedido["destino_lat"],
            pedido["destino_lng"],
            pedido["product_id"],
            pedido["fare_id"],
            access_token,
        )
    except requests.RequestException as e:
        atualizar_uber_pedido(conn, pedido_id, status="erro", erro=str(e))
        conn.close()
        return jsonify({"error": "não consegui pedir a corrida agora"}), 502

    atualizar_uber_pedido(
        conn, pedido_id, status="confirmado", request_id=resultado.get("request_id") or ""
    )
    conn.close()
    return jsonify({"ok": True, "request_id": resultado.get("request_id")})

@bp.route("/api/uber/pedidos/<int:pedido_id>/cancelar", methods=["POST"])
def uber_cancelar(pedido_id):
    conn = get_db()
    pedido = uber_pedido(conn, pedido_id)
    if not pedido:
        conn.close()
        return jsonify({"error": "pedido não encontrado"}), 404
    atualizar_uber_pedido(conn, pedido_id, status="cancelado")
    conn.close()
    return jsonify({"ok": True})
