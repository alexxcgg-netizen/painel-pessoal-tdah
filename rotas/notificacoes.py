"""Blueprint notificacoes - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo

bp = Blueprint("notificacoes", __name__)

@bp.route("/api/notificacoes/verificar-agora", methods=["POST"])
def notificacoes_verificar_agora():
    app = app_modulo()
    verificar_e_notificar = app.verificar_e_notificar
    enviados = verificar_e_notificar()
    return jsonify({"avisos_enviados": enviados})
