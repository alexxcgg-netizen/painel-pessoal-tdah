// linha-do-tempo-tarefas.js: a parte pura da aba Tarefas nova (leva 06/11, frente 6) - em que grupo
// cada tarefa cai, o texto da linha, a conta da regua do dia (7h-23h, 15 em 15 min, chuva) e os
// chips da folha. Datas fixas: 06/11/2026 e uma sexta.
const test = require("node:test");
const assert = require("node:assert");
const TL = require("../../static/js/secoes/tarefas/linha-do-tempo-tarefas.js");

const AGORA = new Date(2026, 10, 6, 14, 12); // sexta 06/11, 14:12

test("grupoDaTarefa: atrasadas, manha/tarde/noite/sem hora de hoje, amanha, outros dias e sem data", () => {
  const g = (due_date, hora) => TL.grupoDaTarefa({ due_date, hora }, AGORA);
  assert.deepStrictEqual(g(null, null), { chave: "sem-data", rotulo: "Sem data" });
  assert.strictEqual(g("2026-11-04", "10:00").chave, "atrasadas");
  assert.strictEqual(g("2026-11-04", null).alerta, true);
  assert.strictEqual(g("2026-11-06", "08:30").chave, "manha");
  assert.strictEqual(g("2026-11-06", "08:30").rotulo, "Manhã");
  assert.strictEqual(g("2026-11-06", "12:00").chave, "tarde");
  assert.strictEqual(g("2026-11-06", "17:59").chave, "tarde");
  assert.strictEqual(g("2026-11-06", "18:00").chave, "noite");
  assert.strictEqual(g("2026-11-06", null).chave, "sem-hora");
  assert.strictEqual(g("2026-11-06", "lixo").chave, "sem-hora");
  assert.deepStrictEqual(g("2026-11-07", "09:00"), { chave: "amanha", rotulo: "Amanhã" });
  assert.deepStrictEqual(g("2026-11-08", null), { chave: "2026-11-08", rotulo: "Domingo, 8 nov" });
});

test("grupoDaTarefa: virada de mes e de ano", () => {
  const fimDoAno = new Date(2026, 11, 31, 10, 0);
  assert.strictEqual(TL.grupoDaTarefa({ due_date: "2027-01-01" }, fimDoAno).chave, "amanha");
  assert.strictEqual(TL.grupoDaTarefa({ due_date: "2026-12-30" }, fimDoAno).chave, "atrasadas");
});

test("linhaDaTarefa: hora a direita, proxima e passou, atrasada sem hora a direita", () => {
  const prox = TL.linhaDaTarefa({ due_date: "2026-11-06", hora: "15:00", title: "x" }, AGORA, null);
  assert.strictEqual(prox.hora, "15:00");
  assert.strictEqual(prox.horaClasse, "cor");
  assert.deepStrictEqual(prox.partes, ["em 48 min"]);
  const longe = TL.linhaDaTarefa({ due_date: "2026-11-06", hora: "21:00" }, AGORA, null);
  assert.deepStrictEqual(longe.partes, [], "mais de 3 h pra frente nao poluí a linha");
  const passou = TL.linhaDaTarefa({ due_date: "2026-11-06", hora: "13:00" }, AGORA, null);
  assert.deepStrictEqual(passou.partes, ["passou há 1h12"]);
  const atr = TL.linhaDaTarefa({ due_date: "2026-11-05", hora: "10:00" }, AGORA, null);
  assert.strictEqual(atr.hora, "");
  assert.deepStrictEqual(atr.partes, ["era pra ontem às 10:00"]);
  const amanha = TL.linhaDaTarefa({ due_date: "2026-11-07", hora: "9:00" }, AGORA, null);
  assert.strictEqual(amanha.hora, "09:00");
  assert.strictEqual(amanha.horaClasse, "");
});

test("linhaDaTarefa: lugar, rotina, passos, cadeado, premio e chuva na saida", () => {
  const t = {
    due_date: "2026-11-06",
    hora: "20:00",
    local: "Viva Beach",
    estilo: "date",
    recorrente_origem_id: 3,
    subtasks: [{ completed_at: "x" }, { completed_at: null }],
    empacada_dias: 1,
    inegociavel: 1,
    extras: JSON.stringify({ pacote: { premio: "série" } }),
  };
  const l = TL.linhaDaTarefa(t, AGORA, { de: 17 * 60, ate: 21 * 60 });
  assert.deepStrictEqual(l.partes, ["Viva Beach", "rotina", "1 de 2 passos", "travada há 1 dia", "não pode falhar", "prêmio: série"]);
  assert.strictEqual(l.chuva, "chuva na saída");
  const fora = TL.linhaDaTarefa({ due_date: "2026-11-06", hora: "21:00" }, AGORA, { de: 17 * 60, ate: 21 * 60 });
  assert.strictEqual(fora.chuva, "", "a faixa e [de, ate)");
  const semSaida = TL.linhaDaTarefa({ due_date: "2026-11-06", hora: "18:00" }, AGORA, { de: 17 * 60, ate: 21 * 60 });
  assert.strictEqual(semSaida.chuva, "chuva nessa hora");
  const extrasRuim = TL.linhaDaTarefa({ due_date: null, due_at: "sexta de manhã", extras: "{nao e json" }, AGORA, null);
  assert.deepStrictEqual(extrasRuim.partes, ["sexta de manhã"]);
});

test("ehSaida: lugar, date ou balada", () => {
  assert.strictEqual(TL.ehSaida({ local: "obra" }), true);
  assert.strictEqual(TL.ehSaida({ local: "  " }), false);
  assert.strictEqual(TL.ehSaida({ estilo: "balada" }), true);
  assert.strictEqual(TL.ehSaida({ title: "ler" }), false);
});

test("faixaDaRegua: 7h-23h e estica de hora em hora quando tem tarefa fora", () => {
  assert.deepStrictEqual(TL.faixaDaRegua([]), { ini: 420, fim: 1380 });
  assert.deepStrictEqual(TL.faixaDaRegua([9 * 60, 22 * 60]), { ini: 420, fim: 1380 });
  assert.deepStrictEqual(TL.faixaDaRegua([5 * 60 + 30]), { ini: 300, fim: 1380 });
  assert.deepStrictEqual(TL.faixaDaRegua([22 * 60 + 50]), { ini: 420, fim: 1440 });
  assert.deepStrictEqual(TL.faixaDaRegua([23 * 60 + 50, null, NaN]), { ini: 420, fim: 1440 });
});

test("posicaoNaRegua / minutoDoPonto: 15 em 15 min, presa nas pontas", () => {
  assert.strictEqual(TL.posicaoNaRegua(420, 420, 1380), 0);
  assert.strictEqual(TL.posicaoNaRegua(900, 420, 1380), 50);
  assert.strictEqual(TL.posicaoNaRegua(2000, 420, 1380), 100);
  assert.strictEqual(TL.minutoDoPonto(150, 300, 420, 1380), 900); // meio = 15:00
  assert.strictEqual(TL.minutoDoPonto(152, 300, 420, 1380), 900); // 15:04,8 -> 15:00
  assert.strictEqual(TL.minutoDoPonto(153, 300, 420, 1380), 915); // 15:09,6 -> 15:15
  assert.strictEqual(TL.minutoDoPonto(-40, 300, 420, 1380), 420);
  assert.strictEqual(TL.minutoDoPonto(999, 300, 420, 1380), 1380);
  assert.strictEqual(TL.minutoDoPonto(999, 300, 420, 1440), 1425, "nunca passa de 23:45");
  assert.strictEqual(TL.minutoDoPonto(10, 0, 420, 1380), 420);
});

test("passoNaRegua: setas andam 15 min e encaixam hora quebrada", () => {
  assert.strictEqual(TL.passoNaRegua(900, 1, 420, 1380), 915);
  assert.strictEqual(TL.passoNaRegua(900, -1, 420, 1380), 885);
  assert.strictEqual(TL.passoNaRegua(980, 1, 420, 1380), 990); // 16:20 -> 16:30
  assert.strictEqual(TL.passoNaRegua(980, -1, 420, 1380), 975); // 16:20 -> 16:15
  assert.strictEqual(TL.passoNaRegua(420, -1, 420, 1380), 420);
  assert.strictEqual(TL.passoNaRegua(1380, 1, 420, 1380), 1380);
});

test("rotulosDaRegua: de 3 em 3 horas", () => {
  assert.deepStrictEqual(
    TL.rotulosDaRegua(420, 1380).map((r) => r.texto),
    ["7h", "10h", "13h", "16h", "19h", "22h"]
  );
  assert.deepStrictEqual(TL.rotulosDaRegua(300, 1440).map((r) => r.texto), ["5h", "8h", "11h", "14h", "17h", "20h", "23h"]);
});

test("faixaDeChuva: so com alerta da previsao, cortada na regua", () => {
  assert.strictEqual(TL.faixaDeChuva(null, 420, 1380), null);
  assert.strictEqual(TL.faixaDeChuva({ alerta: false, hora_inicio: 17, hora_fim: 20 }, 420, 1380), null);
  assert.strictEqual(TL.faixaDeChuva({ alerta: true }, 420, 1380), null);
  assert.deepStrictEqual(TL.faixaDeChuva({ alerta: true, hora_inicio: 17, hora_fim: 20, chuva_pct_max: 80 }, 420, 1380), {
    de: 1020,
    ate: 1200,
    pct: 80,
  });
  assert.deepStrictEqual(TL.faixaDeChuva({ alerta: true, hora_inicio: 4, hora_fim: 24 }, 420, 1380), { de: 420, ate: 1380, pct: null });
  assert.strictEqual(TL.faixaDeChuva({ alerta: true, hora_inicio: 2, hora_fim: 5 }, 420, 1380), null);
});

test("rotulosVisiveis: rotulo que encostaria no anterior some", () => {
  assert.deepStrictEqual(TL.rotulosVisiveis([10, 12, 30, 31, 33], 5), [true, false, true, false, false]);
  assert.deepStrictEqual(TL.rotulosVisiveis([], 5), []);
});

test("horaSomada: +30/+1h em cima da hora da tarefa ou de agora arredondado; passou da meia-noite = null", () => {
  assert.strictEqual(TL.horaSomada("16:30", 30, AGORA), "17:00");
  assert.strictEqual(TL.horaSomada("16:30", 60, AGORA), "17:30");
  assert.strictEqual(TL.horaSomada(null, 30, AGORA), "14:45"); // 14:12 -> 14:15 + 30
  assert.strictEqual(TL.horaSomada("23:40", 30, AGORA), null);
  assert.strictEqual(TL.horaSomada("23:00", 59, AGORA), "23:59");
});

test("diasDaFolha e rotuloDestino", () => {
  assert.deepStrictEqual(
    TL.diasDaFolha(AGORA).map((d) => [d.iso, d.rotulo]),
    [
      ["2026-11-06", "Hoje"],
      ["2026-11-07", "Amanhã"],
      ["2026-11-08", "Domingo"],
      ["2026-11-09", "Segunda"],
      ["2026-11-10", "Terça"],
    ]
  );
  assert.strictEqual(TL.rotuloDestino("2026-11-06", AGORA), "pra hoje");
  assert.strictEqual(TL.rotuloDestino("2026-11-07", AGORA), "pra amanhã");
  assert.strictEqual(TL.rotuloDestino("2026-11-20", AGORA), "pra sexta, 20 nov");
});

test("resumoDoDia: conta de hoje, atrasadas e chuva", () => {
  const tarefas = [
    { due_date: "2026-11-06", hora: "15:00" },
    { due_date: "2026-11-06", hora: null },
    { due_date: "2026-11-05", hora: null },
    { due_date: "2026-11-07", hora: "09:00" },
  ];
  assert.strictEqual(TL.resumoDoDia(tarefas, AGORA, null), "2 tarefas hoje, 1 com hora. 1 atrasada.");
  assert.strictEqual(
    TL.resumoDoDia(tarefas.slice(0, 1), AGORA, { de: 17 * 60, ate: 24 * 60 }),
    "1 tarefa hoje, 1 com hora. Chuva das 17h às meia-noite."
  );
  assert.strictEqual(TL.resumoDoDia([], AGORA, null), "Nada marcado pra hoje.");
});

test("rotuloAtraso, rotuloDiaLongo e tlDuracao", () => {
  assert.strictEqual(TL.rotuloAtraso("2026-11-05", AGORA), "ontem");
  assert.strictEqual(TL.rotuloAtraso("2026-11-02", AGORA), "seg 2");
  assert.strictEqual(TL.rotuloDiaLongo(AGORA), "sexta, 6 de novembro");
  assert.strictEqual(TL.tlDuracao(40), "40 min");
  assert.strictEqual(TL.tlDuracao(130), "2h10");
  assert.strictEqual(TL.tlDuracao(180), "3h");
  assert.strictEqual(TL.tlHora(905), "15:05");
});
