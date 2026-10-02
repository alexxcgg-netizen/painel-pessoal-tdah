"""Blueprint treino - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
import vida
from db import (
    delete_ficha_treino,
    desfazer_treinos_do_dia_por_grupo,
    get_db,
    get_ficha_treino,
    list_fichas_treino,
    list_treinos,
    registrar_treino,
    salvar_ficha_treino,
    treinos_do_dia_por_grupo,
    utc_para_hora_local,
)

bp = Blueprint("treino", __name__)

@bp.route("/api/treino/fichas", methods=["GET"])
def fichas_treino():
    app = app_modulo()
    conn = get_db()
    resultado = list_fichas_treino(conn)
    # R4: "Feito hoje" por ficha (treino do dia com o mesmo grupo). Modo visitante: oculto.
    feitos = None if app._modo_visitante_ativo() else treinos_do_dia_por_grupo(conn, app.date.today().isoformat())
    conn.close()
    for f in resultado:
        if feitos is None:
            f["feito_hoje"] = None
            f["feito_as"] = None
        else:
            criado = feitos.get(vida.normalizar_nome(f["grupo"]))
            f["feito_hoje"] = criado is not None
            f["feito_as"] = utc_para_hora_local(criado) if criado else None
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


@bp.route("/api/treino/fichas/<int:ficha_id>/feito", methods=["POST"])
def marcar_ficha_feita(ficha_id):
    """R4: "Feito hoje" - registra um treino simples de hoje com o grupo da ficha
    (idempotente: se o dia ja tem treino desse grupo, nao duplica)."""
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    hoje = app.date.today().isoformat()
    conn = get_db()
    try:
        ficha = get_ficha_treino(conn, ficha_id)
        if not ficha:
            return jsonify({"error": "ficha não encontrada"}), 404
        chave = vida.normalizar_nome(ficha["grupo"])
        ja = treinos_do_dia_por_grupo(conn, hoje).get(chave)
        criou = ja is None
        if criou:
            registrar_treino(conn, hoje, ficha["grupo"], None, None, origem="botao")
            app._marcar_atividade(conn)
            conn.commit()
            ja = treinos_do_dia_por_grupo(conn, hoje).get(chave)
    finally:
        conn.close()
    return jsonify({"ok": True, "feito": True, "hora": utc_para_hora_local(ja)}), (201 if criou else 200)


@bp.route("/api/treino/fichas/<int:ficha_id>/feito", methods=["DELETE"])
def desfazer_ficha_feita(ficha_id):
    """R4: desfaz o "Feito hoje" da ficha (idempotente). So apaga o que o botao marcou;
    treino registrado pelo chat ou pela tela de treinos fica."""
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    conn = get_db()
    try:
        ficha = get_ficha_treino(conn, ficha_id)
        if not ficha:
            return jsonify({"error": "ficha não encontrada"}), 404
        desfazer_treinos_do_dia_por_grupo(conn, app.date.today().isoformat(), ficha["grupo"])
    finally:
        conn.close()
    return jsonify({"ok": True, "feito": False})
