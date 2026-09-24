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

  const dicaSono = $("#dica-sono");
  dicaSono.hidden = !data.dica_sono;
  dicaSono.textContent = data.dica_sono || "";
  const dicaHumor = $("#dica-humor");
  dicaHumor.hidden = !data.dica_humor;
  dicaHumor.textContent = data.dica_humor || "";

  if (!temAlgumDado) return;

  $("#saude-passos").textContent = dados.passos != null ? dados.passos.toLocaleString("pt-BR") : "-";
  $("#saude-distancia").textContent = dados.distancia_km != null ? dados.distancia_km.toFixed(1) : "-";
  $("#saude-sono").textContent = dados.sono_horas != null ? dados.sono_horas.toFixed(1) : "-";
}

// Fase 6 US-F1: feedback forte ao toque no botao de agua - "+1" flutuante
// que sobe e some sozinho (por animationend, com timeout de seguranca pra
// nunca ficar preso na tela em navegador sem o evento/com reduced-motion).
function celebrarHidratacao(btn) {
  btn.classList.remove("tocando");
  void btn.offsetWidth; // forca reflow pra animacao reiniciar em cliques seguidos
  btn.classList.add("tocando");
  vibrar(15);
  const flutuante = document.createElement("span");
  flutuante.className = "hidratacao-flutuante";
  flutuante.textContent = "+1";
  flutuante.setAttribute("aria-hidden", "true");
  btn.appendChild(flutuante);
  const limpar = () => flutuante.remove();
  flutuante.addEventListener("animationend", limpar, { once: true });
  setTimeout(limpar, 1200);
}

$("#hidratacao-btn").addEventListener("click", async () => {
  const btn = $("#hidratacao-btn");
  btn.disabled = true;
  const data = await apiFetch("/api/hidratacao", { method: "POST" });
  btn.disabled = false;
  if (!data) return;
  $("#hidratacao-total").textContent = data.total_hoje;
  pulsarSucesso($("#hidratacao-total"));
  celebrarHidratacao(btn);
});
