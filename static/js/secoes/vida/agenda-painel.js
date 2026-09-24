// static/js/secoes/vida/agenda-painel.js - Secao vida > agenda-painel (HTML: templates/secoes/vida/agenda-painel.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 869-904.
// Fase 7 (V3-organizacao): botao "Criar evento" abre o formulario num bottom-sheet
// (contrato: docs/agentes/fase7-visual.md). Usa window.abrirBottomSheet/fecharBottomSheet
// (faixa V0d) quando existir; fallback so alterna o atributo hidden do painel.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

function abrirPainelEvento() {
  const sheet = $("#evento-sheet");
  if (typeof window.abrirBottomSheet === "function") window.abrirBottomSheet(sheet);
  else sheet.hidden = false;
}

function fecharPainelEvento() {
  const sheet = $("#evento-sheet");
  if (typeof window.fecharBottomSheet === "function") window.fecharBottomSheet(sheet);
  else sheet.hidden = true;
}

$("#evento-abrir-btn").addEventListener("click", abrirPainelEvento);
$("#evento-cancelar-btn").addEventListener("click", () => {
  $("#evento-form").reset();
  fecharPainelEvento();
});

async function loadEventosCriados() {
  const eventos = await apiFetch("/api/agenda/eventos-criados");
  if (!eventos) return;
  const lista = $("#lista-eventos-criados");
  lista.innerHTML = "";
  $("#eventos-criados-vazio").hidden = eventos.length > 0;
  eventos.forEach((e) => {
    const li = itemSimples(e.titulo, [`${fmtDataBr(e.inicio.slice(0, 10))} ${e.inicio.slice(11, 16)}-${e.fim.slice(11, 16)}`], [
      (el) => botaoApagar(`/api/agenda/eventos/${e.uid}`, el),
    ]);
    li.classList.add("lista-item");
    li.querySelectorAll(".item-quando").forEach((el) => el.classList.add("chip", "chip--compacto"));
    lista.appendChild(li);
  });
}

ligarForm(
  "#evento-form",
  "#evento-btn",
  "Criar evento",
  () => {
    const titulo = $("#evento-titulo").value.trim();
    const data = $("#evento-data").value;
    const hora_inicio = $("#evento-hora-inicio").value;
    const hora_fim = $("#evento-hora-fim").value;
    if (!titulo || !data || !hora_inicio || !hora_fim) return null;
    const corpo = { titulo, data, hora_inicio, hora_fim };
    const lembrar = $("#evento-lembrar").value;
    if (lembrar !== "") corpo.lembrar_min_antes = Number(lembrar);
    return corpo;
  },
  "/api/agenda/eventos",
  () => {
    fecharPainelEvento();
    loadEventosCriados();
  }
);

// ---- Fase 2: treino ----
