// static/js/secoes/hoje/rotina.js - Secao hoje > rotina (HTML: templates/secoes/hoje/rotina.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 30-70.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

function rotinaVisivel(momento) {
  const h = new Date().getHours();
  return momento === "manha" ? h >= 5 && h < 12 : h >= 20 || h < 3;
}

async function loadRotina() {
  const data = await apiFetch("/api/rotina");
  if (!data) return;
  const box = $("#rotina-box");
  const completa = data.total > 0 && data.feitos === data.total;
  box.hidden = !rotinaVisivel(data.momento) || data.total === 0 || completa;
  if (box.hidden) return;

  $("#rotina-titulo").textContent = data.momento === "manha" ? "Rotina da manha" : "Rotina da noite";
  $("#rotina-progresso").textContent = `${data.feitos} de ${data.total}`;
  const lista = $("#rotina-lista");
  lista.innerHTML = "";
  data.itens.forEach((item) => {
    const li = criarEl("li", "checklist-item" + (item.feito ? " feito" : ""));
    const label = criarEl("label");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = item.feito;
    cb.addEventListener("change", async () => {
      const r = await apiFetch(`/api/rotina/${item.id}/alternar`, { method: "POST" });
      if (!r) {
        cb.checked = !cb.checked;
        return;
      }
      if (r.feito) vibrar(20);
      loadRotina();
    });
    label.appendChild(cb);
    label.appendChild(criarEl("span", null, item.texto));
    li.appendChild(label);
    lista.appendChild(li);
  });
}

// ---- Check-in de 1 toque ----
