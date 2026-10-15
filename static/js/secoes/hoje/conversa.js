// static/js/secoes/hoje/conversa.js - Modo conversa por voz do chat (botão #chat-conversa).
// Script clássico (escopo global compartilhado) - carrega depois de nucleo/voz.js e hoje/chat.js
// (usa criarGravacao/transcreverGravacao de chat.js).
//
// Ida e volta, como uma ligação: ouve -> a fala termina no toque em "Pronto" OU ~1,5s calado ->
// transcreve (Whisper, /api/voz/transcrever) -> manda pro chat com modo "voz" (resposta falável,
// 2-4 frases) -> a Roberta fala a resposta inteira -> o microfone reabre sozinho.
// 2026-10-14 (pedido do Alex: "tipo ChatGPT, infinito"): a conversa NÃO fecha mais sozinha se
// ninguém falar (antes: 12s) - só acaba no toque no botão de conversa ou ao sair do app. E o
// enviar vira um "Pronto" grande enquanto ouve: com voz/barulho de fundo segurando o silêncio,
// o toque resolve na hora.
//
// O microfone é SOLTO antes de ela falar: no iPhone, com o microfone aberto o som sai
// baixo pelo alto-falante de ligação (e o microfone ouviria a própria voz dela).
// Durante a conversa o botão de ditado some - um botão morto ao lado confundia.

// 2026-10-13: 3s -> 1,5s ("demora muito ate mandar"). O que mais segurava era a voz de fundo
// contando como fala - agora fundo conta como silencio (VOZ_FRACAO_FUNDO em chat.js) - e o botao
// de enviar manda na hora.
const CONVERSA_SILENCIO_MS = 1500;
// sem prazo pra ele comecar a falar: a conversa fica aberta ate ele encerrar
const CONVERSA_ESPERA_FALA_MS = Infinity;
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
  const form = $("#chat-form");
  if (form) {
    form.classList.toggle("conversa-ouvindo", estado === "ouvindo");
    form.classList.toggle("conversa-ativa", !!estado);
  }
  const enviar = $("#chat-send");
  if (enviar) enviar.setAttribute("aria-label", estado === "ouvindo" ? "Pronto, mandar a fala" : "Enviar");
}

// Sinal "Suave" (escolhido pelo Alex entre 3 amostras): quando o microfone de fato abriu
// ("pode falar", Dó -> Sol subindo) e quando a conversa termina (Sol -> Dó descendo).
// Cada nota: fundamental + 2º e 3º harmônicos bem baixos (corpo quente, nada "eletrônico"),
// entrada redonda de 30ms (curva seno, sem estalo), queda exponencial longa e um eco curto
// de sala pequena. Toca pelo mesmo AudioContext da conversa.
const _SINAL_NOTAS = { sobe: [523.25, 783.99], desce: [783.99, 523.25] };
const _SINAL_PARCIAIS = [
  [1, 1.0, 0],
  [2, 0.18, 6],
  [3, 0.05, 10],
]; // [harmônico, volume, queda extra por segundo]
const _SINAL_ATAQUE = 0.03;
let _sinalCurvaAtaque = null;

function _conversaSinal(subindo) {
  const ctx = Conversa.ctx;
  if (!ctx || ctx.state === "closed") return;
  try {
    if (!_sinalCurvaAtaque) {
      _sinalCurvaAtaque = new Float32Array(32);
      for (let i = 0; i < 32; i++) _sinalCurvaAtaque[i] = Math.sin((0.5 * Math.PI * i) / 31);
    }
    const pico = subindo ? 0.1 : 0.09;
    // eco curto: duas repetições que somem (sala pequena)
    const saida = ctx.createGain();
    saida.connect(ctx.destination);
    [
      [0.11, 0.18],
      [0.187, 0.09],
    ].forEach(([atraso, ganho]) => {
      const d = ctx.createDelay(0.5);
      const g = ctx.createGain();
      d.delayTime.value = atraso;
      g.gain.value = ganho;
      saida.connect(d).connect(g).connect(ctx.destination);
    });

    const t0 = ctx.currentTime + 0.02;
    (subindo ? _SINAL_NOTAS.sobe : _SINAL_NOTAS.desce).forEach((freq, i) => {
      const inicio = t0 + i * 0.12;
      const queda = i === 0 ? 0.22 : 0.3;
      _SINAL_PARCIAIS.forEach(([harm, volume, quedaExtra]) => {
        const osc = ctx.createOscillator();
        const ganho = ctx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(freq * harm, inicio);
        const alvo = pico * volume;
        ganho.gain.setValueAtTime(0, inicio);
        ganho.gain.setValueCurveAtTime(_sinalCurvaAtaque.map((v) => v * alvo), inicio, _SINAL_ATAQUE);
        // queda exponencial: constante de tempo combinada (nota + harmônico)
        ganho.gain.setTargetAtTime(0, inicio + _SINAL_ATAQUE, 1 / (1 / queda + quedaExtra));
        osc.connect(ganho).connect(saida);
        osc.start(inicio);
        osc.stop(inicio + _SINAL_ATAQUE + queda * 6);
      });
    });
  } catch {}
}

// Uma fala do Alex: {blob, duracaoS} quando ele toca em "Pronto" ou fica ~1,5s calado depois de
// ter falado; {semVoz} se o limite de 90s passou sem voz; null se a conversa foi encerrada no meio.
// `sinal`: o "pode falar" so toca quando e a vez dele de verdade - nao a cada 90s de silencio.
async function _conversaOuvirUmaFala(sinal = true) {
  // "interrupted" (iPhone na volta do fundo) tambem para o detector - nao so "suspended"
  if (Conversa.ctx.state !== "running") {
    try {
      await Promise.race([Conversa.ctx.resume(), new Promise((r) => setTimeout(r, 300))]);
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
  } catch (e) {
    gravacao.parar("cancelada");
    _avisoFalhaMicrofone(e);
    return null;
  }
  if (Conversa.ativa) {
    _conversaEstado("ouvindo");
    if (sinal) _conversaSinal(true);
  }
  const gravado = await gravacao.pronto;
  if (Conversa.gravacao === gravacao) Conversa.gravacao = null;
  return Conversa.ativa ? gravado : null;
}

async function _conversaLaco() {
  let sinal = true;
  while (Conversa.ativa) {
    const fala = await _conversaOuvirUmaFala(sinal);
    if (!Conversa.ativa || !fala) break;
    // barulho sem voz / 90s calado: volta a ouvir em silencio, sem mandar nada nem tocar o sinal
    sinal = !fala.semVoz && !fala.curto;
    if (fala.semVoz || fala.curto) continue;

    _conversaEstado("pensando");
    // limpar: tira muleta/autocorrecao e frase solta de outra pessoa no fundo (ia/funcoes/fala.py)
    const texto = await transcreverGravacao(fala, { limpar: true });
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
  // ouvindo na conversa: o botao de enviar (campo vazio) vira "Pronto" e manda a fala na hora, sem
  // esperar o silencio. O texto nasce escondido (largura 0) e abre com a mola so na vez dele.
  const enviar = $("#chat-send");
  if (enviar && !enviar.querySelector(".chat-send-pronto")) {
    const rotulo = document.createElement("span");
    rotulo.className = "chat-send-pronto";
    rotulo.setAttribute("aria-hidden", "true");
    rotulo.textContent = "Pronto";
    enviar.appendChild(rotulo);
  }
  const form = $("#chat-form");
  if (form) {
    form.addEventListener(
      "submit",
      (ev) => {
        if (!Conversa.ativa || !Conversa.gravacao || $("#chat-input").value.trim()) return;
        ev.preventDefault();
        ev.stopImmediatePropagation();
        vibrar(18);
        Conversa.gravacao.parar("fala");
      },
      { capture: true }
    );
  }
  // saiu do app / trocou de aba no meio: não deixa microfone aberto em segundo plano
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && Conversa.ativa) encerrarConversa();
  });
}
