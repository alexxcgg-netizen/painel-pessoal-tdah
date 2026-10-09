// static/js/nucleo/localizacao.js - Localização do celular pro chat (pedido do Alex, 2026-10-09).
// Script clássico (escopo global compartilhado) - a ordem de carga está em templates/scripts.html.
//
// Pega o GPS ao abrir o app e de novo a cada mensagem do chat (só quando a última leitura
// já tem mais de 5 min). Nada em segundo plano: o iPhone nem deixa um app web fazer isso.
// O iPhone pede permissão na primeira vez; recusou = o painel segue como antes (Brusque/casa).
// A posição vai só pro servidor do próprio painel, junto da mensagem - nunca na URL.

const LOCAL_VALIDADE_MS = 5 * 60 * 1000;
const LOCAL_ESPERA_CHAT_MS = 2500; // quanto a mensagem espera um GPS novo antes de ir sem ele

let _localAtual = null; // { lat, lon, precisao, em }
let _localBuscando = null;

function _lerGps(timeoutMs) {
  if (!("geolocation" in navigator)) return Promise.resolve(null);
  if (_localBuscando) return _localBuscando;
  _localBuscando = new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        _localAtual = {
          lat: pos.coords.latitude,
          lon: pos.coords.longitude,
          precisao: pos.coords.accuracy,
          em: Date.now(),
        };
        resolve(_localAtual);
      },
      () => resolve(null), // recusou / sem sinal: segue sem localização
      { enableHighAccuracy: false, maximumAge: LOCAL_VALIDADE_MS, timeout: timeoutMs }
    );
  }).finally(() => {
    _localBuscando = null;
  });
  return _localBuscando;
}

// Ao abrir o app: busca sem pressa (resultado fica guardado pra próxima mensagem).
function iniciarLocalizacao() {
  _lerGps(15000);
}

// Pro corpo do POST /api/chat: { lat, lon, precisao, idade_s } ou null.
async function localParaChat() {
  const fresca = _localAtual && Date.now() - _localAtual.em < LOCAL_VALIDADE_MS;
  if (!fresca) {
    await Promise.race([_lerGps(10000), new Promise((r) => setTimeout(r, LOCAL_ESPERA_CHAT_MS))]);
  }
  if (!_localAtual) return null;
  return {
    lat: _localAtual.lat,
    lon: _localAtual.lon,
    precisao: Math.round(_localAtual.precisao || 0),
    idade_s: Math.round((Date.now() - _localAtual.em) / 1000),
  };
}
