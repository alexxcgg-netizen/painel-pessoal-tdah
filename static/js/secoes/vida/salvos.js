// static/js/secoes/vida/salvos.js - Secao vida > salvos (HTML: templates/secoes/vida/salvos.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 1649-1697.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadSalvos() {
  const itens = await apiFetch("/api/salvos");
  if (!itens) return;
  const lista = $("#lista-salvos");
  lista.innerHTML = "";
  $("#salvos-vazio").hidden = itens.length > 0;
  itens.forEach((sv) => {
    const acoes = [];
    if (!sv.lido_em) {
      acoes.push(
        botaoAcao("vi", async () => {
          const ok = await jsonPost(`/api/salvos/${sv.id}/lido`);
          if (ok) loadSalvos();
          return ok;
        })
      );
    }
    acoes.push((el) => botaoApagar(`/api/salvos/${sv.id}`, el));
    const li = itemSimples(sv.titulo || sv.url, [], acoes, sv.lido_em ? "lido" : "");
    let host = sv.url;
    try {
      host = new URL(sv.url).hostname.replace(/^www\./, "");
    } catch (_) {}
    const link = criarEl("a", "salvo-link", sv.titulo ? host : sv.url);
    link.href = sv.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    li.querySelector(".item-linha > div").appendChild(link);
    if (sv.resumo) li.appendChild(criarEl("p", "salvo-resumo", sv.resumo));
    lista.appendChild(li);
  });
}

$("#salvo-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const url = $("#salvo-url").value.trim();
  if (!url) return;
  const btn = $("#salvo-btn");
  setBotaoCarregando(btn, true, "lendo...");
  const r = await jsonPost("/api/salvos", { url });
  setBotaoCarregando(btn, false, "Salvar e resumir");
  if (!r) return;
  $("#salvo-url").value = "";
  if (r.aviso) mostrarErro(r.aviso);
  loadSalvos();
});

// ---- Fase 3: progresso, revisao do mes e uso do celular ----
