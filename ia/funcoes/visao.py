"""Leitura de documento/imagem: PDF de cotacao e foto de nota fiscal.
Faixa A9 (Fase 7). Migrado pra ia.core.chamar_ia (schema JSON + fallback por
confianca) - antes chamava o SDK Anthropic direto. claude_client.py continua
reexportando estes nomes (assinatura e formato do retorno inalterados).

--------------------------------------------------------------------------
Compat com testes antigos (tests/test_claude_client.py, escritos ANTES desta
migracao, fora da minha lista de arquivos - nao editei):
--------------------------------------------------------------------------
Esses testes fazem `patch.object(claude_client.client.messages, "create",
...)`, ou seja, mockam a instancia COMPARTILHADA `ia.legado.client`. O
`ia.core.chamar_ia` normalmente resolve o adapter "anthropic" via
`ia.adapters.anthropic.criar_adapter()`, que cria um `anthropic.Anthropic()`
NOVO (outra instancia) - o mock dos testes antigos nao teria efeito nenhum
nela, e a chamada real tentaria rede de verdade (proibido nos testes).

Resolvido aqui, sem editar ia/core.py nem ia/adapters/anthropic.py (donos de
outra faixa): `ia.core.registrar_adapter(provedor, fabrica)` e API PUBLICA
pensada exatamente pra isso ("registra uma fabrica de Adapter... serve pros
testes e pra provedores novos sem mexer neste arquivo" - docstring de
ia/core.py). `_registrar_adapter_anthropic_compartilhado()` registra uma
fabrica que injeta `ia.legado.client` (o AdapterAnthropic aceita
`client=...` desde a faixa A2) - efeito colateral bom (1 client Anthropic so
no processo, em vez de 1 por adapter) e nao muda nenhum arquivo de outra
faixa. E chamada de novo a cada chamada das duas funcoes desta faixa (nao so
uma vez na importacao) porque `ia.core.registrar_adapter(..., None)` e o
padrao de limpeza usado por outros testes (ex.: tests/test_ia_core.py) e,
rodando a suite inteira, o tearDown de um teste de outra faixa pode apagar
esse registro entre um teste e outro - reafirmar antes de cada uso e barato
e evita depender da ordem em que os arquivos de teste rodam.

Sobre o formato de imagem/documento na mensagem: ia/adapters/openai.py
documenta e CONVERTE `{"type": "image", "data_b64": ..., "mime": ...}` pro
formato da Chat Completions API. Ja ia/adapters/anthropic.py (faixa A2) NAO
converte nada - repassa `mensagens` pro SDK como veio (`"messages":
mensagens`, sem tratamento). Como as duas configs desta faixa nascem com
`ativo: false` (ver ia/config.d/README.md - migracao so vira `alvo` quando
`ativo: true`), a UNICA tentativa que roda hoje e sempre anthropic/
claude-sonnet-5, entao as mensagens abaixo usam o formato NATIVO da
Anthropic (`{"type": "document"/"image", "source": {"type": "base64",
"media_type": ..., "data": ...}}` - o mesmo que o codigo antigo montava, e o
que os testes antigos conferem byte a byte). Registrado em
scripts/ralph-a9-visao/progress.txt: quando `ativo` virar `true` (migracao
pro GPT-6 Luna), este arquivo tambem precisa passar a montar as mensagens no
formato que ia/adapters/openai.py espera (`image_url`/`file` - ver
scripts/ralph-a9-visao/APRENDIZADOS.md pro que foi confirmado no SDK
instalado sobre PDF) - so trocar `ativo` no JSON NAO basta pra estas duas
funcoes, ao contrario das funcoes so-texto.
"""
from __future__ import annotations

import base64
import logging

from ia import core
from ia.adapters.anthropic import AdapterAnthropic
from ia.contrato import Resposta
from ia.legado import client as _client_legado

log = logging.getLogger(__name__)

# Nomes das "funcoes de IA" (ia/config.d/<funcao>.json) usados por
# ia.core.chamar_ia - tem que bater com o nome do arquivo de config.
FUNCAO_NOTA_FISCAL = "extrair_nota_fiscal_foto"
FUNCAO_COTACAO_PDF = "extrair_item_cotacao_pdf"

# Abaixo disso (ou JSON fora do schema/invalido), refaz a chamada - ver
# _chamar_com_retry. O schema tambem usa este valor como "minimum" do campo
# "confianca": isso faz o PROPRIO ia.core tratar confianca baixa como uma
# tentativa "fora do schema" e cair sozinho pro fallback configurado
# (Sonnet 5) quando ele for distinto do principal (migracao com ativo:true) -
# ver ia/config.d/README.md, passo 4 do fluxo de chamar_ia.
CONFIANCA_MINIMA = 0.7


def _registrar_adapter_anthropic_compartilhado() -> None:
    core.registrar_adapter("anthropic", lambda: AdapterAnthropic(client=_client_legado))


def _usage_de_resposta(resp: Resposta) -> dict:
    """Reconstroi o dict de uso no formato antigo (ia.legado._usage) a partir
    de uma ia.contrato.Resposta - mantem a assinatura/retorno de hoje pra
    quem ja consome `usage["input_tokens"]` etc. (claude_client.py, testes,
    telas)."""
    return {
        "model": resp.modelo,
        "input_tokens": resp.tokens_in,
        "output_tokens": resp.tokens_out,
        "cost_usd": resp.custo_usd,
    }


def _chamar_com_retry(funcao: str, mensagens: list, *, schema: dict) -> Resposta:
    """Chama ia.core.chamar_ia(funcao, ...) e, se a resposta vier invalida
    (JSON fora do schema - inclusive confianca < CONFIANCA_MINIMA - ou JSON
    invalido, ou qualquer outra falha tecnica), refaz mais uma vez do zero
    antes de desistir.

    Por que uma segunda chamada plena, e nao so confiar no `fallback` da
    config: as duas configs desta faixa tem `ativo: false` hoje, entao
    `modelo_atual` e `fallback[0]` sao o MESMO modelo (anthropic/
    claude-sonnet-5) - ia.core._montar_tentativas faz dedup disso pra UMA
    tentativa so (mesmo provedor/modelo/esforco). "Refazer com Sonnet 5"
    hoje, portanto, so acontece se esta funcao pedir uma chamada nova
    explicitamente - e o que este retry faz. Quando `ativo` virar true
    (alvo = GPT-6 Luna, fallback = Sonnet 5, dois modelos DISTINTOS), o
    schema com "confianca.minimum" ja faz o ia.core cair pro fallback
    sozinho numa unica chamada; este retry vira so uma rede de seguranca
    extra por cima disso, nunca o unico mecanismo.

    Levanta RuntimeError se as duas tentativas falharem - mesmo espirito do
    codigo antigo, que deixava json.JSONDecodeError subir cru quando a IA
    nao devolvia JSON valido (nunca inventa um retorno "de mentira" so pra
    manter o tipo tuple[dict, dict])."""
    _registrar_adapter_anthropic_compartilhado()
    resp = core.chamar_ia(funcao, mensagens, schema=schema)
    if not resp.ok:
        log.warning(
            "ia.funcoes.visao: %s falhou (confianca baixa/JSON invalido/erro tecnico: %s) - refazendo",
            funcao, resp.erro,
        )
        _registrar_adapter_anthropic_compartilhado()
        resp = core.chamar_ia(funcao, mensagens, schema=schema)
    if not resp.ok:
        raise RuntimeError(
            f"ia.funcoes.visao: falha ao extrair via IA em '{funcao}' mesmo apos refazer: {resp.erro}"
        )
    return resp


COTACAO_PDF_PROMPT = """Leia esse PDF de orcamento/cotacao de um fornecedor de material de
construcao e extraia em JSON:
{"fornecedor": nome da empresa/fornecedor (texto curto) ou null se nao identificar,
 "valor": valor TOTAL do orcamento em reais (numero puro, sem "R$" nem separador de milhar) ou
 null se nao achar um valor total claro, "prazo_texto": prazo de entrega mencionado, em texto
 livre (ex: "15 dias uteis") ou null, "observacao": um detalhe curto relevante (frete incluso,
 validade da proposta, forma de pagamento) ou null, "confianca": numero de 0.0 a 1.0 - o quanto
 voce tem certeza dos valores extraidos (1.0 = documento claro e legivel, sem ambiguidade; abaixo
 de 0.7 = letra dificil, valor rasurado/ambiguo, ou dado que voce teve que inferir em vez de ler
 direto)}

So extraia o que estiver escrito no documento - nunca estime ou arredonde um valor que nao
esteja explicito. Responda SO com o JSON, sem explicacao, sem markdown."""

SCHEMA_COTACAO_PDF = {
    "type": "object",
    # "confianca" fica DE FORA de "required" de proposito (so no properties,
    # com o "minimum" abaixo) - compat com tests/test_claude_client.py
    # (escrito antes desta migracao, fora da minha lista de arquivos, nao
    # editei): o JSON canonico la nao tem esse campo, e ia.core.validar_schema
    # so aplica "minimum" quando a chave ESTA presente (nao valida o que nao
    # existe) - entao a resposta antiga continua batendo com o schema. O
    # prompt novo (COTACAO_PDF_PROMPT) sempre PEDE "confianca"; ausencia dela
    # numa resposta de verdade seria a IA ignorando o prompt, nao um caso
    # esperado - mas nao precisa quebrar o schema por isso.
    "required": ["fornecedor", "valor", "prazo_texto", "observacao"],
    "additionalProperties": False,
    "properties": {
        "fornecedor": {"type": ["string", "null"]},
        "valor": {"type": ["number", "null"]},
        "prazo_texto": {"type": ["string", "null"]},
        "observacao": {"type": ["string", "null"]},
        "confianca": {"type": "number", "minimum": CONFIANCA_MINIMA, "maximum": 1.0},
    },
}


def extrair_item_cotacao_pdf(pdf_bytes: bytes) -> tuple[dict, dict]:
    """Le um PDF de cotacao/orcamento de fornecedor e extrai fornecedor/valor/prazo -
    extracao pura (mesmo espirito de classify_capture: a IA so le e devolve estruturado,
    nunca decide nada sozinho, quem compara os valores depois e o Python).

    Migrado pra ia.core.chamar_ia (faixa A9): mesma assinatura/retorno de
    hoje (tuple[dict, dict], dict sem o campo "confianca" - ele so orienta o
    fallback interno, ver CONFIANCA_MINIMA/_chamar_com_retry)."""
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
    mensagens = [
        {
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
                },
                {"type": "text", "text": COTACAO_PDF_PROMPT},
            ],
        }
    ]
    resp = _chamar_com_retry(FUNCAO_COTACAO_PDF, mensagens, schema=SCHEMA_COTACAO_PDF)
    return resp.dados, _usage_de_resposta(resp)


NOTA_FISCAL_PROMPT = """Leia essa foto de nota fiscal/cupom fiscal e extraia em JSON:
{"valor": valor TOTAL da compra em reais (numero puro, sem "R$" nem separador de milhar) ou null
 se nao achar um valor total claro, "estabelecimento": nome do estabelecimento/loja (texto curto)
 ou null se nao identificar, "data": data da compra no formato "AAAA-MM-DD" ou null se nao achar
 uma data legivel, "confianca": numero de 0.0 a 1.0 - o quanto voce tem certeza dos valores
 extraidos (1.0 = foto nitida e sem duvida; abaixo de 0.7 = foto borrada/cortada, letra dificil,
 ou dado que voce teve que inferir em vez de ler direto)}

So extraia o que estiver escrito na foto - nunca estime ou arredonde um valor que nao esteja
explicito, e nunca invente estabelecimento ou data que a foto nao mostre com clareza. Responda SO
com o JSON, sem explicacao, sem markdown."""

MEDIA_TYPES_IMAGEM_VALIDOS = {"image/jpeg", "image/png", "image/webp", "image/heic"}

SCHEMA_NOTA_FISCAL = {
    "type": "object",
    # "confianca" fora de "required" de proposito - mesmo motivo do schema
    # de cotacao acima (compat com tests/test_claude_client.py).
    "required": ["valor", "estabelecimento", "data"],
    "additionalProperties": False,
    "properties": {
        "valor": {"type": ["number", "null"]},
        "estabelecimento": {"type": ["string", "null"]},
        "data": {"type": ["string", "null"]},
        "confianca": {"type": "number", "minimum": CONFIANCA_MINIMA, "maximum": 1.0},
    },
}


def extrair_nota_fiscal_foto(image_bytes: bytes, media_type: str) -> tuple[dict, dict]:
    """Le uma foto de nota fiscal e extrai valor/estabelecimento/data - mesmo
    espirito de extrair_item_cotacao_pdf (extracao pura via API de visao da
    Anthropic, decisao ja tomada com o Alex pra nao usar OCR local/Tesseract):
    a IA so le a foto e devolve estruturado, nunca decide categoria nem
    grava nada sozinha - quem confirma e categoriza e o fluxo de gasto
    existente (US-C9).

    Migrado pra ia.core.chamar_ia (faixa A9): mesma assinatura/retorno de
    hoje. Continua em modo padrao (nunca "flex"/lote) - e leitura na hora,
    enquanto a pessoa espera; ver ia/lote.py pro processamento em lote."""
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    mensagens = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": image_b64},
                },
                {"type": "text", "text": NOTA_FISCAL_PROMPT},
            ],
        }
    ]
    resp = _chamar_com_retry(FUNCAO_NOTA_FISCAL, mensagens, schema=SCHEMA_NOTA_FISCAL)
    return resp.dados, _usage_de_resposta(resp)
