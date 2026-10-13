// cards-rotina.js: fechar_dia e semana (renderizadores puros, sem DOM).
const test = require("node:test");
const assert = require("node:assert");
const Cards = require("../../static/js/cards.js");
require("../../static/js/cards-rotina.js");

function html(type, data) {
  return Cards.renderizarListaHTML([{ type, id: "r1", data, actions: [] }], { passos: [] });
}

const DIA = {
  dia: "2026-10-13", feitas: 3, mais: 0, ids_adiar: [7, 9],
  pendentes: [
    { id: 7, titulo: "Pagar boleto", hora: null, data: "2026-10-11", atrasada: true },
    { id: 9, titulo: "Ligar pro instrutor", hora: "10:30", data: "2026-10-13", atrasada: false },
  ],
  agua: { copos: 5, meta: 8 }, gasto: 42.5, voo_horas: 1.5, quiz: { respondidas: 4, acertos: 3 },
};

test("fechar_dia: anel, pendentes com checkbox e botao com os ids", () => {
  const h = html("fechar_dia", DIA);
  assert.match(h, /<b class="vivo-num">3<\/b><small>de 5<\/small>/);
  assert.match(h, /data-tarefa-id="7"/);
  assert.match(h, /desde 11 out/);
  assert.match(h, /10:30/);
  assert.match(h, /data-acao="adiar_pendentes" data-ids="7,9"/);
  assert.match(h, /Passar as 2 pra amanhã/);
  assert.match(h, /1,5 h/);
  assert.match(h, /3\/4/);
  assert.match(h, /R\$ 43/);
});

test("fechar_dia: dia limpo sem botao, visitante sem agua e gasto", () => {
  const limpo = html("fechar_dia", { ...DIA, pendentes: [], ids_adiar: [] });
  assert.match(limpo, /rt-fechar limpo/);
  assert.doesNotMatch(limpo, /adiar_pendentes/);
  const oculto = html("fechar_dia", { ...DIA, oculto: true });
  assert.doesNotMatch(oculto, /água/);
  assert.doesNotMatch(oculto, /R\$/);
});

test("fechar_dia: escapa titulo e nao quebra com dado faltando", () => {
  const h = html("fechar_dia", { ...DIA, pendentes: [{ id: 1, titulo: "<img src=x onerror=1>" }], ids_adiar: [1] });
  assert.doesNotMatch(h, /<img src=x/);
  assert.doesNotThrow(() => html("fechar_dia", { dia: "2026-10-13" }));
});

const SEMANA = {
  de: "2026-10-07", ate: "2026-10-13", meta_agua: 8, melhor_dia: "2026-10-11",
  dias: ["qua", "qui", "sex", "sáb", "dom", "seg", "ter"].map((r, i) => ({
    dia: `2026-10-${String(7 + i).padStart(2, "0")}`, rotulo: r, tarefas: i === 4 ? 6 : i, voo_h: i === 2 ? 1.2 : 0,
  })),
  agua_dia: [8, 4, 0, 8, 2, 9, 1], gasto: 300, gasto_ant: 200, tarefas: 21, tarefas_ant: 21, voo_horas: 1.2,
  observacoes: ["Domingo foi teu dia mais produtivo, 6 tarefas riscadas."],
};

test("semana: 7 colunas na escala, melhor dia, agua cheia, deltas", () => {
  const h = html("semana", SEMANA);
  assert.strictEqual((h.match(/class="rt-col[ "]/g) || []).length, 7);
  assert.match(h, /rt-col melhor" style="--i:4;--h:1\.000"/);
  assert.match(h, /--h:0\.500/);
  assert.strictEqual((h.match(/rt-col-agua cheia/g) || []).length, 3);
  assert.match(h, /rt-delta sobe">▲ 50%/);
  assert.match(h, /rt-delta">igual/);
  assert.match(h, /7 out a 13 out/);
  assert.match(h, /dia mais produtivo/);
});

test("semana: visitante sem gasto, dias incompletos nao renderizam", () => {
  assert.doesNotMatch(html("semana", { ...SEMANA, oculto: true, gasto: null }), /gastos/);
  assert.doesNotMatch(html("semana", { ...SEMANA, dias: SEMANA.dias.slice(0, 3) }), /rt-cols/);
});
