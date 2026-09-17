import os
from datetime import date

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

import claude_client
from db import get_db, init_db

app = Flask(__name__)
init_db()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/capture", methods=["POST"])
def capture():
    text = (request.json or {}).get("text", "").strip()
    if not text:
        return jsonify({"error": "texto vazio"}), 400

    parsed = claude_client.classify_capture(text)
    conn = get_db()
    if parsed["tipo"] == "gasto":
        conn.execute(
            "INSERT INTO expenses (amount, category, description, source_text) VALUES (?, ?, ?, ?)",
            (parsed["valor"], parsed.get("categoria") or "outros", parsed["titulo"], text),
        )
    else:
        conn.execute(
            "INSERT INTO tasks (title, due_at, source_text) VALUES (?, ?, ?)",
            (parsed["titulo"], parsed.get("quando"), text),
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
    conn.close()
    return jsonify([dict(r) for r in rows])


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

    steps = claude_client.break_down_task(task["title"])
    for i, step in enumerate(steps):
        conn.execute(
            "INSERT INTO subtasks (task_id, title, position) VALUES (?, ?, ?)",
            (task_id, step, i),
        )
    conn.commit()
    conn.close()
    return jsonify({"steps": steps})


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
    conn.close()

    text = claude_client.summarize_day(
        [r["title"] for r in done],
        [r["title"] for r in pending],
        [dict(r) for r in expenses],
    )
    return jsonify({"summary": text})


@app.route("/api/construtora/resumo", methods=["GET"])
def construtora_resumo():
    base_url = os.environ.get("CONSTRUTORA_API_URL")
    api_key = os.environ.get("CONSTRUTORA_API_KEY")
    if not base_url or not api_key:
        return jsonify({"configurado": False})

    resp = requests.get(
        f"{base_url}/api/resumo", headers={"X-API-Key": api_key}, timeout=5
    )
    resp.raise_for_status()
    return jsonify({"configurado": True, "dados": resp.json()})


if __name__ == "__main__":
    app.run(debug=True, port=5001)
