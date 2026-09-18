const $ = (sel) => document.querySelector(sel);

let textoPendente = null;

const fmtMoeda = (valor) =>
  Number(valor).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

function mostrarErro(msg) {
  const banner = $("#erro-banner");
  banner.textContent = msg;
  banner.hidden = false;
}

function limparErro() {
  $("#erro-banner").hidden = true;
}

async function apiFetch(url, options) {
  let res;
  try {
    res = await fetch(url, options);
  } catch {
    mostrarErro("Sem conexao com o servidor. Confere se o painel esta rodando.");
    return null;
  }
  let data = null;
  try {
    data = await res.json();
  } catch {
    // resposta sem corpo (ex: 204) - segue com data null
  }
  if (!res.ok) {
    mostrarErro((data && data.error) || `Erro inesperado (HTTP ${res.status}).`);
    return null;
  }
  limparErro();
  return data;
}

function showTab(name) {
  document.querySelectorAll(".tab-content").forEach((el) => {
    el.hidden = el.id !== `tab-${name}`;
  });
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === name);
  });
  if (name === "tarefas") loadTasks();
  if (name === "gastos") {
    loadExpenses();
    loadMetas();
  }
  if (name === "bancos") loadBancos();
  if (name === "construtora") loadConstrutora();
}

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => showTab(btn.dataset.tab));
});

function setBotaoCarregando(btn, carregando, rotulo) {
  if (carregando) {
    btn.dataset.rotuloOriginal = btn.dataset.rotuloOriginal || btn.textContent;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span>${rotulo}`;
  } else {
    btn.disabled = false;
    btn.textContent = btn.dataset.rotuloOriginal || rotulo;
  }
}

function pulsarSucesso(el) {
  el.classList.remove("sucesso");
  // forca reflow pra animacao reiniciar mesmo em capturas seguidas
  void el.offsetWidth;
  el.classList.add("sucesso");
}

async function enviarCaptura(text, clarificacao) {
  const capturaBtn = $("#captura-btn");
  const duvidaBtn = $("#duvida-btn");
  setBotaoCarregando(capturaBtn, true, "Pensando...");
  duvidaBtn.disabled = true;

  const data = await apiFetch("/api/capture", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, clarificacao }),
  });

  setBotaoCarregando(capturaBtn, false, "Adicionar");
  duvidaBtn.disabled = false;

  if (!data) return;

  loadUso();

  if (data.duvida) {
    textoPendente = data.texto_original;
    $("#duvida-texto").textContent = data.duvida;
    $("#duvida-input").value = "";
    $("#duvida-box").hidden = false;
    return;
  }

  textoPendente = null;
  $("#duvida-box").hidden = true;
  pulsarSucesso($("#captura-input"));
  loadSummary();
  if (!$("#tab-tarefas").hidden) loadTasks();
  if (!$("#tab-gastos").hidden) {
    loadExpenses();
    loadMetas();
  }
}

$("#captura-btn").addEventListener("click", () => {
  const input = $("#captura-input");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  enviarCaptura(text, "");
});

$("#captura-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") $("#captura-btn").click();
});

$("#duvida-btn").addEventListener("click", () => {
  const resposta = $("#duvida-input").value.trim();
  if (!resposta || !textoPendente) return;
  enviarCaptura(textoPendente, resposta);
});

$("#duvida-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") $("#duvida-btn").click();
});

async function loadSummary() {
  $("#resumo-texto").textContent = "Carregando...";

  const [data, tasks, metas] = await Promise.all([
    apiFetch("/api/summary/today"),
    apiFetch("/api/tasks"),
    apiFetch("/api/metas"),
  ]);

  if (tasks) $("#stat-tarefas").textContent = tasks.length;
  if (metas) {
    const ativas = metas.filter((m) => m.valor_guardado < m.valor_alvo).length;
    $("#stat-metas").textContent = ativas;
  }

  if (!data) {
    $("#resumo-texto").textContent = "Nao consegui gerar o resumo agora.";
    return;
  }
  $("#stat-gasto").textContent = fmtMoeda(data.gasto_hoje);
  $("#resumo-texto").textContent = data.summary;
  $("#resumo-stats").textContent = `${data.tarefas_concluidas} tarefa(s) concluida(s) hoje`;
}

async function loadUso() {
  const data = await apiFetch("/api/uso/total");
  if (!data) return;
  $("#uso-custo").textContent = `gasto com IA ate agora: ${fmtMoeda(data.custo_usd)}`;
}

function criarItemTarefa(t) {
  const li = document.createElement("li");
  li.className = "item";

  const linha = document.createElement("div");
  linha.className = "item-linha";

  const tituloWrap = document.createElement("div");
  const titulo = document.createElement("span");
  titulo.className = "item-titulo";
  titulo.textContent = t.title;
  tituloWrap.appendChild(titulo);
  if (t.due_at) {
    const quando = document.createElement("span");
    quando.className = "item-quando";
    quando.textContent = t.due_at;
    tituloWrap.appendChild(quando);
  }

  const acoes = document.createElement("div");
  acoes.className = "item-acoes";

  if (t.subtasks.length === 0) {
    const btnQuebrar = document.createElement("button");
    btnQuebrar.textContent = "quebrar em passos";
    btnQuebrar.addEventListener("click", async () => {
      setBotaoCarregando(btnQuebrar, true, "quebrando...");
      const data = await apiFetch(`/api/tasks/${t.id}/breakdown`, { method: "POST" });
      if (data) loadTasks();
      else setBotaoCarregando(btnQuebrar, false, "quebrar em passos");
    });
    acoes.appendChild(btnQuebrar);
  }

  const btnConcluir = document.createElement("button");
  btnConcluir.className = "primario";
  btnConcluir.textContent = "concluir";
  btnConcluir.addEventListener("click", async () => {
    const data = await apiFetch(`/api/tasks/${t.id}/complete`, { method: "POST" });
    if (data) {
      loadTasks();
      loadSummary();
    }
  });
  acoes.appendChild(btnConcluir);

  linha.appendChild(tituloWrap);
  linha.appendChild(acoes);
  li.appendChild(linha);

  if (t.subtasks.length > 0) {
    const sub = document.createElement("ul");
    sub.className = "subtarefas";
    t.subtasks.forEach((s) => {
      const subLi = document.createElement("li");
      subLi.className = "subtarefa" + (s.completed_at ? " concluida" : "");

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = Boolean(s.completed_at);
      checkbox.disabled = Boolean(s.completed_at);
      checkbox.addEventListener("change", async () => {
        const data = await apiFetch(`/api/subtasks/${s.id}/complete`, { method: "POST" });
        if (data) loadTasks();
      });

      const label = document.createElement("span");
      label.textContent = s.title;

      subLi.appendChild(checkbox);
      subLi.appendChild(label);
      sub.appendChild(subLi);
    });
    li.appendChild(sub);
  }

  return li;
}

async function loadTasks() {
  const tasks = await apiFetch("/api/tasks");
  if (!tasks) return;
  const list = $("#lista-tarefas");
  list.innerHTML = "";
  $("#tarefas-vazio").hidden = tasks.length > 0;
  tasks.forEach((t) => list.appendChild(criarItemTarefa(t)));
}

function criarItemGasto(e) {
  const li = document.createElement("li");
  li.className = "item";

  const linha = document.createElement("div");
  linha.className = "item-linha";

  const info = document.createElement("div");
  const valor = document.createElement("span");
  valor.className = "gasto-valor";
  valor.textContent = fmtMoeda(e.amount);
  const cat = document.createElement("span");
  cat.className = "gasto-categoria";
  cat.dataset.cat = e.category;
  cat.textContent = e.category;
  info.appendChild(valor);
  info.appendChild(cat);
  if (e.description) {
    const desc = document.createElement("span");
    desc.className = "item-quando";
    desc.textContent = e.description;
    info.appendChild(desc);
  }

  linha.appendChild(info);
  li.appendChild(linha);
  return li;
}

async function loadExpenses() {
  const expenses = await apiFetch("/api/expenses");
  if (!expenses) return;
  const list = $("#lista-gastos");
  list.innerHTML = "";
  $("#gastos-vazio").hidden = expenses.length > 0;
  expenses.forEach((e) => list.appendChild(criarItemGasto(e)));
}

function criarItemBanco(conta) {
  const li = document.createElement("li");
  li.className = "item";

  const linha = document.createElement("div");
  linha.className = "item-linha";

  const info = document.createElement("div");
  const nome = document.createElement("span");
  nome.className = "item-titulo";
  const rotuloTipo = conta.tipo === "cartao" ? "cartao" : "conta";
  nome.textContent = `${conta.banco.charAt(0).toUpperCase() + conta.banco.slice(1)} (${rotuloTipo})`;
  info.appendChild(nome);

  const stats = document.createElement("span");
  stats.className = "item-quando";
  stats.textContent = conta.ultima_transacao
    ? `${conta.total_transacoes} transacao(oes) - ${fmtMoeda(conta.total_gasto)} em gastos - ultima em ${conta.ultima_transacao}`
    : "nenhuma transacao ainda";
  info.appendChild(stats);

  linha.appendChild(info);
  li.appendChild(linha);
  return li;
}

async function loadBancos() {
  const [contas, status] = await Promise.all([
    apiFetch("/api/bancos"),
    apiFetch("/api/bancos/sync-status"),
  ]);

  if (status) {
    $("#bancos-status").textContent = status.info;
    $("#conectar-btn").hidden = !status.sincronizacao_automatica;
  }

  if (!contas) return;
  const list = $("#lista-bancos");
  list.innerHTML = "";
  $("#bancos-vazio").hidden = contas.length > 0;
  contas.forEach((c) => list.appendChild(criarItemBanco(c)));
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

$("#importar-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const banco = $("#banco-select").value;
  const tipo = $("#tipo-select").value;
  const arquivo = $("#ofx-input").files[0];
  if (!arquivo) return;

  const importarBtn = $("#importar-btn");
  setBotaoCarregando(importarBtn, true, "Importando...");

  const form = new FormData();
  form.append("banco", banco);
  form.append("tipo", tipo);
  form.append("arquivo", arquivo);
  const data = await apiFetch("/api/bancos/importar", { method: "POST", body: form });

  setBotaoCarregando(importarBtn, false, "Importar extrato");

  if (!data) return;
  $("#ofx-input").value = "";
  $("#bancos-status").textContent =
    `Importado: ${data.novas} nova(s), ${data.duplicadas} ja existiam de ${data.encontradas} encontradas.`;
  loadBancos();
});

function criarItemMeta(meta) {
  const li = document.createElement("li");
  li.className = "item";

  const titulo = document.createElement("span");
  titulo.className = "item-titulo";
  titulo.textContent = meta.titulo;
  li.appendChild(titulo);

  const pct = Math.min(100, (meta.valor_guardado / meta.valor_alvo) * 100 || 0);
  const barra = document.createElement("div");
  barra.className = "meta-progresso";
  const barraInterna = document.createElement("div");
  barraInterna.className = "meta-progresso-barra";
  barraInterna.style.width = `${pct}%`;
  barra.appendChild(barraInterna);
  li.appendChild(barra);

  const detalhe = document.createElement("p");
  detalhe.className = "meta-detalhe";
  const guardadoTxt = `${fmtMoeda(meta.valor_guardado)} de ${fmtMoeda(meta.valor_alvo)} guardado`;
  const prazoTxt = meta.prazo
    ? meta.por_mes != null
      ? ` - guarde ${fmtMoeda(meta.por_mes)}/mes ate ${meta.prazo}`
      : ` - prazo: ${meta.prazo}`
    : " - sem prazo definido";
  detalhe.textContent = guardadoTxt + prazoTxt;
  li.appendChild(detalhe);

  const guardarWrap = document.createElement("div");
  guardarWrap.className = "meta-guardar";
  const input = document.createElement("input");
  input.type = "number";
  input.step = "0.01";
  input.min = "0.01";
  input.placeholder = "guardei R$...";
  const btn = document.createElement("button");
  btn.textContent = "Registrar";
  btn.addEventListener("click", async () => {
    const valor = parseFloat(input.value);
    if (!valor || valor <= 0) return;
    setBotaoCarregando(btn, true, "salvando...");
    const data = await apiFetch(`/api/metas/${meta.id}/guardar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ valor }),
    });
    setBotaoCarregando(btn, false, "Registrar");
    if (data) loadMetas();
  });
  guardarWrap.appendChild(input);
  guardarWrap.appendChild(btn);
  li.appendChild(guardarWrap);

  return li;
}

async function loadMetas() {
  const metas = await apiFetch("/api/metas");
  if (!metas) return;
  const list = $("#lista-metas");
  list.innerHTML = "";
  $("#metas-vazio").hidden = metas.length > 0;
  metas.forEach((m) => list.appendChild(criarItemMeta(m)));
}

async function loadConstrutora() {
  $("#construtora-info").textContent = "Carregando...";
  const data = await apiFetch("/api/construtora/resumo");
  if (!data) return;
  if (!data.configurado) {
    $("#construtora-info").textContent = "Ainda nao conectado a API da construtora.";
  } else if (data.erro) {
    $("#construtora-info").textContent = data.erro;
  } else {
    $("#construtora-info").textContent = JSON.stringify(data.dados);
  }
}

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/static/service-worker.js");
}

loadSummary();
loadUso();
