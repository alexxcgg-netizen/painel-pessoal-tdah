// Testes do widget Scriptable (Fase 7, faixa N3b) - roda o SCRIPT REAL
// (scriptable/scriptable-widget.js) contra uma simulacao em Node da API do
// app Scriptable (Request, ListWidget, FileManager, config, Script, Color,
// Font, args), com `node --test`:
//
//   node --test tests/js/scriptable_widget.test.js
//
// O script real so exporta funcoes (nao chama main() sozinho) quando
// `module` existe - ver o guard `typeof module !== "undefined"` no final do
// arquivo, mesmo padrao usado em static/js/*.js. Os globais do Scriptable
// (Request, ListWidget, ...) nao existem em Node, entao este arquivo os
// define em `global.*` ANTES de dar require() no script - dentro do wrapper
// CommonJS, identificadores soltos (ex: `new Request(...)`) resolvem pelo
// objeto global quando nao ha `const`/`let` local com o mesmo nome, entao o
// script roda de verdade contra esses mocks, sem precisar editar uma linha
// dele pra ser testavel.
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const {
  MockColor,
  MockFont,
  MockSize,
  MockPoint,
  MockRect,
  MockPath,
  MockDrawContext,
  MockListWidget,
  MockRequest,
  criarMockFileManager,
  coletarTextos,
  coletarCores,
  acharImagens,
  instalarGlobais,
} = require("./_scriptable_mocks");

// ---- Setup dos globais + require do script real ----

const CAMINHO_SCRIPT = path.join(__dirname, "..", "..", "scriptable", "scriptable-widget.js");

function prepararGlobaisBase() {
  instalarGlobais(global);
  global.FileManager = criarMockFileManager();
  global.config = { runsInWidget: true, widgetFamily: "small" };
  global.args = { widgetParameter: "" };
  global.Script = {
    _widget: null,
    setWidget(w) {
      this._widget = w;
    },
    complete() {},
  };
  global.__mockFetchHandler = null;
}

prepararGlobaisBase();
const widgetModulo = require(CAMINHO_SCRIPT);

// Reseta o estado mutavel entre testes SEM re-exigir o modulo (as funcoes
// exportadas leem os globais em tempo de chamada, entao um require() so
// basta pro arquivo inteiro).
test.beforeEach(() => {
  global.config = { runsInWidget: true, widgetFamily: "small" };
  global.args = { widgetParameter: "" };
  global.FileManager = criarMockFileManager();
  global.__mockFetchHandler = null;
});

// ---- Fixtures do contrato fixo (GET /api/widget) ----

const JSON_NORMAL = {
  versao: 1,
  atualizado_em: "2026-09-23T20:10:00Z",
  estado: "normal",
  foco: { titulo: "Revisar contrato", em_minutos: 19, hora: "14:30" },
  proxima_conta: { nome: "Cartão", em_dias: 3 },
  habitos: { feitos: 3, total: 5 },
  custo_ia: { percentual_teto: 42 },
  comida: { kcal: 1066, proteina_g: 102, refeicoes: 2, meta_kcal: 2550, meta_proteina_g: 115 },
  linhas: [
    "Foco: Revisar contrato em 19 min",
    "Conta: Cartão em 3 dias",
    "Hábitos: 3/5",
    "IA: 42% do teto",
  ],
};

const JSON_VAZIO = {
  versao: 1,
  atualizado_em: "2026-09-23T20:10:00Z",
  estado: "vazio",
  foco: null,
  proxima_conta: null,
  habitos: { feitos: 0, total: 0 },
  custo_ia: { percentual_teto: 0 },
  linhas: ["Nada marcado por enquanto.", "Aproveita o tempo livre."],
};

const JSON_ERRO = {
  versao: 1,
  atualizado_em: "2026-09-23T20:10:00Z",
  estado: "erro",
  foco: null,
  proxima_conta: null,
  habitos: null,
  custo_ia: null,
  linhas: ["O painel encontrou um erro.", "Tente novamente mais tarde."],
};

function handlerSucesso(json) {
  return async () => json;
}

function handlerFalha() {
  return async () => {
    throw new Error("network error simulado");
  };
}

// ============================================================
// Estado normal, nos 4 tamanhos
// ============================================================

// 2026-10-13: widget "proximo + comida" (escolha do Alex) - conta/habitos/IA saem do layout.
function acharBarras(node) {
  const out = [];
  const visitar = (n) => {
    if (!n || !Array.isArray(n.children)) return;
    if (n.size && n.size.height === 5 && n.backgroundColor && n.backgroundColor.hex === "#1f272e") {
      const cheio = n.children.find((c) => c.size);
      out.push({ largura: n.size.width, cheio: cheio ? cheio.size.width : 0 });
    }
    n.children.forEach(visitar);
  };
  visitar(node);
  return out;
}

test("normal / small: proximo (hora, 'em X min', titulo) + kcal do dia com barra", async () => {
  global.config.widgetFamily = "small";
  global.__mockFetchHandler = handlerSucesso(JSON_NORMAL);

  const widget = await widgetModulo.montarWidget();
  const textos = coletarTextos(widget);

  for (const t of ["PRÓXIMO", "14:30", "em 19 min", "Revisar contrato", "COMIDA HOJE", "1.066 / 2.550 kcal"]) {
    assert.ok(textos.includes(t), `faltou "${t}" em ${JSON.stringify(textos)}`);
  }
  // small nao tem proteina nem conta/habitos/IA
  assert.ok(!textos.some((t) => t.startsWith("Proteína")));
  assert.ok(!textos.some((t) => /Cartão|Hábitos|IA/.test(t)));
  const barras = acharBarras(widget);
  assert.equal(barras.length, 1);
  assert.equal(barras[0].cheio, Math.round(126 * (1066 / 2550)));
  assert.equal(widget.backgroundColor.hex, "#000000");
  assert.ok(coletarCores(widget).includes("#9fdcb0"), "rotulo da comida na cor do card refeicao");
  // tocar abre o chat
  assert.equal(widget.url, "http://SEU-IP-OU-DOMINIO:5001/?aba=assistente");
});

test("normal / medium: duas colunas - proximo e comida com kcal + proteina e as duas barras", async () => {
  global.config.widgetFamily = "medium";
  global.__mockFetchHandler = handlerSucesso(JSON_NORMAL);

  const widget = await widgetModulo.montarWidget();
  const textos = coletarTextos(widget);

  for (const t of ["PRÓXIMO", "14:30", "Revisar contrato", "COMIDA HOJE", "1.066 / 2.550 kcal", "Proteína 102 / 115 g", "2 refeições pela foto"]) {
    assert.ok(textos.includes(t), `faltou "${t}"`);
  }
  const barras = acharBarras(widget);
  assert.equal(barras.length, 2);
  assert.equal(barras[1].cheio, Math.round(150 * (102 / 115)));
});

test("normal / medium sem comida: so o proximo, sem coluna vazia", async () => {
  global.config.widgetFamily = "medium";
  global.__mockFetchHandler = handlerSucesso({ ...JSON_NORMAL, comida: null });
  const textos = coletarTextos(await widgetModulo.montarWidget());
  assert.ok(textos.includes("Revisar contrato"));
  assert.ok(!textos.includes("COMIDA HOJE"));
});

test("normal sem foco: 'Nada marcado agora'; meta batida nao estoura a barra; sem meta, sem barra", async () => {
  global.config.widgetFamily = "small";
  global.__mockFetchHandler = handlerSucesso({ ...JSON_NORMAL, foco: null, comida: { ...JSON_NORMAL.comida, kcal: 3100 } });
  let widget = await widgetModulo.montarWidget();
  assert.ok(coletarTextos(widget).includes("Nada marcado agora"));
  assert.equal(acharBarras(widget)[0].cheio, 126);

  global.__mockFetchHandler = handlerSucesso({ ...JSON_NORMAL, comida: { kcal: 800, proteina_g: 40, refeicoes: 1, meta_kcal: null, meta_proteina_g: null } });
  widget = await widgetModulo.montarWidget();
  assert.ok(coletarTextos(widget).includes("800 kcal"));
  assert.equal(acharBarras(widget).length, 0);
});

// 2026-10-13: tela de bloqueio desenhada (anel + barras) - "fica muito pequeno"

// barra desenhada (imagemBarra): 1o preenchimento = trilho, 2o = parte cheia (desenhada em 3x)
function fracaoDaBarra(imagemNode) {
  const [trilho, cheio] = imagemNode.image.preenchimentos;
  return cheio ? cheio.largura / trilho.largura : 0;
}

test("normal / accessoryCircular: anel desenhado com a % da meta de kcal no meio, sem cor customizada", async () => {
  global.config.widgetFamily = "accessoryCircular";
  global.__mockFetchHandler = handlerSucesso(JSON_NORMAL);

  const widget = await widgetModulo.montarWidget();
  const textos = coletarTextos(widget);

  assert.deepEqual(textos, ["42%", "kcal"]); // 1066 / 2550
  const [anel] = acharImagens(widget);
  assert.equal(anel.image.tracos, 2, "trilho + parte preenchida");
  assert.equal(coletarCores(widget).length, 0, "familia accessory* nao pode setar textColor (iOS ignora/distorce)");
  assert.equal(widget.backgroundColor, null, "familia accessory* nao pode setar backgroundColor");

  // sem comida: o anel mostra a hora do proximo, so com o trilho
  global.__mockFetchHandler = handlerSucesso({ ...JSON_NORMAL, comida: null });
  const semComida = await widgetModulo.montarWidget();
  assert.deepEqual(coletarTextos(semComida), ["14:30", "19 min"]);
  assert.equal(acharImagens(semComida)[0].image.tracos, 1);
});

test("normal / accessoryRectangular: hora grande, titulo e barra de kcal desenhada", async () => {
  global.config.widgetFamily = "accessoryRectangular";
  global.__mockFetchHandler = handlerSucesso(JSON_NORMAL);

  const widget = await widgetModulo.montarWidget();
  const textos = coletarTextos(widget);

  for (const t of ["14:30", "em 19 min", "Revisar contrato", "1.066 kcal"]) {
    assert.ok(textos.includes(t), `faltou "${t}" em ${JSON.stringify(textos)}`);
  }
  const barras = acharImagens(widget);
  assert.equal(barras.length, 1);
  assert.ok(Math.abs(fracaoDaBarra(barras[0]) - 1066 / 2550) < 0.001);
  assert.equal(barras[0].imageSize.width, 70);
  assert.equal(coletarCores(widget).length, 0);
  assert.equal(widget.backgroundColor, null);
});

test("accessoryRectangular com parametro 'comida': kcal grande + barras de kcal e proteina, sem o proximo", async () => {
  global.config.widgetFamily = "accessoryRectangular";
  global.args = { widgetParameter: "comida" };
  global.__mockFetchHandler = handlerSucesso(JSON_NORMAL);

  const widget = await widgetModulo.montarWidget();
  const textos = coletarTextos(widget);
  for (const t of ["1.066", "/ 2.550 kcal", "Proteína 102 / 115 g"]) {
    assert.ok(textos.includes(t), `faltou "${t}" em ${JSON.stringify(textos)}`);
  }
  assert.ok(!textos.includes("Revisar contrato"));
  const barras = acharImagens(widget);
  assert.equal(barras.length, 2);
  assert.ok(Math.abs(fracaoDaBarra(barras[1]) - 102 / 115) < 0.001);
  // parametro de modo nao vira URL do painel
  assert.equal(widget.url, "http://SEU-IP-OU-DOMINIO:5001/?aba=assistente");

  // sem nada comido ainda: convite em vez de zeros
  global.__mockFetchHandler = handlerSucesso({ ...JSON_NORMAL, comida: null });
  assert.ok(coletarTextos(await widgetModulo.montarWidget()).includes("manda a foto do prato"));
});

test("accessoryRectangular com parametro 'proximo': so o compromisso, hora grande", async () => {
  global.config.widgetFamily = "accessoryRectangular";
  global.args = { widgetParameter: "Próximo" };
  global.__mockFetchHandler = handlerSucesso(JSON_NORMAL);

  const widget = await widgetModulo.montarWidget();
  assert.deepEqual(coletarTextos(widget), ["PRÓXIMO · em 19 min", "14:30", "Revisar contrato"]);
  assert.equal(acharImagens(widget).length, 0);
  const hora = widget.children.find((n) => n.text === "14:30");
  assert.equal(hora.font.size, 26);

  global.__mockFetchHandler = handlerSucesso({ ...JSON_NORMAL, foco: null });
  assert.ok(coletarTextos(await widgetModulo.montarWidget()).includes("Nada marcado agora"));
});

test("accessoryCircular com parametro 'proximo': anel com a hora mesmo havendo comida", async () => {
  global.config.widgetFamily = "accessoryCircular";
  global.args = { widgetParameter: "proximo" };
  global.__mockFetchHandler = handlerSucesso(JSON_NORMAL);
  assert.deepEqual(coletarTextos(await widgetModulo.montarWidget()), ["14:30", "19 min"]);
});

test("accessoryInline: uma linha so, respeitando o parametro", async () => {
  global.config.widgetFamily = "accessoryInline";
  global.__mockFetchHandler = handlerSucesso(JSON_NORMAL);
  assert.deepEqual(coletarTextos(await widgetModulo.montarWidget()), ["14:30 Revisar contrato · 1.066 / 2.550 kcal"]);

  global.args = { widgetParameter: "comida" };
  assert.deepEqual(coletarTextos(await widgetModulo.montarWidget()), ["1.066 / 2.550 kcal"]);

  global.args = { widgetParameter: "" };
  global.__mockFetchHandler = handlerSucesso({ ...JSON_NORMAL, foco: null, comida: null });
  assert.deepEqual(coletarTextos(await widgetModulo.montarWidget()), ["Nada marcado agora"]);
});

test("modoDoWidget: 'comida'/'proximo' sao modo; 'URL|TOKEN' e URL continuam sendo configuracao", () => {
  const casos = [
    ["", "ambos"],
    ["comida", "comida"],
    ["  Comida ", "comida"],
    ["kcal", "comida"],
    ["proximo", "proximo"],
    ["Próximo", "proximo"],
    ["https://meu-pc.exemplo.ts.net:8443|tok", "ambos"],
    ["https://meu-pc.exemplo.ts.net:8443", "ambos"],
    ["qualquer coisa", "ambos"],
  ];
  for (const [parametro, esperado] of casos) {
    global.args = { widgetParameter: parametro };
    assert.equal(widgetModulo.modoDoWidget(), esperado, parametro);
  }
  global.args = { widgetParameter: "comida" };
  const cfg = widgetModulo.resolverConfig();
  assert.equal(cfg.url, "http://SEU-IP-OU-DOMINIO:5001");
  assert.equal(cfg.token, "");
});

test("familia desconhecida (ex: large) cai no layout de small sem quebrar", async () => {
  global.config.widgetFamily = "large";
  global.__mockFetchHandler = handlerSucesso(JSON_NORMAL);

  const widget = await widgetModulo.montarWidget();
  const textos = coletarTextos(widget);
  assert.ok(textos.includes("PRÓXIMO"));
  assert.ok(textos.includes("Revisar contrato"));
});

test("quandoTexto: agora, minutos, horas", () => {
  assert.equal(widgetModulo.quandoTexto(0), "agora");
  assert.equal(widgetModulo.quandoTexto(25), "em 25 min");
  assert.equal(widgetModulo.quandoTexto(80), "em 1h20");
  assert.equal(widgetModulo.quandoTexto(120), "em 2h");
  assert.equal(widgetModulo.quandoTexto(undefined), "agora");
});

test("tocar no widget: so vira link com URL http(s) de verdade", async () => {
  global.config.widgetFamily = "small";
  global.args = { widgetParameter: "https://meu-pc.exemplo.ts.net:8443|tok" };
  global.__mockFetchHandler = handlerSucesso(JSON_NORMAL);
  assert.equal((await widgetModulo.montarWidget()).url, "https://meu-pc.exemplo.ts.net:8443/?aba=assistente");
  global.args = { widgetParameter: "javascript:alert(1)|tok" };
  assert.equal((await widgetModulo.montarWidget()).url, null);
});

// ============================================================
// Estado vazio
// ============================================================

test("vazio / small: mostra a primeira linha do contrato como mensagem", async () => {
  global.config.widgetFamily = "small";
  global.__mockFetchHandler = handlerSucesso(JSON_VAZIO);

  const widget = await widgetModulo.montarWidget();
  const textos = coletarTextos(widget);
  assert.ok(textos.includes("Nada marcado por enquanto."));
});

test("vazio / accessoryCircular: mostra rotulo 'livre', sem cor", async () => {
  global.config.widgetFamily = "accessoryCircular";
  global.__mockFetchHandler = handlerSucesso(JSON_VAZIO);

  const widget = await widgetModulo.montarWidget();
  const textos = coletarTextos(widget);
  assert.ok(textos.includes("livre"));
  assert.equal(coletarCores(widget).length, 0);
});

test("vazio: sem linhas no payload cai no texto padrao claro", async () => {
  global.config.widgetFamily = "small";
  global.__mockFetchHandler = handlerSucesso({ ...JSON_VAZIO, linhas: [] });

  const widget = await widgetModulo.montarWidget();
  const textos = coletarTextos(widget);
  assert.ok(textos.some((t) => t.toLowerCase().includes("livre") || t.toLowerCase().includes("nada")));
});

// ============================================================
// Estado erro (reportado pela propria API)
// ============================================================

test("erro / small: usa a cor de perigo no titulo e mostra a mensagem do contrato", async () => {
  global.config.widgetFamily = "small";
  global.__mockFetchHandler = handlerSucesso(JSON_ERRO);

  const widget = await widgetModulo.montarWidget();
  const textos = coletarTextos(widget);
  assert.ok(textos.includes("O painel encontrou um erro."));
  const cores = coletarCores(widget);
  assert.ok(cores.includes("#ff5c72")); // --danger
});

test("erro / accessoryRectangular: mostra as linhas do contrato, sem cor customizada", async () => {
  global.config.widgetFamily = "accessoryRectangular";
  global.__mockFetchHandler = handlerSucesso(JSON_ERRO);

  const widget = await widgetModulo.montarWidget();
  const textos = coletarTextos(widget);
  assert.equal(textos[0], "O painel encontrou um erro.");
  assert.equal(coletarCores(widget).length, 0);
});

test("erro: sem linhas no payload cai no texto padrao claro", async () => {
  global.config.widgetFamily = "medium";
  global.__mockFetchHandler = handlerSucesso({ ...JSON_ERRO, linhas: [] });

  const widget = await widgetModulo.montarWidget();
  const textos = coletarTextos(widget);
  assert.ok(textos.some((t) => t.toLowerCase().includes("erro")));
});

// ============================================================
// Falha de rede + fallback de cache
// ============================================================

test("rede falha sem cache previo: mostra mensagem clara de sem conexao", async () => {
  global.config.widgetFamily = "small";
  global.__mockFetchHandler = handlerFalha();

  const widget = await widgetModulo.montarWidget();
  const textos = coletarTextos(widget);
  assert.ok(textos.some((t) => t.includes("Sem conexão")));
});

test("rede falha sem cache previo (accessoryCircular): mostra placeholder, sem travar", async () => {
  global.config.widgetFamily = "accessoryCircular";
  global.__mockFetchHandler = handlerFalha();

  const widget = await widgetModulo.montarWidget();
  const textos = coletarTextos(widget);
  assert.ok(textos.includes("--"));
});

test("cache: 1a busca com sucesso grava; 2a busca falha e usa o cache com 'atualizado ha X'", async () => {
  global.config.widgetFamily = "small";

  // 1a chamada: rede OK -> grava cache
  global.__mockFetchHandler = handlerSucesso(JSON_NORMAL);
  const primeiro = await widgetModulo.montarWidget();
  assert.ok(coletarTextos(primeiro).includes("Revisar contrato"));
  assert.equal(global.FileManager.__store.size, 1, "deveria ter gravado 1 arquivo de cache");

  // 2a chamada: rede falha -> deveria usar o cache gravado na 1a
  global.__mockFetchHandler = handlerFalha();
  const segundo = await widgetModulo.montarWidget();
  const textos = coletarTextos(segundo);

  assert.ok(textos.includes("Revisar contrato"), "deveria mostrar os dados salvos, nao 'sem conexao'");
  assert.ok(
    textos.some((t) => t.startsWith("atualizado")),
    "deveria mostrar 'atualizado ha X' quando usa dados de cache"
  );
});

test("cache: fallback funciona tambem em accessoryRectangular (rotulo com 'atualizado')", async () => {
  global.config.widgetFamily = "accessoryRectangular";
  global.__mockFetchHandler = handlerSucesso(JSON_NORMAL);
  await widgetModulo.montarWidget();

  global.__mockFetchHandler = handlerFalha();
  const widget = await widgetModulo.montarWidget();
  const textos = coletarTextos(widget);
  assert.ok(textos.some((t) => t.includes("atualizado")));
});

test("cache: resposta HTTP com status de erro (>=400) tambem aciona o fallback", async () => {
  global.config.widgetFamily = "small";
  global.__mockFetchHandler = handlerSucesso(JSON_NORMAL);
  await widgetModulo.montarWidget();

  global.__mockFetchHandler = async (req) => {
    req.response = { statusCode: 401 };
    return { erro: "token invalido" };
  };
  const widget = await widgetModulo.montarWidget();
  const textos = coletarTextos(widget);
  assert.ok(textos.includes("Revisar contrato"));
  assert.ok(textos.some((t) => t.startsWith("atualizado")));
});

// ============================================================
// Configuracao (URL/token) e formatacao de tempo
// ============================================================

test("resolverConfig: usa as constantes fixas quando nao ha parametro do widget", () => {
  global.args = { widgetParameter: "" };
  const { url, token } = widgetModulo.resolverConfig();
  assert.equal(typeof url, "string");
  assert.equal(token, "");
});

test("resolverConfig: parametro do widget 'URL|TOKEN' sobrescreve as constantes", () => {
  global.args = { widgetParameter: "http://192.168.1.10:5001/ | segredo123" };
  const { url, token } = widgetModulo.resolverConfig();
  assert.equal(url, "http://192.168.1.10:5001");
  assert.equal(token, "segredo123");
});

test("resolverConfig: parametro so com URL mantem token vazio", () => {
  global.args = { widgetParameter: "http://192.168.1.10:5001" };
  const { url } = widgetModulo.resolverConfig();
  assert.equal(url, "http://192.168.1.10:5001");
});

test("buscarDados: manda Authorization Bearer quando ha token", async () => {
  global.args = { widgetParameter: "http://exemplo.com|abc123" };
  let headersRecebidos = null;
  global.__mockFetchHandler = async (req) => {
    headersRecebidos = req.headers;
    return JSON_NORMAL;
  };
  const { url, token } = widgetModulo.resolverConfig();
  await widgetModulo.buscarDados(url, token);
  assert.deepEqual(headersRecebidos, { Authorization: "Bearer abc123" });
});

test("buscarDados: sem token, nao manda header de Authorization", async () => {
  let headersRecebidos = "nao-chamado";
  global.__mockFetchHandler = async (req) => {
    headersRecebidos = req.headers;
    return JSON_NORMAL;
  };
  await widgetModulo.buscarDados("http://exemplo.com", "");
  assert.deepEqual(headersRecebidos, {});
});

test("formatarAtualizadoHaX: menos de 1 min vira 'agora'", () => {
  const agora = new Date("2026-09-23T20:10:30Z");
  assert.equal(widgetModulo.formatarAtualizadoHaX("2026-09-23T20:10:00Z", agora), "agora");
});

test("formatarAtualizadoHaX: minutos", () => {
  const agora = new Date("2026-09-23T20:25:00Z");
  assert.equal(widgetModulo.formatarAtualizadoHaX("2026-09-23T20:10:00Z", agora), "há 15 min");
});

test("formatarAtualizadoHaX: horas", () => {
  const agora = new Date("2026-09-23T23:10:00Z");
  assert.equal(widgetModulo.formatarAtualizadoHaX("2026-09-23T20:10:00Z", agora), "há 3 h");
});

test("formatarAtualizadoHaX: dias", () => {
  const agora = new Date("2026-09-26T20:10:00Z");
  assert.equal(widgetModulo.formatarAtualizadoHaX("2026-09-23T20:10:00Z", agora), "há 3 d");
});

test("formatarAtualizadoHaX: data invalida nao quebra", () => {
  assert.equal(widgetModulo.formatarAtualizadoHaX("nao-e-uma-data", new Date()), "há um tempo");
});

// ============================================================
// main(): integra config.runsInWidget / presentXxx sem quebrar
// ============================================================

test("main(): dentro do widget de verdade, chama Script.setWidget", async () => {
  global.config = { runsInWidget: true, widgetFamily: "small" };
  global.__mockFetchHandler = handlerSucesso(JSON_NORMAL);
  global.Script._widget = null;

  await widgetModulo.main();
  assert.ok(global.Script._widget instanceof MockListWidget);
});

test("main(): rodando manualmente (fora do widget), chama o present certo pra familia", async () => {
  global.config = { runsInWidget: false, widgetFamily: "accessoryRectangular" };
  global.__mockFetchHandler = handlerSucesso(JSON_NORMAL);

  await widgetModulo.main();
  // nao ha widget global pra inspecionar aqui, mas rodar sem lancar excecao
  // ja cobre o caminho - a asserção de conteudo fica nos testes de
  // montarWidget() acima.
  assert.ok(true);
});

test("dentro do Scriptable de verdade (tem `module`, nao tem `process`): main() roda e entrega o widget", async () => {
  // bug do 1o teste no iPhone: o script so exportava (achava que era Node) e nunca desenhava nada
  const vm = require("node:vm");
  const fs = require("node:fs");
  const codigo = fs.readFileSync(CAMINHO_SCRIPT, "utf8");
  let entregue = null;
  const contexto = {
    module: { exports: {} }, // o Scriptable tem isso
    FileManager: criarMockFileManager(),
    config: { runsInWidget: true, widgetFamily: "small" },
    args: { widgetParameter: "" },
    Script: { setWidget: (w) => (entregue = w), complete() {} },
    console,
  };
  instalarGlobais(contexto);
  global.__mockFetchHandler = handlerSucesso(JSON_NORMAL);
  contexto.global = contexto;
  contexto.__mockFetchHandler = global.__mockFetchHandler;
  vm.runInNewContext(codigo, contexto);
  for (let i = 0; i < 20 && !entregue; i++) await new Promise((r) => setTimeout(r, 5));
  assert.ok(entregue, "main() nao rodou dentro do Scriptable");
  assert.ok(coletarTextos(entregue).includes("PRÓXIMO"));
});
