"""Blueprint lugares - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import delete_lugar, get_db, list_lugares, proximo_lugar_para_geocodificar

bp = Blueprint("lugares", __name__)

@bp.route("/api/lugares", methods=["GET"])
def lugares():
    app = app_modulo()
    _agora_utc = app._agora_utc
    _fmt_utc = app._fmt_utc
    _geocodificar_lugar = app._geocodificar_lugar
    conn = get_db()
    resultado = list_lugares(conn)
    # US-F13: backfill de lugares que ja existiam antes desta historia (ou
    # cuja falha temporaria ja esperou GEOCODE_ESPERA_APOS_ERRO) - no MAXIMO
    # 1 geocode por chamada, pra nunca estourar 1 req/s nem prender o worker.
    pendente = proximo_lugar_para_geocodificar(conn, _fmt_utc(_agora_utc()))
    if pendente:
        _geocodificar_lugar(conn, pendente["id"], pendente["nome"], pendente.get("cidade"))
        resultado = list_lugares(conn)
    conn.close()
    return jsonify(resultado)

@bp.route("/api/lugares", methods=["POST"])
def criar_lugar_rota():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _criar_lugar = app._criar_lugar
    body = _corpo_json()
    conn = get_db()
    resultado = _criar_lugar(conn, body.get("nome"), body.get("cidade"), body.get("tipo"), body.get("nota"))
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201

@bp.route("/api/lugares/<int:lugar_id>", methods=["DELETE"])
def apagar_lugar(lugar_id):
    conn = get_db()
    delete_lugar(conn, lugar_id)
    conn.close()
    return jsonify({"ok": True})
