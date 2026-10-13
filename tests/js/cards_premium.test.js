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
