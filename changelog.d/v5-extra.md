### Fase 7 - faixa V5-extra (Viagens, Lugares, Cotações, Aviação)

- **Botão "adicionar" grande + bottom-sheet** nas 3 seções com formulário de
  criação pequeno: Vida > Viagens ("Nova viagem"), Vida > Lugares ("Novo
  lugar") e Construtora > Cotações ("Nova cotação") — trocam o antigo botão
  de submit sem estilo (aparência crua do navegador) pelo contrato
  `.btn-adicionar` + `.bottom-sheet`. Mesmas rotas de sempre; fecha e
  recarrega a lista ao salvar. Chama `abrirBottomSheet`/`fecharBottomSheet`
  (V0d, `static/js/ui/bottom-sheet.js`) com fallback local só-`[hidden]`
  enquanto essa faixa não chega na integração — cede lugar sozinho assim
  que a implementação real existir.
- **Acabamento de profundidade na aba Aviação** sem trocar cor/fonte/
  animação (reaproveita `--glass-*`, `--cor-aviacao(-fill)`,
  `--shadow-card`): título de aba novo em `templates/abas/aviacao.html`
  (única aba sem `<h2>` próprio até então); formulários de Registrar voo e
  METAR/TAF ganharam moldura "glass"; botões "Registrar" e "Consultar"
  (antes `<button>` cru) viraram CTA cheio na cor da aba.
- **Cotações**: grade sutil (reaproveita `.grafico-grid`) no gráfico de
  comparação de fornecedores; botão "+ Adicionar" e label de upload de PDF
  (antes crus) ganharam contorno. **Lugares**: sombra "glass" no mapa
  Leaflet só depois de carregado — SRI e popup via `textContent`
  (revisão da Fase 6) intocados.
- Testes do próprio módulo 100% verdes (`test_fase7_estrutura_frontend`,
  `test_fase6_f3_{viagens,lugares_mapa,cotacoes_grafico}`, `test_voos`,
  `test_metar`, `test_vida_{fase2,fase3,revisao}`, `test_fase6_{e2_modulos,
  e4_chat,revisao_seguranca}`, `test_notificacoes`, `test_app`); Playwright
  390x844 na última história (ver `scripts/ralph-v5-extra/`).
