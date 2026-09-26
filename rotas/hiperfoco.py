"""Blueprint hiperfoco - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import definir_configuracao, get_db
import vida

bp = Blueprint("hiperfoco", __name__)

@bp.route("/api/hiperfoco", methods=["GET"])
def hiperfoco():
    app = app_modulo()
    _estado_hiperfoco = app._estado_hiperfoco
    conn = get_db()
    estado = _estado_hiperfoco(conn)
    conn.close()
    return jsonify(estado)

@bp.route("/api/hiperfoco", methods=["POST"])
def iniciar_hiperfoco_rota():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _iniciar_hiperfoco = app._iniciar_hiperfoco
    minutos = _corpo_json().get("minutos")
    if isinstance(minutos, bool) or minutos not in vida.DURACOES_HIPERFOCO:
        return jsonify({"error": "duracao deve ser 25, 50 ou 90 minutos"}), 400
    conn = get_db()
    estado = _iniciar_hiperfoco(conn, minutos)
    conn.close()
    return jsonify(estado)

@bp.route("/api/hiperfoco", methods=["DELETE"])
def encerrar_hiperfoco():
    conn = get_db()
    definir_configuracao(conn, "hiperfoco_ate", "")
    conn.close()
    return jsonify({"ativo": False, "ate": None, "minutos_restantes": 0, "segundos_restantes": 0})
