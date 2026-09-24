// M1 (m1-front): o Desfazer dos cards de assinatura e compra parcelada chamava
// /api/desfazer/<token> e recebia 404 - essas entidades tem rota propria da N1
// (POST /api/financas/desfazer/<token>, rotas/n1_financas.py; docs/contrato-assinaturas.md).
// Testa a funcao PURA que escolhe a URL (Cards.urlDesfazer).
//
//   node --test tests/js/m1_cards_desfazer.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const Cards = require(path.join(__dirname, "..", "..", "static", "js", "cards.js"));
require(path.join(__dirname, "..", "..", "static", "js", "cards-tipos.js"));

test("assinatura e compra_parcelada usam a rota da N1", () => {
  assert.equal(Cards.urlDesfazer("assinatura", "abc123"), "/api/financas/desfazer/abc123");
  assert.equal(Cards.urlDesfazer("compra_parcelada", "abc123"), "/api/financas/desfazer/abc123");
});

test("demais tipos continuam na rota generica", () => {
  for (const tipo of ["tarefa", "evento", "gasto", "lembrete", "resumo_financeiro_recorrente", "desconhecido"]) {
    assert.equal(Cards.urlDesfazer(tipo, "tk"), "/api/desfazer/tk", tipo);
  }
});

test("tipo ausente ou invalido cai na rota generica (card sem data-card-type)", () => {
  for (const tipo of [undefined, null, "", 0, {}, [], "Assinatura", " assinatura", "assinatura "]) {
    assert.equal(Cards.urlDesfazer(tipo, "tk"), "/api/desfazer/tk", String(tipo));
  }
});

test("token e codificado na URL", () => {
  assert.equal(Cards.urlDesfazer("assinatura", "a/b?c#d"), "/api/financas/desfazer/a%2Fb%3Fc%23d");
  assert.equal(Cards.urlDesfazer("tarefa", "ç é"), "/api/desfazer/%C3%A7%20%C3%A9");
  assert.equal(Cards.urlDesfazer("assinatura", "../../x"), "/api/financas/desfazer/..%2F..%2Fx");
});

test("token ausente nao vira a string 'undefined'", () => {
  assert.equal(Cards.urlDesfazer("assinatura", undefined), "/api/financas/desfazer/");
  assert.equal(Cards.urlDesfazer("tarefa", null), "/api/desfazer/");
  assert.equal(Cards.urlDesfazer("tarefa", 42), "/api/desfazer/42");
});

// Liga o render ao clique: o data-card-type do <article> e o data-token do botao
// sao exatamente o que o handler de cards.js le.
function tipoETokenDoHTML(html) {
  const tipo = /<article[^>]*data-card-type="([^"]*)"/.exec(html);
  const token = /data-acao="desfazer" data-token="([^"]*)"/.exec(html);
  return { tipo: tipo && tipo[1], token: token && token[1] };
}

test("card de assinatura renderizado aponta pra rota da N1", () => {
  const html = Cards.renderizarCardHTML({
    type: "assinatura",
    id: "c1",
    data: { nome: "Streaming Exemplo", valor: 39.9, dia_cobranca: 10 },
    actions: [{ tipo: "desfazer", rotulo: "Desfazer", token: "tok-ass-1" }],
  });
  const { tipo, token } = tipoETokenDoHTML(html);
  assert.equal(tipo, "assinatura");
  assert.equal(token, "tok-ass-1");
  assert.equal(Cards.urlDesfazer(tipo, token), "/api/financas/desfazer/tok-ass-1");
});

test("card de compra parcelada renderizado aponta pra rota da N1", () => {
  const html = Cards.renderizarCardHTML({
    type: "compra_parcelada",
    id: "c2",
    data: { descricao: "Notebook exemplo", valor_parcela: 250, n_parcelas: 10, parcela_atual: 1 },
    actions: [{ tipo: "desfazer", rotulo: "Desfazer", token: "tok-parc-1" }],
  });
  const { tipo, token } = tipoETokenDoHTML(html);
  assert.equal(tipo, "compra_parcelada");
  assert.equal(token, "tok-parc-1");
  assert.equal(Cards.urlDesfazer(tipo, token), "/api/financas/desfazer/tok-parc-1");
});
