"""Faixa P3 - rotas de sessao (PIN) do assistente proativo: horario dos dois
briefings (GET/PUT) e previa sem enviar (GET), pra UI e teste.

Sao rotas de sessao, nao de token maquina-a-maquina: nao declaram
ROTAS_COM_TOKEN. A autenticacao e a mesma do resto do painel - o
before_request global de app.py ja bloqueia requisicao sem sessao antes de
chegar aqui (mesmo padrao de outras rotas de sessao ja existentes, ex.:
previa_noite_rota em app.py), entao este arquivo nao confere PIN por conta
propria.
"""

from datetime import date

from flask import Blueprint, jsonify, request

from assistente import briefing
from db import get_db

bp = Blueprint("p3_briefing", __name__)


def _corpo_json() -> dict:
    corpo = request.get_json(silent=True)
    return corpo if isinstance(corpo, dict) else {}


@bp.route("/api/assistente/briefing/horarios", methods=["GET"])
def obter_horarios():
    conn = get_db()
    try:
        resultado = {"manha": briefing.horario_manha(conn), "noite": briefing.horario_noite(conn)}
    finally:
        conn.close()
    return jsonify(resultado)


@bp.route("/api/assistente/briefing/horarios", methods=["PUT"])
def definir_horarios():
    corpo = _corpo_json()
    manha = corpo.get("manha")
    noite = corpo.get("noite")

    if manha is not None and not briefing.horario_valido(manha):
        return jsonify({"error": "horario 'manha' invalido, use HH:MM"}), 400
    if noite is not None and not briefing.horario_valido(noite):
        return jsonify({"error": "horario 'noite' invalido, use HH:MM"}), 400
    if manha is None and noite is None:
        return jsonify({"error": "informe 'manha' e/ou 'noite'"}), 400

    conn = get_db()
    try:
        if manha is not None:
            briefing.definir_horario_manha(conn, manha)
        if noite is not None:
            briefing.definir_horario_noite(conn, noite)
        resultado = {"manha": briefing.horario_manha(conn), "noite": briefing.horario_noite(conn)}
    finally:
        conn.close()
    return jsonify(resultado)


@bp.route("/api/assistente/briefing/previa", methods=["GET"])
def previa():
    tipo = request.args.get("tipo", "manha")
    if tipo not in ("manha", "noite"):
        return jsonify({"error": "tipo precisa ser 'manha' ou 'noite'"}), 400

    conn = get_db()
    try:
        hoje = date.today()
        dados = briefing.montar_manha(conn, hoje) if tipo == "manha" else briefing.montar_noite(conn, hoje)
    finally:
        conn.close()
    return jsonify(dados)
