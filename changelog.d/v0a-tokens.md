### Fase 7 - faixa V0a (tokens de forma/profundidade + MASTER.md)

- **`static/css/ui/tokens.css`**: tokens de forma e profundidade para as faixas V, sem
  mudar cor, fonte nem animação (decisão do Alex). Tudo é derivado das variáveis que já
  existem no `:root` do `style.css`: raios (`--raio-xs/-sm/--raio/-lg/-pilula`, reaproveitando
  20px/14px), espaço em grade de 8px (`--espaco-1..6`), superfícies em camadas
  (`--superficie-1..3`, `--realce-superficie`, véus de hover/pressionado/fundo), bordas
  (`--linha`, `--borda-sutil/-forte`), elevação em camadas finas (`--elevacao-0..3`),
  `--fonte-mono` (= `--font-tech`, IBM Plex Mono já carregada), movimento com as mesmas
  durações/curvas do app (`--transicao-rapida/-media/-lenta/-pressionar`), toque
  (`--toque-min` 44px, `--toque-confortavel` 48px), `--anel-foco` visível no preto e camadas
  de z-index para sheet/FAB. Com `prefers-reduced-motion` as durações zeram. Só há
  variáveis no `:root` e nenhum seletor visual, então a tela não muda (conferido por diff de
  pixel no Playwright 390x844, Hoje e Vida).
- **`docs/MASTER.md`**: o guia que V0b-V6 seguem. Traz os princípios, a paleta e a tipografia
  existentes documentadas, a tabela de tokens, receitas (card, card de destaque, lista-item,
  campo, chip, botões incluindo `.btn-adicionar`, seção recolhível, bottom-sheet), os estados
  (hover, pressionado, foco, desabilitado, vazio, erro), números em mono, ícones de traço,
  área de toque de 44px, pegadinhas do app e o checklist da faixa.
- **`scripts/ralph-v0a-tokens/`**: `servidor.py` (app num banco temporário) e `verificar.py`
  (Playwright 390x844: erros de console e de rede, e se os tokens resolvem), que servem de
  modelo para a verificação das próximas faixas V.
- **Para o integrador:** o `:focus-visible` global do `style.css` usa `--accent-2`
  (`#08080a`) e quase some no fundo preto. A sugestão é trocar por `box-shadow: var(--anel-foco)`.
