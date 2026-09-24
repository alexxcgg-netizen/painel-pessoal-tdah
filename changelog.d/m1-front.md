### Fase 7 M1 - faixa m1-front (pendências da C2 em style.css e cards.js)

Fecha três pendências que a C2 deixou pro integrador em arquivos sem dono. Não muda cor,
cor de destaque, fonte nem animação (decisão do Alex).

- **Foco global visível no preto.** O `:focus-visible` do `static/css/style.css` usava um
  anel de `--accent-2` a 45% que quase sumia no fundo preto. Agora usa `box-shadow:
  var(--anel-foco)`, o mesmo token dos componentes da Fase 7 (`static/css/ui/tokens.css`).
  Ganha `outline: 2px solid transparent`, que só aparece no modo de alto contraste do
  sistema, onde o `box-shadow` é descartado.
- **Rede de segurança do `[hidden]`.** `[hidden] { display: none !important; }` logo depois
  do `:root` no `style.css`. Qualquer `display: flex` por classe ou id vencia o atributo
  `hidden` e deixava o elemento na tela. As guardas por componente continuam valendo.
- **Desfazer de assinatura e compra parcelada.** O botão chamava `/api/desfazer/<token>` e
  recebia 404. Agora os cards `assinatura` e `compra_parcelada` usam
  `POST /api/financas/desfazer/<token>`, a rota própria da N1 (`rotas/n1_financas.py`,
  `docs/contrato-assinaturas.md`). A escolha da URL virou a função pura
  `Cards.urlDesfazer(tipoCard, token)` em `static/js/cards.js`. Os outros tipos seguem na
  rota genérica.
- **Testes.** `tests/test_fase7_m1_front.py` confere as duas regras do `style.css`, e
  `tests/js/m1_cards_desfazer.test.js` confere a escolha da URL, com casos de borda e o card
  renderizado. A verificação no Playwright em 390x844 cobre foco por Tab, abrir e fechar o
  bottom-sheet, o clique no Desfazer com a rota interceptada e 0 erros de console.

#### Rodada 2 - cinco correções pequenas de UI (pendências anotadas pela C3a)

Continua sem mexer em cor, cor de destaque, fonte ou animação.

- **Bottom sheet reaberto rápido.** `static/js/ui/bottom-sheet.js` guarda o id do
  `setTimeout(finalizar, 240)` de cada sheet e o cancela ao reabrir (e ao fechar de novo).
  Antes, abrir, fechar, reabrir e fechar dentro da janela deixava o timer antigo vivo: ele
  finalizava o fechamento novo antes da hora, devolvia o foco e disparava
  `bottomsheet:fechado` duas vezes. Numa rajada de 20 abre/fecha/reabre no navegador,
  eram 12 fechamentos indevidos. Agora são 0.
- **Contraste do placeholder.** `static/css/ui/componentes/campo.css`: o fundo do `.campo`
  (normal, com foco e dentro de `.form-linha`, que é o caso de todo sheet) passa a ser
  `--superficie-1`. O placeholder em `--text-faint` sobe de 4,3:1 para 4,82:1, medido com as
  cores computadas no Playwright. Não entra cor nova, e o foco continua visível pela borda
  forte e pelo `--anel-foco`. É o mesmo desvio do MASTER que a C3a já tinha feito no campo
  inline da aba Vida.
- **Comentário que engolia `.garantia-chip`.** No `static/css/style.css`, o trecho
  `.limite-cartao-*/` fechava o comentário antes da hora e a regra virava parte de um seletor
  inválido. Agora está escrito `.limite-cartao-* /`. O `text-transform: uppercase` dessa
  regra, que nunca chegou a valer, foi removido para o chip não ficar em caixa-alta. A
  duplicata da C3a em `secoes/vida/garantia.css` continua lá.
- **Área de toque da dica "!".** Saiu o `::after` local com `inset: -12px` de
  `secoes/vida/viagens.css` e `lugares.css`. Somado ao `::after` do componente
  (`ui/componentes/secao.css`, 44px centrado), ele deslocava a área de toque para o canto. O
  hit-test em ±20px do centro agora não tem ponto morto.
- **Seção recolhida fora do Tab.** `static/js/ui/secao-recolhivel.js` põe `inert` no
  `.secao-conteudo` quando a seção recolhe, inclusive no estado inicial e no estado vindo do
  localStorage, e tira ao abrir. Se o foco estava dentro, ele volta para o cabeçalho. O
  `secao.css` não mudou, porque `visibility: hidden` exigiria mexer na transição.
- **Testes.** Há 2 testes novos em `tests/js/bottom_sheet.test.js` e 5 em
  `tests/js/secao_recolhivel.test.js` (JS: 226/226). `scripts/ralph-m1-front/verificar_r2.py`
  roda no Playwright em 390x844, na porta 5141, com a trava de rede da C3a. Ele cobre
  contraste, CSSOM do chip, hit-test da dica, rajada de sheet e Tab em seção recolhida, com
  0 erros de console e 0 saídas de rede.
