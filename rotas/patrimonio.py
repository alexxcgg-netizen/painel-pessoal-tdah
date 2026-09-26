"""Blueprint patrimonio - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import get_db

bp = Blueprint("patrimonio", __name__)


@bp.route("/api/patrimonio", methods=["GET"])
def patrimonio_rota():
    app = app_modulo()
    _modo_visitante_ativo = app._modo_visitante_ativo
    _patrimonio_consolidado = app._patrimonio_consolidado
    if _modo_visitante_ativo():
        return jsonify(
            {
                "saldo_bancario": 0,
                "fatura_aberta": 0,
                "valor_guardado_metas": 0,
                "patrimonio_total": 0,
                "contas": [],
                "metas": [],
                "oculto": True,
            }
        )
    conn = get_db()
    resultado = _patrimonio_consolidado(conn)
    conn.close()
    return jsonify(resultado)
