"""Blueprint tempo - Grupo B da leva do Laboratorio v4 (fita, espera, calibrador, disjuntor, porta).
Logica em tempo.py; os gatilhos (cards no chat, pushes) rodam no tick de conversa_proativa.verificar."""

from __future__ import annotations

from datetime import date, datetime

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import get_db
import tempo

bp = Blueprint("tempo", __name__)


def _int(v, minimo=1, maximo=10**9):
    return v if isinstance(v, int) and not isinstance(v, bool) and minimo <= v <= maximo else None


def _dia_ok(v):
    try:
        date.fromisoformat(str(v))
        return str(v)
    except ValueError:
        return None


@bp.route("/api/tempo/fita", methods=["GET"])
def fita():
    app = app_modulo()
    if app._modo_visitante_ativo():
        return jsonify({"fita": None})
    conn = get_db()
    try:
        return jsonify({"fita": tempo.fita(conn, datetime.now())})
    finally:
        conn.close()


@bp.route("/api/tempo/espera/chamar", methods=["POST"])
def espera_chamar():
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    c = app._corpo_json()
    ref, ligado = _int(c.get("ref"), 0), c.get("ligado")
    if c.get("kind") not in ("voo", "tarefa", "habito", "agenda") or ref is None or not isinstance(ligado, bool):
        return jsonify({"error": "mande kind, ref e ligado (true/false)"}), 400
    conn = get_db()
    try:
        tempo.definir_chamada(conn, c["kind"], ref, ligado)
    finally:
        conn.close()
    return jsonify({"ok": True, "ligado": ligado})


@bp.route("/api/tempo/calibrador", methods=["GET"])
def calibrador():
    app = app_modulo()
    if app._modo_visitante_ativo():
        return jsonify({"card": None})
    conn = get_db()
    try:
        card = tempo.card_calibrador(conn, datetime.now())
        return jsonify({"card": card["data"] if card else None, "fator": tempo.fator(conn)})
    finally:
        conn.close()


@bp.route("/api/tempo/calibrador/palpite", methods=["POST"])
def calibrador_palpite():
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    c = app._corpo_json()
    tid, minutos = _int(c.get("task_id")), _int(c.get("minutos"), 1, 600)
    if tid is None or minutos is None:
        return jsonify({"error": "mande task_id e minutos (1 a 600)"}), 400
    conn = get_db()
    try:
        if not tempo.guardar_palpite(conn, tid, minutos):
            return jsonify({"error": "tarefa não encontrada ou já concluída"}), 404
        f = tempo.fator(conn)
        return jsonify({"ok": True, "minutos": minutos, "reserva": tempo.reservar(minutos, f["fator"] if f else 1.0)})
    finally:
        conn.close()


@bp.route("/api/tempo/disjuntor", methods=["POST"])
def disjuntor():
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    acao = app._corpo_json().get("acao")
    conn = get_db()
    try:
        r = tempo.responder_disjuntor(conn, acao, datetime.now())
        if r.get("error"):
            return jsonify(r), 400
        app._marcar_atividade(conn)
        conn.commit()
        return jsonify({"ok": True, **r})
    finally:
        conn.close()


@bp.route("/api/tempo/porta", methods=["GET"])
def porta_estado():
    """Estado atual das listas (o card do historico sincroniza daqui)."""
    app = app_modulo()
    if app._modo_visitante_ativo():
        return jsonify({"card": None})
    from flask import request

    dia = _dia_ok(request.args.get("dia")) or date.today().isoformat()
    voo = _int(request.args.get("voo_id", type=int))
    conn = get_db()
    try:
        return jsonify({"card": tempo.card_porta(conn, request.args.get("lugar", ""), dia, voo_id=voo)["data"]})
    finally:
        conn.close()


@bp.route("/api/tempo/porta/marcar", methods=["POST"])
def porta_marcar():
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    c = app._corpo_json()
    dia, feito = _dia_ok(c.get("dia")), c.get("feito")
    if c.get("lugar") not in tempo.LUGARES or not isinstance(feito, bool) or not dia or not isinstance(c.get("i"), int):
        return jsonify({"error": "mande lugar, i, feito e dia"}), 400
    conn = get_db()
    try:
        m = tempo.marcar_item(conn, c["lugar"], c["i"], feito, dia, _int(c.get("voo_id")))
    finally:
        conn.close()
    if m is None:
        return jsonify({"error": "item inválido"}), 400
    return jsonify({"ok": True, "feitos": m})


@bp.route("/api/tempo/porta/item", methods=["POST"])
def porta_item():
    """Esqueci uma vez -> entra na lista pra sempre (acao 'add'); 'remover' tira um que ele mesmo pos."""
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    c = app._corpo_json()
    lugar, item = c.get("lugar"), c.get("item")
    if lugar not in tempo.LUGARES or not isinstance(item, str) or not item.strip():
        return jsonify({"error": "mande lugar e item"}), 400
    conn = get_db()
    try:
        ok = tempo.remover_item(conn, lugar, item) if c.get("acao") == "remover" else tempo.adicionar_item(conn, lugar, item)
        if not ok:
            return jsonify({"error": "não deu"}), 400
        dia = _dia_ok(c.get("dia")) or date.today().isoformat()
        return jsonify({"ok": True, "card": tempo.card_porta(conn, lugar, dia, voo_id=_int(c.get("voo_id")))["data"]})
    finally:
        conn.close()
