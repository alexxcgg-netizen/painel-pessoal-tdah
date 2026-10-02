// static/js/secoes/vida/projetos.js - Secao vida > projetos (HTML: templates/secoes/vida/projetos.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 791-868.
// Fase 7 (V3-organizacao): botao "Novo projeto" abre o formulario num bottom-sheet
// (contrato: docs/agentes/fase7-visual.md). Usa window.abrirBottomSheet/fecharBottomSheet
// (faixa V0d) quando existir; fallback so alterna o atributo hidden do painel.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

function abrirPainelProjeto() {
  const sheet = $("#projeto-sheet");
  if (typeof window.abrirBottomSheet === "function") window.abrirBottomSheet(sheet);
  else sheet.hidden = false;
}

function fecharPainelProjeto() {
  const sheet = $("#projeto-sheet");
  if (typeof window.fecharBottomSheet === "function") window.fecharBottomSheet(sheet);
  else sheet.hidden = true;
}

$("#projeto-abrir-btn").addEventListener("click", abrirPainelProjeto);
$("#projeto-cancelar-btn").addEventListener("click", () => {
  $("#projeto-form").reset();
  fecharPainelProjeto();
});

function renderProjetoBarra(p) {
  const wrap = criarEl("div", "projeto-barra");
  const trilho = criarEl("div", "projeto-barra-trilho");
  const preenchido = criarEl("div", "projeto-barra-preenchido");
  definirProgressoBarra(preenchido, p.percentual);
  trilho.appendChild(preenchido);
  if (p.posicao_hoje != null) {
    const marcador = criarEl("div", "projeto-barra-hoje");
    marcador.style.left = `${p.posicao_hoje}%`;
    marcador.title = "Posição de hoje entre início e prazo";
    trilho.appendChild(marcador);
  }
  wrap.appendChild(trilho);
  return wrap;
}

const STATUS_PROJETO_ROTULO = { no_rumo: "no rumo", atrasado: "atrasado", pausado: "pausado" };

function criarCardProjeto(p, liWrapper) {
  const box = criarEl("div", "card-vida projeto-card card");
  const topo = criarEl("div", "card-vida-topo");
  topo.appendChild(criarEl("h3", null, p.nome));
  topo.appendChild(criarEl("span", `projeto-status projeto-status-${p.status} chip chip--compacto`, STATUS_PROJETO_ROTULO[p.status] || p.status));
  box.appendChild(topo);
  const meta = [`${p.etapas_feitas}/${p.total_etapas} etapas (${p.percentual}%)`];
  if (p.prazo_final) meta.push(`prazo ${fmtDataBr(p.prazo_final)}`);
  box.appendChild(criarEl("p", "card-vida-meta", meta.join(" - ")));
  box.appendChild(renderProjetoBarra(p));
  if (p.proxima_etapa) {
    const linha = criarEl("div", "form-linha");
    linha.appendChild(criarEl("span", "item-quando", `Próxima: ${p.proxima_etapa.texto}`));
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
    const li = criarEl("li", "lista-item");
    li.dataset.entidade = "projeto"; // destino do link de card (Fase 6, US-E7)
    li.dataset.id = p.id;
    li.appendChild(criarCardProjeto(p, li));
    lista.appendChild(li);
  });
}

ligarForm(
  "#projeto-form",
  "#projeto-btn",
  "Salvar projeto",
  () => {
    const nome = $("#projeto-nome").value.trim();
    return nome ? { nome, prazo_final: $("#projeto-prazo").value || null } : null;
  },
  "/api/projetos",
  () => {
    fecharPainelProjeto();
    loadProjetos();
  }
);

// ---- Fase 6 (US-E14): Agenda no calendario "Painel" (CalDAV) ----
