// static/js/secoes/vida/treino.js - Secao vida > treino (HTML: templates/secoes/vida/treino.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 905-1086.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

let fichasTreinoCache = null;

async function obterFichasTreino(forcar = false) {
  if (!fichasTreinoCache || forcar) {
    const fichas = await apiFetch("/api/treino/fichas");
    if (fichas) fichasTreinoCache = fichas;
  }
  return fichasTreinoCache || [];
}

// Fase 6 US-F4: cada exercicio guardado por linha, campos separados por "|"
// (nome|series|reps|carga - "|" nunca aparece em nome de exercicio digitado
// a mao). Ficha ANTIGA (texto livre, uma linha por exercicio, sem "|") cai
// no `else` e continua mostrada palavra por palavra, sem perder nada.
function parseLinhaExercicio(linha) {
  const partes = linha.split("|");
  if (partes.length === 4) {
    const [nome, series, reps, carga] = partes.map((p) => p.trim());
    if (nome) return { nome, series, reps, carga, estruturado: true };
  }
  return { nome: linha, series: "", reps: "", carga: "", estruturado: false };
}

function serializarExercicio(ex) {
  return [ex.nome, ex.series, ex.reps, ex.carga].map((v) => (v || "").toString().trim()).join("|");
}

function renderExerciciosFicha(ficha) {
  const box = criarEl("div", "ficha-treino");
  box.appendChild(criarEl("p", "ficha-treino-grupo", ficha.grupo));
  const ul = criarEl("ul", "ficha-treino-lista");
  ficha.exercicios
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)
    .forEach((linha) => {
      const ex = parseLinhaExercicio(linha);
      const li = criarEl("li", "ficha-exercicio-linha");
      li.appendChild(criarEl("span", "ficha-exercicio-nome", ex.nome));
      if (ex.estruturado) {
        const detalhe = [ex.series && ex.reps ? `${ex.series}x${ex.reps}` : ex.series || ex.reps, ex.carga]
          .filter(Boolean)
          .join(" · ");
        if (detalhe) li.appendChild(criarEl("span", "ficha-exercicio-detalhe", detalhe));
      }
      ul.appendChild(li);
    });
  box.appendChild(ul);
  return box;
}

// ---- Fase 6 US-F4: montar a ficha um exercicio por vez ----

let fichaExerciciosPendentes = [];

function renderFichaExerciciosPendentes() {
  const ul = $("#ficha-exercicios-pendentes");
  ul.innerHTML = "";
  $("#ficha-exercicios-vazio").hidden = fichaExerciciosPendentes.length > 0;
  fichaExerciciosPendentes.forEach((ex, idx) => {
    const li = criarEl("li", "ficha-exercicio-pendente");
    const info = criarEl("span", null, ex.nome);
    const detalhe = [ex.series && ex.reps ? `${ex.series}x${ex.reps}` : ex.series || ex.reps, ex.carga]
      .filter(Boolean)
      .join(" · ");
    if (detalhe) {
      const span = criarEl("span", "ficha-exercicio-detalhe", ` ${detalhe}`);
      info.appendChild(span);
    }
    li.appendChild(info);
    const remover = criarEl("button", "btn-link", "remover");
    remover.type = "button";
    remover.setAttribute("aria-label", `Remover ${ex.nome} da ficha`);
    remover.addEventListener("click", () => {
      fichaExerciciosPendentes.splice(idx, 1);
      renderFichaExerciciosPendentes();
    });
    li.appendChild(remover);
    ul.appendChild(li);
  });
}

$("#ficha-ex-add-btn").addEventListener("click", () => {
  const nomeInput = $("#ficha-ex-nome");
  const nome = nomeInput.value.trim();
  if (!nome) {
    mostrarErro("Digite o nome do exercicio antes de adicionar.");
    return;
  }
  fichaExerciciosPendentes.push({
    nome,
    series: $("#ficha-ex-series").value.trim(),
    reps: $("#ficha-ex-reps").value.trim(),
    carga: $("#ficha-ex-carga").value.trim(),
  });
  nomeInput.value = "";
  $("#ficha-ex-series").value = "";
  $("#ficha-ex-reps").value = "";
  $("#ficha-ex-carga").value = "";
  pulsarSucesso(nomeInput);
  renderFichaExerciciosPendentes();
  nomeInput.focus();
});

// Chamado pelo criarItemTarefa (app.js) quando a tarefa bate com uma ficha.
function botaoFichaTreino(t, li) {
  const btn = criarEl("button", "btn-info-treino", "!");
  btn.type = "button";
  btn.setAttribute("aria-label", `Ver ficha de treino de ${t.title}`);
  btn.setAttribute("aria-expanded", "false");
  btn.addEventListener("click", async () => {
    const aberto = li.querySelector(".fichas-da-tarefa");
    if (aberto) {
      aberto.remove();
      btn.setAttribute("aria-expanded", "false");
      return;
    }
    let cache = await obterFichasTreino();
    // Ficha criada pelo chat (ou em outro aparelho) depois do cache: recarrega.
    if (t.fichas_treino.some((id) => !cache.some((f) => f.id === id))) cache = await obterFichasTreino(true);
    const fichas = cache.filter((f) => t.fichas_treino.includes(f.id));
    const wrap = criarEl("div", "fichas-da-tarefa");
    fichas.forEach((f) => wrap.appendChild(renderExerciciosFicha(f)));
    li.appendChild(wrap);
    btn.setAttribute("aria-expanded", "true");
  });
  return btn;
}

async function loadTreino() {
  const fichas = await obterFichasTreino(true);
  const lista = $("#lista-fichas");
  lista.innerHTML = "";
  $("#fichas-vazio").hidden = fichas.length > 0;
  fichas.forEach((f) => {
    const n = f.exercicios.split("\n").filter((l) => l.trim()).length;
    const li = itemSimples(f.grupo, [`${n} exercicio(s)`], [(el) => botaoApagar(`/api/treino/fichas/${f.id}`, el)]);
    li.classList.add("lista-item");
    li.appendChild(renderExerciciosFicha(f));
    lista.appendChild(li);
  });
  const treinos = await apiFetch("/api/treino");
  const recentes = $("#treinos-recentes");
  if (treinos && treinos.length) {
    recentes.hidden = false;
    recentes.textContent =
      "Ultimos treinos: " +
      treinos
        .slice(0, 4)
        .map((t) => [fmtDataBr(t.data), t.grupo, t.duracao_min ? `${t.duracao_min}min` : null].filter(Boolean).join(" "))
        .join(" | ");
  } else {
    recentes.hidden = true;
  }
}

// Fase 7 V4: botao "Nova ficha" abre o formulario num bottom-sheet
// (static/js/ui/bottom-sheet.js, faixa V0d). Enquanto essa faixa nao chega na
// integracao, cai no fallback inline (so hidden) - retestado depois do merge
// com origin/fase7/integracao.
$("#ficha-abrir-btn").addEventListener("click", () => {
  const sheet = $("#sheet-ficha");
  if (window.abrirBottomSheet) window.abrirBottomSheet(sheet);
  else sheet.hidden = false;
});

$("#ficha-fechar-btn").addEventListener("click", () => {
  const sheet = $("#sheet-ficha");
  if (window.fecharBottomSheet) window.fecharBottomSheet(sheet);
  else sheet.hidden = true;
});

ligarForm(
  "#ficha-form",
  "#ficha-btn",
  "Salvar ficha",
  () => {
    const grupo = $("#ficha-grupo").value.trim();
    if (!grupo || !fichaExerciciosPendentes.length) {
      mostrarErro("Informe o grupo e adicione ao menos 1 exercicio antes de salvar.");
      return null;
    }
    const exercicios = fichaExerciciosPendentes.map(serializarExercicio).join("\n");
    return { grupo, exercicios };
  },
  "/api/treino/fichas",
  (r) => {
    fichaExerciciosPendentes = [];
    renderFichaExerciciosPendentes();
    const sheet = $("#sheet-ficha");
    if (window.fecharBottomSheet) window.fecharBottomSheet(sheet);
    else sheet.hidden = true;
    loadTreino(r);
  }
);

// ---- Fase 2 + Fase 5 (US-C14) + Fase 6 (US-E1a): manutencao (secao unica) ----
// tipo='carro' e HISTORICO (registro novo a cada manutencao feita, aviso por
// km/data, sem botao "feita hoje"); os demais tipos (casa/equipamento/outro)
// sao EDICAO NO LUGAR (um item so, "feita hoje" atualiza a data), igual
// sempre foi antes da unificacao das duas secoes.
