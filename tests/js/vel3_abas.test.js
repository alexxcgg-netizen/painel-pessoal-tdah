// Vel (vel3): logica nova da troca de aba - cache curto de carga por aba
// (static/js/nucleo/navegacao.js) e ocultar conteudo de secao fechada
// (static/js/nucleo/movimento.js). Sem navegador: node:test + vm.
//
//   node --test tests/js/vel3_abas.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const RAIZ = path.join(__dirname, "..", "..", "static", "js", "nucleo");

// ---- ocultarConteudoFechado (movimento.js exporta via module.exports) --------
const movimento = require(path.join(RAIZ, "movimento.js"));

function elementoFalso() {
  const classes = new Set();
  return {
    classList: {
      add: (c) => classes.add(c),
      remove: (c) => classes.delete(c),
      contains: (c) => classes.has(c),
    },
  };
}

test("ocultarConteudoFechado: estado inicial fechado oculta na hora", () => {
  const el = elementoFalso();
  movimento.ocultarConteudoFechado(el, false, true);
  assert.equal(el.classList.contains("c2-cv-oculto"), true);
});

test("ocultarConteudoFechado: abrir tira a classe na hora", () => {
  const el = elementoFalso();
  movimento.ocultarConteudoFechado(el, false, true);
  movimento.ocultarConteudoFechado(el, true, false);
  assert.equal(el.classList.contains("c2-cv-oculto"), false);
});

test("ocultarConteudoFechado: fechar espera a animacao de altura antes de ocultar", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const el = elementoFalso();
  movimento.ocultarConteudoFechado(el, false, false);
  t.mock.timers.tick(300);
  assert.equal(el.classList.contains("c2-cv-oculto"), false, "ainda animando - conteudo tem que continuar visivel");
  t.mock.timers.tick(200);
  assert.equal(el.classList.contains("c2-cv-oculto"), true);
});

test("ocultarConteudoFechado: reabrir antes do fim cancela a ocultacao pendente", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const el = elementoFalso();
  movimento.ocultarConteudoFechado(el, false, false);
  t.mock.timers.tick(200);
  movimento.ocultarConteudoFechado(el, true, false);
  t.mock.timers.tick(1000);
  assert.equal(el.classList.contains("c2-cv-oculto"), false);
});

test("ocultarConteudoFechado: entradas invalidas nao quebram", () => {
  movimento.ocultarConteudoFechado(null, false, true);
  movimento.ocultarConteudoFechado(undefined, true, false);
  movimento.ocultarConteudoFechado({}, false, false);
});

// ---- cache curto de carga (navegacao.js, script classico -> vm) --------------
function carregarNavegacao() {
  const ouvintes = { document: {}, window: {} };
  let agora = 1_000_000;
  const ctx = vm.createContext({
    document: {
      visibilityState: "visible",
      getElementById: () => null,
      querySelectorAll: () => [],
      addEventListener: (nome, fn) => (ouvintes.document[nome] = fn),
    },
    window: { addEventListener: (nome, fn) => (ouvintes.window[nome] = fn) },
    Date: { now: () => agora },
  });
  vm.runInContext(fs.readFileSync(path.join(RAIZ, "navegacao.js"), "utf8"), ctx);
  const chamar = (expr) => vm.runInContext(expr, ctx);
  return { chamar, ouvintes, avancar: (ms) => (agora += ms) };
}

test("cache de aba: primeira visita carrega, segunda logo depois nao", () => {
  const n = carregarNavegacao();
  assert.equal(n.chamar('abaPrecisaCarregar("tarefas")'), true);
  assert.equal(n.chamar('abaPrecisaCarregar("tarefas")'), false);
  assert.equal(n.chamar('abaPrecisaCarregar("gastos")'), true, "cada aba tem a propria chave");
});

test("cache de aba: passou o TTL, recarrega", () => {
  const n = carregarNavegacao();
  n.chamar('abaPrecisaCarregar("tarefas")');
  n.avancar(29_000);
  assert.equal(n.chamar('abaPrecisaCarregar("tarefas")'), false);
  n.avancar(2_000);
  assert.equal(n.chamar('abaPrecisaCarregar("tarefas")'), true);
  assert.equal(n.chamar('abaPrecisaCarregar("tarefas")'), false, "recarregou: janela nova");
});

test("cache de aba: escrita/falha (invalidarDadosAbas) forca recarga em todas as abas", () => {
  const n = carregarNavegacao();
  n.chamar('abaPrecisaCarregar("tarefas")');
  n.chamar('abaPrecisaCarregar("vida")');
  n.chamar("invalidarDadosAbas()");
  assert.equal(n.chamar('abaPrecisaCarregar("tarefas")'), true);
  assert.equal(n.chamar('abaPrecisaCarregar("vida")'), true);
});

test("cache de aba: voltar do segundo plano e rede voltando invalidam", () => {
  const n = carregarNavegacao();
  n.chamar('abaPrecisaCarregar("gastos")');
  n.ouvintes.document.visibilitychange();
  assert.equal(n.chamar('abaPrecisaCarregar("gastos")'), true);
  n.ouvintes.window.online();
  assert.equal(n.chamar('abaPrecisaCarregar("gastos")'), true);
});

test("cache de aba: relogio andando pra tras recarrega em vez de ficar 'fresca' ate o relogio alcancar", () => {
  const n = carregarNavegacao();
  n.chamar('abaPrecisaCarregar("painel")');
  n.avancar(-500_000); // relogio ajustado pra tras
  assert.equal(n.chamar('abaPrecisaCarregar("painel")'), true);
});
