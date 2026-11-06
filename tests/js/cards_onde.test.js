// Painel mais esperto (06/11/2026, static/js/cards-onde.js): "Indo pro date?", diário do dia por lugar,
// "Sai às X" (meu tempo) e o recado de atraso. Puro, sem DOM. Dados inventados.
//
//   node --test tests/js/cards_onde.test.js
//
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const js = (f) => path.join(__dirname, "..", "..", "static", "js", f);
const Cards = require(js("cards.js"));
require(js("cards-d.js"));
const O = require(js("cards-onde.js"));

const AGORA = new Date(2026, 10, 6, 19, 31);
const html = (type, data) => Cards.renderizarCardHTML({ type, id: "c1", data, actions: [] }, { agora: AGORA });
const CARA_DE_IA = /fio-luz|luz-dedo|selo-brilho|eyebrow|text-transform:\s*uppercase|degrade|neon|tilt/;

test("indo_pra: pílula aberta com destino, chegada, linha do trajeto e os dois botões", () => {
  const h = html("indo_pra", {
    id: 4, tarefa_id: 7, titulo: "Indo pro date com a Júlia?", destino: "Viva Beach", hora: "20:00", estilo: "date",
    chega: "19:55", chega_s: 1440, gerado_ts: AGORA.getTime() / 1000, atrasa: false,
    eventos: [
      { hora: "19:30", titulo: "Saiu de casa", sub: "perto da hora de sair (19:35)", tipo: "saiu" },
      { hora: "19:40", titulo: "Lento na BR-470, Gaspar (2 km)", sub: "+4 min, já contado", tipo: "lento" },
      { hora: "19:55", titulo: "Chega no Viva Beach", sub: "5 min antes", tipo: "fim" },
    ],
  });
  assert.match(h, /class="vivo-d" data-v="indo" style="--cc:#f5a3b8" aria-expanded="true"/);
  assert.match(h, /<span class="v-t">Indo pro date com a Júlia\?<\/span>/);
  assert.match(h, /Viva Beach · date às 20:00/);
  assert.match(h, /<small>chega<\/small><b><span class="rl"/);
  assert.match(h, /<li class="on-ev lento" style="--k:1"><span class="h">19:40<\/span>/);
  assert.match(h, /<li class="on-ev fim"/);
  assert.match(h, /data-acao="indo_resposta" data-id="4" data-r="sim">É isso<\/button>/);
  assert.match(h, /data-acao="indo_resposta" data-id="4" data-r="outro">Vou pra outro lugar<\/button>/);
  assert.doesNotMatch(h, CARA_DE_IA);
});

test("indo_pra: escapa HTML, já respondido vira nota, sem chegada o campo some, atrasado marca", () => {
  const h = html("indo_pra", { id: 1, titulo: "<b>x</b>", destino: "<i>y</i>", eventos: [{ hora: "1", titulo: "<s>", tipo: "bomba" }] });
  assert.match(h, /&lt;b&gt;x&lt;\/b&gt;/);
  assert.doesNotMatch(h, /<i>y<\/i>|<s>/);
  assert.match(h, /class="on-ev saiu"/); // tipo desconhecido cai no neutro
  assert.doesNotMatch(h, /<small>chega<\/small>/);
  assert.match(html("indo_pra", { id: 1, titulo: "Indo?", resposta: "outro" }), /Beleza, não insisto\./);
  assert.match(html("indo_pra", { id: 1, titulo: "Indo?", atrasa: true, chega: "20:15" }), /data-atrasa="1"/);
  assert.match(html("indo_pra", { titulo: "Indo?", oculto: true }), /data-v="indo"/);
  assert.match(html("indo_pra", {}), /card-contrato-fallback/);
});

test("diario_lugares: barra do dia, lugar + hora + duração, 'fora' e a nota do caminho", () => {
  const h = html("diario_lugares", {
    dia: "2026-11-06", titulo: "Teu dia, por onde passou", n_lugares: 3, fora_min: 170,
    lugares: [
      { lugar: "Casa", hora: "00:00", ate: "08:10", min: 490, casa: true, sub: "desde ontem, saiu 08:10", cor: "#8a8a94" },
      { lugar: "Mecânico", hora: "08:30", ate: "09:40", min: 70, casa: false, sub: "feito: levar o carro", cor: "#8fd0ff" },
      { lugar: "Lugar sem nome", hora: "10:00", ate: "10:20", min: 20, casa: false, sub: "saiu 10:20", cor: "url(javascript:x)" },
    ],
    barra: [{ min: 490, casa: true }, { min: 20, vazio: true }, { min: 70, cor: "#8fd0ff" }, { min: 0, cor: "#fff" }],
  });
  assert.match(h, /data-v="diario" style="--cc:#9fdcb0"/);
  assert.match(h, /<span>3 lugares<\/span>/);
  assert.match(h, /<small>fora<\/small><b>2 h 50<\/b>/);
  assert.match(h, /<i class="casa" style="flex:490;--k:0"><\/i><i class="vazio" style="flex:20;--k:1"><\/i><i style="flex:70;--k:2;--lc:#8fd0ff"><\/i><\/div>/);
  assert.match(h, /<b>Mecânico<\/b><span>feito: levar o carro<\/span><\/span><span class="dur">1 h 10<\/span>/);
  assert.match(h, /<span class="dur">8 h 10<\/span>/);
  assert.doesNotMatch(h, /javascript/); // cor que não é #hex cai no padrão
  assert.match(h, /nunca o caminho/);
  assert.doesNotMatch(h, CARA_DE_IA);
  // sem 'fora' (sem casa no dia): o campo some; sem lugar nenhum: fallback
  assert.doesNotMatch(html("diario_lugares", { lugares: [{ lugar: "A", hora: "10:00", min: 30 }] }), /<small>fora/);
  assert.match(html("diario_lugares", { lugares: [] }), /card-contrato-fallback/);
  assert.match(html("diario_lugares", { titulo: "Ontem, por onde passou", oculto: true }), /Ontem, por onde passou/);
  assert.equal(O.duracao(218), "3 h 38");
  assert.equal(O.duracao(60), "1 h");
  assert.equal(O.duracao(5), "5 min");
});

test("meu_tempo: 'Sai às' com o jeito dele, barrinhas das últimas saídas e o segmentado", () => {
  const base = { tarefa_id: 7, titulo: "Date com a Júlia", hora: "19:40", estilo: "date", sair_meu: "19:05", sair_padrao: "19:15",
    ajuste_min: 10, saida_min: 10, trajeto_min: 0, amostras: [8, 12, 6, 14, 9, 11], usar: "meu" };
  const h = html("meu_tempo", base);
  assert.match(h, /<span class="v-t">Sai às 19:05<\/span>/);
  assert.match(h, /10 min antes: é o teu jeito/);
  assert.match(h, /<small>date<\/small><b>19:40<\/b>/);
  assert.match(h, /Nas últimas 6 saídas tu saiu de casa uns <b>10 min depois<\/b> do aviso\. Então eu já aviso 10 min antes\./);
  assert.equal((h.match(/<div style="--k:\d"><i style="height:\d+px"><\/i><small>\+\d+<\/small><\/div>/g) || []).length, 6);
  assert.match(h, /style="--i:0"/);
  assert.match(h, /data-acao="meu_tempo_usar" data-v="meu" aria-pressed="true">Meu tempo/);
  assert.match(h, /data-meu="19:05" data-padrao="19:15"/);
  const p = html("meu_tempo", { ...base, usar: "padrao", trajeto_min: 4 });
  assert.match(p, /Sai às 19:15/);
  assert.match(p, /o padrão: trajeto \+ folga/);
  assert.match(p, /style="--i:1"/);
  assert.match(p, /E nesse horário o caminho leva uns 4 min a mais/);
  assert.match(html("meu_tempo", { ...base, estilo: null, titulo: "Dentista" }), /<small>dentista<\/small>/);
  assert.match(html("meu_tempo", { ...base, sair_meu: null }), /card-contrato-fallback/);
  assert.doesNotMatch(h, CARA_DE_IA);
});

test("recado_atraso: chips trocam o número, balão com o texto, WhatsApp com o texto e nunca manda sozinho", () => {
  const d = { tarefa_id: 7, indo_id: 4, titulo: "date com a Júlia", hora: "19:40", chega: "19:52", atraso_min: 12, escolhido: 15,
    opcoes: [10, 15, 20], modelo: "transito", via: "BR-470", texto: "x" };
  const h = html("recado_atraso", d);
  assert.match(h, /data-v="recado" style="--cc:#f47671"/);
  assert.match(h, /<span class="v-t">Vai chegar 19:52<\/span>/);
  assert.match(h, /date com a Júlia às 19:40 · lento na BR-470/);
  assert.match(h, /<small>atraso<\/small><b>12 min<\/b>/);
  assert.match(h, /data-m="15" aria-pressed="true">15 min<\/button>/);
  assert.match(h, /data-m="10" aria-pressed="false">10 min<\/button>/);
  assert.match(h, /<div class="on-balao" aria-live="polite">Oi! Peguei trânsito na BR-470, chego uns 15 min atrasado\. Já tô a caminho\.<\/div>/);
  assert.match(h, /<a class="pri on-zap" href="https:\/\/wa\.me\/\?text=Oi!%20Peguei%20tr%C3%A2nsito%20na%20BR-470%2C%20chego%20uns%2015%20min/);
  assert.match(h, /rel="noopener noreferrer">Abrir no WhatsApp<\/a>/);
  assert.match(h, /Quem manda é tu\./);
  assert.doesNotMatch(h, /fetch|send|enviar automatic/i);
  // mesmo texto do servidor (onde_vou.texto_recado)
  assert.equal(O.textoRecado("transito", 10, ""), "Oi! Peguei trânsito, chego uns 10 min atrasado. Já tô a caminho.");
  assert.equal(O.textoRecado("saindo", 20), "Oi! Vou chegar uns 20 min atrasado. Já já tô saindo.");
  assert.equal(O.textoRecado("caminho", 5), "Oi! Vou chegar uns 5 min atrasado. Já tô a caminho.");
  assert.equal(O.linkZap("a&b"), "https://wa.me/?text=a%26b");
  // sem chegada: título pelo atraso; opções tortas: 10/15/20; via com HTML é escapada
  const s = html("recado_atraso", { titulo: "x", opcoes: ["<b>", -3], via: "<img>", modelo: "transito" });
  assert.match(s, /Vai atrasar uns 15 min/);
  assert.match(s, /data-m="20"/);
  assert.doesNotMatch(s, /<img>/);
  assert.match(html("recado_atraso", { titulo: "x", oculto: true }), /Vai atrasar/);
  assert.doesNotMatch(h, CARA_DE_IA);
});
