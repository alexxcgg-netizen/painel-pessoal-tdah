"""rotas/onde_vou.py - leva 06/11 "painel mais esperto" (onde_vou.py): os botoes dos cards novos.

  - `POST /api/onde-vou/<id>/resposta` {resposta: "sim" | "outro"} - "E isso" / "Vou pra outro lugar" do
    card `indo_pra`. Outro lugar: o painel para de insistir nessa tarefa hoje (sem recado, sem amostra).
  - `POST /api/tempos-reais/usar` {usar: "meu" | "padrao"} - o segmentado "Meu tempo / Padrao" do card
    `meu_tempo` (config `tempos_reais_usar`; vale pra todos os avisos de sair).
  - `GET /api/tempos-reais` - o que o painel aprendeu (pra tela/IA): minutos, frase, amostras, preferencia.

Sessao do PIN (rota normal do app). Modo visitante: 403 nos POST.
"""

from __future__ import annotations

from flask import Blueprint, jsonify

import onde_vou
from db import get_db
from rotas._base import app_modulo

bp = Blueprint("onde_vou", __name__)


@bp.route("/api/onde-vou/<int:indo_id>/resposta", methods=["POST"])
def responder(indo_id):
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    resposta = app._corpo_json().get("resposta")
    if resposta not in ("sim", "outro"):
        return jsonify({"error": "resposta tem que ser 'sim' ou 'outro'"}), 400
    conn = get_db()
    try:
        r = onde_vou.responder(conn, indo_id, resposta)
    finally:
        conn.close()
    if r is None:
        return jsonify({"error": "nao achei essa saida"}), 404
    return jsonify(r)


@bp.route("/api/tempos-reais/usar", methods=["POST"])
def usar():
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    valor = app._corpo_json().get("usar")
    if valor not in ("meu", "padrao"):
        return jsonify({"error": "usar tem que ser 'meu' ou 'padrao'"}), 400
    conn = get_db()
    try:
        return jsonify({"ok": True, "usar": onde_vou.definir_preferencia(conn, valor)})
    finally:
        conn.close()


@bp.route("/api/tempos-reais", methods=["GET"])
def ver():
    conn = get_db()
    try:
        a = onde_vou.ajuste(conn)
    finally:
        conn.close()
    return jsonify({k: a[k] for k in ("aprendido", "saida_min", "usar", "amostras", "frase")})
