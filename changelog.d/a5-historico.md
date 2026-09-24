### Fase 7 - faixa A5 (historico do chat, resumo fixo + reconstrucao)

- Novo `ia/historico.py`: mecanismo de "resumo fixo + reconstrucao" pra
  cortar o custo do chat (85-95% do custo de IA hoje vem de reenviar o
  historico inteiro a cada mensagem). `montar_contexto(conn, agora=None)`
  devolve `{"contexto_fixo": str, "mensagens": list}` prontos pra
  `ia.core.chamar_ia("chat", ..., contexto_fixo=..., mensagens=...)`: o
  `contexto_fixo` (resumo) fica identico entre chamadas seguidas ate a
  proxima reconstrucao (cache de prompt do provedor), so as ultimas
  interacoes vao na integra e mudam a cada turno.
- Reconstrucao do resumo (`ia.core.chamar_ia("resumo_historico", ...)`,
  config em `ia/config.d/resumo_historico.json` - alvo openai gpt-6-luna
  esforco medio, fallback Haiku 4.5, saida max 400 tokens) dispara quando o
  historico alem do resumo passa de ~6.000 tokens (estimativa `len//4`) OU
  o dia muda. As mensagens originais nunca saem de `chat_mensagens`; o
  resumo e so uma tabela derivada (`chat_resumo_historico`, migracao
  `migracoes/202609241100_a5_historico.sql`).
- `tests/test_ia_historico.py` (24 casos, tudo com duble de IA): banco
  vazio, poucas mensagens (sem IA), corte sempre alinhado numa mensagem
  `user`, reconstrucao por tamanho e por virada de dia, `contexto_fixo`
  estavel entre chamadas sem reconstrucao, falha de IA sem derrubar o
  chat, config valida via `ia.core.carregar_todas_configs()`.
- Ainda nao mexe no chat em si (`ia/funcoes/chat.py`/`claude_client.py` -
  a faixa A6 e quem vai consumir `ia.historico.montar_contexto`).
