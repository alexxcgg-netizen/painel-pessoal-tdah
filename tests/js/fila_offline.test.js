// Testes da logica PURA da fila offline (sem navegador/IndexedDB) - roda com
// o test runner nativo do Node (nenhuma dependencia nova no projeto):
//
//   node --test tests/js/fila_offline.test.js
//
// static/js/fila-offline.js exporta so as funcoes sem IO (criarItem,
// ordenarFifo, ehErroDeServidor) via module.exports quando roda em Node - o
// resto (IndexedDB, fetch, listeners) so existe em navegador de verdade e
// esta coberto pelo teste manual descrito no relatorio final / CHANGELOG.
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const { criarItem, ordenarFifo, ehErroDeServidor } = require(
  path.join(__dirname, "..", "..", "static", "js", "fila-offline.js")
);

test("criarItem gera um id quando nenhum e passado", () => {
  const item = criarItem({ url: "/api/capture", method: "POST", body: "{}", tipo: "capture" });
  assert.ok(item.id && typeof item.id === "string" && item.id.length > 0);
});

test("criarItem reaproveita o id passado (client_id da captura)", () => {
  const item = criarItem({ url: "/api/capture", tipo: "capture", id: "abc-123" });
  assert.equal(item.id, "abc-123");
});

test("criarItem preenche method/headers/body/tipo com defaults seguros", () => {
  const item = criarItem({ url: "/api/checkin" });
  assert.equal(item.method, "POST");
  assert.deepEqual(item.headers, {});
  assert.equal(item.body, null);
  assert.equal(item.tipo, "generico");
  assert.ok(item.criadoEm); // timestamp presente, usado pra ordenar FIFO
});

test("criarItem preserva os dados passados sem alterar", () => {
  const item = criarItem({
    url: "/api/checkin",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ energia: "bom" }),
    tipo: "checkin",
  });
  assert.equal(item.url, "/api/checkin");
  assert.equal(item.body, JSON.stringify({ energia: "bom" }));
  assert.equal(item.headers["Content-Type"], "application/json");
});

test("ordenarFifo mantem ordem de criacao (mais antigo primeiro)", () => {
  const itens = [
    { id: "3", criadoEm: "2026-09-23T10:02:00.000Z" },
    { id: "1", criadoEm: "2026-09-23T10:00:00.000Z" },
    { id: "2", criadoEm: "2026-09-23T10:01:00.000Z" },
  ];
  const ordenado = ordenarFifo(itens).map((i) => i.id);
  assert.deepEqual(ordenado, ["1", "2", "3"]);
});

test("ordenarFifo nao muta o array original", () => {
  const itens = [
    { id: "b", criadoEm: "2026-09-23T10:01:00.000Z" },
    { id: "a", criadoEm: "2026-09-23T10:00:00.000Z" },
  ];
  const copia = [...itens];
  ordenarFifo(itens);
  assert.deepEqual(itens, copia);
});

test("ordenarFifo lida com fila vazia", () => {
  assert.deepEqual(ordenarFifo([]), []);
});

test("ehErroDeServidor: 4xx e 5xx sao erro real do servidor (descarta o item)", () => {
  assert.equal(ehErroDeServidor(400), true);
  assert.equal(ehErroDeServidor(401), true);
  assert.equal(ehErroDeServidor(404), true);
  assert.equal(ehErroDeServidor(500), true);
  assert.equal(ehErroDeServidor(502), true);
});

test("ehErroDeServidor: 2xx nao e erro (sincronizou com sucesso)", () => {
  assert.equal(ehErroDeServidor(200), false);
  assert.equal(ehErroDeServidor(201), false);
  assert.equal(ehErroDeServidor(204), false);
});

test("ehErroDeServidor: valores invalidos/ausentes nunca contam como erro de servidor", () => {
  // isso importa pro caller: so decide "descartar da fila" com um status
  // numerico de verdade vindo de uma resposta HTTP real - nunca por engano
  // com undefined/null (que aconteceria se o fetch tivesse falhado de rede,
  // caso que e tratado ANTES, sem nem chegar a checar status).
  assert.equal(ehErroDeServidor(undefined), false);
  assert.equal(ehErroDeServidor(null), false);
  assert.equal(ehErroDeServidor("500"), false);
});
