// cards-aviacao.js: renderizador do briefing de voo (puro, sem DOM) + filtro de link externo.
const test = require("node:test");
const assert = require("node:assert");
const Cards = require("../../static/js/cards.js");
require("../../static/js/cards-aviacao.js");

const BASE = {
  icao: "SBNF", nome: "Navegantes", substituto_de: "SSBL", categoria: "LIFR", observado: "08:00", idade_min: 22,
  vento: { direcao: 260, variavel: false, velocidade_kt: 6, rajada_kt: null }, visibilidade_m: 3000, teto_ft: 300,
  nuvens: [{ tipo: "OVC", altura_ft: 300 }], temp: 19, orvalho: 18, qnh: 1012, fenomenos: ["chuvisco fraco"],
  taf: [{ rotulo: "Temporariamente", de: "09:00", ate: "13:00", categoria: "IFR", resumo: "teto 800 pés" }],
  metar_bruto: "METAR SBNF 131100Z 26006KT 3000 -DZ BR OVC003 19/18 Q1012", windy_url: "https://www.windy.com/?-26.880,-48.651,10",
};

function html(data, actions) {
  return Cards.renderizarListaHTML([{ type: "briefing_voo", id: "b1", data, actions: actions || [] }], { passos: [] });
}

test("briefing mostra categoria, troca de aerodromo, vento e TAF", () => {
  const h = html(BASE);
  assert.match(h, /data-categoria="LIFR"/);
  assert.match(h, /SSBL não publica METAR/);
  assert.match(h, /--dir:260deg/);
  assert.match(h, /bv-cat-IFR/);
  assert.match(h, /chuvisco fraco/);
  assert.match(h, /decisão de voar é sua/);
});

test("briefing escapa texto vindo do boletim", () => {
  const h = html({ ...BASE, fenomenos: ["<img src=x onerror=alert(1)>"], metar_bruto: "<script>x</script>" });
  assert.doesNotMatch(h, /<img src=x/);
  assert.doesNotMatch(h, /<script>x/);
});

test("vento calmo, variavel e dado faltando nao quebram", () => {
  assert.match(html({ ...BASE, vento: { direcao: 0, variavel: false, velocidade_kt: 0 } }), /bv-calmo/);
  assert.match(html({ ...BASE, vento: { direcao: null, variavel: true, velocidade_kt: 3 } }), /bv-variavel/);
  assert.doesNotThrow(() => html({ icao: "SBNF" }));
  assert.match(html({ icao: "SBNF", categoria: "XPTO" }), /data-categoria=""/);
});

test("link externo: Windy e Maps passam, outro dominio nao", () => {
  const ok = html(BASE, [{ tipo: "abrir_link", rotulo: "Abrir no Windy", url: BASE.windy_url }]);
  assert.match(ok, /href="https:\/\/www\.windy\.com\//);
  const ruim = html(BASE, [{ tipo: "abrir_link", rotulo: "x", url: "https://www.windy.com.evil.example/" }]);
  assert.doesNotMatch(ruim, /evil/);
  const ruim2 = html(BASE, [{ tipo: "abrir_link", rotulo: "x", url: "javascript:alert(1)" }]);
  assert.doesNotMatch(ruim2, /javascript:/);
});

const QUIZ = {
  id: 7, tema: "Meteorologia aeronautica", enunciado: "Qual nuvem traz trovoada?", caixa: 0, caixa_max: 5,
  alternativas: ["Cirrus", "Cumulonimbus", "Estratos", "Altocumulus"],
};
const quiz = (data) => Cards.renderizarListaHTML([{ type: "quiz_aviacao", id: "q1", data, actions: [] }], { passos: [] });

test("quiz aberto: 4 alternativas clicaveis, sem revelar a certa", () => {
  const h = quiz(QUIZ);
  assert.strictEqual((h.match(/data-acao="quiz_responder"/g) || []).length, 4);
  assert.match(h, /data-estado="aberta"/);
  assert.match(h, /Banca · Meteorologia</);
  assert.doesNotMatch(h, /qz-alt certa/);
  assert.doesNotMatch(h, / disabled/);
});

test("quiz respondido (voz/historico): estado final com certa, errada e explicacao", () => {
  const h = quiz({ ...QUIZ, resposta: { escolhida: 0, correta: 1, acertou: false, explicacao: "CB <b>vertical</b>", caixa: 0, proxima_revisao: "2099-01-01" } });
  assert.match(h, /data-estado="respondida"/);
  assert.match(h, /qz-alt certa/);
  assert.match(h, /qz-alt escolhida errada/);
  assert.match(h, /A certa é a B: Cumulonimbus/);
  assert.match(h, /CB &lt;b&gt;vertical/);
  assert.strictEqual((h.match(/ disabled/g) || []).length, 4);
});

test("quiz com dado ruim nao renderiza nem quebra", () => {
  assert.doesNotThrow(() => quiz({ id: 1, alternativas: ["a"] }));
  assert.doesNotThrow(() => quiz({ alternativas: ["a", "b", "c", "d"] }));
  assert.doesNotMatch(quiz({ ...QUIZ, enunciado: "<img src=x onerror=1>" }), /<img src=x/);
});

test("Cards.registrarAcao existe pro clique do quiz", () => {
  assert.strictEqual(typeof Cards.registrarAcao, "function");
});

// ---- voo_agendado (2026-10-14): cartao de embarque com as pernas
const VOO = {
  id: 7, data: "2099-10-17", hora: "14:00", local: false,
  paradas: [
    { icao: "SSBL", nome: "Blumenau", decola: "14:00" },
    { icao: "SBNF", nome: "Navegantes", pousa: "14:22", decola: "14:37" },
    { icao: "SBFL", nome: "Florianópolis", pousa: "15:15", decola: "15:30" },
    { icao: "SSBL", nome: "Blumenau", pousa: "16:15" },
  ],
  pernas: [{ nm: 24 }, { nm: 48 }, { nm: 58 }], total_nm: 130, duracao_min: 135, pouso: "16:15",
  antecedencia_min: 45, chegar: "13:15", sair_casa: "12:10", trajeto_min: 65, horas_min: 3726, meta_horas: 150,
};
const voo = (data) => Cards.renderizarListaHTML([{ type: "voo_agendado", id: "v1", data, actions: [] }], { passos: [] });

test("voo_agendado: pernas em NM, paradas tocaveis e horarios", () => {
  const h = voo(VOO);
  assert.match(h, /data-vivo="voo-rota"/);
  assert.strictEqual((h.match(/data-acao="voo_parada"/g) || []).length, 4);
  assert.match(h, /24 NM/);
  assert.match(h, /58 NM/);
  assert.match(h, /~130 NM/);
  assert.match(h, /Saída<\/span><b class="vivo-num">12:10/);
  assert.match(h, /Chega<\/span><b class="vivo-num">13:15<\/b><small>45 min antes/);
  assert.match(h, /~16:15/);
  assert.match(h, /data-nome="Volta pra Blumenau"/);
  assert.match(h, /data-resto="perna 1, 24 NM · pousa ~14:22, decola ~14:37"/);
  assert.match(h, /62,1 h/);
  assert.match(h, /~64,4 h/);
});

test("voo_agendado: voo local vira circuito, sem paradas tocaveis", () => {
  const h = voo({ ...VOO, local: true, paradas: [VOO.paradas[0], { icao: "SSBL", nome: "Blumenau" }], pernas: [], total_nm: null, duracao_min: null, pouso: null, sair_casa: null });
  assert.match(h, /data-vivo="voo-local"/);
  assert.doesNotMatch(h, /voo_parada/);
  assert.doesNotMatch(h, /Saída/);
  assert.match(h, /voo local/);
});

test("voo_agendado: escapa nome de aerodromo e some sem paradas", () => {
  const h = voo({ ...VOO, paradas: [{ icao: "<b>X", nome: "<img src=x>" }, VOO.paradas[1]], pernas: [{ nm: null }] });
  assert.doesNotMatch(h, /<img src=x>/);
  assert.doesNotMatch(h, /<b>X/);
  const vazio = voo({ ...VOO, paradas: [] });
  assert.doesNotMatch(vazio, /data-vivo="voo-rota"/);
});

test("voo_agendado: caminho tem um arco por perna", () => {
  const Av = require("../../static/js/cards-aviacao.js");
  const xs = Av.vaPontos(4);
  assert.deepStrictEqual(xs.map(Math.round), [10, 103, 197, 290]);
  assert.strictEqual((Av.vaCaminho(xs).match(/Q/g) || []).length, 3);
});
