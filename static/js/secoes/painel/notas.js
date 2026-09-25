// static/js/secoes/painel/notas.js - Secao painel > notas (HTML: templates/secoes/painel/notas.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 1987-2047.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadNotas() {
  const notas = await apiFetch("/api/notas");
  if (!notas) return;

  const list = $("#lista-notas");
  list.innerHTML = "";
  $("#notas-vazio").hidden = notas.length > 0;

  notas.forEach((n) => {
    const li = document.createElement("li");
    li.className = "item";

    const linha = document.createElement("div");
    linha.className = "item-linha";

    const tituloWrap = document.createElement("div");
    const titulo = document.createElement("span");
    titulo.className = "item-titulo";
    titulo.textContent = n.titulo;
    tituloWrap.appendChild(titulo);

    const corpo = document.createElement("span");
    corpo.className = "item-quando";
    corpo.textContent = n.corpo.length > 140 ? `${n.corpo.slice(0, 140)}...` : n.corpo;
    tituloWrap.appendChild(corpo);

    if (n.tags) {
      const tags = document.createElement("span");
      tags.className = "item-quando";
      tags.textContent = n.tags
        .split(",")
        .map((t) => `#${t}`)
        .join(" ");
      tituloWrap.appendChild(tags);
    }
    linha.appendChild(tituloWrap);

    const acoes = document.createElement("div");
    acoes.className = "item-acoes";
    const apagarBtn = document.createElement("button");
    apagarBtn.className = "btn-com-icone";
    apagarBtn.innerHTML = ICONE_TRASH;
    apagarBtn.setAttribute("aria-label", "Apagar");
    apagarBtn.addEventListener("click", async () => {
      apagarBtn.disabled = true;
      const ok = await apiFetch(`/api/notas/${n.id}`, { method: "DELETE" });
      if (ok) {
        li.classList.add("saindo");
        setTimeout(() => li.remove(), 250);
      } else {
        apagarBtn.disabled = false;
      }
    });
    acoes.appendChild(apagarBtn);
    linha.appendChild(acoes);

    li.appendChild(linha);
    list.appendChild(li);
  });
}
