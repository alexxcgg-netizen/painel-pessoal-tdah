// Cards do Laboratorio v4, Grupo F (static/js/cards-aviacao-lab.js): renderizam o estado final, escapam texto,
// dado faltando nao vira fallback e a conta do vento bate com a do servidor (aviacao_lab.calcular_vento).
//
//   node --test tests/js/cards_aviacao_lab.test.js
//
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const Cards = require(path.join(__dirname, "..", "..", "static", "js", "cards.js"));
const Lab = require(path.join(__dirname, "..", "..", "static", "js", "cards-aviacao-lab.js"));

const html = (type, data) => Cards.renderizarCardHTML({ type, id: "c1", data, actions: [] }, { agora: new Date(2026, 9, 30, 10, 0) });
const semFallback = (h) => assert.ok(!h.includes("card-contrato-fallback"), h);
const TIPOS = ["radar_validades", "previsao_cheque", "banca", "chair_flying", "vento_pista", "passaporte"];

test("os seis tipos estao registrados e dado vazio nao vira fallback", () => {
  for (const t of TIPOS) {
    assert.ok(Cards.temRenderizador(t), t);
    semFallback(html(t, {}));
  }
});

test("radar: pendente da CIV primeiro, botao Confirmei, regua com pontos e CMA marcado nao conferido", () => {
  const h = html("radar_validades", {
    hoje: "2026-10-30",
    itens: [
      { chave: "cma", nome: "CMA", vence: "2027-03-17", dias: 138, detalhe: "vence 17/03/2027", tom: "ok", pendente: false, verbo: "vence" },
      { chave: "civ7", nome: "Confirmar o voo de 29/10 na CIV", vence: null, dias: 0, detalhe: "o instrutor lançou? Confirma no Super App", tom: "perigo", pendente: true, voo_id: 7 },
      { chave: "fgv", nome: "Inscrição <b>FGV</b>", vence: "2026-11-17", dias: 18, detalhe: "cai em 17/11/2026", tom: "alerta", pendente: false, verbo: "cai em" },
    ],
    campos: [{ chave: "cma", nome: "CMA", modo: "vence", ajuda: "digita a data", valor: "2027-03-17" }],
  });
  semFallback(h);
  assert.match(h, /data-acao="av_civ" data-id="7"/);
  assert.ok(h.indexOf("Confirmar o voo") < h.indexOf("Inscrição"));
  assert.ok(h.indexOf("Inscrição") < h.indexOf(">CMA<"));
  assert.match(h, /Inscrição &lt;b&gt;FGV&lt;\/b&gt;/);
  assert.equal((h.match(/class="av-p"/g) || []).length, 3);
  assert.match(h, /17&nbsp;d|18&nbsp;d/); // dias recalculados com o relogio (30/10 -> 17/11 = 18 d)
  assert.match(h, /av-nc/);
  assert.match(h, /não conferido/);
  assert.match(h, /type="date" class="av-data" data-chave="cma"/);
});

test("radar vazio abre direto o formulario de datas", () => {
  const h = html("radar_validades", { itens: [], campos: [{ chave: "cma", nome: "CMA", ajuda: "", valor: null }] });
  assert.match(h, /Nenhuma data ainda/);
  assert.doesNotMatch(h, /av-datas" hidden/);
});

test("posRegua: hoje no comeco, 30 d no fim da primeira zona, 1 ano+ perto do fim", () => {
  assert.equal(Lab.posRegua(0), 1);
  assert.equal(Lab.posRegua(30), 33);
  assert.equal(Lab.posRegua(60), 65);
  assert.ok(Lab.posRegua(3000) <= 98);
});

const CHEQUE = {
  hoje: "2026-10-30", dias_mes: 30.4375, ritmo_mes: 8.7, janela_dias: 28,
  requisitos: [
    { chave: "total", nome: "Totais", h: 36, meta: 150, falta: 114, ritmo_mes: 8.7, fechou: false, data: "2027-12-01", rotulo: "dez/2027" },
    { chave: "navegacao", nome: "Navegação", h: 36, meta: 20, falta: 0, ritmo_mes: 8.7, fechou: true, data: null, rotulo: null },
    { chave: "instrumentos", nome: "Instrumentos", h: 6, meta: 10, falta: 4, ritmo_mes: 1, fechou: false, data: "2027-02-27", rotulo: "fev/2027" },
    { chave: "noturno", nome: "Noturno", h: 0.8, meta: 5, falta: 4.2, ritmo_mes: 0, fechou: false, data: null, rotulo: null },
  ],
  gargalo: "noturno", gargalo_sem_ritmo: true, data_cheque: null, rotulo_cheque: null, rotulo_sem_gargalo: "dez/2027",
  tudo_fechado: false, sem_ritmo_total: false, horas_a_voar: 114, valor_hora: 1050, custo: 119700,
  simulacao_noturno: { falta: 4.2, atual_mes: 0, outras_sem_ritmo: false, outras_max: "2027-12-01" },
  lembrete_navegacao: "A navegação de 20 h inclui uma de 300 NM.", fonte: "RBAC 61.101",
};

test("cheque: gargalo sem ritmo nao inventa data, mostra o noturno em destaque e o slider", () => {
  const h = html("previsao_cheque", CHEQUE);
  semFallback(h);
  assert.match(h, /pc-grande">—</);
  assert.match(h, /Noturno: nenhuma hora nas últimas 4 semanas/);
  assert.match(h, /Sem isso, seria dez\/2027/);
  assert.match(h, /pc-l gargalo" data-r="noturno"/);
  assert.match(h, /data-sim="cheque"/);
  assert.match(h, /R\$[\s ]119\.700/);
  assert.match(h, /ok<\/span>/); // navegacao fechada
});

test("cheque: com data mostra o mes/ano, e sem valor da hora pede o valor", () => {
  const d = Object.assign({}, CHEQUE, { gargalo: "total", gargalo_sem_ritmo: false, data_cheque: "2027-12-01", rotulo_cheque: "dez/2027", custo: null, valor_hora: null });
  const h = html("previsao_cheque", d);
  assert.match(h, /pc-grande">dez\/2027</);
  assert.match(h, /As horas totais são o que segura/);
  assert.match(h, /data-acao="av_hora"/);
});

test("cheque no modo visitante nao mostra custo nem pede valor", () => {
  const h = html("previsao_cheque", Object.assign({}, CHEQUE, { custo: undefined, valor_hora: undefined, oculto: true }));
  assert.doesNotMatch(h, /R\$/);
  assert.doesNotMatch(h, /av_hora/);
});

test("textoGrande cobre tudo fechado e sem ritmo", () => {
  assert.equal(Lab.textoGrande({ tudo_fechado: true })[1], "fechados");
  assert.equal(Lab.textoGrande({ sem_ritmo_total: true, requisitos: [] })[1], "—");
});

const BANCA = {
  hoje: "2026-10-30", questoes: 20, minimo: 70, pronto_pct: 80, pronto_seguidos: 3, foco: "MET", vencidas: 4,
  cadernos: [
    { sigla: "REG", nome: "Regulamentos", tempo_min: null, tempo_conferido: false, ultimos: [82, 85, 88], ultimo: 88, ultimo_id: 3, pronto: true, risco: false },
    { sigla: "MET", nome: "Meteorologia", tempo_min: null, tempo_conferido: false, ultimos: [65, 70, 62], ultimo: 62, ultimo_id: 6, pronto: false, risco: true },
    { sigla: "NAV", nome: "Navegação", tempo_min: 100, tempo_conferido: true, ultimos: [], ultimo: null, ultimo_id: null, pronto: false, risco: false },
    { sigla: "TV", nome: "Teoria de voo", tempo_min: null, tempo_conferido: false, ultimos: [], ultimo: null, ultimo_id: null, pronto: false, risco: false },
    { sigla: "CTA", nome: "Conhecimentos técnicos", tempo_min: null, tempo_conferido: false, ultimos: [], ultimo: null, ultimo_id: null, pronto: false, risco: false },
  ],
  revisao: [{ id: 9, sigla: "MET", enunciado: "Nevoeiro de <i>advecção</i>", resposta: "Ar úmido sobre superfície fria", explicacao: "Esfria até o orvalho.", errou_em: "2026-10-27" }],
  fonte: "IS 00-003 Rev. H",
};

test("banca: cinco colunas, linha dos 70%, risco e pronto, caderno em foco e tempo nao conferido", () => {
  const h = html("banca", BANCA);
  semFallback(h);
  assert.equal((h.match(/class="bc-col/g) || []).length, 5);
  assert.equal((h.match(/bc-linha70/g) || []).length, 5);
  assert.match(h, /bc-col pronto/);
  assert.match(h, /bc-col risco" data-acao="bc_sel" data-c="MET" aria-pressed="true"/);
  assert.match(h, /Meteorologia · tempo de prova <span class="av-nc"/);
  assert.match(h, /Abaixo de 70%: prioridade/);
  assert.match(h, /height:62%/);
  assert.match(h, /Revisão de hoje · 1 de 1/);
  assert.match(h, /Nevoeiro de &lt;i&gt;advecção/);
  assert.match(h, /errou dia 27\/10/);
  assert.match(h, /data-acao="bc_rev" data-id="9" data-ok="0"/);
});

test("banca: navegacao mostra os 100 min conferidos, sem aviso de nao conferido", () => {
  const h = Lab.raizBanca(BANCA, { sel: "NAV" });
  assert.match(h, /Navegação · 100 min</);
  assert.match(h, /Nenhum simulado registrado ainda/);
  assert.doesNotMatch(h.slice(h.indexOf("bc-det"), h.indexOf("Revisão")), /av-nc/);
});

test("banca: registrando, o passo conta acertos de 20 e mostra a porcentagem", () => {
  const h = Lab.raizBanca(BANCA, { sel: "MET", reg: true, acertos: 14 });
  assert.match(h, /14\/20 · 70%/);
  assert.match(h, /data-acao="bc_registrar"/);
});

test("banca sem revisao vencida explica a regra do Leitner", () => {
  const h = html("banca", Object.assign({}, BANCA, { revisao: [], vencidas: 0 }));
  assert.match(h, /volta amanhã/);
});

test("chair: antes de comecar mostra a nota de roteiro sem procedimento e o botao Comecar", () => {
  const d = { voo: { id: 1, icao: "SSBL", hora: "08:00" }, passos: [{ titulo: "Rolagem", texto: "Fala os callouts." }], chips: ["Rolagem", "Nada, foi liso"], nada: "Nada, foi liso", comeca_por: ["Rolagem"], personalizado: false };
  const h = html("chair_flying", d);
  semFallback(h);
  assert.match(h, /Fecha os olhos\. Tu tá no ponto de espera, em SSBL/);
  assert.match(h, /Começa por onde travou da última vez: Rolagem/);
  assert.match(h, /conteúdo certo é o do teu instrutor/);
  assert.match(h, /data-acao="cf_avancar"/);
});

test("chair: passo em andamento, fim com chips e guardado", () => {
  const d = { voo: null, passos: [{ titulo: "Rolagem", texto: "Fala os <b>callouts</b>." }, { titulo: "Subida", texto: "Faz o flow." }], chips: ["Rolagem", "Subida", "Nada, foi liso"], nada: "Nada, foi liso", comeca_por: [], personalizado: true };
  const meio = Lab.raizChair(d, { k: 0, travou: [] });
  assert.match(meio, /Fala os &lt;b&gt;callouts/);
  assert.match(meio, /Falei, próximo/);
  assert.match(Lab.raizChair(d, { k: 1, travou: [] }), /Terminar/);
  const fim = Lab.raizChair(d, { k: 2, travou: ["Subida"] });
  assert.match(fim, /Onde tu travou\?/);
  assert.match(fim, /data-t="Subida" aria-pressed="true"/);
  assert.match(fim, /data-t="Rolagem" aria-pressed="false"/);
  assert.match(fim, /data-acao="cf_guardar"/);
  assert.match(Lab.raizChair(d, { k: 2, travou: [], guardado: true }), /Guardado\./);
});

const PISTA = { cabeceiras: [18, 36], decl_w: 20.6, conferido: false, padrao_de_terceiros: true };
const VENTO = { icao: "SSBL", metar: "SSBL 301200Z 29012KT 9999 SCT030 24/17 Q1016", hora_z: "1200Z", medido: true, variavel: false, direcao: 290, velocidade: 12, rajada: null, pista: PISTA, limite_kt: 10, fonte: "x" };

test("vento: a conta do front e a mesma do servidor (290 V a 12 kt: proa 8, traves 9 na 36)", () => {
  const c = Lab.calcVento(290, 12, PISTA, true, null);
  assert.deepEqual([c.cab, c.proa, c.trav], [36, 8, 9]);
  const errada = Lab.calcVento(290, 12, PISTA, false, null);
  assert.deepEqual([errada.proa, errada.trav], [4, 11]);
  const sul = Lab.calcVento(160, 10, PISTA, false, null);
  assert.deepEqual([sul.cab, sul.proa], [18, 9]);
  const [tom, txt] = Lab.veredito(c, 10, true);
  assert.equal(tom, "alerta");
  assert.match(txt, /Voa, mas com atenção\. Través 9 kt, teu limite é 10 kt\./);
  assert.match(Lab.veredito(errada, 10, false)[1], /Conta errada: sem a declinação/);
});

test("vento: card ja nasce com a conta, METAR real, selo de nao conferido e seta na direcao magnetica", () => {
  const h = html("vento_pista", VENTO);
  semFallback(h);
  assert.match(h, /METAR 1200Z/);
  assert.match(h, /29012KT/);
  assert.match(h, /vp-trav">9 kt/);
  assert.match(h, /vp-proa">8 kt/);
  assert.match(h, /vp-cab">36</);
  assert.match(h, /rotate\(311deg\)|rotate\(310\.6/);
  assert.match(h, /vp-aviso">Pista 18\/36 e declinação de 20,6° W: <span class="av-nc"/);
  assert.match(h, /data-acao="vp_conferi"/);
  assert.match(h, /Voa, mas com atenção/);
  assert.match(h, /data-acao="vp_corrige" data-v="1" aria-pressed="true"/);
});

test("vento conferido some com o aviso e o botao; sem METAR avisa e deixa simular", () => {
  const ok = html("vento_pista", Object.assign({}, VENTO, { pista: Object.assign({}, PISTA, { conferido: true, padrao_de_terceiros: false }) }));
  assert.doesNotMatch(ok, /vp_conferi/);
  assert.match(ok, /conferidas por ti/);
  const sem = html("vento_pista", Object.assign({}, VENTO, { medido: false, metar: null, direcao: null, velocidade: null }));
  assert.match(sem, /Sem METAR de SSBL agora/);
  assert.match(sem, /sem METAR agora/);
  const vrb = html("vento_pista", Object.assign({}, VENTO, { variavel: true, direcao: null }));
  assert.match(vrb, /Vento variável no METAR/);
});

test("passaporte: carimbos paginados de 6 em 6, estatisticas e capa", () => {
  const car = Array.from({ length: 8 }, (_, i) => ({ icao: `SB${String.fromCharCode(65 + i)}${String.fromCharCode(66 + i)}`, primeiro: `2026-0${(i % 9) + 1}-12`, voos: 1, nome: null, novo: i === 7 }));
  const h = html("passaporte", { carimbos: car, horas: 41.6, aeronaves: 2, voos: 20, fonte: "diário" });
  semFallback(h);
  assert.equal((h.match(/class="pp-car[ "]/g) || []).length, 6);
  assert.match(h, /REPÚBLICA DOS VOOS/);
  assert.match(h, /página 1 de 2/);
  assert.match(h, /41,6&nbsp;h/);
  assert.match(h, /8<\/b><small>aeródromos/);
  assert.match(h, /12 JAN 26/);
  const p2 = Lab.raizPassaporte({ carimbos: car, horas: 1, aeronaves: 0 }, { pag: 1, aberto: true });
  assert.equal((p2.match(/class="pp-car[ "]/g) || []).length, 2);
  assert.match(p2, /pp-car novo/);
  assert.match(p2, /pp-livro aberto/);
});

test("passaporte vazio e com texto perigoso", () => {
  const h = html("passaporte", { carimbos: [], horas: 0, aeronaves: 0 });
  assert.match(h, /Nenhum pouso no diário ainda/);
  const x = html("passaporte", { carimbos: [{ icao: "<b>X", primeiro: "2026-01-02", voos: 1, nome: "<script>" }], horas: 1 });
  assert.doesNotMatch(x, /<script>/);
});

test("vento: cabeceira sempre com 2 digitos (SSBL e 01/19, o Alex confirmou em 04/11/2026)", () => {
  const p0119 = { cabeceiras: [1, 19], decl_w: 20.6, conferido: false, padrao_de_terceiros: true };
  const c = Lab.calcVento(290, 12, p0119, true, null);
  assert.deepEqual([c.cab, c.proa, c.trav], [1, 6, 10]);
  const h = html("vento_pista", Object.assign({}, VENTO, { pista: p0119 }));
  assert.match(h, /vp-cab">01</);
  assert.match(h, /<text x="100" y="40">19<\/text><text x="100" y="170">01<\/text>/);
  assert.match(h, /vp-aviso">Pista 01\/19 e declinação/);
});
