"""Blueprint push - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import delete_push_subscription, get_db, list_push_subscriptions, save_push_subscription
import json
from datetime import datetime, timezone
import push_client

bp = Blueprint("push", __name__)

@bp.route("/api/push/status", methods=["GET"])
def push_status():
    import db

    conn = get_db()
    try:
        teste = db.obter_configuracao(conn, CHAVE_TESTE_BOTOES)
    finally:
        conn.close()
    try:
        teste = json.loads(teste) if teste else None
    except ValueError:
        teste = None
    return jsonify({
        "configurado": push_client.configurado(),
        "public_key": push_client.public_key(),
        "agendador": app_modulo().estado_agendador(),
        "teste_botoes": teste,
    })


# Leva 22/10: botoes "Feito" / "Adiar 1 h" no aviso de uma tarefa. O aviso de teste tambem vem com
# eles - o que ele tocou fica guardado aqui e a tela diz se o iPhone mostrou os botoes.
CHAVE_TESTE_BOTOES = "push_teste_botoes"
TAG_TESTE = "teste-0"


def _adiar_uma_hora(conn, tarefa: dict, agora) -> dict:
    """Hora + 1 h no mesmo dia; sem hora, ou passando da meia-noite, vai pra amanha (mesma hora)."""
    from datetime import date, datetime, timedelta

    agora = agora.replace(tzinfo=None)
    hora = tarefa["hora"] or ""
    hoje = agora.date()
    try:
        base = datetime.combine(date.fromisoformat(tarefa["due_date"] or hoje.isoformat()), datetime.strptime(hora, "%H:%M").time())
        if base < agora:  # aviso de tarefa ja atrasada: adia a partir de agora
            base = agora.replace(second=0, microsecond=0)
        nova = base + timedelta(hours=1)
        if nova.date() == base.date():
            dados = {"due_date": nova.date().isoformat(), "hora": nova.strftime("%H:%M")}
        else:
            dados = {"due_date": (base.date() + timedelta(days=1)).isoformat(), "hora": hora}
    except ValueError:
        dados = {"due_date": (hoje + timedelta(days=1)).isoformat(), "hora": tarefa["hora"]}
    conn.execute("UPDATE tasks SET due_date = ?, hora = ? WHERE id = ?", (dados["due_date"], dados["hora"], tarefa["id"]))
    if dados["due_date"] != (tarefa["due_date"] or hoje.isoformat()):
        import dia_ruim

        dia_ruim.registrar_adiamento(conn, [tarefa["id"]], tarefa["due_date"], dados["due_date"])
    conn.commit()
    return dados


@bp.route("/api/push/acao", methods=["POST"])
def push_acao():
    """Botao tocado no proprio aviso (service worker): "feito" conclui a tarefa, "adiar" empurra 1 h.
    `tag` = "<tipo>-<id da tarefa>", a mesma do envio; o aviso para de insistir. Teste (tag "teste-0")
    so guarda o que foi tocado - "toque" = tocou no aviso, nao num botao."""
    import db

    app = app_modulo()
    corpo = app._corpo_json()
    tag, acao = corpo.get("tag"), corpo.get("acao")
    if not isinstance(tag, str) or not tag.strip() or len(tag) > 120 or acao not in ("feito", "adiar", "toque"):
        return jsonify({"error": "pedido inválido"}), 400
    tag = tag.strip()
    conn = get_db()
    try:
        if tag == TAG_TESTE:
            db.definir_configuracao(conn, CHAVE_TESTE_BOTOES, json.dumps(
                {"acao": acao, "em": app._agora_brasilia().isoformat(timespec="minutes")}))
            conn.commit()
            return jsonify({"ok": True, "teste": True})
        recusa = app._recusar_no_modo_visitante()
        if recusa:
            return recusa
        tipo, _, ref = tag.rpartition("-")
        if acao == "toque" or tipo not in app._AVISOS_DE_UMA_TAREFA or not ref.isdigit():
            return jsonify({"error": "esse aviso não tem botão"}), 400
        tarefa = conn.execute("SELECT id, title, due_date, hora, completed_at FROM tasks WHERE id = ?", (int(ref),)).fetchone()
        if not tarefa:
            return jsonify({"error": "tarefa não encontrada"}), 404
        db.marcar_aviso_aberto(conn, tag)
        if tarefa["completed_at"]:
            return jsonify({"ok": True, "titulo": tarefa["title"], "ja_feita": True})
        if acao == "feito":
            db.complete_task(conn, tarefa["id"])
            app._marcar_atividade(conn)
            conn.commit()
            return jsonify({"ok": True, "titulo": tarefa["title"]})
        dados = _adiar_uma_hora(conn, dict(tarefa), app._agora_brasilia())
        return jsonify({"ok": True, "titulo": tarefa["title"], **dados})
    finally:
        conn.close()

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

    import de_onde_parei

    app = app_modulo()
    conn = get_db()
    try:
        n = db.marcar_avisos_vistos(conn)
        # de onde parei (leva 22/10): voltou depois de 2 h com tarefa pela metade -> card no chat
        parei = False
        if not app._modo_visitante_ativo():
            try:
                agora = app._agora_brasilia()
                parei = de_onde_parei.ao_ver(conn, datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0), agora.date().isoformat())
            except Exception:
                app.app.logger.exception("de onde parei falhou")
    finally:
        conn.close()
    return jsonify({"ok": True, "parou": n, "de_onde_parei": parei})


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
            "Teste com botões: segura o aviso (ou puxa pra baixo) e toca em Feito ou Adiar.",
            url="/?aba=tarefas",
            tag=TAG_TESTE,
            acoes=[{"action": "feito", "title": "Feito"}, {"action": "adiar", "title": "Adiar 1 h"}],
        )
        if ok:
            enviados += 1
        else:
            delete_push_subscription(conn, s["endpoint"])
    conn.close()
    return jsonify({"enviados": enviados, "total": len(subscriptions)})
