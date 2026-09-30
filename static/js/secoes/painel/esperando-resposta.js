// static/js/secoes/painel/esperando-resposta.js - Secao painel > esperando-resposta (HTML: templates/secoes/painel/esperando-resposta.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 1873-1986, app.js 2379-2406.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

const ICONE_ESTRELA_CHEIA =
  '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"><path d="M12 3.5l2.6 5.4 5.9.8-4.3 4.2 1 5.9L12 17l-5.2 2.8 1-5.9-4.3-4.2 5.9-.8L12 3.5Z"/></svg>';
const ICONE_ESTRELA_VAZIA =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"><path d="M12 3.5l2.6 5.4 5.9.8-4.3 4.2 1 5.9L12 17l-5.2 2.8 1-5.9-4.3-4.2 5.9-.8L12 3.5Z"/></svg>';

async function loadEsperas() {
  // Fase 6 (US-F8): /api/esperas/prioridade em vez de /api/esperas puro -
  // MESMA lista (list_esperas_pendentes por baixo), so que ja vem com
  // dias_parado calculado e ordenada por vida.priorizar_esperas (tempo
  // parado + importancia) - esse endpoint ja existia desde a Fase 5 (US-C5)
  // mas nenhuma tela usava, a lista ficava na ordem de criacao sem mostrar
  // ha quanto tempo cada uma ta parada.
  const esperas = await apiFetch("/api/esperas/prioridade");
  if (!esperas) return;

  const list = $("#lista-esperas");
  list.innerHTML = "";
  $("#esperas-vazio").hidden = esperas.length > 0;

  esperas.forEach((esp) => {
    const li = document.createElement("li");
    li.className = "item";

    const linha = document.createElement("div");
    linha.className = "item-linha";

    const tituloWrap = document.createElement("div");
    const titulo = document.createElement("span");
    titulo.className = "item-titulo";
    titulo.textContent = esp.quem;
    tituloWrap.appendChild(titulo);
    const sobre = document.createElement("span");
    sobre.className = "item-quando";
    sobre.textContent = esp.sobre;
    tituloWrap.appendChild(sobre);
    if (typeof esp.dias_parado === "number") {
      const parado = document.createElement("span");
      const critico = esp.dias_parado > 5;
      parado.className = `item-quando espera-dias-parado${critico ? " espera-dias-parado-critico" : ""}`;
      parado.textContent =
        esp.dias_parado === 0 ? "esperando desde hoje" : `esperando ha ${esp.dias_parado} dia(s)`;
      tituloWrap.appendChild(parado);
    }
    linha.appendChild(tituloWrap);

    const acoes = document.createElement("div");
    acoes.className = "item-acoes";

    // Fase 6 (US-F8): mesma logica do botao "importante" - endpoint
    // /api/esperas/<id>/importante ja existia (Fase 5, US-C5, usado so pelo
    // calculo de prioridade), sem nenhum jeito de marcar pela tela.
    const importanteBtn = document.createElement("button");
    importanteBtn.className = "btn-com-icone btn-espera-importante";
    importanteBtn.setAttribute("aria-label", esp.importante ? "Desmarcar como importante" : "Marcar como importante");
    importanteBtn.setAttribute("aria-pressed", esp.importante ? "true" : "false");
    importanteBtn.classList.toggle("ativo", Boolean(esp.importante));
    importanteBtn.innerHTML = esp.importante ? ICONE_ESTRELA_CHEIA : ICONE_ESTRELA_VAZIA;
    importanteBtn.addEventListener("click", async () => {
      importanteBtn.disabled = true;
      const novoValor = !esp.importante;
      const data = await apiFetch(`/api/esperas/${esp.id}/importante`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ importante: novoValor }),
      });
      if (data) {
        esp.importante = novoValor;
        importanteBtn.classList.toggle("ativo", novoValor);
        importanteBtn.innerHTML = novoValor ? ICONE_ESTRELA_CHEIA : ICONE_ESTRELA_VAZIA;
        importanteBtn.setAttribute("aria-label", novoValor ? "Desmarcar como importante" : "Marcar como importante");
        importanteBtn.setAttribute("aria-pressed", novoValor ? "true" : "false");
        pulsarSucesso(importanteBtn);
      }
      importanteBtn.disabled = false;
    });
    acoes.appendChild(importanteBtn);

    const resolverBtn = document.createElement("button");
    resolverBtn.className = "btn-com-icone primario";
    resolverBtn.innerHTML = `${ICONE_CHECK}Resolvido`;
    resolverBtn.addEventListener("click", async () => {
      resolverBtn.disabled = true;
      const ok = await apiFetch(`/api/esperas/${esp.id}/resolver`, { method: "POST" });
      if (ok) {
        removerLiAnimado(li);
      } else {
        resolverBtn.disabled = false;
      }
    });
    acoes.appendChild(resolverBtn);

    const apagarBtn = document.createElement("button");
    apagarBtn.className = "btn-com-icone";
    apagarBtn.innerHTML = ICONE_TRASH;
    apagarBtn.setAttribute("aria-label", "Apagar");
    apagarBtn.addEventListener("click", async () => {
      apagarBtn.disabled = true;
      const ok = await apiFetch(`/api/esperas/${esp.id}`, { method: "DELETE" });
      if (ok) {
        removerLiAnimado(li);
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

$("#espera-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#espera-btn");
  const quemInput = $("#espera-quem");
  const sobreInput = $("#espera-sobre");
  const quem = quemInput.value.trim();
  const sobre = sobreInput.value.trim();
  if (!quem || !sobre) {
    mostrarErro("Confere quem e sobre o que você está esperando.");
    return;
  }

  setBotaoCarregando(btn, true, "salvando...");
  const data = await apiFetch("/api/esperas", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ quem, sobre }),
  });
  setBotaoCarregando(btn, false, "Salvar espera");
  if (!data) return;

  quemInput.value = "";
  sobreInput.value = "";
  pulsarSucesso(quemInput);
  e.target.dispatchEvent(new CustomEvent("bottomsheet:sucesso", { bubbles: true })); // C2: fecha o sheet
  loadEsperas();
  loadStreak();
});
