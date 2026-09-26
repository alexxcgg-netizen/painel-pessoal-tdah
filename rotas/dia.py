"""Blueprint dia - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from rotas._base import app_modulo
from datetime import timedelta
from db import get_db, list_memorias
import vida

bp = Blueprint("dia", __name__)

@bp.route("/api/visao-dia/hoje", methods=["GET"])
def visao_dia_hoje():
    app = app_modulo()
    _proximo_item_em_foco = app._proximo_item_em_foco
    _status_do_dia = app._status_do_dia
    _visao_do_dia_itens = app._visao_do_dia_itens
    date = app.date
    datetime = app.datetime
    materializar_tarefas_recorrentes = app.materializar_tarefas_recorrentes
    conn = get_db()
    materializar_tarefas_recorrentes(conn)
    hoje = date.today()
    agora = datetime.now()
    itens = _visao_do_dia_itens(conn, hoje)
    conn.close()
    concluidas = sum(1 for i in itens if i.get("concluido"))
    return jsonify(
        {
            "status": _status_do_dia(itens, agora),
            "em_foco": _proximo_item_em_foco(itens, agora),
            "total_itens": len(itens),
            "total_concluidas": concluidas,
            "timeline": itens,
        }
    )

@bp.route("/api/visao-dia/periodo", methods=["GET"])
def visao_dia_periodo():
    app = app_modulo()
    _contagem_dia = app._contagem_dia
    _semana_de = app._semana_de
    date = app.date
    tipo = request.args.get("tipo", "semana")
    hoje = date.today()
    if tipo == "mes":
        inicio = hoje.replace(day=1)
        fim = vida.somar_meses(inicio, 1) - timedelta(days=1)
    else:
        tipo = "semana"
        inicio, fim_iso = _semana_de(hoje)
        inicio = date.fromisoformat(inicio)
        fim = date.fromisoformat(fim_iso)
    conn = get_db()
    dias = []
    d = inicio
    while d <= fim:
        dias.append(_contagem_dia(conn, d))
        d += timedelta(days=1)
    conn.close()
    return jsonify({"tipo": tipo, "dias": dias})

@bp.route("/api/plano-do-dia", methods=["POST"])
def plano_do_dia():
    app = app_modulo()
    _call_claude = app._call_claude
    _eventos_de_hoje_com_seguranca = app._eventos_de_hoje_com_seguranca
    _log_usage = app._log_usage
    _marcar_atividade = app._marcar_atividade
    _tarefas_pendentes_sem_horario_hoje = app._tarefas_pendentes_sem_horario_hoje
    claude_client = app.claude_client
    conn = get_db()
    pending = _tarefas_pendentes_sem_horario_hoje(conn)
    eventos = _eventos_de_hoje_com_seguranca(conn)
    memorias = list_memorias(conn)

    result, error = _call_claude(
        claude_client.plano_do_dia,
        [r["title"] for r in pending],
        eventos,
        [m["texto"] for m in memorias],
    )
    if error:
        conn.close()
        return error
    texto, usage = result

    _log_usage(conn, usage, "plano_dia")
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"plano": texto})
