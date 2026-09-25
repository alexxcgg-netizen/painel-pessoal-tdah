// static/js/secoes/hoje/conversa.js - Secao hoje > conversa (HTML: templates/secoes/hoje/conversa.html).
// Fase 9 (C2): topo da aba Hoje em formato de conversa (mensagens do assistente montadas
// em codigo, sem IA nenhuma) com cartoes e um grafico SVG do gasto acumulado do mes.
// So consome rotas que ja existem (/api/financas/resumo, /api/financas/extrato,
// /api/sobrecarga, /api/essencial, /api/hiperfoco, /api/calendario/hoje) - nao reimplementa
// nenhum calculo financeiro nem de agenda, so formata pra exibir.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

// ---- Grafico SVG do acumulado do mes: funcao pura (sem DOM), testavel isolada -----
// (mesma forma do chartAcumulado do laboratorio visual docs/fase9-lab2/d01.js, direcao
// "Conversa", so trocando os hex fixos pelos tokens/fmtMoeda do app de verdade).
// `porDiaMes` = [{data, acumulado}, ...] (US futura da faixa de financas); se ainda nao
// vier da API, esta funcao nao e chamada (loadConversaHoje guarda antes) - por isso ela
// pode assumir uma lista nao vazia.
function construirSvgGastoAcumulado(porDiaMes, refValor, formatarMoeda, w, h) {
  w = w || 300;
  h = h || 92;
  const padB = 16;
  const vals = porDiaMes.map((d) => Number(d.acumulado) || 0);
  const maxVal = Math.max.apply(null, vals.concat([Number(refValor) || 0, 1]));
  const n = porDiaMes.length;
  const stepX = n > 1 ? w / (n - 1) : 0;
  const scaleY = (v) => h - padB - (v / maxVal) * (h - padB - 8);
  const pts = porDiaMes.map((d, i) => [i * stepX, scaleY(Number(d.acumulado) || 0)]);
  const path = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
  const area = path + ` L${pts[n - 1][0].toFixed(1)},${(h - padB).toFixed(1)} L0,${(h - padB).toFixed(1)} Z`;
  const showRef = refValor && refValor <= maxVal;
  const refY = scaleY(Number(refValor) || 0);
  const last = pts[n - 1];
  const fmt = formatarMoeda || ((v) => String(v));
  return (
    `<svg viewBox="0 0 ${w} ${h}" class="conversa-svg-grafico" role="img" aria-label="Gasto acumulado do mes, dia a dia">` +
    `<line x1="0" y1="${(h - padB).toFixed(1)}" x2="${w}" y2="${(h - padB).toFixed(1)}" class="eixo"/>` +
    (showRef
      ? `<line x1="0" y1="${refY.toFixed(1)}" x2="${w}" y2="${refY.toFixed(1)}" class="ref"/>` +
        `<text x="${w}" y="${(refY - 4).toFixed(1)}" class="ref-lbl" text-anchor="end">mes anterior ${fmt(refValor)}</text>`
      : "") +
    `<path d="${area}" class="area"/>` +
    `<path d="${path}" class="linha"/>` +
    `<circle cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="3" class="ponto"/>` +
    `<text x="0" y="${h}" class="eixo-lbl">dia 1</text>` +
    `<text x="${w}" y="${h}" class="eixo-lbl" text-anchor="end">dia ${n}</text>` +
    `</svg>`
  );
}

// ---- Texto de saudacao (mesma faixa de horario de saudacao.js, so pra nao depender da
// ordem de carga - mostrarSaudacao() roda depois, em nucleo/init.js) ----
function textoSaudacaoConversa() {
  const agora = new Date();
  const hora = agora.getHours();
  const saudacao = hora < 5 ? "Boa noite" : hora < 12 ? "Bom dia" : hora < 18 ? "Boa tarde" : "Boa noite";
  const primeiroNome = (typeof NOME_USUARIO !== "undefined" && NOME_USUARIO ? NOME_USUARIO : "").split(" ")[0];
  const dataFormatada = agora.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });
  const dataCap = dataFormatada.charAt(0).toUpperCase() + dataFormatada.slice(1);
  const horaTxt = agora.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  return `${saudacao}${primeiroNome ? ", " + primeiroNome : ""}. ${dataCap}, ${horaTxt}.`;
}

async function renderConversaAviso() {
  const dados = await apiFetch("/api/sobrecarga");
  const box = $("#conversa-aviso");
  if (!dados || !dados.sobrecarregado) {
    box.hidden = true;
    return;
  }
  const rotulo = typeof SINAL_TEXTO === "object" && SINAL_TEXTO ? SINAL_TEXTO : {};
  const lista = (dados.sinais || []).map((s) => rotulo[s] || s).join(", ");
  $("#conversa-aviso-texto").textContent = `Varios sinais juntos: ${lista}. Talvez valha desacelerar hoje.`;
  box.hidden = false;
}

async function renderConversaGasto() {
  const [resumo, extratoHoje] = await Promise.all([
    apiFetch("/api/financas/resumo"),
    apiFetch("/api/financas/extrato?dias=1"),
  ]);
  if (!resumo) return;

  $("#gasto-valor").textContent = fmtMoeda(resumo.gasto_mes || 0);
  $("#gasto-fatura").textContent = fmtMoeda(resumo.fatura_atual || 0);
  $("#gasto-conta").textContent = fmtMoeda(resumo.saldo_conta || 0);

  const gastoHoje =
    extratoHoje && Array.isArray(extratoHoje.itens)
      ? extratoHoje.itens.filter((i) => i.valor < 0).reduce((soma, i) => soma + Math.abs(i.valor), 0)
      : null;
  $("#gasto-hoje").textContent = gastoHoje === null ? "--" : fmtMoeda(gastoHoje);

  const pill = $("#gasto-variacao");
  if (resumo.gasto_mes_anterior) {
    const delta = ((resumo.gasto_mes - resumo.gasto_mes_anterior) / resumo.gasto_mes_anterior) * 100;
    const subiu = delta >= 0;
    pill.textContent = `${subiu ? "▲" : "▼"} ${Math.abs(delta).toFixed(0)}%`;
    pill.classList.toggle("conversa-pill--up", subiu);
    pill.classList.toggle("conversa-pill--down", !subiu);
    pill.hidden = false;
  } else {
    pill.hidden = true;
  }

  // Fase 9: /api/financas/resumo ainda pode nao trazer por_dia_mes (outra faixa
  // esta adicionando) - sem ele, so o valor/minis acima aparecem, sem grafico.
  const grafico = $("#gasto-grafico");
  if (Array.isArray(resumo.por_dia_mes) && resumo.por_dia_mes.length > 0) {
    grafico.innerHTML = construirSvgGastoAcumulado(
      resumo.por_dia_mes,
      resumo.por_dia_mes_anterior,
      fmtMoeda,
      300,
      92
    );
  } else {
    grafico.innerHTML = "";
  }
}

async function renderConversaFoco() {
  const [essencial, hiperfoco] = await Promise.all([apiFetch("/api/essencial"), apiFetch("/api/hiperfoco")]);
  const texto = $("#foco-texto");
  if (hiperfoco && hiperfoco.ativo) {
    const min = Math.ceil((hiperfoco.segundos_restantes || 0) / 60);
    texto.textContent = `Hiperfoco ativo - faltam ${min} min`;
    return;
  }
  const pendente = essencial && Array.isArray(essencial.tarefas) ? essencial.tarefas.find((t) => !t.feita) : null;
  texto.textContent = pendente ? pendente.title : "Nada urgente pra agora.";
}

async function renderConversaProximos() {
  const dados = await apiFetch("/api/calendario/hoje");
  const lista = $("#proximos-lista");
  const vazio = $("#proximos-vazio");
  lista.innerHTML = "";
  const eventos = (dados && Array.isArray(dados.eventos) ? dados.eventos : []).slice(0, 3);
  vazio.hidden = eventos.length > 0;
  eventos.forEach((ev) => {
    const li = document.createElement("li");
    li.className = "conversa-proximo-item";
    const nome = document.createElement("span");
    nome.className = "conversa-proximo-titulo";
    nome.textContent = ev.titulo;
    const quando = document.createElement("span");
    quando.className = "conversa-proximo-hora";
    quando.textContent = ev.dia_inteiro ? "dia todo" : fmtHora(ev.inicio);
    li.appendChild(nome);
    li.appendChild(quando);
    lista.appendChild(li);
  });
}

async function loadConversaHoje() {
  const saudacaoEl = $("#conversa-saudacao");
  if (saudacaoEl) saudacaoEl.textContent = textoSaudacaoConversa();
  await Promise.all([renderConversaAviso(), renderConversaGasto(), renderConversaFoco(), renderConversaProximos()]);
}

const btnGastoMes = $("#card-gasto-mes");
if (btnGastoMes) {
  btnGastoMes.addEventListener("click", () => showTab("gastos"));
}

$("#conversa-chips")
  .querySelectorAll(".chip")
  .forEach((chip) => {
    chip.addEventListener("click", () => {
      const input = $("#chat-input");
      if (input) input.value = "";
      enviarChat(chip.dataset.msg);
    });
  });

document.querySelectorAll(".tab-btn").forEach((btn) => {
  if (btn.dataset.tab === "hoje") btn.addEventListener("click", loadConversaHoje);
});
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") loadConversaHoje();
});

loadConversaHoje();

// Dual export (mesmo padrao de static/js/ui/secao-recolhivel.js): em Node (testes
// `node --test`, sem DOM) so a funcao pura do grafico fica acessivel.
if (typeof module !== "undefined" && module.exports) {
  module.exports = { construirSvgGastoAcumulado };
}
