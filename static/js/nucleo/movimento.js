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

// <details> que expande sem "pulo": o navegador mostra/esconde o conteudo
// de um <details> na hora (sem transicao nenhuma) - aqui o <details> fica
// SEMPRE aberto no DOM (details.open = true, permanente) e um wrapper novo
// (grid-template-rows 0fr -> 1fr, filho com overflow:hidden - tecnica da
// skill animacoes-interface) faz o visual de abrir/fechar. summary.click()
// tem o comportamento nativo cancelado (preventDefault) pra nao entrar em
// conflito com esse estado sintetico. Usado por secoes/gastos/gastos.js no
// <details id="fc-card-ultimos-dias">.
function ligarDetalheAnimado(details) {
  if (!details || details.dataset.c2DetalheLigado === "1") return;
  if (typeof document === "undefined" || typeof document.createElement !== "function") return;
  const summary = details.querySelector ? details.querySelector("summary") : null;
  if (!summary) return;
  details.dataset.c2DetalheLigado = "1";

  const abertoInicial = !!details.open;
  const externo = document.createElement("div");
  externo.className = "c2-details-externo" + (abertoInicial ? "" : " c2-details-fechado");
  const interno = document.createElement("div");
  interno.className = "c2-details-interno";
  const filhos = Array.prototype.slice.call(details.children).filter((el) => el !== summary);
  filhos.forEach((el) => interno.appendChild(el));
  externo.appendChild(interno);
  details.appendChild(externo);

  details.open = true; // fica sempre aberto no DOM - o wrapper controla o visual
  details.dataset.c2Aberto = abertoInicial ? "1" : "0";
  summary.setAttribute("aria-expanded", abertoInicial ? "true" : "false");

  summary.addEventListener("click", (evento) => {
    if (evento && typeof evento.preventDefault === "function") evento.preventDefault();
    const aberto = details.dataset.c2Aberto === "1";
    details.dataset.c2Aberto = aberto ? "0" : "1";
    summary.setAttribute("aria-expanded", aberto ? "false" : "true");
    externo.classList.toggle("c2-details-fechado", aberto);
  });
}

// Toast/aviso fixo (banner de erro, offline, "servidor acordando" -
// nucleo/api.js, secoes/topo/captura.js): entra com o CSS de cada banner
// (translateY + opacity, --dur-media, ja tocava sozinho ao [hidden] sair) -
// aqui so cuida da SAIDA, que antes era instantanea ([hidden]=true direto).
// Adiciona .c2-toast-sai (--dur-rapida, fade), espera o animationend (com
// timeout de seguranca caso o navegador nao dispare) e so entao chama
// aoEsconder - nunca trava (reduzirMovimento esconde na hora, sem esperar).
function saidaAnimada(el, aoEsconder) {
  if (!el) {
    if (aoEsconder) aoEsconder();
    return;
  }
  if (reduzirMovimento() || typeof requestAnimationFrame !== "function") {
    if (aoEsconder) aoEsconder();
    return;
  }
  el.classList.add("c2-toast-sai");
  let feito = false;
  const finalizar = () => {
    if (feito) return;
    feito = true;
    el.classList.remove("c2-toast-sai");
    if (aoEsconder) aoEsconder();
  };
  if (typeof el.addEventListener === "function") {
    el.addEventListener("animationend", finalizar, { once: true });
  }
  setTimeout(finalizar, 200);
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
    saidaAnimada,
    ligarDetalheAnimado,
  };
}
