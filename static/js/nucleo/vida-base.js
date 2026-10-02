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
      removerLiAnimado(li);
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

// R4: "marcar como feito hoje" de remedio (Tomei) e treino (Feito hoje) - mesmo comportamento do
// check de habito: otimista (muda na hora, volta se a gravacao falhar), traco + pulso do
// animarCheck, "Desfazer" no estado feito. Um toque so por vez (ocupado) e o Desfazer ignora
// toque colado no de marcar (duplo toque nunca marca e desmarca). A API (marcar/desfazer)
// devolve o objeto da resposta ou null em erro (apiFetch ja mostra o aviso).
function horaLocalAgora() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function criarCheckDia(opcoes) {
  // opcoes: {rotuloMarcar, textoFeito(hora), nome, feito, hora, marcar(), desfazer(), aoMudar(feito), depois(ok)}
  const raiz = criarEl("div", "check-dia");
  const botao = criarEl("button", "btn btn-primario btn-com-icone check-dia-marcar");
  botao.type = "button";
  botao.innerHTML = `${ICONE_CHECK}${opcoes.rotuloMarcar}`;
  botao.setAttribute("aria-label", `${opcoes.rotuloMarcar}: ${opcoes.nome}`);
  const feitoBox = criarEl("div", "check-dia-feito");
  const selo = criarEl("span", "check-dia-selo");
  selo.setAttribute("aria-hidden", "true");
  selo.innerHTML = ICONE_CHECK;
  const texto = criarEl("span", "check-dia-texto");
  texto.setAttribute("role", "status");
  const desfazer = criarEl("button", "check-dia-desfazer", "Desfazer");
  desfazer.type = "button";
  desfazer.setAttribute("aria-label", `Desfazer: ${opcoes.nome}`);
  feitoBox.append(selo, texto, desfazer);
  raiz.append(botao, feitoBox);

  let feito = Boolean(opcoes.feito);
  let hora = opcoes.hora || null;
  let ocupado = false;
  let marcouEm = 0;

  const desenhar = (mudou = true) => {
    raiz.dataset.estado = feito ? "feito" : "pendente";
    botao.hidden = feito;
    feitoBox.hidden = !feito;
    texto.textContent = opcoes.textoFeito(hora);
    if (mudou && opcoes.aoMudar) opcoes.aoMudar(feito);
  };

  botao.addEventListener("click", async () => {
    if (ocupado || feito) return;
    ocupado = true;
    marcouEm = Date.now();
    feito = true;
    hora = horaLocalAgora();
    desenhar();
    animarCheck(selo);
    const r = await opcoes.marcar();
    ocupado = false;
    if (!r) {
      feito = false;
      hora = null;
      desenhar();
    } else if (r.hora) {
      hora = r.hora;
      desenhar(false);
    }
    if (opcoes.depois) opcoes.depois(Boolean(r));
  });

  desfazer.addEventListener("click", async () => {
    if (ocupado || !feito || Date.now() - marcouEm < 600) return;
    ocupado = true;
    const horaAnterior = hora;
    feito = false;
    hora = null;
    desenhar();
    const r = await opcoes.desfazer();
    ocupado = false;
    if (!r) {
      feito = true;
      hora = horaAnterior;
      desenhar();
    }
    if (opcoes.depois) opcoes.depois(Boolean(r));
  });

  desenhar(false);
  return raiz;
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
