"""Blueprint notas - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import apagar_nota, get_db, list_notas

bp = Blueprint("notas", __name__)

@bp.route("/api/notas", methods=["GET"])
def notas():
    conn = get_db()
    resultado = list_notas(conn)
    conn.close()
    return jsonify(resultado)

@bp.route("/api/notas/<int:nota_id>", methods=["DELETE"])
def apagar_nota_rota(nota_id):
    conn = get_db()
    apagar_nota(conn, nota_id)
    conn.close()
    return jsonify({"ok": True})
