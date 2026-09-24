### Fase 7 - faixa V0b (componente de botão)

- **`static/css/ui/componentes/botao.css`**: `.btn` base + `.btn-primario`,
  `.btn-secundario`, `.btn-perigo`, `.btn-fab` (com variante `.btn-fab--mais`) e
  `.btn-adicionar` (com variante `.btn-adicionar--pilula`) - o botão único, grande
  (altura mínima 48px, 100% de largura no contexto de seção por padrão) que substitui os
  botões "adicionar" azuis e pequenos espalhados pelas seções. Reaproveita só cor que já
  existe no app (`--accent`/`--accent-text`/`--danger`/`--surface-*`/`--border*`), nenhuma
  cor nova. Ícone "+" sem emoji: pseudo-elemento com duas barras em `background-image`
  (badge do `.btn-adicionar`) e CSS mask com SVG inline (`.btn-fab--mais`). Estados
  `disabled` e `is-carregando` (spinner via `::after`, some o texto), `:focus-visible`
  com anel próprio (nunca o azul padrão do navegador). Área de toque ≥44px. Tokens de
  forma da V0a (`--raio`, `--espaco-*`, `--elevacao-*`, `--borda-sutil`,
  `--superficie-2/3`) ainda não existem em `tokens.css` nesta integração - usados como
  `var(--token-v0a, fallback-encadeado-no-token-que-já-existe)`, resolvem sozinhos quando
  a V0a entrar. Durações/easings 100% reaproveitados de `style.css` (nenhum timing novo).
- Dois bugs de CSS achados e corrigidos durante a verificação (detalhes em
  `scripts/ralph-v0b-botoes/APRENDIZADOS.md`): um comentário com notação de wildcard em
  prosa continha "asterisco seguido de barra" no meio do texto, o que fecha um comentário
  CSS ali mesmo e derrubou a regra `:root` (e o ícone) do CSSOM; e um empate de
  especificidade fazia o anel de foco e o estado "carregando" perderem pra cada variante
  por ordem no arquivo (corrigido movendo as duas seções pro final do arquivo).
- Inventário (não editado nesta faixa) de todos os botões "adicionar/criar/+novo" atuais
  em `templates/secoes/` - lista completa em `scripts/ralph-v0b-botoes/progress.txt`, pra
  as faixas V3-V6 trocarem pelos `.btn-adicionar`.
- Verificação: `scripts/ralph-v0b-botoes/servidor.py` + `verificar.py` (Playwright
  390x844, banco de teste, botão de cada tipo injetado em `#tab-hoje` já existente no
  app) - zero erro de console, todos os botões ≥44px, anel de foco confirmado.
