"""Blueprint refeicoes - "corrige" do card `proteina` (Refeicao pela proteina, leva 22/10). Logica em
refeicoes.py; a foto em si continua em rotas/chat.py (/api/chat/foto)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import get_db
import refeicoes

bp = Blueprint("refeicoes", __name__)


@bp.route("/api/refeicoes/<int:refeicao_id>/proteina", methods=["POST"])
def corrigir_proteina(refeicao_id):
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    g = app._corpo_json().get("proteina_g")
    if isinstance(g, bool) or not isinstance(g, (int, float)) or not 0 <= g <= 300:
        return jsonify({"error": "proteína tem que ser um número de 0 a 300"}), 400
    conn = get_db()
    try:
        d = refeicoes.corrigir_proteina(conn, refeicao_id, g)
    finally:
        conn.close()
    if d is None:
        return jsonify({"error": "refeição não encontrada"}), 404
    return jsonify({"ok": True, "prato_g": d["prato_g"], "dia_g": d["dia_g"], "meta_g": d["meta_g"]})
