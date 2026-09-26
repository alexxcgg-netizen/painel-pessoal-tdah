// static/js/secoes/construtora/cotacoes.js - Secao construtora > cotacoes (HTML: templates/secoes/construtora/cotacoes.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 3283-3525.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadCotacoes() {
  const data = await apiFetch("/api/cotacoes");
  const list = $("#lista-cotacoes");
  list.innerHTML = "";
  if (!Array.isArray(data)) return; // null (erro ja mostrado) ou resposta fora do formato
  $("#cotacoes-oculto-visitante").hidden = !modoVisitanteAtivo;
  $("#cotacoes-vazio").hidden = modoVisitanteAtivo || data.length > 0;
  data.forEach((c) => list.appendChild(criarItemCotacao(c)));
}

// US-F14: grafico de comparacao entre fornecedores - SVG inline no mesmo
// padrao visual dos cards (barras horizontais, cor da secao), so aparece
// com 2+ fornecedores com valor (1 so nao "compara" nada). Mais barato
// primeiro (mesma ordem que list_itens_cotacao ja devolve - ver db.py).
function graficoComparacaoCotacoes(itens) {
  const comValor = itens.filter((i) => typeof i.valor === "number" && Number.isFinite(i.valor));
  if (comValor.length < 2) return null;
  const max = Math.max(...comValor.map((i) => i.valor), 1);
  const alturaLinha = 28;
  const largura = 300;
  const xBarra = 96;
  const larguraMax = largura - xBarra - 58;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "card-grafico cotacao-grafico");
  svg.setAttribute("viewBox", `0 0 ${largura} ${comValor.length * alturaLinha}`);
  svg.setAttribute("role", "img");
  const titulo = comValor.map((i) => `${i.fornecedor || "fornecedor"}: ${fmtMoeda(i.valor)}`).join(", ");
  svg.setAttribute("aria-label", `Comparacao de fornecedores - ${titulo}`);

  // Grade sutil (mesma classe/opacidade do grafico-grid de charts.js - so
  // uma marca de escala no fornecedor mais caro, recessiva, nunca compete
  // com as barras em si).
  const linhaGradeNs = "http://www.w3.org/2000/svg";
  const grade = document.createElementNS(linhaGradeNs, "line");
  grade.setAttribute("x1", String(xBarra + larguraMax));
  grade.setAttribute("y1", "0");
  grade.setAttribute("x2", String(xBarra + larguraMax));
  grade.setAttribute("y2", String(comValor.length * alturaLinha));
  grade.setAttribute("stroke", "var(--border)");
  grade.setAttribute("stroke-width", "1");
  grade.setAttribute("class", "grafico-grid");
  svg.appendChild(grade);

  comValor.forEach((item, i) => {
    const y = i * alturaLinha;
    const w = Math.max(4, (item.valor / max) * larguraMax);
    const nomeBruto = item.fornecedor || "sem nome";
    const nome = nomeBruto.length > 14 ? `${nomeBruto.slice(0, 13)}…` : nomeBruto;
    const ns = "http://www.w3.org/2000/svg";
    const rotulo = document.createElementNS(ns, "text");
    rotulo.setAttribute("class", "card-graf-rotulo");
    rotulo.setAttribute("x", "0");
    rotulo.setAttribute("y", String(y + 18));
    rotulo.textContent = nome;
    const barra = document.createElementNS(ns, "rect");
    barra.setAttribute("class", "card-graf-barra");
    barra.setAttribute("x", String(xBarra));
    barra.setAttribute("y", String(y + 7));
    barra.setAttribute("width", w.toFixed(1));
    barra.setAttribute("height", "13");
    barra.setAttribute("rx", "6.5");
    if (i === 0) barra.classList.add("cotacao-grafico-menor");
    const valor = document.createElementNS(ns, "text");
    valor.setAttribute("class", "card-graf-valor");
    valor.setAttribute("x", (xBarra + w + 6).toFixed(1));
    valor.setAttribute("y", String(y + 18));
    valor.textContent = fmtMoeda(item.valor);
    svg.appendChild(rotulo);
    svg.appendChild(barra);
    svg.appendChild(valor);
  });
  return svg;
}

function criarItemCotacao(c) {
  const li = document.createElement("li");
  li.className = "item cotacao-card";

  const cabecalho = document.createElement("div");
  cabecalho.className = "cotacao-cabecalho";
  cabecalho.tabIndex = 0;
  cabecalho.setAttribute("role", "button");
  cabecalho.setAttribute("aria-expanded", "false");

  const titulo = document.createElement("span");
  titulo.className = "item-titulo";
  titulo.textContent = c.titulo;

  const resumo = document.createElement("span");
  resumo.className = "item-quando";
  resumo.textContent =
    c.total_itens === 0
      ? "nenhum fornecedor ainda"
      : `${c.total_itens} fornecedor(es)` +
        (c.menor_valor != null ? ` - menor: ${fmtMoeda(c.menor_valor)}` : "");

  cabecalho.appendChild(titulo);
  cabecalho.appendChild(resumo);
  li.appendChild(cabecalho);

  const detalhe = document.createElement("div");
  detalhe.className = "cotacao-detalhe";
  detalhe.hidden = true;
  li.appendChild(detalhe);

  let carregado = false;
  const abrirFechar = async () => {
    detalhe.hidden = !detalhe.hidden;
    cabecalho.setAttribute("aria-expanded", String(!detalhe.hidden));
    if (!detalhe.hidden && !carregado) {
      carregado = true;
      await preencherDetalheCotacao(c.id, detalhe);
    }
  };
  cabecalho.addEventListener("click", abrirFechar);
  cabecalho.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      abrirFechar();
    }
  });

  return li;
}

async function preencherDetalheCotacao(cotacaoId, container) {
  container.textContent = "Carregando...";
  const data = await apiFetch(`/api/cotacoes/${cotacaoId}`);
  if (!data || !Array.isArray(data.itens)) {
    container.textContent = "";
    return;
  }
  container.innerHTML = "";

  if (data.itens.length === 0) {
    const vazio = document.createElement("p");
    vazio.className = "dica-metas";
    vazio.textContent = "Nenhum fornecedor registrado ainda.";
    container.appendChild(vazio);
  } else {
    const listaItens = document.createElement("ul");
    listaItens.className = "cotacao-itens";
    data.itens.forEach((item, i) => {
      const itemLi = document.createElement("li");
      itemLi.className = "cotacao-item" + (i === 0 && item.valor != null ? " cotacao-item-menor" : "");

      // Fornecedor a esquerda, valor em mono/tabular a direita (MASTER 7:
      // numero que o olho compara) - so apresentacao, o valor vem pronto.
      const texto = document.createElement("span");
      texto.className = "cotacao-item-texto";
      const nome = document.createElement("span");
      nome.className = "cotacao-item-fornecedor";
      nome.textContent = item.fornecedor || "fornecedor sem nome";
      texto.appendChild(nome);
      if (item.prazo_texto) {
        const prazo = document.createElement("span");
        prazo.className = "cotacao-item-prazo";
        prazo.textContent = item.prazo_texto;
        texto.appendChild(prazo);
      }
      itemLi.appendChild(texto);
      const valorEl = document.createElement("span");
      valorEl.className = "cotacao-item-valor";
      valorEl.textContent = item.valor != null ? fmtMoeda(item.valor) : "sem valor";
      itemLi.appendChild(valorEl);

      const btnApagar = document.createElement("button");
      btnApagar.type = "button";
      btnApagar.className = "cotacao-item-apagar";
      btnApagar.setAttribute("aria-label", `Apagar ${item.fornecedor || "fornecedor"}`);
      btnApagar.innerHTML =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg>';
      btnApagar.addEventListener("click", async () => {
        btnApagar.disabled = true;
        const ok = await apiFetch(`/api/cotacoes/${cotacaoId}/itens/${item.id}`, { method: "DELETE" });
        if (!ok) {
          btnApagar.disabled = false;
          return;
        }
        preencherDetalheCotacao(cotacaoId, container);
        loadCotacoes();
      });
      itemLi.appendChild(btnApagar);
      listaItens.appendChild(itemLi);
    });
    container.appendChild(listaItens);

    const grafico = graficoComparacaoCotacoes(data.itens);
    if (grafico) {
      const graficoBox = document.createElement("div");
      graficoBox.className = "grafico-card cotacao-grafico-box";
      const graficoTitulo = document.createElement("p");
      graficoTitulo.className = "grafico-titulo";
      graficoTitulo.textContent = "Comparacao entre fornecedores";
      graficoBox.appendChild(graficoTitulo);
      graficoBox.appendChild(grafico);
      container.appendChild(graficoBox);
    }
  }

  const formItem = document.createElement("form");
  formItem.className = "form-linha cotacao-add-form";
  const inputFornecedor = document.createElement("input");
  inputFornecedor.type = "text";
  inputFornecedor.className = "campo";
  inputFornecedor.placeholder = "Fornecedor";
  inputFornecedor.setAttribute("aria-label", "Fornecedor");
  inputFornecedor.maxLength = 120;
  inputFornecedor.required = true;
  const inputValor = document.createElement("input");
  inputValor.type = "text";
  inputValor.className = "campo";
  inputValor.inputMode = "decimal";
  inputValor.placeholder = "Valor R$";
  inputValor.setAttribute("aria-label", "Valor em reais");
  inputValor.maxLength = 18;
  inputValor.required = true;
  const btnAdd = document.createElement("button");
  btnAdd.type = "submit";
  btnAdd.className = "btn btn-secundario";
  btnAdd.textContent = "Adicionar";
  btnAdd.setAttribute("aria-label", "Adicionar fornecedor");
  formItem.appendChild(inputFornecedor);
  formItem.appendChild(inputValor);
  formItem.appendChild(btnAdd);
  formItem.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const fornecedor = inputFornecedor.value.trim();
    const valor = parseFloat(inputValor.value.trim().replace(",", "."));
    if (!fornecedor || Number.isNaN(valor)) return;
    if (!Number.isFinite(valor) || valor < 0) {
      mostrarErro("Valor inválido - use um número positivo (ex: 4200,50).");
      return;
    }
    setBotaoCarregando(btnAdd, true, "salvando...");
    const r = await apiFetch(`/api/cotacoes/${cotacaoId}/itens`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fornecedor, valor }),
    });
    setBotaoCarregando(btnAdd, false, "Adicionar");
    if (r) {
      preencherDetalheCotacao(cotacaoId, container);
      loadCotacoes();
    }
  });
  container.appendChild(formItem);

  const uploadLabel = document.createElement("label");
  uploadLabel.className = "cotacao-upload-label";
  const uploadTexto = document.createElement("span");
  uploadTexto.textContent = "Anexar PDF do orcamento";
  const uploadInput = document.createElement("input");
  uploadInput.type = "file";
  uploadInput.accept = "application/pdf";
  uploadLabel.appendChild(uploadTexto);
  uploadLabel.appendChild(uploadInput);
  uploadInput.addEventListener("change", async () => {
    const arquivo = uploadInput.files[0];
    if (!arquivo) return;
    uploadTexto.textContent = "Lendo PDF...";
    const form = new FormData();
    form.append("arquivo", arquivo);
    const r = await apiFetch(`/api/cotacoes/${cotacaoId}/itens/pdf`, { method: "POST", body: form });
    if (r) {
      preencherDetalheCotacao(cotacaoId, container);
      loadCotacoes();
    } else {
      uploadTexto.textContent = "Anexar PDF do orcamento";
    }
  });
  container.appendChild(uploadLabel);
}

// Fase 7 (V5-extra/C3b): "Nova cotacao" abre o formulario no bottom-sheet
// compartilhado (static/js/ui/bottom-sheet.js, V0d). Fallback so pro caso de
// o componente nao ter carregado: alterna o atributo hidden.
function abrirPainelCotacao() {
  const sheet = $("#cotacao-sheet");
  if (typeof levarSheetProBody === "function") levarSheetProBody(sheet); // ver secoes/vida/viagens.js
  if (typeof window.abrirBottomSheet === "function") window.abrirBottomSheet(sheet);
  else sheet.hidden = false;
}

function fecharPainelCotacao() {
  const sheet = $("#cotacao-sheet");
  if (typeof window.fecharBottomSheet === "function") window.fecharBottomSheet(sheet);
  else sheet.hidden = true;
}

$("#cotacao-abrir-btn").addEventListener("click", abrirPainelCotacao);
$("#cotacao-cancelar-btn").addEventListener("click", () => {
  $("#cotacao-form").reset();
  fecharPainelCotacao();
});

$("#cotacao-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("#cotacao-titulo");
  const btn = $("#cotacao-btn");
  const titulo = input.value.trim();
  if (!titulo || btn.disabled) return;
  setBotaoCarregando(btn, true, "salvando...");
  const r = await apiFetch("/api/cotacoes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ titulo }),
  });
  setBotaoCarregando(btn, false, "Salvar cotacao");
  if (r) {
    input.value = "";
    fecharPainelCotacao();
    loadCotacoes();
  }
});
