// static/js/secoes/vida/contas-pessoais.js - Secao vida > contas-pessoais (HTML: templates/secoes/vida/contas-pessoais.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 389-455.
// Fase 7 (faixa v6-financas): botao "adicionar" -> .btn-adicionar + .bottom-sheet.
// Fase 7 (faixa C3c): sheet so pelo componente compartilhado (abre por
// data-abre-sheet, fecha por "bottomsheet:sucesso"), validacao em pt-BR dentro do sheet, valor fora do titulo (nao some mais com
// reticencias em 390px) e acoes com as classes do contrato. Os helpers
// *Financas (numeroFinancas, fmtMoedaFinancas, sucessoSheetFinancas...) moram em
// static/js/secoes/gastos/assinaturas.js, que carrega DEPOIS deste arquivo -
// por isso so sao chamados dentro de handlers/loads, nunca no topo.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

function quandoContaPessoal(c) {
  const venc = fmtDataFinancas(c.proximo_vencimento);
  const dias = numeroFinancas(c.dias_ate_vencer);
  if (c.paga) return `paga (vencimento ${venc})`;
  if (dias === null) return `vence ${venc}`;
  if (dias < 0) return `venceu ${venc} · ha ${-dias} dia(s)`;
  if (dias === 0) return "vence hoje";
  return `vence ${venc} · em ${dias} dia(s)`;
}

async function loadContasPessoais() {
  const contas = await apiFetch("/api/contas-pessoais");
  if (!Array.isArray(contas)) return;
  const lista = $("#lista-contas-pessoais");
  lista.innerHTML = "";
  const validas = contas.filter((c) => c && typeof c === "object");
  lista.hidden = validas.length === 0;
  $("#contas-pessoais-vazio").hidden = validas.length > 0;
  validas.forEach((c) => {
    const dias = numeroFinancas(c.dias_ate_vencer);
    const urgente = !c.paga && dias !== null && dias <= 3;
    const nome = textoFinancas(c.nome, "Conta sem nome");
    const li = criarEl("li", "lista-item" + (urgente ? " item-atencao" : ""));
    const corpo = criarEl("div", "lista-item-corpo");
    corpo.appendChild(criarEl("span", "lista-item-titulo", nome));
    const metaPartes = [];
    if (numeroFinancas(c.valor) !== null) metaPartes.push(fmtMoedaFinancas(c.valor));
    metaPartes.push(quandoContaPessoal(c));
    corpo.appendChild(criarEl("span", "lista-item-meta valor-mono", metaPartes.join(" · ")));
    li.appendChild(corpo);

    const acoes = criarEl("div", "lista-item-acoes");
    if (!c.paga) {
      const pagar = criarEl("button", "btn btn-secundario btn-pagar-conta");
      pagar.type = "button";
      pagar.innerHTML = `${ICONE_CHECK}<span>Paga</span>`;
      pagar.setAttribute("aria-label", `Marcar ${nome} como paga`);
      pagar.addEventListener("click", async () => {
        pagar.disabled = true;
        const r = await apiFetch(`/api/contas-pessoais/${c.id}/paga`, { method: "POST" });
        if (r) loadContasPessoais();
        else pagar.disabled = false;
      });
      acoes.appendChild(pagar);
    }
    acoes.appendChild(botaoApagarFinancas(`/api/contas-pessoais/${c.id}`, li, nome));
    li.appendChild(acoes);
    lista.appendChild(li);
  });
}

let salvandoContaPessoal = false;
$("#conta-pessoal-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (salvandoContaPessoal) return;
  const nome = $("#conta-pessoal-nome").value.trim();
  const dia = lerInteiroFinancas($("#conta-pessoal-dia"));
  const valor = lerValorFinancas($("#conta-pessoal-valor"));
  if (!nome) return mostrarErroSheet("conta-pessoal-erro", "Da um nome pra conta.");
  if (dia === null || dia < 1 || dia > 31)
    return mostrarErroSheet("conta-pessoal-erro", "Dia do vencimento vai de 1 a 31 (dia 31 em mês curto vence no último dia).");
  if (valor !== null && !valorValidoFinancas(valor))
    return mostrarErroSheet("conta-pessoal-erro", "Valor precisa ser um número maior que zero (ou deixa em branco).");
  $("#conta-pessoal-erro").hidden = true;
  const btn = $("#conta-pessoal-btn");
  salvandoContaPessoal = true;
  setBotaoCarregando(btn, true, "Salvando...");
  const r = await apiFetch("/api/contas-pessoais", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nome: nome.slice(0, 80), dia_vencimento: dia, valor }),
  });
  setBotaoCarregando(btn, false, "Salvar conta");
  salvandoContaPessoal = false;
  if (!r) return mostrarErroSheet("conta-pessoal-erro", "Não consegui salvar agora. Confere os campos e tenta de novo.");
  sucessoSheetFinancas($("#conta-pessoal-form"));
  loadContasPessoais();
});
