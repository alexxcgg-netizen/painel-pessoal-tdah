// Comando de voz (Fase 5, Grupo B - US-B1 a US-B5) ---------------------------
//
// Fluxo: SpeechRecognition (Web Speech API, best-effort - ver AGENTS.md pra
// instabilidade conhecida em PWA standalone no iOS Safari, dispositivo
// principal do Alex) transcreve local -> texto vai pro classificador
// (POST /api/intent/classificar, contrato em docs/INTENT.md) -> a acao
// classificada e roteada pra um fluxo JA EXISTENTE do painel (captura,
// chat, navegacao de aba) - este arquivo NUNCA reimplementa essa logica,
// so decide pra onde mandar o texto (ver executarAcao).
//
// US-B2 (confirmacao antes de acao "destrutiva") e US-B3 (dialogo de
// correcao de 2 turnos) usam o MESMO estado de "comando pendente" abaixo -
// a diferenca e so o motivo de aparecer (confianca baixa = tambem oferece
// corrigir; confianca alta mas destrutiva = so confirmar/cancelar).
//
// US-B5 (fallback offline): reusa a fila da Fase 4 (FilaOffline, ver
// static/js/fila-offline.js) - o mesmo padrao ja usado por captura/check-in.
//
// Estrutura dupla de export igual fila-offline.js: em navegador vira o
// global `VozComando` (script classico); em Node (testes, sem
// window/document/SpeechRecognition) so a logica PURA fica acessivel via
// module.exports.
const VozComando = (function () {
  // ---- logica pura (sem DOM/fetch/SpeechRecognition - testavel isolado) --

  // Acoes que, mesmo com confianca alta (precisa_confirmacao=false vindo do
  // contrato), ainda exigem confirmacao explicita antes de executar (US-B2).
  // O contrato fechado (docs/INTENT.md / claude_client.ACOES_INTENT) ainda
  // nao tem nenhuma acao literalmente "destrutiva" (tipo deletar_tarefa) -
  // so pode GANHAR uma no futuro (regra do contrato: so aditivo). Ate la,
  // corrigir_ultimo e o mais proximo disso que existe (sobrescreve a
  // classificacao do ultimo item capturado) - mesma decisao documentada em
  // app.py (_classificar_intent/_texto_falado_intent, US-B4). Constante
  // pequena e isolada de proposito (1 API roundtrip so pra isso seria
  // exagero) - se crescer, atualizar os dois lugares (ver AGENTS.md).
  const ACOES_DESTRUTIVAS = new Set(["corrigir_ultimo"]);

  function exigeConfirmacao(resultado) {
    if (!resultado || typeof resultado !== "object") return true;
    return Boolean(resultado.precisa_confirmacao) || ACOES_DESTRUTIVAS.has(resultado.acao);
  }

  // Mapa tela -> sinonimos aceitos em parametros.tela (texto livre vindo da
  // IA - claude_client.INTENT_PROMPT nao fixa um enum pra esse campo).
  const MAPA_TELAS = {
    hoje: ["hoje", "inicio", "principal", "home"],
    painel: ["painel", "resumo do dia", "resumo"],
    vida: ["vida", "rotina", "check-in", "checkin", "hiperfoco"],
    tarefas: ["tarefa", "afazer", "pendencia"],
    gastos: ["gasto", "despesa", "financ", "meta", "banco", "extrato", "conta"],
    construtora: ["construtora", "obra", "empresa"],
    aviacao: ["aviacao", "voo", "piloto"],
  };

  function _normalizarTexto(t) {
    return String(t == null ? "" : t)
      .toLowerCase()
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .trim();
  }

  // Devolve a chave de ORDEM_ABAS (app.js) que melhor bate com o texto livre
  // de parametros.tela, ou null se nao reconhecer nenhuma (a UI mostra uma
  // mensagem de "nao entendi pra qual tela" nesse caso, em vez de navegar
  // errado por um palpite ruim).
  function resolverTela(textoTela) {
    if (!textoTela || typeof textoTela !== "string") return null;
    const normalizado = _normalizarTexto(textoTela);
    if (!normalizado) return null;
    for (const tab of Object.keys(MAPA_TELAS)) {
      if (MAPA_TELAS[tab].some((sinonimo) => normalizado.includes(sinonimo))) return tab;
    }
    return null;
  }

  // Rotulo curto pra UI (o que o painel entendeu do comando) - mesmo
  // espirito de app._texto_falado_intent (Python, US-B4), mas separado de
  // proposito: um formata pra fala do Siri, este pra texto na tela - 2
  // apresentacoes do MESMO resultado do classificador, nao 2 classificacoes.
  const ROTULO_ACAO = {
    registrar_tarefa: "registrar uma tarefa",
    registrar_gasto: "registrar um gasto",
    registrar_checkin: "abrir o check-in do dia",
    navegar_tela: "navegar pra uma tela",
    consultar: "responder uma pergunta",
    corrigir_ultimo: "corrigir o último item",
    desconhecido: "comando não entendido",
  };

  function descreverResultado(resultado) {
    if (!resultado || typeof resultado !== "object") return "Não consegui entender o comando.";
    if (resultado.teto_ia_estourado) {
      return "Limite mensal de IA atingido - não consegui interpretar esse comando agora.";
    }
    const rotulo = ROTULO_ACAO[resultado.acao] || ROTULO_ACAO.desconhecido;
    const parametros = resultado.parametros || {};
    let detalhe = "";
    if (resultado.acao === "navegar_tela" && parametros.tela) detalhe = ` (${parametros.tela})`;
    else if (parametros.titulo) detalhe = `: ${parametros.titulo}`;
    else if (parametros.pergunta) detalhe = `: ${parametros.pergunta}`;
    return `Entendi: ${rotulo}${detalhe}`;
  }

  // US-B3 (2o turno): quando a confianca veio baixa, a UI oferece essas
  // opcoes de correcao (nunca "desconhecido" - corrigir pra "nao entendi"
  // nao faz sentido). Escolher uma alimenta o padrao aprendido
  // (POST /api/intent/corrigir, US-A3/US-A4) com a acao certa pro mesmo
  // texto, sem duplicar essa logica aqui - so decide qual acao mandar.
  const ROTULO_CORRIGIR = {
    registrar_tarefa: "Era tarefa",
    registrar_gasto: "Era gasto",
    registrar_checkin: "Era check-in",
    navegar_tela: "Era navegacao",
    consultar: "Era pergunta",
    corrigir_ultimo: "Era correção do último item",
  };

  function opcoesDeCorrecao() {
    return Object.keys(ROTULO_CORRIGIR).map((acao) => ({ acao, rotulo: ROTULO_CORRIGIR[acao] }));
  }

  // ---- US-B6: classificador LOCAL (bag-of-words simples) -----------------
  //
  // Avaliacao de viabilidade (ver tasks/fase5/progress-grupo-b.txt pro
  // registro completo): Core ML/Neural Engine de verdade exige app nativo
  // (Swift + runtime Core ML) ou WebNN - suporte de navegador extremamente
  // limitado em 2026, nada confiavel numa PWA rodando principalmente no
  // Safari do iPhone do Alex. Fora do escopo/prazo de uma PWA.
  //
  // O que EXISTE abaixo, em vez disso, e a versao reduzida que o proprio
  // AC #3 da US-B6 permite: uma heuristica de palavras-chave (bag-of-words)
  // 100% local, SEM QUALQUER modelo de machine learning de verdade - nao e
  // Core ML, nao "aprende" nada novo sozinha, so casa palavras fixas.
  // Resolve APENAS o caso mais simples e inequivoco (navegar pra uma tela
  // conhecida, ex: "abre os gastos") sem precisar de rede nem custar
  // nenhuma chamada de IA - qualquer coisa fora desse padrao bem especifico
  // devolve null e o fluxo normal (rede, ou fila offline da US-B5 se a rede
  // cair) assume.
  const PALAVRAS_NAVEGACAO = ["abre", "abrir", "mostra", "mostrar", "navega", "ir pra", "ir para", "vai pra", "vai para"];

  function classificarLocalmente(texto) {
    const normalizado = _normalizarTexto(texto);
    if (!normalizado) return null;
    const pareceNavegacao = PALAVRAS_NAVEGACAO.some(
      (palavra) => normalizado === palavra || normalizado.startsWith(`${palavra} `) || normalizado.includes(` ${palavra} `)
    );
    if (!pareceNavegacao) return null;
    const tab = resolverTela(normalizado);
    if (!tab) return null;
    return {
      acao: "navegar_tela",
      confianca: 0.9,
      parametros: { tela: tab },
      precisa_confirmacao: false,
      classificado_localmente: true,
    };
  }

  return {
    ACOES_DESTRUTIVAS,
    exigeConfirmacao,
    resolverTela,
    descreverResultado,
    opcoesDeCorrecao,
    classificarLocalmente,
    _normalizarTexto,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  // Node (testes) - so a logica pura, sem DOM/fetch/SpeechRecognition.
  module.exports = {
    exigeConfirmacao: VozComando.exigeConfirmacao,
    resolverTela: VozComando.resolverTela,
    descreverResultado: VozComando.descreverResultado,
    opcoesDeCorrecao: VozComando.opcoesDeCorrecao,
    classificarLocalmente: VozComando.classificarLocalmente,
    ACOES_DESTRUTIVAS: VozComando.ACOES_DESTRUTIVAS,
  };
}

// ---- wiring de navegador (DOM/fetch/SpeechRecognition - so roda com pagina real) ----
if (typeof document !== "undefined" && typeof window !== "undefined") {
  (function () {
    const btn = document.getElementById("comando-voz-btn");
    const statusEl = document.getElementById("comando-voz-status");
    const confirmarBox = document.getElementById("comando-voz-confirmar");
    if (!btn || !statusEl || !confirmarBox) return; // pagina sem essa UI (ex: outra tela/teste) - nao quebra nada

    const confirmarTextoEl = document.getElementById("comando-voz-confirmar-texto");
    const confirmarOpcoesEl = document.getElementById("comando-voz-confirmar-opcoes");
    const confirmarSimBtn = document.getElementById("comando-voz-confirmar-sim");
    const confirmarNaoBtn = document.getElementById("comando-voz-confirmar-nao");

    let estadoPendente = null; // { texto, resultado } aguardando confirmar/corrigir (US-B2/US-B3)

    function mostrarStatus(msg) {
      statusEl.textContent = msg;
      statusEl.hidden = !msg;
    }

    function esconderConfirmacao() {
      estadoPendente = null;
      confirmarBox.hidden = true;
      if (confirmarOpcoesEl) confirmarOpcoesEl.innerHTML = "";
    }

    function mostrarConfirmacao(texto, resultado) {
      estadoPendente = { texto, resultado };
      confirmarTextoEl.textContent = `${VozComando.descreverResultado(resultado)} - confirma?`;
      if (confirmarOpcoesEl) {
        confirmarOpcoesEl.innerHTML = "";
        // So oferece "corrigir" quando a duvida e de VERDADE (confianca
        // baixa) - numa acao destrutiva de confianca alta nao ha ambiguidade
        // pra corrigir, so decidir se executa ou nao (US-B2).
        if (resultado.precisa_confirmacao) {
          VozComando.opcoesDeCorrecao().forEach(({ acao, rotulo }) => {
            const opcaoBtn = document.createElement("button");
            opcaoBtn.type = "button";
            opcaoBtn.className = "btn-link comando-voz-opcao";
            opcaoBtn.textContent = rotulo;
            opcaoBtn.addEventListener("click", () => corrigirPara(acao));
            confirmarOpcoesEl.appendChild(opcaoBtn);
          });
        }
      }
      confirmarBox.hidden = false;
    }

    async function reforcarPadrao(texto, acaoCorreta, parametros) {
      try {
        await window.apiFetch("/api/intent/corrigir", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ texto, acao_correta: acaoCorreta, parametros: parametros || {} }),
        });
      } catch {
        // reforco de padrao e so uma otimizacao (aprendizado) - uma falha
        // aqui nao pode travar o fluxo principal do comando de voz
      }
    }

    function executarAcao(texto, resultado) {
      const parametros = resultado.parametros || {};
      switch (resultado.acao) {
        case "navegar_tela": {
          const tab = VozComando.resolverTela(parametros.tela);
          if (tab && typeof window.showTab === "function") {
            window.showTab(tab);
            mostrarStatus(`Abri: ${tab}.`);
          } else {
            mostrarStatus('Nao identifiquei pra qual tela ir - tenta dizer o nome da aba (ex: "abre os gastos").');
          }
          break;
        }
        case "registrar_tarefa":
        case "registrar_gasto":
          // Reusa o MESMO pipeline de captura da caixa de texto (classify_capture,
          // fila offline, cards na tela) - o classificador de intent so decidiu
          // QUE ISSO e uma captura, quem sabe extrair titulo/valor/categoria de
          // verdade continua sendo /api/capture (nunca duplicado aqui).
          if (typeof window.enviarCaptura === "function") {
            window.enviarCaptura(texto, "");
            mostrarStatus("Enviei pra captura.");
          }
          break;
        case "registrar_checkin":
          // US-E7: "tomei um copo de agua" (parametros.campo = "hidratacao",
          // docs/INTENT.md) vai pro chat, que resolve no classificador local
          // e devolve o card de saude do dia - nada e duplicado aqui.
          if (parametros.campo === "hidratacao" && typeof window.enviarChat === "function") {
            window.enviarChat(texto);
            mostrarStatus("Registrei no chat.");
            break;
          }
          // O contrato de intent nao fixa um formato confiavel pra
          // campo/valor do check-in (energia/sono/humor) - em vez de
          // adivinhar errado, abre a tela onde o check-in de 1 toque ja
          // existe (static/js/vida.js) pro Alex confirmar com 1 toque.
          if (typeof window.showTab === "function") window.showTab("hoje");
          mostrarStatus("Abri o check-in do dia pra você preencher.");
          break;
        case "consultar":
        case "corrigir_ultimo":
          // Idem captura: o chat (tool-use) ja sabe responder pergunta sobre
          // dado existente e corrigir o último item - reusa em vez de duplicar.
          if (typeof window.enviarChat === "function") {
            window.enviarChat(texto);
            mostrarStatus("Perguntei pro assistente.");
          }
          break;
        default:
          mostrarStatus("Nao entendi esse comando. Tenta de novo.");
      }
    }

    function corrigirPara(acaoEscolhida) {
      if (!estadoPendente) return;
      const { texto } = estadoPendente;
      reforcarPadrao(texto, acaoEscolhida, {});
      esconderConfirmacao();
      const resultadoCorrigido = { acao: acaoEscolhida, confianca: 1, parametros: {}, precisa_confirmacao: false };
      mostrarStatus(VozComando.descreverResultado(resultadoCorrigido));
      executarAcao(texto, resultadoCorrigido);
    }

    function processarResultado(texto, resultado) {
      if (!resultado || typeof resultado !== "object") {
        mostrarStatus("Nao consegui entender o comando agora.");
        return;
      }
      if (resultado.teto_ia_estourado) {
        mostrarStatus(VozComando.descreverResultado(resultado));
        return;
      }
      if (VozComando.exigeConfirmacao(resultado)) {
        mostrarConfirmacao(texto, resultado);
        return;
      }
      mostrarStatus(VozComando.descreverResultado(resultado));
      executarAcao(texto, resultado);
    }

    async function enviarComando(texto) {
      // US-B6: caso mais simples (navegar pra uma tela conhecida) resolve
      // 100% local, sem rede nem custo de IA - so ai cai pro classificador
      // remoto (que, sem rede, cai pra fila offline da US-B5).
      const local = VozComando.classificarLocalmente(texto);
      if (local) {
        processarResultado(texto, local);
        return;
      }

      mostrarStatus("Entendendo...");
      // US-D2: estado "processando" com o MESMO padrao ja usado em todo
      // formulario do app (setBotaoCarregando, spinner via .spinner/girar) -
      // sem isso, o botao voltava pro visual parado assim que a escuta
      // terminava (recognition "end" ja tira a classe .ouvindo antes desta
      // chamada async resolver), sem nenhum feedback visual ENQUANTO
      // classifica, so o texto pequeno abaixo do botao.
      if (typeof window.setBotaoCarregando === "function") {
        window.setBotaoCarregando(btn, true, "Entendendo...");
      }
      const clientId = typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `voz-${Date.now()}`;
      try {
        const data = await window.apiFetch(
          "/api/intent/classificar",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ texto, client_id: clientId }),
          },
          { tipo: "comando_voz", id: clientId }
        );
        if (!data) return;
        if (data.__enfileirado) {
          // US-B5: sem rede - o texto ja transcrito fica na mesma fila da
          // Fase 4 e sincroniza sozinho quando a conexao voltar (callback
          // "comando_voz" abaixo processa o resultado real na hora).
          mostrarStatus("Sem conexao - comando salvo, vai ser entendido quando a conexao voltar.");
          return;
        }
        processarResultado(texto, data);
      } finally {
        if (typeof window.setBotaoCarregando === "function") {
          window.setBotaoCarregando(btn, false, "Comando de voz");
        }
      }
    }

    if (typeof FilaOffline !== "undefined") {
      FilaOffline.registrarCallback("comando_voz", (data, item) => {
        let texto = "";
        try {
          texto = JSON.parse(item.body).texto || "";
        } catch {
          texto = "";
        }
        processarResultado(texto, data);
      });
    }

    confirmarSimBtn.addEventListener("click", () => {
      if (!estadoPendente) return;
      const { texto, resultado } = estadoPendente;
      // O Alex confirmou que a classificacao estava certa - se ela tinha
      // vindo com baixa confianca, isso e sinal forte o bastante pra
      // alimentar o padrao aprendido direto (mesmo espirito da US-A4:
      // uma correcao/confirmacao manual vale mais que repetir 3x sozinha).
      if (resultado.precisa_confirmacao) {
        reforcarPadrao(texto, resultado.acao, resultado.parametros);
      }
      esconderConfirmacao();
      executarAcao(texto, resultado);
    });

    confirmarNaoBtn.addEventListener("click", () => {
      esconderConfirmacao();
      mostrarStatus("Cancelado.");
    });

    // ---- Web Speech API (US-B1) - best-effort, ver AGENTS.md pra instabilidade
    // conhecida em PWA standalone no iOS Safari (dispositivo principal do Alex) ----
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      mostrarStatus("Reconhecimento de voz não suportado neste navegador - use os Atalhos da Siri (ver README).");
      btn.disabled = true;
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "pt-BR";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    let ouvindo = false;

    const pararDeOuvir = () => {
      ouvindo = false;
      btn.classList.remove("ouvindo");
    };

    recognition.addEventListener("result", (e) => {
      const texto = e.results[0][0].transcript;
      enviarComando(texto);
    });
    recognition.addEventListener("end", pararDeOuvir);
    recognition.addEventListener("error", (e) => {
      pararDeOuvir();
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        mostrarStatus("Permissao de microfone negada.");
      } else if (e.error !== "aborted" && e.error !== "no-speech") {
        mostrarStatus("Nao consegui ouvir. Tenta de novo.");
      }
    });

    btn.addEventListener("click", () => {
      if (ouvindo) {
        recognition.stop();
        return;
      }
      ouvindo = true;
      btn.classList.add("ouvindo");
      mostrarStatus("Ouvindo...");
      try {
        recognition.start();
      } catch {
        pararDeOuvir();
      }
    });
  })();
}
