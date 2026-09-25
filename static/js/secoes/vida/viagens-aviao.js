// static/js/secoes/vida/viagens-aviao.js - Fase 9 (C5: faixa "Viagens"):
// aviaozinho animado na linha do tempo de planejamento da viagem (US-F11 ja
// existente em cards-tipos.js/vida.py, faixa desta versao NAO edita esses
// dois arquivos - so consome o que /api/viagens ja manda pronto por viagem:
// `data_ida`, `criado_em`, `marcos_planejamento`).
//
// So funcao PURA (calculo de posicao/rotulo + montagem do HTML do bloco) -
// nada de DOM aqui, pra dar pra testar em Node sem navegador
// (tests/js/viagens_aviao.test.js, node --test). Quem liga a animacao de
// verdade (classe .em-voo, IntersectionObserver) e static/js/secoes/vida/viagens.js.
//
// Escala da linha (0..1): 0% = data de criacao/planejamento da viagem
// (`criado_em`) quando valida, senao `data_ida` - 60 dias; 100% = `data_ida`
// (a viagem em si - nunca `data_volta`, o planejamento e sempre em funcao da
// ida). Regra pratica generica, mesma origem do card US-F11 - nunca preco em
// tempo real.
(function (raiz) {
  "use strict";

  function esc(valor) {
    if (valor === null || valor === undefined) return "";
    return String(valor)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function clamp(v, min, max) {
    return Math.max(min, Math.min(max, v));
  }

  // "AAAA-MM-DD" (ou "AAAA-MM-DD HH:MM:SS") -> Date local ao meio-dia, pra
  // nunca escorregar de dia por fuso (mesma receita de cards.js parseDia).
  function parseDiaLocal(iso) {
    if (typeof iso !== "string") return null;
    const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!m) return null;
    const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]), 12, 0, 0);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  // Diferenca em dias inteiros (b - a), por data de calendario (UTC-based),
  // igual cards.js diasEntre - nao usa diferenca bruta de ms (DST quebraria).
  function diasInteiros(a, b) {
    const ua = Date.UTC(a.getFullYear(), a.getMonth(), a.getDate());
    const ub = Date.UTC(b.getFullYear(), b.getMonth(), b.getDate());
    return Math.round((ub - ua) / 86400000);
  }

  // Janela [inicio, ida] usada pra escala 0..1 da linha inteira (marcos e
  // aviao usam a MESMA janela, senao os pontos nao alinham com a linha).
  function resolverJanela(dataIdaISO, inicioISO) {
    const ida = parseDiaLocal(dataIdaISO);
    if (!ida) return null;
    let inicio = parseDiaLocal(inicioISO);
    if (!inicio || inicio.getTime() >= ida.getTime()) {
      inicio = new Date(ida.getTime());
      inicio.setDate(inicio.getDate() - 60);
    }
    return { inicio, ida };
  }

  function fracaoNaJanela(dataISO, janela) {
    if (!janela) return null;
    const d = parseDiaLocal(dataISO);
    if (!d) return null;
    const total = diasInteiros(janela.inicio, janela.ida);
    if (total <= 0) return 1;
    return clamp(diasInteiros(janela.inicio, d) / total, 0, 1);
  }

  // Calculo puro de posicao/rotulo do aviaozinho - contrato testado em
  // tests/js/viagens_aviao.test.js:
  //   - antes do inicio da janela -> fracao 0
  //   - no meio -> fracao proporcional
  //   - no dia da viagem -> fracao 1, rotulo "viagem hoje"
  //   - depois da viagem -> fracao 1 (fica no fim da linha), rotulo "já passou"
  function calcularAviao(dataIdaISO, inicioISO, agora) {
    const janela = resolverJanela(dataIdaISO, inicioISO);
    if (!janela) return null;
    const ref = agora instanceof Date && !Number.isNaN(agora.getTime()) ? agora : new Date();
    const diasFaltam = diasInteiros(ref, janela.ida);
    let fracao;
    if (diasFaltam <= 0) {
      fracao = 1; // no dia ou depois: o aviao fica parado no fim da linha (embarque)
    } else {
      const total = diasInteiros(janela.inicio, janela.ida);
      fracao = total > 0 ? diasInteiros(janela.inicio, ref) / total : 1;
    }
    fracao = clamp(fracao, 0, 1);
    let rotulo;
    if (diasFaltam > 0) rotulo = `faltam ${diasFaltam} dia${diasFaltam === 1 ? "" : "s"}`;
    else if (diasFaltam === 0) rotulo = "viagem hoje";
    else rotulo = "já passou";
    return {
      fracao,
      percentual: Math.round(fracao * 1000) / 10,
      diasFaltam,
      rotulo,
      passou: diasFaltam < 0,
      janela,
    };
  }

  // Marcos da linha (US-F11: passagem/hospedagem/seguro, so o que a viagem
  // tiver - nacional nunca tem "seguro") + o embarque (data_ida, sempre no
  // fim da linha), na MESMA janela do aviao pra ficarem alinhados.
  const ROTULO_MARCO = { passagem: "passagem", hospedagem: "hotel", seguro: "seguro" };
  const ORDEM_MARCO = ["passagem", "hospedagem", "seguro"];

  function marcosParaTrilha(marcos, dataIdaISO, inicioISO) {
    const janela = resolverJanela(dataIdaISO, inicioISO);
    if (!janela) return [];
    const porChave = {};
    (Array.isArray(marcos) ? marcos : []).forEach((m) => {
      if (m && typeof m === "object" && typeof m.chave === "string" && typeof m.data === "string") {
        porChave[m.chave] = m;
      }
    });
    const pontos = [];
    ORDEM_MARCO.forEach((chave) => {
      const m = porChave[chave];
      if (!m) return;
      const fracao = fracaoNaJanela(m.data, janela);
      if (fracao === null) return;
      pontos.push({ chave, rotulo: ROTULO_MARCO[chave], data: m.data, fracao });
    });
    pontos.push({ chave: "embarque", rotulo: "embarque", data: dataIdaISO, fracao: 1 });
    return pontos;
  }

  // Quando uma viagem e criada perto da ida, os marcos (calculados so a
  // partir de data_ida, com antecedencias fixas de 30-120 dias - vida.py)
  // podem cair TODOS antes do inicio da janela (0%) e empilhar no mesmo
  // ponto. Em vez de deixar os rotulos sobrepostos (ilegivel), espalha em
  // "raias" verticais os que ficam a menos de 6% de distancia um do outro.
  function calcularRaias(pontos) {
    const raiaPorChave = new Map();
    const ordenados = pontos.slice().sort((a, b) => a.fracao - b.fracao);
    let raia = 0;
    let anterior = null;
    ordenados.forEach((p) => {
      raia = anterior !== null && p.fracao - anterior <= 0.06 ? raia + 1 : 0;
      anterior = p.fracao;
      raiaPorChave.set(p.chave, raia);
    });
    return raiaPorChave;
  }

  // Rotulo centrado no ponto (padrao) estoura a lateral do cartao quando o
  // ponto esta perto de 0% ou 100% (texto mais largo que o padding lateral
  // do trilho) - mesma ideia de "na-borda-inicio"/"na-borda-fim" que
  // cards-tipos.js ja usa pro marcador HOJE do card de cima (US-E13): perto
  // da borda, ancora o texto NA borda em vez de centralizar nela.
  function classeBorda(fracao) {
    if (fracao <= 0.08) return " viagem-aviao-borda-inicio";
    if (fracao >= 0.92) return " viagem-aviao-borda-fim";
    return "";
  }

  // HTML do cartao inteiro (traco simples, cor por CSS via --cor-acento -
  // static/css/secoes/vida/viagens-conversa.css). Devolve "" quando a viagem
  // nao tem data_ida valida (nunca quebra o card de cima, so nao acrescenta
  // o aviao).
  function renderAviaoHTML(viagem, agora) {
    if (!viagem || typeof viagem !== "object") return "";
    const calc = calcularAviao(viagem.data_ida, viagem.criado_em, agora);
    if (!calc) return "";
    const pontos = marcosParaTrilha(viagem.marcos_planejamento, viagem.data_ida, viagem.criado_em);
    const raias = calcularRaias(pontos);
    const marcosHtml = pontos
      .map((p) => {
        const titulo = p.data ? `${p.rotulo} · ${p.data}` : p.rotulo;
        const raia = raias.get(p.chave) || 0;
        const estiloRotulo = raia > 0 ? ` style="top:${14 + raia * 12}px"` : "";
        return (
          `<span class="viagem-aviao-marco viagem-aviao-marco-${esc(p.chave)}" style="left:${(p.fracao * 100).toFixed(2)}%" title="${esc(titulo)}">` +
          `<span class="viagem-aviao-marco-ponto" aria-hidden="true"></span>` +
          `<span class="viagem-aviao-marco-rotulo${classeBorda(p.fracao)}"${estiloRotulo}>${esc(p.rotulo)}</span>` +
          `</span>`
        );
      })
      .join("");
    const destino = viagem.destino ? ` para ${viagem.destino}` : "";
    return (
      `<div class="viagem-aviao-card" data-aviao-fracao="${calc.fracao.toFixed(4)}">` +
      `<div class="viagem-aviao-trilha" role="img" aria-label="${esc(calc.rotulo)}${esc(destino)}">` +
      `<span class="viagem-aviao-eixo">` +
      `<span class="viagem-aviao-linha" aria-hidden="true"></span>` +
      `<span class="viagem-aviao-marcos">${marcosHtml}</span>` +
      `<span class="viagem-aviao-aviao" style="--aviao-fracao:${calc.fracao.toFixed(4)}" aria-hidden="true">` +
      `<svg viewBox="0 0 24 24" class="viagem-aviao-svg" focusable="false"><path d="M21 3 3 10.5l7 2.5M21 3l-7.5 17-2.5-7M21 3 10.5 13.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>` +
      `<span class="viagem-aviao-legenda${classeBorda(calc.fracao)}">${esc(calc.rotulo)}</span>` +
      `</span>` +
      `</span>` +
      `</div>` +
      `</div>`
    );
  }

  const ViagemAviao = {
    esc,
    clamp,
    parseDiaLocal,
    diasInteiros,
    resolverJanela,
    fracaoNaJanela,
    calcularAviao,
    marcosParaTrilha,
    renderAviaoHTML,
  };

  raiz.ViagemAviao = ViagemAviao;
  if (typeof module !== "undefined" && module.exports) module.exports = ViagemAviao;
})(typeof window !== "undefined" ? window : this);
