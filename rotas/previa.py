"""Blueprint previa - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import get_db

bp = Blueprint("previa", __name__)

@bp.route("/api/previa-noite", methods=["GET"])
def previa_noite_rota():
    app = app_modulo()
    _modo_visitante_ativo = app._modo_visitante_ativo
    _previa_noite_anterior = app._previa_noite_anterior
    date = app.date
    if _modo_visitante_ativo():
        return jsonify({"oculto": True})
    conn = get_db()
    resultado = _previa_noite_anterior(conn, date.today())
    conn.close()
    return jsonify(resultado)
