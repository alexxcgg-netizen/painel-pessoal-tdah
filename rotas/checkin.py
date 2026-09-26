"""Blueprint checkin - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import get_checkin, get_db, salvar_checkin
import vida

bp = Blueprint("checkin", __name__)

@bp.route("/api/checkin/hoje", methods=["GET"])
def checkin_hoje():
    app = app_modulo()
    _checkin_com_rotulos = app._checkin_com_rotulos
    date = app.date
    conn = get_db()
    checkin = get_checkin(conn, date.today().isoformat())
    conn.close()
    return jsonify({"checkin": _checkin_com_rotulos(checkin)})

@bp.route("/api/checkin", methods=["POST"])
def salvar_checkin_rota():
    app = app_modulo()
    _checkin_com_rotulos = app._checkin_com_rotulos
    _corpo_json = app._corpo_json
    _marcar_atividade = app._marcar_atividade
    date = app.date
    body = _corpo_json()
    campos = {c: vida.valor_checkin(body.get(c)) for c in vida.CAMPOS_CHECKIN if c in body}
    campos = {c: v for c, v in campos.items() if v is not None}
    if not campos:
        return jsonify({"error": "mande energia, sono ou humor como 'ruim', 'ok' ou 'bom'"}), 400
    conn = get_db()
    checkin = salvar_checkin(conn, date.today().isoformat(), campos)
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"checkin": _checkin_com_rotulos(checkin)})
