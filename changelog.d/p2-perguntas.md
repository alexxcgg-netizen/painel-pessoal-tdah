### Fase 7, P2 - perguntas de acompanhamento (backend, sem IA)

- `assistente/gatilhos/p2_perguntas.py`: `executar(conn, agora)` com 5
  gatilhos sem IA, cada um idempotente via `chave_unica` no formato
  `p2_<subtipo>:<id>:<data>`:
  - conta pessoal (`contas_pessoais`) no dia do vencimento e ainda nao paga
    -> "Pagou X?" (sim marca paga via `db.marcar_conta_paga`; ainda nao/adiar
    nao mexem no estado).
  - evento/reuniao da agenda (CalDAV/iCloud, via `caldav_client.eventos_do_dia`,
    so quando configurado - sem chamada real em teste) que ja terminou ->
    "Como foi X? Algo a anotar?"; "anotar" com texto vira nota
    (`db.create_nota`).
  - tarefa com `due_date` vencido -> "Fez X?"; sim conclui
    (`db.complete_task`), ou adia (amanha / proxima semana / escolher
    data livre, ISO ou BR) via UPDATE direto em `tasks.due_date`.
  - lembrete (`lembretes`, unico ou recorrente anual - reusa
    `notificacoes.proxima_ocorrencia_lembrete`) sem resposta -> reenviado
    como pergunta; "feito" apaga o lembrete unico (recorrente fica, volta
    ano que vem), "adiar" empurra a data 1 dia.
  - "esperando resposta de X" (`esperas`) parada ha N dias (config
    `assistente.p2.espera_dias`, padrao 3) -> "Ainda esperando X sobre Y?";
    "ja respondeu" resolve (`db.resolver_espera`), "cobrar" so fecha o item
    sem mudar estado.
  - `ao_resolver(conn, item, resposta, texto, agora=None)` despacha pelo
    prefixo/subtipo de `item["origem"]` pro handler certo.
  - Vida amorosa/relacionamento (decisao do Alex, ja documentada em
    `db.py`) nunca vira pergunta - filtro de palavra-chave em
    `assistente/perguntas.py:eh_relacionamento`, aplicado nos 5 gatilhos.
  - Flag `assistente.p2.ativo` (padrao ligado) desliga a faixa inteira.
- `assistente/perguntas.py`: logica pura (sem banco, sem relogio real) -
  filtro de relacionamento, textos das perguntas, parse de data livre
  (ISO/BR/dia-mes), calculo de data de "adiar" tarefa, parse do limiar de
  dias de espera.
- Nao precisou de migracao/tabela nova - `contas_pessoais(_pagas)`,
  `esperas`, `notas`, `tasks`, `lembretes` ja tinham tudo (ver
  `scripts/ralph-p2-perguntas/progress.txt`).
- `assistente/caixa.py` (P1a) ainda nao existe nesta integracao - import
  tardio de `enfileirar` dentro da funcao, mockado nos testes via
  `sys.modules` (nenhuma dependencia da P1a pronta pra rodar
  `tests/test_fase7_p2_perguntas.py`, 79 testes, relogio sempre injetado).
