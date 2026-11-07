// "Tá aberto?" (frente D, 07/11/2026): a pílula da tarefa com lugar ganha a linha do lugar fechado/
// fechando na hora de chegar (data.lugar_fechado, montado em cards.card_tarefas_criadas). Puro, sem DOM.
//
//   node --test tests/js/lugar_fechado.test.js
//
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const js = (f) => path.join(__dirname, "..", "..", "static", "js", f);
const Cards = require(js("cards.js"));
require(js("cards-d.js"));
require(js("cards-tipos.js"));

const AGORA = new Date(2026, 10, 7, 20, 0);
const G = AGORA.getTime() / 1000;
const card = (data) => Cards.renderizarCardHTML({ type: "tarefas_criadas", id: "t1", data, actions: [] }, { agora: AGORA });
const T = { id: 5, titulo: "Comprar tênis", data: "2026-11-07", hora: "22:10", local: "Shopping" };
const FECHADO = { estado: "fechado", frase: "Fecha às 22h e tu chega 22h10.", curta: "fecha 22h, tu chega 22h10", nome: "Shopping" };

test("lugar fechado na chegada: linha curta no lugar do 'quando' e a frase inteira dentro", () => {
  const h = card({ tarefas: [T], em_s: 7800, gerado_ts: G, lugar_fechado: FECHADO });
  assert.match(h, /<span class="v-s"><span class="v-s-alerta">fecha 22h, tu chega 22h10<\/span><\/span>/);
  assert.match(h, /<p class="v-nota alerta v-lugar-fechado">Fecha às 22h e tu chega 22h10\.<\/p>/);
  assert.doesNotMatch(h, /Comprar tênis · /); // o "quando" sai pra caber em 390 px
  assert.doesNotMatch(h, /você/i);
});

test("sem alerta (ou alerta quebrado / sem lugar) a pílula fica como era", () => {
  for (const ruim of [undefined, null, "x", {}, { curta: "a" }, { frase: "b" }, { curta: 1, frase: 2 }]) {
    const h = card({ tarefas: [T], em_s: 7800, gerado_ts: G, lugar_fechado: ruim });
    assert.doesNotMatch(h, /v-s-alerta|v-lugar-fechado/);
    assert.match(h, /Comprar tênis · /);
  }
  const semLugar = card({ tarefas: [{ ...T, local: null }], em_s: 7800, gerado_ts: G, lugar_fechado: FECHADO });
  assert.doesNotMatch(semLugar, /v-s-alerta|v-lugar-fechado/);
});

test("texto do Google entra escapado", () => {
  const h = card({ tarefas: [T], em_s: 7800, gerado_ts: G,
    lugar_fechado: { ...FECHADO, curta: "<b>x</b>", frase: '<img src=x onerror="1">' } });
  assert.ok(!h.includes("<img") && !h.includes("<b>x"));
});
