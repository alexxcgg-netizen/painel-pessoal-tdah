// Cards das automacoes da 4a leva (2026-10-15, docs/briefings/2026-10-15-4a-leva.md): o assistente
// puxa o assunto sozinho no chat (conversa_proativa) e o card ja traz o proximo passo num toque.
//   documento_validade - carteirinha com contagem regressiva (marcos 60/30/7) + "criar tarefa de agendar";
//   compras_previsao   - itens que pelo historico estao acabando: "por na lista" / "ainda tem";
//   assinatura_subiu   - preco velho riscado -> novo e "mantem" / "me lembra de cancelar".
//
// Mesmo contrato do resto: renderizador PURO (estado final, historico, testes em Node), entrada
// animada so em .card-novo (CSS), cliques via Cards.registrarAcao. prefers-reduced-motion: nada anima.
// O que ele ja respondeu num card (tarefa criada, item na lista) fica guardado neste aparelho pra o
// historico nao oferecer o mesmo botao de novo (conveniencia - a fonte da verdade e o servidor).
(function (raiz) {
  "use strict";
  const Cards = raiz.Cards || (typeof require === "function" ? require("./cards.js") : null);
  if (!Cards) return;
  const { esc, numeroValido } = Cards;
  const lista = (v) => (Array.isArray(v) ? v : []);

  const svg = (corpo, extra = "") =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"${extra}>${corpo}</svg>`;
  const I = {
    documento: svg('<rect x="3" y="5" width="18" height="14" rx="2.5"/><circle cx="8.5" cy="11" r="2"/><path d="M5.8 16c.6-1.4 1.6-2 2.7-2s2.1.6 2.7 2M14 10h4M14 13.5h3"/>'),
    carrinho: svg('<path d="M3 4h2l2.2 10.5a1.5 1.5 0 0 0 1.5 1.2h8.6a1.5 1.5 0 0 0 1.5-1.1L21 8H6.2"/><circle cx="9.5" cy="19.5" r="1.3"/><circle cx="17" cy="19.5" r="1.3"/>'),
    assinatura: svg('<path d="M4 12a8 8 0 0 1 13.7-5.6L20 8.5"/><path d="M20 4v4.5h-4.5"/><path d="M20 12a8 8 0 0 1-13.7 5.6L4 15.5"/><path d="M4 20v-4.5h4.5"/>'),
    seta: svg('<path d="M5 12h14M13 6l6 6-6 6"/>'),
    ok: svg('<circle cx="12" cy="12" r="8.5"/><path d="m8.5 12.3 2.4 2.3 4.6-4.9"/>'),
    alerta: svg('<path d="M12 4 2.8 19.5h18.4L12 4Z"/><path d="M12 10v4M12 17h.01"/>'),
    relogio: svg('<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>'),
    mais: svg('<path d="M12 5v14M5 12h14"/>'),
  };
  const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  const diaMes = (iso) => {
    const d = Cards.parseDia(iso);
    return d ? `${d.getDate()} ${MESES[d.getMonth()]}` : "";
  };
  const diaMesAno = (iso, agora) => {
    const d = Cards.parseDia(iso);
    if (!d) return "";
    return d.getFullYear() === agora.getFullYear() ? diaMes(iso) : `${diaMes(iso)} ${d.getFullYear()}`;
  };
  const isoDe = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const amanhaIso = () => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return isoDe(d);
  };
  const olho = (icone, texto, quando) =>
    `<div class="card-resultado-eyebrow">${icone}<span>${esc(texto)}</span>${quando ? `<span class="sd-quando">${esc(quando)}</span>` : ""}</div>`;
  const reais = (v) => Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

  // ---- memoria local do que ja foi respondido (try/catch: Safari privado/sem storage)
  const CHAVE_FEITO = "cards-automacao-feito";
  function lerFeitos() {
    try {
      const v = JSON.parse(raiz.localStorage.getItem(CHAVE_FEITO) || "{}");
      return v && typeof v === "object" ? v : {};
    } catch (_) {
      return {};
    }
  }
  function lembrar(chave, valor) {
    try {
      const v = lerFeitos();
      v[chave] = valor;
      const chaves = Object.keys(v);
      if (chaves.length > 200) chaves.slice(0, chaves.length - 200).forEach((k) => delete v[k]);
      raiz.localStorage.setItem(CHAVE_FEITO, JSON.stringify(v));
    } catch (_) {
      /* sem storage: o card so nao lembra no historico */
    }
  }

  // ===================================================== documento_validade
  const MARCO_MAX = 60;
  const R_ANEL = 25;
  const VOLTA = 2 * Math.PI * R_ANEL;
  function fraseDocumento(dias) {
    if (dias < 0) return { texto: "Já venceu — renova o quanto antes.", nivel: "urgente" };
    if (dias === 0) return { texto: "Vence hoje.", nivel: "urgente" };
    if (dias <= 7) return { texto: "Última semana: se ainda não agendou, é agora.", nivel: "urgente" };
    if (dias <= 30) return { texto: "Um mês: já dá pra agendar a renovação sem correria.", nivel: "atencao" };
    return { texto: "Com folga — bom momento pra ver o que precisa.", nivel: "folga" };
  }
  const contagem = (dias) => (dias < 0 ? "vencido" : dias === 0 ? "hoje" : dias === 1 ? "1 dia" : `${dias} dias`);

  Cards.registrar("documento_validade", (data, _card, ctx) => {
    if (!data || !data.titulo || !data.vence) return null;
    const agora = (ctx && ctx.agora) || new Date();
    const vence = Cards.parseDia(data.vence);
    if (!vence) return null;
    // o historico reabre dias depois: conta de novo a partir de hoje
    const dias = Cards.diasEntre(agora, vence);
    const f = fraseDocumento(dias);
    const frac = Math.max(0, Math.min(1, dias / MARCO_MAX));
    const marcos = [60, 30, 7]
      .map((m) => `<span class="dv-marco${dias <= m ? " chegou" : ""}${data.marco === m ? " atual" : ""}"><i></i>${m} d</span>`)
      .join("");
    const chave = `doc:${data.id}:${data.vence}`;
    return (
      `<div class="sd dv" data-nivel="${f.nivel}" data-feito-chave="${esc(chave)}">` +
      olho(I.documento, "Documento vencendo", data.recorrente ? "renova todo ano" : "") +
      `<div class="dv-carteira">` +
      `<div class="dv-anel" style="--frac:${frac.toFixed(3)}"><svg viewBox="0 0 60 60" aria-hidden="true">` +
      `<circle class="dv-anel-base" cx="30" cy="30" r="${R_ANEL}"/>` +
      `<circle class="dv-anel-fio" cx="30" cy="30" r="${R_ANEL}" stroke-dasharray="${VOLTA.toFixed(2)}" stroke-dashoffset="${(VOLTA * (1 - frac)).toFixed(2)}"/></svg>` +
      `<b class="vivo-num"${dias >= 0 && dias < MARCO_MAX ? ` data-contar-de="${MARCO_MAX}" data-contar-ate="${dias}"` : ""}>${dias < 0 ? "!" : esc(dias)}</b><small>${dias < 0 ? "venceu" : dias === 1 ? "dia" : "dias"}</small></div>` +
      `<div class="dv-dados"><p class="dv-titulo">${esc(data.titulo)}</p>` +
      `<p class="dv-vence">vence <b class="vivo-num">${esc(diaMesAno(data.vence, agora))}</b> · ${esc(contagem(dias))}</p>` +
      `<div class="dv-marcos" aria-label="avisos em 60, 30 e 7 dias">${marcos}</div></div>` +
      `<span class="dv-furo" aria-hidden="true"></span>` +
      `</div>` +
      `<p class="sd-status${f.nivel === "urgente" ? " alerta" : ""}">${f.nivel === "folga" ? I.relogio : I.alerta}<span>${esc(f.texto)}</span></p>` +
      `<button type="button" class="ca-botao" data-acao="doc_agendar" data-titulo="${esc(data.titulo)}">${I.mais}<span>Me lembra de agendar amanhã</span></button>` +
      `</div>`
    );
  });

  // ===================================================== compras_previsao
  // cupom de mercado (docs/CARDS.md: "mercado = cupom saindo da impressora" - mesmo papel do gasto,
  // .tx-* em cards-vivos.css): cada linha e um item que deve estar acabando; "por na lista" carimba.
  function quandoAcaba(dias) {
    if (!numeroValido(dias)) return "";
    if (dias < 0) return `acabou há ${-dias} ${dias === -1 ? "dia" : "dias"}`;
    if (dias === 0) return "acaba hoje";
    if (dias === 1) return "acaba amanhã";
    return `acaba em ${dias} dias`;
  }

  Cards.registrar("compras_previsao", (data) => {
    const itens = lista(data && data.itens).filter((i) => i && i.item).slice(0, 4);
    if (!itens.length) return null;
    const linhas = itens
      .map((it, k) => {
        const int = numeroValido(it.intervalo_dias) && it.intervalo_dias > 0 ? it.intervalo_dias : null;
        // quanto do ciclo ja passou desde a ultima compra (100% = dia previsto)
        const passou = int && numeroValido(it.dias) ? Math.max(0.04, Math.min(1, (int - it.dias) / int)) : 0.9;
        const sub = [int ? `a cada ~${int} dias` : "", it.ultima ? `última ${diaMes(it.ultima)}` : ""].filter(Boolean).join(" · ");
        return (
          `<li class="cp-item" style="--k:${k}" data-item="${esc(it.item)}" data-feito-chave="${esc(`compra:${it.chave || it.item}:${it.ultima || ""}`)}">` +
          `<p class="tx-l cp-l"><span class="cp-nome">${esc(it.item)}</span><span class="cp-quando${numeroValido(it.dias) && it.dias <= 0 ? " ja" : ""}">${esc(quandoAcaba(it.dias))}</span></p>` +
          `<div class="cp-ciclo" aria-hidden="true"><i style="--passou:${passou.toFixed(3)}"></i></div>` +
          (sub ? `<p class="cp-sub">${esc(sub)}</p>` : "") +
          `<div class="cp-acoes"><button type="button" class="cp-b cp-lista" data-acao="compra_lista"><span class="cp-caixa" aria-hidden="true"></span>pôr na lista</button>` +
          `<button type="button" class="cp-b cp-adiar" data-acao="compra_adiar">ainda tem</button></div>` +
          `<p class="cp-feito" hidden></p>` +
          `<span class="cp-carimbo" aria-hidden="true">na lista</span>` +
          `</li>`
        );
      })
      .join("");
    return (
      `<div class="sd cp">` +
      olho(I.carrinho, "Compras que acabam", itens.length === 1 ? "1 item" : `${itens.length} itens`) +
      `<p class="cp-intro">Pelo teu ritmo de compra, ${itens.length === 1 ? "isso deve estar" : "isso aqui deve estar"} acabando:</p>` +
      `<div class="tx-impressora"><div class="tx-fresta"><div class="tx-cupom cp-cupom">` +
      `<p class="tx-c">Previsão · mercado</p>` +
      `<p class="tx-l"><span>pelo histórico</span><span>${itens.length} ${itens.length === 1 ? "item" : "itens"}</span></p><hr>` +
      `<ul class="cp-lista">${linhas}</ul><hr>` +
      `<p class="tx-l tx-total"><span>NA LISTA</span><span class="cp-total" data-total="${itens.length}">0/${itens.length}</span></p>` +
      `</div></div></div>` +
      `</div>`
    );
  });

  // ===================================================== assinatura_subiu
  // Etiqueta de remarcacao: a etiqueta velha (riscada) fica embaixo e a nova e colada por cima,
  // um pouco torta, como no mercado. Valores somem no modo visitante (cards.CAMPOS_SENSIVEIS).
  const reaisNbsp = (v) => reais(v).replace(/\s/, " ");
  Cards.registrar("assinatura_subiu", (data) => {
    if (!data || !data.descricao) return null;
    const oculto = !!data.oculto || !numeroValido(data.de) || !numeroValido(data.para);
    const dif = oculto ? 0 : Math.round((data.para - data.de) * 100) / 100;
    const precos = oculto
      ? `<p class="as-oculto">${esc(Cards.MOEDA_OCULTA)} · valores ocultos no modo visitante</p>`
      : `<div class="as-etiquetas">` +
        `<div class="as-tag as-velha"><span class="as-furo"></span><small>era</small><s class="vivo-num">${esc(reaisNbsp(data.de))}</s></div>` +
        `<div class="as-tag as-nova"><span class="as-furo"></span><small>agora</small>` +
        `<b class="vivo-num" data-contar-de="${esc(data.de)}" data-contar-ate="${esc(data.para)}" data-contar-fmt="moeda">${esc(reaisNbsp(data.para))}</b>` +
        (numeroValido(data.pct) ? `<span class="as-pct vivo-num">+${esc(Math.round(data.pct))}%</span>` : "") +
        `</div></div>` +
        `<p class="as-dif">São <b class="vivo-num">${esc(reaisNbsp(dif))}</b> a mais por mês — <b class="vivo-num">${esc(reaisNbsp(dif * 12))}</b> num ano.</p>`;
    return (
      `<div class="sd as" data-feito-chave="${esc(`assin:${String(data.descricao).toLowerCase()}:${oculto ? "" : data.para}`)}">` +
      olho(I.assinatura, "Assinatura mais cara", "remarcou") +
      `<p class="sd-hero">${esc(data.descricao)}</p>` +
      precos +
      (oculto
        ? ""
        : `<div class="as-acoes"><button type="button" class="ca-botao ca-leve" data-acao="assin_manter"><span>Mantém</span></button>` +
          `<button type="button" class="ca-botao" data-acao="assin_cancelar" data-descricao="${esc(data.descricao)}"><span>Me lembra de cancelar</span></button></div>`) +
      `<p class="sd-status" aria-live="polite"></p>` +
      `</div>`
    );
  });

  // ============================================================== interacoes
  const vibrar = (ms) => typeof raiz.vibrar === "function" && raiz.vibrar(ms);
  const status = (el, icone, texto, classe = "ok") => {
    if (!el) return;
    el.className = `sd-status ${classe}`;
    el.innerHTML = `${icone}<span class="sd-troca">${esc(texto)}</span>`;
  };
  async function postar(deps, url, corpo) {
    if (typeof deps.apiFetch !== "function") return null;
    try {
      return await deps.apiFetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(corpo),
      });
    } catch (_) {
      return null;
    }
  }
  const textoFeito = {
    doc: () => "Tarefa criada pra amanhã. Tá na aba Tarefas.",
    manter: () => "Fica como está. Não pergunto de novo desse aumento.",
    cancelar: () => "Tarefa de cancelar criada pra amanhã.",
  };

  // aplica um "ja respondido" no card (agora ou ao reabrir o historico)
  function aplicarFeito(alvo, feito, agora = false) {
    if (!alvo || !feito || typeof feito !== "object") return;
    if (alvo.classList.contains("cp-item")) {
      const msg = alvo.querySelector(".cp-feito");
      const acoes = alvo.querySelector(".cp-acoes");
      if (acoes) acoes.hidden = true;
      const naLista = feito.tipo === "lista";
      alvo.classList.add(naLista ? "na-lista" : "adiado");
      if (naLista && agora) alvo.classList.add("carimbou"); // so no toque: historico abre carimbado e parado
      if (msg) {
        msg.hidden = false;
        msg.textContent = naLista ? "foi pra lista de compras" : `ainda tem · pergunto de novo ${feito.ate ? `lá por ${diaMes(feito.ate)}` : "mais pra frente"}`;
        if (agora) msg.classList.add("sd-troca");
      }
      const cupom = alvo.closest(".cp-cupom");
      const total = cupom && cupom.querySelector(".cp-total");
      if (total) total.textContent = `${cupom.querySelectorAll(".cp-item.na-lista").length}/${total.dataset.total}`;
      return;
    }
    const botao = alvo.querySelector(".ca-botao:not(.ca-leve)");
    const acoes = alvo.querySelector(".as-acoes");
    if (acoes) acoes.hidden = true;
    else if (botao) botao.hidden = true;
    const t = (textoFeito[feito.tipo] || textoFeito.doc)();
    status(alvo.querySelector(".sd-status"), I.ok, t);
  }

  function preparar(el) {
    if (!el || !el.querySelectorAll) return;
    const feitos = lerFeitos();
    el.querySelectorAll("[data-feito-chave]").forEach((alvo) => {
      const f = feitos[alvo.dataset.feitoChave];
      if (f) aplicarFeito(alvo, f);
    });
  }

  async function criarTarefa(btn, alvo, deps, titulo, tipo) {
    if (btn.disabled) return;
    btn.disabled = true;
    btn.classList.add("enviando");
    const res = await postar(deps, "/api/tasks", { titulo: titulo.slice(0, 200), due_date: amanhaIso() });
    btn.disabled = false;
    btn.classList.remove("enviando");
    if (!res || !res.ok) {
      status(alvo.querySelector(".sd-status"), I.alerta, "Não deu pra criar a tarefa agora. Tenta de novo?", "alerta");
      return;
    }
    const feito = { tipo };
    lembrar(alvo.dataset.feitoChave, feito);
    aplicarFeito(alvo, feito, true);
    vibrar(10);
    if (raiz.CardsPremium && typeof raiz.CardsPremium.festejar === "function") raiz.CardsPremium.festejar(alvo.querySelector(".sd-status svg"));
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  }

  // ===================================================== despertador
  // "Amanhã quero acordar às 7" no chat: hora grande + botão que abre o Atalho "Despertador do Painel"
  // (a Apple só deixa o app Atalhos criar alarme; o botão é o servidor que manda, no rodapé do card).
  const ICONE_DESPERTA =
    '<svg class="vv-despertador" viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="16" cy="17.5" r="9.5"/><path d="M16 12v5.5l3.5 2.2"/><path d="M5 8.5 8.5 5M27 8.5 23.5 5"/><path d="M10 26.5 8 29M22 26.5 24 29"/></svg>';
  const horaValida = (h) => typeof h === "string" && /^([01]\d|2[0-3]):[0-5]\d$/.test(h);
  Cards.registrar("despertador", (data, _card, ctx) => {
    if (!data || !horaValida(data.hora) || !Cards.parseDia(data.data)) return null;
    const agora = (ctx && ctx.agora) || new Date();
    const dia = Cards.rotuloDia(data.data, agora);
    const antes = horaValida(data.pedida) && data.pedida !== data.hora;
    const sub = antes
      ? `um compromisso pede antes das ${data.pedida} que você pediu`
      : `${dia}${dia === "hoje" || dia === "amanhã" ? ", " + Cards.dataCurta(data.data) : ""}`;
    return (
      `<div class="sd dsp">` +
      olho(I.relogio, "Despertador", antes ? dia : "") +
      `<div class="vv-hero">${ICONE_DESPERTA}<span class="vv-hero-rot">Acorda</span><b class="vivo-num">${esc(data.hora)}</b>` +
      `<span class="vv-hero-sub">${esc(sub)}</span></div>` +
      `</div>`
    );
  });

  if (typeof Cards.registrarAcao === "function") {
    Cards.registrarAcao("doc_agendar", (btn, _cardEl, deps) => {
      const alvo = btn.closest(".dv");
      // "Renovar CNH" / "Renovação do passaporte" -> "Agendar renovação: CNH" / "...: passaporte"
      const doc = (btn.dataset.titulo || "documento").replace(/^renova(r|ção)\s+(d[aoe]s?\s+)?/i, "") || "documento";
      if (alvo) return criarTarefa(btn, alvo, deps, `Agendar renovação: ${doc}`, "doc");
    });

    Cards.registrarAcao("assin_cancelar", (btn, _cardEl, deps) => {
      const alvo = btn.closest(".as");
      if (alvo) return criarTarefa(btn, alvo, deps, `Cancelar ${btn.dataset.descricao || "assinatura"}`, "cancelar");
    });

    Cards.registrarAcao("assin_manter", (btn) => {
      const alvo = btn.closest(".as");
      if (!alvo) return;
      const feito = { tipo: "manter" };
      lembrar(alvo.dataset.feitoChave, feito);
      aplicarFeito(alvo, feito, true);
      vibrar(6);
    });

    const compra = (tipo) => async (btn, _cardEl, deps) => {
      const li = btn.closest(".cp-item");
      if (!li || li.dataset.enviando) return;
      const item = li.dataset.item;
      li.dataset.enviando = "1";
      li.querySelectorAll(".cp-b").forEach((b) => (b.disabled = true));
      const res = await postar(deps, tipo === "lista" ? "/api/compras" : "/api/compras/adiar", { item });
      delete li.dataset.enviando;
      li.querySelectorAll(".cp-b").forEach((b) => (b.disabled = false));
      if (!res || !res.ok) {
        const msg = li.querySelector(".cp-feito");
        if (msg) {
          msg.hidden = false;
          msg.textContent = "não deu agora — tenta de novo?";
        }
        return;
      }
      const feito = tipo === "lista" ? { tipo } : { tipo, ate: res.ate || null };
      lembrar(li.dataset.feitoChave, feito);
      aplicarFeito(li, feito, true);
      vibrar(tipo === "lista" ? [6, 50, 14] : 6); // carimbo: toque duplo curto
      if (typeof deps.aoMudar === "function") deps.aoMudar();
    };
    Cards.registrarAcao("compra_lista", compra("lista"));
    Cards.registrarAcao("compra_adiar", compra("adiar"));
  }

  // numeros que contam de um valor ate outro (preco velho -> novo, 60 -> dias que faltam)
  const suaveSaida = (k) => 1 - Math.pow(1 - k, 3);
  function animar(el) {
    if (!el || !el.querySelectorAll || typeof raiz.requestAnimationFrame !== "function") return;
    if (raiz.matchMedia && raiz.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    el.querySelectorAll("[data-contar-de][data-contar-ate]").forEach((n) => {
      const de = Number(n.dataset.contarDe);
      const ate = Number(n.dataset.contarAte);
      if (!Number.isFinite(de) || !Number.isFinite(ate)) return;
      const fmt = n.dataset.contarFmt === "moeda" ? reaisNbsp : (v) => String(Math.round(v));
      const final = n.textContent;
      const atraso = n.closest(".as-nova") ? 650 : 300; // o preco novo conta depois que a etiqueta cola
      n.textContent = fmt(de);
      setTimeout(() => {
        const t0 = performance.now();
        const passo = (t) => {
          const k = Math.min(1, (t - t0) / 1100);
          n.textContent = k < 1 ? fmt(de + (ate - de) * suaveSaida(k)) : final;
          if (k < 1) raiz.requestAnimationFrame(passo);
        };
        raiz.requestAnimationFrame(passo);
      }, atraso);
    });
  }

  const CardsAutomacao = { preparar, animar, fraseDocumento, quandoAcaba, aplicarFeito };
  raiz.CardsAutomacao = CardsAutomacao;
  if (typeof module !== "undefined" && module.exports) module.exports = CardsAutomacao;
})(typeof window !== "undefined" ? window : globalThis);
