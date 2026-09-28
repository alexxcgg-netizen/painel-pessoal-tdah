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
let _audioPremium = null;
let _buscandoPremium = false;

function _pararVozPremium() {
  const audio = _audioPremium;
  _audioPremium = null;
  if (audio) {
    try {
      audio.pause();
    } catch (e) {}
    if (audio._urlPremium) URL.revokeObjectURL(audio._urlPremium);
  }
  document.querySelectorAll(".btn-ouvir.falando").forEach((b) => b.classList.remove("falando"));
}

async function falarPremium(btn, texto) {
  if (!texto || _buscandoPremium) return;
  const falandoSintetico = "speechSynthesis" in window && window.speechSynthesis.speaking;
  if (_audioPremium || falandoSintetico) {
    _pararVozPremium();
    if (falandoSintetico) window.speechSynthesis.cancel();
    return;
  }
  let audio = null;
  _buscandoPremium = true;
  try {
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
    _buscandoPremium = false;
    if (res.status !== 200) throw new Error("sem audio premium");
    const blob = await res.blob();
    if (!blob.size) throw new Error("audio vazio");
    audio = new Audio(URL.createObjectURL(blob));
    audio._urlPremium = audio.src;
    _audioPremium = audio;
    const terminar = () => {
      if (_audioPremium === audio) _audioPremium = null;
      btn.classList.remove("falando");
      URL.revokeObjectURL(audio._urlPremium);
    };
    audio.onended = terminar;
    audio.onerror = terminar;
    btn.classList.add("falando");
    await audio.play();
  } catch (e) {
    _buscandoPremium = false;
    if (audio) {
      if (_audioPremium === audio) _audioPremium = null;
      btn.classList.remove("falando");
      URL.revokeObjectURL(audio._urlPremium);
    }
    falarTexto(btn, texto);
  }
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
  module.exports = { primeiraFrase };
}
