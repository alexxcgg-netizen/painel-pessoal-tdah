// Cards do dia da leva de 22/10 (static/js/cards-dia.js): dia_ruim e alerta_dia renderizam o estado final,
// escapam texto e nao viram fallback com dado faltando.
//
//   node --test tests/js/cards_dia.test.js
//
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const Cards = require(path.join(__dirname, "..", "..", "static", "js", "cards.js"));
require(path.join(__dirname, "..", "..", "static", "js", "cards-dia.js"));

const html = (type, data) => Cards.renderizarCardHTML({ type, id: "c1", data, actions: [] });
const semFallback = (h) => assert.ok(!h.includes("card-contrato-fallback"), h);

test("dia_ruim aliviado: 4 grupos, botoes certos, hero conta, guia no passo 2", () => {
  const h = html("dia_ruim", {
    ativo: true,
    inegociavel: [{ id: 1, titulo: "Consulta", hora: "15:00" }],
    reduzido: [{ id: 2, titulo: "Treino", hora: "18:00", curta: "versão leve · 25 min" }],
    fica: [{ id: 3, titulo: "<b>Lavar</b>", hora: null }],
    amanha: [{ id: 4, titulo: "Garagem", hora: "10:00" }],
  });
  semFallback(h);
  assert.match(h, /O mínimo basta: 1 inegociável, 1 versão curta, 1 pra amanhã\./);
  assert.match(h, /Treino · versão leve · 25 min<small>antes: 18:00/);
  assert.match(h, /data-acao="dr_empurrar" data-id="3"/);
  assert.match(h, /data-acao="dr_trazer" data-id="4"/);
  assert.match(h, /&lt;b&gt;Lavar/);
  assert.match(h, /cd-seg" data-p="1"/);
  assert.match(h, /<i class="ok"><\/i><i class="on"><\/i>/);
});

test("dia_ruim como estava: uma lista so e o Aliviado brilhando", () => {
  const h = html("dia_ruim", { ativo: false, fica: [{ id: 3, titulo: "Lavar" }], inegociavel: [], reduzido: [], amanha: [] });
  semFallback(h);
  assert.match(h, /Teu dia/);
  assert.match(h, /1 coisa hoje\./);
  assert.match(h, /class="cd-aqui" data-acao="dr_modo" data-modo="1"/);
  semFallback(html("dia_ruim", {}));
});

test("alerta_dia: sinais, cadeado por tarefa (o solto brilha), Aliviar e Segue", () => {
  const h = html("alerta_dia", {
    sinais: [{ tipo: "sono", texto: "Dormiu 5,2 h" }, { tipo: "empurradas", texto: "3 tarefas empurradas" }],
    tarefas: [{ id: 1, titulo: "Consulta", hora: "15:00", inegociavel: true }, { id: 2, titulo: "Garagem", inegociavel: false }],
  });
  semFallback(h);
  assert.match(h, /Hoje pede mais cuidado\./);
  assert.equal((h.match(/class="cd-sinal"/g) || []).length, 2);
  assert.match(h, /data-acao="cd_travar" data-id="1" aria-pressed="true"/);
  assert.match(h, /class="cd-cad cd-aqui" data-acao="cd_travar" data-id="2" aria-pressed="false"/);
  assert.match(h, /data-acao="al_aliviar"/);
  assert.match(h, /data-estado="\{&quot;tarefas&quot;/);
  assert.match(html("alerta_dia", { oculto: true }), /Oculto no modo visitante/);
  semFallback(html("alerta_dia", {}));
});

test("alerta_dia aliviado: travadas ficam, o resto foi pra amanha e o fim conta", () => {
  const h = html("alerta_dia", {
    aliviado: true,
    tarefas: [{ id: 1, titulo: "Consulta", inegociavel: true }, { id: 2, titulo: "Garagem", inegociavel: false }],
  });
  assert.match(h, /Fica hoje/);
  assert.match(h, /Foi pra amanhã/);
  assert.match(h, /1 inegociável fica como está\. O resto/);
  assert.ok(!h.includes("al_aliviar"));
});

test("de_onde_parei: barra ate onde parou, proximo passo respira, escapa texto", () => {
  const h = html("de_onde_parei", {
    task_id: 7, titulo: "Revisar <i>meteorologia</i>", parado_h: 3,
    passos: [{ id: 1, titulo: "Ler o resumo", feito: true }, { id: 2, titulo: "Questões 1 a 7", feito: true }, { id: 3, titulo: "Questões 8 a 13", feito: false }],
  });
  semFallback(h);
  assert.match(h, /há 3 h/);
  assert.match(h, /Revisar &lt;i&gt;meteorologia/);
  assert.match(h, /width:67%/);
  assert.match(h, /2 de 3 passos · falta 1/);
  assert.match(h, /<li class=" proximo" data-i="2">/);
  assert.match(h, /data-acao="pa_continuar"/);
  assert.match(h, /data-acao="pa_deixar"/);
  // tudo feito: some o Continuar, aparece Concluir a tarefa
  const fim = html("de_onde_parei", { task_id: 7, titulo: "X", passos: [{ id: 1, titulo: "A", feito: true }] });
  assert.match(fim, /Tudo feito por aqui\./);
  assert.match(fim, /data-acao="pa_concluir"/);
  assert.doesNotMatch(fim, /pa_continuar/);
  semFallback(html("de_onde_parei", {}));
});

test("foco: pronto, meio com 3 respostas, feito com o tempo, escapa texto", () => {
  const base = { id: 9, titulo: "Fotos <b>", passo: "Abre a galeria", total_s: 600, decorrido_s: 0, fase: "pronto" };
  const h = html("foco", base);
  semFallback(h);
  assert.match(h, /Fotos &lt;b&gt;/);
  assert.match(h, /10:00/);
  assert.match(h, /data-acao="fo_comecar">Começar 10 min/);
  const meio = html("foco", Object.assign({}, base, { fase: "meio", decorrido_s: 300 }));
  assert.match(meio, /05:00/);
  assert.match(meio, /data-r="ainda"/);
  assert.match(meio, /data-r="travei"/);
  assert.match(meio, /data-r="fim"/);
  const travou = html("foco", Object.assign({}, base, { fase: "pausado", decorrido_s: 300, travei: true, passo: "Só 5 fotos" }));
  assert.match(travou, /Passo menor/);
  assert.match(travou, /Só 5 fotos/);
  const feito = html("foco", Object.assign({}, base, { fase: "feito", decorrido_s: 312, levou_s: 312 }));
  assert.match(feito, /Terminou em 5 min 12 s/);
  assert.match(feito, /fo-estouro vai/);
  assert.doesNotMatch(feito, /fo_comecar/);
  semFallback(html("foco", {}));
});

test("combinados: pessoas com Cobrar/Responder, empresa so leitura sem total, escapa texto", () => {
  const d = {
    pessoas: [
      { tipo: "espera", id: 1, quem: "Instrutor <x>", sobre: "o documento", dias: 4, rascunho: "Oi" },
      { tipo: "responder", id: 2, quem: "Ana", sobre: "", dias: 1, rascunho: "Oi" },
    ],
    empresa: { disponivel: true, atrasadas: [{ nome: "Concreto", descricao: "", valor: 7850, dias: 2 }], mais: 0 },
  };
  const h = html("combinados", d);
  semFallback(h);
  assert.match(h, /2 combinados em aberto com pessoas/);
  assert.match(h, /Instrutor &lt;x&gt;/);
  assert.match(h, /data-acao="cb_cobrar" data-i="0">Cobrar/);
  assert.match(h, /data-acao="cb_cobrar" data-i="1">Responder/);
  assert.match(h, /esperando há 4 dias/);
  assert.match(h, /tu deve resposta há 1 dia/);
  const emp = require(path.join(__dirname, "..", "..", "static", "js", "cards-dia.js")).raizCombinados(Object.assign({}, d, { aba: 1, passo: 2 }));
  assert.match(emp, /1 conta atrasada na empresa/);
  assert.match(emp, /2 dias de atraso/);
  assert.match(emp, /R\$&nbsp;7\.850,00/);
  assert.doesNotMatch(emp, /total/i);
  const fora = require(path.join(__dirname, "..", "..", "static", "js", "cards-dia.js")).raizCombinados({ pessoas: [], empresa: { disponivel: false }, aba: 1 });
  assert.match(fora, /fora do ar/);
  assert.match(html("combinados", { oculto: true }), /Oculto no modo visitante/);
  semFallback(html("combinados", {}));
});

test("proteina: so proteina, copo contra a meta, sugestoes e corrige", () => {
  const d = { id: 5, refeicao: "almoço", hora: "12:30", prato_g: 38, dia_g: 92, meta_g: 140,
    total: { kcal: 600, proteina_g: 38, carbo_g: 60, gordura_g: 12 },
    sugestoes: [{ nome: "Frango <grelhado>", g: 45 }, { nome: "Ovos (3 unidades)", g: 18 }] };
  const h = html("proteina", d);
  semFallback(h);
  assert.match(h, /Esse prato: ~<span class="pr-prato-g">38<\/span>&nbsp;g de proteína/);
  assert.match(h, /<b class="pr-tot">92<\/b><small>de 140 g/);
  assert.match(h, /<span class="pr-falta-g">48<\/span> g/);
  assert.match(h, /Frango &lt;grelhado&gt; · 45 g/);
  assert.match(h, /data-acao="pr_corrige"/);
  assert.doesNotMatch(h.replace(/data-estado="[^"]*"/g, ""), /kcal/);
  const sem = html("proteina", Object.assign({}, d, { meta_g: null }));
  assert.match(sem, /me diz teu peso/);
  semFallback(html("proteina", {}));
});

test("diario_bordo: 3 perguntas, barras do RBAC, mais atrasada e TGL so com toques", () => {
  const cats = [
    { chave: "total", nome: "Total", h: 112.4, meta: 150 },
    { chave: "navegacao", nome: "Navegação", h: 14.2, meta: 20 },
    { chave: "noturno", nome: "Noturno", h: 3.5, meta: 5 },
    { chave: "instrumentos", nome: "Instrumentos", h: 9, meta: 10 },
  ];
  const d = { id: 4, data: "2026-10-22", rota: "SSBL → SSBL", horas: 1.3, estimado: true, natureza: null, noturno: false,
    toques: 4, registrado: false, cats, pior: "navegacao", toques_curso: 38, fonte: "RBAC 61.101" };
  const h = html("diario_bordo", d);
  semFallback(h);
  assert.match(h, /<b class="db-h">1,3<\/b>/);
  assert.match(h, /data-acao="db_tipo" data-n="tgl" aria-pressed="false">TGL/);
  assert.doesNotMatch(h, /Pista/i);
  assert.match(h, /data-acao="db_registrar" disabled/);
  assert.match(h, /class="db-linha atraso" data-c="navegacao"/);
  assert.match(h, /Faltam 5,8&nbsp;h pra fechar essa categoria/);
  assert.match(h, /<b class="db-toques">38<\/b> toques/);
  assert.match(h, /RBAC 61\.101/);
  assert.match(h, /class="db-aviao" style="left:74\.9%"/);
  assert.doesNotMatch(h, /db_toques/); // stepper de toques so aparece no TGL
  const tgl = require(path.join(__dirname, "..", "..", "static", "js", "cards-dia.js")).raizDiario(Object.assign({}, d, { tipo: "tgl", toques_total: 38 }));
  assert.match(tgl, /data-acao="db_toques"/);
  assert.match(tgl, /4 toques/);
  assert.match(tgl, /Conta os toques, confere o tempo e registra/);
  const reg = html("diario_bordo", Object.assign({}, d, { registrado: true, natureza: "navegacao", noturno: true }));
  assert.match(reg, /Registrado: 1,3 h de navegação, noite\./);
  assert.match(reg, /data-acao="db_desfazer"/);
  assert.doesNotMatch(reg, /db_registrar/);
  assert.match(html("diario_bordo", Object.assign({}, d, { rota: "<x>" })), /&lt;x&gt;/);
  semFallback(html("diario_bordo", {}));
});
