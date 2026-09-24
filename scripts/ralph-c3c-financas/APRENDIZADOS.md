# Aprendizados - faixa c3c-financas

1. **CSS provisório de sheet brigando com o componente real.** O visual do sheet
   da V6 (`.bottom-sheet-financas` com `position: fixed`, padding, borda e
   `max-height`) foi escrito antes da V0d existir. Quando a V0d montou
   `.bottom-sheet > .bottom-sheet-fundo + .bottom-sheet-painel`, a moldura
   passou a ter o visual do painel e o painel real saiu 90px acima da tela.
   Ao adotar um componente, apague o CSS provisório em vez de deixar os dois
   convivendo.

2. **`input type=number` e o formato pt-BR não combinam.** No Chromium com
   locale en-US, `21,90` num `type=number` vira `value=""` com `badInput`. O
   JS lê string vazia e a mensagem diz "valor obrigatório" para quem digitou
   um valor. Para dinheiro, use `type=text inputmode=decimal` e faça o parse
   próprio (`lerValorFinancas`).

3. **Bug da N1 que corrompe o banco (fora desta faixa).** `POST
   /api/financas/parcelas` com `primeira_parcela` inválida devolve 400, mas
   o INSERT já foi feito. A partir daí, `GET /parcelas` e `/comprometido`
   dão 500 em toda carga. Achei isso no fuzz pela API. A UI desta faixa
   barra antes (data entre 2000 e 2100), mas a correção certa é validar
   antes do INSERT. Também zerou o banco de teste: reinicie o `servidor.py`
   depois de qualquer fuzz direto na API.

4. **V0d: reabrir durante a animação de fechar escondia o sheet.** O
   `setTimeout` do fechamento disparava depois da reabertura e punha
   `hidden`. A C2 corrigiu no `bottom-sheet.js`, e depois do merge o fuzz
   passou. Não contornei localmente.

5. **O auditor de toque precisa entender `::after`.** A receita do Chip no
   MASTER completa os 44px com um `::after` invisível, e o
   `getBoundingClientRect` não enxerga isso. O `auditar.py` soma o
   `top/bottom` negativos do `::after` absoluto. Sem esse ajuste, o chip
   aparece como falso positivo.

6. **O fundo em degradê engana a medição de contraste.** O
   `.badge-sucesso` (texto escuro sobre degradê claro) aparece com 1,2:1 no
   auditor, porque ele só lê `background-color`. É falso positivo, conferido
   no screenshot.

7. **Na API síncrona do Playwright, `page.route` só responde durante uma
   chamada ao Playwright.** Com `time.sleep` no roteiro, a resposta forçada
   fica parada e a tela mostra "Carregando..." (falso positivo). Use
   `page.wait_for_timeout`.

8. **O proxy de saída do sandbox escuta em loopback (`127.0.0.1:40971`).** Uma
   guarda de socket do tipo "só loopback" deixa passar tudo o que vai pelo
   proxy. O `servidor.py` tira as variáveis `*_proxy` e bloqueia também a
   porta do proxy. Todo `connect` bloqueado aparece como `BLOQUEADO` no log.

9. **Sheet do componente volta para dentro da aba ao fechar (portal da C2).**
   Então campos de um sheet fechado entram na varredura da aba. O fuzz
   ignora `input` dentro de `.bottom-sheet`, porque ali está o texto que o
   próprio fuzz digitou.
