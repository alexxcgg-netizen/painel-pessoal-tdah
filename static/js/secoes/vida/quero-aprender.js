// static/js/secoes/vida/quero-aprender.js - Secao vida > quero-aprender (HTML: templates/secoes/vida/quero-aprender.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 1616-1648.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadAprender() {
  const itens = await apiFetch("/api/aprender");
  if (!itens) return;
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
      ], a.dias_parado >= 14 ? "item-atencao" : "")
    );
  });
}

ligarForm("#aprender-form", "#aprender-btn", "Adicionar", () => {
  const tema = $("#aprender-tema").value.trim();
  return tema ? { tema } : null;
}, "/api/aprender", loadAprender);

// ---- Fase 3: links salvos ----
