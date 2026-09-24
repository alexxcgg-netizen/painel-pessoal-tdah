// static/js/nucleo/base.js - Nucleo compartilhado: helpers globais basicos ($, NOME_USUARIO, textoPendente, CATEGORIAS_GASTO, vibracao/sons).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 1-9, app.js 45-91.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

const $ = (sel) => document.querySelector(sel);

// app de uso unico (so o Alex) - nome fixo aqui mesmo pra saudacao
// personalizada, mesmo espirito do "so o Alex usa o PIN hoje" do painel_web
// da construtora. Se um dia isso precisar mudar, e essa unica linha.
const NOME_USUARIO = "Alex";

let textoPendente = null;

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
