// 2026-11-06: marcou Feito/Desfazer dentro do app do iPhone e a ilha (atividade ao vivo) continuava.
// A pagina agora avisa o app (window.webkit.messageHandlers.painel) depois de qualquer escrita;
// o app confere a atividade e os avisos (native/ios/App/PainelApp.swift, AvisoDaPagina).
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const CODIGO = fs.readFileSync(path.join(__dirname, "..", "..", "static", "js", "nucleo", "api.js"), "utf8");

function montar({ comCanal = true, status = 200 } = {}) {
  const recados = [];
  const banner = { hidden: true, classList: { remove() {} } };
  const ctx = {
    console,
    setTimeout,
    clearTimeout,
    AbortController,
    $: () => banner,
    fetch: async () => ({ ok: status < 400, status, json: async () => ({ ok: true }) }),
    window: comCanal ? { webkit: { messageHandlers: { painel: { postMessage: (m) => recados.push(m) } } } } : {},
  };
  vm.createContext(ctx);
  vm.runInContext(CODIGO, ctx);
  return { ctx, recados };
}

const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

test("escrita avisa o app uma vez so, mesmo com varias seguidas (Feito + Desfazer)", async () => {
  const { ctx, recados } = montar();
  await ctx.apiFetch("/api/tasks/90/complete", { method: "POST" });
  await ctx.apiFetch("/api/desfazer/abc", { method: "POST" });
  assert.deepStrictEqual(recados, []); // ainda juntando
  await esperar(900);
  assert.deepStrictEqual(recados, ["mudou"]);
});

test("leitura nao avisa o app", async () => {
  const { ctx, recados } = montar();
  await ctx.apiFetch("/api/tasks");
  await esperar(900);
  assert.deepStrictEqual(recados, []);
});

test("fora do app (Safari/PWA, sem o canal) a escrita segue normal", async () => {
  const { ctx } = montar({ comCanal: false });
  const r = await ctx.apiFetch("/api/tasks/90/complete", { method: "POST" });
  assert.deepStrictEqual({ ...r }, { ok: true });
  await esperar(900);
});
