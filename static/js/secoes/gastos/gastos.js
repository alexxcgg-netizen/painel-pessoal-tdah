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
  valor.textContent = fmtMoedaFinancas(e.amount);
  // Fase 7 (C3c): <button> de verdade (teclado/leitor de tela), visual de chip
  // compacto com area de toque de 44px completada por ::after (gastos.css).
  // Fase 8 (F1): gasto de origem bancaria (sem e.id, veio de bank_transactions)
  // nao tem rota /api/expenses/<id>/... pra editar - chip vira so exibicao.
  const editavel = e.origem === undefined || e.origem === "manual";
  const cat = document.createElement(editavel ? "button" : "span");
  if (editavel) cat.type = "button";
  cat.className = "gasto-categoria chip chip--compacto";
  cat.dataset.cat = e.category;
  cat.textContent = e.category;
  if (editavel) {
    cat.title = "toque pra corrigir a categoria";
    cat.setAttribute("aria-label", `Categoria ${e.category}: toque pra corrigir`);
    cat.addEventListener("click", () => {
      const select = criarSeletorCategoriaGasto(e, cat, li);
      cat.replaceWith(select);
      select.focus();
    });
  }
  info.appendChild(valor);
  info.appendChild(cat);
  if (e.tipo === "planejado") {
    const badge = document.createElement("span");
    badge.className = "badge-planejado";
    badge.textContent = "planejado";
    info.appendChild(badge);
  }
  // Fase 8 (F1): selo de origem - "manual" (digitado) ou o nome do banco
  // (ex: "Nubank", sincronizado automatico). Reusa a classe badge-planejado
  // (ja usa var(--cor-bancos)) em vez de criar cor nova.
  if (e.origem) {
    const origem = document.createElement("span");
    origem.className = "badge-planejado";
    origem.textContent = e.origem === "manual" ? "manual" : e.origem;
    info.appendChild(origem);
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
  btnCorrigirTipo.type = "button";
  btnCorrigirTipo.className = "btn btn-secundario btn-com-icone btn-corrigir-gasto";
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
  if (editavel) acoes.appendChild(btnCorrigirTipo);

  linha.appendChild(info);
  linha.appendChild(acoes);
  li.appendChild(linha);
  return li;
}

// Fase 9 (f9-ui): botao unico de sincronizacao da aba Financas - bate na
// rota que le PLUGGY_ITEM_ID_NUBANK do .env (rotas/f8_banco.py, nao e meu).
// Resposta esperada: {ok, novas, atualizadas, sem_mudanca, mensagem}.
const btnSincronizarNubank = $("#btn-sincronizar-nubank");
if (btnSincronizarNubank) {
  btnSincronizarNubank.addEventListener("click", async () => {
    const status = $("#sincronizar-nubank-status");
    setBotaoCarregando(btnSincronizarNubank, true, "Sincronizando...");
    status.hidden = true;
    const data = await apiFetch("/api/bancos/sincronizar-nubank", { method: "POST" });
    setBotaoCarregando(btnSincronizarNubank, false, "Sincronizar");
    if (data) {
      const n = (v) => numeroFinancas(v) ?? 0;
      status.textContent =
        typeof data.mensagem === "string" && data.mensagem
          ? data.mensagem
          : `${n(data.novas)} nova(s), ${n(data.atualizadas)} atualizada(s), ${n(data.sem_mudanca)} sem mudanca.`;
      status.hidden = false;
      loadExpenses();
      loadBancos();
      if (typeof loadResumoFinancas === "function") loadResumoFinancas();
      if (typeof loadExtratoFinancas === "function") loadExtratoFinancas();
    }
  });
}

// Fase 9 (f9-ui): resumo do topo (GET /api/financas/resumo) - substitui o uso
// de /api/patrimonio na interface. Fatura e saldo nunca sao somados - sao
// mostrados separados, porque fatura e divida, nao dinheiro disponivel.
async function loadResumoFinancas() {
  const resumo = await apiFetch("/api/financas/resumo");
  const box = $("#resumo-financas-box");
  if (!resumo || typeof resumo !== "object") {
    if (box) box.hidden = true;
    return;
  }
  $("#resumo-financas-mes").textContent = typeof resumo.mes === "string" ? resumo.mes : "";
  $("#resumo-financas-gasto").textContent = fmtMoedaFinancas(resumo.gasto_mes);
  $("#resumo-financas-fatura").textContent = fmtMoedaFinancas(resumo.fatura_atual);
  $("#resumo-financas-saldo").textContent = fmtMoedaFinancas(resumo.saldo_conta);
  $("#resumo-financas-patrimonio").textContent = fmtMoedaFinancas(resumo.patrimonio);
  box.hidden = false;
}

// Fase 9 (f9-ui): extrato paginado de 15 em 15 dias (GET /api/financas/extrato)
// - contrato implementado em paralelo por outra faixa (rotas/f9_financas.py).
let extratoFinancasProximoAntes = null;

function criarItemExtratoFinancas(item) {
  const li = document.createElement("li");
  li.className = "item";

  const linha = document.createElement("div");
  linha.className = "item-linha";

  const info = document.createElement("div");
  const titulo = document.createElement("span");
  titulo.className = "item-titulo";
  titulo.textContent = item.descricao || "(sem descricao)";
  const origemChip = document.createElement("span");
  origemChip.className = "chip chip--compacto";
  origemChip.textContent = item.origem === "Nubank" ? "Nubank" : "manual";
  titulo.appendChild(origemChip);
  if (item.tipo_conta) {
    const tipoChip = document.createElement("span");
    tipoChip.className = "chip chip--compacto";
    tipoChip.textContent = item.tipo_conta === "cartao" ? "cartao" : "conta";
    titulo.appendChild(tipoChip);
  }
  if (item.estorno_de) {
    const estornoChip = document.createElement("span");
    estornoChip.className = "chip chip--compacto";
    estornoChip.textContent = "estorno";
    titulo.appendChild(estornoChip);
  }
  info.appendChild(titulo);

  const detalhe = document.createElement("span");
  detalhe.className = "item-quando";
  detalhe.textContent = [item.data, item.categoria].filter(Boolean).join(" · ");
  info.appendChild(detalhe);
  linha.appendChild(info);

  const valor = document.createElement("span");
  const numero = numeroFinancas(item.valor) ?? 0;
  valor.className = "valor-mono" + (numero < 0 ? " banco-saldo-negativo" : "");
  valor.textContent = fmtMoedaFinancas(numero);
  linha.appendChild(valor);

  li.appendChild(linha);
  return li;
}

async function loadExtratoFinancas(antes, acumular) {
  const btnMais = $("#btn-carregar-mais-extrato");
  const params = new URLSearchParams({ dias: "15" });
  if (antes) params.set("antes", antes);
  const resposta = await apiFetch(`/api/financas/extrato?${params.toString()}`);
  const list = $("#lista-extrato-financas");
  if (!resposta || !Array.isArray(resposta.itens)) {
    if (!acumular) {
      list.innerHTML = "";
      $("#extrato-financas-vazio").hidden = false;
    }
    if (btnMais) btnMais.hidden = true;
    return;
  }
  if (!acumular) list.innerHTML = "";
  $("#extrato-financas-vazio").hidden = list.children.length > 0 || resposta.itens.length > 0;
  resposta.itens.forEach((item) => list.appendChild(criarItemExtratoFinancas(item)));
  extratoFinancasProximoAntes = resposta.proximo_antes || null;
  if (btnMais) btnMais.hidden = !extratoFinancasProximoAntes;
}

const btnCarregarMaisExtrato = $("#btn-carregar-mais-extrato");
if (btnCarregarMaisExtrato) {
  btnCarregarMaisExtrato.addEventListener("click", async () => {
    if (!extratoFinancasProximoAntes) return;
    setBotaoCarregando(btnCarregarMaisExtrato, true, "Carregando...");
    await loadExtratoFinancas(extratoFinancasProximoAntes, true);
    setBotaoCarregando(btnCarregarMaisExtrato, false, "Carregar mais 15 dias");
  });
}

// Fase 8 (F2): "Proximas cobrancas" (assinaturas + parcelas da Fase 7) no
// topo da lista unificada de gastos. A data ja vem calculada do backend
// (financas_recorrentes.proximas_cobrancas) - aqui e so exibicao.
function criarItemGastosProximaCobranca(c) {
  const li = document.createElement("li");
  li.className = "item";
  li.dataset.entidade = c.tipo === "assinatura" ? "assinatura" : "compra_parcelada";
  li.dataset.id = c.id;

  const linha = document.createElement("div");
  linha.className = "item-linha";

  const info = document.createElement("div");
  const valor = document.createElement("span");
  valor.className = "gasto-valor";
  valor.textContent = fmtMoedaFinancas(c.valor);
  info.appendChild(valor);

  const nome = document.createElement("span");
  nome.className = "gasto-categoria chip chip--compacto";
  nome.textContent = c.nome || c.descricao || "";
  info.appendChild(nome);

  const quando = document.createElement("span");
  quando.className = "item-quando";
  quando.textContent = c.label || "";
  info.appendChild(quando);

  if (c.duplicado) {
    const aviso = document.createElement("span");
    aviso.className = "badge-planejado";
    aviso.textContent = c.aviso || "possível duplicidade";
    info.appendChild(aviso);
  }

  linha.appendChild(info);
  li.appendChild(linha);
  return li;
}

async function loadGastosProximasCobrancas() {
  const cobrancas = await apiFetch("/api/gastos/proximas-cobrancas");
  const box = $("#gastos-proximas-cobrancas-box");
  const list = $("#gastos-lista-proximas-cobrancas");
  if (!box || !list) return;
  if (!Array.isArray(cobrancas) || cobrancas.length === 0 || modoVisitanteAtivo) {
    box.hidden = true;
    return;
  }
  list.innerHTML = "";
  cobrancas.forEach((c) => list.appendChild(criarItemGastosProximaCobranca(c)));
  box.hidden = false;
}

async function loadExpenses() {
  // Fase 8 (F1): lista unificada (manual + banco), cada item com "origem".
  const expenses = await apiFetch("/api/gastos/unificados");
  if (!Array.isArray(expenses)) return;
  const list = $("#lista-gastos");
  list.innerHTML = "";
  $("#gastos-oculto-visitante").hidden = !modoVisitanteAtivo;
  $("#gastos-vazio").hidden = modoVisitanteAtivo || expenses.length > 0;
  expenses.forEach((e) => list.appendChild(criarItemGasto(e)));
  loadGastosProximasCobrancas();

  const historicoBruto = await apiFetch("/api/expenses/historico?dias=14");
  // Fase 7 (C3c): ponto sem total numerico viraria <rect height="NaN"> (erro
  // de console) - descarta antes de desenhar.
  const historico = Array.isArray(historicoBruto)
    ? historicoBruto
        .filter((d) => d && typeof d.data === "string")
        .map((d) => ({ ...d, total: numeroFinancas(d.total) || 0 }))
    : null;
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
  if (!data || typeof data !== "object") return;
  // Fase 7 (C3c): fmtUSD(undefined) viraria "$NaN".
  const usd = (v) => (numeroFinancas(v) === null ? "\u2014" : fmtUSD(v));
  $("#custo-ia-box").hidden = false;
  $("#custo-ia-mes").textContent = `${usd(data.mes_atual_usd)} esse mes`;
  $("#custo-ia-30dias").textContent = `Ultimos 30 dias: ${usd(data.ultimos_30_dias_usd)}.`;

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
    const fracao = numeroFinancas(data.fracao_teto);
    aviso.textContent = fracao === null ? "Perto do teto mensal." : `Perto do teto mensal (ja usou ${Math.round(fracao * 100)}%).`;
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
  setBotaoCarregando(btn, false, "Salvar teto");
  if (!data) return;
  preencherCustoIA(data);
  pulsarSucesso(input);
});

async function loadResumoSemanal() {
  const data = await apiFetch("/api/gastos/resumo-semanal");
  const box = $("#resumo-semanal-box");
  const total = data && typeof data === "object" ? numeroFinancas(data.total_semana) : null;
  if (total === null || total <= 0) {
    box.hidden = true;
    return;
  }

  $("#resumo-semanal-total").textContent = fmtMoedaFinancas(total);

  const partes = [];
  const variacao = numeroFinancas(data.variacao_pct);
  if (variacao !== null) {
    partes.push(variacao >= 0 ? `${variacao}% a mais que a semana passada` : `${Math.abs(variacao)}% a menos que a semana passada`);
  }
  if (typeof data.categoria_top === "string" && data.categoria_top) {
    if (partes.length) partes.push(" \u00b7 ");
    partes.push(`maior peso: ${data.categoria_top} (`, { r: data.categoria_top_valor }, ")");
  }
  preencherLinhaComValores($("#resumo-semanal-detalhe"), partes);

  box.hidden = false;
}

async function loadFimMes() {
  const s = await apiFetch("/api/sobra-do-mes");
  if (!s || !s.projecao) return;
  const semDado = !s.renda_mes && !s.gasto_mes;
  $("#fim-mes-box").hidden = semDado;
  if (semDado) return;
  const p = s.projecao;
  const dias = numeroFinancas(p.dias_restantes);
  $("#fim-mes-dias").textContent = dias === null ? "" : `faltam ${dias} dia(s)`;
  preencherLinhaComValores($("#fim-mes-agora"), [
    "Agora: ", { r: s.renda_mes }, " entrou, ", { r: s.gasto_mes }, " saiu \u00b7 sobra ", { r: s.sobra }, ".",
  ]);
  const partes = ["No ritmo de ", { r: p.ritmo_diario }, "/dia, deve sobrar ", { r: p.sobra_projetada }, " no fim do mes"];
  if (numeroFinancas(p.contas_pendentes)) partes.push(" (com ", { r: p.contas_pendentes }, " de contas que ainda vencem)");
  partes.push(".");
  preencherLinhaComValores($("#fim-mes-projecao"), partes);
}

// Fase 7 (C3c): frase com valores em R$ - o texto fica na fonte de texto e
// cada valor num <span class="valor-mono"> (MASTER #7, numero em mono). So
// textContent/createTextNode, nada de innerHTML com dado.
function preencherLinhaComValores(el, partes) {
  el.textContent = "";
  partes.forEach((parte) => {
    if (parte && typeof parte === "object") el.appendChild(criarEl("span", "valor-mono", fmtMoedaFinancas(parte.r)));
    else el.appendChild(document.createTextNode(String(parte)));
  });
}

// ---- Fase 5 (US-C22): sinal de sobrecarga ----
