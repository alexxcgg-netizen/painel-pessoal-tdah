"""Blueprint clima - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from rotas._base import app_modulo
import metar
import os

bp = Blueprint("clima", __name__)

@bp.route("/api/clima/metar", methods=["GET"])
def clima_metar():
    icao = (request.args.get("icao") or "").strip()
    resultado = metar.buscar_metar_taf(icao)
    return jsonify(resultado)

@bp.route("/api/clima/hoje", methods=["GET"])
def clima_hoje_rota():
    app = app_modulo()
    clima = app.clima
    cidade = os.environ.get("CIDADE_PADRAO", "").strip()
    if not cidade:
        return jsonify({"configurado": False})
    resumo = clima.resumo_chuva_hoje_para_cidade(cidade)
    if not resumo:
        return jsonify({"configurado": True, "erro": "não consegui buscar a previsão agora"})
    return jsonify({"configurado": True, **resumo})
