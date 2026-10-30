// Medalha na hora (lab v4, Grupo G, 2026-10-30): no treino ao vivo, a caixinha que bate o recorde de
// carga (1RM estimado, Epley) faz cair uma medalha holografica no proprio card. O brilho segue o dedo.
// Protótipo aprovado: docs/prototipos/laboratorio-v4 (ideia "medalha"). Servidor: medalha.py.
//
//   CardsMedalha.mini(m)        -> HTML da moedinha na linha do exercicio (estado final, historico)
//   CardsMedalha.cair(card, m)  -> faz a medalha grande cair no card .tv (resposta nova)
//   CardsMedalha.tirar(card, i) -> recolhe a medalha se desmarcou o exercicio que a ganhou
//
// Sem DOM em Node: so mini()/palcoHTML() sao puros (testados em tests/js/cards_fechamento.test.js).
(function (raiz) {
  "use strict";
  const esc = (v) => (v == null ? "" : String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;"));
  const num = (v) => String(Math.round(Number(v) * 10) / 10).replace(".", ",");
  const reduz = () => typeof raiz.matchMedia === "function" && raiz.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function mini(m) {
    if (!m || !Number.isFinite(Number(m.rm))) return "";
    const ganho = Number.isFinite(Number(m.ganho)) && m.ganho > 0 ? `<em>+${esc(num(m.ganho))}</em>` : "";
    return (
      `<span class="tv-med" role="img" aria-label="Recorde: 1RM estimado de ${esc(num(m.rm))} kg"><i aria-hidden="true"></i>${ganho}</span>`
    );
  }

  // palco = onde a medalha cai. `on` entra depois (a altura anima de 0 e a medalha cai com mola).
  function palcoHTML(m) {
    const legenda = m.legenda || "";
    return (
      `<div class="md-palco" data-i="${esc(m.i)}">` +
      `<div class="md-med"><div class="md-holo"></div><div class="md-txt"><small>RECORDE</small><b>${esc(num(m.rm))} kg</b><span>1RM estimado</span></div></div>` +
      `<p class="md-leg"><strong>${esc(m.nome || "")}</strong>${legenda ? `<br>${esc(legenda)}` : ""}</p>` +
      `</div>`
    );
  }

  function seguirDedo(palco) {
    const med = palco.querySelector(".md-med");
    if (!med) return;
    palco.addEventListener("pointermove", (e) => {
      const r = med.getBoundingClientRect();
      if (!r.width) return;
      const x = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
      const y = Math.max(0, Math.min(1, (e.clientY - r.top) / r.height));
      med.style.setProperty("--mx", `${(x * 100).toFixed(1)}%`);
      med.style.setProperty("--my", `${(y * 100).toFixed(1)}%`);
      med.style.setProperty("--ang", `${(x * 180).toFixed(1)}deg`);
    });
  }

  function cair(cardEl, m) {
    if (!cardEl || !m) return;
    const anterior = cardEl.querySelector(".md-palco");
    if (anterior) anterior.remove();
    const ancora = cardEl.querySelector(".tv-barra") || cardEl.querySelector(".card-titulo");
    if (!ancora) return;
    ancora.insertAdjacentHTML("afterend", palcoHTML(m));
    const palco = cardEl.querySelector(".md-palco");
    seguirDedo(palco);
    // a moedinha da linha tambem aparece agora (fica gravada)
    const li = cardEl.querySelectorAll(".tv-ex")[m.i];
    const nome = li && li.querySelector(".tv-nome");
    if (nome && !li.querySelector(".tv-med")) nome.insertAdjacentHTML("afterbegin", mini(m));
    if (reduz()) {
      palco.classList.add("on");
      return;
    }
    void palco.offsetHeight; // forca o layout: a altura 0 -> 210 precisa de um quadro de partida
    requestAnimationFrame(() => palco.classList.add("on"));
  }

  function tirar(cardEl, i) {
    if (!cardEl) return;
    const palco = cardEl.querySelector(`.md-palco[data-i="${Number(i)}"]`);
    if (palco) palco.remove();
    const li = cardEl.querySelectorAll(".tv-ex")[i];
    const mini_ = li && li.querySelector(".tv-med");
    if (mini_) mini_.remove();
  }

  const api = { mini, palcoHTML, cair, tirar };
  raiz.CardsMedalha = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
