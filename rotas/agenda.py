"""Blueprint agenda - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import get_db, list_eventos_criados

bp = Blueprint("agenda", __name__)

@bp.route("/api/agenda/eventos", methods=["POST"])
def criar_evento_agenda_rota():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _criar_evento_agenda = app._criar_evento_agenda
    _recusar_no_modo_visitante = app._recusar_no_modo_visitante
    recusa = _recusar_no_modo_visitante()  # escreve no iCloud real do Alex
    if recusa:
        return recusa
    body = _corpo_json()
    conn = get_db()
    resultado = _criar_evento_agenda(
        conn, body.get("titulo"), body.get("data"), body.get("hora_inicio"), body.get("hora_fim"),
        body.get("lembrar_min_antes"),
    )
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201

@bp.route("/api/agenda/eventos/<uid>", methods=["DELETE"])
def apagar_evento_agenda_rota(uid):
    app = app_modulo()
    _apagar_evento_agenda = app._apagar_evento_agenda
    _recusar_no_modo_visitante = app._recusar_no_modo_visitante
    recusa = _recusar_no_modo_visitante()  # apaga no iCloud real do Alex
    if recusa:
        return recusa
    conn = get_db()
    resultado = _apagar_evento_agenda(conn, uid)
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado)

@bp.route("/api/agenda/eventos-criados", methods=["GET"])
def eventos_criados_rota():
    conn = get_db()
    resultado = list_eventos_criados(conn)
    conn.close()
    return jsonify(resultado)

@bp.route("/api/calendario/hoje", methods=["GET"])
def calendario_hoje():
    app = app_modulo()
    _compromissos_de_hoje = app._compromissos_de_hoje
    _tarefas_concluidas_com_horario_hoje = app._tarefas_concluidas_com_horario_hoje
    caldav_client = app.caldav_client
    date = app.date
    materializar_tarefas_recorrentes = app.materializar_tarefas_recorrentes
    conn = get_db()
    materializar_tarefas_recorrentes(conn)
    configurado = caldav_client.configurado()
    erro = None
    icloud_eventos = []
    if configurado:
        try:
            icloud_eventos = caldav_client.eventos_do_dia(date.today())
        except Exception:
            erro = "Nao consegui falar com o iCloud agora."
    eventos = _compromissos_de_hoje(conn, icloud_eventos)
    eventos += _tarefas_concluidas_com_horario_hoje(conn)
    eventos.sort(key=lambda e: e["inicio"])
    conn.close()
    resposta = {"configurado": configurado, "eventos": eventos}
    if erro:
        resposta["erro"] = erro
    return jsonify(resposta)
