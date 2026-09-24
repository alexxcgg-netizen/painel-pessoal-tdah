# classificador_local/regras/p4_regra.py — faixa P4 (Fase 7): reconhece
# (sem IA) que uma frase e um pedido de criar uma regra ("me avisa se...",
# "me lembra de...", "todo dia às...", "toda segunda...") e devolve um card
# de CONFIRMACAO no contrato de cards (docs/CARDS.md: {cards, resumo_texto,
# passos}) com botoes Confirmar/Cancelar - contrato deste arquivo em si
# (casar/executar) e o de classificador_local/__init__.py (Etapa 0/X1).
#
# casar(texto): so reconhece a INTENCAO (e um pedido de regra?), rapido e
# barato - nao interpreta o conteudo. executar(conn, parametros): faz a
# interpretacao de verdade (assistente.regras.interpretar_regra - parser
# local primeiro, IA so se precisar) e monta o card.
#
# NOTA pro integrador/faixa de frontend (P4 UI / cards.py e docs/CARDS.md
# sao compartilhados, fora dos arquivos desta faixa - ver
# docs/agentes/fase7-regras-faixa.md): falta 1) documentar o card
# "p4_regra_confirmacao" em docs/CARDS.md, 2) registrar o renderizador em
# static/js/cards-tipos.js, 3) os botoes Confirmar/Cancelar do card chamam
# POST /api/p4_regras/confirmar (rotas/p4_regras.py) com
# {"texto_original": data.texto_original, "json": {"gatilho":...,
# "condicao":..., "acao":..., "texto":...}} - Cancelar so descarta o card,
# sem chamada nenhuma (nada foi criado ainda nesse ponto).
from __future__ import annotations

import re

from assistente import regras as motor

# So reconhece a INTENCAO (virou candidato a regra) - a interpretacao de
# verdade (gatilho/condicao/acao) e feita por assistente.regras.interpretar_regra.
_PADROES_INTENCAO = (
    re.compile(r"\bme\s+avisa(?:r)?\s+se\b", re.IGNORECASE),
    re.compile(r"\bme\s+lembr\w*\s+de\b", re.IGNORECASE),
    re.compile(r"\btodo(?:s)?\s+(?:os\s+)?dias?\s+(?:às|as|a)\s+\d", re.IGNORECASE),
    re.compile(
        r"\btod[ao](?:s)?\s+(?:a|as|o|os)?\s*"
        r"(?:segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo)",
        re.IGNORECASE,
    ),
)


def casar(texto: str) -> dict | None:
    """Devolve {"acao", "confianca", "parametros"} (contrato de
    classificador_local/__init__.py) quando o texto parece um pedido de
    regra, senao None (nao e desta faixa). `parametros["texto"]` e o que
    executar() repassa pra assistente.regras.interpretar_regra."""
    if not isinstance(texto, str) or not texto.strip():
        return None
    for padrao in _PADROES_INTENCAO:
        if padrao.search(texto):
            return {"acao": "criar_regra", "confianca": 1.0, "parametros": {"texto": texto.strip()}}
    return None


def _card_recusa(mensagem: str) -> dict:
    return {
        "cards": [],
        "resumo_texto": mensagem,
        "passos": [
            {"modulo": "Assistente", "descricao": "Nao criou a regra", "ms": 0, "erro": True}
        ],
    }


def executar(conn, parametros: dict) -> dict:
    """Interpreta o texto (local ou IA) e devolve o card de confirmacao, no
    contrato {cards, resumo_texto, passos} (docs/CARDS.md). `conn` nao e
    usado aqui (a interpretacao nao consulta banco) - fica no parametro pra
    seguir o mesmo formato de assinatura dos outros classificador_local/regras/*.py."""
    texto = (parametros or {}).get("texto") or ""
    resultado = motor.interpretar_regra(texto)

    if not resultado["ok"]:
        mensagem = resultado["erro"] or "Nao entendi essa regra. Pode tentar descrever de outro jeito?"
        return _card_recusa(mensagem)

    regra = resultado["regra"]
    resumo = motor.montar_resumo_regra(regra)
    card = {
        "type": "p4_regra_confirmacao",
        "id": "c1",
        "data": {
            "texto_original": texto,
            "resumo": resumo,
            "gatilho": regra["gatilho"],
            "condicao": regra["condicao"],
            "acao": regra["acao"],
            "texto": regra["texto"],
            "interpretado_por": resultado["fonte"],
        },
        "actions": [
            {"tipo": "confirmar_regra", "rotulo": "Confirmar"},
            {"tipo": "cancelar_regra", "rotulo": "Cancelar"},
        ],
    }
    return {
        "cards": [card],
        "resumo_texto": f"{resumo} Confirma?",
        "passos": [
            {"modulo": "Assistente", "descricao": "Interpretou o pedido de regra", "ms": 0}
        ],
    }
