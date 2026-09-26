"""Blueprint salvos - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import delete_salvo, get_db, list_salvos, marcar_salvo_lido

bp = Blueprint("salvos", __name__)

@bp.route("/api/salvos", methods=["GET"])
def salvos():
    conn = get_db()
    resultado = list_salvos(conn)
    conn.close()
    return jsonify(resultado)

@bp.route("/api/salvos", methods=["POST"])
def salvar_link_rota():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _salvar_link = app._salvar_link
    conn = get_db()
    resultado = _salvar_link(conn, _corpo_json().get("url"))
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201

@bp.route("/api/salvos/<int:salvo_id>/lido", methods=["POST"])
def salvo_lido(salvo_id):
    conn = get_db()
    ok = marcar_salvo_lido(conn, salvo_id)
    conn.close()
    if not ok:
        return jsonify({"error": "link nao encontrado"}), 404
    return jsonify({"ok": True})

@bp.route("/api/salvos/<int:salvo_id>", methods=["DELETE"])
def apagar_salvo(salvo_id):
    conn = get_db()
    delete_salvo(conn, salvo_id)
    conn.close()
    return jsonify({"ok": True})
