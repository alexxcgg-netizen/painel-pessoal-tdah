# A15: Adapter Gemini para Google Generative AI

**Faixa**: A15 (Adapter Gemini)  
**Status**: Implementado e testado  
**Branch**: `fase7/a15-gemini`

## O que mudou

### Novo: `ia/adapters/gemini.py`

Implementa a interface `ia.contrato.Adapter` para o provedor Gemini da Google, permitindo usar modelos como `gemini-3.5-flash-lite` no assistente.

**Características**:
- SDK `google-genai` com import tardio (não quebra se não instalado)
- Erro de rede/timeout sobe como exceção (retry automático em `ia/core.py`)
- Erro de API vira `Resposta(ok=False, erro=...)` (fallback em `ia/core.py`)
- Extração de JSON com suporte a markdown (`` ```json ... ``` ``)
- Preço via centralizado `ia.precos.custo_usd()` (faixa A4)
- Sem cache de prompt nativo (parâmetros aceitos por compatibilidade)

### Novo: `tests/test_ia_adapter_gemini.py`

15 testes cobrindo:
- Chamada básica com retorno correto
- Máximo de tokens de saída
- Sistema + contexto fixo montando instrução
- Resposta sem texto (vazia)
- Erro de conexão levantando exceção
- Timeout levantando exceção
- Erro de API retornando `Resposta(ok=False)`
- SDK não instalado retornando erro claro
- Schema com JSON válido extraindo dados
- JSON envolto em markdown parseando corretamente
- JSON inválido não quebrando a chamada
- Sem schema não parseando JSON mesmo que presente
- Custo em USD ficando 0.0 se arquivo/modelo ausente
- Adapter construindo sem env var `GEMINI_API_KEY`
- Descoberta via `criar_adapter()`

**Status**: 15/15 testes passando ✓

### Novo: `docs/ia-provedores-gemini.md`

Documentação completa do adapter:
- Instalação (SDK `google-genai`)
- Configuração (env var, `ia/config.d/*.json`)
- Modelos suportados (recomendado: `gemini-3.5-flash-lite`)
- Tratamento de erros
- Schema e JSON parsing
- Preços e cache
- Registro em `ia/core.py` (blocker: A1 precisa atualizar)
- Próximos passos

### Novo: `scripts/ralph-a15-gemini/progress.txt`

Rastreamento de progresso da faixa.

## Blocker: Registro em ia/core.py

O arquivo `ia/core.py` (A1) precisa registrar o provedor:

```python
# Em MODULOS_ADAPTER:
"gemini": "ia.adapters.gemini",

# Em _NOMES_CLASSE_ADAPTER:
"gemini": ("AdapterGemini", "GeminiAdapter"),
```

Sem isso, configurações com `"provedor": "gemini"` falham com erro.

## Como usar

1. Instalar SDK: `pip install google-genai`
2. Configurar chave: `export GEMINI_API_KEY="sua-chave"`
3. Atualizar `ia/core.py` (A1)
4. Preencher preços em `ia/precos.json` (A4)
5. Criar config em `ia/config.d/<funcao>.json` com `"provedor": "gemini"`
6. Ativar com `"ativo": true` após testar qualidade/custo

## Arquivo.py descrito

## Files Changed

- ✨ `ia/adapters/gemini.py` (244 linhas)
- ✨ `tests/test_ia_adapter_gemini.py` (320 linhas)
- ✨ `docs/ia-provedores-gemini.md` (210 linhas)
- ✨ `scripts/ralph-a15-gemini/progress.txt`
- ✨ `changelog.d/a15-gemini.md` (este arquivo)

## Notas Técnicas

- **Late import**: O SDK só é importado dentro de `chamar()`, nunca no módulo top-level
- **Error handling**: Distingue rede (sobe) de API (retorna ok=False)
- **Preço centralizado**: Usa `ia.precos.custo_usd()` em vez de ler JSON localmente
- **Mock-friendly**: Testes injetam client fake, não precisam do SDK real

## Próximo

- A1 atualiza `ia/core.py` para registrar provedor
- A4 preenche preços de Gemini em `ia/precos.json`
- Usuário testa e compara qualidade/custo vs. Anthropic/OpenAI
