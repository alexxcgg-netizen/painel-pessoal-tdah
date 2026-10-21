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

test("tarefas_criadas com aperto: lupa de 3h, faixa entre os inicios, botao com a sugestao", () => {
  const card = (aperto, agora = AGORA) =>
    Cards.renderizarCardHTML({
      type: "tarefas_criadas",
      data: {
        tarefas: [{ id: 3, titulo: "Consulta com tricologista", data: "2026-09-23", hora: "09:30" }],
        dia: "2026-09-23",
        aperto,
        agenda_do_dia: [{ id: 1, titulo: "Mikael", hora: "09:00" }, { id: 3, titulo: "Consulta com tricologista", hora: "09:30", nova: true }],
      },
    }, { agora });
  const h = card({ id: 1, titulo: "<Mikael>", hora: "09:00", sugestao: "08:30" }, new Date(2026, 8, 23, 8, 20));
  assert.match(h, /ap-lupa/);
  assert.match(h, />08h<.*>09h<.*>10h<.*>11h</); // janela comeca 1h antes da primeira
  assert.match(h, /ap-faixa" style="left:33\.33%;width:16\.67%/);
  assert.match(h, /ap-bloco l1 outra" style="left:33\.33%/);
  assert.match(h, /ap-bloco l2 nova" style="left:50\.00%;width:33\.33%"><span>nova · 9h30/);
  assert.match(h, /ap-agora" style="left:11\.11%/);
  assert.match(h, /<b>&lt;Mikael&gt;<\/b> é às 9h — 30 min antes dessa/);
  assert.match(h, /data-acao="aperto_mover" data-id="1" data-hora="08:30" data-ini="480">Passar &lt;Mikael&gt; pras 8h30/);
  assert.match(h, /data-acao="aperto_deixa"/);
  assert.doesNotMatch(h, /vivo-dia-lista/);

  const semSugestao = card({ id: 1, titulo: "Mikael", hora: "09:00", sugestao: null });
  assert.match(semSugestao, /ap-status/);
  assert.doesNotMatch(semSugestao, /aperto_mover/);
  assert.match(semSugestao, /ap-agora" style="left:66\.67%/);
  // linha do "agora" so no proprio dia
  assert.doesNotMatch(card({ id: 1, titulo: "Mikael", hora: "09:00", sugestao: null }, new Date(2026, 8, 22, 9, 0)), /ap-agora/);
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

test("transacao: gasto com contexto do mes vira cupom + barra do teto + 14 barrinhas", () => {
  const base = {
    entidade: "gasto", sentido: "saida", titulo: "Mercado Giassi", valor: 87.4, categoria: "mercado",
    data: "2026-09-23", status: "real",
    dias: [0, 84.3, 0, 0, 41.9, 0, 0, 120, 0, 33.5, 0, 67.8, 22, 87.4],
  };
  const html = Cards.renderizarCardHTML({
    type: "transacao",
    data: { ...base, mes: { categoria: "mercado", gasto: 456.9, antes: 369.5, limite: 900, dias_restantes: 8, sobra: 443.1, sobra_dia: 55.39 } },
  }, { agora: AGORA });
  assert.match(html, /tx-cupom/);
  assert.match(html, /Mercado Giassi/);
  assert.match(html, /23\/09\/2026/);
  assert.match(html, /class="card-valor-grande">-R\$\s?87,40/); // odometro continua achando o valor
  assert.match(html, /Mercado · setembro/);
  assert.match(html, /data-contar-moeda="456.9"/);
  assert.match(html, /de R\$\s?900/);
  assert.match(html, /tx-barra/);
  assert.doesNotMatch(html, /tx-estourou/);
  assert.equal((html.match(/style="--h:/g) || []).length, 14);
  assert.match(html, /<i class="tx-hoje" style="--h:72\.8%/); // 87,40 sobre o maior dia (120)


  const estourou = Cards.renderizarCardHTML({
    type: "transacao",
    data: { ...base, mes: { categoria: "mercado", gasto: 456.9, antes: 369.5, limite: 400, dias_restantes: 8, sobra: -56.9, sobra_dia: 0 } },
  }, { agora: AGORA });
  assert.match(estourou, /tx-estourou/);
  assert.match(estourou, /passou R\$\s?57 do teto/);

  const semTeto = Cards.renderizarCardHTML({
    type: "transacao", data: { ...base, mes: { categoria: "mercado", gasto: 456.9, antes: 369.5, limite: null, dias_restantes: 8 } },
  }, { agora: AGORA });
  assert.doesNotMatch(semTeto, /tx-barra/);
  assert.match(semTeto, /no mês/);
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

// ---- cards de visual complexo (US-E4) - dado de exemplo do docs/CARDS.md ----

test("agenda: data por extenso, barra do dia 06h-22h com o bloco, reservadas, lembrar, confirmacao + desfazer com uid", () => {
  const html = Cards.renderizarCardHTML({
    type: "agenda",
    data: {
      titulo: "Reunião com o contador", inicio: "2026-09-29T14:00", fim: "2026-09-29T15:00",
      lembrar_min_antes: 30, uid: "abc@painel", calendario: "Painel", confirmado: true,
    },
    actions: [{ tipo: "desfazer", token: "tk", alvo: [{ entidade: "evento", uid: "abc@painel" }] }],
  });
  assert.match(html, /terça, 29 de setembro, das 14:00 às 15:00/);
  // 14h-15h em 06h-22h: left = 8/16 = 50%, width = 1/16 = 6.25%
  assert.match(html, /card-dia-bloco" style="left:50\.00%;width:6\.25%"/);
  assert.match(html, />06h</);
  assert.match(html, />22h</);
  assert.match(html, /1h reservadas/);
  assert.match(html, /Lembrar 30 min antes/);
  assert.match(html, /Está na sua agenda<\/span><span class="card-sep"[^>]*>·<\/span><button[^>]*data-acao="desfazer"/);
  assert.equal(html.match(/data-acao="desfazer"/g).length, 1);
});

test("blocoDoDia corta nas bordas e sem fim assume 1h", () => {
  const b = Cards.blocoDoDia(new Date(2026, 8, 29, 5, 0), null);
  assert.equal(b.left, 0);
  assert.equal(b.minutos, 60);
  const tarde = Cards.blocoDoDia(new Date(2026, 8, 29, 21, 30), new Date(2026, 8, 29, 23, 30));
  assert.ok(tarde.left + tarde.width <= 100.0001);
  assert.equal(Cards.blocoDoDia(null, null), null);
});

test("agenda sem inicio nao quebra", () => {
  const html = Cards.renderizarCardHTML({ type: "agenda", data: { titulo: "x" } });
  assert.doesNotMatch(html, /fallback/);
  assert.match(html, /Horário a definir/);
});

test("projeto_viagem: checklist, barra com HOJE, '25% · 2/8 tarefas · 22 dez', marco, chip No rumo", () => {
  const etapas = [
    { titulo: "Passagem", feito: true, data: "2026-09-10" },
    { titulo: "Hotel", feito: true },
    ...Array.from({ length: 6 }, (_, i) => ({ titulo: `Etapa ${i + 3}`, feito: false })),
  ];
  const html = Cards.renderizarCardHTML(
    {
      type: "projeto_viagem",
      data: {
        titulo: "Viagem pra Gramado", origem: "viagem", inicio: "2026-09-01", prazo: "2026-12-22",
        etapas, proximo_marco: { titulo: "Reservar carro", data: "2026-10-15" }, status: "no_rumo",
      },
      actions: [{ tipo: "abrir_aba", rotulo: "Abrir Projetos", aba: "vida" }],
    },
    { agora: new Date(2026, 8, 23, 12, 0) }
  );
  assert.match(html, /<strong>25%<\/strong> · 2\/8 tarefas · 22 dez/);
  assert.match(html, /class="card-hoje" style="left:\d+\.\d+%"><span>HOJE<\/span>/);
  assert.match(html, /Próximo marco: <strong>Reservar carro<\/strong> · 15 out/);
  assert.match(html, /No rumo/);
  assert.match(html, /\+3 etapas/);
  assert.match(html, />Viagem</);
  assert.match(html, /Abrir Projetos/);
});

test("projeto_viagem: linha do tempo de planejamento (US-F11) so aparece quando o backend manda marcos_planejamento", () => {
  const semMarcos = Cards.renderizarCardHTML({
    type: "projeto_viagem",
    data: { titulo: "Projeto generico", origem: "projeto", etapas: [], status: "no_rumo" },
  });
  assert.doesNotMatch(semMarcos, /card-marcos-planejamento/);

  const comMarcos = Cards.renderizarCardHTML(
    {
      type: "projeto_viagem",
      data: {
        titulo: "Viagem pra Lisboa",
        origem: "viagem",
        etapas: [],
        status: "no_rumo",
        marcos_planejamento: [
          { chave: "passagem", titulo: "Melhor janela pra comprar a passagem", data: "2026-08-27", dias_antes: 120 },
          { chave: "documento", titulo: "Conferir visto/passaporte valido", data: "2026-09-26", dias_antes: 90 },
          { chave: "checkin", titulo: "Check-in online libera", data: "2026-12-23", dias_antes: 2 },
        ],
        aviso_regra_pratica: "Regra pratica generica - nao e preco em tempo real.",
      },
      actions: [],
    },
    { agora: new Date(2026, 8, 23, 12, 0) }
  );
  assert.match(comMarcos, /card-marcos-planejamento/);
  assert.match(comMarcos, /Regra pratica generica - nao e preco em tempo real\./);
  assert.match(comMarcos, /Melhor janela pra comprar a passagem/);
  assert.match(comMarcos, /class="item hoje-marcador"[^>]*><span class="item-titulo">HOJE<\/span>/);
  // 2026-09-23: passagem (27 ago) e documento (26 set) ja passaram, checkin (23 dez) nao
  const idxPassagem = comMarcos.indexOf("Melhor janela");
  const idxHoje = comMarcos.indexOf("HOJE");
  const idxCheckin = comMarcos.indexOf("Check-in online libera");
  assert.ok(idxPassagem < idxHoje && idxHoje < idxCheckin, "HOJE deve ficar entre os marcos passados e os futuros");
  assert.match(comMarcos, /class="item passado">.*Melhor janela/s);
  assert.match(comMarcos, /class="item proximo">.*Check-in online libera/s);
});

test("progressoProjeto usa os campos prontos do backend quando vierem", () => {
  const p = Cards.progressoProjeto({ etapas: [], percentual: 40, feitas: 4, total: 10, hoje_fracao: 0.5 });
  assert.deepEqual(p, { pct: 40, feitas: 4, total: 10, hoje: 0.5 });
  const sem = Cards.progressoProjeto({ etapas: [{ feito: true }, { feito: false }] });
  assert.equal(sem.pct, 50);
  assert.equal(sem.hoje, null);
});

test("saude_treino: totais, lista, grafico SVG por atividade, chip Registrado", () => {
  const html = Cards.renderizarCardHTML({
    type: "saude_treino",
    data: {
      periodo: "últimos 7 dias",
      sessoes: [
        { atividade: "Corrida", fonte: "Apple Saúde", minutos: 40, data: "2026-09-22" },
        { atividade: "Musculação", fonte: "Painel", minutos: 50, data: "2026-09-21" },
        { atividade: "Corrida", fonte: "Apple Saúde", minutos: 20, data: "2026-09-19" },
      ],
      registrado: true,
    },
  });
  assert.match(html, /Sessões registradas: <strong>3<\/strong> · Tempo de atividade: <strong>1h50<\/strong>/);
  assert.match(html, /<svg class="card-grafico"/);
  assert.equal(html.match(/class="card-graf-barra"/g).length, 2); // agrupado por atividade
  assert.match(html, /Registrado/);
  assert.match(html, /Apple Saúde · terça 22/);
});

test("minutosPorAtividade agrupa e ordena do maior pro menor", () => {
  assert.deepEqual(Cards.minutosPorAtividade([{ atividade: "A", minutos: 10 }, { atividade: "B", minutos: 30 }, { atividade: "A", minutos: 25 }]), [
    { atividade: "A", minutos: 35 },
    { atividade: "B", minutos: 30 },
  ]);
});

test("sugestao: horario grande, duracao, caixa 'Com a sua rotina em mente'", () => {
  const html = Cards.renderizarCardHTML({
    type: "sugestao",
    data: { titulo: "Estudar meteorologia", inicio: "2026-09-24T19:00", duracao_min: 45, porque: "Você rende melhor <à noite>." },
  });
  assert.match(html, /card-hora-grande">19:00</);
  assert.match(html, /quinta, 24 de setembro · 45 min \(até 19:45\)/);
  assert.match(html, /Com a sua rotina em mente/);
  assert.match(html, /Você rende melhor &lt;à noite&gt;\./);
  assert.doesNotMatch(Cards.renderizarCardHTML({ type: "sugestao", data: { titulo: "x" } }), /rotina em mente/);
});

test("habito: meta, 7 circulos S T Q Q S S D (hoje tracejado, feitos acesos), ativos 4 -> 5, contexto", () => {
  const semana = ["2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25", "2026-09-26", "2026-09-27"].map((d, i) => ({
    data: d,
    feito: i < 2,
  }));
  const html = Cards.renderizarCardHTML({
    type: "habito",
    data: {
      nome: "Meditar", meta: "15 min", frequencia: "qualquer dia conta", horario: "08:00", hoje: "2026-09-23",
      semana, ativos_antes: 4, ativos_depois: 5, contexto: "Encaixei logo depois do café.",
    },
  });
  assert.match(html, /15 min · qualquer dia conta · às 8h/);
  const letras = [...html.matchAll(/card-habito-letra" aria-hidden="true">(\w)</g)].map((m) => m[1]).join("");
  assert.equal(letras, "STQQSSD");
  assert.equal(html.match(/card-habito-dia feito/g).length, 2);
  assert.equal(html.match(/ hoje"/g).length, 1);
  assert.match(html, /quarta \(hoje\): não feito/);
  assert.match(html, /Hábitos ativos: 4 <span class="card-seta"[^>]*>→<\/span> <strong>5<\/strong>/);
  assert.match(html, /Encaixei logo depois do café\./);
});

test("semanaHabito completa 7 dias e usa o relogio quando nao vem 'hoje'", () => {
  const dias = Cards.semanaHabito({ semana: [{ feito: true }] }, new Date(2026, 8, 27, 10, 0)); // domingo
  assert.equal(dias.length, 7);
  assert.equal(dias[0].feito, true);
  assert.equal(dias[6].hoje, true);
  assert.equal(Cards.horaCurta("08:30"), "8h30");
  assert.equal(Cards.horaCurta("x"), "");
});

test("types complexos com data vazia nunca viram excecao", () => {
  for (const t of ["agenda", "projeto_viagem", "saude_treino", "sugestao", "habito"]) {
    assert.ok(Cards.temRenderizador(t), t);
    assert.doesNotThrow(() => Cards.renderizarCardHTML({ type: t, data: {} }));
    assert.doesNotMatch(Cards.renderizarCardHTML({ type: t, data: {} }), /card-contrato-fallback/, t);
    assert.doesNotThrow(() => Cards.renderizarCardHTML({ type: t, data: { etapas: "x", sessoes: 5, semana: null } }));
  }
});

// ---- desfazer + link (US-E5) ----

test("card com desfeito=true (vindo do historico) nasce marcado", () => {
  const html = Cards.renderizarCardHTML({
    type: "tarefas_criadas",
    desfeito: true,
    data: { tarefas: [{ id: 1, titulo: "x" }] },
    actions: [{ tipo: "desfazer", token: "t" }],
  });
  assert.match(html, /card-contrato-tarefas_criadas card-desfeito"/);
  assert.match(html, /data-desfeito="1"/);
});

test("abrir_aba leva aba e destaque do item; sem destaque nao inventa atributo", () => {
  assert.match(
    Cards.acaoHTML({ tipo: "abrir_aba", rotulo: "Abrir no extrato", aba: "gastos", destaque: { entidade: "gasto", id: 5 } }),
    /data-aba="gastos" data-destaque-entidade="gasto" data-destaque-id="5"/
  );
  assert.doesNotMatch(Cards.acaoHTML({ tipo: "abrir_aba", aba: "painel" }), /destaque/);
  assert.equal(Cards.acaoHTML({ tipo: "abrir_aba" }), ""); // sem aba: nada
  assert.equal(Cards.acaoHTML({ tipo: "desfazer" }), ""); // sem token: nada
});

// ---- saude_dia (US-E7, aditivo) ----

test("saude_dia: copos em destaque, gotas acesas, chips de passos/sono/treino, chip Registrado", () => {
  const html = Cards.renderizarCardHTML({
    type: "saude_dia",
    id: "c1",
    data: { data: "2026-09-23", agua_copos: 3, passos: 8240, sono_horas: 7.5, treino_min: 45, registrado: "agua" },
    actions: [],
  });
  assert.match(html, /card-contrato-saude_dia/);
  assert.match(html, /card-hora-grande">3</);
  assert.match(html, /copos de água/);
  assert.equal((html.match(/card-gota cheia/g) || []).length, 3);
  assert.equal((html.match(/class="card-gota[ "]/g) || []).length, 8);
  assert.match(html, /card-gota cheia nova/);
  assert.match(html, /8,2 mil passos/);
  assert.match(html, /Sono 7h30/);
  assert.match(html, /Treino 45 min/);
  assert.match(html, /Registrado/);
});

test("saude_dia: mais de 8 copos mostra +N; 1 copo no singular; sem registro sem chip", () => {
  const muitos = Cards.renderizarCardHTML({ type: "saude_dia", data: { agua_copos: 11 }, actions: [] });
  assert.match(muitos, /\+3/);
  const um = Cards.renderizarCardHTML({ type: "saude_dia", data: { agua_copos: 1 }, actions: [] });
  assert.match(um, /copo de água/);
  assert.ok(!um.includes("Registrado"));
});

test("saude_dia com data vazia/lixo nunca vira excecao nem fallback", () => {
  for (const data of [{}, { agua_copos: "<b>x</b>", passos: -1, sono_horas: "oi" }, { agua_copos: NaN }]) {
    const html = Cards.renderizarCardHTML({ type: "saude_dia", data, actions: [] });
    assert.ok(!html.includes("card-contrato-fallback"), html);
    assert.ok(!html.includes("<b>x</b>"));
  }
});

test("fmtPassos/fmtSono formatam e ignoram lixo", () => {
  assert.equal(Cards.fmtPassos(950), "950 passos");
  assert.equal(Cards.fmtPassos(12000), "12 mil passos");
  assert.equal(Cards.fmtPassos(null), "");
  assert.equal(Cards.fmtSono(8), "Sono 8h");
  assert.equal(Cards.fmtSono(0), "");
});

test("meta vinda de consulta (data.consulta) nao diz 'Meta criada'", () => {
  const base = { titulo: "Reserva", valor_guardado: 10, valor_alvo: 100, percentual: 10 };
  assert.match(Cards.renderizarCardHTML({ type: "meta", data: base, actions: [] }), /Meta criada/);
  const html = Cards.renderizarCardHTML({ type: "meta", data: { ...base, consulta: true }, actions: [] });
  assert.ok(!html.includes("Meta criada"));
  assert.match(html, /<span>Meta<\/span>/);
});

test("projeto_viagem sem etapa nao mostra '0/0 tarefas'", () => {
  const html = Cards.renderizarCardHTML({
    type: "projeto_viagem",
    data: { origem: "viagem", titulo: "Viagem pra Gramado", etapas: [], prazo: "2026-12-15", total: 0, feitas: 0, percentual: 0 },
    actions: [],
  });
  assert.ok(!html.includes("0/0"));
  assert.match(html, /Sem checklist ainda/);
});

// ---- modo visitante nos cards de saude (revisao da Fase 6) ----

test("saude_dia/saude_treino com oculto: so o aviso, nenhum numero de saude", () => {
  const dia = Cards.renderizarCardHTML({
    type: "saude_dia",
    data: { data: "2026-09-23", oculto: true, agua_copos: 3, passos: 4321, sono_horas: 3.5 },
    actions: [],
  });
  assert.match(dia, /ocultos no modo visitante/);
  assert.ok(!dia.includes("4,3 mil"), dia);
  assert.ok(!/Sono/.test(dia), dia);
  assert.ok(!dia.includes("card-gota"), dia);
  const treino = Cards.renderizarCardHTML({
    type: "saude_treino",
    data: { periodo: "últimos 7 dias", oculto: true, sessoes: [{ atividade: "Perna", minutos: 50 }] },
    actions: [],
  });
  assert.match(treino, /ocultos no modo visitante/);
  assert.ok(!treino.includes("Perna"), treino);
  assert.ok(!treino.includes("card-contrato-fallback"), treino);
});

test("rota: destino, km/tempo, paradas e botao do Google Maps (so link do Maps)", () => {
  const url = "https://www.google.com/maps/dir/?api=1&travelmode=driving&destination=Aeroclube";
  const card = {
    type: "rota",
    data: {
      paradas: [
        { nome: "Rua Exemplo, 10", endereco: "Rua Exemplo, 10, Brusque - SC" },
        { nome: "Aeroclube de Blumenau", endereco: "R. Ernst Kaestner, 1255 - Itoupava Central, Blumenau - SC" },
        { nome: "Rua Exemplo, 10", endereco: "Rua Exemplo, 10, Brusque - SC" },
      ],
      distancia_km: 118.6,
      duracao_min: 136,
    },
    actions: [{ tipo: "abrir_link", rotulo: "Abrir no Google Maps", url }],
  };
  const html = Cards.renderizarCardHTML(card);
  assert.ok(!html.includes("card-contrato-fallback"), html);
  assert.match(html, /Rota · ida e volta/);
  assert.match(html, /Aeroclube de Blumenau/);
  assert.match(html, /119 km · 2h16/);
  assert.match(html, /href="https:\/\/www\.google\.com\/maps\/dir\/\?api=1&amp;travelmode=driving/);
  assert.match(html, /target="_blank"/);

  const deOndeEstou = Cards.renderizarCardHTML({ ...card, data: { ...card.data, partir_de_onde_estou: true } });
  assert.match(deOndeEstou, /Onde você está/);

  const malicioso = Cards.renderizarCardHTML({ ...card, actions: [{ tipo: "abrir_link", rotulo: "x", url: "javascript:alert(1)" }] });
  assert.ok(!malicioso.includes("javascript:"), malicioso);
  const outroSite = Cards.renderizarCardHTML({ ...card, actions: [{ tipo: "abrir_link", rotulo: "x", url: "https://evil.example/maps/" }] });
  assert.ok(!outroSite.includes("evil.example"), outroSite);
  assert.match(Cards.renderizarCardHTML({ type: "rota", data: { paradas: [] } }), /card-contrato-fallback/);
});

test("local do GPS aparece na tarefa e no lembrete (e some quando nao tem)", () => {
  const tarefa = Cards.renderizarCardHTML({
    type: "tarefas_criadas",
    data: { tarefas: [{ id: 1, titulo: "comprar pão", local: "Rua Exemplo, Centro, Blumenau - SC" }] },
    actions: [],
  });
  assert.match(tarefa, /card-local/);
  assert.match(tarefa, /Rua Exemplo, Centro, Blumenau - SC/);
  const semLocal = Cards.renderizarCardHTML({ type: "tarefas_criadas", data: { tarefas: [{ id: 1, titulo: "x" }] }, actions: [] });
  assert.ok(!semLocal.includes("card-local"), semLocal);
  const lembrete = Cards.renderizarCardHTML({
    type: "lembrete",
    data: { id: 1, titulo: "voltar aqui", data: "2026-10-20", local: "<b>Rua</b>" },
    actions: [],
  });
  assert.match(lembrete, /&lt;b&gt;Rua&lt;\/b&gt;/); // escapado
});

test("rota com transito: +N min, trecho parado (sem afirmar a causa), trecho no mapa e botao do Waze", () => {
  const card = {
    type: "rota",
    data: {
      paradas: [
        { nome: "Casa", endereco: "Rua Exemplo, 10, Brusque - SC" },
        { nome: "Aeroclube de Blumenau", endereco: "Blumenau - SC" },
      ],
      distancia_km: 40,
      duracao_min: 62,
      transito_min: 14,
      lentidao: [
        { nivel: "parado", frase: "Parado na BR-470, Gaspar (2 km) - pode ser acidente ou blitz" },
        { nivel: "qualquer", frase: "ignorado" },
      ],
      traco: {
        w: 320, h: 200,
        pontos: [[20, 20], [160, 100], [300, 180]],
        paradas: [[20, 20], [300, 180]],
        lentos: [{ nivel: "parado", pontos: [[100, 60], [160, 100]] }, { nivel: "x", pontos: [[1, 1], [2, 2]] }],
      },
    },
    actions: [
      { tipo: "abrir_link", rotulo: "Abrir no Google Maps", url: "https://www.google.com/maps/dir/?api=1&destination=x" },
      { tipo: "abrir_link", rotulo: "Ir com Waze", url: "https://waze.com/ul?ll=-26.85000,-49.10000&navigate=yes" },
    ],
  };
  const html = Cards.renderizarCardHTML(card);
  assert.ok(!html.includes("card-contrato-fallback"), html);
  assert.match(html, /\+14 min de trânsito/);
  assert.match(html, /card-rota-lento--parado/);
  assert.match(html, /pode ser acidente ou blitz/);
  assert.ok(!html.includes("ignorado"), html);
  assert.match(html, /vivo-rota-lento--parado" d="M100 60 L160 100"/);
  assert.ok(!html.includes("vivo-rota-lento--x"), html);
  assert.match(html, /href="https:\/\/waze\.com\/ul\?ll=-26\.85000,-49\.10000&amp;navigate=yes"/);
  assert.match(html, /Ir com Waze/);

  // transito pequeno (< 3 min) nao aparece; Waze falso (outro dominio / sem /ul?) nao vira botao
  const pouco = Cards.renderizarCardHTML({ ...card, data: { ...card.data, transito_min: 2, lentidao: [] } });
  assert.ok(!pouco.includes("de trânsito"), pouco);
  for (const url of ["https://waze.com.evil.example/ul?x", "https://waze.com/live-map", "http://waze.com/ul?ll=1,2"]) {
    const falso = Cards.renderizarCardHTML({ ...card, actions: [{ tipo: "abrir_link", rotulo: "Waze", url }] });
    assert.ok(!falso.includes("card-btn-link"), url);
  }
});

test("rota com tempo no caminho: barra pintada por trecho, so os trechos ruins na lista, tipo estranho fora", () => {
  const base = {
    paradas: [{ nome: "Casa", endereco: "Rua Exemplo, 10" }, { nome: "Curitiba", endereco: "Curitiba - PR" }],
    distancia_km: 200,
    duracao_min: 180,
    traco: {
      w: 320, h: 200, pontos: [[20, 20], [160, 100], [300, 180]], paradas: [[20, 20], [300, 180]],
      tempo: [{ nivel: "neblina", pontos: [[160, 100], [300, 180]] }, { nivel: "x", pontos: [[1, 1], [2, 2]] }],
    },
    tempo: {
      total_km: 200, saida: "08:00",
      trechos: [
        { tipo: "ok", de_km: 0, ate_km: 40, frase: "x" },
        { tipo: "chuva", de_km: 40, ate_km: 100, frase: "Chuva do km 40 ao 100, por volta das 9h - 85% de chance" },
        { tipo: "neblina", de_km: 160, ate_km: 200, frase: "Neblina na serra <b>BR</b>, do km 160 ao 200" },
        { tipo: "tornado", de_km: 1, ate_km: 2, frase: "nao aparece" },
      ],
    },
  };
  const html = Cards.renderizarCardHTML({ type: "rota", data: base, actions: [] });
  assert.ok(!html.includes("card-contrato-fallback"), html);
  assert.match(html, /Tempo no caminho · saindo 08:00/);
  assert.match(html, /card-rota-tempo-faixa card-rota-tempo--chuva" style="left:20\.00%;width:30\.00%/);
  assert.match(html, /85% de chance/);
  assert.match(html, /Neblina na serra &lt;b&gt;BR&lt;\/b&gt;/);
  assert.ok(!html.includes("nao aparece"), html);
  assert.ok(!html.includes("card-rota-tempo--tornado"), html);
  assert.match(html, /vivo-rota-tempo card-rota-tempo--neblina" d="M160 100 L300 180"/);
  assert.ok(!html.includes("card-rota-tempo--x"), html);

  const firme = Cards.renderizarCardHTML({ type: "rota", data: { ...base, tempo: { total_km: 200, trechos: [{ tipo: "ok", de_km: 0, ate_km: 200 }] } }, actions: [] });
  assert.match(firme, /Tempo firme no caminho todo/);
  const sem = Cards.renderizarCardHTML({ type: "rota", data: { ...base, tempo: { total_km: "x" } }, actions: [] });
  assert.ok(!sem.includes("Tempo no caminho"), sem);
});
