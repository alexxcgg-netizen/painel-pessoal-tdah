// cards-premium.js: acabamento dos cards novos (odometro, selo, confete). Em Node nao
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

test("so tipos que registram ganham selo (consulta nao)", () => {
  assert.ok(CardsPremium.TIPOS_REGISTRO.has("transacao"));
  assert.ok(CardsPremium.TIPOS_REGISTRO.has("tarefas_criadas"));
  assert.ok(!CardsPremium.TIPOS_REGISTRO.has("gastos_resumo"));
  assert.ok(!CardsPremium.TIPOS_REGISTRO.has("clima"));
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
