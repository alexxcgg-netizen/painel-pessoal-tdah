// static/js/secoes/painel/agenda-de-hoje.js - Secao painel > agenda-de-hoje (HTML: templates/secoes/painel/agenda-de-hoje.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 928-947.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadAgenda() {
  const data = await apiFetch("/api/calendario/hoje");
  if (!data) return;

  $("#agenda-desconectada").hidden = data.configurado;

  const list = $("#lista-agenda");
  list.innerHTML = "";
  $("#agenda-vazio").hidden = data.eventos.length > 0;

  const agora = new Date();
  let proximoMarcado = false;

  data.eventos.forEach((ev) => {
    const { li, marcouProximo } = criarItemLinhaDoTempo(ev, agora, proximoMarcado);
    if (marcouProximo) proximoMarcado = true;
    list.appendChild(li);
  });
}
