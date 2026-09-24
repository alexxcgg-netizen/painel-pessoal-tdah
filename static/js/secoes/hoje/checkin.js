// static/js/secoes/hoje/checkin.js - Secao hoje > checkin (HTML: templates/secoes/hoje/checkin.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 71-131.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

const CHECKIN_CAMPOS = [
  ["energia", "Energia"],
  ["sono", "Sono"],
  ["humor", "Humor"],
];

if (typeof FilaOffline !== "undefined") {
  // Assim que um check-in enfileirado sincroniza de verdade, recarrega a
  // caixa pra refletir o estado real vindo do servidor.
  FilaOffline.registrarCallback("checkin", () => loadCheckin());
}

async function loadCheckin() {
  const data = await apiFetch("/api/checkin/hoje");
  if (!data) return;
  const atual = data.checkin || {};
  const completo = CHECKIN_CAMPOS.every(([c]) => atual[c]);
  $("#checkin-box").hidden = completo;
  if (completo) return;

  const linhas = $("#checkin-linhas");
  linhas.innerHTML = "";
  CHECKIN_CAMPOS.forEach(([campo, rotulo]) => {
    const linha = criarEl("div", "checkin-linha");
    linha.appendChild(criarEl("span", "checkin-rotulo", rotulo));
    const opcoes = criarEl("div", "checkin-opcoes");
    ["ruim", "ok", "bom"].forEach((valor) => {
      const b = criarEl("button", "checkin-opcao" + (atual[campo] === valor ? " escolhida" : ""), valor);
      b.type = "button";
      b.dataset.valor = valor;
      b.addEventListener("click", async () => {
        const r = await apiFetch(
          "/api/checkin",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ [campo]: valor }),
          },
          { tipo: "checkin" }
        );
        if (!r) return;
        vibrar(15);
        if (r.__enfileirado) {
          // otimista: marca a opcao escolhida na hora - o checkin e um
          // upsert por dia no servidor, entao reenviar o mesmo valor depois
          // (quando sincronizar) nunca duplica nada.
          opcoes.querySelectorAll(".checkin-opcao").forEach((el) => el.classList.remove("escolhida"));
          b.classList.add("escolhida");
          return;
        }
        loadCheckin();
      });
      opcoes.appendChild(b);
    });
    linha.appendChild(opcoes);
    linhas.appendChild(linha);
  });
}

// ---- So o essencial ----
