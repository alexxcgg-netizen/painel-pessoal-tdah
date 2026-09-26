"""Blueprint medicamentos - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import delete_medicamento, get_db, list_medicamentos_ativos

bp = Blueprint("medicamentos", __name__)

@bp.route("/api/medicamentos", methods=["GET"])
def medicamentos():
    conn = get_db()
    resultado = list_medicamentos_ativos(conn)
    conn.close()
    return jsonify(resultado)

@bp.route("/api/medicamentos", methods=["POST"])
def criar_medicamento_rota():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _criar_medicamento = app._criar_medicamento
    _marcar_atividade = app._marcar_atividade
    body = _corpo_json()
    nome = (body.get("nome") or "").strip()
    if not nome:
        return jsonify({"error": "informe o nome do remedio"}), 400
    dosagem = (body.get("dosagem") or "").strip() or None
    horario = (body.get("horario") or "").strip()
    recorrencia = (body.get("recorrencia") or "diaria").strip()

    conn = get_db()
    resultado = _criar_medicamento(conn, nome, dosagem, horario, recorrencia, None)
    if "erro" in resultado:
        conn.close()
        return jsonify({"error": resultado["erro"]}), 400
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify(resultado), 201

@bp.route("/api/medicamentos/<int:medicamento_id>", methods=["DELETE"])
def apagar_medicamento(medicamento_id):
    conn = get_db()
    delete_medicamento(conn, medicamento_id)
    conn.close()
    return jsonify({"ok": True})
