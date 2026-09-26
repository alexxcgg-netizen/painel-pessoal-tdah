"""Rotas da aba Construtora (Fase 7, C1) - movidas de app.py na faixa R1
(divisao de app.py em blueprints por dominio).

- GET /api/construtora/resumo -> status/tot_entradas/tot_saidas (via
  `construtora_cliente`, nunca lucro/margem/VGV) + contas a vencer.

Helpers (`_cliente_construtora`, `_buscar_resumo_construtora`,
`_buscar_contas_a_vencer_construtora`) continuam em app.py - sao
compartilhados com outras faixas (ex: briefing, testes fazem
`patch.object(app, "_buscar_contas_a_vencer_construtora", ...)`) - por isso
vem sempre via `app_modulo()`, nunca reimplementados aqui.
"""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo

bp = Blueprint("construtora", __name__)


@bp.route("/api/construtora/resumo", methods=["GET"])
def construtora_resumo():
    """Aba Construtora. Fase 7 (C1): via construtora_cliente (vale o modo
    mock CONSTRUTORA_API_MOCK=1) e so com o que o painel pessoal pode mostrar:
    `dados` = status/tot_entradas/tot_saidas (nunca lucro, margem, VGV) e a
    lista de contas a vencer (que a propria aba pede)."""
    app = app_modulo()
    if not app._cliente_construtora().configurado():
        return jsonify({"configurado": False})

    dados = app._buscar_resumo_construtora()
    if dados is None:
        return jsonify({"configurado": True, "erro": "Nao consegui falar com a API da construtora agora."}), 502

    dados_contas = app._buscar_contas_a_vencer_construtora(dias=30)
    contas = dados_contas.get("contas") if dados_contas and dados_contas.get("status") == "ok" else None

    return jsonify({"configurado": True, "dados": dados, "contas": contas})
