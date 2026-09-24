### Fase 7B - faixa C2 (polimento visual de V0a-V3 e P1b)

Revisão final do que V0a, V0b, V0c, V0d, V1, V2, V3 e P1b entregaram. Não muda cor,
fonte nem animação (decisão do Alex). Só acabamento, profundidade sutil e bugs.

- **Bugs corrigidos**
  - As abas Painel e Assistente apareciam embaixo de todas as outras. O `display:flex`
    por id vencia o `[hidden]`; agora a regra usa `#tab-x:not([hidden])` e há um teste.
  - O card "Custo de IA" estava incluído duas vezes no Painel e o segundo ficava em
    "Carregando...".
  - Bottom-sheet: ao abrir, o sheet sobe pro `<body>` e, ao fechar, volta pro lugar de
    origem. Antes ficava preso dentro da aba, com a barra de abas por cima. Reabrir no meio
    da animação de fechar não esconde mais o sheet. O CSS provisório da V3, que pintava a
    moldura da tela inteira em 4 arquivos, saiu.
  - Card, campo, chip, botão, lista, seção e selo passam a respeitar o `[hidden]`. Antes
    campos escondidos continuavam na tela, como "Quantas vezes por semana" e os 7 dias no
    sheet de hábito.
  - A lista de Avisos não quebra mais com um item nulo (achado no fuzz). O tile "gasto hoje"
    sai do shimmer quando o resumo falha.
- **Adicionar vira `.btn-adicionar` + bottom-sheet** em Datas importantes, Medicamentos,
  Esperando resposta e Diário de decisão (o "Registrar" era um botão nativo branco). Os
  sheets ganham título e o botão final diz o que faz ("Salvar remédio"). O "+" que aparecia
  duplicado nos botões de adicionar saiu.
- **Anel de foco visível** (`--anel-foco`) em botão, chip, campo, card, linha de lista, aba
  da barra, ajuda "!", checkbox e em todo alvo focável das abas da C2. A troca do global
  do `style.css` ficou com o integrador.
- **Toque de 44px** em tudo nas abas da C2 (51 alvos menores → 0). O visual continua
  compacto: um `::after` invisível amplia a área nas ações de lista e no "!".
- **Checkbox do app** com a aparência do contrato: superfície em camada, borda fina e marca
  de traço. A regra usa `:where()`, então o tamanho definido por cada seção continua valendo.
- **Tarefas/Vida**: os rótulos viraram `.chip--compacto`, com a cor de alerta de volta em
  "atrasada"/"travada" e no status do projeto. Energia virou chips com `aria-pressed`. O card
  de projeto ocupa a linha toda e o hábito empilha título, ações e semana.
- **Assistente**: o item da Caixa/Regras virou bloco interno (sem card dentro de card) e o
  rótulo de tipo ficou pequeno. Os Avisos (50 tipos, ~8000px) ficam numa seção recolhível
  com "N de M ligados". O "Ver tudo" ganhou contraste (2,2:1 → ~8:1). A cor nova `#ffc45c`
  voltou pra paleta (`--cor-bancos`). O `.nav-selo` ficou num lugar só.
- **Cards de assinatura, parcela e resumo recorrente** seguem o contrato da N1
  (`docs/contrato-assinaturas.md`), e os nomes provisórios da V1 continuam aceitos.
- **Componentes na receita do MASTER**: realce de topo no card e no `.btn-adicionar`,
  `.btn-perigo` com texto `--danger` sobre `--danger-bg`, véu de hover na linha, rótulo de
  campo sem maiúsculas e sheet com fundo opaco.
- Testes: `tests/test_fase7_c2_visual.py` (novo), `tests/js/c2_assistente.test.js` (novo),
  `tests/js/cards_tipos_fase7.test.js` (reescrito) e `tests/js/bottom_sheet.test.js`
  (portal e reabertura rápida). Fuzz de UI com 74 cenários, sem erro de console e sem
  exceção (`scripts/ralph-c2-visual/fuzz.py`).
