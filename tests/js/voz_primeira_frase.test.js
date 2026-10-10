// tests/js/voz_primeira_frase.test.js - primeiraFrase (static/js/nucleo/voz.js): so a 1a frase
// da resposta do chat vai pra voz premium (max 200 caracteres).
//
//   node --test tests/js/voz_primeira_frase.test.js

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const { primeiraFrase } = require(path.join(__dirname, "..", "..", "static", "js", "nucleo", "voz.js"));

test("corta no primeiro ponto, exclamacao ou interrogacao (mantendo a pontuacao)", () => {
  assert.equal(primeiraFrase("Oi, tudo bem? Como posso ajudar."), "Oi, tudo bem?");
  assert.equal(primeiraFrase("Feito! Criei a tarefa."), "Feito!");
  assert.equal(primeiraFrase("Anotei. Mais nada."), "Anotei.");
});

test("corta na quebra de linha", () => {
  assert.equal(primeiraFrase("Resumo do dia\n- item 1\n- item 2"), "Resumo do dia");
  assert.equal(primeiraFrase("\n\n  Primeira linha.\nSegunda"), "Primeira linha.");
});

test("texto sem pontuacao curto fica inteiro", () => {
  assert.equal(primeiraFrase("so isso aqui"), "so isso aqui");
});

test("sem pontuacao e maior que 200: corta no ultimo espaco, ate 200", () => {
  const texto = "palavra ".repeat(60).trim();
  const f = primeiraFrase(texto);
  assert.ok(f.length <= 200);
  assert.match(f, /palavra$/);
});

test("uma palavra gigante sem espaco corta seco em 200", () => {
  assert.equal(primeiraFrase("x".repeat(500)).length, 200);
});

test("frase com pontuacao mas maior que 200 tambem respeita o teto", () => {
  const f = primeiraFrase(("abc ".repeat(80)) + "fim.");
  assert.ok(f.length <= 200);
});

test("entradas vazias ou estranhas nao quebram", () => {
  assert.equal(primeiraFrase(""), "");
  assert.equal(primeiraFrase(null), "");
  assert.equal(primeiraFrase(undefined), "");
  assert.equal(primeiraFrase("   "), "");
  assert.equal(primeiraFrase(42), "42");
  assert.equal(primeiraFrase("..."), "...");
  assert.equal(primeiraFrase("Gastou R$ 1.500,50 hoje. Sobrou pouco."), "Gastou R$ 1.500,50 hoje.");
});

test("_partesFala: resposta longa vira primeira frase + resto; curta fica inteira", () => {
  const { _partesFala } = require(path.join(__dirname, "..", "..", "static", "js", "nucleo", "voz.js"));
  assert.deepEqual(_partesFala("Oi Alex, tudo certo."), ["Oi Alex, tudo certo."]);
  const longa =
    "Você tem quarenta e nove horas e vinte e quatro minutos de voo, em quarenta e quatro voos. " +
    "A maior parte foi em instrução, e onze horas foram solo. Seu último voo foi em outubro do ano passado.";
  const partes = _partesFala(longa);
  assert.equal(partes.length, 2);
  assert.ok(partes[0].endsWith("voos."), partes[0]);
  assert.equal(partes.join(" "), longa);
});
