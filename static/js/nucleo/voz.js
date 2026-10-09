// static/js/nucleo/voz.js - Nucleo compartilhado: falarTexto (SpeechSynthesis) - usado pelo chat, resumo da manha e METAR/TAF.
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 3852-3867.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

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

// Voz premium (ElevenLabs, so frases curtas) - POST /api/voz/falar devolve mp3
// (200) ou 204 quando nao ha chave / estourou o limite do mes / deu erro. Em
// QUALQUER outro caso (204, erro, sem rede, play() recusado) cai na voz de
// sempre do iPhone (falarTexto) - o premium nunca pode deixar o botao mudo.
//
// iOS Safari so deixa um <audio> tocar se ele ja tiver sido "tocado" dentro de
// um toque do usuario. Como o mp3 so chega depois de um fetch (o gesto ja
// passou), um UNICO elemento de audio e reaproveitado e destravado de forma
// sincrona no inicio do clique (desbloquearAudioPremium) - quem tem await antes
// de chamar falarPremium precisa chamar desbloquearAudioPremium() primeiro.
const _SILENCIO_WAV =
  "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";
let _elementoAudioPremium = null;
let _audioPremiumTocando = false;
let _urlPremium = null;
let _buscandoPremium = false;

function _audioPremium() {
  if (!_elementoAudioPremium && typeof Audio !== "undefined") {
    _elementoAudioPremium = new Audio();
    _elementoAudioPremium.preload = "auto";
  }
  return _elementoAudioPremium;
}

function desbloquearAudioPremium() {
  const audio = _audioPremium();
  if (!audio || _audioPremiumTocando) return;
  try {
    audio.src = _SILENCIO_WAV;
    const p = audio.play();
    if (p && p.catch) p.catch(() => {});
  } catch (e) {}
}

function vozTocando() {
  return _audioPremiumTocando || ("speechSynthesis" in window && window.speechSynthesis.speaking);
}

function _liberarUrlPremium() {
  if (_urlPremium) URL.revokeObjectURL(_urlPremium);
  _urlPremium = null;
}

function pararVoz() {
  const audio = _elementoAudioPremium;
  _audioPremiumTocando = false;
  if (audio) {
    try {
      audio.pause();
    } catch (e) {}
  }
  _liberarUrlPremium();
  if ("speechSynthesis" in window && window.speechSynthesis.speaking) window.speechSynthesis.cancel();
  document.querySelectorAll(".btn-ouvir.falando").forEach((b) => b.classList.remove("falando"));
}

async function falarPremium(btn, texto) {
  if (!texto || _buscandoPremium) return;
  if (vozTocando()) {
    pararVoz();
    return;
  }
  desbloquearAudioPremium(); // no-op seguro se ja foi destravado neste toque
  const audio = _audioPremium();
  _buscandoPremium = true;
  try {
    if (!audio) throw new Error("sem Audio");
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 8000);
    let res;
    try {
      res = await fetch("/api/voz/falar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto }),
        signal: ctrl.signal,
      });
    } finally {
      clearTimeout(timer);
    }
    if (res.status !== 200) throw new Error("sem audio premium");
    const blob = await res.blob();
    if (!blob.size) throw new Error("audio vazio");
    _liberarUrlPremium();
    _urlPremium = URL.createObjectURL(blob);
    const terminar = () => {
      _audioPremiumTocando = false;
      btn.classList.remove("falando");
      _liberarUrlPremium();
    };
    audio.onended = terminar;
    audio.onerror = terminar;
    audio.src = _urlPremium;
    _audioPremiumTocando = true;
    btn.classList.add("falando");
    _buscandoPremium = false;
    await audio.play();
  } catch (e) {
    _buscandoPremium = false;
    _audioPremiumTocando = false;
    btn.classList.remove("falando");
    _liberarUrlPremium();
    falarTexto(btn, texto);
  }
}

// Resposta inteira pronta pra voz: sem markdown/setas/emoji e no maximo 700
// caracteres (mesmo teto de voz_premium.MAX_CARACTERES), cortando no fim de
// uma frase pra nunca parar no meio de uma palavra.
const MAX_FALA = 700;

function textoParaFala(texto) {
  let t = String(texto == null ? "" : texto)
    .replace(/(^|\n)\s*->\s*/g, "$1")
    .replace(/->/g, ",")
    .replace(/[*_#`>]+/g, "")
    .replace(/\p{Extended_Pictographic}/gu, "")
    .replace(/\s*\n+\s*/g, ". ")
    .replace(/\.\s*\./g, ".")
    .replace(/\s{2,}/g, " ")
    .trim();
  if (t.length > MAX_FALA) {
    const corte = t.slice(0, MAX_FALA);
    const fim = Math.max(corte.lastIndexOf(". "), corte.lastIndexOf("! "), corte.lastIndexOf("? "));
    t = fim > 80 ? corte.slice(0, fim + 1) : corte.slice(0, corte.lastIndexOf(" ")).trim();
  }
  return t;
}

// Igual falarPremium, mas devolve uma Promise que so resolve quando a fala
// TERMINA (ou falha) - o modo conversa precisa disso pra reabrir o microfone
// so depois que ela parou de falar. Cai na voz do iPhone do mesmo jeito.
function falarEsperando(texto) {
  return new Promise(async (resolve) => {
    const t = textoParaFala(texto);
    if (!t) return resolve();
    const audio = _audioPremium();
    const viaIphone = () => {
      if (!("speechSynthesis" in window)) return resolve();
      const u = new SpeechSynthesisUtterance(t);
      u.lang = "pt-BR";
      u.rate = 0.98;
      u.onend = () => resolve();
      u.onerror = () => resolve();
      window.speechSynthesis.speak(u);
    };
    try {
      if (!audio) throw new Error("sem Audio");
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 12000);
      let res;
      try {
        res = await fetch("/api/voz/falar", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ texto: t }),
          signal: ctrl.signal,
        });
      } finally {
        clearTimeout(timer);
      }
      if (res.status !== 200) throw new Error("sem audio premium");
      const blob = await res.blob();
      if (!blob.size) throw new Error("audio vazio");
      _liberarUrlPremium();
      _urlPremium = URL.createObjectURL(blob);
      const terminar = () => {
        _audioPremiumTocando = false;
        _liberarUrlPremium();
        resolve();
      };
      audio.onended = terminar;
      audio.onerror = terminar;
      audio.onpause = () => {
        if (!audio.ended) terminar(); // pararVoz() no meio da fala
      };
      audio.src = _urlPremium;
      _audioPremiumTocando = true;
      await audio.play();
    } catch (e) {
      _audioPremiumTocando = false;
      _liberarUrlPremium();
      viaIphone();
    }
  });
}

// Primeira frase de uma resposta do chat (ate . ! ? ou quebra de linha, max 200
// caracteres; sem pontuacao corta em 200 no ultimo espaco) - so ela vai pra voz
// premium, pra caber no plano gratis.
function primeiraFrase(texto) {
  const t = String(texto == null ? "" : texto).trim();
  const m = t.match(/^(?:[^.!?\n]|[.!?](?=\S))*[.!?]?/);
  let frase = (m ? m[0] : t).trim();
  if (frase.length > 200) {
    const corte = frase.slice(0, 200);
    const i = corte.lastIndexOf(" ");
    frase = (i > 0 ? corte.slice(0, i) : corte).trim();
  }
  return frase;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { primeiraFrase, textoParaFala };
}
