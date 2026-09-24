// tests/js/c2_assistente.test.js - C2: lista de Avisos do assistente (static/js/secoes/assistente/avisos.js)
// Cada tipo virou linha (.lista-item) com <select class="campo"> direto (sem caixa dentro
// de caixa) e o cabecalho da secao recolhivel mostra "N de M ligados".
//
//   node --test tests/js/c2_assistente.test.js

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const Avisos = require(path.join(__dirname, "..", "..", "static", "js", "secoes", "assistente", "avisos.js"));

const TIPO = { tipo: "bom_dia", label: "Bom dia (rotina da manha)", ligado: true, canal: "caixa" };

test("tipo vira linha da lista, nao card dentro do card", () => {
  const html = Avisos.renderTipoHTML(TIPO);
  assert.match(html, /^<li class="lista-item aviso-item"/);
  assert.doesNotMatch(html, /class="card/);
});

test("canal e um select.campo direto, com rotulo acessivel (sem label.campo em volta)", () => {
  const html = Avisos.renderTipoHTML(TIPO);
  assert.match(html, /<select class="campo aviso-canal" data-tipo="bom_dia" aria-label="Canal: Bom dia \(rotina da manha\)">/);
  assert.doesNotMatch(html, /<label class="campo/);
  assert.match(html, /<option value="caixa" selected>Caixa<\/option>/);
});

test("checkbox reflete ligado/desligado", () => {
  assert.match(Avisos.renderTipoHTML(TIPO), /class="aviso-ligado" data-tipo="bom_dia" checked>/);
  assert.doesNotMatch(Avisos.renderTipoHTML({ ...TIPO, ligado: false }), / checked>/);
});

test("rotulo e tipo com HTML sao escapados (inclusive dentro do aria-label)", () => {
  const html = Avisos.renderTipoHTML({ tipo: '"><img>', label: "<b>x</b>", ligado: false, canal: "push" });
  assert.doesNotMatch(html, /<img>|<b>/);
  assert.match(html, /&lt;b&gt;x&lt;\/b&gt;/);
});

test("textoContagem: N de M ligados", () => {
  assert.equal(Avisos.textoContagem([TIPO, { ...TIPO, ligado: false }, { ...TIPO }]), "2 de 3 ligados");
  assert.equal(Avisos.textoContagem([{ ...TIPO, ligado: false }]), "0 de 1 ligados");
});

test("textoContagem aguenta lista vazia, null e itens quebrados", () => {
  assert.equal(Avisos.textoContagem([]), "");
  assert.equal(Avisos.textoContagem(null), "");
  assert.equal(Avisos.textoContagem("x"), "");
  assert.equal(Avisos.textoContagem([null, TIPO, 5]), "1 de 3 ligados");
});

test("lista vazia mostra a frase de vazio", () => {
  assert.match(Avisos.renderListaHTML([]), /avisos-vazio/);
  assert.match(Avisos.renderListaHTML(undefined), /avisos-vazio/);
});
