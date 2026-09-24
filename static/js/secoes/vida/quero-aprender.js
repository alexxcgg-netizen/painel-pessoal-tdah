// static/js/secoes/vida/quero-aprender.js - Secao vida > quero-aprender (HTML: templates/secoes/vida/quero-aprender.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 1616-1648.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadAprender() {
  const itens = await apiFetch("/api/aprender");
  // Fase 7 C3a: resposta fora do formato (ex.: {} no lugar de lista) nao derruba a secao.
  if (!Array.isArray(itens)) return;
  const lista = $("#lista-aprender");
  lista.innerHTML = "";
  $("#aprender-vazio").hidden = itens.length > 0;
  itens.forEach((a) => {
    const parado =
      a.dias_parado > 0 ? `parado ha ${a.dias_parado} dia(s)` : a.ultima_vez ? "mexeu hoje" : "adicionado hoje";
    lista.appendChild(
      itemSimples(a.tema, [a.nota, parado], [
        botaoAcao("mexi hoje", async () => {
          const ok = await jsonPost(`/api/aprender/${a.id}/retomei`);
          if (ok) loadAprender();
          return ok;
        }),
        botaoAcao("aprendi", async () => {
          const ok = await jsonPost(`/api/aprender/${a.id}/concluido`);
          if (ok) loadAprender();
          return ok;
        }, false),
      ], "lista-item" + (a.dias_parado >= 14 ? " item-atencao" : ""))
    );
  });
}

// Fase 7 V4: botao "Adicionar tema" abre o formulario num bottom-sheet
// (static/js/ui/bottom-sheet.js, faixa V0d). Enquanto essa faixa nao chega na
// integracao, cai no fallback inline (so hidden) - retestado depois do merge
// com origin/fase7/integracao.
$("#aprender-abrir-btn").addEventListener("click", () => {
  const sheet = $("#sheet-aprender");
  // Fase 7 C3a: toque durante a animacao de fechar (240ms) e ignorado - reabrir nessa
  // janela deixava o sheet preso (bug do V0d anotado no progress da C3a).
  if (sheet.classList.contains("bottom-sheet--fechando")) return;
  if (window.abrirBottomSheet) window.abrirBottomSheet(sheet);
  else sheet.hidden = false;
});

$("#aprender-cancelar-btn").addEventListener("click", () => {
  $("#aprender-form").reset();
  const sheet = $("#sheet-aprender");
  if (window.fecharBottomSheet) window.fecharBottomSheet(sheet);
  else sheet.hidden = true;
});

ligarForm("#aprender-form", "#aprender-btn", "Adicionar", () => {
  const tema = $("#aprender-tema").value.trim();
  return tema ? { tema } : null;
}, "/api/aprender", (r) => {
  const sheet = $("#sheet-aprender");
  if (window.fecharBottomSheet) window.fecharBottomSheet(sheet);
  else sheet.hidden = true;
  loadAprender(r);
});

// ---- Fase 3: links salvos ----
