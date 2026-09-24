# STATUS - Fase 7 (atualizado pelo integrador a cada rodada)

Atualizado: 2026-09-24 (rodada 2)

## Resumo
- Integracao: `fase7/integracao` (nada vai pra `main` ate o fim da 7C).
- Faixas integradas: A1, A2, A3, A4 (+ custo unificado em ia/precos.py). 125 testes de IA passando.
- Em andamento: X1 (extracao backend), X2 (extracao frontend), A5, A11, A12, A13, A15, N3b, N3c/N3d, N3e.
- Esperando a Etapa 0 (X1/X2): A6-A10, A14, N1, N2, N3a, P1a-P9, V0a-V6.
- Bloqueadas: nenhuma.
- Limite de uso: sem aviso ate agora.

## Por faixa
| Faixa | Estado | Nota |
|---|---|---|
| A1 nucleo | integrada | 45 testes; teto checado dentro de chamar_ia |
| A2 Anthropic | integrada | 22 testes; erro de rede sobe pra retry |
| A3 OpenAI | integrada | 19 testes; Luna/Sol, Flex, visao; SDK openai 3.19.2 |
| A4 medicao/teto | integrada | 39 testes; teto R$ 40, cambio 5,50, desfazer nunca bloqueia |
| X1 backend | rodando | |
| X2 frontend | rodando | |
| A5, A11, A12, A13, A15, N3b, N3cd, N3e | rodando | |

## Achados do integrador
- Isolamento automatico de worktree do ambiente cobre o repo errado (financeiro-construtora);
  faixas criam worktree propria do painel. Nada foi editado no financeiro-construtora.
- Adapters liam precos.json em formatos diferentes do real (custo 0 silencioso) - corrigido.
- Push de tag bloqueado (403); rollback pela tag local `pre-fase-7` ou commit `789171d`.
