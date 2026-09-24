# Aprendizados - faixa p1b-caixa-ui

- **Contagem da faixa compacta vs. contagem no titulo**: a faixa compacta
  mostra so os 3 itens mais urgentes (`itensUrgentes(itens, 3)`), mas o
  titulo "Pendencias do assistente (N)" e o selo `.nav-selo` usam
  `pendentes` (a contagem TOTAL que a API devolve), nao `itens.length` da
  lista renderizada. Um teste que espera a lista encolher a cada resposta
  esta errado quando ha mais de 3 pendentes: responder o 4o-pra-3o item nao
  muda a CONTAGEM da lista visivel (continua cabendo 3), so troca QUAL item
  aparece. A prova certa e o item respondido (por `data-item-id`) sumir do
  DOM, nao o `.count()` da lista cair.

- **"Ver tudo" precisa clicar o botao de verdade, nao chamar `showTab()`
  direto**: cada secao da tela Assistente (caixa/regras/avisos.js) carrega
  os proprios dados no evento de CLIQUE do botao `.tab-btn[data-tab=
  "assistente"]` (porque `nucleo/navegacao.js` nao e arquivo desta faixa e
  `ORDEM_ABAS`/`showTab()` nao conhecem "assistente" - ver progress.txt).
  O link "Ver tudo" da faixa compacta, ao inves de chamar `showTab(
  "assistente")` direto (o que troca a aba visualmente mas NAO dispara o
  evento `click` do botao), agora faz `btn.click()` no botao de verdade -
  assim os 3 listeners (caixa/regras/avisos) disparam juntos, exatamente
  como se o Alex tivesse tocado na aba. Sem isso, Regras/Avisos ficavam
  vazios ate o usuario clicar de novo na aba manualmente.

- **`.chip` pede `.chip--compacto` pra virar so um rotulo**: o contrato de
  `ui/componentes/chip.css` (V0c) da `min-height: 44px` a QUALQUER `.chip`
  por padrao (pensado pra chip clicavel/filtro). Uma tag pequena dentro de
  um card (tipo do item, gatilho da regra) precisa do modificador
  `.chip--compacto` (que o proprio chip.css ja prevê: "tag dentro de um
  card"), senao a UI fica com pilulas enormes onde deveria ser um rotulo
  discreto.

- **Quando a faixa que voce depende ainda nao esta na integracao**: o
  prompt manda ler o contrato via `git show origin/fase7/<faixa>:<arquivo>`
  e seguir. Na pratica, ao chegar na ultima historia (o
  `git merge origin/fase7/integracao`), as duas faixas que faltavam
  (p1a-caixa, p4-regras) JA TINHAM chegado la sozinhas nesse meio-tempo -
  nao precisei copiar nada manualmente pra testar. Vale sempre checar de
  novo com `git fetch && git log HEAD..origin/fase7/integracao --oneline`
  antes de montar qualquer gambiarra de "copiar arquivo do outro branch so
  pra testar localmente".

- **CSS escrito antes de V0a-V0d chegarem**: dá pra escrever contra o
  contrato de classes (`.card`, `.chip`, `.secao-recolhivel`) mesmo com os
  arquivos de componente ainda vazios, com fallback `var(--x, valor)` em
  tudo. Quando a faixa real chega (aqui, V0c chegou no meio do caminho),
  vale reler o CSS proprio procurando declaracao que agora DUPLICA ou
  CONFLITA com o componente de verdade (mesmo seletor/especificidade, a
  ordem de import faz a sua ganhar por ultimo) - nao e so "deixar por
  cima", pode ficar visualmente pior que o componente novo (ex: o chevron
  desenhado com borda rotacionada por cima do chevron SVG com mascara do
  V0c).
