// Cards da leva Lab v4 "Avisos e manha" (static/js/cards-manha.js): cartoes_manha, bom_dia, se_entao e carro
// renderizam o estado final, escapam texto e nao viram fallback com dado faltando.
//
//   node --test tests/js/cards_manha.test.js
//
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const Cards = require(path.join(__dirname, "..", "..", "static", "js", "cards.js"));
require(path.join(__dirname, "..", "..", "static", "js", "cards-manha.js"));

const html = (type, data) => Cards.renderizarCardHTML({ type, id: "c1", data, actions: [] });
const semFallback = (h) => assert.ok(!h.includes("card-contrato-fallback"), h);

test("cartoes_manha: so os novos viram pilha, contador e botoes com o rotulo da IA", () => {
  const h = html("cartoes_manha", {
    preparado_as: "04:00",
    cartoes: [
      { id: 1, titulo: "Presente <b>da mãe</b>", texto: "Falou dia 12.", rotulo: "Ver 3 ideias", status: "novo" },
      { id: 2, titulo: "Óleo", texto: "9.400 km.", rotulo: "Marcar", status: "novo" },
      { id: 3, titulo: "Já foi", texto: "x", rotulo: "y", status: "feito" },
    ],
  });
  semFallback(h);
  assert.match(h, /preparado às 04:00/);
  assert.match(h, /1 de 2 · Presente &lt;b&gt;da mãe/);
  assert.match(h, /2 de 2 · Óleo/);
  assert.doesNotMatch(h, /Já foi/);
  assert.match(h, /data-acao="mn_r" data-id="1"[^>]*>Ver 3 ideias</);
  assert.match(h, /data-acao="mn_d"/);
  assert.match(h, /data-acao="mn_e"/);
  assert.match(h, /data-ids="1,2,3"/);
});

test("cartoes_manha sem cartao novo mostra o fim, e dado faltando nao quebra", () => {
  const h = html("cartoes_manha", { cartoes: [{ id: 1, titulo: "a", texto: "b", rotulo: "c", status: "feito" }] });
  semFallback(h);
  assert.match(h, /Tudo em dia/);
  assert.match(h, /Amanhã tem mais, se tiver\./);
  semFallback(html("cartoes_manha", {}));
});

test("bom_dia: onda, linhas com trilho do sono e a nota da voz", () => {
  const h = html("bom_dia", {
    hora: "07:30",
    linhas: [
      { rot: "Sono", valor: "6h40 · dormiu 23:50", trilho: 0.83 },
      { rot: "Agenda", valor: "Voo 9:00" },
    ],
  });
  semFallback(h);
  assert.match(h, /mn-onda/);
  assert.match(h, /6h40 · dormiu 23:50/);
  assert.match(h, /width:83%/);
  assert.match(h, /Voo 9:00/);
  assert.match(h, /falado em voz alta, em uns 20 segundos/);
  semFallback(html("bom_dia", {}));
});

test("se_entao: frase com dois buracos, chips de gatilho (mais 'numa hora'), acoes e Ativar desligado", () => {
  const h = html("se_entao", {
    meta: "beber <i>agua</i>",
    gatilhos: [{ id: "acordar", rotulo: "acordar" }, { id: "chegar_casa", rotulo: "chegar em casa" }],
    acoes: ["bebo um copo", "encho a garrafa"],
  });
  semFallback(h);
  assert.match(h, /Quando<\/span><span class="mn-slot" data-s="0">/);
  assert.match(h, /data-acao="se_g" data-g="acordar"/);
  assert.match(h, /data-g="hora" data-r="numa hora"/);
  assert.match(h, /data-acao="se_a" data-i="1"[^>]*>encho a garrafa/);
  assert.match(h, /data-acao="se_ativar" disabled/);
  assert.match(h, /&lt;i&gt;agua/);
  assert.match(h, /type="time"/);
  semFallback(html("se_entao", {}));
});

test("carro: fala em destaque e a parada custa +N min", () => {
  const h = html("carro", { hora: "18:00", fala: "Academia às 18h30, tu chega 18h25.", extra_min: 5, parada: "Posto X" });
  semFallback(h);
  assert.match(h, /No caminho/);
  assert.match(h, /Academia às 18h30/);
  assert.match(h, /\+5 min com a parada/);
  assert.doesNotMatch(html("carro", { fala: "x" }), /min com a parada/);
  semFallback(html("carro", {}));
});
