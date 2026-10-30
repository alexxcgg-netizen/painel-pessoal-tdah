// static/js/cards-foco-ideias.js - cards do Grupo A (Foco) do Laboratorio v4 (30/10/2026), iguais as demos aprovadas
// (docs/prototipos/laboratorio-v4/demos/20-foco.js, 70-vida-fone.js, 90-bonus.js):
//   e_agora (E agora?), travou (Por que travou?), pacote (Pacote de tentacao), segundo_antes (Um segundo antes),
//   recomeco (Recomeco). Logica no servidor (foco_ideias.py / recomeco.py); aqui so a cara e os toques.
// Renderizadores PUROS (estado inicial); cliques trocam so o pedaco que mudou. Script classico - ordem de carga em
// templates/scripts.html (depois de cards-dia.js).

(function (raiz) {
  "use strict";

  const Cards = raiz.Cards;
  if (!Cards) return;
  const esc = Cards.esc;
  const reduz = () => typeof raiz.matchMedia === "function" && raiz.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const lista = (v) => (Array.isArray(v) ? v : []);
  const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;

  const ICONE = {
    alvo: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r=".8"/>',
    check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    elo: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    pedra: '<path d="M4 18.5 8 9l4 3.5L15 6l5 12.5z"/>',
    pausa: '<circle cx="12" cy="12" r="8.5"/><path d="M10 9v6M14 9v6"/>',
    caixa: '<rect x="3.5" y="4.5" width="17" height="5" rx="1.5"/><path d="M5 9.5V18a1.5 1.5 0 0 0 1.5 1.5h11A1.5 1.5 0 0 0 19 18V9.5M10 13.5h4"/>',
    volta: '<path d="M4.5 12a7.5 7.5 0 1 0 2.2-5.3"/><path d="M4.5 4.5v4h4"/>',
  };
  const svg = (nome, larg) =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${larg || 2}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONE[nome] || ""}</svg>`;
  const topo = (ic, nome, quando) =>
    `<div class="cd-topo"><span class="cd-selo">${svg(ic)}${esc(nome)}</span>${quando ? `<span class="cd-quando">${esc(quando)}</span>` : ""}</div>`;
  const oculto = (ic, nome) => topo(ic, nome, "") + `<p class="cd-nota">Oculto no modo visitante.</p>`;

  async function postar(deps, url, corpo) {
    if (typeof deps.apiFetch !== "function") return null;
    try {
      return await deps.apiFetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(corpo || {}),
      });
    } catch (e) {
      return null;
    }
  }
  const lerEstado = (el) => {
    try {
      return JSON.parse(el.dataset.estado || "{}");
    } catch (e) {
      return {};
    }
  };
  const volta = (b) => b.classList.remove("cd-enviando");

  // pedaco que sai (sobe e some) e o novo que entra - mesma "assentada" das demos; sem movimento, troca seca
  function trocar(pai, htmlNovo, aoEntrar) {
    const velho = pai.firstElementChild;
    const t = document.createElement("div");
    t.innerHTML = htmlNovo;
    const novo = t.firstElementChild;
    if (!novo) return null;
    if (velho && !reduz()) {
      velho.classList.add("fi-vai");
      setTimeout(() => velho.remove(), 300);
    } else if (velho) {
      velho.remove();
    }
    pai.appendChild(novo);
    if (aoEntrar) aoEntrar(novo);
    return novo;
  }

  // avisinho no pe da tela (premio liberado etc.); tarefas.js tambem chama mostrarPremioLiberado
  let timerToast = null;
  function toastFoco(msg) {
    if (typeof document === "undefined") return;
    let el = document.getElementById("fi-toast");
    if (!el) {
      el = document.createElement("div");
      el.id = "fi-toast";
      el.className = "fi-toast";
      el.setAttribute("role", "status");
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.classList.remove("on");
    void el.offsetWidth;
    el.classList.add("on");
    clearTimeout(timerToast);
    timerToast = setTimeout(() => el.classList.remove("on"), 3200);
  }
  raiz.mostrarPremioLiberado = (premio) => toastFoco(`${premio} liberado. Aproveita.`);

  // ================================================================ e_agora
  function sugestaoHtml(s, vem) {
    const dur = Number(s.min) || 0;
    return (
      `<div class="ea-sug${vem ? " vem" : ""}"><p class="cd-rot">Faz isto</p><p class="cd-hero">${esc(s.titulo)}</p>` +
      `<p class="cd-nota ea-meta">${dur ? `<span class="ea-dur">${dur} min</span> · ` : ""}${esc(s.porque || "")}` +
      `${s.premio ? ` <span class="ea-premio">Prêmio: ${esc(s.premio)}</span>` : ""}</p></div>`
    );
  }
  function peAgora(n) {
    return (
      `<div class="cd-acoes ea-pe">` +
      (n > 1 ? `<button type="button" class="cd-acao" data-acao="ea_outra">Outra</button>` : "") +
      `<button type="button" class="cd-acao primaria cd-aqui" data-acao="ea_bora">Bora</button></div>`
    );
  }
  Cards.registrar("e_agora", (data) => {
    const d = data || {};
    if (d.oculto) return oculto("alvo", "Agora");
    const sug = lista(d.sugestoes);
    const quando = [d.quando, d.livre_min ? `${d.livre_min} min livres` : ""].filter(Boolean).join(" · ");
    if (!sug.length)
      return topo("alvo", "Agora", quando) + `<p class="cd-hero">Nada pendente. Respira.</p><p class="cd-nota">Quando aparecer tarefa, é só tocar de novo.</p>`;
    return (
      topo("alvo", "Agora", quando) +
      `<div class="cd-raiz ea-raiz" data-estado="${esc(JSON.stringify({ sugestoes: sug, i: 0 }))}">` +
      `<div class="ea-vazio"><button type="button" class="ea-botao" data-acao="ea_revelar">E agora?</button>` +
      `<p class="cd-nota">Toca e eu escolho por ti.</p></div></div>`
    );
  }
  );
  Cards.registrarAcao("ea_revelar", (btn, cardEl) => {
    const r = cardEl.querySelector(".ea-raiz");
    if (!r) return;
    const est = lerEstado(r);
    const vazio = r.querySelector(".ea-vazio");
    if (vazio) vazio.classList.add("some");
    setTimeout(
      () => {
        r.innerHTML = `<div class="ea-palco">${sugestaoHtml(lista(est.sugestoes)[0], false)}</div>` + peAgora(lista(est.sugestoes).length);
      },
      reduz() ? 0 : 300
    );
  });
  Cards.registrarAcao("ea_outra", (btn, cardEl) => {
    const r = cardEl.querySelector(".ea-raiz");
    const palco = r && r.querySelector(".ea-palco");
    if (!palco) return;
    const est = lerEstado(r);
    const sug = lista(est.sugestoes);
    est.i = ((Number(est.i) || 0) + 1) % sug.length;
    r.dataset.estado = JSON.stringify(est);
    trocar(palco, sugestaoHtml(sug[est.i], true));
  });
  Cards.registrarAcao("ea_bora", async (btn, cardEl, deps) => {
    const r = cardEl.querySelector(".ea-raiz");
    if (!r) return;
    const est = lerEstado(r);
    const s = lista(est.sugestoes)[Number(est.i) || 0];
    if (!s) return;
    btn.classList.add("cd-enviando");
    const res = await postar(deps, "/api/e-agora/bora", { task_id: s.id });
    if (!res || !res.ok) return volta(btn);
    const pe = r.querySelector(".ea-pe");
    if (pe) pe.outerHTML = `<span class="ea-fazendo">${svg("check", 2.4)}Fazendo agora · cronômetro ligado</span>`;
    toastFoco("Bora. Te chamo quando acabar o tempo.");
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  });

  // ================================================================ travou (Por que travou?)
  const MOTIVOS = [
    ["chato", "É chato"],
    ["dificil", "É difícil"],
    ["medo", "Dá medo/vergonha"],
    ["sem_rumo", "Não sei por onde"],
  ];
  Cards.registrar("travou", (data) => {
    const d = data || {};
    if (d.oculto) return oculto("pedra", "Tarefa travada");
    const n = Number(d.adiadas) || 3;
    const chips = MOTIVOS.map(
      ([k, rot]) => `<button type="button" class="fi-chip" data-acao="tv_motivo" data-m="${k}" aria-pressed="${d.motivo === k ? "true" : "false"}">${esc(rot)}</button>`
    ).join("");
    return (
      topo("pedra", "Tarefa travada", `adiada ${n}x`) +
      `<div class="cd-raiz tv-raiz" data-estado="${esc(JSON.stringify({ task_id: d.task_id }))}">` +
      `<p class="cd-hero">${esc(d.titulo || "")}</p>` +
      `<p class="cd-nota tv-pergunta">Tu já empurrou essa ${n} vezes. O que pega?</p>` +
      `<div class="fi-chips">${chips}</div><div class="pq-res"></div></div>`
    );
  });
  function remedioHtml(r) {
    let corpo = "";
    if (r.roteiro && r.roteiro.length) corpo += `<ol class="pq-rot">${r.roteiro.map((x) => `<li>${esc(x)}</li>`).join("")}</ol>`;
    if (r.texto) corpo += `<p>${esc(r.texto)}</p>`;
    if (r.passos && r.passos.length) corpo += `<ul class="pq-passos">${r.passos.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
    let extra = "";
    if (r.acao === "juntar") {
      extra =
        `<div class="fi-chips">${lista(r.premios).map((p) => `<button type="button" class="fi-chip" data-acao="tv_premio" aria-pressed="false">${esc(p)}</button>`).join("")}</div>` +
        `<input class="fi-campo" type="text" maxlength="60" placeholder="Outro prêmio" aria-label="Outro prêmio" data-campo="premio">`;
    }
    return (
      `<div class="pq-caixa"><p class="cd-rot">${esc(r.titulo || "")}</p>${corpo}${extra}` +
      `<button type="button" class="cd-acao primaria" data-acao="tv_aplicar" data-a="${esc(r.acao)}"${r.acao === "juntar" ? " disabled" : ""}>${esc(r.botao || "Ok")}</button></div>`
    );
  }
  Cards.registrarAcao("tv_motivo", async (btn, cardEl, deps) => {
    const r = cardEl.querySelector(".tv-raiz");
    if (!r) return;
    const est = lerEstado(r);
    cardEl.querySelectorAll(".tv-raiz > .fi-chips .fi-chip").forEach((c) => c.setAttribute("aria-pressed", "false"));
    btn.setAttribute("aria-pressed", "true");
    const res = await postar(deps, "/api/travou/responder", { task_id: est.task_id, motivo: btn.dataset.m });
    const palco = r.querySelector(".pq-res");
    if (!res || !res.remedio) return btn.setAttribute("aria-pressed", "false");
    trocar(palco, remedioHtml(res.remedio));
  });
  Cards.registrarAcao("tv_premio", (btn, cardEl) => {
    const caixa = btn.closest(".pq-caixa");
    caixa.querySelectorAll(".fi-chip").forEach((c) => c.setAttribute("aria-pressed", "false"));
    btn.setAttribute("aria-pressed", "true");
    const campo = caixa.querySelector(".fi-campo");
    if (campo) campo.value = "";
    const ok = caixa.querySelector('[data-acao="tv_aplicar"]');
    if (ok) ok.disabled = false;
  });
  Cards.registrarAcao("tv_aplicar", async (btn, cardEl, deps) => {
    const r = cardEl.querySelector(".tv-raiz");
    if (!r) return;
    const est = lerEstado(r);
    const caixa = btn.closest(".pq-caixa");
    const acao = btn.dataset.a;
    let premio = "";
    if (acao === "juntar") {
      const sel = caixa.querySelector(".fi-chip[aria-pressed='true']");
      const campo = caixa.querySelector(".fi-campo");
      premio = ((campo && campo.value.trim()) || (sel && sel.textContent) || "").trim();
      if (!premio) return;
    }
    btn.classList.add("cd-enviando");
    const res = await postar(deps, "/api/travou/aplicar", { task_id: est.task_id, acao, premio });
    if (!res || !res.ok) return volta(btn);
    btn.disabled = true;
    volta(btn);
    btn.textContent = "Feito";
    toastFoco(
      acao === "juntar" ? `Feito. ${res.premio} só vale junto com essa tarefa.` :
      acao === "passos" ? `${plural(res.passos || 0, "passo adicionado", "passos adicionados")} na tarefa.` : "Foco ligado. Bora."
    );
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  });
  // digitou um premio proprio: solta o chip e libera o botao
  if (typeof document !== "undefined") {
    document.addEventListener("input", (e) => {
      const campo = e.target && e.target.matches && e.target.matches(".fi-campo") ? e.target : null;
      if (!campo) return;
      const caixa = campo.closest(".pq-caixa, .pc-raiz");
      if (!caixa) return;
      if (campo.value.trim()) caixa.querySelectorAll(".fi-chip[data-acao='tv_premio'], .fi-chip[data-g='b']").forEach((c) => c.setAttribute("aria-pressed", "false"));
      const ok = caixa.querySelector('[data-acao="tv_aplicar"], [data-acao="pc_juntar"]');
      if (ok && ok.dataset.acao === "tv_aplicar") ok.disabled = !campo.value.trim() && !caixa.querySelector(".fi-chip[aria-pressed='true']");
      if (ok && ok.dataset.acao === "pc_juntar") atualizarJunta(caixa);
    });
  }

  // ================================================================ pacote
  function itemPacote(t, premio) {
    return (
      `<li class="pt-item" data-id="${esc(t.id)}" data-premio="${esc(premio)}">` +
      `<button type="button" class="pa-cx" data-acao="pc_marcar" aria-pressed="false" aria-label="Marcar como feita: ${esc(t.titulo)}">${svg("check", 3)}</button>` +
      `<span class="pa-txt">${esc(t.titulo)}<small>prêmio: ${esc(String(premio).toLowerCase())}</small></span></li>`
    );
  }
  Cards.registrar("pacote", (data) => {
    const d = data || {};
    if (d.oculto) return oculto("elo", "Juntar");
    const chatas = lista(d.chatas);
    const ativos = lista(d.ativos);
    const chipsA = chatas.length
      ? chatas.map((t) => `<button type="button" class="fi-chip" data-acao="pc_escolher" data-g="a" data-id="${esc(t.id)}" aria-pressed="false">${esc(t.titulo)}</button>`).join("")
      : `<p class="cd-nota">Nenhuma tarefa aberta sem pacote.</p>`;
    const chipsB = lista(d.premios)
      .map((p) => `<button type="button" class="fi-chip" data-acao="pc_escolher" data-g="b" aria-pressed="false">${esc(p)}</button>`)
      .join("");
    return (
      topo("elo", "Juntar", ativos.length ? plural(ativos.length, "pacote", "pacotes") : "") +
      `<div class="cd-raiz pc-raiz"><p class="cd-rot">A tarefa chata</p><div class="fi-chips">${chipsA}</div>` +
      `<p class="cd-rot">Só pode junto com</p><div class="fi-chips">${chipsB}</div>` +
      `<input class="fi-campo" type="text" maxlength="60" placeholder="Outro prêmio" aria-label="Outro prêmio" data-campo="premio">` +
      `<button type="button" class="cd-acao primaria" data-acao="pc_juntar" disabled>Juntar os dois</button>` +
      `<div class="pt-res"></div>` +
      (ativos.length ? `<p class="cd-rot">No ar agora</p><ul class="pa-lista pt-lista">${ativos.map((t) => itemPacote(t, t.premio)).join("")}</ul>` : `<ul class="pa-lista pt-lista" hidden></ul>`) +
      `</div>`
    );
  });
  const premioEscolhido = (caixa) => {
    const campo = caixa.querySelector(".fi-campo");
    const sel = caixa.querySelector(".fi-chip[data-g='b'][aria-pressed='true']");
    return ((campo && campo.value.trim()) || (sel && sel.textContent) || "").trim();
  };
  function atualizarJunta(caixa) {
    const a = caixa.querySelector(".fi-chip[data-g='a'][aria-pressed='true']");
    const ok = caixa.querySelector('[data-acao="pc_juntar"]');
    if (ok) ok.disabled = !(a && premioEscolhido(caixa));
  }
  Cards.registrarAcao("pc_escolher", (btn, cardEl) => {
    const caixa = btn.closest(".pc-raiz");
    caixa.querySelectorAll(`.fi-chip[data-g='${btn.dataset.g}']`).forEach((c) => c.setAttribute("aria-pressed", "false"));
    btn.setAttribute("aria-pressed", "true");
    if (btn.dataset.g === "b") {
      const campo = caixa.querySelector(".fi-campo");
      if (campo) campo.value = "";
    }
    atualizarJunta(caixa);
  });
  Cards.registrarAcao("pc_juntar", async (btn, cardEl, deps) => {
    const caixa = btn.closest(".pc-raiz");
    const a = caixa.querySelector(".fi-chip[data-g='a'][aria-pressed='true']");
    const premio = premioEscolhido(caixa);
    if (!a || !premio) return;
    btn.classList.add("cd-enviando");
    const res = await postar(deps, "/api/pacote", { task_id: Number(a.dataset.id), premio });
    volta(btn);
    if (!res || !res.ok) return;
    const par = document.createElement("div");
    par.className = "pt-par";
    par.innerHTML = `<span class="pt-a">${esc(res.titulo)}</span><span class="pt-elo">${svg("elo", 2.2)}</span><span class="pt-b">${esc(res.premio)}</span>`;
    const resEl = caixa.querySelector(".pt-res");
    resEl.innerHTML = "";
    resEl.appendChild(par);
    const ul = caixa.querySelector(".pt-lista");
    ul.hidden = false;
    ul.insertAdjacentHTML("afterbegin", itemPacote({ id: res.id, titulo: res.titulo }, res.premio));
    a.remove();
    caixa.querySelectorAll(".fi-chip[data-g='b']").forEach((c) => c.setAttribute("aria-pressed", "false"));
    const campo = caixa.querySelector(".fi-campo");
    if (campo) campo.value = "";
    atualizarJunta(caixa);
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  });
  Cards.registrarAcao("pc_marcar", async (btn, cardEl, deps) => {
    const li = btn.closest(".pt-item");
    if (!li || btn.classList.contains("cd-enviando")) return;
    const id = li.dataset.id;
    const marcando = btn.getAttribute("aria-pressed") !== "true";
    const sm = li.querySelector("small");
    btn.classList.add("cd-enviando");
    const res = await postar(deps, `/api/tasks/${id}/${marcando ? "complete" : "reabrir"}`, {});
    volta(btn);
    if (!res || !res.ok) return;
    btn.setAttribute("aria-pressed", String(marcando));
    li.classList.toggle("marcado", marcando);
    li.classList.toggle("liberou", marcando);
    if (sm) sm.textContent = marcando ? `${li.dataset.premio} liberado` : `prêmio: ${String(li.dataset.premio).toLowerCase()}`;
    if (marcando) raiz.mostrarPremioLiberado(li.dataset.premio);
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  });

  // ================================================================ segundo_antes
  function abrirTela(tarefa) {
    if (typeof document === "undefined") return;
    const ov = document.createElement("div");
    ov.className = "sa-ov";
    ov.setAttribute("role", "dialog");
    ov.setAttribute("aria-label", "Um segundo antes");
    ov.innerHTML =
      `<div class="sa-bola" aria-hidden="true"></div><p class="sa-p">Ia fazer o quê?</p>` +
      (tarefa ? `<p class="sa-t">Agora era: <b>${esc(tarefa)}</b></p>` : "") +
      `<div class="sa-bts"><button type="button" class="cd-acao primaria" data-b="volta">Voltar pra tarefa</button>` +
      `<button type="button" class="cd-acao" data-b="segue">Seguir pro app</button></div>`;
    document.body.appendChild(ov);
    requestAnimationFrame(() => ov.classList.add("on"));
    const bts = ov.querySelectorAll("button");
    bts.forEach((b) => (b.disabled = true));
    setTimeout(() => bts.forEach((b) => (b.disabled = false)), reduz() ? 0 : 2500);
    const fecha = (msg) => {
      ov.classList.remove("on");
      setTimeout(() => ov.remove(), reduz() ? 0 : 500);
      toastFoco(msg);
    };
    bts[0].addEventListener("click", () => fecha("Assim aparece no iPhone. Na prévia não conta."));
    bts[1].addEventListener("click", () => fecha("Tudo bem. Abre o app."));
    ov.addEventListener("keydown", (e) => e.key === "Escape" && !bts[0].disabled && fecha("Fechou a prévia."));
    bts[0].focus && setTimeout(() => bts[0].focus(), 50);
  }
  Cards.registrar("segundo_antes", (data) => {
    const d = data || {};
    if (d.oculto) return oculto("pausa", "Um segundo antes");
    const n = Number(d.voltou_semana) || 0;
    return (
      topo("pausa", "Um segundo antes", `semana: voltou ${n}×`) +
      `<div class="cd-raiz sa-raiz" data-estado="${esc(JSON.stringify({ tarefa: d.tarefa || "" }))}">` +
      `<p class="cd-hero">Uma pausa antes do app que te puxa.</p>` +
      `<p class="cd-nota">No iPhone, uma automação do Atalhos (“quando abrir o app”) mostra 5 segundos de respiro com a tua tarefa e dois botões. Não bloqueia nada: só conta quantas vezes tu voltou.</p>` +
      `<button type="button" class="cd-acao primaria" data-acao="sa_ver">Ver como aparece</button></div>`
    );
  });
  Cards.registrarAcao("sa_ver", (btn, cardEl) => {
    const r = cardEl.querySelector(".sa-raiz");
    abrirTela(lerEstado(r || { dataset: {} }).tarefa || "");
  });

  // ================================================================ recomeco
  const MAX_MANTER = 3;
  function contar(el, de, para, ms) {
    if (reduz() || typeof raiz.requestAnimationFrame !== "function" || de === para) {
      el.textContent = String(para);
      return;
    }
    const t0 = performance.now();
    const passo = (t) => {
      const f = Math.min(1, (t - t0) / ms);
      el.textContent = String(Math.round(de + (para - de) * (1 - Math.pow(1 - f, 3))));
      if (f < 1) raiz.requestAnimationFrame(passo);
    };
    raiz.requestAnimationFrame(passo);
  }
  function itensRecomeco(e, pos) {
    const todos = lista(e.itens);
    const vis = todos.slice(0, 10);
    const mais = todos.length - vis.length;
    return (
      vis
        .map((i) => {
          const tag = pos ? "button" : "div";
          return (
            `<${tag}${pos ? ` type="button" aria-pressed="false" data-acao="rc_fica"` : ""} class="rc-it${i.velho && !pos ? " velho" : ""}${i.protegido ? " prot" : ""}${pos ? " pode" : ""}" data-id="${esc(i.id)}">` +
            `<span>${esc(i.titulo)}</span><small>${i.protegido ? "protegido" : (Number(i.dias) === 1 ? "1 dia" : (Number(i.dias) === 1 ? "1 dia" : `${esc(i.dias)} dias`))}</small></${tag}>`
          );
        })
        .join("") + (mais > 0 ? `<p class="cd-nota">e mais ${mais}</p>` : "")
    );
  }
  function raizRecomeco(e) {
    const total = Number(e.total) || 0;
    const velhas = Number(e.velhas) || 0;
    const arq = Number(e.arquivadas_n) || 0;
    const pos = arq > 0 && velhas === 0;
    let h = `<div class="cd-raiz rc-raiz" data-estado="${esc(JSON.stringify(e))}">`;
    h += `<div class="rc-cab"><span class="rc-n">${total}</span><span class="cd-nota rc-meta">` +
      (total === 0 ? "atrasadas. Tudo em dia." : pos ? "de pé. Escolhe os 3 que importam." : "atrasadas. Sem culpa: bora limpar.") + `</span></div>`;
    if (total) h += `<div class="rc-lista">${itensRecomeco(e, pos)}</div>`;
    if (pos) h += `<button type="button" class="cd-acao primaria rc-manter" data-acao="rc_manter" hidden>Esses ficam pra hoje</button>`;
    else if (velhas > 0) h += `<button type="button" class="cd-acao primaria" data-acao="rc_arquivar">Arquivar os de mais de 7 dias</button>`;
    if (arq > 0)
      h +=
        `<div class="rc-arq"><span class="rc-caixa">${svg("caixa")}</span><span><b>${plural(arq, "no arquivo", "no arquivo")}</b><small>a um toque, se precisar</small></span>` +
        `<button type="button" class="cd-mini" data-acao="rc_ver">Ver</button><button type="button" class="cd-mini" data-acao="rc_desfazer">Desfazer</button></div>` +
        `<div class="rc-arquivo" hidden>${lista(e.arquivo).map((a) => `<div class="rc-ar" data-id="${esc(a.id)}"><span>${esc(a.titulo)}</span><button type="button" class="cd-mini" data-acao="rc_devolver">Devolver</button></div>`).join("")}</div>`;
    return h + `</div>`;
  }
  Cards.registrar("recomeco", (data) => {
    const d = data || {};
    if (d.oculto) return oculto("volta", "Recomeço");
    return topo("volta", "Recomeço", "sem culpa") + raizRecomeco(d);
  });
  function trocarRecomeco(cardEl, e, de) {
    const velho = cardEl.querySelector(".rc-raiz");
    if (!velho) return;
    const t = document.createElement("div");
    t.innerHTML = raizRecomeco(e);
    const novo = t.firstElementChild;
    velho.replaceWith(novo);
    const n = novo.querySelector(".rc-n");
    if (n && typeof de === "number") contar(n, de, Number(e.total) || 0, 700);
    novo.classList.add("fi-entra");
  }
  Cards.registrarAcao("rc_arquivar", async (btn, cardEl, deps) => {
    const r = cardEl.querySelector(".rc-raiz");
    const antes = Number(lerEstado(r).total) || 0;
    btn.classList.add("cd-enviando");
    const res = await postar(deps, "/api/recomeco/arquivar", {});
    if (!res || !res.ok) return volta(btn);
    const velhos = r.querySelectorAll(".rc-it.velho");
    velhos.forEach((v, i) => setTimeout(() => v.classList.add("vai"), reduz() ? 0 : i * 90));
    setTimeout(() => {
      trocarRecomeco(cardEl, res, antes);
      toastFoco(`${plural(res.arquivadas || 0, "tarefa arquivada", "tarefas arquivadas")}. Nada se perdeu.`);
      if (typeof deps.aoMudar === "function") deps.aoMudar();
    }, reduz() ? 0 : velhos.length * 90 + 450);
  });
  Cards.registrarAcao("rc_fica", (btn, cardEl) => {
    const r = cardEl.querySelector(".rc-raiz");
    const marcados = r.querySelectorAll(".rc-it.fica");
    const ligando = !btn.classList.contains("fica");
    if (ligando && marcados.length >= MAX_MANTER) return toastFoco(`Só ${MAX_MANTER}. Tira um pra escolher outro.`);
    btn.classList.toggle("fica", ligando);
    btn.setAttribute("aria-pressed", String(ligando));
    const ok = r.querySelector(".rc-manter");
    if (ok) ok.hidden = r.querySelectorAll(".rc-it.fica").length === 0;
  });
  Cards.registrarAcao("rc_manter", async (btn, cardEl, deps) => {
    const r = cardEl.querySelector(".rc-raiz");
    const ids = Array.from(r.querySelectorAll(".rc-it.fica")).map((x) => Number(x.dataset.id));
    if (!ids.length) return;
    const antes = Number(lerEstado(r).total) || 0;
    btn.classList.add("cd-enviando");
    const res = await postar(deps, "/api/recomeco/manter", { ids });
    if (!res || !res.ok) return volta(btn);
    trocarRecomeco(cardEl, res, antes);
    toastFoco(`${plural(res.mantidas || ids.length, "ficou", "ficaram")} pra hoje.`);
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  });
  Cards.registrarAcao("rc_ver", (btn, cardEl) => {
    const a = cardEl.querySelector(".rc-arquivo");
    if (!a) return;
    a.hidden = !a.hidden;
    btn.textContent = a.hidden ? "Ver" : "Fechar";
  });
  Cards.registrarAcao("rc_desfazer", async (btn, cardEl, deps) => {
    const r = cardEl.querySelector(".rc-raiz");
    const antes = Number(lerEstado(r).total) || 0;
    btn.classList.add("cd-enviando");
    const res = await postar(deps, "/api/recomeco/desfazer", {});
    if (!res || !res.ok) return volta(btn);
    trocarRecomeco(cardEl, res, antes);
    toastFoco("Voltou tudo. Nada se perdeu.");
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  });
  Cards.registrarAcao("rc_devolver", async (btn, cardEl, deps) => {
    const r = cardEl.querySelector(".rc-raiz");
    const antes = Number(lerEstado(r).total) || 0;
    const linha = btn.closest(".rc-ar");
    btn.classList.add("cd-enviando");
    const res = await postar(deps, "/api/recomeco/devolver", { id: Number(linha.dataset.id) });
    if (!res || !res.ok) return volta(btn);
    trocarRecomeco(cardEl, res, antes);
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  });
})(typeof window !== "undefined" ? window : globalThis);
