// static/js/secoes/aviacao/registrar-voo.js - Secao aviacao > registrar-voo (HTML: templates/secoes/aviacao/registrar-voo.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 3689-3745.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

aplicarMascaraData($("#voo-data"));

// Fase 7 (C3b): o formulario de voo (longo, 6 campos) saiu do meio da aba e
// foi pro bottom-sheet compartilhado (static/js/ui/bottom-sheet.js, V0d), que
// abre pelo .btn-adicionar "Registrar voo" (MASTER.md 11: formulario nao fica
// sempre aberto na secao). Fallback so pro caso de o componente nao carregar.
function abrirPainelVoo() {
  const sheet = $("#voo-sheet");
  if (typeof levarSheetProBody === "function") levarSheetProBody(sheet); // ver secoes/vida/viagens.js
  if (typeof window.abrirBottomSheet === "function") window.abrirBottomSheet(sheet);
  else sheet.hidden = false;
}

function fecharPainelVoo() {
  const sheet = $("#voo-sheet");
  if (typeof window.fecharBottomSheet === "function") window.fecharBottomSheet(sheet);
  else sheet.hidden = true;
}

$("#voo-abrir-btn").addEventListener("click", abrirPainelVoo);
$("#voo-cancelar-btn").addEventListener("click", () => {
  $("#voo-form").reset();
  fecharPainelVoo();
});

$("#voo-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#voo-btn");
  if (btn.disabled) return; // ja salvando - evita voo duplicado com toque duplo
  const dataInput = $("#voo-data");
  const horaInput = $("#voo-hora");
  const origemInput = $("#voo-origem");
  const destinoInput = $("#voo-destino");
  const horasInput = $("#voo-horas");
  const obsInput = $("#voo-obs");

  const dataIso = mascaraDataParaIso(dataInput.value.trim());
  const destino = destinoInput.value.trim();
  if (!dataIso || !destino) {
    mostrarErro("Confere a data (dd/mm/aaaa) e o destino.");
    return;
  }
  const horasTxt = horasInput.value.trim();
  const horas = horasTxt ? parseHoras(horasTxt) : null;
  if (horasTxt && !horas) {
    mostrarErro("Horas invalidas - use um número tipo 1,5 (ou deixe em branco se só agendado).");
    return;
  }
  const horaTxt = horaInput.value.trim();
  if (horaTxt && !/^([01]?\d|2[0-3]):[0-5]\d$/.test(horaTxt)) {
    mostrarErro("Horário do voo inválido - use hh:mm (ex: 14:00), ou deixe em branco.");
    return;
  }

  setBotaoCarregando(btn, true, "salvando...");
  const data = await apiFetch("/api/voos", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      data: dataIso,
      hora: horaTxt || undefined,
      origem: origemInput.value.trim() || undefined,
      destino,
      horas,
      observacao: obsInput.value.trim() || undefined,
    }),
  });
  setBotaoCarregando(btn, false, "Salvar voo");
  if (!data) return;

  dataInput.value = "";
  horaInput.value = "";
  origemInput.value = "";
  destinoInput.value = "";
  horasInput.value = "";
  obsInput.value = "";
  fecharPainelVoo();
  loadVoosResumo();
  loadStreak();
});
