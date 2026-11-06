// static/js/secoes/tarefas/tarefas.js - Secao tarefas > tarefas (HTML: templates/secoes/tarefas/tarefas.html).
// Fase 7 (X2): extraido do antigo app.js. Fase 7 (V3): "Nova tarefa" abre o formulario num bottom-sheet.
// Leva 06/11 (frente 6, docs/briefings/2026-11-06-painel-esperto.md): a lista vira grupos (Atrasadas /
// Manha / Tarde / Noite / Sem hora / Amanha / proximos dias / Sem data) em linhas estilo Ajustes do
// iPhone - caixinha redonda que marca feito sem abrir nada, titulo, linha cinza de baixo e a hora em
// mono a direita. Tocar na linha abre a folha de acoes (folha-tarefa.js); a regua do dia e o texto
// vivo ("em 40 min") moram em linha-do-tempo-tarefas.js; deslizar pra apagar em arrastar-excluir.js.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

function abrirPainelTarefa() {
  const sheet = $("#tarefa-sheet");
  if (typeof window.abrirBottomSheet === "function") window.abrirBottomSheet(sheet);
  else sheet.hidden = false;
}

function fecharPainelTarefa() {
  const sheet = $("#tarefa-sheet");
  if (typeof window.fecharBottomSheet === "function") window.fecharBottomSheet(sheet);
  else sheet.hidden = true;
}

$("#tarefa-abrir-btn").addEventListener("click", abrirPainelTarefa);
$("#tarefa-cancelar-btn").addEventListener("click", () => {
  $("#nova-tarefa-form").reset();
  fecharPainelTarefa();
});

// ---- Sugestao por energia (Fase 5, US-C7) -------------------------------
async function carregarSugestaoEnergia(nivel) {
  const tasks = await apiFetch(`/api/tarefas/sugestao-energia?nivel=${nivel}`);
  if (!tasks) return;

  const list = $("#lista-sugestao-energia");
  list.innerHTML = "";
  $("#sugestao-energia-vazio").hidden = tasks.length > 0;
  tasks.forEach((t) => list.appendChild(criarItemTarefa(t)));
  atualizarLinhasTarefas(list);
}

$("#energia-botoes")
  .querySelectorAll("button")
  .forEach((btn) => {
    btn.addEventListener("click", () => {
      // Vel A2b: otimista - o chip ativo troca na hora do toque; a lista de
      // sugestoes (que depende da rede) chega depois.
      $("#energia-botoes")
        .querySelectorAll("button")
        .forEach((b) => {
          const ativo = b === btn;
          b.classList.toggle("primario", ativo);
          b.classList.toggle("chip--ativo", ativo); // C2: chip do contrato
          b.setAttribute("aria-pressed", ativo ? "true" : "false");
        });
      carregarSugestaoEnergia(btn.dataset.nivel);
    });
  });

const NIVEIS_ENERGIA = ["baixa", "media", "alta"];

// check da caixinha: o traco se desenha (stroke-dashoffset) quando a linha ganha .feito
const ICONE_CHECK_CAIXA =
  '<svg viewBox="0 0 24 24" fill="none" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7"/></svg>';

function _menosMovimentoTarefas() {
  return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// Uma linha da lista. Os handlers leem li._tarefa (nao o `t` do fechamento): a linha e reaproveitada
// entre montagens e a tarefa pode ter mudado (hora, titulo) sem recriar o <li>.
function criarItemTarefa(t) {
  const li = document.createElement("li");
  li.className = "tt-item";
  // data-entidade/data-id: o link "Abrir Tarefas" de um card (static/js/cards.js) rola ate o item
  li.dataset.entidade = "tarefa";
  li.dataset.id = t.id;
  li._tarefa = t;

  const caixa = document.createElement("button");
  caixa.type = "button";
  caixa.className = "tt-caixa";
  caixa.innerHTML = ICONE_CHECK_CAIXA;

  const abrir = document.createElement("button");
  abrir.type = "button";
  abrir.className = "tt-abrir";
  abrir.setAttribute("aria-haspopup", "dialog");
  abrir.innerHTML = '<span class="tt-textos"><b class="tt-titulo"></b><span class="tt-meta"></span></span><span class="tt-hora"></span>';

  li.appendChild(caixa);
  li.appendChild(abrir);

  caixa.addEventListener("click", (e) => {
    e.stopPropagation();
    concluirTarefaDaLista(li, li._tarefa, caixa, [caixa]);
  });
  abrir.addEventListener("click", () => {
    if (li.classList.contains("saindo")) return;
    if (typeof abrirFolhaTarefa === "function") abrirFolhaTarefa(li._tarefa, li);
  });

  preencherItemTarefa(li, t, new Date(), typeof chuvaDeHoje === "function" ? chuvaDeHoje() : null);
  // arrastar pra esquerda = excluir (sem concluir) - arrastar-excluir.js
  if (typeof ligarArrastarExcluir === "function") ligarArrastarExcluir(li, t);
  return li;
}

function preencherItemTarefa(li, t, agora, chuva) {
  li._tarefa = t;
  const linha = linhaDaTarefa(t, agora, chuva);
  li.querySelector(".tt-caixa").setAttribute("aria-label", `Marcar ${t.title} como feita`);
  const titulo = li.querySelector(".tt-titulo");
  if (titulo.textContent !== t.title) titulo.textContent = t.title;
  const meta = li.querySelector(".tt-meta");
  meta.replaceChildren();
  linha.partes.forEach((p, i) => {
    if (i) meta.append(" · ");
    meta.append(p);
  });
  if (linha.chuva) {
    if (linha.partes.length) meta.append(" · ");
    const c = document.createElement("span");
    c.className = "tt-chuva";
    c.textContent = linha.chuva;
    meta.appendChild(c);
  }
  meta.hidden = !meta.childNodes.length;
  const hora = li.querySelector(".tt-hora");
  hora.textContent = linha.hora;
  hora.className = `tt-hora${linha.horaClasse ? ` ${linha.horaClasse}` : ""}`;
  hora.hidden = !linha.hora;
  li.classList.toggle("tt-atrasada", Boolean(t.due_date && t.due_date < tlIsoDe(agora)));
  li.querySelector(".tt-abrir").setAttribute(
    "aria-label",
    [t.title, linha.hora && `às ${linha.hora}`, ...linha.partes, linha.chuva].filter(Boolean).join(", ")
  );
}

// texto vivo ("em 40 min", "passou ha 20 min", chuva) - relogio de 30 s (linha-do-tempo-tarefas.js)
function atualizarLinhasTarefas(raiz) {
  const alvo = raiz || $("#tab-tarefas");
  if (!alvo) return;
  const agora = new Date();
  const chuva = typeof chuvaDeHoje === "function" ? chuvaDeHoje() : null;
  alvo.querySelectorAll("li.tt-item").forEach((li) => {
    if (li._tarefa && !li.classList.contains("saindo")) preencherItemTarefa(li, li._tarefa, agora, chuva);
  });
}

// Concluir pela caixinha (ou pelo Feito da folha). Vel A2b: otimista - a caixinha enche de verde, o
// check se desenha com um pulinho e o titulo risca na hora; ~420 ms depois a linha fecha o espaco e
// sai. A gravacao (POST) vai por tras; o toast traz o Desfazer (reabre). Erro: a linha volta no lugar.
async function concluirTarefaDaLista(li, t, origem, botoes) {
  if (li.classList.contains("saindo") || botoes.some((b) => b.disabled)) return; // duplo toque
  botoes.forEach((b) => (b.disabled = true));
  const pai = li.parentElement;
  const proximoIrmao = li.nextElementSibling;
  const menosMovimento = _menosMovimentoTarefas();
  vibrar(30);
  if (typeof tocarSomConcluido === "function") tocarSomConcluido();
  li.classList.add("saindo", "feito");
  t._saindo = true;
  if (typeof renderReguaTarefas === "function") renderReguaTarefas();
  const colapsarTimeout = setTimeout(() => li.classList.add("tt-some"), menosMovimento ? 0 : 420);
  let avisarRemovido;
  const removido = new Promise((ok) => (avisarRemovido = ok));
  const removerTimeout = setTimeout(
    () => {
      avisarRemovido();
      const grupo = li.closest(".tt-grupo");
      li.remove();
      if (grupo && !grupo.querySelector("li.tt-item")) grupo.hidden = true;
    },
    menosMovimento ? 260 : 760
  );

  const data = await apiFetch(`/api/tasks/${t.id}/complete`, { method: "POST" });
  if (data) {
    if (data.premio && typeof mostrarPremioLiberado === "function") mostrarPremioLiberado(data.premio);
    if (typeof mostrarDesfazer === "function") {
      mostrarDesfazer(`“${_tituloCurto(t.title)}” feita`, async () => {
        const r = await apiFetch(`/api/tasks/${t.id}/reabrir`, { method: "POST" });
        if (r) _recarregarTarefas();
        return Boolean(r);
      });
    }
    // a lista so recarrega depois que a linha saiu - senao o re-render corta o check no meio
    removido.then(() => _recarregarTarefas());
    loadSummary();
    loadStreak();
    if (!$("#tab-painel").hidden) loadFechamentoDoDia();
    // M3: concluida some da lista principal mas, se "Ver concluidas" ja
    // ta aberto, essa que acabou de ser marcada deveria aparecer nela.
    const listaConcluidas = $("#lista-tarefas-concluidas");
    if (listaConcluidas && !listaConcluidas.hidden) loadTarefasConcluidas();
    return;
  }
  clearTimeout(colapsarTimeout);
  clearTimeout(removerTimeout);
  delete t._saindo;
  li.classList.remove("saindo", "feito", "tt-some");
  botoes.forEach((b) => (b.disabled = false));
  if (pai && !pai.contains(li)) {
    if (proximoIrmao && proximoIrmao.parentElement === pai) pai.insertBefore(li, proximoIrmao);
    else pai.appendChild(li);
    const grupo = pai.closest(".tt-grupo");
    if (grupo) grupo.hidden = false;
  }
  if (typeof renderReguaTarefas === "function") renderReguaTarefas();
}

function _tituloCurto(titulo) {
  const s = String(titulo || "Tarefa");
  return s.length > 34 ? `${s.slice(0, 33).trimEnd()}…` : s;
}

// recarrega do servidor mesmo que o hash seja igual (depois de desfazer/mudar)
function _recarregarTarefas() {
  _ultimoHashTarefas = null;
  loadTasks();
  if (typeof loadSummary === "function") loadSummary();
  if (typeof loadAgenda === "function") loadAgenda();
}

// Correcao rapida "isso não e uma tarefa, e um gasto" - formulario minimo
// (o texto original pode nao ter um valor claro, entao pede o valor certo
// na hora). Mora na folha de acoes desde 06/11; `aoCorrigir` fecha a folha.
function criarFormularioTarefaParaGasto(t, aoCorrigir) {
  const form = document.createElement("div");
  form.className = "correcao-form";

  const valorInput = document.createElement("input");
  valorInput.type = "number";
  valorInput.step = "0.01";
  valorInput.min = "0.01";
  valorInput.placeholder = "valor (R$)";
  valorInput.className = "correcao-input";
  valorInput.setAttribute("aria-label", "Valor do gasto em reais");

  const categoriaSelect = document.createElement("select");
  categoriaSelect.className = "correcao-select";
  categoriaSelect.setAttribute("aria-label", "Categoria do gasto");
  CATEGORIAS_GASTO.forEach((cat) => {
    const opt = document.createElement("option");
    opt.value = cat;
    opt.textContent = cat;
    categoriaSelect.appendChild(opt);
  });

  const btnConfirmar = document.createElement("button");
  btnConfirmar.type = "button";
  btnConfirmar.className = "primario btn-com-icone";
  btnConfirmar.innerHTML = `${ICONE_CHECK}virar gasto`;
  btnConfirmar.addEventListener("click", async () => {
    const valor = parseFloat(valorInput.value);
    if (!valor || valor <= 0) {
      valorInput.focus();
      return;
    }
    setBotaoCarregando(btnConfirmar, true, "corrigindo...");
    const data = await apiFetch(`/api/tasks/${t.id}/reclassificar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ valor, categoria: categoriaSelect.value }),
    });
    if (data) {
      if (typeof aoCorrigir === "function") aoCorrigir();
      _recarregarTarefas();
      loadExpenses();
    } else {
      setBotaoCarregando(btnConfirmar, false, "virar gasto");
    }
  });

  form.appendChild(valorInput);
  form.appendChild(categoriaSelect);
  form.appendChild(btnConfirmar);
  return form;
}

// Vel A2b: hash barato do ultimo /api/tasks renderizado - troca de aba pra
// tarefas repete essa chamada toda vez, mas se os dados nao mudaram desde a
// ultima renderizacao nao vale a pena reconstruir a lista de novo.
let _ultimoHashTarefas = null;

// Lista longa (100 tarefas) so monta 10 por vez: "Ver mais" acrescenta o proximo
// lote. O que ja foi mostrado continua mostrado quando a lista recarrega.
const LOTE_INICIAL_TAREFAS = 10;
let _tarefasPendentes = [];
let _tarefasMostradas = LOTE_INICIAL_TAREFAS;

function proximoLoteTarefas(total, mostradas) {
  return Math.min(total, mostradas + LOTE_INICIAL_TAREFAS);
}

function atualizarVerMaisTarefas() {
  const btn = $("#tarefas-ver-mais");
  if (!btn) return;
  const faltam = _tarefasPendentes.length - _tarefasMostradas;
  btn.hidden = faltam <= 0;
  btn.textContent = `Ver mais (${faltam})`;
}

// id -> {li, json}: tarefa que nao mudou reaproveita o <li>; grupo -> <section>
const _itensTarefas = new Map();
const _gruposTarefas = new Map();
let _tarefasEntradaPendente = true; // 1a montagem (e ao reabrir a aba) entra em cascata

function _grupoEl(g) {
  let el = _gruposTarefas.get(g.chave);
  if (!el) {
    el = document.createElement("section");
    el.className = "tt-grupo";
    el.dataset.ttChave = `g:${g.chave}`;
    const h = document.createElement("h3");
    h.innerHTML = '<span class="tt-grupo-nome"></span><span class="tt-grupo-conta"></span>';
    const ul = document.createElement("ul");
    ul.className = "tt-lista";
    el.appendChild(h);
    el.appendChild(ul);
    _gruposTarefas.set(g.chave, el);
  }
  el.classList.toggle("alerta", Boolean(g.alerta));
  el.querySelector(".tt-grupo-nome").textContent = g.rotulo;
  return el;
}

// FLIP: mede linhas e grupos, roda `mudar()` e desliza cada um do lugar velho pro novo (quem trocou de
// grupo desliza ate o grupo novo em vez de sumir e aparecer).
function comDeslizeTarefas(raiz, mudar) {
  const animar = !_menosMovimentoTarefas() && raiz.offsetParent !== null;
  const chave = (el) => el.dataset.ttChave || (el.dataset.id ? `t:${el.dataset.id}` : null);
  const alvos = () => raiz.querySelectorAll(".tt-grupo, li.tt-item");
  const antes = new Map();
  if (animar) alvos().forEach((el) => chave(el) && antes.set(chave(el), el.getBoundingClientRect().top));
  const resultado = mudar();
  if (!animar) return resultado;
  alvos().forEach((el) => {
    const topo = antes.get(chave(el));
    if (topo === undefined || typeof el.animate !== "function") return;
    const dy = topo - el.getBoundingClientRect().top;
    if (Math.abs(dy) < 1) return;
    el.animate([{ translate: `0 ${dy}px` }, { translate: "0 0" }], { duration: 520, easing: "cubic-bezier(0.22, 1, 0.36, 1)" });
  });
  return resultado;
}

function montarListaTarefas(opcoes = {}) {
  const raiz = $("#lista-tarefas");
  const visiveis = _tarefasPendentes.slice(0, _tarefasMostradas);
  const hoje = new Date();
  const chuva = typeof chuvaDeHoje === "function" ? chuvaDeHoje() : null;
  const contagem = new Map();
  _tarefasPendentes.forEach((t) => {
    const k = grupoDaTarefa(t, hoje).chave;
    contagem.set(k, (contagem.get(k) || 0) + 1);
  });
  const novos = [];
  const cascata = _tarefasEntradaPendente || !raiz.querySelector("li.tt-item");
  _tarefasEntradaPendente = false;
  comDeslizeTarefas(raiz, () => {
    const grupos = [];
    const vivos = new Set();
    let atual = null;
    visiveis.forEach((t) => {
      const g = grupoDaTarefa(t, hoje);
      if (!atual || atual.chave !== g.chave) {
        atual = { chave: g.chave, el: _grupoEl(g), itens: [] };
        grupos.push(atual);
      }
      const json = JSON.stringify(t);
      const reg = _itensTarefas.get(t.id);
      let li;
      if (reg && reg.json === json && !reg.li.classList.contains("saindo")) {
        li = reg.li;
        preencherItemTarefa(li, t, hoje, chuva);
      } else {
        li = criarItemTarefa(t);
        _itensTarefas.set(t.id, { li, json });
        if (reg && opcoes.destacar && String(opcoes.destacar) === String(t.id)) novos.push(li);
      }
      vivos.add(t.id);
      atual.itens.push(li);
    });
    Array.from(_itensTarefas.keys()).forEach((id) => vivos.has(id) || _itensTarefas.delete(id));
    grupos.forEach((g) => {
      g.el.hidden = false;
      g.el.querySelector(".tt-grupo-conta").textContent = String(contagem.get(g.chave) || g.itens.length);
      g.el.querySelector(".tt-lista").replaceChildren(...g.itens);
    });
    raiz.replaceChildren(...grupos.map((g) => g.el));
  });
  atualizarVerMaisTarefas();
  if (typeof atualizarAgoraTarefas === "function") atualizarAgoraTarefas();
  if (_menosMovimentoTarefas()) return;
  if (cascata) {
    Array.from(raiz.children)
      .slice(0, 8)
      .forEach((el, i) => {
        el.classList.remove("tt-entra");
        el.style.setProperty("--tt-i", i);
        void el.offsetWidth;
        el.classList.add("tt-entra");
        setTimeout(() => el.classList.remove("tt-entra"), 700 + i * 50);
      });
  }
  novos.forEach((li) => {
    li.classList.remove("tt-chegando");
    void li.offsetWidth;
    li.classList.add("tt-chegando");
    setTimeout(() => li.classList.remove("tt-chegando"), 1300);
  });
}

// Mudanca local (otimista) de uma tarefa: troca os campos, reordena como o servidor ordena (dia, sem
// dia no fim; dentro do dia por hora, sem hora fecha o dia) e remonta com deslize.
function _ordemTarefa(a, b) {
  const da = a.due_date || "￿";
  const dbb = b.due_date || "￿";
  if (da !== dbb) return da < dbb ? -1 : 1;
  const ha = a.hora || "￿";
  const hb = b.hora || "￿";
  if (ha !== hb) return ha < hb ? -1 : 1;
  return 0;
}

function aplicarMudancaTarefa(id, campos) {
  const i = _tarefasPendentes.findIndex((t) => String(t.id) === String(id));
  if (i === -1) return null;
  const antes = _tarefasPendentes[i];
  const depois = { ...antes, ...campos };
  const lista = _tarefasPendentes.slice();
  lista[i] = depois;
  // sort estavel: quem empata fica na ordem de antes (a do servidor)
  _tarefasPendentes = lista.map((t, k) => [t, k]).sort((x, y) => _ordemTarefa(x[0], y[0]) || x[1] - y[1]).map((x) => x[0]);
  const pos = _tarefasPendentes.indexOf(depois);
  if (pos >= _tarefasMostradas) _tarefasMostradas = proximoLoteTarefas(_tarefasPendentes.length, pos);
  _ultimoHashTarefas = null;
  montarListaTarefas({ destacar: id });
  return antes;
}

async function loadTasks() {
  const tasks = await apiFetch("/api/tasks");
  if (!tasks) return;
  const hash = calcularHashTarefas(tasks);
  if (hash === _ultimoHashTarefas) return; // dados iguais - nao reconstroi a lista
  _ultimoHashTarefas = hash;
  $("#tarefas-vazio").hidden = tasks.length > 0;
  _tarefasPendentes = tasks;
  montarListaTarefas();
}

$("#tarefas-ver-mais").addEventListener("click", () => {
  _tarefasMostradas = proximoLoteTarefas(_tarefasPendentes.length, _tarefasMostradas);
  montarListaTarefas();
});

// Toque numa notificacao de tarefa (?aba=tarefas&tarefa=ID, nucleo/init.js): espera a lista
// chegar, rola ate a tarefa, acende a linha e abre a folha (o Waze esta la, um toque).
// Tarefa que ja saiu (concluida em outro lugar) = so fica na aba.
function focarTarefaDoAviso(id, tentativas = 30) {
  const li = document.querySelector(`#lista-tarefas li.tt-item[data-id="${CSS.escape(String(id))}"]`);
  if (!li) {
    if (tentativas > 0) setTimeout(() => focarTarefaDoAviso(id, tentativas - 1), 100);
    return;
  }
  const menos = _menosMovimentoTarefas();
  li.scrollIntoView({ block: "center", behavior: menos ? "auto" : "smooth" });
  if (!menos) {
    li.classList.remove("tt-chegando");
    void li.offsetWidth;
    li.classList.add("tt-chegando");
    setTimeout(() => li.classList.remove("tt-chegando"), 1300);
  }
  if (typeof abrirFolhaTarefa === "function") setTimeout(() => abrirFolhaTarefa(li._tarefa, li), menos ? 0 : 350);
}

// ---- "Ver concluidas" (M3, uso diario) ----------------------------------
// Concluida some da lista principal (filtro no /api/tasks padrao), mas NUNCA
// e apagada - aqui da pra ver de novo e desmarcar (POST /api/tasks/:id/reabrir).
// Busca preguicosa: so bate a API quando o dono toca no botao.
function rotuloToggleConcluidas(mostrando) {
  return mostrando ? "Esconder concluídas" : "Ver concluídas";
}

function criarItemTarefaConcluida(t) {
  const li = document.createElement("li");
  li.className = "item lista-item item-concluida";
  li.dataset.entidade = "tarefa";
  li.dataset.id = t.id;

  const linha = document.createElement("div");
  linha.className = "item-linha";

  const tituloWrap = document.createElement("div");
  const titulo = document.createElement("span");
  titulo.className = "item-titulo";
  titulo.textContent = t.title;
  tituloWrap.appendChild(titulo);

  if (t.completed_at) {
    const quando = document.createElement("span");
    quando.className = "item-quando chip chip--compacto";
    quando.textContent = `concluída ${fmtDataBr(t.completed_at.slice(0, 10))}`;
    tituloWrap.appendChild(quando);
  }

  const acoes = document.createElement("div");
  acoes.className = "item-acoes";

  const btnDesmarcar = document.createElement("button");
  btnDesmarcar.className = "btn-com-icone";
  btnDesmarcar.textContent = "desmarcar";
  btnDesmarcar.title = "voltar essa tarefa pra pendente";
  btnDesmarcar.addEventListener("click", async () => {
    setBotaoCarregando(btnDesmarcar, true, "desmarcando...");
    const data = await apiFetch(`/api/tasks/${t.id}/reabrir`, { method: "POST" });
    if (data) {
      loadTasks();
      loadTarefasConcluidas();
    } else {
      setBotaoCarregando(btnDesmarcar, false, "desmarcar");
    }
  });
  acoes.appendChild(btnDesmarcar);

  linha.appendChild(tituloWrap);
  linha.appendChild(acoes);
  li.appendChild(linha);
  return li;
}

async function loadTarefasConcluidas() {
  const tasks = await apiFetch("/api/tasks?estado=concluidas");
  if (!tasks) return;
  const list = $("#lista-tarefas-concluidas");
  list.innerHTML = "";
  $("#tarefas-concluidas-vazio").hidden = tasks.length > 0;
  tasks.forEach((t) => list.appendChild(criarItemTarefaConcluida(t)));
}

$("#tarefas-concluidas-toggle").addEventListener("click", async () => {
  const btn = $("#tarefas-concluidas-toggle");
  const list = $("#lista-tarefas-concluidas");
  const vaiMostrar = list.hidden;
  if (vaiMostrar) {
    await loadTarefasConcluidas(); // so busca aqui - nunca no carregamento normal da aba
  } else {
    $("#tarefas-concluidas-vazio").hidden = true;
  }
  list.hidden = !vaiMostrar;
  btn.textContent = rotuloToggleConcluidas(vaiMostrar);
  btn.setAttribute("aria-expanded", vaiMostrar ? "true" : "false");
});

// Vel (A2d): item provisorio pro formulario direto - titulo real + "salvando" (spinner), com a
// marca .item-otimista (borda tracejada/opacidade) ate o servidor confirmar. Entra num grupo
// proprio no topo da lista.
function criarItemTarefaOtimista(titulo, prazoDate) {
  const grupo = document.createElement("section");
  grupo.className = "tt-grupo tt-grupo-otimista";
  const ul = document.createElement("ul");
  ul.className = "tt-lista";
  const li = document.createElement("li");
  li.className = "tt-item item-otimista";
  const caixa = document.createElement("span");
  caixa.className = "tt-caixa";
  caixa.setAttribute("aria-hidden", "true");
  const textos = document.createElement("span");
  textos.className = "tt-textos";
  const tituloEl = document.createElement("b");
  tituloEl.className = "tt-titulo";
  tituloEl.textContent = titulo;
  const meta = document.createElement("span");
  meta.className = "tt-meta";
  meta.innerHTML = '<span class="spinner"></span> ';
  meta.append(prazoDate ? `salvando · ${formatarPrazoTarefa(prazoDate)}` : "salvando");
  textos.appendChild(tituloEl);
  textos.appendChild(meta);
  li.appendChild(caixa);
  li.appendChild(textos);
  ul.appendChild(li);
  grupo.appendChild(ul);
  return grupo;
}

// Fase 6 (US-F10): formulario direto na aba Tarefas - titulo obrigatorio,
// prazo OPCIONAL (POST /api/tasks, sem passar pela IA).
$("#nova-tarefa-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#nova-tarefa-btn");
  const tituloInput = $("#nova-tarefa-titulo");
  const prazoInput = $("#nova-tarefa-prazo");
  const titulo = tituloInput.value.trim();
  if (!titulo) {
    mostrarErro("Escreve o que precisa ser feito.");
    return;
  }
  const prazo = prazoInput.value || null;

  // Vel (A2d): otimista - a tarefa aparece na lista na hora do toque (estado
  // "salvando"), confirma com os dados reais quando o POST volta; em erro
  // sai da lista e devolve o texto pro campo (mostrarErro ja vem do apiFetch).
  const list = $("#lista-tarefas");
  const grupoOtimista = criarItemTarefaOtimista(titulo, prazo);
  if (list) {
    list.insertBefore(grupoOtimista, list.firstChild);
    $("#tarefas-vazio").hidden = true;
  }
  tituloInput.value = "";
  prazoInput.value = "";

  setBotaoCarregando(btn, true, "salvando...");
  const data = await apiFetch("/api/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ titulo, due_date: prazo }),
  });
  setBotaoCarregando(btn, false, "Salvar tarefa");
  grupoOtimista.remove();
  if (!data) {
    tituloInput.value = titulo;
    if (prazo) prazoInput.value = prazo;
    if (list && !list.querySelector("li.tt-item")) $("#tarefas-vazio").hidden = false;
    return;
  }

  pulsarSucesso(tituloInput);
  fecharPainelTarefa();
  loadTasks();
});

// Vel A2b: extraido pra teste puro (node --test) - mesma logica usada em
// loadTasks() pra decidir se reconstroi a lista (nao muda comportamento).
function calcularHashTarefas(tasks) {
  return JSON.stringify(tasks);
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { calcularHashTarefas, proximoLoteTarefas, NIVEIS_ENERGIA };
}
