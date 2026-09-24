// static/js/secoes/hoje/previa-noite.js - Secao hoje > previa-noite (HTML: templates/secoes/hoje/previa-noite.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 1771-1801.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadPreviaNoite() {
  const data = await apiFetch("/api/previa-noite");
  if (!data) return;
  const box = $("#previa-noite-box");
  const oculto = $("#previa-noite-oculto");
  const texto = $("#previa-noite-texto");

  if (data.oculto) {
    box.hidden = false;
    oculto.hidden = false;
    texto.hidden = true;
    $("#previa-noite-data").textContent = "";
    return;
  }
  oculto.hidden = true;
  texto.hidden = false;

  const partes = [];
  if (data.sono_horas != null) partes.push(`dormiu ${data.sono_horas.toFixed(1)}h`);
  else if (data.sono_checkin != null) partes.push(`marcou o sono como ${data.sono_checkin}/5`);
  if (data.copos_agua) partes.push(`${data.copos_agua} copo(s) de agua`);
  if (data.medicamentos_total > 0) {
    partes.push(`remedio: ${data.medicamentos_tomados}/${data.medicamentos_total} tomado(s)`);
  }

  box.hidden = partes.length === 0;
  if (partes.length === 0) return;
  $("#previa-noite-data").textContent = fmtDataBr(data.data);
  texto.textContent = partes.join(" - ") + ".";
}
