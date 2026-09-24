### Fase 7 - faixa A9 (visao: nota fiscal e cotacao em PDF)

- `extrair_nota_fiscal_foto`/`extrair_item_cotacao_pdf` (`ia/funcoes/visao.py`)
  migradas pra `ia.core.chamar_ia` (schema JSON), mesma assinatura/retorno
  de hoje (`tuple[dict, dict]`). Prompts ganharam um campo novo `confianca`
  (0.0-1.0); se a resposta vier com confianca abaixo de 0.7 (ou JSON fora do
  schema/invalido), a funcao refaz a chamada uma vez antes de desistir
  (levanta `RuntimeError` se as duas falharem).
- Configs novas `ia/config.d/extrair_nota_fiscal_foto.json` e
  `extrair_item_cotacao_pdf.json`: `ativo: false` (comportamento identico ao
  de hoje, Sonnet 5), `alvo` openai `gpt-6-luna` esforco medio, `fallback`
  Sonnet 5, `max_tokens_saida: 500`.
- `ia/lote.py` (`processar_lote(funcao, itens, ...)`): processa varios itens
  da mesma funcao de IA forcando `opcoes["modo"] = "flex"` (o adapter OpenAI
  mapeia pra `service_tier="flex"`, metade do preco) - base pronta pra
  extrato bancario em lote no futuro; nada usa isto ainda (foto de nota
  fiscal continua em modo padrao, na hora).
- `tests/test_fase7_a9_extracao_visao.py` (16 casos, tudo com dublê, PDF/
  imagem sinteticos gerados no proprio teste - a imagem via Pillow):
  retorno identico + formato de mensagem, fallback por confianca baixa,
  fallback por JSON invalido, fallback automatico via config quando
  `ativo: true` (dois modelos distintos), lote sempre em modo flex,
  resiliencia a item que falha no lote.
- Nota tecnica (ver `scripts/ralph-a9-visao/APRENDIZADOS.md` pro detalhe):
  o adapter Anthropic (`ia/adapters/anthropic.py`, faixa A2) NAO converte o
  formato de imagem/documento - repassa `mensagens` cru pro SDK. Como as
  duas configs nascem com `ativo: false`, as mensagens usam o formato
  nativo da Anthropic (igual ao codigo antigo); quando `ativo` virar `true`
  (migracao pro GPT-6 Luna), este arquivo tambem vai precisar passar a
  montar as mensagens no formato que `ia/adapters/openai.py` espera.
