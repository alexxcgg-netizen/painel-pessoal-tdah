// static/js/secoes/bancos/bancos.js - Secao bancos > bancos (HTML: templates/secoes/bancos/bancos.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 2903-3068.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

function criarItemBanco(conta) {
  const li = document.createElement("li");
  li.className = "item";

  const linha = document.createElement("div");
  linha.className = "item-linha";

  const info = document.createElement("div");
  const nome = document.createElement("span");
  nome.className = "item-titulo";
  const rotuloTipo = conta.tipo === "cartao" ? "cartao" : "conta";
  const banco = textoFinancas(conta.banco, "banco");
  nome.textContent = banco.charAt(0).toUpperCase() + banco.slice(1);
  const tipoChip = document.createElement("span");
  tipoChip.className = "chip chip--compacto banco-tipo-chip";
  tipoChip.textContent = rotuloTipo;
  nome.appendChild(tipoChip);
  info.appendChild(nome);

  const stats = document.createElement("span");
  stats.className = "item-quando valor-mono";
  stats.textContent = conta.ultima_transacao
    ? `${numeroFinancas(conta.total_transacoes) ?? 0} transacao(oes) \u00b7 ${fmtMoedaFinancas(conta.total_gasto)} em gastos \u00b7 ultima em ${conta.ultima_transacao}`
    : "nenhuma transacao ainda";
  info.appendChild(stats);

  linha.appendChild(info);

  if (numeroFinancas(conta.saldo) !== null) {
    const saldo = document.createElement("span");
    saldo.className = "banco-saldo" + (conta.saldo < 0 ? " banco-saldo-negativo" : "");
    saldo.textContent = fmtMoedaFinancas(conta.saldo);
    linha.appendChild(saldo);
  }

  li.appendChild(linha);

  // Fase 6 (US-E15): limite manual do cartao - Open Finance nao manda isso,
  // entao o Alex digita. Sem limite configurado o aviso de 90% (US-E8)
  // simplesmente nao existe - nunca inventa um numero.
  if (conta.tipo === "cartao") {
    li.appendChild(criarLimiteCartaoBox(conta));
  }

  return li;
}

function criarLimiteCartaoBox(conta) {
  const box = document.createElement("div");
  box.className = "limite-cartao";

  const fracao = conta.limite_info ? numeroFinancas(conta.limite_info.fracao) : null;
  if (fracao !== null) {
    const barra = document.createElement("div");
    barra.className = "limite-cartao-trilho";
    const preenchido = document.createElement("div");
    preenchido.className = "limite-cartao-preenchido" + (fracao >= 0.9 ? " limite-cartao-alerta" : "");
    preenchido.style.width = `${Math.max(0, Math.min(fracao * 100, 100))}%`;
    barra.appendChild(preenchido);
    box.appendChild(barra);
    const texto = document.createElement("p");
    texto.className = "item-quando valor-mono";
    texto.textContent = `${fmtMoedaFinancas(conta.gasto_ciclo)} de ${fmtMoedaFinancas(conta.limite)} (${Math.round(fracao * 100)}%) \u00b7 sobra ${fmtMoedaFinancas(conta.limite_info.sobra)}`;
    box.appendChild(texto);
  }

  const linha = document.createElement("div");
  linha.className = "form-linha";
  const input = document.createElement("input");
  input.className = "campo valor-mono";
  input.type = "number";
  input.min = "0";
  input.step = "0.01";
  input.inputMode = "decimal";
  input.placeholder = "Limite do cartao (opcional)";
  input.setAttribute("aria-label", `Limite do cartao ${conta.banco}`);
  if (conta.limite != null) input.value = conta.limite;
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "btn btn-secundario";
  btn.textContent = "Salvar limite";
  btn.addEventListener("click", async () => {
    setBotaoCarregando(btn, true, "salvando...");
    const valor = input.value.trim();
    // Fase 7 (C3c): texto/negativo/infinito nao vai pro back como NaN/null silencioso.
    const numero = valor === "" ? null : Number(valor);
    if (numero !== null && !(Number.isFinite(numero) && numero >= 0)) {
      setBotaoCarregando(btn, false, "Salvar limite");
      mostrarErro("Limite precisa ser um numero maior ou igual a zero (ou em branco).");
      return;
    }
    const ok = await apiFetch(`/api/bancos/${conta.id}/limite`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ limite: numero }),
    });
    setBotaoCarregando(btn, false, "Salvar limite");
    if (ok) loadBancos();
  });
  linha.appendChild(input);
  linha.appendChild(btn);
  box.appendChild(linha);
  return box;
}

async function loadBancos() {
  const [contas, status, patrimonio] = await Promise.all([
    apiFetch("/api/bancos"),
    apiFetch("/api/bancos/sync-status"),
    apiFetch("/api/patrimonio"),
  ]);

  if (status) {
    $("#bancos-status").textContent = typeof status.info === "string" ? status.info : "";
    $("#conectar-btn").hidden = !status.sincronizacao_automatica;
    // aviso discreto - so aparece quando ENCRYPTION_KEY nao esta configurada
    // (ver docs/SEGURANCA.md); nao bloqueia nada, so avisa.
    $("#cripto-aviso").hidden = status.criptografia_ativa !== false;
  }

  if (patrimonio && typeof patrimonio === "object") {
    $("#patrimonio-total").textContent = fmtMoedaFinancas(patrimonio.patrimonio_total);
    const detalhes = [];
    if (numeroFinancas(patrimonio.saldo_bancario)) detalhes.push("saldo em conta/cartao: ", { r: patrimonio.saldo_bancario });
    if (numeroFinancas(patrimonio.valor_guardado_metas)) {
      if (detalhes.length) detalhes.push(" \u00b7 ");
      detalhes.push("guardado em metas: ", { r: patrimonio.valor_guardado_metas });
    }
    preencherLinhaComValores($("#patrimonio-detalhe"), detalhes);
    const nContas = Array.isArray(patrimonio.contas) ? patrimonio.contas.length : 0;
    const nMetas = Array.isArray(patrimonio.metas) ? patrimonio.metas.length : 0;
    $("#patrimonio-box").hidden = nContas === 0 && nMetas === 0;
  }

  if (!Array.isArray(contas)) return;
  const list = $("#lista-bancos");
  list.innerHTML = "";
  $("#bancos-vazio").hidden = contas.length > 0;
  contas.filter((c) => c && typeof c === "object").forEach((c) => list.appendChild(criarItemBanco(c)));
}

let pluggyScriptCarregado = null;

function carregarPluggyScript() {
  if (pluggyScriptCarregado) return pluggyScriptCarregado;
  pluggyScriptCarregado = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://cdn.pluggy.ai/pluggy-connect/latest/pluggy-connect.js";
    script.onload = resolve;
    script.onerror = reject;
    document.head.appendChild(script);
  });
  return pluggyScriptCarregado;
}

$("#conectar-btn").addEventListener("click", async () => {
  const btn = $("#conectar-btn");
  setBotaoCarregando(btn, true, "Abrindo...");

  const [tokenData] = await Promise.all([
    apiFetch("/api/bancos/conectar/token", { method: "POST" }),
    carregarPluggyScript().catch(() => mostrarErro("Nao consegui carregar o widget de conexao.")),
  ]);

  setBotaoCarregando(btn, false, "Conectar banco automaticamente");
  if (!tokenData) return;

  const widget = new PluggyConnect({
    connectToken: tokenData.connect_token,
    includeSandbox: false,
    onSuccess: async ({ item }) => {
      setBotaoCarregando(btn, true, "Sincronizando...");
      const data = await apiFetch("/api/bancos/conectar/finalizar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item_id: item.id }),
      });
      setBotaoCarregando(btn, false, "Conectar banco automaticamente");
      if (data) loadBancos();
    },
    onError: () => mostrarErro("A conexao com o banco falhou. Tenta de novo."),
  });
  widget.init();
});
