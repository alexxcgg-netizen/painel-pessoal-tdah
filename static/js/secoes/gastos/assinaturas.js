// static/js/secoes/gastos/assinaturas.js - Secao gastos > assinaturas (HTML: templates/secoes/gastos/assinaturas.html).
// Fase 7 (faixa v6-financas): consome a API da faixa N1 (/api/financas/*, contrato
// em rotas/n1_financas.py + financas_recorrentes.py) - CRUD puro, sem IA. Script
// classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

// ---- Bottom sheet: usa a API do contrato (static/js/ui/bottom-sheet.js, faixa V0d)
// quando ela ja estiver carregada; enquanto isso nao acontece (ou nalgum navegador
// que falhe ao carregar aquele arquivo), cai pro fallback direto no atributo
// `hidden`, que sozinho ja cobre a funcionalidade (so sem fundo escurecido/ESC/
// foco preso - isso vem de graca quando a V0d entrar na integracao). ----

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

function abrirSheetAssinaturas(id) {
  if (typeof window.abrirBottomSheet === "function") {
    window.abrirBottomSheet(id);
    return;
  }
  // Fallback sem a V0d ainda na integracao: fundo escurecido + ESC feitos
  // aqui mesmo (funcionalidade minima - foco preso fica pra quando a V0d
  // entrar, que substitui este caminho inteiro).
  const el = document.getElementById(id);
  if (!el) return;
  if (!backdropAssinaturas) {
    backdropAssinaturas = criarEl("div", "bottom-sheet-backdrop-fallback");
    backdropAssinaturas.addEventListener("click", () => fecharSheetAssinaturas(id));
    document.body.appendChild(backdropAssinaturas);
  }
  backdropAssinaturas.hidden = false;
  el.hidden = false;
}

function fecharSheetAssinaturas(id) {
  if (typeof window.fecharBottomSheet === "function") {
    window.fecharBottomSheet(id);
    return;
  }
  const el = document.getElementById(id);
  if (el) el.hidden = true;
  if (backdropAssinaturas) backdropAssinaturas.hidden = true;
}

document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape" || typeof window.abrirBottomSheet === "function") return;
  ["sheet-nova-assinatura", "sheet-nova-parcela"].forEach((id) => {
    const el = document.getElementById(id);
    if (el && !el.hidden) fecharSheetAssinaturas(id);
  });
});

$("#btn-nova-assinatura").addEventListener("click", () => abrirSheetAssinaturas("sheet-nova-assinatura"));
$("#btn-nova-parcela").addEventListener("click", () => abrirSheetAssinaturas("sheet-nova-parcela"));
document.querySelectorAll("#assinaturas-financas-box [data-fechar-sheet]").forEach((btn) => {
  btn.addEventListener("click", () => fecharSheetAssinaturas(btn.dataset.fecharSheet));
});

// ---- Listas ----

function criarChipCartao(texto) {
  const chip = criarEl("span", "chip chip-neutro", texto);
  return chip;
}

function criarItemProximaCobranca(item) {
  const nome = item.tipo === "assinatura" ? item.nome : item.descricao;
  const li = criarEl("li", "item lista-item" + (item.dias <= 0 ? " item-atencao" : ""));
  const linha = criarEl("div", "item-linha");
  const wrap = criarEl("div");
  wrap.appendChild(criarEl("span", "item-titulo", nome));
  const detalhePartes = [item.label];
  if (item.tipo === "compra_parcelada") detalhePartes.push(`parcela ${item.parcela_atual}/${item.n_parcelas}`);
  const formaOuCartao = item.tipo === "assinatura" ? item.cartao_ou_forma : item.cartao;
  if (formaOuCartao) detalhePartes.push(formaOuCartao);
  wrap.appendChild(criarEl("span", "item-quando", detalhePartes.join(" - ")));
  linha.appendChild(wrap);
  linha.appendChild(criarEl("span", "valor-mono item-valor", fmtMoeda(item.valor)));
  li.appendChild(linha);
  return li;
}

function criarItemAssinaturaAtiva(a) {
  const li = criarEl("li", "item lista-item");
  const linha = criarEl("div", "item-linha");
  const wrap = criarEl("div");
  wrap.appendChild(criarEl("span", "item-titulo", a.nome));
  const detalhe = [`${fmtMoeda(a.valor)}/mes`, `dia ${a.dia_cobranca}`];
  if (a.proxima_cobranca) detalhe.push(`proxima ${fmtDataBr(a.proxima_cobranca)}`);
  wrap.appendChild(criarEl("span", "item-quando", detalhe.join(" - ")));
  linha.appendChild(wrap);
  if (a.cartao_ou_forma) linha.appendChild(criarChipCartao(a.cartao_ou_forma));
  li.appendChild(linha);

  const acoes = criarEl("div", "item-acoes");
  const btnCancelar = criarEl("button", "btn-com-icone");
  btnCancelar.textContent = "Cancelar";
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
  const linhaAcoes = criarEl("div", "item-linha");
  linhaAcoes.appendChild(acoes);
  li.appendChild(linhaAcoes);
  return li;
}

function criarItemParcela(c, info) {
  const li = criarEl("li", "item lista-item");
  const linha = criarEl("div", "item-linha");
  const wrap = criarEl("div");
  wrap.appendChild(criarEl("span", "item-titulo", c.descricao));
  const detalhe = [
    `${fmtMoeda(c.valor_parcela)}/mes`,
    `parcela ${info.parcela_atual_calculada}/${c.n_parcelas}`,
    `termina ${info.mes_termino_nome}`,
  ];
  wrap.appendChild(criarEl("span", "item-quando", detalhe.join(" - ")));
  linha.appendChild(wrap);
  if (c.cartao) linha.appendChild(criarChipCartao(c.cartao));
  li.appendChild(linha);

  const progresso = criarEl("div", "meta-progresso parcela-progresso");
  const pct = Math.min(100, (info.parcelas_pagas / c.n_parcelas) * 100);
  const barra = criarEl("div", "meta-progresso-barra");
  barra.style.width = `${pct}%`;
  progresso.appendChild(barra);
  li.appendChild(progresso);

  const linhaAcoes = criarEl("div", "item-linha");
  const acoes = criarEl("div", "item-acoes");
  acoes.appendChild(botaoApagar(`/api/financas/parcelas/${c.id}`, li));
  linhaAcoes.appendChild(acoes);
  li.appendChild(linhaAcoes);
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
  const assinaturas = await apiFetch("/api/financas/assinaturas?ativas=1");
  if (!assinaturas) return;
  const lista = $("#lista-assinaturas-ativas");
  lista.innerHTML = "";
  $("#assinaturas-ativas-vazio").hidden = assinaturas.length > 0;
  assinaturas.forEach((a) => lista.appendChild(criarItemAssinaturaAtiva(a)));
}

async function loadParcelasEmAndamento() {
  const parcelas = await apiFetch("/api/financas/parcelas?em_andamento=1");
  if (!parcelas) return;
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
