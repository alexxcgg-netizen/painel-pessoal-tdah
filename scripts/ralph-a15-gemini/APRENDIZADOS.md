# A15: Aprendizados e Notas Técnicas

## Decisões de Design

### 1. Import Tardio vs. Top-Level
**Decisão**: Import do SDK `google-genai` dentro de `chamar()`, não no topo do módulo.

**Motivo**: Se o SDK não estiver instalado, o módulo continua carregável. A falha só ocorre quando realmente chamado. Isso permite que o adapter seja descoberto pelo `ia/core.py` sem quebrar se o SDK não existir.

**Implementação**:
```python
def chamar(self, ...):
    try:
        import google.genai as genai
    except ImportError:
        return Resposta(ok=False, erro="SDK google-genai nao instalado")
    # ... resto
```

### 2. Tratamento de Erros de Rede
**Decisão**: Erros de rede/timeout sobem como exceção; erros de API viram `Resposta(ok=False)`.

**Motivo**: `ia/core.py` (A1) decide retry/fallback. Se a exceção subir, o retry acontece. Se virar `Resposta(ok=False)`, vai direto para fallback.

**Implementação**:
```python
eh_rede = isinstance(e, (ConnectionError, TimeoutError, socket.timeout))
tipo_erro = type(e).__name__
if eh_rede or any(nome in tipo_erro for nome in [...]):
    e.retentavel = True  # Marca pra core.py saber
    raise
else:
    e.retentavel = False  # Marca como não-retentável
    return Resposta(ok=False, erro=str(e))
```

### 3. Preço Centralizado
**Decisão**: Usar `ia.precos.custo_usd()` (A4) em vez de ler JSON localmente.

**Motivo**: Fonte única de verdade. Se a A1/A4 mudar o formato, o adapter não quebra. Não duplica lógica de cálculo.

**Resultado**: Removemos 40 linhas de código de cálculo local, temos mais confiança no preço.

### 4. Schema e JSON
**Decisão**: Best-effort parsing. JSON inválido não quebra a chamada.

**Motivo**: Nem todo modelo responde JSON perfeito. Markdown (`` ```json ... ``` ``) é comum. Quando falha, retorna `dados=None` mas `ok=True` (preserva o `texto`).

## Testes

### Estratégia
15 testes, sem chamadas reais de API:
- Mock do SDK via `sys.modules["google.genai"] = MagicMock()` no início do arquivo
- Client fake injetado no adapter
- Resposta fake com mesma estrutura do SDK real

### Cobertura
- Caminho feliz (chamada básica)
- Configuração de parâmetros (máx tokens, sistema, contexto, schema)
- Todos os tipos de erro (rede, API, SDK ausente)
- JSON parsing (valido, markdown, inválido)
- Descoberta do adapter

### Aprendizados
1. Mock de `sys.modules` funciona melhor que patch de import
2. `SimpleNamespace` é perfeito pra simular objetos do SDK
3. Testes com mock injetado são muito mais rápidos e confiáveis

## Problemas Encontrados

### 1. ConnectionError não era detectado
**Problema**: String "ConnectionError" não contém "ConnectError" na busca.

**Solução**: Usar `isinstance()` junto com busca por nome.

```python
eh_rede = isinstance(e, (ConnectionError, TimeoutError, socket.timeout))
```

### 2. Google.genai não estava instalado
**Problema**: Testes falhavam com import error.

**Solução**: Mock no `sys.modules` antes de importar o adapter.

## TODO/Confirmar

Deixei varios `# TODO:` no código:

1. **Confirmar nomes de parâmetro**: `generate_content`, `max_output_tokens`, `system_instruction` etc. precisam ser confirmados contra documentação/SDK real.
2. **Estrutura de resposta**: `.text`, `.usage_metadata.prompt_token_count` etc. precisam ser confirmados.
3. **Nomes de atributos de cache**: `cached_content_input_token_count`, `cache_creation_input_token_count`.
4. **Controle de esforço**: Se Gemini suporta reasoning/thinking e como configura.

Esses TODOs devem ser resolvidos quando o SDK estiver instalado de verdade e pudermos testar contra a API.

## Core.py: Blocker Necessário

O arquivo `ia/core.py` (A1) precisa adicionar:

```python
MODULOS_ADAPTER = {
    ...
    "gemini": "ia.adapters.gemini",  # <-- adicionar aqui
}

_NOMES_CLASSE_ADAPTER = {
    ...
    "gemini": ("AdapterGemini", "GeminiAdapter"),  # <-- adicionar aqui
}
```

Sem isso, configurações não funcionam.

## Integração Esperada

1. A1 (core.py) registra o provedor
2. A4 (precos.py) preenche preços de Gemini em `ia/precos.json`
3. Usuário testa com `ia/config.d/<funcao>.json` apontando `"provedor": "gemini"`
4. Após comparar qualidade/custo, ativa com `"ativo": true`

## Referências

- Adaptei padrão de `ia/adapters/anthropic.py` (existe na integração)
- Usamos a mesma interface `ia.contrato.Adapter`
- Centralizamos custo via `ia.precos.custo_usd()` (novo em fase7)
- Mocks de teste seguem padrão de `tests/test_ia_adapter_anthropic.py`

## Pontos Fortes

1. **Testado**: 15 testes, todos passando
2. **Robusto**: Import tardio, tratamento de erro completo
3. **Compatível**: Segue padrão do Anthropic adapter
4. **Documentado**: README com instruções, TODOs claros
5. **Desacoplado**: Preço centralizado, não reimplementa lógica

## Pontos Fracos

1. **TODOs pendentes**: Nomes de parâmetro/resposta precisam confirmação contra SDK real
2. **SDK não instalado**: Testes passam com mock, mas comportamento real não testado
3. **Cache não suportado**: Gemini pode ter cache mas não exploramos; parâmetros apenas ignorados
