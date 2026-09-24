# STATUS - Fase 7 (atualizado pelo integrador a cada rodada)

Atualizado: 2026-09-24 (rodada 5)

## Resumo
- Integracao: `fase7/integracao` (nada vai pra `main` ate o fim da 7C).
- Etapa 0 completa: contratos, extracao do backend (X1) e do frontend (X2), donos.json, testes.sh, integrar.sh.
- Integradas (25): A1, A2, A3, A4, A5, A10, A11, A13, A14, A15, N2, N3a, N3b, N3c/N3d, N3e,
  P1a, P2, P3, P4, P5, P7, P8, P9, V0a (+ X1, X2).
- Rodando (16): A6, A7, A8, A9, A12, N1, V0b, V0c, V0d, V1, V2, V3, V4, V5, V6, P1b.
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
- Ligar `assistente.avisos.aviso_permitido` no loop de push antigo (app.py ~4512, P8).
- Push antigo `fechamento_noturno` (21h) duplica o briefing da noite da P3 - desligar um.
- `POST /api/plano-do-dia` antigo nao checa teto (P5) - vira automatico com A8.
- Trocar acesso a construtora em app.py pelo construtora_cliente.py (A10, docs/contrato-api-construtora.md).
- Datas relativas: modelo nao deve calcular (A13/docs/calculos.md) - A6/A7 tratam.
- Percentual de meta duplicado (cards.py x app.py, arredondamentos diferentes) - A13.
- Foco visivel quase invisivel no style.css (V0a) - usar --anel-foco.
- Telegram: webhook novo x polling antigo no mesmo bot (N2) - usar bot separado.
- Tipos da Caixa x catalogo de avisos da P8 nao batem (P1a) - liga/desliga fino ainda nao alcanca a Caixa.
