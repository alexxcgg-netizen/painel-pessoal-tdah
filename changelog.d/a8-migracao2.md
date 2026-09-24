### Fase 7 - Faixa A8 (Migração 2: planejamento)

- **`ia/funcoes/planejamento.py`**: as 5 funções de planejamento
  (`break_down_task`, `requebrar_tarefa`, `gerar_mala`, `resumir_link`,
  `plano_do_dia`) passam a chamar `ia.core.chamar_ia(...)` em vez do SDK
  Anthropic direto. Assinatura e retorno (tupla `(resultado, usage)`)
  continuam idênticos - `claude_client.py` não mudou. `break_down_task`,
  `requebrar_tarefa` e `gerar_mala` ganharam schema JSON (`{"passos": [...]}`
  / `{"itens": [...]}`); `resumir_link` e `plano_do_dia` continuam texto
  livre. Prompt fixo de cada função vai em `contexto_fixo` (prefixo
  estável, pronto pro cache de prompt do provedor); os dados que mudam a
  cada chamada (título da tarefa, destino, texto da página...) ficam só na
  mensagem.
- **`resumir_link` trunca a entrada**: o texto da página é cortado em até
  12.000 caracteres antes de mandar pro modelo, preferindo parar no fim de
  uma frase perto do limite.
- **`ia/config.d/{gerar_mala,resumir_link,break_down_task,requebrar_tarefa,plano_do_dia}.json`
  (novos)**: `ativo: false` em todos (`modelo_atual` = o modelo que cada
  função já usa hoje: Haiku 4.5 pras duas primeiras, Sonnet 5 pras outras
  3), `alvo` = openai `gpt-6-luna` esforço médio, fallback conforme cada
  função (Haiku 4.5 pras duas primeiras, openai `gpt-6-sol` esforço médio
  pras outras 3).
- **Teto mensal de IA passa a valer nas 5 rotas de graça**: nenhuma das 5
  rotas que usam estas funções checava o teto mensal antes (só a rota de
  captura checava); com `chamar_ia` isso passa a valer automaticamente,
  porque o teto é checado dentro do próprio núcleo antes de qualquer
  chamada de IA. Resolve, pra `gerar_mala` (e as outras 4), a pendência da
  Fase 6 sobre funcionalidade fora do teto (o PDF de cotação é outra
  função, faixa A9, fora do escopo desta faixa).
- **`tests/test_fase7_a8_planejamento.py` (novo)**: 35 testes - retorno
  idêntico via dublê de `ia.core.chamar_ia`, argumentos passados
  (função/contexto_fixo/schema/mensagens), schema, truncamento de
  `resumir_link`, formato normalizado das 5 configs, e uma suíte de
  integração fim-a-fim com `ia/core.py` real + adapter falso (fallback,
  teto bloqueando sem chamar nenhum adapter, JSON fora do schema).
