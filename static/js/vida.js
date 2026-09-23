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

if (typeof FilaOffline !== "undefined") {
  // Assim que um check-in enfileirado sincroniza de verdade, recarrega a
  // caixa pra refletir o estado real vindo do servidor.
  FilaOffline.registrarCallback("checkin", () => loadCheckin());
}

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
        const r = await apiFetch(
          "/api/checkin",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ [campo]: valor }),
          },
          { tipo: "checkin" }
        );
        if (!r) return;
        vibrar(15);
        if (r.__enfileirado) {
          // otimista: marca a opcao escolhida na hora - o checkin e um
          // upsert por dia no servidor, entao reenviar o mesmo valor depois
          // (quando sincronizar) nunca duplica nada.
          opcoes.querySelectorAll(".checkin-opcao").forEach((el) => el.classList.remove("escolhida"));
          b.classList.add("escolhida");
          return;
        }
        loadCheckin();
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
  // Conta a partir dos segundos restantes (vem do servidor) em vez de ler o
  // horario "ate" - o servidor pode estar em outro fuso que o celular.
  hiperfocoAte = ativo ? Date.now() + estado.segundos_restantes * 1000 : null;
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

// Fase 6 US-F3: chip curto de status (some por cima do texto ja existente,
// nao substitui - so da pra escanear a lista de relance sem ler frase por
// frase pra achar quem esta atrasado).
function pessoaChip(p) {
  if (p.dias_sem_falar == null) {
    return p.atrasada ? { texto: "sem conversa ainda", classe: "atrasada" } : { texto: "novo(a)", classe: "novo" };
  }
  if (p.dias_sem_falar === 0) return { texto: "falou hoje", classe: "em-dia" };
  return p.atrasada
    ? { texto: `atrasada ha ${p.dias_sem_falar}d`, classe: "atrasada" }
    : { texto: `ha ${p.dias_sem_falar}d`, classe: "em-dia" };
}

// Toggle "ver conversas" - reusa GET /api/conversas?pessoa_id= (ja existia,
// so nao tinha lugar nenhum na UI que chamasse ele pra uma pessoa so).
async function alternarConversasPessoa(li, pessoaId) {
  const aberto = li.querySelector(".pessoa-conversas");
  if (aberto) {
    aberto.remove();
    return false;
  }
  const conversas = (await apiFetch(`/api/conversas?pessoa_id=${pessoaId}`)) || [];
  const box = criarEl("div", "pessoa-conversas");
  if (!conversas.length) {
    box.appendChild(criarEl("p", "vazio", "Nenhuma conversa registrada ainda."));
  } else {
    const ul = criarEl("ul", "pessoa-conversas-lista");
    conversas.slice(0, 6).forEach((c) => {
      const item = criarEl("li");
      item.appendChild(criarEl("span", "item-quando", fmtDataBr(c.data)));
      item.appendChild(criarEl("span", null, c.sobre || "(sem assunto)"));
      ul.appendChild(item);
    });
    box.appendChild(ul);
  }
  li.appendChild(box);
  return true;
}

async function loadPessoas() {
  const pessoas = await apiFetch("/api/pessoas");
  if (!pessoas) return;
  const lista = $("#lista-pessoas");
  lista.innerHTML = "";
  $("#pessoas-vazio").hidden = pessoas.length > 0;
  pessoas.forEach((p) => {
    const li = criarEl("li", "item pessoa-item" + (p.atrasada ? " item-atencao" : ""));
    const linha = criarEl("div", "item-linha");
    const cabecalho = criarEl("div", "pessoa-cabecalho");

    const avatar = criarEl("div", "pessoa-avatar" + (p.atrasada ? " atrasada" : ""), (p.nome.trim()[0] || "?").toUpperCase());
    cabecalho.appendChild(avatar);

    const wrap = criarEl("div", "pessoa-info");
    const tituloLinha = criarEl("div", "pessoa-titulo-linha");
    tituloLinha.appendChild(criarEl("span", "item-titulo", p.nome));
    const chip = pessoaChip(p);
    tituloLinha.appendChild(criarEl("span", `pessoa-chip pessoa-chip-${chip.classe}`, chip.texto));
    wrap.appendChild(tituloLinha);
    wrap.appendChild(criarEl("span", "item-quando", `contato a cada ${p.frequencia_dias} dia(s)`));
    if (p.ultima_conversa) wrap.appendChild(criarEl("span", "item-quando", `sobre: ${p.ultima_conversa}`));
    if (p.dias_sem_falar != null && p.frequencia_dias > 0) {
      const fracao = Math.min(1, p.dias_sem_falar / p.frequencia_dias);
      const trilho = criarEl("div", "pessoa-barra-trilho");
      const preenchido = criarEl("div", "pessoa-barra-preenchido" + (p.atrasada ? " pessoa-barra-alerta" : ""));
      preenchido.style.width = `${Math.round(fracao * 100)}%`;
      trilho.appendChild(preenchido);
      wrap.appendChild(trilho);
    }
    cabecalho.appendChild(wrap);
    linha.appendChild(cabecalho);

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
      if (r) {
        vibrar(15);
        loadPessoas();
      } else falei.disabled = false;
    });
    acoes.appendChild(falei);

    const verConversas = criarEl("button", "btn-link", "ver conversas");
    verConversas.type = "button";
    verConversas.addEventListener("click", async () => {
      const abriu = await alternarConversasPessoa(li, p.id);
      verConversas.textContent = abriu ? "esconder conversas" : "ver conversas";
    });
    acoes.appendChild(verConversas);

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
      : c.dias_ate_vencer < 0
      ? `venceu ${fmtDataBr(c.proximo_vencimento)} - ha ${-c.dias_ate_vencer} dia(s)`
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

function aplicarModoVisitanteNaDecisao(ativo) {
  $("#decisao-oculto-visitante").hidden = !ativo;
  $("#decisao-form").hidden = ativo;
  if (ativo) $("#decisao-resultado").hidden = true;
}
document.addEventListener("modo-visitante-mudou", (e) => aplicarModoVisitanteNaDecisao(e.detail.ativo));

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

// ---- Fase 2: pra responder ----

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

async function loadResponder() {
  const itens = await apiFetch("/api/responder");
  if (!itens) return;
  const lista = $("#lista-responder");
  lista.innerHTML = "";
  $("#responder-vazio").hidden = itens.length > 0;
  itens.forEach((r) => {
    const quando = r.dias === 0 ? "de hoje" : `ha ${r.dias} dia(s)`;
    lista.appendChild(
      itemSimples(r.quem, [r.sobre, quando], [
        botaoAcao("respondi", async () => {
          const ok = await jsonPost(`/api/responder/${r.id}/feito`);
          if (ok) loadResponder();
          return ok;
        }),
      ], r.dias >= 2 ? "item-atencao" : "")
    );
  });
}

ligarForm("#responder-form", "#responder-btn", "Adicionar", () => {
  const quem = $("#responder-quem").value.trim();
  return quem ? { quem, sobre: $("#responder-sobre").value.trim() } : null;
}, "/api/responder", loadResponder);

// ---- Fase 2: lista de compras ----

async function loadCompras() {
  const itens = await apiFetch("/api/compras");
  if (!itens) return;
  const lista = $("#lista-compras");
  lista.innerHTML = "";
  $("#compras-vazio").hidden = itens.length > 0;
  itens.forEach((c) => {
    const li = criarEl("li", "checklist-item");
    const label = criarEl("label");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.addEventListener("change", async () => {
      const ok = await jsonPost(`/api/compras/${c.id}/comprado`);
      if (!ok) {
        cb.checked = false;
        return;
      }
      li.classList.add("feito", "saindo");
      setTimeout(() => loadCompras(), 250);
    });
    label.appendChild(cb);
    label.appendChild(criarEl("span", null, c.item));
    li.appendChild(label);
    lista.appendChild(li);
  });
}

ligarForm("#compra-form", "#compra-btn", "Adicionar", () => {
  const item = $("#compra-item").value.trim();
  return item ? { itens: [item] } : null;
}, "/api/compras", loadCompras);

// ---- Fase 6 (US-E12): Habitos - NOVO, separado da Rotina guiada (rotina
// manha/noite continua em loadRotina acima) ----

function atualizarCamposFrequenciaHabito() {
  const tipo = $("#habito-frequencia-tipo").value;
  $("#habito-dias-semana-campo").hidden = tipo !== "dias_semana";
  $("#habito-vezes-semana").hidden = tipo !== "n_vezes_semana";
}
$("#habito-frequencia-tipo").addEventListener("change", atualizarCamposFrequenciaHabito);

function renderHabitoSemana(ultimos7) {
  const wrap = criarEl("div", "habito-semana");
  ultimos7.forEach((dia) => {
    const classe = ["habito-circulo", dia.feito ? "feito" : "", dia.hoje ? "hoje" : ""].filter(Boolean).join(" ");
    const c = criarEl("span", classe, dia.letra);
    c.title = fmtDataBr(dia.data);
    wrap.appendChild(c);
  });
  return wrap;
}

async function loadHabitos() {
  const data = await apiFetch("/api/habitos");
  if (!data) return;
  const lista = $("#lista-habitos");
  lista.innerHTML = "";
  $("#habitos-vazio").hidden = data.habitos.length > 0;
  data.habitos.forEach((h) => {
    const detalhes = [h.meta, h.horario ? `lembrete ${h.horario}` : null].filter(Boolean);
    const li = itemSimples(
      h.nome,
      detalhes,
      [
        botaoAcao(
          h.feito_hoje ? "feito hoje" : "marcar hoje",
          async () => {
            const r = await jsonPost(`/api/habitos/${h.id}/marcar`);
            if (r) loadHabitos();
            return r;
          },
          !h.feito_hoje
        ),
        (el) => botaoApagar(`/api/habitos/${h.id}`, el),
      ],
      h.passou_batido ? "item-atencao" : ""
    );
    li.appendChild(renderHabitoSemana(h.ultimos_7));
    li.dataset.entidade = "habito"; // destino do link de card (Fase 6, US-E7)
    li.dataset.id = h.id;
    lista.appendChild(li);
  });
}

ligarForm(
  "#habito-form",
  "#habito-btn",
  "Adicionar",
  () => {
    const nome = $("#habito-nome").value.trim();
    if (!nome) return null;
    const frequencia_tipo = $("#habito-frequencia-tipo").value;
    const corpo = {
      nome,
      meta: $("#habito-meta").value.trim() || null,
      frequencia_tipo,
      horario: $("#habito-horario").value || null,
    };
    if (frequencia_tipo === "dias_semana") {
      corpo.dias_semana = Array.from($("#habito-dias-semana-campo").querySelectorAll("input:checked")).map((c) => Number(c.value));
      if (!corpo.dias_semana.length) {
        mostrarErro("Marca pelo menos um dia da semana.");
        return null;
      }
    } else if (frequencia_tipo === "n_vezes_semana") {
      corpo.vezes_por_semana = Number($("#habito-vezes-semana").value);
      if (!(corpo.vezes_por_semana >= 1 && corpo.vezes_por_semana <= 7)) {
        mostrarErro("Informa quantas vezes por semana (1 a 7).");
        return null;
      }
    }
    return corpo;
  },
  "/api/habitos",
  () => {
    $("#habito-dias-semana-campo")
      .querySelectorAll("input")
      .forEach((c) => (c.checked = false));
    atualizarCamposFrequenciaHabito();
    loadHabitos();
  }
);

// ---- Fase 6 (US-E13): Projetos (generico - Viagens NAO migra pra ca, ver
// loadViagens abaixo; o card de viagem so reaproveita esse mesmo formato
// visual via /api/viagens/<id>/como-projeto quando precisar) ----

function renderProjetoBarra(p) {
  const wrap = criarEl("div", "projeto-barra");
  const trilho = criarEl("div", "projeto-barra-trilho");
  const preenchido = criarEl("div", "projeto-barra-preenchido");
  preenchido.style.width = `${p.percentual}%`;
  trilho.appendChild(preenchido);
  if (p.posicao_hoje != null) {
    const marcador = criarEl("div", "projeto-barra-hoje");
    marcador.style.left = `${p.posicao_hoje}%`;
    marcador.title = "Posicao de hoje entre inicio e prazo";
    trilho.appendChild(marcador);
  }
  wrap.appendChild(trilho);
  return wrap;
}

const STATUS_PROJETO_ROTULO = { no_rumo: "no rumo", atrasado: "atrasado", pausado: "pausado" };

function criarCardProjeto(p, liWrapper) {
  const box = criarEl("div", "card-vida projeto-card");
  const topo = criarEl("div", "card-vida-topo");
  topo.appendChild(criarEl("h3", null, p.nome));
  topo.appendChild(criarEl("span", `projeto-status projeto-status-${p.status}`, STATUS_PROJETO_ROTULO[p.status] || p.status));
  box.appendChild(topo);
  const meta = [`${p.etapas_feitas}/${p.total_etapas} etapas (${p.percentual}%)`];
  if (p.prazo_final) meta.push(`prazo ${fmtDataBr(p.prazo_final)}`);
  box.appendChild(criarEl("p", "card-vida-meta", meta.join(" - ")));
  box.appendChild(renderProjetoBarra(p));
  if (p.proxima_etapa) {
    const linha = criarEl("div", "form-linha");
    linha.appendChild(criarEl("span", "item-quando", `Proxima: ${p.proxima_etapa.texto}`));
    linha.appendChild(
      botaoAcao("concluir", async () => {
        const r = await jsonPost(`/api/projetos/etapas/${p.proxima_etapa.id}/concluir`);
        if (r) loadProjetos();
        return r;
      })
    );
    box.appendChild(linha);
  }
  if (p.dias_sem_toque != null && p.dias_sem_toque >= 7) {
    box.appendChild(criarEl("p", "vazio", `${p.dias_sem_toque} dias sem toque.`));
  }
  const rodape = criarEl("div", "item-acoes");
  rodape.appendChild(botaoApagar(`/api/projetos/${p.id}`, liWrapper));
  box.appendChild(rodape);
  return box;
}

async function loadProjetos() {
  const projetos = await apiFetch("/api/projetos");
  if (!projetos) return;
  const lista = $("#lista-projetos");
  lista.innerHTML = "";
  $("#projetos-vazio").hidden = projetos.length > 0;
  projetos.forEach((p) => {
    const li = criarEl("li");
    li.dataset.entidade = "projeto"; // destino do link de card (Fase 6, US-E7)
    li.dataset.id = p.id;
    li.appendChild(criarCardProjeto(p, li));
    lista.appendChild(li);
  });
}

ligarForm(
  "#projeto-form",
  "#projeto-btn",
  "Adicionar",
  () => {
    const nome = $("#projeto-nome").value.trim();
    return nome ? { nome, prazo_final: $("#projeto-prazo").value || null } : null;
  },
  "/api/projetos",
  loadProjetos
);

// ---- Fase 6 (US-E14): Agenda no calendario "Painel" (CalDAV) ----

async function loadEventosCriados() {
  const eventos = await apiFetch("/api/agenda/eventos-criados");
  if (!eventos) return;
  const lista = $("#lista-eventos-criados");
  lista.innerHTML = "";
  $("#eventos-criados-vazio").hidden = eventos.length > 0;
  eventos.forEach((e) => {
    lista.appendChild(
      itemSimples(e.titulo, [`${fmtDataBr(e.inicio.slice(0, 10))} ${e.inicio.slice(11, 16)}-${e.fim.slice(11, 16)}`], [
        (el) => botaoApagar(`/api/agenda/eventos/${e.uid}`, el),
      ])
    );
  });
}

ligarForm(
  "#evento-form",
  "#evento-btn",
  "Criar evento",
  () => {
    const titulo = $("#evento-titulo").value.trim();
    const data = $("#evento-data").value;
    const hora_inicio = $("#evento-hora-inicio").value;
    const hora_fim = $("#evento-hora-fim").value;
    if (!titulo || !data || !hora_inicio || !hora_fim) return null;
    const corpo = { titulo, data, hora_inicio, hora_fim };
    const lembrar = $("#evento-lembrar").value;
    if (lembrar !== "") corpo.lembrar_min_antes = Number(lembrar);
    return corpo;
  },
  "/api/agenda/eventos",
  loadEventosCriados
);

// ---- Fase 2: treino ----

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
    loadTreino(r);
  }
);

// ---- Fase 2 + Fase 5 (US-C14) + Fase 6 (US-E1a): manutencao (secao unica) ----
// tipo='carro' e HISTORICO (registro novo a cada manutencao feita, aviso por
// km/data, sem botao "feita hoje"); os demais tipos (casa/equipamento/outro)
// sao EDICAO NO LUGAR (um item so, "feita hoje" atualiza a data), igual
// sempre foi antes da unificacao das duas secoes.

const ROTULO_TIPO_MANUTENCAO = { casa: "Casa", carro: "Carro", equipamento: "Equipamento", outro: "Outro" };

function textoProximaManutencaoCarro(m) {
  const partes = [];
  if (m.km != null) partes.push(`${m.km} km na hora`);
  if (m.proxima_em_km != null) partes.push(`proxima em ${m.proxima_em_km} km`);
  if (m.proxima_em_data) partes.push(`proxima em ${fmtDataBr(m.proxima_em_data)}`);
  return partes;
}

async function loadManutencoes() {
  const itens = await apiFetch("/api/manutencoes");
  if (!itens) return;
  const lista = $("#lista-manutencoes");
  lista.innerHTML = "";
  $("#manutencoes-vazio").hidden = itens.length > 0;
  itens.forEach((m) => {
    const rotuloTipo = ROTULO_TIPO_MANUTENCAO[m.tipo] || "Outro";
    if (m.tipo === "carro") {
      lista.appendChild(
        itemSimples(
          m.item,
          [rotuloTipo, fmtDataBr(m.data), ...textoProximaManutencaoCarro(m)],
          [(el) => botaoApagar(`/api/manutencoes/${m.id}`, el)]
        )
      );
      return;
    }
    const quando =
      m.dias_ate < 0
        ? `passou do prazo ha ${-m.dias_ate} dia(s)`
        : m.dias_ate === 0
        ? "vence hoje"
        : `proxima em ${fmtDataBr(m.proxima)} (${m.dias_ate} dias)`;
    lista.appendChild(
      itemSimples(m.item, [rotuloTipo, `a cada ${m.intervalo_meses} mes(es)`, quando], [
        botaoAcao("feita hoje", async () => {
          const ok = await jsonPost(`/api/manutencoes/${m.id}/feita`);
          if (ok) loadManutencoes();
          return ok;
        }),
        (el) => botaoApagar(`/api/manutencoes/${m.id}`, el),
      ], m.dias_ate <= 7 ? "item-atencao" : "")
    );
  });
}

$("#manutencao-tipo").addEventListener("change", () => {
  const carro = $("#manutencao-tipo").value === "carro";
  $("#manutencao-campos-carro").hidden = !carro;
  $("#manutencao-campos-tempo").hidden = carro;
});

ligarForm("#manutencao-form", "#manutencao-btn", "Adicionar", () => {
  const tipo = $("#manutencao-tipo").value;
  const item = $("#manutencao-item").value.trim();
  if (!item) {
    mostrarErro("Confere o item.");
    return null;
  }
  if (tipo === "carro") {
    const data = $("#manutencao-data").value;
    if (!data) {
      mostrarErro("Confere a data.");
      return null;
    }
    const km = $("#manutencao-km").value;
    const proximaKm = $("#manutencao-proxima-km").value;
    return {
      tipo, item, data,
      km: km === "" ? null : Number(km),
      proxima_em_km: proximaKm === "" ? null : Number(proximaKm),
      proxima_em_data: $("#manutencao-proxima-data").value || null,
    };
  }
  const meses = Number($("#manutencao-meses").value);
  if (!(meses >= 1 && meses <= 120)) {
    mostrarErro("Confere o intervalo (1 a 120 meses).");
    return null;
  }
  return { tipo, item, intervalo_meses: meses, ultima_vez: $("#manutencao-ultima").value || null };
}, "/api/manutencoes", loadManutencoes);

// ---- Fase 5 + Fase 6 (US-F5): garantia de produtos ----

// Chip curto de status - a mesma logica de "<=15 dias = atencao" que ja
// existia (classe item-atencao), so com um rotulo mais claro que "vence em
// (X dias)" no meio da frase.
function garantiaChip(g) {
  if (g.dias_ate < 0) return { texto: `venceu ha ${-g.dias_ate}d`, classe: "vencida" };
  if (g.dias_ate === 0) return { texto: "vence hoje", classe: "vencida" };
  if (g.dias_ate <= 15) return { texto: `vence em ${g.dias_ate}d`, classe: "alerta" };
  return { texto: `vence em ${g.dias_ate}d`, classe: "ok" };
}

// Fracao do prazo de garantia ja decorrida (0..1) - so matematica de data
// local, sem endpoint novo (data_compra/vencimento ja vinham no /api/garantias).
function garantiaFracaoDecorrida(g) {
  const compra = new Date(`${g.data_compra}T00:00:00`).getTime();
  const vence = new Date(`${g.vencimento}T00:00:00`).getTime();
  if (!(vence > compra)) return 1;
  return Math.min(1, Math.max(0, (Date.now() - compra) / (vence - compra)));
}

async function loadGarantias() {
  const itens = await apiFetch("/api/garantias");
  if (!itens) return;
  const lista = $("#lista-garantias");
  lista.innerHTML = "";
  $("#garantias-vazio").hidden = itens.length > 0;
  // O que vence mais logo primeiro (inclusive ja vencido) - "destaque do que
  // vence logo" e o pedido explicito da US-F5, a ordem por data de compra
  // que a API devolve nao ajuda a bater o olho nisso.
  itens
    .slice()
    .sort((a, b) => a.dias_ate - b.dias_ate)
    .forEach((g) => {
      const li = criarEl("li", "item garantia-item" + (g.dias_ate <= 15 ? " item-atencao" : ""));
      const linha = criarEl("div", "item-linha");

      const wrap = criarEl("div");
      const tituloLinha = criarEl("div", "pessoa-titulo-linha");
      tituloLinha.appendChild(criarEl("span", "item-titulo", g.produto));
      const chip = garantiaChip(g);
      tituloLinha.appendChild(criarEl("span", `garantia-chip garantia-chip-${chip.classe}`, chip.texto));
      wrap.appendChild(tituloLinha);
      wrap.appendChild(
        criarEl(
          "span",
          "item-quando",
          `${g.prazo_garantia_meses} mes(es) - comprado em ${fmtDataBr(g.data_compra)}, vence ${fmtDataBr(g.vencimento)}`
        )
      );
      const trilho = criarEl("div", "garantia-barra-trilho");
      const preenchido = criarEl("div", `garantia-barra-preenchido garantia-barra-${chip.classe}`);
      preenchido.style.width = `${Math.round(garantiaFracaoDecorrida(g) * 100)}%`;
      trilho.appendChild(preenchido);
      wrap.appendChild(trilho);
      linha.appendChild(wrap);

      const acoes = criarEl("div", "item-acoes");
      acoes.appendChild(botaoApagar(`/api/garantias/${g.id}`, li));
      linha.appendChild(acoes);

      li.appendChild(linha);
      lista.appendChild(li);
    });
}

$("#garantia-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const produto = $("#garantia-produto").value.trim();
  const dataCompra = $("#garantia-data-compra").value;
  const prazo = Number($("#garantia-prazo").value);
  if (!produto || !dataCompra || !(prazo >= 1 && prazo <= 600)) {
    mostrarErro("Confere o produto, a data de compra e o prazo de garantia.");
    return;
  }
  const arquivo = $("#garantia-anexo").files[0];
  const btn = $("#garantia-btn");
  setBotaoCarregando(btn, true, "salvando...");
  const form = new FormData();
  form.append("produto", produto);
  form.append("data_compra", dataCompra);
  form.append("prazo_garantia_meses", String(prazo));
  if (arquivo) form.append("nota_fiscal", arquivo);
  const r = await apiFetch("/api/garantias", { method: "POST", body: form });
  setBotaoCarregando(btn, false, "Adicionar");
  if (!r) return;
  $("#garantia-form").reset();
  pulsarSucesso($("#garantia-produto"));
  loadGarantias();
});

// ---- Fase 2: viagens e lugares ----

function renderItensMala(v, li) {
  const antigo = li.querySelector(".mala");
  if (antigo) antigo.remove();
  if (!v.itens.length) return;
  const ul = criarEl("ul", "checklist mala");
  v.itens.forEach((item) => {
    const itemLi = criarEl("li", "checklist-item" + (item.feito ? " feito" : ""));
    const label = criarEl("label");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = Boolean(item.feito);
    cb.addEventListener("change", async () => {
      const r = await jsonPost(`/api/viagens/itens/${item.id}/alternar`);
      if (!r) {
        cb.checked = !cb.checked;
        return;
      }
      itemLi.classList.toggle("feito", r.feito);
    });
    label.appendChild(cb);
    label.appendChild(criarEl("span", null, item.texto));
    itemLi.appendChild(label);
    ul.appendChild(itemLi);
  });
  li.appendChild(ul);
}

async function loadViagens() {
  const viagens = await apiFetch("/api/viagens");
  if (!viagens) return;
  const lista = $("#lista-viagens");
  lista.innerHTML = "";
  $("#viagens-vazio").hidden = viagens.length > 0;
  viagens.forEach((v) => {
    const datas = v.data_volta ? `${fmtDataBr(v.data_ida)} a ${fmtDataBr(v.data_volta)}` : fmtDataBr(v.data_ida);
    const quando = v.dias_ate > 0 ? `em ${v.dias_ate} dia(s)` : v.dias_ate === 0 ? "hoje" : "em andamento";
    const lugares = v.lugares.length ? `voce curtiu la: ${v.lugares.map((l) => l.nome).join(", ")}` : null;
    const malaBtn = criarEl("button", "btn-com-icone", v.itens.length ? "refazer mala" : "montar mala");
    let li;
    malaBtn.addEventListener("click", async () => {
      setBotaoCarregando(malaBtn, true, "pensando...");
      const r = await jsonPost(`/api/viagens/${v.id}/mala`);
      setBotaoCarregando(malaBtn, false, "refazer mala");
      if (r) renderItensMala(r, li);
    });
    li = itemSimples(v.destino, [`${datas} - ${quando}`, lugares], [malaBtn, (el) => botaoApagar(`/api/viagens/${v.id}`, el)]);
    renderItensMala(v, li);
    li.dataset.entidade = "viagem"; // destino do link de card (Fase 6, US-E7)
    li.dataset.id = v.id;
    lista.appendChild(li);
  });
}

ligarForm("#viagem-nova-form", "#viagem-nova-btn", "Adicionar", () => {
  const destino = $("#viagem-nova-destino").value.trim();
  const ida = $("#viagem-nova-ida").value;
  return destino && ida ? { destino, data_ida: ida, data_volta: $("#viagem-nova-volta").value || null } : null;
}, "/api/viagens", loadViagens);

async function loadLugares() {
  const lugares = await apiFetch("/api/lugares");
  if (!lugares) return;
  const lista = $("#lista-lugares");
  lista.innerHTML = "";
  $("#lugares-vazio").hidden = lugares.length > 0;
  lugares.forEach((l) => {
    lista.appendChild(
      itemSimples(l.nome, [[l.tipo, l.cidade].filter(Boolean).join(" - "), l.nota], [
        (el) => botaoApagar(`/api/lugares/${l.id}`, el),
      ])
    );
  });
}

ligarForm("#lugar-form", "#lugar-btn", "Adicionar", () => {
  const nome = $("#lugar-nome").value.trim();
  return nome ? { nome, cidade: $("#lugar-cidade").value.trim() } : null;
}, "/api/lugares", loadLugares);

// ---- Fase 5: ideias de presente ----

async function loadIdeiasPresente() {
  const itens = await apiFetch("/api/ideias-presente");
  if (!itens) return;
  const lista = $("#lista-ideias-presente");
  lista.innerHTML = "";
  $("#ideias-presente-vazio").hidden = itens.length > 0;
  itens.forEach((i) => {
    const btnComprado = criarEl("button", "btn-com-icone" + (i.comprado ? " primario" : ""));
    btnComprado.textContent = i.comprado ? "comprado" : "marcar comprado";
    btnComprado.addEventListener("click", async () => {
      btnComprado.disabled = true;
      const r = await jsonPost(`/api/ideias-presente/${i.id}/comprado`);
      if (r) loadIdeiasPresente();
      else btnComprado.disabled = false;
    });
    lista.appendChild(
      itemSimples(`${i.pessoa}: ${i.ideia}`, [i.ocasiao], [btnComprado, (el) => botaoApagar(`/api/ideias-presente/${i.id}`, el)])
    );
  });
}

ligarForm("#ideia-presente-form", "#ideia-presente-btn", "Adicionar", () => {
  const pessoa = $("#ideia-presente-pessoa").value.trim();
  const ideia = $("#ideia-presente-ideia").value.trim();
  if (!pessoa || !ideia) {
    mostrarErro("Confere pra quem e a ideia de presente.");
    return null;
  }
  return { pessoa, ideia, ocasiao: $("#ideia-presente-ocasiao").value.trim() || null };
}, "/api/ideias-presente", loadIdeiasPresente);

// ---- Fase 2: mensagem dificil ----

$("#mensagem-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const situacao = $("#mensagem-situacao").value.trim();
  if (!situacao) return;
  const btn = $("#mensagem-btn");
  setBotaoCarregando(btn, true, "escrevendo...");
  const r = await jsonPost("/api/mensagem-dificil", { situacao, para_quem: $("#mensagem-para").value.trim() });
  setBotaoCarregando(btn, false, "Escrever pra mim");
  if (!r) return;
  const box = $("#mensagem-resultado");
  box.innerHTML = "";
  box.hidden = false;
  [
    ["direta", "Direta"],
    ["gentil", "Mais gentil"],
  ].forEach(([chave, rotulo]) => {
    box.appendChild(criarEl("p", "decisao-rotulo", rotulo));
    box.appendChild(criarEl("p", "mensagem-texto", r[chave]));
    const copiar = criarEl("button", "btn-link", "copiar");
    copiar.type = "button";
    copiar.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(r[chave]);
        copiar.textContent = "copiado";
      } catch {
        copiar.textContent = "nao deu pra copiar - segura no texto";
      }
    });
    box.appendChild(copiar);
  });
});

// ---- Fase 3: quero aprender ----

async function loadAprender() {
  const itens = await apiFetch("/api/aprender");
  if (!itens) return;
  const lista = $("#lista-aprender");
  lista.innerHTML = "";
  $("#aprender-vazio").hidden = itens.length > 0;
  itens.forEach((a) => {
    const parado =
      a.dias_parado > 0 ? `parado ha ${a.dias_parado} dia(s)` : a.ultima_vez ? "mexeu hoje" : "adicionado hoje";
    lista.appendChild(
      itemSimples(a.tema, [a.nota, parado], [
        botaoAcao("mexi hoje", async () => {
          const ok = await jsonPost(`/api/aprender/${a.id}/retomei`);
          if (ok) loadAprender();
          return ok;
        }),
        botaoAcao("aprendi", async () => {
          const ok = await jsonPost(`/api/aprender/${a.id}/concluido`);
          if (ok) loadAprender();
          return ok;
        }, false),
      ], a.dias_parado >= 14 ? "item-atencao" : "")
    );
  });
}

ligarForm("#aprender-form", "#aprender-btn", "Adicionar", () => {
  const tema = $("#aprender-tema").value.trim();
  return tema ? { tema } : null;
}, "/api/aprender", loadAprender);

// ---- Fase 3: links salvos ----

async function loadSalvos() {
  const itens = await apiFetch("/api/salvos");
  if (!itens) return;
  const lista = $("#lista-salvos");
  lista.innerHTML = "";
  $("#salvos-vazio").hidden = itens.length > 0;
  itens.forEach((sv) => {
    const acoes = [];
    if (!sv.lido_em) {
      acoes.push(
        botaoAcao("vi", async () => {
          const ok = await jsonPost(`/api/salvos/${sv.id}/lido`);
          if (ok) loadSalvos();
          return ok;
        })
      );
    }
    acoes.push((el) => botaoApagar(`/api/salvos/${sv.id}`, el));
    const li = itemSimples(sv.titulo || sv.url, [], acoes, sv.lido_em ? "lido" : "");
    let host = sv.url;
    try {
      host = new URL(sv.url).hostname.replace(/^www\./, "");
    } catch (_) {}
    const link = criarEl("a", "salvo-link", sv.titulo ? host : sv.url);
    link.href = sv.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    li.querySelector(".item-linha > div").appendChild(link);
    if (sv.resumo) li.appendChild(criarEl("p", "salvo-resumo", sv.resumo));
    lista.appendChild(li);
  });
}

$("#salvo-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const url = $("#salvo-url").value.trim();
  if (!url) return;
  const btn = $("#salvo-btn");
  setBotaoCarregando(btn, true, "lendo...");
  const r = await jsonPost("/api/salvos", { url });
  setBotaoCarregando(btn, false, "Salvar e resumir");
  if (!r) return;
  $("#salvo-url").value = "";
  if (r.aviso) mostrarErro(r.aviso);
  loadSalvos();
});

// ---- Fase 3: progresso, revisao do mes e uso do celular ----

async function loadProgresso() {
  const p = await apiFetch("/api/progresso?dias=30");
  if (p) {
    const grid = $("#progresso-grid");
    grid.innerHTML = "";
    [
      [p.tarefas_feitas, "tarefas feitas"],
      [`${p.rotina_manha_dias}/${p.dias}`, "dias com rotina da manha"],
      [p.treinos_por_semana, "treinos por semana"],
      [p.copos_por_dia, "copos de agua por dia"],
      [p.sono_medio != null ? `${p.sono_medio}h` : "-", "sono medio"],
      [p.humor_medio || "-", "humor na media"],
    ].forEach(([valor, rotulo]) => {
      const item = criarEl("div", "progresso-item");
      item.appendChild(criarEl("span", "progresso-valor", String(valor)));
      item.appendChild(criarEl("span", "progresso-rotulo", rotulo));
      grid.appendChild(item);
    });
    const metas = $("#progresso-metas");
    metas.innerHTML = "";
    p.metas.forEach((m) => metas.appendChild(criarEl("li", null, `${m.titulo}: ${m.pct}%`)));
  }
  const revisao = await apiFetch("/api/revisao-mensal");
  const revEl = $("#revisao-mes");
  revEl.hidden = !revisao;
  if (revisao) revEl.textContent = revisao.texto;

  const uso = await apiFetch("/api/uso-apps?dias=7");
  $("#uso-apps-box").hidden = !uso || !uso.apps.length;
  if (uso && uso.apps.length) {
    const lista = $("#lista-uso-apps");
    lista.innerHTML = "";
    uso.apps.forEach((a) => {
      const li = criarEl("li");
      li.appendChild(criarEl("span", null, a.app));
      li.appendChild(criarEl("span", "progresso-rotulo", a.texto));
      lista.appendChild(li);
    });
  }
}

// ---- Fase 3: fim do mes (aba Gastos) ----

async function loadFimMes() {
  const s = await apiFetch("/api/sobra-do-mes");
  if (!s || !s.projecao) return;
  const semDado = !s.renda_mes && !s.gasto_mes;
  $("#fim-mes-box").hidden = semDado;
  if (semDado) return;
  const p = s.projecao;
  $("#fim-mes-dias").textContent = `faltam ${p.dias_restantes} dia(s)`;
  $("#fim-mes-agora").textContent = `Agora: ${fmtMoeda(s.renda_mes)} entrou, ${fmtMoeda(s.gasto_mes)} saiu - sobra ${fmtMoeda(s.sobra)}.`;
  const contas = p.contas_pendentes ? ` (com ${fmtMoeda(p.contas_pendentes)} de contas que ainda vencem)` : "";
  $("#fim-mes-projecao").textContent = `No ritmo de ${fmtMoeda(p.ritmo_diario)}/dia, deve sobrar ${fmtMoeda(p.sobra_projetada)} no fim do mes${contas}.`;
}

// ---- Fase 5 (US-C22): sinal de sobrecarga ----

const SINAL_TEXTO = { "tarefas atrasadas": "tarefas atrasadas", "sono ruim": "sono ruim seguido", "semana pesada": "semana cheia pela frente" };

async function loadSobrecarga() {
  const data = await apiFetch("/api/sobrecarga");
  if (!data) return;
  const box = $("#sobrecarga-box");
  box.hidden = !data.sobrecarregado;
  if (!data.sobrecarregado) return;
  $("#sobrecarga-pontuacao").textContent = `${data.pontuacao}/3 sinais`;
  const lista = data.sinais.map((s) => SINAL_TEXTO[s] || s).join(", ");
  $("#sobrecarga-texto").textContent = `Varios sinais juntos: ${lista}. Talvez valha desacelerar hoje.`;
}

// ---- Fase 5 (US-C21): previa da noite anterior ----

async function loadPreviaNoite() {
  const data = await apiFetch("/api/previa-noite");
  if (!data) return;
  const box = $("#previa-noite-box");
  const oculto = $("#previa-noite-oculto");
  const texto = $("#previa-noite-texto");

  if (data.oculto) {
    box.hidden = false;
    oculto.hidden = false;
    texto.hidden = true;
    $("#previa-noite-data").textContent = "";
    return;
  }
  oculto.hidden = true;
  texto.hidden = false;

  const partes = [];
  if (data.sono_horas != null) partes.push(`dormiu ${data.sono_horas.toFixed(1)}h`);
  else if (data.sono_checkin != null) partes.push(`marcou o sono como ${data.sono_checkin}/5`);
  if (data.copos_agua) partes.push(`${data.copos_agua} copo(s) de agua`);
  if (data.medicamentos_total > 0) {
    partes.push(`remedio: ${data.medicamentos_tomados}/${data.medicamentos_total} tomado(s)`);
  }

  box.hidden = partes.length === 0;
  if (partes.length === 0) return;
  $("#previa-noite-data").textContent = fmtDataBr(data.data);
  texto.textContent = partes.join(" - ") + ".";
}

// ---- Carga inicial + recarga ao trocar de aba ----

function loadVidaHoje() {
  loadSobrecarga();
  loadPreviaNoite();
  loadRotina();
  loadCheckin();
  loadEssencial();
  loadHiperfoco();
}

function loadVidaAba() {
  loadHabitos();
  loadProjetos();
  loadEventosCriados();
  loadResponder();
  loadCompras();
  loadPessoas();
  loadTreino();
  loadContasPessoais();
  loadAssinaturasRevisao();
  loadManutencoes();
  loadGarantias();
  loadViagens();
  loadLugares();
  loadIdeiasPresente();
  loadAprender();
  loadSalvos();
  loadProgresso();
}

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.dataset.tab === "hoje") loadVidaHoje();
    if (btn.dataset.tab === "vida") loadVidaAba();
    if (btn.dataset.tab === "gastos") loadFimMes();
  });
});

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") loadVidaHoje();
});

loadVidaHoje();
