// tests/js/bottom_sheet.test.js - Testes do bottom sheet (static/js/ui/bottom-sheet.js)
// com um DOM MINIMO simulado aqui mesmo (sem jsdom - nenhuma dependencia
// nova no projeto, package.json nao existe de proposito, ver
// docs/agentes/fase7-regras-faixa.md). O bottom-sheet.js roda SEM NENHUMA
// MODIFICACAO contra esse DOM falso: ele so implementa os pedacos de
// document/Element que o componente realmente usa (getElementById,
// createElement, classList<->className ligados como no navegador de
// verdade, addEventListener/dispatchEvent com bolha manual ate o
// document, closest com seletor simples, foco). Cobre abrir/fechar, ESC,
// foco preso e devolvido, e o evento "bottomsheet:fechado". Arrastar (Pointer
// Events) e a transicao visual de verdade ficam pra verificacao no
// Playwright headless (scripts/ralph-v0d-sheet-nav/), ver AGENTS.md.
//
//   node --test tests/js/bottom_sheet.test.js

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const CAMINHO_MODULO = path.join(__dirname, "..", "..", "static", "js", "ui", "bottom-sheet.js");

// ---- DOM minimo ----

function elementMatches(el, selector) {
  selector = String(selector).trim();
  if (selector.startsWith(".")) return !!(el.classList && el.classList.contains(selector.slice(1)));
  if (selector.startsWith("#")) return el.id === selector.slice(1);
  if (selector.startsWith("[") && selector.endsWith("]")) {
    const inner = selector.slice(1, -1);
    const igual = inner.indexOf("=");
    if (igual === -1) return el.hasAttribute(inner);
    const attr = inner.slice(0, igual);
    const valor = inner.slice(igual + 1).replace(/^["']|["']$/g, "");
    return el.getAttribute(attr) === valor;
  }
  return el.tagName === selector.toUpperCase();
}

class FakeEvento {
  constructor(type, opts = {}) {
    this.type = type;
    this.bubbles = !!opts.bubbles;
    this.detail = opts.detail;
    this.shiftKey = !!opts.shiftKey;
    this.key = opts.key;
    this.target = null;
    this.defaultPrevented = false;
  }
  preventDefault() {
    this.defaultPrevented = true;
  }
}

class FakeElement {
  constructor(tag) {
    this.nodeType = 1;
    this.tagName = String(tag || "div").toUpperCase();
    this.id = "";
    this.hidden = false;
    this.disabled = false;
    this.style = {};
    this.parentNode = null;
    this.ownerDocument = null;
    this.children = [];
    this._attrs = new Map();
    this._listeners = new Map();

    // className <-> classList ligados de verdade, igual DOM real (bottom-sheet.js
    // usa tanto `el.className = "x"` na hora de criar quanto `classList.add/remove/
    // contains` depois - os dois precisam enxergar o mesmo conjunto).
    const grupo = new Set();
    Object.defineProperty(this, "className", {
      get: () => Array.from(grupo).join(" "),
      set: (valor) => {
        grupo.clear();
        String(valor)
          .split(/\s+/)
          .filter(Boolean)
          .forEach((c) => grupo.add(c));
      },
    });
    this.classList = {
      add: (...cs) => cs.forEach((c) => grupo.add(c)),
      remove: (...cs) => cs.forEach((c) => grupo.delete(c)),
      contains: (c) => grupo.has(c),
    };
  }
  get firstChild() {
    return this.children[0] || null;
  }
  setAttribute(nome, valor) {
    this._attrs.set(nome, String(valor));
    if (nome === "id") this.id = String(valor);
  }
  getAttribute(nome) {
    return this._attrs.has(nome) ? this._attrs.get(nome) : null;
  }
  hasAttribute(nome) {
    return this._attrs.has(nome);
  }
  removeAttribute(nome) {
    this._attrs.delete(nome);
  }
  appendChild(filho) {
    if (filho.parentNode) {
      const i = filho.parentNode.children.indexOf(filho);
      if (i !== -1) filho.parentNode.children.splice(i, 1);
    }
    filho.parentNode = this;
    filho.ownerDocument = this.ownerDocument;
    this.children.push(filho);
    return filho;
  }
  // C2: insertBefore/removeChild pro portal (o sheet sobe pro body ao abrir).
  insertBefore(novo, referencia) {
    if (novo.parentNode) {
      const i = novo.parentNode.children.indexOf(novo);
      if (i !== -1) novo.parentNode.children.splice(i, 1);
    }
    const j = this.children.indexOf(referencia);
    novo.parentNode = this;
    if (j === -1) this.children.push(novo);
    else this.children.splice(j, 0, novo);
    return novo;
  }
  removeChild(filho) {
    const i = this.children.indexOf(filho);
    if (i !== -1) this.children.splice(i, 1);
    filho.parentNode = null;
    return filho;
  }
  addEventListener(tipo, fn) {
    if (!this._listeners.has(tipo)) this._listeners.set(tipo, new Set());
    this._listeners.get(tipo).add(fn);
  }
  removeEventListener(tipo, fn) {
    if (this._listeners.has(tipo)) this._listeners.get(tipo).delete(fn);
  }
  dispatchEvent(evento) {
    evento.target = evento.target || this;
    let no = this;
    while (no) {
      const fns = no._listeners && no._listeners.get(evento.type);
      if (fns) for (const fn of Array.from(fns)) fn.call(no, evento);
      if (!evento.bubbles) return !evento.defaultPrevented;
      no = no.parentNode;
    }
    // chegou no topo da arvore de elementos - continua a bolha ate o document.
    if (this.ownerDocument) this.ownerDocument._receberBolha(evento);
    return !evento.defaultPrevented;
  }
  focus() {
    if (this.disabled) return;
    if (this.ownerDocument) this.ownerDocument.activeElement = this;
  }
  closest(selector) {
    let no = this;
    while (no && no.nodeType === 1) {
      if (elementMatches(no, selector)) return no;
      no = no.parentNode;
    }
    return null;
  }
}

class FakeDocument {
  constructor() {
    this.body = new FakeElement("body");
    this.body.ownerDocument = this;
    this.activeElement = null;
    this._porId = new Map();
    this._listeners = new Map();
  }
  createElement(tag) {
    const el = new FakeElement(tag);
    el.ownerDocument = this;
    return el;
  }
  createComment(texto) {
    // comentario so precisa de parentNode (marca do lugar original do sheet)
    return { nodeType: 8, textContent: String(texto), parentNode: null, children: [] };
  }
  // Nao ha arvore real ligada ao document nesse DOM minimo - registra o id
  // manualmente na criacao (getElementById dos testes usa esse indice).
  registrar(el) {
    if (el.id) this._porId.set(el.id, el);
  }
  getElementById(id) {
    return this._porId.get(id) || null;
  }
  addEventListener(tipo, fn) {
    if (!this._listeners.has(tipo)) this._listeners.set(tipo, new Set());
    this._listeners.get(tipo).add(fn);
  }
  removeEventListener(tipo, fn) {
    if (this._listeners.has(tipo)) this._listeners.get(tipo).delete(fn);
  }
  dispatchEvent(evento) {
    evento.target = evento.target || this;
    this._receberBolha(evento);
    return !evento.defaultPrevented;
  }
  _receberBolha(evento) {
    const fns = this._listeners.get(evento.type);
    if (fns) for (const fn of Array.from(fns)) fn.call(this, evento);
  }
}

function montarAmbiente() {
  const doc = new FakeDocument();
  const anterior = { document: globalThis.document, CustomEvent: globalThis.CustomEvent };
  globalThis.document = doc;
  // Sombra sempre o CustomEvent nativo do Node: o CustomEvent de verdade tem
  // `target` so-leitura (definido pelo mecanismo real de dispatch), o que
  // quebraria o dispatchEvent manual acima. bottom-sheet.js so usa `new
  // raiz.CustomEvent(tipo, opts)`, entao um FakeEvento serve igual.
  globalThis.CustomEvent = function CustomEvent(tipo, opts) {
    return new FakeEvento(tipo, opts);
  };
  return {
    doc,
    restaurar() {
      globalThis.document = anterior.document;
      globalThis.CustomEvent = anterior.CustomEvent;
    },
  };
}

function novoSheet(doc, id) {
  const sheet = doc.createElement("div");
  sheet.classList.add("bottom-sheet");
  sheet.hidden = true;
  sheet.setAttribute("id", id);
  doc.registrar(sheet);
  return sheet;
}

function novoBotao(doc, texto) {
  const btn = doc.createElement("button");
  btn.textContent = texto;
  return btn;
}

// Nunca deixamos `window` global (assim `raiz` dentro do modulo cai em
// globalThis e os gatilhos de clique automaticos - que precisam de um
// document conectado de verdade - ficam desligados; esses sao cobertos no
// Playwright). Cache do require e limpo a cada teste pra zerar o estado
// interno do modulo (lista de sheets abertos, WeakMaps de foco/origem).
let BottomSheet;
let ambiente;

test.beforeEach(() => {
  ambiente = montarAmbiente();
  delete require.cache[require.resolve(CAMINHO_MODULO)];
  BottomSheet = require(CAMINHO_MODULO);
});

test.afterEach(() => {
  ambiente.restaurar();
  delete require.cache[require.resolve(CAMINHO_MODULO)];
});

// ---- abrir/fechar ----

test("abrirBottomSheet por id: fica visivel, dialog modal, classe de aberto", () => {
  const { doc } = ambiente;
  const sheet = novoSheet(doc, "sheet-1");
  sheet.appendChild(novoBotao(doc, "Salvar"));

  BottomSheet.abrirBottomSheet("sheet-1");

  assert.equal(sheet.hidden, false);
  assert.equal(sheet.getAttribute("role"), "dialog");
  assert.equal(sheet.getAttribute("aria-modal"), "true");
  assert.ok(sheet.classList.contains("bottom-sheet--aberto"));
});

test("abrirBottomSheet aceita o proprio elemento, sem precisar de id", () => {
  const { doc } = ambiente;
  const sheet = novoSheet(doc, "sheet-el");
  BottomSheet.abrirBottomSheet(sheet);
  assert.equal(sheet.hidden, false);
});

test("abrirBottomSheet com id inexistente nao lanca excecao", () => {
  assert.doesNotThrow(() => BottomSheet.abrirBottomSheet("nao-existe"));
});

test("abrir bloqueia o scroll do body; fechar libera", () => {
  const { doc } = ambiente;
  const sheet = novoSheet(doc, "sheet-scroll");
  sheet.appendChild(novoBotao(doc, "Ok"));

  BottomSheet.abrirBottomSheet("sheet-scroll");
  assert.ok(doc.body.classList.contains("bottom-sheet-bloqueado"));

  BottomSheet.fecharBottomSheet("sheet-scroll");
  assert.equal(doc.body.classList.contains("bottom-sheet-bloqueado"), false);
});

test("fecharBottomSheet: esconde de novo, tira a classe e o aria-modal", () => {
  const { doc } = ambiente;
  const sheet = novoSheet(doc, "sheet-2");
  sheet.appendChild(novoBotao(doc, "Salvar"));
  BottomSheet.abrirBottomSheet("sheet-2");

  BottomSheet.fecharBottomSheet("sheet-2");

  assert.equal(sheet.hidden, true);
  assert.equal(sheet.classList.contains("bottom-sheet--aberto"), false);
  assert.equal(sheet.getAttribute("aria-modal"), null);
});

test("fechar um sheet que ja esta fechado nao quebra (idempotente)", () => {
  const { doc } = ambiente;
  const sheet = novoSheet(doc, "sheet-3");
  assert.doesNotThrow(() => BottomSheet.fecharBottomSheet("sheet-3"));
  assert.doesNotThrow(() => BottomSheet.fecharBottomSheet(sheet));
});

test("abrir o mesmo sheet duas vezes seguidas nao empilha (2a chamada e no-op)", () => {
  const { doc } = ambiente;
  const sheet = novoSheet(doc, "sheet-dup");
  sheet.appendChild(novoBotao(doc, "Ok"));
  BottomSheet.abrirBottomSheet("sheet-dup");
  const focoDepoisDaPrimeira = doc.activeElement;

  BottomSheet.abrirBottomSheet("sheet-dup");

  assert.equal(doc.activeElement, focoDepoisDaPrimeira);
});

// ---- ESC ----

test("ESC fecha o sheet aberto no topo da pilha", () => {
  const { doc } = ambiente;
  const sheet = novoSheet(doc, "sheet-esc");
  sheet.appendChild(novoBotao(doc, "Ok"));
  BottomSheet.abrirBottomSheet("sheet-esc");

  doc.dispatchEvent(new FakeEvento("keydown", { key: "Escape" }));

  assert.equal(sheet.hidden, true);
});

test("ESC sem nenhum sheet aberto nao quebra", () => {
  const { doc } = ambiente;
  assert.doesNotThrow(() => doc.dispatchEvent(new FakeEvento("keydown", { key: "Escape" })));
});

// ---- foco preso e devolvido ----

test("abrir foca o primeiro elemento focavel de dentro do sheet", () => {
  const { doc } = ambiente;
  const sheet = novoSheet(doc, "sheet-foco");
  const primeiro = novoBotao(doc, "Primeiro");
  const segundo = novoBotao(doc, "Segundo");
  sheet.appendChild(primeiro);
  sheet.appendChild(segundo);

  BottomSheet.abrirBottomSheet("sheet-foco");

  assert.equal(doc.activeElement, primeiro);
});

test("Tab no ultimo focavel volta pro primeiro (armadilha de foco)", () => {
  const { doc } = ambiente;
  const sheet = novoSheet(doc, "sheet-trap");
  const primeiro = novoBotao(doc, "Primeiro");
  const ultimo = novoBotao(doc, "Ultimo");
  sheet.appendChild(primeiro);
  sheet.appendChild(ultimo);
  BottomSheet.abrirBottomSheet("sheet-trap");

  ultimo.focus();
  const evento = new FakeEvento("keydown", { key: "Tab" });
  doc.dispatchEvent(evento);

  assert.equal(doc.activeElement, primeiro);
  assert.equal(evento.defaultPrevented, true);
});

test("Shift+Tab no primeiro focavel vai pro ultimo", () => {
  const { doc } = ambiente;
  const sheet = novoSheet(doc, "sheet-trap-2");
  const primeiro = novoBotao(doc, "Primeiro");
  const ultimo = novoBotao(doc, "Ultimo");
  sheet.appendChild(primeiro);
  sheet.appendChild(ultimo);
  BottomSheet.abrirBottomSheet("sheet-trap-2");

  primeiro.focus();
  const evento = new FakeEvento("keydown", { key: "Tab", shiftKey: true });
  doc.dispatchEvent(evento);

  assert.equal(doc.activeElement, ultimo);
  assert.equal(evento.defaultPrevented, true);
});

test("Tab no meio da lista nao e interceptado (segue o fluxo normal)", () => {
  const { doc } = ambiente;
  const sheet = novoSheet(doc, "sheet-trap-3");
  const primeiro = novoBotao(doc, "Primeiro");
  const meio = novoBotao(doc, "Meio");
  const ultimo = novoBotao(doc, "Ultimo");
  sheet.appendChild(primeiro);
  sheet.appendChild(meio);
  sheet.appendChild(ultimo);
  BottomSheet.abrirBottomSheet("sheet-trap-3");

  meio.focus();
  const evento = new FakeEvento("keydown", { key: "Tab" });
  doc.dispatchEvent(evento);

  assert.equal(evento.defaultPrevented, false);
});

test("fechar devolve o foco pro elemento que abriu o sheet", () => {
  const { doc } = ambiente;
  const sheet = novoSheet(doc, "sheet-devolve");
  sheet.appendChild(novoBotao(doc, "Ok"));
  const gatilho = novoBotao(doc, "Abrir");
  gatilho.focus();

  BottomSheet.abrirBottomSheet("sheet-devolve");
  assert.notEqual(doc.activeElement, gatilho); // foco foi pro conteudo do sheet

  BottomSheet.fecharBottomSheet("sheet-devolve");

  assert.equal(doc.activeElement, gatilho);
});

test("sheet sem nenhum elemento focavel nao quebra: o proprio painel recebe o foco", () => {
  const { doc } = ambiente;
  const sheet = novoSheet(doc, "sheet-vazio");

  assert.doesNotThrow(() => BottomSheet.abrirBottomSheet("sheet-vazio"));
  assert.ok(doc.activeElement);
});

// ---- evento de fechado ----

test("fechar dispara bottomsheet:fechado no proprio sheet, com o id no detail", () => {
  const { doc } = ambiente;
  const sheet = novoSheet(doc, "sheet-evento");
  sheet.appendChild(novoBotao(doc, "Ok"));
  BottomSheet.abrirBottomSheet("sheet-evento");

  let recebido = null;
  sheet.addEventListener("bottomsheet:fechado", (e) => {
    recebido = e;
  });

  BottomSheet.fecharBottomSheet("sheet-evento");

  assert.ok(recebido);
  assert.equal(recebido.detail.id, "sheet-evento");
});

test("bottomsheet:fechado borbulha ate o document", () => {
  const { doc } = ambiente;
  const sheet = novoSheet(doc, "sheet-bolha");
  sheet.appendChild(novoBotao(doc, "Ok"));
  BottomSheet.abrirBottomSheet("sheet-bolha");

  let viuNoDocumento = false;
  doc.addEventListener("bottomsheet:fechado", () => {
    viuNoDocumento = true;
  });

  BottomSheet.fecharBottomSheet("sheet-bolha");

  assert.equal(viuNoDocumento, true);
});

// ---- data-fecha-ao-enviar / bottomsheet:sucesso ----

test("form com data-fecha-ao-enviar fecha o sheet ao receber bottomsheet:sucesso", () => {
  const { doc } = ambiente;
  const sheet = novoSheet(doc, "sheet-form");
  const form = doc.createElement("form");
  form.setAttribute("data-fecha-ao-enviar", "");
  form.appendChild(doc.createElement("input"));
  sheet.appendChild(form);

  BottomSheet.abrirBottomSheet("sheet-form");
  assert.equal(sheet.hidden, false);

  form.dispatchEvent(new FakeEvento("bottomsheet:sucesso", { bubbles: true }));

  assert.equal(sheet.hidden, true);
});

test("bottomsheet:sucesso fora de um form marcado nao fecha nada", () => {
  const { doc } = ambiente;
  const sheet = novoSheet(doc, "sheet-form-2");
  const form = doc.createElement("form"); // sem data-fecha-ao-enviar
  form.appendChild(doc.createElement("input"));
  sheet.appendChild(form);

  BottomSheet.abrirBottomSheet("sheet-form-2");
  form.dispatchEvent(new FakeEvento("bottomsheet:sucesso", { bubbles: true }));

  assert.equal(sheet.hidden, false);
});

// ---- helpers puros expostos (elementosFocaveis / ehFocavel) ----

test("ehFocavel ignora desabilitado, escondido e aria-hidden", () => {
  const { doc } = ambiente;
  const btn = novoBotao(doc, "x");
  assert.equal(BottomSheet.ehFocavel(btn), true);

  btn.setAttribute("disabled", "");
  assert.equal(BottomSheet.ehFocavel(btn), false);
  btn.removeAttribute("disabled");

  btn.hidden = true;
  assert.equal(BottomSheet.ehFocavel(btn), false);
  btn.hidden = false;

  btn.setAttribute("aria-hidden", "true");
  assert.equal(BottomSheet.ehFocavel(btn), false);
});

test("ehFocavel: input type=hidden nao conta, input normal conta", () => {
  const { doc } = ambiente;
  const oculto = doc.createElement("input");
  oculto.setAttribute("type", "hidden");
  assert.equal(BottomSheet.ehFocavel(oculto), false);

  const visivel = doc.createElement("input");
  visivel.setAttribute("type", "text");
  assert.equal(BottomSheet.ehFocavel(visivel), true);
});

test("ehFocavel: link so conta com href", () => {
  const { doc } = ambiente;
  const semHref = doc.createElement("a");
  assert.equal(BottomSheet.ehFocavel(semHref), false);

  const comHref = doc.createElement("a");
  comHref.setAttribute("href", "#");
  assert.equal(BottomSheet.ehFocavel(comHref), true);
});

test("elementosFocaveis encontra em qualquer profundidade, na ordem do DOM", () => {
  const { doc } = ambiente;
  const raizEl = doc.createElement("div");
  const a = novoBotao(doc, "a");
  const wrap = doc.createElement("div");
  const b = novoBotao(doc, "b");
  wrap.appendChild(b);
  raizEl.appendChild(a);
  raizEl.appendChild(wrap);

  const focaveis = BottomSheet.elementosFocaveis(raizEl);

  assert.equal(focaveis.length, 2);
  assert.equal(focaveis[0], a);
  assert.equal(focaveis[1], b);
});

// ---- C2: portal pro body e reabrir durante a animacao de fechar ----

test("abrir leva o sheet pro body e fechar devolve pro mesmo lugar", () => {
  const { doc } = ambiente;
  const aba = doc.createElement("section");
  const antes = doc.createElement("p");
  const depois = doc.createElement("p");
  const sheet = novoSheet(doc, "sheet-portal");
  sheet.appendChild(novoBotao(doc, "Salvar"));
  aba.appendChild(antes);
  aba.appendChild(sheet);
  aba.appendChild(depois);

  BottomSheet.abrirBottomSheet("sheet-portal");
  assert.equal(sheet.parentNode, doc.body, "aberto: filho direto do body");
  assert.equal(aba.children.indexOf(sheet), -1);

  BottomSheet.fecharBottomSheet("sheet-portal");
  assert.equal(sheet.parentNode, aba, "fechado: volta pra aba");
  assert.deepEqual(aba.children, [antes, sheet, depois], "mesma posicao, sem sobra da marca");
});

test("sheet que ja e filho do body nao e movido nem quebra", () => {
  const { doc } = ambiente;
  const sheet = novoSheet(doc, "sheet-body");
  doc.body.appendChild(sheet);
  BottomSheet.abrirBottomSheet(sheet);
  BottomSheet.fecharBottomSheet(sheet);
  assert.equal(sheet.parentNode, doc.body);
  assert.equal(sheet.hidden, true);
});

test("sheet solto (sem pai) abre e fecha sem portal", () => {
  const { doc } = ambiente;
  const sheet = novoSheet(doc, "sheet-solto");
  assert.doesNotThrow(() => BottomSheet.abrirBottomSheet(sheet));
  assert.equal(sheet.hidden, false);
  BottomSheet.fecharBottomSheet(sheet);
  assert.equal(sheet.hidden, true);
});

test("reabrir durante a animacao de fechar: o fechamento antigo nao esconde o sheet", (t) => {
  const { doc } = ambiente;
  const anteriorMM = globalThis.matchMedia;
  globalThis.matchMedia = () => ({ matches: false }); // pode animar
  t.mock.timers.enable({ apis: ["setTimeout"] });
  try {
    const aba = doc.createElement("section");
    const sheet = novoSheet(doc, "sheet-rapido");
    aba.appendChild(sheet);
    BottomSheet.abrirBottomSheet(sheet);
    BottomSheet.fecharBottomSheet(sheet); // agenda o finalizar (240ms)
    BottomSheet.abrirBottomSheet(sheet); // toque rapido: abre de novo
    t.mock.timers.tick(500);
    assert.equal(sheet.hidden, false, "continua visivel");
    assert.ok(sheet.classList.contains("bottom-sheet--aberto"));
    assert.equal(sheet.parentNode, doc.body, "continua no body enquanto aberto");
    BottomSheet.fecharBottomSheet(sheet);
    t.mock.timers.tick(500);
    assert.equal(sheet.hidden, true);
    assert.equal(sheet.parentNode, aba);
  } finally {
    globalThis.matchMedia = anteriorMM;
  }
});

// M1 (rodada 2): o timer do fechamento antigo tem que ser CANCELADO ao reabrir. So o guarda
// `abertos.includes` nao bastava: fechar -> reabrir -> fechar de novo deixava o 1o timer
// vivo, e ele finalizava o 2o fechamento antes da hora (e "fechado" saia duas vezes).
function comAnimacao(t, corpo) {
  const anteriorMM = globalThis.matchMedia;
  globalThis.matchMedia = () => ({ matches: false }); // pode animar
  t.mock.timers.enable({ apis: ["setTimeout"] });
  try {
    corpo();
  } finally {
    globalThis.matchMedia = anteriorMM;
  }
}

test("reabrir na janela cancela o timer antigo: 2o fechamento dura a animacao inteira", (t) => {
  comAnimacao(t, () => {
    const { doc } = ambiente;
    const aba = doc.createElement("section");
    const sheet = novoSheet(doc, "sheet-timer");
    aba.appendChild(sheet);
    let fechados = 0;
    sheet.addEventListener("bottomsheet:fechado", () => fechados++);

    BottomSheet.abrirBottomSheet(sheet);
    BottomSheet.fecharBottomSheet(sheet); // timer A: finaliza em t=240
    t.mock.timers.tick(200);
    BottomSheet.abrirBottomSheet(sheet); // t=200: reabre -> cancela A
    t.mock.timers.tick(20);
    BottomSheet.fecharBottomSheet(sheet); // t=220: timer B finaliza em t=460
    t.mock.timers.tick(30); // t=250: A ja teria disparado aqui
    assert.equal(sheet.hidden, false, "timer antigo nao pode cortar a animacao nova");
    assert.equal(fechados, 0);
    t.mock.timers.tick(300); // t=550
    assert.equal(sheet.hidden, true);
    assert.equal(fechados, 1, "bottomsheet:fechado sai uma vez so");
    assert.equal(sheet.parentNode, aba);
    assert.ok(!doc.body.classList.contains("bottom-sheet-bloqueado"));
  });
});

test("abrir/fechar/reabrir rapido 20 vezes: termina aberto, no body, scroll travado; depois fecha limpo", (t) => {
  comAnimacao(t, () => {
    const { doc } = ambiente;
    const aba = doc.createElement("section");
    const sheet = novoSheet(doc, "sheet-rajada");
    aba.appendChild(sheet);
    let fechados = 0;
    sheet.addEventListener("bottomsheet:fechado", () => fechados++);

    for (let i = 0; i < 20; i++) {
      BottomSheet.abrirBottomSheet(sheet);
      t.mock.timers.tick(50);
      BottomSheet.fecharBottomSheet(sheet);
      t.mock.timers.tick(100); // dentro da janela de 240ms
    }
    BottomSheet.abrirBottomSheet(sheet);
    t.mock.timers.tick(1000);
    assert.equal(sheet.hidden, false);
    assert.ok(sheet.classList.contains("bottom-sheet--aberto"));
    assert.ok(!sheet.classList.contains("bottom-sheet--fechando"));
    assert.equal(sheet.parentNode, doc.body);
    assert.ok(doc.body.classList.contains("bottom-sheet-bloqueado"));
    assert.equal(fechados, 0, "nenhum fechamento chegou a finalizar");

    BottomSheet.fecharBottomSheet(sheet);
    t.mock.timers.tick(1000);
    assert.equal(sheet.hidden, true);
    assert.equal(sheet.parentNode, aba);
    assert.equal(fechados, 1);
    assert.ok(!doc.body.classList.contains("bottom-sheet-bloqueado"));
    // e continua abrindo depois disso
    BottomSheet.abrirBottomSheet(sheet);
    assert.equal(sheet.hidden, false);
  });
});
