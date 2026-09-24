# Aprendizados - faixa A9 (visao: nota fiscal e cotacao em PDF)

## PDF direto no GPT-6 Luna (item 2 do briefing)

Confirmado lendo o SDK `openai` 3.19.2 instalado (`.venv/lib/python3.11/site-packages/openai/`),
NAO na documentacao publica (offline aqui), com data de hoje (2026-09-24):

- `types/chat/chat_completion_content_part_param.py` define, pra Chat Completions
  (`client.chat.completions.create`, o mesmo endpoint que `ia/adapters/openai.py` usa),
  um content part `File` com `type: "file"` e `file: {file_data, file_id, filename}` -
  `file_data`: "The base64 encoded file data, used when passing the file to the model
  as a string." Faz parte do `Union` de `ChatCompletionContentPartParam` (junto com
  text/image/input_audio), ou seja, GPT-6 Luna aceita arquivo (PDF incluso) DIRETO
  nessa API, sem precisar converter pagina em imagem.
- `types/responses/response_input_file_param.py` (API de Responses, nao usada aqui)
  tem o equivalente `input_file`/`file_data`/`file_url`, com um comentario explicito:
  "for GPT-5.6 and later models, `auto` uses high-quality rendering" - confirma que
  modelos da familia GPT-5.6+ (GPT-6 Luna incluso) processam arquivo/PDF nativamente,
  nao so imagem.
- **Nao confirmado** (e nao dava pra confirmar so lendo o SDK, sem chamada real - e
  chamada real e proibida nos testes desta faixa): se `file_data` no formato "file"
  da Chat Completions precisa do prefixo `data:application/pdf;base64,...` (igual o
  `image_url` que `ia/adapters/openai.py` ja monta) ou aceita base64 puro. Assumi o
  prefixo por paridade com `image_url` (mesmo padrao "data URI" usado no resto do SDK,
  ver `types/realtime/realtime_conversation_item_user_message*.py`, que documenta
  exatamente esse formato pra imagem). **Fica pro proximo passo (quando `ativo` virar
  true de verdade) reconfirmar isso com uma chamada real, ou perguntar direto pro
  Alex/doc oficial.**
- Conclusao pratica: **nao precisei converter PDF em imagem** (e portanto nao precisei
  de lib nova tipo PyMuPDF/pdf2image/poppler - `pip list` do `.venv` so tem `pillow`,
  que nao rasteriza PDF sozinho). Nada foi instalado no `.venv` compartilhado.

## Anthropic adapter NAO converte o formato de imagem/documento (avisado no briefing)

Confirmado lendo `ia/adapters/anthropic.py` (faixa A2, nao editei): `AdapterAnthropic.chamar()`
faz `kwargs["messages"] = mensagens` e repassa direto pro SDK, sem nenhuma conversao de
content parts (ao contrario do adapter OpenAI, que documenta e CONVERTE
`{"type":"image","data_b64":...,"mime":...}` pro formato dele).

Resolvido do meu lado (sem editar nenhum adapter): como as duas configs desta faixa nascem
com `ativo: false`, a UNICA tentativa que roda hoje e sempre `anthropic/claude-sonnet-5` -
entao `ia/funcoes/visao.py` monta as mensagens no formato NATIVO da Anthropic
(`{"type": "document"/"image", "source": {"type": "base64", "media_type": ..., "data": ...}}`),
igual o codigo antigo ja fazia. **Isso significa que so trocar `ativo: true` no JSON NAO
basta pra estas duas funcoes** (ao contrario das funcoes so-texto, onde a migracao e mesmo
so o flag) - quando alguem for migrar de verdade pro GPT-6 Luna, este arquivo precisa
tambem passar a montar as mensagens no formato de `ia/adapters/openai.py`
(`image_url`/`file`, ver secao acima sobre PDF) - ou um branch por provedor dentro da
propria `ia/funcoes/visao.py`, sem tocar em nenhum adapter.

## Client compartilhado do adapter Anthropic (compat com testes antigos)

`ia.core._obter_adapter("anthropic")`, sem fabrica registrada, instancia
`AdapterAnthropic()` que cria um `anthropic.Anthropic()` NOVO - uma instancia diferente
de `ia.legado.client` (usada por `claude_client.py` e por `tests/test_claude_client.py`,
que fazem `patch.object(claude_client.client.messages, "create", ...)`). Migrar direto
pra `ia.core.chamar_ia` sem mais nada faria aqueles testes tentarem rede de verdade (e
falhar, ja que nao mockam a instancia certa).

Resolvido com a API publica `ia.core.registrar_adapter(provedor, fabrica)` (pensada
exatamente pra isso, ver docstring de `ia/core.py`): `ia/funcoes/visao.py` registra,
a cada chamada, `AdapterAnthropic(client=ia.legado.client)` - o mesmo client que os
testes antigos ja mockavam. Nao editei `ia/core.py` nem `ia/adapters/anthropic.py`.
Reafirmar a cada chamada (nao so na importacao) porque `core.registrar_adapter(prov,
None)` e o padrao de limpeza usado por outros testes (`tests/test_ia_core.py`) - rodando
a suite inteira, o tearDown de outro teste pode apagar o registro entre um teste e outro.

**Consequencia pra quem for escrever teste novo pra estas 2 funcoes**: nao adianta
`core.registrar_adapter("anthropic", dublê)` no setUp (a propria funcao sob teste
sobrescreve antes de cada chamada) - tem que mockar `ia.legado.client.messages.create`
direto, igual `tests/test_claude_client.py` sempre fez. `tests/test_fase7_a9_extracao_visao.py`
documenta isso no topo. O provedor "openai" nao tem esse problema (esta faixa nunca
mexe no adapter openai), `core.registrar_adapter("openai", dublê)` funciona normal.

## Teto de IA precisa de banco migrado (achado rodando os testes, nao no briefing)

`ia.core.chamar_ia` consulta `ia.teto.teto_permite` antes de qualquer chamada -
`ia/teto.py` (faixa A4) usa `db.get_db()`/`db.obter_teto_mensal_ia` de verdade (tabela
`configuracoes`). `tests/test_claude_client.py` (anterior a esta migracao) nunca tocava
`ia.core`/banco nenhum - so agora, com a migracao, essas 2 classes de teste passaram a
depender de um banco com schema aplicado (`db.init_db()`). **Isso so funciona porque
`tests/test_app.py` (que o proprio grep `extrair_nota_fiscal\|cotacao_pdf` tambem
encontra) troca `db.DB_PATH` pra um arquivo temporario e importa `app.py` (que chama
`init_db()` na importacao) ANTES de `test_claude_client.py` rodar, na mesma sessao do
pytest** - confirmado rodando os dois juntos (`scripts/testes.sh tests/test_app.py
tests/test_claude_client.py` -> os 30 testes de `test_claude_client.py` passam) e
tambem rodando so `tests/test_claude_client.py` sozinho (falha por banco sem schema,
`sqlite3.OperationalError: no such table: configuracoes` -> `ia.teto._teto_permite`
bloqueia por seguranca "na duvida"). Nao editei `db.py`/`ia/teto.py`/`test_claude_client.py`
- e um acoplamento involuntario entre arquivos de faixas diferentes, registrado aqui e
em `progress.txt` pro integrador saber que os dois arquivos de teste precisam continuar
rodando juntos (ou `test_claude_client.py` precisa ganhar seu proprio fixture de banco,
igual `tests/test_ia_teto.py` ja tem, no dia em que alguem quiser rodar so ele isolado).
