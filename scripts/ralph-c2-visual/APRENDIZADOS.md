# C2 (polimento visual): aprendizados

## Armadilhas de CSS que derrubaram telas inteiras
- **`display` por classe ou id vence o `[hidden]`.** A regra do navegador para `[hidden]`
  é a mais fraca que existe: qualquer `.x { display: flex }` do autor ganha dela. Com
  isso, `el.hidden = true` deixou de esconder card, campo e botão, e com `#tab-painel`
  a aba inteira vazava pra baixo das outras. Pra evitar: container de aba usa
  `#tab-x:not([hidden])`, e todo componente que define display ganha
  `.classe[hidden] { display: none }`. `tests/test_fase7_c2_visual.py` cobra as duas coisas.
- **`animation-fill-mode: both` com `transform` deixa um transform aplicado pra sempre.**
  Esse ancestral vira o bloco de contenção de todo `position: fixed` e cria um contexto de
  empilhamento próprio. O sheet ficava preso na aba e a barra de abas (z-index 10 na raiz)
  passava por cima. O integrador trocou pra `backwards` no `style.css`. O `bottom-sheet.js`
  também leva o sheet pro `<body>` enquanto ele está aberto, como defesa. Efeito colateral
  aceito: enquanto o sheet está aberto, o CSS escopado por `#tab-x` não alcança o
  conteúdo dele. Por isso o visual do sheet fica nos componentes (`.campo`, `.btn`,
  `.bottom-sheet-*`) ou em seletores `.bottom-sheet #id`.
- **CSS "provisório" sem escopo vira dívida quando o componente de verdade chega.** A V3
  copiou `.bottom-sheet { background; padding; border }` em 4 arquivos, e isso pintou a
  moldura de tela cheia de todo sheet do app. Fallback de componente precisa de escopo
  (`#meu-sheet`) e tem data pra sair.
- **`.chip` carregado depois do `style.css` apaga a cor semântica de classes antigas**
  (`.item-tag-travada`, `.projeto-status-atrasado`), porque a especificidade é a mesma e
  quem vem depois ganha. Quem reaproveita um componente em cima de uma classe com cor
  própria precisa restaurar a cor com `.antiga.chip`.
- `.form-linha input[type=text]` (0,2,1) vencia `.campo` (0,1,0). Pra ganhar sem
  `!important`: `.form-linha :is(input, select, textarea).campo`, que tem o mesmo peso e
  carrega depois.
- Checkbox com `appearance: none` aceita `::before` e `::after` no Chromium e no WebKit. Com
  `:where(input[type=checkbox])` a especificidade é zero e o tamanho que as seções já
  definem continua valendo. O `::after` de 44px entra só em checkbox solto (fora de
  `<label>`), pra não sobrepor os vizinhos em linhas densas.

## Medição (levantamento.py)
- `box-shadow` com `transition` precisa de ~350ms depois do `focus()` pra mostrar o valor
  final. Ler na hora dá o valor inicial e acusa "sem anel" à toa.
- `:focus-visible` com `focus()` programático só casa se a última interação foi pelo
  teclado. Um `keyboard.press("Shift")` antes resolve.
- Pra contraste, somo a pilha de `background-color` até o `<body>` sobre o `--bg` preto e
  multiplico pela opacidade dos ancestrais. Texto com `background-clip: text` (o shimmer do
  stat-tile) aparece como 1:1, e não é falso positivo: o tile ficava travado no shimmer.

## Fuzz (fuzz.py)
- No Chromium headless sem GPU, o blur de 38px da barra de abas gera quadros longos, e o
  `setTimeout` de 240ms do fechamento do sheet pode atrasar mais de 450ms. Por isso as
  invariantes esperam o estado assentar (até 3s) antes de acusar erro.
- O navegador loga todo 4xx/5xx como "Failed to load resource" no console. Os cenários que
  provocam 500 de propósito filtram só essa linha e continuam pegando erro de verdade do app.
- `page.route("**/api/assistente/**")` com JSON malformado, HTML, lista no lugar de objeto
  e itens com campos lixo achou o único crash da rodada (item `null` na lista de Avisos).

## Processo
- `pgrep -f padrao` casa com o próprio `bash -c` que roda o comando. Pra matar o servidor,
  ancore no início da linha de comando (`^/caminho/python scripts/...`) ou use o id da
  tarefa em segundo plano.
- O Flask guarda os templates em cache: depois de editar HTML é preciso reiniciar o
  servidor de teste. Isso não vale pra estático.
