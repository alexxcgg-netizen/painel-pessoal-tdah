### Fase 7, faixa A11 - Teste A/B de IA

- **`scripts/ab_teste_ia.py`**: compara modelo atual x candidato por função de IA do
  painel (Sol x Sonnet 5 no `chat`/`analisar_decisao`/`redigir_mensagem_dificil`,
  julgado às cegas pelo tom, com gabarito em arquivo separado; Luna x Haiku 4.5
  [+ Gemini Flash-Lite se houver `GEMINI_API_KEY`] nas 9 funções simples; Luna x
  Sonnet 5 em nota fiscal/cotação). Mede acerto contra o gabarito das fixtures,
  % de JSON válido, custo, tokens e latência; imprime recomendação (acerto igual
  ou melhor, JSON válido > 98%, custo menor) e gera `relatorio_ab.html` +
  `relatorio_ab.gabarito.json`.
  - Não usa `ia.core.chamar_ia` (nenhuma das 14 funções tem `ia/config.d/<funcao>.json`
    ainda - não foram migradas pra `ia/core`, seguem em `claude_client.py`). Chama o
    adapter direto, reaproveitando a mesma descoberta/execução do núcleo
    (`ia.core._obter_adapter`/`registrar_adapter`/`_chamar_uma_vez`/`_erro_de_rede`/
    `_extrair_json`/`validar_schema`/`_teto_permite`) sem editar `ia/core.py`.
  - `--dry-run` (usado pelos testes) registra adapters-dublê no núcleo - nenhuma
    chamada real, nenhuma credencial necessária. Modo real depende de
    `ia/adapters/{anthropic,openai}.py` (faixas A2/A3) estarem mergeados em
    `fase7/integracao` (ainda não estavam em 2026-09-24 - ver progress.txt).
  - `extrair_item_cotacao_pdf` via Luna (OpenAI): adapter A3 ainda não converte
    PDF/documento (só imagem/texto) - o script detecta isso e marca o item como
    "pulado" no relatório em vez de fingir que o teste rodou.
  - `tests/fixtures/ab/<funcao>.json`: fixtures sintéticas pt-BR, 5-6 por função
    (14 funções), com campo `esperado` (gabarito) quando aplicável.
  - `tests/test_ab_teste_ia.py`: 58 testes, tudo com `--dry-run`.
  - `docs/ab-teste.md`: como rodar no fim com as chaves reais, flags, modelos
    comparados, critério de recomendação e limitações conhecidas (chat sem
    tool-use, cotação PDF via Luna, preços simulados).
