// static/js/secoes/vida/garantia.js - Secao vida > garantia (HTML: templates/secoes/vida/garantia.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 1172-1262.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

// Chip curto de status - a mesma logica de "<=15 dias = atencao" que ja
// existia (classe item-atencao), so com um rotulo mais claro que "vence em
// (X dias)" no meio da frase.
function garantiaChip(g) {
  if (g.dias_ate < 0) return { texto: `venceu ha ${-g.dias_ate}d`, classe: "vencida" };
  if (g.dias_ate === 0) return { texto: "vence hoje", classe: "vencida" };
  if (g.dias_ate <= 15) return { texto: `vence em ${g.dias_ate}d`, classe: "alerta" };
  return { texto: `vence em ${g.dias_ate}d`, classe: "ok" };
}

// Fracao do prazo de garantia ja decorrida (0..1) - so matematica de data
// local, sem endpoint novo (data_compra/vencimento ja vinham no /api/garantias).
function garantiaFracaoDecorrida(g) {
  const compra = new Date(`${g.data_compra}T00:00:00`).getTime();
  const vence = new Date(`${g.vencimento}T00:00:00`).getTime();
  if (!(vence > compra)) return 1;
  return Math.min(1, Math.max(0, (Date.now() - compra) / (vence - compra)));
}

async function loadGarantias() {
  const itens = await apiFetch("/api/garantias");
  if (!itens) return;
  const lista = $("#lista-garantias");
  lista.innerHTML = "";
  $("#garantias-vazio").hidden = itens.length > 0;
  // O que vence mais logo primeiro (inclusive ja vencido) - "destaque do que
  // vence logo" e o pedido explicito da US-F5, a ordem por data de compra
  // que a API devolve nao ajuda a bater o olho nisso.
  itens
    .slice()
    .sort((a, b) => a.dias_ate - b.dias_ate)
    .forEach((g) => {
      const li = criarEl("li", "item lista-item garantia-item" + (g.dias_ate <= 15 ? " item-atencao" : ""));
      const linha = criarEl("div", "item-linha");

      const wrap = criarEl("div");
      const tituloLinha = criarEl("div", "pessoa-titulo-linha");
      tituloLinha.appendChild(criarEl("span", "item-titulo", g.produto));
      const chip = garantiaChip(g);
      tituloLinha.appendChild(criarEl("span", `garantia-chip garantia-chip-${chip.classe}`, chip.texto));
      wrap.appendChild(tituloLinha);
      wrap.appendChild(
        criarEl(
          "span",
          "item-quando",
          `${g.prazo_garantia_meses} mes(es) - comprado em ${fmtDataBr(g.data_compra)}, vence ${fmtDataBr(g.vencimento)}`
        )
      );
      const trilho = criarEl("div", "garantia-barra-trilho");
      const preenchido = criarEl("div", `garantia-barra-preenchido garantia-barra-${chip.classe}`);
      preenchido.style.width = `${Math.round(garantiaFracaoDecorrida(g) * 100)}%`;
      trilho.appendChild(preenchido);
      wrap.appendChild(trilho);
      linha.appendChild(wrap);

      const acoes = criarEl("div", "item-acoes");
      acoes.appendChild(botaoApagar(`/api/garantias/${g.id}`, li));
      linha.appendChild(acoes);

      li.appendChild(linha);
      lista.appendChild(li);
    });
}

// Fase 7 V4: botao "Adicionar produto" abre o formulario num bottom-sheet
// (static/js/ui/bottom-sheet.js, faixa V0d). Enquanto essa faixa nao chega na
// integracao, cai no fallback inline (so hidden/classe) - retestado depois do
// merge com origin/fase7/integracao.
$("#garantia-abrir-btn").addEventListener("click", () => {
  const sheet = $("#sheet-garantia");
  if (window.abrirBottomSheet) window.abrirBottomSheet(sheet);
  else sheet.hidden = false;
});

$("#garantia-cancelar-btn").addEventListener("click", () => {
  $("#garantia-form").reset();
  const sheet = $("#sheet-garantia");
  if (window.fecharBottomSheet) window.fecharBottomSheet(sheet);
  else sheet.hidden = true;
});

$("#garantia-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const produto = $("#garantia-produto").value.trim();
  const dataCompra = $("#garantia-data-compra").value;
  const prazo = Number($("#garantia-prazo").value);
  if (!produto || !dataCompra || !(prazo >= 1 && prazo <= 600)) {
    mostrarErro("Confere o produto, a data de compra e o prazo de garantia.");
    return;
  }
  const arquivo = $("#garantia-anexo").files[0];
  const btn = $("#garantia-btn");
  setBotaoCarregando(btn, true, "salvando...");
  const form = new FormData();
  form.append("produto", produto);
  form.append("data_compra", dataCompra);
  form.append("prazo_garantia_meses", String(prazo));
  if (arquivo) form.append("nota_fiscal", arquivo);
  const r = await apiFetch("/api/garantias", { method: "POST", body: form });
  setBotaoCarregando(btn, false, "Adicionar");
  if (!r) return;
  $("#garantia-form").reset();
  const sheet = $("#sheet-garantia");
  if (window.fecharBottomSheet) window.fecharBottomSheet(sheet);
  else sheet.hidden = true;
  pulsarSucesso($("#garantia-produto"));
  loadGarantias();
});

// ---- Fase 2: viagens e lugares ----
