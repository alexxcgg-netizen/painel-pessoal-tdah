// static/js/secoes/painel/custo-ia.js - Secao painel > custo-ia (HTML: templates/secoes/painel/custo-ia.html).
// Fase 7, faixa V2: card "Custo de IA" - GET /api/ia/uso/resumo (rotas/v2_custo_ia.py) +
// grafico de barras (static/js/charts.js, o mesmo ja usado em gastos.js). Script classico
// (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

const CUSTO_IA_V2_ROTULO_NIVEL = {
  normal: "",
  aviso_80: "Ja passou de 80% do teto do mes - modo economia liga em 100%.",
  estourado_100:
    "Teto do mes estourado - so as funcoes essenciais (classificacao/captura) continuam chamando IA ate o mes virar.",
};

function custoIaV2FormatarPercentual(fracao) {
  return `${Math.round(fracao * 100)}%`;
}

function custoIaV2PreencherTabela(porFuncao) {
  const corpo = $("#custo-ia-v2-tabela-corpo");
  const tabela = $("#custo-ia-v2-tabela");
  corpo.innerHTML = "";
  if (!porFuncao.length) {
    tabela.hidden = true;
    return;
  }
  tabela.hidden = false;
  porFuncao.forEach((linha) => {
    const tr = document.createElement("tr");

    const tdFuncao = document.createElement("td");
    tdFuncao.textContent = linha.funcao;
    tr.appendChild(tdFuncao);

    const tdChamadas = document.createElement("td");
    tdChamadas.textContent = linha.chamadas;
    tr.appendChild(tdChamadas);

    const tdGasto = document.createElement("td");
    tdGasto.textContent = fmtMoeda(linha.gasto_brl);
    tr.appendChild(tdGasto);

    corpo.appendChild(tr);
  });
}

function custoIaV2PreencherGrafico(porDia) {
  const container = $("#custo-ia-v2-grafico");
  if (!container) return;
  const dados = porDia.map((d) => ({ data: d.data, total: d.gasto_brl }));
  desenharGraficoBarras(container, dados, {
    cor: "var(--cor-painel)",
    formatarValor: fmtMoeda,
    rotulo: "Gasto de IA por dia, esse mes",
  });
}

async function loadCustoIAV2() {
  const dados = await apiFetch("/api/ia/uso/resumo");
  $("#custo-ia-v2-carregando").hidden = !!dados;
  if (!dados) return;

  $("#custo-ia-v2-conteudo").hidden = false;
  $("#custo-ia-v2-gasto").textContent = fmtMoeda(dados.gasto_brl);
  $("#custo-ia-v2-mes").textContent = `em ${dados.mes} (teto: ${fmtMoeda(dados.teto_brl)})`;

  const pct = Math.min(100, Math.max(0, dados.fracao_teto * 100));
  const barra = $("#custo-ia-v2-barra");
  barra.style.width = `${pct}%`;
  barra.classList.toggle("completa", dados.nivel_alerta === "estourado_100");
  $("#custo-ia-v2-fracao").textContent = `${custoIaV2FormatarPercentual(dados.fracao_teto)} do teto usado`;
  $("#custo-ia-v2-projecao").textContent = `Projecao ate o fim do mes: ${fmtMoeda(dados.projecao_fim_mes_brl)}.`;

  const nivelEl = $("#custo-ia-v2-nivel");
  const textoNivel = CUSTO_IA_V2_ROTULO_NIVEL[dados.nivel_alerta] || "";
  nivelEl.textContent = textoNivel;
  nivelEl.hidden = !textoNivel;
  nivelEl.classList.toggle("custo-ia-nivel-estourado", dados.nivel_alerta === "estourado_100");
  nivelEl.classList.toggle("custo-ia-nivel-aviso", dados.nivel_alerta === "aviso_80");

  const semUso = dados.total_chamadas === 0;
  $("#custo-ia-v2-vazio").hidden = !semUso;
  $("#custo-ia-v2-grafico").hidden = semUso;
  custoIaV2PreencherTabela(dados.por_funcao);
  if (!semUso) custoIaV2PreencherGrafico(dados.por_dia);
}
