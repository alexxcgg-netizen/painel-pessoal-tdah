"""Blueprint aprender - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import delete_aprender, get_db, list_aprender, marcar_aprender

bp = Blueprint("aprender", __name__)

@bp.route("/api/aprender", methods=["GET"])
def aprender():
    app = app_modulo()
    date = app.date
    hoje = date.today()
    conn = get_db()
    resultado = []
    for a in list_aprender(conn):
        base = a["ultima_vez"] or a["criado_em"][:10]
        resultado.append({**a, "dias_parado": (hoje - date.fromisoformat(base)).days})
    conn.close()
    return jsonify(resultado)

@bp.route("/api/aprender", methods=["POST"])
def criar_aprender_rota():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _criar_aprender = app._criar_aprender
    body = _corpo_json()
    conn = get_db()
    resultado = _criar_aprender(conn, body.get("tema"), body.get("nota"))
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201

@bp.route("/api/aprender/<int:aprender_id>/<acao>", methods=["POST"])
def marcar_aprender_rota(aprender_id, acao):
    app = app_modulo()
    _marcar_atividade = app._marcar_atividade
    date = app.date
    campo = {"retomei": "ultima_vez", "concluido": "concluido_em"}.get(acao)
    if not campo:
        return jsonify({"error": "acao invalida"}), 404
    conn = get_db()
    ok = marcar_aprender(conn, aprender_id, campo, date.today().isoformat())
    if ok:
        _marcar_atividade(conn)
        conn.commit()
    conn.close()
    if not ok:
        return jsonify({"error": "tema nao encontrado"}), 404
    return jsonify({"ok": True})

@bp.route("/api/aprender/<int:aprender_id>", methods=["DELETE"])
def apagar_aprender(aprender_id):
    conn = get_db()
    delete_aprender(conn, aprender_id)
    conn.close()
    return jsonify({"ok": True})
