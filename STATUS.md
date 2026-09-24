# STATUS - Fase 7 (atualizado pelo integrador a cada rodada)

Atualizado: 2026-09-24 (final)

## Estado
**Fase 7 concluída na integração, aguardando merge na main.**
- Integração: `fase7/integracao`. Consolidação final da documentação na branch
  `fase7/m1-final` (sai dela pra integração, depois `main`).
- Falta: suíte completa na integração depois do `m1-final` e o merge na `main` (integrador).
- Bloqueadas: nenhuma.
- Rollback: tag local `pre-fase-7` ou commit `789171d` (push de tag bloqueado, 403).
- O que mudou: entrada "Fase 7 (v12)" no topo do `CHANGELOG.md`. Pegadinhas: seção
  "Aprendizados da Fase 7" no `AGENTS.md`.

## Faixas integradas (47 + Etapa 0)
- **Etapa 0**: contratos (`ia/contrato.py`, `assistente/contrato.py`), X1 backend, X2
  frontend, `donos.json`, `scripts/testes.sh`, `scripts/integrar.sh`.
- **IA (15)**: A1 núcleo, A2 adapter Anthropic, A3 adapter OpenAI, A4 medição e teto,
  A5 histórico, A6 chat, A7 migração 1, A8 migração 2, A9 visão, A10 decisões da Fase 6,
  A11 A/B, A12 infra de testes, A13 cálculos, A14 roteador, A15 Gemini.
- **Finanças/Telegram/Widgets (6)**: N1 assinaturas e parcelas, N2 Telegram, N3a endpoint do
  widget, N3b Scriptable, N3c/N3d docs de widget, N3e WidgetKit.
- **Assistente (9)**: P1a Caixa, P1b Caixa UI, P2 perguntas, P3 briefing, P4 regras,
  P5 replanejar, P7 sinais do iPhone, P8 central de avisos, P9 memória viva.
- **Visual (10)**: V0a tokens/MASTER, V0b botões, V0c seções/cards, V0d bottom sheet e
  navegação, V1 Hoje, V2 Painel, V3 organização, V4 Vida, V5 Viagens/Aviação (v5-extra),
  V6 Finanças.
- **Polimento (5)**: C1 backend, C2 visual (V0-V3, P1b), C3a Vida, C3b Viagens, C3c Finanças.
- **Integração (2)**: m1-front (foco global, `[hidden]`, Desfazer da N1, sheet/campo/seção)
  e m1-final (CHANGELOG, AGENTS, TODO, STATUS, `.env.example`, service worker v15,
  MASTER, percentual pt-BR em "Seu progresso", gitleaks zerado).

## Achados do integrador (resolvidos)
- Worktree automática do ambiente cobre o repo errado (`financeiro-construtora`); as faixas
  criam worktree própria do painel. Nada foi editado no `financeiro-construtora`.
- Custo com fonte única (`ia/precos.py`), provedor Gemini registrado no núcleo, A/B em
  `--dry-run` sem consultar o teto real, testes de infra isolados.
- `origem` da Caixa = `<arquivo do gatilho>:<resto>`; a P3 não gravava o humor (C1).
- Regra local da P4 engolia remédio/tarefa recorrente/brain dump (corrigido).
- Todas as "pendências pro M1" anotadas pelas faixas foram fechadas (C1, C2, C3, m1-front).

## Pendências abertas (perguntas pro Alex, detalhe no `TODO.md`)
- Modo economia do teto: liberar classificação a 100% ou manter "o teto vale pra tudo"?
- Aviso de teto por push ainda não funciona no teto padrão de R$ 40.
- Memória: adicionar inline ou em bottom-sheet?
- Valor dos cards de assinatura/parcela no modo visitante (front mostra, servidor esconde).
- Visão no GPT-6 Luna: testar a primeira chamada real ao ligar `ativo: true`.
- `telegram_bot.py` parar sozinho ao receber 409.

## Pendências técnicas pequenas (sem dono nesta rodada)
- `static/css/ui/tokens.css` ~l.106: comentário do `--anel-foco` ainda diz que o foco global
  usa `--accent-2` (o `style.css` já usa `--anel-foco`).
- Docstrings de `tests/test_app.py` e `tests/test_vida_fase3.py` citam
  `changelog.d/a12-testes.md`, que virou parte da entrada da Fase 7 no `CHANGELOG.md`.
