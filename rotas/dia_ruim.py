"""Blueprint dia_ruim - botao "dia ruim", cadeado (inegociavel) e o alerta da manha (leva 22/10).
Logica em dia_ruim.py; aqui so a casca HTTP dos botoes dos cards `dia_ruim` / `alerta_dia` e do Inicio."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from rotas._base import app_modulo
from db import get_db
import dia_ruim

bp = Blueprint("dia_ruim", __name__)

FRASES_DIA_RUIM = (
    "Entendi. Deixei só o essencial pra hoje.",
    "Tudo bem. Aliviei teu dia: ficou só o que importa.",
)


def _hoje():
    return app_modulo()._agora_brasilia().date()


@bp.route("/api/dia-ruim", methods=["POST"])
def aliviar_dia():
    """Botao do Inicio e "Aliviar o resto" do alerta: alivia e deixa o card no chat."""
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    import conversa_proativa

    hoje = _hoje()
    conn = get_db()
    try:
        estado = dia_ruim.aliviar(conn, hoje)
        texto = FRASES_DIA_RUIM[hoje.toordinal() % len(FRASES_DIA_RUIM)]
        corpo = request.get_json(silent=True)
        if not (isinstance(corpo, dict) and corpo.get("no_chat") is False):
            conversa_proativa.publicar(conn, "dia_ruim_chat", texto, [dia_ruim.card_dia_ruim(conn, hoje)])
        return jsonify({"ok": True, **estado})
    finally:
        conn.close()


@bp.route("/api/dia-ruim/trazer", methods=["POST"])
def trazer_de_volta():
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    tid = app._corpo_json().get("id")
    if not isinstance(tid, int) or isinstance(tid, bool):
        return jsonify({"error": "id inválido"}), 400
    conn = get_db()
    try:
        estado = dia_ruim.trazer_de_volta(conn, tid, _hoje())
    finally:
        conn.close()
    if estado is None:
        return jsonify({"error": "essa tarefa não foi aliviada hoje"}), 404
    return jsonify({"ok": True, **estado})


@bp.route("/api/dia-ruim/empurrar", methods=["POST"])
def empurrar():
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    tid = app._corpo_json().get("id")
    if not isinstance(tid, int) or isinstance(tid, bool):
        return jsonify({"error": "id inválido"}), 400
    conn = get_db()
    try:
        estado = dia_ruim.empurrar(conn, tid, _hoje())
    finally:
        conn.close()
    if estado is None:
        return jsonify({"error": "não dá pra empurrar essa"}), 404
    return jsonify({"ok": True, **estado})


@bp.route("/api/dia-ruim/desfazer", methods=["POST"])
def desfazer_dia_ruim():
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    conn = get_db()
    try:
        return jsonify({"ok": True, **dia_ruim.desfazer(conn, _hoje())})
    finally:
        conn.close()


@bp.route("/api/tasks/<int:task_id>/inegociavel", methods=["POST"])
def travar_tarefa(task_id):
    """O cadeado: trava (true) ou destrava (false)."""
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    valor = app._corpo_json().get("valor")
    if not isinstance(valor, bool):
        return jsonify({"error": "valor tem que ser true ou false"}), 400
    conn = get_db()
    try:
        r = dia_ruim.travar(conn, task_id, valor)
    finally:
        conn.close()
    if r is None:
        return jsonify({"error": "tarefa não encontrada"}), 404
    return jsonify({"ok": True, **r})
