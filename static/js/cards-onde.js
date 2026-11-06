// Painel mais esperto (06/11/2026, docs/briefings/2026-11-06-painel-esperto.md, frentes 4 e 7): os 4 cards
// de "onde estou / pra onde vou", todos na casca D (CardsD.pilula, linguagem aprovada em 04/11):
//
//   indo_pra       "Indo pro date?" - saiu perto da hora de sair: linha do trajeto (saiu, lento, chuva,
//                  chega) + "É isso" / "Vou pra outro lugar" (POST /api/onde-vou/<id>/resposta).
//   diario_lugares "Teu dia, por onde passou" - barra do dia + lugar, hora e quanto ficou. Nunca o caminho.
//   meu_tempo      "Sai às 19:05 / 10 min antes: é o teu jeito" - as últimas saídas em barrinhas e o
//                  segmentado Meu tempo / Padrão (POST /api/tempos-reais/usar).
//   recado_atraso  "Vai chegar 19:52" - chips 10/15/20 min trocam o texto do recado e o botão abre o
//                  WhatsApp (wa.me) com ele. Quem manda é ele: o painel nunca envia nada.
//
// Renderizadores PUROS (estado final; histórico abre parado; testes em Node). O que ele respondeu fica no
// localStorage pro histórico não oferecer de novo (mesma regra dos cards de automação).
(function (raiz) {
  "use strict";
  const Cards = raiz.Cards || (typeof require === "function" ? require("./cards.js") : null);
  const D = raiz.CardsD || (typeof require === "function" ? require("./cards-d.js") : null);
  if (!Cards || !D) return;
  const { esc, numeroValido } = Cards;
  const lista = (v) => (Array.isArray(v) ? v : []);

  const COR = { date: "#f5a3b8", balada: "#c4a1ff" };
  const COR_TAREFA = "#f0a58f";
  const COR_FEITO = "#9fdcb0";
  const COR_PERIGO = "#f47671";
  const corDe = (estilo) => COR[estilo] || COR_TAREFA;
  const corSegura = (c, padrao) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : padrao);
  const traco = (corpo, w = 2) =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${corpo}</svg>`;
  const IC_PIN_FINO = traco('<circle cx="12" cy="10" r="3"/><path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11z"/>');
  const IC_CRONO = traco('<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2.5 2M9 2h6"/>');
  const IC_BALAO = traco('<path d="M4 18.5V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H8z"/>');

  // "20 min" / "1 h" / "3 h 38" (igual ao diario_lugares.duracao)
  function duracao(min) {
    const m = Math.max(0, Math.round(Number(min) || 0));
    if (m < 60) return `${m} min`;
    const h = Math.floor(m / 60);
    const r = m % 60;
    return r ? `${h} h ${String(r).padStart(2, "0")}` : `${h} h`;
  }

  // ------------------------------------------------------------------ o que ele já respondeu (aparelho)
  const CHAVE = "cards-onde-resp";
  function lerResp(tipo, id) {
    try {
      const m = JSON.parse(raiz.localStorage.getItem(CHAVE) || "{}");
      return (m && m[`${tipo}:${id}`]) || null;
    } catch (_) {
      return null;
    }
  }
  function guardarResp(tipo, id, valor) {
    try {
      const m = JSON.parse(raiz.localStorage.getItem(CHAVE) || "{}") || {};
      m[`${tipo}:${id}`] = valor;
      const chaves = Object.keys(m);
      if (chaves.length > 80) chaves.slice(0, chaves.length - 80).forEach((k) => delete m[k]);
      raiz.localStorage.setItem(CHAVE, JSON.stringify(m));
    } catch (_) {
      /* sem armazenamento: o card só oferece de novo */
    }
  }

  async function postar(deps, url, corpo) {
    if (!deps || typeof deps.apiFetch !== "function") return null;
    try {
      return await deps.apiFetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo || {}) });
    } catch (_) {
      return null;
    }
  }

  // ================================================================== indo_pra
  const TIPOS_EV = ["saiu", "lento", "chuva", "fim", "alerta"];
  function linhaTrajeto(eventos) {
    const evs = lista(eventos).filter((e) => e && e.hora && e.titulo);
    if (!evs.length) return "";
    return (
      `<ol class="on-linha">` +
      evs
        .map((e, i) => {
          const tipo = TIPOS_EV.includes(e.tipo) ? e.tipo : "saiu";
          return (
            `<li class="on-ev ${tipo}" style="--k:${i}"><span class="h">${esc(e.hora)}</span><span class="p" aria-hidden="true"></span>` +
            `<span class="c"><b>${esc(e.titulo)}</b>${e.sub ? `<span>${esc(e.sub)}</span>` : ""}</span></li>`
          );
        })
        .join("") +
      `</ol>`
    );
  }
  const NOTA_INDO = { sim: "Boa. Se o trânsito apertar, eu te aviso.", outro: "Beleza, não insisto." };
  function botoesIndo(d) {
    const resp = d.resposta || lerResp("indo", d.id);
    if (NOTA_INDO[resp]) return `<p class="v-nota on-resp">${esc(NOTA_INDO[resp])}</p>`;
    if (!numeroValido(d.id)) return "";
    return (
      `<div class="v-bts on-bts">` +
      `<button type="button" class="pri" data-acao="indo_resposta" data-id="${esc(d.id)}" data-r="sim">É isso</button>` +
      `<button type="button" data-acao="indo_resposta" data-id="${esc(d.id)}" data-r="outro">Vou pra outro lugar</button></div>`
    );
  }
  Cards.registrar("indo_pra", (data) => {
    const d = data || {};
    if (!d.titulo) return null;
    const cor = corDe(d.estilo);
    const icone = d.estilo === "date" ? D.IC.coracao : D.IC.pin;
    if (d.oculto) return D.pilula({ v: "indo", cor, icone, titulo: d.titulo });
    const sub = [d.destino, d.hora ? `${d.estilo === "date" ? "date" : ""} às ${d.hora}`.trim() : ""].filter(Boolean);
    return D.pilula({
      v: "indo",
      cor,
      icone,
      titulo: d.titulo,
      sub: sub.length ? `<span>${esc(sub.join(" · "))}</span>` : "",
      rotulo: d.chega ? "chega" : "",
      valor: d.chega ? D.rl(d.chega) : "",
      aberto: true,
      attrs: d.atrasa ? ' data-atrasa="1"' : "",
      corpo: linhaTrajeto(d.eventos) + botoesIndo(d),
    });
  });
  Cards.registrarAcao("indo_resposta", async (btn, cardEl, deps) => {
    const caixa = btn.closest(".on-bts");
    const r = btn.dataset.r;
    if (!caixa || !NOTA_INDO[r]) return;
    const doc = raiz.document;
    const nota = doc.createElement("p");
    nota.className = "v-nota on-resp";
    nota.textContent = NOTA_INDO[r];
    const pai = caixa.parentNode;
    pai.replaceChild(nota, caixa);
    if (typeof raiz.vibrar === "function") raiz.vibrar(8);
    const res = await postar(deps, `/api/onde-vou/${encodeURIComponent(btn.dataset.id)}/resposta`, { resposta: r });
    if (!res || !res.ok) {
      pai.replaceChild(caixa, nota); // volta: o servidor não guardou
      return;
    }
    guardarResp("indo", btn.dataset.id, r);
  });

  // ================================================================== diario_lugares
  const NOTA_DIARIO = "Só o lugar e o tempo que ficou, nunca o caminho. Some depois de 30 dias.";
  function barraDia(barra) {
    const bs = lista(barra).filter((b) => b && numeroValido(b.min) && b.min > 0);
    if (!bs.length) return "";
    return (
      `<div class="on-barra" aria-hidden="true">` +
      bs
        .map((b, i) => {
          const cls = b.vazio ? "vazio" : b.casa ? "casa" : "";
          const fundo = b.vazio || b.casa ? "" : `;--lc:${corSegura(b.cor, COR_FEITO)}`;
          return `<i${cls ? ` class="${cls}"` : ""} style="flex:${Math.round(b.min)};--k:${i}${fundo}"></i>`;
        })
        .join("") +
      `</div>`
    );
  }
  Cards.registrar("diario_lugares", (data) => {
    const d = data || {};
    const titulo = d.titulo || "Teu dia, por onde passou";
    if (d.oculto) return D.pilula({ v: "diario", cor: COR_FEITO, icone: IC_PIN_FINO, titulo });
    const ls = lista(d.lugares).filter((l) => l && l.lugar && l.hora);
    if (!ls.length) return null;
    const n = numeroValido(d.n_lugares) ? d.n_lugares : ls.length;
    const fora = numeroValido(d.fora_min) && d.fora_min > 0 ? duracao(d.fora_min) : "";
    const itens = ls
      .map(
        (l, i) =>
          `<li class="on-lugar${l.casa ? " casa" : ""}" style="--lc:${corSegura(l.cor, COR_FEITO)};--k:${i}">` +
          `<span class="h">${esc(l.hora)}</span><span class="p" aria-hidden="true"></span>` +
          `<span class="c"><b>${esc(l.lugar)}</b>${l.sub ? `<span>${esc(l.sub)}</span>` : ""}</span>` +
          `<span class="dur">${numeroValido(l.min) ? esc(duracao(l.min)) : ""}</span></li>`
      )
      .join("");
    return D.pilula({
      v: "diario",
      cor: COR_FEITO,
      icone: IC_PIN_FINO,
      titulo,
      sub: `<span>${esc(n)} ${n === 1 ? "lugar" : "lugares"}</span>`,
      rotulo: fora ? "fora" : "",
      valor: fora ? esc(fora) : "",
      aberto: true,
      corpo: barraDia(d.barra) + `<ul class="on-diario">${itens}</ul><p class="on-nota">${esc(d.nota || NOTA_DIARIO)}</p>`,
    });
  });

  // ================================================================== meu_tempo
  const num = (v) => (numeroValido(v) ? Number(v) : 0);
  function subMeu(usar, ajuste) {
    return usar === "padrao" ? "o padrão: trajeto + folga" : `${ajuste} min antes: é o teu jeito`;
  }
  function fraseMeu(d) {
    const s = num(d.saida_min);
    const t = num(d.trajeto_min);
    const n = lista(d.amostras).length;
    let txt = "";
    if (s) {
      txt = `Nas últimas ${n} saídas tu saiu de casa uns <b>${esc(s)} min depois</b> do aviso. Então eu já aviso ${esc(s)} min antes.`;
      if (t) txt += ` E nesse horário o caminho leva uns ${esc(t)} min a mais que o Maps diz.`;
    } else if (t) {
      txt = `Nesse horário o caminho leva uns <b>${esc(t)} min a mais</b> que o Maps diz. Então eu já aviso ${esc(t)} min antes.`;
    }
    return txt ? `<p class="v-nota">${txt}</p>` : "";
  }
  function barrinhas(amostras) {
    const vs = lista(amostras).filter(numeroValido).slice(-6);
    if (!vs.length) return "";
    const max = Math.max(...vs.map((v) => Math.abs(v)), 1);
    return (
      `<div class="on-atrasos" role="img" aria-label="Minutos depois do aviso nas últimas ${vs.length} saídas: ${esc(vs.join(", "))}">` +
      vs
        .map((v, i) => {
          const h = Math.max(6, Math.round((Math.abs(v) / max) * 46));
          const rot = v > 0 ? `+${v}` : v < 0 ? `−${Math.abs(v)}` : "0";
          return `<div style="--k:${i}"><i style="height:${h}px"${v < 0 ? ' class="antes"' : ""}></i><small>${esc(rot)}</small></div>`;
        })
        .join("") +
      `</div>`
    );
  }
  function rotuloCompromisso(d) {
    if (d.estilo === "date" || d.estilo === "balada") return d.estilo;
    const p = String(d.titulo || "").trim().split(/\s+/)[0] || "";
    return p.length > 1 && p.length <= 14 ? p.toLowerCase() : "às";
  }
  Cards.registrar("meu_tempo", (data) => {
    const d = data || {};
    if (!d.sair_meu || !d.sair_padrao) return null;
    const usar = d.usar === "padrao" ? "padrao" : "meu";
    const ajuste = num(d.ajuste_min);
    const sair = usar === "meu" ? d.sair_meu : d.sair_padrao;
    const cor = corDe(d.estilo);
    const seg =
      `<div class="on-seg" role="group" aria-label="Qual tempo usar" style="--i:${usar === "meu" ? 0 : 1}">` +
      `<span class="pil" aria-hidden="true"></span>` +
      `<button type="button" data-acao="meu_tempo_usar" data-v="meu" aria-pressed="${usar === "meu"}">Meu tempo</button>` +
      `<button type="button" data-acao="meu_tempo_usar" data-v="padrao" aria-pressed="${usar === "padrao"}">Padrão</button></div>`;
    return D.pilula({
      v: "meu-tempo",
      cor,
      icone: IC_CRONO,
      titulo: `Sai às ${sair}`,
      sub: `<span class="on-sub-meu">${esc(subMeu(usar, ajuste))}</span>`,
      rotulo: d.hora ? rotuloCompromisso(d) : "",
      valor: d.hora ? esc(d.hora) : "",
      aberto: true,
      attrs: ` data-meu="${esc(d.sair_meu)}" data-padrao="${esc(d.sair_padrao)}" data-ajuste="${esc(ajuste)}"`,
      corpo: fraseMeu(d) + barrinhas(d.amostras) + seg,
    });
  });
  function aplicarUsar(v, usar) {
    const seg = v.querySelector(".on-seg");
    if (seg) {
      seg.style.setProperty("--i", usar === "meu" ? "0" : "1");
      seg.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === usar)));
    }
    const t = v.querySelector(".v-t");
    if (t) {
      t.textContent = `Sai às ${usar === "meu" ? v.dataset.meu : v.dataset.padrao}`;
      t.classList.remove("on-troca");
      void t.offsetWidth; // reinicia a animação do título
      t.classList.add("on-troca");
    }
    const s = v.querySelector(".on-sub-meu");
    if (s) s.textContent = subMeu(usar, v.dataset.ajuste);
  }
  Cards.registrarAcao("meu_tempo_usar", async (btn, cardEl, deps) => {
    const v = btn.closest(".vivo-d");
    const usar = btn.dataset.v === "padrao" ? "padrao" : "meu";
    if (!v || btn.getAttribute("aria-pressed") === "true") return;
    const antes = usar === "meu" ? "padrao" : "meu";
    aplicarUsar(v, usar);
    if (typeof raiz.vibrar === "function") raiz.vibrar(6);
    const res = await postar(deps, "/api/tempos-reais/usar", { usar });
    if (!res || !res.ok) aplicarUsar(v, antes);
  });

  // ================================================================== recado_atraso
  // mesmo texto do servidor (onde_vou.texto_recado): os chips trocam só o número
  function textoRecado(modelo, minutos, via) {
    if (modelo === "transito") {
      return `Oi! Peguei trânsito${via ? ` na ${via}` : ""}, chego uns ${minutos} min atrasado. Já tô a caminho.`;
    }
    if (modelo === "saindo") return `Oi! Vou chegar uns ${minutos} min atrasado. Já já tô saindo.`;
    return `Oi! Vou chegar uns ${minutos} min atrasado. Já tô a caminho.`;
  }
  const linkZap = (texto) => `https://wa.me/?text=${encodeURIComponent(texto)}`;
  Cards.registrar("recado_atraso", (data) => {
    const d = data || {};
    if (!d.titulo) return null;
    if (d.oculto) return D.pilula({ v: "recado", cor: COR_PERIGO, icone: IC_BALAO, titulo: "Vai atrasar" });
    let opcoes = lista(d.opcoes).filter((m) => numeroValido(m) && m > 0 && m < 600).slice(0, 3);
    if (!opcoes.length) opcoes = [10, 15, 20];
    const n = numeroValido(d.escolhido) && opcoes.includes(d.escolhido) ? d.escolhido : opcoes[Math.min(1, opcoes.length - 1)];
    const modelo = ["transito", "saindo", "caminho"].includes(d.modelo) ? d.modelo : "caminho";
    const via = typeof d.via === "string" ? d.via.slice(0, 40) : "";
    const texto = textoRecado(modelo, n, via);
    const titulo = d.chega ? `Vai chegar ${d.chega}` : `Vai atrasar uns ${n} min`;
    const sub = `${d.titulo}${d.hora ? ` às ${d.hora}` : ""}${via ? ` · lento na ${via}` : ""}`;
    const resp = lerResp("recado", `${d.tarefa_id}:${d.atraso_min}`);
    const chips =
      `<div class="on-chips" role="group" aria-label="Quanto vai atrasar">` +
      opcoes
        .map((m) => `<button type="button" class="on-chip" data-acao="recado_min" data-m="${esc(m)}" aria-pressed="${m === n}">${esc(m)} min</button>`)
        .join("") +
      `</div>`;
    const acoes = resp
      ? `<p class="v-nota on-resp">Beleza, sem recado.</p>`
      : chips +
        `<div class="on-balao" aria-live="polite">${esc(texto)}</div>` +
        `<div class="v-bts"><a class="pri on-zap" href="${esc(linkZap(texto))}" target="_blank" rel="noopener noreferrer">Abrir no WhatsApp</a>` +
        `<button type="button" data-acao="recado_nao" data-chave="${esc(`${d.tarefa_id}:${d.atraso_min}`)}">Não precisa</button></div>` +
        `<p class="on-nota">Abre o WhatsApp com o texto pronto. Quem manda é tu.</p>`;
    return D.pilula({
      v: "recado",
      cor: COR_PERIGO,
      icone: IC_BALAO,
      titulo,
      sub: `<span>${esc(sub)}</span>`,
      rotulo: numeroValido(d.atraso_min) ? "atraso" : "",
      valor: numeroValido(d.atraso_min) ? esc(`${Math.round(d.atraso_min)} min`) : "",
      aberto: true,
      attrs: ` data-modelo="${esc(modelo)}" data-via="${esc(via)}"`,
      corpo: acoes,
    });
  });
  Cards.registrarAcao("recado_min", (btn) => {
    const v = btn.closest(".vivo-d");
    if (!v) return;
    const m = Number(btn.dataset.m);
    v.querySelectorAll(".on-chip").forEach((c) => c.setAttribute("aria-pressed", String(c === btn)));
    const texto = textoRecado(v.dataset.modelo, m, v.dataset.via);
    const balao = v.querySelector(".on-balao");
    if (balao) {
      balao.textContent = texto;
      balao.classList.remove("on-troca");
      void balao.offsetWidth;
      balao.classList.add("on-troca");
    }
    const zap = v.querySelector(".on-zap");
    if (zap) zap.setAttribute("href", linkZap(texto));
    if (typeof raiz.vibrar === "function") raiz.vibrar(6);
  });
  Cards.registrarAcao("recado_nao", (btn) => {
    const v = btn.closest(".vivo-d");
    const cont = v && v.querySelector(".v-cont");
    if (!cont) return;
    cont.innerHTML = `<p class="v-nota on-resp">Beleza, sem recado.</p>`;
    guardarResp("recado", btn.dataset.chave, "nao");
  });

  const CardsOnde = { duracao, textoRecado, linkZap, linhaTrajeto, barraDia, barrinhas };
  raiz.CardsOnde = CardsOnde;
  if (typeof module !== "undefined" && module.exports) module.exports = CardsOnde;
})(typeof window !== "undefined" ? window : globalThis);
