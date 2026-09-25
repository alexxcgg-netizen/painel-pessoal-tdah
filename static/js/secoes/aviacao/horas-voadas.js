// static/js/secoes/aviacao/horas-voadas.js - Secao aviacao > horas-voadas (HTML: templates/secoes/aviacao/horas-voadas.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 3645-3688.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadVoosResumo() {
  const vazioEl = $("#voos-vazio");
  const vazioTexto = $("#voos-vazio-texto");
  const textoOriginal = vazioTexto.textContent;
  // busca a previsao do tempo pra cada voo agendado, entao pode demorar um
  // pouco mais que uma chamada comum - mostra que ta carregando em vez de
  // deixar a lista parecendo vazia/quebrada nesse meio tempo
  vazioTexto.textContent = "Carregando voos e previsao do tempo...";
  vazioEl.hidden = false;

  const data = await apiFetch("/api/voos/resumo");
  vazioTexto.textContent = textoOriginal;
  // null (erro ja mostrado) ou resposta fora do formato: deixa a tela como estava
  if (!data || typeof data !== "object" || !Array.isArray(data.proximos)) {
    vazioEl.hidden = $("#lista-voos").children.length > 0;
    return;
  }

  animarNumero($("#voo-horas-semana"), data.horas_semana, fmtHoras);
  animarNumero($("#voo-horas-mes"), data.horas_mes, fmtHoras);
  animarNumero($("#voo-horas-total"), data.horas_total, fmtHoras);

  const currencyChip = $("#currency-voo-chip");
  if (data.dias_desde_ultimo_voo === null || data.dias_desde_ultimo_voo === undefined) {
    currencyChip.hidden = true;
  } else {
    const dias = data.dias_desde_ultimo_voo;
    $("#currency-voo-texto").textContent =
      dias === 0 ? "Voou hoje" : dias === 1 ? "1 dia sem voar" : `${dias} dias sem voar`;
    currencyChip.classList.toggle("alerta", dias >= 21);
    currencyChip.hidden = false;
  }

  const list = $("#lista-voos");
  list.innerHTML = "";
  vazioEl.hidden = data.proximos.length > 0;
  data.proximos.forEach((v) => list.appendChild(criarItemVoo(v)));

  const historico = await apiFetch("/api/voos/historico");
  if (Array.isArray(historico)) {
    desenharGraficoLinha($("#grafico-voos"), historico, {
      cor: "var(--cor-aviacao)",
      formatarValor: fmtHoras,
      rotulo: "Evolucao das horas de voo acumuladas",
    });
  }
}

