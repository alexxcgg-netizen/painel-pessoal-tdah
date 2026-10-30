"""Fase 7, faixa P7 (sinais do iPhone via app Atalhos).

POST /api/sinal recebe eventos genericos mandados pelas automacoes pessoais
do app Atalhos (Automacao pessoal -> Chegar/Sair de local, Alarme parado,
Modo Sono, Carregador conectado - ver docs/atalhos-sinais.md) e grava uma
linha em `sinais` (migracoes/202609241240_p7_sinais.sql). Alimenta o motor
de regras da faixa P4 e a propria P7 via assistente/sinais.py
(ultimos_sinais/sinal_recente/reagir).

Nao confundir com /api/atalho/local (app.py, ja existente, nao mexido aqui):
aquele e especifico pra geofence casa/mercado, autentica por
X-Webhook-Token/PAINEL_ATALHOS_TOKEN e devolve uma MENSAGEM pro proprio
Atalho mostrar na hora (com dedup de 2h). Este endpoint e generico (qualquer
tipo de sinal), autentica por Authorization: Bearer/PAINEL_SINAL_TOKEN (rota
maquina-a-maquina declarada em ROTAS_COM_TOKEN - Etapa 0) e so devolve um
JSON curto de confirmacao, nunca uma mensagem de display.

A validacao de verdade (token, tipo, formato de `quando`) e a gravacao
mesma moram em assistente/sinais.py (token_valido/quando_valido/gravar) -
propositalmente, pra dar pra testar tudo isso sem precisar da infra de
Blueprint (rotas/_base.py, Etapa 0/X1) estar mesclada. Este arquivo fica so
com o pouco que so faz sentido dentro de uma requisicao Flask."""

import os
from datetime import datetime

from flask import Blueprint, jsonify, request

import db
from assistente.sinais import TIPOS_VALIDOS, gravar, quando_valido, reagir, token_valido
from rotas._base import app_modulo

bp = Blueprint("p7_sinais", __name__)
ROTAS_COM_TOKEN = {"/api/sinal"}


@bp.route("/api/sinal", methods=["POST"])
def registrar_sinal():
    if not token_valido(request.headers.get("Authorization"), os.environ.get("PAINEL_SINAL_TOKEN")):
        return jsonify({"error": "token inválido"}), 401
    app = app_modulo()
    corpo = app._corpo_json()

    tipo = corpo.get("tipo")
    if tipo not in TIPOS_VALIDOS:
        return jsonify({"error": "tipo inválido - use um de: " + ", ".join(TIPOS_VALIDOS)}), 400

    lugar_bruto = corpo.get("lugar")
    if lugar_bruto is not None and not isinstance(lugar_bruto, str):
        return jsonify({"error": "lugar precisa ser texto"}), 400
    lugar = app._texto_curto(lugar_bruto, 120) if lugar_bruto else None

    quando_bruto = corpo.get("quando")
    if quando_bruto in (None, ""):
        quando = datetime.now().isoformat(timespec="seconds")
    else:
        quando = quando_valido(quando_bruto)
        if quando is None:
            return jsonify({"error": "quando precisa ser ISO 8601 valido"}), 400

    conn = db.get_db()
    try:
        sinal_id = gravar(conn, tipo, lugar, quando)
        try:
            reagir(conn, tipo, lugar, quando)
        except Exception:
            pass  # reacao e extra - nunca derruba a gravacao do sinal, que ja foi commitada
        try:  # se-entao (Lab v4): acordei / cheguei em casa disparam os combinados "quando X, eu Y"
            import se_entao

            if tipo == "acordei":
                se_entao.disparar(conn, "acordar")
            elif tipo == "cheguei" and (lugar or "").strip().lower() == "casa":
                se_entao.disparar(conn, "chegar_casa")
        except Exception:
            pass
    finally:
        conn.close()
    return jsonify({"ok": True, "id": sinal_id}), 201
