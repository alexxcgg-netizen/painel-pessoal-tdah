### Fase 7 - Faixa N2 (captura por Telegram)

- **`telegram_captura.py` (novo)**: fluxo de captura por Telegram, por
  WEBHOOK (diferente de `telegram_bot.py`, Fase 3, que é o canal de
  *conversa* por long polling e continua existindo sem mudança nenhuma -
  ver "convivência" abaixo). Texto vira tarefa/gasto/meta (mesmo
  classificador de `/api/capture`, `app._executar_captura` - fonte única,
  nunca reimplementada aqui); um link puro (só a URL, nada mais na
  mensagem) é resumido e salvo em "Salvos pra ver depois"
  (`app._salvar_link`); mensagem de voz é transcrita (Groq
  `whisper-large-v3-turbo`, US$0,04/hora - a mais barata encontrada que
  atende bem pt-BR, pesquisado 2026-09-24, comparação completa em
  `docs/telegram-captura.md`) e cai no mesmo fluxo de texto; foto de nota
  fiscal (`claude_client.extrair_nota_fiscal_foto`) vira gasto direto, com
  Desfazer (o card em si só existe no app - o Telegram não renderiza
  cards, então a resposta é um resumo curto em texto). Tudo com injeção
  de dependência (nunca importa `app.py` no topo do arquivo - evita
  import circular), 100% testável com dublês.
- **`rotas/n2_telegram.py` (novo)**, `POST /api/telegram/webhook`: valida
  o segredo do webhook (header `X-Telegram-Bot-Api-Secret-Token` contra
  `TELEGRAM_WEBHOOK_SECRET`, `hmac.compare_digest`) e uma lista de
  permissão de UM chat só (`TELEGRAM_CHAT_ID_PERMITIDO`) - qualquer outro
  chat é ignorado em silêncio (200 sem ação nenhuma, nunca revela que o
  bot existe). Idempotência por `update_id`
  (`telegram_updates_processados`,
  `migracoes/202609241310_n2_telegram.sql`) - o Telegram reenvia update
  que não recebeu 200 a tempo, e o site pode estar dormindo.
- **Bloqueio de infra evitado**: a Etapa 0 (Blueprint com carga
  automática, `rotas/_base.py`/`rotas/__init__.py`) ainda não tinha
  chegado em `fase7/integracao` quando esta faixa rodou (`STATUS.md` já
  listava N2 como dependente dela) - `rotas/n2_telegram.py` foi escrito
  seguindo o contrato exato lido direto do worktree paralelo do
  `e0-backend`, com um fallback local (`_garantir_tabela`) pra não
  depender do runner de `migracoes/*.sql` ainda ausente. Quando a Etapa 0
  mergear, basta o merge normal (nenhum arquivo colide).
- **Decisão pro integrador**: `TELEGRAM_BOT_TOKEN` é compartilhado com o
  bot antigo (`telegram_bot.py`, long polling) - a API do Telegram não
  permite webhook e `getUpdates` juntos no mesmo token (erro 409). Três
  opções documentadas em `docs/telegram-captura.md` (bot separado -
  recomendado -, migrar tudo pra webhook, ou alternar manualmente); nenhum
  arquivo compartilhado foi tocado por esta faixa pra resolver isso
  sozinha.
- `docs/telegram-captura.md` (novo): passo a passo @BotFather → chat_id →
  segredo → `setWebhook`, tabela de variáveis de ambiente novas (faltam em
  `.env.example`, fora do escopo desta faixa), comparação de preço de
  transcrição e a convivência com o bot antigo.
- `tests/test_fase7_n2_telegram_{captura,transcricao,rota}.py`: 61 testes,
  0 falhas, nenhuma chamada real ao Telegram nem a nenhum provedor de IA
  (tudo dublê/mock).
