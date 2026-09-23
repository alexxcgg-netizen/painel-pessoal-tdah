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

function rotinaVisivel(momento) {
  const h = new Date().getHours();
  return momento === "manha" ? h >= 5 && h < 12 : h >= 20 || h < 3;
}

async function loadRotina() {
  const data = await apiFetch("/api/rotina");
  if (!data) return;
  const box = $("#rotina-box");
  const completa = data.total > 0 && data.feitos === data.total;
  box.hidden = !rotinaVisivel(data.momento) || data.total === 0 || completa;
  if (box.hidden) return;

  $("#rotina-titulo").textContent = data.momento === "manha" ? "Rotina da manha" : "Rotina da noite";
  $("#rotina-progresso").textContent = `${data.feitos} de ${data.total}`;
  const lista = $("#rotina-lista");
  lista.innerHTML = "";
  data.itens.forEach((item) => {
    const li = criarEl("li", "checklist-item" + (item.feito ? " feito" : ""));
    const label = criarEl("label");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = item.feito;
    cb.addEventListener("change", async () => {
      const r = await apiFetch(`/api/rotina/${item.id}/alternar`, { method: "POST" });
      if (!r) {
        cb.checked = !cb.checked;
        return;
      }
      if (r.feito) vibrar(20);
      loadRotina();
    });
    label.appendChild(cb);
    label.appendChild(criarEl("span", null, item.texto));
    li.appendChild(label);
    lista.appendChild(li);
  });
}

// ---- Check-in de 1 toque ----

const CHECKIN_CAMPOS = [
  ["energia", "Energia"],
  ["sono", "Sono"],
  ["humor", "Humor"],
];

async function loadCheckin() {
  const data = await apiFetch("/api/checkin/hoje");
  if (!data) return;
  const atual = data.checkin || {};
  const completo = CHECKIN_CAMPOS.every(([c]) => atual[c]);
  $("#checkin-box").hidden = completo;
  if (completo) return;

  const linhas = $("#checkin-linhas");
  linhas.innerHTML = "";
  CHECKIN_CAMPOS.forEach(([campo, rotulo]) => {
    const linha = criarEl("div", "checkin-linha");
    linha.appendChild(criarEl("span", "checkin-rotulo", rotulo));
    const opcoes = criarEl("div", "checkin-opcoes");
    ["ruim", "ok", "bom"].forEach((valor) => {
      const b = criarEl("button", "checkin-opcao" + (atual[campo] === valor ? " escolhida" : ""), valor);
      b.type = "button";
      b.dataset.valor = valor;
      b.addEventListener("click", async () => {
        const r = await apiFetch("/api/checkin", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ [campo]: valor }),
        });
        if (r) {
          vibrar(15);
          loadCheckin();
        }
      });
      opcoes.appendChild(b);
    });
    linha.appendChild(opcoes);
    linhas.appendChild(linha);
  });
}

// ---- So o essencial ----

function aplicarModoEssencial(ativo) {
  document.body.classList.toggle("modo-essencial", ativo);
  const btn = $("#essencial-modo-btn");
  btn.setAttribute("aria-pressed", String(ativo));
  btn.textContent = ativo ? "sair do modo foco" : "modo foco no dia";
}

function renderEssencial(tarefas) {
  const lista = $("#essencial-lista");
  lista.innerHTML = "";
  $("#essencial-vazio").hidden = tarefas.length > 0;
  tarefas.forEach((t) => {
    const li = criarEl("li", "essencial-item" + (t.feita ? " feita" : ""));
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = t.feita;
    cb.disabled = t.feita;
    cb.setAttribute("aria-label", `Concluir ${t.title}`);
    cb.addEventListener("change", async () => {
      const r = await apiFetch(`/api/tasks/${t.id}/complete`, { method: "POST" });
      if (!r) {
        cb.checked = false;
        return;
      }
      explodirConcluido(cb);
      vibrar(30);
      tocarSomConcluido();
      loadEssencial();
      loadSummary();
      loadStreak();
    });
    const textos = criarEl("div", "essencial-textos");
    textos.appendChild(criarEl("span", "essencial-titulo", t.title));
    const detalhe = [t.hora ? `as ${t.hora}` : null, t.motivo].filter(Boolean).join(" - ");
    if (detalhe) textos.appendChild(criarEl("span", "essencial-motivo", detalhe));
    li.appendChild(cb);
    li.appendChild(textos);
    if (!t.feita) {
      const trocar = criarEl("button", "btn-link", "trocar");
      trocar.type = "button";
      trocar.setAttribute("aria-label", `Trocar ${t.title} por outra tarefa`);
      trocar.addEventListener("click", async () => {
        trocar.disabled = true;
        const r = await apiFetch("/api/essencial/trocar", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ task_id: t.id }),
        });
        if (r) renderEssencial(r.tarefas);
        else trocar.disabled = false;
      });
      li.appendChild(trocar);
    }
    lista.appendChild(li);
  });
}

async function loadEssencial() {
  const data = await apiFetch("/api/essencial");
  if (!data) return;
  aplicarModoEssencial(data.modo_ativo);
  renderEssencial(data.tarefas);
}

$("#essencial-modo-btn").addEventListener("click", async () => {
  const ativo = !document.body.classList.contains("modo-essencial");
  const r = await apiFetch("/api/essencial/modo", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ativo }),
  });
  if (r) aplicarModoEssencial(r.modo_ativo);
});

// ---- Hiperfoco ----

let hiperfocoAte = null;
let hiperfocoTimer = null;

function atualizarContagemHiperfoco() {
  if (!hiperfocoAte) return;
  const restanteMs = hiperfocoAte - Date.now();
  if (restanteMs <= 0) {
    renderHiperfoco({ ativo: false });
    return;
  }
  const min = Math.ceil(restanteMs / 60000);
  $("#hiperfoco-restante").textContent = `faltam ${min} min`;
}

function renderHiperfoco(estado) {
  const ativo = Boolean(estado && estado.ativo);
  $("#hiperfoco-ativo").hidden = !ativo;
  $("#hiperfoco-inativo").hidden = ativo;
  document.body.classList.toggle("em-hiperfoco", ativo);
  clearInterval(hiperfocoTimer);
  hiperfocoAte = ativo ? new Date(estado.ate).getTime() : null;
  if (ativo) {
    atualizarContagemHiperfoco();
    hiperfocoTimer = setInterval(atualizarContagemHiperfoco, 30000);
  }
}

async function loadHiperfoco() {
  const estado = await apiFetch("/api/hiperfoco");
  if (estado) renderHiperfoco(estado);
}

document.querySelectorAll(".hiperfoco-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const estado = await apiFetch("/api/hiperfoco", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ minutos: Number(btn.dataset.minutos) }),
    });
    if (estado) {
      vibrar(20);
      renderHiperfoco(estado);
    }
  });
});

$("#hiperfoco-parar").addEventListener("click", async () => {
  const estado = await apiFetch("/api/hiperfoco", { method: "DELETE" });
  if (estado) renderHiperfoco(estado);
});

// ---- Pessoas ----

async function loadPessoas() {
  const pessoas = await apiFetch("/api/pessoas");
  if (!pessoas) return;
  const lista = $("#lista-pessoas");
  lista.innerHTML = "";
  $("#pessoas-vazio").hidden = pessoas.length > 0;
  pessoas.forEach((p) => {
    const li = criarEl("li", "item" + (p.atrasada ? " item-atencao" : ""));
    const linha = criarEl("div", "item-linha");
    const wrap = criarEl("div");
    wrap.appendChild(criarEl("span", "item-titulo", p.nome));
    const quando =
      p.dias_sem_falar == null
        ? `a cada ${p.frequencia_dias} dias - sem conversa registrada`
        : p.dias_sem_falar === 0
        ? "falou hoje"
        : `ultima conversa ha ${p.dias_sem_falar} dia(s) - a cada ${p.frequencia_dias}`;
    wrap.appendChild(criarEl("span", "item-quando", quando));
    if (p.ultima_conversa) wrap.appendChild(criarEl("span", "item-quando", `sobre: ${p.ultima_conversa}`));
    linha.appendChild(wrap);

    const acoes = criarEl("div", "item-acoes");
    const falei = criarEl("button", "primario btn-com-icone");
    falei.innerHTML = `${ICONE_CHECK}falei hoje`;
    falei.addEventListener("click", async () => {
      falei.disabled = true;
      const r = await apiFetch(`/api/pessoas/${p.id}/falei`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (r) loadPessoas();
      else falei.disabled = false;
    });
    acoes.appendChild(falei);
    acoes.appendChild(botaoApagar(`/api/pessoas/${p.id}`, li));
    linha.appendChild(acoes);
    li.appendChild(linha);
    lista.appendChild(li);
  });
}

$("#pessoa-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const nome = $("#pessoa-nome").value.trim();
  const freq = $("#pessoa-freq").value.trim();
  if (!nome) return;
  const btn = $("#pessoa-btn");
  setBotaoCarregando(btn, true, "salvando...");
  const r = await apiFetch("/api/pessoas", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nome, frequencia_dias: freq ? Number(freq) : null }),
  });
  setBotaoCarregando(btn, false, "Adicionar");
  if (!r) return;
  $("#pessoa-nome").value = "";
  $("#pessoa-freq").value = "";
  pulsarSucesso($("#pessoa-nome"));
  loadPessoas();
});

// ---- Contas pessoais ----

async function loadContasPessoais() {
  const contas = await apiFetch("/api/contas-pessoais");
  if (!contas) return;
  const lista = $("#lista-contas-pessoais");
  lista.innerHTML = "";
  $("#contas-pessoais-vazio").hidden = contas.length > 0;
  contas.forEach((c) => {
    const urgente = !c.paga && c.dias_ate_vencer <= 3;
    const li = criarEl("li", "item" + (urgente ? " item-atencao" : ""));
    const linha = criarEl("div", "item-linha");
    const wrap = criarEl("div");
    const titulo = c.valor != null ? `${c.nome} - ${fmtMoeda(c.valor)}` : c.nome;
    wrap.appendChild(criarEl("span", "item-titulo", titulo));
    const quando = c.paga
      ? `paga (vencimento ${fmtDataBr(c.proximo_vencimento)})`
      : c.dias_ate_vencer === 0
      ? "vence hoje"
      : `vence ${fmtDataBr(c.proximo_vencimento)} - em ${c.dias_ate_vencer} dia(s)`;
    wrap.appendChild(criarEl("span", "item-quando", quando));
    linha.appendChild(wrap);

    const acoes = criarEl("div", "item-acoes");
    if (!c.paga) {
      const pagar = criarEl("button", "primario btn-com-icone");
      pagar.innerHTML = `${ICONE_CHECK}paga`;
      pagar.addEventListener("click", async () => {
        pagar.disabled = true;
        const r = await apiFetch(`/api/contas-pessoais/${c.id}/paga`, { method: "POST" });
        if (r) loadContasPessoais();
        else pagar.disabled = false;
      });
      acoes.appendChild(pagar);
    }
    acoes.appendChild(botaoApagar(`/api/contas-pessoais/${c.id}`, li));
    linha.appendChild(acoes);
    li.appendChild(linha);
    lista.appendChild(li);
  });
}

$("#conta-pessoal-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const nome = $("#conta-pessoal-nome").value.trim();
  const dia = Number($("#conta-pessoal-dia").value);
  const valorTxt = $("#conta-pessoal-valor").value.trim();
  if (!nome || !(dia >= 1 && dia <= 31)) {
    mostrarErro("Confere o nome e o dia de vencimento (1 a 31).");
    return;
  }
  const btn = $("#conta-pessoal-btn");
  setBotaoCarregando(btn, true, "salvando...");
  const r = await apiFetch("/api/contas-pessoais", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nome, dia_vencimento: dia, valor: valorTxt ? Number(valorTxt) : null }),
  });
  setBotaoCarregando(btn, false, "Adicionar");
  if (!r) return;
  ["#conta-pessoal-nome", "#conta-pessoal-dia", "#conta-pessoal-valor"].forEach((s) => ($(s).value = ""));
  pulsarSucesso($("#conta-pessoal-nome"));
  loadContasPessoais();
});

// ---- Assinaturas: "ainda usa?" ----

async function loadAssinaturasRevisao() {
  const pendentes = await apiFetch("/api/assinaturas/revisao");
  if (!pendentes) return;
  $("#assinaturas-box").hidden = pendentes.length === 0;
  const lista = $("#lista-assinaturas");
  lista.innerHTML = "";
  pendentes.forEach((a) => {
    const li = criarEl("li", "item");
    const linha = criarEl("div", "item-linha");
    const wrap = criarEl("div");
    wrap.appendChild(criarEl("span", "item-titulo", a.descricao));
    wrap.appendChild(criarEl("span", "item-quando", `${fmtMoeda(a.valor)} por mes`));
    linha.appendChild(wrap);
    const acoes = criarEl("div", "item-acoes");
    [
      ["usa", "uso"],
      ["nao_usa", "nao uso mais"],
    ].forEach(([resposta, rotulo]) => {
      const b = criarEl("button", resposta === "usa" ? "btn-com-icone" : "primario btn-com-icone", rotulo);
      b.addEventListener("click", async () => {
        b.disabled = true;
        const r = await apiFetch("/api/assinaturas/revisao", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ descricao: a.descricao, valor: a.valor, resposta }),
        });
        if (!r) {
          b.disabled = false;
          return;
        }
        li.classList.add("saindo");
        setTimeout(() => {
          li.remove();
          if (!$("#lista-assinaturas").children.length) $("#assinaturas-box").hidden = true;
        }, 250);
      });
      acoes.appendChild(b);
    });
    linha.appendChild(acoes);
    li.appendChild(linha);
    lista.appendChild(li);
  });
}

// ---- Vale a pena? ----

const INCLINACAO_TEXTO = { vale: "Inclina pra: vale", nao_vale: "Inclina pra: nao vale", depende: "Depende" };

function renderDecisao(analise) {
  const box = $("#decisao-resultado");
  box.innerHTML = "";
  box.hidden = false;
  if (analise.resumo) box.appendChild(criarEl("p", "decisao-resumo", analise.resumo));
  [
    ["pros", "Pros"],
    ["contras", "Contras"],
    ["perguntas_chave", "O que mudaria a resposta"],
  ].forEach(([chave, rotulo]) => {
    const itens = Array.isArray(analise[chave]) ? analise[chave] : [];
    if (!itens.length) return;
    box.appendChild(criarEl("p", "decisao-rotulo", rotulo));
    const ul = criarEl("ul", "decisao-lista");
    itens.forEach((i) => ul.appendChild(criarEl("li", null, String(i))));
    box.appendChild(ul);
  });
  const inclinacao = INCLINACAO_TEXTO[analise.inclinacao] || null;
  if (inclinacao || analise.porque) {
    box.appendChild(
      criarEl("p", "decisao-veredito", [inclinacao, analise.porque].filter(Boolean).join(" - "))
    );
  }
}

$("#decisao-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const pergunta = $("#decisao-pergunta").value.trim();
  if (!pergunta) return;
  const btn = $("#decisao-btn");
  setBotaoCarregando(btn, true, "pensando...");
  const r = await apiFetch("/api/decisao", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pergunta }),
  });
  setBotaoCarregando(btn, false, "Analisar");
  if (r) renderDecisao(r.analise);
});

// ---- Carga inicial + recarga ao trocar de aba ----

function loadVidaHoje() {
  loadRotina();
  loadCheckin();
  loadEssencial();
  loadHiperfoco();
}

function loadVidaPainel() {
  loadPessoas();
  loadContasPessoais();
  loadAssinaturasRevisao();
}

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.dataset.tab === "hoje") loadVidaHoje();
    if (btn.dataset.tab === "painel") loadVidaPainel();
  });
});

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") loadVidaHoje();
});

loadVidaHoje();
loadVidaPainel();
