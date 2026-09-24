# STATUS - Fase 7 (atualizado pelo integrador a cada rodada)

Atualizado: 2026-09-24 (rodada 7)

## Resumo
- Integracao: `fase7/integracao` (nada vai pra `main` ate o fim da 7C).
- Etapa 0 completa: contratos, extracao do backend (X1) e do frontend (X2), donos.json, testes.sh, integrar.sh.
- Integradas (38): todas as faixas A, N, P e V, menos a V5 (+ X1, X2).
- Rodando (3): V5 (Viagens/Aviacao), C1 (polimento backend), C2 (polimento visual V0-V3/P1b).
- Proxima: C3 (visual V4-V6) quando a V5 entrar; depois M1 final e merge na main.
- Falta depois: 7C (C1 backend, C2/C3 visual), consolidacao M1 (CHANGELOG/AGENTS/TODO,
  service worker, gitleaks, suite completa) e merge na main.
- Bloqueadas: nenhuma.
- Limite de uso: sem aviso (creditos extras ativos). Limite de 20 subagentes simultaneos da sessao.

## Achados do integrador
- Isolamento automatico de worktree do ambiente cobre o repo errado (financeiro-construtora);
  faixas criam worktree propria do painel. Nada foi editado no financeiro-construtora.
- Adapters liam precos.json em formatos diferentes do real (custo 0 silencioso) - corrigido com ia/precos.py.
- Nucleo nao conhecia o provedor gemini e o preco do Gemini tinha id errado - corrigido.
- Contrato do assistente: `origem` = `<arquivo do gatilho>:<resto>` (divide no primeiro `:`);
  assistente/contrato.py agora delega pra caixa (P1a) e avisos (P8).
- Testes de infra supunham pastas vazias - isolados.
- A/B em --dry-run consultava o teto real - corrigido.
- Push de tag bloqueado (403); rollback pela tag local `pre-fase-7` ou commit `789171d`.

## Pendencias pro M1 (anotadas pelas faixas)
- [feito] Liga/desliga por tipo (P8) no loop de push antigo: usa `esta_ligado`, nao `aviso_permitido`
  completo (o silencio padrao 22h-7h calaria urgente e o lembrete de sono das 22h).
- [feito] registrar_tarefa do chat grava data resolvida em codigo (A6 resolver_quando_data).
- [feito] Adapter Anthropic: esforco vazio ou modelo Haiku nao manda effort/thinking (achado da A6).
- [feito] loadCustoIAV2 ligado na aba painel; aba assistente no ORDEM_ABAS.
- Chat: passar contexto_fixo da A5 + medir_uso=True (A6) - cuidado com contagem dupla de uso
  (_log_usage antigo + uso_ia novo) e historico duplicado - vai pra C1.
- [feito] tests/conftest.py: rede de seguranca que nunca deixa teste gravar no data/painel.db do checkout.
- [feito] Regra local da P4 engolia remedio/tarefa recorrente/brain dump - corrigido.
- Push antigo `fechamento_noturno` (21h) duplica o briefing da noite da P3 - desligar um.
- `POST /api/plano-do-dia` antigo nao checa teto (P5) - vira automatico com A8.
- Trocar acesso a construtora em app.py pelo construtora_cliente.py (A10, docs/contrato-api-construtora.md).
- Datas relativas: modelo nao deve calcular (A13/docs/calculos.md) - A6/A7 tratam.
- Percentual de meta duplicado (cards.py x app.py, arredondamentos diferentes) - A13.
- Foco visivel quase invisivel no style.css (V0a) - usar --anel-foco.
- Telegram: webhook novo x polling antigo no mesmo bot (N2) - usar bot separado.
- Tipos da Caixa x catalogo de avisos da P8 nao batem (P1a) - liga/desliga fino ainda nao alcanca a Caixa.
