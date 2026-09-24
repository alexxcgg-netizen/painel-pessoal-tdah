// static/js/secoes/vida/ainda-usa.js - Secao vida > ainda-usa (HTML: templates/secoes/vida/ainda-usa.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 456-501.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadAssinaturasRevisao() {
  const pendentes = await apiFetch("/api/assinaturas/revisao");
  if (!pendentes) return;
  $("#assinaturas-box").hidden = pendentes.length === 0;
  const lista = $("#lista-assinaturas");
  lista.innerHTML = "";
  pendentes.forEach((a) => {
    const li = criarEl("li", "item");
    const linha = criarEl("div", "item-linha");
    const wrap = criarEl("div");
    wrap.appendChild(criarEl("span", "item-titulo", a.descricao));
    wrap.appendChild(criarEl("span", "item-quando", `${fmtMoeda(a.valor)} por mes`));
    linha.appendChild(wrap);
    const acoes = criarEl("div", "item-acoes");
    [
      ["usa", "uso"],
      ["nao_usa", "nao uso mais"],
    ].forEach(([resposta, rotulo]) => {
      const b = criarEl("button", resposta === "usa" ? "btn-com-icone" : "primario btn-com-icone", rotulo);
      b.addEventListener("click", async () => {
        b.disabled = true;
        const r = await apiFetch("/api/assinaturas/revisao", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ descricao: a.descricao, valor: a.valor, resposta }),
        });
        if (!r) {
          b.disabled = false;
          return;
        }
        li.classList.add("saindo");
        setTimeout(() => {
          li.remove();
          if (!$("#lista-assinaturas").children.length) $("#assinaturas-box").hidden = true;
        }, 250);
      });
      acoes.appendChild(b);
    });
    linha.appendChild(acoes);
    li.appendChild(linha);
    lista.appendChild(li);
  });
}

// ---- Vale a pena? ----
