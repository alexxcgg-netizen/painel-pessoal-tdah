"""Blueprint estudo - resposta do quiz de aviacao pelo clique no card (2026-10-13).

A pergunta nasce no chat (ferramenta fazer_pergunta_aviacao); aqui so corrige e agenda a
revisao (estudo_quiz.responder). Login global (rotas/__init__.py)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify

import db
import estudo_quiz
from rotas._base import app_modulo

bp = Blueprint("estudo", __name__)


@bp.route("/api/estudo/responder", methods=["POST"])
def estudo_responder():
    app = app_modulo()
    corpo = app._corpo_json()
    pergunta_id = corpo.get("id")
    if isinstance(pergunta_id, bool) or not isinstance(pergunta_id, int) or pergunta_id <= 0:
        return jsonify({"error": "id inválido"}), 400
    if estudo_quiz.letra_pra_indice(corpo.get("alternativa")) is None:
        return jsonify({"error": "alternativa tem que ser A, B, C ou D"}), 400
    hoje = datetime.now(timezone(timedelta(hours=-3))).date()
    conn = db.get_db()
    try:
        r = estudo_quiz.responder(conn, pergunta_id, corpo.get("alternativa"), hoje)
    finally:
        conn.close()
    if r.get("erro"):
        return jsonify({"error": r["erro"]}), 404
    return jsonify(r)
