// static/js/secoes/topo/cabecalho.js - Secao topo > cabecalho (HTML: templates/secoes/topo/cabecalho.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 2407-2412, app.js 3938-3982, app.js 4111-4284.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadUso() {
  const data = await apiFetch("/api/uso/total");
  // Fase 9 (P-topo): #uso-custo saiu do cabecalho - o custo de IA ja aparece,
  // mais completo (grafico, tabela por funcao, projecao), dentro da folha de
  // Configuracoes (templates/secoes/painel/custo-ia.html). Varias outras
  // faixas ainda chamam loadUso() pra atualizar aquele texto (captura.js,
  // chat.js, gastos.js, plano-do-dia.js, nucleo/init.js) - guarda contra
  // elemento ausente em vez de editar cada chamador.
  const el = $("#uso-custo");
  if (!data || !el) return;
  el.textContent = `gasto com IA ate agora: ${fmtUSD(data.custo_usd)}`;
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

  (async () => {
    const dados = await apiFetch("/api/modo-visitante");
    if (dados) aplicarEstado(Boolean(dados.ativo));
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

// ---- Fase 9 (P-topo): popover do hiperfoco no cabecalho -------------------
// #hiperfoco-box (mesmo miolo/ids/handlers de static/js/secoes/hoje/hiperfoco.js,
// so mudou de lugar - antes sempre visivel do lado do campo de captura, agora um
// popover fechado por padrao, aberto pelo botao-relogio #hiperfoco-toggle-btn).
function initHiperfocoPopover() {
  const btn = $("#hiperfoco-toggle-btn");
  const box = $("#hiperfoco-box");
  if (!btn || !box) return;

  function fechar() {
    if (box.hidden) return;
    box.hidden = true;
    btn.setAttribute("aria-expanded", "false");
  }

  function abrir() {
    box.hidden = false;
    btn.setAttribute("aria-expanded", "true");
  }

  btn.addEventListener("click", (ev) => {
    ev.stopPropagation();
    if (box.hidden) abrir();
    else fechar();
  });

  // Clique fora fecha (fora do botao e fora do proprio popover).
  document.addEventListener("click", (ev) => {
    if (box.hidden) return;
    if (box.contains(ev.target) || ev.target === btn) return;
    fechar();
  });

  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && !box.hidden) {
      fechar();
      btn.focus();
    }
  });

  // Escolher uma duracao ou encerrar o hiperfoco fecha o popover sozinho -
  // os handlers de verdade (POST/DELETE /api/hiperfoco) continuam intactos em
  // hiperfoco.js, este listener so reage ao mesmo clique pra fechar a caixa.
  box.addEventListener("click", (ev) => {
    if (ev.target.closest(".hiperfoco-btn, #hiperfoco-parar")) {
      setTimeout(fechar, 150);
    }
  });
}

// ---- Fase 9 (P-topo): aviso critico no topo (global, todas as abas) -------
// Mesma fonte de dado que o cartao de aviso da conversa do Hoje
// (GET /api/sobrecarga, ja consumido por static/js/secoes/hoje/conversa.js) -
// aqui so controla um ponto discreto ancorado no botao de comando de voz,
// visivel em qualquer aba (o topo e global, nao so na Hoje). Nao reimplementa
// nenhum calculo de sobrecarga, so le o mesmo campo `sobrecarregado`.
async function atualizarAvisoCriticoTopo() {
  const el = $("#topo-aviso-critico");
  if (!el) return;
  const dados = await apiFetch("/api/sobrecarga");
  el.hidden = !(dados && dados.sobrecarregado);
}

function initAvisoCriticoTopo() {
  if (!$("#topo-aviso-critico")) return;
  atualizarAvisoCriticoTopo();
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") atualizarAvisoCriticoTopo();
  });
  setInterval(atualizarAvisoCriticoTopo, 5 * 60 * 1000);
}

// ---- Fase 9 (P-topo): atalho do relogio pra "visao do dia" (so aba Hoje) --
// O botao so aparece na aba Hoje (CSS em secoes/topo.css, casado com o
// [hidden] que showTab() ja alterna em #tab-hoje) - aqui so abre a secao
// (mesmo contrato de static/js/ui/secao-recolhivel.js: clica no cabecalho de
// verdade em vez de chamar a API interna direto) e rola ate ela.
function initAtalhoVisaoDia() {
  const btn = $("#btn-visao-dia");
  if (!btn) return;
  btn.addEventListener("click", () => {
    const secao = document.querySelector('[data-secao-id="visao-dia-hoje"]');
    if (!secao) return;
    const cabecalhoSecao = secao.querySelector(".secao-cabecalho");
    if (secao.dataset.aberto !== "true" && cabecalhoSecao) cabecalhoSecao.click();
    secao.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

initHiperfocoPopover();
initAvisoCriticoTopo();
initAtalhoVisaoDia();
