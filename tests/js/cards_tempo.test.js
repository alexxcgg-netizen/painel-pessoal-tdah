// Grupo B (Tempo), leva do Laboratorio v4: cards espera / calibrador / disjuntor / porta (static/js/cards-tempo.js) e a
// fita do topo (static/js/secoes/topo/fita.js). Renderizam o estado final, escapam texto e nao viram fallback com dado faltando.
//
//   node --test tests/js/cards_tempo.test.js
//
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const Cards = require(path.join(__dirname, "..", "..", "static", "js", "cards.js"));
const CardsTempo = require(path.join(__dirname, "..", "..", "static", "js", "cards-tempo.js"));
const Fita = require(path.join(__dirname, "..", "..", "static", "js", "secoes", "topo", "fita.js"));

const html = (type, data) => Cards.renderizarCardHTML({ type, id: "c1", data, actions: [] });
const semFallback = (h) => assert.ok(!h.includes("card-contrato-fallback"), h);

test("dur: horas e minutos do jeito da demo", () => {
  assert.equal(CardsTempo.dur(130), "2h10");
  assert.equal(CardsTempo.dur(120), "2h");
  assert.equal(CardsTempo.dur(45), "45 min");
  assert.equal(CardsTempo.dur(-3), "0 min");
});

test("espera: livre ate, faixa na proporcao, cabe nessa janela e a chave ligada", () => {
  const h = html("espera", {
    kind: "voo", ref: 7, titulo: "Voo", hora: "15:00", livre_ate: "13:50", sair: "14:35", livre_min: 130, arrumar_min: 45, ir_min: 25,
    chamar: "ligado", cabe: [{ id: 3, titulo: "Pagar a <b>fatura</b>", min: 8 }, { id: 4, titulo: "Mochila", min: 10 }],
  });
  semFallback(h);
  assert.match(h, /Livre até/);
  assert.match(h, /class="tp-grande">13:50</);
  assert.match(h, /2h10 livres · depois: se arrumar 45 min, sair 14:35/);
  assert.match(h, /tp-es-livre" style="flex:130"/);
  assert.match(h, /tp-es-arr" style="flex:45"/);
  assert.match(h, /tp-es-tr" style="flex:25"/);
  assert.match(h, /Cabe nessa janela/);
  assert.match(h, /Pagar a &lt;b&gt;fatura/);
  assert.match(h, /data-acao="tp_cabe" data-id="3"/);
  assert.match(h, /<input type="checkbox" data-acao="tp_chama" data-kind="voo" data-ref="7" checked/);
  assert.match(h, /Eu te chamo às 13:50/);
});

test("espera: desligado nao vem marcado; garantido nao mostra chave; sem cabe nao mostra a lista", () => {
  const base = { kind: "tarefa", ref: 1, titulo: "Jantar", hora: "20:00", livre_ate: "18:50", sair: "19:45", livre_min: 90, arrumar_min: 0, ir_min: 15, cabe: [] };
  const off = html("espera", Object.assign({}, base, { chamar: "desligado" }));
  assert.ok(!/ checked/.test(off));
  assert.ok(!off.includes("Cabe nessa janela"));
  assert.match(off, /sair 19:45/);
  const garantido = html("espera", Object.assign({}, base, { chamar: "garantido" }));
  assert.ok(!garantido.includes("tp_chama"));
  assert.match(garantido, /já tá garantido/);
  semFallback(html("espera", {}));
});

test("calibrador: fator com virgula, grafico, media e o slider com a conta do fator", () => {
  const h = html("calibrador", {
    fator: 1.7, n: 5, est_media: 26, real_media: 44, padrao_min: 20,
    historico: [{ titulo: "Lavar o carro", est: 30, real: 55 }, { titulo: "<i>x</i>", est: 15, real: 30 }],
    nova: { id: 9, titulo: "Lavar a moto" },
  });
  semFallback(h);
  assert.match(h, /data-tp-contar-ate="1.7"[^>]*>×1,7</);
  assert.match(h, /Tu estima, em média, 26 min\. Leva 44\./);
  assert.match(h, /30→55/);
  assert.match(h, /&lt;i&gt;x&lt;\/i&gt;/);
  assert.match(h, /Tarefa nova: Lavar a moto/);
  assert.match(h, /data-fator="1.7"/);
  assert.match(h, /tp-ca-dest">35 min</); // 20 min x 1,7 -> 35
  assert.match(h, /data-acao="tp_palpite" data-id="9"/);
  assert.equal(CardsTempo.reservaCalibrador(20, 1.7), 35);
  assert.equal(CardsTempo.reservaCalibrador(5, 0.5), 5);
});

test("calibrador sem tarefa nova: slider generico, sem botao de guardar; dado faltando nao quebra", () => {
  const h = html("calibrador", { fator: 2, n: 3, est_media: 10, real_media: 20, historico: [], nova: null });
  semFallback(h);
  assert.match(h, /Se tu achar que leva/);
  assert.ok(!h.includes("tp_palpite"));
  semFallback(html("calibrador", {}));
});

test("disjuntor: tempo direto, ultima agua, tres opcoes de 1 toque e escape", () => {
  const h = html("disjuntor", { desde: "13:10", minutos: 125, motivo: "tempo", ultima_agua: "12:55", copos: 2, refeicoes: 0, dia: "2026-10-30" });
  semFallback(h);
  assert.match(h, /foco desde 13:10/);
  assert.match(h, /2h05 direto sem pausa/);
  assert.match(h, /Última água 12:55 · refeição não registrada/);
  assert.equal((h.match(/data-acao="tp_dj"/g) || []).length, 3);
  assert.match(h, /data-k="agua"/);
  assert.match(h, /data-k="comer"/);
  assert.match(h, /data-k="alongar"/);
  assert.match(h, /data-tp-chave="dj-2026-10-30-13:10"/);
  assert.match(h, /stroke-dashoffset:0\.167/); // 125/150 do arco
  assert.match(h, /Tocar registra na hora/);
});

test("disjuntor por refeicao e sem agua; dado faltando nao quebra", () => {
  const h = html("disjuntor", { desde: "<b>", minutos: 50, motivo: "refeicao", ultima_agua: null, refeicoes: 1 });
  semFallback(h);
  assert.match(h, /50 min no foco, sem refeição hoje/);
  assert.match(h, /Sem água registrada hoje · 1 refeição registrada/);
  assert.match(h, /foco desde &lt;b&gt;/);
  semFallback(html("disjuntor", {}));
});

test("porta: lista do lugar, itens que o Alex acrescentou com botao de tirar, e a porta fechada", () => {
  const h = html("porta", {
    lugar: "Academia", sai: "8:05", dia: "2026-10-30", voo_id: null, vespera: false,
    lugares: [
      { nome: "Voo", itens: [{ texto: "CIV e CMA", feito: true, meu: false }] },
      { nome: "Academia", itens: [{ texto: "Toalha", feito: true, meu: false }, { texto: "Cinto <b>x</b>", feito: false, meu: true }] },
      { nome: "Faculdade", itens: [] },
    ],
  });
  semFallback(h);
  assert.match(h, /Antes de sair/);
  assert.match(h, /sai 8:05/);
  assert.match(h, /tp-seg" data-p="1"/);
  assert.match(h, /data-acao="tp_lugar" data-i="1" aria-pressed="true"/);
  assert.match(h, /data-lugar="Voo"[^>]* hidden/);
  assert.match(h, /data-lugar="Academia"(?![^>]* hidden)/);
  assert.match(h, /Falta pegar 1/);
  assert.ok(!/tp-porta aberta/.test(h));
  assert.match(h, /Cinto &lt;b&gt;x&lt;\/b&gt;/);
  assert.match(h, /data-acao="tp_rm" data-lugar="Academia" data-item="Cinto &lt;b&gt;x&lt;\/b&gt;"/);
  assert.equal((h.match(/data-acao="tp_rm"/g) || []).length, 1); // so o item dele tem X
  assert.match(h, /data-acao="tp_add"/);
  assert.match(h, /font|placeholder="Esqueci uma vez…"/);
});

test("porta: tudo marcado abre a porta; voo diz bom voo; vespera diz mochila pronta", () => {
  const todos = (nome) => ({ nome, itens: [{ texto: "A", feito: true, meu: false }] });
  const voo = html("porta", { lugar: "Voo", dia: "2026-10-30", lugares: [todos("Voo"), todos("Academia")] });
  assert.match(voo, /tp-porta aberta/);
  assert.match(voo, /Pode sair\. Bom voo!/);
  const ves = html("porta", { lugar: "Academia", dia: "2026-10-31", vespera: true, lugares: [todos("Voo"), todos("Academia")] });
  assert.match(ves, /Deixa pronta\?/);
  assert.match(ves, /Mochila pronta\. Amanhã é só pegar\./);
  assert.equal(CardsTempo.textoPorta(3, "Voo", false), "Falta pegar 3");
  semFallback(html("porta", {}));
});

test("fita: texto, estado e proporcao pela demo (sair em 1h40 -> perto -> hora de sair -> agora)", () => {
  const f = { titulo: "Academia", hora: "18:30", tem_saida: true, sair_em_s: 100 * 60, evento_em_s: 125 * 60, janela_min: 180 };
  let r = Fita.textoDaFita(f, 0);
  assert.equal(r.texto, "Sair pra academia em 1h40");
  assert.equal(r.estado, "normal");
  assert.ok(Math.abs(r.p - 100 / 180) < 1e-9);
  r = Fita.textoDaFita(f, 90 * 60);
  assert.equal(r.texto, "Sair pra academia em 10 min");
  assert.equal(r.estado, "perto");
  r = Fita.textoDaFita(f, 105 * 60);
  assert.equal(r.texto, "Hora de sair. Academia às 18:30");
  assert.equal(r.estado, "ja");
  assert.equal(r.p, 0);
  r = Fita.textoDaFita(f, 130 * 60);
  assert.equal(r.texto, "Academia agora");
});

test("fita sem saida conta ate o compromisso; 1a letra baixa so quando a 2a nao e maiuscula", () => {
  const f = { titulo: "Dentista", hora: "16:00", tem_saida: false, sair_em_s: 3600, evento_em_s: 3600, janela_min: 180 };
  assert.equal(Fita.textoDaFita(f, 0).texto, "Dentista em 1h");
  assert.equal(Fita.textoDaFita(f, 3000).estado, "perto");
  assert.equal(Fita.minuscula("Academia"), "academia");
  assert.equal(Fita.minuscula("CIV na carteira"), "CIV na carteira");
  assert.equal(Fita.dur(0.2), "1 min"); // nunca "0 min" antes da hora
  assert.equal(Fita.textoDaFita({ titulo: "Voo", hora: "15:00", tem_saida: true, sair_em_s: 30, evento_em_s: 2000 }, 0).texto, "Sair pra voo em 1 min");
});

test("espera (07/11): o topo usa o nome curto do servidor; card antigo cai no titulo", () => {
  const base = { kind: "tarefa", ref: 1, hora: "15:00", livre_ate: "13:50", sair: "14:35", livre_min: 130, arrumar_min: 0, ir_min: 25, cabe: [] };
  const novo = html("espera", Object.assign({}, base, { titulo: "Levar a Sta no dentista às 15 e depois passar no mercado", nome: "dentista" }));
  semFallback(novo);
  assert.match(novo, /<span class="cd-quando">hoje · dentista 15:00<\/span>/);
  assert.doesNotMatch(novo, /mercado/);
  const velho = html("espera", Object.assign({}, base, { titulo: "Jantar" }));
  assert.match(velho, /hoje · Jantar 15:00/);
});
