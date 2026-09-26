"""Blueprint notas_fiscais - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import get_db
import base64
import binascii
import gastos

bp = Blueprint("notas_fiscais", __name__)


@bp.route("/api/notas-fiscais/extrair", methods=["POST"])
def extrair_nota_fiscal():
    """Recebe a foto de uma nota fiscal (base64, nao multipart - de proposito:
    o corpo em JSON e o mesmo formato que /api/capture ja usa, entao a fila
    offline (fila-offline.js, generica pra qualquer url/method/headers/body)
    consegue reenfileirar essa chamada sem precisar de nenhum tratamento
    especial pra FormData/Blob quando a foto e tirada sem internet) e extrai
    valor/estabelecimento/data via claude_client (API de visao da Anthropic -
    decisao ja tomada com o Alex, sem OCR local). So extrai: NUNCA grava o
    gasto direto, porque a leitura por IA pode errar o valor - a confirmacao
    e o fluxo de registro ficam com /api/notas-fiscais/confirmar (US-C9)."""
    app = app_modulo()
    TAMANHO_MAX_IMAGEM_BYTES = app.TAMANHO_MAX_IMAGEM_BYTES
    TETO_IA_MSG = app.TETO_IA_MSG
    _TETO_IA_LOCK = app._TETO_IA_LOCK
    _call_claude = app._call_claude
    _corpo_json = app._corpo_json
    _log_usage = app._log_usage
    _teto_ia_estourado = app._teto_ia_estourado
    claude_client = app.claude_client
    body = _corpo_json()
    imagem_b64 = body.get("imagem_base64")
    media_type = (body.get("media_type") or "").strip().lower()
    if not imagem_b64 or not isinstance(imagem_b64, str):
        return jsonify({"error": "anexe uma foto da nota fiscal"}), 400
    if media_type not in claude_client.MEDIA_TYPES_IMAGEM_VALIDOS:
        return jsonify({"error": "formato de imagem não suportado (use jpeg, png, webp ou heic)"}), 400

    try:
        image_bytes = base64.b64decode(imagem_b64, validate=True)
    except (binascii.Error, ValueError):
        return jsonify({"error": "imagem inválida (base64 malformado)"}), 400
    if not image_bytes:
        return jsonify({"error": "imagem vazia"}), 400
    if len(image_bytes) > TAMANHO_MAX_IMAGEM_BYTES:
        return jsonify({"error": "foto maior que 10MB - manda uma foto menor"}), 400

    conn = get_db()
    # Mesmo teto mensal da US-A6 (ver _classificar_intent) - extracao por
    # visao usa Sonnet, mais caro que o Haiku do classificador de intent,
    # entao e a chamada mais cara do app pra deixar sem controle de gasto.
    # Revisao de seguranca da Fase 5 achou que so o classificador de intent
    # respeitava o teto - corrigido aqui. Mesmo _TETO_IA_LOCK da
    # _classificar_intent (fecha a mesma janela TOCTOU nos dois pontos que
    # respeitam o teto).
    with _TETO_IA_LOCK:
        if _teto_ia_estourado("extrair_nota_fiscal_foto"):
            conn.close()
            return jsonify({"error": TETO_IA_MSG}), 402

        result, error = _call_claude(claude_client.extrair_nota_fiscal_foto, image_bytes, media_type)
        if error:
            conn.close()
            return error
        dados, usage = result

        _log_usage(conn, usage, "nota_fiscal")
        conn.commit()
    conn.close()
    return jsonify(dados), 200


@bp.route("/api/notas-fiscais/confirmar", methods=["POST"])
def confirmar_nota_fiscal():
    """Segundo passo do fluxo (US-C9): recebe o valor/estabelecimento/data
    que o Alex CONFIRMOU na tela (pode ter editado o que a IA leu errado -
    nunca salva o que veio de /extrair sem passar por aqui) e vira um gasto
    de verdade, com a MESMA sugestao automatica de categoria ja usada pro
    extrato bancario (gastos.sugerir_categoria, historico de gastos
    categorizados manualmente - nao um classificador novo e paralelo)."""
    app = app_modulo()
    _corpo_json = app._corpo_json
    _marcar_atividade = app._marcar_atividade
    _texto_seguro = app._texto_seguro
    date = app.date
    body = _corpo_json()
    valor = body.get("valor")
    estabelecimento = _texto_seguro(body.get("estabelecimento")).strip()
    data_compra = _texto_seguro(body.get("data")).strip() or None
    categoria_informada = _texto_seguro(body.get("categoria")).strip() or None

    if not isinstance(valor, (int, float)) or isinstance(valor, bool) or valor <= 0:
        return jsonify({"error": "informe um valor valido (maior que zero)"}), 400
    if not estabelecimento:
        return jsonify({"error": "informe o estabelecimento"}), 400
    if data_compra:
        try:
            date.fromisoformat(data_compra)
        except ValueError:
            return jsonify({"error": "data inválida (use AAAA-MM-DD)"}), 400

    conn = get_db()
    categoria = categoria_informada
    if not categoria:
        historico = conn.execute(
            "SELECT category, description, source_text FROM expenses "
            "WHERE tipo = 'real' AND category IS NOT NULL"
        ).fetchall()
        categoria = gastos.sugerir_categoria(estabelecimento, [dict(r) for r in historico]) or "outros"

    created_at = f"{data_compra} 12:00:00" if data_compra else None
    if created_at:
        cur = conn.execute(
            "INSERT INTO expenses (amount, category, description, source_text, tipo, created_at) "
            "VALUES (?, ?, ?, ?, 'real', ?)",
            (valor, categoria, estabelecimento, f"Nota fiscal (foto): {estabelecimento}", created_at),
        )
    else:
        cur = conn.execute(
            "INSERT INTO expenses (amount, category, description, source_text, tipo) "
            "VALUES (?, ?, ?, ?, 'real')",
            (valor, categoria, estabelecimento, f"Nota fiscal (foto): {estabelecimento}"),
        )
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"id": cur.lastrowid, "ok": True, "categoria": categoria}), 201
