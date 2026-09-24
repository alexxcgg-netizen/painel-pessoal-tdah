## Fase 7 P3: briefing da manha e fechamento da noite

- `assistente/briefing.py`: montagem por codigo (sem IA) dos dois briefings
  proativos do dia. Manha: agenda, tarefas pendentes, habitos do dia e
  contas dos proximos dias (pessoais + "proxima conta a pagar" da
  construtora, so nome e quando - nunca valor, integracao HTTP read-only
  ja existente). Noite: fechamento (reaproveita
  `notificacoes.mensagem_fechamento_noturno`), o que passa pra amanha e a
  pergunta "Como foi o dia?" com opcoes curtas (vira `checkins.humor` na
  resposta). Horarios configuraveis (padrao 07:30/21:00) e flags
  `assistente.p3.ativo` / `assistente.p3.reescrever_ia` (Luna, opcional,
  desligada) em `configuracoes`.
- `assistente/gatilhos/p3_briefing.py`: `executar(conn, agora)` idempotente
  (chave_unica por dia), dispara na janela do horario configurado;
  `ao_resolver` grava o humor do fechamento.
- `rotas/p3_briefing.py`: `GET/PUT /api/assistente/briefing/horarios`,
  `GET /api/assistente/briefing/previa?tipo=manha|noite`.
- `ia/config.d/reescrever_briefing.json`: config da reescrita opcional.
- Testes: `tests/test_fase7_p3_briefing.py`,
  `tests/test_fase7_p3_gatilho.py`, `tests/test_fase7_p3_rotas.py` - 49
  casos, 0 falhas (dia vazio, dia cheio, virada de dia, horario editado,
  nao dispara 2x, ao_resolver, rotas).
- Pendente pro integrador: ver nota de duplicidade com o push antigo de
  fechamento noturno em `scripts/ralph-p3-briefing/progress.txt`.
