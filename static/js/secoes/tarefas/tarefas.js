// static/js/secoes/tarefas/tarefas.js - Secao tarefas > tarefas (HTML: templates/secoes/tarefas/tarefas.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 2304-2324, app.js 2413-2702.
// Fase 7 (V3-organizacao): botao "Nova tarefa" abre o formulario num bottom-sheet
// (contrato: docs/agentes/fase7-visual.md). Usa window.abrirBottomSheet/fecharBottomSheet
// (faixa V0d) quando existir; fallback so alterna o atributo hidden do painel.
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

// Fase 5 (US-C7): esforco estimado da tarefa - mesmo espirito de
// criarSeletorCategoriaGasto (tag que vira <select> num toque), pra
// vida.tarefas_compativeis_com_energia ter o que filtrar.
function criarTagEsforco(t) {
  // C2: <button> (era <span> clicavel: sem teclado nem foco) e chip compacto (rotulo, nao CTA).
  const tag = document.createElement("button");
  tag.type = "button";
  tag.className = "item-quando item-tag-esforco chip chip--compacto";
  tag.textContent = t.esforco ? `esforço: ${t.esforco}` : "definir esforço";
  tag.title = "toque pra marcar o esforco dessa tarefa";
  tag.addEventListener("click", () => {
    const select = document.createElement("select");
    select.className = "correcao-select";
    NIVEIS_ENERGIA.forEach((n) => {
      const opt = document.createElement("option");
      opt.value = n;
      opt.textContent = n;
      if (n === t.esforco) opt.selected = true;
      select.appendChild(opt);
    });
    select.addEventListener("click", (ev) => ev.stopPropagation());
    select.addEventListener("blur", () => {
      if (select.parentElement) select.replaceWith(tag);
    });
    select.addEventListener("change", async () => {
      select.disabled = true;
      const data = await apiFetch(`/api/tasks/${t.id}/esforco`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ esforco: select.value }),
      });
      if (data) loadTasks();
      else select.disabled = false;
    });
    tag.replaceWith(select);
    select.focus();
  });
  return tag;
}

function criarItemTarefa(t) {
  const li = document.createElement("li");
  li.className = "item lista-item";
  // data-entidade/data-id: o link "Abrir Tarefas" de um card (Fase 6,
  // static/js/cards.js) rola ate o item e destaca.
  li.dataset.entidade = "tarefa";
  li.dataset.id = t.id;

  const linha = document.createElement("div");
  linha.className = "item-linha";

  const tituloWrap = document.createElement("div");
  tituloWrap.className = "item-textos";
  const titulo = document.createElement("span");
  titulo.className = "item-titulo";
  titulo.textContent = t.title;
  tituloWrap.appendChild(titulo);
  // R3 (acabamento): os chips (prazo, atrasada, travada, rotina, esforço) saem de dentro do
  // título e vão pra uma linha própria embaixo dele - título de 17px respira e os chips
  // quebram linha sem espremer nada.
  const chips = document.createElement("div");
  chips.className = "item-chips";
  if (t.recorrente_origem_id) {
    const tagRotina = document.createElement("span");
    tagRotina.className = "item-tag-tarefa chip chip--compacto";
    tagRotina.textContent = "rotina";
    chips.appendChild(tagRotina);
  }
  if (t.due_at || t.hora || t.due_date) {
    const quando = document.createElement("span");
    quando.className = "item-quando chip chip--compacto";
    // Fase 6 (US-F10): due_at (texto livre tipo "amanha") continua tendo
    // prioridade quando existe (e o que o chat grava) - due_date sozinho
    // (o formulario direto novo grava so isso, sem passar pela IA) cai no
    // formatarPrazoTarefa pra pelo menos mostrar ALGUMA data, em vez de
    // nada (gap real: antes uma tarefa so com due_date nao mostrava prazo
    // nenhum na lista).
    const base = t.due_at || (t.due_date ? formatarPrazoTarefa(t.due_date) : "hoje");
    quando.textContent = t.hora ? `${base} às ${t.hora}` : base;
    chips.appendChild(quando);
  }
  // Mesma tag de atencao que "travada ha X dias" ja usa (--danger) - so
  // quando devido sem due_at/hora ja passou (devido com due_at continua sem
  // deteccao de atraso, devido/registrar_tarefa nunca calculou isso - fora
  // do escopo desta historia mexer nesse caminho tambem).
  if (t.due_date && !t.due_at && !t.hora && t.due_date < hojeIsoLocal()) {
    const tagAtrasada = document.createElement("span");
    tagAtrasada.className = "item-tag-travada chip chip--compacto";
    tagAtrasada.textContent = "atrasada";
    chips.appendChild(tagAtrasada);
  }

  const acoes = document.createElement("div");
  acoes.className = "item-acoes";

  if (t.empacada_dias) {
    const tagTravada = document.createElement("span");
    tagTravada.className = "item-tag-travada chip chip--compacto";
    tagTravada.textContent = `travada há ${t.empacada_dias} ${t.empacada_dias === 1 ? "dia" : "dias"}`;
    chips.appendChild(tagTravada);
  }
  chips.appendChild(criarTagEsforco(t));
  tituloWrap.appendChild(chips);


  if (t.empacada_dias) {
    const btnRequebrar = document.createElement("button");
    btnRequebrar.className = "btn-com-icone";
    btnRequebrar.innerHTML = `${ICONE_PASSOS}quebrar diferente`;
    btnRequebrar.addEventListener("click", async () => {
      setBotaoCarregando(btnRequebrar, true, "pensando...");
      const data = await apiFetch(`/api/tasks/${t.id}/requebrar`, { method: "POST" });
      if (data) loadTasks();
      else setBotaoCarregando(btnRequebrar, false, "quebrar diferente");
    });
    acoes.appendChild(btnRequebrar);
  } else if (t.subtasks.length === 0) {
    const btnQuebrar = document.createElement("button");
    btnQuebrar.className = "btn-com-icone";
    btnQuebrar.innerHTML = `${ICONE_PASSOS}quebrar em passos`;
    btnQuebrar.addEventListener("click", async () => {
      setBotaoCarregando(btnQuebrar, true, "quebrando...");
      const data = await apiFetch(`/api/tasks/${t.id}/breakdown`, { method: "POST" });
      if (data) loadTasks();
      else setBotaoCarregando(btnQuebrar, false, "quebrar em passos");
    });
    acoes.appendChild(btnQuebrar);
  }

  if (t.fichas_treino && t.fichas_treino.length && typeof botaoFichaTreino === "function") {
    acoes.appendChild(botaoFichaTreino(t, li));
  }

  const btnCorrigir = document.createElement("button");
  btnCorrigir.className = "btn-com-icone tarefa-corrigir";
  btnCorrigir.title = "isso não é uma tarefa?";
  btnCorrigir.setAttribute("aria-label", "Isso não é uma tarefa? Corrigir");
  btnCorrigir.innerHTML = ICONE_CORRIGIR;
  btnCorrigir.addEventListener("click", () => {
    const jaAberto = li.querySelector(".correcao-form");
    if (jaAberto) {
      jaAberto.remove();
      return;
    }
    li.appendChild(criarFormularioTarefaParaGasto(t, li));
  });
  acoes.appendChild(btnCorrigir);

  const btnConcluir = document.createElement("button");
  btnConcluir.className = "primario btn-com-icone";
  btnConcluir.innerHTML = `${ICONE_CHECK}concluir`;
  btnConcluir.addEventListener("click", async () => {
    if (btnConcluir.disabled) return; // evita duplo toque
    btnConcluir.disabled = true;
    // Vel A2b: otimista - marca, anima e remove da lista na hora do toque;
    // a gravacao (POST) vai por tras. Guarda a posicao pra devolver a
    // tarefa no mesmo lugar se a rede falhar (mostrarErro ja vem do apiFetch).
    const pai = li.parentElement;
    const proximoIrmao = li.nextElementSibling;
    explodirConcluido(btnConcluir);
    vibrar(30);
    tocarSomConcluido();
    // Vis (C2): "saindo" primeiro (e o que a Vel A2b mede - some quase na
    // hora do toque, sem esperar nada abaixo). O resto do reforco visual
    // (check desenhando, titulo riscando) vem depois, protegido por
    // try/catch pra nunca atrasar nem quebrar a saida otimista se o SVG/
    // getTotalLength falhar em algum navegador.
    li.classList.add("saindo");
    // rAF: o reforco visual (check desenhando/titulo riscando) roda so DEPOIS
    // do frame que ja mostra "saindo" - nunca compete com o trabalho sincrono
    // do proprio toque (o que a Vel A2b mede continua sendo so a linha acima).
    requestAnimationFrame(() => {
      try {
        if (typeof animarConclusaoTarefa === "function" && li.isConnected) animarConclusaoTarefa(li);
      } catch (erro) {
        /* reforco visual e cosmetico - a tarefa ja saiu da lista, nao trava por isso */
      }
      try {
        // Limpa (A-anim): fecha o espaco da lista suavemente (grid-rows,
        // movimento.js) - roda no mesmo rAF que o reforco visual acima,
        // sempre DEPOIS do "saindo" sincrono, nunca no meio do toque.
        if (typeof colapsarSaidaLista === "function" && li.isConnected) colapsarSaidaLista(li);
      } catch (erro) {
        /* colapso e cosmetico - nao trava a saida otimista se falhar */
      }
    });
    // 260ms: da tempo do colapso de altura (--dur-media, comeca ~1 frame
    // depois do toque) terminar antes da remocao de verdade, sem a lista
    // "pular" no instante em que o <li> sai do DOM.
    const removerTimeout = setTimeout(() => li.remove(), 260);

    const data = await apiFetch(`/api/tasks/${t.id}/complete`, { method: "POST" });
    if (data) {
      loadTasks();
      loadSummary();
      loadStreak();
      if (!$("#tab-painel").hidden) loadFechamentoDoDia();
      // M3: concluida some da lista principal mas, se "Ver concluidas" ja
      // ta aberto, essa que acabou de ser marcada deveria aparecer nela.
      const listaConcluidas = $("#lista-tarefas-concluidas");
      if (listaConcluidas && !listaConcluidas.hidden) loadTarefasConcluidas();
    } else {
      clearTimeout(removerTimeout);
      li.classList.remove("saindo");
      // Limpa (A-anim): tira o colapso de altura tambem - o rAF que liga
      // c2-saindo-colapsa confere .saindo antes de aplicar, mas se ele ja
      // tinha corrido antes do erro chegar, desfaz aqui pra nao deixar a
      // linha "achatada" com o item de volta na lista.
      li.classList.remove("c2-colapsavel");
      li.classList.remove("c2-saindo-colapsa");
      const tituloRiscado = li.querySelector(".c2-titulo-riscando");
      if (tituloRiscado) tituloRiscado.classList.remove("c2-titulo-riscando");
      const checkDesenhado = li.querySelector(".c2-check-desenha");
      if (checkDesenhado) checkDesenhado.classList.remove("c2-check-desenha");
      btnConcluir.disabled = false;
      if (pai && !pai.contains(li)) {
        if (proximoIrmao && proximoIrmao.parentElement === pai) pai.insertBefore(li, proximoIrmao);
        else pai.appendChild(li);
      }
    }
  });
  acoes.appendChild(btnConcluir);

  linha.appendChild(tituloWrap);
  linha.appendChild(acoes);
  li.appendChild(linha);

  if (t.subtasks.length > 0) {
    const sub = document.createElement("ul");
    sub.className = "subtarefas";
    t.subtasks.forEach((s) => {
      const subLi = document.createElement("li");
      subLi.className = "subtarefa" + (s.completed_at ? " concluida" : "");

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = Boolean(s.completed_at);
      checkbox.disabled = Boolean(s.completed_at);
      checkbox.addEventListener("change", async () => {
        const data = await apiFetch(`/api/subtasks/${s.id}/complete`, { method: "POST" });
        if (data) loadTasks();
      });

      const label = document.createElement("span");
      label.textContent = s.title;

      subLi.appendChild(checkbox);
      subLi.appendChild(label);
      sub.appendChild(subLi);
    });
    li.appendChild(sub);
  }

  return li;
}

// Correcao rapida "isso não e uma tarefa, e um gasto" - formulario minimo
// (o texto original pode nao ter um valor claro, entao pede o valor certo
// na hora, do jeito que o Alex quiser) que aparece inline no card e some se
// for cancelado ou depois de corrigir com sucesso.
function criarFormularioTarefaParaGasto(t, li) {
  const form = document.createElement("div");
  form.className = "correcao-form";

  const valorInput = document.createElement("input");
  valorInput.type = "number";
  valorInput.step = "0.01";
  valorInput.min = "0.01";
  valorInput.placeholder = "valor (R$)";
  valorInput.className = "correcao-input";

  const categoriaSelect = document.createElement("select");
  categoriaSelect.className = "correcao-select";
  CATEGORIAS_GASTO.forEach((cat) => {
    const opt = document.createElement("option");
    opt.value = cat;
    opt.textContent = cat;
    categoriaSelect.appendChild(opt);
  });

  const btnConfirmar = document.createElement("button");
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
      li.classList.add("saindo");
      setTimeout(() => {
        loadTasks();
        loadExpenses();
      }, 220);
    } else {
      setBotaoCarregando(btnConfirmar, false, "virar gasto");
    }
  });

  const btnCancelar = document.createElement("button");
  btnCancelar.className = "btn-com-icone";
  btnCancelar.textContent = "cancelar";
  btnCancelar.addEventListener("click", () => form.remove());

  form.appendChild(valorInput);
  form.appendChild(categoriaSelect);
  form.appendChild(btnConfirmar);
  form.appendChild(btnCancelar);
  return form;
}

// Vel A2b: hash barato do ultimo /api/tasks renderizado - troca de aba pra
// tarefas repete essa chamada toda vez, mas se os dados nao mudaram desde a
// ultima renderizacao nao vale a pena reconstruir ~100 <li> de novo.
let _ultimoHashTarefas = null;

// Vel (A2d): medido - abrir a aba tarefas com ~100 itens tinha
// "resultado visivel" (a aba aparecer de fato) mais lento que o proprio
// toque (INP), porque a montagem dos ~100 <li> (apos o fetch acima
// resolver, quase sempre rapido) rodava tudo numa tarefa so, sem deixar o
// navegador pintar o `hidden = false` da aba no meio do caminho - o loop de
// medicao (rAF) so via a condicao satisfeita depois que essa tarefa toda
// terminava. Aqui o primeiro lote (o que cabe na tela sem rolar) monta na
// hora; o resto entra num frame seguinte (rAF + setTimeout 0, mesmo padrao
// da aba gastos acima) pra nao competir com esse primeiro paint.
const LOTE_INICIAL_TAREFAS = 10;

// Lista longa (100 tarefas) so monta 10 por vez: "Ver mais" acrescenta o proximo
// lote. O que ja foi mostrado continua mostrado quando a lista recarrega.
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

function montarListaTarefas() {
  const list = $("#lista-tarefas");
  const frag = document.createDocumentFragment();
  _tarefasPendentes
    .slice(0, _tarefasMostradas)
    .forEach((t) => frag.appendChild(criarItemTarefa(t)));
  list.innerHTML = "";
  list.appendChild(frag);
  atualizarVerMaisTarefas();
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
  const novoTotal = proximoLoteTarefas(_tarefasPendentes.length, _tarefasMostradas);
  const list = $("#lista-tarefas");
  const frag = document.createDocumentFragment();
  _tarefasPendentes
    .slice(_tarefasMostradas, novoTotal)
    .forEach((t) => frag.appendChild(criarItemTarefa(t)));
  list.appendChild(frag);
  _tarefasMostradas = novoTotal;
  atualizarVerMaisTarefas();
});

// ---- "Ver concluidas" (M3, uso diario) ----------------------------------
// Concluida some da lista principal (filtro no /api/tasks padrao), mas NUNCA
// e apagada - aqui da pra ver de novo e desmarcar (POST /api/tasks/:id/reabrir,
// mesma rota que ja existe pro checkbox do card em tarefas_criadas). Busca
// preguicosa: so bate a API quando o dono toca no botao, nunca junto do
// loadTasks() normal.
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

// Vel (A2d): item provisorio pro formulario direto - mesmo espirito visual
// de criarCardCapturaSalvando (captura.js): titulo real + chip "salvando"
// (spinner), borda tracejada/opacidade (.item-otimista, static/css/style.css)
// pra ficar claro que ainda nao confirmou com o servidor.
function criarItemTarefaOtimista(titulo, prazoDate) {
  const li = document.createElement("li");
  li.className = "item lista-item item-otimista";

  const linha = document.createElement("div");
  linha.className = "item-linha";

  const tituloWrap = document.createElement("div");
  const tituloEl = document.createElement("span");
  tituloEl.className = "item-titulo";
  tituloEl.textContent = titulo;
  tituloWrap.appendChild(tituloEl);

  if (prazoDate) {
    const prazoEl = document.createElement("span");
    prazoEl.className = "item-quando chip chip--compacto";
    prazoEl.textContent = formatarPrazoTarefa(prazoDate);
    tituloWrap.appendChild(prazoEl);
  }

  const salvando = document.createElement("span");
  salvando.className = "item-quando chip chip--compacto";
  salvando.innerHTML = `<span class="spinner"></span><span>salvando...</span>`;
  tituloWrap.appendChild(salvando);

  linha.appendChild(tituloWrap);
  li.appendChild(linha);
  return li;
}

// Fase 6 (US-F10): formulario direto na aba Tarefas - titulo obrigatorio,
// prazo OPCIONAL (POST /api/tasks novo, sem passar pela IA - o chat/captura
// ja tinham esse caminho via registrar_tarefa/quando_data havia tempos).
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

  // Vel (A2d): otimista - mesmo padrao do botao "concluir" (Vel A2b, acima
  // nesse arquivo): a tarefa aparece na lista na hora do toque (estado
  // "salvando"), confirma com os dados reais quando o POST volta; em erro
  // sai da lista e devolve o texto pro campo (mostrarErro ja vem do
  // apiFetch).
  const list = $("#lista-tarefas");
  const liOtimista = criarItemTarefaOtimista(titulo, prazo);
  if (list) {
    list.insertBefore(liOtimista, list.firstChild);
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
  liOtimista.remove();
  if (!data) {
    tituloInput.value = titulo;
    if (prazo) prazoInput.value = prazo;
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
  module.exports = { calcularHashTarefas, proximoLoteTarefas };
}
