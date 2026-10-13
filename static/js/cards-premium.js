// Acabamento "premium" dos cards do chat (2026-10-13) - camada por cima do registro
// (cards.js / cards-tipos.js / cards-vivos.js), sem mexer em renderizador nenhum:
//  - card novo chega com profundidade (desfoque -> nitido) e um brilho passa pelo vidro 1x;
//  - card que REGISTROU algo ganha o selo: o icone do topo da um pulinho com uma onda;
//  - numero grande (valor do gasto, hora do lembrete, % da meta) rola feito odometro e
//    "assenta" no valor certo; a barra da meta enche do zero;
//  - tarefa concluida pelo card solta um confete curtinho na cor do card;
//  - desfazer "expira" o card (encolhe um tico e volta) em vez de so apagar seco.
// Tudo tem estado final estatico: historico abre parado, prefers-reduced-motion nao anima.
(function (raiz) {
  "use strict";

  const reduzido = () => !!(raiz.matchMedia && raiz.matchMedia("(prefers-reduced-motion: reduce)").matches);

  // tipos que REGISTRAM/mudam algo (consulta pura nao ganha selo)
  const TIPOS_REGISTRO = new Set([
    "tarefas_criadas", "transacao", "lembrete", "meta", "habito", "assinatura",
    "compra_parcelada", "refeicao", "agua", "edicao", "saude_treino",
  ]);

  // numeros que viram odometro (os cartoes vivos ja contam os deles com data-contar-*)
  const SELETOR_ODOMETRO = [
    ".card-valor-grande:not(.oculto)",
    ".card-hora-grande",
    ".card-meta-valores strong",
    ".card-contrato-meta .card-linha-meta strong",
  ].join(",");

  const ODO_DURACAO = 1050; // ms do digito mais lento
  const ODO_PASSO = 45; // atraso entre um digito e o proximo (esquerda -> direita)

  function escapar(c) {
    return c === "&" ? "&amp;" : c === "<" ? "&lt;" : c === ">" ? "&gt;" : c;
  }

  // Troca o texto por colunas de digitos que rolam ate o valor; no fim volta pro texto
  // puro (o card desfeito risca o valor, leitor de tela le normal).
  function odometro(el) {
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
        const atraso = ordem * ODO_PASSO;
        const dur = ODO_DURACAO - (digitos - 1 - ordem) * 60;
        const fita = "0123456789".repeat(2).split("").map((d) => `<i>${d}</i>`).join("");
        return `<span class="odo-dig" aria-hidden="true" style="--odo-alvo:${voltas};--odo-atraso:${atraso}ms;--odo-dur:${Math.max(500, dur)}ms"><span class="odo-fita">${fita}</span></span>`;
      })
      .join("");
    const total = (digitos - 1) * ODO_PASSO + ODO_DURACAO + 120;
    setTimeout(() => {
      el.textContent = final;
      el.removeAttribute("aria-label");
      delete el.dataset.odometro;
    }, total);
  }

  // Toca a chegada so nos cards de uma resposta NOVA (chat.js chama logo depois de anexar).
  function animar(grupo) {
    if (!grupo || !grupo.querySelectorAll || reduzido()) return;
    grupo.querySelectorAll(".card-contrato").forEach((card, i) => {
      card.classList.add("card-novo");
      card.style.setProperty("--chegada", `${i * 90}ms`);
      const tipo = card.dataset.cardType;
      const olho = card.querySelector(".card-resultado-eyebrow");
      const consulta = tipo === "meta" && olho && !/criada/i.test(olho.textContent);
      if (TIPOS_REGISTRO.has(tipo) && !consulta && !card.classList.contains("card-desfeito")) {
        card.classList.add("card-selo");
      }
      // o numero so comeca a rolar quando o card ja esta assentando
      setTimeout(() => card.querySelectorAll(SELETOR_ODOMETRO).forEach(odometro), 180 + i * 90);
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

  const CardsPremium = { animar, odometro, festejar, desfeito, costurar, geometriaCostura, TIPOS_REGISTRO };
  raiz.CardsPremium = CardsPremium;
  if (typeof module !== "undefined" && module.exports) module.exports = CardsPremium;
})(typeof window !== "undefined" ? window : globalThis);
