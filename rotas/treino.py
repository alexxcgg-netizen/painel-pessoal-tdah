"""Blueprint treino - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import delete_ficha_treino, get_db, list_fichas_treino, list_treinos, registrar_treino, salvar_ficha_treino

bp = Blueprint("treino", __name__)

@bp.route("/api/treino/fichas", methods=["GET"])
def fichas_treino():
    conn = get_db()
    resultado = list_fichas_treino(conn)
    conn.close()
    return jsonify(resultado)

@bp.route("/api/treino/fichas", methods=["POST"])
def salvar_ficha_treino_rota():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _texto_curto = app._texto_curto
    body = _corpo_json()
    grupo = _texto_curto(body.get("grupo"), 40)
    exercicios = body.get("exercicios")
    if isinstance(exercicios, list):
        exercicios = "\n".join(str(e).strip() for e in exercicios if str(e).strip())
    exercicios = _texto_curto(exercicios, 3000)
    if not grupo or not exercicios:
        return jsonify({"error": "informe o grupo e os exercicios (um por linha)"}), 400
    conn = get_db()
    ficha_id = salvar_ficha_treino(conn, grupo, exercicios)
    conn.close()
    return jsonify({"ok": True, "id": ficha_id}), 201

@bp.route("/api/treino/fichas/<int:ficha_id>", methods=["DELETE"])
def apagar_ficha_treino(ficha_id):
    conn = get_db()
    delete_ficha_treino(conn, ficha_id)
    conn.close()
    return jsonify({"ok": True})

@bp.route("/api/treino", methods=["GET"])
def treinos():
    conn = get_db()
    resultado = list_treinos(conn)
    conn.close()
    return jsonify(resultado)

@bp.route("/api/treino", methods=["POST"])
def registrar_treino_rota():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _inteiro_no_intervalo = app._inteiro_no_intervalo
    _marcar_atividade = app._marcar_atividade
    _texto_curto = app._texto_curto
    date = app.date
    body = _corpo_json()
    grupo = _texto_curto(body.get("grupo"), 40)
    nota = _texto_curto(body.get("nota"), 300)
    duracao = body.get("duracao_min")
    if duracao not in (None, ""):
        duracao = _inteiro_no_intervalo(duracao, 1, 600)
        if duracao is None:
            return jsonify({"error": "duracao deve ser de 1 a 600 minutos"}), 400
    else:
        duracao = None
    conn = get_db()
    treino_id = registrar_treino(conn, date.today().isoformat(), grupo, duracao, nota)
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "id": treino_id}), 201
