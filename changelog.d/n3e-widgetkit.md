## Fase 7 (N3e) - base do widget nativo iOS (WidgetKit), preparado mas não compilado

Sem Mac/Xcode neste ambiente — código escrito e revisado por leitura, pronto pra alguém com
Mac abrir, compilar e testar. Não altera nenhum comportamento do painel web/backend.

- **`native/widgetkit/PainelWidget.swift`**: modelo `Codable` do contrato JSON de
  `GET /api/widget` (`Authorization: Bearer`), `TimelineProvider` com refresh a cada ~20 min
  e fallback pro último dado bom guardado em App Group quando a rede falha, views SwiftUI
  pras 5 famílias (`systemSmall`, `systemMedium`, `accessoryCircular`,
  `accessoryRectangular`, `accessoryInline`) e estados `normal`/`vazio`/`erro`.
- **`native/widgetkit/PainelWidgetBundle.swift`**: ponto de entrada `@main` da extensão.
- **`native/widgetkit/Config.swift`**: URL e token lidos de `UserDefaults` do App Group
  (nunca hardcoded) + cache do último payload.
- **`native/widgetkit/README.md`**: passo a passo (gerar projeto Xcode via PWABuilder,
  adicionar Widget Extension, colar os arquivos, configurar App Group, instalar) e a lista
  do que exige Mac com Xcode + conta Apple Developer paga pra rodar fora do simulador. Deixa
  explícito que o código não foi compilado.
- Cores usadas no widget vêm do `:root` real de `static/css/style.css` (`--surface`,
  `--text`, `--text-muted`, `--text-faint`, `--cor-painel` como accent, `--danger`,
  `--border`) — nada inventado. Famílias de tela de bloqueio ficam monocromáticas (o iOS
  ignora cor customizada nesses slots, mesma nota já registrada em
  `docs/WIDGET_TELA_BLOQUEIO.md` pro widget Scriptable irmão).
- Nota de escopo: o endpoint `GET /api/widget` em si (rota Flask/cálculo do JSON) não faz
  parte desta faixa — só o cliente Swift que consome o contrato dado no prompt da tarefa.
