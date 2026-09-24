// Renderizadores dos types do contrato de cards (docs/CARDS.md). Cada um e
// uma funcao PURA (data, card, ctx) -> string HTML registrada no registro de
// static/js/cards.js. Todo texto vindo de `data` passa por esc(); moeda sempre
// por Cards.moeda (= fmtMoeda do app.js). Dado faltando nunca lanca excecao
// de proposito - no pior caso o registro troca pelo card fallback.
(function (raiz) {
  "use strict";
  const Cards = raiz.Cards || (typeof require === "function" ? require("./cards.js") : null);
  if (!Cards) return;

  const { esc, moeda, numeroValido, MOEDA_OCULTA } = Cards;

  // Mesmos tracos dos icones do card de resultado antigo (app.js) - stroke 1.8,
  // cantos arredondados - pra ficar parte do mesmo produto.
  const ICONES = {
    tarefa:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 12l2.5 2.5L16 9"/></svg>',
    gasto:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18"/><circle cx="16.5" cy="14" r="1"/></svg>',
    meta:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="0.8" fill="currentColor" stroke="none"/></svg>',
    lembrete:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="13" r="8"/><path d="M12 9v4l2.5 2.5M5 3 2 6M19 3l3 3"/></svg>',
    resumo:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.4L12 3z"/></svg>',
  };

  function eyebrow(icone, texto, extra) {
    return `<div class="card-resultado-eyebrow">${icone || ""}<span>${esc(texto)}</span>${extra || ""}</div>`;
  }

  function segundos(ms) {
    const bruto = Math.max(0, Math.round(Number(ms) || 0));
    if (bruto < 1000) return `${bruto} ms`;
    const s = bruto / 1000;
    if (s < 10) return `${s.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} s`;
    return `${Math.round(s)} s`;
  }

  function lista(v) {
    return Array.isArray(v) ? v : [];
  }

  // ---- tarefas_criadas ------------------------------------------------------

  function quandoTarefa(t) {
    const partes = [];
    if (t.recorrencia) partes.push("rotina");
    else if (t.data) partes.push(Cards.dataCurta(t.data));
    else if (t.quando) partes.push(String(t.quando));
    if (t.hora) partes.push(String(t.hora));
    return partes.length ? partes.join(" · ") : "sem data";
  }

  Cards.registrar("tarefas_criadas", (data) => {
    const tarefas = lista(data.tarefas).filter((t) => t && typeof t === "object");
    const titulo = tarefas.length === 1 ? "Tarefa criada" : "Tarefas criadas";
    const itens = tarefas
      .map((t) => {
        const id = t.id !== undefined && t.id !== null ? esc(t.id) : "";
        const marcada = t.concluida ? " checked" : "";
        return (
          `<li class="card-tarefa${t.concluida ? " concluida" : ""}">` +
          `<label><input type="checkbox"${id ? ` data-tarefa-id="${id}"` : " disabled"}${marcada} aria-label="Concluir ${esc(t.titulo)}">` +
          `<span class="card-tarefa-titulo">${esc(t.titulo)}</span></label>` +
          `<span class="card-tarefa-quando">${esc(quandoTarefa(t))}</span>` +
          `</li>`
        );
      })
      .join("");
    const contador = tarefas.length > 1 ? `<span class="card-contador">${tarefas.length}</span>` : "";
    return eyebrow(ICONES.tarefa, titulo, contador) + `<ul class="card-tarefas">${itens}</ul>`;
  });

  // ---- transacao ------------------------------------------------------------

  Cards.registrar("transacao", (data, card, ctx) => {
    const entrada = data.sentido === "entrada";
    const planejado = data.status === "planejado";
    const rotulo = entrada ? "Entrada registrada" : planejado ? "Gasto planejado" : "Gasto registrado";
    const oculto = Boolean(data.oculto) || !numeroValido(data.valor);
    const valorTxt = oculto ? MOEDA_OCULTA : `${entrada ? "+" : "-"}${moeda(data.valor)}`;
    const dia = data.data ? Cards.rotuloDia(data.data, ctx && ctx.agora) : "";
    const linha = [dia, data.meio, data.categoria].filter(Boolean).map((p) => esc(p)).join(" · ");
    const cat = entrada ? "entrada" : data.categoria || "outros";
    let saldo = "";
    const s = data.saldo;
    if (!data.oculto && s && typeof s === "object" && numeroValido(s.antes) && numeroValido(s.depois)) {
      saldo =
        `<p class="card-saldo"><span class="card-saldo-rotulo">Saldo${s.conta ? ` ${esc(s.conta)}` : ""}</span>` +
        `<span class="card-saldo-valores">${esc(moeda(s.antes))} <span class="card-seta" aria-hidden="true">→</span> <strong>${esc(moeda(s.depois))}</strong></span></p>`;
    }
    return (
      eyebrow(ICONES.gasto, rotulo, planejado ? '<span class="card-chip card-chip-planejado">planejado</span>' : "") +
      `<div class="card-transacao-topo"><span class="card-bolinha" data-cat="${esc(cat)}" aria-hidden="true"></span>` +
      `<p class="card-titulo">${esc(data.titulo)}</p></div>` +
      `<p class="card-valor-grande${entrada ? " entrada" : ""}${oculto ? " oculto" : ""}">${esc(valorTxt)}</p>` +
      (linha ? `<p class="card-linha-meta">${linha}</p>` : "") +
      saldo
    );
  });

  // ---- lembrete -------------------------------------------------------------

  // Alvo da contagem: data + hora do lembrete, ou 09:00 do dia (mesmo
  // horario do push "Desperta voce" - notificacoes.HORA_PADRAO_DESPERTAR).
  function alvoLembrete(data) {
    return Cards.parseDataHora(data.data, data.hora || "09:00");
  }

  Cards.registrar(
    "lembrete",
    (data, card, ctx) => {
      const agora = (ctx && ctx.agora) || new Date();
      const alvo = alvoLembrete(data);
      const destaque = data.hora ? String(data.hora) : Cards.diaMesCurto(data.data) || "—";
      const dia = data.data ? Cards.rotuloDia(data.data, agora) : "";
      const contagem = alvo
        ? `<span class="card-contagem-viva" data-contagem-alvo="${esc(alvo.toISOString())}">${esc(Cards.textoContagem(alvo, agora))}</span>`
        : "";
      const botoes = ["desfazer", "despertar"]
        .flatMap((tipo) => Cards.acoesDoTipo(card, tipo))
        .map(Cards.acaoHTML)
        .join("");
      return (
        eyebrow(ICONES.lembrete, "Lembrete criado", data.recorrente ? '<span class="card-chip">repete todo ano</span>' : "") +
        `<p class="card-titulo">${esc(data.titulo)}</p>` +
        `<p class="card-hora-grande">${esc(destaque)}</p>` +
        `<p class="card-linha-meta">${esc(dia)}${dia && contagem ? " · " : ""}${contagem}</p>` +
        (botoes ? `<div class="card-botoes">${botoes}</div>` : "")
      );
    },
    { consome: ["desfazer", "despertar"] }
  );

  // ---- meta -----------------------------------------------------------------

  function dataPlanejada(iso) {
    const d = Cards.parseDia(iso);
    if (!d) return "Sem data planejada";
    return `Data planejada: ${Cards.diaMesCurto(iso)} ${d.getFullYear()}`;
  }

  Cards.registrar("meta", (data) => {
    const oculto = Boolean(data.oculto) || !numeroValido(data.valor_alvo);
    const guardado = numeroValido(data.valor_guardado) ? data.valor_guardado : 0;
    let pct = numeroValido(data.percentual)
      ? data.percentual
      : !oculto && data.valor_alvo > 0
        ? (guardado / data.valor_alvo) * 100
        : 0;
    pct = Math.max(0, Math.min(100, pct));
    const valores = oculto
      ? `<strong>${MOEDA_OCULTA}</strong> de ${MOEDA_OCULTA}`
      : `<strong>${esc(moeda(guardado))}</strong> de ${esc(moeda(data.valor_alvo))}`;
    const falta = oculto
      ? MOEDA_OCULTA
      : moeda(numeroValido(data.falta) ? data.falta : Math.max(0, data.valor_alvo - guardado));
    return (
      eyebrow(ICONES.meta, data.consulta ? "Meta" : "Meta criada") +
      `<p class="card-titulo">${esc(data.titulo)}</p>` +
      `<p class="card-meta-valores">${valores}</p>` +
      `<div class="meta-progresso" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(pct)}">` +
      `<div class="meta-progresso-barra${pct >= 100 ? " completa" : ""}" style="width:${pct.toFixed(1)}%"></div></div>` +
      `<p class="card-linha-meta"><strong>${Math.round(pct)}%</strong> da meta · faltam ${esc(falta)}</p>` +
      `<p class="card-linha-meta">${esc(dataPlanejada(data.prazo))}</p>`
    );
  });

  // ---- resumo_final -----------------------------------------------------------

  Cards.registrar("resumo_final", (data, card, ctx) => {
    const linhas = lista(data.linhas)
      .filter((l) => l && typeof l === "object")
      .map(
        (l) =>
          `<li><span class="card-seta" aria-hidden="true">→</span><span><strong>${esc(l.modulo)}:</strong> ${esc(l.texto)}</span></li>`
      )
      .join("");
    const passos = lista(ctx && ctx.passos).filter((p) => p && typeof p === "object");
    const total = numeroValido(data.passos_total) ? data.passos_total : passos.length;
    const modulos = lista(data.modulos).map(String);
    const resumoPassos = [`${total} ${total === 1 ? "passo" : "passos"}`, segundos(data.duracao_ms), modulos.join(", ")]
      .filter(Boolean)
      .map(esc)
      .join(" · ");
    const itensPassos = passos
      .map(
        (p) =>
          `<li${p.erro ? ' class="erro"' : ""}><span class="card-passo-modulo">${esc(p.modulo)}</span>` +
          `<span class="card-passo-desc">${esc(p.descricao)}</span>` +
          `<span class="card-passo-ms">${esc(Number(p.ms) || 0)} ms</span></li>`
      )
      .join("");
    const detalhe = itensPassos
      ? `<details class="card-passos"><summary>${resumoPassos}</summary><ol>${itensPassos}</ol></details>`
      : `<p class="card-passos-resumo">${resumoPassos}</p>`;
    return eyebrow(ICONES.resumo, "Resumo") + `<ul class="card-resumo-linhas">${linhas}</ul>` + detalhe;
  });

  Cards.ICONES = ICONES;
  Cards.segundos = segundos;
})(typeof window !== "undefined" ? window : globalThis);

// ---- cards de visual complexo (US-E4) ---------------------------------------
// Renderizadores prontos contra o formato de docs/CARDS.md; o dado real de
// agenda (US-E14), projeto/viagem (US-E13), habito (US-E12) e o "porque" da
// sugestao (US-E10) e ligado por outras faixas (US-E7b).
(function (raiz) {
  "use strict";
  const Cards = raiz.Cards || (typeof require === "function" ? require("./cards.js") : null);
  if (!Cards) return;
  const { esc, numeroValido, moeda } = Cards;

  const ICONES = Object.assign(Cards.ICONES || {}, {
    assinatura:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 21v-5h5"/></svg>',
    parcela:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2.5" y="7.5" width="16" height="11" rx="2"/><rect x="5.5" y="4.5" width="16" height="11" rx="2"/><path d="M9 10h4"/></svg>',
    agenda:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 9.5h17M8 3v4M16 3v4"/></svg>',
    projeto:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 21V4M5 4h11l-2 4 2 4H5"/></svg>',
    viagem:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m14.8 9.2-1.6 4-4 1.6 1.6-4 4-1.6Z"/></svg>',
    treino:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12h4l3-7 4 14 3-7h4"/></svg>',
    sugestao:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg>',
    habito:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M17 2.5 20.5 6 17 9.5"/><path d="M3.5 11V9.5A3.5 3.5 0 0 1 7 6h13.5M7 21.5 3.5 18 7 14.5"/><path d="M20.5 13v1.5A3.5 3.5 0 0 1 17 18H3.5"/></svg>',
    check:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5 10 17 19 7"/></svg>',
    bandeira:
      '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" aria-hidden="true"><path d="M5 21V4" fill="none"/><path d="M5 4h11l-2 4 2 4H5z"/></svg>',
  });

  function eyebrow(icone, texto, extra) {
    return `<div class="card-resultado-eyebrow">${icone || ""}<span>${esc(texto)}</span>${extra || ""}</div>`;
  }

  function lista(v) {
    return Array.isArray(v) ? v : [];
  }

  function limitar(n, min, max) {
    return Math.max(min, Math.min(max, n));
  }

  // "08:00" -> "8h", "08:30" -> "8h30"
  function horaCurta(hhmmTxt) {
    const m = typeof hhmmTxt === "string" ? hhmmTxt.match(/^(\d{1,2}):(\d{2})/) : null;
    if (!m) return "";
    const h = Number(m[1]);
    return m[2] === "00" ? `${h}h` : `${h}h${m[2]}`;
  }

  // ---- agenda -----------------------------------------------------------------

  const DIA_INICIO_H = 6;
  const DIA_FIM_H = 22;

  // Posicao do bloco na barra do dia (06h-22h), em % - cortado nas bordas.
  function blocoDoDia(inicio, fim) {
    if (!(inicio instanceof Date)) return null;
    const fimReal = fim instanceof Date && fim > inicio ? fim : new Date(inicio.getTime() + 60 * 60000);
    const total = (DIA_FIM_H - DIA_INICIO_H) * 60;
    const minDoDia = (d, base) =>
      Cards.mesmoDia(d, base) ? d.getHours() * 60 + d.getMinutes() : d > base ? 24 * 60 : 0;
    const ini = limitar(minDoDia(inicio, inicio) - DIA_INICIO_H * 60, 0, total);
    const fi = limitar(minDoDia(fimReal, inicio) - DIA_INICIO_H * 60, 0, total);
    const left = (ini / total) * 100;
    const width = Math.max(1.5, ((fi - ini) / total) * 100);
    return { left: Math.min(left, 100 - width), width, minutos: Math.round((fimReal - inicio) / 60000) };
  }

  function barraDoDia(inicio, fim, rotulo) {
    const b = blocoDoDia(inicio, fim);
    if (!b) return "";
    const marcas = [6, 10, 14, 18, 22]
      .map((h) => {
        const pos = ((h - DIA_INICIO_H) / (DIA_FIM_H - DIA_INICIO_H)) * 100;
        return `<span class="card-dia-marca" style="left:${pos.toFixed(2)}%">${String(h).padStart(2, "0")}h</span>`;
      })
      .join("");
    return (
      `<div class="card-dia" role="img" aria-label="${esc(rotulo)}">` +
      `<div class="card-dia-trilho"><div class="card-dia-bloco" style="left:${b.left.toFixed(2)}%;width:${b.width.toFixed(2)}%"></div></div>` +
      `<div class="card-dia-escala">${marcas}</div></div>`
    );
  }

  Cards.registrar(
    "agenda",
    (data, card) => {
      const inicio = Cards.parseDataHora(data.inicio);
      const fimInformado = Cards.parseDataHora(data.fim);
      const fim = fimInformado && inicio && fimInformado > inicio ? fimInformado : inicio ? new Date(inicio.getTime() + 3600000) : null;
      const quando = inicio
        ? `${Cards.dataPorExtenso(inicio)}, das ${Cards.hhmm(inicio)} às ${Cards.hhmm(fim)}`
        : "Horário a definir";
      const minutos = inicio ? Math.round((fim - inicio) / 60000) : 0;
      const lembrar = numeroValido(data.lembrar_min_antes) && data.lembrar_min_antes > 0
        ? `<span class="card-chip">${ICONES.sugestao}Lembrar ${esc(data.lembrar_min_antes)} min antes</span>`
        : "";
      const desfazer = Cards.acoesDoTipo(card, "desfazer").map(Cards.acaoHTML).join("");
      const confirmacao = data.confirmado
        ? `<p class="card-confirmacao">${ICONES.check}<span>Está na sua agenda</span>${desfazer ? `<span class="card-sep" aria-hidden="true">·</span>${desfazer}` : ""}</p>`
        : desfazer
          ? `<div class="card-botoes">${desfazer}</div>`
          : "";
      return (
        eyebrow(ICONES.agenda, data.calendario ? `Agenda · ${data.calendario}` : "Agenda") +
        `<p class="card-titulo">${esc(data.titulo)}</p>` +
        `<p class="card-linha-meta card-primeira-maiuscula">${esc(quando)}</p>` +
        (inicio ? barraDoDia(inicio, fim, quando) : "") +
        (inicio ? `<div class="card-linha-chips"><span class="card-reservado">${esc(Cards.fmtDuracao(minutos))} reservadas</span>${lembrar}</div>` : "") +
        confirmacao
      );
    },
    { consome: ["desfazer"] }
  );

  // ---- projeto_viagem -----------------------------------------------------------

  // % concluido, n/total e posicao de HOJE (0..1) entre inicio e prazo. Usa
  // o que o backend mandar pronto (US-E13) e so calcula o que faltar.
  function progressoProjeto(data, agora) {
    const etapas = lista(data.etapas).filter((e) => e && typeof e === "object");
    const total = numeroValido(data.total) ? data.total : etapas.length;
    const feitas = numeroValido(data.feitas) ? data.feitas : etapas.filter((e) => e.feito).length;
    const pct = numeroValido(data.percentual) ? limitar(data.percentual, 0, 100) : total > 0 ? (feitas / total) * 100 : 0;
    let hoje = numeroValido(data.hoje_fracao) ? limitar(data.hoje_fracao, 0, 1) : null;
    if (hoje === null) {
      const ini = Cards.parseDia(data.inicio);
      const fim = Cards.parseDia(data.prazo);
      const ref = agora instanceof Date ? agora : new Date();
      if (ini && fim && fim > ini) hoje = limitar((ref - ini) / (fim - ini), 0, 1);
    }
    return { pct, feitas, total, hoje };
  }

  const STATUS_PROJETO = {
    no_rumo: "No rumo",
    atrasado: "Atrasado",
    pausado: "Pausado",
  };

  // ---- US-F11: linha do tempo de planejamento (regra pratica) -------------
  // Mini linha do tempo vertical, MESMA classe/marcacao visual da agenda/visao
  // do dia (.linha-do-tempo, style.css) - so acrescenta uma classe .mini pra
  // caber dentro do card sem competir com o card-checklist/progresso acima.
  // So aparece quando o backend mandar `marcos_planejamento` (so viagem tem -
  // projeto generico nunca tem esse campo, entao o bloco inteiro some).
  function linhaDoTempoPlanejamentoHTML(marcos, aviso, agora) {
    const lista = Array.isArray(marcos)
      ? marcos.filter((m) => m && typeof m === "object" && m.titulo && typeof m.data === "string")
      : [];
    if (!lista.length) return "";
    const ref = agora instanceof Date ? agora : new Date();
    const hojeIso = `${ref.getFullYear()}-${String(ref.getMonth() + 1).padStart(2, "0")}-${String(ref.getDate()).padStart(2, "0")}`;
    const ordenados = lista.slice().sort((a, b) => (a.data < b.data ? -1 : a.data > b.data ? 1 : 0));
    let hojeInserido = false;
    const itensHtml = [];
    ordenados.forEach((m) => {
      if (!hojeInserido && hojeIso <= m.data) {
        itensHtml.push(`<li class="item hoje-marcador" aria-current="date"><span class="item-titulo">HOJE</span></li>`);
        hojeInserido = true;
      }
      const passado = m.data < hojeIso;
      itensHtml.push(
        `<li class="item${passado ? " passado" : " proximo"}">` +
          `<span class="item-titulo">${esc(m.titulo)}</span>` +
          `<span class="card-linha-meta">${esc(Cards.diaMesCurto(m.data))}</span></li>`
      );
    });
    if (!hojeInserido) {
      itensHtml.push(`<li class="item hoje-marcador" aria-current="date"><span class="item-titulo">HOJE</span></li>`);
    }
    return (
      `<div class="card-marcos-planejamento">` +
      `<p class="card-linha-meta card-marcos-aviso">${ICONES.sugestao || ""}<span>${esc(aviso || "Regra prática, não é preço em tempo real.")}</span></p>` +
      `<ul class="linha-do-tempo mini">${itensHtml.join("")}</ul>` +
      `</div>`
    );
  }

  Cards.registrar("projeto_viagem", (data, card, ctx) => {
    const etapas = lista(data.etapas).filter((e) => e && typeof e === "object");
    const p = progressoProjeto(data, ctx && ctx.agora);
    const statusTxt = STATUS_PROJETO[data.status];
    const chip = statusTxt ? `<span class="card-chip card-status-${esc(data.status)}">${esc(statusTxt)}</span>` : "";
    const visiveis = etapas.slice(0, 5);
    const itens = visiveis
      .map(
        (e) =>
          `<li class="${e.feito ? "feito" : ""}"><span class="card-check" aria-hidden="true">${e.feito ? ICONES.check : ""}</span>` +
          `<span class="card-check-titulo">${esc(e.titulo)}</span>${e.data ? `<span class="card-check-data">${esc(Cards.diaMesCurto(e.data))}</span>` : ""}` +
          `<span class="sr-only">${e.feito ? "feito" : "pendente"}</span></li>`
      )
      .join("");
    const resto = etapas.length > visiveis.length ? `<li class="card-check-mais">+${etapas.length - visiveis.length} etapas</li>` : "";
    const marcador =
      p.hoje !== null
        ? `<span class="card-hoje${p.hoje < 0.08 ? " na-borda-inicio" : p.hoje > 0.92 ? " na-borda-fim" : ""}" style="left:${(p.hoje * 100).toFixed(2)}%"><span>HOJE</span></span>`
        : "";
    // sem nenhuma etapa (ex: viagem sem checklist de mala ainda) "0% · 0/0"
    // nao diz nada - mostra so que falta o checklist + o prazo
    const linha = [
      p.total > 0 ? `<strong>${Math.round(p.pct)}%</strong>` : "Sem checklist ainda",
      p.total > 0 ? `${esc(p.feitas)}/${esc(p.total)} ${p.total === 1 ? "tarefa" : "tarefas"}` : "",
      data.prazo ? esc(Cards.diaMesCurto(data.prazo)) : "",
    ]
      .filter(Boolean)
      .join(" · ");
    const marco = data.proximo_marco && typeof data.proximo_marco === "object" && data.proximo_marco.titulo
      ? `<p class="card-marco">${ICONES.bandeira}<span>Próximo marco: <strong>${esc(data.proximo_marco.titulo)}</strong>${data.proximo_marco.data ? ` · ${esc(Cards.diaMesCurto(data.proximo_marco.data))}` : ""}</span></p>`
      : "";
    return (
      eyebrow(data.origem === "viagem" ? ICONES.viagem : ICONES.projeto, data.origem === "viagem" ? "Viagem" : "Projeto", chip) +
      `<p class="card-titulo">${esc(data.titulo)}</p>` +
      (itens ? `<ul class="card-checklist">${itens}${resto}</ul>` : "") +
      `<div class="card-progresso${marcador ? " com-hoje" : ""}">${marcador}<div class="meta-progresso" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(p.pct)}">` +
      `<div class="meta-progresso-barra${p.pct >= 100 ? " completa" : ""}" style="width:${p.pct.toFixed(1)}%"></div></div></div>` +
      `<p class="card-linha-meta">${linha}</p>` +
      marco +
      linhaDoTempoPlanejamentoHTML(data.marcos_planejamento, data.aviso_regra_pratica, ctx && ctx.agora)
    );
  });

  // ---- saude_treino -------------------------------------------------------------

  function minutosPorAtividade(sessoes) {
    const mapa = new Map();
    sessoes.forEach((s) => {
      const nome = String(s.atividade || "Atividade");
      mapa.set(nome, (mapa.get(nome) || 0) + Math.max(0, Number(s.minutos) || 0));
    });
    return Array.from(mapa, ([atividade, minutos]) => ({ atividade, minutos })).sort((a, b) => b.minutos - a.minutos);
  }

  // Barras horizontais (rotulo a esquerda, valor direto na ponta - sem
  // legenda nem eixo), SVG inline, uma cor so (a do card).
  function graficoBarras(grupos) {
    if (!grupos.length) return "";
    const max = Math.max(...grupos.map((g) => g.minutos), 1);
    const alturaLinha = 26;
    const largura = 300;
    const xBarra = 92;
    const larguraMax = largura - xBarra - 52;
    const linhas = grupos
      .map((g, i) => {
        const y = i * alturaLinha;
        const w = Math.max(4, (g.minutos / max) * larguraMax);
        const nome = g.atividade.length > 13 ? `${g.atividade.slice(0, 12)}…` : g.atividade;
        return (
          `<text class="card-graf-rotulo" x="0" y="${y + 16}">${esc(nome)}</text>` +
          `<rect class="card-graf-barra" x="${xBarra}" y="${y + 6}" width="${w.toFixed(1)}" height="12" rx="6"/>` +
          `<text class="card-graf-valor" x="${(xBarra + w + 6).toFixed(1)}" y="${y + 16}">${esc(Cards.fmtDuracao(g.minutos))}</text>`
        );
      })
      .join("");
    const titulo = grupos.map((g) => `${g.atividade}: ${Cards.fmtDuracao(g.minutos)}`).join(", ");
    return `<svg class="card-grafico" viewBox="0 0 ${largura} ${grupos.length * alturaLinha}" role="img" aria-label="${esc(`Minutos por atividade - ${titulo}`)}">${linhas}</svg>`;
  }

  // Modo visitante (revisao da Fase 6): o servidor tira `sessoes` e manda
  // `oculto: true` - o card so diz que o dado esta escondido.
  const TEXTO_SAUDE_OCULTA = "Dados de saúde ocultos no modo visitante.";

  Cards.registrar("saude_treino", (data) => {
    if (data.oculto) {
      return eyebrow(ICONES.treino, "Treinos") + `<p class="card-linha-meta">${esc(TEXTO_SAUDE_OCULTA)}</p>`;
    }
    const sessoes = lista(data.sessoes).filter((s) => s && typeof s === "object");
    const totalMin = sessoes.reduce((acc, s) => acc + Math.max(0, Number(s.minutos) || 0), 0);
    const chip = data.registrado ? `<span class="card-chip">${ICONES.check}Registrado</span>` : "";
    const itens = sessoes
      .slice(0, 6)
      .map(
        (s) =>
          `<li><span class="card-sessao-nome">${esc(s.atividade || "Atividade")}</span>` +
          `<span class="card-sessao-fonte">${esc([s.fonte, s.data ? Cards.dataCurta(s.data) : ""].filter(Boolean).join(" · "))}</span>` +
          `<span class="card-sessao-dur">${esc(Cards.fmtDuracao(s.minutos))}</span></li>`
      )
      .join("");
    return (
      eyebrow(ICONES.treino, "Treinos", chip) +
      (data.periodo ? `<p class="card-titulo card-primeira-maiuscula">${esc(data.periodo)}</p>` : "") +
      `<p class="card-linha-meta">Sessões registradas: <strong>${sessoes.length}</strong> · Tempo de atividade: <strong>${esc(Cards.fmtDuracao(totalMin))}</strong></p>` +
      (itens ? `<ul class="card-sessoes">${itens}</ul>` : "") +
      graficoBarras(minutosPorAtividade(sessoes))
    );
  });

  // ---- sugestao -----------------------------------------------------------------

  Cards.registrar("sugestao", (data) => {
    const inicio = Cards.parseDataHora(data.inicio);
    const dur = numeroValido(data.duracao_min) && data.duracao_min > 0 ? data.duracao_min : null;
    const fim = inicio && dur ? new Date(inicio.getTime() + dur * 60000) : null;
    const linha = [
      inicio ? Cards.dataPorExtenso(inicio) : "",
      dur ? `${Cards.fmtDuracao(dur)}${fim ? ` (até ${Cards.hhmm(fim)})` : ""}` : "",
    ]
      .filter(Boolean)
      .map(esc)
      .join(" · ");
    const porque = data.porque
      ? `<div class="card-contexto"><p class="card-contexto-rotulo">Com a sua rotina em mente</p><p>${esc(data.porque)}</p></div>`
      : "";
    return (
      eyebrow(ICONES.sugestao, "Horário sugerido") +
      `<p class="card-titulo">${esc(data.titulo)}</p>` +
      `<p class="card-hora-grande">${esc(inicio ? Cards.hhmm(inicio) : "—")}</p>` +
      (linha ? `<p class="card-linha-meta card-primeira-maiuscula">${linha}</p>` : "") +
      porque
    );
  });

  // ---- habito -------------------------------------------------------------------

  const LETRAS_SEMANA = ["S", "T", "Q", "Q", "S", "S", "D"];
  const NOMES_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"];

  // Sempre 7 posicoes (segunda..domingo): completa com "nao feito" se o
  // backend mandar menos, e marca hoje por data.hoje (ou pelo relogio).
  function semanaHabito(data, agora) {
    const semana = lista(data.semana).slice(0, 7);
    const ref = agora instanceof Date ? agora : new Date();
    const hojeIso = typeof data.hoje === "string" ? data.hoje : null;
    const idxHojeRelogio = (ref.getDay() + 6) % 7;
    return LETRAS_SEMANA.map((letra, i) => {
      const dia = semana[i] && typeof semana[i] === "object" ? semana[i] : {};
      const ehHoje = hojeIso ? dia.data === hojeIso : i === idxHojeRelogio;
      return { letra, nome: NOMES_SEMANA[i], feito: Boolean(dia.feito), hoje: ehHoje, data: dia.data || null };
    });
  }

  Cards.registrar("habito", (data, card, ctx) => {
    const dias = semanaHabito(data, ctx && ctx.agora);
    const meta = [data.meta, data.frequencia, data.horario ? `às ${horaCurta(data.horario)}` : ""]
      .filter(Boolean)
      .map(esc)
      .join(" · ");
    const circulos = dias
      .map(
        (d) =>
          `<li class="card-habito-dia${d.feito ? " feito" : ""}${d.hoje ? " hoje" : ""}" aria-label="${esc(`${d.nome}${d.hoje ? " (hoje)" : ""}: ${d.feito ? "feito" : "não feito"}`)}">` +
          `<span class="card-habito-circ">${d.feito ? ICONES.check : ""}</span><span class="card-habito-letra" aria-hidden="true">${d.letra}</span></li>`
      )
      .join("");
    const ativos =
      numeroValido(data.ativos_depois)
        ? `<p class="card-linha-meta">Hábitos ativos: ${numeroValido(data.ativos_antes) ? `${esc(data.ativos_antes)} <span class="card-seta" aria-hidden="true">→</span> ` : ""}<strong>${esc(data.ativos_depois)}</strong></p>`
        : "";
    const contexto = data.contexto
      ? `<div class="card-contexto"><p>${esc(data.contexto)}</p></div>`
      : "";
    return (
      eyebrow(ICONES.habito, "Hábito") +
      `<p class="card-titulo">${esc(data.nome)}</p>` +
      (meta ? `<p class="card-linha-meta">${meta}</p>` : "") +
      `<ul class="card-habito-semana">${circulos}</ul>` +
      ativos +
      contexto
    );
  });

  // ---- saude_dia (US-E7, aditivo) -------------------------------------------
  // Copos de agua do dia em destaque + passos/sono/treino quando existirem.
  // Os copos viram uma fileira de gotas (ate 8 acesas; alem disso, "+N").

  const GOTA =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3.5c3.2 4 5.5 7.2 5.5 10.3a5.5 5.5 0 0 1-11 0C6.5 10.7 8.8 7.5 12 3.5Z"/></svg>';
  ICONES.agua = GOTA;

  const COPOS_VISIVEIS = 8;

  function fmtPassos(n) {
    if (!numeroValido(n) || n < 0) return "";
    if (n >= 1000) return `${(n / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mil passos`;
    return `${Math.round(n)} passos`;
  }

  function fmtSono(h) {
    if (!numeroValido(h) || h <= 0) return "";
    const total = Math.round(h * 60);
    const hh = Math.floor(total / 60);
    const mm = total % 60;
    return `Sono ${hh}h${mm ? String(mm).padStart(2, "0") : ""}`;
  }

  Cards.registrar("saude_dia", (data) => {
    if (data.oculto) {
      return eyebrow(ICONES.agua, "Saúde") + `<p class="card-linha-meta">${esc(TEXTO_SAUDE_OCULTA)}</p>`;
    }
    const copos = numeroValido(data.agua_copos) && data.agua_copos > 0 ? Math.floor(data.agua_copos) : 0;
    const chip = data.registrado ? `<span class="card-chip">${ICONES.check}Registrado</span>` : "";
    const gotas = Array.from({ length: COPOS_VISIVEIS }, (_, i) =>
      `<li class="card-gota${i < copos ? " cheia" : ""}${data.registrado === "agua" && i === copos - 1 ? " nova" : ""}">${GOTA}</li>`
    ).join("");
    const extra = copos > COPOS_VISIVEIS ? `<li class="card-gota-mais">+${copos - COPOS_VISIVEIS}</li>` : "";
    const chips = [
      fmtPassos(data.passos),
      fmtSono(data.sono_horas),
      numeroValido(data.treino_min) && data.treino_min > 0 ? `Treino ${Cards.fmtDuracao(data.treino_min)}` : "",
    ]
      .filter(Boolean)
      .map((t) => `<span class="card-chip card-chip-neutro">${esc(t)}</span>`)
      .join("");
    const dia = Cards.parseDia(data.data);
    const titulo = dia && !Cards.mesmoDia(dia, new Date()) ? `Saúde · ${Cards.dataCurta(data.data)}` : "Saúde hoje";
    return (
      eyebrow(ICONES.agua, titulo, chip) +
      `<div class="card-saude-agua"><span class="card-hora-grande">${esc(copos)}</span>` +
      `<span class="card-linha-meta">${copos === 1 ? "copo de água" : "copos de água"}</span></div>` +
      `<ul class="card-gotas" aria-label="${esc(`${copos} ${copos === 1 ? "copo" : "copos"} de água`)}">${gotas}${extra}</ul>` +
      (chips ? `<div class="card-linha-chips">${chips}</div>` : "")
    );
  });

  // ---- assinatura / compra_parcelada (Fase 7, faixa V1 - contrato N1) -----
  // Formato de `data` combinado com a faixa N1 (docs/contrato-assinaturas.md,
  // se ja estiver na integracao) - suposicao registrada em
  // scripts/ralph-v1-hoje/progress.txt enquanto a N1 nao entra. Diferente de
  // `transacao`/`meta`, esses dois NUNCA escondem valor (Alex pediu
  // explicitamente: "sao do proprio Alex", sem MOEDA_OCULTA/`data.oculto`).

  function emDiasTexto(n) {
    if (!numeroValido(n)) return "";
    if (n <= 0) return "hoje";
    if (n === 1) return "amanhã";
    return `em ${n} dias`;
  }

  Cards.registrar("assinatura", (data) => {
    const ativa = data.ativa !== false;
    const chip = ativa ? "" : '<span class="card-chip card-chip-neutro">Inativa</span>';
    const detalhe = [
      numeroValido(data.dia_cobranca) ? `dia ${data.dia_cobranca}` : "",
      data.cartao,
      data.categoria,
    ]
      .filter(Boolean)
      .map(esc)
      .join(" · ");
    const prox = data.proxima_cobranca ? Cards.diaMesCurto(data.proxima_cobranca) : "";
    const emDias = emDiasTexto(data.em_dias);
    const proxLinha = [prox ? `Próxima cobrança: ${prox}` : "", emDias].filter(Boolean).join(" · ");
    const valorTxt = numeroValido(data.valor) ? `${moeda(data.valor)} /mês` : "—";
    return (
      eyebrow(ICONES.assinatura, "Assinatura", chip) +
      `<p class="card-titulo">${esc(data.nome)}</p>` +
      `<p class="card-valor-grande">${esc(valorTxt)}</p>` +
      (detalhe ? `<p class="card-linha-meta">${detalhe}</p>` : "") +
      (proxLinha ? `<p class="card-linha-meta">${esc(proxLinha)}</p>` : "")
    );
  });

  Cards.registrar("compra_parcelada", (data) => {
    const atual = numeroValido(data.parcela_atual) ? data.parcela_atual : null;
    const total = numeroValido(data.n_parcelas) ? data.n_parcelas : null;
    const restantes = numeroValido(data.restantes)
      ? data.restantes
      : atual !== null && total !== null
        ? Math.max(0, total - atual)
        : null;
    const pct = atual !== null && total ? limitar((atual / total) * 100, 0, 100) : 0;
    const progresso =
      atual !== null && total
        ? `<div class="card-progresso"><div class="meta-progresso" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(pct)}">` +
          `<div class="meta-progresso-barra${pct >= 100 ? " completa" : ""}" style="width:${pct.toFixed(1)}%"></div></div></div>`
        : "";
    const detalhe = [
      atual !== null && total !== null ? `Parcela ${atual} de ${total}` : "",
      restantes !== null ? `${restantes} ${restantes === 1 ? "restante" : "restantes"}` : "",
      data.termina_em ? `termina ${Cards.diaMesCurto(data.termina_em)}` : "",
      data.cartao || "",
    ]
      .filter(Boolean)
      .map(esc)
      .join(" · ");
    const valorTxt = numeroValido(data.valor_parcela) ? `${moeda(data.valor_parcela)} /mês` : "—";
    return (
      eyebrow(ICONES.parcela, "Compra parcelada") +
      `<p class="card-titulo">${esc(data.descricao)}</p>` +
      `<p class="card-valor-grande">${esc(valorTxt)}</p>` +
      progresso +
      (detalhe ? `<p class="card-linha-meta">${detalhe}</p>` : "")
    );
  });

  // ---- resumo_financeiro_recorrente (agregado; formato NAO fechado com a
  // N1 ainda - suposicao registrada em scripts/ralph-v1-hoje/progress.txt) --

  Cards.registrar("resumo_financeiro_recorrente", (data) => {
    const totalTxt = numeroValido(data.total_mes) ? moeda(data.total_mes) : "—";
    const detalhe = [
      numeroValido(data.n_assinaturas)
        ? `${data.n_assinaturas} ${data.n_assinaturas === 1 ? "assinatura" : "assinaturas"}`
        : "",
      numeroValido(data.n_parcelas)
        ? `${data.n_parcelas} ${data.n_parcelas === 1 ? "parcela ativa" : "parcelas ativas"}`
        : "",
    ]
      .filter(Boolean)
      .map(esc)
      .join(" · ");
    const prox =
      data.proxima_cobranca && typeof data.proxima_cobranca === "object" && data.proxima_cobranca.nome
        ? `<p class="card-linha-meta">Próxima cobrança: <strong>${esc(data.proxima_cobranca.nome)}</strong>` +
          `${data.proxima_cobranca.data ? ` · ${esc(Cards.diaMesCurto(data.proxima_cobranca.data))}` : ""}</p>`
        : "";
    return (
      eyebrow(ICONES.resumo, "Recorrentes do mês") +
      `<p class="card-valor-grande">${esc(totalTxt)}</p>` +
      (detalhe ? `<p class="card-linha-meta">${detalhe}</p>` : "") +
      prox
    );
  });

  Object.assign(Cards, { blocoDoDia, progressoProjeto, minutosPorAtividade, semanaHabito, horaCurta, fmtPassos, fmtSono, emDiasTexto });
})(typeof window !== "undefined" ? window : globalThis);
