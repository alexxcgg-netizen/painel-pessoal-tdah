### Fase 7 - faixa V0c (secoes recolhiveis, cards, chips, campos, itens de lista)

- Preenchidos os 5 componentes visuais vazios da Etapa 0 (`static/css/ui/componentes/`):
  `secao.css` (`.secao-recolhivel`, `.secao-cabecalho`, `.chevron`, `.secao-conteudo`),
  `card.css` (`.card`, `.card-titulo`, `.card--destaque`, `.card--compacto`, numeros em
  `--font-numeros`), `chip.css` (`.chip`, `.chip--ativo`, `.chip--compacto`), `campo.css`
  (`.campo` pra input/select/textarea, foco visivel sem o azul padrao do navegador) e
  `lista-item.css` (`.lista`, `.lista-item`, linha divisoria, acoes a direita).
- Tokens novos da V0a (`--raio`, `--raio-sm`, `--espaco-1..6`, `--elevacao-1..3`,
  `--borda-sutil`, `--superficie-2/3`) usados com `var(--x, fallback)` porque a V0a ainda
  nao chegou na integracao quando essa faixa rodou - os fallbacks encadeiam pras variaveis
  de cor/raio que ja existem em `style.css` (`--radius`, `--radius-sm`, `--surface-2/3`,
  `--border`) e caem pra um valor fixo so no ultimo nivel. Zero cor/fonte/animacao nova.
- `static/js/ui/secao-recolhivel.js`: liga sozinho toda `.secao-recolhivel` da pagina no
  carregamento e observa o DOM (`MutationObserver`) pra ligar secoes inseridas depois;
  `ligarSecoesRecolhiveis(raiz)` fica global e e idempotente (chamar de novo na mesma secao
  nao duplica o listener de clique). Estado (`data-aberto`, `aria-expanded` no botao) e
  persistido por `data-secao-id` em `localStorage` (`secaoRecolhivel:<id>`, tudo em
  try/catch - sem `data-secao-id` nao salva, sem `localStorage` disponivel/bloqueado nao
  quebra). Corpo anima com `max-height` medido (`scrollHeight`), respeitando o
  `prefers-reduced-motion` global que ja existe em `style.css`.
- `tests/js/secao_recolhivel.test.js` (18 casos, `node --test`, DOM simulado minimo:
  elemento falso com `classList`/`dataset`/`querySelector(All)`/`addEventListener`):
  abre/fecha por clique, `aria-expanded` acompanha, estado salvo tem prioridade sobre o
  `data-aberto` do HTML ao religar a pagina, chaves de `localStorage` isoladas por secao,
  `ligarUma`/`ligarSecoesRecolhiveis` idempotentes e nunca lancam excecao mesmo sem
  `.secao-conteudo`, sem `localStorage` ou com `localStorage` que lanca (quota
  cheia/privado).
- Ultima historia: verificacao headless (Playwright, 390x844) com uma secao recolhivel +
  card + chips + campo + lista dentro de um container real, banco de teste isolado -
  screenshots fechado/aberto em `scripts/ralph-v0c-secoes/`, zero erro de console.
