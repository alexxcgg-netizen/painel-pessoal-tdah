// static/js/secoes/vida/mensagem-dificil.js - Secao vida > mensagem-dificil (HTML: templates/secoes/vida/mensagem-dificil.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 1563-1615.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

$("#mensagem-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const situacao = $("#mensagem-situacao").value.trim();
  if (!situacao) return;
  const btn = $("#mensagem-btn");
  setBotaoCarregando(btn, true, "escrevendo...");
  const r = await jsonPost("/api/mensagem-dificil", { situacao, para_quem: $("#mensagem-para").value.trim() });
  setBotaoCarregando(btn, false, "Escrever pra mim");
  if (!r) return;
  // Fase 6 (US-F9): 2 paragrafos rotulados empilhados viraram 2 cartoes lado
  // a lado (empilham no mobile por causa do wrap) - cada um com selo de qual
  // versao e e um botao de copiar com icone (mesmo padrao .btn-com-icone do
  // resto do app, em vez do link de texto solto que nao dava nenhum retorno
  // visual alem de trocar a palavra).
  const box = $("#mensagem-resultado");
  box.innerHTML = "";
  box.hidden = false;
  box.className = "card-resultado mensagem-cards";
  [
    ["direta", "Direta", "mensagem-card-direta"],
    ["gentil", "Mais gentil", "mensagem-card-gentil"],
  ].forEach(([chave, rotulo, classeCor]) => {
    const texto = r[chave];
    if (!texto) return;
    const card = criarEl("div", `mensagem-card ${classeCor}`);

    const topo = criarEl("div", "mensagem-card-topo");
    topo.appendChild(criarEl("span", "item-tag-tarefa", rotulo));
    const copiar = criarEl("button", "btn-com-icone mensagem-copiar");
    copiar.type = "button";
    copiar.innerHTML = `${ICONE_COPIAR}Copiar`;
    copiar.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(texto);
        copiar.innerHTML = `${ICONE_CHECK}Copiado`;
        pulsarSucesso(copiar);
        setTimeout(() => {
          copiar.innerHTML = `${ICONE_COPIAR}Copiar`;
        }, 1800);
      } catch {
        copiar.textContent = "não deu - segura no texto";
      }
    });
    topo.appendChild(copiar);
    card.appendChild(topo);

    card.appendChild(criarEl("p", "mensagem-texto", texto));
    box.appendChild(card);
  });
});

// ---- Fase 3: quero aprender ----
