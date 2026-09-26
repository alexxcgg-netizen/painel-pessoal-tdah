// static/js/secoes/painel/peso-e-medidas.js - Secao painel > peso-e-medidas (HTML: templates/secoes/painel/peso-e-medidas.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 1284-1462.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

// Fase 6 US-F2: grafico de evolucao (mesmo helper de linha SVG das Metas e
// Aviacao, static/js/charts.js) - pega o tipo mais recente que tenha pelo
// menos 2 registros ("peso" tem prioridade por ser o mais comum), sem
// requisicao nova: usa a lista que loadMedidas ja buscou.
function dadosGraficoMedida(medidas) {
  if (!medidas.length) return null;
  const tipoPreferido = medidas.some((m) => m.tipo === "peso") ? "peso" : medidas[0].tipo;
  const doTipo = medidas.filter((m) => m.tipo === tipoPreferido);
  if (doTipo.length < 2) return null;
  const pontos = doTipo
    .slice()
    .sort((a, b) => (a.data < b.data ? -1 : a.data > b.data ? 1 : a.id - b.id))
    .map((m) => ({ data: m.data, acumulado: m.valor }));
  return { tipo: tipoPreferido, unidade: doTipo[0].unidade, pontos };
}

async function loadMedidas() {
  const medidas = await apiFetch("/api/medidas");
  // Fase 7 C3a: resposta fora do formato (ex.: {} no lugar de lista) nao derruba a secao.
  if (!Array.isArray(medidas)) return;

  const list = $("#lista-medidas");
  list.innerHTML = "";
  $("#medidas-oculto-visitante").hidden = !modoVisitanteAtivo;
  $("#medidas-vazio").hidden = modoVisitanteAtivo || medidas.length > 0;
  if (modoVisitanteAtivo) {
    $("#grafico-medidas").hidden = true;
    return;
  }

  const tipoJaMostrouTendencia = new Set();

  medidas.forEach((m, idx) => {
    const li = document.createElement("li");
    li.className = "item lista-item";

    const linha = document.createElement("div");
    linha.className = "item-linha";

    const tituloWrap = document.createElement("div");
    const titulo = document.createElement("span");
    titulo.className = "item-titulo";
    titulo.textContent = `${m.tipo}: ${m.valor}${m.unidade}`;
    tituloWrap.appendChild(titulo);

    const quando = document.createElement("span");
    quando.className = "item-quando";
    quando.textContent = fmtDataBr(m.data);
    tituloWrap.appendChild(quando);

    // So o registro mais recente de cada tipo ganha a tendencia (comparado
    // com o registro anterior mais proximo do MESMO tipo) - historico antigo
    // fica so como lista, sem repetir a mesma seta em cada linha.
    if (!tipoJaMostrouTendencia.has(m.tipo)) {
      tipoJaMostrouTendencia.add(m.tipo);
      const anterior = medidas.slice(idx + 1).find((x) => x.tipo === m.tipo);
      if (anterior && anterior.valor !== m.valor) {
        const tendencia = document.createElement("span");
        const subiu = m.valor > anterior.valor;
        const delta = (m.valor - anterior.valor).toFixed(1);
        tendencia.className = `medida-tendencia ${subiu ? "subiu" : "desceu"}`;
        tendencia.textContent = subiu ? `+${delta}` : delta;
        tituloWrap.appendChild(tendencia);
      }
    }
    linha.appendChild(tituloWrap);

    const acoes = document.createElement("div");
    acoes.className = "item-acoes";
    const apagarBtn = document.createElement("button");
    apagarBtn.className = "btn-com-icone";
    apagarBtn.innerHTML = `${ICONE_TRASH}Apagar`;
    apagarBtn.addEventListener("click", async () => {
      apagarBtn.disabled = true;
      const ok = await apiFetch(`/api/medidas/${m.id}`, { method: "DELETE" });
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

  const grafico = $("#grafico-medidas");
  const dadosGrafico = dadosGraficoMedida(medidas);
  grafico.hidden = !dadosGrafico;
  if (dadosGrafico) {
    desenharGraficoLinha(grafico, dadosGrafico.pontos, {
      cor: "var(--cor-financeiro)",
      formatarValor: (v) => `${v}${dadosGrafico.unidade}`,
      altura: 80,
      rotulo: `Evolução de ${dadosGrafico.tipo}`,
    });
  }
}

// Fase 6 US-F2: unidade padrao muda com o tipo escolhido (mesma regra que ja
// existia no backend pra quando a unidade vem vazia - api/medidas, "kg" pra
// peso e "cm" pro resto) - so espelhado aqui pra pre-selecionar sem precisar
// que o Alex troque na mao toda vez.
const MEDIDA_UNIDADE_PADRAO = { peso: "kg", gordura: "%" };

function medidaTipoEscolhido() {
  const sel = $("#medida-tipo-select").value;
  return sel === "outro" ? $("#medida-tipo-outro").value.trim().toLowerCase() : sel;
}

function medidaUnidadeEscolhida() {
  const sel = $("#medida-unidade-select").value;
  return sel === "outra" ? $("#medida-unidade-outra").value.trim() : sel;
}

$("#medida-tipo-select").addEventListener("change", () => {
  const ehOutro = $("#medida-tipo-select").value === "outro";
  $("#medida-tipo-outro").hidden = !ehOutro;
  if (ehOutro) {
    $("#medida-tipo-outro").focus();
    return;
  }
  // Nao pisa numa unidade "outra" que o Alex ja tenha escolhido na mao.
  if ($("#medida-unidade-select").value !== "outra") {
    $("#medida-unidade-select").value = MEDIDA_UNIDADE_PADRAO[$("#medida-tipo-select").value] || "cm";
  }
});

$("#medida-unidade-select").addEventListener("change", () => {
  const ehOutra = $("#medida-unidade-select").value === "outra";
  $("#medida-unidade-outra").hidden = !ehOutra;
  if (ehOutra) $("#medida-unidade-outra").focus();
});

function medidaStepAtual() {
  return Number($("#medida-valor").step) || 0.1;
}

function medidaAjustarValor(delta) {
  const input = $("#medida-valor");
  const atual = Number(input.value) || 0;
  const novo = Math.max(0, Math.round((atual + delta) * 100) / 100);
  input.value = novo;
  pulsarSucesso(input);
}

$("#medida-valor-menos").addEventListener("click", () => medidaAjustarValor(-medidaStepAtual()));
$("#medida-valor-mais").addEventListener("click", () => medidaAjustarValor(medidaStepAtual()));

// Fase 7 V4: botao "Adicionar medida" abre o formulario num bottom-sheet
// (static/js/ui/bottom-sheet.js, faixa V0d). Enquanto essa faixa nao chega na
// integracao, cai no fallback inline (so hidden) - retestado depois do merge
// com origin/fase7/integracao.
$("#medida-abrir-btn").addEventListener("click", () => {
  const sheet = $("#sheet-medida");
  // Fase 7 C3a: toque durante a animacao de fechar (240ms) e ignorado - reabrir nessa
  // janela deixava o sheet preso (bug do V0d anotado no progress da C3a).
  if (sheet.classList.contains("bottom-sheet--fechando")) return;
  if (window.abrirBottomSheet) window.abrirBottomSheet(sheet);
  else sheet.hidden = false;
});

$("#medida-cancelar-btn").addEventListener("click", () => {
  $("#medida-form").reset();
  $("#medida-tipo-outro").hidden = true;
  $("#medida-unidade-outra").hidden = true;
  const sheet = $("#sheet-medida");
  if (window.fecharBottomSheet) window.fecharBottomSheet(sheet);
  else sheet.hidden = true;
});

$("#medida-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#medida-btn");
  const valorInput = $("#medida-valor");
  const tipo = medidaTipoEscolhido();
  const unidade = medidaUnidadeEscolhida();
  const valor = valorInput.value.trim();
  if (!tipo || !valor) {
    mostrarErro("Confere o tipo e o valor da medida.");
    return;
  }

  setBotaoCarregando(btn, true, "salvando...");
  const data = await apiFetch("/api/medidas", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tipo, valor: Number(valor), unidade }),
  });
  setBotaoCarregando(btn, false, "Adicionar");
  if (!data) return;

  valorInput.value = "";
  $("#medida-tipo-outro").value = "";
  $("#medida-unidade-outra").value = "";
  const sheet = $("#sheet-medida");
  if (window.fecharBottomSheet) window.fecharBottomSheet(sheet);
  else sheet.hidden = true;
  pulsarSucesso(valorInput);
  loadMedidas();
});
