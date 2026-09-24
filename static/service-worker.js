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
// v14: Fase 7 (X2) - app.js/vida.js divididos em static/js/nucleo/*.js +
// static/js/secoes/<aba>/<secao>.js; todos entram no precache pro app abrir offline.
const CACHE_NAME = "painel-pessoal-v14";
const ASSETS = [
  "/",
  "/static/css/style.css",
  // Fase 7 (X2): mesma lista/ordem de templates/scripts.html (scripts por secao).
  "/static/js/charts.js",
  "/static/js/fila-offline.js",
  "/static/js/cards.js",
  "/static/js/cards-tipos.js",
  "/static/js/nucleo/base.js",
  "/static/js/nucleo/icones.js",
  "/static/js/nucleo/formatos.js",
  "/static/js/nucleo/api.js",
  "/static/js/nucleo/navegacao.js",
  "/static/js/nucleo/ui.js",
  "/static/js/nucleo/linha-do-tempo.js",
  "/static/js/nucleo/voz.js",
  "/static/js/nucleo/vida-base.js",
  "/static/js/ui/bottom-sheet.js",
  "/static/js/ui/secao-recolhivel.js",
  "/static/js/secoes/topo/cabecalho.js",
  "/static/js/secoes/topo/captura.js",
  "/static/js/secoes/hoje/saudacao.js",
  "/static/js/secoes/hoje/sobrecarga.js",
  "/static/js/secoes/hoje/previa-noite.js",
  "/static/js/secoes/hoje/rotina.js",
  "/static/js/secoes/hoje/checkin.js",
  "/static/js/secoes/hoje/essencial.js",
  "/static/js/secoes/hoje/hiperfoco.js",
  "/static/js/secoes/hoje/chat.js",
  "/static/js/secoes/painel/resumo.js",
  "/static/js/secoes/painel/agenda-de-hoje.js",
  "/static/js/secoes/painel/fechamento.js",
  "/static/js/secoes/painel/saude-hoje.js",
  "/static/js/secoes/painel/peso-e-medidas.js",
  "/static/js/secoes/painel/plano-do-dia.js",
  "/static/js/secoes/painel/devo-sair.js",
  "/static/js/secoes/painel/datas-importantes.js",
  "/static/js/secoes/painel/medicamentos.js",
  "/static/js/secoes/painel/memoria.js",
  "/static/js/secoes/painel/esperando-resposta.js",
  "/static/js/secoes/painel/notas.js",
  "/static/js/secoes/painel/diario-de-decisao.js",
  "/static/js/secoes/painel/brain-dump.js",
  "/static/js/secoes/vida/habitos.js",
  "/static/js/secoes/vida/projetos.js",
  "/static/js/secoes/vida/agenda-painel.js",
  "/static/js/secoes/vida/pra-responder.js",
  "/static/js/secoes/vida/lista-de-compras.js",
  "/static/js/secoes/vida/pessoas.js",
  "/static/js/secoes/vida/treino.js",
  "/static/js/secoes/vida/contas-pessoais.js",
  "/static/js/secoes/vida/ainda-usa.js",
  "/static/js/secoes/vida/manutencao.js",
  "/static/js/secoes/vida/garantia.js",
  "/static/js/secoes/vida/viagens.js",
  "/static/js/secoes/vida/lugares.js",
  "/static/js/secoes/vida/ideias-de-presente.js",
  "/static/js/secoes/vida/quero-aprender.js",
  "/static/js/secoes/vida/salvos.js",
  "/static/js/secoes/vida/mensagem-dificil.js",
  "/static/js/secoes/vida/vale-a-pena.js",
  "/static/js/secoes/vida/seu-progresso.js",
  "/static/js/secoes/vida/revisao-trimestral.js",
  "/static/js/secoes/tarefas/tarefas.js",
  "/static/js/secoes/gastos/gastos.js",
  "/static/js/secoes/gastos/metas.js",
  "/static/js/secoes/bancos/bancos.js",
  "/static/js/secoes/bancos/ofx.js",
  "/static/js/secoes/construtora/construtora.js",
  "/static/js/secoes/construtora/contas-a-pagar.js",
  "/static/js/secoes/construtora/cotacoes.js",
  "/static/js/secoes/aviacao/horas-voadas.js",
  "/static/js/secoes/aviacao/registrar-voo.js",
  "/static/js/secoes/aviacao/proximos-voos.js",
  "/static/js/secoes/aviacao/metar.js",
  "/static/js/secoes/assistente/caixa.js",
  "/static/js/secoes/assistente/regras.js",
  "/static/js/secoes/assistente/avisos.js",
  "/static/js/nucleo/init.js",
  "/static/js/visao-dia.js",
  "/static/js/voz-comando.js",
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
