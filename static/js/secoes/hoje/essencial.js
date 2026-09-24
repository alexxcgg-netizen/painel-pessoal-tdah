// static/js/secoes/hoje/essencial.js - Secao hoje > essencial (HTML: templates/secoes/hoje/essencial.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 132-207.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

function aplicarModoEssencial(ativo) {
  document.body.classList.toggle("modo-essencial", ativo);
  const btn = $("#essencial-modo-btn");
  btn.setAttribute("aria-pressed", String(ativo));
  btn.textContent = ativo ? "sair do modo foco" : "modo foco no dia";
}

function renderEssencial(tarefas) {
  const lista = $("#essencial-lista");
  lista.innerHTML = "";
  $("#essencial-vazio").hidden = tarefas.length > 0;
  tarefas.forEach((t) => {
    const li = criarEl("li", "essencial-item" + (t.feita ? " feita" : ""));
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = t.feita;
    cb.disabled = t.feita;
    cb.setAttribute("aria-label", `Concluir ${t.title}`);
    cb.addEventListener("change", async () => {
      const r = await apiFetch(`/api/tasks/${t.id}/complete`, { method: "POST" });
      if (!r) {
        cb.checked = false;
        return;
      }
      explodirConcluido(cb);
      vibrar(30);
      tocarSomConcluido();
      loadEssencial();
      loadSummary();
      loadStreak();
    });
    const textos = criarEl("div", "essencial-textos");
    textos.appendChild(criarEl("span", "essencial-titulo", t.title));
    const detalhe = [t.hora ? `as ${t.hora}` : null, t.motivo].filter(Boolean).join(" - ");
    if (detalhe) textos.appendChild(criarEl("span", "essencial-motivo", detalhe));
    li.appendChild(cb);
    li.appendChild(textos);
    if (!t.feita) {
      const trocar = criarEl("button", "btn-link", "trocar");
      trocar.type = "button";
      trocar.setAttribute("aria-label", `Trocar ${t.title} por outra tarefa`);
      trocar.addEventListener("click", async () => {
        trocar.disabled = true;
        const r = await apiFetch("/api/essencial/trocar", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ task_id: t.id }),
        });
        if (r) renderEssencial(r.tarefas);
        else trocar.disabled = false;
      });
      li.appendChild(trocar);
    }
    lista.appendChild(li);
  });
}

async function loadEssencial() {
  const data = await apiFetch("/api/essencial");
  if (!data) return;
  aplicarModoEssencial(data.modo_ativo);
  renderEssencial(data.tarefas);
}

$("#essencial-modo-btn").addEventListener("click", async () => {
  const ativo = !document.body.classList.contains("modo-essencial");
  const r = await apiFetch("/api/essencial/modo", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ativo }),
  });
  if (r) aplicarModoEssencial(r.modo_ativo);
});

// ---- Hiperfoco ----
