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
  // Desde 04/11 é a pílula D (mais abaixo). O cartão de embarque com o arco das pernas saiu; as
  // pernas viram a linha "Rota" (NM e tempo fora do chão).
  const ICONE_AVIAO =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.5 13.5 3 11l1.5-1.5 8 1L17 6a2 2 0 0 1 3 3l-4.5 4.5 1 8L15 23l-2.5-7.5"/></svg>';
  const hDecimal = (min) => (Math.round((min / 60) * 10) / 10).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const fmtMin = (min) => (min >= 60 ? `${Math.floor(min / 60)}h${String(Math.round(min % 60)).padStart(2, "0")}` : `${Math.round(min)} min`);

  // 3a leva (2026-10-14): o TAF so cobre ~30 h - o card so pede a previsao dentro dessa janela
  // e antes do voo passar (a rota /api/voos/<id>/tempo confere de novo e nunca inventa)
  const JANELA_TAF_H = 30;
  function tempoNaJanela(data, agora) {
    if (!numeroValido(data.id) || !data.hora || !/^\d{2}:\d{2}$/.test(data.hora)) return false;
    const d = Cards.parseDia(data.data);
    if (!d) return false;
    const [h, m] = data.hora.split(":").map(Number);
    const quando = new Date(d.getFullYear(), d.getMonth(), d.getDate(), h, m).getTime();
    const ms = quando - agora.getTime();
    return ms > -3600000 && ms <= JANELA_TAF_H * 3600000;
  }

  // ================================================================ projecao
  // "Quando eu chego na meta?" (4a leva, cards.projecao_horas): ritmo dos ultimos 2 meses e o
  // cenario de 1 voo a mais por semana. Conta pura do historico - o servidor manda null quando nao
  // tem voo recente ou a meta ja foi batida, e aqui nao aparece nada.
  const MESES_CURTOS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  const ICONE_PROJ =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/></svg>';
  function mesAno(iso) {
    const d = Cards.parseDia(iso);
    return d ? `${MESES_CURTOS[d.getMonth()]} ${d.getFullYear()}` : ""; // nbsp: "mai 2027" nao quebra
  }
  function partesProjecao(p) {
    if (!p || typeof p !== "object" || !numeroValido(p.ritmo_h_semana) || !numeroValido(p.meta_horas)) return null;
    const meses = Math.max(1, Math.round((numeroValido(p.janela_dias) ? p.janela_dias : 60) / 30));
    const ritmo = Number(p.ritmo_h_semana).toLocaleString("pt-BR", { maximumFractionDigits: 1 });
    const quando = p.data_meta ? mesAno(p.data_meta) : "";
    const mais = p.data_meta_mais_um && p.data_meta_mais_um !== p.data_meta ? mesAno(p.data_meta_mais_um) : "";
    return {
      base: `No ritmo dos últimos ${meses} ${meses === 1 ? "mês" : "meses"} (${ritmo} h/semana)`,
      meta: p.meta_horas,
      quando,
      mais,
    };
  }
  function textoProjecao(p) {
    const t = partesProjecao(p);
    if (!t) return "";
    const fim = t.quando ? `os ${t.meta} h chegam lá por ${t.quando}.` : `os ${t.meta} h ficam pra mais de 5 anos.`;
    return `${t.base}, ${fim}${t.mais ? ` Com 1 voo a mais por semana: ${t.mais}.` : ""}`;
  }
  // Regua "hoje -> meta": os dois cenarios no mesmo trilho. Posicao pura (sem relogio): no ritmo
  // atual a meta fica no fim (100%); com +1 voo/semana chega em ritmo/(ritmo + h por voo) do caminho.
  function projecaoHTML(p) {
    const t = partesProjecao(p);
    if (!t) return "";
    const pv = numeroValido(p.horas_por_voo) && p.horas_por_voo > 0 ? p.horas_por_voo : null;
    const a = pv && p.ritmo_h_semana > 0 ? p.ritmo_h_semana / (p.ritmo_h_semana + pv) : null;
    const falta = numeroValido(p.falta_h) ? Number(p.falta_h).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) : null;
    const ritmo = Number(p.ritmo_h_semana).toLocaleString("pt-BR", { maximumFractionDigits: 1 });
    const meses = Math.max(1, Math.round((numeroValido(p.janela_dias) ? p.janela_dias : 60) / 30));
    const marco = (classe, pos, data, rot) =>
      `<span class="va-proj-m ${classe}" style="--pos:${pos.toFixed(3)}"><i></i><b class="vivo-num">${esc(data)}</b><small>${esc(rot)}</small></span>`;
    return (
      `<div class="va-proj" role="img" aria-label="${esc(textoProjecao(p))}">` +
      `<div class="va-proj-topo">${ICONE_PROJ}<span>Quando chega nos <b class="vivo-num">${esc(t.meta)} h</b></span>` +
      (falta ? `<span class="va-proj-falta">faltam <b class="vivo-num">${esc(falta)} h</b></span>` : "") + `</div>` +
      `<div class="va-proj-regua" aria-hidden="true"><i class="va-proj-trilho"></i><i class="va-proj-cheio"></i><span class="va-proj-hoje">hoje</span>` +
      (t.mais && a !== null ? marco("va-proj-mais", a, t.mais, "+1 voo/semana") : "") +
      marco("va-proj-ritmo", 1, t.quando || "5+ anos", "no ritmo atual") +
      `</div>` +
      `<p class="va-proj-nota">Ritmo dos últimos ${meses} ${meses === 1 ? "mês" : "meses"}: ${esc(ritmo)} h/semana` +
      (numeroValido(p.voos_semana) ? ` (${esc(Number(p.voos_semana).toLocaleString("pt-BR", { maximumFractionDigits: 1 }))} voo/semana)` : "") + `.</p>` +
      `</div>`
    );
  }

  // ===================================================== voo_agendado (linguagem D, 04/11)
  // Pílula "ao vivo" (docs/CARDS.md, cena 3): fechada conta até sair de casa / chegar / decolar
  // (segundos do servidor + gerado_ts). Aberta: seletor dos aeródromos da rota; pra cada um, a pista
  // desenhada gira até a cabeceira em uso e a seta do vento (magnético) vem do METAR de agora
  // (/api/clima/metar, só dentro de 30 h do voo). Pista só quando conferida (SSBL 01/19,
  // aviacao_lab.pista_config); aeródromo sem pista mostra o vento e diz que não conferiu.
  const D = () => raiz.CardsD || (typeof require === "function" ? require("./cards-d.js") : null);
  const LAB = () => raiz.CardsAviacaoLab || (typeof require === "function" ? require("./cards-aviacao-lab.js") : null);
  const cab2 = (n) => String(n).padStart(2, "0");

  function tituloVoo(paradas, local) {
    if (local) return { titulo: `${paradas[0].icao} · voo local`, idaVolta: false };
    const icaos = paradas.map((p) => p.icao).filter((c, i, a) => i === 0 || c !== a[i - 1]);
    const idaVolta = icaos.length > 2 && icaos[0] === icaos[icaos.length - 1];
    const ida = idaVolta ? icaos.slice(0, -1) : icaos;
    return { titulo: ida.join(" → "), idaVolta };
  }

  // o painel de um aeródromo sem METAR ainda ("buscando"); pintarAd preenche no navegador
  function adEsqueleto(ad) {
    const p = ad && ad.pista;
    const cabs = p && Array.isArray(p.cabeceiras) && p.cabeceiras.length === 2 ? p.cabeceiras : null;
    const pista = cabs
      ? `<g class="ad-rw" style="transform:rotate(${cabs[0] * 10}deg)"><rect x="70" y="26" width="20" height="108" rx="2.5" fill="#3a3a3c"/>` +
        `<path d="M80 34v92" stroke="#8e8e93" stroke-width="1" stroke-dasharray="5 5"/>` +
        `<text class="ad-rw-a" x="80" y="128" text-anchor="middle" font-size="10" font-weight="700" fill="#fff">${esc(cab2(cabs[0]))}</text>` +
        `<text class="ad-rw-b" x="80" y="40" text-anchor="middle" font-size="10" font-weight="700" fill="#8e8e93" transform="rotate(180 80 37)">${esc(cab2(cabs[1]))}</text></g>`
      : "";
    const rl = D().rl;
    return (
      `<div class="ad-painel"><div class="ad-pista"><svg viewBox="0 0 160 160" aria-hidden="true">` +
      `<circle cx="80" cy="80" r="72" fill="none" stroke="#2c2c2e" stroke-width="1"/>` +
      `<g fill="#636366" font-size="9" text-anchor="middle"><text x="80" y="17">N</text><text x="147" y="83">L</text><text x="80" y="150">S</text><text x="13" y="83">O</text></g>` +
      pista +
      `<g class="ad-vento" style="transform:rotate(0deg)" visibility="hidden"><path d="M80 4v30" stroke="var(--cc)" stroke-width="3" stroke-linecap="round"/>` +
      `<path d="M72 26l8 11 8-11" fill="none" stroke="var(--cc)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></g></svg></div>` +
      `<div class="ad-num">` +
      (cabs
        ? `<div><small>Cabeceira</small><b>${rl("–", ' data-ad="cab"')}</b></div>` +
          `<div><small>Proa</small><b>${rl("–", ' data-ad="proa"')}<i>kt</i></b></div>` +
          `<div><small>Través</small><b>${rl("–", ' data-ad="trav"')}<i>kt</i></b></div>`
        : `<div><small>Pista</small><b class="nao">não conferi a de ${esc(ad.icao)}</b></div>`) +
      `</div></div>` +
      `<div class="ad-grade"><div><small>Teto</small><b>${rl("–", ' data-ad="teto"')}</b></div>` +
      `<div><small>Visibilidade</small><b>${rl("–", ' data-ad="vis"')}</b></div>` +
      `<div><small>Vento</small><b>${rl("–", ' data-ad="vento"')}</b></div></div>` +
      `<p class="ad-ver" aria-live="polite">Buscando o METAR de ${esc(ad.icao)}...</p>` +
      `<code class="ad-metar" hidden></code>` +
      `<p class="ad-fonte">METAR de agora, não a previsão da hora do voo (essa é o TAF).</p>`
    );
  }

  function aerodromosHTML(data, agora) {
    const ads = lista(data.aerodromos).filter((a) => a && a.icao);
    if (!ads.length) return "";
    if (!tempoNaJanela(data, agora)) {
      return `<p class="ad-vazio">Vento, teto e pista de ${esc(ads.map((a) => a.icao).join(" e "))} aparecem aqui a partir de 30 h antes do voo.</p>`;
    }
    const seg =
      ads.length > 1
        ? `<div class="seg-ad" role="tablist" aria-label="Aeródromo" style="--n:${ads.length};--i:0"><span class="pil" aria-hidden="true"></span>` +
          ads
            .map(
              (a, i) =>
                `<button type="button" role="tab" aria-selected="${i === 0}" data-acao="voo_ad" data-i="${i}">${esc(a.icao)}${a.nome && a.nome !== a.icao ? ` · ${esc(a.nome)}` : ""}</button>`,
            )
            .join("") +
          `</div>`
        : "";
    const limite = numeroValido(data.limite_kt) ? data.limite_kt : "";
    return (
      seg +
      `<div class="ad-vivo" data-ads="${esc(JSON.stringify(ads))}" data-limite="${esc(limite)}" data-i="0">` +
      adEsqueleto(ads[0]) +
      `</div>`
    );
  }

  function linhasVoo(data, prox) {
    const meta = numeroValido(data.meta_horas) && data.meta_horas > 0 ? data.meta_horas : 150;
    const linhas = [
      data.sair_casa ? ["Sair de casa", data.sair_casa, "sair_s"] : null,
      data.chegar
        ? [numeroValido(data.antecedencia_min) ? `Briefing (${data.antecedencia_min} min antes)` : "Chegar no aeroclube", data.chegar, "chegar_s"]
        : null,
      data.hora ? ["Decolagem", data.hora, "decola_s"] : null,
      data.pouso ? ["Pouso", `~${data.pouso}`, ""] : null,
      numeroValido(data.total_nm) || numeroValido(data.duracao_min)
        ? [
            "Rota",
            [numeroValido(data.total_nm) ? `${data.total_nm} NM` : "", numeroValido(data.duracao_min) ? `~${fmtMin(data.duracao_min)} fora do chão` : ""].filter(Boolean).join(" · "),
            "",
          ]
        : null,
      numeroValido(data.horas_min) ? ["Horas no curso", `${hDecimal(data.horas_min)} de ${meta}`, ""] : null,
    ].filter(Boolean);
    if (!linhas.length) return "";
    return (
      `<div class="v-linhas">` +
      linhas.map(([r, v, k]) => `<div class="v-linha${prox && k === prox ? " agora" : ""}"><span>${esc(r)}</span><span>${esc(v)}</span></div>`).join("") +
      `</div>`
    );
  }

  Cards.registrar("voo_agendado", (data, card, ctx) => {
    const paradas = lista(data && data.paradas).filter((p) => p && p.icao);
    if (!data || !data.data || paradas.length < 2) return null;
    const cd = D();
    const agora = (ctx && ctx.agora) || new Date();
    const ag = agora.getTime();
    const { titulo, idaVolta } = tituloVoo(paradas, !!data.local);
    const dia = Cards.parseDia(data.data);
    const delta = dia ? Cards.diasEntre(agora, dia) : null;
    const quando = delta === 0 ? "" : Cards.rotuloDia(data.data);
    const sub = [quando, data.hora ? `Voo ${data.hora}` : "", idaVolta ? "ida e volta" : ""].filter(Boolean).join(" · ");
    const passos = [
      ["sai em", "sair_s"],
      ["chega em", "chegar_s"],
      ["decola em", "decola_s"],
    ];
    const prox = passos.find(([, k]) => numeroValido(data[k]) && cd.restante(data[k], data.gerado_ts, ag) > 0);
    return cd.pilula({
      v: "voo",
      icone: cd.IC.aviao,
      titulo,
      sub: sub ? `<span>${esc(sub)}</span>` : "",
      rotulo: prox ? prox[0] : "",
      valor: prox ? cd.contagem(data[prox[1]], data.gerado_ts, "min", agora) : "",
      corpo:
        aerodromosHTML(data, agora) +
        linhasVoo(data, prox && prox[1]) +
        (tempoNaJanela(data, agora) ? `<div class="va-tempo" data-voo-tempo="${esc(data.id)}" aria-live="polite" hidden></div>` : "") +
        projecaoHTML(data.projecao) +
        cd.botoes(card),
    });
  });

  // ------------------------------------------------ METAR por aeródromo (navegador)
  const METAR_CACHE = new Map();
  async function buscarMetar(icao) {
    const g = METAR_CACHE.get(icao);
    if (g && Date.now() - g.t < 600000) return g.r;
    const api = typeof raiz.apiFetch === "function" ? raiz.apiFetch : null;
    if (!api) return null;
    let r = null;
    try {
      r = await api(`/api/clima/metar?icao=${encodeURIComponent(icao)}`);
    } catch (_) {
      r = null;
    }
    if (r && r.metar) METAR_CACHE.set(icao, { t: Date.now(), r });
    return r && r.metar ? r : null;
  }

  // tudo que o painel mostra a partir do METAR decodificado (puro; testado em Node)
  function valoresAd(ad, res, limite) {
    const dec = (res && res.metar_decodificado) || {};
    const v = dec.vento && typeof dec.vento === "object" ? dec.vento : null;
    const cat = catValida(res && res.metar_categoria);
    const out = {
      teto: numeroValido(dec.teto_ft) ? `${milhar(dec.teto_ft)} ft` : "sem teto",
      vis: visTexto(numeroValido(dec.visibilidade_m) ? dec.visibilidade_m : null),
      vento: "–",
      cat,
      seta: null,
      cab: null,
      proa: null,
      trav: null,
      tom: "",
      ver: "",
      rwGraus: null,
    };
    // a categoria vai no selo ao lado da frase (pintarAd); a frase não repete
    if (!v) {
      out.ver = `Sem vento no METAR de ${ad.icao}.`;
      return out;
    }
    const raj = numeroValido(v.rajada_kt) ? v.rajada_kt : null;
    if (v.velocidade_kt === 0) {
      out.vento = "calmo";
      out.ver = `Vento calmo.`;
      return out;
    }
    if (v.variavel || !numeroValido(v.direcao)) {
      out.vento = `VRB ${v.velocidade_kt} kt`;
      out.ver = `Vento variável, ${v.velocidade_kt} kt${raj ? ` (rajada ${raj})` : ""}.`;
      return out;
    }
    const p = ad.pista;
    const lab = LAB();
    if (p && Array.isArray(p.cabeceiras) && p.cabeceiras.length === 2 && lab) {
      const c = lab.calcVento(v.direcao, v.velocidade_kt, p, true, raj);
      const [tom, txt] = lab.veredito(c, numeroValido(limite) && limite > 0 ? limite : 15, true);
      // a caixa mostra o vento como está no METAR (verdadeiro); a seta, magnética como a pista
      out.vento = `${String(v.direcao).padStart(3, "0")}° ${v.velocidade_kt}${raj ? `G${raj}` : ""} kt`;
      out.seta = c.dm;
      out.cab = lab.cabTxt ? lab.cabTxt(c.cab) : cab2(c.cab);
      out.rwGraus = c.cab * 10;
      out.proa = String(Math.max(0, c.proa));
      out.trav = String(c.trav);
      out.tom = tom;
      out.ver = `${txt}`;
      return out;
    }
    // sem pista conferida: o vento como veio (direção verdadeira do METAR), sem inventar cabeceira
    const dir = String(v.direcao).padStart(3, "0");
    out.vento = `${dir}° ${v.velocidade_kt}${raj ? `G${raj}` : ""} kt`;
    out.seta = v.direcao;
    out.ver = `Vento ${dir}° verdadeiro, ${v.velocidade_kt} kt. A pista daqui eu não conferi, então não calculo través.`;
    return out;
  }

  function pintarAd(caixa, ad, res) {
    const cd = D();
    const val = valoresAd(ad, res, Number(caixa.dataset.limite));
    const q = (s) => caixa.querySelector(s);
    cd.semRolar(() => {
      [["cab", val.cab], ["proa", val.proa], ["trav", val.trav], ["teto", val.teto], ["vis", val.vis], ["vento", val.vento]].forEach(([k, t]) => {
        const el = q(`[data-ad="${k}"]`);
        if (el) cd.rolar(el, t === null ? "–" : t);
      });
      const rw = q(".ad-rw");
      if (rw && val.rwGraus !== null) {
        rw.style.transform = `rotate(${val.rwGraus}deg)`;
        const outra = ad.pista.cabeceiras.find((n) => n * 10 !== val.rwGraus);
        const a = q(".ad-rw-a");
        const b = q(".ad-rw-b");
        if (a) a.textContent = val.cab;
        if (b && outra !== undefined) b.textContent = cab2(outra);
      }
      const seta = q(".ad-vento");
      if (seta) {
        if (val.seta === null) seta.setAttribute("visibility", "hidden");
        else {
          seta.removeAttribute("visibility");
          seta.style.transform = `rotate(${val.seta}deg)`;
        }
      }
      const ver = q(".ad-ver");
      if (ver) {
        ver.className = `ad-ver${val.tom === "alerta" || val.tom === "perigo" ? ` ${val.tom}` : ""}`;
        ver.innerHTML = (val.cat ? `<span class="cat ${val.cat}">${val.cat}</span> ` : "") + esc(val.ver);
      }
      const met = q(".ad-metar");
      if (met) {
        met.textContent = res.metar;
        met.hidden = false;
      }
    });
  }

  async function carregarAd(vivo) {
    const caixa = vivo && vivo.querySelector(".ad-vivo");
    if (!caixa) return;
    let ads = [];
    try {
      ads = JSON.parse(caixa.dataset.ads || "[]");
    } catch (_) {
      ads = [];
    }
    const i = Number(caixa.dataset.i) || 0;
    const ad = ads[i];
    if (!ad || caixa.dataset.pintado === ad.icao) return;
    const res = await buscarMetar(ad.icao);
    if (!caixa.isConnected || (Number(caixa.dataset.i) || 0) !== i) return;
    if (!res) {
      const ver = caixa.querySelector(".ad-ver");
      if (ver) ver.textContent = `Não consegui o METAR de ${ad.icao} agora.`;
      return;
    }
    caixa.dataset.pintado = ad.icao;
    pintarAd(caixa, ad, res);
  }

  if (D()) D().registrarAbrir("voo", (vivo) => carregarAd(vivo));

  if (typeof Cards.registrarAcao === "function") {
    Cards.registrarAcao("voo_ad", (btn) => {
      const vivo = btn.closest(".vivo-d");
      const caixa = vivo && vivo.querySelector(".ad-vivo");
      const seg = btn.closest(".seg-ad");
      const i = Number(btn.dataset.i);
      if (!caixa || !seg || !Number.isInteger(i)) return;
      let ads = [];
      try {
        ads = JSON.parse(caixa.dataset.ads || "[]");
      } catch (_) {
        ads = [];
      }
      if (!ads[i] || Number(caixa.dataset.i) === i) return;
      D().semRolar(() => {
        seg.style.setProperty("--i", i);
        seg.querySelectorAll("[role=tab]").forEach((b) => b.setAttribute("aria-selected", String(b === btn)));
        // outro aeródromo: só pista conferida nos dois mantém o desenho (e ele gira); senão troca
        const tinhaPista = !!caixa.querySelector(".ad-rw");
        const temPista = !!(ads[i].pista && Array.isArray(ads[i].pista.cabeceiras));
        caixa.dataset.i = String(i);
        delete caixa.dataset.pintado;
        if (!(tinhaPista && temPista)) caixa.innerHTML = adEsqueleto(ads[i]);
        else {
          const ver = caixa.querySelector(".ad-ver");
          if (ver) ver.textContent = `Buscando o METAR de ${ads[i].icao}...`;
        }
      });
      if (typeof raiz.vibrar === "function") raiz.vibrar(6);
      carregarAd(vivo);
    });
  }

  const SETA_VENTO =
    '<svg class="va-seta" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20V5M6.5 10.5 12 5l5.5 5.5"/></svg>';

  // vento: a seta aponta PRA ONDE o vento vai (vem de 090 -> aponta pro oeste)
  function ventoCurto(v) {
    if (!v || typeof v !== "object" || v.velocidade_kt === 0) return { html: "<b>calmo</b>", dir: null };
    const kt = `<b class="vivo-num">${esc(v.velocidade_kt)}</b> kt${v.rajada_kt ? ` <span class="va-rajada">G${esc(v.rajada_kt)}</span>` : ""}`;
    if (v.variavel || !numeroValido(v.direcao)) return { html: `VRB ${kt}`, dir: null };
    return { html: `${String(v.direcao).padStart(3, "0")}° ${kt}`, dir: (v.direcao + 180) % 360 };
  }

  function tempoHTML(p) {
    const cat = catValida(p.categoria);
    const vento = ventoCurto(p.vento);
    const teto = numeroValido(p.teto_ft) ? `${milhar(p.teto_ft)} <small>ft</small>` : "sem teto";
    const fen = lista(p.fenomenos).slice(0, 2).map((f) => `<span class="bv-fen">${esc(f)}</span>`).join("");
    const pode = lista(p.pode_ter)
      .filter((x) => x && x.resumo)
      .map((x) => {
        const c = catValida(x.categoria);
        return `<li>${c ? `<em class="va-cat va-cat-${c}">${c}</em>` : ""}<span><b>${esc(x.rotulo || "pode ter")}:</b> ${esc(x.resumo)}${x.vento ? ` · ${esc(x.vento)}` : ""}</span></li>`;
      })
      .join("");
    const fonte = p.substituto_de ? `TAF de ${esc(p.icao)} (perto de ${esc(p.substituto_de)})` : `TAF de ${esc(p.icao)}`;
    const seta = vento.dir === null ? "" : SETA_VENTO.replace('class="va-seta"', `class="va-seta" style="--dir:${vento.dir}deg"`);
    return (
      `<div class="va-tempo-cab"><span class="va-tempo-tit">Tempo às <b class="vivo-num">${esc(p.hora || "")}</b></span>` +
      (cat ? `<em class="va-cat va-cat-${cat}" title="${esc(CATEGORIAS[cat].dica)}">${cat}</em>` : "") + `</div>` +
      `<div class="va-tempo-linha">` +
      `<span class="va-tempo-item">${seta}<span>${vento.html}</span></span>` +
      `<span class="va-tempo-item"><small>teto</small><span class="vivo-num">${teto}</span></span>` +
      `<span class="va-tempo-item"><small>vis</small><span class="vivo-num">${visTexto(numeroValido(p.visibilidade_m) ? p.visibilidade_m : null)}</span></span>` +
      `</div>` +
      (fen ? `<div class="bv-chips">${fen}</div>` : "") +
      (pode ? `<ul class="va-tempo-pode">${pode}</ul>` : "") +
      `<p class="va-tempo-nota">${fonte} · ${esc(p.aviso || "Previsão convertida, não é liberação: a decisão é tua e do instrutor.")}</p>`
    );
  }

  // guarda a resposta por 10 min: o chat re-renderiza o historico e nao precisa pedir de novo
  const TEMPO_CACHE = new Map();
  async function preencherTempo(slot) {
    if (slot.dataset.pedido) return;
    slot.dataset.pedido = "1";
    const id = slot.dataset.vooTempo;
    const api = typeof raiz.apiFetch === "function" ? raiz.apiFetch : null;
    let prev = null;
    const guardado = TEMPO_CACHE.get(id);
    if (guardado && Date.now() - guardado.t < 600000) prev = guardado.prev;
    else if (api) {
      try {
        const res = await api(`/api/voos/${encodeURIComponent(id)}/tempo`);
        prev = res && res.previsao && typeof res.previsao === "object" ? res.previsao : null;
        if (res && res.ok) TEMPO_CACHE.set(id, { t: Date.now(), prev });
      } catch (_) {
        prev = null;
      }
    }
    if (!prev || !slot.isConnected) return;
    slot.innerHTML = tempoHTML(prev);
    slot.dataset.categoria = catValida(prev.categoria) || "";
    slot.hidden = false;
    if (!(guardado && guardado.prev)) slot.classList.add("va-tempo-chegou");
  }

  // ================================================================ voo_horas
  // "Pousou? Quanto deu?" (3a leva): um toque num chip grava as horas e a barra anda na hora.
  const fmtH = (h) => Number(h).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const HORAS_MIN = 0.1;
  const HORAS_MAX = 12;

  function vhStatus(horas, outrosMin, meta) {
    if (!numeroValido(horas)) return "Um toque e eu somo nas horas do curso.";
    const falta = Math.max(0, meta - (outrosMin / 60 + horas));
    return falta <= 0 ? `Somei ${fmtH(horas)} h — meta de ${meta} h batida!` : `Somei ${fmtH(horas)} h — faltam ${fmtH(falta)} h pra meta.`;
  }
  function vhBarra(outrosMin, horas, meta) {
    const ja = Math.min(100, (outrosMin / (meta * 60)) * 100);
    const mais = numeroValido(horas) ? Math.max(0, Math.min(100 - ja, ((horas * 60) / (meta * 60)) * 100)) : 0;
    return { ja: ja.toFixed(2), mais: mais.toFixed(2) };
  }

  Cards.registrar("voo_horas", (data) => {
    if (!data || !numeroValido(data.id)) return null;
    const meta = numeroValido(data.meta_horas) && data.meta_horas > 0 ? data.meta_horas : 150;
    const outros = numeroValido(data.horas_min) ? data.horas_min : 0;
    const escolhida = numeroValido(data.horas) ? Math.round(data.horas * 10) / 10 : null;
    const est = numeroValido(data.estimativa) ? Math.round(data.estimativa * 10) / 10 : null;
    let chips = lista(data.sugestoes).filter(numeroValido).map((h) => Math.round(h * 10) / 10);
    if (!chips.length) chips = [1.0, 1.2, 1.5];
    if (escolhida !== null && !chips.includes(escolhida)) chips = [...chips, escolhida].sort((a, b) => a - b);
    const botoes = chips
      .map(
        (h, k) =>
          `<button type="button" role="radio" aria-checked="${h === escolhida}" class="vh-chip${h === est ? " vh-est" : ""}${h === escolhida ? " atual" : ""}" data-acao="voo_horas" data-h="${h}" style="--k:${k}">` +
          `<b class="vivo-num">${fmtH(h)}</b><small>${h === est ? "estimativa" : "h"}</small></button>`
      )
      .join("");
    const inicio = escolhida !== null ? escolhida : est !== null ? est : 1.0;
    const barra = vhBarra(outros, escolhida, meta);
    const quando = [data.rota || (data.icao ? `voo local · ${data.icao}` : ""), data.hora ? `decolou ${data.hora}` : ""].filter(Boolean).join(" · ");
    return (
      `<div class="vh" data-voo="${esc(data.id)}" data-outros="${esc(outros)}" data-meta="${esc(meta)}">` +
      `<div class="card-resultado-eyebrow">${ICONE_AVIAO}<span>Quanto deu o voo?</span>${data.data ? `<span class="va-quando">${esc(Cards.rotuloDia(data.data) || "")}</span>` : ""}</div>` +
      (quando ? `<p class="vh-rota vivo-num">${esc(quando)}</p>` : "") +
      `<div class="vh-chips" role="radiogroup" aria-label="Horas do voo">${botoes}` +
      `<button type="button" class="vh-chip vh-outro" data-acao="voo_horas_outro" aria-expanded="false" style="--k:${chips.length}"><b>outro</b><small>±0,1</small></button></div>` +
      `<div class="vh-ajuste" hidden><button type="button" class="vh-passo" data-acao="voo_horas_passo" data-d="-1" aria-label="menos 0,1 hora">−</button>` +
      `<output class="vh-valor vivo-num" data-h="${inicio}">${fmtH(inicio)}<small> h</small></output>` +
      `<button type="button" class="vh-passo" data-acao="voo_horas_passo" data-d="1" aria-label="mais 0,1 hora">+</button>` +
      `<button type="button" class="vh-salvar" data-acao="voo_horas" data-h="${inicio}">Salvar</button></div>` +
      `<div class="va-horas"><div class="va-horas-topo"><span>Horas de voo</span>` +
      `<b class="vivo-num vh-total">${hDecimal(outros + (escolhida || 0) * 60)} h</b>` +
      `<span class="va-meta">meta <b class="vivo-num">${esc(meta)} h</b></span></div>` +
      `<div class="va-barra"><i class="va-ja" style="width:${barra.ja}%"></i><i class="va-novo" style="left:${barra.ja}%;width:${barra.mais}%"></i></div></div>` +
      `<p class="vh-status${escolhida !== null ? " ok" : ""}" aria-live="polite">${esc(vhStatus(escolhida, outros, meta))}</p>` +
      projecaoHTML(data.projecao) +
      `</div>`
    );
  });

  function vhAplicar(vh, horas, outros) {
    const meta = Number(vh.dataset.meta) || 150;
    if (numeroValido(outros)) vh.dataset.outros = String(outros);
    const out = Number(vh.dataset.outros) || 0;
    vh.querySelectorAll(".vh-chip[data-h]").forEach((b) => {
      const sim = numeroValido(horas) && Math.abs(Number(b.dataset.h) - horas) < 0.001;
      b.classList.toggle("atual", sim);
      b.setAttribute("aria-checked", String(sim));
    });
    const barra = vhBarra(out, horas, meta);
    const ja = vh.querySelector(".va-ja");
    const novo = vh.querySelector(".va-novo");
    if (ja) ja.style.width = `${barra.ja}%`;
    if (novo) {
      novo.style.left = `${barra.ja}%`;
      novo.style.width = `${barra.mais}%`;
    }
    const total = vh.querySelector(".vh-total");
    if (total) total.textContent = `${hDecimal(out + (numeroValido(horas) ? horas * 60 : 0))} h`;
    const st = vh.querySelector(".vh-status");
    if (st) {
      st.textContent = vhStatus(horas, out, meta);
      st.classList.toggle("ok", numeroValido(horas));
      st.classList.remove("va-troca");
      void st.offsetWidth;
      st.classList.add("va-troca");
    }
  }

  // ================================================================ vespera_voo
  // Vespera do voo (4a leva, conversa_proativa.vespera_do_voo - so quando tem voo com hora):
  // "Acorda HH:MM" grande, linha acorda -> sai -> chega -> decola (mesma linha dos compromissos,
  // cards-saidas.css), a faixa do TAF na hora do voo e a mochila que marca (estado no servidor,
  // /api/voos/<id>/mochila - o historico pede de novo no preparar).
  const ICONE_LUA =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z"/></svg>';
  const ICONE_CHECK =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12.5 4.2 4L19 7"/></svg>';
  const ICONE_RELOGIO =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg>';
  const horaOk = (h) => typeof h === "string" && /^\d{2}:\d{2}$/.test(h);
  const contaMochila = (feitos, total) => (feitos >= total ? "mochila fechada" : `${feitos} de ${total}`);
  const ICONE_DESPERTADOR =
    '<svg class="vv-despertador" viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="16" cy="17.5" r="9.5"/><path d="M16 12v5.5l3.5 2.2"/><path class="vv-sino" d="M5 8.5 8.5 5M27 8.5 23.5 5"/><path d="M10 26.5 8 29M22 26.5 24 29"/></svg>';
  const ICONE_MOCHILA =
    '<svg class="vv-mochila-ico" viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 7V5.5a4 4 0 0 1 8 0V7"/><rect x="7" y="7" width="18" height="21" rx="6"/><path class="vv-ziper" d="M11 15h10"/><rect x="11" y="19" width="10" height="6" rx="2"/><path class="vv-ok" d="m12.5 15.2 2.6 2.5 5-5.2"/></svg>';
  // "pra 8 h de sono, na cama ate" = acordar - 8h (volta pro dia anterior)
  const SONO_H = 8;
  const deitarAte = (acordar) => {
    const [h, m] = acordar.split(":").map(Number);
    const t = (h * 60 + m - SONO_H * 60 + 1440) % 1440;
    return `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`;
  };

  Cards.registrar("vespera_voo", (data, _card, ctx) => {
    if (!data || !numeroValido(data.id) || !horaOk(data.hora) || !horaOk(data.acordar)) return null;
    const agora = (ctx && ctx.agora) || new Date();
    const paradas = [
      ["acorda", data.acordar],
      ["sai de casa", data.sair],
      [`chega ${data.icao || ""}`.trim(), data.chegar],
      ["decola", data.hora],
    ].filter(([, h]) => horaOk(h));
    const linha =
      `<div class="sd-linha" style="--n:${paradas.length}">` +
      paradas
        .map(([rot, h], i) => `<div class="sd-parada${i === 0 ? " destaque" : ""}" style="--k:${i}"><i></i><b class="vivo-num">${esc(h)}</b><span>${esc(rot)}</span></div>`)
        .join("") +
      `</div>`;
    const folgas = [
      numeroValido(data.arrumar_min) ? `<b class="vivo-num">${esc(data.arrumar_min)} min</b> pra se arrumar` : "",
      numeroValido(data.trajeto_min) ? `<b class="vivo-num">${esc(data.trajeto_min)} min</b> de carro${numeroValido(data.transito_min) && data.transito_min >= 3 ? ` (+${esc(data.transito_min)} de trânsito)` : ""}` : "",
      numeroValido(data.antecedencia_min) ? `chega <b class="vivo-num">${esc(data.antecedencia_min)} min</b> antes` : "",
      horaOk(data.pouso) ? `pousa <b class="vivo-num">~${esc(data.pouso)}</b>` : "",
    ].filter(Boolean);
    const itens = lista(data.mochila).filter((it) => it && it.texto);
    const feitos = itens.filter((it) => it.feito).length;
    const mochila = itens.length
      ? `<div class="vv-mochila" data-mochila-voo="${esc(data.id)}">` +
        `<div class="vv-mochila-topo">${ICONE_MOCHILA}<span class="sd-rotulo">Mochila</span><span class="vv-conta vivo-num${feitos >= itens.length ? " completa" : ""}" data-total="${itens.length}">${esc(contaMochila(feitos, itens.length))}</span></div>` +
        `<ul class="sd-check">` +
        itens
          .map(
            (it, i) =>
              `<li class="${it.feito ? "marcado" : ""}" style="--k:${i}"><button type="button" class="sd-check-item" data-acao="mochila_item" data-voo="${esc(data.id)}" data-i="${i}" aria-pressed="${!!it.feito}">` +
              `<span class="sd-caixinha">${ICONE_CHECK}</span><span class="sd-item-txt">${esc(it.texto)}</span></button></li>`
          )
          .join("") +
        `</ul></div>`
      : "";
    const sub = [data.rota || (data.icao ? `voo local · ${data.icao}` : ""), `decola ${data.hora}`].filter(Boolean).join(" · ");
    return (
      `<div class="sd vv" data-voo="${esc(data.id)}">` +
      `<div class="card-resultado-eyebrow">${ICONE_LUA}<span>Véspera do voo</span><span class="sd-quando">${esc(Cards.rotuloDia(data.data, agora) || "")}</span></div>` +
      `<div class="vv-hero">${ICONE_DESPERTADOR}<span class="vv-hero-rot">Acorda</span><b class="vivo-num">${esc(data.acordar)}</b>` +
      `<span class="vv-hero-sub vivo-num">${esc(sub)}</span>` +
      `<span class="vv-sono">${ICONE_LUA}<span>Pra ${SONO_H} h de sono, na cama até <b class="vivo-num">${esc(deitarAte(data.acordar))}</b>.</span></span></div>` +
      linha +
      (folgas.length ? `<p class="vv-folgas">${ICONE_RELOGIO}<span>${folgas.map((f) => `<span class="vv-f">${f}</span>`).join(`<i aria-hidden="true">·</i>`)}</span></p>` : "") +
      (tempoNaJanela(data, agora) ? `<div class="va-tempo" data-voo-tempo="${esc(data.id)}" aria-live="polite" hidden></div>` : "") +
      mochila +
      `<p class="sd-status">${ICONE_AVIAO}<span>De manhã eu mando o METAR atualizado e a hora de sair.</span></p>` +
      `</div>`
    );
  });

  function marcarMochila(cardEl, feitos) {
    const itens = cardEl.querySelectorAll(".vv-mochila li");
    lista(feitos).forEach((f, i) => {
      const li = itens[i];
      if (!li) return;
      li.classList.toggle("marcado", !!f);
      const b = li.querySelector("[data-acao]");
      if (b) b.setAttribute("aria-pressed", String(!!f));
    });
    contarMochila(cardEl);
  }
  function contarMochila(cardEl) {
    const conta = cardEl.querySelector(".vv-conta");
    if (!conta) return;
    const total = Number(conta.dataset.total) || 0;
    const n = cardEl.querySelectorAll(".vv-mochila li.marcado").length;
    conta.textContent = contaMochila(n, total);
    const completa = total > 0 && n >= total;
    conta.classList.toggle("completa", completa);
    const caixa = cardEl.closest ? (cardEl.classList.contains("vv-mochila") ? cardEl : cardEl.querySelector(".vv-mochila")) : null;
    if (caixa) caixa.classList.toggle("fechada", completa);
  }
  async function carregarMochila(caixa) {
    if (caixa.dataset.pedido) return;
    caixa.dataset.pedido = "1";
    const api = typeof raiz.apiFetch === "function" ? raiz.apiFetch : null;
    if (!api) return;
    let res = null;
    try {
      res = await api(`/api/voos/${encodeURIComponent(caixa.dataset.mochilaVoo)}/mochila`);
    } catch (_) {
      res = null;
    }
    if (res && res.ok && caixa.isConnected) marcarMochila(caixa, res.feitos);
  }

  function preparar(el) {
    if (!el || !el.querySelectorAll) return;
    el.querySelectorAll("[data-voo-tempo]").forEach((slot) => preencherTempo(slot));
    el.querySelectorAll("[data-mochila-voo]").forEach((caixa) => carregarMochila(caixa));
  }

  // a pílula D do voo anima pela casca (cards-d.js); aqui não sobrou entrada própria
  function animar() {}

  if (typeof Cards.registrarAcao === "function") {
    Cards.registrarAcao("voo_horas", async (btn, _cardEl, deps) => {
      const vh = btn.closest(".vh");
      const horas = Math.round(Number(btn.dataset.h) * 10) / 10;
      if (!vh || vh.dataset.enviando || typeof deps.apiFetch !== "function" || !(horas >= HORAS_MIN && horas <= HORAS_MAX)) return;
      const antes = vh.querySelector(".vh-chip.atual");
      const antesH = antes ? Number(antes.dataset.h) : null;
      if (btn.classList.contains("vh-salvar") && !vh.querySelector(`.vh-chip[data-h="${horas}"]`)) {
        // valor do "outro" vira um chip (fica marcado e da pra trocar depois)
        const outro = vh.querySelector(".vh-outro");
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "vh-chip";
        chip.setAttribute("role", "radio");
        chip.dataset.acao = "voo_horas";
        chip.dataset.h = String(horas);
        chip.innerHTML = `<b class="vivo-num">${fmtH(horas)}</b><small>h</small>`;
        if (outro) outro.before(chip);
      }
      vhAplicar(vh, horas); // otimista: a barra ja anda
      const ajuste = vh.querySelector(".vh-ajuste");
      if (ajuste) ajuste.hidden = true;
      const outroBtn = vh.querySelector(".vh-outro");
      if (outroBtn) outroBtn.setAttribute("aria-expanded", "false");
      if (typeof raiz.vibrar === "function") raiz.vibrar(8);
      vh.dataset.enviando = "1";
      let res = null;
      try {
        res = await deps.apiFetch(`/api/voos/${encodeURIComponent(vh.dataset.voo)}/horas`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ horas }),
        });
      } catch (_) {
        res = null;
      }
      delete vh.dataset.enviando;
      if (!res || !res.ok) {
        vhAplicar(vh, antesH);
        return;
      }
      vhAplicar(vh, res.horas, numeroValido(res.horas_min) ? res.horas_min - Math.round(res.horas * 60) : undefined);
      const marcado = vh.querySelector(".vh-chip.atual b");
      if (marcado && antesH === null && raiz.CardsPremium && typeof raiz.CardsPremium.festejar === "function") raiz.CardsPremium.festejar(marcado);
      if (typeof deps.aoMudar === "function") deps.aoMudar();
    });

    Cards.registrarAcao("mochila_item", async (btn, cardEl, deps) => {
      if (typeof deps.apiFetch !== "function" || btn.dataset.enviando) return;
      const li = btn.closest("li");
      const caixa = btn.closest(".vv-mochila");
      if (!li || !caixa) return;
      const feito = !li.classList.contains("marcado");
      li.classList.toggle("marcado", feito); // otimista
      btn.setAttribute("aria-pressed", String(feito));
      if (feito) {
        li.classList.remove("voou");
        void li.offsetWidth;
        li.classList.add("voou");
      }
      contarMochila(caixa);
      const ico = caixa.querySelector(".vv-mochila-ico");
      if (ico && feito) {
        ico.classList.remove("pulou");
        void ico.getBoundingClientRect();
        ico.classList.add("pulou");
      }
      if (typeof raiz.vibrar === "function") raiz.vibrar(feito && caixa.querySelectorAll("li:not(.marcado)").length === 0 ? [10, 40, 16] : 8);
      btn.dataset.enviando = "1";
      let res = null;
      try {
        res = await deps.apiFetch(`/api/voos/${encodeURIComponent(btn.dataset.voo)}/mochila`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ i: Number(btn.dataset.i), feito }),
        });
      } catch (_) {
        res = null;
      }
      delete btn.dataset.enviando;
      if (!res || !res.ok) {
        li.classList.toggle("marcado", !feito);
        btn.setAttribute("aria-pressed", String(!feito));
        contarMochila(caixa);
      }
    });

    Cards.registrarAcao("voo_horas_outro", (btn) => {
      const vh = btn.closest(".vh");
      const ajuste = vh && vh.querySelector(".vh-ajuste");
      if (!ajuste) return;
      ajuste.hidden = !ajuste.hidden;
      btn.setAttribute("aria-expanded", String(!ajuste.hidden));
      if (!ajuste.hidden) ajuste.classList.add("va-troca");
    });

    Cards.registrarAcao("voo_horas_passo", (btn) => {
      const vh = btn.closest(".vh");
      const valor = vh && vh.querySelector(".vh-valor");
      const salvar = vh && vh.querySelector(".vh-salvar");
      if (!valor || !salvar) return;
      const atual = Number(valor.dataset.h) || 1;
      const novo = Math.min(HORAS_MAX, Math.max(HORAS_MIN, Math.round((atual + Number(btn.dataset.d) * 0.1) * 10) / 10));
      valor.dataset.h = String(novo);
      salvar.dataset.h = String(novo);
      valor.innerHTML = `<span class="va-troca">${fmtH(novo)}</span><small> h</small>`;
      if (typeof raiz.vibrar === "function") raiz.vibrar(4);
    });
  }

  const CardsAviacao = { CATEGORIAS, quandoVolta, preparar, animar, tempoHTML, tempoNaJanela, textoProjecao, projecaoHTML, tituloVoo, valoresAd, adEsqueleto };
  raiz.CardsAviacao = CardsAviacao;
  if (typeof module !== "undefined" && module.exports) module.exports = CardsAviacao;
})(typeof window !== "undefined" ? window : globalThis);
