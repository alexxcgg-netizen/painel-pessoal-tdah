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

// Modo teste de IA (config persistida, GET/POST /api/configuracoes/teste-ia
// - rotas em app.py): toggle isolado do resto do card, carrega/salva sozinho.
async function loadTesteIA() {
  const checkbox = $("#teste-ia-checkbox");
  if (!checkbox) return;
  // navegacao.js chama loadCustoIAV2 (e este) toda vez que a aba Painel abre
  // de novo - sem a guarda, cada visita empilha mais um listener no mesmo
  // checkbox (mesmo padrao ja usado em avisos.js:wireFormSilencio). Anexa
  // o listener ANTES do primeiro `await` (o GET abaixo) - se anexasse depois,
  // um clique do usuario entre a chamada e a resposta do GET mudaria o
  // estado nativo do checkbox sem disparar o POST (evento perdido, checkbox
  // e servidor ficam dessincronizados ate a proxima visita a aba).
  if (!checkbox.dataset.wired) {
    checkbox.dataset.wired = "1";
    checkbox.addEventListener("change", async () => {
      const ativo = checkbox.checked;
      const resultado = await apiFetch("/api/configuracoes/teste-ia", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ativo }),
      });
      // POST falhou (rede/erro) - nao deixa o toggle mentir sobre o estado real.
      if (!resultado || resultado.ativo !== ativo) checkbox.checked = !ativo;
    });
  }
  const dados = await apiFetch("/api/configuracoes/teste-ia");
  if (dados) checkbox.checked = !!dados.ativo;
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
