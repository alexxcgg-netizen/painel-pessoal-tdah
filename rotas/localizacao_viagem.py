"""rotas/localizacao_viagem.py - GPS mais esperto do iPhone (leva 06/11 "painel mais esperto", frente 3).

Maquina-a-maquina, mesmo token Bearer das visitas (`PAINEL_WIDGET_TOKEN`, SO no header - nunca na URL):

  - `GET /api/localizacao/cercas`: ate 20 `{id, nome, lat, lng, raio_m}` pro app vigiar (CLCircularRegion).
    Entrou/saiu o app manda pro POST /api/localizacao/visita de sempre, com `fonte: "cerca"`.
  - `POST /api/localizacao/posicao` `{lat, lng, velocidade, precisao, em}`: so guarda com viagem em andamento
    ou compromisso de saida no ao vivo; fora disso apaga tudo e responde `acompanhar: false` (o app para).
    Chegou perto do destino da viagem: encerra e apaga o caminho (`chegou: true`).

Logica em viagem_acompanhada.py. Sem token / errado = 401; modo visitante = 403; corpo ruim = 400.
"""

from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

import db
import viagem_acompanhada

bp = Blueprint("localizacao_viagem", __name__)

ROTAS_COM_TOKEN = {"/api/localizacao/cercas", "/api/localizacao/posicao"}


def _token_ok() -> bool:
    from rotas.onde_estou import _token_no_header_valido

    return _token_no_header_valido()


def _agora() -> datetime:
    return datetime.now()


@bp.route("/api/localizacao/cercas", methods=["GET"])
def listar_cercas():
    if not _token_ok():
        return jsonify({"error": "token invalido"}), 401
    agora = _agora()
    try:
        conn = db.get_db()
        try:
            lista = viagem_acompanhada.cercas(conn, agora)
        finally:
            conn.close()
    except Exception:
        current_app.logger.exception("cercas: falhou ao montar")
        return jsonify({"error": "falhou ao montar"}), 500
    return jsonify({"cercas": lista, "gerado_em": agora.replace(microsecond=0).astimezone().isoformat()})


@bp.route("/api/localizacao/posicao", methods=["POST"])
def receber_posicao():
    if not _token_ok():
        return jsonify({"error": "token invalido"}), 401
    from rotas._base import app_modulo

    recusa = app_modulo()._recusar_no_modo_visitante()
    if recusa:
        return recusa
    agora = _agora()
    dados = viagem_acompanhada.validar_posicao(request.get_json(silent=True), agora)
    if isinstance(dados, str):
        return jsonify({"error": dados}), 400
    try:
        conn = db.get_db()
        try:
            resultado = viagem_acompanhada.guardar_posicao(conn, dados, agora)
        finally:
            conn.close()
    except Exception:
        current_app.logger.exception("posicao: falhou ao guardar")
        return jsonify({"error": "falhou ao guardar"}), 500
    return jsonify(resultado)
