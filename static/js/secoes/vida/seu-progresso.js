// static/js/secoes/vida/seu-progresso.js - Secao vida > seu-progresso (HTML: templates/secoes/vida/seu-progresso.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 1698-1740.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

// Fase 7 M1: desde a C1 o `pct` da meta vem com 1 casa (calculos.percentual_meta_exibicao,
// ex.: 33.3). Na tela vai em pt-BR, com virgula ("33,3%"; inteiro fica "100%"), no mesmo
// padrao de toLocaleString("pt-BR") de nucleo/formatos.js. Valor fora do formato vira "-".
function fmtPctMeta(pct) {
  const n = typeof pct === "number" ? pct : Number.parseFloat(pct);
  if (pct == null || pct === "" || !Number.isFinite(n)) return "-";
  return `${n.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
}

async function loadProgresso() {
  const p = await apiFetch("/api/progresso?dias=30");
  // Fase 7 C3a: resposta fora do formato (ex.: {} no lugar de lista) nao derruba a secao.
  if (p && typeof p === "object") {
    const grid = $("#progresso-grid");
    grid.innerHTML = "";
    const contar = !window._c2ProgressoContou; // conta so na 1a exibicao (nunca a cada recarga)
    window._c2ProgressoContou = true;
    [
      [p.tarefas_feitas, "tarefas feitas"],
      [`${p.rotina_manha_dias}/${p.dias}`, "dias com rotina da manhã"],
      [p.treinos_por_semana, "treinos por semana"],
      [p.copos_por_dia, "copos de água por dia"],
      [p.sono_medio != null ? `${p.sono_medio}h` : "-", "sono médio"],
      [p.humor_medio || "-", "humor na média"],
    ].forEach(([valor, rotulo]) => {
      const item = criarEl("div", "progresso-item");
      const valorEl = criarEl("span", "progresso-valor", String(valor));
      item.appendChild(valorEl);
      const num = typeof valor === "number" ? valor : NaN; // so numeros puros (nunca "3/7" nem "8h")
      if (contar && Number.isFinite(num) && num !== 0 && typeof animarNumero === "function") {
        const casas = (String(valor).split(".")[1] || "").length;
        animarNumero(valorEl, num, (v) => (casas ? Number(v).toFixed(casas) : String(Math.round(v))));
      }
      item.appendChild(criarEl("span", "progresso-rotulo", rotulo));
      grid.appendChild(item);
    });
    const metas = $("#progresso-metas");
    metas.innerHTML = "";
    (Array.isArray(p.metas) ? p.metas : []).forEach((m) => metas.appendChild(criarEl("li", null, `${m.titulo}: ${fmtPctMeta(m.pct)}`)));
  }
  const revisao = await apiFetch("/api/revisao-mensal");
  const revEl = $("#revisao-mes");
  revEl.hidden = !(revisao && revisao.texto);
  if (revisao && revisao.texto) revEl.textContent = revisao.texto;

  const uso = await apiFetch("/api/uso-apps?dias=7");
  const apps = uso && Array.isArray(uso.apps) ? uso.apps : [];
  $("#uso-apps-box").hidden = !apps.length;
  if (apps.length) {
    const lista = $("#lista-uso-apps");
    lista.innerHTML = "";
    apps.forEach((a) => {
      const li = criarEl("li");
      li.appendChild(criarEl("span", null, a.app));
      li.appendChild(criarEl("span", "progresso-rotulo", a.texto));
      lista.appendChild(li);
    });
  }
}

// ---- Fase 3: fim do mes (aba Gastos) ----
