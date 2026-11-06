// Painel mais esperto, frente 7 (06/11/2026, docs/briefings/2026-11-06-painel-esperto.md): os 3 cards da IA
// que decidem/perguntam sozinhos, todos na casca D (CardsD.pilula, linguagem aprovada em 04/11):
//
//   voo_decisao      "Voo de amanhã, 09:30 / SSBL · navegação" - veredito grande (voa verde, não dá vermelho,
//                    no limite amarelo, sem dado cinza), 4 quadradinhos Teto/Visibilidade/Vento/Sono (o ruim em
//                    vermelho) e a nota do porquê. "Não dá" com horário bom: Remarcar pras HH:MM / Mantém
//                    (POST /api/esperto/voo/<id>/remarcar, com Desfazer).
//   rotina_proposta  "Academia toda terça e quinta / 18:00 · já faz 3 semanas" - Virar rotina / Não
//                    (POST /api/esperto/rotina; "sim" volta com Desfazer).
//   tarefa_adiada    "“Separar os papéis” já foi adiada 3 vezes" - chips Quebrar em passos / Mudar o dia /
//                    Apagar (rotas que já existem + /api/esperto/tarefa/<id>/mudar-dia), cada uma com Desfazer.
//
// Renderizadores PUROS (estado final; histórico abre parado; testes em Node). O que ele respondeu fica no
// localStorage pro histórico não oferecer de novo (mesma regra de cards-onde.js).
(function (raiz) {
  "use strict";
  const Cards = raiz.Cards || (typeof require === "function" ? require("./cards.js") : null);
  const D = raiz.CardsD || (typeof require === "function" ? require("./cards-d.js") : null);
  if (!Cards || !D) return;
  const { esc } = Cards;
  const lista = (v) => (Array.isArray(v) ? v : []);

  const COR_VOO = "#8fd0ff";
  const COR_ROTINA = "#c4a1ff";
  const COR_TAREFA = "#f0a58f";
  const VEREDITOS = ["voa", "nao", "limite", "incerto"];
  const TONS = ["ok", "limite", "ruim"];
  const HORA = /^\d{2}:\d{2}$/;
  const traco = (corpo, w = 2) =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${corpo}</svg>`;
  const IC_ROTINA = traco('<path d="M17 2l3 3-3 3"/><path d="M4 11V9a4 4 0 0 1 4-4h12M7 22l-3-3 3-3"/><path d="M20 13v2a4 4 0 0 1-4 4H4"/>');
  const IC_CRONO = traco('<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2.5 2M9 2h6"/>');

  // ------------------------------------------------------------------ o que ele já respondeu (aparelho)
  const CHAVE = "cards-esperto-resp";
  function lerResp(k) {
    try {
      const m = JSON.parse(raiz.localStorage.getItem(CHAVE) || "{}");
      return (m && m[k]) || null;
    } catch (_) {
      return null;
    }
  }
  function guardarResp(k, valor) {
    try {
      const m = JSON.parse(raiz.localStorage.getItem(CHAVE) || "{}") || {};
      m[k] = valor;
      const chaves = Object.keys(m);
      if (chaves.length > 80) chaves.slice(0, chaves.length - 80).forEach((c) => delete m[c]);
      raiz.localStorage.setItem(CHAVE, JSON.stringify(m));
    } catch (_) {
      /* sem armazenamento: o card só oferece de novo */
    }
  }

  async function pedir(deps, url, metodo, corpo) {
    if (!deps || typeof deps.apiFetch !== "function") return null;
    try {
      const op = { method: metodo || "POST" };
      if (corpo) {
        op.headers = { "Content-Type": "application/json" };
        op.body = JSON.stringify(corpo);
      }
      return await deps.apiFetch(url, op);
    } catch (_) {
      return null;
    }
  }

  // resposta no lugar dos botões; com token, um Desfazer pequeno ao lado (desfaz sem sair do card)
  function respostaHTML(texto, desfazer) {
    const bt = desfazer
      ? `<div class="v-bts"><button type="button" data-acao="esperto_desfazer" data-url="${esc(desfazer.url)}" data-metodo="${esc(desfazer.metodo || "POST")}">Desfazer</button></div>`
      : "";
    return `<div class="es-resp"><p class="v-nota">${esc(texto)}</p>${bt}</div>`;
  }
  function trocarPorResposta(caixa, texto, desfazer) {
    if (!caixa || !caixa.parentNode) return null;
    const doc = raiz.document;
    const tmp = doc.createElement("div");
    tmp.innerHTML = respostaHTML(texto, desfazer);
    const nova = tmp.firstChild;
    caixa.parentNode.replaceChild(nova, caixa);
    if (typeof raiz.vibrar === "function") raiz.vibrar(8);
    return nova;
  }
  const urlDesfazer = (token) => Cards.urlDesfazer(undefined, token);

  // ================================================================== voo_decisao
  const ROTULO_DIR = { amanha: "decide", hoje: "conferido" };
  function quadradinhos(conds) {
    const cs = lista(conds).filter((c) => c && c.rotulo && c.valor);
    if (!cs.length) return "";
    return (
      `<div class="es-cond">` +
      cs
        .map((c, i) => {
          const tom = TONS.includes(c.tom) ? c.tom : "ok";
          return `<div class="${tom}" style="--k:${i}"><small>${esc(c.rotulo)}</small><b>${esc(c.valor)}</b></div>`;
        })
        .join("") +
      `</div>`
    );
  }
  function botoesVoo(d) {
    if (d.veredito !== "nao") return "";
    if (lerResp(`voo:${d.voo_id}:${d.hora}`)) return "";
    const r = d.remarcar;
    if (r && HORA.test(r.hora || "")) {
      return (
        `<div class="v-bts es-bts">` +
        `<button type="button" class="pri" data-acao="esperto_remarcar" data-id="${esc(d.voo_id)}" data-hora="${esc(r.hora)}" data-de="${esc(d.hora)}">Remarcar pras ${esc(r.hora)}</button>` +
        `<button type="button" data-acao="esperto_manter" data-id="${esc(d.voo_id)}" data-de="${esc(d.hora)}">Mantém</button>` +
        `</div>`
      );
    }
    if (d.perguntar_remarcar) {
      return (
        `<div class="v-bts es-bts">` +
        `<button type="button" class="pri" data-acao="esperto_remarcar_chat" data-quando="${esc(d.quando === "hoje" ? "de hoje" : "de amanhã")}">Remarcar</button>` +
        `<button type="button" data-acao="esperto_manter" data-id="${esc(d.voo_id)}" data-de="${esc(d.hora)}">Mantém</button>` +
        `</div>`
      );
    }
    return "";
  }
  Cards.registrar("voo_decisao", (data, card) => {
    const d = data || {};
    if (!d.hora) return null;
    const dia = d.quando === "hoje" ? "hoje" : "amanhã";
    const titulo = `Voo de ${dia}, ${d.hora}`;
    const vd = VEREDITOS.includes(d.veredito) ? d.veredito : "incerto";
    const corpo =
      `<p class="es-veredito" data-vd="${vd}">${esc(d.frase || "Ainda não dá pra saber.")}</p>` +
      quadradinhos(d.conds) +
      (d.nota ? `<p class="v-nota${vd === "limite" ? " alerta" : ""}">${esc(d.nota)}</p>` : "") +
      botoesVoo(d) +
      D.botoes(card, "", ["desfazer"]);
    return D.pilula({
      v: "voo-decisao",
      cor: COR_VOO,
      icone: D.IC.aviao,
      titulo,
      sub: d.sub ? `<span>${esc(d.sub)}</span>` : "",
      rotulo: ROTULO_DIR[d.quando] || "",
      valor: d.quando === "hoje" ? esc(d.emissao ? `TAF ${d.emissao}` : "agora") : "hoje",
      corpo,
      aberto: true,
      attrs: ` data-vd="${vd}"`,
    });
  });
  Cards.registrarAcao("esperto_remarcar", async (btn, cardEl, deps) => {
    const caixa = btn.closest(".es-bts");
    if (!caixa || btn.disabled) return;
    caixa.querySelectorAll("button").forEach((b) => (b.disabled = true));
    const res = await pedir(deps, `/api/esperto/voo/${encodeURIComponent(btn.dataset.id)}/remarcar`, "POST", { hora: btn.dataset.hora });
    if (!res || !res.ok) {
      caixa.querySelectorAll("button").forEach((b) => (b.disabled = false));
      return;
    }
    guardarResp(`voo:${btn.dataset.id}:${btn.dataset.de}`, "remarcou");
    trocarPorResposta(caixa, res.texto || `Remarquei pras ${btn.dataset.hora}.`, res.token ? { url: urlDesfazer(res.token) } : null);
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  });
  Cards.registrarAcao("esperto_manter", (btn) => {
    const caixa = btn.closest(".es-bts");
    if (!caixa) return;
    guardarResp(`voo:${btn.dataset.id}:${btn.dataset.de}`, "manteve");
    trocarPorResposta(caixa, "Ok, mantido. Se o TAF melhorar eu te aviso.");
  });
  // sem horário bom no TAF: a remarcação vai pela conversa (a IA escolhe o dia com ele)
  Cards.registrarAcao("esperto_remarcar_chat", (btn) => {
    const campo = raiz.document && raiz.document.getElementById("chat-input");
    if (!campo) return;
    campo.value = `Remarca o voo ${btn.dataset.quando || ""} pra `.replace(/\s+/g, " ");
    campo.focus();
  });

  // ================================================================== rotina_proposta
  Cards.registrar("rotina_proposta", (data) => {
    const d = data || {};
    if (!d.chave || !d.titulo) return null;
    const resp = lerResp(`rotina:${d.chave}`);
    const corpo =
      `<p class="v-nota">${esc(d.texto || "Viro rotina?")}</p>` +
      (resp
        ? respostaHTML(resp === "sim" ? "Virou rotina." : "Ok, não pergunto mais desse.")
        : `<div class="v-bts es-bts">` +
          `<button type="button" class="pri" data-acao="esperto_rotina" data-r="sim" data-chave="${esc(d.chave)}">Virar rotina</button>` +
          `<button type="button" data-acao="esperto_rotina" data-r="nao" data-chave="${esc(d.chave)}">Não</button>` +
          `</div>`);
    return D.pilula({
      v: "rotina",
      cor: COR_ROTINA,
      icone: IC_ROTINA,
      titulo: d.titulo,
      sub: d.sub ? `<span>${esc(d.sub)}</span>` : "",
      corpo,
      aberto: true,
    });
  });
  Cards.registrarAcao("esperto_rotina", async (btn, cardEl, deps) => {
    const caixa = btn.closest(".es-bts");
    if (!caixa || btn.disabled) return;
    caixa.querySelectorAll("button").forEach((b) => (b.disabled = true));
    const res = await pedir(deps, "/api/esperto/rotina", "POST", { chave: btn.dataset.chave, resposta: btn.dataset.r });
    if (!res || !res.ok) {
      caixa.querySelectorAll("button").forEach((b) => (b.disabled = false));
      return;
    }
    guardarResp(`rotina:${btn.dataset.chave}`, btn.dataset.r);
    trocarPorResposta(caixa, res.texto || "Feito.", res.token ? { url: urlDesfazer(res.token) } : null);
    if (btn.dataset.r === "sim" && typeof deps.aoMudar === "function") deps.aoMudar();
  });

  // ================================================================== tarefa_adiada
  const ACOES_ADIADA = [
    ["passos", "Quebrar em passos"],
    ["dia", "Mudar o dia"],
    ["apagar", "Apagar"],
  ];
  Cards.registrar("tarefa_adiada", (data) => {
    const d = data || {};
    if (d.task_id == null) return null;
    const n = Number(d.adiadas) > 0 ? Math.round(Number(d.adiadas)) : 3;
    const titulo = d.oculto || !d.titulo ? `Tarefa adiada ${n} vezes` : `“${d.titulo}” já foi adiada ${n} vezes`;
    const resp = lerResp(`adiada:${d.task_id}`);
    const corpo = resp
      ? respostaHTML(resp)
      : `<div class="es-chips es-bts">` +
        ACOES_ADIADA.map(
          ([a, r]) => `<button type="button" class="es-chip" data-acao="esperto_adiada" data-a="${a}" data-id="${esc(d.task_id)}">${esc(r)}</button>`
        ).join("") +
        `</div>`;
    return D.pilula({
      v: "adiada",
      cor: COR_TAREFA,
      icone: IC_CRONO,
      titulo,
      sub: `<span>o que eu faço com ela?</span>`,
      corpo,
      aberto: true,
    });
  });
  function textoPassos(res) {
    const n = lista(res && res.subtasks).length;
    return n ? `Quebrei em ${n} passos. Tá na aba Tarefas.` : "Quebrei em passos. Tá na aba Tarefas.";
  }
  Cards.registrarAcao("esperto_adiada", async (btn, cardEl, deps) => {
    const caixa = btn.closest(".es-bts");
    if (!caixa || btn.disabled) return;
    const id = encodeURIComponent(btn.dataset.id);
    const a = btn.dataset.a;
    caixa.querySelectorAll("button").forEach((b) => (b.disabled = true));
    btn.setAttribute("aria-pressed", "true");
    let res = null;
    let texto = "";
    let desfazer = null;
    if (a === "passos") {
      res = await pedir(deps, `/api/tasks/${id}/breakdown`, "POST");
      if (res && Array.isArray(res.subtasks)) {
        texto = textoPassos(res);
        desfazer = { url: `/api/tasks/${id}/subtasks`, metodo: "DELETE" };
      }
    } else if (a === "dia") {
      res = await pedir(deps, `/api/esperto/tarefa/${id}/mudar-dia`, "POST");
      if (res && res.ok) {
        texto = res.texto || "Mudei o dia.";
        if (res.token) desfazer = { url: urlDesfazer(res.token) };
      }
    } else if (a === "apagar") {
      res = await pedir(deps, `/api/tasks/${id}`, "DELETE");
      if (res && res.ok) {
        texto = "Apaguei.";
        if (res.token) desfazer = { url: urlDesfazer(res.token) };
      }
    }
    if (!texto) {
      btn.removeAttribute("aria-pressed");
      caixa.querySelectorAll("button").forEach((b) => (b.disabled = false));
      return;
    }
    guardarResp(`adiada:${btn.dataset.id}`, texto);
    trocarPorResposta(caixa, texto, desfazer);
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  });

  // Desfazer pequeno da resposta (rotina criada, voo remarcado, dia mudado, passos, apagada)
  Cards.registrarAcao("esperto_desfazer", async (btn, cardEl, deps) => {
    if (btn.disabled) return;
    const url = btn.dataset.url || "";
    if (!/^\/api\/(desfazer\/|tasks\/\d+\/subtasks$)/.test(url)) return;
    btn.disabled = true;
    const res = await pedir(deps, url, btn.dataset.metodo === "DELETE" ? "DELETE" : "POST");
    if (!res) {
      btn.disabled = false;
      return;
    }
    const caixa = btn.closest(".es-resp");
    const nota = caixa && caixa.querySelector(".v-nota");
    if (nota) nota.textContent = "Desfeito.";
    const bts = btn.closest(".v-bts");
    if (bts) bts.remove();
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  });

  const CardsEsperto = { quadradinhos, respostaHTML, botoesVoo, textoPassos };
  raiz.CardsEsperto = CardsEsperto;
  if (typeof module !== "undefined" && module.exports) module.exports = CardsEsperto;
})(typeof window !== "undefined" ? window : globalThis);
