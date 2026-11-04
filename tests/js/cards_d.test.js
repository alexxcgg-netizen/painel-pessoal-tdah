// Linguagem D "ao vivo" (static/js/cards-d.js, 04/11/2026): a casca da pílula, a contagem em
// segundos do servidor, os pedaços (cadeia, tempo hora a hora, o que levar, anéis), o type novo
// lugar_salvo e a pílula da tarefa com hora (cards-tipos.js). Puro, sem DOM.
//
//   node --test tests/js/cards_d.test.js
//
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const js = (f) => path.join(__dirname, "..", "..", "static", "js", f);
const Cards = require(js("cards.js"));
const D = require(js("cards-d.js"));
require(js("cards-tipos.js"));

const AGORA = new Date(2026, 10, 4, 8, 0);
const G = AGORA.getTime() / 1000;

test("contagem: segundos do servidor menos o que passou desde gerado_ts (nunca hora de parede)", () => {
  assert.equal(D.restante(840, G, AGORA.getTime()), 840);
  assert.equal(D.restante(840, G, AGORA.getTime() + 60000), 780);
  assert.equal(D.restante(840, null, AGORA.getTime()), 840); // sem gerado_ts: nao desconta
  assert.equal(D.restante("x", G), null);
  assert.equal(D.fmtCd(840, "min"), "14 min");
  assert.equal(D.fmtCd(5400, "min"), "1h30");
  assert.equal(D.fmtCd(0, "min"), "agora");
  assert.equal(D.fmtCd(3 * 86400, "min"), "3 dias");
  assert.equal(D.fmtCd(839, "mmss"), "13:59");
  assert.equal(D.fmtCd(3723, "mmss"), "1:02:03");
  const h = D.contagem(840, G, "min", AGORA);
  assert.match(h, /class="rl" data-cd-s="840" data-cd-g="\d+" data-fmt="min" data-txt="14 min"/);
  assert.match(h, /<span class="rl-sr">14 min<\/span>/); // leitor de tela le o texto inteiro
  assert.equal(D.contagem(null, G, "min", AGORA), "");
});

test("pilula: fechada com icone, titulo, linha e valor; toque abre (botao com aria-expanded)", () => {
  const h = D.pilula({ v: "x", cor: "#fff", icone: "<svg></svg>", titulo: "<b>T</b>", sub: "<span>s</span>", rotulo: "em", valor: "1", corpo: "<p>c</p>" });
  assert.match(h, /^<div class="vivo-d" data-v="x" style="--cc:#fff" aria-expanded="false">/);
  assert.match(h, /<button type="button" class="v-top" aria-expanded="false">/);
  assert.match(h, /<span class="v-t">&lt;b&gt;T&lt;\/b&gt;<\/span>/);
  assert.match(h, /<span class="v-dir"><small>em<\/small><b>1<\/b><\/span>/);
  assert.match(h, /<div class="v-in"><div class="v-cont"><p>c<\/p><\/div><\/div>/);
  assert.doesNotMatch(D.pilula({ titulo: "a" }), /v-dir/); // sem valor, sem coluna da direita
});

test("cadeia, tempo hora a hora e o que levar: so com dado, nada inventado", () => {
  assert.equal(D.cadeia([]), "");
  assert.match(D.cadeia([{ rotulo: "Sair", hora: "18:30" }, { rotulo: "Chegar", hora: "19:00" }]), /style="--n:2"/);
  assert.equal(D.tempoHoras(null), "");
  const t = D.tempoHoras([{ hora: 19, temp: 17.6, chuva_pct: 60, codigo: 61, marca: "chegada" }, { hora: 20, temp: null, chuva_pct: 5 }]);
  assert.match(t, /data-rot="chegada" data-h="19"/);
  assert.match(t, /data-txt="18°"/);
  assert.match(t, /<em>60%<\/em>/);
  assert.match(t, /data-txt="–"/); // sem temperatura: traco, nao numero
  assert.equal(D.levar([]), "");
  assert.match(D.levar([{ item: "casaco", titulo: "Casaco", motivo: "15° na volta, 23h" }]), /Casaco<small>15° na volta, 23h<\/small>/);
});

test("aneis: gasto enche ate a fracao; tarefas do dia em pedacos (ate 12)", () => {
  assert.match(D.anelIcone(0.5), /stroke-dasharray="66\.0 200"/);
  assert.match(D.anelIcone(3), /stroke-dasharray="131\.9 200"/); // passa do teto: anel cheio
  const p = D.anelPedacos(4, 6);
  assert.equal((p.match(/stroke="var\(--cc\)"/g) || []).length, 4);
  assert.equal((p.match(/<path/g) || []).length, 6);
  assert.equal((D.anelPedacos(10, 40).match(/<path/g) || []).length, 12);
});

test("lugar_salvo: apelido + nome do Google, circulo de 150 m, 'Nao e essa' e Mapas so do Google", () => {
  const card = (data) => Cards.renderizarCardHTML({ type: "lugar_salvo", id: "l1", data, actions: [] }, { agora: AGORA });
  const h = card({ apelido: "oficina", nome: "Mecânica Irmãos Rossi", endereco: "R. das Palmeiras, 210", raio_m: 150, de_casa_min: 14, achado: true,
    maps_url: "https://www.google.com/maps/search/?api=1&query=R.%20das%20Palmeiras" });
  assert.match(h, /class="vivo-d" data-v="lugar" style="--cc:#7fd9d0"/);
  assert.match(h, /<span class="v-t">oficina<\/span>/);
  assert.match(h, /Mecânica Irmãos Rossi/);
  assert.match(h, /<small>de casa<\/small><b>14 min<\/b>/);
  assert.match(h, /raio de 150 m/);
  assert.match(h, /data-acao="lugar_nao_e" data-apelido="oficina">Não é essa/);
  assert.match(h, /<a class="pri" href="https:\/\/www\.google\.com\/maps\/search\/\?api=1&amp;query=/);
  // sem trajeto medido: nao mostra "de casa"; link de fora do Google nao vira botao
  const s = card({ apelido: "<x>", endereco: "Rua A", maps_url: "https://mal.example/maps/" });
  assert.doesNotMatch(s, /de casa/);
  assert.doesNotMatch(s, /mal\.example/);
  assert.match(s, /&lt;x&gt;/);
  assert.match(card({ apelido: "casa", oculto: true }), /lugar salvo/);
  assert.match(card({}), /card-contrato-fallback/);
});

test("tarefa com hora (D): conta ate ela; com lugar tem rota, 'Ja sai' e '+10 min'", () => {
  const card = (data) => Cards.renderizarCardHTML({ type: "tarefas_criadas", id: "t1", data, actions: [] }, { agora: AGORA });
  const t = { id: 9, titulo: "Levar o carro", data: "2026-11-04", hora: "08:14", local: "Mecânica Rossi" };
  const h = card({ tarefas: [t], em_s: 840, gerado_ts: G });
  assert.match(h, /class="vivo-d" data-v="tarefa"[^>]*data-tarefa="9" data-hora="08:14" data-alvo="\d+"/);
  assert.match(h, /<span class="v-t">Mecânica Rossi<\/span>/);
  assert.match(h, /Levar o carro · /);
  assert.match(h, /<small>em<\/small><b><span class="rl" data-cd-s="840"[^>]*data-txt="14 min"/);
  assert.match(h, /class="v-grande"><span class="rl" data-cd-s="840"[^>]*data-fmt="mmss" data-txt="14:00"/);
  assert.match(h, /<span class="rt l">Casa<\/span>/);
  assert.match(h, /data-acao="tarefa_saiu" data-tarefa="9">Já saí/);
  assert.match(h, /data-acao="tarefa_mais10" data-tarefa="9">\+10 min/);
  // sem lugar: sem rota nem "Ja sai"; hora que ja passou: sem contagem nem botoes
  const sem = card({ tarefas: [{ ...t, local: null }], em_s: 840, gerado_ts: G });
  assert.doesNotMatch(sem, /v-rota|tarefa_saiu/);
  assert.match(sem, /tarefa_mais10/);
  const passou = card({ tarefas: [t], em_s: -60, gerado_ts: G });
  assert.match(passou, /<small>era às<\/small>/);
  assert.doesNotMatch(passou, /data-cd-s|tarefa_mais10/);
  // 23:55 + 10 passaria da meia-noite: sem o botao
  assert.doesNotMatch(card({ tarefas: [{ ...t, hora: "23:55" }], em_s: 840, gerado_ts: G }), /tarefa_mais10/);
  // sem segundos do servidor continua o card antigo
  assert.doesNotMatch(card({ tarefas: [t] }), /vivo-d/);
});

test("deslize: HTML acessivel (slider com teclado) e registro pelo nome", () => {
  const h = D.deslizaHTML("conta_paga", "deslize se já pagou", ' data-conta="4"');
  assert.match(h, /class="v-desliza" data-desliza="conta_paga" data-conta="4"/);
  assert.match(h, /role="slider" tabindex="0" aria-label="deslize se já pagou" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"/);
  assert.doesNotThrow(() => D.registrarDesliza("x", async () => true));
});

test("sem DOM nada quebra", () => {
  assert.doesNotThrow(() => D.preparar(null));
  assert.doesNotThrow(() => D.animar(null));
  assert.doesNotThrow(() => D.desfeito(null));
  assert.equal(D.tique({ querySelectorAll: () => [] }), 0);
});
