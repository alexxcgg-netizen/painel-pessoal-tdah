const $ = (sel) => document.querySelector(sel);

// app de uso unico (so o Alex) - nome fixo aqui mesmo pra saudacao
// personalizada, mesmo espirito do "so o Alex usa o PIN hoje" do painel_web
// da construtora. Se um dia isso precisar mudar, e essa unica linha.
const NOME_USUARIO = "Alex";

let textoPendente = null;

function mostrarSaudacao() {
  const agora = new Date();
  const hora = agora.getHours();
  const saudacao = hora < 5 ? "Boa noite" : hora < 12 ? "Bom dia" : hora < 18 ? "Boa tarde" : "Boa noite";
  $("#saudacao-texto").textContent = `${saudacao}, ${NOME_USUARIO.split(" ")[0]}`;
  const dataFormatada = agora.toLocaleDateString("pt-BR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
  $("#saudacao-data").textContent = dataFormatada.charAt(0).toUpperCase() + dataFormatada.slice(1);
  $("#avatar-usuario").textContent = NOME_USUARIO.charAt(0).toUpperCase();
}

const ICONE_TRASH =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M9 7V4.5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1V7M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13"/></svg>';
const ICONE_PASSOS =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h4M4 12h4M4 18h4M11 6h9M11 12h9M11 18h9"/></svg>';
const ICONE_CHECK =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12.5 9 17 20 6"/></svg>';
const ICONE_PLUS =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>';
const ICONE_TAREFA_CARD =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 12l2.5 2.5L16 9"/></svg>';
const ICONE_GASTO_CARD =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18"/><circle cx="16.5" cy="14" r="1"/></svg>';
const ICONE_META_CARD =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="0.8" fill="currentColor" stroke="none"/></svg>';
const ICONE_VIAGEM_CARD =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="m14.8 9.2-1.6 4-4 1.6 1.6-4 4-1.6Z"/></svg>';
const ICONE_CORRIGIR =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>';

// Mesmas categorias que claude_client.CAPTURE_PROMPT ensina a IA a usar -
// duplicado aqui de proposito (o front nao chama o backend so pra montar um
// <select>): se uma categoria nova entrar la, precisa entrar aqui tambem.
const CATEGORIAS_GASTO = ["mercado", "transporte", "lazer", "contas", "saude", "outros"];

// Vibracao (Vibration API): funciona no Chrome/Android, mas o Safari no
// iOS NUNCA implementou isso (decisao de plataforma da Apple, nao falta de
// suporte tecnico) - no iPhone essa chamada simplesmente nao faz nada,
// silenciosamente. Deixa aqui mesmo assim (feature-detected, sem erro em
// nenhum navegador) pra funcionar de verdade se um dia isso rodar em
// Android, ou se a Apple mudar de ideia.
function vibrar(padrao) {
  if ("vibrate" in navigator) navigator.vibrate(padrao);
}

let audioCtx = null;

function tocarTom(freqs, duracaoMs, volume = 0.09) {
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === "suspended") audioCtx.resume();
    const agora = audioCtx.currentTime;
    freqs.forEach((freq, i) => {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = "sine";
      osc.frequency.value = freq;
      const inicio = agora + i * (duracaoMs / 1000 / freqs.length) * 0.85;
      gain.gain.setValueAtTime(0, inicio);
      gain.gain.linearRampToValueAtTime(volume, inicio + 0.012);
      gain.gain.exponentialRampToValueAtTime(0.0001, inicio + duracaoMs / 1000);
      osc.connect(gain).connect(audioCtx.destination);
      osc.start(inicio);
      osc.stop(inicio + duracaoMs / 1000 + 0.02);
    });
  } catch {
    // Web Audio pode falhar por politica de autoplay antes do primeiro toque
    // do usuario, ou nao existir em navegadores antigos - som e so um extra,
    // nunca pode quebrar a acao de verdade (concluir tarefa, registrar algo).
  }
}

// dois tons curtos subindo (quinta justa) - "cling" limpo, sem ser um efeito
// de jogo/notificacao generica
const tocarSomSucesso = () => tocarTom([740, 988], 220);
const tocarSomConcluido = () => tocarTom([659, 880, 1109], 260, 0.08);

const fmtMoeda = (valor) =>
  Number(valor).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

const fmtHoras = (h) =>
  `${Number(h).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 2 })}h`;

// Horas nao tem a complexidade de moeda (sem milhar, poucas casas decimais)
// entao aceita virgula ou ponto direto, sem mascara "digito a digito".
function parseHoras(texto) {
  const limpo = (texto || "").trim().replace(",", ".");
  if (!limpo) return null;
  const n = parseFloat(limpo);
  return Number.isFinite(n) && n > 0 ? n : null;
}

// Mascara de moeda BR no estilo "digito da direita pra esquerda" (o mesmo
// dos apps de banco): o campo so guarda digitos, os 2 ultimos viram
// centavos, e o texto e sempre reconstruido do zero a cada tecla - por
// isso apagar nunca desorganiza a pontuacao nem o cursor (ele so encolhe
// a string de digitos e redesenha).
function aplicarMascaraMoeda(input) {
  input.addEventListener("input", () => {
    let digitos = input.value.replace(/\D/g, "").replace(/^0+(?=\d)/, "");
    if (!digitos) {
      input.value = "";
      return;
    }
    digitos = digitos.padStart(3, "0");
    const inteiro = digitos.slice(0, -2).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    const centavos = digitos.slice(-2);
    input.value = `${inteiro},${centavos}`;
  });
}

function valorMascaraParaNumero(texto) {
  const limpo = texto.replace(/\./g, "").replace(",", ".");
  const n = parseFloat(limpo);
  return Number.isFinite(n) ? n : 0;
}

// Mesma logica de digito-a-digito pra data: so digitos, barras entram
// sozinhas conforme a posicao - apagar so encolhe os digitos, nunca deixa
// barra sobrando nem quebra o cursor.
function aplicarMascaraData(input) {
  input.addEventListener("input", () => {
    const digitos = input.value.replace(/\D/g, "").slice(0, 8);
    const partes = [];
    if (digitos.length > 0) partes.push(digitos.slice(0, 2));
    if (digitos.length > 2) partes.push(digitos.slice(2, 4));
    if (digitos.length > 4) partes.push(digitos.slice(4, 8));
    input.value = partes.join("/");
  });
}

function mascaraDataParaIso(texto) {
  const m = texto.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (!m) return null;
  const dia = Number(m[1]);
  const mes = Number(m[2]);
  const ano = Number(m[3]);
  if (mes < 1 || mes > 12) return null;
  const diasNoMes = new Date(ano, mes, 0).getDate();
  if (dia < 1 || dia > diasNoMes) return null;
  return `${String(ano).padStart(4, "0")}-${String(mes).padStart(2, "0")}-${String(dia).padStart(2, "0")}`;
}

function mostrarErro(msg) {
  const banner = $("#erro-banner");
  banner.textContent = msg;
  banner.hidden = false;
}

function limparErro() {
  $("#erro-banner").hidden = true;
}

// 45s porque varias chamadas passam pela IA (classificacao, chat, leitura de PDF de
// cotacao) - um timeout curto demais aborta uma chamada real em andamento, nao so
// uma conexao morta.
const API_FETCH_TIMEOUT_MS = 45000;

// `fila`: so pras 2-3 acoes criticas do BRIEFING (captura, check-in) - o
// caller passa { tipo: "capture"|"checkin", id? }. Em qualquer outra chamada
// (a esmagadora maioria - leituras e a maioria das escritas), fila fica
// undefined e o comportamento e IDENTICO ao de antes: erro de rede so mostra
// mostrarErro() e devolve null. So quando fila e passado e o fetch falha por
// rede/timeout (nunca por uma resposta HTTP real, 4xx/5xx - essa nem cai
// nesse catch) e que a requisicao vira um item na fila local (IndexedDB) em
// vez de virar um erro pro usuario - devolve { __enfileirado: true } pro
// caller decidir a UX otimista (ex: mostrar como se tivesse capturado, sem
// esperar a classificacao da IA que so vai vir quando sincronizar de verdade).
async function apiFetch(url, options, fila) {
  let res;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_FETCH_TIMEOUT_MS);
  try {
    res = await fetch(url, { ...options, signal: controller.signal });
  } catch (e) {
    if (fila) {
      try {
        await FilaOffline.enfileirar({
          url,
          method: options && options.method,
          headers: options && options.headers,
          body: options && options.body,
          tipo: fila.tipo,
          id: fila.id,
        });
        atualizarIndicadorOffline(await FilaOffline.contar());
        return { __enfileirado: true };
      } catch {
        // IndexedDB tambem falhou (raro - modo privado, quota cheia): cai
        // pro comportamento de erro normal em vez de fingir que deu certo.
      }
    }
    mostrarErro(
      e && e.name === "AbortError"
        ? "O painel demorou demais pra responder. Tenta de novo."
        : "Sem conexao com o servidor. Confere se o painel esta rodando."
    );
    return null;
  } finally {
    clearTimeout(timeoutId);
  }
  let data = null;
  try {
    data = await res.json();
  } catch {
    // resposta sem corpo (ex: 204) - segue com data null
  }
  if (res.status === 401) {
    window.location.href = "/login";
    return null;
  }
  if (!res.ok) {
    mostrarErro((data && data.error) || `Erro inesperado (HTTP ${res.status}).`);
    return null;
  }
  limparErro();
  return data;
}

// Ordem das abas na barra - usada so pra saber se a troca "avança" ou
// "volta" e entrar do lado certo (slide pra direita indo pra frente, pra
// esquerda voltando) - o mesmo tipo de pista de direcao que apps premium
// usam em transicao de aba, em vez de um fade generico igual pra qualquer
// troca.
const ORDEM_ABAS = ["hoje", "painel", "vida", "tarefas", "gastos", "bancos", "construtora", "aviacao"];
let abaAtual = "hoje";

function showTab(name) {
  const indiceAtual = ORDEM_ABAS.indexOf(abaAtual);
  const indiceNovo = ORDEM_ABAS.indexOf(name);
  const direcao =
    indiceNovo > indiceAtual ? "entra-direita" : indiceNovo < indiceAtual ? "entra-esquerda" : null;
  abaAtual = name;

  document.querySelectorAll(".tab-content").forEach((el) => {
    el.classList.remove("entra-direita", "entra-esquerda");
    el.hidden = el.id !== `tab-${name}`;
  });
  if (direcao) {
    document.getElementById(`tab-${name}`).classList.add(direcao);
  }
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === name);
  });
  if (name === "painel") {
    loadSummary();
    loadAgenda();
    loadFechamentoDoDia();
    loadSaude();
    loadMemorias();
    loadLembretes();
    loadMedicamentos();
    loadMedidas();
    loadEsperas();
    loadNotas();
  }
  if (name === "tarefas") loadTasks();
  if (name === "gastos") {
    loadExpenses();
    loadMetas();
  }
  if (name === "bancos") loadBancos();
  if (name === "construtora") {
    loadConstrutora();
    loadCotacoes();
  }
  if (name === "aviacao") loadVoosResumo();
}

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => showTab(btn.dataset.tab));
});

function setBotaoCarregando(btn, carregando, rotulo) {
  if (carregando) {
    if (btn.dataset.htmlOriginal === undefined) btn.dataset.htmlOriginal = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span>${rotulo}`;
  } else {
    btn.disabled = false;
    btn.innerHTML = btn.dataset.htmlOriginal !== undefined ? btn.dataset.htmlOriginal : rotulo;
  }
}

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

function pulsarSucesso(el) {
  el.classList.remove("sucesso");
  // forca reflow pra animacao reiniciar mesmo em capturas seguidas
  void el.offsetWidth;
  el.classList.add("sucesso");
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
  eyebrow.innerHTML = `${ICONE_TAREFA_CARD}<span>Sem conexao - salvo, vai sincronizar</span>`;
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
    banner.textContent = `Sem conexao - ${n} ${n === 1 ? "item pendente" : "itens pendentes"}, vai sincronizar quando voltar.`;
    banner.hidden = false;
  } else {
    banner.hidden = true;
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
      aviso.textContent = `Capturado offline, mas ficou em duvida: "${data.duvida}". Repete a captura quando puder pra confirmar.`;
      $("#chat-mensagens").appendChild(aviso);
    } else if (data) {
      const novoCard = criarCardResultado(data);
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
    mostrarErro((corpo && corpo.error) || `Nao consegui sincronizar um item pendente (HTTP ${status}). Foi descartado.`);
  });
}

async function enviarCaptura(text, clarificacao) {
  const capturaBtn = $("#captura-btn");
  const duvidaBtn = $("#duvida-btn");
  setBotaoCarregando(capturaBtn, true, "Pensando...");
  duvidaBtn.disabled = true;

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

  if (!data) return;

  if (data.__enfileirado) {
    // otimista: o Alex nao pode ficar sem poder anotar nada so por falta de
    // sinal - mostra como se tivesse dado certo, sincroniza sozinho depois.
    textoPendente = null;
    $("#duvida-box").hidden = true;
    pulsarSucesso($("#captura-input"));
    vibrar(20);
    const listaChat = $("#chat-mensagens");
    listaChat.querySelector(".chat-vazio")?.remove();
    listaChat.appendChild(criarCardCapturaPendente(clientId, text));
    listaChat.scrollTop = listaChat.scrollHeight;
    return;
  }

  loadUso();

  if (data.duvida) {
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
  const listaChat = $("#chat-mensagens");
  listaChat.querySelector(".chat-vazio")?.remove();
  listaChat.appendChild(criarCardResultado(data));
  listaChat.scrollTop = listaChat.scrollHeight;
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
  enviarCaptura(text, "");
});

$("#captura-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") $("#captura-btn").click();
});

$("#duvida-btn").addEventListener("click", () => {
  const resposta = $("#duvida-input").value.trim();
  if (!resposta || !textoPendente) return;
  enviarCaptura(textoPendente, resposta);
});

$("#duvida-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") $("#duvida-btn").click();
});

function animarNumero(el, valorFinal, formatador) {
  el.classList.remove("shimmer");
  const duracao = 420;
  const inicio = performance.now();
  function passo(agora) {
    const progresso = Math.min(1, (agora - inicio) / duracao);
    const suavizado = 1 - Math.pow(1 - progresso, 3);
    const valorAtual = valorFinal * suavizado;
    el.textContent = formatador ? formatador(valorAtual) : Math.round(valorAtual);
    if (progresso < 1) {
      requestAnimationFrame(passo);
    } else {
      el.classList.remove("num-pop");
      void el.offsetWidth;
      el.classList.add("num-pop");
    }
  }
  requestAnimationFrame(passo);
}

function explodirConcluido(origemEl) {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const r = origemEl.getBoundingClientRect();
  const cx = r.left + r.width / 2;
  const cy = r.top + r.height / 2;

  const wrap = document.createElement("div");
  wrap.className = "burst-wrap";
  wrap.style.left = `${cx}px`;
  wrap.style.top = `${cy}px`;
  wrap.appendChild(document.createElement("span")).className = "burst-anel";

  const cores = ["var(--cor-financeiro)", "var(--accent)", "var(--accent-2)", "var(--cor-bancos)"];
  const total = 8;
  for (let i = 0; i < total; i++) {
    const ang = (Math.PI * 2 * i) / total + (Math.random() - 0.5) * 0.5;
    const dist = 30 + Math.random() * 18;
    const p = document.createElement("span");
    p.className = "burst-particula";
    p.style.setProperty("--tx", `${Math.cos(ang) * dist}px`);
    p.style.setProperty("--ty", `${Math.sin(ang) * dist}px`);
    p.style.background = cores[i % cores.length];
    wrap.appendChild(p);
  }
  document.body.appendChild(wrap);
  setTimeout(() => wrap.remove(), 650);
}

// Cache do ultimo resumo com sucesso (so o texto/numeros, nada de PII alem do que ja
// aparece na tela) - se abrir o painel sem rede, mostra o ultimo estado conhecido em
// vez de uma tela vazia. Por viewer/dispositivo so, nunca sincroniza entre aparelhos -
// e so uma conveniencia visual, cada leitura/escrita protegida (localStorage pode
// falhar ou nao existir: aba anonima, storage bloqueado etc).
const CHAVE_CACHE_RESUMO = "painel:ultimo-resumo";

function salvarResumoCache(data) {
  try {
    localStorage.setItem(CHAVE_CACHE_RESUMO, JSON.stringify(data));
  } catch {
    // ignora - cache e so uma conveniencia, nunca deve quebrar o carregamento
  }
}

function lerResumoCache() {
  try {
    const bruto = localStorage.getItem(CHAVE_CACHE_RESUMO);
    return bruto ? JSON.parse(bruto) : null;
  } catch {
    return null;
  }
}

async function loadSummary() {
  const resumoEl = $("#resumo-texto");
  resumoEl.classList.add("carregando");
  resumoEl.textContent = "Carregando...";

  const [data, tasks, metas] = await Promise.all([
    apiFetch("/api/summary/today"),
    apiFetch("/api/tasks"),
    apiFetch("/api/metas"),
  ]);

  if (tasks) animarNumero($("#stat-tarefas"), tasks.length);
  if (metas) {
    const ativas = metas.filter((m) => m.valor_guardado < m.valor_alvo).length;
    animarNumero($("#stat-metas"), ativas);
  }

  resumoEl.classList.remove("carregando");

  const dadosPraMostrar = data || lerResumoCache();
  if (!dadosPraMostrar) {
    resumoEl.textContent = "Nao consegui gerar o resumo agora.";
    return;
  }
  animarNumero($("#stat-gasto"), dadosPraMostrar.gasto_hoje, fmtMoeda);
  const planejadoEl = $("#stat-gasto-planejado");
  if (dadosPraMostrar.gasto_planejado > 0) {
    planejadoEl.textContent = `+${fmtMoeda(dadosPraMostrar.gasto_planejado)} planejado`;
    planejadoEl.hidden = false;
  } else {
    planejadoEl.hidden = true;
  }
  resumoEl.textContent = dadosPraMostrar.summary;
  $("#resumo-stats").textContent = data
    ? `${data.tarefas_concluidas} tarefa(s) concluida(s) hoje`
    : `${dadosPraMostrar.tarefas_concluidas} tarefa(s) concluida(s) - sem conexao, mostrando o ultimo resumo salvo`;

  if (data) salvarResumoCache(data);
}

async function loadStreak() {
  const data = await apiFetch("/api/streak");
  const chip = $("#streak-chip");
  if (!data || data.dias < 1) {
    chip.hidden = true;
    return;
  }
  $("#streak-texto").textContent =
    data.dias === 1 ? "1 dia seguido usando o painel" : `${data.dias} dias seguidos usando o painel`;
  chip.hidden = false;
}

let climaUltimoLoad = 0;

async function loadClimaHoje() {
  climaUltimoLoad = Date.now();
  const data = await apiFetch("/api/clima/hoje");
  const chip = $("#clima-chip");
  if (!data || !data.configurado || data.erro) {
    chip.hidden = true;
    return;
  }
  chip.classList.toggle("alerta", Boolean(data.alerta));
  const prefixo = data.chovendo_agora ? "Chovendo agora - " : "";
  $("#clima-texto").textContent = `${prefixo}${data.cidade}: ${data.texto}`;
  chip.hidden = false;
}

// a previsao so e buscada de novo (a) a cada 20min, pra acompanhar a hora
// "agora" avancando sem precisar recarregar a pagina, e (b) quando volta
// pra aba depois de um tempo longe - assim um PWA deixado aberto o dia
// inteiro nao fica mostrando a janela de chuva calculada de manha
setInterval(loadClimaHoje, 20 * 60 * 1000);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && Date.now() - climaUltimoLoad > 5 * 60 * 1000) {
    loadClimaHoje();
  }
  if (document.visibilityState === "visible") loadUberPendentes();
});

async function loadUberPendentes() {
  const data = await apiFetch("/api/uber/pedidos");
  const box = $("#uber-pendentes");
  box.innerHTML = "";
  if (!data || data.length === 0) return;

  data.forEach((p) => {
    const card = document.createElement("div");
    card.className = "uber-pendente-card";

    const titulo = document.createElement("p");
    titulo.className = "uber-pendente-titulo";
    titulo.textContent = `Uber pra ${p.destino}`;
    card.appendChild(titulo);

    const preco = document.createElement("p");
    preco.className = "uber-pendente-preco";
    preco.textContent = p.preco_texto || "preco nao disponivel";
    card.appendChild(preco);

    const acoes = document.createElement("div");
    acoes.className = "uber-pendente-acoes";

    const btnConfirmar = document.createElement("button");
    btnConfirmar.className = "uber-btn-confirmar";
    btnConfirmar.textContent = "Confirmar";
    btnConfirmar.addEventListener("click", async () => {
      btnConfirmar.disabled = true;
      btnCancelar.disabled = true;
      const r = await apiFetch(`/api/uber/pedidos/${p.id}/confirmar`, { method: "POST" });
      if (r && r.ok) {
        loadUberPendentes();
      } else {
        btnConfirmar.disabled = false;
        btnCancelar.disabled = false;
      }
    });

    const btnCancelar = document.createElement("button");
    btnCancelar.className = "uber-btn-cancelar";
    btnCancelar.textContent = "Cancelar";
    btnCancelar.addEventListener("click", async () => {
      btnConfirmar.disabled = true;
      btnCancelar.disabled = true;
      await apiFetch(`/api/uber/pedidos/${p.id}/cancelar`, { method: "POST" });
      loadUberPendentes();
    });

    acoes.appendChild(btnConfirmar);
    acoes.appendChild(btnCancelar);
    card.appendChild(acoes);
    box.appendChild(card);
  });
}

function fmtHora(isoString) {
  const d = new Date(isoString);
  return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

async function loadAgenda() {
  const data = await apiFetch("/api/calendario/hoje");
  if (!data) return;

  $("#agenda-desconectada").hidden = data.configurado;

  const list = $("#lista-agenda");
  list.innerHTML = "";
  $("#agenda-vazio").hidden = data.eventos.length > 0;

  // linha do tempo (inspirada no Tiimo): em vez de so uma lista de texto, cada
  // compromisso marca sua posicao na linha vertical - o que ja passou fica
  // apagado, o proximo que ainda vai acontecer ganha destaque, pra ajudar
  // com cegueira de tempo (comum em TDAH) a bater o olho e saber onde esta
  // no dia sem ter que ler tudo.
  const agora = new Date();
  let proximoMarcado = false;

  data.eventos.forEach((ev) => {
    const li = document.createElement("li");
    li.className = "item";

    if (!ev.dia_inteiro) {
      const jaPassou = new Date(ev.fim) < agora;
      if (ev.origem === "tarefa" && ev.concluido) {
        // concluida: bolinha verde, mesmo se foi feita adiantada (antes do horario)
        li.classList.add("concluido");
      } else if (ev.origem === "tarefa" && jaPassou) {
        // tarefa com horario que passou e nao foi marcada como feita: bolinha vermelha
        li.classList.add("perdido");
      } else if (jaPassou) {
        // compromisso de calendario nao tem como confirmar presenca - fica so apagado, sem julgar
        li.classList.add("passado");
      } else if (!proximoMarcado) {
        li.classList.add("proximo");
        proximoMarcado = true;
      }
    }

    const titulo = document.createElement("span");
    titulo.className = "item-titulo";
    titulo.textContent = ev.titulo;
    if (ev.origem === "tarefa") {
      const tag = document.createElement("span");
      tag.className = "item-tag-tarefa";
      tag.textContent = "tarefa";
      titulo.appendChild(tag);
    }
    if (li.classList.contains("proximo")) {
      const badge = document.createElement("span");
      badge.className = "item-badge-proximo";
      badge.textContent = "proximo";
      titulo.appendChild(badge);
    }
    const horario = document.createElement("span");
    horario.className = "item-quando";
    horario.textContent = ev.dia_inteiro
      ? "dia todo"
      : ev.inicio === ev.fim
      ? fmtHora(ev.inicio)
      : `${fmtHora(ev.inicio)} - ${fmtHora(ev.fim)}`;
    li.appendChild(titulo);
    li.appendChild(horario);
    list.appendChild(li);
  });
}

async function loadFechamentoDoDia() {
  const data = await apiFetch("/api/fechamento-do-dia");
  if (!data) return;

  const concluidasEl = $("#fechamento-concluidas");
  concluidasEl.textContent =
    data.concluidas.length > 0
      ? `Feito hoje: ${data.concluidas.join(", ")}.`
      : "Nada concluido hoje ainda.";

  const pendentesEl = $("#fechamento-pendentes");
  pendentesEl.textContent =
    data.pendentes_hoje.length > 0
      ? `Ainda fica pra depois: ${data.pendentes_hoje.join(", ")}.`
      : "Nada ficou pra tras hoje.";
}

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
    btn.addEventListener("click", () => falarTexto(btn, texto));
  }
  return btn;
}

// Ritmo humano (pedido explicito: "diferentes ritmos... mas nao algo devagar"):
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
  historico.forEach((m) => lista.appendChild(criarBolhaChat(m.papel, m.texto)));
  lista.scrollTop = lista.scrollHeight;
}

async function enviarChat(texto) {
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

  const data = await apiFetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mensagem: texto }),
  });

  digitando.remove();
  setBotaoCarregando(btn, false, "Enviar");
  if (!data) return;

  lista.appendChild(criarBolhaChat("assistant", data.resposta, true));
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

async function loadSaude() {
  const data = await apiFetch("/api/saude/hoje");
  if (!data) return;

  const dados = data.dados;
  const temAlgumDado =
    dados && (dados.passos != null || dados.distancia_km != null || dados.sono_horas != null);

  $("#saude-vazio").hidden = temAlgumDado;
  $("#saude-grid").hidden = !temAlgumDado;
  $("#hidratacao-total").textContent = data.hidratacao_hoje ?? 0;

  const dicaSono = $("#dica-sono");
  dicaSono.hidden = !data.dica_sono;
  dicaSono.textContent = data.dica_sono || "";
  const dicaHumor = $("#dica-humor");
  dicaHumor.hidden = !data.dica_humor;
  dicaHumor.textContent = data.dica_humor || "";

  if (!temAlgumDado) return;

  $("#saude-passos").textContent = dados.passos != null ? dados.passos.toLocaleString("pt-BR") : "-";
  $("#saude-distancia").textContent = dados.distancia_km != null ? dados.distancia_km.toFixed(1) : "-";
  $("#saude-sono").textContent = dados.sono_horas != null ? dados.sono_horas.toFixed(1) : "-";
}

$("#hidratacao-btn").addEventListener("click", async () => {
  const btn = $("#hidratacao-btn");
  btn.disabled = true;
  const data = await apiFetch("/api/hidratacao", { method: "POST" });
  btn.disabled = false;
  if (!data) return;
  $("#hidratacao-total").textContent = data.total_hoje;
  pulsarSucesso($("#hidratacao-total"));
});

async function loadMedidas() {
  const medidas = await apiFetch("/api/medidas");
  if (!medidas) return;

  const list = $("#lista-medidas");
  list.innerHTML = "";
  $("#medidas-vazio").hidden = medidas.length > 0;

  const tipoJaMostrouTendencia = new Set();

  medidas.forEach((m, idx) => {
    const li = document.createElement("li");
    li.className = "item";

    const linha = document.createElement("div");
    linha.className = "item-linha";

    const tituloWrap = document.createElement("div");
    const titulo = document.createElement("span");
    titulo.className = "item-titulo";
    titulo.textContent = `${m.tipo}: ${m.valor}${m.unidade}`;
    tituloWrap.appendChild(titulo);

    const quando = document.createElement("span");
    quando.className = "item-quando";
    quando.textContent = fmtDataBr(m.data);
    tituloWrap.appendChild(quando);

    // So o registro mais recente de cada tipo ganha a tendencia (comparado
    // com o registro anterior mais proximo do MESMO tipo) - historico antigo
    // fica so como lista, sem repetir a mesma seta em cada linha.
    if (!tipoJaMostrouTendencia.has(m.tipo)) {
      tipoJaMostrouTendencia.add(m.tipo);
      const anterior = medidas.slice(idx + 1).find((x) => x.tipo === m.tipo);
      if (anterior && anterior.valor !== m.valor) {
        const tendencia = document.createElement("span");
        const subiu = m.valor > anterior.valor;
        const delta = (m.valor - anterior.valor).toFixed(1);
        tendencia.className = `medida-tendencia ${subiu ? "subiu" : "desceu"}`;
        tendencia.textContent = subiu ? `+${delta}` : delta;
        tituloWrap.appendChild(tendencia);
      }
    }
    linha.appendChild(tituloWrap);

    const acoes = document.createElement("div");
    acoes.className = "item-acoes";
    const apagarBtn = document.createElement("button");
    apagarBtn.className = "btn-com-icone";
    apagarBtn.innerHTML = `${ICONE_TRASH}Apagar`;
    apagarBtn.addEventListener("click", async () => {
      apagarBtn.disabled = true;
      const ok = await apiFetch(`/api/medidas/${m.id}`, { method: "DELETE" });
      if (ok) {
        li.classList.add("saindo");
        setTimeout(() => li.remove(), 250);
      } else {
        apagarBtn.disabled = false;
      }
    });
    acoes.appendChild(apagarBtn);
    linha.appendChild(acoes);

    li.appendChild(linha);
    list.appendChild(li);
  });
}

$("#medida-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#medida-btn");
  const tipoInput = $("#medida-tipo");
  const valorInput = $("#medida-valor");
  const unidadeInput = $("#medida-unidade");
  const tipo = tipoInput.value.trim();
  const valor = valorInput.value.trim();
  if (!tipo || !valor) {
    mostrarErro("Confere o tipo e o valor da medida.");
    return;
  }

  setBotaoCarregando(btn, true, "salvando...");
  const data = await apiFetch("/api/medidas", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tipo, valor: Number(valor), unidade: unidadeInput.value.trim() }),
  });
  setBotaoCarregando(btn, false, "Adicionar");
  if (!data) return;

  tipoInput.value = "";
  valorInput.value = "";
  unidadeInput.value = "";
  pulsarSucesso(tipoInput);
  loadMedidas();
});

async function loadMemorias() {
  const memorias = await apiFetch("/api/memorias");
  if (!memorias) return;

  const list = $("#lista-memorias");
  list.innerHTML = "";
  $("#memorias-vazio").hidden = memorias.length > 0;

  memorias.forEach((m) => {
    const li = document.createElement("li");
    li.className = "item";

    const linha = document.createElement("div");
    linha.className = "item-linha";

    const titulo = document.createElement("span");
    titulo.className = "item-titulo";
    titulo.textContent = m.texto;
    linha.appendChild(titulo);

    const acoes = document.createElement("div");
    acoes.className = "item-acoes";
    const apagarBtn = document.createElement("button");
    apagarBtn.className = "btn-com-icone";
    apagarBtn.innerHTML = `${ICONE_TRASH}Apagar`;
    apagarBtn.addEventListener("click", async () => {
      apagarBtn.disabled = true;
      const ok = await apiFetch(`/api/memorias/${m.id}`, { method: "DELETE" });
      if (ok) {
        li.classList.add("saindo");
        setTimeout(() => li.remove(), 250);
      } else {
        apagarBtn.disabled = false;
      }
    });
    acoes.appendChild(apagarBtn);
    linha.appendChild(acoes);

    li.appendChild(linha);
    list.appendChild(li);
  });
}

function fmtDataBr(isoDate) {
  const [ano, mes, dia] = isoDate.split("-");
  return `${dia}/${mes}/${ano}`;
}

async function loadLembretes() {
  const lembretes = await apiFetch("/api/lembretes");
  if (!lembretes) return;

  const list = $("#lista-lembretes");
  list.innerHTML = "";
  $("#lembretes-vazio").hidden = lembretes.length > 0;

  lembretes.forEach((l) => {
    const li = document.createElement("li");
    li.className = "item";

    const linha = document.createElement("div");
    linha.className = "item-linha";

    const tituloWrap = document.createElement("div");
    const titulo = document.createElement("span");
    titulo.className = "item-titulo";
    titulo.textContent = l.titulo;
    tituloWrap.appendChild(titulo);
    const quando = document.createElement("span");
    quando.className = "item-quando";
    // proxima_ocorrencia (calculada no backend) em vez de l.data crua - pra
    // um lembrete recorrente mostrar o PROXIMO aniversario da data, nao o
    // ano em que ele foi cadastrado originalmente.
    const dataMostrada = l.proxima_ocorrencia || l.data;
    quando.textContent = l.recorrente ? `${fmtDataBr(dataMostrada)} - todo ano` : fmtDataBr(dataMostrada);
    tituloWrap.appendChild(quando);

    if (typeof l.dias_restantes === "number") {
      const contagem = document.createElement("span");
      const urgente = l.dias_restantes <= 7;
      contagem.className = urgente ? "item-quando lembrete-contagem-urgente" : "item-quando";
      contagem.textContent =
        l.dias_restantes < 0
          ? `passou ha ${Math.abs(l.dias_restantes)} dia(s)`
          : l.dias_restantes === 0
          ? "e hoje"
          : l.dias_restantes === 1
          ? "e amanha"
          : `faltam ${l.dias_restantes} dias`;
      tituloWrap.appendChild(contagem);
    }
    if (l.sugestao && typeof l.dias_restantes === "number" && l.dias_restantes <= 7) {
      const sugestao = document.createElement("span");
      sugestao.className = "item-quando lembrete-sugestao";
      sugestao.textContent = l.sugestao;
      tituloWrap.appendChild(sugestao);
    }
    linha.appendChild(tituloWrap);

    const acoes = document.createElement("div");
    acoes.className = "item-acoes";
    const apagarBtn = document.createElement("button");
    apagarBtn.className = "btn-com-icone";
    apagarBtn.innerHTML = `${ICONE_TRASH}Apagar`;
    apagarBtn.addEventListener("click", async () => {
      apagarBtn.disabled = true;
      const ok = await apiFetch(`/api/lembretes/${l.id}`, { method: "DELETE" });
      if (ok) {
        li.classList.add("saindo");
        setTimeout(() => li.remove(), 250);
      } else {
        apagarBtn.disabled = false;
      }
    });
    acoes.appendChild(apagarBtn);
    linha.appendChild(acoes);

    li.appendChild(linha);
    list.appendChild(li);
  });
}

aplicarMascaraData($("#lembrete-data"));

$("#lembrete-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#lembrete-btn");
  const tituloInput = $("#lembrete-titulo");
  const dataInput = $("#lembrete-data");
  const titulo = tituloInput.value.trim();
  const dataIso = mascaraDataParaIso(dataInput.value.trim());
  if (!titulo || !dataIso) {
    mostrarErro("Confere o titulo e a data (dd/mm/aaaa).");
    return;
  }

  setBotaoCarregando(btn, true, "salvando...");
  const data = await apiFetch("/api/lembretes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      titulo,
      data: dataIso,
      recorrente: $("#lembrete-recorrente").checked,
    }),
  });
  setBotaoCarregando(btn, false, "Adicionar");
  if (!data) return;

  tituloInput.value = "";
  dataInput.value = "";
  $("#lembrete-recorrente").checked = false;
  pulsarSucesso(tituloInput);
  loadLembretes();
  loadStreak();
});

async function loadMedicamentos() {
  const medicamentos = await apiFetch("/api/medicamentos");
  if (!medicamentos) return;

  const list = $("#lista-medicamentos");
  list.innerHTML = "";
  $("#medicamentos-vazio").hidden = medicamentos.length > 0;

  medicamentos.forEach((m) => {
    const li = document.createElement("li");
    li.className = "item";

    const linha = document.createElement("div");
    linha.className = "item-linha";

    const tituloWrap = document.createElement("div");
    const titulo = document.createElement("span");
    titulo.className = "item-titulo";
    titulo.textContent = m.dosagem ? `${m.nome} - ${m.dosagem}` : m.nome;
    tituloWrap.appendChild(titulo);
    const quando = document.createElement("span");
    quando.className = "item-quando";
    quando.textContent = `todo dia as ${m.horario}`;
    tituloWrap.appendChild(quando);
    linha.appendChild(tituloWrap);

    const acoes = document.createElement("div");
    acoes.className = "item-acoes";
    const apagarBtn = document.createElement("button");
    apagarBtn.className = "btn-com-icone";
    apagarBtn.innerHTML = `${ICONE_TRASH}Apagar`;
    apagarBtn.addEventListener("click", async () => {
      apagarBtn.disabled = true;
      const ok = await apiFetch(`/api/medicamentos/${m.id}`, { method: "DELETE" });
      if (ok) {
        li.classList.add("saindo");
        setTimeout(() => li.remove(), 250);
      } else {
        apagarBtn.disabled = false;
      }
    });
    acoes.appendChild(apagarBtn);
    linha.appendChild(acoes);

    li.appendChild(linha);
    list.appendChild(li);
  });
}

$("#medicamento-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#medicamento-btn");
  const nomeInput = $("#medicamento-nome");
  const dosagemInput = $("#medicamento-dosagem");
  const horarioInput = $("#medicamento-horario");
  const nome = nomeInput.value.trim();
  const horario = horarioInput.value.trim();
  if (!nome || !horario) {
    mostrarErro("Confere o nome e o horario do remedio.");
    return;
  }

  setBotaoCarregando(btn, true, "salvando...");
  const data = await apiFetch("/api/medicamentos", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      nome,
      dosagem: dosagemInput.value.trim(),
      horario,
    }),
  });
  setBotaoCarregando(btn, false, "Adicionar");
  if (!data) return;

  nomeInput.value = "";
  dosagemInput.value = "";
  horarioInput.value = "";
  pulsarSucesso(nomeInput);
  loadMedicamentos();
});

async function loadEsperas() {
  const esperas = await apiFetch("/api/esperas");
  if (!esperas) return;

  const list = $("#lista-esperas");
  list.innerHTML = "";
  $("#esperas-vazio").hidden = esperas.length > 0;

  esperas.forEach((esp) => {
    const li = document.createElement("li");
    li.className = "item";

    const linha = document.createElement("div");
    linha.className = "item-linha";

    const tituloWrap = document.createElement("div");
    const titulo = document.createElement("span");
    titulo.className = "item-titulo";
    titulo.textContent = esp.quem;
    tituloWrap.appendChild(titulo);
    const sobre = document.createElement("span");
    sobre.className = "item-quando";
    sobre.textContent = esp.sobre;
    tituloWrap.appendChild(sobre);
    linha.appendChild(tituloWrap);

    const acoes = document.createElement("div");
    acoes.className = "item-acoes";

    const resolverBtn = document.createElement("button");
    resolverBtn.className = "btn-com-icone primario";
    resolverBtn.innerHTML = `${ICONE_CHECK}Resolvido`;
    resolverBtn.addEventListener("click", async () => {
      resolverBtn.disabled = true;
      const ok = await apiFetch(`/api/esperas/${esp.id}/resolver`, { method: "POST" });
      if (ok) {
        li.classList.add("saindo");
        setTimeout(() => li.remove(), 250);
      } else {
        resolverBtn.disabled = false;
      }
    });
    acoes.appendChild(resolverBtn);

    const apagarBtn = document.createElement("button");
    apagarBtn.className = "btn-com-icone";
    apagarBtn.innerHTML = ICONE_TRASH;
    apagarBtn.setAttribute("aria-label", "Apagar");
    apagarBtn.addEventListener("click", async () => {
      apagarBtn.disabled = true;
      const ok = await apiFetch(`/api/esperas/${esp.id}`, { method: "DELETE" });
      if (ok) {
        li.classList.add("saindo");
        setTimeout(() => li.remove(), 250);
      } else {
        apagarBtn.disabled = false;
      }
    });
    acoes.appendChild(apagarBtn);

    linha.appendChild(acoes);
    li.appendChild(linha);
    list.appendChild(li);
  });
}

async function loadNotas() {
  const notas = await apiFetch("/api/notas");
  if (!notas) return;

  const list = $("#lista-notas");
  list.innerHTML = "";
  $("#notas-vazio").hidden = notas.length > 0;

  notas.forEach((n) => {
    const li = document.createElement("li");
    li.className = "item";

    const linha = document.createElement("div");
    linha.className = "item-linha";

    const tituloWrap = document.createElement("div");
    const titulo = document.createElement("span");
    titulo.className = "item-titulo";
    titulo.textContent = n.titulo;
    tituloWrap.appendChild(titulo);

    const corpo = document.createElement("span");
    corpo.className = "item-quando";
    corpo.textContent = n.corpo.length > 140 ? `${n.corpo.slice(0, 140)}...` : n.corpo;
    tituloWrap.appendChild(corpo);

    if (n.tags) {
      const tags = document.createElement("span");
      tags.className = "item-quando";
      tags.textContent = n.tags
        .split(",")
        .map((t) => `#${t}`)
        .join(" ");
      tituloWrap.appendChild(tags);
    }
    linha.appendChild(tituloWrap);

    const acoes = document.createElement("div");
    acoes.className = "item-acoes";
    const apagarBtn = document.createElement("button");
    apagarBtn.className = "btn-com-icone";
    apagarBtn.innerHTML = ICONE_TRASH;
    apagarBtn.setAttribute("aria-label", "Apagar");
    apagarBtn.addEventListener("click", async () => {
      apagarBtn.disabled = true;
      const ok = await apiFetch(`/api/notas/${n.id}`, { method: "DELETE" });
      if (ok) {
        li.classList.add("saindo");
        setTimeout(() => li.remove(), 250);
      } else {
        apagarBtn.disabled = false;
      }
    });
    acoes.appendChild(apagarBtn);
    linha.appendChild(acoes);

    li.appendChild(linha);
    list.appendChild(li);
  });
}

$("#espera-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#espera-btn");
  const quemInput = $("#espera-quem");
  const sobreInput = $("#espera-sobre");
  const quem = quemInput.value.trim();
  const sobre = sobreInput.value.trim();
  if (!quem || !sobre) {
    mostrarErro("Confere quem e sobre o que voce esta esperando.");
    return;
  }

  setBotaoCarregando(btn, true, "salvando...");
  const data = await apiFetch("/api/esperas", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ quem, sobre }),
  });
  setBotaoCarregando(btn, false, "Adicionar");
  if (!data) return;

  quemInput.value = "";
  sobreInput.value = "";
  pulsarSucesso(quemInput);
  loadEsperas();
  loadStreak();
});

async function loadUso() {
  const data = await apiFetch("/api/uso/total");
  if (!data) return;
  $("#uso-custo").textContent = `gasto com IA ate agora: ${fmtMoeda(data.custo_usd)}`;
}

function criarItemTarefa(t) {
  const li = document.createElement("li");
  li.className = "item";

  const linha = document.createElement("div");
  linha.className = "item-linha";

  const tituloWrap = document.createElement("div");
  const titulo = document.createElement("span");
  titulo.className = "item-titulo";
  titulo.textContent = t.title;
  if (t.recorrente_origem_id) {
    const tagRotina = document.createElement("span");
    tagRotina.className = "item-tag-tarefa";
    tagRotina.textContent = "rotina";
    titulo.appendChild(tagRotina);
  }
  tituloWrap.appendChild(titulo);
  if (t.due_at || t.hora) {
    const quando = document.createElement("span");
    quando.className = "item-quando";
    const base = t.due_at || "hoje";
    quando.textContent = t.hora ? `${base} as ${t.hora}` : base;
    tituloWrap.appendChild(quando);
  }

  const acoes = document.createElement("div");
  acoes.className = "item-acoes";

  if (t.empacada_dias) {
    const tagTravada = document.createElement("span");
    tagTravada.className = "item-tag-travada";
    tagTravada.textContent = `travada ha ${t.empacada_dias} dias`;
    titulo.appendChild(tagTravada);

    const btnRequebrar = document.createElement("button");
    btnRequebrar.className = "btn-com-icone";
    btnRequebrar.innerHTML = `${ICONE_PASSOS}quebrar diferente`;
    btnRequebrar.addEventListener("click", async () => {
      setBotaoCarregando(btnRequebrar, true, "pensando...");
      const data = await apiFetch(`/api/tasks/${t.id}/requebrar`, { method: "POST" });
      if (data) loadTasks();
      else setBotaoCarregando(btnRequebrar, false, "quebrar diferente");
    });
    acoes.appendChild(btnRequebrar);
  } else if (t.subtasks.length === 0) {
    const btnQuebrar = document.createElement("button");
    btnQuebrar.className = "btn-com-icone";
    btnQuebrar.innerHTML = `${ICONE_PASSOS}quebrar em passos`;
    btnQuebrar.addEventListener("click", async () => {
      setBotaoCarregando(btnQuebrar, true, "quebrando...");
      const data = await apiFetch(`/api/tasks/${t.id}/breakdown`, { method: "POST" });
      if (data) loadTasks();
      else setBotaoCarregando(btnQuebrar, false, "quebrar em passos");
    });
    acoes.appendChild(btnQuebrar);
  }

  if (t.fichas_treino && t.fichas_treino.length && typeof botaoFichaTreino === "function") {
    acoes.appendChild(botaoFichaTreino(t, li));
  }

  const btnCorrigir = document.createElement("button");
  btnCorrigir.className = "btn-com-icone";
  btnCorrigir.title = "isso nao e uma tarefa?";
  btnCorrigir.innerHTML = ICONE_CORRIGIR;
  btnCorrigir.addEventListener("click", () => {
    const jaAberto = li.querySelector(".correcao-form");
    if (jaAberto) {
      jaAberto.remove();
      return;
    }
    li.appendChild(criarFormularioTarefaParaGasto(t, li));
  });
  acoes.appendChild(btnCorrigir);

  const btnConcluir = document.createElement("button");
  btnConcluir.className = "primario btn-com-icone";
  btnConcluir.innerHTML = `${ICONE_CHECK}concluir`;
  btnConcluir.addEventListener("click", async () => {
    const data = await apiFetch(`/api/tasks/${t.id}/complete`, { method: "POST" });
    if (data) {
      explodirConcluido(btnConcluir);
      vibrar(30);
      tocarSomConcluido();
      li.classList.add("saindo");
      setTimeout(() => {
        loadTasks();
        loadSummary();
        loadStreak();
        if (!$("#tab-painel").hidden) loadFechamentoDoDia();
      }, 220);
    }
  });
  acoes.appendChild(btnConcluir);

  linha.appendChild(tituloWrap);
  linha.appendChild(acoes);
  li.appendChild(linha);

  if (t.subtasks.length > 0) {
    const sub = document.createElement("ul");
    sub.className = "subtarefas";
    t.subtasks.forEach((s) => {
      const subLi = document.createElement("li");
      subLi.className = "subtarefa" + (s.completed_at ? " concluida" : "");

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = Boolean(s.completed_at);
      checkbox.disabled = Boolean(s.completed_at);
      checkbox.addEventListener("change", async () => {
        const data = await apiFetch(`/api/subtasks/${s.id}/complete`, { method: "POST" });
        if (data) loadTasks();
      });

      const label = document.createElement("span");
      label.textContent = s.title;

      subLi.appendChild(checkbox);
      subLi.appendChild(label);
      sub.appendChild(subLi);
    });
    li.appendChild(sub);
  }

  return li;
}

// Correcao rapida "isso nao e uma tarefa, e um gasto" - formulario minimo
// (o texto original pode nao ter um valor claro, entao pede o valor certo
// na hora, do jeito que o Alex quiser) que aparece inline no card e some se
// for cancelado ou depois de corrigir com sucesso.
function criarFormularioTarefaParaGasto(t, li) {
  const form = document.createElement("div");
  form.className = "correcao-form";

  const valorInput = document.createElement("input");
  valorInput.type = "number";
  valorInput.step = "0.01";
  valorInput.min = "0.01";
  valorInput.placeholder = "valor (R$)";
  valorInput.className = "correcao-input";

  const categoriaSelect = document.createElement("select");
  categoriaSelect.className = "correcao-select";
  CATEGORIAS_GASTO.forEach((cat) => {
    const opt = document.createElement("option");
    opt.value = cat;
    opt.textContent = cat;
    categoriaSelect.appendChild(opt);
  });

  const btnConfirmar = document.createElement("button");
  btnConfirmar.className = "primario btn-com-icone";
  btnConfirmar.innerHTML = `${ICONE_CHECK}virar gasto`;
  btnConfirmar.addEventListener("click", async () => {
    const valor = parseFloat(valorInput.value);
    if (!valor || valor <= 0) {
      valorInput.focus();
      return;
    }
    setBotaoCarregando(btnConfirmar, true, "corrigindo...");
    const data = await apiFetch(`/api/tasks/${t.id}/reclassificar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ valor, categoria: categoriaSelect.value }),
    });
    if (data) {
      li.classList.add("saindo");
      setTimeout(() => {
        loadTasks();
        loadExpenses();
      }, 220);
    } else {
      setBotaoCarregando(btnConfirmar, false, "virar gasto");
    }
  });

  const btnCancelar = document.createElement("button");
  btnCancelar.className = "btn-com-icone";
  btnCancelar.textContent = "cancelar";
  btnCancelar.addEventListener("click", () => form.remove());

  form.appendChild(valorInput);
  form.appendChild(categoriaSelect);
  form.appendChild(btnConfirmar);
  form.appendChild(btnCancelar);
  return form;
}

async function loadTasks() {
  const tasks = await apiFetch("/api/tasks");
  if (!tasks) return;
  const list = $("#lista-tarefas");
  list.innerHTML = "";
  $("#tarefas-vazio").hidden = tasks.length > 0;
  tasks.forEach((t) => list.appendChild(criarItemTarefa(t)));
}

// Categoria errada e o caso mais comum de corrigir (a IA acerta o "e um
// gasto" quase sempre, erra mais na categoria) - por isso a propria tag vira
// um <select> ali mesmo, sem sair do card: um toque abre, outro escolhe.
function criarSeletorCategoriaGasto(e, cat, li) {
  const select = document.createElement("select");
  select.className = "correcao-select correcao-select-categoria";
  CATEGORIAS_GASTO.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c;
    opt.textContent = c;
    if (c === e.category) opt.selected = true;
    select.appendChild(opt);
  });
  select.addEventListener("click", (ev) => ev.stopPropagation());
  select.addEventListener("blur", () => {
    if (select.parentElement) select.replaceWith(cat);
  });
  select.addEventListener("change", async () => {
    const categoriaNova = select.value;
    if (categoriaNova === e.category) {
      select.replaceWith(cat);
      return;
    }
    select.disabled = true;
    const data = await apiFetch(`/api/expenses/${e.id}/categoria`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ categoria: categoriaNova }),
    });
    if (data) loadExpenses();
    else select.disabled = false;
  });
  return select;
}

function criarItemGasto(e) {
  const li = document.createElement("li");
  li.className = "item" + (e.tipo === "planejado" ? " item-planejado" : "");

  const linha = document.createElement("div");
  linha.className = "item-linha";

  const info = document.createElement("div");
  const valor = document.createElement("span");
  valor.className = "gasto-valor";
  valor.textContent = fmtMoeda(e.amount);
  const cat = document.createElement("span");
  cat.className = "gasto-categoria";
  cat.dataset.cat = e.category;
  cat.textContent = e.category;
  cat.title = "toque pra corrigir a categoria";
  cat.addEventListener("click", () => {
    const select = criarSeletorCategoriaGasto(e, cat, li);
    cat.replaceWith(select);
    select.focus();
  });
  info.appendChild(valor);
  info.appendChild(cat);
  if (e.tipo === "planejado") {
    const badge = document.createElement("span");
    badge.className = "badge-planejado";
    badge.textContent = "planejado";
    info.appendChild(badge);
  }
  if (e.description) {
    const desc = document.createElement("span");
    desc.className = "item-quando";
    desc.textContent = e.description;
    info.appendChild(desc);
  }

  const acoes = document.createElement("div");
  acoes.className = "item-acoes";
  const btnCorrigirTipo = document.createElement("button");
  btnCorrigirTipo.className = "btn-com-icone";
  btnCorrigirTipo.title = "isso nao e um gasto?";
  btnCorrigirTipo.innerHTML = `${ICONE_CORRIGIR}e tarefa`;
  btnCorrigirTipo.addEventListener("click", async () => {
    setBotaoCarregando(btnCorrigirTipo, true, "corrigindo...");
    const data = await apiFetch(`/api/expenses/${e.id}/reclassificar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    if (data) {
      li.classList.add("saindo");
      setTimeout(() => {
        loadExpenses();
        loadTasks();
      }, 220);
    } else {
      setBotaoCarregando(btnCorrigirTipo, false, "e tarefa");
    }
  });
  acoes.appendChild(btnCorrigirTipo);

  linha.appendChild(info);
  linha.appendChild(acoes);
  li.appendChild(linha);
  return li;
}

async function loadExpenses() {
  const expenses = await apiFetch("/api/expenses");
  if (!expenses) return;
  const list = $("#lista-gastos");
  list.innerHTML = "";
  $("#gastos-vazio").hidden = expenses.length > 0;
  expenses.forEach((e) => list.appendChild(criarItemGasto(e)));

  const historico = await apiFetch("/api/expenses/historico?dias=14");
  if (historico) {
    desenharGraficoBarras($("#grafico-gastos"), historico, {
      cor: "var(--cor-financeiro)",
      formatarValor: fmtMoeda,
      rotulo: "Gasto diario nos ultimos 14 dias",
    });
  }

  loadResumoSemanal();
}

async function loadResumoSemanal() {
  const data = await apiFetch("/api/gastos/resumo-semanal");
  const box = $("#resumo-semanal-box");
  if (!data || data.total_semana <= 0) {
    box.hidden = true;
    return;
  }

  $("#resumo-semanal-total").textContent = fmtMoeda(data.total_semana);

  const partes = [];
  if (data.variacao_pct !== null) {
    partes.push(
      data.variacao_pct >= 0
        ? `${data.variacao_pct}% a mais que a semana passada`
        : `${Math.abs(data.variacao_pct)}% a menos que a semana passada`
    );
  }
  if (data.categoria_top) {
    partes.push(`maior peso: ${data.categoria_top} (${fmtMoeda(data.categoria_top_valor)})`);
  }
  $("#resumo-semanal-detalhe").textContent = partes.join(" - ");

  box.hidden = false;
}

function criarItemBanco(conta) {
  const li = document.createElement("li");
  li.className = "item";

  const linha = document.createElement("div");
  linha.className = "item-linha";

  const info = document.createElement("div");
  const nome = document.createElement("span");
  nome.className = "item-titulo";
  const rotuloTipo = conta.tipo === "cartao" ? "cartao" : "conta";
  nome.textContent = `${conta.banco.charAt(0).toUpperCase() + conta.banco.slice(1)} (${rotuloTipo})`;
  info.appendChild(nome);

  const stats = document.createElement("span");
  stats.className = "item-quando";
  stats.textContent = conta.ultima_transacao
    ? `${conta.total_transacoes} transacao(oes) - ${fmtMoeda(conta.total_gasto)} em gastos - ultima em ${conta.ultima_transacao}`
    : "nenhuma transacao ainda";
  info.appendChild(stats);

  linha.appendChild(info);

  if (conta.saldo !== null && conta.saldo !== undefined) {
    const saldo = document.createElement("span");
    saldo.className = "banco-saldo" + (conta.saldo < 0 ? " banco-saldo-negativo" : "");
    saldo.textContent = fmtMoeda(conta.saldo);
    linha.appendChild(saldo);
  }

  li.appendChild(linha);
  return li;
}

async function loadBancos() {
  const [contas, status] = await Promise.all([
    apiFetch("/api/bancos"),
    apiFetch("/api/bancos/sync-status"),
  ]);

  if (status) {
    $("#bancos-status").textContent = status.info;
    $("#conectar-btn").hidden = !status.sincronizacao_automatica;
    // aviso discreto - so aparece quando ENCRYPTION_KEY nao esta configurada
    // (ver docs/SEGURANCA.md); nao bloqueia nada, so avisa.
    $("#cripto-aviso").hidden = status.criptografia_ativa !== false;
  }

  if (!contas) return;
  const list = $("#lista-bancos");
  list.innerHTML = "";
  $("#bancos-vazio").hidden = contas.length > 0;
  contas.forEach((c) => list.appendChild(criarItemBanco(c)));
}

let pluggyScriptCarregado = null;

function carregarPluggyScript() {
  if (pluggyScriptCarregado) return pluggyScriptCarregado;
  pluggyScriptCarregado = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://cdn.pluggy.ai/pluggy-connect/latest/pluggy-connect.js";
    script.onload = resolve;
    script.onerror = reject;
    document.head.appendChild(script);
  });
  return pluggyScriptCarregado;
}

$("#conectar-btn").addEventListener("click", async () => {
  const btn = $("#conectar-btn");
  setBotaoCarregando(btn, true, "Abrindo...");

  const [tokenData] = await Promise.all([
    apiFetch("/api/bancos/conectar/token", { method: "POST" }),
    carregarPluggyScript().catch(() => mostrarErro("Nao consegui carregar o widget de conexao.")),
  ]);

  setBotaoCarregando(btn, false, "Conectar banco automaticamente");
  if (!tokenData) return;

  const widget = new PluggyConnect({
    connectToken: tokenData.connect_token,
    includeSandbox: false,
    onSuccess: async ({ item }) => {
      setBotaoCarregando(btn, true, "Sincronizando...");
      const data = await apiFetch("/api/bancos/conectar/finalizar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item_id: item.id }),
      });
      setBotaoCarregando(btn, false, "Conectar banco automaticamente");
      if (data) loadBancos();
    },
    onError: () => mostrarErro("A conexao com o banco falhou. Tenta de novo."),
  });
  widget.init();
});

const OFX_LABEL_PADRAO = "Escolher extrato (.ofx, .qfx)";

function atualizarOfxLabel() {
  const label = $("#ofx-input-label");
  const span = label.querySelector("span");
  const arquivo = $("#ofx-input").files[0];
  span.textContent = arquivo ? arquivo.name : OFX_LABEL_PADRAO;
  label.classList.toggle("tem-arquivo", Boolean(arquivo));
}

$("#ofx-input").addEventListener("change", atualizarOfxLabel);

$("#importar-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const banco = $("#banco-select").value;
  const tipo = $("#tipo-select").value;
  const arquivo = $("#ofx-input").files[0];
  if (!arquivo) return;

  const importarBtn = $("#importar-btn");
  setBotaoCarregando(importarBtn, true, "Importando...");

  const form = new FormData();
  form.append("banco", banco);
  form.append("tipo", tipo);
  form.append("arquivo", arquivo);
  const data = await apiFetch("/api/bancos/importar", { method: "POST", body: form });

  setBotaoCarregando(importarBtn, false, "Importar extrato");

  if (!data) return;
  $("#ofx-input").value = "";
  atualizarOfxLabel();
  $("#bancos-status").textContent =
    `Importado: ${data.novas} nova(s), ${data.duplicadas} ja existiam de ${data.encontradas} encontradas.`;
  loadBancos();
});

function criarItemMeta(meta) {
  const li = document.createElement("li");
  li.className = "item";

  const titulo = document.createElement("span");
  titulo.className = "item-titulo";
  titulo.textContent = meta.titulo;
  li.appendChild(titulo);

  const pct = Math.min(100, (meta.valor_guardado / meta.valor_alvo) * 100 || 0);
  const barra = document.createElement("div");
  barra.className = "meta-progresso";
  const barraInterna = document.createElement("div");
  barraInterna.className = "meta-progresso-barra" + (pct >= 100 ? " completa" : "");
  barraInterna.style.width = `${pct}%`;
  barra.appendChild(barraInterna);
  li.appendChild(barra);
  if (pct >= 100) {
    const badge = document.createElement("span");
    badge.className = "badge-sucesso";
    badge.textContent = "meta batida! \u{1F389}";
    li.appendChild(badge);
  }

  const detalhe = document.createElement("p");
  detalhe.className = "meta-detalhe";
  const guardadoTxt = `${fmtMoeda(meta.valor_guardado)} de ${fmtMoeda(meta.valor_alvo)} guardado`;
  const diasTxt =
    pct < 100 && meta.dias_restantes != null
      ? meta.dias_restantes >= 0
        ? ` (faltam ${meta.dias_restantes} dia${meta.dias_restantes === 1 ? "" : "s"})`
        : ` (${Math.abs(meta.dias_restantes)} dia${Math.abs(meta.dias_restantes) === 1 ? "" : "s"} atrasada)`
      : "";
  const prazoTxt = meta.prazo
    ? meta.por_mes != null
      ? ` - guarde ${fmtMoeda(meta.por_mes)}/mes ate ${meta.prazo}${diasTxt}`
      : ` - prazo: ${meta.prazo}${diasTxt}`
    : " - sem prazo definido";
  detalhe.textContent = guardadoTxt + prazoTxt;
  li.appendChild(detalhe);
  if (meta.previsao && pct < 100) {
    const previsao = document.createElement("p");
    previsao.className = "meta-detalhe";
    previsao.textContent = `No ritmo atual (${fmtMoeda(meta.previsao.ritmo_mensal)}/mes), bate em ${fmtDataBr(meta.previsao.data_prevista)}.`;
    li.appendChild(previsao);
  }

  const graficoWrap = document.createElement("div");
  graficoWrap.className = "grafico-container meta-grafico";
  graficoWrap.id = `grafico-meta-${meta.id}`;
  li.appendChild(graficoWrap);

  const guardarWrap = document.createElement("div");
  guardarWrap.className = "meta-guardar";
  const input = document.createElement("input");
  input.type = "text";
  input.inputMode = "decimal";
  input.placeholder = "guardei R$...";
  aplicarMascaraMoeda(input);
  const btn = document.createElement("button");
  btn.className = "btn-com-icone";
  btn.innerHTML = `${ICONE_PLUS}Registrar`;
  btn.addEventListener("click", async () => {
    const valor = valorMascaraParaNumero(input.value);
    if (!valor || valor <= 0) return;
    setBotaoCarregando(btn, true, "salvando...");
    const data = await apiFetch(`/api/metas/${meta.id}/guardar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ valor }),
    });
    setBotaoCarregando(btn, false, "Registrar");
    if (data) {
      loadMetas();
      loadStreak();
    }
  });
  guardarWrap.appendChild(input);
  guardarWrap.appendChild(btn);
  li.appendChild(guardarWrap);

  return li;
}

async function loadMetas() {
  const metas = await apiFetch("/api/metas");
  if (!metas) return;
  const list = $("#lista-metas");
  list.innerHTML = "";
  $("#metas-vazio").hidden = metas.length > 0;
  metas.forEach((m) => list.appendChild(criarItemMeta(m)));

  metas.forEach(async (m) => {
    const historico = await apiFetch(`/api/metas/${m.id}/historico`);
    const container = $(`#grafico-meta-${m.id}`);
    if (historico && container) {
      desenharGraficoLinha(container, historico.pontos, {
        cor: "var(--cor-hoje)",
        valorAlvo: historico.valor_alvo,
        formatarValor: fmtMoeda,
        altura: 70,
        rotulo: `Evolucao de "${m.titulo}"`,
      });
    }
  });
}

async function loadConstrutora() {
  const info = $("#construtora-info");
  const listaContas = $("#lista-contas-a-vencer");
  info.classList.add("carregando");
  info.textContent = "Carregando...";
  listaContas.innerHTML = "";
  $("#contas-a-vencer-vazio").hidden = true;

  const data = await apiFetch("/api/construtora/resumo");
  info.classList.remove("carregando");
  if (!data) return;
  if (!data.configurado) {
    info.textContent = "Ainda nao conectado a API da construtora.";
    return;
  }
  if (data.erro) {
    info.textContent = data.erro;
    return;
  }

  const d = data.dados;
  info.textContent =
    `Entradas ${fmtMoeda(d.tot_entradas)} · Saidas ${fmtMoeda(d.tot_saidas)} · ` +
    `Lucro liquido ${fmtMoeda(d.lucro_liquido)} (margem ${d.margem.toFixed(1)}%)`;

  const contas = data.contas || [];
  $("#contas-a-vencer-vazio").hidden = contas.length > 0;
  contas.forEach((c) => listaContas.appendChild(criarItemContaAVencer(c)));
}

function criarItemContaAVencer(c) {
  const li = document.createElement("li");
  li.className = "item";

  const linha = document.createElement("div");
  linha.className = "item-linha";

  const tituloWrap = document.createElement("div");
  const titulo = document.createElement("span");
  titulo.className = "item-titulo";
  titulo.textContent = c.fornecedor || c.descricao || "Fornecedor nao informado";
  if (c.dias_ate_vencer < 0) {
    const badge = document.createElement("span");
    badge.className = "item-badge-vencida";
    badge.textContent = "vencida";
    titulo.appendChild(badge);
  }
  tituloWrap.appendChild(titulo);

  const quando = document.createElement("span");
  quando.className = "item-quando";
  let quandoTexto;
  if (c.dias_ate_vencer < 0) {
    quandoTexto = `venceu ha ${Math.abs(c.dias_ate_vencer)} dia(s)`;
  } else if (c.dias_ate_vencer === 0) {
    quandoTexto = "vence hoje";
  } else {
    quandoTexto = `vence em ${c.dias_ate_vencer} dia(s)`;
  }
  quando.textContent = `${fmtMoeda(c.valor)} · ${quandoTexto}`;
  tituloWrap.appendChild(quando);

  linha.appendChild(tituloWrap);
  li.appendChild(linha);
  return li;
}

async function loadCotacoes() {
  const data = await apiFetch("/api/cotacoes");
  const list = $("#lista-cotacoes");
  list.innerHTML = "";
  if (!data) return;
  $("#cotacoes-vazio").hidden = data.length > 0;
  data.forEach((c) => list.appendChild(criarItemCotacao(c)));
}

function criarItemCotacao(c) {
  const li = document.createElement("li");
  li.className = "item cotacao-card";

  const cabecalho = document.createElement("div");
  cabecalho.className = "cotacao-cabecalho";
  cabecalho.tabIndex = 0;
  cabecalho.setAttribute("role", "button");
  cabecalho.setAttribute("aria-expanded", "false");

  const titulo = document.createElement("span");
  titulo.className = "item-titulo";
  titulo.textContent = c.titulo;

  const resumo = document.createElement("span");
  resumo.className = "item-quando";
  resumo.textContent =
    c.total_itens === 0
      ? "nenhum fornecedor ainda"
      : `${c.total_itens} fornecedor(es)` +
        (c.menor_valor != null ? ` - menor: ${fmtMoeda(c.menor_valor)}` : "");

  cabecalho.appendChild(titulo);
  cabecalho.appendChild(resumo);
  li.appendChild(cabecalho);

  const detalhe = document.createElement("div");
  detalhe.className = "cotacao-detalhe";
  detalhe.hidden = true;
  li.appendChild(detalhe);

  let carregado = false;
  const abrirFechar = async () => {
    detalhe.hidden = !detalhe.hidden;
    cabecalho.setAttribute("aria-expanded", String(!detalhe.hidden));
    if (!detalhe.hidden && !carregado) {
      carregado = true;
      await preencherDetalheCotacao(c.id, detalhe);
    }
  };
  cabecalho.addEventListener("click", abrirFechar);
  cabecalho.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      abrirFechar();
    }
  });

  return li;
}

async function preencherDetalheCotacao(cotacaoId, container) {
  container.textContent = "Carregando...";
  const data = await apiFetch(`/api/cotacoes/${cotacaoId}`);
  if (!data) {
    container.textContent = "";
    return;
  }
  container.innerHTML = "";

  if (data.itens.length === 0) {
    const vazio = document.createElement("p");
    vazio.className = "dica-metas";
    vazio.textContent = "Nenhum fornecedor registrado ainda.";
    container.appendChild(vazio);
  } else {
    const listaItens = document.createElement("ul");
    listaItens.className = "cotacao-itens";
    data.itens.forEach((item, i) => {
      const itemLi = document.createElement("li");
      itemLi.className = "cotacao-item" + (i === 0 && item.valor != null ? " cotacao-item-menor" : "");

      const texto = document.createElement("span");
      const partes = [item.fornecedor || "fornecedor sem nome"];
      partes.push(item.valor != null ? fmtMoeda(item.valor) : "sem valor");
      if (item.prazo_texto) partes.push(item.prazo_texto);
      texto.textContent = partes.join(" - ");
      itemLi.appendChild(texto);

      const btnApagar = document.createElement("button");
      btnApagar.type = "button";
      btnApagar.className = "cotacao-item-apagar";
      btnApagar.setAttribute("aria-label", "Apagar item");
      btnApagar.textContent = "×";
      btnApagar.addEventListener("click", async () => {
        await apiFetch(`/api/cotacoes/${cotacaoId}/itens/${item.id}`, { method: "DELETE" });
        preencherDetalheCotacao(cotacaoId, container);
        loadCotacoes();
      });
      itemLi.appendChild(btnApagar);
      listaItens.appendChild(itemLi);
    });
    container.appendChild(listaItens);
  }

  const formItem = document.createElement("form");
  formItem.className = "form-linha cotacao-add-form";
  const inputFornecedor = document.createElement("input");
  inputFornecedor.type = "text";
  inputFornecedor.placeholder = "Fornecedor";
  inputFornecedor.required = true;
  const inputValor = document.createElement("input");
  inputValor.type = "text";
  inputValor.inputMode = "decimal";
  inputValor.placeholder = "Valor R$";
  inputValor.required = true;
  const btnAdd = document.createElement("button");
  btnAdd.type = "submit";
  btnAdd.className = "btn-com-icone";
  btnAdd.textContent = "+ Adicionar";
  formItem.appendChild(inputFornecedor);
  formItem.appendChild(inputValor);
  formItem.appendChild(btnAdd);
  formItem.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const fornecedor = inputFornecedor.value.trim();
    const valor = parseFloat(inputValor.value.trim().replace(",", "."));
    if (!fornecedor || Number.isNaN(valor)) return;
    const r = await apiFetch(`/api/cotacoes/${cotacaoId}/itens`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fornecedor, valor }),
    });
    if (r) {
      preencherDetalheCotacao(cotacaoId, container);
      loadCotacoes();
    }
  });
  container.appendChild(formItem);

  const uploadLabel = document.createElement("label");
  uploadLabel.className = "cotacao-upload-label";
  const uploadTexto = document.createElement("span");
  uploadTexto.textContent = "Anexar PDF do orcamento";
  const uploadInput = document.createElement("input");
  uploadInput.type = "file";
  uploadInput.accept = "application/pdf";
  uploadLabel.appendChild(uploadTexto);
  uploadLabel.appendChild(uploadInput);
  uploadInput.addEventListener("change", async () => {
    const arquivo = uploadInput.files[0];
    if (!arquivo) return;
    uploadTexto.textContent = "Lendo PDF...";
    const form = new FormData();
    form.append("arquivo", arquivo);
    const r = await apiFetch(`/api/cotacoes/${cotacaoId}/itens/pdf`, { method: "POST", body: form });
    if (r) {
      preencherDetalheCotacao(cotacaoId, container);
      loadCotacoes();
    } else {
      uploadTexto.textContent = "Anexar PDF do orcamento";
    }
  });
  container.appendChild(uploadLabel);
}

$("#cotacao-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("#cotacao-titulo");
  const titulo = input.value.trim();
  if (!titulo) return;
  const r = await apiFetch("/api/cotacoes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ titulo }),
  });
  if (r) {
    input.value = "";
    loadCotacoes();
  }
});

function criarItemVoo(v) {
  const li = document.createElement("li");
  li.className = "item";

  const linha = document.createElement("div");
  linha.className = "item-linha";

  const tituloWrap = document.createElement("div");
  const titulo = document.createElement("span");
  titulo.className = "item-titulo";
  titulo.textContent = v.origem ? `${v.origem} → ${v.destino}` : v.destino;
  tituloWrap.appendChild(titulo);

  const quando = document.createElement("span");
  quando.className = "item-quando";
  let quandoTxt = fmtDataBr(v.data);
  if (v.hora) quandoTxt += ` as ${v.hora}`;
  if (v.horas) quandoTxt += ` - ${fmtHoras(v.horas)} voadas`;
  quando.textContent = quandoTxt;
  tituloWrap.appendChild(quando);

  const saidaResultado = document.createElement("p");
  saidaResultado.className = "resumo-texto voo-saida-resultado";
  saidaResultado.hidden = true;
  tituloWrap.appendChild(saidaResultado);

  if (v.clima) {
    const climaEl = document.createElement("span");
    climaEl.className = "voo-clima" + (v.clima.alerta_chuva ? " alerta" : "");
    climaEl.textContent =
      `${Math.round(v.clima.chuva_pct)}% chance de chuva, ` +
      `${Math.round(v.clima.temp_min)}–${Math.round(v.clima.temp_max)}°C em ${v.clima.cidade}`;
    tituloWrap.appendChild(climaEl);
  }

  linha.appendChild(tituloWrap);

  const acoes = document.createElement("div");
  acoes.className = "item-acoes";

  if (v.clima) {
    const windyBtn = document.createElement("a");
    windyBtn.className = "btn-com-icone";
    windyBtn.href = `https://www.windy.com/?cbase,${v.clima.lat},${v.clima.lon},9`;
    windyBtn.target = "_blank";
    windyBtn.rel = "noopener";
    windyBtn.textContent = "Windy";
    acoes.appendChild(windyBtn);
  }

  if (v.hora) {
    const sairBtn = document.createElement("button");
    sairBtn.className = "btn-com-icone";
    sairBtn.textContent = "Quando sair?";
    sairBtn.addEventListener("click", async () => {
      setBotaoCarregando(sairBtn, true, "calculando...");
      const data = await apiFetch("/api/viagem/quando-sair", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          destino: v.destino,
          chegar_ate: `${v.data}T${v.hora}`,
          margem_minutos: 60,
        }),
      });
      setBotaoCarregando(sairBtn, false, "Quando sair?");
      if (!data) return;
      const sairEm = new Date(data.sair_ate);
      const horaTxt = sairEm.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
      saidaResultado.textContent =
        `Saia ate as ${horaTxt} (viagem de ${data.duracao_minutos}min, ${data.distancia_km}km, ` +
        `com ${data.margem_minutos}min de margem pro voo)`;
      saidaResultado.hidden = false;
    });
    acoes.appendChild(sairBtn);
  }

  const apagarBtn = document.createElement("button");
  apagarBtn.className = "btn-com-icone";
  apagarBtn.innerHTML = `${ICONE_TRASH}Apagar`;
  apagarBtn.addEventListener("click", async () => {
    apagarBtn.disabled = true;
    const ok = await apiFetch(`/api/voos/${v.id}`, { method: "DELETE" });
    if (ok) {
      li.classList.add("saindo");
      setTimeout(() => loadVoosResumo(), 220);
    } else {
      apagarBtn.disabled = false;
    }
  });
  acoes.appendChild(apagarBtn);

  linha.appendChild(acoes);
  li.appendChild(linha);

  if (v.observacao) {
    const diario = document.createElement("p");
    diario.className = "voo-diario";
    diario.textContent = v.observacao;
    li.appendChild(diario);
  }

  return li;
}

async function loadVoosResumo() {
  const vazioEl = $("#voos-vazio");
  const vazioTexto = $("#voos-vazio-texto");
  const textoOriginal = vazioTexto.textContent;
  // busca a previsao do tempo pra cada voo agendado, entao pode demorar um
  // pouco mais que uma chamada comum - mostra que ta carregando em vez de
  // deixar a lista parecendo vazia/quebrada nesse meio tempo
  vazioTexto.textContent = "Carregando voos e previsao do tempo...";
  vazioEl.hidden = false;

  const data = await apiFetch("/api/voos/resumo");
  vazioTexto.textContent = textoOriginal;
  if (!data) return;

  animarNumero($("#voo-horas-semana"), data.horas_semana, fmtHoras);
  animarNumero($("#voo-horas-mes"), data.horas_mes, fmtHoras);
  animarNumero($("#voo-horas-total"), data.horas_total, fmtHoras);

  const currencyChip = $("#currency-voo-chip");
  if (data.dias_desde_ultimo_voo === null || data.dias_desde_ultimo_voo === undefined) {
    currencyChip.hidden = true;
  } else {
    const dias = data.dias_desde_ultimo_voo;
    $("#currency-voo-texto").textContent =
      dias === 0 ? "Voou hoje" : dias === 1 ? "1 dia sem voar" : `${dias} dias sem voar`;
    currencyChip.classList.toggle("alerta", dias >= 21);
    currencyChip.hidden = false;
  }

  const list = $("#lista-voos");
  list.innerHTML = "";
  vazioEl.hidden = data.proximos.length > 0;
  data.proximos.forEach((v) => list.appendChild(criarItemVoo(v)));

  const historico = await apiFetch("/api/voos/historico");
  if (historico) {
    desenharGraficoLinha($("#grafico-voos"), historico, {
      cor: "var(--cor-aviacao)",
      formatarValor: fmtHoras,
      rotulo: "Evolucao das horas de voo acumuladas",
    });
  }
}

aplicarMascaraData($("#voo-data"));

$("#voo-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#voo-btn");
  const dataInput = $("#voo-data");
  const horaInput = $("#voo-hora");
  const origemInput = $("#voo-origem");
  const destinoInput = $("#voo-destino");
  const horasInput = $("#voo-horas");
  const obsInput = $("#voo-obs");

  const dataIso = mascaraDataParaIso(dataInput.value.trim());
  const destino = destinoInput.value.trim();
  if (!dataIso || !destino) {
    mostrarErro("Confere a data (dd/mm/aaaa) e o destino.");
    return;
  }
  const horasTxt = horasInput.value.trim();
  const horas = horasTxt ? parseHoras(horasTxt) : null;
  if (horasTxt && !horas) {
    mostrarErro("Horas invalidas - use um numero tipo 1,5 (ou deixe em branco se so agendado).");
    return;
  }
  const horaTxt = horaInput.value.trim();
  if (horaTxt && !/^([01]?\d|2[0-3]):[0-5]\d$/.test(horaTxt)) {
    mostrarErro("Horario do voo invalido - use hh:mm (ex: 14:00), ou deixe em branco.");
    return;
  }

  setBotaoCarregando(btn, true, "salvando...");
  const data = await apiFetch("/api/voos", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      data: dataIso,
      hora: horaTxt || undefined,
      origem: origemInput.value.trim() || undefined,
      destino,
      horas,
      observacao: obsInput.value.trim() || undefined,
    }),
  });
  setBotaoCarregando(btn, false, "Registrar");
  if (!data) return;

  dataInput.value = "";
  horaInput.value = "";
  origemInput.value = "";
  destinoInput.value = "";
  horasInput.value = "";
  obsInput.value = "";
  pulsarSucesso(destinoInput);
  loadVoosResumo();
  loadStreak();
});

function renderCamposMeteo(container, decodificado) {
  container.innerHTML = "";
  if (!decodificado) return;
  const linhas = [];
  if (decodificado.vento) {
    const v = decodificado.vento;
    let txt = v.variavel
      ? `variável, ${v.velocidade_kt}kt`
      : `${String(v.direcao).padStart(3, "0")}° / ${v.velocidade_kt}kt`;
    if (v.rajada_kt) txt += `, rajada ${v.rajada_kt}kt`;
    linhas.push(["Vento", txt, false]);
  }
  if (decodificado.visibilidade_m != null) {
    const txt = decodificado.visibilidade_m >= 9999 ? "10km+" : `${decodificado.visibilidade_m}m`;
    linhas.push(["Vis.", txt, false]);
  }
  if (decodificado.teto_ft != null) {
    linhas.push(["Teto", `${decodificado.teto_ft} ft`, true]);
  } else if (decodificado.nuvens && decodificado.nuvens.length === 0) {
    linhas.push(["Nuvens", "céu limpo", false]);
  }
  if (decodificado.temp != null) {
    const orv = decodificado.ponto_orvalho != null ? ` / ${decodificado.ponto_orvalho}°C` : "";
    linhas.push(["Temp.", `${decodificado.temp}°C${orv}`, false]);
  }
  if (decodificado.qnh_hpa) {
    linhas.push(["QNH", `${decodificado.qnh_hpa} hPa`, false]);
  }
  linhas.forEach(([rotulo, valor, destaque]) => {
    const linha = document.createElement("div");
    linha.className = "metar-campo-linha";
    const r = document.createElement("span");
    r.className = "metar-campo-rotulo";
    r.textContent = rotulo;
    const val = document.createElement("span");
    val.className = "metar-campo-valor" + (destaque ? " teto" : "");
    val.textContent = valor;
    linha.appendChild(r);
    linha.appendChild(val);
    container.appendChild(linha);
  });
}

function renderSegmentosTaf(container, segmentos) {
  container.innerHTML = "";
  if (!segmentos) return;
  segmentos.forEach((seg) => {
    const bloco = document.createElement("div");
    bloco.className = "taf-segmento";
    const titulo = document.createElement("div");
    titulo.className = "taf-segmento-titulo";
    titulo.textContent = seg.periodo ? `${seg.tipo} (${seg.periodo})` : seg.tipo;
    bloco.appendChild(titulo);
    const campos = document.createElement("div");
    renderCamposMeteo(campos, seg.decodificado);
    bloco.appendChild(campos);
    container.appendChild(bloco);
  });
}

let metarFaladoAtual = null;
let tafFaladoAtual = null;

function falarTexto(btn, texto) {
  if (!texto || !("speechSynthesis" in window)) return;
  if (window.speechSynthesis.speaking) {
    window.speechSynthesis.cancel();
    document.querySelectorAll(".btn-ouvir.falando").forEach((b) => b.classList.remove("falando"));
    return;
  }
  const utter = new SpeechSynthesisUtterance(texto);
  utter.lang = "pt-BR";
  utter.rate = 0.98;
  utter.onstart = () => btn.classList.add("falando");
  utter.onend = () => btn.classList.remove("falando");
  utter.onerror = () => btn.classList.remove("falando");
  window.speechSynthesis.speak(utter);
}

if ("speechSynthesis" in window) {
  $("#metar-ouvir").addEventListener("click", () => falarTexto($("#metar-ouvir"), metarFaladoAtual));
  $("#taf-ouvir").addEventListener("click", () => falarTexto($("#taf-ouvir"), tafFaladoAtual));
} else {
  $("#metar-ouvir").hidden = true;
  $("#taf-ouvir").hidden = true;
}

$("#metar-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#metar-btn");
  const icao = $("#metar-icao").value.trim().toUpperCase();
  if (!icao) return;

  setBotaoCarregando(btn, true, "buscando...");
  $("#metar-resultado").hidden = true;
  const data = await apiFetch(`/api/clima/metar?icao=${encodeURIComponent(icao)}`);
  setBotaoCarregando(btn, false, "Consultar");
  if (!data) return;

  if (!data.metar && !data.taf) {
    mostrarErro(data.erro || "nao encontrei dado nenhum pra esse codigo.");
    return;
  }
  $("#metar-texto").textContent = data.metar || "sem METAR disponivel agora.";
  $("#taf-texto").textContent = data.taf || "sem TAF disponivel agora.";
  renderCamposMeteo($("#metar-campos"), data.metar_decodificado);
  renderSegmentosTaf($("#taf-segmentos"), data.taf_segmentos);
  metarFaladoAtual = data.metar_falado;
  tafFaladoAtual = data.taf_falado;
  if ("speechSynthesis" in window) {
    $("#metar-ouvir").hidden = !metarFaladoAtual;
    $("#taf-ouvir").hidden = !tafFaladoAtual;
  }
  $("#metar-resultado").hidden = false;
});

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)));
}

async function initPush() {
  const btn = $("#push-btn");
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;

  const status = await apiFetch("/api/push/status");
  if (!status || !status.configurado) return;

  const reg = await navigator.serviceWorker.ready;
  const existente = await reg.pushManager.getSubscription();
  btn.hidden = false;

  if (existente) {
    btn.textContent = "Notificacoes ativadas";
    btn.disabled = true;
    return;
  }

  btn.addEventListener("click", async () => {
    const permissao = await Notification.requestPermission();
    if (permissao !== "granted") {
      mostrarErro("Permissao de notificacao negada no navegador.");
      return;
    }
    setBotaoCarregando(btn, true, "Ativando...");
    const subscription = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(status.public_key),
    });
    await apiFetch("/api/push/inscrever", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(subscription.toJSON()),
    });
    setBotaoCarregando(btn, false, "Notificacoes ativadas");
    btn.disabled = true;
  });
}

$("#plano-btn").addEventListener("click", async () => {
  const btn = $("#plano-btn");
  const saida = $("#plano-texto");
  setBotaoCarregando(btn, true, "Pensando...");
  saida.hidden = true;

  const data = await apiFetch("/api/plano-do-dia", { method: "POST" });

  setBotaoCarregando(btn, false, "Gerar plano do dia");
  loadUso();
  if (!data) return;
  saida.textContent = data.plano;
  saida.hidden = false;
});

$("#viagem-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#viagem-btn");
  const saida = $("#viagem-resultado");
  const chegarInput = $("#viagem-chegar").value;
  if (!chegarInput) return;

  setBotaoCarregando(btn, true, "Calculando...");
  saida.hidden = true;

  const data = await apiFetch("/api/viagem/quando-sair", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      origem: $("#viagem-origem").value.trim(),
      destino: $("#viagem-destino").value.trim(),
      chegar_ate: chegarInput,
    }),
  });

  setBotaoCarregando(btn, false, "Calcular");
  if (!data) return;

  const sairEm = new Date(data.sair_ate);
  const horaTxt = sairEm.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  const destino = $("#viagem-destino").value.trim();

  // Mesmo card de resultado usado no chat (tarefa/gasto/meta) - pedido do
  // Alex ("achei muito simples") era so de apresentacao, o calculo em si
  // (Google Maps, transito real) ja estava certo.
  saida.innerHTML = "";
  const eyebrow = document.createElement("div");
  eyebrow.className = "card-resultado-eyebrow";
  eyebrow.innerHTML = `${ICONE_VIAGEM_CARD}<span>Pra ${destino}</span>`;
  saida.appendChild(eyebrow);

  const valor = document.createElement("p");
  valor.className = "card-resultado-valor";
  valor.textContent = `Saia ate as ${horaTxt}`;
  saida.appendChild(valor);

  const detalhe = document.createElement("p");
  detalhe.className = "card-resultado-detalhe";
  detalhe.textContent =
    `${data.duracao_minutos}min de viagem - ${data.distancia_km}km - ` +
    `${data.margem_minutos}min de margem`;
  saida.appendChild(detalhe);

  saida.hidden = false;
  const wazeLink = $("#viagem-waze");
  wazeLink.href = `https://waze.com/ul?q=${encodeURIComponent(destino)}&navigate=yes`;
  wazeLink.hidden = false;

  const uberLink = $("#viagem-uber");
  uberLink.href = `https://m.uber.com/ul/?action=setPickup&pickup=my_location&dropoff[formatted_address]=${encodeURIComponent(destino)}`;
  uberLink.hidden = false;
  $("#viagem-uber-dica").hidden = false;
});

/* Dicas colapsaveis: o paragrafo comeca escondido atras do icone "!" e, na
   primeira vez que abre, o texto "digita" progressivamente em vez de
   aparecer tudo de uma vez - reforca que e uma explicacao extra, nao
   conteudo que precisa ser lido toda vez que a secao aparece na tela. */
function initDicas() {
  const reduzMovimento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  document.querySelectorAll(".dica-colapsavel").forEach((wrapper) => {
    const btn = wrapper.querySelector(".dica-toggle");
    const texto = wrapper.querySelector(".dica-texto");
    if (!btn || !texto) return;

    const conteudoCompleto = texto.textContent.trim();
    let jaDigitou = false;
    let timerId = null;

    function digitar() {
      if (jaDigitou || reduzMovimento) {
        texto.textContent = conteudoCompleto;
        jaDigitou = true;
        return;
      }
      texto.textContent = "";
      texto.classList.add("digitando");
      let i = 0;
      const passo = () => {
        i += 1;
        texto.textContent = conteudoCompleto.slice(0, i);
        if (i < conteudoCompleto.length) {
          timerId = setTimeout(passo, 14);
        } else {
          texto.classList.remove("digitando");
          jaDigitou = true;
        }
      };
      passo();
    }

    btn.addEventListener("click", () => {
      const aberto = btn.getAttribute("aria-expanded") === "true";
      if (aberto) {
        btn.setAttribute("aria-expanded", "false");
        texto.hidden = true;
        clearTimeout(timerId);
        texto.classList.remove("digitando");
        return;
      }
      btn.setAttribute("aria-expanded", "true");
      texto.hidden = false;
      digitar();
    });
  });
}

function initSilencio() {
  const btn = $("#silencio-btn");
  const painel = $("#silencio-painel");
  const inicioInput = $("#silencio-inicio");
  const fimInput = $("#silencio-fim");
  const status = $("#silencio-status");
  let carregado = false;

  async function carregar() {
    const dados = await apiFetch("/api/configuracoes/silencio");
    if (!dados) return;
    inicioInput.value = dados.inicio;
    fimInput.value = dados.fim;
    carregado = true;
  }

  btn.addEventListener("click", async () => {
    const aberto = btn.getAttribute("aria-expanded") === "true";
    if (aberto) {
      btn.setAttribute("aria-expanded", "false");
      btn.classList.remove("ativo");
      painel.hidden = true;
      return;
    }
    btn.setAttribute("aria-expanded", "true");
    btn.classList.add("ativo");
    painel.hidden = false;
    if (!carregado) await carregar();
  });

  $("#silencio-salvar").addEventListener("click", async () => {
    const salvarBtn = $("#silencio-salvar");
    status.textContent = "";
    setBotaoCarregando(salvarBtn, true, "Salvando...");
    const dados = await apiFetch("/api/configuracoes/silencio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ inicio: inicioInput.value.trim(), fim: fimInput.value.trim() }),
    });
    setBotaoCarregando(salvarBtn, false, "Salvar");
    if (!dados) return;
    inicioInput.value = dados.inicio;
    fimInput.value = dados.fim;
    status.textContent = `Salvo: das ${dados.inicio} ate ${dados.fim}.`;
  });
}

function initBackup() {
  const btn = $("#backup-btn");
  const painel = $("#backup-painel");

  btn.addEventListener("click", () => {
    const aberto = btn.getAttribute("aria-expanded") === "true";
    if (aberto) {
      btn.setAttribute("aria-expanded", "false");
      btn.classList.remove("ativo");
      painel.hidden = true;
      return;
    }
    btn.setAttribute("aria-expanded", "true");
    btn.classList.add("ativo");
    painel.hidden = false;
  });
}

async function initViagemOrigemPadrao() {
  const status = await apiFetch("/api/viagem/status");
  if (status && status.origem_padrao) {
    $("#viagem-origem").placeholder = `De onde? (padrao: ${status.origem_padrao})`;
  }
}

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/static/service-worker.js");
  initPush();
}

if (typeof FilaOffline !== "undefined") {
  // Mostra o indicador se ja existia algo pendente de uma sessao offline
  // anterior (app fechado/pagina recarregada antes de sincronizar), e
  // tenta sincronizar de cara caso a rede ja tenha voltado nesse meio tempo.
  FilaOffline.contar().then(atualizarIndicadorOffline);
  FilaOffline.sincronizar(atualizarIndicadorOffline);
  // evento "online" + poll de reforco (o poll e quem realmente cobre o iOS,
  // onde o evento "online" de um PWA no Safari nao e confiavel).
  FilaOffline.iniciarAutoSync(atualizarIndicadorOffline);
}

$("#logout-btn").addEventListener("click", async () => {
  // Sempre navega pro login, mesmo se a chamada falhar (rede fora do ar etc) -
  // o objetivo e sair da tela autenticada, nao garantir que o servidor confirmou.
  try {
    await fetch("/logout", { method: "POST" });
  } catch {
    // ignora - segue pro login de qualquer jeito
  }
  window.location.href = "/login";
});

mostrarSaudacao();
loadSummary();
loadUso();
loadStreak();
loadClimaHoje();
loadUberPendentes();
loadAgenda();
loadFechamentoDoDia();
loadMemorias();
loadLembretes();
loadMedicamentos();
loadMedidas();
loadEsperas();
loadSaude();
loadChatHistorico();
initViagemOrigemPadrao();
initVozChat();
initDicas();
initSilencio();
initBackup();
