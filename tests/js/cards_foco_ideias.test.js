// Cards do Grupo A (Foco) do Laboratorio v4 (static/js/cards-foco-ideias.js): e_agora, travou, pacote,
// segundo_antes e recomeco renderizam, escapam texto e nao viram fallback com dado faltando.
//
//   node --test tests/js/cards_foco_ideias.test.js
//
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const Cards = require(path.join(__dirname, "..", "..", "static", "js", "cards.js"));
require(path.join(__dirname, "..", "..", "static", "js", "cards-foco-ideias.js"));

const html = (type, data) => Cards.renderizarCardHTML({ type, id: "c1", data, actions: [] });
const semFallback = (h) => assert.ok(!h.includes("card-contrato-fallback"), h);

test("e_agora: comeca no botao e carrega as sugestoes no estado; vazio nao quebra", () => {
  const h = html("e_agora", {
    quando: "14:20", livre_min: 40, livre_ate: "Academia",
    sugestoes: [{ id: 1, titulo: "<b>Pagar</b> a fatura", min: 8, porque: "Vence hoje." }],
  });
  semFallback(h);
  assert.match(h, /14:20 · 40 min livres/);
  assert.match(h, /class="ea-botao" data-acao="ea_revelar"/);
  assert.match(h, /Toca e eu escolho por ti\./);
  assert.match(h, /data-estado="\{&quot;sugestoes&quot;/);
  assert.ok(!h.includes("<b>Pagar</b>"));
  const vazio = html("e_agora", { sugestoes: [] });
  semFallback(vazio);
  assert.match(vazio, /Nada pendente\. Respira\./);
  semFallback(html("e_agora", {}));
  assert.match(html("e_agora", { oculto: true }), /Oculto no modo visitante/);
});

test("travou: hero, pergunta com a contagem e as 4 respostas", () => {
  const h = html("travou", { task_id: 7, titulo: "Ligar pro <i>cartório</i>", adiadas: 3, motivo: "medo" });
  semFallback(h);
  assert.match(h, /adiada 3x/);
  assert.match(h, /Tu já empurrou essa 3 vezes\. O que pega\?/);
  for (const m of ["chato", "dificil", "medo", "sem_rumo"]) assert.match(h, new RegExp(`data-acao="tv_motivo" data-m="${m}"`));
  assert.match(h, /data-m="medo" aria-pressed="true"/);
  assert.match(h, /data-m="chato" aria-pressed="false"/);
  assert.ok(!h.includes("<i>cartório</i>"));
  assert.match(h, /data-estado="\{&quot;task_id&quot;:7\}"/);
  semFallback(html("travou", {}));
  assert.match(html("travou", { oculto: true }), /Oculto no modo visitante/);
});

test("pacote: tarefas e premios em chips, juntar comeca desligado, ativos viram checklist com premio", () => {
  const h = html("pacote", {
    chatas: [{ id: 1, titulo: "Faxina <u>do quarto</u>", adiadas: 2 }],
    premios: ["Podcast de aviação", "Playlist nova"],
    ativos: [{ id: 5, titulo: "Esteira 30 min", premio: "Série" }],
  });
  semFallback(h);
  assert.match(h, /data-g="a" data-id="1"/);
  assert.equal((h.match(/data-g="b"/g) || []).length, 2);
  assert.match(h, /data-acao="pc_juntar" disabled/);
  assert.match(h, /1 pacote/);
  assert.match(h, /data-acao="pc_marcar" aria-pressed="false"/);
  assert.match(h, /prêmio: série/);
  assert.ok(!h.includes("<u>do quarto</u>"));
  const vazio = html("pacote", { chatas: [], premios: [], ativos: [] });
  semFallback(vazio);
  assert.match(vazio, /Nenhuma tarefa aberta sem pacote/);
  semFallback(html("pacote", {}));
});

test("segundo_antes: contagem da semana, tarefa no estado e botao da previa", () => {
  const h = html("segundo_antes", { tarefa: "Separar a <b>CIV</b>", voltou_semana: 7 });
  semFallback(h);
  assert.match(h, /semana: voltou 7×/);
  assert.match(h, /data-acao="sa_ver"/);
  assert.match(h, /Não bloqueia nada/);
  assert.ok(!h.includes("<b>CIV</b>"));
  assert.match(html("segundo_antes", {}), /voltou 0×/);
});

test("recomeco antes: velhas marcadas, protegidas sinalizadas e botao de arquivar", () => {
  const h = html("recomeco", {
    total: 3, velhas: 1, arquivadas_n: 0,
    itens: [
      { id: 1, titulo: "Ligar pro <b>dentista</b>", dias: 21, protegido: false, velho: true },
      { id: 2, titulo: "Pagar a Enel", dias: 12, protegido: true, velho: false },
      { id: 3, titulo: "Devolver o livro", dias: 3, protegido: false, velho: false },
    ],
  });
  semFallback(h);
  assert.match(h, /<span class="rc-n">3<\/span>/);
  assert.match(h, /Sem culpa: bora limpar\./);
  assert.equal((h.match(/class="rc-it velho"/g) || []).length, 1);
  assert.match(h, /class="rc-it prot"[^>]*><span>Pagar a Enel<\/span><small>protegido/);
  assert.match(h, /data-acao="rc_arquivar">Arquivar os de mais de 7 dias/);
  assert.ok(!h.includes("<b>dentista</b>"));
  assert.ok(!h.includes("rc-arq"));
});

test("recomeco depois: escolhe 3 (botao some ate marcar), arquivo com Ver/Desfazer/Devolver", () => {
  const h = html("recomeco", {
    total: 2, velhas: 0, arquivadas_n: 6,
    itens: [{ id: 2, titulo: "Pagar a Enel", dias: 2, protegido: true }, { id: 3, titulo: "Livro", dias: 3, protegido: false }],
    arquivo: [{ id: 9, titulo: "Fotos" }],
  });
  semFallback(h);
  assert.match(h, /de pé\. Escolhe os 3 que importam\./);
  assert.match(h, /<button type="button" aria-pressed="false" data-acao="rc_fica" class="rc-it prot pode"/);
  assert.match(h, /data-acao="rc_manter" hidden/);
  assert.match(h, /6 no arquivo/);
  assert.match(h, /data-acao="rc_desfazer"/);
  assert.match(h, /<div class="rc-arquivo" hidden>.*data-acao="rc_devolver"/s);
  assert.ok(!h.includes('data-acao="rc_arquivar"'));
  const tudo = html("recomeco", { total: 0, velhas: 0, arquivadas_n: 0, itens: [] });
  semFallback(tudo);
  assert.match(tudo, /Tudo em dia/);
  semFallback(html("recomeco", {}));
  assert.match(html("recomeco", { oculto: true }), /Oculto no modo visitante/);
});

test("mostrarPremioLiberado existe pro tarefas.js chamar", () => {
  assert.equal(typeof globalThis.mostrarPremioLiberado, "function");
});
