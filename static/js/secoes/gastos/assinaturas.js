// static/js/secoes/gastos/assinaturas.js - Secao gastos > assinaturas (HTML: templates/secoes/gastos/assinaturas.html).
// Fase 7 (faixa v6-financas): consome a API da faixa N1 (/api/financas/*, contrato
// em docs/contrato-assinaturas.md) - CRUD puro, sem IA. Script classico (escopo
// global compartilhado) - a ordem de carga esta em templates/scripts.html.
// Fase 7 (faixa C3c): sheet so pelo componente compartilhado (V0d + C2),
// validacao propria com erro dentro do sheet, guarda contra NaN/undefined vindo
// da API e acoes da lista com as classes do contrato (.btn.btn-secundario).

// ---- Helpers compartilhados pelas secoes financeiras desta faixa ----
// (contas-pessoais.js, construtora.js, contas-a-pagar.js e bancos.js usam
// dentro de funcoes chamadas depois da carga de todos os scripts.)

// Numero de verdade ou null (nunca NaN/Infinity/string solta).
function numeroFinancas(v) {
  if (v === null || v === undefined || v === "" || typeof v === "boolean") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

// fmtMoeda(undefined) vira "R$ NaN" - aqui vira travessao.
function fmtMoedaFinancas(v) {
  const n = numeroFinancas(v);
  return n === null ? "—" : fmtMoeda(n);
}

// fmtDataBr quebra (TypeError) com undefined/formato estranho.
function fmtDataFinancas(iso) {
  if (typeof iso !== "string" || !/^\d{4}-\d{2}-\d{2}/.test(iso)) return "—";
  return fmtDataBr(iso.slice(0, 10));
}

function textoFinancas(v, padrao) {
  return typeof v === "string" && v.trim() ? v : padrao;
}

// Botao de acao de linha (.lista-item-acoes): so icone, 44px, rotulo acessivel.
function botaoIconeFinancas(iconeHtml, rotulo, extraClasse) {
  const btn = criarEl("button", "btn btn-secundario btn-icone-financas" + (extraClasse ? " " + extraClasse : ""));
  btn.type = "button";
  btn.innerHTML = iconeHtml;
  btn.setAttribute("aria-label", rotulo);
  btn.title = rotulo;
  return btn;
}

// Reaproveita botaoApagar (nucleo/vida-base.js - mesma logica de DELETE) e so
// troca o visual: icone de 44px em vez do botao nativo com texto.
function botaoApagarFinancas(url, li, nome) {
  const btn = botaoApagar(url, li);
  btn.type = "button";
  btn.className = "btn btn-secundario btn-icone-financas btn-apagar-financas";
  btn.innerHTML = ICONE_TRASH;
  btn.setAttribute("aria-label", `Apagar ${nome}`);
  btn.title = "Apagar";
  return btn;
}

// Sheets: componente compartilhado (static/js/ui/bottom-sheet.js). Abre por
// `data-abre-sheet` no botao (o componente foca o 1o campo, sobe o sheet pro
// <body> e devolve ao fechar); fecha no sucesso via "bottomsheet:sucesso" no
// <form data-fecha-ao-enviar>. Aqui so o que e desta faixa: o erro de
// validacao some quando o sheet fecha (nao reaparece velho ao reabrir).
function mostrarErroSheet(idErro, msg) {
  const p = document.getElementById(idErro);
  if (!p) return;
  p.querySelector("span").textContent = msg;
  p.hidden = false;
}

function sucessoSheetFinancas(form) {
  form.reset();
  form.dispatchEvent(new CustomEvent("bottomsheet:sucesso", { bubbles: true }));
}

document.addEventListener("bottomsheet:fechado", (e) => {
  const sheet = e.target;
  if (!sheet || !sheet.classList || !sheet.classList.contains("bottom-sheet-financas")) return;
  sheet.querySelectorAll(".sheet-erro").forEach((p) => (p.hidden = true));
});

// ---- Listas (contrato .lista-item: docs/MASTER.md #5) ----

function criarChipCartao(texto) {
  return criarEl("span", "chip chip--compacto chip-cartao-financas", texto);
}

function criarLinhaLista(titulo, metaPartes, valorTexto) {
  const li = criarEl("li", "lista-item");
  const corpo = criarEl("div", "lista-item-corpo");
  corpo.appendChild(criarEl("span", "lista-item-titulo", titulo));
  corpo.appendChild(criarEl("span", "lista-item-meta valor-mono", metaPartes.filter(Boolean).join(" · ")));
  li.appendChild(corpo);
  if (valorTexto != null) li.appendChild(criarEl("span", "valor-mono lista-item-valor", valorTexto));
  return li;
}

function criarItemAssinaturaAtiva(a) {
  const nome = textoFinancas(a.nome, "Sem nome");
  const metaPartes = [`${fmtMoedaFinancas(a.valor)}/mes`];
  if (numeroFinancas(a.dia_cobranca) !== null) metaPartes.push(`dia ${a.dia_cobranca}`);
  if (a.proxima_cobranca) metaPartes.push(`proxima ${fmtDataFinancas(a.proxima_cobranca)}`);
  const li = criarEl("li", "lista-item");
  const corpo = criarEl("div", "lista-item-corpo");
  corpo.appendChild(criarEl("span", "lista-item-titulo", nome));
  corpo.appendChild(criarEl("span", "lista-item-meta valor-mono", metaPartes.join(" · ")));
  if (textoFinancas(a.cartao_ou_forma, "")) corpo.appendChild(criarChipCartao(a.cartao_ou_forma));

  // Fase 8/F3: interruptor "avisar antes de cobrar" - desligado por padrao
  // (a.avisar_antes_cobrar vem 0/1 do banco). Mesmo padrao visual de
  // static/js/secoes/assistente/avisos.js (.aviso-toggle/.aviso-label).
  const labelAviso = criarEl("label", "aviso-toggle assinatura-aviso-toggle");
  const chkAviso = document.createElement("input");
  chkAviso.type = "checkbox";
  chkAviso.className = "aviso-ligado";
  chkAviso.checked = !!a.avisar_antes_cobrar;
  chkAviso.setAttribute("aria-label", `Avisar antes de cobrar: ${nome}`);
  chkAviso.addEventListener("change", async () => {
    chkAviso.disabled = true;
    const r = await apiFetch(`/api/financas/assinaturas/${a.id}/avisar_antes_cobrar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ligado: chkAviso.checked }),
    });
    if (!r) chkAviso.checked = !chkAviso.checked;
    chkAviso.disabled = false;
  });
  labelAviso.appendChild(chkAviso);
  labelAviso.appendChild(criarEl("span", "aviso-label", "Avisar antes de cobrar"));
  corpo.appendChild(labelAviso);

  li.appendChild(corpo);

  const acoes = criarEl("div", "lista-item-acoes");
  const btnCancelar = criarEl("button", "btn btn-secundario btn-cancelar-assinatura", "Cancelar");
  btnCancelar.type = "button";
  btnCancelar.setAttribute("aria-label", `Cancelar assinatura ${nome}`);
  btnCancelar.addEventListener("click", async () => {
    btnCancelar.disabled = true;
    const r = await apiFetch(`/api/financas/assinaturas/${a.id}/cancelar`, { method: "POST" });
    if (r) {
      removerLiAnimado(li, loadAssinaturas);
    } else {
      btnCancelar.disabled = false;
    }
  });
  acoes.appendChild(btnCancelar);
  acoes.appendChild(botaoApagarFinancas(`/api/financas/assinaturas/${a.id}`, li, nome));
  li.appendChild(acoes);
  return li;
}

function criarItemParcela(c) {
  const nome = textoFinancas(c.descricao, "Sem descricao");
  const nParcelas = numeroFinancas(c.n_parcelas);
  const atual = numeroFinancas(c.parcela_atual_calculada);
  const metaPartes = [`${fmtMoedaFinancas(c.valor_parcela)}/mes`];
  if (atual !== null && nParcelas !== null) metaPartes.push(`parcela ${atual}/${nParcelas}`);
  if (textoFinancas(c.mes_termino_nome, "")) metaPartes.push(`termina ${c.mes_termino_nome}`);
  const li = criarEl("li", "lista-item");
  const corpo = criarEl("div", "lista-item-corpo");
  corpo.appendChild(criarEl("span", "lista-item-titulo", nome));
  corpo.appendChild(criarEl("span", "lista-item-meta valor-mono", metaPartes.join(" · ")));
  if (textoFinancas(c.cartao, "")) corpo.appendChild(criarChipCartao(c.cartao));

  const pagas = numeroFinancas(c.parcelas_pagas);
  if (pagas !== null && nParcelas) {
    const progresso = criarEl("div", "meta-progresso parcela-progresso");
    const barra = criarEl("div", "meta-progresso-barra");
    barra.style.width = `${Math.max(0, Math.min(100, (pagas / nParcelas) * 100))}%`;
    progresso.appendChild(barra);
    corpo.appendChild(progresso);
  }
  li.appendChild(corpo);

  const acoes = criarEl("div", "lista-item-acoes");
  acoes.appendChild(botaoApagarFinancas(`/api/financas/parcelas/${c.id}`, li, nome));
  li.appendChild(acoes);
  return li;
}

function desenharLimiteCartao(impactos) {
  const card = $("#limite-cartao-card");
  const alvo = Array.isArray(impactos) ? impactos.find((i) => i && Array.isArray(i.meses) && i.meses.length) : null;
  if (!alvo) {
    card.hidden = true;
    return;
  }
  // So o primeiro cartao citado (a tela e "mini grafico", nao um dashboard
  // completo) - com limite configurado mostra fracao (%), sem limite mostra
  // o total comprometido em R$ mesmo (nunca inventa um limite).
  const cartao = textoFinancas(alvo.cartao, "cartão");
  card.hidden = false;
  $("#limite-cartao-titulo").textContent =
    impactos.length > 1 ? `Limite comprometido · ${cartao} (+${impactos.length - 1})` : `Limite comprometido · ${cartao}`;

  const limite = numeroFinancas(alvo.limite);
  const temLimite = limite !== null && limite > 0;
  const dados = alvo.meses
    .filter((m) => m && typeof m.mes === "string")
    .map((m) => ({
      data: `${m.mes}-01`,
      total: temLimite ? Math.round((numeroFinancas(m.fracao) || 0) * 1000) / 10 : numeroFinancas(m.total) || 0,
    }));
  desenharGraficoBarras($("#grafico-limite-cartao"), dados, {
    cor: "var(--cor-financeiro)",
    formatarValor: temLimite ? (v) => `${v}%` : fmtMoedaFinancas,
    rotulo: `Projeção de comprometimento do cartão ${cartao} nos próximos meses`,
    altura: 84,
  });
  $("#limite-cartao-legenda").textContent = temLimite
    ? `Limite de ${fmtMoedaFinancas(limite)}. Só conta assinatura e parcela: pode ter mais gasto no cartão além disso.`
    : "Sem limite configurado pra esse cartão (aba Bancos): mostrando o total comprometido em R$.";
}

async function loadComprometido() {
  const data = await apiFetch("/api/financas/comprometido");
  if (!data || typeof data !== "object") return;
  const total = data.total_mensal && typeof data.total_mensal === "object" ? data.total_mensal : {};
  const valorTotal = numeroFinancas(total.total) || 0;
  const temAlgo = valorTotal > 0;
  $("#comprometido-box").hidden = !temAlgo;
  $("#comprometido-vazio").hidden = temAlgo;
  if (temAlgo) {
    const nA = Array.isArray(total.detalhe_assinaturas) ? total.detalhe_assinaturas.length : 0;
    const nP = Array.isArray(total.detalhe_parcelas) ? total.detalhe_parcelas.length : 0;
    $("#comprometido-total").textContent = fmtMoedaFinancas(valorTotal);
    $("#chip-assinaturas").textContent = `${nA} assinatura(s) · ${fmtMoedaFinancas(total.assinaturas_total || 0)}`;
    $("#chip-parcelas").textContent = `${nP} parcela(s) · ${fmtMoedaFinancas(total.parcelas_total || 0)}`;
  }
  desenharLimiteCartao(data.impacto_limite_cartao);
  // Fase 8: lista antiga de "proximas cobrancas" removida (dedup com o bloco
  // unificado da aba Gastos - ver gastos.js). data.proximas_cobrancas nao e
  // mais usada aqui.
}

async function loadAssinaturasAtivas() {
  const data = await apiFetch("/api/financas/assinaturas?ativas=1");
  if (!data || typeof data !== "object") return;
  const assinaturas = Array.isArray(data.assinaturas) ? data.assinaturas.filter((a) => a && typeof a === "object") : [];
  const lista = $("#lista-assinaturas-ativas");
  lista.innerHTML = "";
  lista.hidden = assinaturas.length === 0;
  $("#assinaturas-ativas-vazio").hidden = assinaturas.length > 0;
  assinaturas.forEach((a) => lista.appendChild(criarItemAssinaturaAtiva(a)));
}

async function loadParcelasEmAndamento() {
  const data = await apiFetch("/api/financas/parcelas?em_andamento=1");
  if (!data || typeof data !== "object") return;
  const parcelas = Array.isArray(data.parcelas) ? data.parcelas.filter((c) => c && typeof c === "object") : [];
  const lista = $("#lista-parcelas");
  lista.innerHTML = "";
  lista.hidden = parcelas.length === 0;
  $("#parcelas-vazio").hidden = parcelas.length > 0;
  parcelas.forEach((c) => lista.appendChild(criarItemParcela(c)));
}

async function loadAssinaturas() {
  loadComprometido();
  loadAssinaturasAtivas();
  loadParcelasEmAndamento();
}

// ---- Formularios (bottom sheet) ----
// `novalidate` no <form>: a validacao e daqui, em pt-BR, com o erro dentro do
// sheet. Teto de valor: acima de R$ 100 milhoes e quase certo erro de digitacao
// (e estoura o layout em 390px); a API da N1 nao tem teto proprio.

const VALOR_MAX_FINANCAS = 100000000;
const PARCELAS_MAX_FINANCAS = 600;

// "abc", "1e400", "-5" -> NaN; "" -> null; aceita virgula decimal ("21,90")
// e milhar com ponto ("1.234,56").
function lerValorFinancas(input) {
  const bruto = String(input.value || "").trim().replace(/\s/g, "");
  if (!bruto) return null;
  const normalizado = /^\d{1,3}(\.\d{3})+(,\d+)?$/.test(bruto) ? bruto.replace(/\./g, "").replace(",", ".") : bruto.replace(",", ".");
  if (!/^\d+(\.\d+)?$/.test(normalizado)) return NaN;
  const n = Number(normalizado);
  return Number.isFinite(n) ? Math.round(n * 100) / 100 : NaN;
}

function lerInteiroFinancas(input) {
  const bruto = String(input.value || "").trim();
  if (!/^\d{1,6}$/.test(bruto)) return null;
  return Number(bruto);
}

function valorValidoFinancas(v) {
  return v !== null && Number.isFinite(v) && v > 0 && v <= VALOR_MAX_FINANCAS;
}

let salvandoAssinatura = false;
$("#form-nova-assinatura").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (salvandoAssinatura) return;
  const nome = $("#assinatura-nome").value.trim();
  const valor = lerValorFinancas($("#assinatura-valor"));
  const dia = lerInteiroFinancas($("#assinatura-dia"));
  if (!nome) return mostrarErroSheet("assinatura-erro", "Dá um nome pra assinatura.");
  if (!valorValidoFinancas(valor))
    return mostrarErroSheet("assinatura-erro", "Valor mensal precisa ser um número maior que zero (até R$ 100 milhões).");
  if (dia === null || dia < 1 || dia > 31)
    return mostrarErroSheet("assinatura-erro", "Dia da cobrança vai de 1 a 31 (dia 31 em mês curto cobra no último dia).");
  $("#assinatura-erro").hidden = true;
  const btn = $("#assinatura-salvar-btn");
  salvandoAssinatura = true;
  setBotaoCarregando(btn, true, "Salvando...");
  const r = await apiFetch("/api/financas/assinaturas", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      nome: nome.slice(0, 80),
      valor,
      dia_cobranca: dia,
      cartao_ou_forma: $("#assinatura-cartao").value.trim() || null,
      categoria: $("#assinatura-categoria").value.trim() || null,
    }),
  });
  setBotaoCarregando(btn, false, "Salvar assinatura");
  salvandoAssinatura = false;
  if (!r) return mostrarErroSheet("assinatura-erro", "Não consegui salvar agora. Confere os campos e tenta de novo.");
  sucessoSheetFinancas($("#form-nova-assinatura"));
  loadAssinaturas();
});

let salvandoParcela = false;
$("#form-nova-parcela").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (salvandoParcela) return;
  const descricao = $("#parcela-descricao").value.trim();
  const nParcelas = lerInteiroFinancas($("#parcela-n"));
  const valorTotal = lerValorFinancas($("#parcela-valor-total"));
  const valorParcela = lerValorFinancas($("#parcela-valor-parcela"));
  const primeiraInput = $("#parcela-primeira");
  const primeira = primeiraInput.value;
  if (!descricao) return mostrarErroSheet("parcela-erro", "Dá uma descrição pra compra.");
  if (nParcelas === null || nParcelas < 1 || nParcelas > PARCELAS_MAX_FINANCAS)
    return mostrarErroSheet("parcela-erro", `Número de parcelas vai de 1 a ${PARCELAS_MAX_FINANCAS}.`);
  if (valorTotal === null && valorParcela === null)
    return mostrarErroSheet("parcela-erro", "Informa o valor total ou o valor da parcela.");
  if ((valorTotal !== null && !valorValidoFinancas(valorTotal)) || (valorParcela !== null && !valorValidoFinancas(valorParcela)))
    return mostrarErroSheet("parcela-erro", "Valor precisa ser um número maior que zero (até R$ 100 milhões).");
  // Campo de data com texto incompleto: o navegador devolve "" mas marca badInput.
  if ((primeiraInput.validity && primeiraInput.validity.badInput) || (primeira && !(primeira >= "2000-01-01" && primeira <= "2100-12-31")))
    return mostrarErroSheet("parcela-erro", "Data da primeira parcela inválida (use uma data entre 2000 e 2100).");
  $("#parcela-erro").hidden = true;
  const btn = $("#parcela-salvar-btn");
  salvandoParcela = true;
  setBotaoCarregando(btn, true, "Salvando...");
  const r = await apiFetch("/api/financas/parcelas", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      descricao: descricao.slice(0, 120),
      n_parcelas: nParcelas,
      valor_total: valorTotal,
      valor_parcela: valorParcela,
      cartao: $("#parcela-cartao").value.trim() || null,
      primeira_parcela: primeira || null,
    }),
  });
  setBotaoCarregando(btn, false, "Salvar parcela");
  salvandoParcela = false;
  if (!r) return mostrarErroSheet("parcela-erro", "Nao consegui salvar agora. Confere os campos e tenta de novo.");
  sucessoSheetFinancas($("#form-nova-parcela"));
  loadAssinaturas();
});

// ---- Carga: a aba Gastos e recarregada por showTab() (nucleo/navegacao.js,
// compartilhado - esta faixa nao edita esse arquivo), que ainda nao conhece
// esta secao nova. Listener proprio a mais no mesmo botao de aba (nao
// substitui nada, so soma) ate o integrador somar a chamada direto la. ----

document.querySelectorAll(".tab-btn").forEach((btn) => {
  if (btn.dataset.tab === "gastos") btn.addEventListener("click", loadAssinaturas);
});
