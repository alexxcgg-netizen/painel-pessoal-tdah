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
// v15: fim da Fase 7 - CSS/JS das faixas V/C/P1b/M1 (componentes, bottom-sheet, Caixa,
// custo de IA, assinaturas...) mudaram depois do v14; o iPhone que ja tem o v14 precisa
// buscar tudo de novo. Lista conferida contra scripts.html/head.html/fase7.css.
// v16: Fase 8 F1 - gastos.js/gastos.html mudaram (lista unificada com selo de origem
// Nubank/manual, botao "Sincronizar Nubank").
// v91: animacao 3D do exercicio da vez no treino ao vivo (exercicio-3d.js, 43 exercicios).
// v92: carga x sono no treino (barras no card de troca + "Dormiu quanto?" no treino ao vivo).
// v93: card "como tu ta hoje?" (check-in no chat, leva de 22/10).
// v94: botoes "Feito" / "Adiar 1 h" no aviso de uma tarefa (+ aviso de teste que diz se o iPhone mostrou).
// v96: treino ao vivo em 3D de verdade (215 exercicios, corpo MakeHuman + three.js). So o catalogo
// (treino3d-catalogo.js) entra no precache; o motor/corpo/three (~1,8 MB) vao pro cache na 1a vez que
// um card de treino aparece (o fetch abaixo guarda tudo de /static/).
// v97: Laboratorio v4, os 33 "quero" (foco, tempo, avisos e manha, memoria da IA, dinheiro, aviacao,
// fechamento) - um arquivo de cards por grupo; ver docs/briefings/2026-10-30-lab-v4-*.md.
// v102: abrir o app sem ir a rede pra cada arquivo (leva "perfeicao", 2026-11-05). A pagina agora pede
// /static/x.js?v=<impressao do conteudo> (estaticos.py) e toda resposta de /static/ traz a mesma impressao
// no cabecalho X-Versao. Copia guardada com a versao pedida sai daqui na hora; versao diferente (ou pedido
// sem ?v, como os modulos do treino 3D) vai a rede como antes e cai na copia velha se a rede falhar. Uma copia
// por arquivo (a chave e o caminho, sem o ?v), entao o cache nao cresce a cada mudanca.
const CACHE_NAME = "painel-pessoal-v105";
const ASSETS = [
  "/",
  // R2-css: style.css dividido em arquivos por assunto (mesma ordem de carga do
  // templates/head.html); style.css em si nao existe mais.
  "/static/css/base/variaveis.css",
  "/static/css/base/reset.css",
  "/static/css/base/botoes.css",
  "/static/css/base/layout.css",
  "/static/css/base/abas-barra.css",
  "/static/css/secoes-antigas/parte-01.css",
  "/static/css/secoes-antigas/parte-02.css",
  "/static/css/secoes-antigas/parte-03.css",
  "/static/css/secoes-antigas/parte-04.css",
  "/static/css/secoes-antigas/parte-05.css",
  "/static/css/secoes-antigas/parte-06.css",
  "/static/css/secoes-antigas/parte-07.css",
  "/static/css/fase7.css",
  "/static/css/ui/tokens.css",
  "/static/css/ui/movimento.css",
  "/static/css/ui/desempenho.css",
  "/static/css/ui/componentes/botao.css",
  "/static/css/ui/componentes/secao.css",
  "/static/css/ui/componentes/card.css",
  "/static/css/ui/componentes/chip.css",
  "/static/css/ui/componentes/campo.css",
  "/static/css/ui/componentes/lista-item.css",
  "/static/css/ui/componentes/bottom-sheet.css",
  "/static/css/ui/componentes/navegacao.css",
  "/static/css/secoes/topo.css",
  "/static/css/secoes/hoje.css",
  "/static/css/secoes/painel.css",
  "/static/css/secoes/vida.css",
  "/static/css/secoes/tarefas.css",
  "/static/css/secoes/gastos.css",
  "/static/css/secoes/bancos.css",
  "/static/css/secoes/construtora.css",
  "/static/css/secoes/aviacao.css",
  "/static/css/secoes/assistente.css",
  "/static/css/secoes/topo/cabecalho.css",
  "/static/css/secoes/topo/captura.css",
  "/static/css/secoes/hoje/saudacao.css",
  "/static/css/secoes/hoje/sobrecarga.css",
  "/static/css/secoes/hoje/previa-noite.css",
  "/static/css/secoes/hoje/rotina.css",
  "/static/css/secoes/hoje/checkin.css",
  "/static/css/secoes/hoje/essencial.css",
  "/static/css/secoes/hoje/hiperfoco.css",
  "/static/css/secoes/hoje/chat.css",
  "/static/css/secoes/hoje/cards-vivos.css",
  "/static/css/secoes/hoje/cards-dia.css",
  "/static/css/secoes/hoje/cards-tempo.css",
  "/static/css/secoes/hoje/cards-foco-ideias.css",
  "/static/css/secoes/hoje/cards-manha.css",
  "/static/css/secoes/hoje/cards-premium.css",
  "/static/css/secoes/hoje/cards-aviacao.css",
  "/static/css/secoes/hoje/cards-aviacao-lab.css",
  "/static/css/secoes/hoje/cards-saidas.css",
  "/static/css/secoes/hoje/cards-viagem.css",
  "/static/css/secoes/hoje/cards-automacao.css",
  "/static/css/secoes/hoje/cards-dinheiro.css",
  "/static/css/secoes/hoje/cards-memoria.css",
  "/static/css/secoes/hoje/cards-rotina.css",
  "/static/css/secoes/hoje/cards-fechamento.css",
  "/static/css/secoes/hoje/cards-d.css",
  "/static/css/secoes/hoje/cards-onde.css",
  "/static/css/secoes/hoje/cards-esperto.css",
  "/static/css/secoes/hoje/visao-do-dia.css",
  "/static/css/secoes/painel/resumo.css",
  "/static/css/secoes/painel/agenda-de-hoje.css",
  "/static/css/secoes/painel/fechamento.css",
  "/static/css/secoes/painel/saude-hoje.css",
  "/static/css/secoes/painel/custo-ia.css",
  "/static/css/secoes/painel/peso-e-medidas.css",
  "/static/css/secoes/painel/plano-do-dia.css",
  "/static/css/secoes/painel/devo-sair.css",
  "/static/css/secoes/painel/datas-importantes.css",
  "/static/css/secoes/painel/medicamentos.css",
  "/static/css/secoes/painel/memoria.css",
  "/static/css/secoes/painel/esperando-resposta.css",
  "/static/css/secoes/painel/notas.css",
  "/static/css/secoes/painel/diario-de-decisao.css",
  "/static/css/secoes/painel/brain-dump.css",
  "/static/css/secoes/vida/habitos.css",
  "/static/css/secoes/vida/projetos.css",
  "/static/css/secoes/vida/agenda-painel.css",
  "/static/css/secoes/vida/pra-responder.css",
  "/static/css/secoes/vida/lista-de-compras.css",
  "/static/css/secoes/vida/pessoas.css",
  "/static/css/secoes/vida/treino.css",
  "/static/css/secoes/vida/contas-pessoais.css",
  "/static/css/secoes/vida/ainda-usa.css",
  "/static/css/secoes/vida/manutencao.css",
  "/static/css/secoes/vida/garantia.css",
  "/static/css/secoes/vida/viagens.css",
  "/static/css/secoes/vida/lugares.css",
  "/static/css/secoes/vida/ideias-de-presente.css",
  "/static/css/secoes/vida/quero-aprender.css",
  "/static/css/secoes/vida/salvos.css",
  "/static/css/secoes/vida/mensagem-dificil.css",
  "/static/css/secoes/vida/vale-a-pena.css",
  "/static/css/secoes/vida/seu-progresso.css",
  "/static/css/secoes/vida/revisao-trimestral.css",
  "/static/css/secoes/tarefas/tarefas.css",
  "/static/css/secoes/gastos/gastos.css",
  "/static/css/secoes/gastos/conversa.css",
  "/static/css/secoes/gastos/metas.css",
  "/static/css/secoes/gastos/assinaturas.css",
  "/static/css/secoes/bancos/bancos.css",
  "/static/css/secoes/construtora/construtora.css",
  "/static/css/secoes/construtora/contas-a-pagar.css",
  "/static/css/secoes/construtora/cotacoes.css",
  "/static/css/secoes/aviacao/horas-voadas.css",
  "/static/css/secoes/aviacao/registrar-voo.css",
  "/static/css/secoes/aviacao/proximos-voos.css",
  "/static/css/secoes/aviacao/metar.css",
  "/static/css/secoes/aviacao/painel-de-voo.css",
  "/static/css/secoes/assistente/caixa.css",
  "/static/css/secoes/assistente/regras.css",
  "/static/css/secoes/assistente/avisos.css",
  // Fase 7 (X2): mesma lista/ordem de templates/scripts.html (scripts por secao).
  "/static/js/charts.js",
  "/static/js/fila-offline.js",
  "/static/js/cards.js",
  "/static/js/cards-d.js",
  "/static/js/treino3d-catalogo.js",
  "/static/js/cards-tipos.js",
  "/static/js/cards-vivos.js",
  "/static/js/cards-dia.js",
  "/static/js/cards-tempo.js",
  "/static/js/secoes/topo/fita.js",
  "/static/js/cards-foco-ideias.js",
  "/static/js/cards-manha.js",
  "/static/js/cards-premium.js",
  "/static/js/cards-aviacao.js",
  "/static/js/cards-aviacao-lab.js",
  "/static/js/cards-saidas.js",
  "/static/js/cards-viagem.js",
  "/static/js/cards-automacao.js",
  "/static/js/cards-dinheiro.js",
  "/static/js/cards-memoria.js",
  "/static/js/cards-rotina.js",
  "/static/js/cards-fechamento.js",
  "/static/js/cards-onde.js",
  "/static/js/cards-esperto.js",
  "/static/js/cards-medalha.js",
  "/static/js/nucleo/base.js",
  "/static/js/nucleo/icones.js",
  "/static/js/nucleo/formatos.js",
  "/static/js/nucleo/api.js",
  "/static/js/nucleo/badge.js",
  "/static/js/nucleo/cores.js",
  "/static/js/nucleo/movimento.js",
  "/static/js/nucleo/navegacao.js",
  "/static/js/nucleo/ui.js",
  "/static/js/nucleo/linha-do-tempo.js",
  "/static/js/nucleo/voz.js",
  "/static/js/nucleo/localizacao.js",
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
  "/static/js/secoes/hoje/conversa.js",
  "/static/js/secoes/hoje/foto.js",
  "/static/js/secoes/hoje/visao-do-dia.js",
  "/static/js/secoes/painel/resumo.js",
  "/static/js/secoes/painel/agenda-de-hoje.js",
  "/static/js/secoes/painel/fechamento.js",
  "/static/js/secoes/painel/saude-hoje.js",
  "/static/js/secoes/painel/custo-ia.js",
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
  "/static/js/secoes/tarefas/linha-do-tempo-tarefas.js",
  "/static/js/secoes/tarefas/tarefas.js",
  "/static/js/secoes/tarefas/arrastar-excluir.js",
  "/static/js/secoes/tarefas/folha-tarefa.js",
  "/static/js/secoes/gastos/gastos.js",
  "/static/js/secoes/gastos/metas.js",
  "/static/js/secoes/gastos/assinaturas.js",
  "/static/js/secoes/bancos/bancos.js",
  "/static/js/secoes/construtora/construtora.js",
  "/static/js/secoes/construtora/contas-a-pagar.js",
  "/static/js/secoes/construtora/cotacoes.js",
  "/static/js/secoes/aviacao/horas-voadas.js",
  "/static/js/secoes/aviacao/registrar-voo.js",
  "/static/js/secoes/aviacao/proximos-voos.js",
  "/static/js/secoes/aviacao/metar.js",
  "/static/js/secoes/aviacao/painel-de-voo.js",
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
  event.waitUntil(guardarTudo());
});

// Guarda os ASSETS 8 por vez (v102). O addAll pedia os ~220 de uma vez: pelo Tailscale (HTTP/2) chegavam todos
// juntos e o waitress recusava conexao ("connection limit", 75 vezes entre 02 e 04/11), com o app abrindo ao mesmo
// tempo. Arquivo que falha derruba a instalacao inteira, igual ao addAll (o teste do SW real confere).
async function guardarTudo() {
  const cache = await caches.open(CACHE_NAME);
  const fila = ASSETS.slice();
  const trabalhador = async () => {
    while (fila.length) {
      const url = fila.shift();
      const res = await fetch(url);
      if (!res.ok) throw new Error(`precache: ${url} -> ${res.status}`);
      await cache.put(url, res);
    }
  };
  await Promise.all(Array.from({ length: 8 }, trabalhador));
}

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
  // alcance "/" (pra notificacao funcionar), mas so os arquivos de /static/ passam por aqui:
  // dados (/api), login e a pagina continuam indo direto pro servidor, como sempre foi.
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin || !url.pathname.startsWith("/static/")) return;
  // pedido de pedaco (audio/video) o navegador resolve sozinho: resposta inteira no lugar dele quebra o Safari
  if (event.request.headers.has("range")) return;
  event.respondWith(doCacheOuDaRede(event, url));
});

async function doCacheOuDaRede(event, url) {
  const cache = await caches.open(CACHE_NAME);
  const chave = url.pathname;
  const guardado = await cache.match(chave, { ignoreVary: true });
  const versao = url.searchParams.get("v");
  if (guardado && versao && guardado.headers.get("X-Versao") === versao) return guardado;
  try {
    const res = await fetch(event.request);
    if (res.ok) event.waitUntil(cache.put(chave, res.clone()).catch(() => {}));
    return res;
  } catch (erro) {
    if (guardado) return guardado;
    throw erro;
  }
}

self.addEventListener("push", (event) => {
  let dados = {};
  try {
    dados = event.data ? event.data.json() : {};
  } catch {
    dados = { titulo: "Painel Pessoal", corpo: event.data ? event.data.text() : "" };
  }
  const titulo = dados.titulo || "Painel Pessoal";
  const opcoes = {
    body: dados.corpo || "",
    icon: "/static/icons/icon-192.png",
    badge: "/static/icons/icon-192.png",
    timestamp: Date.now(),
    data: {
      url: typeof dados.url === "string" && dados.url.startsWith("/") ? dados.url : "/",
      tag: dados.tag ? String(dados.tag) : "",
    },
  };
  // numero no icone do app (badge.py): vem junto de cada aviso; sem push silencioso no iOS, e assim que o icone
  // acompanha o dia com o app fechado
  const numero = typeof dados.badge === "number" && dados.badge >= 0 ? Math.floor(dados.badge) : null;
  const pintarBadge = numero === null ? Promise.resolve() : _pintarBadge(numero);
  // mesmo aviso de novo (mesma tag) substitui o anterior em vez de empilhar - e ainda toca
  if (dados.tag) {
    opcoes.tag = String(dados.tag);
    opcoes.renotify = true;
  }
  // leva 22/10: "Feito" / "Adiar 1 h" no proprio aviso (o iPhone pode nao mostrar - ver /api/push/acao)
  if (Array.isArray(dados.acoes) && dados.acoes.length) {
    opcoes.actions = dados.acoes
      .slice(0, 2)
      .filter((a) => a && typeof a.action === "string" && typeof a.title === "string")
      .map((a) => ({ action: a.action, title: a.title }));
  }
  event.waitUntil(Promise.all([self.registration.showNotification(titulo, opcoes), pintarBadge]));
});

function _pintarBadge(n) {
  try {
    if (n > 0 && self.navigator && typeof self.navigator.setAppBadge === "function") return self.navigator.setAppBadge(n).catch(() => {});
    if (n === 0 && self.navigator && typeof self.navigator.clearAppBadge === "function") return self.navigator.clearAppBadge().catch(() => {});
  } catch (e) {
    // sem a API: segue sem numero
  }
  return Promise.resolve();
}

// Toque no aviso: abre na aba certa. App ja aberto -> traz pra frente e troca de aba
// (postMessage, sem recarregar); fechado -> abre direto no ?aba=.
function _postarJson(url, corpo) {
  return fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
  });
}

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/";
  const tag = (event.notification.data && event.notification.data.tag) || "";
  // botao do proprio aviso (leva 22/10): resolve sem abrir o app; deu errado -> abre a tarefa
  if (tag && (event.action === "feito" || event.action === "adiar")) {
    event.waitUntil(
      _postarJson("/api/push/acao", { tag, acao: event.action })
        .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
        .then((r) => {
          if (r.teste) return null;
          if (typeof r.badge === "number") _pintarBadge(Math.floor(r.badge)); // concluiu: o numero do icone desce
          const titulo = r.titulo ? String(r.titulo).slice(0, 80) : "Tarefa";
          const corpo = r.mensagem
            ? String(r.mensagem).slice(0, 120)
            : event.action === "feito" ? "Marquei como feita." : r.hora ? `Passei pras ${r.hora}.` : "Passei pra amanhã.";
          return self.registration.showNotification(titulo, {
            body: corpo,
            icon: "/static/icons/icon-192.png",
            badge: "/static/icons/icon-192.png",
            tag: `${tag}-ok`,
            silent: true,
            data: { url: "/?aba=tarefas", tag: "" },
          });
        })
        .catch(() => clients.openWindow(url))
    );
    return;
  }
  if (tag === "teste-0") _postarJson("/api/push/acao", { tag, acao: "toque" }).catch(() => {});
  // aviso importante insiste ate ser tocado (notificacoes.INSISTENCIA): avisa que viu
  const viu = tag
    ? fetch("/api/push/aberto", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tag }),
      }).catch(() => {})
    : Promise.resolve();
  event.waitUntil(
    Promise.all([viu, clients.matchAll({ type: "window", includeUncontrolled: true })]).then(([, janelas]) => {
      const aberta = janelas.find((j) => new URL(j.url).origin === self.location.origin);
      if (aberta) {
        aberta.postMessage({ tipo: "abrir-aviso", url });
        return aberta.focus();
      }
      return clients.openWindow(url);
    })
  );
});
