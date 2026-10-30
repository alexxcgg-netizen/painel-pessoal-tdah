// static/js/cards-aviacao-lab.js - Laboratorio v4, Grupo F (Aviacao), 30/10/2026 (docs/briefings/2026-10-30-lab-v4-aviacao.md).
// Seis cards feitos igual as demos aprovadas no Laboratorio: radar_validades (radar de validades), previsao_cheque
// (previsao do cheque), banca (banca por caderno), chair_flying (voo de cadeira), vento_pista (vento na pista) e
// passaporte (passaporte de piloto). Dado vem de aviacao_lab.py; o servidor faz a conta, aqui so desenha.
//
// REGRA FORTE do Alex: termo/regra de aviacao so com fonte conferida. O que nao foi conferido aparece com a marca
// "nao conferido" (pista 18/36 e declinacao de SSBL, validade do CMA, tempo de prova dos cadernos).
// Renderizadores PUROS (estado final); os cliques re-renderizam o miolo (.av-raiz) com o dado que a rota devolve.
// Script classico - ordem de carga em templates/scripts.html (depois de cards-aviacao.js).

(function (raiz) {
  "use strict";

  const Cards = raiz.Cards;
  if (!Cards) return;
  const esc = Cards.esc;
  const lista = (v) => (Array.isArray(v) ? v : []);
  const reduz = () => typeof raiz.matchMedia === "function" && raiz.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

  const ICONE = {
    radar: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><path d="M12 12 18 6"/>',
    rumo: '<path d="M4 20 20 4"/><path d="M13 4h7v7"/><path d="M4 12v8h8"/>',
    caderno: '<path d="M6 3.5h11a1.5 1.5 0 0 1 1.5 1.5v15L16 18.5H6z"/><path d="M9 8h6M9 11.5h6"/>',
    cadeira: '<path d="M7 4v9h10"/><path d="M7 13v7M17 13v7"/><path d="M5 20h14"/>',
    vento: '<path d="M3 9h11a2.5 2.5 0 1 0-2.5-2.5"/><path d="M3 14h15a2.5 2.5 0 1 1-2.5 2.5"/>',
    passaporte: '<rect x="5" y="3.5" width="14" height="17" rx="2"/><circle cx="12" cy="11" r="3.2"/><path d="M8.5 17h7"/>',
    check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  };
  const svg = (nome, larg) =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${larg || 2}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONE[nome] || ""}</svg>`;
  const topo = (ic, nome, quando) =>
    `<div class="cd-topo"><span class="cd-selo">${svg(ic)}${esc(nome)}</span>${quando ? `<span class="cd-quando">${esc(quando)}</span>` : ""}</div>`;
  const virgula = (n, casas) => Number(n).toLocaleString("pt-BR", { minimumFractionDigits: casas || 0, maximumFractionDigits: casas === undefined ? 1 : casas });
  const nbsp = (s) => String(s).replace(/ /g, "&nbsp;");
  const NAO_CONFERIDO = '<span class="av-nc" title="Não conferido numa fonte oficial">não conferido</span>';

  function diasAte(iso, agora) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
    if (!m) return null;
    const a = Date.UTC(+m[1], +m[2] - 1, +m[3]);
    const h = Date.UTC(agora.getFullYear(), agora.getMonth(), agora.getDate());
    return Math.round((a - h) / 86400000);
  }
  const dataBr = (iso) => {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
    return m ? `${m[3]}/${m[2]}/${m[1]}` : "";
  };
  const mesAno = (d) => `${MESES[d.getUTCMonth()]}/${d.getUTCFullYear()}`;
  const somaDias = (iso, n) => {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
    return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]) + n * 86400000);
  };

  async function postar(deps, url, corpo) {
    if (!deps || typeof deps.apiFetch !== "function") return null;
    try {
      return await deps.apiFetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo || {}) });
    } catch (e) {
      return null;
    }
  }
  function estadoDe(cardEl) {
    const r = cardEl && cardEl.querySelector(".av-raiz[data-estado]");
    try {
      return JSON.parse((r && r.dataset.estado) || "{}");
    } catch (e) {
      return {};
    }
  }
  const guardar = (cardEl, est) => {
    const r = cardEl.querySelector(".av-raiz");
    if (r) r.dataset.estado = JSON.stringify(est);
  };
  function trocarRaiz(cardEl, html) {
    const velho = cardEl.querySelector(".av-raiz");
    if (!velho) return null;
    const t = document.createElement("div");
    t.innerHTML = html;
    const novo = t.firstElementChild;
    velho.replaceWith(novo);
    return novo;
  }
  const raizAttr = (tipo, est) => `class="av-raiz av-${tipo}" data-estado="${esc(JSON.stringify(est))}"`;

  // ================================================================ radar_validades
  const posRegua = (d) => (d <= 0 ? 1 : d <= 30 ? 1 + (d / 30) * 32 : d <= 60 ? 33 + ((d - 30) / 30) * 32 : Math.min(98, 65 + ((d - 60) / 400) * 33));
  const tomDe = (n, pendente) => (pendente || n <= 7 ? "perigo" : n <= 30 ? "alerta" : "ok");
  function itemRadar(i, agora, k) {
    const n = i.pendente ? 0 : i.vence ? diasAte(i.vence, agora) : i.dias;
    const dias = n === null || n === undefined ? i.dias : n;
    let detalhe = i.detalhe || "";
    if (!i.pendente && i.vence && i.verbo) {
      detalhe = dias < 0 ? `${i.verbo === "vence" ? "venceu" : "acabou"} em ${dataBr(i.vence)}` : `${i.verbo} ${dataBr(i.vence)}`;
    }
    return Object.assign({}, i, { dias, detalhe, tom: tomDe(dias, i.pendente), k });
  }
  function camposRadar(d) {
    return lista(d.campos)
      .map(
        (c) =>
          `<label class="av-campo"><span class="av-campo-n">${esc(c.nome)}${c.chave === "cma" ? " " + NAO_CONFERIDO : ""}</span>` +
          `<input type="date" class="av-data" data-chave="${esc(c.chave)}" data-orig="${esc(c.valor || "")}" value="${esc(c.valor || "")}" aria-label="${esc(c.nome)}">` +
          `<small>${esc(c.ajuda)}</small></label>`
      )
      .join("");
  }
  function raizRadar(d, agora, aberto) {
    const itens = lista(d.itens).map((i, k) => itemRadar(i, agora, k)).sort((a, b) => (b.pendente ? 1 : 0) - (a.pendente ? 1 : 0) || a.dias - b.dias);
    const vazio = !itens.length;
    const pontos = itens
      .map((i) => `<span class="av-p" style="left:${posRegua(i.pendente ? 0 : i.dias).toFixed(1)}%;--c:var(--av-${i.tom});--k:${i.k}"></span>`)
      .join("");
    const regua =
      `<div class="rv-regua"><div class="rv-faixa"><i class="z1"></i><i class="z2"></i><i class="z3"></i>${pontos}</div>` +
      `<div class="rv-ticks"><span>hoje</span><span>30 d</span><span>60 d</span><span>1 ano+</span></div></div>`;
    const lis = itens
      .map(
        (i) =>
          `<div class="rv-it" data-k="${esc(i.chave)}" style="--k:${i.k}"><span class="rv-dot" style="background:var(--av-${i.tom})"></span>` +
          `<div class="rv-t"><b>${esc(i.nome)}</b><small>${esc(i.detalhe)}</small></div>` +
          (i.pendente
            ? `<button type="button" class="cd-mini" data-acao="av_civ" data-id="${esc(i.voo_id)}">Confirmei</button>`
            : `<span class="rv-d">${i.dias < 0 ? "vencido" : i.dias === 0 ? "hoje" : `${i.dias}&nbsp;d`}</span>`) +
          `</div>`
      )
      .join("");
    const abrir = vazio || aberto;
    return (
      `<div ${raizAttr("radar", Object.assign({}, d, { aberto: !!abrir }))}>` +
      (vazio
        ? `<p class="cd-hero">Nenhuma data ainda.</p><p class="cd-nota">Digita cada data uma vez (a ANAC não tem API pública) e o painel avisa com 60, 30 e 7 dias.</p>`
        : regua + `<div class="rv-lista">${lis}</div>`) +
      `<div class="cd-acoes"><button type="button" class="cd-acao" data-acao="av_datas" aria-expanded="${abrir ? "true" : "false"}">${abrir ? "Fechar as datas" : "Ajustar as datas"}</button></div>` +
      `<div class="av-datas"${abrir ? "" : " hidden"}>${camposRadar(d)}<div class="cd-acoes"><button type="button" class="cd-acao primaria" data-acao="av_prazos_salvar">Salvar datas</button></div></div>` +
      `<p class="cd-pe">${esc(d.fonte ? "Prazos pelo RBAC 61 e pela IS 00-003." : "")} A validade do CMA (RBAC 67) eu não conferi: tu digita a data que está nele.</p></div>`
    );
  }
  Cards.registrar("radar_validades", (data, _c, ctx) => topo("radar", "Radar de validades", "hoje") + raizRadar(data || {}, (ctx && ctx.agora) || new Date(), false));
  Cards.registrarAcao("av_datas", (btn, cardEl) => {
    const est = estadoDe(cardEl);
    const agora = new Date();
    trocarRaiz(cardEl, raizRadar(est, agora, !est.aberto));
  });
  Cards.registrarAcao("av_prazos_salvar", async (btn, cardEl, deps) => {
    if (btn.disabled) return;
    const mudou = Array.from(cardEl.querySelectorAll(".av-data")).filter((i) => (i.value || "") !== (i.dataset.orig || ""));
    if (!mudou.length) return trocarRaiz(cardEl, raizRadar(estadoDe(cardEl), new Date(), false));
    btn.disabled = true;
    let ultimo = null;
    for (const inp of mudou) {
      const r = await postar(deps, "/api/aviacao/prazos", { chave: inp.dataset.chave, data: inp.value || null });
      if (!r || !r.ok) {
        btn.disabled = false;
        return;
      }
      ultimo = r.card;
    }
    if (ultimo) trocarRaiz(cardEl, raizRadar(ultimo, new Date(), false));
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  });
  Cards.registrarAcao("av_civ", async (btn, cardEl, deps) => {
    if (btn.disabled) return;
    btn.disabled = true;
    const r = await postar(deps, `/api/voos/${encodeURIComponent(btn.dataset.id)}/civ`, { confirmada: true });
    if (!r || !r.ok) {
      btn.disabled = false;
      return;
    }
    const linha = btn.closest(".rv-it");
    if (linha) {
      linha.classList.add("feito");
      linha.querySelector("small").textContent = "confirmado no Super App. Conta nas horas.";
      linha.querySelector(".rv-dot").style.background = "var(--av-ok)";
      btn.replaceWith(Object.assign(document.createElement("span"), { className: "rv-d", textContent: "ok" }));
    }
    setTimeout(() => {
      const est = estadoDe(cardEl);
      trocarRaiz(cardEl, raizRadar(Object.assign({}, r.card, { aberto: est.aberto }), new Date(), est.aberto));
    }, reduz() ? 0 : 1100);
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  });

  // ================================================================ previsao_cheque
  const h1 = (n) => virgula(Math.round((Number(n) || 0) * 10) / 10, 1).replace(",0", "") ;
  function textoGrande(d) {
    const g = lista(d.requisitos).find((r) => r.chave === d.gargalo);
    const sem = d.rotulo_sem_gargalo && d.rotulo_sem_gargalo !== d.rotulo_cheque ? ` Sem ${g ? g.nome.toLowerCase() : "ele"}, seria ${d.rotulo_sem_gargalo}.` : "";
    if (d.tudo_fechado) return ["Os requisitos de horas", "fechados", "Confere na CIV e combina o cheque com o instrutor."];
    if (d.sem_ritmo_total) return ["Sem voo nas últimas 4 semanas", "—", "Sem ritmo não dá pra projetar. Registra um voo e a previsão aparece."];
    if (d.gargalo_sem_ritmo && g)
      return ["No teu ritmo, cheque em", "—", `${g.nome}: nenhuma hora nas últimas ${Math.round((d.janela_dias || 28) / 7)} semanas, por isso não tem data.${d.rotulo_sem_gargalo ? ` Sem isso, seria ${d.rotulo_sem_gargalo}.` : ""}`];
    return ["No teu ritmo, cheque em", d.rotulo_cheque || "—", g ? `${g.nome === "Totais" ? "As horas totais são" : `${g.nome} é`} o que segura.${sem}` : ""];
  }
  function linhaReq(r, gargalo) {
    const q = r.fechou ? "ok" : r.rotulo || "—";
    return (
      `<div class="pc-l${gargalo ? " gargalo" : ""}" data-r="${esc(r.chave)}"><span class="pc-n">${esc(r.nome)}</span>` +
      `<div class="pc-trilho"><i style="width:${Math.min(100, ((Number(r.h) || 0) / (Number(r.meta) || 1)) * 100).toFixed(1)}%"></i></div>` +
      `<span class="pc-v">${h1(r.h)}/${esc(r.meta)}&nbsp;h</span><span class="pc-q">${esc(q)}</span></div>`
    );
  }
  function custoBloco(d) {
    if (d.oculto) return "";
    if (d.custo != null && d.valor_hora)
      return (
        `<div class="pc-custo"><span class="cd-nota">Até o cheque, no mínimo ${h1(d.horas_a_voar)}&nbsp;h de voo, na hora de ${nbsp(Cards.moeda(d.valor_hora))}:</span>` +
        `<b class="pc-r">${nbsp(Cards.moeda(d.custo))}</b></div>`
      );
    return (
      `<div class="pc-custo vazio"><span class="cd-nota">Quanto custa a tua hora no aeroclube? Com isso o painel diz quanto falta gastar até o cheque.</span>` +
      `<div class="pc-hora"><input type="number" class="av-num" inputmode="decimal" min="1" step="1" placeholder="R$ por hora" aria-label="Valor da hora de voo"><button type="button" class="cd-mini" data-acao="av_hora">Guardar</button></div></div>`
    );
  }
  function raizCheque(d) {
    const reqs = lista(d.requisitos);
    const [rot, grande, meta] = textoGrande(d);
    const sim = d.simulacao_noturno;
    const ini = sim ? Math.min(3, Math.max(0.5, Math.round((Number(sim.atual_mes) || 0.5) * 2) / 2)) : 0.5;
    return (
      `<div ${raizAttr("cheque", d)}>` +
      `<div class="pc-big"><span class="cd-rot">${esc(rot)}</span><b class="pc-grande">${esc(grande)}</b><span class="cd-nota pc-meta">${esc(meta)}</span></div>` +
      `<div class="pc-gr">${reqs.map((r) => linhaReq(r, r.chave === d.gargalo)).join("")}</div>` +
      (sim
        ? `<div class="pc-sim"><p class="cd-rot">E se eu voar mais à noite?</p><div class="pc-sim-l"><span class="cd-nota">Noturno por mês:</span><output class="pc-out">${virgula(ini, 1)} h</output></div>` +
          `<input type="range" class="av-range" data-sim="cheque" min="0.5" max="3" step="0.5" value="${ini}" aria-label="Horas noturnas por mês"></div>`
        : "") +
      custoBloco(d) +
      `<p class="cd-nota">Ritmo das últimas ${Math.round((d.janela_dias || 28) / 7)} semanas: ${virgula(d.ritmo_mes || 0, 1)} h/mês. ${esc(d.lembrete_navegacao || "")}</p>` +
      `<p class="cd-pe">${esc(d.fonte || "")}</p></div>`
    );
  }
  Cards.registrar("previsao_cheque", (data) => topo("rumo", "Rumo ao cheque", `ritmo: ${virgula((data || {}).ritmo_mes || 0, 1)} h/mês`) + raizCheque(data || {}));
  Cards.registrarAcao("av_hora", async (btn, cardEl, deps) => {
    const inp = cardEl.querySelector(".pc-hora input");
    const v = inp ? Number(String(inp.value).replace(",", ".")) : NaN;
    if (!(v > 0) || btn.disabled) return;
    btn.disabled = true;
    const r = await postar(deps, "/api/aviacao/valor-hora", { valor: v });
    if (!r || !r.ok) {
      btn.disabled = false;
      return;
    }
    trocarRaiz(cardEl, raizCheque(r.card));
  });
  // simulacao do noturno: mesma conta do servidor (dias = falta / (h por mes) * 30,4375, arredondado pra cima)
  function simularCheque(rootEl, v) {
    let est;
    try {
      est = JSON.parse(rootEl.dataset.estado || "{}");
    } catch (e) {
      return;
    }
    const sim = est.simulacao_noturno;
    if (!sim || !(v > 0)) return;
    const dt = somaDias(est.hoje, Math.ceil((sim.falta / v) * (est.dias_mes || 30.4375)));
    const rotNot = mesAno(dt);
    const out = rootEl.querySelector(".pc-out");
    if (out) out.textContent = `${virgula(v, 1)} h`;
    const linha = rootEl.querySelector('.pc-l[data-r="noturno"]');
    let gargalo = true;
    let grande = rotNot;
    let meta = "O noturno é o que segura.";
    if (sim.outras_sem_ritmo) {
      grande = "—";
      meta = "Outro requisito ainda não tem ritmo, por isso não dá data.";
      gargalo = false;
    } else if (sim.outras_max) {
      const om = somaDias(sim.outras_max, 0);
      if (dt <= om) {
        grande = mesAno(om);
        meta = `Com ${virgula(v, 1)} h/mês o noturno deixa de ser o gargalo: fecha em ${rotNot}.`;
        gargalo = false;
      }
    }
    if (linha) {
      linha.querySelector(".pc-q").textContent = rotNot;
      linha.classList.toggle("gargalo", gargalo);
    }
    const g = rootEl.querySelector(".pc-grande");
    if (g && g.textContent !== grande) {
      g.textContent = grande;
      g.classList.remove("troca");
      void g.offsetWidth;
      g.classList.add("troca");
    }
    const m = rootEl.querySelector(".pc-meta");
    if (m) m.textContent = meta;
  }

  // ================================================================ banca
  function textoDetalhe(c) {
    if (!c.ultimos || !c.ultimos.length) return "Nenhum simulado registrado ainda.";
    const u = c.ultimos.map((p) => `${p}%`).join(", ");
    return `Últimos simulados: ${u}. ` + (c.pronto ? "Pronto." : c.risco ? "Abaixo de 70%: prioridade." : "Falta passar de 80% três vezes seguidas.");
  }
  function detalheBanca(d, est) {
    const c = lista(d.cadernos).find((x) => x.sigla === est.sel) || lista(d.cadernos)[0];
    if (!c) return "";
    const tempo = c.tempo_min
      ? `${c.tempo_min} min${c.tempo_conferido ? "" : " (o que tu pôs)"}`
      : `tempo de prova ${NAO_CONFERIDO}`;
    const reg = est.reg
      ? `<div class="bc-reg"><p class="cd-rot">Quantas tu acertou, de ${esc(d.questoes)}?</p><div class="bc-passos">` +
        `<button type="button" class="cd-cad" data-acao="bc_acertos" data-d="-1" aria-label="Menos um acerto">−</button>` +
        `<output class="bc-v">${esc(est.acertos)}/${esc(d.questoes)} · ${Math.round((est.acertos / d.questoes) * 100)}%</output>` +
        `<button type="button" class="cd-cad" data-acao="bc_acertos" data-d="1" aria-label="Mais um acerto">+</button></div>` +
        `<div class="cd-acoes"><button type="button" class="cd-acao primaria" data-acao="bc_registrar">Registrar</button><button type="button" class="cd-acao" data-acao="bc_registro_fechar">Cancelar</button></div></div>`
      : `<div class="cd-acoes"><button type="button" class="cd-acao primaria" data-acao="bc_registro_abrir">Registrar simulado</button>` +
        (c.ultimo_id && est.ultimo === c.ultimo_id ? `<button type="button" class="cd-acao" data-acao="bc_desfazer" data-id="${esc(c.ultimo_id)}">Desfazer o último</button>` : "") +
        `</div>`;
    const tempoEd =
      !c.tempo_conferido && !est.reg
        ? `<div class="bc-tempo"><span class="cd-nota">Tempo de prova deste caderno (min):</span><input type="number" class="av-num" inputmode="numeric" min="1" max="600" value="${esc(c.tempo_min || "")}" aria-label="Minutos de prova"><button type="button" class="cd-mini" data-acao="bc_tempo" data-c="${esc(c.sigla)}">Guardar</button></div>`
        : "";
    return (
      `<div class="bc-det"><b>${esc(c.nome)} · ${tempo}</b><span class="cd-nota">${esc(textoDetalhe(c))}</span>${reg}${tempoEd}` +
      (est.msg ? `<p class="bc-msg" role="status">${esc(est.msg)}</p>` : "") +
      `</div>`
    );
  }
  function revisaoBanca(d, est) {
    const rev = lista(d.revisao);
    const i = Math.min(est.rev || 0, rev.length);
    if (!rev.length)
      return `<p class="cd-rot">Revisão de hoje</p><p class="cd-nota">Nenhuma revisão vencida. O que tu errar no quiz do chat volta amanhã; o que acertar volta em 3, 7, 14 dias.</p>`;
    if (i >= rev.length)
      return `<p class="cd-rot">Revisão de hoje</p><div class="cd-ok">${svg("check", 2.4)}<span>Revisões de hoje feitas.${d.vencidas > rev.length ? ` Ainda tem ${d.vencidas - rev.length} pra outro dia.` : ""}</span></div>`;
    const r = rev[i];
    return (
      `<p class="cd-rot">Revisão de hoje · ${i + 1} de ${rev.length}</p>` +
      `<div class="bc-flip${est.virado ? " virado" : ""}" data-acao="bc_virar" role="button" tabindex="0" aria-label="Virar cartão">` +
      `<div class="bc-face fr"><small>${esc(r.sigla || "QUIZ")}${r.errou_em ? ` · errou dia ${esc(dataBr(r.errou_em).slice(0, 5))}` : ""}</small><p>${esc(r.enunciado)}</p><span class="cd-nota">toca pra ver a resposta</span></div>` +
      `<div class="bc-face vs"><small>Resposta</small><p>${esc(r.resposta)}</p><span class="cd-nota">${esc(r.explicacao)}</span>` +
      `<div class="cd-acoes"><button type="button" class="pr-chip" data-acao="bc_rev" data-id="${esc(r.id)}" data-ok="0">Errei de novo</button><button type="button" class="pr-chip" data-acao="bc_rev" data-id="${esc(r.id)}" data-ok="1">Acertei</button></div></div></div>`
    );
  }
  function raizBanca(d, estIn) {
    const cads = lista(d.cadernos);
    const est = Object.assign({ sel: d.foco || (cads.find((c) => c.risco) || cads[0] || {}).sigla, reg: false, acertos: 14, rev: 0, virado: false }, estIn || {});
    const cols = cads
      .map((c, i) => {
        const cls = c.pronto ? " pronto" : c.risco ? " risco" : "";
        return (
          `<button type="button" class="bc-col${cls}" data-acao="bc_sel" data-c="${esc(c.sigla)}" aria-pressed="${c.sigla === est.sel}" style="--i:${i}">` +
          `<span class="bc-barra"><i style="height:${c.ultimo == null ? 0 : c.ultimo}%"></i><b class="bc-linha70"></b></span>` +
          `<span class="bc-s">${esc(c.sigla)}</span><small>${c.ultimo == null ? "—" : `${c.ultimo}%`}</small></button>`
        );
      })
      .join("");
    return (
      `<div ${raizAttr("banca", Object.assign({}, d, { _est: est }))}>` +
      `<div class="bc-gr">${cols}</div><div class="bc-info">${detalheBanca(d, est)}</div>${revisaoBanca(d, est)}` +
      `<p class="cd-pe">${esc(d.fonte || "")}</p></div>`
    );
  }
  Cards.registrar("banca", (data) => topo("caderno", "Banca PC/IFR", "70% em cada") + raizBanca(data || {}, null));
  function dadosBanca(cardEl) {
    const e = estadoDe(cardEl);
    const est = e._est || {};
    const d = Object.assign({}, e);
    delete d._est;
    return [d, est];
  }
  function repintarBanca(cardEl, d, est) {
    trocarRaiz(cardEl, raizBanca(d, est));
  }
  Cards.registrarAcao("bc_sel", (btn, cardEl) => {
    const [d, est] = dadosBanca(cardEl);
    est.sel = btn.dataset.c;
    est.reg = false;
    est.msg = "";
    repintarBanca(cardEl, d, est);
  });
  Cards.registrarAcao("bc_registro_abrir", (btn, cardEl) => {
    const [d, est] = dadosBanca(cardEl);
    est.reg = true;
    est.msg = "";
    repintarBanca(cardEl, d, est);
  });
  Cards.registrarAcao("bc_registro_fechar", (btn, cardEl) => {
    const [d, est] = dadosBanca(cardEl);
    est.reg = false;
    repintarBanca(cardEl, d, est);
  });
  Cards.registrarAcao("bc_acertos", (btn, cardEl) => {
    const [d, est] = dadosBanca(cardEl);
    est.acertos = Math.max(0, Math.min(d.questoes || 20, (est.acertos || 0) + Number(btn.dataset.d)));
    guardar(cardEl, Object.assign({}, d, { _est: est }));
    const v = cardEl.querySelector(".bc-v");
    if (v) v.textContent = `${est.acertos}/${d.questoes} · ${Math.round((est.acertos / d.questoes) * 100)}%`;
  });
  Cards.registrarAcao("bc_registrar", async (btn, cardEl, deps) => {
    const [d, est] = dadosBanca(cardEl);
    if (btn.disabled) return;
    btn.disabled = true;
    const r = await postar(deps, "/api/aviacao/banca/simulado", { caderno: est.sel, acertos: est.acertos });
    if (!r || !r.ok) {
      btn.disabled = false;
      return;
    }
    const pct = Math.round((est.acertos / d.questoes) * 100);
    const novo = Object.assign({}, r.card);
    repintarBanca(cardEl, novo, { sel: est.sel, reg: false, acertos: est.acertos, rev: est.rev, virado: false, ultimo: r.simulado_id, msg: pct >= (d.minimo || 70) ? `Registrado: ${pct}%.` : `Registrado: ${pct}%, abaixo de ${d.minimo || 70}%. Esse caderno vira prioridade.` });
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  });
  Cards.registrarAcao("bc_desfazer", async (btn, cardEl, deps) => {
    const [d, est] = dadosBanca(cardEl);
    if (btn.disabled) return;
    btn.disabled = true;
    const r = await postar(deps, `/api/aviacao/banca/simulado/${encodeURIComponent(btn.dataset.id)}/apagar`, {});
    if (!r || !r.ok) {
      btn.disabled = false;
      return;
    }
    repintarBanca(cardEl, r.card, { sel: est.sel, reg: false, acertos: est.acertos, rev: est.rev, msg: "Simulado desfeito." });
  });
  Cards.registrarAcao("bc_tempo", async (btn, cardEl, deps) => {
    const [d, est] = dadosBanca(cardEl);
    const inp = btn.parentNode.querySelector("input");
    const n = inp && inp.value ? Number(inp.value) : null;
    const r = await postar(deps, "/api/aviacao/banca/tempo", { caderno: btn.dataset.c, minutos: n && Number.isInteger(n) ? n : null });
    if (!r || !r.ok) return;
    repintarBanca(cardEl, r.card, Object.assign({}, est, { msg: n ? "Tempo guardado. Segue sem fonte oficial: confere na IS 00-003." : "Tempo apagado." }));
  });
  Cards.registrarAcao("bc_virar", (btn, cardEl) => {
    const f = cardEl.querySelector(".bc-flip");
    if (!f) return;
    f.classList.toggle("virado");
    const [d, est] = dadosBanca(cardEl);
    est.virado = f.classList.contains("virado");
    guardar(cardEl, Object.assign({}, d, { _est: est }));
  });
  Cards.registrarAcao("bc_rev", async (btn, cardEl, deps) => {
    const [d, est] = dadosBanca(cardEl);
    if (btn.disabled) return;
    btn.disabled = true;
    const r = await postar(deps, "/api/aviacao/banca/revisao", { id: Number(btn.dataset.id), acertou: btn.dataset.ok === "1" });
    if (!r || !r.ok) {
      btn.disabled = false;
      return;
    }
    const f = cardEl.querySelector(".bc-flip .vs");
    if (f) f.querySelector(".cd-acoes").innerHTML = `<span class="cd-nota bc-volta">${esc(r.revisao.texto)}</span>`;
    setTimeout(() => repintarBanca(cardEl, d, Object.assign({}, est, { rev: (est.rev || 0) + 1, virado: false })), reduz() ? 0 : 1200);
  });

  // ================================================================ chair_flying
  function raizChair(d, est) {
    const passos = lista(d.passos);
    const k = est.k;
    const fim = k >= passos.length;
    const prog = passos.map((_, j) => `<i class="${j <= k ? "on" : ""}"></i>`).join("");
    let palco;
    let botao;
    if (est.guardado) {
      palco = `<p class="cd-hero">Guardado.</p><p class="cd-nota">A próxima véspera começa por onde tu travou.</p>`;
      botao = "";
    } else if (fim) {
      const sel = lista(est.travou);
      palco =
        `<p class="cd-hero">Onde tu travou?</p><div class="cd-acoes cf-chips">` +
        lista(d.chips)
          .map((c) => `<button type="button" class="pr-chip" data-acao="cf_chip" data-t="${esc(c)}" aria-pressed="${sel.indexOf(c) >= 0}">${esc(c)}</button>`)
          .join("") +
        `</div>`;
      botao = `<button type="button" class="cd-acao primaria" data-acao="cf_guardar"${sel.length ? "" : " disabled"}>Guardar no diário</button>`;
    } else if (k >= 0) {
      const p = passos[k];
      palco = `<div class="cf-p"><p class="cd-rot">${esc(p.titulo)}</p><p class="cd-hero">${esc(p.texto)}</p></div>`;
      botao = `<button type="button" class="cd-acao primaria cd-aqui" data-acao="cf_avancar">${k === passos.length - 1 ? "Terminar" : "Falei, próximo"}</button>`;
    } else {
      const onde = d.voo ? `no ponto de espera, em ${d.voo.icao}` : "no ponto de espera";
      palco =
        `<p class="cd-hero">Fecha os olhos. Tu tá ${esc(onde)}.</p>` +
        (lista(d.comeca_por).length ? `<p class="cd-nota">Começa por onde travou da última vez: ${esc(d.comeca_por.join(", "))}.</p>` : "") +
        (d.personalizado ? "" : `<p class="cd-nota">Roteiro sem procedimento escrito: o conteúdo certo é o do teu instrutor e o do manual da aeronave.</p>`);
      botao = `<button type="button" class="cd-acao primaria cd-aqui" data-acao="cf_avancar">Começar</button>`;
    }
    const onda = !fim && !est.guardado ? `<div class="cf-onda${est.falando ? "" : " para"}" aria-hidden="true">${Array.from({ length: 24 }, (_, i) => `<i style="animation-delay:${(i * 0.05).toFixed(2)}s"></i>`).join("")}</div>` : "";
    return (
      `<div ${raizAttr("chair", Object.assign({}, d, { _est: est }))}><div class="cf-prog" aria-hidden="true">${prog}</div>` +
      `<div class="cf-palco" aria-live="polite">${palco}</div>${onda}${botao ? `<div class="cd-acoes">${botao}</div>` : ""}</div>`
    );
  }
  Cards.registrar("chair_flying", (data) => {
    const d = data || {};
    const quando = d.voo ? `véspera${d.voo.hora ? ` · voo ${d.voo.hora}` : ""}` : "antes do voo";
    return topo("cadeira", "Voo de cadeira", quando) + raizChair(d, { k: -1, travou: [] });
  });
  function dadosChair(cardEl) {
    const e = estadoDe(cardEl);
    const est = e._est || { k: -1, travou: [] };
    const d = Object.assign({}, e);
    delete d._est;
    return [d, est];
  }
  function pintarChair(cardEl, d, est) {
    trocarRaiz(cardEl, raizChair(d, est));
  }
  Cards.registrarAcao("cf_avancar", async (btn, cardEl) => {
    const [d, est] = dadosChair(cardEl);
    est.k += 1;
    const passos = lista(d.passos);
    if (est.k < passos.length) {
      est.falando = true;
      pintarChair(cardEl, d, est);
      const p = passos[est.k];
      const apagar = () => {
        const [d2, e2] = dadosChair(cardEl);
        if (e2.k !== est.k) return;
        e2.falando = false;
        const onda = cardEl.querySelector(".cf-onda");
        if (onda) onda.classList.add("para");
        guardar(cardEl, Object.assign({}, d2, { _est: e2 }));
      };
      const fala = `${p.titulo}. ${p.texto}`;
      if (typeof raiz.falarEsperando === "function") {
        raiz.falarEsperando(fala).then(apagar, apagar);
      } else {
        setTimeout(apagar, 2200);
      }
    } else {
      est.falando = false;
      if (typeof raiz.pararVoz === "function") raiz.pararVoz();
      pintarChair(cardEl, d, est);
    }
  });
  Cards.registrarAcao("cf_chip", (btn, cardEl) => {
    const [d, est] = dadosChair(cardEl);
    const t = btn.dataset.t;
    let sel = lista(est.travou);
    if (t === d.nada) sel = sel.indexOf(t) >= 0 ? [] : [t];
    else sel = sel.indexOf(t) >= 0 ? sel.filter((x) => x !== t) : sel.filter((x) => x !== d.nada).concat([t]);
    est.travou = sel;
    guardar(cardEl, Object.assign({}, d, { _est: est }));
    cardEl.querySelectorAll(".cf-chips .pr-chip").forEach((c) => c.setAttribute("aria-pressed", String(sel.indexOf(c.dataset.t) >= 0)));
    const g = cardEl.querySelector('[data-acao="cf_guardar"]');
    if (g) g.disabled = !sel.length;
  });
  Cards.registrarAcao("cf_guardar", async (btn, cardEl, deps) => {
    const [d, est] = dadosChair(cardEl);
    if (btn.disabled) return;
    btn.disabled = true;
    const r = await postar(deps, "/api/aviacao/chair", { voo_id: d.voo ? d.voo.id : null, travou: lista(est.travou) });
    if (!r || !r.ok) {
      btn.disabled = false;
      return;
    }
    est.guardado = true;
    pintarChair(cardEl, d, est);
  });

  // ================================================================ vento_pista
  // Mesma conta do servidor (aviacao_lab.calcular_vento): vento do METAR em graus VERDADEIROS, pista em MAGNETICOS;
  // com declinacao oeste, magnetico = verdadeiro + declinacao.
  function calcVento(dirV, vel, pista, corrige, rajada) {
    const dm = (((dirV + (corrige ? pista.decl_w : 0)) % 360) + 360) % 360;
    const lado = (cab, v) => {
      const th = ((dm - ((cab * 10) % 360)) * Math.PI) / 180;
      return [v * Math.cos(th), Math.abs(v * Math.sin(th))];
    };
    const cab = lista(pista.cabeceiras).slice().sort((a, b) => lado(b, vel)[0] - lado(a, vel)[0])[0];
    const [proa, trav] = lado(cab, vel);
    const travRaj = rajada ? lado(cab, rajada)[1] : null;
    return { dm, cab, proa: Math.round(proa), trav: Math.round(trav), travRaj: travRaj === null ? null : Math.round(travRaj) };
  }
  function veredito(c, limite, corrige) {
    const t = Math.max(c.trav, c.travRaj || 0);
    const ok = t <= limite * 0.7;
    const at = t <= limite;
    const tom = ok ? "ok" : at ? "alerta" : "perigo";
    const txt = `${ok ? "Tranquilo. " : at ? "Voa, mas com atenção. " : "Acima do teu limite. "}Través ${t} kt${c.travRaj && c.travRaj > c.trav ? " (com rajada)" : ""}, teu limite é ${limite} kt.${corrige ? "" : " (Conta errada: sem a declinação.)"}`;
    return [tom, txt];
  }
  const tresDig = (n) => String(Math.round(n)).padStart(3, "0");
  // tudo que a tela mostra do vento a partir do estado + dos dois controles (o render e o arrastar usam a mesma conta)
  function valoresVento(est, dv, v) {
    const mexeu = dv !== est.dir0 || v !== est.vel0;
    const raj = !mexeu && est.rajada ? est.rajada : null;
    const c = calcVento(dv, v, est.pista, est.corrige !== false, raj);
    const [tom, txt] = veredito(c, est.limite_kt, est.corrige !== false);
    return { c, tom, txt: (mexeu || !est.medido ? "Simulando. " : "") + txt };
  }
  function raizVento(d) {
    const p = d.pista || { cabeceiras: [18, 36], decl_w: 20.6, conferido: false };
    const alto = Math.max(p.cabeceiras[0], p.cabeceiras[1]);
    const baixo = Math.min(p.cabeceiras[0], p.cabeceiras[1]);
    const dir = d.direcao != null ? (Math.round(d.direcao / 5) * 5) % 360 : 0;
    const vel = d.velocidade != null ? Math.min(35, d.velocidade) : 0;
    const est = Object.assign({}, d, { pista: p, limite_kt: d.limite_kt || 10, corrige: true, dir0: dir, vel0: vel });
    const ini = valoresVento(est, dir, vel);
    const aviso = p.conferido
      ? `<p class="cd-nota vp-ok">Pista e declinação conferidas por ti no AISWEB/ROTAER.</p>`
      : `<p class="vp-aviso">Pista ${p.cabeceiras[0]}/${p.cabeceiras[1]} e declinação de ${virgula(p.decl_w, 1)}° W: ${NAO_CONFERIDO}. Vêm de fonte de terceiros; confere no AISWEB/ROTAER.</p>`;
    const msg = !d.medido
      ? `<p class="cd-nota">Sem METAR de ${esc(d.icao || "SSBL")} agora. Mexe nos controles pra simular.</p>`
      : d.variavel
        ? `<p class="cd-nota">Vento variável no METAR: sem conta de través. Mexe nos controles pra simular.</p>`
        : "";
    return (
      `<div ${raizAttr("vento", est)}>` +
      `<div class="vp-vis"><svg viewBox="0 0 200 200" aria-hidden="true"><circle cx="100" cy="100" r="92" class="vp-rosa"/>` +
      `<g class="vp-pista"><rect x="88" y="22" width="24" height="156" rx="3"/><text x="100" y="40">${alto}</text><text x="100" y="170">${baixo}</text><path d="M100 50v100" class="vp-eixo"/></g>` +
      `<g class="vp-seta" style="transform:rotate(${ini.c.dm}deg)"><path d="M100 6v38"/><path d="M92 34l8 12 8-12"/></g></svg>` +
      `<div class="vp-num"><div><small>proa</small><b class="vp-proa">${ini.c.proa} kt</b></div><div><small>través</small><b class="vp-trav">${ini.c.trav} kt</b></div><div><small>cabeceira</small><b class="vp-cab">${ini.c.cab}</b></div></div></div>` +
      `<div class="vp-metar">${esc(d.metar || "sem METAR agora")}</div>${msg}` +
      `<div class="vp-ctl"><label>direção <span class="vp-d">${tresDig(dir)}° V</span></label><input type="range" class="av-range" data-sim="vento" data-k="dir" min="0" max="355" step="5" value="${dir}" aria-label="Direção do vento (verdadeira)"></div>` +
      `<div class="vp-ctl"><label>velocidade <span class="vp-v">${vel} kt</span></label><input type="range" class="av-range" data-sim="vento" data-k="vel" min="0" max="35" value="${vel}" aria-label="Velocidade do vento"></div>` +
      `<div class="cd-seg vp-seg" data-p="0" role="group" aria-label="Correção da declinação"><span class="cd-pil" aria-hidden="true"></span>` +
      `<button type="button" data-acao="vp_corrige" data-v="1" aria-pressed="true">Com correção</button><button type="button" data-acao="vp_corrige" data-v="0" aria-pressed="false">Sem correção</button></div>` +
      `<p class="vp-ver ${ini.tom}" role="status">${esc(ini.txt)}</p>${aviso}` +
      `<details class="vp-aj"><summary>Ajustar pista, declinação e limite</summary><div class="vp-aj-c">` +
      `<label>Cabeceira A <input type="number" class="av-num" data-k="cab" min="1" max="36" value="${esc(p.cabeceiras[0])}"></label>` +
      `<label>Declinação W (°) <input type="number" class="av-num" data-k="decl" step="0.1" value="${esc(p.decl_w)}"></label>` +
      `<label>Teu limite de través (kt) <input type="number" class="av-num" data-k="lim" min="1" max="40" value="${esc(est.limite_kt)}"></label>` +
      `<div class="cd-acoes"><button type="button" class="cd-acao" data-acao="vp_salvar">Salvar</button>` +
      (p.conferido ? "" : `<button type="button" class="cd-acao primaria" data-acao="vp_conferi">Conferi no AISWEB</button>`) +
      `</div></div></details>` +
      `<p class="cd-pe">Vento do METAR em graus verdadeiros; pista em magnéticos. ${esc(d.fonte || "")}</p></div>`
    );
  }
  function pintarVento(rootEl) {
    let est;
    try {
      est = JSON.parse(rootEl.dataset.estado || "{}");
    } catch (e) {
      return;
    }
    const dirEl = rootEl.querySelector('[data-k="dir"]');
    const velEl = rootEl.querySelector('[data-k="vel"]');
    if (!dirEl || !velEl) return;
    const dv = Number(dirEl.value);
    const v = Number(velEl.value);
    const { c, tom, txt } = valoresVento(est, dv, v);
    const seta = rootEl.querySelector(".vp-seta");
    if (seta) seta.style.transform = `rotate(${c.dm}deg)`;
    rootEl.querySelector(".vp-proa").textContent = `${c.proa} kt`;
    rootEl.querySelector(".vp-trav").textContent = `${c.trav} kt`;
    rootEl.querySelector(".vp-cab").textContent = String(c.cab);
    rootEl.querySelector(".vp-d").textContent = `${tresDig(dv)}° V`;
    rootEl.querySelector(".vp-v").textContent = `${v} kt`;
    const ver = rootEl.querySelector(".vp-ver");
    ver.className = `vp-ver ${tom}`;
    ver.textContent = txt;
  }
  Cards.registrar("vento_pista", (data) => {
    const d = data || {};
    return topo("vento", "Vento agora", d.hora_z ? `METAR ${d.hora_z}` : d.icao || "SSBL") + raizVento(d);
  });
  Cards.registrarAcao("vp_corrige", (btn, cardEl) => {
    const r = cardEl.querySelector(".av-raiz");
    const est = estadoDe(cardEl);
    est.corrige = btn.dataset.v === "1";
    guardar(cardEl, est);
    const seg = btn.closest(".cd-seg");
    seg.dataset.p = est.corrige ? "0" : "1";
    seg.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
    pintarVento(r);
  });
  async function salvarPista(btn, cardEl, deps, extra) {
    const r0 = cardEl.querySelector(".av-raiz");
    const num = (k) => {
      const e = r0.querySelector(`.vp-aj [data-k="${k}"]`);
      return e && e.value !== "" ? Number(String(e.value).replace(",", ".")) : null;
    };
    const cab = num("cab");
    const corpo = Object.assign({}, extra);
    if (cab !== null && Number.isInteger(cab) && cab >= 1 && cab <= 36) corpo.cabeceiras = [cab, cab > 18 ? cab - 18 : cab + 18];
    if (num("decl") !== null) corpo.decl_w = num("decl");
    if (num("lim") !== null && Number.isInteger(num("lim"))) corpo.limite_kt = num("lim");
    btn.disabled = true;
    const r = await postar(deps, "/api/aviacao/pista", corpo);
    btn.disabled = false;
    if (!r || !r.ok) return;
    trocarRaiz(cardEl, raizVento(r.card));
    pintarVento(cardEl.querySelector(".av-raiz"));
  }
  Cards.registrarAcao("vp_salvar", (btn, cardEl, deps) => salvarPista(btn, cardEl, deps, {}));
  Cards.registrarAcao("vp_conferi", (btn, cardEl, deps) => salvarPista(btn, cardEl, deps, { conferido: true }));

  // ================================================================ passaporte
  const POR_PAGINA = 6;
  const INCLINA = [-8, 6, -4, 9, -10, 3];
  const MES3 = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"];
  function dataCarimbo(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
    return m ? `${m[3]} ${MES3[+m[2] - 1]} ${m[1].slice(2)}` : "";
  }
  function carimbos(d, pag) {
    const todos = lista(d.carimbos);
    return todos
      .slice(pag * POR_PAGINA, pag * POR_PAGINA + POR_PAGINA)
      .map((c, j) => {
        const i = pag * POR_PAGINA + j;
        return (
          `<div class="pp-car${c.novo ? " novo" : ""}" style="--r:${INCLINA[i % INCLINA.length]}deg;--d:${(0.35 + j * 0.16).toFixed(2)}s;--h:${(i * 57) % 360}" title="${esc(c.nome || c.icao)}${c.voos ? ` · ${c.voos} ${c.voos === 1 ? "pouso" : "pousos"}` : ""}">` +
          `<b>${esc(c.icao)}</b><small>${esc(dataCarimbo(c.primeiro))}</small></div>`
        );
      })
      .join("");
  }
  function raizPassaporte(d, est) {
    const todos = lista(d.carimbos);
    const paginas = Math.max(1, Math.ceil(todos.length / POR_PAGINA));
    const pag = Math.min(est.pag || 0, paginas - 1);
    const aberto = !!est.aberto;
    const nav =
      paginas > 1
        ? `<div class="pp-nav"><button type="button" class="cd-cad" data-acao="pp_pag" data-d="-1" aria-label="Página anterior"${pag === 0 ? " disabled" : ""}>‹</button>` +
          `<span class="cd-nota">página ${pag + 1} de ${paginas}</span><button type="button" class="cd-cad" data-acao="pp_pag" data-d="1" aria-label="Próxima página"${pag === paginas - 1 ? " disabled" : ""}>›</button></div>`
        : "";
    return (
      `<div ${raizAttr("passaporte", Object.assign({}, d, { _est: { pag, aberto } }))}>` +
      `<div class="pp-livro${aberto ? " aberto" : ""}"><div class="pp-pag pp-capa"><div><small>REPÚBLICA DOS VOOS</small><b>PASSAPORTE</b><span>de piloto</span></div>` +
      `<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"/></svg></div>` +
      `<div class="pp-pag pp-dentro">${todos.length ? `<div class="pp-carimbos">${carimbos(d, pag)}</div>` : `<p class="pp-vazio">Nenhum pouso no diário ainda. O primeiro carimbo cai quando tu registrar um voo.</p>`}</div></div>` +
      nav +
      `<div class="pp-est"><div><b>${nbsp(virgula(d.horas || 0, 1))}&nbsp;h</b><small>no diário</small></div>` +
      `<div><b>${esc(d.aeronaves || 0)}</b><small>${d.aeronaves === 1 ? "aeronave" : "aeronaves"}</small></div>` +
      `<div><b>${esc(todos.length)}</b><small>${todos.length === 1 ? "aeródromo" : "aeródromos"}</small></div></div>` +
      `<div class="cd-acoes"><button type="button" class="cd-acao primaria" data-acao="pp_abrir">${aberto ? "Fechar" : "Abrir o passaporte"}</button></div>` +
      `<p class="cd-pe">${esc(d.fonte || "")}. O carimbo é o primeiro pouso em cada aeródromo (destino e escalas).</p></div>`
    );
  }
  Cards.registrar("passaporte", (data) => {
    const d = data || {};
    const n = lista(d.carimbos).length;
    return topo("passaporte", "Passaporte", `${n} ${n === 1 ? "aeródromo" : "aeródromos"}`) + raizPassaporte(d, { pag: 0, aberto: false });
  });
  function dadosPP(cardEl) {
    const e = estadoDe(cardEl);
    const est = e._est || { pag: 0, aberto: false };
    const d = Object.assign({}, e);
    delete d._est;
    return [d, est];
  }
  Cards.registrarAcao("pp_abrir", (btn, cardEl) => {
    const [d, est] = dadosPP(cardEl);
    est.aberto = !est.aberto;
    const livro = cardEl.querySelector(".pp-livro");
    livro.classList.toggle("aberto", est.aberto);
    btn.textContent = est.aberto ? "Fechar" : "Abrir o passaporte";
    guardar(cardEl, Object.assign({}, d, { _est: est }));
  });
  Cards.registrarAcao("pp_pag", (btn, cardEl) => {
    const [d, est] = dadosPP(cardEl);
    est.pag = Math.max(0, (est.pag || 0) + Number(btn.dataset.d));
    trocarRaiz(cardEl, raizPassaporte(d, est));
  });

  // ---- sliders: um ouvinte so no documento (vale pro chat e pra aba) ----------------------------
  if (typeof document !== "undefined" && document.addEventListener) {
    document.addEventListener("input", (e) => {
      const alvo = e.target;
      if (!alvo || !alvo.classList || !alvo.classList.contains("av-range")) return;
      const rootEl = alvo.closest(".av-raiz");
      if (!rootEl) return;
      if (alvo.dataset.sim === "cheque") simularCheque(rootEl, Number(alvo.value));
      else if (alvo.dataset.sim === "vento") pintarVento(rootEl);
    });
  }

  // chamado depois que o card entra na tela: o vento tira a primeira conta
  function preparar(el) {
    if (!el || !el.querySelectorAll) return;
    el.querySelectorAll(".av-vento").forEach((r) => pintarVento(r));
  }

  const api = { raizRadar, raizCheque, raizBanca, raizChair, raizVento, raizPassaporte, calcVento, veredito, preparar, textoGrande, posRegua };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  raiz.CardsAviacaoLab = api;
})(typeof window !== "undefined" ? window : globalThis);
