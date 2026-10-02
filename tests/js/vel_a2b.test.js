// tests/js/vel_a2b.test.js - Vel A2b (uso diario, atualizacao otimista):
// testa as funcoes puras extraidas (guarda `typeof module`) de
// static/js/secoes/tarefas/tarefas.js (calcularHashTarefas, usada em
// loadTasks() pra nao reconstruir a lista se os dados nao mudaram) e de
// static/js/secoes/painel/saude-hoje.js (calcularProximoTotalHidratacao,
// usada no +1 copo otimista). Node puro, sem DOM.
const test = require("node:test");
const assert = require("node:assert/strict");

// Esses dois arquivos sao "scripts classicos" (escopo global do navegador) e
// ligam listeners de DOM no top-level (`$("#...").addEventListener(...)`) -
// sem isso o require() quebra fora do navegador. Shim minimo, so pra deixar
// esse top-level rodar; as funcoes puras testadas abaixo nao usam DOM.
global.$ = () => ({
  addEventListener() {},
  querySelectorAll() {
    return [];
  },
  querySelector() {
    return null;
  },
});

const { calcularHashTarefas, proximoLoteTarefas } = require("../../static/js/secoes/tarefas/tarefas.js");
const { calcularProximoTotalHidratacao } = require("../../static/js/secoes/painel/saude-hoje.js");

test("calcularHashTarefas: mesma lista de tarefas gera o mesmo hash", () => {
  const tasks = [
    { id: 1, title: "a" },
    { id: 2, title: "b" },
  ];
  const copia = JSON.parse(JSON.stringify(tasks));
  assert.equal(calcularHashTarefas(tasks), calcularHashTarefas(copia));
});

test("calcularHashTarefas: lista diferente gera hash diferente (dispara reconstrucao)", () => {
  const antes = [{ id: 1, title: "a" }];
  const depois = [{ id: 1, title: "a" }, { id: 2, title: "b" }];
  assert.notEqual(calcularHashTarefas(antes), calcularHashTarefas(depois));
});

test("calcularHashTarefas: lista vazia e estavel entre chamadas", () => {
  assert.equal(calcularHashTarefas([]), calcularHashTarefas([]));
});

test("calcularProximoTotalHidratacao: soma 1 ao total atual (otimista)", () => {
  assert.equal(calcularProximoTotalHidratacao("3"), 4);
  assert.equal(calcularProximoTotalHidratacao(0), 1);
  assert.equal(calcularProximoTotalHidratacao("10"), 11);
});

test("calcularProximoTotalHidratacao: texto nao numerico devolve o mesmo valor (defesa)", () => {
  assert.equal(calcularProximoTotalHidratacao("-"), "-");
  assert.equal(calcularProximoTotalHidratacao(""), "");
});

test("proximoLoteTarefas: soma 10 por vez e nunca passa do total", () => {
  assert.equal(proximoLoteTarefas(100, 10), 20);
  assert.equal(proximoLoteTarefas(25, 20), 25);
  assert.equal(proximoLoteTarefas(5, 10), 5);
});
