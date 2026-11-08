"""Blueprint lembretes - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import create_lembrete, delete_lembrete, get_db, list_lembretes
import db
import notificacoes
import vida

bp = Blueprint("lembretes", __name__)

@bp.route("/api/lembretes", methods=["GET"])
def lembretes():
    app = app_modulo()
    date = app.date
    conn = get_db()
    resultado = list_lembretes(conn)
    conn.close()
    # Pedido do Alex ("datas importantes" parecia simples demais): manda a
    # PROXIMA ocorrencia + dias restantes calculados, nao so a data crua -
    # sem isso um lembrete recorrente mostrava o ano ORIGINAL de criacao pra
    # sempre, nunca o proximo aniversario de verdade.
    hoje = date.today()
    for item in resultado:
        # 08/11: linha antiga gravada torta pelo chat ("2026-11-15T09:00", "") derrubava a lista inteira
        # com 500 - le pelo mesmo normalizador do executor; o que nao for data vira sem proxima ocorrencia
        try:
            data_item = app._data_iso(item["data"])
        except ValueError:
            data_item = None
        if not data_item:
            item["proxima_ocorrencia"] = None
            item["dias_restantes"] = None
            item["sugestao"] = vida.sugestao_acao_data(item["titulo"])
            continue
        proxima = notificacoes.proxima_ocorrencia_lembrete(
            date.fromisoformat(data_item), bool(item["recorrente"]), hoje
        )
        item["proxima_ocorrencia"] = proxima.isoformat()
        item["dias_restantes"] = (proxima - hoje).days
        item["sugestao"] = vida.sugestao_acao_data(item["titulo"])
    return jsonify(resultado)

@bp.route("/api/lembretes", methods=["POST"])
def criar_lembrete():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _marcar_atividade = app._marcar_atividade
    date = app.date
    body = _corpo_json()
    titulo = (body.get("titulo") or "").strip()
    data_str = (body.get("data") or "").strip()
    recorrente = bool(body.get("recorrente", False))
    if not titulo:
        return jsonify({"error": "informe um titulo"}), 400
    try:  # 08/11: mesmo normalizador do chat - grava sempre AAAA-MM-DD ("20261115" passava cru)
        data_str = app._data_iso(data_str)
    except (ValueError, TypeError):
        data_str = None
    if not data_str:
        return jsonify({"error": "data precisa estar em formato AAAA-MM-DD"}), 400

    conn = get_db()
    lembrete_id = create_lembrete(conn, titulo, data_str, recorrente)
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"id": lembrete_id, "ok": True}), 201

@bp.route("/api/lembretes/<int:lembrete_id>", methods=["DELETE"])
def apagar_lembrete(lembrete_id):
    conn = get_db()
    delete_lembrete(conn, lembrete_id)
    conn.close()
    return jsonify({"ok": True})

@bp.route("/api/lembretes/<int:lembrete_id>/despertar", methods=["POST"])
def despertar_lembrete(lembrete_id):
    """Fase 6 (US-E3, botao "Desperta voce" do card de lembrete): liga/
    desliga um push NO HORARIO do lembrete (hora, ou 09:00 quando o lembrete
    e so por dia) - o PWA nao consegue tocar alarme de verdade, entao o
    "despertar" e a notificacao push (ver notificacoes.lembretes_para_despertar)."""
    app = app_modulo()
    _corpo_json = app._corpo_json
    ativo = _corpo_json().get("ativo", True)
    if not isinstance(ativo, bool):
        return jsonify({"error": "ativo deve ser true ou false"}), 400
    conn = get_db()
    ok = db.definir_despertar_lembrete(conn, lembrete_id, ativo)
    conn.close()
    if not ok:
        return jsonify({"error": "lembrete não encontrado"}), 404
    return jsonify({"ok": True, "ativo": ativo})
