# Provedores de IA (Fase 7 - hibrido Anthropic + OpenAI)

Este documento registra o que cada faixa confirmou de verdade lendo a documentacao/codigo
do SDK instalado, com data, versus o que ficou como TODO por falta de confirmacao -
regra explicita do briefing da Fase 7 pra nunca assumir parametro de API sem checar.

## OpenAI (faixa A3, `ia/adapters/openai.py`)

Confirmado em **2026-09-24**, lendo o codigo do pacote `openai` versao **3.19.2**
instalado no `.venv` deste worktree (`.venv/lib/python3.11/site-packages/openai/`) -
nao inventado, nao vindo de memoria de treinamento (que nao cobre um SDK lancado depois
do cutoff):

- **Metodo da chamada**: `client.chat.completions.create(...)` (Chat Completions API).
  O SDK recomenda a `Responses API` pra projetos novos (aviso no docstring de `create`),
  mas o briefing da faixa pedia Chat Completions OU Responses e o formato de
  `mensagens`/`sistema` do contrato (`ia/contrato.py`) mapeia mais direto pra
  Chat Completions (lista de mensagens com role), entao foi essa a escolhida.
- **Role do "sistema"**: usamos `"developer"`, nao `"system"`. Confirmado no docstring
  de `openai.types.chat.chat_completion_developer_message_param.ChatCompletionDeveloperMessageParam`:
  *"With o1 models and newer, `developer` messages replace the previous `system`
  messages"*. GPT-6 Luna/Sol suportam `reasoning_effort` (ver abaixo), entao tratamos
  como modelos de raciocinio e usamos `developer`. O SDK ainda aceita `role: "system"`
  (nao foi removido), entao se isso se provar errado pra Luna/Sol especificamente e um
  ajuste de uma linha, nao estrutural.
- **Esforco de raciocinio**: parametro `reasoning_effort` existe em
  `chat.completions.create` (visto na assinatura em
  `openai/resources/chat/completions/completions.py`). Valores aceitos pelo SDK:
  `none | minimal | low | medium | high | xhigh | max` (mais granular que o briefing
  pedia). Seguimos a instrucao literal do briefing e mapeamos so pros 3 baldes
  pedidos: `baixo->low, medio->medium, alto/xhigh/max->high` (`_MAPA_ESFORCO` no
  adapter); um valor de esforco desconhecido cai em `medium` por seguranca, nunca
  quebra a chamada.
- **Modo Flex/Batch**: parametro `service_tier`, aceita o literal `"flex"` (Flex
  Processing, preco menor pra processamento nao urgente) - confirmado no `Literal[...]`
  da assinatura de `create`. Usado quando `modo == "flex"`.
- **Schema JSON (Structured Outputs)**: `response_format={"type": "json_schema",
  "json_schema": {"name": ..., "schema": ..., "strict": ...}}` - estrutura confirmada
  lendo `openai/types/shared_params/response_format_json_schema.py`
  (`ResponseFormatJSONSchema`/`JSONSchema`). Se a chamada com `response_format` falhar
  por qualquer motivo (modelo nao suporta, schema invalido pro modo `strict` etc), o
  adapter cai pro fallback: reenvia sem `response_format`, com uma instrucao de texto
  pedindo JSON puro anexada na mensagem `developer`, e faz `json.loads()` best-effort
  no texto que voltar (`dados=None` se o parse falhar - a chamada em si continua
  `ok=True`, so o campo estruturado fica vazio).
- **`max_tokens` vs `max_completion_tokens`**: usamos `max_completion_tokens`.
  `max_tokens` aparece marcado como deprecado no docstring do proprio `create`
  ("This value is now deprecated in favor of `max_completion_tokens`... not compatible
  with o-series/reasoning models").
- **Uso/tokens na resposta**: `response.usage.prompt_tokens` e
  `response.usage.completion_tokens` (confirmado em
  `openai/types/completion_usage.py`, classe `CompletionUsage`). Cache:
  `response.usage.prompt_tokens_details.cached_tokens` (tokens de entrada lidos do
  cache) e `response.usage.prompt_tokens_details.cache_write_tokens` (tokens
  escritos no cache) - os dois confirmados na classe `PromptTokensDetails` no mesmo
  arquivo. Isso foi uma surpresa boa: o briefing so citava `cached_tokens` como
  possivel; o SDK instalado tambem expoe `cache_write_tokens` de verdade, entao
  `tokens_cache_escrito` do contrato e preenchido com valor real, nao fica zerado.
- **Cache de prompt**: nao ha `cache_control` explicito por bloco (diferente da
  Anthropic). A OpenAI cacheia automaticamente PREFIXOS IDENTICOS e repetidos entre
  chamadas (documentado no proprio SDK via `prompt_cache_key`/`prompt_cache_options`
  em `create`). Na pratica isso significa: `sistema` + `contexto_fixo` precisam ficar
  exatamente iguais, byte a byte, entre chamadas seguidas da mesma funcao pra manter o
  prefixo cacheavel - nunca interpolar algo variavel (timestamp, id de sessao) dentro
  desse trecho. Ver comentario em `_montar_conteudo_sistema` no adapter.
- **Formato de imagem (visao)**: `{"type": "image_url", "image_url": {"url":
  "data:<mime>;base64,<...>"}}` - confirmado em
  `openai/types/chat/chat_completion_content_part_image_param.py`
  (`ChatCompletionContentPartImageParam`/`ImageURL`, campo `url` aceita "URL da
  imagem OU dado base64 codificado"). O formato de entrada que este adapter aceita em
  `mensagens` (`{"type": "image", "data_b64": ..., "mime": ...}`) e uma convencao
  desta faixa (A3), documentada no topo de `ia/adapters/openai.py`, ja que o contrato
  (`ia/contrato.py`) nao fixa o formato de mensagem multimodal.
- **Excecoes**: hierarquia real do SDK (`openai.__init__`, testado com
  `ClasseX.__mro__`): `APITimeoutError` e subclasse de `APIConnectionError`, que por
  sua vez e subclasse de `APIError` -> `OpenAIError` -> `Exception`. Erro de
  rede/timeout (`APIConnectionError`, que cobre `APITimeoutError`) e deixado subir
  (raise) do adapter, com `exc.retentavel = True` marcado antes - ajuste de contrato
  pedido pelo nucleo (`ia/core.py`, faixa A1) depois da implementacao inicial: sem
  isso, o nucleo nunca teria uma excecao pra re-tentar. Qualquer outro erro (auth,
  rate limit, 4xx/5xx de aplicacao, erro de parsing) continua virando
  `Resposta(ok=False, erro=str(e))`, nunca sobe cru.
- **Cliente sem credencial**: `openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY",
  ""))` NAO levanta excecao na construcao mesmo com `api_key=""` (testado direto:
  so falha se `api_key` nao for passado nem existir a env var - passar string vazia
  conta como "foi passado"). Confirmado rodando o construtor sem a env var no
  ambiente e comparando com passar `api_key=""` explicitamente.

### TODOs (nao confirmado, documentado em comentario `# TODO` no codigo)

- **Preco (`ia/precos.json`)**: a faixa A4 esta criando esse arquivo em paralelo. O
  formato usado por `_calcular_custo` em `ia/adapters/openai.py`
  (`{"openai": {"<modelo>": {"entrada": ..., "saida": ..., "cache_leitura": ...,
  "cache_escrita": ..., "limiar_tokens_in": ..., "multiplicador_entrada_acima": ...,
  "multiplicador_saida_acima": ...}}}`) e uma SUPOSICAO desta faixa, nao confirmada
  com a A4. Se o arquivo nao existir ou tiver outro formato, `custo_usd` fica `0.0`
  (nunca quebra a chamada por causa disso).
- **Preco escalonado do GPT-6 Sol acima de 272 mil tokens de entrada** (2x entrada,
  1.5x saida, conforme o briefing): implementado de forma generica (campos opcionais
  `limiar_tokens_in`/`multiplicador_entrada_acima`/`multiplicador_saida_acima` em
  `ia/precos.json`, se existirem), mas os NOMES desses campos nao foram combinados
  com a A4 - pode precisar de ajuste quando o formato real dela aparecer.
- **`reasoning_effort` em modelos que nao sejam GPT-6 Luna/Sol**: o SDK aceita o
  parametro pra "modelos de raciocinio" em geral, mas nao ha confirmacao de que TODO
  modelo aceito por este adapter vai suportar - se um modelo nao suportar,
  presumivelmente a API responde com erro 400 pra esse campo especifico (nao
  testado contra a API real, so contra o SDK/mock). Fica documentado aqui como
  comportamento nao verificado end-to-end (sem credencial real disponivel pra
  testar, conforme regra da tarefa).
