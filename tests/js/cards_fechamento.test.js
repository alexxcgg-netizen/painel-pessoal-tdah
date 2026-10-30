// Grupo G do lab v4 (2026-10-30): placar_feito, pouso_dia, retrospectiva (cards-fechamento.js) e a
// Medalha na hora (cards-medalha.js + moedinha no treino_agora). Renderizadores puros, sem DOM.
//
//   node --test tests/js/cards_fechamento.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const raiz = path.join(__dirname, "..", "..", "static", "js");
const Cards = require(path.join(raiz, "cards.js"));
require(path.join(raiz, "cards-tipos.js"));
const Medalha = require(path.join(raiz, "cards-medalha.js"));
const Fech = require(path.join(raiz, "cards-fechamento.js"));

const html = (type, data) => Cards.renderizarCardHTML({ type, id: "x1", data, actions: [] });
const semFallback = (h) => assert.ok(!h.includes("card-contrato-fallback"), h.slice(0, 200));

// ---------------------------------------------------------------- placar do feito
const PLACAR = {
  dia: "2026-10-30", hora: "22:10", total: 4,
  itens: [
    { texto: "Pagou a Enel", origem: "tarefa", rotulo: "planejado" },
    { texto: "Treino de Peito", origem: "treino", rotulo: "planejado" },
    { texto: "Voo SSBL → SBNF", origem: "voo", rotulo: "planejado" },
    { texto: "Lavei a louça", origem: "extra", rotulo: "fora do plano", id: 7 },
  ],
  sugestoes: ["Liguei pro banco", "Arrumei a casa"],
};

test("placar_feito: contador, itens com rotulo, extra com botao de tirar, chips e campo", () => {
  const h = html("placar_feito", PLACAR);
  semFallback(h);
  assert.match(h, /Feito hoje/);
  assert.match(h, /<span class="pf-n vivo-num">4<\/span> <span class="pf-un">coisas feitas<\/span>/);
  assert.match(h, /Pagou a Enel/);
  assert.match(h, /planejado/);
  assert.match(h, /data-extra-id="7"/);
  assert.equal((h.match(/data-acao="placar_remover"/g) || []).length, 1); // so o que ele anotou sai
  assert.match(h, /data-acao="placar_add" data-texto="Liguei pro banco"/);
  assert.match(h, /Fez algo fora do plano\?/);
  assert.match(h, /class="pf-input"/);
});

test("placar_feito: zero e um (singular), vazio convida a anotar, visitante sem campo", () => {
  const zero = html("placar_feito", { ...PLACAR, itens: [], total: 0 });
  assert.match(zero, /coisas feitas/);
  assert.doesNotMatch(zero, /pf-vazio" hidden/);
  const um = html("placar_feito", { ...PLACAR, itens: [PLACAR.itens[0]] });
  assert.match(um, /coisa feita/);
  assert.match(um, /pf-vazio" hidden/);
  const oculto = html("placar_feito", { ...PLACAR, oculto: true });
  assert.doesNotMatch(oculto, /pf-input|placar_add/);
});

test("placar_feito: texto do usuario passa por escape", () => {
  const h = html("placar_feito", { ...PLACAR, itens: [{ texto: '<img src=x onerror="a()">', origem: "extra", rotulo: "fora do plano", id: 1 }] });
  assert.doesNotMatch(h, /<img src=x/);
  assert.match(h, /&lt;img/);
});

// ---------------------------------------------------------------- pouso do dia
const POUSO = {
  dia: "2026-10-30", amanha: "2026-10-31", mais: 0, ids_adiar: [3, 4],
  pendentes: [
    { id: 3, titulo: "Ligar pro dentista", hora: null, data: "2026-10-30", atrasada: false },
    { id: 4, titulo: "Ler motores", hora: "10:00", data: "2026-10-28", atrasada: true },
  ],
  primeira: { texto: "Voo SSBL → SBNF", hora: "08:00", tipo: "voo" },
  mochila: { voo_id: 9, hora: "08:00", itens: [{ texto: "CIV e CMA", feito: true }, { texto: "Headset", feito: false }] },
  pousado: false,
};

test("pouso_dia: 3 passos (so o primeiro visivel), trilha, botoes e mochila com o estado do voo", () => {
  const h = html("pouso_dia", POUSO);
  semFallback(h);
  assert.match(h, /Pouso do dia/);
  assert.equal((h.match(/<section class="pd-passo"/g) || []).length, 3);
  assert.match(h, /1 de 3<\/small><b class="pd-tit">Ficou aberto/);
  assert.match(h, /Empurrar as 2 pra amanhã/);
  assert.match(h, /data-ids="3,4"/);
  assert.match(h, /Deixar como está/);
  assert.match(h, /Primeira coisa amanhã/);
  assert.match(h, /Voo SSBL → SBNF/);
  assert.match(h, /data-acao="pouso_item" data-voo="9" data-i="0" aria-pressed="true"/);
  assert.match(h, /data-acao="pouso_item" data-voo="9" data-i="1" aria-pressed="false"/);
  assert.match(h, /data-total="3"/);
  assert.equal((h.match(/class="pd-passo"[^>]* hidden/g) || []).length, 2);
  assert.match(h, /class="pd-final" hidden/);
  assert.equal((h.match(/<i class="agora">/g) || []).length, 1);
});

test("pouso_dia: so os passos que existem; sem nada vai direto pro 'Dia pousado.'", () => {
  const sem = html("pouso_dia", { ...POUSO, ids_adiar: [], pendentes: [], mochila: null });
  assert.equal((sem.match(/<section class="pd-passo"/g) || []).length, 1);
  assert.match(sem, /1 de 1/);
  const vazio = html("pouso_dia", { ...POUSO, ids_adiar: [], pendentes: [], mochila: null, primeira: null });
  assert.doesNotMatch(vazio, /pd-passo/);
  assert.match(vazio, /pd pousado/);
  assert.match(vazio, /Dia pousado\./);
  assert.match(vazio, /Amanhã é um dia limpo/);
  assert.doesNotMatch(vazio, /class="pd-final" hidden/);
  const um = html("pouso_dia", { ...POUSO, ids_adiar: [3], pendentes: [POUSO.pendentes[0]] });
  assert.match(um, /Empurrar essa pra amanhã/);
});

test("pouso_dia: card de um dia que ja pousou volta no final, com a primeira coisa de amanha", () => {
  const h = html("pouso_dia", { ...POUSO, pousado: true });
  assert.match(h, /pd pousado/);
  assert.doesNotMatch(h, /pd-passo/);
  assert.match(h, /Amanhã começa por Voo SSBL → SBNF\./);
});

test("pouso_dia: titulo de tarefa com HTML passa por escape", () => {
  const h = html("pouso_dia", { ...POUSO, pendentes: [{ id: 3, titulo: "<b>x</b>", hora: null, data: "2026-10-30", atrasada: false }] });
  assert.doesNotMatch(h, /<b>x<\/b>/);
});

// ---------------------------------------------------------------- retrospectiva
const RETRO = {
  mes: "2026-10", mes_nome: "outubro", proximo_mes: "2026-11", proximo_nome: "novembro", anterior_nome: "setembro",
  tarefas: 87, tarefas_ant: 64, kg: 41380, treinos: 12, recorde: { nome: "Supino reto", rm: 92, total: 3 },
  voo_horas: 6.4, voos: 5, aerodromos_novos: 3, gasto_cresceu: { categoria: "delivery", mais: 140, total: 300 },
  metas: ["Voar 8 h", "Zerar atrasados", "Dormir 7 h+"], meta_escolhida: null,
};

test("retrospectiva: capa com os numeros e o botao que carrega o card", () => {
  const h = html("retrospectiva", RETRO);
  semFallback(h);
  assert.match(h, /data-acao="retro_abrir" data-mes="2026-10"/);
  assert.match(h, /Abrir a retrospectiva de outubro/);
  assert.match(h, /87/);
  assert.match(h, /6,4 h/);
  assert.doesNotMatch(h, /Meta de novembro/);
  const com = html("retrospectiva", { ...RETRO, meta_escolhida: "Voar 8 h" });
  assert.match(com, /Meta de novembro: <b>Voar 8 h<\/b>/);
});

test("retrospectiva: telas so de quem tem dado de verdade", () => {
  const t = Fech.telasRetro(RETRO);
  assert.deepEqual(t.map((x) => x.k), ["intro", "tarefas", "kg", "voo", "recorde", "gasto", "meta"]);
  assert.equal(t[0].pequeno, "outubro, em números");
  assert.equal(t[1].sub, "23 a mais que setembro");
  assert.equal(t[2].grande, "41.380 kg");
  assert.equal(t[3].grande, "6,4 h");
  assert.equal(t[3].sub, "3 aeródromos novos");
  assert.equal(t[4].grande, "92 kg");
  assert.match(t[4].sub, /1RM estimado no supino reto · 3 recordes no mês/);
  assert.equal(t[5].sub, "+R$ 140 em relação a setembro");
  assert.equal(t[6].pequeno, "pra novembro, uma coisa só:");
});

test("retrospectiva: mes sem treino/voo/gasto nao ganha essas telas; visitante sem dinheiro", () => {
  const t = Fech.telasRetro({ ...RETRO, kg: 0, recorde: null, voo_horas: 0, gasto_cresceu: null, tarefas_ant: 87 });
  assert.deepEqual(t.map((x) => x.k), ["intro", "tarefas", "meta"]);
  assert.equal(t[1].sub, "igual a setembro");
  const v = Fech.telasRetro({ ...RETRO, oculto: true, gasto_cresceu: undefined });
  assert.ok(!v.some((x) => x.k === "gasto"));
  const menos = Fech.telasRetro({ ...RETRO, tarefas: 10, tarefas_ant: 30 });
  assert.equal(menos[1].sub, "20 a menos que setembro");
  const sem_novos = Fech.telasRetro({ ...RETRO, aerodromos_novos: 0 });
  assert.equal(sem_novos.find((x) => x.k === "voo").sub, "5 voos no mês");
});

// ---------------------------------------------------------------- medalha
test("medalha: moedinha (estado final) e palco com a conta", () => {
  const m = { i: 0, nome: "Supino reto", rm: 92, ganho: 3, carga: 72.5, reps: 8, legenda: "+3 kg no 1RM estimado. 72,5 × (1 + 8/30) = 91,8." };
  const mini = Medalha.mini(m);
  assert.match(mini, /class="tv-med"/);
  assert.match(mini, /1RM estimado de 92 kg/);
  assert.match(mini, /<em>\+3<\/em>/);
  assert.equal(Medalha.mini(null), "");
  const palco = Medalha.palcoHTML(m);
  assert.match(palco, /<small>RECORDE<\/small><b>92 kg<\/b><span>1RM estimado<\/span>/);
  assert.match(palco, /72,5 × \(1 \+ 8\/30\) = 91,8\./);
  assert.match(palco, /class="md-holo"/);
  assert.match(palco, /data-i="0"/);
});

test("treino_agora: exercicio com recorde ganha a moedinha na linha; sem recorde, nada", () => {
  const data = {
    sessao_id: 1, ficha_id: 1, grupo: "Peito", data: "2026-10-30",
    exercicios: [{ nome: "Supino reto", series: "4", reps: "10", carga: "25 kg" }, { nome: "Crucifixo", series: "3", reps: "12", carga: "" }],
    feitos: [0], concluido: false, duracao_min: null, sono_horas: null,
    medalhas: [{ i: 0, nome: "Supino reto", rm: 33.3, ganho: 6.6, carga: 25, reps: 10 }],
  };
  const h = html("treino_agora", data);
  semFallback(h);
  assert.equal((h.match(/class="tv-med"/g) || []).length, 1);
  assert.match(h, /class="tv-nome"><span class="tv-med"/); // moedinha antes do nome
  const sem = html("treino_agora", { ...data, medalhas: [] });
  assert.doesNotMatch(sem, /tv-med/);
  const antigo = html("treino_agora", { ...data, medalhas: undefined });
  semFallback(antigo);
});
