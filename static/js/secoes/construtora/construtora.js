// static/js/secoes/construtora/construtora.js - Secao construtora > construtora (HTML: templates/secoes/construtora/construtora.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 3216-3245.
// Fase 7 (faixa v6-financas): card com 2 stats + tempo ate a proxima conta.
// Decisao do Alex (docs/contrato-api-construtora.md, faixa A10): o painel
// mostra SO gastos, entradas e tempo ate a proxima conta a pagar - nunca
// lucro, margem nem VGV. A rota `/api/construtora/resumo` (app.py, fora desta
// faixa) ainda devolve lucro_liquido/margem no JSON; aqui so tot_entradas e
// tot_saidas sao lidos (lista branca), o resto e descartado na hora.
// Fase 7 (faixa C3c): estado de erro de verdade (antes o "Carregando..."
// ficava pra sempre quando a rota respondia 502/500 ou JSON invalido) e guarda
// contra NaN/undefined.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

// So formatacao, nao conta: de R$ 100 mil pra cima os centavos nao dizem nada e fazem o
// valor quebrar linha no celular ("R$ 1.258.000" em vez de "R$ 1.258.000,00").
function fmtNumeroGrande(v) {
  if (Math.abs(v) < 100000) return fmtMoedaFinancas(v);
  return `R$ ${Math.round(v).toLocaleString("pt-BR")}`;
}

function rotuloProximaConta(contas) {
  // "socio" = o Ademir paga em especie, nao sai do caixa da empresa -> nao conta aqui
  const comDias = contas.filter((c) => numeroFinancas(c.dias_ate_vencer) !== null && c.pagador !== "socio");
  if (comDias.length === 0) return "Nenhuma conta em aberto nos próximos 30 dias.";
  const proxima = comDias.reduce((m, c) => (Number(c.dias_ate_vencer) < Number(m.dias_ate_vencer) ? c : m));
  const dias = Number(proxima.dias_ate_vencer);
  if (dias < 0) return `Próxima conta venceu há ${Math.abs(dias)} dia(s).`;
  if (dias === 0) return "Próxima conta vence hoje.";
  if (dias === 1) return "Próxima conta vence amanhã.";
  return `Próxima conta em ${dias} dias.`;
}

async function loadConstrutora() {
  const info = $("#construtora-info");
  const card = $("#construtora-card");
  const listaContas = $("#lista-contas-a-vencer");
  info.hidden = false;
  info.classList.add("carregando");
  info.setAttribute("aria-busy", "true");
  info.textContent = "Carregando...";
  card.hidden = true;
  listaContas.innerHTML = "";
  listaContas.hidden = true;
  $("#contas-a-vencer-vazio").hidden = true;

  const data = await apiFetch("/api/construtora/resumo");
  info.classList.remove("carregando");
  info.removeAttribute("aria-busy");
  if (!data || typeof data !== "object") {
    info.textContent = "Não consegui falar com a construtora agora. Tenta de novo daqui a pouco.";
    return;
  }
  if (!data.configurado) {
    info.textContent = "Ainda não conectado à API da construtora.";
    return;
  }
  if (data.erro) {
    info.textContent = String(data.erro);
    return;
  }

  // 4 numeros prontos da construtora (decisao do Alex 10/10). Cada um que nao vier some
  // sozinho; nada e somado nem recalculado aqui.
  const d = data.dados && typeof data.dados === "object" ? data.dados : {};
  const contas = Array.isArray(data.contas) ? data.contas.filter((c) => c && typeof c === "object") : [];
  const numeros = {
    caixa: numeroFinancas(d.saldo_caixa),
    receber: numeroFinancas(d.a_receber),
    lucro: numeroFinancas(d.lucro_obras_fechadas),
    venda: numeroFinancas(d.estoque_a_venda),
  };
  const algum = Object.values(numeros).some((v) => v !== null);

  if (!algum && contas.length === 0) {
    info.textContent = "A construtora respondeu sem dado utilizavel agora.";
    return;
  }

  info.hidden = true;
  card.hidden = false;
  Object.entries(numeros).forEach(([chave, valor]) => {
    $(`#construtora-stat-${chave}`).hidden = valor === null;
    if (valor !== null) $(`#construtora-${chave}`).textContent = fmtNumeroGrande(valor);
  });
  const obras = numeroFinancas(d.obras_fechadas);
  $("#construtora-lucro-sub").textContent = obras ? `${obras} ${obras === 1 ? "obra fechada" : "obras fechadas"}` : "";
  const unidades = numeroFinancas(d.unidades_a_venda);
  $("#construtora-venda-sub").textContent = unidades !== null ? `${unidades} ${unidades === 1 ? "unidade" : "unidades"}` : "";
  $("#construtora-proxima-conta-texto").textContent = rotuloProximaConta(contas);

  $("#contas-a-vencer-vazio").hidden = contas.length > 0;
  listaContas.hidden = contas.length === 0;
  contas.forEach((c) => listaContas.appendChild(criarItemContaAVencer(c)));
}
