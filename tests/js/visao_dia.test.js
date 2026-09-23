// Testes da logica PURA da visao do dia (Fase 6, Grupo E5 - US-E9), sem
// navegador/DOM - roda com o test runner nativo do Node:
//
//   node --test tests/js/visao_dia.test.js
//
// static/js/visao-dia.js exporta so as funcoes sem IO (nomeDiaCurto,
// textoResumoDia) via module.exports quando roda em Node - o wiring de DOM
// (seletor Dia/Semana/Mes, card "em foco agora", timeline) so existe em
// navegador de verdade, coberto por verificacao headless (Playwright)
// separada, ver AGENTS.md.
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const { nomeDiaCurto, textoResumoDia } = require(
  path.join(__dirname, "..", "..", "static", "js", "visao-dia.js")
);

// ---- nomeDiaCurto ----

test("nomeDiaCurto: mesma data que hoje vira 'Hoje'", () => {
  assert.equal(nomeDiaCurto("2026-09-23", "2026-09-23"), "Hoje");
});

test("nomeDiaCurto: dia seguinte vira 'Amanha'", () => {
  assert.equal(nomeDiaCurto("2026-09-24", "2026-09-23"), "Amanha");
});

test("nomeDiaCurto: dia anterior vira 'Ontem'", () => {
  assert.equal(nomeDiaCurto("2026-09-22", "2026-09-23"), "Ontem");
});

test("nomeDiaCurto: qualquer outro dia vira 'abrev dd'", () => {
  // 2026-09-23 e uma quarta-feira
  assert.equal(nomeDiaCurto("2026-09-26", "2026-09-23"), "sab 26");
  assert.equal(nomeDiaCurto("2026-09-20", "2026-09-23"), "dom 20");
});

test("nomeDiaCurto: funciona atravessando virada de mes", () => {
  assert.equal(nomeDiaCurto("2026-10-01", "2026-09-30"), "Amanha");
});

// ---- textoResumoDia ----

test("textoResumoDia: exemplo literal do AC (US-E9)", () => {
  assert.equal(textoResumoDia(6, 3), "Hoje · 6 itens · 3 concluidas");
});

test("textoResumoDia: zero itens e zero concluidas (plural)", () => {
  assert.equal(textoResumoDia(0, 0), "Hoje · 0 itens · 0 concluidas");
});

test("textoResumoDia: singular certo pros dois numeros independentemente", () => {
  assert.equal(textoResumoDia(1, 0), "Hoje · 1 item · 0 concluidas");
  assert.equal(textoResumoDia(1, 1), "Hoje · 1 item · 1 concluida");
  assert.equal(textoResumoDia(5, 1), "Hoje · 5 itens · 1 concluida");
});
