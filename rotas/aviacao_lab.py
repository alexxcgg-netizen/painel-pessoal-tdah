"""Blueprint aviacao_lab - Laboratorio v4, Grupo F (30/10/2026): radar de validades, previsao do cheque, banca
por caderno, voo de cadeira, vento na pista e passaporte (aviacao_lab.py faz a conta; aqui so HTTP).

GET /api/aviacao/card/<qual> devolve o card pronto (mesmo formato do chat) pra aba Aviacao; os POST gravam e
devolvem o dado novo do card. Login global (rotas/__init__.py); escrita recusada no modo visitante."""

from __future__ import annotations

from flask import Blueprint, jsonify

import aviacao_lab
import cards
import db
from rotas._base import app_modulo

bp = Blueprint("aviacao_lab", __name__)

QUAIS = {
    "radar": aviacao_lab.card_radar,
    "cheque": aviacao_lab.card_previsao_cheque,
    "banca": aviacao_lab.card_banca,
    "chair": aviacao_lab.card_chair,
    # card_vento recebe o ICAO (nao a data): a rota chama montar(conn, hoje) igual pra todos
    "vento": lambda conn, _hoje=None: aviacao_lab.card_vento(conn),
    "passaporte": aviacao_lab.card_passaporte,
}


def _hoje():
    return app_modulo()._agora_brasilia().date()


def _escrita(fn):
    """Abre conexao, recusa visitante, devolve (resposta de erro | None). `fn(conn, corpo, hoje)` devolve o JSON."""
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    corpo = app._corpo_json()
    conn = db.get_db()
    try:
        try:
            saida = fn(conn, corpo, _hoje())
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        app._marcar_atividade(conn)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, **saida})


@bp.route("/api/aviacao/card/<qual>", methods=["GET"])
def card_da_aviacao(qual):
    montar = QUAIS.get(qual)
    if montar is None:
        return jsonify({"error": "card desconhecido"}), 404
    app = app_modulo()
    conn = db.get_db()
    try:
        card = montar(conn, _hoje())
    finally:
        conn.close()
    card = {**card, "id": f"av-{qual}"}
    if app._modo_visitante_ativo():
        card = cards.mascarar_cards([card])[0]
    return jsonify({"ok": True, "card": card})


# ---- radar de validades ---------------------------------------------------------------------
@bp.route("/api/aviacao/prazos", methods=["POST"])
def salvar_prazo():
    def fn(conn, corpo, hoje):
        aviacao_lab.salvar_prazo(conn, str(corpo.get("chave") or ""), corpo.get("data"))
        return {"card": aviacao_lab.radar(conn, hoje)}

    return _escrita(fn)


@bp.route("/api/voos/<int:voo_id>/civ", methods=["POST"])
def confirmar_civ(voo_id):
    def fn(conn, corpo, hoje):
        if not aviacao_lab.confirmar_civ(conn, voo_id, corpo.get("confirmada") is not False):
            raise ValueError("voo não encontrado")
        return {"card": aviacao_lab.radar(conn, hoje)}

    return _escrita(fn)


# ---- previsao do cheque ---------------------------------------------------------------------
@bp.route("/api/aviacao/valor-hora", methods=["POST"])
def valor_hora():
    def fn(conn, corpo, hoje):
        aviacao_lab.salvar_valor_hora(conn, corpo.get("valor"))
        return {"card": aviacao_lab.previsao_cheque(conn, hoje)}

    return _escrita(fn)


# ---- banca ----------------------------------------------------------------------------------
@bp.route("/api/aviacao/banca/simulado", methods=["POST"])
def banca_simulado():
    def fn(conn, corpo, hoje):
        novo = aviacao_lab.registrar_simulado(conn, str(corpo.get("caderno") or ""), corpo.get("acertos"), hoje)
        return {"simulado_id": novo, "card": aviacao_lab.banca(conn, hoje)}

    return _escrita(fn)


@bp.route("/api/aviacao/banca/simulado/<int:simulado_id>/apagar", methods=["POST"])
def banca_simulado_apagar(simulado_id):
    def fn(conn, corpo, hoje):
        if not aviacao_lab.apagar_simulado(conn, simulado_id):
            raise ValueError("simulado não encontrado")
        return {"card": aviacao_lab.banca(conn, hoje)}

    return _escrita(fn)


@bp.route("/api/aviacao/banca/tempo", methods=["POST"])
def banca_tempo():
    def fn(conn, corpo, hoje):
        aviacao_lab.salvar_tempo_banca(conn, str(corpo.get("caderno") or ""), corpo.get("minutos"))
        return {"card": aviacao_lab.banca(conn, hoje)}

    return _escrita(fn)


@bp.route("/api/aviacao/banca/revisao", methods=["POST"])
def banca_revisao():
    def fn(conn, corpo, hoje):
        pid = corpo.get("id")
        if isinstance(pid, bool) or not isinstance(pid, int):
            raise ValueError("id da pergunta inválido")
        return {"revisao": aviacao_lab.revisar(conn, pid, bool(corpo.get("acertou")), hoje)}

    return _escrita(fn)


# ---- voo de cadeira -------------------------------------------------------------------------
@bp.route("/api/aviacao/chair", methods=["POST"])
def chair_registrar():
    def fn(conn, corpo, hoje):
        return {"id": aviacao_lab.registrar_chair(conn, corpo.get("voo_id"), corpo.get("travou"), hoje)}

    return _escrita(fn)


@bp.route("/api/aviacao/chair/roteiro", methods=["POST"])
def chair_roteiro():
    def fn(conn, corpo, hoje):
        n = aviacao_lab.salvar_roteiro(conn, corpo.get("passos"))
        return {"passos": n, "card": aviacao_lab.chair_flying(conn, hoje)}

    return _escrita(fn)


# ---- vento na pista -------------------------------------------------------------------------
@bp.route("/api/aviacao/pista", methods=["POST"])
def pista():
    def fn(conn, corpo, hoje):
        aviacao_lab.salvar_pista(conn, corpo)
        return {"card": aviacao_lab.vento_pista(conn)}

    return _escrita(fn)
