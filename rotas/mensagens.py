"""Blueprint mensagens - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import create_responder, get_db, list_responder_pendentes, marcar_respondido

bp = Blueprint("mensagens", __name__)

@bp.route("/api/responder", methods=["GET"])
def responder_pendentes():
    app = app_modulo()
    date = app.date
    datetime = app.datetime
    hoje = date.today()
    conn = get_db()
    resultado = []
    for r in list_responder_pendentes(conn):
        dias = (hoje - datetime.fromisoformat(r["criado_em"]).date()).days
        resultado.append({**r, "dias": dias})
    conn.close()
    return jsonify(resultado)

@bp.route("/api/responder", methods=["POST"])
def criar_responder_rota():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _texto_curto = app._texto_curto
    body = _corpo_json()
    quem = _texto_curto(body.get("quem"), 60)
    if not quem:
        return jsonify({"error": "informe pra quem voce precisa responder"}), 400
    conn = get_db()
    responder_id = create_responder(conn, quem, _texto_curto(body.get("sobre"), 200))
    conn.close()
    return jsonify({"ok": True, "id": responder_id}), 201

@bp.route("/api/responder/<int:responder_id>/feito", methods=["POST"])
def responder_feito(responder_id):
    app = app_modulo()
    _marcar_atividade = app._marcar_atividade
    conn = get_db()
    marcar_respondido(conn, responder_id)
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@bp.route("/api/mensagem-dificil", methods=["POST"])
def mensagem_dificil():
    app = app_modulo()
    CLAUDE_FORMAT_ERROR_MSG = app.CLAUDE_FORMAT_ERROR_MSG
    _call_claude = app._call_claude
    _corpo_json = app._corpo_json
    _log_usage = app._log_usage
    _texto_curto = app._texto_curto
    claude_client = app.claude_client
    body = _corpo_json()
    situacao = _texto_curto(body.get("situacao"), 1500)
    if not situacao:
        return jsonify({"error": "conte a situacao (ate 1500 caracteres)"}), 400
    para_quem = _texto_curto(body.get("para_quem"), 60)
    conn = get_db()
    result, error = _call_claude(claude_client.redigir_mensagem_dificil, situacao, para_quem)
    if error:
        conn.close()
        return error
    versoes, usage = result
    if not isinstance(versoes, dict) or not all(isinstance(versoes.get(k), str) for k in ("direta", "gentil")):
        conn.close()
        return jsonify({"error": CLAUDE_FORMAT_ERROR_MSG}), 502
    _log_usage(conn, usage, "mensagem_dificil")
    conn.close()
    return jsonify({"direta": versoes["direta"], "gentil": versoes["gentil"]})
