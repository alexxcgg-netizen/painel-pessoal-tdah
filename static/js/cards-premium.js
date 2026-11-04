// Acabamento dos cards do chat (2026-10-13; "sem cara de IA" em 04/11/2026, linguagem D) - camada
// por cima do registro (cards.js / cards-tipos.js / cards-vivos.js), sem mexer em renderizador:
//  - card novo chega com profundidade (desfoque -> nitido) e as pecas entram em cascata;
//  - SAIU em 04/11 (cara de IA, pedido do Alex): fio de luz na borda, brilho que passa no vidro,
//    selo aceso no icone, luz que segue o dedo e inclinacao 3D. O toque so cede um tico;
//  - numero grande (valor do gasto, hora do lembrete, % da meta) rola feito odometro e
//    "assenta" no valor certo; a barra da meta enche do zero;
//  - tarefa concluida pelo card solta um confete curtinho na cor do card;
//  - desfazer "expira" o card (encolhe um tico e volta) em vez de so apagar seco.
// Tudo tem estado final estatico: historico abre parado, prefers-reduced-motion nao anima.
(function (raiz) {
  "use strict";

  const reduzido = () => !!(raiz.matchMedia && raiz.matchMedia("(prefers-reduced-motion: reduce)").matches);

  // numeros que viram odometro (os cartoes vivos ja contam os deles com data-contar-*)
  const SELETOR_ODOMETRO = [
    ".card-valor-grande:not(.oculto)",
    ".card-hora-grande",
    ".card-meta-valores strong",
    ".card-contrato-meta .card-linha-meta strong",
  ].join(",");

  const ODO_DURACAO = 1050; // ms do digito mais lento
  const ODO_ESPERA_CUPOM = 1150; // ms: a impressora termina o papel em ~1,5 s
  const ODO_PASSO = 45; // atraso entre um digito e o proximo (esquerda -> direita)

  function escapar(c) {
    return c === "&" ? "&amp;" : c === "<" ? "&lt;" : c === ">" ? "&gt;" : c;
  }

  // Troca o texto por colunas de digitos que rolam ate o valor; no fim volta pro texto
  // puro (o card desfeito risca o valor, leitor de tela le normal).
  // `espera` (ms): atraso extra antes de rolar (o total do cupom so rola quando o papel ja saiu da impressora)
  function odometro(el, espera = 0) {
    if (!el || el.dataset.odometro) return;
    const final = el.textContent;
    const digitos = final.replace(/\D/g, "").length;
    if (!digitos || final.length > 24) return;
    el.dataset.odometro = "1";
    el.setAttribute("aria-label", final.trim());
    let i = 0;
    el.innerHTML = Array.from(final)
      .map((c) => {
        if (!/\d/.test(c)) return `<span class="odo-fixo" aria-hidden="true">${escapar(c)}</span>`;
        const ordem = i++;
        // o da direita gira mais (como odometro de verdade) e termina por ultimo
        const voltas = 10 + Number(c);
        const atraso = ordem * ODO_PASSO + espera;
        const dur = ODO_DURACAO - (digitos - 1 - ordem) * 60;
        const fita = "0123456789".repeat(2).split("").map((d) => `<i>${d}</i>`).join("");
        return `<span class="odo-dig" aria-hidden="true" style="--odo-alvo:${voltas};--odo-atraso:${atraso}ms;--odo-dur:${Math.max(500, dur)}ms"><span class="odo-fita">${fita}</span></span>`;
      })
      .join("");
    const total = (digitos - 1) * ODO_PASSO + ODO_DURACAO + 120 + espera;
    setTimeout(() => {
      el.textContent = final;
      el.removeAttribute("aria-label");
      delete el.dataset.odometro;
    }, total);
  }

  const EASE_SUAVE = "cubic-bezier(0.22, 1, 0.36, 1)";
  const PECA_INICIO = 230; // ms depois da chegada do card: o vidro ja abriu
  const PECA_PASSO = 75;

  // Card que se monta: as pecas de dentro (titulo, numero, grafico, lista, rodape) entram uma
  // depois da outra, de cima pra baixo. (O fio de luz na borda saiu em 04/11: cara de IA.)
  function montar(card, chegadaMs) {
    if (typeof document === "undefined") return;
    const pecas = Array.from(card.children).filter((el) => !el.classList.contains("card-confete"));
    pecas.forEach((p, k) => {
      if (typeof p.animate !== "function") return;
      p.animate(
        [
          { opacity: 0, translate: "0 8px", filter: "blur(3px)" },
          { opacity: 1, translate: "0 0", filter: "blur(0)" },
        ],
        { duration: 560, delay: chegadaMs + PECA_INICIO + k * PECA_PASSO, easing: EASE_SUAVE, fill: "backwards" }
      );
    });
  }

  // Toca a chegada so nos cards de uma resposta NOVA (chat.js chama logo depois de anexar).
  function animar(grupo) {
    if (!grupo || !grupo.querySelectorAll || reduzido()) return;
    grupo.querySelectorAll(".card-contrato").forEach((card, i) => {
      card.classList.add("card-novo");
      card.style.setProperty("--chegada", `${i * 90}ms`);
      // pilula D (cards-d.js) entra inteira com a mola dela; o resto monta peca por peca
      if (!card.classList.contains("card-contrato-fallback") && !card.classList.contains("card-d")) montar(card, i * 90);
      // o numero so comeca a rolar quando o card ja esta assentando
      setTimeout(
        () =>
          card.querySelectorAll(SELETOR_ODOMETRO).forEach((n) =>
            // total do cupom que sai da impressora: so rola quando o papel ja desceu (Lab v4, cupom-impresso)
            odometro(n, n.closest(".tx-cupom") ? ODO_ESPERA_CUPOM : 0),
          ),
        180 + i * 90,
      );
    });
  }

  // Confete curtinho saindo da caixinha da tarefa concluida (cor do card).
  function festejar(caixa) {
    if (!caixa || reduzido() || typeof document === "undefined") return;
    const card = caixa.closest(".card-contrato");
    if (!card) return;
    const rc = card.getBoundingClientRect();
    const rb = caixa.getBoundingClientRect();
    const burst = document.createElement("span");
    burst.className = "card-confete";
    burst.setAttribute("aria-hidden", "true");
    burst.style.left = `${rb.left - rc.left + rb.width / 2}px`;
    burst.style.top = `${rb.top - rc.top + rb.height / 2}px`;
    const N = 10;
    for (let k = 0; k < N; k++) {
      const p = document.createElement("i");
      const ang = (360 / N) * k + (Math.random() * 18 - 9);
      p.style.setProperty("--ang", `${ang}deg`);
      p.style.setProperty("--dist", `${20 + Math.random() * 14}px`);
      p.style.setProperty("--giro", `${Math.random() * 220 - 110}deg`);
      if (k % 3 === 0) p.className = "risco";
      burst.appendChild(p);
    }
    card.appendChild(burst);
    if (typeof raiz.vibrar === "function") raiz.vibrar(12);
    setTimeout(() => burst.remove(), 900);
  }

  // Desfazer: o card "expira" (encolhe um tico e volta) antes de ficar apagado.
  function desfeito(cardEl) {
    if (!cardEl || reduzido()) return;
    cardEl.classList.remove("card-desfazendo");
    void cardEl.offsetWidth;
    cardEl.classList.add("card-desfazendo");
  }

  // ---- costura: quando uma resposta traz 2+ cards (voo + agua + viagem + dia...), um fio
  // de luz corre na coluna do avatar ligando um card no outro, no da cor de cada um. Na
  // resposta nova o fio se desenha card a card, conforme eles chegam, e no fim um ponto de
  // luz percorre tudo uma vez ("ta tudo ligado"). Historico: fio parado, ja desenhado.
  const COSTURA_PASSO = 90; // mesmo ritmo do --chegada de animar()

  // Parte pura (testavel): nos [{y, cor}] em px relativos ao grupo -> fios entre vizinhos.
  function geometriaCostura(nos) {
    const validos = (nos || []).filter((n) => n && Number.isFinite(n.y));
    const fios = [];
    for (let i = 0; i < validos.length - 1; i++) {
      const a = validos[i];
      const b = validos[i + 1];
      if (b.y <= a.y) continue;
      fios.push({ top: a.y, altura: b.y - a.y, de: a.cor, para: b.cor, atraso: (i + 1) * COSTURA_PASSO + 260 });
    }
    return { nos: validos, fios, total: validos.length ? validos[validos.length - 1].y - validos[0].y : 0 };
  }

  function corDoCard(card) {
    try {
      const c = raiz.getComputedStyle(card).getPropertyValue("--card-cor").trim();
      return c || "currentColor";
    } catch (e) {
      return "currentColor";
    }
  }

  // offsetTop (layout) e nao getBoundingClientRect: na chegada o card ainda esta deslocado
  // pela animacao (translateY/scale) e o no sairia torto. O grupo costurado e position:relative.
  function posicionarCostura(grupo, camada) {
    const cards = Array.from(grupo.querySelectorAll(".card-contrato")).filter((c) => c.parentElement === grupo);
    const nos = cards.map((card) => {
      const olho = card.querySelector(".card-resultado-eyebrow");
      let y = card.offsetTop + 20;
      if (olho && olho.offsetParent === card) y = card.offsetTop + olho.offsetTop + olho.offsetHeight / 2;
      return { y: Math.round(y), cor: corDoCard(card) };
    });
    const g = geometriaCostura(nos);
    const inicio = g.nos.length ? g.nos[0].y : 0;
    // a luz anda em velocidade constante; cada no pisca na hora exata em que ela passa
    const durLuz = Math.min(1600, Math.max(650, g.total * 2.2));
    camada.style.setProperty("--costura-total", `${g.total}px`);
    camada.style.setProperty("--costura-inicio", `${inicio}px`);
    camada.style.setProperty("--costura-luz-dur", `${Math.round(durLuz)}ms`);
    if (g.nos.length) camada.style.setProperty("--primeira-cor", g.nos[0].cor);
    const pulso = (n) => Math.round(g.total ? ((n.y - inicio) / g.total) * durLuz : 0);
    const fios = camada.querySelectorAll(".costura-fio");
    const pontos = camada.querySelectorAll(".costura-no");
    if (fios.length === g.fios.length && pontos.length === g.nos.length) {
      // so reposiciona: recriar os elementos reiniciaria a animacao no meio
      g.fios.forEach((f, i) => {
        fios[i].style.top = `${f.top}px`;
        fios[i].style.height = `${f.altura}px`;
      });
      g.nos.forEach((n, i) => {
        pontos[i].style.top = `${n.y}px`;
      });
      return;
    }
    camada.innerHTML =
      g.fios
        .map((f) => `<i class="costura-fio" style="top:${f.top}px;height:${f.altura}px;--de:${f.de};--para:${f.para};--costura-atraso:${f.atraso}ms"></i>`)
        .join("") +
      g.nos
        .map((n, i) => `<b class="costura-no" style="top:${n.y}px;--no-cor:${n.cor};--costura-atraso:${i * COSTURA_PASSO + 200}ms;--pulso:${pulso(n)}ms"></b>`)
        .join("") +
      `<span class="costura-luz"></span>`;
  }

  // chat.js chama pra TODO grupo (historico tambem); `nova` = resposta que acabou de chegar.
  function costurar(grupo, opcoes) {
    if (!grupo || !grupo.querySelectorAll || typeof document === "undefined") return;
    const cards = Array.from(grupo.querySelectorAll(".card-contrato")).filter((c) => c.parentElement === grupo);
    if (cards.length < 2 || grupo.querySelector(":scope > .costura")) return;
    const camada = document.createElement("div");
    camada.className = "costura";
    camada.setAttribute("aria-hidden", "true");
    if (opcoes && opcoes.nova && !reduzido()) {
      camada.classList.add("costura-nova");
      camada.style.setProperty("--costura-luz-atraso", `${cards.length * COSTURA_PASSO + 900}ms`);
    }
    grupo.classList.add("cards-costurados");
    grupo.appendChild(camada);
    const refazer = () => {
      try {
        posicionarCostura(grupo, camada);
      } catch (e) {
        /* sem layout (aba escondida): fica pro proximo resize */
      }
    };
    refazer();
    // cards vivos crescem/encolhem (lista expande, aba volta a aparecer): o fio acompanha
    if (typeof raiz.ResizeObserver === "function") {
      let quadro = 0;
      const ro = new raiz.ResizeObserver(() => {
        if (quadro) return;
        quadro = raiz.requestAnimationFrame(() => {
          quadro = 0;
          refazer();
        });
      });
      ro.observe(grupo);
      cards.forEach((c) => ro.observe(c));
    }
  }

  // ---- toque que responde (todos os cards, historico tambem) -----------------------
  //  - segurar afunda o card um tico (a inclinacao 3D e a luz que seguia o dedo sairam em
  //    04/11/2026: cara de IA);
  //  - card com .card-expande: tocar em qualquer lugar dele abre/fecha o detalhe;
  //  - tarefa pendente dentro do card: arrastar pra direita conclui (mesma caixinha de
  //    sempre por baixo - o change dela e quem fala com o servidor, em cards.js).
  const ARRASTO_LIMIAR = 72; // px pra direita que concluem a tarefa
  const ARRASTO_ELASTICO = 90; // daqui pra frente a linha resiste
  const SEGURAR_MS = 140;
  const INTERATIVO = "a, button, input, label, select, textarea, summary, [data-acao]";

  // Parte pura: dedo andou `mx` px pra direita -> quanto a linha anda e o progresso (0-1).
  function arrasto(mx) {
    const m = Math.max(0, Number(mx) || 0);
    const dx = m <= ARRASTO_ELASTICO ? m : ARRASTO_ELASTICO + (m - ARRASTO_ELASTICO) * 0.35;
    return { dx: +Math.min(140, dx).toFixed(1), p: +Math.min(1, dx / ARRASTO_LIMIAR).toFixed(3), conclui: dx >= ARRASTO_LIMIAR };
  }

  function endireitar(card) {
    if (!card) return;
    card.classList.remove("card-apertado");
  }

  function alternarDetalhe(card) {
    if (!card || !card.querySelector(".card-expande")) return;
    const aberto = card.classList.toggle("card-aberto");
    card.querySelectorAll('[data-acao="expandir"]').forEach((b) => {
      b.setAttribute("aria-expanded", String(aberto));
      const rot = b.querySelector("span");
      if (rot) rot.textContent = aberto ? "Fechar" : b.dataset.rotulo || "Ver mais";
    });
  }

  function linhaArrastavel(alvo) {
    const li = alvo && alvo.closest ? alvo.closest("li.card-tarefa") : null;
    const caixa = li && li.querySelector("input[data-tarefa-id]");
    return caixa && !caixa.checked && !caixa.disabled ? li : null;
  }

  function ligarToque(container) {
    if (!container || container.dataset.toqueLigado || typeof document === "undefined") return;
    container.dataset.toqueLigado = "1";
    let st = null; // dedo/botao pressionado agora
    let engolirClique = false;

    const cardDe = (alvo) => {
      const c = alvo && alvo.closest ? alvo.closest(".card-contrato") : null;
      return c && container.contains(c) && !c.classList.contains("card-contrato-fallback") ? c : null;
    };

    container.addEventListener("pointerdown", (e) => {
      const card = cardDe(e.target);
      if (!card || (e.pointerType === "mouse" && e.button !== 0)) return;
      const dedo = e.pointerType !== "mouse";
      st = { card, id: e.pointerId, x0: e.clientX, y0: e.clientY, eixo: null, linha: linhaArrastavel(e.target), mov: null, dedo };
      // segurar (sem rolar) afunda o card um tico
      if (!st.linha && !e.target.closest(INTERATIVO) && !e.target.closest(".vivo-d")) {
        st.segura = setTimeout(() => card.classList.add("card-apertado"), SEGURAR_MS);
      }
    });

    container.addEventListener("pointermove", (e) => {
      if (st && e.pointerId === st.id) {
        const mx = e.clientX - st.x0;
        const my = e.clientY - st.y0;
        if (!st.eixo && Math.hypot(mx, my) > 6) {
          st.eixo = Math.abs(mx) > Math.abs(my) ? "x" : "y";
          clearTimeout(st.segura);
          st.card.classList.remove("card-apertado");
          if (st.eixo === "x" && st.linha && mx > 0) {
            st.linha.classList.add("arrastando");
            try {
              st.linha.setPointerCapture(e.pointerId);
            } catch (err) {
              /* ponteiro ja solto */
            }
          } else {
            st.linha = null;
          }
        }
        if (st.linha && st.eixo === "x") {
          st.mov = arrasto(mx);
          st.linha.style.setProperty("--arrasto", `${st.mov.dx}px`);
          st.linha.style.setProperty("--arrasto-p", String(st.mov.p));
          st.linha.classList.toggle("vai-concluir", st.mov.conclui);
          return;
        }
      }
    });

    const soltar = (e, cancelou) => {
      if (!st || e.pointerId !== st.id) return;
      const { card, linha, mov } = st;
      clearTimeout(st.segura);
      st = null;
      if (linha) {
        linha.classList.remove("arrastando", "vai-concluir");
        linha.style.setProperty("--arrasto", "0px");
        linha.style.setProperty("--arrasto-p", "0");
        if (mov) {
          // o clique que o navegador solta depois do arrasto nao pode marcar/desmarcar a caixinha
          engolirClique = true;
          setTimeout(() => (engolirClique = false), 400);
        }
        if (mov && mov.conclui && !cancelou) {
          const caixa = linha.querySelector("input[data-tarefa-id]");
          if (caixa && !caixa.checked && !caixa.disabled) {
            caixa.checked = true;
            caixa.dispatchEvent(new Event("change", { bubbles: true }));
          }
        }
      }
      endireitar(card);
    };
    container.addEventListener("pointerup", (e) => soltar(e, false));
    container.addEventListener("pointercancel", (e) => soltar(e, true));

    container.addEventListener(
      "click",
      (e) => {
        if (!engolirClique) return;
        engolirClique = false;
        e.preventDefault();
        e.stopPropagation();
      },
      true
    );
    // tocar no corpo do card abre/fecha o detalhe (botoes, links e caixinhas fazem o deles)
    container.addEventListener("click", (e) => {
      if (e.target.closest(INTERATIVO)) return;
      const card = cardDe(e.target);
      if (card) alternarDetalhe(card);
    });
  }

  if (raiz.Cards && typeof raiz.Cards.registrarAcao === "function") {
    raiz.Cards.registrarAcao("expandir", (btn, cardEl) => alternarDetalhe(cardEl));
  }

  const CardsPremium = {
    animar,
    odometro,
    festejar,
    desfeito,
    costurar,
    geometriaCostura,
    ligarToque,
    arrasto,
    alternarDetalhe,
  };
  raiz.CardsPremium = CardsPremium;
  if (typeof module !== "undefined" && module.exports) module.exports = CardsPremium;
})(typeof window !== "undefined" ? window : globalThis);
