# Faixa V2 (Painel) - aprendizados

- `.btn-com-icone` (style.css) so define layout (flex/gap) - o "cromo" visual de botao
  (fundo/padding/borda escuros) vem do `<button>` NATIVO por causa de `color-scheme: dark`
  no `:root` (Chromium aplica a UA stylesheet escura sozinho). Um `<a class="btn-com-icone">`
  (ex: link de download) NAO ganha esse cromo de graca - precisa de CSS proprio (ver
  `.custo-ia-exportar` em `static/css/secoes/painel/custo-ia.css`) ou virar `<button>` com
  JS. Mantive `<a href=... download>` (funciona sem JS, permite "salvar como").

- `ia.teto._teto_mensal_brl()`/`ia.medicao._limite_utc_inicio_mes()` sao privados (prefixo
  `_`) mas sao exatamente a fonte unica de calculo que a regra de ouro #2 pede pra
  reaproveitar (teto em BRL, corte de mes local->UTC) - importar e chamar direto (com
  comentario explicando o porque) bate menos risco de divergir do que reimplementar a
  mesma conta only pra evitar o underscore.

- V0a (tokens.css) e V0c (secao.css/card.css/...) ainda nao estavam em `fase7/integracao`
  no inicio desta faixa, mas chegaram no meio da sessao (`git fetch origin` + merge das 2
  branches, sem heavy conflict, so CHANGELOG.md com adicoes concorrentes). Vale sempre
  reconferir com `git fetch` antes de decidir "vou so simular o contrato sem visual real" -
  economizou boa parte do trabalho de verificacao.

- `templates/scripts.html`, `static/css/fase7.css`, `static/js/nucleo/navegacao.js` e
  `static/service-worker.js` sao do integrador (nao editar), mas pra rodar o Playwright de
  verdade uma secao NOVA (fora das que a Etapa 0 ja linkou) precisa aparecer neles. Pattern
  que funcionou: editar os 3 primeiros na mao so pro teste local, `git checkout --` neles
  depois de rodar o Playwright (fica registrado no progress.txt o diff exato), e deixar
  `static/service-worker.js` (bump de CACHE_NAME + ASSETS) so anotado, sem nem aplicar
  localmente (nao afeta o teste Playwright, que nao passa pelo Service Worker num
  browser context novo).
