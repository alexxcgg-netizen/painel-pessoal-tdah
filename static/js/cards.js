// Registro de cards da aba Hoje (Fase 6, "Padrao Nectar").
//
// Contrato completo em docs/CARDS.md: toda resposta de /api/chat e
// /api/capture traz { cards: [{ type, id, data, actions }], resumo_texto,
// passos }. Este arquivo e o REGISTRO type -> renderizador do front:
//
//   Cards.registrar("meu_tipo", (data, card, ctx) => "<p>...</p>", { consome: ["desfazer"] })
//
// Renderizador = funcao PURA que devolve uma string HTML (todo texto vindo de
// `data` passa por Cards.esc). Por isso da pra testar tudo em Node sem DOM
// (tests/js/cards.test.js). `consome` lista os tipos de action que o proprio
// renderizador ja desenhou no lugar certo - o resto vira o rodape padrao.
//
// Nunca quebra a tela: type desconhecido, card malformado ou erro dentro de
// um renderizador viram o card fallback "Este trecho nao pode ser exibido.
// Os dados foram preservados." (o card original fica em data-card-json).
//
// Carregado ANTES de app.js (index.html): fmtMoeda e resolvido na hora da
// chamada e apiFetch/showTab chegam por Cards.ligar(...), que app.js chama.
// Em Node so a parte pura e usada (module.exports).
(function (raiz) {
  "use strict";

  const TEXTO_FALLBACK = "Este trecho não pode ser exibido. Os dados foram preservados.";
  const registro = new Map();

  // ---- utilitarios puros ----------------------------------------------------

  function esc(valor) {
    if (valor === null || valor === undefined) return "";
    return String(valor)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function numeroValido(v) {
    return typeof v === "number" && Number.isFinite(v);
  }

  // Moeda SEMPRE pelo helper que ja existe no app (fmtMoeda, app.js). O
  // fallback so existe pra rodar em Node (teste) - mesma formatacao.
  function moeda(valor) {
    if (typeof raiz.fmtMoeda === "function") return raiz.fmtMoeda(valor);
    if (typeof fmtMoeda === "function") return fmtMoeda(valor); // eslint-disable-line no-undef
    return Number(valor).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  }

  const MOEDA_OCULTA = "R$ •••";

  // "AAAA-MM-DD" -> Date local (meio-dia, pra nunca escorregar de dia por fuso)
  function parseDia(iso) {
    if (typeof iso !== "string") return null;
    const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!m) return null;
    const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]), 12, 0, 0);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  // "AAAA-MM-DDTHH:MM" (ou "AAAA-MM-DD" + "HH:MM" separado) -> Date local
  function parseDataHora(iso, hora) {
    if (typeof iso !== "string") return null;
    const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/);
    if (!m) return null;
    let h = m[4];
    let min = m[5];
    if (h === undefined && typeof hora === "string") {
      const mh = hora.match(/^(\d{1,2}):(\d{2})/);
      if (mh) {
        h = mh[1];
        min = mh[2];
      }
    }
    if (h === undefined) return null;
    const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]), Number(h), Number(min), 0);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  function mesmoDia(a, b) {
    return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  }

  function diasEntre(a, b) {
    const ua = Date.UTC(a.getFullYear(), a.getMonth(), a.getDate());
    const ub = Date.UTC(b.getFullYear(), b.getMonth(), b.getDate());
    return Math.round((ub - ua) / 86400000);
  }

  const DIAS_SEMANA = ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"];
  const MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
  ];
  const MESES_CURTOS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

  // "quarta 23" (dia da semana sem "-feira" + dia do mes)
  function dataCurta(iso) {
    const d = parseDia(iso);
    if (!d) return "";
    return `${DIAS_SEMANA[d.getDay()]} ${d.getDate()}`;
  }

  // "hoje" / "amanhã" / "ontem" / "quarta 23"
  function rotuloDia(iso, agora) {
    const d = parseDia(iso);
    if (!d) return "";
    const ref = agora instanceof Date ? agora : new Date();
    const delta = diasEntre(ref, d);
    if (delta === 0) return "hoje";
    if (delta === 1) return "amanhã";
    if (delta === -1) return "ontem";
    return dataCurta(iso);
  }

  // "terça, 29 de setembro"
  function dataPorExtenso(d) {
    if (!(d instanceof Date)) return "";
    return `${DIAS_SEMANA[d.getDay()]}, ${d.getDate()} de ${MESES[d.getMonth()]}`;
  }

  // "22 dez"
  function diaMesCurto(iso) {
    const d = parseDia(iso);
    if (!d) return "";
    return `${d.getDate()} ${MESES_CURTOS[d.getMonth()]}`;
  }

  function hhmm(d) {
    if (!(d instanceof Date)) return "";
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  }

  // Contagem regressiva humana: "faltam 23h 6min", "faltam 3 dias",
  // "faltam 12min", "agora", "passou há 5min".
  function textoContagem(alvo, agora) {
    if (!(alvo instanceof Date) || Number.isNaN(alvo.getTime())) return "";
    const ref = agora instanceof Date ? agora : new Date();
    const diffMin = Math.round((alvo.getTime() - ref.getTime()) / 60000);
    if (diffMin === 0) return "agora";
    const abs = Math.abs(diffMin);
    let corpo;
    if (abs >= 48 * 60) {
      const dias = Math.round(abs / (24 * 60));
      corpo = `${dias} dias`;
    } else if (abs >= 60) {
      const h = Math.floor(abs / 60);
      const m = abs % 60;
      corpo = m ? `${h}h ${m}min` : `${h}h`;
    } else {
      corpo = `${abs}min`;
    }
    return diffMin > 0 ? `faltam ${corpo}` : `passou há ${corpo}`;
  }

  // 110 -> "1h50", 45 -> "45 min", 60 -> "1h"
  function fmtDuracao(minutos) {
    const n = Math.max(0, Math.round(Number(minutos) || 0));
    if (n < 60) return `${n} min`;
    const h = Math.floor(n / 60);
    const m = n % 60;
    return m ? `${h}h${String(m).padStart(2, "0")}` : `${h}h`;
  }

  // ---- registro -------------------------------------------------------------

  function registrar(tipo, renderizador, opcoes) {
    if (typeof tipo !== "string" || !tipo || typeof renderizador !== "function") {
      throw new Error("Cards.registrar(tipo, fn): tipo string e fn funcao");
    }
    registro.set(tipo, { fn: renderizador, consome: new Set((opcoes && opcoes.consome) || []) });
  }

  function temRenderizador(tipo) {
    return registro.has(tipo);
  }

  function tiposRegistrados() {
    return Array.from(registro.keys());
  }

  // ---- actions --------------------------------------------------------------

  const ICONE_SETA =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg>';
  const ICONE_DESFAZER =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/></svg>';
  const ICONE_SINO =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>';

  const ICONE_MAPA =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 4 3.5 6v14L9 18l6 2 5.5-2V4L15 6 9 4Z"/><path d="M9 4v14M15 6v14"/></svg>';

  function acoesDoTipo(card, tipo) {
    return (Array.isArray(card && card.actions) ? card.actions : []).filter(
      (a) => a && typeof a === "object" && a.tipo === tipo
    );
  }

  function acaoHTML(acao) {
    if (!acao || typeof acao !== "object") return "";
    if (acao.tipo === "abrir_aba" && typeof acao.aba === "string") {
      const dest = acao.destaque && typeof acao.destaque === "object" ? acao.destaque : null;
      const attrsDestaque = dest
        ? ` data-destaque-entidade="${esc(dest.entidade)}" data-destaque-id="${esc(dest.id)}"`
        : "";
      return `<button type="button" class="card-link" data-acao="abrir_aba" data-aba="${esc(acao.aba)}"${attrsDestaque}>${esc(acao.rotulo || "Abrir")}${ICONE_SETA}</button>`;
    }
    if (acao.tipo === "desfazer" && typeof acao.token === "string") {
      return `<button type="button" class="card-btn card-btn-desfazer" data-acao="desfazer" data-token="${esc(acao.token)}">${ICONE_DESFAZER}<span>${esc(acao.rotulo || "Desfazer")}</span></button>`;
    }
    if (acao.tipo === "despertar" && acao.lembrete_id !== undefined) {
      const ativo = Boolean(acao.ativo);
      return `<button type="button" class="card-btn card-btn-despertar${ativo ? " ativo" : ""}" data-acao="despertar" data-lembrete-id="${esc(acao.lembrete_id)}" aria-pressed="${ativo}">${ICONE_SINO}<span>${esc(acao.rotulo || "Desperta você")}</span></button>`;
    }
    // link externo (card de rota -> Google Maps). So https do proprio Google Maps;
    // qualquer outra URL e ignorada, mesmo que o servidor mande.
    if (acao.tipo === "abrir_link" && typeof acao.url === "string" && /^https:\/\/www\.google\.com\/maps\//.test(acao.url)) {
      return `<a class="card-btn card-btn-link" href="${esc(acao.url)}" target="_blank" rel="noopener noreferrer">${ICONE_MAPA}<span>${esc(acao.rotulo || "Abrir")}</span></a>`;
    }
    return ""; // tipo de action desconhecido: ignora (nunca quebra o card)
  }

  function rodapeHTML(card, consome) {
    const acoes = (Array.isArray(card.actions) ? card.actions : []).filter(
      (a) => a && typeof a === "object" && !consome.has(a.tipo)
    );
    const botoes = acoes.filter((a) => a.tipo !== "abrir_aba").map(acaoHTML).join("");
    const links = acoes.filter((a) => a.tipo === "abrir_aba").map(acaoHTML).join("");
    if (!botoes && !links) return "";
    return `<div class="card-rodape">${botoes ? `<div class="card-rodape-botoes">${botoes}</div>` : ""}${links}</div>`;
  }

  // ---- renderizacao ---------------------------------------------------------

  function jsonSeguro(obj) {
    try {
      return JSON.stringify(obj);
    } catch {
      return "";
    }
  }

  function fallbackHTML(card) {
    const tipo = card && typeof card === "object" && typeof card.type === "string" ? card.type : "";
    return (
      `<article class="card-resultado card-contrato card-contrato-fallback" role="note" data-card-type="${esc(tipo)}" data-card-json="${esc(jsonSeguro(card))}">` +
      `<p class="card-fallback-texto">${esc(TEXTO_FALLBACK)}</p>` +
      `</article>`
    );
  }

  function renderizarCardHTML(card, ctx) {
    try {
      if (!card || typeof card !== "object" || typeof card.type !== "string") return fallbackHTML(card);
      const entrada = registro.get(card.type);
      if (!entrada) return fallbackHTML(card);
      const data = card.data && typeof card.data === "object" ? card.data : {};
      const contexto = Object.assign({ agora: new Date() }, ctx || {});
      const corpo = entrada.fn(data, card, contexto);
      if (typeof corpo !== "string") return fallbackHTML(card);
      const idAttr = typeof card.id === "string" ? ` data-card-id="${esc(card.id)}"` : "";
      // `desfeito` (aditivo, vem do historico): o Desfazer ja foi usado.
      const desfeito = card.desfeito === true ? " card-desfeito" : "";
      const desfeitoAttr = card.desfeito === true ? ' data-desfeito="1"' : "";
      return (
        `<article class="card-resultado card-contrato card-contrato-${esc(card.type)}${desfeito}" data-card-type="${esc(card.type)}"${idAttr}${desfeitoAttr}>` +
        corpo +
        rodapeHTML(card, entrada.consome) +
        `</article>`
      );
    } catch (e) {
      if (typeof console !== "undefined" && console.warn) console.warn("card nao renderizado", e);
      return fallbackHTML(card);
    }
  }

  function renderizarListaHTML(cards, ctx) {
    if (!Array.isArray(cards)) return "";
    return cards.map((c) => renderizarCardHTML(c, ctx)).join("");
  }

  // ---- DOM (so navegador) -----------------------------------------------------

  // Grupo de cards de UMA resposta, pronto pra entrar no #chat-mensagens.
  // `passos` vai junto (o resumo_final le daqui pra lista recolhivel).
  function criarGrupo(cards, passos) {
    const grupo = document.createElement("div");
    grupo.className = "cards-grupo";
    grupo.innerHTML = renderizarListaHTML(cards, { passos: Array.isArray(passos) ? passos : [] });
    grupo.querySelectorAll(".card-contrato").forEach((el, i) => {
      el.style.animationDelay = `${i * 70}ms`;
    });
    grupo.querySelectorAll('[data-desfeito="1"]').forEach(marcarDesfeito);
    atualizarContagens(grupo);
    return grupo;
  }

  // Estado "desfeito": o card fica na conversa, apagado, sem acao que mude
  // dado (so o link pra aba continua).
  function marcarDesfeito(cardEl) {
    if (!cardEl) return;
    cardEl.classList.add("card-desfeito");
    cardEl.querySelectorAll("input, [data-acao]").forEach((el) => {
      if (el.dataset.acao !== "abrir_aba") el.disabled = true;
    });
    cardEl.querySelectorAll('[data-acao="desfazer"]').forEach((btn) => {
      btn.innerHTML = `${ICONE_DESFAZER}<span>Desfeito</span>`;
    });
  }

  function atualizarContagens(raizEl) {
    const agora = new Date();
    (raizEl || document).querySelectorAll("[data-contagem-alvo]").forEach((el) => {
      const alvo = new Date(el.dataset.contagemAlvo);
      const texto = textoContagem(alvo, agora);
      if (texto && el.textContent !== texto) el.textContent = texto;
    });
  }

  let relogio = null;
  function iniciarRelogio() {
    if (relogio || typeof setInterval !== "function") return;
    relogio = setInterval(() => {
      // Vel (vel4): com o app em segundo plano ninguem ve a contagem; ao
      // voltar, o proximo tick (<= 30 s) e o visibilitychange ja atualizam.
      if (typeof document !== "undefined" && document.hidden) return;
      atualizarContagens(document);
    }, 30000);
  }

  function destacarItem(aba, entidade, id) {
    // A lista da aba recarrega async (showTab dispara o load) e troca os <li>
    // - entao continua olhando por ~3s e destaca de novo se o elemento foi
    // substituido (senao o destaque ia pro <li> velho que acabou de sumir).
    let tentativas = 0;
    let ultimo = null;
    const seletor = `#tab-${CSS.escape(aba)} [data-entidade="${CSS.escape(String(entidade))}"][data-id="${CSS.escape(String(id))}"]`;
    const procurar = () => {
      const alvo = document.querySelector(seletor);
      if (alvo && alvo !== ultimo) {
        ultimo = alvo;
        alvo.scrollIntoView({ block: "center", behavior: "smooth" });
        alvo.classList.remove("item-destacado");
        void alvo.offsetWidth;
        alvo.classList.add("item-destacado");
        setTimeout(() => alvo.classList.remove("item-destacado"), 2200);
      }
      if (++tentativas < 15) setTimeout(procurar, 200);
    };
    procurar();
  }

  // Tipos de card cujo Desfazer usa a rota propria da N1 (docs/contrato-assinaturas.md,
  // rotas/n1_financas.py): o desfazer generico (/api/desfazer/<token>) ainda nao conhece
  // essas entidades e responde 404. Quando o generico aprender, basta esvaziar a lista.
  const TIPOS_DESFAZER_FINANCAS = ["assinatura", "compra_parcelada"];

  // Funcao PURA: tipo do card (data-card-type) + token -> URL do POST de desfazer.
  function urlDesfazer(tipoCard, token) {
    const base = TIPOS_DESFAZER_FINANCAS.includes(tipoCard) ? "/api/financas/desfazer/" : "/api/desfazer/";
    return base + encodeURIComponent(token == null ? "" : String(token));
  }

  const handlers = {};

  // Liga a delegacao de eventos UMA vez no container (#chat-mensagens).
  // `deps`: { apiFetch, showTab, aoMudar } - injetados por app.js.
  function ligar(container, deps) {
    if (!container || container.dataset.cardsLigado) return;
    container.dataset.cardsLigado = "1";
    Object.assign(handlers, deps || {});
    iniciarRelogio();

    container.addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-acao]");
      if (!btn || !container.contains(btn)) return;
      const acao = btn.dataset.acao;
      const cardEl = btn.closest(".card-contrato");

      if (acao === "abrir_aba") {
        const aba = btn.dataset.aba;
        if (typeof handlers.showTab === "function") handlers.showTab(aba);
        if (btn.dataset.destaqueEntidade && btn.dataset.destaqueId) {
          destacarItem(aba, btn.dataset.destaqueEntidade, btn.dataset.destaqueId);
        }
        return;
      }

      if (acao === "desfazer" && typeof handlers.apiFetch === "function") {
        if (btn.disabled) return;
        btn.disabled = true;
        const tipoCard = cardEl ? cardEl.dataset.cardType : undefined;
        const res = await handlers.apiFetch(urlDesfazer(tipoCard, btn.dataset.token), {
          method: "POST",
        });
        if (!res) {
          btn.disabled = false;
          return;
        }
        marcarDesfeito(cardEl);
        if (raiz.CardsPremium) raiz.CardsPremium.desfeito(cardEl);
        if (typeof handlers.aoMudar === "function") handlers.aoMudar();
        return;
      }

      if (acao === "despertar" && typeof handlers.apiFetch === "function") {
        if (btn.disabled) return;
        const ativar = btn.getAttribute("aria-pressed") !== "true";
        btn.disabled = true;
        const res = await handlers.apiFetch(`/api/lembretes/${encodeURIComponent(btn.dataset.lembreteId)}/despertar`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ativo: ativar }),
        });
        btn.disabled = false;
        if (!res) return;
        btn.setAttribute("aria-pressed", String(Boolean(res.ativo)));
        btn.classList.toggle("ativo", Boolean(res.ativo));
      }
    });

    container.addEventListener("change", async (e) => {
      const caixa = e.target.closest("input[data-tarefa-id]");
      if (!caixa || typeof handlers.apiFetch !== "function") return;
      const id = encodeURIComponent(caixa.dataset.tarefaId);
      const concluir = caixa.checked;
      caixa.disabled = true;
      const res = await handlers.apiFetch(`/api/tasks/${id}/${concluir ? "complete" : "reabrir"}`, { method: "POST" });
      caixa.disabled = false;
      if (!res) {
        caixa.checked = !concluir;
        return;
      }
      const li = caixa.closest("li");
      if (li) li.classList.toggle("concluida", concluir);
      if (concluir && raiz.CardsPremium) raiz.CardsPremium.festejar(caixa);
      if (typeof handlers.aoMudar === "function") handlers.aoMudar();
    });
  }

  // Bloco do planejar_dia (2026-10-11): "Comer: almoco - arroz..." e "... (até 12:00)" sao
  // convencao do servidor; na tela viram icone de prato e "11:30 –12:00" na coluna da hora.
  const ICONE_TIPO_TAREFA = {
    comer:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 3v8M5 3v5a2 2 0 0 0 4 0V3M7 11v10"/><path d="M17 21V3c-2.2 0-3.5 2.6-3.5 6.5 0 2.4 1.2 3.5 3.5 3.5"/></svg>',
    voo:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.5 13.5 3 11l1.5-1.5 8 1L17 6a2 2 0 0 1 3 3l-4.5 4.5 1 8L15 23l-2.5-7.5"/></svg>',
  };

  function partesTarefa(titulo) {
    let t = String(titulo == null ? "" : titulo).trim();
    let fim = "";
    const m = t.match(/\s*\(at[eé] (\d{2}:\d{2})\)\s*$/i);
    if (m) {
      fim = m[1];
      t = t.slice(0, m.index).trim();
    }
    let tipo = "";
    if (/^comer\s*:/i.test(t)) {
      tipo = "comer";
      t = t.replace(/^comer\s*:\s*/i, "");
      t = t.charAt(0).toUpperCase() + t.slice(1);
    } else if (/^voo\b/i.test(t)) {
      tipo = "voo";
    }
    return { titulo: t || String(titulo || ""), fim, tipo };
  }

  // HTML do titulo (icone + texto escapado) e da coluna de hora ("11:30" + "–12:00").
  function tituloTarefaHTML(titulo) {
    const p = partesTarefa(titulo);
    const icone = p.tipo ? `<span class="card-tarefa-icone" data-tipo="${p.tipo}">${ICONE_TIPO_TAREFA[p.tipo]}</span>` : "";
    return `${icone}${esc(p.titulo)}`;
  }

  function horaTarefaHTML(titulo, hora) {
    const p = partesTarefa(titulo);
    return `${esc(hora || "")}${p.fim && hora ? `<span class="card-tarefa-fim">–${esc(p.fim)}</span>` : ""}`;
  }

  const Cards = {
    partesTarefa,
    tituloTarefaHTML,
    horaTarefaHTML,
    TEXTO_FALLBACK,
    MOEDA_OCULTA,
    registrar,
    temRenderizador,
    tiposRegistrados,
    renderizarCardHTML,
    renderizarListaHTML,
    fallbackHTML,
    acaoHTML,
    acoesDoTipo,
    esc,
    moeda,
    numeroValido,
    parseDia,
    parseDataHora,
    mesmoDia,
    diasEntre,
    dataCurta,
    rotuloDia,
    dataPorExtenso,
    diaMesCurto,
    hhmm,
    textoContagem,
    fmtDuracao,
    criarGrupo,
    urlDesfazer,
    ligar,
    atualizarContagens,
  };

  raiz.Cards = Cards;
  if (typeof module !== "undefined" && module.exports) module.exports = Cards;
})(typeof window !== "undefined" ? window : globalThis);
