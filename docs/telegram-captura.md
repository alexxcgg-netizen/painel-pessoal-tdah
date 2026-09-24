# Captura por Telegram (N2) — guia de configuração

Fase 7, faixa N2. Fluxo **novo**, por **webhook** (`rotas/n2_telegram.py`, POST
`/api/telegram/webhook`), pra mandar texto, áudio, foto de nota fiscal ou link pro Telegram e
o painel capturar/gravar automaticamente — resumo curto de volta no próprio Telegram (que não
renderiza os cards do app).

> Isso é **diferente** do bot que já existe (`telegram_bot.py`, Fase 3): aquele é o canal de
> *conversa* (você manda mensagem, ele roda o mesmo pipeline de `/api/chat` e responde), usa
> **long polling** (`getUpdates`) e continua existindo sem mudança nenhuma. Este aqui é só pra
> **captura rápida**, usa **webhook**. Ver "Convivência com o bot antigo" no fim deste guia —
> **os dois não podem ficar ligados ao mesmo tempo pro MESMO bot/token** (limitação da própria
> API do Telegram).

## 1. Criar o bot no @BotFather (se ainda não tiver um)

Se `TELEGRAM_BOT_TOKEN` já está configurado (o bot de conversa da Fase 3 já existe), você pode
reusar o mesmo bot — mas leia "Convivência com o bot antigo" antes de decidir. Pra criar um bot
**novo** (recomendado, evita o conflito webhook×polling):

1. Abra uma conversa com [@BotFather](https://t.me/BotFather) no Telegram.
2. Mande `/newbot`, escolha um nome de exibição e um `username` terminado em `bot` (ex.:
   `AlexCapturaBot`).
3. O BotFather devolve um **token** (formato `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`) —
   isso vai em `TELEGRAM_BOT_TOKEN`.

## 2. Pegar o seu `chat_id`

1. Mande **qualquer mensagem** pro bot novo (ex.: "oi").
2. Abra no navegador (troque `<TOKEN>` pelo token do passo 1):
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Na resposta JSON, procure `"message":{"chat":{"id": ...}}` — esse número (pode ser negativo,
   em grupo) é o seu `chat_id`. Vai em `TELEGRAM_CHAT_ID_PERMITIDO`.

Esse é o **único** chat que o webhook processa — qualquer mensagem vinda de outro `chat_id` é
ignorada em silêncio (200 sem nenhuma ação, nunca revela que o bot faz algo), mesmo que o token
do bot vaze.

## 3. Gerar o segredo do webhook

Um valor aleatório, só pra este webhook (não reusa nenhum outro segredo do projeto):

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Isso vai em `TELEGRAM_WEBHOOK_SECRET`.

## 4. Variáveis de ambiente

| Variável | Obrigatória | O que é |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | sim | Token do bot (BotFather) — mesma variável usada pelo bot de conversa (Fase 3); só um bot pode estar com webhook ligado por vez, ver seção 6. |
| `TELEGRAM_CHAT_ID_PERMITIDO` | sim | O único `chat_id` que o webhook processa (passo 2). |
| `TELEGRAM_WEBHOOK_SECRET` | sim | Segredo comparado (tempo constante, `hmac.compare_digest`) contra o cabeçalho `X-Telegram-Bot-Api-Secret-Token` que o Telegram manda em toda chamada (passo 3). |
| `GROQ_API_KEY` | só se for usar áudio | Chave da Groq, usada por `telegram_captura.transcrever` pra transcrever mensagem de voz — ver seção 5. Sem ela, texto/foto/link continuam funcionando normalmente; áudio responde com um aviso pedindo pra mandar por texto. |
| `APP_URL_PUBLICA` | não | URL pública do painel (ex.: `https://painel.seu-dominio.com`) — se configurada, entra no fim de cada resumo mandado no Telegram, pra você abrir o app e ver/editar/desfazer o card de verdade. |

> Essas variáveis **não foram adicionadas a `.env.example`** por esta faixa (arquivo
> compartilhado, fora do escopo dela — ver `scripts/ralph-n2-telegram/progress.txt`). O
> integrador precisa acrescentá-las lá.

## 5. Escolha do provedor de transcrição de áudio

Pesquisado em **2026-09-24** (preço/modelo podem mudar — reconfirme antes de decidir de novo).
Comparação das opções mais citadas pra transcrição via API, com suporte a pt-BR (todas usam
variantes do Whisper ou equivalente multilíngue):

| Provedor / modelo | Preço | Observação |
|---|---|---|
| **Groq — `whisper-large-v3-turbo`** | **US$0,04/hora de áudio** (≈US$0,00067/min) | **Escolhido.** Mesmo modelo Whisper Large v3 (qualidade multilíngue, inclui pt-BR), rodando na infra da Groq — API compatível com o formato OpenAI (`/openai/v1/audio/transcriptions`), sem custo de assinatura, sem mínimo mensal. |
| OpenAI — `gpt-4o-mini-transcribe` | US$0,003/min (≈US$0,18/hora) | ~4,5× mais caro que a Groq pro mesmo caso de uso. |
| OpenAI — Whisper (`whisper-1`) | US$0,006/min (≈US$0,36/hora) | ~9× mais caro que a Groq. |
| Deepgram — Nova-2 (batch) | ≈US$0,26/hora | ~6,5× mais caro que a Groq. |

A Groq foi a **mais barata** encontrada que atende bem pt-BR (mesmo modelo Whisper Large v3,
reconhecido multilíngue) — por isso `telegram_captura.transcrever` chama
`https://api.groq.com/openai/v1/audio/transcriptions` com `model=whisper-large-v3-turbo` e
`language=pt`.

Fontes consultadas: [Groq ASR API docs](https://console.groq.com/docs/speech-to-text) (preço
oficial do modelo), comparativos de mercado de 2026 (eesel.ai, futureagi.substack.com,
tokenmix.ai) pros preços da OpenAI/Deepgram usados na tabela acima.

Cada chamada passa por `ia.teto.teto_permite("transcricao")` **antes** (bloqueia se o teto
mensal de IA já estourou 100% — mesma trava usada por captura/intent, ver `ia/teto.py`) e por
`ia.medicao.registrar_uso(...)` **depois** (grava tokens não se aplicam aqui, mas custo em USD
sim — calculado a partir da duração do áudio, que o próprio Telegram já informa em
`message.voice.duration`, sem precisar abrir o arquivo de áudio pra medir).

## 6. Registrar o webhook (`setWebhook`)

Depois do painel estar no ar com uma URL pública (ex.: já publicado no Render — ver
`render.yaml`), registre o webhook:

```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
        "url": "https://SEU-DOMINIO/api/telegram/webhook",
        "secret_token": "<TELEGRAM_WEBHOOK_SECRET>",
        "allowed_updates": ["message"]
      }'
```

Pra conferir que ficou registrado: `https://api.telegram.org/bot<TOKEN>/getWebhookInfo`. Pra
desligar o webhook (ex.: voltar a usar só o bot de conversa por polling nesse token):
`https://api.telegram.org/bot<TOKEN>/deleteWebhook`.

## 7. Convivência com o bot antigo (`telegram_bot.py`, Fase 3)

`telegram_bot.py` usa **long polling** (`getUpdates`) — a API do Telegram **não permite**
`getUpdates` funcionando ao mesmo tempo que um webhook estiver registrado pro mesmo bot
(`getUpdates` passa a devolver erro 409 assim que `setWebhook` roda pra esse token).

**Desde a Fase 7 (C1) o painel garante que os dois nunca rodam juntos no mesmo bot.** Quem
decide é `telegram_captura.modo_telegram()`, lido por `app.iniciar_telegram` (sobe ou não o
polling) e por `POST /api/telegram/webhook` (processa ou responde `503`):

| Variável | Efeito |
| :--- | :--- |
| `TELEGRAM_MODO` | `auto` (padrão), `polling`, `webhook`, `ambos` ou `desligado`. |
| `TELEGRAM_BOT_TOKEN_CAPTURA` | Token de um **bot separado** só pra captura (recomendado). Sem ela, a captura usa o mesmo `TELEGRAM_BOT_TOKEN` do bot antigo. |

Regras:

- **Bots separados** (`TELEGRAM_BOT_TOKEN_CAPTURA` diferente de `TELEGRAM_BOT_TOKEN`): os dois
  podem rodar juntos (`auto`/`ambos`); `polling`/`webhook` liga só um deles.
- **Um bot só**: nunca os dois. `auto` escolhe o **webhook** quando `TELEGRAM_WEBHOOK_SECRET`
  está configurado (sinal de que o `setWebhook` foi feito - o polling daria 409), senão o
  **polling**. `ambos` com um bot só vira webhook. `polling`/`webhook` forçam o modo.
- Webhook fora do modo responde **503** (depois de conferir o segredo, que continua dando 401
  se estiver errado): o Telegram guarda o update e reenvia, e o erro aparece em
  `getWebhookInfo` (`last_error_message`) - nada se perde.
- Pra voltar pro polling com um bot só: `TELEGRAM_MODO=polling` **e** `deleteWebhook` no
  Telegram (senão o `getUpdates` continua dando 409).

Recomendação: criar um bot só pra captura (seção 1) e pôr o token dele em
`TELEGRAM_BOT_TOKEN_CAPTURA`. As duas variáveis novas precisam entrar no `.env.example`
(integrador).

## 8. O que cada tipo de mensagem faz

| Você manda... | O painel faz |
|---|---|
| Texto (ex.: "lembra de pagar a água amanhã") | Mesma classificação de `/api/capture` (tarefa/gasto/meta) — resumo curto de volta. |
| Um link puro (só a URL, nada mais no texto) | Resume a página (`claude_client.resumir_link`) e salva em "Salvos pra ver depois" — resumo de volta. |
| Áudio (mensagem de voz) | Transcreve (Groq, seção 5) e roda o mesmo fluxo de texto acima — a transcrição também aparece na resposta, pra você conferir se entendeu certo. |
| Foto de nota fiscal/cupom | Lê valor/estabelecimento/data (`claude_client.extrair_nota_fiscal_foto`) e já registra como gasto (com Desfazer — abra o app pra desfazer, o Telegram não mostra o botão). Sem um valor claro na foto, pede pra mandar por texto. |
| Qualquer outra coisa (figurinha, vídeo, documento...) | Avisa que só entende texto/áudio/foto por enquanto. |

## 9. Idempotência

O Telegram reenvia um update que não recebeu `200` a tempo (ex.: o site estava dormindo/
acordando). `rotas/n2_telegram.py` guarda cada `update_id` já processado (tabela
`telegram_updates_processados`, `migracoes/202609241310_n2_telegram.sql`) — um reenvio do
mesmo `update_id` responde `200` sem processar de novo (nunca duplica tarefa/gasto/nota
salva).
