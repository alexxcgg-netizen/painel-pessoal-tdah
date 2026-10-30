// Treino ao vivo em 3D (leva 29/10): catalogo + mapeador "nome livre da ficha" -> exercicio animado
// (static/js/treino3d-catalogo.js) e o modulo gerado do motor (static/treino3d/treino3d.js).
//
//   node --test tests/js/treino3d.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const STATIC = path.join(__dirname, "..", "..", "static");
const T = require(path.join(STATIC, "js", "treino3d-catalogo.js"));

test("catalogo com os 215 exercicios, todos com molde e sem nome repetido", () => {
  assert.ok(T.lista.length >= 215, String(T.lista.length));
  assert.equal(new Set(T.lista).size, T.lista.length);
  for (const nome of T.lista) {
    const c = T.acha(nome);
    assert.equal(c[1], nome);
    assert.ok(typeof c[2] === "string" && c[2] && !c[2].startsWith("~"), nome);
    assert.equal(typeof c[3], "object");
  }
  assert.equal(T.acha("nao existe"), null);
  assert.equal(T.acha(""), null);
});

test("cada nome do catalogo casa com ele mesmo (com e sem acento, maiuscula)", () => {
  for (const nome of T.lista) {
    assert.equal(T.tipo(nome), nome, nome);
    assert.equal(T.tipo(nome.toUpperCase().normalize("NFD").replace(/[̀-ͯ]/g, "")), nome, nome);
  }
});

test("nome solto da ficha vira o exercicio certo (variacao mais comum quando ele nao diz)", () => {
  const casos = {
    "Supino reto": "Supino reto com barra", "supino reto 4x10 com 20kg": "Supino reto com barra",
    "SUPINO INCLINADO COM HALTERES": "Supino inclinado com halteres", "Supino declinado": "Supino declinado com barra",
    "Tríceps testa": "Tríceps testa com barra W", "Triceps corda": "Tríceps na polia com corda", "Tríceps pulley": "Tríceps na polia com corda",
    "Tríceps francês": "Tríceps francês com halter", "Extensora": "Cadeira extensora", "Mesa flexora": "Mesa flexora",
    "Cadeira abdutora": "Cadeira abdutora", "Cadeira adutora": "Cadeira adutora", "Agachamento": "Agachamento livre com barra",
    "Agachamento búlgaro": "Agachamento búlgaro", "Leg press": "Leg press 45°", "Leg 45": "Leg press 45°", "Hack": "Agachamento hack na máquina",
    "Elevação lateral": "Elevação lateral com halteres", "Elevação pélvica": "Elevação pélvica com barra (hip thrust)",
    "Hip thrust": "Elevação pélvica com barra (hip thrust)", "Remada unilateral": "Remada unilateral com halter (serrote)",
    "Serrote": "Remada unilateral com halter (serrote)", "Remada sentada": "Remada baixa na polia (triângulo)", "Remada alta": "Remada alta com barra",
    "Voador": "Voador (peck deck)", "Peck deck": "Voador (peck deck)", "Voador inverso": "Crucifixo inverso na máquina",
    "Crucifixo": "Crucifixo reto com halteres", "Crossover": "Crossover na polia alta", "Rosca martelo": "Rosca martelo",
    "Rosca direta": "Rosca direta com barra", "Rosca Scott": "Rosca Scott com barra", "Desenvolvimento militar": "Desenvolvimento com barra em pé",
    "Puxada frente": "Puxada frontal pegada aberta", "Pulldown": "Pulldown com corda", "Barra fixa": "Barra fixa pronada",
    "Terra": "Levantamento terra", "Stiff": "Stiff com barra", "RDL": "Levantamento terra romeno", "Panturrilha em pé": "Panturrilha em pé na máquina",
    "Flexão de braço": "Flexão de braço", "Prancha": "Prancha frontal", "Abdominal": "Abdominal supra no solo", "Afundo": "Avanço com halteres",
    "Mergulho": "Mergulho nas paralelas (peito)", "Encolhimento": "Encolhimento com barra", "Esteira": "Esteira", "Bike": "Bicicleta ergométrica",
    "Bicicleta": "Bicicleta ergométrica",
  };
  for (const [nome, esperado] of Object.entries(casos)) assert.equal(T.tipo(nome), esperado, nome);
});

test("nome que nao casa com seguranca = null (painel escondido, nunca a animacao de outro)", () => {
  for (const nome of ["Corrida na rua", "Natação", "Alongamento", "Supino reto pegada aberta", "abc", "", "   ", "4x10", null, undefined, 42, {}]) {
    assert.equal(T.tipo(nome), null, String(nome));
  }
});

test("modulo do motor: imports so do three vendorizado, sem biblioteca/#perf do prototipo, com o contrato do card", () => {
  const m = fs.readFileSync(path.join(STATIC, "treino3d", "treino3d.js"), "utf8");
  const imports = [...m.matchAll(/^import .* from "([^"]+)";$/gm)].map((x) => x[1]);
  assert.deepEqual(imports.sort(), ["/static/vendor/three/RoomEnvironment.js", "/static/vendor/three/RoundedBoxGeometry.js", "/static/vendor/three/three.module.min.js"]);
  for (const f of imports) assert.ok(fs.existsSync(path.join(STATIC, "..", f)), f);
  assert.ok(!/from "three/.test(m));
  assert.ok(!m.includes("#perf") && !m.includes("desenhaLista") && !m.includes("document.querySelector("));
  assert.match(m, /fetch\("\/static\/treino3d\/corpo\.json"\)/);
  assert.match(m, /palco\.dispatchEvent\(new CustomEvent\("rep"/);
  assert.match(m, /Object\.assign\(window\.TREINO3D, \{ palco, tamanho, toca:/);
  // todo molde que o catalogo usa existe no motor
  for (const nome of T.lista) {
    const molde = T.acha(nome)[2];
    assert.ok(new RegExp(String.raw`(^|[\s.])${molde}\s*(:\s*\{|=)`, "m").test(m), `${nome} -> ${molde}`);
  }
  for (const f of ["RoomEnvironment.js", "RoundedBoxGeometry.js"]) {
    assert.ok(!/from 'three'/.test(fs.readFileSync(path.join(STATIC, "vendor", "three", f), "utf8")), f);
  }
  const corpo = JSON.parse(fs.readFileSync(path.join(STATIC, "treino3d", "corpo.json"), "utf8"));
  assert.ok(corpo && typeof corpo === "object");
});
