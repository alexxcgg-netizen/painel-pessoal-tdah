// Renderizadores dos types do contrato de cards (docs/CARDS.md). Cada um e
// uma funcao pura (data, card, ctx) -> string HTML registrada no registro de
// static/js/cards.js. Todo texto vindo de `data` passa por esc().
(function (raiz) {
  "use strict";
  const Cards = raiz.Cards || (typeof require === "function" ? require("./cards.js") : null);
  if (!Cards) return;
})(typeof window !== "undefined" ? window : globalThis);
