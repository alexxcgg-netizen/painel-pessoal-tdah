// static/js/cards-dia.js - cards do dia da leva de 22/10 (docs/briefings/2026-10-22-leva-ideias-v3.md), feitos
// igual ao prototipo aprovado "Ideias do Painel": `dia_ruim` (Botao dia ruim), `alerta_dia` (Dia que vai dar errado)
// e `de_onde_parei` (ao reabrir o app com tarefa pela metade).
//
// Linguagem do prototipo (v3): linha-guia com pontinhos de passo + o que tocar agora, o proximo toque brilha
// (.cd-aqui), cadeado que fecha e abre de verdade com estalo, itens que deslizam pro grupo novo (FLIP).
// Renderizadores PUROS (estado final); os cliques re-renderizam o miolo (.cd-raiz) com o estado que a rota devolve.
// Script classico - ordem de carga em templates/scripts.html (depois de cards.js e cards-vivos.js).

(function (raiz) {
  "use strict";

  const Cards = raiz.Cards;
  if (!Cards) return;
  const esc = Cards.esc;
  const reduz = () => typeof raiz.matchMedia === "function" && raiz.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const ICONE = {
    lua: '<path d="M19 14.5A7.5 7.5 0 0 1 9.5 5a7.5 7.5 0 1 0 9.5 9.5z"/>',
    alerta: '<path d="M12 4 2.8 19.5h18.4z"/><path d="M12 10v4.2M12 16.9v.1"/>',
    cadeado: '<rect x="5.5" y="10.5" width="13" height="9.5" rx="2.5"/><path class="arco" d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5"/>',
    cama: '<path d="M3.5 18V7M3.5 14h17v4M20.5 14v-2.5A2.5 2.5 0 0 0 18 9h-6v5"/><circle cx="7.5" cy="11" r="1.5"/>',
    relogio: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    carteira: '<path d="M4 7.5A2.5 2.5 0 0 1 6.5 5H18v4"/><rect x="3.5" y="7.5" width="17" height="12" rx="3"/><circle cx="16" cy="13.5" r="1.2"/>',
    raio: '<path d="M13 3 5 13.5h6L10 21l8-10.5h-6z"/>',
    check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    alvo: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r=".8"/>',
    volta: '<path d="M4.5 12a7.5 7.5 0 1 0 2.2-5.3"/><path d="M4.5 4.5v4h4"/>',
  };
  const svg = (nome, larg) =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${larg || 2}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONE[nome] || ""}</svg>`;
  const lista = (v) => (Array.isArray(v) ? v : []);
  const topo = (ic, nome, quando) =>
    `<div class="cd-topo"><span class="cd-selo">${svg(ic)}${esc(nome)}</span>${quando ? `<span class="cd-quando">${esc(quando)}</span>` : ""}</div>`;
  const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;

  // linha-guia: pontinhos de passo + o que tocar agora (passo = indice; fim = texto final, tudo verde)
  function guia(passos, passo, fim) {
    const pts = passos.map((_, j) => `<i class="${fim || j < passo ? "ok" : j === passo ? "on" : ""}"></i>`).join("");
    return `<div class="cd-guia${fim ? " feito" : ""}"><span class="cd-pts" aria-hidden="true">${pts}</span><p class="cd-guia-txt" aria-live="polite"><span>${esc(fim || passos[passo] || "")}</span></p></div>`;
  }
  const cadeado = (id, ligado) =>
    `<button type="button" class="cd-cad" data-acao="cd_travar" data-id="${esc(id)}" aria-pressed="${ligado ? "true" : "false"}" aria-label="Inegociável">${svg("cadeado")}</button>`;
  function estalo(b) {
    b.classList.remove("estalo");
    void b.offsetWidth;
    b.classList.add("estalo");
  }
  // FLIP: quem ja existia desliza pro lugar novo; quem e novo entra de leve
  function flip(caixa, trocar) {
    const antes = {};
    caixa.querySelectorAll("[data-k]").forEach((n) => (antes[n.dataset.k] = n.getBoundingClientRect()));
    const novo = trocar();
    if (!novo || reduz() || typeof novo.animate !== "function") return novo;
    novo.querySelectorAll("[data-k]").forEach((n, i) => {
      const a = antes[n.dataset.k];
      const b = n.getBoundingClientRect();
      if (!a) {
        n.animate([{ opacity: 0, transform: "translateY(10px) scale(.97)" }, { opacity: 1, transform: "none" }], {
          duration: 480, delay: 120 + i * 35, easing: "cubic-bezier(.22,1,.36,1)", fill: "both",
        });
        return;
      }
      const dx = a.left - b.left;
      const dy = a.top - b.top;
      if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return;
      n.animate([{ transform: `translate(${dx}px,${dy}px)` }, { transform: "none" }], {
        duration: 700, delay: i * 30, easing: "cubic-bezier(.34,1.25,.64,1)", fill: "both",
      });
    });
    return novo;
  }
  function trocarRaiz(cardEl, html) {
    const velho = cardEl.querySelector(".cd-raiz");
    if (!velho) return null;
    return flip(velho, () => {
      const t = document.createElement("div");
      t.innerHTML = html;
      const novo = t.firstElementChild;
      velho.replaceWith(novo);
      return novo;
    });
  }
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
  const quando = (t) => (t.atrasada ? "atrasada" : t.hora || "");

  // ================================================================ dia_ruim
  const GUIA_DR = ["Esse é teu dia. Toca em Aliviado", "Toca num item pra empurrar ou trazer de volta"];
  function heroDiaRuim(d) {
    if (!d.ativo) {
      const n = lista(d.inegociavel).length + lista(d.reduzido).length + lista(d.fica).length;
      return n ? `${plural(n, "coisa", "coisas")} hoje.` : "Nada pendente hoje.";
    }
    const am = lista(d.amanha).length;
    return (
      `O mínimo basta: ${plural(lista(d.inegociavel).length, "inegociável", "inegociáveis")}, ` +
      `${plural(lista(d.reduzido).length, "versão curta", "versões curtas")}` + (am ? `, ${am} pra amanhã.` : ".")
    );
  }
  function itemDR(t, botao) {
    return `<div class="cd-item" data-k="t${esc(t.id)}"><span class="cd-t">${esc(t.titulo)}</span>${botao || `<span class="cd-qd">${esc(quando(t))}</span>`}</div>`;
  }
  function miolosDiaRuim(d) {
    const ineg = lista(d.inegociavel);
    const red = lista(d.reduzido);
    const fica = lista(d.fica);
    const am = lista(d.amanha);
    if (!d.ativo) {
      const todos = [...ineg, ...red, ...fica];
      return `<div class="cd-grupo" data-k="g-todos"><p class="cd-rot">Teu dia</p>${todos.map((t) => itemDR(t)).join("") || '<p class="cd-nota">Nada pendente.</p>'}</div>`;
    }
    let h = "";
    if (ineg.length)
      h += `<div class="cd-grupo ineg" data-k="g-ineg"><p class="cd-rot">${svg("cadeado")}Inegociável · fica igual, com aviso extra</p>${ineg.map((t) => itemDR(t)).join("")}</div>`;
    if (red.length)
      h += `<div class="cd-grupo" data-k="g-leve"><p class="cd-rot">Reduzido</p>${red
        .map((t) => `<div class="cd-item" data-k="t${esc(t.id)}"><span class="cd-t">${esc(t.titulo)} · ${esc(t.curta || "versão curta")}<small>antes: ${esc(t.hora || "sem hora")}</small></span></div>`)
        .join("")}</div>`;
    if (fica.length)
      h += `<div class="cd-grupo" data-k="g-fica"><p class="cd-rot">Fica hoje</p>${fica
        .map((t) => itemDR(t, `<button type="button" class="cd-mini" data-acao="dr_empurrar" data-id="${esc(t.id)}">Empurrar</button>`))
        .join("")}</div>`;
    if (am.length)
      h += `<div class="cd-grupo amanha" data-k="g-amanha"><p class="cd-rot">Empurrado pra amanhã</p>${am
        .map((t) => itemDR(t, `<button type="button" class="cd-mini" data-acao="dr_trazer" data-id="${esc(t.id)}">Trazer de volta</button>`))
        .join("")}</div>`;
    return h || '<p class="cd-nota">Nada pendente hoje.</p>';
  }
  function raizDiaRuim(d) {
    const ativo = !!d.ativo;
    return (
      `<div class="cd-raiz" data-ativo="${ativo ? 1 : 0}">` +
      guia(GUIA_DR, ativo ? 1 : 0) +
      `<p class="cd-hero">${esc(heroDiaRuim(d))}</p>` +
      `<div class="cd-seg" data-p="${ativo ? 1 : 0}" role="group" aria-label="Dia"><span class="cd-pil" aria-hidden="true"></span>` +
      `<button type="button" data-acao="dr_modo" data-modo="0" aria-pressed="${!ativo}">Como estava</button>` +
      `<button type="button" class="${ativo ? "" : "cd-aqui"}" data-acao="dr_modo" data-modo="1" aria-pressed="${ativo}">Aliviado</button></div>` +
      `<div class="cd-grupos">${miolosDiaRuim(d)}</div>` +
      `<p class="cd-pe">Voltar pra "Como estava" desfaz tudo.</p></div>`
    );
  }
  Cards.registrar("dia_ruim", (data) => topo("lua", "Dia ruim", "hoje") + raizDiaRuim(data || {}));

  async function acaoDiaRuim(btn, cardEl, deps, url, corpo) {
    const caixa = cardEl.querySelector(".cd-raiz");
    if (!caixa || caixa.dataset.enviando) return;
    caixa.dataset.enviando = "1";
    btn.classList.add("cd-enviando");
    const r = await postar(deps, url, corpo);
    delete caixa.dataset.enviando;
    btn.classList.remove("cd-enviando");
    if (!r || !r.ok) return;
    if (typeof raiz.vibrar === "function") raiz.vibrar(8);
    trocarRaiz(cardEl, raizDiaRuim(r));
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  }
  Cards.registrarAcao("dr_modo", (btn, cardEl, deps) => {
    if (btn.getAttribute("aria-pressed") === "true") return;
    const seg = btn.closest(".cd-seg");
    if (seg) seg.dataset.p = btn.dataset.modo; // a pilula ja desliza enquanto a rota responde
    return btn.dataset.modo === "1"
      ? acaoDiaRuim(btn, cardEl, deps, "/api/dia-ruim", { no_chat: false })
      : acaoDiaRuim(btn, cardEl, deps, "/api/dia-ruim/desfazer");
  });
  Cards.registrarAcao("dr_trazer", (btn, cardEl, deps) => acaoDiaRuim(btn, cardEl, deps, "/api/dia-ruim/trazer", { id: Number(btn.dataset.id) }));
  Cards.registrarAcao("dr_empurrar", (btn, cardEl, deps) => acaoDiaRuim(btn, cardEl, deps, "/api/dia-ruim/empurrar", { id: Number(btn.dataset.id) }));

  // ============================================================== alerta_dia
  const GUIA_AL = ["Toca no cadeado do que não pode falhar", "Agora toca em Aliviar o resto"];
  const ICONE_SINAL = { sono: "cama", empurradas: "relogio", gasto: "carteira", energia: "raio" };
  const subIneg = (ligado) => (ligado ? "inegociável · aviso 30 e 5 min antes" : "normal · pode ser empurrada");
  function raizAlerta(d, passo) {
    const tarefas = lista(d.tarefas);
    const aliviado = !!d.aliviado;
    const fica = aliviado ? tarefas.filter((t) => t.inegociavel) : tarefas;
    const foi = aliviado ? tarefas.filter((t) => !t.inegociavel) : [];
    const p = aliviado ? 2 : passo || 0;
    const estado = { tarefas, aliviado, respondido: !!d.respondido };
    let h =
      `<div class="cd-raiz" data-estado="${esc(JSON.stringify(estado))}">` +
      (aliviado || d.respondido ? guia(GUIA_AL, 2, aliviado ? "Travadas ficam. O resto foi pra amanhã." : "Beleza. Dia como estava.") : guia(GUIA_AL, p)) +
      `<div class="cd-grupos"><div class="cd-grupo ineg" data-k="g1"><p class="cd-rot">${svg("cadeado")}${aliviado ? "Fica hoje" : "Tem que fazer de qualquer jeito?"}</p>` +
      fica
        .map(
          (t) =>
            `<div class="cd-item" data-k="t${esc(t.id)}"><span class="cd-t">${esc(t.titulo)}${t.hora ? ` às ${esc(t.hora)}` : ""}<small>${subIneg(t.inegociavel)}</small></span>` +
            cadeado(t.id, t.inegociavel).replace('class="cd-cad"', `class="cd-cad${!aliviado && p === 0 && !t.inegociavel ? " cd-aqui" : ""}"`) +
            `</div>`
        )
        .join("") +
      `<p class="cd-nota">Toca no cadeado pra travar ou soltar.</p></div>`;
    if (foi.length)
      h += `<div class="cd-grupo amanha" data-k="g2"><p class="cd-rot">Foi pra amanhã</p>${foi
        .map((t) => `<div class="cd-item" data-k="t${esc(t.id)}"><span class="cd-t">${esc(t.titulo)}</span><span class="cd-qd">amanhã</span></div>`)
        .join("")}</div>`;
    h += `</div>`;
    if (aliviado) {
      const n = fica.length;
      const frase = n === 1 ? "1 inegociável fica como está" : `${n} inegociáveis ficam como estão`;
      h += `<div class="cd-ok">${svg("check", 2.4)}<span>${esc(`${frase}. O resto foi pra amanhã.`)}</span></div>`;
    } else if (d.respondido) {
      h += `<div class="cd-ok">${svg("check", 2.4)}<span>Beleza. Dia como estava, inegociáveis travados.</span></div>`;
    } else {
      h +=
        `<div class="cd-acoes"><button type="button" class="cd-acao primaria${p === 1 ? " cd-aqui" : ""}" data-acao="al_aliviar">Aliviar o resto</button>` +
        `<button type="button" class="cd-acao" data-acao="al_segue">Tô bem, segue</button></div>`;
    }
    return h + `</div>`;
  }
  Cards.registrar("alerta_dia", (data) => {
    const d = data || {};
    if (d.oculto) return topo("alerta", "Cuidado hoje", "") + `<p class="card-linha-meta">Oculto no modo visitante.</p>`;
    const sinais = lista(d.sinais)
      .map((s) => `<span class="cd-sinal">${svg(ICONE_SINAL[s.tipo] || "alerta")}${esc(s.texto)}</span>`)
      .join("");
    return topo("alerta", "Cuidado hoje", "manhã") + `<p class="cd-hero">Hoje pede mais cuidado.</p>` + (sinais ? `<div class="cd-sinais">${sinais}</div>` : "") + raizAlerta(d, 0);
  });
  // estado vivo do alerta: vai junto do miolo (data-estado) - o card do historico comeca do que o servidor gravou
  function estadoAlerta(cardEl) {
    const r = cardEl.querySelector(".cd-raiz[data-estado]");
    try {
      return JSON.parse((r && r.dataset.estado) || "{}");
    } catch (e) {
      return {};
    }
  }
  Cards.registrarAcao("cd_travar", async (btn, cardEl, deps) => {
    const id = Number(btn.dataset.id);
    const ligado = btn.getAttribute("aria-pressed") !== "true";
    btn.setAttribute("aria-pressed", String(ligado));
    estalo(btn);
    const sm = btn.closest(".cd-item") && btn.closest(".cd-item").querySelector("small");
    if (sm) sm.textContent = subIneg(ligado);
    if (typeof raiz.vibrar === "function") raiz.vibrar(ligado ? 12 : 6);
    const r = await postar(deps, `/api/tasks/${id}/inegociavel`, { valor: ligado });
    if (!r || !r.ok) {
      btn.setAttribute("aria-pressed", String(!ligado));
      if (sm) sm.textContent = subIneg(!ligado);
      return;
    }
    if (cardEl.dataset.cardType === "alerta_dia") {
      const est = estadoAlerta(cardEl);
      lista(est.tarefas).forEach((t) => {
        if (Number(t.id) === id) t.inegociavel = ligado;
      });
      const r2 = cardEl.querySelector(".cd-raiz[data-estado]");
      if (r2) r2.dataset.estado = JSON.stringify(est);
      // passo 2 da guia: "Agora toca em Aliviar o resto" (sem re-render: o cadeado acabou de estalar)
      if (!est.aliviado && !est.respondido) {
        const g = cardEl.querySelector(".cd-guia");
        if (g) g.outerHTML = guia(GUIA_AL, 1);
        cardEl.querySelectorAll(".cd-aqui").forEach((n) => n.classList.remove("cd-aqui"));
        const al = cardEl.querySelector('[data-acao="al_aliviar"]');
        if (al) al.classList.add("cd-aqui");
      }
    }
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  });
  Cards.registrarAcao("al_aliviar", async (btn, cardEl, deps) => {
    const est = estadoAlerta(cardEl);
    btn.disabled = true;
    const r = await postar(deps, "/api/dia-ruim", { no_chat: false });
    btn.disabled = false;
    if (!r || !r.ok) return;
    est.aliviado = true;
    const travadas = new Set(lista(r.inegociavel).map((t) => Number(t.id)));
    lista(est.tarefas).forEach((t) => (t.inegociavel = travadas.has(Number(t.id))));
    trocarRaiz(cardEl, raizAlerta(est, 2));
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  });
  Cards.registrarAcao("al_segue", (btn, cardEl) => {
    const est = estadoAlerta(cardEl);
    est.respondido = true;
    trocarRaiz(cardEl, raizAlerta(est, 2));
  });

  // ================================================================ de_onde_parei
  // Igual ao cParei do prototipo: a barra enche ate onde ele parou, a caixinha do proximo passo respira, marcar risca
  // e anda a barra. Os cliques mexem so no pedaco que mudou (sem re-render), o estado vai em data-estado.
  const GUIA_PA = ["Toca em Continuar pra abrir o próximo passo", "Marca o passo quando terminar"];
  function contaPA(passos) {
    const f = passos.filter((p) => p.feito).length;
    return { f, n: passos.length, prox: passos.findIndex((p) => !p.feito) };
  }
  const notaPA = (c) => (c.n ? `${c.f} de ${c.n} passos · ${c.f === c.n ? "tudo feito" : `falta ${c.n - c.f}`}` : "");
  function raizParei(d) {
    const passos = lista(d.passos);
    const c = contaPA(passos);
    const fim = d.deixado ? "Combinado. Hoje não falo mais disso." : c.n && c.prox < 0 ? "Tudo feito por aqui." : "";
    const estado = { task_id: d.task_id, passos, passo: d.passo || 0, deixado: !!d.deixado, concluida: !!d.concluida };
    const itens = passos
      .map(
        (p, i) =>
          `<li class="${p.feito ? "marcado" : ""}${i === c.prox && !d.deixado ? " proximo" : ""}" data-i="${i}">` +
          `<button type="button" class="pa-cx" data-acao="pa_marcar" data-i="${i}" aria-pressed="${p.feito ? "true" : "false"}" aria-label="${p.feito ? "Desmarcar" : "Marcar"}: ${esc(p.titulo)}">${svg("check", 3)}</button>` +
          `<span class="pa-txt">${esc(p.titulo)}</span></li>`
      )
      .join("");
    const acoes = d.deixado || c.prox < 0
      ? (c.prox < 0 && !d.concluida && d.task_id ? `<div class="cd-acoes"><button type="button" class="cd-acao primaria cd-aqui" data-acao="pa_concluir">Concluir a tarefa</button></div>` : "")
      : `<div class="cd-acoes"><button type="button" class="cd-acao primaria${estado.passo === 0 ? " cd-aqui" : ""}" data-acao="pa_continuar">Continuar de onde parei</button>` +
        `<button type="button" class="cd-acao" data-acao="pa_deixar">Deixar pra lá</button></div>`;
    const bolha = d.deixado
      ? `<div class="pa-bolha"><small>combinado</small>Deixei de lado. Se continuar pela metade, amanhã eu lembro.</div>`
      : d.concluida ? `<div class="cd-ok">${svg("check", 2.4)}Tarefa concluída.</div>`
      : estado.passo === 1 && c.prox >= 0 ? `<div class="pa-bolha"><small>agora</small>${esc(passos[c.prox].titulo)}</div>` : "";
    return (
      `<div class="cd-raiz" data-estado="${esc(JSON.stringify(estado))}">` +
      guia(GUIA_PA, estado.passo, fim || (d.concluida ? "Tarefa concluída." : "")) +
      `<div><div class="pa-trilho" role="progressbar" aria-valuemin="0" aria-valuemax="${c.n}" aria-valuenow="${c.f}"><i style="width:${c.n ? Math.round((c.f / c.n) * 100) : 0}%"></i></div><p class="cd-nota pa-nota">${esc(notaPA(c))}</p></div>` +
      `<ul class="pa-lista">${itens}</ul>${acoes}${bolha}</div>`
    );
  }
  Cards.registrar("de_onde_parei", (data) => {
    const d = data || {};
    const h = Number(d.parado_h);
    const quando = Number.isFinite(h) && h > 0 ? `há ${h} h` : "";
    return topo("volta", "De onde parei", quando) + `<p class="cd-hero">${esc(d.titulo || "")}</p>` + raizParei(d);
  });
  function salvarPA(cardEl, est) {
    const r = cardEl.querySelector(".cd-raiz[data-estado]");
    if (r) r.dataset.estado = JSON.stringify(est);
  }
  // so o pedaco que mudou: classes da lista, barra (transicao), nota e a guia/acoes quando fecha tudo
  function pintarPA(cardEl, est) {
    const c = contaPA(est.passos);
    cardEl.querySelectorAll(".pa-lista li").forEach((li, i) => {
      const p = est.passos[i] || {};
      li.classList.toggle("marcado", !!p.feito);
      li.classList.toggle("proximo", i === c.prox && !est.deixado);
      const b = li.querySelector(".pa-cx");
      if (b) b.setAttribute("aria-pressed", p.feito ? "true" : "false");
    });
    const barra = cardEl.querySelector(".pa-trilho");
    if (barra) {
      barra.setAttribute("aria-valuenow", String(c.f));
      barra.firstElementChild.style.width = `${c.n ? Math.round((c.f / c.n) * 100) : 0}%`;
    }
    const nota = cardEl.querySelector(".pa-nota");
    if (nota) nota.textContent = notaPA(c);
    salvarPA(cardEl, est);
    const fechou = c.n && c.prox < 0;
    const temConcluir = !!cardEl.querySelector('[data-acao="pa_concluir"]');
    if (fechou !== temConcluir) trocarRaiz(cardEl, raizParei(est));
    else if (est.passo === 1 && !fechou) {
      const bolha = cardEl.querySelector(".pa-bolha");
      if (bolha) bolha.innerHTML = `<small>agora</small>${esc(est.passos[c.prox].titulo)}`;
    }
  }
  Cards.registrarAcao("pa_marcar", async (btn, cardEl, deps) => {
    const est = estadoAlerta(cardEl);
    const p = lista(est.passos)[Number(btn.dataset.i)];
    if (!p) return;
    const antes = !!p.feito;
    p.feito = !antes; // otimista: risca na hora, volta se a rota falhar
    pintarPA(cardEl, est);
    const r = await postar(deps, `/api/subtasks/${encodeURIComponent(p.id)}/marcar`, { feito: p.feito });
    if (!r || !r.ok) {
      p.feito = antes;
      pintarPA(cardEl, est);
      return;
    }
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  });
  Cards.registrarAcao("pa_continuar", (btn, cardEl) => {
    const est = estadoAlerta(cardEl);
    if (est.passo === 1) return;
    est.passo = 1;
    trocarRaiz(cardEl, raizParei(est));
    const li = cardEl.querySelector(".pa-lista li.proximo .pa-cx");
    if (li) li.classList.add("cd-aqui");
  });
  Cards.registrarAcao("pa_deixar", async (btn, cardEl, deps) => {
    const est = estadoAlerta(cardEl);
    btn.disabled = true;
    const r = await postar(deps, "/api/de-onde-parei/deixar", { task_id: est.task_id });
    btn.disabled = false;
    if (!r || !r.ok) return;
    est.deixado = true;
    trocarRaiz(cardEl, raizParei(est));
  });
  Cards.registrarAcao("pa_concluir", async (btn, cardEl, deps) => {
    const est = estadoAlerta(cardEl);
    btn.disabled = true;
    const r = await postar(deps, `/api/tasks/${encodeURIComponent(est.task_id)}/complete`, {});
    btn.disabled = false;
    if (!r) return;
    est.concluida = true;
    trocarRaiz(cardEl, raizParei(est));
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  });

  // ================================================================ foco (Parceiro de foco)
  // Igual ao cFoco do prototipo: o anel corre com uma ponta que brilha; no meio o relogio espera e pergunta; no
  // fim dois aneis se abrem como um estouro e o check se desenha. Relogio de verdade: o servidor guarda a sessao
  // (foco.py), o card so anda o ponteiro entre um estado e outro (um relogio por pagina, 1 s).
  const GUIA_FO = ["Toca em Começar", "Faz só o primeiro passo", "Responde: ainda nisso?"];
  const FINAIS_FO = ["feito", "largado", "encerrada"];
  const mmss = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
  const durTexto = (s) => (s >= 60 ? `${Math.floor(s / 60)} min${s % 60 ? ` ${s % 60} s` : ""}` : `${s} s`);
  function pontaFoco(f) {
    const a = f * Math.PI * 2 - Math.PI / 2;
    return [(50 + 42 * Math.cos(a)).toFixed(2), (50 + 42 * Math.sin(a)).toFixed(2)];
  }
  function anelFoco(f) {
    const [x, y] = pontaFoco(f);
    return (
      `<svg viewBox="0 0 100 100" aria-hidden="true"><circle class="fo-fundo" cx="50" cy="50" r="42"/>` +
      `<circle class="fo-marcas" cx="50" cy="50" r="42" pathLength="1" transform="rotate(-90 50 50)"/>` +
      `<circle class="fo-cheio" cx="50" cy="50" r="42" pathLength="1" transform="rotate(-90 50 50)" style="stroke-dashoffset:${(1 - f).toFixed(4)}"/>` +
      `<circle class="fo-ponta" cx="${x}" cy="${y}" r="4.5"/></svg>`
    );
  }
  function botoesFoco(e, fase, total) {
    if (fase === "meio")
      return (
        `<div class="fo-pergunta"><p class="cd-rot">Passou metade. Ainda nisso?</p><div class="cd-acoes">` +
        `<button type="button" class="cd-mini cd-aqui" data-acao="fo_resp" data-r="ainda">Ainda nisso</button>` +
        `<button type="button" class="cd-mini" data-acao="fo_resp" data-r="travei">Travei</button>` +
        `<button type="button" class="cd-mini" data-acao="fo_resp" data-r="fim">Terminei</button></div></div>`
      );
    if (fase === "acabou")
      return (
        `<div class="cd-acoes"><button type="button" class="cd-acao primaria cd-aqui" data-acao="fo_resp" data-r="fim">Terminei</button>` +
        `<button type="button" class="cd-acao" data-acao="fo_resp" data-r="mais">Mais 5 min</button></div>`
      );
    if (FINAIS_FO.includes(fase)) return "";
    const rot = fase === "rodando" ? "Pausar" : fase === "pronto" ? `Começar ${Math.round(total / 60)} min` : "Continuar";
    const brilha = fase === "pronto" || (e.travei && fase === "pausado");
    return (
      `<div class="cd-acoes"><button type="button" class="cd-acao primaria${brilha ? " cd-aqui" : ""}" data-acao="${fase === "rodando" ? "fo_pausar" : "fo_comecar"}">${rot}</button>` +
      (fase !== "pronto" ? `<button type="button" class="cd-acao" data-acao="fo_resp" data-r="fim">Terminei</button>` : "") +
      `</div>`
    );
  }
  function raizFoco(e, t0) {
    const total = Number(e.total_s) || 600;
    const d = Math.min(total, Math.max(0, Number(e.decorrido_s) || 0));
    const fase = e.fase || "pronto";
    const final = FINAIS_FO.includes(fase);
    const fim =
      fase === "feito" ? "Feito. A tarefa já foi marcada." : final ? "Sessão fechada." :
      fase === "acabou" ? "Deu o tempo. Terminou ou quer mais um pouco?" : "";
    let guiaHtml = guia(GUIA_FO, fase === "pronto" ? 0 : fase === "meio" ? 2 : 1, fim);
    if (!fim && e.travei && fase === "pausado") guiaHtml = guiaHtml.replace(esc(GUIA_FO[1]), "Passo menor. Toca em Continuar quando quiser");
    const saida =
      fase === "feito" ? `<div class="cd-ok">${svg("check", 2.4)}Terminou em ${esc(durTexto(Number(e.levou_s) || d))}. +1 tarefa feita.</div>` : "";
    const estado = Object.assign({}, e, { decorrido_s: d });
    return (
      `<div class="cd-raiz fo-raiz" data-estado="${esc(JSON.stringify(estado))}" data-t0="${esc(t0)}" data-fase="${esc(fase)}">` + guiaHtml +
      `<div class="fo-linha"><div class="fo-anel${fase === "rodando" ? " corre" : ""}">${anelFoco(d / total)}` +
      `<div class="fo-meio"><b class="fo-tempo">${mmss(Math.max(0, total - d))}</b><small>meta ${Math.round(total / 60)} min</small></div>` +
      `<span class="fo-estouro${fase === "feito" ? " vai" : ""}" aria-hidden="true"><i></i><i></i></span></div>` +
      `<div class="fo-passo"><p class="cd-rot">${e.travei ? "Passo menor" : "Passo de 2 min"}</p><p>${esc(e.passo || "")}</p></div></div>` +
      botoesFoco(e, fase, total) + saida + `</div>`
    );
  }
  Cards.registrar("foco", (data, card, ctx) => {
    const e = data || {};
    if (e.oculto) return topo("alvo", "Foco", "") + `<p class="card-linha-meta">Oculto no modo visitante.</p>`;
    const t0 = ctx && ctx.agora instanceof Date ? ctx.agora.getTime() : 0;
    return topo("alvo", "Foco", `${Math.round((Number(e.total_s) || 600) / 60)} min`) + `<p class="cd-hero">${esc(e.titulo || "")}</p>` + raizFoco(e, t0);
  });
  function aplicarFoco(cardEl, sessao, estourar) {
    const novo = trocarRaiz(cardEl, raizFoco(sessao, Date.now()));
    const q = cardEl.querySelector(".cd-quando");
    if (q && sessao.total_s) q.textContent = `${Math.round(sessao.total_s / 60)} min`;
    if (novo) novo.dataset.sync = "1";
    if (estourar && novo) {
      const b = novo.querySelector(".fo-estouro");
      if (b) {
        b.classList.remove("vai");
        void b.offsetWidth;
        b.classList.add("vai");
      }
    }
    ligarRelogioFoco();
  }
  async function acaoFoco(cardEl, deps, url, corpo, estourar) {
    const est = estadoAlerta(cardEl);
    const r = await postar(deps, url, Object.assign({ id: est.id }, corpo || {}));
    if (r && r.sessao) aplicarFoco(cardEl, r.sessao, estourar);
    else if (r && r.error) aplicarFoco(cardEl, Object.assign({}, est, { fase: "encerrada" }));
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  }
  Cards.registrarAcao("fo_comecar", (btn, cardEl, deps) => acaoFoco(cardEl, deps, "/api/foco/comecar"));
  Cards.registrarAcao("fo_pausar", (btn, cardEl, deps) => acaoFoco(cardEl, deps, "/api/foco/pausar"));
  Cards.registrarAcao("fo_resp", (btn, cardEl, deps) => {
    btn.classList.add("cd-enviando");
    return acaoFoco(cardEl, deps, "/api/foco/responder", { r: btn.dataset.r }, btn.dataset.r === "fim");
  });

  // um relogio por pagina: anda o ponteiro de quem esta correndo; chegou no meio/fim -> pergunta ao servidor.
  // Card que ainda nao conversou com o servidor (historico, recarga) sincroniza uma vez pelo GET /api/foco.
  let relogioFoco = null;
  let buscando = null;
  function buscarFoco() {
    if (!buscando && typeof raiz.fetch === "function") {
      buscando = raiz
        .fetch("/api/foco", { credentials: "same-origin" })
        .then((r) => (r.ok ? r.json() : null))
        .catch(() => null)
        .finally(() => setTimeout(() => (buscando = null), 0));
    }
    return buscando || Promise.resolve(null);
  }
  function tickFoco() {
    if (typeof document === "undefined") return;
    const raizes = document.querySelectorAll(".fo-raiz");
    if (!raizes.length) {
      clearInterval(relogioFoco);
      relogioFoco = null;
      return;
    }
    if (document.hidden) return;
    raizes.forEach((r) => {
      const cardEl = r.closest(".card-contrato");
      let e;
      try {
        e = JSON.parse(r.dataset.estado || "{}");
      } catch (x) {
        return;
      }
      if (!cardEl) return;
      if (r.dataset.sync !== "1") {
        r.dataset.sync = "1";
        if (FINAIS_FO.includes(e.fase)) return;
        buscarFoco().then((j) => {
          if (!j) return;
          const s = j.sessao;
          aplicarFoco(cardEl, s && s.id === e.id ? s : Object.assign({}, e, { fase: "encerrada" }));
        });
        return;
      }
      if (e.fase !== "rodando") return;
      const total = Number(e.total_s) || 600;
      const passou = (Date.now() - (Number(r.dataset.t0) || Date.now())) / 1000;
      const limite = e.meio_ok ? total : total / 2;
      let d = Math.min(total, (Number(e.decorrido_s) || 0) + passou);
      if (d >= limite) {
        d = limite;
        if (r.dataset.pediu !== "1") {
          r.dataset.pediu = "1";
          buscarFoco().then((j) => j && j.sessao && j.sessao.id === e.id && aplicarFoco(cardEl, j.sessao));
        }
      }
      const f = d / total;
      const cheio = r.querySelector(".fo-cheio");
      if (cheio) cheio.style.strokeDashoffset = (1 - f).toFixed(4);
      const ponta = r.querySelector(".fo-ponta");
      if (ponta) {
        const [x, y] = pontaFoco(f);
        ponta.setAttribute("cx", x);
        ponta.setAttribute("cy", y);
      }
      const t = r.querySelector(".fo-tempo");
      if (t) t.textContent = mmss(Math.max(0, Math.ceil(total - d)));
    });
  }
  function ligarRelogioFoco() {
    if (relogioFoco || typeof setInterval !== "function" || typeof document === "undefined") return;
    relogioFoco = setInterval(tickFoco, 1000);
    setTimeout(tickFoco, 50);
  }
  if (typeof document !== "undefined" && typeof MutationObserver === "function") {
    // card de foco entrou no chat (resposta nova ou historico): liga o relogio
    new MutationObserver(() => {
      if (!relogioFoco && document.querySelector(".fo-raiz")) ligarRelogioFoco();
    }).observe(document.documentElement, { childList: true, subtree: true });
  }

  const api = { guia, heroDiaRuim, raizDiaRuim, raizAlerta, raizParei, raizFoco };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  raiz.CardsDia = api;
})(typeof window !== "undefined" ? window : globalThis);
