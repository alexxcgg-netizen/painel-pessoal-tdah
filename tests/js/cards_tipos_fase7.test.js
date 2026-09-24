// Testes dos renderizadores novos da Fase 7 (faixa V1-hoje): assinatura,
// compra_parcelada e resumo_financeiro_recorrente (static/js/cards-tipos.js).
// Mesmo padrao de tests/js/cards.test.js - renderizador e funcao pura, testa
// sem DOM. Contrato de `data`: docs/CARDS.md (suposicao registrada em
// scripts/ralph-v1-hoje/progress.txt enquanto a faixa N1 nao publica
// docs/contrato-assinaturas.md na integracao).
//
//   node --test tests/js/cards_tipos_fase7.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const Cards = require(path.join(__dirname, "..", "..", "static", "js", "cards.js"));
require(path.join(__dirname, "..", "..", "static", "js", "cards-tipos.js"));

// ---- assinatura -------------------------------------------------------------

test("assinatura: titulo, valor/mes, dia de cobranca, cartao, categoria e proxima cobranca", () => {
  const html = Cards.renderizarCardHTML({
    type: "assinatura",
    data: {
      nome: "Netflix",
      valor: 44.9,
      dia_cobranca: 12,
      proxima_cobranca: "2026-10-12",
      em_dias: 18,
      cartao: "Nubank",
      categoria: "streaming",
      ativa: true,
    },
  });
  assert.match(html, /<p class="card-titulo">Netflix<\/p>/);
  assert.match(html, /R\$\s?44,90 \/mês/);
  assert.match(html, /dia 12 · Nubank · streaming/);
  assert.match(html, /Próxima cobrança: 12 out · em 18 dias/);
  assert.doesNotMatch(html, /Inativa/);
});

test("assinatura inativa ganha o chip 'Inativa'", () => {
  const html = Cards.renderizarCardHTML({
    type: "assinatura",
    data: { nome: "Academia", valor: 120, ativa: false },
  });
  assert.match(html, /card-chip-neutro">Inativa<\/span>/);
});

test("assinatura: em_dias 0/1 viram 'hoje'/'amanhã', sem em_dias some a parte", () => {
  const hoje = Cards.renderizarCardHTML({ type: "assinatura", data: { nome: "x", valor: 10, em_dias: 0 } });
  assert.match(hoje, /hoje/);
  const amanha = Cards.renderizarCardHTML({ type: "assinatura", data: { nome: "x", valor: 10, em_dias: 1 } });
  assert.match(amanha, /amanhã/);
  const semData = Cards.renderizarCardHTML({ type: "assinatura", data: { nome: "x", valor: 10 } });
  assert.doesNotMatch(semData, /Próxima cobrança/);
});

test("assinatura NUNCA esconde o valor (sem MOEDA_OCULTA mesmo se data.oculto vier true)", () => {
  const html = Cards.renderizarCardHTML({
    type: "assinatura",
    data: { nome: "Spotify", valor: 21.9, oculto: true },
  });
  assert.match(html, /R\$\s?21,90/);
  assert.doesNotMatch(html, new RegExp(Cards.MOEDA_OCULTA.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
});

test("assinatura sem valor mostra travessao em vez de quebrar", () => {
  const html = Cards.renderizarCardHTML({ type: "assinatura", data: { nome: "Sem valor" } });
  assert.match(html, /card-valor-grande">—<\/p>/);
});

// ---- compra_parcelada --------------------------------------------------------

test("compra_parcelada: parcela atual/total, restantes, barra de progresso, termina em, cartao", () => {
  const html = Cards.renderizarCardHTML({
    type: "compra_parcelada",
    data: {
      descricao: "Notebook",
      valor_parcela: 350,
      parcela_atual: 3,
      n_parcelas: 10,
      restantes: 7,
      termina_em: "2027-05-15",
      cartao: "Itaú",
    },
  });
  assert.match(html, /<p class="card-titulo">Notebook<\/p>/);
  assert.match(html, /R\$\s?350,00 \/mês/);
  assert.match(html, /width:30\.0%/);
  assert.match(html, /Parcela 3 de 10 · 7 restantes · termina 15 mai · Itaú/);
});

test("compra_parcelada calcula 'restantes' (n_parcelas - parcela_atual) quando o backend nao manda", () => {
  const html = Cards.renderizarCardHTML({
    type: "compra_parcelada",
    data: { descricao: "TV", valor_parcela: 100, parcela_atual: 9, n_parcelas: 10 },
  });
  assert.match(html, /Parcela 9 de 10 · 1 restante\b/);
});

test("compra_parcelada: ultima parcela mostra '0 restantes' e completa a barra em 100%", () => {
  const html = Cards.renderizarCardHTML({
    type: "compra_parcelada",
    data: { descricao: "Geladeira", valor_parcela: 200, parcela_atual: 12, n_parcelas: 12 },
  });
  assert.match(html, /0 restantes\b/);
  assert.match(html, /width:100\.0%/);
  assert.match(html, /meta-progresso-barra completa/);
});

test("compra_parcelada: 1 parcela restante usa singular", () => {
  const html = Cards.renderizarCardHTML({
    type: "compra_parcelada",
    data: { descricao: "Fogão", valor_parcela: 150, parcela_atual: 11, n_parcelas: 12 },
  });
  assert.match(html, /1 restante\b/);
});

test("compra_parcelada NUNCA esconde o valor da parcela", () => {
  const html = Cards.renderizarCardHTML({
    type: "compra_parcelada",
    data: { descricao: "Sofá", valor_parcela: 89.5, parcela_atual: 1, n_parcelas: 6, oculto: true },
  });
  assert.match(html, /R\$\s?89,50/);
});

test("compra_parcelada sem parcela_atual/n_parcelas nao quebra e some a barra", () => {
  const html = Cards.renderizarCardHTML({ type: "compra_parcelada", data: { descricao: "x", valor_parcela: 10 } });
  assert.doesNotMatch(html, /meta-progresso/);
  assert.doesNotMatch(html, /card-contrato-fallback/);
});

// ---- resumo_financeiro_recorrente -------------------------------------------

test("resumo_financeiro_recorrente: total do mes, contagem de assinaturas/parcelas e proxima cobranca", () => {
  const html = Cards.renderizarCardHTML({
    type: "resumo_financeiro_recorrente",
    data: {
      total_mes: 612.4,
      n_assinaturas: 4,
      n_parcelas: 2,
      proxima_cobranca: { nome: "Netflix", data: "2026-10-01" },
    },
  });
  assert.match(html, /R\$\s?612,40/);
  assert.match(html, /4 assinaturas · 2 parcelas ativas/);
  assert.match(html, /Próxima cobrança: <strong>Netflix<\/strong> · 1 out/);
});

test("resumo_financeiro_recorrente com 1 de cada usa singular e sem proxima cobranca some a linha", () => {
  const html = Cards.renderizarCardHTML({
    type: "resumo_financeiro_recorrente",
    data: { total_mes: 50, n_assinaturas: 1, n_parcelas: 1 },
  });
  assert.match(html, /1 assinatura · 1 parcela ativa/);
  assert.doesNotMatch(html, /Próxima cobrança/);
});

// ---- resiliencia (mesmo padrao de "types complexos com data vazia") --------

test("assinatura/compra_parcelada/resumo_financeiro_recorrente com data vazia ou malformada nunca quebram", () => {
  for (const t of ["assinatura", "compra_parcelada", "resumo_financeiro_recorrente"]) {
    assert.ok(Cards.temRenderizador(t), t);
    assert.doesNotThrow(() => Cards.renderizarCardHTML({ type: t, data: {} }), t);
    assert.doesNotMatch(Cards.renderizarCardHTML({ type: t, data: {} }), /card-contrato-fallback/, t);
    assert.doesNotThrow(
      () =>
        Cards.renderizarCardHTML({
          type: t,
          data: { valor: "x", valor_parcela: null, parcela_atual: "a", n_parcelas: {}, proxima_cobranca: 5 },
        }),
      t
    );
  }
});

test("assinatura/compra_parcelada escapam HTML nos campos de texto (nome/descricao/cartao/categoria)", () => {
  const malicioso = '<img src=x onerror="alert(1)">';
  const a = Cards.renderizarCardHTML({
    type: "assinatura",
    data: { nome: malicioso, valor: 10, cartao: malicioso, categoria: malicioso },
  });
  assert.ok(!a.includes("<img"));
  const c = Cards.renderizarCardHTML({
    type: "compra_parcelada",
    data: { descricao: malicioso, valor_parcela: 10, cartao: malicioso },
  });
  assert.ok(!c.includes("<img"));
});

// ---- ganham o rodape padrao (desfazer) como qualquer outro card ------------

test("assinatura e compra_parcelada ganham o botao Desfazer do rodape padrao (nao 'consomem' a action)", () => {
  const acoes = [{ tipo: "desfazer", rotulo: "Desfazer", token: "tok_9", alvo: [] }];
  const a = Cards.renderizarCardHTML({ type: "assinatura", data: { nome: "x", valor: 10 }, actions: acoes });
  assert.match(a, /data-acao="desfazer" data-token="tok_9"/);
  const c = Cards.renderizarCardHTML({
    type: "compra_parcelada",
    data: { descricao: "x", valor_parcela: 10 },
    actions: acoes,
  });
  assert.match(c, /data-acao="desfazer" data-token="tok_9"/);
});
