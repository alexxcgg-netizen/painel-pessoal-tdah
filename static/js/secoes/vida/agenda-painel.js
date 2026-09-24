// static/js/secoes/vida/agenda-painel.js - Secao vida > agenda-painel (HTML: templates/secoes/vida/agenda-painel.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 869-904.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadEventosCriados() {
  const eventos = await apiFetch("/api/agenda/eventos-criados");
  if (!eventos) return;
  const lista = $("#lista-eventos-criados");
  lista.innerHTML = "";
  $("#eventos-criados-vazio").hidden = eventos.length > 0;
  eventos.forEach((e) => {
    lista.appendChild(
      itemSimples(e.titulo, [`${fmtDataBr(e.inicio.slice(0, 10))} ${e.inicio.slice(11, 16)}-${e.fim.slice(11, 16)}`], [
        (el) => botaoApagar(`/api/agenda/eventos/${e.uid}`, el),
      ])
    );
  });
}

ligarForm(
  "#evento-form",
  "#evento-btn",
  "Criar evento",
  () => {
    const titulo = $("#evento-titulo").value.trim();
    const data = $("#evento-data").value;
    const hora_inicio = $("#evento-hora-inicio").value;
    const hora_fim = $("#evento-hora-fim").value;
    if (!titulo || !data || !hora_inicio || !hora_fim) return null;
    const corpo = { titulo, data, hora_inicio, hora_fim };
    const lembrar = $("#evento-lembrar").value;
    if (lembrar !== "") corpo.lembrar_min_antes = Number(lembrar);
    return corpo;
  },
  "/api/agenda/eventos",
  loadEventosCriados
);

// ---- Fase 2: treino ----
