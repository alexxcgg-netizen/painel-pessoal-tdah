// static/js/secoes/hoje/chat.js - Secao hoje > chat (HTML: templates/secoes/hoje/chat.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 965-1218.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

const ICONE_ASSISTENTE =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3l1.6 4.9L18 9.5l-4.4 1.6L12 16l-1.6-4.9L6 9.5l4.4-1.6L12 3Z"/><path d="M19 14l.7 2.3L22 17l-2.3.7L19 20l-.7-2.3L16 17l2.3-.7L19 14Z"/></svg>';

function criarAvatarChat() {
  const div = document.createElement("div");
  div.className = "chat-avatar";
  div.innerHTML = ICONE_ASSISTENTE;
  return div;
}

const ICONE_OUVIR =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5 6 9H2v6h4l5 4V5z"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>';

function criarBotaoOuvirChat(texto) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "btn-ouvir btn-ouvir-chat";
  btn.setAttribute("aria-label", "Ouvir essa resposta");
  btn.innerHTML = ICONE_OUVIR;
  if (!("speechSynthesis" in window)) {
    btn.hidden = true;
  } else {
    btn.addEventListener("click", () => falarPremium(btn, primeiraFrase(texto)));
  }
  return btn;
}

// Ritmo humano (pedido explicito: "diferentes ritmos... mas não algo devagar"):
// o passo base continua limitando a duracao TOTAL (nao fica mais lento que
// antes - a media do jitter e 1.0x), mas cada palavra varia +-20% em vez de
// ser um metronomo identico, palavras bem curtas (ate 2 letras - "e", "a",
// "no") saem mais rapido, e pontuacao de fim de frase/virgula ganha uma
// pausa de verdade - e assim que gente digita, nao um bloco uniforme.
function escreverPalavraAPalavra(elemento, texto) {
  const tokens = texto.split(/(\s+)/);
  const palavras = tokens.filter((t) => t.trim() !== "").length;
  const passoBase = Math.min(22, Math.max(7, 620 / Math.max(palavras, 1)));
  let acumulado = 0;
  tokens.forEach((token) => {
    if (token.trim() === "") {
      elemento.appendChild(document.createTextNode(token));
      return;
    }
    const span = document.createElement("span");
    span.className = "palavra-surgindo";
    span.textContent = token;
    span.style.animationDelay = `${acumulado}ms`;
    elemento.appendChild(span);

    let incremento = passoBase * (0.8 + Math.random() * 0.4);
    if (token.length <= 2) incremento *= 0.7;
    if (/[.!?]$/.test(token)) incremento += passoBase * 2.2;
    else if (/[,;:]$/.test(token)) incremento += passoBase * 1.1;
    acumulado += incremento;
  });
}

function criarBolhaChat(papel, texto, animarEntrada = false) {
  const bolha = document.createElement("div");
  bolha.className = `chat-bolha ${papel}`;
  if (animarEntrada && papel === "assistant") {
    escreverPalavraAPalavra(bolha, texto);
  } else {
    bolha.textContent = texto;
  }

  const linha = document.createElement("div");
  linha.className = `chat-linha ${papel}`;
  if (papel === "assistant") {
    linha.appendChild(criarAvatarChat());
    linha.appendChild(bolha);
    linha.appendChild(criarBotaoOuvirChat(texto));
  } else {
    linha.appendChild(bolha);
  }
  return linha;
}

function criarIndicadorDigitando() {
  const bolha = document.createElement("div");
  bolha.className = "chat-bolha assistant chat-digitando";
  bolha.innerHTML = '<div class="chat-dots"><span></span><span></span><span></span></div>';

  const linha = document.createElement("div");
  linha.className = "chat-linha assistant";
  linha.appendChild(criarAvatarChat());
  linha.appendChild(bolha);
  return linha;
}

async function loadChatHistorico() {
  const historico = await apiFetch("/api/chat/historico");
  if (!historico) return;

  const lista = $("#chat-mensagens");
  lista.innerHTML = "";
  if (historico.length === 0) {
    const vazio = document.createElement("p");
    vazio.className = "chat-vazio";
    vazio.innerHTML =
      ICONE_ASSISTENTE + "<br>Fala comigo - posso registrar tarefa, gasto, meta ou montar o plano do dia.";
    lista.appendChild(vazio);
    return;
  }
  historico.forEach((m) => {
    lista.appendChild(criarBolhaChat(m.papel, m.texto));
    if (m.papel === "assistant") anexarCardsResposta(lista, m.cards, null);
  });
  lista.scrollTop = lista.scrollHeight;
}

// Fase 6 (contrato de cards, docs/CARDS.md): os cards da resposta entram
// logo abaixo da bolha - renderizados pelo registro de static/js/cards.js
// (type desconhecido vira o card fallback, nunca quebra o chat).
function anexarCardsResposta(lista, cards, passos) {
  if (!Array.isArray(cards) || cards.length === 0 || typeof Cards === "undefined") return null;
  const grupo = Cards.criarGrupo(cards, passos);
  lista.appendChild(grupo);
  return grupo;
}

// Recarrega as telas que um card pode ter mudado (desfazer, concluir
// tarefa pelo checkbox do card) - mesmas que o caminho de acao do chat ja
// recarrega.
function recarregarAposMudancaDeCard() {
  loadSummary();
  loadStreak();
  if (!$("#tab-painel").hidden) loadLembretes();
  if (!$("#tab-tarefas").hidden) loadTasks();
  if (!$("#tab-gastos").hidden) {
    loadExpenses();
    loadMetas();
  }
}

if (typeof Cards !== "undefined") {
  Cards.ligar($("#chat-mensagens"), {
    apiFetch,
    // A aba Vida so carrega as listas no clique da tabbar (vida.js) - o
    // link "Abrir Projetos/Hábitos/Viagens" de um card (US-E7) precisa
    // disparar o mesmo carregamento, senao a lista de destino fica vazia.
    // R1: showTab agora dispara "aba:aberta" e init.js carrega Vida por esse evento
    // (com o cache curto de abaPrecisaCarregar) - chamar loadVidaAba aqui duplicaria.
    showTab: (aba) => showTab(aba),
    aoMudar: recarregarAposMudancaDeCard,
  });
}

// `opcoes` (US-E6): { rota, corpo } manda pra outra rota que devolve o MESMO
// contrato de /api/chat (ex: "processar" um item do brain dump) - a bolha
// do usuario, o "digitando", a resposta e os cards seguem o mesmo caminho.
async function enviarChat(texto, opcoes = {}) {
  const lista = $("#chat-mensagens");
  const vazio = lista.querySelector(".chat-vazio");
  if (vazio) vazio.remove();

  lista.appendChild(criarBolhaChat("user", texto));
  lista.scrollTop = lista.scrollHeight;

  const btn = $("#chat-send");
  setBotaoCarregando(btn, true, "...");

  const digitando = criarIndicadorDigitando();
  lista.appendChild(digitando);
  lista.scrollTop = lista.scrollHeight;

  const data = await apiFetch(opcoes.rota || "/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(opcoes.corpo || { mensagem: texto }),
  });

  digitando.remove();
  setBotaoCarregando(btn, false, "Enviar");
  if (!data) return null;

  // resumo_texto = contrato da Fase 6; `resposta` = mesmo texto no campo
  // legado (fallback se um backend mais velho responder).
  lista.appendChild(criarBolhaChat("assistant", data.resumo_texto || data.resposta, true));
  anexarCardsResposta(lista, data.cards, data.passos);
  lista.scrollTop = lista.scrollHeight;
  loadStreak();

  if (data.acoes && data.acoes.length > 0) {
    vibrar(20);
    tocarSomSucesso();
    loadSummary();
    loadUso();
    if (!$("#tab-painel").hidden) {
      loadAgenda();
      loadMemorias();
      loadLembretes();
      loadEsperas();
    }
    if (!$("#tab-tarefas").hidden) loadTasks();
    if (!$("#tab-gastos").hidden) {
      loadExpenses();
      loadMetas();
    }
  }
  return data;
}

$("#chat-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = $("#chat-input");
  const texto = input.value.trim();
  if (!texto) return;
  input.value = "";
  enviarChat(texto);
});

function initVozChat() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const micBtn = $("#chat-mic");
  if (!SpeechRecognition) return;

  const recognition = new SpeechRecognition();
  recognition.lang = "pt-BR";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  let ouvindo = false;

  const pararDeOuvir = () => {
    ouvindo = false;
    micBtn.classList.remove("ouvindo");
  };

  recognition.addEventListener("result", (e) => {
    const texto = e.results[0][0].transcript;
    const input = $("#chat-input");
    input.value = texto;
    input.focus();
  });
  recognition.addEventListener("end", pararDeOuvir);
  recognition.addEventListener("error", pararDeOuvir);

  micBtn.hidden = false;
  micBtn.addEventListener("click", () => {
    if (ouvindo) {
      recognition.stop();
      return;
    }
    ouvindo = true;
    micBtn.classList.add("ouvindo");
    try {
      recognition.start();
    } catch {
      pararDeOuvir();
    }
  });
}
