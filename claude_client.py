"""Fachada da IA antiga (Fase 7, Etapa 0): o codigo mora em `ia/legado.py`
(cliente, modelos, preco, helpers) e em `ia/funcoes/<grupo>.py` (um arquivo por
grupo de funcao, cada um com a faixa dona). Este modulo so REEXPORTA tudo, pra
`app.py`, `telegram_bot.py` e os testes continuarem usando `claude_client.X`
sem mudar nada.

Pegadinhas de quem mexe aqui:
- `app.py` chama `claude_client.X(...)` na hora da chamada, entao
  `patch("claude_client.chat")` continua valendo pro app.
- `claude_client.client` e o MESMO objeto de `ia.legado.client` - patch em
  `claude_client.client.messages.create` pega todas as funcoes.
- Mas `patch("claude_client._usage")` (ou qualquer nome usado DENTRO de
  `ia/funcoes/*`) NAO afeta as funcoes de la: patche no modulo onde a funcao
  usa o nome (ex: `ia.funcoes.captura._usage`).
- Funcao nova vai no arquivo do grupo (ou num arquivo novo em ia/funcoes/) e
  ganha uma linha de reexport aqui.
"""
# ruff: noqa: F401
import base64
import json
import os
from datetime import date, datetime

from anthropic import Anthropic

from ia.funcoes.captura import (
    ACOES_INTENT,
    CAPTURE_PROMPT,
    CONFIANCA_MINIMA_INTENT,
    ESSENCIAL_PROMPT,
    INTENT_PROMPT,
    SUMMARY_PROMPT,
    classify_capture,
    classify_intent,
    escolher_essencial,
    summarize_day,
)
from ia.funcoes.chat import (
    CHAT_SYSTEM_PROMPT,
    CHAT_TOOLS,
    DECISAO_PROMPT,
    MENSAGEM_DIFICIL_PROMPT,
    analisar_decisao,
    ao_texto,
    chat,
    opcoes_chat,
    redigir_mensagem_dificil,
    resolver_quando_data,
)
from ia.funcoes.planejamento import (
    BREAKDOWN_PROMPT,
    MALA_PROMPT,
    PLANO_PROMPT,
    REQUEBRAR_PROMPT,
    RESUMO_LINK_PROMPT,
    break_down_task,
    gerar_mala,
    plano_do_dia,
    requebrar_tarefa,
    resumir_link,
)
from ia.funcoes.visao import (
    COTACAO_PDF_PROMPT,
    MEDIA_TYPES_IMAGEM_VALIDOS,
    NOTA_FISCAL_PROMPT,
    extrair_item_cotacao_pdf,
    extrair_nota_fiscal_foto,
)
from ia.legado import HAIKU, PRICING, SONNET, _extract_json, _usage, client
