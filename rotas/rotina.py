"""Blueprint rotina - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from rotas._base import app_modulo
from db import alternar_rotina_item, create_rotina_item, delete_rotina_item, get_db
import vida

bp = Blueprint("rotina", __name__)

@bp.route("/api/rotina", methods=["GET"])
def rotina():
    app = app_modulo()
    _rotina_do_dia = app._rotina_do_dia
    datetime = app.datetime
    momento = request.args.get("momento") or vida.momento_rotina(datetime.now())
    if momento not in vida.ITENS_ROTINA_PADRAO:
        return jsonify({"error": "momento deve ser 'manha' ou 'noite'"}), 400
    conn = get_db()
    resultado = _rotina_do_dia(conn, momento, vida.dia_da_rotina(momento, datetime.now()).isoformat())
    conn.close()
    return jsonify(resultado)

@bp.route("/api/rotina/<int:item_id>/alternar", methods=["POST"])
def alternar_rotina(item_id):
    app = app_modulo()
    _marcar_atividade = app._marcar_atividade
    datetime = app.datetime
    conn = get_db()
    existe = conn.execute("SELECT momento FROM rotina_itens WHERE id = ? AND ativo = 1", (item_id,)).fetchone()
    if not existe:
        conn.close()
        return jsonify({"error": "item não encontrado"}), 404
    dia = vida.dia_da_rotina(existe["momento"], datetime.now())
    feito = alternar_rotina_item(conn, dia.isoformat(), item_id)
    if feito:
        _marcar_atividade(conn)
        conn.commit()
    conn.close()
    return jsonify({"feito": feito})

@bp.route("/api/rotina/itens", methods=["POST"])
def criar_item_rotina():
    app = app_modulo()
    _corpo_json = app._corpo_json
    body = _corpo_json()
    momento = (body.get("momento") or "").strip()
    texto = (body.get("texto") or "").strip()
    if momento not in vida.ITENS_ROTINA_PADRAO:
        return jsonify({"error": "momento deve ser 'manha' ou 'noite'"}), 400
    if not texto or len(texto) > 120:
        return jsonify({"error": "escreva o item (até 120 caracteres)"}), 400
    conn = get_db()
    item_id = create_rotina_item(conn, momento, texto)
    conn.close()
    return jsonify({"ok": True, "id": item_id}), 201

@bp.route("/api/rotina/itens/<int:item_id>", methods=["DELETE"])
def apagar_item_rotina(item_id):
    conn = get_db()
    delete_rotina_item(conn, item_id)
    conn.close()
    return jsonify({"ok": True})
