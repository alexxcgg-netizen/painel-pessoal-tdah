// static/js/secoes/vida/pessoas.js - Secao vida > pessoas (HTML: templates/secoes/vida/pessoas.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 263-388.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

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
    const li = criarEl("li", "item lista-item pessoa-item" + (p.atrasada ? " item-atencao" : ""));
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

// Fase 7 V4: botao "Adicionar" abre o formulario num bottom-sheet
// (static/js/ui/bottom-sheet.js, faixa V0d). Enquanto essa faixa nao chega na
// integracao, cai no fallback inline (so hidden) - retestado depois do merge
// com origin/fase7/integracao.
$("#pessoa-abrir-btn").addEventListener("click", () => {
  const sheet = $("#sheet-pessoa");
  if (window.abrirBottomSheet) window.abrirBottomSheet(sheet);
  else sheet.hidden = false;
});

$("#pessoa-cancelar-btn").addEventListener("click", () => {
  $("#pessoa-form").reset();
  const sheet = $("#sheet-pessoa");
  if (window.fecharBottomSheet) window.fecharBottomSheet(sheet);
  else sheet.hidden = true;
});

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
  const sheet = $("#sheet-pessoa");
  if (window.fecharBottomSheet) window.fecharBottomSheet(sheet);
  else sheet.hidden = true;
  pulsarSucesso($("#pessoa-nome"));
  loadPessoas();
});

// ---- Contas pessoais ----
