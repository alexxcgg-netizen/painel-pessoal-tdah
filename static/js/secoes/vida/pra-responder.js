// static/js/secoes/vida/pra-responder.js - Secao vida > pra-responder (HTML: templates/secoes/vida/pra-responder.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 636-662.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadResponder() {
  const itens = await apiFetch("/api/responder");
  // Fase 7 C3a: resposta fora do formato (ex.: {} no lugar de lista) nao derruba a secao.
  if (!Array.isArray(itens)) return;
  const lista = $("#lista-responder");
  lista.innerHTML = "";
  $("#responder-vazio").hidden = itens.length > 0;
  itens.forEach((r) => {
    const quando = r.dias === 0 ? "de hoje" : `há ${r.dias} dia(s)`;
    lista.appendChild(
      itemSimples(r.quem, [r.sobre, quando], [
        botaoAcao("respondi", async () => {
          const ok = await jsonPost(`/api/responder/${r.id}/feito`);
          if (ok) loadResponder();
          return ok;
        }),
      ], "lista-item" + (r.dias >= 2 ? " item-atencao" : ""))
    );
  });
}

// Fase 7 V4: botao "Adicionar pendência" abre o formulario num bottom-sheet
// (static/js/ui/bottom-sheet.js, faixa V0d). Enquanto essa faixa nao chega na
// integracao, cai no fallback inline (so hidden) - retestado depois do merge
// com origin/fase7/integracao.
$("#responder-abrir-btn").addEventListener("click", () => {
  const sheet = $("#sheet-responder");
  // Fase 7 C3a: toque durante a animacao de fechar (240ms) e ignorado - reabrir nessa
  // janela deixava o sheet preso (bug do V0d anotado no progress da C3a).
  if (sheet.classList.contains("bottom-sheet--fechando")) return;
  if (window.abrirBottomSheet) window.abrirBottomSheet(sheet);
  else sheet.hidden = false;
});

$("#responder-cancelar-btn").addEventListener("click", () => {
  $("#responder-form").reset();
  const sheet = $("#sheet-responder");
  if (window.fecharBottomSheet) window.fecharBottomSheet(sheet);
  else sheet.hidden = true;
});

ligarForm("#responder-form", "#responder-btn", "Adicionar", () => {
  const quem = $("#responder-quem").value.trim();
  return quem ? { quem, sobre: $("#responder-sobre").value.trim() } : null;
}, "/api/responder", (r) => {
  const sheet = $("#sheet-responder");
  if (window.fecharBottomSheet) window.fecharBottomSheet(sheet);
  else sheet.hidden = true;
  loadResponder(r);
});

// ---- Fase 2: lista de compras ----
