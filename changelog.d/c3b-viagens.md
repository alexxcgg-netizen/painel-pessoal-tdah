### Fase 7 - faixa C3b (polimento visual de Viagens, Lugares, Cotações e Aviação)

Sem cor, fonte ou animação nova (decisão do Alex): só forma, profundidade e toque.

- **Seções recolhíveis** (`.secao-recolhivel`, V0c, começam abertas e lembram o
  estado): Vida > Viagens e Lugares, Construtora > Cotações, Aviação > Próximos voos
  e METAR/TAF. O card de viagem do chat reabre a seção sozinho se ela estiver fechada.
- **Bottom-sheet de verdade (V0d)** nos 4 formulários: viagem, lugar, cotação e,
  novo, **Registrar voo**, que saiu do meio da aba (formulário longo sempre aberto) e
  virou `.btn.btn-adicionar` + sheet. Os templates pararam de escrever
  `.bottom-sheet-painel` à mão, então o componente monta o fundo escurecido, a alça e o
  toque fora. O CSS local por ID que a V5-extra deixou foi removido. Cada sheet tem
  título, rótulo acima do campo e botão final "Salvar viagem/lugar/cotação/voo".
- **Correção do sheet preso na aba:** o `.tab-content` anima com `fill-mode: both` e
  deixa um `transform`, que virava o bloco de contenção do `position: fixed`. O
  sheet cobria a aba inteira e o painel abria longe da borda de baixo. Contorno local:
  os sheets da faixa vão pro `<body>` na primeira abertura. A correção global fica com
  o integrador (ver progress).
- **Toque de 44px e nada nativo:** "Salvar" do número do voo e "Ver no mapa" (cinza
  nativo, 21px) viraram `.btn.btn-secundario`. O link "Windy" deixou de usar o azul
  padrão do navegador (contraste 1,9:1) e ficou igual às outras ações. O "×" de apagar
  fornecedor virou ícone SVG de traço com 44px. Ações das listas, dicas "!", botões
  "ouvir" e zoom do Leaflet chegam a 44px, com área invisível quando o visual é menor.
- **Hierarquia:** viagens, lugares, cotações e voos viram blocos internos dentro do
  card da seção (sem card dentro de card). Fornecedores viram lista com divisor, valor
  R$ em mono tabular e o menor preço marcado por barra fina e peso.
- **Mapa do Leaflet abria com 26px** (bug antigo de cascata: o próprio `.lugar-mapa`
  vira `.leaflet-container` e herdava `height: 100%`). Agora abre com 180px. O SRI e o
  popup por `textContent` continuam iguais.
- **Robustez:** as listas ignoram respostas fora do formato (500, JSON inválido,
  objeto no lugar de lista). O fornecedor com valor negativo/infinito é recusado na
  tela, "volta antes da ida" é bloqueada, e o voo não duplica com toque repetido em
  Salvar.
- Testes: `tests/test_fase7_c3b_viagens.py` (7 guardas de estrutura). Os scripts de
  auditoria, fuzz (71 cenários) e servidor de banco sintético ficam em
  `scripts/ralph-c3b-viagens/`.
