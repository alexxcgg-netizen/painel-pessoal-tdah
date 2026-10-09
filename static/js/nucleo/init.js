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
// R2: Início (hero, "Agora", números, atalhos) - uma ida a /api/inicio, sem IA. Marca o
// cache curto de navegacao.js pra não buscar de novo no 1º "aba:aberta" do Início.
if (typeof loadInicio === "function") {
  abaPrecisaCarregar("inicio");
  loadInicio();
}
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
initConversaVoz();
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

// M1 (uso): saudacao/sobrecarga/previa-noite/rotina/checkin mudaram de
// aba Hoje pra Painel (Hoje ficou so com chat, foco atual e agenda do dia)
// - o load desse grupo agora acompanha a aba Painel, nao mais a Hoje.
// showTab("painel") em navegacao.js ja recarrega esse grupo a cada troca
// pra aba; aqui so cobre a carga inicial da pagina e o retorno de
// segundo plano (visibilitychange), igual antes.
function loadPainelVidaMovida() {
  loadSobrecarga();
  loadPreviaNoite();
  loadRotina();
  loadCheckin();
}

function loadVidaHoje() {
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

// R1: era um listener no clique de cada .tab-btn - Vida saiu da barra (abre pelo Mais),
// entao a carga passou a ouvir o evento "aba:aberta" que showTab() dispara no fim da troca
// (mesma ordem de antes: depois da troca; vale pra qualquer caminho de abertura).
document.addEventListener("aba:aberta", (ev) => {
  const aba = ev.detail && ev.detail.aba;
  {
    if (aba === "hoje") {
      loadVidaHoje();
      // R2: depois do frame da revelação (mesmo padrão de Gastos/Vida) e com o cache curto.
      if (typeof loadInicio === "function") {
        requestAnimationFrame(() =>
          setTimeout(() => {
            if (abaPrecisaCarregar("inicio")) loadInicio();
          }, 0)
        );
      }
    }
    // Vel (vel3): as 17 cargas de Vida rodavam SINCRONAS dentro do clique
    // (~38ms medidos com CPU 4x antes do 1o paint da aba) - agora vao pra
    // depois do frame da revelacao (mesmo padrao de Gastos) e respeitam o
    // cache curto de navegacao.js (abaPrecisaCarregar).
    if (aba === "vida") {
      requestAnimationFrame(() =>
        setTimeout(() => {
          if (abaPrecisaCarregar("vida")) loadVidaAba();
        }, 0)
      );
    }
    // Vel (A2d): mesmo motivo do navegacao.js - nao competir com o primeiro
    // paint da revelacao da aba gastos.
    if (aba === "gastos") {
      requestAnimationFrame(() =>
        setTimeout(() => {
          if (abaPrecisaCarregar("gastos-fim-mes")) loadFimMes();
        }, 0)
      );
    }
  }
});

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    loadVidaHoje();
    loadPainelVidaMovida();
    // R2: o Início é a tela que volta aberta do segundo plano - saudação e números frescos.
    if (typeof loadInicio === "function" && abaAtual === "hoje") loadInicio();
  }
});

loadVidaHoje();
loadPainelVidaMovida();
