// 4a leva (2026-10-15): vespera_voo + projecao (cards-aviacao.js) e documento_validade /
// compras_previsao / assinatura_subiu (cards-automacao.js). Renderizadores puros.
const test = require("node:test");
const assert = require("node:assert");
const Cards = require("../../static/js/cards.js");
const Aviacao = require("../../static/js/cards-aviacao.js");
const Automacao = require("../../static/js/cards-automacao.js");
require("../../static/js/cards-vivos.js");

const AGORA = new Date(2026, 9, 15, 20, 30);
const card = (type, data) => Cards.renderizarCardHTML({ type, id: "x1", data, actions: [] }, { agora: AGORA });

const VESPERA = {
  id: 7, data: "2026-10-16", hora: "08:00", rota: null, icao: "SSBL", acordar: "06:15", sair: "07:00",
  chegar: "07:15", pouso: "09:00", trajeto_min: 20, arrumar_min: 45, antecedencia_min: 45,
  mochila: [{ texto: "CIV e CMA", feito: true }, { texto: "Headset", feito: false }, { texto: "Carta", feito: false }],
};

test("vespera_voo: acorda grande, linha de 4 paradas, TAF na janela e mochila marcavel", () => {
  const h = card("vespera_voo", VESPERA);
  assert.match(h, /Véspera do voo/);
  assert.match(h, /class="vv-despertador"/);
  assert.match(h, /<span class="vv-hero-rot">Acorda<\/span><b class="vivo-num">06:15<\/b>/);
  // 8 h de sono antes de acordar (volta pro dia anterior)
  assert.match(h, /na cama até <b class="vivo-num">22:15<\/b>/);
  assert.match(card("vespera_voo", { ...VESPERA, acordar: "05:30" }), /na cama até <b class="vivo-num">21:30<\/b>/);
  assert.match(card("vespera_voo", { ...VESPERA, mochila: VESPERA.mochila.map((m) => ({ ...m, feito: true })) }), /vv-conta vivo-num completa[^>]*>mochila fechada/);
  assert.match(h, /class="sd-linha" style="--n:4"/);
  assert.match(h, /chega SSBL/);
  assert.match(h, /data-voo-tempo="7"/);
  assert.match(h, /data-mochila-voo="7"/);
  assert.strictEqual((h.match(/data-acao="mochila_item"/g) || []).length, 3);
  assert.match(h, /<li class="marcado"[^>]*><button[^>]*aria-pressed="true"[^>]*>.*CIV e CMA/);
  assert.match(h, /1 de 3/);
  assert.match(h, /20 min<\/b> de carro/);
  assert.match(h, /voo local · SSBL/);
});

test("vespera_voo: sem hora ou acordar invalido nao renderiza; escapa texto", () => {
  assert.doesNotMatch(card("vespera_voo", { ...VESPERA, hora: null }), /vv-hero/);
  assert.doesNotMatch(card("vespera_voo", { ...VESPERA, acordar: "6h" }), /vv-hero/);
  const h = card("vespera_voo", { ...VESPERA, mochila: [{ texto: "<img src=x onerror=1>", feito: false }] });
  assert.doesNotMatch(h, /<img/);
});

test("vespera_voo: voo longe (mais de 30 h) nao pede TAF", () => {
  assert.doesNotMatch(card("vespera_voo", { ...VESPERA, data: "2026-10-18" }), /data-voo-tempo/);
});

const PROJ = { ritmo_h_semana: 2.1, voos_semana: 1.6, horas_por_voo: 1.3, falta_h: 40.5, meta_horas: 150,
  data_meta: "2027-02-10", data_meta_mais_um: "2026-12-20", janela_dias: 60 };

test("projecao: texto com ritmo, mes da meta e cenario de 1 voo a mais", () => {
  const t = Aviacao.textoProjecao(PROJ);
  assert.strictEqual(t, "No ritmo dos últimos 2 meses (2,1 h/semana), os 150 h chegam lá por fev 2027. Com 1 voo a mais por semana: dez 2026.");
  assert.match(Aviacao.textoProjecao({ ...PROJ, data_meta: null, data_meta_mais_um: null }), /mais de 5 anos\.$/);
  assert.strictEqual(Aviacao.textoProjecao(null), "");
  assert.strictEqual(Aviacao.projecaoHTML(undefined), "");
});

test("projecao aparece no voo_agendado, voo_horas e voo_resumo", () => {
  const ag = card("voo_agendado", { id: 3, data: "2026-10-20", hora: "09:00", paradas: [{ icao: "SSBL" }, { icao: "SBJV" }], projecao: PROJ });
  assert.match(ag, /class="va-proj"/);
  // regua: no ritmo atual a meta fica no fim; +1 voo/semana em ritmo/(ritmo + h por voo) do caminho
  assert.match(ag, /va-proj-mais" style="--pos:0\.618"/);
  assert.match(ag, /va-proj-ritmo" style="--pos:1\.000"/);
  assert.match(ag, /faltam <b class="vivo-num">40,5 h/);
  assert.match(Aviacao.projecaoHTML({ ...PROJ, data_meta: null, data_meta_mais_um: null }), /5\+ anos/);
  const vh = card("voo_horas", { id: 3, data: "2026-10-15", projecao: PROJ });
  assert.match(vh, /fev 2027/);
  const vr = card("voo_resumo", { total_min: 3000, voos: 30, meta_horas: 150, meta_definida: true, projecao: PROJ });
  assert.match(vr, /class="va-proj"/);
  assert.doesNotMatch(card("voo_resumo", { total_min: 3000, voos: 30, projecao: null }), /va-proj/);
});

test("documento_validade: anel, marco atual e frase pelo prazo recalculado na hora", () => {
  const h = card("documento_validade", { id: 4, titulo: "Renovar CMA", vence: "2026-11-10", dias: 26, marco: 30, recorrente: true });
  assert.match(h, /data-nivel="atencao"/);
  assert.match(h, /<b class="vivo-num" data-contar-de="60" data-contar-ate="26">26<\/b><small>dias/);
  assert.match(h, /dv-marco chegou atual"><i><\/i>30 d/);
  assert.match(h, /dv-marco"><i><\/i>7 d/);
  assert.match(h, /renova todo ano/);
  assert.match(h, /data-acao="doc_agendar" data-titulo="Renovar CMA"/);
  assert.match(card("documento_validade", { id: 4, titulo: "CNH", vence: "2026-10-19", marco: 7 }), /data-nivel="urgente"/);
  assert.match(card("documento_validade", { id: 4, titulo: "CNH", vence: "2026-10-10", marco: 7 }), /venceu/);
  assert.doesNotMatch(card("documento_validade", { id: 4, titulo: "CNH" }), /dv-carteira/);
});

test("documento: frase por faixa", () => {
  assert.strictEqual(Automacao.fraseDocumento(45).nivel, "folga");
  assert.strictEqual(Automacao.fraseDocumento(30).nivel, "atencao");
  assert.strictEqual(Automacao.fraseDocumento(7).nivel, "urgente");
  assert.match(Automacao.fraseDocumento(0).texto, /hoje/);
});

test("compras_previsao: ate 4 itens, ciclo e botoes por item", () => {
  const itens = ["café", "leite", "arroz", "ovos", "papel"].map((item, k) => ({
    item, chave: item, intervalo_dias: 10, ultima: "2026-10-06", prevista: "2026-10-16", dias: k - 1,
  }));
  const h = card("compras_previsao", { itens });
  assert.strictEqual((h.match(/class="cp-item"/g) || []).length, 4);
  assert.strictEqual((h.match(/data-acao="compra_lista"/g) || []).length, 4);
  assert.strictEqual((h.match(/data-acao="compra_adiar"/g) || []).length, 4);
  assert.match(h, /acabou há 1 dia/);
  assert.match(h, /cp-quando ja">acaba hoje/);
  assert.match(h, /a cada ~10 dias · última 6 out/);
  assert.match(h, /--passou:1\.000/);
  assert.match(h, /class="tx-cupom cp-cupom"/);
  assert.match(h, /cp-total" data-total="4">0\/4/);
  assert.doesNotMatch(card("compras_previsao", { itens: [] }), /cp-lista/);
});

test("assinatura_subiu: riscado -> novo, pct, botoes; visitante esconde valor e botoes", () => {
  const h = card("assinatura_subiu", { descricao: "Netflix", categoria: "assinaturas", de: 39.9, para: 44.9, pct: 13 });
  assert.match(h, /as-velha.*<s class="vivo-num">R\$\s39,90<\/s>/);
  assert.match(h, /as-nova.*data-contar-de="39.9" data-contar-ate="44.9" data-contar-fmt="moeda">R\$\s44,90/);
  assert.match(h, /\+13%/);
  assert.match(h, /R\$\s5,00<\/b> a mais por mês — <b class="vivo-num">R\$\s60,00<\/b> num ano/);
  assert.match(h, /data-acao="assin_cancelar" data-descricao="Netflix"/);
  assert.match(h, /data-acao="assin_manter"/);
  const o = card("assinatura_subiu", { descricao: "Netflix", oculto: true });
  assert.match(o, /modo visitante/);
  assert.doesNotMatch(o, /data-acao=/);
  assert.doesNotMatch(o, /39,90/);
});

// ---- despertador pedido no chat (2026-10-16)
test("despertador: hora grande, botão que abre o Atalho e só esse link de atalho passa", () => {
  const h = card("despertador", { hora: "07:00", data: "2026-10-16", pedida: null });
  assert.match(h, /Despertador/);
  assert.match(h, /<span class="vv-hero-rot">Acorda<\/span><b class="vivo-num">07:00<\/b>/);
  assert.match(h, /amanhã, sexta 16/);

  // um compromisso pediu antes: a hora do alarme muda e o card diz por quê
  const antes = card("despertador", { hora: "06:15", data: "2026-10-16", pedida: "07:00" });
  assert.match(antes, /06:15/);
  assert.match(antes, /pede antes das 07:00/);

  const link = (url) => Cards.renderizarCardHTML(
    { type: "despertador", id: "x1", data: { hora: "07:00", data: "2026-10-16" }, actions: [{ tipo: "abrir_link", rotulo: "Pôr no despertador do iPhone", url }] },
    { agora: AGORA });
  assert.match(link("shortcuts://run-shortcut?name=Despertador%20do%20Painel"), /href="shortcuts:\/\/run-shortcut\?name=Despertador%20do%20Painel"/);
  for (const url of ["shortcuts://x-callback-url/run-shortcut?name=a", "shortcuts://run-shortcut?name=a&input=text&x=<b>", "javascript:alert(1)", "shortcuts://run-shortcut?name="]) {
    assert.ok(!link(url).includes("card-btn-link"), url);
  }

  // dado quebrado nunca derruba o histórico
  assert.doesNotThrow(() => card("despertador", { hora: "7", data: "x" }));
  assert.doesNotMatch(card("despertador", { hora: "7", data: "x" }), /Acorda/);
});
