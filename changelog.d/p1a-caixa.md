### Fase 7, P1a - núcleo da Caixa do assistente (backend)

- `assistente/caixa.py`: implementa `enfileirar`/`resolver` do contrato
  compartilhado (`assistente/contrato.py`), mais `listar` (ordenado por
  urgência: pergunta vencida > pergunta > aviso > sugestão > briefing >
  proposta de memória), `contar_pendentes`, `processar_repeticoes`
  (reenvio de push depois de 2h e 4h, máximo 3 por dia, respeitando
  `aviso_permitido` da P8) e `expirar`. Quando um item é resolvido, chama
  o `ao_resolver` do gatilho de origem (`assistente/gatilhos/<módulo>.py`)
  se ele existir. Filtra vida amorosa/relacionamento antes de criar
  qualquer item (decisão do Alex, fora do escopo da Caixa).
- `migracoes/202609241200_p1a_assistente_itens.sql`: tabela
  `assistente_itens` com dedupe por `chave_unica`.
- `rotas/p1a_caixa.py`: `GET /api/assistente/caixa`,
  `POST /api/assistente/caixa/<id>/responder`, `POST /api/tick` (token,
  chama todos os gatilhos + repetição + expiração) e
  `GET /api/assistente/saude` (avisa se o tick está atrasado).
- `docs/tick.md`: como configurar um cron externo (grátis) ou
  systemd timer/cron numa VPS pra chamar `/api/tick` a cada 5 minutos -
  necessário porque o Render grátis dorme sem requisição HTTP chegando.
- 97 testes novos (`tests/test_fase7_p1a_caixa.py`,
  `tests/test_fase7_p1a_rotas.py`), relógio sempre injetado.
