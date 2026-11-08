"""Blueprint resumo - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from rotas._base import app_modulo
from db import get_db, list_memorias, obter_resumo_dia_cache, salvar_resumo_dia_cache
import json
from concurrent.futures import ThreadPoolExecutor

bp = Blueprint("resumo", __name__)

@bp.route("/api/resumo-manha", methods=["GET"])
def resumo_manha_rota():
    app = app_modulo()
    _resumo_falado_manha = app._resumo_falado_manha
    conn = get_db()
    texto = _resumo_falado_manha(conn)
    conn.close()
    return jsonify({"texto": texto})

@bp.route("/api/summary/today", methods=["GET"])
def summary_today():
    app = app_modulo()
    conn = get_db()
    try:
        corpo, erro = resumo_do_dia(app, conn, forcar=request.args.get("forcar") == "1")
    finally:
        conn.close()
    return erro if erro is not None else jsonify(corpo)


def resumo_do_dia(app, conn, *, forcar: bool = False):
    """Monta o resumo de hoje: (corpo, None) ou (None, resposta de erro do _call_claude).
    Usado pela rota e pelo preparo da madrugada (app.preparar_dia), que deixa o texto no cache
    antes de ele abrir o app - na primeira abertura do dia o resumo ja sai do cache."""
    _call_claude = app._call_claude
    _clima_contexto_resumo = app._clima_contexto_resumo
    _construtora_contexto_resumo = app._construtora_contexto_resumo
    _eventos_de_hoje_com_seguranca = app._eventos_de_hoje_com_seguranca
    _impressao_resumo_dia = app._impressao_resumo_dia
    _log_usage = app._log_usage
    _modo_visitante_ativo = app._modo_visitante_ativo
    _saude_contexto_resumo = app._saude_contexto_resumo
    claude_client = app.claude_client
    today = app.date.today().isoformat()
    app.materializar_tarefas_recorrentes(conn)
    done = conn.execute(f"SELECT title FROM tasks WHERE {app.DIA_CONCLUSAO_SQL} = ?", (today,)).fetchall()
    pending = conn.execute(
        "SELECT title FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL"
    ).fetchall()
    if _modo_visitante_ativo():
        # US-C20: nem chama a IA - o resumo em texto livre poderia mencionar
        # valor gasto ou dado de saude, e nao da pra garantir que um prompt
        # "sem esses dados" nunca vaze nada por inferencia. Mais seguro nao
        # gerar o texto nenhum enquanto o modo visitante estiver ativo.
        eventos = _eventos_de_hoje_com_seguranca(conn)
        return {
            "summary": "Resumo oculto no modo visitante.",
            "gasto_hoje": None,
            "gasto_planejado": None,
            "tarefas_concluidas": len(done),
            "eventos_hoje": len(eventos),
        }, None
    expenses = conn.execute(
        f"SELECT amount, category FROM expenses WHERE {app.DIA_GASTO_SQL} = ? AND tipo = 'real'", (today,)
    ).fetchall()
    gasto_hoje = sum(r["amount"] for r in expenses)
    gasto_planejado = conn.execute(
        f"SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE {app.DIA_GASTO_SQL} = ? AND tipo = 'planejado'",
        (today,),
    ).fetchone()["total"]
    eventos = _eventos_de_hoje_com_seguranca(conn)
    numeros = {
        "gasto_hoje": gasto_hoje,
        "gasto_planejado": gasto_planejado,
        "tarefas_concluidas": len(done),
        "eventos_hoje": len(eventos),
    }

    # Faixa M4: so o texto (summary) vem do cache - gasto_hoje/gasto_planejado/
    # tarefas_concluidas/eventos_hoje acima sao recalculados sempre, frescos.
    impressao = _impressao_resumo_dia(conn, today, len(eventos))
    cache = None if forcar else obter_resumo_dia_cache(conn, today)
    if cache and cache["impressao"] == impressao:
        return {"summary": json.loads(cache["resposta_json"])["summary"], **numeros}, None

    # construtora e tempo saem juntos (2026-11-05): antes iam em fila, um esperando o outro
    fora = ThreadPoolExecutor(max_workers=2, thread_name_prefix="resumo-dia")
    try:
        f_construtora = fora.submit(_construtora_contexto_resumo)
        f_clima = fora.submit(_clima_contexto_resumo)
        memorias = list_memorias(conn)
        saude = _saude_contexto_resumo(conn)
        construtora = f_construtora.result()
        clima_hoje = f_clima.result()
    finally:
        fora.shutdown(wait=False)

    result, error = _call_claude(
        claude_client.summarize_day,
        [r["title"] for r in done],
        [r["title"] for r in pending],
        [dict(r) for r in expenses],
        [e["titulo"] for e in eventos],
        [m["texto"] for m in memorias],
        saude,
        construtora,
        clima_hoje,
    )
    if error:
        return None, error
    text, usage = result

    _log_usage(conn, usage, "resumo_dia")
    salvar_resumo_dia_cache(conn, today, impressao, json.dumps({"summary": text}))
    return {"summary": text, **numeros}, None
