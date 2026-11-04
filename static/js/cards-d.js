// Casca D "Ao vivo" dos cards do chat (aprovada pelo Alex em 04/11/2026 - docs/CARDS.md "Linguagem
// visual", briefing docs/briefings/2026-11-04-cards-ao-vivo.md, protótipo cards-sem-ia.html aba D).
//
//  - Fechado: pílula escura lisa (sem borda brilhante): ícone num círculo com a cor do assunto,
//    título, linha do tempo embaixo e, à direita, um rótulo pequeno + o valor ao vivo.
//  - Toque abre: grid-rows 0fr -> 1fr com mola cubic-bezier(.32,1.2,.42,1); o conteúdo entra com
//    fade/blur. Números trocam rolando, só o dígito que mudou (rolar).
//  - Contagem ao vivo por segundo. O servidor manda SEGUNDOS até o evento (`*_s`) e `gerado_ts`
//    (época Unix de quando montou o card, sem fuso); o front desconta o que passou desde então e
//    nunca lê hora absoluta de parede pra contar (regra de tempo.py: servidor e celular podem estar
//    em fusos diferentes).
//
// Os renderizadores continuam PUROS (estado final, histórico abre parado, testes em Node): aqui
// tem os pedaços de HTML (pilula, cadeia, tempo hora a hora, o que levar, botões) e, no navegador,
// o relógio de 1 s, o abre/fecha e o rolar dos dígitos. Também registra o type novo `lugar_salvo`.
(function (raiz) {
  "use strict";
  const Cards = raiz.Cards || (typeof require === "function" ? require("./cards.js") : null);
  if (!Cards) return;
  const { esc, numeroValido } = Cards;

  const reduzido = () => !!(raiz.matchMedia && raiz.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const pad = (n) => String(n).padStart(2, "0");
  const lista = (v) => (Array.isArray(v) ? v : []);

  // ícones cheios/finos do protótipo D (24x24, currentColor)
  const traco = (corpo, w = 2) =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${corpo}</svg>`;
  const cheio = (d) => `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="${d}"/></svg>`;
  const IC = {
    coracao: cheio("M12 20.6l-1.3-1.2C6 15.2 3 12.4 3 8.9 3 6.1 5.2 4 7.9 4c1.6 0 3.1.7 4.1 1.9C13 4.7 14.5 4 16.1 4 18.8 4 21 6.1 21 8.9c0 3.5-3 6.3-7.7 10.5L12 20.6z"),
    lua: cheio("M20.5 14.2A8.5 8.5 0 019.8 3.5a8.5 8.5 0 1010.7 10.7z"),
    aviao: cheio("M21 15.5v-1.7l-8-5V3.3a1.3 1.3 0 00-2.6 0v5.5l-8 5v1.7l8-2.4v5.4l-2 1.5V21l3.3-1 3.3 1v-1.5l-2-1.5v-5.4l8 2.4z"),
    pin: cheio("M12 2a7 7 0 00-7 7c0 5.2 7 13 7 13s7-7.8 7-13a7 7 0 00-7-7zm0 9.5A2.5 2.5 0 1112 6a2.5 2.5 0 010 5.5z"),
    raio: cheio("M13.5 2L4 13.5h7L10 22l10-12h-7l.5-8z"),
    carro: traco('<path d="M5 17h14v-4l-2-5H7l-2 5v4z"/><circle cx="8" cy="17" r="1.6"/><circle cx="16" cy="17" r="1.6"/><path d="M5 13h14"/>'),
    carroCheio: traco('<path d="M5 17h14v-4l-2-5H7l-2 5v4z"/><path d="M5 13h14"/>', 2.4),
    relogio: traco('<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>'),
    carrinho: traco('<path d="M3 6h2l2.2 10.2a1.5 1.5 0 001.5 1.2h8.6a1.5 1.5 0 001.5-1.1L21 9H6"/><circle cx="9" cy="21" r=".8"/><circle cx="18" cy="21" r=".8"/>'),
    check: traco('<path d="M5 12.5l4.5 4.5L19 7.5"/>', 2.8),
    seta: traco('<path d="M5 12h14M13 6l6 6-6 6"/>', 2.6),
    chuva: traco('<path d="M17.5 14H8a5 5 0 114.8-6.5h1.2a3.5 3.5 0 013.5 6.5z"/><path d="M8 17.5l-1 2.5M12 17.5l-1 2.5M16 17.5l-1 2.5"/>'),
    nuvem: traco('<path d="M17.5 18H8a5 5 0 114.8-6.5h1.2a3.5 3.5 0 013.5 6.5z"/>'),
    sol: traco('<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/>'),
    guardaChuva: traco('<path d="M12 3a9 9 0 019 9H3a9 9 0 019-9z"/><path d="M12 12v6.5a2 2 0 01-4 0"/>'),
    casaco: traco('<path d="M8 3l4 3 4-3 4 3-2 4h-2v11H8V10H6L4 6z"/>'),
    tarefa: traco('<rect x="4" y="4" width="16" height="16" rx="4"/><path d="M8.5 12l2.5 2.5 4.5-5"/>'),
  };

  // ------------------------------------------------------------------ tempo e contagem (puro)

  // segundos que faltam AGORA: o que o servidor mandou menos o que passou desde que ele montou o card
  function restante(segundos, geradoTs, agoraMs) {
    if (!numeroValido(segundos)) return null;
    const agora = numeroValido(agoraMs) ? agoraMs : Date.now();
    const passou = numeroValido(geradoTs) ? agora / 1000 - geradoTs : 0;
    return segundos - Math.max(0, passou);
  }

  // "min": "14 min" / "1h20" / "agora"; "mmss": "13:59" / "1:02:03"
  function fmtCd(rest, fmt) {
    const r = Math.max(0, Number(rest) || 0);
    if (fmt === "mmss") {
      const s = Math.ceil(r);
      const h = Math.floor(s / 3600);
      const m = Math.floor((s % 3600) / 60);
      return h ? `${h}:${pad(m)}:${pad(s % 60)}` : `${m}:${pad(s % 60)}`;
    }
    if (r <= 0) return "agora";
    const mm = Math.ceil(r / 60);
    if (mm >= 48 * 60) return `${Math.round(mm / 1440)} dias`;
    return mm >= 60 ? `${Math.floor(mm / 60)}h${pad(mm % 60)}` : `${mm} min`;
  }

  // HH:MM a partir de "minutos do dia" (aceita passar da meia-noite)
  const hm = (min) => `${pad(Math.floor((((min % 1440) + 1440) % 1440) / 60))}:${pad((((min % 60) + 60) % 60))}`;
  const minDia = (h) => {
    const m = /^(\d{1,2}):(\d{2})/.exec(h || "");
    return m ? +m[1] * 60 + +m[2] : null;
  };

  // ------------------------------------------------------------------ dígitos que rolam

  const charSpan = (c, extra = "") => `<span${extra}>${c === " " ? "&nbsp;" : esc(c)}</span>`;
  // texto pronto (estado final): o leitor de tela lê o .rl-sr; os caracteres são só desenho
  function rl(txt, attrs = "") {
    const t = String(txt == null ? "" : txt);
    return `<span class="rl"${attrs} data-txt="${esc(t)}"><span class="rl-sr">${esc(t)}</span><span class="rl-c" aria-hidden="true">${[...t].map((c) => charSpan(c)).join("")}</span></span>`;
  }
  // contagem viva: o texto inicial já sai certo pro relógio do ctx (puro); o relógio de 1 s segue
  function contagem(segundos, geradoTs, fmt, agora) {
    const ag = agora instanceof Date ? agora.getTime() : Date.now();
    const r = restante(segundos, geradoTs, ag);
    if (r === null) return "";
    return rl(fmtCd(r, fmt), ` data-cd-s="${esc(segundos)}" data-cd-g="${numeroValido(geradoTs) ? esc(geradoTs) : ""}" data-fmt="${fmt === "mmss" ? "mmss" : "min"}"`);
  }

  // DOM: troca o texto; só o caractere que mudou entra rolando (placar)
  function rolar(el, txt, semAnimar) {
    if (!el) return;
    const t = String(txt);
    const antigo = el.getAttribute("data-txt");
    if (antigo === t) return;
    el.setAttribute("data-txt", t);
    const sr = el.querySelector(".rl-sr");
    if (sr) sr.textContent = t;
    const anima = !semAnimar && !reduzido() && antigo !== null;
    const html = [...t]
      .map((c, i) => charSpan(c, anima && antigo[i] !== c ? ` class="novo" style="animation-delay:${i * 22}ms"` : ""))
      .join("");
    const caixa = el.querySelector(".rl-c");
    if (caixa) caixa.innerHTML = html;
    else el.innerHTML = `<span class="rl-sr">${esc(t)}</span><span class="rl-c" aria-hidden="true">${html}</span>`;
  }

  // ------------------------------------------------------------------ pedaços de HTML (puros)

  // o: {v, cor, icone, anel, titulo, sub (html pronto), rotulo, valor (html pronto), corpo (html), aberto, attrs}
  function pilula(o) {
    const aberto = o.aberto ? "true" : "false";
    return (
      `<div class="vivo-d" data-v="${esc(o.v || "")}" style="--cc:${o.cor || "var(--card-cor)"}" aria-expanded="${aberto}"${o.attrs || ""}>` +
      `<button type="button" class="v-top" aria-expanded="${aberto}">` +
      `<span class="v-ic" aria-hidden="true">${o.anel || ""}${o.icone || ""}</span>` +
      `<span class="v-tx"><span class="v-t">${esc(o.titulo || "")}</span>${o.sub ? `<span class="v-s">${o.sub}</span>` : ""}</span>` +
      (o.valor ? `<span class="v-dir">${o.rotulo ? `<small>${esc(o.rotulo)}</small>` : ""}<b>${o.valor}</b></span>` : "") +
      `</button>` +
      `<div class="v-in"><div class="v-cont">${o.corpo || ""}</div></div>` +
      `</div>`
    );
  }

  // botões em pílula: o que o renderizador mandou (`extra`) + as actions do card que mexem em
  // dado ou abrem algo (Desfazer, Waze/Maps, Abrir aba). O rodapé padrão some no card D (cards.js).
  function botoes(card, extra, tipos) {
    const quais = tipos || ["desfazer", "abrir_link", "abrir_aba", "despertar"];
    const acoes = lista(card && card.actions)
      .filter((a) => a && quais.includes(a.tipo))
      .sort((a, b) => quais.indexOf(a.tipo) - quais.indexOf(b.tipo))
      .map(Cards.acaoHTML)
      .join("");
    const html = (extra || "") + acoes;
    return html ? `<div class="v-bts">${html}</div>` : "";
  }

  // Se arrumar -> Sair -> (Parada) -> Chegar: caixas com a hora; a última na cor do assunto
  function cadeia(passos) {
    const ps = lista(passos).filter((p) => p && p.hora && p.rotulo);
    if (!ps.length) return "";
    return (
      `<div class="v-cadeia" style="--n:${ps.length}">` +
      ps.map((p) => `<div${p.parada ? ' class="parada"' : ""}><small>${esc(p.rotulo)}</small><b>${rl(p.hora)}</b></div>`).join("") +
      `</div>`
    );
  }

  // ícone do tempo de uma hora: chuva >= 40% (ou código de chuva) / nublado / limpo (lua à noite)
  function iconeTempo(h) {
    const c = numeroValido(h.chuva_pct) ? h.chuva_pct : 0;
    const cod = numeroValido(h.codigo) ? h.codigo : null;
    if (c >= 40 || (cod !== null && cod >= 51)) return IC.chuva;
    if (c >= 15 || (cod !== null && cod >= 2)) return IC.nuvem;
    const hora = numeroValido(h.hora) ? h.hora : 12;
    return hora >= 18 || hora < 6 ? IC.lua : IC.sol;
  }

  // 7 colunas da hora antes da chegada até a volta (o servidor manda; nada inventado aqui)
  function tempoHoras(horas) {
    const hs = lista(horas).filter((h) => h && numeroValido(h.hora));
    if (!hs.length) return "";
    return (
      `<div class="v-tempo" style="--n:${hs.length}" role="list" aria-label="Tempo hora a hora">` +
      hs
        .map((h) => {
          const c = numeroValido(h.chuva_pct) ? Math.max(0, Math.min(100, Math.round(h.chuva_pct))) : 0;
          const marca = h.marca === "chegada" || h.marca === "volta" ? h.marca : "";
          const temp = numeroValido(h.temp) ? `${Math.round(h.temp)}°` : "–";
          return (
            `<div class="v-hora${marca ? " marca" : ""}" role="listitem"${marca ? ` data-rot="${marca}"` : ""} data-h="${esc(h.hora)}">` +
            `<small>${esc(h.hora)}h</small>${iconeTempo(h)}<b>${rl(temp)}</b>` +
            `<span class="ch"><i style="--c:${c}%"></i></span><em>${c >= 20 ? `${c}%` : ""}</em></div>`
          );
        })
        .join("") +
      `</div>`
    );
  }

  // "o que levar": guarda-chuva / casaco, cada um com o motivo
  function levar(itens) {
    const is = lista(itens).filter((i) => i && i.titulo);
    if (!is.length) return "";
    const icone = (i) => (i.item === "guarda_chuva" ? IC.guardaChuva : IC.casaco);
    return (
      `<div class="v-levar">` +
      is.map((i) => `<span>${icone(i)}<span>${esc(i.titulo)}${i.motivo ? `<small>${esc(i.motivo)}</small>` : ""}</span></span>`).join("") +
      `</div>`
    );
  }

  // anel do ícone: cheio até `frac` (gasto) ou em pedaços (tarefas do dia)
  function anelIcone(frac) {
    const r = 21;
    const c = 2 * Math.PI * r;
    const f = Math.max(0, Math.min(1, Number(frac) || 0));
    return (
      `<svg class="anel" viewBox="0 0 46 46" aria-hidden="true"><circle cx="23" cy="23" r="${r}" fill="none" stroke="#2c2c2e" stroke-width="2.5"/>` +
      `<circle cx="23" cy="23" r="${r}" fill="none" stroke="var(--cc)" stroke-width="2.5" stroke-linecap="round" stroke-dasharray="${(c * f).toFixed(1)} 200"/></svg>`
    );
  }
  function anelPedacos(feitas, total) {
    const n = Math.max(1, Math.min(12, total));
    const k = total > 12 ? Math.round((feitas / total) * 12) : feitas;
    const r = 21;
    const cx = 23;
    const vao = n > 1 ? 5 : 0;
    let h = "";
    if (n === 1) {
      h = `<circle cx="23" cy="23" r="${r}" fill="none" stroke="${k >= 1 ? "var(--cc)" : "#2c2c2e"}" stroke-width="2.5"/>`;
    } else {
      for (let i = 0; i < n; i++) {
        const a1 = (((i * 360) / n + vao) * Math.PI) / 180;
        const a2 = ((((i + 1) * 360) / n - vao) * Math.PI) / 180;
        h +=
          `<path d="M${(cx + r * Math.cos(a1)).toFixed(2)} ${(cx + r * Math.sin(a1)).toFixed(2)} A${r} ${r} 0 0 1 ${(cx + r * Math.cos(a2)).toFixed(2)} ${(cx + r * Math.sin(a2)).toFixed(2)}"` +
          ` fill="none" stroke="${i < k ? "var(--cc)" : "#2c2c2e"}" stroke-width="2.5" stroke-linecap="round"/>`;
      }
    }
    return `<svg class="anel" viewBox="0 0 46 46" aria-hidden="true">${h}</svg>`;
  }

  // ------------------------------------------------------------------ lugar_salvo (type novo)
  // "a oficina é a Mecânica Rossi": apelido + nome achado no Google + "de casa: N min" quando houver.
  // Aberto: o círculo de 150 m (onde_estou.RAIO_M) que o iPhone usa pra saber que ele chegou.
  const COR_LUGAR = "#7fd9d0";
  function mapaLugar(raio) {
    return (
      `<div class="v-mapa"><svg viewBox="0 0 400 150" preserveAspectRatio="xMidYMid slice" aria-hidden="true">` +
      `<rect width="400" height="150" fill="#202022"/>` +
      `<g fill="#262628"><rect x="14" y="8" width="90" height="44" rx="3"/><rect x="128" y="8" width="56" height="44" rx="3"/><rect x="214" y="8" width="70" height="44" rx="3"/><rect x="306" y="8" width="84" height="44" rx="3"/><rect x="14" y="76" width="90" height="30" rx="3"/><rect x="306" y="76" width="84" height="30" rx="3"/></g>` +
      `<g stroke="#38383a" stroke-width="7" fill="none" stroke-linecap="round"><path d="M0 64 H400"/><path d="M116 0 V150"/><path d="M296 0 V150"/></g>` +
      `<g stroke="#2e2e30" stroke-width="3" fill="none"><path d="M200 0 V100"/><path d="M0 116 H120"/></g>` +
      `<circle class="onda" cx="200" cy="75" r="46" fill="none" stroke="var(--cc)" stroke-width="1.5"/>` +
      `<circle class="onda o2" cx="200" cy="75" r="46" fill="none" stroke="var(--cc)" stroke-width="1.5"/>` +
      `<circle class="cerca" cx="200" cy="75" r="46" stroke="var(--cc)" stroke-width="1" stroke-dasharray="4 4"/>` +
      `<circle cx="200" cy="75" r="9" fill="var(--cc)" stroke="#202022" stroke-width="3"/></svg>` +
      `<span class="raio">raio de ${esc(raio)} m</span></div>`
    );
  }
  Cards.registrar("lugar_salvo", (data, card) => {
    if (!data || !data.apelido) return null;
    const raio = numeroValido(data.raio_m) && data.raio_m > 0 ? Math.round(data.raio_m) : 150;
    if (data.oculto) {
      return pilula({ v: "lugar", cor: COR_LUGAR, icone: IC.pin, titulo: data.apelido, sub: "lugar salvo" });
    }
    const nome = data.nome || data.endereco || "";
    const temCasa = numeroValido(data.de_casa_min);
    const extra =
      `<button type="button" data-acao="lugar_nao_e" data-apelido="${esc(data.apelido)}">Não é essa</button>` +
      (data.maps_url && /^https:\/\/www\.google\.com\/maps\//.test(data.maps_url)
        ? `<a class="pri" href="${esc(data.maps_url)}" target="_blank" rel="noopener noreferrer">Abrir no Mapas</a>`
        : "");
    return pilula({
      v: "lugar",
      cor: COR_LUGAR,
      icone: IC.pin,
      titulo: data.apelido,
      sub: nome ? `<span>${esc(nome)}</span>` : "",
      rotulo: temCasa ? "de casa" : "",
      valor: temCasa ? esc(`${Math.round(data.de_casa_min)} min`) : "",
      corpo:
        mapaLugar(raio) +
        `<p class="v-nota">${data.endereco ? `${esc(data.endereco)}. ` : ""}Quando o iPhone te ver dentro desse círculo, eu aviso e puxo a próxima tarefa.</p>` +
        botoes(card, extra, ["desfazer"]),
    });
  });

  // ------------------------------------------------------------------ navegador

  // Mudança de DOM do relógio não é mensagem nova: o auto-rolar do chat ignora (chat.js)
  function semRolar(fn) {
    const doc = raiz.document && raiz.document.documentElement;
    if (doc) doc.dataset.vivoSemRolar = "1";
    try {
      fn();
    } finally {
      setTimeout(() => doc && delete doc.dataset.vivoSemRolar, 0);
    }
  }

  // um tique: toda contagem visível anda (só o dígito que mudou rola)
  function tique(raizEl) {
    const doc = raizEl || (raiz.document || null);
    if (!doc || !doc.querySelectorAll) return 0;
    const els = doc.querySelectorAll(".vivo-d [data-cd-s]:not([data-parado])");
    // carrinho a caminho ("Já saí"): anda pela fração do tempo entre sair e a hora marcada
    const rotas = doc.querySelectorAll(".vivo-d .v-rota[data-ini][data-fim]");
    if (!els.length && !rotas.length) return 0;
    const agora = Date.now();
    semRolar(() => {
      els.forEach((el) => {
        const r = restante(Number(el.dataset.cdS), el.dataset.cdG === "" ? null : Number(el.dataset.cdG), agora);
        if (r !== null) rolar(el, fmtCd(r, el.dataset.fmt));
      });
      rotas.forEach((rota) => {
        const ini = Number(rota.dataset.ini);
        const fim = Number(rota.dataset.fim);
        const p = fim > ini ? Math.max(0, Math.min(1, (agora - ini) / (fim - ini))) : 1;
        rota.style.setProperty("--p", p.toFixed(4));
      });
    });
    return els.length + rotas.length;
  }

  const aoAbrir = {};
  // registrarAbrir("gasto", (vivoEl) => ...) - roda quando a pílula daquele data-v abre
  function registrarAbrir(v, fn) {
    if (typeof v === "string" && typeof fn === "function") aoAbrir[v] = fn;
  }

  function alternar(v, abre) {
    const vai = typeof abre === "boolean" ? abre : v.getAttribute("aria-expanded") !== "true";
    semRolar(() => {
      v.setAttribute("aria-expanded", String(vai));
      const top = v.querySelector(".v-top");
      if (top) top.setAttribute("aria-expanded", String(vai));
    });
    if (vai && aoAbrir[v.dataset.v]) {
      try {
        aoAbrir[v.dataset.v](v);
      } catch (e) {
        if (raiz.console) raiz.console.warn("card D: abrir falhou", e);
      }
    }
    if (typeof raiz.vibrar === "function") raiz.vibrar(6);
  }

  const INTERATIVO = "a, button, input, label, select, textarea, summary, [data-acao], .v-desliza";
  let ligado = false;
  let relogio = null;
  function ligar() {
    if (ligado || !raiz.document || typeof raiz.document.addEventListener !== "function") return;
    ligado = true;
    raiz.document.addEventListener("click", (e) => {
      const alvo = e.target && e.target.closest ? e.target : null;
      const v = alvo && alvo.closest(".vivo-d");
      if (!v) return;
      const top = alvo.closest(".v-top");
      if (!top && alvo.closest(INTERATIVO)) return;
      if (v.closest(".card-desfeito") && !top) return;
      alternar(v);
    });
    relogio = setInterval(() => {
      if (raiz.document.hidden) return;
      tique();
    }, 1000);
    raiz.document.addEventListener("visibilitychange", () => {
      if (!raiz.document.hidden) tique();
    });
    ligarDesliza();
  }

  // estado que vive no aparelho (ex.: "Já saí") reaplicado no histórico
  const aoPreparar = {};
  function registrarPreparar(v, fn) {
    if (typeof v === "string" && typeof fn === "function") aoPreparar[v] = fn;
  }

  // chamado pra todo grupo de cards (histórico também; CardsVivos.preparar)
  function preparar(raizEl) {
    if (!raizEl || !raizEl.querySelectorAll) return;
    ligar();
    raizEl.querySelectorAll(".vivo-d").forEach((v) => {
      if (!aoPreparar[v.dataset.v]) return;
      try {
        aoPreparar[v.dataset.v](v);
      } catch (e) {
        if (raiz.console) raiz.console.warn("card D: preparar falhou", e);
      }
    });
    tique(raizEl);
    raizEl.querySelectorAll(".vivo-d[aria-expanded='true']").forEach((v) => aoAbrir[v.dataset.v] && aoAbrir[v.dataset.v](v));
  }

  // Desfazer deu certo (cards.js): a pílula volta o que tinha mudado (ex.: hora que rolou)
  const aoDesfazer = {};
  function registrarDesfazer(v, fn) {
    if (typeof v === "string" && typeof fn === "function") aoDesfazer[v] = fn;
  }
  function desfeito(cardEl) {
    if (!cardEl || !cardEl.querySelectorAll) return;
    cardEl.querySelectorAll(".vivo-d").forEach((v) => aoDesfazer[v.dataset.v] && aoDesfazer[v.dataset.v](v));
  }

  // ------------------------------------------------------------------ deslize (conta paga)
  // <div class="v-desliza" data-desliza="nome"> ... <span class="bolinha" role="slider" tabindex="0">
  // Passou de 82% = confirma; registrarDesliza(nome, async (deslizaEl, vivoEl, deps) => true/false).
  const aoDeslizar = {};
  function registrarDesliza(nome, fn) {
    if (typeof nome === "string" && typeof fn === "function") aoDeslizar[nome] = fn;
  }
  function deslizaHTML(nome, texto, attrs = "") {
    return (
      `<div class="v-desliza" data-desliza="${esc(nome)}"${attrs}><span class="rastro"></span><span class="txt">${esc(texto)}</span>` +
      `<span class="bolinha" role="slider" tabindex="0" aria-label="${esc(texto)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">${IC.seta}</span></div>`
    );
  }
  function ligarDesliza() {
    const doc = raiz.document;
    let st = null;
    const maxDe = (dz) => Math.max(1, dz.clientWidth - 56);
    const por = (dz, x) => {
      dz.style.setProperty("--x", `${x}px`);
      dz.style.setProperty("--f", (x / maxDe(dz)).toFixed(3));
      const b = dz.querySelector(".bolinha");
      if (b) b.setAttribute("aria-valuenow", String(Math.round((x / maxDe(dz)) * 100)));
    };
    async function confirmar(dz) {
      if (dz.dataset.feito || dz.dataset.enviando) return;
      dz.dataset.enviando = "1";
      dz.classList.add("solto");
      por(dz, maxDe(dz));
      const fn = aoDeslizar[dz.dataset.desliza];
      let ok = false;
      try {
        ok = fn ? await fn(dz, dz.closest(".vivo-d"), Cards.deps || {}) : false;
      } catch (_) {
        ok = false;
      }
      delete dz.dataset.enviando;
      if (ok) {
        dz.dataset.feito = "1";
        if (typeof raiz.vibrar === "function") raiz.vibrar([6, 50, 14]);
      } else {
        por(dz, 0);
      }
    }
    doc.addEventListener("pointerdown", (e) => {
      const b = e.target.closest && e.target.closest(".v-desliza .bolinha");
      if (!b) return;
      const dz = b.closest(".v-desliza");
      if (dz.dataset.feito || dz.dataset.enviando) return;
      st = { dz, b, x0: e.clientX, x: 0, id: e.pointerId };
      dz.classList.remove("solto");
      try {
        b.setPointerCapture(e.pointerId);
      } catch (_) {
        /* ponteiro ja solto */
      }
      e.preventDefault();
    });
    doc.addEventListener("pointermove", (e) => {
      if (!st || e.pointerId !== st.id) return;
      st.x = Math.max(0, Math.min(maxDe(st.dz), e.clientX - st.x0));
      por(st.dz, st.x);
    });
    const soltar = (e) => {
      if (!st || e.pointerId !== st.id) return;
      const { dz, x } = st;
      st = null;
      if (x > maxDe(dz) * 0.82) confirmar(dz);
      else {
        dz.classList.add("solto");
        por(dz, 0);
      }
    };
    doc.addEventListener("pointerup", soltar);
    doc.addEventListener("pointercancel", soltar);
    doc.addEventListener("keydown", (e) => {
      const b = e.target.closest && e.target.closest(".v-desliza .bolinha");
      if (!b || !["Enter", " ", "ArrowRight"].includes(e.key)) return;
      e.preventDefault();
      confirmar(b.closest(".v-desliza"));
    });
  }

  // só a resposta NOVA: o que precisa "acontecer" na frente dele (hora que rola da velha pra nova)
  const aoChegar = {};
  function registrarChegar(v, fn) {
    if (typeof v === "string" && typeof fn === "function") aoChegar[v] = fn;
  }
  function animar(raizEl) {
    if (!raizEl || !raizEl.querySelectorAll || reduzido()) return;
    raizEl.querySelectorAll(".vivo-d").forEach((v) => aoChegar[v.dataset.v] && aoChegar[v.dataset.v](v));
  }

  // "Não é essa": a correção vai pela conversa (a IA procura de novo e troca o endereço)
  if (typeof Cards.registrarAcao === "function") {
    Cards.registrarAcao("lugar_nao_e", (btn) => {
      const campo = raiz.document && raiz.document.getElementById("chat-input");
      if (!campo) return;
      campo.value = `A ${btn.dataset.apelido || "lugar"} não é essa. É `;
      campo.focus();
      try {
        campo.setSelectionRange(campo.value.length, campo.value.length);
      } catch (_) {
        /* input sem seleção: só foca */
      }
    });
  }

  const CardsD = {
    IC,
    restante,
    fmtCd,
    hm,
    minDia,
    rl,
    contagem,
    rolar,
    pilula,
    botoes,
    cadeia,
    tempoHoras,
    iconeTempo,
    levar,
    anelIcone,
    anelPedacos,
    tique,
    alternar,
    registrarAbrir,
    registrarChegar,
    registrarPreparar,
    registrarDesfazer,
    registrarDesliza,
    deslizaHTML,
    desfeito,
    preparar,
    animar,
    semRolar,
    reduzido,
  };
  raiz.CardsD = CardsD;
  if (typeof module !== "undefined" && module.exports) module.exports = CardsD;
})(typeof window !== "undefined" ? window : globalThis);
