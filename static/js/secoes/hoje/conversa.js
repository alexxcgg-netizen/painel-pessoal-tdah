// static/js/secoes/hoje/conversa.js - Modo conversa por voz do chat (botão #chat-conversa).
// Script clássico (escopo global compartilhado) - carrega depois de nucleo/voz.js e hoje/chat.js.
//
// Ida e volta, como uma ligação: ouve -> ~3s de silêncio encerra a fala -> transcreve
// (Whisper, /api/voz/transcrever) -> manda pro chat com modo "voz" (resposta falável,
// 2-4 frases) -> a Roberta fala a resposta inteira -> o microfone reabre sozinho.
// Encerra com um toque no botão ou se ninguém falar por ~12s.
//
// O microfone é SOLTO antes de ela falar: no iPhone, com o microfone aberto o som sai
// baixo pelo alto-falante de ligação (e o microfone ouviria a própria voz dela).

const CONVERSA_SILENCIO_MS = 3000; // pedido do Alex: "uns 3 segundos"
const CONVERSA_ESPERA_FALA_MS = 12000; // ninguém falou -> encerra a conversa
const CONVERSA_MAX_FALA_MS = 90000;
const CONVERSA_TICK_MS = 100;

const Conversa = {
  ativa: false,
  ctx: null,
  stream: null,
  gravador: null,
  tick: null,
  btn: null,
  placeholderOriginal: "",
};

function _conversaEstado(estado) {
  const btn = Conversa.btn;
  const input = $("#chat-input");
  if (!btn || !input) return;
  btn.dataset.estado = estado || "";
  const textos = { ouvindo: "Pode falar…", pensando: "Pensando…", falando: "Falando…" };
  input.placeholder = textos[estado] || Conversa.placeholderOriginal;
}

function _conversaSoltarMicrofone() {
  clearInterval(Conversa.tick);
  Conversa.tick = null;
  if (Conversa.stream) Conversa.stream.getTracks().forEach((t) => t.stop());
  Conversa.stream = null;
}

// Uma fala do Alex: resolve com {blob, duracaoS} quando ele fica ~3s calado depois de
// ter falado, ou null se ninguém falou / a conversa foi encerrada no meio.
async function _conversaOuvirUmaFala() {
  try {
    Conversa.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
  } catch {
    mostrarErro("Sem acesso ao microfone. Libera nos Ajustes do iPhone pro painel.");
    return null;
  }
  if (!Conversa.ativa) {
    _conversaSoltarMicrofone();
    return null;
  }
  if (Conversa.ctx.state === "suspended") {
    try {
      await Conversa.ctx.resume();
    } catch {}
  }
  const fonte = Conversa.ctx.createMediaStreamSource(Conversa.stream);
  const analisador = Conversa.ctx.createAnalyser();
  analisador.fftSize = 1024;
  fonte.connect(analisador);
  const amostras = new Float32Array(analisador.fftSize);

  const mime = _mimeGravacao();
  const gravador = mime ? new MediaRecorder(Conversa.stream, { mimeType: mime }) : new MediaRecorder(Conversa.stream);
  Conversa.gravador = gravador;
  const pedacos = [];
  gravador.addEventListener("dataavailable", (e) => {
    if (e.data && e.data.size) pedacos.push(e.data);
  });

  return new Promise((resolve) => {
    const inicio = Date.now();
    let ruido = 0;
    let calibracoes = 0;
    let limiar = 0.015;
    let acimaSeguidos = 0;
    let falou = false;
    let silencioDesde = 0;
    let resultado = null;

    gravador.addEventListener("stop", () => {
      fonte.disconnect();
      _conversaSoltarMicrofone();
      Conversa.gravador = null;
      if (resultado === "fala" && Conversa.ativa) {
        const blob = new Blob(pedacos, { type: (gravador.mimeType || mime || "audio/mp4").split(";")[0] });
        resolve(blob.size ? { blob, duracaoS: (Date.now() - inicio) / 1000 } : null);
      } else {
        resolve(null);
      }
    });

    const parar = (motivo) => {
      if (resultado !== null) return;
      resultado = motivo;
      clearInterval(Conversa.tick);
      if (gravador.state !== "inactive") gravador.stop();
    };

    gravador.start(500);
    _conversaEstado("ouvindo");
    Conversa.tick = setInterval(() => {
      if (!Conversa.ativa) return parar("encerrada");
      analisador.getFloatTimeDomainData(amostras);
      let soma = 0;
      for (let i = 0; i < amostras.length; i++) soma += amostras[i] * amostras[i];
      const rms = Math.sqrt(soma / amostras.length);
      const decorrido = Date.now() - inicio;

      // primeiros ~400ms: mede o ruído do ambiente pra não confundir ventilador com fala
      if (decorrido < 400) {
        ruido += rms;
        calibracoes++;
        return;
      }
      if (calibracoes) {
        limiar = Math.max(0.012, (ruido / calibracoes) * 3);
        calibracoes = 0;
      }

      if (rms > limiar) {
        acimaSeguidos++;
        silencioDesde = 0;
        if (acimaSeguidos >= 3) falou = true; // ~300ms de voz de verdade
      } else {
        acimaSeguidos = 0;
        if (falou && !silencioDesde) silencioDesde = Date.now();
      }

      if (falou && silencioDesde && Date.now() - silencioDesde >= CONVERSA_SILENCIO_MS) return parar("fala");
      if (!falou && decorrido >= CONVERSA_ESPERA_FALA_MS) return parar("ninguem");
      if (decorrido >= CONVERSA_MAX_FALA_MS) return parar(falou ? "fala" : "ninguem");
    }, CONVERSA_TICK_MS);
  });
}

async function _conversaTranscrever({ blob, duracaoS }) {
  const corpo = new FormData();
  const ext = blob.type.includes("mp4") ? "m4a" : blob.type.includes("ogg") ? "ogg" : "webm";
  corpo.append("audio", blob, `fala.${ext}`);
  corpo.append("duracao", String(Math.round(duracaoS)));
  const data = await apiFetch("/api/voz/transcrever", { method: "POST", body: corpo });
  return data && data.texto ? data.texto : null;
}

async function _conversaLaco() {
  while (Conversa.ativa) {
    const fala = await _conversaOuvirUmaFala();
    if (!Conversa.ativa || !fala) break;

    _conversaEstado("pensando");
    const texto = await _conversaTranscrever(fala);
    if (!Conversa.ativa) break;
    if (!texto) continue; // não entendeu - volta a ouvir

    const data = await enviarChat(texto, { corpo: { mensagem: texto, modo: "voz" } });
    if (!Conversa.ativa || !data) break;
    const resposta = data.resumo_texto || data.resposta;
    if (resposta) {
      _conversaEstado("falando");
      await falarEsperando(resposta);
    }
  }
  encerrarConversa();
}

function iniciarConversa() {
  if (Conversa.ativa) return;
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!Ctx) return;
  // tudo que o iPhone exige "dentro do toque" acontece aqui, antes de qualquer await
  desbloquearAudioPremium();
  if (!Conversa.ctx) Conversa.ctx = new Ctx();
  Conversa.ctx.resume().catch(() => {});

  Conversa.ativa = true;
  Conversa.placeholderOriginal = $("#chat-input").placeholder;
  Conversa.btn.classList.add("conversando");
  Conversa.btn.setAttribute("aria-pressed", "true");
  Conversa.btn.setAttribute("aria-label", "Encerrar conversa por voz");
  const mic = $("#chat-mic");
  if (mic) mic.disabled = true;
  _conversaLaco();
}

function encerrarConversa() {
  const estavaAtiva = Conversa.ativa;
  Conversa.ativa = false;
  if (Conversa.gravador && Conversa.gravador.state !== "inactive") Conversa.gravador.stop();
  _conversaSoltarMicrofone();
  if (estavaAtiva && vozTocando()) pararVoz();
  if (!Conversa.btn) return;
  Conversa.btn.classList.remove("conversando");
  Conversa.btn.setAttribute("aria-pressed", "false");
  Conversa.btn.setAttribute("aria-label", "Conversar por voz");
  _conversaEstado("");
  const mic = $("#chat-mic");
  if (mic) mic.disabled = false;
}

function initConversaVoz() {
  const btn = $("#chat-conversa");
  if (!btn) return;
  const suportado =
    !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder) &&
    !!(window.AudioContext || window.webkitAudioContext);
  if (!suportado) return;
  Conversa.btn = btn;
  btn.hidden = false;
  btn.addEventListener("click", () => (Conversa.ativa ? encerrarConversa() : iniciarConversa()));
  // saiu do app / trocou de aba no meio: não deixa microfone aberto em segundo plano
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && Conversa.ativa) encerrarConversa();
  });
}

