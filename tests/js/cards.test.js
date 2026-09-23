// Testes da logica PURA do registro de cards (static/js/cards.js) e dos
// renderizadores (static/js/cards-tipos.js) - contrato em docs/CARDS.md.
//
//   node --test tests/js/cards.test.js
//
// Renderizador = funcao pura (data, card, ctx) -> string HTML, entao da pra
// testar sem DOM. O wiring de eventos (desfazer, abrir aba, checkbox) e
// conferido no navegador headless (Playwright), ver AGENTS.md.
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const Cards = require(path.join(__dirname, "..", "..", "static", "js", "cards.js"));
require(path.join(__dirname, "..", "..", "static", "js", "cards-tipos.js"));

const FALLBACK = "Este trecho não pode ser exibido. Os dados foram preservados.";

// ---- registro + fallback (US-E2) ----

test("type desconhecido vira o card fallback com o texto do contrato", () => {
  const html = Cards.renderizarCardHTML({ type: "tipo_que_nao_existe", id: "c1", data: { a: 1 }, actions: [] });
  assert.match(html, /card-contrato-fallback/);
  assert.ok(html.includes(Cards.esc(FALLBACK)));
  assert.equal(Cards.TEXTO_FALLBACK, FALLBACK);
});

test("fallback preserva o card original (data-card-json) escapado", () => {
  const card = { type: "x", data: { titulo: '<img src=x onerror="alert(1)">' }, actions: [] };
  const html = Cards.renderizarCardHTML(card);
  assert.ok(!html.includes("<img"));
  assert.match(html, /data-card-json="\{&quot;type&quot;:&quot;x&quot;/);
});

test("card malformado nunca lanca excecao", () => {
  for (const ruim of [null, undefined, 42, "texto", [], {}, { type: 5 }, { type: "" }]) {
    assert.doesNotThrow(() => Cards.renderizarCardHTML(ruim));
    assert.match(Cards.renderizarCardHTML(ruim), /card-contrato-fallback/);
  }
});

test("renderizador que lanca erro vira fallback (nao derruba a lista)", () => {
  Cards.registrar("teste_quebrado", () => {
    throw new Error("boom");
  });
  Cards.registrar("teste_ok", (d) => `<p class="ok">${Cards.esc(d.t)}</p>`);
  const aviso = console.warn;
  console.warn = () => {};
  try {
    const html = Cards.renderizarListaHTML([
      { type: "teste_quebrado", data: {}, actions: [] },
      { type: "teste_ok", data: { t: "oi" }, actions: [] },
    ]);
    assert.match(html, /card-contrato-fallback/);
    assert.match(html, /<p class="ok">oi<\/p>/);
  } finally {
    console.warn = aviso;
  }
});

test("renderizador que nao devolve string vira fallback", () => {
  Cards.registrar("teste_sem_string", () => 123);
  assert.match(Cards.renderizarCardHTML({ type: "teste_sem_string", data: {} }), /fallback/);
});

test("registrar exige tipo string e funcao", () => {
  assert.throws(() => Cards.registrar("", () => ""));
  assert.throws(() => Cards.registrar("x", "nao e funcao"));
});

test("renderizarListaHTML com entrada que nao e lista devolve vazio", () => {
  assert.equal(Cards.renderizarListaHTML(null), "");
  assert.equal(Cards.renderizarListaHTML({}), "");
});

test("card registrado ganha o invólucro com type/id e o rodapé de actions", () => {
  Cards.registrar("teste_rodape", () => "<p>corpo</p>");
  const html = Cards.renderizarCardHTML({
    type: "teste_rodape",
    id: "c9",
    data: {},
    actions: [
      { tipo: "abrir_aba", rotulo: "Abrir Tarefas", aba: "tarefas", destaque: { entidade: "tarefa", id: 3 } },
      { tipo: "desfazer", rotulo: "Desfazer", token: "tok_1", alvo: [] },
      { tipo: "acao_do_futuro", rotulo: "???" },
    ],
  });
  assert.match(html, /data-card-type="teste_rodape"/);
  assert.match(html, /data-card-id="c9"/);
  assert.match(html, /data-acao="abrir_aba" data-aba="tarefas" data-destaque-entidade="tarefa" data-destaque-id="3"/);
  assert.match(html, /data-acao="desfazer" data-token="tok_1"/);
  assert.ok(!html.includes("???")); // action desconhecida e ignorada
});

test("consome: action desenhada pelo renderizador nao repete no rodape", () => {
  Cards.registrar("teste_consome", (d, card) => Cards.acoesDoTipo(card, "desfazer").map(Cards.acaoHTML).join(""), {
    consome: ["desfazer"],
  });
  const html = Cards.renderizarCardHTML({
    type: "teste_consome",
    data: {},
    actions: [{ tipo: "desfazer", token: "t" }],
  });
  assert.equal(html.match(/data-acao="desfazer"/g).length, 1);
});

// ---- utilitarios puros ----

test("esc escapa os 5 caracteres perigosos e trata null", () => {
  assert.equal(Cards.esc(`<a href="x">'&'</a>`), "&lt;a href=&quot;x&quot;&gt;&#39;&amp;&#39;&lt;/a&gt;");
  assert.equal(Cards.esc(null), "");
  assert.equal(Cards.esc(undefined), "");
  assert.equal(Cards.esc(0), "0");
});

test("moeda usa o fmtMoeda do app quando existe", () => {
  globalThis.fmtMoeda = (v) => `FMT(${v})`;
  try {
    assert.equal(Cards.moeda(10), "FMT(10)");
  } finally {
    delete globalThis.fmtMoeda;
  }
  assert.match(Cards.moeda(9000), /R\$\s?9\.000,00/);
});

test("dataCurta: 'quarta 23'", () => {
  assert.equal(Cards.dataCurta("2026-09-23"), "quarta 23");
  assert.equal(Cards.dataCurta("2026-09-27"), "domingo 27");
  assert.equal(Cards.dataCurta("lixo"), "");
  assert.equal(Cards.dataCurta(null), "");
});

test("rotuloDia: hoje / amanha / ontem / data curta", () => {
  const agora = new Date(2026, 8, 23, 10, 0);
  assert.equal(Cards.rotuloDia("2026-09-23", agora), "hoje");
  assert.equal(Cards.rotuloDia("2026-09-24", agora), "amanhã");
  assert.equal(Cards.rotuloDia("2026-09-22", agora), "ontem");
  assert.equal(Cards.rotuloDia("2026-09-30", agora), "quarta 30");
});

test("textoContagem: horas+minutos, minutos, dias, agora, passado", () => {
  const agora = new Date(2026, 8, 23, 10, 0);
  assert.equal(Cards.textoContagem(new Date(2026, 8, 24, 9, 6), agora), "faltam 23h 6min");
  assert.equal(Cards.textoContagem(new Date(2026, 8, 23, 10, 12), agora), "faltam 12min");
  assert.equal(Cards.textoContagem(new Date(2026, 8, 23, 12, 0), agora), "faltam 2h");
  assert.equal(Cards.textoContagem(new Date(2026, 8, 26, 10, 0), agora), "faltam 3 dias");
  assert.equal(Cards.textoContagem(new Date(2026, 8, 23, 10, 0), agora), "agora");
  assert.equal(Cards.textoContagem(new Date(2026, 8, 23, 9, 55), agora), "passou há 5min");
  assert.equal(Cards.textoContagem(new Date("lixo"), agora), "");
});

test("fmtDuracao", () => {
  assert.equal(Cards.fmtDuracao(110), "1h50");
  assert.equal(Cards.fmtDuracao(45), "45 min");
  assert.equal(Cards.fmtDuracao(60), "1h");
  assert.equal(Cards.fmtDuracao(65), "1h05");
  assert.equal(Cards.fmtDuracao("x"), "0 min");
});

test("parseDataHora aceita ISO com T ou dia + hora separada", () => {
  assert.deepEqual(Cards.hhmm(Cards.parseDataHora("2026-09-29T14:00")), "14:00");
  assert.deepEqual(Cards.hhmm(Cards.parseDataHora("2026-09-29", "8:05")), "08:05");
  assert.equal(Cards.parseDataHora("2026-09-29"), null);
  assert.equal(Cards.parseDataHora(undefined), null);
});

test("dataPorExtenso e diaMesCurto", () => {
  assert.equal(Cards.dataPorExtenso(new Date(2026, 8, 29, 14, 0)), "terça, 29 de setembro");
  assert.equal(Cards.diaMesCurto("2026-12-22"), "22 dez");
});
