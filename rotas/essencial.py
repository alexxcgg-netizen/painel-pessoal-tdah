"""Blueprint essencial - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import definir_configuracao, get_db, get_essencial, obter_configuracao, salvar_essencial
import json

bp = Blueprint("essencial", __name__)

@bp.route("/api/essencial", methods=["GET"])
def essencial():
    app = app_modulo()
    _essencial_detalhado = app._essencial_detalhado
    _gerar_essencial = app._gerar_essencial
    date = app.date
    hoje = date.today()
    conn = get_db()
    if obter_configuracao(conn, "essencial_gerado_em") != hoje.isoformat():
        _gerar_essencial(conn, hoje)
        definir_configuracao(conn, "essencial_gerado_em", hoje.isoformat())
    resultado = {
        "modo_ativo": obter_configuracao(conn, "modo_essencial_data") == hoje.isoformat(),
        "tarefas": _essencial_detalhado(conn, hoje),
    }
    conn.close()
    return jsonify(resultado)

@bp.route("/api/essencial/gerar", methods=["POST"])
def regerar_essencial():
    app = app_modulo()
    _essencial_detalhado = app._essencial_detalhado
    _gerar_essencial = app._gerar_essencial
    date = app.date
    hoje = date.today()
    conn = get_db()
    _gerar_essencial(conn, hoje)
    definir_configuracao(conn, "essencial_gerado_em", hoje.isoformat())
    tarefas = _essencial_detalhado(conn, hoje)
    conn.close()
    return jsonify({"tarefas": tarefas})

@bp.route("/api/essencial/trocar", methods=["POST"])
def trocar_essencial():
    app = app_modulo()
    _candidatas_essencial = app._candidatas_essencial
    _corpo_json = app._corpo_json
    _essencial_detalhado = app._essencial_detalhado
    date = app.date
    task_id = _corpo_json().get("task_id")
    hoje = date.today()
    conn = get_db()
    atuais = get_essencial(conn, hoje.isoformat())
    ja_usadas = {e["task_id"] for e in atuais}
    if isinstance(task_id, bool) or task_id not in ja_usadas:
        conn.close()
        return jsonify({"error": "essa tarefa não esta no essencial de hoje"}), 400
    restantes = [(e["task_id"], e["motivo"]) for e in atuais if e["task_id"] != task_id]
    try:
        rejeitadas = json.loads(obter_configuracao(conn, "essencial_rejeitadas") or "{}")
    except ValueError:
        rejeitadas = {}
    ids_rejeitados = set(rejeitadas.get("ids", [])) if rejeitadas.get("data") == hoje.isoformat() else set()
    ids_rejeitados.add(task_id)
    definir_configuracao(
        conn, "essencial_rejeitadas", json.dumps({"data": hoje.isoformat(), "ids": sorted(ids_rejeitados)})
    )
    for t in _candidatas_essencial(conn, hoje):
        if t["id"] not in ja_usadas and t["id"] not in ids_rejeitados:
            restantes.append((t["id"], None))
            break
    salvar_essencial(conn, hoje.isoformat(), restantes)
    tarefas = _essencial_detalhado(conn, hoje)
    conn.close()
    return jsonify({"tarefas": tarefas})

@bp.route("/api/essencial/modo", methods=["POST"])
def modo_essencial():
    app = app_modulo()
    _corpo_json = app._corpo_json
    date = app.date
    ativo = _corpo_json().get("ativo") is True
    conn = get_db()
    definir_configuracao(conn, "modo_essencial_data", date.today().isoformat() if ativo else "")
    conn.close()
    return jsonify({"modo_ativo": ativo})
