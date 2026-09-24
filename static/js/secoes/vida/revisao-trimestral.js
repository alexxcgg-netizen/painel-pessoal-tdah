// static/js/secoes/vida/revisao-trimestral.js - Secao vida > revisao-trimestral (HTML: templates/secoes/vida/revisao-trimestral.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 2325-2378.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

// ---- Revisao trimestral/anual (Fase 5, US-C3) ---------------------------
async function carregarRevisaoPeriodo() {
  const tipo = $("#revisao-periodo-tipo").value;
  const ano = $("#revisao-periodo-ano").value || new Date().getFullYear();
  const trimestre = $("#revisao-periodo-trimestre").value;
  const params = new URLSearchParams({ tipo, ano });
  if (tipo === "trimestre") params.set("trimestre", trimestre);

  const dados = await apiFetch(`/api/revisao-periodo?${params.toString()}`);
  if (!dados) return;

  const box = $("#revisao-periodo-box");
  box.hidden = false;
  $("#revisao-periodo-titulo").textContent =
    dados.tipo === "trimestre"
      ? `T${dados.trimestre}/${dados.ano} (${dados.inicio} a ${dados.fim})`
      : `${dados.ano} (${dados.inicio} a ${dados.fim})`;

  const grid = $("#revisao-periodo-grid");
  grid.innerHTML = "";
  const stats = [
    ["Tarefas concluídas", dados.tarefas_feitas],
    ["Gasto total", fmtMoeda(dados.gasto_total)],
    ["Sono médio", dados.sono_medio != null ? `${dados.sono_medio}h` : "—"],
    ["Humor médio", dados.humor_medio || "—"],
    ["Decisões registradas", dados.decisoes.length],
    ["Decisões com resultado", dados.decisoes_com_resultado],
  ];
  stats.forEach(([rotulo, valor]) => {
    const item = document.createElement("div");
    item.className = "progresso-item";
    const v = document.createElement("span");
    v.className = "progresso-valor";
    v.textContent = valor;
    const r = document.createElement("span");
    r.className = "progresso-rotulo";
    r.textContent = rotulo;
    item.appendChild(v);
    item.appendChild(r);
    grid.appendChild(item);
  });

  const listaDecisoes = $("#revisao-periodo-decisoes");
  listaDecisoes.innerHTML = "";
  $("#revisao-periodo-decisoes-titulo").hidden = dados.decisoes.length === 0;
  dados.decisoes.forEach((d) => {
    const li = document.createElement("li");
    li.textContent = d.resultado ? `${d.decisao} — ${d.resultado}` : d.decisao;
    listaDecisoes.appendChild(li);
  });
}

$("#revisao-periodo-btn").addEventListener("click", carregarRevisaoPeriodo);
