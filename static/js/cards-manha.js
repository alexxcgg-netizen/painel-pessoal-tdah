// static/js/cards-manha.js - cards da leva Lab v4 "Avisos e manha" (docs/briefings/2026-10-30-lab-v4-avisos.md), feitos
// igual as demos aprovadas do Laboratorio v4: `cartoes_manha` (pilha "Pra hoje"), `bom_dia` (onda + linhas),
// `se_entao` (Quando ___ eu ___) e `carro` (No caminho + Waze).
// Renderizadores PUROS (estado final); os cliques mexem so no pedaco do card e chamam as rotas de rotas/avisos_manha.py.
// Script classico - ordem de carga em templates/scripts.html (depois de cards-dia.js).

(function (raiz) {
  "use strict";

  const Cards = raiz.Cards;
  if (!Cards) return;
  const esc = Cards.esc;
  const reduz = () => typeof raiz.matchMedia === "function" && raiz.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const lista = (v) => (Array.isArray(v) ? v : []);

  const ICONE = {
    ia: '<path d="M12 3.5l1.9 4.6 4.6 1.9-4.6 1.9L12 16.5l-1.9-4.6-4.6-1.9 4.6-1.9z"/><path d="M18.5 15.5l.8 1.9 1.9.8-1.9.8-.8 1.9-.8-1.9-1.9-.8 1.9-.8z"/>',
    sol: '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4"/>',
    laco: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    carro: '<path d="M4 16v-3.2l1.7-4.3A2 2 0 0 1 7.6 7h8.8a2 2 0 0 1 1.9 1.5L20 12.8V16"/><path d="M3.5 16h17v2.5h-3V16M6.5 16v2.5h-3"/><circle cx="7.5" cy="13" r=".9"/><circle cx="16.5" cy="13" r=".9"/>',
    check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    pino: '<path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.3"/>',
  };
  const svg = (nome, larg) =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${larg || 2}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONE[nome] || ""}</svg>`;
  const topo = (ic, nome, quando) =>
    `<div class="cd-topo"><span class="cd-selo">${svg(ic)}${esc(nome)}</span>${quando ? `<span class="cd-quando">${esc(quando)}</span>` : ""}</div>`;

  async function postar(deps, url, corpo) {
    if (!deps || typeof deps.apiFetch !== "function") return null;
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
  // aviso curto dentro do proprio card (nao depende de componente global)
  function avisar(cardEl, texto) {
    const raizEl = cardEl.querySelector(".mn-raiz");
    if (!raizEl || !texto) return;
    let t = raizEl.querySelector(".mn-toast");
    if (!t) {
      t = document.createElement("p");
      t.className = "mn-toast";
      t.setAttribute("role", "status");
      raizEl.appendChild(t);
    }
    t.textContent = texto;
    t.classList.remove("on");
    void t.offsetWidth;
    t.classList.add("on");
  }

  // ================================================================ cartoes_manha
  const TOAST_CM = { r: "Feito.", d: "Volta amanhã.", e: "Não puxo mais esse assunto." };
  const FIM_CM = `<div class="mn-fim"><span class="mn-ok">${svg("check", 2.4)}</span><p class="cd-hero">Tudo em dia</p><p class="cd-nota">Amanhã tem mais, se tiver.</p></div>`;
  function pendentes(d) {
    return lista(d.cartoes).filter((c) => c && c.status === "novo");
  }
  function pilhaCM(cs) {
    const n = cs.length;
    return (
      `<div class="mn-pilha">` +
      cs
        .map(
          (c, i) =>
            `<div class="mn-c" style="--i:${i}" data-id="${esc(c.id)}"><p class="cd-rot">${i + 1} de ${n} · ${esc(c.titulo)}</p>` +
            `<p class="mn-t">${esc(c.texto)}</p><div class="mn-ac">` +
            `<button type="button" class="cd-mini on" data-acao="mn_r" data-id="${esc(c.id)}"${i ? " tabindex=\"-1\"" : ""}>${esc(c.rotulo || "Resolver")}</button>` +
            `<button type="button" class="cd-mini" data-acao="mn_d" data-id="${esc(c.id)}"${i ? " tabindex=\"-1\"" : ""}>Depois</button>` +
            `<button type="button" class="cd-mini" data-acao="mn_e" data-id="${esc(c.id)}"${i ? " tabindex=\"-1\"" : ""}>Esquece</button>` +
            `</div></div>`
        )
        .join("") +
      `</div>`
    );
  }
  Cards.registrar("cartoes_manha", (data) => {
    const d = data || {};
    const cs = pendentes(d);
    const ids = lista(d.cartoes).map((c) => c.id).join(",");
    return (
      topo("ia", "Pra hoje", d.preparado_as ? `preparado às ${d.preparado_as}` : "") +
      `<div class="mn-raiz" data-ids="${esc(ids)}">${cs.length ? pilhaCM(cs) : FIM_CM}</div>`
    );
  });
  function repintarCM(cardEl, cs) {
    const raizEl = cardEl.querySelector(".mn-raiz");
    if (!raizEl) return;
    raizEl.innerHTML = cs.length ? pilhaCM(cs) : FIM_CM;
  }
  async function acaoCM(btn, cardEl, deps, qual, rota) {
    const topoEl = btn.closest(".mn-c");
    if (!topoEl || topoEl.classList.contains("sai-d") || topoEl.classList.contains("sai-e")) return;
    if (topoEl.previousElementSibling) return; // so o cartao de cima responde
    const id = btn.dataset.id;
    topoEl.querySelectorAll("button").forEach((b) => (b.disabled = true));
    const r = await postar(deps, `/api/manha/${encodeURIComponent(id)}/${rota}`, {});
    if (!r || r.ok === false) {
      topoEl.querySelectorAll("button").forEach((b) => (b.disabled = false));
      avisar(cardEl, "Não consegui agora. Tenta de novo.");
      return;
    }
    topoEl.classList.add(qual === "e" ? "sai-e" : "sai-d");
    avisar(cardEl, TOAST_CM[qual]);
    const resto = Array.from(cardEl.querySelectorAll(".mn-c")).filter((n) => n !== topoEl).map((n) => ({
      id: n.dataset.id,
      titulo: (n.querySelector(".cd-rot").textContent.split(" · ").slice(1).join(" · ")),
      texto: n.querySelector(".mn-t").textContent,
      rotulo: n.querySelector('[data-acao="mn_r"]').textContent,
      status: "novo",
    }));
    setTimeout(() => repintarCM(cardEl, resto), reduz() ? 0 : 420);
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  }
  Cards.registrarAcao("mn_r", (btn, cardEl, deps) => acaoCM(btn, cardEl, deps, "r", "resolver"));
  Cards.registrarAcao("mn_d", (btn, cardEl, deps) => acaoCM(btn, cardEl, deps, "d", "depois"));
  Cards.registrarAcao("mn_e", (btn, cardEl, deps) => acaoCM(btn, cardEl, deps, "e", "esquecer"));

  // card antigo no historico: confere o status e some com o que ja foi resolvido (mesmo padrao do foco)
  const JA_SINCRONIZADO = new WeakSet();
  async function sincronizarCM(raizEl) {
    if (JA_SINCRONIZADO.has(raizEl)) return;
    JA_SINCRONIZADO.add(raizEl);
    const ids = (raizEl.dataset.ids || "").split(",").filter(Boolean);
    if (!ids.length || typeof raiz.fetch !== "function") return;
    try {
      const resp = await raiz.fetch(`/api/manha/estado?ids=${encodeURIComponent(ids.join(","))}`, { credentials: "same-origin" });
      if (!resp.ok) return;
      const j = await resp.json();
      const est = (j && j.estados) || {};
      const vivos = Array.from(raizEl.querySelectorAll(".mn-c")).filter((n) => !est[n.dataset.id] || est[n.dataset.id] === "novo");
      if (vivos.length === raizEl.querySelectorAll(".mn-c").length) return;
      repintarCM(raizEl.closest(".card-resultado") || raizEl.parentElement, vivos.map((n) => ({
        id: n.dataset.id,
        titulo: n.querySelector(".cd-rot").textContent.split(" · ").slice(1).join(" · "),
        texto: n.querySelector(".mn-t").textContent,
        rotulo: n.querySelector('[data-acao="mn_r"]').textContent,
        status: "novo",
      })));
    } catch (e) {
      /* offline: fica como veio */
    }
  }
  if (typeof document !== "undefined" && typeof MutationObserver === "function") {
    new MutationObserver(() => {
      document.querySelectorAll(".mn-raiz[data-ids]").forEach((r) => {
        if (r.querySelector(".mn-c")) sincronizarCM(r);
      });
    }).observe(document.documentElement, { childList: true, subtree: true });
  }

  // ================================================================ bom_dia
  function linhaBD(l, i) {
    const trilho =
      typeof l.trilho === "number"
        ? `<span class="mn-trilho" aria-hidden="true"><i style="width:${Math.round(Math.max(0, Math.min(1, l.trilho)) * 100)}%"></i></span>`
        : "";
    return `<div class="mn-l" style="--k:${i}"><span class="mn-lr">${esc(l.rot)}</span><span class="mn-lv">${esc(l.valor)}${trilho}</span></div>`;
  }
  Cards.registrar("bom_dia", (data) => {
    const d = data || {};
    const ondas = Array.from({ length: 5 }, (_, i) => `<i style="--b:${i}"></i>`).join("");
    return (
      topo("sol", "Bom dia", d.hora || "") +
      `<div class="mn-raiz"><div class="mn-onda" aria-hidden="true">${ondas}</div>` +
      `<div class="mn-ls">${lista(d.linhas).map(linhaBD).join("")}</div>` +
      `<p class="cd-nota">Isso é falado em voz alta, em uns 20 segundos.</p></div>`
    );
  });
  // a onda para sozinha: e so o "tocando" do Atalho, nao um video infinito
  function pararOndas() {
    if (typeof document === "undefined") return;
    document.querySelectorAll(".mn-onda:not([data-parou])").forEach((o) => {
      o.dataset.parou = "1";
      setTimeout(() => o.classList.add("quieta"), 5200);
    });
  }
  if (typeof document !== "undefined" && typeof MutationObserver === "function") {
    new MutationObserver(pararOndas).observe(document.documentElement, { childList: true, subtree: true });
  }

  // ================================================================ se_entao
  const GATILHO_HORA = "hora";
  function estadoSE(cardEl) {
    const r = cardEl.querySelector(".mn-se");
    if (!r) return null;
    if (!r._est) r._est = { g: null, a: null, hora: "" };
    return r._est;
  }
  function slotSE(cardEl, i, texto) {
    const s = cardEl.querySelector(`.mn-slot[data-s="${i}"]`);
    if (!s) return;
    s.textContent = texto || "…";
    s.classList.toggle("cheio", !!texto);
    if (texto && !reduz()) {
      s.classList.remove("pop");
      void s.offsetWidth;
      s.classList.add("pop");
    }
  }
  function prontoSE(cardEl) {
    const e = estadoSE(cardEl);
    const b = cardEl.querySelector('[data-acao="se_ativar"]');
    if (!e || !b) return;
    b.disabled = !(e.g && e.a && (e.g !== GATILHO_HORA || /^\d{2}:\d{2}$/.test(e.hora)));
  }
  Cards.registrar("se_entao", (data) => {
    const d = data || {};
    const gs = lista(d.gatilhos).concat([{ id: GATILHO_HORA, rotulo: "numa hora" }]);
    const chipsG = gs.map((g) => `<button type="button" class="mn-chip" aria-pressed="false" data-acao="se_g" data-g="${esc(g.id)}" data-r="${esc(g.rotulo)}">${esc(g.rotulo)}</button>`).join("");
    const chipsA = lista(d.acoes).map((a, i) => `<button type="button" class="mn-chip" aria-pressed="false" data-acao="se_a" data-i="${i}">${esc(a)}</button>`).join("");
    return (
      topo("laco", "Plano se-então", "") +
      `<div class="mn-raiz mn-se" data-meta="${esc(d.meta || "")}">` +
      (d.meta ? `<p class="cd-nota mn-meta">Tua meta: ${esc(d.meta)}</p>` : "") +
      `<div class="mn-frase"><span class="mn-k">Quando</span><span class="mn-slot" data-s="0">…</span><span class="mn-k">eu</span><span class="mn-slot" data-s="1">…</span></div>` +
      `<p class="cd-rot">Quando</p><div class="mn-chips">${chipsG}</div>` +
      `<label class="mn-hora" hidden><span class="cd-rot">A que horas</span><input type="time" class="mn-inp" data-hora></label>` +
      `<p class="cd-rot">Eu</p><div class="mn-chips">${chipsA}</div>` +
      `<div class="mn-pe"><button type="button" class="cd-acao primaria" data-acao="se_ativar" disabled>Ativar</button></div></div>`
    );
  });
  Cards.registrarAcao("se_g", (btn, cardEl) => {
    const e = estadoSE(cardEl);
    if (!e) return;
    cardEl.querySelectorAll('[data-acao="se_g"]').forEach((o) => o.setAttribute("aria-pressed", "false"));
    btn.setAttribute("aria-pressed", "true");
    e.g = btn.dataset.g;
    const h = cardEl.querySelector(".mn-hora");
    if (h) h.hidden = e.g !== GATILHO_HORA;
    slotSE(cardEl, 0, e.g === GATILHO_HORA ? (e.hora ? `chegar ${e.hora}` : "numa hora") : btn.dataset.r);
    prontoSE(cardEl);
  });
  Cards.registrarAcao("se_a", (btn, cardEl) => {
    const e = estadoSE(cardEl);
    if (!e) return;
    cardEl.querySelectorAll('[data-acao="se_a"]').forEach((o) => o.setAttribute("aria-pressed", "false"));
    btn.setAttribute("aria-pressed", "true");
    e.a = btn.textContent;
    slotSE(cardEl, 1, e.a);
    prontoSE(cardEl);
  });
  if (typeof document !== "undefined") {
    document.addEventListener("input", (ev) => {
      const t = ev.target;
      if (!t || !t.matches || !t.matches("input[data-hora]")) return;
      const cardEl = t.closest(".card-resultado");
      const e = cardEl && estadoSE(cardEl);
      if (!e) return;
      e.hora = t.value || "";
      if (e.g === GATILHO_HORA) slotSE(cardEl, 0, e.hora ? `às ${e.hora}` : "numa hora");
      prontoSE(cardEl);
    });
  }
  function pintarAtivo(cardEl, regra) {
    const pe = cardEl.querySelector(".mn-pe");
    if (!pe) return;
    pe.classList.add("ativo");
    pe.dataset.regra = String(regra.id);
    pe.innerHTML =
      `<span class="mn-feito">${svg("check", 2.4)}Ativo</span>` +
      `<span class="mn-pe-bt"><button type="button" class="cd-mini" data-acao="se_testar">Testar</button>` +
      `<button type="button" class="cd-mini" data-acao="se_desativar">Desativar</button></span>`;
    cardEl.querySelectorAll(".mn-chip, .mn-inp").forEach((c) => (c.disabled = true));
  }
  Cards.registrarAcao("se_ativar", async (btn, cardEl, deps) => {
    const e = estadoSE(cardEl);
    if (!e || btn.disabled) return;
    btn.disabled = true;
    const meta = cardEl.querySelector(".mn-se").dataset.meta || e.a;
    const r = await postar(deps, "/api/se-entao", { meta, gatilho: e.g, hora: e.g === GATILHO_HORA ? e.hora : null, acao: e.a });
    if (!r || !r.ok) {
      btn.disabled = false;
      avisar(cardEl, (r && r.error) || "Não consegui ativar agora.");
      return;
    }
    pintarAtivo(cardEl, { id: r.id });
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  });
  Cards.registrarAcao("se_testar", async (btn, cardEl, deps) => {
    const pe = cardEl.querySelector(".mn-pe");
    if (!pe || !pe.dataset.regra) return;
    btn.disabled = true;
    const r = await postar(deps, `/api/se-entao/${encodeURIComponent(pe.dataset.regra)}/testar`, {});
    btn.disabled = false;
    avisar(cardEl, r && r.ok ? (r.enviado ? "Mandei o aviso de teste." : "Teste feito, mas o push está desligado.") : "Não consegui testar agora.");
  });
  Cards.registrarAcao("se_desativar", async (btn, cardEl, deps) => {
    const pe = cardEl.querySelector(".mn-pe");
    if (!pe || !pe.dataset.regra) return;
    btn.disabled = true;
    const r = await postar(deps, `/api/se-entao/${encodeURIComponent(pe.dataset.regra)}/desativar`, {});
    if (!r || !r.ok) {
      btn.disabled = false;
      avisar(cardEl, "Não consegui desativar agora.");
      return;
    }
    pe.classList.remove("ativo");
    delete pe.dataset.regra;
    pe.innerHTML = `<span class="mn-feito off">Desativado</span>`;
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  });

  // ================================================================ carro
  Cards.registrar("carro", (data) => {
    const d = data || {};
    const ondas = Array.from({ length: 5 }, (_, i) => `<i style="--b:${i}"></i>`).join("");
    const extra = d.extra_min != null && d.parada ? `<p class="cd-nota mn-extra">+${esc(d.extra_min)} min com a parada</p>` : "";
    return (
      topo("carro", "No caminho", d.hora || "") +
      `<div class="mn-raiz"><div class="mn-onda" aria-hidden="true">${ondas}</div>` +
      `<p class="cd-hero mn-fala">${esc(d.fala || "")}</p>${extra}</div>`
    );
  });
})(typeof window !== "undefined" ? window : globalThis);
