// static/js/nucleo/ui.js - Nucleo compartilhado: helpers de interface (setBotaoCarregando, pulsarSucesso, animarNumero, explodirConcluido, initDicas).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 297-307, app.js 367-373, app.js 650-697, app.js 4057-4110.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

function setBotaoCarregando(btn, carregando, rotulo) {
  if (carregando) {
    if (btn.dataset.htmlOriginal === undefined) btn.dataset.htmlOriginal = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span>${rotulo}`;
  } else {
    btn.disabled = false;
    btn.innerHTML = btn.dataset.htmlOriginal !== undefined ? btn.dataset.htmlOriginal : rotulo;
  }
}

function pulsarSucesso(el) {
  el.classList.remove("sucesso");
  // forca reflow pra animacao reiniciar mesmo em capturas seguidas
  void el.offsetWidth;
  el.classList.add("sucesso");
}

function animarNumero(el, valorFinal, formatador) {
  el.classList.remove("shimmer");
  // Vis (C2): "reduzir movimento" tem que mostrar o valor final direto, sem
  // contar (skill animacoes-interface) - antes esta funcao sempre contava,
  // mesmo com o sistema preferindo menos movimento. Duracao vem do token
  // --dur-contagem (700ms, tokens.css) quando disponivel, com o 420ms antigo
  // como fallback (getComputedStyle pode nao existir num teste sem DOM real).
  if (typeof reduzirMovimento === "function" && reduzirMovimento()) {
    el.textContent = formatador ? formatador(valorFinal) : Math.round(valorFinal);
    return;
  }
  let duracao = 420;
  try {
    const token = getComputedStyle(document.documentElement).getPropertyValue("--dur-contagem").trim();
    const ms = parseFloat(token);
    if (ms > 0) duracao = ms;
  } catch (erro) {
    /* sem getComputedStyle (ambiente de teste) - segue com o fallback */
  }
  const inicio = performance.now();
  function passo(agora) {
    const progresso = Math.min(1, (agora - inicio) / duracao);
    const suavizado = 1 - Math.pow(1 - progresso, 3);
    const valorAtual = valorFinal * suavizado;
    el.textContent = formatador ? formatador(valorAtual) : Math.round(valorAtual);
    if (progresso < 1) {
      requestAnimationFrame(passo);
    } else {
      el.classList.remove("num-pop");
      void el.offsetWidth;
      el.classList.add("num-pop");
    }
  }
  requestAnimationFrame(passo);
}

function explodirConcluido(origemEl) {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const r = origemEl.getBoundingClientRect();
  const cx = r.left + r.width / 2;
  const cy = r.top + r.height / 2;

  const wrap = document.createElement("div");
  wrap.className = "burst-wrap";
  wrap.style.left = `${cx}px`;
  wrap.style.top = `${cy}px`;
  wrap.appendChild(document.createElement("span")).className = "burst-anel";

  const cores = ["var(--cor-financeiro)", "var(--accent)", "var(--accent-2)", "var(--cor-bancos)"];
  const total = 8;
  for (let i = 0; i < total; i++) {
    const ang = (Math.PI * 2 * i) / total + (Math.random() - 0.5) * 0.5;
    const dist = 30 + Math.random() * 18;
    const p = document.createElement("span");
    p.className = "burst-particula";
    p.style.setProperty("--tx", `${Math.cos(ang) * dist}px`);
    p.style.setProperty("--ty", `${Math.sin(ang) * dist}px`);
    p.style.background = cores[i % cores.length];
    wrap.appendChild(p);
  }
  document.body.appendChild(wrap);
  setTimeout(() => wrap.remove(), 650);
}

/* Dicas colapsaveis: o paragrafo comeca escondido atras do icone "!" e, na
   primeira vez que abre, o texto "digita" progressivamente em vez de
   aparecer tudo de uma vez - reforca que e uma explicacao extra, nao
   conteudo que precisa ser lido toda vez que a secao aparece na tela. */
function initDicas() {
  const reduzMovimento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  document.querySelectorAll(".dica-colapsavel").forEach((wrapper) => {
    const btn = wrapper.querySelector(".dica-toggle");
    const texto = wrapper.querySelector(".dica-texto");
    if (!btn || !texto) return;

    const conteudoCompleto = texto.textContent.trim();
    let jaDigitou = false;
    let timerId = null;

    function digitar() {
      if (jaDigitou || reduzMovimento) {
        texto.textContent = conteudoCompleto;
        jaDigitou = true;
        return;
      }
      texto.textContent = "";
      texto.classList.add("digitando");
      let i = 0;
      const passo = () => {
        i += 1;
        texto.textContent = conteudoCompleto.slice(0, i);
        if (i < conteudoCompleto.length) {
          timerId = setTimeout(passo, 14);
        } else {
          texto.classList.remove("digitando");
          jaDigitou = true;
        }
      };
      passo();
    }

    btn.addEventListener("click", () => {
      const aberto = btn.getAttribute("aria-expanded") === "true";
      if (aberto) {
        btn.setAttribute("aria-expanded", "false");
        texto.hidden = true;
        clearTimeout(timerId);
        texto.classList.remove("digitando");
        return;
      }
      btn.setAttribute("aria-expanded", "true");
      texto.hidden = false;
      digitar();
    });
  });
}
