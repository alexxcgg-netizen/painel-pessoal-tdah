// static/js/nucleo/api.js - Nucleo compartilhado: mostrarErro/limparErro e apiFetch (com fila offline opcional).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 163-240.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

function mostrarErro(msg) {
  const banner = $("#erro-banner");
  if (typeof banner.classList !== "undefined") banner.classList.remove("c2-toast-sai");
  banner.textContent = msg;
  banner.hidden = false;
}

// Vis (C2): saida animada (--dur-rapida, fade) em vez de [hidden]=true na
// hora - saidaAnimada (movimento.js) ja respeita "reduzir movimento" e cai
// pra instantaneo sem `movimento.js` carregado (typeof guard).
function limparErro() {
  const banner = $("#erro-banner");
  if (banner.hidden) return;
  if (typeof saidaAnimada === "function") {
    saidaAnimada(banner, () => {
      banner.hidden = true;
    });
  } else {
    banner.hidden = true;
  }
}

// 45s porque varias chamadas passam pela IA (classificacao, chat, leitura de PDF de
// cotacao) - um timeout curto demais aborta uma chamada real em andamento, nao so
// uma conexao morta.
const API_FETCH_TIMEOUT_MS = 45000;

// Vel A2b: aviso discreto e fixo quando uma chamada demora mais de 3s (ex:
// Render free "acordando" depois de ficar parado) - um so aviso mesmo com
// varias chamadas lentas ao mesmo tempo (contador), some quando a ultima
// que disparou o aviso termina. Nao muda assinatura nem retorno do apiFetch.
const AVISO_LENTO_MS = 3000;
let _apiFetchPendentesLentos = 0;

function _apiFetchMostrarAvisoLento() {
  let banner = document.getElementById("acordando-banner");
  if (!banner) {
    banner = document.createElement("div");
    banner.id = "acordando-banner";
    banner.setAttribute("role", "status");
    banner.setAttribute("aria-live", "polite");
    banner.textContent = "Servidor acordando… (primeiro acesso depois de um tempo parado pode levar até 1 minuto)";
    banner.style.position = "fixed";
    banner.style.left = "0";
    banner.style.right = "0";
    banner.style.top = "0";
    banner.style.zIndex = "9999";
    banner.style.textAlign = "center";
    banner.style.padding = "0.5rem 1rem";
    banner.style.fontSize = "0.85rem";
    banner.style.background = "var(--accent, #2d6cdf)";
    banner.style.color = "#fff";
    document.body.appendChild(banner);
  }
  banner.classList.remove("c2-toast-sai");
  banner.classList.add("c2-toast-entra");
  banner.hidden = false;
}

function _apiFetchEsconderAvisoLento() {
  const banner = document.getElementById("acordando-banner");
  if (!banner || banner.hidden) return;
  if (typeof saidaAnimada === "function") {
    saidaAnimada(banner, () => {
      banner.hidden = true;
    });
  } else {
    banner.hidden = true;
  }
}

// `fila`: so pras acoes criticas de captura de dado do usuario (captura,
// check-in, e desde a Fase 5/US-B5 tambem comando de voz) - o caller passa
// { tipo: "capture"|"checkin"|"comando_voz", id? } (ver static/js/voz-comando.js
// pro caso de comando de voz). Em qualquer outra chamada
// (a esmagadora maioria - leituras e a maioria das escritas), fila fica
// undefined e o comportamento e IDENTICO ao de antes: erro de rede so mostra
// mostrarErro() e devolve null. So quando fila e passado e o fetch falha por
// rede/timeout (nunca por uma resposta HTTP real, 4xx/5xx - essa nem cai
// nesse catch) e que a requisicao vira um item na fila local (IndexedDB) em
// vez de virar um erro pro usuario - devolve { __enfileirado: true } pro
// caller decidir a UX otimista (ex: mostrar como se tivesse capturado, sem
// esperar a classificacao da IA que so vai vir quando sincronizar de verdade).
async function apiFetch(url, options, fila) {
  // Vel (vel3): escrita ou falha = o que as abas mostram pode estar velho;
  // a proxima troca de aba recarrega (cache curto em nucleo/navegacao.js).
  const _metodo = ((options && options.method) || "GET").toUpperCase();
  const _invalidarSeEscreveu = () => {
    if (_metodo !== "GET" && typeof invalidarDadosAbas === "function") invalidarDadosAbas();
  };
  let res;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_FETCH_TIMEOUT_MS);
  let avisouLento = false;
  const avisoTimeoutId = setTimeout(() => {
    avisouLento = true;
    _apiFetchPendentesLentos++;
    _apiFetchMostrarAvisoLento();
  }, AVISO_LENTO_MS);
  const pararAvisoLento = () => {
    clearTimeout(avisoTimeoutId);
    if (avisouLento) {
      _apiFetchPendentesLentos = Math.max(0, _apiFetchPendentesLentos - 1);
      if (_apiFetchPendentesLentos === 0) _apiFetchEsconderAvisoLento();
    }
  };
  try {
    res = await fetch(url, { ...options, signal: controller.signal });
  } catch (e) {
    pararAvisoLento();
    if (typeof invalidarDadosAbas === "function") invalidarDadosAbas();
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
  pararAvisoLento();
  _invalidarSeEscreveu();
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
    if (typeof invalidarDadosAbas === "function") invalidarDadosAbas();
    mostrarErro((data && data.error) || `Erro inesperado (HTTP ${res.status}).`);
    return null;
  }
  limparErro();
  return data;
}
