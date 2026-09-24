// static/js/nucleo/linha-do-tempo.js - Nucleo compartilhado: fmtHora + criarItemLinhaDoTempo (usado pela agenda do Painel e pela visao-dia.js).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 857-927.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

function fmtHora(isoString) {
  const d = new Date(isoString);
  return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

// Rotulo da tag por origem (Fase 6, US-E9: visao do dia marca cada item por
// quem ele veio - Tarefas/Agenda/Habitos). "tarefa" ja existia (US-B?), so
// acrescenta habito/calendario - sem rotulo pra qualquer origem nova que
// aparecer no futuro (a tag so some, nunca quebra).
const ROTULO_ORIGEM_ITEM = { tarefa: "tarefa", habito: "habito", calendario: "agenda" };

// Cria um <li> da linha do tempo (inspirada no Tiimo): cada compromisso marca
// sua posicao na linha vertical - o que ja passou fica apagado, o proximo que
// ainda vai acontecer ganha destaque, pra ajudar com cegueira de tempo (comum
// em TDAH) a bater o olho e saber onde esta no dia sem ter que ler tudo.
// Compartilhada (Fase 6, US-E9) entre a agenda de hoje (#lista-agenda, aba
// Painel) e a visao do dia (#visao-dia-timeline, aba Hoje) - a MESMA marcacao
// visual em vez de duas implementacoes. `proximoJaMarcado` vem de fora (o
// chamador acumula pelas chamadas do loop) porque so o primeiro item futuro
// da lista ganha o destaque "proximo".
function criarItemLinhaDoTempo(ev, agora, proximoJaMarcado) {
  const li = document.createElement("li");
  li.className = "item";
  const completavel = ev.origem === "tarefa" || ev.origem === "habito";
  let marcouProximo = false;

  if (!ev.dia_inteiro) {
    const jaPassou = new Date(ev.fim) < agora;
    if (completavel && ev.concluido) {
      // concluido: bolinha verde, mesmo se foi feito adiantado (antes do horario)
      li.classList.add("concluido");
    } else if (completavel && jaPassou) {
      // tarefa/habito com horario que passou e nao foi marcado como feito: bolinha vermelha
      li.classList.add("perdido");
    } else if (jaPassou) {
      // compromisso de calendario nao tem como confirmar presenca - fica so apagado, sem julgar
      li.classList.add("passado");
    } else if (!proximoJaMarcado) {
      li.classList.add("proximo");
      marcouProximo = true;
    }
  }

  const titulo = document.createElement("span");
  titulo.className = "item-titulo";
  titulo.textContent = ev.titulo;
  const rotuloOrigem = ROTULO_ORIGEM_ITEM[ev.origem];
  if (rotuloOrigem) {
    const tag = document.createElement("span");
    tag.className = ev.origem === "tarefa" ? "item-tag-tarefa" : `item-tag-${ev.origem}`;
    tag.textContent = rotuloOrigem;
    titulo.appendChild(tag);
  }
  if (li.classList.contains("proximo")) {
    const badge = document.createElement("span");
    badge.className = "item-badge-proximo";
    badge.textContent = "proximo";
    titulo.appendChild(badge);
  }
  const horario = document.createElement("span");
  horario.className = "item-quando";
  horario.textContent = ev.dia_inteiro
    ? "dia todo"
    : ev.inicio === ev.fim
    ? fmtHora(ev.inicio)
    : `${fmtHora(ev.inicio)} - ${fmtHora(ev.fim)}`;
  li.appendChild(titulo);
  li.appendChild(horario);
  return { li, marcouProximo };
}
