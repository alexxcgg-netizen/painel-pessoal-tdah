# ia/adapters/openai.py — Faixa A3 (adapter OpenAI, hibrido Anthropic+OpenAI)
#
# Implementa `Adapter.chamar(...)` (contrato em `ia/contrato.py`, que esta faixa
# NAO altera) usando o SDK oficial `openai` (pacote `openai`, versao instalada
# durante o desenvolvimento desta faixa: 3.19.2 — ver docs/ia-provedores.md pra
# o que foi de fato confirmado lendo o codigo do SDK instalado, com data, vs o
# que ficou como TODO por falta de confirmacao).
#
# ---------------------------------------------------------------------------
# Formato esperado de `mensagens` (contrato nao fixa isso - definido aqui pela
# faixa A3, mesma convencao que outros adapters devem seguir se quiserem
# suportar visao de forma compativel):
#
#   [
#     {"role": "user", "content": "texto simples"},
#     {"role": "assistant", "content": "texto simples"},
#     {"role": "user", "content": [
#         {"type": "text", "text": "o que tem nessa foto?"},
#         {"type": "image", "data_b64": "<base64 sem prefixo data:>",
#          "mime": "image/jpeg"},  # "mime" opcional, default "image/png"
#     ]},
#   ]
#
# Cada item de "content" em lista pode ser {"type": "text", "text": ...} ou
# {"type": "image", "data_b64": ..., "mime": ...}. Uma "content" string pura
# tambem e aceita (repassada como esta). Esta funcao converte "image" pro
# formato que a Chat Completions API da OpenAI espera:
# {"type": "image_url", "image_url": {"url": "data:<mime>;base64,<...>"}}
# (confirmado lendo `openai.types.chat.chat_completion_content_part_image_param`
# no pacote instalado — ver docs/ia-provedores.md).
# ---------------------------------------------------------------------------

import json
import os
import time
from typing import Optional

import openai

from ia import precos
from ia.contrato import Adapter, Resposta

# Esforco (contrato usa baixo/medio/alto) -> `reasoning_effort` da Chat
# Completions API. O SDK instalado aceita um leque maior (none/minimal/low/
# medium/high/xhigh/max - confirmado lendo o parametro `reasoning_effort` em
# `openai.resources.chat.completions.completions`), mas o briefing pediu
# especificamente so estes 3 baldes de saida (alto/xhigh/max colapsam em
# "high"); se o valor recebido nao estiver no mapa, cai em "medium" (nao
# quebra a chamada por um esforco desconhecido).
_MAPA_ESFORCO = {
    "baixo": "low",
    "medio": "medium",
    "alto": "high",
    "xhigh": "high",
    "max": "high",
}

# Caminho do arquivo de precos que a faixa A4 esta criando em paralelo
# (`ia/precos.json`). Formato assumido por esta faixa (A3), documentado em
# docs/ia-provedores.md - NAO confirmado com a A4 ainda:
#   {"openai": {"<modelo>": {"entrada": <usd por 1M tok>, "saida": ...,
#                             "cache_leitura": ..., "cache_escrita": ...}}}
# Se o arquivo nao existir, ou o modelo/campo nao estiver la, custo fica 0.0
# (nunca quebra a chamada por falta de preco).
_PRECOS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "precos.json")


class AdapterOpenAI(Adapter):
    """Adapter da OpenAI (GPT-6 Luna / GPT-6 Sol) pro contrato hibrido de IA."""

    def __init__(self, cliente: Optional["openai.OpenAI"] = None):
        # `cliente` opcional facilita mock em teste (unittest.mock) sem tocar
        # em rede nem em OPENAI_API_KEY. Sem injecao, cria um client "normal"
        # que NAO falha na importacao/instanciacao mesmo sem a env var (uma
        # string vazia e um `api_key` "dado" pro SDK, que so reclama de
        # credencial ausente numa chamada de verdade - nunca na construcao).
        self._cliente_injetado = cliente

    def _client(self) -> "openai.OpenAI":
        if self._cliente_injetado is not None:
            return self._cliente_injetado
        return openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

    # -- montagem da chamada --------------------------------------------

    @staticmethod
    def _converter_parte_conteudo(parte: dict) -> dict:
        if not isinstance(parte, dict):
            return {"type": "text", "text": str(parte)}
        tipo = parte.get("type")
        fonte = parte.get("source")
        # Fase 7 (C1): formato NATIVO da Anthropic, que ia/funcoes/visao.py
        # (A9) monta - {"type": "image"|"document", "source": {"type":
        # "base64", "media_type": ..., "data": ...}}. Sem isto, com
        # `ativo: true` a imagem ia vazia (sem data_b64) e o PDF ia cru (a
        # API recusa) - toda chamada caia no fallback Anthropic pagando 2x.
        if tipo in ("image", "document") and isinstance(fonte, dict):
            if fonte.get("type") != "base64" or not isinstance(fonte.get("data"), str):
                raise ValueError(f"{tipo} sem base64 nao suportado no adapter OpenAI")
            mime = fonte.get("media_type") or ("image/png" if tipo == "image" else "application/pdf")
            if tipo == "image":
                return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{fonte['data']}"}}
            if mime != "application/pdf":
                # Chat Completions so aceita PDF em `file_data` (guia oficial
                # "PDF files", developers.openai.com, lido em 2026-09-24).
                raise ValueError(f"documento {mime!r} nao suportado no adapter OpenAI (so PDF)")
            # Content part `File` (SDK instalado: openai.types.chat.
            # chat_completion_content_part_param.File/FileFile) com data URI,
            # como no guia oficial de PDF.
            return {
                "type": "file",
                "file": {"filename": "documento.pdf", "file_data": f"data:application/pdf;base64,{fonte['data']}"},
            }
        if tipo == "image":
            mime = parte.get("mime", "image/png")
            data_b64 = parte.get("data_b64", "")
            return {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{data_b64}"},
            }
        if tipo == "text":
            # C1: sem cache_control (campo da Anthropic, a OpenAI recusa).
            return {"type": "text", "text": parte.get("text", "")}
        # Tipo desconhecido: repassa como esta (best-effort, nao quebra).
        return parte

    @classmethod
    def _converter_mensagem(cls, mensagem: dict) -> dict:
        conteudo = mensagem.get("content")
        if isinstance(conteudo, list):
            conteudo = [cls._converter_parte_conteudo(p) for p in conteudo]
        convertida = dict(mensagem)
        convertida["content"] = conteudo
        return convertida

    @staticmethod
    def _montar_conteudo_sistema(sistema: str, contexto_fixo: str) -> str:
        # A OpenAI nao tem um `cache_control` explicito por bloco (diferente
        # da Anthropic, que a faixa A2 usa em ia/adapters/anthropic.py) - o
        # cache de prompt da OpenAI e automatico e por PREFIXO IDENTICO entre
        # chamadas (documentado no proprio SDK, parametro `prompt_cache_key`/
        # `prompt_cache_options` de `chat.completions.create`). Por isso e
        # importante que `sistema` + `contexto_fixo` fiquem sempre no mesmo
        # texto, na mesma ordem, byte a byte, entre chamadas seguidas da
        # mesma funcao - qualquer diferenca (espaco, timestamp embutido etc)
        # quebra o prefixo cacheavel e a chamada volta a custar preco cheio
        # de entrada. Nao ha acao explicita a tomar aqui alem de nunca
        # interpolar algo variavel (hora, id de sessao) DENTRO desse prefixo.
        if contexto_fixo:
            return f"{sistema}\n\n{contexto_fixo}" if sistema else contexto_fixo
        return sistema

    def _montar_mensagens(self, sistema: str, contexto_fixo: str, mensagens: list) -> list:
        msgs = []
        conteudo_sistema = self._montar_conteudo_sistema(sistema, contexto_fixo)
        if conteudo_sistema:
            # "developer" e o role recomendado pelo SDK instalado pra
            # modelos de raciocinio (confirmado lendo
            # `openai.types.chat.chat_completion_developer_message_param`:
            # "With o1 models and newer, `developer` messages replace the
            # previous `system` messages"). GPT-6 Luna/Sol suportam
            # `reasoning_effort` (ver `_MAPA_ESFORCO` acima), entao tratamos
            # como modelo de raciocinio e usamos "developer" aqui.
            msgs.append({"role": "developer", "content": conteudo_sistema})
        for m in mensagens or []:
            msgs.append(self._converter_mensagem(m))
        return msgs

    @staticmethod
    def _montar_response_format(schema: dict) -> dict:
        # Estrutura confirmada lendo
        # `openai.types.shared_params.response_format_json_schema` no SDK
        # instalado: {"type": "json_schema", "json_schema": {"name": ...,
        # "schema": ..., "strict": ...}}.
        if isinstance(schema, dict) and "schema" in schema and "name" in schema:
            # Ja veio no formato esperado (name + schema separados).
            nome = schema.get("name", "resposta")
            corpo_schema = schema.get("schema")
        else:
            nome = "resposta"
            corpo_schema = schema
        return {
            "type": "json_schema",
            "json_schema": {
                "name": nome,
                "schema": corpo_schema,
                "strict": True,
            },
        }

    # -- custo -------------------------------------------------------------

    @staticmethod
    def _calcular_custo(modelo: str, tokens_in: int, tokens_out: int,
                         tokens_cache_lido: int, tokens_cache_escrito: int) -> float:
        return precos.custo_usd(modelo, tokens_in, tokens_out, tokens_cache_lido, tokens_cache_escrito)

    # -- chamada principal ---------------------------------------------

    def chamar(self, *, modelo: str, esforco: str, sistema: str,
               contexto_fixo: str, mensagens: list, schema: Optional[dict],
               max_tokens_saida: int, cache: dict, modo: str) -> Resposta:
        # `cache` (dict passado pelo contrato) e um mecanismo generico entre
        # chamadas - a OpenAI nao usa `cache_control` explicito por bloco
        # (ver comentario em `_montar_conteudo_sistema`), entao esta faixa
        # nao consome nada dele; fica so pra manter a assinatura compativel
        # com o contrato e com o que os outros adapters (ex: Anthropic, que
        # tem cache explicito) esperam receber.
        #
        # Erro de rede/timeout (`openai.APIConnectionError`, que inclui
        # `openai.APITimeoutError` como subclasse - confirmado com
        # `openai.APITimeoutError.__mro__` no SDK instalado) NAO vira
        # Resposta(ok=False) aqui - e deixado subir (raise), com
        # `exc.retentavel = True` marcado antes, pro nucleo (`ia/core.py`,
        # faixa A1) decidir o retry. Combinado com o nucleo: um adapter que
        # ENGOLE erro de conexao numa Resposta nunca seria re-tentado, entao
        # esses dois tipos especificos sao a excecao a regra "nunca deixa
        # subir cru" - todo o resto (erro de autenticacao, rate limit, 4xx/5xx
        # de aplicacao, erro de parsing etc) continua virando
        # Resposta(ok=False, erro=...) normalmente.
        inicio = time.monotonic()
        try:
            client = self._client()
            msgs = self._montar_mensagens(sistema, contexto_fixo, mensagens)

            kwargs = {
                "model": modelo,
                "messages": msgs,
                # `max_completion_tokens` e o parametro atual - `max_tokens`
                # esta deprecado no SDK instalado (visto no docstring de
                # `chat.completions.create`) e nao e compativel com modelos
                # de raciocinio.
                "max_completion_tokens": max_tokens_saida,
            }

            esforco_api = _MAPA_ESFORCO.get(esforco, "medium")
            kwargs["reasoning_effort"] = esforco_api

            if modo == "flex":
                # Confirmado no SDK instalado: `service_tier` aceita "flex"
                # (Flex Processing, preco menor pra processamento nao
                # urgente) - visto no Literal do parametro em
                # `chat.completions.create`.
                kwargs["service_tier"] = "flex"

            usou_schema_estruturado = False
            resp = None
            if schema:
                try:
                    kwargs_schema = dict(kwargs)
                    kwargs_schema["response_format"] = self._montar_response_format(schema)
                    resp = client.chat.completions.create(**kwargs_schema)
                    usou_schema_estruturado = True
                except openai.APIConnectionError:
                    # Erro de rede/timeout na tentativa estruturada: nao e
                    # problema do schema, entao nao tenta fallback - deixa
                    # subir direto pro handler externo (que marca
                    # `retentavel` e re-levanta).
                    raise
                except Exception:
                    # Fallback documentado no briefing: se `response_format`
                    # com json_schema nao for aceito (modelo nao suporta,
                    # erro de validacao do proprio schema etc), cai pra
                    # instrucao no prompt + json.loads best-effort. Se a
                    # tentativa de fallback tambem levantar (inclusive
                    # APIConnectionError), propaga direto - so o handler
                    # externo decide o que fazer com ela.
                    kwargs_fallback = dict(kwargs)
                    if kwargs_fallback["messages"] and kwargs_fallback["messages"][0].get("role") == "developer":
                        kwargs_fallback["messages"][0] = dict(kwargs_fallback["messages"][0])
                        kwargs_fallback["messages"][0]["content"] = (
                            kwargs_fallback["messages"][0]["content"]
                            + "\n\nResponda APENAS com um JSON valido, sem texto extra, "
                              "seguindo este schema: " + json.dumps(schema, ensure_ascii=False)
                        )
                    else:
                        kwargs_fallback["messages"] = [
                            {
                                "role": "developer",
                                "content": (
                                    "Responda APENAS com um JSON valido, sem texto extra, "
                                    "seguindo este schema: " + json.dumps(schema, ensure_ascii=False)
                                ),
                            }
                        ] + kwargs_fallback["messages"]
                    resp = client.chat.completions.create(**kwargs_fallback)
            else:
                resp = client.chat.completions.create(**kwargs)

            latencia_ms = int((time.monotonic() - inicio) * 1000)

            texto = None
            if resp.choices:
                texto = resp.choices[0].message.content

            dados = None
            if schema and texto is not None:
                try:
                    dados = json.loads(texto)
                except (json.JSONDecodeError, TypeError):
                    dados = None

            usage = getattr(resp, "usage", None)
            tokens_in = getattr(usage, "prompt_tokens", 0) or 0
            tokens_out = getattr(usage, "completion_tokens", 0) or 0
            tokens_cache_lido = 0
            tokens_cache_escrito = 0
            detalhes_prompt = getattr(usage, "prompt_tokens_details", None)
            if detalhes_prompt is not None:
                # Confirmado no SDK instalado (`openai.types.completion_usage`
                # .PromptTokensDetails): campos `cached_tokens` e
                # `cache_write_tokens`.
                tokens_cache_lido = getattr(detalhes_prompt, "cached_tokens", 0) or 0
                tokens_cache_escrito = getattr(detalhes_prompt, "cache_write_tokens", 0) or 0

            custo_usd = self._calcular_custo(
                modelo, tokens_in, tokens_out, tokens_cache_lido, tokens_cache_escrito
            )

            return Resposta(
                ok=True,
                texto=texto,
                dados=dados,
                provedor="openai",
                modelo=modelo,
                esforco=esforco,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                tokens_cache_lido=tokens_cache_lido,
                tokens_cache_escrito=tokens_cache_escrito,
                custo_usd=custo_usd,
                latencia_ms=latencia_ms,
                fallback_usado=bool(schema) and not usou_schema_estruturado,
            )
        except openai.APIConnectionError as e:
            # Erro de rede/timeout (inclui APITimeoutError, subclasse) -
            # marca retentavel e deixa subir pro nucleo (ia/core.py, faixa
            # A1) decidir o retry, em vez de engolir numa Resposta(ok=False)
            # (combinado com a faixa A1 - ver comentario no topo de `chamar`).
            e.retentavel = True
            raise
        except Exception as e:
            # Qualquer outro erro (autenticacao, rate limit, 4xx/5xx de
            # aplicacao, parsing etc): nunca deixa subir cru - contrato pede
            # Resposta(ok=False, erro=...).
            latencia_ms = int((time.monotonic() - inicio) * 1000)
            return Resposta(
                ok=False,
                provedor="openai",
                modelo=modelo,
                esforco=esforco,
                latencia_ms=latencia_ms,
                erro=str(e),
            )


def criar_adapter() -> AdapterOpenAI:
    """Fabrica que o nucleo (ia/core.py, faixa A1) usa pra descobrir e
    instanciar este adapter (por convencao de nome de funcao no modulo -
    alternativa a importar a classe `AdapterOpenAI` diretamente)."""
    return AdapterOpenAI()
