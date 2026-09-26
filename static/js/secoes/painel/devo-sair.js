// static/js/secoes/painel/devo-sair.js - Secao painel > devo-sair (HTML: templates/secoes/painel/devo-sair.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 3998-4056, app.js 4285-4291.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

$("#viagem-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#viagem-btn");
  const saida = $("#viagem-resultado");
  const chegarInput = $("#viagem-chegar").value;
  if (!chegarInput) return;

  setBotaoCarregando(btn, true, "Calculando...");
  saida.hidden = true;

  const data = await apiFetch("/api/viagem/quando-sair", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      origem: $("#viagem-origem").value.trim(),
      destino: $("#viagem-destino").value.trim(),
      chegar_ate: chegarInput,
    }),
  });

  setBotaoCarregando(btn, false, "Calcular");
  if (!data) return;

  const sairEm = new Date(data.sair_ate);
  const horaTxt = sairEm.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  const destino = $("#viagem-destino").value.trim();

  // Mesmo card de resultado usado no chat (tarefa/gasto/meta) - pedido do
  // Alex ("achei muito simples") era so de apresentacao, o calculo em si
  // (Google Maps, transito real) ja estava certo.
  saida.innerHTML = "";
  const eyebrow = document.createElement("div");
  eyebrow.className = "card-resultado-eyebrow";
  eyebrow.innerHTML = `${ICONE_VIAGEM_CARD}<span>Pra ${destino}</span>`;
  saida.appendChild(eyebrow);

  const valor = document.createElement("p");
  valor.className = "card-resultado-valor";
  valor.textContent = `Saia até as ${horaTxt}`;
  saida.appendChild(valor);

  const detalhe = document.createElement("p");
  detalhe.className = "card-resultado-detalhe";
  detalhe.textContent =
    `${data.duracao_minutos}min de viagem - ${data.distancia_km}km - ` +
    `${data.margem_minutos}min de margem`;
  saida.appendChild(detalhe);

  saida.hidden = false;
  const wazeLink = $("#viagem-waze");
  wazeLink.href = `https://waze.com/ul?q=${encodeURIComponent(destino)}&navigate=yes`;
  wazeLink.hidden = false;

  const uberLink = $("#viagem-uber");
  uberLink.href = `https://m.uber.com/ul/?action=setPickup&pickup=my_location&dropoff[formatted_address]=${encodeURIComponent(destino)}`;
  uberLink.hidden = false;
  $("#viagem-uber-dica").hidden = false;
});

async function initViagemOrigemPadrao() {
  const status = await apiFetch("/api/viagem/status");
  if (status && status.origem_padrao) {
    $("#viagem-origem").placeholder = `De onde? (padrao: ${status.origem_padrao})`;
  }
}
