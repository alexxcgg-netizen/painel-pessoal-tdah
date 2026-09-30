// anim2: logica pura da lista sem reanimar (movimento.js) e do copo (saude-hoje.js).
//   node --test tests/js/anim2_lista.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { calcularItensNovos } = require(path.join(__dirname, "..", "..", "static", "js", "nucleo", "movimento.js"));

test("1a carga: entram so os 12 primeiros", () => {
  const sigs = Array.from({ length: 30 }, (_, i) => "i" + i);
  const r = calcularItensNovos(null, sigs);
  assert.equal(r.entram.length, 12);
  assert.deepEqual(r.entram.slice(0, 3), [0, 1, 2]);
});

test("reconstrucao com os mesmos dados: ninguem entra", () => {
  const sigs = ["a", "b", "c"];
  const r1 = calcularItensNovos(null, sigs);
  assert.deepEqual(calcularItensNovos(r1.mapa, sigs).entram, []);
});

test("item novo no topo: so ele entra", () => {
  const r1 = calcularItensNovos(null, ["a", "b"]);
  assert.deepEqual(calcularItensNovos(r1.mapa, ["nova", "a", "b"]).entram, [0]);
});

test("apagar: ninguem entra; duplicados contam por quantidade", () => {
  const r1 = calcularItensNovos(null, ["a", "a", "b"]);
  assert.deepEqual(calcularItensNovos(r1.mapa, ["a", "b"]).entram, []);
  const r2 = calcularItensNovos(r1.mapa, ["a", "a", "a", "b"]);
  assert.deepEqual(r2.entram, [2]);
});

test("lista esvaziada e repovoada: entram todos (ate 12)", () => {
  const r1 = calcularItensNovos(null, ["a"]);
  const r2 = calcularItensNovos(r1.mapa, []);
  assert.deepEqual(calcularItensNovos(r2.mapa, ["a", "b"]).entram, [0, 1]);
});

test("fuzz: 200 sequencias aleatorias nunca passam de 12 e so marcam o que e novo", () => {
  let seed = 7;
  const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  for (let k = 0; k < 200; k++) {
    let mapa = rnd() < 0.5 ? null : new Map();
    for (let passo = 0; passo < 5; passo++) {
      const n = Math.floor(rnd() * 25);
      const sigs = Array.from({ length: n }, () => "s" + Math.floor(rnd() * 10));
      const r = calcularItensNovos(mapa, sigs);
      assert.ok(r.entram.length <= 12);
      assert.ok(r.entram.every((i) => i >= 0 && i < n));
      assert.equal(new Set(r.entram).size, r.entram.length);
      mapa = r.mapa;
    }
  }
});
