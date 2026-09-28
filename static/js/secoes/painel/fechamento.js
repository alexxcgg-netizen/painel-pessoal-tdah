// static/js/secoes/painel/fechamento.js - Secao painel > fechamento (HTML: templates/secoes/painel/fechamento.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 948-964.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadFechamentoDoDia() {
  const data = await apiFetch("/api/fechamento-do-dia");
  if (!data) return;

  const concluidasEl = $("#fechamento-concluidas");
  concluidasEl.textContent =
    data.concluidas.length > 0
      ? `Feito hoje: ${data.concluidas.join(", ")}.`
      : "Nada concluído hoje ainda.";

  const pendentesEl = $("#fechamento-pendentes");
  pendentesEl.textContent =
    data.pendentes_hoje.length > 0
      ? `Ainda fica pra depois: ${data.pendentes_hoje.join(", ")}.`
      : "Nada ficou pra tras hoje.";
}

// Botao "ouvir": frase curta da noite (/api/voz/frase) -> voz premium, que cai
// sozinha na voz do iPhone (falarPremium em nucleo/voz.js). Mesma regra dos
// outros .btn-ouvir: sem speechSynthesis o botao some.
const fechamentoOuvirBtn = $("#fechamento-ouvir");
if (fechamentoOuvirBtn) {
  if (!("speechSynthesis" in window)) {
    fechamentoOuvirBtn.hidden = true;
  } else {
    fechamentoOuvirBtn.addEventListener("click", async () => {
      if (vozTocando()) {
        pararVoz();
        return;
      }
      desbloquearAudioPremium(); // ainda dentro do toque (iOS) - antes do await
      const frase = await apiFetch("/api/voz/frase?momento=noite");
      if (!frase || !frase.texto) return;
      falarPremium(fechamentoOuvirBtn, frase.texto);
    });
  }
}
