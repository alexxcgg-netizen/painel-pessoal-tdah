# Aprendizados - Fase 7, faixa C3b (Viagens, Lugares, Cotações, Aviação)

## `position: fixed` dentro de `.tab-content` não é fixo na tela
`.tab-content:not([hidden]) { animation: tabEntra ... both }` (style.css ~l.990) deixa o
último keyframe aplicado. Mesmo sendo `translate(0)`, um `transform` diferente de `none`
transforma a aba no bloco de contenção de todo descendente `position: fixed`. O
`.bottom-sheet` media 6.600px (a aba inteira) e o painel abria no fim da aba, fora da
tela. Isso só aparece medindo no Playwright: `getBoundingClientRect()` do sheet deve
ser 390x844. O contorno da faixa é mover o sheet pro `<body>` na primeira abertura. A
correção global é trocar o fill para `backwards` ou fazer o V0d portar o sheet pro body.

## V0d pula a estrutura se o autor já escreveu `.bottom-sheet-painel`
O `garantirEstrutura()` devolve o painel existente e não cria `.bottom-sheet-fundo` nem
`.bottom-sheet-alca`, então não há fundo escurecido nem toque fora. Escreva só
`<div class="bottom-sheet" hidden>conteúdo</div>`.

## `L.map(el)` transforma o próprio `el` em `.leaflet-container`
Uma regra `.x:has(.leaflet-container)` nunca casa quando o mapa foi criado no próprio
`.x`, e o `.leaflet-container { height: 100% }` genérico ganha da altura fixa se vier
depois na cascata. Selecione `.x.leaflet-container`.

## Fuzz com sheets: resete o form entre cenários
ESC fecha o sheet **sem** limpar (de propósito: o rascunho sobrevive a um fechamento
acidental). Um cenário de "hora inválida" deixou `25:99` no campo e fez o cenário
seguinte falhar sem bug nenhum no app.

## Playwright + `pkill -f`
`pkill -f "servidor.py"` casa com o próprio shell que roda o comando (a linha de
comando contém o texto). Use `pgrep -f "^/caminho/python scripts/..."` ancorado no início.
