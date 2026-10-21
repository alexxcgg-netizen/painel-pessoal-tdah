"""Blueprint treino - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
import treino_vivo
import vida
from db import (
    delete_ficha_treino,
    desfazer_treinos_do_dia_por_grupo,
    get_db,
    get_ficha_treino,
    list_fichas_treino,
    list_treinos,
    marcar_exercicio_sessao,
    registrar_treino,
    salvar_ficha_treino,
    sessao_treino,
    treinos_do_dia_por_grupo,
    upsert_saude_dia,
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


@bp.route("/api/treino/sessoes/<int:sessao_id>/exercicio", methods=["POST"])
def marcar_exercicio(sessao_id):
    """Treino ao vivo (card `treino_agora`): caixinha de um exercicio. O ultimo marcado registra
    o treino do dia; desmarcar depois disso tira o registro."""
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    body = app._corpo_json()
    i, feito = body.get("i"), body.get("feito")
    if not isinstance(i, int) or isinstance(i, bool) or i < 0 or not isinstance(feito, bool):
        return jsonify({"error": "informe i (indice do exercicio) e feito (true/false)"}), 400
    conn = get_db()
    try:
        sessao = sessao_treino(conn, sessao_id)
        ficha = get_ficha_treino(conn, sessao["ficha_id"]) if sessao else None
        if not ficha:
            return jsonify({"error": "treino não encontrado"}), 404
        total = len(treino_vivo.exercicios_da_ficha(ficha["exercicios"]))
        if i >= total:
            return jsonify({"error": "exercício fora da ficha"}), 400
        sessao = marcar_exercicio_sessao(conn, sessao_id, i, feito, total)
        if sessao["concluido_em"]:
            app._marcar_atividade(conn)
            conn.commit()
        duracao = None
        if isinstance(sessao["treino_id"], int):
            t = conn.execute("SELECT duracao_min FROM treinos WHERE id = ?", (sessao["treino_id"],)).fetchone()
            duracao = t["duracao_min"] if t else None
    finally:
        conn.close()
    return jsonify({"ok": True, "feitos": sessao["feitos"], "total": total,
                    "concluido": bool(sessao["concluido_em"]), "duracao_min": duracao})


@bp.route("/api/treino/sessoes/<int:sessao_id>/sono", methods=["POST"])
def sono_do_treino(sessao_id):
    """Treino ao vivo: "Dormiu quanto essa noite?" (1 toque no card `treino_agora`). Grava no
    sono do dia da sessao (o mesmo campo que o Atalho do Saude preenche) pra cruzar com a carga."""
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    horas = app._corpo_json().get("horas")
    if isinstance(horas, bool) or not isinstance(horas, (int, float)) or not 2 <= horas <= 14:
        return jsonify({"error": "informe horas (de 2 a 14)"}), 400
    conn = get_db()
    try:
        sessao = sessao_treino(conn, sessao_id)
        if not sessao:
            return jsonify({"error": "treino não encontrado"}), 404
        upsert_saude_dia(conn, sessao["data"], {"sono_horas": round(float(horas) * 4) / 4})
    finally:
        conn.close()
    return jsonify({"ok": True, "sono_horas": round(float(horas) * 4) / 4})


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
