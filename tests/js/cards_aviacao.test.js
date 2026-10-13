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
