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

  const CardsAviacao = { CATEGORIAS, quandoVolta };
  raiz.CardsAviacao = CardsAviacao;
  if (typeof module !== "undefined" && module.exports) module.exports = CardsAviacao;
})(typeof window !== "undefined" ? window : globalThis);
