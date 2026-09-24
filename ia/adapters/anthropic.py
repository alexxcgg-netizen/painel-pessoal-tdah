# ia/adapters/anthropic.py — faixa A2. Implementa ia.contrato.Adapter usando
# o SDK oficial `anthropic` (client.messages.create). So mexe aqui, no
# ia/adapters/__init__.py e no proprio teste — ia/contrato.py, ia/core.py e
# os outros adapters sao donos de outras faixas.
#
# Quem decide retry/fallback e o ia/core.py (faixa A1): este adapter nunca
# deixa uma excecao do SDK subir crua, sempre devolve Resposta(ok=False, ...).
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

import anthropic

from ia.contrato import Adapter, Resposta

# Mapa PT->valor aceito pela API em output_config.effort. "xhigh" e "max" ja
# chegam prontos (mesmo nome dos dois lados), so baixo/medio/alto precisam de
# traducao.
MAPA_ESFORCO = {
    "baixo": "low",
    "medio": "medium",
    "alto": "high",
}

# Estimativa grosseira de quantos tokens o contexto_fixo precisa ter pra
# cache_control valer a pena (a Anthropic exige um minimo por modelo pra
# aceitar o bloco como cacheavel — abaixo disso a API ignora o cache_control
# silenciosamente). Numeros aqui sao um palpite razoavel, NAO os valores
# oficiais — a faixa A4 fica de reconferir contra a doc/precos oficiais em
# ia/precos.json; isto aqui e so o mecanismo (liga/desliga cache), nao a
# fonte de verdade.
CACHE_MIN_TOKENS_POR_MODELO = {
    "claude-opus-5": 2048,
    "claude-sonnet-5": 1024,
    "claude-haiku-4-5": 4096,
}
CACHE_MIN_TOKENS_PADRAO = 1024

CAMINHO_PRECOS = Path(__file__).resolve().parent.parent / "precos.json"


def _cache_min_tokens(modelo: str) -> int:
    return CACHE_MIN_TOKENS_POR_MODELO.get(modelo, CACHE_MIN_TOKENS_PADRAO)


def _estimar_tokens(texto: str) -> int:
    """Aproximacao grosseira (~4 chars/token) so pra decidir se vale cachear.
    Nao e contagem real de tokens (isso exigiria client.messages.count_tokens,
    uma chamada de rede a mais) — e so o suficiente pro mecanismo de decisao."""
    return len(texto) // 4


def _instrucao_schema(schema: dict) -> str:
    return (
        "\n\nResponda usando APENAS um JSON valido (sem texto antes ou depois, "
        "sem bloco de codigo markdown) seguindo exatamente este schema:\n"
        + json.dumps(schema, ensure_ascii=False)
    )


def _extrair_json(texto: str) -> Optional[dict]:
    """Best-effort: tenta json.loads no texto puro e, se vier envolvido em
    ```json ... ``` (comum quando o modelo ignora a instrucao de "so JSON"),
    tenta de novo so com o miolo do bloco de codigo. Nao ha structured output
    de verdade aqui — e so prompt, entao isso pode falhar, e falhar aqui NUNCA
    deve derrubar a chamada (dados fica None, resto da Resposta continua ok)."""
    if not texto:
        return None
    candidato = texto.strip()
    try:
        dados = json.loads(candidato)
        return dados if isinstance(dados, dict) else None
    except (json.JSONDecodeError, ValueError):
        pass

    if candidato.startswith("```"):
        sem_cerca = candidato.strip("`")
        if sem_cerca.startswith("json"):
            sem_cerca = sem_cerca[4:]
        try:
            dados = json.loads(sem_cerca.strip())
            return dados if isinstance(dados, dict) else None
        except (json.JSONDecodeError, ValueError):
            return None
    return None


def _calcular_custo_usd(modelo: str, tokens_in: int, tokens_out: int,
                         tokens_cache_lido: int, tokens_cache_escrito: int) -> float:
    """Le ia/precos.json (formato ainda sendo definido pela faixa A4) e tenta
    calcular o custo. Leitura defensiva: arquivo ausente (A4 ainda nao
    terminou) ou formato inesperado -> custo_usd fica 0.0, nunca quebra a
    chamada.
    # TODO: A4 preenche ia/precos.json — reconferir aqui o formato real
    # assim que existir (esta funcao assume
    # {"<modelo>": {"input_por_mtok": x, "output_por_mtok": y,
    #                "cache_leitura_por_mtok": z, "cache_escrita_por_mtok": w}}
    # como palpite provisorio de layout).
    """
    try:
        with open(CAMINHO_PRECOS, "r", encoding="utf-8") as f:
            tabela = json.load(f)
    except FileNotFoundError:
        return 0.0
    except (json.JSONDecodeError, OSError):
        return 0.0

    try:
        precos_modelo = tabela.get(modelo)
        if not precos_modelo:
            return 0.0
        custo = (
            tokens_in * precos_modelo.get("input_por_mtok", 0) / 1_000_000
            + tokens_out * precos_modelo.get("output_por_mtok", 0) / 1_000_000
            + tokens_cache_lido * precos_modelo.get("cache_leitura_por_mtok", 0) / 1_000_000
            + tokens_cache_escrito * precos_modelo.get("cache_escrita_por_mtok", 0) / 1_000_000
        )
        return round(custo, 6)
    except (AttributeError, TypeError):
        return 0.0


class AdapterAnthropic(Adapter):
    """Adapter da Anthropic pro contrato ia.contrato.Adapter. O cliente e
    criado com a env var lida em tempo de importacao vazia por padrao (nunca
    falha so por faltar ANTHROPIC_API_KEY) — a falha real (se houver) so
    acontece na hora de chamar a API de verdade, dentro de .chamar()."""

    def __init__(self, client: Optional["anthropic.Anthropic"] = None):
        self._client = client or anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", "")
        )

    def chamar(self, *, modelo: str, esforco: str, sistema: str,
               contexto_fixo: str, mensagens: list, schema: Optional[dict],
               max_tokens_saida: int, cache: dict, modo: str) -> Resposta:
        cache = cache or {}

        texto_sistema = sistema or ""
        if schema:
            texto_sistema = texto_sistema + _instrucao_schema(schema)

        blocos_sistema = []
        if texto_sistema:
            blocos_sistema.append({"type": "text", "text": texto_sistema})

        if contexto_fixo:
            bloco_contexto = {"type": "text", "text": contexto_fixo}
            if cache.get("ativo") and _estimar_tokens(contexto_fixo) >= _cache_min_tokens(modelo):
                bloco_contexto["cache_control"] = {
                    "type": "ephemeral",
                    "ttl": cache.get("ttl", "5m"),
                }
            blocos_sistema.append(bloco_contexto)

        kwargs = {
            "model": modelo,
            "max_tokens": max_tokens_saida,
            "messages": mensagens,
        }
        if blocos_sistema:
            kwargs["system"] = blocos_sistema

        esforco_api = MAPA_ESFORCO.get(esforco, esforco)
        if esforco != "baixo":
            kwargs["thinking"] = {"type": "adaptive"}
        kwargs["output_config"] = {"effort": esforco_api}

        inicio = time.monotonic()
        try:
            resposta_api = self._client.messages.create(**kwargs)
        except anthropic.APIConnectionError as e:
            # Erro de rede/timeout (inclui anthropic.APITimeoutError, que e
            # subclasse de APIConnectionError) - o ia/core.py (faixa A1) e
            # quem decide retry/fallback, e so faz isso se a excecao SUBIR.
            # Por isso este caso (so este) e re-levantado em vez de virar
            # Resposta(ok=False, ...). Marca .retentavel = True pra deixar a
            # decisao explicita pra quem pegar a excecao mais acima.
            e.retentavel = True
            raise
        except anthropic.APIStatusError as e:
            # Erro de status HTTP (4xx/5xx) - nao e problema de rede, e
            # resposta da API (credencial invalida, rate limit, 500 etc). Vira
            # Resposta(ok=False, ...) normal, nao sobe.
            e.retentavel = False
            latencia_ms = int((time.monotonic() - inicio) * 1000)
            return Resposta(
                ok=False,
                provedor="anthropic",
                modelo=modelo,
                esforco=esforco,
                latencia_ms=latencia_ms,
                erro=str(e),
            )
        except anthropic.APIError as e:
            # Qualquer outro erro do SDK nao coberto pelos dois casos acima
            # (ex: erro de validacao da resposta) - trata como nao-retentavel.
            e.retentavel = False
            latencia_ms = int((time.monotonic() - inicio) * 1000)
            return Resposta(
                ok=False,
                provedor="anthropic",
                modelo=modelo,
                esforco=esforco,
                latencia_ms=latencia_ms,
                erro=str(e),
            )
        except Exception as e:  # defesa extra: bug nosso, nao do SDK/rede
            latencia_ms = int((time.monotonic() - inicio) * 1000)
            return Resposta(
                ok=False,
                provedor="anthropic",
                modelo=modelo,
                esforco=esforco,
                latencia_ms=latencia_ms,
                erro=str(e),
            )
        latencia_ms = int((time.monotonic() - inicio) * 1000)

        texto = "".join(
            bloco.text for bloco in resposta_api.content
            if getattr(bloco, "type", None) == "text"
        )

        dados = _extrair_json(texto) if schema else None

        usage = resposta_api.usage
        tokens_in = getattr(usage, "input_tokens", 0) or 0
        tokens_out = getattr(usage, "output_tokens", 0) or 0
        tokens_cache_lido = getattr(usage, "cache_read_input_tokens", 0) or 0
        tokens_cache_escrito = getattr(usage, "cache_creation_input_tokens", 0) or 0

        custo_usd = _calcular_custo_usd(
            modelo, tokens_in, tokens_out, tokens_cache_lido, tokens_cache_escrito
        )

        return Resposta(
            ok=True,
            texto=texto,
            dados=dados,
            provedor="anthropic",
            modelo=modelo,
            esforco=esforco,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            tokens_cache_lido=tokens_cache_lido,
            tokens_cache_escrito=tokens_cache_escrito,
            custo_usd=custo_usd,
            latencia_ms=latencia_ms,
            fallback_usado=False,
            erro=None,
        )


def criar_adapter() -> AdapterAnthropic:
    """Ponto de descoberta pro ia/core.py (faixa A1): instancia o adapter com
    o client padrao (le ANTHROPIC_API_KEY do ambiente). O nucleo tambem pode
    instanciar AdapterAnthropic diretamente - as duas formas funcionam."""
    return AdapterAnthropic()
