// static/js/nucleo/navegacao.js - Nucleo compartilhado: ORDEM_ABAS, showTab() e o clique nos botoes da barra de abas.
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 241-296.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

// Ordem das abas na barra - usada so pra saber se a troca "avança" ou
// "volta" e entrar do lado certo (slide pra direita indo pra frente, pra
// esquerda voltando) - o mesmo tipo de pista de direcao que apps premium
// usam em transicao de aba, em vez de um fade generico igual pra qualquer
// troca.
const ORDEM_ABAS = ["hoje", "tarefas", "gastos", "vida"];
let abaAtual = "hoje";

// Fase 9 (C-nav): a barra caiu de 8 pra 4 abas - painel/assistente foram
// absorvidas por "hoje" (e parte por "vida"), construtora por "gastos" e
// aviacao por "vida". Nomes antigos continuam reconhecidos aqui (voz, links
// de card, atalhos internos) e so redirecionam pro destino novo - ninguem
// mais precisa saber que a aba antiga sumiu. Ver contrato em
// docs/fase9-mapa-abas.md (NAVEGACAO E CONTROLE).
const REDIRECIONA_ABA = { painel: "hoje", assistente: "hoje", construtora: "gastos", aviacao: "vida" };
// Aba antiga -> id da secao pra rolar ate depois que a aba destino abrir
// (o conteudo mudou de aba mas continua endereçavel por esse id, contrato
// combinado com C-abas: #secao-construtora dentro de gastos, #secao-aviacao
// dentro de vida).
const ROLAR_ATE_SECAO = { construtora: "secao-construtora", aviacao: "secao-aviacao" };

function showTab(name) {
  const nomeOriginal = name;
  if (Object.prototype.hasOwnProperty.call(REDIRECIONA_ABA, name)) {
    name = REDIRECIONA_ABA[name];
  }
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
  if (name === "hoje") {
    // Resumo/agenda/plano do dia/devo sair/fechamento - o que a antiga aba
    // "painel" carregava pra essas secoes, que agora moraram em "hoje"
    // (contrato Fase 9 C-nav, docs/fase9-mapa-abas.md).
    loadSummary();
    loadAgenda();
    loadFechamentoDoDia();
    loadLembretes();
  }
  if (name === "tarefas") loadTasks();
  if (name === "gastos") {
    loadExpenses();
    loadMetas();
    loadBancos();
    if (typeof loadResumoFinancas === "function") loadResumoFinancas();
    if (typeof loadExtratoFinancas === "function") loadExtratoFinancas();
    // Secao "Construtora" (antiga aba "construtora") agora vive no fim da
    // aba Financas (#secao-construtora, template a cargo da faixa C-abas).
    loadConstrutora();
    loadCotacoes();
  }
  if (name === "vida") {
    // Saude/medicamentos/peso/datas/memoria/notas/diario de decisao/brain
    // dump/esperando resposta - o que a antiga aba "painel" carregava pra
    // essas secoes, que agora moraram em "vida".
    loadSaude();
    loadMemorias();
    loadMedicamentos();
    loadMedidas();
    loadEsperas();
    loadNotas();
    loadDecisoes();
    loadBrainDump();
    // Bloco "Aviacao" (antiga aba "aviacao") agora vive no topo da aba Vida
    // (#secao-aviacao, template a cargo da faixa C-abas).
    loadVoosResumo();
  }
  if (Object.prototype.hasOwnProperty.call(ROLAR_ATE_SECAO, nomeOriginal)) {
    const idSecao = ROLAR_ATE_SECAO[nomeOriginal];
    // A secao so existe depois que o template/conteudo da aba destino
    // termina de renderizar (loads acima sao assincronos) - tenta por um
    // tempinho em vez de assumir que o elemento ja esta no DOM neste frame.
    let tentativas = 0;
    const rolarQuandoExistir = () => {
      const alvo = document.getElementById(idSecao);
      if (alvo) {
        alvo.scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }
      tentativas += 1;
      if (tentativas < 20) setTimeout(rolarQuandoExistir, 100);
    };
    rolarQuandoExistir();
  }
}

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => showTab(btn.dataset.tab));
});
