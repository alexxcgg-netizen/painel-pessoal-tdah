import os
from datetime import date

import anthropic
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

import bank_ofx
import claude_client
import pluggy_client
from db import (
    add_to_goal,
    create_goal,
    get_db,
    get_or_create_bank_account,
    init_db,
    insert_bank_transactions,
    list_goals,
    record_usage,
    total_cost_usd,
)

app = Flask(__name__)
init_db()

CLAUDE_ERROR_MSG = "Erro ao falar com a IA. Tenta de novo em instantes."
CLAUDE_FORMAT_ERROR_MSG = "A IA respondeu em um formato inesperado. Tenta de novo."


def _log_usage(conn, usage: dict):
    record_usage(conn, usage["model"], usage["input_tokens"], usage["output_tokens"], usage["cost_usd"])


def _call_claude(fn, *args):
    """Chama uma funcao do claude_client e traduz falhas em uma resposta de erro pronta pra devolver."""
    try:
        return fn(*args), None
    except anthropic.APIError:
        return None, (jsonify({"error": CLAUDE_ERROR_MSG}), 502)
    except (ValueError, KeyError):
        return None, (jsonify({"error": CLAUDE_FORMAT_ERROR_MSG}), 502)


def _calculo_meta(goal: dict) -> dict:
    """Faz a conta de quanto falta guardar por mes - em Python puro, nao pela IA."""
    falta = goal["valor_alvo"] - goal["valor_guardado"]
    por_mes = None
    meses = None
    if goal["prazo"]:
        hoje = date.today()
        prazo = date.fromisoformat(goal["prazo"])
        meses = (prazo.year - hoje.year) * 12 + (prazo.month - hoje.month)
        if prazo.day < hoje.day:
            meses -= 1
        meses = max(meses, 1)
        por_mes = max(falta, 0) / meses
    return {**goal, "falta": falta, "meses_restantes": meses, "por_mes": por_mes}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/capture", methods=["POST"])
def capture():
    body = request.json or {}
    text = body.get("text", "").strip()
    clarificacao = body.get("clarificacao", "").strip()
    if not text:
        return jsonify({"error": "texto vazio"}), 400

    full_text = f"{text}. Contexto adicional: {clarificacao}" if clarificacao else text

    result, error = _call_claude(claude_client.classify_capture, full_text)
    if error:
        return error
    parsed, usage = result

    conn = get_db()
    _log_usage(conn, usage)

    # Se a IA ainda ficou em duvida, so pede esclarecimento uma vez (quando a
    # clarificacao ja foi enviada, seguimos com o melhor palpite mesmo assim).
    if parsed.get("duvida") and not clarificacao:
        conn.close()
        return jsonify({"duvida": parsed["duvida"], "texto_original": text})

    if parsed["tipo"] == "gasto":
        conn.execute(
            "INSERT INTO expenses (amount, category, description, source_text) VALUES (?, ?, ?, ?)",
            (parsed["valor"], parsed.get("categoria") or "outros", parsed["titulo"], full_text),
        )
    elif parsed["tipo"] == "meta":
        create_goal(conn, parsed["titulo"], parsed["valor"], parsed.get("prazo"))
    else:
        conn.execute(
            "INSERT INTO tasks (title, due_at, source_text) VALUES (?, ?, ?)",
            (parsed["titulo"], parsed.get("quando"), full_text),
        )
    conn.commit()
    conn.close()
    return jsonify(parsed), 201


@app.route("/api/tasks", methods=["GET"])
def list_tasks():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE completed_at IS NULL ORDER BY created_at DESC"
    ).fetchall()
    tasks = []
    for row in rows:
        task = dict(row)
        subtasks = conn.execute(
            "SELECT * FROM subtasks WHERE task_id = ? ORDER BY position", (task["id"],)
        ).fetchall()
        task["subtasks"] = [dict(s) for s in subtasks]
        tasks.append(task)
    conn.close()
    return jsonify(tasks)


@app.route("/api/tasks/<int:task_id>/complete", methods=["POST"])
def complete_task(task_id):
    conn = get_db()
    conn.execute("UPDATE tasks SET completed_at = datetime('now') WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/tasks/<int:task_id>/breakdown", methods=["POST"])
def breakdown_task(task_id):
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

    _log_usage(conn, usage)
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


@app.route("/api/subtasks/<int:subtask_id>/complete", methods=["POST"])
def complete_subtask(subtask_id):
    conn = get_db()
    conn.execute("UPDATE subtasks SET completed_at = datetime('now') WHERE id = ?", (subtask_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/expenses", methods=["GET"])
def list_expenses():
    conn = get_db()
    rows = conn.execute("SELECT * FROM expenses ORDER BY created_at DESC LIMIT 50").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/summary/today", methods=["GET"])
def summary_today():
    today = date.today().isoformat()
    conn = get_db()
    done = conn.execute("SELECT title FROM tasks WHERE date(completed_at) = ?", (today,)).fetchall()
    pending = conn.execute("SELECT title FROM tasks WHERE completed_at IS NULL").fetchall()
    expenses = conn.execute(
        "SELECT amount, category FROM expenses WHERE date(created_at) = ?", (today,)
    ).fetchall()
    gasto_hoje = sum(r["amount"] for r in expenses)

    result, error = _call_claude(
        claude_client.summarize_day,
        [r["title"] for r in done],
        [r["title"] for r in pending],
        [dict(r) for r in expenses],
    )
    if error:
        conn.close()
        return error
    text, usage = result

    _log_usage(conn, usage)
    conn.close()
    return jsonify({"summary": text, "gasto_hoje": gasto_hoje, "tarefas_concluidas": len(done)})


@app.route("/api/uso/total", methods=["GET"])
def uso_total():
    conn = get_db()
    total = total_cost_usd(conn)
    conn.close()
    return jsonify({"custo_usd": round(total, 4)})


@app.route("/api/bancos/importar", methods=["POST"])
def importar_extrato():
    banco = request.form.get("banco", "").strip().lower()
    tipo = request.form.get("tipo", "conta").strip().lower()
    if tipo not in ("conta", "cartao"):
        tipo = "conta"
    arquivo = request.files.get("arquivo")
    if not banco or not arquivo:
        return jsonify({"error": "informe o banco e o arquivo OFX"}), 400

    texto = bank_ofx.decode_ofx(arquivo.read())
    try:
        transacoes = bank_ofx.parse_transactions(texto)
    except ValueError:
        return jsonify({"error": "nao consegui ler as datas/valores desse arquivo OFX"}), 400

    if not transacoes:
        return jsonify({"error": "nenhuma transacao encontrada nesse arquivo"}), 400

    conn = get_db()
    conta_id = get_or_create_bank_account(conn, banco, tipo)
    novas = insert_bank_transactions(conn, conta_id, transacoes)
    conn.close()
    return jsonify(
        {
            "conta_id": conta_id,
            "encontradas": len(transacoes),
            "novas": novas,
            "duplicadas": len(transacoes) - novas,
        }
    )


@app.route("/api/bancos", methods=["GET"])
def listar_bancos():
    conn = get_db()
    contas = conn.execute("SELECT * FROM bank_accounts ORDER BY banco, tipo").fetchall()
    resultado = []
    for c in contas:
        stats = conn.execute(
            """SELECT COUNT(*) AS total, MAX(data) AS ultima,
                      COALESCE(SUM(CASE WHEN valor < 0 THEN -valor ELSE 0 END), 0) AS total_gasto
               FROM bank_transactions WHERE bank_account_id = ?""",
            (c["id"],),
        ).fetchone()
        resultado.append(
            {
                **dict(c),
                "total_transacoes": stats["total"],
                "ultima_transacao": stats["ultima"],
                "total_gasto": stats["total_gasto"],
            }
        )
    conn.close()
    return jsonify(resultado)


@app.route("/api/bancos/<int:conta_id>/transacoes", methods=["GET"])
def transacoes_banco(conta_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM bank_transactions WHERE bank_account_id = ? ORDER BY data DESC LIMIT 100",
        (conta_id,),
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/bancos/sync-status", methods=["GET"])
def bancos_sync_status():
    configurado = pluggy_client.configurado()
    return jsonify(
        {
            "sincronizacao_automatica": configurado,
            "info": (
                "Conecte um banco automaticamente pra sincronizar sem precisar exportar OFX."
                if configurado
                else "Sincronizacao automatica ainda nao configurada - veja o README (integracao com Pluggy)."
            ),
        }
    )


@app.route("/api/bancos/conectar/token", methods=["POST"])
def bancos_conectar_token():
    if not pluggy_client.configurado():
        return jsonify({"error": "sincronizacao automatica nao configurada"}), 400
    try:
        token = pluggy_client.create_connect_token()
    except requests.RequestException:
        return jsonify({"error": "nao consegui falar com a Pluggy agora"}), 502
    return jsonify({"connect_token": token})


@app.route("/api/bancos/conectar/finalizar", methods=["POST"])
def bancos_conectar_finalizar():
    if not pluggy_client.configurado():
        return jsonify({"error": "sincronizacao automatica nao configurada"}), 400

    item_id = (request.json or {}).get("item_id")
    if not item_id:
        return jsonify({"error": "item_id obrigatorio"}), 400

    try:
        item = pluggy_client.get_item(item_id)
        contas_pluggy = pluggy_client.get_accounts(item_id)
    except requests.RequestException:
        return jsonify({"error": "nao consegui buscar os dados na Pluggy agora"}), 502

    banco = item.get("connector", {}).get("name", "banco").lower()

    conn = get_db()
    resumo = []
    for conta_pluggy in contas_pluggy:
        tipo = "cartao" if conta_pluggy.get("type") == "CREDIT" else "conta"
        conta_id = get_or_create_bank_account(conn, banco, tipo)
        try:
            transacoes_pluggy = pluggy_client.get_transactions(conta_pluggy["id"])
        except requests.RequestException:
            conn.close()
            return jsonify({"error": "nao consegui buscar as transacoes na Pluggy agora"}), 502
        transacoes = pluggy_client.normalizar_transacoes(transacoes_pluggy)
        novas = insert_bank_transactions(conn, conta_id, transacoes)
        resumo.append({"conta_id": conta_id, "tipo": tipo, "novas": novas})
    conn.close()

    return jsonify({"banco": banco, "contas": resumo})


@app.route("/api/metas", methods=["GET"])
def metas():
    conn = get_db()
    goals = list_goals(conn)
    conn.close()
    return jsonify([_calculo_meta(g) for g in goals])


@app.route("/api/metas/<int:goal_id>/guardar", methods=["POST"])
def guardar_meta(goal_id):
    valor = (request.json or {}).get("valor")
    if not isinstance(valor, (int, float)) or valor <= 0:
        return jsonify({"error": "informe um valor positivo"}), 400

    conn = get_db()
    add_to_goal(conn, goal_id, valor)
    goal = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
    conn.close()
    if not goal:
        return jsonify({"error": "meta nao encontrada"}), 404
    return jsonify(_calculo_meta(dict(goal)))


@app.route("/api/construtora/resumo", methods=["GET"])
def construtora_resumo():
    base_url = os.environ.get("CONSTRUTORA_API_URL")
    api_key = os.environ.get("CONSTRUTORA_API_KEY")
    if not base_url or not api_key:
        return jsonify({"configurado": False})

    try:
        resp = requests.get(
            f"{base_url}/api/resumo", headers={"X-API-Key": api_key}, timeout=5
        )
        resp.raise_for_status()
    except requests.RequestException:
        return jsonify({"configurado": True, "erro": "Nao consegui falar com a API da construtora agora."}), 502

    return jsonify({"configurado": True, "dados": resp.json()})


if __name__ == "__main__":
    app.run(debug=True, port=5001)
