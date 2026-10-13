// static/js/secoes/tarefas/linha-do-tempo-tarefas.js - a aba Tarefas como LINHA DO TEMPO (2026-10-13).
// Prototipo escolhido pelo Alex ("linha do tempo eu gostei mais"):
// https://claude.ai/artifact/V1bNK612xPzqBVXmuX1Guq
//
// A ordem ja vem certa do servidor (GET /api/tasks: dia, depois hora). Aqui so o desenho:
//  - um cabecalho por dia (Atrasadas / Hoje / Amanha / "quinta 15" / Sem data) com quantas abertas;
//  - hora grande na coluna da esquerda, trilho com uma bolinha por tarefa (tocar conclui);
//  - "agora": marcador vivo entre as tarefas de hoje, a proxima respira com "em 40 min" e a
//    que ja passou fica avermelhada ("passou ha 1h20") - atualiza sozinho a cada 30 s;
//  - reordenar animado (FLIP): quando a lista muda, quem ja estava desliza pro lugar novo e
//    quem chegou/mudou acende; abrir a aba faz a lista entrar em cascata.
// Os itens continuam sendo os <li> de criarItemTarefa (tarefas.js) - cabecalho e marcador sao
// <div> de proposito, pra "#lista-tarefas li" continuar contando so tarefa.
// Script classico (escopo global); a parte pura tambem roda em Node (tests/js).

const TL_DIAS_SEMANA = ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"];
const TL_DIAS_CURTOS = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
const TL_MESES_CURTOS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

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

// 40 -> "40 min", 130 -> "2h10", 180 -> "3h"
function tlDuracao(min) {
  const n = Math.max(0, Math.round(min));
  if (n < 60) return `${n} min`;
  const h = Math.floor(n / 60);
  const r = n % 60;
  return r ? `${h}h${String(r).padStart(2, "0")}` : `${h}h`;
}

// Grupo (cabecalho) de uma tarefa. Puro: `hoje` e um Date.
function grupoDaTarefa(t, hoje) {
  const hojeIso = tlIsoDe(hoje);
  const am = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate() + 1, 12);
  const amanhaIso = tlIsoDe(am);
  const d = t && t.due_date;
  if (!d) return { chave: "sem-data", rotulo: "Sem data", dia: "" };
  if (d < hojeIso) return { chave: "atrasadas", rotulo: "Atrasadas", dia: "", alerta: true };
  const data = tlDataDe(d);
  const diaTxt = data ? `${TL_DIAS_SEMANA[data.getDay()]} ${data.getDate()}` : "";
  if (d === hojeIso) return { chave: d, rotulo: "Hoje", dia: diaTxt, hoje: true };
  if (d === amanhaIso) return { chave: d, rotulo: "Amanhã", dia: diaTxt };
  return { chave: d, rotulo: diaTxt || d, dia: data ? `${data.getDate()} ${TL_MESES_CURTOS[data.getMonth()]}` : "" };
}

// "ontem" / "seg 12" - o que a coluna da hora mostra numa atrasada
function rotuloAtraso(dueIso, hoje) {
  const d = tlDataDe(dueIso);
  if (!d) return "";
  const dias = Math.round((new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate(), 12) - d) / 86400000);
  if (dias === 1) return "ontem";
  return `${TL_DIAS_CURTOS[d.getDay()]} ${d.getDate()}`;
}

// Estado de cada tarefa visivel, na ordem da lista. Puro: devolve um item por tarefa
// ({classe, hora, horaVazia, meta}) + onde vai o marcador de agora ({antesDe: id} /
// {depoisDe: id} / null). `agora` e um Date.
function estadosDaLinha(tarefas, agora) {
  const hojeIso = tlIsoDe(agora);
  const agoraMin = agora.getHours() * 60 + agora.getMinutes();
  let proxima = null;
  let ultimaHojeComHora = null;
  const itens = tarefas.map((t) => {
    const min = tlMinutos(t.hora);
    if (t.due_date && t.due_date < hojeIso) {
      return { id: t.id, classe: "tl-atrasada", hora: rotuloAtraso(t.due_date, agora), horaVazia: false, meta: t.hora ? `era às ${t.hora}` : "" };
    }
    if (t.due_date === hojeIso && min !== null) {
      ultimaHojeComHora = t.id;
      if (min < agoraMin) {
        return { id: t.id, classe: "tl-passou", hora: t.hora, horaVazia: false, meta: `passou há ${tlDuracao(agoraMin - min)}` };
      }
      if (proxima === null) {
        proxima = t.id;
        const falta = min - agoraMin;
        return { id: t.id, classe: "tl-proxima", hora: t.hora, horaVazia: false, meta: falta === 0 ? "agora" : `em ${tlDuracao(falta)}` };
      }
    }
    // due_at = texto livre do chat ("sexta de manha") - so aparece quando nao ha data de verdade
    const meta = !t.due_date && t.due_at ? String(t.due_at) : "";
    return { id: t.id, classe: "", hora: min !== null ? t.hora : "—", horaVazia: min === null, meta };
  });
  let agoraEm = null;
  if (proxima !== null) agoraEm = { antesDe: proxima };
  else if (ultimaHojeComHora !== null) agoraEm = { depoisDe: ultimaHojeComHora };
  return { itens, agoraEm };
}

// ---- DOM (so navegador) --------------------------------------------------------------

const _tlCabecalhos = new Map(); // chave do grupo -> <div.tl-dia>
let _tlAgora = null; // <div.tl-agora> (um so)
let _tlEntradaPendente = true; // proxima montagem entra em cascata (1a vez e ao reabrir a aba)
let _tlRelogio = null;

function _tlMenosMovimento() {
  return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function _tlCabecalho(g, abertas) {
  let el = _tlCabecalhos.get(g.chave);
  if (!el) {
    el = document.createElement("div");
    el.className = "tl-dia";
    el.setAttribute("role", "heading");
    el.setAttribute("aria-level", "3");
    el.dataset.tlChave = `g:${g.chave}`;
    el.innerHTML = '<span class="tl-dia-nome"></span><small class="tl-dia-conta"></small>';
    _tlCabecalhos.set(g.chave, el);
  }
  el.classList.toggle("tl-dia-alerta", Boolean(g.alerta));
  const nome = el.querySelector(".tl-dia-nome");
  nome.textContent = g.rotulo;
  if (g.dia && g.dia !== g.rotulo) {
    const dia = document.createElement("em");
    dia.textContent = ` · ${g.dia}`;
    nome.appendChild(dia);
  }
  el.querySelector(".tl-dia-conta").textContent = `${abertas} ${abertas === 1 ? "aberta" : "abertas"}`;
  return el;
}

function _tlMarcadorAgora() {
  if (!_tlAgora) {
    _tlAgora = document.createElement("div");
    _tlAgora.className = "tl-agora";
    _tlAgora.setAttribute("aria-hidden", "true");
    _tlAgora.dataset.tlChave = "agora";
    _tlAgora.innerHTML = '<span class="tl-agora-hora"></span><span class="tl-agora-ponto"></span><span class="tl-agora-linha"></span>';
  }
  return _tlAgora;
}

// Ponta do trilho: a 1a tarefa de cada dia nao tem linha subindo, a ultima nao tem descendo.
function _tlMarcarPontas(lista) {
  const filhos = Array.from(lista.children);
  filhos.forEach((el, i) => {
    if (!el.classList.contains("tl-item")) return;
    const ant = filhos[i - 1];
    const prox = filhos[i + 1];
    el.classList.toggle("tl-primeiro", !ant || ant.classList.contains("tl-dia"));
    el.classList.toggle("tl-ultimo", !prox || prox.classList.contains("tl-dia") || !(prox.classList.contains("tl-item") || prox.classList.contains("tl-agora")));
  });
}

// FLIP: mede quem tem data-tl-chave, roda `mudar()` e desliza cada um do lugar velho pro novo.
function comDeslize(lista, mudar) {
  const animar = !_tlMenosMovimento() && lista.offsetParent !== null;
  const antes = new Map();
  if (animar) lista.querySelectorAll(":scope > [data-tl-chave]").forEach((el) => antes.set(el.dataset.tlChave, el.getBoundingClientRect().top));
  const resultado = mudar();
  if (!animar) return resultado;
  lista.querySelectorAll(":scope > [data-tl-chave]").forEach((el) => {
    const topo = antes.get(el.dataset.tlChave);
    if (topo === undefined || typeof el.animate !== "function") return;
    const dy = topo - el.getBoundingClientRect().top;
    if (Math.abs(dy) < 1) return;
    el.animate([{ translate: `0 ${dy}px` }, { translate: "0 0" }], { duration: 560, easing: "cubic-bezier(0.22, 1, 0.36, 1)" });
  });
  return resultado;
}

// Atualiza hora/estado/meta de cada tarefa e poe o marcador de agora no lugar.
function atualizarAgoraTarefas(lista) {
  lista = lista || (typeof document !== "undefined" && document.getElementById("lista-tarefas"));
  if (!lista) return;
  const lis = Array.from(lista.querySelectorAll(":scope > li.tl-item")).filter((li) => li._tarefa);
  const agora = new Date();
  const { itens, agoraEm } = estadosDaLinha(lis.map((li) => li._tarefa), agora);
  lis.forEach((li, i) => {
    const e = itens[i];
    li.classList.remove("tl-atrasada", "tl-passou", "tl-proxima");
    if (e.classe) li.classList.add(e.classe);
    const hora = li.querySelector(".tl-hora");
    if (hora && hora.textContent !== e.hora) hora.textContent = e.hora;
    if (hora) hora.classList.toggle("vazia", e.horaVazia);
    const meta = li.querySelector(".tl-meta");
    if (meta && meta.textContent !== e.meta) meta.textContent = e.meta;
  });
  const marcador = _tlMarcadorAgora();
  if (!agoraEm) {
    marcador.remove();
  } else {
    marcador.querySelector(".tl-agora-hora").textContent = `${String(agora.getHours()).padStart(2, "0")}:${String(agora.getMinutes()).padStart(2, "0")}`;
    const alvo = lis.find((li) => String(li._tarefa.id) === String(agoraEm.antesDe ?? agoraEm.depoisDe));
    if (alvo) {
      if (agoraEm.antesDe !== undefined && alvo.previousElementSibling !== marcador) lista.insertBefore(marcador, alvo);
      if (agoraEm.depoisDe !== undefined && alvo.nextElementSibling !== marcador) alvo.after(marcador);
    } else {
      marcador.remove();
    }
  }
  _tlMarcarPontas(lista);
}

// Monta a lista principal: cabecalhos + itens (reaproveitando o <li> de quem nao mudou) +
// marcador. `cache` = Map id -> {li, json} (tarefas.js guarda); `criar(t)` = criarItemTarefa.
function montarLinhaDoTempo(lista, tarefas, total, cache, criar) {
  lista.classList.add("tl-lista");
  const hoje = new Date();
  const primeira = !lista.querySelector(":scope > li.tl-item");
  const cascata = _tlEntradaPendente || primeira;
  _tlEntradaPendente = false;
  const abertasPorGrupo = new Map();
  total.forEach((t) => {
    const k = grupoDaTarefa(t, hoje).chave;
    abertasPorGrupo.set(k, (abertasPorGrupo.get(k) || 0) + 1);
  });
  const jaNaTela = new Set(Array.from(lista.querySelectorAll(":scope > li.tl-item")).map((li) => li.dataset.tlChave));
  const novos = [];
  const mudados = [];
  comDeslize(lista, () => {
    const frag = document.createDocumentFragment();
    let grupoAtual = null;
    const vivos = new Set();
    tarefas.forEach((t) => {
      const g = grupoDaTarefa(t, hoje);
      if (g.chave !== grupoAtual) {
        frag.appendChild(_tlCabecalho(g, abertasPorGrupo.get(g.chave) || 0));
        grupoAtual = g.chave;
      }
      const json = JSON.stringify(t);
      const reg = cache.get(t.id);
      let li;
      if (reg && reg.json === json && !reg.li.classList.contains("saindo")) {
        li = reg.li;
      } else {
        li = criar(t);
        cache.set(t.id, { li, json });
        if (reg) mudados.push(li);
      }
      li._tarefa = t;
      li.dataset.tlChave = `t:${t.id}`;
      if (!jaNaTela.has(li.dataset.tlChave)) novos.push(li);
      vivos.add(t.id);
      frag.appendChild(li);
    });
    Array.from(cache.keys()).forEach((id) => vivos.has(id) || cache.delete(id));
    lista.replaceChildren(frag);
    atualizarAgoraTarefas(lista);
  });
  if (_tlMenosMovimento()) return;
  if (cascata) {
    // so o que cabe na tela entra em cascata (o resto ja chega parado)
    Array.from(lista.children)
      .slice(0, 14)
      .forEach((el, i) => {
        el.classList.remove("tl-entra");
        el.style.setProperty("--tl-i", i);
        void el.offsetWidth;
        el.classList.add("tl-entra");
        setTimeout(() => el.classList.remove("tl-entra"), 900 + i * 45);
      });
    return;
  }
  // tarefa nova (ou que mudou de hora/dia) acende ao chegar no lugar
  novos.concat(mudados.filter((li) => !novos.includes(li))).forEach((li) => {
    li.classList.remove("tl-chegando");
    void li.offsetWidth;
    li.classList.add("tl-chegando");
    setTimeout(() => li.classList.remove("tl-chegando"), 1900);
  });
}

// Reabrir a aba: a proxima montagem entra em cascata de novo (e, se a lista nao mudou, ja
// toca agora com o que esta na tela) + o relogio do "agora" so roda com a aba aberta.
function entrarAbaTarefas() {
  const lista = typeof document !== "undefined" && document.getElementById("lista-tarefas");
  if (!lista) return;
  if (lista.querySelector(":scope > li.tl-item")) {
    comDeslize(lista, () => atualizarAgoraTarefas(lista));
    if (!_tlMenosMovimento()) {
      Array.from(lista.children)
        .slice(0, 14)
        .forEach((el, i) => {
          el.classList.remove("tl-entra");
          el.style.setProperty("--tl-i", i);
          void el.offsetWidth;
          el.classList.add("tl-entra");
          setTimeout(() => el.classList.remove("tl-entra"), 900 + i * 45);
        });
    }
  } else {
    _tlEntradaPendente = true;
  }
  if (!_tlRelogio) {
    _tlRelogio = setInterval(() => {
      const aba = document.getElementById("tab-tarefas");
      if (document.hidden || !aba || aba.hidden) return;
      const l = document.getElementById("lista-tarefas");
      if (l && l.querySelector(":scope > li.tl-item")) comDeslize(l, () => atualizarAgoraTarefas(l));
    }, 30000);
  }
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { grupoDaTarefa, estadosDaLinha, rotuloAtraso, tlDuracao, tlMinutos };
}
