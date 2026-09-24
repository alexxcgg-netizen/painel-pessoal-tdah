// static/js/secoes/assistente/regras.js - Fase 7, faixa P1b: secao "Regras"
// da tela Assistente (templates/secoes/assistente/regras.html) - lista as
// regras em portugues criadas pelo Alex (faixa P4), com pausar/retomar/apagar.
//
// API consumida (rotas/p4_regras.py, contrato em docs/agentes/fase7-regras-faixa.md):
//   GET    /api/p4_regras              -> {regras: [{id, texto_original, json:{gatilho,...}, ativa, pausada_ate, criada_em, ultima_vez}]}
//   POST   /api/p4_regras/<id>/pausar  body {} (indeterminado) | {dias:N} | {ate: ISO}
//   POST   /api/p4_regras/<id>/retomar
//   DELETE /api/p4_regras/<id>
//
// Estrutura dupla de export igual caixa.js/visao-dia.js: logica pura testavel
// via module.exports (Node), wiring de DOM/fetch guardado pra navegador.
const RegrasAssistente = (function () {
  function esc(valor) {
    if (valor === null || valor === undefined) return "";
    return String(valor)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  const ROTULO_GATILHO = {
    horario: "Horario",
    gasto_categoria: "Gasto por categoria",
    habito_nao_feito_ate: "Habito nao feito",
    tarefa_vencida: "Tarefa vencida",
    sinal_iphone: "Sinal do iPhone",
  };

  function rotuloGatilho(regra) {
    const gatilho = regra && regra.json && regra.json.gatilho;
    return ROTULO_GATILHO[gatilho] || gatilho || "Regra";
  }

  // Pausa indeterminada usa a data-sentinela 9999-12-31 (ver rotas/p4_regras.py,
  // _PAUSA_INDETERMINADA) - trata como "pausada" sem tentar formatar a data.
  function statusRegra(regra) {
    if (!regra) return { pausada: false, texto: "Ativa" };
    if (!regra.pausada_ate) return { pausada: false, texto: "Ativa" };
    if (String(regra.pausada_ate).startsWith("9999")) {
      return { pausada: true, texto: "Pausada" };
    }
    return { pausada: true, texto: `Pausada ate ${esc(regra.pausada_ate)}` };
  }

  function renderRegraHTML(regra) {
    const status = statusRegra(regra);
    const botaoPausaRetoma = status.pausada
      ? `<button type="button" class="btn btn-secundario regra-retomar" data-id="${esc(regra.id)}">Retomar</button>`
      : `<button type="button" class="btn btn-secundario regra-pausar" data-id="${esc(regra.id)}">Pausar</button>`;
    return (
      `<li class="card regra-item" data-id="${esc(regra.id)}">` +
      `<span class="chip regra-gatilho">${esc(rotuloGatilho(regra))}</span>` +
      `<p class="card-titulo regra-texto">${esc(regra.texto_original)}</p>` +
      `<p class="regra-status ${status.pausada ? "regra-status-pausada" : "regra-status-ativa"}">${esc(status.texto)}</p>` +
      `<div class="regra-acoes">` +
      botaoPausaRetoma +
      `<button type="button" class="btn btn-perigo regra-apagar" data-id="${esc(regra.id)}">Apagar</button>` +
      `</div>` +
      `</li>`
    );
  }

  function renderListaHTML(regras) {
    if (!Array.isArray(regras) || !regras.length) {
      return `<li class="regras-vazio">Nenhuma regra criada ainda.</li>`;
    }
    return regras.map(renderRegraHTML).join("");
  }

  return { esc, rotuloGatilho, statusRegra, renderRegraHTML, renderListaHTML, ROTULO_GATILHO };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = RegrasAssistente;
}

if (typeof document !== "undefined" && typeof window !== "undefined") {
  (function () {
    function wireAcoes(lista) {
      lista.querySelectorAll(".regra-pausar").forEach((btn) => {
        if (btn.dataset.wired) return;
        btn.dataset.wired = "1";
        btn.addEventListener("click", () => pausar(btn.dataset.id));
      });
      lista.querySelectorAll(".regra-retomar").forEach((btn) => {
        if (btn.dataset.wired) return;
        btn.dataset.wired = "1";
        btn.addEventListener("click", () => retomar(btn.dataset.id));
      });
      lista.querySelectorAll(".regra-apagar").forEach((btn) => {
        if (btn.dataset.wired) return;
        btn.dataset.wired = "1";
        btn.addEventListener("click", () => apagar(btn.dataset.id));
      });
    }

    async function carregarRegras() {
      const lista = document.getElementById("regras-lista");
      if (!lista) return;
      const dados = await apiFetch("/api/p4_regras");
      if (!dados) return;
      lista.innerHTML = RegrasAssistente.renderListaHTML(dados.regras);
      wireAcoes(lista);
    }

    async function pausar(id) {
      if (!id) return;
      const r = await apiFetch(`/api/p4_regras/${encodeURIComponent(id)}/pausar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!r) return;
      vibrar(15);
      carregarRegras();
    }

    async function retomar(id) {
      if (!id) return;
      const r = await apiFetch(`/api/p4_regras/${encodeURIComponent(id)}/retomar`, { method: "POST" });
      if (!r) return;
      vibrar(15);
      carregarRegras();
    }

    async function apagar(id) {
      if (!id) return;
      if (!window.confirm("Apagar esta regra? Nao da pra desfazer.")) return;
      const r = await apiFetch(`/api/p4_regras/${encodeURIComponent(id)}`, { method: "DELETE" });
      if (!r) return;
      vibrar(15);
      carregarRegras();
    }

    const btnAbaAssistente = document.querySelector('.tab-btn[data-tab="assistente"]');
    if (btnAbaAssistente) {
      btnAbaAssistente.addEventListener("click", carregarRegras);
    }

    window.carregarRegrasAssistente = carregarRegras;
  })();
}
