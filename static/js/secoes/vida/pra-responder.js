// static/js/secoes/vida/pra-responder.js - Secao vida > pra-responder (HTML: templates/secoes/vida/pra-responder.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 636-662.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadResponder() {
  const itens = await apiFetch("/api/responder");
  if (!itens) return;
  const lista = $("#lista-responder");
  lista.innerHTML = "";
  $("#responder-vazio").hidden = itens.length > 0;
  itens.forEach((r) => {
    const quando = r.dias === 0 ? "de hoje" : `ha ${r.dias} dia(s)`;
    lista.appendChild(
      itemSimples(r.quem, [r.sobre, quando], [
        botaoAcao("respondi", async () => {
          const ok = await jsonPost(`/api/responder/${r.id}/feito`);
          if (ok) loadResponder();
          return ok;
        }),
      ], r.dias >= 2 ? "item-atencao" : "")
    );
  });
}

ligarForm("#responder-form", "#responder-btn", "Adicionar", () => {
  const quem = $("#responder-quem").value.trim();
  return quem ? { quem, sobre: $("#responder-sobre").value.trim() } : null;
}, "/api/responder", loadResponder);

// ---- Fase 2: lista de compras ----
