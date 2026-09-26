// static/js/nucleo/movimento.js - Faixa vis/C2-animacao (skill animacoes-interface).
// Novo arquivo, dono unico (C2). Helpers de movimento reaproveitados por
// navegacao.js, tarefas.js e gastos.js. Script classico (escopo global
// compartilhado) - carregado em templates/scripts.html ANTES de navegacao.js
// (que ja chama trocarAba na primeira troca de aba) e antes dos scripts de
// secao (que usam marcarEntradaEscalonada/animarGraficoNaEntrada).

function reduzirMovimento() {
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch (erro) {
    return false; // sem matchMedia (ambiente de teste sem DOM real): assume sem reducao
  }
}

// Troca de aba: View Transitions nativo onde existe (Chromium/Safari 18+),
// cross-fade + translateY 8px via ::view-transition-old/new(root) em
// static/css/ui/movimento.css. Sem suporte, ou com "reduzir movimento", `fn`
// roda direto e style.css cuida do fallback (.entra-direita/.entra-esquerda,
// ou nenhuma animacao com reduzir movimento - os --dur-* zeram sozinhos).
// ACHADO (Vis C2, medido com Playwright/Chromium headless CPU 4x): chamar
// document.startViewTransition aqui deixava o overlay de
// ::view-transition-group(root) "vivo" depois da troca (a promise finished
// as vezes nao resolve nesse Chromium headless) e ele intercepta o proximo
// toque - quebrou o teste tests/test_vel_a2b_otimista.py (concluir tarefa
// direto depois de trocar pra aba Tarefas parava de responder ao toque
// real, so a chamadas .click() sinteticas continuavam funcionando). Erro
// silencioso (sem pageerror), so detectavel pelo toque real nao gerar POST -
// por isso a funcao fica pronta (CSS em ui/movimento.css ja cobre o
// ::view-transition-*(root)) mas SEM religar o startViewTransition real
// ate confirmar num Chromium mais novo/nao-headless. Fallback (CSS
// entra-direita/entra-esquerda -> tabEntra, ambos no token --dur-media/
// --ease-saida + translateY(--deslocamento-entrada) em style.css) cobre a
// troca de aba sozinho, sem esse risco.
function trocarAba(fn) {
  fn();
}

// Cards entrando escalonado (30ms), so os 8 primeiros, so na 1a vez que a
// aba/lista abre nesta sessao de pagina (dataset flag no container - troca
// de aba de volta NAO repete a entrada, senao vira "tudo pisca de novo" a
// cada toque, o que o brief pede pra evitar).
function marcarEntradaEscalonada(container, seletorItens) {
  if (!container || container.dataset.c2Entrou === "1") return;
  container.dataset.c2Entrou = "1";
  if (reduzirMovimento()) return;
  const itens = container.querySelectorAll(seletorItens || ":scope > *");
  itens.forEach((el, i) => {
    if (i >= 8) return;
    el.style.setProperty("--i", i);
    el.classList.add("c2-entra");
  });
}

// Concluir tarefa: prepara o SVG do check (stroke-dasharray = comprimento
// real do path, medido com getTotalLength) e risca o titulo. Chamado pelo
// botao "concluir" antes de remover o item (tarefas.js).
function animarConclusaoTarefa(li) {
  if (!li || reduzirMovimento()) return;
  const svg = li.querySelector(".c2-check-desenha, button.primario svg");
  const caminho = svg && svg.querySelector ? svg.querySelector("path, circle") : null;
  if (caminho && typeof caminho.getTotalLength === "function") {
    try {
      const len = caminho.getTotalLength();
      caminho.style.setProperty("--c2-check-len", len);
      caminho.classList.add("c2-check-desenha");
    } catch (erro) {
      /* SVG sem getBBox (jsdom/ambiente de teste) - sem risco, so nao anima o traco */
    }
  }
  const titulo = li.querySelector(".item-titulo");
  if (titulo) titulo.classList.add("c2-titulo-riscando");
}

// Grafico (barra/linha) so anima na 1a vez que aparece na tela - observa via
// IntersectionObserver e desliga sozinho depois de disparar uma vez por
// elemento (nunca reanima em toda atualizacao dos dados).
function animarGraficoNaEntrada(container) {
  if (!container || reduzirMovimento()) return;
  if (typeof IntersectionObserver !== "function") return; // ambiente sem DOM real (teste)
  const barras = container.querySelectorAll(".fc-catbar");
  barras.forEach((b, i) => {
    b.style.setProperty("--i", i);
  });
  const linha = container.querySelector(".fc-linha");
  if (linha && typeof linha.getTotalLength === "function") {
    try {
      linha.style.setProperty("--c2-linha-len", linha.getTotalLength());
    } catch (erro) {
      /* sem getBBox - segue sem medir */
    }
  }
  const obs = new IntersectionObserver(
    (entradas, observer) => {
      entradas.forEach((entrada) => {
        if (!entrada.isIntersecting) return;
        barras.forEach((b) => b.classList.add("c2-barra-desenha"));
        if (linha) linha.classList.add("c2-linha-desenha");
        observer.disconnect();
      });
    },
    { threshold: 0.2 }
  );
  obs.observe(container);
}

// Node (tests/js/*.test.js roda sem DOM real) - mesmo padrao de export duplo
// usado no resto do nucleo (ex: secao-recolhivel.js).
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    reduzirMovimento,
    trocarAba,
    marcarEntradaEscalonada,
    animarConclusaoTarefa,
    animarGraficoNaEntrada,
  };
}
