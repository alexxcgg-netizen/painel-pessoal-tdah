"""Blueprint contaspessoais - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import create_conta_pessoal, delete_conta_pessoal, get_db, marcar_conta_paga
import math

bp = Blueprint("contaspessoais", __name__)

@bp.route("/api/contas-pessoais", methods=["GET"])
def contas_pessoais():
    app = app_modulo()
    _contas_pessoais_com_status = app._contas_pessoais_com_status
    date = app.date
    conn = get_db()
    resultado = _contas_pessoais_com_status(conn, date.today())
    conn.close()
    return jsonify(resultado)

@bp.route("/api/contas-pessoais", methods=["POST"])
def criar_conta_pessoal():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _inteiro_no_intervalo = app._inteiro_no_intervalo
    body = _corpo_json()
    nome = (body.get("nome") or "").strip()
    dia = _inteiro_no_intervalo(body.get("dia_vencimento"), 1, 31)
    if not nome or len(nome) > 80:
        return jsonify({"error": "informe o nome da conta (até 80 caracteres)"}), 400
    if dia is None:
        return jsonify({"error": "dia de vencimento deve ser de 1 a 31"}), 400
    valor = body.get("valor")
    if valor in ("", None):
        valor = None
    else:
        try:
            valor = float(valor)
        except (TypeError, ValueError):
            return jsonify({"error": "valor inválido"}), 400
        if isinstance(body.get("valor"), bool) or valor < 0 or not math.isfinite(valor):
            return jsonify({"error": "valor inválido"}), 400
    conn = get_db()
    conta_id = create_conta_pessoal(conn, nome, dia, valor)
    conn.close()
    return jsonify({"ok": True, "id": conta_id}), 201

@bp.route("/api/contas-pessoais/<int:conta_id>", methods=["DELETE"])
def apagar_conta_pessoal(conta_id):
    conn = get_db()
    delete_conta_pessoal(conn, conta_id)
    conn.close()
    return jsonify({"ok": True})

@bp.route("/api/contas-pessoais/<int:conta_id>/paga", methods=["POST"])
def pagar_conta_pessoal(conta_id):
    app = app_modulo()
    _marcar_atividade = app._marcar_atividade
    _vencimento_em_aberto = app._vencimento_em_aberto
    date = app.date
    conn = get_db()
    conta = conn.execute("SELECT * FROM contas_pessoais WHERE id = ?", (conta_id,)).fetchone()
    if not conta:
        conn.close()
        return jsonify({"error": "conta não encontrada"}), 404
    venc = _vencimento_em_aberto(conn, conta, date.today())
    marcar_conta_paga(conn, conta_id, venc.isoformat())
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "vencimento": venc.isoformat()})
