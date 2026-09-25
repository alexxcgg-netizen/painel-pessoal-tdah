// tests/js/viagens_aviao.test.js - Fase 9 (C5: faixa "Viagens"). Logica PURA
// do aviaozinho da linha do tempo (static/js/secoes/vida/viagens-aviao.js):
// calculo de posicao/rotulo (calcularAviao) e montagem do HTML do cartao
// (renderAviaoHTML), sem DOM - o wiring de verdade (IntersectionObserver,
// classe .em-voo) fica pro print Playwright (ver
// tests/test_fase9_p_viagens.py e AGENTS.md/POLISH.md desta faixa).
//
//   node --test tests/js/viagens_aviao.test.js

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const ViagemAviao = require(path.join(__dirname, "..", "..", "static", "js", "secoes", "vida", "viagens-aviao.js"));

function dia(iso) {
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]), 12, 0, 0);
}

function isoDe(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function somarDias(d, n) {
  const r = new Date(d.getTime());
  r.setDate(r.getDate() + n);
  return r;
}

// ---- calcularAviao: contrato do briefing (C5) ----

test("antes do inicio da janela: fracao 0 (aviao no comeco da linha)", () => {
  const ida = dia("2026-12-01");
  const inicio = isoDe(somarDias(ida, -60));
  const agora = somarDias(ida, -90); // antes do inicio calculado
  const r = ViagemAviao.calcularAviao(isoDe(ida), inicio, agora);
  assert.ok(r);
  assert.equal(r.fracao, 0);
  assert.equal(r.percentual, 0);
  assert.ok(r.diasFaltam > 0);
  assert.match(r.rotulo, /^faltam \d+ dias?$/);
});

test("no meio da janela: fracao proporcional (~50%)", () => {
  const ida = dia("2026-12-01");
  const inicioD = somarDias(ida, -60);
  const agora = somarDias(inicioD, 30); // metade do caminho entre inicio e ida
  const r = ViagemAviao.calcularAviao(isoDe(ida), isoDe(inicioD), agora);
  assert.ok(r);
  assert.ok(Math.abs(r.fracao - 0.5) < 0.02, `esperava ~0.5, veio ${r.fracao}`);
  assert.equal(r.diasFaltam, 30);
  assert.equal(r.rotulo, "faltam 30 dias");
});

test("sem inicio (criado_em invalido/ausente): usa ida - 60 dias como 0%", () => {
  const ida = dia("2026-12-01");
  const r = ViagemAviao.calcularAviao(isoDe(ida), null, somarDias(ida, -30));
  assert.ok(r);
  // ida - 30 fica exatamente na metade de uma janela de 60 dias
  assert.ok(Math.abs(r.fracao - 0.5) < 0.02, `esperava ~0.5, veio ${r.fracao}`);
});

test("no dia da viagem: fracao 1 (100%), rotulo 'viagem hoje'", () => {
  const ida = dia("2026-12-01");
  const r = ViagemAviao.calcularAviao(isoDe(ida), isoDe(somarDias(ida, -60)), ida);
  assert.ok(r);
  assert.equal(r.fracao, 1);
  assert.equal(r.percentual, 100);
  assert.equal(r.diasFaltam, 0);
  assert.equal(r.rotulo, "viagem hoje");
  assert.equal(r.passou, false);
});

test("depois da data: fracao continua 1 (100%), rotulo 'já passou'", () => {
  const ida = dia("2026-12-01");
  const r = ViagemAviao.calcularAviao(isoDe(ida), isoDe(somarDias(ida, -60)), somarDias(ida, 5));
  assert.ok(r);
  assert.equal(r.fracao, 1);
  assert.equal(r.percentual, 100);
  assert.ok(r.diasFaltam < 0);
  assert.equal(r.rotulo, "já passou");
  assert.equal(r.passou, true);
});

test("singular: 'faltam 1 dia' (sem 's')", () => {
  const ida = dia("2026-12-01");
  const r = ViagemAviao.calcularAviao(isoDe(ida), isoDe(somarDias(ida, -60)), somarDias(ida, -1));
  assert.equal(r.diasFaltam, 1);
  assert.equal(r.rotulo, "faltam 1 dia");
});

test("data_ida invalida/ausente: devolve null (nunca quebra o card)", () => {
  assert.equal(ViagemAviao.calcularAviao(undefined, null, new Date()), null);
  assert.equal(ViagemAviao.calcularAviao("", null, new Date()), null);
  assert.equal(ViagemAviao.calcularAviao("data-invalida", null, new Date()), null);
});

// ---- marcosParaTrilha: passagem/hotel/seguro + embarque, mesma janela ----

test("marcosParaTrilha: so os marcos presentes viram ponto, embarque sempre em 100%", () => {
  const ida = dia("2026-12-01");
  const inicio = isoDe(somarDias(ida, -60));
  const marcos = [
    { chave: "passagem", titulo: "Melhor janela pra comprar a passagem", data: isoDe(somarDias(ida, -45)) },
    { chave: "hospedagem", titulo: "Reservar hospedagem", data: isoDe(somarDias(ida, -21)) },
    { chave: "checkin", titulo: "Check-in online libera", data: isoDe(somarDias(ida, -1)) },
  ];
  const pontos = ViagemAviao.marcosParaTrilha(marcos, isoDe(ida), inicio);
  const chaves = pontos.map((p) => p.chave);
  assert.deepEqual(chaves, ["passagem", "hospedagem", "embarque"]); // checkin nao faz parte da trilha (so passagem/hotel/seguro/embarque)
  const embarque = pontos.find((p) => p.chave === "embarque");
  assert.equal(embarque.fracao, 1);
  assert.equal(embarque.rotulo, "embarque");
  const passagem = pontos.find((p) => p.chave === "passagem");
  assert.ok(passagem.fracao > 0 && passagem.fracao < 1);
});

test("marcosParaTrilha: viagem internacional acrescenta 'seguro'", () => {
  const ida = dia("2026-12-01");
  const marcos = [
    { chave: "passagem", data: isoDe(somarDias(ida, -120)) },
    { chave: "seguro", data: isoDe(somarDias(ida, -30)) },
    { chave: "hospedagem", data: isoDe(somarDias(ida, -45)) },
  ];
  const pontos = ViagemAviao.marcosParaTrilha(marcos, isoDe(ida), isoDe(somarDias(ida, -150)));
  assert.deepEqual(
    pontos.map((p) => p.rotulo),
    ["passagem", "hotel", "seguro", "embarque"]
  );
});

// ---- renderAviaoHTML: o SVG do aviao existe no card ----

test("renderAviaoHTML: cartao com SVG do aviao, faltando N dias e marcos", () => {
  const ida = dia("2026-12-20"); // ~19 dias de "hoje" no cenario de exemplo do briefing
  const agora = somarDias(ida, -19);
  const viagem = {
    destino: "Lisboa",
    data_ida: isoDe(ida),
    criado_em: isoDe(somarDias(ida, -150)) + " 10:00:00",
    internacional: true,
    marcos_planejamento: [
      { chave: "passagem", titulo: "Melhor janela pra comprar a passagem", data: isoDe(somarDias(ida, -120)) },
      { chave: "documento", titulo: "Conferir visto/passaporte valido", data: isoDe(somarDias(ida, -90)) },
      { chave: "seguro", titulo: "Contratar seguro viagem", data: isoDe(somarDias(ida, -30)) },
      { chave: "hospedagem", titulo: "Reservar hospedagem", data: isoDe(somarDias(ida, -45)) },
      { chave: "checkin", titulo: "Check-in online libera", data: isoDe(somarDias(ida, -2)) },
    ],
  };
  const html = ViagemAviao.renderAviaoHTML(viagem, agora);
  assert.match(html, /class="viagem-aviao-card"/);
  assert.match(html, /<svg viewBox="0 0 24 24" class="viagem-aviao-svg"/);
  assert.match(html, /viagem-aviao-marco-embarque/);
  assert.match(html, /viagem-aviao-marco-passagem/);
  assert.match(html, /viagem-aviao-marco-seguro/);
  assert.match(html, /faltam 19 dias/);
  assert.match(html, /--aviao-fracao:/);
});

test("renderAviaoHTML: marcos empilhados no mesmo ponto ganham raias verticais distintas (sem rotulo sobreposto)", () => {
  // viagem criada no mesmo dia da ida-19 (curto prazo): passagem/hotel/seguro
  // (antecedencia de 120/45/30 dias) caem todos ANTES do inicio da janela
  // (criado_em) e colam em fracao 0 - cenario real do print desta faixa.
  const ida = dia("2026-12-20");
  const agora = somarDias(ida, -19);
  const viagem = {
    destino: "Lisboa",
    data_ida: isoDe(ida),
    criado_em: isoDe(agora) + " 09:00:00",
    marcos_planejamento: [
      { chave: "passagem", data: isoDe(somarDias(ida, -120)) },
      { chave: "hospedagem", data: isoDe(somarDias(ida, -45)) },
      { chave: "seguro", data: isoDe(somarDias(ida, -30)) },
    ],
  };
  const html = ViagemAviao.renderAviaoHTML(viagem, agora);
  // as 3 caem em 0.00% - tem que ter raias diferentes (top:14/26/38), nao os 3 no mesmo y
  const tops = [...html.matchAll(/viagem-aviao-marco-rotulo[^"]*" style="top:(\d+)px"/g)].map((m) => m[1]);
  assert.deepEqual(new Set(tops).size, tops.length, "duas raias iguais - rotulos vao se sobrepor");
  assert.ok(tops.length >= 2, `esperava pelo menos 2 marcos com raia>0, veio ${JSON.stringify(tops)}`);
});

test("renderAviaoHTML: aviao/legenda perto da borda ganham ancora na borda (nao ficam cortados pelo overflow:hidden)", () => {
  const ida = dia("2026-12-20");
  // fracao 0 (agora == inicio == criado_em): legenda "faltam 19 dias" tem
  // que ancorar em viagem-aviao-borda-inicio, nao ficar centrada em 0%
  const agora = somarDias(ida, -19);
  const html0 = ViagemAviao.renderAviaoHTML(
    { destino: "Lisboa", data_ida: isoDe(ida), criado_em: isoDe(agora) + " 09:00:00" },
    agora
  );
  assert.match(html0, /class="viagem-aviao-legenda viagem-aviao-borda-inicio"/);

  // fracao 1 (no dia ou depois): legenda tem que ancorar em borda-fim
  const html1 = ViagemAviao.renderAviaoHTML(
    { destino: "Lisboa", data_ida: isoDe(ida), criado_em: isoDe(somarDias(ida, -60)) },
    ida
  );
  assert.match(html1, /class="viagem-aviao-legenda viagem-aviao-borda-fim"/);

  // marco "embarque" e sempre fracao 1 -> sempre borda-fim tambem
  assert.match(html1, /viagem-aviao-marco-embarque[\s\S]*?viagem-aviao-marco-rotulo viagem-aviao-borda-fim/);
});

test("renderAviaoHTML: viagem sem data_ida valida devolve string vazia (nunca quebra)", () => {
  assert.equal(ViagemAviao.renderAviaoHTML({ destino: "X" }), "");
  assert.equal(ViagemAviao.renderAviaoHTML(null), "");
});

test("renderAviaoHTML: escapa HTML do destino no aria-label (sem XSS)", () => {
  const html = ViagemAviao.renderAviaoHTML({
    destino: '<img src=x onerror="alert(1)">',
    data_ida: "2026-12-01",
  }, dia("2026-11-01"));
  assert.ok(!html.includes("<img"));
});
