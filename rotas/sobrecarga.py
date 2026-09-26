"""Blueprint sobrecarga - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import get_db

bp = Blueprint("sobrecarga", __name__)

@bp.route("/api/sobrecarga", methods=["GET"])
def sobrecarga_rota():
    app = app_modulo()
    _sinal_sobrecarga_hoje = app._sinal_sobrecarga_hoje
    conn = get_db()
    resultado = _sinal_sobrecarga_hoje(conn)
    conn.close()
    return jsonify(resultado)
