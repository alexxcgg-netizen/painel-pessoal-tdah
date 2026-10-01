// static/js/nucleo/navegacao.js - Nucleo compartilhado: ORDEM_ABAS, showTab() e o clique nos botoes da barra de abas.
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 241-296.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

// Ordem das abas na barra - usada so pra saber se a troca "avança" ou
// "volta" e entrar do lado certo (slide pra direita indo pra frente, pra
// esquerda voltando) - o mesmo tipo de pista de direcao que apps premium
// usam em transicao de aba, em vez de um fade generico igual pra qualquer
// troca.
// R1 (reformulação): a barra tem 5 itens (Início, Tarefas, IA, Finanças, Mais). As telas
// que saíram da barra (TELAS_DO_MAIS) continuam existindo com os mesmos ids/loaders e abrem
// pela tela Mais: com uma delas aberta o item "Mais" fica ativo e o cabeçalho da tela tem
// o "‹" que volta pra Mais. Na direção da animação elas contam como "depois do Mais"
// (abrir = avança; voltar pra Mais = volta).
const ORDEM_ABAS = ["hoje", "tarefas", "assistente", "gastos", "mais"];
const TELAS_DO_MAIS = ["painel", "vida", "aviacao", "construtora", "ajustes-ia", "config"];
// Telas onde o botão "+" (captura, secoes/topo/captura.html) aparece.
const TELAS_COM_FAB = ["hoje", "tarefas", "gastos"];
let abaAtual = "hoje";

function itemDaBarra(name) {
  return TELAS_DO_MAIS.includes(name) ? "mais" : name;
}

function posicaoDaAba(name) {
  const i = ORDEM_ABAS.indexOf(name);
  if (i >= 0) return i * 100;
  const j = TELAS_DO_MAIS.indexOf(name);
  return j >= 0 ? ORDEM_ABAS.indexOf("mais") * 100 + 1 + j : -1;
}

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
  const indiceAtual = posicaoDaAba(abaAtual);
  const indiceNovo = posicaoDaAba(name);
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
    const item = itemDaBarra(name);
    document.querySelectorAll(".tab-btn").forEach((btn) => {
      const ativo = btn.dataset.tab === item;
      btn.classList.toggle("active", ativo);
      if (ativo) btn.setAttribute("aria-current", "page");
      else btn.removeAttribute("aria-current");
    });
    const fab = document.getElementById("fab-captura");
    if (fab) fab.hidden = !TELAS_COM_FAB.includes(name);
  });
  // R1: a folha do "+" fecha se algo trocar de tela com ela aberta (ex.: comando de voz
  // "abre a aba vida").
  const folha = document.getElementById("folha-captura");
  if (folha && !folha.hidden && typeof fecharBottomSheet === "function") fecharBottomSheet(folha);
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
  // R1: aviso de "tela aberta" pra quem carrega dados ao abrir uma tela que não tem mais
  // botão na barra (Vida em init.js; caixa/regras/avisos em ajustes-ia). Antes eles
  // ouviam o clique do .tab-btn da própria aba; agora vale pra qualquer caminho (barra,
  // Mais, link de card, comando de voz). Síncrono, no fim da troca - mesma ordem de antes.
  document.dispatchEvent(new CustomEvent("aba:aberta", { detail: { aba: name } }));
}

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => showTab(btn.dataset.tab));
});

// ---- R1: tela Mais, cabeçalho por tela ("‹" e ação) ----

// Abre uma tela vinda do Mais (ou da ação de um cabeçalho). `alvo` (opcional) é um seletor
// CSS dentro da tela: rola até ele e, se estiver numa .secao-recolhivel fechada, abre.
function abrirPeloMais(aba, alvo) {
  // Volta pro topo ANTES de revelar a tela nova: com a tela de saída ainda montada o
  // scroll não força layout da tela que entra dentro do toque (medido: rolar depois do
  // showTab punha ~30 ms de layout síncrono no INP do toque).
  if (!alvo) window.scrollTo({ top: 0, behavior: "instant" });
  showTab(aba);
  if (!alvo) return;
  // Depois do frame da revelação (a tela acabou de sair do hidden).
  requestAnimationFrame(() => {
    const tela = document.getElementById(`tab-${aba}`);
    const el = tela && tela.querySelector(alvo);
    if (!el) return;
    const secao = el.closest(".secao-recolhivel") || (el.matches(".secao-recolhivel") ? el : null);
    if (secao && secao.dataset.aberto === "false") {
      const cab = secao.querySelector(".secao-cabecalho");
      if (cab) cab.click();
    }
    const bloco = el.closest(".card, .secao-recolhivel") || el;
    const reduzir = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const topo = bloco.getBoundingClientRect().top + window.scrollY - 12;
    window.scrollTo({ top: Math.max(0, topo), behavior: reduzir ? "instant" : "smooth" });
  });
}

document.addEventListener("click", (ev) => {
  const voltar = ev.target.closest(".cab-tela-voltar");
  if (voltar) {
    window.scrollTo({ top: 0, behavior: "instant" });
    showTab(voltar.dataset.voltaPara || "mais");
    return;
  }
  const abre = ev.target.closest("[data-abre-tela]");
  if (abre) abrirPeloMais(abre.dataset.abreTela, abre.dataset.alvo || null);
});

// Subtítulo do Início: data de hoje por extenso ("quinta, 1 de outubro").
(function preencherDataDoInicio() {
  const el = document.getElementById("cab-inicio-data");
  if (!el) return;
  try {
    const txt = new Date().toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });
    el.textContent = txt.charAt(0).toUpperCase() + txt.slice(1);
  } catch (e) {
    /* mantém "Hoje" do HTML */
  }
})();
