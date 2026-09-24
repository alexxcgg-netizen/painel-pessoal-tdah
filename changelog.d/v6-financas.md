### Fase 7 - faixa v6-financas (acabamento visual: Gastos, Bancos, Construtora)

- **Acabamento moderno com profundidade** (docs/agentes/fase7-visual.md), sem
  mexer em cor/fonte/animação, nas seções `gastos/gastos`, `gastos/metas`,
  `bancos/bancos`, `bancos/ofx`, `construtora/construtora`,
  `construtora/contas-a-pagar` e `vida/contas-pessoais` - radius/borda
  fina/elevação sutil via `var(--token, fallback)` (V0a ainda não estava na
  integração; o fallback some sozinho quando ela definir os tokens de
  verdade). Categoria do gasto e tipo da conta bancária (conta/cartão) agora
  são chips. Botão de adicionar de `vida/contas-pessoais` virou
  `.btn-adicionar` + `.bottom-sheet`.
- **Construtora mostra só gastos, entradas e tempo até a próxima conta a
  pagar** (decisão do Alex, `docs/contrato-api-construtora.md`, faixa A10) -
  lucro líquido/margem pararam de aparecer na tela.
- **Seção nova "Assinaturas e parcelas" (`gastos/assinaturas`), junto do
  cartão**: consome `/api/financas/*` (faixa N1 - assinaturas e compras
  parceladas declaradas a mão, ainda não integradas quando esta faixa foi
  escrita, ver `scripts/ralph-v6-financas/APRENDIZADOS.md`). Lista de
  próximas cobranças ("em N dias"), assinaturas ativas, parcelas em
  andamento, total mensal comprometido e um mini gráfico (SVG próprio,
  `static/js/charts.js` - sem Chart.js, ver aprendizados) do impacto no
  limite do cartão nos próximos 6 meses. Formulário de nova
  assinatura/parcela em 2 bottom sheets. Estados vazio/erro cobertos.
- Achado real corrigido: `templates/secoes/vida/ainda-usa.html` já usava
  `id="assinaturas-box"` (recorrência detectada por histórico, não tem
  relação com a assinatura declarada da faixa N1) - a seção nova nasceu com
  `id="assinaturas-financas-box"` pra não colidir.
