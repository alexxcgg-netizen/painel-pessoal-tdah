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
