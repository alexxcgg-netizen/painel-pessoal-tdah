### Fase 7 - Faixa A6 (chat: cache, limites, roteador, datas em codigo)

- **`chat()` com layout de cache estavel** (`ia/funcoes/chat.py`): o contexto do dia (tarefas,
  gastos, compromissos, saude, clima, voos) saiu do system e vai num bloco "Contexto de agora"
  junto da mensagem nova do Alex. O system so tem regras, data e memorias (estavel no dia).
  4 breakpoints de `cache_control`: ultimo tool, bloco fixo do historico (resumo da A5, kwarg
  `contexto_fixo`), fim do historico estavel e um rolante no fim da mensagem nova/ultimo
  tool_result. Prefixo identico byte a byte entre chamadas seguidas (testado).
- **Limites de saida**: chat 500 (refaz a rodada 1x com 1500 se cortar - brain dump nao perde
  tarefa), `analisar_decisao` 700, `redigir_mensagem_dificil` 500. Tudo em `ia/config.d/`.
- **Configs novas** `chat.json`, `chat_simples.json`, `analisar_decisao.json`,
  `redigir_mensagem_dificil.json`: `ativo: false`, `modelo_atual` Sonnet 5 (esforco baixo),
  alvo OpenAI `gpt-6-sol` medio (`gpt-6-luna` no chat_simples). Producao fica em Sonnet 5 ate o
  Alex aprovar o A/B.
- **Roteador A14 antes de responder**: `luna` -> resposta direta sem tools via
  `chamar_ia("chat_simples")` (se o modelo disser que precisa de ferramenta, cai pro chat
  normal); `local`/`padrao` -> chat normal. Com a flag do roteador desligada (padrao), nada muda.
- **Medicao/teto novos no chat** (`medir_uso=True`, o app liga na integracao): consulta
  `ia.teto.teto_permite("chat")` e grava cada rodada em `uso_ia` com tokens de cache.
- **Chat com tools continua no SDK Anthropic direto** (o contrato `chamar_ia` ainda nao tem
  tools - o que falta esta em `scripts/ralph-a6-chat/APRENDIZADOS.md`). Decisao e mensagem
  dificil passam por `chamar_ia` quando a config estiver `ativo: true`.
- **Datas relativas em codigo**: `resolver_data_relativa(texto, hoje)` ("amanha", "sexta que
  vem", "daqui 6 meses", "15/10", "dia 30"...) e `resolver_quando_data(entrada, hoje)` pro
  executor do `registrar_tarefa` (troca no `app.py` fica com o integrador).
- Testes: `tests/test_fase7_a6_chat.py`, `tests/test_fase7_a6_datas.py`.
