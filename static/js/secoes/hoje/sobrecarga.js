// static/js/secoes/hoje/sobrecarga.js - Secao hoje > sobrecarga (HTML: templates/secoes/hoje/sobrecarga.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 1756-1770.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

const SINAL_TEXTO = { "tarefas atrasadas": "tarefas atrasadas", "sono ruim": "sono ruim seguido", "semana pesada": "semana cheia pela frente" };

async function loadSobrecarga() {
  const data = await apiFetch("/api/sobrecarga");
  if (!data) return;
  const box = $("#sobrecarga-box");
  box.hidden = !data.sobrecarregado;
  if (!data.sobrecarregado) return;
  $("#sobrecarga-pontuacao").textContent = `${data.pontuacao}/3 sinais`;
  const lista = data.sinais.map((s) => SINAL_TEXTO[s] || s).join(", ");
  $("#sobrecarga-texto").textContent = `Vários sinais juntos: ${lista}. Talvez valha desacelerar hoje.`;
}

// ---- Fase 5 (US-C21): previa da noite anterior ----
