// static/js/nucleo/api.js - Nucleo compartilhado: mostrarErro/limparErro e apiFetch (com fila offline opcional).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 163-240.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

function mostrarErro(msg) {
  const banner = $("#erro-banner");
  banner.textContent = msg;
  banner.hidden = false;
}

function limparErro() {
  $("#erro-banner").hidden = true;
}

// 45s porque varias chamadas passam pela IA (classificacao, chat, leitura de PDF de
// cotacao) - um timeout curto demais aborta uma chamada real em andamento, nao so
// uma conexao morta.
const API_FETCH_TIMEOUT_MS = 45000;

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
  let res;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_FETCH_TIMEOUT_MS);
  try {
    res = await fetch(url, { ...options, signal: controller.signal });
  } catch (e) {
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
    mostrarErro((data && data.error) || `Erro inesperado (HTTP ${res.status}).`);
    return null;
  }
  limparErro();
  return data;
}
