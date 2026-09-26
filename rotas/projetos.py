"""Blueprint projetos - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import apagar_etapa_projeto, concluir_etapa_projeto, definir_status_projeto, delete_projeto, get_db, list_projetos

bp = Blueprint("projetos", __name__)

@bp.route("/api/projetos", methods=["GET"])
def projetos_rota():
    app = app_modulo()
    _projeto_detalhado = app._projeto_detalhado
    date = app.date
    conn = get_db()
    resultado = [_projeto_detalhado(conn, p, date.today()) for p in list_projetos(conn)]
    conn.close()
    return jsonify(resultado)

@bp.route("/api/projetos", methods=["POST"])
def criar_projeto_rota():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _criar_projeto = app._criar_projeto
    body = _corpo_json()
    conn = get_db()
    resultado = _criar_projeto(conn, body.get("nome"), body.get("prazo_final"))
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201

@bp.route("/api/projetos/<int:projeto_id>", methods=["DELETE"])
def apagar_projeto_rota(projeto_id):
    conn = get_db()
    delete_projeto(conn, projeto_id)
    conn.close()
    return jsonify({"ok": True})

@bp.route("/api/projetos/<int:projeto_id>/status", methods=["POST"])
def definir_status_projeto_rota(projeto_id):
    app = app_modulo()
    _corpo_json = app._corpo_json
    status = _corpo_json().get("status")
    conn = get_db()
    ok = definir_status_projeto(conn, projeto_id, status)
    conn.close()
    if not ok:
        return jsonify({"error": "projeto não encontrado ou status inválido (no_rumo/atrasado/pausado)"}), 400
    return jsonify({"ok": True})

@bp.route("/api/projetos/<int:projeto_id>/etapas", methods=["POST"])
def adicionar_etapa_rota(projeto_id):
    app = app_modulo()
    _adicionar_etapa = app._adicionar_etapa
    _corpo_json = app._corpo_json
    body = _corpo_json()
    conn = get_db()
    resultado = _adicionar_etapa(conn, projeto_id, body.get("texto"), body.get("data_prevista"))
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201

@bp.route("/api/projetos/etapas/<int:etapa_id>/concluir", methods=["POST"])
def concluir_etapa_rota(etapa_id):
    conn = get_db()
    projeto_id = concluir_etapa_projeto(conn, etapa_id)
    conn.close()
    if projeto_id is None:
        return jsonify({"error": "etapa não encontrada"}), 404
    return jsonify({"ok": True, "projeto_id": projeto_id})

@bp.route("/api/projetos/etapas/<int:etapa_id>", methods=["DELETE"])
def apagar_etapa_rota(etapa_id):
    conn = get_db()
    projeto_id = apagar_etapa_projeto(conn, etapa_id)
    conn.close()
    if projeto_id is None:
        return jsonify({"error": "etapa não encontrada"}), 404
    return jsonify({"ok": True})
