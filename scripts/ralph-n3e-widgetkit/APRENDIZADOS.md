# Aprendizados — faixa n3e-widgetkit (Fase 7)

- **`/api/widget` (Authorization: Bearer) ainda não existe** nesta integração — o único
  endpoint de widget hoje é `/api/atalho/resumo` (token via `X-Webhook-Token`, campos
  diferentes: `tarefas_pendentes`, `gasto_hoje`, `proximo_titulo`, `proximo_hora`,
  `resumo_curto`, `linha_extra`). Quem for implementar essa rota deve conferir se o
  contrato do prompt desta faixa (campos `foco`/`proxima_conta`/`habitos`/`custo_ia`/
  `linhas`, ver `native/widgetkit/README.md`) já bate com algo que outra faixa fez, pra não
  duplicar/divergir.
- **Cores das famílias de tela de bloqueio são sempre monocromáticas** — o iOS ignora cor
  customizada em `accessoryCircular`/`accessoryRectangular`/`accessoryInline` (mesma
  descoberta já documentada em `docs/WIDGET_TELA_BLOQUEIO.md` pro widget Scriptable
  irmão). `PainelWidget.swift` já nasceu respeitando isso — essas 3 views usam só
  `.primary`/`.secondary`, nunca a paleta custom.
- **`.containerBackground(for: .widget)` é obrigatório a partir do iOS 17** pro fundo do
  widget (WidgetKit rejeita/ignora `.background` puro nessa versão); em iOS 16 (onde os
  `accessory*` de tela de bloqueio já existem) o `.background` comum ainda funciona. O
  helper `fundoDoWidget(_:)` em `PainelWidget.swift` cobre os dois com `#available`.
- **App Group é a única ponte entre o app principal (PWABuilder) e a extensão de widget** —
  não dá pra hardcodar URL/token no Swift do widget porque o Alex pode trocar de rede ou
  girar o token sem recompilar; por isso `Config.swift` lê tudo de
  `UserDefaults(suiteName: appGroupID)` em vez de constantes.
- **Nada disso foi compilado** (sem Mac/Xcode neste ambiente) — tratar como ponto de partida
  revisado por leitura, não como código validado. Ver seção final do README com os pontos
  mais prováveis de precisar ajuste na primeira compilação.
