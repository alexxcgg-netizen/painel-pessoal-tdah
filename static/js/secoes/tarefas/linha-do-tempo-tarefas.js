// static/js/secoes/tarefas/linha-do-tempo-tarefas.js - a aba Tarefas nova (leva 06/11, frente 6 de
// docs/briefings/2026-11-06-painel-esperto.md; prototipo aprovado: cena "Tarefas" do artefato
// https://claude.ai/artifact/WXSEtwp14Y1UwGEc86TYTX).
//
// Este arquivo tem:
//  - a parte PURA (roda em Node, tests/js/tarefas_linha_do_tempo.test.js): em que grupo cada tarefa
//    cai (Atrasadas / Manha / Tarde / Noite / Sem hora / Amanha / proximos dias / Sem data), o texto
//    da linha (hora a direita + a linha cinza de baixo), a conta da regua do dia (7h-23h, posicao,
//    arredondar de 15 em 15 min, faixa de chuva) e os chips de dia da folha;
//  - a REGUA DO DIA (DOM): bolinha por tarefa de hoje com hora (coral; saida/compromisso em rosa),
//    linha vermelha do agora, faixa listrada azul onde a previsao (/api/clima/hoje, a mesma do chip
//    de clima do Inicio) diz chuva; arrastar a bolinha muda a hora de 15 em 15 min (setas tambem -
//    role="slider"), com Desfazer;
//  - entrarAbaTarefas (nucleo/navegacao.js chama ao abrir a aba): relogio de 30 s do "agora" e a
//    previsao de chuva.
// A lista em si (criarItemTarefa, montarListaTarefas) mora em tarefas.js e a folha de acoes em
// folha-tarefa.js. Script classico (escopo global compartilhado).

const TL_DIAS_SEMANA = ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"];
const TL_DIAS_CURTOS = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
const TL_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
const TL_MESES_CURTOS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

const REGUA_INICIO = 7 * 60;
const REGUA_FIM = 23 * 60;
const REGUA_PASSO = 15;
const REGUA_ULTIMO = 23 * 60 + 45; // a ultima hora que da pra marcar arrastando

const _maiuscula = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);

function tlIsoDe(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function tlDataDe(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
  return m ? new Date(+m[1], +m[2] - 1, +m[3], 12) : null;
}

function tlMinutos(hora) {
  const m = /^(\d{1,2}):(\d{2})/.exec(hora || "");
  return m ? +m[1] * 60 + +m[2] : null;
}

function tlHora(min) {
  return `${String(Math.floor(min / 60)).padStart(2, "0")}:${String(min % 60).padStart(2, "0")}`;
}

function tlMaisDias(hoje, n) {
  return new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate() + n, 12);
}

// 40 -> "40 min", 130 -> "2h10", 180 -> "3h"
function tlDuracao(min) {
  const n = Math.max(0, Math.round(min));
  if (n < 60) return `${n} min`;
  const h = Math.floor(n / 60);
  const r = n % 60;
  return r ? `${h}h${String(r).padStart(2, "0")}` : `${h}h`;
}

// "ontem" / "seg 12" - quando era uma atrasada
function rotuloAtraso(dueIso, hoje) {
  const d = tlDataDe(dueIso);
  if (!d) return "";
  const dias = Math.round((new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate(), 12) - d) / 86400000);
  if (dias === 1) return "ontem";
  return `${TL_DIAS_CURTOS[d.getDay()]} ${d.getDate()}`;
}

// "sexta, 7 de novembro" (embaixo do "Hoje")
function rotuloDiaLongo(d) {
  return `${TL_DIAS_SEMANA[d.getDay()]}, ${d.getDate()} de ${TL_MESES[d.getMonth()]}`;
}

// Saida/compromisso (bolinha rosa na regua, "chuva na saida"): tarefa com lugar, date ou balada.
function ehSaida(t) {
  return Boolean(t && ((t.local && String(t.local).trim()) || t.estilo === "date" || t.estilo === "balada"));
}

// Grupo da lista. Hoje se divide pela hora (manha < 12h, tarde < 18h, noite); depois de amanha, um
// grupo por dia. `ordem` so serve pra teste/depuracao - a lista ja vem na ordem do servidor.
function grupoDaTarefa(t, hoje) {
  const hojeIso = tlIsoDe(hoje);
  const amanhaIso = tlIsoDe(tlMaisDias(hoje, 1));
  const d = t && t.due_date;
  if (!d) return { chave: "sem-data", rotulo: "Sem data" };
  if (d < hojeIso) return { chave: "atrasadas", rotulo: "Atrasadas", alerta: true };
  if (d === hojeIso) {
    const min = tlMinutos(t.hora);
    if (min === null) return { chave: "sem-hora", rotulo: "Sem hora", hoje: true };
    if (min < 12 * 60) return { chave: "manha", rotulo: "Manhã", hoje: true };
    if (min < 18 * 60) return { chave: "tarde", rotulo: "Tarde", hoje: true };
    return { chave: "noite", rotulo: "Noite", hoje: true };
  }
  if (d === amanhaIso) return { chave: "amanha", rotulo: "Amanhã" };
  const data = tlDataDe(d);
  if (!data) return { chave: d, rotulo: d };
  return { chave: d, rotulo: `${_maiuscula(TL_DIAS_SEMANA[data.getDay()])}, ${data.getDate()} ${TL_MESES_CURTOS[data.getMonth()]}` };
}

// O texto de uma linha da lista: hora a direita (coral nas de hoje) e as partes da linha de baixo
// (juntadas com " · "). `chuva` = faixa de chuva de hoje ({de, ate} em minutos) ou null.
function linhaDaTarefa(t, agora, chuva) {
  const hojeIso = tlIsoDe(agora);
  const agoraMin = agora.getHours() * 60 + agora.getMinutes();
  const min = tlMinutos(t.hora);
  const partes = [];
  let hora = min !== null ? tlHora(min) : "";
  let horaClasse = "";
  let chuvaTxt = "";
  if (t.due_date && t.due_date < hojeIso) {
    partes.push(`era pra ${rotuloAtraso(t.due_date, agora)}${hora ? ` às ${hora}` : ""}`);
    hora = "";
  } else if (t.due_date === hojeIso && min !== null) {
    horaClasse = "cor";
    if (min < agoraMin) partes.push(`passou há ${tlDuracao(agoraMin - min)}`);
    else if (min - agoraMin <= 180) partes.push(min === agoraMin ? "agora" : `em ${tlDuracao(min - agoraMin)}`);
    if (chuva && min >= chuva.de && min < chuva.ate) chuvaTxt = ehSaida(t) ? "chuva na saída" : "chuva nessa hora";
  }
  if (t.local && String(t.local).trim()) partes.push(String(t.local).trim());
  if (!t.due_date && t.due_at) partes.push(String(t.due_at));
  if (t.recorrente_origem_id) partes.push("rotina");
  const passos = Array.isArray(t.subtasks) ? t.subtasks : [];
  if (passos.length) partes.push(`${passos.filter((s) => s.completed_at).length} de ${passos.length} passos`);
  if (t.empacada_dias) partes.push(`travada há ${t.empacada_dias} ${t.empacada_dias === 1 ? "dia" : "dias"}`);
  if (t.inegociavel) partes.push("não pode falhar");
  try {
    const pacote = t.extras ? JSON.parse(t.extras).pacote : null;
    if (pacote && pacote.premio) partes.push(`prêmio: ${pacote.premio}`);
  } catch (erro) {
    /* extras malformado: sem o premio, a linha segue normal */
  }
  return { hora, horaClasse, partes, chuva: chuvaTxt };
}

// Faixa da regua: 7h-23h, esticada (de hora em hora) se tiver tarefa de hoje fora disso.
function faixaDaRegua(minutos) {
  let ini = REGUA_INICIO;
  let fim = REGUA_FIM;
  (minutos || []).forEach((m) => {
    if (typeof m !== "number" || !Number.isFinite(m)) return;
    if (m < ini) ini = Math.max(0, Math.floor(m / 60) * 60);
    if (m + REGUA_PASSO > fim) fim = Math.min(24 * 60, Math.ceil((m + REGUA_PASSO) / 60) * 60);
  });
  return { ini, fim };
}

// minuto -> % da largura (0-100)
function posicaoNaRegua(min, ini, fim) {
  if (fim <= ini) return 0;
  return Math.max(0, Math.min(100, ((min - ini) / (fim - ini)) * 100));
}

function _limitarNaRegua(min, ini, fim) {
  return Math.max(ini, Math.min(Math.min(fim, REGUA_ULTIMO), min));
}

// x do ponteiro (px a partir da esquerda do trilho) -> minuto, de 15 em 15
function minutoDoPonto(x, largura, ini, fim) {
  if (!(largura > 0)) return ini;
  const bruto = ini + (x / largura) * (fim - ini);
  return _limitarNaRegua(Math.round(bruto / REGUA_PASSO) * REGUA_PASSO, ini, fim);
}

// setas do teclado: anda 15 min (encaixando na grade de 15 se a hora era quebrada, ex. 16:20)
function passoNaRegua(min, sentido, ini, fim) {
  const base = sentido > 0 ? Math.floor(min / REGUA_PASSO) * REGUA_PASSO : Math.ceil(min / REGUA_PASSO) * REGUA_PASSO;
  return _limitarNaRegua(base + sentido * REGUA_PASSO, ini, fim);
}

// "7h", "10h"... de 3 em 3 horas a partir do comeco
function rotulosDaRegua(ini, fim) {
  const lista = [];
  for (let m = Math.ceil(ini / 60) * 60; m <= fim; m += 180) lista.push({ min: m, texto: `${m / 60}h` });
  return lista;
}

// /api/clima/hoje ({alerta, hora_inicio, hora_fim, chuva_pct_max}) -> {de, ate, pct} dentro da regua
function faixaDeChuva(clima, ini, fim) {
  if (!clima || !clima.alerta) return null;
  const hi = Number(clima.hora_inicio);
  const hf = Number(clima.hora_fim);
  if (!Number.isFinite(hi) || !Number.isFinite(hf)) return null;
  const de = Math.max(ini, hi * 60);
  const ate = Math.min(fim, hf * 60);
  if (ate <= de) return null;
  const pct = Number(clima.chuva_pct_max);
  return { de, ate, pct: Number.isFinite(pct) ? Math.round(pct) : null };
}

// Rotulos das bolinhas que encostariam um no outro: so o primeiro aparece (a hora continua no
// aria-valuetext e na lista). `pcts` em ordem; `minDist` em %.
function rotulosVisiveis(pcts, minDist) {
  let ultimo = -Infinity;
  return pcts.map((p) => {
    if (p - ultimo < minDist) return false;
    ultimo = p;
    return true;
  });
}

// Hora da folha: +30 min / +1 h em cima da hora da tarefa (ou de agora, arredondado pra cima de 15
// em 15, se ela nao tem hora). Passou da meia-noite = null (o chip fica desligado).
function horaSomada(hora, delta, agora) {
  let base = tlMinutos(hora);
  if (base === null) base = Math.ceil((agora.getHours() * 60 + agora.getMinutes()) / REGUA_PASSO) * REGUA_PASSO;
  const novo = base + delta;
  return novo >= 0 && novo < 24 * 60 ? tlHora(novo) : null;
}

// Chips de dia da folha: Hoje, Amanha e os 3 dias seguintes pelo nome ("Domingo").
function diasDaFolha(hoje) {
  const lista = [
    { iso: tlIsoDe(hoje), rotulo: "Hoje" },
    { iso: tlIsoDe(tlMaisDias(hoje, 1)), rotulo: "Amanhã" },
  ];
  for (let n = 2; n <= 4; n++) {
    const d = tlMaisDias(hoje, n);
    lista.push({ iso: tlIsoDe(d), rotulo: _maiuscula(TL_DIAS_SEMANA[d.getDay()]) });
  }
  return lista;
}

// "pra amanhã" / "pra sexta, 14 nov" (toast)
function rotuloDestino(iso, hoje) {
  if (iso === tlIsoDe(hoje)) return "pra hoje";
  if (iso === tlIsoDe(tlMaisDias(hoje, 1))) return "pra amanhã";
  const d = tlDataDe(iso);
  if (!d) return `pra ${iso}`;
  return `pra ${TL_DIAS_SEMANA[d.getDay()]}, ${d.getDate()} ${TL_MESES_CURTOS[d.getMonth()]}`;
}

// Frase de cima: "5 tarefas hoje, 3 com hora. Chuva das 17h às 20h."
function resumoDoDia(tarefas, hoje, chuva) {
  const hojeIso = tlIsoDe(hoje);
  const deHoje = (tarefas || []).filter((t) => t.due_date === hojeIso);
  const atrasadas = (tarefas || []).filter((t) => t.due_date && t.due_date < hojeIso).length;
  const comHora = deHoje.filter((t) => tlMinutos(t.hora) !== null).length;
  let frase;
  if (!deHoje.length) frase = "Nada marcado pra hoje.";
  else {
    frase = `${deHoje.length} ${deHoje.length === 1 ? "tarefa" : "tarefas"} hoje`;
    frase += comHora ? `, ${comHora} com hora.` : ", nenhuma com hora.";
  }
  if (atrasadas) frase += ` ${atrasadas} ${atrasadas === 1 ? "atrasada" : "atrasadas"}.`;
  if (chuva) frase += ` Chuva das ${Math.floor(chuva.de / 60)}h às ${chuva.ate >= 24 * 60 ? "meia-noite" : `${Math.floor(chuva.ate / 60)}h`}.`;
  return frase;
}

// ---- DOM (so navegador) ------------------------------------------------------------------

let _tlRelogio = null;
let _climaRegua = null; // ultima resposta de /api/clima/hoje
let _climaReguaEm = 0;
let _climaReguaBuscando = null;

function _tlMenosMovimento() {
  return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// Previsao de chuva de hoje - a mesma que o chip de clima do Inicio ja busca; aqui no maximo uma vez
// a cada 20 min. Sem cidade/sem rede = sem faixa (nunca inventa).
function _buscarChuvaRegua() {
  if (_climaReguaBuscando || Date.now() - _climaReguaEm < 20 * 60 * 1000) return _climaReguaBuscando;
  _climaReguaBuscando = (async () => {
    try {
      const r = await fetch("/api/clima/hoje", { credentials: "same-origin" });
      const dados = r.ok ? await r.json() : null;
      _climaRegua = dados && dados.configurado && !dados.erro ? dados : null;
    } catch (erro) {
      _climaRegua = null;
    }
    _climaReguaEm = Date.now();
    _climaReguaBuscando = null;
    if (typeof atualizarAgoraTarefas === "function") atualizarAgoraTarefas();
  })();
  return _climaReguaBuscando;
}

// Faixa de chuva de hoje na escala da regua atual (tarefas.js usa pra "chuva na saida").
function chuvaDeHoje() {
  const hoje = new Date();
  const minutos = _tarefasDeHojeComHora(hoje).map((t) => tlMinutos(t.hora));
  const { ini, fim } = faixaDaRegua(minutos);
  return faixaDeChuva(_climaRegua, ini, fim);
}

function _tarefasDeHojeComHora(hoje) {
  const hojeIso = tlIsoDe(hoje);
  const todas = typeof _tarefasPendentes !== "undefined" ? _tarefasPendentes : [];
  return todas
    .filter((t) => t.due_date === hojeIso && tlMinutos(t.hora) !== null && !t._saindo)
    .sort((a, b) => tlMinutos(a.hora) - tlMinutos(b.hora));
}

function renderReguaTarefas() {
  const regua = typeof document !== "undefined" && document.getElementById("tt-regua");
  if (!regua) return;
  const trilho = document.getElementById("tt-regua-trilho");
  if (regua.dataset.arrastando) return; // nao redesenha embaixo do dedo
  const agora = new Date();
  const tarefas = _tarefasDeHojeComHora(agora);
  const { ini, fim } = faixaDaRegua(tarefas.map((t) => tlMinutos(t.hora)));
  regua._faixa = { ini, fim };

  // horas embaixo
  const horas = document.getElementById("tt-regua-horas");
  horas.replaceChildren(
    ...rotulosDaRegua(ini, fim).map((r) => {
      const s = document.createElement("span");
      const p = posicaoNaRegua(r.min, ini, fim);
      s.style.left = `${p}%`;
      if (p <= 0) s.classList.add("ponta-ini");
      else if (p >= 100) s.classList.add("ponta-fim");
      s.textContent = r.texto;
      return s;
    })
  );

  // agora
  const agoraMin = agora.getHours() * 60 + agora.getMinutes();
  const linhaAgora = document.getElementById("tt-regua-agora");
  linhaAgora.hidden = agoraMin < ini || agoraMin > fim;
  linhaAgora.style.left = `${posicaoNaRegua(agoraMin, ini, fim)}%`;

  // chuva
  const chuva = faixaDeChuva(_climaRegua, ini, fim);
  const faixa = document.getElementById("tt-regua-chuva");
  faixa.hidden = !chuva;
  if (chuva) {
    faixa.style.left = `${posicaoNaRegua(chuva.de, ini, fim)}%`;
    faixa.style.width = `${posicaoNaRegua(chuva.ate, ini, fim) - posicaoNaRegua(chuva.de, ini, fim)}%`;
    faixa.querySelector("i").textContent = chuva.pct ? `chuva ${chuva.pct}%` : "chuva";
  }

  // bolinhas: reaproveita a de quem ja estava (o foco do teclado nao se perde)
  const velhas = new Map(Array.from(trilho.querySelectorAll(".tt-marco")).map((m) => [m.dataset.id, m]));
  const largura = trilho.getBoundingClientRect().width || 320;
  const pcts = tarefas.map((t) => posicaoNaRegua(tlMinutos(t.hora), ini, fim));
  const comRotulo = rotulosVisiveis(pcts, (46 / largura) * 100);
  tarefas.forEach((t, i) => {
    const id = String(t.id);
    let m = velhas.get(id);
    velhas.delete(id);
    if (!m) {
      m = document.createElement("div");
      m.className = "tt-marco";
      m.dataset.id = id;
      m.tabIndex = 0;
      m.setAttribute("role", "slider");
      m.innerHTML = "<span></span>";
      _ligarArrastoMarco(m);
      trilho.appendChild(m);
    }
    const min = tlMinutos(t.hora);
    m.classList.toggle("saida", ehSaida(t));
    m.classList.toggle("sem-rotulo", !comRotulo[i]);
    m.style.left = `${pcts[i]}%`;
    m.setAttribute("aria-label", `${t.title}, hora`);
    m.setAttribute("aria-valuemin", String(ini));
    m.setAttribute("aria-valuemax", String(Math.min(fim, REGUA_ULTIMO)));
    m.setAttribute("aria-valuenow", String(min));
    m.setAttribute("aria-valuetext", tlHora(min));
    m.querySelector("span").textContent = tlHora(min);
  });
  velhas.forEach((m) => m.remove());

  const dica = document.getElementById("tt-regua-dica");
  if (dica) dica.textContent = tarefas.length ? "Arrasta uma bolinha pra mudar a hora." : "Nada com hora hoje.";
  regua.hidden = false;
}

function _tarefaDoMarco(m) {
  const todas = typeof _tarefasPendentes !== "undefined" ? _tarefasPendentes : [];
  return todas.find((t) => String(t.id) === m.dataset.id) || null;
}

function _pintarMarco(m, min) {
  const regua = document.getElementById("tt-regua");
  const { ini, fim } = regua._faixa || { ini: REGUA_INICIO, fim: REGUA_FIM };
  m.style.left = `${posicaoNaRegua(min, ini, fim)}%`;
  m.querySelector("span").textContent = tlHora(min);
  m.setAttribute("aria-valuenow", String(min));
  m.setAttribute("aria-valuetext", tlHora(min));
}

function _ligarArrastoMarco(m) {
  let antes = null; // minuto de quando o dedo encostou
  let atual = null;
  let idPonteiro = null;
  const regua = () => document.getElementById("tt-regua");

  m.addEventListener("pointerdown", (ev) => {
    if (ev.pointerType === "mouse" && ev.button !== 0) return;
    const t = _tarefaDoMarco(m);
    if (!t) return;
    antes = tlMinutos(t.hora);
    atual = antes;
    idPonteiro = ev.pointerId;
    try {
      m.setPointerCapture(ev.pointerId);
    } catch (erro) {
      /* sem captura o arrasto ainda funciona com o dedo em cima */
    }
    m.classList.add("arrastando");
    regua().dataset.arrastando = "1";
    ev.preventDefault();
  });
  m.addEventListener("pointermove", (ev) => {
    if (antes === null || ev.pointerId !== idPonteiro) return;
    const trilho = document.getElementById("tt-regua-trilho");
    const r = trilho.getBoundingClientRect();
    const { ini, fim } = regua()._faixa || { ini: REGUA_INICIO, fim: REGUA_FIM };
    const min = minutoDoPonto(ev.clientX - r.left, r.width, ini, fim);
    if (min === atual) return;
    atual = min;
    _pintarMarco(m, min);
    if (typeof vibrar === "function") vibrar(6);
  });
  const soltar = (ev, cancelou) => {
    if (antes === null || (ev && ev.pointerId !== idPonteiro)) return;
    const de = antes;
    const para = cancelou ? antes : atual;
    antes = null;
    idPonteiro = null;
    m.classList.remove("arrastando");
    delete regua().dataset.arrastando;
    if (para === de) {
      _pintarMarco(m, de);
      return;
    }
    const t = _tarefaDoMarco(m);
    if (t && typeof moverTarefaDaAba === "function") moverTarefaDaAba(t, { hora: tlHora(para) }, `${t.title}: ${tlHora(de)} → ${tlHora(para)}`);
  };
  m.addEventListener("pointerup", (ev) => soltar(ev, false));
  m.addEventListener("pointercancel", (ev) => soltar(ev, true));
  m.addEventListener("lostpointercapture", (ev) => soltar(ev, false));

  // teclado: setas andam 15 min; cada toque grava (com Desfazer), igual ao prototipo
  m.addEventListener("keydown", (ev) => {
    const sentido = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1 }[ev.key];
    if (!sentido) return;
    ev.preventDefault();
    const t = _tarefaDoMarco(m);
    if (!t) return;
    const { ini, fim } = regua()._faixa || { ini: REGUA_INICIO, fim: REGUA_FIM };
    const de = tlMinutos(t.hora);
    const para = passoNaRegua(de, sentido, ini, fim);
    if (para === de) return;
    _pintarMarco(m, para);
    if (typeof moverTarefaDaAba === "function") moverTarefaDaAba(t, { hora: tlHora(para) }, `${t.title}: ${tlHora(de)} → ${tlHora(para)}`);
  });
}

// Cabecalho do dia + regua + o texto vivo das linhas ("em 40 min", "passou ha...") - chamado a cada
// montagem da lista e no relogio de 30 s.
function atualizarAgoraTarefas() {
  if (typeof document === "undefined") return;
  const agora = new Date();
  const cab = document.getElementById("tt-cab-dia-data");
  if (cab) cab.textContent = rotuloDiaLongo(agora);
  const resumo = document.getElementById("tt-resumo-dia");
  if (resumo) resumo.textContent = resumoDoDia(typeof _tarefasPendentes !== "undefined" ? _tarefasPendentes : [], agora, chuvaDeHoje());
  renderReguaTarefas();
  if (typeof atualizarLinhasTarefas === "function") atualizarLinhasTarefas();
}

// Abrir a aba: previsao de chuva (cache de 20 min) + relogio do agora, que so roda com a aba aberta.
function entrarAbaTarefas() {
  if (typeof document === "undefined") return;
  _buscarChuvaRegua();
  atualizarAgoraTarefas();
  if (!_tlRelogio) {
    _tlRelogio = setInterval(() => {
      const aba = document.getElementById("tab-tarefas");
      if (document.hidden || !aba || aba.hidden) return;
      _buscarChuvaRegua();
      atualizarAgoraTarefas();
    }, 30000);
  }
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    grupoDaTarefa,
    linhaDaTarefa,
    rotuloAtraso,
    rotuloDiaLongo,
    rotuloDestino,
    tlDuracao,
    tlMinutos,
    tlHora,
    ehSaida,
    faixaDaRegua,
    posicaoNaRegua,
    minutoDoPonto,
    passoNaRegua,
    rotulosDaRegua,
    faixaDeChuva,
    rotulosVisiveis,
    horaSomada,
    diasDaFolha,
    resumoDoDia,
  };
}
