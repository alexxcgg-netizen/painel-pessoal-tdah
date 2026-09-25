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

    // Fase 7 (V1, decisao D3 do Alex): "Guardar" ja processa em cards num
    // toque so (ver processarBrainDump, chamado direto no submit do form
    // logo abaixo) - o botao "Processar" por item saiu daqui. Os itens que
    // sobrarem pendentes (de antes dessa mudanca, ou porque a IA falhou na
    // hora de guardar) continuam podendo virar tarefa/nota/gasto na mao ou
    // serem apagados.
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

// Fase 7 (V1, decisao D3 do Alex): mesma chamada que o antigo botao
// "Processar" por item fazia (US-E6) - o texto inteiro vai pro pipeline do
// chat (`/api/brain-dump/<id>/converter` com `tipo: "assistente"`), que
// devolve o MESMO contrato de /api/chat: cada coisa misturada (gasto, tarefa,
// lembrete...) vira um card na aba Hoje, com Desfazer independente em cada
// um. `showTab("hoje")` leva o Alex pra ver os cards surgirem.
async function processarBrainDumpNoAssistente(itemId, texto) {
  showTab("hoje");
  return enviarChat(texto, {
    rota: `/api/brain-dump/${itemId}/converter`,
    corpo: { tipo: "assistente" },
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
  if (!data) {
    setBotaoCarregando(btn, false, "Guardar");
    return;
  }

  input.value = "";
  pulsarSucesso(input);
  loadBrainDump();

  // "Guardar" ja processa em cards num toque so - nao espera outro toque
  // num botao "Processar" separado. Se a IA falhar (teto atingido, erro),
  // o item continua pendente na lista (o servidor devolve `processado` pro
  // estado anterior) e da pra converter na mao (-> tarefa/nota/gasto) ou
  // apagar.
  setBotaoCarregando(btn, true, "processando...");
  await processarBrainDumpNoAssistente(data.id, texto);
  setBotaoCarregando(btn, false, "Guardar");
  loadBrainDump();
});

// Fase 9 C-abas: esta secao so carregava via navegacao.js (`if (name === "painel")`),
// gatilho que sumiu com a aba Painel. Agora mora dentro de #tab-vida - carrega quando
// a tab-btn "vida" e clicada (mesmo padrao que init.js ja usa pra loadVidaAba()).
if (typeof document !== "undefined") {
  const btnAbaVidaBrainDump = document.querySelector('.tab-btn[data-tab="vida"]');
  if (btnAbaVidaBrainDump) {
    btnAbaVidaBrainDump.addEventListener("click", loadBrainDump);
  }
}
