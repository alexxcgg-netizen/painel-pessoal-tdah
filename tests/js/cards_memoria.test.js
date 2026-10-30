// Grupo D do Laboratorio v4 (2026-10-30): guardados, o_que_falei, neste_dia, coincidencia
// (static/js/cards-memoria.js). Renderizadores puros.
const test = require("node:test");
const assert = require("node:assert");
const Cards = require("../../static/js/cards.js");
require("../../static/js/cards-memoria.js");

const AGORA = new Date(2026, 9, 30, 9, 0);
const card = (type, data) => Cards.renderizarCardHTML({ type, id: "x1", data, actions: [] }, { agora: AGORA });

const ITENS = [
  { id: 1, objeto: "Passaporte", lugar: "gaveta azul do quarto", quando: "hoje às 02:14" },
  { id: 2, objeto: "CIV", lugar: "mochila do voo", quando: "12/10" },
];

test("guardados: achei mostra o lugar grande, quando guardou e o resto da lista", () => {
  const h = card("guardados", { modo: "achei", destaque: ITENS[0], itens: ITENS, total: 2 });
  assert.match(h, /class="sd gd" data-modo="achei"/);
  assert.match(h, /<p class="sd-hero">gaveta azul do quarto<\/p>/);
  assert.match(h, /Tu guardou hoje às 02:14/);
  assert.match(h, /Outros guardados/);
  // o destaque nao se repete na lista
  assert.doesNotMatch(h, /data-gd-id="1"/);
  assert.match(h, /data-gd-id="2"/);
});

test("guardados: guardado diz o lugar de antes quando mudou, e nao_achei nao chuta lugar", () => {
  const h = card("guardados", { modo: "guardado", destaque: { ...ITENS[0], anterior: "mochila" }, itens: ITENS, total: 2 });
  assert.match(h, /Guardado: Passaporte/);
  assert.match(h, /Antes estava em mochila/);
  const v = card("guardados", { modo: "nao_achei", busca: "carregador", itens: [], total: 0 });
  assert.match(v, /Não tenho nada guardado sobre “carregador”/);
  assert.doesNotMatch(v, /gd-lista/);
});

test("guardados: alvo de toque de 44 px (botao tirar) com rotulo, e HTML escapado", () => {
  const h = card("guardados", { modo: "lista", itens: [{ id: 9, objeto: "<img src=x>", lugar: "<b>x</b>", quando: "" }], total: 1 });
  assert.match(h, /class="gd-tirar" data-acao="gd_tirar" data-id="9" aria-label="Tirar &lt;img src=x&gt; da lista"/);
  assert.doesNotMatch(h, /<img src=x>/);
  assert.doesNotMatch(h, /<b>x<\/b>/);
  assert.match(h, /1 item/);
});

test("guardados: modo visitante e dado faltando nao quebram", () => {
  assert.match(card("guardados", { oculto: true }), /Escondido no modo visitante/);
  assert.doesNotThrow(() => card("guardados", {}));
  assert.doesNotThrow(() => card("guardados", null));
});

test("o_que_falei: frases com data (ano so quando muda) e quantas vezes", () => {
  const h = card("o_que_falei", {
    assunto: "pouso", total: 3,
    itens: [{ dia: "2026-10-21", texto: "olhar pro fim da pista" }, { dia: "2025-12-02", texto: "arredondar cedo" }],
  });
  assert.match(h, /3 vezes/);
  assert.match(h, /sobre “pouso”/);
  assert.match(h, /<span class="oq-dia">21\/10<\/span>/);
  assert.match(h, /<span class="oq-dia">02\/12\/2025<\/span>/);
  assert.match(h, /Mostrando as 2 mais recentes de 3/);
});

test("o_que_falei: texto escapado e vazio sem quebrar", () => {
  const h = card("o_que_falei", { assunto: "<x>", total: 1, itens: [{ dia: "2026-10-01", texto: "<script>alert(1)</script>" }] });
  assert.doesNotMatch(h, /<script>/);
  assert.match(card("o_que_falei", { assunto: "x", total: 0, itens: [] }), /Nada que tu tenha dito/);
  assert.match(card("o_que_falei", { oculto: true }), /Escondido no modo visitante/);
});

test("neste_dia: rotulo, data real de cada marco, icone por tipo e a regra de quando aparece", () => {
  const h = card("neste_dia", {
    rotulo: "30 de outubro",
    itens: [
      { rotulo: "Há 1 ano", quando: "29/10/2025", texto: "Primeiro voo registrado.", icone: "voo" },
      { rotulo: "Há 1 mês", quando: "29/09/2026", texto: "Supino 75 kg. Hoje: 85 kg.", icone: "saude" },
    ],
  });
  assert.match(h, /30 de outubro/);
  assert.match(h, /<small>Há 1 ano · 29\/10\/2025<\/small>/);
  assert.match(h, /Supino 75 kg\. Hoje: 85 kg\./);
  assert.match(h, /Só aparece quando a data tem algo bom/);
  assert.match(h, /style="--n:1"/);
});

const COINC = {
  tipo: "sono", periodo: "últimos 30 dias", titulo: "Noite curta pesa no teu dia.", rot_bom: "7 h+", rot_ruim: "< 6 h",
  linhas: [
    { rotulo: "Tarefas fechadas", bom: 6.1, ruim: 3.7, unidade: "" },
    { rotulo: "Delivery", bom: 12, ruim: 38, unidade: "R$ " },
  ],
  aviso: "É coincidência nos teus dados (19 noites boas × 11 noites curtas), não prova de causa.",
  detalhe: [{ dia: "2026-10-29", lado: "ruim", sono: 4.5, treinou: false, tarefas: 1, delivery: 40 }],
};

test("coincidencia: duas barras por linha, proporcionais ao maior, numeros do Alex e aviso de causa", () => {
  const h = card("coincidencia", COINC);
  assert.match(h, /Noite curta pesa no teu dia\./);
  assert.match(h, /7 h\+: 6,1/);
  assert.match(h, /&lt; 6 h: 3,7/);
  assert.match(h, /7 h\+: R\$ 12/);
  assert.match(h, /&lt; 6 h: R\$ 38/);
  // barra do maior = 1; a outra proporcional
  assert.match(h, /class="ruim" style="--w:1\.000"/);
  assert.match(h, /class="bom" style="--w:0\.316"/);
  assert.match(h, /não prova de causa/);
});

test("coincidencia: botoes Nao ligo / Quero ver mais e detalhe escondido por padrao", () => {
  const h = card("coincidencia", COINC);
  assert.match(h, /data-acao="co_ocultar" data-tipo="sono">Não ligo pra isso/);
  assert.match(h, /data-acao="co_detalhe" aria-expanded="false">Quero ver mais/);
  assert.match(h, /<div class="co-detalhe" hidden>/);
  assert.match(h, /<td>29\/10<\/td><td>4,5 h<\/td><td>1<\/td><td>R\$ 40<\/td>/);
  const sem = card("coincidencia", { ...COINC, detalhe: [] });
  assert.doesNotMatch(sem, /co_detalhe/);
});

test("coincidencia: sem linhas nao desenha nada; visitante ve so o aviso de escondido", () => {
  const vazio = Cards.renderizarCardHTML({ type: "coincidencia", id: "x", data: { ...COINC, linhas: [] }, actions: [] }, { agora: AGORA });
  assert.doesNotMatch(vazio, /co-linha/);
  assert.match(card("coincidencia", { oculto: true, tipo: "sono" }), /Escondido no modo visitante/);
});
