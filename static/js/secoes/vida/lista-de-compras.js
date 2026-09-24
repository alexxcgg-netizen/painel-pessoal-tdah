// static/js/secoes/vida/lista-de-compras.js - Secao vida > lista-de-compras (HTML: templates/secoes/vida/lista-de-compras.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 663-697.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadCompras() {
  const itens = await apiFetch("/api/compras");
  if (!itens) return;
  const lista = $("#lista-compras");
  lista.innerHTML = "";
  $("#compras-vazio").hidden = itens.length > 0;
  itens.forEach((c) => {
    const li = criarEl("li", "checklist-item");
    const label = criarEl("label");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.addEventListener("change", async () => {
      const ok = await jsonPost(`/api/compras/${c.id}/comprado`);
      if (!ok) {
        cb.checked = false;
        return;
      }
      li.classList.add("feito", "saindo");
      setTimeout(() => loadCompras(), 250);
    });
    label.appendChild(cb);
    label.appendChild(criarEl("span", null, c.item));
    li.appendChild(label);
    lista.appendChild(li);
  });
}

ligarForm("#compra-form", "#compra-btn", "Adicionar", () => {
  const item = $("#compra-item").value.trim();
  return item ? { itens: [item] } : null;
}, "/api/compras", loadCompras);

// ---- Fase 6 (US-E12): Habitos - NOVO, separado da Rotina guiada (rotina
// manha/noite continua em loadRotina acima) ----
