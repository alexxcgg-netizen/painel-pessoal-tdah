// Motor 3D dos exercicios (static/js/exercicio-3d.js): nome livre da ficha -> tipo, e todo tipo
// desenha em qualquer ponto do movimento sem NaN (o laco no navegador so repete isso por quadro).
//
//   node --test tests/js/exercicio.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const Exercicio = require(path.join(__dirname, "..", "..", "static", "js", "exercicio-3d.js"));

test("~40 exercicios, todos desenham do comeco ao fim do movimento", () => {
  assert.ok(Exercicio.lista.length >= 40, String(Exercicio.lista.length));
  for (const tp of Exercicio.lista) {
    for (const t of [0, 0.25, 0.5, 0.75, 1]) {
      const svg = Exercicio.desenhar(tp, t, 0.8);
      assert.ok(svg.startsWith("<defs>"), tp);
      assert.ok(!/NaN|undefined|Infinity/.test(svg), `${tp} t=${t}`);
    }
  }
  assert.equal(Exercicio.desenhar("nao_existe", 0), "");
});

test("ids de gradiente unicos por desenho (dois paineis na tela nao se misturam)", () => {
  const a = Exercicio.desenhar("supino_barra", 0).match(/id="gPele(\w+)"/)[1];
  const b = Exercicio.desenhar("supino_barra", 0).match(/id="gPele(\w+)"/)[1];
  assert.notEqual(a, b);
});

test("nome da ficha (texto livre, com ou sem acento) vira o tipo certo; desconhecido vira null", () => {
  const casos = {
    "Supino reto": "supino_barra", "SUPINO INCLINADO COM HALTERES": "supino_inclinado", "Supino declinado": "supino_declinado",
    "Tríceps testa": "triceps_testa", "Triceps corda": "triceps_corda", "Tríceps francês": "triceps_frances",
    "Cadeira flexora": "flexora", "Mesa flexora": "flexora", "Cadeira extensora": "extensora", "Cadeira abdutora": "abdutora",
    "Agachamento búlgaro": "bulgaro", "Agachamento livre": "agachamento", "Leg press 45": "leg_press",
    "Elevação lateral": "elevacao_lateral", "Elevação pélvica": "elevacao_pelvica", "Elevação de pernas": "elevacao_pernas",
    "Remada unilateral": "serrote", "Remada baixa": "remada_baixa", "Remada curvada": "remada_curvada",
    "Voador": "peck_deck", "Voador inverso": "crucifixo_inverso", "Crucifixo": "crucifixo", "Crossover": "crossover",
    "Rosca martelo": "rosca_martelo", "Rosca direta": "rosca_direta", "Rosca Scott": "rosca_scott",
    "Desenvolvimento com halteres": "desenvolvimento_halter", "Desenvolvimento militar": "desenvolvimento_barra",
    "Puxada frente": "puxada", "Barra fixa": "barra_fixa", "Levantamento terra": "terra", "Stiff": "stiff",
    "Panturrilha em pé": "panturrilha", "Flexão de braço": "flexao", "Prancha": "prancha", "Abdominal": "abdominal",
    "Afundo": "avanco", "Mergulho": "mergulho", "Encolhimento": "encolhimento", "Pullover": "pullover",
  };
  for (const [nome, tp] of Object.entries(casos)) {
    assert.equal(Exercicio.tipo(nome), tp, nome);
    assert.ok(Exercicio.lista.includes(tp), tp);
  }
  for (const nome of ["Esteira", "Remada alta", "Cadeira adutora", "", null, undefined, 42]) assert.equal(Exercicio.tipo(nome), null, String(nome));
});
