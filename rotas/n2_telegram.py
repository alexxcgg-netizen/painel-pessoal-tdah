"""Fase 7, faixa N2 (captura por Telegram) - webhook novo.

POST /api/telegram/webhook: rota maquina-a-maquina (token proprio, ver
ROTAS_COM_TOKEN abaixo) que o Telegram chama a cada mensagem nova pro bot
(setWebhook - ver docs/telegram-captura.md). Valida o segredo do webhook e a
lista de permissao de chat, garante idempotencia por update_id (o Telegram
reenvia update que nao recebeu 200 a tempo) e delega o processamento de
verdade pra telegram_captura.processar_atualizacao - este arquivo so faz a
parte de HTTP/seguranca/infra, nunca reimplementa classificacao de captura,
extracao de nota fiscal ou resumo de link (essas continuam so em
claude_client.py / app._executar_captura / app._salvar_link).

Convencao de rota-por-Blueprint (docs/agentes/fase7-regras-faixa.md, Etapa
0): helpers de app.py sempre via `app_modulo()` DENTRO da funcao da rota
(nunca `import app` no topo - import circular, ver rotas/_base.py)."""

from __future__ import annotations

import hmac
import os

from flask import Blueprint, jsonify, request

import claude_client
import db
import telegram_captura
from rotas._base import app_modulo

bp = Blueprint("n2_telegram", __name__)

# Rota maquina-a-maquina - o proprio Telegram chama, sem sessao/PIN. A rota
# e' responsavel por checar o token (o header secreto abaixo) na primeira
# linha, senao fica aberta pra internet (ver rotas/__init__.py).
ROTAS_COM_TOKEN = {"/api/telegram/webhook"}

CABECALHO_SECRETO = "X-Telegram-Bot-Api-Secret-Token"

# Retencao da idempotencia: so precisa cobrir um reenvio do Telegram (site
# dormindo/acordando), nunca dias - mesmo espirito de
# app._gravar_resposta_capture (capture_idempotency, 7 dias), aqui um pouco
# mais folgado porque o Telegram pode retentar por mais tempo que a fila
# offline do navegador.
RETENCAO_IDEMPOTENCIA_DIAS = 30

_SQL_GARANTIR_TABELA = """
CREATE TABLE IF NOT EXISTS telegram_updates_processados (
    update_id INTEGER PRIMARY KEY,
    processado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_telegram_updates_processado_em
    ON telegram_updates_processados(processado_em);
"""


def _garantir_tabela(conn) -> None:
    """Fallback idempotente (CREATE TABLE/INDEX IF NOT EXISTS), redundante
    com migracoes/202609241310_n2_telegram.sql (ja aplicada pelo runner de
    migracoes/ - Etapa 0 - em todo banco que passar por db.init_db()) -
    mantido por seguranca pra um banco que, por algum motivo, ainda nao
    rodou init_db() com essa migracao (ex: teste isolado que pula
    db.init_db()). Mesmo schema dos dois lados, nunca devem divergir.
    Seguro chamar em toda requisicao, igual ia/migracao_uso_ia.garantir_tabela."""
    conn.executescript(_SQL_GARANTIR_TABELA)
    conn.commit()


def _ja_processado_ou_marca(conn, update_id: int) -> bool:
    """True se `update_id` JA tinha sido processado (update duplicado,
    Telegram reenviando) - senao marca como processado agora (dentro da
    mesma transacao) e devolve False. INSERT direto (não INSERT OR IGNORE +
    checar rowcount porque sqlite3 as vezes reporta rowcount=-1 pra
    INSERT/IGNORE): tenta inserir, IntegrityError == ja existia."""
    try:
        conn.execute("INSERT INTO telegram_updates_processados (update_id) VALUES (?)", (update_id,))
        conn.execute(
            "DELETE FROM telegram_updates_processados WHERE processado_em < datetime('now', ?)",
            (f"-{RETENCAO_IDEMPOTENCIA_DIAS} days",),
        )
        conn.commit()
        return False
    except db.sqlite3.IntegrityError:
        conn.rollback()
        return True


def _secret_valido(recebido: str | None) -> bool:
    esperado = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
    if not esperado or not recebido:
        return False
    return hmac.compare_digest(recebido, esperado)


def _executar_captura_dict(texto: str, clarificacao: str) -> tuple[dict, int]:
    """Adapta app._executar_captura (devolve (Response, status)) pro
    contrato de telegram_captura.processar_atualizacao (dict, status) -
    fonte unica da classificacao continua sendo _executar_captura, aqui so
    desembrulha o Response do Flask."""
    resposta, status = app_modulo()._executar_captura(texto, clarificacao)
    return resposta.get_json(), status


def _salvar_link_dict(conn, url: str) -> dict:
    return app_modulo()._salvar_link(conn, url)


def _extrair_nota_fiscal(image_bytes: bytes, media_type: str) -> tuple[dict | None, str | None]:
    """Envolve claude_client.extrair_nota_fiscal_foto com o MESMO controle
    de teto/lock/log de uso que /api/extrair-nota-fiscal (app.py) ja usa -
    nunca reimplementa esse controle, so reusa via app_modulo()."""
    app = app_modulo()
    conn = db.get_db()
    try:
        with app._TETO_IA_LOCK:
            # C1: teto unico do app (ia.teto via app._teto_ia_estourado).
            if app._teto_ia_estourado("extrair_nota_fiscal_foto"):
                return None, app.TETO_IA_MSG
            resultado, erro = app._call_claude(claude_client.extrair_nota_fiscal_foto, image_bytes, media_type)
            if erro:
                return None, "nao consegui ler a foto agora"
            dados, usage = resultado
            app._log_usage(conn, usage, "nota_fiscal")
            conn.commit()
        return dados, None
    finally:
        conn.close()


@bp.route("/api/telegram/webhook", methods=["POST"])
def webhook():
    if not _secret_valido(request.headers.get(CABECALHO_SECRETO)):
        return jsonify({"error": "token invalido"}), 401
    # C1: com um bot so, webhook e polling nunca rodam juntos (409 no
    # Telegram). Webhook fora do modo -> 503, o Telegram guarda e reenvia o
    # update (aparece em getWebhookInfo.last_error_message) - nada se perde.
    if not telegram_captura.modo_telegram()["webhook"]:
        return jsonify({"error": "webhook desligado (TELEGRAM_MODO)"}), 503

    corpo = request.get_json(silent=True)
    if not isinstance(corpo, dict):
        return jsonify({"error": "corpo invalido"}), 400

    update_id = corpo.get("update_id")
    if not isinstance(update_id, int):
        return jsonify({"error": "update_id ausente"}), 400

    # Lista de permissao: qualquer chat diferente do configurado e' ignorado
    # em SILENCIO (200 sem nenhuma acao) - nunca revela que o bot existe/faz
    # algo pra quem nao e' o Alex, mesmo que descubra o token do bot.
    chat_id = telegram_captura.extrair_chat_id(corpo)
    chat_permitido = os.environ.get("TELEGRAM_CHAT_ID_PERMITIDO", "")
    if not chat_permitido or chat_id != chat_permitido:
        return jsonify({"ok": True}), 200

    conn = db.get_db()
    try:
        _garantir_tabela(conn)
        if _ja_processado_ou_marca(conn, update_id):
            return jsonify({"ok": True, "duplicado": True}), 200
    finally:
        conn.close()

    conn = db.get_db()
    try:
        telegram_captura.processar_atualizacao(
            corpo,
            conn=conn,
            executar_captura=_executar_captura_dict,
            salvar_link=_salvar_link_dict,
            extrair_nota_fiscal=_extrair_nota_fiscal,
            url_app=os.environ.get("APP_URL_PUBLICA", ""),
        )
    finally:
        conn.close()
    return jsonify({"ok": True}), 200
