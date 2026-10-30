"""Grupo G do lab v4 (2026-10-30): rotas do Placar do feito, do Pouso do dia e da Retrospectiva.

  GET/POST /api/feito-hoje, DELETE /api/feito-hoje/<id>   - placar (o que ele fez, inclusive fora do plano)
  GET /api/pouso-dia/amanha, POST /api/pouso-dia/pousar    - passos 2 e 3 do pouso, e "Dia pousado."
  GET /api/retrospectiva/<AAAA-MM>, POST .../meta          - historia do mes e a meta do mes novo

Regra: a rota que grava nao funciona no modo visitante. Logica em fechamento_dia.py / retrospectiva.py.
"""

from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, jsonify

import fechamento_dia
import retrospectiva
from db import get_db
from rotas._base import app_modulo

bp = Blueprint("fechamento_v4", __name__)

DIAS_ACEITOS_PRA_TRAS = 2  # o card de ontem ainda aceita "fiz isso ontem"


def _dia_do_corpo(app, corpo) -> date | None:
    """`dia` opcional do corpo (o do card): hoje ou ate 2 dias atras. Sem `dia` = hoje."""
    hoje = app._agora_brasilia().date()
    bruto = corpo.get("dia")
    if bruto in (None, ""):
        return hoje
    try:
        dia = date.fromisoformat(str(bruto))
    except ValueError:
        return None
    return dia if hoje - timedelta(days=DIAS_ACEITOS_PRA_TRAS) <= dia <= hoje else None


@bp.route("/api/feito-hoje", methods=["GET"])
def feito_hoje():
    app = app_modulo()
    conn = get_db()
    try:
        agora = app._agora_brasilia()
        dados = fechamento_dia.dados_placar(conn, agora.date(), agora.strftime("%H:%M"))
    finally:
        conn.close()
    return jsonify(dados)


@bp.route("/api/feito-hoje", methods=["POST"])
def feito_hoje_adicionar():
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    corpo = app._corpo_json()
    dia = _dia_do_corpo(app, corpo)
    if dia is None:
        return jsonify({"error": "dia inválido"}), 400
    conn = get_db()
    try:
        item = fechamento_dia.adicionar_extra(conn, corpo.get("texto"), dia)
        if not item:
            return jsonify({"error": "escreve o que tu fez"}), 400
        total = len(fechamento_dia.feitos_do_dia(conn, dia))
        if item["novo"]:
            app._marcar_atividade(conn)
            conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, "item": {**item, "origem": "extra", "rotulo": "fora do plano"}, "total": total}), \
        (201 if item["novo"] else 200)


@bp.route("/api/feito-hoje/<int:extra_id>", methods=["DELETE"])
def feito_hoje_remover(extra_id):
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    conn = get_db()
    try:
        ok = fechamento_dia.remover_extra(conn, extra_id)
    finally:
        conn.close()
    return jsonify({"ok": ok}), (200 if ok else 404)


@bp.route("/api/pouso-dia/amanha", methods=["GET"])
def pouso_amanha():
    """Passos 2 e 3 do pouso, frescos (depois de empurrar tarefas pra amanha, a primeira coisa muda)."""
    app = app_modulo()
    conn = get_db()
    try:
        hoje = app._agora_brasilia().date()
        return jsonify({"primeira": fechamento_dia.primeira_de_amanha(conn, hoje),
                        "mochila": fechamento_dia.mochila_de_amanha(conn, hoje)})
    finally:
        conn.close()


@bp.route("/api/pouso-dia/pousar", methods=["POST"])
def pouso_pousar():
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    dia = _dia_do_corpo(app, app._corpo_json())
    if dia is None:
        return jsonify({"error": "dia inválido"}), 400
    conn = get_db()
    try:
        fechamento_dia.marcar_pousado(conn, dia)
    finally:
        conn.close()
    return jsonify({"ok": True, "dia": dia.isoformat()})


@bp.route("/api/retrospectiva/<mes>", methods=["GET"])
def retrospectiva_mes(mes):
    app = app_modulo()
    alvo = retrospectiva.parse_mes(mes)
    if not alvo:
        return jsonify({"error": "mês inválido (use AAAA-MM)"}), 400
    conn = get_db()
    try:
        c = retrospectiva.card(conn, alvo[0], alvo[1], app._agora_brasilia().date())
    finally:
        conn.close()
    if not c:
        return jsonify({"error": "esse mês não tem nada pra contar"}), 404
    dados = dict(c["data"])
    if app._modo_visitante_ativo():
        dados.pop("gasto_cresceu", None)
        dados["oculto"] = True
    return jsonify(dados)


@bp.route("/api/retrospectiva/<mes>/meta", methods=["POST"])
def retrospectiva_meta(mes):
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    alvo = retrospectiva.parse_mes(mes)
    if not alvo:
        return jsonify({"error": "mês inválido (use AAAA-MM)"}), 400
    conn = get_db()
    try:
        texto = retrospectiva.escolher_meta(conn, alvo[0], alvo[1], app._corpo_json().get("meta"))
    finally:
        conn.close()
    if not texto:
        return jsonify({"error": "escolhe uma meta"}), 400
    return jsonify({"ok": True, "meta": texto})
