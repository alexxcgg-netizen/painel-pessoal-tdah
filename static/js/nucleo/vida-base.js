// static/js/nucleo/vida-base.js - Nucleo compartilhado: helpers do antigo vida.js (criarEl, botaoApagar, jsonPost, itemSimples, botaoAcao, ligarForm).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 1-29, vida.js 586-635.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

// Assistente de vida (BRIEFING.md): rotina guiada, check-in, "so o essencial",
// hiperfoco, pessoas, contas pessoais, assinaturas e "vale a pena?".
// Usa os helpers globais do app.js ($, apiFetch, fmtMoeda, fmtDataBr...).

function criarEl(tag, classe, texto) {
  const el = document.createElement(tag);
  if (classe) el.className = classe;
  if (texto != null) el.textContent = texto;
  return el;
}

function botaoApagar(url, li) {
  const btn = criarEl("button", "btn-com-icone");
  btn.innerHTML = `${ICONE_TRASH}Apagar`;
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    const ok = await apiFetch(url, { method: "DELETE" });
    if (ok) {
      li.classList.add("saindo");
      setTimeout(() => li.remove(), 250);
    } else {
      btn.disabled = false;
    }
  });
  return btn;
}

// ---- Rotina guiada (manha 7h / noite 22h) ----

function jsonPost(url, corpo) {
  return apiFetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo || {}),
  });
}

function itemSimples(titulo, subtitulos, acoes, classeExtra) {
  const li = criarEl("li", "item" + (classeExtra ? ` ${classeExtra}` : ""));
  const linha = criarEl("div", "item-linha");
  const wrap = criarEl("div");
  wrap.appendChild(criarEl("span", "item-titulo", titulo));
  subtitulos.filter(Boolean).forEach((t) => wrap.appendChild(criarEl("span", "item-quando", t)));
  linha.appendChild(wrap);
  const caixa = criarEl("div", "item-acoes");
  acoes.forEach((a) => caixa.appendChild(typeof a === "function" ? a(li) : a));
  linha.appendChild(caixa);
  li.appendChild(linha);
  return li;
}

function botaoAcao(rotulo, onClick, primario = true) {
  const b = criarEl("button", (primario ? "primario " : "") + "btn-com-icone");
  b.innerHTML = primario ? `${ICONE_CHECK}${rotulo}` : "";
  if (!primario) b.textContent = rotulo;
  b.addEventListener("click", async () => {
    b.disabled = true;
    const ok = await onClick();
    if (!ok) b.disabled = false;
  });
  return b;
}

function ligarForm(formSel, btnSel, rotulo, montarCorpo, url, depois) {
  $(formSel).addEventListener("submit", async (e) => {
    e.preventDefault();
    const corpo = montarCorpo();
    if (!corpo) return;
    const btn = $(btnSel);
    setBotaoCarregando(btn, true, "salvando...");
    const r = await jsonPost(url, corpo);
    setBotaoCarregando(btn, false, rotulo);
    if (!r) return;
    $(formSel).reset();
    pulsarSucesso($(formSel).querySelector("input, textarea"));
    depois(r);
  });
}
