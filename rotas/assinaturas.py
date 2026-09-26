"""Blueprint assinaturas - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import get_db, responder_assinatura
import gastos
import math

bp = Blueprint("assinaturas", __name__)



@bp.route("/api/assinaturas/revisao", methods=["GET"])
def assinaturas_revisao():
    app = app_modulo()
    _assinaturas_pendentes_revisao = app._assinaturas_pendentes_revisao
    date = app.date
    conn = get_db()
    resultado = _assinaturas_pendentes_revisao(conn, date.today())
    conn.close()
    return jsonify(resultado)


@bp.route("/api/assinaturas/revisao", methods=["POST"])
def responder_assinatura_rota():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _marcar_atividade = app._marcar_atividade
    date = app.date
    body = _corpo_json()
    descricao = (body.get("descricao") or "").strip() if isinstance(body.get("descricao"), str) else ""
    resposta = body.get("resposta")
    if not descricao or len(descricao) > 200 or resposta not in ("usa", "nao_usa"):
        return jsonify({"error": "mande descrição e resposta ('usa' ou 'nao_usa')"}), 400
    valor = body.get("valor")
    valor = valor if isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor) else None
    conn = get_db()
    responder_assinatura(
        conn, gastos._normalizar_descricao(descricao), date.today().strftime("%Y-%m"), descricao, valor, resposta
    )
    tarefa_id = None
    if resposta == "nao_usa":
        cur = conn.execute("INSERT INTO tasks (title) VALUES (?)", (f"Cancelar assinatura: {descricao}",))
        tarefa_id = cur.lastrowid
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "tarefa_id": tarefa_id})
