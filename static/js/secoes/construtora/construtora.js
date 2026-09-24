// static/js/secoes/construtora/construtora.js - Secao construtora > construtora (HTML: templates/secoes/construtora/construtora.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 3216-3245.
// Fase 7 (faixa v6-financas): acabamento (card com 2 stats + tempo ate a
// proxima conta) - a API `/api/construtora/resumo` (app.py, compartilhado,
// esta faixa nao edita) continua devolvendo tot_entradas/tot_saidas/
// lucro_liquido/margem, mas a decisao do Alex (docs/contrato-api-construtora.md,
// faixa A10) e o painel mostrar SO gastos, entradas e tempo ate a proxima
// conta a pagar - por isso lucro_liquido/margem nunca aparecem na tela,
// mesmo vindo no JSON. `construtora_cliente.py` (faixa A10) ja tem essa API
// enxuta pronta (gastos_do_mes/entradas_do_mes/proxima_conta) mas ainda nao
// esta ligada em app.py (nota em scripts/ralph-v6-financas/progress.txt).
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

function rotuloProximaConta(contas) {
  if (!contas || contas.length === 0) return "Nenhuma conta em aberto nos proximos 30 dias.";
  const proxima = contas.reduce((m, c) => (c.dias_ate_vencer < m.dias_ate_vencer ? c : m));
  if (proxima.dias_ate_vencer < 0) {
    return `Proxima conta venceu ha ${Math.abs(proxima.dias_ate_vencer)} dia(s).`;
  }
  if (proxima.dias_ate_vencer === 0) return "Proxima conta vence hoje.";
  return `Proxima conta em ${proxima.dias_ate_vencer} dia(s).`;
}

async function loadConstrutora() {
  const info = $("#construtora-info");
  const card = $("#construtora-card");
  const listaContas = $("#lista-contas-a-vencer");
  info.hidden = false;
  info.classList.add("carregando");
  info.textContent = "Carregando...";
  card.hidden = true;
  listaContas.innerHTML = "";
  $("#contas-a-vencer-vazio").hidden = true;

  const data = await apiFetch("/api/construtora/resumo");
  info.classList.remove("carregando");
  if (!data) return;
  if (!data.configurado) {
    info.textContent = "Ainda nao conectado a API da construtora.";
    return;
  }
  if (data.erro) {
    info.textContent = data.erro;
    return;
  }

  const d = data.dados;
  const contas = data.contas || [];

  info.hidden = true;
  card.hidden = false;
  $("#construtora-entradas").textContent = fmtMoeda(d.tot_entradas);
  $("#construtora-saidas").textContent = fmtMoeda(d.tot_saidas);
  $("#construtora-proxima-conta").textContent = rotuloProximaConta(contas);

  $("#contas-a-vencer-vazio").hidden = contas.length > 0;
  contas.forEach((c) => listaContas.appendChild(criarItemContaAVencer(c)));
}
