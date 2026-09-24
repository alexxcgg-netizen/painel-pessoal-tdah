"""Nucleo compartilhado da IA antiga (antes do ia/core.py da Fase 7): cliente
Anthropic, modelos, tabela de preco e helpers usados por mais de um grupo de
funcoes em ia/funcoes/. Extraido de claude_client.py sem mudar comportamento
(Fase 7, Etapa 0). claude_client.py continua reexportando tudo daqui."""
import json
import os

from anthropic import Anthropic

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-5"

# USD por 1M tokens (input, output)
PRICING = {
    HAIKU: (1.00, 5.00),
    SONNET: (2.00, 10.00),
}


def _extract_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def _usage(response) -> dict:
    input_price, output_price = PRICING[response.model]
    cost = (response.usage.input_tokens / 1_000_000) * input_price + (
        response.usage.output_tokens / 1_000_000
    ) * output_price
    return {
        "model": response.model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cost_usd": cost,
    }
