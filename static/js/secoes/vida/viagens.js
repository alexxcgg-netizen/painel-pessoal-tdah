// static/js/secoes/vida/viagens.js - Secao vida > viagens (HTML: templates/secoes/vida/viagens.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 1263-1419.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

function renderItensMala(v, li) {
  const antigo = li.querySelector(".mala");
  if (antigo) antigo.remove();
  if (!Array.isArray(v.itens) || !v.itens.length) return;
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

// US-F11: card projeto_viagem completo (progresso + linha do tempo de
// planejamento) - vem pronto de /timeline-card (cards.card_viagem), o front
// so pede pra renderizar (Cards.renderizarCardHTML), nunca recalcula nada.
async function renderTimelineViagem(viagemId, container) {
  const card = await apiFetch(`/api/viagens/${viagemId}/timeline-card`);
  if (!card || !container.isConnected) return;
  container.innerHTML = Cards.renderizarCardHTML(card, { agora: new Date() });
}

// US-F12: status de voo em tempo real por numero (atraso, portao, terminal) -
// ver voo_status.py. Sem VOO_STATUS_API_KEY configurada no servidor, a rota
// devolve configurado=false e a tela mostra "configure a chave" sem quebrar.
function criarBlocoVoo(v, li) {
  const box = criarEl("div", "viagem-voo-box");
  const form = criarEl("form", "form-linha viagem-voo-form");
  const input = document.createElement("input");
  input.type = "text";
  input.className = "campo";
  input.placeholder = "Numero do voo (ex: LA3251)";
  input.maxLength = 12;
  input.value = v.numero_voo || "";
  input.setAttribute("aria-label", `Numero do voo da viagem para ${v.destino}`);
  const salvarBtn = criarEl("button", "btn btn-secundario", v.numero_voo ? "Atualizar" : "Salvar");
  salvarBtn.type = "submit";
  form.appendChild(input);
  form.appendChild(salvarBtn);
  const status = criarEl("div", "viagem-voo-status");
  box.appendChild(form);
  box.appendChild(status);

  async function carregarStatus() {
    if (!v.numero_voo) {
      status.innerHTML = "";
      return;
    }
    status.innerHTML = `<p class="card-linha-meta">consultando...</p>`;
    const r = await apiFetch(`/api/viagens/${v.id}/voo-status`);
    if (!r) {
      status.innerHTML = "";
      return;
    }
    status.innerHTML = "";
    status.appendChild(criarStatusVooEl(r));
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    setBotaoCarregando(salvarBtn, true, "salvando...");
    const r = await apiFetch(`/api/viagens/${v.id}/numero-voo`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ numero_voo: input.value.trim() }),
    });
    setBotaoCarregando(salvarBtn, false, v.numero_voo ? "Atualizar" : "Salvar");
    if (!r) return;
    v.numero_voo = r.numero_voo;
    salvarBtn.textContent = v.numero_voo ? "Atualizar" : "Salvar";
    carregarStatus();
  });

  carregarStatus();
  return box;
}

function criarStatusVooEl(r) {
  const box = criarEl("div", "voo-status-card");
  if (!r.configurado) {
    box.appendChild(criarEl("p", "card-linha-meta voo-status-aviso", "status em tempo real: configurar chave"));
    return box;
  }
  if (r.erro) {
    box.appendChild(criarEl("p", "card-linha-meta voo-status-aviso", r.erro));
    return box;
  }
  const linha1 = criarEl("p", "voo-status-linha-principal");
  const situacao = criarEl("span", `voo-status-chip voo-status-${r.status || "desconhecido"}`, r.status_texto || "sem dado");
  linha1.appendChild(situacao);
  if (r.atraso_min) linha1.appendChild(criarEl("span", "card-linha-meta", ` atraso de ${r.atraso_min} min`));
  box.appendChild(linha1);
  const detalhes = [
    r.portao ? `Portao ${r.portao}` : null,
    r.terminal ? `Terminal ${r.terminal}` : null,
    r.horario_partida_real ? `Partida real ${r.horario_partida_real}` : r.horario_partida_previsto ? `Partida prevista ${r.horario_partida_previsto}` : null,
  ].filter(Boolean);
  if (detalhes.length) box.appendChild(criarEl("p", "card-linha-meta", detalhes.join(" · ")));
  if (r.cache) box.appendChild(criarEl("p", "card-linha-meta voo-status-cache", `dado de ${r.buscado_em_texto || "cache recente"}`));
  // Plano gratis da AviationStack e so HTTP (o dado pode ser alterado no
  // caminho) - so exibicao, nunca decisao automatica (revisao da Fase 6).
  box.appendChild(criarEl("p", "card-linha-meta voo-status-confirmar", "Confirme no app da companhia."));
  return box;
}

async function loadViagens() {
  const viagens = await apiFetch("/api/viagens");
  if (!Array.isArray(viagens)) return; // null (erro ja mostrado) ou resposta fora do formato
  const lista = $("#lista-viagens");
  lista.innerHTML = "";
  $("#viagens-vazio").hidden = viagens.length > 0;
  viagens.forEach((v) => {
    const datas = v.data_volta ? `${fmtDataBr(v.data_ida)} a ${fmtDataBr(v.data_volta)}` : fmtDataBr(v.data_ida);
    const quando = v.dias_ate > 0 ? `em ${v.dias_ate} dia(s)` : v.dias_ate === 0 ? "hoje" : "em andamento";
    v.itens = Array.isArray(v.itens) ? v.itens : [];
    const lugaresV = Array.isArray(v.lugares) ? v.lugares : [];
    const lugares = lugaresV.length ? `voce curtiu la: ${lugaresV.map((l) => l.nome).join(", ")}` : null;
    const tipoViagem = v.internacional ? "internacional" : "nacional";
    const malaBtn = criarEl("button", "btn-com-icone", v.itens.length ? "refazer mala" : "montar mala");
    let li;
    malaBtn.addEventListener("click", async () => {
      setBotaoCarregando(malaBtn, true, "pensando...");
      const r = await jsonPost(`/api/viagens/${v.id}/mala`);
      setBotaoCarregando(malaBtn, false, "refazer mala");
      if (r) renderItensMala(r, li);
    });
    li = itemSimples(v.destino, [`${datas} - ${quando} - viagem ${tipoViagem}`, lugares], [malaBtn, (el) => botaoApagar(`/api/viagens/${v.id}`, el)]);
    renderItensMala(v, li);
    li.appendChild(criarBlocoVoo(v, li));
    const timelineBox = criarEl("div", "viagem-timeline-box");
    li.appendChild(timelineBox);
    renderTimelineViagem(v.id, timelineBox);
    li.dataset.entidade = "viagem"; // destino do link de card (Fase 6, US-E7)
    li.dataset.id = v.id;
    lista.appendChild(li);
  });
}

// Fase 7 (V5-extra/C3b): "Nova viagem" abre o formulario no bottom-sheet
// compartilhado (static/js/ui/bottom-sheet.js, V0d - ESC, toque fora, foco
// preso e devolvido ficam todos la). Fallback so pro caso de o componente
// nao ter carregado: alterna o atributo hidden.
// A aba (.tab-content) entra com `animation: ... both`, que deixa um `transform`
// no fim - e todo ancestral com transform vira o bloco de contencao de um
// `position: fixed`. Resultado: o sheet cobria a ABA inteira (milhares de px)
// em vez da tela, e o painel abria longe da borda de baixo. Enquanto isso nao
// e corrigido no style.css/bottom-sheet.js (anotado no progress da C3b), os
// sheets da faixa C3b vao pro <body> na primeira abertura (idempotente).
function levarSheetProBody(sheet) {
  if (sheet && document.body && sheet.parentElement !== document.body) document.body.appendChild(sheet);
}

function abrirPainelViagem() {
  const sheet = $("#viagem-sheet");
  levarSheetProBody(sheet);
  if (typeof window.abrirBottomSheet === "function") window.abrirBottomSheet(sheet);
  else sheet.hidden = false;
}

function fecharPainelViagem() {
  const sheet = $("#viagem-sheet");
  if (typeof window.fecharBottomSheet === "function") window.fecharBottomSheet(sheet);
  else sheet.hidden = true;
}

$("#viagem-abrir-btn").addEventListener("click", abrirPainelViagem);
$("#viagem-cancelar-btn").addEventListener("click", () => {
  $("#viagem-nova-form").reset();
  fecharPainelViagem();
});

// Card de viagem no chat (Fase 6, US-E7) destaca o <li> via cards.js
// (classe .item-destacado). Com a secao recolhida o <li> esta escondido e o
// destaque nao aparece - entao reabre a secao quando isso acontece.
function abrirSecaoSeDestacado(listaSel) {
  const lista = $(listaSel);
  if (!lista || typeof MutationObserver === "undefined") return;
  new MutationObserver((mutacoes) => {
    const destacado = mutacoes.some((m) => m.target.classList && m.target.classList.contains("item-destacado"));
    if (!destacado) return;
    const secao = lista.closest(".secao-recolhivel");
    if (secao && secao.dataset.aberto !== "true") {
      const cab = secao.querySelector(".secao-cabecalho");
      if (cab) cab.click();
    }
  }).observe(lista, { attributes: true, attributeFilter: ["class"], subtree: true });
}
abrirSecaoSeDestacado("#lista-viagens");

ligarForm("#viagem-nova-form", "#viagem-nova-btn", "Salvar viagem", () => {
  const destino = $("#viagem-nova-destino").value.trim();
  const ida = $("#viagem-nova-ida").value;
  const volta = $("#viagem-nova-volta").value || null;
  if (!destino || !ida) return null;
  if (volta && volta < ida) {
    mostrarErro("A volta nao pode ser antes da ida.");
    return null;
  }
  return { destino, data_ida: ida, data_volta: volta, internacional: $("#viagem-nova-internacional").checked };
}, "/api/viagens", () => {
  fecharPainelViagem();
  loadViagens();
});
