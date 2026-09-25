# STATUS - estado entre fases (ler primeiro numa sessão nova)

Atualizado: 2026-09-25, fim da Fase 8. `main` em dia com `origin/main`; deploy Render
(`painel-pessoal-tdah`, srv-dapsp5ugekts73f30t2g) está Live com o commit `8f203b4` + este.

## Como começar a próxima fase
1. Ler este arquivo, `REGRAS-OPERACAO` (colado pelo dono no briefing), `AGENTS.md` (regras +
   aprendizados), `MAPA.md` (mapa arquivo→função da Fase 8; regenerar/atualizar na Etapa 0
   pras áreas da fase nova) e o topo do `CHANGELOG.md`.
2. Worktree por faixa a partir de `origin/main`; nunca editar `/home/user/financeiro-construtora`.

## Fase 9 (CONCLUÍDA em 2026-09-25) - ler primeiro
- **Tudo na main** e publicado no Render (deploy automático): Etapa A (Finanças unificada, sync
  idempotente + reconciliação, extrato 15 dias, sem OFX), laboratórios B (10 HUD recusadas → 20
  apps reais → escolhida **1 "Conversa"**; Vida = variante **Grupos**), Etapa C completa.
- App agora: **4 abas** (Hoje / Tarefas / Finanças / Vida) na barra de vidro + ⚙ no topo. Mapa
  de onde foi cada seção: `docs/fase9-mapa-abas.md`. Direção visual: tokens em
  `static/css/ui/tokens.css`; referências `docs/fase9-lab2/d01.js`, `docs/fase9-lab3/v03.js`.
- Suíte final: 3776 Python + 240 JS ok; única falha = `test_formato_da_resposta` (data, antiga).
- **Pendente para o dono**: abrir o app no iPhone (fechar e abrir para pegar o cache v23),
  entrar com o PIN, tocar em Sincronizar (Render free zera o banco a cada deploy), e dizer o
  que ajustar. Laboratórios: HUD https://claude.ai/artifact/GCruFZzZ9MFT6RcFmokxuH, apps reais
  https://claude.ai/artifact/KsbJFGMP9cfwovHcDhY1Qb, Vida https://claude.ai/artifact/CKmFmoe1Z65hN2i43TkTp2.
- **Pendências técnicas**: compra parcelada sem interruptor de aviso; testes que leem `.env` real;
  teste dependente de data; revogar a chave da API do Render colada no chat; página carrega
  `summarize_day` (IA) a cada abertura — conferir se o teto de R$ 40/mês segura; `AGENTS.md` tem
  55k caracteres (regra: ≤ 12k) — enxugar numa fase própria.
- **Lições de custo desta fase**: faixas de UI grandes estouraram o teto (f9-ui 99, C-abas 189,
  P-topo 158, P-viagens 109, P-tarefas 104 chamadas). Regra prática: faixa de front = 1 aba ou 1
  componente, e prints só no fim (debug de Playwright foi o maior consumo).

## Feito
- **Antes da Fase 8:** modo teste de IA (toggle no card Custo de IA, aba Painel; config
  `configuracoes.modo_teste_ia`, desligado por padrão; resposta de cards fixa sem chamar IA
  nem gravar histórico) - commit `7713d07`.
- **Fase 8 (visual):** D1 tema escuro neutro (tokens `--cor-bg`, `--cor-superficie`,
  `--cor-superficie-2`, `--cor-borda`, `--cor-texto`, `--cor-texto-fraco`, `--cor-acento`,
  `--cor-sucesso` em `static/css/ui/tokens.css` - dono único; faixas novas só usam, não criam
  cor solta). D2 "Ruim/Ok/Bom" capitalizado + LED de concluído sóbrio. D3 hiperfoco no topo
  ao lado do comando de voz (`templates/secoes/topo/captura.html`), chat subiu. D4 checkbox
  marcado em `--cor-sucesso` (`static/css/ui/componentes/campo.css`). D5 visão do dia recolhida
  por padrão (reloginho com próximo horário). D6 clima já existia (`clima.py`,
  `/api/clima/hoje`, `#clima-chip`) - sem mudança.
- **Fase 8 (financeiro):** F1 `rotas/f8_banco.py`: `POST /api/bancos/sincronizar-nubank`
  (item via env, sem Connect) e `GET /api/gastos/unificados` (manual + banco com selo de
  origem). F2 `GET /api/gastos/proximas-cobrancas` + bloco no topo da aba Gastos, com aviso de
  "possível duplicidade" (nome normalizado, ±R$0,50, ±5 dias); lista antiga dentro de
  Assinaturas removida. F3 interruptor `avisar_antes_cobrar` por assinatura (migração
  `202609251200_f8_assinatura_aviso.sql`, default 0) + gatilho
  `assistente/gatilhos/f8_aviso_cobranca.py` (3/2/1 dias, "amanhã", idempotente).
- **Pós-fase:** `pluggy_client.get_transactions` migrado pra `/v2/transactions` com cursor (o
  `/transactions` antigo responde 410 ENDPOINT_DEPRECATED). Testado com a conexão real:
  sincronização 200, 58 lançamentos com origem "Nubank" (banco temporário) - commit `8f203b4`.

## Pluggy (valendo)
- Conexão via **Meu Pluggy → aplicação demo do Dashboard da Pluggy** (o dono conecta o banco
  no Meu Pluggy e liga o item na aplicação demo; nenhuma permissão nova é pedida). Fluxo da
  API: `POST /auth` (clientId/clientSecret) → `X-API-KEY` → `/items`, `/accounts?itemId=`,
  `/v2/transactions?accountId=` (cursor em `next`).
- Item Nubank: `ce7aa441-09c5-4bec-8436-27ed704bf374` - conector Nubank, **conta real**
  (não sandbox), contas: corrente + cartão de crédito "gold".
- Variáveis de ambiente (valores **nunca** em arquivo versionado):
  `PLUGGY_CLIENT_ID`, `PLUGGY_CLIENT_SECRET`, `PLUGGY_ITEM_ID_NUBANK`.
  - Render: as 3 configuradas via API em 2026-09-25 (demais variáveis intactas).
  - Local: `/home/user/painel-pessoal-tdah/.env` (gitignored). **Efeito colateral:** com esse
    `.env` presente, 3 testes "sem configuração" de `tests/test_app.py` falham (o app carrega
    o `.env`). Não é bug de código; corrigir na fase de segurança fazendo os testes ignorarem
    o `.env` real.
- Novo banco no Meu Pluggy = repetir a ligação na aplicação demo e criar outra variável de
  item (hoje só existe a do Nubank).

## Decisões tomadas
- Modo bruto até a fase de segurança: só duas regras valem já - toda IA nova passa pelo teto
  de R$ 40/mês; nenhuma chave em arquivo versionado.
- Aviso de cobrança é opt-in por assinatura, nunca ligado sozinho.
- Duplicidade Nubank × assinatura cadastrada: mostrar uma vez com aviso, não somar em dobro;
  cruzamento em Python (`rotas/f8_banco.py`), não no JS.
- Redução geral de informação nas telas: rodada futura, tela por tela (não inventar cortes).
- Sessão principal só coordena; subagente Sonnet para código, Haiku para mecânico; modelo
  sempre explícito ao lançar.

## Pendências
- Sincronizar Nubank no Render: o dono entra com o PIN, aba Financeiro → "Sincronizar
  Nubank" (Render free apaga o banco a cada deploy/hibernação - sincronizar de novo depois).
- Compra parcelada ainda sem interruptor de aviso (só assinatura).
- Aba Tarefas só lista pendentes (concluídas não aparecem).
- Testes que leem o `.env` real (ver Pluggy acima).
- Falha pré-existente dependente de data: `tests/test_fase7_n1_rotas.py::test_formato_da_resposta`
  e 4 testes de notificação de voo em `tests/test_app.py` (`test_verificar_*voo*`), que já
  falhavam na `main` antes da Fase 8.
- Recomendação de segurança ao dono: revogar a chave da API do Render que foi colada no chat.

## Custo (medido nos transcritos, para planejar)
- Fase 8: ~59 M tokens (subagentes 32,2 M em 9 faixas, máx. 116k de contexto, nenhuma chamada
  acima de 150k; sessão principal 26,6 M em 57 chamadas, com contexto de ~450-519k por ser a
  mesma conversa desde a Fase 7). Fase 7 foi ~1.160 M.
- Estouraram o teto de 50 chamadas: F3 71, D2+D4 63, F1 59, F2 54.
- **Lições:** sessão nova por fase (principal começa em ~50k); teto de 40 chamadas e uma
  história por faixa; agrupar tarefas pequenas num Haiku.

## Testes (fim da Fase 8)
Suíte completa: 3458 Python ok + 226 JS ok; falhas só as conhecidas acima (`.env` real e
teste dependente de data).
