// static/js/secoes/construtora/contas-a-pagar.js - Secao construtora > contas-a-pagar (HTML: templates/secoes/construtora/contas-a-pagar.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 3246-3282.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

function criarItemContaAVencer(c) {
  const li = document.createElement("li");
  li.className = "item";

  const linha = document.createElement("div");
  linha.className = "item-linha";

  const tituloWrap = document.createElement("div");
  const titulo = document.createElement("span");
  titulo.className = "item-titulo";
  titulo.textContent = c.fornecedor || c.descricao || "Fornecedor nao informado";
  if (c.dias_ate_vencer < 0) {
    const badge = document.createElement("span");
    badge.className = "item-badge-vencida";
    badge.textContent = "vencida";
    titulo.appendChild(badge);
  }
  tituloWrap.appendChild(titulo);

  const quando = document.createElement("span");
  quando.className = "item-quando";
  let quandoTexto;
  if (c.dias_ate_vencer < 0) {
    quandoTexto = `venceu ha ${Math.abs(c.dias_ate_vencer)} dia(s)`;
  } else if (c.dias_ate_vencer === 0) {
    quandoTexto = "vence hoje";
  } else {
    quandoTexto = `vence em ${c.dias_ate_vencer} dia(s)`;
  }
  quando.textContent = `${fmtMoeda(c.valor)} · ${quandoTexto}`;
  tituloWrap.appendChild(quando);

  linha.appendChild(tituloWrap);
  li.appendChild(linha);
  return li;
}
