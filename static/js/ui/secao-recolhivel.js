// static/js/ui/secao-recolhivel.js - Fase 7 (V0c): comportamento de secao recolhivel
// reutilizavel (contrato em docs/agentes/fase7-visual.md).
//
//   <section class="secao-recolhivel" data-aberto="false" data-secao-id="memoria">
//     <button class="secao-cabecalho" aria-expanded="false">Titulo <span class="chevron"></span></button>
//     <div class="secao-conteudo">...</div>
//   </section>
//
// Liga sozinho toda `.secao-recolhivel` da pagina no carregamento (inclusive as que ja
// estao no HTML servido pelo Flask) e observa o DOM pra ligar as que forem inseridas depois
// (ex: lista recarregada via fetch) - por isso o service worker/HTML pode inserir a secao a
// qualquer momento sem precisar chamar nada manualmente. Quem preferir ligar na mao (ex: logo
// apos montar um pedaco de HTML) pode chamar a funcao global `ligarSecoesRecolhiveis(raiz)`
// diretamente, que e idempotente (nao liga a mesma secao duas vezes).
//
// Estrutura dupla de export igual visao-dia.js/voz-comando.js: em navegador vira o global
// `ligarSecoesRecolhiveis` (script classico, escopo compartilhado); em Node (testes, sem DOM
// real) a logica de estado/localStorage fica acessivel via module.exports com um DOM
// simulado minimo (ver tests/js/secao_recolhivel.test.js).
const SecaoRecolhivel = (function () {
  const CHAVE_PREFIXO = "secaoRecolhivel:";

  // ---- localStorage (try/catch em tudo - modo privado/quota cheia/SSR nao pode quebrar a secao) ----

  function lerEstadoSalvo(secaoId) {
    if (!secaoId) return null;
    try {
      if (typeof localStorage === "undefined" || !localStorage) return null;
      const valor = localStorage.getItem(CHAVE_PREFIXO + secaoId);
      if (valor === "1") return true;
      if (valor === "0") return false;
      return null;
    } catch (erro) {
      return null;
    }
  }

  function salvarEstado(secaoId, aberto) {
    if (!secaoId) return; // sem data-secao-id: nao salva (regra explicita do contrato)
    try {
      if (typeof localStorage === "undefined" || !localStorage) return;
      localStorage.setItem(CHAVE_PREFIXO + secaoId, aberto ? "1" : "0");
    } catch (erro) {
      // localStorage indisponivel/bloqueado - a secao continua funcionando, so nao lembra o estado
    }
  }

  // ---- altura animada do corpo (max-height medido, ver secao.css pra transicao) ----

  function abrirConteudo(conteudoEl) {
    if (!conteudoEl || !conteudoEl.style) return;
    const altura = conteudoEl.scrollHeight || 0;
    conteudoEl.style.maxHeight = altura + "px";
    if (typeof conteudoEl.addEventListener !== "function") return;
    const aoFimTransicao = (evento) => {
      if (evento && evento.propertyName && evento.propertyName !== "max-height") return;
      conteudoEl.style.maxHeight = "none"; // libera pra crescer sem limite (conteudo dinamico depois de aberto)
      if (typeof conteudoEl.removeEventListener === "function") {
        conteudoEl.removeEventListener("transitionend", aoFimTransicao);
      }
    };
    conteudoEl.addEventListener("transitionend", aoFimTransicao);
  }

  function fecharConteudo(conteudoEl) {
    if (!conteudoEl || !conteudoEl.style) return;
    const atual = conteudoEl.style.maxHeight;
    if (!atual || atual === "none") {
      // estava totalmente aberto (sem limite) - fixa a altura atual antes de poder animar pra 0
      conteudoEl.style.maxHeight = (conteudoEl.scrollHeight || 0) + "px";
    }
    const fecharAgora = () => {
      conteudoEl.style.maxHeight = "0px";
    };
    if (typeof requestAnimationFrame === "function") {
      requestAnimationFrame(fecharAgora);
    } else {
      fecharAgora();
    }
  }

  // ---- teclado: conteudo recolhido fora do Tab (M1 r2) ----
  //
  // Recolhida, a secao so tem max-height 0 + overflow hidden: os botoes/campos de dentro
  // continuavam no Tab (foco "sumia" dentro de uma caixa de altura zero) e no leitor de tela.
  // `inert` tira tudo isso do Tab, do clique e da arvore de acessibilidade, sem mudar o visual
  // nem a transicao de altura (o conteudo segue visivel enquanto encolhe). Se o foco estava
  // dentro do conteudo na hora de recolher, ele volta pro cabecalho em vez de cair no <body>.

  function contemFoco(conteudoEl) {
    if (typeof document === "undefined" || !document || typeof conteudoEl.contains !== "function") return false;
    const ativo = document.activeElement;
    return !!ativo && ativo !== conteudoEl && conteudoEl.contains(ativo);
  }

  function definirInerte(conteudoEl, cabecalhoEl, inerte) {
    if (inerte && cabecalhoEl && typeof cabecalhoEl.focus === "function" && contemFoco(conteudoEl)) {
      cabecalhoEl.focus();
    }
    try {
      conteudoEl.inert = inerte;
    } catch (erro) {
      // navegador sem suporte a `inert`: a secao continua funcionando, so sem essa guarda
    }
  }

  // ---- estado aberto/fechado (DOM + aria + localStorage) ----

  function definirAberto(secaoEl, cabecalhoEl, conteudoEl, aberto, opts) {
    opts = opts || {};
    secaoEl.dataset.aberto = aberto ? "true" : "false";
    if (cabecalhoEl && typeof cabecalhoEl.setAttribute === "function") {
      cabecalhoEl.setAttribute("aria-expanded", aberto ? "true" : "false");
    }
    if (conteudoEl) {
      definirInerte(conteudoEl, cabecalhoEl, !aberto);
      if (opts.semAnimar) {
        conteudoEl.style.maxHeight = aberto ? "none" : "0px";
      } else if (aberto) {
        abrirConteudo(conteudoEl);
      } else {
        fecharConteudo(conteudoEl);
      }
    }
    if (!opts.semSalvar) salvarEstado(secaoEl.dataset.secaoId, aberto);
  }

  // ---- ligar uma secao (idempotente) ----

  function ligarUma(secaoEl) {
    if (!secaoEl || typeof secaoEl.querySelector !== "function") return;
    if (secaoEl.dataset && secaoEl.dataset.secaoLigada === "1") return; // ja ligada, nao duplica listener

    const cabecalhoEl = secaoEl.querySelector(".secao-cabecalho");
    if (!cabecalhoEl) return; // estrutura fora do contrato - nao quebra, so nao liga
    const conteudoEl = secaoEl.querySelector(".secao-conteudo");

    secaoEl.dataset.secaoLigada = "1";

    const secaoId = secaoEl.dataset.secaoId || null;
    const salvo = lerEstadoSalvo(secaoId);
    const abertoInicial = salvo !== null ? salvo : secaoEl.dataset.aberto === "true";

    // estado inicial sem animar e sem regravar no localStorage o que acabou de ler dele
    definirAberto(secaoEl, cabecalhoEl, conteudoEl, abertoInicial, { semAnimar: true, semSalvar: true });

    if (typeof cabecalhoEl.addEventListener === "function") {
      cabecalhoEl.addEventListener("click", () => {
        const abertoAtual = secaoEl.dataset.aberto === "true";
        definirAberto(secaoEl, cabecalhoEl, conteudoEl, !abertoAtual);
      });
    }
  }

  // ---- ligar todas as secoes sob uma raiz (global, chamavel a qualquer momento) ----

  function ligarSecoesRecolhiveis(raiz) {
    const base = raiz || (typeof document !== "undefined" ? document : null);
    if (!base) return;
    const temClasse =
      base.classList && typeof base.classList.contains === "function" && base.classList.contains("secao-recolhivel");
    if (temClasse) ligarUma(base);
    if (typeof base.querySelectorAll !== "function") return;
    const encontradas = base.querySelectorAll(".secao-recolhivel");
    for (let i = 0; i < encontradas.length; i++) ligarUma(encontradas[i]);
  }

  return {
    CHAVE_PREFIXO,
    lerEstadoSalvo,
    salvarEstado,
    definirAberto,
    ligarUma,
    ligarSecoesRecolhiveis,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  // Node (testes) - DOM simulado minimo, sem browser real.
  module.exports = SecaoRecolhivel;
}

// ---- wiring de navegador (DOM real) ----------------------------------------
if (typeof document !== "undefined" && typeof window !== "undefined") {
  window.ligarSecoesRecolhiveis = SecaoRecolhivel.ligarSecoesRecolhiveis;

  const iniciar = () => {
    SecaoRecolhivel.ligarSecoesRecolhiveis(document);
    if (typeof MutationObserver !== "undefined" && document.body) {
      const observer = new MutationObserver((mutacoes) => {
        mutacoes.forEach((mutacao) => {
          if (!mutacao.addedNodes) return;
          mutacao.addedNodes.forEach((node) => {
            if (node.nodeType === 1) SecaoRecolhivel.ligarSecoesRecolhiveis(node);
          });
        });
      });
      observer.observe(document.body, { childList: true, subtree: true });
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar);
  } else {
    iniciar();
  }
}
