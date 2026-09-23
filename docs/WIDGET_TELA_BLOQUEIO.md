# Widget de tela de bloqueio (iOS, via Scriptable)

Fase 5 (US-C1). Reaproveita o mesmo endpoint do widget de tela inicial
(`GET /api/atalho/resumo`, token-gated, sem IA - so leitura rapida do banco),
so que agora ele tambem devolve dois campos pensados especificamente pro
espaco minimo da tela de bloqueio:

- `resumo_curto`: uma linha so (ex: `"3 tarefas · R$ 45,00 hoje"`), pro
  formato `accessoryInline` (que so cabe uma linha) e como primeira linha do
  `accessoryRectangular`.
- `linha_extra`: o proximo compromisso do dia (ex: `"14:30 dentista"`), ou
  `null` se nao houver nenhum - segunda linha do `accessoryRectangular`.

Os campos que ja existiam (`tarefas_pendentes`, `gasto_hoje`,
`proximo_titulo`, `proximo_hora`) continuam do jeito que estavam, usados pelo
widget de tela inicial (`scriptable/widget_painel.js`).

## Por que um script separado do widget de tela inicial

O widget de tela de bloqueio do iOS (16+) usa familias diferentes
(`accessoryInline`, `accessoryCircular`, `accessoryRectangular`) que o
sistema sempre renderiza **monocromatico** - definir cor de texto/fundo
customizada (como o `widget_painel.js` faz, com a paleta do app) e ignorado
ou fica errado nesses slots. Por isso o script de tela de bloqueio
(`scriptable/widget_lockscreen.js`) e um arquivo a parte, sem nenhuma cor
customizada, so texto.

## Como configurar

1. Instala o **Scriptable** (App Store, gratis), se ainda nao tiver.
2. Abre o Scriptable, cria um script novo, cola o conteudo de
   `scriptable/widget_lockscreen.js` inteiro.
3. Edita as duas constantes no topo do script:
   - `PAINEL_URL`: endereco do painel (ex: `http://192.168.1.10:5001`)
   - `TOKEN`: o valor de `PAINEL_ATALHOS_TOKEN` do `.env`, se tiver
     configurado (ver secao abaixo)
4. Roda o script uma vez dentro do proprio Scriptable pra testar (mostra uma
   previa no formato retangular).
5. Na **tela de bloqueio** do iPhone: segura o dedo na tela -> **Personalizar**
   -> toca num dos widgets abaixo do relogio -> **+** -> procura
   **Scriptable** -> escolhe o tamanho:
   - **Retangular** (mais comum): mostra `resumo_curto` + `linha_extra` (2
     linhas)
   - **Circular**: mostra so o numero de tarefas pendentes
   - **Em linha** (`accessoryInline`, ao lado da data): mostra so
     `resumo_curto`
6. Na configuracao do widget que aparece, escolhe o script que voce colou no
   passo 2.

O iOS decide sozinho o intervalo de atualizacao do widget (o Scriptable nao
controla isso) - normal levar alguns minutos pra refletir uma mudanca.

## Protegendo o endpoint (opcional)

Mesma logica de todos os outros endpoints `/api/atalho/*`: sem
`PAINEL_ATALHOS_TOKEN` configurado no `.env`, o endpoint fica aberto
(tranquilo numa rede local). Configurando essa variavel, tanto este widget
quanto o de tela inicial (`widget_painel.js`) precisam mandar o mesmo valor
no header `X-Webhook-Token` (a constante `TOKEN` no topo do script).

## Testes

Cobertos em `tests/test_app.py` (`test_atalho_resumo_traz_campos_compactos_pra_widget_de_tela_de_bloqueio`,
`test_atalho_resumo_linha_extra_traz_proximo_compromisso`) e em
`tests/test_vida.py` (`ResumoCurtoLockscreenTestCase`, a funcao pura que
monta o texto de uma linha).
