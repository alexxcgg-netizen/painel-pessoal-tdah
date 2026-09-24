# Aprendizados - faixa A11 (Teste A/B de IA)

- **`ia.core.chamar_ia` não tem override de modelo** - sempre lê
  `ia/config.d/<funcao>.json` (config fixa por função). Nenhuma das 14 funções
  comparadas aqui tem esse arquivo (não foram migradas pra `ia/core` - ainda
  vivem em `claude_client.py`). Pra testar dois modelos na mesma execução, dá
  pra chamar o adapter direto reaproveitando `ia.core._obter_adapter`/
  `registrar_adapter`/`_chamar_uma_vez`/`_erro_de_rede`/`_teto_permite` (todas
  "privadas" por convenção `_`, mas nada no núcleo impede reuso de outro
  módulo do mesmo pacote) - ver `_chamar_com_override` em `scripts/ab_teste_ia.py`.

- **`ia.core._chamar_uma_vez` exige JSON raiz OBJETO quando recebe `schema`**
  (`elif not isinstance(dados, dict): erro = "JSON precisa ser objeto"`) - não
  aceita lista no topo. Três funções já existentes em `claude_client.py`
  (`break_down_task`, `gerar_mala`, `requebrar_tarefa`) devolvem uma LISTA no
  nível raiz. Se uma faixa futura migrar essas funções pra `ia/core` via
  `chamar_ia` de verdade (não só este script de teste), vai bater nesse mesmo
  limite - ou envolve a lista num objeto (`{"itens": [...]}`, muda o contrato
  do prompt) ou pede pra faixa A1 relaxar o gate. Este script contornou
  passando `schema=None` pro parâmetro de validação de `_chamar_uma_vez` (mas
  mantendo `schema` dentro de `kwargs` pro adapter instruir o modelo) e validando
  o JSON por conta própria depois, com `core._extrair_json`/`core.validar_schema`
  direto (que funcionam com lista ou objeto).

- **`ia/precos.json` tem formato DIFERENTE entre as branches não-mergeadas
  `fase7/a3-adapter-openai` e `fase7/a4-medicao-teto`**: a A3 assumiu
  `{"openai": {"<modelo>": {...}}}` (aninhado por provedor); a A4 na prática
  criou `{"modelos": {"<modelo>": {...}}}` (achatado, todos os provedores
  juntos). Nenhuma reconferiu com a outra ainda (comentário "TODO" no
  adapter da A3 confirma). Quem for integrar A3+A4 vai precisar resolver essa
  divergência antes do custo real funcionar pra OpenAI.

- **Nomes de modelo confirmados em 2026-09-24** (lendo `ia/precos.json` na
  branch `fase7/a4-medicao-teto` e as strings literais nos adapters das
  branches `fase7/a2-adapter-anthropic`/`fase7/a3-adapter-openai`, nenhuma
  mergeada): `claude-sonnet-5`, `claude-haiku-4-5-20251001`,
  `claude-opus-5-5`, `gpt-6-sol`, `gpt-6-luna`, `gemini-3-5-flash-lite`
  ("Sol"/"Luna" = codinomes da OpenAI pra dois modelos GPT-6, não é nome
  nosso - confirmado no docstring de `AdapterOpenAI` na branch A3: "Adapter
  da OpenAI (GPT-6 Luna / GPT-6 Sol)").

- **Adapter OpenAI (A3) não tem convenção de documento/PDF** - só
  `image`/`text` em `_converter_parte_conteudo`. `extrair_item_cotacao_pdf`
  manda um PDF (formato nativo Anthropic, `type: document`) - não dá pra
  comparar Luna nessa função até a A3 ganhar suporte a isso. Documentado e
  tratado explicitamente (`NaoSuportado`/item "pulado"), não escondido.

- **`core.registrar_adapter` + `core._obter_adapter` CACHEIA o adapter por
  provedor** (`_CACHE_ADAPTERS.setdefault`) - registrar uma fábrica nova
  depois que o provedor já foi resolvido uma vez não tem efeito até
  `core.limpar_cache()`. Pra simular respostas diferentes por fixture em
  `--dry-run` sem ficar limpando cache toda hora, o jeito mais simples é um
  adapter-dublê ÚNICO por provedor com uma fila (`AdapterDubleAB.enfileirar`),
  igual o `AdapterDuble` que `tests/test_ia_core.py` (faixa A1) já usa -
  reaproveitei o mesmo padrão em vez de inventar outro.

- **Um `dict`/`list` construído em tempo de IMPORTAÇÃO do módulo não vê
  mudança de env var feita depois** (ex: `os.environ["GEMINI_API_KEY"] = ...`
  num teste, setado DEPOIS que o módulo já foi importado). `FUNCOES` é
  montado uma vez só na importação - qualquer coisa que dependa de env var
  pra decidir a lista de candidatos por função precisa ser recalculada em
  tempo de EXECUÇÃO (`candidatos_efetivos()`), nunca guardada direto no
  dicionário estático. Bug real que os próprios testes pegaram
  (`test_gemini_so_entra_com_env_var` falhou antes da correção).
