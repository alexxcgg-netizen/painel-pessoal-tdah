// static/js/secoes/painel/resumo.js - Secao painel > resumo (HTML: templates/secoes/painel/resumo.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 698-761.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

// Cache do ultimo resumo com sucesso (so o texto/numeros, nada de PII alem do que ja
// aparece na tela) - se abrir o painel sem rede, mostra o ultimo estado conhecido em
// vez de uma tela vazia. Por viewer/dispositivo so, nunca sincroniza entre aparelhos -
// e so uma conveniencia visual, cada leitura/escrita protegida (localStorage pode
// falhar ou nao existir: aba anonima, storage bloqueado etc).
const CHAVE_CACHE_RESUMO = "painel:ultimo-resumo";

function salvarResumoCache(data) {
  try {
    localStorage.setItem(CHAVE_CACHE_RESUMO, JSON.stringify(data));
  } catch {
    // ignora - cache e so uma conveniencia, nunca deve quebrar o carregamento
  }
}

function lerResumoCache() {
  try {
    const bruto = localStorage.getItem(CHAVE_CACHE_RESUMO);
    return bruto ? JSON.parse(bruto) : null;
  } catch {
    return null;
  }
}

async function loadSummary() {
  const resumoEl = $("#resumo-texto");
  resumoEl.classList.add("carregando");
  resumoEl.setAttribute("aria-busy", "true");
  resumoEl.textContent = "Carregando...";

  const [data, tasks, metas] = await Promise.all([
    apiFetch("/api/summary/today"),
    apiFetch("/api/tasks"),
    apiFetch("/api/metas"),
  ]);

  if (tasks) animarNumero($("#stat-tarefas"), tasks.length);
  if (metas) {
    const ativas = metas.filter((m) => m.valor_guardado < m.valor_alvo).length;
    animarNumero($("#stat-metas"), ativas);
  }

  resumoEl.classList.remove("carregando");
  resumoEl.removeAttribute("aria-busy");

  const dadosPraMostrar = data || lerResumoCache();
  if (!dadosPraMostrar) {
    resumoEl.textContent = "Não consegui gerar o resumo agora.";
    // C2: sem resumo (IA fora/teto), o tile "gasto hoje" ficava no shimmer pra sempre.
    const gastoEl = $("#stat-gasto");
    gastoEl.classList.remove("shimmer");
    gastoEl.textContent = "—";
    return;
  }
  animarNumero($("#stat-gasto"), dadosPraMostrar.gasto_hoje, fmtMoeda);
  const planejadoEl = $("#stat-gasto-planejado");
  if (dadosPraMostrar.gasto_planejado > 0) {
    planejadoEl.textContent = `+${fmtMoeda(dadosPraMostrar.gasto_planejado)} planejado`;
    planejadoEl.hidden = false;
  } else {
    planejadoEl.hidden = true;
  }
  resumoEl.textContent = dadosPraMostrar.summary;
  $("#resumo-stats").textContent = data
    ? `${data.tarefas_concluidas} tarefa(s) concluída(s) hoje`
    : `${dadosPraMostrar.tarefas_concluidas} tarefa(s) concluída(s) - sem conexão, mostrando o último resumo salvo`;

  if (data) salvarResumoCache(data);
}
