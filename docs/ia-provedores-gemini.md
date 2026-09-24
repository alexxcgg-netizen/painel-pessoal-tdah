# Provider Gemini (Google Generative AI)

**Faixa A15** — Adapter para o modelo Gemini da Google.

## Visão Geral

O adapter Gemini (`ia/adapters/gemini.py`) implementa a interface `ia.contrato.Adapter` e permite usar modelos Gemini (ex.: `gemini-3.5-flash-lite`) como um dos provedores de IA do assistente.

**Status**: Desligado por padrão (só ativado se configurado em `ia/config.d/*/json`).

## Instalação

O SDK oficial é `google-genai`:

```bash
pip install google-genai
```

**Importante**: O adapter usa import tardio — se o SDK não estiver instalado, o adapter retorna `Resposta(ok=False, erro="SDK google-genai nao instalado")` em vez de quebrar na inicialização.

## Configuração

### Variável de Ambiente

Define a chave API do Gemini:

```bash
export GEMINI_API_KEY="sua-chave-aqui"
```

A chave é lida no construtor `AdapterGemini()` e pode estar vazia (falha real só ocorre na chamada da API).

### Config de Função

Para usar Gemini em uma função de IA, crie um arquivo `ia/config.d/<funcao>.json`:

```json
{
  "funcao": "classify_capture",
  "ativo": false,
  "modelo_atual": {"provedor": "anthropic", "modelo": "claude-haiku-4-5-20251001"},
  "alvo": {"provedor": "gemini", "modelo": "gemini-3.5-flash-lite", "esforco": "medio"},
  "fallback": [{"provedor": "anthropic", "modelo": "claude-haiku-4-5-20251001"}],
  "max_tokens_saida": 300,
  "cache": {"ativo": false, "ttl": "5m"},
  "modo": "padrao"
}
```

- `ativo: true` ativa a migração para Gemini
- `ativo: false` mantém o modelo atual (Anthropic no exemplo)
- O fallback é tentado se o alvo falhar

## Modelos Suportados

Candidate barato (padrão recomendado):
- `gemini-3.5-flash-lite` — modelo leve, baixo custo

Outros modelos Google Gemini devem funcionar (ex.: `gemini-pro`, `gemini-2.0-flash`, etc.).

**Nota**: Confirmar nomes e disponibilidade dos modelos via [documentação oficial do Gemini](https://cloud.google.com/vertex-ai/generative-ai/docs/models/gemini).

## Tratamento de Erros

### Rede/Timeout

Se a chamada falhar por motivos de rede ou timeout, o erro **sobe como exceção** (com `exc.retentavel = True`) para que `ia/core.py` (faixa A1) faça 1 retry no mesmo modelo antes de tentar fallback.

Exemplos:
- `ConnectionError`
- `TimeoutError`
- `socket.timeout`
- Qualquer erro com "Timeout" ou "NetworkError" no nome

### API

Outros erros da API (credencial inválida, rate limit, 500 etc.) retornam `Resposta(ok=False, erro=...)` sem retry automático.

## Schema e JSON

Se a chamada incluir um `schema`, o adapter espera JSON válido na resposta e:

1. Tenta parsear como JSON puro
2. Se não conseguir, procura por bloco markdown (`` ```json ... ``` ``) e tenta de novo
3. Se ainda não conseguir, retorna `Resposta` com `dados=None` mas `ok=True` (não quebra a chamada)

## Cache de Prompt

Gemini não tem suporte nativo a cache de prompt como Anthropic. Os parâmetros `cache` em `ia/config.d/*.json` são aceitos por compatibilidade com o contrato, mas **não usados** no adapter.

## Preços

O custo em USD é calculado via `ia.precos.custo_usd()` (centralizado em `ia/precos.py`). O arquivo `ia/precos.json` deve conter:

```json
{
  "modelos": {
    "gemini-3.5-flash-lite": {
      "entrada": 0.075,
      "saida": 0.3,
      "cache_leitura": 0.01125,
      "cache_escrita_5min": 0.3
    }
  }
}
```

Unidades: USD por milhão de tokens (1M tokens).

**Valores de exemplo acima** — para valores reais, consultar a [página de preços do Gemini](https://ai.google.dev/pricing).

Se o arquivo estiver ausente ou o modelo não for encontrado, `custo_usd` fica 0.0.

## Esforço (Thinking/Reasoning)

O parâmetro `esforco` em `ia/config.d/*.json` é traduzido:

- `"baixo"` → `"low"`
- `"medio"` → `"medium"`
- `"alto"` → `"high"`

Outros valores são passados como-estão.

**Nota**: Confirmar se Gemini suporta controle de esforço/reasoning e nomes de parâmetro corretos via SDK.

## Testes

Testes em `tests/test_ia_adapter_gemini.py`:

- 15 testes cobrindo: chamada básica, máx tokens, erro de rede, erro de API, schema, custo, descoberta de adapter
- Todos os testes usam client mock (sem chamadas reais de API)
- Rodando: `python -m unittest tests.test_ia_adapter_gemini -v`

## Descoberta do Adapter

O `ia/core.py` descobre o adapter de duas formas:

1. **Função `criar_adapter()`** — chamada por `ia/core.py` se o módulo a exportar
2. **Classe `AdapterGemini`** — descoberta automática se `criar_adapter()` não existir

No caso do Gemini: `ia/adapters/gemini.py` exporta `criar_adapter()` e `AdapterGemini`.

## Registro em core.py

**Blocker**: O arquivo `ia/core.py` (A1) precisa ser atualizado para registrar o provedor:

```python
MODULOS_ADAPTER = {
    "anthropic": "ia.adapters.anthropic",
    "openai": "ia.adapters.openai",
    "gemini": "ia.adapters.gemini",  # <-- adicionar
}

_NOMES_CLASSE_ADAPTER = {
    "anthropic": ("AdapterAnthropic", "AnthropicAdapter"),
    "openai": ("AdapterOpenAI", "AdapterOpenAi", "OpenAIAdapter"),
    "gemini": ("AdapterGemini", "GeminiAdapter"),  # <-- adicionar
}
```

Sem isso, configurações que apontam `"provedor": "gemini"` em `ia/config.d/*.json` falharão com "provedor de IA desconhecido: 'gemini'".

## Próximos Passos

1. Instalar `google-genai` no ambiente
2. Atualizar `ia/core.py` para registrar o provedor (ver seção "Registro em core.py" acima)
3. Preencher `ia/precos.json` com preços reais do Gemini (se não existir)
4. Configurar chave API: `export GEMINI_API_KEY="..."`
5. Criar `ia/config.d/<funcao>.json` com `"provedor": "gemini"` e testar
6. Comparar qualidade/custo do Gemini vs. Anthropic/OpenAI
7. Quando satisfeito, virar `"ativo": true` na config

## Referências

- [SDK google-genai (PyPI)](https://pypi.org/project/google-genai/)
- [Documentação Gemini API](https://ai.google.dev/docs)
- [Modelos Gemini disponíveis](https://ai.google.dev/models)
- [Preços Gemini](https://ai.google.dev/pricing)
