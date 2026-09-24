// static/js/secoes/aviacao/registrar-voo.js - Secao aviacao > registrar-voo (HTML: templates/secoes/aviacao/registrar-voo.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 3689-3745.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

aplicarMascaraData($("#voo-data"));

$("#voo-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#voo-btn");
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
    mostrarErro("Horas invalidas - use um numero tipo 1,5 (ou deixe em branco se so agendado).");
    return;
  }
  const horaTxt = horaInput.value.trim();
  if (horaTxt && !/^([01]?\d|2[0-3]):[0-5]\d$/.test(horaTxt)) {
    mostrarErro("Horario do voo invalido - use hh:mm (ex: 14:00), ou deixe em branco.");
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
  setBotaoCarregando(btn, false, "Registrar");
  if (!data) return;

  dataInput.value = "";
  horaInput.value = "";
  origemInput.value = "";
  destinoInput.value = "";
  horasInput.value = "";
  obsInput.value = "";
  pulsarSucesso(destinoInput);
  loadVoosResumo();
  loadStreak();
});
