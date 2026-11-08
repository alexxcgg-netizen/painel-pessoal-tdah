"""Blueprint fechamento - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import get_db

bp = Blueprint("fechamento", __name__)

@bp.route("/api/fechamento-do-dia", methods=["GET"])
def fechamento_do_dia():
    """Ritual de fechamento (inspirado no 'shutdown' do Sunsama): o que foi
    concluido hoje e o que ainda ficou marcado pra hoje e nao foi feito -
    sem cobranca, a tarefa continua pendente naturalmente e reaparece
    amanha, isso aqui e so uma fotografia pra fechar o dia com a cabeca
    tranquila."""
    app = app_modulo()
    date = app.date
    hoje = date.today().isoformat()
    conn = get_db()
    concluidas = conn.execute(
        f"SELECT title FROM tasks WHERE {app.DIA_CONCLUSAO_SQL} = ? ORDER BY completed_at", (hoje,)
    ).fetchall()
    pendentes_hoje = conn.execute(
        "SELECT title FROM tasks WHERE completed_at IS NULL AND due_date = ? "
        "ORDER BY hora IS NULL, hora",
        (hoje,),
    ).fetchall()
    conn.close()
    return jsonify(
        {
            "concluidas": [r["title"] for r in concluidas],
            "pendentes_hoje": [r["title"] for r in pendentes_hoje],
        }
    )
