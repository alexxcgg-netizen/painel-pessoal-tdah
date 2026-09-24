# Aprendizados - faixa A5 (historico do chat)

- `migracoes/` e `changelog.d/` ainda nao existem em `fase7/integracao`
  (a infra da Etapa 0 que aplica migracao sozinha ainda nao chegou). Criei
  os dois diretorios so com os arquivos desta faixa dentro (o `.sql` e o
  `.md` pedidos no prompt), sem inventar um runner. Nos testes, o SQL da
  migracao e lido do arquivo e aplicado direto com `conn.executescript` num
  banco `:memory:` - nao depende de `db.py` nem do runner.

- `ia.core.chamar_ia` ja aceita `contexto_fixo` e `mensagens` desde a faixa
  A1 (ver `ia/core.py`/`ia/contrato.py`) - o mecanismo de cache de prompt
  (bloco de sistema com `cache_control`) e implementado no adapter
  (`ia/adapters/anthropic.py`, faixa A2), nao aqui. `ia/historico.py` so
  precisa devolver o mesmo texto em `contexto_fixo` entre chamadas
  seguidas pra esse cache valer a pena rio abaixo.

- `mensagens` no contrato e uma lista Anthropic-shaped:
  `{"role": "user"|"assistant", "content": "..."}` (confirmado lendo
  `ia/adapters/anthropic.py`, que repassa a lista direto pra
  `client.messages.create(messages=...)`, e `claude_client.py` legado, que
  usa o mesmo formato). Isso bate com `papel` em `chat_mensagens`
  (`CHECK (papel IN ('user','assistant'))`) - nao precisou de traducao.

- Cuidado ao cortar o trecho "sempre na integra": se o corte cai numa
  mensagem `assistant`, a lista de mensagens comeca com `assistant`, o que
  a API da Anthropic rejeita (tem que comecar com `user`). Resolvido
  andando o corte pra tras ate cair num `user` (`_cortar_para_verbatim`) -
  por isso o numero de mensagens verbatim pode passar um pouco de 12 em vez
  de ficar cravado nisso.

- `criado_em` em `chat_mensagens` e UTC (`datetime('now')` do SQLite, ver
  comentario de `db.py:_criado_local`), mas isso NAO importa pra decisao de
  "o dia mudou" aqui: uso o relogio injetavel (`agora`) tanto pra gravar
  `dia` na reconstrucao quanto pra comparar na proxima chamada - os dois
  lados vem da mesma fonte, entao o fuso do SQLite nunca entra na conta.

- Reconstrucao com falha da IA (`ok=False` ou texto vazio) NAO avanca
  `ultimo_mensagem_id` nem `dia` - assim a proxima chamada tenta nos mesmos
  dados (o historico so cresce ate uma reconstrucao dar certo). Virada de
  dia sem nada alem do trecho verbatim (ou seja, nada pra dobrar) tambem
  nao chama IA - so atualiza o marcador `dia`, senao ficaria tentando
  reconstruir (e falhando/gastando) toda chamada do dia.
