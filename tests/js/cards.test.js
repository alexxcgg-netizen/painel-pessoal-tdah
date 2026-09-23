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

// ---- cards simples (US-E3) ----

const AGORA = new Date(2026, 8, 23, 10, 0);

test("tarefas_criadas: checkbox funcional por id, titulo escapado, data curta", () => {
  const html = Cards.renderizarCardHTML(
    {
      type: "tarefas_criadas",
      data: {
        tarefas: [
          { id: 12, titulo: "Levar <carro>", data: "2026-09-23", hora: "14:00", concluida: false },
          { id: 13, titulo: "Rotina", recorrencia: "semanal:1", concluida: true },
          { id: 14, titulo: "Vago", quando: "essa semana" },
        ],
      },
      actions: [{ tipo: "abrir_aba", rotulo: "Abrir Tarefas", aba: "tarefas" }],
    },
    { agora: AGORA }
  );
  assert.match(html, /data-tarefa-id="12"/);
  assert.match(html, /Levar &lt;carro&gt;/);
  assert.match(html, /quarta 23 · 14:00/);
  assert.match(html, />rotina</);
  assert.match(html, />essa semana</);
  assert.match(html, /data-tarefa-id="13" checked/);
  assert.match(html, /Tarefas criadas/);
  assert.match(html, /Abrir Tarefas/);
});

test("tarefas_criadas: uma so fica no singular e lista vazia nao quebra", () => {
  assert.match(Cards.renderizarCardHTML({ type: "tarefas_criadas", data: { tarefas: [{ id: 1, titulo: "a" }] } }), /Tarefa criada/);
  assert.doesNotMatch(Cards.renderizarCardHTML({ type: "tarefas_criadas", data: {} }), /fallback/);
});

test("transacao: gasto -R$ neutro, entrada +R$ verde, linha data · meio · categoria, saldo", () => {
  const gasto = Cards.renderizarCardHTML(
    {
      type: "transacao",
      data: {
        entidade: "gasto", sentido: "saida", titulo: "Mercado", valor: 45.9, categoria: "mercado",
        data: "2026-09-23", meio: "Nubank", status: "real",
        saldo: { conta: "nubank", antes: 1000, depois: 954.1 },
      },
      actions: [],
    },
    { agora: AGORA }
  );
  assert.match(gasto, /-R\$\s?45,90/);
  assert.match(gasto, /hoje · Nubank · mercado/);
  assert.match(gasto, /R\$\s?1\.000,00 <span class="card-seta"/);
  assert.match(gasto, /R\$\s?954,10/);
  assert.match(gasto, /data-cat="mercado"/);
  assert.doesNotMatch(gasto, /card-valor-grande entrada/);

  const renda = Cards.renderizarCardHTML({
    type: "transacao",
    data: { entidade: "renda", sentido: "entrada", titulo: "Salario", valor: 3000, categoria: "salario" },
  });
  assert.match(renda, /\+R\$\s?3\.000,00/);
  assert.match(renda, /card-valor-grande entrada/);
  assert.match(renda, /Entrada registrada/);
});

test("transacao oculta (modo visitante) nunca mostra valor nem saldo", () => {
  const html = Cards.renderizarCardHTML({
    type: "transacao",
    data: { sentido: "saida", titulo: "Presente", oculto: true, categoria: "lazer", saldo: { antes: 1, depois: 2 } },
  });
  assert.match(html, /R\$ •••/);
  assert.doesNotMatch(html, /card-saldo/);
});

test("transacao planejada ganha chip", () => {
  const html = Cards.renderizarCardHTML({ type: "transacao", data: { sentido: "saida", valor: 10, status: "planejado" } });
  assert.match(html, /Gasto planejado/);
  assert.match(html, /card-chip-planejado/);
});

test("lembrete: hora grande, 'amanhã · faltam ...', Desfazer e Desperta voce no corpo", () => {
  const html = Cards.renderizarCardHTML(
    {
      type: "lembrete",
      data: { id: 3, titulo: "Renovar CMA", data: "2026-09-24", hora: "09:06", recorrente: false, despertar: false },
      actions: [
        { tipo: "desfazer", token: "tk", alvo: [] },
        { tipo: "despertar", rotulo: "Desperta você", lembrete_id: 3, ativo: false },
        { tipo: "abrir_aba", rotulo: "Abrir em Lembretes", aba: "painel" },
      ],
    },
    { agora: AGORA }
  );
  assert.match(html, /card-hora-grande">09:06</);
  assert.match(html, /amanhã · <span class="card-contagem-viva" data-contagem-alvo="[^"]+">faltam 23h 6min</);
  assert.equal(html.match(/data-acao="desfazer"/g).length, 1);
  assert.match(html, /data-acao="despertar" data-lembrete-id="3" aria-pressed="false"/);
  assert.match(html, /Abrir em Lembretes/);
});

test("lembrete sem hora mostra o dia em destaque e conta ate 09:00", () => {
  const html = Cards.renderizarCardHTML(
    { type: "lembrete", data: { titulo: "Seguro", data: "2026-09-26", recorrente: true } },
    { agora: AGORA }
  );
  assert.match(html, /card-hora-grande">26 set</);
  assert.match(html, /faltam 2 dias|faltam 3 dias/);
  assert.match(html, /repete todo ano/);
});

test("meta: 'R$ 9.000,00 de R$ 15.000,00', barra 60%, faltam, data planejada", () => {
  const html = Cards.renderizarCardHTML({
    type: "meta",
    data: { titulo: "Reserva", valor_guardado: 9000, valor_alvo: 15000, percentual: 60, falta: 6000, prazo: "2026-12-22" },
  });
  assert.match(html, /R\$\s?9\.000,00<\/strong> de R\$\s?15\.000,00/);
  assert.match(html, /width:60\.0%/);
  assert.match(html, /<strong>60%<\/strong> da meta · faltam R\$\s?6\.000,00/);
  assert.match(html, /Data planejada: 22 dez 2026/);
});

test("meta oculta mostra percentual mas nao valor", () => {
  const html = Cards.renderizarCardHTML({ type: "meta", data: { titulo: "Carro", percentual: 25, oculto: true } });
  assert.match(html, /R\$ •••<\/strong> de R\$ •••/);
  assert.match(html, /25%/);
  assert.doesNotMatch(html, /\d\.\d{3},\d{2}/);
});

test("meta sem percentual calcula e limita a 100%", () => {
  const html = Cards.renderizarCardHTML({ type: "meta", data: { titulo: "x", valor_guardado: 300, valor_alvo: 200 } });
  assert.match(html, /width:100\.0%/);
  assert.match(html, /completa/);
});

test("resumo_final: linhas em seta + linha recolhivel com passos", () => {
  const html = Cards.renderizarCardHTML(
    {
      type: "resumo_final",
      data: {
        linhas: [{ modulo: "Finanças", texto: "1 gasto registrado" }, { modulo: "Tarefas", texto: "2 tarefas criadas" }],
        passos_total: 13, duracao_ms: 31000, modulos: ["Tarefas", "Finanças", "Hábitos"],
      },
    },
    { passos: [{ modulo: "Tarefas", descricao: "Criou <x>", ms: 12 }, { modulo: "Saúde", descricao: "falhou", ms: 3, erro: true }] }
  );
  assert.match(html, /→<\/span><span><strong>Finanças:<\/strong> 1 gasto registrado/);
  assert.match(html, /<summary>13 passos · 31 s · Tarefas, Finanças, Hábitos<\/summary>/);
  assert.match(html, /Criou &lt;x&gt;/);
  assert.match(html, /<li class="erro">/);
});

test("resumo_final sem passos no contexto mostra a linha sem recolher", () => {
  const html = Cards.renderizarCardHTML({ type: "resumo_final", data: { linhas: [], passos_total: 1, duracao_ms: 400 } });
  assert.match(html, /card-passos-resumo">1 passo · 400 ms</);
});

test("todos os types simples registrados", () => {
  for (const t of ["tarefas_criadas", "transacao", "lembrete", "meta", "resumo_final"]) {
    assert.ok(Cards.temRenderizador(t), t);
  }
});
