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
  if (name === "gastos") loadExpenses();
  if (name === "construtora") loadConstrutora();
}

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => showTab(btn.dataset.tab));
});

async function enviarCaptura(text, clarificacao) {
  const capturaBtn = $("#captura-btn");
  const duvidaBtn = $("#duvida-btn");
  capturaBtn.disabled = true;
  duvidaBtn.disabled = true;
  const rotuloOriginal = capturaBtn.textContent;
  capturaBtn.textContent = "Pensando...";

  const data = await apiFetch("/api/capture", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, clarificacao }),
  });

  capturaBtn.disabled = false;
  duvidaBtn.disabled = false;
  capturaBtn.textContent = rotuloOriginal;

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
  loadSummary();
  if (!$("#tab-tarefas").hidden) loadTasks();
  if (!$("#tab-gastos").hidden) loadExpenses();
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
  const data = await apiFetch("/api/summary/today");
  if (!data) {
    $("#resumo-texto").textContent = "Nao consegui gerar o resumo agora.";
    return;
  }
  $("#resumo-texto").textContent = data.summary;
  $("#resumo-stats").textContent =
    `${data.tarefas_concluidas} tarefa(s) concluida(s) hoje - ${fmtMoeda(data.gasto_hoje)} gastos hoje`;
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
      btnQuebrar.disabled = true;
      btnQuebrar.textContent = "quebrando...";
      const data = await apiFetch(`/api/tasks/${t.id}/breakdown`, { method: "POST" });
      if (data) loadTasks();
      else {
        btnQuebrar.disabled = false;
        btnQuebrar.textContent = "quebrar em passos";
      }
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
