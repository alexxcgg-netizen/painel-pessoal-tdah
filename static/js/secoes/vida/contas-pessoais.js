// static/js/secoes/vida/contas-pessoais.js - Secao vida > contas-pessoais (HTML: templates/secoes/vida/contas-pessoais.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 389-455.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadContasPessoais() {
  const contas = await apiFetch("/api/contas-pessoais");
  if (!contas) return;
  const lista = $("#lista-contas-pessoais");
  lista.innerHTML = "";
  $("#contas-pessoais-vazio").hidden = contas.length > 0;
  contas.forEach((c) => {
    const urgente = !c.paga && c.dias_ate_vencer <= 3;
    const li = criarEl("li", "item" + (urgente ? " item-atencao" : ""));
    const linha = criarEl("div", "item-linha");
    const wrap = criarEl("div");
    const titulo = c.valor != null ? `${c.nome} - ${fmtMoeda(c.valor)}` : c.nome;
    wrap.appendChild(criarEl("span", "item-titulo", titulo));
    const quando = c.paga
      ? `paga (vencimento ${fmtDataBr(c.proximo_vencimento)})`
      : c.dias_ate_vencer < 0
      ? `venceu ${fmtDataBr(c.proximo_vencimento)} - ha ${-c.dias_ate_vencer} dia(s)`
      : c.dias_ate_vencer === 0
      ? "vence hoje"
      : `vence ${fmtDataBr(c.proximo_vencimento)} - em ${c.dias_ate_vencer} dia(s)`;
    wrap.appendChild(criarEl("span", "item-quando", quando));
    linha.appendChild(wrap);

    const acoes = criarEl("div", "item-acoes");
    if (!c.paga) {
      const pagar = criarEl("button", "primario btn-com-icone");
      pagar.innerHTML = `${ICONE_CHECK}paga`;
      pagar.addEventListener("click", async () => {
        pagar.disabled = true;
        const r = await apiFetch(`/api/contas-pessoais/${c.id}/paga`, { method: "POST" });
        if (r) loadContasPessoais();
        else pagar.disabled = false;
      });
      acoes.appendChild(pagar);
    }
    acoes.appendChild(botaoApagar(`/api/contas-pessoais/${c.id}`, li));
    linha.appendChild(acoes);
    li.appendChild(linha);
    lista.appendChild(li);
  });
}

$("#conta-pessoal-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const nome = $("#conta-pessoal-nome").value.trim();
  const dia = Number($("#conta-pessoal-dia").value);
  const valorTxt = $("#conta-pessoal-valor").value.trim();
  if (!nome || !(dia >= 1 && dia <= 31)) {
    mostrarErro("Confere o nome e o dia de vencimento (1 a 31).");
    return;
  }
  const btn = $("#conta-pessoal-btn");
  setBotaoCarregando(btn, true, "salvando...");
  const r = await apiFetch("/api/contas-pessoais", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nome, dia_vencimento: dia, valor: valorTxt ? Number(valorTxt) : null }),
  });
  setBotaoCarregando(btn, false, "Adicionar");
  if (!r) return;
  ["#conta-pessoal-nome", "#conta-pessoal-dia", "#conta-pessoal-valor"].forEach((s) => ($(s).value = ""));
  pulsarSucesso($("#conta-pessoal-nome"));
  loadContasPessoais();
});

// ---- Assinaturas: "ainda usa?" ----
