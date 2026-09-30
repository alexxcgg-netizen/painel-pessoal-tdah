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

// Vel: getComputedStyle forca o navegador a fechar qualquer recalc de
// estilo pendente antes de responder - caro no caminho quente da troca de
// aba (Financas chama animarNumero 3x por abertura: frase, fatura, conta).
// Le o token --dur-contagem uma unica vez por carregamento de pagina em vez
// de a cada chamada (o valor nao muda depois que a pagina carrega).
let _c2DuracaoContagemCache = null;
function _obterDuracaoContagem() {
  if (_c2DuracaoContagemCache !== null) return _c2DuracaoContagemCache;
  let duracao = 420;
  try {
    const token = getComputedStyle(document.documentElement).getPropertyValue("--dur-contagem").trim();
    const ms = parseFloat(token);
    if (ms > 0) duracao = ms;
  } catch (erro) {
    /* sem getComputedStyle (ambiente de teste) - segue com o fallback */
  }
  _c2DuracaoContagemCache = duracao;
  return duracao;
}

function animarNumero(el, valorFinal, formatador) {
  el.classList.remove("shimmer");
  const escrever = (v) => {
    el.textContent = formatador ? formatador(v) : Math.round(v);
  };
  // uma contagem por elemento: nova chamada cancela a anterior (sem duas
  // competindo pelo mesmo texto)
  if (el._c2Contagem) el._c2Contagem();
  // Vis (C2): "reduzir movimento" tem que mostrar o valor final direto, sem
  // contar (skill animacoes-interface). Duracao vem do token --dur-contagem.
  if (typeof reduzirMovimento === "function" && reduzirMovimento()) {
    escrever(valorFinal);
    return;
  }
  const duracao = _obterDuracaoContagem();
  const inicio = performance.now();
  let acabou = false;
  let timer = null;
  const cancelar = () => {
    acabou = true;
    clearTimeout(timer);
    document.removeEventListener("visibilitychange", aoVoltar);
    if (el._c2Contagem === cancelar) el._c2Contagem = null;
  };
  // Sempre termina no valor final: rAF pausa com o app em 2o plano no iOS;
  // o timeout e o visibilitychange escrevem o valor certo mesmo assim.
  const terminar = () => {
    if (acabou) return;
    cancelar();
    escrever(valorFinal);
    el.classList.remove("num-pop");
    void el.offsetWidth;
    el.classList.add("num-pop");
  };
  function aoVoltar() {
    if (!document.hidden && performance.now() - inicio >= duracao) terminar();
  }
  function passo(agora) {
    if (acabou) return;
    const progresso = Math.min(1, (agora - inicio) / duracao);
    if (progresso >= 1) {
      terminar();
      return;
    }
    const suavizado = 1 - Math.pow(1 - progresso, 3);
    escrever(valorFinal * suavizado);
    requestAnimationFrame(passo);
  }
  el._c2Contagem = cancelar;
  document.addEventListener("visibilitychange", aoVoltar);
  timer = setTimeout(terminar, duracao + 150);
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
