// static/js/secoes/construtora/contas-a-pagar.js - Secao construtora > contas-a-pagar (HTML: templates/secoes/construtora/contas-a-pagar.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 3246-3282.
// Fase 7 (faixa C3c): vira .lista-item (MASTER #5, lista dentro de card), valor
// a direita em mono, selo "vencida" com icone (cor nunca e o unico sinal) e
// guarda contra campo faltando (fornecedor/descricao podem vir null -
// docs/contrato-api-construtora.md).
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

const ICONE_ALERTA_CONTA =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5"/><path d="M12 16.5h.01"/></svg>';

function quandoContaAVencer(dias) {
  if (dias === null) return "sem data";
  if (dias < 0) return `venceu ha ${Math.abs(dias)} dia(s)`;
  if (dias === 0) return "vence hoje";
  if (dias === 1) return "vence amanha";
  return `vence em ${dias} dias`;
}

function criarItemContaAVencer(c) {
  const dias = numeroFinancas(c.dias_ate_vencer);
  const vencida = dias !== null && dias < 0;
  const li = criarEl("li", "lista-item" + (vencida ? " conta-vencida" : ""));

  const corpo = criarEl("div", "lista-item-corpo");
  const titulo = textoFinancas(c.fornecedor, "") || textoFinancas(c.descricao, "") || "Fornecedor não informado";
  corpo.appendChild(criarEl("span", "lista-item-titulo", titulo));

  const meta = criarEl("span", "lista-item-meta");
  if (vencida) {
    const selo = criarEl("span", "selo-vencida");
    selo.innerHTML = ICONE_ALERTA_CONTA;
    selo.appendChild(document.createTextNode("vencida"));
    meta.appendChild(selo);
  }
  meta.appendChild(document.createTextNode(quandoContaAVencer(dias)));
  corpo.appendChild(meta);
  li.appendChild(corpo);

  li.appendChild(criarEl("span", "valor-mono lista-item-valor", fmtMoedaFinancas(c.valor)));
  return li;
}
