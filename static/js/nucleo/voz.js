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

// Voz premium (ElevenLabs) - POST /api/voz/falar devolve mp3 (200) ou 204 quando nao ha
// chave / estourou o limite / deu erro. Em QUALQUER falha cai na voz do iPhone.
//
// Tocador reescrito em 2026-10-10 (a Roberta "as vezes nao falava / bugava"):
//  - cada fala tem uma GERACAO; falar de novo ou parar invalida a anterior, e todo
//    callback confere a geracao antes de mexer em qualquer coisa (antes, o onpause que o
//    modo conversa deixava no elemento compartilhado apagava o audio do botao "ouvir");
//  - resposta longa e dividida em 2 partes buscadas EM PARALELO: a primeira frase comeca a
//    tocar enquanto o resto ainda e gerado;
//  - vigia de tempo: se o audio/voz do iPhone nunca avisar que acabou, a promessa resolve
//    sozinha - o modo conversa nunca mais fica parado esperando.
//
// iOS Safari so deixa um <audio> tocar se ele ja tiver sido "tocado" dentro de um toque do
// usuario: um UNICO elemento e reaproveitado e destravado no inicio do clique
// (desbloquearAudioPremium) - quem tem await antes de falar precisa chamar isso primeiro.
const _SILENCIO_WAV =
  "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";
const VOZ_TIMEOUT_MS = 9000;
let _elementoAudioPremium = null;
let _vozGeracao = 0;
let _vozAtiva = false; // buscando OU tocando (premium ou iPhone)
let _vozBotao = null;
let _vozFimAtual = null; // encerra na hora a fala em andamento (pararVoz chama)
const _vozUrls = new Set();

function _audioPremium() {
  if (!_elementoAudioPremium && typeof Audio !== "undefined") {
    _elementoAudioPremium = new Audio();
    _elementoAudioPremium.preload = "auto";
  }
  return _elementoAudioPremium;
}

function desbloquearAudioPremium() {
  const audio = _audioPremium();
  if (!audio || _vozAtiva) return;
  try {
    audio.onended = audio.onerror = audio.onpause = null;
    audio.src = _SILENCIO_WAV;
    const p = audio.play();
    if (p && p.catch) p.catch(() => {});
  } catch (e) {}
}

function vozTocando() {
  return _vozAtiva || ("speechSynthesis" in window && window.speechSynthesis.speaking);
}

function _liberarUrls() {
  _vozUrls.forEach((u) => URL.revokeObjectURL(u));
  _vozUrls.clear();
}

function _marcarBotao(btn, ligado) {
  if (btn && btn.classList) btn.classList.toggle("falando", ligado);
}

function pararVoz() {
  _vozGeracao++;
  _vozAtiva = false;
  const fim = _vozFimAtual;
  _vozFimAtual = null;
  if (fim) fim(); // quem espera a fala (modo conversa) fica sabendo na hora
  const audio = _elementoAudioPremium;
  if (audio) {
    audio.onended = audio.onerror = audio.onpause = null;
    // o silencio do destravamento continua: pausar ele logo depois do play() no iOS pode
    // desfazer o "destravado" antes da fala chegar
    if (audio.src !== _SILENCIO_WAV) {
      try {
        audio.pause();
      } catch (e) {}
    }
  }
  _liberarUrls();
  if ("speechSynthesis" in window && window.speechSynthesis.speaking) window.speechSynthesis.cancel();
  document.querySelectorAll(".btn-ouvir.falando").forEach((b) => b.classList.remove("falando"));
  _vozBotao = null;
}

// Divide em ate 2 partes: a primeira frase (ou o que couber em ~160 caracteres) e o resto.
function _partesFala(t) {
  if (t.length <= 180) return [t];
  const m = t.slice(0, 200).match(/^.{40,}?[.!?](\s|$)/);
  const corte = m ? m[0].length : t.slice(0, 160).lastIndexOf(" ");
  if (corte <= 0 || corte >= t.length - 20) return [t];
  return [t.slice(0, corte).trim(), t.slice(corte).trim()];
}

async function _buscarAudio(texto, geracao) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), VOZ_TIMEOUT_MS);
  try {
    const res = await fetch("/api/voz/falar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ texto }),
      signal: ctrl.signal,
    });
    if (res.status !== 200) return null;
    const blob = await res.blob();
    if (!blob.size || geracao !== _vozGeracao) return null;
    const url = URL.createObjectURL(blob);
    _vozUrls.add(url);
    return url;
  } catch (e) {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

// Toca uma URL e resolve true quando termina, false se falhou/foi cancelada.
function _tocarUrl(url, geracao) {
  return new Promise((resolve) => {
    const audio = _audioPremium();
    if (!audio || geracao !== _vozGeracao) return resolve(false);
    let vigia = null;
    let acabou = false;
    const acabar = (ok) => {
      if (acabou) return;
      acabou = true;
      clearTimeout(vigia);
      if (_vozFimAtual === cancelar) _vozFimAtual = null;
      audio.onended = audio.onerror = audio.onpause = audio.onloadedmetadata = null;
      resolve(ok && geracao === _vozGeracao);
    };
    const cancelar = () => acabar(false);
    _vozFimAtual = cancelar;
    audio.onended = () => acabar(true);
    audio.onerror = () => acabar(false);
    audio.onpause = () => {
      if (!audio.ended) acabar(false);
    };
    audio.onloadedmetadata = () => {
      // vigia: duracao do audio + folga (nunca espera pra sempre)
      clearTimeout(vigia);
      const seg = isFinite(audio.duration) ? audio.duration : 60;
      vigia = setTimeout(() => acabar(true), (seg + 3) * 1000);
    };
    vigia = setTimeout(() => acabar(true), 90000);
    audio.src = url;
    const p = audio.play();
    if (p && p.catch) p.catch(() => acabar(false));
  });
}

// Voz do iPhone com vigia de tempo (no iOS, fora de um toque, ela as vezes nem comeca
// e nunca chama onend).
function _falarIphone(texto, geracao) {
  return new Promise((resolve) => {
    if (!("speechSynthesis" in window) || geracao !== _vozGeracao) return resolve();
    const u = new SpeechSynthesisUtterance(texto);
    u.lang = "pt-BR";
    u.rate = 0.98;
    let vigia = null;
    const acabar = () => {
      clearTimeout(vigia);
      if (_vozFimAtual === acabar) _vozFimAtual = null;
      resolve();
    };
    vigia = setTimeout(acabar, texto.length * 85 + 2500);
    _vozFimAtual = acabar;
    u.onend = u.onerror = acabar;
    window.speechSynthesis.speak(u);
  });
}

// Nucleo: busca as partes em paralelo e toca em sequencia; qualquer falha cai no iPhone
// a partir daquela parte. Resolve quando a fala acabou (ou foi interrompida).
async function _falar(texto, btn) {
  const t = textoParaFala(texto);
  if (!t) return;
  pararVoz();
  const geracao = _vozGeracao;
  _vozAtiva = true;
  _vozBotao = btn || null;
  _marcarBotao(btn, true); // ja mostra que esta vindo (antes so acendia quando tocava)
  try {
    const partes = _partesFala(t);
    const buscas = partes.map((parte) => _buscarAudio(parte, geracao));
    for (let i = 0; i < partes.length; i++) {
      if (geracao !== _vozGeracao) return;
      const url = await buscas[i];
      if (geracao !== _vozGeracao) return;
      const tocou = url ? await _tocarUrl(url, geracao) : false;
      if (geracao !== _vozGeracao) return;
      if (!tocou) {
        await _falarIphone(partes.slice(i).join(" "), geracao);
        return;
      }
    }
  } finally {
    if (geracao === _vozGeracao) {
      _vozAtiva = false;
      _marcarBotao(btn, false);
      _liberarUrls();
    }
  }
}

// Botao "ouvir": toque de novo no mesmo botao = parar.
async function falarPremium(btn, texto) {
  if (!texto) return;
  if (vozTocando() && _vozBotao === btn) {
    pararVoz();
    return;
  }
  desbloquearAudioPremium(); // dentro do toque, antes de qualquer await
  await _falar(texto, btn);
}

// Modo conversa: resolve so quando a fala TERMINA (pra reabrir o microfone depois).
function falarEsperando(texto) {
  return _falar(texto, null);
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
  module.exports = { primeiraFrase, textoParaFala, _partesFala };
}
