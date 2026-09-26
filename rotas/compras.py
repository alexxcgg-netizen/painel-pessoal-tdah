"""Blueprint compras - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import delete_compra, get_db, list_compras_pendentes, marcar_comprado

bp = Blueprint("compras", __name__)

@bp.route("/api/compras", methods=["GET"])
def compras():
    conn = get_db()
    resultado = list_compras_pendentes(conn)
    conn.close()
    return jsonify(resultado)

@bp.route("/api/compras", methods=["POST"])
def adicionar_compras_rota():
    app = app_modulo()
    _adicionar_compras = app._adicionar_compras
    _corpo_json = app._corpo_json
    body = _corpo_json()
    conn = get_db()
    resultado = _adicionar_compras(conn, body.get("itens", body.get("item")))
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201

@bp.route("/api/compras/<int:compra_id>/comprado", methods=["POST"])
def compra_comprada(compra_id):
    conn = get_db()
    marcar_comprado(conn, compra_id)
    conn.close()
    return jsonify({"ok": True})

@bp.route("/api/compras/<int:compra_id>", methods=["DELETE"])
def apagar_compra(compra_id):
    conn = get_db()
    delete_compra(conn, compra_id)
    conn.close()
    return jsonify({"ok": True})
