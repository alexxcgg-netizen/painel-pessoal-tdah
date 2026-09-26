"""Blueprint config - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from rotas._base import app_modulo
from db import definir_configuracao, get_db, obter_configuracao
import auth

bp = Blueprint("config", __name__)

@bp.route("/api/modo-visitante", methods=["GET"])
def modo_visitante_rota():
    app = app_modulo()
    _modo_visitante_ativo = app._modo_visitante_ativo
    return jsonify({"ativo": _modo_visitante_ativo()})

@bp.route("/api/modo-visitante", methods=["POST"])
def alternar_modo_visitante_rota():
    """Ativar e livre (1 toque, pra dar tempo de esconder a tela antes de
    passar o celular pra alguem). Desativar exige o PIN de verdade - senao
    quem ja esta com o celular desbloqueado (a propria pessoa de quem voce
    esta escondendo o dado) conseguiria desligar sozinha so cutucando um
    botao."""
    app = app_modulo()
    _corpo_json = app._corpo_json
    body = _corpo_json()
    if bool(body.get("ativar")):
        session["modo_visitante"] = True
        return jsonify({"ativo": True})

    ip = request.remote_addr or "desconhecido"
    conn = get_db()
    try:
        pode_tentar, msg_bloqueio = auth.verificar_bloqueio(conn, ip)
        if not pode_tentar:
            return jsonify({"error": msg_bloqueio}), 429
        pin_ok = auth.verificar_pin(conn, body.get("pin"))
        auth.registrar_tentativa(conn, ip, sucesso=pin_ok)
    finally:
        conn.close()
    if not pin_ok:
        return jsonify({"error": "PIN incorreto"}), 403
    session["modo_visitante"] = False
    return jsonify({"ativo": False})

@bp.route("/api/configuracoes/teste-ia", methods=["GET"])
def obter_teste_ia():
    app = app_modulo()
    _modo_teste_ia_ativo = app._modo_teste_ia_ativo
    conn = get_db()
    try:
        return jsonify({"ativo": _modo_teste_ia_ativo(conn)})
    finally:
        conn.close()

@bp.route("/api/configuracoes/teste-ia", methods=["POST"])
def definir_teste_ia():
    app = app_modulo()
    _corpo_json = app._corpo_json
    body = _corpo_json()
    ativo = bool(body.get("ativo"))
    conn = get_db()
    try:
        definir_configuracao(conn, "modo_teste_ia", "1" if ativo else "0")
    finally:
        conn.close()
    return jsonify({"ativo": ativo})

@bp.route("/api/configuracoes/silencio", methods=["GET"])
def obter_silencio():
    conn = get_db()
    inicio = obter_configuracao(conn, "silencio_inicio") or "22:00"
    fim = obter_configuracao(conn, "silencio_fim") or "07:00"
    # Fase 5 (US-C4): notificacao agrupada mora no mesmo endpoint/mecanismo
    # do modo silencioso configuravel (mesma tabela `configuracoes`, mesmo
    # painel de ajustes de notificacao) em vez de um sistema paralelo -
    # desligada por padrao pra nao mudar o comportamento de quem nunca
    # mexeu nisso.
    agrupar = (obter_configuracao(conn, "notificacoes_agrupar") or "0") == "1"
    agrupar_janela_min = int(obter_configuracao(conn, "notificacoes_agrupar_janela_min") or "2")
    conn.close()
    return jsonify({"inicio": inicio, "fim": fim, "agrupar": agrupar, "agrupar_janela_min": agrupar_janela_min})

@bp.route("/api/configuracoes/silencio", methods=["POST"])
def definir_silencio():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _normalizar_hora = app._normalizar_hora
    corpo = _corpo_json()
    inicio = _normalizar_hora(corpo.get("inicio"))
    fim = _normalizar_hora(corpo.get("fim"))
    if not inicio or not fim:
        return jsonify({"error": "horário inválido - use HH:MM"}), 400

    conn = get_db()
    definir_configuracao(conn, "silencio_inicio", inicio)
    definir_configuracao(conn, "silencio_fim", fim)

    resultado = {"ok": True, "inicio": inicio, "fim": fim}
    if "agrupar" in corpo:
        agrupar = bool(corpo.get("agrupar"))
        definir_configuracao(conn, "notificacoes_agrupar", "1" if agrupar else "0")
        resultado["agrupar"] = agrupar
    if "agrupar_janela_min" in corpo:
        try:
            janela = int(corpo.get("agrupar_janela_min"))
        except (TypeError, ValueError):
            conn.close()
            return jsonify({"error": "agrupar_janela_min precisa ser um número inteiro"}), 400
        if janela < 1:
            conn.close()
            return jsonify({"error": "agrupar_janela_min precisa ser pelo menos 1"}), 400
        definir_configuracao(conn, "notificacoes_agrupar_janela_min", str(janela))
        resultado["agrupar_janela_min"] = janela

    conn.close()
    return jsonify(resultado)
