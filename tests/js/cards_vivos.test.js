// Cartoes vivos (static/js/cards-vivos.js + rota/treino em cards-tipos.js): o HTML ja sai no
// estado final, nada vira fallback com dado real, e todo texto passa por esc().
//
//   node --test tests/js/cards_vivos.test.js
//
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const Cards = require(path.join(__dirname, "..", "..", "static", "js", "cards.js"));
require(path.join(__dirname, "..", "..", "static", "js", "cards-tipos.js"));
const CardsVivos = require(path.join(__dirname, "..", "..", "static", "js", "cards-vivos.js"));

const html = (type, data, actions = []) => Cards.renderizarCardHTML({ type, id: "c1", data, actions });
const semFallback = (h) => assert.ok(!h.includes("card-contrato-fallback"), h);

test("edicao: antes riscado, depois em destaque, tudo escapado", () => {
  const h = html("edicao", {
    itens: [{ rotulo: "Tarefa", titulo: "<b>Contabilidade</b>", mudancas: [{ campo: "hora", de: "09:00", para: "10:30" }] }],
  });
  semFallback(h);
  assert.match(h, /<s class="vivo-de">09:00<\/s>/);
  assert.match(h, /<strong class="vivo-para">10:30<\/strong>/);
  assert.match(h, /&lt;b&gt;Contabilidade/);
  assert.match(html("edicao", { itens: [] }), /card-contrato-fallback/);
});

test("voo_resumo: total em HH:MM, meta, barras por funcao e aeronave com hifen", () => {
  const h = html("voo_resumo", {
    total_min: 2964, voos: 44, meta_horas: 150, meta_definida: false,
    por_funcao: [{ nome: "Piloto em Instrução", min: 2214 }, { nome: "Piloto em Instrução Solo", min: 660 }],
    por_aeronave: [{ nome: "PRLOM", min: 1002 }], primeiro_solo: { minutos: 1020 },
    ultimo: { data: "2025-10-21", aeronave: "PRRGS" }, dias_sem_voar: 353, simulador_min: 240,
  });
  semFallback(h);
  assert.match(h, /49:24/);
  assert.match(h, /data-meta="150"/);
  assert.match(h, /data-solo="1020"/);
  assert.match(h, /PR-LOM<b>16:42<\/b>/);
  assert.match(h, /353 dias sem voar/);
  assert.match(h, /meta de exemplo/);
  // passou da meta: o arco cresce junto
  assert.match(html("voo_resumo", { total_min: 200 * 60, voos: 1, meta_horas: 150 }), /data-meta="220"/);
});

test("clima: cena pelo texto da condicao e barras de chuva", () => {
  assert.equal(CardsVivos.cenaClima("Trovoada com granizo"), "trovoada");
  assert.equal(CardsVivos.cenaClima("pancadas de chuva"), "chuva");
  assert.equal(CardsVivos.cenaClima("céu limpo"), "limpo");
  assert.equal(CardsVivos.cenaClima("nublado"), "nublado");
  const h = html("clima", {
    lugar: "Itoupava Central",
    agora: { condicao: "chuva", temperatura: 18.4, sensacao: 17.6, umidade_pct: 96, vento_kmh: 12 },
    proximas_horas: [{ hora: 14, chuva_pct: 80 }, { hora: 15, chuva_pct: 40 }],
  });
  semFallback(h);
  assert.match(h, /data-cena="chuva"/);
  assert.match(h, /18°/);
  assert.match(h, /14h/);
});

test("gastos_resumo: rosca, legenda e modo visitante", () => {
  const h = html("gastos_resumo", {
    periodo: { de: "2026-10-01", ate: "2026-10-09" }, total: 300, quantidade: 4,
    por_categoria: [{ categoria: "mercado", valor: 200 }, { categoria: "combustivel", valor: 100 }],
  });
  semFallback(h);
  assert.equal((h.match(/stroke-dasharray/g) || []).length, 2);
  assert.match(h, /mercado/);
  const oculto = html("gastos_resumo", { oculto: true });
  assert.match(oculto, /ocultos no modo visitante/);
  assert.ok(!oculto.includes("R$"), oculto);
});

test("dia: linha do tempo com 'agora' so quando e hoje", () => {
  const d = new Date();
  const hoje = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const h = html("dia", { dia: hoje, compromissos: [{ hora: "09:00", titulo: "Contabilidade" }], tarefas_sem_hora: ["Pagar boleto"] });
  semFallback(h);
  assert.match(h, /vivo-agora/);
  assert.match(h, /data-min="540"/);
  assert.match(h, /Pagar boleto/);
  assert.ok(!html("dia", { dia: "2020-01-01", compromissos: [{ hora: "09:00", titulo: "x" }] }).includes("vivo-agora"));
});

test("viagem_janelas: dois cenarios com botao de alternar, faixas e selos", () => {
  const cenario = (ida, alta, status) => ({
    ida, alta,
    janelas: [
      { item: "passagem", inicio: "2026-10-09", fim: "2026-11-08", status, dias: 30 },
      { item: "hotel", inicio: "2026-08-10", fim: "2026-11-08", status, dias: 30 },
    ],
  });
  const h = html("viagem_janelas", {
    mes: "2027-02", dia_definido: false,
    cenarios: {
      no_feriado: cenario("2027-02-06", { nome: "Carnaval", de: "2027-02-06", ate: "2027-02-10" }, "agora"),
      fora: cenario("2027-02-15", null, "em_breve"),
    },
  });
  semFallback(h);
  assert.equal((h.match(/class="vivo-alternar"/g) || []).length, 2);
  assert.match(h, /No Carnaval/);
  assert.match(h, /vivo-selo-agora/);
  assert.match(h, /data-cenario-bloco="fora" hidden/);
  assert.equal((h.match(/class="vivo-faixa /g) || []).length, 4);
});

test("agua: copos, meta e copinhos cheios", () => {
  const h = html("agua", { copos: 3, meta: 8 });
  semFallback(h);
  assert.equal((h.match(/class="cheio"/g) || []).length, 3);
  assert.match(h, /faltam 5/);
  assert.match(h, /data-nivel="0.375"/);
  assert.match(html("agua", { oculto: true }), /Oculto no modo visitante/);
});

test("rota com traco: mapa do caminho real; sem traco: sem mapa", () => {
  const base = {
    paradas: [{ nome: "Casa", endereco: "Brusque - SC" }, { nome: "Aeroclube", endereco: "Blumenau - SC" }],
    distancia_km: 47.7, duracao_min: 52,
  };
  const comMapa = html("rota", { ...base, traco: { w: 320, h: 200, pontos: [[10, 10], [50, 60], [100, 90]], paradas: [[10, 10], [100, 90]] } });
  semFallback(comMapa);
  assert.match(comMapa, /vivo-rota-caminho" d="M10 10 L50 60 L100 90"/);
  assert.equal((comMapa.match(/vivo-rota-pino/g) || []).length, 2);
  assert.ok(!html("rota", base).includes("vivo-mapa"));
  // traco malformado nao quebra o card
  semFallback(html("rota", { ...base, traco: { pontos: [["x", 1]], paradas: [] } }));
});

test("treino: aneis da semana fechados nos dias treinados", () => {
  const semana = Array.from({ length: 7 }, (_, i) => ({ data: `2026-10-0${i + 5}`, feito: i === 0 || i === 2, hoje: i === 4 }));
  const h = html("saude_treino", { periodo: "últimos 7 dias", sessoes: [], semana, meta_semana: 4 });
  semFallback(h);
  assert.equal((h.match(/data-feito="1"/g) || []).length, 2);
  assert.match(h, /<strong>2<\/strong> de 4/);
  // sem semana (dado antigo): card continua como antes
  assert.ok(!html("saude_treino", { periodo: "hoje", sessoes: [] }).includes("vivo-semana"));
});
