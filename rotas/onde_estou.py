"""rotas/onde_estou.py - leva "onde eu estou" (2026-11-04).

`POST /api/localizacao/visita`: o app iOS manda cada visita do iPhone
({lat, lon, precisao, chegada, saida} em ISO 8601; `saida` nula = chegou e ainda esta la).
Maquina-a-maquina: o app nao tem a sessao do PIN fora da WebView, entao autentica pelo token do
widget (`PAINEL_WIDGET_TOKEN`), SO no header `Authorization: Bearer` - localizacao nunca na URL,
nem o token. Sem token configurado / sem / errado = 401. Modo visitante = 403.
A reacao (mensagem de chegada, atraso, push) roda depois da resposta - ver onde_estou.py.
"""

import hmac
from datetime import datetime

from flask import Blueprint, jsonify, request

import db
import onde_estou

bp = Blueprint("onde_estou", __name__)

ROTAS_COM_TOKEN = {"/api/localizacao/visita"}


def _token_no_header_valido() -> bool:
    from rotas.n3a_widget import _token_widget_esperado

    esperado = _token_widget_esperado()
    cabecalho = request.headers.get("Authorization") or ""
    if not esperado or not cabecalho.lower().startswith("bearer "):
        return False
    enviado = cabecalho[len("Bearer "):].strip()
    return bool(enviado) and hmac.compare_digest(enviado.encode("utf-8"), esperado.encode("utf-8"))


@bp.route("/api/localizacao/visita", methods=["POST"])
def receber_visita():
    if not _token_no_header_valido():
        return jsonify({"error": "token invalido"}), 401
    from rotas._base import app_modulo

    recusa = app_modulo()._recusar_no_modo_visitante()
    if recusa:
        return recusa
    agora = datetime.now()
    dados = onde_estou.validar(request.get_json(silent=True), agora)
    if isinstance(dados, str):
        return jsonify({"error": dados}), 400
    conn = db.get_db()
    try:
        visita_id, nova = onde_estou.registrar(conn, dados, agora)
    finally:
        conn.close()
    onde_estou.reagir_depois(visita_id)
    return jsonify({"ok": True, "id": visita_id, "nova": nova})
