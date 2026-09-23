// Testes da logica PURA do comando de voz (sem navegador/DOM/SpeechRecognition) -
// roda com o test runner nativo do Node (nenhuma dependencia nova no projeto):
//
//   node --test tests/js/voz_comando.test.js
//
// static/js/voz-comando.js exporta so as funcoes sem IO (exigeConfirmacao,
// resolverTela, descreverResultado, opcoesDeCorrecao, ACOES_DESTRUTIVAS) via
// module.exports quando roda em Node - o wiring de DOM/SpeechRecognition
// (US-B1) so existe em navegador de verdade, coberto por verificacao
// headless (Playwright) separada, ver AGENTS.md/progress.
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const {
  exigeConfirmacao,
  resolverTela,
  descreverResultado,
  opcoesDeCorrecao,
  classificarLocalmente,
  ACOES_DESTRUTIVAS,
} = require(path.join(__dirname, "..", "..", "static", "js", "voz-comando.js"));
const { criarItem, ehErroDeServidor } = require(
  path.join(__dirname, "..", "..", "static", "js", "fila-offline.js")
);

// ---- exigeConfirmacao (US-B2) ----

test("exigeConfirmacao: precisa_confirmacao=true do contrato e sempre respeitado", () => {
  assert.equal(exigeConfirmacao({ acao: "registrar_tarefa", precisa_confirmacao: true }), true);
});

test("exigeConfirmacao: acao nao-destrutiva de confianca alta NAO pede confirmacao", () => {
  assert.equal(exigeConfirmacao({ acao: "registrar_tarefa", precisa_confirmacao: false }), false);
  assert.equal(exigeConfirmacao({ acao: "registrar_gasto", precisa_confirmacao: false }), false);
  assert.equal(exigeConfirmacao({ acao: "navegar_tela", precisa_confirmacao: false }), false);
  assert.equal(exigeConfirmacao({ acao: "consultar", precisa_confirmacao: false }), false);
});

test("exigeConfirmacao: acao destrutiva PEDE confirmacao mesmo com confianca alta", () => {
  assert.equal(exigeConfirmacao({ acao: "corrigir_ultimo", precisa_confirmacao: false }), true);
});

test("exigeConfirmacao: resultado ausente/invalido e tratado como 'precisa confirmar' (seguro por padrao)", () => {
  assert.equal(exigeConfirmacao(null), true);
  assert.equal(exigeConfirmacao(undefined), true);
  assert.equal(exigeConfirmacao("string qualquer"), true);
});

test("ACOES_DESTRUTIVAS e um Set no formato esperado", () => {
  assert.ok(ACOES_DESTRUTIVAS instanceof Set);
  assert.ok(ACOES_DESTRUTIVAS.has("corrigir_ultimo"));
});

// ---- resolverTela (roteamento de navegar_tela) ----

test("resolverTela reconhece sinonimos comuns por aba", () => {
  assert.equal(resolverTela("gastos"), "gastos");
  assert.equal(resolverTela("financeiro"), "gastos");
  assert.equal(resolverTela("tarefas"), "tarefas");
  assert.equal(resolverTela("aviação"), "aviacao");
  assert.equal(resolverTela("Construtora"), "construtora");
  assert.equal(resolverTela("os bancos"), "bancos");
});

test("resolverTela ignora acento/caixa", () => {
  assert.equal(resolverTela("AVIAÇÃO"), "aviacao");
  assert.equal(resolverTela("chEck-In"), "vida");
});

test("resolverTela devolve null pra texto nao reconhecido/vazio/invalido", () => {
  assert.equal(resolverTela("xablau"), null);
  assert.equal(resolverTela(""), null);
  assert.equal(resolverTela(undefined), null);
  assert.equal(resolverTela(null), null);
  assert.equal(resolverTela(123), null);
});

// ---- descreverResultado ----

test("descreverResultado descreve navegar_tela com o parametro tela", () => {
  const texto = descreverResultado({ acao: "navegar_tela", parametros: { tela: "gastos" } });
  assert.match(texto, /navegar/);
  assert.match(texto, /gastos/);
});

test("descreverResultado avisa sobre teto de IA estourado", () => {
  const texto = descreverResultado({ acao: "desconhecido", teto_ia_estourado: true, parametros: {} });
  assert.match(texto, /limite mensal/i);
});

test("descreverResultado lida com resultado ausente/invalido sem quebrar", () => {
  assert.equal(typeof descreverResultado(null), "string");
  assert.equal(typeof descreverResultado(undefined), "string");
  assert.equal(typeof descreverResultado({}), "string");
});

// ---- opcoesDeCorrecao (US-B3, 2o turno) ----

test("opcoesDeCorrecao nunca inclui 'desconhecido' (corrigir pra 'nao entendi' nao faz sentido)", () => {
  const opcoes = opcoesDeCorrecao();
  assert.ok(opcoes.every((o) => o.acao !== "desconhecido"));
});

test("opcoesDeCorrecao cobre as 6 acoes reais do contrato, cada uma com rotulo nao vazio", () => {
  const opcoes = opcoesDeCorrecao();
  const acoes = opcoes.map((o) => o.acao).sort();
  assert.deepEqual(acoes, [
    "consultar",
    "corrigir_ultimo",
    "navegar_tela",
    "registrar_checkin",
    "registrar_gasto",
    "registrar_tarefa",
  ]);
  opcoes.forEach((o) => assert.ok(o.rotulo && typeof o.rotulo === "string"));
});

// ---- US-B5: fallback offline - comando de voz reusa a MESMA fila da Fase 4
// (static/js/fila-offline.js), so com tipo "comando_voz" (mesma logica
// generica de criarItem/ehErroDeServidor testada em fila_offline.test.js -
// aqui so confere que o formato que voz-comando.js manda pra fila encaixa
// nessa mesma logica sem precisar de nenhum campo especial). ----

test("um comando de voz enfileirado offline vira um item generico valido da fila", () => {
  const item = criarItem({
    url: "/api/intent/classificar",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ texto: "abre os gastos", client_id: "voz-abc-123" }),
    tipo: "comando_voz",
    id: "voz-abc-123",
  });
  assert.equal(item.id, "voz-abc-123");
  assert.equal(item.tipo, "comando_voz");
  assert.equal(JSON.parse(item.body).texto, "abre os gastos");
  assert.ok(item.criadoEm); // usado pra ordenar FIFO igual qualquer outro item
});

test("um comando de voz so enfileira de novo em falha de rede, nunca em erro real do servidor", () => {
  // mesma regra generica de qualquer item da fila (texto vazio, contrato
  // do classificador, etc viram 400 real - nao devem ficar tentando pra
  // sempre): ver ehErroDeServidor em fila_offline.test.js.
  assert.equal(ehErroDeServidor(400), true);
  assert.equal(ehErroDeServidor(200), false);
});

// ---- US-B6: classificador local (bag-of-words, NAO e Core ML/Neural Engine
// de verdade - ver comentario em static/js/voz-comando.js pra avaliacao
// completa de viabilidade) - so resolve navegacao simples, 100% offline. ----

test("classificarLocalmente resolve um pedido de navegacao claro sem precisar de rede", () => {
  const r = classificarLocalmente("abre os gastos");
  assert.ok(r);
  assert.equal(r.acao, "navegar_tela");
  assert.equal(r.parametros.tela, "gastos");
  assert.equal(r.precisa_confirmacao, false);
  assert.equal(r.classificado_localmente, true);
});

test("classificarLocalmente reconhece variacoes de verbo de navegacao", () => {
  assert.equal(classificarLocalmente("mostra as tarefas").parametros.tela, "tarefas");
  assert.equal(classificarLocalmente("vai pra aviacao").parametros.tela, "aviacao");
  assert.equal(classificarLocalmente("navega pros bancos").parametros.tela, "bancos");
});

test("classificarLocalmente devolve null pra qualquer coisa fora do padrao de navegacao simples", () => {
  // texto que nao e um pedido de navegacao (ex: uma captura) NUNCA deve
  // resolver local por engano - cai pro classificador de verdade (rede).
  assert.equal(classificarLocalmente("gastei 50 reais no mercado"), null);
  assert.equal(classificarLocalmente("lembra de ligar pro dentista"), null);
  assert.equal(classificarLocalmente("quanto eu gastei esse mes"), null);
  assert.equal(classificarLocalmente(""), null);
  assert.equal(classificarLocalmente(undefined), null);
});

test("classificarLocalmente devolve null quando pede pra navegar mas a tela nao e reconhecida", () => {
  assert.equal(classificarLocalmente("abre o xablau"), null);
});
