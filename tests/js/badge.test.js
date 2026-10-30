// Numero no icone (static/js/nucleo/badge.js): aplica/limpa pela Badging API, ignora lixo e nao levanta sem a API.
//
//   node --test tests/js/badge.test.js
//
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const codigo = fs.readFileSync(path.join(__dirname, "..", "..", "static", "js", "nucleo", "badge.js"), "utf8");

function carregar({ comApi, resposta }) {
  const chamadas = [];
  const navigator = comApi
    ? { setAppBadge: (n) => (chamadas.push(["set", n]), Promise.resolve()), clearAppBadge: () => (chamadas.push(["clear"]), Promise.resolve()) }
    : {};
  const ctx = {
    navigator, window: {}, setTimeout, clearTimeout, console,
    fetch: async () => ({ ok: true, json: async () => resposta || { n: 3 } }),
  };
  vm.createContext(ctx);
  vm.runInContext(codigo, ctx);
  return { Badge: ctx.window.Badge, chamadas };
}

test("aplica o numero e limpa no zero", () => {
  const { Badge, chamadas } = carregar({ comApi: true });
  assert.equal(Badge.aplicar(4), true);
  assert.equal(Badge.aplicar(0), true);
  assert.deepEqual(chamadas, [["set", 4], ["clear"]]);
});

test("lixo e negativo sao ignorados", () => {
  const { Badge, chamadas } = carregar({ comApi: true });
  for (const v of [-1, "abc", NaN, undefined, null === 0 ? 0 : "x"]) assert.equal(Badge.aplicar(v), false);
  assert.deepEqual(chamadas, []);
});

test("sem a API (desktop) nao faz nada e nao levanta", async () => {
  const { Badge } = carregar({ comApi: false });
  assert.equal(Badge.suportado(), false);
  assert.equal(Badge.aplicar(2), false);
  assert.equal(await Badge.atualizar(), null);
  assert.doesNotThrow(() => Badge.atualizarDepois(0));
});

test("atualizar busca o numero do servidor e pinta", async () => {
  const { Badge, chamadas } = carregar({ comApi: true, resposta: { n: 7 } });
  assert.equal(await Badge.atualizar(), 7);
  assert.deepEqual(chamadas, [["set", 7]]);
});
