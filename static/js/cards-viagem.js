// Viagem planejada + abastecimento (leva "painel mais esperto", 06/11/2026,
// docs/briefings/2026-11-06-painel-esperto.md). O card `viagem` e o MESMO card de rota do app (mapa com o
// caminho real e o carrinho - Cards.mapaRota/tempoRota de cards-tipos.js), com coisas a mais: postos, chuva,
// lento e noite por cima do caminho, a barra "Tempo no caminho" com posto e trecho de noite, os 3 horarios de
// saida (tudo ja calculado no servidor: trocar o chip so mostra outra camada, sem chamar o Google), linha do
// tempo, tanque (estimativa), gasolina/custo/chegada e Maps/Waze com as paradas.
// `abastecimento` usa a casca D (CardsD.pilula). Renderizadores PUROS: todo texto passa por esc().
(function (raiz) {
  "use strict";
  const Cards = raiz.Cards || (typeof require === "function" ? require("./cards.js") : null);
  if (!Cards) return;
  const CardsD = raiz.CardsD || (typeof require === "function" ? require("./cards-d.js") : null);

  const { esc, moeda, numeroValido } = Cards;
  const lista = (v) => (Array.isArray(v) ? v : []);
  const texto = (v) => (typeof v === "string" ? v : "");
  const HORA = /^\d{2}:\d{2}( \(\+1\))?$/;
  const TIPOS_CHUVA = ["granizo", "trovoada", "neblina", "chuva_forte", "chuva", "vento"];
  const TIPOS_EVENTO = ["", "chuva", "lento", "posto", "alerta", "fim"];
  const COR_POSTO = "#9fdcb0";

  function fmtKm(km) {
    return numeroValido(km) ? Math.round(km).toLocaleString("pt-BR") : "";
  }

  function fmtDur(min) {
    if (!numeroValido(min) || min < 0) return "";
    const h = Math.floor(min / 60);
    const m = Math.round(min % 60);
    return h ? `${h}h${String(m).padStart(2, "0")}` : `${m} min`;
  }

  // ---- geometria: o traco do servidor traz o km de cada ponto desenhado (traco.km) -----------------
  function pontosKm(traco) {
    if (!traco || typeof traco !== "object") return null;
    const pts = lista(traco.pontos);
    const km = lista(traco.km);
    if (pts.length < 2 || km.length !== pts.length) return null;
    if (!pts.every((p) => Array.isArray(p) && p.length === 2 && p.every(numeroValido)) || !km.every(numeroValido)) return null;
    return { pts, km };
  }

  function noKm(g, k) {
    const { pts, km } = g;
    if (k <= km[0]) return pts[0];
    for (let i = 1; i < km.length; i++) {
      if (km[i] >= k) {
        const f = km[i] === km[i - 1] ? 0 : (k - km[i - 1]) / (km[i] - km[i - 1]);
        return [+(pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * f).toFixed(1), +(pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * f).toFixed(1)];
      }
    }
    return pts[pts.length - 1];
  }

  function trechoKm(g, a, b) {
    if (!(b > a)) return "";
    const meio = [];
    g.km.forEach((k, i) => {
      if (k > a && k < b) meio.push(g.pts[i]);
    });
    const todos = [noKm(g, a), ...meio, noKm(g, b)];
    return "M" + todos.map((p) => `${p[0]} ${p[1]}`).join(" L");
  }

  // ---- camada por cima do mapa (uma por saida; so a escolhida aparece) ----------------------------
  function camada(g, s, i, on) {
    if (!g) return "";
    const total = g.km[g.km.length - 1] || 1;
    const chuva = lista(s.chuva)
      .filter((c) => c && TIPOS_CHUVA.includes(c.tipo) && numeroValido(c.de_km) && numeroValido(c.ate_km))
      .map((c) => `<path class="vivo-rota-tempo card-rota-tempo--${c.tipo}" d="${trechoKm(g, c.de_km, c.ate_km)}"/>`)
      .join("");
    const noite = lista(s.noite)
      .filter((n) => n && numeroValido(n.de_km) && numeroValido(n.ate_km))
      .map((n) => `<path class="cv-rota-noite" d="${trechoKm(g, n.de_km, n.ate_km)}"/>`)
      .join("");
    const lentos = lista(s.lentos)
      .filter((x) => x && (x.nivel === "lento" || x.nivel === "parado") && numeroValido(x.de_km) && numeroValido(x.ate_km))
      .map((x) => `<path class="vivo-rota-lento vivo-rota-lento--${x.nivel}" d="${trechoKm(g, x.de_km, Math.max(x.ate_km, x.de_km + total * 0.012))}"/>`)
      .join("");
    const postos = lista(s.postos)
      .filter((p) => p && numeroValido(p.km))
      .map((p) => {
        const [x, y] = noKm(g, p.km);
        const nome = String(p.nome || "").split(" ").slice(0, 3).join(" ").slice(0, 22);
        return (
          `<g class="cv-posto-pino${p.nome ? "" : " cv-posto-sem"}" transform="translate(${x} ${y})">` +
          `<circle r="11" class="cv-posto-halo"/><circle r="6" class="cv-posto-miolo"/>` +
          `<path class="cv-posto-bomba" d="M-2.4 2.6V-2.6H1.6V2.6M-2.4 0H1.6"/>` +
          (nome ? `<text class="vivo-pino-nome" x="0" y="-15" text-anchor="middle">${esc(nome)}</text>` : "") +
          `</g>`
        );
      })
      .join("");
    return `<g class="cv-camada" data-cv-s="${i}"${on ? " data-on" : ""}>${chuva}${noite}${lentos}${postos}</g>`;
  }

  function mapaViagem(data, saidas, escolhida) {
    const html = Cards.mapaRota ? Cards.mapaRota(data.traco, [data.origem || "Saída", data.destino || ""]) : "";
    if (!html) return "";
    const g = pontosKm(data.traco);
    const camadas = saidas.map((s, i) => camada(g, s, i, i === escolhida)).join("");
    // por cima do caminho e dos pinos, por baixo do carrinho
    return html.replace('<g class="vivo-rota-carro">', `${camadas}<g class="vivo-rota-carro">`);
  }

  // ---- barra "Tempo no caminho" da saida: chuva + noite + lento + posto ----------------------------
  function barra(s, total) {
    const pct = (km) => Math.max(0, Math.min(100, (km / total) * 100));
    const faixa = (cls, a, b, n) =>
      `<i class="${cls}" style="left:${pct(a).toFixed(2)}%;width:${Math.max(0.6, pct(b) - pct(a)).toFixed(2)}%;--i:${n}"></i>`;
    let n = 0;
    const partes = [
      ...lista(s.chuva)
        .filter((c) => c && TIPOS_CHUVA.includes(c.tipo) && numeroValido(c.de_km) && numeroValido(c.ate_km))
        .map((c) => faixa(`card-rota-tempo-faixa card-rota-tempo--${c.tipo}`, c.de_km, c.ate_km, n++)),
      ...lista(s.noite)
        .filter((x) => x && numeroValido(x.de_km) && numeroValido(x.ate_km))
        .map((x) => faixa("card-rota-tempo-faixa cv-faixa-noite", x.de_km, x.ate_km, n++)),
      ...lista(s.lentos)
        .filter((x) => x && (x.nivel === "lento" || x.nivel === "parado") && numeroValido(x.de_km))
        .map((x) => faixa(`card-rota-tempo-faixa cv-faixa-lento cv-faixa-lento--${x.nivel}`, x.de_km, numeroValido(x.ate_km) ? x.ate_km : x.de_km, n++)),
      ...lista(s.postos)
        .filter((p) => p && numeroValido(p.km))
        .map((p) => `<i class="cv-faixa-posto" style="left:${pct(p.km).toFixed(2)}%"></i>`),
    ];
    return `<div class="card-rota-tempo-barra cv-barra" role="img" aria-label="Chuva, trânsito, posto e noite ao longo da rota">${partes.join("")}</div>`;
  }

  function itensSaida(s, total) {
    const li = (cls, txt) => `<li class="card-rota-lento ${cls}"><i aria-hidden="true"></i>${esc(txt)}</li>`;
    const itens = [];
    lista(s.chuva)
      .filter((c) => c && TIPOS_CHUVA.includes(c.tipo) && texto(c.frase))
      .slice(0, 3)
      .forEach((c) => itens.push(li(`card-rota-tempo-item card-rota-tempo--${c.tipo}`, c.frase)));
    lista(s.lentos)
      .filter((x) => x && (x.nivel === "lento" || x.nivel === "parado") && texto(x.frase))
      .slice(0, 3)
      .forEach((x) => itens.push(li(`card-rota-lento--${x.nivel}`, x.frase)));
    lista(s.postos)
      .filter((p) => p && numeroValido(p.km))
      .forEach((p) => {
        const aberto = p.h24 ? ", aberto 24 h" : texto(p.ate) ? `, aberto até ${p.ate}` : "";
        itens.push(li("cv-item-posto", p.nome ? `Abastece no km ${fmtKm(p.km)}, ${p.nome}${aberto}` : `Abastece até o km ${fmtKm(p.km)}`));
      });
    const noite = lista(s.noite).filter((x) => x && numeroValido(x.de_km) && numeroValido(x.ate_km));
    noite.forEach((x) => {
      const km = Math.round(x.ate_km - x.de_km);
      const fim = x.ate_km >= total - 1;
      itens.push(li("cv-item-noite", fim ? `Escurece no km ${fmtKm(x.de_km)}: últimos ${km} km de noite` : `${km} km de noite (do km ${fmtKm(x.de_km)} ao ${fmtKm(x.ate_km)})`));
    });
    if (!itens.length) itens.push(li("card-rota-tempo-item card-rota-tempo--ok", "Sem chuva, sem lentidão e com luz do dia."));
    return `<ul class="card-rota-lentos">${itens.join("")}</ul>`;
  }

  function eventos(s) {
    const ev = lista(s.eventos).filter((e) => e && HORA.test(texto(e.hora).slice(0, 5)) && texto(e.titulo));
    if (!ev.length) return "";
    return (
      `<ol class="cv-linha">` +
      ev
        .map((e, i) => {
          const tipo = TIPOS_EVENTO.includes(e.tipo) ? e.tipo : "";
          return (
            `<li class="cv-ev${tipo ? ` cv-ev--${tipo}` : ""}" style="--i:${i}"><span class="cv-ev-h">${esc(texto(e.hora).slice(0, 5))}</span>` +
            `<span class="cv-ev-p" aria-hidden="true"></span><span class="cv-ev-c"><b>${esc(e.titulo)}</b>${texto(e.sub) ? `<span>${esc(e.sub)}</span>` : ""}</span></li>`
          );
        })
        .join("") +
      `</ol>`
    );
  }

  function tanqueHTML(t) {
    if (!t || typeof t !== "object" || !numeroValido(t.fracao)) return "";
    const f = Math.max(0, Math.min(1, t.fracao));
    const reserva =
      numeroValido(t.reserva_km) && numeroValido(t.km_l) && numeroValido(t.tanque_l) && t.km_l > 0 && t.tanque_l > 0
        ? Math.min(0.5, t.reserva_km / t.km_l / t.tanque_l)
        : null;
    const rotulo = f >= 0.98 ? "cheio" : numeroValido(t.litros) ? `~${Math.round(t.litros)} L` : "";
    return (
      `<div class="cv-tanque"><p class="cv-rotulo">Tanque</p>` +
      `<div class="cv-tanque-linha"><div class="cv-tanque-barra" role="img" aria-label="Tanque estimado: ${esc(rotulo || "sem dado")}">` +
      `<i style="width:${(f * 100).toFixed(1)}%"></i>${reserva !== null ? `<span class="cv-reserva" style="left:${(reserva * 100).toFixed(1)}%"></span>` : ""}</div>` +
      (rotulo ? `<small>${esc(rotulo)}</small>` : "") +
      `</div>` +
      (texto(t.texto) ? `<p class="cv-estimativa">${esc(t.texto)}${numeroValido(t.reserva_km) ? ` Reserva com ${esc(Math.round(t.reserva_km))} km de folga.` : ""}</p>` : "") +
      `</div>`
    );
  }

  function numerosSaida(s, custo, oculto) {
    const cel = (rot, val) => (val ? `<div><small>${esc(rot)}</small><strong>${val}</strong></div>` : "");
    const custoTxt = oculto ? "" : numeroValido(custo) ? esc(moeda(custo)).replace(" ", "&nbsp;") : "";
    const html =
      cel("Gasolina", numeroValido(s.litros) ? esc(`~${s.litros} L`) : "") +
      cel("Custo", custoTxt) +
      cel("Chega", HORA.test(texto(s.chega)) ? esc(s.chega) : "");
    return html ? `<div class="cv-numeros">${html}</div>` : "";
  }

  Cards.registrar("viagem", (data, card) => {
    const saidas = lista(data.saidas).filter((s) => s && typeof s === "object" && HORA.test(texto(s.hora)));
    if (!saidas.length || !texto(data.destino)) return null;
    const esc0 = numeroValido(data.escolhida) && data.escolhida >= 0 && data.escolhida < saidas.length ? data.escolhida : 0;
    const total = numeroValido(data.total_km) && data.total_km > 0 ? data.total_km : null;
    const custos = lista(data.custos);
    const on = (i) => (i === esc0 ? " data-on" : "");
    const bloco = (i, html) => (html ? `<div data-cv-s="${i}"${on(i)}>${html}</div>` : "");

    const numeros = saidas
      .map((s, i) => {
        const dur = fmtDur(s.duracao_total_min);
        const t = [total ? `${fmtKm(total)} km` : "", dur].filter(Boolean).join(" · ");
        return t ? `<p class="card-hora-grande card-rota-numeros" data-cv-s="${i}"${on(i)}>${esc(t)}</p>` : "";
      })
      .join("");
    const tempo = total
      ? saidas
          .map((s, i) =>
            bloco(
              i,
              `<div class="card-rota-tempo"><p class="card-rota-tempo-rotulo">Tempo no caminho · saindo ${esc(s.hora)}</p>` +
                barra(s, total) +
                `<div class="card-rota-tempo-km"><span>km 0</span><span>km ${esc(fmtKm(total))}</span></div>` +
                itensSaida(s, total) +
                `</div>`,
            ),
          )
          .join("")
      : "";
    const chips =
      saidas.length > 1
        ? `<div class="cv-saidas"><p class="cv-rotulo">Melhor hora pra sair</p>` +
          `<div class="cv-chips" role="group" aria-label="Hora de saída">` +
          saidas
            .map(
              (s, i) =>
                `<button type="button" class="cv-chip${i === data.melhor ? " cv-chip--melhor" : ""}" data-acao="viagem_saida" data-i="${i}" data-viagem="${esc(numeroValido(data.id) ? data.id : "")}" aria-pressed="${i === esc0}">${esc(s.hora)}</button>`,
            )
            .join("") +
          `</div>` +
          (texto(data.frase_melhor) ? `<p class="cv-melhor">${esc(data.frase_melhor)}</p>` : "") +
          saidas.map((s, i) => (texto(s.dica) ? `<p class="cv-dica" data-cv-s="${i}"${on(i)}>${esc(s.dica)}</p>` : "")).join("") +
          `</div>`
        : "";
    const linha = saidas.map((s, i) => bloco(i, eventos(s))).join("");
    const nums = saidas.map((s, i) => bloco(i, numerosSaida(s, custos[i], data.oculto))).join("");
    const links = saidas
      .map((s) => ({
        maps: /^https:\/\/www\.google\.com\/maps\//.test(texto(s.maps_url)) ? s.maps_url : "",
        waze: /^https:\/\/waze\.com\/ul\?/.test(texto(s.waze_url)) ? s.waze_url : "",
      }));
    const quando = texto(data.quando);
    return (
      Cards.eyebrowCard(Cards.ICONE_ROTA, `Rota · viagem${quando ? ` · ${quando}` : ""}`) +
      `<div class="cv-viagem" data-cv-links="${esc(JSON.stringify(links))}">` +
      `<p class="card-titulo">${esc(data.destino)}</p>` +
      mapaViagem(data, saidas, esc0) +
      numeros +
      tempo +
      chips +
      (texto(data.aviso_noite) ? `<p class="cv-aviso">${esc(data.aviso_noite)}</p>` : "") +
      (linha ? `<div class="cv-sep"></div>${linha}` : "") +
      tanqueHTML(data.tanque) +
      nums +
      (data.encerrada ? `<p class="cv-estimativa">Viagem encerrada.</p>` : "") +
      `</div>`
    );
  });

  // troca de saida: so mostra a outra camada (dado ja no card), avisa o servidor qual vale (pro GPS do
  // iPhone); falhou = volta pra de antes
  function mostrarSaida(cardEl, i) {
    cardEl.querySelectorAll("[data-cv-s]").forEach((el) => {
      if (el.getAttribute("data-cv-s") === String(i)) el.setAttribute("data-on", "");
      else el.removeAttribute("data-on");
    });
    cardEl.querySelectorAll(".cv-chip").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.i === String(i))));
    const caixa = cardEl.querySelector(".cv-viagem");
    let links = [];
    try {
      links = JSON.parse((caixa && caixa.getAttribute("data-cv-links")) || "[]");
    } catch (_) {
      links = [];
    }
    const l = links[i] || {};
    cardEl.querySelectorAll("a.card-btn-link").forEach((a) => {
      const href = a.getAttribute("href") || "";
      if (l.maps && href.startsWith("https://www.google.com/maps/")) a.setAttribute("href", l.maps);
      if (l.waze && href.startsWith("https://waze.com/ul?")) a.setAttribute("href", l.waze);
    });
  }

  if (typeof Cards.registrarAcao === "function") {
    Cards.registrarAcao("viagem_saida", async (btn, cardEl, deps) => {
      if (!cardEl || btn.getAttribute("aria-pressed") === "true" || cardEl.dataset.cvEnviando) return;
      const antes = (cardEl.querySelector('.cv-chip[aria-pressed="true"]') || {}).dataset;
      const i = Number(btn.dataset.i);
      mostrarSaida(cardEl, i); // otimista
      const id = btn.dataset.viagem;
      if (!id || !deps || typeof deps.apiFetch !== "function") return;
      cardEl.dataset.cvEnviando = "1";
      const res = await deps.apiFetch(`/api/viagens-planejadas/${encodeURIComponent(id)}/saida`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ indice: i }),
      });
      delete cardEl.dataset.cvEnviando;
      if ((!res || !res.ok) && antes && antes.i !== undefined) mostrarSaida(cardEl, Number(antes.i));
    });
  }

  // ---- abastecimento (casca D) -------------------------------------------------------------------
  const BOMBA =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 20V5.5A1.5 1.5 0 0 1 5.5 4h7A1.5 1.5 0 0 1 14 5.5V20M3 20h12M4 10h10M14 8l3 2.5V16a1.5 1.5 0 0 0 3 0V9l-3-3"/></svg>';

  Cards.registrar("abastecimento", (data, card) => {
    if (!CardsD || typeof CardsD.pilula !== "function") return null;
    const litros = numeroValido(data.litros) ? data.litros : null;
    if (!data.cheio && litros === null && !numeroValido(data.valor) && !data.oculto) return null;
    const titulo = data.cheio ? "Tanque cheio" : litros !== null ? `Abasteceu ${String(litros).replace(".", ",")} L` : "Abastecimento";
    const sub = [texto(data.lugar), texto(data.carro)].filter(Boolean)[0] || "";
    const t = data.tanque && typeof data.tanque === "object" ? data.tanque : null;
    const linhas = [];
    if (litros !== null) linhas.push(["Litros", `${String(litros).replace(".", ",")} L`]);
    if (numeroValido(data.valor) && !data.oculto) linhas.push(["Valor", moeda(data.valor)]);
    if (numeroValido(data.preco_litro) && !data.oculto) linhas.push(["Litro", moeda(data.preco_litro)]);
    if (numeroValido(data.hodometro_km)) linhas.push(["Hodômetro", `${fmtKm(data.hodometro_km)} km`]);
    if (data.consumo && numeroValido(data.consumo.km_l)) {
      linhas.push(["Consumo real", `${String(data.consumo.km_l).replace(".", ",")} km/l`]);
    } else if (data.consumo_padrao && numeroValido(data.consumo_padrao.estrada)) {
      linhas.push(["Consumo", `${data.consumo_padrao.estrada} estrada · ${data.consumo_padrao.cidade} cidade (de partida)`]);
    }
    const corpo =
      (t ? tanqueHTML({ ...t, texto: "", reserva_km: null }) : "") +
      (t && numeroValido(t.autonomia_km)
        ? `<p class="cv-estimativa">Estimativa: dá uns ${esc(fmtKm(t.autonomia_km))} km${numeroValido(t.margem_l) ? ` (margem de ±${esc(Math.round(t.margem_l))} L)` : ""}. Tanque de ${esc(t.tanque_l)} L${t.tanque_conferido ? "" : ", a confirmar"}.</p>`
        : "") +
      (linhas.length
        ? `<dl class="cv-linhas">${linhas.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v).replace(/R\$ /, "R$&nbsp;")}</dd></div>`).join("")}</dl>`
        : "") +
      (texto(data.dica) ? `<p class="v-nota">${esc(data.dica)}</p>` : "") +
      CardsD.botoes(card, "", ["desfazer"]);
    return CardsD.pilula({
      v: "abastecimento",
      cor: COR_POSTO,
      icone: BOMBA,
      titulo,
      sub: sub ? `<span>${esc(sub)}</span>` : "",
      rotulo: t ? "tanque" : "",
      valor: t ? esc(t.fracao >= 0.98 ? "cheio" : `~${Math.round(t.litros)} L`) : "",
      corpo,
    });
  });

  const CardsViagem = { pontosKm, noKm, trechoKm, camada, fmtDur };
  raiz.CardsViagem = CardsViagem;
  if (typeof module !== "undefined" && module.exports) module.exports = CardsViagem;
})(typeof window !== "undefined" ? window : globalThis);
