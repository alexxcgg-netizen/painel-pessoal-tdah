// static/js/secoes/hoje/conversa.js - Modo conversa por voz do chat (botão #chat-conversa).
// Script clássico (escopo global compartilhado) - carrega depois de nucleo/voz.js e hoje/chat.js
// (usa criarGravacao/transcreverGravacao de chat.js).
//
// Ida e volta, como uma ligação: ouve -> ~3s calado encerra a fala -> transcreve
// (Whisper, /api/voz/transcrever) -> manda pro chat com modo "voz" (resposta falável,
// 2-4 frases) -> a Roberta fala a resposta inteira -> o microfone reabre sozinho.
// Encerra com um toque no botão, se ninguém falar por ~12s ou ao sair do app.
//
// O microfone é SOLTO antes de ela falar: no iPhone, com o microfone aberto o som sai
// baixo pelo alto-falante de ligação (e o microfone ouviria a própria voz dela).
// Durante a conversa o botão de ditado some - um botão morto ao lado confundia.

const CONVERSA_SILENCIO_MS = 3000; // pedido do Alex: "uns 3 segundos"
const CONVERSA_ESPERA_FALA_MS = 12000;
const CONVERSA_MAX_FALA_MS = 90000;

const Conversa = {
  ativa: false,
  ctx: null,
  gravacao: null,
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

// Sinal curtinho quando o microfone de fato abriu ("pode falar", subindo) e quando a
// conversa termina (descendo) - duas notas senoidais com ataque/queda suaves, volume
// baixo; nada de "bip" seco. Toca pelo mesmo AudioContext da conversa.
function _conversaSinal(subindo) {
  const ctx = Conversa.ctx;
  if (!ctx || ctx.state === "closed") return;
  try {
    const notas = subindo ? [660, 990] : [880, 587];
    const t0 = ctx.currentTime + 0.02;
    notas.forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const ganho = ctx.createGain();
      const inicio = t0 + i * 0.09;
      osc.type = "sine";
      osc.frequency.setValueAtTime(freq, inicio);
      ganho.gain.setValueAtTime(0.0001, inicio);
      ganho.gain.exponentialRampToValueAtTime(0.09, inicio + 0.015);
      ganho.gain.exponentialRampToValueAtTime(0.0001, inicio + 0.16);
      osc.connect(ganho).connect(ctx.destination);
      osc.start(inicio);
      osc.stop(inicio + 0.18);
    });
  } catch {}
}

// Uma fala do Alex: {blob, duracaoS} quando ele fica ~3s calado depois de ter falado,
// ou null se ninguém falou / a conversa foi encerrada no meio.
async function _conversaOuvirUmaFala() {
  if (Conversa.ctx.state === "suspended") {
    try {
      await Conversa.ctx.resume();
    } catch {}
  }
  const gravacao = criarGravacao({
    detectarSilencio: true,
    silencioMs: CONVERSA_SILENCIO_MS,
    esperaFalaMs: CONVERSA_ESPERA_FALA_MS,
    maxMs: CONVERSA_MAX_FALA_MS,
    contextoAudio: Conversa.ctx,
  });
  Conversa.gravacao = gravacao;
  try {
    await gravacao.iniciar();
  } catch {
    gravacao.parar("cancelada");
    mostrarErro("Sem acesso ao microfone. Libera nos Ajustes do iPhone pro painel.");
    return null;
  }
  if (Conversa.ativa) {
    _conversaEstado("ouvindo");
    _conversaSinal(true);
  }
  const gravado = await gravacao.pronto;
  if (Conversa.gravacao === gravacao) Conversa.gravacao = null;
  return Conversa.ativa ? gravado : null;
}

async function _conversaLaco() {
  while (Conversa.ativa) {
    const fala = await _conversaOuvirUmaFala();
    if (!Conversa.ativa || !fala) break;

    _conversaEstado("pensando");
    const texto = await transcreverGravacao(fala);
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
  if (mic) mic.hidden = true;
  _conversaLaco();
}

function encerrarConversa() {
  const estavaAtiva = Conversa.ativa;
  Conversa.ativa = false;
  if (Conversa.gravacao) Conversa.gravacao.parar("cancelada");
  Conversa.gravacao = null;
  if (estavaAtiva && vozTocando()) pararVoz();
  if (estavaAtiva) _conversaSinal(false);
  if (!Conversa.btn) return;
  Conversa.btn.classList.remove("conversando");
  Conversa.btn.setAttribute("aria-pressed", "false");
  Conversa.btn.setAttribute("aria-label", "Conversar por voz");
  _conversaEstado("");
  const mic = $("#chat-mic");
  if (mic) mic.hidden = false;
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
