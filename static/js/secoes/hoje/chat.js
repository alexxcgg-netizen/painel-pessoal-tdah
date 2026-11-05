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

// ---- resposta AO VIVO (2026-10-13) ------------------------------------------------------
// O texto chega aos pedacos do /api/chat/stream e entra palavra por palavra com o mesmo
// blur+fade do escreverPalavraAPalavra - so que no ritmo de quem esta digitando AGORA: uma
// fila que pinga cada palavra com variacao (+-30%), pausa em fim de frase/virgula, e acelera
// sozinha quando acumula (a IA escreve mais rapido que a gente le), pra nunca ficar pra tras.
function criarEscritaAoVivo(bolha) {
  let pendente = ""; // trecho ainda sem espaco no fim (palavra pode estar pela metade)
  const fila = [];
  let timer = null;
  let terminou = null;
  const reduzido = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function pingar() {
    timer = null;
    if (!fila.length) {
      if (terminou) terminou();
      return;
    }
    const token = fila.shift();
    if (token.trim() === "") {
      bolha.appendChild(document.createTextNode(token));
    } else {
      const span = document.createElement("span");
      span.className = "palavra-surgindo";
      span.textContent = token;
      bolha.appendChild(span);
    }
    const lista = bolha.closest(".chat-mensagens, #chat-mensagens");
    if (lista && lista.scrollHeight - lista.scrollTop - lista.clientHeight < 140) lista.scrollTop = lista.scrollHeight;
    let passo = 34 * (0.7 + Math.random() * 0.6);
    if (token.length <= 2) passo *= 0.6;
    // pausas do prototipo aprovado em 2026-10-21 ("rapida e natural"): respira no ponto e na virgula
    if (/[.!?]$/.test(token)) passo += 180;
    else if (/[,;:]$/.test(token)) passo += 75;
    const atraso = fila.length > 24 ? 6 : fila.length > 10 ? passo * 0.45 : passo;
    timer = setTimeout(pingar, reduzido ? 0 : atraso);
  }

  function enfileirar(tokens) {
    tokens.forEach((t) => t && fila.push(t));
    if (!timer) timer = setTimeout(pingar, 0);
  }

  return {
    adicionar(pedaco) {
      pendente += pedaco;
      const partes = pendente.split(/(\s+)/);
      // o ultimo pedaco so sai quando vier o espaco depois dele (palavra inteira)
      pendente = partes.pop();
      enfileirar(partes);
    },
    // fim da resposta: solta o resto e resolve quando a ultima palavra apareceu
    terminar() {
      if (pendente) enfileirar([pendente]);
      pendente = "";
      return new Promise((res) => {
        terminou = res;
        if (!timer && !fila.length) res();
      });
    },
    limpar() {
      fila.length = 0;
      pendente = "";
      clearTimeout(timer);
      timer = null;
      bolha.textContent = "";
    },
  };
}

// POST no /api/chat/stream lendo o text/event-stream. Devolve o MESMO corpo do /api/chat
// (evento "fim"), null em erro ja mostrado, ou undefined quando nem deu pra abrir o stream
// (rede/servidor antigo) - ai o chamador cai no caminho normal (apiFetch /api/chat).
async function chatAoVivo(corpo, { aoTexto, aoRecomeca, aoPasso }) {
  const controller = new AbortController();
  const limite = setTimeout(() => controller.abort(), 200000);
  let res;
  try {
    res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corpo),
      signal: controller.signal,
    });
  } catch {
    clearTimeout(limite);
    return undefined;
  }
  if (res.status === 401) {
    window.location.href = "/login";
    return null;
  }
  const tipo = res.headers.get("Content-Type") || "";
  if (!res.ok || !tipo.includes("text/event-stream") || !res.body) {
    clearTimeout(limite);
    if (res.status >= 400 && res.status < 500) {
      let data = null;
      try {
        data = await res.json();
      } catch {}
      mostrarErro((data && data.error) || `Erro inesperado (HTTP ${res.status}).`);
      return null;
    }
    return undefined;
  }
  const leitor = res.body.getReader();
  const decod = new TextDecoder();
  let buffer = "";
  let final = null;
  try {
    for (;;) {
      const { value, done } = await leitor.read();
      if (done) break;
      buffer += decod.decode(value, { stream: true });
      let corte;
      while ((corte = buffer.indexOf("\n\n")) >= 0) {
        const bloco = buffer.slice(0, corte);
        buffer = buffer.slice(corte + 2);
        let evento = "message";
        let dado = "";
        bloco.split("\n").forEach((l) => {
          if (l.startsWith("event: ")) evento = l.slice(7);
          else if (l.startsWith("data: ")) dado += l.slice(6);
        });
        if (!dado) continue;
        let obj;
        try {
          obj = JSON.parse(dado);
        } catch {
          continue;
        }
        if (evento === "texto") aoTexto(obj);
        else if (evento === "recomeca") aoRecomeca();
        else if (evento === "passo" && aoPasso) aoPasso(obj);
        else if (evento === "fim") final = obj;
        else if (evento === "erro") {
          mostrarErro(obj.error || "A IA não respondeu agora. Tenta de novo.");
          final = null;
          return null;
        }
      }
    }
  } catch {
    if (!final) {
      mostrarErro("A conexão caiu no meio da resposta. Tenta de novo.");
      return null;
    }
  } finally {
    clearTimeout(limite);
    if (typeof invalidarDadosAbas === "function") invalidarDadosAbas();
  }
  if (!final) mostrarErro("A resposta veio incompleta. Tenta de novo.");
  return final;
}

// ---- linha "pensando" (2026-10-14, 3a leva - prototipo aprovado em docs/prototipos/cards-ia-v2.html)
// Enquanto as ferramentas rodam, o servidor manda cada passo ("Calculando o trajeto ate o Lume").
// Os pontinhos viram a orbita + o passo atual com brilho correndo; passo novo sobe e empurra o
// anterior. Quando o texto comeca, a linha vira o recibo recolhivel "N passos · 2,1 s".
const ICONE_RECIBO_OK =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="m8.5 12.3 2.4 2.3 4.6-4.9"/></svg>';
const ICONE_RECIBO_SETA =
  '<svg class="chat-recibo-seta" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg>';

function criarLinhaPensando(bolha) {
  bolha.classList.remove("chat-digitando");
  bolha.classList.add("chat-bolha-pensando");
  bolha.innerHTML =
    '<div class="chat-pensando" role="status" aria-live="polite"><span class="chat-orbita" aria-hidden="true"><i></i><i></i><i></i></span>' +
    '<span class="chat-pensando-texto"></span></div>';
  const caixa = bolha.querySelector(".chat-pensando-texto");
  return {
    passo(texto) {
      caixa.querySelectorAll(".chat-passo:not(.sai)").forEach((velho) => {
        velho.classList.add("sai");
        setTimeout(() => velho.remove(), 450);
      });
      const novo = document.createElement("span");
      novo.className = "chat-passo";
      novo.textContent = texto;
      caixa.appendChild(novo);
    },
  };
}

function reciboPassosHTML(passos, ms) {
  const seg = (Math.max(0.1, ms / 1000)).toLocaleString("pt-BR", { maximumFractionDigits: 1 });
  const itens = passos.map((p) => `<li>${escaparHTMLChat(p)}</li>`).join("");
  return (
    `<details class="chat-recibo"><summary>${ICONE_RECIBO_OK}<span>${passos.length} ${passos.length === 1 ? "passo" : "passos"} · ${seg} s</span>${ICONE_RECIBO_SETA}</summary>` +
    `<ol>${itens}</ol></details>`
  );
}

function escaparHTMLChat(t) {
  return String(t == null ? "" : t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
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
    const linha = criarBolhaChat(m.papel, m.texto);
    lista.appendChild(linha);
    if (m.papel === "assistant") juntarBalaoECard(linha, anexarCardsResposta(lista, m.cards, null), false);
  });
  lista.scrollTop = lista.scrollHeight;
  // o card guardado no historico e uma foto do momento - acerta com o estado de agora
  sincronizarCardsTarefas();
}

// Cards de tarefa conversam com o resto do app (2026-10-14). Marca/desmarca a caixinha e a
// classe "concluida" do li - o MutationObserver dos cards vivos (cards-vivos.js) cuida da
// bandeira que hasteia, da contagem e da "proxima". Caixa no meio de um envio (disabled) fica.
function _aplicarEstadoTarefaNosCards(id, concluida) {
  const lista = $("#chat-mensagens");
  if (!lista) return;
  lista.querySelectorAll(`input[data-tarefa-id="${CSS.escape(String(id))}"]`).forEach((caixa) => {
    if (caixa.disabled || caixa.checked === concluida) return;
    caixa.checked = concluida;
    const li = caixa.closest("li");
    if (li) li.classList.toggle("concluida", concluida);
  });
}

// Pergunta ao servidor o estado das tarefas que aparecem nos cards (concluida em outra tela,
// pelo aviso, pela Siri...). Tarefa apagada nao volta na resposta e o card fica como estava.
let _sincronizandoCards = null;
async function sincronizarCardsTarefas() {
  const lista = $("#chat-mensagens");
  if (!lista || _sincronizandoCards) return _sincronizandoCards;
  // + cards de compromisso (date/balada/documentos/presente): o que foi marcado depois
  const ids = [
    ...new Set([
      ...[...lista.querySelectorAll("input[data-tarefa-id]")].map((c) => c.dataset.tarefaId),
      ...[...lista.querySelectorAll("[data-compromisso]")].map((c) => c.dataset.compromisso),
    ]),
  ]
    .filter((id) => /^\d+$/.test(id))
    .slice(-200);
  if (!ids.length) return null;
  _sincronizandoCards = (async () => {
    const data = await apiFetch(`/api/tasks/estado?ids=${ids.join(",")}`);
    if (data && data.estados) Object.entries(data.estados).forEach(([id, feita]) => _aplicarEstadoTarefaNosCards(id, !!feita));
    if (data && data.extras && typeof CardsSaidas !== "undefined") {
      Object.entries(data.extras).forEach(([id, estado]) => CardsSaidas.aplicarEstado(lista, id, estado));
    }
  })().finally(() => (_sincronizandoCards = null));
  return _sincronizandoCards;
}

document.addEventListener("tarefa:mudou", (ev) => {
  if (ev.detail) _aplicarEstadoTarefaNosCards(ev.detail.id, !!ev.detail.concluida);
});
document.addEventListener("aba:aberta", (ev) => {
  if (ev.detail && ev.detail.aba === "assistente") sincronizarCardsTarefas();
});
// voltou pro app (pode ter concluido pelo aviso, pela Siri, no computador...)
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && $("#tab-assistente") && !$("#tab-assistente").hidden) sincronizarCardsTarefas();
});

// Fase 6 (contrato de cards, docs/CARDS.md): os cards da resposta entram
// logo abaixo da bolha - renderizados pelo registro de static/js/cards.js
// (type desconhecido vira o card fallback, nunca quebra o chat).
function anexarCardsResposta(lista, cards, passos, nova) {
  if (!Array.isArray(cards) || cards.length === 0 || typeof Cards === "undefined") return null;
  const grupo = Cards.criarGrupo(cards, passos);
  lista.appendChild(grupo);
  // cartoes vivos: liga ceu/aviao/onda (historico tambem, parado no estado final)
  if (typeof CardsVivos !== "undefined") CardsVivos.preparar(grupo);
  // 2+ cards: o fio que liga um no outro (so a resposta nova desenha animado)
  if (typeof CardsPremium !== "undefined") CardsPremium.costurar(grupo, { nova: !!nova });
  return grupo;
}

// Balao que vira card (2026-10-21, prototipo aprovado pelo Alex - modelo "B"): a resposta e o
// card sao UMA coisa. O balao se abre pra largura toda, o canto de baixo endireita, a borda pega
// a cor do card e o card desce de dentro dele (cortina de cima pra baixo). O card continua no
// grupo de sempre (mesma largura, mesmo costurar/animar) - so cola no balao. Historico abre
// colado e parado.
function juntarBalaoECard(linha, grupo, animar) {
  if (!linha || !grupo || !linha.classList.contains("assistant")) return;
  const bolha = linha.querySelector(".chat-bolha");
  const primeiro = grupo.querySelector(".card-contrato");
  if (!bolha || !primeiro) return;
  const lista = grupo.parentElement;
  const folga = lista ? parseFloat(getComputedStyle(lista).rowGap) || 0 : 0;
  const cor = getComputedStyle(primeiro).getPropertyValue("--card-cor").trim();
  if (cor) linha.style.setProperty("--balao-cor", cor);
  primeiro.classList.add("card-do-balao");
  grupo.style.setProperty("--balao-folga", `${folga}px`);
  const reduzido = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!animar || reduzido || typeof grupo.animate !== "function") {
    linha.classList.add("chat-linha--virou");
    grupo.classList.add("cards-grupo--do-balao");
    return;
  }
  linha.classList.add("chat-linha--virando");
  // um quadro pro navegador pintar o estado de antes - senao a transicao nao acontece
  requestAnimationFrame(() => {
    linha.classList.add("chat-linha--virou");
    grupo.classList.add("cards-grupo--do-balao");
    grupo.animate(
      [{ clipPath: "inset(0 0 100% 0 round 18px)", opacity: 0.4 }, { clipPath: "inset(0 0 0 0 round 0px)", opacity: 1 }],
      { duration: 760, delay: 140, easing: "cubic-bezier(0.22, 1, 0.36, 1)", fill: "backwards" },
    );
    setTimeout(() => linha.classList.remove("chat-linha--virando"), 900);
  });
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

  if (!opcoes.linhaUsuario) lista.appendChild(criarBolhaChat("user", texto));
  lista.scrollTop = lista.scrollHeight;

  const btn = $("#chat-send");
  setBotaoCarregando(btn, true, "...");

  const digitando = criarIndicadorDigitando();
  lista.appendChild(digitando);
  lista.scrollTop = lista.scrollHeight;

  // GPS do celular junto da mensagem (nucleo/localizacao.js) - espera no máximo ~2,5s,
  // enquanto os três pontinhos já estão na tela; sem permissão/sinal vai sem.
  const corpo = Object.assign({}, opcoes.corpo || { mensagem: texto });
  if (!opcoes.rota && typeof localParaChat === "function") {
    const local = await localParaChat();
    if (local) corpo.local = local;
  }

  // Chat normal: resposta AO VIVO (a bolha dos pontinhos vira a resposta e o texto entra
  // enquanto a IA escreve). Outra rota (brain dump) ou stream indisponivel: caminho antigo.
  let data;
  let escrita = null;
  let alvoTexto = null; // onde as palavras entram (abaixo do recibo, quando teve passos)
  const bolhaViva = digitando.querySelector(".chat-bolha");
  const passos = [];
  const inicio = performance.now();
  let pensando = null;
  if (!opcoes.rota) {
    data = await chatAoVivo(corpo, {
      aoPasso: (p) => {
        if (!p || !p.texto) return;
        passos.push(String(p.texto));
        if (escrita) return; // texto ja correndo: o passo so entra no recibo
        if (!pensando) pensando = criarLinhaPensando(bolhaViva);
        pensando.passo(String(p.texto));
        lista.scrollTop = lista.scrollHeight;
      },
      aoTexto: (pedaco) => {
        if (!escrita) {
          bolhaViva.classList.remove("chat-digitando", "chat-bolha-pensando");
          bolhaViva.innerHTML = (passos.length ? reciboPassosHTML(passos, performance.now() - inicio) : "") +
            '<span class="chat-texto-vivo"></span>';
          pensando = null;
          alvoTexto = bolhaViva.querySelector(".chat-texto-vivo");
          escrita = criarEscritaAoVivo(alvoTexto);
        }
        escrita.adicionar(pedaco);
      },
      aoRecomeca: () => {
        // o que apareceu era um "deixa eu ver..." antes de usar ferramenta: volta pro "pensando"
        // (ou pros pontinhos, se ainda nao teve passo)
        if (!escrita) return;
        escrita.limpar();
        escrita = null;
        alvoTexto = null;
        if (passos.length) {
          pensando = criarLinhaPensando(bolhaViva);
          pensando.passo(passos[passos.length - 1]);
        } else {
          bolhaViva.classList.add("chat-digitando");
          bolhaViva.innerHTML = '<div class="chat-dots"><span></span><span></span><span></span></div>';
        }
      },
    });
  }
  if (data === undefined) {
    data = await apiFetch(opcoes.rota || "/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corpo),
    });
  }

  setBotaoCarregando(btn, false, "Enviar");
  if (!data) {
    digitando.remove();
    return null;
  }

  // resumo_texto = contrato da Fase 6; `resposta` = mesmo texto no campo
  // legado (fallback se um backend mais velho responder).
  const textoFinal = data.resumo_texto || data.resposta || "";
  let linhaResposta;
  if (escrita) {
    await escrita.terminar();
    const mesmo = (s) => String(s || "").replace(/\s+/g, " ").trim();
    if (mesmo(alvoTexto.textContent) !== mesmo(textoFinal)) {
      alvoTexto.textContent = "";
      escreverPalavraAPalavra(alvoTexto, textoFinal);
    }
    digitando.appendChild(criarBotaoOuvirChat(textoFinal));
    linhaResposta = digitando;
  } else {
    digitando.remove();
    linhaResposta = criarBolhaChat("assistant", textoFinal, true);
    lista.appendChild(linhaResposta);
  }
  const grupoCards = anexarCardsResposta(lista, data.cards, data.passos, true);
  juntarBalaoECard(linhaResposta, grupoCards, true);
  // so a resposta NOVA ganha a entrada animada (o historico abre parado)
  if (grupoCards && typeof CardsVivos !== "undefined") CardsVivos.animar(grupoCards);
  if (grupoCards && typeof CardsPremium !== "undefined") CardsPremium.animar(grupoCards);
  lista.scrollTop = lista.scrollHeight;
  loadStreak();

  if (data.acoes && data.acoes.length > 0) {
    vibrar(20);
    tocarSomSucesso();
    sincronizarCardsTarefas(); // a IA pode ter concluido/reaberto tarefa de um card mais antigo
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

// Aquecer o chat (leva "perfeicao", 2026-11-05): ao tocar no campo ou no microfone, o servidor ja busca a
// agenda do iCloud (~4 s) e a construtora, o que mais atrasava o comeco da resposta. Quando a mensagem sai,
// esta tudo no cache. O servidor tambem segura repeticao (30 s); falha aqui nao muda nada pra ele.
let _chatAquecidoEm = 0;
function aquecerChat() {
  const agora = Date.now();
  if (agora - _chatAquecidoEm < 30000) return;
  _chatAquecidoEm = agora;
  fetch("/api/chat/aquecer", { method: "POST" }).catch(() => {});
}
$("#chat-input").addEventListener("focus", aquecerChat);

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
    contextoAudio: contextoInicial = null,
  } = opcoes;
  let contextoAudio = contextoInicial;
  let stream = null;
  let rec = null;
  let fonte = null;
  let tick = null;
  let limite = null;
  let resultado = null; // null enquanto grava; "fala" | "ninguem" | "cancelada" depois
  // onde a voz comecou/terminou (ms desde o inicio) - vai pro servidor descartar o que o
  // Whisper "ouvir" fora disso (ele inventa palavra em silencio: "E ai", "Idiota."...)
  let falaDesdeMs = null;
  let falaAteMs = null;
  // 2026-10-13 (voz de fundo misturando): trechos [ini, fim] em ms em que a voz DELE (perto do
  // microfone, bem mais alta que a do fundo) estava ativa - o servidor joga fora o que o Whisper
  // transcrever fora disso (gente conversando atras, TV)
  const trechosVoz = [];
  let vadAtivo = false;
  // o detector recebeu algum som (nem que seja ruido)? Zeros puros = contexto de audio parado,
  // nao silencio - ai a gravacao vale e vai pro servidor (que ja corta alucinacao do Whisper)
  let somChegou = false;
  let nivelAtual = 0; // RMS suavizado - a onda da barra de gravacao le daqui
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
      // mandou antes de o microfone abrir: avisa em vez de sumir calado
      resolver(motivo === "fala" ? { curto: true } : null);
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
    let voz = 0; // volume tipico da voz dele (envelope dos picos de fala)
    let trechoAberto = null;
    const TICK = 50;

    tick = setInterval(() => {
      analisador.getFloatTimeDomainData(amostras);
      let soma = 0;
      for (let i = 0; i < amostras.length; i++) soma += amostras[i] * amostras[i];
      const rms = Math.sqrt(soma / amostras.length);
      if (rms > 0) somChegou = true;
      // 2026-10-15: contexto de audio parado (iPhone deixa "interrupted" na volta do fundo) = o
      // detector so le zeros. Tenta acordar; enquanto nao acordar, ele nao decide nada.
      if (!somChegou) {
        if (Date.now() - inicio > 1200 && contextoAudio.state !== "running") contextoAudio.resume().catch(() => {});
        return;
      }
      nivel = nivel ? nivel * 0.7 + rms * 0.3 : rms;
      nivelAtual = nivel;
      // piso comeca BAIXO (nao no 1o quadro): se o Alex ja comeca falando, a propria voz
      // virava o "ruido de fundo" e so era percebida depois da primeira pausa
      if (piso === null) piso = Math.min(nivel, 0.004);
      else if (nivel < piso) piso = piso * 0.8 + nivel * 0.2;
      else piso += (nivel - piso) * 0.003;

      const limiarFala = Math.max(0.008, piso * 2.5 + 0.004);
      const limiarSilencio = Math.max(0.005, piso * 1.6 + 0.002);
      const agora = Date.now();
      // voz de fundo e bem mais baixa que a dele falando perto: abaixo de ~22% do volume tipico
      // dele (~ -13 dB) conta como silencio - antes a conversa do fundo segurava a gravacao aberta
      if (falou && nivel > limiarFala) voz = nivel > voz ? voz * 0.75 + nivel * 0.25 : voz * 0.985 + nivel * 0.015;
      const limiarVoz = Math.max(limiarSilencio, voz * VOZ_FRACAO_FUNDO);
      const ms = agora - inicio;
      if (falou && nivel > limiarVoz) {
        if (!trechoAberto) trechosVoz.push((trechoAberto = [Math.max(0, ms - 3 * TICK), ms]));
        else trechoAberto[1] = ms;
      } else if (trechoAberto && ms - trechoAberto[1] > 300) {
        trechoAberto = null; // pausa > 300ms fecha o trecho
      }

      if (nivel > limiarFala) {
        acima++;
        if (acima >= 3) {
          if (!falou) falaDesdeMs = Math.max(0, agora - inicio - 3 * TICK);
          falou = true; // ~150ms seguidos de voz
        }
      } else {
        acima = 0;
      }
      if (falou && nivel > limiarVoz) falaAteMs = agora - inicio;
      if (nivel > limiarVoz) {
        caladoDesde = 0;
      } else if (falou && !caladoDesde) {
        caladoDesde = agora;
      }

      if (!detectarSilencio) return; // ditado: so mede onde teve voz, quem para e o toque
      if (falou && caladoDesde && agora - caladoDesde >= silencioMs) parar("fala");
      else if (!falou && agora - inicio >= esperaFalaMs) parar("ninguem");
    }, TICK);
  }

  async function iniciar() {
    stream = await _abrirMicrofone();
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
      const detectorOuviu = vadAtivo && somChegou;
      if (vadAtivo && !somChegou) _diagMic("detector_surdo", { ctx: contextoAudio && contextoAudio.state, duracaoS, bytes: blob.size });
      // o detector rodou, recebeu som e nunca ouviu voz: nao manda (so silencio = Whisper inventa frase)
      if (detectorOuviu && falaDesdeMs === null) return resolver(resultado === "fala" ? { semVoz: true } : null);
      if (resultado === "fala" && (!blob.size || duracaoS < 0.6)) {
        _diagMic("curto", { duracaoS, bytes: blob.size, tipo });
        return resolver({ curto: true });
      }
      resolver(
        resultado === "fala"
          ? {
              blob,
              duracaoS,
              // detector surdo: sem marcas de onde teve voz (o servidor nao corta nada por elas)
              falaDesdeS: detectorOuviu && falaDesdeMs !== null ? falaDesdeMs / 1000 : null,
              falaAteS: detectorOuviu && falaAteMs !== null ? falaAteMs / 1000 : null,
              trechos: detectorOuviu
                ? trechosVoz.slice(0, 200).map(([a, b]) => [+(a / 1000).toFixed(2), +(b / 1000).toFixed(2)])
                : [],
            }
          : null
      );
    });
    inicio = Date.now();
    rec.start();
    limite = setTimeout(() => parar("fala"), maxMs);
    if (contextoAudio) {
      vadAtivo = true;
      try {
        _vigiarSilencio();
      } catch (e) {
        // detector nao montou: grava sem ele (o toque para; nada e jogado fora)
        vadAtivo = false;
        clearInterval(tick);
        _diagMic("detector_falhou", { erro: (e && e.name) || "Erro", ctx: contextoAudio.state });
      }
    }
  }

  // usarContexto: o microfone do chat mostra a barra na hora e acorda o AudioContext em paralelo
  const usarContexto = (ctx) => {
    if (!vadAtivo) contextoAudio = ctx;
  };
  return { iniciar, parar, pronto, usarContexto, nivel: () => nivelAtual, desde: () => inicio };
}

// fracao do volume tipico da voz dele abaixo da qual o som conta como fundo (ver _vigiarSilencio)
const VOZ_FRACAO_FUNDO = 0.22;

// 2026-10-15 ("clico pra falar e as vezes nao sai"): no app da tela de inicio o iPhone as vezes
// nao responde o pedido do microfone (a barra ficava em 0:00 pra sempre) ou recusa porque o
// microfone ainda esta preso na gravacao/voz anterior. Prazo de 5 s; microfone ocupado = mais uma
// tentativa depois de 400 ms; restricao que o aparelho nao aceita = tenta o pedido simples.
const MIC_PRAZO_MS = 5000;
const _AUDIO_IDEAL = { echoCancellation: true, noiseSuppression: true, autoGainControl: true, voiceIsolation: true };

function _comPrazo(promessa, ms) {
  let id;
  const prazo = new Promise((_, rejeitar) => {
    id = setTimeout(() => {
      const erro = new Error("o microfone nao respondeu");
      erro.name = "PrazoMicrofone";
      rejeitar(erro);
    }, ms);
  });
  return Promise.race([promessa, prazo]).finally(() => clearTimeout(id));
}

async function _abrirMicrofone() {
  const pedir = (audio) => {
    const p = navigator.mediaDevices.getUserMedia({ audio });
    return _comPrazo(p, MIC_PRAZO_MS).catch((e) => {
      // se o microfone abrir DEPOIS do prazo, solta na hora (senao fica a bolinha laranja do iOS)
      if (e && e.name === "PrazoMicrofone") p.then((s) => s.getTracks().forEach((t) => t.stop()), () => {});
      throw e;
    });
  };
  try {
    return await pedir(_AUDIO_IDEAL);
  } catch (e) {
    const nome = (e && e.name) || "Erro";
    if (nome === "NotAllowedError" || nome === "SecurityError" || nome === "PrazoMicrofone") throw e;
    _diagMic("tentou_de_novo", { erro: nome });
    if (nome === "NotReadableError" || nome === "AbortError") await new Promise((r) => setTimeout(r, 400));
    return pedir(nome === "OverconstrainedError" || nome === "TypeError" ? true : _AUDIO_IDEAL);
  }
}

function _diagMic(evento, dados = {}) {
  if (typeof enviarDiagnostico !== "function") return;
  if (!/iPhone|iPad|iPod/.test(navigator.userAgent || "")) return;
  const ios = /OS (\d+)_(\d+)/.exec(navigator.userAgent || "");
  enviarDiagnostico("mic", {
    evento,
    ios: ios ? `${ios[1]}.${ios[2]}` : "?",
    app: window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true,
    ...dados,
  }, true);
}

// Mensagem certa pra cada jeito de o microfone falhar (antes: tudo virava "sem acesso").
function _avisoFalhaMicrofone(erro) {
  const nome = (erro && erro.name) || "Erro";
  _diagMic("falhou", { erro: nome, msg: String((erro && erro.message) || "").slice(0, 60) });
  if (nome === "NotAllowedError" || nome === "SecurityError") {
    mostrarErro("Sem acesso ao microfone. Libera nos Ajustes do iPhone pro painel.");
  } else if (nome === "PrazoMicrofone") {
    mostrarErro("O microfone não respondeu. Toca de novo pra falar.");
  } else {
    mostrarErro("O microfone travou. Toca de novo pra falar.");
  }
}

// AudioContext pronto pra medir a voz: o iPhone deixa "interrupted"/"suspended" na volta do
// fundo (e as vezes "closed"). Acorda; se nao acordar, cria outro.
async function _contextoAudioVivo(ctx) {
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!Ctx) return null;
  try {
    if (!ctx || ctx.state === "closed") ctx = new Ctx();
    if (ctx.state !== "running") {
      await Promise.race([ctx.resume(), new Promise((r) => setTimeout(r, 300))]);
    }
    if (ctx.state !== "running") {
      try {
        ctx.close();
      } catch {}
      ctx = new Ctx();
      ctx.resume().catch(() => {});
    }
    return ctx;
  } catch {
    return null;
  }
}

async function transcreverGravacao({ blob, duracaoS, falaDesdeS, falaAteS, trechos }, opcoes = {}) {
  const corpo = new FormData();
  // limpar: o servidor reescreve como ele QUIS dizer (autocorrecao, "tipo/ne", nome mal ouvido)
  if (opcoes.limpar) corpo.append("limpar", "1");
  // so o FIM da fala vai pro servidor: e no silencio do fim que o Whisper inventa palavra; cortar
  // o comeco por medicao arriscaria perder a primeira frase de verdade
  if (falaAteS !== null && falaAteS !== undefined) corpo.append("fala_ate", falaAteS.toFixed(2));
  if (trechos && trechos.length) corpo.append("trechos_voz", JSON.stringify(trechos));
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

// Audio do chat (2026-10-12, pedido do Alex: "igual mandar audio pro ChatGPT/Gemini - posso errar
// que ele entende"). Toque no microfone -> a barra vira gravacao (ponto vermelho, onda com a voz
// de verdade, tempo, X pra cancelar); o botao de enviar manda. Manda DIRETO: aparece a bolha dele
// "Entendendo...", o servidor transcreve (Whisper) e limpa (autocorrecao, muleta, nome mal ouvido -
// ia/funcoes/fala.py), a bolha ganha o texto limpo e o chat responde sabendo que veio de audio.
const ICONE_MIC_BOLHA =
  '<svg class="bolha-voz-icone" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="2.5" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0"/><path d="M12 17.5V21"/></svg>';
const ONDA_BARRAS = 30;

function _fmtTempoGravacao(ms) {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function initGravadorChat(micBtn) {
  const form = $("#chat-form");
  const sendBtn = $("#chat-send");
  let atual = null; // gravacao em andamento (ou abrindo o microfone)
  let ctxAudio = null;
  let loopOnda = null;
  let loopTempo = null;

  // barra de gravacao (fica escondida dentro do form ate gravar)
  const barra = document.createElement("div");
  barra.className = "gravacao-barra";
  barra.setAttribute("role", "status");
  barra.setAttribute("aria-live", "polite");
  barra.innerHTML =
    '<button type="button" class="gravacao-cancelar" aria-label="Cancelar áudio">' +
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg></button>' +
    '<span class="gravacao-ponto" aria-hidden="true"></span>' +
    `<span class="gravacao-onda" aria-hidden="true">${"<i></i>".repeat(ONDA_BARRAS)}</span>` +
    '<span class="gravacao-tempo">0:00</span>' +
    '<span class="sr-only">Gravando áudio</span>';
  form.insertBefore(barra, sendBtn);
  const barras = [...barra.querySelectorAll(".gravacao-onda i")];
  const tempoEl = barra.querySelector(".gravacao-tempo");
  const historico = new Array(ONDA_BARRAS).fill(0.06);

  function avisoBreve(texto) {
    const input = $("#chat-input");
    const original = input.placeholder;
    input.placeholder = texto;
    setTimeout(() => {
      if (input.placeholder === texto) input.placeholder = original;
    }, 2400);
  }

  function mostrarBarra(ligada) {
    form.classList.toggle("gravando", ligada);
    sendBtn.setAttribute("aria-label", ligada ? "Enviar áudio" : "Enviar");
    clearInterval(loopOnda);
    clearInterval(loopTempo);
    if (!ligada) return;
    historico.fill(0.06);
    barras.forEach((b) => (b.style.transform = "scaleY(0.06)"));
    tempoEl.textContent = "0:00";
    // onda: a voz de verdade (RMS do microfone), da direita pra esquerda
    loopOnda = setInterval(() => {
      if (!atual) return;
      const rms = atual.nivel();
      const alvo = Math.min(1, Math.max(0.06, Math.sqrt(rms * 14)));
      historico.shift();
      historico.push(alvo);
      for (let k = 0; k < ONDA_BARRAS; k++) barras[k].style.transform = `scaleY(${historico[k].toFixed(3)})`;
    }, 70);
    loopTempo = setInterval(() => {
      if (atual && atual.desde()) tempoEl.textContent = _fmtTempoGravacao(Date.now() - atual.desde());
    }, 250);
  }

  async function comecar() {
    aquecerChat();
    // a voz da IA falando segura o audio do iPhone em modo "tocar" - microfone abre mudo
    if (typeof pararVoz === "function") pararVoz();
    const gravacao = criarGravacao({ maxMs: MIC_MAX_MS, contextoAudio: null });
    atual = gravacao;
    mostrarBarra(true);
    vibrar(12);
    gravacao.pronto.then((gravado) => {
      if (atual === gravacao) atual = null;
      mostrarBarra(false);
      if (gravado && gravado.semVoz) avisoBreve("Não ouvi nada - tenta de novo");
      else if (gravado && gravado.curto) avisoBreve("Gravou muito pouco - tenta de novo");
      else if (gravado) enviarAudio(gravado);
    });
    // o detector de voz (mesmo do modo conversa) mede onde teve fala e da o nivel da onda
    ctxAudio = await _contextoAudioVivo(ctxAudio);
    gravacao.usarContexto(ctxAudio);
    try {
      await gravacao.iniciar();
    } catch (e) {
      gravacao.parar("cancelada");
      _avisoFalhaMicrofone(e);
    }
  }

  function terminar(motivo) {
    if (!atual) return;
    if (motivo === "fala") vibrar(18);
    atual.parar(motivo);
  }

  micBtn.hidden = false;
  micBtn.addEventListener("click", () => {
    if (atual) terminar("fala");
    else comecar();
  });
  barra.querySelector(".gravacao-cancelar").addEventListener("click", () => terminar("cancelada"));
  // gravando, o botao de enviar manda o audio (o submit normal do texto fica de fora)
  form.addEventListener(
    "submit",
    (ev) => {
      if (!form.classList.contains("gravando")) return;
      ev.preventDefault();
      ev.stopImmediatePropagation();
      terminar("fala");
    },
    { capture: true }
  );
}

// Bolha "Entendendo..." -> texto limpo -> chat. Falhou: a bolha oferece tentar de novo com o MESMO audio.
async function enviarAudio(gravado, linhaExistente) {
  const lista = $("#chat-mensagens");
  const vazio = lista.querySelector(".chat-vazio");
  if (vazio) vazio.remove();
  const linha = linhaExistente || criarBolhaChat("user", "");
  const bolha = linha.querySelector(".chat-bolha");
  bolha.className = "chat-bolha user bolha-voz pendente";
  bolha.innerHTML =
    `${ICONE_MIC_BOLHA}<span class="bolha-voz-texto">Entendendo` +
    '<span class="bolha-voz-pontos" aria-hidden="true"><i></i><i></i><i></i></span></span>';
  if (!linhaExistente) lista.appendChild(linha);
  lista.scrollTop = lista.scrollHeight;

  const texto = await transcreverGravacao(gravado, { limpar: true });
  if (!texto) {
    bolha.className = "chat-bolha user bolha-voz falhou";
    bolha.innerHTML =
      `${ICONE_MIC_BOLHA}<span class="bolha-voz-texto">Não consegui entender o áudio.</span>` +
      '<button type="button" class="bolha-voz-tentar">Tentar de novo</button>';
    bolha.querySelector(".bolha-voz-tentar").addEventListener("click", () => enviarAudio(gravado, linha), { once: true });
    return;
  }
  bolha.className = "chat-bolha user bolha-voz chegou";
  bolha.innerHTML = `${ICONE_MIC_BOLHA}<span class="bolha-voz-texto"></span>`;
  bolha.querySelector(".bolha-voz-texto").textContent = texto;
  lista.scrollTop = lista.scrollHeight;
  await enviarChat(texto, { linhaUsuario: linha, corpo: { mensagem: texto, audio: true } });
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
    // cartoes vivos (static/js/cards-vivos.js) mexem no texto de numeros/relogio - isso nao e
    // mensagem nova, entao nao pode puxar a tela pro fim enquanto o Alex le mais acima
    if (document.documentElement.dataset.vivoSemRolar) return;
    window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "instant" });
  }
  new MutationObserver(irProFim).observe(lista, { childList: true, subtree: true, characterData: true });
  document.addEventListener("aba:aberta", (ev) => {
    // depois do 1º paint da tela (mesmo padrão de Gastos em navegacao.js): não soma
    // layout ao toque que abriu a IA.
    if (ev.detail && ev.detail.aba === "assistente") requestAnimationFrame(() => setTimeout(irProFim, 0));
  });
})();
