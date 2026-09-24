// Testes da logica PURA da Caixa do assistente (static/js/secoes/assistente/caixa.js)
// - faixa compacta da aba Hoje + secao "Caixa" da aba Assistente. Sem
// navegador/DOM: so as funcoes de render/normalizacao/texto, exportadas via
// module.exports quando roda em Node (mesmo padrao de tests/js/cards.test.js
// e tests/js/visao_dia.test.js). O wiring de fetch/DOM (responder de
// verdade, o item sumir com animacao, o selo mudar na barra) e conferido a
// parte, no Playwright headless (docs/agentes/fase7-regras-faixa.md).
//
//   node --test tests/js/caixa_assistente.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const CaixaAssistente = require(path.join(__dirname, "..", "..", "static", "js", "secoes", "assistente", "caixa.js"));

// ---- textoContagem (titulo "Pendencias do assistente (N)") ----

test("textoContagem: zero pendencias", () => {
  assert.equal(CaixaAssistente.textoContagem(0), "Pendencias do assistente (0)");
});

test("textoContagem: N pendencias", () => {
  assert.equal(CaixaAssistente.textoContagem(5), "Pendencias do assistente (5)");
});

test("textoContagem: valor ausente/invalido vira 0", () => {
  assert.equal(CaixaAssistente.textoContagem(undefined), "Pendencias do assistente (0)");
  assert.equal(CaixaAssistente.textoContagem(null), "Pendencias do assistente (0)");
  assert.equal(CaixaAssistente.textoContagem("nao e numero"), "Pendencias do assistente (0)");
});

// ---- itensUrgentes (as 3 mais urgentes da faixa compacta) ----

test("itensUrgentes: corta na quantidade pedida (padrao 3)", () => {
  const itens = [{ id: 1 }, { id: 2 }, { id: 3 }, { id: 4 }, { id: 5 }];
  const top = CaixaAssistente.itensUrgentes(itens);
  assert.equal(top.length, 3);
  assert.deepEqual(top.map((i) => i.id), [1, 2, 3]);
});

test("itensUrgentes: limite customizado", () => {
  const itens = [{ id: 1 }, { id: 2 }, { id: 3 }];
  assert.equal(CaixaAssistente.itensUrgentes(itens, 1).length, 1);
  assert.equal(CaixaAssistente.itensUrgentes(itens, 10).length, 3);
});

test("itensUrgentes: lista vazia/invalida nunca lanca excecao", () => {
  assert.deepEqual(CaixaAssistente.itensUrgentes([]), []);
  assert.deepEqual(CaixaAssistente.itensUrgentes(null), []);
  assert.deepEqual(CaixaAssistente.itensUrgentes(undefined), []);
});

// ---- normalizarOpcoes (os botoes de um toque: Sim/Ainda nao/Adiar etc.) ----

test("normalizarOpcoes: lista de strings vira rotulo=valor=a propria string", () => {
  const item = { tipo: "pergunta", opcoes: ["Sim", "Ainda nao", "Adiar"] };
  assert.deepEqual(CaixaAssistente.normalizarOpcoes(item), [
    { rotulo: "Sim", valor: "Sim" },
    { rotulo: "Ainda nao", valor: "Ainda nao" },
    { rotulo: "Adiar", valor: "Adiar" },
  ]);
});

test("normalizarOpcoes: lista de {label, valor} usa os campos do objeto", () => {
  const item = { tipo: "sugestao", opcoes: [{ label: "Aceitar", valor: "aceitar" }, { label: "Nao, obrigado", valor: "recusar" }] };
  assert.deepEqual(CaixaAssistente.normalizarOpcoes(item), [
    { rotulo: "Aceitar", valor: "aceitar" },
    { rotulo: "Nao, obrigado", valor: "recusar" },
  ]);
});

test("normalizarOpcoes: sem opcoes proprias usa o padrao do tipo (pergunta)", () => {
  const item = { tipo: "pergunta", opcoes: null };
  assert.deepEqual(CaixaAssistente.normalizarOpcoes(item), [
    { rotulo: "Sim", valor: "sim" },
    { rotulo: "Nao", valor: "nao" },
    { rotulo: "Adiar", valor: "adiar" },
  ]);
});

test("normalizarOpcoes: tipo sem padrao conhecido cai em aceitar/recusar", () => {
  const item = { tipo: "tipo_desconhecido" };
  assert.deepEqual(CaixaAssistente.normalizarOpcoes(item), [
    { rotulo: "Aceitar", valor: "aceitar" },
    { rotulo: "Recusar", valor: "recusar" },
  ]);
});

test("normalizarOpcoes: opcoes vazia ([]) tambem cai no padrao do tipo", () => {
  const item = { tipo: "briefing", opcoes: [] };
  assert.deepEqual(CaixaAssistente.normalizarOpcoes(item), [{ rotulo: "Aceitar", valor: "aceitar" }]);
});

// ---- textoAtraso (aviso discreto de tick atrasado, GET /api/assistente/saude) ----

test("textoAtraso: tick em dia nao gera aviso", () => {
  assert.equal(CaixaAssistente.textoAtraso({ atrasado: false, minutos_desde_ultimo_tick: 3 }), null);
});

test("textoAtraso: sem dado de saude nao gera aviso", () => {
  assert.equal(CaixaAssistente.textoAtraso(null), null);
  assert.equal(CaixaAssistente.textoAtraso(undefined), null);
});

test("textoAtraso: atrasado com minutos conhecidos", () => {
  const texto = CaixaAssistente.textoAtraso({ atrasado: true, minutos_desde_ultimo_tick: 42.6 });
  assert.match(texto, /atrasado/);
  assert.match(texto, /43 min/); // arredonda
});

test("textoAtraso: atrasado sem nenhum tick registrado ainda", () => {
  const texto = CaixaAssistente.textoAtraso({ atrasado: true, minutos_desde_ultimo_tick: null });
  assert.match(texto, /ainda nao rodou/);
});

// ---- render da faixa compacta / lista (renderItemHTML, renderListaHTML) ----

test("renderItemHTML: mostra tipo, titulo, corpo e um botao por opcao", () => {
  const item = {
    id: 7,
    tipo: "pergunta",
    titulo: "Pagou o cartao?",
    corpo: "Vence hoje.",
    opcoes: ["Sim", "Ainda nao"],
  };
  const html = CaixaAssistente.renderItemHTML(item);
  assert.match(html, /data-item-id="7"/);
  assert.match(html, /data-tipo="pergunta"/);
  assert.match(html, /Pergunta/);
  assert.match(html, /Pagou o cartao\?/);
  assert.match(html, /Vence hoje\./);
  assert.equal((html.match(/caixa-item-opcao/g) || []).length, 2);
  assert.match(html, /data-valor="Sim"/);
  assert.match(html, /data-valor="Ainda nao"/);
});

test("renderItemHTML: sem corpo nao imprime paragrafo vazio", () => {
  const html = CaixaAssistente.renderItemHTML({ id: 1, tipo: "aviso", titulo: "Oi", corpo: "" });
  assert.ok(!html.includes("caixa-item-corpo"));
});

test("renderItemHTML: escapa HTML do titulo/corpo (sem XSS)", () => {
  const html = CaixaAssistente.renderItemHTML({
    id: 1,
    tipo: "aviso",
    titulo: '<img src=x onerror="alert(1)">',
    corpo: "<script>alert(2)</script>",
  });
  assert.ok(!html.includes("<img"));
  assert.ok(!html.includes("<script>"));
  assert.match(html, /&lt;img/);
  assert.match(html, /&lt;script&gt;/);
});

test("renderListaHTML: itens em ordem, um <li class=caixa-item> cada", () => {
  const itens = [
    { id: 1, tipo: "pergunta", titulo: "A" },
    { id: 2, tipo: "aviso", titulo: "B" },
  ];
  const html = CaixaAssistente.renderListaHTML(itens);
  assert.equal((html.match(/class="card caixa-item"/g) || []).length, 2);
  assert.ok(html.indexOf(">A<") < html.indexOf(">B<") || html.indexOf("A") < html.indexOf("B"));
});

test("renderListaHTML: lista vazia mostra mensagem (contagem zero fica visivelmente clara)", () => {
  assert.match(CaixaAssistente.renderListaHTML([]), /caixa-vazio/);
  assert.match(CaixaAssistente.renderListaHTML(null), /caixa-vazio/);
  assert.match(CaixaAssistente.renderListaHTML(undefined, { vazio: "Tudo em dia" }), /Tudo em dia/);
});

// ---- historico (resolvido, com a resposta dada) ----

test("renderHistoricoItemHTML: mostra a resposta e o texto livre quando houver", () => {
  const html = CaixaAssistente.renderHistoricoItemHTML({
    id: 3,
    tipo: "pergunta",
    titulo: "Foi ao dentista?",
    resposta: "sim",
    resposta_texto: "marquei pra sexta",
  });
  assert.match(html, /Resposta: Sim/);
  assert.match(html, /marquei pra sexta/);
});

test("renderHistoricoItemHTML: resposta customizada (nao-padrao) some sem quebrar", () => {
  const html = CaixaAssistente.renderHistoricoItemHTML({ id: 4, tipo: "sugestao", titulo: "X", resposta: "outra_opcao" });
  assert.match(html, /Resposta: outra_opcao/);
});

test("renderHistoricoHTML: vazio mostra mensagem propria", () => {
  assert.match(CaixaAssistente.renderHistoricoHTML([]), /sem historico/);
});
