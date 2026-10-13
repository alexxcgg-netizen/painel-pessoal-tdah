// Simulacao em Node da API do app Scriptable, compartilhada pelos testes do widget
// (tests/js/scriptable_widget*.test.js). Nao termina em .test.js de proposito: nao roda sozinho.

class MockColor {
  constructor(hex, alfa) {
    this.hex = hex;
    this.alpha = alfa === undefined ? 1 : alfa;
  }
}

class MockFont {
  static systemFont(size) {
    return { kind: "system", size };
  }
  static boldSystemFont(size) {
    return { kind: "bold", size };
  }
  static mediumSystemFont(size) {
    return { kind: "medium", size };
  }
  static semiboldSystemFont(size) {
    return { kind: "semibold", size };
  }
  static boldRoundedSystemFont(size) {
    return { kind: "boldRounded", size };
  }
  static semiboldRoundedSystemFont(size) {
    return { kind: "semiboldRounded", size };
  }
}

class MockPoint {
  constructor(x, y) {
    this.x = x;
    this.y = y;
  }
}

class MockRect {
  constructor(x, y, w, h) {
    this.x = x;
    this.y = y;
    this.width = w;
    this.height = h;
  }
}

class MockPath {
  constructor() {
    this.ops = [];
  }
  move(p) {
    this.ops.push(["move", p]);
  }
  addLine(p) {
    this.ops.push(["line", p]);
  }
  addRoundedRect(rect) {
    this.ops.push(["roundedRect", rect]);
  }
}

// DrawContext: guarda o que foi desenhado (textos, tracos, preenchimentos) pra o teste conferir a
// imagem gerada sem renderizar nada de verdade.
class MockDrawContext {
  constructor() {
    this.size = null;
    this.textos = [];
    this.tracos = 0;
    this.preenchimentos = [];
    this._caminho = null;
    this._corTexto = null;
  }
  setLineWidth() {}
  setStrokeColor() {}
  setFillColor(cor) {
    this._corFill = cor;
  }
  setTextColor(cor) {
    this._corTexto = cor;
  }
  setFont() {}
  setTextAlignedCenter() {}
  addPath(p) {
    this._caminho = p;
  }
  strokePath() {
    this.tracos++;
  }
  strokeEllipse() {
    this.tracos++;
  }
  fillPath() {
    const rr = this._caminho && this._caminho.ops.find((o) => o[0] === "roundedRect");
    this.preenchimentos.push({ largura: rr ? rr[1].width : null, alfa: this._corFill ? this._corFill.alpha : null });
  }
  fillEllipse() {}
  drawTextInRect(texto) {
    this.textos.push(texto);
  }
  getImage() {
    return { tamanho: this.size, textos: this.textos.slice(), tracos: this.tracos, preenchimentos: this.preenchimentos.slice() };
  }
}

class MockWidgetImage {
  constructor(imagem) {
    this.image = imagem;
    this.imageSize = null;
    // textos desenhados dentro da imagem entram na coleta de textos dos testes
    this.children = imagem.textos.map((t) => ({ text: t }));
  }
  centerAlignImage() {}
}

class MockSize {
  constructor(w, h) {
    this.width = w;
    this.height = h;
  }
}

class MockWidgetText {
  constructor(text) {
    this.text = text;
    this.textColor = null;
    this.font = null;
    this.minimumScaleFactor = null;
    this._align = null;
  }
  centerAlignText() {
    this._align = "center";
  }
  leftAlignText() {
    this._align = "left";
  }
  rightAlignText() {
    this._align = "right";
  }
}

class MockWidgetStack {
  constructor() {
    this.children = [];
    this.backgroundColor = null;
    this.cornerRadius = null;
    this.spacing = 0;
    this._padding = null;
    this._layout = null;
  }
  addText(text) {
    const node = new MockWidgetText(text);
    this.children.push(node);
    return node;
  }
  addStack() {
    const stack = new MockWidgetStack();
    this.children.push(stack);
    return stack;
  }
  addImage(imagem) {
    const node = new MockWidgetImage(imagem);
    this.children.push(node);
    return node;
  }
  topAlignContent() {}
  centerAlignContent() {}
  bottomAlignContent() {}
  addSpacer(tamanho) {
    this.children.push({ spacer: tamanho === undefined ? true : tamanho });
  }
  layoutHorizontally() {
    this._layout = "horizontal";
  }
  layoutVertically() {
    this._layout = "vertical";
  }
  setPadding(a, b, c, d) {
    this._padding = [a, b, c, d];
  }
}

class MockListWidget extends MockWidgetStack {
  constructor() {
    super();
    this.url = null;
    this._presentedAs = null;
  }
  async presentSmall() {
    this._presentedAs = "small";
  }
  async presentMedium() {
    this._presentedAs = "medium";
  }
  async presentLarge() {
    this._presentedAs = "large";
  }
  async presentAccessoryCircular() {
    this._presentedAs = "accessoryCircular";
  }
  async presentAccessoryRectangular() {
    this._presentedAs = "accessoryRectangular";
  }
  async presentAccessoryInline() {
    this._presentedAs = "accessoryInline";
  }
}



// Request: `handler(mockRequest)` decide a resposta - pode devolver um
// objeto (sucesso, populando req.response.statusCode = 200) ou lancar/
// rejeitar (falha de rede). Pra simular HTTP 4xx/5xx com corpo valido, o
// handler pode setar req.response.statusCode manualmente antes de devolver.
class MockRequest {
  constructor(url) {
    this.url = url;
    this.headers = undefined;
    this.timeoutInterval = undefined;
    this.response = undefined;
  }
  async loadJSON() {
    const handler = global.__mockFetchHandler;
    if (!handler) throw new Error("mock de rede nao configurado no teste");
    const resultado = await handler(this);
    if (!this.response) this.response = { statusCode: 200 };
    return resultado;
  }
}

// FileManager local, em memoria, isolado por teste (`criarMockFileManager`
// cria um Map novo a cada chamada) - simula persistencia real entre duas
// chamadas de montarWidget() dentro do MESMO teste (necessario pro cenario
// de fallback de cache: 1a chamada com rede OK grava, 2a com rede falhando
// le o que a 1a gravou).
function criarMockFileManager() {
  const store = new Map();
  return {
    local() {
      return {
        documentsDirectory: () => "/mock/documentos",
        joinPath: (a, b) => `${a}/${b}`,
        fileExists: (caminho) => store.has(caminho),
        readString: (caminho) => {
          if (!store.has(caminho)) throw new Error("arquivo nao existe");
          return store.get(caminho);
        },
        writeString: (caminho, conteudo) => {
          store.set(caminho, conteudo);
        },
      };
    },
    __store: store,
  };
}


// 2026-10-13 (widgets redesenhados): gradiente de fundo e simbolos da Apple (SF Symbols)
class MockLinearGradient {
  constructor() {
    this.colors = [];
    this.locations = [];
    this.startPoint = null;
    this.endPoint = null;
  }
}

class MockSFSymbol {
  static named(nome) {
    const s = new MockSFSymbol();
    s.nome = nome;
    return s;
  }
  applyFont(f) {
    this.fonte = f;
  }
  applyBoldWeight() {}
  applySemiboldWeight() {}
  get image() {
    return { simbolo: this.nome, textos: [], tracos: 0, preenchimentos: [] };
  }
}

// Coleta todos os textos (recursivamente, atravessando stacks aninhados) -
// facilita asserts sem depender da arvore exata de widgets/stacks.
function coletarTextos(node) {
  const out = [];
  const visitar = (n) => {
    if (!n) return;
    if (n.text !== undefined) out.push(n.text);
    if (Array.isArray(n.children)) n.children.forEach(visitar);
  };
  visitar(node);
  return out;
}

function coletarCores(node) {
  const out = [];
  const visitar = (n) => {
    if (!n) return;
    if (n.textColor) out.push(n.textColor.hex);
    if (Array.isArray(n.children)) n.children.forEach(visitar);
  };
  visitar(node);
  return out;
}

// imagens (DrawContext ou SF Symbol) em qualquer nivel
function acharImagens(node) {
  const out = [];
  const visitar = (n) => {
    if (!n) return;
    if (n.image) out.push(n);
    if (Array.isArray(n.children)) n.children.forEach(visitar);
  };
  visitar(node);
  return out;
}

const simbolosUsados = (node) => acharImagens(node).map((n) => n.image.simbolo).filter(Boolean);

// Instala os globais do Scriptable no objeto `alvo` (global do Node ou contexto de vm)
function instalarGlobais(alvo) {
  Object.assign(alvo, {
    Color: MockColor,
    Font: MockFont,
    Size: MockSize,
    Point: MockPoint,
    Rect: MockRect,
    Path: MockPath,
    DrawContext: MockDrawContext,
    LinearGradient: MockLinearGradient,
    SFSymbol: MockSFSymbol,
    ListWidget: MockListWidget,
    Request: MockRequest,
  });
}

// Payload completo do GET /api/widget com os campos novos de 2026-10-13 (agenda + macros da comida).
// O `foco` (so tarefa/habito) e diferente do 1o da agenda (compromisso do iCloud) de proposito.
const JSON_COMPLETO = {
  versao: 1,
  atualizado_em: "2026-10-13T17:05:00Z",
  estado: "normal",
  foco: { titulo: "Revisar contrato", em_minutos: 145, hora: "16:30" },
  proxima_conta: { nome: "Cartão", em_dias: 3 },
  habitos: { feitos: 3, total: 5 },
  custo_ia: { percentual_teto: 42 },
  comida: { kcal: 1066, proteina_g: 102, carbo_g: 118, gordura_g: 31, refeicoes: 2, meta_kcal: 2550, meta_proteina_g: 115 },
  agenda: [
    { hora: "13:00", titulo: "Almoço", em_minutos: 0, tipo: "habito", concluido: true },
    { hora: "14:30", titulo: "Dentista", em_minutos: 25, tipo: "compromisso", concluido: false },
    { hora: "16:30", titulo: "Revisar contrato", em_minutos: 145, tipo: "tarefa", concluido: false },
    { hora: "19:00", titulo: "Aula de navegação", em_minutos: 295, tipo: "compromisso", concluido: false },
    { hora: "21:30", titulo: "Ler 20 páginas", em_minutos: 445, tipo: "habito", concluido: false },
  ],
  linhas: ["Foco: Revisar contrato em 145 min", "Conta: Cartão em 3 dias", "Hábitos: 3/5", "IA: 42% do teto"],
};

module.exports = {
  JSON_COMPLETO,
  MockColor,
  MockFont,
  MockSize,
  MockPoint,
  MockRect,
  MockPath,
  MockDrawContext,
  MockWidgetImage,
  MockWidgetText,
  MockWidgetStack,
  MockListWidget,
  MockRequest,
  MockLinearGradient,
  MockSFSymbol,
  criarMockFileManager,
  coletarTextos,
  coletarCores,
  acharImagens,
  simbolosUsados,
  instalarGlobais,
};
