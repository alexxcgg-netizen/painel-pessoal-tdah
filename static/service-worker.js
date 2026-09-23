// v3: antes disso o fetch era cache-first pra TUDO (inclusive "/" no precache), e sem
// handler de "activate" - um SW instalado uma vez, sem o proprio arquivo mudar, nunca
// buscava versao nova de HTML/CSS/JS (o navegador so reinstala quando o BYTE do
// service-worker.js muda). Trocado pra network-first: sempre tenta a rede primeiro
// (app atualizado, dado financeiro/tarefas nunca vem de cache velho), cai pro cache
// so quando a rede falha (funciona offline). "activate" limpa cache de versao antiga.
const CACHE_NAME = "painel-pessoal-v5";
const ASSETS = [
  "/",
  "/static/css/style.css",
  "/static/js/app.js",
  "/static/js/vida.js",
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
