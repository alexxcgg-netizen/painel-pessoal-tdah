# A6 (chat) - aprendizados e decisoes

## Layout de cache do chat
- Ordem do provedor: tools -> system -> messages. Maximo 4 `cache_control` por request, lookback
  de 20 posicoes, Sonnet 5 so cacheia prefixo >= 1024 tokens (guia de prompt caching da
  Anthropic; `cache_control` aceito em tool, text e tool_result - conferido nos tipos do SDK
  anthropic 1.7.0: `tool_param.py`, `text_block_param.py`, `tool_result_block_param.py`).
- Breakpoints: ultimo tool; 1o bloco das mensagens (resumo A5 ou texto fixo); ultimo bloco do
  historico estavel; ultimo bloco da mensagem nova (rolante: vai pro ultimo tool_result a cada
  rodada do loop). O bloco "Contexto de agora" (muda a cada chamada) fica na mensagem nova,
  nunca antes de um breakpoint estavel.
- O system continua string com data e memorias: mudam no maximo 1x/dia (ou quando nasce
  memoria) e os testes antigos fazem `assertIn(trecho, kwargs["system"])`. O breakpoint logo
  depois dele (1o bloco das mensagens) cacheia tools+system do mesmo jeito.
- Mensagem `role: "system"` no meio da conversa NAO existe no Sonnet 5 (guia de caching) - por
  isso o contexto do dia vai como bloco de texto na mensagem do usuario, rotulado.
- Mensagens consecutivas do mesmo papel sao aceitas (a API junta) - docstring do SDK
  `messages.create`.

## Por que o chat com tools nao passa por chamar_ia (e o que falta)
O contrato (`ia/contrato.py`) nao tem tools. Pra levar o chat pro contrato faltaria:
1. `chamar_ia(..., tools=[...])` e `Adapter.chamar(..., tools)` (schema neutro; o adapter
   OpenAI traduz pra `functions`/`tools` do Responses/Chat).
2. `Resposta` com `stop_reason` e `chamadas_ferramenta: [{id, nome, entrada}]` e um jeito de
   mandar de volta o turno do assistente + `tool_result` em formato neutro (hoje o loop reenvia
   `response.content` do SDK Anthropic cru).
3. Cache por bloco (mais de um breakpoint) no adapter - hoje so o `contexto_fixo` tem cache.
4. Retry/fallback no meio do loop: se cair pro fallback na rodada 2, o historico de tool_use
   precisa estar no formato do outro provedor.
Enquanto isso o chat le modelo/max_tokens/cache de `ia/config.d/chat.json` e mede por
`ia.medicao`/`ia.teto` quando `medir_uso=True`. Com `ativo: true` e alvo OpenAI, o chat com
tools fica no `modelo_atual` (log de aviso).

## chamar_ia e os testes antigos
`chamar_ia` sempre consulta o teto e grava `uso_ia` em `db.DB_PATH`. Teste antigo que chama a
funcao com o cliente mockado e sem isolar o banco quebra (tabela ausente) ou, no checkout
principal, grava uso falso no banco real. Por isso `analisar_decisao`/`redigir_mensagem_dificil`
so passam pelo contrato com `ativo: true`; com `ativo: false` e o caminho de hoje (SDK direto no
`modelo_atual`), so que com o limite de saida da config. O adapter "anthropic" do nucleo passa a
usar `ia.legado.client` (se ninguem registrou outro), pra `patch.object(claude_client.client.messages,
"create")` continuar pegando tudo.

## Limite de saida do chat
500 tokens corta brain dump com 8+ tool_use (US-E6). Quando uma rodada volta com
`stop_reason == "max_tokens"`, ela e refeita 1x com 1500 (o teto antigo). Custo extra so nesse caso.

## Datas relativas
`resolver_data_relativa(texto, hoje)` e deterministico e conservador (vago -> None). Dia da
semana = proxima ocorrencia DEPOIS de hoje; "X da semana que vem" = aquele dia na semana
seguinte. `resolver_quando_data` da prioridade ao codigo e usa o `quando_data` do modelo so
como transicao.
