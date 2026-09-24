### Fase 7 - faixa V0d (bottom sheet + barra de navegação)

- **`static/js/ui/bottom-sheet.js`**: API global `abrirBottomSheet(elOuId)` /
  `fecharBottomSheet(elOuId)`. O autor de uma seção só escreve
  `<div class="bottom-sheet" hidden>…</div>` (contrato do `docs/agentes/fase7-visual.md`);
  na primeira abertura o componente monta sozinho `.bottom-sheet-fundo` (fundo escurecido,
  clique fora fecha) e `.bottom-sheet-painel` (o painel que sobe, com a `.bottom-sheet-alça`),
  movendo o conteúdo original pra dentro. Fecha com ESC, clique no fundo, ou arrastando a
  alça pra baixo (best-effort via Pointer Events). Foco fica preso dentro do painel
  (Tab/Shift+Tab não escapam) e volta pro elemento que abriu o sheet ao fechar; `role="dialog"`
  + `aria-modal="true"`; rolagem interna; `env(safe-area-inset-bottom)`; respeita
  `prefers-reduced-motion` (fecha/abre sem a transição). Trava o scroll do `body` enquanto
  aberto. Emite `bottomsheet:fechado` (bubbles, `detail.id`) ao fechar por qualquer motivo.
  Um `<form data-fecha-ao-enviar>` dentro do sheet fecha sozinho quando o próprio handler de
  sucesso dispara `bottomsheet:sucesso` (bubbles) — contrato pras próximas faixas que forem
  colocar formulários dentro de um sheet.
- **`static/css/ui/componentes/bottom-sheet.css`**: segue a receita do `docs/MASTER.md`
  (V0a) — `--superficie-2` + `--realce-superficie`, `border-radius: var(--raio-lg)` nos
  cantos de cima, borda de cima `--borda-forte`, `--elevacao-3`, alça 36×4px, padding
  `--espaço-4` + `env(safe-area-inset-bottom)`, véu `--veu-fundo` em `--camada-veu`, painel
  em `--camada-sheet`, entra com `--transicao-lenta`. Nenhuma cor/fonte/animação nova.
- **`static/css/ui/componentes/navegacao.css`**: acabamento por cima do `#tabbar` que já
  existe em `style.css` (vidro/blur/glow — não duplicado aqui): área de toque garantida de
  `--toque-min` (44px), indicador de aba ativa refinado (pontinho, além do "cartão aceso"
  que já existia), e o selo de contagem `.nav-selo` (a faixa P1b vai colocar o HTML na aba
  Hoje — contrato documentado no topo do arquivo e no `progress.txt`). Ícones de
  `templates/navegacao.html` já são SVG de traço em todas as 7 abas, não emoji — nada pra
  trocar.
- **`tests/js/bottom_sheet.test.js`** (23 testes, `node --test`): abrir/fechar (por id e por
  elemento, idempotente, sem quebrar com id inexistente), ESC, foco preso (Tab e Shift+Tab)
  e devolvido ao elemento de origem, evento `bottomsheet:fechado` (inclusive com bolha até o
  `document`), `data-fecha-ao-enviar` + `bottomsheet:sucesso`, scroll do body, e os helpers
  puros `elementosFocaveis`/`ehFocavel`. Sem jsdom (o projeto não tem `package.json`/
  `node_modules` de propósito) — DOM mínimo simulado no próprio arquivo de teste, sombrando
  `document`/`CustomEvent` antes do `require()` do módulo.
- **Verificação Playwright** (`scripts/ralph-v0d-sheet-nav/servidor.py` + `verificar.py`,
  390×844, banco temporário): injeta um `.bottom-sheet` de teste (nenhuma seção real usa a
  API ainda) e confere abrir/ESC/foco/evento/scroll-lock de ponta a ponta num navegador de
  verdade, mais `.tab-btn` com 44px de toque mínimo. 0 erro de console (fora as falhas de
  ambiente já conhecidas da Fase 7: Google Fonts sem CA válido no sandbox e
  `/api/summary/today` 502 com chave de IA dublê). Screenshots não versionados.
