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

// Vel (vel3): cache curto de "esta aba ja carregou". Cada troca de aba
// re-disparava TODOS os GET /api dela (13 em Gastos, 17 em Vida, ~18 em
// Painel) e re-renderizava tudo, mesmo se nada mudou desde a ultima visita -
// trabalho de rede + JS + layout que competia com o toque seguinte. Agora a
// aba so recarrega se: passaram mais de TTL_DADOS_ABA_MS desde a ultima carga,
// OU algo foi escrito/falhou desde entao (apiFetch chama invalidarDadosAbas()
// em POST/PUT/PATCH/DELETE e em qualquer erro), OU o app voltou do segundo
// plano / a rede voltou (dado pode ter mudado por outro lado: Telegram,
// outro aparelho). A primeira visita sempre carrega.
const TTL_DADOS_ABA_MS = 30000;
const _dadosAbaCarregadosEm = {};
let _versaoDadosAbas = 0;

function invalidarDadosAbas() {
  _versaoDadosAbas++;
}

function abaPrecisaCarregar(chave) {
  const agora = Date.now();
  const anterior = _dadosAbaCarregadosEm[chave];
  const idade = anterior ? agora - anterior.em : -1;
  // idade < 0 = relogio voltou atras: nao confia, recarrega
  if (anterior && anterior.versao === _versaoDadosAbas && idade >= 0 && idade < TTL_DADOS_ABA_MS) {
    return false;
  }
  _dadosAbaCarregadosEm[chave] = { em: agora, versao: _versaoDadosAbas };
  return true;
}

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") invalidarDadosAbas();
});
window.addEventListener("online", invalidarDadosAbas);

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
    }
    document.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.tab === name);
    });
  });
  // Vis (C2) + Vel (medir_velocidade.py "resultado visivel" = ate #tab-X sem
  // hidden): a aba precisa aparecer PRIMEIRO - a marcacao escalonada (30ms, 8
  // primeiros, SO na 1a abertura de Painel/Vida nesta sessao) nunca entra na
  // MESMA tarefa sincrona que tira o hidden (linhas acima), senao o trabalho
  // de marcar os cards atrasa exatamente o "resultado visivel" medido. Um
  // rAF aqui roda no MESMO frame, ANTES do proximo paint (nao um frame
  // depois) - por isso nao ha "flash": e a 1a vez que esses cards pintam
  // (estavam dentro da aba escondida), a classe c2-entra ja chega antes
  // desse 1o paint. marcarEntradaEscalonada (movimento.js) so mede/marca
  // quem esta dentro da viewport, no maximo 8 - nunca percorre/mede a lista
  // inteira. Deliberadamente NAO em Tarefas (deixa test_vel_a2b_otimista
  // instavel - achado da faixa anterior).
  if (elNovo && typeof marcarEntradaEscalonada === "function" && (name === "painel" || name === "vida")) {
    requestAnimationFrame(() => {
      if (name === "painel") marcarEntradaEscalonada(elNovo);
      else marcarEntradaEscalonada(elNovo.querySelector(".vida-secoes"));
    });
  }
  if (name === "painel" && abaPrecisaCarregar("painel")) {
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
  if (name === "tarefas" && abaPrecisaCarregar("tarefas")) loadTasks();
  if (name === "gastos" && abaPrecisaCarregar("gastos")) {
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
        // Limpa (D): loadExpenses() ja chama loadExtratoFinancas() por dentro
        // (gastos.js) - chamar de novo aqui duplicava o GET /api/financas/extrato
        // a cada troca pra aba Gastos.
        loadExpenses();
        loadMetas();
        loadBancos();
        if (typeof loadResumoFinancas === "function") loadResumoFinancas();
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
