// static/js/secoes/vida/manutencao.js - Secao vida > manutencao (HTML: templates/secoes/vida/manutencao.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 1087-1171.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

const ROTULO_TIPO_MANUTENCAO = { casa: "Casa", carro: "Carro", equipamento: "Equipamento", outro: "Outro" };

function textoProximaManutencaoCarro(m) {
  const partes = [];
  if (m.km != null) partes.push(`${m.km} km na hora`);
  if (m.proxima_em_km != null) partes.push(`próxima em ${m.proxima_em_km} km`);
  if (m.proxima_em_data) partes.push(`próxima em ${fmtDataBr(m.proxima_em_data)}`);
  return partes;
}

async function loadManutencoes() {
  const itens = await apiFetch("/api/manutencoes");
  // Fase 7 C3a: resposta fora do formato (ex.: {} no lugar de lista) nao derruba a secao.
  if (!Array.isArray(itens)) return;
  const lista = $("#lista-manutencoes");
  lista.innerHTML = "";
  $("#manutencoes-vazio").hidden = itens.length > 0;
  itens.forEach((m) => {
    const rotuloTipo = ROTULO_TIPO_MANUTENCAO[m.tipo] || "Outro";
    if (m.tipo === "carro") {
      lista.appendChild(
        itemSimples(
          m.item,
          [rotuloTipo, fmtDataBr(m.data), ...textoProximaManutencaoCarro(m)],
          [(el) => botaoApagar(`/api/manutencoes/${m.id}`, el)],
          "lista-item"
        )
      );
      return;
    }
    const quando =
      m.dias_ate < 0
        ? `passou do prazo ha ${-m.dias_ate} dia(s)`
        : m.dias_ate === 0
        ? "vence hoje"
        : `próxima em ${fmtDataBr(m.proxima)} (${m.dias_ate} dias)`;
    lista.appendChild(
      itemSimples(m.item, [rotuloTipo, `a cada ${m.intervalo_meses} mes(es)`, quando], [
        botaoAcao("feita hoje", async () => {
          const ok = await jsonPost(`/api/manutencoes/${m.id}/feita`);
          if (ok) loadManutencoes();
          return ok;
        }),
        (el) => botaoApagar(`/api/manutencoes/${m.id}`, el),
      ], "lista-item" + (m.dias_ate <= 7 ? " item-atencao" : ""))
    );
  });
}

$("#manutencao-tipo").addEventListener("change", () => {
  const carro = $("#manutencao-tipo").value === "carro";
  $("#manutencao-campos-carro").hidden = !carro;
  $("#manutencao-campos-tempo").hidden = carro;
});

// Fase 7 V4: botao "Adicionar manutenção" abre o formulario num bottom-sheet
// (static/js/ui/bottom-sheet.js, faixa V0d). Enquanto essa faixa nao chega na
// integracao, cai no fallback inline (so hidden) - retestado depois do merge
// com origin/fase7/integracao.
$("#manutencao-abrir-btn").addEventListener("click", () => {
  const sheet = $("#sheet-manutencao");
  // Fase 7 C3a: toque durante a animacao de fechar (240ms) e ignorado - reabrir nessa
  // janela deixava o sheet preso (bug do V0d anotado no progress da C3a).
  if (sheet.classList.contains("bottom-sheet--fechando")) return;
  if (window.abrirBottomSheet) window.abrirBottomSheet(sheet);
  else sheet.hidden = false;
});

$("#manutencao-cancelar-btn").addEventListener("click", () => {
  $("#manutencao-form").reset();
  const sheet = $("#sheet-manutencao");
  if (window.fecharBottomSheet) window.fecharBottomSheet(sheet);
  else sheet.hidden = true;
});

ligarForm("#manutencao-form", "#manutencao-btn", "Adicionar", () => {
  const tipo = $("#manutencao-tipo").value;
  const item = $("#manutencao-item").value.trim();
  if (!item) {
    mostrarErro("Confere o item.");
    return null;
  }
  if (tipo === "carro") {
    const data = $("#manutencao-data").value;
    if (!data) {
      mostrarErro("Confere a data.");
      return null;
    }
    const km = $("#manutencao-km").value;
    const proximaKm = $("#manutencao-proxima-km").value;
    return {
      tipo, item, data,
      km: km === "" ? null : Number(km),
      proxima_em_km: proximaKm === "" ? null : Number(proximaKm),
      proxima_em_data: $("#manutencao-proxima-data").value || null,
    };
  }
  const meses = Number($("#manutencao-meses").value);
  if (!(meses >= 1 && meses <= 120)) {
    mostrarErro("Confere o intervalo (1 a 120 meses).");
    return null;
  }
  return { tipo, item, intervalo_meses: meses, ultima_vez: $("#manutencao-ultima").value || null };
}, "/api/manutencoes", (r) => {
  const sheet = $("#sheet-manutencao");
  if (window.fecharBottomSheet) window.fecharBottomSheet(sheet);
  else sheet.hidden = true;
  loadManutencoes(r);
});

// ---- Fase 5 + Fase 6 (US-F5): garantia de produtos ----
