---
name: ler-chat
description: Lê a conversa do Alex com a IA do app (chat do Painel Pessoal) pra entender o que ele pede, o que ele corrige e o que não gosta. Usar quando ele pedir "lê o chat", "olha o que eu falei pra IA", "vê a conversa", ou antes de mexer no comportamento/prompt/ferramentas do chat do app.
---

# Ler o chat do app

Pedido do Alex (2026-10-15): "toda vez que tu pedir, essa cópia do chat vai pra você" - ele quer
que o Claude Code acompanhe a conversa dele com a IA do painel, inclusive coisa pessoal, pra
entender melhor o que ele gosta e o que não gosta. A conversa é só entre ele e o Claude.

## Como
1. `.venv/Scripts/python.exe scripts/ler_chat.py` (últimos 7 dias; `--dias 30`,
   `--desde AAAA-MM-DD --ate AAAA-MM-DD`). Abre `data/painel.db` em **modo só leitura**
   (`mode=ro`) - nunca grava, nunca importa `app.py`.
2. Ler `data/chat_para_claude.md` (Read). Formato: um bloco por dia, `**HH:MM Alex:**` /
   `**HH:MM IA:**`, cards resumidos em `↳ card \`tipo\`: campos`. `⚠` marca mensagem dele logo
   depois de uma resposta que *parece* correção (só pista - ler o contexto).
3. Responder ao Alex com o que deu pra entender: o que ele pediu, onde a IA errou ou fez ele
   repetir, padrões (ex.: prefere que a IA escolha o horário), bugs vistos (card duplicado, card
   que contradiz o texto, ferramenta que falta). Separar "já corrigido" de "ainda acontece"
   conferindo no código antes de afirmar.
4. Se ele reclamar de barra de abas cortada ou microfone que falha: olhar a seção final
   "Diagnóstico do aparelho" (medidas reais do iPhone, `rotas/diagnostico.py`). `tela`: `bruto`
   vs `ancora`/`aplicado` diz se a barra foi empurrada e quanto (`clientH` NÃO é onde ela se prende no iOS); `barraFundo` maior que `vvH`/
   `innerH` = barra saindo da tela. `mic`: `evento` diz o que falhou (`falhou` com o nome do erro,
   `tentou_de_novo`, `detector_surdo`, `detector_falhou`, `curto`).

## Regras
- A cópia tem coisa pessoal (endereços, nomes, saúde, dinheiro): fica só em `data/` (gitignored).
  **Nunca** copiar trecho dela pra commit, `docs/`, CHANGELOG, teste ou artefato publicado -
  nesses lugares, só o aprendizado generalizado, sem nome/endereço/valor.
- Números longos (CPF, cartão, conta, telefone) e o que vem depois de "senha/pin/token/chave
  pix" já saem como `[oculto]`; se aparecer outra coisa sensível, não repetir na resposta.
- Preferência dele que aparecer no chat e valer pra sempre → memória (`feedback`), em termos
  gerais. Mudança no comportamento da IA do app → seguir o fluxo normal (briefing, teste, CHANGELOG).
