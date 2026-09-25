// static/js/secoes/tarefas/tarefas.js - Secao tarefas > tarefas (HTML: templates/secoes/tarefas/tarefas.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 2304-2324, app.js 2413-2702.
// Fase 7 (V3-organizacao): botao "Nova tarefa" abre o formulario num bottom-sheet
// (contrato: docs/agentes/fase7-visual.md). Usa window.abrirBottomSheet/fecharBottomSheet
// (faixa V0d) quando existir; fallback so alterna o atributo hidden do painel.
// Fase 9 (faixa P-tarefas): topo em estilo "Conversa" (frase-resumo calculada em codigo +
// mini grafico de barras dos ultimos 7 dias) + seletor segmentado Pendentes/Hoje/Concluidas
// (contrato: tests/test_fase9_p_tarefas.py). loadTasks() continua sendo a funcao publica
// que o resto do app chama pra atualizar a aba (nucleo/navegacao.js, topo/captura.js,
// painel/brain-dump.js, gastos/gastos.js, hoje/chat.js) - ela agora tambem decide o que
// mostrar de acordo com o filtro atual, sem mudar essa assinatura (sem argumento).
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

  $("#energia-botoes")
    .querySelectorAll("button")
    .forEach((b) => {
      const ativo = b.dataset.nivel === nivel;
      b.classList.toggle("primario", ativo);
      b.classList.toggle("chip--ativo", ativo); // C2: chip do contrato
      b.setAttribute("aria-pressed", ativo ? "true" : "false");
    });

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

// Fase 9 (P-tarefas): mesma etiqueta de esforco, mas so leitura - nas
// tarefas concluidas nao faz sentido reabrir o <select> pra editar (o card
// e leve, so "titulo + linha fraca"); some se a tarefa nunca teve esforco
// marcado, em vez de convidar a marcar algo que ja acabou.
function criarTagEsforcoEstatica(t) {
  if (!t.esforco) return null;
  const tag = document.createElement("span");
  tag.className = "item-quando item-tag-esforco chip chip--compacto";
  tag.textContent = `esforço: ${t.esforco}`;
  return tag;
}

// Fase 9 (P-tarefas): "concluida em 12/09 as 14:32" a partir de completed_at
// (formato sqlite `datetime('now')`: "AAAA-MM-DD HH:MM:SS"). Mesmo formato
// de data de fmtDataBr (static/js/nucleo/formatos.js); sem conversao de fuso
// (o valor gravado e UTC "cru", igual o resto do app ja exibe esse campo).
function formatarConcluidaEm(completedAt) {
  if (!completedAt) return "";
  const [dataParte, horaParte] = String(completedAt).split(" ");
  if (!dataParte) return "";
  const hhmm = horaParte ? horaParte.slice(0, 5) : "";
  return hhmm ? `concluída em ${fmtDataBr(dataParte)} às ${hhmm}` : `concluída em ${fmtDataBr(dataParte)}`;
}

// Fase 9 (P-tarefas): mesma convencao de exibicao que criarItemTarefa ja usava
// pra "quando" (devido sem due_at/due_date cai em "hoje" quando so tem hora) -
// aqui reaproveitada pra decidir se a tarefa entra na aba "Hoje" do seletor.
function isTarefaDeHoje(t) {
  if (t.due_date) return t.due_date === hojeIsoLocal();
  if (t.due_at) return String(t.due_at).trim().toLowerCase() === "hoje";
  return Boolean(t.hora);
}

// Fase 9 (P-tarefas): checkbox redondo a esquerda do card (contrato visual da
// faixa: marcado = --cor-acento, sem glow, alvo de toque 44px via ::before em
// static/css/secoes/tarefas/conversa.css). Concluir chama /api/tasks/:id/complete
// (mesma rota de sempre); desmarcar uma concluida chama /api/tasks/:id/reabrir
// (rota que ja existia, Fase 6 US-E3) - "desfazer" pedido pela faixa.
function criarCheckboxTarefa(t, concluida, li, btnConcluirLegado) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "tf-check" + (concluida ? " tf-check--marcado" : "");
  btn.setAttribute("aria-pressed", concluida ? "true" : "false");
  btn.setAttribute("aria-label", concluida ? `Reabrir tarefa "${t.title}"` : `Concluir tarefa "${t.title}"`);
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    if (concluida) {
      const data = await apiFetch(`/api/tasks/${t.id}/reabrir`, { method: "POST" });
      if (data) {
        li.classList.add("saindo");
        setTimeout(loadTasks, 220);
      } else {
        btn.disabled = false;
      }
      return;
    }
    const data = await apiFetch(`/api/tasks/${t.id}/complete`, { method: "POST" });
    if (data) {
      explodirConcluido(btnConcluirLegado || btn);
      vibrar(30);
      tocarSomConcluido();
      li.classList.add("saindo");
      setTimeout(() => {
        loadTasks();
        loadSummary();
        loadStreak();
        // Fase 9 C-abas: fechamento-do-dia migrou de #tab-painel pra #tab-hoje.
        if (!$("#tab-hoje").hidden) loadFechamentoDoDia();
      }, 220);
    } else {
      btn.disabled = false;
    }
  });
  return btn;
}

function criarItemTarefa(t, concluida) {
  const li = document.createElement("li");
  li.className = "item lista-item";
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
    tagRotina.className = "item-tag-tarefa chip chip--compacto";
    tagRotina.textContent = "rotina";
    titulo.appendChild(tagRotina);
  }
  tituloWrap.appendChild(titulo);

  if (concluida) {
    // Fase 9 (P-tarefas): card leve - linha fraca com data/hora de conclusao
    // (a "categoria" da tarefa, aqui, e o esforco - tasks nao tem campo de
    // categoria como os gastos) em vez do "quando" de prazo, que ja passou.
    const quando = document.createElement("span");
    quando.className = "item-quando chip chip--compacto";
    quando.textContent = formatarConcluidaEm(t.completed_at);
    if (quando.textContent) tituloWrap.appendChild(quando);
    const esforcoEstatico = criarTagEsforcoEstatica(t);
    if (esforcoEstatico) tituloWrap.appendChild(esforcoEstatico);
  } else {
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
      quando.textContent = t.hora ? `${base} as ${t.hora}` : base;
      tituloWrap.appendChild(quando);
    }
    // Mesma tag de atencao que "travada ha X dias" ja usa (--danger) - so
    // quando devido sem due_at/hora ja passou (devido com due_at continua sem
    // deteccao de atraso, devido/registrar_tarefa nunca calculou isso - fora
    // do escopo desta historia mexer nesse caminho tambem).
    if (t.due_date && !t.due_at && !t.hora && t.due_date < hojeIsoLocal()) {
      const tagAtrasada = document.createElement("span");
      tagAtrasada.className = "item-tag-travada chip chip--compacto";
      tagAtrasada.textContent = "atrasada";
      titulo.appendChild(tagAtrasada);
    }
    tituloWrap.appendChild(criarTagEsforco(t));
  }

  const acoes = document.createElement("div");
  acoes.className = "item-acoes";

  // Fase 9 (P-tarefas): as acoes abaixo (requebrar/quebrar em passos, virar
  // gasto, fichas de treino) so fazem sentido numa tarefa ainda pendente - o
  // card de concluida fica so com titulo + linha fraca + checkbox (pedido
  // "cartoes leves" da faixa).
  if (!concluida) {
    if (t.empacada_dias) {
      const tagTravada = document.createElement("span");
      tagTravada.className = "item-tag-travada chip chip--compacto";
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
  }

  const linhaTopo = document.createElement("div");
  linhaTopo.className = "tf-item-linha";
  const checkbox = criarCheckboxTarefa(t, Boolean(concluida), li, null);
  const corpo = document.createElement("div");
  corpo.className = "tf-item-corpo";

  linha.appendChild(tituloWrap);
  linha.appendChild(acoes);
  corpo.appendChild(linha);

  if (t.subtasks.length > 0) {
    const sub = document.createElement("ul");
    sub.className = "subtarefas";
    t.subtasks.forEach((s) => {
      const subLi = document.createElement("li");
      subLi.className = "subtarefa" + (s.completed_at ? " concluida" : "");

      const checkboxSub = document.createElement("input");
      checkboxSub.type = "checkbox";
      checkboxSub.checked = Boolean(s.completed_at);
      checkboxSub.disabled = Boolean(s.completed_at) || concluida;
      checkboxSub.addEventListener("change", async () => {
        const data = await apiFetch(`/api/subtasks/${s.id}/complete`, { method: "POST" });
        if (data) loadTasks();
      });

      const label = document.createElement("span");
      label.textContent = s.title;

      subLi.appendChild(checkboxSub);
      subLi.appendChild(label);
      sub.appendChild(subLi);
    });
    corpo.appendChild(sub);
  }

  linhaTopo.appendChild(checkbox);
  linhaTopo.appendChild(corpo);
  li.appendChild(linhaTopo);

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

// ---- Fase 9 (P-tarefas): topo "Conversa" (frase-resumo + grafico) + seletor
// segmentado Pendentes/Hoje/Concluidas --------------------------------------

let filtroTarefasAtual = "pendentes";

const DIAS_SEMANA_ABREV = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];

// Fase 9 (P-tarefas): funcao pura (sem DOM), testavel isolada - mesmo espirito
// de construirSvgGastoAcumulado (static/js/secoes/hoje/conversa.js). Conta,
// por dia, quantas tarefas de `concluidas` (lista real da API, sem inventar
// numero) tem completed_at nesse dia; eixo com os ultimos 7 dias terminando
// hoje, rotulado com o dia da semana em pt-BR abreviado.
function construirGraficoSemanalTarefas(concluidas, hojeIso) {
  hojeIso = hojeIso || hojeIsoLocal();
  const hoje = new Date(`${hojeIso}T00:00:00`);
  const dias = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date(hoje);
    d.setDate(d.getDate() - i);
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    dias.push({ iso, rotulo: DIAS_SEMANA_ABREV[d.getDay()], total: 0 });
  }
  const porDia = {};
  dias.forEach((d) => (porDia[d.iso] = d));
  (concluidas || []).forEach((t) => {
    if (!t.completed_at) return;
    const iso = String(t.completed_at).slice(0, 10);
    if (porDia[iso]) porDia[iso].total += 1;
  });
  const maxTotal = Math.max.apply(
    null,
    dias.map((d) => d.total).concat([1])
  );
  const colunas = dias
    .map((d) => {
      const alturaPct = d.total ? Math.max(Math.round((d.total / maxTotal) * 100), 8) : 0;
      const ehHoje = d.iso === hojeIso ? " tf-barra-col--hoje" : "";
      return (
        `<div class="tf-barra-col${ehHoje}">` +
        `<span class="tf-barra-total">${d.total || ""}</span>` +
        `<div class="tf-barra-trilho"><div class="tf-barra" style="height:${alturaPct}%"></div></div>` +
        `<span class="tf-barra-rotulo">${d.rotulo}</span>` +
        `</div>`
      );
    })
    .join("");
  return `<div class="tf-grafico-barras">${colunas}</div>`;
}

// Fase 9 (P-tarefas): "Você tem 7 pendentes, 2 pra hoje." - contagem calculada
// em codigo a partir da lista real de pendentes (sem IA, sem numero inventado).
function montarFraseResumoTarefas(totalPendentes, totalHoje) {
  if (totalPendentes === 0) return "Você não tem tarefas pendentes. Tudo em dia.";
  const plural = totalPendentes === 1 ? "" : "s";
  const partePendentes = `Você tem ${totalPendentes} pendente${plural}`;
  const parteHoje = totalHoje > 0 ? `${totalHoje} pra hoje.` : "nenhuma pra hoje.";
  return `${partePendentes}, ${parteHoje}`;
}

function atualizarConversaTarefas(pendentes, concluidas) {
  const totalHoje = pendentes.filter(isTarefaDeHoje).length;
  $("#tf-frase-resumo").textContent = montarFraseResumoTarefas(pendentes.length, totalHoje);
  $("#tf-grafico-semana").innerHTML = construirGraficoSemanalTarefas(concluidas);
}

function textoVazioTarefas(filtro) {
  if (filtro === "concluidas") return "Nenhuma tarefa concluída ainda.";
  if (filtro === "hoje") return "Nenhuma tarefa pra hoje.";
  return "Nenhuma tarefa pendente. Ta tudo feito.";
}

async function loadTasks() {
  const filtro = filtroTarefasAtual;
  const [pendentes, concluidas] = await Promise.all([
    apiFetch("/api/tasks"),
    apiFetch("/api/tasks?estado=concluidas&limite=100"),
  ]);
  if (!pendentes) return;
  const listaConcluidas = Array.isArray(concluidas) ? concluidas : [];

  atualizarConversaTarefas(pendentes, listaConcluidas);

  let tasks;
  let concluida = false;
  if (filtro === "concluidas") {
    // Contrato da faixa: mostra as ultimas 30 (o grafico acima usa ate 100
    // pra nao perder dias com mais conclusoes do que cabem na lista).
    tasks = listaConcluidas.slice(0, 30);
    concluida = true;
  } else if (filtro === "hoje") {
    tasks = pendentes.filter(isTarefaDeHoje);
  } else {
    tasks = pendentes;
  }

  const list = $("#lista-tarefas");
  list.innerHTML = "";
  $("#tarefas-vazio-texto").textContent = textoVazioTarefas(filtro);
  $("#tarefas-vazio").hidden = tasks.length > 0;
  tasks.forEach((t) => list.appendChild(criarItemTarefa(t, concluida)));

  // Triar por energia so faz sentido pra tarefa ainda pendente.
  const blocoEnergia = $("#tf-bloco-energia");
  if (blocoEnergia) blocoEnergia.hidden = filtro !== "pendentes";
}

$("#tarefas-seletor")
  .querySelectorAll(".tf-seg-btn")
  .forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.dataset.estado === filtroTarefasAtual) return;
      filtroTarefasAtual = btn.dataset.estado;
      $("#tarefas-seletor")
        .querySelectorAll(".tf-seg-btn")
        .forEach((b) => {
          const ativo = b === btn;
          b.classList.toggle("chip--ativo", ativo);
          b.setAttribute("aria-pressed", ativo ? "true" : "false");
        });
      loadTasks();
    });
  });

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
  setBotaoCarregando(btn, false, "Salvar tarefa");
  if (!data) return;

  tituloInput.value = "";
  prazoInput.value = "";
  pulsarSucesso(tituloInput);
  fecharPainelTarefa();
  loadTasks();
});

// Dual export (mesmo padrao de static/js/ui/secao-recolhivel.js): em Node
// (testes `node --test`, sem DOM) so as funcoes puras ficam acessiveis.
if (typeof module !== "undefined" && module.exports) {
  module.exports = { construirGraficoSemanalTarefas, montarFraseResumoTarefas, isTarefaDeHoje };
}
