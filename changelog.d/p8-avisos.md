### Fase 7, P8 - central de avisos (backend)

- `assistente/avisos.py`: implementa `aviso_permitido(tipo, agora=None)` do
  contrato do assistente proativo - liga/desliga por tipo, canal (push,
  caixa, ambos) e horario de silencio (global 22:00-07:00 por padrao, com
  override opcional por tipo). Catalogo `TIPOS` com ~49 tipos de aviso: as
  6 proatividades da Fase 6, os tipos ja existentes no pipeline de push de
  `notificacoes.py`/`app.py`, e os novos da Fase 7 (pergunta de conta,
  reuniao, tarefa vencida, lembrete, espera, briefing manha/noite, regra,
  sinal, memoria viva, replanejar). Config guardada em
  `configuracoes.assistente_avisos_config` (JSON, so overrides).
- `rotas/p8_avisos.py`: `GET /api/assistente/avisos`,
  `PUT /api/assistente/avisos/<tipo>`, `PUT /api/assistente/avisos/silencio`.
- Ainda NAO ligado ao pipeline antigo de push (`app.py:verificar_e_notificar`)
  - ponto exato de integracao anotado em `scripts/ralph-p8-avisos/progress.txt`.
