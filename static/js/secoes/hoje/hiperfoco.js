// static/js/secoes/hoje/hiperfoco.js - Secao hoje > hiperfoco (HTML: templates/secoes/hoje/hiperfoco.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 208-262.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

let hiperfocoAte = null;
let hiperfocoTimer = null;

function atualizarContagemHiperfoco() {
  if (!hiperfocoAte) return;
  const restanteMs = hiperfocoAte - Date.now();
  if (restanteMs <= 0) {
    renderHiperfoco({ ativo: false });
    return;
  }
  const min = Math.ceil(restanteMs / 60000);
  $("#hiperfoco-restante").textContent = `faltam ${min} min`;
}

function renderHiperfoco(estado) {
  const ativo = Boolean(estado && estado.ativo);
  $("#hiperfoco-ativo").hidden = !ativo;
  $("#hiperfoco-inativo").hidden = ativo;
  document.body.classList.toggle("em-hiperfoco", ativo);
  clearInterval(hiperfocoTimer);
  // Conta a partir dos segundos restantes (vem do servidor) em vez de ler o
  // horario "ate" - o servidor pode estar em outro fuso que o celular.
  hiperfocoAte = ativo ? Date.now() + estado.segundos_restantes * 1000 : null;
  if (ativo) {
    atualizarContagemHiperfoco();
    hiperfocoTimer = setInterval(atualizarContagemHiperfoco, 30000);
  }
}

async function loadHiperfoco() {
  const estado = await apiFetch("/api/hiperfoco");
  if (estado) renderHiperfoco(estado);
}

document.querySelectorAll(".hiperfoco-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const estado = await apiFetch("/api/hiperfoco", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ minutos: Number(btn.dataset.minutos) }),
    });
    if (estado) {
      vibrar(20);
      renderHiperfoco(estado);
    }
  });
});

$("#hiperfoco-parar").addEventListener("click", async () => {
  const estado = await apiFetch("/api/hiperfoco", { method: "DELETE" });
  if (estado) renderHiperfoco(estado);
});

// ---- Pessoas ----
