"""Blueprint esperas - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import apagar_espera, create_espera, get_db, list_esperas_pendentes, marcar_espera_importante, resolver_espera
import vida

bp = Blueprint("esperas", __name__)

@bp.route("/api/esperas", methods=["GET"])
def esperas():
    conn = get_db()
    resultado = list_esperas_pendentes(conn)
    conn.close()
    return jsonify(resultado)

@bp.route("/api/esperas", methods=["POST"])
def criar_espera():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _marcar_atividade = app._marcar_atividade
    _texto_seguro = app._texto_seguro
    body = _corpo_json()
    quem = _texto_seguro(body.get("quem"))
    sobre = _texto_seguro(body.get("sobre"))
    if not quem or not sobre:
        return jsonify({"error": "informe quem e sobre o que"}), 400

    conn = get_db()
    espera_id = create_espera(conn, quem, sobre)
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"id": espera_id, "ok": True}), 201

@bp.route("/api/esperas/<int:espera_id>/resolver", methods=["POST"])
def resolver_espera_rota(espera_id):
    conn = get_db()
    ok = resolver_espera(conn, espera_id)
    conn.close()
    if not ok:
        return jsonify({"error": "espera não encontrada ou já resolvida"}), 404
    return jsonify({"ok": True})

@bp.route("/api/esperas/<int:espera_id>", methods=["DELETE"])
def apagar_espera_rota(espera_id):
    conn = get_db()
    apagar_espera(conn, espera_id)
    conn.close()
    return jsonify({"ok": True})

@bp.route("/api/esperas/<int:espera_id>/importante", methods=["POST"])
def marcar_espera_importante_rota(espera_id):
    """Fase 5 (US-C5): marca/desmarca uma espera pendente como importante -
    entra no calculo de prioridade de quem responder primeiro (ver
    /api/esperas/prioridade e vida.priorizar_esperas)."""
    app = app_modulo()
    _corpo_json = app._corpo_json
    body = _corpo_json()
    importante = bool(body.get("importante", True))
    conn = get_db()
    ok = marcar_espera_importante(conn, espera_id, importante)
    conn.close()
    if not ok:
        return jsonify({"error": "espera não encontrada"}), 404
    return jsonify({"ok": True, "importante": importante})

@bp.route("/api/esperas/prioridade", methods=["GET"])
def esperas_priorizadas():
    """Fase 5 (US-C5): quem responder primeiro entre as esperas pendentes -
    reaproveita a mesma tabela/logica de list_esperas_pendentes (TODO #76),
    so ordena por vida.priorizar_esperas (tempo parado + importancia) em vez
    da ordem de criacao que /api/esperas devolve."""
    app = app_modulo()
    date = app.date
    conn = get_db()
    esperas = list_esperas_pendentes(conn)
    conn.close()
    return jsonify(vida.priorizar_esperas(esperas, date.today()))
