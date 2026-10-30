// static/js/secoes/aviacao/painel-de-voo.js - Secao aviacao > painel de voo (HTML: templates/secoes/aviacao/painel-de-voo.html).
// Laboratorio v4, Grupo F (30/10/2026): radar de validades, rumo ao cheque, banca, voo de cadeira, vento na pista e
// passaporte. Os cards sao os MESMOS do chat (static/js/cards-aviacao-lab.js); aqui so pede cada um pro servidor
// (GET /api/aviacao/card/<qual>), desenha e liga os cliques. Nada de conta no front.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

const PAINEL_DE_VOO = ["radar", "cheque", "banca", "chair", "vento", "passaporte"];
let painelDeVooLigado = false;

async function carregarPainelDeVoo() {
  const caixa = document.getElementById("aviacao-lab-cards");
  const aviso = document.getElementById("painel-de-voo-carregando");
  if (!caixa || typeof Cards === "undefined") return;
  if (!painelDeVooLigado) {
    painelDeVooLigado = true;
    Cards.ligar(caixa, {
      apiFetch,
      showTab: typeof showTab === "function" ? showTab : undefined,
      aoMudar: () => {},
    });
  }
  // um lugar por card, na ordem; cada um entra quando chega (o vento espera o METAR e nao segura os outros)
  if (!caixa.children.length) {
    PAINEL_DE_VOO.forEach((q) => {
      const lugar = document.createElement("div");
      lugar.className = "aviacao-lab-lugar";
      lugar.dataset.qual = q;
      caixa.appendChild(lugar);
    });
  }
  let chegou = 0;
  await Promise.all(
    PAINEL_DE_VOO.map(async (qual) => {
      const r = await apiFetch(`/api/aviacao/card/${qual}`);
      const lugar = caixa.querySelector(`[data-qual="${qual}"]`);
      if (!lugar) return;
      if (r && r.ok && r.card) {
        const novo = !lugar.firstChild;
        lugar.innerHTML = Cards.renderizarCardHTML(r.card, { agora: new Date() });
        // so na primeira vez que o card aparece: entra animado como no chat (reabrir a aba nao repete)
        if (novo && typeof CardsPremium !== "undefined") CardsPremium.animar(lugar);
        chegou += 1;
      } else if (!lugar.firstChild) {
        lugar.innerHTML = '<p class="vazio">Não consegui carregar este card agora.</p>';
      }
      if (aviso) aviso.hidden = true;
    })
  );
  if (aviso) aviso.hidden = true;
}

document.addEventListener("aba:aberta", (e) => {
  if (e.detail && e.detail.aba === "aviacao") carregarPainelDeVoo();
});
