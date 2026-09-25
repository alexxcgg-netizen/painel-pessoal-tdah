# Laboratório de Telas (rodada 2) — brief comum

Pasta: `/tmp/claude-0/-home-user-financeiro-construtora/17e4bd9b-4591-5043-a1c2-e3ff8a458d65/scratchpad/lab2/`.
Nunca toque em `/home/user/financeiro-construtora` nem `/home/user/painel-pessoal-tdah`. Sem git.

## O que o dono disse da rodada 1 (10 direções HUD de ficção científica)
"Achei da hora, mas muito falso, coisa de filme. Tem que parecer uma coisa real, tipo um ChatGPT.
A parte de finanças por categoria eu achei legal. Quero 20 totalmente diferentes uma da outra."

Então: **cada direção tem que parecer um app de verdade que já poderia estar na App Store**, com
acabamento de produto (hierarquia, espaçamento, tipografia, estados), não um cenário de filme.
Nada de anéis girando, varredura de radar, grades de HUD, cantoneiras, texto "SYS-01", scanlines.
Animação só a de produto real: transição curta ao abrir, número que atualiza, barra que cresce,
indicador de digitando. Respeite `ctx.reduzido`.

## Formato do arquivo (igual à rodada 1)
Leia `../lab/CONTRATO.md` só as seções "Arquivo" e "Três telas" (formato `window.DIRECOES[N]`,
`render(root, D, ctx)` em ShadowRoot, retorno de limpeza, `ctx.irPara`). Use SEMPRE os dados de
`D` (arquivo `../dados_lab.json`, dados reais do Nubank do dono), nunca números fixos.
O arquivo agora é `lab2/dNN.js` (NN = 01..20). `nome` = 1–2 palavras; `ideia` = 1 linha.
`acento` = cor de destaque. `fontes` = famílias do Google Fonts no formato css2 (`"Inter:wght@400;600"`).
Ícones: SVG inline simples, sem emoji.

## Regras visuais
- A direção decide seu próprio fundo. Escuras usam `#000` puro. Claras são permitidas quando o
  estilo pede (a direção diz se é clara).
- Uma cor de destaque + neutros; cores de categoria só onde o gráfico precisa (máx. 6, com
  legenda). Sem glow, sem sombra luminosa, sem LED.
- **Finanças sempre com "gasto por categoria" em destaque e bem feito** (o dono gostou disso):
  barras/rosca/treemap/lista com barras, valores reais, legível. Cada direção faz de um jeito
  coerente com o estilo dela.
- Menos coisa na tela; detalhe ao tocar. Toque ≥ 44px. Contraste ≥ 4.5:1. Moeda pt-BR com
  `Intl.NumberFormat("pt-BR",{style:"currency",currency:"BRL"})`. `tabular-nums` em números.
- Largura 360–430px sem rolagem horizontal da página. Palco ~760px de altura; a tela pode rolar
  por dentro. Barra de navegação própria (Hoje/Finanças/Vida) é recomendada.
- Hoje: hora e data, clima, botão de voz, aviso crítico (`D.aviso_critico`) no topo, gasto do mês
  com gráfico, hoje/fatura/conta, "em foco agora", atalhos, campo do chat.
  Finanças: resumo do mês, gasto por categoria, fatura x conta, últimos 15 dias (mostra ~6 +
  "carregar mais"); extrato e assinaturas só ao tocar.
  Vida: as 18 seções (`D.vida_secoes`) como ícones pequenos no topo; só abre a tocada.

## Teste (uma vez, no máximo duas rodadas)
`cd lab2 && python3 montar.py <seus números>` gera `previa-<n>-<n>.html`. Prints com Playwright
(Python do venv `/home/user/painel-pessoal-tdah/.venv/bin/python`, Chromium em
`executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome"`, nunca `playwright install`),
viewport 390x844, em UM comando Bash: para cada direção clique `#nN`, depois `#t-hoje`,
`#t-financas`, `#t-vida`, salve em `lab2/prints/dN-<tela>.png`; capture `pageerror` e confira
`document.documentElement.scrollWidth <= 390`. Olhe os prints, corrija, no máximo mais uma rodada.
Teto: 40 chamadas de ferramenta. Bash com `| tail -20`.

## Relatório final (máx. 6 linhas)
Arquivos escritos, 1 linha por direção (como ficou), problemas conhecidos, chamadas usadas.

## PEDIDO NOVO DO DONO: "tem que ter gráficos"
Cada direção precisa de gráficos de verdade, bem feitos, no estilo dela — no mínimo:
- Hoje: gráfico do gasto acumulado do mês (`por_dia_mes`), com o mês anterior como referência se couber.
- Finanças: (1) gasto por categoria (`por_categoria`) e (2) evolução do mês por dia (`por_dia_mes`),
  e (3) fatura x conta como comparação visual. Pode ter mais (ex.: gasto por dia da semana, barras
  dos últimos 15 dias calculadas de `ultimos_15_dias`).
- Vida: ao menos um gráfico pequeno na seção aberta (ex.: progresso/sequência), mesmo que com
  dado de exemplo marcado como exemplo.
Gráficos em SVG desenhado à mão, escala correta, eixos/rótulos só de valores reais, legíveis a 390px.
