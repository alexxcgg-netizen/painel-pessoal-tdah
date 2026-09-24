// static/js/secoes/construtora/cotacoes.js - Secao construtora > cotacoes (HTML: templates/secoes/construtora/cotacoes.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 3283-3525.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadCotacoes() {
  const data = await apiFetch("/api/cotacoes");
  const list = $("#lista-cotacoes");
  list.innerHTML = "";
  if (!data) return;
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
  if (!data) {
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

      const texto = document.createElement("span");
      const partes = [item.fornecedor || "fornecedor sem nome"];
      partes.push(item.valor != null ? fmtMoeda(item.valor) : "sem valor");
      if (item.prazo_texto) partes.push(item.prazo_texto);
      texto.textContent = partes.join(" - ");
      itemLi.appendChild(texto);

      const btnApagar = document.createElement("button");
      btnApagar.type = "button";
      btnApagar.className = "cotacao-item-apagar";
      btnApagar.setAttribute("aria-label", "Apagar item");
      btnApagar.textContent = "×";
      btnApagar.addEventListener("click", async () => {
        await apiFetch(`/api/cotacoes/${cotacaoId}/itens/${item.id}`, { method: "DELETE" });
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
  inputFornecedor.placeholder = "Fornecedor";
  inputFornecedor.required = true;
  const inputValor = document.createElement("input");
  inputValor.type = "text";
  inputValor.inputMode = "decimal";
  inputValor.placeholder = "Valor R$";
  inputValor.required = true;
  const btnAdd = document.createElement("button");
  btnAdd.type = "submit";
  btnAdd.className = "btn btn-secundario btn-com-icone";
  btnAdd.textContent = "+ Adicionar";
  formItem.appendChild(inputFornecedor);
  formItem.appendChild(inputValor);
  formItem.appendChild(btnAdd);
  formItem.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const fornecedor = inputFornecedor.value.trim();
    const valor = parseFloat(inputValor.value.trim().replace(",", "."));
    if (!fornecedor || Number.isNaN(valor)) return;
    const r = await apiFetch(`/api/cotacoes/${cotacaoId}/itens`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fornecedor, valor }),
    });
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

// Fase 7 (V5-extra): botao "Nova cotacao" abre o formulario num bottom-sheet
// (contrato: docs/agentes/fase7-visual.md). Usa window.abrirBottomSheet/
// fecharBottomSheet (faixa V0d) quando existir; fallback minimo enquanto
// essa faixa nao chega na integracao (mesmo padrao de secoes/vida/habitos.js
// e secoes/vida/viagens.js).
function abrirPainelCotacao() {
  const sheet = $("#cotacao-sheet");
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
$("#cotacao-sheet").addEventListener("click", (e) => {
  if (typeof window.abrirBottomSheet !== "function" && e.target === e.currentTarget) fecharPainelCotacao();
});
document.addEventListener("keydown", (e) => {
  if (typeof window.abrirBottomSheet !== "function" && e.key === "Escape" && !$("#cotacao-sheet").hidden) fecharPainelCotacao();
});

$("#cotacao-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("#cotacao-titulo");
  const titulo = input.value.trim();
  if (!titulo) return;
  const r = await apiFetch("/api/cotacoes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ titulo }),
  });
  if (r) {
    input.value = "";
    fecharPainelCotacao();
    loadCotacoes();
  }
});
