"""rotas/p1a_caixa.py — Faixa P1a (Fase 7): rotas HTTP da Caixa do
assistente (GET/POST protegidas por sessao, igual ao resto do app) e o tick
periodico (POST /api/tick, protegido por token - ver docs/tick.md).

O Blueprint `bp` e registrado sozinho pelo autoloader de rotas/ (Etapa 0/X1,
ver docs/agentes/fase7-regras-faixa.md - "Rota nova: crie rotas/<faixa>.py
com um Blueprint bp, que e registrado sozinho"). `ROTAS_COM_TOKEN` e o que
libera /api/tick da checagem normal de sessao/PIN que roda em todo /api/*
(app.py, `_verificar_autenticacao`) - a checagem de verdade de quem pode
chamar o tick e feita aqui dentro, por token, nao por sessao (quem chama e
um cron externo, que nao guarda cookie)."""

from __future__ import annotations

import hmac
import os
from datetime import datetime

from flask import Blueprint, jsonify, request

import db
from assistente import caixa
from assistente.gatilhos import executar_todos

bp = Blueprint("p1a_caixa", __name__)

# Consultado pelo autoloader de rotas (Etapa 0/X1) pra saber quais caminhos
# NAO exigem sessao/PIN - a rota mesmo assim tem que checar o proprio token.
ROTAS_COM_TOKEN = {"/api/tick"}

MINUTOS_TICK_ATRASADO = 15


def _token_valido() -> bool:
    """Sem PAINEL_TICK_TOKEN configurado, a rota fica sempre fechada (ao
    contrario do padrao de PAINEL_ATALHOS_TOKEN em app.py, que cai pra
    sessao quando nao configurado) - o tick nunca chega com sessao de
    login, so por cron externo, entao "sem token = aberta" seria deixar
    /api/tick publica sem querer."""
    token_esperado = os.environ.get("PAINEL_TICK_TOKEN")
    if not token_esperado:
        return False
    cabecalho = request.headers.get("Authorization") or ""
    if not cabecalho.startswith("Bearer "):
        return False
    enviado = cabecalho[len("Bearer "):]
    return hmac.compare_digest(enviado.encode(), token_esperado.encode())


@bp.route("/api/assistente/caixa", methods=["GET"])
def listar_caixa():
    """Lista da Caixa (tela Assistente + faixa compacta em Hoje) mais a
    contagem pro selo. ?estado= filtra por outro estado (historico); sem
    parametro, so os itens pendentes (o padrao de assistente.caixa.listar)."""
    estado = request.args.get("estado") or None
    limite_bruto = request.args.get("limite")
    try:
        limite = int(limite_bruto) if limite_bruto else 200
    except ValueError:
        limite = 200

    conn = db.get_db()
    try:
        try:
            itens = caixa.listar(conn, estado=estado, limite=limite)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        pendentes = caixa.contar_pendentes(conn)
    finally:
        conn.close()
    return jsonify({"itens": itens, "pendentes": pendentes})


@bp.route("/api/assistente/caixa/<item_id>/responder", methods=["POST"])
def responder_caixa(item_id):
    """Body: {"resposta": "sim"|"nao"|"adiar"|"aceitar"|"recusar"|<opcao
    propria do item>, "texto": opcional}."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):  # C1: lista/texto no corpo nao vira 500
        body = {}
    resposta = body.get("resposta")
    resposta = resposta.strip() if isinstance(resposta, str) else ""
    texto = body.get("texto")
    texto = texto[:4000] if isinstance(texto, str) else ""
    if not resposta:
        return jsonify({"error": "resposta obrigatoria"}), 400
    try:
        caixa.resolver(item_id, resposta, texto)
    except ValueError as exc:
        mensagem = str(exc)
        status = 404 if "não encontrado" in mensagem else 400
        return jsonify({"error": mensagem}), status
    return jsonify({"ok": True})


@bp.route("/api/tick", methods=["POST"])
def tick():
    """Chamado a cada poucos minutos por um cron externo (docs/tick.md).
    Roda todo gatilho do assistente (assistente.gatilhos.executar_todos -
    Etapa 0/X1; ela mesma isola a excecao de CADA gatilho, entao um gatilho
    com bug nunca derruba os outros nem o resto do tick), depois repeticao
    e expiracao da Caixa, e registra o horario pra /api/assistente/saude.
    Idempotente por construcao: rodar 2x no mesmo minuto nao duplica item
    (chave_unica) nem manda push a mais (processar_repeticoes respeita
    pushes_hoje)."""
    if not _token_valido():
        return jsonify({"error": "token inválido"}), 401

    agora = datetime.now()
    conn = db.get_db()
    try:
        try:
            gatilhos_resultado = executar_todos(conn, agora)
        except Exception as exc:  # nunca deixa um bug do proprio agregador derrubar o tick
            gatilhos_resultado = {"erro": str(exc)}

        repeticoes = caixa.processar_repeticoes(conn, agora)
        expirados = caixa.expirar(conn, agora)
        db.definir_configuracao(conn, caixa.CHAVE_ULTIMO_TICK, agora.strftime("%Y-%m-%d %H:%M:%S"))
    finally:
        conn.close()

    return jsonify(
        {
            "ok": True,
            "gatilhos": gatilhos_resultado,
            "reativados": repeticoes["reativados"],
            "pushes_enviados": repeticoes["pushes_enviados"],
            "expirados": expirados,
        }
    )


@bp.route("/api/assistente/saude", methods=["GET"])
def saude():
    """A UI mostra um aviso quando o tick esta atrasado (Render grátis
    dorme sem cron externo batendo - ver docs/tick.md)."""
    conn = db.get_db()
    try:
        ultimo = db.obter_configuracao(conn, caixa.CHAVE_ULTIMO_TICK)
    finally:
        conn.close()

    if not ultimo:
        return jsonify({"ultimo_tick_em": None, "minutos_desde_ultimo_tick": None, "atrasado": True})

    try:
        momento = datetime.strptime(ultimo, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return jsonify({"ultimo_tick_em": ultimo, "minutos_desde_ultimo_tick": None, "atrasado": True})

    minutos = (datetime.now() - momento).total_seconds() / 60
    return jsonify(
        {
            "ultimo_tick_em": ultimo,
            "minutos_desde_ultimo_tick": round(minutos, 1),
            "atrasado": minutos > MINUTOS_TICK_ATRASADO,
        }
    )
