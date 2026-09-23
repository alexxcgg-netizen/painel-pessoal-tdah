// Visao do dia (Fase 6, Grupo E5 - US-E9): aba Hoje, abaixo do chat. Seletor
// Dia/Semana/Mes, linha de status, card "Em foco agora" (liga no hiperfoco
// que ja existe, ver static/js/vida.js) e a linha do tempo do dia - que
// REUSA a mesma marcacao visual (.linha-do-tempo, criarItemLinhaDoTempo em
// app.js) que a agenda de hoje (aba Painel) ja tinha, em vez de duplicar.
//
// Estrutura dupla de export igual voz-comando.js/fila-offline.js: em
// navegador vira o global `VisaoDia` (script classico); em Node (testes, sem
// DOM) so a logica PURA fica acessivel via module.exports.
const VisaoDia = (function () {
  // ---- logica pura (sem DOM/fetch - testavel isolado) ----------------------

  const DIAS_SEMANA_CURTO = ["dom", "seg", "ter", "qua", "qui", "sex", "sab"];

  // "Hoje"/"Amanha"/"Ontem" pros dias vizinhos, "seg 23" pro resto - usado na
  // lista agregada de Semana/Mes.
  function nomeDiaCurto(dataISO, hojeISO) {
    if (dataISO === hojeISO) return "Hoje";
    const d = new Date(`${dataISO}T00:00:00`);
    const h = new Date(`${hojeISO}T00:00:00`);
    const diffDias = Math.round((d - h) / 86400000);
    if (diffDias === 1) return "Amanha";
    if (diffDias === -1) return "Ontem";
    const diaSemana = DIAS_SEMANA_CURTO[d.getDay()];
    const diaMes = String(d.getDate()).padStart(2, "0");
    return `${diaSemana} ${diaMes}`;
  }

  // "Hoje · 6 itens · 3 concluidas" (AC literal da US-E9, com singular/plural
  // certo pros dois numeros independentemente um do outro).
  function textoResumoDia(totalItens, totalConcluidas) {
    const itens = totalItens === 1 ? "item" : "itens";
    const concluidas = totalConcluidas === 1 ? "concluida" : "concluidas";
    return `Hoje · ${totalItens} ${itens} · ${totalConcluidas} ${concluidas}`;
  }

  return { nomeDiaCurto, textoResumoDia };
})();

if (typeof module !== "undefined" && module.exports) {
  // Node (testes) - so a logica pura, sem DOM/fetch.
  module.exports = {
    nomeDiaCurto: VisaoDia.nomeDiaCurto,
    textoResumoDia: VisaoDia.textoResumoDia,
  };
}

// ---- wiring de navegador (DOM/fetch - so roda com pagina real) ------------
if (typeof document !== "undefined" && typeof window !== "undefined") {
  (function () {
    const seletor = document.querySelectorAll(".visao-dia-periodo-btn");
    const boxDia = document.getElementById("visao-dia-periodo-dia");
    const boxPeriodo = document.getElementById("visao-dia-periodo-agregado");
    if (!seletor.length || !boxDia || !boxPeriodo) return; // pagina sem essa UI (ex: teste isolado) - nao quebra nada

    const statusEl = document.getElementById("visao-dia-status");
    const focoBox = document.getElementById("visao-dia-foco");
    const focoVazio = document.getElementById("visao-dia-foco-vazio");
    const focoTitulo = document.getElementById("visao-dia-foco-titulo");
    const focoEm = document.getElementById("visao-dia-foco-em");
    const focoHiperfocoBtn = document.getElementById("visao-dia-foco-hiperfoco");
    const focoConcluirBtn = document.getElementById("visao-dia-foco-concluir");
    const resumoEl = document.getElementById("visao-dia-resumo");
    const timelineEl = document.getElementById("visao-dia-timeline");
    const vazioEl = document.getElementById("visao-dia-vazio");
    const periodoListaEl = document.getElementById("visao-dia-periodo-lista");

    // Duracao padrao do hiperfoco disparado pelo card (a mais curta das 3
    // opcoes ja existentes em #hiperfoco-box - o menos disruptivo por
    // padrao; o Alex ainda pode ajustar/encerrar pela aba Vida como sempre).
    const MINUTOS_FOCO_PADRAO = 25;

    let emFocoAtual = null;

    function renderEmFoco(emFoco) {
      emFocoAtual = emFoco;
      focoBox.hidden = !emFoco;
      focoVazio.hidden = Boolean(emFoco);
      if (!emFoco) return;
      focoTitulo.textContent = emFoco.titulo;
      focoEm.textContent = emFoco.em_texto;
    }

    async function loadVisaoDiaHoje() {
      const data = await window.apiFetch("/api/visao-dia/hoje");
      if (!data) return;

      statusEl.classList.remove("shimmer");
      statusEl.textContent = data.status;
      renderEmFoco(data.em_foco);
      resumoEl.textContent = VisaoDia.textoResumoDia(data.total_itens, data.total_concluidas);

      timelineEl.innerHTML = "";
      vazioEl.hidden = data.timeline.length > 0;
      const agora = new Date();
      let proximoMarcado = false;
      data.timeline.forEach((ev) => {
        const { li, marcouProximo } = criarItemLinhaDoTempo(ev, agora, proximoMarcado);
        if (marcouProximo) proximoMarcado = true;
        timelineEl.appendChild(li);
      });
    }

    async function loadVisaoDiaPeriodo(tipo) {
      const data = await window.apiFetch(`/api/visao-dia/periodo?tipo=${tipo}`);
      if (!data) return;
      const hojeISO = new Date().toISOString().slice(0, 10);
      periodoListaEl.innerHTML = "";
      data.dias.forEach((dia) => {
        const li = document.createElement("li");
        if (dia.data === hojeISO) li.classList.add("visao-dia-periodo-dia-hoje");
        const nome = document.createElement("span");
        nome.className = "visao-dia-periodo-dia-nome";
        nome.textContent = VisaoDia.nomeDiaCurto(dia.data, hojeISO);
        const contagem = document.createElement("span");
        contagem.className = "visao-dia-periodo-contagem";
        contagem.textContent = `${dia.concluidas}/${dia.total}`;
        li.appendChild(nome);
        li.appendChild(contagem);
        periodoListaEl.appendChild(li);
      });
    }

    seletor.forEach((btn) => {
      btn.addEventListener("click", () => {
        if (btn.classList.contains("active")) return;
        seletor.forEach((b) => {
          b.classList.remove("active");
          b.setAttribute("aria-selected", "false");
        });
        btn.classList.add("active");
        btn.setAttribute("aria-selected", "true");
        const periodo = btn.dataset.periodo;
        if (periodo === "dia") {
          boxDia.hidden = false;
          boxPeriodo.hidden = true;
          loadVisaoDiaHoje();
        } else {
          boxDia.hidden = true;
          boxPeriodo.hidden = false;
          loadVisaoDiaPeriodo(periodo);
        }
      });
    });

    focoHiperfocoBtn.addEventListener("click", async () => {
      const estado = await window.apiFetch("/api/hiperfoco", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ minutos: MINUTOS_FOCO_PADRAO }),
      });
      // renderHiperfoco (static/js/vida.js) ja cuida do card de hiperfoco da
      // aba Hoje - reusado aqui em vez de duplicar o estado/contagem.
      if (estado && typeof renderHiperfoco === "function") renderHiperfoco(estado);
    });

    focoConcluirBtn.addEventListener("click", async () => {
      if (!emFocoAtual || !emFocoAtual.id) return;
      const rota =
        emFocoAtual.origem === "habito"
          ? `/api/habitos/${emFocoAtual.id}/marcar`
          : `/api/tasks/${emFocoAtual.id}/complete`;
      const r = await window.apiFetch(rota, { method: "POST" });
      if (r) loadVisaoDiaHoje();
    });

    // Carga inicial + recarga ao voltar pra aba Hoje (mesmo padrao de
    // loadVidaHoje em vida.js - listener PROPRIO aqui, sem depender de
    // vida.js carregar antes/depois) - recarrega so o periodo que estiver
    // ativo no momento (Dia por padrao).
    function carregarPeriodoAtivo() {
      const ativo = document.querySelector(".visao-dia-periodo-btn.active");
      const periodo = ativo ? ativo.dataset.periodo : "dia";
      if (periodo === "dia") loadVisaoDiaHoje();
      else loadVisaoDiaPeriodo(periodo);
    }

    document.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (btn.dataset.tab === "hoje") carregarPeriodoAtivo();
      });
    });

    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") carregarPeriodoAtivo();
    });

    window.loadVisaoDiaHoje = loadVisaoDiaHoje;
    loadVisaoDiaHoje();
  })();
}
