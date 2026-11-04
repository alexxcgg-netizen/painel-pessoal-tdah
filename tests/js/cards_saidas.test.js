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

test("date (D, 04/11): pilula conta ate se arrumar; aberto tem cadeia, tempo hora a hora, o que levar e a lista", () => {
  const g = AGORA.getTime() / 1000;
  const h = html("date", {
    id: 7, titulo: "Jantar", data: "2026-10-17", hora: "20:00", lugar: "Lume <b>", com_quem: "Júlia",
    comecar: "19:00", sair: "19:40", trajeto_min: 15, clima: { temp: 15.6, chuva_pct: 55 },
    cadeia: [
      { rotulo: "Se arrumar", hora: "19:00", em_s: 291600 },
      { rotulo: "Sair", hora: "19:40", em_s: 294000 },
      { rotulo: "Chegar", hora: "20:00", em_s: 295200 },
    ],
    gerado_ts: g,
    clima_horas: [
      { hora: 19, temp: 17, chuva_pct: 30, codigo: 3, marca: null },
      { hora: 20, temp: 16, chuva_pct: 55, codigo: 61, marca: "chegada" },
      { hora: 23, temp: 14, chuva_pct: 10, codigo: 1, marca: "volta" },
    ],
    clima_lugar: "Brusque",
    levar: [{ item: "guarda_chuva", titulo: "Guarda-chuva", motivo: "55% às 20h" }, { item: "casaco", titulo: "Casaco", motivo: "14° na volta, 23h" }],
    lista: [{ texto: "Reservar mesa", quando: "hoje", feito: true }, { texto: "Flores", detalhe: "fecha 19h" }],
  });
  semFallback(h);
  assert.match(h, /class="vivo-d" data-v="date" style="--cc:#f5a3b8" aria-expanded="false" data-compromisso="7"/);
  assert.match(h, /<span class="v-t">Date com Júlia<\/span>/);
  assert.match(h, /sábado · chegar 20:00 · 16° · 55%/); // tempo na chegada vem da coluna marcada
  assert.match(h, /<small>arrumar em<\/small><b><span class="rl" data-cd-s="291600"/);
  assert.match(h, /data-txt="3 dias"/); // 81 h: conta em dias
  assert.match(h, /class="v-cadeia" style="--n:3"><div><small>Se arrumar<\/small>/);
  assert.match(h, /class="v-tempo" style="--n:3"/);
  assert.match(h, /class="v-hora marca" role="listitem" data-rot="chegada" data-h="20"/);
  assert.match(h, /data-rot="volta"/);
  assert.match(h, /Guarda-chuva<small>55% às 20h<\/small>/);
  assert.match(h, /Casaco<small>14° na volta, 23h<\/small>/);
  assert.match(h, /15 min de carro até lá\. Previsão pra Brusque\. Se mudar até a hora, eu ajusto a saída e te aviso\./);
  assert.match(h, /<li class="marcado"[^>]*><button[^>]*data-acao="lista_item" data-tarefa="7" data-i="0" aria-pressed="true"/);
  // sem cara de IA: nada de hero gigante, fichas com icone ou rotulo em maiusculas
  assert.doesNotMatch(h, /sd-hero|sd-ficha|sd-coracao|Lume <b>/);
});

test("date (D): passos que ja passaram nao contam; card antigo sem cadeia monta as caixas", () => {
  const g = AGORA.getTime() / 1000;
  const base = { id: 7, titulo: "Jantar", data: "2026-10-14", hora: "11:00", comecar: "09:30", sair: "10:20" };
  const h = html("date", { ...base, gerado_ts: g, cadeia: [
    { rotulo: "Se arrumar", hora: "09:30", em_s: -1800 },
    { rotulo: "Sair", hora: "10:20", em_s: 1200 },
    { rotulo: "Chegar", hora: "11:00", em_s: 3600 },
  ] });
  assert.match(h, /<small>sair em<\/small>/);
  assert.match(h, /data-txt="20 min"/);
  const antigo = html("date", base);
  assert.match(antigo, /class="v-cadeia" style="--n:3"/);
  assert.doesNotMatch(antigo, /data-cd-s/); // sem segundos do servidor, nada de contagem inventada
});

test("date sem hora: so a pilula com o dia, sem cadeia", () => {
  const h = html("date", { id: 1, titulo: "Cinema", data: "2026-10-30" });
  semFallback(h);
  assert.ok(!h.includes("v-cadeia"));
  assert.match(h, /sex 30 out/);
});

test("saida com parada no caminho (Frente 2): a parada entra na cadeia", () => {
  const h = html("balada", {
    id: 3, titulo: "Balada", data: "2026-10-16", hora: "23:00", lugar: "Warung", comecar: "21:40", sair: "22:20",
    gerado_ts: AGORA.getTime() / 1000,
    cadeia: [
      { rotulo: "Se arrumar", hora: "21:40", em_s: 200400 },
      { rotulo: "Sair", hora: "22:20", em_s: 202800 },
      { rotulo: "Casa do guri", hora: "22:30", em_s: 203400, parada: true },
      { rotulo: "Chegar", hora: "23:00", em_s: 205200 },
    ],
  });
  assert.match(h, /class="v-cadeia" style="--n:4"/);
  assert.match(h, /<div class="parada"><small>Casa do guri<\/small>/);
});

test("balada (D): pilula com a lua, sono so quando veio do servidor, como volta (dirigindo por padrao)", () => {
  const base = { id: 3, titulo: "Balada no Warung", data: "2026-10-16", hora: "23:00", lugar: "Warung", com_quem: "a galera", comecar: "21:40", sair: "22:20" };
  const livre = html("balada", { ...base, volta: null });
  semFallback(livre);
  assert.match(livre, /class="vivo-d" data-v="balada" style="--cc:#c4a1ff"/);
  assert.match(livre, /<span class="v-t">Warung<\/span>/);
  assert.match(livre, /sexta · chegar 23:00/);
  assert.ok(!livre.includes("sd-sono"), "sem compromisso no dia seguinte: nada de horas de sono");
  assert.match(livre, /class="sd-volta" data-modo="dirigindo" style="--i:0"/, "sem hora de volta o controle aparece igual");
  assert.match(livre, /Volta dirigindo: zero álcool, combinado\?/);
  assert.doesNotMatch(livre, /sd-ceu|sd-estrela|sd-cidade/); // o ceu desenhado saiu

  const h = html("balada", {
    ...base, volta: "03:00", volta_modo: "uber",
    sono: { min: 200, volta: "04:30", acordar: "07:50", compromisso: "Prova <i>", hora: "09:00" },
  });
  assert.match(h, /3 h 20 min de sono/);
  assert.match(h, /sd-sono pouco/);
  assert.match(h, /Menos de 6 h de sono\. Vale voltar mais cedo\./);
  assert.match(h, /Prova &lt;i&gt;/);
  assert.match(h, /class="sd-volta" data-modo="uber" style="--i:2"/);
  assert.strictEqual((h.match(/data-acao="volta"/g) || []).length, 3);
  assert.match(h, /role="radio" aria-checked="true" class="sd-volta-op atual" data-acao="volta" data-modo="uber" data-k="2" data-tarefa="3" data-volta="03:00"/);
  assert.match(h, /Te lembro às 2h30 de chamar o Uber\./);
  assert.equal(CardsSaidas.textoVolta("uber", "00:10").texto, "Te lembro às 23h40 de chamar o Uber.");
  assert.equal(CardsSaidas.textoVolta("uber", null).texto, "Te lembro às 2h30 de chamar o Uber.");
  assert.equal(CardsSaidas.textoVolta("carona").texto, "De carona: beleza, sem lembrete nenhum.");
  assert.match(html("balada", { ...base, volta_modo: "<x>" }), /data-modo="dirigindo"/);
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
  assert.match(h, /tudo na pasta</);
  assert.doesNotMatch(h, /✓/);
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

test("presente anual: selo todo ano e o que ele deu ano passado", () => {
  const h = html("presente", { id: 4, titulo: "Aniversário da mãe", data: "2026-10-26", compra_ate: "2026-10-22", ideias: [], anual: true, ano_passado: "Kit <jardim>" });
  semFallback(h);
  assert.match(h, /class="sd-anual">.*todo ano<\/span>/);
  assert.match(h, /Ano passado: <b>Kit &lt;jardim&gt;<\/b>/);
  const comum = html("presente", { id: 4, titulo: "Despedida", data: "2026-10-26", compra_ate: "2026-10-22", ideias: [] });
  assert.ok(!comum.includes("sd-anual") && !comum.includes("Ano passado"));
});

test("dado faltando nao quebra: vira fallback", () => {
  for (const tipo of ["date", "balada", "documentos", "presente"]) {
    assert.match(html(tipo, { titulo: "x" }), /card-contrato-fallback/, tipo);
  }
});
