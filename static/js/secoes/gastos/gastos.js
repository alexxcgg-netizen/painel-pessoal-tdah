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
      $("#nota-fiscal-status").textContent = "Sem conexão - a foto foi salva e vai ler assim que voltar.";
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

// Faixa limpa/d-financas: a lista antiga (#lista-gastos, criarItemGasto)
// saiu da tela - o extrato novo (criarItemExtratoFinancas, mais abaixo) e a
// UNICA lista da aba Financas agora. As duas acoes que so existiam ali
// (corrigir categoria / "e tarefa") continuam vivas e reaproveitadas: viram
// criarBotaoReclassificarGasto (abaixo) e a mesma criarSeletorCategoriaGasto
// de sempre, so que chamadas de dentro do item do extrato.
function criarBotaoReclassificarGasto(expenseId, li) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "btn btn-secundario btn-com-icone btn-corrigir-gasto";
  btn.title = "isso não é um gasto?";
  btn.innerHTML = `${ICONE_CORRIGIR}é tarefa`;
  btn.addEventListener("click", async (ev) => {
    if (ev) ev.stopPropagation();
    setBotaoCarregando(btn, true, "corrigindo...");
    const data = await apiFetch(`/api/expenses/${expenseId}/reclassificar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    if (data) {
      if (li) li.classList.add("saindo");
      setTimeout(() => {
        loadExpenses();
        if (typeof loadTasks === "function") loadTasks();
      }, 220);
    } else {
      setBotaoCarregando(btn, false, "é tarefa");
    }
  });
  return btn;
}

// GET /api/financas/extrato ja devolve a categoria traduzida (financas_
// descricao.rotulo_categoria_manual, ex: "mercado" -> "Mercado") em vez da
// chave crua que criarSeletorCategoriaGasto espera pra pre-selecionar a
// opcao atual. So preselecao/exibicao: se o rotulo nao bater com nenhuma
// chave conhecida, o <select> abre sem nada marcado e a correcao funciona
// do mesmo jeito (o usuario escolhe a categoria certa).
const ROTULO_PARA_CATEGORIA_GASTO = {
  Mercado: "mercado",
  Transporte: "transporte",
  Lazer: "lazer",
  Contas: "contas",
  Saúde: "saude",
  Outros: "outros",
};

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

  // Vis (C2): "numeros contando" so na 1a abertura da aba Financas nesta
  // sessao de pagina (mesmo padrao de container.dataset usado em
  // marcarEntradaEscalonada, movimento.js) - loadResumoFinancas roda de novo
  // a cada troca de aba/refresh, e recontar toda vez ficaria irritante.
  const conversaEl = $("#financas-conversa");
  const primeiraAbertura = !!(conversaEl && conversaEl.dataset.c2Contou !== "1");
  if (conversaEl) conversaEl.dataset.c2Contou = "1";

  // Fase 9 (C3): topo "Conversa" - mesma resposta de /api/financas/resumo,
  // sem chamada extra a API.
  const fraseEl = $("#fc-frase-resumo");
  if (fraseEl) montarFraseResumoFinancas(fraseEl, resumo, primeiraAbertura);
  renderizarCategoriaFinancas(resumo.por_categoria);
  renderizarEvolucaoFinancas(resumo.por_dia_mes, resumo.por_dia_mes_anterior);
  renderizarFaturaContaFinancas(resumo.fatura_atual, resumo.saldo_conta, resumo.patrimonio, primeiraAbertura);
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
// Vis (C2): partes separadas (antes do valor / valor / depois do valor) pra
// poder animar so o numero com animarNumero (montarFraseResumoFinancas) sem
// duplicar a logica de calculo - calcularFraseResumoFinancas (texto puro,
// usado por quem so quer a string) so junta essas 3 partes.
function partesFraseResumoFinancas(resumo) {
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

  const antes = "Você gastou ";
  let depois = `${mesTxt ? ` em ${mesTxt}` : ""} até agora`;

  const diaAlvo = ultimo ? ultimo.dia : null;
  let comparavel = diaAlvo != null ? porDiaMesAnterior.find((d) => d && d.dia === diaAlvo) || null : null;
  if (!comparavel && porDiaMesAnterior.length) comparavel = porDiaMesAnterior[porDiaMesAnterior.length - 1];
  const valorAnterior =
    comparavel && Number.isFinite(Number(comparavel.acumulado)) ? Number(comparavel.acumulado) : null;

  if (valorAnterior !== null && valorAnterior > 0) {
    const pct = Math.round(((valorHoje - valorAnterior) / valorAnterior) * 100);
    const comparativo = pct >= 0 ? `${pct}% a mais` : `${Math.abs(pct)}% a menos`;
    depois += `, ${comparativo} que no mesmo dia do mês passado.`;
  } else {
    depois += ".";
  }
  return { antes, valorHoje, depois };
}

function calcularFraseResumoFinancas(resumo) {
  const { antes, valorHoje, depois } = partesFraseResumoFinancas(resumo);
  return `${antes}${_fmtMoedaFraseFinancas(valorHoje)}${depois}`;
}

// Vis (C2): preenche a frase no DOM - na 1a abertura da aba, o valor conta
// (animarNumero, que ja respeita "reduzir movimento" e mostra o valor final
// direto); nas trocas de aba seguintes so texto, sem recontar.
function montarFraseResumoFinancas(fraseEl, resumo, primeiraAbertura) {
  const { antes, valorHoje, depois } = partesFraseResumoFinancas(resumo);
  if (!primeiraAbertura || typeof animarNumero !== "function") {
    fraseEl.textContent = `${antes}${_fmtMoedaFraseFinancas(valorHoje)}${depois}`;
    return;
  }
  fraseEl.textContent = "";
  fraseEl.appendChild(document.createTextNode(antes));
  const valorEl = document.createElement("span");
  fraseEl.appendChild(valorEl);
  fraseEl.appendChild(document.createTextNode(depois));
  animarNumero(valorEl, valorHoje, _fmtMoedaFraseFinancas);
}

// Card "Gasto por categoria": barras horizontais, top 8 (a API ja manda so
// os 8 maiores). Faixa vis/C1: cada barra usa a cor fixa da propria
// categoria (corDaCategoria, nucleo/cores.js) - antes era cor unica de
// acento com opacidade decrescente.
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
    bar.style.background = corDaCategoria(c.categoria);
    bar.style.width = `${max ? (valor / max) * 100 : 0}%`;
    bar.style.opacity = Math.max(0.55, 1 - i * 0.05).toFixed(2);
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
    container.innerHTML = '<p class="vazio">Sem gastos registrados este mês ainda.</p>';
    return;
  }
  // R3 (acabamento): com 1 dia só, a "linha" seria um ponto solto no meio de um card vazio -
  // mostra o total do dia com a explicação de quando a linha aparece.
  if (dias.length === 1) {
    container.innerHTML =
      `<div class="fc-evolucao-um-dia"><b>${fmtMoedaFinancas(dias[0].acumulado)}</b>` +
      `<span>gasto até o dia ${dias[0].dia}. A linha do mês aparece a partir do 2º dia com gasto.</span></div>`;
    return;
  }
  const anterior = Array.isArray(porDiaMesAnterior)
    ? porDiaMesAnterior.filter((d) => d && typeof d.dia === "number" && numeroFinancas(d.acumulado) !== null)
    : [];

  const w = 300;
  const h = 110;
  const padB = 4;
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
  container.innerHTML = `<svg viewBox="0 0 ${w} ${h}" class="fc-chart-acum" role="img" aria-label="Gasto acumulado do mês, dia a dia, comparado ao mesmo período do mês anterior">
      <line x1="0" y1="${baseY}" x2="${w}" y2="${baseY}" class="fc-eixo"></line>
      ${caminhoAnterior ? `<path d="${caminhoAnterior}" class="fc-ref"></path>` : ""}
      <path d="${area}" class="fc-area"></path>
      <path d="${caminhoAtual}" class="fc-linha"></path>
      <circle cx="${ultimo[0].toFixed(1)}" cy="${ultimo[1].toFixed(1)}" r="3" class="fc-ponto"></circle>
      <text x="${ultimo[0].toFixed(1)}" y="${Math.max(10, ultimo[1] - 8).toFixed(1)}" class="fc-valor-final" text-anchor="${n > 1 ? "end" : "middle"}">${valorFinalTxt}</text>
    </svg>
    <div class="fc-eixo-linha"><span>dia 1</span><span>dia ${dias[n - 1].dia}</span></div>
    ${caminhoAnterior ? '<p class="fc-legenda-ref"><span aria-hidden="true"></span>mês anterior (mesmo período)</p>' : ""}`;
}

// Card "Fatura x conta": duas barras comparativas (fatura em --cor-alerta,
// conta em --cor-acento) + patrimonio numa linha pequena.
function renderizarFaturaContaFinancas(fatura, saldoConta, patrimonio, primeiraAbertura) {
  const faturaEl = $("#fc-fatura-valor");
  const contaEl = $("#fc-conta-valor");
  const faturaBarra = $("#fc-fatura-barra");
  const contaBarra = $("#fc-conta-barra");
  const patrimonioEl = $("#fc-patrimonio-valor");
  if (!faturaEl || !contaEl || !faturaBarra || !contaBarra || !patrimonioEl) return;

  const faturaValor = numeroFinancas(fatura) || 0;
  const contaValor = numeroFinancas(saldoConta) || 0;
  const max = Math.max(faturaValor, contaValor, 1);
  // Vis (C2): so conta (animarNumero) na 1a abertura da aba - trocas de aba
  // seguintes so texto direto, sem recontar (mesma regra da frase-resumo).
  if (primeiraAbertura && typeof animarNumero === "function") {
    animarNumero(faturaEl, faturaValor, fmtMoedaFinancas);
    animarNumero(contaEl, contaValor, fmtMoedaFinancas);
  } else {
    faturaEl.textContent = fmtMoedaFinancas(faturaValor);
    contaEl.textContent = fmtMoedaFinancas(contaValor);
  }
  faturaBarra.style.width = `${(faturaValor / max) * 100}%`;
  contaBarra.style.width = `${(contaValor / max) * 100}%`;
  patrimonioEl.textContent = fmtMoedaFinancas(patrimonio);
}

// Vis (C2): "Ultimos dias" (<details>) expande sem pulo - ver
// ligarDetalheAnimado em nucleo/movimento.js.
if (typeof ligarDetalheAnimado === "function") {
  ligarDetalheAnimado($("#fc-card-ultimos-dias"));
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
  titulo.textContent = item.descricao || "(sem descrição)";
  const origemChip = document.createElement("span");
  origemChip.className = "chip chip--compacto";
  origemChip.textContent = item.origem === "Nubank" ? "Nubank" : "manual";
  titulo.appendChild(origemChip);
  if (item.tipo_conta) {
    const tipoChip = document.createElement("span");
    tipoChip.className = "chip chip--compacto";
    tipoChip.textContent = item.tipo_conta === "cartao" ? "cartão" : "conta";
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

  // Faixa limpa/d-financas: lancamento manual (tem "exp-<id>") ganha as
  // mesmas acoes que a lista antiga tinha - corrigir categoria e "e tarefa"
  // (POST /api/expenses/<id>/categoria e /reclassificar, as MESMAS rotas de
  // sempre). Ficam escondidas ate o toque no item porque essa linha aqui e
  // fina de proposito (cartao "Ultimos dias", conversa.css) - nao cabem
  // sempre visiveis como cabiam no card grande da lista antiga.
  const expenseId = item.origem === "manual" && typeof item.id === "string" && item.id.startsWith("exp-") ? item.id.slice(4) : null;
  if (expenseId) {
    li.classList.add("fc-extrato-editavel");
    li.dataset.entidade = "gasto";
    li.dataset.id = expenseId;
    linha.setAttribute("role", "button");
    linha.setAttribute("tabindex", "0");
    linha.setAttribute("aria-expanded", "false");
    linha.title = "toque pra corrigir a categoria ou marcar como tarefa";

    const acoes = document.createElement("div");
    acoes.className = "item-acoes fc-extrato-acoes";
    acoes.hidden = true;

    const categoriaRaw = ROTULO_PARA_CATEGORIA_GASTO[item.categoria] || "outros";
    const catBtn = document.createElement("button");
    catBtn.type = "button";
    catBtn.className = "gasto-categoria chip chip--compacto";
    catBtn.dataset.cat = categoriaRaw;
    catBtn.style.setProperty("--cat-cor", corDaCategoria(categoriaRaw));
    catBtn.textContent = item.categoria || categoriaRaw;
    catBtn.title = "toque pra corrigir a categoria";
    catBtn.setAttribute("aria-label", `Categoria ${item.categoria}: toque pra corrigir`);
    catBtn.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const select = criarSeletorCategoriaGasto({ id: expenseId, category: categoriaRaw }, catBtn, li);
      catBtn.replaceWith(select);
      select.focus();
    });
    acoes.appendChild(catBtn);
    acoes.appendChild(criarBotaoReclassificarGasto(expenseId, li));
    li.appendChild(acoes);

    const alternarAcoes = () => {
      const abrindo = acoes.hidden;
      acoes.hidden = !abrindo;
      linha.setAttribute("aria-expanded", String(abrindo));
    };
    linha.addEventListener("click", alternarAcoes);
    linha.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        alternarAcoes();
      }
    });
  }

  return li;
}

async function loadExtratoFinancas(antes, acumular) {
  const btnMais = $("#btn-carregar-mais-extrato");
  const params = new URLSearchParams({ dias: "15" });
  if (antes) params.set("antes", antes);
  const resposta = await apiFetch(`/api/financas/extrato?${params.toString()}`);
  const list = $("#lista-extrato-financas");
  const vazioEl = $("#extrato-financas-vazio");
  if (!resposta || !Array.isArray(resposta.itens)) {
    if (!acumular) {
      list.innerHTML = "";
      if (vazioEl) {
        vazioEl.textContent = "Não consegui carregar o extrato agora.";
        vazioEl.hidden = false;
      }
    }
    if (btnMais) btnMais.hidden = true;
    return;
  }
  if (!acumular) list.innerHTML = "";
  if (vazioEl) {
    // Fase 9 (f9-api) ja escondia a lista inteira em modo visitante
    // (extrato() devolve {itens: [], oculto: true}) - a lista antiga tinha
    // uma mensagem propria pra isso (#gastos-oculto-visitante); como agora
    // so sobra esta lista, o mesmo aviso mora aqui.
    vazioEl.textContent = resposta.oculto ? "Oculto no modo visitante." : "Nenhum lançamento nesse período.";
    vazioEl.hidden = list.children.length > 0 || resposta.itens.length > 0;
  }
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

// Faixa limpa/d-financas: a lista antiga (#lista-gastos, paginada por
// /api/gastos/unificados) saiu da aba - so sobrou o extrato novo
// (loadExtratoFinancas, GET /api/financas/extrato). A rota /api/gastos/
// unificados continua existindo pra quem mais a usa (ver rotas/f8_banco.py
// e tests/test_vel_a2a_gastos.py, tests/test_fase8_f1_banco.py - nao sao
// meus arquivos, nao mudei nada nela).
//
// loadExpenses(), porem, e chamada de fora daqui (navegacao.js, init.js,
// captura.js, brain-dump.js, chat.js, tarefas.js - nenhum e meu) sempre que
// um gasto e criado/editado/sincronizado. Continua existindo com o mesmo
// nome pra nao quebrar quem chama - so que agora recarrega o extrato + os
// widgets que dependiam dela (grafico de 14 dias, proximas cobrancas,
// resumo semanal, custo com IA) em vez de montar a lista antiga.
async function loadExpenses() {
  if (typeof loadExtratoFinancas === "function") loadExtratoFinancas();
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
      rotulo: "Gasto diário nos últimos 14 dias",
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
  $("#custo-ia-mes").textContent = `${usd(data.mes_atual_usd)} esse mês`;
  $("#custo-ia-30dias").textContent = `Últimos 30 dias: ${usd(data.ultimos_30_dias_usd)}.`;

  const inputTeto = $("#custo-ia-teto-input");
  if (document.activeElement !== inputTeto) {
    inputTeto.value = data.teto_mensal_usd ?? "";
  }

  const aviso = $("#custo-ia-teto-aviso");
  if (data.teto_estourado) {
    aviso.textContent =
      "Teto estourado esse mês - o classificador de intent (navegacao por voz) vai preferir " +
      "resolver por padrão já aprendido em vez de chamar a IA, até o mês virar.";
    aviso.hidden = false;
  } else if (data.teto_perto) {
    const fracao = numeroFinancas(data.fracao_teto);
    aviso.textContent = fracao === null ? "Perto do teto mensal." : `Perto do teto mensal (já usou ${Math.round(fracao * 100)}%).`;
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
