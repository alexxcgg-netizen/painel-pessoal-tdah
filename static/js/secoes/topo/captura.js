// static/js/secoes/topo/captura.js - Secao topo > captura (HTML: templates/secoes/topo/captura.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 308-366, app.js 374-455, app.js 563-649.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

function criarCardResultado(parsed) {
  const card = document.createElement("div");
  card.className = `card-resultado card-resultado-${parsed.tipo}`;

  const eyebrow = document.createElement("div");
  eyebrow.className = "card-resultado-eyebrow";
  const rotulos = { tarefa: "Tarefa criada", gasto: "Gasto registrado", meta: "Meta criada" };
  const icones = { tarefa: ICONE_TAREFA_CARD, gasto: ICONE_GASTO_CARD, meta: ICONE_META_CARD };
  eyebrow.innerHTML = `${icones[parsed.tipo] || ""}<span>${rotulos[parsed.tipo] || "Criado"}</span>`;
  card.appendChild(eyebrow);

  const titulo = document.createElement("p");
  titulo.className = "card-resultado-titulo";
  titulo.textContent = parsed.titulo;
  card.appendChild(titulo);

  if (parsed.tipo === "gasto") {
    const valor = document.createElement("p");
    valor.className = "card-resultado-valor";
    valor.textContent = `-${fmtMoeda(parsed.valor)}`;
    card.appendChild(valor);
    if (parsed.categoria) {
      const tag = document.createElement("span");
      tag.className = "gasto-categoria";
      tag.dataset.cat = parsed.categoria;
      tag.textContent = parsed.categoria;
      card.appendChild(tag);
    }
  } else if (parsed.tipo === "meta") {
    const valor = document.createElement("p");
    valor.className = "card-resultado-valor";
    valor.textContent = fmtMoeda(parsed.valor);
    card.appendChild(valor);
    const detalhe = document.createElement("p");
    detalhe.className = "card-resultado-detalhe";
    detalhe.textContent = parsed.prazo ? `Prazo: ${parsed.prazo}` : "Sem prazo definido";
    card.appendChild(detalhe);
  } else {
    const detalhe = document.createElement("p");
    detalhe.className = "card-resultado-detalhe";
    detalhe.textContent = parsed.hora
      ? `${parsed.quando || "hoje"} as ${parsed.hora}`
      : parsed.quando || "sem prazo definido";
    card.appendChild(detalhe);
  }

  return card;
}

// Fase 6 (docs/CARDS.md): resposta da captura com o contrato de cards vira
// os cards do registro (static/js/cards.js); resposta de um servidor mais
// velho (sem `cards`) cai no card de resultado antigo acima.
function criarCardsCaptura(data) {
  if (data && Array.isArray(data.cards) && data.cards.length && typeof Cards !== "undefined") {
    return Cards.criarGrupo(data.cards, data.passos);
  }
  return criarCardResultado(data);
}

// Card provisorio mostrado quando a captura foi enfileirada offline - sem
// classificacao da IA ainda (ela so roda quando a requisicao de verdade
// chegar no servidor), entao mostra o texto cru + um aviso, no lugar do
// card com titulo/categoria/valor que so a resposta real traz. `id` e o
// mesmo client_id usado no corpo da requisicao e na fila (liga o card na
// tela ao item que vai sincronizar depois, pra poder trocar pelo real).
function criarCardCapturaPendente(id, text) {
  const card = document.createElement("div");
  card.className = "card-resultado card-resultado-pendente";
  card.id = `fila-${id}`;

  const eyebrow = document.createElement("div");
  eyebrow.className = "card-resultado-eyebrow";
  eyebrow.innerHTML = `${ICONE_TAREFA_CARD}<span>Sem conexão - salvo, vai sincronizar</span>`;
  card.appendChild(eyebrow);

  const titulo = document.createElement("p");
  titulo.className = "card-resultado-titulo";
  titulo.textContent = text;
  card.appendChild(titulo);

  return card;
}

// Vel A2b: card provisorio "Salvando…" mostrado na hora do toque, antes da
// resposta chegar - mesmo estilo visual do card de fila offline (borda
// tracejada) mas so um placeholder local, nunca vira item de fila.
function criarCardCapturaSalvando(text) {
  const card = document.createElement("div");
  card.className = "card-resultado card-resultado-pendente";

  const eyebrow = document.createElement("div");
  eyebrow.className = "card-resultado-eyebrow";
  eyebrow.innerHTML = `${ICONE_TAREFA_CARD}<span>Salvando…</span>`;
  card.appendChild(eyebrow);

  const titulo = document.createElement("p");
  titulo.className = "card-resultado-titulo";
  titulo.textContent = text;
  card.appendChild(titulo);

  return card;
}

// Mostra/esconde o indicador discreto de fila offline - some sozinho quando
// tudo sincroniza (n chega a 0). Chamado pela propria FilaOffline (a cada
// item processado) e no carregamento da pagina.
function atualizarIndicadorOffline(n) {
  const banner = $("#offline-banner");
  if (!banner) return;
  if (n > 0) {
    banner.classList.remove("c2-toast-sai");
    banner.textContent = `Sem conexão - ${n} ${n === 1 ? "item pendente" : "itens pendentes"}, vai sincronizar quando voltar.`;
    banner.hidden = false;
  } else if (!banner.hidden) {
    if (typeof saidaAnimada === "function") {
      saidaAnimada(banner, () => {
        banner.hidden = true;
      });
    } else {
      banner.hidden = true;
    }
  }
}

if (typeof FilaOffline !== "undefined") {
  // Assim que uma captura enfileirada sincroniza de verdade, troca o card
  // provisorio pelo resultado real (ou, no raro caso de a IA ainda ficar em
  // duvida, avisa em vez de travar a fila esperando o Alex responder) e
  // recarrega as mesmas telas que o caminho online ja recarrega.
  FilaOffline.registrarCallback("capture", (data, item) => {
    const cardPendente = document.getElementById(`fila-${item.id}`);
    if (data && data.duvida) {
      if (cardPendente) cardPendente.remove();
      const aviso = document.createElement("p");
      aviso.className = "card-resultado-detalhe";
      aviso.textContent = `Capturado offline, mas ficou em dúvida: "${data.duvida}". Repete a captura quando puder pra confirmar.`;
      $("#chat-mensagens").appendChild(aviso);
    } else if (data) {
      const novoCard = criarCardsCaptura(data);
      if (cardPendente) cardPendente.replaceWith(novoCard);
      else $("#chat-mensagens").appendChild(novoCard);
    }
    loadUso();
    loadSummary();
    loadStreak();
    if (data && data.memoria) loadMemorias();
    if (!$("#tab-tarefas").hidden) loadTasks();
    if (!$("#tab-gastos").hidden) {
      loadExpenses();
      loadMetas();
    }
  });

  FilaOffline.registrarCallback("erro", (item, corpo, status) => {
    const cardPendente = document.getElementById(`fila-${item.id}`);
    if (cardPendente) cardPendente.remove();
    mostrarErro((corpo && corpo.error) || `Não consegui sincronizar um item pendente (HTTP ${status}). Foi descartado.`);
  });

  // Nota fiscal tirada sem internet (US-C8): a extracao em si nao pode
  // esperar so no navegador porque depende da API de visao - fica na fila
  // igual qualquer outra escrita, e quando sincronizar mostra a MESMA tela
  // de confirmacao de quem tirou a foto com internet (nunca salva sozinho).
  FilaOffline.registrarCallback("nota_fiscal_extrair", (data) => {
    if (data && !data.duvida) mostrarConfirmacaoNotaFiscal(data);
  });
}

async function enviarCaptura(text, clarificacao, campoOrigem) {
  const capturaBtn = $("#captura-btn");
  const duvidaBtn = $("#duvida-btn");
  setBotaoCarregando(capturaBtn, true, "Pensando...");
  duvidaBtn.disabled = true;

  // Vel A2b: card "Salvando…" aparece na hora do toque (o campo ja foi
  // limpo por quem chamou); troca pelo card real quando a resposta chegar,
  // ou some (devolvendo o texto pro campo) se der erro.
  const listaChat = $("#chat-mensagens");
  listaChat.querySelector(".chat-vazio")?.remove();
  const cardSalvando = criarCardCapturaSalvando(text);
  listaChat.appendChild(cardSalvando);
  listaChat.scrollTop = listaChat.scrollHeight;

  const clientId = crypto.randomUUID();
  const data = await apiFetch(
    "/api/capture",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, clarificacao, client_id: clientId }),
    },
    { tipo: "capture", id: clientId }
  );

  setBotaoCarregando(capturaBtn, false, "Adicionar");
  duvidaBtn.disabled = false;

  if (!data) {
    // erro (mostrarErro ja foi chamado pelo apiFetch): desfaz o otimista,
    // devolve o texto pro campo de origem.
    cardSalvando.remove();
    if (campoOrigem) campoOrigem.value = text;
    return;
  }

  if (data.__enfileirado) {
    // otimista de fila offline: o Alex nao pode ficar sem poder anotar nada
    // so por falta de sinal - mostra como se tivesse dado certo, sincroniza
    // sozinho depois.
    textoPendente = null;
    $("#duvida-box").hidden = true;
    pulsarSucesso($("#captura-input"));
    vibrar(20);
    cardSalvando.replaceWith(criarCardCapturaPendente(clientId, text));
    listaChat.scrollTop = listaChat.scrollHeight;
    return;
  }

  loadUso();

  if (data.duvida) {
    cardSalvando.remove();
    textoPendente = data.texto_original;
    $("#duvida-texto").textContent = data.duvida;
    $("#duvida-input").value = "";
    $("#duvida-box").hidden = false;
    return;
  }

  textoPendente = null;
  $("#duvida-box").hidden = true;
  pulsarSucesso($("#captura-input"));
  vibrar(20);
  tocarSomSucesso();
  const cardsNovos = criarCardsCaptura(data);
  cardSalvando.replaceWith(cardsNovos);
  listaChat.scrollTop = listaChat.scrollHeight;
  avisarRetornoNaFolha(cardsNovos);
  loadSummary();
  loadStreak();
  if (data.memoria) loadMemorias();
  if (!$("#tab-tarefas").hidden) loadTasks();
  if (!$("#tab-gastos").hidden) {
    loadExpenses();
    loadMetas();
  }
}

$("#captura-btn").addEventListener("click", () => {
  const input = $("#captura-input");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  enviarCaptura(text, "", input);
});

$("#captura-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") $("#captura-btn").click();
});

$("#duvida-btn").addEventListener("click", () => {
  const input = $("#duvida-input");
  const resposta = input.value.trim();
  if (!resposta || !textoPendente) return;
  enviarCaptura(textoPendente, resposta, input);
});

$("#duvida-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") $("#duvida-btn").click();
});

// ---- R1 (reformulação): folha do botão "+" (secoes/topo/captura.html) ----
// O resultado da captura continua indo pro histórico (#chat-mensagens, agora na tela IA);
// a folha mostra uma linha curta de confirmação pra quem está nela não ficar no escuro.
function avisarRetornoNaFolha(cardsNovos) {
  const retorno = document.getElementById("captura-retorno");
  if (!retorno) return;
  let titulo = "";
  try {
    const el = cardsNovos && cardsNovos.querySelector && cardsNovos.querySelector('[class*="titulo"]');
    titulo = el ? el.textContent.trim() : "";
  } catch (e) {
    titulo = "";
  }
  retorno.textContent = titulo ? `Salvo: ${titulo}` : "Salvo.";
  retorno.hidden = false;
}

// Atalhos (Tarefa, Gasto, Lembrete, Nota): não há fluxo próprio - põem um prefixo no MESMO
// campo, que já classifica texto livre, e devolvem o foco pra ele.
(function ligarAtalhosDaFolha() {
  const campo = document.getElementById("captura-input");
  const atalhos = document.querySelectorAll(".folha-atalho[data-prefixo]");
  if (!campo || !atalhos.length) return;
  const prefixos = Array.from(atalhos, (b) => b.dataset.prefixo);
  atalhos.forEach((btn) => {
    btn.addEventListener("click", () => {
      let texto = campo.value;
      for (const p of prefixos) {
        if (texto.toLowerCase().startsWith(p.toLowerCase())) {
          texto = texto.slice(p.length);
          break;
        }
      }
      campo.value = btn.dataset.prefixo + texto;
      atalhos.forEach((b) => b.setAttribute("aria-pressed", b === btn ? "true" : "false"));
      campo.focus();
      try {
        campo.setSelectionRange(campo.value.length, campo.value.length);
      } catch (e) {
        /* input sem seleção (navegador antigo): só o foco já serve */
      }
    });
  });
  // Folha abrindo de novo: limpa a confirmação da vez anterior.
  const fab = document.getElementById("fab-captura");
  if (fab) {
    fab.addEventListener("click", () => {
      const retorno = document.getElementById("captura-retorno");
      if (retorno) retorno.hidden = true;
      atalhos.forEach((b) => b.setAttribute("aria-pressed", "false"));
      requestAnimationFrame(() => campo.focus());
    });
  }
})();
