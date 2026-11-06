// static/js/nucleo/api.js - Nucleo compartilhado: mostrarErro/limparErro e apiFetch (com fila offline opcional).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 163-240.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

// Toast some sozinho depois de ERRO_TOAST_MS (cobria o título da tela até alguém
// tocar nele); tocar continua fechando na hora e um erro novo reinicia a contagem.
const ERRO_TOAST_MS = 6000;
let _erroToastTimer = null;

function mostrarErro(msg) {
  const banner = $("#erro-banner");
  if (typeof banner.classList !== "undefined") banner.classList.remove("c2-toast-sai");
  banner.textContent = msg;
  banner.hidden = false;
  if (_erroToastTimer) clearTimeout(_erroToastTimer);
  _erroToastTimer = setTimeout(() => {
    _erroToastTimer = null;
    limparErro();
  }, ERRO_TOAST_MS);
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

// R2: o banner virou toast fixo no topo (static/css/base/abas-barra.css, #erro-banner) - nao
// empurra mais a tela; tocar nele fecha (a proxima chamada que der certo tambem limpa).
(function () {
  const banner = typeof document !== "undefined" ? document.getElementById("erro-banner") : null;
  if (banner && banner.addEventListener) banner.addEventListener("click", limparErro);
})();

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
const URLS_OPCIONAIS_SEM_INVALIDAR = ["/api/summary/today"];
function ehUrlOpcionalSemInvalidar(url) {
  const caminho = String(url || "").split("?")[0];
  return URLS_OPCIONAIS_SEM_INVALIDAR.includes(caminho);
}

// App do iPhone (native/ios/App/PainelApp.swift, 2026-11-06): marcou Feito/Desfazer/mudou hora aqui dentro
// e a ilha/tela bloqueada nao sabia ate sair e voltar pro app. Depois de uma escrita, avisa o app (que
// confere a atividade ao vivo e os avisos). Fora do app (Safari/PWA) o canal nao existe e nada acontece.
let _avisarAppTimer = null;
function avisarAppNativo() {
  const canal =
    typeof window !== "undefined" && window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.painel;
  if (!canal) return;
  clearTimeout(_avisarAppTimer);
  // junta varias escritas seguidas (ex.: Feito + Desfazer) num aviso so
  _avisarAppTimer = setTimeout(() => {
    try {
      canal.postMessage("mudou");
    } catch (_) {
      // app antigo sem o canal: ignora
    }
  }, 800);
}

async function apiFetch(url, options, fila) {
  // Vel (vel3): escrita ou falha = o que as abas mostram pode estar velho;
  // a proxima troca de aba recarrega (cache curto em nucleo/navegacao.js).
  const _metodo = ((options && options.method) || "GET").toUpperCase();
  const _invalidarSeEscreveu = () => {
    if (_metodo !== "GET" && typeof invalidarDadosAbas === "function") invalidarDadosAbas();
    // numero no icone do app (nucleo/badge.js): qualquer escrita pode ter mudado o que vence hoje
    if (_metodo !== "GET" && typeof Badge !== "undefined") Badge.atualizarDepois();
    if (_metodo !== "GET") avisarAppNativo();
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
        : "Sem conexao com o servidor. Confere se o painel está rodando."
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
    // Vel (vel4): o resumo do dia depende de IA (teto de custo/fora do ar ->
    // 502/429) e a tela ja tem fallback (lerResumoCache). Se o erro dele
    // invalidasse o cache curto das abas, o Painel refazia os ~18 GET /api a
    // CADA visita enquanto a IA estivesse fora. Os demais erros continuam
    // invalidando.
    if (!ehUrlOpcionalSemInvalidar(url) && typeof invalidarDadosAbas === "function") invalidarDadosAbas();
    mostrarErro((data && data.error) || `Erro inesperado (HTTP ${res.status}).`);
    return null;
  }
  limparErro();
  _avisarTarefaMudou(url, _metodo);
  return data;
}

// 2026-10-14 (print do Alex: concluiu o tricologista na aba Tarefas e o card da IA continuou
// desmarcado): qualquer tela que conclui/reabre uma tarefa (Tarefas, Inicio, saudacao, card)
// avisa o resto - o chat escuta "tarefa:mudou" e acerta as caixinhas dos cards na hora.
function _avisarTarefaMudou(url, metodo) {
  if (metodo !== "POST" || typeof document === "undefined") return;
  const m = /\/api\/tasks\/(\d+)\/(complete|reabrir)(?:$|\?)/.exec(String(url));
  if (!m) return;
  document.dispatchEvent(new CustomEvent("tarefa:mudou", { detail: { id: m[1], concluida: m[2] === "complete" } }));
}

// Diagnostico do aparelho (2026-10-15): bug de iPhone (barra pela metade, microfone que nao grava)
// era corrigido no chute. Manda um retrato curto (so numeros/nome de erro) pra /api/diagnostico;
// o Claude le pelo scripts/ler_chat.py. Silencioso: nunca mostra erro, no maximo 1 por tipo/20 s.
const _diagnosticoUltimo = {};
function enviarDiagnostico(tipo, dados, forcar = false) {
  try {
    const agora = Date.now();
    if (!forcar && agora - (_diagnosticoUltimo[tipo] || 0) < 20000) return;
    _diagnosticoUltimo[tipo] = agora;
    fetch("/api/diagnostico", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tipo, dados }),
      keepalive: true,
    }).catch(() => {});
  } catch {}
}
