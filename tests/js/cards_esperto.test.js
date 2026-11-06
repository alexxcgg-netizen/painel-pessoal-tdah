// Painel mais esperto, frente 7 (06/11/2026, static/js/cards-esperto.js): voo decidido na véspera, rotina
// descoberta e tarefa adiada 3 vezes. Puro, sem DOM. Dados inventados.
//
//   node --test tests/js/cards_esperto.test.js
//
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const js = (f) => path.join(__dirname, "..", "..", "static", "js", f);
const Cards = require(js("cards.js"));
require(js("cards-d.js"));
const E = require(js("cards-esperto.js"));

const AGORA = new Date(2026, 10, 6, 20, 31);
const html = (type, data, actions) => Cards.renderizarCardHTML({ type, id: "c1", data, actions: actions || [] }, { agora: AGORA });
const CARA_DE_IA = /fio-luz|luz-dedo|selo-brilho|eyebrow|text-transform:\s*uppercase|degrade|neon|tilt/;

const COND_BOA = [
  { rotulo: "Teto", valor: "livre", tom: "ok" },
  { rotulo: "Visibilidade", valor: "10 km+", tom: "ok" },
  { rotulo: "Vento", valor: "090° 3 kt", tom: "ok" },
  { rotulo: "Sono", valor: "8 h · deita 23h", tom: "ok" },
];

test("voo_decisao: voa - pílula aberta, veredito verde, 4 quadradinhos e a nota", () => {
  const h = html("voo_decisao", {
    voo_id: 3, data: "2026-11-07", hora: "09:30", quando: "amanha", sub: "SSBL · local", veredito: "voa",
    frase: "Amanhã voa.", conds: COND_BOA, nota: "TAF das 14h cobre a hora do voo. Confiro de novo às 06:30 e te aviso se mudar.",
  });
  assert.match(h, /class="vivo-d" data-v="voo-decisao" style="--cc:#8fd0ff" aria-expanded="true" data-vd="voa"/);
  assert.match(h, /<span class="v-t">Voo de amanhã, 09:30<\/span>/);
  assert.match(h, /<span class="v-s"><span>SSBL · local<\/span><\/span>/);
  assert.match(h, /<small>decide<\/small><b>hoje<\/b>/);
  assert.match(h, /<p class="es-veredito" data-vd="voa">Amanhã voa\.<\/p>/);
  assert.equal((h.match(/<div class="ok" style="--k:\d">/g) || []).length, 4);
  assert.match(h, /Confiro de novo às 06:30/);
  assert.doesNotMatch(h, /esperto_remarcar/);
  assert.doesNotMatch(h, CARA_DE_IA);
});

test("voo_decisao: não dá - quadradinho ruim, Remarcar pras HH:MM / Mantém", () => {
  const h = html("voo_decisao", {
    voo_id: 3, hora: "09:30", quando: "amanha", veredito: "nao", frase: "Amanhã não dá.",
    conds: [{ rotulo: "Teto", valor: "800 ft", tom: "ruim" }, ...COND_BOA.slice(1)],
    nota: "Teto 800 ft na hora do voo (IFR). Às 12h o TAF já fica bom e tu tá livre. Remarco pras 12:00?",
    remarcar: { data: "2026-11-07", hora: "12:00" },
  });
  assert.match(h, /<p class="es-veredito" data-vd="nao">Amanhã não dá\.<\/p>/);
  assert.match(h, /<div class="ruim" style="--k:0"><small>Teto<\/small><b>800 ft<\/b><\/div>/);
  assert.match(h, /class="pri" data-acao="esperto_remarcar" data-id="3" data-hora="12:00" data-de="09:30">Remarcar pras 12:00<\/button>/);
  assert.match(h, /data-acao="esperto_manter" data-id="3" data-de="09:30">Mantém<\/button>/);
});

test("voo_decisao: sem horário bom só pergunta; hora inválida não vira botão; incerto e hoje", () => {
  const sem = html("voo_decisao", { voo_id: 3, hora: "09:30", quando: "amanha", veredito: "nao", frase: "x", perguntar_remarcar: true });
  assert.match(sem, /data-acao="esperto_remarcar_chat" data-quando="de amanhã">Remarcar<\/button>/);
  const torto = html("voo_decisao", { voo_id: 3, hora: "09:30", veredito: "nao", frase: "x", remarcar: { hora: "<b>" } });
  assert.doesNotMatch(torto, /esperto_remarcar"/);
  const inc = html("voo_decisao", { voo_id: 3, hora: "16:00", quando: "hoje", veredito: "talvez", emissao: "05:00" });
  assert.match(inc, /data-vd="incerto">Ainda não dá pra saber\.<\/p>/);
  assert.match(inc, /Voo de hoje, 16:00/);
  assert.match(inc, /<small>conferido<\/small><b>TAF 05:00<\/b>/);
  assert.equal(html("voo_decisao", { voo_id: 3 }).includes("vivo-d"), false);
});

test("voo_decisao: escapa HTML do servidor", () => {
  const h = html("voo_decisao", {
    voo_id: 3, hora: "09:30", veredito: "voa", frase: "<img src=x>", sub: "<script>", nota: "<i>",
    conds: [{ rotulo: "<b>", valor: "<u>", tom: "<x>" }],
  });
  assert.doesNotMatch(h, /<img|<script|<i>|<u>/);
  assert.match(h, /<div class="ok" style="--k:0">/); // tom desconhecido cai em ok
});

test("rotina_proposta: título, sub e Virar rotina / Não", () => {
  const h = html("rotina_proposta", {
    chave: "lugar:academia:1,3", titulo: "Academia toda terça e quinta", sub: "18:00 · já faz 3 semanas",
    texto: "Vi tu chegar na academia nesses dias. Viro rotina? Aí eu já lembro e conto a semana.",
  });
  assert.match(h, /data-v="rotina" style="--cc:#c4a1ff" aria-expanded="true"/);
  assert.match(h, /<span class="v-t">Academia toda terça e quinta<\/span>/);
  assert.match(h, /18:00 · já faz 3 semanas/);
  assert.match(h, /class="pri" data-acao="esperto_rotina" data-r="sim" data-chave="lugar:academia:1,3">Virar rotina<\/button>/);
  assert.match(h, /data-acao="esperto_rotina" data-r="nao" data-chave="lugar:academia:1,3">Não<\/button>/);
  assert.doesNotMatch(h, CARA_DE_IA);
  assert.equal(html("rotina_proposta", { titulo: "x" }).includes("vivo-d"), false);
});

test("tarefa_adiada: título com aspas e os três chips", () => {
  const h = html("tarefa_adiada", { task_id: 9, titulo: "Separar os papéis", adiadas: 3 });
  assert.match(h, /data-v="adiada" style="--cc:#f0a58f"/);
  assert.match(h, /<span class="v-t">“Separar os papéis” já foi adiada 3 vezes<\/span>/);
  assert.match(h, /o que eu faço com ela\?/);
  for (const [a, r] of [["passos", "Quebrar em passos"], ["dia", "Mudar o dia"], ["apagar", "Apagar"]]) {
    assert.match(h, new RegExp(`class="es-chip" data-acao="esperto_adiada" data-a="${a}" data-id="9">${r}</button>`));
  }
  const oculto = html("tarefa_adiada", { task_id: 9, oculto: true, adiadas: 4 });
  assert.match(oculto, /Tarefa adiada 4 vezes/);
  assert.equal(html("tarefa_adiada", { titulo: "x" }).includes("vivo-d"), false);
});

test("helpers: resposta com Desfazer pequeno e texto dos passos", () => {
  const r = E.respostaHTML("Virou rotina: terça, 18:00.", { url: "/api/desfazer/abc" });
  assert.match(r, /<p class="v-nota">Virou rotina: terça, 18:00\.<\/p>/);
  assert.match(r, /data-acao="esperto_desfazer" data-url="\/api\/desfazer\/abc" data-metodo="POST">Desfazer<\/button>/);
  assert.doesNotMatch(E.respostaHTML("Ok."), /Desfazer/);
  assert.equal(E.textoPassos({ subtasks: [1, 2, 3] }), "Quebrei em 3 passos. Tá na aba Tarefas.");
  assert.equal(E.textoPassos({}), "Quebrei em passos. Tá na aba Tarefas.");
});
