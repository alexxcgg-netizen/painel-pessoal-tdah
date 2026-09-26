"""Blueprint habitos - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import alternar_habito_dia, delete_habito, get_db, get_habito, list_habitos

bp = Blueprint("habitos", __name__)

@bp.route("/api/habitos", methods=["GET"])
def habitos_rota():
    app = app_modulo()
    _habito_detalhado = app._habito_detalhado
    date = app.date
    conn = get_db()
    resultado = [_habito_detalhado(conn, h, date.today()) for h in list_habitos(conn)]
    conn.close()
    return jsonify({"habitos": resultado, "ativos_total": len(resultado)})

@bp.route("/api/habitos", methods=["POST"])
def criar_habito_rota():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _criar_habito = app._criar_habito
    body = _corpo_json()
    conn = get_db()
    resultado = _criar_habito(
        conn, body.get("nome"), body.get("meta"), body.get("frequencia_tipo"),
        body.get("dias_semana"), body.get("vezes_por_semana"), body.get("horario"),
    )
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201

@bp.route("/api/habitos/<int:habito_id>", methods=["DELETE"])
def apagar_habito_rota(habito_id):
    conn = get_db()
    delete_habito(conn, habito_id)
    conn.close()
    return jsonify({"ok": True})

@bp.route("/api/habitos/<int:habito_id>/marcar", methods=["POST"])
def marcar_habito_rota(habito_id):
    app = app_modulo()
    date = app.date
    conn = get_db()
    if not get_habito(conn, habito_id):
        conn.close()
        return jsonify({"error": "hábito não encontrado"}), 404
    feito = alternar_habito_dia(conn, date.today().isoformat(), habito_id)
    conn.close()
    return jsonify({"feito": feito})
