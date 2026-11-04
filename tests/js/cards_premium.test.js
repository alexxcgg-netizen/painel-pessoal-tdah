// cards-premium.js: acabamento dos cards novos (odometro, confete, costura; selo e inclinacao sairam em 04/11). Em Node nao
// ha DOM - garante que nada quebra sem navegador e que o odometro devolve o texto final.
const test = require("node:test");
const assert = require("node:assert");
const CardsPremium = require("../../static/js/cards-premium.js");

test("exporta a API e nao quebra sem DOM", () => {
  for (const nome of ["animar", "odometro", "festejar", "desfeito"]) {
    assert.strictEqual(typeof CardsPremium[nome], "function", nome);
  }
  assert.doesNotThrow(() => CardsPremium.animar(null));
  assert.doesNotThrow(() => CardsPremium.festejar(null));
  assert.doesNotThrow(() => CardsPremium.desfeito(null));
  assert.doesNotThrow(() => CardsPremium.odometro(null));
});

test("sem cara de IA (04/11): sem selo brilhante, sem inclinacao 3D e sem luz que segue o dedo", () => {
  // o selo "registrado" e a inclinacao/luz sairam da API (docs/CARDS.md "Linguagem visual")
  assert.strictEqual(CardsPremium.TIPOS_REGISTRO, undefined);
  assert.strictEqual(CardsPremium.inclinacao, undefined);
  const fs = require("node:fs");
  const path = require("node:path");
  const js = fs.readFileSync(path.join(__dirname, "..", "..", "static", "js", "cards-premium.js"), "utf8");
  assert.doesNotMatch(js, /card-fio-borda|card-selo|rotateX|--luz-x|function inclinacao/);
  const css = fs.readFileSync(path.join(__dirname, "..", "..", "static", "css", "secoes", "hoje", "cards-premium.css"), "utf8");
  assert.doesNotMatch(css, /card-fio-borda|--fio-ang|card-selo|perspective\s*:|rotateX|--luz-x/);
});

test("odometro monta as fitas e volta pro texto exato no fim", async () => {
  const el = {
    textContent: "-R$ 89,90",
    dataset: {},
    attrs: {},
    setAttribute(k, v) { this.attrs[k] = v; },
    removeAttribute(k) { delete this.attrs[k]; },
    set innerHTML(v) { this._html = v; },
    get innerHTML() { return this._html; },
  };
  CardsPremium.odometro(el);
  assert.strictEqual((el.innerHTML.match(/class="odo-dig"/g) || []).length, 4);
  assert.strictEqual(el.attrs["aria-label"], "-R$ 89,90");
  await new Promise((r) => setTimeout(r, 1500));
  assert.strictEqual(el.textContent, "-R$ 89,90");
  assert.strictEqual(el.attrs["aria-label"], undefined);
});

test("odometro ignora texto sem digito", () => {
  const el = { textContent: "R$ •••", dataset: {}, setAttribute() { throw new Error("nao devia"); } };
  assert.doesNotThrow(() => CardsPremium.odometro(el));
});

test("costura: um fio entre cada par de cards vizinhos, na ordem", () => {
  const g = CardsPremium.geometriaCostura([
    { y: 20, cor: "red" },
    { y: 180, cor: "blue" },
    { y: 400, cor: "green" },
  ]);
  assert.strictEqual(g.fios.length, 2);
  assert.deepStrictEqual(
    g.fios.map((f) => [f.top, f.altura, f.de, f.para]),
    [[20, 160, "red", "blue"], [180, 220, "blue", "green"]],
  );
  assert.ok(g.fios[1].atraso > g.fios[0].atraso, "trecho de baixo desenha depois");
  assert.strictEqual(g.total, 380);
});

test("costura: sem layout (aba escondida, tudo em 0) nao gera fio torto", () => {
  const g = CardsPremium.geometriaCostura([{ y: 0, cor: "a" }, { y: 0, cor: "b" }, { y: NaN }]);
  assert.strictEqual(g.fios.length, 0);
  assert.strictEqual(g.nos.length, 2);
  assert.deepStrictEqual(CardsPremium.geometriaCostura(null).fios, []);
});

test("costurar nao quebra sem DOM", () => {
  assert.doesNotThrow(() => CardsPremium.costurar(null));
  assert.doesNotThrow(() => CardsPremium.costurar({ querySelectorAll: () => [] }, { nova: true }));
});

test("arrasto: segue o dedo, resiste depois de 90px e conclui a partir de 72px", () => {
  assert.deepStrictEqual(CardsPremium.arrasto(-30), { dx: 0, p: 0, conclui: false });
  const pouco = CardsPremium.arrasto(40);
  assert.strictEqual(pouco.dx, 40);
  assert.ok(!pouco.conclui && pouco.p < 1);
  assert.ok(CardsPremium.arrasto(72).conclui);
  const longe = CardsPremium.arrasto(200);
  assert.ok(longe.dx < 200 && longe.dx > 90 && longe.dx <= 140, String(longe.dx));
  assert.strictEqual(longe.p, 1);
});

test("toque: sem DOM nada quebra", () => {
  assert.doesNotThrow(() => CardsPremium.ligarToque(null));
  assert.doesNotThrow(() => CardsPremium.alternarDetalhe(null));
});
