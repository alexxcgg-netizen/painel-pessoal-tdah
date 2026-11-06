"""rotas/esperto.py - botoes dos cards da frente 7 da leva 06/11 "painel mais esperto"
(docs/briefings/2026-11-06-painel-esperto.md). Regra em voo_vespera.py e rotinas_esperto.py.

- `POST /api/esperto/rotina`                    {chave, resposta: "sim"|"nao"} -> cria a rotina (com Desfazer) ou
  "nao pergunto mais";
- `POST /api/esperto/tarefa/<id>/mudar-dia`     -> dia menos corrido sem chuva dos proximos 7 (com Desfazer);
- `POST /api/esperto/voo/<id>/remarcar`         {hora: "HH:MM"} -> muda a hora do voo (com Desfazer).
Todas atras do PIN de sempre e recusadas no modo visitante.
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

import db
from rotas._base import app_modulo

log = logging.getLogger(__name__)

bp = Blueprint("esperto", __name__)


def _corpo() -> dict:
    corpo = request.get_json(silent=True)
    return corpo if isinstance(corpo, dict) else {}


@bp.route("/api/esperto/rotina", methods=["POST"])
def esperto_rotina():
    import rotinas_esperto

    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    corpo = _corpo()
    chave, resposta = corpo.get("chave"), corpo.get("resposta")
    if not isinstance(chave, str) or not chave or len(chave) > 200 or resposta not in ("sim", "nao"):
        return jsonify({"error": "pedido inválido"}), 400
    conn = db.get_db()
    try:
        r = rotinas_esperto.responder_rotina(conn, chave, resposta, app._agora_brasilia())
    except Exception:
        log.exception("esperto: rotina falhou")
        return jsonify({"error": "não consegui agora, tenta de novo"}), 500
    finally:
        conn.close()
    if not r:
        return jsonify({"error": "essa proposta já foi respondida"}), 409
    return jsonify(r)


@bp.route("/api/esperto/tarefa/<int:task_id>/mudar-dia", methods=["POST"])
def esperto_mudar_dia(task_id):
    import rotinas_esperto

    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    conn = db.get_db()
    try:
        r = rotinas_esperto.mudar_dia(conn, task_id, app._agora_brasilia())
    except Exception:
        log.exception("esperto: mudar dia falhou")
        return jsonify({"error": "não consegui agora, tenta de novo"}), 500
    finally:
        conn.close()
    if not r:
        return jsonify({"error": "tarefa não encontrada"}), 404
    return jsonify(r)


@bp.route("/api/esperto/voo/<int:voo_id>/remarcar", methods=["POST"])
def esperto_remarcar_voo(voo_id):
    import voo_vespera

    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    hora = _corpo().get("hora")
    if not isinstance(hora, str) or len(hora) != 5:
        return jsonify({"error": "hora inválida"}), 400
    conn = db.get_db()
    try:
        r = voo_vespera.remarcar(conn, voo_id, hora)
    except Exception:
        log.exception("esperto: remarcar voo falhou")
        return jsonify({"error": "não consegui agora, tenta de novo"}), 500
    finally:
        conn.close()
    if not r:
        return jsonify({"error": "voo não encontrado"}), 404
    return jsonify({**r, "texto": f"Remarquei pras {r['hora']}."})
