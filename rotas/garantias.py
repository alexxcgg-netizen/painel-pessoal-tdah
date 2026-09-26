"""Blueprint garantias - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from rotas._base import app_modulo
from db import delete_garantia, get_db, list_garantias
import base64

bp = Blueprint("garantias", __name__)

@bp.route("/api/garantias", methods=["GET"])
def garantias_rota():
    app = app_modulo()
    _garantia_com_status = app._garantia_com_status
    date = app.date
    conn = get_db()
    hoje = date.today()
    resultado = [_garantia_com_status(g, hoje) for g in list_garantias(conn)]
    conn.close()
    resultado.sort(key=lambda g: g["dias_ate"])
    return jsonify(resultado)

@bp.route("/api/garantias", methods=["POST"])
def criar_garantia_rota():
    app = app_modulo()
    EXTENSOES_ANEXO_GARANTIA = app.EXTENSOES_ANEXO_GARANTIA
    TAMANHO_MAX_ANEXO_GARANTIA_BYTES = app.TAMANHO_MAX_ANEXO_GARANTIA_BYTES
    _conteudo_bate_com_extensao = app._conteudo_bate_com_extensao
    _corpo_json = app._corpo_json
    _criar_garantia = app._criar_garantia
    conn = get_db()
    anexo_b64 = None
    if request.content_type and "multipart/form-data" in request.content_type:
        produto = request.form.get("produto")
        data_compra = request.form.get("data_compra")
        prazo = request.form.get("prazo_garantia_meses")
        arquivo = request.files.get("nota_fiscal")
        if arquivo and arquivo.filename:
            nome = arquivo.filename.lower()
            if not nome.endswith(EXTENSOES_ANEXO_GARANTIA):
                conn.close()
                return jsonify({"error": "anexo precisa ser PDF, JPG ou PNG"}), 400
            dados = arquivo.read()
            if len(dados) > TAMANHO_MAX_ANEXO_GARANTIA_BYTES:
                conn.close()
                return jsonify({"error": "anexo maior que 5MB - manda um arquivo menor"}), 400
            if not _conteudo_bate_com_extensao(nome, dados):
                conn.close()
                return jsonify({"error": "conteúdo do arquivo não bate com a extensao (PDF, JPG ou PNG de verdade)"}), 400
            anexo_b64 = base64.b64encode(dados).decode("ascii")
    else:
        body = _corpo_json()
        produto = body.get("produto")
        data_compra = body.get("data_compra")
        prazo = body.get("prazo_garantia_meses")
    resultado = _criar_garantia(conn, produto, data_compra, prazo, anexo_b64)
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201

@bp.route("/api/garantias/<int:garantia_id>", methods=["DELETE"])
def apagar_garantia_rota(garantia_id):
    conn = get_db()
    delete_garantia(conn, garantia_id)
    conn.close()
    return jsonify({"ok": True})
