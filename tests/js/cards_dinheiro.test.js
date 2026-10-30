// Grupo E (Dinheiro), Lab v4 30/10/2026: cupom_itens e contas_email (cards-dinheiro.js). Renderizadores puros.
const test = require("node:test");
const assert = require("node:assert");
const Cards = require("../../static/js/cards.js");
const Dinheiro = require("../../static/js/cards-dinheiro.js");

const AGORA = new Date(2026, 9, 30, 10, 0);
const card = (type, data) => Cards.renderizarCardHTML({ type, id: "x1", data, actions: [] }, { agora: AGORA });

const CUPOM = {
  cupom_id: 7, estabelecimento: "SUPERMERCADO EXEMPLO", emitido_em: "2026-10-28T18:42", total: 312.58, qtd_itens: 23, registrado: false,
  categorias: [
    { nome: "Comida", valor: 168.4, itens: 12, cor: "#b5e48c" },
    { nome: "Besteira", valor: 61.9, itens: 5, cor: "#f47671" },
    { nome: "Limpeza", valor: 47.3, itens: 4, cor: "#8fd0ff" },
    { nome: "Suplemento", valor: 35, itens: 1, cor: "#c4a1ff" },
  ],
  exemplos: ["whey 900 g (suplemento)", "refrigerante 2 l (besteira)"],
};

test("cupom_itens: QR, barra, uma linha por categoria e o botao de registrar", () => {
  const h = card("cupom_itens", CUPOM);
  assert.match(h, /Cupom fiscal/);
  assert.match(h, /cd-quando">R\$.312,58/);
  assert.match(h, /SUPERMERCADO EXEMPLO · emitido em 28\/10/);
  assert.match(h, /class="cu-qr"/);
  assert.strictEqual((h.match(/class="cu-l"/g) || []).length, 4);
  assert.match(h, /<span class="cu-n">Besteira<\/span><span class="cu-v">R\$.61,90<\/span>/);
  assert.match(h, /flex:61.9;background:#f47671/);
  assert.match(h, /23 itens separados\. Ex\.: whey 900 g \(suplemento\), refrigerante 2 l \(besteira\)\./);
  assert.match(h, /data-acao="cupom_registrar" data-cupom="7"/);
});

test("cupom_itens: registrado troca o botao pela confirmacao; 1 item no singular", () => {
  const h = card("cupom_itens", { ...CUPOM, registrado: true, qtd_itens: 1, exemplos: [] });
  assert.doesNotMatch(h, /cupom_registrar/);
  assert.match(h, /Já tá no teu extrato/);
  assert.match(h, /1 item separado\./);
});

test("cupom_itens: visitante nao ve dinheiro; sem id nao renderiza; texto escapado", () => {
  const h = card("cupom_itens", { cupom_id: 7, estabelecimento: "X", oculto: true });
  assert.match(h, /ocultos no modo visitante/);
  assert.doesNotMatch(h, /cu-l|cupom_registrar/);
  assert.doesNotMatch(card("cupom_itens", { ...CUPOM, cupom_id: null }), /cu-qr/);
  const x = card("cupom_itens", { ...CUPOM, estabelecimento: "<img src=x onerror=1>", categorias: [{ nome: "<b>x</b>", valor: 10, cor: "red;x" }] });
  assert.doesNotMatch(x, /<img|<b>x/);
});

test("cupom_itens: categoria com dado ruim nao quebra", () => {
  const h = card("cupom_itens", { ...CUPOM, categorias: [null, { nome: "A", valor: "x" }, { nome: "B", valor: -3 }], exemplos: [5, null] });
  assert.match(h, /class="cu-qr"/);
  assert.strictEqual((h.match(/class="cu-l"/g) || []).length, 0);
});

const CONTAS = {
  lidos: 23, varredura: "07:00",
  contas: [
    { id: 1, nome: "Enel", tipo: "boleto", valor: 187.4, vence: "2026-11-05", dias: 6, codigo: "00190.00009 01000.000007 00000.000019 1 12340000018740", status: "nova" },
    { id: 2, nome: "Aeroclube", tipo: "pix", valor: 450, vence: "2026-11-10", dias: 11, codigo: "000201abc", status: "nova" },
    { id: 3, nome: "Amazon", tipo: "rastreio", valor: null, vence: null, dias: null, codigo: "AB123456789BR", status: "nova" },
    { id: 4, nome: "Cartão", tipo: "fatura", valor: 99.9, vence: "2026-10-29", dias: -1, codigo: null, status: "paga" },
  ],
};

test("contas_email: uma linha por conta com copiar, ja paguei e rastreio", () => {
  const h = card("contas_email", CONTAS);
  assert.match(h, /Achei no e-mail/);
  assert.match(h, /varredura 07:00/);
  assert.match(h, /Li 23 e-mails · achei 4/);
  assert.strictEqual((h.match(/class="ce-conta/g) || []).length, 4);
  assert.match(h, /<b>Enel<\/b><small>vence 05\/11 \(em 6 dias\)<\/small>/);
  assert.match(h, /R\$.187,40/);
  assert.match(h, /Copiar boleto/);
  assert.match(h, /Copiar PIX copia-e-cola/);
  assert.match(h, /data-codigo="000201abc" data-tipo="pix"/);
  assert.match(h, /a caminho/);
  assert.match(h, /Ver rastreio/);
  assert.match(h, /rel="noopener noreferrer"/);
  assert.strictEqual((h.match(/data-acao="conta_paga"/g) || []).length, 2); // boleto e pix; rastreio nao paga; a paga nao repete
  assert.match(h, /class="ce-conta paga"/);
  assert.match(h, /venceu 29\/10 \(há 1 dia\)/);
  assert.match(h, /data-feito-chave="conta:1"/);
});

test("contas_email: vencimento em palavras", () => {
  const q = Dinheiro.quandoVence;
  assert.strictEqual(q({ tipo: "boleto", vence: "2026-10-30", dias: 0 }), "vence hoje (30/10)");
  assert.strictEqual(q({ tipo: "boleto", vence: "2026-10-31", dias: 1 }), "vence amanhã (31/10)");
  assert.strictEqual(q({ tipo: "boleto", vence: null }), "sem vencimento no e-mail");
  assert.strictEqual(q({ tipo: "rastreio", vence: null }), "código de rastreio");
});

test("contas_email: visitante, lista vazia, texto escapado e sem codigo sem botao copiar", () => {
  assert.match(card("contas_email", { oculto: true }), /contas ocultas no modo visitante/);
  assert.doesNotMatch(card("contas_email", { contas: [] }), /ce-conta/);
  const h = card("contas_email", { contas: [{ id: 9, nome: "<script>x</script>", tipo: "fatura", valor: 10, vence: "2026-11-01", dias: 2, codigo: null }] });
  assert.doesNotMatch(h, /<script>/);
  assert.doesNotMatch(h, /ce-copia/);
  assert.match(h, /data-acao="conta_paga"/);
});

test("cards-dinheiro: sem DOM nada quebra", () => {
  assert.doesNotThrow(() => Dinheiro.preparar(null));
  assert.doesNotThrow(() => Dinheiro.preparar({}));
});
