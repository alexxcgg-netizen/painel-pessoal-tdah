"""rotas/avisos_app.py - avisos que o app nativo do iPhone agenda (leva 06/11/2026,
docs/briefings/2026-11-06-avisos-app.md). Conta e regra em `avisos_app.py` (raiz).

Rotas de maquina (sem PIN), token do widget so no header `Authorization: Bearer` (igual /api/ao-vivo):
- `GET  /api/app/avisos`            -> {"avisos": [...], "gerado_em": ts} o que o app agenda;
- `POST /api/app/avisos/agendados`  -> o app conta o que ficou agendado (o navegador nao repete esses);
- `POST /api/app/aviso/acao`        -> Feito / Adiar 1 h / toque no aviso local (mesma logica do
  /api/push/acao e /api/push/aberto).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify, request

import avisos_app
import db
from rotas._base import app_modulo

bp = Blueprint("avisos_app", __name__)

ROTAS_COM_TOKEN = {"/api/app/avisos", "/api/app/avisos/agendados", "/api/app/aviso/acao"}

FOCO_SEM_FIM_MIN = 90  # modo foco (relogio correndo) nao tem hora de fim: segura os proximos 90 min


def _token_ok() -> bool:
    from rotas.ao_vivo import _token_valido

    return _token_valido()


def _corpo() -> dict:
    corpo = request.get_json(silent=True)
    return corpo if isinstance(corpo, dict) else {}


def _segurar_ate(app, conn, agora: datetime) -> datetime | None:
    """Ate quando o hiperfoco / modo foco segura aviso nao critico (o servidor faz o mesmo no tick)."""
    import foco
    import vida

    ate = db.obter_configuracao(conn, "hiperfoco_ate")
    fim = None
    if vida.hiperfoco_ativo(ate, agora):
        fim = datetime.fromisoformat(ate)
    try:
        if foco.segurando_avisos(conn, agora):
            fim = max(fim or agora, agora + timedelta(minutes=FOCO_SEM_FIM_MIN))
    except Exception:  # noqa: BLE001
        pass
    return fim


@bp.route("/api/app/avisos", methods=["GET"])
def app_avisos():
    if not _token_ok():
        return jsonify({"error": "token invalido"}), 401
    app = app_modulo()
    import vida

    conn = db.get_db()
    try:
        agora = datetime.now()
        itens = avisos_app.montar(
            conn, agora,
            minutos_arrumar=app._minutos_se_arrumar(conn),
            trajeto_min=lambda local: app._trajeto_min_aviso(app.vida_assistente.resolver_lugar(conn, local)),
            trajeto_parada=lambda parada, local: app._trajetos_parada_aviso(conn, parada, local),
            clima=app._clima_aviso,
            saida_voo=lambda voo: app._saida_do_voo(voo, conn=conn),
            ligado=lambda tipo: app.avisos_assistente.esta_ligado(tipo, conn=conn),
            ja_notificou=lambda tipo, ref: app.ja_notificou_hoje(conn, tipo, ref),
            segurar_ate=_segurar_ate(app, conn, agora),
            criticos=frozenset(vida.CRITICOS_HIPERFOCO),
            url_do_aviso=app._url_do_aviso,
            de_uma_tarefa=frozenset(app._AVISOS_DE_UMA_TAREFA),
            agendados=avisos_app.carregar_agendados(conn, agora),
        )
        return jsonify({"avisos": itens, "gerado_em": int(agora.timestamp())})
    except Exception:
        current_app.logger.exception("avisos do app: falhou ao montar")
        return jsonify({"error": "falhou ao montar"}), 500
    finally:
        conn.close()


@bp.route("/api/app/avisos/agendados", methods=["POST"])
def app_avisos_agendados():
    if not _token_ok():
        return jsonify({"error": "token invalido"}), 401
    itens = _corpo().get("itens")
    if not isinstance(itens, list):
        return jsonify({"error": "itens precisa ser uma lista"}), 400
    conn = db.get_db()
    try:
        n = avisos_app.gravar_agendados(conn, itens, datetime.now())
    finally:
        conn.close()
    return jsonify({"ok": True, "guardados": n})


@bp.route("/api/app/aviso/acao", methods=["POST"])
def app_aviso_acao():
    """{"tag": "tarefa_horario-12", "acao": "feito" | "adiar" | "toque"}."""
    if not _token_ok():
        return jsonify({"error": "token invalido"}), 401
    from rotas.push import executar_acao, registrar_toque

    corpo = _corpo()
    tag = corpo.get("tag")
    if isinstance(tag, str) and tag.startswith("tarefa_agora-") and tag[len("tarefa_agora-"):].isdigit():
        # o "e agora" e do app; mexer nele (toque, Feito, Adiar) para a insistencia do aviso de tarefa
        # que o servidor ainda repete pelo navegador
        conn = db.get_db()
        try:
            db.marcar_aviso_aberto(conn, "tarefa_horario-" + tag[len("tarefa_agora-"):])
        finally:
            conn.close()
    if corpo.get("acao") == "toque":
        return registrar_toque(tag)
    acao = corpo.get("acao")
    if acao == "amanha" and isinstance(tag, str) and tag.startswith("casa_tarefa-"):
        acao = "adiar"  # botao "Amanha" do aviso "Chegou em casa" (categoria "casa"): hora_certa.acao_casa
    return executar_acao(tag, acao)
