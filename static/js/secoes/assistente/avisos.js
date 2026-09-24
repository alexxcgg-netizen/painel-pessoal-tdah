// static/js/secoes/assistente/avisos.js - Fase 7, faixa P1b: secao "Avisos"
// da tela Assistente (templates/secoes/assistente/avisos.html) - liga/desliga
// por tipo, canal (push/caixa/ambos) e horario de silencio global.
//
// API consumida (rotas/p8_avisos.py - ja mesclada na integracao):
//   GET /api/assistente/avisos            -> {tipos: [{tipo,label,ligado,canal,...}], silencio: {inicio,fim}}
//   PUT /api/assistente/avisos/<tipo>      body {ligado?, canal?}
//   PUT /api/assistente/avisos/silencio    body {inicio, fim}  (HH:MM)
//
// Estrutura dupla de export igual caixa.js/regras.js: logica pura testavel
// via module.exports (Node), wiring de DOM/fetch guardado pra navegador.
const AvisosAssistente = (function () {
  function esc(valor) {
    if (valor === null || valor === undefined) return "";
    return String(valor)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  const CANAIS = ["push", "caixa", "ambos"];
  const ROTULO_CANAL = { push: "Push", caixa: "Caixa", ambos: "Ambos" };

  function renderOpcoesCanalHTML(tipo) {
    return CANAIS.map((c) => `<option value="${c}"${c === tipo.canal ? " selected" : ""}>${ROTULO_CANAL[c]}</option>`).join("");
  }

  // C2: cada tipo e uma LINHA da lista (.lista-item com divisor), nao um card dentro do
  // card da secao; o canal e um <select class="campo"> direto (antes era um <label
  // class="campo"> com outro campo dentro - caixa dentro de caixa).
  function renderTipoHTML(tipo) {
    const rotulo = esc(tipo.label);
    return (
      `<li class="lista-item aviso-item" data-tipo="${esc(tipo.tipo)}">` +
      `<label class="aviso-toggle">` +
      `<input type="checkbox" class="aviso-ligado" data-tipo="${esc(tipo.tipo)}"${tipo.ligado ? " checked" : ""}>` +
      `<span class="aviso-label">${rotulo}</span>` +
      `</label>` +
      `<select class="campo aviso-canal" data-tipo="${esc(tipo.tipo)}" aria-label="Canal: ${rotulo}">${renderOpcoesCanalHTML(tipo)}</select>` +
      `</li>`
    );
  }

  // "12 de 50 ligados" - vai no cabecalho da secao recolhivel (a lista comeca fechada).
  function textoContagem(tipos) {
    if (!Array.isArray(tipos) || !tipos.length) return "";
    const ligados = tipos.filter((t) => t && t.ligado).length;
    return `${ligados} de ${tipos.length} ligados`;
  }

  function renderListaHTML(tipos) {
    if (!Array.isArray(tipos) || !tipos.length) {
      return `<li class="avisos-vazio">Nenhum tipo de aviso cadastrado.</li>`;
    }
    return tipos.map(renderTipoHTML).join("");
  }

  // Sempre HH:MM valido (o backend recusa qualquer outra coisa) - so
  // normaliza pra nunca deixar o <input type=time> sem valor.
  function horaValida(valor) {
    return typeof valor === "string" && /^([01]\d|2[0-3]):[0-5]\d$/.test(valor);
  }

  return { esc, CANAIS, ROTULO_CANAL, renderTipoHTML, renderListaHTML, horaValida, textoContagem };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = AvisosAssistente;
}

if (typeof document !== "undefined" && typeof window !== "undefined") {
  (function () {
    function wireItens(lista) {
      lista.querySelectorAll(".aviso-ligado").forEach((el) => {
        if (el.dataset.wired) return;
        el.dataset.wired = "1";
        el.addEventListener("change", () => atualizarTipo(el.dataset.tipo, { ligado: el.checked }));
      });
      lista.querySelectorAll(".aviso-canal").forEach((el) => {
        if (el.dataset.wired) return;
        el.dataset.wired = "1";
        el.addEventListener("change", () => atualizarTipo(el.dataset.tipo, { canal: el.value }));
      });
    }

    async function carregarAvisos() {
      const lista = document.getElementById("avisos-lista");
      if (!lista) return;
      const dados = await apiFetch("/api/assistente/avisos");
      if (!dados) return;
      lista.innerHTML = AvisosAssistente.renderListaHTML(dados.tipos);
      wireItens(lista);
      atualizarContagem(dados.tipos);

      const inicio = document.getElementById("avisos-silencio-inicio");
      const fim = document.getElementById("avisos-silencio-fim");
      if (inicio && fim && dados.silencio) {
        if (AvisosAssistente.horaValida(dados.silencio.inicio)) inicio.value = dados.silencio.inicio;
        if (AvisosAssistente.horaValida(dados.silencio.fim)) fim.value = dados.silencio.fim;
      }
    }

    let tiposAtuais = [];
    function atualizarContagem(tipos) {
      if (Array.isArray(tipos)) tiposAtuais = tipos;
      const el = document.getElementById("avisos-contagem");
      if (el) el.textContent = AvisosAssistente.textoContagem(tiposAtuais);
    }

    async function atualizarTipo(tipo, campos) {
      if (!tipo) return;
      const r = await apiFetch(`/api/assistente/avisos/${encodeURIComponent(tipo)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(campos),
      });
      if (!r) return;
      const atual = tiposAtuais.find((t) => t && t.tipo === tipo);
      if (atual) Object.assign(atual, campos);
      atualizarContagem();
      vibrar(15);
    }

    function wireFormSilencio() {
      const form = document.getElementById("avisos-silencio-form");
      if (!form || form.dataset.wired) return;
      form.dataset.wired = "1";
      form.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const inicio = document.getElementById("avisos-silencio-inicio").value;
        const fim = document.getElementById("avisos-silencio-fim").value;
        const r = await apiFetch("/api/assistente/avisos/silencio", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ inicio, fim }),
        });
        if (!r) return;
        vibrar(15);
        tocarSomSucesso();
      });
    }

    wireFormSilencio();

    const btnAbaAssistente = document.querySelector('.tab-btn[data-tab="assistente"]');
    if (btnAbaAssistente) {
      btnAbaAssistente.addEventListener("click", carregarAvisos);
    }

    window.carregarAvisosAssistente = carregarAvisos;
  })();
}
