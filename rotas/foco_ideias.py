"""Blueprint foco_ideias - Grupo A (Foco) do Laboratorio v4, 30/10/2026: E agora?, Por que travou?, Pacote de
tentacao, Um segundo antes e Recomeco. Logica em foco_ideias.py / recomeco.py; aqui so a casca HTTP dos botoes dos
cards (`e_agora`, `travou`, `pacote`, `segundo_antes`, `recomeco`) e do Atalho do iPhone."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

import foco_ideias
import recomeco
from db import get_db
from rotas._base import app_modulo

bp = Blueprint("foco_ideias", __name__)

# Atalho do iPhone (automacao "quando abrir o app X"): a rota confere o PROPRIO token (_token_atalho_valido)
ROTAS_COM_TOKEN = {"/api/atalho/segundo-antes"}


def _agora():
    return app_modulo()._agora_brasilia().replace(tzinfo=None)


def _escrita():
    """Visitante nao grava nada (devolve a resposta de recusa pronta, ou None)."""
    return app_modulo()._recusar_no_modo_visitante()


def _id(corpo, chave="task_id"):
    v = corpo.get(chave)
    return v if isinstance(v, int) and not isinstance(v, bool) else None


# ---------------------------------------------------------------- E agora?
@bp.route("/api/e-agora", methods=["GET"])
def e_agora():
    app = app_modulo()
    if app._modo_visitante_ativo():
        return jsonify({"oculto": True, "sugestoes": []})
    conn = get_db()
    try:
        return jsonify(foco_ideias.e_agora(conn, _agora(), app._eventos_de_hoje_com_seguranca(conn)))
    finally:
        conn.close()


@bp.route("/api/e-agora/bora", methods=["POST"])
def bora():
    recusa = _escrita()
    if recusa:
        return recusa
    tid = _id(app_modulo()._corpo_json())
    if tid is None:
        return jsonify({"error": "id inválido"}), 400
    conn = get_db()
    try:
        sessao = foco_ideias.bora(conn, _agora(), tid)
    finally:
        conn.close()
    if not sessao:
        return jsonify({"error": "essa tarefa não está mais aberta"}), 404
    return jsonify({"ok": True, "sessao": sessao})


# ---------------------------------------------------------------- Pacote de tentacao
@bp.route("/api/pacote", methods=["GET"])
def pacote_dados():
    if app_modulo()._modo_visitante_ativo():
        return jsonify({"oculto": True, "chatas": [], "premios": [], "ativos": []})
    conn = get_db()
    try:
        return jsonify(foco_ideias.pacote(conn))
    finally:
        conn.close()


@bp.route("/api/pacote", methods=["POST"])
def pacote_juntar():
    recusa = _escrita()
    if recusa:
        return recusa
    app = app_modulo()
    corpo = app._corpo_json()
    tid = _id(corpo)
    premio = app._texto_curto(corpo.get("premio"), 60) if isinstance(corpo.get("premio"), str) else ""
    if tid is None or not premio:
        return jsonify({"error": "mande a tarefa e o prêmio"}), 400
    conn = get_db()
    try:
        r = foco_ideias.juntar(conn, tid, premio)
    finally:
        conn.close()
    if not r:
        return jsonify({"error": "essa tarefa não está mais aberta"}), 404
    return jsonify({"ok": True, **r})


@bp.route("/api/pacote/desfazer", methods=["POST"])
def pacote_desfazer():
    recusa = _escrita()
    if recusa:
        return recusa
    tid = _id(app_modulo()._corpo_json())
    if tid is None:
        return jsonify({"error": "id inválido"}), 400
    conn = get_db()
    try:
        ok = foco_ideias.desfazer_pacote(conn, tid)
    finally:
        conn.close()
    return jsonify({"ok": True}) if ok else (jsonify({"error": "essa tarefa não tem pacote"}), 404)


# ---------------------------------------------------------------- Por que travou?
@bp.route("/api/travou/responder", methods=["POST"])
def travou_responder():
    recusa = _escrita()
    if recusa:
        return recusa
    corpo = app_modulo()._corpo_json()
    tid = _id(corpo)
    if tid is None or corpo.get("motivo") not in foco_ideias.MOTIVOS:
        return jsonify({"error": "mande a tarefa e o motivo"}), 400
    conn = get_db()
    try:
        r = foco_ideias.responder_travou(conn, tid, corpo["motivo"], _agora())
    finally:
        conn.close()
    return jsonify({"ok": True, "remedio": r}) if r else (jsonify({"error": "essa tarefa não está mais aberta"}), 404)


@bp.route("/api/travou/aplicar", methods=["POST"])
def travou_aplicar():
    recusa = _escrita()
    if recusa:
        return recusa
    app = app_modulo()
    corpo = app._corpo_json()
    tid = _id(corpo)
    acao = corpo.get("acao")
    if tid is None or acao not in ("juntar", "comecar", "passos"):
        return jsonify({"error": "mande a tarefa e a ação"}), 400
    premio = app._texto_curto(corpo.get("premio"), 60) if isinstance(corpo.get("premio"), str) else None
    conn = get_db()
    try:
        r = foco_ideias.aplicar_remedio(conn, _agora(), tid, acao, premio)
    finally:
        conn.close()
    return jsonify(r) if r else (jsonify({"error": "não deu pra aplicar (responde o motivo primeiro)"}), 409)


# ---------------------------------------------------------------- Recomeco
@bp.route("/api/recomeco", methods=["GET"])
def recomeco_estado():
    if app_modulo()._modo_visitante_ativo():
        return jsonify({"oculto": True, "itens": [], "total": 0})
    conn = get_db()
    try:
        return jsonify(recomeco.estado(conn, _agora().date()))
    finally:
        conn.close()


def _recomeco(fn, *args):
    recusa = _escrita()
    if recusa:
        return recusa
    conn = get_db()
    try:
        r = fn(conn, _agora().date(), *args)
    finally:
        conn.close()
    return jsonify({"ok": True, **r}) if r is not None else (jsonify({"error": "nada a fazer aí"}), 404)


@bp.route("/api/recomeco/arquivar", methods=["POST"])
def recomeco_arquivar():
    return _recomeco(lambda conn, hoje: recomeco.arquivar(conn, hoje, _agora()))


@bp.route("/api/recomeco/desfazer", methods=["POST"])
def recomeco_desfazer():
    return _recomeco(recomeco.desfazer)


@bp.route("/api/recomeco/devolver", methods=["POST"])
def recomeco_devolver():
    tid = _id(app_modulo()._corpo_json(), "id")
    if tid is None:
        return jsonify({"error": "id inválido"}), 400
    return _recomeco(recomeco.devolver, tid)


@bp.route("/api/recomeco/manter", methods=["POST"])
def recomeco_manter():
    ids = app_modulo()._corpo_json().get("ids")
    if not isinstance(ids, list) or not ids or len(ids) > recomeco.MAX_MANTER:
        return jsonify({"error": f"escolhe de 1 a {recomeco.MAX_MANTER}"}), 400
    return _recomeco(recomeco.manter, ids)


# ---------------------------------------------------------------- Um segundo antes
@bp.route("/api/segundo-antes", methods=["GET"])
def segundo_antes_tela():
    """Dado do card (preview da tela + quantas vezes voltou na semana). Sessao normal."""
    app = app_modulo()
    if app._modo_visitante_ativo():
        return jsonify({"oculto": True, "tarefa": None, "voltou_semana": 0})
    conn = get_db()
    try:
        return jsonify(foco_ideias.tela_segundo_antes(conn, _agora(), request.args.get("app", ""),
                                                      app._eventos_de_hoje_com_seguranca(conn)))
    finally:
        conn.close()


@bp.route("/api/segundo-antes", methods=["POST"])
def segundo_antes_escolha():
    recusa = _escrita()
    if recusa:
        return recusa
    app = app_modulo()
    corpo = app._corpo_json()
    conn = get_db()
    try:
        r = foco_ideias.registrar_escolha(conn, _agora(), corpo.get("escolha"), app._texto_curto(corpo.get("app"), 30) or "")
    finally:
        conn.close()
    return jsonify({"ok": True, **r}) if r else (jsonify({"error": "escolha 'voltou' ou 'seguiu'"}), 400)


@bp.route("/api/atalho/segundo-antes", methods=["GET", "POST"])
def atalho_segundo_antes():
    """Automacao "quando abrir o app X" do Atalhos. GET -> a tela (pergunta, tarefa do momento, voltou na semana).
    POST {escolha: voltou|seguiu, app} -> conta e devolve a mensagem curta. Nao bloqueia nada."""
    app = app_modulo()
    if not app._token_atalho_valido(obrigatorio=True):
        return jsonify({"error": "token inválido"}), 401
    conn = get_db()
    try:
        if request.method == "GET":
            return jsonify(foco_ideias.tela_segundo_antes(conn, _agora(), request.args.get("app", ""),
                                                          app._eventos_de_hoje_com_seguranca(conn)))
        corpo = app._corpo_json()
        r = foco_ideias.registrar_escolha(conn, _agora(), corpo.get("escolha"), app._texto_curto(corpo.get("app"), 30) or "")
    finally:
        conn.close()
    return jsonify({"ok": True, **r}) if r else (jsonify({"error": "escolha 'voltou' ou 'seguiu'"}), 400)
