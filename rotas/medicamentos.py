"""Blueprint medicamentos - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import (
    complete_task,
    delete_medicamento,
    get_db,
    get_medicamento_ativo,
    instancia_do_dia_do_medicamento,
    list_medicamentos_ativos,
    reabrir_tarefa,
    utc_para_hora_local,
)

bp = Blueprint("medicamentos", __name__)

@bp.route("/api/medicamentos", methods=["GET"])
def medicamentos():
    app = app_modulo()
    visitante = app._modo_visitante_ativo()
    conn = get_db()
    resultado = list_medicamentos_ativos(conn)
    if not visitante and resultado:
        # R4 ("Tomei"): a dose de hoje e a instancia de hoje da tarefa recorrente do remedio.
        app.materializar_tarefas_recorrentes(conn)
    hoje = app.date.today().isoformat()
    for m in resultado:
        inst = None if visitante else instancia_do_dia_do_medicamento(conn, m, hoje)
        m["devido_hoje"] = inst is not None
        m["tomado_hoje"] = bool(inst and inst["completed_at"])
        m["tomado_as"] = utc_para_hora_local(inst["completed_at"]) if inst else None
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


@bp.route("/api/medicamentos/<int:medicamento_id>/tomar", methods=["POST"])
def tomar_medicamento(medicamento_id):
    """R4: "Tomei" - conclui a instancia de HOJE da tarefa do remedio (idempotente:
    repetir devolve a hora da primeira vez, sem duplicar nem reescrever)."""
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    conn = get_db()
    try:
        med = get_medicamento_ativo(conn, medicamento_id)
        if not med:
            return jsonify({"error": "remédio não encontrado"}), 404
        app.materializar_tarefas_recorrentes(conn)
        inst = instancia_do_dia_do_medicamento(conn, med, app.date.today().isoformat())
        if not inst:
            return jsonify({"error": "esse remédio não cai hoje"}), 409
        criou = not inst["completed_at"]
        if criou:
            complete_task(conn, inst["id"])
            app._marcar_atividade(conn)
            conn.commit()
            inst = instancia_do_dia_do_medicamento(conn, med, app.date.today().isoformat())
    finally:
        conn.close()
    return jsonify({"ok": True, "tomado": True, "hora": utc_para_hora_local(inst["completed_at"])}), (
        201 if criou else 200
    )


@bp.route("/api/medicamentos/<int:medicamento_id>/tomar", methods=["DELETE"])
def desfazer_tomada_medicamento(medicamento_id):
    """R4: desfaz o "Tomei" de hoje (reabre a instancia; idempotente)."""
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    conn = get_db()
    try:
        med = get_medicamento_ativo(conn, medicamento_id)
        if not med:
            return jsonify({"error": "remédio não encontrado"}), 404
        inst = instancia_do_dia_do_medicamento(conn, med, app.date.today().isoformat())
        if inst and inst["completed_at"]:
            reabrir_tarefa(conn, inst["id"])
    finally:
        conn.close()
    return jsonify({"ok": True, "tomado": False})
