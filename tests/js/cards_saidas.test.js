// Cards de compromisso (static/js/cards-saidas.js, 2026-10-14): date, balada, documentos e
// presente saem no estado final, com tudo escapado e sem cair no fallback.
//
//   node --test tests/js/cards_saidas.test.js
//
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const Cards = require(path.join(__dirname, "..", "..", "static", "js", "cards.js"));
const CardsSaidas = require(path.join(__dirname, "..", "..", "static", "js", "cards-saidas.js"));

const AGORA = new Date(2026, 9, 14, 10, 0); // quarta 14/out
const html = (type, data) => Cards.renderizarCardHTML({ type, id: "c1", data, actions: [] }, { agora: AGORA });
const semFallback = (h) => assert.ok(!h.includes("card-contrato-fallback"), h);

test("date: hero com quem + lugar, linha se arrumar -> sair -> chegar, clima vira ficha, lista marca", () => {
  const h = html("date", {
    id: 7, titulo: "Jantar", data: "2026-10-17", hora: "20:00", lugar: "Lume <b>", com_quem: "Júlia",
    comecar: "19:00", sair: "19:40", trajeto_min: 15, clima: { temp: 15.6, chuva_pct: 55 },
    lista: [{ texto: "Reservar mesa", quando: "hoje", feito: true }, { texto: "Flores", detalhe: "fecha 19h" }],
  });
  semFallback(h);
  assert.match(h, /sábado · 20:00/);
  assert.match(h, /Júlia · Lume &lt;b&gt;/);
  assert.match(h, /em 3 dias · 15 min de carro/);
  assert.match(h, /sd-parada destaque[^>]*><i><\/i><b class="vivo-num">19:00<\/b><span>se arrumar/);
  assert.match(h, /16°<\/b> à noite/);
  assert.match(h, /leva jaqueta/);
  assert.match(h, /chuva <b class="vivo-num">55%/);
  // lugar ja esta no hero e na linha: so clima/jaqueta/chuva nas fichas
  assert.equal((h.match(/class="sd-ficha"/g) || []).length, 3);
  assert.match(h, /<li class="marcado"[^>]*><button[^>]*data-acao="lista_item" data-tarefa="7" data-i="0" aria-pressed="true"/);
  assert.match(h, /data-compromisso="7"/);
});

test("date sem hora: sem linha da noite, mas ainda e card de date", () => {
  const h = html("date", { id: 1, titulo: "Cinema", data: "2026-10-30" });
  semFallback(h);
  assert.ok(!h.includes("sd-linha"));
  assert.match(h, /sex 30 out/);
});

test("balada: ceu da noite, sono so quando veio do servidor, chave do Uber com a hora de chamar", () => {
  const base = { id: 3, titulo: "Balada no Warung", data: "2026-10-16", hora: "23:00", lugar: "Warung", com_quem: "a galera", comecar: "21:40", sair: "22:20" };
  const livre = html("balada", { ...base, volta: null });
  semFallback(livre);
  assert.match(livre, /Sexta à noite/);
  assert.match(livre, /em 2 dias · com a galera/);
  assert.ok(!livre.includes("sd-sono"), "sem compromisso no dia seguinte: nada de horas de sono");
  assert.ok(!livre.includes("sd-chave"), "sem volta: sem chave do Uber");

  const h = html("balada", {
    ...base, volta: "03:00", uber: false,
    sono: { min: 200, volta: "04:30", acordar: "07:50", compromisso: "Prova <i>", hora: "09:00" },
  });
  assert.match(h, /--n:4/);
  assert.match(h, /3 h 20 min de sono/);
  assert.match(h, /sd-sono pouco/);
  assert.match(h, /Prova &lt;i&gt;/);
  assert.match(h, /role="switch" aria-checked="false" data-acao="uber" data-tarefa="3" data-volta="03:00"/);
  assert.match(h, /liga e eu te lembro às 2h30/);
  assert.equal(CardsSaidas.textoUber(true, "00:10"), "te lembro às 23h40 de chamar");
});

test("documentos: pasta conta o que ja foi, carimbo bate com tudo marcado, horario do Google avisa", () => {
  const lista = [{ texto: "RG", feito: true }, { texto: "Contrato", feito: true }];
  const h = html("documentos", {
    id: 9, titulo: "Reconhecer firma", data: "2026-10-15", hora: "12:30", lugar: "1º Tabelionato",
    lista, horario: { faixas: [["09:00", "12:00"], ["13:00", "17:00"]] },
  });
  semFallback(h);
  assert.match(h, /Tabelionato/);
  assert.match(h, /amanhã · 12:30/);
  assert.match(h, /tudo na pasta ✓/);
  assert.match(h, /sd-carimbo bateu/);
  assert.match(h, /15·out/);
  assert.match(h, /abre <b class="vivo-num">9h–17h<\/b> · almoço 12h–13h/);
  assert.match(h, /Às 12h30 ainda tá fechado — abre de novo às 13h/);

  const ok = CardsSaidas.horarioTexto({ faixas: [["09:00", "17:00"]] }, "10:00");
  assert.equal(ok.aviso, "");
  assert.match(CardsSaidas.horarioTexto({ faixas: [["09:00", "17:00"]] }, "18:00").aviso, /já fechou — fecha às 17h/);
  assert.match(CardsSaidas.horarioTexto({ fechado: true }, "10:00").aviso, /fecha nesse dia/);
  assert.deepEqual(CardsSaidas.horarioTexto(null, "10:00"), { ficha: "", aviso: "" });
});

test("presente: contagem, prazo de compra na linha, ideia escolhida e aviso em cima da hora", () => {
  const ideias = [{ titulo: "Kit <jardim>", porque: "orquídeas", preco: 180 }, { titulo: "Livro" }];
  const h = html("presente", { id: 4, titulo: "Aniversário da mãe", data: "2026-10-26", compra_ate: "2026-10-22", ideias, escolha: 0 });
  semFallback(h);
  assert.match(h, /seg 26 out</);
  assert.match(h, /<span class="vivo-num">12<\/span><small>dias · Aniversário da mãe/);
  assert.match(h, /sd-marco limite" style="left:66\.7%"/);
  assert.match(h, /Kit &lt;jardim&gt;/);
  assert.match(h, /~R\$&nbsp;180/);
  assert.match(h, /sd-ideias escolheu/);
  assert.match(h, /sd-ideia escolhida"[^>]*data-i="0" aria-pressed="true"/);
  assert.match(h, /Guardei: <b>Kit &lt;jardim&gt;<\/b>\. Te lembro dia 22 de comprar\./);

  const perto = html("presente", { id: 4, titulo: "Aniversário", data: "2026-10-17", compra_ate: "2026-10-14", ideias });
  assert.match(perto, /sábado, 17 out/);
  assert.ok(!perto.includes("sd-marco limite"));
  assert.match(perto, /Pela internet não chega mais a tempo/);

  // limite colado no "hoje": vai pra frase em vez de encavalar o rotulo
  const longe = html("presente", { id: 4, titulo: "Natal", data: "2026-12-25", compra_ate: "2026-10-16", ideias: [] });
  assert.ok(!longe.includes("sd-marco limite"));
  assert.match(longe, /Comprar até dia 16 pra entrega chegar a tempo/);
});

test("dado faltando nao quebra: vira fallback", () => {
  for (const tipo of ["date", "balada", "documentos", "presente"]) {
    assert.match(html(tipo, { titulo: "x" }), /card-contrato-fallback/, tipo);
  }
});
