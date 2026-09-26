"""Blueprint presentes - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import alternar_ideia_presente_comprada, delete_ideia_presente, get_db, list_ideias_presente

bp = Blueprint("presentes", __name__)

@bp.route("/api/ideias-presente", methods=["GET"])
def ideias_presente_rota():
    conn = get_db()
    resultado = list_ideias_presente(conn)
    conn.close()
    return jsonify(resultado)

@bp.route("/api/ideias-presente", methods=["POST"])
def criar_ideia_presente_rota():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _criar_ideia_presente = app._criar_ideia_presente
    body = _corpo_json()
    conn = get_db()
    resultado = _criar_ideia_presente(conn, body.get("pessoa"), body.get("ideia"), body.get("ocasiao"))
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201

@bp.route("/api/ideias-presente/<int:ideia_id>/comprado", methods=["POST"])
def alternar_ideia_presente_rota(ideia_id):
    conn = get_db()
    comprado = alternar_ideia_presente_comprada(conn, ideia_id)
    conn.close()
    if comprado is None:
        return jsonify({"error": "ideia nao encontrada"}), 404
    return jsonify({"comprado": comprado})

@bp.route("/api/ideias-presente/<int:ideia_id>", methods=["DELETE"])
def apagar_ideia_presente_rota(ideia_id):
    conn = get_db()
    delete_ideia_presente(conn, ideia_id)
    conn.close()
    return jsonify({"ok": True})
