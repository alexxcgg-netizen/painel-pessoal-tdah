#!/usr/bin/env python3
# scripts/ab_teste_ia.py — Faixa A11 (Fase 7): teste A/B de IA por funcao.
#
# Compara pares/trincas de modelo por funcao de IA do painel (Sol x Sonnet 5 no
# chat/decisao/mensagem dificil; Luna x Haiku 4.5 [x Gemini Flash-Lite se houver
# GEMINI_API_KEY] nas funcoes simples; Luna x Sonnet 5 em nota fiscal/cotacao).
# Roda com --dry-run (dubles, usado nos testes - NENHUMA chamada real) ou sem
# a flag, pra rodar de verdade no fim, com as chaves reais do Alex.
#
# Nao usa ia.core.chamar_ia porque ela sempre le ia/config.d/<funcao>.json (uma
# config fixa por funcao) e nenhuma destas 14 funcoes tem esse arquivo ainda
# (nao foram migradas pra ia/core - ainda vivem em claude_client.py). Este
# script PRECISA testar dois/tres modelos diferentes pra mesma funcao na
# mesma execucao, entao chama o adapter direto - mas usando a MESMA descoberta
# de adapter que o nucleo usa (ia.core._obter_adapter/registrar_adapter) e as
# mesmas rotinas de uma-chamada/retry/extracao-de-JSON (ia.core._chamar_uma_vez,
# ._erro_de_rede, ._extrair_json, .validar_schema, ._teto_permite), sem
# duplicar essa logica e SEM editar ia/core.py (ver docs/agentes/fase7-regras-
# faixa.md e docs/ab-teste.md).
#
# ia/adapters/{anthropic,openai}.py (faixas A2/A3) e ia/medicao.py e ia/teto.py
# (faixa A4) ainda nao foram mergeados em fase7/integracao em 2026-09-24 (ver
# scripts/ralph-a11-ab/progress.txt) - o MODO REAL deste script so funciona
# depois que essas faixas chegarem na integracao (o modo --dry-run, usado nos
# testes, nao depende delas: registra adapters-dublê com
# ia.core.registrar_adapter, o mesmo mecanismo tolerante a modulo ausente que
# o nucleo ja usa pra medicao/teto).
from __future__ import annotations

import argparse
import base64
import html
import json
import os
import random
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from ia import core  # noqa: E402 - faixa A1, reaproveitado (nunca editado por esta faixa)
from ia.contrato import Adapter, Resposta  # noqa: E402

DIR_FIXTURES_SINTETICAS = RAIZ / "tests" / "fixtures" / "ab"


# ---------------------------------------------------------------------------
# Registro de modelos ("apelidos" usados nas comparacoes abaixo)
# ---------------------------------------------------------------------------

MODELOS: dict[str, dict] = {
    "sonnet5_medio": {
        "provedor": "anthropic", "modelo": "claude-sonnet-5", "esforco": "medio",
        "rotulo": "Sonnet 5 (médio)",
    },
    "sol_medio": {
        "provedor": "openai", "modelo": "gpt-6-sol", "esforco": "medio",
        "rotulo": "Sol (médio)",
    },
    "luna_medio": {
        "provedor": "openai", "modelo": "gpt-6-luna", "esforco": "medio",
        "rotulo": "Luna (médio)",
    },
    "haiku_4_5": {
        "provedor": "anthropic", "modelo": "claude-haiku-4-5-20251001", "esforco": "medio",
        "rotulo": "Haiku 4.5",
    },
    "gemini_flash_lite": {
        "provedor": "gemini", "modelo": "gemini-3-5-flash-lite", "esforco": "medio",
        "rotulo": "Gemini 3.5 Flash-Lite",
    },
}

# USD por 1M tokens - so pra SIMULAR custo em --dry-run (a chamada real usa o
# custo que o proprio adapter calcula, lendo ia/precos.json de verdade quando
# existir - faixa A4, ainda nao mergeada; 0.0 se nao existir, nunca quebra).
# Numeros conferidos em 2026-09-23 (ver ia/precos.json na branch fase7/a4-
# medicao-teto, ainda nao mergeada - ver progress.txt) - reconferir se
# mudarem antes do preco real do provedor mudar.
PRECOS_SIMULADOS = {
    "claude-sonnet-5": (2.00, 10.00),
    "gpt-6-sol": (2.00, 10.00),
    "gpt-6-luna": (0.10, 0.50),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "gemini-3-5-flash-lite": (0.30, 2.50),
}


def _gemini_disponivel() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


class NaoSuportado(Exception):
    """Levantada por um `montar` quando a combinacao funcao+provedor nao tem
    como ser testada de verdade (ex: PDF pro adapter OpenAI - ver comentario
    em `montar_cotacao_pdf`). O item fica marcado como 'pulado' no relatorio,
    fora das estatisticas de acerto/JSON valido/custo."""


# ---------------------------------------------------------------------------
# Adapter Gemini minimo (REST direto, sem SDK - nenhuma faixa ainda possui um
# adapter Gemini "oficial"). So usado em modo REAL, so se GEMINI_API_KEY
# existir, e registrado pelo MESMO mecanismo do nucleo (core.registrar_adapter)
# - nao inventa um caminho de chamada paralelo.
# ---------------------------------------------------------------------------

class AdapterGeminiRest(Adapter):
    """Implementa ia.contrato.Adapter chamando a API REST do Gemini
    diretamente com `requests` (ja e dependencia do projeto). Suporta so texto
    (nenhuma funcao de visao deste script usa "gemini" como candidato - ver
    FUNCOES). Formato confirmado em 2026-09-24 na documentacao publica da API
    generativelanguage.googleapis.com (v1beta, generateContent) - nao ha SDK
    `google-generativeai` instalado neste worktree pra confirmar via codigo."""

    ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY", "")

    def chamar(self, *, modelo: str, esforco: str, sistema: str, contexto_fixo: str,
               mensagens: list, schema: Optional[dict], max_tokens_saida: int,
               cache: dict, modo: str) -> Resposta:
        import requests  # import tardio, mesmo espirito dos adapters da A1/A2/A3

        texto_sistema = "\n\n".join(t for t in (sistema, contexto_fixo) if t)
        contents = []
        for m in mensagens or []:
            conteudo = m.get("content")
            texto = conteudo if isinstance(conteudo, str) else json.dumps(conteudo, ensure_ascii=False)
            contents.append({
                "role": "model" if m.get("role") == "assistant" else "user",
                "parts": [{"text": texto}],
            })
        corpo: dict = {"contents": contents, "generationConfig": {"maxOutputTokens": max_tokens_saida}}
        if texto_sistema:
            corpo["systemInstruction"] = {"parts": [{"text": texto_sistema}]}
        if schema:
            corpo["generationConfig"]["responseMimeType"] = "application/json"

        inicio = time.monotonic()
        try:
            r = requests.post(
                self.ENDPOINT.format(modelo=modelo),
                params={"key": self._api_key},
                json=corpo,
                timeout=60,
            )
        except requests.exceptions.RequestException as e:
            e.retentavel = True
            raise
        latencia_ms = int((time.monotonic() - inicio) * 1000)
        if r.status_code != 200:
            return Resposta(ok=False, provedor="gemini", modelo=modelo, esforco=esforco,
                            latencia_ms=latencia_ms, erro=f"HTTP {r.status_code}: {r.text[:300]}")
        try:
            corpo_resp = r.json()
            texto = "".join(p.get("text", "") for p in corpo_resp["candidates"][0]["content"]["parts"])
        except (ValueError, KeyError, IndexError) as e:
            return Resposta(ok=False, provedor="gemini", modelo=modelo, esforco=esforco,
                            latencia_ms=latencia_ms, erro=f"resposta inesperada da API: {e}")
        uso = corpo_resp.get("usageMetadata", {})
        tokens_in = int(uso.get("promptTokenCount", 0) or 0)
        tokens_out = int(uso.get("candidatesTokenCount", 0) or 0)
        preco_in, preco_out = PRECOS_SIMULADOS.get(modelo, (0.0, 0.0))
        custo = round(tokens_in * preco_in / 1_000_000 + tokens_out * preco_out / 1_000_000, 6)
        return Resposta(ok=True, texto=texto, dados=None, provedor="gemini", modelo=modelo,
                        esforco=esforco, tokens_in=tokens_in, tokens_out=tokens_out,
                        custo_usd=custo, latencia_ms=latencia_ms)


# ---------------------------------------------------------------------------
# Adapter-dublê (modo --dry-run): mesma ideia de tests/test_ia_core.py
# (AdapterDuble) - consome uma fila de Resposta/excecao enfileirada pelo
# orquestrador ANTES de cada chamada, pra ia.core._obter_adapter devolver
# exatamente o que este script decidiu simular pra aquela fixture+modelo.
# ---------------------------------------------------------------------------

class AdapterDubleAB(Adapter):
    def __init__(self):
        self.fila: list = []

    def enfileirar(self, item) -> None:
        self.fila.append(item)

    def chamar(self, **kwargs) -> Resposta:
        if not self.fila:
            raise AssertionError(
                "AdapterDubleAB chamado sem resposta enfileirada - bug no orquestrador do --dry-run")
        item = self.fila.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


# ---------------------------------------------------------------------------
# Chamada com override explicito de modelo (real OU dublê - o modo so muda
# quais adapters estao registrados no nucleo, ver `preparar_adapters`)
# ---------------------------------------------------------------------------

_DRY_RUN_ATIVO = False


def _chamar_com_override(funcao: str, entrada_modelo: dict, *, sistema: str, contexto_fixo: str,
                          mensagens: list, schema: Optional[dict],
                          max_tokens_saida: int) -> tuple[Optional[Resposta], Optional[str]]:
    """Uma chamada de IA com provedor/modelo forcados (nao vem de ia/config.d).
    Reaproveita ia.core._teto_permite, ._obter_adapter, ._chamar_uma_vez,
    ._erro_de_rede e .ESPERA_RETRY_S (nucleo, faixa A1) - mesma checagem de
    teto, mesmo cache/descoberta de adapter, mesmo 1-retry em erro de rede.

    NAO passa `schema` pro parametro homonimo de `_chamar_uma_vez`: aquela
    funcao exige que o JSON validado seja um OBJETO (`dict`) - ver
    ia/core.py, comentario "JSON precisa ser objeto" - e 3 das 14 funcoes
    testadas aqui (break_down_task, gerar_mala, requebrar_tarefa) devolvem
    uma LISTA no nivel raiz (mesmo formato ja usado hoje em claude_client.py).
    `schema` ainda vai dentro de `kwargs["schema"]`, entao o adapter continua
    usando ele pra instruir o modelo (texto/Structured Outputs) - so a
    validacao pos-resposta e feita por este script (`avaliar_json`, abaixo),
    chamando core._extrair_json/core.validar_schema diretamente, que
    funcionam com raiz lista ou objeto."""
    # Em --dry-run nao ha custo real: nao consulta o teto (que le o banco do app).
    if not _DRY_RUN_ATIVO and not core._teto_permite(funcao):
        resp = Resposta(ok=False, provedor=entrada_modelo["provedor"], modelo=entrada_modelo["modelo"],
                        esforco=entrada_modelo["esforco"], erro="teto_ia_estourado")
        return resp, "teto_ia_estourado"

    try:
        adapter = core._obter_adapter(entrada_modelo["provedor"])
    except Exception as exc:  # noqa: BLE001
        return None, f"{entrada_modelo['provedor']}: {exc}"

    kwargs = {
        "sistema": sistema,
        "contexto_fixo": contexto_fixo,
        "mensagens": mensagens,
        "schema": schema,
        "max_tokens_saida": max_tokens_saida,
        "cache": {"ativo": False, "ttl": "5m"},
        "modo": "padrao",
    }
    resp, erro, exc = core._chamar_uma_vez(funcao, entrada_modelo, adapter, kwargs, schema=None)
    if exc is not None and core._erro_de_rede(exc):
        if core.ESPERA_RETRY_S:
            time.sleep(core.ESPERA_RETRY_S)
        resp, erro, exc = core._chamar_uma_vez(funcao, entrada_modelo, adapter, kwargs, schema=None)
    return resp, erro


def avaliar_json(resp: Optional[Resposta], schema: Optional[dict]) -> tuple[Optional[Any], Optional[bool]]:
    """(dados, json_valido). json_valido=None quando a funcao e formato
    "texto" (schema=None) - metrica nao se aplica. Reaproveita
    core._extrair_json/core.validar_schema (funcionam com raiz lista ou
    objeto, ao contrario do gate interno de _chamar_uma_vez)."""
    if schema is None:
        return None, None
    if resp is None or not resp.ok:
        return None, False
    dados, erro_extracao = core._extrair_json(resp)
    if erro_extracao:
        return None, False
    problema = core.validar_schema(dados, schema)
    return dados, problema is None


def _conteudo_imagem(provedor: str, imagem_b64: str, media_type: str) -> dict:
    """Bloco de imagem no formato que CADA adapter espera - ia/contrato.py nao
    fixa isso (visao multimodal ainda nao tem convencao unica entre A2/A3):
    Anthropic usa o formato nativo da API (`type: image, source: {...}`, igual
    claude_client.extrair_nota_fiscal_foto ja usa hoje); OpenAI usa a
    convencao inventada pela faixa A3 (`type: image, data_b64, mime` -
    documentado no topo de ia/adapters/openai.py) que o proprio adapter
    converte pro formato da Chat Completions API."""
    if provedor == "openai":
        return {"type": "image", "data_b64": imagem_b64, "mime": media_type}
    if provedor == "anthropic":
        return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": imagem_b64}}
    raise NaoSuportado(f"visao nao suportada pro provedor {provedor!r} (adapter nao tem convencao de imagem)")


# ---------------------------------------------------------------------------
# Prompts - adaptados dos que ja existem em claude_client.py (mesmo espirito,
# mesmos campos) em 2026-09-24. Estas 14 funcoes ainda NAO foram migradas pra
# ia/core (ainda chamam a Anthropic direto em claude_client.py) - quando forem
# (ia/funcoes/*.py, outra faixa), reconferir se o prompt daqui ainda bate;
# nao ha fonte unica hoje porque a migracao ainda nao aconteceu.
# ---------------------------------------------------------------------------

CAPTURE_PROMPT_AB = """Hoje e {hoje}. Classifique o texto do usuario como "tarefa", "gasto" ou "meta"
(meta financeira, tipo "quero juntar X ate Y" ou "economizar pra comprar Z") e extraia os campos.
Responda so com JSON, sem markdown, no formato:
{{"tipo": "tarefa" ou "gasto" ou "meta", "titulo": "...", "valor": numero ou null, "categoria": "..." ou null, "status": "real" ou "planejado" ou null, "quando_data": "AAAA-MM-DD" ou null, "hora": "HH:MM" ou null, "prazo": "AAAA-MM-DD" ou null}}

Categorias de gasto: mercado, transporte, lazer, contas, saude, outros.
Se tipo="gasto": "status" e "real" quando ja aconteceu, "planejado" quando e so intencao futura.

Texto: {text}"""

BREAKDOWN_PROMPT_AB = """Quebre esta tarefa em 3 a 6 passos pequenos e concretos, cada um algo que da
pra fazer de uma vez. Responda so com um JSON de lista de strings, sem markdown.

Tarefa: {title}"""

SUMMARY_PROMPT_AB = """Escreva um resumo do dia em 2 a 3 frases. Tom neutro e factual, sem cobranca e
sem elogio vazio. Se houver compromissos na agenda, mencione quantos tem.

Tarefas concluidas: {done}
Tarefas pendentes: {pending}
Gastos de hoje: {expenses}
Compromissos na agenda hoje: {eventos}
Contexto de saude de hoje (mencione so se notavel): {saude}"""

PLANO_PROMPT_AB = """Voce ajuda uma pessoa com TDAH a organizar o resto do dia. Agora sao {agora}.
Compromissos tem horario FIXO; tarefas pendentes nao tem horario - sugira a ordem.
Responda em lista numerada curta (maximo 6 itens), cada item uma linha, direto ao ponto.

Compromissos de hoje (hora fixa): {eventos}
Tarefas pendentes (sem hora fixa): {tarefas}"""

ESSENCIAL_PROMPT_AB = """Das tarefas abaixo, escolha as 1 a 3 MAIS importantes pra hoje ({hoje}).
Criterio: o que tem consequencia real se nao for feito hoje.

Tarefas (id | titulo | prazo | hora):
{tarefas}

Responda SO com JSON, sem markdown: [{{"id": <id>, "motivo": "<ate 8 palavras>"}}]"""

REQUEBRAR_PROMPT_AB = """A tarefa abaixo esta travada ha {dias} dias - proponha um jeito DIFERENTE de
atacar, em 3 a 5 passos. O primeiro passo tem que ser ridiculamente facil (2 a 5 minutos).

Tarefa: {titulo}
Passos antigos que nao andaram: {passos}

Responda so com um JSON de lista de strings, sem markdown."""

DECISAO_PROMPT_AB = """Ajude a decidir rapido se vale a pena. Seja honesto e direto, termine com uma
inclinacao explicita.

Decisao: {pergunta}

Responda SO com JSON, sem markdown:
{{"resumo": "<1 frase>", "pros": ["<ate 4>"], "contras": ["<ate 4>"], "perguntas_chave": ["<ate 3>"],
  "inclinacao": "<'vale', 'nao_vale' ou 'depende'>", "porque": "<1 frase>"}}"""

MALA_PROMPT_AB = """Monte um checklist de mala CURTO e pratico pra uma viagem (maximo 15 itens).
Destino: {destino}
Dias: {dias}
Motivo: {motivo}
Clima previsto: {clima}

Responda so com um JSON de lista de strings, sem markdown."""

MENSAGEM_DIFICIL_PROMPT_AB = """Ajude a escrever uma mensagem dificil (cobrar alguem, dizer nao, pedir
desculpa, resolver conflito) - entregue pronta pra copiar, em portugues do Brasil, curta e clara.

Pra quem: {para_quem}
Situacao: {situacao}

Responda SO com JSON, sem markdown: {{"direta": "<versao objetiva>", "gentil": "<versao mais suave>"}}"""

RESUMO_LINK_PROMPT_AB = """Resuma pra uma pessoa com TDAH decidir se vale ler/ver agora: 3 a 5 pontos
curtos com o que importa de verdade, em portugues do Brasil.

Titulo: {titulo}
Texto: {texto}

Responda so com o resumo em topicos comecando com "- ", sem introducao."""

INTENT_PROMPT_AB = """Hoje e {hoje}. Classifique o comando numa das acoes fechadas abaixo:
registrar_tarefa, registrar_gasto, registrar_checkin, navegar_tela, consultar, corrigir_ultimo,
desconhecido.

Responda SO com JSON, sem markdown:
{{"acao": "uma das acoes acima", "confianca": numero de 0.0 a 1.0, "parametros": {{}}}}

Texto do usuario: "{texto}\""""

NOTA_FISCAL_PROMPT_AB = """Leia essa foto de nota fiscal/cupom fiscal e extraia em JSON:
{"valor": valor TOTAL da compra em reais (numero puro) ou null, "estabelecimento": nome da loja
(texto curto) ou null, "data": data da compra "AAAA-MM-DD" ou null}

So extraia o que estiver escrito na foto - nunca estime. Responda SO com o JSON, sem markdown."""

COTACAO_PDF_PROMPT_AB = """Leia esse PDF de orcamento/cotacao de fornecedor de material de construcao
e extraia em JSON:
{"fornecedor": nome da empresa (texto curto) ou null, "valor": valor TOTAL em reais (numero puro) ou
null, "prazo_texto": prazo de entrega em texto livre ou null, "observacao": um detalhe curto ou null}

So extraia o que estiver escrito no documento - nunca estime. Responda SO com o JSON, sem markdown."""

CHAT_SISTEMA_AB = """Voce e o assistente pessoal do Alex, que tem TDAH - seja direto e curto, sem
enrolacao, tom de colega que ajuda e nao de atendente corporativo. Sem emoji em excesso. So devolva
uma resposta mais longa quando ele pedir explicitamente ("explica melhor", "detalha").

(Comparacao A11: esta e uma versao reduzida do system prompt de producao, sem as ferramentas de
tool-use - o que esta em teste aqui e so o TOM da resposta em texto livre, nao a orquestracao de
ferramentas. Ver docs/ab-teste.md.)"""


# ---------------------------------------------------------------------------
# Schemas (subconjunto de JSON Schema aceito por core.validar_schema) - usados
# pra instruir o modelo (via kwargs["schema"], que os adapters embutem no
# prompt/Structured Outputs) e pra medir "% JSON valido" (avaliar_json acima).
# ---------------------------------------------------------------------------

SCHEMA_CAPTURE = {
    "type": "object", "required": ["tipo"],
    "properties": {
        "tipo": {"type": "string", "enum": ["tarefa", "gasto", "meta"]},
        "titulo": {"type": ["string", "null"]},
        "valor": {"type": ["number", "null"]},
        "categoria": {"type": ["string", "null"]},
        "status": {"type": ["string", "null"]},
        "quando_data": {"type": ["string", "null"]},
        "hora": {"type": ["string", "null"]},
        "prazo": {"type": ["string", "null"]},
    },
}
SCHEMA_LISTA_STR = {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 20}
SCHEMA_ESSENCIAL = {
    "type": "array",
    "items": {"type": "object", "required": ["id", "motivo"],
              "properties": {"motivo": {"type": "string"}}},
}
SCHEMA_DECISAO = {
    "type": "object", "required": ["resumo", "inclinacao"],
    "properties": {
        "resumo": {"type": "string"},
        "pros": {"type": "array"},
        "contras": {"type": "array"},
        "perguntas_chave": {"type": "array"},
        "inclinacao": {"type": "string", "enum": ["vale", "nao_vale", "depende"]},
        "porque": {"type": "string"},
    },
}
SCHEMA_MENSAGEM_DIFICIL = {
    "type": "object", "required": ["direta", "gentil"],
    "properties": {"direta": {"type": "string"}, "gentil": {"type": "string"}},
}
SCHEMA_INTENT = {
    "type": "object", "required": ["acao", "confianca"],
    "properties": {
        "acao": {"type": "string", "enum": [
            "registrar_tarefa", "registrar_gasto", "registrar_checkin",
            "navegar_tela", "consultar", "corrigir_ultimo", "desconhecido"]},
        "confianca": {"type": "number", "minimum": 0, "maximum": 1},
        "parametros": {"type": "object"},
    },
}
SCHEMA_NOTA_FISCAL = {
    "type": "object",
    "properties": {
        "valor": {"type": ["number", "null"]},
        "estabelecimento": {"type": ["string", "null"]},
        "data": {"type": ["string", "null"]},
    },
}
SCHEMA_COTACAO = {
    "type": "object",
    "properties": {
        "fornecedor": {"type": ["string", "null"]},
        "valor": {"type": ["number", "null"]},
        "prazo_texto": {"type": ["string", "null"]},
        "observacao": {"type": ["string", "null"]},
    },
}


# ---------------------------------------------------------------------------
# montar_<funcao>(entrada, provedor) -> {"sistema", "contexto_fixo",
# "mensagens", "schema", "max_tokens_saida"} - `provedor` importa so pras
# funcoes de visao (formato de imagem/documento difere por adapter).
# ---------------------------------------------------------------------------

def _msg(texto: str) -> list:
    return [{"role": "user", "content": texto}]


def montar_chat(entrada: dict, provedor: str) -> dict:
    return {"sistema": CHAT_SISTEMA_AB, "contexto_fixo": "",
            "mensagens": _msg(entrada["mensagem"]), "schema": None, "max_tokens_saida": 500}


def montar_classify_capture(entrada: dict, provedor: str) -> dict:
    from datetime import date
    texto = CAPTURE_PROMPT_AB.format(hoje=entrada.get("hoje") or date.today().isoformat(),
                                      text=entrada["text"])
    return {"sistema": "", "contexto_fixo": "", "mensagens": _msg(texto),
            "schema": SCHEMA_CAPTURE, "max_tokens_saida": 250}


def montar_break_down_task(entrada: dict, provedor: str) -> dict:
    texto = BREAKDOWN_PROMPT_AB.format(title=entrada["title"])
    return {"sistema": "", "contexto_fixo": "", "mensagens": _msg(texto),
            "schema": SCHEMA_LISTA_STR, "max_tokens_saida": 300}


def montar_summarize_day(entrada: dict, provedor: str) -> dict:
    texto = SUMMARY_PROMPT_AB.format(
        done=entrada.get("done") or "nenhuma", pending=entrada.get("pending") or "nenhuma",
        expenses=entrada.get("expenses") or "nenhum", eventos=entrada.get("eventos") or "nenhum",
        saude=entrada.get("saude") or "sem dados de saude hoje")
    return {"sistema": "", "contexto_fixo": "", "mensagens": _msg(texto),
            "schema": None, "max_tokens_saida": 200}


def montar_plano_do_dia(entrada: dict, provedor: str) -> dict:
    from datetime import datetime
    texto = PLANO_PROMPT_AB.format(agora=entrada.get("agora") or datetime.now().strftime("%H:%M"),
                                    eventos=entrada.get("eventos") or "nenhum",
                                    tarefas=entrada.get("tarefas") or "nenhuma")
    return {"sistema": "", "contexto_fixo": "", "mensagens": _msg(texto),
            "schema": None, "max_tokens_saida": 400}


def montar_escolher_essencial(entrada: dict, provedor: str) -> dict:
    from datetime import date
    linhas = "\n".join(
        f"{t['id']} | {t['title']} | {t.get('due_date') or 'sem prazo'} | {t.get('hora') or '-'}"
        for t in entrada["tarefas"])
    texto = ESSENCIAL_PROMPT_AB.format(hoje=entrada.get("hoje") or date.today().isoformat(), tarefas=linhas)
    return {"sistema": "", "contexto_fixo": "", "mensagens": _msg(texto),
            "schema": SCHEMA_ESSENCIAL, "max_tokens_saida": 250}


def montar_requebrar_tarefa(entrada: dict, provedor: str) -> dict:
    texto = REQUEBRAR_PROMPT_AB.format(titulo=entrada["titulo"], dias=entrada["dias"],
                                        passos="; ".join(entrada.get("passos_antigos") or []) or "nenhum")
    return {"sistema": "", "contexto_fixo": "", "mensagens": _msg(texto),
            "schema": SCHEMA_LISTA_STR, "max_tokens_saida": 350}


def montar_analisar_decisao(entrada: dict, provedor: str) -> dict:
    texto = DECISAO_PROMPT_AB.format(pergunta=entrada["pergunta"])
    return {"sistema": "", "contexto_fixo": "", "mensagens": _msg(texto),
            "schema": SCHEMA_DECISAO, "max_tokens_saida": 600}


def montar_gerar_mala(entrada: dict, provedor: str) -> dict:
    texto = MALA_PROMPT_AB.format(destino=entrada["destino"], dias=entrada["dias"],
                                   motivo=entrada.get("motivo") or "nao informado",
                                   clima=entrada.get("clima_texto") or "sem previsao")
    return {"sistema": "", "contexto_fixo": "", "mensagens": _msg(texto),
            "schema": SCHEMA_LISTA_STR, "max_tokens_saida": 400}


def montar_redigir_mensagem_dificil(entrada: dict, provedor: str) -> dict:
    texto = MENSAGEM_DIFICIL_PROMPT_AB.format(situacao=entrada["situacao"],
                                               para_quem=entrada.get("para_quem") or "nao informado")
    return {"sistema": "", "contexto_fixo": "", "mensagens": _msg(texto),
            "schema": SCHEMA_MENSAGEM_DIFICIL, "max_tokens_saida": 600}


def montar_resumir_link(entrada: dict, provedor: str) -> dict:
    texto = RESUMO_LINK_PROMPT_AB.format(titulo=entrada.get("titulo") or "sem titulo", texto=entrada["texto"])
    return {"sistema": "", "contexto_fixo": "", "mensagens": _msg(texto),
            "schema": None, "max_tokens_saida": 400}


def montar_classify_intent(entrada: dict, provedor: str) -> dict:
    from datetime import date
    texto = INTENT_PROMPT_AB.format(hoje=entrada.get("hoje") or date.today().isoformat(), texto=entrada["texto"])
    return {"sistema": "", "contexto_fixo": "", "mensagens": _msg(texto),
            "schema": SCHEMA_INTENT, "max_tokens_saida": 200}


def montar_nota_fiscal(entrada: dict, provedor: str) -> dict:
    media_type = entrada.get("media_type", "image/jpeg")
    conteudo = [_conteudo_imagem(provedor, entrada["imagem_b64"], media_type),
                {"type": "text", "text": NOTA_FISCAL_PROMPT_AB}]
    return {"sistema": "", "contexto_fixo": "", "mensagens": [{"role": "user", "content": conteudo}],
            "schema": SCHEMA_NOTA_FISCAL, "max_tokens_saida": 300}


def montar_cotacao_pdf(entrada: dict, provedor: str) -> dict:
    if provedor != "anthropic":
        # O adapter OpenAI (faixa A3) so sabe converter partes "image"/"text"
        # (ver ia/adapters/openai.py, _converter_parte_conteudo) - nao ha
        # convencao de "documento"/PDF nele ainda. Mandar o PDF mesmo assim
        # (ex: disfarçado de imagem) so produziria um erro confuso da API ou
        # uma extracao as cegas sem ver o conteudo - preferimos marcar
        # explicitamente como nao suportado (item "pulado" no relatorio, fora
        # das estatisticas) a fingir que o teste rodou. Ver docs/ab-teste.md.
        raise NaoSuportado(
            f"extrair_item_cotacao_pdf via provedor {provedor!r}: adapter OpenAI (A3) ainda nao "
            f"converte PDF/documento (so imagem/texto) - comparacao Luna fica pendente ate a A3 "
            f"ganhar suporte a documento.")
    pdf_b64 = entrada["pdf_b64"]
    conteudo = [
        {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64}},
        {"type": "text", "text": COTACAO_PDF_PROMPT_AB},
    ]
    return {"sistema": "", "contexto_fixo": "", "mensagens": [{"role": "user", "content": conteudo}],
            "schema": SCHEMA_COTACAO, "max_tokens_saida": 400}


# ---------------------------------------------------------------------------
# avaliar_<funcao>(dados, texto, esperado) -> Optional[bool] - None quando o
# fixture nao tem gabarito pra essa funcao (fica fora da media de acerto), ou
# quando a funcao e do grupo "cego" (tom julgado pelo Alex, nunca por script).
# ---------------------------------------------------------------------------

def _contem_tudo(texto: Optional[str], itens: list[str]) -> bool:
    if not texto:
        return False
    alvo = texto.casefold()
    return all(item.casefold() in alvo for item in itens)


def _proximo(a, b, tolerancia=0.01) -> bool:
    if a is None or b is None:
        return a == b
    try:
        return abs(float(a) - float(b)) <= tolerancia
    except (TypeError, ValueError):
        return a == b


def avaliar_cego(dados, texto, esperado) -> Optional[bool]:
    return None  # chat / analisar_decisao / redigir_mensagem_dificil: decisao do Alex pelo tom


def avaliar_classify_intent(dados, texto, esperado) -> Optional[bool]:
    if not esperado or "acao" not in esperado or not isinstance(dados, dict):
        return None if not esperado else False
    return dados.get("acao") == esperado["acao"]


def avaliar_classify_capture(dados, texto, esperado) -> Optional[bool]:
    if not esperado or "tipo" not in esperado:
        return None
    if not isinstance(dados, dict):
        return False
    ok = dados.get("tipo") == esperado["tipo"]
    if ok and "valor" in esperado:
        ok = _proximo(dados.get("valor"), esperado["valor"])
    return ok


def avaliar_texto_contem(dados, texto, esperado) -> Optional[bool]:
    if not esperado or "contem" not in esperado:
        return None
    return _contem_tudo(texto, esperado["contem"])


def avaliar_lista_contem(dados, texto, esperado) -> Optional[bool]:
    """Pra funcoes que devolvem uma LISTA (gerar_mala): cada substring
    esperada precisa aparecer em pelo menos um item da lista."""
    if not esperado or "contem" not in esperado:
        return None
    if not isinstance(dados, list):
        return False
    junto = " | ".join(str(item) for item in dados)
    return _contem_tudo(junto, esperado["contem"])


def avaliar_tamanho_lista(dados, texto, esperado) -> Optional[bool]:
    """Pra break_down_task/requebrar_tarefa: sem gabarito de conteudo (a
    tarefa e sintetica), so verifica se o numero de passos ficou na faixa
    pedida no prompt (esperado["min"]/esperado["max"])."""
    if not esperado or ("min" not in esperado and "max" not in esperado):
        return None
    if not isinstance(dados, list):
        return False
    minimo = esperado.get("min", 0)
    maximo = esperado.get("max", 10**9)
    return minimo <= len(dados) <= maximo


def avaliar_escolher_essencial(dados, texto, esperado) -> Optional[bool]:
    if not esperado or "ids" not in esperado:
        return None
    if not isinstance(dados, list):
        return False
    try:
        obtidos = {int(item["id"]) for item in dados if isinstance(item, dict) and "id" in item}
    except (TypeError, ValueError):
        return False
    return obtidos == set(esperado["ids"])


def avaliar_nota_fiscal(dados, texto, esperado) -> Optional[bool]:
    if not esperado:
        return None
    if not isinstance(dados, dict):
        return False
    ok = True
    if "valor" in esperado:
        ok = ok and _proximo(dados.get("valor"), esperado["valor"])
    if "estabelecimento" in esperado and esperado["estabelecimento"] is not None:
        obtido = (dados.get("estabelecimento") or "")
        ok = ok and esperado["estabelecimento"].casefold() in obtido.casefold()
    if "data" in esperado:
        ok = ok and dados.get("data") == esperado["data"]
    return ok


def avaliar_cotacao(dados, texto, esperado) -> Optional[bool]:
    if not esperado:
        return None
    if not isinstance(dados, dict):
        return False
    ok = True
    if "valor" in esperado:
        ok = ok and _proximo(dados.get("valor"), esperado["valor"])
    if "fornecedor" in esperado and esperado["fornecedor"] is not None:
        obtido = (dados.get("fornecedor") or "")
        ok = ok and esperado["fornecedor"].casefold() in obtido.casefold()
    return ok


# ---------------------------------------------------------------------------
# fabricar_<funcao>(fixture) -> (texto, dados) - a resposta "correta" canonica
# usada em --dry-run (nunca chama nenhuma API). Fixtures podem sobrescrever
# isso por modelo com "simulacao_dry_run" (ver aplicar_simulacao, mais abaixo)
# pra exercitar os caminhos de JSON invalido/campo errado/API falhou no teste
# da propria logica de agregacao/relatorio deste script.
# ---------------------------------------------------------------------------

def fabricar_classify_intent(fixture: dict) -> tuple[str, Any]:
    esperado = fixture.get("esperado") or {}
    dados = {"acao": esperado.get("acao", "desconhecido"), "confianca": 0.9,
             "parametros": esperado.get("parametros", {})}
    return json.dumps(dados, ensure_ascii=False), dados


def fabricar_classify_capture(fixture: dict) -> tuple[str, Any]:
    esperado = fixture.get("esperado") or {}
    dados = {"tipo": esperado.get("tipo", "tarefa"), "titulo": fixture["entrada"].get("text", "")[:40],
             "valor": esperado.get("valor"), "categoria": esperado.get("categoria"),
             "status": esperado.get("status"), "quando_data": None, "hora": None, "prazo": None}
    return json.dumps(dados, ensure_ascii=False), dados


def fabricar_texto_contem(fixture: dict) -> tuple[str, Any]:
    esperado = fixture.get("esperado") or {}
    itens = esperado.get("contem") or ["ponto simulado"]
    texto = "\n".join(f"- {i}" for i in itens)
    return texto, None


def fabricar_lista_contem(fixture: dict) -> tuple[str, Any]:
    esperado = fixture.get("esperado") or {}
    base = list(esperado.get("contem") or ["item simulado"])
    while len(base) < 3:
        base.append(f"Item extra {len(base) + 1}")
    return json.dumps(base, ensure_ascii=False), base


def fabricar_lista_tamanho(fixture: dict) -> tuple[str, Any]:
    esperado = fixture.get("esperado") or {}
    minimo = max(esperado.get("min", 3), 1)
    dados = [f"Passo {i + 1} simulado" for i in range(minimo)]
    return json.dumps(dados, ensure_ascii=False), dados


def fabricar_escolher_essencial(fixture: dict) -> tuple[str, Any]:
    esperado = fixture.get("esperado") or {}
    ids = esperado.get("ids") or []
    dados = [{"id": i, "motivo": "prioridade simulada"} for i in ids]
    return json.dumps(dados, ensure_ascii=False), dados


def fabricar_analisar_decisao(fixture: dict) -> tuple[str, Any]:
    dados = {"resumo": "resumo simulado", "pros": ["pro simulado"], "contras": ["contra simulado"],
             "perguntas_chave": [], "inclinacao": "depende", "porque": "simulado"}
    return json.dumps(dados, ensure_ascii=False), dados


def fabricar_redigir_mensagem_dificil(fixture: dict) -> tuple[str, Any]:
    dados = {"direta": "mensagem direta simulada", "gentil": "mensagem gentil simulada"}
    return json.dumps(dados, ensure_ascii=False), dados


def fabricar_chat(fixture: dict) -> tuple[str, Any]:
    return "Resposta simulada de chat (dry-run).", None


def fabricar_nota_fiscal(fixture: dict) -> tuple[str, Any]:
    esperado = fixture.get("esperado") or {}
    dados = {"valor": esperado.get("valor"), "estabelecimento": esperado.get("estabelecimento"),
             "data": esperado.get("data")}
    return json.dumps(dados, ensure_ascii=False), dados


def fabricar_cotacao(fixture: dict) -> tuple[str, Any]:
    esperado = fixture.get("esperado") or {}
    dados = {"fornecedor": esperado.get("fornecedor"), "valor": esperado.get("valor"),
             "prazo_texto": esperado.get("prazo_texto"), "observacao": esperado.get("observacao")}
    return json.dumps(dados, ensure_ascii=False), dados


# ---------------------------------------------------------------------------
# Registro de funcoes
# ---------------------------------------------------------------------------

@dataclass
class Especificacao:
    grupo: str                       # "cego" | "simples" | "visao"
    candidatos: list[str]            # apelidos em MODELOS; candidatos[0] = linha de base atual
    formato: str                     # "json" | "texto"
    montar: Callable[[dict, str], dict]
    fabricar: Callable[[dict], tuple]
    avaliar: Callable[[Any, Optional[str], Optional[dict]], Optional[bool]]


def _candidatos_simples(baseline: str) -> list[str]:
    return [baseline, "luna_medio"]


def candidatos_efetivos(especificacao: "Especificacao") -> list[str]:
    """especificacao.candidatos e fixo (definido na importacao do modulo) -
    "gemini_flash_lite" so entra nas funcoes do grupo "simples" quando
    GEMINI_API_KEY existir NA HORA DE RODAR (nao na hora de importar o
    modulo, que e cedo demais pra ver a env var que os testes setam/removem
    em cada caso - ver TestExecutarDryRun.test_gemini_so_entra_com_env_var)."""
    candidatos = list(especificacao.candidatos)
    if especificacao.grupo == "simples" and _gemini_disponivel() and "gemini_flash_lite" not in candidatos:
        candidatos.append("gemini_flash_lite")
    return candidatos


FUNCOES: dict[str, Especificacao] = {
    "chat": Especificacao("cego", ["sonnet5_medio", "sol_medio"], "texto",
                          montar_chat, fabricar_chat, avaliar_cego),
    "analisar_decisao": Especificacao("cego", ["sonnet5_medio", "sol_medio"], "json",
                                      montar_analisar_decisao, fabricar_analisar_decisao, avaliar_cego),
    "redigir_mensagem_dificil": Especificacao(
        "cego", ["sonnet5_medio", "sol_medio"], "json",
        montar_redigir_mensagem_dificil, fabricar_redigir_mensagem_dificil, avaliar_cego),

    "classify_intent": Especificacao("simples", _candidatos_simples("haiku_4_5"), "json",
                                     montar_classify_intent, fabricar_classify_intent, avaliar_classify_intent),
    "classify_capture": Especificacao("simples", _candidatos_simples("haiku_4_5"), "json",
                                      montar_classify_capture, fabricar_classify_capture, avaliar_classify_capture),
    "summarize_day": Especificacao("simples", _candidatos_simples("haiku_4_5"), "texto",
                                   montar_summarize_day, fabricar_texto_contem, avaliar_texto_contem),
    "escolher_essencial": Especificacao("simples", _candidatos_simples("haiku_4_5"), "json",
                                        montar_escolher_essencial, fabricar_escolher_essencial,
                                        avaliar_escolher_essencial),
    "gerar_mala": Especificacao("simples", _candidatos_simples("haiku_4_5"), "json",
                                montar_gerar_mala, fabricar_lista_contem, avaliar_lista_contem),
    "resumir_link": Especificacao("simples", _candidatos_simples("haiku_4_5"), "texto",
                                  montar_resumir_link, fabricar_texto_contem, avaliar_texto_contem),
    "break_down_task": Especificacao("simples", _candidatos_simples("sonnet5_medio"), "json",
                                     montar_break_down_task, fabricar_lista_tamanho, avaliar_tamanho_lista),
    "requebrar_tarefa": Especificacao("simples", _candidatos_simples("sonnet5_medio"), "json",
                                      montar_requebrar_tarefa, fabricar_lista_tamanho, avaliar_tamanho_lista),
    "plano_do_dia": Especificacao("simples", _candidatos_simples("sonnet5_medio"), "texto",
                                  montar_plano_do_dia, fabricar_texto_contem, avaliar_texto_contem),

    "extrair_nota_fiscal_foto": Especificacao("visao", ["sonnet5_medio", "luna_medio"], "json",
                                              montar_nota_fiscal, fabricar_nota_fiscal, avaliar_nota_fiscal),
    "extrair_item_cotacao_pdf": Especificacao("visao", ["sonnet5_medio", "luna_medio"], "json",
                                              montar_cotacao_pdf, fabricar_cotacao, avaliar_cotacao),
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def carregar_fixtures_sinteticas(funcao: str, base_dir: Path = DIR_FIXTURES_SINTETICAS) -> list[dict]:
    caminho = base_dir / f"{funcao}.json"
    if not caminho.exists():
        return []
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    if not isinstance(dados, list):
        raise ValueError(f"{caminho}: esperava uma lista de fixtures (um objeto por cenario)")
    return dados


def _carregar_binario_b64(caminho: Path) -> str:
    return base64.standard_b64encode(caminho.read_bytes()).decode("ascii")


def carregar_fixtures_reais(funcao: str, base_dir: Path) -> list[dict]:
    """Exemplos reais opcionais do Alex (pasta gitignored - ver .gitignore,
    ja tinha `fixtures_reais/` antes desta faixa). Aceita: um arquivo
    "<funcao>.json" com uma lista de fixtures (mesmo formato das sinteticas),
    e/ou uma pasta "<funcao>/" com um fixture por arquivo *.json dentro. Um
    fixture pode apontar pra uma imagem/PDF real em vez de embutir base64
    inline, com "imagem_path"/"pdf_path" (relativo a base_dir) em vez de
    "imagem_b64"/"pdf_b64"."""
    achadas: list[dict] = []
    arquivo_unico = base_dir / f"{funcao}.json"
    if arquivo_unico.exists():
        dados = json.loads(arquivo_unico.read_text(encoding="utf-8"))
        achadas.extend(dados if isinstance(dados, list) else [dados])
    pasta = base_dir / funcao
    if pasta.is_dir():
        for arq in sorted(pasta.glob("*.json")):
            achadas.append(json.loads(arq.read_text(encoding="utf-8")))
    for fixture in achadas:
        entrada = fixture.setdefault("entrada", {})
        if "imagem_path" in entrada and "imagem_b64" not in entrada:
            entrada["imagem_b64"] = _carregar_binario_b64(base_dir / entrada["imagem_path"])
        if "pdf_path" in entrada and "pdf_b64" not in entrada:
            entrada["pdf_b64"] = _carregar_binario_b64(base_dir / entrada["pdf_path"])
    return achadas


def carregar_fixtures(funcao: str, fixtures_reais_dir: Optional[Path],
                      fixtures_sinteticas_dir: Path = DIR_FIXTURES_SINTETICAS) -> list[dict]:
    fixtures = list(carregar_fixtures_sinteticas(funcao, fixtures_sinteticas_dir))
    if fixtures_reais_dir is not None and fixtures_reais_dir.is_dir():
        fixtures.extend(carregar_fixtures_reais(funcao, fixtures_reais_dir))
    return fixtures


# ---------------------------------------------------------------------------
# Simulacao --dry-run (sobrescritas opcionais por fixture/modelo)
# ---------------------------------------------------------------------------

def aplicar_simulacao(texto, dados, sim: Optional[dict]):
    """(texto, dados, api_falhou, multiplicador_custo, latencia_extra_ms).
    `sim` vem de fixture["simulacao_dry_run"][apelido] (opcional) - existe pra
    exercitar nos testes os caminhos de JSON invalido/campo errado/API
    falhou da propria logica deste script (acerto/json_valido/agregacao),
    sem depender de rede nenhuma."""
    if not sim:
        return texto, dados, False, 1.0, 0
    if sim.get("api_falhou"):
        return None, None, True, 1.0, 0
    if sim.get("json_invalido"):
        texto = "isto nao eh { json valido"
        dados = None
    if "errar_campo" in sim and isinstance(dados, dict):
        campo, valor = sim["errar_campo"]["campo"], sim["errar_campo"]["valor"]
        dados = {**dados, campo: valor}
        texto = json.dumps(dados, ensure_ascii=False)
    if "ids_errados" in sim and isinstance(dados, list):
        dados = [{"id": i, "motivo": "simulado (errado)"} for i in sim["ids_errados"]]
        texto = json.dumps(dados, ensure_ascii=False)
    if sim.get("sem_conteudo_esperado"):
        if isinstance(dados, list):
            # Lista valida (JSON continua ok) mas generica, sem as
            # substrings esperadas - testa "acerto=False" sem derrubar
            # json_valido junto (diferente de json_invalido, acima).
            dados = ["item generico 1", "item generico 2", "item generico 3"]
            texto = json.dumps(dados, ensure_ascii=False)
        else:
            texto = "Resposta simulada sem os pontos esperados."
    return texto, dados, False, float(sim.get("custo_multiplicador", 1.0)), int(sim.get("latencia_extra_ms", 0))


# ---------------------------------------------------------------------------
# Resultados / agregacao
# ---------------------------------------------------------------------------

@dataclass
class ItemResultado:
    fixture_id: str
    apelido: str
    ok: bool
    pulado: bool = False
    motivo_pulado: str = ""
    erro: Optional[str] = None
    texto: Optional[str] = None
    dados: Any = None
    acerto: Optional[bool] = None
    json_valido: Optional[bool] = None
    custo_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    latencia_ms: int = 0


@dataclass
class ResultadoModelo:
    apelido: str
    rotulo: str
    itens: list = field(default_factory=list)

    @property
    def considerados(self) -> list:
        return [i for i in self.itens if not i.pulado]

    @property
    def total(self) -> int:
        return len(self.considerados)

    @property
    def pulados(self) -> int:
        return sum(1 for i in self.itens if i.pulado)

    @property
    def falhas(self) -> int:
        return sum(1 for i in self.considerados if not i.ok)

    @property
    def acerto_pct(self) -> Optional[float]:
        avaliaveis = [i for i in self.considerados if i.acerto is not None]
        if not avaliaveis:
            return None
        return sum(1 for i in avaliaveis if i.acerto) / len(avaliaveis) * 100

    @property
    def json_valido_pct(self) -> Optional[float]:
        aplicaveis = [i for i in self.considerados if i.json_valido is not None]
        if not aplicaveis:
            return None
        return sum(1 for i in aplicaveis if i.json_valido) / len(aplicaveis) * 100

    @property
    def custo_medio(self) -> Optional[float]:
        ok_itens = [i for i in self.considerados if i.ok]
        if not ok_itens:
            return None
        return statistics.mean(i.custo_usd for i in ok_itens)

    @property
    def tokens_medio(self) -> Optional[float]:
        ok_itens = [i for i in self.considerados if i.ok]
        if not ok_itens:
            return None
        return statistics.mean(i.tokens_in + i.tokens_out for i in ok_itens)

    @property
    def latencia_media_ms(self) -> Optional[float]:
        ok_itens = [i for i in self.considerados if i.ok]
        if not ok_itens:
            return None
        return statistics.mean(i.latencia_ms for i in ok_itens)


def executar_funcao(funcao: str, especificacao: Especificacao, fixtures: list[dict], *,
                    dry_run: bool, duble_por_provedor: dict, rng: random.Random):
    candidatos = candidatos_efetivos(especificacao)
    resultados = {apelido: ResultadoModelo(apelido, MODELOS[apelido]["rotulo"])
                  for apelido in candidatos}
    itens_cego = []

    for indice, fixture in enumerate(fixtures):
        fixture_id = fixture.get("id") or f"{funcao}_{indice}"
        respostas_cego: dict[str, ItemResultado] = {}

        for apelido in candidatos:
            entrada_modelo = MODELOS[apelido]
            try:
                montado = especificacao.montar(fixture["entrada"], entrada_modelo["provedor"])
            except NaoSuportado as exc:
                resultados[apelido].itens.append(ItemResultado(
                    fixture_id=fixture_id, apelido=apelido, ok=False, pulado=True, motivo_pulado=str(exc)))
                continue

            if dry_run:
                texto_base, dados_base = especificacao.fabricar(fixture)
                sim = (fixture.get("simulacao_dry_run") or {}).get(apelido)
                texto_sim, dados_sim, api_falhou, mult_custo, latencia_extra = aplicar_simulacao(
                    texto_base, dados_base, sim)
                fila = duble_por_provedor[entrada_modelo["provedor"]]
                if api_falhou:
                    fila.enfileirar(Resposta(ok=False, provedor=entrada_modelo["provedor"],
                        modelo=entrada_modelo["modelo"], esforco=entrada_modelo["esforco"],
                        erro="simulado: falha da API"))
                else:
                    preco_in, preco_out = PRECOS_SIMULADOS.get(entrada_modelo["modelo"], (0.0, 0.0))
                    tokens_in = max(len(json.dumps(montado["mensagens"], ensure_ascii=False)) // 4, 10)
                    tokens_out = max(len(texto_sim or "") // 4, 5)
                    custo = round((tokens_in * preco_in + tokens_out * preco_out) / 1_000_000 * mult_custo, 6)
                    fila.enfileirar(Resposta(
                        ok=True, texto=texto_sim, dados=None, provedor=entrada_modelo["provedor"],
                        modelo=entrada_modelo["modelo"], esforco=entrada_modelo["esforco"],
                        tokens_in=tokens_in, tokens_out=tokens_out, custo_usd=custo,
                        latencia_ms=300 + latencia_extra))

            resp, erro = _chamar_com_override(
                funcao, entrada_modelo, sistema=montado["sistema"], contexto_fixo=montado["contexto_fixo"],
                mensagens=montado["mensagens"], schema=montado["schema"],
                max_tokens_saida=montado["max_tokens_saida"])

            sucesso_api = resp is not None and resp.ok
            if sucesso_api:
                dados_avaliados, json_valido = avaliar_json(resp, montado["schema"])
                acerto = especificacao.avaliar(dados_avaliados, resp.texto, fixture.get("esperado"))
            else:
                dados_avaliados, json_valido, acerto = None, None, None

            item = ItemResultado(
                fixture_id=fixture_id, apelido=apelido, ok=sucesso_api,
                erro=(erro if not sucesso_api else None),
                texto=(resp.texto if resp else None), dados=dados_avaliados, acerto=acerto,
                json_valido=json_valido, custo_usd=(resp.custo_usd if resp else 0.0),
                tokens_in=(resp.tokens_in if resp else 0), tokens_out=(resp.tokens_out if resp else 0),
                latencia_ms=(resp.latencia_ms if resp else 0))
            resultados[apelido].itens.append(item)
            if especificacao.grupo == "cego":
                respostas_cego[apelido] = item

        if especificacao.grupo == "cego" and len(respostas_cego) == len(candidatos):
            ordem = list(candidatos)
            rng.shuffle(ordem)
            itens_cego.append({"fixture_id": fixture_id, "entrada": fixture["entrada"],
                               "ordem": ordem, "respostas": respostas_cego})

    return resultados, itens_cego


# ---------------------------------------------------------------------------
# Adapters do nucleo (real ou dublê) - preparados/limpos em volta de `executar`
# ---------------------------------------------------------------------------

class _ContextoAdapters:
    """Registra os adapters em ia.core pro tempo de uma execucao (mesmo
    mecanismo de tests/test_ia_core.py: core.registrar_adapter tem
    prioridade sobre a descoberta por modulo, e limpar_cache() garante que
    nao sobra adapter/cache de uma chamada anterior neste processo)."""

    def __init__(self, dry_run: bool):
        self.dry_run = dry_run
        self.duble_por_provedor: dict[str, AdapterDubleAB] = {}

    def __enter__(self) -> dict:
        global _DRY_RUN_ATIVO
        _DRY_RUN_ATIVO = self.dry_run
        core.limpar_cache()
        if self.dry_run:
            for provedor in ("anthropic", "openai", "gemini"):
                duble = AdapterDubleAB()
                self.duble_por_provedor[provedor] = duble
                core.registrar_adapter(provedor, (lambda d=duble: d))
        elif _gemini_disponivel():
            core.registrar_adapter("gemini", AdapterGeminiRest)
        return self.duble_por_provedor

    def __exit__(self, *exc) -> None:
        global _DRY_RUN_ATIVO
        _DRY_RUN_ATIVO = False
        for provedor in ("anthropic", "openai", "gemini"):
            core.registrar_adapter(provedor, None)
        core.limpar_cache()


# ---------------------------------------------------------------------------
# Recomendacao (so pros grupos "simples"/"visao" - "cego" e decisao do Alex)
# ---------------------------------------------------------------------------

@dataclass
class Recomendacao:
    funcao: str
    baseline: str
    candidato: str
    recomendar: Optional[bool]
    motivos: list = field(default_factory=list)


def avaliar_recomendacao(funcao: str, resultados: dict, baseline_apelido: str,
                          candidato_apelido: str) -> Recomendacao:
    baseline = resultados[baseline_apelido]
    candidato = resultados[candidato_apelido]
    motivos = []

    if baseline.acerto_pct is None or candidato.acerto_pct is None:
        acerto_ok = None
        motivos.append("acerto nao medido (fixtures desta funcao sem campo \"esperado\") - "
                       "recomendacao parcial, baseada so em JSON valido/custo")
    else:
        acerto_ok = candidato.acerto_pct >= baseline.acerto_pct
        motivos.append(f"acerto: {candidato.rotulo} {candidato.acerto_pct:.0f}% vs "
                       f"{baseline.rotulo} {baseline.acerto_pct:.0f}% "
                       f"({'igual ou melhor' if acerto_ok else 'pior que a linha de base'})")

    if candidato.json_valido_pct is None:
        json_ok = None
    else:
        json_ok = candidato.json_valido_pct > 98.0
        motivos.append(f"JSON válido: {candidato.rotulo} {candidato.json_valido_pct:.1f}% "
                       f"({'acima de 98%' if json_ok else 'abaixo de 98% - nao bate o criterio'})")

    if baseline.custo_medio is None or candidato.custo_medio is None:
        custo_ok = None
    else:
        custo_ok = candidato.custo_medio < baseline.custo_medio
        motivos.append(f"custo médio: {candidato.rotulo} US$ {candidato.custo_medio:.6f} vs "
                       f"{baseline.rotulo} US$ {baseline.custo_medio:.6f} "
                       f"({'menor, ok' if custo_ok else 'nao ficou menor que a linha de base'})")

    criterios = [c for c in (acerto_ok, json_ok, custo_ok) if c is not None]
    recomendar = bool(criterios) and all(criterios)
    return Recomendacao(funcao, baseline_apelido, candidato_apelido, recomendar, motivos)


# ---------------------------------------------------------------------------
# Execucao de ponta a ponta
# ---------------------------------------------------------------------------

def executar(*, dry_run: bool, fixtures_reais_dir: Optional[Path], funcoes_filtro: Optional[list],
            fixtures_sinteticas_dir: Path = DIR_FIXTURES_SINTETICAS, seed: int = 42) -> dict:
    rng = random.Random(seed)
    nomes = [f for f in FUNCOES if funcoes_filtro is None or f in funcoes_filtro]
    resultado_geral: dict[str, dict] = {}
    with _ContextoAdapters(dry_run) as duble_por_provedor:
        for funcao in nomes:
            especificacao = FUNCOES[funcao]
            fixtures = carregar_fixtures(funcao, fixtures_reais_dir, fixtures_sinteticas_dir)
            resultados, itens_cego = executar_funcao(
                funcao, especificacao, fixtures, dry_run=dry_run,
                duble_por_provedor=duble_por_provedor, rng=rng)
            recomendacoes = []
            if especificacao.grupo != "cego":
                candidatos = candidatos_efetivos(especificacao)
                baseline = candidatos[0]
                for candidato_apelido in candidatos[1:]:
                    recomendacoes.append(avaliar_recomendacao(funcao, resultados, baseline, candidato_apelido))
            resultado_geral[funcao] = {
                "especificacao": especificacao, "resultados": resultados, "itens_cego": itens_cego,
                "recomendacoes": recomendacoes, "total_fixtures": len(fixtures),
            }
    return resultado_geral


# ---------------------------------------------------------------------------
# Relatorio (HTML + gabarito separado dos itens as cegas)
# ---------------------------------------------------------------------------

def _fmt_pct(v: Optional[float]) -> str:
    return "n/d" if v is None else f"{v:.0f}%"


def _fmt_pct1(v: Optional[float]) -> str:
    return "n/d" if v is None else f"{v:.1f}%"


def _fmt_usd(v: Optional[float]) -> str:
    return "n/d" if v is None else f"US$ {v:.6f}"


def _fmt_ms(v: Optional[float]) -> str:
    return "n/d" if v is None else f"{v:.0f} ms"


def _tabela_metricas(especificacao: Especificacao, resultados: dict) -> str:
    linhas = []
    apelidos = list(resultados)  # ja na ordem efetiva (ver candidatos_efetivos)
    for apelido in apelidos:
        r = resultados[apelido]
        marcador = " (linha de base)" if apelido == apelidos[0] else ""
        linhas.append(
            f"<tr><td>{html.escape(r.rotulo)}{html.escape(marcador)}</td>"
            f"<td>{r.total}</td><td>{r.falhas}</td><td>{r.pulados}</td>"
            f"<td>{_fmt_pct(r.acerto_pct)}</td><td>{_fmt_pct1(r.json_valido_pct)}</td>"
            f"<td>{_fmt_usd(r.custo_medio)}</td><td>{_fmt_ms(r.latencia_media_ms)}</td></tr>")
    return (
        "<table class='metricas'><thead><tr><th>Modelo</th><th>Fixtures</th><th>Falhas</th>"
        "<th>Pulados</th><th>Acerto</th><th>JSON válido</th><th>Custo médio</th>"
        "<th>Latência média</th></tr></thead><tbody>" + "".join(linhas) + "</tbody></table>")


def _bloco_recomendacoes(recomendacoes: list) -> str:
    partes = []
    for rec in recomendacoes:
        rotulo_cand = MODELOS[rec.candidato]["rotulo"]
        rotulo_base = MODELOS[rec.baseline]["rotulo"]
        veredito = ("RECOMENDADO virar padrão" if rec.recomendar
                    else "NÃO recomendado (ainda) virar padrão")
        classe = "recomendado" if rec.recomendar else "nao-recomendado"
        itens = "".join(f"<li>{html.escape(m)}</li>" for m in rec.motivos)
        partes.append(
            f"<div class='recomendacao {classe}'><strong>{html.escape(rotulo_cand)} "
            f"vs {html.escape(rotulo_base)}:</strong> {veredito}<ul>{itens}</ul></div>")
    return "".join(partes)


def _bloco_cego(funcao: str, itens_cego: list) -> tuple[str, list]:
    """Devolve (html_da_secao, entradas_do_gabarito) - o gabarito (qual lado
    A/B era qual apelido) NUNCA entra no HTML, so no arquivo separado."""
    blocos = []
    gabarito = []
    for item in itens_cego:
        apelido_a, apelido_b = item["ordem"]
        resp_a = item["respostas"][apelido_a]
        resp_b = item["respostas"][apelido_b]
        entrada_fmt = html.escape(json.dumps(item["entrada"], ensure_ascii=False, indent=None))
        texto_a = html.escape(resp_a.texto or f"(sem resposta - {resp_a.erro or 'falha'})")
        texto_b = html.escape(resp_b.texto or f"(sem resposta - {resp_b.erro or 'falha'})")
        blocos.append(
            f"<div class='item-cego'><p class='entrada'><em>Entrada:</em> {entrada_fmt}</p>"
            f"<div class='lado'><h4>Resposta A</h4><pre>{texto_a}</pre></div>"
            f"<div class='lado'><h4>Resposta B</h4><pre>{texto_b}</pre></div></div>")
        gabarito.append({"fixture_id": item["fixture_id"], "A": apelido_a, "B": apelido_b})
    titulo = f"<p>{len(itens_cego)} item(ns) às cegas - escolha pelo TOM, sem saber qual é qual " \
             f"(o gabarito está em arquivo separado).</p>"
    return titulo + "".join(blocos), gabarito


CSS_RELATORIO = """
body { font-family: -apple-system, system-ui, sans-serif; max-width: 900px; margin: 2rem auto;
       padding: 0 1rem; color: #1a1a1a; line-height: 1.5; }
h1 { font-size: 1.5rem; } h2 { margin-top: 2.5rem; border-bottom: 2px solid #ddd; padding-bottom: .3rem; }
table.metricas { border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: .9rem; }
table.metricas th, table.metricas td { border: 1px solid #ccc; padding: .4rem .6rem; text-align: left; }
table.metricas th { background: #f4f4f4; }
.recomendacao { border-left: 4px solid #999; padding: .5rem 1rem; margin: .5rem 0; background: #fafafa; }
.recomendacao.recomendado { border-color: #2a7d2a; background: #eef8ee; }
.recomendacao.nao-recomendado { border-color: #b33; background: #fdecec; }
.item-cego { border: 1px solid #ddd; border-radius: 6px; padding: .8rem 1rem; margin: 1rem 0; }
.item-cego .entrada { color: #555; font-size: .85rem; }
.lado { margin-top: .5rem; } .lado h4 { margin: 0 0 .2rem; font-size: .85rem; color: #666; }
.lado pre { white-space: pre-wrap; background: #f7f7f7; padding: .5rem; border-radius: 4px; margin: 0; }
.aviso { background: #fff8e1; border: 1px solid #e0c34a; padding: .6rem 1rem; border-radius: 6px; }
"""


def gerar_html(resultado_geral: dict, *, dry_run: bool, gerado_em: str) -> tuple[str, dict]:
    secoes = []
    gabarito_geral: dict[str, list] = {}
    for funcao, dados in resultado_geral.items():
        especificacao: Especificacao = dados["especificacao"]
        secoes.append(f"<h2>{html.escape(funcao)} <small>({especificacao.grupo}, "
                      f"{dados['total_fixtures']} fixture(s))</small></h2>")
        if especificacao.grupo == "cego":
            html_cego, gabarito = _bloco_cego(funcao, dados["itens_cego"])
            secoes.append(html_cego)
            secoes.append("<p><em>Métricas agregadas (custo/latência/JSON válido, identificadas "
                          "por modelo - só o TEXTO acima ficou às cegas):</em></p>")
            secoes.append(_tabela_metricas(especificacao, dados["resultados"]))
            if gabarito:
                gabarito_geral[funcao] = gabarito
        else:
            secoes.append(_tabela_metricas(especificacao, dados["resultados"]))
            secoes.append(_bloco_recomendacoes(dados["recomendacoes"]))

    modo = "SIMULAÇÃO (--dry-run, dublês - nenhuma chamada real)" if dry_run else "EXECUÇÃO REAL"
    corpo = (
        f"<h1>Teste A/B de IA — Faixa A11</h1>"
        f"<p class='aviso'>Modo: <strong>{html.escape(modo)}</strong> · gerado em {html.escape(gerado_em)}"
        f"<br>Critério de recomendação: acerto igual ou melhor, JSON válido &gt; 98%, custo menor "
        f"que a linha de base. Chat/decisão/mensagem difícil: decisão sempre do Alex, pelo tom.</p>"
        + "".join(secoes)
    )
    pagina = (
        "<!DOCTYPE html><html lang='pt-BR'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>Teste A/B de IA</title><style>{CSS_RELATORIO}</style></head><body>{corpo}</body></html>"
    )
    return pagina, gabarito_geral


def escrever_relatorio(resultado_geral: dict, saida_dir: Path, *, dry_run: bool) -> tuple[Path, Path]:
    from datetime import datetime
    saida_dir.mkdir(parents=True, exist_ok=True)
    gerado_em = datetime.now().strftime("%Y-%m-%d %H:%M")
    pagina, gabarito = gerar_html(resultado_geral, dry_run=dry_run, gerado_em=gerado_em)
    caminho_html = saida_dir / "relatorio_ab.html"
    caminho_gabarito = saida_dir / "relatorio_ab.gabarito.json"
    caminho_html.write_text(pagina, encoding="utf-8")
    caminho_gabarito.write_text(
        json.dumps({"aviso": "NAO abrir antes de escolher pelo tom no relatorio_ab.html - "
                             "isso revela qual resposta era de qual modelo.",
                   "gabarito": gabarito}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    return caminho_html, caminho_gabarito


def imprimir_resumo(resultado_geral: dict) -> None:
    for funcao, dados in resultado_geral.items():
        especificacao: Especificacao = dados["especificacao"]
        print(f"\n== {funcao} ({especificacao.grupo}) — {dados['total_fixtures']} fixture(s) ==")
        for apelido in dados["resultados"]:
            r = dados["resultados"][apelido]
            print(f"  {r.rotulo}: acerto={_fmt_pct(r.acerto_pct)} json_valido={_fmt_pct1(r.json_valido_pct)} "
                  f"custo_medio={_fmt_usd(r.custo_medio)} latencia_media={_fmt_ms(r.latencia_media_ms)} "
                  f"falhas={r.falhas}/{r.total} pulados={r.pulados}")
        for rec in dados["recomendacoes"]:
            veredito = "RECOMENDADO" if rec.recomendar else "nao recomendado"
            print(f"  -> {MODELOS[rec.candidato]['rotulo']} vs {MODELOS[rec.baseline]['rotulo']}: {veredito}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Teste A/B de IA por funcao (Fase 7, faixa A11) - compara modelo atual x "
                    "candidato por funcao do painel.")
    parser.add_argument("--dry-run", action="store_true",
                       help="usa dubles (nenhuma chamada real, nenhuma credencial necessaria) - "
                            "o que os testes automatizados usam")
    parser.add_argument("--fixtures-reais", default="fixtures_reais",
                       help="pasta com exemplos reais do Alex (gitignored; padrao: fixtures_reais/)")
    parser.add_argument("--funcoes", default=None,
                       help="lista separada por virgula pra rodar so algumas funcoes (padrao: todas)")
    parser.add_argument("--saida", default=None,
                       help="pasta de saida do relatorio (padrao: <fixtures-reais>/relatorios_ab)")
    parser.add_argument("--seed", type=int, default=42,
                       help="semente do embaralhamento as cegas (reprodutibilidade)")
    args = parser.parse_args(argv)

    if not args.dry_run and not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
        print("Aviso: nem ANTHROPIC_API_KEY nem OPENAI_API_KEY estao definidas - todas as chamadas "
              "reais vao falhar. Use --dry-run pra testar sem chaves.", file=sys.stderr)

    fixtures_reais_dir = Path(args.fixtures_reais).resolve()
    saida_dir = Path(args.saida).resolve() if args.saida else (fixtures_reais_dir / "relatorios_ab")
    funcoes_filtro = [f.strip() for f in args.funcoes.split(",")] if args.funcoes else None
    if funcoes_filtro:
        desconhecidas = [f for f in funcoes_filtro if f not in FUNCOES]
        if desconhecidas:
            print(f"Funcao(oes) desconhecida(s): {', '.join(desconhecidas)}. "
                  f"Disponiveis: {', '.join(FUNCOES)}", file=sys.stderr)
            return 2

    resultado_geral = executar(dry_run=args.dry_run, fixtures_reais_dir=fixtures_reais_dir,
                               funcoes_filtro=funcoes_filtro, seed=args.seed)
    caminho_html, caminho_gabarito = escrever_relatorio(resultado_geral, saida_dir, dry_run=args.dry_run)
    imprimir_resumo(resultado_geral)
    print(f"\nRelatório: {caminho_html}\nGabarito (não abrir antes de julgar pelo tom): {caminho_gabarito}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
