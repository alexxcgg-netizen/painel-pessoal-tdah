// Testes da logica de static/js/ui/secao-recolhivel.js (Fase 7, V0c) - sem
// navegador/DOM real: roda com o test runner nativo do Node.
//
//   node --test tests/js/secao_recolhivel.test.js
//
// O modulo detecta Node (sem `document`/`window` globais) e so exporta a logica via
// module.exports, sem ligar nada sozinho - por isso o wiring de navegador real
// (MutationObserver, DOMContentLoaded) fica coberto so pela verificacao headless
// (Playwright, ver AGENTS.md); aqui simulamos o pedacinho minimo de DOM que
// `ligarSecoesRecolhiveis`/`ligarUma` precisam: classList, dataset, querySelector(All),
// addEventListener/dispatch e um `style` de mentira.
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const SecaoRecolhivel = require(path.join(__dirname, "..", "..", "static", "js", "ui", "secao-recolhivel.js"));

// ---- DOM simulado minimo ----------------------------------------------------

function dashParaCamel(nome) {
  return nome.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
}
function camelParaDash(nome) {
  return nome.replace(/[A-Z]/g, (c) => "-" + c.toLowerCase());
}

class ClasseFalsa {
  constructor(el) {
    this._el = el;
  }
  contains(nome) {
    return this._el._classes.has(nome);
  }
  add(nome) {
    this._el._classes.add(nome);
  }
  remove(nome) {
    this._el._classes.delete(nome);
  }
}

class ElementoFalso {
  constructor(tag, classes) {
    this.tagName = tag;
    this._classes = new Set(classes || []);
    this.classList = new ClasseFalsa(this);
    this._attrs = {};
    this._filhos = [];
    this.parentNode = null;
    this._listeners = {};
    this.style = {};
    this.scrollHeight = 120; // valor fixo de mentira, so pra exercitar o codigo que le
    const elemento = this;
    this.dataset = new Proxy(
      {},
      {
        get(_alvo, prop) {
          const chave = "data-" + camelParaDash(String(prop));
          return elemento._attrs[chave];
        },
        set(_alvo, prop, valor) {
          const chave = "data-" + camelParaDash(String(prop));
          elemento._attrs[chave] = String(valor);
          return true;
        },
      }
    );
  }

  setAttribute(nome, valor) {
    this._attrs[nome] = String(valor);
  }

  getAttribute(nome) {
    return Object.prototype.hasOwnProperty.call(this._attrs, nome) ? this._attrs[nome] : null;
  }

  appendChild(filho) {
    filho.parentNode = this;
    this._filhos.push(filho);
    return filho;
  }

  addEventListener(tipo, handler) {
    (this._listeners[tipo] = this._listeners[tipo] || []).push(handler);
  }

  removeEventListener(tipo, handler) {
    if (!this._listeners[tipo]) return;
    this._listeners[tipo] = this._listeners[tipo].filter((h) => h !== handler);
  }

  disparar(tipo, evento) {
    (this._listeners[tipo] || []).forEach((h) => h(evento || {}));
  }

  _todosDescendentes() {
    let acc = [];
    this._filhos.forEach((f) => {
      acc.push(f);
      acc = acc.concat(f._todosDescendentes());
    });
    return acc;
  }

  // suporte so pra seletor de UMA classe (".x"), suficiente pro modulo testado
  querySelectorAll(seletor) {
    const nomeClasse = seletor.replace(/^\./, "");
    return this._todosDescendentes().filter((el) => el._classes && el._classes.has(nomeClasse));
  }

  querySelector(seletor) {
    return this.querySelectorAll(seletor)[0] || null;
  }
}

function criarSecao({ id, abertoInicial, semConteudo } = {}) {
  const secao = new ElementoFalso("section", ["secao-recolhivel"]);
  if (abertoInicial !== undefined) secao.setAttribute("data-aberto", abertoInicial ? "true" : "false");
  if (id) secao.setAttribute("data-secao-id", id);

  const cabecalho = new ElementoFalso("button", ["secao-cabecalho"]);
  cabecalho.setAttribute("aria-expanded", "false");
  secao.appendChild(cabecalho);

  let conteudo = null;
  if (!semConteudo) {
    conteudo = new ElementoFalso("div", ["secao-conteudo"]);
    secao.appendChild(conteudo);
  }

  return { secao, cabecalho, conteudo };
}

// ---- localStorage de mentira -------------------------------------------------

function criarLocalStorageFalso() {
  const dados = new Map();
  return {
    getItem: (k) => (dados.has(k) ? dados.get(k) : null),
    setItem: (k, v) => dados.set(k, String(v)),
    removeItem: (k) => dados.delete(k),
    _dados: dados,
  };
}

function comLocalStorage(fn) {
  const antes = global.localStorage;
  global.localStorage = criarLocalStorageFalso();
  try {
    fn(global.localStorage);
  } finally {
    if (antes === undefined) delete global.localStorage;
    else global.localStorage = antes;
  }
}

// ---- testes: abre/fecha + aria-expanded --------------------------------------

test("secao com data-aberto=false comeca fechada (padrao) e aria-expanded=false", () => {
  comLocalStorage(() => {
    const { secao, cabecalho } = criarSecao({ abertoInicial: false });
    SecaoRecolhivel.ligarUma(secao);
    assert.equal(secao.dataset.aberto, "false");
    assert.equal(cabecalho.getAttribute("aria-expanded"), "false");
  });
});

test("secao com data-aberto=true comeca aberta e aria-expanded=true", () => {
  comLocalStorage(() => {
    const { secao, cabecalho } = criarSecao({ abertoInicial: true });
    SecaoRecolhivel.ligarUma(secao);
    assert.equal(secao.dataset.aberto, "true");
    assert.equal(cabecalho.getAttribute("aria-expanded"), "true");
  });
});

test("clique no cabecalho alterna aberto/fechado e aria-expanded junto", () => {
  comLocalStorage(() => {
    const { secao, cabecalho } = criarSecao({ abertoInicial: false });
    SecaoRecolhivel.ligarUma(secao);

    cabecalho.disparar("click");
    assert.equal(secao.dataset.aberto, "true");
    assert.equal(cabecalho.getAttribute("aria-expanded"), "true");

    cabecalho.disparar("click");
    assert.equal(secao.dataset.aberto, "false");
    assert.equal(cabecalho.getAttribute("aria-expanded"), "false");
  });
});

test("ligarUma e idempotente: chamar duas vezes nao duplica o listener de clique", () => {
  comLocalStorage(() => {
    const { secao, cabecalho } = criarSecao({ abertoInicial: false });
    SecaoRecolhivel.ligarUma(secao);
    SecaoRecolhivel.ligarUma(secao); // segunda chamada nao deveria religar

    cabecalho.disparar("click"); // se tivesse ligado 2x, isso abriria e fecharia -> continuaria false
    assert.equal(secao.dataset.aberto, "true");
  });
});

test("secao sem .secao-cabecalho nao quebra (so nao liga nada)", () => {
  comLocalStorage(() => {
    const secao = new ElementoFalso("section", ["secao-recolhivel"]);
    secao.setAttribute("data-aberto", "false");
    assert.doesNotThrow(() => SecaoRecolhivel.ligarUma(secao));
  });
});

test("secao sem .secao-conteudo nao quebra e o cabecalho continua clicavel", () => {
  comLocalStorage(() => {
    const { secao, cabecalho } = criarSecao({ abertoInicial: false, semConteudo: true });
    assert.doesNotThrow(() => SecaoRecolhivel.ligarUma(secao));
    assert.doesNotThrow(() => cabecalho.disparar("click"));
    assert.equal(secao.dataset.aberto, "true");
  });
});

// ---- testes: estado salvo/restaurado no localStorage -------------------------

test("com data-secao-id, alternar salva o estado no localStorage", () => {
  comLocalStorage((ls) => {
    const { secao, cabecalho } = criarSecao({ id: "memoria", abertoInicial: false });
    SecaoRecolhivel.ligarUma(secao);
    cabecalho.disparar("click");
    assert.equal(ls.getItem("secaoRecolhivel:memoria"), "1");
    cabecalho.disparar("click");
    assert.equal(ls.getItem("secaoRecolhivel:memoria"), "0");
  });
});

test("estado salvo no localStorage tem prioridade sobre o data-aberto do HTML ao ligar", () => {
  comLocalStorage((ls) => {
    ls.setItem("secaoRecolhivel:memoria", "1");
    // HTML diz fechado, mas o localStorage lembra que o usuario deixou aberto
    const { secao, cabecalho } = criarSecao({ id: "memoria", abertoInicial: false });
    SecaoRecolhivel.ligarUma(secao);
    assert.equal(secao.dataset.aberto, "true");
    assert.equal(cabecalho.getAttribute("aria-expanded"), "true");
  });
});

test("sem data-secao-id, o estado NAO e salvo no localStorage", () => {
  comLocalStorage((ls) => {
    const { secao, cabecalho } = criarSecao({ abertoInicial: false });
    SecaoRecolhivel.ligarUma(secao);
    cabecalho.disparar("click");
    assert.equal(secao.dataset.aberto, "true");
    assert.equal(ls._dados.size, 0);
  });
});

test("cada secao-id tem sua propria chave no localStorage (nao vaza entre secoes)", () => {
  comLocalStorage((ls) => {
    const a = criarSecao({ id: "rotina", abertoInicial: false });
    const b = criarSecao({ id: "planos", abertoInicial: false });
    SecaoRecolhivel.ligarUma(a.secao);
    SecaoRecolhivel.ligarUma(b.secao);
    a.cabecalho.disparar("click");
    assert.equal(a.secao.dataset.aberto, "true");
    assert.equal(b.secao.dataset.aberto, "false");
    assert.equal(ls.getItem("secaoRecolhivel:rotina"), "1");
    assert.equal(ls.getItem("secaoRecolhivel:planos"), null);
  });
});

// ---- testes: sem localStorage nao quebra --------------------------------------

test("sem localStorage no ambiente (undefined), ligar e clicar nao lancam excecao", () => {
  const antes = global.localStorage;
  delete global.localStorage;
  try {
    const { secao, cabecalho } = criarSecao({ id: "memoria", abertoInicial: false });
    assert.doesNotThrow(() => SecaoRecolhivel.ligarUma(secao));
    assert.doesNotThrow(() => cabecalho.disparar("click"));
    assert.equal(secao.dataset.aberto, "true");
  } finally {
    if (antes === undefined) delete global.localStorage;
    else global.localStorage = antes;
  }
});

test("localStorage que lanca excecao (quota cheia/modo privado) nao quebra a secao", () => {
  const antes = global.localStorage;
  global.localStorage = {
    getItem() {
      throw new Error("bloqueado");
    },
    setItem() {
      throw new Error("quota cheia");
    },
  };
  try {
    const { secao, cabecalho } = criarSecao({ id: "memoria", abertoInicial: false });
    assert.doesNotThrow(() => SecaoRecolhivel.ligarUma(secao));
    assert.doesNotThrow(() => cabecalho.disparar("click"));
    assert.equal(secao.dataset.aberto, "true");
  } finally {
    if (antes === undefined) delete global.localStorage;
    else global.localStorage = antes;
  }
});

// ---- testes: ligarSecoesRecolhiveis (varias secoes sob uma raiz, inclusive aninhadas) ----

test("ligarSecoesRecolhiveis liga todas as secoes sob a raiz de uma vez", () => {
  comLocalStorage(() => {
    const raiz = new ElementoFalso("main", []);
    const a = criarSecao({ id: "a", abertoInicial: false });
    const b = criarSecao({ id: "b", abertoInicial: false });
    raiz.appendChild(a.secao);
    raiz.appendChild(b.secao);

    SecaoRecolhivel.ligarSecoesRecolhiveis(raiz);
    a.cabecalho.disparar("click");
    b.cabecalho.disparar("click");
    assert.equal(a.secao.dataset.aberto, "true");
    assert.equal(b.secao.dataset.aberto, "true");
  });
});

test("ligarSecoesRecolhiveis aceita a propria secao como raiz (ex: no inserido pelo MutationObserver)", () => {
  comLocalStorage(() => {
    const { secao, cabecalho } = criarSecao({ abertoInicial: false });
    SecaoRecolhivel.ligarSecoesRecolhiveis(secao);
    cabecalho.disparar("click");
    assert.equal(secao.dataset.aberto, "true");
  });
});

test("ligarSecoesRecolhiveis com raiz vazia/sem secoes nao lanca excecao", () => {
  comLocalStorage(() => {
    const raiz = new ElementoFalso("main", []);
    assert.doesNotThrow(() => SecaoRecolhivel.ligarSecoesRecolhiveis(raiz));
  });
});

// ---- testes: helpers de storage isolados (lerEstadoSalvo/salvarEstado) --------

test("lerEstadoSalvo devolve null quando nao ha secaoId", () => {
  comLocalStorage(() => {
    assert.equal(SecaoRecolhivel.lerEstadoSalvo(null), null);
    assert.equal(SecaoRecolhivel.lerEstadoSalvo(""), null);
  });
});

test("lerEstadoSalvo devolve null quando a chave nao existe ainda", () => {
  comLocalStorage(() => {
    assert.equal(SecaoRecolhivel.lerEstadoSalvo("nunca-salvo"), null);
  });
});

test("salvarEstado sem secaoId e no-op (nao lanca, nao grava)", () => {
  comLocalStorage((ls) => {
    assert.doesNotThrow(() => SecaoRecolhivel.salvarEstado(null, true));
    assert.equal(ls._dados.size, 0);
  });
});
