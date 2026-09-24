// static/js/secoes/vida/ideias-de-presente.js - Secao vida > ideias-de-presente (HTML: templates/secoes/vida/ideias-de-presente.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 1530-1562.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadIdeiasPresente() {
  const itens = await apiFetch("/api/ideias-presente");
  if (!itens) return;
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
      itemSimples(`${i.pessoa}: ${i.ideia}`, [i.ocasiao], [btnComprado, (el) => botaoApagar(`/api/ideias-presente/${i.id}`, el)])
    );
  });
}

ligarForm("#ideia-presente-form", "#ideia-presente-btn", "Adicionar", () => {
  const pessoa = $("#ideia-presente-pessoa").value.trim();
  const ideia = $("#ideia-presente-ideia").value.trim();
  if (!pessoa || !ideia) {
    mostrarErro("Confere pra quem e a ideia de presente.");
    return null;
  }
  return { pessoa, ideia, ocasiao: $("#ideia-presente-ocasiao").value.trim() || null };
}, "/api/ideias-presente", loadIdeiasPresente);

// ---- Fase 2: mensagem dificil ----
