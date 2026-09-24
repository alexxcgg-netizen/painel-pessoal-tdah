// static/js/ui/bottom-sheet.js - Fase 7 (V0d): bottom sheet reutilizavel.
//
// API global (script classico, sem modulos - ver docs/agentes/mapa-frontend.md):
//   abrirBottomSheet(elOuId)   - elOuId e o proprio <div class="bottom-sheet">
//   fecharBottomSheet(elOuId)    ou o id dele (string)
//
// Contrato de autoria (docs/agentes/fase7-visual.md): o autor de uma secao so
// escreve `<div class="bottom-sheet" hidden>...conteudo...</div>` (pode ter
// role/aria-modal ja escritos, ou nao - este arquivo garante os dois). Na
// primeira vez que o sheet abre, este arquivo monta a estrutura interna
// sozinho (idempotente - roda so uma vez por sheet):
//
//   .bottom-sheet                (fixed, cobre o viewport - so moldura)
//     .bottom-sheet-fundo        (fundo escurecido - clique fora fecha)
//     .bottom-sheet-painel       (o painel que sobe - foco fica PRESO aqui)
//       .bottom-sheet-alca       (alcinha decorativa - tambem area de arrastar)
//       ...todo o conteudo original do autor, movido pra dentro...
//
// Fecha com ESC, clique no fundo escurecido, ou arrastando o painel pra
// baixo a partir da alca (best-effort - so liga se o navegador tiver Pointer
// Events). Foco fica preso dentro do painel enquanto aberto (Tab/Shift+Tab
// nao escapam) e volta pro elemento que abriu o sheet quando ele fecha.
// Respeita `prefers-reduced-motion` (fecha/abre sem a transicao de slide).
//
// Gatilhos declarativos (opcionais, prontos sem precisar chamar a API na
// mao): um elemento com `data-abre-sheet="id-do-sheet"` abre esse sheet no
// clique; um elemento DENTRO de um sheet com `data-fecha-sheet` fecha o
// sheet ancestral mais proximo no clique.
//
// Formulario que deve fechar o sheet sozinho ao salvar com sucesso: marca o
// <form> com o atributo `data-fecha-ao-enviar` e, no handler de sucesso (DEPOIS
// do fetch/await confirmar, nunca so no submit em si - o componente nao tem
// como saber se deu certo sozinho), dispara:
//
//   form.dispatchEvent(new CustomEvent("bottomsheet:sucesso", { bubbles: true }))
//
// Este arquivo ouve esse evento delegado no documento e fecha o sheet mais
// proximo automaticamente.
//
// Evento emitido ao fechar (por qualquer motivo - API, ESC, fundo, arrastar,
// `bottomsheet:sucesso`): "bottomsheet:fechado" no proprio elemento do sheet
// (bubbles: true), com detail: { id }.

(function (raiz) {
  "use strict";

  const CLASSE_ABERTO = "bottom-sheet--aberto";
  const CLASSE_FECHANDO = "bottom-sheet--fechando";
  const ATRIBUTO_FECHA_AO_ENVIAR = "data-fecha-ao-enviar";
  const TAGS_FOCAVEIS = new Set(["A", "BUTTON", "TEXTAREA", "INPUT", "SELECT"]);
  const LIMIAR_ARRASTAR_PX = 90;
  const DURACAO_TRANSICAO_MS = 240;

  // Sheets abertos agora, na ordem em que abriram (o ultimo e o topo da
  // pilha) - permite empilhar sem quebrar: ESC/fundo so afetam o do topo, e
  // o scroll do body so libera quando NENHUM sheet fica aberto.
  const abertos = [];
  // Elemento com foco antes de cada sheet abrir, pra devolver ao fechar.
  const origemPorSheet = new WeakMap();
  const inicializados = new WeakSet();

  function ehElemento(v) {
    return !!v && typeof v === "object" && v.nodeType === 1;
  }

  function resolverElemento(elOuId) {
    if (ehElemento(elOuId)) return elOuId;
    if (typeof elOuId === "string" && raiz.document) {
      return raiz.document.getElementById(elOuId);
    }
    return null;
  }

  // ---- foco: quem e "focavel" e a armadilha de Tab/Shift+Tab ----

  function ehFocavel(el) {
    if (!ehElemento(el)) return false;
    if (el.hidden) return false;
    if (el.hasAttribute && el.hasAttribute("disabled")) return false;
    if (el.getAttribute && el.getAttribute("aria-hidden") === "true") return false;
    const tag = el.tagName;
    if (tag === "A") return el.hasAttribute("href");
    if (tag === "INPUT") return el.getAttribute("type") !== "hidden";
    if (TAGS_FOCAVEIS.has(tag)) return true;
    const tabindex = el.getAttribute ? el.getAttribute("tabindex") : null;
    return tabindex !== null && tabindex !== undefined && tabindex !== "-1";
  }

  // Varredura manual em pre-ordem (nao usa querySelectorAll) pra funcionar
  // igual em DOM real e no DOM simulado dos testes
  // (tests/js/bottom_sheet.test.js) - PRECISA ser pre-ordem (visita o pai
  // antes dos irmaos seguintes) pra bater com a ordem de Tab de verdade do
  // navegador: um campo dentro de um <label> mais cedo no HTML vem antes de
  // um botao irmao mais tarde, mesmo o campo estando "mais fundo" na arvore.
  function elementosFocaveis(container) {
    const resultado = [];
    if (!ehElemento(container)) return resultado;
    (function visitar(el) {
      const filhos = Array.from(el.children || []);
      for (const filho of filhos) {
        if (ehFocavel(filho)) resultado.push(filho);
        visitar(filho);
      }
    })(container);
    return resultado;
  }

  function prenderFoco(painel, evento) {
    const focaveis = elementosFocaveis(painel);
    if (!focaveis.length) {
      evento.preventDefault && evento.preventDefault();
      painel.focus && painel.focus();
      return;
    }
    const primeiro = focaveis[0];
    const ultimo = focaveis[focaveis.length - 1];
    const doc = raiz.document;
    const ativo = doc ? doc.activeElement : null;
    if (evento.shiftKey) {
      if (ativo === primeiro || focaveis.indexOf(ativo) === -1) {
        evento.preventDefault && evento.preventDefault();
        ultimo.focus();
      }
    } else if (ativo === ultimo || focaveis.indexOf(ativo) === -1) {
      evento.preventDefault && evento.preventDefault();
      primeiro.focus();
    }
  }

  // ---- reduced motion ----

  function podeAnimar() {
    // Sem matchMedia (ambiente de teste, navegador exotico) fica do lado
    // seguro: nao anima, fecha/abre na hora - nunca o contrario.
    try {
      return !!(raiz.matchMedia && !raiz.matchMedia("(prefers-reduced-motion: reduce)").matches);
    } catch {
      return false;
    }
  }

  // ---- scroll do body ----

  function bloquearScrollDoBody() {
    const body = raiz.document && raiz.document.body;
    if (body && body.classList) body.classList.add("bottom-sheet-bloqueado");
  }

  function liberarScrollDoBody() {
    const body = raiz.document && raiz.document.body;
    if (body && body.classList) body.classList.remove("bottom-sheet-bloqueado");
  }

  // ---- portal: o sheet sobe pro <body> enquanto esta aberto ----
  //
  // C2 (bug real): toda .tab-content roda a animacao de entrada do style.css com
  // `animation-fill-mode: both`, que DEIXA um `transform` aplicado na aba. Um ancestral
  // com transform vira o "containing block" de todo `position: fixed` de dentro e cria
  // um stacking context proprio - o sheet deixava de cobrir a tela (ficava preso a
  // altura da aba) e a barra de abas (#tabbar, z-index 10 na raiz) passava POR CIMA do
  // painel. Solucao: ao abrir, o sheet vai pro fim do <body> (um comentario marca o
  // lugar original); ao terminar de fechar, volta exatamente pro mesmo lugar. Quem busca
  // o sheet por id/querySelector continua achando; so os seletores CSS escopados pela aba
  // (#tab-x .algo) deixam de valer ENQUANTO ele esta aberto - por isso o visual do sheet
  // mora nos componentes (.campo, .btn, .bottom-sheet-*), nunca no CSS da aba.
  const marcaPorSheet = new WeakMap();

  function levarParaBody(sheet) {
    const doc = sheet.ownerDocument || raiz.document;
    const body = doc && doc.body;
    const pai = sheet.parentNode;
    if (!body || !pai || pai === body || marcaPorSheet.has(sheet)) return;
    if (typeof doc.createComment !== "function" || typeof pai.insertBefore !== "function") return;
    const marca = doc.createComment("bottom-sheet:" + (sheet.id || ""));
    pai.insertBefore(marca, sheet);
    marcaPorSheet.set(sheet, marca);
    body.appendChild(sheet);
  }

  function devolverAoLugar(sheet) {
    const marca = marcaPorSheet.get(sheet);
    if (!marca) return;
    marcaPorSheet.delete(sheet);
    const pai = marca.parentNode;
    if (pai && typeof pai.insertBefore === "function") {
      pai.insertBefore(sheet, marca);
      pai.removeChild && pai.removeChild(marca);
    }
    // marca sem pai (a secao inteira foi re-renderizada): o sheet fica no body, escondido -
    // continua achavel por id e abre normal da proxima vez.
  }

  // ---- estrutura interna (montada sozinha na 1a abertura) ----

  function encontrarFilhoComClasse(el, classe) {
    const filhos = el.children ? Array.from(el.children) : [];
    return filhos.find((f) => f.classList && f.classList.contains(classe)) || null;
  }

  function ligarArrastarParaFechar(sheet, painel, alca) {
    if (!alca || !alca.addEventListener || typeof raiz.PointerEvent === "undefined") return;
    let arrastando = false;
    let inicioY = 0;
    let deltaAtual = 0;

    alca.addEventListener("pointerdown", (e) => {
      arrastando = true;
      inicioY = e.clientY;
      painel.classList && painel.classList.add("bottom-sheet-painel--arrastando");
    });
    const doc = raiz.document;
    doc.addEventListener("pointermove", (e) => {
      if (!arrastando) return;
      deltaAtual = Math.max(0, e.clientY - inicioY);
      if (painel.style) painel.style.transform = `translateY(${deltaAtual}px)`;
    });
    const soltar = () => {
      if (!arrastando) return;
      arrastando = false;
      painel.classList && painel.classList.remove("bottom-sheet-painel--arrastando");
      if (painel.style) painel.style.transform = "";
      const passouDoLimiar = deltaAtual > LIMIAR_ARRASTAR_PX;
      deltaAtual = 0;
      if (passouDoLimiar) fecharBottomSheet(sheet);
    };
    doc.addEventListener("pointerup", soltar);
    doc.addEventListener("pointercancel", soltar);
  }

  function garantirEstrutura(sheet) {
    if (inicializados.has(sheet)) {
      return encontrarFilhoComClasse(sheet, "bottom-sheet-painel") || sheet;
    }
    inicializados.add(sheet);

    const painelExistente = encontrarFilhoComClasse(sheet, "bottom-sheet-painel");
    if (painelExistente) return painelExistente; // autor ja escreveu a estrutura na mao

    const doc = sheet.ownerDocument || raiz.document;
    if (!doc || !doc.createElement) return sheet; // DOM minimo demais: usa o proprio sheet

    const fundo = doc.createElement("div");
    fundo.className = "bottom-sheet-fundo";
    fundo.setAttribute("aria-hidden", "true");

    const painel = doc.createElement("div");
    painel.className = "bottom-sheet-painel";
    painel.setAttribute("tabindex", "-1");

    const alca = doc.createElement("div");
    alca.className = "bottom-sheet-alca";
    alca.setAttribute("aria-hidden", "true");
    painel.appendChild(alca);

    // Move todo o conteudo que o autor escreveu direto dentro de
    // `.bottom-sheet` (contrato em docs/agentes/fase7-visual.md) pra dentro
    // do painel - quem faz `sheet.querySelector(...)` continua achando tudo
    // normalmente, so muda quem e o pai imediato.
    while (sheet.firstChild) {
      painel.appendChild(sheet.firstChild);
    }

    sheet.appendChild(fundo);
    sheet.appendChild(painel);

    fundo.addEventListener("click", () => fecharBottomSheet(sheet));
    ligarArrastarParaFechar(sheet, painel, alca);

    return painel;
  }

  // ---- listeners globais (ESC, Tab, submit com sucesso) ----

  function aoTeclar(evento) {
    const topo = abertos[abertos.length - 1];
    if (!topo) return;
    if (evento.key === "Escape" || evento.key === "Esc") {
      evento.preventDefault && evento.preventDefault();
      fecharBottomSheet(topo);
      return;
    }
    if (evento.key === "Tab") {
      const painel = encontrarFilhoComClasse(topo, "bottom-sheet-painel") || topo;
      prenderFoco(painel, evento);
    }
  }

  function aoSucessoDeFormulario(evento) {
    const alvo = evento.target;
    if (!ehElemento(alvo) || !alvo.closest) return;
    const form = alvo.closest(`[${ATRIBUTO_FECHA_AO_ENVIAR}]`);
    if (!form) return;
    const sheet = alvo.closest(".bottom-sheet");
    if (sheet) fecharBottomSheet(sheet);
  }

  let listenersGlobaisLigados = false;
  function ligarListenersGlobais() {
    if (listenersGlobaisLigados || !raiz.document) return;
    listenersGlobaisLigados = true;
    raiz.document.addEventListener("keydown", aoTeclar);
    raiz.document.addEventListener("bottomsheet:sucesso", aoSucessoDeFormulario);
  }

  // ---- API publica ----

  function abrirBottomSheet(elOuId) {
    const sheet = resolverElemento(elOuId);
    if (!ehElemento(sheet) || abertos.includes(sheet)) return;

    ligarListenersGlobais();
    const painel = garantirEstrutura(sheet);

    const doc = raiz.document;
    origemPorSheet.set(sheet, (doc && doc.activeElement) || null);

    levarParaBody(sheet);
    sheet.hidden = false;
    if (!sheet.getAttribute || !sheet.getAttribute("role")) {
      sheet.setAttribute && sheet.setAttribute("role", "dialog");
    }
    sheet.setAttribute && sheet.setAttribute("aria-modal", "true");
    if (sheet.classList) {
      sheet.classList.remove(CLASSE_FECHANDO);
      sheet.classList.add(CLASSE_ABERTO);
    }

    abertos.push(sheet);
    bloquearScrollDoBody();

    const focar = () => {
      const alvo = elementosFocaveis(painel)[0] || painel;
      alvo.focus && alvo.focus();
    };
    if (raiz.requestAnimationFrame) raiz.requestAnimationFrame(focar);
    else focar();
  }

  function fecharBottomSheet(elOuId) {
    const sheet = resolverElemento(elOuId);
    if (!ehElemento(sheet)) return;
    const indice = abertos.indexOf(sheet);
    if (indice === -1) return; // ja fechado - idempotente

    abertos.splice(indice, 1);

    const finalizar = () => {
      // C2: reaberto durante a animacao de fechar (toque rapido duplo) - o fechamento
      // antigo nao pode esconder o sheet que ja esta aberto de novo.
      if (abertos.includes(sheet)) return;
      sheet.hidden = true;
      if (sheet.classList) {
        sheet.classList.remove(CLASSE_ABERTO);
        sheet.classList.remove(CLASSE_FECHANDO);
      }
      sheet.removeAttribute && sheet.removeAttribute("aria-modal");
      devolverAoLugar(sheet);

      if (!abertos.length) liberarScrollDoBody();

      const origem = origemPorSheet.get(sheet);
      origemPorSheet.delete(sheet);
      if (origem && origem.focus && !origem.disabled) {
        try {
          origem.focus();
        } catch {
          /* elemento de origem pode ter saido do DOM - ignora */
        }
      }

      if (raiz.CustomEvent && sheet.dispatchEvent) {
        sheet.dispatchEvent(
          new raiz.CustomEvent("bottomsheet:fechado", {
            bubbles: true,
            detail: { id: sheet.id || null },
          })
        );
      }
    };

    if (sheet.classList && podeAnimar()) {
      sheet.classList.add(CLASSE_FECHANDO);
      sheet.classList.remove(CLASSE_ABERTO);
      if (raiz.setTimeout) raiz.setTimeout(finalizar, DURACAO_TRANSICAO_MS);
      else finalizar();
    } else {
      finalizar();
    }
  }

  // ---- gatilhos declarativos (so em browser de verdade) ----

  function ligarGatilhosDeclarativos() {
    if (!raiz.document || !raiz.document.addEventListener) return;
    raiz.document.addEventListener("click", (evento) => {
      const alvo = evento.target;
      if (!ehElemento(alvo) || !alvo.closest) return;
      const abre = alvo.closest("[data-abre-sheet]");
      if (abre) {
        const id = abre.getAttribute("data-abre-sheet");
        if (id) abrirBottomSheet(id);
        return;
      }
      const fecha = alvo.closest("[data-fecha-sheet]");
      if (fecha) {
        const sheet = fecha.closest(".bottom-sheet");
        if (sheet) fecharBottomSheet(sheet);
      }
    });
  }

  if (typeof window !== "undefined") {
    ligarGatilhosDeclarativos();
  }

  raiz.abrirBottomSheet = abrirBottomSheet;
  raiz.fecharBottomSheet = fecharBottomSheet;

  if (typeof module !== "undefined" && module.exports) {
    // Node (testes) - expoe tambem os helpers internos usados pela armadilha
    // de foco, pra tests/js/bottom_sheet.test.js poder checar sem precisar
    // recriar a logica.
    module.exports = {
      abrirBottomSheet,
      fecharBottomSheet,
      elementosFocaveis,
      ehFocavel,
    };
  }
})(typeof window !== "undefined" ? window : globalThis);
