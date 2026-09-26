"""Blueprint tasks - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from rotas._base import app_modulo
from db import complete_task, criar_tarefa_de_brain_dump, definir_esforco_tarefa, get_db, list_fichas_treino, reclassificar_tarefa_para_gasto, registrar_correcao_classificacao
import db
import math
import vida

bp = Blueprint("tasks", __name__)

@bp.route("/api/tasks", methods=["GET"])
def list_tasks():
    app = app_modulo()
    date = app.date
    materializar_tarefas_recorrentes = app.materializar_tarefas_recorrentes
    conn = get_db()
    materializar_tarefas_recorrentes(conn)
    # M3 (uso diario): "Ver concluidas" na aba Tarefas - concluida NUNCA e apagada
    # (so sai da lista padrao por esse filtro completed_at IS NULL), so busca as
    # ultimas quando o dono pedir explicitamente via ?estado=concluidas (a UI so
    # chama isso ao tocar no botao - preguicoso, nunca no carregamento normal).
    # Qualquer outro valor (ou nenhum) cai no comportamento padrao de sempre.
    estado = request.args.get("estado", "")
    if estado == "concluidas":
        rows = conn.execute(
            "SELECT * FROM tasks WHERE completed_at IS NOT NULL AND recorrencia IS NULL "
            "ORDER BY completed_at DESC LIMIT 50"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL "
            "ORDER BY created_at DESC"
        ).fetchall()
    # Uma query so pras subtarefas de todas as tasks (em vez de uma query por task -
    # nao pesava nada com poucas tarefas, mas escala mal conforme o historico cresce).
    task_ids = [row["id"] for row in rows]
    subtasks_por_task = {}
    if task_ids:
        placeholders = ",".join("?" for _ in task_ids)
        subtask_rows = conn.execute(
            f"SELECT * FROM subtasks WHERE task_id IN ({placeholders}) ORDER BY position",
            task_ids,
        ).fetchall()
        for s in subtask_rows:
            subtasks_por_task.setdefault(s["task_id"], []).append(dict(s))
    fichas = list_fichas_treino(conn)
    conn.close()

    hoje = date.today()
    tasks = []
    for row in rows:
        task = dict(row)
        task["subtasks"] = subtasks_por_task.get(task["id"], [])
        task["empacada_dias"] = vida.dias_empacada(task, task["subtasks"], hoje)
        task["fichas_treino"] = [f["id"] for f in vida.ficha_para_titulo(fichas, task["title"])]
        tasks.append(task)
    return jsonify(tasks)

@bp.route("/api/tasks", methods=["POST"])
def criar_tarefa_direta():
    """Fase 6 (US-F10): formulario direto na aba Tarefas, sem passar pela
    classificacao por IA (essa ja existe via chat/captura, /api/capture e
    registrar_tarefa) - so titulo + prazo OPCIONAL. Reusa o mesmo insert
    minimo de criar_tarefa_de_brain_dump (Fase 5, US-C6) em vez de duplicar
    o INSERT numa terceira funcao."""
    app = app_modulo()
    _corpo_json = app._corpo_json
    _marcar_atividade = app._marcar_atividade
    date = app.date
    body = _corpo_json()
    titulo = (body.get("titulo") or "").strip()
    if not titulo:
        return jsonify({"error": "informe um titulo"}), 400
    if len(titulo) > 200:
        return jsonify({"error": "titulo muito longo (max 200 caracteres)"}), 400

    due_date_bruto = body.get("due_date")
    due_date = due_date_bruto.strip() if isinstance(due_date_bruto, str) else None
    if due_date:
        try:
            date.fromisoformat(due_date)
        except ValueError:
            return jsonify({"error": "prazo precisa estar em formato AAAA-MM-DD"}), 400
    else:
        due_date = None

    conn = get_db()
    task_id = criar_tarefa_de_brain_dump(conn, titulo, due_date)
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"id": task_id, "ok": True}), 201

@bp.route("/api/tasks/<int:task_id>/complete", methods=["POST"])
def complete_task_rota(task_id):
    app = app_modulo()
    _marcar_atividade = app._marcar_atividade
    conn = get_db()
    complete_task(conn, task_id)
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@bp.route("/api/tasks/<int:task_id>/reabrir", methods=["POST"])
def reabrir_task_rota(task_id):
    """Fase 6 (US-E3): desmarcar o checkbox de uma tarefa no card
    tarefas_criadas volta ela pra pendente (o par do /complete)."""
    conn = get_db()
    ok = db.reabrir_tarefa(conn, task_id)
    conn.close()
    if not ok:
        return jsonify({"error": "tarefa nao encontrada"}), 404
    return jsonify({"ok": True})

@bp.route("/api/tasks/<int:task_id>/esforco", methods=["POST"])
def definir_esforco_tarefa_rota(task_id):
    """Fase 5 (US-C7)."""
    app = app_modulo()
    _corpo_json = app._corpo_json
    body = _corpo_json()
    esforco = body.get("esforco")
    if esforco not in vida.NIVEIS_ENERGIA:
        return jsonify({"error": "esforco precisa ser baixa, media ou alta"}), 400
    conn = get_db()
    ok = definir_esforco_tarefa(conn, task_id, esforco)
    conn.close()
    if not ok:
        return jsonify({"error": "tarefa nao encontrada"}), 404
    return jsonify({"ok": True, "esforco": esforco})

@bp.route("/api/tarefas/sugestao-energia", methods=["GET"])
def sugestao_por_energia():
    """Fase 5 (US-C7): sugere tarefas pendentes compativeis com o nivel de
    energia atual informado (baixa/media/alta) - so filtra as ja listadas
    por /api/tasks (mesma fonte, sem duplicar a query)."""
    nivel = request.args.get("nivel", "")
    if nivel not in vida.NIVEIS_ENERGIA:
        return jsonify({"error": "nivel precisa ser baixa, media ou alta"}), 400
    conn = get_db()
    tasks = conn.execute(
        "SELECT * FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL "
        "ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    compativeis = vida.tarefas_compativeis_com_energia([dict(t) for t in tasks], nivel)
    return jsonify(compativeis)

@bp.route("/api/tasks/<int:task_id>/breakdown", methods=["POST"])
def breakdown_task(task_id):
    app = app_modulo()
    _call_claude = app._call_claude
    _log_usage = app._log_usage
    claude_client = app.claude_client
    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return jsonify({"error": "tarefa nao encontrada"}), 404

    result, error = _call_claude(claude_client.break_down_task, task["title"])
    if error:
        conn.close()
        return error
    steps, usage = result

    _log_usage(conn, usage, "quebra_tarefa")
    for i, step in enumerate(steps):
        conn.execute(
            "INSERT INTO subtasks (task_id, title, position) VALUES (?, ?, ?)",
            (task_id, step, i),
        )
    conn.commit()
    subtasks = conn.execute(
        "SELECT * FROM subtasks WHERE task_id = ? ORDER BY position", (task_id,)
    ).fetchall()
    conn.close()
    return jsonify({"subtasks": [dict(s) for s in subtasks]})

@bp.route("/api/subtasks/<int:subtask_id>/complete", methods=["POST"])
def complete_subtask(subtask_id):
    app = app_modulo()
    _marcar_atividade = app._marcar_atividade
    conn = get_db()
    conn.execute("UPDATE subtasks SET completed_at = datetime('now') WHERE id = ?", (subtask_id,))
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@bp.route("/api/tasks/<int:task_id>/reclassificar", methods=["POST"])
def reclassificar_tarefa_rota(task_id):
    """Correcao rapida: a IA classificou como tarefa algo que na verdade era
    gasto. "valor" e obrigatorio - o texto original pode nao ter um numero
    claro, entao quem esta corrigindo (o Alex, nao a IA de novo) informa."""
    app = app_modulo()
    _corpo_json = app._corpo_json
    _marcar_atividade = app._marcar_atividade
    corpo = _corpo_json()
    valor = corpo.get("valor")
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor) or valor <= 0:
        return jsonify({"error": "informe um valor valido"}), 400
    categoria = corpo.get("categoria") if isinstance(corpo.get("categoria"), str) else None
    tipo = corpo.get("tipo") if corpo.get("tipo") in ("real", "planejado") else "real"

    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return jsonify({"error": "tarefa nao encontrada"}), 404

    resultado = reclassificar_tarefa_para_gasto(conn, task_id, float(valor), categoria, tipo)
    novo_id, subtasks_removidas = resultado
    registrar_correcao_classificacao(
        conn, task["source_text"] or task["title"], "tarefa", None, "gasto", categoria
    )
    _marcar_atividade(conn)
    conn.close()
    return jsonify({"ok": True, "novo_id": novo_id, "subtasks_removidas": subtasks_removidas})

@bp.route("/api/tasks/<int:task_id>/requebrar", methods=["POST"])
def requebrar_task(task_id):
    """Tarefa empacada: pede um jeito DIFERENTE de atacar (primeiro passo
    ridiculamente facil). Passos ja feitos ficam; os nao feitos sao trocados."""
    app = app_modulo()
    CLAUDE_FORMAT_ERROR_MSG = app.CLAUDE_FORMAT_ERROR_MSG
    _call_claude = app._call_claude
    _log_usage = app._log_usage
    claude_client = app.claude_client
    date = app.date
    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return jsonify({"error": "tarefa nao encontrada"}), 404
    subtasks = [
        dict(s)
        for s in conn.execute(
            "SELECT * FROM subtasks WHERE task_id = ? ORDER BY position", (task_id,)
        ).fetchall()
    ]
    dias = vida.dias_empacada(dict(task), subtasks, date.today()) or 0
    antigos = [s["title"] for s in subtasks if not s["completed_at"]]
    result, error = _call_claude(claude_client.requebrar_tarefa, task["title"], dias, antigos)
    if error:
        conn.close()
        return error
    passos, usage = result
    passos = [p.strip() for p in passos if isinstance(p, str) and p.strip()] if isinstance(passos, list) else []
    if not passos:
        conn.close()
        return jsonify({"error": CLAUDE_FORMAT_ERROR_MSG}), 502
    _log_usage(conn, usage, "requebrar_tarefa")
    conn.execute("DELETE FROM subtasks WHERE task_id = ? AND completed_at IS NULL", (task_id,))
    inicio = max((s["position"] for s in subtasks if s["completed_at"]), default=-1) + 1
    for i, passo in enumerate(passos):
        conn.execute(
            "INSERT INTO subtasks (task_id, title, position) VALUES (?, ?, ?)",
            (task_id, passo, inicio + i),
        )
    conn.commit()
    novas = conn.execute(
        "SELECT * FROM subtasks WHERE task_id = ? ORDER BY position", (task_id,)
    ).fetchall()
    conn.close()
    return jsonify({"subtasks": [dict(s) for s in novas]})
