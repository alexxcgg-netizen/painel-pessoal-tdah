# Aprendizados - faixa v6-financas

1. **API da faixa N1 (assinaturas/parcelas) ainda nao esta em `fase7/integracao`
   nem em origin** - so existe (sem commit) no worktree
   `/home/user/painel-pessoal-tdah-fase7-n1-assinaturas`. `docs/contrato-assinaturas.md`
   tambem ainda nao existe. Li o codigo de la direto (`rotas/n1_financas.py` +
   `financas_recorrentes.py`) em vez de supor o formato - contrato real:
   - `GET /api/financas/assinaturas?ativas=1` -> `{assinaturas: [...]}`
   - `GET/POST/PATCH /api/financas/assinaturas/<id>`, `POST .../cancelar`, `DELETE`
   - `GET /api/financas/parcelas?em_andamento=1` -> `{parcelas: [...]}`
   - `GET/POST/DELETE /api/financas/parcelas/<id>`
   - `GET /api/financas/comprometido` -> `{total_mensal, proximas_cobrancas, impacto_limite_cartao}`
   Enquanto N1 nao entra na integracao, toda chamada da minha secao devolve
   404 e a tela cai nos estados vazio/erro (o banner de erro padrao do app,
   via `apiFetch` - nao reinventei outro mecanismo).

2. **"Mini grafico Chart.js" (pedido do prompt) x realidade do app**: o app
   NAO carrega Chart.js nem nenhuma lib externa via CDN - ja tem uma
   biblioteca propria de grafico SVG (`static/js/charts.js`,
   `desenharGraficoBarras`/`desenharGraficoLinha`, sem dependencia externa,
   funciona offline). Colocar Chart.js de verdade exigiria `<script>` novo em
   `templates/scripts.html` + `static/service-worker.js` (arquivos do
   integrador, fora da minha lista) e destoaria do padrao (nenhuma outra
   secao usa Chart.js). Usei `desenharGraficoBarras` pro "mini grafico" do
   limite comprometido por cartao nos proximos 6 meses
   (`assinaturas.js::desenharLimiteCartao`). Se Chart.js for mesmo exigido
   por algum motivo (ex: interatividade que o SVG proprio nao cobre), isso
   precisa de uma decisao do integrador, nao de uma faixa que so mexe nas
   proprias secoes.

3. **`.bottom-sheet` dentro de `.tab-content` fica preso errado**:
   `.tab-content:not([hidden])` ganha `animation ... both`
   (`static/css/style.css` ~L990) que deixa `transform: translateX(0)
   scale(1)` aplicado mesmo depois da animacao acabar - isso cria um bloco
   de posicionamento (containing block) novo pra qualquer descendente
   `position: fixed`, entao um bottom sheet nascido DENTRO da aba fica preso
   na base da propria `.tab-content` (que pode ser mais alta que a tela), nao
   na base da VIEWPORT como devia. Contornei subindo os `.bottom-sheet` pra
   `document.body` via JS uma vez, na carga do script (ver
   `static/js/secoes/gastos/assinaturas.js` e
   `static/js/secoes/vida/contas-pessoais.js`) - funciona hoje e continua
   funcionando quando a V0d substituir meu fallback por
   `abrirBottomSheet`/`fecharBottomSheet` de verdade (a API do contrato so
   se importa com o atributo `hidden`, nao com onde o elemento mora no DOM).
   Vale a pena `static/js/ui/bottom-sheet.js` (V0d) fazer esse reparent pra
   `document.body` centralizado, uma vez so, em vez de cada faixa reinventar
   a mesma correcao.

4. **Colisao de id encontrada e corrigida**: `templates/secoes/vida/ainda-usa.html`
   ja usava `id="assinaturas-box"` (a secao "Ainda usa?", que DETECTA
   recorrencia por historico - coisa diferente da assinatura DECLARADA da
   faixa N1). Minha secao nova ia nascer com o mesmo id no mesmo documento
   (as abas inteiras ficam todas no DOM, so uma fica visivel por vez) -
   renomeei a minha pra `id="assinaturas-financas-box"` antes de qualquer
   commit. Nao existe teste automatico que pegue id duplicado no HTML final;
   conferi na mao (`client.get("/")` + contar `id="..."` repetido). Pode
   valer a pena o integrador considerar um teste assim em
   `test_fase7_estrutura_frontend.py`.

5. **`construtora_cliente.py` (faixa A10)** ja tem uma API limpa
   (`gastos_do_mes`/`entradas_do_mes`/`proxima_conta`) que bate exatamente
   com o que este painel deveria mostrar, mas ainda **nao esta ligada** em
   `app.py` (nota no proprio docstring do arquivo - "ainda nao esta ligado a
   nada em app.py"). Como `app.py` nao e meu arquivo, nao fiz essa ligacao;
   em vez disso so **parei de mostrar** `lucro_liquido`/`margem` que a rota
   antiga (`/api/construtora/resumo`, ainda em uso) ja devolvia - certo pro
   Alex hoje (decisao dele, so gastos/entradas/tempo ate a proxima conta),
   mas o ideal e o integrador trocar essa rota pra usar
   `construtora_cliente.py` e o JSON ja sair enxuto do back tambem.
