// Painel puxando assunto (2026-10-13, conversa_proativa.py): cards das mensagens que a IA
// abre sozinha no chat - "fechar o dia" (21h) e "padroes da semana" (domingo). Renderizador
// puro com estado final; entrada animada so por CSS no .card-novo (historico abre parado).
(function (raiz) {
  "use strict";
  const Cards = raiz.Cards || (typeof require === "function" ? require("./cards.js") : null);
  if (!Cards) return;
  const { esc, numeroValido } = Cards;
  const lista = (v) => (Array.isArray(v) ? v : []);
  const DIAS = ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"];
  const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  const ICONE_LUA =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z"/></svg>';
  const ICONE_SEMANA =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 20V11M10 20V5M15 20v-7M20 20V8"/></svg>';
  const ICONE_AMANHA =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h13M13 6l6 6-6 6"/></svg>';
  const ICONE_FEITO =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>';

  const diaMes = (iso) => {
    const d = Cards.parseDia(iso);
    return d ? `${d.getDate()} ${MESES[d.getMonth()]}` : "";
  };
  const nomeDia = (iso) => {
    const d = Cards.parseDia(iso);
    return d ? DIAS[d.getDay()] : "";
  };
  const reais = (v) => `R$ ${Math.round(Number(v) || 0).toLocaleString("pt-BR")}`;
  const horas = (h) => `${String(Math.round((Number(h) || 0) * 10) / 10).replace(".", ",")} h`;

  // ================================================================== fechar_dia
  function anel(feitas, total) {
    const frac = total > 0 ? feitas / total : 1;
    const C = 2 * Math.PI * 26;
    return (
      `<div class="rt-anel" style="--frac:${frac.toFixed(3)}"><svg viewBox="0 0 64 64" aria-hidden="true">` +
      `<circle cx="32" cy="32" r="26" class="rt-anel-fundo"/>` +
      `<circle cx="32" cy="32" r="26" class="rt-anel-valor" stroke-dasharray="${C.toFixed(1)}" stroke-dashoffset="${(C * (1 - frac)).toFixed(1)}"/></svg>` +
      `<div class="rt-anel-meio"><b class="vivo-num">${esc(feitas)}</b><small>de ${esc(total)}</small></div></div>`
    );
  }

  Cards.registrar("fechar_dia", (data) => {
    const pend = lista(data.pendentes).filter((p) => p && numeroValido(p.id));
    const feitas = Number(data.feitas) || 0;
    const nPend = lista(data.ids_adiar).length || pend.length;
    const total = feitas + nPend;
    const chips = [];
    if (!data.oculto && data.agua && numeroValido(data.agua.copos)) {
      const ok = data.agua.copos >= data.agua.meta;
      chips.push(`<span class="rt-chip${ok ? " ok" : ""}"><small>água</small><b class="vivo-num">${esc(data.agua.copos)}/${esc(data.agua.meta)}</b></span>`);
    }
    if (Number(data.voo_horas) > 0) chips.push(`<span class="rt-chip"><small>voo</small><b class="vivo-num">${esc(horas(data.voo_horas))}</b></span>`);
    if (data.quiz && data.quiz.respondidas) chips.push(`<span class="rt-chip"><small>quiz</small><b class="vivo-num">${esc(data.quiz.acertos)}/${esc(data.quiz.respondidas)}</b></span>`);
    if (!data.oculto && Number(data.gasto) > 0) chips.push(`<span class="rt-chip"><small>gasto</small><b class="vivo-num">${esc(reais(data.gasto))}</b></span>`);

    const itens = pend
      .map(
        (p, i) =>
          `<li class="rt-pend${p.atrasada ? " atrasada" : ""}" style="--i:${i}"><label class="rt-pend-linha">` +
          `<input type="checkbox" data-tarefa-id="${esc(p.id)}" aria-label="concluir ${esc(p.titulo)}">` +
          `<span class="rt-pend-titulo">${esc(p.titulo)}</span>` +
          `<span class="rt-pend-quando vivo-num">${p.atrasada ? `desde ${esc(diaMes(p.data))}` : p.hora ? esc(p.hora) : ""}</span></label></li>`
      )
      .join("");
    const botao = nPend
      ? `<button type="button" class="rt-adiar" data-acao="adiar_pendentes" data-ids="${esc(lista(data.ids_adiar).join(","))}">` +
        `<span class="rt-adiar-txt">Passar ${nPend === 1 ? "essa" : `as ${nPend}`} pra amanhã</span>${ICONE_AMANHA}</button>`
      : "";
    return (
      `<div class="rt-fechar${nPend ? "" : " limpo"}">` +
      `<div class="card-resultado-eyebrow">${ICONE_LUA}<span>Fechando o dia · ${esc(nomeDia(data.dia))}</span></div>` +
      `<div class="rt-fechar-topo">${anel(feitas, total)}<div class="rt-fechar-info">` +
      `<p class="rt-fechar-frase">${nPend ? `${nPend} ${nPend === 1 ? "ficou" : "ficaram"} pendurada${nPend === 1 ? "" : "s"}` : "Nada pendurado hoje"}</p>` +
      (chips.length ? `<div class="rt-chips">${chips.join("")}</div>` : "") +
      `</div></div>` +
      (itens ? `<ul class="rt-pends">${itens}</ul>` : "") +
      (data.mais ? `<p class="vivo-sub">e mais ${esc(data.mais)}</p>` : "") +
      botao +
      `</div>`
    );
  });

  if (typeof Cards.registrarAcao === "function") {
    Cards.registrarAcao("adiar_pendentes", async (btn, cardEl, deps) => {
      if (btn.disabled || typeof deps.apiFetch !== "function") return;
      const raizCard = btn.closest(".rt-fechar");
      // o que ele riscou no proprio card enquanto isso nao vai pra amanha
      const riscados = new Set(
        Array.from(raizCard.querySelectorAll("input[data-tarefa-id]:checked")).map((c) => Number(c.dataset.tarefaId))
      );
      const ids = String(btn.dataset.ids || "")
        .split(",")
        .map(Number)
        .filter((n) => n > 0 && !riscados.has(n));
      if (!ids.length) return;
      btn.disabled = true;
      btn.classList.add("enviando");
      const res = await deps.apiFetch("/api/tarefas/adiar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids }),
      });
      btn.classList.remove("enviando");
      if (!res) {
        btn.disabled = false;
        return;
      }
      raizCard.querySelectorAll(".rt-pend").forEach((li) => {
        const c = li.querySelector("input[data-tarefa-id]");
        if (c && !c.checked) {
          li.classList.add("adiada");
          c.disabled = true;
        }
      });
      btn.classList.add("feito");
      btn.innerHTML = `${ICONE_FEITO}<span class="rt-adiar-txt">${res.movidas === 1 ? "Passei pra amanhã" : `Passei ${esc(res.movidas)} pra amanhã`}</span>`;
      if (typeof raiz.vibrar === "function") raiz.vibrar(12);
      if (typeof deps.aoMudar === "function") deps.aoMudar();
    });
  }

  // ======================================================================= semana
  Cards.registrar("semana", (data) => {
    const dias = lista(data.dias).filter((d) => d && d.dia);
    if (dias.length !== 7) return null;
    const max = Math.max(1, ...dias.map((d) => Number(d.tarefas) || 0));
    const agua = lista(data.agua_dia);
    const meta = Number(data.meta_agua) || 8;
    const colunas = dias
      .map((d, i) => {
        const n = Number(d.tarefas) || 0;
        const melhor = d.dia === data.melhor_dia;
        const a = numeroValido(agua[i]) ? Math.min(1, agua[i] / meta) : null;
        return (
          `<li class="rt-col${melhor ? " melhor" : ""}" style="--i:${i};--h:${(n / max).toFixed(3)}">` +
          `<span class="rt-col-n vivo-num">${n || ""}</span>` +
          `<span class="rt-col-trilho"><i></i></span>` +
          // altura fixa: coluna com ou sem marca fica com a barra na mesma linha de base
          `<span class="rt-col-marcas">` +
          (a !== null ? `<span class="rt-col-agua${a >= 1 ? " cheia" : ""}" style="--a:${a.toFixed(2)}" title="${esc(agua[i])} de ${meta} copos"></span>` : "") +
          (Number(d.voo_h) > 0 ? `<span class="rt-col-voo" title="${esc(horas(d.voo_h))} de voo"></span>` : "") +
          `</span>` +
          `<small>${esc(d.rotulo)}</small></li>`
        );
      })
      .join("");
    const delta = (atual, ant) => {
      if (!ant) return "";
      const pct = Math.round(((atual - ant) / ant) * 100);
      if (!pct) return `<em class="rt-delta">igual</em>`;
      return `<em class="rt-delta ${pct > 0 ? "sobe" : "desce"}">${pct > 0 ? "▲" : "▼"} ${Math.abs(pct)}%</em>`;
    };
    const tiles = [
      `<div class="rt-tile"><small>tarefas</small><b class="vivo-num">${esc(data.tarefas || 0)}</b>${delta(Number(data.tarefas) || 0, Number(data.tarefas_ant) || 0)}</div>`,
    ];
    if (!data.oculto && numeroValido(data.gasto)) {
      tiles.push(`<div class="rt-tile"><small>gastos</small><b class="vivo-num">${esc(reais(data.gasto))}</b>${delta(data.gasto, data.gasto_ant)}</div>`);
    }
    if (Number(data.voo_horas) > 0) tiles.push(`<div class="rt-tile"><small>voo</small><b class="vivo-num">${esc(horas(data.voo_horas))}</b></div>`);
    const obs = lista(data.observacoes).map((o, i) => `<li style="--i:${i}">${esc(o)}</li>`).join("");
    return (
      `<div class="rt-semana">` +
      `<div class="card-resultado-eyebrow">${ICONE_SEMANA}<span>Tua semana · ${esc(diaMes(data.de))} a ${esc(diaMes(data.ate))}</span></div>` +
      `<ol class="rt-cols" aria-label="tarefas feitas por dia">${colunas}</ol>` +
      `<p class="rt-legenda"><span><i class="rt-leg-agua"></i>água na meta</span><span><i class="rt-leg-voo"></i>dia com voo</span></p>` +
      `<div class="rt-tiles">${tiles.join("")}</div>` +
      (obs ? `<ul class="rt-obs">${obs}</ul>` : "") +
      (data.sugestao ? `<p class="rt-sugestao"><small>Pra semana que vem</small>${esc(data.sugestao)}</p>` : "") +
      `</div>`
    );
  });

  const CardsRotina = {};
  raiz.CardsRotina = CardsRotina;
  if (typeof module !== "undefined" && module.exports) module.exports = CardsRotina;
})(typeof window !== "undefined" ? window : globalThis);
