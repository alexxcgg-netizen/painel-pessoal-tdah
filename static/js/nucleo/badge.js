// static/js/nucleo/badge.js - numero no icone do app (leva Lab v4, ideia "badge"; servidor em badge.py).
// Badging API: funciona em web app da tela de inicio (iOS 16.4+) com a permissao de notificacao ja dada.
// App aberto: este arquivo poe o numero (ao abrir, ao voltar pra tela e logo depois de qualquer escrita).
// App fechado: o service worker poe o numero que vem dentro de cada aviso push.
// Script classico, escopo global (templates/scripts.html). Sem a API (desktop, Safari comum) nao faz nada.

const Badge = (() => {
  let ultimo = null;
  let timer = null;

  function suportado() {
    return typeof navigator !== "undefined" && typeof navigator.setAppBadge === "function";
  }

  // n inteiro >= 0; 0 apaga o numero (clearAppBadge). Nunca levanta: badge e enfeite util, nao pode quebrar tela.
  function aplicar(n) {
    const v = Number(n);
    if (!Number.isFinite(v) || v < 0) return false;
    ultimo = Math.floor(v);
    if (!suportado()) return false;
    try {
      const p = ultimo > 0 ? navigator.setAppBadge(ultimo) : navigator.clearAppBadge && navigator.clearAppBadge();
      if (p && typeof p.catch === "function") p.catch(() => {});
      return true;
    } catch (e) {
      return false;
    }
  }

  async function atualizar() {
    if (!suportado() || typeof fetch !== "function") return null;
    try {
      const r = await fetch("/api/badge", { credentials: "same-origin" });
      if (!r.ok) return null;
      const j = await r.json();
      if (j && typeof j.n === "number") aplicar(j.n);
      return j && typeof j.n === "number" ? j.n : null;
    } catch (e) {
      return null;
    }
  }

  // depois de escrever (concluir, criar, adiar): espera a rajada acabar e confere o numero no servidor
  function atualizarDepois(ms) {
    if (!suportado()) return;
    clearTimeout(timer);
    timer = setTimeout(atualizar, ms == null ? 700 : ms);
  }

  if (typeof document !== "undefined") {
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) atualizarDepois(0); // vai pro fundo: deixa o numero certo no icone
    });
  }

  return { aplicar, atualizar, atualizarDepois, suportado, ultimo: () => ultimo };
})();
if (typeof window !== "undefined") window.Badge = Badge;
