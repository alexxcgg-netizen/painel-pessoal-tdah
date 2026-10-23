"""Blueprint de_onde_parei - botoes do card `de_onde_parei` (leva 22/10). Logica em de_onde_parei.py; o
gatilho (voltou depois de 2 h) roda no batimento /api/push/visto."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import get_db
import de_onde_parei

bp = Blueprint("de_onde_parei", __name__)


def _id_valido(v):
    return isinstance(v, int) and not isinstance(v, bool) and v > 0


@bp.route("/api/de-onde-parei/deixar", methods=["POST"])
def deixar():
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    tid = app._corpo_json().get("task_id")
    if not _id_valido(tid):
        return jsonify({"error": "task_id inválido"}), 400
    conn = get_db()
    try:
        de_onde_parei.deixar(conn, tid, app._agora_brasilia().date().isoformat())
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.route("/api/subtasks/<int:subtask_id>/marcar", methods=["POST"])
def marcar_passo(subtask_id):
    """Caixinha do card: marca (feito: true) ou desmarca (false) - a rota /complete antiga so marcava."""
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    feito = app._corpo_json().get("feito")
    if not isinstance(feito, bool):
        return jsonify({"error": "feito tem que ser true ou false"}), 400
    conn = get_db()
    try:
        r = de_onde_parei.marcar_passo(conn, subtask_id, feito)
        if r is not None:
            app._marcar_atividade(conn)
            conn.commit()
    finally:
        conn.close()
    if r is None:
        return jsonify({"error": "passo não encontrado"}), 404
    return jsonify({"ok": True, **r})
