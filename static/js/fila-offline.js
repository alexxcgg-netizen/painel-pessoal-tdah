// Fila offline (BRIEFING Fase 4, item 2: resiliencia offline) --------------
//
// Por que a fila vive AQUI (JS da pagina + IndexedDB) e nao no Service
// Worker: o app roda principalmente no iPhone do Alex, e o Safari no iOS
// nunca implementou a Background Sync API (decisao de plataforma da Apple,
// nao falta de suporte - o mesmo motivo por tras do feature-detect em
// `vibrar()` no app.js). Um SW que dependesse de Background Sync simplesmente
// nunca sincronizaria sozinho num iPhone. IndexedDB, em compensacao, e
// suportado igual nos dois lados (pagina e SW) - entao a escolha nao e sobre
// "o que funciona", e sim sobre onde fica mais simples: aqui a fila tem
// acesso direto as funcoes de recarregar tela (loadSummary, loadCheckin...)
// sem precisar de postMessage entre SW e pagina pra avisar "sincronizei,
// atualiza a tela". Reforco automatico (evento "online" + poll periodico)
// cobre o caso comum do iOS de o evento "online" nao disparar de forma
// confiavel em toda situacao - com a pagina aberta (que e a unica hora em
// que uma captura pode ter sido digitada), isso e suficiente.
//
// So as 2-3 acoes criticas pedidas no BRIEFING passam por aqui (captura por
// texto livre e check-in de energia/sono/humor) - GET nunca entra na fila
// (dado velho nao ajuda em nada), e uma resposta 4xx/5xx REAL do servidor
// (dado invalido etc) tambem nunca entra: so falha de rede/timeout enfileira.
//
// Estrutura dupla de export de proposito: em navegador isso vira o global
// `FilaOffline` (script classico, sem <script type=module>, igual o resto do
// projeto); em Node (rodado por `node --test` nos testes da fila, sem
// IndexedDB disponivel) so as funcoes PURAS (sem IO) ficam acessiveis via
// module.exports - sao elas que dao pra testar isolado sem navegador de
// verdade.
const FilaOffline = (function () {
  const DB_NOME = "painel-fila-offline";
  const DB_VERSAO = 1;
  const LOJA = "pendentes";

  // ---- logica pura (sem IndexedDB/DOM/fetch - testavel isolado) ----------

  function _gerarId() {
    if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
    // fallback bem improvavel de precisar (todo navegador/Node moderno tem
    // crypto.randomUUID), mas nao deixa a fila quebrar por isso.
    return `fila-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }

  function criarItem({ url, method, headers, body, tipo, id }) {
    return {
      id: id || _gerarId(),
      url,
      method: method || "POST",
      headers: headers || {},
      body: body || null,
      tipo: tipo || "generico",
      criadoEm: new Date().toISOString(),
    };
  }

  // FIFO por horario de criacao - defensivo (o IndexedDB ja devolve na ordem
  // da chave, mas isso garante a ordem mesmo se a fonte mudar um dia).
  function ordenarFifo(itens) {
    return [...itens].sort((a, b) => (a.criadoEm < b.criadoEm ? -1 : a.criadoEm > b.criadoEm ? 1 : 0));
  }

  // 4xx/5xx == resposta REAL que veio do servidor (dado invalido, etc) -
  // nunca e falha de rede, entao um item assim NAO pode ficar tentando pra
  // sempre (travaria o resto da fila atras dele).
  function ehErroDeServidor(status) {
    return typeof status === "number" && status >= 400;
  }

  // ---- IndexedDB (so existe em navegador de verdade) ---------------------

  function _abrirDB() {
    return new Promise((resolve, reject) => {
      if (typeof indexedDB === "undefined") {
        reject(new Error("IndexedDB indisponivel neste navegador"));
        return;
      }
      const req = indexedDB.open(DB_NOME, DB_VERSAO);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(LOJA)) {
          db.createObjectStore(LOJA, { keyPath: "id" });
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  async function enfileirar(dados) {
    const item = criarItem(dados);
    const db = await _abrirDB();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(LOJA, "readwrite");
      tx.objectStore(LOJA).put(item);
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
    db.close();
    return item;
  }

  async function listar() {
    const db = await _abrirDB();
    const itens = await new Promise((resolve, reject) => {
      const tx = db.transaction(LOJA, "readonly");
      const req = tx.objectStore(LOJA).getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    });
    db.close();
    return ordenarFifo(itens);
  }

  async function remover(id) {
    const db = await _abrirDB();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(LOJA, "readwrite");
      tx.objectStore(LOJA).delete(id);
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
    db.close();
  }

  async function contar() {
    try {
      const itens = await listar();
      return itens.length;
    } catch {
      return 0;
    }
  }

  // ---- sincronizacao -------------------------------------------------

  const callbacks = {};
  let sincronizando = false;

  // callback("capture"|"checkin"|...) roda depois que UM item desse tipo
  // sincronizou com sucesso, pra tela trocar o estado otimista pelo real.
  // callback("erro") roda quando um item foi descartado por erro real do
  // servidor (nao de rede).
  function registrarCallback(tipo, fn) {
    callbacks[tipo] = fn;
  }

  async function sincronizar(aoAtualizarContagem) {
    if (sincronizando) return; // evento "online" + timer podem coincidir - so uma passada por vez
    sincronizando = true;
    try {
      // eslint-disable-next-line no-constant-condition
      while (true) {
        let itens;
        try {
          itens = await listar();
        } catch {
          break; // IndexedDB indisponivel (modo privado etc) - nada a sincronizar
        }
        if (aoAtualizarContagem) aoAtualizarContagem(itens.length);
        if (itens.length === 0) break;

        const item = itens[0]; // FIFO - um de cada vez
        let res;
        try {
          res = await fetch(item.url, { method: item.method, headers: item.headers, body: item.body });
        } catch {
          // continua sem rede (ou timeout) - para por aqui SEM remover o
          // item, tenta de novo no proximo reforco (evento online / poll).
          break;
        }

        let corpo = null;
        try {
          corpo = await res.json();
        } catch {
          corpo = null; // resposta sem corpo - segue com null
        }

        if (ehErroDeServidor(res.status)) {
          await remover(item.id).catch(() => {});
          if (callbacks.erro) {
            try {
              callbacks.erro(item, corpo, res.status);
            } catch {
              // callback de UI nao pode travar o resto da fila
            }
          }
          continue;
        }

        await remover(item.id).catch(() => {});
        if (callbacks[item.tipo]) {
          try {
            await callbacks[item.tipo](corpo, item);
          } catch {
            // idem - erro na tela nao pode travar a sincronizacao dos proximos
          }
        }
      }
    } finally {
      sincronizando = false;
      if (aoAtualizarContagem) aoAtualizarContagem(await contar());
    }
  }

  function iniciarAutoSync(aoAtualizarContagem) {
    if (typeof window === "undefined") return;
    window.addEventListener("online", () => sincronizar(aoAtualizarContagem));
    // Reforco pro iOS: alem do evento "online" (que o Safari as vezes nao
    // dispara de forma confiavel em toda troca de rede), um poll leve a cada
    // 45s tenta sincronizar se houver algo pendente - so tem efeito de
    // verdade quando a fila tem itens (sincronizar() sai rapido se vazia).
    setInterval(() => sincronizar(aoAtualizarContagem), 45000);
  }

  return {
    criarItem,
    ordenarFifo,
    ehErroDeServidor,
    enfileirar,
    listar,
    remover,
    contar,
    registrarCallback,
    sincronizar,
    iniciarAutoSync,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  // Node (testes) - so a logica pura, sem IndexedDB/fetch/DOM.
  module.exports = {
    criarItem: FilaOffline.criarItem,
    ordenarFifo: FilaOffline.ordenarFifo,
    ehErroDeServidor: FilaOffline.ehErroDeServidor,
  };
}
