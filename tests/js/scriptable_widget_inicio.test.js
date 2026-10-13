// Tela de inicio do widget (pequeno/medio/grande) redesenhada em 2026-10-13: fundo que muda com a
// hora, cards de vidro, aneis de comida, agenda, habitos e conta. Roda o script real contra os
// mocks do Scriptable (tests/js/_scriptable_mocks.js):
//
//   node --test tests/js/scriptable_widget_inicio.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const {
  JSON_COMPLETO,
  MockListWidget,
  criarMockFileManager,
  coletarTextos,
  acharImagens,
  simbolosUsados,
  instalarGlobais,
} = require("./_scriptable_mocks");

instalarGlobais(global);
global.FileManager = criarMockFileManager();
global.config = { runsInWidget: true, widgetFamily: "small" };
global.args = { widgetParameter: "" };
global.Script = { setWidget() {}, complete() {} };
const W = require(path.join(__dirname, "..", "..", "scriptable", "scriptable-widget.js"));

test.beforeEach(() => {
  global.config = { runsInWidget: true, widgetFamily: "small" };
  global.args = { widgetParameter: "" };
  global.FileManager = criarMockFileManager();
});

const comDados = (json) => {
  global.__mockFetchHandler = async () => json;
};

async function montar(familia, json, parametro) {
  global.config.widgetFamily = familia;
  global.args = { widgetParameter: parametro || "" };
  comDados(json || JSON_COMPLETO);
  return W.montarWidget();
}

// barras de stack (adicionarBarra): trilho com tamanho fixo e o cheio dentro
function acharBarras(node) {
  const out = [];
  const visitar = (n) => {
    if (!n || !Array.isArray(n.children)) return;
    const trilho = n.backgroundColor && n.backgroundColor.hex === "#ffffff" && n.backgroundColor.alpha === 0.14;
    if (trilho && n.size && n.size.height <= 5) {
      const cheio = n.children.find((c) => c.size);
      out.push({ largura: n.size.width, cheio: cheio ? cheio.size.width : 0, cor: cheio ? cheio.backgroundColor.hex : null });
    }
    n.children.forEach(visitar);
  };
  visitar(node);
  return out;
}

function acharCartoes(node) {
  const out = [];
  const visitar = (n) => {
    if (!n || !Array.isArray(n.children)) return;
    if (n.borderWidth === 1 && n.cornerRadius === 16) out.push(n);
    n.children.forEach(visitar);
  };
  visitar(node);
  return out;
}

// ---- fundo que muda com a hora ----

test("paletaDoHorario: madrugada, manha, tarde, por do sol e noite", () => {
  const em = (h) => W.paletaDoHorario(new Date(2026, 9, 13, h, 10)).nome;
  assert.equal(em(3), "madrugada");
  assert.equal(em(8), "manha");
  assert.equal(em(13), "tarde");
  assert.equal(em(17), "por do sol");
  assert.equal(em(21), "noite");
  assert.equal(W.paletaDoHorario(new Date(2026, 9, 13, 8)).saudacao, "Bom dia");
});

test("misturarHex: interpola os canais e mantem o formato #rrggbb", () => {
  assert.equal(W.misturarHex("#000000", "#ffffff", 0), "#000000");
  assert.equal(W.misturarHex("#000000", "#ffffff", 1), "#ffffff");
  assert.equal(W.misturarHex("#000000", "#ffffff", 0.5), "#808080");
});

test("fundo: imagem desenhada (gradiente + brilhos) por cima de um gradiente de reserva", async () => {
  const w = await montar("small");
  assert.ok(w.backgroundImage, "deveria ter imagem de fundo");
  assert.ok(w.backgroundImage.tamanho.width === 170 && w.backgroundImage.tamanho.height === 170);
  assert.ok(w.backgroundGradient && w.backgroundGradient.colors.length === 2);
  const grande = await montar("large");
  assert.deepEqual([grande.backgroundImage.tamanho.width, grande.backgroundImage.tamanho.height], [364, 382]);
});

test("dataCurta: 'terça, 13 out'", () => {
  assert.equal(W.dataCurta(new Date(2026, 9, 13, 10)), "terça, 13 out");
});

// ---- o "proximo" agora inclui compromisso do iCloud ----

test("proximoDe: 1o pendente da agenda (compromisso), pulando o concluido; sem agenda cai no foco", () => {
  assert.deepEqual(W.proximoDe(JSON_COMPLETO), { titulo: "Dentista", em_minutos: 25, hora: "14:30", tipo: "compromisso" });
  const antigo = { ...JSON_COMPLETO, agenda: undefined };
  assert.equal(W.proximoDe(antigo).titulo, "Revisar contrato");
  assert.equal(W.proximoDe({ foco: null, agenda: [] }), null);
  assert.equal(W.agendaPendente(JSON_COMPLETO, 2).length, 2);
});

// ---- pequeno ----

test("pequeno: proximo (hora, pilula 'em 25 min', titulo) + aneis da comida com kcal e proteina", async () => {
  const w = await montar("small");
  const t = coletarTextos(w);
  for (const s of ["PRÓXIMO", "em 25 min", "14:30", "Dentista", "1.066", "/ 2.550 kcal", "P 102 / 115 g"]) {
    assert.ok(t.includes(s), `faltou "${s}" em ${JSON.stringify(t)}`);
  }
  const aneis = acharImagens(w).filter((n) => n.image.tracos);
  assert.equal(aneis.length, 1);
  assert.equal(aneis[0].image.tracos, 4, "2 aneis = 2 trilhos + 2 arcos");
  assert.ok(simbolosUsados(w).includes("calendar"));
  assert.equal(w.url, "http://SEU-IP-OU-DOMINIO:5001/?aba=assistente");
  assert.ok(w.refreshAfterDate instanceof Date);
});

test("pequeno sem comida: mostra o que vem depois; sem nada marcado: 'Dia livre'", async () => {
  let t = coletarTextos(await montar("small", { ...JSON_COMPLETO, comida: null }));
  assert.ok(t.includes("depois · 16:30 Revisar contrato"), JSON.stringify(t));
  t = coletarTextos(await montar("small", { ...JSON_COMPLETO, comida: null, agenda: [], foco: null }));
  assert.ok(t.includes("Dia livre"));
});

test("pequeno com Parameter 'comida': aneis grandes com a % no meio", async () => {
  const w = await montar("small", JSON_COMPLETO, "comida");
  const t = coletarTextos(w);
  assert.ok(t.includes("COMIDA HOJE"));
  assert.ok(t.includes("42%") && t.includes("kcal"), JSON.stringify(t));
  assert.ok(t.includes("1.066 / 2.550 kcal"));
  assert.ok(!t.includes("Dentista"));
});

test("pequeno com Parameter 'agenda': lista do dia, concluido com check", async () => {
  const w = await montar("small", JSON_COMPLETO, "agenda");
  const t = coletarTextos(w);
  for (const s of ["14:30", "Dentista", "16:30", "Revisar contrato", "19:00"]) assert.ok(t.includes(s), s);
  assert.ok(!t.includes("Almoço"), "agendaPendente tira o concluido");
});

test("meta de kcal batida: anel de fora fica dourado", async () => {
  const w = await montar("small", { ...JSON_COMPLETO, comida: { ...JSON_COMPLETO.comida, kcal: 2700 } }, "comida");
  assert.ok(coletarTextos(w).includes("106%"));
});

// ---- medio ----

test("medio: card de vidro com o proximo + 'depois' e coluna de comida com macros e habitos", async () => {
  const w = await montar("medium");
  const t = coletarTextos(w);
  for (const s of ["PRÓXIMO", "14:30", "Dentista", "depois · 16:30 Revisar contrato", "COMIDA HOJE", "1.066", "P 102 / 115 g", "C 118 g · G 31 g", "3/5 hábitos"]) {
    assert.ok(t.includes(s), `faltou "${s}" em ${JSON.stringify(t)}`);
  }
  assert.equal(acharCartoes(w).length, 1);
});

test("medio sem comida: a direita vira a agenda (sem coluna vazia)", async () => {
  const t = coletarTextos(await montar("medium", { ...JSON_COMPLETO, comida: null }));
  assert.ok(t.includes("DEPOIS") && t.includes("Revisar contrato") && t.includes("Aula de navegação"));
  assert.ok(!t.includes("COMIDA HOJE"));
});

test("medio com Parameter 'comida': barras de proteina (meta), carbo e gordura (fatia da energia)", async () => {
  const w = await montar("medium", JSON_COMPLETO, "comida");
  const barras = acharBarras(w);
  assert.equal(barras.length, 3);
  assert.equal(barras[0].cheio, Math.round(140 * (102 / 115)));
  const energia = 102 * 4 + 118 * 4 + 31 * 9;
  assert.equal(barras[1].cheio, Math.round(140 * ((118 * 4) / energia)));
  assert.equal(barras[2].cheio, Math.max(4, Math.round(140 * ((31 * 9) / energia))));
  assert.ok(coletarTextos(w).includes("118 g"));
});

// ---- grande ----

test("grande: saudacao, proximo em destaque, agenda com 'em X', comida, habitos e conta", async () => {
  const w = await montar("large");
  const t = coletarTextos(w);
  assert.ok(t.some((s) => /^(Bom dia|Boa tarde|Boa noite), Alex$/.test(s)), JSON.stringify(t));
  for (const s of ["PRÓXIMO", "14:30", "Dentista", "DEPOIS", "16:30", "Revisar contrato", "Aula de navegação", "Ler 20 páginas", "COMIDA HOJE", "1.066", "HÁBITOS", "3", " / 5", "Cartão · em 3 dias"]) {
    assert.ok(t.includes(s), `faltou "${s}" em ${JSON.stringify(t)}`);
  }
  assert.ok(t.includes("2h25"), "agenda mostra quanto falta");
  assert.equal(acharCartoes(w).length, 4);
  // pontinhos dos habitos desenhados
  assert.ok(acharImagens(w).some((n) => n.image.tamanho && n.image.tamanho.height === 30));
});

test("grande com payload antigo (sem agenda nem macros) e sem habitos/conta: nao quebra nem mostra undefined", async () => {
  const antigo = { ...JSON_COMPLETO, agenda: undefined, habitos: null, proxima_conta: null, comida: { kcal: 500, proteina_g: 30, refeicoes: 1, meta_kcal: null, meta_proteina_g: null } };
  const t = coletarTextos(await montar("large", antigo));
  assert.ok(t.includes("Revisar contrato"));
  assert.ok(t.includes("resto do dia livre"));
  assert.ok(t.includes("nada pra hoje"));
  assert.ok(!t.some((s) => /undefined|NaN/.test(s)), JSON.stringify(t));
});

test("conta vencendo amanha ganha cor de alerta", async () => {
  const w = await montar("large", { ...JSON_COMPLETO, proxima_conta: { nome: "Luz", em_dias: 1 } });
  assert.ok(coletarTextos(w).includes("Luz · vence amanhã"));
});

test("cache: tela de inicio mostra 'atualizado ha X' no rodape", async () => {
  await montar("medium");
  global.__mockFetchHandler = async () => {
    throw new Error("sem rede");
  };
  const w = await W.montarWidget();
  assert.ok(coletarTextos(w).some((s) => s.startsWith("atualizado")));
  assert.ok(w instanceof MockListWidget);
});
