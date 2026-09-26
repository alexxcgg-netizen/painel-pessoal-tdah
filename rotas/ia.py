"""Blueprint ia - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import definir_teto_mensal_ia, get_db, resumo_custo_api
import math

bp = Blueprint("ia", __name__)

@bp.route("/api/ia/custo", methods=["GET"])
def ia_custo():
    """Resumo do gasto com a API da Anthropic pro card financeiro (US-A5) -
    mes atual e ultimos 30 dias, mais teto/fracao/estourado (US-A6). Ver
    db.resumo_custo_api."""
    conn = get_db()
    resumo = resumo_custo_api(conn)
    conn.close()
    return jsonify(resumo)

@bp.route("/api/ia/teto", methods=["POST"])
def ia_definir_teto():
    """Define (ou remove, com null/0) o teto mensal de gasto com IA (US-A6) -
    editavel via UI no card financeiro."""
    app = app_modulo()
    _corpo_json = app._corpo_json
    body = _corpo_json()
    teto = body.get("teto_mensal_usd")
    if teto is not None:
        if isinstance(teto, bool) or not isinstance(teto, (int, float)) or not math.isfinite(teto):
            return jsonify({"error": "teto_mensal_usd precisa ser um numero"}), 400
        if teto < 0:
            return jsonify({"error": "teto_mensal_usd nao pode ser negativo"}), 400
    conn = get_db()
    definir_teto_mensal_ia(conn, teto)
    resumo = resumo_custo_api(conn)
    conn.close()
    return jsonify(resumo)
