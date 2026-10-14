// Professor de aviacao no chat (2026-10-13): card do briefing meteorologico (METAR/TAF ja
// decodificados no servidor, briefing_voo.py). Mesmo contrato dos cartoes vivos: o
// renderizador e puro e devolve o ESTADO FINAL; a entrada animada e so CSS em cima do
// .card-novo que o CardsPremium.animar poe nas respostas novas (historico abre parado,
// prefers-reduced-motion nao anima).
(function (raiz) {
  "use strict";
  const Cards = raiz.Cards || (typeof require === "function" ? require("./cards.js") : null);
  if (!Cards) return;
  const { esc, numeroValido } = Cards;
  const lista = (v) => (Array.isArray(v) ? v : []);

  const ICONE_BRIEFING =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 21V4"/><path d="M4 5h11l-2 3 2 3H4"/><path d="M15 6.5 20 7v2l-5 .5"/></svg>';

  const CATEGORIAS = {
    VFR: { nome: "VFR", dica: "teto acima de 3.000 pés e visibilidade acima de 5 milhas" },
    MVFR: { nome: "MVFR", dica: "teto de 1.000 a 3.000 pés ou visibilidade de 3 a 5 milhas" },
    IFR: { nome: "IFR", dica: "teto de 500 a 999 pés ou visibilidade de 1 a 3 milhas" },
    LIFR: { nome: "LIFR", dica: "teto abaixo de 500 pés ou visibilidade abaixo de 1 milha" },
  };
  const catValida = (c) => (CATEGORIAS[c] ? c : null);
  const isoHoje = () => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  };
  const milhar = (n) => Math.round(Number(n) || 0).toLocaleString("pt-BR");

  function visTexto(m) {
    if (!numeroValido(m)) return "—";
    if (m >= 9999) return "10+ km";
    if (m >= 1000) return `${(m / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} km`;
    return `${m} m`;
  }

  // rosa dos ventos: a seta entra pela borda DE ONDE o vento vem e aponta pro centro
  function rosa(vento) {
    const v = vento && typeof vento === "object" ? vento : null;
    const calmo = !v || v.velocidade_kt === 0;
    const variavel = v && v.variavel;
    const dir = v && numeroValido(v.direcao) ? v.direcao : 0;
    const marcas = Array.from({ length: 12 }, (_, i) => {
      const a = i * 30;
      const longa = a % 90 === 0;
      return `<line x1="50" y1="${longa ? 7 : 9}" x2="50" y2="${longa ? 13 : 12}" transform="rotate(${a} 50 50)" class="${longa ? "bv-marca-forte" : ""}"/>`;
    }).join("");
    const setor =
      v && Array.isArray(v.variavel_entre) && v.variavel_entre.length === 2
        ? (() => {
            const [a, b] = v.variavel_entre.map(Number);
            const arco = ((b - a + 360) % 360) || 360;
            const r = 36;
            const p = (ang) => [50 + r * Math.sin((ang * Math.PI) / 180), 50 - r * Math.cos((ang * Math.PI) / 180)];
            const [x1, y1] = p(a);
            const [x2, y2] = p(b);
            return `<path class="bv-setor" d="M50 50 L${x1.toFixed(1)} ${y1.toFixed(1)} A${r} ${r} 0 ${arco > 180 ? 1 : 0} 1 ${x2.toFixed(1)} ${y2.toFixed(1)} Z"/>`;
          })()
        : "";
    const seta = calmo
      ? `<circle cx="50" cy="50" r="5" class="bv-calmo"/>`
      : variavel
        ? `<circle cx="50" cy="50" r="22" class="bv-variavel"/>`
        : `<g class="bv-seta" style="--dir:${dir}deg"><path d="M50 16 L50 44" class="bv-haste"/><path d="M50 50 L44.5 40 L55.5 40 Z" class="bv-ponta"/>` +
          `<path d="M50 16 l-6 -5 M50 22 l-6 -5" class="bv-penas"/></g>`;
    const rotulo = calmo
      ? "calmo"
      : `${variavel ? "VRB" : `${String(dir).padStart(3, "0")}°`} <b>${esc(v.velocidade_kt)}</b> kt${v.rajada_kt ? ` <span class="bv-rajada">G${esc(v.rajada_kt)}</span>` : ""}`;
    return (
      `<figure class="bv-rosa"><svg viewBox="0 0 100 100" role="img" aria-label="${esc(calmo ? "vento calmo" : `vento de ${variavel ? "direção variável" : `${dir} graus`} com ${v.velocidade_kt} nós${v.rajada_kt ? `, rajada ${v.rajada_kt}` : ""}`)}">` +
      `<circle cx="50" cy="50" r="41" class="bv-aro"/>${marcas}${setor}` +
      `<text x="50" y="23" class="bv-n">N</text>${seta}</svg>` +
      `<figcaption class="vivo-num">${rotulo}</figcaption></figure>`
    );
  }

  // barra de 0 ao topo da escala, com os limiares das categorias marcados
  function regua(rotulo, valorTxt, frac, marcas, extra) {
    const f = Math.max(0.02, Math.min(1, frac));
    const tiques = marcas.map((m) => `<i class="bv-tique" style="left:${(m * 100).toFixed(1)}%"></i>`).join("");
    return (
      `<div class="bv-medida"><span class="bv-medida-rot">${esc(rotulo)}</span>` +
      `<span class="vivo-num bv-medida-val">${valorTxt}</span>` +
      `<div class="bv-trilho">${tiques}<b style="--frac:${f.toFixed(3)}"></b></div>${extra || ""}</div>`
    );
  }

  Cards.registrar("briefing_voo", (data) => {
    if (!data || !data.icao) return null;
    const cat = catValida(data.categoria);
    const idade = numeroValido(data.idade_min) ? (data.idade_min < 60 ? `há ${data.idade_min} min` : `há ${Math.floor(data.idade_min / 60)}h`) : "";
    const obs = data.observado ? `<span class="bv-obs vivo-num">${esc(data.observado)}${idade ? ` · ${esc(idade)}` : ""}</span>` : "";
    const troca = data.substituto_de
      ? `<p class="vivo-sub bv-troca">${esc(data.substituto_de)} não publica METAR, então esse é o de ${esc(data.icao)} (${esc(data.nome || "")}), o mais perto.</p>`
      : "";
    const voo = data.voo && data.voo.data
      ? `<p class="bv-voo"><span class="bv-voo-hora vivo-num">${esc(data.voo.hora || "—")}</span>` +
        `<span>seu voo ${data.voo.data === isoHoje() ? "hoje" : `dia ${esc(Cards.dataCurta(data.voo.data))}`}${data.voo.origem ? ` · ${esc(data.voo.origem)}` : ""}${data.voo.destino ? ` → ${esc(data.voo.destino)}` : ""}</span></p>`
      : "";

    const teto = numeroValido(data.teto_ft) ? data.teto_ft : null;
    const tetoTxt = teto === null ? "sem teto" : `${milhar(teto)} <small>ft</small>`;
    const vis = numeroValido(data.visibilidade_m) ? data.visibilidade_m : null;
    const medidas =
      regua("Teto", tetoTxt, teto === null ? 1 : teto / 5000, [500 / 5000, 1000 / 5000, 3000 / 5000]) +
      regua("Visibilidade", visTexto(vis), vis === null ? 0 : vis / 10000, [1609 / 10000, 4828 / 10000, 8047 / 10000]) +
      `<div class="bv-mini"><span><small>QNH</small><b class="vivo-num">${data.qnh ? esc(data.qnh) : "—"}</b></span>` +
      `<span><small>Temp / orvalho</small><b class="vivo-num">${numeroValido(data.temp) ? `${data.temp}°` : "—"}<i>/</i>${numeroValido(data.orvalho) ? `${data.orvalho}°` : "—"}</b></span></div>`;

    const fen = lista(data.fenomenos).map((f) => `<span class="bv-fen">${esc(f)}</span>`).join("");
    const nuvens = lista(data.nuvens)
      .filter((n) => n && n.tipo)
      .map((n) => `<span class="bv-nuvem vivo-num">${esc(n.tipo)}${numeroValido(n.altura_ft) ? ` ${milhar(n.altura_ft)}` : ""}</span>`)
      .join("");

    const taf = lista(data.taf).filter((t) => t && t.rotulo);
    const linhaTaf = taf
      .map((t, i) => {
        const c = catValida(t.categoria);
        const quando = t.de && t.ate ? `${t.de} → ${t.ate}` : t.de ? `a partir de ${t.de}` : "";
        return (
          `<li class="bv-taf-item${c ? ` bv-cat-${c}` : ""}" style="--i:${i}"><span class="bv-taf-ponto" aria-hidden="true"></span>` +
          `<div class="bv-taf-cab"><b>${esc(t.rotulo)}</b>${quando ? `<span class="vivo-num">${esc(quando)}</span>` : ""}${c ? `<em>${c}</em>` : ""}</div>` +
          `<p>${esc(t.resumo || "")}${t.vento ? ` · ${esc(t.vento)}` : ""}</p></li>`
        );
      })
      .join("");

    const bruto =
      data.metar_bruto || data.taf_bruto
        ? `<details class="bv-bruto"><summary>Boletim bruto</summary>` +
          (data.metar_bruto ? `<pre>${esc(data.metar_bruto)}</pre>` : "") +
          (data.taf_bruto ? `<pre>${esc(data.taf_bruto)}</pre>` : "") +
          `</details>`
        : "";

    return (
      `<div class="bv" data-categoria="${cat || ""}">` +
      `<div class="card-resultado-eyebrow">${ICONE_BRIEFING}<span>METAR · ${esc(data.icao)}${data.nome && data.nome !== data.icao ? ` ${esc(data.nome)}` : ""}</span>${obs}</div>` +
      troca +
      voo +
      `<div class="bv-topo"><div class="bv-cat"${cat ? ` title="${esc(CATEGORIAS[cat].dica)}"` : ""}>` +
      `<span class="bv-cat-selo">${cat || "—"}</span><small>${cat ? esc(CATEGORIAS[cat].dica) : "sem teto nem visibilidade no boletim"}</small></div>` +
      rosa(data.vento) +
      `</div>` +
      (fen || nuvens ? `<div class="bv-chips">${fen}${nuvens}</div>` : "") +
      `<div class="bv-medidas">${medidas}</div>` +
      (linhaTaf ? `<p class="vivo-sub bv-taf-tit">Próximas horas (TAF)</p><ol class="bv-taf">${linhaTaf}</ol>` : "") +
      bruto +
      `<p class="vivo-nota">${esc(data.aviso || "Conversão do boletim oficial, não é liberação: a decisão de voar é sua e do instrutor.")}</p>` +
      `</div>`
    );
  });

  // ================================================================ quiz_aviacao
  // Pergunta da banca: 4 alternativas clicaveis; a correcao vem do servidor
  // (/api/estudo/responder) - o card nunca sabe a certa antes de responder.
  const ICONE_QUIZ =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m3 9 9-5 9 5-9 5-9-5Z"/><path d="M7 11.2V16c0 1.2 2.2 2.5 5 2.5s5-1.3 5-2.5v-4.8"/><path d="M21 9v5"/></svg>';
  const MARCA_CERTO = '<svg class="qz-marca" viewBox="0 0 20 20" aria-hidden="true"><path d="M5 10.5 8.5 14 15 6.5"/></svg>';
  const MARCA_ERRADO = '<svg class="qz-marca" viewBox="0 0 20 20" aria-hidden="true"><path d="M6 6l8 8M14 6l-8 8"/></svg>';
  const LETRAS = "ABCD";
  const TEMA_CURTO = (t) => String(t || "").replace(/\s*\(.*\)$/, "").replace(/ aeronautica$/i, "").replace(/^Regulamentacao$/i, "Regulamentação").replace(/^Navegacao$/i, "Navegação");

  function quandoVolta(iso) {
    const d = Cards.parseDia(iso);
    const h = Cards.parseDia(isoHoje());
    if (!d || !h) return "";
    const dias = Math.round((d - h) / 86400000);
    if (dias <= 0) return "volta hoje";
    if (dias === 1) return "volta amanhã";
    return `volta em ${dias} dias`;
  }

  function pontosCaixa(caixa, max) {
    const n = Math.max(1, Number(max) || 5);
    const c = Math.max(0, Math.min(n, Number(caixa) || 0));
    return (
      `<span class="qz-caixas" role="img" aria-label="nível ${c} de ${n} na revisão">` +
      Array.from({ length: n }, (_, i) => `<i class="${i < c ? "cheia" : ""}" style="--k:${i}"></i>`).join("") +
      `</span>`
    );
  }

  function blocoResultado(r, alternativas) {
    if (!r) return `<div class="qz-explica"><div></div></div>`;
    const certa = Number(r.correta);
    const veredito = r.acertou
      ? "Na mosca."
      : `Quase. A certa é a ${LETRAS[certa] || "?"}${alternativas && alternativas[certa] ? `: ${esc(alternativas[certa])}` : ""}`;
    return (
      `<div class="qz-explica"><div><p class="qz-veredito">${veredito}</p>` +
      `<p class="qz-porque">${esc(r.explicacao || "")}</p>` +
      `<p class="qz-prox">${esc(quandoVolta(r.proxima_revisao))}${r.acertou ? "" : " pra você fixar"}</p></div></div>`
    );
  }

  function classeAlt(i, r) {
    if (!r) return "";
    const c = [];
    if (i === Number(r.correta)) c.push("certa");
    if (i === Number(r.escolhida)) c.push("escolhida");
    if (i === Number(r.escolhida) && !r.acertou) c.push("errada");
    return c.join(" ");
  }

  Cards.registrar("quiz_aviacao", (data) => {
    const alts = lista(data.alternativas);
    if (!numeroValido(data.id) || alts.length !== 4) return null;
    const r = data.resposta && typeof data.resposta === "object" ? data.resposta : null;
    const caixa = r && numeroValido(r.caixa) ? r.caixa : data.caixa;
    const botoes = alts
      .map((a, i) => {
        const cls = classeAlt(i, r);
        const marca = r && i === Number(r.correta) ? MARCA_CERTO : r && cls.includes("errada") ? MARCA_ERRADO : "";
        return (
          `<li><button type="button" class="qz-alt ${cls}" data-acao="quiz_responder" data-alt="${i}"${r ? " disabled" : ""} style="--i:${i}">` +
          `<span class="qz-letra">${LETRAS[i]}</span><span class="qz-txt">${esc(a)}</span>${marca}</button></li>`
        );
      })
      .join("");
    return (
      `<div class="qz" data-quiz-id="${esc(data.id)}" data-estado="${r ? "respondida" : "aberta"}"${r ? ` data-acertou="${r.acertou ? 1 : 0}"` : ""}>` +
      olhoQuiz(data, caixa) +
      `<p class="qz-enunciado">${esc(data.enunciado)}</p>` +
      `<ol class="qz-alts">${botoes}</ol>` +
      blocoResultado(r, alts) +
      `</div>`
    );
  });

  function olhoQuiz(data, caixa) {
    return (
      `<div class="card-resultado-eyebrow">${ICONE_QUIZ}<span>Banca · ${esc(TEMA_CURTO(data.tema))}</span>` +
      (data.revisao ? `<span class="qz-revisao">revisão</span>` : "") +
      pontosCaixa(caixa, data.caixa_max) +
      `</div>`
    );
  }

  // clique numa alternativa: trava as 4, manda pro servidor e revela no proprio card
  if (typeof Cards.registrarAcao === "function") Cards.registrarAcao("quiz_responder", async (btn, cardEl, deps) => {
    const quiz = btn.closest(".qz");
    if (!quiz || quiz.dataset.estado !== "aberta" || typeof deps.apiFetch !== "function") return;
    const escolha = Number(btn.dataset.alt);
    const botoes = Array.from(quiz.querySelectorAll(".qz-alt"));
    quiz.dataset.estado = "enviando";
    botoes.forEach((b) => (b.disabled = true));
    btn.classList.add("escolhendo");
    const res = await deps.apiFetch("/api/estudo/responder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: Number(quiz.dataset.quizId), alternativa: LETRAS[escolha] }),
    });
    btn.classList.remove("escolhendo");
    if (!res || !numeroValido(res.correta)) {
      quiz.dataset.estado = "aberta";
      botoes.forEach((b) => (b.disabled = false));
      return;
    }
    const alts = botoes.map((b) => (b.querySelector(".qz-txt") || {}).textContent || "");
    botoes.forEach((b, i) => {
      const cls = classeAlt(i, res);
      if (cls) b.className = `qz-alt ${cls}`;
      if (i === Number(res.correta)) b.insertAdjacentHTML("beforeend", MARCA_CERTO);
      else if (cls.includes("errada")) b.insertAdjacentHTML("beforeend", MARCA_ERRADO);
    });
    // a explicacao entra com texto ja escapado (o servidor manda texto puro)
    const tmp = document.createElement("div");
    tmp.innerHTML = blocoResultado(res, alts);
    const velho = quiz.querySelector(".qz-explica");
    if (velho && tmp.firstElementChild) velho.replaceWith(tmp.firstElementChild);
    const caixas = quiz.querySelector(".qz-caixas");
    if (caixas && numeroValido(res.caixa)) {
      caixas.querySelectorAll("i").forEach((i, k) => i.classList.toggle("cheia", k < res.caixa));
    }
    quiz.dataset.acertou = res.acertou ? "1" : "0";
    quiz.classList.add("qz-revelando");
    // um frame depois pra transicao da explicacao abrir (0fr -> 1fr)
    requestAnimationFrame(() => (quiz.dataset.estado = "respondida"));
    if (res.acertou && raiz.CardsPremium) raiz.CardsPremium.festejar(quiz.querySelector(".qz-alt.certa .qz-letra"));
    if (typeof raiz.vibrar === "function") raiz.vibrar(res.acertou ? 12 : [8, 60, 8]);
  });

  // ================================================================ voo_agendado
  // Cartao de embarque do voo marcado (2026-10-14, docs/CARDS.md "Linguagem visual"): rota com
  // as pernas em NM, horarios (sair de casa / chegar / decola / pousa) e as horas do curso. Tocar
  // num aerodromo faz o aviao ir (ou voltar) ate la e mostra a perna. O SVG usa viewBox fixo com
  // "meet" (escala igual nos dois eixos), entao os botoes posicionados em % batem com os pontos.
  const ICONE_AVIAO =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.5 13.5 3 11l1.5-1.5 8 1L17 6a2 2 0 0 1 3 3l-4.5 4.5 1 8L15 23l-2.5-7.5"/></svg>';
  const AVIAO_CHEIO =
    '<path d="M21.6 11.2 14 8.4V3.6a1.6 1.6 0 0 0-3.2 0v4.8L3.4 11.2a.9.9 0 0 0-.6.9v1.1l8-1.7v5l-2.3 1.7v1.4l3.5-.9 3.5.9v-1.4L13.2 16.5v-5l8 1.7v-1.1a.9.9 0 0 0-.6-.9z" transform="scale(.82) translate(-12 -12) rotate(90 12 12)"/>';
  const VA_LARG = 300;
  const VA_Y = 34;
  const VA_TOPO = -6;

  function vaPontos(n) {
    if (n <= 1) return [VA_LARG / 2];
    return Array.from({ length: n }, (_, i) => 10 + (i * (VA_LARG - 20)) / (n - 1));
  }
  function vaCaminho(xs) {
    if (xs.length < 2) return "";
    let d = `M${xs[0].toFixed(1)} ${VA_Y}`;
    for (let i = 1; i < xs.length; i++) {
      const meio = (xs[i - 1] + xs[i]) / 2;
      d += ` Q${meio.toFixed(1)} ${VA_TOPO} ${xs[i].toFixed(1)} ${VA_Y}`;
    }
    return d;
  }
  const hDecimal = (min) => (Math.round((min / 60) * 10) / 10).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const fmtMin = (min) => (min >= 60 ? `${Math.floor(min / 60)}h${String(Math.round(min % 60)).padStart(2, "0")}` : `${Math.round(min)} min`);

  function vaInfo(p, i, paradas, pernas, data) {
    const ultima = i === paradas.length - 1;
    const voltou = ultima && i > 0 && p.icao === paradas[0].icao;
    const nome = voltou ? `Volta pra ${paradas[0].nome || p.icao}` : p.nome || p.icao;
    const partes = [];
    if (i === 0) {
      if (p.decola) partes.push(`decola ${p.decola}`);
      if (data.chegar) partes.push(`chega no aeroclube ${data.chegar}`);
    } else {
      const perna = pernas[i - 1] || {};
      partes.push(`perna ${i}${numeroValido(perna.nm) ? `, ${perna.nm} NM` : ""}`);
      if (p.pousa) partes.push(`pousa ~${p.pousa}${p.decola ? `, decola ~${p.decola}` : ""}`);
    }
    return { nome, resto: partes.join(" · ") };
  }

  Cards.registrar("voo_agendado", (data) => {
    const paradas = lista(data.paradas).filter((p) => p && p.icao);
    if (!data || !data.data || paradas.length < 2) return null;
    const pernas = lista(data.pernas);
    const local = !!data.local;
    const dia = Cards.parseDia(data.data);
    const hojeD = Cards.parseDia(isoHoje());
    const dias = dia && hojeD ? Cards.diasEntre(hojeD, dia) : null;
    const quando = [Cards.rotuloDia(data.data), dias > 1 ? `em ${dias} dias` : ""].filter(Boolean).join(" · ");

    let rota;
    if (local) {
      // voo local (sai e volta sem escala): circuito de trafego em volta do aerodromo
      const p = paradas[0];
      rota =
        `<div class="va-local" data-vivo="voo-local"><svg class="va-svg" viewBox="0 0 ${VA_LARG} 70" aria-hidden="true">` +
        `<path class="va-base" d="M70 14 H230 a20 20 0 0 1 20 20 v2 a20 20 0 0 1 -20 20 H70 a20 20 0 0 1 -20 -20 v-2 a20 20 0 0 1 20 -20 Z"/>` +
        `<path class="va-feito" pathLength="1" d="M70 14 H230 a20 20 0 0 1 20 20 v2 a20 20 0 0 1 -20 20 H70 a20 20 0 0 1 -20 -20 v-2 a20 20 0 0 1 20 -20 Z"/>` +
        `<g class="va-aviao" transform="translate(70 14)">${AVIAO_CHEIO}</g></svg>` +
        `<div class="va-local-nome"><b class="vivo-num">${esc(p.icao)}</b><span>voo local · ${esc(p.nome || "")}</span></div></div>`;
    } else {
      const xs = vaPontos(paradas.length);
      const d = vaCaminho(xs);
      const ult = xs[xs.length - 1];
      const legendas = pernas
        .map((pn, i) => (numeroValido(pn && pn.nm) && xs[i + 1] !== undefined
          ? `<span class="va-perna vivo-num" style="left:${(((xs[i] + xs[i + 1]) / 2 / VA_LARG) * 100).toFixed(2)}%">${esc(pn.nm)} NM</span>`
          : ""))
        .join("");
      const botoes = paradas
        .map((p, i) => {
          const info = vaInfo(p, i, paradas, pernas, data);
          const lado = i === 0 ? " va-ini" : i === paradas.length - 1 ? " va-fim" : "";
          const rot = i === paradas.length - 1 && i > 0 && p.icao === paradas[0].icao ? "volta" : p.nome || "";
          return (
            `<button type="button" class="va-parada${lado}" data-acao="voo_parada" data-i="${i}" style="left:${((xs[i] / VA_LARG) * 100).toFixed(2)}%"` +
            ` data-nome="${esc(info.nome)}" data-resto="${esc(info.resto)}" aria-label="${esc(`${p.icao}, ${info.nome}`)}">` +
            `<b class="vivo-num">${esc(p.icao)}</b><span>${esc(rot)}</span></button>`
          );
        })
        .join("");
      rota =
        `<div class="va-rota" data-vivo="voo-rota">` +
        `<svg class="va-svg" viewBox="0 ${VA_TOPO - 2} ${VA_LARG} ${VA_Y - VA_TOPO + 8}" aria-hidden="true">` +
        `<path class="va-base" d="${d}"/><path class="va-feito" pathLength="1" d="${d}"/>` +
        `<g class="va-aviao" transform="translate(${ult.toFixed(1)} ${VA_Y})">${AVIAO_CHEIO}</g></svg>` +
        `<div class="va-legendas">${legendas}</div><div class="va-paradas">${botoes}</div></div>`;
    }

    const resumo = [
      numeroValido(data.total_nm) ? `total <b class="vivo-num">~${esc(data.total_nm)} NM</b>` : "",
      numeroValido(data.duracao_min) ? `fora do chão <b class="vivo-num">~${esc(fmtMin(data.duracao_min))}</b>` : "",
    ].filter(Boolean);
    const etapas = [
      data.sair_casa ? ["Saída", data.sair_casa, numeroValido(data.trajeto_min) ? `${data.trajeto_min} min de carro` : "de casa"] : null,
      data.chegar ? ["Chega", data.chegar, numeroValido(data.antecedencia_min) ? `${data.antecedencia_min} min antes` : ""] : null,
      data.hora ? ["Decola", data.hora, "", true] : null,
      data.pouso ? ["Pousa", `~${data.pouso}`, ""] : null,
    ].filter(Boolean);
    const etapasHTML = etapas.length
      ? `<div class="va-etapas" style="--n:${etapas.length}">` +
        etapas.map(([r, v, s, destaque]) => `<div class="va-etapa${destaque ? " va-destaque" : ""}"><span>${r}</span><b class="vivo-num">${esc(v)}</b>${s ? `<small>${esc(s)}</small>` : ""}</div>`).join("") +
        `</div>`
      : "";

    const meta = numeroValido(data.meta_horas) && data.meta_horas > 0 ? data.meta_horas : 150;
    const feitas = numeroValido(data.horas_min) ? data.horas_min : 0;
    const novo = numeroValido(data.duracao_min) ? data.duracao_min : 0;
    const ja = Math.min(100, (feitas / (meta * 60)) * 100);
    const mais = Math.max(0, Math.min(100 - ja, (novo / (meta * 60)) * 100));
    const horas =
      `<div class="va-horas"><div class="va-horas-topo"><span>Horas de voo</span>` +
      `<b class="vivo-num">${hDecimal(feitas)} h</b>${novo ? `<span class="va-depois">→ <b class="vivo-num">~${hDecimal(feitas + novo)} h</b> depois desse</span>` : ""}` +
      `<span class="va-meta">meta <b class="vivo-num">${esc(meta)} h</b></span></div>` +
      `<div class="va-barra"><i class="va-ja" style="width:${ja.toFixed(2)}%"></i><i class="va-novo" style="left:${ja.toFixed(2)}%;width:${mais.toFixed(2)}%"></i></div></div>`;

    return (
      `<div class="va" data-local="${local ? 1 : 0}">` +
      `<div class="card-resultado-eyebrow">${ICONE_AVIAO}<span>Voo agendado</span>${quando ? `<span class="va-quando">${esc(quando)}</span>` : ""}</div>` +
      rota +
      (resumo.length ? `<p class="va-resumo">${resumo.join(`<span aria-hidden="true">·</span>`)}</p>` : "") +
      (local ? "" : `<p class="va-info" aria-live="polite">${ICONE_AVIAO}<span>Toca num aeródromo pra ver a perna.</span></p>`) +
      etapasHTML +
      `<div class="va-picote" aria-hidden="true"></div>` +
      horas +
      `</div>`
    );
  });

  // ---- aviao no caminho (DOM): posicionar, voar entre paradas, entrada animada
  const reduzido = () => !!(raiz.matchMedia && raiz.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const suave = (k) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);

  function vooControle(caixa) {
    if (caixa._voo) return caixa._voo;
    const base = caixa.querySelector(".va-base");
    const feito = caixa.querySelector(".va-feito");
    const aviao = caixa.querySelector(".va-aviao");
    if (!base || !aviao || typeof base.getTotalLength !== "function") return null;
    const L = base.getTotalLength();
    if (!L) return null;
    const pernas = [...caixa.querySelectorAll(".va-perna")];
    const botoes = [...caixa.querySelectorAll(".va-parada")];
    // fracao do caminho em cada parada (o x cresce sempre, entao busca binaria no x)
    const fracaoNoX = (x) => {
      let lo = 0, hi = L;
      for (let i = 0; i < 28; i++) {
        const m = (lo + hi) / 2;
        if (base.getPointAtLength(m).x < x) lo = m;
        else hi = m;
      }
      return lo / L;
    };
    const xs = vaPontos(botoes.length);
    const paradas = botoes.length ? xs.map((x, i) => (i === 0 ? 0 : i === xs.length - 1 ? 1 : fracaoNoX(x))) : [0, 1];
    let atual = 1, sentido = 1, quadro = 0;
    const pintar = (f, ang) => {
      const p = base.getPointAtLength(L * f);
      aviao.setAttribute("transform", `translate(${p.x.toFixed(2)} ${p.y.toFixed(2)}) rotate(${ang.toFixed(1)})`);
      if (feito) feito.style.strokeDashoffset = String(1 - f);
      pernas.forEach((pn, i) => pn.classList.toggle("va-viu", f >= (paradas[i] + paradas[i + 1]) / 2 - 0.001));
    };
    const angulo = (f) => {
      const a = base.getPointAtLength(L * f);
      const b = base.getPointAtLength(Math.min(L, Math.max(0, L * f + sentido)));
      return (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI;
    };
    function irPara(alvo, msTotal = 2600) {
      cancelAnimationFrame(quadro);
      const de = atual;
      if (Math.abs(alvo - de) < 0.0005) return Promise.resolve();
      sentido = alvo > de ? 1 : -1;
      const dur = reduzido() ? 0 : Math.max(650, Math.abs(alvo - de) * msTotal);
      const t0 = performance.now();
      return new Promise((fim) => {
        const passo = (agora) => {
          const k = dur ? Math.min(1, (agora - t0) / dur) : 1;
          atual = de + (alvo - de) * suave(k);
          // parado na ponta: nariz na horizontal, virado pro lado de onde veio o movimento
          pintar(atual, k < 1 ? angulo(atual) : sentido > 0 ? 0 : 180);
          if (k < 1) quadro = requestAnimationFrame(passo);
          else fim();
        };
        quadro = requestAnimationFrame(passo);
      });
    }
    function ir(de, alvo, ms) {
      atual = de;
      pintar(de, 0);
      return irPara(alvo, ms);
    }
    caixa._voo = { irPara, ir, paradas, pintar: (f) => pintar(f, 0) };
    return caixa._voo;
  }

  function preparar(el) {
    if (!el || !el.querySelectorAll) return;
    el.querySelectorAll('[data-vivo="voo-rota"],[data-vivo="voo-local"]').forEach((caixa) => {
      const c = vooControle(caixa);
      if (c) c.pintar(1);
    });
  }

  function animar(el) {
    if (!el || !el.querySelectorAll || reduzido()) return;
    el.querySelectorAll('[data-vivo="voo-rota"],[data-vivo="voo-local"]').forEach((caixa) => {
      const c = vooControle(caixa);
      if (!c) return;
      c.pintar(0);
      setTimeout(() => c.ir(0, 1, caixa.dataset.vivo === "voo-local" ? 2400 : 2800), 380);
    });
  }

  if (typeof Cards.registrarAcao === "function") Cards.registrarAcao("voo_parada", (btn) => {
    const caixa = btn.closest('[data-vivo="voo-rota"]');
    const card = btn.closest(".va");
    const c = caixa && vooControle(caixa);
    const i = Number(btn.dataset.i);
    if (!c || !Number.isInteger(i) || c.paradas[i] === undefined) return;
    caixa.querySelectorAll(".va-parada").forEach((b) => b.classList.toggle("va-atual", b === btn));
    caixa.querySelectorAll(".va-perna").forEach((pn, k) => pn.classList.toggle("va-foco", k === i - 1));
    c.irPara(c.paradas[i]);
    const info = card && card.querySelector(".va-info span");
    if (info) {
      const novo = document.createElement("span");
      novo.className = "va-troca";
      const forte = document.createElement("b");
      forte.textContent = btn.dataset.nome || "";
      novo.append(forte, btn.dataset.resto ? ` · ${btn.dataset.resto}` : "");
      info.replaceWith(novo);
    }
    if (typeof raiz.vibrar === "function") raiz.vibrar(6);
  });

  const CardsAviacao = { CATEGORIAS, quandoVolta, preparar, animar, vaPontos, vaCaminho };
  raiz.CardsAviacao = CardsAviacao;
  if (typeof module !== "undefined" && module.exports) module.exports = CardsAviacao;
})(typeof window !== "undefined" ? window : globalThis);
