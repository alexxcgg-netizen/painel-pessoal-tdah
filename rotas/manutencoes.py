"""Blueprint manutencoes - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import delete_manutencao, get_db, get_manutencao, marcar_manutencao_feita

bp = Blueprint("manutencoes", __name__)

@bp.route("/api/manutencoes", methods=["GET"])
def manutencoes():
    app = app_modulo()
    _manutencoes_com_status = app._manutencoes_com_status
    date = app.date
    conn = get_db()
    resultado = _manutencoes_com_status(conn, date.today())
    conn.close()
    return jsonify(resultado)

@bp.route("/api/manutencoes", methods=["POST"])
def criar_manutencao_rota():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _criar_manutencao = app._criar_manutencao
    _marcar_atividade = app._marcar_atividade
    body = _corpo_json()
    conn = get_db()
    resultado = _criar_manutencao(conn, body)
    if "ok" in resultado:
        _marcar_atividade(conn)
        conn.commit()
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201

@bp.route("/api/manutencoes/<int:manutencao_id>/feita", methods=["POST"])
def manutencao_feita(manutencao_id):
    app = app_modulo()
    _marcar_atividade = app._marcar_atividade
    date = app.date
    conn = get_db()
    existente = get_manutencao(conn, manutencao_id)
    if not existente:
        conn.close()
        return jsonify({"error": "manutencao nao encontrada"}), 404
    if existente["tipo"] == "carro":
        conn.close()
        return jsonify({"error": "manutencao de carro nao usa 'feita' - adicione um novo registro"}), 400
    ok = marcar_manutencao_feita(conn, manutencao_id, date.today().isoformat())
    if ok:
        _marcar_atividade(conn)
        conn.commit()
    conn.close()
    if not ok:
        return jsonify({"error": "manutencao nao encontrada"}), 404
    return jsonify({"ok": True})

@bp.route("/api/manutencoes/<int:manutencao_id>", methods=["DELETE"])
def apagar_manutencao(manutencao_id):
    conn = get_db()
    delete_manutencao(conn, manutencao_id)
    conn.close()
    return jsonify({"ok": True})
