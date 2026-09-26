"""Blueprint cotacoes - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from rotas._base import app_modulo
from db import criar_cotacao, criar_item_cotacao, delete_cotacao, delete_item_cotacao, get_cotacao, get_db, list_cotacoes, list_itens_cotacao

bp = Blueprint("cotacoes", __name__)

@bp.route("/api/cotacoes", methods=["GET"])
def listar_cotacoes():
    app = app_modulo()
    _modo_visitante_ativo = app._modo_visitante_ativo
    # US-F14: cotacao compara preco de fornecedor - e dado financeiro,
    # mesmo tratamento que /api/expenses/etc em modo visitante (lista
    # inteira escondida, nao so o valor - achado real: essa rota nunca
    # tinha ganhado essa checagem antes desta historia).
    if _modo_visitante_ativo():
        return jsonify([])
    conn = get_db()
    resultado = list_cotacoes(conn)
    conn.close()
    return jsonify(resultado)

@bp.route("/api/cotacoes", methods=["POST"])
def criar_cotacao_rota():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _modo_visitante_ativo = app._modo_visitante_ativo
    if _modo_visitante_ativo():
        return jsonify({"error": "indisponivel no modo visitante"}), 403
    titulo = (_corpo_json().get("titulo") or "").strip()
    if not titulo:
        return jsonify({"error": "informe o titulo da cotacao"}), 400
    conn = get_db()
    cotacao_id = criar_cotacao(conn, titulo)
    conn.close()
    return jsonify({"id": cotacao_id, "ok": True}), 201

@bp.route("/api/cotacoes/<int:cotacao_id>", methods=["GET"])
def ver_cotacao(cotacao_id):
    app = app_modulo()
    _modo_visitante_ativo = app._modo_visitante_ativo
    if _modo_visitante_ativo():
        return jsonify({"error": "indisponivel no modo visitante"}), 403
    conn = get_db()
    cotacao = get_cotacao(conn, cotacao_id)
    if not cotacao:
        conn.close()
        return jsonify({"error": "cotacao nao encontrada"}), 404
    itens = list_itens_cotacao(conn, cotacao_id)
    conn.close()
    return jsonify({**cotacao, "itens": itens})

@bp.route("/api/cotacoes/<int:cotacao_id>", methods=["DELETE"])
def apagar_cotacao(cotacao_id):
    conn = get_db()
    delete_cotacao(conn, cotacao_id)
    conn.close()
    return jsonify({"ok": True})

@bp.route("/api/cotacoes/<int:cotacao_id>/itens", methods=["POST"])
def adicionar_item_cotacao(cotacao_id):
    app = app_modulo()
    _corpo_json = app._corpo_json
    _modo_visitante_ativo = app._modo_visitante_ativo
    if _modo_visitante_ativo():
        return jsonify({"error": "indisponivel no modo visitante"}), 403
    conn = get_db()
    if not get_cotacao(conn, cotacao_id):
        conn.close()
        return jsonify({"error": "cotacao nao encontrada"}), 404

    body = _corpo_json()
    fornecedor = (body.get("fornecedor") or "").strip() or None
    valor = body.get("valor")
    if valor is not None and not isinstance(valor, (int, float)):
        conn.close()
        return jsonify({"error": "valor precisa ser um numero"}), 400

    item_id = criar_item_cotacao(
        conn,
        cotacao_id,
        fornecedor,
        valor,
        (body.get("prazo_texto") or "").strip() or None,
        (body.get("observacao") or "").strip() or None,
        origem="texto",
    )
    conn.close()
    return jsonify({"id": item_id, "ok": True}), 201

@bp.route("/api/cotacoes/<int:cotacao_id>/itens/pdf", methods=["POST"])
def adicionar_item_cotacao_pdf(cotacao_id):
    """Le um PDF de orcamento de fornecedor e extrai fornecedor/valor/prazo
    automaticamente - o Alex so anexa o PDF que recebeu, sem digitar nada."""
    app = app_modulo()
    TAMANHO_MAX_PDF_BYTES = app.TAMANHO_MAX_PDF_BYTES
    _call_claude = app._call_claude
    _log_usage = app._log_usage
    _modo_visitante_ativo = app._modo_visitante_ativo
    claude_client = app.claude_client
    if _modo_visitante_ativo():
        return jsonify({"error": "indisponivel no modo visitante"}), 403
    conn = get_db()
    if not get_cotacao(conn, cotacao_id):
        conn.close()
        return jsonify({"error": "cotacao nao encontrada"}), 404

    arquivo = request.files.get("arquivo")
    if not arquivo or not arquivo.filename:
        conn.close()
        return jsonify({"error": "anexe um arquivo PDF"}), 400
    if not arquivo.filename.lower().endswith(".pdf"):
        conn.close()
        return jsonify({"error": "so aceito arquivo PDF"}), 400

    pdf_bytes = arquivo.read()
    if len(pdf_bytes) > TAMANHO_MAX_PDF_BYTES:
        conn.close()
        return jsonify({"error": "PDF maior que 15MB - manda um arquivo menor"}), 400

    result, error = _call_claude(claude_client.extrair_item_cotacao_pdf, pdf_bytes)
    if error:
        conn.close()
        return error
    dados, usage = result

    _log_usage(conn, usage, "cotacao_pdf")
    item_id = criar_item_cotacao(
        conn,
        cotacao_id,
        dados.get("fornecedor"),
        dados.get("valor"),
        dados.get("prazo_texto"),
        dados.get("observacao"),
        origem="pdf",
    )
    conn.commit()
    conn.close()
    return jsonify({"id": item_id, "ok": True, **dados}), 201

@bp.route("/api/cotacoes/<int:cotacao_id>/itens/<int:item_id>", methods=["DELETE"])
def apagar_item_cotacao(cotacao_id, item_id):
    conn = get_db()
    delete_item_cotacao(conn, item_id)
    conn.close()
    return jsonify({"ok": True})
