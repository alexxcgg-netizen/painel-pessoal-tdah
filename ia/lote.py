# ia/lote.py — faixa A9 (Fase 7): processamento de varios documentos da MESMA
# funcao de IA de uma vez, em modo "nao urgente".
#
# Por que: ia/adapters/openai.py mapeia `modo="flex"` (do contrato em
# ia/contrato.py) pra `service_tier="flex"` da Chat Completions API - Flex
# Processing custa metade do preco normal, ao custo de latencia maior/menos
# previsivel (nao serve pra quem esta esperando na tela, so pra lote
# processado em segundo plano). `processar_lote` e generico - nao sabe nada
# de nota fiscal/cotacao especificamente - serve pra qualquer funcao de IA
# (ia/config.d/<funcao>.json) que precise rodar sobre varios itens de uma vez
# sem pressa. Hoje nada chama isto ainda (foto de nota fiscal continua em
# modo padrao, na hora - ver docstring de
# ia.funcoes.visao.extrair_nota_fiscal_foto); e a base pronta pra quando
# existir importacao de extrato bancario em lote (varias paginas/arquivos de
# uma vez), citada no briefing da faixa.
#
# O adapter Anthropic (ia/adapters/anthropic.py, faixa A2) NAO faz nada
# especial com `modo` alem de repassar - "flex" so tem efeito de custo no
# adapter OpenAI hoje; nas demais chamadas o campo e ignorado sem quebrar
# nada (mesmo espirito do "cache" no adapter OpenAI, ver comentario la).

from __future__ import annotations

import logging
from typing import Callable, Optional

from ia import core
from ia.contrato import Resposta

log = logging.getLogger(__name__)


def processar_lote(
    funcao: str,
    itens: list,
    *,
    schema: Optional[dict] = None,
    sistema: str = "",
    montar_mensagens: Optional[Callable[[object], list]] = None,
    opcoes: Optional[dict] = None,
) -> list[tuple[object, Resposta]]:
    """Processa `itens` (qualquer lista) pela funcao de IA `funcao`
    (ia/config.d/<funcao>.json), um item por chamada de ia.core.chamar_ia,
    sempre com `opcoes["modo"] = "flex"` (nao urgente, metade do preco no
    adapter OpenAI - ver comentario no topo do arquivo). Qualquer `modo`
    passado em `opcoes` e sobrescrito de proposito: e o motivo deste modulo
    existir.

    `montar_mensagens(item) -> list[mensagem]` (opcional): converte cada item
    bruto (ex.: bytes de um PDF, um dict com pagina+mime) na lista de
    `mensagens` que ia.core.chamar_ia espera. Se omitido, cada item de
    `itens` PRECISA ja ser essa lista de mensagens pronta.

    Devolve uma lista de (item, Resposta) na MESMA ordem de `itens` - nunca
    levanta por causa de um item falhar isoladamente (a Resposta daquele item
    vem com ok=False e o erro em .erro; quem chama decide o que fazer com
    item que falhou, igual ao resto do contrato de ia.core.chamar_ia)."""
    opcoes_lote = dict(opcoes or {})
    opcoes_lote["modo"] = "flex"

    resultados: list[tuple[object, Resposta]] = []
    for item in itens:
        mensagens = montar_mensagens(item) if montar_mensagens else item
        try:
            resp = core.chamar_ia(funcao, mensagens, sistema=sistema, schema=schema, opcoes=opcoes_lote)
        except Exception as exc:  # noqa: BLE001 - erro de programacao (ex.: config invalida)
            # config ausente/invalida (ia.core.ConfigIAErro) e erro de
            # programacao e deveria mesmo quebrar cedo (ver ia/core.py) -
            # mas um item bruto que faz montar_mensagens() ou o proprio
            # chamar_ia levantar algo inesperado nao pode derrubar o lote
            # inteiro por causa de UM documento ruim. Vira Resposta(ok=False)
            # igual a qualquer outra falha, com o motivo em .erro.
            log.exception("ia.lote: item falhou em '%s' - seguindo pro proximo", funcao)
            resp = Resposta(ok=False, erro=f"{exc.__class__.__name__}: {exc}")
        resultados.append((item, resp))
    return resultados
