# MASTER: design system do painel (Fase 7B)

Guia que as faixas **V0b a V6** (e a P1b) seguem ao reformar o visual. Ele não traz cor
nova, fonte nova nem animação nova. A identidade atual fica como está, e o que muda é a
**forma** (raio, espaço, borda) e a **profundidade** (camadas, elevação).

- Tokens: `static/css/ui/tokens.css` (faixa V0a). Só variáveis no `:root`, derivadas do `style.css`.
- Ordem de precedência quando dois textos discordam: `docs/agentes/fase7-visual.md` (decisão do
  Alex) > este MASTER > o que o `style.css` faz hoje.
- Onde cada seção mora: `docs/agentes/mapa-frontend.md`.

---

## 1. Princípios

1. **Sério, tecnológico, refinado.** A referência é o Néctar: pouca cor, muito contraste de
   hierarquia, detalhe fino. Nada de "Windows 1990", ou seja, botão cinza nativo, borda
   chanfrada, caixa sem respiro ou azul padrão do navegador.
2. **Profundidade por camadas, não por sombra.** A superfície fica mais clara quanto mais perto do
   dedo: fundo preto, depois `--superficie-2` (card) e `--superficie-3` (algo dentro do card).
   O contorno vem da **borda fina de 1px**. A sombra só sugere altura e nunca é uma mancha cinza grande.
3. **A cor é da aba, não do componente.** Cada aba já tem a sua (`--glass-tint`, `--secao-cor`).
   O componente fica neutro e usa a cor da aba só em borda fina, ícone, indicador ativo ou
   número de destaque. Preenchimento grande de cor usa sempre a versão `-fill` (escurecida).
4. **Hierarquia por peso e tamanho, não por caixa.** Nem tudo precisa virar card. Uma lista dentro
   de um card é linha com divisor, não card dentro de card dentro de card.
5. **Uma coisa em destaque por tela.** Só o card principal da seção ganha `--elevacao-2`. O resto
   fica em `--elevacao-1` ou plano.
6. **Movimento responde ao toque.** Use as durações e curvas que já existem (`--transicao-*`).
   Nenhuma animação decorativa nova. Com `prefers-reduced-motion`, os tokens de duração zeram sozinhos.
7. **Dá pra usar com uma mão e sem óculos:** alvo de 44px ou mais, foco visível, contraste de
   texto de 4.5:1 no mínimo e cor sempre acompanhada de ícone ou texto.

---

## 2. Paleta EXISTENTE (documentada, não nova)

Tudo abaixo já está no `:root` do `static/css/style.css` (linhas 1 a 217). **Não crie cor.** Se
faltar um tom, derive com `color-mix()` a partir destas variáveis e explique no comentário.

| Papel | Variável | Valor |
|---|---|---|
| Fundo da página | `--bg` | `#000000` (preto puro, com aurora e grão por cima) |
| Superfície 1 (seção) | `--surface` | `#121212` |
| Superfície 2 (card) | `--surface-2` | `#181818` |
| Superfície 3 (aninhado) | `--surface-3` | `#1e1e1e` |
| Borda sutil | `--border` | `rgba(218,226,243,.09)` |
| Borda forte | `--border-strong` | `rgba(218,226,243,.18)` |
| Texto | `--text` | `#eceef3` |
| Texto secundário | `--text-muted` | `#a7afbc` |
| Texto terciário, dica | `--text-faint` | `#788292` |
| Marca (neutra, grafite) | `--accent` / `--accent-fill` | `#45454a` / 30% em preto |
| Marca 2 | `--accent-2` / `--accent-2-fill` | `#08080a` |
| Texto sobre marca | `--accent-text` | `#f4eeff` |
| Fundo suave da marca | `--accent-soft-bg` | `--accent` a 16% |
| Aba Hoje | `--cor-hoje` | `= --accent` |
| Aba Painel e Vida | `--cor-painel` | `#41aa75` (esmeralda) |
| Aba Tarefas | `--cor-tarefas` | `#5246d8` |
| Aba Gastos | `--cor-financeiro` | `#04759a` |
| Aba Bancos | `--cor-bancos` | `#a27c2f` |
| Aba Construtora | `--cor-construtora` | `#aa320e` (terracota, **não** é erro) |
| Aba Aviação | `--cor-aviacao` | `#3d8cfa` |
| Erro (só erro) | `--danger` / `--danger-bg` | `#ff5c72` / 14% |

- Toda `--cor-X` tem uma `--cor-X-fill` (a mesma cor misturada a 30% com preto). Use a viva em
  texto, ícone e borda fina, e a `-fill` em preenchimento grande.
- Borda e brilho tingidos pela aba: use `var(--glass-border)` e `var(--glass-shadow)`, que cada
  `#tab-X` já redeclara (ver a pegadinha na seção 10).
- Não existe tema claro. O `color-scheme: dark light` do `style.css` não vem acompanhado de
  paleta clara, e esta fase **não** cria uma.

## 3. Tipografia EXISTENTE

| Papel | Variável (tokens) | Família |
|---|---|---|
| Título | `--fonte-titulo` = `--font-display` | Sora 600 a 800 |
| Corpo | `--fonte-texto` = `--font-body` | Sora 400 a 600 |
| Número em destaque (stat-tile) | `--font-numeros` | Sora 700 a 800 |
| **Número de dado** | `--fonte-mono` = `--font-tech` | IBM Plex Mono 400 a 700 |

As duas famílias já são carregadas no `templates/head.html`. Não baixe outra.

---

## 4. Tokens (V0a)

### Forma
| Token | Valor | Uso |
|---|---|---|
| `--raio-xs` | 10px | miniatura, ícone com fundo |
| `--raio-sm` | 14px (`--radius-sm`) | botão, campo, item dentro de card |
| `--raio` | 20px (`--radius`) | card, lista-item solto |
| `--raio-lg` | 28px | bottom-sheet (cantos de cima), card hero |
| `--raio-pilula` | 999px | chip, botão pílula, toggle |

Raio concêntrico: o elemento de dentro usa mais ou menos o raio de fora menos o padding. Card
com 20px e padding de 16px pede filho com raio próximo de `--raio-xs`/`--raio-sm`.

### Espaço (grade de 8px)
`--espaco-1` 4px (meio-passo, só entre ícone e texto) · `--espaco-2` 8px · `--espaco-3` 16px ·
`--espaco-4` 24px · `--espaco-5` 32px · `--espaco-6` 48px. Todos em rem.

### Profundidade
| Token | O que é |
|---|---|
| `--superficie-1` | `--surface` (fundo de seção) |
| `--superficie-2` | `--surface-2` a 94% (card) |
| `--superficie-3` | `--surface-3` a 96% (dentro do card, ou card sobre card) |
| `--realce-superficie` | degradê de luz no topo, a 3.5% do `--text`. Vai como **primeira** camada do `background` |
| `--veu-hover` / `--veu-pressionado` | `--text` a 4% e a 7%, por cima da superfície |
| `--veu-fundo` | `--bg` a 60%, atrás do bottom-sheet |
| `--linha` | 1px |
| `--borda-sutil` / `--borda-forte` | `--border` / `--border-strong` |
| `--elevacao-0` | só o realce interno de 1px (plano) |
| `--elevacao-1` | realce + contato curto. Card comum, lista-item, campo |
| `--elevacao-2` | + queda suave. Card destaque, hover de card, chip ativo |
| `--elevacao-3` | + queda longa. Bottom-sheet, menu flutuante, FAB |

### Movimento, toque e camadas
| Token | Valor | Uso |
|---|---|---|
| `--transicao-rapida` | 0.15s ease | cor, fundo, borda, opacidade |
| `--transicao-media` | 0.22s `--ease-bounce` | transform ao soltar |
| `--transicao-lenta` | 0.3s `--ease-suave` | abrir e fechar, sheet, recolhível |
| `--transicao-pressionar` | 0.09s ease-in | afundar no toque |
| `--escala-pressionado` | 0.97 | card ou linha inteira pressionada |
| `--toque-min` / `--toque-confortavel` | 44px / 48px | alvo mínimo / botão principal e linha |
| `--anel-foco` | folga de 2px do fundo + anel de `--text` a 55% | `:focus-visible` dos componentes |
| `--camada-fab` / `--camada-veu` / `--camada-sheet` | 20 / 40 / 41 | acima do `#tabbar` (10), abaixo do grão (50) |

Com `prefers-reduced-motion: reduce`, as durações caem para ~0 e `--escala-pressionado` vira 1.

---

## 5. Receitas

Receitas de referência. A implementação oficial de cada classe é de V0b a V0d. A seção só
**usa** a classe e, se precisar, ajusta com um seletor específico no próprio CSS dela.

### Card (padrão)
```css
.card {
  background: var(--realce-superficie), var(--superficie-2);
  border: var(--linha) solid var(--borda-sutil);
  border-radius: var(--raio);
  padding: var(--espaco-3);
  box-shadow: var(--elevacao-1);
}
.card-titulo { /* já existe no style.css (cards do chat): 0.95rem, 600, --text */ }
```
Hierarquia interna: título (`--text`, 600) → linha de meta (`--text-muted`, 0.8rem) → número
(`--fonte-mono`). Ações ficam no rodapé ou à direita, nunca soltas no meio.

### Card de destaque (um por seção, no máximo)
```css
.card.card-destaque {
  border-color: var(--glass-border);   /* tingido pela aba */
  box-shadow: var(--elevacao-2);
}
```
Nunca pinte o fundo inteiro com a cor da aba. No máximo `--cor-X-fill` num bloco pequeno
(stat-tile) ou uma barra de 3px de `--cor-X` à esquerda.

### Card sobre card / bloco interno
`background: var(--superficie-3); border-radius: var(--raio-sm); box-shadow: var(--elevacao-0);`
Se vai ter mais de 2 níveis, troque o de dentro por **lista com divisor**.

### Lista-item
Linha de 48px ou mais (`--toque-confortavel`), padding `--espaco-2 --espaco-3`, divisor
`border-bottom: var(--linha) solid var(--borda-sutil)` (o último sem divisor). Solto na aba vira
card (receita acima). Dentro de card, é só linha. Ação secundária (apagar) em ícone de 44px
à direita, `--text-faint`, e vira `--danger` só no hover ou foco.

### Campo
`min-height: var(--toque-min); background: var(--superficie-3); border: var(--linha) solid var(--borda-sutil); border-radius: var(--raio-sm); padding: 0 var(--espaco-3); font: inherit; color: var(--text);`.
Placeholder em `--text-faint`. No foco: `border-color: var(--borda-forte); box-shadow: var(--anel-foco);`.
Rótulo acima do campo (0.8rem, `--text-muted`). Não use o placeholder como único rótulo em formulário longo.

### Chip
Pílula (`--raio-pilula`), altura de 32px com área de toque de 44px (padding vertical ou
`::after` invisível), fundo `--superficie-3`, borda sutil, texto 0.8rem. Ativo:
`border-color: var(--glass-border); color: var(--text); box-shadow: var(--elevacao-2)`.

### Botões
| Classe | Aparência |
|---|---|
| `.btn.btn-primario` | fundo `--accent-fill` + `--realce-superficie`, borda `--borda-forte`, texto `--accent-text`, 600, `--raio-sm`, 44px ou mais |
| `.btn-secundario` | fundo transparente ou `--superficie-3`, borda sutil, texto `--text` |
| `.btn-perigo` | texto `--danger`, fundo `--danger-bg`, borda `--danger` a ~35%. Só para ação destrutiva |
| `.btn-adicionar` | **o botão de adicionar do app.** Largura cheia, 48px ou mais, ícone "+" de traço à esquerda, `--superficie-2` + realce, borda tracejada ou `--glass-border`, `--elevacao-1`. Abre um `.bottom-sheet` com o formulário (o formulário não fica mais aberto na seção) |
| `.btn-fab` | redondo, 56px, `--elevacao-3`, `z-index: var(--camada-fab)`, acima da barra de abas |

Nunca deixe aparecer o botão nativo do navegador (cinza ou azul, com borda chanfrada). Hoje isso
acontece em "Ouvir resumo da manha" (Hoje) e em "+ Adicionar" de Hábitos e Projetos (Vida). É
o alvo número um das faixas V.

### Seção recolhível
```html
<section class="secao-recolhivel" data-aberto="false" data-secao-id="memoria">
  <button class="secao-cabecalho" aria-expanded="false">Título <span class="chevron"></span></button>
  <div class="secao-conteudo">…</div>
</section>
```
Cabeçalho de 48px ou mais com o título à esquerda e um chevron de traço à direita (gira 180°
com `--transicao-lenta`). O conteúdo abre com `--transicao-lenta`. O JS (`static/js/ui/secao-recolhivel.js`,
da V0c) liga sozinho e salva o estado por `data-secao-id`. `data-secao-id` é único no app.

### Bottom-sheet
`<div class="bottom-sheet" hidden>…</div>`, com a API `abrirBottomSheet(elOuId)` e
`fecharBottomSheet(elOuId)` (`static/js/ui/bottom-sheet.js`, da V0d). Visual: fundo
`--superficie-2` + realce, `border-radius: var(--raio-lg) var(--raio-lg) 0 0`, borda de cima
`--borda-forte`, `--elevacao-3`, pegador de 36×4px em `--borda-forte`, padding `--espaco-4` e
`padding-bottom` com `env(safe-area-inset-bottom)`. Véu `--veu-fundo` em `--camada-veu`.
Entra de baixo com `--transicao-lenta`. O título do sheet repete o verbo do botão que o abriu
("Adicionar hábito") e o botão final diz o que faz ("Salvar hábito").

---

## 6. Estados

| Estado | Como |
|---|---|
| Hover (só em `@media (hover: hover)`) | `border-color: var(--borda-forte)` + `--elevacao-2`, ou `--veu-hover` em linha. O `button` global já sobe 1px (não duplique) |
| Pressionado | `transform: scale(var(--escala-pressionado)); transition: transform var(--transicao-pressionar)` + `--veu-pressionado`. O `button` global já faz `scale(0.93)`, então não empilhe outra escala num `<button>` |
| Soltar | `transition: transform var(--transicao-media)` (a mola que o app já tem) |
| Foco visível | `outline: none; box-shadow: var(--anel-foco);` (junte com a elevação: `box-shadow: var(--anel-foco), var(--elevacao-1)`) |
| Desabilitado | `opacity: .5; cursor: not-allowed`, sem hover e sem sombra |
| Carregando | `.spinner` existente dentro do botão, com o rótulo mantido ("Salvando…") |
| Vazio | frase curta de convite em `--text-muted` + `.btn-adicionar` logo abaixo |
| Erro | texto `--danger` + ícone. Explica o que houve e o que fazer, sem pedir desculpa |
| Ativo ou selecionado | borda `--glass-border` + indicador na cor da aba (barra, ponto ou ícone), nunca só a cor |

## 7. Números em mono

Todo dado numérico que o olho compara (R$, horas, contagens, %, datas curtas, METAR) usa
`font-family: var(--fonte-mono); font-variant-numeric: tabular-nums;`. O número grande do
stat-tile continua em `--font-numeros` (Sora), que já é o padrão da aba Hoje e não muda. Unidade e
rótulo ficam na fonte de texto, menores e em `--text-muted`.

## 8. Ícones de traço

- SVG inline, `viewBox="0 0 24 24"`, `fill="none" stroke="currentColor"`,
  `stroke-linecap="round" stroke-linejoin="round"`.
- Espessura: **1.8** para ícone de interface (o padrão do app, com 108 usos), e **2.2** só para
  glifos pequenos de ação dentro de botão (`ICONE_PLUS`, `ICONE_CHECK`).
- Tamanho: 16px dentro de botão, 18 a 20px em cabeçalho de seção, 24px na barra de abas.
- Reaproveite `static/js/nucleo/icones.js` (`ICONE_*`). Ícone novo vai no arquivo da seção.
  Não use emoji como ícone de interface: emoji só aparece em conteúdo do usuário.

## 9. Toque e acessibilidade

- Área tocável de `--toque-min` (44px) ou mais em tudo. O visual pode ser menor, desde que o
  padding ou um `::after` complete a área.
- Contraste de texto de 4.5:1 ou mais (o `--text-faint` sobre `--superficie-3` fica perto do
  limite, então use só para dica, nunca para dado).
- A cor nunca é o único sinal: sempre vem com ícone ou texto.
- O `hidden` e o `aria-expanded` refletem o estado real. O foco vai para o primeiro campo do sheet ao abrir
  e volta para o botão de origem ao fechar.

---

## 10. Pegadinhas deste app

- **Variável composta congela a cor.** `--glass-border`/`--glass-shadow` são redeclarados em cada
  `#tab-X` porque um `var()` dentro de uma variável resolve onde ela foi declarada. Se criar
  variável composta que dependa de `--glass-tint`/`--secao-cor`, declare-a no elemento da seção,
  não no `:root`. Os tokens da V0a só dependem de variáveis fixas e podem ser herdados sem esse problema.
- **O `button` global** (`style.css` ~l.344 e l.412) já tem transição, sobe 1px no hover e
  encolhe para 0.93 no toque. Seus botões herdam isso. Não brigue com ele e não use `!important`.
- **O `:focus-visible` global** usa `--accent-2` (`#08080a`) e quase some no preto. Os componentes
  usam `--anel-foco`. Trocar o global é com o integrador (o `style.css` não é de faixa nenhuma).
- **`.card-titulo` já existe** (`style.css` ~l.5526, cards de resultado do chat em
  `cards-tipos.js`). Se o `.card` novo precisar de outro título, escope como `.card > .card-titulo`.
- **`li.item`** já tem animação de entrada escalonada e hover próprios. Numa lista que passa a usar
  `.lista-item`, não mantenha as duas classes no mesmo elemento.
- A cascata vai de `style.css` para `fase7.css` (tokens, componentes, aba, seção). Arquivo que vem
  depois ganha no empate, então use seletores específicos da seção e não `!important`.

## 11. Não fazer

- Cor, fonte ou animação decorativa nova. Gradiente como enfeite.
- Sombra única grande e cinza (`0 10px 30px rgba(0,0,0,.3)`), ou vários cards iguais com a mesma sombra.
- Card dentro de card dentro de card.
- Rótulo todo em MAIÚSCULAS em cada bloco (o título de seção já existente é a exceção, não o modelo).
- Botão nativo sem estilo, azul padrão ou alvo menor que 44px.
- Formulário sempre aberto no meio da seção (vai para o bottom-sheet).

## 12. Checklist da faixa antes de fechar

- [ ] Só as classes do contrato (`.btn-*`, `.secao-recolhivel`, `.bottom-sheet`, `.card`,
      `.card-titulo`, `.chip`, `.campo`, `.lista-item`) e só os tokens (sem hex novo).
- [ ] Hierarquia: no máximo um card com `--elevacao-2` por seção.
- [ ] Números em `--fonte-mono` com `tabular-nums`.
- [ ] Ícones de traço, sem emoji de interface.
- [ ] Alvos de 44px ou mais, foco visível com `--anel-foco` e estados de hover, pressionado e desabilitado.
- [ ] Playwright 390x844, banco de teste, sem erro de console e no máximo 2 screenshots por tela.
      Modelo pronto: `scripts/ralph-v0a-tokens/servidor.py` + `verificar.py`.

## 13. Adendos da C2 (polimento final)

- **`[hidden]` sempre vence.** Componente que define `display` numa classe precisa da
  guarda `.classe[hidden] { display: none }`. Container de aba usa `#tab-x:not([hidden])`.
  `tests/test_fase7_c2_visual.py` cobra as duas regras.
- **Bottom-sheet:** o título vai em `<h3 class="bottom-sheet-titulo">` como primeiro filho
  do `.bottom-sheet`. O formulário com `.form-linha` vira coluna, e o último `.form-linha`
  dele é a linha de ações (`.btn-primario` "Salvar X" + `.btn-secundario` Cancelar com
  `data-fecha-sheet`). Aberto, o sheet mora no `<body>`: não estilize o conteúdo dele com
  `#tab-x ...`, use os componentes ou `.bottom-sheet #id`.
- **Rótulo dentro de card** (tipo de item, status, prazo) é `.chip.chip--compacto`, com
  24px e sem área de 44px. `.chip` sozinho é para o que se toca.
- **Checkbox:** o `campo.css` estiliza todo `input[type=checkbox]` com `:where()`
  (especificidade zero). Não use `accent-color` para "consertar" o visual.
- **Ação pequena em linha de lista:** mantenha o visual compacto e amplie o toque com
  `::after` invisível de `max(100%, var(--toque-min))` × `var(--toque-min)`.
