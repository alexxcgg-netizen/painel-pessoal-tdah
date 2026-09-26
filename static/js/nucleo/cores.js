// static/js/nucleo/cores.js - Nucleo compartilhado: cor fixa por categoria de gasto
// (paleta "Gelo preto", faixa vis/C1). Script classico (escopo global compartilhado) -
// a ordem de carga esta em templates/scripts.html.
//
// Tabela fixa pras categorias conhecidas (mesma categoria sempre a mesma cor, mesmo se
// a lista de categorias do backend mudar de ordem); qualquer categoria fora da tabela
// cai num hash estavel do nome nas mesmas 8 cores (--cor-cat-1..8, static/css/ui/tokens.css).
const CATEGORIAS_COR_FIXA = {
  mercado: 1,
  transporte: 2,
  alimentacao: 3,
  farmacia: 4,
  saude: 5,
  compras: 6,
  "compras online": 7,
  servicos: 8,
  "servicos digitais": 1,
  streaming: 2,
  combustivel: 3,
  telecomunicacoes: 4,
  eletronicos: 5,
  "academia e bem-estar": 6,
  viagem: 7,
  hospedagem: 8,
  impostos: 1,
  educacao: 2,
  lazer: 3,
  contas: 4,
  outros: 5,
};

// Remove acento/caixa pra "Alimentação"/"ALIMENTAÇÃO" casarem com a chave "alimentacao".
function _normalizarNomeCategoria(nome) {
  return String(nome || "")
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");
}

// Hash simples e estavel (mesma string sempre o mesmo numero, sem Math.random em
// nenhum ponto) pra categoria que nao esta na tabela fixa acima.
function _hashCategoria(nome) {
  let h = 0;
  for (let i = 0; i < nome.length; i++) {
    h = (h * 31 + nome.charCodeAt(i)) >>> 0;
  }
  return (h % 8) + 1;
}

// corDaCategoria("Mercado") -> "var(--cor-cat-1)". Mesma categoria sempre a mesma cor
// (conhecida = tabela fixa; desconhecida = hash do nome, tambem estavel).
function corDaCategoria(nome) {
  const chave = _normalizarNomeCategoria(nome);
  const indice = CATEGORIAS_COR_FIXA[chave] || _hashCategoria(chave || "outros");
  return `var(--cor-cat-${indice})`;
}
