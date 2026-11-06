// Viagem planejada + abastecimento (static/js/cards-viagem.js, leva "painel mais esperto" 06/11/2026):
// o card `viagem` e o card de rota (mapa) com postos/chuva/lento/noite por saida, 3 chips de saida, linha
// do tempo, tanque e numeros; `abastecimento` na casca D. Puro, sem DOM.
//
//   node --test tests/js/cards_viagem.test.js
//
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const js = (f) => path.join(__dirname, "..", "..", "static", "js", f);
const Cards = require(js("cards.js"));
require(js("cards-d.js"));
require(js("cards-tipos.js"));
const V = require(js("cards-viagem.js"));

const TRACO = {
  w: 320,
  h: 200,
  pontos: [[20, 180], [100, 140], [200, 80], [300, 20]],
  paradas: [[20, 180], [300, 20]],
  lentos: [],
  km: [0, 200, 400, 600],
};

function saida(hora, extra) {
  return {
    hora,
    saida_em: `2026-11-07T${hora}`,
    chegada_em: "2026-11-07T14:15",
    chega: "14:15",
    duracao_total_min: 495,
    transito_min: 4,
    litros: 51,
    lentos: [{ nivel: "parado", de_km: 300, ate_km: 302.5, frase: "Parado na BR-000 (2,5 km) - pode ser acidente ou blitz" }],
    chuva: [{ tipo: "chuva", de_km: 100, ate_km: 200, hora: "10:30", frase: "Chuva do km 100 ao 200, entre 10h30 e 12h - 80% de chance" }],
    noite: [],
    postos: [{ km: 500, nome: "Posto Rodovia 24h", lat: -22.5, lng: -48.9, h24: true, ate: null, litros: 38, desvio_min: 0 }],
    eventos: [
      { hora, tipo: "", titulo: "Sai de casa", sub: "tanque cheio (estimativa)" },
      { hora: "11:59", tipo: "posto", titulo: "Abastece em Posto Rodovia 24h (km 500)", sub: "aberto 24 h · ~38 L" },
      { hora: "14:15", tipo: "fim", titulo: "Chega em Destino Teste", sub: "" },
    ],
    dica: "Pega chuva do km 100 ao 200 e chega com luz do dia.",
    maps_url: `https://www.google.com/maps/dir/?api=1&h=${hora}`,
    waze_url: "https://waze.com/ul?ll=-22.50000,-48.90000&navigate=yes",
    waze_para: "Posto Rodovia 24h",
    ...extra,
  };
}

const BASE = {
  id: 7,
  destino: "Destino Teste",
  origem: "casa",
  quando: "sábado",
  total_km: 600,
  traco: TRACO,
  saidas: [saida("05:00"), saida("06:00", { noite: [{ de_km: 520, ate_km: 600 }] }), saida("08:00", { chuva: [] })],
  escolhida: 1,
  pedida: 1,
  melhor: 0,
  frase_melhor: "Melhor sair 05:00: chega antes de escurecer.",
  aviso_noite: "80 km de noite (pôr do sol 18:52)",
  tanque: { litros: 48, fracao: 1, tanque_l: 48, conferido: false, km_l: 13, reserva_km: 60, texto: "Estimativa: tanque de 48 L (a confirmar)." },
  custos: [306, 306, 306],
};
const ACOES = [
  { tipo: "abrir_link", rotulo: "Abrir no Maps", url: "https://www.google.com/maps/dir/?api=1&h=06:00" },
  { tipo: "abrir_link", rotulo: "Waze até Posto Rodovia 24h", url: "https://waze.com/ul?ll=-22.50000,-48.90000&navigate=yes" },
];

test("viagem: mapa da rota com camada por saida, so a escolhida acesa, chips e linha do tempo", () => {
  const html = Cards.renderizarCardHTML({ type: "viagem", data: BASE, actions: ACOES });
  assert.match(html, /card-contrato-viagem/);
  assert.match(html, /Rota · viagem · sábado/);
  assert.match(html, /vivo-rota-mapa/); // o mesmo mapa do card de rota (o carrinho anda pelo cards-vivos.js)
  assert.equal((html.match(/class="cv-camada"/g) || []).length, 3);
  assert.match(html, /class="cv-camada" data-cv-s="1" data-on/);
  assert.ok(!/class="cv-camada" data-cv-s="0" data-on/.test(html));
  assert.match(html, /cv-posto-pino/);
  assert.match(html, /vivo-rota-tempo card-rota-tempo--chuva/);
  assert.match(html, /vivo-rota-lento vivo-rota-lento--parado/);
  assert.match(html, /cv-rota-noite/);
  // camada vem antes do carrinho (por cima do caminho, por baixo do carro)
  assert.ok(html.indexOf("cv-camada") < html.indexOf("vivo-rota-carro"));
  assert.match(html, /data-acao="viagem_saida" data-i="1" data-viagem="7" aria-pressed="true">06:00/);
  assert.match(html, /cv-chip cv-chip--melhor/);
  assert.match(html, /Melhor sair 05:00/);
  assert.match(html, /cv-faixa-posto/);
  assert.match(html, /cv-faixa-noite/);
  assert.match(html, /Abastece em Posto Rodovia 24h \(km 500\)/);
  assert.match(html, /cv-ev--fim/);
  assert.match(html, /R\$(\u00a0|&nbsp;)306/);
  assert.match(html, /Estimativa: tanque de 48 L \(a confirmar\)/);
  assert.match(html, /600 km · 8h15/);
  assert.match(html, /href="https:\/\/www\.google\.com\/maps\/dir\/\?api=1&amp;h=06:00"/);
  // nada da "cara de IA"
  assert.ok(!/card-premium|fio-luz|selo-brilho/.test(html));
});

test("viagem: escapa HTML vindo do servidor", () => {
  const ruim = "<img src=x onerror=alert(1)>";
  const data = {
    ...BASE,
    destino: ruim,
    frase_melhor: ruim,
    saidas: [saida("06:00", { dica: ruim, postos: [{ km: 500, nome: ruim, h24: true }], eventos: [{ hora: "06:00", tipo: "<b>", titulo: ruim, sub: ruim }] })],
    escolhida: 0,
  };
  const html = Cards.renderizarCardHTML({ type: "viagem", data, actions: [] });
  assert.ok(!html.includes("<img"), html);
  assert.match(html, /&lt;img/);
  assert.ok(!html.includes("cv-ev--<b>"));
});

test("viagem: dado faltando nao quebra (sem traco.km, sem tanque, sem custo, sem chips)", () => {
  const sem = Cards.renderizarCardHTML({
    type: "viagem",
    data: { destino: "X", saidas: [{ hora: "06:00" }], traco: { ...TRACO, km: undefined } },
    actions: [],
  });
  assert.match(sem, /card-contrato-viagem/);
  assert.ok(!sem.includes("cv-camada"));
  assert.ok(!sem.includes("cv-chips"));
  assert.ok(!sem.includes("cv-tanque"));
  assert.ok(!sem.includes("Custo"));
  // sem saida valida / sem destino: fallback
  assert.match(Cards.renderizarCardHTML({ type: "viagem", data: { destino: "X", saidas: [] } }), /card-contrato-fallback/);
  assert.match(Cards.renderizarCardHTML({ type: "viagem", data: { saidas: [{ hora: "06:00" }] } }), /card-contrato-fallback/);
  // visitante: custos fora
  const vis = Cards.renderizarCardHTML({ type: "viagem", data: { ...BASE, custos: undefined, oculto: true }, actions: [] });
  assert.ok(!vis.includes("Custo"));
});

test("geometria: ponto e trecho pelo km do traco", () => {
  const g = V.pontosKm(TRACO);
  assert.deepEqual(V.noKm(g, 0), [20, 180]);
  assert.deepEqual(V.noKm(g, 100), [60, 160]);
  assert.deepEqual(V.noKm(g, 9999), [300, 20]);
  assert.equal(V.trechoKm(g, 100, 300), "M60 160 L100 140 L150 110");
  assert.equal(V.trechoKm(g, 300, 100), "");
  assert.equal(V.pontosKm({ ...TRACO, km: [0, 1] }), null);
  assert.equal(V.pontosKm(null), null);
  assert.equal(V.fmtDur(495), "8h15");
  assert.equal(V.fmtDur(45), "45 min");
});

test("abastecimento: pilula D com tanque estimado, consumo e Desfazer; dinheiro some no visitante", () => {
  const data = {
    litros: 41.5,
    valor: 249,
    preco_litro: 6,
    cheio: true,
    lugar: "Posto Teste",
    carro: "Carro Teste",
    consumo: null,
    consumo_padrao: { estrada: 13, cidade: 10 },
    tanque: { litros: 48, fracao: 1, tanque_l: 48, tanque_conferido: false, autonomia_km: 624, margem_l: 4.8 },
    dica: "Diz o hodômetro quando encher o tanque.",
  };
  const html = Cards.renderizarCardHTML({ type: "abastecimento", data, actions: [{ tipo: "desfazer", token: "t1" }] });
  assert.match(html, /card-d/);
  assert.match(html, /Tanque cheio/);
  assert.match(html, /Posto Teste/);
  assert.match(html, /dá uns 624 km/);
  assert.match(html, /a confirmar/);
  assert.match(html, /41,5 L/);
  assert.match(html, /R\$(\u00a0|&nbsp;)249/);
  assert.match(html, /13 estrada · 10 cidade \(de partida\)/);
  assert.match(html, /data-acao="desfazer" data-token="t1"/);
  const vis = Cards.renderizarCardHTML({ type: "abastecimento", data: { ...data, valor: undefined, preco_litro: undefined, oculto: true }, actions: [] });
  assert.ok(!vis.includes("R$"));
  const ruim = Cards.renderizarCardHTML({ type: "abastecimento", data: { litros: 30, lugar: "<script>x</script>" }, actions: [] });
  assert.ok(!ruim.includes("<script>"));
  assert.match(ruim, /Abasteceu 30 L/);
  assert.match(Cards.renderizarCardHTML({ type: "abastecimento", data: {} }), /card-contrato-fallback/);
});

test("rota comum: +N min de transito com a hora prevista da saida (so HH:MM valido)", () => {
  const base = { paradas: [{ nome: "A" }, { nome: "B" }], transito_min: 12 };
  const com = Cards.renderizarCardHTML({ type: "rota", data: { ...base, transito_saida: "19:00" }, actions: [] });
  assert.match(com, /\+12 min de trânsito <span class="card-rota-transito-quando">previsto pra saída das 19:00<\/span>/);
  const ruim = Cards.renderizarCardHTML({ type: "rota", data: { ...base, transito_saida: "<b>" }, actions: [] });
  assert.ok(!ruim.includes("previsto"));
});
