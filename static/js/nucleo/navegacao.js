// static/js/nucleo/navegacao.js - Nucleo compartilhado: ORDEM_ABAS, showTab() e o clique nos botoes da barra de abas.
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 241-296.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

// Ordem das abas na barra - usada so pra saber se a troca "avança" ou
// "volta" e entrar do lado certo (slide pra direita indo pra frente, pra
// esquerda voltando) - o mesmo tipo de pista de direcao que apps premium
// usam em transicao de aba, em vez de um fade generico igual pra qualquer
// troca.
const ORDEM_ABAS = ["hoje", "painel", "aviacao", "vida", "tarefas", "gastos", "construtora", "assistente"];
let abaAtual = "hoje";

function showTab(name) {
  const indiceAtual = ORDEM_ABAS.indexOf(abaAtual);
  const indiceNovo = ORDEM_ABAS.indexOf(name);
  const direcao =
    indiceNovo > indiceAtual ? "entra-direita" : indiceNovo < indiceAtual ? "entra-esquerda" : null;

  // Vel (A2c): antes isto rodava sobre TODAS as 8 abas em toda troca (8x
  // classList.remove + 8x escrita de `.hidden`, so pra trocar 2). So a aba
  // que sai e a que entra precisam mudar - menos escrita = menos trabalho de
  // estilo/layout pro navegador considerar a cada troca (medido: troca de
  // aba leve custava ~730ms com CPU 4x, a maior parte em TaskDuration fora
  // de Script/Layout/RecalcStyle explicitos - ver ANALISE_A2C.md).
  const elAnterior = document.getElementById(`tab-${abaAtual}`);
  const elNovo = document.getElementById(`tab-${name}`);
  abaAtual = name;

  // Vis (C2): so a troca de hidden/active entra no View Transition (fn
  // sincrona, do jeito que a API espera) - com suporte nativo o navegador
  // cross-fada + sobe 8px sozinho (::view-transition-*(root), ui/movimento.
  // css); sem suporte, ou reduzir movimento, roda direto e cai no CSS de
  // entra-direita/entra-esquerda/tabEntra que style.css ja tinha (as duas
  // classes continuam existindo so pra isso, hoje as duas viram o mesmo
  // keyframe). Os loads de dados abaixo ficam FORA (sao assincronos, nao
  // fazem parte do "antes/depois" que a VT tira foto).
  const trocarAbaFn = typeof trocarAba === "function" ? trocarAba : (fn) => fn();
  trocarAbaFn(() => {
    if (elAnterior && elAnterior !== elNovo) {
      elAnterior.classList.remove("entra-direita", "entra-esquerda");
      elAnterior.hidden = true;
    }
    if (elNovo) {
      elNovo.classList.remove("entra-direita", "entra-esquerda");
      elNovo.hidden = false;
      if (direcao) elNovo.classList.add(direcao);
      // Vis (C2): cards entrando escalonados (30ms, 8 primeiros) SO na 1a
      // abertura de Painel/Vida nesta sessao de pagina (marcarEntradaEscalonada
      // ja se marca sozinha, nao repete em trocas seguintes) - roda no MESMO
      // tick que revela a aba (hidden=false, linha de cima), antes do proximo
      // paint, senao os cards apareceriam prontos por 1 frame e "pulariam" pra
      // entrada. Deliberadamente NAO em Tarefas (deixa test_vel_a2b_otimista
      // instavel - achado da faixa anterior).
      if (typeof marcarEntradaEscalonada === "function") {
        if (name === "painel") marcarEntradaEscalonada(elNovo);
        else if (name === "vida") marcarEntradaEscalonada(elNovo.querySelector(".vida-secoes"));
      }
    }
    document.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.tab === name);
    });
  });
  if (name === "painel") {
    // Vel (A2c): os 5 primeiros sao os que aparecem sem rolar (mesma ordem
    // de templates/abas/painel.html); o resto (abaixo da dobra) espera um
    // tick (requestAnimationFrame) pra nao competir por CPU com o primeiro
    // paint/animacao da troca de aba - pedido do brief ("os que ficam
    // abaixo da dobra podem esperar requestAnimationFrame/um tick").
    loadSobrecarga();
    loadPreviaNoite();
    loadRotina();
    loadCheckin();
    loadSummary();
    requestAnimationFrame(() => {
      loadAgenda();
      loadFechamentoDoDia();
      loadSaude();
      loadMemorias();
      loadLembretes();
      loadMedicamentos();
      loadMedidas();
      loadEsperas();
      loadNotas();
      loadDecisoes();
      loadBrainDump();
      if (typeof loadCustoIAV2 === "function") loadCustoIAV2();
      if (typeof loadTesteIA === "function") loadTesteIA();
    });
  }
  if (name === "tarefas") loadTasks();
  if (name === "gastos") {
    // Vel (A2d): medido - a aba gastos era a unica com INP MEDIANO alto
    // (~188ms, nao so no pior caso), porque os 5 loads abaixo rodavam na
    // MESMA tarefa que revela a aba (elNovo.hidden = false, algumas linhas
    // acima). O navegador so pinta a revelacao depois que a tarefa toda
    // termina - entao qualquer trabalho aqui, mesmo o pouco JS sincrono de
    // cada função antes do primeiro await, competia com esse primeiro paint.
    // rAF garante que o frame da revelacao ja foi agendado antes de rodar;
    // setTimeout(0) joga pra DEPOIS desse frame (rAF sozinho ainda roda
    // antes do paint). Meta: INP < 100ms.
    requestAnimationFrame(() => {
      setTimeout(() => {
        loadExpenses();
        loadMetas();
        loadBancos();
        if (typeof loadResumoFinancas === "function") loadResumoFinancas();
        if (typeof loadExtratoFinancas === "function") loadExtratoFinancas();
      }, 0);
    });
  }
  if (name === "construtora") {
    loadConstrutora();
    loadCotacoes();
  }
  if (name === "aviacao") loadVoosResumo();
}

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => showTab(btn.dataset.tab));
});
