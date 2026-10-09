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
    btn.addEventListener("click", () => falarPremium(btn, textoParaFala(texto)));
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

// R2 (reformulação, etapa 2): estado vazio da tela IA como na prévia aprovada (tela 2) -
// avatar em tile, "Oi, Alex", frase curta e 6 sugestões em grade 2 colunas. Tocar numa
// sugestão manda a pergunta pelo MESMO fluxo do chat (enviarChat), que já tira o
// .chat-vazio da lista (captura.js também tira, ao responder pelo chat).
const SUGESTOES_CHAT = [
  ["O que tenho hoje?", '<rect x="3.5" y="5" width="17" height="15.5" rx="3"/><path d="M3.5 10h17M8 3v4M16 3v4"/>'],
  ["Quanto gastei este mês?", '<path d="M4 7.5A2.5 2.5 0 0 1 6.5 5H18v4"/><rect x="3.5" y="7.5" width="17" height="12" rx="3"/><circle cx="16" cy="13.5" r="1.2"/>'],
  ["O que está atrasado?", '<path d="M12 4 3 19.5h18z"/><path d="M12 10v4.5M12 17.2v.1"/>'],
  ["O que vence essa semana?", '<path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 1.5h-15z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>'],
  ["Me ajuda a planejar o dia", '<path d="M13 3.5 6 13.5h5.5l-1 7 7-10H12z"/>'],
  ["Quando é meu próximo voo?", '<path d="M10.5 13.5 3 11l1.5-1.5 7.5 1L16.5 6A1.8 1.8 0 0 1 19 8.5L14.5 13l1 7.5L14 22l-2.5-7.5-3.5 3.5V20l-1.5 1.5-1-3-3-1L4 16h2.5l4-2.5Z"/>'],
];

function criarChatVazio() {
  const vazio = document.createElement("div");
  vazio.className = "chat-vazio chat-vazio-r2";
  const nome = (typeof NOME_USUARIO === "string" && NOME_USUARIO.trim().split(" ")[0]) || "";
  const ola = document.createElement("div");
  ola.className = "chat-ola";
  ola.innerHTML = `<div class="chat-ola-avatar">${ICONE_ASSISTENTE}</div>`;
  const titulo = document.createElement("h2");
  titulo.className = "chat-ola-titulo";
  titulo.textContent = nome ? `Oi, ${nome}` : "Oi";
  const frase = document.createElement("p");
  frase.className = "chat-ola-frase";
  frase.textContent = "Pergunta o que quiser do seu dia, ou fala uma coisa pra eu anotar.";
  ola.append(titulo, frase);
  const grade = document.createElement("div");
  grade.className = "chat-sugestoes";
  SUGESTOES_CHAT.forEach(([texto, icone]) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chat-sugestao";
    btn.dataset.pergunta = texto;
    btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icone}</svg>`;
    const span = document.createElement("span");
    span.textContent = texto;
    btn.appendChild(span);
    btn.addEventListener("click", () => {
      if (btn.disabled) return;
      grade.querySelectorAll("button").forEach((b) => (b.disabled = true));
      enviarChat(texto);
    });
    grade.appendChild(btn);
  });
  vazio.append(ola, grade);
  return vazio;
}

async function loadChatHistorico() {
  const historico = await apiFetch("/api/chat/historico");
  if (!historico) return;

  const lista = $("#chat-mensagens");
  lista.innerHTML = "";
  if (historico.length === 0) {
    lista.appendChild(criarChatVazio());
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

// Microfone do chat: grava o áudio inteiro (toque liga, toque para) e manda pro
// Whisper no servidor (/api/voz/transcrever). O reconhecimento nativo do Safari
// cortava na primeira pausa e errava muito - fica só de reserva pra navegador
// sem MediaRecorder.
const MIC_MAX_MS = 120000;

function _mimeGravacao() {
  const opcoes = ["audio/mp4", "audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"];
  return opcoes.find((m) => MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(m)) || "";
}

function _colocarNoCampo(texto) {
  const input = $("#chat-input");
  const atual = input.value.trim();
  input.value = atual ? `${atual} ${texto}` : texto;
  input.focus();
}

// Motor único de gravação (microfone do chat e modo conversa). Cada gravação tem o
// próprio estado - nada de variável compartilhada que um "stop" atrasado possa zerar
// enquanto outra gravação já começou (era o que travava o microfone).
//
// Grava SEM timeslice (`start()` sem intervalo): no iPhone, gravar em pedaços de
// 0,5-1s gera um mp4 fragmentado com buracos e o Whisper recebia a fala picotada.
//
// detectarSilencio: encerra sozinho depois de `silencioMs` calado (só depois de ter
// ouvido fala de verdade), ou devolve null se ninguém falar em `esperaFalaMs`.
// O piso de ruído é acompanhado o tempo todo (desce rápido, sobe devagar) e há
// histerese entre "começou a falar" e "ficou calado" - uma pausa curta, uma
// respiração ou a voz mais baixa no fim da frase não contam como silêncio.
function criarGravacao(opcoes = {}) {
  const {
    detectarSilencio = false,
    silencioMs = 3000,
    esperaFalaMs = 12000,
    maxMs = MIC_MAX_MS,
    contextoAudio = null,
  } = opcoes;
  let stream = null;
  let rec = null;
  let fonte = null;
  let tick = null;
  let limite = null;
  let resultado = null; // null enquanto grava; "fala" | "ninguem" | "cancelada" depois
  let inicio = 0;
  let resolver;
  const pronto = new Promise((r) => (resolver = r));
  const pedacos = [];

  const soltar = () => {
    clearInterval(tick);
    clearTimeout(limite);
    if (fonte) {
      try {
        fonte.disconnect();
      } catch {}
    }
    if (stream) stream.getTracks().forEach((t) => t.stop());
    stream = null;
  };

  function parar(motivo = "fala") {
    if (resultado !== null) return;
    resultado = motivo;
    if (rec && rec.state !== "inactive") {
      rec.stop(); // o "stop" abaixo solta o microfone e resolve
    } else {
      soltar();
      resolver(null);
    }
  }

  function _vigiarSilencio() {
    const analisador = contextoAudio.createAnalyser();
    analisador.fftSize = 1024;
    analisador.smoothingTimeConstant = 0;
    fonte = contextoAudio.createMediaStreamSource(stream);
    fonte.connect(analisador);
    const amostras = new Float32Array(analisador.fftSize);
    let nivel = 0;
    let piso = null;
    let acima = 0;
    let falou = false;
    let caladoDesde = 0;
    const TICK = 50;

    tick = setInterval(() => {
      analisador.getFloatTimeDomainData(amostras);
      let soma = 0;
      for (let i = 0; i < amostras.length; i++) soma += amostras[i] * amostras[i];
      const rms = Math.sqrt(soma / amostras.length);
      nivel = nivel ? nivel * 0.7 + rms * 0.3 : rms;
      if (piso === null) piso = nivel;
      else if (nivel < piso) piso = piso * 0.8 + nivel * 0.2;
      else piso += (nivel - piso) * 0.003;

      const limiarFala = Math.max(0.008, piso * 2.5 + 0.004);
      const limiarSilencio = Math.max(0.005, piso * 1.6 + 0.002);
      const agora = Date.now();

      if (nivel > limiarFala) {
        acima++;
        if (acima >= 3) falou = true; // ~150ms seguidos de voz
      } else {
        acima = 0;
      }
      if (nivel > limiarSilencio) {
        caladoDesde = 0;
      } else if (falou && !caladoDesde) {
        caladoDesde = agora;
      }

      if (falou && caladoDesde && agora - caladoDesde >= silencioMs) parar("fala");
      else if (!falou && agora - inicio >= esperaFalaMs) parar("ninguem");
    }, TICK);
  }

  async function iniciar() {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    if (resultado !== null) {
      // cancelada enquanto o iPhone ainda liberava o microfone
      soltar();
      return;
    }
    const mime = _mimeGravacao();
    rec = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
    const tipo = (rec.mimeType || mime || "audio/mp4").split(";")[0];
    rec.addEventListener("dataavailable", (e) => {
      if (e.data && e.data.size) pedacos.push(e.data);
    });
    rec.addEventListener("stop", () => {
      const duracaoS = (Date.now() - inicio) / 1000;
      soltar();
      if (resultado === null) resultado = "fala"; // parou sozinho (ex: iPhone interrompeu)
      const blob = new Blob(pedacos, { type: tipo });
      resolver(resultado === "fala" && blob.size && duracaoS >= 0.6 ? { blob, duracaoS } : null);
    });
    inicio = Date.now();
    rec.start();
    limite = setTimeout(() => parar("fala"), maxMs);
    if (detectarSilencio && contextoAudio) _vigiarSilencio();
  }

  return { iniciar, parar, pronto };
}

async function transcreverGravacao({ blob, duracaoS }) {
  const corpo = new FormData();
  const ext = blob.type.includes("mp4") ? "m4a" : blob.type.includes("ogg") ? "ogg" : "webm";
  corpo.append("audio", blob, `fala.${ext}`);
  corpo.append("duracao", String(Math.round(duracaoS)));
  const data = await apiFetch("/api/voz/transcrever", { method: "POST", body: corpo });
  return data && data.texto ? data.texto : null;
}

function initVozChat() {
  const micBtn = $("#chat-mic");
  if (!micBtn) return;
  const temGravador = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
  if (temGravador) {
    initGravadorChat(micBtn);
  } else {
    initReconhecimentoNativoChat(micBtn);
  }
}

// Ditado: toque liga, toque para; o texto cai no campo pra conferir antes de enviar.
function initGravadorChat(micBtn) {
  let atual = null; // gravação em andamento (ou abrindo o microfone)
  let transcrevendo = false;

  async function transcrever(gravado) {
    const input = $("#chat-input");
    const placeholderOriginal = input.placeholder;
    transcrevendo = true;
    micBtn.classList.add("transcrevendo");
    input.placeholder = "Transcrevendo…";
    try {
      const texto = await transcreverGravacao(gravado);
      if (texto) _colocarNoCampo(texto);
    } finally {
      transcrevendo = false;
      micBtn.classList.remove("transcrevendo");
      input.placeholder = placeholderOriginal;
    }
  }

  async function comecar() {
    const gravacao = criarGravacao({ maxMs: MIC_MAX_MS });
    atual = gravacao;
    micBtn.classList.add("ouvindo");
    gravacao.pronto.then((gravado) => {
      if (atual === gravacao) atual = null;
      micBtn.classList.remove("ouvindo");
      if (gravado) transcrever(gravado);
    });
    try {
      await gravacao.iniciar();
    } catch {
      gravacao.parar("cancelada");
      mostrarErro("Sem acesso ao microfone. Libera nos Ajustes do iPhone pro painel.");
    }
  }

  micBtn.hidden = false;
  micBtn.addEventListener("click", () => {
    if (transcrevendo) return;
    if (atual) {
      atual.parar("fala");
      return;
    }
    comecar();
  });
}

function initReconhecimentoNativoChat(micBtn) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
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
    _colocarNoCampo(e.results[0][0].transcript);
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

// R1 (reformulação): na tela IA a conversa rola com a página (static/css/secoes/hoje/chat.css),
// não mais numa caixa com rolagem própria - o `lista.scrollTop = lista.scrollHeight` de cima
// continua inofensivo; aqui a PÁGINA vai pro fim quando chega mensagem/card novo (inclusive o
// texto que aparece palavra a palavra) e quando a tela IA abre, sempre deixando a última
// mensagem logo acima do campo fixo.
(function () {
  const lista = document.getElementById("chat-mensagens");
  if (!lista || typeof MutationObserver === "undefined") return;
  function irProFim() {
    const tela = document.getElementById("tab-assistente");
    if (!tela || tela.hidden || !tela.contains(lista)) return;
    window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "instant" });
  }
  new MutationObserver(irProFim).observe(lista, { childList: true, subtree: true, characterData: true });
  document.addEventListener("aba:aberta", (ev) => {
    // depois do 1º paint da tela (mesmo padrão de Gastos em navegacao.js): não soma
    // layout ao toque que abriu a IA.
    if (ev.detail && ev.detail.aba === "assistente") requestAnimationFrame(() => setTimeout(irProFim, 0));
  });
})();
