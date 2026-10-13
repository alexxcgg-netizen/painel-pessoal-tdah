// Testes dos modos do widget de TELA DE BLOQUEIO do Scriptable (redondo, retangular e linha), escolhidos
// pelo parametro do widget. Roda o script real contra a simulacao do Scriptable, com `node --test`:
//
//   node --test tests/js/scriptable_widget_bloqueio.test.js
//
// Mesmo setup de scriptable_widget.test.js (globais antes do require, reset a cada teste).
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const {
  JSON_COMPLETO,
  MockDrawContext,
  criarMockFileManager,
  coletarTextos,
  coletarCores,
  acharImagens,
  simbolosUsados,
  instalarGlobais,
} = require("./_scriptable_mocks");

const CAMINHO_SCRIPT = path.join(__dirname, "..", "..", "scriptable", "scriptable-widget.js");

// O mock de DrawContext nao guarda as bolinhas (fillEllipse); aqui elas passam a ser contadas na imagem
// final pra os testes conferirem quantas bolinhas/pontos foram desenhados.
const getImageOriginal = MockDrawContext.prototype.getImage;
MockDrawContext.prototype.fillEllipse = function (rect) {
  (this.elipses = this.elipses || []).push(rect);
};
MockDrawContext.prototype.getImage = function () {
  const img = getImageOriginal.call(this);
  img.elipses = (this.elipses || []).slice();
  return img;
};

function prepararGlobaisBase() {
  instalarGlobais(global);
  global.FileManager = criarMockFileManager();
  global.config = { runsInWidget: true, widgetFamily: "accessoryRectangular" };
  global.args = { widgetParameter: "" };
  global.Script = { _widget: null, setWidget() {}, complete() {} };
  global.__mockFetchHandler = null;
}

prepararGlobaisBase();
const w = require(CAMINHO_SCRIPT);

test.beforeEach(() => {
  global.config = { runsInWidget: true, widgetFamily: "accessoryRectangular" };
  global.args = { widgetParameter: "" };
  global.FileManager = criarMockFileManager();
  global.__mockFetchHandler = null;
});

function handlerSucesso(json) {
  return async () => json;
}

async function montar(familia, parametro, dados) {
  global.config.widgetFamily = familia;
  global.args = { widgetParameter: parametro || "" };
  global.__mockFetchHandler = handlerSucesso(dados === undefined ? JSON_COMPLETO : dados);
  return w.montarWidget();
}

const RET = "accessoryRectangular";
const CIRC = "accessoryCircular";
const LINHA = "accessoryInline";

// payload de antes da agenda/macros: sem `agenda`, sem carbo_g/gordura_g
const JSON_VELHO = (() => {
  const v = JSON.parse(JSON.stringify(JSON_COMPLETO));
  delete v.agenda;
  delete v.comida.carbo_g;
  delete v.comida.gordura_g;
  v.foco = { titulo: "Revisar contrato", em_minutos: 19, hora: "14:30" };
  return v;
})();

const JSON_SEM_NADA = {
  ...JSON_COMPLETO,
  foco: null,
  habitos: null,
  comida: null,
  agenda: [],
};

// itens da agenda com campos faltando (hora, em_minutos, tipo)
const JSON_AGENDA_TORTA = {
  ...JSON_COMPLETO,
  foco: null,
  agenda: [
    { titulo: "Sem hora", concluido: false },
    { hora: "15:00", titulo: "Sem minutos", tipo: "tarefa", concluido: false },
    { hora: "16:00", em_minutos: "abc", titulo: "Minutos ruins", concluido: false },
  ],
};

// barra desenhada (imagemBarra): 1o preenchimento = trilho, 2o = parte cheia (desenhada em 3x)
function fracaoDaBarra(imagemNode) {
  const [trilho, cheio] = imagemNode.image.preenchimentos;
  return cheio ? cheio.largura / trilho.largura : 0;
}

const semSimbolos = (node) => acharImagens(node).filter((n) => !n.image.simbolo);

function semCorCustomizada(widget, rotulo) {
  assert.equal(coletarCores(widget).length, 0, `${rotulo}: lock screen nao pode setar textColor`);
  assert.equal(widget.backgroundColor, null, `${rotulo}: lock screen nao pode setar backgroundColor`);
}

// ============================================================
// modoDoWidget / modoParaFamilia
// ============================================================

test("modoDoWidget: apelidos, sem acento, sem diferenca de maiuscula, comeco da palavra", () => {
  const casos = [
    ["", "ambos"],
    ["comida", "comida"],
    ["Comida", "comida"],
    ["kcal", "comida"],
    ["proximo", "proximo"],
    ["PRÓXIMO", "proximo"],
    ["Próximo", "proximo"],
    ["aneis", "aneis"],
    ["Anéis", "aneis"],
    ["anel", "aneis"],
    ["proteina", "proteina"],
    ["Proteína", "proteina"],
    ["prot", "proteina"],
    ["contagem", "contagem"],
    ["tempo", "contagem"],
    ["Tempo restante", "contagem"],
    ["habitos", "habitos"],
    ["Hábitos", "habitos"],
    ["agenda", "agenda"],
    ["AGENDA", "agenda"],
    ["dia", "dia"],
    ["Dia", "dia"],
    ["macros", "macros"],
    ["Macro", "macros"],
    ["qualquer coisa", "ambos"],
    // configuracao (URL|TOKEN) nunca e modo
    ["https://meu-pc.exemplo.ts.net:8443|tok", "ambos"],
    ["https://meu-pc.exemplo.ts.net:8443", "ambos"],
    ["http://agenda.local", "ambos"],
    ["agenda|tok", "ambos"],
  ];
  for (const [parametro, esperado] of casos) {
    global.args = { widgetParameter: parametro };
    assert.equal(w.modoDoWidget(), esperado, JSON.stringify(parametro));
  }
});

test("modoParaFamilia: modo que so existe em outra familia vira o mais parecido", () => {
  assert.equal(w.modoParaFamilia("agenda", CIRC), "proximo");
  assert.equal(w.modoParaFamilia("dia", CIRC), "contagem");
  assert.equal(w.modoParaFamilia("macros", CIRC), "aneis");
  assert.equal(w.modoParaFamilia("aneis", RET), "comida");
  assert.equal(w.modoParaFamilia("proteina", RET), "comida");
  assert.equal(w.modoParaFamilia("contagem", RET), "proximo");
  assert.equal(w.modoParaFamilia("dia", LINHA), "contagem");
  assert.equal(w.modoParaFamilia("habitos", CIRC), "habitos");
  assert.equal(w.modoParaFamilia("ambos", RET), "ambos");
});

// ============================================================
// Funcoes puras
// ============================================================

test("tempoCompacto: agora, minutos, horas", () => {
  assert.equal(w.tempoCompacto(0), "agora");
  assert.equal(w.tempoCompacto(25), "25m");
  assert.equal(w.tempoCompacto(59), "59m");
  assert.equal(w.tempoCompacto(60), "1h");
  assert.equal(w.tempoCompacto(95), "1h35");
  assert.equal(w.tempoCompacto(125), "2h05");
  assert.equal(w.tempoCompacto(-5), "agora");
  assert.equal(w.tempoCompacto(undefined), "agora");
});

test("fracaoContagem: esvazia conforme chega (janela de 2h), nunca NaN", () => {
  assert.equal(w.fracaoContagem(0), 0);
  assert.equal(w.fracaoContagem(60), 0.5);
  assert.equal(w.fracaoContagem(120), 1);
  assert.equal(w.fracaoContagem(500), 1);
  assert.equal(w.fracaoContagem(-10), 0);
  assert.equal(w.fracaoContagem(undefined), 0);
  assert.equal(w.fracaoContagem("abc"), 0);
  assert.equal(w.fracaoContagem(null), 0);
});

test("habitosDe: so com total > 0; feitos nunca passa do total", () => {
  assert.deepEqual(w.habitosDe({ habitos: { feitos: 3, total: 5 } }), { feitos: 3, total: 5 });
  assert.deepEqual(w.habitosDe({ habitos: { feitos: 9, total: 5 } }), { feitos: 5, total: 5 });
  assert.equal(w.habitosDe({ habitos: { feitos: 0, total: 0 } }), null);
  assert.equal(w.habitosDe({ habitos: null }), null);
  assert.equal(w.habitosDe({}), null);
  assert.equal(w.habitosDe(null), null);
});

test("macrosDe: fatia de energia P*4 / C*4 / G*9; null se faltar carbo ou gordura", () => {
  const m = w.macrosDe(JSON_COMPLETO.comida);
  assert.deepEqual(
    m.map((x) => x.letra),
    ["P", "C", "G"]
  );
  const soma = 102 * 4 + 118 * 4 + 31 * 9;
  assert.ok(Math.abs(m[0].frac - (102 * 4) / soma) < 1e-9);
  assert.ok(Math.abs(m[1].frac - (118 * 4) / soma) < 1e-9);
  assert.ok(Math.abs(m[2].frac - (31 * 9) / soma) < 1e-9);
  assert.ok(Math.abs(m[0].frac + m[1].frac + m[2].frac - 1) < 1e-9);
  assert.equal(m[0].meta, 115);
  assert.equal(m[1].meta, null);
  assert.equal(w.macrosDe(JSON_VELHO.comida), null);
  assert.equal(w.macrosDe(null), null);
  // tudo zero: sem divisao por zero
  const zero = w.macrosDe({ proteina_g: 0, carbo_g: 0, gordura_g: 0 });
  assert.deepEqual(
    zero.map((x) => x.frac),
    [0, 0, 0]
  );
});

test("truncar / linhaDoProximo: o 'em 25 min' nunca e cortado", () => {
  assert.equal(w.truncar("abcdef", 10), "abcdef");
  assert.equal(w.truncar("abcdefghij", 5), "abcd…");
  assert.equal(w.truncar(undefined, 5), "");
  assert.equal(w.linhaDoProximo({ hora: "14:30", titulo: "Dentista", em_minutos: 25 }), "14:30 Dentista · em 25 min");
  const longa = w.linhaDoProximo({ hora: "14:30", titulo: "Reuniao muito longa com o time todo", em_minutos: 25 });
  assert.ok(longa.endsWith(" · em 25 min"), longa);
  assert.ok(longa.includes("…"), longa);
  assert.ok(longa.length <= 30, longa);
  // sem hora e sem minutos: so o titulo
  assert.equal(w.linhaDoProximo({ titulo: "Algo" }), "Algo");
});

test("horizonteDoDia / posicoesDoDia: de 1h a 6h, so o que cabe", () => {
  assert.equal(w.horizonteDoDia([]), 60);
  assert.equal(w.horizonteDoDia([{ em_minutos: 25 }]), 60);
  assert.equal(w.horizonteDoDia([{ em_minutos: 25 }, { em_minutos: 200 }]), 200);
  assert.equal(w.horizonteDoDia([{ em_minutos: 900 }]), 360);
  assert.equal(w.horizonteDoDia([{}, { em_minutos: "x" }]), 60);
  const itens = [{ em_minutos: 30 }, { em_minutos: 60 }, { em_minutos: 500 }, {}];
  const pos = w.posicoesDoDia(itens, 120);
  assert.deepEqual(pos, [
    { indice: 0, frac: 0.25 },
    { indice: 1, frac: 0.5 },
  ]);
});

test("geometriaPontos: raio e passo cabem na largura", () => {
  for (const n of [1, 3, 5, 10, 16]) {
    const g = w.geometriaPontos(n, 148, 16);
    assert.ok(g.raio >= 2 && g.raio <= 7, `raio ${g.raio} (n=${n})`);
    assert.ok(g.x0 + (n - 1) * g.passo + g.raio <= 148 + 0.001, `estoura a largura (n=${n})`);
  }
});

// ============================================================
// Redondo
// ============================================================

test("redondo / padrao: anel de kcal (como antes)", async () => {
  const widget = await montar(CIRC, "");
  assert.deepEqual(coletarTextos(widget), ["42%", "kcal"]);
  assert.equal(acharImagens(widget)[0].image.tracos, 2);
  semCorCustomizada(widget, "padrao");
});

test("redondo / aneis: dois aneis (kcal fora, proteina dentro) com a % no meio", async () => {
  const widget = await montar(CIRC, "aneis");
  assert.deepEqual(coletarTextos(widget), ["42%"]);
  const imgs = acharImagens(widget);
  assert.equal(imgs.length, 1);
  assert.equal(imgs[0].image.tracos, 4, "2 aneis = 2 trilhos + 2 arcos");
  semCorCustomizada(widget, "aneis");

  // sem meta de proteina: so o anel de fora (2 tracos)
  const semMeta = JSON.parse(JSON.stringify(JSON_COMPLETO));
  delete semMeta.comida.meta_proteina_g;
  const w2 = await montar(CIRC, "Anéis", semMeta);
  assert.equal(acharImagens(w2)[0].image.tracos, 2);

  // sem comida: cai na hora do proximo
  const w3 = await montar(CIRC, "aneis", { ...JSON_COMPLETO, comida: null });
  assert.deepEqual(coletarTextos(w3), ["14:30", "25 min"]);
});

test("redondo / proteina: anel da proteina com os gramas e 'prot'", async () => {
  const widget = await montar(CIRC, "proteina");
  assert.deepEqual(coletarTextos(widget), ["102g", "prot"]);
  assert.equal(acharImagens(widget)[0].image.tracos, 2);
  semCorCustomizada(widget, "proteina");

  // sem meta: so o trilho
  const semMeta = JSON.parse(JSON.stringify(JSON_COMPLETO));
  delete semMeta.comida.meta_proteina_g;
  const w2 = await montar(CIRC, "prot", semMeta);
  assert.deepEqual(coletarTextos(w2), ["102g", "prot"]);
  assert.equal(acharImagens(w2)[0].image.tracos, 1);

  // sem comida: placeholder
  const w3 = await montar(CIRC, "proteina", { ...JSON_COMPLETO, comida: null });
  assert.deepEqual(coletarTextos(w3), ["—", "prot"]);
});

test("redondo / contagem: o anel esvazia, tempo compacto no meio e a hora embaixo", async () => {
  const widget = await montar(CIRC, "contagem");
  assert.deepEqual(coletarTextos(widget), ["25m", "14:30"]); // Dentista, em 25 min
  assert.equal(acharImagens(widget)[0].image.tracos, 2, "trilho + arco parcial");
  semCorCustomizada(widget, "contagem");

  // alias "tempo"
  assert.deepEqual(coletarTextos(await montar(CIRC, "tempo")), ["25m", "14:30"]);

  // na hora: anel vazio (so o trilho), 'agora'
  const agora = JSON.parse(JSON.stringify(JSON_COMPLETO));
  agora.agenda[1].em_minutos = 0;
  const w2 = await montar(CIRC, "contagem", agora);
  assert.deepEqual(coletarTextos(w2), ["agora", "14:30"]);
  assert.equal(acharImagens(w2)[0].image.tracos, 1);

  // longe (>= 2h): anel cheio; horas compactas
  const longe = JSON.parse(JSON.stringify(JSON_COMPLETO));
  longe.agenda[1].em_minutos = 215;
  const w3 = await montar(CIRC, "contagem", longe);
  assert.deepEqual(coletarTextos(w3), ["3h35", "14:30"]);
  assert.equal(acharImagens(w3)[0].image.tracos, 2);

  // sem nada pela frente
  assert.deepEqual(coletarTextos(await montar(CIRC, "contagem", JSON_SEM_NADA)), ["—", "livre"]);
});

test("redondo / habitos: anel feitos/total com '3/5' e 'hábitos'", async () => {
  const widget = await montar(CIRC, "habitos");
  assert.deepEqual(coletarTextos(widget), ["3/5", "hábitos"]);
  assert.equal(acharImagens(widget)[0].image.tracos, 2);
  semCorCustomizada(widget, "habitos");

  const completo = await montar(CIRC, "hábitos", { ...JSON_COMPLETO, habitos: { feitos: 5, total: 5 } });
  assert.deepEqual(coletarTextos(completo), ["5/5", "hábitos"]);
  const nenhum = await montar(CIRC, "habitos", { ...JSON_COMPLETO, habitos: { feitos: 0, total: 0 } });
  assert.deepEqual(coletarTextos(nenhum), ["—", "hábitos"]);
  const ausente = await montar(CIRC, "habitos", { ...JSON_COMPLETO, habitos: undefined });
  assert.deepEqual(coletarTextos(ausente), ["—", "hábitos"]);
});

test("redondo / proximo: hora no meio e 'em' sem o prefixo, agora vindo da agenda", async () => {
  const widget = await montar(CIRC, "proximo");
  assert.deepEqual(coletarTextos(widget), ["14:30", "25 min"]);
});

test("redondo: modos so do retangular viram o parecido (agenda->proximo, dia->contagem, macros->aneis)", async () => {
  assert.deepEqual(coletarTextos(await montar(CIRC, "agenda")), ["14:30", "25 min"]);
  assert.deepEqual(coletarTextos(await montar(CIRC, "dia")), ["25m", "14:30"]);
  assert.deepEqual(coletarTextos(await montar(CIRC, "macros")), ["42%"]);
});

test("redondo: dado do cache mostra 'salvo' no lugar do rotulo, em cada modo", async () => {
  global.config.widgetFamily = CIRC;
  global.args = { widgetParameter: "contagem" };
  global.__mockFetchHandler = handlerSucesso(JSON_COMPLETO);
  await w.montarWidget(); // grava o cache
  global.__mockFetchHandler = async () => {
    throw new Error("sem rede");
  };
  for (const modo of ["contagem", "habitos", "proteina"]) {
    global.args = { widgetParameter: modo };
    const textos = coletarTextos(await w.montarWidget());
    assert.ok(textos.includes("salvo"), `${modo}: ${JSON.stringify(textos)}`);
  }
});

// ============================================================
// Retangular
// ============================================================

test("retangular / padrao com agenda: hora + quando + titulo + barra, com simbolos de calendario e garfo", async () => {
  const widget = await montar(RET, "");
  const textos = coletarTextos(widget);
  for (const t of ["14:30", "em 25 min", "Dentista", "1.066 kcal"]) {
    assert.ok(textos.includes(t), `faltou "${t}" em ${JSON.stringify(textos)}`);
  }
  assert.deepEqual(simbolosUsados(widget), ["calendar", "fork.knife"]);
  assert.equal(semSimbolos(widget).length, 1, "so a barra de kcal");
  semCorCustomizada(widget, "padrao");

  // compromisso da agenda vem antes do foco da API (a tarefa das 16:30)
  assert.ok(!textos.includes("Revisar contrato"));
});

test("retangular / padrao: simbolo acompanha o tipo do item (tarefa = checkmark.circle)", async () => {
  const tarefa = JSON.parse(JSON.stringify(JSON_COMPLETO));
  tarefa.agenda[1].tipo = "tarefa";
  assert.deepEqual(simbolosUsados(await montar(RET, "", tarefa)), ["checkmark.circle", "fork.knife"]);
  const habito = JSON.parse(JSON.stringify(JSON_COMPLETO));
  habito.agenda[1].tipo = "habito";
  assert.deepEqual(simbolosUsados(await montar(RET, "", habito)), ["repeat", "fork.knife"]);
});

test("retangular / proximo e comida: simbolo no cabecalho pequeno", async () => {
  const prox = await montar(RET, "proximo");
  assert.deepEqual(coletarTextos(prox), ["PRÓXIMO · em 25 min", "14:30", "Dentista"]);
  assert.deepEqual(simbolosUsados(prox), ["calendar"]);
  assert.equal(semSimbolos(prox).length, 0);
  semCorCustomizada(prox, "proximo");

  const comida = await montar(RET, "comida");
  const textos = coletarTextos(comida);
  for (const t of ["1.066", "/ 2.550 kcal", "Proteína 102 / 115 g"]) assert.ok(textos.includes(t), t);
  assert.deepEqual(simbolosUsados(comida), ["fork.knife"]);
  assert.equal(semSimbolos(comida).length, 2, "barra de kcal e de proteina");
  semCorCustomizada(comida, "comida");
});

test("retangular / agenda: 3 proximos pendentes, 1o maior, '+N' quando tem mais", async () => {
  const widget = await montar(RET, "agenda");
  const textos = coletarTextos(widget);
  assert.deepEqual(textos, ["14:30", "Dentista", "16:30", "Revisar contrato", "19:00", "Aula de navegação", "+1"]);
  assert.ok(!textos.includes("Almoço"), "concluido nao entra");
  assert.ok(!textos.includes("Ler 20 páginas"), "o 4o fica de fora");
  semCorCustomizada(widget, "agenda");

  const linhas = widget.children.filter((c) => c.children);
  assert.equal(linhas.length, 3);
  const [hora1, hora2] = linhas.map((l) => l.children.find((c) => c.text && /^\d\d:\d\d$/.test(c.text)));
  assert.ok(hora1.font.size > hora2.font.size, "1o item maior");
  assert.equal(hora1.textOpacity, undefined, "1o item em branco cheio");
  assert.ok(hora2.textOpacity < 1, "demais um pouco mais apagados");

  // 3 ou menos: sem '+N'
  const tres = JSON.parse(JSON.stringify(JSON_COMPLETO));
  tres.agenda.pop();
  assert.ok(!coletarTextos(await montar(RET, "agenda", tres)).some((t) => /^\+\d/.test(t)));
  // um so
  const um = await montar(RET, "agenda", { ...JSON_COMPLETO, agenda: JSON_COMPLETO.agenda.slice(1, 2) });
  assert.deepEqual(coletarTextos(um), ["14:30", "Dentista"]);
  // vazio
  assert.ok(coletarTextos(await montar(RET, "agenda", JSON_SEM_NADA)).includes("Dia livre"));
  // tudo concluido
  const feito = { ...JSON_COMPLETO, foco: null, agenda: JSON_COMPLETO.agenda.map((i) => ({ ...i, concluido: true })) };
  assert.ok(coletarTextos(await montar(RET, "agenda", feito)).includes("Dia livre"));
});

test("retangular / agenda com payload velho (sem agenda): cai no foco", async () => {
  const widget = await montar(RET, "agenda", JSON_VELHO);
  assert.deepEqual(coletarTextos(widget), ["14:30", "Revisar contrato"]);
});

test("retangular / dia: proximo em cima e linha do tempo desenhada com uma bolinha por item", async () => {
  const widget = await montar(RET, "dia");
  const textos = coletarTextos(widget);
  assert.ok(textos.includes("14:30 Dentista · em 25 min"), JSON.stringify(textos));
  // rodape: "agora" a esquerda e a hora do ultimo item que cabe (o das 21:30 passa de 6h, fica de fora)
  assert.ok(textos.includes("agora"));
  assert.ok(textos.includes("19:00"));
  assert.ok(!textos.includes("21:30"));
  const imagens = semSimbolos(widget);
  assert.equal(imagens.length, 1);
  assert.equal(imagens[0].imageSize.width, 148);
  assert.equal(imagens[0].imageSize.height, 20);
  assert.equal(imagens[0].image.elipses.length, 3, "3 itens dentro das 6h");
  assert.ok(imagens[0].image.preenchimentos.length >= 2, "trilho + trecho ate o proximo");
  assert.deepEqual(simbolosUsados(widget), ["calendar"]);
  semCorCustomizada(widget, "dia");
});

test("retangular / dia: dia livre mostra a linha vazia; payload velho usa o foco", async () => {
  const vazio = await montar(RET, "dia", JSON_SEM_NADA);
  assert.ok(coletarTextos(vazio).includes("Dia livre"));
  const [trilho] = semSimbolos(vazio);
  assert.equal(trilho.image.elipses.length, 0, "sem bolinhas");

  const velho = await montar(RET, "dia", JSON_VELHO);
  const linhaVelha = coletarTextos(velho).find((t) => /^14:30 /.test(t));
  assert.ok(linhaVelha && linhaVelha.startsWith("14:30 Revisar") && linhaVelha.endsWith(" · em 19 min"), linhaVelha);
  assert.equal(semSimbolos(velho)[0].image.elipses.length, 1);
});

test("retangular / habitos: '3/5' grande, 'hábitos hoje' e uma bolinha por habito (cheia = feito)", async () => {
  const widget = await montar(RET, "habitos");
  assert.deepEqual(coletarTextos(widget), ["3/5", "hábitos hoje"]);
  const [pontos] = semSimbolos(widget);
  assert.equal(pontos.image.elipses.length, 3, "3 cheias");
  assert.equal(pontos.image.tracos, 2, "2 so contorno");
  assert.deepEqual(simbolosUsados(widget), ["checkmark.circle"]);
  semCorCustomizada(widget, "habitos");

  // sem habito nenhum
  const nenhum = await montar(RET, "habitos", { ...JSON_COMPLETO, habitos: { feitos: 0, total: 0 } });
  assert.ok(coletarTextos(nenhum).includes("Nenhum hábito hoje"));
  const ausente = await montar(RET, "habitos", { ...JSON_COMPLETO, habitos: null });
  assert.ok(coletarTextos(ausente).includes("Nenhum hábito hoje"));

  // muitos habitos: vira barra em vez de 20 bolinhas
  const muitos = await montar(RET, "habitos", { ...JSON_COMPLETO, habitos: { feitos: 10, total: 20 } });
  const [barra] = semSimbolos(muitos);
  assert.ok(Math.abs(fracaoDaBarra(barra) - 0.5) < 0.001);
});

test("retangular / macros: tres barras P/C/G com a fatia de energia e os gramas (proteina contra a meta)", async () => {
  const widget = await montar(RET, "macros");
  const textos = coletarTextos(widget);
  for (const t of ["1.066 kcal", "P", "C", "G", "102/115 g", "118 g", "31 g"]) {
    assert.ok(textos.includes(t), `faltou "${t}" em ${JSON.stringify(textos)}`);
  }
  const barras = semSimbolos(widget);
  assert.equal(barras.length, 3);
  const soma = 102 * 4 + 118 * 4 + 31 * 9;
  assert.ok(Math.abs(fracaoDaBarra(barras[0]) - (102 * 4) / soma) < 0.001);
  assert.ok(Math.abs(fracaoDaBarra(barras[1]) - (118 * 4) / soma) < 0.001);
  assert.ok(Math.abs(fracaoDaBarra(barras[2]) - (31 * 9) / soma) < 0.001);
  assert.deepEqual(simbolosUsados(widget), ["fork.knife"]);
  semCorCustomizada(widget, "macros");

  // sem meta de proteina: so os gramas
  const semMeta = JSON.parse(JSON.stringify(JSON_COMPLETO));
  delete semMeta.comida.meta_proteina_g;
  assert.ok(coletarTextos(await montar(RET, "macros", semMeta)).includes("102 g"));
});

test("retangular / macros com payload velho (sem carbo/gordura): mostra a comida simples, sem P/C/G", async () => {
  const widget = await montar(RET, "macros", JSON_VELHO);
  const textos = coletarTextos(widget);
  assert.ok(textos.includes("1.066"));
  assert.ok(textos.includes("Proteína 102 / 115 g"));
  assert.ok(!textos.includes("C"));
  // sem comida: convite
  assert.ok(coletarTextos(await montar(RET, "macros", { ...JSON_COMPLETO, comida: null })).includes("manda a foto do prato"));
});

test("retangular: modos so do redondo viram o parecido (aneis/proteina->comida, contagem->proximo)", async () => {
  const comida = coletarTextos(await montar(RET, "comida"));
  assert.deepEqual(coletarTextos(await montar(RET, "aneis")), comida);
  assert.deepEqual(coletarTextos(await montar(RET, "proteina")), comida);
  const prox = coletarTextos(await montar(RET, "proximo"));
  assert.deepEqual(coletarTextos(await montar(RET, "contagem")), prox);
});

test("retangular: dado do cache mostra o aviso 'atualizado ha X' nos modos novos", async () => {
  global.config.widgetFamily = RET;
  global.args = { widgetParameter: "" };
  global.__mockFetchHandler = handlerSucesso(JSON_COMPLETO);
  await w.montarWidget();
  global.__mockFetchHandler = async () => {
    throw new Error("sem rede");
  };
  for (const modo of ["agenda", "dia", "habitos", "macros", "proximo", "comida", ""]) {
    global.args = { widgetParameter: modo };
    const textos = coletarTextos(await w.montarWidget());
    assert.ok(
      textos.some((t) => /atualizado/.test(t)),
      `${modo || "ambos"}: ${JSON.stringify(textos)}`
    );
  }
});

// ============================================================
// Linha (accessoryInline)
// ============================================================

test("linha: simbolo + texto por modo", async () => {
  const casos = [
    ["", "calendar", "14:30 Dentista · 1.066 / 2.550 kcal"],
    ["proximo", "calendar", "14:30 Dentista"],
    ["comida", "fork.knife", "1.066 / 2.550 kcal"],
    ["habitos", "checkmark.circle", "3/5 hábitos"],
    ["macros", "fork.knife", "P 102g · C 118g · G 31g"],
    ["agenda", "calendar", "14:30 Dentista +3"],
    ["contagem", "calendar", "em 25 min · Dentista"],
    ["dia", "calendar", "em 25 min · Dentista"],
    ["aneis", "fork.knife", "1.066 / 2.550 kcal"],
    ["proteina", "fork.knife", "1.066 / 2.550 kcal"],
  ];
  for (const [parametro, simboloEsperado, texto] of casos) {
    const widget = await montar(LINHA, parametro);
    assert.deepEqual(coletarTextos(widget), [texto], `texto de "${parametro}"`);
    assert.deepEqual(simbolosUsados(widget), [simboloEsperado], `simbolo de "${parametro}"`);
    // simbolo vem antes do texto, os dois direto no widget
    assert.ok(widget.children[0].image, "o simbolo vem primeiro");
    assert.equal(widget.children[1].text, texto);
    semCorCustomizada(widget, `linha ${parametro}`);
  }
});

test("linha: estados vazios e payload velho", async () => {
  assert.deepEqual(coletarTextos(await montar(LINHA, "", JSON_SEM_NADA)), ["Nada marcado agora"]);
  assert.deepEqual(coletarTextos(await montar(LINHA, "agenda", JSON_SEM_NADA)), ["Dia livre"]);
  assert.deepEqual(coletarTextos(await montar(LINHA, "habitos", JSON_SEM_NADA)), ["Sem hábitos hoje"]);
  assert.deepEqual(coletarTextos(await montar(LINHA, "comida", JSON_SEM_NADA)), ["manda a foto do prato"]);
  assert.deepEqual(coletarTextos(await montar(LINHA, "macros", JSON_SEM_NADA)), ["manda a foto do prato"]);
  // payload velho: macros cai nos kcal, agenda no foco
  assert.deepEqual(coletarTextos(await montar(LINHA, "macros", JSON_VELHO)), ["1.066 / 2.550 kcal"]);
  assert.deepEqual(coletarTextos(await montar(LINHA, "agenda", JSON_VELHO)), ["14:30 Revisar contrato"]);
  assert.deepEqual(coletarTextos(await montar(LINHA, "contagem", JSON_VELHO)), ["em 19 min · Revisar contrato"]);
});

// ============================================================
// Todos os modos x familias: nunca quebra, nunca "undefined"/"NaN", sempre monocromatico
// ============================================================

test("matriz modos x familias x payloads: sem excecao, sem undefined/NaN, sem cor customizada", async () => {
  const modos = ["", "comida", "proximo", "aneis", "proteina", "contagem", "tempo", "habitos", "agenda", "dia", "macros"];
  const payloads = {
    completo: JSON_COMPLETO,
    velho: JSON_VELHO,
    sem_nada: JSON_SEM_NADA,
    agenda_torta: JSON_AGENDA_TORTA,
    sem_habitos_nem_comida: { ...JSON_COMPLETO, habitos: undefined, comida: undefined, agenda: undefined, foco: undefined },
    agenda_nula: { ...JSON_COMPLETO, agenda: null },
  };
  for (const familia of [CIRC, RET, LINHA]) {
    for (const modo of modos) {
      for (const [nome, dados] of Object.entries(payloads)) {
        const rotulo = `${familia} / "${modo}" / ${nome}`;
        let widget;
        try {
          widget = await montar(familia, modo, dados);
        } catch (e) {
          assert.fail(`${rotulo} lancou: ${e.stack}`);
        }
        const textos = coletarTextos(widget);
        assert.ok(textos.length > 0, `${rotulo}: sem nenhum texto`);
        for (const t of textos) {
          assert.ok(!/undefined|NaN|null|\[object/.test(String(t)), `${rotulo}: texto feio "${t}"`);
        }
        semCorCustomizada(widget, rotulo);
      }
    }
  }
});

test("estado vazio/erro/sem conexao continuam funcionando com parametro de modo", async () => {
  for (const modo of ["agenda", "dia", "habitos", "macros", "aneis"]) {
    for (const familia of [CIRC, RET, LINHA]) {
      const vazio = await montar(familia, modo, { versao: 1, estado: "vazio", foco: null, linhas: ["Nada marcado por enquanto."] });
      assert.ok(coletarTextos(vazio).length > 0);
      const erro = await montar(familia, modo, { versao: 1, estado: "erro", linhas: ["O painel encontrou um erro."] });
      assert.ok(coletarTextos(erro).length > 0);
    }
  }
});
