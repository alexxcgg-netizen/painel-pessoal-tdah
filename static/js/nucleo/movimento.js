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

// Troca de aba: View Transitions nativo SO no Safari (o alvo real e o
// iPhone) - cross-fade + translateY 8px via ::view-transition-old/new(root)
// em static/css/ui/movimento.css. No Chromium (inclusive Chromium headless
// dos testes) e em qualquer navegador sem suporte, `fn` roda direto e
// style.css cuida do fallback (.entra-direita/.entra-esquerda), sem chamar
// a API nativa.
//
// ACHADO (Vis C2, medido com Playwright/Chromium headless CPU 4x): chamar
// document.startViewTransition no Chromium deixava o overlay de
// ::view-transition-group(root) "vivo" depois da troca (a promise finished
// as vezes nao resolve nesse Chromium headless) e ele intercepta o proximo
// toque - quebrou o teste tests/test_vel_a2b_otimista.py (concluir tarefa
// direto depois de trocar pra aba Tarefas parava de responder ao toque
// real, so as chamadas .click() sinteticas continuavam funcionando). Erro
// silencioso (sem pageerror), so detectavel pelo toque real nao gerar POST.
//
// Faixa limpa/A-anim: religa a chamada real, mas SO quando o motor NAO e
// Chromium (navigator.userAgent tem "Safari" e nao tem "Chrome"/"CriOS" -
// Chromium/Chrome/Edge/Opera/o proprio Chrome no iOS (CriOS) sempre
// incluem "Chrome" na UA; so o Safari de verdade tem "Safari" sem
// "Chrome"). Alem disso, um timeout de seguranca chama
// transition.skipTransition() em 400ms: se por qualquer motivo a promise
// "finished" nunca resolver nesse Safari tambem, a transicao e forcada a
// terminar em vez de ficar com o overlay vivo travando o proximo toque -
// mesmo risco do achado acima, agora coberto. Nenhum teste deste repo roda
// em WebKit real (so Chromium, que sempre cai no fallback CSS), entao esse
// caminho novo nunca é exercitado pela suite - fica documentado aqui pro
// dono confirmar num Safari 18 de verdade antes de confiar 100%.
function ehSafariNaoChromium() {
  try {
    const ua = (typeof navigator !== "undefined" && navigator.userAgent) || "";
    return ua.indexOf("Safari") !== -1 && ua.indexOf("Chrome") === -1 && ua.indexOf("CriOS") === -1;
  } catch (erro) {
    return false; // sem navigator (ambiente de teste sem DOM real): assume que nao e Safari
  }
}

function trocarAba(fn) {
  const podeUsarNativo =
    typeof document !== "undefined" &&
    typeof document.startViewTransition === "function" &&
    !reduzirMovimento() &&
    ehSafariNaoChromium();
  if (!podeUsarNativo) {
    fn();
    return;
  }
  let transition;
  try {
    transition = document.startViewTransition(fn);
  } catch (erro) {
    fn(); // startViewTransition rejeitou antes de rodar fn (raro) - roda direto, sem perder a troca
    return;
  }
  if (transition && typeof transition.skipTransition === "function") {
    setTimeout(() => {
      try {
        transition.skipTransition();
      } catch (erro) {
        /* ja tinha terminado sozinha - nada a fazer */
      }
    }, 400);
  }
}

// Cards entrando escalonado (30ms), so os 8 primeiros QUE APARECEM SEM
// ROLAR, so na 1a vez que a aba/lista abre nesta sessao de pagina (dataset
// flag no container - troca de aba de volta NAO repete a entrada, senao vira
// "tudo pisca de novo" a cada toque, o que o brief pede pra evitar).
// Vel: chamado de dentro de um requestAnimationFrame (navegacao.js), ja
// depois da aba revelada - por isso o getBoundingClientRect aqui (forca
// layout) roda no lugar certo (rAF, antes do proximo paint) e so nos
// primeiros itens: para de olhar a lista assim que um item cai fora da
// janela (ordem vertical - o resto abaixo tambem estaria fora), nunca mede
// nem escreve estilo na lista inteira quando ela e grande (Painel/Vida podem
// ter mais de 8 filhos).
function marcarEntradaEscalonada(container, seletorItens) {
  if (!container || container.dataset.c2Entrou === "1") return;
  container.dataset.c2Entrou = "1";
  if (reduzirMovimento()) return;
  const itens = container.querySelectorAll(seletorItens || ":scope > *");
  const alturaJanela = typeof window !== "undefined" && typeof window.innerHeight === "number" ? window.innerHeight : null;
  let marcados = 0;
  for (let i = 0; i < itens.length && marcados < 8; i++) {
    const el = itens[i];
    if (alturaJanela !== null && typeof el.getBoundingClientRect === "function") {
      const r = el.getBoundingClientRect();
      if (r.top >= alturaJanela) break; // abaixo da dobra: para (ordem vertical, o resto tambem esta)
      if (r.bottom <= 0) continue; // acima da dobra (raro aqui, mas nao conta)
    }
    el.style.setProperty("--i", marcados);
    el.classList.add("c2-entra");
    marcados++;
  }
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
  // Vel: loadResumoFinancas roda de novo a cada troca de aba/refresh (nao so
  // na 1a vez) - sem esta marca, um IntersectionObserver novo era criado e
  // disparava TODA vez que a aba Financas era revisitada (o container ja
  // esta na tela assim que a aba aparece), repetindo querySelectorAll +
  // getTotalLength + escrita de estilo em toda troca, nao so na entrada real
  // do card. Mesma marca dataset usada em marcarEntradaEscalonada.
  if (container.dataset.c2GraficoEntrou === "1") return;
  container.dataset.c2GraficoEntrou = "1";
  // Vel: nada de medir (getTotalLength forca layout) nem escrever --i no
  // momento em que a aba Financas acabou de carregar - so quando o card de
  // verdade entra na tela (isIntersecting) e dentro de um requestAnimationFrame,
  // pra nao competir com o "resultado visivel" da troca de aba/loadResumoFinancas.
  const obs = new IntersectionObserver(
    (entradas, observer) => {
      entradas.forEach((entrada) => {
        if (!entrada.isIntersecting) return;
        observer.disconnect();
        requestAnimationFrame(() => {
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
          barras.forEach((b) => b.classList.add("c2-barra-desenha"));
          if (linha) linha.classList.add("c2-linha-desenha");
        });
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
  // Vel: o chevron usava seletor CSS :has() (detalhe do wrapper) pra saber se
  // esta aberto - :has() e caro de recalcular a cada mudanca de estilo/DOM
  // (inclusive quando a aba/lista em volta e revelada), e entrava no caminho
  // quente da troca de aba. Uma classe setada aqui no toggle (summary sabe o
  // proprio estado, sem o navegador precisar varrer os filhos) substitui os
  // seletores :has() em movimento.css/conversa.css sem mudar o visual.
  summary.classList.toggle("c2-resumo-aberto", abertoInicial);

  summary.addEventListener("click", (evento) => {
    if (evento && typeof evento.preventDefault === "function") evento.preventDefault();
    const aberto = details.dataset.c2Aberto === "1";
    details.dataset.c2Aberto = aberto ? "0" : "1";
    summary.setAttribute("aria-expanded", aberto ? "false" : "true");
    externo.classList.toggle("c2-details-fechado", aberto);
    summary.classList.toggle("c2-resumo-aberto", !aberto);
  });
}

// Tarefa concluida: fecha o espaco que ela deixa na lista sem "pular".
// tarefas.js ja marca .saindo IMEDIATAMENTE no toque (sincrono, nada mais
// nessa linha - e o que a Vel A2b mede em <150ms). Esta funcao roda so
// DEPOIS, dentro de um requestAnimationFrame chamado por tarefas.js (nunca
// no clique em si), e liga o colapso de altura (grid-template-rows 1fr ->
// 0fr, tecnica da skill animacoes-interface) que ja existe em
// li.item.c2-colapsavel/c2-saindo-colapsa (ui/movimento.css) - so faltava
// alguem ligar as classes. Duas etapas (a classe base primeiro, a que
// dispara a transicao so no rAF seguinte) pra garantir que o navegador
// registre o "1fr" antes de mudar pra "0fr" (senao nao ha transicao pra
// ver). Confere .saindo de novo antes da 2a classe: se o POST falhou nesse
// meio tempo (erro 500) e tarefas.js ja tirou .saindo pra devolver o item,
// aqui desiste sem colapsar por baixo do usuario.
function colapsarSaidaLista(li) {
  if (!li || !li.classList || typeof requestAnimationFrame !== "function") return;
  if (reduzirMovimento()) return; // reduzir movimento: sem colapso animado, li.remove() de tarefas.js ja basta
  li.classList.add("c2-colapsavel");
  requestAnimationFrame(() => {
    if (li.isConnected && li.classList.contains("saindo")) li.classList.add("c2-saindo-colapsa");
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
    ehSafariNaoChromium,
    marcarEntradaEscalonada,
    animarConclusaoTarefa,
    colapsarSaidaLista,
    animarGraficoNaEntrada,
    saidaAnimada,
    ligarDetalheAnimado,
  };
}
