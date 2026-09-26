"""Blueprint pessoas - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from rotas._base import app_modulo
from db import delete_pessoa, get_db, list_conversas, registrar_conversa

bp = Blueprint("pessoas", __name__)

@bp.route("/api/pessoas", methods=["GET"])
def pessoas():
    app = app_modulo()
    _pessoas_com_status = app._pessoas_com_status
    date = app.date
    conn = get_db()
    resultado = _pessoas_com_status(conn, date.today())
    conn.close()
    return jsonify(resultado)

@bp.route("/api/pessoas", methods=["POST"])
def criar_pessoa_rota():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _inteiro_no_intervalo = app._inteiro_no_intervalo
    _salvar_pessoa = app._salvar_pessoa
    body = _corpo_json()
    nome = (body.get("nome") or "").strip() if isinstance(body.get("nome"), str) else ""
    freq_bruta = body.get("frequencia_dias")
    freq = 14 if freq_bruta in (None, "") else _inteiro_no_intervalo(freq_bruta, 1, 365)
    if not nome or len(nome) > 60:
        return jsonify({"error": "informe o nome (até 60 caracteres)"}), 400
    if freq is None:
        return jsonify({"error": "frequencia deve ser de 1 a 365 dias"}), 400
    conn = get_db()
    pessoa_id, atualizada = _salvar_pessoa(conn, nome, freq)
    conn.close()
    return jsonify({"ok": True, "id": pessoa_id, "atualizada": atualizada}), 200 if atualizada else 201

@bp.route("/api/pessoas/<int:pessoa_id>", methods=["DELETE"])
def apagar_pessoa(pessoa_id):
    conn = get_db()
    delete_pessoa(conn, pessoa_id)
    conn.close()
    return jsonify({"ok": True})

@bp.route("/api/pessoas/<int:pessoa_id>/falei", methods=["POST"])
def falei_com_pessoa(pessoa_id):
    app = app_modulo()
    _corpo_json = app._corpo_json
    _marcar_atividade = app._marcar_atividade
    date = app.date
    sobre_bruto = _corpo_json().get("sobre")
    sobre = sobre_bruto.strip()[:300] if isinstance(sobre_bruto, str) and sobre_bruto.strip() else None
    conn = get_db()
    pessoa = conn.execute("SELECT * FROM pessoas WHERE id = ?", (pessoa_id,)).fetchone()
    if not pessoa:
        conn.close()
        return jsonify({"error": "pessoa não encontrada"}), 404
    registrar_conversa(conn, pessoa_id, pessoa["nome"], sobre, date.today().isoformat())
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@bp.route("/api/conversas", methods=["GET"])
def conversas():
    pessoa_id = request.args.get("pessoa_id", type=int)
    conn = get_db()
    resultado = list_conversas(conn, pessoa_id=pessoa_id, limite=30)
    conn.close()
    return jsonify(resultado)
