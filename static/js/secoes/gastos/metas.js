// static/js/secoes/gastos/metas.js - Secao gastos > metas (HTML: templates/secoes/gastos/metas.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 3107-3215.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

function criarItemMeta(meta) {
  const li = document.createElement("li");
  li.className = "item";
  li.dataset.entidade = "meta"; // destino do link de card (Fase 6)
  li.dataset.id = meta.id;

  const titulo = document.createElement("span");
  titulo.className = "item-titulo";
  titulo.textContent = meta.titulo;
  li.appendChild(titulo);

  const pct = Math.min(100, (meta.valor_guardado / meta.valor_alvo) * 100 || 0);
  const barra = document.createElement("div");
  barra.className = "meta-progresso";
  const barraInterna = document.createElement("div");
  barraInterna.className = "meta-progresso-barra" + (pct >= 100 ? " completa" : "");
  barraInterna.style.width = `${pct}%`;
  barra.appendChild(barraInterna);
  li.appendChild(barra);
  if (pct >= 100) {
    const badge = document.createElement("span");
    badge.className = "badge-sucesso";
    badge.textContent = "meta batida! \u{1F389}";
    li.appendChild(badge);
  }

  const detalhe = document.createElement("p");
  detalhe.className = "meta-detalhe";
  const guardadoTxt = `${fmtMoeda(meta.valor_guardado)} de ${fmtMoeda(meta.valor_alvo)} guardado`;
  const diasTxt =
    pct < 100 && meta.dias_restantes != null
      ? meta.dias_restantes >= 0
        ? ` (faltam ${meta.dias_restantes} dia${meta.dias_restantes === 1 ? "" : "s"})`
        : ` (${Math.abs(meta.dias_restantes)} dia${Math.abs(meta.dias_restantes) === 1 ? "" : "s"} atrasada)`
      : "";
  const prazoTxt = meta.prazo
    ? meta.por_mes != null
      ? ` - guarde ${fmtMoeda(meta.por_mes)}/mes ate ${meta.prazo}${diasTxt}`
      : ` - prazo: ${meta.prazo}${diasTxt}`
    : " - sem prazo definido";
  detalhe.textContent = guardadoTxt + prazoTxt;
  li.appendChild(detalhe);
  if (meta.previsao && pct < 100) {
    const previsao = document.createElement("p");
    previsao.className = "meta-detalhe";
    previsao.textContent = `No ritmo atual (${fmtMoeda(meta.previsao.ritmo_mensal)}/mes), bate em ${fmtDataBr(meta.previsao.data_prevista)}.`;
    li.appendChild(previsao);
  }

  const graficoWrap = document.createElement("div");
  graficoWrap.className = "grafico-container meta-grafico";
  graficoWrap.id = `grafico-meta-${meta.id}`;
  li.appendChild(graficoWrap);

  const guardarWrap = document.createElement("div");
  guardarWrap.className = "meta-guardar";
  const input = document.createElement("input");
  input.type = "text";
  input.inputMode = "decimal";
  input.placeholder = "guardei R$...";
  aplicarMascaraMoeda(input);
  const btn = document.createElement("button");
  btn.className = "btn-com-icone";
  btn.innerHTML = `${ICONE_PLUS}Registrar`;
  btn.addEventListener("click", async () => {
    const valor = valorMascaraParaNumero(input.value);
    if (!valor || valor <= 0) return;
    setBotaoCarregando(btn, true, "salvando...");
    const data = await apiFetch(`/api/metas/${meta.id}/guardar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ valor }),
    });
    setBotaoCarregando(btn, false, "Registrar");
    if (data) {
      loadMetas();
      loadStreak();
    }
  });
  guardarWrap.appendChild(input);
  guardarWrap.appendChild(btn);
  li.appendChild(guardarWrap);

  return li;
}

async function loadMetas() {
  const metas = await apiFetch("/api/metas");
  if (!metas) return;
  const list = $("#lista-metas");
  list.innerHTML = "";
  $("#metas-vazio").hidden = metas.length > 0;
  metas.forEach((m) => list.appendChild(criarItemMeta(m)));

  metas.forEach(async (m) => {
    const historico = await apiFetch(`/api/metas/${m.id}/historico`);
    const container = $(`#grafico-meta-${m.id}`);
    if (historico && container) {
      desenharGraficoLinha(container, historico.pontos, {
        cor: "var(--cor-hoje)",
        valorAlvo: historico.valor_alvo,
        formatarValor: fmtMoeda,
        altura: 70,
        rotulo: `Evolucao de "${m.titulo}"`,
      });
    }
  });
}
