"""Blueprint memorias - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import CATEGORIAS_MEMORIA, create_memoria, delete_memoria, get_db, list_memorias, update_memoria

bp = Blueprint("memorias", __name__)

@bp.route("/api/memorias", methods=["GET"])
def memorias():
    conn = get_db()
    resultado = list_memorias(conn)
    conn.close()
    return jsonify(resultado)

@bp.route("/api/memorias", methods=["POST"])
def criar_memoria_rota():
    """Fase 6 (US-E10): cria uma memoria - com `categoria` (um dos 3 grupos
    fixos de "O que eu lembro sobre voce": sua_rotina/seus_planos/
    fora_do_painel) quando adicionada por um dos formularios de grupo, ou
    sem categoria (generica, mesmo caminho que `registrar_memoria` do chat
    ja usava) quando omitida.

    Modo visitante: 403 (revisao da Fase 6) - memoria entra no system prompt
    do chat, seria uma injecao persistente."""
    app = app_modulo()
    _corpo_json = app._corpo_json
    _recusar_no_modo_visitante = app._recusar_no_modo_visitante
    _texto_curto = app._texto_curto
    recusa = _recusar_no_modo_visitante()
    if recusa:
        return recusa
    body = _corpo_json()
    texto = _texto_curto(body.get("texto"), 500)
    if not texto:
        return jsonify({"error": "informe o texto"}), 400
    categoria = body.get("categoria")
    if categoria is not None and categoria not in CATEGORIAS_MEMORIA:
        return jsonify({"error": "categoria invalida"}), 400
    conn = get_db()
    memoria_id = create_memoria(conn, texto, None, categoria)
    conn.close()
    return jsonify({"ok": True, "memoria_id": memoria_id}), 201

@bp.route("/api/memorias/<int:memoria_id>", methods=["PUT"])
def editar_memoria_rota(memoria_id):
    """Fase 6 (US-E10): edicao no lugar do texto (categoria/source_text nao
    mudam) - os 3 grupos fixos e a lista generica sao editaveis na tela."""
    app = app_modulo()
    _corpo_json = app._corpo_json
    _recusar_no_modo_visitante = app._recusar_no_modo_visitante
    _texto_curto = app._texto_curto
    recusa = _recusar_no_modo_visitante()
    if recusa:
        return recusa
    body = _corpo_json()
    texto = _texto_curto(body.get("texto"), 500)
    if not texto:
        return jsonify({"error": "informe o texto"}), 400
    conn = get_db()
    ok = update_memoria(conn, memoria_id, texto)
    conn.close()
    if not ok:
        return jsonify({"error": "memoria nao encontrada"}), 404
    return jsonify({"ok": True})

@bp.route("/api/memorias/<int:memoria_id>", methods=["DELETE"])
def apagar_memoria(memoria_id):
    app = app_modulo()
    _recusar_no_modo_visitante = app._recusar_no_modo_visitante
    recusa = _recusar_no_modo_visitante()
    if recusa:
        return recusa
    conn = get_db()
    delete_memoria(conn, memoria_id)
    conn.close()
    return jsonify({"ok": True})
