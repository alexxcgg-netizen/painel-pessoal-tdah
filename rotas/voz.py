"""Blueprint voz - voz natural (ElevenLabs) so pra frases curtas.

Autenticacao: global (`_verificar_autenticacao` em app.py) - nenhuma excecao.
Sem chave / limite do mes / erro: POST /api/voz/falar responde 204 e o front
cai na voz do iPhone.
"""

from __future__ import annotations

from flask import Blueprint, Response, jsonify, request

from rotas._base import app_modulo
from db import get_db
import voz_premium

bp = Blueprint("voz", __name__)


@bp.route("/api/voz/frase", methods=["GET"])
def voz_frase():
    momento = request.args.get("momento", "")
    if momento not in ("manha", "noite"):
        return jsonify({"erro": "momento deve ser 'manha' ou 'noite'"}), 400
    app = app_modulo()
    conn = get_db()
    try:
        if momento == "manha":
            app.materializar_tarefas_recorrentes(conn)
            texto = voz_premium.frase_curta_manha(conn)
        else:
            texto = voz_premium.frase_curta_noite(conn)
    finally:
        conn.close()
    return jsonify({"texto": texto, "premium": voz_premium.configurado()})


@bp.route("/api/voz/falar", methods=["POST"])
def voz_falar():
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return jsonify({"erro": "JSON invalido"}), 400
    texto = dados.get("texto")
    if not isinstance(texto, str) or not texto.strip() or len(texto) > voz_premium.MAX_CARACTERES:
        return jsonify({"erro": "texto ausente, invalido ou longo demais"}), 400
    conn = get_db()
    try:
        audio = voz_premium.sintetizar(conn, texto)
    except Exception:
        audio = None
    finally:
        conn.close()
    if not audio:
        return Response(status=204)
    return Response(audio, status=200, mimetype="audio/mpeg")


@bp.route("/api/voz/uso", methods=["GET"])
def voz_uso():
    conn = get_db()
    try:
        mes = voz_premium.mes_atual()
        usado = voz_premium.uso_do_mes(conn, mes)
    finally:
        conn.close()
    return jsonify(
        {
            "configurado": voz_premium.configurado(),
            "mes": mes,
            "caracteres": usado,
            "limite": voz_premium.limite_mes(),
        }
    )
