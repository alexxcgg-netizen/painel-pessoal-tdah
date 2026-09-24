### Fase 7 - Faixa P9 (memoria viva)

- **`assistente/memoria_viva.py` (novo)**: uma vez por semana, detecta
  padroes de comportamento inteiramente em codigo (nenhum numero vem da
  IA) - horario medio de um habito de treino, media de horas de sono,
  gastos recorrentes/assinaturas (reaproveita `gastos.
  detectar_gastos_recorrentes`) e itens de rotina cumpridos com
  consistencia (>=85% dos ultimos 14 dias) - e chama `ia.core.chamar_ia
  ("propor_memoria", ...)` uma vez por fato so pra REDIGIR o texto,
  nunca pra decidir o numero. Schema valida
  `{"propostas":[{"acao","memoria_id","texto","motivo"}]}`. Filtro
  `contem_assunto_proibido` (regex com borda de palavra) descarta qualquer
  proposta sobre vida amorosa/relacionamento ou com valor financeiro da
  construtora - roda tanto no dado de origem (nome de habito, texto de
  rotina, descricao de gasto) quanto no texto final da IA.
- **`assistente/gatilhos/p9_memoria.py` (novo)**: `executar(conn, agora)`
  roda so domingo a noite (>=19h), idempotente por semana ISO (flag
  `assistente.p9_memoria.ativo`, padrao ligado) - cada proposta vira item
  da Caixa (`tipo="proposta_memoria"`, opcoes aceitar/recusar,
  `chave_unica="p9:<semana>:<chave-do-fato>"`). `ao_resolver` aplica a
  memoria com `db.create_memoria`/`update_memoria`/`delete_memoria`
  quando aceito; quando recusado, so registra (tabela
  `p9_memoria_recusas`) - a mesma chave nao e reproposta por 8 semanas.
- **`ia/config.d/propor_memoria.json` (novo)**: `ativo: false`,
  `modelo_atual` Haiku 4.5, `alvo` openai `gpt-6-luna` esforco medio,
  `max_tokens_saida` 500.
- **`migracoes/202609241250_p9_memoria_recusas.sql` (novo)**: 2 tabelas
  pequenas e proprias desta faixa (`p9_memoria_propostas`,
  `p9_memoria_recusas`) - tambem criadas sob demanda pelo proprio
  `p9_memoria.py` porque a infra de migracao automatica ainda nao estava
  integrada nesta branch (ver `scripts/ralph-p9-memoria/APRENDIZADOS.md`).
- **Testes**: `tests/test_fase7_p9_memoria_viva.py` +
  `tests/test_fase7_p9_gatilho.py` - IA e Caixa sempre mockadas, relogio
  sempre injetado, com fuzzing de texto/entrada corrompida (marcado_em
  ilegivel, origem nao-string, resposta fora do enum, JSON fora do
  schema). 58 passed (52 subtests), 0 failed.
