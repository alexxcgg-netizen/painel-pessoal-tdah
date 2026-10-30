"""Blueprint dinheiro_lab - Grupo E (Dinheiro) do Laboratorio v4, 30/10/2026.

Cupom vira itens (`nfce.py`) e cacador de contas no e-mail (`email_contas.py`). Dinheiro PESSOAL do
Alex; nunca toca a construtora. Tudo exige login (nenhuma rota maquina-a-maquina aqui: o Atalho do
iPhone entra pelo /api/atalho/capturar que ja existe, e a regra local reconhece o link do cupom).
Visitante: nada escreve, nada devolve valor.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from rotas._base import app_modulo
from db import get_db

bp = Blueprint("dinheiro_lab", __name__)


@bp.route("/api/cupons/<int:cupom_id>/registrar", methods=["POST"])
def registrar_cupom_como_gasto(cupom_id):
    """"Registrar como gasto" do card do cupom: cria (ou vincula, se o gasto do mesmo valor ja existe) a
    linha em `expenses`. Idempotente - tocar duas vezes nao duplica."""
    import nfce

    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    conn = get_db()
    try:
        r = nfce.registrar_gasto(conn, cupom_id, app._agora_brasilia().date().isoformat())
    finally:
        conn.close()
    if r is None:
        return jsonify({"error": "cupom não encontrado"}), 404
    return jsonify({"ok": True, **r})


@bp.route("/api/cupons/resumo", methods=["GET"])
def resumo_cupons():
    """Quanto saiu por categoria nos cupons lidos (`?categoria=Besteira&dias=30`)."""
    import nfce

    app = app_modulo()
    if app._modo_visitante_ativo():
        return jsonify({"oculto": True})
    categoria = request.args.get("categoria", "Besteira")
    if categoria not in nfce.CATEGORIAS:
        return jsonify({"error": "categoria inválida"}), 400
    try:
        dias = int(request.args.get("dias", 30))
    except ValueError:
        return jsonify({"error": "dias inválido"}), 400
    conn = get_db()
    try:
        return jsonify(nfce.total_por_categoria(conn, categoria, dias))
    finally:
        conn.close()


@bp.route("/api/contas-email", methods=["GET"])
def contas_email_lista():
    import email_contas

    app = app_modulo()
    ligado = email_contas.configurado()
    if app._modo_visitante_ativo():
        return jsonify({"ligado": ligado, "oculto": True, "contas": []})
    conn = get_db()
    try:
        return jsonify({"ligado": ligado, "contas": email_contas.pendentes(conn, 20)})
    finally:
        conn.close()


@bp.route("/api/contas-email/varrer", methods=["POST"])
def contas_email_varrer():
    """Varredura na hora (o scheduler ja faz a cada 30 min). Sem EMAIL_IMAP_* no .env: 200 com ligado=false."""
    import email_contas

    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    conn = get_db()
    try:
        r = email_contas.varrer(conn, app._agora_brasilia().replace(tzinfo=None), forcar=True)
    finally:
        conn.close()
    return jsonify({"ligado": r["ligado"], "rodou": r["rodou"], "novas": len(r["novas"]), "lidos": r["lidos"], "erro": r["erro"]})


@bp.route("/api/contas-email/<int:conta_id>/status", methods=["POST"])
def contas_email_status(conta_id):
    """{"status": "paga" | "ignorada" | "nova"}. Paga tambem fecha a tarefa de lembrete."""
    import email_contas

    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    status = app._corpo_json().get("status")
    if status not in ("paga", "ignorada", "nova"):
        return jsonify({"error": "status inválido"}), 400
    conn = get_db()
    try:
        ok = email_contas.marcar(conn, conta_id, status)
    finally:
        conn.close()
    if not ok:
        return jsonify({"error": "conta não encontrada"}), 404
    return jsonify({"ok": True, "status": status})
