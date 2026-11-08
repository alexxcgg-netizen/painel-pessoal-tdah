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
)
# "me lembra de X" sozinho e lembrete de UMA vez ("me lembra de tomar o remedio
# as 7" = amanha 7h se ja passou): fica com a IA do chat, que cria a tarefa.
# So vira regra com repeticao ("todo dia", "sempre") ou condicao ("quando eu
# chegar", "se chover") - antes virava "todo dia as 07:00" sem ele ter dito.
_LEMBRA_DE = re.compile(r"\bme\s+lembr\w*\b", re.IGNORECASE)
_REPETE_OU_CONDICAO = re.compile(
    r"\b(?:tod[ao]s?\s+(?:os\s+|as\s+)?(?:dias?|semanas?|m[eê]s|meses|manh[aã]s?|noites?|tardes?)|"
    r"sempre|diariamente|toda\s+vez|cada\s+vez|quando|assim\s+que|"
    r"se\s+(?:eu|chover|n[aã]o|o\s+tempo|estiver|tiver|for))\b",
    re.IGNORECASE,
)
# Recorrencia ("todo dia as 8h", "toda segunda") so vira regra quando vem
# junto de um pedido ao assistente ("me avisa/manda/lembra/pergunta/cobra").
# Sozinha ela e tarefa recorrente ou remedio ("tenho que tomar Losartana todo
# dia as 8h") e fica com a IA (registrar_tarefa/registrar_medicamento).
_PADROES_RECORRENCIA = (
    re.compile(r"\btodo(?:s)?\s+(?:os\s+)?dias?\s+(?:às|as|a)\s+\d", re.IGNORECASE),
    re.compile(
        r"\btod[ao](?:s)?\s+(?:a|as|o|os)?\s*"
        r"(?:segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo)",
        re.IGNORECASE,
    ),
)
_PEDIDO_AO_ASSISTENTE = re.compile(r"\bme\s+(?:avisa|lembr\w*|manda|pergunta|cobra)\b", re.IGNORECASE)
# Brain dump (varias frases ou texto longo) nunca vira UMA regra: segue pra
# IA, que separa os itens (um deles pode ser o "me lembra de..." de la).
_TAMANHO_MAXIMO = 160
_VARIAS_FRASES = re.compile(r"[.!?;]\s+\S")


def casar(texto: str) -> dict | None:
    """Devolve {"acao", "confianca", "parametros"} (contrato de
    classificador_local/__init__.py) quando o texto parece um pedido de
    regra, senao None (nao e desta faixa). `parametros["texto"]` e o que
    executar() repassa pra assistente.regras.interpretar_regra."""
    if not isinstance(texto, str) or not texto.strip():
        return None
    limpo = texto.strip()
    if len(limpo) > _TAMANHO_MAXIMO or "\n" in limpo or _VARIAS_FRASES.search(limpo):
        return None
    pedido = (
        any(p.search(limpo) for p in _PADROES_INTENCAO)
        or (_LEMBRA_DE.search(limpo) and _REPETE_OU_CONDICAO.search(limpo))
        or (_PEDIDO_AO_ASSISTENTE.search(limpo) and any(p.search(limpo) for p in _PADROES_RECORRENCIA))
    )
    if pedido:
        return {"acao": "criar_regra", "confianca": 1.0, "parametros": {"texto": limpo}}
    return None


def _card_recusa(mensagem: str) -> dict:
    return {
        "cards": [],
        "resumo_texto": mensagem,
        "passos": [
            {"modulo": "Assistente", "descricao": "Não criou a regra", "ms": 0, "erro": True}
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
        mensagem = resultado["erro"] or "Não entendi essa regra. Pode tentar descrever de outro jeito?"
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
