"""Rotas da faixa P8 (Fase 7): central de avisos do assistente. Sessao (PIN
normal, sem token) - a autenticacao e GLOBAL (`@app.before_request` em
app.py) quando este Blueprint for registrado por `rotas.registrar_todas`
(infra da Etapa 0, `e0-backend`; ver `rotas/__init__.py` quando integrada).

Ate essa infra chegar em `fase7/integracao` (nao chegou ainda quando esta
faixa foi feita - conferido com `git log origin/fase7/integracao`), este
modulo nao depende de nada de `rotas/_base.py` (que ainda nao existe aqui):
usa so `db.get_db()` e o corpo JSON puro do Flask, pra funcionar sozinho
tanto registrado manualmente num app de teste (`tests/test_fase7_p8_rotas.py`)
quanto, sem nenhuma mudanca neste arquivo, quando `registrar_todas` passar a
importa-lo de verdade.

- GET  /api/assistente/avisos            -> catalogo inteiro com estado atual
- PUT  /api/assistente/avisos/<tipo>      -> muda ligado/canal/silencio de UM tipo
- PUT  /api/assistente/avisos/silencio    -> muda o silencio GLOBAL (janela padrao)
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

import db
from assistente import avisos

bp = Blueprint("p8_avisos", __name__)


@bp.route("/api/assistente/avisos", methods=["GET"])
def listar_avisos():
    conn = db.get_db()
    try:
        return jsonify(
            {
                "tipos": avisos.listar_estado(conn=conn),
                "silencio": avisos.obter_silencio_global(conn=conn),
            }
        )
    finally:
        conn.close()


@bp.route("/api/assistente/avisos/silencio", methods=["PUT"])
def atualizar_silencio_global():
    corpo = request.get_json(silent=True)
    if not isinstance(corpo, dict):
        corpo = {}
    inicio = corpo.get("inicio")
    fim = corpo.get("fim")
    if not isinstance(inicio, str) or not isinstance(fim, str):
        return jsonify({"error": "informe inicio e fim, no formato HH:MM"}), 400
    conn = db.get_db()
    try:
        silencio = avisos.definir_silencio_global(inicio, fim, conn=conn)
    except ValueError as erro:
        return jsonify({"error": str(erro)}), 400
    finally:
        conn.close()
    return jsonify({"silencio": silencio})


@bp.route("/api/assistente/avisos/<tipo>", methods=["PUT"])
def atualizar_aviso(tipo: str):
    corpo = request.get_json(silent=True) or {}
    if not isinstance(corpo, dict):
        return jsonify({"error": "corpo invalido"}), 400

    campos: dict = {}
    if "ligado" in corpo:
        if not isinstance(corpo["ligado"], bool):
            return jsonify({"error": "ligado precisa ser true/false"}), 400
        campos["ligado"] = corpo["ligado"]
    if "canal" in corpo:
        campos["canal"] = corpo["canal"]
    if "silencio_inicio" in corpo:
        campos["silencio_inicio"] = corpo["silencio_inicio"]
    if "silencio_fim" in corpo:
        campos["silencio_fim"] = corpo["silencio_fim"]

    conn = db.get_db()
    try:
        estado = avisos.definir_tipo(tipo, conn=conn, **campos)
    except avisos.TipoDesconhecido:
        return jsonify({"error": f"tipo de aviso desconhecido: {tipo}"}), 404
    except ValueError as erro:
        return jsonify({"error": str(erro)}), 400
    finally:
        conn.close()
    return jsonify(estado)
