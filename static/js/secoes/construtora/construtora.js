// static/js/secoes/construtora/construtora.js - Secao construtora > construtora (HTML: templates/secoes/construtora/construtora.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 3216-3245.
// Fase 7 (faixa v6-financas): card com 2 stats + tempo ate a proxima conta.
// Decisao do Alex (docs/contrato-api-construtora.md, faixa A10): o painel
// mostra SO gastos, entradas e tempo ate a proxima conta a pagar - nunca
// lucro, margem nem VGV. A rota `/api/construtora/resumo` (app.py, fora desta
// faixa) ainda devolve lucro_liquido/margem no JSON; aqui so tot_entradas e
// tot_saidas sao lidos (lista branca), o resto e descartado na hora.
// Fase 7 (faixa C3c): estado de erro de verdade (antes o "Carregando..."
// ficava pra sempre quando a rota respondia 502/500 ou JSON invalido) e guarda
// contra NaN/undefined.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

function rotuloProximaConta(contas) {
  const comDias = contas.filter((c) => numeroFinancas(c.dias_ate_vencer) !== null);
  if (comDias.length === 0) return "Nenhuma conta em aberto nos proximos 30 dias.";
  const proxima = comDias.reduce((m, c) => (Number(c.dias_ate_vencer) < Number(m.dias_ate_vencer) ? c : m));
  const dias = Number(proxima.dias_ate_vencer);
  if (dias < 0) return `Proxima conta venceu ha ${Math.abs(dias)} dia(s).`;
  if (dias === 0) return "Proxima conta vence hoje.";
  if (dias === 1) return "Proxima conta vence amanha.";
  return `Proxima conta em ${dias} dias.`;
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
  listaContas.hidden = true;
  $("#contas-a-vencer-vazio").hidden = true;

  const data = await apiFetch("/api/construtora/resumo");
  info.classList.remove("carregando");
  if (!data || typeof data !== "object") {
    info.textContent = "Nao consegui falar com a construtora agora. Tenta de novo daqui a pouco.";
    return;
  }
  if (!data.configurado) {
    info.textContent = "Ainda nao conectado a API da construtora.";
    return;
  }
  if (data.erro) {
    info.textContent = String(data.erro);
    return;
  }

  // Lista branca: so estes dois campos do resumo sao usados (nunca lucro/margem/VGV).
  const d = data.dados && typeof data.dados === "object" ? data.dados : {};
  const entradas = numeroFinancas(d.tot_entradas);
  const gastos = numeroFinancas(d.tot_saidas);
  const contas = Array.isArray(data.contas) ? data.contas.filter((c) => c && typeof c === "object") : [];

  if (entradas === null && gastos === null && contas.length === 0) {
    info.textContent = "A construtora respondeu sem dado utilizavel agora.";
    return;
  }

  info.hidden = true;
  card.hidden = false;
  $("#construtora-entradas").textContent = fmtMoedaFinancas(entradas);
  $("#construtora-saidas").textContent = fmtMoedaFinancas(gastos);
  $("#construtora-proxima-conta-texto").textContent = rotuloProximaConta(contas);

  $("#contas-a-vencer-vazio").hidden = contas.length > 0;
  listaContas.hidden = contas.length === 0;
  contas.forEach((c) => listaContas.appendChild(criarItemContaAVencer(c)));
}

// Fase 9 C-abas: esta secao so carregava via navegacao.js (`if (name === "construtora")`),
// gatilho que sumiu com a aba Construtora. Agora mora dentro de #tab-gastos (Financas) -
// carrega quando a tab-btn "gastos" e clicada.
if (typeof document !== "undefined") {
  const btnAbaGastosConstrutora = document.querySelector('.tab-btn[data-tab="gastos"]');
  if (btnAbaGastosConstrutora) {
    btnAbaGastosConstrutora.addEventListener("click", loadConstrutora);
  }
}
