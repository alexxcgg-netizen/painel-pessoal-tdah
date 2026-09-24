// static/js/secoes/painel/plano-do-dia.js - Secao painel > plano-do-dia (HTML: templates/secoes/painel/plano-do-dia.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 3983-3997.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

$("#plano-btn").addEventListener("click", async () => {
  const btn = $("#plano-btn");
  const saida = $("#plano-texto");
  setBotaoCarregando(btn, true, "Pensando...");
  saida.hidden = true;

  const data = await apiFetch("/api/plano-do-dia", { method: "POST" });

  setBotaoCarregando(btn, false, "Gerar plano do dia");
  loadUso();
  if (!data) return;
  saida.textContent = data.plano;
  saida.hidden = false;
});
