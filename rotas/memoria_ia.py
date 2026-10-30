"""Blueprint memoria_ia - Grupo D do Laboratorio v4 (2026-10-30): onde guardei e coincidencias.

Rotas dos botoes dos cards (os cards em si nascem no chat):
- GET    /api/guardados            lista o que ele guardou (mais recente primeiro)
- DELETE /api/guardados/<id>       "Tirar da lista" (esquecer um objeto)
- POST   /api/coincidencias/ocultar  "Nao ligo pra isso": esconde aquele tipo de padrao pra sempre
"""

from __future__ import annotations

from flask import Blueprint, jsonify

import coincidencias
import guardados
from rotas._base import app_modulo

bp = Blueprint("memoria_ia", __name__)


@bp.route("/api/guardados", methods=["GET"])
def listar_guardados():
    app = app_modulo()
    if app._modo_visitante_ativo():
        return jsonify({"oculto": True, "itens": []})
    conn = app.get_db()
    try:
        return jsonify({"itens": guardados.listar(conn, 50), "total": guardados.total(conn)})
    finally:
        conn.close()


@bp.route("/api/guardados/<int:guardado_id>", methods=["DELETE"])
def apagar_guardado(guardado_id):
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    conn = app.get_db()
    try:
        if not guardados.apagar(conn, guardado_id):
            return jsonify({"error": "nao achei esse registro"}), 404
        return jsonify({"ok": True})
    finally:
        conn.close()


@bp.route("/api/coincidencias/ocultar", methods=["POST"])
def ocultar_coincidencia():
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    tipo = app._texto_curto(app._corpo_json().get("tipo"), 30)
    conn = app.get_db()
    try:
        if not tipo or not coincidencias.ocultar(conn, tipo):
            return jsonify({"error": "tipo de coincidencia invalido"}), 400
        return jsonify({"ok": True, "tipo": tipo})
    finally:
        conn.close()
