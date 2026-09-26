"""Blueprint metas - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import add_to_goal, get_db, list_goal_deposits, list_goals
import math
import vida

bp = Blueprint("metas", __name__)

@bp.route("/api/metas", methods=["GET"])
def metas():
    app = app_modulo()
    _calculo_meta = app._calculo_meta
    date = app.date
    hoje = date.today()
    conn = get_db()
    resultado = []
    for g in list_goals(conn):
        meta = _calculo_meta(g)
        meta["previsao"] = vida.previsao_meta(
            g["valor_alvo"], g["valor_guardado"], list_goal_deposits(conn, g["id"]), hoje
        )
        resultado.append(meta)
    conn.close()
    return jsonify(resultado)

@bp.route("/api/metas/<int:goal_id>/guardar", methods=["POST"])
def guardar_meta(goal_id):
    app = app_modulo()
    _calculo_meta = app._calculo_meta
    _corpo_json = app._corpo_json
    _marcar_atividade = app._marcar_atividade
    valor = _corpo_json().get("valor")
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor) or valor <= 0:
        return jsonify({"error": "informe um valor positivo"}), 400

    conn = get_db()
    goal = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
    if not goal:
        conn.close()
        return jsonify({"error": "meta nao encontrada"}), 404
    add_to_goal(conn, goal_id, valor)
    goal = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify(_calculo_meta(dict(goal)))

@bp.route("/api/metas/<int:goal_id>/historico", methods=["GET"])
def meta_historico(goal_id):
    conn = get_db()
    goal = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
    if not goal:
        conn.close()
        return jsonify({"error": "meta nao encontrada"}), 404
    depositos = list_goal_deposits(conn, goal_id)
    conn.close()

    acumulado = 0.0
    pontos = [{"data": goal["criado_em"][:10], "acumulado": 0.0}]
    for d in depositos:
        acumulado += d["valor"]
        pontos.append({"data": d["criado_em"][:10], "acumulado": round(acumulado, 2)})
    return jsonify({"pontos": pontos, "valor_alvo": goal["valor_alvo"]})
