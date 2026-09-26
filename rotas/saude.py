"""Blueprint saude - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from rotas._base import app_modulo
from db import CAMPOS_SAUDE, contar_hidratacao_dia, create_medida_corporal, delete_medida_corporal, get_db, get_saude_dia, list_medidas_corporais, registrar_hidratacao, upsert_saude_dia
import aprendizado
import math
import os

bp = Blueprint("saude", __name__)

@bp.route("/api/saude/importar", methods=["POST"])
def saude_importar():
    app = app_modulo()
    _corpo_json = app._corpo_json
    date = app.date
    token_esperado = os.environ.get("SAUDE_WEBHOOK_TOKEN")
    if token_esperado and request.headers.get("X-Webhook-Token") != token_esperado:
        return jsonify({"error": "token invalido"}), 401

    body = _corpo_json()
    data = body.get("data") or date.today().isoformat()
    try:
        date.fromisoformat(data)
    except ValueError:
        return jsonify({"error": "data precisa estar em formato AAAA-MM-DD"}), 400

    campos = {c: body[c] for c in CAMPOS_SAUDE if body.get(c) is not None}
    if not campos:
        return (
            jsonify({"error": "informe ao menos um campo: " + ", ".join(CAMPOS_SAUDE)}),
            400,
        )

    conn = get_db()
    upsert_saude_dia(conn, data, campos)
    conn.close()
    return jsonify({"ok": True, "data": data, **campos})

@bp.route("/api/saude/hoje", methods=["GET"])
def saude_hoje():
    app = app_modulo()
    _modo_visitante_ativo = app._modo_visitante_ativo
    date = app.date
    if _modo_visitante_ativo():
        return jsonify(
            {"dados": None, "hidratacao_hoje": None, "dica_sono": None, "dica_humor": None, "oculto": True}
        )
    conn = get_db()
    dia = get_saude_dia(conn, date.today().isoformat())
    hidratacao_hoje = contar_hidratacao_dia(conn, date.today().isoformat())
    dica_sono = aprendizado.dica_sono_produtividade(conn)
    dica_humor = aprendizado.dica_sono_humor(conn)
    conn.close()
    return jsonify(
        {"dados": dia, "hidratacao_hoje": hidratacao_hoje, "dica_sono": dica_sono, "dica_humor": dica_humor}
    )

@bp.route("/api/hidratacao", methods=["POST"])
def registrar_hidratacao_rota():
    app = app_modulo()
    _marcar_atividade = app._marcar_atividade
    date = app.date
    conn = get_db()
    total = registrar_hidratacao(conn, date.today().isoformat())
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "total_hoje": total}), 201

@bp.route("/api/medidas", methods=["GET"])
def medidas():
    app = app_modulo()
    _modo_visitante_ativo = app._modo_visitante_ativo
    if _modo_visitante_ativo():
        return jsonify([])
    tipo = request.args.get("tipo") or None
    conn = get_db()
    resultado = list_medidas_corporais(conn, tipo=tipo)
    conn.close()
    return jsonify(resultado)

@bp.route("/api/medidas", methods=["POST"])
def criar_medida_rota():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _marcar_atividade = app._marcar_atividade
    date = app.date
    body = _corpo_json()
    tipo = (body.get("tipo") or "").strip().lower()
    unidade = (body.get("unidade") or "").strip()
    data_medida = (body.get("data") or date.today().isoformat()).strip()
    if not tipo:
        return jsonify({"error": "informe o tipo da medida (ex: peso, biceps)"}), 400
    try:
        valor = float(body.get("valor"))
    except (TypeError, ValueError):
        return jsonify({"error": "valor invalido"}), 400
    if not math.isfinite(valor):
        return jsonify({"error": "valor invalido"}), 400
    try:
        date.fromisoformat(data_medida)
    except ValueError:
        return jsonify({"error": "data invalida - use AAAA-MM-DD"}), 400

    if not unidade:
        unidade = "kg" if tipo == "peso" else "cm"

    conn = get_db()
    medida_id = create_medida_corporal(conn, tipo, valor, unidade, data_medida)
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "medida_id": medida_id}), 201

@bp.route("/api/medidas/<int:medida_id>", methods=["DELETE"])
def apagar_medida(medida_id):
    conn = get_db()
    delete_medida_corporal(conn, medida_id)
    conn.close()
    return jsonify({"ok": True})
