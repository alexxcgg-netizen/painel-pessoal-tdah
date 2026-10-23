// static/js/secoes/topo/cabecalho.js - Secao topo > cabecalho (HTML: templates/secoes/topo/cabecalho.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 2407-2412, app.js 3938-3982, app.js 4111-4284.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadUso() {
  const data = await apiFetch("/api/uso/total");
  if (!data) return;
  $("#uso-custo").textContent = `gasto com IA até agora: ${fmtUSD(data.custo_usd)}`;
}

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)));
}

// Notificacoes (reescrito 2026-10-10): a linha fica SEMPRE visivel em Mais › Configurações
// e diz o que falta quando nao da pra ativar - antes ela sumia em silencio (iPhone so libera
// push pra app instalado na Tela de Início; tela aberta antes das chaves existirem).
function _pushIos() {
  return /iphone|ipad|ipod/i.test(navigator.userAgent || "");
}

function _pushInstalado() {
  return window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
}

function _pushEstado(btn, estado, sub, ligado) {
  $("#push-estado").textContent = estado;
  $("#push-sub").textContent = sub;
  btn.classList.toggle("ativo", !!ligado);
}

async function _pushRegistro() {
  // ready nunca resolve se o service worker nao registrou - nao deixa a tela esperando pra sempre
  return Promise.race([navigator.serviceWorker.ready, new Promise((r) => setTimeout(() => r(null), 6000))]);
}

async function initPush() {
  const btn = $("#push-btn");
  if (!btn) return;
  let acao = null; // o que o toque faz no estado atual
  btn.addEventListener("click", () => acao && acao());

  const semSuporte = !("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window);
  if (semSuporte) {
    const msg = _pushIos() && !_pushInstalado()
      ? "No iPhone: Compartilhar › Adicionar à Tela de Início e abrir pelo ícone"
      : "Este navegador não recebe notificações";
    _pushEstado(btn, "Indisponível", msg, false);
    acao = () => mostrarErro(msg + ".");
    return;
  }

  const status = await apiFetch("/api/push/status");
  if (!status || !status.configurado) {
    _pushEstado(btn, "Desligado", "Falta configurar as chaves no servidor", false);
    acao = () => mostrarErro("As notificações ainda não foram configuradas no servidor do painel.");
    return;
  }
  if (Notification.permission === "denied") {
    _pushEstado(btn, "Bloqueado", "Libere em Ajustes › Notificações › Painel", false);
    acao = () => mostrarErro("As notificações estão bloqueadas. Libere em Ajustes › Notificações › Painel.");
    return;
  }

  const reg = await _pushRegistro();
  if (!reg) {
    _pushEstado(btn, "Indisponível", "Feche e abra o app de novo", false);
    acao = () => location.reload();
    return;
  }

  // inscrito no iPhone nao basta: quem dispara os avisos e o agendador do servidor
  // (bug real: ficou desligado sem ninguem ver). Mostra quando ele nao esta rodando.
  const agendadorParado = status.agendador && status.agendador.ligado === false;
  const prontoParaTeste = () => {
    if (agendadorParado) {
      _pushEstado(btn, "Parado", "O servidor não está mandando avisos - reinicie o painel", false);
      acao = () => mostrarErro("O iPhone está pronto, mas o agendador do servidor está parado. Reinicie o painel no computador.");
      return;
    }
    // teste com botoes (leva 22/10): o que ele tocou no ultimo aviso de teste diz se o iPhone mostra
    // "Feito / Adiar" no proprio aviso (sem botao, o toque abre a tarefa com concluir / pra amanha)
    const t = status.teste_botoes;
    const resultado = !t ? "" : t.acao === "toque" ? " · último teste: sem botão no aviso" : " · último teste: botões funcionam";
    _pushEstado(btn, "Ligado", `Avisos chegando sozinhos${resultado} · toque pra um teste`, true);
    acao = async () => {
      const r = await apiFetch("/api/push/testar", { method: "POST" });
      if (r) _pushEstado(btn, "Ligado", r.enviados ? "Teste enviado: segura o aviso e toca em Feito" : "Toque pra receber um teste", true);
    };
  };

  const existente = await reg.pushManager.getSubscription();
  if (existente) {
    // garante que o servidor conhece essa inscricao (ex: depois de trocar as chaves)
    apiFetch("/api/push/inscrever", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(existente.toJSON()),
    });
    prontoParaTeste();
    return;
  }

  _pushEstado(btn, "Desligado", "Toque pra receber lembretes, chuva, contas e voos", false);
  acao = async () => {
    // a permissao tem que ser pedida DENTRO do toque (iPhone)
    const permissao = await Notification.requestPermission();
    if (permissao !== "granted") {
      _pushEstado(btn, "Bloqueado", "Libere em Ajustes › Notificações › Painel", false);
      return;
    }
    _pushEstado(btn, "Ativando…", "Um instante", false);
    try {
      const assinatura = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(status.public_key),
      });
      const ok = await apiFetch("/api/push/inscrever", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(assinatura.toJSON()),
      });
      if (!ok) throw new Error("servidor recusou");
      prontoParaTeste();
    } catch (e) {
      _pushEstado(btn, "Desligado", "Não deu pra ativar - toque pra tentar de novo", false);
      mostrarErro("Não consegui ativar as notificações agora. Tenta de novo.");
    }
  };
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
    status.textContent = `Salvo: das ${dados.inicio} até ${dados.fim}.`;
  });
}

let modoVisitanteAtivo = false;

function initModoVisitante() {
  const btn = $("#modo-visitante-btn");
  const painel = $("#modo-visitante-painel");
  const pinInput = $("#modo-visitante-pin");
  const status = $("#modo-visitante-status");

  // 2026-10-12: ligado, o modo visitante aparece em TODA tela (selo no topo) e desliga sozinho em
  // 1 h (servidor). Antes so dava pra ver em Mais > Configuracoes - o Alex ligou sem querer e passou
  // 2 dias com o chat dizendo "modo visitante, nao posso mexer".
  let timerFim = null;
  function selo(ativo, minutos) {
    let el = document.getElementById("selo-visitante");
    clearTimeout(timerFim);
    if (!ativo) {
      if (el) {
        el.classList.add("saindo");
        setTimeout(() => el.remove(), 260);
      }
      return;
    }
    if (!el) {
      el = document.createElement("button");
      el.type = "button";
      el.id = "selo-visitante";
      el.innerHTML =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>' +
        '<span>Modo visitante</span><span class="selo-visitante-sair">Sair</span>';
      el.setAttribute("aria-label", "Modo visitante ligado. Toque pra sair com o PIN");
      el.addEventListener("click", () => {
        showTab("config");
        painel.hidden = false;
        setTimeout(() => {
          painel.scrollIntoView({ behavior: "smooth", block: "center" });
          pinInput.focus({ preventScroll: true });
        }, 320);
      });
      document.body.appendChild(el);
    }
    if (minutos) {
      timerFim = setTimeout(async () => {
        const dados = await apiFetch("/api/modo-visitante");
        if (dados && !dados.ativo) aplicarEstado(false);
        else if (dados) selo(true, dados.minutos_restantes);
      }, minutos * 60 * 1000 + 1500);
    }
  }

  function aplicarEstado(ativo, minutos) {
    modoVisitanteAtivo = ativo;
    selo(ativo, minutos);
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
      aplicarEstado(true, dados.minutos_restantes);
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
      if (dados) aplicarEstado(true, dados.minutos_restantes);
      return;
    }
    painel.hidden = !painel.hidden;
  });

  // voltou pro app depois de um tempo: o servidor pode ja ter desligado sozinho
  document.addEventListener("visibilitychange", async () => {
    if (document.hidden || !modoVisitanteAtivo) return;
    const dados = await apiFetch("/api/modo-visitante");
    if (dados && !dados.ativo) aplicarEstado(false);
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

// Widget do iPhone (2026-10-13): ao abrir, busca o script do Scriptable + token
// (/api/widget/instalacao, so com PIN) e deixa os dois botoes de copiar prontos. O texto ja fica
// em memoria ANTES do toque - o iPhone so deixa escrever na area de transferencia dentro do
// proprio toque, sem esperar rede no meio.
function initWidgetIphone() {
  const btn = $("#widget-btn");
  const painel = $("#widget-painel");
  if (!btn || !painel) return;
  const btnScript = $("#widget-copiar-script");
  const btnAjuste = $("#widget-copiar-ajuste");
  const status = $("#widget-status");
  let script = "";
  let ajuste = "";

  async function carregar() {
    status.textContent = "Carregando…";
    const dados = await apiFetch("/api/widget/instalacao");
    if (!dados) {
      status.textContent = "";
      return;
    }
    script = dados.script || "";
    ajuste = dados.token ? `${location.origin}|${dados.token}` : "";
    // o script ja vai com endereco e chave preenchidos: a previa dentro do Scriptable mostra os
    // dados de verdade e o campo Parameter do widget vira opcional
    if (dados.token) {
      script = script
        .replace('const PAINEL_URL = "http://SEU-IP-OU-DOMINIO:5001";', `const PAINEL_URL = ${JSON.stringify(location.origin)};`)
        .replace('const TOKEN = "";', `const TOKEN = ${JSON.stringify(dados.token)};`);
    }
    btnScript.disabled = !script;
    btnAjuste.disabled = !ajuste;
    status.textContent = dados.configurado
      ? ""
      : "Falta criar a chave do widget (PAINEL_WIDGET_TOKEN no .env do PC) - sem ela o widget não consegue ler o painel.";
  }

  async function copiar(texto, botao, rotulo) {
    try {
      await navigator.clipboard.writeText(texto);
      status.textContent = `${rotulo} copiado.`;
      botao.classList.add("ativo");
      setTimeout(() => botao.classList.remove("ativo"), 1200);
    } catch {
      status.textContent = "Não consegui copiar - tenta de novo.";
    }
  }

  btnScript.addEventListener("click", () => script && copiar(script, btnScript, "Script"));
  btnAjuste.addEventListener("click", () => ajuste && copiar(ajuste, btnAjuste, "Ajuste"));
  btn.addEventListener("click", () => {
    const aberto = btn.getAttribute("aria-expanded") === "true";
    btn.setAttribute("aria-expanded", String(!aberto));
    btn.classList.toggle("ativo", !aberto);
    painel.hidden = aberto;
    if (!aberto && !script) carregar();
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
