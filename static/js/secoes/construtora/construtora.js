// static/js/secoes/construtora/construtora.js - Secao construtora > construtora (HTML: templates/secoes/construtora/construtora.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 3216-3245.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadConstrutora() {
  const info = $("#construtora-info");
  const listaContas = $("#lista-contas-a-vencer");
  info.classList.add("carregando");
  info.textContent = "Carregando...";
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
  info.textContent =
    `Entradas ${fmtMoeda(d.tot_entradas)} · Saidas ${fmtMoeda(d.tot_saidas)} · ` +
    `Lucro liquido ${fmtMoeda(d.lucro_liquido)} (margem ${d.margem.toFixed(1)}%)`;

  const contas = data.contas || [];
  $("#contas-a-vencer-vazio").hidden = contas.length > 0;
  contas.forEach((c) => listaContas.appendChild(criarItemContaAVencer(c)));
}
