// Cards de compromisso com cara propria (2026-10-14, 2a leva do prototipo aprovado - docs/CARDS.md
// "Linguagem visual dos cards"): date (coracao + linha se arrumar -> sair -> chegar), balada (ceu
// de noite + sono ate o compromisso do dia seguinte + chave do Uber), documentos (pasta que
// recebe os papeis + carimbo + horario do Google) e presente (caixa que abre + prazo de compra +
// ideias que viram lembrete). Fonte: tasks.estilo/extras (cards.card_compromisso).
//
// Mesmo contrato do resto: o renderizador e PURO e devolve o estado final (historico, testes em
// Node); a entrada animada e CSS em .card-novo (cards-premium.js poe a classe so na resposta nova);
// cliques via Cards.registrarAcao. prefers-reduced-motion: nada anima.
(function (raiz) {
  "use strict";
  const Cards = raiz.Cards || (typeof require === "function" ? require("./cards.js") : null);
  if (!Cards) return;
  const { esc, numeroValido } = Cards;

  const svg = (corpo, extra = "") =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"${extra}>${corpo}</svg>`;
  const I = {
    coracao: svg('<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10Z"/>'),
    lua: svg('<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z"/>'),
    pasta: svg('<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>'),
    presente: svg('<rect x="3.5" y="9" width="17" height="11" rx="2"/><path d="M2.5 9h19M12 9v11M12 9c-2-4-7-4-5 0M12 9c2-4 7-4 5 0"/>'),
    termometro: svg('<path d="M10 14V5a2 2 0 0 1 4 0v9a4 4 0 1 1-4 0Z"/>'),
    camisa: svg('<path d="M8 4 4 6.5 5.5 10 7 9.5V20h10V9.5l1.5.5L20 6.5 16 4a4 4 0 0 1-8 0Z"/>'),
    chuva: svg('<path d="M17.5 15H9a6 6 0 1 1 5.7-7.9h1.3a4 4 0 0 1 1.5 7.9Z"/><path d="M9 18l-1 2.5M13 18l-1 2.5M17 18l-1 2.5"/>'),
    pin: svg('<path d="M12 21s-7-6-7-11a7 7 0 0 1 14 0c0 5-7 11-7 11Z"/><circle cx="12" cy="10" r="2.5"/>'),
    relogio: svg('<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>'),
    alerta: svg('<path d="M12 4 2.8 19.5h18.4L12 4Z"/><path d="M12 10v4M12 17h.01"/>'),
    ok: svg('<circle cx="12" cy="12" r="8.5"/><path d="m8.5 12.3 2.4 2.3 4.6-4.9"/>'),
    check: svg('<path d="m5 12.5 4.2 4L19 7"/>', ' stroke-width="3"'),
    carro: svg('<path d="M5 16.5V12l1.8-4.6A2 2 0 0 1 8.7 6h6.6a2 2 0 0 1 1.9 1.4L19 12v4.5"/><path d="M4 12h16v4.5H4z"/><circle cx="7.5" cy="16.5" r="1.6"/><circle cx="16.5" cy="16.5" r="1.6"/>'),
    carona: svg('<circle cx="9" cy="8" r="3"/><circle cx="17" cy="9.5" r="2.4"/><path d="M3.5 19a5.5 5.5 0 0 1 11 0M14.5 15.2a4.3 4.3 0 0 1 6 3.8"/>'),
    celular: svg('<rect x="7" y="3" width="10" height="18" rx="2.5"/><path d="M11 17.5h2"/>'),
    sem_alcool: svg('<path d="M8 3h8l-1 8a3 3 0 0 1-6 0Z"/><path d="M12 14v6M9 20.5h6"/><path d="M4 4l16 16"/>'),
    repete: svg('<path d="M4 12a8 8 0 0 1 13.7-5.6L20 8.5"/><path d="M20 4v4.5h-4.5"/><path d="M20 12a8 8 0 0 1-13.7 5.6L4 15.5"/><path d="M4 20v-4.5h4.5"/>'),
  };
  const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  const DIAS = ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"];
  const lista = (v) => (Array.isArray(v) ? v : []);
  const minDia = (h) => {
    const m = /^(\d{1,2}):(\d{2})/.exec(h || "");
    return m ? +m[1] * 60 + +m[2] : null;
  };
  // "20:00" -> "20h"; "20:15" -> "20h15"
  const horaBr = (h) => {
    const m = minDia(h);
    return m === null ? "" : `${Math.floor(m / 60)}h${m % 60 ? String(m % 60).padStart(2, "0") : ""}`;
  };
  function olho(icone, texto, extra) {
    return `<div class="card-resultado-eyebrow">${icone}<span>${esc(texto)}</span>${extra || ""}</div>`;
  }
  // "sábado" (ate 6 dias) / "hoje" / "amanhã" / "sáb 24 out"
  function quandoDia(iso, agora) {
    const d = Cards.parseDia(iso);
    if (!d) return "";
    const delta = Cards.diasEntre(agora, d);
    if (delta === 0) return "hoje";
    if (delta === 1) return "amanhã";
    if (delta > 1 && delta < 7) return DIAS[d.getDay()];
    return `${DIAS[d.getDay()].slice(0, 3)} ${d.getDate()} ${MESES[d.getMonth()]}`;
  }
  function ficha(icone, html, extra = "") {
    return `<span class="sd-ficha${extra}">${icone}<span>${html}</span></span>`;
  }
  // caixinhas que marcam (persistem no servidor - /api/tasks/<id>/lista)
  function checklist(itens, taskId) {
    return (
      `<ul class="sd-check">` +
      itens
        .map((it, i) => {
          const feito = !!it.feito;
          return (
            `<li class="${feito ? "marcado" : ""}" style="--k:${i}"><button type="button" class="sd-check-item" data-acao="lista_item" data-tarefa="${esc(taskId)}" data-i="${i}" aria-pressed="${feito}">` +
            `<span class="sd-caixinha">${I.check}</span><span class="sd-item-txt">${esc(it.texto)}` +
            (it.detalhe ? `<small>${esc(it.detalhe)}</small>` : "") +
            `</span>` +
            (it.quando ? `<span class="sd-item-quando">${esc(it.quando)}</span>` : "") +
            `</button></li>`
          );
        })
        .join("") +
      `</ul>`
    );
  }

  // ============================================================ linguagem D (04/11)
  // Date e balada viram a pílula "ao vivo" (docs/CARDS.md, cena 2): fechada conta até o próximo passo
  // (se arrumar / sair / chegar, em SEGUNDOS do servidor + gerado_ts); aberta mostra a cadeia, o tempo
  // hora a hora, o que levar e a nota. Checklist do date, sono e volta da balada continuam embaixo.
  const D = () => raiz.CardsD || (typeof require === "function" ? require("./cards-d.js") : null);
  const COR_DATE = "#f5a3b8";
  const COR_BALADA = "#c4a1ff";
  const ROTULO_CONTA = { "Se arrumar": "arrumar em", Sair: "sair em", Chegar: "chega em" };

  // o próximo passo que ainda não passou (pelo relógio do ctx), pra contagem da direita
  function proximoPasso(cadeia, geradoTs, agora) {
    const cd = D();
    const ag = agora instanceof Date ? agora.getTime() : Date.now();
    return lista(cadeia).find((p) => p && numeroValido(p.em_s) && cd.restante(p.em_s, geradoTs, ag) > 0) || null;
  }
  // tempo na chegada: a coluna marcada do hora a hora; senão o clima da hora que já vinha
  function tempoChegada(data) {
    const h = lista(data.clima_horas).find((x) => x && x.marca === "chegada");
    if (h) return { temp: h.temp, chuva_pct: h.chuva_pct };
    return data.clima && numeroValido(data.clima.temp) ? data.clima : null;
  }
  function subSaida(data, agora) {
    const dia = quandoDia(data.data, agora);
    const partes = [];
    if (dia && dia !== "hoje") partes.push(dia);
    if (data.hora) partes.push(`chegar ${data.hora}`);
    const t = tempoChegada(data);
    if (t && numeroValido(t.temp)) {
      partes.push(`${Math.round(t.temp)}°${numeroValido(t.chuva_pct) && t.chuva_pct >= 20 ? ` · ${Math.round(t.chuva_pct)}%` : ""}`);
    }
    return partes.length ? `<span>${esc(partes.join(" · "))}</span>` : "";
  }
  function notaSaida(data) {
    const partes = [];
    if (numeroValido(data.trajeto_min)) {
      const transito = numeroValido(data.transito_min) && data.transito_min >= 3 ? ` (${data.transito_min} de trânsito)` : "";
      partes.push(`${data.trajeto_min} min de carro até lá${transito}.`);
    }
    if (lista(data.clima_horas).length) {
      partes.push(`${data.clima_lugar ? `Previsão pra ${data.clima_lugar}. ` : ""}Se mudar até a hora, eu ajusto a saída e te aviso.`);
    }
    return partes.length ? `<p class="v-nota">${esc(partes.join(" "))}</p>` : "";
  }
  // cadeia do servidor; card antigo (sem cadeia) monta as caixas com as horas que já tinha
  function cadeiaSaida(data) {
    const cd = D();
    if (lista(data.cadeia).length) return cd.cadeia(data.cadeia);
    if (!data.comecar || !data.hora) return "";
    return cd.cadeia([
      { rotulo: "Se arrumar", hora: data.comecar },
      { rotulo: "Sair", hora: data.sair },
      { rotulo: "Chegar", hora: data.hora },
    ]);
  }
  function pilulaSaida(data, card, ctx, o) {
    const cd = D();
    const agora = (ctx && ctx.agora) || new Date();
    const prox = proximoPasso(data.cadeia, data.gerado_ts, agora);
    const rotulo = prox ? (prox.parada ? "parada em" : ROTULO_CONTA[prox.rotulo] || "em") : "";
    return cd.pilula({
      v: o.v,
      cor: o.cor,
      icone: o.icone,
      titulo: o.titulo,
      sub: subSaida(data, agora),
      rotulo,
      valor: prox ? cd.contagem(prox.em_s, data.gerado_ts, "min", agora) : "",
      attrs: data.id !== undefined ? ` data-compromisso="${esc(data.id)}"` : "",
      corpo:
        cadeiaSaida(data) +
        cd.tempoHoras(data.clima_horas) +
        cd.levar(data.levar) +
        notaSaida(data) +
        (o.extra || "") +
        cd.botoes(card),
    });
  }

  // ======================================================================= date
  Cards.registrar("date", (data, card, ctx) => {
    if (!data.titulo || !data.data) return null;
    const itens = lista(data.lista).filter((i) => i && i.texto);
    const titulo = data.com_quem ? `Date com ${data.com_quem}` : data.lugar ? `Date · ${data.lugar}` : "Date";
    return pilulaSaida(data, card, ctx, {
      v: "date",
      cor: COR_DATE,
      icone: D().IC.coracao,
      titulo,
      extra: itens.length ? `<span class="sd-rotulo">Antes do date</span>${checklist(itens, data.id)}` : "",
    });
  });

  // ===================================================================== balada
  // 3a leva (2026-10-14): "dificilmente volto de Uber - geralmente dirigindo ou de carona"
  const MODOS_VOLTA = [
    ["dirigindo", "dirigindo", I.carro],
    ["carona", "carona", I.carona],
    ["uber", "Uber", I.celular],
  ];
  const VOLTA_PADRAO = "03:00";
  function textoVolta(modo, volta) {
    if (modo === "carona") return { icone: I.carona, texto: "De carona: beleza, sem lembrete nenhum." };
    if (modo === "uber") {
      const antes = minDia(volta || VOLTA_PADRAO);
      const m = (antes - 30 + 1440) % 1440;
      const chamar = horaBr(`${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`);
      return { icone: I.celular, texto: `Te lembro às ${chamar} de chamar o Uber.` };
    }
    return { icone: I.sem_alcool, texto: "Volta dirigindo: zero álcool, combinado?" };
  }
  function voltaHTML(data) {
    const modo = MODOS_VOLTA.some(([m]) => m === data.volta_modo) ? data.volta_modo : "dirigindo";
    const i = MODOS_VOLTA.findIndex(([m]) => m === modo);
    const frase = textoVolta(modo, data.volta);
    return (
      `<div class="sd-volta" data-modo="${modo}" style="--i:${i}">` +
      `<span class="sd-rotulo">Como tu volta</span>` +
      `<div class="sd-volta-opcoes" role="radiogroup" aria-label="Como tu volta"><i class="sd-volta-pilula" aria-hidden="true"></i>` +
      MODOS_VOLTA.map(
        ([m, rot, ic], k) =>
          `<button type="button" role="radio" aria-checked="${m === modo}" class="sd-volta-op${m === modo ? " atual" : ""}" data-acao="volta" data-modo="${m}" data-k="${k}" data-tarefa="${esc(data.id)}" data-volta="${esc(data.volta || "")}">${ic}<span>${esc(rot)}</span></button>`
      ).join("") +
      `</div><p class="sd-volta-frase" aria-live="polite">${frase.icone}<span>${esc(frase.texto)}</span></p></div>`
    );
  }

  function sonoHTML(s) {
    if (!s || !numeroValido(s.min)) return "";
    const h = Math.floor(s.min / 60);
    const m = s.min % 60;
    const pouco = s.min < 6 * 60;
    return (
      `<div class="sd-sono${pouco ? " pouco" : ""}"><div class="sd-sono-topo">${I.lua}<strong>${h} h${m ? ` ${m} min` : ""} de sono</strong>` +
      `<span class="vivo-num">${esc(horaBr(s.volta))} → ${esc(horaBr(s.acordar))}</span></div>` +
      `<div class="sd-sono-barra"><i style="--sono:${Math.min(1, s.min / 480).toFixed(3)}"></i></div>` +
      `<div class="sd-sono-marcas"><span><b class="vivo-num">${esc(s.volta)}</b>volta</span><span><b class="vivo-num">${esc(s.acordar)}</b>acordar</span>` +
      `<span><b class="vivo-num">${esc(s.hora || "")}</b><em>${esc(s.compromisso || "compromisso")}</em></span></div>` +
      (pouco ? `<p class="sd-sono-aviso">${I.alerta}<span>Menos de 6 h de sono. Vale voltar mais cedo.</span></p>` : "") +
      `</div>`
    );
  }

  Cards.registrar("balada", (data, card, ctx) => {
    if (!data.titulo || !data.data) return null;
    const titulo = data.lugar || (/balada|festa/i.test(data.titulo) ? "Balada" : data.titulo);
    return pilulaSaida(data, card, ctx, {
      v: "balada",
      cor: COR_BALADA,
      icone: D().IC.lua,
      titulo,
      extra: sonoHTML(data.sono) + (data.id !== undefined ? voltaHTML(data) : ""),
    });
  });

  // ================================================================= documentos
  function rotuloDocumentos(data) {
    const t = `${data.titulo} ${data.lugar || ""}`.toLowerCase();
    if (/tabeli/.test(t)) return "Tabelionato";
    if (/cart[oó]rio/.test(t)) return "Cartório";
    if (/detran/.test(t)) return "Detran";
    if (/banco|caixa econ|ag[eê]ncia/.test(t)) return "Banco";
    return "Documentos";
  }
  // faixas do Google -> "abre 9h–17h · almoço 12h–13h"; e se a hora marcada cai fora/no almoco
  function horarioTexto(h, hora) {
    if (!h) return { ficha: "", aviso: "" };
    if (h.fechado) return { ficha: ficha(I.relogio, "fechado nesse dia", " alerta"), aviso: "O Google diz que fecha nesse dia — confere antes de ir." };
    const faixas = lista(h.faixas).filter((f) => Array.isArray(f) && f.length === 2);
    if (!faixas.length) return { ficha: "", aviso: "" };
    const abre = faixas[0][0];
    const fecha = faixas[faixas.length - 1][1];
    let txt = `abre <b class="vivo-num">${esc(horaBr(abre))}–${esc(horaBr(fecha))}</b>`;
    if (faixas.length === 2) txt += ` · almoço ${esc(horaBr(faixas[0][1]))}–${esc(horaBr(faixas[1][0]))}`;
    let aviso = "";
    const m = minDia(hora);
    if (m !== null && !faixas.some(([a, f]) => m >= minDia(a) && m < (minDia(f) || 1440))) {
      const proxima = faixas.find(([a]) => minDia(a) > m);
      aviso = proxima
        ? `Às ${horaBr(hora)} ainda tá fechado — abre ${faixas.length === 2 && proxima === faixas[1] ? "de novo " : ""}às ${horaBr(proxima[0])}.`
        : `Às ${horaBr(hora)} já fechou — fecha às ${horaBr(fecha)}.`;
    }
    return { ficha: ficha(I.relogio, txt), aviso };
  }
  const PASTA =
    '<svg class="sd-pasta" viewBox="0 0 50 42" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" aria-hidden="true"><path class="sd-pasta-fundo" d="M3 9a3 3 0 0 1 3-3h11l4 4h23a3 3 0 0 1 3 3v23a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3Z"/><path d="M3 15h44"/></svg>';
  function contaPasta(feitos, total) {
    return feitos >= total ? "tudo na pasta" : `${feitos} de ${total} na pasta`;
  }

  Cards.registrar("documentos", (data, _card, ctx) => {
    if (!data.titulo || !data.data) return null;
    const agora = (ctx && ctx.agora) || new Date();
    const itens = lista(data.lista).filter((i) => i && i.texto);
    const feitos = itens.filter((i) => i.feito).length;
    const completo = itens.length > 0 && feitos === itens.length;
    const d = Cards.parseDia(data.data);
    const carimboData = d ? `${d.getDate()}·${MESES[d.getMonth()]}` : "";
    const horario = horarioTexto(data.horario, data.hora);
    const fichas = [horario.ficha, data.lugar ? ficha(I.pin, esc(data.lugar)) : ""].filter(Boolean);
    return (
      `<div class="sd sd-documentos">` +
      olho(I.pasta, rotuloDocumentos(data), `<span class="sd-quando vivo-num">${esc(quandoDia(data.data, agora))}${data.hora ? ` · ${esc(data.hora)}` : ""}</span>`) +
      `<div class="sd-pasta-topo" data-compromisso="${esc(data.id)}">${PASTA}<div><h3 class="sd-hero">${esc(data.titulo)}</h3>` +
      (itens.length ? `<span class="sd-conta-pasta" data-total="${itens.length}">${esc(contaPasta(feitos, itens.length))}</span>` : "") +
      `</div></div>` +
      (itens.length
        ? `<div class="sd-carimbo-area">${checklist(itens, data.id)}<div class="sd-carimbo${completo ? " bateu" : ""}" aria-hidden="true">Pasta<br>pronta<small>${esc(carimboData)}</small></div></div>`
        : "") +
      (fichas.length ? `<div class="sd-fichas">${fichas.join("")}</div>` : "") +
      (horario.aviso ? `<p class="sd-status alerta">${I.alerta}<span>${esc(horario.aviso)}</span></p>` : "") +
      `</div>`
    );
  });

  // =================================================================== presente
  const CAIXA =
    '<svg class="sd-caixa" viewBox="0 0 64 64" aria-hidden="true"><g><path class="sd-brilho" d="M50 8l1.5 4 4 1.5-4 1.5L50 19l-1.5-4-4-1.5 4-1.5z"/><path class="sd-brilho" d="M14 6l1 2.6 2.6 1-2.6 1L14 13l-1-2.4-2.6-1 2.6-1z"/><path class="sd-brilho" d="M58 26l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z"/></g>' +
    '<rect class="sd-caixa-base" x="11" y="31" width="42" height="27" rx="4"/><rect class="sd-fita" x="29" y="31" width="6" height="27"/>' +
    '<g class="sd-tampa"><rect class="sd-caixa-base" x="8" y="22" width="48" height="10" rx="3"/><rect class="sd-fita" x="29" y="22" width="6" height="10"/><path class="sd-laco" d="M32 22c-5-9-14-7-10-1M32 22c5-9 14-7 10-1"/></g></svg>';
  const diaMes = (iso) => {
    const d = Cards.parseDia(iso);
    return d ? `${d.getDate()} ${MESES[d.getMonth()]}` : "";
  };
  function textoEscolha(ideia, compraAte, agora) {
    const d = Cards.parseDia(compraAte);
    const delta = d ? Cards.diasEntre(agora || new Date(), d) : null;
    const quando = delta === null ? "" : delta <= 0 ? "hoje" : delta === 1 ? "amanhã" : `dia ${d.getDate()}`;
    const loja = delta !== null && delta <= 0 ? " — em loja, que pela internet não chega" : "";
    return `Guardei: <b>${esc(ideia)}</b>. Te lembro ${quando} de comprar${loja}.`;
  }

  Cards.registrar("presente", (data, _card, ctx) => {
    if (!data.titulo || !data.data) return null;
    const agora = (ctx && ctx.agora) || new Date();
    const fim = Cards.parseDia(data.data);
    const compra = Cards.parseDia(data.compra_ate);
    const dias = fim ? Math.max(0, Cards.diasEntre(agora, fim)) : null;
    const ideias = lista(data.ideias).filter((i) => i && i.titulo);
    const escolha = Number.isInteger(data.escolha) && ideias[data.escolha] ? data.escolha : null;
    const contagem =
      dias === null
        ? ""
        : dias === 0
          ? `<div class="sd-contagem">hoje<small>${esc(data.titulo)}</small></div>`
          : `<div class="sd-contagem"><span class="vivo-num">${dias}</span><small>${dias === 1 ? "dia" : "dias"} · ${esc(data.titulo)}</small></div>`;
    // linha hoje -> comprar ate -> a data; sem margem pra entrega = aviso em vez do marco
    let prazos = "";
    let aviso = "";
    let prazoTexto = "";
    if (fim && dias > 0) {
      const ateCompra = compra ? Math.max(0, Cards.diasEntre(agora, compra)) : 0;
      const pct = Math.max(0, Math.min(100, (ateCompra / dias) * 100));
      // colado no "hoje" ou no fim o rotulo encavala - ai o prazo vai pra frase de baixo
      const marcoLimite = ateCompra > 0 && pct >= 20 && pct <= 78;
      if (ateCompra > 0 && !marcoLimite) prazoTexto = `Comprar até dia ${compra.getDate()} pra entrega chegar a tempo.`;
      prazos =
        `<div class="sd-prazos" style="--ate:${(pct / 100).toFixed(3)}"><div class="sd-linha-p"><i></i></div>` +
        `<div class="sd-marco agora"><i></i><b>hoje</b></div>` +
        (marcoLimite ? `<div class="sd-marco limite" style="left:${pct.toFixed(1)}%"><i></i><b class="vivo-num">${esc(compra.getDate())}</b>comprar até</div>` : "") +
        `<div class="sd-marco fim"><i></i><b class="vivo-num">${esc(fim.getDate())}</b>${esc(dias === 1 ? "amanhã" : "o dia")}</div></div>`;
      if (!ateCompra) aviso = "Pela internet não chega mais a tempo — melhor comprar em loja.";
    }
    const temPorque = ideias.some((i) => i.porque);
    const botoes = ideias
      .map(
        (it, i) =>
          `<button type="button" class="sd-ideia${escolha === i ? " escolhida" : ""}" data-acao="presente_ideia" data-tarefa="${esc(data.id)}" data-i="${i}" aria-pressed="${escolha === i}" style="--k:${i}">` +
          `<b>${esc(it.titulo)}</b>${it.porque ? `<small>${esc(it.porque)}</small>` : ""}` +
          (numeroValido(it.preco) ? `<span class="sd-preco vivo-num">~R$&nbsp;${esc(Math.round(it.preco))}</span>` : "") +
          `</button>`
      )
      .join("");
    const status =
      escolha !== null
        ? `<p class="sd-status ok">${I.ok}<span>${textoEscolha(ideias[escolha].titulo, data.compra_ate, agora)}</span></p>`
        : aviso
          ? `<p class="sd-status alerta">${I.alerta}<span>${esc(aviso)}</span></p>`
          : prazoTexto
            ? `<p class="sd-status">${I.relogio}<span>${esc(prazoTexto)}</span></p>`
            : `<p class="sd-status"></p>`;
    return (
      `<div class="sd sd-presente">` +
      olho(I.presente, "Presente", `${data.anual ? `<span class="sd-anual">${I.repete}todo ano</span>` : ""}<span class="sd-quando">${esc(quandoDia(data.data, agora))}${fim && Cards.diasEntre(agora, fim) > 1 && Cards.diasEntre(agora, fim) < 7 ? `, ${esc(diaMes(data.data))}` : ""}</span>`) +
      `<div class="sd-presente-topo" data-compromisso="${esc(data.id)}">${CAIXA}<div class="sd-presente-cab">${contagem}` +
      (data.ano_passado ? `<p class="sd-ano-passado">Ano passado: <b>${esc(data.ano_passado)}</b></p>` : "") +
      `</div></div>` +
      prazos +
      (ideias.length
        ? `<span class="sd-rotulo">${temPorque ? "Do que tu já me contou" : "Ideias"}</span><div class="sd-ideias${escolha !== null ? " escolheu" : ""}">${botoes}</div>`
        : "") +
      status +
      `</div>`
    );
  });

  // ============================================================== interacoes
  const vibrar = (ms) => typeof raiz.vibrar === "function" && raiz.vibrar(ms);
  const animaUmaVez = (el, classe) => {
    if (!el) return;
    el.classList.remove(classe);
    void el.offsetWidth;
    el.classList.add(classe);
  };

  // pasta/carimbo/contador do card de documentos a partir das caixinhas marcadas
  function atualizarPasta(cardEl, recebeu) {
    const conta = cardEl.querySelector(".sd-conta-pasta");
    if (!conta) return;
    const total = +conta.dataset.total || 0;
    const feitos = cardEl.querySelectorAll(".sd-check li.marcado").length;
    conta.textContent = contaPasta(feitos, total);
    if (recebeu) animaUmaVez(cardEl.querySelector(".sd-pasta"), "recebeu");
    const carimbo = cardEl.querySelector(".sd-carimbo");
    if (!carimbo) return;
    const completo = total > 0 && feitos === total;
    if (completo && !carimbo.classList.contains("bateu")) {
      carimbo.classList.add("bateu", "batendo");
      animaUmaVez(cardEl, "sd-tremeu");
      vibrar([10, 40, 18]);
    } else if (!completo) {
      carimbo.classList.remove("bateu", "batendo");
    }
  }

  function marcarItem(li, feito) {
    li.classList.toggle("marcado", feito);
    const b = li.querySelector("[data-acao]");
    if (b) b.setAttribute("aria-pressed", String(feito));
  }

  if (typeof Cards.registrarAcao === "function") {
    Cards.registrarAcao("lista_item", async (btn, cardEl, deps) => {
      if (typeof deps.apiFetch !== "function" || btn.dataset.enviando) return;
      const li = btn.closest("li");
      const feito = !li.classList.contains("marcado");
      marcarItem(li, feito); // otimista: o toque responde na hora
      if (feito) animaUmaVez(li, "voou");
      atualizarPasta(cardEl, feito);
      vibrar(8);
      btn.dataset.enviando = "1";
      const res = await deps.apiFetch(`/api/tasks/${encodeURIComponent(btn.dataset.tarefa)}/lista`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ i: +btn.dataset.i, feito }),
      });
      delete btn.dataset.enviando;
      if (!res || !res.ok) {
        marcarItem(li, !feito);
        atualizarPasta(cardEl, false);
      }
    });

    Cards.registrarAcao("presente_ideia", async (btn, cardEl, deps) => {
      if (typeof deps.apiFetch !== "function" || btn.disabled) return;
      const caixa = btn.closest(".sd-ideias");
      caixa.querySelectorAll(".sd-ideia").forEach((b) => (b.disabled = true));
      const res = await deps.apiFetch(`/api/tasks/${encodeURIComponent(btn.dataset.tarefa)}/presente`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ i: +btn.dataset.i }),
      });
      caixa.querySelectorAll(".sd-ideia").forEach((b) => (b.disabled = false));
      if (!res || !res.ok) return;
      caixa.classList.add("escolheu");
      caixa.querySelectorAll(".sd-ideia").forEach((b) => {
        b.classList.toggle("escolhida", b === btn);
        b.setAttribute("aria-pressed", String(b === btn));
      });
      const status = cardEl.querySelector(".sd-status");
      if (status) {
        status.className = "sd-status ok";
        status.innerHTML = `${I.ok}<span class="sd-troca">${textoEscolha(btn.querySelector("b").textContent, res.compra_ate)}</span>`;
      }
      animaUmaVez(cardEl.querySelector(".sd-caixa"), "pulou");
      vibrar(12);
      if (typeof deps.aoMudar === "function") deps.aoMudar();
    });

    Cards.registrarAcao("volta", async (btn, _cardEl, deps) => {
      const caixa = btn.closest(".sd-volta");
      if (typeof deps.apiFetch !== "function" || !caixa || caixa.dataset.enviando) return;
      const antes = caixa.dataset.modo;
      const modo = btn.dataset.modo;
      if (modo === antes) return;
      aplicarVolta(caixa, modo, true); // otimista: a pilula ja desliza
      vibrar(8);
      caixa.dataset.enviando = "1";
      const res = await deps.apiFetch(`/api/tasks/${encodeURIComponent(btn.dataset.tarefa)}/volta`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ modo }),
      });
      delete caixa.dataset.enviando;
      if (!res || !res.ok) aplicarVolta(caixa, antes, true);
      else if (typeof deps.aoMudar === "function") deps.aoMudar();
    });
  }

  function aplicarVolta(caixa, modo, trocarFrase) {
    const k = MODOS_VOLTA.findIndex(([m]) => m === modo);
    if (k < 0) return;
    caixa.dataset.modo = modo;
    caixa.style.setProperty("--i", k);
    caixa.querySelectorAll(".sd-volta-op").forEach((b) => {
      const sim = b.dataset.modo === modo;
      b.classList.toggle("atual", sim);
      b.setAttribute("aria-checked", String(sim));
    });
    const frase = caixa.querySelector(".sd-volta-frase");
    const op = caixa.querySelector(".sd-volta-op");
    if (frase && trocarFrase) {
      const t = textoVolta(modo, op && op.dataset.volta);
      frase.innerHTML = `${t.icone}<span class="sd-troca">${esc(t.texto)}</span>`;
    }
  }

  // Historico: o card e a foto do momento da resposta - o que foi marcado/escolhido depois vem
  // de /api/tasks/estado (chat.js chama com os ids de [data-compromisso]).
  function aplicarEstado(raizEl, id, estado) {
    if (!raizEl || !estado) return;
    raizEl.querySelectorAll(`[data-compromisso="${CSS.escape(String(id))}"]`).forEach((ancora) => {
      const cardEl = ancora.closest(".card-contrato");
      if (!cardEl) return;
      const itens = cardEl.querySelectorAll(".sd-check li");
      lista(estado.lista).forEach((feito, i) => itens[i] && marcarItem(itens[i], !!feito));
      atualizarPasta(cardEl, false);
      const caixa = cardEl.querySelector(".sd-ideias");
      if (caixa && Number.isInteger(estado.escolha)) {
        caixa.classList.add("escolheu");
        caixa.querySelectorAll(".sd-ideia").forEach((b, i) => {
          b.classList.toggle("escolhida", i === estado.escolha);
          b.setAttribute("aria-pressed", String(i === estado.escolha));
        });
      }
      const volta = cardEl.querySelector(".sd-volta");
      if (volta && estado.volta_modo && volta.dataset.modo !== estado.volta_modo) aplicarVolta(volta, estado.volta_modo, true);
    });
  }

  const CardsSaidas = { aplicarEstado, horarioTexto, textoVolta };
  raiz.CardsSaidas = CardsSaidas;
  if (typeof module !== "undefined" && module.exports) module.exports = CardsSaidas;
})(typeof window !== "undefined" ? window : globalThis);
