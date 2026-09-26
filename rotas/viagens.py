"""Blueprint viagens - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import alternar_item_viagem, definir_numero_voo_viagem, delete_viagem, get_db, list_itens_viagem, list_viagens_futuras, obter_status_voo_cache, salvar_status_voo_cache, substituir_itens_viagem
import cards
import maps_client
import os
import requests
import vida
import voo_status

bp = Blueprint("viagens", __name__)

@bp.route("/api/viagem/status", methods=["GET"])
def viagem_status():
    return jsonify(
        {
            "configurado": maps_client.configurado(),
            "origem_padrao": os.environ.get("ENDERECO_CASA", ""),
        }
    )

@bp.route("/api/viagem/quando-sair", methods=["POST"])
def viagem_quando_sair():
    app = app_modulo()
    _corpo_json = app._corpo_json
    datetime = app.datetime
    if not maps_client.configurado():
        return jsonify({"error": "calculadora de deslocamento nao configurada - veja o README"}), 400

    body = _corpo_json()
    destino = (body.get("destino") or "").strip()
    chegar_ate_str = body.get("chegar_ate")
    origem = (body.get("origem") or "").strip() or os.environ.get("ENDERECO_CASA", "").strip()
    margem = body.get("margem_minutos", 15)
    modo = (body.get("modo") or "DRIVE").strip().upper()

    if not destino or not chegar_ate_str or not origem:
        return (
            jsonify({"error": "informe destino e horario de chegada (e origem, se nao tiver ENDERECO_CASA configurado)"}),
            400,
        )

    try:
        chegar_ate = datetime.fromisoformat(chegar_ate_str)
    except ValueError:
        return jsonify({"error": "chegar_ate precisa estar em formato AAAA-MM-DDTHH:MM"}), 400

    try:
        margem = int(margem)
    except (TypeError, ValueError):
        margem = 15

    try:
        resultado = maps_client.horario_de_saida(origem, destino, chegar_ate, margem, modo)
    except requests.RequestException:
        return jsonify({"error": "nao consegui calcular a rota agora"}), 502
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(resultado)

@bp.route("/api/viagens", methods=["GET"])
def viagens():
    app = app_modulo()
    _viagem_detalhada = app._viagem_detalhada
    date = app.date
    hoje = date.today()
    conn = get_db()
    resultado = [_viagem_detalhada(conn, v, hoje) for v in list_viagens_futuras(conn, hoje.isoformat())]
    conn.close()
    return jsonify(resultado)

@bp.route("/api/viagens", methods=["POST"])
def criar_viagem_rota():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _criar_viagem = app._criar_viagem
    body = _corpo_json()
    conn = get_db()
    resultado = _criar_viagem(
        conn,
        body.get("destino"),
        body.get("data_ida"),
        body.get("data_volta"),
        body.get("motivo"),
        body.get("internacional"),
    )
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201

@bp.route("/api/viagens/<int:viagem_id>/numero-voo", methods=["POST"])
def definir_numero_voo_viagem_rota(viagem_id):
    """US-F12: o Alex preenche o numero do voo comprado (ex: "LA3251") depois
    da compra - so registra o numero, a consulta de status em si e
    GET /api/viagens/<id>/voo-status (voo_status.py, cacheada)."""
    app = app_modulo()
    _corpo_json = app._corpo_json
    _texto_curto = app._texto_curto
    body = _corpo_json()
    numero = _texto_curto(body.get("numero_voo"), 12)
    numero = numero.upper().replace(" ", "") if numero else None
    conn = get_db()
    ok = definir_numero_voo_viagem(conn, viagem_id, numero)
    conn.close()
    if not ok:
        return jsonify({"error": "viagem nao encontrada"}), 404
    return jsonify({"ok": True, "numero_voo": numero})

@bp.route("/api/viagens/<int:viagem_id>/voo-status", methods=["GET"])
def viagem_voo_status_rota(viagem_id):
    """US-F12: status do voo comprado (voo_status.py, cacheado - nunca chama
    a API de novo dentro da janela de cache). Sem numero_voo cadastrado ou
    sem AVIATIONSTACK_API_KEY, volta so o suficiente pra tela mostrar o
    aviso certo, sem tentar rede nenhuma."""
    conn = get_db()
    registro = conn.execute("SELECT * FROM viagens WHERE id = ?", (viagem_id,)).fetchone()
    if not registro:
        conn.close()
        return jsonify({"error": "viagem nao encontrada"}), 404
    numero_voo = registro["numero_voo"]
    if not numero_voo:
        conn.close()
        return jsonify({"configurado": voo_status.configurado(), "erro": "informe o numero do voo primeiro"})
    resultado = voo_status.status_voo(
        numero_voo,
        registro["data_ida"],
        lambda nv, d: obter_status_voo_cache(conn, nv, d),
        lambda nv, d, j: salvar_status_voo_cache(conn, nv, d, j),
    )
    conn.close()
    return jsonify(resultado)

@bp.route("/api/viagens/<int:viagem_id>", methods=["DELETE"])
def apagar_viagem(viagem_id):
    conn = get_db()
    delete_viagem(conn, viagem_id)
    conn.close()
    return jsonify({"ok": True})

@bp.route("/api/viagens/<int:viagem_id>/mala", methods=["POST"])
def gerar_mala_rota(viagem_id):
    app = app_modulo()
    CLAUDE_FORMAT_ERROR_MSG = app.CLAUDE_FORMAT_ERROR_MSG
    _call_claude = app._call_claude
    _clima_texto_para = app._clima_texto_para
    _log_usage = app._log_usage
    _viagem_detalhada = app._viagem_detalhada
    claude_client = app.claude_client
    date = app.date
    conn = get_db()
    registro = conn.execute("SELECT * FROM viagens WHERE id = ?", (viagem_id,)).fetchone()
    if not registro:
        conn.close()
        return jsonify({"error": "viagem nao encontrada"}), 404
    ida = date.fromisoformat(registro["data_ida"])
    volta = date.fromisoformat(registro["data_volta"]) if registro["data_volta"] else ida
    dias = (volta - ida).days + 1
    clima_txt = _clima_texto_para(registro["destino"], registro["data_ida"])
    result, error = _call_claude(claude_client.gerar_mala, registro["destino"], dias, registro["motivo"], clima_txt)
    if error:
        conn.close()
        return error
    itens, usage = result
    itens = [i.strip()[:120] for i in itens if isinstance(i, str) and i.strip()][:20] if isinstance(itens, list) else []
    if not itens:
        conn.close()
        return jsonify({"error": CLAUDE_FORMAT_ERROR_MSG}), 502
    _log_usage(conn, usage, "mala_viagem")
    substituir_itens_viagem(conn, viagem_id, itens)
    resultado = _viagem_detalhada(conn, dict(registro), date.today())
    conn.close()
    return jsonify(resultado)

@bp.route("/api/viagens/itens/<int:item_id>/alternar", methods=["POST"])
def alternar_item_viagem_rota(item_id):
    conn = get_db()
    feito = alternar_item_viagem(conn, item_id)
    conn.close()
    if feito is None:
        return jsonify({"error": "item nao encontrado"}), 404
    return jsonify({"feito": feito})

@bp.route("/api/viagens/<int:viagem_id>/como-projeto", methods=["GET"])
def viagem_como_projeto_rota(viagem_id):
    app = app_modulo()
    date = app.date
    conn = get_db()
    registro = conn.execute("SELECT * FROM viagens WHERE id = ?", (viagem_id,)).fetchone()
    if not registro:
        conn.close()
        return jsonify({"error": "viagem nao encontrada"}), 404
    itens = list_itens_viagem(conn, viagem_id)
    conn.close()
    return jsonify(vida.viagem_como_projeto_detalhada(dict(registro), itens, date.today()))

@bp.route("/api/viagens/<int:viagem_id>/timeline-card", methods=["GET"])
def viagem_timeline_card_rota(viagem_id):
    """US-F11: mesmo `data` do card projeto_viagem (Fase 6, US-E13) que o chat
    ja usa (cards.card_viagem) - a tela de Viagens reaproveita o MESMO
    adaptador, sem recalcular etapas/progresso/marcos no front. Sem `actions`
    (a tela ja esta na aba Viagens - um botao "abrir aba Viagens" ali seria
    um link circular pro mesmo lugar)."""
    app = app_modulo()
    date = app.date
    conn = get_db()
    card = cards.card_viagem(conn, viagem_id, date.today(), actions_extra=[])
    conn.close()
    if not card:
        return jsonify({"error": "viagem nao encontrada"}), 404
    card["actions"] = []
    return jsonify(card)
