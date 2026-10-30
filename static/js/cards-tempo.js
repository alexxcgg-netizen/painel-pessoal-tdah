// static/js/cards-tempo.js - Grupo B (Tempo) da leva do Laboratorio v4 (docs/briefings/2026-10-30-lab-v4-tempo.md):
// `espera` (Modo espera), `calibrador` (Calibrador de tempo), `disjuntor` (Disjuntor do hiperfoco) e `porta`
// (Checklist da porta), iguais as demos aprovadas em docs/prototipos/laboratorio-v4/demos (30-tempo, 50-corpo-grana,
// 70-vida-fone) mas com dado real do painel.
//
// Renderizadores PUROS (o HTML ja sai no estado final; a entrada animada e CSS em `.card-novo`). O que depende do
// navegador (numero que conta, estado guardado do que ele ja respondeu) entra por um observador no fim do arquivo.
// Reusa as classes `.cd-*` de cards-dia.css (selo, hero, rotulo, botoes). Script classico - ordem em templates/scripts.html.

(function (raiz) {
  "use strict";

  const Cards = raiz.Cards;
  if (!Cards) return;
  const esc = Cards.esc;
  const reduz = () => typeof raiz.matchMedia === "function" && raiz.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const lista = (v) => (Array.isArray(v) ? v : []);
  const num = (v, pad) => (Number.isFinite(Number(v)) ? Number(v) : pad || 0);

  const ICONE = {
    relogio: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    raio: '<path d="M13 3 5 13.5h6L10 21l8-10.5h-6z"/>',
    porta: '<path d="M6 20.5V4.5a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v16M4 20.5h16"/><circle cx="14.5" cy="12.5" r=".9"/>',
    aviao: '<path d="M21 15.5v-1.8l-7.5-4.6V4a1.5 1.5 0 0 0-3 0v5.1L3 13.7v1.8l7.5-2.3v4.9L8.6 19.5V21l3.4-1 3.4 1v-1.5l-1.9-1.4v-4.9z"/>',
    pino: '<path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.3"/>',
    check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    gota: '<path d="M12 3.5s-6 6.3-6 10.5a6 6 0 0 0 12 0c0-4.2-6-10.5-6-10.5z"/>',
    garfo: '<path d="M7 3v8M4.5 3v5a2.5 2.5 0 0 0 5 0V3M7 11v10"/><path d="M17 21V3c-2.2 1.2-3.5 3.6-3.5 7v3H17"/>',
    alongar: '<circle cx="12" cy="5" r="2"/><path d="M12 7.5v6M12 13.5l-3.5 7M12 13.5l3.5 7M5 10l7-2 7 2"/>',
    x: '<path d="m7 7 10 10M17 7 7 17"/>',
  };
  const svg = (nome, larg) =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${larg || 2}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONE[nome] || ""}</svg>`;
  const topo = (ic, nome, quando) =>
    `<div class="cd-topo"><span class="cd-selo">${svg(ic)}${esc(nome)}</span>${quando ? `<span class="cd-quando">${esc(quando)}</span>` : ""}</div>`;
  const virgula = (n, casas) => Number(n).toFixed(casas).replace(".", ",");
  const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;

  // 130 -> "2h10"; 120 -> "2h"; 45 -> "45 min"
  function dur(min) {
    min = Math.max(0, Math.round(num(min)));
    const h = Math.floor(min / 60);
    const m = min % 60;
    return h ? `${h}h${m ? String(m).padStart(2, "0") : ""}` : `${m} min`;
  }
  async function postar(deps, url, corpo) {
    if (!deps || typeof deps.apiFetch !== "function") return null;
    try {
      return await deps.apiFetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo || {}) });
    } catch (e) {
      return null;
    }
  }

  // ================================================================ espera (Modo espera)
  // Demo "espera": "13:50" grande, a faixa livre / arrumar / ir / compromisso, "Cabe nessa janela" e a chave "Eu te chamo".
  function linhaEspera(d) {
    const livre = Math.max(num(d.livre_min), 1);
    const arr = num(d.arrumar_min);
    const ir = Math.max(num(d.ir_min), 1);
    const fim = d.kind === "voo" ? svg("aviao") : svg("pino");
    return (
      `<div class="tp-es-linha" aria-hidden="true"><span class="tp-es-livre" style="flex:${livre}"><b>livre</b></span>` +
      (arr ? `<span class="tp-es-arr" style="flex:${arr}">arrumar</span>` : "") +
      `<span class="tp-es-tr" style="flex:${ir}">ir</span><span class="tp-es-fim" style="flex:30">${fim}</span></div>`
    );
  }
  function chamaEspera(d) {
    if (d.chamar === "garantido")
      return `<p class="tp-garantido">${svg("check", 2.4)}Eu te chamo às ${esc(d.livre_ate)}. O aviso de se arrumar já tá garantido.</p>`;
    return (
      `<div class="tp-pe"><label class="tp-chama"><input type="checkbox" data-acao="tp_chama" data-kind="${esc(d.kind)}" data-ref="${esc(d.ref)}"` +
      `${d.chamar === "desligado" ? "" : " checked"} aria-label="Eu te chamo às ${esc(d.livre_ate)}"><span class="tp-sw" aria-hidden="true"></span>` +
      `<span class="tp-chama-txt">Eu te chamo às ${esc(d.livre_ate)}</span></label></div>`
    );
  }
  function cabeEspera(d) {
    const cabe = lista(d.cabe);
    if (!cabe.length) return "";
    const itens = cabe
      .map(
        (t, i) =>
          `<li style="--k:${i}"><button type="button" class="tp-cx" data-acao="tp_cabe" data-id="${esc(t.id)}" aria-label="Marcar feito: ${esc(t.titulo)}" aria-pressed="false">${svg("check", 2.6)}</button>` +
          `<span class="tp-txt">${esc(t.titulo)}<small>${esc(dur(t.min))}</small></span></li>`
      )
      .join("");
    return `<p class="cd-rot">Cabe nessa janela</p><ul class="tp-lista">${itens}</ul>`;
  }
  Cards.registrar("espera", (data) => {
    const d = data || {};
    const livre = num(d.livre_min);
    const depois = num(d.arrumar_min) ? `se arrumar ${d.arrumar_min} min, sair ${esc(d.sair)}` : `sair ${esc(d.sair)}`;
    return (
      topo("relogio", "Livre até", `hoje · ${d.titulo || ""} ${d.hora || ""}`.trim()) +
      `<div class="cd-raiz tp-raiz tp-espera">` +
      `<div class="tp-es-big"><span class="tp-grande">${esc(d.livre_ate || "--:--")}</span><span class="cd-nota">${esc(dur(livre))} livres · depois: ${depois}</span></div>` +
      linhaEspera(d) + cabeEspera(d) + chamaEspera(d) + `</div>`
    );
  });
  Cards.registrarAcao("tp_chama", async (btn, cardEl, deps) => {
    const ligado = !!btn.checked;
    const r = await postar(deps, "/api/tempo/espera/chamar", { kind: btn.dataset.kind, ref: Number(btn.dataset.ref), ligado });
    if (!r || !r.ok) btn.checked = !ligado; // reverte: o servidor nao guardou
  });
  Cards.registrarAcao("tp_cabe", async (btn, cardEl, deps) => {
    if (btn.getAttribute("aria-pressed") === "true") return;
    const li = btn.closest("li");
    btn.setAttribute("aria-pressed", "true");
    if (li) li.classList.add("marcado");
    const r = await postar(deps, `/api/tasks/${encodeURIComponent(btn.dataset.id)}/complete`, {});
    if (!r) {
      btn.setAttribute("aria-pressed", "false");
      if (li) li.classList.remove("marcado");
    } else if (typeof deps.aoMudar === "function") deps.aoMudar();
  });

  // ================================================================ calibrador (Teu fator)
  function graficoCalibrador(hist) {
    const max = Math.max(10, ...hist.map((x) => Math.max(num(x.est), num(x.real))));
    return hist
      .map(
        (x, i) =>
          `<div class="tp-ca-l" style="--k:${i}"><span class="tp-ca-n">${esc(x.titulo)}</span><div class="tp-ca-b">` +
          `<i class="est" style="width:${((num(x.est) / max) * 100).toFixed(1)}%"></i><i class="real" style="width:${((num(x.real) / max) * 100).toFixed(1)}%"></i></div>` +
          `<span class="tp-ca-v">${num(x.est)}→${num(x.real)}</span></div>`
      )
      .join("");
  }
  const reservaCalibrador = (min, f) => Math.max(5, Math.round((min * f) / 5) * 5);
  function novaCalibrador(d, f) {
    const padrao = num(d.padrao_min, 20);
    const t = d.nova;
    return (
      `<div class="tp-ca-nova" data-fator="${esc(f)}"><p class="cd-rot">${t ? `Tarefa nova: ${esc(t.titulo)}` : "Se tu achar que leva"}</p>` +
      `<div class="tp-ca-linha"><span class="cd-nota">Tu acha:</span><output class="tp-ca-out">${padrao} min</output></div>` +
      `<input type="range" class="tp-range" data-tp-range="1" min="5" max="60" step="5" value="${padrao}" aria-label="Quanto tu acha que leva">` +
      `<p class="cd-hero tp-ca-res">Reservo <span class="tp-ca-dest">${reservaCalibrador(padrao, f)} min</span> na tua agenda</p>` +
      (t ? `<div class="cd-acoes"><button type="button" class="cd-acao primaria" data-acao="tp_palpite" data-id="${esc(t.id)}">Guardar o palpite</button></div>` : "") +
      `</div>`
    );
  }
  Cards.registrar("calibrador", (data) => {
    const d = data || {};
    const f = num(d.fator, 1);
    const hist = lista(d.historico);
    return (
      topo("relogio", "Teu fator", `últimas ${num(d.n)}`) +
      `<div class="cd-raiz tp-raiz tp-calib">` +
      `<p class="tp-grande" data-tp-contar-ate="${esc(f)}" data-tp-contar-fmt="fator">×${esc(virgula(f, 1))}</p>` +
      `<p class="cd-nota">Tu estima, em média, ${num(d.est_media)} min. Leva ${num(d.real_media)}.</p>` +
      `<div class="tp-ca-gr">${graficoCalibrador(hist)}</div>` +
      `<div class="tp-ca-leg"><span><i class="est"></i>achou</span><span><i class="real"></i>levou</span></div>` +
      novaCalibrador(d, f) + `</div>`
    );
  });
  function pintarReserva(range) {
    const caixa = range.closest(".tp-ca-nova");
    if (!caixa) return;
    const f = num(caixa.dataset.fator, 1);
    const v = num(range.value);
    const out = caixa.querySelector(".tp-ca-out");
    const dest = caixa.querySelector(".tp-ca-dest");
    if (out) out.textContent = `${v} min`;
    if (dest) dest.textContent = `${reservaCalibrador(v, f)} min`;
    // a faixa preenchida do slider acompanha o dedo
    range.style.setProperty("--tp-p", `${((v - num(range.min)) / (num(range.max) - num(range.min))) * 100}%`);
  }
  Cards.registrarAcao("tp_palpite", async (btn, cardEl, deps) => {
    const caixa = btn.closest(".tp-ca-nova");
    const range = caixa && caixa.querySelector(".tp-range");
    if (!range) return;
    btn.classList.add("cd-enviando");
    const r = await postar(deps, "/api/tempo/calibrador/palpite", { task_id: Number(btn.dataset.id), minutos: Number(range.value) });
    btn.classList.remove("cd-enviando");
    if (!r || !r.ok) return;
    btn.disabled = true;
    btn.textContent = `Guardado: ${r.minutos} min. Quando tu terminar no foco, eu comparo.`;
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  });

  // ================================================================ disjuntor (Disjuntor do hiperfoco)
  const OPS_DJ = [["agua", "Água", "gota"], ["comer", "Comer algo", "garfo"], ["alongar", "Alongar 2 min", "alongar"]];
  const FEEDBACK_DJ = { agua: "Água registrada.", comer: "Refeição registrada.", alongar: "Alonga 2 min. Eu espero." };
  function medidorDisjuntor(min) {
    const f = Math.max(0, Math.min(1, num(min) / 150));
    return (
      `<div class="tp-dj-medidor"><svg viewBox="0 0 120 70" aria-hidden="true"><path class="tp-dj-f" d="M10 64 A50 50 0 0 1 110 64" pathLength="1"/>` +
      `<path class="tp-dj-c" d="M10 64 A50 50 0 0 1 110 64" pathLength="1" style="stroke-dashoffset:${(1 - f).toFixed(3)}"/></svg>` +
      `<b class="tp-dj-t" data-tp-contar-ate="${esc(num(min))}" data-tp-contar-fmt="hm">${esc(hm(min))}</b></div>`
    );
  }
  const hm = (min) => `${Math.floor(num(min) / 60)}h${String(Math.round(num(min)) % 60).padStart(2, "0")}`;
  Cards.registrar("disjuntor", (data) => {
    const d = data || {};
    const min = num(d.minutos);
    const hero = d.motivo === "refeicao" ? `${dur(min)} no foco, sem refeição hoje` : `${dur(min)} direto sem pausa`;
    const agua = d.ultima_agua ? `Última água ${esc(d.ultima_agua)}` : "Sem água registrada hoje";
    const comida = num(d.refeicoes) ? plural(num(d.refeicoes), "refeição registrada", "refeições registradas") : "refeição não registrada";
    const ops = OPS_DJ.map(
      ([k, rot, ic]) =>
        `<button type="button" class="tp-dj-op" data-acao="tp_dj" data-k="${k}" aria-pressed="false"><span class="tp-dj-ic">${svg(ic)}</span><span>${rot}</span></button>`
    ).join("");
    return (
      topo("raio", "Disjuntor", `foco desde ${d.desde || "--:--"}`) +
      `<div class="cd-raiz tp-raiz tp-disj" data-tp-chave="dj-${esc(d.dia)}-${esc(d.desde)}" data-minutos="${min}">` +
      `<div class="tp-dj-topo">${medidorDisjuntor(min)}<div><p class="cd-hero tp-dj-hero">${esc(hero)}</p><p class="cd-nota">${agua} · ${esc(comida)}</p></div></div>` +
      `<div class="tp-dj-ops">${ops}</div>` +
      `<p class="cd-nota tp-dj-fb" aria-live="polite">Tocar registra na hora. Depois tu volta pro foco.</p></div>`
    );
  });
  function djAlongar(raizEl, fb) {
    if (raizEl._tpAlongar) return;
    let s = 120;
    const pinta = () => (fb.textContent = `Alongar: ${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}. Volta quando zerar.`);
    pinta();
    raizEl._tpAlongar = setInterval(() => {
      s -= 1;
      if (s <= 0) {
        clearInterval(raizEl._tpAlongar);
        fb.textContent = "Alongou. Pode voltar pro foco.";
        return;
      }
      pinta();
    }, 1000);
  }
  Cards.registrarAcao("tp_dj", async (btn, cardEl, deps) => {
    const raizEl = btn.closest(".tp-disj");
    if (!raizEl || btn.getAttribute("aria-pressed") === "true") return;
    const k = btn.dataset.k;
    btn.setAttribute("aria-pressed", "true");
    const fb = raizEl.querySelector(".tp-dj-fb");
    const r = await postar(deps, "/api/tempo/disjuntor", { acao: k });
    if (!r || !r.ok) {
      btn.setAttribute("aria-pressed", "false");
      if (fb) fb.textContent = "Não consegui registrar agora. Tenta de novo.";
      return;
    }
    guardarFeito(raizEl.dataset.tpChave, k);
    if (fb) fb.textContent = k === "agua" && r.copos ? `Água registrada: ${plural(r.copos, "copo", "copos")} hoje.` : FEEDBACK_DJ[k];
    if (k === "alongar" && fb) djAlongar(raizEl, fb);
    if (r.zerou || raizEl.querySelectorAll('.tp-dj-op[aria-pressed="true"]').length === 3) {
      setTimeout(() => {
        const hero = raizEl.querySelector(".tp-dj-hero");
        if (hero) hero.textContent = "Corpo em dia. Pode voltar.";
        const c = raizEl.querySelector(".tp-dj-c");
        if (c) c.style.strokeDashoffset = "1";
        const t = raizEl.querySelector(".tp-dj-t");
        if (t) t.textContent = "0h00";
      }, 400);
    }
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  });

  // ================================================================ porta (Antes de sair)
  function listaPorta(l, d, ativo, k) {
    const itens = lista(l.itens)
      .map(
        (it, i) =>
          `<li class="${it.feito ? "marcado" : ""}" style="--k:${i}"><button type="button" class="tp-cx" data-acao="tp_marca" data-lugar="${esc(l.nome)}" data-i="${i}" ` +
          `aria-pressed="${it.feito ? "true" : "false"}" aria-label="Peguei: ${esc(it.texto)}">${svg("check", 2.6)}</button><span class="tp-txt">${esc(it.texto)}</span>` +
          (it.meu ? `<button type="button" class="tp-rm" data-acao="tp_rm" data-lugar="${esc(l.nome)}" data-item="${esc(it.texto)}" aria-label="Tirar da lista: ${esc(it.texto)}">${svg("x", 2.2)}</button>` : "") +
          `</li>`
      )
      .join("");
    return `<ul class="tp-lista tp-porta-lista" data-lugar="${esc(l.nome)}"${ativo ? "" : " hidden"}>${itens}</ul>`;
  }
  function raizPorta(d) {
    const ls = lista(d.lugares);
    const atual = Math.max(0, ls.findIndex((l) => l.nome === d.lugar));
    const pilula = ls.map((l, i) => `<button type="button" data-acao="tp_lugar" data-i="${i}" aria-pressed="${i === atual ? "true" : "false"}">${esc(l.nome)}</button>`).join("");
    const falta = lista((ls[atual] || {}).itens).filter((it) => !it.feito).length;
    const aberta = ls[atual] && !falta;
    return (
      `<div class="cd-raiz tp-raiz tp-portaria" data-dia="${esc(d.dia)}" data-voo="${esc(d.voo_id == null ? "" : d.voo_id)}" data-vespera="${d.vespera ? "1" : ""}">` +
      `<div class="tp-seg" data-p="${atual}" style="--n:${Math.max(ls.length, 1)}"><span class="tp-pil" aria-hidden="true"></span>${pilula}</div>` +
      ls.map((l, i) => listaPorta(l, d, i === atual, i)).join("") +
      `<div class="tp-porta${aberta ? " aberta" : ""}"><div class="tp-folha" aria-hidden="true"></div><span class="tp-pt-txt" aria-live="polite">${esc(textoPorta(falta, ls[atual] && ls[atual].nome, d.vespera))}</span></div>` +
      `<div class="tp-add"><input type="text" maxlength="40" class="tp-add-in" placeholder="Esqueci uma vez…" aria-label="Item que tu esqueceu"><button type="button" class="cd-mini" data-acao="tp_add">Guardar</button></div>` +
      `<p class="cd-nota">O que tu esquece uma vez entra na lista pra sempre.</p></div>`
    );
  }
  function textoPorta(falta, lugar, vespera) {
    if (falta) return `Falta pegar ${falta}`;
    if (vespera) return "Mochila pronta. Amanhã é só pegar.";
    return lugar === "Voo" ? "Pode sair. Bom voo!" : "Pode sair.";
  }
  Cards.registrar("porta", (data) => {
    const d = data || {};
    return topo("porta", d.vespera ? "Deixa pronta?" : "Antes de sair", d.sai ? `sai ${d.sai}` : d.vespera ? "véspera" : "") + raizPorta(d);
  });
  function repintarPorta(raizEl) {
    const p = raizEl.querySelector(".tp-seg");
    const i = num(p && p.dataset.p);
    const ul = raizEl.querySelectorAll(".tp-porta-lista")[i];
    const nome = ul ? ul.dataset.lugar : "";
    const falta = ul ? ul.querySelectorAll("li:not(.marcado)").length : 0;
    const porta = raizEl.querySelector(".tp-porta");
    if (!porta) return;
    porta.classList.toggle("aberta", !!ul && falta === 0);
    porta.querySelector(".tp-pt-txt").textContent = textoPorta(falta, nome, raizEl.dataset.vespera === "1");
  }
  Cards.registrarAcao("tp_lugar", (btn, cardEl) => {
    const raizEl = btn.closest(".tp-portaria");
    if (!raizEl) return;
    const i = num(btn.dataset.i);
    raizEl.querySelector(".tp-seg").dataset.p = String(i);
    raizEl.querySelectorAll(".tp-seg button").forEach((b, j) => b.setAttribute("aria-pressed", j === i ? "true" : "false"));
    raizEl.querySelectorAll(".tp-porta-lista").forEach((ul, j) => (ul.hidden = j !== i));
    repintarPorta(raizEl);
  });
  Cards.registrarAcao("tp_marca", async (btn, cardEl, deps) => {
    const raizEl = btn.closest(".tp-portaria");
    const li = btn.closest("li");
    if (!raizEl || !li) return;
    const feito = !li.classList.contains("marcado");
    li.classList.toggle("marcado", feito);
    btn.setAttribute("aria-pressed", feito ? "true" : "false");
    repintarPorta(raizEl);
    const r = await postar(deps, "/api/tempo/porta/marcar", {
      lugar: btn.dataset.lugar, i: num(btn.dataset.i), feito, dia: raizEl.dataset.dia, voo_id: raizEl.dataset.voo ? Number(raizEl.dataset.voo) : null,
    });
    if (!r || !r.ok) {
      li.classList.toggle("marcado", !feito);
      btn.setAttribute("aria-pressed", !feito ? "true" : "false");
      repintarPorta(raizEl);
    }
  });
  async function itemPorta(btn, cardEl, deps, lugar, item, acao) {
    const raizEl = btn.closest(".tp-portaria");
    if (!raizEl) return;
    const r = await postar(deps, "/api/tempo/porta/item", {
      lugar, item, acao, dia: raizEl.dataset.dia, voo_id: raizEl.dataset.voo ? Number(raizEl.dataset.voo) : null,
    });
    if (!r || !r.ok || !r.card) return;
    const novo = document.createElement("div");
    novo.innerHTML = raizPorta(Object.assign({}, r.card, { lugar, sai: null }));
    raizEl.replaceWith(novo.firstElementChild);
  }
  Cards.registrarAcao("tp_add", (btn, cardEl, deps) => {
    const raizEl = btn.closest(".tp-portaria");
    const inp = raizEl && raizEl.querySelector(".tp-add-in");
    const ul = raizEl && raizEl.querySelectorAll(".tp-porta-lista")[num(raizEl.querySelector(".tp-seg").dataset.p)];
    const texto = inp ? inp.value.trim() : "";
    if (!texto || !ul) return;
    return itemPorta(btn, cardEl, deps, ul.dataset.lugar, texto, "add");
  });
  Cards.registrarAcao("tp_rm", (btn, cardEl, deps) => itemPorta(btn, cardEl, deps, btn.dataset.lugar, btn.dataset.item, "remover"));

  // ================================================================ navegador: numero que conta + o que ja respondeu
  // Guardado so no aparelho (conveniencia): o historico do chat nao oferece de novo o que ele ja tocou.
  const CHAVE_LS = "cards-tempo-feito";
  function lerFeitos() {
    try {
      return JSON.parse(raiz.localStorage.getItem(CHAVE_LS) || "{}") || {};
    } catch (e) {
      return {};
    }
  }
  function guardarFeito(chave, k) {
    if (!chave) return;
    try {
      const t = lerFeitos();
      t[chave] = Array.from(new Set([...(t[chave] || []), k]));
      const chaves = Object.keys(t);
      if (chaves.length > 40) delete t[chaves[0]];
      raiz.localStorage.setItem(CHAVE_LS, JSON.stringify(t));
    } catch (e) {
      /* sem armazenamento: o card so nao lembra */
    }
  }
  const suave = (k) => 1 - Math.pow(1 - k, 3);
  const FMT = { fator: (v) => `×${virgula(v, 1)}`, hm: (v) => hm(v) };
  function contar(n) {
    const ate = Number(n.dataset.tpContarAte);
    const fmt = FMT[n.dataset.tpContarFmt];
    if (!Number.isFinite(ate) || !fmt || reduz() || typeof raiz.requestAnimationFrame !== "function") return;
    const de = n.dataset.tpContarFmt === "fator" ? 1 : 0;
    const final = n.textContent;
    n.textContent = fmt(de);
    setTimeout(() => {
      const t0 = performance.now();
      const passo = (t) => {
        const k = Math.min(1, (t - t0) / 1300);
        n.textContent = k < 1 ? fmt(de + (ate - de) * suave(k)) : final;
        if (k < 1) raiz.requestAnimationFrame(passo);
      };
      raiz.requestAnimationFrame(passo);
    }, 350);
  }
  function preparar(escopo) {
    if (!escopo || !escopo.querySelectorAll) return;
    escopo.querySelectorAll(".tp-raiz:not([data-tp-ok])").forEach((r) => {
      r.dataset.tpOk = "1";
      const chave = r.dataset.tpChave;
      if (chave) {
        const feitos = lerFeitos()[chave] || [];
        r.querySelectorAll(".tp-dj-op").forEach((b) => b.setAttribute("aria-pressed", feitos.includes(b.dataset.k) ? "true" : "false"));
        if (feitos.length) {
          const fb = r.querySelector(".tp-dj-fb");
          if (fb) fb.textContent = feitos.length === 3 ? "Corpo em dia." : "Já registrado por aqui.";
        }
      }
      r.querySelectorAll(".tp-range").forEach(pintarReserva);
      if (r.closest(".card-novo")) r.querySelectorAll("[data-tp-contar-ate]").forEach(contar);
    });
  }
  if (typeof document !== "undefined") {
    document.addEventListener("input", (e) => {
      const t = e.target;
      if (t && t.matches && t.matches("[data-tp-range]")) pintarReserva(t);
    });
    document.addEventListener("keydown", (e) => {
      const t = e.target;
      if (e.key === "Enter" && t && t.classList && t.classList.contains("tp-add-in")) {
        e.preventDefault();
        const b = t.parentElement.querySelector('[data-acao="tp_add"]');
        if (b) b.click();
      }
    });
    const ligar = () => {
      preparar(document);
      if (typeof MutationObserver === "function")
        new MutationObserver(() => preparar(document)).observe(document.body, { childList: true, subtree: true });
    };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", ligar);
    else ligar();
  }

  const CardsTempo = { dur, hm, reservaCalibrador, textoPorta, preparar };
  raiz.CardsTempo = CardsTempo;
  if (typeof module !== "undefined" && module.exports) module.exports = CardsTempo;
})(typeof window !== "undefined" ? window : globalThis);
