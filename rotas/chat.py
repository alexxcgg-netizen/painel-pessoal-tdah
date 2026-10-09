"""Blueprint chat - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import cards_de_mensagem_chat, get_db, list_chat_mensagens
import cards
import db

bp = Blueprint("chat", __name__)

@bp.route("/api/chat", methods=["POST"])
def chat():
    app = app_modulo()
    MSG_TEXTO_LONGO = app.MSG_TEXTO_LONGO
    TAMANHO_MAX_TEXTO_CHAT = app.TAMANHO_MAX_TEXTO_CHAT
    TETO_IA_MSG = app.TETO_IA_MSG
    _corpo_json = app._corpo_json
    _processar_mensagem_chat = app._processar_mensagem_chat
    _resposta_contrato = app._resposta_contrato
    _texto_seguro = app._texto_seguro
    body = _corpo_json()
    texto = _texto_seguro(body.get("mensagem"))
    if not texto:
        return jsonify({"error": "mensagem vazia"}), 400
    if len(texto) > TAMANHO_MAX_TEXTO_CHAT:
        return jsonify({"error": MSG_TEXTO_LONGO}), 400

    conn = get_db()
    detalhes: dict = {}
    resposta, acoes, erro = _processar_mensagem_chat(conn, texto, detalhes, modo_voz=body.get("modo") == "voz")
    conn.close()
    if erro:
        return jsonify({"error": erro}), 402 if erro == TETO_IA_MSG else 502
    # `resposta`/`acoes` = campos legados (frontend antigo em cache do PWA);
    # cards/resumo_texto/passos = contrato da Fase 6 (docs/CARDS.md).
    corpo = {"resposta": resposta, "acoes": acoes}
    corpo.update(detalhes or cards.envelope([], resposta, []))
    return jsonify(_resposta_contrato(corpo))

@bp.route("/api/chat/historico", methods=["GET"])
def chat_historico():
    app = app_modulo()
    _modo_visitante_ativo = app._modo_visitante_ativo
    conn = get_db()
    mensagens = list(reversed(list_chat_mensagens(conn, limit=30)))
    conn.close()
    visitante = _modo_visitante_ativo()
    for m in mensagens:
        m["cards"] = cards_de_mensagem_chat(m)
    # US-E5: card cujo Desfazer ja foi usado volta marcado como desfeito
    # (campo aditivo `desfeito` no card, docs/CARDS.md).
    tokens = [
        a.get("token")
        for m in mensagens
        for c in m["cards"]
        for a in (c.get("actions") or [])
        if isinstance(a, dict) and a.get("tipo") == "desfazer"
    ]
    conn = get_db()
    desfeitos = db.tokens_desfeitos(conn, tokens)
    conn.close()
    for m in mensagens:
        for c in m["cards"]:
            if any(isinstance(a, dict) and a.get("token") in desfeitos for a in (c.get("actions") or [])):
                c["desfeito"] = True
        # Fase 6: os cards da resposta ficam gravados junto da mensagem
        # (cards_json, criptografado em repouso como o resto do dado
        # financeiro) - recarregar a pagina nao perde os cards.
        m.pop("cards_json", None)
        if visitante and m["papel"] == "assistant":
            m["cards"] = cards.mascarar_cards(m["cards"])
            m["texto"] = cards.ocultar_valores_texto(m["texto"])
    return jsonify(mensagens)
