// static/js/secoes/gastos/assinaturas.js - Secao gastos > assinaturas (HTML: templates/secoes/gastos/assinaturas.html).
// Fase 7 (faixa v6-financas): consome a API da faixa N1 (/api/financas/*, contrato
// em rotas/n1_financas.py + financas_recorrentes.py) - CRUD puro, sem IA. Script
// classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

// ---- Bottom sheet: usa a API do contrato (static/js/ui/bottom-sheet.js, faixa V0d)
// quando ela ja estiver carregada; enquanto isso nao acontece (static/js/ui/bottom-sheet.js
// segue vazio nesta integracao), cai pro fallback local logo abaixo (hidden + fundo
// escurecido + ESC + foco no primeiro campo/de volta no botao, docs/MASTER.md #9). ----

// `position: fixed` so posiciona relativo a viewport de verdade quando NENHUM
// ancestral tem `transform` - a troca de aba (nucleo/navegacao.js) deixa
// `transform: translateX(0) scale(1)` aplicado em `.tab-content` mesmo depois
// da animacao acabar (fill-mode `both`), o que cria um novo bloco de
// posicionamento pros filhos `fixed`. Pra nao depender de quando isso for
// ajustado no CSS compartilhado, os proprios paineis sobem pra `document.body`
// uma vez, na carga do script - onde `position: fixed` sempre funciona
// relativo a viewport, chame quem chamar `abrirBottomSheet`.
["sheet-nova-assinatura", "sheet-nova-parcela"].forEach((id) => {
  const el = document.getElementById(id);
  if (el && el.parentElement !== document.body) document.body.appendChild(el);
});

let backdropAssinaturas = null;
let sheetOrigemAssinaturas = null;

function abrirSheetAssinaturas(id, origem) {
  if (typeof window.abrirBottomSheet === "function") {
    window.abrirBottomSheet(id);
    return;
  }
  const el = document.getElementById(id);
  if (!el) return;
  sheetOrigemAssinaturas = origem || document.activeElement;
  if (!backdropAssinaturas) {
    backdropAssinaturas = criarEl("div", "bottom-sheet-backdrop-fallback");
    backdropAssinaturas.addEventListener("click", () => fecharSheetAssinaturas(id));
    document.body.appendChild(backdropAssinaturas);
  }
  backdropAssinaturas.hidden = false;
  el.hidden = false;
  const primeiroCampo = el.querySelector("input, select, textarea");
  if (primeiroCampo) primeiroCampo.focus();
}

function fecharSheetAssinaturas(id) {
  if (typeof window.fecharBottomSheet === "function") {
    window.fecharBottomSheet(id);
    return;
  }
  const el = document.getElementById(id);
  if (el) el.hidden = true;
  if (backdropAssinaturas) backdropAssinaturas.hidden = true;
  if (sheetOrigemAssinaturas) {
    sheetOrigemAssinaturas.focus();
    sheetOrigemAssinaturas = null;
  }
}

document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape" || typeof window.abrirBottomSheet === "function") return;
  ["sheet-nova-assinatura", "sheet-nova-parcela"].forEach((id) => {
    const el = document.getElementById(id);
    if (el && !el.hidden) fecharSheetAssinaturas(id);
  });
});

$("#btn-nova-assinatura").addEventListener("click", (e) => abrirSheetAssinaturas("sheet-nova-assinatura", e.currentTarget));
$("#btn-nova-parcela").addEventListener("click", (e) => abrirSheetAssinaturas("sheet-nova-parcela", e.currentTarget));
document.querySelectorAll("#assinaturas-financas-box [data-fechar-sheet]").forEach((btn) => {
  btn.addEventListener("click", () => fecharSheetAssinaturas(btn.dataset.fecharSheet));
});

// ---- Listas (contrato .lista-item: docs/MASTER.md #5) ----

function criarChipCartao(texto) {
  return criarEl("span", "chip chip--compacto", texto);
}

function criarLinhaLista(titulo, metaPartes, valorTexto) {
  const li = criarEl("li", "lista-item");
  const corpo = criarEl("div", "lista-item-corpo");
  corpo.appendChild(criarEl("span", "lista-item-titulo", titulo));
  corpo.appendChild(criarEl("span", "lista-item-meta", metaPartes.filter(Boolean).join(" - ")));
  li.appendChild(corpo);
  if (valorTexto != null) li.appendChild(criarEl("span", "valor-mono lista-item-valor", valorTexto));
  return li;
}

function criarItemProximaCobranca(item) {
  const nome = item.tipo === "assinatura" ? item.nome : item.descricao;
  const metaPartes = [item.label];
  if (item.tipo === "compra_parcelada") metaPartes.push(`parcela ${item.parcela_atual}/${item.n_parcelas}`);
  const formaOuCartao = item.tipo === "assinatura" ? item.cartao_ou_forma : item.cartao;
  if (formaOuCartao) metaPartes.push(formaOuCartao);
  const li = criarLinhaLista(nome, metaPartes, fmtMoeda(item.valor));
  if (item.dias <= 0) li.classList.add("item-atencao");
  return li;
}

function criarItemAssinaturaAtiva(a) {
  const metaPartes = [`${fmtMoeda(a.valor)}/mes`, `dia ${a.dia_cobranca}`];
  if (a.proxima_cobranca) metaPartes.push(`proxima ${fmtDataBr(a.proxima_cobranca)}`);
  const li = criarEl("li", "lista-item");
  const corpo = criarEl("div", "lista-item-corpo");
  corpo.appendChild(criarEl("span", "lista-item-titulo", a.nome));
  corpo.appendChild(criarEl("span", "lista-item-meta", metaPartes.join(" - ")));
  if (a.cartao_ou_forma) corpo.appendChild(criarChipCartao(a.cartao_ou_forma));
  li.appendChild(corpo);

  const acoes = criarEl("div", "lista-item-acoes");
  const btnCancelar = criarEl("button", "btn-com-icone", "Cancelar");
  btnCancelar.addEventListener("click", async () => {
    btnCancelar.disabled = true;
    const r = await apiFetch(`/api/financas/assinaturas/${a.id}/cancelar`, { method: "POST" });
    if (r) {
      li.classList.add("saindo");
      setTimeout(loadAssinaturas, 250);
    } else {
      btnCancelar.disabled = false;
    }
  });
  acoes.appendChild(btnCancelar);
  acoes.appendChild(botaoApagar(`/api/financas/assinaturas/${a.id}`, li));
  li.appendChild(acoes);
  return li;
}

function criarItemParcela(c, info) {
  const metaPartes = [`${fmtMoeda(c.valor_parcela)}/mes`, `parcela ${info.parcela_atual_calculada}/${c.n_parcelas}`, `termina ${info.mes_termino_nome}`];
  const li = criarEl("li", "lista-item");
  const corpo = criarEl("div", "lista-item-corpo");
  corpo.appendChild(criarEl("span", "lista-item-titulo", c.descricao));
  corpo.appendChild(criarEl("span", "lista-item-meta", metaPartes.join(" - ")));
  if (c.cartao) corpo.appendChild(criarChipCartao(c.cartao));

  const progresso = criarEl("div", "meta-progresso parcela-progresso");
  const pct = Math.min(100, (info.parcelas_pagas / c.n_parcelas) * 100);
  const barra = criarEl("div", "meta-progresso-barra");
  barra.style.width = `${pct}%`;
  progresso.appendChild(barra);
  corpo.appendChild(progresso);
  li.appendChild(corpo);

  const acoes = criarEl("div", "lista-item-acoes");
  acoes.appendChild(botaoApagar(`/api/financas/parcelas/${c.id}`, li));
  li.appendChild(acoes);
  return li;
}

function desenharLimiteCartao(impactos) {
  const card = $("#limite-cartao-card");
  if (!impactos || impactos.length === 0) {
    card.hidden = true;
    return;
  }
  // So o primeiro cartao citado (a tela e "mini grafico", nao um dashboard
  // completo) - com limite configurado mostra fracao (%), sem limite mostra
  // o total comprometido em R$ mesmo (nunca inventa um limite).
  const alvo = impactos[0];
  card.hidden = false;
  $("#limite-cartao-titulo").textContent =
    impactos.length > 1
      ? `Limite comprometido - ${alvo.cartao} (+${impactos.length - 1})`
      : `Limite comprometido - ${alvo.cartao}`;

  const temLimite = alvo.limite != null;
  const dados = alvo.meses.map((m) => ({
    data: `${m.mes}-01`,
    total: temLimite ? Math.round((m.fracao || 0) * 1000) / 10 : m.total,
  }));
  desenharGraficoBarras($("#grafico-limite-cartao"), dados, {
    cor: "var(--cor-financeiro)",
    formatarValor: temLimite ? (v) => `${v}%` : fmtMoeda,
    rotulo: `Projecao de comprometimento do cartao ${alvo.cartao} nos proximos meses`,
    altura: 84,
  });
  $("#limite-cartao-legenda").textContent = temLimite
    ? `Limite de ${fmtMoeda(alvo.limite)} - so conta o que esta faixa conhece (assinatura/parcela), pode ter mais gasto no cartao alem disso.`
    : "Sem limite configurado pra esse cartao (aba Bancos) - mostrando o total comprometido em R$.";
}

async function loadComprometido() {
  const data = await apiFetch("/api/financas/comprometido");
  if (!data) return;
  const total = data.total_mensal || {};
  const temAlgo = (total.total || 0) > 0;
  $("#comprometido-box").hidden = !temAlgo;
  $("#comprometido-vazio").hidden = temAlgo;
  if (temAlgo) {
    $("#comprometido-total").textContent = fmtMoeda(total.total);
    $("#chip-assinaturas").textContent = `${(total.detalhe_assinaturas || []).length} assinatura(s) - ${fmtMoeda(total.assinaturas_total || 0)}`;
    $("#chip-parcelas").textContent = `${(total.detalhe_parcelas || []).length} parcela(s) - ${fmtMoeda(total.parcelas_total || 0)}`;
  }
  desenharLimiteCartao(data.impacto_limite_cartao);

  const proximas = data.proximas_cobrancas || [];
  const listaProximas = $("#lista-proximas-cobrancas");
  listaProximas.innerHTML = "";
  $("#proximas-cobrancas-vazio").hidden = proximas.length > 0;
  proximas.forEach((item) => listaProximas.appendChild(criarItemProximaCobranca(item)));
}

async function loadAssinaturasAtivas() {
  const data = await apiFetch("/api/financas/assinaturas?ativas=1");
  if (!data) return;
  const assinaturas = data.assinaturas || [];
  const lista = $("#lista-assinaturas-ativas");
  lista.innerHTML = "";
  $("#assinaturas-ativas-vazio").hidden = assinaturas.length > 0;
  assinaturas.forEach((a) => lista.appendChild(criarItemAssinaturaAtiva(a)));
}

async function loadParcelasEmAndamento() {
  const data = await apiFetch("/api/financas/parcelas?em_andamento=1");
  if (!data) return;
  const parcelas = data.parcelas || [];
  const lista = $("#lista-parcelas");
  lista.innerHTML = "";
  $("#parcelas-vazio").hidden = parcelas.length > 0;
  parcelas.forEach((c) => lista.appendChild(criarItemParcela(c, c)));
}

async function loadAssinaturas() {
  loadComprometido();
  loadAssinaturasAtivas();
  loadParcelasEmAndamento();
}

// ---- Formularios (bottom sheet) ----

$("#form-nova-assinatura").addEventListener("submit", async (e) => {
  e.preventDefault();
  const nome = $("#assinatura-nome").value.trim();
  const valor = Number($("#assinatura-valor").value);
  const dia = Number($("#assinatura-dia").value);
  if (!nome || !(valor > 0) || !(dia >= 1 && dia <= 31)) {
    mostrarErro("Confere o nome, o valor (maior que zero) e o dia (1 a 31).");
    return;
  }
  const btn = $("#assinatura-salvar-btn");
  setBotaoCarregando(btn, true, "salvando...");
  const r = await apiFetch("/api/financas/assinaturas", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      nome,
      valor,
      dia_cobranca: dia,
      cartao_ou_forma: $("#assinatura-cartao").value.trim() || null,
      categoria: $("#assinatura-categoria").value.trim() || null,
    }),
  });
  setBotaoCarregando(btn, false, "Salvar assinatura");
  if (!r) return;
  $("#form-nova-assinatura").reset();
  fecharSheetAssinaturas("sheet-nova-assinatura");
  loadAssinaturas();
});

$("#form-nova-parcela").addEventListener("submit", async (e) => {
  e.preventDefault();
  const descricao = $("#parcela-descricao").value.trim();
  const nParcelas = Number($("#parcela-n").value);
  const valorTotalTxt = $("#parcela-valor-total").value.trim();
  const valorParcelaTxt = $("#parcela-valor-parcela").value.trim();
  if (!descricao || !(nParcelas > 0) || (!valorTotalTxt && !valorParcelaTxt)) {
    mostrarErro("Confere a descricao, o numero de parcelas e informe o valor total ou o valor da parcela.");
    return;
  }
  const btn = $("#parcela-salvar-btn");
  setBotaoCarregando(btn, true, "salvando...");
  const r = await apiFetch("/api/financas/parcelas", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      descricao,
      n_parcelas: nParcelas,
      valor_total: valorTotalTxt ? Number(valorTotalTxt) : null,
      valor_parcela: valorParcelaTxt ? Number(valorParcelaTxt) : null,
      cartao: $("#parcela-cartao").value.trim() || null,
      primeira_parcela: $("#parcela-primeira").value || null,
    }),
  });
  setBotaoCarregando(btn, false, "Salvar parcela");
  if (!r) return;
  $("#form-nova-parcela").reset();
  fecharSheetAssinaturas("sheet-nova-parcela");
  loadAssinaturas();
});

// ---- Carga: a aba Gastos e recarregada por showTab() (nucleo/navegacao.js,
// compartilhado - esta faixa nao edita esse arquivo), que ainda nao conhece
// esta secao nova. Listener proprio a mais no mesmo botao de aba (nao
// substitui nada, so soma) ate o integrador somar a chamada direto la. ----

document.querySelectorAll(".tab-btn").forEach((btn) => {
  if (btn.dataset.tab === "gastos") btn.addEventListener("click", loadAssinaturas);
});
