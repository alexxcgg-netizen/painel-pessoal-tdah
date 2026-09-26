"""Blueprint resumo - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from rotas._base import app_modulo
from db import get_db, list_memorias, obter_resumo_dia_cache, salvar_resumo_dia_cache
import json

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
    _call_claude = app._call_claude
    _clima_contexto_resumo = app._clima_contexto_resumo
    _construtora_contexto_resumo = app._construtora_contexto_resumo
    _eventos_de_hoje_com_seguranca = app._eventos_de_hoje_com_seguranca
    _impressao_resumo_dia = app._impressao_resumo_dia
    _log_usage = app._log_usage
    _modo_visitante_ativo = app._modo_visitante_ativo
    _saude_contexto_resumo = app._saude_contexto_resumo
    claude_client = app.claude_client
    date = app.date
    materializar_tarefas_recorrentes = app.materializar_tarefas_recorrentes
    today = date.today().isoformat()
    conn = get_db()
    materializar_tarefas_recorrentes(conn)
    done = conn.execute("SELECT title FROM tasks WHERE date(completed_at) = ?", (today,)).fetchall()
    pending = conn.execute(
        "SELECT title FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL"
    ).fetchall()
    if _modo_visitante_ativo():
        # US-C20: nem chama a IA - o resumo em texto livre poderia mencionar
        # valor gasto ou dado de saude, e nao da pra garantir que um prompt
        # "sem esses dados" nunca vaze nada por inferencia. Mais seguro nao
        # gerar o texto nenhum enquanto o modo visitante estiver ativo.
        eventos = _eventos_de_hoje_com_seguranca(conn)
        conn.close()
        return jsonify(
            {
                "summary": "Resumo oculto no modo visitante.",
                "gasto_hoje": None,
                "gasto_planejado": None,
                "tarefas_concluidas": len(done),
                "eventos_hoje": len(eventos),
            }
        )
    expenses = conn.execute(
        "SELECT amount, category FROM expenses WHERE date(created_at) = ? AND tipo = 'real'", (today,)
    ).fetchall()
    gasto_hoje = sum(r["amount"] for r in expenses)
    gasto_planejado = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE date(created_at) = ? AND tipo = 'planejado'",
        (today,),
    ).fetchone()["total"]
    eventos = _eventos_de_hoje_com_seguranca(conn)

    # Faixa M4: so o texto (summary) vem do cache - gasto_hoje/gasto_planejado/
    # tarefas_concluidas/eventos_hoje acima sao recalculados sempre, frescos.
    forcar = request.args.get("forcar") == "1"
    impressao = _impressao_resumo_dia(conn, today, len(eventos))
    cache = None if forcar else obter_resumo_dia_cache(conn, today)
    if cache and cache["impressao"] == impressao:
        conn.close()
        return jsonify(
            {
                "summary": json.loads(cache["resposta_json"])["summary"],
                "gasto_hoje": gasto_hoje,
                "gasto_planejado": gasto_planejado,
                "tarefas_concluidas": len(done),
                "eventos_hoje": len(eventos),
            }
        )

    memorias = list_memorias(conn)
    saude = _saude_contexto_resumo(conn)
    construtora = _construtora_contexto_resumo()
    clima_hoje = _clima_contexto_resumo()

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
        conn.close()
        return error
    text, usage = result

    _log_usage(conn, usage, "resumo_dia")
    salvar_resumo_dia_cache(conn, today, impressao, json.dumps({"summary": text}))
    conn.close()
    return jsonify(
        {
            "summary": text,
            "gasto_hoje": gasto_hoje,
            "gasto_planejado": gasto_planejado,
            "tarefas_concluidas": len(done),
            "eventos_hoje": len(eventos),
        }
    )
