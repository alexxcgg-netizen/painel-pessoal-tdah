"""Viagem planejada (leva "painel mais esperto", 2026-11-06): o chip de outra saida no card `viagem` diz pro
servidor qual horario vale (o GPS/ao vivo do iPhone le pelo viagem_planejada.plano_ativo), e "encerrar" fecha
a viagem. Nenhuma chamada ao Google aqui - o plano ja esta gravado."""

from __future__ import annotations

from flask import Blueprint, jsonify

import db
import viagem_planejada
from rotas._base import app_modulo

bp = Blueprint("viagem_planejada", __name__)


@bp.route("/api/viagens-planejadas/<int:viagem_id>/saida", methods=["POST"])
def escolher_saida(viagem_id: int):
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    corpo = app._corpo_json()
    indice = corpo.get("indice")
    if isinstance(indice, bool) or not isinstance(indice, int):
        return jsonify({"ok": False, "error": "indice invalido"}), 400
    conn = db.get_db()
    try:
        r = viagem_planejada.escolher_saida(conn, viagem_id, indice)
    finally:
        conn.close()
    if not r:
        return jsonify({"ok": False, "error": "viagem ou saida nao encontrada"}), 404
    return jsonify({"ok": True, **r})


@bp.route("/api/viagens-planejadas/<int:viagem_id>/encerrar", methods=["POST"])
def encerrar(viagem_id: int):
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    conn = db.get_db()
    try:
        ok = viagem_planejada.encerrar(conn, viagem_id)
    finally:
        conn.close()
    return jsonify({"ok": ok}), (200 if ok else 404)
