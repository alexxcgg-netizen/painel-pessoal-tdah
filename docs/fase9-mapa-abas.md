# Fase 9: Mapa de Abas para Consolidação

**Data:** 2026-09-25  
**Objetivo:** Mapear as 8 abas atuais para consolidação em 4 abas + configurações  
**Consolidação planejada:** Hoje (Hoje+Assistente+resumo Painel) | Tarefas | Finanças (Gastos+Construtora) | Vida (Vida+Aviação) | Configurações (resto Painel)

---

## ABA: HOJE

**ID:** `id="tab-hoje"` | `data-tab="hoje"` | **Status:** Ativa por padrão

| Arquivo | Linhas | Seções/Conteúdo |
|---------|--------|-----------------|
| `templates/abas/hoje.html` | 13 | Template com 9 includes + div#caixa-assistente (injeção dinâmica de chat) |
| `secoes/hoje/saudacao.html` | 37 | Saudação personalizada, clima, Uber, streak |
| `secoes/hoje/sobrecarga.html` | 8 | Indicador de sobrecarga do dia |
| `secoes/hoje/previa-noite.html` | 9 | Pré-visualização de eventos noturnos |
| `secoes/hoje/rotina.html` | 8 | Rotina (manhã/dia/noite/dormir) |
| `secoes/hoje/checkin.html` | 8 | Check-in do dia (corpo/mente/energia) |
| `secoes/hoje/essencial.html` | 9 | Modo essencial (tarefas críticas) |
| `secoes/hoje/hiperfoco.html` | 7 | Contador hiperfoco |
| `secoes/hoje/chat.html` | 12 | Caixa de chat para assistente |
| `secoes/hoje/visao-do-dia.html` | 56 | Timeline visual do dia (eventos+tarefas+gastos) |

**JavaScript da Aba (9 arquivos, ~654 linhas)**

| Arquivo | Linhas | Funções top-level |
|---------|--------|-------------------|
| `saudacao.js` | 138 | `mostrarSaudacao()` · `loadStreak()` · `loadClimaHoje()` · `loadUberPendentes()` |
| `chat.js` | 257 | `criarAvatarChat()` · `criarBotaoOuvirChat()` · `escreverPalavraAPalavra()` · `criarBolhaChat()` · `criarIndicadorDigitando()` · `loadChatHistorico()` · `anexarCardsResposta()` · `recarregarAposMudancaDeCard()` · `enviarChat()` · `initVozChat()` |
| `essencial.js` | 79 | `aplicarModoEssencial()` · `renderEssencial()` · `loadEssencial()` |
| `hiperfoco.js` | 58 | `atualizarContagemHiperfoco()` · `renderHiperfoco()` · `loadHiperfoco()` |
| `previa-noite.js` | 34 | `loadPreviaNoite()` |
| `rotina.js` | 44 | `rotinaVisivel()` · `loadRotina()` |
| `checkin.js` | 64 | `loadCheckin()` |
| `sobrecarga.js` | 18 | `loadSobrecarga()` |
| `visao-do-dia.js` | 4 | (vazio/importado dinamicamente) |

**APIs Chamadas (13 endpoints)**

```
/api/chat/historico
/api/checkin/hoje
/api/clima/hoje
/api/essencial · /api/essencial/modo · /api/essencial/trocar
/api/hiperfoco
/api/previa-noite
/api/resumo-manha
/api/rotina
/api/sobrecarga
/api/streak
/api/uber/pedidos
```

---

## ABA: PAINEL

**ID:** `id="tab-painel"` | `data-tab="painel"` | **Status:** Oculta (hidden)

| Arquivo | Linhas | Seções/Conteúdo |
|---------|--------|-----------------|
| `templates/abas/painel.html` | 18 | 15 includes |
| `secoes/painel/resumo.html` | 9 | Resumo do dia (pct tarefas, saúde, humor) |
| `secoes/painel/agenda-de-hoje.html` | 15 | Calendário integrado |
| `secoes/painel/fechamento.html` | 18 | Encerramento do dia (reflexão) |
| `secoes/painel/saude-hoje.html` | 36 | Hidratação, ciclos, medicamentos |
| **secoes/painel/custo-ia.html** | 67 | **Custo IA + Modo teste IA + Exportar CSV** |
| `secoes/painel/peso-e-medidas.html` | 56 | Gráfico de evolução (peso, medidas) |
| `secoes/painel/plano-do-dia.html` | 13 | Plano estruturado |
| **secoes/painel/devo-sair.html** | 43 | **Integração de viagem (quando sair/status)** |
| `secoes/painel/datas-importantes.html` | 39 | Lembretes e datas |
| `secoes/painel/medicamentos.html` | 38 | Próximas doses |
| `secoes/painel/memoria.html` | 61 | Notas/memória pessoal |
| `secoes/painel/esperando-resposta.html` | 37 | Itens aguardando retorno |
| `secoes/painel/notas.html` | 21 | Notas rápidas |
| `secoes/painel/diario-de-decisao.html` | 32 | Decisões importantes |
| `secoes/painel/brain-dump.html` | 25 | Brain dump para processamento |

**JavaScript da Aba (15 arquivos, ~1,403 linhas)**

| Arquivo | Linhas | Funções top-level |
|---------|--------|-------------------|
| `resumo.js` | 71 | `salvarResumoCache()` · `lerResumoCache()` · `loadSummary()` |
| `custo-ia.js` | 113 | `custoIaV2FormatarPercentual()` · `custoIaV2PreencherTabela()` · `custoIaV2PreencherGrafico()` · `loadTesteIA()` · `loadCustoIAV2()` |
| `peso-e-medidas.js` | 208 | `dadosGraficoMedida()` · `loadMedidas()` · `medidaTipoEscolhido()` · `medidaUnidadeEscolhida()` · `medidaStepAtual()` · `medidaAjustarValor()` |
| `memoria.js` | 142 | `criarItemMemoria()` · `iniciarEdicaoMemoria()` · `loadMemorias()` |
| `datas-importantes.js` | 133 | `loadLembretes()` |
| `brain-dump.js` | 139 | `loadBrainDump()` · `processarBrainDumpNoAssistente()` |
| `medicamentos.js` | 118 | `proximaDoseTexto()` · `formatarDuracaoMin()` · `loadMedicamentos()` |
| `diario-de-decisao.js` | 136 | `loadDecisoes()` |
| `esperando-resposta.js` | 146 | `loadEsperas()` |
| `saude-hoje.js` | 68 | `loadSaude()` · `celebrarHidratacao()` |
| `notas.js` | 64 | `loadNotas()` |
| `devo-sair.js` | 69 | `initViagemOrigemPadrao()` |
| `agenda-de-hoje.js` | 23 | `loadAgenda()` |
| `fechamento.js` | 20 | `loadFechamentoDoDia()` |
| `plano-do-dia.js` | 18 | (função load() implícita) |

**APIs Chamadas (21 endpoints)**

```
/api/summary/today · /api/agenda/eventos-criados
/api/calendario/hoje · /api/fechamento-do-dia
/api/saude/hoje · /api/hidratacao
/api/medidas · /api/medicamentos
/api/memorias · /api/lembretes
/api/notas · /api/diario-decisoes
/api/esperas · /api/esperas/prioridade
/api/brain-dump · /api/assistente/caixa
/api/viagem/status · /api/viagem/quando-sair
/api/ia/uso/resumo · /api/configuracoes/teste-ia
/api/ia/uso.csv (download) · /api/tasks · /api/metas · /api/plano-do-dia
```

**Acoplamento:** Brain-dump envia para Assistente; Painel carrega dados de Tarefas (showTab → loadTasks); Devo-sair carrega Viagem (aba Vida)

---

## ABA: VIDA

**ID:** `id="tab-vida"` | `data-tab="vida"` | **Status:** Oculta

| Arquivo | Linhas | Seções/Conteúdo |
|---------|--------|-----------------|
| `templates/abas/vida.html` | 30 | 20 includes dentro de div.vida-secoes |
| `secoes/vida/habitos.html` | 47 | Hábitos + painel de edição |
| `secoes/vida/projetos.html` | 32 | Projetos pessoais |
| `secoes/vida/agenda-painel.html` | 35 | Eventos criados (Google Calendar) |
| `secoes/vida/pra-responder.html` | 31 | Conversas pendentes |
| `secoes/vida/lista-de-compras.html` | 30 | Compras |
| `secoes/vida/pessoas.html` | 36 | Pessoas de relacionamento |
| `secoes/vida/treino.html` | 41 | Fichas de treino + exercícios |
| `secoes/vida/contas-pessoais.html` | 39 | Contas bancárias pessoais |
| `secoes/vida/ainda-usa.html` | 12 | Assinaturas para revisão |
| `secoes/vida/manutencao.html` | 53 | Itens de manutenção de casa/carro |
| `secoes/vida/garantia.html` | 36 | Garantias de produtos |
| `secoes/vida/viagens.html` | 44 | Viagens (timeline, mala, voos) |
| `secoes/vida/lugares.html` | 32 | Mapa de lugares + Leaflet |
| `secoes/vida/ideias-de-presente.html` | 32 | Ideias de presente |
| `secoes/vida/quero-aprender.html` | 24 | Aprendizados em fila |
| `secoes/vida/salvos.html` | 24 | Conteúdo salvo (links, tweets) |
| `secoes/vida/mensagem-dificil.html` | 16 | Modelos de mensagens difíceis |
| `secoes/vida/vale-a-pena.html` | 19 | Decisões (análise benefício/custo) |
| `secoes/vida/seu-progresso.html` | 20 | Progresso contra metas pessoais |
| `secoes/vida/revisao-trimestral.html` | 37 | Revisão trimestral (reflexão) |

**JavaScript da Aba (20 arquivos, ~2,157 linhas)**

| Arquivo | Linhas | Funções top-level |
|---------|--------|-------------------|
| `habitos.js` | 122 | `abrirPainelHabito()` · `fecharPainelHabito()` · `atualizarCamposFrequenciaHabito()` · `renderHabitoSemana()` · `loadHabitos()` |
| `projetos.js` | 106 | `carregarProjetos()` · `fecharPainelProjeto()` · `abrirPainelProjeto()` · `criarItemProjeto()` · `loadProjetos()` |
| `agenda-painel.js` | 64 | `abrirPainelEvento()` · `fecharPainelEvento()` · `loadEventosCriados()` |
| `pra-responder.js` | 81 | `renderItemResponder()` · `loadResponder()` |
| `lista-de-compras.js` | 64 | `loadCompras()` |
| `pessoas.js` | 124 | `criarItemPessoa()` · `abrirPainelPessoa()` · `fecharPainelPessoa()` · `loadPessoas()` |
| `treino.js` | 212 | `obterFichasTreino()` · `parseLinhaExercicio()` · `serializarExercicio()` · `renderExerciciosFicha()` · `renderFichaTreinosPendentes()` · `botaoFichaTreino()` · `loadTreino()` |
| `contas-pessoais.js` | 89 | `quandoContaPessoal()` · `loadContasPessoais()` |
| `ainda-usa.js` | 50 | `loadAssinaturasRevisao()` |
| `manutencao.js` | 133 | `criarItemManutencao()` · `abrirPainelManutencao()` · `fecharPainelManutencao()` · `loadManutencoes()` |
| `garantia.js` | 118 | `garantiaChip()` · `garantiaFracaoDecorrida()` · `loadGarantias()` |
| `viagens.js` | 221 | `renderItensMala()` · `renderTimelineViagem()` · `criarBlocoVoo()` · `criarStatusVooEl()` · `loadViagens()` · `levarSheetProBody()` · `abrirPainelViagem()` · `fecharPainelViagem()` · `abrirSecaoSeDestacado()` |
| `lugares.js` | 138 | `carregarLeaflet()` · `criarBlocoMapaLugar()` · `loadLugares()` · `abrirPainelLugar()` · `fecharPainelLugar()` |
| `ideias-de-presente.js` | 62 | `loadIdeiasPresente()` |
| `quero-aprender.js` | 76 | `loadAprender()` |
| `salvos.js` | 76 | `loadSalvos()` |
| `mensagem-dificil.js` | 47 | `criarBlocoMensagem()` · `loadMensagensModelo()` |
| `vale-a-pena.js` | 87 | `renderDecisao()` · `aplicarModoVisitanteNaDecisao()` |
| `seu-progresso.js` | 57 | `fmtPctMeta()` · `loadProgresso()` |
| `revisao-trimestral.js` | 58 | `carregarRevisaoPeriodo()` |

**APIs Chamadas (23 endpoints)**

```
/api/habitos · /api/projetos
/api/agenda/eventos-criados
/api/responder
/api/compras
/api/pessoas
/api/treino · /api/treino/fichas
/api/contas-pessoais
/api/assinaturas/revisao
/api/manutencoes
/api/garantias
/api/viagens
/api/lugares
/api/ideias-presente
/api/aprender
/api/salvos
/api/decisao
/api/progresso?dias=30
/api/uso-apps?dias=7
/api/revisao-mensal
```

---

## ABA: TAREFAS

**ID:** `id="tab-tarefas"` | `data-tab="tarefas"` | **Status:** Oculta

| Arquivo | Linhas | Seções/Conteúdo |
|---------|--------|-----------------|
| `templates/abas/tarefas.html` | 4 | 1 include simples |
| `secoes/tarefas/tarefas.html` | 38 | Lista de tarefas com filtros (hoje/semana/backlog) |

**JavaScript da Aba (1 arquivo, 343 linhas)**

| Arquivo | Linhas | Funções top-level |
|---------|--------|-------------------|
| `tarefas.js` | 343 | `abrirPainelTarefa()` · `fecharPainelTarefa()` · `carregarSugestaoEnergia()` · `criarTagEsforco()` · `criarItemTarefa()` · `criarFormularioTarefaParaGasto()` · `loadTasks()` |

**APIs Chamadas (1 endpoint)**

```
/api/tasks
```

---

## ABA: GASTOS (Finanças)

**ID:** `id="tab-gastos"` | `data-tab="gastos"` | **Status:** Oculta

| Arquivo | Linhas | Seções/Conteúdo |
|---------|--------|-----------------|
| `templates/abas/gastos.html` | 12 | 4 includes (bancos, gastos, assinaturas, metas) |
| `secoes/bancos/bancos.html` | 15 | Integração Nubank |
| `secoes/gastos/gastos.html` | 118 | Extrato, resumo semanal, fim de mês |
| `secoes/gastos/assinaturas.html` | 131 | Assinaturas ativas + parceladas |
| `secoes/gastos/metas.html` | 10 | Metas de gasto por categoria |

**JavaScript da Aba (3 arquivos, ~1,045 linhas)**

| Arquivo | Linhas | Funções top-level |
|---------|--------|-------------------|
| `gastos.js` | 549 | `lerArquivoComoBase64()` · `mostrarConfirmacaoNotaFiscal()` · `criarSeletorCategoriaGasto()` · `criarItemGasto()` · `loadResumoFinancas()` · `criarItemExtratoFinancas()` · `loadExtratoFinancas()` · `criarItemGastosProximaCobranca()` · `loadGastosProximasCobrancas()` · `loadExpenses()` · `preencherCustoIA()` · `loadCustoIA()` · `loadResumoSemanal()` · `loadFimMes()` · `preencherLinhaComValores()` |
| `assinaturas.js` | 378 | `numeroFinancas()` · `fmtMoedaFinancas()` · `fmtDataFinancas()` · `textoFinancas()` · `botaoIconeFinancas()` · `botaoApagarFinancas()` · `mostrarErroSheet()` · `sucessoSheetFinancas()` · `criarChipCartao()` · `criarLinhaLista()` · `criarItemAssinaturaAtiva()` · `criarItemParcela()` · `desenharLimiteCartao()` · `loadComprometido()` · `loadAssinaturasAtivas()` · `loadParcelasEmAndamento()` · `loadAssinaturas()` · `lerValorFinancas()` · `lerInteiroFinancas()` · `valorValidoFinancas()` |
| `metas.js` | 118 | `criarItemMeta()` · `loadMetas()` |

**APIs Chamadas (16 endpoints)**

```
/api/bancos/sincronizar-nubank
/api/expenses/historico?dias=14
/api/gastos/unificados · /api/gastos/resumo-semanal · /api/gastos/proximas-cobrancas
/api/financas/resumo · /api/financas/assinaturas · /api/financas/assinaturas?ativas=1
/api/financas/parcelas · /api/financas/parcelas?em_andamento=1
/api/financas/comprometido
/api/metas
/api/ia/custo · /api/ia/teto
/api/notas-fiscais/confirmar
/api/sobra-do-mes
```

---

## ABA: CONSTRUTORA

**ID:** `id="tab-construtora"` | `data-tab="construtora"` | **Status:** Oculta

| Arquivo | Linhas | Seções/Conteúdo |
|---------|--------|-----------------|
| `templates/abas/construtora.html` | 6 | 3 includes |
| `secoes/construtora/construtora.html` | 32 | Resumo de obras |
| `secoes/construtora/contas-a-pagar.html` | 10 | Contas a vencer da empresa |
| `secoes/construtora/cotacoes.html` | 38 | Comparação de cotações de materiais |

**JavaScript da Aba (3 arquivos, 433 linhas)**

| Arquivo | Linhas | Funções top-level |
|---------|--------|-------------------|
| `construtora.js` | 72 | `rotuloProximaConta()` · `loadConstrutora()` |
| `contas-a-pagar.js` | 42 | `quandoContaAVencer()` · `criarItemContaAVencer()` |
| `cotacoes.js` | 319 | `loadCotacoes()` · `graficoComparacaoCotacoes()` · `criarItemCotacao()` · `preencherDetalheCotacao()` · `abrirPainelCotacao()` · `fecharPainelCotacao()` |

**APIs Chamadas (2 endpoints)**

```
/api/construtora/resumo
/api/cotacoes
```

---

## ABA: AVIAÇÃO

**ID:** `id="tab-aviacao"` | `data-tab="aviacao"` | **Status:** Oculta

| Arquivo | Linhas | Seções/Conteúdo |
|---------|--------|-----------------|
| `templates/abas/aviacao.html` | 10 | 4 includes |
| `secoes/aviacao/horas-voadas.html` | 28 | Resumo de horas voadas |
| `secoes/aviacao/registrar-voo.html` | 39 | Formulário de registro de voo |
| `secoes/aviacao/proximos-voos.html` | 14 | Voos agendados |
| `secoes/aviacao/metar.html` | 47 | METAR/TAF decodificado |

**JavaScript da Aba (4 arquivos, 410 linhas)**

| Arquivo | Linhas | Funções top-level |
|---------|--------|-------------------|
| `horas-voadas.js` | 51 | `loadVoosResumo()` |
| `proximos-voos.js` | 122 | `criarIconeStatusVoo()` · `criarItemVoo()` |
| `metar.js` | 153 | `criarChipCategoriaVoo()` · `criarIconeVento()` · `renderCamposMeteo()` · `renderSegmentosTaf()` |
| `registrar-voo.js` | 84 | `abrirPainelVoo()` · `fecharPainelVoo()` |

**APIs Chamadas (4 endpoints)**

```
/api/voos/resumo
/api/voos · /api/voos/historico
/api/viagem/quando-sair
```

---

## ABA: ASSISTENTE

**ID:** `id="tab-assistente"` | `data-tab="assistente"` | **Status:** Oculta

| Arquivo | Linhas | Seções/Conteúdo |
|---------|--------|-----------------|
| `templates/abas/assistente.html` | 5 | 3 includes |
| `secoes/assistente/caixa.html` | 19 | Caixa de entrada (avisos processados) |
| `secoes/assistente/regras.html` | 7 | Configurações de automação |
| `secoes/assistente/avisos.html` | 32 | Avisos do sistema |

**JavaScript da Aba (3 arquivos, 652 linhas)**

| Arquivo | Linhas | Funções/Padrão |
|---------|--------|-----------------|
| `caixa.js` | 351 | `const CaixaAssistente = { ... }` (padrão módulo IIFE) |
| `regras.js` | 145 | `const RegrasAssistente = { ... }` (padrão módulo IIFE) |
| `avisos.js` | 156 | `const AvisosAssistente = { ... }` (padrão módulo IIFE) |

**APIs Chamadas (6 endpoints)**

```
/api/assistente/caixa
/api/assistente/caixa?estado=resolvido&limite=100
/api/assistente/avisos · /api/assistente/avisos/silencio
/api/assistente/saude
/api/p4_regras
```

---

## NAVEGAÇÃO E CONTROLE

**Arquivo:** `templates/navegacao.html` (41 linhas)

| Elemento | Data-tab | Classe | Função |
|----------|----------|--------|--------|
| Hoje | `data-tab="hoje"` | `.tab-btn.active` | Aba inicial ativa |
| Painel | `data-tab="painel"` | `.tab-btn` | Resumo + config |
| Vida | `data-tab="vida"` | `.tab-btn` | Pessoal + Aviação (futura) |
| Tarefas | `data-tab="tarefas"` | `.tab-btn` | Afazeres |
| Finanças | `data-tab="gastos"` | `.tab-btn` | Gastos + Construtora (futura) |
| Construtora | `data-tab="construtora"` | `.tab-btn` | Empresa |
| Aviação | `data-tab="aviacao"` | `.tab-btn` | Piloto |
| Assistente | `data-tab="assistente"` | `.tab-btn` | Avisos+caixa |

**CSS de Navegação:** `static/css/style.css` (linhas 910–1019)

| Seletor | Linhas | Função |
|---------|--------|--------|
| `#tabbar` | 910–930 | Barra fixa, flex, suporta .nav-selo |
| `.tab-btn` | 931–963 | Botão, font-size adaptativo, ícone+texto |
| `.tab-btn:hover:not(.active)` | 964–969 | Cor ao passar |
| `.tab-btn.active` | 970–1003 | Cor ativa, underline, icone preenchido |
| `.tab-content` | 1004–1015 | Hidden por padrão, transição suave |
| `.tab-content.entra-direita` | 1016–1018 | Slide da direita (avanço) |
| `.tab-content.entra-esquerda` | 1019 | Slide da esquerda (volta) |

**JavaScript de Navegação:** `static/js/nucleo/navegacao.js` (64 linhas)

| Função | Comportamento |
|--------|---------------|
| `const ORDEM_ABAS` | Array hardcoded: ["hoje", "painel", "vida", "tarefas", "gastos", "construtora", "aviacao", "assistente"] |
| `showTab(name)` | Calcula direção (slideX), hidden/show, carrega dados (showTab(painel) → loadTasks, loadExpenses, etc) |
| `.tab-btn.addEventListener("click")` | Chama showTab com btn.dataset.tab |

**Resolução de Telas por Voz:** `static/js/voz-comando.js` (linhas 45–53)

| Aba | Sinônimos |
|-----|-----------|
| `hoje` | hoje, inicio, principal, home |
| `painel` | painel, resumo do dia, resumo |
| `vida` | vida, rotina, check-in, checkin, hiperfoco |
| `tarefas` | tarefa, afazer, pendencia |
| `gastos` | gasto, despesa, financ, meta, banco, extrato, conta |
| `construtora` | construtora, obra, empresa |
| `aviacao` | aviacao, voo, piloto |
| *(assistente não mapeado)* | — |

---

## PAINEL: CARDS DE CONFIGURAÇÃO/MENU

**No template `painel.html` (secões destacadas com **)**

| Card | Template | Função | Linhas |
|------|----------|--------|--------|
| **Custo de IA** | `custo-ia.html` | Mostra gasto IA deste mês, barra de progresso, tabela por função, **Modo teste de IA** (checkbox), **Exportar CSV** | 67 |
| **Devo sair?** | `devo-sair.html` | Integra com Viagem (aba Vida): status de saída, horário estimado | 43 |
| Resumo | `resumo.html` | Resumo do dia (cache local) | 9 |
| Agend. de Hoje | `agenda-de-hoje.html` | Calendário | 15 |
| Fechamento | `fechamento.html` | Encerramento reflexivo | 18 |
| Saúde Hoje | `saude-hoje.html` | Hidratação, ciclos | 36 |
| Peso e Medidas | `peso-e-medidas.html` | Gráfico de evolução | 56 |
| Plano do Dia | `plano-do-dia.html` | Plano estruturado | 13 |
| Datas Importantes | `datas-importantes.html` | Lembretes | 39 |
| Medicamentos | `medicamentos.html` | Próximas doses | 38 |
| Memória | `memoria.html` | Notas pessoais | 61 |
| Esp. Resposta | `esperando-resposta.html` | Itens em fila | 37 |
| Notas | `notas.html` | Notas rápidas | 21 |
| Diário Decisão | `diario-de-decisao.html` | Decisões | 32 |
| Brain Dump | `brain-dump.html` | Dump → Assistente | 25 |

**NÃO há cards de "Exportar Geral", "Backup", ou "Sair/Logout"** dentro de Painel. Estes podem estar em menu global ou não implementados.

---

## TESTES COM REFERÊNCIA A ABAS/NAVEGAÇÃO

| Arquivo de teste | Ocorrências | Contexto |
|------------------|-------------|---------|
| `test_fase7_c2_visual.py` | 3 | Testes visuais de navegação |
| `test_fase7_estrutura_frontend.py` | 1 | Estrutura HTML/CSS |
| `test_fase9_c1_tokens.py` | 4 | Tokenização e abas |
| `test_fase9_ui.py` | 4 | Testes de UI/abas |

Total: 4 arquivos de teste, 12 ocorrências agregadas

---

## RISCOS DE ACOPLAMENTO (5 principais)

1. **Hoje ↔ Assistente (caixa dinâmica):** Hoje injeta `<div id="caixa-assistente"></div>` na linha 7 do template, mas a caixa de chat é renderizada dinamicamente por `chat.js` chamando `/api/chat/historico`. Ao consolidar Hoje+Assistente, risco de duplicação de renderização ou competição de event listeners no mesmo DOM.

2. **Painel carregar dados de TODAS as abas:** showTab("painel") chama 12+ funções de load (loadTasks, loadExpenses, loadMetas, loadBancos, etc). Isso acoplá-a tightly. Se uma aba falhar, Painel fica incompleto. Consolidação deve separá-lo em blocos lazy-load, não eager.

3. **Vida (20 seções) é um monolito:** Div.vida-secoes tem 20 includes muito acopladas (habitos → pessoas → treino → viagens → lugares são todas interdependentes via localStorage/arrays compartilhados). Qualquer refactor de uma afeta as outras.

4. **Gastos ↔ Construtora (financeiro):** Ambas chamam /api/ia/custo e /api/ia/teto, indicando compartilhamento de contexto de custos. Gastos também chama /api/metas (Painel). Consolidação em "Finanças" deve respeitar esse acoplamento.

5. **Aviação usa /api/viagem/quando-sair (Vida):** Registrar-voo.js e Painel/devo-sair.js ambos chamam a mesma rota de viagem. Consolidar Aviação em Vida resolve isso, mas cria novo acoplamento: dois contextos (aviação + vida pessoal) no mesmo espaço visual.

---

## RESUMO FINAL

- **8 abas mapeadas** (Hoje, Painel, Vida, Tarefas, Gastos, Construtora, Aviação, Assistente)
- **Documento:** `/home/user/painel-pessoal-tdah/docs/fase9-mapa-abas.md`  
- **Linhas:** 489
- **Chamadas bash usadas:** 8 (grep, find, wc, cat)
- **Riscos principais:** Hoje↔Assistente injeção DOM; Painel eager-load de 12 abas; Vida=20-seção monolito; Gastos↔Construtora financeiro compartilhado; Aviação↔Vida viagem acoplada

