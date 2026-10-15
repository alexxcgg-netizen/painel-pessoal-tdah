// static/js/nucleo/init.js - Nucleo compartilhado: carga inicial (fim do antigo app.js e do antigo vida.js) - roda DEPOIS de todas as secoes.
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 4292-4349, vida.js 1802-1845.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

if ("serviceWorker" in navigator) {
  // da RAIZ, com alcance "/": so assim ele controla a pagina e o iPhone libera notificacao.
  // O registro antigo (de /static/, que nunca controlou nada) e removido.
  navigator.serviceWorker.register("/service-worker.js", { scope: "/" });
  navigator.serviceWorker.getRegistrations
    && navigator.serviceWorker.getRegistrations().then((regs) =>
      regs.filter((r) => /\/static\/$/.test(r.scope)).forEach((r) => r.unregister())
    );
}
initPush();

// Toque numa notificacao: "/?aba=tarefas" abre direto na aba do aviso.
function abrirAbaDoAviso(url) {
  let aba = null;
  try {
    aba = new URL(url, location.origin).searchParams.get("aba");
  } catch {
    return;
  }
  if (aba && /^[a-z-]+$/.test(aba) && document.getElementById(`tab-${aba}`)) showTab(aba);
  // aviso de uma tarefa (2026-10-13): abre a propria tarefa, com concluir / pra amanha a mao
  let tarefa = null;
  try {
    tarefa = new URL(url, location.origin).searchParams.get("tarefa");
  } catch {
    tarefa = null;
  }
  if (aba === "tarefas" && tarefa && /^\d+$/.test(tarefa) && typeof focarTarefaDoAviso === "function") {
    focarTarefaDoAviso(tarefa);
  }
}
if (new URLSearchParams(location.search).has("aba")) {
  const urlAviso = location.href;
  history.replaceState(null, "", location.pathname); // recarregar nao volta pra aba do aviso
  requestAnimationFrame(() => abrirAbaDoAviso(urlAviso));
}
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.addEventListener("message", (ev) => {
    if (ev.data && ev.data.tipo === "abrir-aviso") abrirAbaDoAviso(ev.data.url);
  });
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
if (typeof iniciarLocalizacao === "function") iniciarLocalizacao();
initDicas();
initSilencio();
initModoViagem();
initModoVisitante();
initBackup();
initWidgetIphone();

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

// iPhone (app na tela inicial): sair com o teclado aberto e voltar deixava o iOS com a medida
// da tela de quando o teclado estava aberto - o campo do chat, a nota e a barra de abas (tudo
// position: fixed no fundo) ficavam pendurados no meio da tela ate a proxima rolagem. Fecha o
// teclado antes de sair e, na volta (e quando o teclado recolhe), forca o iOS a medir de novo
// com um vai-e-volta de 1px na rolagem - no mesmo frame, nao aparece na tela.
const _CAMPO_DE_TECLADO = "input, textarea, select, [contenteditable]";

function _realinharTela() {
  const y = window.scrollY;
  window.scrollTo(window.scrollX, y > 0 ? y - 1 : y + 1);
  window.scrollTo(window.scrollX, y);
}

function _realinharDepoisDoTeclado() {
  requestAnimationFrame(_realinharTela);
  setTimeout(_realinharTela, 350); // o teclado do iOS leva ~300 ms pra recolher
}

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    const ativo = document.activeElement;
    if (ativo && ativo.matches && ativo.matches(_CAMPO_DE_TECLADO)) ativo.blur();
  } else {
    _realinharDepoisDoTeclado();
  }
});
window.addEventListener("pageshow", _realinharDepoisDoTeclado);
if (window.visualViewport) {
  let _alturaVisivel = window.visualViewport.height;
  window.visualViewport.addEventListener("resize", () => {
    const altura = window.visualViewport.height;
    const ativo = document.activeElement;
    const digitando = ativo && ativo.matches && ativo.matches(_CAMPO_DE_TECLADO);
    // cresceu bastante = o teclado recolheu
    if (altura > _alturaVisivel + 80 && !digitando) _realinharDepoisDoTeclado();
    _alturaVisivel = altura;
  });
}

// 2a camada (2026-10-14 - o vai-e-volta acima nao bastou: print do Alex na tela IA com o campo
// e a barra de abas no meio da tela, o card continuando por baixo). O iOS pode deixar o fundo
// da tela VISIVEL (visualViewport) mais baixo que o fundo onde o position:fixed se ancora
// (layout) depois que o teclado some. Mede essa diferenca e desce as pecas fixas do fundo
// exatamente esse tanto (--vv-desvio, usado por #tabbar/#chat-form/.chat-nota). Sem campo em
// foco e sem zoom; tudo certo = 0 e nada muda.
// 3a camada (2026-10-14, print do Alex com a barra cortada pela metade): no app da tela de
// inicio o fundo visivel fica SEMPRE ~34pt (faixa da barrinha do iPhone) abaixo do fundo do
// layout - isso e o normal dele, nao o bug.
// 4a camada (2026-10-15, "ainda aparece pela metade"): a 3a usava o MENOR desvio ja visto como
// normal - se a 1a medida saia 0 e depois vinha a folga, a barra descia.
// 5a camada (2026-10-15, medida real do iPhone dele em /api/diagnostico, iOS 18.7 no app da tela de
// inicio): clientHeight = 894 mas a barra position:fixed fica presa em 956 (= innerHeight); os
// 62px de diferenca sao a faixa do relogio la em cima, nao bug - e a conta "fundo visivel -
// clientHeight" descia a barra 62px pra fora da tela. clientHeight nao e onde o fixed se ancora.
// Agora mede o ancoradouro DE VERDADE: uma sonda invisivel position:fixed; bottom:0 - o topo dela
// e exatamente onde o fundo das pecas fixas fica. Sem chute de base: so desce quando o fundo
// visivel passa do ancoradouro em >= 48px (o teclado preso, que e centenas de px).
const _DESVIO_MINIMO_BUG = 48; // folga pequena nunca mexe; o bug do teclado preso e bem maior
let _ultimoDesvio = { bruto: 0, aplicado: 0, ancora: null };
let _sondaFundo = null;
function _ancoraDoFixo() {
  if (!document.body) return null;
  if (!_sondaFundo || !_sondaFundo.isConnected) {
    _sondaFundo = document.createElement("div");
    _sondaFundo.setAttribute("aria-hidden", "true");
    _sondaFundo.style.cssText = "position:fixed;left:0;bottom:0;width:0;height:0;visibility:hidden;pointer-events:none";
    document.body.appendChild(_sondaFundo);
  }
  return _sondaFundo.getBoundingClientRect().top;
}
function _medirDesvioTela() {
  const vv = window.visualViewport;
  if (!vv) return;
  const ativo = document.activeElement;
  const digitando = ativo && ativo.matches && ativo.matches(_CAMPO_DE_TECLADO);
  const fundoVisivel = vv.offsetTop + vv.height;
  const ancora = _ancoraDoFixo();
  let desvio = 0;
  let bruto = 0;
  if (ancora !== null && !digitando && vv.scale <= 1.01) {
    bruto = Math.max(0, Math.round(fundoVisivel - ancora));
    desvio = bruto >= _DESVIO_MINIMO_BUG ? bruto : 0;
  }
  _ultimoDesvio = { bruto, aplicado: desvio, ancora: ancora === null ? null : Math.round(ancora) };
  document.documentElement.style.setProperty("--vv-desvio", `${desvio}px`);
  if (desvio) _retratoTela("desvio");
}
window.addEventListener("orientationchange", () => setTimeout(_medirDesvioTela, 400));

// Retrato da tela pro diagnostico (rotas/diagnostico.py): so no iPhone/iPad, onde o bug mora.
// Onde a barra de abas esta de verdade x o que o iOS diz da tela - se ela voltar a aparecer pela
// metade, o numero ja esta la em vez de chute.
const _EH_IOS = /iPhone|iPad|iPod/.test(navigator.userAgent || "");
function _retratoTela(motivo) {
  if (!_EH_IOS || typeof enviarDiagnostico !== "function") return;
  try {
    const vv = window.visualViewport;
    const barra = document.getElementById("tabbar");
    const r = barra ? barra.getBoundingClientRect() : null;
    const ios = /OS (\d+)_(\d+)/.exec(navigator.userAgent || "");
    const sonda = document.createElement("div");
    sonda.style.cssText = "position:fixed;left:0;top:0;width:0;padding-bottom:env(safe-area-inset-bottom);padding-top:env(safe-area-inset-top);visibility:hidden;pointer-events:none";
    document.body.appendChild(sonda);
    const cs = getComputedStyle(sonda);
    const seguraBaixo = parseFloat(cs.paddingBottom) || 0;
    const seguraTopo = parseFloat(cs.paddingTop) || 0;
    sonda.remove();
    enviarDiagnostico("tela", {
      motivo,
      ios: ios ? `${ios[1]}.${ios[2]}` : "?",
      app: window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true,
      innerH: window.innerHeight,
      outerH: window.outerHeight,
      telaH: window.screen ? window.screen.height : null,
      clientH: document.documentElement.clientHeight,
      vvH: vv ? Math.round(vv.height * 10) / 10 : null,
      vvTopo: vv ? Math.round(vv.offsetTop * 10) / 10 : null,
      vvEscala: vv ? Math.round(vv.scale * 100) / 100 : null,
      seguraBaixo,
      seguraTopo,
      bruto: _ultimoDesvio.bruto,
      aplicado: _ultimoDesvio.aplicado,
      ancora: _ultimoDesvio.ancora,
      barraTopo: r ? Math.round(r.top) : null,
      barraFundo: r ? Math.round(r.bottom) : null,
      barraAltura: r ? Math.round(r.height) : null,
      aba: (document.querySelector(".tab-btn.active") || {}).dataset?.tab || null,
    }, motivo === "abriu");
  } catch {}
}
if (window.visualViewport) {
  window.visualViewport.addEventListener("resize", _medirDesvioTela);
  window.visualViewport.addEventListener("scroll", _medirDesvioTela);
  window.addEventListener("pageshow", _medirDesvioTela);
  document.addEventListener("focusout", () => setTimeout(_medirDesvioTela, 350));
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) return;
    // o iOS termina de se arrumar em tempos diferentes na volta: mede algumas vezes
    [0, 350, 900].forEach((ms) => setTimeout(_medirDesvioTela, ms));
    setTimeout(() => _retratoTela("voltou"), 1000);
  });
  _medirDesvioTela();
  setTimeout(() => _retratoTela("abriu"), 1500);
}

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
