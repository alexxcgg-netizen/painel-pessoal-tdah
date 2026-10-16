"""Blueprint push - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import delete_push_subscription, get_db, list_push_subscriptions, save_push_subscription
import json
import push_client

bp = Blueprint("push", __name__)

@bp.route("/api/push/status", methods=["GET"])
def push_status():
    return jsonify({
        "configurado": push_client.configurado(),
        "public_key": push_client.public_key(),
        "agendador": app_modulo().estado_agendador(),
    })

@bp.route("/api/push/inscrever", methods=["POST"])
def push_inscrever():
    app = app_modulo()
    _corpo_json = app._corpo_json
    subscription = _corpo_json()
    endpoint = subscription.get("endpoint")
    if not endpoint:
        return jsonify({"error": "inscricao inválida"}), 400
    conn = get_db()
    save_push_subscription(conn, endpoint, json.dumps(subscription))
    conn.close()
    return jsonify({"ok": True})

@bp.route("/api/push/aberto", methods=["POST"])
def push_aberto():
    """Toque numa notificacao (service worker): aviso importante para de insistir
    (notificacoes.INSISTENCIA). Tag = "<tipo>-<ref_id>", a mesma do envio."""
    corpo = app_modulo()._corpo_json()
    tag = corpo.get("tag") if isinstance(corpo, dict) else None
    if not isinstance(tag, str) or not tag.strip() or len(tag) > 120:
        return jsonify({"error": "tag inválida"}), 400
    import db

    conn = get_db()
    try:
        n = db.marcar_aviso_aberto(conn, tag.strip())
    finally:
        conn.close()
    return jsonify({"ok": True, "parou": n})

@bp.route("/api/push/visto", methods=["POST"])
def push_visto():
    """O app esta aberto na tela (init.js): os avisos que insistem hoje deixam de insistir.
    Mesma ideia do toque na notificacao (/api/push/aberto), sem exigir o toque."""
    import db

    conn = get_db()
    try:
        n = db.marcar_avisos_vistos(conn)
    finally:
        conn.close()
    return jsonify({"ok": True, "parou": n})


@bp.route("/api/push/testar", methods=["POST"])
def push_testar():
    if not push_client.configurado():
        return jsonify({"error": "notificacao push não configurada - veja o README"}), 400

    conn = get_db()
    subscriptions = list_push_subscriptions(conn)
    enviados = 0
    for s in subscriptions:
        sub_dict = json.loads(s["subscription_json"])
        ok = push_client.enviar(
            sub_dict,
            "Painel Pessoal",
            "Teste ok - é assim que os avisos vão chegar. Toque pra abrir as tarefas.",
            url="/?aba=tarefas",
            tag="teste",
        )
        if ok:
            enviados += 1
        else:
            delete_push_subscription(conn, s["endpoint"])
    conn.close()
    return jsonify({"enviados": enviados, "total": len(subscriptions)})
