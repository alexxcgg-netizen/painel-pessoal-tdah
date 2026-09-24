// static/js/secoes/bancos/ofx.js - Secao bancos > ofx (HTML: templates/secoes/bancos/ofx.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 3069-3106.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

const OFX_LABEL_PADRAO = "Escolher extrato (.ofx, .qfx)";

function atualizarOfxLabel() {
  const label = $("#ofx-input-label");
  const span = label.querySelector("span");
  const arquivo = $("#ofx-input").files[0];
  span.textContent = arquivo ? arquivo.name : OFX_LABEL_PADRAO;
  label.classList.toggle("tem-arquivo", Boolean(arquivo));
}

$("#ofx-input").addEventListener("change", atualizarOfxLabel);

$("#importar-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const banco = $("#banco-select").value;
  const tipo = $("#tipo-select").value;
  const arquivo = $("#ofx-input").files[0];
  if (!arquivo) return;

  const importarBtn = $("#importar-btn");
  setBotaoCarregando(importarBtn, true, "Importando...");

  const form = new FormData();
  form.append("banco", banco);
  form.append("tipo", tipo);
  form.append("arquivo", arquivo);
  const data = await apiFetch("/api/bancos/importar", { method: "POST", body: form });

  setBotaoCarregando(importarBtn, false, "Importar extrato");

  if (!data) return;
  $("#ofx-input").value = "";
  atualizarOfxLabel();
  const n = (v) => numeroFinancas(v) ?? 0;
  $("#bancos-status").textContent =
    `Importado: ${n(data.novas)} nova(s), ${n(data.duplicadas)} ja existiam de ${n(data.encontradas)} encontradas.`;
  loadBancos();
});
