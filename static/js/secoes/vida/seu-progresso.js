// static/js/secoes/vida/seu-progresso.js - Secao vida > seu-progresso (HTML: templates/secoes/vida/seu-progresso.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 1698-1740.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadProgresso() {
  const p = await apiFetch("/api/progresso?dias=30");
  if (p) {
    const grid = $("#progresso-grid");
    grid.innerHTML = "";
    [
      [p.tarefas_feitas, "tarefas feitas"],
      [`${p.rotina_manha_dias}/${p.dias}`, "dias com rotina da manha"],
      [p.treinos_por_semana, "treinos por semana"],
      [p.copos_por_dia, "copos de agua por dia"],
      [p.sono_medio != null ? `${p.sono_medio}h` : "-", "sono medio"],
      [p.humor_medio || "-", "humor na media"],
    ].forEach(([valor, rotulo]) => {
      const item = criarEl("div", "progresso-item");
      item.appendChild(criarEl("span", "progresso-valor", String(valor)));
      item.appendChild(criarEl("span", "progresso-rotulo", rotulo));
      grid.appendChild(item);
    });
    const metas = $("#progresso-metas");
    metas.innerHTML = "";
    p.metas.forEach((m) => metas.appendChild(criarEl("li", null, `${m.titulo}: ${m.pct}%`)));
  }
  const revisao = await apiFetch("/api/revisao-mensal");
  const revEl = $("#revisao-mes");
  revEl.hidden = !revisao;
  if (revisao) revEl.textContent = revisao.texto;

  const uso = await apiFetch("/api/uso-apps?dias=7");
  $("#uso-apps-box").hidden = !uso || !uso.apps.length;
  if (uso && uso.apps.length) {
    const lista = $("#lista-uso-apps");
    lista.innerHTML = "";
    uso.apps.forEach((a) => {
      const li = criarEl("li");
      li.appendChild(criarEl("span", null, a.app));
      li.appendChild(criarEl("span", "progresso-rotulo", a.texto));
      lista.appendChild(li);
    });
  }
}

// ---- Fase 3: fim do mes (aba Gastos) ----
