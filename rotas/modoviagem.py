"""Blueprint modoviagem - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import get_db
import viagem

bp = Blueprint("modoviagem", __name__)

@bp.route("/api/modo-viagem", methods=["GET"])
def modo_viagem_rota():
    app = app_modulo()
    _modo_viagem_estado = app._modo_viagem_estado
    date = app.date
    conn = get_db()
    estado = _modo_viagem_estado(conn)
    conn.close()
    return jsonify({**estado, "ativo_agora": viagem.modo_viagem_ativo(estado, date.today())})

@bp.route("/api/modo-viagem", methods=["POST"])
def salvar_modo_viagem_rota():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _data_iso_valida = app._data_iso_valida
    _salvar_modo_viagem = app._salvar_modo_viagem
    date = app.date
    body = _corpo_json()
    ativo = bool(body.get("ativo"))
    data_inicio = _data_iso_valida(body.get("data_inicio")) if body.get("data_inicio") else None
    data_fim = _data_iso_valida(body.get("data_fim")) if body.get("data_fim") else None
    if body.get("data_inicio") and not data_inicio:
        return jsonify({"error": "data de inicio inválida (AAAA-MM-DD)"}), 400
    if body.get("data_fim") and not data_fim:
        return jsonify({"error": "data de fim inválida (AAAA-MM-DD)"}), 400
    if data_inicio and data_fim and data_fim < data_inicio:
        return jsonify({"error": "data de fim inválida (tem que ser depois do inicio)"}), 400
    conn = get_db()
    estado = _salvar_modo_viagem(conn, ativo, data_inicio, data_fim)
    conn.close()
    return jsonify({**estado, "ativo_agora": viagem.modo_viagem_ativo(estado, date.today())})
