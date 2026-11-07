"""rotas/avisos_app.py - avisos que o app nativo do iPhone agenda (leva 06/11/2026,
docs/briefings/2026-11-06-avisos-app.md). Conta e regra em `avisos_app.py` (raiz).

Rotas de maquina (sem PIN), token do widget so no header `Authorization: Bearer` (igual /api/ao-vivo):
- `GET  /api/app/avisos`            -> {"avisos": [...], "gerado_em": ts} o que o app agenda;
- `POST /api/app/avisos/agendados`  -> o app conta o que ficou agendado (o navegador nao repete esses);
- `POST /api/app/aviso/acao`        -> Feito / Adiar 1 h / toque no aviso local (mesma logica do
  /api/push/acao e /api/push/aberto). 07/11: + "mais15" (soneca: o app avisa de novo em 15 min, aqui so para
  a insistencia), "amanha" (tarefa pra amanha, mesma hora) e "rota" (abriu o Waze = toque);
- `GET  /api/app/avisos/pendentes`  -> 07/11 (frente C): fila de avisos sem hora conhecida (avisos_pendentes.py)
  que o app mostra como aviso local; `POST /api/app/avisos/pendentes/entregues` conta o que ele pegou.
Toda rota daqui marca o contato do app (o "app vivo" das 36 h que segura o push do navegador).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify, request

import avisos_app
import db
from rotas._base import app_modulo

bp = Blueprint("avisos_app", __name__)

ROTAS_COM_TOKEN = {"/api/app/avisos", "/api/app/avisos/agendados", "/api/app/aviso/acao",
                   "/api/app/avisos/pendentes", "/api/app/avisos/pendentes/entregues"}
ACOES_APP = ("feito", "adiar", "toque", "amanha", "mais15", "rota")

FOCO_SEM_FIM_MIN = 90  # modo foco (relogio correndo) nao tem hora de fim: segura os proximos 90 min


def _token_ok() -> bool:
    from rotas.ao_vivo import _token_valido

    return _token_valido()


def _contato(conn, agora: datetime | None = None) -> None:
    """O app falou com o painel (avisos_pendentes.app_vivo). Nunca derruba a rota."""
    try:
        import avisos_pendentes

        avisos_pendentes.marcar_contato(conn, agora or datetime.now())
    except Exception:  # noqa: BLE001
        current_app.logger.exception("avisos do app: contato nao gravou")


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
        _contato(conn, agora)
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
        _contato(conn)
    finally:
        conn.close()
    return jsonify({"ok": True, "guardados": n})


@bp.route("/api/app/avisos/pendentes", methods=["GET"])
def app_avisos_pendentes():
    """Fila de avisos sem hora conhecida (atraso, insistencia, IA...). O app mostra como aviso local."""
    if not _token_ok():
        return jsonify({"error": "token invalido"}), 401
    import avisos_pendentes

    conn = db.get_db()
    try:
        agora = datetime.now()
        _contato(conn, agora)
        return jsonify({"avisos": avisos_pendentes.para_app(conn, agora), "gerado_em": int(agora.timestamp())})
    except Exception:
        current_app.logger.exception("avisos do app: fila falhou")
        return jsonify({"error": "falhou ao montar"}), 500
    finally:
        conn.close()


@bp.route("/api/app/avisos/pendentes/entregues", methods=["POST"])
def app_avisos_pendentes_entregues():
    """{"ids": [1, 2]}: o app mostrou/agendou estes; o navegador nao manda mais."""
    if not _token_ok():
        return jsonify({"error": "token invalido"}), 401
    ids = _corpo().get("ids")
    if not isinstance(ids, list):
        return jsonify({"error": "ids precisa ser uma lista"}), 400
    import avisos_pendentes

    conn = db.get_db()
    try:
        agora = datetime.now()
        _contato(conn, agora)
        n = avisos_pendentes.marcar_entregues(conn, ids, agora)
    finally:
        conn.close()
    return jsonify({"ok": True, "entregues": n})


def _pra_amanha(tag: str):
    """Botao "Amanha" num aviso de tarefa: mesma hora, dia seguinte (a partir de hoje)."""
    import badge

    app = app_modulo()
    tipo, _, ref = tag.rpartition("-")
    if tipo not in app._AVISOS_DE_UMA_TAREFA or not ref.isdigit():
        return jsonify({"error": "esse aviso não tem botão"}), 400
    conn = db.get_db()
    try:
        recusa = app._recusar_no_modo_visitante()
        if recusa:
            return recusa
        t = conn.execute("SELECT id, title, due_date, completed_at FROM tasks WHERE id = ?", (int(ref),)).fetchone()
        if not t:
            return jsonify({"error": "tarefa não encontrada"}), 404
        db.marcar_aviso_aberto(conn, tag)
        hoje = app._agora_brasilia().date()
        if t["completed_at"]:
            return jsonify({"ok": True, "titulo": t["title"], "ja_feita": True})
        amanha = (hoje + timedelta(days=1)).isoformat()
        conn.execute("UPDATE tasks SET due_date = ? WHERE id = ?", (amanha, t["id"]))
        try:
            import dia_ruim

            dia_ruim.registrar_adiamento(conn, [t["id"]], t["due_date"], amanha)
        except Exception:  # noqa: BLE001 - contar o adiamento e extra
            current_app.logger.exception("avisos do app: adiamento nao contou")
        conn.commit()
        return jsonify({"ok": True, "titulo": t["title"], "due_date": amanha, "mensagem": "Passei pra amanhã.",
                        "badge": badge.contagem(conn, hoje)})
    finally:
        conn.close()


def _soneca(tag: str):
    """"+15 min": o app avisa de novo sozinho; aqui o navegador para de insistir nesse aviso."""
    import avisos_pendentes

    conn = db.get_db()
    try:
        db.marcar_aviso_aberto(conn, tag)
        avisos_pendentes.cancelar(conn, tag, datetime.now())
    finally:
        conn.close()
    return jsonify({"ok": True, "soneca_min": 15})


@bp.route("/api/app/aviso/acao", methods=["POST"])
def app_aviso_acao():
    """{"tag": "tarefa_horario-12", "acao": "feito" | "adiar" | "toque"}."""
    if not _token_ok():
        return jsonify({"error": "token invalido"}), 401
    from rotas.push import executar_acao, registrar_toque

    corpo = _corpo()
    tag = corpo.get("tag")
    acao = corpo.get("acao")
    if not isinstance(tag, str) or not tag.strip() or len(tag) > 120 or acao not in ACOES_APP:
        return jsonify({"error": "pedido inválido"}), 400
    tag = tag.strip()
    conn = db.get_db()
    try:
        _contato(conn)
    finally:
        conn.close()
    if tag.startswith("tarefa_agora-") and tag[len("tarefa_agora-"):].isdigit():
        # o "e agora" e do app; mexer nele (toque, Feito, Adiar) para a insistencia do aviso de tarefa
        # que o servidor ainda repete pelo navegador
        conn = db.get_db()
        try:
            db.marcar_aviso_aberto(conn, "tarefa_horario-" + tag[len("tarefa_agora-"):])
        finally:
            conn.close()
    if acao in ("toque", "rota"):  # "Abrir rota" abre o Waze no iPhone; aqui conta como toque
        return registrar_toque(tag)
    if acao == "mais15":
        return _soneca(tag)
    if acao == "amanha" and tag.startswith(("casa_tarefa-", "chegou_casa-")):
        acao = "adiar"  # botao "Amanha" do aviso "Chegou em casa" (categoria "casa"): hora_certa.acao_casa
    elif acao == "amanha":
        return _pra_amanha(tag)  # 07/11: categoria "hora" (Feito / +15 min / Amanha)
    return executar_acao(tag, acao)
