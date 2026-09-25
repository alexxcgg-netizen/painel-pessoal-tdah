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
  abaAtual = name;

  document.querySelectorAll(".tab-content").forEach((el) => {
    el.classList.remove("entra-direita", "entra-esquerda");
    el.hidden = el.id !== `tab-${name}`;
  });
  if (direcao) {
    document.getElementById(`tab-${name}`).classList.add(direcao);
  }
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === name);
  });
  if (name === "painel") {
    loadSobrecarga();
    loadPreviaNoite();
    loadRotina();
    loadCheckin();
    loadSummary();
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
  }
  if (name === "tarefas") loadTasks();
  if (name === "gastos") {
    loadExpenses();
    loadMetas();
    loadBancos();
    if (typeof loadResumoFinancas === "function") loadResumoFinancas();
    if (typeof loadExtratoFinancas === "function") loadExtratoFinancas();
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
