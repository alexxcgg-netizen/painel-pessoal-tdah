// static/js/secoes/gastos/gastos.js - Secao gastos > gastos (HTML: templates/secoes/gastos/gastos.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 456-562, app.js 2703-2902, vida.js 1741-1755.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

// Nota fiscal por foto (US-C8/US-C9) ----------------------------------------

function lerArquivoComoBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

function mostrarConfirmacaoNotaFiscal(dados) {
  $("#nf-valor").value = dados.valor != null ? dados.valor : "";
  $("#nf-estabelecimento").value = dados.estabelecimento || "";
  $("#nf-data").value = dados.data || "";
  $("#nf-categoria").value = "";
  $("#nota-fiscal-status").textContent =
    dados.valor == null || !dados.estabelecimento
      ? "Nao consegui ler tudo com certeza na foto - confere/completa antes de salvar."
      : "Confere os dados da nota antes de salvar.";
  $("#nota-fiscal-confirmacao").hidden = false;
}

const notaFiscalInput = $("#nota-fiscal-input");
if (notaFiscalInput) {
  notaFiscalInput.addEventListener("change", async (e) => {
    const file = e.target.files && e.target.files[0];
    e.target.value = ""; // permite escolher a mesma foto de novo depois
    if (!file) return;

    const label = $("#nota-fiscal-label");
    const htmlOriginal = label.innerHTML;
    label.innerHTML = `<span class="spinner"></span><span>Lendo a nota...</span>`;
    let imagemBase64;
    try {
      imagemBase64 = await lerArquivoComoBase64(file);
    } catch {
      label.innerHTML = htmlOriginal;
      mostrarErro("Nao consegui ler essa foto. Tenta de novo.");
      return;
    }

    const clientId = crypto.randomUUID ? crypto.randomUUID() : `nf-${Date.now()}`;
    const data = await apiFetch(
      "/api/notas-fiscais/extrair",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ imagem_base64: imagemBase64, media_type: file.type || "image/jpeg" }),
      },
      { tipo: "nota_fiscal_extrair", id: clientId }
    );
    label.innerHTML = htmlOriginal;
    if (!data) return; // erro real ja mostrado por apiFetch
    if (data.__enfileirado) {
      $("#nota-fiscal-status").textContent = "Sem conexao - a foto foi salva e vai ler assim que voltar.";
      $("#nota-fiscal-confirmacao").hidden = true;
      return;
    }
    mostrarConfirmacaoNotaFiscal(data);
  });
}

const nfConfirmarBtn = $("#nf-confirmar-btn");
if (nfConfirmarBtn) {
  nfConfirmarBtn.addEventListener("click", async () => {
    const valor = parseFloat($("#nf-valor").value);
    const estabelecimento = $("#nf-estabelecimento").value.trim();
    if (!estabelecimento || !(valor > 0)) {
      mostrarErro("Preenche valor (maior que zero) e estabelecimento antes de salvar.");
      return;
    }
    setBotaoCarregando(nfConfirmarBtn, true, "Salvando...");
    const data = await apiFetch("/api/notas-fiscais/confirmar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        valor,
        estabelecimento,
        data: $("#nf-data").value || null,
        categoria: $("#nf-categoria").value || null,
      }),
    });
    setBotaoCarregando(nfConfirmarBtn, false, "Confirmar e salvar");
    if (!data) return;
    // US-D3: faltava a mesma micro-interacao de confirmacao que todo outro
    // formulario ja tem (pulsarSucesso, animacao pulseBorda em CSS aplicada
    // so a input dentro de .form-linha - #nf-valor serve). Pulsa e espera
    // um instante antes de esconder a caixa (mesmo tempo ja usado no
    // "saindo" de item apagado/convertido nas listas) pra confirmacao ficar
    // visivel antes do formulario sumir, em vez de sumir na hora sem feedback.
    pulsarSucesso($("#nf-valor"));
    setTimeout(() => {
      $("#nota-fiscal-confirmacao").hidden = true;
    }, 250);
    loadExpenses();
    loadUso();
  });
}

const nfCancelarBtn = $("#nf-cancelar-btn");
if (nfCancelarBtn) {
  nfCancelarBtn.addEventListener("click", () => {
    $("#nota-fiscal-confirmacao").hidden = true;
  });
}

// Categoria errada e o caso mais comum de corrigir (a IA acerta o "e um
// gasto" quase sempre, erra mais na categoria) - por isso a propria tag vira
// um <select> ali mesmo, sem sair do card: um toque abre, outro escolhe.
function criarSeletorCategoriaGasto(e, cat, li) {
  const select = document.createElement("select");
  select.className = "correcao-select correcao-select-categoria";
  CATEGORIAS_GASTO.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c;
    opt.textContent = c;
    if (c === e.category) opt.selected = true;
    select.appendChild(opt);
  });
  select.addEventListener("click", (ev) => ev.stopPropagation());
  select.addEventListener("blur", () => {
    if (select.parentElement) select.replaceWith(cat);
  });
  select.addEventListener("change", async () => {
    const categoriaNova = select.value;
    if (categoriaNova === e.category) {
      select.replaceWith(cat);
      return;
    }
    select.disabled = true;
    const data = await apiFetch(`/api/expenses/${e.id}/categoria`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ categoria: categoriaNova }),
    });
    if (data) loadExpenses();
    else select.disabled = false;
  });
  return select;
}

function criarItemGasto(e) {
  const li = document.createElement("li");
  li.className = "item" + (e.tipo === "planejado" ? " item-planejado" : "");
  li.dataset.entidade = "gasto"; // destino do link de card (Fase 6)
  li.dataset.id = e.id;

  const linha = document.createElement("div");
  linha.className = "item-linha";

  const info = document.createElement("div");
  const valor = document.createElement("span");
  valor.className = "gasto-valor";
  valor.textContent = fmtMoeda(e.amount);
  const cat = document.createElement("span");
  cat.className = "gasto-categoria chip";
  cat.dataset.cat = e.category;
  cat.textContent = e.category;
  cat.title = "toque pra corrigir a categoria";
  cat.addEventListener("click", () => {
    const select = criarSeletorCategoriaGasto(e, cat, li);
    cat.replaceWith(select);
    select.focus();
  });
  info.appendChild(valor);
  info.appendChild(cat);
  if (e.tipo === "planejado") {
    const badge = document.createElement("span");
    badge.className = "badge-planejado";
    badge.textContent = "planejado";
    info.appendChild(badge);
  }
  if (e.description) {
    const desc = document.createElement("span");
    desc.className = "item-quando";
    desc.textContent = e.description;
    info.appendChild(desc);
  }

  const acoes = document.createElement("div");
  acoes.className = "item-acoes";
  const btnCorrigirTipo = document.createElement("button");
  btnCorrigirTipo.className = "btn-com-icone";
  btnCorrigirTipo.title = "isso nao e um gasto?";
  btnCorrigirTipo.innerHTML = `${ICONE_CORRIGIR}e tarefa`;
  btnCorrigirTipo.addEventListener("click", async () => {
    setBotaoCarregando(btnCorrigirTipo, true, "corrigindo...");
    const data = await apiFetch(`/api/expenses/${e.id}/reclassificar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    if (data) {
      li.classList.add("saindo");
      setTimeout(() => {
        loadExpenses();
        loadTasks();
      }, 220);
    } else {
      setBotaoCarregando(btnCorrigirTipo, false, "e tarefa");
    }
  });
  acoes.appendChild(btnCorrigirTipo);

  linha.appendChild(info);
  linha.appendChild(acoes);
  li.appendChild(linha);
  return li;
}

async function loadExpenses() {
  const expenses = await apiFetch("/api/expenses");
  if (!expenses) return;
  const list = $("#lista-gastos");
  list.innerHTML = "";
  $("#gastos-oculto-visitante").hidden = !modoVisitanteAtivo;
  $("#gastos-vazio").hidden = modoVisitanteAtivo || expenses.length > 0;
  expenses.forEach((e) => list.appendChild(criarItemGasto(e)));

  const historico = await apiFetch("/api/expenses/historico?dias=14");
  if (historico) {
    desenharGraficoBarras($("#grafico-gastos"), historico, {
      cor: "var(--cor-financeiro)",
      formatarValor: fmtMoeda,
      rotulo: "Gasto diario nos ultimos 14 dias",
    });
  }

  loadResumoSemanal();
  loadCustoIA();
}

function preencherCustoIA(data) {
  if (!data) return;
  $("#custo-ia-box").hidden = false;
  $("#custo-ia-mes").textContent = `${fmtUSD(data.mes_atual_usd)} esse mes`;
  $("#custo-ia-30dias").textContent = `Ultimos 30 dias: ${fmtUSD(data.ultimos_30_dias_usd)}.`;

  const inputTeto = $("#custo-ia-teto-input");
  if (document.activeElement !== inputTeto) {
    inputTeto.value = data.teto_mensal_usd ?? "";
  }

  const aviso = $("#custo-ia-teto-aviso");
  if (data.teto_estourado) {
    aviso.textContent =
      "Teto estourado esse mes - o classificador de intent (navegacao por voz) vai preferir " +
      "resolver por padrao ja aprendido em vez de chamar a IA, ate o mes virar.";
    aviso.hidden = false;
  } else if (data.teto_perto) {
    aviso.textContent = `Perto do teto mensal (ja usou ${Math.round(data.fracao_teto * 100)}%).`;
    aviso.hidden = false;
  } else {
    aviso.hidden = true;
  }
}

async function loadCustoIA() {
  preencherCustoIA(await apiFetch("/api/ia/custo"));
}

$("#custo-ia-teto-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("#custo-ia-teto-input");
  const btn = $("#custo-ia-teto-btn");
  const bruto = input.value.trim();
  const teto_mensal_usd = bruto === "" ? null : Number(bruto);

  setBotaoCarregando(btn, true, "salvando...");
  const data = await apiFetch("/api/ia/teto", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ teto_mensal_usd }),
  });
  setBotaoCarregando(btn, false, "Salvar");
  if (!data) return;
  preencherCustoIA(data);
  pulsarSucesso(input);
});

async function loadResumoSemanal() {
  const data = await apiFetch("/api/gastos/resumo-semanal");
  const box = $("#resumo-semanal-box");
  if (!data || data.total_semana <= 0) {
    box.hidden = true;
    return;
  }

  $("#resumo-semanal-total").textContent = fmtMoeda(data.total_semana);

  const partes = [];
  if (data.variacao_pct !== null) {
    partes.push(
      data.variacao_pct >= 0
        ? `${data.variacao_pct}% a mais que a semana passada`
        : `${Math.abs(data.variacao_pct)}% a menos que a semana passada`
    );
  }
  if (data.categoria_top) {
    partes.push(`maior peso: ${data.categoria_top} (${fmtMoeda(data.categoria_top_valor)})`);
  }
  $("#resumo-semanal-detalhe").textContent = partes.join(" - ");

  box.hidden = false;
}

async function loadFimMes() {
  const s = await apiFetch("/api/sobra-do-mes");
  if (!s || !s.projecao) return;
  const semDado = !s.renda_mes && !s.gasto_mes;
  $("#fim-mes-box").hidden = semDado;
  if (semDado) return;
  const p = s.projecao;
  $("#fim-mes-dias").textContent = `faltam ${p.dias_restantes} dia(s)`;
  $("#fim-mes-agora").textContent = `Agora: ${fmtMoeda(s.renda_mes)} entrou, ${fmtMoeda(s.gasto_mes)} saiu - sobra ${fmtMoeda(s.sobra)}.`;
  const contas = p.contas_pendentes ? ` (com ${fmtMoeda(p.contas_pendentes)} de contas que ainda vencem)` : "";
  $("#fim-mes-projecao").textContent = `No ritmo de ${fmtMoeda(p.ritmo_diario)}/dia, deve sobrar ${fmtMoeda(p.sobra_projetada)} no fim do mes${contas}.`;
}

// ---- Fase 5 (US-C22): sinal de sobrecarga ----
