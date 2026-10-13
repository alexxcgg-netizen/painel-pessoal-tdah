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

  const CardsAviacao = { CATEGORIAS };
  raiz.CardsAviacao = CardsAviacao;
  if (typeof module !== "undefined" && module.exports) module.exports = CardsAviacao;
})(typeof window !== "undefined" ? window : globalThis);
