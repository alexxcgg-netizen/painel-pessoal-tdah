"""Rotas da leva Lab v4, Grupo C (avisos e manha) - 30/10/2026. Ver docs/briefings/2026-10-30-lab-v4-avisos.md.

  GET  /api/badge                         numero do icone do app (badge.py)
  GET|POST /api/atalho/bom-dia            Atalho "alarme parado" (token): grava o sono, devolve fala + linhas (bom_dia.py)
  GET  /api/atalho/bom-dia/audio          mp3 da fala de hoje (ElevenLabs); 204 sem chave/limite (o Atalho usa a voz do iPhone)
  GET|POST /api/atalho/carro              Atalho "Bluetooth/CarPlay conecta" (token): fala + Waze (carro.py)
  POST /api/atalho/gatilho                Atalho qualquer: {"evento": "sentar_estudar"|...} dispara os combinados (se_entao.py)
  GET  /api/manha/estado?ids=1,2,3        status dos cartoes (card antigo no historico sincroniza)
  POST /api/manha/<id>/resolver|depois|esquecer     os 3 botoes dos cartoes da manha (manha.py)
  POST /api/manha/preparar                monta os cartoes de hoje agora (o tick ja faz sozinho depois das 4h)
  GET|POST /api/se-entao, POST /api/se-entao/<id>/desativar|testar     combinados "quando X, eu Y" (se_entao.py)
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from flask import Blueprint, Response, jsonify, request

import badge
import bom_dia
import carro
import db
import manha
import se_entao
from rotas._base import app_modulo

bp = Blueprint("avisos_manha", __name__)
# maquina-a-maquina (o Atalho do iPhone nao guarda cookie): cada rota confere o token dos Atalhos sozinha
ROTAS_COM_TOKEN = {"/api/atalho/bom-dia", "/api/atalho/bom-dia/audio", "/api/atalho/carro", "/api/atalho/gatilho"}

CHAVE_BOM_DIA = "bom_dia_ultimo"
CHAVE_CARRO = "carro_ultimo"
_TRES_HORAS = timedelta(hours=3)  # a mesma fala do carro nao vira card de novo antes disso


def _agora(app) -> datetime:
    return app._agora_brasilia().replace(tzinfo=None)


def _entrada(app) -> dict:
    """GET (query) ou POST (JSON): o Atalhos manda os dois jeitos."""
    corpo = {}
    if request.method == "POST":
        j = request.get_json(silent=True)
        corpo = dict(j) if isinstance(j, dict) else {}
    for k, v in request.args.items():
        corpo.setdefault(k, v)
    return corpo


def _negado(app):
    if not app._token_atalho_valido(obrigatorio=True):
        return jsonify({"error": "token inválido"}), 401
    return None


# ------------------------------------------------------------------ badge


@bp.route("/api/badge", methods=["GET"])
def numero_do_icone():
    app = app_modulo()
    conn = db.get_db()
    try:
        return jsonify({"n": badge.contagem(conn, app._agora_brasilia().date())})
    finally:
        conn.close()


# ------------------------------------------------------------------ bom dia


def _voos_do_dia(conn, hoje):
    return [dict(r) for r in conn.execute(
        "SELECT origem, hora FROM voos WHERE data = ? AND hora IS NOT NULL AND horas IS NULL "
        "AND COALESCE(tipo, '') != 'simulador' ORDER BY hora", (hoje.isoformat(),)).fetchall()]


def _clima_da_cidade(cidade):
    import clima

    if not cidade:
        return None
    local = clima.geocodificar_cidade(cidade)
    return clima.tempo_agora(local["lat"], local["lon"]) if local else None


@bp.route("/api/atalho/bom-dia", methods=["GET", "POST"])
def atalho_bom_dia():
    import json as _json

    import rota_voo
    import vida_assistente
    from assistente import sinais
    import conversa_proativa
    import cards

    app = app_modulo()
    negado = _negado(app)
    if negado:
        return negado
    corpo = _entrada(app)
    agora = _agora(app)
    hoje = agora.date()
    conn = db.get_db()
    try:
        horas, _ = bom_dia.ler_sono(corpo)
        if horas is not None:
            db.upsert_saude_dia(conn, hoje.isoformat(), {"sono_horas": horas})
        primeira_vez = vida_assistente.acordou_hoje(conn, agora) is None
        if primeira_vez:
            vida_assistente.registrar_acordou(conn, agora.replace(second=0, microsecond=0))
            try:
                sinais.gravar(conn, "acordei", None, agora.isoformat(timespec="seconds"))
            except Exception:  # noqa: BLE001 - o sinal e extra
                pass
        salvo = (db.get_saude_dia(conn, hoje.isoformat()) or {}).get("sono_horas")
        eventos = app._eventos_de_hoje_com_seguranca(conn)
        voos = _voos_do_dia(conn, hoje)
        sem_hora = conn.execute(
            "SELECT COUNT(*) n FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL AND due_date = ? "
            "AND (hora IS NULL OR hora = '')", (hoje.isoformat(),)).fetchone()["n"]
        icao = (rota_voo.aerodromo(voos[0]["origem"]) or rota_voo.ORIGEM_PADRAO) if voos else None
        tempo = bom_dia.tempo_da_manha(os.environ.get("CIDADE_PADRAO", "").strip(), icao, buscar_clima=_clima_da_cidade)
        try:
            primeiro = app._primeiro_compromisso_do_dia(conn, hoje.isoformat())
        except Exception:  # noqa: BLE001 - Maps/rede
            primeiro = None
        if primeiro and primeiro.get("sair") and primeiro["sair"] < f"{agora:%H:%M}":
            primeiro = None  # a hora de sair ja passou: o passo vira a primeira tarefa
        t1 = conn.execute(
            "SELECT title FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL AND due_date = ? "
            "ORDER BY hora IS NULL, hora, id LIMIT 1", (hoje.isoformat(),)).fetchone()
        r = bom_dia.montar(agora=agora, corpo=corpo, eventos=eventos, voos=voos, sem_hora=sem_hora, tempo=tempo,
                           primeiro=primeiro, tarefa_primeira=t1["title"] if t1 else None,
                           sono_salvo=float(salvo) if salvo not in (None, "") else None)
        db.definir_configuracao(conn, CHAVE_BOM_DIA, _json.dumps({"dia": hoje.isoformat(), "fala": r["fala"]}, ensure_ascii=False))
        publicado = False
        if not app._modo_visitante_ativo() and not db.ja_notificou_hoje(conn, "bom_dia_chat"):
            conversa_proativa.publicar(conn, "bom_dia_chat", "Bom dia. Esse é o teu começo de dia.", [cards.card_bom_dia(r)])
            publicado = True
        conn.commit()
        # combinados "quando eu acordar, eu ..." (se_entao.py)
        disparados = se_entao.disparar(conn, "acordar", agora) if primeira_vez else []
        from voz_premium import configurado as voz_ok

        return jsonify({
            "ok": True, "fala": r["fala"], "linhas": r["linhas"], "hora": r["hora"], "sono_horas": r["sono_horas"],
            "no_chat": publicado, "combinados": [d["frase"] for d in disparados],
            # o Atalho toca este mp3 (mesmo token); sem ele cai em "Falar texto" com o campo `fala`
            "audio_url": "/api/atalho/bom-dia/audio" if voz_ok() else None,
        })
    finally:
        conn.close()


@bp.route("/api/atalho/bom-dia/audio", methods=["GET"])
def atalho_bom_dia_audio():
    import json as _json

    import voz_premium

    app = app_modulo()
    negado = _negado(app)
    if negado:
        return negado
    conn = db.get_db()
    try:
        try:
            dados = _json.loads(db.obter_configuracao(conn, CHAVE_BOM_DIA) or "{}")
        except ValueError:
            dados = {}
        if dados.get("dia") != _agora(app).date().isoformat() or not dados.get("fala") or not voz_premium.configurado():
            return Response(status=204)
        mp3 = voz_premium.sintetizar(conn, dados["fala"])
        conn.commit()
    finally:
        conn.close()
    if not mp3:
        return Response(status=204)
    return Response(mp3, mimetype="audio/mpeg", headers={"Cache-Control": "no-store"})


# ------------------------------------------------------------------ carro


@bp.route("/api/atalho/carro", methods=["GET", "POST"])
def atalho_carro():
    import json as _json

    import cards
    import conversa_proativa
    import maps_client
    import vida_assistente

    app = app_modulo()
    negado = _negado(app)
    if negado:
        return negado
    corpo = _entrada(app)
    agora = _agora(app)
    conn = db.get_db()
    try:
        maps = maps_client if maps_client.configurado() else None
        r = carro.montar(
            conn, agora.date(), agora, carro.parse_origem(corpo), maps=maps,
            resolver_lugar=lambda t: vida_assistente.resolver_lugar(conn, t),
            voo_antes_min=vida_assistente.voo_briefing_min(conn),
        )
        publicado = False
        c = carro.card(r, agora)
        if c and not app._modo_visitante_ativo():
            try:
                ant = _json.loads(db.obter_configuracao(conn, CHAVE_CARRO) or "{}")
                repetida = ant.get("fala") == r["fala"] and agora - datetime.fromisoformat(ant["em"]) < _TRES_HORAS
            except (ValueError, KeyError, TypeError):
                repetida = False
            if not repetida:
                conversa_proativa.publicar(conn, "carro_chat", "Tu ligou o carro. Isso é o que tem no caminho.", [c])
                db.definir_configuracao(conn, CHAVE_CARRO, _json.dumps({"fala": r["fala"], "em": agora.isoformat()}))
                publicado = True
        conn.commit()
        return jsonify({**{k: r.get(k) for k in ("tem", "fala", "titulo", "hora", "lugar", "chega_as", "trajeto_min", "waze")},
                        "parada": (r.get("parada") or {}).get("nome"), "no_chat": publicado})
    finally:
        conn.close()


# ------------------------------------------------------------------ gatilho generico


@bp.route("/api/atalho/gatilho", methods=["POST"])
def atalho_gatilho():
    app = app_modulo()
    negado = _negado(app)
    if negado:
        return negado
    evento = app._texto_curto(_entrada(app).get("evento"), 30)
    if evento not in se_entao.GATILHOS_DE_EVENTO:
        return jsonify({"error": "evento inválido - use um de: " + ", ".join(se_entao.GATILHOS_DE_EVENTO)}), 400
    conn = db.get_db()
    try:
        d = se_entao.disparar(conn, evento, _agora(app))
    finally:
        conn.close()
    return jsonify({"ok": True, "disparados": [x["frase"] for x in d]})


# ------------------------------------------------------------------ cartoes da manha


@bp.route("/api/manha/estado", methods=["GET"])
def manha_estado():
    ids = [int(x) for x in (request.args.get("ids") or "").split(",") if x.strip().isdigit()][:20]
    conn = db.get_db()
    try:
        return jsonify({"estados": {str(k): v for k, v in manha.estado_de(conn, ids).items()}})
    finally:
        conn.close()


def _acao_cartao(acao: str, cartao_id: int):
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    hoje = app._agora_brasilia().date()
    conn = db.get_db()
    try:
        r = {"resolver": lambda: manha.resolver(conn, cartao_id, hoje),
             "depois": lambda: manha.depois(conn, cartao_id, hoje),
             "esquecer": lambda: manha.esquecer(conn, cartao_id)}[acao]()
    finally:
        conn.close()
    if r is None:
        return jsonify({"error": "cartão não encontrado"}), 404
    return jsonify(r)


@bp.route("/api/manha/<int:cartao_id>/resolver", methods=["POST"])
def manha_resolver(cartao_id):
    return _acao_cartao("resolver", cartao_id)


@bp.route("/api/manha/<int:cartao_id>/depois", methods=["POST"])
def manha_depois(cartao_id):
    return _acao_cartao("depois", cartao_id)


@bp.route("/api/manha/<int:cartao_id>/esquecer", methods=["POST"])
def manha_esquecer(cartao_id):
    return _acao_cartao("esquecer", cartao_id)


@bp.route("/api/manha/preparar", methods=["POST"])
def manha_preparar():
    """Prepara os cartoes de hoje AGORA (o tick faz sozinho depois das 4h; aqui e pra testar/forcar)."""
    import conversa_proativa

    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    agora = _agora(app)
    conn = db.get_db()
    try:
        db.definir_configuracao(conn, manha.CONFIG_DIA, "{}")  # recomeca o dia
        linhas = manha.preparar(conn, agora.date(), agora)
        if linhas:
            conversa_proativa.publicar(conn, "cartoes_manha_chat", "Preparei o que ficou solto.", [manha.card(linhas, agora)])
        return jsonify({"ok": linhas is not None, "cartoes": len(linhas or [])})
    finally:
        conn.close()


# ------------------------------------------------------------------ se-entao


@bp.route("/api/se-entao", methods=["GET"])
def se_entao_listar():
    conn = db.get_db()
    try:
        return jsonify({"combinados": se_entao.listar(conn)})
    finally:
        conn.close()


@bp.route("/api/se-entao", methods=["POST"])
def se_entao_ativar():
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    corpo = app._corpo_json()
    conn = db.get_db()
    try:
        regra, motivo = se_entao.ativar(conn, corpo.get("meta"), corpo.get("gatilho"), corpo.get("hora"), corpo.get("acao"))
    finally:
        conn.close()
    if not regra:
        return jsonify({"error": motivo}), 400
    return jsonify({"ok": True, "id": regra["id"], "frase": regra["frase"]}), 201


@bp.route("/api/se-entao/<int:regra_id>/desativar", methods=["POST"])
def se_entao_desativar(regra_id):
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    conn = db.get_db()
    try:
        ok = se_entao.desativar(conn, regra_id)
    finally:
        conn.close()
    return (jsonify({"ok": True}) if ok else (jsonify({"error": "combinado não encontrado"}), 404))


@bp.route("/api/se-entao/<int:regra_id>/testar", methods=["POST"])
def se_entao_testar(regra_id):
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    conn = db.get_db()
    try:
        enviou = se_entao.testar(conn, regra_id)
    finally:
        conn.close()
    return jsonify({"ok": True, "enviado": bool(enviou)})
