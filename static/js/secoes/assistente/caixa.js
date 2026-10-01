// static/js/secoes/assistente/caixa.js - Fase 7, faixa P1b: secao "Caixa" da
// tela Assistente (templates/secoes/assistente/caixa.html) E a faixa
// compacta do topo da aba Hoje (montada via JS dentro de #caixa-assistente,
// ja existente em templates/abas/hoje.html - nao edite aquele HTML).
//
// API consumida (contrato da faixa P1a, assistente/contrato.py):
//   GET  /api/assistente/caixa?estado=&limite=  -> {itens: [...], pendentes: N}
//   POST /api/assistente/caixa/<id>/responder    body {resposta, texto?}
//   GET  /api/assistente/saude                   -> {atrasado, minutos_desde_ultimo_tick, ...}
//
// Estrutura dupla de export igual visao-dia.js/fila-offline.js: em navegador
// vira o global `CaixaAssistente` (script classico); em Node (testes, sem
// DOM) so a logica PURA (render de HTML a partir de dados, sem fetch/DOM)
// fica acessivel via module.exports - o wiring de fetch/DOM e conferido a
// parte, no Playwright headless (ver docs/agentes/fase7-regras-faixa.md).
const CaixaAssistente = (function () {
  // ---- logica pura (sem DOM/fetch - testavel isolado) ----------------------

  function esc(valor) {
    if (valor === null || valor === undefined) return "";
    return String(valor)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  const ROTULO_TIPO = {
    pergunta: "Pergunta",
    aviso: "Aviso",
    sugestao: "Sugestão",
    briefing: "Briefing",
    proposta_memoria: "Memória",
  };

  const ROTULO_RESPOSTA = {
    sim: "Sim",
    nao: "Não",
    adiar: "Adiar",
    aceitar: "Aceitar",
    recusar: "Recusar",
  };

  // Quando o item nao traz `opcoes` proprias (contrato: campo opcional), a
  // faixa produtora nao especificou botao nenhum - usa um conjunto padrao
  // coerente com o tipo, sempre dentro do vocabulario de RESPOSTAS_PADRAO de
  // assistente/caixa.py (sim|nao|adiar|aceitar|recusar).
  const OPCOES_PADRAO_POR_TIPO = {
    pergunta: ["sim", "nao", "adiar"],
    aviso: ["aceitar", "adiar"],
    sugestao: ["aceitar", "recusar"],
    briefing: ["aceitar"],
    proposta_memoria: ["aceitar", "recusar"],
  };

  // `item.opcoes` pode vir null/ausente (usa o padrao do tipo), lista de
  // strings ("Sim", "Ainda nao", "Adiar") ou lista de {label, valor} - ver
  // assistente/caixa.py `resolver()`: opcao string vira ela mesma no set de
  // respostas validas, opcao objeto usa `opcao["valor"]`.
  function normalizarOpcoes(item) {
    const opcoes =
      item && Array.isArray(item.opcoes) ? item.opcoes.filter((o) => o !== null && o !== undefined) : [];
    if (opcoes.length) {
      return opcoes.map((op) => {
        if (typeof op === "object") {
          const valor = op.valor !== undefined && op.valor !== null ? op.valor : op.label;
          const rotulo = op.label !== undefined && op.label !== null ? op.label : valor;
          return { rotulo: String(rotulo), valor: String(valor) };
        }
        return { rotulo: String(op), valor: String(op) };
      });
    }
    const padrao = (item && OPCOES_PADRAO_POR_TIPO[item.tipo]) || ["aceitar", "recusar"];
    return padrao.map((valor) => ({ rotulo: ROTULO_RESPOSTA[valor] || valor, valor }));
  }

  // As N mais urgentes pra faixa compacta - a lista que a API devolve
  // (GET /api/assistente/caixa, estado=pendente) ja vem ordenada por
  // urgencia (assistente/caixa.py: pergunta vencida > pergunta > aviso >
  // sugestao > briefing/memoria), entao aqui e so um slice.
  function itensUrgentes(itens, limite) {
    if (!Array.isArray(itens)) return [];
    return itens.slice(0, limite === undefined ? 3 : limite);
  }

  function textoContagem(pendentes) {
    const n = Number(pendentes) || 0;
    return `Pendências do assistente (${n})`;
  }

  // Aviso discreto quando o tick (POST /api/tick, cron externo) esta
  // atrasado - null quando nao ha nada a avisar (saude ausente, tick em dia,
  // ou dado inesperado).
  function textoAtraso(saude) {
    if (!saude || !saude.atrasado) return null;
    const min = saude.minutos_desde_ultimo_tick;
    if (min === null || min === undefined) {
      return "O assistente ainda não rodou nesta instalação.";
    }
    const minArred = Math.max(0, Math.round(min));
    return `O assistente está atrasado (última verificação há ${minArred} min).`;
  }

  function renderBotoesHTML(item) {
    return normalizarOpcoes(item)
      .map(
        (op) =>
          `<button type="button" class="btn btn-secundario caixa-item-opcao" data-item-id="${esc(item.id)}" data-valor="${esc(op.valor)}">${esc(op.rotulo)}</button>`
      )
      .join("");
  }

  function renderItemHTML(item) {
    const corpo = item.corpo ? `<p class="caixa-item-corpo">${esc(item.corpo)}</p>` : "";
    return (
      `<li class="card caixa-item" data-item-id="${esc(item.id)}" data-tipo="${esc(item.tipo)}">` +
      `<span class="chip chip--compacto caixa-item-tipo">${esc(ROTULO_TIPO[item.tipo] || item.tipo)}</span>` +
      `<p class="card-titulo caixa-item-titulo">${esc(item.titulo)}</p>` +
      corpo +
      `<div class="caixa-item-acoes">${renderBotoesHTML(item)}</div>` +
      `</li>`
    );
  }

  function renderListaHTML(itens, opts) {
    const vazio = (opts && opts.vazio) || "Nada pendente por aqui.";
    if (!Array.isArray(itens) || !itens.length) {
      return `<li class="caixa-vazio">${esc(vazio)}</li>`;
    }
    return itens.map(renderItemHTML).join("");
  }

  function renderHistoricoItemHTML(item) {
    const rotuloResposta = ROTULO_RESPOSTA[item.resposta] || item.resposta || "-";
    const textoResp = item.resposta_texto ? ` - "${esc(item.resposta_texto)}"` : "";
    return (
      `<li class="card caixa-item caixa-item-historico" data-item-id="${esc(item.id)}">` +
      `<span class="chip chip--compacto caixa-item-tipo">${esc(ROTULO_TIPO[item.tipo] || item.tipo)}</span>` +
      `<p class="card-titulo caixa-item-titulo">${esc(item.titulo)}</p>` +
      `<p class="caixa-item-resposta">Resposta: ${esc(rotuloResposta)}${textoResp}</p>` +
      `</li>`
    );
  }

  function renderHistoricoHTML(itens) {
    if (!Array.isArray(itens) || !itens.length) {
      return `<li class="caixa-vazio">Ainda sem histórico.</li>`;
    }
    return itens.map(renderHistoricoItemHTML).join("");
  }

  return {
    esc,
    ROTULO_TIPO,
    ROTULO_RESPOSTA,
    OPCOES_PADRAO_POR_TIPO,
    normalizarOpcoes,
    itensUrgentes,
    textoContagem,
    textoAtraso,
    renderItemHTML,
    renderListaHTML,
    renderHistoricoItemHTML,
    renderHistoricoHTML,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = CaixaAssistente;
}

// ---- wiring de DOM/fetch (so em navegador) -------------------------------
if (typeof document !== "undefined" && typeof window !== "undefined") {
  (function () {
    let ultimosItens = [];
    let ultimosPendentes = 0;

    function atualizarSelo(pendentes) {
      const n = Number(pendentes) || 0;
      document.querySelectorAll(".nav-selo").forEach((el) => {
        el.textContent = n > 99 ? "99+" : String(n);
        el.hidden = n <= 0;
      });
    }

    // Toggle de `.secao-recolhivel`: a faixa V0c (static/js/ui/secao-recolhivel.js,
    // ja mesclada na integracao) liga sozinha toda `.secao-recolhivel` da
    // pagina, inclusive a que este arquivo injeta via innerHTML depois do
    // carregamento (ela observa o DOM com MutationObserver) - ver
    // docs/agentes/fase7-visual.md. So chamamos `ligarSecoesRecolhiveis`
    // explicitamente por seguranca (idempotente - `ligarUma` nunca liga a
    // mesma secao 2x) com um fallback minimo pro caso raro de rodar sem
    // aquele script carregado (ex.: alguem abrir este HTML fora da pagina
    // inteira, em teste manual).
    function wireToggleRecolhivel(secao) {
      if (!secao) return;
      if (typeof window.ligarSecoesRecolhiveis === "function") {
        window.ligarSecoesRecolhiveis(secao);
        return;
      }
      const cabecalho = secao.querySelector(".secao-cabecalho");
      if (!cabecalho || cabecalho.dataset.temToggle) return;
      cabecalho.dataset.temToggle = "1";
      cabecalho.addEventListener("click", () => {
        const aberto = secao.dataset.aberto !== "false";
        secao.dataset.aberto = aberto ? "false" : "true";
        cabecalho.setAttribute("aria-expanded", String(!aberto));
      });
    }

    // R2 (reformulação): o card "Pendências do assistente" saiu do topo do Início (a lista
    // inteira mora em Mais › Avisos e regras, que já tem o selo). No Início fica só um aviso
    // de 1 linha, tocável, que aparece quando há pendência (ou quando o assistente está
    // atrasado - #caixa-compacta-atraso, preenchido por carregarSaude).
    function montarFaixaCompacta() {
      const raiz = document.getElementById("caixa-assistente");
      if (!raiz || raiz.dataset.montado) return;
      raiz.dataset.montado = "1";
      raiz.innerHTML =
        '<button type="button" class="caixa-aviso-linha" id="caixa-compacta-linha" data-abre-tela="ajustes-ia" hidden>' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 1.5h-15z"/><path d="M10 20.5a2 2 0 0 0 4 0"/></svg>' +
        '<span id="caixa-compacta-titulo">' +
        CaixaAssistente.textoContagem(0) +
        "</span>" +
        '<svg class="caixa-aviso-seta" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9.5 6 6 6-6 6"/></svg>' +
        "</button>" +
        '<button type="button" class="caixa-aviso-linha caixa-aviso-atraso-linha" data-abre-tela="ajustes-ia" id="caixa-compacta-atraso" hidden></button>';
    }

    function wireBotoesResposta(container) {
      if (!container) return;
      container.querySelectorAll(".caixa-item-opcao").forEach((btn) => {
        if (btn.dataset.wired) return;
        btn.dataset.wired = "1";
        btn.addEventListener("click", () => {
          responderItem(btn.dataset.itemId, btn.dataset.valor);
        });
      });
    }

    function renderFaixaCompacta() {
      const titulo = document.getElementById("caixa-compacta-titulo");
      const linha = document.getElementById("caixa-compacta-linha");
      if (!titulo || !linha) return;
      titulo.textContent = CaixaAssistente.textoContagem(ultimosPendentes);
      linha.hidden = ultimosPendentes <= 0;
    }

    function renderSecaoCompleta() {
      const listaPendentes = document.getElementById("caixa-lista-pendentes");
      const titulo = document.getElementById("caixa-secao-titulo");
      if (titulo) titulo.textContent = CaixaAssistente.textoContagem(ultimosPendentes);
      if (listaPendentes) {
        listaPendentes.innerHTML = CaixaAssistente.renderListaHTML(ultimosItens, { vazio: "Nada pendente por aqui." });
        wireBotoesResposta(listaPendentes);
      }
    }

    async function carregarHistorico() {
      const lista = document.getElementById("caixa-lista-historico");
      if (!lista) return;
      const dados = await apiFetch("/api/assistente/caixa?estado=resolvido&limite=100");
      if (!dados) return;
      lista.innerHTML = CaixaAssistente.renderHistoricoHTML(dados.itens);
    }

    async function carregarCaixa() {
      const dados = await apiFetch("/api/assistente/caixa");
      if (!dados) return;
      ultimosItens = Array.isArray(dados.itens) ? dados.itens : [];
      ultimosPendentes = Number(dados.pendentes) || 0;
      atualizarSelo(ultimosPendentes);
      renderFaixaCompacta();
      renderSecaoCompleta();
    }

    async function carregarSaude() {
      const dados = await apiFetch("/api/assistente/saude");
      const aviso = document.getElementById("caixa-compacta-atraso");
      if (!aviso) return;
      const texto = dados ? CaixaAssistente.textoAtraso(dados) : null;
      if (texto) {
        aviso.textContent = texto;
        aviso.hidden = false;
      } else {
        aviso.hidden = true;
        aviso.textContent = "";
      }
    }

    async function responderItem(itemId, valor) {
      if (!itemId || !valor) return;
      const r = await apiFetch(`/api/assistente/caixa/${encodeURIComponent(itemId)}/responder`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resposta: valor }),
      });
      if (!r) return;
      vibrar(15);
      // Some com animacao discreta (classe CSS + transitionend, com timeout
      // de seguranca caso o navegador nao dispare o evento) antes de
      // recarregar a lista/contagem de verdade a partir do servidor.
      const seletorId = window.CSS && CSS.escape ? CSS.escape(String(itemId)) : itemId;
      document.querySelectorAll(`.caixa-item[data-item-id="${seletorId}"]`).forEach((el) => {
        el.classList.add("caixa-item-saindo");
        const recarregar = () => carregarCaixa();
        el.addEventListener("transitionend", recarregar, { once: true });
        setTimeout(recarregar, 400);
      });
    }

    montarFaixaCompacta();
    wireToggleRecolhivel(document.querySelector('#secao-caixa-assistente .secao-recolhivel[data-secao-id="caixa-historico"]'));
    carregarCaixa();
    carregarSaude();

    // A aba Assistente ainda nao entra no roteiro de showTab() (nucleo/navegacao.js
    // nao e arquivo desta faixa - anotado em scripts/ralph-p1b-caixa-ui/progress.txt).
    // A propria secao recarrega os dados no clique do botao da barra.
    // R1: a caixa mudou pra tela "ajustes-ia" (sem botao na barra) - recarrega quando
    // ela abre (evento de showTab), por qualquer caminho.
    document.addEventListener("aba:aberta", (ev) => {
      if (!ev.detail || ev.detail.aba !== "ajustes-ia") return;
      carregarCaixa();
      carregarHistorico();
    });

    window.carregarCaixaAssistente = carregarCaixa;
  })();
}
