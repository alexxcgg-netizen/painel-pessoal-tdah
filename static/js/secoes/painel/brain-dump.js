// static/js/secoes/painel/brain-dump.js - Secao painel > brain-dump (HTML: templates/secoes/painel/brain-dump.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 2180-2303.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

// ---- Brain dump (Fase 5, US-C6) ----------------------------------------
async function loadBrainDump() {
  const itens = await apiFetch("/api/brain-dump");
  if (!itens) return;

  const list = $("#lista-brain-dump");
  list.innerHTML = "";
  $("#brain-dump-vazio").hidden = itens.length > 0;

  itens.forEach((item) => {
    const li = document.createElement("li");
    li.className = "item";

    const linha = document.createElement("div");
    linha.className = "item-linha";

    const tituloWrap = document.createElement("div");
    const titulo = document.createElement("span");
    titulo.className = "item-titulo";
    titulo.textContent = item.texto;
    tituloWrap.appendChild(titulo);
    linha.appendChild(tituloWrap);

    const acoes = document.createElement("div");
    acoes.className = "item-acoes";

    // US-E6: "Processar" manda o despejo inteiro pro assistente (mesmo
    // pipeline do chat) - cada coisa misturada no texto vira um card na aba
    // Hoje, com Desfazer independente.
    const processar = async (btn) => {
      btn.disabled = true;
      showTab("hoje");
      const data = await enviarChat(item.texto, {
        rota: `/api/brain-dump/${item.id}/converter`,
        corpo: { tipo: "assistente" },
      });
      btn.disabled = false;
      if (data) loadBrainDump();
    };
    const processarBtn = document.createElement("button");
    processarBtn.className = "btn-com-icone btn-brain-processar";
    processarBtn.textContent = "Processar";
    processarBtn.setAttribute("aria-label", "Processar com o assistente");
    processarBtn.addEventListener("click", () => processar(processarBtn));
    acoes.appendChild(processarBtn);

    const converterPara = async (tipo) => {
      const corpo = { tipo };
      if (tipo === "gasto") {
        const valorTexto = window.prompt("Valor do gasto (ex: 30.00)?");
        const valor = parseFloat((valorTexto || "").replace(",", "."));
        if (!valor || valor <= 0) return;
        corpo.valor = valor;
      }
      const data = await apiFetch(`/api/brain-dump/${item.id}/converter`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(corpo),
      });
      if (!data) return;
      li.classList.add("saindo");
      setTimeout(() => {
        loadBrainDump();
        if (tipo === "tarefa") loadTasks();
        if (tipo === "nota") loadNotas();
        if (tipo === "gasto") loadExpenses();
      }, 220);
    };

    [
      ["tarefa", "→ tarefa"],
      ["nota", "→ nota"],
      ["gasto", "→ gasto"],
    ].forEach(([tipo, rotulo]) => {
      const btn = document.createElement("button");
      btn.className = "btn-com-icone";
      btn.textContent = rotulo;
      btn.addEventListener("click", () => converterPara(tipo));
      acoes.appendChild(btn);
    });

    const apagarBtn = document.createElement("button");
    apagarBtn.className = "btn-com-icone";
    apagarBtn.innerHTML = ICONE_TRASH;
    apagarBtn.setAttribute("aria-label", "Apagar");
    apagarBtn.addEventListener("click", async () => {
      apagarBtn.disabled = true;
      const ok = await apiFetch(`/api/brain-dump/${item.id}`, { method: "DELETE" });
      if (ok) {
        li.classList.add("saindo");
        setTimeout(() => li.remove(), 250);
      } else {
        apagarBtn.disabled = false;
      }
    });
    acoes.appendChild(apagarBtn);
    linha.appendChild(acoes);

    li.appendChild(linha);
    list.appendChild(li);
  });
}

$("#brain-dump-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#brain-dump-btn");
  const input = $("#brain-dump-texto");
  const texto = input.value.trim();
  if (!texto) return;

  setBotaoCarregando(btn, true, "guardando...");
  const data = await apiFetch("/api/brain-dump", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ texto }),
  });
  setBotaoCarregando(btn, false, "Guardar");
  if (!data) return;

  input.value = "";
  pulsarSucesso(input);
  loadBrainDump();
});
