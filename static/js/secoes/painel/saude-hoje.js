// static/js/secoes/painel/saude-hoje.js - Secao painel > saude-hoje (HTML: templates/secoes/painel/saude-hoje.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 1219-1283.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadSaude() {
  const data = await apiFetch("/api/saude/hoje");
  if (!data) return;

  $("#saude-oculto-visitante").hidden = !data.oculto;
  if (data.oculto) {
    $("#saude-vazio").hidden = true;
    $("#saude-grid").hidden = true;
    $("#dica-sono").hidden = true;
    $("#dica-humor").hidden = true;
    $("#hidratacao-total").textContent = "-";
    return;
  }

  const dados = data.dados;
  const temAlgumDado =
    dados && (dados.passos != null || dados.distancia_km != null || dados.sono_horas != null);

  $("#saude-vazio").hidden = temAlgumDado;
  $("#saude-grid").hidden = !temAlgumDado;
  $("#hidratacao-total").textContent = data.hidratacao_hoje ?? 0;
  definirNivelCopo(data.hidratacao_hoje ?? 0);

  const dicaSono = $("#dica-sono");
  dicaSono.hidden = !data.dica_sono;
  dicaSono.textContent = data.dica_sono || "";
  const dicaHumor = $("#dica-humor");
  dicaHumor.hidden = !data.dica_humor;
  dicaHumor.textContent = data.dica_humor || "";

  if (!temAlgumDado) return;

  $("#saude-passos").textContent = dados.passos != null ? dados.passos.toLocaleString("pt-BR") : "-";
  if (dados.passos != null && !window._c2SaudeContou && typeof animarNumero === "function") {
    window._c2SaudeContou = true; // conta so na 1a exibicao
    animarNumero($("#saude-passos"), dados.passos, (v) => Math.round(v).toLocaleString("pt-BR"));
  }
  $("#saude-distancia").textContent = dados.distancia_km != null ? dados.distancia_km.toFixed(1) : "-";
  $("#saude-sono").textContent = dados.sono_horas != null ? dados.sono_horas.toFixed(1) : "-";
}

// anim2: o copo "enche" (scaleY do .hidratacao-nivel, meta de 8 copos/dia) e o
// contador da um micro-pulse - sem particulas, glow nem "+1" flutuante.
const HIDRATACAO_META_COPOS = 8;
function definirNivelCopo(total) {
  const el = document.getElementById("hidratacao-nivel");
  const n = parseInt(total, 10);
  if (!el) return;
  el.style.setProperty("--nivel", String(Number.isFinite(n) ? Math.max(0, Math.min(1, n / HIDRATACAO_META_COPOS)) : 0));
}

function celebrarHidratacao() {
  vibrar(15);
}

// Vel A2b: +1 copo otimista - o contador sobe e a animacao roda na hora do
// toque, sem esperar o POST. Se a rede falhar, desfaz o contador (o aviso ja
// vem do apiFetch via mostrarErro).
let pendenteHidratacao = 0;
$("#hidratacao-btn").addEventListener("click", async () => {
  // anim2: o botao NUNCA fica disabled durante o POST (iOS descarta o 2o toque
  // e perde o :active) - 2 toques rapidos = 2 copos, cada um com seu POST.
  const btn = $("#hidratacao-btn");
  const totalEl = $("#hidratacao-total");
  const anterior = totalEl.textContent;
  pendenteHidratacao++;
  totalEl.textContent = calcularProximoTotalHidratacao(anterior);
  definirNivelCopo(totalEl.textContent);
  pulsarSucesso(totalEl);
  celebrarHidratacao(btn);

  const data = await apiFetch("/api/hidratacao", { method: "POST" });
  if (!data) {
    pendenteHidratacao = Math.max(0, pendenteHidratacao - 1);
    // desfaz so este copo (outro toque pode ter somado por cima)
    const atual = parseInt(totalEl.textContent, 10);
    totalEl.textContent = Number.isFinite(atual) ? Math.max(0, atual - 1) : anterior;
    definirNivelCopo(totalEl.textContent);
    return;
  }
  pendenteHidratacao = Math.max(0, pendenteHidratacao - 1);
  if (pendenteHidratacao > 0) return; // ha outro POST em voo: o ultimo sincroniza
  totalEl.textContent = data.total_hoje; // sincroniza com o valor real do servidor
  definirNivelCopo(data.total_hoje);
});

// Vel A2b: extraido pra teste puro (node --test) - mesma logica usada no
// clique de +1 copo (otimista) e no desfazer em erro.
function calcularProximoTotalHidratacao(atualTexto) {
  const n = parseInt(atualTexto, 10);
  return Number.isFinite(n) ? n + 1 : atualTexto;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { calcularProximoTotalHidratacao };
}
