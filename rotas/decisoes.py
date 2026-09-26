"""Blueprint decisoes - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import apagar_diario_decisao, create_decisao, create_diario_decisao, get_db, list_decisoes, list_diario_decisoes, list_memorias, registrar_resultado_diario_decisao
import json

bp = Blueprint("decisoes", __name__)

@bp.route("/api/diario-decisoes", methods=["GET"])
def diario_decisoes():
    app = app_modulo()
    _modo_visitante_ativo = app._modo_visitante_ativo
    if _modo_visitante_ativo():
        return jsonify([])
    conn = get_db()
    resultado = list_diario_decisoes(conn)
    conn.close()
    return jsonify(resultado)

@bp.route("/api/diario-decisoes", methods=["POST"])
def criar_diario_decisao():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _marcar_atividade = app._marcar_atividade
    _modo_visitante_ativo = app._modo_visitante_ativo
    _texto_seguro = app._texto_seguro
    if _modo_visitante_ativo():
        return jsonify({"error": "desative o modo visitante pra usar o diario de decisao"}), 403
    body = _corpo_json()
    decisao = _texto_seguro(body.get("decisao"))
    if not decisao:
        return jsonify({"error": "informe a decisao"}), 400
    contexto = _texto_seguro(body.get("contexto")) or None
    revisao_em = _texto_seguro(body.get("revisao_em")) or None

    conn = get_db()
    decisao_id = create_diario_decisao(conn, decisao, contexto, revisao_em)
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"id": decisao_id, "ok": True}), 201

@bp.route("/api/diario-decisoes/<int:decisao_id>/resultado", methods=["POST"])
def registrar_resultado_diario_decisao_rota(decisao_id):
    app = app_modulo()
    _corpo_json = app._corpo_json
    _modo_visitante_ativo = app._modo_visitante_ativo
    _texto_seguro = app._texto_seguro
    if _modo_visitante_ativo():
        return jsonify({"error": "desative o modo visitante pra usar o diario de decisao"}), 403
    body = _corpo_json()
    resultado = _texto_seguro(body.get("resultado"))
    if not resultado:
        return jsonify({"error": "informe o resultado"}), 400

    conn = get_db()
    ok = registrar_resultado_diario_decisao(conn, decisao_id, resultado)
    conn.close()
    if not ok:
        return jsonify({"error": "decisao nao encontrada"}), 404
    return jsonify({"ok": True})

@bp.route("/api/diario-decisoes/<int:decisao_id>", methods=["DELETE"])
def apagar_diario_decisao_rota(decisao_id):
    conn = get_db()
    apagar_diario_decisao(conn, decisao_id)
    conn.close()
    return jsonify({"ok": True})

@bp.route("/api/decisao", methods=["POST"])
def decisao():
    app = app_modulo()
    CLAUDE_FORMAT_ERROR_MSG = app.CLAUDE_FORMAT_ERROR_MSG
    _call_claude = app._call_claude
    _corpo_json = app._corpo_json
    _log_usage = app._log_usage
    _modo_visitante_ativo = app._modo_visitante_ativo
    claude_client = app.claude_client
    if _modo_visitante_ativo():
        return jsonify({"error": "desative o modo visitante pra usar o diario de decisao"}), 403
    bruto = _corpo_json().get("pergunta")
    pergunta = bruto.strip() if isinstance(bruto, str) else ""
    if not pergunta or len(pergunta) > 1000:
        return jsonify({"error": "escreva a decisao (ate 1000 caracteres)"}), 400
    conn = get_db()
    memorias = [m["texto"] for m in list_memorias(conn)]
    result, error = _call_claude(claude_client.analisar_decisao, pergunta, memorias)
    if error:
        conn.close()
        return error
    analise, usage = result
    if not isinstance(analise, dict):
        conn.close()
        return jsonify({"error": CLAUDE_FORMAT_ERROR_MSG}), 502
    _log_usage(conn, usage, "decisao")
    decisao_id = create_decisao(conn, pergunta, json.dumps(analise, ensure_ascii=False))
    conn.close()
    return jsonify({"id": decisao_id, "pergunta": pergunta, "analise": analise})

@bp.route("/api/decisoes", methods=["GET"])
def decisoes():
    app = app_modulo()
    _modo_visitante_ativo = app._modo_visitante_ativo
    if _modo_visitante_ativo():
        return jsonify([])
    conn = get_db()
    resultado = [
        {
            "id": d["id"],
            "pergunta": d["pergunta"],
            "analise": json.loads(d["analise_json"]),
            "criado_em": d["criado_em"],
        }
        for d in list_decisoes(conn)
    ]
    conn.close()
    return jsonify(resultado)
