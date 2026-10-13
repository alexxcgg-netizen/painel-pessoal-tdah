// linha-do-tempo-tarefas.js: a parte pura da aba Tarefas como linha do tempo - em que
// cabecalho cada tarefa cai e o estado de cada linha (passou / proxima / atrasada) + onde
// vai o marcador de "agora". Datas fixas: 13/10/2026 e uma terca.
const test = require("node:test");
const assert = require("node:assert");
const TL = require("../../static/js/secoes/tarefas/linha-do-tempo-tarefas.js");

const HOJE = new Date(2026, 9, 13, 14, 0); // terca 13/10, 14:00

test("grupoDaTarefa: sem data, atrasadas, hoje, amanha e dia da semana", () => {
  assert.deepStrictEqual(TL.grupoDaTarefa({ due_date: null }, HOJE), { chave: "sem-data", rotulo: "Sem data", dia: "" });
  const atr = TL.grupoDaTarefa({ due_date: "2026-10-10" }, HOJE);
  assert.strictEqual(atr.chave, "atrasadas");
  assert.strictEqual(atr.alerta, true);
  const hoje = TL.grupoDaTarefa({ due_date: "2026-10-13" }, HOJE);
  assert.strictEqual(hoje.rotulo, "Hoje");
  assert.strictEqual(hoje.dia, "terça 13");
  assert.strictEqual(hoje.hoje, true);
  assert.strictEqual(TL.grupoDaTarefa({ due_date: "2026-10-14" }, HOJE).rotulo, "Amanhã");
  const qui = TL.grupoDaTarefa({ due_date: "2026-10-15" }, HOJE);
  assert.strictEqual(qui.chave, "2026-10-15");
  assert.strictEqual(qui.rotulo, "quinta 15");
  assert.strictEqual(qui.dia, "15 out");
});

test("grupoDaTarefa: virada de mes no amanha", () => {
  const ult = new Date(2026, 9, 31, 9, 0);
  assert.strictEqual(TL.grupoDaTarefa({ due_date: "2026-11-01" }, ult).rotulo, "Amanhã");
});

test("tlDuracao e tlMinutos", () => {
  assert.strictEqual(TL.tlDuracao(40), "40 min");
  assert.strictEqual(TL.tlDuracao(130), "2h10");
  assert.strictEqual(TL.tlDuracao(180), "3h");
  assert.strictEqual(TL.tlDuracao(-5), "0 min");
  assert.strictEqual(TL.tlMinutos("09:30"), 570);
  assert.strictEqual(TL.tlMinutos(""), null);
  assert.strictEqual(TL.tlMinutos(null), null);
});

test("rotuloAtraso: ontem ou dia curto", () => {
  assert.strictEqual(TL.rotuloAtraso("2026-10-12", HOJE), "ontem");
  assert.strictEqual(TL.rotuloAtraso("2026-10-08", HOJE), "qui 8");
});

test("estadosDaLinha: passou, proxima respira e o agora fica antes dela", () => {
  const tarefas = [
    { id: 1, due_date: "2026-10-12", hora: "10:00" },
    { id: 2, due_date: "2026-10-13", hora: "11:40" },
    { id: 3, due_date: "2026-10-13", hora: "14:40" },
    { id: 4, due_date: "2026-10-13", hora: "18:00" },
    { id: 5, due_date: "2026-10-13", hora: null },
    { id: 6, due_date: null, due_at: "sexta de manha" },
  ];
  const { itens, agoraEm } = TL.estadosDaLinha(tarefas, HOJE);
  assert.deepStrictEqual(itens.map((e) => e.classe), ["tl-atrasada", "tl-passou", "tl-proxima", "", "", ""]);
  assert.strictEqual(itens[0].hora, "ontem");
  assert.strictEqual(itens[0].meta, "era às 10:00");
  assert.strictEqual(itens[1].meta, "passou há 2h20");
  assert.strictEqual(itens[2].meta, "em 40 min");
  assert.strictEqual(itens[3].meta, "");
  assert.strictEqual(itens[4].hora, "—");
  assert.strictEqual(itens[4].horaVazia, true);
  assert.strictEqual(itens[5].meta, "sexta de manha");
  assert.deepStrictEqual(agoraEm, { antesDe: 3 });
});

test("estadosDaLinha: tudo de hoje ja passou -> agora depois da ultima; nada hoje -> sem marcador", () => {
  const passou = TL.estadosDaLinha(
    [
      { id: 1, due_date: "2026-10-13", hora: "08:00" },
      { id: 2, due_date: "2026-10-13", hora: "13:00" },
    ],
    HOJE,
  );
  assert.deepStrictEqual(passou.agoraEm, { depoisDe: 2 });
  const nada = TL.estadosDaLinha([{ id: 1, due_date: "2026-10-20", hora: "09:00" }], HOJE);
  assert.strictEqual(nada.agoraEm, null);
  assert.strictEqual(nada.itens[0].classe, "");
  assert.strictEqual(nada.itens[0].hora, "09:00");
});

test("estadosDaLinha: na hora exata diz 'agora'", () => {
  const { itens } = TL.estadosDaLinha([{ id: 1, due_date: "2026-10-13", hora: "14:00" }], HOJE);
  assert.strictEqual(itens[0].classe, "tl-proxima");
  assert.strictEqual(itens[0].meta, "agora");
});
