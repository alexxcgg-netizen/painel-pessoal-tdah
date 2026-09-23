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
      eyebrow(ICONES.meta, "Meta criada") +
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
