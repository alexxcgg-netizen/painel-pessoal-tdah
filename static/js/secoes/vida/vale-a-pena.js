// static/js/secoes/vida/vale-a-pena.js - Secao vida > vale-a-pena (HTML: templates/secoes/vida/vale-a-pena.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 502-585.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

// Fase 6 (US-F9): a inclinacao ('vale'/'nao_vale'/'depende', ja vem pronta
// do prompt - claude_client.DECISAO_PROMPT, ajustado na faixa E1) virou um
// selo de veredito no TOPO do card, com cor propria (semaforo: verde/
// vermelho/ambar) em vez de uma frase "Inclina pra: X" perdida no fim do
// texto corrido - bate o pedido "recomendacao direta", ve-se de relance sem
// ler o resto.
const INCLINACAO_INFO = {
  vale: { rotulo: "Vale a pena", classe: "decisao-veredito-vale" },
  nao_vale: { rotulo: "Nao vale a pena", classe: "decisao-veredito-nao-vale" },
  depende: { rotulo: "Depende", classe: "decisao-veredito-depende" },
};

function renderDecisao(analise) {
  const box = $("#decisao-resultado");
  box.innerHTML = "";
  box.hidden = false;

  const info = INCLINACAO_INFO[analise.inclinacao];
  if (info) {
    const veredito = criarEl("div", `decisao-veredito ${info.classe}`);
    veredito.appendChild(criarEl("span", "decisao-veredito-selo", info.rotulo));
    if (analise.porque) veredito.appendChild(criarEl("span", "decisao-veredito-porque", analise.porque));
    box.appendChild(veredito);
  }

  if (analise.resumo) box.appendChild(criarEl("p", "decisao-resumo", analise.resumo));

  // Pros/contras eram 2 listas empilhadas com o mesmo rotulo cinza - viram
  // colunas lado a lado (empilham no mobile), cada uma com a cor "fatos
  // organizados" pedida (US-F9): verde pra pros, ambar pra contras (nunca
  // --danger aqui - a paleta reserva vermelho so pro veredito negativo/erro
  // de verdade, nao pra "contra" que pode ser so um detalhe menor).
  const pros = Array.isArray(analise.pros) ? analise.pros : [];
  const contras = Array.isArray(analise.contras) ? analise.contras : [];
  if (pros.length || contras.length) {
    const grade = criarEl("div", "decisao-grade");
    [
      [pros, "Pros", "decisao-coluna-pros"],
      [contras, "Contras", "decisao-coluna-contras"],
    ].forEach(([itens, rotulo, classeCor]) => {
      if (!itens.length) return;
      const coluna = criarEl("div", `decisao-coluna ${classeCor}`);
      coluna.appendChild(criarEl("p", "decisao-rotulo", rotulo));
      const ul = criarEl("ul", "decisao-lista");
      itens.forEach((i) => ul.appendChild(criarEl("li", null, String(i))));
      coluna.appendChild(ul);
      grade.appendChild(coluna);
    });
    box.appendChild(grade);
  }

  const perguntas = Array.isArray(analise.perguntas_chave) ? analise.perguntas_chave : [];
  if (perguntas.length) {
    box.appendChild(criarEl("p", "decisao-rotulo", "O que mudaria a resposta"));
    const ul = criarEl("ul", "decisao-lista");
    perguntas.forEach((p) => ul.appendChild(criarEl("li", null, String(p))));
    box.appendChild(ul);
  }
}

function aplicarModoVisitanteNaDecisao(ativo) {
  $("#decisao-oculto-visitante").hidden = !ativo;
  $("#decisao-form").hidden = ativo;
  if (ativo) $("#decisao-resultado").hidden = true;
}
document.addEventListener("modo-visitante-mudou", (e) => aplicarModoVisitanteNaDecisao(e.detail.ativo));

$("#decisao-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const pergunta = $("#decisao-pergunta").value.trim();
  if (!pergunta) return;
  const btn = $("#decisao-btn");
  setBotaoCarregando(btn, true, "pensando...");
  const r = await apiFetch("/api/decisao", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pergunta }),
  });
  setBotaoCarregando(btn, false, "Analisar");
  if (r) renderDecisao(r.analise);
});

// ---- Fase 2: pra responder ----
