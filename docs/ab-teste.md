# Teste A/B de IA (Fase 7, faixa A11)

`scripts/ab_teste_ia.py` compara modelo atual x candidato, função por função do
painel, antes de o Alex trocar de verdade o `modelo_atual`/`alvo` de uma função em
`ia/config.d/<funcao>.json`. Mede acerto (quando a fixture tem gabarito), % de JSON
válido, custo, tokens e latência, e imprime uma recomendação por critério fixo. Para
`chat`, `analisar_decisao` e `redigir_mensagem_dificil` (texto livre/tom), a decisão
nunca é automática — o script gera um relatório às cegas para o Alex escolher.

## Como rodar

**Agora (desenvolvimento, sem chaves — o que os testes usam):**

```bash
.venv/bin/python scripts/ab_teste_ia.py --dry-run
```

Usa dublês (`ia.core.registrar_adapter`) — nenhuma chamada real, nenhuma credencial
necessária. É exatamente o que `tests/test_ab_teste_ia.py` roda.

**No fim (com as chaves reais do Alex):**

```bash
export ANTHROPIC_API_KEY=...
export OPENAI_API_KEY=...
export GEMINI_API_KEY=...   # opcional - sem ela, Gemini Flash-Lite fica de fora
.venv/bin/python scripts/ab_teste_ia.py
```

Sem `--dry-run`, o script chama os provedores de verdade. **Pré-requisito**:
`ia/adapters/anthropic.py` (faixa A2) e `ia/adapters/openai.py` (faixa A3) precisam
já estar mergeados em `fase7/integracao` — em 2026-09-24, quando esta faixa (A11) foi
escrita, ainda não estavam (ver `scripts/ralph-a11-ab/progress.txt`). Sem eles, toda
chamada real falha com um erro claro (`adapter do provedor 'anthropic' indisponível
(...)`) — o script não trava, só reporta a falha por item.

### Flags

| Flag | Padrão | O que faz |
|---|---|---|
| `--dry-run` | desligado | Usa dublês, nenhuma chamada real. |
| `--fixtures-reais <caminho>` | `fixtures_reais/` | Pasta com exemplos reais do Alex (já no `.gitignore` desde a Etapa 0). |
| `--funcoes f1,f2` | todas as 14 | Roda só as funções listadas. |
| `--saida <pasta>` | `<fixtures-reais>/relatorios_ab/` | Onde gravar o relatório (essa pasta também cai dentro do `.gitignore`, por estar sob `fixtures_reais/` — nunca comitar um relatório gerado com dado real do Alex). |
| `--seed <n>` | `42` | Semente do embaralhamento A/B às cegas (reprodutibilidade). |

## Fixtures

- **Sintéticas** (`tests/fixtures/ab/<funcao>.json`, uma lista de ≥5 cenários por
  função, comitadas): usadas sempre, inclusive nos testes automatizados. Cada item
  tem `id`, `entrada` (os argumentos da função) e, quando aplicável, `esperado`
  (gabarito) — sem `esperado`/sem o campo relevante, a função conta como "acerto não
  medido" pra aquele item (fora da média, sem travar a recomendação sozinho).
- **Reais** (`--fixtures-reais`, padrão `fixtures_reais/`, gitignored — nunca sai do
  ambiente do Alex): aceita um arquivo `<funcao>.json` (mesma lista) e/ou uma pasta
  `<funcao>/` com um arquivo por cenário. Para nota fiscal/cotação, uma fixture pode
  apontar `imagem_path`/`pdf_path` (relativo à pasta) em vez de embutir base64 —
  o script lê o arquivo e converte na hora.
- `simulacao_dry_run` (fixture sintética, opcional): sobrescreve a resposta fabricada
  em `--dry-run` por apelido de modelo (`json_invalido`, `errar_campo`, `ids_errados`,
  `sem_conteudo_esperado`, `api_falhou`, `custo_multiplicador`,
  `latencia_extra_ms`) — existe só pra exercitar os caminhos de erro da própria lógica
  de agregação/relatório nos testes, nunca é usado fora de `--dry-run`.

## Modelos comparados (por função)

| Grupo | Funções | Linha de base | Candidato(s) |
|---|---|---|---|
| Às cegas (tom, decisão do Alex) | `chat`, `analisar_decisao`, `redigir_mensagem_dificil` | Sonnet 5 (médio) | Sol (médio) |
| Simples (JSON/texto curto) | `classify_intent`, `classify_capture`, `summarize_day`, `escolher_essencial`, `gerar_mala`, `resumir_link`, `break_down_task`, `requebrar_tarefa`, `plano_do_dia` | Haiku 4.5 ou Sonnet 5 (médio) — ver `FUNCOES` no script | Luna (médio) [+ Gemini Flash-Lite se `GEMINI_API_KEY` existir] |
| Visão (nota fiscal/cotação) | `extrair_nota_fiscal_foto`, `extrair_item_cotacao_pdf` | Sonnet 5 (médio) | Luna (médio) |

Os apelidos (`sonnet5_medio`, `sol_medio`, `luna_medio`, `haiku_4_5`,
`gemini_flash_lite`) e os IDs reais de modelo (`claude-sonnet-5`, `gpt-6-sol`,
`gpt-6-luna`, `claude-haiku-4-5-20251001`, `gemini-3-5-flash-lite`) estão no dicionário
`MODELOS` no topo do script — conferidos em 2026-09-24 lendo `ia/precos.json` e os
adapters das branches `fase7/a2-adapter-anthropic`/`fase7/a3-adapter-openai`/
`fase7/a4-medicao-teto` (nenhuma ainda mergeada em `fase7/integracao`).

## Critério de recomendação

Para os grupos "simples" e "visão", o script recomenda trocar a linha de base pelo
candidato quando **todos** os critérios medidos batem:

1. **Acerto**: candidato ≥ linha de base (contra o gabarito das fixtures que têm
   `esperado`). Se nenhuma fixture da função tiver gabarito, este critério fica
   "não medido" e não trava a recomendação sozinho.
2. **JSON válido**: > 98% das respostas do candidato (só se aplica a funções que
   devolvem JSON).
3. **Custo**: custo médio do candidato menor que o da linha de base.

Para `chat`, `analisar_decisao` e `redigir_mensagem_dificil` **não há recomendação
automática** — o relatório mostra as respostas embaralhadas (`Resposta A`/`Resposta
B`, sem dizer qual é qual) para o Alex escolher pelo tom. O gabarito (qual letra era
qual modelo) fica em `relatorio_ab.gabarito.json`, arquivo **separado** do
`relatorio_ab.html` — só abrir depois de decidir pelo tom.

## Como funciona por dentro (pra quem for mexer depois)

`ia.core.chamar_ia` (faixa A1) sempre lê `ia/config.d/<funcao>.json` — uma config
fixa por função — e não tem como forçar um provedor/modelo específico numa chamada.
Como estas 14 funções ainda não foram migradas pra `ia/core` (ainda vivem em
`claude_client.py`, chamando a Anthropic direto) e nenhuma tem esse arquivo de
config ainda, este script **não usa `chamar_ia`**: chama o adapter diretamente, mas
reaproveitando a mesma descoberta/execução que o núcleo usa — sem editar
`ia/core.py` nem duplicar a lógica:

- `ia.core._obter_adapter`/`ia.core.registrar_adapter` — mesmo cache/descoberta de
  adapter por provedor (é também assim que `tests/test_ia_core.py` registra os
  dublês da faixa A1 — o script segue o mesmo padrão).
- `ia.core._chamar_uma_vez`, `ia.core._erro_de_rede`, `ia.core.ESPERA_RETRY_S` — uma
  chamada com 1 retry em erro de rede, igual ao núcleo.
- `ia.core._extrair_json`/`ia.core.validar_schema` — usados por este script
  diretamente (fora do `_chamar_uma_vez`, que só aceita JSON raiz **objeto** — três
  das 14 funções devolvem uma **lista** no nível raiz, mesmo formato que
  `claude_client.py` já usa hoje para `break_down_task`/`gerar_mala`/
  `requebrar_tarefa`) — ver comentário em `_chamar_com_override` no script.
- `ia.core._teto_permite`, `ia.core._registrar_uso` — o teto mensal de IA é checado
  antes de cada chamada real, e todo uso é registrado em `ia.medicao` quando esse
  módulo existir (faixa A4) — mesmo import tardio/tolerante que `ia/core.py` já usa,
  então o teto/medição "ligam sozinhos" quando a A4 chegar na integração, sem
  precisar mexer neste script.

Em `--dry-run`, os mesmos `ia.core.registrar_adapter`/`_obter_adapter` são usados,
só que com um adapter-dublê (`AdapterDubleAB`, mesma ideia do `AdapterDuble` de
`tests/test_ia_core.py`) que devolve uma `Resposta` fabricada a partir do `esperado`
da fixture — nunca chama rede.

## Limitações conhecidas (documentadas, não escondidas)

- **`chat`** é testado como um único turno de texto livre (system prompt reduzido,
  só a parte de tom/persona) — **sem** o loop de tool-use de produção (`CHAT_TOOLS`
  em `claude_client.py`, ~30 ferramentas). O que está em comparação aqui é só o TOM
  da resposta, que é exatamente o critério de decisão pedido (Alex julga pelo tom).
- **`extrair_item_cotacao_pdf` via Luna (OpenAI)**: o adapter OpenAI (faixa A3,
  `ia/adapters/openai.py`) só converte partes `image`/`text` — não tem convenção de
  documento/PDF ainda. O script detecta isso (`NaoSuportado`) e marca o item como
  **pulado** no relatório (fora das estatísticas de acerto/JSON válido/custo) em vez
  de mandar um PDF disfarçado de imagem e fingir que o teste rodou. Até a A3 ganhar
  suporte a documento, esta comparação fica só com a linha de base (Sonnet 5).
- **Preços em `--dry-run`** vêm de uma tabela local (`PRECOS_SIMULADOS`, no script) —
  só pra simulação ter números plausíveis. A chamada real usa o custo calculado
  dentro do próprio adapter (lê `ia/precos.json` de verdade, quando existir).
- **Adapter Gemini** (`AdapterGeminiRest`, neste script): REST direto (sem SDK —
  `google-generativeai` não está instalado neste worktree), só texto (nenhuma função
  de visão usa Gemini como candidato). Formato conferido na documentação pública da
  API em 2026-09-24, não em código de SDK instalado (diferente de como as faixas
  A2/A3 confirmaram Anthropic/OpenAI) — reconferir se o formato mudar.
- **Prompts** deste script são adaptados dos que já existem em `claude_client.py`
  (mesmo espírito, versões mais enxutas) — não há uma fonte única hoje porque estas
  14 funções ainda não foram migradas pra `ia/funcoes/*.py`. Quando forem, vale
  conferir se o prompt usado aqui ainda bate com o de produção.
