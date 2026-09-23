// v3: antes disso o fetch era cache-first pra TUDO (inclusive "/" no precache), e sem
// handler de "activate" - um SW instalado uma vez, sem o proprio arquivo mudar, nunca
// buscava versao nova de HTML/CSS/JS (o navegador so reinstala quando o BYTE do
// service-worker.js muda). Trocado pra network-first: sempre tenta a rede primeiro
// (app atualizado, dado financeiro/tarefas nunca vem de cache velho), cai pro cache
// so quando a rede falha (funciona offline). "activate" limpa cache de versao antiga.
// v9: fila offline (BRIEFING Fase 4, item 2). A fila em si (captura/check-in
// enfileirados quando falha rede/timeout) mora em static/js/fila-offline.js,
// rodando na PAGINA com IndexedDB, e nao aqui no SW - decisao deliberada:
// o app roda sobretudo no iPhone do Alex, e o Safari no iOS nunca implementou
// a Background Sync API (nem "sync" nem "periodicsync" chegam a disparar
// nesse SW), entao um SW dependendo dela simplesmente nunca sincronizaria
// sozinho ali. A pagina, em compensacao, ja fica aberta quando uma captura e
// digitada, tem acesso direto as funcoes de recarregar tela (loadSummary,
// loadCheckin...) sem precisar de postMessage SW<->pagina, e o reforco por
// poll (setInterval) funciona identico em qualquer navegador. Esse SW so
// precisa saber que fila-offline.js existe pra ir pro precache (senao o app
// abriria offline sem a fila disponivel) - por isso essa versao sobe.
// v10: comando de voz (Fase 5, Grupo B) - static/js/voz-comando.js reusa a
// mesma fila offline de static/js/fila-offline.js (US-B5), mesma logica do
// v9 acima: so precisa entrar no precache pra existir offline tambem.
// v11: contrato de cards (Fase 6, docs/CARDS.md) - cards.js/cards-tipos.js
// entram no precache pra aba Hoje renderizar os cards tambem offline.
// v12: fim da Fase 6 - visao-dia.js (US-E9) entra no precache e o CSS/JS do
// polimento por secao (Grupo F) precisa chegar no iPhone que ja tem o v11.
// v13: correcoes da revisao independente da Fase 6 - cards de saude com
// `oculto` (cards-tipos.js), popup do mapa sem HTML + SRI do Leaflet e aviso
// de status de voo (vida.js), barra do chat e CSS duplicado (style.css).
const CACHE_NAME = "painel-pessoal-v13";
const ASSETS = [
  "/",
  "/static/css/style.css",
  "/static/js/fila-offline.js",
  "/static/js/cards.js",
  "/static/js/cards-tipos.js",
  "/static/js/app.js",
  "/static/js/vida.js",
  "/static/js/voz-comando.js",
  "/static/js/visao-dia.js",
  "/static/js/charts.js",
  "/static/manifest.json",
  "/static/icons/icon.svg",
  "/static/icons/icon-180.png",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS)));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((nomes) => Promise.all(nomes.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith(
    fetch(event.request)
      .then((res) => {
        const copia = res.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copia));
        return res;
      })
      .catch(() => caches.match(event.request))
  );
});

self.addEventListener("push", (event) => {
  let dados = {};
  try {
    dados = event.data ? event.data.json() : {};
  } catch {
    dados = { titulo: "Painel Pessoal", corpo: event.data ? event.data.text() : "" };
  }
  const titulo = dados.titulo || "Painel Pessoal";
  event.waitUntil(
    self.registration.showNotification(titulo, {
      body: dados.corpo || "",
      icon: "/static/icons/icon-192.png",
      badge: "/static/icons/icon-192.png",
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow("/"));
});
