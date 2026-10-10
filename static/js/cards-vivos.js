// Cartoes vivos do chat (2026-10-09) - cada assunto tem um card que se monta na frente do
// Alex: aviao no diario de voo, caminho da rota se desenhando, ceu do clima, rosca de gastos,
// linha do tempo do dia, janelas de compra da viagem, copo de agua, edicao com antes/depois.
// Prototipo aprovado: https://claude.ai/artifact/A81nC3Yim5toSYRtJs34TU
//
// Duas fases, de proposito:
//  - o RENDERIZADOR (data -> HTML) e puro e ja devolve o ESTADO FINAL (numero certo, barra
//    cheia) - historico do chat, modo sem animacao e testes em Node veem tudo certo;
//  - CardsVivos.preparar(el) liga o que precisa do navegador (canvas do ceu, aviao no arco)
//    e CardsVivos.animar(el) toca a entrada so nas respostas NOVAS (chat.js chama).
// prefers-reduced-motion: nada anima, fica o estado final.
(function (raiz) {
  "use strict";
  const Cards = raiz.Cards || (typeof require === "function" ? require("./cards.js") : null);
  if (!Cards) return;
  const { esc, moeda, numeroValido } = Cards;

  const ICONES = {
    edicao:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16v4Z"/><path d="m13.5 6.5 4 4"/></svg>',
    voo:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z"/></svg>',
    clima:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M17.5 19H9a7 7 0 1 1 6.7-9h1.8a4.5 4.5 0 0 1 0 9Z"/></svg>',
    gasto:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18"/></svg>',
    dia:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg>',
    viagem:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 7h18v12H3z"/><path d="M8 7V5h8v2"/><path d="M3 12h18"/></svg>',
    agua:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11Z"/></svg>',
  };
  const AVIAO =
    '<path d="M-7 1.5 L-1.5 1.2 L2.8 6.5 L4.4 6.5 L2.4 1.1 L6.5 0.9 Q8.3 0 6.5 -0.9 L2.4 -1.1 L4.4 -6.5 L2.8 -6.5 L-1.5 -1.2 L-7 -1.5 L-8.4 -4 L-9.6 -4 L-8.8 0 L-9.6 4 L-8.4 4 Z" fill="currentColor"/>';
  const CORES_CAT = ["#e8cf8a", "#f0a58f", "#e39fc9", "#b79cf0", "#7cc4e8", "#9fdcb0", "#9aa8f0", "#7fd9d0"];

  function olho(icone, texto, extra) {
    return `<div class="card-resultado-eyebrow">${icone || ""}<span>${esc(texto)}</span>${extra || ""}</div>`;
  }
  const lista = (v) => (Array.isArray(v) ? v : []);
  const hhmmMin = (min) => {
    const n = Math.max(0, Math.round(Number(min) || 0));
    return `${Math.floor(n / 60)}:${String(n % 60).padStart(2, "0")}`;
  };
  const km = (v) =>
    numeroValido(v) ? Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : "—";
  const fmtHmin = (min) => {
    const n = Math.max(0, Math.round(Number(min) || 0));
    return n < 60 ? `${n} min` : `${Math.floor(n / 60)}h${String(n % 60).padStart(2, "0")}`;
  };
  const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  // "2026-11-08" -> "8 nov" (ou "8 nov 2027" se for de outro ano)
  const diaMes = (iso) => {
    const d = Cards.parseDia(iso);
    if (!d) return "";
    const ano = d.getFullYear() !== new Date().getFullYear() ? ` ${d.getFullYear()}` : "";
    return `${d.getDate()} ${MESES[d.getMonth()]}${ano}`;
  };
  const dataBr = (iso) => {
    const d = Cards.parseDia(iso);
    return d ? `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}/${d.getFullYear()}` : "";
  };
  // valores da rosca: sem centavos (cabe no miolo e na legenda); o detalhe fica na aba Finanças
  const moedaCurta = (v) => (numeroValido(v) ? `R$ ${Math.round(v).toLocaleString("pt-BR")}` : moeda(v));
  const nomeFuncao = (nome) => {
    const n = String(nome || "");
    if (/^co-?piloto/i.test(n)) return "Copiloto";
    return n.replace(/^Piloto em /, "").replace(/^Instrução Solo$/, "Instrução solo");
  };
  const isoHoje = () => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  };

  // ===================================================================== edicao
  Cards.registrar("edicao", (data) => {
    const itens = lista(data.itens).filter((i) => i && typeof i === "object");
    if (!itens.length) return null;
    const linhas = itens
      .map(
        (it) =>
          `<li class="vivo-edicao-item"><p class="vivo-edicao-titulo"><span class="card-chip">${esc(it.rotulo)}</span>${esc(it.titulo)}</p>` +
          lista(it.mudancas)
            .map(
              (m) =>
                `<p class="vivo-mudanca"><span class="vivo-mudanca-campo">${esc(m.campo)}</span>` +
                `<s class="vivo-de">${esc(m.de)}</s><span class="vivo-seta" aria-hidden="true">→</span>` +
                `<strong class="vivo-para">${esc(m.para)}</strong></p>`
            )
            .join("") +
          `</li>`
      )
      .join("");
    const contador = itens.length > 1 ? `<span class="card-contador">${itens.length}</span>` : "";
    return olho(ICONES.edicao, itens.length > 1 ? "Alterados" : "Alterado", contador) + `<ul class="vivo-edicao" data-vivo="edicao">${linhas}</ul>`;
  });

  // ================================================================ voo_resumo
  const ARCO = "M16 96 C 110 96, 150 30, 344 22";
  Cards.registrar("voo_resumo", (data) => {
    if (!numeroValido(data.total_min)) return null;
    const total = data.total_min;
    const metaDef = numeroValido(data.meta_horas) ? data.meta_horas : 150;
    const bateu = total >= metaDef * 60;
    // passou da meta: o arco cresce 10% alem do total pra o aviao nao ficar colado na ponta
    const metaH = bateu ? Math.ceil((total / 60) * 1.1 - 1e-9) : metaDef;
    const funcoes = lista(data.por_funcao).filter((f) => f && numeroValido(f.min));
    const maxF = Math.max(1, ...funcoes.map((f) => f.min));
    const barras = funcoes
      .map(
        (f) =>
          `<div class="vivo-barra-linha"><span title="${esc(f.nome)}">${esc(nomeFuncao(f.nome))}</span>` +
          `<span class="vivo-num">${hhmmMin(f.min)}</span><div class="vivo-trilho"><i style="width:${((f.min / maxF) * 100).toFixed(1)}%"></i></div></div>`
      )
      .join("");
    const anvs = lista(data.por_aeronave)
      .filter((a) => a && a.nome)
      .map((a) => `<span class="vivo-anv">${esc(String(a.nome).replace(/^([A-Z]{2})([A-Z]{3})$/, "$1-$2"))}<b>${hhmmMin(a.min)}</b></span>`)
      .join("");
    const u = data.ultimo || {};
    const semVoar = numeroValido(data.dias_sem_voar)
      ? data.dias_sem_voar === 0
        ? "voou hoje"
        : `${data.dias_sem_voar} ${data.dias_sem_voar === 1 ? "dia" : "dias"} sem voar`
      : "";
    const nota = [
      u.data ? `Último voo ${dataBr(u.data)}${u.aeronave ? ` no ${esc(String(u.aeronave).replace(/^([A-Z]{2})([A-Z]{3})$/, "$1-$2"))}` : ""}` : "",
      semVoar,
      data.simulador_min ? `simulador ${hhmmMin(data.simulador_min)} à parte` : "",
    ]
      .filter(Boolean)
      .join(" · ");
    const solo = data.primeiro_solo && numeroValido(data.primeiro_solo.minutos) ? data.primeiro_solo.minutos : null;
    return (
      olho(ICONES.voo, "Diário de voo") +
      `<div class="vivo-cabeca"><span class="vivo-num vivo-grande" data-contar-hhmm="${total}">${hhmmMin(total)}</span>` +
      `<span class="vivo-sub">horas de voo · ${esc(data.voos)} voos</span></div>` +
      `<svg class="vivo-arco" viewBox="0 0 360 120" role="img" aria-label="${esc(hhmmMin(total))} de ${metaH} horas" data-vivo="voo" ` +
      `data-total="${total}" data-meta="${metaH}"${solo !== null ? ` data-solo="${solo}"` : ""}>` +
      `<path class="vivo-arco-base" d="${ARCO}"/><path class="vivo-arco-rastro" d="${ARCO}"/>` +
      `<g class="vivo-marcos"></g><g class="vivo-aviao"><circle r="13" class="vivo-aviao-halo"/>${AVIAO}</g>` +
      `<text x="16" y="114">0 h</text><text x="344" y="12" text-anchor="end">${bateu ? `meta ${metaDef} h batida` : `meta ${metaH} h${data.meta_definida ? "" : "*"}`}</text></svg>` +
      (barras ? `<div class="vivo-barras">${barras}</div>` : "") +
      (anvs ? `<div class="vivo-anvs">${anvs}</div>` : "") +
      `<p class="vivo-nota">${nota}${data.meta_definida ? "" : `${nota ? " · " : ""}*meta de exemplo: diga “minha meta é 150 horas”`}</p>`
    );
  });

  // ===================================================================== clima
  function cenaClima(condicao) {
    const c = String(condicao || "").toLowerCase();
    if (c.includes("trovoada")) return "trovoada";
    if (c.includes("chuva") || c.includes("garoa") || c.includes("pancada")) return "chuva";
    if (c.includes("limpo")) return "limpo";
    if (c.includes("neblina")) return "neblina";
    return "nublado";
  }
  Cards.registrar("clima", (data) => {
    const a = data.agora && typeof data.agora === "object" ? data.agora : null;
    if (!a) return null;
    const horas = lista(data.proximas_horas).filter((h) => h && numeroValido(h.chuva_pct));
    const barras = horas
      .map(
        (h) =>
          `<div class="vivo-hora" title="${esc(h.chuva_pct)}% de chance de chuva"><i style="height:${Math.max(4, h.chuva_pct * 0.5).toFixed(0)}px"></i>` +
          `<small>${String(h.hora).padStart(2, "0")}h</small></div>`
      )
      .join("");
    const sensacao = numeroValido(a.sensacao) ? ` · sensação ${Math.round(a.sensacao)}°` : "";
    return (
      `<div class="vivo-ceu" data-vivo="clima" data-cena="${cenaClima(a.condicao)}" data-temp="${numeroValido(a.temperatura) ? Math.round(a.temperatura) : ""}">` +
      `<canvas aria-hidden="true"></canvas>` +
      olho(ICONES.clima, `Agora${data.lugar ? ` · ${data.lugar}` : ""}`) +
      `<div class="vivo-ceu-rodape"><div><span class="vivo-num vivo-grande" data-contar-graus="${numeroValido(a.temperatura) ? Math.round(a.temperatura) : ""}">` +
      `${numeroValido(a.temperatura) ? Math.round(a.temperatura) : "—"}°</span>` +
      `<p class="vivo-sub">${esc(a.condicao || "")}${sensacao}</p></div>` +
      `<p class="vivo-sub vivo-direita">umidade <b class="vivo-num">${numeroValido(a.umidade_pct) ? a.umidade_pct : "—"}%</b><br>` +
      `vento <b class="vivo-num">${numeroValido(a.vento_kmh) ? Math.round(a.vento_kmh) : "—"} km/h</b></p></div></div>` +
      (barras ? `<p class="vivo-sub vivo-rotulo-horas">Chance de chuva nas próximas horas</p><div class="vivo-horas">${barras}</div>` : "")
    );
  });

  // ============================================================ gastos_resumo
  const R_ROSCA = 15.9155;
  function arcosRosca(cats, total, fracao) {
    let acum = 0;
    return cats
      .map((c, i) => {
        const fatia = total > 0 ? (c.valor / total) * 100 : 0;
        const vis = Math.max(0, Math.min(fatia, fracao * 100 - acum) - (fatia > 1.2 ? 0.8 : 0));
        const html = `<circle cx="21" cy="21" r="${R_ROSCA}" fill="none" stroke="${CORES_CAT[i % CORES_CAT.length]}" stroke-width="5.5" stroke-dasharray="${vis.toFixed(2)} ${(100 - vis).toFixed(2)}" stroke-dashoffset="${(-acum).toFixed(2)}"/>`;
        acum += fatia;
        return html;
      })
      .join("");
  }
  Cards.registrar("gastos_resumo", (data) => {
    const p = data.periodo || {};
    const titulo = data.categoria_filtrada ? `Gastos · ${data.categoria_filtrada}` : "Gastos";
    const periodo = p.de && p.ate ? `${diaMes(p.de)} a ${diaMes(p.ate)}` : "";
    if (data.oculto) return olho(ICONES.gasto, titulo) + `<p class="card-linha-meta">Valores ocultos no modo visitante.</p>`;
    const cats = lista(data.por_categoria).filter((c) => c && numeroValido(c.valor) && c.valor > 0).slice(0, 6);
    const total = numeroValido(data.total) ? data.total : cats.reduce((s, c) => s + c.valor, 0);
    const legenda = cats
      .map(
        (c, i) =>
          `<div><i style="background:${CORES_CAT[i % CORES_CAT.length]}"></i><span>${esc(c.categoria)}</span><span class="vivo-num">${esc(moedaCurta(c.valor))}</span></div>`
      )
      .join("");
    return (
      olho(ICONES.gasto, titulo) +
      (periodo ? `<p class="vivo-sub">${esc(periodo)} · ${esc(data.quantidade || 0)} lançamentos</p>` : "") +
      `<div class="vivo-rosca-linha"><div class="vivo-rosca"><svg viewBox="0 0 42 42" aria-hidden="true" data-vivo="gastos" data-cats='${esc(JSON.stringify(cats.map((c) => c.valor)))}' data-total="${total}">` +
      `<circle cx="21" cy="21" r="${R_ROSCA}" fill="none" class="vivo-rosca-fundo" stroke-width="5.5"/>${arcosRosca(cats, total, 1)}</svg>` +
      `<div class="vivo-rosca-meio"><small>total</small><span class="vivo-num" data-contar-moeda="${total}">${esc(moedaCurta(total))}</span></div></div>` +
      `<div class="vivo-legenda">${legenda || '<p class="vivo-sub">Nenhum gasto no período.</p>'}</div></div>`
    );
  });

  // ======================================================================= dia
  Cards.registrar("dia", (data) => {
    const itens = lista(data.compromissos).filter((c) => c && c.titulo);
    const semHora = lista(data.tarefas_sem_hora).filter(Boolean);
    const ehHoje = data.dia === isoHoje();
    const titulo = ehHoje ? "Seu dia" : data.dia ? `Dia ${Cards.dataCurta(data.dia)}` : "Agenda";
    const linhas = itens
      .map((c) => {
        const h = c.dia_inteiro ? "dia todo" : c.hora || "—";
        const min = c.hora && /^\d{2}:\d{2}$/.test(c.hora) ? +c.hora.slice(0, 2) * 60 + +c.hora.slice(3) : "";
        return `<li class="vivo-comp${c.concluida ? " feito" : ""}" data-min="${min}"><time>${esc(h)}</time><span>${esc(c.titulo)}</span></li>`;
      })
      .join("");
    const chips = semHora.map((t) => `<span class="vivo-chip-tarefa">${esc(t)}</span>`).join("");
    return (
      olho(ICONES.dia, titulo) +
      (ehHoje && itens.length ? `<div class="vivo-cabeca"><span class="vivo-num vivo-grande vivo-falta">—</span><span class="vivo-sub vivo-falta-txt"></span></div>` : "") +
      (linhas ? `<ol class="vivo-linha-tempo" data-vivo="dia" data-hoje="${ehHoje ? 1 : 0}">${linhas}${ehHoje ? '<li class="vivo-agora" aria-hidden="true"><span>agora</span></li>' : ""}</ol>` : `<p class="vivo-sub">Nada com horário marcado.</p>`) +
      (chips ? `<p class="vivo-sub">Sem horário</p><div class="vivo-chips">${chips}</div>` : "")
    );
  });

  // ============================================================ viagem_janelas
  const NOME_ITEM = { passagem: "Comprar passagem", hotel: "Reservar hotel" };
  const SELO = { agora: "agora", em_breve: "em breve", passou: "já passou" };
  function svgJanelas(cenario) {
    const ida = Cards.parseDia(cenario.ida);
    const janelas = lista(cenario.janelas);
    const hoje = Cards.parseDia(isoHoje());
    if (!ida || !hoje) return "";
    const inicios = janelas.map((j) => Cards.parseDia(j.inicio)).filter(Boolean);
    const ini = new Date(Math.min(hoje.getTime(), ...inicios.map((d) => d.getTime())));
    ini.setDate(1);
    const fim = new Date(ida.getFullYear(), ida.getMonth() + 1, 0);
    const X0 = 64, X1 = 350; // coluna da esquerda e dos rotulos "Passagem"/"Hotel"
    const x = (d) => X0 + (X1 - X0) * ((d - ini) / Math.max(1, fim - ini));
    let partes = "";
    for (let m = new Date(ini); m <= fim; m = new Date(m.getFullYear(), m.getMonth() + 1, 1)) {
      partes += `<line x1="${x(m).toFixed(1)}" x2="${x(m).toFixed(1)}" y1="26" y2="100" class="vivo-grade"/>`;
      partes += `<text x="${(x(m) + 3).toFixed(1)}" y="116">${esc(m.toLocaleDateString("pt-BR", { month: "short" }).replace(".", ""))}</text>`;
    }
    janelas.forEach((j, i) => {
      const a = Cards.parseDia(j.inicio), b = Cards.parseDia(j.fim);
      if (!a || !b) return;
      const y = 44 + i * 28;
      const xa = Math.max(X0, x(a)), larg = Math.max(2, x(b) - xa);
      partes += `<rect class="vivo-faixa vivo-faixa-${esc(j.item)}" x="${xa.toFixed(1)}" y="${y - 9}" width="${larg.toFixed(1)}" height="18" rx="6" data-larg="${larg.toFixed(1)}"/>`;
      partes += `<text class="vivo-faixa-rot" x="0" y="${y + 3.5}">${j.item === "hotel" ? "Hotel" : "Passagem"}</text>`;
    });
    const xv = x(ida), xh = x(hoje);
    partes += `<path d="M${xv.toFixed(1)} 22 l0 82" class="vivo-viagem-linha"/><circle cx="${xv.toFixed(1)}" cy="22" r="4" class="vivo-viagem-ponto"/>`;
    partes += `<text x="${xv.toFixed(1)}" y="14" text-anchor="end">viagem</text>`;
    partes += `<line x1="${xh.toFixed(1)}" x2="${xh.toFixed(1)}" y1="22" y2="104" class="vivo-hoje"/><text x="${xh.toFixed(1)}" y="14" text-anchor="middle" class="vivo-hoje-txt">hoje</text>`;
    return `<svg class="vivo-janelas" viewBox="0 0 360 124" role="img" aria-label="Janelas de compra até a viagem">${partes}</svg>`;
  }
  function blocoCenario(cenario) {
    const dicas = lista(cenario.janelas)
      .map((j) => {
        const sel = SELO[j.status] || "";
        const detalhe =
          j.status === "agora"
            ? `janela boa até ${diaMes(j.fim)} (faltam ${j.dias} dias)`
            : j.status === "em_breve"
              ? `de ${diaMes(j.inicio)} a ${diaMes(j.fim)} · abre em ${j.dias} dias`
              : `a janela boa era até ${diaMes(j.fim)}; ainda dá, tende a sair mais caro`;
        return `<li class="vivo-dica"><span class="vivo-selo vivo-selo-${esc(j.status)}">${esc(sel)}</span><b>${esc(NOME_ITEM[j.item] || j.item)}</b><p>${esc(detalhe)}</p></li>`;
      })
      .join("");
    const alta = cenario.alta
      ? `<p class="vivo-sub">${esc(cenario.alta.nome)} de ${diaMes(cenario.alta.de)} a ${diaMes(cenario.alta.ate)} · alta temporada</p>`
      : "";
    return alta + svgJanelas(cenario) + `<ul class="vivo-dicas">${dicas}</ul>`;
  }
  Cards.registrar("viagem_janelas", (data) => {
    const cen = data.cenarios && typeof data.cenarios === "object" ? data.cenarios : {};
    const chaves = ["no_feriado", "fora"].filter((k) => cen[k]);
    if (!chaves.length) return null;
    const principal = chaves[0];
    const ida = Cards.parseDia(cen[principal].ida);
    const hoje = Cards.parseDia(isoHoje());
    const dias = ida && hoje ? Math.max(0, Math.round((ida - hoje) / 86400000)) : null;
    const mesNome = data.mes ? new Date(+data.mes.slice(0, 4), +data.mes.slice(5, 7) - 1, 1).toLocaleDateString("pt-BR", { month: "long", year: "numeric" }) : "";
    const alternar =
      chaves.length > 1
        ? `<div class="vivo-chips" role="group" aria-label="Período da viagem">` +
          chaves
            .map(
              (k, i) =>
                `<button type="button" class="vivo-alternar" data-cenario="${k}" aria-pressed="${i === 0}">${
                  k === "fora" ? `Fora ${cen.no_feriado && cen.no_feriado.alta ? `do ${esc(cen.no_feriado.alta.nome)}` : "do feriado"}` : `No ${esc((cen[k].alta || {}).nome || "feriado")}`
                }</button>`
            )
            .join("") +
          `</div>`
        : "";
    const blocos = chaves
      .map((k, i) => `<div class="vivo-cenario" data-cenario-bloco="${k}"${i === 0 ? "" : " hidden"}>${blocoCenario(cen[k])}</div>`)
      .join("");
    return (
      olho(ICONES.viagem, `Viagem${mesNome ? ` · ${mesNome}` : ""}`) +
      `<div class="vivo-cabeca"><span class="vivo-num vivo-grande" data-contar-int="${dias ?? ""}">${dias ?? "—"}</span>` +
      `<span class="vivo-sub">${dias === 1 ? "dia" : "dias"} até ${data.dia_definido ? diaMes(cen[principal].ida) : "a viagem"}${data.destino ? ` · ${esc(data.destino)}` : ""}${data.internacional ? " · internacional" : ""}</span></div>` +
      alternar +
      `<div data-vivo="viagem">${blocos}</div>` +
      `<p class="vivo-nota">Tendências de pesquisas de preço (Viajala, Skyscanner, Google Flights), não garantia. Reserve hotel com cancelamento grátis.</p>`
    );
  });

  // ====================================================================== agua
  const COPO = "M14 10 L82 10 L74 118 Q73 122 69 122 L27 122 Q23 122 22 118 Z";
  Cards.registrar("agua", (data) => {
    if (data.oculto) return olho(ICONES.agua, "Água hoje") + `<p class="card-linha-meta">Oculto no modo visitante.</p>`;
    const copos = Math.max(0, Number(data.copos) || 0);
    const meta = Math.max(1, Number(data.meta) || 8);
    const fila = Array.from({ length: Math.max(meta, copos) }, (_, i) => `<i class="${i < copos ? "cheio" : ""}"></i>`).join("");
    const falta = meta - copos;
    return (
      olho(ICONES.agua, "Água hoje") +
      `<div class="vivo-agua"><svg class="vivo-copo" viewBox="0 0 96 128" aria-hidden="true" data-vivo="agua" data-nivel="${Math.min(1, copos / meta).toFixed(3)}">` +
      `<clipPath id="vivo-clip-copo"><path d="${COPO}"/></clipPath><g clip-path="url(#vivo-clip-copo)"><rect width="96" height="128" class="vivo-copo-fundo"/>` +
      `<path class="vivo-onda vivo-onda-1" d="M0 ${(122 - 112 * Math.min(1, copos / meta)).toFixed(1)} H96 V128 H0 Z"/><path class="vivo-onda vivo-onda-2" d="M0 128 H96 V128 H0 Z"/></g>` +
      `<path d="${COPO}" class="vivo-copo-borda"/></svg>` +
      `<div class="vivo-agua-info"><div class="vivo-cabeca"><span class="vivo-num vivo-grande" data-contar-int="${copos}">${copos}</span><span class="vivo-sub">de ${meta} copos</span></div>` +
      `<div class="vivo-copinhos">${fila}</div><p class="vivo-sub">${falta > 0 ? `faltam ${falta}` : "meta do dia batida"}</p></div></div>`
    );
  });

  // ============================================================= tarefas_lista
  const R_ANEL = 22;
  const C_ANEL = +(2 * Math.PI * R_ANEL).toFixed(2);
  function anelTarefas(feitas, total) {
    const frac = total > 0 ? feitas / total : 0;
    return (
      `<svg class="vivo-anel-tarefas" viewBox="0 0 54 54" aria-hidden="true" data-c="${C_ANEL}">` +
      `<circle cx="27" cy="27" r="${R_ANEL}" class="vivo-anel-fundo"/>` +
      `<circle cx="27" cy="27" r="${R_ANEL}" class="vivo-anel-cheio" transform="rotate(-90 27 27)" ` +
      `stroke-dasharray="${C_ANEL}" stroke-dashoffset="${(C_ANEL * (1 - frac)).toFixed(2)}"/></svg>`
    );
  }
  // "hoje" / "amanhã" / "ontem" / "sex 16 out"
  function diaRelativo(iso) {
    const d = Cards.parseDia(iso);
    const h = Cards.parseDia(isoHoje());
    if (!d || !h) return "";
    const dif = Math.round((d - h) / 86400000);
    if (dif === 0) return "hoje";
    if (dif === 1) return "amanhã";
    if (dif === -1) return "ontem";
    const sem = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"][d.getDay()];
    return `${sem} ${d.getDate()} ${MESES[d.getMonth()]}`;
  }
  const minutosDe = (hora) => (hora && /^\d{2}:\d{2}$/.test(hora) ? +hora.slice(0, 2) * 60 + +hora.slice(3) : "");
  function linhaTarefa(t) {
    const quando = [t.atrasada && t.data ? diaRelativo(t.data) : "", t.hora || ""].filter(Boolean).join(" · ");
    return (
      `<li class="card-tarefa vivo-tarefa${t.concluida ? " concluida" : ""}${t.atrasada ? " atrasada" : ""}" data-min="${t.atrasada ? "" : minutosDe(t.hora)}">` +
      `<label><input type="checkbox" data-tarefa-id="${esc(t.id)}"${t.concluida ? " checked" : ""} aria-label="Concluir ${esc(t.titulo)}">` +
      `<span class="card-tarefa-titulo">${esc(t.titulo)}</span></label>` +
      (quando ? `<span class="card-tarefa-quando">${esc(quando)}</span>` : "") +
      `</li>`
    );
  }
  function fraseTarefas(feitas, total, atrasadas) {
    const pend = total - feitas;
    if (total === 0) return atrasadas ? `Nada pra hoje · ${atrasadas} atrasada${atrasadas > 1 ? "s" : ""}` : "Nada marcado.";
    if (pend === 0) return atrasadas ? `Hoje feito · ${atrasadas} atrasada${atrasadas > 1 ? "s" : ""}` : "Tudo feito. Dia limpo.";
    return `${pend} ${pend === 1 ? "falta" : "faltam"}${atrasadas ? ` · ${atrasadas} atrasada${atrasadas > 1 ? "s" : ""}` : ""}`;
  }
  const grupo = (titulo, itens, extra = "") =>
    `${titulo ? `<p class="vivo-grupo${extra}">${esc(titulo)}</p>` : ""}<ul class="card-tarefas vivo-lista-tarefas">${itens.map(linhaTarefa).join("")}</ul>`;
  const ICONE_FEITO =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path class="vivo-feito-traco" d="M5 12.5 10 17 19 7"/></svg>';

  Cards.registrar("tarefas_lista", (data) => {
    const itens = lista(data.itens).filter((t) => t && t.titulo);
    const atrasadas = lista(data.atrasadas).filter((t) => t && t.titulo);
    const ehHoje = data.de === data.ate && data.de === data.hoje;
    const umDia = data.de === data.ate;
    const titulo = data.so_concluidas
      ? "Concluídas"
      : ehHoje
        ? "Tarefas de hoje"
        : umDia
          ? `Tarefas · ${diaRelativo(data.de)}`
          : `Tarefas · ${diaMes(data.de)} a ${diaMes(data.ate)}`;
    const total = Number(data.total) || 0;
    const feitas = Number(data.feitas) || 0;
    const completo = total > 0 && feitas >= total;

    let corpo = "";
    if (atrasadas.length) corpo += grupo("Atrasadas", atrasadas, " vivo-grupo-alerta");
    if (!umDia) {
      // varios dias: um grupo por dia, na ordem
      const porDia = new Map();
      itens.forEach((t) => {
        const k = t.data || "";
        if (!porDia.has(k)) porDia.set(k, []);
        porDia.get(k).push(t);
      });
      porDia.forEach((lista_, dia) => (corpo += grupo(dia ? diaRelativo(dia) : "Sem data", lista_)));
    } else if (itens.length) {
      const comHora = itens.filter((t) => t.hora);
      const semHora = itens.filter((t) => !t.hora);
      const rotuloHoje = atrasadas.length ? (ehHoje ? "Hoje" : diaRelativo(data.de)) : "";
      if (comHora.length) corpo += grupo(rotuloHoje, comHora);
      if (semHora.length) corpo += grupo(comHora.length || rotuloHoje ? "Sem horário" : "", semHora);
    }
    if (!itens.length && !atrasadas.length) {
      corpo = `<div class="vivo-vazio">${ICONE_FEITO}<p>${data.so_concluidas ? "Nenhuma tarefa concluída no período." : "Nada marcado. Dia livre."}</p></div>`;
    }

    return (
      olho(ICONES.dia, titulo) +
      `<div class="vivo-tarefas-topo${completo ? " completo" : ""}" data-vivo="tarefas" data-total="${total}" data-feitas="${feitas}" data-atrasadas="${atrasadas.length}" data-hoje="${ehHoje ? 1 : 0}">` +
      `<div class="vivo-anel-caixa">${anelTarefas(feitas, total)}<span class="vivo-num vivo-anel-num">${feitas}<small>/${total}</small></span>` +
      `<span class="vivo-anel-feito">${ICONE_FEITO}</span></div>` +
      `<div><p class="vivo-tarefas-frase">${esc(fraseTarefas(feitas, total, atrasadas.length))}</p>` +
      `<p class="vivo-sub vivo-tarefas-conta">${feitas} ${feitas === 1 ? "feita" : "feitas"} de ${total}</p></div></div>` +
      corpo +
      (data.mais ? `<p class="vivo-sub vivo-mais">+${esc(data.mais)} na aba Tarefas</p>` : "")
    );
  });

  // proxima tarefa do dia (so "Tarefas de hoje"): destaque + "em 40 min"
  function marcarProxima(topo) {
    const card = topo.closest(".card-contrato");
    if (!card || topo.dataset.hoje !== "1") return;
    const d = new Date();
    const agora = d.getHours() * 60 + d.getMinutes();
    let proxima = null;
    card.querySelectorAll(".vivo-tarefa").forEach((li) => {
      li.classList.remove("proxima");
      const velho = li.querySelector(".vivo-falta-tarefa");
      if (velho) velho.remove();
      const m = li.dataset.min === "" ? null : +li.dataset.min;
      if (!proxima && m !== null && m >= agora - 15 && !li.classList.contains("concluida")) proxima = li;
    });
    if (!proxima) return;
    proxima.classList.add("proxima");
    const falta = +proxima.dataset.min - agora;
    const quando = proxima.querySelector(".card-tarefa-quando");
    if (quando) {
      const etiqueta = document.createElement("span");
      etiqueta.className = "vivo-falta-tarefa";
      etiqueta.textContent = falta <= 0 ? "agora" : `em ${fmtHmin(falta)}`;
      quando.prepend(etiqueta);
    }
  }

  // ===================================================================== motor
  const reduzido = () => !!(raiz.matchMedia && raiz.matchMedia("(prefers-reduced-motion: reduce)").matches);
  function bezier(x1, y1, x2, y2) {
    const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx;
    const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
    const sx = (t) => ((ax * t + bx) * t + cx) * t;
    const sy = (t) => ((ay * t + by) * t + cy) * t;
    const dx = (t) => (3 * ax * t + 2 * bx) * t + cx;
    return (x) => {
      let t = x;
      for (let i = 0; i < 6; i++) {
        const d = dx(t);
        if (Math.abs(d) < 1e-6) break;
        t -= (sx(t) - x) / d;
      }
      return sy(Math.min(1, Math.max(0, t)));
    };
  }
  const suave = bezier(0.22, 1, 0.36, 1); // = --ease-suave do app
  function tween(dur, passo, easing = suave) {
    return new Promise((fim) => {
      if (reduzido()) {
        passo(1);
        fim();
        return;
      }
      const t0 = performance.now();
      const quadro = (t) => {
        const p = Math.min(1, (t - t0) / dur);
        passo(easing(p));
        if (p < 1) requestAnimationFrame(quadro);
        else fim();
      };
      requestAnimationFrame(quadro);
    });
  }
  const esperar = (ms) => new Promise((r) => setTimeout(r, reduzido() ? 0 : ms));

  // Mudanca de texto feita pelo card (contador, relogio do dia) nao e mensagem nova: marca a
  // pagina pro auto-rolar do chat ignorar (o MutationObserver roda em microtask, por isso o
  // setTimeout pra limpar - ver irProFim em secoes/hoje/chat.js).
  let _semRolarId = 0;
  function semRolar(fn) {
    const doc = raiz.document && raiz.document.documentElement;
    if (doc) doc.dataset.vivoSemRolar = "1";
    try {
      fn();
    } finally {
      clearTimeout(_semRolarId);
      _semRolarId = setTimeout(() => doc && delete doc.dataset.vivoSemRolar, 0);
    }
  }

  // numeros que "contam" ate o valor final (data-contar-*)
  function contar(el, dur = 1400) {
    const alvos = el.querySelectorAll("[data-contar-hhmm],[data-contar-int],[data-contar-moeda],[data-contar-graus]");
    alvos.forEach((n) => {
      const ds = n.dataset;
      const fmt = ds.contarHhmm !== undefined ? hhmmMin : ds.contarMoeda !== undefined ? moedaCurta : ds.contarGraus !== undefined ? (v) => `${Math.round(v)}°` : (v) => String(Math.round(v));
      const alvo = Number(ds.contarHhmm ?? ds.contarInt ?? ds.contarMoeda ?? ds.contarGraus);
      if (!Number.isFinite(alvo)) return;
      tween(dur, (e) => semRolar(() => (n.textContent = fmt(alvo * e))));
    });
  }

  // ---- voo: aviao no arco
  function vooPosicionar(svg, frac) {
    const base = svg.querySelector(".vivo-arco-base");
    const rastro = svg.querySelector(".vivo-arco-rastro");
    const aviao = svg.querySelector(".vivo-aviao");
    if (!base || typeof base.getTotalLength !== "function") return;
    const L = base.getTotalLength();
    const p = base.getPointAtLength(L * frac);
    const q = base.getPointAtLength(Math.min(L, L * frac + 1));
    aviao.setAttribute("transform", `translate(${p.x} ${p.y}) rotate(${(Math.atan2(q.y - p.y, q.x - p.x) * 180) / Math.PI})`);
    rastro.style.strokeDasharray = `${L}`;
    rastro.style.strokeDashoffset = `${L - L * frac}`;
  }
  function vooMarcos(svg) {
    const base = svg.querySelector(".vivo-arco-base");
    const g = svg.querySelector(".vivo-marcos");
    if (!base || !g || typeof base.getTotalLength !== "function") return;
    const L = base.getTotalLength();
    const meta = +svg.dataset.meta * 60;
    const marcos = [];
    if (svg.dataset.solo !== undefined) marcos.push({ min: +svg.dataset.solo, txt: "1º solo" });
    marcos.push({ min: +svg.dataset.total, txt: hhmmMin(+svg.dataset.total), agora: true });
    g.innerHTML = marcos
      .map((m) => {
        const p = base.getPointAtLength(L * Math.min(1, m.min / meta));
        return (
          `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="${m.agora ? 3.5 : 3}" class="${m.agora ? "vivo-marco-agora" : "vivo-marco"}"/>` +
          `<text x="${p.x.toFixed(1)}" y="${(p.y - (m.agora ? 16 : 10)).toFixed(1)}" text-anchor="middle" class="${m.agora ? "vivo-marco-txt-agora" : ""}">${esc(m.txt)}</text>`
        );
      })
      .join("");
  }

  // ---- clima: ceu em canvas
  const CEUS = {
    limpo: { dia: ["#123a5a", "#0b1e30"], noite: ["#0a1430", "#04070f"], nuvens: 1, chuva: 0 },
    nublado: { dia: ["#1b2530", "#0c1117"], noite: ["#111821", "#05080b"], nuvens: 5, chuva: 0 },
    neblina: { dia: ["#222a31", "#10151a"], noite: ["#141a20", "#07090c"], nuvens: 7, chuva: 0, neblina: true },
    chuva: { dia: ["#16202b", "#080c10"], noite: ["#0d141c", "#040609"], nuvens: 6, chuva: 170 },
    trovoada: { dia: ["#120f1f", "#05040a"], noite: ["#0c0a16", "#030207"], nuvens: 7, chuva: 240, raio: true },
  };
  const ceusAtivos = new Set();
  function montarCeu(caixa) {
    const canvas = caixa.querySelector("canvas");
    if (!canvas || !canvas.getContext) return null;
    const ctx = canvas.getContext("2d");
    const hora = new Date().getHours();
    const noite = hora >= 18 || hora < 6;
    const cena = CEUS[caixa.dataset.cena] || CEUS.nublado;
    const st = { canvas, ctx, cena, noite, t: 0, flash: 0, rodando: false, nuvens: [], gotas: [], estrelas: [] };
    st.dimensionar = () => {
      const r = canvas.getBoundingClientRect();
      const dpr = Math.min(2, raiz.devicePixelRatio || 1);
      canvas.width = Math.max(1, r.width * dpr);
      canvas.height = Math.max(1, r.height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const w = r.width, h = r.height;
      st.w = w;
      st.h = h;
      st.nuvens = Array.from({ length: cena.nuvens }, () => ({ x: Math.random() * w, y: 16 + Math.random() * 60, s: 0.7 + Math.random() * 0.8, v: 0.08 + Math.random() * 0.12, a: (cena.neblina ? 0.12 : 0.08) + Math.random() * 0.1 }));
      st.gotas = Array.from({ length: cena.chuva }, () => ({ x: Math.random() * w, y: Math.random() * h, v: 4 + Math.random() * 4, l: 8 + Math.random() * 10 }));
      st.estrelas = noite && !cena.chuva ? Array.from({ length: 40 }, () => ({ x: Math.random() * w, y: Math.random() * h * 0.6, f: Math.random() * 6 })) : [];
    };
    st.dimensionar();
    st.quadro = () => {
      const { w, h } = st;
      st.t += 1;
      const g = ctx.createLinearGradient(0, 0, 0, h);
      const cores = noite ? cena.noite : cena.dia;
      g.addColorStop(0, cores[0]);
      g.addColorStop(1, cores[1]);
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);
      st.estrelas.forEach((e) => {
        ctx.fillStyle = `rgba(230,238,255,${0.25 + 0.35 * Math.abs(Math.sin(st.t * 0.02 + e.f))})`;
        ctx.fillRect(e.x, e.y, 1.4, 1.4);
      });
      if (caixa.dataset.cena === "limpo") {
        const cx = w - 66, cy = 54;
        if (noite) {
          ctx.fillStyle = "rgba(235,240,255,0.92)";
          ctx.beginPath();
          ctx.arc(cx, cy, 16, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillStyle = cores[0];
          ctx.beginPath();
          ctx.arc(cx + 7, cy - 5, 14, 0, Math.PI * 2);
          ctx.fill();
        } else {
          ctx.save();
          ctx.translate(cx, cy);
          ctx.rotate(st.t * 0.003);
          ctx.strokeStyle = "rgba(255,214,140,0.55)";
          ctx.lineWidth = 2;
          ctx.lineCap = "round";
          for (let i = 0; i < 12; i++) {
            ctx.rotate(Math.PI / 6);
            ctx.beginPath();
            ctx.moveTo(0, 30);
            ctx.lineTo(0, 40 + Math.sin(st.t * 0.03 + i) * 3);
            ctx.stroke();
          }
          ctx.restore();
          const sg = ctx.createRadialGradient(cx, cy, 4, cx, cy, 70);
          sg.addColorStop(0, "rgba(255,226,160,1)");
          sg.addColorStop(0.32, "rgba(255,200,120,0.9)");
          sg.addColorStop(0.35, "rgba(255,200,120,0.18)");
          sg.addColorStop(1, "rgba(255,200,120,0)");
          ctx.fillStyle = sg;
          ctx.beginPath();
          ctx.arc(cx, cy, 70, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      st.nuvens.forEach((n) => {
        if (st.rodando) n.x += n.v;
        if (n.x > w + 60) n.x = -110;
        ctx.fillStyle = `rgba(200,215,230,${n.a})`;
        ctx.beginPath();
        [[0, 0, 26], [24, -10, 22], [48, 0, 24], [20, 8, 24]].forEach(([dx, dy, r]) => {
          ctx.moveTo(n.x + dx * n.s + r * n.s, n.y + dy * n.s);
          ctx.arc(n.x + dx * n.s, n.y + dy * n.s, r * n.s, 0, Math.PI * 2);
        });
        ctx.fill();
      });
      if (st.gotas.length) {
        ctx.strokeStyle = "rgba(170,205,235,0.45)";
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        st.gotas.forEach((d) => {
          if (st.rodando) {
            d.y += d.v;
            d.x -= d.v * 0.18;
            if (d.y > h) {
              d.y = -d.l;
              d.x = Math.random() * (w + 40);
            }
          }
          ctx.moveTo(d.x, d.y);
          ctx.lineTo(d.x + d.l * 0.18, d.y - d.l);
        });
        ctx.stroke();
      }
      if (cena.raio && st.rodando) {
        if (st.flash <= 0 && Math.random() < 0.006) st.flash = 1;
        if (st.flash > 0) {
          ctx.fillStyle = `rgba(220,215,255,${st.flash * 0.35})`;
          ctx.fillRect(0, 0, w, h);
          st.flash -= 0.06;
        }
      }
      const sombra = ctx.createLinearGradient(0, h * 0.4, 0, h);
      sombra.addColorStop(0, "rgba(8,11,14,0)");
      sombra.addColorStop(1, "rgba(8,11,14,0.92)");
      ctx.fillStyle = sombra;
      ctx.fillRect(0, 0, w, h);
      if (st.rodando) requestAnimationFrame(st.quadro);
    };
    st.ligar = (sim) => {
      if (reduzido()) sim = false;
      if (sim === st.rodando) return;
      st.rodando = sim;
      if (sim) requestAnimationFrame(st.quadro);
    };
    st.quadro(); // um quadro parado sempre (historico / sem animacao)
    return st;
  }

  // ---- agua: onda
  function montarAgua(svg) {
    const ondas = [svg.querySelector(".vivo-onda-1"), svg.querySelector(".vivo-onda-2")];
    const st = { alvo: +svg.dataset.nivel || 0, nivel: +svg.dataset.nivel || 0, fase: 0, agito: 1.2, rodando: false };
    st.desenhar = () => {
      const topo = 122 - 112 * st.nivel;
      const caminho = (desl, a) => {
        let d = `M0 ${topo.toFixed(2)}`;
        for (let x = 0; x <= 96; x += 4) d += ` L${x} ${(topo + Math.sin((x / 96) * Math.PI * 2 + desl) * a).toFixed(2)}`;
        return d + " L96 128 L0 128 Z";
      };
      ondas[0].setAttribute("d", caminho(st.fase, st.agito));
      ondas[1].setAttribute("d", caminho(st.fase * 0.7 + 1.6, st.agito * 1.4));
    };
    st.laco = () => {
      st.fase += 0.06;
      st.nivel += (st.alvo - st.nivel) * 0.05;
      st.agito += (1.2 - st.agito) * 0.03;
      st.desenhar();
      if (st.rodando) requestAnimationFrame(st.laco);
    };
    st.ligar = (sim) => {
      if (reduzido()) sim = false;
      if (sim === st.rodando) return;
      st.rodando = sim;
      if (sim) requestAnimationFrame(st.laco);
    };
    st.desenhar();
    return st;
  }

  // ---- dia: posicao da linha "agora"
  function posicionarAgora(ol) {
    const itens = [...ol.querySelectorAll(".vivo-comp")].filter((li) => li.dataset.min !== "");
    const linha = ol.querySelector(".vivo-agora");
    const card = ol.closest(".card-contrato");
    if (!linha || !itens.length) return;
    const d = new Date();
    const agora = d.getHours() * 60 + d.getMinutes();
    let proximo = null;
    itens.forEach((li) => {
      const m = +li.dataset.min;
      li.classList.toggle("passou", m <= agora);
      li.classList.remove("proximo");
      if (!proximo && m > agora) proximo = li;
    });
    if (proximo) proximo.classList.add("proximo");
    const tops = itens.map((li) => li.offsetTop + li.offsetHeight / 2);
    const mins = itens.map((li) => +li.dataset.min);
    let topo;
    if (agora <= mins[0]) topo = tops[0] - 16;
    else if (agora >= mins[mins.length - 1]) topo = tops[tops.length - 1] + 16;
    else {
      const i = mins.findIndex((m) => m > agora) - 1;
      topo = tops[i] + (tops[i + 1] - tops[i]) * ((agora - mins[i]) / Math.max(1, mins[i + 1] - mins[i]));
    }
    linha.style.top = `${topo}px`;
    const falta = card && card.querySelector(".vivo-falta");
    const txt = card && card.querySelector(".vivo-falta-txt");
    if (falta && txt) {
      if (proximo) {
        falta.textContent = fmtHmin(+proximo.dataset.min - agora);
        txt.textContent = `até ${proximo.querySelector("span").textContent}`;
      } else {
        falta.textContent = "livre";
        txt.textContent = "nada mais com horário hoje";
      }
    }
  }

  // ---- rota: caminho real + carrinho
  function rotaCarro(svg, frac) {
    const caminho = svg.querySelector(".vivo-rota-caminho");
    const carro = svg.querySelector(".vivo-rota-carro");
    if (!caminho || !carro || typeof caminho.getTotalLength !== "function") return;
    const L = caminho.getTotalLength();
    const p = caminho.getPointAtLength(L * frac);
    carro.setAttribute("transform", `translate(${p.x} ${p.y})`);
  }

  // ---- ciclo de vida (so ate o card sair da tela - nada roda escondido)
  const vigia =
    typeof IntersectionObserver !== "undefined"
      ? new IntersectionObserver(
          (entradas) => entradas.forEach((en) => en.target._vivo && en.target._vivo.ligar(en.isIntersecting)),
          { threshold: 0.15 }
        )
      : null;

  function preparar(raizEl) {
    if (!raizEl || !raizEl.querySelectorAll) return;
    raizEl.querySelectorAll('[data-vivo="voo"]').forEach((svg) => {
      vooMarcos(svg);
      vooPosicionar(svg, Math.min(1, +svg.dataset.total / (+svg.dataset.meta * 60)));
    });
    raizEl.querySelectorAll('[data-vivo="clima"]').forEach((caixa) => {
      const st = montarCeu(caixa);
      if (!st) return;
      caixa._vivo = st;
      ceusAtivos.add(st);
      if (vigia) vigia.observe(caixa);
    });
    raizEl.querySelectorAll('[data-vivo="agua"]').forEach((svg) => {
      svg._vivo = montarAgua(svg);
      if (vigia) vigia.observe(svg);
    });
    raizEl.querySelectorAll('[data-vivo="dia"][data-hoje="1"]').forEach((ol) => {
      requestAnimationFrame(() => semRolar(() => posicionarAgora(ol)));
      if (!ol._relogio)
        ol._relogio = setInterval(() => (ol.isConnected ? semRolar(() => posicionarAgora(ol)) : clearInterval(ol._relogio)), 60000);
    });
    raizEl.querySelectorAll(".vivo-rota-mapa").forEach((svg) => rotaCarro(svg, 1));
    raizEl.querySelectorAll('[data-vivo="tarefas"]').forEach((topo) => {
      const card = topo.closest(".card-contrato");
      if (!card || card._tarefasLigado || typeof MutationObserver === "undefined") return;
      card._tarefasLigado = true;
      // O anel segue o que esta DE FATO concluido: cards.js so marca o <li> com
      // .concluida depois que o servidor confirmou (e desmarca a caixinha se falhar).
      const recontar = () => {
        const lis = [...card.querySelectorAll(".vivo-tarefa")];
        const total = +topo.dataset.total;
        const feitas = Math.min(total, lis.filter((li) => !li.classList.contains("atrasada") && li.classList.contains("concluida")).length);
        const atras = lis.filter((li) => li.classList.contains("atrasada") && !li.classList.contains("concluida")).length;
        semRolar(() => marcarProxima(topo));
        if (feitas === +topo.dataset.feitas && atras === +topo.dataset.atrasadas) return;
        topo.dataset.feitas = feitas;
        topo.dataset.atrasadas = atras;
        topo.classList.toggle("completo", total > 0 && feitas >= total);
        const anel = topo.querySelector(".vivo-anel-cheio");
        const C = +topo.querySelector(".vivo-anel-tarefas").dataset.c;
        if (anel) {
          anel.style.transition = "stroke-dashoffset .7s var(--ease-suave)";
          anel.setAttribute("stroke-dashoffset", (C * (1 - (total ? feitas / total : 0))).toFixed(2));
        }
        semRolar(() => {
          const num = topo.querySelector(".vivo-anel-num");
          if (num) num.innerHTML = `${feitas}<small>/${total}</small>`;
          const frase = topo.querySelector(".vivo-tarefas-frase");
          if (frase) frase.textContent = fraseTarefas(feitas, total, atras);
          const conta = topo.querySelector(".vivo-tarefas-conta");
          if (conta) conta.textContent = `${feitas} ${feitas === 1 ? "feita" : "feitas"} de ${total}`;
        });
      };
      new MutationObserver((muts) => {
        const mudouConclusao = muts.some(
          (m) => m.target.classList && (m.oldValue || "").includes("concluida") !== m.target.classList.contains("concluida")
        );
        if (!mudouConclusao) return;
        muts.forEach((m) => {
          const li = m.target;
          if (li.classList && li.classList.contains("concluida") && !(m.oldValue || "").includes("concluida")) {
            li.classList.remove("vivo-acabou");
            void li.offsetWidth;
            li.classList.add("vivo-acabou");
          }
        });
        recontar();
      }).observe(card, { subtree: true, attributes: true, attributeFilter: ["class"], attributeOldValue: true });
      semRolar(() => marcarProxima(topo));
      if (topo.dataset.hoje === "1" && !topo._relogio)
        topo._relogio = setInterval(() => (topo.isConnected ? semRolar(() => marcarProxima(topo)) : clearInterval(topo._relogio)), 60000);
    });
    // viagem: trocar cenario (no feriado / fora)
    raizEl.querySelectorAll(".vivo-alternar").forEach((b) => {
      if (b._ligado) return;
      b._ligado = true;
      b.addEventListener("click", () => {
        const card = b.closest(".card-contrato");
        card.querySelectorAll(".vivo-alternar").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
        card.querySelectorAll("[data-cenario-bloco]").forEach((bl) => (bl.hidden = bl.dataset.cenarioBloco !== b.dataset.cenario));
        animarViagem(card.querySelector(`[data-cenario-bloco="${b.dataset.cenario}"]`));
      });
    });
  }

  function animarViagem(bloco) {
    if (!bloco) return;
    bloco.querySelectorAll(".vivo-faixa").forEach((r) => {
      const larg = +r.dataset.larg;
      tween(1100, (e) => r.setAttribute("width", (larg * e).toFixed(1)));
    });
    bloco.querySelectorAll(".vivo-dica").forEach((d, i) => {
      d.classList.remove("entrou");
      setTimeout(() => d.classList.add("entrou"), reduzido() ? 0 : 500 + i * 130);
    });
  }

  async function animar(raizEl) {
    if (!raizEl || !raizEl.querySelectorAll || reduzido()) return;
    contar(raizEl);
    raizEl.querySelectorAll('[data-vivo="voo"]').forEach(async (svg) => {
      const fim = Math.min(1, +svg.dataset.total / (+svg.dataset.meta * 60));
      const marcos = svg.querySelector(".vivo-marcos");
      marcos.style.opacity = 0;
      const barras = [...svg.closest(".card-contrato").querySelectorAll(".vivo-trilho i")];
      barras.forEach((b) => (b.style.transform = "scaleX(0)"));
      await tween(2200, (e) => vooPosicionar(svg, fim * e));
      marcos.style.transition = "opacity .6s var(--ease-suave)";
      marcos.style.opacity = 1;
      for (const b of barras) {
        b.style.transition = "transform .9s var(--ease-bounce)";
        b.style.transform = "scaleX(1)";
        await esperar(120);
      }
    });
    raizEl.querySelectorAll(".vivo-rota-mapa").forEach(async (svg) => {
      const caminho = svg.querySelector(".vivo-rota-caminho");
      if (!caminho || typeof caminho.getTotalLength !== "function") return;
      const L = caminho.getTotalLength();
      const pinos = svg.querySelectorAll(".vivo-rota-pino");
      pinos.forEach((p, i) => i && (p.style.opacity = 0));
      caminho.style.strokeDasharray = L;
      await tween(2000, (e) => {
        caminho.style.strokeDashoffset = L * (1 - e);
        rotaCarro(svg, e);
        pinos.forEach((p) => {
          if (+p.dataset.frac <= e + 0.01) p.style.opacity = 1;
        });
      });
    });
    raizEl.querySelectorAll('[data-vivo="gastos"]').forEach((svg) => {
      let vals = [];
      try {
        vals = JSON.parse(svg.dataset.cats || "[]");
      } catch {
        vals = [];
      }
      const total = +svg.dataset.total || 0;
      const arcos = [...svg.querySelectorAll("circle")].slice(1);
      tween(1500, (e) => {
        let acum = 0;
        arcos.forEach((a, i) => {
          const fatia = total > 0 ? (vals[i] / total) * 100 : 0;
          const vis = Math.max(0, Math.min(fatia, e * 100 - acum) - (fatia > 1.2 ? 0.8 : 0));
          a.setAttribute("stroke-dasharray", `${vis.toFixed(2)} ${(100 - vis).toFixed(2)}`);
          acum += fatia;
        });
      });
      svg.closest(".card-contrato").querySelectorAll(".vivo-legenda > div").forEach((l, i) => {
        l.classList.remove("entrou");
        setTimeout(() => l.classList.add("entrou"), 200 + i * 110);
      });
    });
    raizEl.querySelectorAll('[data-vivo="dia"]').forEach((ol) => {
      ol.querySelectorAll(".vivo-comp").forEach((li, i) => {
        li.classList.remove("entrou");
        li.style.opacity = "0";
        setTimeout(() => {
          li.style.opacity = "";
          li.classList.add("entrou");
        }, 120 + i * 90);
      });
    });
    raizEl.querySelectorAll('[data-vivo="viagem"]').forEach((el) => animarViagem(el.querySelector("[data-cenario-bloco]:not([hidden])")));
    raizEl.querySelectorAll('[data-vivo="agua"]').forEach((svg) => {
      if (!svg._vivo) return;
      svg._vivo.nivel = 0;
      svg._vivo.agito = 4;
    });
    raizEl.querySelectorAll(".vivo-copinhos i.cheio").forEach((c, i) => {
      c.classList.remove("cheio");
      setTimeout(() => c.classList.add("cheio"), 200 + i * 120);
    });
    raizEl.querySelectorAll('[data-vivo="edicao"] .vivo-mudanca').forEach((m, i) => {
      m.classList.remove("entrou");
      setTimeout(() => m.classList.add("entrou"), 150 + i * 160);
    });
    raizEl.querySelectorAll(".vivo-semana-anel[data-feito='1']").forEach(async (anel, i) => {
      const C = +anel.dataset.c;
      anel.style.transition = "none";
      anel.setAttribute("stroke-dashoffset", C);
      await esperar(80 + i * 260);
      anel.style.transition = "stroke-dashoffset .8s var(--ease-suave)";
      anel.setAttribute("stroke-dashoffset", 0);
    });
    raizEl.querySelectorAll('[data-vivo="tarefas"]').forEach((topo) => {
      const anel = topo.querySelector(".vivo-anel-cheio");
      const C = +topo.querySelector(".vivo-anel-tarefas").dataset.c;
      const alvo = anel.getAttribute("stroke-dashoffset");
      anel.style.transition = "none";
      anel.setAttribute("stroke-dashoffset", C);
      requestAnimationFrame(() =>
        requestAnimationFrame(() => {
          anel.style.transition = "stroke-dashoffset 1.2s var(--ease-suave)";
          anel.setAttribute("stroke-dashoffset", alvo);
        })
      );
      topo.closest(".card-contrato").querySelectorAll(".vivo-tarefa").forEach((li, i) => {
        li.classList.remove("entrou");
        li.style.opacity = "0";
        setTimeout(() => {
          li.style.opacity = "";
          li.classList.add("entrou");
        }, 150 + i * 70);
      });
    });
    raizEl.querySelectorAll(".card-contrato-tarefas_criadas").forEach((card) => {
      const dia = card.querySelector('[data-vivo="criadas"]');
      if (!dia) {
        card.querySelectorAll(".card-tarefa").forEach((li, i) => {
          li.classList.remove("vivo-caiu");
          setTimeout(() => li.classList.add("vivo-caiu"), 120 + i * 110);
        });
        return;
      }
      // as do dia entram primeiro (apagadas); a nova abre espaco e pousa por ultimo
      const itens = [...dia.querySelectorAll(".vivo-dia-item")];
      itens.forEach((li) => {
        li.classList.remove("entrou", "pousou");
        li.style.opacity = "0"; // escondido ja no 1o quadro (senao aparece e "pisca" antes de entrar)
      });
      const entrar = (li, classe) => {
        li.style.opacity = ""; // a animacao (fill both) assume dali em diante
        li.classList.add(classe);
      };
      itens.filter((li) => !li.classList.contains("vivo-nova")).forEach((li, i) => setTimeout(() => entrar(li, "entrou"), 80 + i * 60));
      const depois = 200 + itens.length * 60;
      itens.filter((li) => li.classList.contains("vivo-nova")).forEach((li, i) => setTimeout(() => entrar(li, "pousou"), depois + i * 180));
    });
    raizEl.querySelectorAll('[data-vivo="clima"] .vivo-hora i').forEach((b, i) => {
      b.style.transform = "scaleY(0)";
      requestAnimationFrame(() => {
        b.style.transition = `transform .8s var(--ease-bounce) ${i * 60}ms`;
        b.style.transform = "scaleY(1)";
      });
    });
  }

  const CardsVivos = { preparar, animar, cenaClima, _esperar: esperar };
  raiz.CardsVivos = CardsVivos;
  if (typeof module !== "undefined" && module.exports) module.exports = CardsVivos;
})(typeof window !== "undefined" ? window : globalThis);
