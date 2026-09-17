const $ = (sel) => document.querySelector(sel);

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

$("#captura-btn").addEventListener("click", async () => {
  const input = $("#captura-input");
  const text = input.value.trim();
  if (!text) return;
  await fetch("/api/capture", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  input.value = "";
  loadSummary();
});

async function loadSummary() {
  const res = await fetch("/api/summary/today");
  const data = await res.json();
  $("#resumo-texto").textContent = data.summary;
}

async function loadTasks() {
  const res = await fetch("/api/tasks");
  const tasks = await res.json();
  const list = $("#lista-tarefas");
  list.innerHTML = "";
  tasks.forEach((t) => {
    const li = document.createElement("li");
    li.textContent = t.title;
    const btn = document.createElement("button");
    btn.textContent = "concluir";
    btn.addEventListener("click", async () => {
      await fetch(`/api/tasks/${t.id}/complete`, { method: "POST" });
      loadTasks();
    });
    li.appendChild(btn);
    list.appendChild(li);
  });
}

async function loadExpenses() {
  const res = await fetch("/api/expenses");
  const expenses = await res.json();
  const list = $("#lista-gastos");
  list.innerHTML = "";
  expenses.forEach((e) => {
    const li = document.createElement("li");
    li.textContent = `R$ ${e.amount.toFixed(2)} - ${e.category} - ${e.description || ""}`;
    list.appendChild(li);
  });
}

async function loadConstrutora() {
  const res = await fetch("/api/construtora/resumo");
  const data = await res.json();
  $("#construtora-info").textContent = data.configurado
    ? JSON.stringify(data.dados)
    : "Ainda nao conectado a API da construtora.";
}

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/static/service-worker.js");
}

loadSummary();
