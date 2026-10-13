"""Blueprint voz - voz natural (ElevenLabs) so pra frases curtas.

Autenticacao: global (`_verificar_autenticacao` em app.py) - nenhuma excecao.
Sem chave / limite do mes / erro: POST /api/voz/falar responde 204 e o front
cai na voz do iPhone.
"""

from __future__ import annotations

import json

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


# 2 min de audio do iPhone (mp4/aac) fica bem abaixo disso; o Groq aceita ate 25MB
TAMANHO_MAX_AUDIO = 15 * 1024 * 1024
_MIMES_AUDIO = ("audio/mp4", "audio/webm", "audio/ogg", "audio/mpeg", "audio/wav", "audio/x-m4a", "audio/aac")


def _trechos_voz(bruto) -> list | None:
    """'[[0.4, 2.1], [2.6, 5]]' -> lista validada (no maximo 200 pares, 0-600 s). Invalido = None
    (sem filtro, como antes)."""
    if not bruto:
        return None
    try:
        dados = json.loads(bruto)
    except ValueError:
        return None
    if not isinstance(dados, list):
        return None
    trechos = []
    for par in dados[:200]:
        if (isinstance(par, list) and len(par) == 2 and all(isinstance(v, (int, float)) for v in par)
                and 0 <= par[0] <= par[1] <= 600):
            trechos.append((float(par[0]), float(par[1])))
    return trechos or None


@bp.route("/api/voz/transcrever", methods=["POST"])
def voz_transcrever():
    """Microfone do chat: o front grava o audio inteiro (MediaRecorder) e manda
    aqui; transcreve com o mesmo Whisper/Groq do Telegram. Nao executa nada -
    so devolve o texto pro campo do chat."""
    import telegram_captura

    arquivo = request.files.get("audio")
    if arquivo is None:
        return jsonify({"erro": "faltou o audio"}), 400
    mime = (arquivo.mimetype or "").split(";")[0].strip().lower()
    if mime not in _MIMES_AUDIO:
        return jsonify({"erro": "formato de audio nao suportado"}), 400
    audio = arquivo.read(TAMANHO_MAX_AUDIO + 1)
    if not audio:
        return jsonify({"erro": "audio vazio"}), 400
    if len(audio) > TAMANHO_MAX_AUDIO:
        return jsonify({"erro": "audio longo demais"}), 413
    try:
        duracao = int(float(request.form.get("duracao") or 0))
    except ValueError:
        duracao = 0

    def _segundos(campo):
        try:
            v = float(request.form.get(campo))
        except (TypeError, ValueError):
            return None
        return v if 0 <= v <= 600 else None

    try:
        # onde a voz comecou/terminou (o app mede): o que o Whisper "ouvir" fora disso e inventado;
        # trechos_voz = quando a voz DELE (perto do microfone) estava ativa - o resto e fundo
        texto = telegram_captura.transcrever(
            audio, mime, duracao_segundos=duracao, fala_desde=_segundos("fala_desde"), fala_ate=_segundos("fala_ate"),
            trechos_voz=_trechos_voz(request.form.get("trechos_voz")),
        )
    except telegram_captura.ErroCaptura as e:
        return jsonify({"erro": str(e), "error": str(e)}), 502
    if request.form.get("limpar") != "1" or not texto:
        return jsonify({"texto": texto})
    # 2026-10-12: microfone do chat manda direto - antes, uma IA rapida reescreve como ele QUIS
    # dizer (autocorrecao, muleta, nome mal ouvido). Falhou = vai o texto cru.
    from ia.funcoes import fala

    conn = get_db()
    try:
        vocabulario = app_modulo()._vocabulario_do_alex(conn)
    finally:
        conn.close()
    limpo, limpou = fala.limpar(texto, vocabulario)
    return jsonify({"texto": limpo, "bruto": texto, "limpo": limpou})


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
