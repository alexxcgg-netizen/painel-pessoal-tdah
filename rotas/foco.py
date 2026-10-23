"""Blueprint foco - botoes do card `foco` (Parceiro de foco, leva 22/10). Logica em foco.py; quem abre a
sessao e a ferramenta `parceiro_foco` do chat."""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import get_db
import foco

bp = Blueprint("foco", __name__)

RESPOSTAS = ("ainda", "travei", "fim", "mais", "largar")


def _sessao_id(corpo):
    v = corpo.get("id")
    return v if isinstance(v, int) and not isinstance(v, bool) else None


@bp.route("/api/foco", methods=["GET"])
def estado_foco():
    """Estado ao vivo (o card do historico sincroniza o relogio daqui)."""
    app = app_modulo()
    if app._modo_visitante_ativo():
        return jsonify({"sessao": None})
    conn = get_db()
    try:
        return jsonify({"sessao": foco.estado(conn, datetime.now())})
    finally:
        conn.close()


def _acao(fn, extra=lambda corpo: ()):
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    corpo = app._corpo_json()
    sid = _sessao_id(corpo)
    if sid is None:
        return jsonify({"error": "id da sessão inválido"}), 400
    conn = get_db()
    try:
        e = fn(conn, datetime.now(), *extra(corpo), sessao_id=sid)
    finally:
        conn.close()
    if e is None:
        return jsonify({"error": "essa sessão de foco já fechou"}), 409
    return jsonify({"ok": True, "sessao": e})


@bp.route("/api/foco/comecar", methods=["POST"])
def comecar():
    return _acao(foco.comecar)


@bp.route("/api/foco/pausar", methods=["POST"])
def pausar():
    return _acao(foco.pausar)


@bp.route("/api/foco/responder", methods=["POST"])
def responder():
    app = app_modulo()
    r = app._corpo_json().get("r")
    if r not in RESPOSTAS:
        return jsonify({"error": "resposta inválida"}), 400
    return _acao(foco.responder, lambda c: (r,))
