# ia/adapters/gemini.py — faixa A15. Implementa ia.contrato.Adapter usando
# o SDK oficial `google-genai` (genai.GenerativeModel.generate_content). So mexe
# aqui, no ia/adapters/__init__.py e no proprio teste — ia/contrato.py,
# ia/core.py e os outros adapters sao donos de outras faixas.
#
# Quem decide retry/fallback e o ia/core.py (faixa A1): este adapter nunca
# deixa uma excecao do SDK subir crua, sempre devolve Resposta(ok=False, ...).
#
# TODO: Confirmar nomes de parametro e estrutura de resposta da API Gemini
# (documentacao oficial se tiver acesso de rede; senao confirmar via SDK).
from __future__ import annotations

import json
import os
import socket
import time
from typing import Optional

from ia.contrato import Adapter, Resposta
from ia import precos

# Mapa PT->valor aceito pela API Gemini. Se Gemini nao tiver equivalente,
# o esforco eh passado como-eh (sera ignorado se nao reconhecido).
# TODO: Confirmar nomes de parametro para controlador de esforco no Gemini.
MAPA_ESFORCO = {
    "baixo": "low",
    "medio": "medium",
    "alto": "high",
}


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




class AdapterGemini(Adapter):
    """Adapter da Google Gemini pro contrato ia.contrato.Adapter. O cliente eh
    criado com a env var lida em tempo de inicializacao (vazia por padrao - nunca
    falha so por faltar GEMINI_API_KEY) — a falha real (se houver) so
    acontece na hora de chamar a API de verdade, dentro de .chamar()."""

    def __init__(self, client: Optional["google.genai.Client"] = None):
        """Inicializa o adapter. Se client for None, cria um novo usando a
        chave da env var GEMINI_API_KEY (que pode estar vazia)."""
        self._client = client
        self._api_key = os.environ.get("GEMINI_API_KEY", "")

    def chamar(self, *, modelo: str, esforco: str, sistema: str,
               contexto_fixo: str, mensagens: list, schema: Optional[dict],
               max_tokens_saida: int, cache: dict, modo: str) -> Resposta:
        """Chama a API Gemini com as configuracoes solicitadas."""
        # Import tardio do SDK - so falha aqui se realmente chamar a API
        try:
            import google.genai as genai
        except ImportError:
            return Resposta(
                ok=False,
                provedor="gemini",
                modelo=modelo,
                esforco=esforco,
                erro="SDK google-genai nao instalado",
            )

        cache = cache or {}
        inicio = time.monotonic()

        try:
            # Configura cliente se nao foi injetado
            if self._client is None:
                genai.configure(api_key=self._api_key)
                client_local = genai.Client()
            else:
                client_local = self._client

            # Monta o sistema (instrucoes + contexto fixo + schema)
            texto_sistema = sistema or ""
            if schema:
                texto_sistema = texto_sistema + _instrucao_schema(schema)
            if contexto_fixo:
                texto_sistema = texto_sistema + "\n\nContexto:\n" + contexto_fixo

            # TODO: Confirmar parametros exatos para generate_content no Gemini
            # (safety_settings, generation_config, etc.)
            kwargs = {
                "model": modelo,
                "contents": mensagens,
            }

            if texto_sistema:
                kwargs["system_instruction"] = texto_sistema

            # TODO: Confirmar como passar max_tokens_saida no Gemini
            # (pode ser generation_config ou outro parametro)
            if max_tokens_saida:
                kwargs["generation_config"] = {
                    "max_output_tokens": max_tokens_saida,
                }

            # Tenta chamar a API
            resposta_api = client_local.models.generate_content(**kwargs)

        except Exception as e:
            # Detecta se eh erro de rede/timeout (deve subir com .retentavel = True)
            # Verifica ambos: classe da excecao e nome do tipo
            eh_rede = isinstance(e, (ConnectionError, TimeoutError, socket.timeout))
            tipo_erro = type(e).__name__
            if eh_rede or any(nome in tipo_erro for nome in [
                "APIConnectionError", "ConnectError", "Timeout",
                "NetworkError", "ReadTimeout", "WriteTimeout", "PoolTimeout"
            ]):
                e.retentavel = True
                raise
            # Outros erros do SDK/rede: marca como nao-retentavel
            e.retentavel = False
            latencia_ms = int((time.monotonic() - inicio) * 1000)
            return Resposta(
                ok=False,
                provedor="gemini",
                modelo=modelo,
                esforco=esforco,
                latencia_ms=latencia_ms,
                erro=str(e),
            )

        latencia_ms = int((time.monotonic() - inicio) * 1000)

        # Extrai texto da resposta
        # TODO: Confirmar estrutura de resposta.content do Gemini
        # (pode ser resposta_api.text, resposta_api.content[0].text, etc.)
        try:
            texto = resposta_api.text or ""
        except (AttributeError, IndexError):
            texto = ""

        dados = _extrair_json(texto) if schema else None

        # Extrai tokens da resposta
        # TODO: Confirmar atributos de uso (token count) no Gemini
        tokens_in = 0
        tokens_out = 0
        tokens_cache_lido = 0
        tokens_cache_escrito = 0

        try:
            # Tenta extrair usage se disponivel
            usage = getattr(resposta_api, "usage_metadata", None)
            if usage:
                tokens_in = getattr(usage, "prompt_token_count", 0) or 0
                tokens_out = getattr(usage, "candidates_token_count", 0) or 0
                # TODO: Confirmar nomes de atributos para cache no Gemini
                tokens_cache_lido = getattr(usage, "cached_content_input_token_count", 0) or 0
                tokens_cache_escrito = getattr(usage, "cache_creation_input_token_count", 0) or 0
        except (AttributeError, TypeError):
            pass

        custo_usd = precos.custo_usd(
            modelo, tokens_in, tokens_out, tokens_cache_lido, tokens_cache_escrito
        )

        return Resposta(
            ok=True,
            texto=texto,
            dados=dados,
            provedor="gemini",
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


def criar_adapter() -> AdapterGemini:
    """Ponto de descoberta pro ia/core.py (faixa A1): instancia o adapter com
    o client padrao (le GEMINI_API_KEY do ambiente). O nucleo tambem pode
    instanciar AdapterGemini diretamente - as duas formas funcionam."""
    return AdapterGemini()
