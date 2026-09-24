// static/js/secoes/vida/viagens.js - Secao vida > viagens (HTML: templates/secoes/vida/viagens.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 1263-1419.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

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
  input.placeholder = "Numero do voo (ex: LA3251)";
  input.maxLength = 12;
  input.value = v.numero_voo || "";
  input.setAttribute("aria-label", `Numero do voo da viagem para ${v.destino}`);
  const salvarBtn = criarEl("button", "btn-com-icone", v.numero_voo ? "atualizar" : "salvar");
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
    setBotaoCarregando(salvarBtn, false, v.numero_voo ? "atualizar" : "salvar");
    if (!r) return;
    v.numero_voo = r.numero_voo;
    salvarBtn.textContent = v.numero_voo ? "atualizar" : "salvar";
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
  if (!viagens) return;
  const lista = $("#lista-viagens");
  lista.innerHTML = "";
  $("#viagens-vazio").hidden = viagens.length > 0;
  viagens.forEach((v) => {
    const datas = v.data_volta ? `${fmtDataBr(v.data_ida)} a ${fmtDataBr(v.data_volta)}` : fmtDataBr(v.data_ida);
    const quando = v.dias_ate > 0 ? `em ${v.dias_ate} dia(s)` : v.dias_ate === 0 ? "hoje" : "em andamento";
    const lugares = v.lugares.length ? `voce curtiu la: ${v.lugares.map((l) => l.nome).join(", ")}` : null;
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

// Contrato Fase 7B (V0d): abrirBottomSheet/fecharBottomSheet reais moram em
// static/js/ui/bottom-sheet.js (fundo escurecido, ESC, toque fora, foco
// preso). Enquanto essa faixa nao chega na integracao, usa um fallback
// minimo so pra secao continuar testavel (so mostra/esconde via [hidden]).
function abrirSheetViagem() {
  const sheet = $("#viagem-sheet");
  if (window.abrirBottomSheet) {
    window.abrirBottomSheet(sheet);
  } else {
    sheet.hidden = false;
  }
}

function fecharSheetViagem() {
  const sheet = $("#viagem-sheet");
  if (window.fecharBottomSheet) {
    window.fecharBottomSheet(sheet);
  } else {
    sheet.hidden = true;
  }
}

$("#viagem-nova-abrir").addEventListener("click", () => abrirSheetViagem());
$("#viagem-sheet-fechar").addEventListener("click", () => fecharSheetViagem());
// fallback de toque-fora/ESC (a versao definitiva e da V0d) - so age quando
// a API real ainda nao existe, pra nao duplicar comportamento dela depois.
$("#viagem-sheet").addEventListener("click", (e) => {
  if (!window.abrirBottomSheet && e.target === e.currentTarget) fecharSheetViagem();
});
document.addEventListener("keydown", (e) => {
  if (!window.abrirBottomSheet && e.key === "Escape" && !$("#viagem-sheet").hidden) fecharSheetViagem();
});

ligarForm("#viagem-nova-form", "#viagem-nova-btn", "Adicionar", () => {
  const destino = $("#viagem-nova-destino").value.trim();
  const ida = $("#viagem-nova-ida").value;
  return destino && ida
    ? { destino, data_ida: ida, data_volta: $("#viagem-nova-volta").value || null, internacional: $("#viagem-nova-internacional").checked }
    : null;
}, "/api/viagens", () => {
  fecharSheetViagem();
  loadViagens();
});
