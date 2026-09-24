### Fase 7 - faixa V2 (aba Painel)

- Secoes recolhiveis (pedido do Alex, contrato V0c): `templates/secoes/painel/memoria.html`
  virou duas `<section class="secao-recolhivel" data-aberto="false">` - "O que eu lembro
  sobre voce" (Sua rotina + Seus planos) e "Fora do painel, outras coisas que anotei"
  (grupo fixo `fora_do_painel` + lista generica) - comecam fechadas, guardam estado por
  `data-secao-id` em `localStorage` (comportamento de `static/js/ui/secao-recolhivel.js`,
  faixa V0c, nao alterado aqui).
- Acabamento com profundidade: `resumo`, `agenda-de-hoje`, `fechamento`, `saude-hoje`,
  `plano-do-dia`, `devo-sair`, `datas-importantes`, `medicamentos`, `esperando-resposta`,
  `notas`, `diario-de-decisao` e `custo-ia` (nova) envolvidas em `<div class="card
  painel-secao-card">` (contrato V0c) no lugar do separador plano antigo
  (`.secao-secundaria`, so uma borda no topo). `static/css/secoes/painel.css` acrescenta
  uma faixa fina de 3px no topo de cada card com a cor de identidade da propria secao
  (`--secao-cor`, ja existia por secao) e o mesmo acento no icone das secoes recolhiveis -
  zero cor/fonte/animacao nova, so os tokens de forma/profundidade (V0a) com fallback.
- Card novo "Custo de IA" (`painel/custo-ia`): gasto do mes em R$, por funcao (tabela),
  projecao ate o fim do mes, % do teto (barra reaproveitando `.meta-progresso` que ja
  existia), grafico de barras (`desenharGraficoBarras`, `static/js/charts.js`) e exportar
  CSV. Backend novo `rotas/v2_custo_ia.py` (`GET /api/ia/uso/resumo`,
  `GET /api/ia/uso.csv`, le a tabela hibrida `uso_ia`) - reaproveita
  `ia.medicao`/`ia.teto` pro cambio/teto/nivel de alerta, nunca duplica esse calculo; o
  endpoint antigo `/api/ia/custo` (Anthropic-only, `api_usage`) continua existindo sem
  mudanca, serve outro card. `tests/test_fase7_v2_custo_ia.py`: 26 testes, incluindo
  fuzzing de massa (70 cenarios: strings extremas/unicode/injecao SQL, numeros extremos,
  concorrencia, corte de mes) - 0 falhas.
- Pendencias pro integrador (arquivos compartilhados, nao editados aqui - ver
  `scripts/ralph-v2-painel/progress.txt` pro diff exato): incluir
  `static/js/secoes/painel/custo-ia.js` em `templates/scripts.html`,
  `static/css/secoes/painel/custo-ia.css` em `static/css/fase7.css`, chamar
  `loadCustoIAV2()` no `showTab("painel")` de `static/js/nucleo/navegacao.js`, e somar os
  2 arquivos novos + bump de `CACHE_NAME` em `static/service-worker.js`.
- Ultima historia: verificacao Playwright 390x844 (`scripts/ralph-v2-painel/`) - secoes de
  memoria comecam fechadas, abrem/fecham por clique real (`aria-expanded`/`data-aberto`),
  card de Custo de IA renderiza gasto/tabela/grafico/exportar, CSV responde 200, zero erro
  de console/rede (fora falhas de ambiente ja conhecidas de outras faixas).
