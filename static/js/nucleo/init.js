// static/js/nucleo/init.js - Nucleo compartilhado: carga inicial (fim do antigo app.js e do antigo vida.js) - roda DEPOIS de todas as secoes.
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 4292-4349, vida.js 1802-1845.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/static/service-worker.js");
  initPush();
}

if (typeof FilaOffline !== "undefined") {
  // Mostra o indicador se ja existia algo pendente de uma sessao offline
  // anterior (app fechado/pagina recarregada antes de sincronizar), e
  // tenta sincronizar de cara caso a rede ja tenha voltado nesse meio tempo.
  FilaOffline.contar().then(atualizarIndicadorOffline);
  FilaOffline.sincronizar(atualizarIndicadorOffline);
  // evento "online" + poll de reforco (o poll e quem realmente cobre o iOS,
  // onde o evento "online" de um PWA no Safari nao e confiavel).
  FilaOffline.iniciarAutoSync(atualizarIndicadorOffline);
}

$("#logout-btn").addEventListener("click", async () => {
  // Sempre navega pro login, mesmo se a chamada falhar (rede fora do ar etc) -
  // o objetivo e sair da tela autenticada, nao garantir que o servidor confirmou.
  try {
    await fetch("/logout", { method: "POST" });
  } catch {
    // ignora - segue pro login de qualquer jeito
  }
  window.location.href = "/login";
});

mostrarSaudacao();
loadSummary();
loadUso();
loadStreak();
loadClimaHoje();
loadUberPendentes();
loadAgenda();
loadFechamentoDoDia();
loadMemorias();
loadLembretes();
loadMedicamentos();
loadMedidas();
loadEsperas();
loadSaude();
loadChatHistorico();
initViagemOrigemPadrao();
initVozChat();
initDicas();
initSilencio();
initModoViagem();
initModoVisitante();
initBackup();

document.addEventListener("modo-visitante-mudou", () => {
  loadExpenses();
  loadSaude();
  loadMedidas();
  loadPreviaNoite();
  loadDecisoes();
  loadBancos();
});
// ---- Carga inicial + recarga ao trocar de aba ----

function loadVidaHoje() {
  loadSobrecarga();
  loadPreviaNoite();
  loadRotina();
  loadCheckin();
  loadEssencial();
  loadHiperfoco();
}

function loadVidaAba() {
  loadHabitos();
  loadProjetos();
  loadEventosCriados();
  loadResponder();
  loadCompras();
  loadPessoas();
  loadTreino();
  loadContasPessoais();
  loadAssinaturasRevisao();
  loadManutencoes();
  loadGarantias();
  loadViagens();
  loadLugares();
  loadIdeiasPresente();
  loadAprender();
  loadSalvos();
  loadProgresso();
}

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.dataset.tab === "hoje") loadVidaHoje();
    if (btn.dataset.tab === "vida") loadVidaAba();
    if (btn.dataset.tab === "gastos") loadFimMes();
  });
});

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") loadVidaHoje();
});

loadVidaHoje();
