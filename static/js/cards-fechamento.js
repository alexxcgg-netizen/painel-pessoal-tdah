// Fechamento e recompensa (lab v4, Grupo G, 2026-10-30): cards "Feito hoje" (placar_feito), "Pouso do
// dia" (pouso_dia) e "Retrospectiva do mes" (retrospectiva, historia em tela cheia). Protótipos
// aprovados em docs/prototipos/laboratorio-v4 (ideias placar-feito, pouso-dia, retrospectiva).
// Servidor: fechamento_dia.py e retrospectiva.py. A medalha mora em cards-medalha.js.
//
// Renderizador puro com estado final; a entrada animada so por CSS no .card-novo (historico abre
// parado). Cliques via Cards.registrarAcao. prefers-reduced-motion: nada anima.
(function (raiz) {
  "use strict";
  const Cards = raiz.Cards || (typeof require === "function" ? require("./cards.js") : null);
  if (!Cards) return;
  const { esc, numeroValido } = Cards;
  const lista = (v) => (Array.isArray(v) ? v : []);
  const reduz = () => typeof raiz.matchMedia === "function" && raiz.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const vibra = (p) => {
    if (typeof raiz.vibrar === "function") raiz.vibrar(p);
  };
  const JSON_HEADERS = { "Content-Type": "application/json" };
  const virgula = (n, casas = 1) => String(Math.round(Number(n) * 10 ** casas) / 10 ** casas).replace(".", ",");

  const ICO_OK =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>';
  const ICO_FEITO =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="m8.5 12.3 2.4 2.4 4.6-5"/></svg>';
  const ICO_AVIAO =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.5 13.5 3 11l1.5-1.5 8 1L17 6a2 2 0 0 1 3 3l-4.5 4.5 1 8L15 23l-2.5-7.5"/></svg>';
  const ICO_HISTORIA =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="6" y="3" width="12" height="18" rx="3"/><path d="M9.5 7h5"/></svg>';
  const ICO_SETA =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h13M13 6l6 6-6 6"/></svg>';
  const eyebrow = (icone, rotulo, extra) =>
    `<div class="card-resultado-eyebrow">${icone}<span>${esc(rotulo)}</span>${extra || ""}</div>`;

  // numero que sobe ate o valor (duracao curta); sem animacao com reduce
  function conta(el, de, para, ms) {
    if (!el) return;
    if (reduz() || de === para || typeof raiz.requestAnimationFrame !== "function") {
      el.textContent = String(para);
      return;
    }
    const t0 = raiz.performance.now();
    const passo = (agora) => {
      const f = Math.min(1, (agora - t0) / ms);
      el.textContent = String(Math.round(de + (para - de) * (1 - Math.pow(1 - f, 3))));
      if (f < 1) raiz.requestAnimationFrame(passo);
    };
    raiz.requestAnimationFrame(passo);
  }

  // ===================================================================== placar_feito
  const textoContagem = (n) => (n === 1 ? "coisa feita" : "coisas feitas");

  function itemPlacar(it, i, novo) {
    const extra = it.origem === "extra" && numeroValido(it.id);
    return (
      `<li class="pf-it${novo ? " novo" : ""}${extra ? " extra" : ""}" style="--k:${i}"${extra ? ` data-extra-id="${esc(it.id)}"` : ""}>` +
      `<span class="pf-ck">${ICO_OK}</span><span class="pf-t">${esc(it.texto)}</span><small>${esc(it.rotulo || "")}</small>` +
      (extra
        ? `<button type="button" class="pf-x" data-acao="placar_remover" aria-label="Tirar ${esc(it.texto)} do placar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="m8 8 8 8M16 8l-8 8"/></svg></button>`
        : "") +
      `</li>`
    );
  }

  Cards.registrar("placar_feito", (data) => {
    const itens = lista(data.itens).filter((it) => it && typeof it.texto === "string");
    const total = itens.length;
    const sug = lista(data.sugestoes).filter((s) => typeof s === "string" && s).slice(0, 4);
    const chips = sug
      .map((s) => `<button type="button" class="pf-chip" data-acao="placar_add" data-texto="${esc(s)}">+ ${esc(s)}</button>`)
      .join("");
    return (
      `<div class="pf" data-dia="${esc(data.dia || "")}" data-total="${total}">` +
      eyebrow(ICO_FEITO, "Feito hoje", data.hora ? `<span class="card-chip pf-hora vivo-num">${esc(data.hora)}</span>` : "") +
      `<p class="pf-grande"><span class="pf-n vivo-num">${total}</span> <span class="pf-un">${textoContagem(total)}</span></p>` +
      `<ul class="pf-lista" role="list">${itens.map((it, i) => itemPlacar(it, i, false)).join("")}</ul>` +
      `<p class="pf-vazio"${total ? " hidden" : ""}>Ainda nada riscado, mas se tu fez algo, mesmo fora do plano, anota aqui.</p>` +
      (data.oculto
        ? ""
        : `<p class="pf-rot">Fez algo fora do plano?</p>` +
          (chips ? `<div class="pf-chips">${chips}</div>` : "") +
          `<div class="pf-form"><input class="pf-input" type="text" maxlength="80" enterkeyhint="done" autocomplete="off" placeholder="Outra coisa que tu fez" aria-label="Outra coisa que tu fez">` +
          `<button type="button" class="pf-mais" data-acao="placar_add" aria-label="Anotar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M12 6v12M6 12h12"/></svg></button></div>`) +
      `</div>`
    );
  });

  function placarAtualiza(raizEl, delta) {
    const n = raizEl.querySelector(".pf-n");
    const de = Number(raizEl.dataset.total) || 0;
    const para = Math.max(0, de + delta);
    raizEl.dataset.total = String(para);
    conta(n, de, para, 500);
    const un = raizEl.querySelector(".pf-un");
    if (un) un.textContent = textoContagem(para);
    const vazio = raizEl.querySelector(".pf-vazio");
    if (vazio) vazio.hidden = para > 0;
  }

  if (typeof Cards.registrarAcao === "function") {
    Cards.registrarAcao("placar_add", async (btn, cardEl, deps) => {
      const pf = btn.closest(".pf");
      if (!pf || btn.disabled || typeof deps.apiFetch !== "function") return;
      const input = pf.querySelector(".pf-input");
      const texto = btn.dataset.texto || (input ? input.value : "");
      if (!String(texto).trim()) {
        if (input) input.focus();
        return;
      }
      btn.disabled = true;
      const res = await deps.apiFetch("/api/feito-hoje", {
        method: "POST",
        headers: JSON_HEADERS,
        body: JSON.stringify({ texto, dia: pf.dataset.dia || undefined }),
      });
      btn.disabled = false;
      if (!res || !res.ok) return;
      if (btn.dataset.texto) {
        btn.disabled = true;
        btn.setAttribute("aria-pressed", "true");
      } else if (input) input.value = "";
      const ul = pf.querySelector(".pf-lista");
      const ja = res.item && ul.querySelector(`[data-extra-id="${res.item.id}"]`);
      if (res.item && !ja) {
        ul.insertAdjacentHTML("beforeend", itemPlacar(res.item, ul.children.length, true));
        placarAtualiza(pf, 1);
        vibra(10);
        const novo = ul.lastElementChild;
        if (novo && typeof novo.scrollIntoView === "function") novo.scrollIntoView({ block: "nearest", behavior: reduz() ? "auto" : "smooth" });
      }
      if (typeof deps.aoMudar === "function") deps.aoMudar();
    });

    Cards.registrarAcao("placar_remover", async (btn, cardEl, deps) => {
      const li = btn.closest(".pf-it");
      const pf = btn.closest(".pf");
      if (!li || !pf || btn.disabled || typeof deps.apiFetch !== "function") return;
      btn.disabled = true;
      const res = await deps.apiFetch(`/api/feito-hoje/${encodeURIComponent(li.dataset.extraId)}`, { method: "DELETE" });
      if (!res || !res.ok) {
        btn.disabled = false;
        return;
      }
      const texto = li.querySelector(".pf-t") ? li.querySelector(".pf-t").textContent : "";
      placarAtualiza(pf, -1);
      pf.querySelectorAll(".pf-chip").forEach((c) => {
        if (c.dataset.texto === texto) {
          c.disabled = false;
          c.removeAttribute("aria-pressed");
        }
      });
      li.classList.add("saindo");
      setTimeout(() => li.remove(), reduz() ? 0 : 320);
    });
  }

  // Enter no campo "outra coisa" = toque no +
  if (typeof document !== "undefined" && document.addEventListener) {
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Enter" || !e.target || !e.target.classList || !e.target.classList.contains("pf-input")) return;
      e.preventDefault();
      const mais = e.target.closest(".pf-form").querySelector(".pf-mais");
      if (mais) mais.click();
    });
  }

  // ======================================================================== pouso_dia
  const HORA_TXT = (h) => (h ? ` · ${esc(h)}` : "");
  const AVIAO_FIM =
    '<svg viewBox="0 0 260 90" aria-hidden="true"><path class="pd-pista" d="M10 78h240"/><path class="pd-faixas" d="M30 78h200"/><g class="pd-aviao"><path d="M0 0l16-3 10-10h4l-5 11 9-1 3-4h3l-2 6 2 6h-3l-3-4-9-1 5 11h-4L16 3z" transform="scale(1.1)"/></g></svg>';

  function fimPouso(data) {
    const p = data.primeira;
    const frase = p && p.texto ? `Boa noite. Amanhã começa por ${esc(p.texto)}.` : "Boa noite. Amanhã é um dia limpo.";
    return `<div class="pd-fim">${AVIAO_FIM}<b>Dia pousado.</b><span class="pd-fim-t">${frase}</span></div>`;
  }

  function passosPouso(data) {
    const passos = [];
    const pend = lista(data.pendentes).filter((p) => p && numeroValido(p.id));
    const ids = lista(data.ids_adiar);
    if (ids.length) {
      const itens = pend
        .map((p) => `<li><span>${esc(p.titulo)}</span><small>${p.atrasada ? "atrasada" : esc(p.hora || "")}</small></li>`)
        .join("");
      passos.push({
        tipo: "aberto",
        titulo: "Ficou aberto",
        corpo:
          `<ul class="pd-lista">${itens}</ul>` + (data.mais ? `<p class="pd-mais">e mais ${esc(data.mais)}</p>` : ""),
        botao: `Empurrar ${ids.length === 1 ? "essa" : `as ${ids.length}`} pra amanhã`,
        extra: `<button type="button" class="pd-deixa" data-acao="pouso_proximo" data-kind="deixa">Deixar como está</button>`,
        attrs: `data-ids="${esc(ids.join(","))}"`,
      });
    }
    if (data.primeira && data.primeira.texto) {
      passos.push({
        tipo: "primeira",
        titulo: "Primeira coisa amanhã",
        corpo: `<p class="pd-primeira"><b>${esc(data.primeira.texto)}</b><small>${data.primeira.hora ? esc(data.primeira.hora) : "sem horário"}</small></p>`,
        botao: "Combinado",
        attrs: "",
      });
    }
    const m = data.mochila;
    if (m && lista(m.itens).length) {
      const itens = lista(m.itens)
        .map(
          (it, i) =>
            `<li><button type="button" class="pd-item${it.feito ? " feito" : ""}" data-acao="pouso_item" data-voo="${esc(m.voo_id)}" data-i="${i}" aria-pressed="${it.feito ? "true" : "false"}">` +
            `<span class="pd-ck">${ICO_OK}</span><span>${esc(it.texto)}</span></button></li>`
        )
        .join("");
      passos.push({
        tipo: "mochila",
        titulo: "Mochila do voo",
        corpo: `<ul class="pd-mochila">${itens}</ul>`,
        botao: "Pronta",
        attrs: `data-voo="${esc(m.voo_id)}" data-n="${lista(m.itens).length}"`,
      });
    }
    return passos;
  }

  Cards.registrar("pouso_dia", (data) => {
    const passos = data.pousado ? [] : passosPouso(data);
    const pousado = data.pousado || passos.length === 0;
    const blocos = passos
      .map(
        (p, k) =>
          `<section class="pd-passo" data-k="${k}" data-tipo="${p.tipo}"${k ? " hidden" : ""}>` +
          `<small class="pd-cont">${k + 1} de ${passos.length}</small><b class="pd-tit">${esc(p.titulo)}</b>${p.corpo}` +
          `<button type="button" class="pd-bt" data-acao="pouso_proximo" data-kind="${p.tipo}" ${p.attrs}>${esc(p.botao)}</button>${p.extra || ""}</section>`
      )
      .join("");
    const trilha = passos.map((_p, k) => `<i${k === 0 ? ' class="agora"' : ""}></i>`).join("");
    return (
      `<div class="pd${pousado ? " pousado" : ""}" data-dia="${esc(data.dia || "")}" data-k="0" data-total="${passos.length}">` +
      eyebrow(ICO_AVIAO, "Pouso do dia", trilha && !pousado ? `<span class="pd-trilha" aria-hidden="true">${trilha}</span>` : "") +
      `<div class="pd-area">${blocos}<div class="pd-final"${pousado ? "" : " hidden"}>${fimPouso(data)}</div></div>` +
      `</div>`
    );
  });

  if (typeof Cards.registrarAcao === "function") {
    const mostraPasso = (pd, k) => {
      pd.dataset.k = String(k);
      pd.querySelectorAll(".pd-passo").forEach((s) => {
        s.hidden = Number(s.dataset.k) !== k;
      });
      pd.querySelectorAll(".pd-trilha i").forEach((p, i) => p.classList.toggle("agora", i === k));
    };

    async function pousar(pd, deps) {
      pd.classList.add("pousado", "chegou");
      pd.querySelectorAll(".pd-passo").forEach((s) => {
        s.hidden = true;
      });
      const fim = pd.querySelector(".pd-final");
      if (fim) fim.hidden = false;
      pd.querySelectorAll(".pd-trilha i").forEach((p) => p.classList.add("agora"));
      vibra([10, 60, 14]);
      if (typeof deps.apiFetch === "function") {
        await deps.apiFetch("/api/pouso-dia/pousar", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ dia: pd.dataset.dia || undefined }) });
      }
    }

    // passos 2 e 3 frescos: depois de empurrar tarefas, a primeira coisa de amanha pode mudar
    async function atualizaAmanha(pd, deps) {
      if (typeof deps.apiFetch !== "function") return;
      const r = await deps.apiFetch("/api/pouso-dia/amanha");
      if (!r) return;
      const pass1 = pd.querySelector('.pd-passo[data-tipo="primeira"]');
      if (pass1) {
        if (r.primeira && r.primeira.texto) {
          const p = pass1.querySelector(".pd-primeira");
          p.querySelector("b").textContent = r.primeira.texto;
          p.querySelector("small").textContent = r.primeira.hora || "sem horário";
        } else pass1.dataset.vazio = "1";
      }
      const tx = pd.querySelector(".pd-fim-t");
      if (tx) tx.textContent = r.primeira && r.primeira.texto ? `Boa noite. Amanhã começa por ${r.primeira.texto}.` : "Boa noite. Amanhã é um dia limpo.";
    }

    function proximoVisivel(pd, de) {
      const passos = Array.from(pd.querySelectorAll(".pd-passo"));
      for (let k = de + 1; k < passos.length; k++) if (!passos[k].dataset.vazio) return k;
      return -1;
    }

    Cards.registrarAcao("pouso_proximo", async (btn, cardEl, deps) => {
      const pd = btn.closest(".pd");
      if (!pd || btn.disabled) return;
      const k = Number(pd.dataset.k) || 0;
      const kind = btn.dataset.kind;
      btn.disabled = true;
      pd.querySelectorAll(".pd-passo:not([hidden]) button").forEach((b) => {
        b.disabled = true;
      });
      let ok = true;
      if (kind === "aberto" && typeof deps.apiFetch === "function") {
        const ids = String(btn.dataset.ids || "").split(",").map(Number).filter((n) => n > 0);
        const res = await deps.apiFetch("/api/tarefas/adiar", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ ids }) });
        ok = !!res;
        if (ok) {
          vibra(12);
          await atualizaAmanha(pd, deps);
          if (typeof deps.aoMudar === "function") deps.aoMudar();
        }
      } else if (kind === "deixa") {
        await atualizaAmanha(pd, deps);
      } else if (kind === "mochila" && typeof deps.apiFetch === "function") {
        const passo = btn.closest(".pd-passo");
        const itens = Array.from(passo.querySelectorAll(".pd-item:not(.feito)"));
        for (const it of itens) {
          const r = await deps.apiFetch(`/api/voos/${encodeURIComponent(it.dataset.voo)}/mochila`, {
            method: "POST",
            headers: JSON_HEADERS,
            body: JSON.stringify({ i: Number(it.dataset.i), feito: true }),
          });
          if (r) {
            it.classList.add("feito");
            it.setAttribute("aria-pressed", "true");
          } else ok = false;
        }
      }
      pd.querySelectorAll(".pd-passo button").forEach((b) => {
        b.disabled = false;
      });
      if (!ok) return;
      const prox = proximoVisivel(pd, k);
      if (prox < 0) await pousar(pd, deps);
      else mostraPasso(pd, prox);
    });

    // item da mochila: o mesmo estado do card da vespera do voo
    Cards.registrarAcao("pouso_item", async (btn, cardEl, deps) => {
      if (btn.dataset.enviando || typeof deps.apiFetch !== "function") return;
      const feito = !btn.classList.contains("feito");
      btn.classList.toggle("feito", feito);
      btn.setAttribute("aria-pressed", String(feito));
      btn.dataset.enviando = "1";
      vibra(8);
      const r = await deps.apiFetch(`/api/voos/${encodeURIComponent(btn.dataset.voo)}/mochila`, {
        method: "POST",
        headers: JSON_HEADERS,
        body: JSON.stringify({ i: Number(btn.dataset.i), feito }),
      });
      delete btn.dataset.enviando;
      if (!r) {
        btn.classList.toggle("feito", !feito);
        btn.setAttribute("aria-pressed", String(!feito));
      }
    });
  }

  // ================================================================== retrospectiva
  // As telas saem dos campos do card: so existe tela de quem tem dado de verdade.
  function telasRetro(d) {
    const telas = [{ k: "intro", pequeno: `${d.mes_nome}, em números`, grande: "", sub: "Toca pra seguir →" }];
    if (numeroValido(d.tarefas) && d.tarefas > 0) {
      let sub = "";
      if (numeroValido(d.tarefas_ant) && d.tarefas_ant > 0) {
        const dif = d.tarefas - d.tarefas_ant;
        sub = dif === 0 ? `igual a ${d.anterior_nome}` : `${Math.abs(dif)} ${dif > 0 ? "a mais" : "a menos"} que ${d.anterior_nome}`;
      }
      telas.push({ k: "tarefas", pequeno: d.tarefas === 1 ? "tarefa fechada" : "tarefas fechadas", grande: String(d.tarefas), sub });
    }
    if (numeroValido(d.kg) && d.kg > 0) {
      const t = numeroValido(d.treinos) && d.treinos > 0 ? `${d.treinos} ${d.treinos === 1 ? "treino marcado" : "treinos marcados"} ao vivo` : "";
      telas.push({ k: "kg", pequeno: "levantados no total", grande: `${Math.round(d.kg).toLocaleString("pt-BR")} kg`, sub: t });
    }
    if (numeroValido(d.voo_horas) && d.voo_horas > 0) {
      const sub = d.aerodromos_novos > 0 ? `${d.aerodromos_novos} ${d.aerodromos_novos === 1 ? "aeródromo novo" : "aeródromos novos"}` : `${d.voos} ${d.voos === 1 ? "voo" : "voos"} no mês`;
      telas.push({ k: "voo", pequeno: "horas voadas", grande: `${virgula(d.voo_horas)} h`, sub });
    }
    if (d.recorde && numeroValido(d.recorde.rm)) {
      const mais = d.recorde.total > 1 ? ` · ${d.recorde.total} recordes no mês` : "";
      telas.push({ k: "recorde", pequeno: "recorde do mês", grande: `${virgula(d.recorde.rm)} kg`, sub: `1RM estimado no ${String(d.recorde.nome || "").toLowerCase()}${mais}` });
    }
    if (!d.oculto && d.gasto_cresceu && d.gasto_cresceu.categoria) {
      telas.push({ k: "gasto", pequeno: "o gasto que mais cresceu", grande: String(d.gasto_cresceu.categoria).charAt(0).toUpperCase() + String(d.gasto_cresceu.categoria).slice(1), sub: `+R$ ${Math.round(d.gasto_cresceu.mais).toLocaleString("pt-BR")} em relação a ${d.anterior_nome}` });
    }
    telas.push({ k: "meta", pequeno: `pra ${d.proximo_nome}, uma coisa só:`, grande: "", sub: "" });
    return telas;
  }

  Cards.registrar("retrospectiva", (data) => {
    const telas = telasRetro(data);
    const numeros = telas
      .filter((t) => t.grande && t.k !== "gasto")
      .slice(0, 3)
      .map((t) => `<span class="rtr-num"><b class="vivo-num">${esc(t.grande)}</b><small>${esc(t.pequeno)}</small></span>`)
      .join("");
    return (
      `<div class="rtr">` +
      eyebrow(ICO_HISTORIA, "Retrospectiva") +
      `<button type="button" class="rtr-capa" data-acao="retro_abrir" data-mes="${esc(data.mes)}" data-retro="${esc(JSON.stringify(data))}" aria-label="Abrir a retrospectiva de ${esc(data.mes_nome)}">` +
      `<span class="rtr-capa-mes">${esc(data.mes_nome)}</span><span class="rtr-capa-sub">em números</span>` +
      (numeros ? `<span class="rtr-nums">${numeros}</span>` : "") +
      `<span class="rtr-ver">Toca pra ver ${ICO_SETA}</span></button>` +
      (data.meta_escolhida ? `<p class="rtr-meta">Meta de ${esc(data.proximo_nome)}: <b>${esc(data.meta_escolhida)}</b></p>` : "") +
      `</div>`
    );
  });
  const DURACAO_TELA = 3200;

  function abrirHistoria(d, deps, opener) {
    if (typeof document === "undefined" || document.querySelector(".rtr-ov")) return;
    const telas = telasRetro(d);
    const auto = !reduz();
    const ov = document.createElement("div");
    ov.className = "rtr-ov";
    ov.setAttribute("role", "dialog");
    ov.setAttribute("aria-modal", "true");
    ov.setAttribute("aria-label", `Retrospectiva de ${d.mes_nome}`);
    ov.innerHTML =
      `<div class="rtr-story"><div class="rtr-barras" aria-hidden="true">${telas.map(() => "<i><b></b></i>").join("")}</div>` +
      `<button type="button" class="rtr-fecha" aria-label="Fechar a retrospectiva"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="m7 7 10 10M17 7 7 17"/></svg></button>` +
      `<div class="rtr-tela" aria-live="polite"></div></div>`;
    document.body.appendChild(ov);
    const story = ov.querySelector(".rtr-story");
    const tela = ov.querySelector(".rtr-tela");
    const barras = Array.from(ov.querySelectorAll(".rtr-barras i"));
    let k = 0, tm = 0, t0 = 0, restante = DURACAO_TELA, segurou = false, suprime = false, hold = 0, fechando = false;
    const ultima = telas.length - 1;

    function fecha() {
      if (fechando) return;
      fechando = true;
      clearTimeout(tm);
      clearTimeout(hold);
      document.removeEventListener("keydown", tecla);
      ov.classList.remove("on");
      setTimeout(() => ov.remove(), reduz() ? 0 : 420);
      if (opener && typeof opener.focus === "function") opener.focus({ preventScroll: true });
    }
    function agenda(ms) {
      clearTimeout(tm);
      t0 = Date.now();
      restante = ms;
      tm = setTimeout(() => vai(k + 1), ms);
    }
    function pausa() {
      if (!tm) return;
      clearTimeout(tm);
      tm = 0;
      restante -= Date.now() - t0;
      const b = barras[k] && barras[k].firstElementChild;
      if (b) b.style.animationPlayState = "paused";
    }
    function retoma() {
      if (tm || !auto || k >= ultima) return;
      const b = barras[k] && barras[k].firstElementChild;
      if (b) b.style.animationPlayState = "running";
      t0 = Date.now();
      tm = setTimeout(() => vai(k + 1), Math.max(300, restante));
    }
    function vai(n) {
      k = Math.max(0, Math.min(ultima, n));
      clearTimeout(tm);
      tm = 0;
      barras.forEach((b, i) => {
        b.className = i < k ? "feito" : i === k ? "agora" : "";
        if (b.firstElementChild) b.firstElementChild.style.animationPlayState = "";
      });
      const t = telas[k];
      tela.style.setProperty("--h", String((k * 47 + 200) % 360));
      tela.innerHTML = "";
      const cont = document.createElement("div");
      cont.className = "rtr-cont";
      cont.innerHTML = `<small></small><b></b><span></span>`;
      cont.querySelector("small").textContent = t.pequeno;
      cont.querySelector("b").textContent = t.grande;
      cont.querySelector("span").textContent = t.sub;
      if (!t.grande) cont.querySelector("b").hidden = true;
      if (!t.sub) cont.querySelector("span").hidden = true;
      tela.appendChild(cont);
      if (k === ultima) montaMeta(cont);
      else if (auto) agenda(DURACAO_TELA);
    }
    function montaMeta(cont) {
      const metas = lista(d.metas).filter((m) => typeof m === "string" && m);
      const chips = document.createElement("div");
      chips.className = "rtr-metas";
      const escolhida = d.meta_escolhida;
      metas.forEach((m) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "rtr-chip";
        b.textContent = m;
        b.setAttribute("aria-pressed", String(m === escolhida));
        b.addEventListener("click", async (e) => {
          e.stopPropagation();
          if (typeof deps.apiFetch !== "function") return;
          const res = await deps.apiFetch(`/api/retrospectiva/${encodeURIComponent(d.mes)}/meta`, {
            method: "POST",
            headers: JSON_HEADERS,
            body: JSON.stringify({ meta: m }),
          });
          if (!res || !res.ok) return;
          chips.querySelectorAll(".rtr-chip").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
          d.meta_escolhida = res.meta;
          conf.textContent = `Meta de ${d.proximo_nome}: ${res.meta}. Fechado.`;
          conf.hidden = false;
          vibra(12);
          const card = opener && opener.closest(".rtr");
          if (card) {
            let p = card.querySelector(".rtr-meta");
            if (!p) {
              p = document.createElement("p");
              p.className = "rtr-meta";
              card.appendChild(p);
            }
            p.textContent = `Meta de ${d.proximo_nome}: ${res.meta}`;
          }
        });
        chips.appendChild(b);
      });
      const conf = document.createElement("p");
      conf.className = "rtr-conf";
      conf.hidden = true;
      cont.appendChild(chips);
      cont.appendChild(conf);
      if (escolhida) {
        conf.textContent = `Meta de ${d.proximo_nome}: ${escolhida}.`;
        conf.hidden = false;
      }
      const fim = document.createElement("button");
      fim.type = "button";
      fim.className = "rtr-fim";
      fim.textContent = "Fechar";
      fim.addEventListener("click", (e) => {
        e.stopPropagation();
        fecha();
      });
      cont.appendChild(fim);
    }
    function tecla(e) {
      if (e.key === "Escape") fecha();
      else if (e.key === "ArrowRight") vai(k + 1);
      else if (e.key === "ArrowLeft") vai(k - 1);
    }
    ov.querySelector(".rtr-fecha").addEventListener("click", (e) => {
      e.stopPropagation();
      fecha();
    });
    // segurar = pausa (como nas historias); toque curto: esquerda volta, o resto avanca
    story.addEventListener("pointerdown", (e) => {
      if (e.target.closest("button")) return;
      segurou = false;
      hold = setTimeout(() => {
        segurou = true;
        pausa();
      }, 220);
    });
    const solta = () => {
      clearTimeout(hold);
      if (segurou) {
        suprime = true;
        retoma();
        setTimeout(() => {
          suprime = false;
        }, 60);
      }
    };
    story.addEventListener("pointerup", solta);
    story.addEventListener("pointercancel", solta);
    story.addEventListener("click", (e) => {
      if (e.target.closest("button") || suprime) return;
      const r = story.getBoundingClientRect();
      vai(e.clientX - r.left < r.width * 0.3 ? k - 1 : k + 1);
    });
    document.addEventListener("keydown", tecla);
    vai(0);
    requestAnimationFrame(() => ov.classList.add("on"));
    const bt = ov.querySelector(".rtr-fecha");
    if (bt) bt.focus({ preventScroll: true });
    vibra(8);
  }

  if (typeof Cards.registrarAcao === "function") {
    Cards.registrarAcao("retro_abrir", async (btn, cardEl, deps) => {
      let d;
      try {
        d = JSON.parse(btn.dataset.retro || "{}");
      } catch (_e) {
        return;
      }
      if (!d || !d.mes_nome) return;
      // meta ja escolhida (pode ter sido depois que o card foi guardado): pergunta fresco, sem travar o toque
      abrirHistoria(d, deps, btn);
      if (typeof deps.apiFetch === "function") {
        const fresco = await deps.apiFetch(`/api/retrospectiva/${encodeURIComponent(d.mes)}`);
        if (fresco && fresco.meta_escolhida) {
          d.meta_escolhida = fresco.meta_escolhida;
          const conf = document.querySelector(".rtr-ov .rtr-conf");
          if (conf) {
            conf.textContent = `Meta de ${d.proximo_nome}: ${fresco.meta_escolhida}.`;
            conf.hidden = false;
            document.querySelectorAll(".rtr-ov .rtr-chip").forEach((c) => c.setAttribute("aria-pressed", String(c.textContent === fresco.meta_escolhida)));
          }
        }
      }
    });
  }

  const api = { telasRetro, passosPouso };
  raiz.CardsFechamento = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
