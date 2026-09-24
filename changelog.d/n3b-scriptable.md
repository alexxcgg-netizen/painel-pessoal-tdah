### Fase 7 - faixa N3b (widget via Scriptable, unificado nos 4 tamanhos)

- Novo `scriptable/scriptable-widget.js`: script único do app Scriptable
  (iOS) que cobre os 4 tamanhos via `config.widgetFamily` - `small`/`medium`
  na tela inicial, `accessoryCircular`/`accessoryRectangular` na tela de
  bloqueio (qualquer outra família cai no layout de `small`, nunca quebra).
  Busca em `GET /api/widget` (contrato fixo da faixa N3a: `versao`,
  `atualizado_em`, `estado` normal/vazio/erro, `foco`, `proxima_conta`,
  `habitos`, `custo_ia`, `linhas` - sem valor em R$), token por
  `Authorization: Bearer` via constante no topo do script **ou** parâmetro
  do widget (`URL|TOKEN`, sobrescreve as constantes). Guarda o último JSON
  bom em `FileManager`; se a busca seguinte falhar (rede, timeout, HTTP
  ≥400, payload malformado), mostra os dados salvos com "atualizado há X"
  (min/h/d) em vez de deixar o widget vazio - só mostra "sem conexão" se não
  houver cache nenhum ainda. Tema escuro com as cores reais do app
  (`static/css/style.css`: `--bg`, `--surface`, `--text`, `--text-muted`,
  `--text-faint`, `--cor-painel` como destaque, `--danger` pro estado de
  erro); tela de bloqueio nunca leva cor customizada (o iOS renderiza
  monocromático nesses slots, mesma regra já usada em `widget_lockscreen.js`
  irmão). Os scripts antigos `scriptable/widget_painel.js` e
  `scriptable/widget_lockscreen.js` (que leem `/api/atalho/resumo`)
  continuam no repo só como referência histórica, não foram editados.
- Novo `tests/js/scriptable_widget.test.js` (`node --test`, 28 casos): roda
  o script **real** contra uma simulação em Node de toda a API do
  Scriptable usada aqui (`Request`, `ListWidget`/stacks/texto, `FileManager`
  em memória, `config`, `Script`, `Color`, `Font`, `args`) - cobre os 4
  tamanhos, os 3 estados (normal/vazio/erro), família desconhecida caindo
  no fallback, resolução de URL/token (constante vs parâmetro do widget),
  formatação de "atualizado há X" (agora/min/h/d + data inválida) e o
  fallback de cache (busca ok grava → busca seguinte falha, inclusive com
  status HTTP de erro → usa o cache salvo com o rótulo "atualizado").
  Nenhuma chamada de rede real.
- Novo `docs/widget-scriptable.md`: guia curto de instalação (passo a
  passo no app Scriptable, os dois formatos de widget, configuração por
  parâmetro do widget, contrato do endpoint, o que cada tamanho mostra, a
  paleta de cores usada e como funciona o cache/fallback).
- Nota de escopo: o endpoint `GET /api/widget` em si (rota Flask/cálculo do
  JSON, faixa N3a) não faz parte desta faixa - só o cliente Scriptable que
  consome o contrato já fixado no prompt da tarefa.
