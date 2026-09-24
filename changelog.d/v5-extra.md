### Fase 7 - faixa V5-extra (Viagens, Lugares, Cotações, Aviação)

- **Botão "adicionar" grande + bottom-sheet** nas 3 seções com formulário de
  criação pequeno: Vida > Viagens ("Nova viagem"), Vida > Lugares ("Novo
  lugar") e Construtora > Cotações ("Nova cotação") — trocam o antigo botão
  de submit sem estilo (aparência crua do navegador) pelo componente real
  `.btn.btn-adicionar` + `.campo` + `.btn.btn-primario`/`.btn.btn-secundario`
  (`ui/componentes/{botao,campo}.css`, já na integração). Mesmas rotas de
  sempre; fecha e recarrega a lista ao salvar, com botão "Cancelar" (mesmo
  padrão de `vida/habitos`). O painel em si (`.bottom-sheet`, sem componente
  compartilhado ainda — só `ui/js/bottom-sheet.js`, V0d) chama
  `abrirBottomSheet`/`fecharBottomSheet` quando existir, com fallback local
  só-`[hidden]`; o CSS do painel fica escopado por ID (nunca a classe
  `.bottom-sheet` pura), pra não regredir os bottom-sheet já integrados de
  outras seções quando a V0d chegar.
- **Acabamento de profundidade na aba Aviação** sem trocar cor/fonte/
  animação: título de aba novo em `templates/abas/aviacao.html` (única aba
  sem `<h2>` próprio até então); formulários de Registrar voo e METAR/TAF
  ganharam moldura "glass" (reaproveita `--glass-*`, já tingido por
  `--cor-aviacao` dentro de `#tab-aviacao`); botões "Registrar" e
  "Consultar" (antes `<button>` cru) agora usam o `.btn.btn-primario` real.
- **Cotações**: grade sutil (reaproveita `.grafico-grid`) no gráfico de
  comparação de fornecedores; botão "+ Adicionar" fornecedor usa
  `.btn.btn-secundario` real, label de upload de PDF (sem componente
  equivalente) ganhou contorno próprio. **Lugares**: sombra "glass" no mapa
  Leaflet só depois de carregado — SRI e popup via `textContent` (revisão
  da Fase 6) intocados.
- Testes do próprio módulo 100% verdes (`test_fase7_estrutura_frontend`,
  `test_fase6_f3_{viagens,lugares_mapa,cotacoes_grafico}`, `test_voos`,
  `test_metar`, `test_vida_{fase2,fase3,revisao}`, `test_fase6_{e2_modulos,
  e4_chat,revisao_seguranca}`, `test_notificacoes`, `test_app`); Playwright
  390x844 real na última história (cria viagem/lugar/voo/cotação com 2
  fornecedores pela UI, num banco de teste) — zero erro de console, 2
  screenshots em `scripts/ralph-v5-extra/` (não versionados).
