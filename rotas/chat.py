"""Blueprint chat - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

import json
import queue
import threading

from flask import Blueprint, Response, copy_current_request_context, jsonify, request

from rotas._base import app_modulo
from db import cards_de_mensagem_chat, get_db, list_chat_mensagens
import cards
import claude_client
import db

bp = Blueprint("chat", __name__)

@bp.route("/api/chat", methods=["POST"])
def chat():
    app = app_modulo()
    MSG_TEXTO_LONGO = app.MSG_TEXTO_LONGO
    TAMANHO_MAX_TEXTO_CHAT = app.TAMANHO_MAX_TEXTO_CHAT
    TETO_IA_MSG = app.TETO_IA_MSG
    _corpo_json = app._corpo_json
    _processar_mensagem_chat = app._processar_mensagem_chat
    _resposta_contrato = app._resposta_contrato
    _texto_seguro = app._texto_seguro
    body = _corpo_json()
    texto = _texto_seguro(body.get("mensagem"))
    if not texto:
        return jsonify({"error": "mensagem vazia"}), 400
    if len(texto) > TAMANHO_MAX_TEXTO_CHAT:
        return jsonify({"error": MSG_TEXTO_LONGO}), 400

    conn = get_db()
    detalhes: dict = {}
    resposta, acoes, erro = _processar_mensagem_chat(
        conn, texto, detalhes, modo_voz=body.get("modo") == "voz", local_gps=body.get("local"),
        origem_audio=body.get("audio") is True,
    )
    conn.close()
    if erro:
        return jsonify({"error": erro}), 402 if erro == TETO_IA_MSG else 502
    # `resposta`/`acoes` = campos legados (frontend antigo em cache do PWA);
    # cards/resumo_texto/passos = contrato da Fase 6 (docs/CARDS.md).
    corpo = {"resposta": resposta, "acoes": acoes}
    corpo.update(detalhes or cards.envelope([], resposta, []))
    return jsonify(_resposta_contrato(corpo))

ESPERA_MAX_STREAM_S = 180  # sem nenhum sinal do trabalhador por 3 min = desiste


def _evento_sse(evento: str, dado) -> str:
    return f"event: {evento}\ndata: {json.dumps(dado, ensure_ascii=False)}\n\n"


@bp.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """Mesmo /api/chat, mas a resposta chega AO VIVO (2026-10-13 - "parece IA esperando o bloco
    inteiro"): text/event-stream com `texto` (pedaco novo), `recomeca` (o que apareceu nao vale
    mais - a IA foi usar ferramenta) e no fim `fim` com o MESMO corpo do /api/chat (cards,
    resumo_texto...) ou `erro` {error, status}. O pipeline roda numa thread (conexao propria do
    SQLite), a resposta HTTP so le a fila - o waitress manda cada evento na hora (send_bytes=1)."""
    app = app_modulo()
    body = app._corpo_json()
    texto = app._texto_seguro(body.get("mensagem"))
    if not texto:
        return jsonify({"error": "mensagem vazia"}), 400
    if len(texto) > app.TAMANHO_MAX_TEXTO_CHAT:
        return jsonify({"error": app.MSG_TEXTO_LONGO}), 400

    fila: queue.Queue = queue.Queue()

    @copy_current_request_context
    def trabalhar():
        conn = get_db()
        try:
            detalhes: dict = {}
            with claude_client.ao_texto(lambda evento, dado: fila.put((evento, dado))):
                resposta, acoes, erro = app._processar_mensagem_chat(
                    conn, texto, detalhes, modo_voz=body.get("modo") == "voz",
                    local_gps=body.get("local"), origem_audio=body.get("audio") is True,
                )
            if erro:
                fila.put(("erro", {"error": erro, "status": 402 if erro == app.TETO_IA_MSG else 502}))
                return
            corpo = {"resposta": resposta, "acoes": acoes}
            corpo.update(detalhes or cards.envelope([], resposta, []))
            fila.put(("fim", app._resposta_contrato(corpo)))
        except Exception:  # noqa: BLE001 - qualquer quebra vira evento de erro, nunca silencio
            app.app.logger.exception("chat stream: pipeline quebrou")
            fila.put(("erro", {"error": app.CLAUDE_ERROR_MSG, "status": 500}))
        finally:
            conn.close()

    threading.Thread(target=trabalhar, name="chat-stream", daemon=True).start()

    def gerar():
        yield ": aberto\n\n"  # abre o stream na hora (a tela ja sabe que chegou no servidor)
        while True:
            try:
                evento, dado = fila.get(timeout=ESPERA_MAX_STREAM_S)
            except queue.Empty:
                yield _evento_sse("erro", {"error": app.CLAUDE_ERROR_MSG, "status": 504})
                return
            yield _evento_sse(evento, dado)
            if evento in ("fim", "erro"):
                return

    return Response(
        gerar(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


MIMES_FOTO = {"image/jpeg", "image/png", "image/webp", "image/heic"}
TAMANHO_MAX_FOTO = 8 * 1024 * 1024


def _fmt_kcal(v) -> str:
    return f"{round(v):,}".replace(",", ".")


@bp.route("/api/chat/foto", methods=["POST"])
def chat_foto():
    """Foto no chat (2026-10-13): hoje so prato de comida - a IA estima itens/gramas/macros, a
    refeicao e registrada (card `refeicao` com Desfazer) e soma no dia contra a meta. A foto nao
    fica guardada."""
    import refeicoes
    from ia import core
    from ia.funcoes import visao

    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    arquivo = request.files.get("imagem")
    if arquivo is None:
        return jsonify({"error": "faltou a foto"}), 400
    mime = (arquivo.mimetype or "").split(";")[0].strip().lower()
    if mime not in MIMES_FOTO:
        return jsonify({"error": "formato de foto não suportado (use jpeg, png, webp ou heic)"}), 400
    imagem = arquivo.read(TAMANHO_MAX_FOTO + 1)
    if not imagem:
        return jsonify({"error": "foto vazia"}), 400
    if len(imagem) > TAMANHO_MAX_FOTO:
        return jsonify({"error": "foto grande demais"}), 413
    texto = app._texto_seguro(request.form.get("texto")) or ""
    texto = texto[:500]
    agora = app._agora_brasilia().replace(tzinfo=None, second=0, microsecond=0)
    try:
        dados, _uso = visao.analisar_prato(imagem, mime, f"{agora:%H:%M}", texto)
    except (core.FalhaChamadaIA, ValueError):
        app.app.logger.exception("chat/foto: analise do prato falhou")
        return jsonify({"error": "não consegui analisar a foto agora - tenta de novo"}), 502

    conn = get_db()
    try:
        texto_usuario = "📷 Foto do prato" + (f" - {texto}" if texto else "")
        itens = refeicoes.itens_limpos((dados or {}).get("itens"))
        if not (dados or {}).get("e_comida") or not itens:
            descricao = str((dados or {}).get("descricao") or "").strip()
            resposta = ("Não vi comida nessa foto" + (f" ({descricao[:160]})" if descricao else "")
                        + ". Por enquanto eu analiso foto de prato ou lanche.")
            db.salvar_mensagem_chat(conn, "user", texto_usuario)
            db.salvar_mensagem_chat(conn, "assistant", resposta)
            corpo = {"resposta": resposta, "acoes": []}
            corpo.update(cards.envelope([], resposta, []))
            return jsonify(app._resposta_contrato(corpo))

        id_ = refeicoes.registrar(conn, itens, dados.get("refeicao"), agora)
        dica = str(dados.get("dica") or "").strip()[:200]
        confianca = dados.get("confianca") if isinstance(dados.get("confianca"), (int, float)) else None
        card = refeicoes.dados_card(conn, id_)
        tot, dia, meta = card["total"], card["dia"], card["meta"]
        # leva 22/10 (Refeicao pela proteina): so proteina, sem caloria nem culpa - os outros macros seguem
        # gravados e aparecem pequenos no card
        resposta = f"Esse {card['refeicao']} tem uns {round(tot['proteina_g'])} g de proteína."
        if meta:
            falta = max(0, meta["proteina_g"] - round(dia["proteina_g"]))
            resposta += f" Falta {falta} g pra tua meta de hoje." if falta else " Meta de proteína de hoje batida."
        if dica:
            resposta += f" {dica}"
        efeito = {"entidade": "refeicao", "id": id_, "dica": dica, "confianca": confianca}
        envelope = cards.montar_resposta(conn, [efeito], resposta, [], app._criar_token_desfazer(conn))
        db.salvar_mensagem_chat(conn, "user", texto_usuario)
        db.salvar_mensagem_chat(conn, "assistant", resposta, envelope["cards"])
        app._marcar_atividade(conn)
    finally:
        conn.close()
    corpo = {"resposta": resposta, "acoes": ["analisar_prato"]}
    corpo.update(envelope)
    return jsonify(app._resposta_contrato(corpo))


@bp.route("/api/chat/historico", methods=["GET"])
def chat_historico():
    app = app_modulo()
    _modo_visitante_ativo = app._modo_visitante_ativo
    conn = get_db()
    mensagens = list(reversed(list_chat_mensagens(conn, limit=30)))
    conn.close()
    visitante = _modo_visitante_ativo()
    for m in mensagens:
        m["cards"] = cards_de_mensagem_chat(m)
    # US-E5: card cujo Desfazer ja foi usado volta marcado como desfeito
    # (campo aditivo `desfeito` no card, docs/CARDS.md).
    tokens = [
        a.get("token")
        for m in mensagens
        for c in m["cards"]
        for a in (c.get("actions") or [])
        if isinstance(a, dict) and a.get("tipo") == "desfazer"
    ]
    conn = get_db()
    desfeitos = db.tokens_desfeitos(conn, tokens)
    for m in mensagens:
        cards.acertar_plano_escolhido(conn, m["cards"])  # trocou pro plano B na pilula
        cards.acertar_treino_agora(conn, m["cards"])  # caixinhas marcadas / carga trocada depois
    conn.close()
    for m in mensagens:
        for c in m["cards"]:
            if any(isinstance(a, dict) and a.get("token") in desfeitos for a in (c.get("actions") or [])):
                c["desfeito"] = True
        # Fase 6: os cards da resposta ficam gravados junto da mensagem
        # (cards_json, criptografado em repouso como o resto do dado
        # financeiro) - recarregar a pagina nao perde os cards.
        m.pop("cards_json", None)
        if visitante and m["papel"] == "assistant":
            m["cards"] = cards.mascarar_cards(m["cards"])
            m["texto"] = cards.ocultar_valores_texto(m["texto"])
    return jsonify(mensagens)
