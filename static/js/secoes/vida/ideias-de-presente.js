// static/js/secoes/vida/ideias-de-presente.js - Secao vida > ideias-de-presente (HTML: templates/secoes/vida/ideias-de-presente.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 1530-1562.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadIdeiasPresente() {
  const itens = await apiFetch("/api/ideias-presente");
  // Fase 7 C3a: resposta fora do formato (ex.: {} no lugar de lista) nao derruba a secao.
  if (!Array.isArray(itens)) return;
  const lista = $("#lista-ideias-presente");
  lista.innerHTML = "";
  $("#ideias-presente-vazio").hidden = itens.length > 0;
  itens.forEach((i) => {
    const btnComprado = criarEl("button", "btn-com-icone" + (i.comprado ? " primario" : ""));
    btnComprado.textContent = i.comprado ? "comprado" : "marcar comprado";
    btnComprado.addEventListener("click", async () => {
      btnComprado.disabled = true;
      const r = await jsonPost(`/api/ideias-presente/${i.id}/comprado`);
      if (r) loadIdeiasPresente();
      else btnComprado.disabled = false;
    });
    lista.appendChild(
      itemSimples(`${i.pessoa}: ${i.ideia}`, [i.ocasiao], [btnComprado, (el) => botaoApagar(`/api/ideias-presente/${i.id}`, el)], "lista-item")
    );
  });
}

// Fase 7 V4: botao "Adicionar" abre o formulario num bottom-sheet
// (static/js/ui/bottom-sheet.js, faixa V0d). Enquanto essa faixa nao chega na
// integracao, cai no fallback inline (so hidden) - retestado depois do merge
// com origin/fase7/integracao.
$("#ideia-presente-abrir-btn").addEventListener("click", () => {
  const sheet = $("#sheet-ideia-presente");
  // Fase 7 C3a: toque durante a animacao de fechar (240ms) e ignorado - reabrir nessa
  // janela deixava o sheet preso (bug do V0d anotado no progress da C3a).
  if (sheet.classList.contains("bottom-sheet--fechando")) return;
  if (window.abrirBottomSheet) window.abrirBottomSheet(sheet);
  else sheet.hidden = false;
});

$("#ideia-presente-cancelar-btn").addEventListener("click", () => {
  $("#ideia-presente-form").reset();
  const sheet = $("#sheet-ideia-presente");
  if (window.fecharBottomSheet) window.fecharBottomSheet(sheet);
  else sheet.hidden = true;
});

ligarForm("#ideia-presente-form", "#ideia-presente-btn", "Adicionar", () => {
  const pessoa = $("#ideia-presente-pessoa").value.trim();
  const ideia = $("#ideia-presente-ideia").value.trim();
  if (!pessoa || !ideia) {
    mostrarErro("Confere pra quem e a ideia de presente.");
    return null;
  }
  return { pessoa, ideia, ocasiao: $("#ideia-presente-ocasiao").value.trim() || null };
}, "/api/ideias-presente", (r) => {
  const sheet = $("#sheet-ideia-presente");
  if (window.fecharBottomSheet) window.fecharBottomSheet(sheet);
  else sheet.hidden = true;
  loadIdeiasPresente(r);
});

// ---- Fase 2: mensagem dificil ----
