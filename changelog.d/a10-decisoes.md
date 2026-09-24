### Fase 7 - faixa A10 (decisões da Fase 6, backend)

- **Cliente novo da API da construtora (`construtora_cliente.py`).** Decisão do
  Alex: o painel pessoal passa a mostrar gastos, entradas e tempo até a próxima
  conta a pagar da construtora (via `GET /api/resumo`/`GET /api/contas_a_vencer`
  do `financeiro-construtora`, que continua nunca sendo tocado direto) - isso
  substitui a regra antiga "nunca número da construtora". `ClienteConstrutora`:
  cache/throttle de 60s por chave (mesmo espírito do cache antigo de `app.py`),
  timeout de 5s, nunca levanta exceção pro chamador, e modo mock
  (`CONSTRUTORA_API_MOCK=1` ou `mock=True` por injeção) com dados sintéticos
  pt-BR pra rodar/testar sem a construtora disponível. API pública enxuta de
  propósito: `gastos_do_mes()`, `entradas_do_mes()`, `proxima_conta(com_valor=False)`
  - nada de faturamento/margem/lucro do lado do painel pessoal.
  `docs/contrato-api-construtora.md` documenta o contrato completo (campos,
  exemplos, erros) e, no fim, a lista exata de pontos em `app.py` que o
  integrador troca pelo cliente novo (arquivo compartilhado, não editado nesta
  faixa) e onde a regra antiga aparece hoje (`claude_client.py`, prompt do chat
  e do card "vale a pena?").
- `tests/test_fase7_a10_construtora_cliente.py`: 52 testes + 25 subtests (config
  ausente, timeout/erro de rede/HTTP de erro/JSON inválido, cache por endpoint e
  por `dias`, modo mock por injeção e por variável de ambiente, API de alto
  nível) - 100% verde, sem nenhuma chamada de rede real.
- **Ação "tomei um copo de água" sem IA (`classificador_local/regras/a10_agua.py`):
  bloqueada.** Depende da infra `classificador_local/` (Etapa 0 X1), que ainda
  não chegou em `fase7/integracao` - ver `scripts/ralph-a10-decisoes/progress.txt`.
