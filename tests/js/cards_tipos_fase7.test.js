// Testes dos renderizadores da Fase 7: assinatura, compra_parcelada e
// resumo_financeiro_recorrente (static/js/cards-tipos.js).
// V1 escreveu contra um formato provisorio; a C2 alinhou ao contrato publicado pela N1
// (docs/contrato-assinaturas.md, secao "Cards"). Os nomes provisorios continuam aceitos
// como reserva - ha testes dos dois.
//
//   node --test tests/js/cards_tipos_fase7.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const Cards = require(path.join(__dirname, "..", "..", "static", "js", "cards.js"));
require(path.join(__dirname, "..", "..", "static", "js", "cards-tipos.js"));

function isoDaquiA(dias) {
  const d = new Date();
  d.setDate(d.getDate() + dias);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// ---- assinatura (contrato N1) -------------------------------------------------

test("assinatura (contrato N1): nome, valor/mes, dia, cartao_ou_forma, categoria, proxima cobranca", () => {
  const prox = isoDaquiA(18);
  const html = Cards.renderizarCardHTML({
    type: "assinatura",
    data: {
      id: 5, nome: "Spotify", valor: 21.9, dia_cobranca: 24, cartao_ou_forma: "nubank",
      categoria: "streaming", ativa: true, inicio: "2026-09-24", cancelada_em: null,
      proxima_cobranca: prox,
    },
  });
  assert.match(html, /<p class="card-titulo">Spotify<\/p>/);
  assert.match(html, /R\$\s?21,90 \/mês/);
  assert.match(html, /todo dia 24 · nubank · streaming/);
  assert.match(html, new RegExp(`Próxima cobrança: ${Cards.diaMesCurto(prox)} · em 18 dias`));
  assert.doesNotMatch(html, /Cancelada/);
});

test("assinatura: dias ate a cobranca vem da proxima_cobranca (hoje/amanha)", () => {
  const hoje = Cards.renderizarCardHTML({ type: "assinatura", data: { nome: "x", valor: 10, proxima_cobranca: isoDaquiA(0) } });
  assert.match(hoje, / · hoje</);
  const amanha = Cards.renderizarCardHTML({ type: "assinatura", data: { nome: "x", valor: 10, proxima_cobranca: isoDaquiA(1) } });
  assert.match(amanha, / · amanhã</);
  const semData = Cards.renderizarCardHTML({ type: "assinatura", data: { nome: "x", valor: 10, proxima_cobranca: null } });
  assert.doesNotMatch(semData, /Próxima cobrança/);
});

test("assinatura cancelada: chip 'Cancelada em <dia>' e sem proxima cobranca", () => {
  const html = Cards.renderizarCardHTML({
    type: "assinatura",
    data: { nome: "Netflix", valor: 55, ativa: false, cancelada_em: "2026-09-20", proxima_cobranca: null },
  });
  assert.match(html, /card-chip-neutro">Cancelada em 20 set<\/span>/);
  assert.doesNotMatch(html, /Próxima cobrança/);
});

test("assinatura: formato provisorio da V1 (cartao, em_dias) ainda funciona", () => {
  const html = Cards.renderizarCardHTML({
    type: "assinatura",
    data: { nome: "Netflix", valor: 44.9, dia_cobranca: 12, cartao: "Nubank", em_dias: 18, proxima_cobranca: "2026-10-12", ativa: false },
  });
  assert.match(html, /todo dia 12 · Nubank/);
  assert.match(html, /card-chip-neutro">Cancelada<\/span>/);
});

test("assinatura NUNCA esconde o valor no front (quem tira no modo visitante e o servidor)", () => {
  const html = Cards.renderizarCardHTML({ type: "assinatura", data: { nome: "Spotify", valor: 21.9, oculto: true } });
  assert.match(html, /R\$\s?21,90/);
  assert.doesNotMatch(html, new RegExp(Cards.MOEDA_OCULTA.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
});

test("assinatura sem valor (servidor tirou no modo visitante) mostra travessao", () => {
  const html = Cards.renderizarCardHTML({ type: "assinatura", data: { nome: "Sem valor" } });
  assert.match(html, /card-valor-grande">—<\/p>/);
});

// ---- compra_parcelada (contrato N1) --------------------------------------------

test("compra_parcelada (contrato N1): parcela, restantes, mes_termino, cartao, total e barra", () => {
  const html = Cards.renderizarCardHTML({
    type: "compra_parcelada",
    data: {
      id: 2, descricao: "geladeira", valor_total: 3000.0, n_parcelas: 12, valor_parcela: 250.0,
      cartao: "nubank", primeira_parcela: "2026-09-24", categoria: null, parcela_atual: 3,
      parcelas_restantes: 10, mes_termino: "2027-08", quitada: false,
    },
  });
  assert.match(html, /<p class="card-titulo">geladeira<\/p>/);
  assert.match(html, /R\$\s?250,00 \/mês/);
  assert.match(html, /width:25\.0%/);
  assert.match(html, /Parcela 3 de 12 · 10 restantes · termina ago 2027 · nubank/);
  assert.match(html, /Total R\$\s?3\.000,00/);
  assert.doesNotMatch(html, /Quitada/);
});

test("compra_parcelada quitada: chip Quitada, barra cheia, 'terminou', sem 'restantes'", () => {
  const html = Cards.renderizarCardHTML({
    type: "compra_parcelada",
    data: { descricao: "TV", valor_parcela: 100, n_parcelas: 10, parcela_atual: 10, parcelas_restantes: 0, mes_termino: "2026-08", quitada: true },
  });
  assert.match(html, /card-chip-neutro">Quitada<\/span>/);
  assert.match(html, /width:100\.0%/);
  assert.match(html, /meta-progresso-barra completa/);
  assert.match(html, /terminou ago 2026/);
  assert.doesNotMatch(html, /restante/);
});

test("compra_parcelada calcula restantes (n_parcelas - parcela_atual) quando nao vem; singular", () => {
  const html = Cards.renderizarCardHTML({ type: "compra_parcelada", data: { descricao: "TV", valor_parcela: 100, parcela_atual: 9, n_parcelas: 10 } });
  assert.match(html, /Parcela 9 de 10 · 1 restante\b/);
});

test("compra_parcelada: formato provisorio da V1 (restantes, termina_em ISO) ainda funciona", () => {
  const html = Cards.renderizarCardHTML({
    type: "compra_parcelada",
    data: { descricao: "Notebook", valor_parcela: 350, parcela_atual: 3, n_parcelas: 10, restantes: 7, termina_em: "2027-05-15", cartao: "Itaú" },
  });
  assert.match(html, /Parcela 3 de 10 · 7 restantes · termina 15 mai · Itaú/);
});

test("compra_parcelada NUNCA esconde o valor da parcela no front", () => {
  const html = Cards.renderizarCardHTML({ type: "compra_parcelada", data: { descricao: "Sofá", valor_parcela: 89.5, parcela_atual: 1, n_parcelas: 6, oculto: true } });
  assert.match(html, /R\$\s?89,50/);
});

test("compra_parcelada sem parcela_atual/n_parcelas nao quebra e some a barra", () => {
  const html = Cards.renderizarCardHTML({ type: "compra_parcelada", data: { descricao: "x", valor_parcela: 10 } });
  assert.doesNotMatch(html, /meta-progresso/);
  assert.doesNotMatch(html, /card-contrato-fallback/);
});

// ---- resumo_financeiro_recorrente (contrato N1) --------------------------------

test("resumo_financeiro_recorrente (contrato N1): mes, total, contagens com subtotais e proximas cobrancas", () => {
  const html = Cards.renderizarCardHTML({
    type: "resumo_financeiro_recorrente",
    data: {
      mes: "2026-09", total_mensal: 571.9, assinaturas_total: 21.9, parcelas_total: 550.0,
      n_assinaturas_ativas: 1, n_compras_em_andamento: 2,
      proximas_cobrancas: [
        { tipo: "assinatura", id: 5, nome: "Spotify", valor: 21.9, data: "2026-10-24", dias: 30, label: "em 30 dias", cartao_ou_forma: "nubank" },
        { tipo: "compra_parcelada", id: 2, descricao: "geladeira", valor: 250, data: "2026-10-24", dias: 30, label: "em 30 dias" },
      ],
      consulta: true,
    },
  });
  assert.match(html, /Recorrentes · set 2026/);
  assert.match(html, /R\$\s?571,90/);
  assert.match(html, /1 assinatura \(R\$\s?21,90\) · 2 parcelas ativas \(R\$\s?550,00\)/);
  assert.match(html, /<strong>Spotify<\/strong><span class="card-linha-meta">24 out · em 30 dias<\/span><span class="card-recorrente-valor">R\$\s?21,90<\/span>/);
  assert.match(html, /<strong>geladeira<\/strong>/);
});

test("resumo_financeiro_recorrente mostra no maximo 3 proximas cobrancas", () => {
  const itens = Array.from({ length: 5 }, (_, i) => ({ nome: `item${i}`, valor: 10, data: "2026-10-01", dias: i }));
  const html = Cards.renderizarCardHTML({ type: "resumo_financeiro_recorrente", data: { total_mensal: 50, proximas_cobrancas: itens } });
  assert.equal((html.match(/card-recorrente-item/g) || []).length, 3);
  assert.doesNotMatch(html, /item3/);
});

test("resumo_financeiro_recorrente: formato provisorio da V1 (total_mes, n_assinaturas, proxima_cobranca) ainda funciona", () => {
  const html = Cards.renderizarCardHTML({
    type: "resumo_financeiro_recorrente",
    data: { total_mes: 612.4, n_assinaturas: 4, n_parcelas: 1, proxima_cobranca: { nome: "Netflix", data: "2026-10-01" } },
  });
  assert.match(html, /R\$\s?612,40/);
  assert.match(html, /4 assinaturas · 1 parcela ativa/);
  assert.match(html, /<strong>Netflix<\/strong><span class="card-linha-meta">1 out<\/span>/);
});

test("resumo_financeiro_recorrente sem proximas cobrancas some a lista", () => {
  const html = Cards.renderizarCardHTML({ type: "resumo_financeiro_recorrente", data: { total_mensal: 0, proximas_cobrancas: [] } });
  assert.doesNotMatch(html, /Próximas cobranças/);
});

// ---- helpers -------------------------------------------------------------------

test("mesCurto: AAAA-MM vira 'mes ano'; lixo vira vazio", () => {
  assert.equal(Cards.mesCurto("2027-08"), "ago 2027");
  assert.equal(Cards.mesCurto("2026-01"), "jan 2026");
  assert.equal(Cards.mesCurto(""), "");
  assert.equal(Cards.mesCurto(null), "");
  assert.equal(Cards.mesCurto("abc"), "");
});

// ---- resiliencia ----------------------------------------------------------------

test("os 3 tipos com data vazia ou malformada nunca quebram nem caem no fallback", () => {
  const lixo = [
    {},
    { valor: "x", valor_parcela: null, parcela_atual: "a", n_parcelas: {}, proxima_cobranca: 5 },
    { proximas_cobrancas: "nao e lista", mes: 202609, mes_termino: 7, cancelada_em: {}, total_mensal: NaN },
    { proximas_cobrancas: [null, 3, { nome: {}, data: 9, dias: "x", valor: "y" }], cartao_ou_forma: ["a"] },
  ];
  for (const t of ["assinatura", "compra_parcelada", "resumo_financeiro_recorrente"]) {
    assert.ok(Cards.temRenderizador(t), t);
    for (const data of lixo) {
      assert.doesNotThrow(() => Cards.renderizarCardHTML({ type: t, data }), t);
      assert.doesNotMatch(Cards.renderizarCardHTML({ type: t, data }), /card-contrato-fallback/, t);
    }
  }
});

test("os 3 tipos escapam HTML em todo texto (nome/descricao/cartao/categoria/label)", () => {
  const mal = '<img src=x onerror="alert(1)">';
  const htmls = [
    Cards.renderizarCardHTML({ type: "assinatura", data: { nome: mal, valor: 10, cartao_ou_forma: mal, categoria: mal } }),
    Cards.renderizarCardHTML({ type: "compra_parcelada", data: { descricao: mal, valor_parcela: 10, cartao: mal } }),
    Cards.renderizarCardHTML({ type: "resumo_financeiro_recorrente", data: { proximas_cobrancas: [{ nome: mal, label: mal, data: "2026-10-01" }] } }),
  ];
  for (const h of htmls) assert.ok(!h.includes("<img"), h);
});

// ---- rodape padrao (Desfazer) ---------------------------------------------------

test("assinatura e compra_parcelada ganham o botao Desfazer do rodape padrao; consulta nao traz action", () => {
  const acoes = [{ tipo: "desfazer", rotulo: "Desfazer", token: "tok_9", alvo: [] }];
  const a = Cards.renderizarCardHTML({ type: "assinatura", data: { nome: "x", valor: 10 }, actions: acoes });
  assert.match(a, /data-acao="desfazer" data-token="tok_9"/);
  const c = Cards.renderizarCardHTML({ type: "compra_parcelada", data: { descricao: "x", valor_parcela: 10 }, actions: acoes });
  assert.match(c, /data-acao="desfazer" data-token="tok_9"/);
  const r = Cards.renderizarCardHTML({ type: "resumo_financeiro_recorrente", data: { total_mensal: 1, consulta: true }, actions: [] });
  assert.doesNotMatch(r, /data-acao="desfazer"/);
});
