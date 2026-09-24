# Mapa do frontend (Fase 7, X2)

Pra achar onde mexer sem ler o repo todo. Cada secao tem **3 arquivos seus** (HTML, JS, CSS):
uma faixa edita so os arquivos das secoes dela. Tudo e JS classico (escopo global
compartilhado, sem modulos) e Jinja `{% include %}`.

## Como a pagina e montada
- `templates/index.html` so faz include: `head.html` -> `secoes/topo/cabecalho.html` ->
  `secoes/topo/captura.html` -> `<main>` com `abas/<aba>.html` (cada aba inclui
  `secoes/<aba>/<secao>.html`) -> `navegacao.html` (barra inferior, botoes das abas) ->
  `scripts.html` (todas as tags `<script>`, NA ORDEM de carga).
- Aba `assistente` (`abas/assistente.html`, `#tab-assistente`) existe escondida e **sem botao**
  na barra ainda; `#caixa-assistente` e o ponto de montagem vazio no topo da aba Hoje.
- Includes ficam na coluna 0 de proposito: assim o HTML renderizado fica byte a byte igual ao
  de antes da divisao (Jinja nao reindenta o conteudo incluido).

## Ordem de carga do JS (`templates/scripts.html`)
`charts.js`, `fila-offline.js`, `cards.js`, `cards-tipos.js` -> `nucleo/` (base, icones,
formatos, api, navegacao, ui, linha-do-tempo, voz, vida-base) -> `ui/` (bottom-sheet,
secao-recolhivel; vazios) -> `secoes/topo`, `hoje`, `painel`, `vida`, `tarefas`, `gastos`,
`bancos`, `construtora`, `aviacao`, `assistente` -> **`nucleo/init.js`** (carga inicial:
`loadSummary()`... e `loadVidaHoje()`, listener de aba da Vida) -> `visao-dia.js` ->
`voz-comando.js`.
- Arquivo de secao so **declara** funcoes/consts e liga listeners dos proprios elementos. Codigo
  que roda na carga e chama funcao de outro arquivo tem que ficar no `nucleo/init.js` (ou o
  arquivo chamado tem que carregar antes) - senao `ReferenceError`. Os `nucleo/*.js` sao
  compartilhados: mudanca ali afeta todas as faixas.
- Nome global e unico no app inteiro (`const`/`let` repetido entre dois arquivos = `SyntaxError`
  que derruba o segundo arquivo inteiro).
- `showTab()` (nucleo/navegacao.js) recarrega Painel/Tarefas/Gastos/Bancos/Construtora/Aviacao;
  a Vida recarrega no clique da barra (listener no `nucleo/init.js`).
- Arquivo JS/CSS **novo** precisa entrar em `static/service-worker.js` (lista `ASSETS`) e subir
  `CACHE_NAME`, senao o app nao abre offline - `tests/test_fase7_estrutura_frontend.py` pega.

## CSS em camadas
`style.css` (nao editar/dividir) -> `static/css/fase7.css` (so `@import`, nessa ordem):
`ui/tokens.css` -> `ui/componentes/{botao,secao,card,chip,campo,lista-item,bottom-sheet,navegacao}.css`
-> `secoes/<aba>.css` -> `secoes/<aba>/<secao>.css`. Todos nasceram vazios; o que vem depois
sobrescreve por cascata. Barra inferior: `templates/navegacao.html` + `ui/componentes/navegacao.css`
(JS da troca de aba: `nucleo/navegacao.js`).

## Secao -> arquivos
Caminhos relativos: HTML em `templates/`, JS em `static/js/`, CSS em `static/css/`.


### topo (fora das abas) - CSS da aba: `secoes/topo.css`

| Secao | HTML | JS | CSS |
|---|---|---|---|
| cabecalho | `secoes/topo/cabecalho.html` | `secoes/topo/cabecalho.js` | `secoes/topo/cabecalho.css` |
| captura | `secoes/topo/captura.html` | `static/js/secoes/topo/captura.js` + `static/js/voz-comando.js` (comando de voz; nao mover) | `secoes/topo/captura.css` |

### hoje - `abas/hoje.html`, CSS da aba: `secoes/hoje.css`

| Secao | HTML | JS | CSS |
|---|---|---|---|
| saudacao | `secoes/hoje/saudacao.html` | `secoes/hoje/saudacao.js` | `secoes/hoje/saudacao.css` |
| sobrecarga | `secoes/hoje/sobrecarga.html` | `secoes/hoje/sobrecarga.js` | `secoes/hoje/sobrecarga.css` |
| previa-noite | `secoes/hoje/previa-noite.html` | `secoes/hoje/previa-noite.js` | `secoes/hoje/previa-noite.css` |
| rotina | `secoes/hoje/rotina.html` | `secoes/hoje/rotina.js` | `secoes/hoje/rotina.css` |
| checkin | `secoes/hoje/checkin.html` | `secoes/hoje/checkin.js` | `secoes/hoje/checkin.css` |
| essencial | `secoes/hoje/essencial.html` | `secoes/hoje/essencial.js` | `secoes/hoje/essencial.css` |
| hiperfoco | `secoes/hoje/hiperfoco.html` | `secoes/hoje/hiperfoco.js` | `secoes/hoje/hiperfoco.css` |
| chat | `secoes/hoje/chat.html` | `secoes/hoje/chat.js` | `secoes/hoje/chat.css` |
| visao-do-dia | `secoes/hoje/visao-do-dia.html` | `static/js/visao-dia.js` (nao mover: testado em tests/js) | `secoes/hoje/visao-do-dia.css` |

### painel - `abas/painel.html`, CSS da aba: `secoes/painel.css`

| Secao | HTML | JS | CSS |
|---|---|---|---|
| resumo | `secoes/painel/resumo.html` | `secoes/painel/resumo.js` | `secoes/painel/resumo.css` |
| agenda-de-hoje | `secoes/painel/agenda-de-hoje.html` | `secoes/painel/agenda-de-hoje.js` | `secoes/painel/agenda-de-hoje.css` |
| fechamento | `secoes/painel/fechamento.html` | `secoes/painel/fechamento.js` | `secoes/painel/fechamento.css` |
| saude-hoje | `secoes/painel/saude-hoje.html` | `secoes/painel/saude-hoje.js` | `secoes/painel/saude-hoje.css` |
| peso-e-medidas | `secoes/painel/peso-e-medidas.html` | `secoes/painel/peso-e-medidas.js` | `secoes/painel/peso-e-medidas.css` |
| plano-do-dia | `secoes/painel/plano-do-dia.html` | `secoes/painel/plano-do-dia.js` | `secoes/painel/plano-do-dia.css` |
| devo-sair | `secoes/painel/devo-sair.html` | `secoes/painel/devo-sair.js` | `secoes/painel/devo-sair.css` |
| datas-importantes | `secoes/painel/datas-importantes.html` | `secoes/painel/datas-importantes.js` | `secoes/painel/datas-importantes.css` |
| medicamentos | `secoes/painel/medicamentos.html` | `secoes/painel/medicamentos.js` | `secoes/painel/medicamentos.css` |
| memoria | `secoes/painel/memoria.html` | `secoes/painel/memoria.js` | `secoes/painel/memoria.css` |
| esperando-resposta | `secoes/painel/esperando-resposta.html` | `secoes/painel/esperando-resposta.js` | `secoes/painel/esperando-resposta.css` |
| notas | `secoes/painel/notas.html` | `secoes/painel/notas.js` | `secoes/painel/notas.css` |
| diario-de-decisao | `secoes/painel/diario-de-decisao.html` | `secoes/painel/diario-de-decisao.js` | `secoes/painel/diario-de-decisao.css` |
| brain-dump | `secoes/painel/brain-dump.html` | `secoes/painel/brain-dump.js` | `secoes/painel/brain-dump.css` |

### vida - `abas/vida.html`, CSS da aba: `secoes/vida.css`

| Secao | HTML | JS | CSS |
|---|---|---|---|
| habitos | `secoes/vida/habitos.html` | `secoes/vida/habitos.js` | `secoes/vida/habitos.css` |
| projetos | `secoes/vida/projetos.html` | `secoes/vida/projetos.js` | `secoes/vida/projetos.css` |
| agenda-painel | `secoes/vida/agenda-painel.html` | `secoes/vida/agenda-painel.js` | `secoes/vida/agenda-painel.css` |
| pra-responder | `secoes/vida/pra-responder.html` | `secoes/vida/pra-responder.js` | `secoes/vida/pra-responder.css` |
| lista-de-compras | `secoes/vida/lista-de-compras.html` | `secoes/vida/lista-de-compras.js` | `secoes/vida/lista-de-compras.css` |
| pessoas | `secoes/vida/pessoas.html` | `secoes/vida/pessoas.js` | `secoes/vida/pessoas.css` |
| treino | `secoes/vida/treino.html` | `secoes/vida/treino.js` | `secoes/vida/treino.css` |
| contas-pessoais | `secoes/vida/contas-pessoais.html` | `secoes/vida/contas-pessoais.js` | `secoes/vida/contas-pessoais.css` |
| ainda-usa | `secoes/vida/ainda-usa.html` | `secoes/vida/ainda-usa.js` | `secoes/vida/ainda-usa.css` |
| manutencao | `secoes/vida/manutencao.html` | `secoes/vida/manutencao.js` | `secoes/vida/manutencao.css` |
| garantia | `secoes/vida/garantia.html` | `secoes/vida/garantia.js` | `secoes/vida/garantia.css` |
| viagens | `secoes/vida/viagens.html` | `secoes/vida/viagens.js` | `secoes/vida/viagens.css` |
| lugares | `secoes/vida/lugares.html` | `secoes/vida/lugares.js` | `secoes/vida/lugares.css` |
| ideias-de-presente | `secoes/vida/ideias-de-presente.html` | `secoes/vida/ideias-de-presente.js` | `secoes/vida/ideias-de-presente.css` |
| quero-aprender | `secoes/vida/quero-aprender.html` | `secoes/vida/quero-aprender.js` | `secoes/vida/quero-aprender.css` |
| salvos | `secoes/vida/salvos.html` | `secoes/vida/salvos.js` | `secoes/vida/salvos.css` |
| mensagem-dificil | `secoes/vida/mensagem-dificil.html` | `secoes/vida/mensagem-dificil.js` | `secoes/vida/mensagem-dificil.css` |
| vale-a-pena | `secoes/vida/vale-a-pena.html` | `secoes/vida/vale-a-pena.js` | `secoes/vida/vale-a-pena.css` |
| seu-progresso | `secoes/vida/seu-progresso.html` | `secoes/vida/seu-progresso.js` | `secoes/vida/seu-progresso.css` |
| revisao-trimestral | `secoes/vida/revisao-trimestral.html` | `secoes/vida/revisao-trimestral.js` | `secoes/vida/revisao-trimestral.css` |

### tarefas - `abas/tarefas.html`, CSS da aba: `secoes/tarefas.css`

| Secao | HTML | JS | CSS |
|---|---|---|---|
| tarefas | `secoes/tarefas/tarefas.html` | `secoes/tarefas/tarefas.js` | `secoes/tarefas/tarefas.css` |

### gastos - `abas/gastos.html`, CSS da aba: `secoes/gastos.css`

| Secao | HTML | JS | CSS |
|---|---|---|---|
| gastos | `secoes/gastos/gastos.html` | `secoes/gastos/gastos.js` | `secoes/gastos/gastos.css` |
| metas | `secoes/gastos/metas.html` | `secoes/gastos/metas.js` | `secoes/gastos/metas.css` |

### bancos - `abas/bancos.html`, CSS da aba: `secoes/bancos.css`

| Secao | HTML | JS | CSS |
|---|---|---|---|
| bancos | `secoes/bancos/bancos.html` | `secoes/bancos/bancos.js` | `secoes/bancos/bancos.css` |
| ofx | `secoes/bancos/ofx.html` | `secoes/bancos/ofx.js` | `secoes/bancos/ofx.css` |

### construtora - `abas/construtora.html`, CSS da aba: `secoes/construtora.css`

| Secao | HTML | JS | CSS |
|---|---|---|---|
| construtora | `secoes/construtora/construtora.html` | `secoes/construtora/construtora.js` | `secoes/construtora/construtora.css` |
| contas-a-pagar | `secoes/construtora/contas-a-pagar.html` | `secoes/construtora/contas-a-pagar.js` | `secoes/construtora/contas-a-pagar.css` |
| cotacoes | `secoes/construtora/cotacoes.html` | `secoes/construtora/cotacoes.js` | `secoes/construtora/cotacoes.css` |

### aviacao - `abas/aviacao.html`, CSS da aba: `secoes/aviacao.css`

| Secao | HTML | JS | CSS |
|---|---|---|---|
| horas-voadas | `secoes/aviacao/horas-voadas.html` | `secoes/aviacao/horas-voadas.js` | `secoes/aviacao/horas-voadas.css` |
| registrar-voo | `secoes/aviacao/registrar-voo.html` | `secoes/aviacao/registrar-voo.js` | `secoes/aviacao/registrar-voo.css` |
| proximos-voos | `secoes/aviacao/proximos-voos.html` | `secoes/aviacao/proximos-voos.js` | `secoes/aviacao/proximos-voos.css` |
| metar | `secoes/aviacao/metar.html` | `secoes/aviacao/metar.js` | `secoes/aviacao/metar.css` |

### assistente - `abas/assistente.html`, CSS da aba: `secoes/assistente.css`

| Secao | HTML | JS | CSS |
|---|---|---|---|
| caixa | `secoes/assistente/caixa.html` | `secoes/assistente/caixa.js` | `secoes/assistente/caixa.css` |
| regras | `secoes/assistente/regras.html` | `secoes/assistente/regras.js` | `secoes/assistente/regras.css` |
| avisos | `secoes/assistente/avisos.html` | `secoes/assistente/avisos.js` | `secoes/assistente/avisos.css` |

## Pegadinhas (codigo que nao mora onde o nome sugere)
- `secoes/painel/resumo.js` (`loadSummary`) tambem preenche os 3 numeros do topo da aba Hoje
  (`#stat-tarefas`, `#stat-gasto`, `#stat-metas`, que estao em `secoes/hoje/saudacao.html`).
- `secoes/hoje/saudacao.js` tem saudacao, streak, clima, Uber pendentes e o botao "Ouvir resumo
  da manha".
- `secoes/hoje/chat.js`: `enviarChat` e reusado pelo brain dump e pelo `voz-comando.js`.
- `secoes/topo/cabecalho.js`: custo de IA no topo (`loadUso`), push, horario silencioso, modo
  visitante (`modoVisitanteAtivo`, global lido por varias secoes), modo viagem e backup.
- `secoes/topo/captura.js`: captura rapida, duvida, cards de resultado e callbacks da fila
  offline; o logout e a sincronizacao inicial da fila ficam no `nucleo/init.js`.
- `secoes/gastos/gastos.js` tambem tem nota fiscal por foto, resumo semanal, custo de IA
  (teto) e `loadFimMes`.
- `secoes/tarefas/tarefas.js` tambem tem a "sugestao por energia"; `criarItemTarefa` e usado
  pelo treino (Vida).
- `secoes/vida/viagens.js` (Vida) e diferente de `secoes/painel/devo-sair.js` (form
  `#viagem-form` "Devo sair ate que horas?").
- `secoes/vida/vale-a-pena.js` (`#decisao-form`) e diferente de
  `secoes/painel/diario-de-decisao.js`.
- `nucleo/voz.js` (`falarTexto`) serve chat, resumo da manha e METAR/TAF.

## Arquivos vazios de proposito (pras faixas)
JS `secoes/assistente/{caixa,regras,avisos}.js`, `ui/bottom-sheet.js`, `ui/secao-recolhivel.js`;
HTML `secoes/assistente/{caixa,regras,avisos}.html`; todo o CSS de `fase7.css`.
