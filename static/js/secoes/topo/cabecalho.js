// static/js/secoes/topo/cabecalho.js - Secao topo > cabecalho (HTML: templates/secoes/topo/cabecalho.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 2407-2412, app.js 3938-3982, app.js 4111-4284.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadUso() {
  const data = await apiFetch("/api/uso/total");
  if (!data) return;
  $("#uso-custo").textContent = `gasto com IA ate agora: ${fmtUSD(data.custo_usd)}`;
}

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)));
}

async function initPush() {
  const btn = $("#push-btn");
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;

  const status = await apiFetch("/api/push/status");
  if (!status || !status.configurado) return;

  const reg = await navigator.serviceWorker.ready;
  const existente = await reg.pushManager.getSubscription();
  btn.hidden = false;

  if (existente) {
    btn.textContent = "Notificacoes ativadas";
    btn.disabled = true;
    return;
  }

  btn.addEventListener("click", async () => {
    const permissao = await Notification.requestPermission();
    if (permissao !== "granted") {
      mostrarErro("Permissao de notificacao negada no navegador.");
      return;
    }
    setBotaoCarregando(btn, true, "Ativando...");
    const subscription = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(status.public_key),
    });
    await apiFetch("/api/push/inscrever", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(subscription.toJSON()),
    });
    setBotaoCarregando(btn, false, "Notificacoes ativadas");
    btn.disabled = true;
  });
}

function initSilencio() {
  const btn = $("#silencio-btn");
  const painel = $("#silencio-painel");
  const inicioInput = $("#silencio-inicio");
  const fimInput = $("#silencio-fim");
  const status = $("#silencio-status");
  let carregado = false;

  async function carregar() {
    const dados = await apiFetch("/api/configuracoes/silencio");
    if (!dados) return;
    inicioInput.value = dados.inicio;
    fimInput.value = dados.fim;
    carregado = true;
  }

  btn.addEventListener("click", async () => {
    const aberto = btn.getAttribute("aria-expanded") === "true";
    if (aberto) {
      btn.setAttribute("aria-expanded", "false");
      btn.classList.remove("ativo");
      painel.hidden = true;
      return;
    }
    btn.setAttribute("aria-expanded", "true");
    btn.classList.add("ativo");
    painel.hidden = false;
    if (!carregado) await carregar();
  });

  $("#silencio-salvar").addEventListener("click", async () => {
    const salvarBtn = $("#silencio-salvar");
    status.textContent = "";
    setBotaoCarregando(salvarBtn, true, "Salvando...");
    const dados = await apiFetch("/api/configuracoes/silencio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ inicio: inicioInput.value.trim(), fim: fimInput.value.trim() }),
    });
    setBotaoCarregando(salvarBtn, false, "Salvar");
    if (!dados) return;
    inicioInput.value = dados.inicio;
    fimInput.value = dados.fim;
    status.textContent = `Salvo: das ${dados.inicio} ate ${dados.fim}.`;
  });
}

let modoVisitanteAtivo = false;

function initModoVisitante() {
  const btn = $("#modo-visitante-btn");
  const painel = $("#modo-visitante-painel");
  const pinInput = $("#modo-visitante-pin");
  const status = $("#modo-visitante-status");

  function aplicarEstado(ativo) {
    modoVisitanteAtivo = ativo;
    btn.classList.toggle("ativo", ativo);
    btn.setAttribute("aria-pressed", ativo ? "true" : "false");
    if (!ativo) {
      painel.hidden = true;
      pinInput.value = "";
      status.textContent = "";
    }
    document.dispatchEvent(new CustomEvent("modo-visitante-mudou", { detail: { ativo } }));
  }

  // Estado inicial: a pagina ja carrega tudo no modo normal (init.js), entao
  // so avisa as secoes (evento modo-visitante-mudou -> recarrega gastos,
  // bancos, saude, medidas, previa, decisoes) se o modo visitante JA estiver
  // ligado. Antes disparava sempre e duplicava 6 chamadas em toda abertura.
  (async () => {
    const dados = await apiFetch("/api/modo-visitante");
    if (!dados) return;
    if (dados.ativo) {
      aplicarEstado(true);
    } else {
      modoVisitanteAtivo = false;
      btn.classList.remove("ativo");
      btn.setAttribute("aria-pressed", "false");
    }
  })();

  btn.addEventListener("click", async () => {
    if (!modoVisitanteAtivo) {
      const dados = await apiFetch("/api/modo-visitante", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ativar: true }),
      });
      if (dados) aplicarEstado(true);
      return;
    }
    painel.hidden = !painel.hidden;
  });

  $("#modo-visitante-desativar").addEventListener("click", async () => {
    const desativarBtn = $("#modo-visitante-desativar");
    status.textContent = "";
    setBotaoCarregando(desativarBtn, true, "Verificando...");
    const dados = await apiFetch("/api/modo-visitante", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ativar: false, pin: pinInput.value.trim() }),
    });
    setBotaoCarregando(desativarBtn, false, "Desativar");
    if (dados && dados.ativo === false) {
      aplicarEstado(false);
      return;
    }
    status.textContent = "PIN incorreto.";
    pinInput.value = "";
    pinInput.focus();
  });
}

function initModoViagem() {
  const btn = $("#modo-viagem-btn");
  const painel = $("#modo-viagem-painel");
  const ativoInput = $("#modo-viagem-ativo");
  const inicioInput = $("#modo-viagem-inicio");
  const fimInput = $("#modo-viagem-fim");
  const status = $("#modo-viagem-status");
  let carregado = false;

  async function carregar() {
    const dados = await apiFetch("/api/modo-viagem");
    if (!dados) return;
    ativoInput.checked = Boolean(dados.ativo);
    inicioInput.value = dados.data_inicio || "";
    fimInput.value = dados.data_fim || "";
    btn.classList.toggle("ativo", Boolean(dados.ativo_agora));
    carregado = true;
  }

  btn.addEventListener("click", async () => {
    const aberto = btn.getAttribute("aria-expanded") === "true";
    if (aberto) {
      btn.setAttribute("aria-expanded", "false");
      painel.hidden = true;
      return;
    }
    btn.setAttribute("aria-expanded", "true");
    painel.hidden = false;
    if (!carregado) await carregar();
  });

  $("#modo-viagem-salvar").addEventListener("click", async () => {
    const salvarBtn = $("#modo-viagem-salvar");
    status.textContent = "";
    setBotaoCarregando(salvarBtn, true, "Salvando...");
    const dados = await apiFetch("/api/modo-viagem", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ativo: ativoInput.checked,
        data_inicio: inicioInput.value || null,
        data_fim: fimInput.value || null,
      }),
    });
    setBotaoCarregando(salvarBtn, false, "Salvar");
    if (!dados) return;
    btn.classList.toggle("ativo", Boolean(dados.ativo_agora));
    status.textContent = dados.ativo_agora ? "Modo viagem ativo." : "Modo viagem desligado.";
  });
}

function initBackup() {
  const btn = $("#backup-btn");
  const painel = $("#backup-painel");

  btn.addEventListener("click", () => {
    const aberto = btn.getAttribute("aria-expanded") === "true";
    if (aberto) {
      btn.setAttribute("aria-expanded", "false");
      btn.classList.remove("ativo");
      painel.hidden = true;
      return;
    }
    btn.setAttribute("aria-expanded", "true");
    btn.classList.add("ativo");
    painel.hidden = false;
  });
}
