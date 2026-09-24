// static/js/secoes/tarefas/tarefas.js - Secao tarefas > tarefas (HTML: templates/secoes/tarefas/tarefas.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 2304-2324, app.js 2413-2702.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

// ---- Sugestao por energia (Fase 5, US-C7) -------------------------------
async function carregarSugestaoEnergia(nivel) {
  const tasks = await apiFetch(`/api/tarefas/sugestao-energia?nivel=${nivel}`);
  if (!tasks) return;

  $("#energia-botoes")
    .querySelectorAll("button")
    .forEach((b) => b.classList.toggle("primario", b.dataset.nivel === nivel));

  const list = $("#lista-sugestao-energia");
  list.innerHTML = "";
  $("#sugestao-energia-vazio").hidden = tasks.length > 0;
  tasks.forEach((t) => list.appendChild(criarItemTarefa(t)));
}

$("#energia-botoes")
  .querySelectorAll("button")
  .forEach((btn) => {
    btn.addEventListener("click", () => carregarSugestaoEnergia(btn.dataset.nivel));
  });

const NIVEIS_ENERGIA = ["baixa", "media", "alta"];

// Fase 5 (US-C7): esforco estimado da tarefa - mesmo espirito de
// criarSeletorCategoriaGasto (tag que vira <select> num toque), pra
// vida.tarefas_compativeis_com_energia ter o que filtrar.
function criarTagEsforco(t) {
  const tag = document.createElement("span");
  tag.className = "item-quando item-tag-esforco";
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
  li.className = "item";
  // data-entidade/data-id: o link "Abrir Tarefas" de um card (Fase 6,
  // static/js/cards.js) rola ate o item e destaca.
  li.dataset.entidade = "tarefa";
  li.dataset.id = t.id;

  const linha = document.createElement("div");
  linha.className = "item-linha";

  const tituloWrap = document.createElement("div");
  const titulo = document.createElement("span");
  titulo.className = "item-titulo";
  titulo.textContent = t.title;
  if (t.recorrente_origem_id) {
    const tagRotina = document.createElement("span");
    tagRotina.className = "item-tag-tarefa";
    tagRotina.textContent = "rotina";
    titulo.appendChild(tagRotina);
  }
  tituloWrap.appendChild(titulo);
  if (t.due_at || t.hora || t.due_date) {
    const quando = document.createElement("span");
    quando.className = "item-quando";
    // Fase 6 (US-F10): due_at (texto livre tipo "amanha") continua tendo
    // prioridade quando existe (e o que o chat grava) - due_date sozinho
    // (o formulario direto novo grava so isso, sem passar pela IA) cai no
    // formatarPrazoTarefa pra pelo menos mostrar ALGUMA data, em vez de
    // nada (gap real: antes uma tarefa so com due_date nao mostrava prazo
    // nenhum na lista).
    const base = t.due_at || (t.due_date ? formatarPrazoTarefa(t.due_date) : "hoje");
    quando.textContent = t.hora ? `${base} as ${t.hora}` : base;
    tituloWrap.appendChild(quando);
  }
  // Mesma tag de atencao que "travada ha X dias" ja usa (--danger) - so
  // quando devido sem due_at/hora ja passou (devido com due_at continua sem
  // deteccao de atraso, devido/registrar_tarefa nunca calculou isso - fora
  // do escopo desta historia mexer nesse caminho tambem).
  if (t.due_date && !t.due_at && !t.hora && t.due_date < hojeIsoLocal()) {
    const tagAtrasada = document.createElement("span");
    tagAtrasada.className = "item-tag-travada";
    tagAtrasada.textContent = "atrasada";
    titulo.appendChild(tagAtrasada);
  }
  tituloWrap.appendChild(criarTagEsforco(t));

  const acoes = document.createElement("div");
  acoes.className = "item-acoes";

  if (t.empacada_dias) {
    const tagTravada = document.createElement("span");
    tagTravada.className = "item-tag-travada";
    tagTravada.textContent = `travada ha ${t.empacada_dias} dias`;
    titulo.appendChild(tagTravada);

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
  btnCorrigir.className = "btn-com-icone";
  btnCorrigir.title = "isso nao e uma tarefa?";
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
    const data = await apiFetch(`/api/tasks/${t.id}/complete`, { method: "POST" });
    if (data) {
      explodirConcluido(btnConcluir);
      vibrar(30);
      tocarSomConcluido();
      li.classList.add("saindo");
      setTimeout(() => {
        loadTasks();
        loadSummary();
        loadStreak();
        if (!$("#tab-painel").hidden) loadFechamentoDoDia();
      }, 220);
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

// Correcao rapida "isso nao e uma tarefa, e um gasto" - formulario minimo
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

async function loadTasks() {
  const tasks = await apiFetch("/api/tasks");
  if (!tasks) return;
  const list = $("#lista-tarefas");
  list.innerHTML = "";
  $("#tarefas-vazio").hidden = tasks.length > 0;
  tasks.forEach((t) => list.appendChild(criarItemTarefa(t)));
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

  setBotaoCarregando(btn, true, "salvando...");
  const data = await apiFetch("/api/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ titulo, due_date: prazoInput.value || null }),
  });
  setBotaoCarregando(btn, false, "Adicionar");
  if (!data) return;

  tituloInput.value = "";
  prazoInput.value = "";
  pulsarSucesso(tituloInput);
  loadTasks();
});
