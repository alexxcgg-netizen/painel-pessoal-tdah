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
