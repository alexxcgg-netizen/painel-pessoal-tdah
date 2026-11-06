// static/js/secoes/tarefas/folha-tarefa.js - a folha de acoes da tarefa (leva 06/11, frente 6 de
// docs/briefings/2026-11-06-painel-esperto.md; prototipo aprovado: a `.folha` da cena Tarefas).
// Tocar numa tarefa abre a folha de baixo (componente ui/bottom-sheet.js): chips de dia (Hoje, Amanha,
// os 3 dias seguintes, "Outro dia" com o calendario nativo), chips de hora (Sem hora, +30 min, +1 h,
// "Escolher" com o relogio nativo), nome editavel (grava ao fechar), Feito e Apagar. Embaixo, o que a
// tarefa ja tinha antes (Waze, quebrar em passos, cadeado, esforco, ficha do treino, virar gasto).
// Toda acao e otimista: a lista muda na hora, o toast traz o Desfazer por 5 s e, se a rota falhar,
// volta como estava. Rotas: POST /api/tasks/<id>/mover e /titulo (rotas/tarefas_acoes.py).
// Script classico (escopo global) - carregado depois de tarefas.js e linha-do-tempo-tarefas.js.

let _folhaTarefa = null; // a tarefa aberta na folha
let _folhaLi = null; // a linha que abriu (pra "Feito"/"Apagar" animarem nela)
let _folhaNomeInicial = "";

const ICONE_NAVEGAR_FOLHA =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 11 21 3l-8 18-2-8-8-2Z"/></svg>';

function _elFolha(id) {
  return document.getElementById(id);
}

// avisa o resto do app (cards do chat escutam "tarefa:mudou"; o app do iPhone ja e avisado pelo
// proprio apiFetch em toda escrita)
function _avisarMudancaTarefa(id, extra) {
  document.dispatchEvent(new CustomEvent("tarefa:mudou", { detail: { id: String(id), concluida: false, ...extra } }));
}

function _chip(texto, extra) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "chip tt-chip";
  b.textContent = texto;
  Object.entries(extra || {}).forEach(([k, v]) => b.setAttribute(k, v));
  return b;
}

// chip que embrulha um <input type=date|time> nativo transparente por cima: o toque cai direto no
// seletor do iPhone (sem showPicker, que nem todo Safari tem)
function _chipComSeletor(texto, tipo, valor, rotuloAcessivel) {
  const label = document.createElement("label");
  label.className = "chip tt-chip tt-chip-seletor";
  const span = document.createElement("span");
  span.textContent = texto;
  const input = document.createElement("input");
  input.type = tipo;
  input.value = valor || "";
  input.setAttribute("aria-label", rotuloAcessivel);
  if (tipo === "time") input.step = "300";
  label.appendChild(span);
  label.appendChild(input);
  return { label, input };
}

function abrirFolhaTarefa(t, li) {
  if (!t) return;
  _folhaTarefa = t;
  _folhaLi = li || null;
  _preencherFolha(t);
  const folha = _elFolha("tarefa-folha");
  if (typeof window.abrirBottomSheet === "function") window.abrirBottomSheet(folha);
  else folha.hidden = false;
}

function fecharFolhaTarefa() {
  const folha = _elFolha("tarefa-folha");
  if (typeof window.fecharBottomSheet === "function") window.fecharBottomSheet(folha);
  else {
    folha.hidden = true;
    _aoFecharFolha();
  }
}

function _preencherFolha(t) {
  const agora = new Date();
  const hojeIso = tlIsoDe(agora);
  _elFolha("tt-folha-titulo").textContent = t.title;
  let quando;
  if (!t.due_date) quando = "sem dia";
  else if (t.due_date < hojeIso) quando = `atrasada, era pra ${rotuloAtraso(t.due_date, agora)}`;
  else quando = rotuloDestino(t.due_date, agora).replace(/^pra /, "");
  const min = tlMinutos(t.hora);
  _elFolha("tt-folha-sub").textContent = `${quando}${min !== null ? ` às ${tlHora(min)}` : ", sem hora"}`;

  // ---- dia
  const dias = _elFolha("tt-folha-dias");
  dias.replaceChildren();
  const opcoes = diasDaFolha(agora);
  opcoes.forEach((d) => {
    const b = _chip(d.rotulo, { "data-dia": d.iso, "aria-pressed": String(t.due_date === d.iso) });
    b.addEventListener("click", () => _escolherDia(d.iso));
    dias.appendChild(b);
  });
  const foraDosChips = t.due_date && t.due_date >= hojeIso && !opcoes.some((d) => d.iso === t.due_date);
  const outro = _chipComSeletor("Outro dia", "date", t.due_date && t.due_date >= hojeIso ? t.due_date : "", "Escolher outro dia");
  outro.label.setAttribute("aria-pressed", String(Boolean(foraDosChips)));
  outro.input.min = hojeIso;
  outro.input.addEventListener("change", () => {
    if (/^\d{4}-\d{2}-\d{2}$/.test(outro.input.value)) _escolherDia(outro.input.value);
  });
  dias.appendChild(outro.label);

  // ---- hora
  const horas = _elFolha("tt-folha-horas");
  horas.replaceChildren();
  const semHora = _chip("Sem hora", { "aria-pressed": String(min === null) });
  semHora.addEventListener("click", () => _escolherHora(null));
  horas.appendChild(semHora);
  [
    [30, "+30 min"],
    [60, "+1 h"],
  ].forEach(([delta, texto]) => {
    const nova = horaSomada(t.hora, delta, agora);
    const b = _chip(texto, { "aria-pressed": "false" });
    if (!nova) b.disabled = true;
    else b.setAttribute("aria-label", `${texto}, fica ${nova}`);
    b.addEventListener("click", () => nova && _escolherHora(nova));
    horas.appendChild(b);
  });
  const escolher = _chipComSeletor(min !== null ? tlHora(min) : "Escolher", "time", min !== null ? tlHora(min) : "", "Escolher a hora");
  escolher.label.setAttribute("aria-pressed", String(min !== null));
  // a roda de hora do iPhone dispara "change" a cada giro: so grava quando o seletor fecha (blur) ou
  // com Enter - senao a folha fechava no primeiro giro
  const gravarHora = () => {
    const v = escolher.input.value;
    if (escolher.input.dataset.gravou || !/^\d{2}:\d{2}$/.test(v) || v === (min !== null ? tlHora(min) : "")) return;
    escolher.input.dataset.gravou = "1"; // Enter e o blur logo depois nao gravam duas vezes
    _escolherHora(v);
  };
  escolher.input.addEventListener("blur", gravarHora);
  escolher.input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      gravarHora();
    }
  });
  horas.appendChild(escolher.label);

  // ---- nome
  const nome = _elFolha("tt-folha-nome");
  nome.value = t.title;
  _folhaNomeInicial = t.title;

  // ---- passos (subtarefas)
  const blocoPassos = _elFolha("tt-folha-passos");
  const ul = blocoPassos.querySelector("ul");
  ul.replaceChildren();
  const passos = Array.isArray(t.subtasks) ? t.subtasks : [];
  blocoPassos.hidden = !passos.length;
  passos.forEach((s) => {
    const item = document.createElement("li");
    item.className = "tt-passo" + (s.completed_at ? " feito" : "");
    const label = document.createElement("label");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = Boolean(s.completed_at);
    cb.disabled = Boolean(s.completed_at);
    cb.addEventListener("change", async () => {
      cb.disabled = true;
      item.classList.add("feito");
      const r = await apiFetch(`/api/subtasks/${s.id}/complete`, { method: "POST" });
      if (r) _atualizarFolhaDoServidor(t.id);
      else {
        cb.checked = false;
        cb.disabled = false;
        item.classList.remove("feito");
      }
    });
    const span = document.createElement("span");
    span.textContent = s.title;
    label.appendChild(cb);
    label.appendChild(span);
    item.appendChild(label);
    ul.appendChild(item);
  });

  // ---- o que a tarefa ja tinha (fica embaixo, menor)
  _preencherMais(t);
}

function _preencherMais(t) {
  const mais = _elFolha("tt-folha-mais");
  const chips = mais.querySelector(".tt-chips");
  const extra = _elFolha("tt-folha-extra");
  chips.replaceChildren();
  extra.replaceChildren();

  if (typeof t.waze === "string" && t.waze.startsWith("https://waze.com/ul?")) {
    const b = _chip("Ir com Waze");
    b.insertAdjacentHTML("afterbegin", ICONE_NAVEGAR_FOLHA);
    b.addEventListener("click", () => window.open(t.waze, "_blank", "noopener"));
    chips.appendChild(b);
  }

  const passos = Array.isArray(t.subtasks) ? t.subtasks : [];
  const acaoPassos = t.empacada_dias
    ? ["Quebrar diferente", "pensando...", `/api/tasks/${t.id}/requebrar`, "POST"]
    : passos.length
      ? ["Desfazer passos", "desfazendo...", `/api/tasks/${t.id}/subtasks`, "DELETE"]
      : ["Quebrar em passos", "quebrando...", `/api/tasks/${t.id}/breakdown`, "POST"];
  const bPassos = _chip(acaoPassos[0]);
  bPassos.addEventListener("click", async () => {
    setBotaoCarregando(bPassos, true, acaoPassos[1]);
    const r = await apiFetch(acaoPassos[2], { method: acaoPassos[3] });
    if (r) _atualizarFolhaDoServidor(t.id);
    else setBotaoCarregando(bPassos, false, acaoPassos[0]);
  });
  chips.appendChild(bPassos);

  const rotuloCadeado = t.inegociavel ? "Soltar o cadeado" : "Não pode falhar";
  const bCadeado = _chip(rotuloCadeado, { "aria-pressed": String(Boolean(t.inegociavel)) });
  bCadeado.addEventListener("click", async () => {
    setBotaoCarregando(bCadeado, true, "...");
    const r = await apiFetch(`/api/tasks/${t.id}/inegociavel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ valor: !t.inegociavel }),
    });
    if (r) _atualizarFolhaDoServidor(t.id);
    else setBotaoCarregando(bCadeado, false, rotuloCadeado);
  });
  chips.appendChild(bCadeado);

  // esforco (Fase 5, US-C7): alimenta a sugestao por energia
  const esforco = document.createElement("label");
  esforco.className = "chip tt-chip tt-chip-esforco";
  esforco.append("Esforço ");
  const sel = document.createElement("select");
  sel.setAttribute("aria-label", "Esforço da tarefa");
  [["", "?"], ...NIVEIS_ENERGIA.map((n) => [n, n === "media" ? "média" : n])].forEach(([v, txt]) => {
    const o = document.createElement("option");
    o.value = v;
    o.textContent = txt;
    if ((t.esforco || "") === v) o.selected = true;
    if (!v) o.disabled = true;
    sel.appendChild(o);
  });
  sel.addEventListener("change", async () => {
    sel.disabled = true;
    const r = await apiFetch(`/api/tasks/${t.id}/esforco`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ esforco: sel.value }),
    });
    sel.disabled = false;
    if (r) _atualizarFolhaDoServidor(t.id);
  });
  esforco.appendChild(sel);
  chips.appendChild(esforco);

  if (t.fichas_treino && t.fichas_treino.length && typeof botaoFichaTreino === "function") {
    const b = botaoFichaTreino(t, extra);
    b.className = "chip tt-chip";
    b.textContent = "Ficha do treino";
    chips.appendChild(b);
  }

  const bGasto = _chip("É um gasto", { "aria-expanded": "false" });
  bGasto.addEventListener("click", () => {
    const aberto = extra.querySelector(".correcao-form");
    if (aberto) {
      aberto.remove();
      bGasto.setAttribute("aria-expanded", "false");
      return;
    }
    extra.appendChild(criarFormularioTarefaParaGasto(t, () => fecharFolhaTarefa()));
    bGasto.setAttribute("aria-expanded", "true");
  });
  chips.appendChild(bGasto);
}

// depois de uma acao que so o servidor sabe o resultado (passos, cadeado, esforco): recarrega e,
// se a folha ainda esta nessa tarefa, redesenha com o que voltou
async function _atualizarFolhaDoServidor(id) {
  _ultimoHashTarefas = null;
  await loadTasks();
  const nova = _tarefasPendentes.find((x) => String(x.id) === String(id));
  if (nova && _folhaTarefa && String(_folhaTarefa.id) === String(id)) {
    const nome = _elFolha("tt-folha-nome").value;
    _folhaTarefa = nova;
    _preencherFolha(nova);
    _elFolha("tt-folha-nome").value = nome; // o que ele estava digitando nao se perde
  }
}

function _aoFecharFolha() {
  const t = _folhaTarefa;
  _folhaTarefa = null;
  _folhaLi = null;
  if (!t) return;
  const novo = _elFolha("tt-folha-nome").value.split(/\s+/).filter(Boolean).join(" ").slice(0, 200);
  if (novo && novo !== _folhaNomeInicial) renomearTarefaDaAba(t, novo);
}

function _escolherDia(iso) {
  const t = _folhaTarefa;
  if (!t) return;
  const hoje = new Date();
  fecharFolhaTarefa();
  if (t.due_date === iso) return;
  moverTarefaDaAba(t, { data: iso }, `“${_tituloCurto(t.title)}” ${rotuloDestino(iso, hoje)}`);
}

function _escolherHora(hora) {
  const t = _folhaTarefa;
  if (!t) return;
  fecharFolhaTarefa();
  if ((t.hora || null) === hora) return;
  moverTarefaDaAba(t, { hora }, hora ? `“${_tituloCurto(t.title)}” às ${hora}` : `“${_tituloCurto(t.title)}” sem hora`);
}

function _liDaTarefa(id) {
  return document.querySelector(`#lista-tarefas li.tt-item[data-id="${CSS.escape(String(id))}"]`);
}

// Muda dia e/ou hora. `mudanca` = {data?, hora?} (o corpo da rota). Otimista: a linha desliza pro
// grupo/hora nova na hora; erro = volta. O Desfazer do toast volta na tela e no servidor.
async function moverTarefaDaAba(t, mudanca, texto) {
  const campos = {};
  if ("data" in mudanca) campos.due_date = mudanca.data;
  if ("hora" in mudanca) campos.hora = mudanca.hora;
  if (campos.hora && !("due_date" in campos) && !t.due_date) campos.due_date = tlIsoDe(new Date()); // igual a rota
  const antes = aplicarMudancaTarefa(t.id, campos) || t;
  const volta = { due_date: antes.due_date || null, hora: antes.hora || null };
  const r = await apiFetch(`/api/tasks/${encodeURIComponent(t.id)}/mover`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(mudanca),
  });
  if (!r) {
    aplicarMudancaTarefa(t.id, volta);
    return false;
  }
  _avisarMudancaTarefa(t.id, { campo: "mover" });
  _sincronizarDepois();
  if (r.mudou && r.token) {
    // date/balada/tarefa com lugar: a rota refez o plano de saida (mesma conta do chat)
    const sai = r.plano && r.plano.sair_de_casa;
    if (sai) texto = `${texto} · sai ${sai}`;
    mostrarDesfazer(texto, () => _desfazerNaTela(t.id, volta, r.token), { desfeito: "Voltou como estava" });
  }
  return true;
}

async function renomearTarefaDaAba(t, titulo) {
  const antes = aplicarMudancaTarefa(t.id, { title: titulo }) || t;
  const volta = { title: antes.title };
  const r = await apiFetch(`/api/tasks/${encodeURIComponent(t.id)}/titulo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ titulo }),
  });
  if (!r) {
    aplicarMudancaTarefa(t.id, volta);
    return false;
  }
  if (r.tarefa && r.tarefa.title && r.tarefa.title !== titulo) aplicarMudancaTarefa(t.id, { title: r.tarefa.title });
  _avisarMudancaTarefa(t.id, { campo: "titulo" });
  _sincronizarDepois();
  if (r.mudou && r.token) mostrarDesfazer("Renomeada", () => _desfazerNaTela(t.id, volta, r.token), { desfeito: "Voltou o nome de antes" });
  return true;
}

async function _desfazerNaTela(id, volta, token) {
  aplicarMudancaTarefa(id, volta);
  const r = await apiFetch(`/api/desfazer/${encodeURIComponent(token)}`, { method: "POST" });
  _avisarMudancaTarefa(id, { campo: "desfazer" });
  _sincronizarDepois();
  return Boolean(r);
}

// a lista ja mostra o certo; o servidor confirma por tras (contagens, outras abas) depois do deslize
let _sincronizarTimer = null;
function _sincronizarDepois() {
  clearTimeout(_sincronizarTimer);
  _sincronizarTimer = setTimeout(() => {
    if (typeof _recarregarTarefas === "function") _recarregarTarefas();
  }, 700);
}

function _feitoDaFolha() {
  const t = _folhaTarefa;
  const li = (_folhaLi && _folhaLi.isConnected && _folhaLi) || (t && _liDaTarefa(t.id));
  fecharFolhaTarefa();
  if (!t || !li) return;
  const caixa = li.querySelector(".tt-caixa");
  concluirTarefaDaLista(li, li._tarefa || t, caixa, caixa ? [caixa] : []);
}

function _apagarDaFolha() {
  const t = _folhaTarefa;
  const li = (_folhaLi && _folhaLi.isConnected && _folhaLi) || (t && _liDaTarefa(t.id));
  fecharFolhaTarefa();
  if (!t || !li) return;
  const fundo = li.querySelector(".arrasta-fundo");
  // mesma saida do deslizar (o vermelho toma a linha) e o mesmo Desfazer
  if (fundo && typeof excluirTarefaArrastada === "function") {
    t._saindo = true;
    if (typeof renderReguaTarefas === "function") renderReguaTarefas();
    excluirTarefaArrastada(li, li._tarefa || t, fundo).then(() => {
      if (li.isConnected) {
        delete t._saindo;
        if (typeof renderReguaTarefas === "function") renderReguaTarefas();
      }
    });
  }
}

(function ligarFolhaTarefa() {
  const folha = _elFolha("tarefa-folha");
  if (!folha) return;
  folha.addEventListener("bottomsheet:fechado", _aoFecharFolha);
  _elFolha("tt-folha-feito").addEventListener("click", _feitoDaFolha);
  _elFolha("tt-folha-apagar").addEventListener("click", _apagarDaFolha);
  _elFolha("tt-folha-nome").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      fecharFolhaTarefa();
    }
  });
})();
