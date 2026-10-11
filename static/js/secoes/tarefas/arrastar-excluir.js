// static/js/secoes/tarefas/arrastar-excluir.js - arrastar a tarefa pra esquerda pra excluir
// (2026-10-11, pedido do Alex: excluir SEM marcar como concluida). Igual ao Mail do iPhone:
// arrasta e aparece "Excluir" vermelho; soltar no meio deixa o botao aberto; arrastar ate o
// fim exclui direto. Sem "tem certeza?": some na hora e o toast "Desfazer" fica 5 s embaixo
// (POST /api/desfazer/<token>, o mesmo dos cards). Dia de rotina = pula so hoje.
// Script classico (escopo global) - carregado depois de tarefas.js (templates/scripts.html).

const ARRASTO_BOTAO_PX = 92; // largura do "Excluir" quando fica aberto
const ARRASTO_INICIO_PX = 9; // anda isso na horizontal antes de virar arrasto (senao e toque/rolagem)
const ARRASTO_ABRIR_PX = 46; // soltou depois disso: abre o botao
const ARRASTO_TOTAL_FRAC = 0.56; // soltou depois dessa fracao da largura: exclui direto
const DESFAZER_MS = 5000;

const ICONE_LIXEIRA =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 7h16M10 11v6M14 11v6"/><path d="M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12"/><path d="M9 7V4.5A1.5 1.5 0 0 1 10.5 3h3A1.5 1.5 0 0 1 15 4.5V7"/></svg>';

let _arrastoAberto = null; // {li, fechar} do item com o botao aberto (so um por vez)

function _menosMovimento() {
  return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function ligarArrastarExcluir(li, t) {
  if (!li || !t || li.classList.contains("arrastavel")) return;
  li.classList.add("arrastavel");

  // os filhos de sempre deslizam juntos (transform via --arrasto, sem embrulhar: o CSS da aba
  // usa "li.item > .item-linha"); o vermelho fica atras, ancorado a direita
  const fundo = document.createElement("div");
  fundo.className = "arrasta-fundo";
  fundo.setAttribute("aria-hidden", "true");
  const botao = document.createElement("button");
  botao.type = "button";
  botao.className = "arrasta-excluir";
  botao.tabIndex = -1;
  botao.innerHTML = `${ICONE_LIXEIRA}<span>Excluir</span>`;
  fundo.appendChild(botao);
  li.insertBefore(fundo, li.firstChild);

  let x0 = 0;
  let y0 = 0;
  let base = 0; // de onde o arrasto comeca (0 fechado, -BOTAO aberto)
  let dx = 0;
  let estado = "parado"; // parado | talvez | arrastando
  let passouDoTotal = false;
  let idPonteiro = null;

  const largura = () => li.getBoundingClientRect().width || 320;

  function pintar(x, animado) {
    li.classList.toggle("arrasta-animando", Boolean(animado) && !_menosMovimento());
    li.style.setProperty("--arrasto", `${x}px`);
    fundo.style.width = `${Math.max(0, -x)}px`;
    li.classList.toggle("arrasta-mostrando", x < -2);
  }

  function fechar() {
    pintar(0, true);
    li.classList.remove("arrasta-aberto", "arrasta-total");
    if (_arrastoAberto && _arrastoAberto.li === li) _arrastoAberto = null;
  }

  function abrir() {
    if (_arrastoAberto && _arrastoAberto.li !== li) _arrastoAberto.fechar();
    pintar(-ARRASTO_BOTAO_PX, true);
    li.classList.add("arrasta-aberto");
    li.classList.remove("arrasta-total");
    _arrastoAberto = { li, fechar };
  }

  function soltar() {
    if (estado !== "arrastando") {
      estado = "parado";
      return;
    }
    estado = "parado";
    const w = largura();
    if (dx <= -w * ARRASTO_TOTAL_FRAC) excluirTarefaArrastada(li, t, fundo);
    else if (dx <= -ARRASTO_ABRIR_PX) abrir();
    else fechar();
    // o toque que terminou um arrasto nao vira clique em botao/checkbox do item
    const engolir = (ev) => {
      ev.stopPropagation();
      ev.preventDefault();
    };
    li.addEventListener("click", engolir, { capture: true, once: true });
    setTimeout(() => li.removeEventListener("click", engolir, { capture: true }), 350);
  }

  li.addEventListener("pointerdown", (ev) => {
    if (ev.pointerType === "mouse" && ev.button !== 0) return;
    if (li.classList.contains("arrasta-saindo")) return;
    if (_arrastoAberto && _arrastoAberto.li !== li) _arrastoAberto.fechar();
    x0 = ev.clientX;
    y0 = ev.clientY;
    base = li.classList.contains("arrasta-aberto") ? -ARRASTO_BOTAO_PX : 0;
    dx = base;
    estado = "talvez";
    passouDoTotal = false;
    idPonteiro = ev.pointerId;
  });

  li.addEventListener("pointermove", (ev) => {
    if (estado === "parado" || ev.pointerId !== idPonteiro) return;
    const mx = ev.clientX - x0;
    const my = ev.clientY - y0;
    if (estado === "talvez") {
      if (Math.abs(my) > ARRASTO_INICIO_PX && Math.abs(my) > Math.abs(mx)) {
        estado = "parado"; // e rolagem da lista - deixa o navegador
        return;
      }
      if (Math.abs(mx) < ARRASTO_INICIO_PX) return;
      estado = "arrastando";
      try {
        li.setPointerCapture(ev.pointerId);
      } catch {
        /* sem captura o arrasto ainda funciona enquanto o dedo estiver em cima */
      }
    }
    // pra direita alem do fechado: resiste (elastico), nunca abre do outro lado
    let x = base + mx;
    if (x > 0) x = x * 0.18;
    dx = x;
    pintar(x, false);
    const total = x <= -largura() * ARRASTO_TOTAL_FRAC;
    if (total !== passouDoTotal) {
      passouDoTotal = total;
      li.classList.toggle("arrasta-total", total);
      if (total && typeof vibrar === "function") vibrar(12);
    }
  });

  li.addEventListener("pointerup", soltar);
  li.addEventListener("pointercancel", () => {
    if (estado === "arrastando") fechar();
    estado = "parado";
  });

  botao.addEventListener("click", (ev) => {
    ev.stopPropagation();
    excluirTarefaArrastada(li, t, fundo);
  });
}

// toque fora fecha o botao aberto
document.addEventListener(
  "pointerdown",
  (ev) => {
    if (_arrastoAberto && !_arrastoAberto.li.contains(ev.target)) _arrastoAberto.fechar();
  },
  { capture: true }
);

async function excluirTarefaArrastada(li, t, fundo) {
  if (li.classList.contains("arrasta-saindo")) return;
  li.classList.add("arrasta-saindo", "arrasta-total");
  if (_arrastoAberto && _arrastoAberto.li === li) _arrastoAberto = null;
  const suave = !_menosMovimento();
  const pai = li.parentElement;
  const proximo = li.nextElementSibling;

  // 1) o conteudo sai pela esquerda e o vermelho toma a linha toda; 2) a linha fecha a altura
  const w = li.getBoundingClientRect().width;
  li.classList.toggle("arrasta-animando", suave);
  li.style.setProperty("--arrasto", `${-w}px`);
  fundo.style.width = `${w}px`;
  const altura = li.getBoundingClientRect().height;
  li.style.height = `${altura}px`;
  setTimeout(
    () => {
      li.style.transition = suave
        ? "height 0.34s var(--ease-suave), margin 0.34s var(--ease-suave), opacity 0.3s var(--ease-suave)"
        : "none";
      li.style.height = "0px";
      li.style.marginTop = "0px";
      li.style.marginBottom = "0px";
      li.style.opacity = "0";
    },
    suave ? 200 : 0
  );
  const remover = setTimeout(() => li.remove(), suave ? 560 : 0);

  const r = await apiFetch(`/api/tasks/${encodeURIComponent(t.id)}`, { method: "DELETE" });
  if (!r) {
    // deu erro (apiFetch ja mostrou): devolve a linha no mesmo lugar
    clearTimeout(remover);
    li.removeAttribute("style");
    li.classList.remove("arrasta-saindo", "arrasta-total", "arrasta-aberto", "arrasta-mostrando", "arrasta-animando");
    fundo.style.width = "0px";
    if (pai && !pai.contains(li)) {
      if (proximo && proximo.parentElement === pai) pai.insertBefore(li, proximo);
      else pai.appendChild(li);
    }
    return;
  }
  _atualizarDepoisDeExcluir();
  const curto = String(r.titulo || t.title || "Tarefa");
  const nome = curto.length > 34 ? `${curto.slice(0, 33).trimEnd()}…` : curto;
  mostrarDesfazer(r.pulada ? `"${nome}" pulada só hoje` : `"${nome}" excluída`, r.token);
}

function _atualizarDepoisDeExcluir() {
  // depois da animacao: a lista se refaz com o que o servidor tem (contagem do "Ver mais" certa)
  setTimeout(() => {
    if (typeof _ultimoHashTarefas !== "undefined") _ultimoHashTarefas = null;
    if (typeof loadTasks === "function") loadTasks();
    if (typeof loadSummary === "function") loadSummary();
    if (typeof loadAgenda === "function") loadAgenda();
  }, 600);
}

// ---- toast "Desfazer" -------------------------------------------------------------
let _desfazerTimer = null;

function _toastDesfazer() {
  let el = document.getElementById("desfazer-toast");
  if (el) return el;
  el = document.createElement("div");
  el.id = "desfazer-toast";
  el.setAttribute("role", "status");
  el.setAttribute("aria-live", "polite");
  el.hidden = true;
  el.innerHTML =
    '<span class="desfazer-texto"></span><button type="button" class="desfazer-btn">Desfazer</button>' +
    '<span class="desfazer-tempo" aria-hidden="true"></span>';
  document.body.appendChild(el);
  return el;
}

function esconderDesfazer() {
  const el = document.getElementById("desfazer-toast");
  if (!el || el.hidden) return;
  if (_desfazerTimer) clearTimeout(_desfazerTimer);
  _desfazerTimer = null;
  el.classList.remove("visivel");
  document.body.classList.remove("desfazer-visivel");
  setTimeout(() => {
    if (!el.classList.contains("visivel")) el.hidden = true;
  }, _menosMovimento() ? 0 : 260);
}

function mostrarDesfazer(texto, token) {
  const el = _toastDesfazer();
  el.querySelector(".desfazer-texto").textContent = texto;
  const btn = el.querySelector(".desfazer-btn");
  btn.hidden = !token;
  btn.disabled = false;
  btn.onclick = async () => {
    if (!token || btn.disabled) return;
    btn.disabled = true;
    const r = await apiFetch(`/api/desfazer/${encodeURIComponent(token)}`, { method: "POST" });
    if (r) {
      el.querySelector(".desfazer-texto").textContent = "Voltou pra lista";
      btn.hidden = true;
      _atualizarDepoisDeExcluir();
      if (_desfazerTimer) clearTimeout(_desfazerTimer);
      _desfazerTimer = setTimeout(esconderDesfazer, 1400);
    } else {
      btn.disabled = false;
    }
  };
  // reinicia a barrinha de tempo
  const tempo = el.querySelector(".desfazer-tempo");
  tempo.style.animation = "none";
  void tempo.offsetWidth;
  tempo.style.animation = "";
  el.style.setProperty("--desfazer-ms", `${DESFAZER_MS}ms`);
  el.hidden = false;
  requestAnimationFrame(() => {
    el.classList.add("visivel");
    document.body.classList.add("desfazer-visivel");
  });
  if (_desfazerTimer) clearTimeout(_desfazerTimer);
  _desfazerTimer = setTimeout(esconderDesfazer, DESFAZER_MS);
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { ligarArrastarExcluir, mostrarDesfazer, esconderDesfazer };
}
