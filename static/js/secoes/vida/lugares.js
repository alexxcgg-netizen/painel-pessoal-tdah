// static/js/secoes/vida/lugares.js - Secao vida > lugares (HTML: templates/secoes/vida/lugares.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 1420-1529.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

// US-F13: mapa (Leaflet + tiles do OpenStreetMap) carregado sob demanda -
// so na primeira vez que o Alex abrir "ver no mapa" de QUALQUER lugar,
// nunca no carregamento da tela (custa uma chamada de rede a mais que a
// maioria das visitas nao precisa). Versao fixada (1.9.4, cdn.jsdelivr.net,
// ver tasks/fase6/progress-f3.txt) - nunca "latest".
// SRI (revisao da Fase 6): hash sha256 calculado sobre os arquivos EXATOS
// dessas URLs (conferido igual no unpkg) - se o CDN servir outra coisa, o
// navegador recusa e a tela cai no aviso "Não consegui carregar o mapa".
// Trocar a versao = recalcular: openssl dgst -sha256 -binary f | openssl base64 -A
const LEAFLET_JS_URL = "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js";
const LEAFLET_JS_SRI = "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=";
const LEAFLET_CSS_URL = "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css";
const LEAFLET_CSS_SRI = "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=";
let leafletCarregando = null;
function carregarLeaflet() {
  if (window.L) return Promise.resolve();
  if (leafletCarregando) return leafletCarregando;
  leafletCarregando = new Promise((resolve, reject) => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = LEAFLET_CSS_URL;
    link.integrity = LEAFLET_CSS_SRI;
    link.crossOrigin = "anonymous";
    document.head.appendChild(link);
    const script = document.createElement("script");
    script.src = LEAFLET_JS_URL;
    script.integrity = LEAFLET_JS_SRI;
    script.crossOrigin = "anonymous";
    script.addEventListener("load", () => resolve());
    script.addEventListener("error", () => {
      leafletCarregando = null; // deixa tentar de novo num proximo clique
      reject(new Error("falha ao carregar o Leaflet"));
    });
    document.head.appendChild(script);
  });
  return leafletCarregando;
}

// A geocodificacao (Nominatim) e sempre feita pelo SERVIDOR (app.py/
// geocode_nominatim.py - 1 req/s, User-Agent proprio, cache em
// lugares.lat/lng/geocode_status) - o front so LE o resultado que ja veio
// em /api/lugares e desenha (ou mostra o motivo de nao ter mapa). Nunca
// chama Nominatim daqui, senao a politica de 1 req/s e o cache ficariam
// impossiveis de garantir com varios navegadores abertos ao mesmo tempo.
function criarBlocoMapaLugar(l) {
  const box = criarEl("div", "lugar-mapa-box");
  const btn = criarEl("button", "btn btn-secundario lugar-mapa-btn", "Ver no mapa");
  btn.type = "button";
  btn.setAttribute("aria-expanded", "false");
  const mapaEl = criarEl("div", "lugar-mapa");
  mapaEl.hidden = true;
  let iniciado = false;
  btn.addEventListener("click", async () => {
    const abrir = mapaEl.hidden;
    mapaEl.hidden = !abrir;
    btn.textContent = abrir ? "Esconder mapa" : "Ver no mapa";
    btn.setAttribute("aria-expanded", String(abrir));
    if (!abrir || iniciado) return;
    if (l.geocode_status !== "ok" || l.lat == null || l.lng == null) {
      mapaEl.textContent =
        l.geocode_status === "nao_encontrado" || l.geocode_status === "recusado"
          ? "Não encontrei esse lugar no mapa (nome/cidade) - o lugar continua salvo normalmente."
          : l.geocode_status === "erro"
            ? "O serviço de mapa não respondeu - tento localizar de novo mais tarde. O lugar continua salvo normalmente."
            : "Ainda localizando no mapa... tente de novo em instantes.";
      return;
    }
    iniciado = true;
    try {
      await carregarLeaflet();
      const mapa = window.L.map(mapaEl).setView([l.lat, l.lng], 15);
      window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }).addTo(mapa);
      // Leaflet trata STRING no popup como HTML (XSS armazenado com o nome
      // do lugar - revisao da Fase 6): sempre um no DOM com textContent.
      const popup = document.createElement("span");
      popup.textContent = l.nome || "";
      window.L.marker([l.lat, l.lng]).addTo(mapa).bindPopup(popup);
    } catch (e) {
      iniciado = false;
      mapaEl.textContent = "Não consegui carregar o mapa agora (sem rede?) - o lugar continua salvo normalmente.";
    }
  });
  box.appendChild(btn);
  box.appendChild(mapaEl);
  return box;
}

async function loadLugares() {
  const lugares = await apiFetch("/api/lugares");
  if (!Array.isArray(lugares)) return; // null (erro ja mostrado) ou resposta fora do formato
  const lista = $("#lista-lugares");
  lista.innerHTML = "";
  $("#lugares-vazio").hidden = lugares.length > 0;
  lugares.forEach((l) => {
    const li = itemSimples(l.nome, [[l.tipo, l.cidade].filter(Boolean).join(" - "), l.nota], [
      (el) => botaoApagar(`/api/lugares/${l.id}`, el),
    ]);
    li.appendChild(criarBlocoMapaLugar(l));
    lista.appendChild(li);
  });
}

// Fase 7 (V5-extra/C3b): "Novo lugar" abre o formulario no bottom-sheet
// compartilhado (static/js/ui/bottom-sheet.js, V0d). Fallback so pro caso de
// o componente nao ter carregado: alterna o atributo hidden.
function abrirPainelLugar() {
  const sheet = $("#lugar-sheet");
  if (typeof levarSheetProBody === "function") levarSheetProBody(sheet); // ver secoes/vida/viagens.js
  if (typeof window.abrirBottomSheet === "function") window.abrirBottomSheet(sheet);
  else sheet.hidden = false;
}

function fecharPainelLugar() {
  const sheet = $("#lugar-sheet");
  if (typeof window.fecharBottomSheet === "function") window.fecharBottomSheet(sheet);
  else sheet.hidden = true;
}

$("#lugar-abrir-btn").addEventListener("click", abrirPainelLugar);
$("#lugar-cancelar-btn").addEventListener("click", () => {
  $("#lugar-form").reset();
  fecharPainelLugar();
});

ligarForm("#lugar-form", "#lugar-btn", "Salvar lugar", () => {
  const nome = $("#lugar-nome").value.trim();
  return nome ? { nome, cidade: $("#lugar-cidade").value.trim() } : null;
}, "/api/lugares", () => {
  fecharPainelLugar();
  loadLugares();
});
