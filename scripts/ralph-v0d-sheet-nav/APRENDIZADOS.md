# Aprendizados - faixa V0d (bottom sheet + barra de navegacao)

- **`elementosFocaveis` precisa ser pre-ordem (DFS visitando o pai antes dos irmaos
  seguintes), nao BFS por nivel.** Primeira versao usava uma fila (`shift`/`push`), que
  processa por nivel da arvore - um `<button>` irmao de um `<label>` aparecia ANTES do
  `<input>` que esta dentro do `<label>`, mesmo o input vindo primeiro no HTML/ordem real de
  Tab do navegador (`<label>Campo <input></label><button>`). So apareceu no Playwright de
  verdade (o teste Node com DOM minimo nao tinha um caso com elemento focavel aninhado
  dentro de um elemento nao-focavel que tem irmao focavel depois) - trocado pra uma
  recursao simples (visita filho, e so DEPOIS entra nos netos) e cobri o caso no teste
  Node tambem (`elementosFocaveis encontra em qualquer profundidade, na ordem do DOM`).
  Se outra faixa reusar esse padrao de armadilha de foco em outro componente, vale copiar
  a recursao, nao a fila.

- **`node --test` sem jsdom da pra simular DOM o suficiente pra testar um componente que
  MEXE em DOM de verdade** (nao so funcoes puras como os outros testes de `tests/js/`).
  O truque: sombrar `globalThis.document`/`globalThis.CustomEvent` ANTES do primeiro
  `require()` do modulo (e limpar `require.cache` a cada teste pra reiniciar o estado
  interno dele), com uma classe `FakeElement` minima que so implementa o que o componente
  realmente usa (nada de querySelectorAll com seletor CSS completo - bottom-sheet.js
  deliberadamente varre a arvore na mao em vez de usar seletor composto, exatamente pra
  isso ficar simples). Pegadinha: o `CustomEvent` NATIVO do Node (existe desde a v18) tem
  `.target` so-leitura, que quebra um `dispatchEvent` com bolha manual (`evento.target =
  ...`) - precisa sombrar `CustomEvent` tambem, sempre, mesmo ele "ja existindo".

- **`className = "x"` e `classList.add("x")` precisam apontar pro MESMO conjunto** no DOM
  falso - bottom-sheet.js usa os dois (cria elemento com `.className`, depois manipula com
  `.classList`), igual o DOM real faz (os dois ficam sincronizados). Um `FakeElement` que
  trata `className` como uma string solta, sem ligar no `Set` do `classList`, faz
  `closest(".bottom-sheet-painel")` falhar silenciosamente sem nenhum erro (so o teste
  falha, sem pista do motivo) - `Object.defineProperty` com getter/setter resolve.

- **`Node.requestAnimationFrame`/`PointerEvent`/`matchMedia` nao existem por padrao** -
  usados isso a favor: bottom-sheet.js cai pro caminho sincrono/sem-animacao quando
  `raiz.requestAnimationFrame`/`raiz.matchMedia` sao `undefined` (o mesmo caminho de
  `prefers-reduced-motion`), entao os testes Node nao precisam de fake timers nem mock de
  RAF pra passar de forma deterministica - e ainda cobre o caso real de reduced-motion de
  graca.

- **Backdrop de bottom sheet sem HTML extra**: o contrato de autoria pede so
  `<div class="bottom-sheet" hidden>...</div>` (sem wrapper pro fundo/painel). Resolvido
  fazendo o JS montar `.bottom-sheet-fundo` + `.bottom-sheet-painel` sozinho na 1a abertura,
  movendo o conteudo original pra dentro do painel. Efeito colateral bom: clique no fundo
  fecha (`evento.target` bate exatamente no elemento fundo, nunca borbulha do conteudo) sem
  nenhuma logica de "clicou fora do retangulo do painel" por coordenada.
