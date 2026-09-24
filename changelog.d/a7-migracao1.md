### Fase 7 - Faixa A7 (Migração 1: captura/intent/resumo)

- **`ia/funcoes/captura.py` (reescrito)**: `classify_capture`, `classify_intent`,
  `summarize_day` e `escolher_essencial` agora chamam `ia.core.chamar_ia`
  (núcleo híbrido da faixa A1) em vez do SDK Anthropic direto - trocar de
  modelo/fornecedor é só editar `ia/config.d/<funcao>.json`, sem tocar em
  código. Mesma assinatura e mesmo formato de retorno de antes (tupla
  `(resultado, usage)`), `claude_client.py` (fachada, não editado) continua
  reexportando tudo sem quebrar `app.py`/`telegram_bot.py`.
- **`resolver_data(texto, hoje)` (novo)**: o modelo não calcula mais data
  relativa (`quando_data`/`prazo`) - só devolve a pista em texto livre ("sexta
  que vem", "em 6 meses", "até dezembro"...), e essa função pura resolve pra
  `AAAA-MM-DD`, ancorada em `hoje`. Cobre amanhã/depois de amanhã/hoje (com
  hora), dia N do mês, dia da semana (com e sem "que vem"), semana/mês que
  vem, "em N dias/semanas/meses/anos", "até <mês>" e datas inválidas (nunca
  levanta exceção, vira `None`). Reaproveita `calculos.data_ultima_parcela`
  pra soma de mês em vez de duplicar a aritmética (ver `docs/calculos.md`).
- **4 configs novas em `ia/config.d/`**: `classify_intent` (300→150 tokens de
  saída), `classify_capture` (300), `summarize_day` (400), `escolher_essencial`
  (300) - todas `ativo: false` (comportamento atual preservado), `modelo_atual`
  Haiku 4.5, `alvo` GPT-6 Luna esforço médio, fallback pro próprio Haiku.
- **`tests/test_fase7_a7_resolver_data.py` e `tests/test_fase7_a7_captura.py`
  (novos)**: 87 testes (dublês, nenhuma chamada real de API) cobrindo formato
  de retorno, schema explícito de cada função, resolução de data (incluindo
  fuzz com entradas inválidas/maliciosas/unicode), e fallback entre
  provedores fim-a-fim contra o `ia/core.py` de verdade.
- **Compatibilidade com `tests/test_claude_client.py::ClassifyIntentTestCase`**:
  esse teste mockava o cliente Anthropic de baixo nível
  (`claude_client.client.messages.create`); migrar `classify_intent` pra
  `AdapterAnthropic` (que por padrão cria seu próprio cliente) quebrava esse
  mock. Resolvido reaproveitando `ia.funcoes.chat._garantir_adapter_anthropic
  _legado()` (faixa A6, trazido pelo merge de `fase7/integracao`) antes de
  cada chamada, e afrouxando `INTENT_SCHEMA` pra não exigir/tipar
  `confianca`/`parametros` (quem sempre tolerou esses dois ausentes/com tipo
  errado foi o código Python de `classify_intent`, não um schema - exigir
  isso no schema fazia `chamar_ia` reprovar a resposta antes do código
  rodar). `tests/test_claude_client.py` 100% (30 passed, 17 subtests),
  `tests/test_modo_viagem.py` 100%, `tests/test_app.py` 528/529 (a única
  falha é uma das "6 falhas conhecidas, que dependem de horário" já
  documentadas em `docs/agentes/fase7-regras-faixa.md`, sem relação com esta
  faixa). Detalhe em `scripts/ralph-a7-migracao1/progress.txt`.
