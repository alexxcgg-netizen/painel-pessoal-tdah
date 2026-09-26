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

  // Fase 9 (C3): topo "Conversa" - mesma resposta de /api/financas/resumo,
  // sem chamada extra a API.
  const fraseEl = $("#fc-frase-resumo");
  if (fraseEl) fraseEl.textContent = calcularFraseResumoFinancas(resumo);
  renderizarCategoriaFinancas(resumo.por_categoria);
  renderizarEvolucaoFinancas(resumo.por_dia_mes, resumo.por_dia_mes_anterior);
  renderizarFaturaContaFinancas(resumo.fatura_atual, resumo.saldo_conta, resumo.patrimonio);
  // Vis (C2): barra de categoria (scaleX) e linha da evolucao (stroke-
  // dashoffset) se desenham so na 1a vez que o card aparece na tela
  // (IntersectionObserver em movimento.js) - nunca a cada atualizacao dos
  // dados, que e o que loadResumoFinancas faz a cada troca de aba/refresh.
  if (typeof animarGraficoNaEntrada === "function") {
    animarGraficoNaEntrada($("#fc-lista-categoria"));
    animarGraficoNaEntrada($("#fc-grafico-evolucao"));
  }
}

// ---- Fase 9 (C3): topo "Conversa" da aba Financas (docs/fase9-lab2/d01.js,
// direcao 1) - frase-resumo + 3 cartoes com grafico, consumindo o mesmo
// GET /api/financas/resumo que o card antigo (#resumo-financas-box, que fica
// so como fallback escondido - static/css/secoes/gastos/conversa.css). ----

const NOMES_MES_FINANCAS = [
  "janeiro", "fevereiro", "março", "abril", "maio", "junho",
  "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
];

// Formatador proprio (nao usa fmtMoedaFinancas) pra calcularFraseResumoFinancas
// continuar uma funcao pura, testavel com `node --test` sem carregar o resto
// do app (fmtMoedaFinancas/fmtMoeda vivem em outros arquivos globais).
function _fmtMoedaFraseFinancas(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return "R$ 0";
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

// Funcao pura: so le o objeto `resumo` (formato de GET /api/financas/resumo)
// e devolve a frase - nenhum acesso a DOM/rede, por isso testavel isolada.
// "Mesmo dia do mes passado": procura em por_dia_mes_anterior o item com o
// mesmo `dia` do ultimo item de por_dia_mes (hoje); se o mes passado for mais
// curto (ex.: hoje e dia 31 e fevereiro nao tem dia 31), usa o ultimo dia
// disponivel do mes anterior em vez de nao comparar nada.
function calcularFraseResumoFinancas(resumo) {
  const r = resumo && typeof resumo === "object" ? resumo : {};
  const porDiaMes = Array.isArray(r.por_dia_mes) ? r.por_dia_mes : [];
  const porDiaMesAnterior = Array.isArray(r.por_dia_mes_anterior) ? r.por_dia_mes_anterior : [];
  const ultimo = porDiaMes.length ? porDiaMes[porDiaMes.length - 1] : null;
  const valorHoje =
    ultimo && Number.isFinite(Number(ultimo.acumulado)) ? Number(ultimo.acumulado) : Number(r.gasto_mes) || 0;

  let mesTxt = "";
  if (typeof r.mes === "string" && /^\d{4}-\d{2}$/.test(r.mes)) {
    const idx = Number(r.mes.slice(5, 7)) - 1;
    mesTxt = NOMES_MES_FINANCAS[idx] || "";
  }

  let frase = `Você gastou ${_fmtMoedaFraseFinancas(valorHoje)}${mesTxt ? ` em ${mesTxt}` : ""} até agora`;

  const diaAlvo = ultimo ? ultimo.dia : null;
  let comparavel = diaAlvo != null ? porDiaMesAnterior.find((d) => d && d.dia === diaAlvo) || null : null;
  if (!comparavel && porDiaMesAnterior.length) comparavel = porDiaMesAnterior[porDiaMesAnterior.length - 1];
  const valorAnterior =
    comparavel && Number.isFinite(Number(comparavel.acumulado)) ? Number(comparavel.acumulado) : null;

  if (valorAnterior !== null && valorAnterior > 0) {
    const pct = Math.round(((valorHoje - valorAnterior) / valorAnterior) * 100);
    const comparativo = pct >= 0 ? `${pct}% a mais` : `${Math.abs(pct)}% a menos`;
    frase += `, ${comparativo} que no mesmo dia do mês passado.`;
  } else {
    frase += ".";
  }
  return frase;
}

// Card "Gasto por categoria": barras horizontais, top 8 (a API ja manda so
// os 8 maiores), cor unica de acento com opacidade decrescente - nunca
// arco-iris (regra da faixa).
function renderizarCategoriaFinancas(categorias) {
  const lista = $("#fc-lista-categoria");
  const vazio = $("#fc-categoria-vazio");
  if (!lista) return;
  lista.innerHTML = "";
  const cats = Array.isArray(categorias)
    ? categorias.filter((c) => c && typeof c.categoria === "string" && numeroFinancas(c.valor) !== null)
    : [];
  if (cats.length === 0) {
    if (vazio) vazio.hidden = false;
    return;
  }
  if (vazio) vazio.hidden = true;
  const max = Math.max.apply(
    null,
    cats.map((c) => numeroFinancas(c.valor) || 0).concat([1])
  );
  cats.slice(0, 8).forEach((c, i) => {
    const valor = numeroFinancas(c.valor) || 0;
    const li = document.createElement("li");
    li.className = "fc-catrow";
    li.appendChild(criarEl("span", "fc-catnome", c.categoria));
    const barWrap = document.createElement("div");
    barWrap.className = "fc-catbarwrap";
    const bar = document.createElement("div");
    bar.className = "fc-catbar";
    bar.style.width = `${max ? (valor / max) * 100 : 0}%`;
    bar.style.opacity = Math.max(0.35, 1 - i * 0.09).toFixed(2);
    barWrap.appendChild(bar);
    li.appendChild(barWrap);
    li.appendChild(criarEl("span", "fc-catval", fmtMoedaFinancas(valor)));
    lista.appendChild(li);
  });
}

// Card "Evolucao do mes": SVG desenhado a mao (sem lib de grafico) -
// acumulado deste mes (linha + area solida) e a mesma janela de dias do mes
// anterior sobreposta (linha tracejada), pra comparar "no mesmo ponto do
// mes". viewBox responsivo (escala com a largura do card).
function renderizarEvolucaoFinancas(porDiaMes, porDiaMesAnterior) {
  const container = $("#fc-grafico-evolucao");
  if (!container) return;
  const dias = Array.isArray(porDiaMes)
    ? porDiaMes.filter((d) => d && typeof d.dia === "number" && numeroFinancas(d.acumulado) !== null)
    : [];
  if (dias.length === 0) {
    container.innerHTML = '<p class="vazio">Sem gastos registrados esse mes ainda.</p>';
    return;
  }
  const anterior = Array.isArray(porDiaMesAnterior)
    ? porDiaMesAnterior.filter((d) => d && typeof d.dia === "number" && numeroFinancas(d.acumulado) !== null)
    : [];

  const w = 300;
  const h = 110;
  const padB = 18;
  const padT = 12;
  const n = dias.length;
  const nComp = Math.min(n, anterior.length);
  const valores = dias.map((d) => d.acumulado);
  const valoresAnterior = anterior.slice(0, nComp).map((d) => d.acumulado);
  const maxVal = Math.max.apply(null, valores.concat(valoresAnterior, [1]));
  const stepX = n > 1 ? w / (n - 1) : 0;
  const escalaY = (v) => padT + (h - padB - padT) - (v / maxVal) * (h - padB - padT);

  const ptsAtual = dias.map((d, i) => [i * stepX, escalaY(d.acumulado)]);
  const caminhoAtual = ptsAtual.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
  const baseY = (h - padB).toFixed(1);
  const area = `${caminhoAtual} L${ptsAtual[n - 1][0].toFixed(1)},${baseY} L0,${baseY} Z`;
  const ultimo = ptsAtual[n - 1];

  let caminhoAnterior = "";
  if (nComp > 1) {
    const ptsAnterior = anterior.slice(0, nComp).map((d, i) => [i * stepX, escalaY(d.acumulado)]);
    caminhoAnterior = ptsAnterior.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
  }

  const valorFinalTxt = fmtMoedaFinancas(dias[n - 1].acumulado);
  container.innerHTML = `<svg viewBox="0 0 ${w} ${h}" class="fc-chart-acum" role="img" aria-label="Gasto acumulado do mes, dia a dia, comparado ao mesmo periodo do mes anterior">
      <line x1="0" y1="${baseY}" x2="${w}" y2="${baseY}" class="fc-eixo"></line>
      ${caminhoAnterior ? `<path d="${caminhoAnterior}" class="fc-ref"></path>` : ""}
      <path d="${area}" class="fc-area"></path>
      <path d="${caminhoAtual}" class="fc-linha"></path>
      <circle cx="${ultimo[0].toFixed(1)}" cy="${ultimo[1].toFixed(1)}" r="3" class="fc-ponto"></circle>
      <text x="${ultimo[0].toFixed(1)}" y="${Math.max(10, ultimo[1] - 8).toFixed(1)}" class="fc-valor-final" text-anchor="${n > 1 ? "end" : "middle"}">${valorFinalTxt}</text>
      <text x="0" y="${h}" class="fc-eixo-lbl">dia 1</text>
      <text x="${w}" y="${h}" class="fc-eixo-lbl" text-anchor="end">dia ${dias[n - 1].dia}</text>
    </svg>
    ${caminhoAnterior ? '<p class="fc-card-topo" style="margin:8px 0 0">- - - mes anterior (mesmo período)</p>' : ""}`;
}

// Card "Fatura x conta": duas barras comparativas (fatura em --cor-alerta,
// conta em --cor-acento) + patrimonio numa linha pequena.
function renderizarFaturaContaFinancas(fatura, saldoConta, patrimonio) {
  const faturaEl = $("#fc-fatura-valor");
  const contaEl = $("#fc-conta-valor");
  const faturaBarra = $("#fc-fatura-barra");
  const contaBarra = $("#fc-conta-barra");
  const patrimonioEl = $("#fc-patrimonio-valor");
  if (!faturaEl || !contaEl || !faturaBarra || !contaBarra || !patrimonioEl) return;

  const faturaValor = numeroFinancas(fatura) || 0;
  const contaValor = numeroFinancas(saldoConta) || 0;
  const max = Math.max(faturaValor, contaValor, 1);
  faturaEl.textContent = fmtMoedaFinancas(faturaValor);
  contaEl.textContent = fmtMoedaFinancas(contaValor);
  faturaBarra.style.width = `${(faturaValor / max) * 100}%`;
  contaBarra.style.width = `${(contaValor / max) * 100}%`;
  patrimonioEl.textContent = fmtMoedaFinancas(patrimonio);
}

// Chips de pergunta rapida (OPCIONAL no escopo da faixa): so preenchem o
// campo do chat do app - nunca chamam IA sozinhos.
document.querySelectorAll("#fc-chips-perguntas .chip").forEach((btn) => {
  btn.addEventListener("click", () => {
    const campo = $("#captura-input");
    if (!campo) return;
    campo.value = btn.dataset.pergunta || btn.textContent.trim();
    campo.focus();
  });
});

// Exportavel pra `node --test` (funcao pura, sem DOM) sem quebrar o script
// classico no navegador (`module` nao existe la).
if (typeof module !== "undefined" && module.exports) {
  module.exports = { calcularFraseResumoFinancas };
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

// Faixa vel/A2a: /api/gastos/unificados agora pagina (30 por vez) - a aba
// travava de 4 a 9s montando um <li> pra cada gasto manual + transacao
// bancaria de uma vez so (3000+1500 no cenario medido). `proximo` guarda o
// cursor da API pra "Carregar mais" pedir a pagina seguinte.
const LIMITE_PAGINA_GASTOS_UNIFICADOS = 30;
let gastosUnificadosProximo = null;

async function loadExpenses() {
  // Fase 8 (F1): lista unificada (manual + banco), cada item com "origem".
  gastosUnificadosProximo = null;
  const list = $("#lista-gastos");
  const esqueleto = $("#gastos-esqueleto");
  const btnMaisGastos = $("#btn-carregar-mais-gastos");
  list.innerHTML = "";
  if (btnMaisGastos) btnMaisGastos.hidden = true;
  if (esqueleto) esqueleto.hidden = false;

  const resposta = await apiFetch(`/api/gastos/unificados?limite=${LIMITE_PAGINA_GASTOS_UNIFICADOS}`);
  if (esqueleto) esqueleto.hidden = true;
  const expenses = resposta && Array.isArray(resposta.itens) ? resposta.itens : null;
  if (!expenses) return;

  $("#gastos-oculto-visitante").hidden = !modoVisitanteAtivo;
  $("#gastos-vazio").hidden = modoVisitanteAtivo || expenses.length > 0;
  // Uma unica inserção no DOM (DocumentFragment) em vez de N appendChild.
  const fragmentoGastos = document.createDocumentFragment();
  expenses.forEach((e) => fragmentoGastos.appendChild(criarItemGasto(e)));
  list.appendChild(fragmentoGastos);
  gastosUnificadosProximo = resposta.proximo || null;
  if (btnMaisGastos) btnMaisGastos.hidden = !gastosUnificadosProximo;
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

async function carregarMaisGastosUnificados() {
  if (!gastosUnificadosProximo) return;
  const list = $("#lista-gastos");
  const btnMaisGastos = $("#btn-carregar-mais-gastos");
  const params = new URLSearchParams({
    limite: String(LIMITE_PAGINA_GASTOS_UNIFICADOS),
    antes: gastosUnificadosProximo,
  });
  const resposta = await apiFetch(`/api/gastos/unificados?${params.toString()}`);
  const itens = resposta && Array.isArray(resposta.itens) ? resposta.itens : [];
  const fragmentoGastos = document.createDocumentFragment();
  itens.forEach((e) => fragmentoGastos.appendChild(criarItemGasto(e)));
  list.appendChild(fragmentoGastos);
  gastosUnificadosProximo = (resposta && resposta.proximo) || null;
  if (btnMaisGastos) btnMaisGastos.hidden = !gastosUnificadosProximo;
}

const btnCarregarMaisGastos = $("#btn-carregar-mais-gastos");
if (btnCarregarMaisGastos) {
  btnCarregarMaisGastos.addEventListener("click", async () => {
    setBotaoCarregando(btnCarregarMaisGastos, true, "Carregando...");
    await carregarMaisGastosUnificados();
    setBotaoCarregando(btnCarregarMaisGastos, false, "Carregar mais");
  });
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
