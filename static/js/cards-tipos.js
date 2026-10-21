// Renderizadores dos types do contrato de cards (docs/CARDS.md). Cada um e
// uma funcao PURA (data, card, ctx) -> string HTML registrada no registro de
// static/js/cards.js. Todo texto vindo de `data` passa por esc(); moeda sempre
// por Cards.moeda (= fmtMoeda do app.js). Dado faltando nunca lanca excecao
// de proposito - no pior caso o registro troca pelo card fallback.
(function (raiz) {
  "use strict";
  const Cards = raiz.Cards || (typeof require === "function" ? require("./cards.js") : null);
  if (!Cards) return;

  const { esc, moeda, numeroValido, MOEDA_OCULTA } = Cards;

  // Mesmos tracos dos icones do card de resultado antigo (app.js) - stroke 1.8,
  // cantos arredondados - pra ficar parte do mesmo produto.
  const ICONES = {
    tarefa:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 12l2.5 2.5L16 9"/></svg>',
    gasto:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18"/><circle cx="16.5" cy="14" r="1"/></svg>',
    meta:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="0.8" fill="currentColor" stroke="none"/></svg>',
    lembrete:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="13" r="8"/><path d="M12 9v4l2.5 2.5M5 3 2 6M19 3l3 3"/></svg>',
    resumo:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.4L12 3z"/></svg>',
  };

  const ICONE_PIN =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11Z"/><circle cx="12" cy="10" r="2.3"/></svg>';

  function eyebrow(icone, texto, extra) {
    return `<div class="card-resultado-eyebrow">${icone || ""}<span>${esc(texto)}</span>${extra || ""}</div>`;
  }

  function segundos(ms) {
    const bruto = Math.max(0, Math.round(Number(ms) || 0));
    if (bruto < 1000) return `${bruto} ms`;
    const s = bruto / 1000;
    if (s < 10) return `${s.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} s`;
    return `${Math.round(s)} s`;
  }

  function lista(v) {
    return Array.isArray(v) ? v : [];
  }

  // ---- tarefas_criadas ------------------------------------------------------

  function diaRelativoTarefa(iso) {
    // os dois pelo mesmo parseDia (ele devolve o dia ao meio-dia) - comparar com a meia-noite
    // de hoje dava meio dia de diferenca e "hoje" virava "amanhã"
    const d = Cards.parseDia(iso);
    const agora = new Date();
    const h = Cards.parseDia(
      `${agora.getFullYear()}-${String(agora.getMonth() + 1).padStart(2, "0")}-${String(agora.getDate()).padStart(2, "0")}`
    );
    if (!d || !h) return Cards.dataCurta(iso);
    const dif = Math.round((d - h) / 86400000);
    if (dif === 0) return "hoje";
    if (dif === 1) return "amanhã";
    return Cards.dataCurta(iso);
  }

  function quandoTarefa(t) {
    const partes = [];
    if (t.recorrencia) partes.push("rotina");
    else if (t.data) partes.push(diaRelativoTarefa(t.data));
    else if (t.quando) partes.push(String(t.quando));
    if (t.hora) partes.push(String(t.hora));
    return partes.length ? partes.join(" · ") : "sem data";
  }

  // ---- tarefa com aperto (2026-10-14, prototipo aprovado, docs/CARDS.md) ----------------
  // A nova caiu a menos de 45 min de outra pendente do dia: uma "lupa" de 3h com as duas,
  // a faixa apertada entre os inicios e o botao de passar a outra pra sugestao do servidor.
  // So horario de inicio e dado de verdade (tarefa nao tem duracao): os blocos tem largura
  // fixa so pra caber o nome.
  const JANELA = 180;
  const minDia = (h) => {
    const m = /^(\d{1,2}):(\d{2})/.exec(h || "");
    return m ? +m[1] * 60 + +m[2] : null;
  };
  const horaBr = (min) => `${Math.floor(min / 60)}h${min % 60 ? String(min % 60).padStart(2, "0") : ""}`;
  const curto = (txt, n) => (txt.length > n ? `${txt.slice(0, n - 1).trimEnd()}…` : txt);

  function apertoHTML(t, data, ctx) {
    const a = data.aperto;
    const n = minDia(t.hora);
    const o = minDia(a.hora);
    const ini = Math.max(0, Math.min(24 * 60 - JANELA, Math.floor(Math.min(n, o) / 60) * 60 - 60));
    const pct = (m) => Math.max(0, Math.min(100, ((m - ini) / JANELA) * 100));
    const largura = (m, dur) => Math.min(pct(m + dur), 100) - pct(m);
    const tiques = [0, 1, 2, 3]
      .map((k) => `<span class="ap-tique${k === 3 ? " ultimo" : ""}" style="left:${(k * 100) / 3}%">${String(ini / 60 + k).padStart(2, "0")}h</span>`)
      .join("");
    const agora = (ctx && ctx.agora) || new Date();
    const dia = Cards.parseDia(data.dia);
    const agoraMin = agora.getHours() * 60 + agora.getMinutes();
    const linhaAgora =
      dia && Cards.mesmoDia(dia, agora) && agoraMin > ini && agoraMin < ini + JANELA
        ? `<span class="ap-agora" style="left:${pct(agoraMin).toFixed(2)}%"></span>`
        : "";
    const titOutra = Cards.partesTarefa(a.titulo).titulo || a.titulo;
    const rotuloEsq = pct(o) > 55 ? " rotulo-esq" : "";
    const diff = Math.abs(n - o);
    const status =
      diff === 0
        ? `<b>${esc(titOutra)}</b> também é às ${esc(horaBr(o))}.`
        : `<b>${esc(titOutra)}</b> é às ${esc(horaBr(o))} — ${diff} min ${o < n ? "antes" : "depois"} dessa.`;
    const sug = minDia(a.sugestao);
    const acoes =
      sug !== null && numeroValido(Number(a.id))
        ? `<div class="ap-acoes"><button type="button" class="ap-acao primaria" data-acao="aperto_mover" data-id="${esc(a.id)}" data-hora="${esc(a.sugestao)}" data-ini="${ini}">` +
          `Passar ${esc(curto(titOutra, 26))} pras ${esc(horaBr(sug))}</button>` +
          `<button type="button" class="ap-acao" data-acao="aperto_deixa">Deixa assim</button></div>`
        : "";
    return (
      eyebrow(ICONES.tarefa, "Tarefa criada", "") +
      `<h3 class="ap-hero">${Cards.tituloTarefaHTML(t.titulo)}</h3>` +
      `<p class="ap-meta"><span class="vivo-num">${esc(t.hora)}</span> · ${esc(diaRelativoTarefa(t.data))}</p>` +
      `<div class="ap-lupa" role="img" aria-label="${esc(`Das ${horaBr(ini)} às ${horaBr(ini + JANELA)}: ${titOutra} às ${a.hora}, a nova às ${t.hora}`)}">` +
      `<div class="ap-grade"></div>${tiques}` +
      `<div class="ap-faixa" style="left:${pct(Math.min(n, o)).toFixed(2)}%;width:${(pct(Math.max(n, o)) - pct(Math.min(n, o))).toFixed(2)}%"></div>` +
      linhaAgora +
      `<div class="ap-bloco l1 outra${rotuloEsq}" style="left:${pct(o).toFixed(2)}%;width:${largura(o, 30).toFixed(2)}%"><span>${esc(curto(titOutra, 22))} · ${esc(horaBr(o))}</span></div>` +
      `<div class="ap-bloco l2 nova" style="left:${pct(n).toFixed(2)}%;width:${largura(n, 60).toFixed(2)}%"><span>nova · ${esc(horaBr(n))}</span></div>` +
      `</div>` +
      `<p class="ap-status" aria-live="polite">${ICONE_ALERTA}<span>${status}</span></p>` +
      acoes
    );
  }

  const ICONE_ALERTA =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4 2.8 19.5h18.4L12 4Z"/><path d="M12 10v4M12 17h.01"/></svg>';
  const ICONE_OK_AP =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="m8.5 12.3 2.4 2.3 4.6-4.9"/></svg>';

  function apertoResolvido(cardEl, texto) {
    const status = cardEl.querySelector(".ap-status");
    const lupa = cardEl.querySelector(".ap-lupa");
    if (lupa) lupa.classList.add("resolvido");
    if (status) {
      status.classList.add("ok");
      status.innerHTML = `${ICONE_OK_AP}<span class="ap-troca">${esc(texto)}</span>`;
    }
    const acoes = cardEl.querySelector(".ap-acoes");
    if (acoes) {
      acoes.classList.add("some");
      setTimeout(() => (acoes.hidden = true), 360);
    }
    if (typeof raiz.vibrar === "function") raiz.vibrar(12);
  }

  if (typeof Cards.registrarAcao === "function") {
    Cards.registrarAcao("aperto_mover", async (btn, cardEl, deps) => {
      if (btn.disabled || typeof deps.apiFetch !== "function") return;
      btn.disabled = true;
      const res = await deps.apiFetch(`/api/tasks/${encodeURIComponent(btn.dataset.id)}/hora`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hora: btn.dataset.hora }),
      });
      if (!res || !res.ok) {
        btn.disabled = false;
        return;
      }
      const m = minDia(res.hora);
      const ini = Number(btn.dataset.ini) || 0;
      const bloco = cardEl.querySelector(".ap-bloco.outra");
      if (bloco && m !== null) {
        const p = Math.max(0, Math.min(100 - parseFloat(bloco.style.width || "0"), ((m - ini) / JANELA) * 100));
        bloco.style.left = `${p.toFixed(2)}%`;
        bloco.classList.toggle("rotulo-esq", p > 55);
        const rot = bloco.querySelector("span");
        if (rot) rot.textContent = rot.textContent.replace(/ · [^·]+$/, ` · ${horaBr(m)}`);
      }
      const titulo = btn.textContent.replace(/^Passar /, "").replace(/ pras .*$/, "");
      apertoResolvido(cardEl, `${titulo} agora às ${horaBr(m)}.`);
      if (typeof deps.aoMudar === "function") deps.aoMudar();
    });
    Cards.registrarAcao("aperto_deixa", (btn, cardEl) => apertoResolvido(cardEl, "Deixei como estava."));
  }

  Cards.registrar("tarefas_criadas", (data, _card, ctx) => {
    const tarefas = lista(data.tarefas).filter((t) => t && typeof t === "object");
    if (tarefas.length === 1 && data.aperto && minDia(data.aperto.hora) !== null && minDia(tarefas[0].hora) !== null && data.aperto.titulo) {
      return apertoHTML(tarefas[0], data, ctx);
    }
    const titulo = tarefas.length === 1 ? "Tarefa criada" : "Tarefas criadas";
    const itens = tarefas
      .map((t) => {
        const id = t.id !== undefined && t.id !== null ? esc(t.id) : "";
        const marcada = t.concluida ? " checked" : "";
        return (
          `<li class="card-tarefa${t.concluida ? " concluida" : ""}">` +
          `<label><input type="checkbox"${id ? ` data-tarefa-id="${id}"` : " disabled"}${marcada} aria-label="Concluir ${esc(t.titulo)}">` +
          `<span class="card-tarefa-titulo">${Cards.tituloTarefaHTML(t.titulo)}</span></label>` +
          `<span class="card-tarefa-quando">${esc(quandoTarefa(t))}</span>` +
          (t.local ? `<span class="card-local">${ICONE_PIN}${esc(t.local)}</span>` : "") +
          `</li>`
        );
      })
      .join("");
    const contador = tarefas.length > 1 ? `<span class="card-contador">${tarefas.length}</span>` : "";
    const agenda = lista(data.agenda_do_dia).filter((t) => t && t.titulo);
    // cartao vivo (2026-10-10): com o dia em volta, a tarefa nova aparece no lugar dela
    // na linha do tempo (as outras do dia apagadas; a nova "pousa" com brilho)
    if (agenda.length > 1 && agenda.some((t) => t.nova)) {
      // dia inteiro montado de uma vez (planejar_dia): todas sao novas, entao o selo "nova"
      // e o pouso com brilho nao distinguem nada - so marca quando ha nova no meio de antigas
      const todasNovas = agenda.every((t) => t.nova);
      const novas = agenda.filter((t) => t.nova).length;
      const rotuloDia = diaRelativoTarefa(data.dia);
      const resumo = todasNovas
        ? `Seu dia ${esc(rotuloDia)}, montado: <strong>${agenda.length}</strong> blocos`
        : `Seu dia ${esc(rotuloDia)}: <strong>${agenda.length}</strong> tarefas${novas > 1 ? `, ${novas} novas` : ""}`;
      const planos = planosValidos(data.planos, agenda);
      const escolhido = planos && planos.escolhido === "b" ? "b" : "a";
      return (
        eyebrow(ICONES.tarefa, todasNovas ? "Dia montado" : titulo, contador) +
        `<p class="card-linha-meta vivo-dia-resumo">${resumo}</p>` +
        (planos ? pilulaPlanosHTML(planos, escolhido, agenda, data.dia) : "") +
        `<div class="dia-miolo">${mioloDiaHTML(planos ? comHorasDoPlano(agenda, planos[escolhido]) : agenda, rotuloDia)}</div>`
      );
    }
    return eyebrow(ICONES.tarefa, titulo, contador) + `<ul class="card-tarefas">${itens}</ul>`;
  });

  function mioloDiaHTML(agenda, rotuloDia) {
    const todasNovas = agenda.every((t) => t.nova);
    const destaca = (t) => t.nova && !todasNovas;
    const linhas = agenda
      .map(
        (t) =>
          `<li class="card-tarefa vivo-dia-item${destaca(t) ? " vivo-nova" : ""}${t.concluida ? " concluida" : ""}">` +
          `<label><input type="checkbox" data-tarefa-id="${esc(t.id)}"${t.concluida ? " checked" : ""} aria-label="Concluir ${esc(Cards.partesTarefa(t.titulo).titulo)}">` +
          `<span class="card-tarefa-titulo">${Cards.tituloTarefaHTML(t.titulo)}</span></label>` +
          `<span class="card-tarefa-quando">${destaca(t) ? '<span class="vivo-selo-nova">nova</span>' : ""}${t.hora ? Cards.horaTarefaHTML(t.titulo, t.hora) : "sem hora"}</span>` +
          `</li>`
      )
      .join("");
    return (
      (typeof Cards.trilhaDia === "function" ? Cards.trilhaDia(agenda, { hoje: rotuloDia === "hoje" }) : "") +
      `<ul class="card-tarefas vivo-dia-lista" data-vivo="criadas">${linhas}</ul>`
    );
  }

  // ---- dois planos dentro do card (2026-10-21, prototipo aprovado "B + pilula") -------------
  // A IA ja escolheu e gravou o plano A; o B fica do lado numa pilula. Tocar troca as horas das
  // tarefas (POST /api/tasks/<id>/hora, uma por uma, otimista) e a lista/trilha se reordena.
  // `escolhido` vem do servidor (o historico confere com as horas de agora).
  function planosValidos(p, agenda) {
    if (!p || typeof p !== "object") return null;
    const ids = new Set(agenda.map((t) => String(t.id)));
    const plano = (x) =>
      x && typeof x === "object"
        ? {
            nome: typeof x.nome === "string" && x.nome ? x.nome : "",
            nota: typeof x.nota === "string" ? x.nota : "",
            itens: lista(x.itens).filter((i) => i && ids.has(String(i.id)) && minDia(i.hora) !== null),
          }
        : null;
    const a = plano(p.a);
    const b = plano(p.b);
    if (!a || !b || !a.nome || !b.nome || !a.itens.length || !b.itens.length) return null;
    return { a, b, escolhido: p.escolhido === "b" ? "b" : "a" };
  }

  function comHorasDoPlano(agenda, plano) {
    const horas = new Map(plano.itens.map((i) => [String(i.id), i.hora]));
    return agenda
      .map((t) => (horas.has(String(t.id)) ? Object.assign({}, t, { hora: horas.get(String(t.id)) }) : t))
      .slice()
      .sort((x, y) => (minDia(x.hora) ?? 9999) - (minDia(y.hora) ?? 9999));
  }

  function pilulaPlanosHTML(planos, escolhido, agenda, dia) {
    const botao = (k) =>
      `<button type="button" data-acao="dia_plano" data-plano="${k}" aria-pressed="${k === escolhido}">${esc(planos[k].nome)}</button>`;
    const estado = esc(JSON.stringify({ planos: { a: planos.a, b: planos.b }, agenda, dia }));
    return (
      `<div class="dia-planos" data-estado="${estado}">` +
      `<div class="dia-planos-pilula" role="group" aria-label="Jeito do dia" style="--p:${escolhido === "b" ? 1 : 0}">` +
      `<span class="dia-planos-fundo" aria-hidden="true"></span>${botao("a")}${botao("b")}</div>` +
      `<p class="dia-planos-nota" aria-live="polite">${esc(planos[escolhido].nota)}</p>` +
      `</div>`
    );
  }

  if (typeof Cards.registrarAcao === "function") {
    Cards.registrarAcao("dia_plano", async (btn, cardEl, deps) => {
      const caixa = btn.closest(".dia-planos");
      const miolo = cardEl.querySelector(".dia-miolo");
      if (!caixa || !miolo || btn.getAttribute("aria-pressed") === "true" || caixa.dataset.trocando) return;
      let estado;
      try {
        estado = JSON.parse(caixa.dataset.estado);
      } catch {
        return;
      }
      const k = btn.dataset.plano === "b" ? "b" : "a";
      const anterior = k === "b" ? "a" : "b";
      const plano = estado.planos[k];
      // caixinhas como estao agora (ele pode ter marcado alguma depois da resposta)
      const feitas = new Set([...miolo.querySelectorAll("input[data-tarefa-id]:checked")].map((c) => c.dataset.tarefaId));
      const agenda = estado.agenda.map((t) => Object.assign({}, t, { concluida: feitas.has(String(t.id)) }));
      const pintar = (qual) => {
        const pil = caixa.querySelector(".dia-planos-pilula");
        pil.style.setProperty("--p", qual === "b" ? 1 : 0);
        pil.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.plano === qual)));
        caixa.querySelector(".dia-planos-nota").textContent = estado.planos[qual].nota || "";
        miolo.classList.remove("dia-miolo-troca");
        miolo.innerHTML = mioloDiaHTML(comHorasDoPlano(agenda, estado.planos[qual]), diaRelativoTarefa(estado.dia));
        void miolo.offsetWidth; // reinicia a animacao de troca
        miolo.classList.add("dia-miolo-troca");
      };
      caixa.dataset.trocando = "1";
      pintar(k);
      if (typeof raiz.vibrar === "function") raiz.vibrar(10);
      let ok = typeof deps.apiFetch === "function";
      for (const item of ok ? plano.itens : []) {
        if (feitas.has(String(item.id))) continue; // feita nao muda de hora (a rota recusa)
        const res = await deps.apiFetch(`/api/tasks/${encodeURIComponent(item.id)}/hora`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ hora: item.hora }),
        });
        if (!res || !res.ok) {
          ok = false;
          break;
        }
      }
      if (!ok) {
        // volta o que ja tinha trocado e o desenho (otimista que deu errado)
        for (const item of estado.planos[anterior].itens) {
          if (feitas.has(String(item.id))) continue;
          await deps.apiFetch(`/api/tasks/${encodeURIComponent(item.id)}/hora`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ hora: item.hora }),
          });
        }
        pintar(anterior);
      } else if (typeof deps.aoMudar === "function") {
        deps.aoMudar();
      }
      delete caixa.dataset.trocando;
    });
  }

  // ---- transacao ------------------------------------------------------------

  Cards.registrar("transacao", (data, card, ctx) => {
    const entrada = data.sentido === "entrada";
    const planejado = data.status === "planejado";
    const rotulo = entrada ? "Entrada registrada" : planejado ? "Gasto planejado" : "Gasto registrado";
    const oculto = Boolean(data.oculto) || !numeroValido(data.valor);
    const valorTxt = oculto ? MOEDA_OCULTA : `${entrada ? "+" : "-"}${moeda(data.valor)}`;
    const dia = data.data ? Cards.rotuloDia(data.data, ctx && ctx.agora) : "";
    const linha = [dia, data.meio, data.categoria].filter(Boolean).map((p) => esc(p)).join(" · ");
    const cat = entrada ? "entrada" : data.categoria || "outros";
    let saldo = "";
    const s = data.saldo;
    if (!data.oculto && s && typeof s === "object" && numeroValido(s.antes) && numeroValido(s.depois)) {
      saldo =
        `<p class="card-saldo"><span class="card-saldo-rotulo">Saldo${s.conta ? ` ${esc(s.conta)}` : ""}</span>` +
        `<span class="card-saldo-valores">${esc(moeda(s.antes))} <span class="card-seta" aria-hidden="true">→</span> <strong>${esc(moeda(s.depois))}</strong></span></p>`;
    }
    // gasto real com o contexto do mes (2026-10-14, docs/CARDS.md "Linguagem visual"): cupom
    // saindo da impressora + quanto a categoria ja tem no mes + os ultimos 14 dias
    if (!entrada && !planejado && !oculto && data.mes && typeof data.mes === "object") {
      return eyebrow(ICONES.gasto, rotulo, "") + cupomGasto(data, valorTxt, ctx) + saldo + mesGasto(data);
    }
    return (
      eyebrow(ICONES.gasto, rotulo, planejado ? '<span class="card-chip card-chip-planejado">planejado</span>' : "") +
      `<div class="card-transacao-topo"><span class="card-bolinha" data-cat="${esc(cat)}" aria-hidden="true"></span>` +
      `<p class="card-titulo">${esc(data.titulo)}</p></div>` +
      `<p class="card-valor-grande${entrada ? " entrada" : ""}${oculto ? " oculto" : ""}">${esc(valorTxt)}</p>` +
      (linha ? `<p class="card-linha-meta">${linha}</p>` : "") +
      saldo
    );
  });

  const MESES_NOME = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
  const reais = (v) => `R$ ${Math.round(v).toLocaleString("pt-BR")}`;

  function cupomGasto(data, valorTxt, ctx) {
    const agora = (ctx && ctx.agora) || new Date();
    const dia = Cards.parseDia(data.data) || agora;
    // so a data: o card re-renderiza no historico, e a hora "de agora" ficaria errada la
    const quando = `${String(dia.getDate()).padStart(2, "0")}/${String(dia.getMonth() + 1).padStart(2, "0")}/${dia.getFullYear()}`;
    return (
      `<div class="tx-impressora" aria-label="${esc(`${data.titulo || "Gasto"}: ${valorTxt}`)}"><div class="tx-fresta"><div class="tx-cupom">` +
      `<p class="tx-c">${esc(data.titulo || data.categoria || "Gasto")}</p><hr>` +
      `<p class="tx-l"><span>${esc(quando)}</span><span>${esc(data.meio || "")}</span></p>` +
      `<p class="tx-l"><span>categoria</span><span>${esc(data.categoria || "outros")}</span></p><hr>` +
      `<p class="tx-l tx-total"><span>TOTAL</span><span class="card-valor-grande">${esc(valorTxt)}</span></p>` +
      `</div></div></div>`
    );
  }

  function mesGasto(data) {
    const m = data.mes;
    if (!numeroValido(m.gasto)) return "";
    const agora = Cards.parseDia(data.data) || new Date();
    const cat = m.categoria || data.categoria || "";
    const titulo = `${cat ? `${cat.charAt(0).toUpperCase()}${cat.slice(1)} · ` : ""}${MESES_NOME[agora.getMonth()]}`;
    const limite = numeroValido(m.limite) && m.limite > 0 ? m.limite : null;
    let barra = "";
    let frase = "";
    if (limite) {
      const antes = numeroValido(m.antes) ? m.antes : 0;
      const ja = Math.min(100, (antes / limite) * 100);
      const novo = Math.max(0, Math.min(100 - ja, ((m.gasto - antes) / limite) * 100));
      const estourou = m.gasto > limite;
      barra =
        `<div class="tx-barra${estourou ? " tx-estourou" : ""}"><i class="tx-ja" style="width:${ja.toFixed(2)}%"></i>` +
        `<i class="tx-novo" style="left:${ja.toFixed(2)}%;width:${novo.toFixed(2)}%"></i></div>`;
      frase = estourou
        ? `passou ${esc(reais(m.gasto - limite))} do teto`
        : numeroValido(m.sobra_dia) && numeroValido(m.dias_restantes)
          ? `sobram ${esc(reais(m.sobra))} · uns ${esc(reais(m.sobra_dia))}/dia até o fim do mês`
          : "";
    }
    const dias = Array.isArray(data.dias) ? data.dias.filter(numeroValido).slice(-14) : [];
    const maior = Math.max(...dias, 0);
    const barras = dias.length && maior > 0
      ? `<div class="tx-dias" aria-hidden="true">${dias
          .map((v, i) => `<i${i === dias.length - 1 ? ' class="tx-hoje"' : ""} style="--h:${Math.max(6, (v / maior) * 100).toFixed(1)}%;--k:${i}"></i>`)
          .join("")}</div><p class="tx-dias-leg"><span>14 dias atrás</span><span>hoje</span></p>`
      : "";
    return (
      `<div class="tx-mes"><div class="tx-mes-topo"><span>${esc(titulo)}</span>` +
      `<span class="tx-mes-val"><b class="vivo-num" data-contar-moeda="${Number(m.gasto)}">${esc(reais(m.gasto))}</b>${limite ? ` de ${esc(reais(limite))}` : " no mês"}</span></div>` +
      barra + (frase ? `<p class="tx-sobra">${frase}</p>` : "") + barras + `</div>`
    );
  }

  // ---- lembrete -------------------------------------------------------------

  // Alvo da contagem: data + hora do lembrete, ou 09:00 do dia (mesmo
  // horario do push "Desperta voce" - notificacoes.HORA_PADRAO_DESPERTAR).
  function alvoLembrete(data) {
    return Cards.parseDataHora(data.data, data.hora || "09:00");
  }

  Cards.registrar(
    "lembrete",
    (data, card, ctx) => {
      const agora = (ctx && ctx.agora) || new Date();
      const alvo = alvoLembrete(data);
      const destaque = data.hora ? String(data.hora) : Cards.diaMesCurto(data.data) || "—";
      const dia = data.data ? Cards.rotuloDia(data.data, agora) : "";
      const contagem = alvo
        ? `<span class="card-contagem-viva" data-contagem-alvo="${esc(alvo.toISOString())}">${esc(Cards.textoContagem(alvo, agora))}</span>`
        : "";
      const botoes = ["desfazer", "despertar"]
        .flatMap((tipo) => Cards.acoesDoTipo(card, tipo))
        .map(Cards.acaoHTML)
        .join("");
      return (
        eyebrow(ICONES.lembrete, "Lembrete criado", data.recorrente ? '<span class="card-chip">repete todo ano</span>' : "") +
        `<p class="card-titulo">${esc(data.titulo)}</p>` +
        `<p class="card-hora-grande">${esc(destaque)}</p>` +
        `<p class="card-linha-meta">${esc(dia)}${dia && contagem ? " · " : ""}${contagem}</p>` +
        (data.local ? `<p class="card-local">${ICONE_PIN}${esc(data.local)}</p>` : "") +
        (botoes ? `<div class="card-botoes">${botoes}</div>` : "")
      );
    },
    { consome: ["desfazer", "despertar"] }
  );

  // ---- meta -----------------------------------------------------------------

  function dataPlanejada(iso) {
    const d = Cards.parseDia(iso);
    if (!d) return "Sem data planejada";
    return `Data planejada: ${Cards.diaMesCurto(iso)} ${d.getFullYear()}`;
  }

  Cards.registrar("meta", (data) => {
    const oculto = Boolean(data.oculto) || !numeroValido(data.valor_alvo);
    const guardado = numeroValido(data.valor_guardado) ? data.valor_guardado : 0;
    let pct = numeroValido(data.percentual)
      ? data.percentual
      : !oculto && data.valor_alvo > 0
        ? (guardado / data.valor_alvo) * 100
        : 0;
    pct = Math.max(0, Math.min(100, pct));
    const valores = oculto
      ? `<strong>${MOEDA_OCULTA}</strong> de ${MOEDA_OCULTA}`
      : `<strong>${esc(moeda(guardado))}</strong> de ${esc(moeda(data.valor_alvo))}`;
    const falta = oculto
      ? MOEDA_OCULTA
      : moeda(numeroValido(data.falta) ? data.falta : Math.max(0, data.valor_alvo - guardado));
    return (
      eyebrow(ICONES.meta, data.consulta ? "Meta" : "Meta criada") +
      `<p class="card-titulo">${esc(data.titulo)}</p>` +
      `<p class="card-meta-valores">${valores}</p>` +
      `<div class="meta-progresso" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(pct)}">` +
      `<div class="meta-progresso-barra${pct >= 100 ? " completa" : ""}" style="width:${pct.toFixed(1)}%"></div></div>` +
      `<p class="card-linha-meta"><strong>${Math.round(pct)}%</strong> da meta · faltam ${esc(falta)}</p>` +
      `<p class="card-linha-meta">${esc(dataPlanejada(data.prazo))}</p>`
    );
  });

  // ---- resumo_final -----------------------------------------------------------

  Cards.registrar("resumo_final", (data, card, ctx) => {
    const linhas = lista(data.linhas)
      .filter((l) => l && typeof l === "object")
      .map(
        (l) =>
          `<li><span class="card-seta" aria-hidden="true">→</span><span><strong>${esc(l.modulo)}:</strong> ${esc(l.texto)}</span></li>`
      )
      .join("");
    const passos = lista(ctx && ctx.passos).filter((p) => p && typeof p === "object");
    const total = numeroValido(data.passos_total) ? data.passos_total : passos.length;
    const modulos = lista(data.modulos).map(String);
    const resumoPassos = [`${total} ${total === 1 ? "passo" : "passos"}`, segundos(data.duracao_ms), modulos.join(", ")]
      .filter(Boolean)
      .map(esc)
      .join(" · ");
    const itensPassos = passos
      .map(
        (p) =>
          `<li${p.erro ? ' class="erro"' : ""}><span class="card-passo-modulo">${esc(p.modulo)}</span>` +
          `<span class="card-passo-desc">${esc(p.descricao)}</span>` +
          `<span class="card-passo-ms">${esc(Number(p.ms) || 0)} ms</span></li>`
      )
      .join("");
    const detalhe = itensPassos
      ? `<details class="card-passos"><summary>${resumoPassos}</summary><ol>${itensPassos}</ol></details>`
      : `<p class="card-passos-resumo">${resumoPassos}</p>`;
    return eyebrow(ICONES.resumo, "Resumo") + `<ul class="card-resumo-linhas">${linhas}</ul>` + detalhe;
  });

  Cards.ICONES = ICONES;
  Cards.segundos = segundos;
})(typeof window !== "undefined" ? window : globalThis);

// ---- cards de visual complexo (US-E4) ---------------------------------------
// Renderizadores prontos contra o formato de docs/CARDS.md; o dado real de
// agenda (US-E14), projeto/viagem (US-E13), habito (US-E12) e o "porque" da
// sugestao (US-E10) e ligado por outras faixas (US-E7b).
(function (raiz) {
  "use strict";
  const Cards = raiz.Cards || (typeof require === "function" ? require("./cards.js") : null);
  if (!Cards) return;
  const { esc, numeroValido, moeda } = Cards;

  const ICONES = Object.assign(Cards.ICONES || {}, {
    assinatura:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 21v-5h5"/></svg>',
    parcela:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2.5" y="7.5" width="16" height="11" rx="2"/><rect x="5.5" y="4.5" width="16" height="11" rx="2"/><path d="M9 10h4"/></svg>',
    agenda:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 9.5h17M8 3v4M16 3v4"/></svg>',
    projeto:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 21V4M5 4h11l-2 4 2 4H5"/></svg>',
    viagem:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m14.8 9.2-1.6 4-4 1.6 1.6-4 4-1.6Z"/></svg>',
    treino:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12h4l3-7 4 14 3-7h4"/></svg>',
    sugestao:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg>',
    habito:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M17 2.5 20.5 6 17 9.5"/><path d="M3.5 11V9.5A3.5 3.5 0 0 1 7 6h13.5M7 21.5 3.5 18 7 14.5"/><path d="M20.5 13v1.5A3.5 3.5 0 0 1 17 18H3.5"/></svg>',
    check:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5 10 17 19 7"/></svg>',
    rota:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="6" cy="19" r="2.2"/><circle cx="18" cy="5" r="2.2"/><path d="M8.2 19H15a3.5 3.5 0 0 0 0-7H9a3.5 3.5 0 0 1 0-7h6.8"/></svg>',
    bandeira:
      '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" aria-hidden="true"><path d="M5 21V4" fill="none"/><path d="M5 4h11l-2 4 2 4H5z"/></svg>',
  });

  function eyebrow(icone, texto, extra) {
    return `<div class="card-resultado-eyebrow">${icone || ""}<span>${esc(texto)}</span>${extra || ""}</div>`;
  }

  function lista(v) {
    return Array.isArray(v) ? v : [];
  }

  function limitar(n, min, max) {
    return Math.max(min, Math.min(max, n));
  }

  // "08:00" -> "8h", "08:30" -> "8h30"
  function horaCurta(hhmmTxt) {
    const m = typeof hhmmTxt === "string" ? hhmmTxt.match(/^(\d{1,2}):(\d{2})/) : null;
    if (!m) return "";
    const h = Number(m[1]);
    return m[2] === "00" ? `${h}h` : `${h}h${m[2]}`;
  }

  // ---- agenda -----------------------------------------------------------------

  const DIA_INICIO_H = 6;
  const DIA_FIM_H = 22;

  // Posicao do bloco na barra do dia (06h-22h), em % - cortado nas bordas.
  function blocoDoDia(inicio, fim) {
    if (!(inicio instanceof Date)) return null;
    const fimReal = fim instanceof Date && fim > inicio ? fim : new Date(inicio.getTime() + 60 * 60000);
    const total = (DIA_FIM_H - DIA_INICIO_H) * 60;
    const minDoDia = (d, base) =>
      Cards.mesmoDia(d, base) ? d.getHours() * 60 + d.getMinutes() : d > base ? 24 * 60 : 0;
    const ini = limitar(minDoDia(inicio, inicio) - DIA_INICIO_H * 60, 0, total);
    const fi = limitar(minDoDia(fimReal, inicio) - DIA_INICIO_H * 60, 0, total);
    const left = (ini / total) * 100;
    const width = Math.max(1.5, ((fi - ini) / total) * 100);
    return { left: Math.min(left, 100 - width), width, minutos: Math.round((fimReal - inicio) / 60000) };
  }

  function barraDoDia(inicio, fim, rotulo) {
    const b = blocoDoDia(inicio, fim);
    if (!b) return "";
    const marcas = [6, 10, 14, 18, 22]
      .map((h) => {
        const pos = ((h - DIA_INICIO_H) / (DIA_FIM_H - DIA_INICIO_H)) * 100;
        return `<span class="card-dia-marca" style="left:${pos.toFixed(2)}%">${String(h).padStart(2, "0")}h</span>`;
      })
      .join("");
    return (
      `<div class="card-dia" role="img" aria-label="${esc(rotulo)}">` +
      `<div class="card-dia-trilho"><div class="card-dia-bloco" style="left:${b.left.toFixed(2)}%;width:${b.width.toFixed(2)}%"></div></div>` +
      `<div class="card-dia-escala">${marcas}</div></div>`
    );
  }

  Cards.registrar(
    "agenda",
    (data, card) => {
      const inicio = Cards.parseDataHora(data.inicio);
      const fimInformado = Cards.parseDataHora(data.fim);
      const fim = fimInformado && inicio && fimInformado > inicio ? fimInformado : inicio ? new Date(inicio.getTime() + 3600000) : null;
      const quando = inicio
        ? `${Cards.dataPorExtenso(inicio)}, das ${Cards.hhmm(inicio)} às ${Cards.hhmm(fim)}`
        : "Horário a definir";
      const minutos = inicio ? Math.round((fim - inicio) / 60000) : 0;
      const lembrar = numeroValido(data.lembrar_min_antes) && data.lembrar_min_antes > 0
        ? `<span class="card-chip">${ICONES.sugestao}Lembrar ${esc(data.lembrar_min_antes)} min antes</span>`
        : "";
      const desfazer = Cards.acoesDoTipo(card, "desfazer").map(Cards.acaoHTML).join("");
      const confirmacao = data.confirmado
        ? `<p class="card-confirmacao">${ICONES.check}<span>Está na sua agenda</span>${desfazer ? `<span class="card-sep" aria-hidden="true">·</span>${desfazer}` : ""}</p>`
        : desfazer
          ? `<div class="card-botoes">${desfazer}</div>`
          : "";
      return (
        eyebrow(ICONES.agenda, data.calendario ? `Agenda · ${data.calendario}` : "Agenda") +
        `<p class="card-titulo">${esc(data.titulo)}</p>` +
        `<p class="card-linha-meta card-primeira-maiuscula">${esc(quando)}</p>` +
        (inicio ? barraDoDia(inicio, fim, quando) : "") +
        (inicio ? `<div class="card-linha-chips"><span class="card-reservado">${esc(Cards.fmtDuracao(minutos))} reservadas</span>${lembrar}</div>` : "") +
        confirmacao
      );
    },
    { consome: ["desfazer"] }
  );

  // ---- projeto_viagem -----------------------------------------------------------

  // % concluido, n/total e posicao de HOJE (0..1) entre inicio e prazo. Usa
  // o que o backend mandar pronto (US-E13) e so calcula o que faltar.
  function progressoProjeto(data, agora) {
    const etapas = lista(data.etapas).filter((e) => e && typeof e === "object");
    const total = numeroValido(data.total) ? data.total : etapas.length;
    const feitas = numeroValido(data.feitas) ? data.feitas : etapas.filter((e) => e.feito).length;
    const pct = numeroValido(data.percentual) ? limitar(data.percentual, 0, 100) : total > 0 ? (feitas / total) * 100 : 0;
    let hoje = numeroValido(data.hoje_fracao) ? limitar(data.hoje_fracao, 0, 1) : null;
    if (hoje === null) {
      const ini = Cards.parseDia(data.inicio);
      const fim = Cards.parseDia(data.prazo);
      const ref = agora instanceof Date ? agora : new Date();
      if (ini && fim && fim > ini) hoje = limitar((ref - ini) / (fim - ini), 0, 1);
    }
    return { pct, feitas, total, hoje };
  }

  const STATUS_PROJETO = {
    no_rumo: "No rumo",
    atrasado: "Atrasado",
    pausado: "Pausado",
  };

  // ---- US-F11: linha do tempo de planejamento (regra pratica) -------------
  // Mini linha do tempo vertical, MESMA classe/marcacao visual da agenda/visao
  // do dia (.linha-do-tempo, style.css) - so acrescenta uma classe .mini pra
  // caber dentro do card sem competir com o card-checklist/progresso acima.
  // So aparece quando o backend mandar `marcos_planejamento` (so viagem tem -
  // projeto generico nunca tem esse campo, entao o bloco inteiro some).
  function linhaDoTempoPlanejamentoHTML(marcos, aviso, agora) {
    const lista = Array.isArray(marcos)
      ? marcos.filter((m) => m && typeof m === "object" && m.titulo && typeof m.data === "string")
      : [];
    if (!lista.length) return "";
    const ref = agora instanceof Date ? agora : new Date();
    const hojeIso = `${ref.getFullYear()}-${String(ref.getMonth() + 1).padStart(2, "0")}-${String(ref.getDate()).padStart(2, "0")}`;
    const ordenados = lista.slice().sort((a, b) => (a.data < b.data ? -1 : a.data > b.data ? 1 : 0));
    let hojeInserido = false;
    const itensHtml = [];
    ordenados.forEach((m) => {
      if (!hojeInserido && hojeIso <= m.data) {
        itensHtml.push(`<li class="item hoje-marcador" aria-current="date"><span class="item-titulo">HOJE</span></li>`);
        hojeInserido = true;
      }
      const passado = m.data < hojeIso;
      itensHtml.push(
        `<li class="item${passado ? " passado" : " proximo"}">` +
          `<span class="item-titulo">${esc(m.titulo)}</span>` +
          `<span class="card-linha-meta">${esc(Cards.diaMesCurto(m.data))}</span></li>`
      );
    });
    if (!hojeInserido) {
      itensHtml.push(`<li class="item hoje-marcador" aria-current="date"><span class="item-titulo">HOJE</span></li>`);
    }
    return (
      `<div class="card-marcos-planejamento">` +
      `<p class="card-linha-meta card-marcos-aviso">${ICONES.sugestao || ""}<span>${esc(aviso || "Regra prática, não é preço em tempo real.")}</span></p>` +
      `<ul class="linha-do-tempo mini">${itensHtml.join("")}</ul>` +
      `</div>`
    );
  }

  Cards.registrar("projeto_viagem", (data, card, ctx) => {
    const etapas = lista(data.etapas).filter((e) => e && typeof e === "object");
    const p = progressoProjeto(data, ctx && ctx.agora);
    const statusTxt = STATUS_PROJETO[data.status];
    const chip = statusTxt ? `<span class="card-chip card-status-${esc(data.status)}">${esc(statusTxt)}</span>` : "";
    const visiveis = etapas.slice(0, 5);
    const itens = visiveis
      .map(
        (e) =>
          `<li class="${e.feito ? "feito" : ""}"><span class="card-check" aria-hidden="true">${e.feito ? ICONES.check : ""}</span>` +
          `<span class="card-check-titulo">${esc(e.titulo)}</span>${e.data ? `<span class="card-check-data">${esc(Cards.diaMesCurto(e.data))}</span>` : ""}` +
          `<span class="sr-only">${e.feito ? "feito" : "pendente"}</span></li>`
      )
      .join("");
    const resto = etapas.length > visiveis.length ? `<li class="card-check-mais">+${etapas.length - visiveis.length} etapas</li>` : "";
    const marcador =
      p.hoje !== null
        ? `<span class="card-hoje${p.hoje < 0.08 ? " na-borda-inicio" : p.hoje > 0.92 ? " na-borda-fim" : ""}" style="left:${(p.hoje * 100).toFixed(2)}%"><span>HOJE</span></span>`
        : "";
    // sem nenhuma etapa (ex: viagem sem checklist de mala ainda) "0% · 0/0"
    // nao diz nada - mostra so que falta o checklist + o prazo
    const linha = [
      p.total > 0 ? `<strong>${Math.round(p.pct)}%</strong>` : "Sem checklist ainda",
      p.total > 0 ? `${esc(p.feitas)}/${esc(p.total)} ${p.total === 1 ? "tarefa" : "tarefas"}` : "",
      data.prazo ? esc(Cards.diaMesCurto(data.prazo)) : "",
    ]
      .filter(Boolean)
      .join(" · ");
    const marco = data.proximo_marco && typeof data.proximo_marco === "object" && data.proximo_marco.titulo
      ? `<p class="card-marco">${ICONES.bandeira}<span>Próximo marco: <strong>${esc(data.proximo_marco.titulo)}</strong>${data.proximo_marco.data ? ` · ${esc(Cards.diaMesCurto(data.proximo_marco.data))}` : ""}</span></p>`
      : "";
    return (
      eyebrow(data.origem === "viagem" ? ICONES.viagem : ICONES.projeto, data.origem === "viagem" ? "Viagem" : "Projeto", chip) +
      `<p class="card-titulo">${esc(data.titulo)}</p>` +
      (itens ? `<ul class="card-checklist">${itens}${resto}</ul>` : "") +
      `<div class="card-progresso${marcador ? " com-hoje" : ""}">${marcador}<div class="meta-progresso" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(p.pct)}">` +
      `<div class="meta-progresso-barra${p.pct >= 100 ? " completa" : ""}" style="width:${p.pct.toFixed(1)}%"></div></div></div>` +
      `<p class="card-linha-meta">${linha}</p>` +
      marco +
      linhaDoTempoPlanejamentoHTML(data.marcos_planejamento, data.aviso_regra_pratica, ctx && ctx.agora)
    );
  });

  // ---- saude_treino -------------------------------------------------------------

  function minutosPorAtividade(sessoes) {
    const mapa = new Map();
    sessoes.forEach((s) => {
      const nome = String(s.atividade || "Atividade");
      mapa.set(nome, (mapa.get(nome) || 0) + Math.max(0, Number(s.minutos) || 0));
    });
    return Array.from(mapa, ([atividade, minutos]) => ({ atividade, minutos })).sort((a, b) => b.minutos - a.minutos);
  }

  // Barras horizontais (rotulo a esquerda, valor direto na ponta - sem
  // legenda nem eixo), SVG inline, uma cor so (a do card).
  function graficoBarras(grupos) {
    if (!grupos.length) return "";
    const max = Math.max(...grupos.map((g) => g.minutos), 1);
    const alturaLinha = 26;
    const largura = 300;
    const xBarra = 92;
    const larguraMax = largura - xBarra - 52;
    const linhas = grupos
      .map((g, i) => {
        const y = i * alturaLinha;
        const w = Math.max(4, (g.minutos / max) * larguraMax);
        const nome = g.atividade.length > 13 ? `${g.atividade.slice(0, 12)}…` : g.atividade;
        return (
          `<text class="card-graf-rotulo" x="0" y="${y + 16}">${esc(nome)}</text>` +
          `<rect class="card-graf-barra" x="${xBarra}" y="${y + 6}" width="${w.toFixed(1)}" height="12" rx="6"/>` +
          `<text class="card-graf-valor" x="${(xBarra + w + 6).toFixed(1)}" y="${y + 16}">${esc(Cards.fmtDuracao(g.minutos))}</text>`
        );
      })
      .join("");
    const titulo = grupos.map((g) => `${g.atividade}: ${Cards.fmtDuracao(g.minutos)}`).join(", ");
    return `<svg class="card-grafico" viewBox="0 0 ${largura} ${grupos.length * alturaLinha}" role="img" aria-label="${esc(`Minutos por atividade - ${titulo}`)}">${linhas}</svg>`;
  }

  // Modo visitante (revisao da Fase 6): o servidor tira `sessoes` e manda
  // `oculto: true` - o card so diz que o dado esta escondido.
  const TEXTO_SAUDE_OCULTA = "Dados de saúde ocultos no modo visitante.";

  Cards.registrar("saude_treino", (data) => {
    if (data.oculto) {
      return eyebrow(ICONES.treino, "Treinos") + `<p class="card-linha-meta">${esc(TEXTO_SAUDE_OCULTA)}</p>`;
    }
    const sessoes = lista(data.sessoes).filter((s) => s && typeof s === "object");
    const totalMin = sessoes.reduce((acc, s) => acc + Math.max(0, Number(s.minutos) || 0), 0);
    const chip = data.registrado ? `<span class="card-chip">${ICONES.check}Registrado</span>` : "";
    const itens = sessoes
      .slice(0, 6)
      .map(
        (s) =>
          `<li><span class="card-sessao-nome">${esc(s.atividade || "Atividade")}</span>` +
          `<span class="card-sessao-fonte">${esc([s.fonte, s.data ? Cards.dataCurta(s.data) : ""].filter(Boolean).join(" · "))}</span>` +
          `<span class="card-sessao-dur">${esc(Cards.fmtDuracao(s.minutos))}</span></li>`
      )
      .join("");
    // Cartao vivo (2026-10-09): aneis seg..dom que se fecham nos dias treinados
    const semana = lista(data.semana).filter((d) => d && typeof d === "object").slice(0, 7);
    const RA = 15, CA = +(2 * Math.PI * RA).toFixed(2);
    const feitosSemana = semana.filter((d) => d.feito).length;
    const aneis = semana.length === 7
      ? `<div class="vivo-semana" aria-label="${feitosSemana} dias com treino nesta semana">` +
        semana
          .map(
            (d, i) =>
              `<div class="vivo-semana-dia${d.hoje ? " hoje" : ""}"><svg viewBox="0 0 40 40" aria-hidden="true">` +
              `<circle cx="20" cy="20" r="${RA}" class="vivo-semana-fundo"/>` +
              `<circle cx="20" cy="20" r="${RA}" class="vivo-semana-anel" data-feito="${d.feito ? 1 : 0}" data-c="${CA}" transform="rotate(-90 20 20)" stroke-dasharray="${CA}" stroke-dashoffset="${d.feito ? 0 : CA}"/>` +
              (d.feito ? `<path d="M14 20.5l4 4 8-9" class="vivo-semana-check"/>` : "") +
              `</svg><small>${["S", "T", "Q", "Q", "S", "S", "D"][i]}</small></div>`
          )
          .join("") +
        `</div>` +
        `<p class="card-linha-meta">Nesta semana: <strong>${feitosSemana}</strong>${numeroValido(data.meta_semana) ? ` de ${esc(data.meta_semana)}` : ""} ${feitosSemana === 1 ? "dia" : "dias"} com treino</p>`
      : "";
    return (
      eyebrow(ICONES.treino, "Treinos", chip) +
      aneis +
      (data.periodo ? `<p class="card-titulo card-primeira-maiuscula">${esc(data.periodo)}</p>` : "") +
      `<p class="card-linha-meta">Sessões registradas: <strong>${sessoes.length}</strong> · Tempo de atividade: <strong>${esc(Cards.fmtDuracao(totalMin))}</strong></p>` +
      (itens ? `<ul class="card-sessoes">${itens}</ul>` : "") +
      graficoBarras(minutosPorAtividade(sessoes))
    );
  });

  // ---- sugestao -----------------------------------------------------------------

  Cards.registrar("sugestao", (data) => {
    const inicio = Cards.parseDataHora(data.inicio);
    const dur = numeroValido(data.duracao_min) && data.duracao_min > 0 ? data.duracao_min : null;
    const fim = inicio && dur ? new Date(inicio.getTime() + dur * 60000) : null;
    const linha = [
      inicio ? Cards.dataPorExtenso(inicio) : "",
      dur ? `${Cards.fmtDuracao(dur)}${fim ? ` (até ${Cards.hhmm(fim)})` : ""}` : "",
    ]
      .filter(Boolean)
      .map(esc)
      .join(" · ");
    const porque = data.porque
      ? `<div class="card-contexto"><p class="card-contexto-rotulo">Com a sua rotina em mente</p><p>${esc(data.porque)}</p></div>`
      : "";
    return (
      eyebrow(ICONES.sugestao, "Horário sugerido") +
      `<p class="card-titulo">${esc(data.titulo)}</p>` +
      `<p class="card-hora-grande">${esc(inicio ? Cards.hhmm(inicio) : "—")}</p>` +
      (linha ? `<p class="card-linha-meta card-primeira-maiuscula">${linha}</p>` : "") +
      porque
    );
  });

  // ---- rota (estimar_trajeto -> botao do Google Maps) ---------------------------

  function kmTexto(km) {
    if (!numeroValido(km)) return "";
    return `${Number(km).toLocaleString("pt-BR", { maximumFractionDigits: km < 10 ? 1 : 0 })} km`;
  }

  Cards.registrar("rota", (data) => {
    const paradas = lista(data.paradas).filter((p) => p && typeof p === "object");
    if (paradas.length < 2) return null;
    const destino = paradas[paradas.length - 1];
    const voltaPraOrigem = paradas.length > 2 && paradas[0].endereco === destino.endereco;
    const alvo = voltaPraOrigem ? paradas[paradas.length - 2] : destino;
    const numeros = [kmTexto(data.distancia_km), numeroValido(data.duracao_min) ? Cards.fmtDuracao(data.duracao_min) : ""]
      .filter(Boolean)
      .join(" · ");
    // 2026-10-15: quanto do tempo e transito + trecho lento/parado ("pode ser acidente ou blitz")
    const transito =
      numeroValido(data.transito_min) && data.transito_min >= 3
        ? `<p class="card-rota-transito">+${esc(data.transito_min)} min de trânsito</p>`
        : "";
    const lentos = lista(data.lentidao)
      .filter((x) => x && (x.nivel === "parado" || x.nivel === "lento") && typeof x.frase === "string")
      .slice(0, 3)
      .map((x) => `<li class="card-rota-lento card-rota-lento--${x.nivel}"><i aria-hidden="true"></i>${esc(x.frase)}</li>`)
      .join("");
    const itens = paradas
      .map((p, i) => {
        const aqui = i === 0 && data.partir_de_onde_estou;
        const nome = aqui ? "Onde você está" : p.nome || p.endereco;
        // "Onde você está": com GPS o servidor manda o endereco aproximado; sem GPS manda vazio
        const endereco = p.endereco && p.endereco !== nome ? `<span class="card-rota-endereco">${esc(p.endereco)}</span>` : "";
        return `<li class="card-rota-parada"><span class="card-rota-nome">${esc(nome)}</span>${endereco}</li>`;
      })
      .join("");
    return (
      eyebrow(ICONES.rota, voltaPraOrigem ? "Rota · ida e volta" : "Rota") +
      `<p class="card-titulo">${esc(alvo.nome || alvo.endereco)}</p>` +
      mapaRota(data.traco, paradas.map((p, i) => (i === 0 && data.partir_de_onde_estou ? "Você" : p.nome || p.endereco))) +
      (numeros ? `<p class="card-hora-grande card-rota-numeros">${esc(numeros)}</p>` : "") +
      transito +
      (lentos ? `<ul class="card-rota-lentos">${lentos}</ul>` : "") +
      tempoRota(data.tempo) +
      `<ol class="card-rota-paradas">${itens}</ol>`
    );
  });

  // 2026-10-21: tempo ao longo do caminho (clima_rota.py) - barra do km 0 ao fim com cada trecho
  // pintado (chuva listrada, neblina enevoada...) e embaixo so os trechos que nao sao tempo firme.
  const TIPOS_TEMPO = ["granizo", "trovoada", "neblina", "chuva_forte", "chuva", "vento", "ok"];
  function tempoRota(t) {
    if (!t || typeof t !== "object" || !numeroValido(t.total_km) || t.total_km <= 0) return "";
    const trechos = lista(t.trechos).filter(
      (x) => x && TIPOS_TEMPO.includes(x.tipo) && numeroValido(x.de_km) && numeroValido(x.ate_km),
    );
    if (!trechos.length) return "";
    const pct = (km) => Math.max(0, Math.min(100, (km / t.total_km) * 100)).toFixed(2);
    const faixas = trechos
      .filter((x) => x.tipo !== "ok")
      .map(
        (x, i) =>
          `<i class="card-rota-tempo-faixa card-rota-tempo--${x.tipo}" style="left:${pct(x.de_km)}%;width:${(pct(x.ate_km) - pct(x.de_km)).toFixed(2)}%;--i:${i}"></i>`,
      )
      .join("");
    const ruins = trechos.filter((x) => x.tipo !== "ok" && typeof x.frase === "string" && x.frase);
    const linhas = ruins.length
      ? ruins
          .slice(0, 4)
          .map((x) => `<li class="card-rota-lento card-rota-tempo-item card-rota-tempo--${x.tipo}"><i aria-hidden="true"></i>${esc(x.frase)}</li>`)
          .join("")
      : `<li class="card-rota-lento card-rota-tempo-item card-rota-tempo--ok"><i aria-hidden="true"></i>Tempo firme no caminho todo.</li>`;
    const saida = typeof t.saida === "string" && t.saida ? ` · saindo ${esc(t.saida)}` : "";
    return (
      `<div class="card-rota-tempo">` +
      `<p class="card-rota-tempo-rotulo">Tempo no caminho${saida}</p>` +
      `<div class="card-rota-tempo-barra" role="img" aria-label="Tempo ao longo da rota">${faixas}</div>` +
      `<div class="card-rota-tempo-km"><span>km 0</span><span>km ${esc(Math.round(t.total_km))}</span></div>` +
      `<ul class="card-rota-lentos">${linhas}</ul>` +
      `</div>`
    );
  }

  function trechosTempo(traco) {
    return lista(traco.tempo)
      .filter((f) => f && TIPOS_TEMPO.includes(f.nivel) && f.nivel !== "ok")
      .map((f) => {
        const pts = lista(f.pontos).filter((p) => Array.isArray(p) && p.length === 2 && p.every(numeroValido));
        if (pts.length < 2) return "";
        return `<path class="vivo-rota-tempo card-rota-tempo--${f.nivel}" d="M${pts.map((p) => `${p[0]} ${p[1]}`).join(" L")}"/>`;
      })
      .join("");
  }

  // Cartao vivo (2026-10-09): o caminho REAL que o Google calculou (servidor ja projeta
  // num quadro 320x200, norte pra cima), desenhado se formando com o carrinho andando
  // (animacao em static/js/cards-vivos.js). Sem `traco` (rota antiga) = sem mapa.
  function mapaRota(traco, nomes) {
    if (!traco || typeof traco !== "object") return "";
    const pts = lista(traco.pontos).filter((p) => Array.isArray(p) && p.length === 2 && p.every(numeroValido));
    const paradas = lista(traco.paradas).filter((p) => Array.isArray(p) && p.length === 2 && p.every(numeroValido));
    if (pts.length < 2 || paradas.length < 2) return "";
    const w = numeroValido(traco.w) ? traco.w : 320;
    const h = numeroValido(traco.h) ? traco.h : 200;
    const d = "M" + pts.map((p) => `${p[0]} ${p[1]}`).join(" L");
    // fracao (aproximada pelo indice) de cada parada ao longo do caminho - o pino acende quando o carro passa
    const frac = (p) => {
      const i = pts.findIndex((q) => q[0] === p[0] && q[1] === p[1]);
      return i < 0 ? 1 : i / (pts.length - 1);
    };
    const vistos = new Set();
    const pinos = paradas
      .map((p, i) => {
        const chave = `${p[0]},${p[1]}`;
        if (vistos.has(chave)) return "";
        vistos.add(chave);
        const ultimo = i === paradas.length - 1 || (i > 0 && i === paradas.length - 2);
        const nome = String((nomes && nomes[i]) || "").split(",")[0].slice(0, 24);
        // rotulo pro lado que tem mais espaco no quadro
        const aDireita = p[0] < w * 0.62;
        return (
          `<g class="vivo-rota-pino" data-frac="${(i === 0 ? 0 : frac(p)).toFixed(3)}" transform="translate(${p[0]} ${p[1]})">` +
          (i === 0 ? `<circle r="6" class="vivo-pino-origem"/>` : `<circle r="12" class="vivo-pino-halo"/><circle r="6" class="vivo-pino-destino"${ultimo ? "" : ""}/>`) +
          (nome ? `<text class="vivo-pino-nome" x="${aDireita ? 12 : -12}" y="4" text-anchor="${aDireita ? "start" : "end"}">${esc(nome)}</text>` : "") +
          `</g>`
        );
      })
      .join("");
    return (
      `<div class="vivo-mapa"><svg class="vivo-rota-mapa" viewBox="0 0 ${w} ${h}" role="img" aria-label="Caminho da rota">` +
      `<defs><pattern id="vivo-grade-mapa" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" class="vivo-grade-linha"/></pattern></defs>` +
      `<rect width="${w}" height="${h}" fill="url(#vivo-grade-mapa)"/>` +
      `<path class="vivo-rota-sombra" d="${d}"/><path class="vivo-rota-caminho" d="${d}"/>${trechosTempo(traco)}${trechosLentos(traco)}${pinos}` +
      `<g class="vivo-rota-carro"><circle r="9" class="vivo-carro-halo"/><circle r="4.5" class="vivo-carro"/></g></svg></div>`
    );
  }

  // Trecho lento/parado (2026-10-15): pintado por cima do caminho, ambar (lento) ou vermelho
  // (parado). Aparece depois que o caminho termina de se desenhar (CSS).
  function trechosLentos(traco) {
    return lista(traco.lentos)
      .filter((f) => f && (f.nivel === "parado" || f.nivel === "lento"))
      .map((f) => {
        const pts = lista(f.pontos).filter((p) => Array.isArray(p) && p.length === 2 && p.every(numeroValido));
        if (pts.length < 2) return "";
        return `<path class="vivo-rota-lento vivo-rota-lento--${f.nivel}" d="M${pts.map((p) => `${p[0]} ${p[1]}`).join(" L")}"/>`;
      })
      .join("");
  }

  // ---- habito -------------------------------------------------------------------

  const LETRAS_SEMANA = ["S", "T", "Q", "Q", "S", "S", "D"];
  const NOMES_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"];

  // Sempre 7 posicoes (segunda..domingo): completa com "nao feito" se o
  // backend mandar menos, e marca hoje por data.hoje (ou pelo relogio).
  function semanaHabito(data, agora) {
    const semana = lista(data.semana).slice(0, 7);
    const ref = agora instanceof Date ? agora : new Date();
    const hojeIso = typeof data.hoje === "string" ? data.hoje : null;
    const idxHojeRelogio = (ref.getDay() + 6) % 7;
    return LETRAS_SEMANA.map((letra, i) => {
      const dia = semana[i] && typeof semana[i] === "object" ? semana[i] : {};
      const ehHoje = hojeIso ? dia.data === hojeIso : i === idxHojeRelogio;
      return { letra, nome: NOMES_SEMANA[i], feito: Boolean(dia.feito), hoje: ehHoje, data: dia.data || null };
    });
  }

  Cards.registrar("habito", (data, card, ctx) => {
    const dias = semanaHabito(data, ctx && ctx.agora);
    const meta = [data.meta, data.frequencia, data.horario ? `às ${horaCurta(data.horario)}` : ""]
      .filter(Boolean)
      .map(esc)
      .join(" · ");
    const circulos = dias
      .map(
        (d) =>
          `<li class="card-habito-dia${d.feito ? " feito" : ""}${d.hoje ? " hoje" : ""}" aria-label="${esc(`${d.nome}${d.hoje ? " (hoje)" : ""}: ${d.feito ? "feito" : "não feito"}`)}">` +
          `<span class="card-habito-circ">${d.feito ? ICONES.check : ""}</span><span class="card-habito-letra" aria-hidden="true">${d.letra}</span></li>`
      )
      .join("");
    const ativos =
      numeroValido(data.ativos_depois)
        ? `<p class="card-linha-meta">Hábitos ativos: ${numeroValido(data.ativos_antes) ? `${esc(data.ativos_antes)} <span class="card-seta" aria-hidden="true">→</span> ` : ""}<strong>${esc(data.ativos_depois)}</strong></p>`
        : "";
    const contexto = data.contexto
      ? `<div class="card-contexto"><p>${esc(data.contexto)}</p></div>`
      : "";
    return (
      eyebrow(ICONES.habito, "Hábito") +
      `<p class="card-titulo">${esc(data.nome)}</p>` +
      (meta ? `<p class="card-linha-meta">${meta}</p>` : "") +
      `<ul class="card-habito-semana">${circulos}</ul>` +
      ativos +
      contexto
    );
  });

  // ---- saude_dia (US-E7, aditivo) -------------------------------------------
  // Copos de agua do dia em destaque + passos/sono/treino quando existirem.
  // Os copos viram uma fileira de gotas (ate 8 acesas; alem disso, "+N").

  const GOTA =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3.5c3.2 4 5.5 7.2 5.5 10.3a5.5 5.5 0 0 1-11 0C6.5 10.7 8.8 7.5 12 3.5Z"/></svg>';
  ICONES.agua = GOTA;

  const COPOS_VISIVEIS = 8;

  function fmtPassos(n) {
    if (!numeroValido(n) || n < 0) return "";
    if (n >= 1000) return `${(n / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mil passos`;
    return `${Math.round(n)} passos`;
  }

  function fmtSono(h) {
    if (!numeroValido(h) || h <= 0) return "";
    const total = Math.round(h * 60);
    const hh = Math.floor(total / 60);
    const mm = total % 60;
    return `Sono ${hh}h${mm ? String(mm).padStart(2, "0") : ""}`;
  }

  Cards.registrar("saude_dia", (data) => {
    if (data.oculto) {
      return eyebrow(ICONES.agua, "Saúde") + `<p class="card-linha-meta">${esc(TEXTO_SAUDE_OCULTA)}</p>`;
    }
    const copos = numeroValido(data.agua_copos) && data.agua_copos > 0 ? Math.floor(data.agua_copos) : 0;
    const chip = data.registrado ? `<span class="card-chip">${ICONES.check}Registrado</span>` : "";
    const gotas = Array.from({ length: COPOS_VISIVEIS }, (_, i) =>
      `<li class="card-gota${i < copos ? " cheia" : ""}${data.registrado === "agua" && i === copos - 1 ? " nova" : ""}">${GOTA}</li>`
    ).join("");
    const extra = copos > COPOS_VISIVEIS ? `<li class="card-gota-mais">+${copos - COPOS_VISIVEIS}</li>` : "";
    const chips = [
      fmtPassos(data.passos),
      fmtSono(data.sono_horas),
      numeroValido(data.treino_min) && data.treino_min > 0 ? `Treino ${Cards.fmtDuracao(data.treino_min)}` : "",
    ]
      .filter(Boolean)
      .map((t) => `<span class="card-chip card-chip-neutro">${esc(t)}</span>`)
      .join("");
    const dia = Cards.parseDia(data.data);
    const titulo = dia && !Cards.mesmoDia(dia, new Date()) ? `Saúde · ${Cards.dataCurta(data.data)}` : "Saúde hoje";
    return (
      eyebrow(ICONES.agua, titulo, chip) +
      `<div class="card-saude-agua"><span class="card-hora-grande">${esc(copos)}</span>` +
      `<span class="card-linha-meta">${copos === 1 ? "copo de água" : "copos de água"}</span></div>` +
      `<ul class="card-gotas" aria-label="${esc(`${copos} ${copos === 1 ? "copo" : "copos"} de água`)}">${gotas}${extra}</ul>` +
      (chips ? `<div class="card-linha-chips">${chips}</div>` : "")
    );
  });

  // ---- assinatura / compra_parcelada / resumo_financeiro_recorrente ---------
  // C2: alinhado ao contrato publicado pela N1 (docs/contrato-assinaturas.md, secao
  // "Cards"). A V1 tinha escrito contra um formato provisorio; os nomes antigos continuam
  // aceitos so como reserva (contrato e "so aditivo", mas o card nao pode quebrar se um
  // dado velho aparecer): cartao -> cartao_ou_forma, restantes -> parcelas_restantes,
  // termina_em -> mes_termino, total_mes -> total_mensal, n_assinaturas ->
  // n_assinaturas_ativas, n_parcelas -> n_compras_em_andamento, proxima_cobranca ->
  // proximas_cobrancas[].
  // Valor: o renderizador nao usa MOEDA_OCULTA (decisao da V1: "sao do proprio Alex"). O
  // contrato marca os campos de dinheiro como sensiveis - quando cards.py os puser em
  // CAMPOS_SENSIVEIS, o SERVIDOR tira o valor no modo visitante e o card mostra "—".

  function emDiasTexto(n) {
    if (!numeroValido(n)) return "";
    if (n <= 0) return "hoje";
    if (n === 1) return "amanhã";
    return `em ${n} dias`;
  }

  // dias ate uma data ISO (a partir de hoje, pelo relogio do aparelho); null se invalida
  function diasAte(iso, agora) {
    const d = Cards.parseDia(iso);
    if (!d) return null;
    return Cards.diasEntre(agora instanceof Date ? agora : new Date(), d);
  }

  // "2027-08" -> "ago 2027" (mes_termino do contrato)
  function mesCurto(anoMes) {
    if (typeof anoMes !== "string") return "";
    const m = anoMes.match(/^(\d{4})-(\d{2})$/);
    if (!m) return Cards.diaMesCurto(anoMes); // reserva: data ISO completa (formato antigo)
    const dia = Cards.diaMesCurto(`${m[1]}-${m[2]}-01`);
    return dia ? `${dia.split(" ")[1]} ${m[1]}` : "";
  }

  function primeiroNumero(...valores) {
    for (const v of valores) if (numeroValido(v)) return v;
    return null;
  }

  function textoOuVazio(v) {
    return typeof v === "string" ? v : "";
  }

  Cards.registrar("assinatura", (data, card, ctx) => {
    const cancelada = data.ativa === false || Boolean(data.cancelada_em);
    const chip = cancelada
      ? `<span class="card-chip card-chip-neutro">${
          data.cancelada_em ? `Cancelada em ${esc(Cards.diaMesCurto(data.cancelada_em))}` : "Cancelada"
        }</span>`
      : "";
    const detalhe = [
      numeroValido(data.dia_cobranca) ? `todo dia ${data.dia_cobranca}` : "",
      textoOuVazio(data.cartao_ou_forma) || textoOuVazio(data.cartao),
      textoOuVazio(data.categoria),
    ]
      .filter(Boolean)
      .map(esc)
      .join(" · ");
    const prox = !cancelada && typeof data.proxima_cobranca === "string" ? data.proxima_cobranca : "";
    const dias = primeiroNumero(data.em_dias, prox ? diasAte(prox, ctx && ctx.agora) : null);
    const proxLinha = [prox ? `Próxima cobrança: ${Cards.diaMesCurto(prox)}` : "", prox ? emDiasTexto(dias) : ""]
      .filter(Boolean)
      .join(" · ");
    const valorTxt = numeroValido(data.valor) ? `${moeda(data.valor)} /mês` : "—";
    return (
      eyebrow(ICONES.assinatura, "Assinatura", chip) +
      `<p class="card-titulo">${esc(data.nome)}</p>` +
      `<p class="card-valor-grande">${esc(valorTxt)}</p>` +
      (detalhe ? `<p class="card-linha-meta">${detalhe}</p>` : "") +
      (proxLinha ? `<p class="card-linha-meta">${esc(proxLinha)}</p>` : "")
    );
  });

  Cards.registrar("compra_parcelada", (data) => {
    const atual = numeroValido(data.parcela_atual) ? data.parcela_atual : null;
    const total = numeroValido(data.n_parcelas) ? data.n_parcelas : null;
    const restantes = primeiroNumero(
      data.parcelas_restantes,
      data.restantes,
      atual !== null && total !== null ? Math.max(0, total - atual) : null
    );
    const quitada = data.quitada === true;
    const pct = quitada ? 100 : atual !== null && total ? limitar((atual / total) * 100, 0, 100) : 0;
    const progresso =
      (atual !== null && total) || quitada
        ? `<div class="card-progresso"><div class="meta-progresso" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(pct)}">` +
          `<div class="meta-progresso-barra${pct >= 100 ? " completa" : ""}" style="width:${pct.toFixed(1)}%"></div></div></div>`
        : "";
    const termino = mesCurto(textoOuVazio(data.mes_termino) || textoOuVazio(data.termina_em));
    const detalhe = [
      atual !== null && total !== null ? `Parcela ${atual} de ${total}` : "",
      !quitada && restantes !== null ? `${restantes} ${restantes === 1 ? "restante" : "restantes"}` : "",
      termino ? `${quitada ? "terminou" : "termina"} ${termino}` : "",
      textoOuVazio(data.cartao),
    ]
      .filter(Boolean)
      .map(esc)
      .join(" · ");
    const totalLinha = numeroValido(data.valor_total) ? `Total ${moeda(data.valor_total)}` : "";
    const chip = quitada ? '<span class="card-chip card-chip-neutro">Quitada</span>' : "";
    const valorTxt = numeroValido(data.valor_parcela) ? `${moeda(data.valor_parcela)} /mês` : "—";
    return (
      eyebrow(ICONES.parcela, "Compra parcelada", chip) +
      `<p class="card-titulo">${esc(data.descricao)}</p>` +
      `<p class="card-valor-grande">${esc(valorTxt)}</p>` +
      progresso +
      (detalhe ? `<p class="card-linha-meta">${detalhe}</p>` : "") +
      (totalLinha ? `<p class="card-linha-meta">${esc(totalLinha)}</p>` : "")
    );
  });

  // proximas_cobrancas do contrato (ate 5); aceita o objeto unico provisorio da V1
  function proximasCobrancas(data) {
    if (Array.isArray(data.proximas_cobrancas)) {
      return data.proximas_cobrancas.filter((c) => c && typeof c === "object");
    }
    const unica = data.proxima_cobranca;
    return unica && typeof unica === "object" ? [unica] : [];
  }

  Cards.registrar("resumo_financeiro_recorrente", (data) => {
    const total = primeiroNumero(data.total_mensal, data.total_mes);
    const totalTxt = total !== null ? moeda(total) : "—";
    const nAss = primeiroNumero(data.n_assinaturas_ativas, data.n_assinaturas);
    const nPar = primeiroNumero(data.n_compras_em_andamento, data.n_parcelas);
    const detalhe = [
      nAss !== null
        ? `${nAss} ${nAss === 1 ? "assinatura" : "assinaturas"}` +
          (numeroValido(data.assinaturas_total) ? ` (${moeda(data.assinaturas_total)})` : "")
        : "",
      nPar !== null
        ? `${nPar} ${nPar === 1 ? "parcela ativa" : "parcelas ativas"}` +
          (numeroValido(data.parcelas_total) ? ` (${moeda(data.parcelas_total)})` : "")
        : "",
    ]
      .filter(Boolean)
      .map(esc)
      .join(" · ");
    const itens = proximasCobrancas(data)
      .slice(0, 3)
      .map((c) => {
        const nome = textoOuVazio(c.nome) || textoOuVazio(c.descricao) || "—";
        const quando = [
          typeof c.data === "string" ? Cards.diaMesCurto(c.data) : "",
          textoOuVazio(c.label) || emDiasTexto(c.dias),
        ]
          .filter(Boolean)
          .join(" · ");
        const valor = numeroValido(c.valor) ? moeda(c.valor) : "";
        return (
          `<li class="card-recorrente-item"><strong>${esc(nome)}</strong>` +
          (quando ? `<span class="card-linha-meta">${esc(quando)}</span>` : "") +
          (valor ? `<span class="card-recorrente-valor">${esc(valor)}</span>` : "") +
          "</li>"
        );
      })
      .join("");
    const mes = mesCurto(textoOuVazio(data.mes));
    return (
      eyebrow(ICONES.resumo, mes ? `Recorrentes · ${mes}` : "Recorrentes do mês") +
      `<p class="card-valor-grande">${esc(totalTxt)}</p>` +
      (detalhe ? `<p class="card-linha-meta">${detalhe}</p>` : "") +
      (itens ? `<p class="card-linha-meta">Próximas cobranças</p><ul class="card-recorrentes">${itens}</ul>` : "")
    );
  });

  Object.assign(Cards, { blocoDoDia, progressoProjeto, minutosPorAtividade, semanaHabito, horaCurta, fmtPassos, fmtSono, emDiasTexto, mesCurto, diasAte });
})(typeof window !== "undefined" ? window : globalThis);
