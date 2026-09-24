// static/js/secoes/painel/diario-de-decisao.js - Secao painel > diario-de-decisao (HTML: templates/secoes/painel/diario-de-decisao.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 2048-2179.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

// ---- Diario de decisao (Fase 5, US-C2) --------------------------------
async function loadDecisoes() {
  const decisoes = await apiFetch("/api/diario-decisoes");
  if (!decisoes) return;

  const list = $("#lista-diario-decisoes");
  list.innerHTML = "";
  $("#diario-decisoes-vazio").hidden = decisoes.length > 0;

  decisoes.forEach((d) => {
    const li = document.createElement("li");
    li.className = "item";

    const linha = document.createElement("div");
    linha.className = "item-linha";

    const tituloWrap = document.createElement("div");
    const titulo = document.createElement("span");
    titulo.className = "item-titulo";
    titulo.textContent = d.decisao;
    // Fase 6 (US-F8): selo de status (pill) alem do texto - "resolvida" ou
    // "aguardando resultado" de relance, sem precisar ler a frase inteira.
    const status = document.createElement("span");
    status.className = d.resultado ? "item-tag-tarefa diario-status-resolvida" : "item-tag-tarefa";
    status.textContent = d.resultado ? "resolvida" : "aguardando";
    titulo.appendChild(status);
    tituloWrap.appendChild(titulo);

    if (d.data) {
      const data = document.createElement("span");
      data.className = "item-quando";
      data.textContent = fmtDataBr(d.data);
      tituloWrap.appendChild(data);
    }

    if (d.contexto) {
      const contexto = document.createElement("span");
      contexto.className = "item-quando";
      contexto.textContent = d.contexto;
      tituloWrap.appendChild(contexto);
    }

    if (d.resultado) {
      const resultado = document.createElement("span");
      resultado.className = "item-quando";
      resultado.textContent = `Resultado: ${d.resultado}`;
      tituloWrap.appendChild(resultado);
    }
    linha.appendChild(tituloWrap);

    const acoes = document.createElement("div");
    acoes.className = "item-acoes";

    if (!d.resultado) {
      const btnResultado = document.createElement("button");
      btnResultado.className = "btn-com-icone";
      btnResultado.innerHTML = `${ICONE_CHECK}resultado`;
      btnResultado.addEventListener("click", () => {
        if (li.querySelector(".correcao-form")) return;
        const form = document.createElement("form");
        form.className = "correcao-form form-linha";
        const input = document.createElement("input");
        input.type = "text";
        input.maxLength = 300;
        input.placeholder = "Como foi?";
        input.required = true;
        const salvar = document.createElement("button");
        salvar.type = "submit";
        salvar.className = "btn-com-icone primario";
        salvar.textContent = "Salvar";
        form.appendChild(input);
        form.appendChild(salvar);
        form.addEventListener("submit", async (ev) => {
          ev.preventDefault();
          const data = await apiFetch(`/api/diario-decisoes/${d.id}/resultado`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ resultado: input.value.trim() }),
          });
          if (data) loadDecisoes();
        });
        li.appendChild(form);
        input.focus();
      });
      acoes.appendChild(btnResultado);
    }

    const apagarBtn = document.createElement("button");
    apagarBtn.className = "btn-com-icone";
    apagarBtn.innerHTML = ICONE_TRASH;
    apagarBtn.setAttribute("aria-label", "Apagar");
    apagarBtn.addEventListener("click", async () => {
      apagarBtn.disabled = true;
      const ok = await apiFetch(`/api/diario-decisoes/${d.id}`, { method: "DELETE" });
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

$("#diario-decisao-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#diario-decisao-btn");
  const textoInput = $("#diario-decisao-texto");
  const contextoInput = $("#diario-decisao-contexto");
  const decisao = textoInput.value.trim();
  if (!decisao) return;

  setBotaoCarregando(btn, true, "salvando...");
  const data = await apiFetch("/api/diario-decisoes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decisao, contexto: contextoInput.value.trim() }),
  });
  setBotaoCarregando(btn, false, "Salvar decisão");
  if (!data) return;

  textoInput.value = "";
  contextoInput.value = "";
  pulsarSucesso(textoInput);
  e.target.dispatchEvent(new CustomEvent("bottomsheet:sucesso", { bubbles: true })); // C2: fecha o sheet
  loadDecisoes();
});
