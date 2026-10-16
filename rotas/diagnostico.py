"""Blueprint diagnostico - medidas reais do aparelho (2026-10-15).

Bug de iPhone (barra de abas pela metade, microfone que não grava) vinha sendo corrigido no
chute, sem iPhone aqui. O app manda um retrato curto da tela/microfone quando algo acontece;
fica guardado (últimos 500) e `scripts/ler_chat.py` mostra junto da conversa.

Autenticação: global (`_verificar_autenticacao` em app.py). Só números/nomes de erro - nada de
conteúdo. Nunca falha alto: diagnóstico não pode virar erro na tela.
"""

from __future__ import annotations

import json

from flask import Blueprint, Response, request

from db import get_db

bp = Blueprint("diagnostico", __name__)

TIPOS = ("tela", "mic", "erro_js")
MAX_LINHAS = 500
MAX_BYTES = 4000
MAX_CAMPOS = 40


def _limpo(dados) -> dict | None:
    """Só pares chave curta -> número/bool/texto curto; o resto é descartado."""
    if not isinstance(dados, dict):
        return None
    saida = {}
    for chave, valor in list(dados.items())[:MAX_CAMPOS]:
        if not isinstance(chave, str) or len(chave) > 32:
            continue
        if isinstance(valor, bool) or valor is None:
            saida[chave] = valor
        elif isinstance(valor, (int, float)):
            saida[chave] = round(float(valor), 2) if isinstance(valor, float) else valor
        elif isinstance(valor, str):
            saida[chave] = valor[:80]
    return saida


@bp.route("/api/diagnostico", methods=["POST"])
def registrar():
    corpo = request.get_json(silent=True)
    if not isinstance(corpo, dict) or corpo.get("tipo") not in TIPOS:
        return Response(status=204)
    dados = _limpo(corpo.get("dados"))
    if dados is None:
        return Response(status=204)
    texto = json.dumps(dados, ensure_ascii=False)
    if len(texto) > MAX_BYTES:
        return Response(status=204)
    conn = get_db()
    try:
        conn.execute("INSERT INTO diagnostico_cliente (tipo, dados_json) VALUES (?, ?)", (corpo["tipo"], texto))
        conn.execute(
            "DELETE FROM diagnostico_cliente WHERE id <= (SELECT MAX(id) FROM diagnostico_cliente) - ?",
            (MAX_LINHAS,),
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()
    return Response(status=204)
