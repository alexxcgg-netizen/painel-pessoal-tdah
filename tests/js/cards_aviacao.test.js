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
const Av = require("../../static/js/cards-aviacao.js");
const voo = (data) => Cards.renderizarListaHTML([{ type: "voo_agendado", id: "v1", data, actions: [] }], { passos: [] });

test("voo_agendado (D, 04/11): pilula com a rota, linhas e as horas do curso", () => {
  const h = voo(VOO);
  assert.match(h, /class="vivo-d" data-v="voo"/);
  assert.match(h, /<span class="v-t">SSBL → SBNF → SBFL<\/span>/); // a volta pra casa nao repete no titulo
  assert.match(h, /Voo 14:00 · ida e volta/);
  assert.match(h, /<span>Sair de casa<\/span><span>12:10<\/span>/);
  assert.match(h, /<span>Briefing \(45 min antes\)<\/span><span>13:15<\/span>/);
  assert.match(h, /<span>Decolagem<\/span><span>14:00<\/span>/);
  assert.match(h, /<span>Pouso<\/span><span>~16:15<\/span>/);
  assert.match(h, /<span>Rota<\/span><span>130 NM · ~2h15 fora do chão<\/span>/);
  assert.match(h, /<span>Horas no curso<\/span><span>62,1 de 150<\/span>/);
  // o arco antigo (cartao de embarque) saiu
  assert.doesNotMatch(h, /voo-rota|voo_parada|va-picote/);
});

test("voo_agendado (D): voo local no titulo, sem sair de casa", () => {
  const h = voo({ ...VOO, local: true, paradas: [VOO.paradas[0], { icao: "SSBL", nome: "Blumenau" }], pernas: [], total_nm: null, duracao_min: null, pouso: null, sair_casa: null });
  assert.match(h, /SSBL · voo local/);
  assert.doesNotMatch(h, /Sair de casa/);
  assert.doesNotMatch(h, /ida e volta/);
  assert.doesNotMatch(h, /<span>Rota<\/span>/);
});

test("voo_agendado: escapa nome de aerodromo e some sem paradas", () => {
  const h = voo({ ...VOO, paradas: [{ icao: "<b>X", nome: "<img src=x>" }, VOO.paradas[1]], pernas: [{ nm: null }],
    aerodromos: [{ icao: "<b>X", nome: "<img src=x>", pista: null }] });
  assert.doesNotMatch(h, /<img src=x>/);
  assert.doesNotMatch(h, /<b>X/);
  const vazio = voo({ ...VOO, paradas: [] });
  assert.doesNotMatch(vazio, /vivo-d/);
});

test("voo_agendado (D): conta ate sair de casa em segundos do servidor, depois ate chegar e decolar", () => {
  const AG = new Date(2026, 10, 7, 7, 0);
  const g = AG.getTime() / 1000;
  const card = (extra) => Cards.renderizarCardHTML({ type: "voo_agendado", id: "v1", data: { ...VOO, data: "2026-11-07", hora: "09:00", ...extra }, actions: [] }, { agora: AG });
  const h = card({ sair_s: 600, chegar_s: 4500, decola_s: 7200, gerado_ts: g });
  assert.match(h, /<small>sai em<\/small><b><span class="rl" data-cd-s="600"/);
  assert.match(h, /data-txt="10 min"/);
  assert.match(h, /<div class="v-linha agora"><span>Sair de casa/);
  // ja saiu de casa: a contagem passa pro briefing
  const depois = card({ sair_s: -60, chegar_s: 4500, decola_s: 7200, gerado_ts: g });
  assert.match(depois, /<small>chega em<\/small>/);
  assert.match(depois, /<div class="v-linha agora"><span>Briefing/);
  // voo passou: sem contagem
  assert.doesNotMatch(card({ sair_s: -9000, chegar_s: -8000, decola_s: -60, gerado_ts: g }), /data-cd-s/);
});

test("voo_agendado (D): aerodromos com seletor e pista so quando conferida, dentro das 30 h", () => {
  const AG = new Date(2026, 9, 14, 10, 0);
  const ads = [
    { icao: "SSBL", nome: "Blumenau", pista: { cabeceiras: [1, 19], decl_w: 20.6, conferido: true } },
    { icao: "SBNF", nome: "Navegantes", pista: null },
  ];
  const card = (data, hora) => Cards.renderizarCardHTML({ type: "voo_agendado", id: "v1", data: { ...VOO, data, hora, aerodromos: ads, limite_kt: 15 }, actions: [] }, { agora: AG });
  const h = card("2026-10-15", "09:00");
  assert.match(h, /class="seg-ad" role="tablist"[^>]*style="--n:2;--i:0"/);
  assert.match(h, /role="tab" aria-selected="true" data-acao="voo_ad" data-i="0">SSBL · Blumenau/);
  assert.match(h, /data-i="1">SBNF · Navegantes/);
  assert.match(h, /class="ad-rw" style="transform:rotate\(10deg\)"/); // 01/19: pista desenhada a 010
  assert.match(h, /Buscando o METAR de SSBL/);
  assert.match(h, /data-limite="15"/);
  // fora da janela do TAF: so avisa quando aparece, sem buscar nada
  const longe = card("2026-10-20", "09:00");
  assert.match(longe, /Vento, teto e pista de SSBL e SBNF aparecem aqui a partir de 30 h antes do voo/);
  assert.doesNotMatch(longe, /ad-vivo|seg-ad/);
});

test("voo_agendado (D): METAR vira cabeceira, proa, traves e veredito (SSBL com declinacao)", () => {
  require("../../static/js/cards-aviacao-lab.js");
  const ssbl = { icao: "SSBL", pista: { cabeceiras: [1, 19], decl_w: 20.6, conferido: true } };
  const metar = (vento, extra) => ({ metar: "METAR SSBL ...", metar_categoria: "VFR", metar_decodificado: { vento, teto_ft: 2500, visibilidade_m: 9999, ...extra } });
  const v = Av.valoresAd(ssbl, metar({ direcao: 290, velocidade_kt: 12, rajada_kt: null }), 15);
  assert.strictEqual(v.cab, "01"); // 290 V + 20,6 W = 311 magnetico: a 01 tem mais proa
  assert.strictEqual(v.rwGraus, 10);
  assert.strictEqual(v.proa, "6");
  assert.strictEqual(v.trav, "10");
  assert.strictEqual(Math.round(v.seta), 311);
  assert.strictEqual(v.teto, "2.500 ft");
  assert.strictEqual(v.vis, "10+ km");
  assert.match(v.ver, /^Tranquilo\. Través 10 kt, teu limite é 15 kt\.$/); // a categoria vai no selo, nao repete
  assert.strictEqual(v.cat, "VFR");
  assert.strictEqual(v.vento, "290° 12 kt"); // a caixa mostra o vento como no METAR
  const sul = Av.valoresAd(ssbl, metar({ direcao: 160, velocidade_kt: 8 }), 15);
  assert.strictEqual(sul.cab, "19");
  assert.strictEqual(sul.rwGraus, 190);
  // aerodromo sem pista conferida: vento como veio, sem inventar cabeceira
  const nf = Av.valoresAd({ icao: "SBNF", pista: null }, metar({ direcao: 90, velocidade_kt: 8 }, { teto_ft: null }), 15);
  assert.strictEqual(nf.cab, null);
  assert.strictEqual(nf.trav, null);
  assert.strictEqual(nf.teto, "sem teto");
  assert.match(nf.ver, /não conferi, então não calculo través/);
  // calmo e variavel
  assert.strictEqual(Av.valoresAd(ssbl, metar({ direcao: 0, velocidade_kt: 0 }), 15).vento, "calmo");
  assert.strictEqual(Av.valoresAd(ssbl, metar({ direcao: null, variavel: true, velocidade_kt: 4 }), 15).cab, null);
});

// ---- 3a leva (2026-10-14): tempo na hora do voo + "quanto deu o voo?"
const AGORA = new Date(2026, 9, 14, 10, 0);
const vooEm = (data, hora) => Cards.renderizarCardHTML({ type: "voo_agendado", id: "v1", data: { ...VOO, data, hora }, actions: [] }, { agora: AGORA });

test("voo_agendado: faixa do tempo so dentro das 30 h do TAF e antes do voo passar", () => {
  assert.match(vooEm("2026-10-15", "14:00"), /class="va-tempo" data-voo-tempo="7"[^>]*hidden/);
  assert.match(vooEm("2026-10-14", "09:30"), /data-voo-tempo/, "decolou ha meia hora: ainda vale");
  assert.doesNotMatch(vooEm("2026-10-14", "08:30"), /data-voo-tempo/, "ja passou");
  assert.doesNotMatch(vooEm("2026-10-15", "17:00"), /data-voo-tempo/, "31 h: fora do TAF");
  assert.doesNotMatch(vooEm("2026-10-15", null), /data-voo-tempo/);
  assert.strictEqual(Av.tempoNaJanela({ id: "x", data: "2026-10-14", hora: "12:00" }, AGORA), false);
});

test("tempo na hora: categoria, seta pra onde o vento vai, pode ter e de onde veio", () => {
  const h = Av.tempoHTML({
    icao: "SBNF", substituto_de: "SSBL", hora: "14:00", categoria: "MVFR",
    vento: { direcao: 90, velocidade_kt: 12, rajada_kt: 22 }, teto_ft: 2500, visibilidade_m: 9999, fenomenos: ["chuva <b>"],
    pode_ter: [{ rotulo: "pode ter", categoria: "IFR", resumo: "trovoada com chuva", vento: "" }],
    aviso: "Previsão (TAF) convertida, não é liberação: a decisão é tua e do instrutor.",
  });
  assert.match(h, /Tempo às <b class="vivo-num">14:00/);
  assert.match(h, /va-cat va-cat-MVFR/);
  assert.match(h, /--dir:270deg/);
  assert.match(h, /090° <b class="vivo-num">12<\/b> kt <span class="va-rajada">G22/);
  assert.match(h, /2\.500 <small>ft/);
  assert.match(h, /10\+ km/);
  assert.match(h, /chuva &lt;b&gt;/);
  assert.match(h, /va-cat-IFR[^<]*<\/em><span><b>pode ter:<\/b> trovoada com chuva/);
  assert.match(h, /TAF de SBNF \(perto de SSBL\)/);
  const calmo = Av.tempoHTML({ icao: "SBNF", hora: "09:00", categoria: null, vento: { velocidade_kt: 0 } });
  assert.match(calmo, /calmo/);
  assert.doesNotMatch(calmo, /va-seta/);
  assert.match(calmo, /sem teto/);
});

const horas = (data) => Cards.renderizarCardHTML({ type: "voo_horas", id: "h1", data, actions: [] }, { agora: AGORA });
const VH = { id: 9, data: "2026-10-14", hora: "10:00", rota: "SSBL → SBNF → SSBL", icao: "SSBL", estimativa: 1.2, sugestoes: [1.0, 1.2, 1.4], horas: null, horas_min: 3726, meta_horas: 150 };

test("voo_horas: chips perto da estimativa, outro com passo de 0,1 e barra ate a meta", () => {
  const h = horas(VH);
  assert.doesNotMatch(h, /card-contrato-fallback/);
  assert.match(h, /Quanto deu o voo\?/);
  assert.match(h, /SSBL → SBNF → SSBL · decolou 10:00/);
  assert.strictEqual((h.match(/class="vh-chip[^"]*" data-acao="voo_horas"/g) || []).length, 3);
  assert.match(h, /class="vh-chip vh-est" data-acao="voo_horas" data-h="1.2"[^>]*><b class="vivo-num">1,2<\/b><small>estimativa/);
  assert.match(h, /data-acao="voo_horas_outro"/);
  assert.match(h, /class="vh-ajuste" hidden/);
  assert.match(h, /class="vh-salvar" data-acao="voo_horas" data-h="1.2"/);
  assert.match(h, /62,1 h/);
  assert.match(h, /Um toque e eu somo/);
});

test("voo_horas: ja respondido abre marcado (mesmo valor fora dos chips) e diz quanto falta", () => {
  const h = horas({ ...VH, horas: 1.7 });
  assert.match(h, /class="vh-chip atual" data-acao="voo_horas" data-h="1.7"/);
  assert.strictEqual((h.match(/class="vh-chip[^"]*" data-acao="voo_horas"/g) || []).length, 4);
  assert.match(h, /Somei 1,7 h — faltam 86,2 h pra meta\./);
  const batida = horas({ ...VH, horas: 1.2, horas_min: 150 * 60 });
  assert.match(batida, /meta de 150 h batida!/);
  assert.match(horas({ id: "x" }), /card-contrato-fallback/);
  assert.match(horas({ ...VH, rota: null, sugestoes: [] }), /voo local · SSBL/);
});
