// GERADO por docs/prototipos/academia-3d/academia/build_app.py (motor.js + moldes/*.js do protótipo) - não editar à mão.
// Treino ao vivo em 3D: corpo MakeHuman (CC0), three.js r170 (MIT, static/vendor/three). Carregado pelo cards-vivos.js
// só quando um card treino_agora tem exercício conhecido. window.TREINO3D: usa(molde, nome, params), palco, toca(on).
import * as THREE from "/static/vendor/three/three.module.min.js";
import { RoomEnvironment } from "/static/vendor/three/RoomEnvironment.js";
import { RoundedBoxGeometry } from "/static/vendor/three/RoundedBoxGeometry.js";

/* Treino 3D: corpo MakeHuman (CC0) com esqueleto de 53 ossos. Todos os ossos têm rotação identidade no repouso,
   então o eixo local de cada osso = eixo do corpo em pé: X = esquerda do personagem, Y = cima, Z = frente.
   Cada molde monta o equipamento (cena) e posa o corpo por quadro (pose(t)): tronco por rotações locais,
   braços e pernas por IK de 2 ossos com vetor de polo. t = 0 em cima (contraído/travado), t = 1 no fim da descida. */
const V3 = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
const reduz = matchMedia("(prefers-reduced-motion: reduce)").matches;
const RAIZ3D = document.createElement("div");
RAIZ3D.innerHTML = `<div class="t3-palco" id="palco"><svg class="t3-guia" id="guia" aria-hidden="true"><path/><circle class="halo" r="9"/><circle r="3.2"/></svg>` +
  `<div class="t3-etq" id="etq"><small>pega mais em</small><b></b><span></span></div><div class="t3-fase"><i id="ponto"></i><span id="faseTxt"></span></div></div>` +
  `<div hidden><i id="carregando"></i><i id="nome"></i><i id="dica"></i><i id="chips"></i><i id="reps"></i><button id="btPlay"></button><button id="btGira"></button><button id="btLento"></button></div>`;
const PALCO3D = RAIZ3D.firstChild; // sai do RAIZ3D quando vai pro card: procura nos dois
const $ = (s) => RAIZ3D.querySelector(s) || PALCO3D.querySelector(s);

// ---------- corpo ----------
const C = await (await fetch("/static/treino3d/corpo.json")).json();
function dec(b64, T) { const s = atob(b64), u = new Uint8Array(s.length); for (let i = 0; i < s.length; i++) u[i] = s.charCodeAt(i); return new T(u.buffer); }
const ossos = C.ossos.map((o) => Object.assign(new THREE.Bone(), { name: o.n }));
const B = Object.fromEntries(ossos.map((b) => [b.name, b]));
const CAB = {}, DIR = {}, COMP = {};
C.ossos.forEach((o, i) => {
  const b = ossos[i], c = V3(...o.c), t = V3(...o.t);
  CAB[o.n] = c; DIR[o.n] = t.clone().sub(c).normalize(); COMP[o.n] = t.distanceTo(c);
  if (o.p < 0) b.position.copy(c); else { ossos[o.p].add(b); b.position.copy(c).sub(V3(...C.ossos[o.p].c)); }
});
const POS_PELVIS = B.pelvis.position.clone();
const MUSC = C.musculos, musU = new Float32Array(16), musAlvo = new Float32Array(16);

// músculo em foco: até 64 segmentos (feixes) numa textura; cada um = cápsula achatada colada na pele (repouso, lado esquerdo;
// o direito é espelho em x). Linha 0: ponta A + raio (negativo = tendão); 1: ponta B + raio; 2: normal da pele + (índice + raio de fundo).
const NSEG = 128, NMUS = 8;
const SEGD = new Float32Array(NSEG * 4 * 4), SEGT = new THREE.DataTexture(SEGD, NSEG, 4, THREE.RGBAFormat, THREE.FloatType);
SEGT.minFilter = SEGT.magFilter = THREE.NearestFilter; SEGT.needsUpdate = true;
const FOCO = { n: 0, I: [...Array(NMUS)].map(() => new THREE.Vector4()), X: [...Array(NMUS)].map(() => new THREE.Vector4()), K: new Float32Array(NMUS), G: new Float32Array(NMUS), alvo: new Float32Array(NMUS), esf: { value: 0 }, nseg: { value: 0 } };
const GLSL_MUSC = `
uniform highp sampler2D uSeg; uniform int uNS; uniform vec4 uMI[${NMUS}]; uniform vec4 uMX[${NMUS}]; uniform float uMK[${NMUS}]; uniform float uEsf; uniform float uGr[${NMUS}];
// devolve: x = máscara do músculo vencedor, y = tendão, z = barriga (0..1 no meio), w = índice.
// Distância normalizada e (<1 dentro; negativa no miolo dos leques). Vence o músculo de menor e; gDiv = folga até o 2º
// (perto de 0 = fronteira entre dois músculos -> sulco), gE2 = e do 2º.
float gDiv = 9.0, gE2 = 9.0, gMesmo = 0.0; // gMesmo = 1 se a fronteira é entre partes do mesmo músculo
vec4 musculo(vec3 pr, vec3 nr, float folga) {
  float eb[${NMUS}]; float et[${NMUS}]; float bz[${NMUS}]; float ec[${NMUS}]; // ec: só os feixes (decide a divisão)
  for (int j = 0; j < ${NMUS}; j++) { eb[j] = 9.0; et[j] = 9.0; bz[j] = 0.0; ec[j] = 9.0; }
  for (int i = 0; i < ${NSEG}; i++) {
    if (i >= uNS) break;
    vec4 a = texelFetch(uSeg, ivec2(i, 0), 0), b = texelFetch(uSeg, ivec2(i, 1), 0), q = texelFetch(uSeg, ivec2(i, 2), 0), c = texelFetch(uSeg, ivec2(i, 3), 0);
    vec3 ab = b.xyz - a.xyz; float t = clamp(dot(pr - a.xyz, ab) / max(dot(ab, ab), 1e-6), 0.0, 1.0);
    vec3 d = pr - (a.xyz + ab * t); float dn = dot(d, q.xyz); vec3 dl = d - q.xyz * dn;
    float r = mix(abs(a.w), b.w, t) * folga, rd = fract(q.w) * folga, e;
    if (c.w > 0.5) { // triângulo a-b-c: dentro = negativo (quanto mais pro miolo), fora = distância até a borda
      vec3 ac = c.xyz - a.xyz, nt = normalize(cross(ab, ac)); vec3 pa = pr - a.xyz; dn = dot(pa, nt); vec3 qq = pr - nt * dn;
      vec3 e0 = b.xyz - a.xyz, e1 = c.xyz - b.xyz, e2v = a.xyz - c.xyz, q0 = qq - a.xyz, q1 = qq - b.xyz, q2 = qq - c.xyz;
      bool dentro = dot(cross(e0, q0), nt) >= 0.0 && dot(cross(e1, q1), nt) >= 0.0 && dot(cross(e2v, q2), nt) >= 0.0;
      vec3 w0 = q0 - e0 * clamp(dot(q0, e0) / dot(e0, e0), 0.0, 1.0), w1 = q1 - e1 * clamp(dot(q1, e1) / dot(e1, e1), 0.0, 1.0), w2 = q2 - e2v * clamp(dot(q2, e2v) / dot(e2v, e2v), 0.0, 1.0);
      float dw = sqrt(min(dot(w0, w0), min(dot(w1, w1), dot(w2, w2))));
      int fl = int(c.w + 0.5) - 1; float big = 1e4;
      float db = sqrt(min((fl & 1) != 0 ? dot(w0, w0) : big, min((fl & 2) != 0 ? dot(w1, w1) : big, (fl & 4) != 0 ? dot(w2, w2) : big)));
      r = abs(a.w) * folga; t = 0.5;
      float zz = dn * dn / (rd * rd);
      e = dentro ? sqrt(zz) - min(db / r, 1.0) * 0.9 : sqrt(dw * dw / (r * r) + zz);
    } else e = sqrt(dot(dl, dl) / (r * r) + dn * dn / (rd * rd));
    e /= max(smoothstep(-0.6, -0.15, dot(nr, q.xyz)), 0.05);
    int k = int(q.w);
    ec[k] = min(ec[k], e);
    if (a.w < 0.0) et[k] = min(et[k], e); else { eb[k] = min(eb[k], e); bz[k] = max(bz[k], clamp(1.0 - e * e, 0.0, 1.0) * sin(3.1416 * clamp(t * 0.8 + 0.1, 0.0, 1.0))); }
  }
  // vence o músculo cujo feixe está mais perto (entre os que cobrem o ponto); a fronteira fica no meio do caminho
  float c1 = 99.0, c2 = 99.0, f2 = 9.0; int w = 0, w2 = 0;
  for (int j = 0; j < ${NMUS}; j++) {
    float fj = min(eb[j], et[j]);
    if (uMK[j] < 0.001 || fj > 1.0) continue;
    float cj = min(ec[j], et[j]);
    if (cj < c1) { c2 = c1; w2 = w; c1 = cj; f2 = 9.0; w = j; } else if (cj < c2) { c2 = cj; f2 = fj; w2 = j; }
  }
  if (c1 > 98.0) { for (int j = 0; j < ${NMUS}; j++) { float fj = min(eb[j], et[j]); if (uMK[j] > 0.001 && fj < min(eb[w], et[w])) w = j; } }
  gDiv = c2 - c1; gE2 = c2 > 98.0 ? 9.0 : 0.0; gMesmo = uGr[w] > 0.5 && abs(uGr[w] - uGr[w2]) < 0.5 ? 1.0 : 0.0;
  float mm = 1.0 - smoothstep(0.78, 1.0, min(eb[w], et[w]));
  return vec4(mm * uMK[w], et[w] < eb[w] ? smoothstep(0.0, 0.25, eb[w] - et[w]) : 0.0, bz[w], float(w));
}
`;
const ESTILO = { esc: { value: 1 }, alvoEsc: 1, atlas: 1, alvoAtlas: 1, anim: false }; // padrão: esculpido + atlas
function comMusculo(mat, forca = 1) {
  mat.onBeforeCompile = (sh) => {
    sh.uniforms.uEscV = ESTILO.esc;
    Object.assign(sh.uniforms, { uGr: { value: FOCO.G }, uSeg: { value: SEGT }, uNS: FOCO.nseg, uMI: { value: FOCO.I }, uMX: { value: FOCO.X }, uMK: { value: FOCO.K }, uEsf: FOCO.esf });
    sh.vertexShader = sh.vertexShader
      .replace("#include <common>", "#include <common>\nattribute float aEsc; attribute vec3 aNrE; uniform float uEscV;\n" + GLSL_MUSC + "\nvarying vec3 vPr;\nvarying vec3 vNr;\nvarying float vPerto;")
      .replace("#include <beginnormal_vertex>", "#include <beginnormal_vertex>\nobjectNormal = normalize(mix(objectNormal, aNrE, uEscV));")
      .replace("#include <begin_vertex>", "#include <begin_vertex>\n" +
        "transformed += normal * aEsc * uEscV;\n" +
        "vPr = vec3(abs(position.x), position.y, position.z); vNr = vec3(position.x < 0.0 ? -normal.x : normal.x, normal.yz);\n" +
        "vPerto = 0.0;\nif (uNS > 0) { vec4 m1 = musculo(vPr, vNr, 1.35); vPerto = m1.x;\n" +
        // incha: barriga do músculo cresce um pouco no esforço (tendão não)
        "  transformed += normal * m1.x * (1.0 - m1.y) * m1.z * uMX[int(m1.w)].w * uMX[int(m1.w)].w * (0.0025 + 0.006 * uEsf); }");
    sh.fragmentShader = sh.fragmentShader
      .replace("#include <common>", "#include <common>\n" + GLSL_MUSC + `
varying vec3 vPr; varying vec3 vNr; varying float vPerto;
float h21(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vn(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(h21(i), h21(i + vec2(1, 0)), f.x), mix(h21(i + vec2(0, 1)), h21(i + vec2(1, 1)), f.x), f.y); }
vec3 bumpMus(vec3 pos, vec3 nrm, float H, float k, float fd) {
  vec2 dH = vec2(dFdx(H), dFdy(H)) * k; vec3 sx = normalize(dFdx(pos)), sy = normalize(dFdy(pos));
  vec3 r1 = cross(sy, nrm), r2 = cross(nrm, sx); float det = dot(sx, r1) * fd;
  return normalize(abs(det) * nrm - sign(det) * (dH.x * r1 + dH.y * r2));
}
vec4 gMus = vec4(0.0); vec3 gCor = vec3(0.0);`)
      .replace("#include <normal_fragment_maps>", "#include <normal_fragment_maps>\n" + `
// laço só perto do músculo; derivadas (dFdx/fwidth) sempre fora de if, senão a borda serrilha
vec4 mv = vec4(0.0); if (vPerto > 0.002) mv = musculo(vPr, normalize(vNr), 1.0);
float sulco = (1.0 - smoothstep(0.0, min(fwidth(gDiv), 0.2) * 1.3 + 0.03, gDiv)) * step(gE2, 1.0) * (1.0 - 0.6 * gMesmo); // fronteira entre dois músculos
int w = int(mv.w); float m = mv.x * ${forca.toFixed(2)};
vec3 I = uMI[w].xyz, ax = uMX[w].xyz, nr = normalize(vNr);
vec3 rp = normalize(cross(ax, nr) + vec3(1e-5)); vec3 dI = vPr - I; float L = length(dI);
float sF = dot(dI / max(L, 1e-4), rp) * uMI[w].w;            // atravessa as fibras
sF += (vn(vec2(L * 28.0, sF * 0.18)) - 0.5) * 0.55 + (vn(vec2(L * 90.0, sF * 0.5)) - 0.5) * 0.15;             // fibra ondula de leve
float fwS = fwidth(sF);
float f = fract(sF), h = smoothstep(0.0, 1.0, 1.0 - abs(f * 2.0 - 1.0));
float fino = 0.5 + 0.5 * sin(sF * 18.85 + vn(vec2(L * 140.0, sF)) * 3.0);
float aa = 1.0 - smoothstep(0.25, 0.7, fwS), aaf = 1.0 - smoothstep(0.08, 0.25, fwS);
float hh = mix(0.5, h * 0.72 + mix(0.5, fino, aaf) * 0.28, aa);
float kw = uMX[w].w, vis = mix(0.14, 1.0, smoothstep(0.08, 1.0, kw * kw * (3.0 - 2.0 * kw)));
float a = smoothstep(0.04, 0.42, m) * vis, ten = mv.y; sulco *= vis;
vec3 nb = bumpMus(-vViewPosition, normal, hh - sulco * 1.6, smoothstep(0.1, 1.0, a) * mix(0.6, 0.3, ten) * vis, faceDirection);
if (m > 0.002) {
  float esf = uEsf * uMX[w].w;
  float fx = h21(vec2(floor(sF), 7.0)) - 0.5; // cada fascículo com um tom
  // quanto mais o músculo trabalha (k), mais vermelho vivo; pouco = rosado, desbotado
  float kk = smoothstep(0.1, 1.0, uMX[w].w);
  vec3 escuro = mix(vec3(0.17, 0.07, 0.065), mix(vec3(0.05, 0.002, 0.003), vec3(0.075, 0.002, 0.003), esf), kk);
  vec3 claro = mix(vec3(0.42, 0.19, 0.17), mix(vec3(0.30, 0.008, 0.01), vec3(0.42, 0.006, 0.008), esf), kk) * (1.0 + fx * 0.3 * vis);
  vec3 cm = mix(escuro, claro, 0.22 + 0.78 * hh);
  cm = mix(cm, mix(vec3(0.45, 0.40, 0.34), vec3(0.80, 0.74, 0.64), hh), ten);
  float borda = smoothstep(0.08, 0.35, m) * (1.0 - smoothstep(0.35, 0.8, m));
  gCor = cm * (1.0 - 0.12 * borda) * (1.0 - 0.7 * sulco); gMus = vec4(a, ten, esf * kk * kk, borda);
  normal = nb;
  roughnessFactor = mix(roughnessFactor, mix(0.46, 0.55, ten), a);
}
`)
      .replace("#include <lights_physical_fragment>", "#include <lights_physical_fragment>\n" +
        "material.sheenColor *= 1.0 - gMus.x;\n#ifdef USE_CLEARCOAT\nmaterial.clearcoat *= 1.0 - gMus.x;\n#endif\nmaterial.specularColor = mix(material.specularColor, vec3(0.03), gMus.x);")
      .replace("#include <emissivemap_fragment>", "#include <emissivemap_fragment>\n" +
        "diffuseColor.rgb = mix(diffuseColor.rgb, gCor, gMus.x);\n" +
        "totalEmissiveRadiance += vec3(0.34, 0.004, 0.004) * gMus.x * (1.0 - gMus.y) * (0.04 + 0.6 * gMus.z);");
  };
  return mat;
}
function malha(d, mat) {
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(dec(d.pos, Float32Array), 3));
  g.setIndex(new THREE.BufferAttribute(dec(d.ind, Uint16Array), 1));
  g.setAttribute("skinIndex", new THREE.BufferAttribute(dec(d.si, Uint8Array), 4));
  g.setAttribute("skinWeight", new THREE.BufferAttribute(dec(d.sw, Uint8Array), 4, true));
  g.setAttribute("aMid", new THREE.BufferAttribute(new Float32Array(dec(d.mid, Uint8Array)), 1));
  g.setAttribute("aMw", new THREE.BufferAttribute(new Float32Array(dec(d.mw, Uint8Array)).map((x) => x / 255), 1));
  g.computeVertexNormals();
  if (d.grupo) { const n = g.index.count; g.addGroup(0, d.grupo, 0); g.addGroup(d.grupo, n - d.grupo, 1); }
  const m = new THREE.SkinnedMesh(g, mat);
  m.castShadow = m.receiveShadow = true; m.frustumCulled = false;
  return m;
}
const pele = comMusculo(new THREE.MeshPhysicalMaterial({ color: 0xc9a58c, roughness: 0.55, sheen: 0.35, sheenRoughness: 0.6, sheenColor: new THREE.Color(0xffd9c2), clearcoat: 0.08, clearcoatRoughness: 0.6 }));
const tecido = comMusculo(new THREE.MeshPhysicalMaterial({ color: 0x23262d, roughness: 0.82, sheen: 0.6, sheenRoughness: 0.8, sheenColor: new THREE.Color(0x5a6070) }), 0.9);
const rig = new THREE.Group();
const corpo = malha(C.corpo, [pele, tecido]);
rig.add(ossos[0], corpo);
rig.updateMatrixWorld(true);
const esqueleto = new THREE.Skeleton(ossos);
corpo.bind(esqueleto);

// ---------- palco ----------
const palco = $("#palco");
const T_INICIO = performance.now();
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.AgXToneMapping; renderer.toneMappingExposure = 1.15;
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
palco.prepend(renderer.domElement);
const cena = new THREE.Scene();
cena.background = new THREE.Color(0x14161b);
const pmrem = new THREE.PMREMGenerator(renderer);
cena.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
cena.environmentIntensity = 0.38;
const chave = new THREE.DirectionalLight(0xfff1e2, 2.6); chave.position.set(2.2, 4.2, 2.6);
chave.castShadow = true; chave.shadow.mapSize.set(2048, 2048); chave.shadow.bias = -0.0004; chave.shadow.normalBias = 0.025;
Object.assign(chave.shadow.camera, { left: -1.8, right: 1.8, top: 1.8, bottom: -1.8, near: 0.5, far: 10 });
const contra = new THREE.DirectionalLight(0xbcd2ff, 1.7); contra.position.set(-3, 2.6, -3.2);
const preenche = new THREE.HemisphereLight(0xdfe6f2, 0x1a1c20, 0.35);
cena.add(chave, chave.target, contra, preenche, rig);
// chão: sombra + mancha de luz de estúdio que some no fundo
const chao = new THREE.Mesh(new THREE.PlaneGeometry(12, 12), new THREE.ShadowMaterial({ opacity: 0.5 }));
chao.rotation.x = -Math.PI / 2; chao.receiveShadow = true; cena.add(chao);
const cv = Object.assign(document.createElement("canvas"), { width: 256, height: 256 }), g2 = cv.getContext("2d");
const grad = g2.createRadialGradient(128, 128, 0, 128, 128, 128);
grad.addColorStop(0, "rgba(255,240,225,0.16)"); grad.addColorStop(0.55, "rgba(255,240,225,0.05)"); grad.addColorStop(1, "rgba(255,240,225,0)");
g2.fillStyle = grad; g2.fillRect(0, 0, 256, 256);
const luzChao = new THREE.Mesh(new THREE.CircleGeometry(2.4, 64), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(cv), transparent: true, depthWrite: false }));
luzChao.rotation.x = -Math.PI / 2; luzChao.position.y = 0.001; cena.add(luzChao);
const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 40);

// ---------- materiais de equipamento ----------
const M = {
  cromo: new THREE.MeshStandardMaterial({ color: 0xd8dce2, metalness: 1, roughness: 0.22 }),
  aco: new THREE.MeshStandardMaterial({ color: 0x8d939c, metalness: 1, roughness: 0.38 }),
  quadro: new THREE.MeshStandardMaterial({ color: 0x2c2f36, metalness: 0.55, roughness: 0.42 }),
  estofado: new THREE.MeshPhysicalMaterial({ color: 0x1d1f24, roughness: 0.5, sheen: 0.4, sheenColor: new THREE.Color(0x3a3f4a), clearcoat: 0.25, clearcoatRoughness: 0.45 }),
  borracha: new THREE.MeshStandardMaterial({ color: 0x18191c, roughness: 0.68, metalness: 0.05 }),
  faixa: new THREE.MeshStandardMaterial({ color: 0x3f6fd8, roughness: 0.55 }),
  tenis: new THREE.MeshPhysicalMaterial({ color: 0xe9eaee, roughness: 0.6, sheen: 0.3 }),
};
const sombreia = (o) => { o.traverse((m) => { if (m.isMesh) { m.castShadow = true; m.receiveShadow = true; } }); return o; };
function cil(r, l, mat, seg = 32) { const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, l, seg), mat); return m; }
function anilha(r = 0.225, e = 0.045) { // perfil de anilha de borracha: aro, face rebaixada, cubo de aço
  const p = [V3(0.026, -e / 2), V3(0.05, -e / 2), V3(0.06, -e / 2 + 0.008), V3(r - 0.03, -e / 2 + 0.008), V3(r - 0.012, -e / 2), V3(r, -e / 2 + 0.008),
    V3(r, e / 2 - 0.008), V3(r - 0.012, e / 2), V3(r - 0.03, e / 2 - 0.008), V3(0.06, e / 2 - 0.008), V3(0.05, e / 2), V3(0.026, e / 2)];
  const g = new THREE.Group();
  g.add(new THREE.Mesh(new THREE.LatheGeometry(p.map((v) => new THREE.Vector2(v.x, v.y)), 64), M.borracha));
  const cubo = cil(0.052, e + 0.004, M.aco, 40); g.add(cubo);
  return g;
}
function barra(kgLado = 1) { // barra olímpica 2,20 m no eixo X local
  const g = new THREE.Group();
  const haste = cil(0.014, 1.31, M.cromo); haste.rotation.z = Math.PI / 2; g.add(haste);
  for (const s of [-1, 1]) {
    const colar = cil(0.026, 0.03, M.aco); colar.rotation.z = Math.PI / 2; colar.position.x = s * 0.67; g.add(colar);
    const manga = cil(0.025, 0.41, M.cromo); manga.rotation.z = Math.PI / 2; manga.position.x = s * 0.89; g.add(manga);
    for (let i = 0; i < kgLado; i++) { const a = anilha(); a.rotation.z = Math.PI / 2; a.position.x = s * (0.71 + i * 0.05); g.add(a); }
    const trava = cil(0.034, 0.025, M.faixa); trava.rotation.z = Math.PI / 2; trava.position.x = s * (0.71 + kgLado * 0.05 - 0.01); g.add(trava);
  }
  return sombreia(g);
}
function halter(kg = 1) {
  const g = new THREE.Group(); const pega = cil(0.016, 0.14, M.aco); pega.rotation.z = Math.PI / 2; g.add(pega);
  for (const s of [-1, 1]) { const c = cil(0.055 + kg * 0.008, 0.05, M.borracha, 6); c.rotation.z = Math.PI / 2; c.position.x = s * 0.1; g.add(c); }
  return sombreia(g);
}
function banco(comp = 1.18, inclina = 0) { // banco reto: estofado, quadro de aço, pés com borracha
  const g = new THREE.Group();
  const est = new THREE.Mesh(new RoundedBoxGeometry(comp, 0.085, 0.29, 4, 0.03), M.estofado); est.position.y = 0.4; g.add(est);
  const base = new THREE.Mesh(new RoundedBoxGeometry(comp - 0.1, 0.03, 0.2, 2, 0.008), M.quadro); base.position.y = 0.345; g.add(base);
  for (const s of [-1, 1]) {
    const perna = new THREE.Mesh(new RoundedBoxGeometry(0.06, 0.34, 0.06, 2, 0.01), M.quadro); perna.position.set(s * (comp / 2 - 0.16), 0.17, 0); g.add(perna);
    const pe = new THREE.Mesh(new RoundedBoxGeometry(0.08, 0.05, 0.46, 2, 0.015), M.quadro); pe.position.set(s * (comp / 2 - 0.16), 0.025, 0); g.add(pe);
    for (const z of [-1, 1]) { const b = cil(0.022, 0.012, M.borracha, 16); b.position.set(s * (comp / 2 - 0.16), 0.006, z * 0.2); g.add(b); }
  }
  return sombreia(g);
}
function suportes(x, alt = 1.05) { // montantes com ganchos em J
  const g = new THREE.Group();
  for (const z of [-0.56, 0.56]) {
    const m = new THREE.Mesh(new RoundedBoxGeometry(0.06, alt, 0.06, 2, 0.01), M.quadro); m.position.set(x, alt / 2, z); g.add(m);
    const gancho = new THREE.Mesh(new RoundedBoxGeometry(0.1, 0.05, 0.065, 2, 0.012), M.aco); gancho.position.set(x + 0.04, alt - 0.13, z); g.add(gancho);
    const base = new THREE.Mesh(new RoundedBoxGeometry(0.42, 0.04, 0.08, 2, 0.01), M.quadro); base.position.set(x, 0.02, z); g.add(base);
  }
  return sombreia(g);
}

// ---------- pose ----------
const _m0 = new THREE.Matrix4(), _m1 = new THREE.Matrix4(), _q = new THREE.Quaternion(), _qp = new THREE.Quaternion();
function zera() { ossos.forEach((b) => b.quaternion.identity()); B.pelvis.position.copy(POS_PELVIS); }
function corpoEm(pos, cabeca, frente) { // pelvis no mundo: onde fica e pra onde apontam cabeça e peito
  const y = cabeca.clone().normalize(), z = frente.clone().sub(y.clone().multiplyScalar(frente.dot(y))).normalize(), x = y.clone().cross(z);
  B.pelvis.quaternion.setFromRotationMatrix(_m0.makeBasis(x, y, z));
  B.pelvis.position.copy(pos).sub(CAB.Root);
}
function gira(nome, eixo, ang) { B[nome].quaternion.multiply(_q.setFromAxisAngle(eixo, ang)); }
const EX = V3(1, 0, 0), EY = V3(0, 1, 0), EZ = V3(0, 0, 1);
function base3(d, h) { const hh = h.clone().sub(d.clone().multiplyScalar(h.dot(d))).normalize(); return _m1.makeBasis(d, hh, d.clone().cross(hh)).clone(); }
function mira(nome, dir, dobradica, dobradica0, torcao = 0) { // gira o osso pra apontar dir com a dobradiça certa
  const b = B[nome], R0 = base3(DIR[nome], dobradica0), R1 = base3(dir.clone().normalize(), dobradica);
  const qw = new THREE.Quaternion().setFromRotationMatrix(R1.multiply(R0.transpose()));
  if (torcao) qw.premultiply(_q.setFromAxisAngle(dir.clone().normalize(), torcao));
  b.parent.getWorldQuaternion(_qp);
  b.quaternion.copy(_qp.invert().multiply(qw));
  b.updateMatrixWorld(true);
}
const ondeEsta = (nome) => B[nome].getWorldPosition(V3());
function ik(S, H, l1, l2, polo) {
  const v = H.clone().sub(S), d = Math.min(v.length(), l1 + l2 - 0.002), n = v.normalize();
  const a = (l1 * l1 - l2 * l2 + d * d) / (2 * d), h = Math.sqrt(Math.max(0, l1 * l1 - a * a));
  const P = polo.clone().sub(n.clone().multiplyScalar(polo.dot(n))).normalize();
  return { E: S.clone().add(n.clone().multiplyScalar(a)).add(P.clone().multiplyScalar(h)), dob: P.clone().cross(n).normalize(), alvo: S.clone().add(n.clone().multiplyScalar(d)) };
}
const DOB0 = {};
for (const l of ["l", "r"]) {
  DOB0["braco_" + l] = DIR["upperarm_" + l].clone().cross(DIR["lowerarm_" + l]).normalize();
  DOB0["perna_" + l] = EX.clone();
}
function membro(l, sup, inf, alvo, polo, torcao = 0) {
  const S = ondeEsta(sup), r = ik(S, alvo, COMP[sup], COMP[inf], polo);
  const d0 = sup.startsWith("upper") ? DOB0["braco_" + l] : DOB0["perna_" + l];
  mira(sup, r.E.clone().sub(S), r.dob, d0);
  mira(inf, r.alvo.clone().sub(r.E), r.dob, d0, torcao);
  return r;
}
const braco = (l, alvo, polo, torcao) => membro(l, "upperarm_" + l, "lowerarm_" + l, alvo, polo, torcao);
const perna = (l, alvo, polo) => membro(l, "thigh_" + l, "calf_" + l, alvo, polo);
function pe(l, frenteW, inclina = null) { // pé apoiado: aponta pra frente com a mesma queda do repouso (sola no chão)
  const h = Math.hypot(DIR["foot_" + l].x, DIR["foot_" + l].z), dy = inclina === null ? DIR["foot_" + l].y : inclina;
  const f = V3(frenteW.x, 0, frenteW.z).normalize();
  const d = f.clone().multiplyScalar(h).add(V3(0, dy, 0)).normalize();
  mira("foot_" + l, d, d.clone().cross(EY).negate().normalize(), EX);
}
const DEDOS = ["index", "middle", "ring", "pinky"];
function fecha(l, k, polegar = 0.5) { // dedos fechando na pegada
  const f = DIR["middle_01_" + l], ip = CAB["index_01_" + l].clone().sub(CAB["pinky_01_" + l]);
  const palma = f.clone().cross(ip).normalize().multiplyScalar(l === "l" ? 1 : -1);
  const eixo = f.clone().cross(palma).normalize();
  for (const d of DEDOS) for (const s of ["01", "02", "03"]) gira(`${d}_${s}_${l}`, eixo, k * (s === "01" ? 1.15 : 1.35));
  for (const s of ["02", "03"]) gira(`thumb_${s}_${l}`, eixo, k * polegar);
}
function mao(l, dirW, palmaW) { // orienta a mão: dedos pra dirW, palma pra palmaW
  const f = DIR["hand_" + l], ip = CAB["index_01_" + l].clone().sub(CAB["pinky_01_" + l]);
  const palma0 = f.clone().cross(ip).normalize().multiplyScalar(l === "l" ? 1 : -1);
  mira("hand_" + l, dirW, palmaW, palma0);
}

// ---------- pegada de verdade: mão no eixo da barra, antebraço gira junto, dedos e polegar abraçam a barra ----------
const MAO0 = {};
for (const l of ["l", "r"]) {
  const sl = l === "l" ? 1 : -1;
  const f = DEDOS.reduce((a, d) => a.add(DIR[d + "_01_" + l]), V3()).normalize();
  const k = CAB["index_01_" + l].clone().sub(CAB["pinky_01_" + l]); k.sub(f.clone().multiplyScalar(k.dot(f))).normalize();
  const n = f.clone().cross(k).multiplyScalar(sl).normalize();
  const qInv = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(f, k, f.clone().cross(k))).invert();
  // dedos juntos (no repouso eles abrem em leque): cada um aponta quase pro mesmo lado, leque pequeno
  const alinha = {};
  const leque = { index: 0.035, middle: 0, ring: -0.025, pinky: -0.06 };
  for (const d of DEDOS) {
    const d0 = DIR[d + "_01_" + l];
    const alvo = f.clone().add(k.clone().multiplyScalar(leque[d])).add(n.clone().multiplyScalar(d0.dot(n))).normalize();
    alinha[d] = new THREE.Quaternion().setFromUnitVectors(d0, alvo);
  }
  MAO0[l] = { f, k, n, qInv, alinha };
}
const G0 = (l, R) => { const m = MAO0[l]; return CAB["middle_01_" + l].clone().sub(CAB["hand_" + l]).add(m.n.clone().multiplyScalar(0.011 + R)).add(m.f.clone().multiplyScalar(-0.006)); };
const _qa = new THREE.Quaternion(), _qw = new THREE.Quaternion();
function giraMundo(nome, eixo, ang) {
  const b = B[nome]; b.getWorldQuaternion(_qw); _qw.premultiply(_qa.setFromAxisAngle(eixo, ang));
  b.parent.getWorldQuaternion(_qp); b.quaternion.copy(_qp.invert().multiply(_qw)); b.updateMatrixWorld(true);
}
const dirMundo = (nome) => DIR[nome].clone().applyQuaternion(B[nome].getWorldQuaternion(new THREE.Quaternion()));
function enrola(nome, O, ax, Rw, min, max) { // dobra o osso em torno de ax até a ponta encostar no cilindro (centro O, raio Rw)
  const p = ondeEsta(nome).sub(O); p.sub(ax.clone().multiplyScalar(p.dot(ax)));
  const d = dirMundo(nome); d.sub(ax.clone().multiplyScalar(d.dot(ax)));
  const L = COMP[nome] * d.length(); if (L < 1e-4) return; d.normalize();
  const e = ax.clone().cross(d), a = p.dot(d), b = p.dot(e), m = Math.hypot(a, b), c = (Rw * Rw - p.lengthSq() - L * L) / (2 * L);
  let th = c < -m ? Math.atan2(b, a) + Math.PI : c > m ? 0 : Math.atan2(b, a) + Math.acos(c / m);
  th = Math.atan2(Math.sin(th), Math.cos(th));
  giraMundo(nome, ax, Math.max(min, Math.min(max, th)));
}
const FLEX = [[-0.15, 1.65], [-0.1, 1.9], [-0.1, 1.45]];
function agarra(l, { ponto = null, punho = null, eixo, palma, polo, R = 0.014, polegar = 1 }) {
  const sl = l === "l" ? 1 : -1, m0 = MAO0[l];
  const k = eixo.clone().normalize(), n = palma.clone().sub(k.clone().multiplyScalar(palma.dot(k))).normalize();
  const f = k.clone().cross(n).multiplyScalar(sl);
  const q = new THREE.Quaternion().setFromRotationMatrix(_m1.makeBasis(f, k, f.clone().cross(k))).multiply(m0.qInv);
  const g = G0(l, R).applyQuaternion(q);
  if (!punho) punho = ponto.clone().sub(g);
  // antebraço: a rotação da mão em volta do eixo do antebraço vai pro antebraço (pronação/supinação), o punho só dobra
  braco(l, punho, polo, 0);
  const qf = B["lowerarm_" + l].getWorldQuaternion(new THREE.Quaternion());
  const rel = qf.clone().invert().multiply(q), a = DIR["lowerarm_" + l];
  const tw = 2 * Math.atan2(rel.x * a.x + rel.y * a.y + rel.z * a.z, rel.w);
  braco(l, punho, polo, Math.atan2(Math.sin(tw), Math.cos(tw)) * 0.9);
  B["lowerarm_" + l].getWorldQuaternion(_qp);
  B["hand_" + l].quaternion.copy(_qp.invert().multiply(q));
  for (const d of DEDOS) { B[d + "_01_" + l].quaternion.copy(m0.alinha[d]); B[d + "_02_" + l].quaternion.identity(); B[d + "_03_" + l].quaternion.identity(); }
  B["hand_" + l].updateMatrixWorld(true);
  const O = ondeEsta("hand_" + l).add(g), Rw = R + 0.0085, axD = f.clone().cross(n).normalize();
  for (const d of DEDOS) ["01", "02", "03"].forEach((sg, i) => enrola(`${d}_${sg}_${l}`, O, axD, Rw, ...FLEX[i]));
  // polegar: o metacarpo vai pro lado do punho da barra e as falanges fecham pelo outro sentido, por cima dos dedos
  if (polegar) {
    const ladoK = ondeEsta("index_01_" + l).sub(O).dot(k);
    const T1 = O.clone().add(f.clone().multiplyScalar(-(Rw + 0.006))).add(n.clone().multiplyScalar(-0.006)).add(k.clone().multiplyScalar(ladoK + 0.006));
    const P1 = ondeEsta("thumb_01_" + l), dAtual = dirMundo("thumb_01_" + l), dAlvo = T1.sub(P1).normalize();
    const b = B["thumb_01_" + l]; b.getWorldQuaternion(_qw); _qw.premultiply(_qa.setFromUnitVectors(dAtual, dAlvo));
    b.parent.getWorldQuaternion(_qp); b.quaternion.copy(_qp.invert().multiply(_qw)); b.updateMatrixWorld(true);
    enrola("thumb_02_" + l, O, axD.clone().negate(), Rw, -0.2, 1.4);
    enrola("thumb_03_" + l, O, axD.clone().negate(), Rw, -0.2, 1.2);
  }
  return O;
}

// ---------- tempo da série: segura em cima, desce 2 s, pausa, sobe 1 s ----------
const RITMO = { topo: 0.7, desce: 2.0, pausa: 0.35, sobe: 1.0 };
const CICLO = RITMO.topo + RITMO.desce + RITMO.pausa + RITMO.sobe;
const sen = (x) => 0.5 - 0.5 * Math.cos(Math.PI * x);
const sobeCurva = (x) => { const a = Math.min(1, x); return a < 0.5 ? 4 * a * a * a : 1 - Math.pow(-2 * a + 2, 3) / 2; };
function fase(s) {
  let u = s % CICLO;
  if (u < RITMO.topo) return { t: 0, f: "trava em cima", esforco: 0.25 };
  u -= RITMO.topo;
  if (u < RITMO.desce) return { t: sen(u / RITMO.desce), f: "desce em 2 s", esforco: 0.45 + 0.25 * (u / RITMO.desce) };
  u -= RITMO.desce;
  if (u < RITMO.pausa) return { t: 1, f: "pausa", esforco: 0.75 };
  u -= RITMO.pausa;
  return { t: 1 - sobeCurva(u / RITMO.sobe), f: "sobe forte", esforco: 1 };
}

// ---------- moldes ----------
const lerp = (a, b, k) => a + (b - a) * k;
const MOLDES = {
  supino: {
    nome: "Supino reto com barra",
    musc: { peitoral: 1, triceps: 0.75, deltoide: 0.6 },
    dica: "Escápulas encaixadas, pés firmes no chão. A barra desce na linha do mamilo com o cotovelo a uns 45° do tronco e sobe levemente em direção aos ombros.",
    cam: { alvo: V3(0.02, 0.6, 0), dist: 4.6, yaw: 52, pitch: 26 },
    cena(g) {
      const p = this.p, a = (p.inclina || 0) * Math.PI / 180;
      if (!a) { g.add(banco()); if (!p.halter) g.add(suportes(-0.62)); }
      else { // banco inclinado: assento + encosto alinhado com as costas
        const ban = new THREE.Group();
        const assento = new THREE.Mesh(new RoundedBoxGeometry(0.42, 0.085, 0.29, 4, 0.03), M.estofado); assento.position.set(0.2, 0.4, 0); ban.add(assento);
        const cab = V3(-Math.cos(a), Math.sin(a), 0), fr = V3(Math.sin(a), Math.cos(a), 0);
        const centro = V3(0.16, 0.565, 0).add(fr.clone().multiplyScalar(-0.165)).add(cab.clone().multiplyScalar(0.36));
        const encosto = new THREE.Mesh(new RoundedBoxGeometry(0.88, 0.085, 0.29, 4, 0.03), M.estofado); encosto.position.copy(centro); encosto.rotation.z = -a; ban.add(encosto);
        const trilho = new THREE.Mesh(new RoundedBoxGeometry(0.06, 0.06, 0.06, 2, 0.01), M.quadro);
        const p1 = V3(0.2, 0.34, 0), p2 = centro.clone().add(fr.clone().multiplyScalar(-0.07)).add(cab.clone().multiplyScalar(0.25));
        trilho.scale.set(1, 1, 1); trilho.position.copy(p1.clone().lerp(p2, 0.5)); trilho.lookAt(p2); trilho.scale.z = p1.distanceTo(p2) / 0.06; ban.add(trilho);
        for (const x of [0.32, -0.4]) { const pe2 = new THREE.Mesh(new RoundedBoxGeometry(0.08, 0.05, 0.46, 2, 0.015), M.quadro); pe2.position.set(x, 0.025, 0); ban.add(pe2);
          const perna2 = new THREE.Mesh(new RoundedBoxGeometry(0.06, x > 0 ? 0.34 : 0.62, 0.06, 2, 0.01), M.quadro); perna2.position.set(x, x > 0 ? 0.17 : 0.31, 0); ban.add(perna2); }
        g.add(sombreia(ban));
        if (!p.halter) g.add(suportes(-0.5, 1.32));
      }
      if (p.halter) { this.h = [halter(0.8), halter(0.8)]; g.add(...this.h); this.bar = null; }
      else { this.bar = barra(1); g.add(this.bar); }
    },
    pose(t) {
      zera();
      const p = this.p, a = (p.inclina || 0) * Math.PI / 180;
      const cab = V3(-Math.cos(a), Math.sin(a), 0), fr = V3(Math.sin(a), Math.cos(a), 0), pes = cab.clone().negate();
      corpoEm(V3(0.16, 0.565, 0), cab, fr);
      gira("spine_02", EX, -0.07); gira("spine_03", EX, -0.06); gira("neck_01", EX, 0.12 - a * 0.2); gira("head", EX, 0.04);
      for (const l of ["l", "r"]) gira("clavicle_" + l, EZ, (l === "l" ? -1 : 1) * 0.04 * t);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { // pés no chão, joelho ~90°
        const s = l === "l" ? -1 : 1;
        perna(l, V3(0.6 - a * 0.25, ALT_TORN, s * 0.31), V3(0.3, 1, s * 0.22));
        pe(l, V3(1, 0, s * 0.25));
      }
      // trajetória em J: embaixo na linha do mamilo (no inclinado, parte de cima do peito), em cima sobre o ombro
      const ombro = ondeEsta("upperarm_l").add(ondeEsta("upperarm_r")).multiplyScalar(0.5);
      const alcance = COMP.upperarm_l + COMP.lowerarm_l;
      const topo = ombro.clone().add(V3(0, alcance * 0.97 + 0.035, 0)).add(pes.clone().multiplyScalar(0.035));
      const baixo = ombro.clone().add(fr.clone().multiplyScalar(p.halter ? 0.14 : 0.085)).add(pes.clone().multiplyScalar((a ? 0.11 : 0.165) + (p.halter ? 0.02 : 0) + (p.fechada ? 0.09 : 0) + (p.neutra ? 0.03 : 0)));
      const d = baixo.clone().sub(topo), curva = Math.sin(t * Math.PI / 2);
      const pos = topo.clone().add(V3(0, d.y * t, 0)).add(V3(d.x, 0, d.z).multiplyScalar(curva));
      if (this.bar) { this.bar.position.copy(pos); this.bar.rotation.y = Math.PI / 2; }
      ["l", "r"].forEach((l, i) => {
        const s = l === "l" ? -1 : 1;
        const larg = p.halter ? lerp(p.neutra ? 0.15 : 0.17, p.neutra ? 0.22 : 0.3, t) : (p.fechada ? 0.2 : 0.41);
        agarra(l, { ponto: pos.clone().add(V3(0, 0, s * larg)), R: this.h ? 0.016 : 0.014,
          eixo: p.neutra ? cab.clone() : V3(0, 0, -s),
          palma: p.neutra ? V3(0, 0, -s).add(pes.clone().multiplyScalar(0.3)) : pes.clone().multiplyScalar(0.8).add(fr.clone().multiplyScalar(0.55)),
          polo: p.fechada || p.neutra ? V3(1, -0.45, s * 0.3) : V3(0.55, -0.55, s * 0.75) });
        if (this.h) seguraHalter(this.h[i], l);
      });
    },
  },
};


// ---------- em pé ----------
corpo.geometry.computeBoundingBox();
const CHAO_Y = corpo.geometry.boundingBox.min.y, ALT_TORN = CAB.foot_l.y - CHAO_Y, ALT_QUADRIL = CAB.pelvis.y - CHAO_Y;
const girarY = (v, a) => v.clone().applyAxisAngle(EY, a);
function emPe(quadril, frente, incl) { // tronco inclinado incl rad pra frente a partir do quadril
  const f = frente.clone().normalize();
  corpoEm(quadril, EY.clone().multiplyScalar(Math.cos(incl)).add(f.clone().multiplyScalar(Math.sin(incl))),
    f.clone().multiplyScalar(Math.cos(incl)).sub(EY.clone().multiplyScalar(Math.sin(incl))));
}
function esquerda(f) { return EY.clone().cross(f).normalize(); }
function pernas(f, { abre = 0.14, fora = 0.3, recuo = 0, poloFora = 0.35, origem = V3() } = {}) {
  const E = esquerda(f);
  for (const l of ["l", "r"]) {
    const s = l === "l" ? 1 : -1, ponta = girarY(f, s * fora);
    const tornozelo = origem.clone().add(E.clone().multiplyScalar(s * abre)).add(f.clone().multiplyScalar(-0.05 - recuo)).setY(ALT_TORN);
    perna(l, tornozelo, f.clone().add(E.clone().multiplyScalar(s * poloFora)).add(V3(0, 0.15, 0)));
    pe(l, ponta);
  }
}
function quadroDe(nome) { const q = B[nome].getWorldQuaternion(new THREE.Quaternion()); return { up: EY.clone().applyQuaternion(q), fr: EZ.clone().applyQuaternion(q), esq: EX.clone().applyQuaternion(q) }; }
function pegada(l, R = 0.014) { // centro da pegada (onde a barra/halter passa na mão)
  return ondeEsta("hand_" + l).add(G0(l, R).applyQuaternion(B["hand_" + l].getWorldQuaternion(new THREE.Quaternion())));
}
function seguraHalter(h, l, R = 0.016) { // halter na mão: cabo no eixo dos nós dos dedos
  const q = B["hand_" + l].getWorldQuaternion(new THREE.Quaternion());
  h.position.copy(pegada(l, R));
  // segue a rotação inteira da mão (só alinhar o cabo deixava o giro em volta dele indefinido: o halter dava um salto)
  h.quaternion.copy(q).multiply(MAO0[l].qH || (MAO0[l].qH = new THREE.Quaternion().setFromUnitVectors(EX, MAO0[l].k)));
}
function barraCurta(r = 0.15, comp = 1.2) {
  const g = new THREE.Group();
  const haste = cil(0.0135, comp, M.cromo); haste.rotation.z = Math.PI / 2; g.add(haste);
  for (const s of [-1, 1]) {
    const a = anilha(r, 0.032); a.rotation.z = Math.PI / 2; a.position.x = s * (comp / 2 - 0.08); g.add(a);
    const t = cil(0.03, 0.02, M.faixa); t.rotation.z = Math.PI / 2; t.position.x = s * (comp / 2 - 0.055); g.add(t);
  }
  return sombreia(g);
}
function tablado() { // plataforma: madeira no meio, borracha nas laterais
  const g = new THREE.Group();
  const madeira = new THREE.Mesh(new RoundedBoxGeometry(1.0, 0.03, 2.4, 2, 0.006), new THREE.MeshStandardMaterial({ color: 0x5b4632, roughness: 0.62 }));
  madeira.position.y = -0.015; g.add(madeira);
  for (const s of [-1, 1]) { const b = new THREE.Mesh(new RoundedBoxGeometry(0.7, 0.03, 2.4, 2, 0.006), M.borracha); b.position.set(s * 0.85, -0.015, 0); g.add(b); }
  g.traverse((m) => { if (m.isMesh) m.receiveShadow = true; });
  return g;
}
const F0 = V3(1, 0, 0); // em pé, de frente pra +X

Object.assign(MOLDES, {
  crucifixo: {
    nome: "Crucifixo reto com halteres",
    musc: { peitoral: 1, deltoide: 0.6, biceps: 0.35 },
    dica: "Cotovelo levemente dobrado e travado do começo ao fim: quem se mexe é o ombro. Abre os braços em arco até sentir o peito alongar, com o halter na linha do peito, e fecha como quem abraça uma árvore.",
    cam: { alvo: V3(0.02, 0.62, 0), dist: 4.4, yaw: 58, pitch: 30 },
    cena(g) { this.p = { ...this.p, halter: true }; MOLDES.supino.cena.call(this, g); },
    pose(t) {
      zera();
      const p = this.p, a = (p.inclina || 0) * Math.PI / 180;
      const cab = V3(-Math.cos(a), Math.sin(a), 0), fr = V3(Math.sin(a), Math.cos(a), 0), pes = cab.clone().negate();
      corpoEm(V3(0.16, 0.565, 0), cab, fr);
      gira("spine_02", EX, -0.07); gira("spine_03", EX, -0.06); gira("neck_01", EX, 0.12 - a * 0.2); gira("head", EX, 0.04);
      // escápula: encaixada embaixo (abre o peito), um pouco pra frente em cima
      for (const l of ["l", "r"]) gira("clavicle_" + l, EZ, (l === "l" ? -1 : 1) * (0.05 * t - 0.03 * (1 - t)));
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) {
        const s = l === "l" ? -1 : 1;
        perna(l, V3(0.6 - a * 0.25, ALT_TORN, s * 0.31), V3(0.3, 1, s * 0.22));
        pe(l, V3(1, 0, s * 0.25));
      }
      const R = (COMP.upperarm_l + COMP.lowerarm_l) * 0.9; // cotovelo ~150°, o mesmo o tempo todo
      const fi = (-0.16 + 1.5 * t); // ângulo a partir da vertical: em cima os halteres quase se tocam, embaixo o braço passa da linha do tronco
      ["l", "r"].forEach((l, i) => {
        const s = l === "l" ? -1 : 1, O = ondeEsta("upperarm_" + l), lado = V3(0, 0, s);
        const dir = fr.clone().multiplyScalar(Math.cos(fi)).add(lado.clone().multiplyScalar(Math.sin(fi))).add(pes.clone().multiplyScalar(0.12)).normalize();
        const palma = lado.clone().multiplyScalar(-Math.cos(fi * 0.85)).add(fr.clone().multiplyScalar(Math.sin(fi * 0.85))); // de frente pro outro halter -> pro teto
        agarra(l, { punho: O.clone().add(dir.multiplyScalar(R)), R: 0.016, eixo: cab.clone(), palma,
          polo: lado.clone().multiplyScalar(1).add(fr.clone().multiplyScalar(-0.35)).add(pes.clone().multiplyScalar(0.25)) });
        seguraHalter(this.h[i], l);
      });
    },
  },
  agachamento: {
    nome: "Agachamento livre com barra",
    musc: { quadriceps: 1, gluteo: 0.9, adutor: 0.5, lombar: 0.45, posterior: 0.35 },
    dica: "Barra apoiada no trapézio, pés na largura dos ombros com a ponta um pouco pra fora. Desce sentando pra trás até a coxa passar da paralela, joelho seguindo a linha do pé.",
    cam: { alvo: V3(0, 0.9, 0), dist: 4.4, yaw: 16, pitch: 14 },
    cena(g) { g.add(tablado()); this.bar = barra(2); g.add(this.bar); },
    pose(t) {
      zera();
      const k = t, sumo = this.p.sumo, alt = ALT_QUADRIL - 0.03 - k * (ALT_QUADRIL - (sumo ? 0.5 : 0.46)), recuo = 0.04 + k * (sumo ? 0.14 : 0.24), incl = 0.08 + k * (sumo ? 0.4 : 0.62);
      emPe(V3(-recuo, alt, 0), F0, incl * 0.55);
      gira("spine_01", EX, incl * 0.12); gira("spine_02", EX, incl * 0.12); gira("spine_03", EX, incl * 0.08);
      gira("neck_01", EX, -incl * 0.45); gira("head", EX, -incl * 0.15);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, sumo ? { abre: 0.31, fora: 0.75, poloFora: 1.0 } : { abre: 0.17, fora: 0.42, poloFora: 0.55 });
      const c = quadroDe("spine_03"), pescoco = ondeEsta("neck_01");
      const bar = pescoco.clone().add(c.fr.clone().multiplyScalar(-0.1)).add(c.up.clone().multiplyScalar(-0.085));
      this.bar.position.copy(bar); this.bar.quaternion.setFromUnitVectors(EX, c.esq);
      for (const l of ["l", "r"]) {
        const s = l === "l" ? 1 : -1;
        agarra(l, { ponto: bar.clone().add(c.esq.clone().multiplyScalar(s * 0.36)), eixo: c.esq.clone().multiplyScalar(-s),
          palma: c.up.clone().add(c.fr.clone().multiplyScalar(0.9)),
          polo: c.up.clone().multiplyScalar(-1).add(c.fr.clone().multiplyScalar(-0.6)).add(c.esq.clone().multiplyScalar(s * 0.3)) });
      }
    },
  },
  terra: {
    nome: "Levantamento terra",
    musc: { gluteo: 1, posterior: 0.9, lombar: 0.85, quadriceps: 0.55, trapezio: 0.5, dorsal: 0.45, antebraco: 0.5 },
    dica: "Barra colada na canela, sobre o meio do pé. Coluna neutra, empurra o chão com os pés e estende quadril e joelho juntos, a barra subindo rente às pernas.",
    cam: { alvo: V3(0, 0.72, 0), dist: 4.3, yaw: 18, pitch: 13 },
    cena(g) { g.add(tablado()); if (this.p.halter) { this.h = [halter(0.8), halter(0.8)]; g.add(...this.h); this.bar = null; } else { this.bar = barra(2); g.add(this.bar); } },
    pose(t) {
      zera();
      const k = t, ease = k * k * (3 - 2 * k), p = this.p;
      const rom = p.romeno, sumo = p.sumo;
      const desce = rom ? (p.stiff ? 0.035 : 0.1) : ALT_QUADRIL - (sumo ? 0.56 : 0.6);
      const alt = ALT_QUADRIL - 0.02 - ease * desce, recuo = 0.02 + ease * (rom ? 0.3 : sumo ? 0.2 : 0.32), incl = 0.02 + ease * (rom ? 1.3 : sumo ? 0.8 : 1.14);
      emPe(V3(-recuo, alt, 0), F0, incl * 0.7);
      gira("spine_02", EX, incl * 0.1); gira("spine_03", EX, incl * 0.08); gira("neck_01", EX, -incl * 0.5);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, sumo ? { abre: 0.33, fora: 0.72, poloFora: 0.95 } : { abre: 0.13, fora: 0.18, poloFora: 0.25 });
      const ombros = ondeEsta("upperarm_l").add(ondeEsta("upperarm_r")).multiplyScalar(0.5);
      const yMao = Math.max(p.halter ? 0.1 : 0.225, ombros.y - (COMP.upperarm_l + COMP.lowerarm_l) * 0.985 - 0.07);
      const bar = V3(p.halter ? 0.06 : 0.02, yMao, 0);
      if (this.bar) { this.bar.position.copy(bar); this.bar.rotation.set(0, Math.PI / 2, 0); }
      ["l", "r"].forEach((l, i) => {
        const s = l === "l" ? 1 : -1, E = esquerda(F0);
        agarra(l, { ponto: bar.clone().add(E.clone().multiplyScalar(s * (sumo ? 0.15 : p.halter ? 0.19 : 0.25))), R: p.halter ? 0.016 : 0.014,
          eixo: p.halter ? F0.clone() : E.clone().multiplyScalar(-s), palma: p.halter ? E.clone().multiplyScalar(-s) : F0.clone().multiplyScalar(-1),
          polo: F0.clone().multiplyScalar(-1).add(E.clone().multiplyScalar(s * 0.4)) });
        if (this.h) seguraHalter(this.h[i], l);
      });
    },
  },
  remada: {
    nome: "Remada curvada com barra",
    musc: { dorsal: 1, trapezio: 0.8, biceps: 0.6, deltoide: 0.35, lombar: 0.5, antebraco: 0.45 },
    dica: "Tronco a uns 45°, joelho levemente dobrado, coluna neutra. Puxa a barra até o umbigo levando o cotovelo pra trás e junta as escápulas no fim.",
    cam: { alvo: V3(0, 0.82, 0), dist: 4.3, yaw: 20, pitch: 13 },
    cena(g) { g.add(tablado()); if (this.p.halter) { this.h = [halter(0.8), halter(0.8)]; g.add(...this.h); this.bar = null; } else { this.bar = barra(1); g.add(this.bar); } },
    pose(t) {
      zera();
      const incl = 1.02;
      emPe(V3(-0.22, ALT_QUADRIL - 0.12, 0), F0, incl * 0.75);
      gira("spine_02", EX, incl * 0.1); gira("spine_03", EX, incl * 0.06); gira("neck_01", EX, -0.55);
      for (const l of ["l", "r"]) gira("clavicle_" + l, EY, (l === "l" ? 1 : -1) * 0.12 * (1 - t));
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.14, fora: 0.2, poloFora: 0.25 });
      const c = quadroDe("spine_03"), ombros = ondeEsta("upperarm_l").add(ondeEsta("upperarm_r")).multiplyScalar(0.5);
      const alcance = COMP.upperarm_l + COMP.lowerarm_l;
      const solto = ombros.clone().add(V3(0, -alcance * 0.97 - 0.06, 0));
      const umbigo = ondeEsta("spine_02").add(c.fr.clone().multiplyScalar(0.15));
      const kk = 1 - t, bar = solto.clone().lerp(umbigo, kk * kk * (3 - 2 * kk));
      if (this.bar) { this.bar.position.copy(bar); this.bar.rotation.set(0, Math.PI / 2, 0); }
      ["l", "r"].forEach((l, i) => {
        const s = l === "l" ? 1 : -1, E = esquerda(F0);
        agarra(l, { ponto: bar.clone().add(E.clone().multiplyScalar(s * (this.h ? 0.2 : 0.24))), R: this.h ? 0.016 : 0.014,
          eixo: this.h ? F0.clone() : E.clone().multiplyScalar(this.p.supinada ? s : -s),
          palma: this.h ? E.clone().multiplyScalar(-s) : F0.clone().multiplyScalar(this.p.supinada ? 1 : -1),
          polo: V3(-1, 0.7, s * (this.h ? 0.15 : 0.35)) });
        if (this.h) seguraHalter(this.h[i], l);
      });
    },
  },
  rosca: {
    nome: "Rosca direta com barra",
    musc: { biceps: 1, antebraco: 0.6, deltoide: 0.2 },
    dica: "Cotovelo colado no corpo e parado; só o antebraço se move. Sobe sem balançar o tronco e desce controlando, até quase esticar.",
    cam: { alvo: V3(0, 1.0, 0), dist: 3.8, yaw: 22, pitch: 12 },
    cena(g) { g.add(tablado()); if (this.p.halter) { this.h = [halter(0.4), halter(0.4)]; g.add(...this.h); this.bar = null; } else { this.bar = barraCurta(); g.add(this.bar); } },
    pose(t) {
      zera();
      emPe(V3(0, ALT_QUADRIL - 0.015, 0), F0, 0.02);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.13, fora: 0.2, poloFora: 0.2 });
      const ang = 0.18 + (1 - t) * 2.25, E = esquerda(F0);
      const pegas = {};
      for (const l of ["l", "r"]) {
        const s = l === "l" ? 1 : -1, S = ondeEsta("upperarm_" + l);
        const cot = S.clone().add(V3(0.015, -COMP.upperarm_l * 0.995, 0)).add(E.clone().multiplyScalar(-s * 0.01));
        const ante = V3(0, -Math.cos(ang), 0).add(F0.clone().multiplyScalar(Math.sin(ang))).add(E.clone().multiplyScalar(-s * (this.p.halter ? 0 : 0.06))).normalize();
        const pr = this.p, n = pr.martelo ? E.clone().multiplyScalar(-s) : ante.clone().cross(E).multiplyScalar(pr.inversa ? -1 : 1);
        const k = pr.martelo ? E.clone().cross(ante).negate() : E.clone().multiplyScalar(pr.inversa ? -s : s);
        pegas[l] = agarra(l, { punho: cot.clone().add(ante.clone().multiplyScalar(COMP.lowerarm_l)), eixo: k, palma: n, R: this.h ? 0.016 : 0.0135,
          polo: F0.clone().multiplyScalar(-1).add(V3(0, -0.2, 0)) });
        if (this.h) seguraHalter(this.h[l === "l" ? 0 : 1], l);
      }
      if (!this.bar) return;
      this.bar.position.copy(pegas.l).add(pegas.r).multiplyScalar(0.5);
      this.bar.quaternion.setFromUnitVectors(EX, pegas.l.clone().sub(pegas.r).normalize());
    },
  },
  elevacao: {
    nome: "Elevação lateral com halteres",
    deltoide: (p) => p.frontal ? "deltoide anterior" : "deltoide lateral",
    musc: { deltoide: 1, trapezio: 0.45 },
    dica: "Cotovelo levemente dobrado e fixo. Sobe os braços pelos lados até a linha do ombro, como se derramasse uma jarra, e desce devagar.",
    cam: { alvo: V3(0, 1.05, 0), dist: 3.9, yaw: 62, pitch: 14 },
    cena(g) { g.add(tablado()); if (this.p.barra) { this.bar = barraCurta(0.12, 1.1); g.add(this.bar); this.h = null; } else { this.h = [halter(0.6), halter(0.6)]; g.add(...this.h); this.bar = null; } },
    pose(t) {
      zera();
      emPe(V3(0, ALT_QUADRIL - 0.015, 0), F0, 0.06);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.13, fora: 0.2, poloFora: 0.2 });
      const ab = 0.22 + (1 - t) * 1.32, E = esquerda(F0), pegas = {};
      ["l", "r"].forEach((l, i) => {
        const s = l === "l" ? 1 : -1, S = ondeEsta("upperarm_" + l);
        const dir = this.p.frontal ? V3(0, -Math.cos(ab), 0).add(F0.clone().multiplyScalar(Math.sin(ab))).add(E.clone().multiplyScalar(s * (this.bar ? 0.02 : 0.14))).normalize()
          : V3(0, -Math.cos(ab), 0).add(E.clone().multiplyScalar(s * Math.sin(ab))).add(F0.clone().multiplyScalar(0.18)).normalize();
        const n = this.bar ? V3(0, -1, 0) : V3(0, -1, 0).add(E.clone().multiplyScalar(-s * 0.4)).normalize();
        pegas[l] = agarra(l, { punho: S.clone().add(dir.clone().multiplyScalar((COMP.upperarm_l + COMP.lowerarm_l) * 0.955)), palma: n, R: this.bar ? 0.0135 : 0.016,
          eixo: this.bar ? E.clone().multiplyScalar(-s) : n.clone().cross(dir).multiplyScalar(s), polo: V3(0, 0.25, 0).add(F0.clone().multiplyScalar(-1)) });
        if (this.h) seguraHalter(this.h[i], l);
      });
      if (this.bar) { this.bar.position.copy(pegas.l).add(pegas.r).multiplyScalar(0.5); this.bar.quaternion.setFromUnitVectors(EX, pegas.l.clone().sub(pegas.r).normalize()); }
    },
  },
  encolhimento: {
    nome: "Encolhimento com barra",
    musc: { trapezio: 1, antebraco: 0.5 },
    dica: "Braço esticado e solto, sem dobrar o cotovelo. Sobe os ombros em direção às orelhas, segura um instante lá em cima e desce até alongar.",
    cam: { alvo: V3(0, 1.1, 0), dist: 3.4, yaw: 28, pitch: 10 },
    cena(g) { g.add(tablado()); if (this.p.halter) { this.h = [halter(0.8), halter(0.8)]; g.add(...this.h); this.bar = null; } else { this.bar = barraCurta(0.2, 1.5); g.add(this.bar); this.h = null; } },
    pose(t) {
      zera();
      emPe(V3(0, ALT_QUADRIL - 0.015, 0), F0, 0.03);
      const sobe = 1 - t;
      for (const l of ["l", "r"]) gira("clavicle_" + l, EZ, (l === "l" ? 1 : -1) * ENC_SINAL * 0.44 * sobe);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.13, fora: 0.2, poloFora: 0.2 });
      const E = esquerda(F0), pegas = {}, reach = (COMP.upperarm_l + COMP.lowerarm_l) * 0.965;
      ["l", "r"].forEach((l, i) => {
        const s = l === "l" ? 1 : -1, S = ondeEsta("upperarm_" + l);
        const dir = this.h ? V3(0, -1, 0).add(E.clone().multiplyScalar(s * 0.05)).normalize() : V3(0, -1, 0).add(F0.clone().multiplyScalar(0.2)).add(E.clone().multiplyScalar(s * 0.02)).normalize();
        pegas[l] = agarra(l, { punho: S.clone().add(dir.multiplyScalar(reach)), R: this.h ? 0.016 : 0.0135,
          eixo: this.h ? F0.clone() : E.clone().multiplyScalar(-s), palma: this.h ? E.clone().multiplyScalar(-s) : F0.clone().multiplyScalar(-1),
          polo: F0.clone().multiplyScalar(-1).add(V3(0, 0.2, 0)) });
        if (this.h) seguraHalter(this.h[i], l);
      });
      if (this.bar) { this.bar.position.copy(pegas.l).add(pegas.r).multiplyScalar(0.5); this.bar.quaternion.setFromUnitVectors(EX, pegas.l.clone().sub(pegas.r).normalize()); }
    },
  },
  desenvolvimento: {
    nome: "Desenvolvimento com barra em pé",
    deltoide: () => "deltoides",
    musc: { deltoide: 1, triceps: 0.7, trapezio: 0.45, abdomen: 0.35 },
    dica: "Barra apoiada na frente do ombro, cotovelo um pouco à frente da barra. Empurra reto pra cima, passa a cabeça e trava em cima com a barra sobre o meio do pé. Glúteo e abdômen firmes, sem arquear a lombar.",
    cam: { alvo: V3(0, 1.22, 0), dist: 4.5, yaw: 30, pitch: 8 },
    cena(g) { g.add(tablado()); if (this.p.halter) { this.h = [halter(0.6), halter(0.6)]; g.add(...this.h); this.bar = null; } else { this.bar = barra(1); g.add(this.bar); this.h = null; } },
    pose(t) {
      zera();
      emPe(V3(0, ALT_QUADRIL - 0.015, 0), F0, -0.02);
      gira("neck_01", EX, -0.22 * Math.sin(Math.PI * Math.min(1, t * 1.3))); gira("head", EX, -0.08 * t); // cabeça sai do caminho da barra
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.14, fora: 0.22, poloFora: 0.25 });
      const E = esquerda(F0), ombro = ondeEsta("upperarm_l").add(ondeEsta("upperarm_r")).multiplyScalar(0.5), reach = COMP.upperarm_l + COMP.lowerarm_l;
      const baixo = ombro.clone().add(V3(0, this.h ? 0.08 : -0.01, 0)).add(F0.clone().multiplyScalar(this.h ? 0.02 : 0.15));
      const topo = ombro.clone().add(V3(0, reach * 0.96, 0)).add(F0.clone().multiplyScalar(-0.02));
      const kk = 1 - t, sk = kk * kk * (3 - 2 * kk), pos = baixo.clone().lerp(topo, sk).add(F0.clone().multiplyScalar(this.h ? 0 : 0.07 * Math.sin(Math.PI * sk)));
      if (this.bar) { this.bar.position.copy(pos); this.bar.rotation.set(0, Math.PI / 2, 0); }
      ["l", "r"].forEach((l, i) => {
        const s = l === "l" ? 1 : -1, larg = this.h ? lerp(0.16, 0.3, t) : 0.27;
        agarra(l, { ponto: pos.clone().add(E.clone().multiplyScalar(s * larg)), eixo: E.clone().multiplyScalar(-s), R: this.h ? 0.016 : 0.014,
          palma: F0.clone().add(V3(0, 0.45, 0)),
          polo: V3(0, -1, 0).add(F0.clone().multiplyScalar(this.h ? 0.2 : 0.75)).add(E.clone().multiplyScalar(s * (this.h ? 0.9 : 0.35))) });
        if (this.h) seguraHalter(this.h[i], l);
      });
    },
  },
  remadaAlta: {
    nome: "Remada alta com barra",
    deltoide: () => "deltoide lateral",
    musc: { deltoide: 1, trapezio: 0.85, biceps: 0.35, antebraco: 0.4 },
    dica: "Pegada um pouco mais fechada que os ombros. Puxa a barra rente ao corpo levando o cotovelo pra cima e pros lados, até a barra chegar perto do peito. Cotovelo sempre acima do punho.",
    cam: { alvo: V3(0, 1.1, 0), dist: 3.7, yaw: 34, pitch: 8 },
    cena(g) { g.add(tablado()); this.bar = barraCurta(0.15, 1.2); g.add(this.bar); },
    pose(t) {
      zera();
      emPe(V3(0, ALT_QUADRIL - 0.015, 0), F0, 0.03);
      for (const l of ["l", "r"]) gira("clavicle_" + l, EZ, (l === "l" ? 1 : -1) * ENC_SINAL * 0.12 * (1 - t));
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.13, fora: 0.2, poloFora: 0.2 });
      const E = esquerda(F0), ombro = ondeEsta("upperarm_l").add(ondeEsta("upperarm_r")).multiplyScalar(0.5), reach = COMP.upperarm_l + COMP.lowerarm_l;
      const solto = ombro.clone().add(V3(0, -reach * 0.95, 0)).add(F0.clone().multiplyScalar(0.11));
      const alto = ombro.clone().add(V3(0, -0.13, 0)).add(F0.clone().multiplyScalar(0.13));
      const kk = 1 - t, sk = kk * kk * (3 - 2 * kk), pos = solto.clone().lerp(alto, sk).add(F0.clone().multiplyScalar(0.06 * Math.sin(Math.PI * sk))), pegas = {};
      ["l", "r"].forEach((l) => {
        const s = l === "l" ? 1 : -1;
        pegas[l] = agarra(l, { ponto: pos.clone().add(E.clone().multiplyScalar(s * 0.12)), eixo: E.clone().multiplyScalar(-s), palma: F0.clone().multiplyScalar(-1), R: 0.0135,
          polo: E.clone().multiplyScalar(s).add(V3(0, 0.5, 0)).add(F0.clone().multiplyScalar(-0.15)) });
      });
      this.bar.position.copy(pegas.l).add(pegas.r).multiplyScalar(0.5); this.bar.quaternion.setFromUnitVectors(EX, pegas.l.clone().sub(pegas.r).normalize());
    },
  },
});
let ENC_SINAL = -1; // sentido da clavícula subindo (conferido na foto)

// ---------- partes do músculo (feixes origem -> inserção; corpo em repouso, lado esquerdo) ----------
// Pontos aproximados FORA da pele; cada um gruda no vértice mais próximo (e pega a normal dele).
// S(osso, t, ang, fora): ponto em volta do osso; ang 0 = frente, 90 = lado de fora, 180 = trás, -90 = lado de dentro.
const POS0 = corpo.geometry.attributes.position, NRM0 = corpo.geometry.attributes.normal;
const PELE_V = new Set(Array.from(corpo.geometry.index.array.slice(0, corpo.geometry.groups[0].count)));
const V_ESQ = []; for (let i = 0; i < POS0.count; i++) if (POS0.getX(i) > -0.002) V_ESQ.push(i);
function gruda(p, lista = V_ESQ) {
  let melhor = 0, dm = 9;
  for (const i of lista) { const d = (POS0.getX(i) - p.x) ** 2 + (POS0.getY(i) - p.y) ** 2 + (POS0.getZ(i) - p.z) ** 2; if (d < dm) { dm = d; melhor = i; } }
  return melhor;
}
const vPos = (i) => V3(POS0.getX(i), POS0.getY(i), POS0.getZ(i)), vNrm = (i) => V3(NRM0.getX(i), NRM0.getY(i), NRM0.getZ(i));
function S(n, t, ang, fora = 0.09) {
  const u = DIR[n], F = EZ.clone().sub(u.clone().multiplyScalar(u.z)).normalize();
  const L = EX.clone().sub(u.clone().multiplyScalar(u.x)).sub(F.clone().multiplyScalar(F.dot(EX))).normalize();
  const a = ang * Math.PI / 180;
  return CAB[n].clone().add(u.clone().multiplyScalar(t * COMP[n])).add(F.multiplyScalar(Math.cos(a) * fora)).add(L.multiplyScalar(Math.sin(a) * fora));
}
const P = (x, y, z) => V3(x, y, z);
const BR = "upperarm_l", AB = "lowerarm_l", CX = "thigh_l", PE = "calf_l";
// cada parte: nome, det, cad = feixes [[ponto, raio], ...], tend = fração final do último trecho que é tendão,
// ins = ponto pra onde as fibras convergem (padrão: fim do 1º feixe), fundo = raio de profundidade (m)
const PARTES = {
  peitoral_sup: { nome: "peitoral superior", det: "porção clavicular", tend: 0.22, fundo: 0.05, cad: [
    [[P(0.1, 0.67, 0.25), 0.014], [S(BR, 0.21, 12, 0.08), 0.01]], [[P(0.012, 0.66, 0.3), 0.014], [S(BR, 0.21, 12, 0.08), 0.01]], [[P(0.008, 0.625, 0.3), 0.014], [S(BR, 0.21, 12, 0.08), 0.01]]] },
  peitoral_med: { nome: "peitoral", det: "porção esternal, o meio do peito", tend: 0.2, fundo: 0.05, cad: [
    [[P(0.008, 0.625, 0.3), 0.014], [S(BR, 0.21, 12, 0.08), 0.01]], [[P(0.008, 0.57, 0.3), 0.014], [S(BR, 0.21, 12, 0.08), 0.01]], [[P(0.01, 0.515, 0.3), 0.014], [S(BR, 0.21, 12, 0.08), 0.01]]] },
  peitoral_inf: { nome: "peitoral inferior", det: "fibras de baixo", tend: 0.2, fundo: 0.05, cad: [
    [[P(0.01, 0.515, 0.3), 0.014], [S(BR, 0.21, 12, 0.08), 0.01]], [[P(0.035, 0.47, 0.3), 0.014], [S(BR, 0.21, 12, 0.08), 0.01]], [[P(0.1, 0.452, 0.3), 0.014], [S(BR, 0.21, 12, 0.08), 0.01]]] },
  deltoide_ant: { nome: "deltoide anterior", det: "frente do ombro", tend: 0.18, fundo: 0.04, cad: [
    [[P(0.15, 0.71, 0.2), 0.026], [S(BR, 0.17, 25), 0.032], [S(BR, 0.48, 75), 0.01]]] },
  deltoide_lat: { nome: "deltoide lateral", det: "lado do ombro", tend: 0.18, fundo: 0.04, cad: [
    [[P(0.24, 0.76, 0.02), 0.028], [S(BR, 0.16, 90), 0.036], [S(BR, 0.48, 80), 0.01]]] },
  deltoide_post: { nome: "deltoide posterior", det: "trás do ombro", tend: 0.18, fundo: 0.04, cad: [
    [[P(0.16, 0.71, -0.2), 0.024], [S(BR, 0.17, 150), 0.03], [S(BR, 0.48, 88), 0.01]]] },
  triceps_longa: { nome: "tríceps", det: "cabeça longa", tend: 0.5, fundo: 0.032, cad: [
    [[S(BR, 0.1, -150), 0.016], [S(BR, 0.42, -160), 0.028], [S(BR, 0.66, 180), 0.022], [S(BR, 1.0, 180), 0.016]]] },
  triceps_lateral: { nome: "tríceps", det: "cabeça lateral", tend: 0.5, fundo: 0.032, cad: [
    [[S(BR, 0.14, 115), 0.018], [S(BR, 0.4, 120), 0.026], [S(BR, 0.64, 150), 0.02], [S(BR, 1.0, 180), 0.016]]] },
  biceps: { nome: "bíceps", det: "as duas cabeças", tend: 0.35, fundo: 0.032, cad: [
    [[S(BR, 0.2, 15), 0.014], [S(BR, 0.55, 12), 0.022], [S(BR, 0.84, 0), 0.016], [S(BR, 1.02, 0), 0.008]],
    [[S(BR, 0.22, -25), 0.014], [S(BR, 0.55, -18), 0.022], [S(BR, 0.84, 0), 0.016], [S(BR, 1.02, 0), 0.008]]] },
  braquial: { nome: "braquial", det: "dos lados do bíceps, mais por fora", tend: 0.15, fundo: 0.03, cheio: false, cad: [
    [[S(BR, 0.5, 82), 0.012], [S(BR, 0.78, 68), 0.02], [S(BR, 0.96, 35), 0.012]],
    [[S(BR, 0.62, -78), 0.009], [S(BR, 0.84, -66), 0.013], [S(BR, 0.96, -35), 0.009]]] },
  braquiorradial: { nome: "braquiorradial", det: "começa no braço, topo do antebraço", tend: 0.92, fundo: 0.03, cad: [
    [[S(BR, 0.74, 95), 0.012], [S(AB, 0.18, 72), 0.022], [S(AB, 0.48, 62), 0.015], [S(AB, 0.97, 55), 0.006]]] },
  antebraco: { nome: "antebraço", det: "flexores, a pegada", tend: 0.3, fundo: 0.032, cad: [
    [[S(AB, 0.05, -60), 0.016], [S(AB, 0.4, -70), 0.026], [S(AB, 0.95, -60), 0.012]],
    [[S(AB, 0.05, -110), 0.016], [S(AB, 0.4, -120), 0.026], [S(AB, 0.95, -100), 0.012]]] },
  antebraco_ext: { nome: "extensores do punho", det: "costas do antebraço", tend: 0.35, fundo: 0.032, cad: [
    [[S(AB, 0.06, 105), 0.016], [S(AB, 0.4, 100), 0.024], [S(AB, 0.95, 92), 0.01]],
    [[S(AB, 0.06, 140), 0.014], [S(AB, 0.4, 145), 0.02], [S(AB, 0.95, 135), 0.009]]] },
  dorsal: { nome: "dorsal", det: "latíssimo, as asas das costas", tend: 0.12, fundo: 0.08, cad: [
    [[P(0.045, 0.5, -0.25), 0.022], [P(0.09, 0.53, -0.24), 0.028], [P(0.14, 0.57, -0.2), 0.03], [S(BR, 0.12, -110, 0.07), 0.014]],
    [[P(0.075, 0.38, -0.25), 0.026], [P(0.12, 0.45, -0.22), 0.036], [P(0.15, 0.55, -0.15), 0.03], [S(BR, 0.12, -110, 0.07), 0.014]],
    [[P(0.13, 0.29, -0.2), 0.024], [P(0.16, 0.42, -0.12), 0.034], [P(0.17, 0.54, -0.08), 0.026], [S(BR, 0.12, -110, 0.07), 0.014]]] },
  trapezio_sup: { nome: "trapézio superior", det: "entre o pescoço e o ombro", tend: 0.06, fundo: 0.07, cad: [
    [[P(0.012, 0.8, -0.15), 0.02], [P(0.08, 0.76, -0.15), 0.032], [P(0.19, 0.73, -0.06), 0.02]],
    [[P(0.005, 0.72, -0.25), 0.022], [P(0.09, 0.715, -0.2), 0.028], [P(0.18, 0.715, -0.12), 0.018]]] },
  trapezio_med: { nome: "trapézio médio", det: "entre as escápulas", tend: 0.1, fundo: 0.07, cad: [
    [[P(0.0, 0.735, -0.25), 0.024], [P(0.19, 0.715, -0.14), 0.02]], [[P(0.0, 0.7, -0.25), 0.026], [P(0.17, 0.695, -0.18), 0.02]], [[P(0.0, 0.64, -0.25), 0.03], [P(0.15, 0.675, -0.2), 0.02]],
    [[P(0.0, 0.57, -0.25), 0.03], [P(0.12, 0.655, -0.2), 0.018]], [[P(0.0, 0.47, -0.25), 0.022], [P(0.085, 0.635, -0.22), 0.014]]] },
  lombar: { nome: "lombar", det: "eretores da espinha", tend: 0.0, fundo: 0.05, ins: P(0.032, 1.4, -0.08), cad: [
    [[P(0.03, 0.16, -0.25), 0.018], [P(0.034, 0.3, -0.25), 0.024], [P(0.032, 0.48, -0.25), 0.018]]] },
  abdomen: { nome: "abdômen", det: "reto abdominal", tend: 0.0, fundo: 0.05, ins: P(0.045, 1.4, 0.15), cad: [
    [[P(0.035, 0.2, 0.3), 0.026], [P(0.045, 0.36, 0.3), 0.034], [P(0.055, 0.5, 0.3), 0.03]]],
    // intersecções tendíneas (o "tanquinho") + linha alba
    tendoes: [[[P(0.0, 0.42, 0.3), 0.005], [P(0.09, 0.425, 0.3), 0.005]], [[P(0.0, 0.355, 0.3), 0.005], [P(0.09, 0.36, 0.3), 0.005]],
      [[P(0.0, 0.29, 0.3), 0.005], [P(0.085, 0.29, 0.3), 0.005]], [[P(0.0, 0.18, 0.3), 0.005], [P(0.0, 0.5, 0.3), 0.005]]] },
  gluteo_max: { nome: "glúteo máximo", det: "o grosso do glúteo", tend: 0.1, fundo: 0.08, cad: [
    [[P(0.02, 0.15, -0.25), 0.035], [S(CX, 0.12, 120), 0.025]], [[P(0.05, 0.24, -0.25), 0.04], [S(CX, 0.12, 120), 0.025]],
    [[P(0.12, 0.26, -0.2), 0.035], [S(CX, 0.12, 120), 0.025]], [[P(0.035, 0.07, -0.25), 0.03], [S(CX, 0.2, 135), 0.022]]] },
  gluteo_med: { nome: "glúteo médio", det: "lado do quadril", tend: 0.15, fundo: 0.05, cad: [
    [[P(0.24, 0.28, -0.03), 0.04], [S(CX, 0.02, 90), 0.018]], [[P(0.2, 0.28, 0.07), 0.03], [S(CX, 0.02, 90), 0.018]]] },
  vasto_lateral: { nome: "quadríceps", det: "vasto lateral, fora da coxa", tend: 0.2, fundo: 0.05, cad: [
    [[S(CX, 0.12, 80), 0.022], [S(CX, 0.5, 65), 0.04], [S(CX, 0.84, 35), 0.018], [S(CX, 0.98, 8), 0.012]]] },
  vasto_medial: { nome: "quadríceps", det: "vasto medial, a gota do joelho", tend: 0.25, fundo: 0.05, cad: [
    [[S(CX, 0.6, -50), 0.014], [S(CX, 0.86, -45), 0.034], [S(CX, 1.03, -12), 0.012]]] },
  reto_femoral: { nome: "quadríceps", det: "reto femoral, meio da coxa", tend: 0.25, fundo: 0.05, cad: [
    [[S(CX, 0.06, 5), 0.018], [S(CX, 0.45, 5), 0.034], [S(CX, 0.86, 0), 0.02], [S(CX, 1.02, 0), 0.014]]] },
  isquio: { nome: "posterior de coxa", det: "isquiotibiais", tend: 0.25, fundo: 0.05, cad: [
    [[S(CX, 0.06, 175), 0.02], [S(CX, 0.5, 150), 0.03], [S(CX, 0.95, 135), 0.012]],
    [[S(CX, 0.06, -175), 0.02], [S(CX, 0.5, -155), 0.03], [S(CX, 0.95, -140), 0.012]]] },
  adutores: { nome: "adutores", det: "parte de dentro da coxa", tend: 0.1, fundo: 0.05, cad: [
    [[S(CX, 0.02, -60, 0.07), 0.025], [S(CX, 0.35, -85), 0.04], [S(CX, 0.72, -95), 0.014]]] },
  panturrilha: { nome: "panturrilha", det: "gastrocnêmio", tend: 0.0, fundo: 0.045, cad: [
    [[S(PE, 0.03, 145), 0.018], [S(PE, 0.28, 140), 0.03], [S(PE, 0.55, 180), 0.012]],
    [[S(PE, 0.03, -145), 0.018], [S(PE, 0.3, -140), 0.032], [S(PE, 0.55, 180), 0.012]]],
    tendoes: [[[S(PE, 0.5, 180), 0.012], [S(PE, 0.97, 180), 0.009]]] },
  // músculos de apoio (estabilizam ou ajudam pouco); traço mais fino, aparecem rosados
  serratil: { nome: "serrátil anterior", det: "as 'costelinhas' do lado do peito", tend: 0.0, fundo: 0.04, cheio: false, ins: P(0.16, 0.6, -0.06), cad: [
    [[P(0.125, 0.47, 0.25), 0.008], [P(0.165, 0.51, 0.0), 0.007]], [[P(0.13, 0.505, 0.25), 0.008], [P(0.17, 0.54, 0.0), 0.007]],
    [[P(0.135, 0.54, 0.25), 0.008], [P(0.175, 0.57, 0.0), 0.007]], [[P(0.15, 0.435, 0.2), 0.007], [P(0.17, 0.475, 0.0), 0.006]]] },
  obliquo: { nome: "oblíquo externo", det: "lado da barriga", tend: 0.0, fundo: 0.05, ins: P(0.04, 0.12, 0.2), cad: [
    [[P(0.17, 0.46, 0.0), 0.018], [P(0.17, 0.36, 0.02), 0.024], [P(0.165, 0.26, 0.02), 0.016]],
    [[P(0.135, 0.47, 0.2), 0.016], [P(0.13, 0.37, 0.2), 0.02], [P(0.115, 0.26, 0.2), 0.015]]] },
  infraespinal: { nome: "infraespinal e redondo", det: "manguito, em cima da escápula", tend: 0.15, fundo: 0.05, cad: [
    [[P(0.05, 0.63, -0.25), 0.018], [P(0.12, 0.64, -0.25), 0.024], [P(0.2, 0.67, -0.15), 0.012]],
    [[P(0.06, 0.56, -0.25), 0.018], [P(0.12, 0.6, -0.25), 0.022], [P(0.19, 0.645, -0.15), 0.012]]] },
  tibial: { nome: "tibial anterior", det: "frente da canela", tend: 0.35, fundo: 0.03, cad: [
    [[S(PE, 0.08, 35), 0.013], [S(PE, 0.38, 30), 0.016], [S(PE, 0.7, 12), 0.01], [S(PE, 0.98, -25), 0.006]]] },
  soleo: { nome: "sóleo", det: "por baixo da panturrilha", tend: 0.0, fundo: 0.04, cheio: false, cad: [
    [[S(PE, 0.3, 105), 0.011], [S(PE, 0.5, 110), 0.015], [S(PE, 0.7, 140), 0.009]],
    [[S(PE, 0.3, -105), 0.011], [S(PE, 0.5, -110), 0.015], [S(PE, 0.7, -140), 0.009]]] },
};
const OSSOS_ANCORA = ["spine_01", "spine_02", "spine_03", "pelvis", "neck_01", "clavicle", "upperarm", "lowerarm", "thigh", "calf"];
for (const [id, pa] of Object.entries(PARTES)) {
  pa.id = id; pa.seg = [];
  const gr = (pt) => { const i = gruda(pt); return { p: vPos(i), n: vNrm(i) }; };
  const poe = (a, b, ra, rb, tendao) => pa.seg.push({ a: a.p, b: b.p, ra: tendao ? -ra : ra, rb, n: a.n.clone().add(b.n).normalize() });
  const tri = (a, b, c, tendao, borda = 0) => { if (a.p.distanceTo(b.p) < 1e-4 || b.p.distanceTo(c.p) < 1e-4 || a.p.distanceTo(c.p) < 1e-4) return;
    pa.seg.push({ a: a.p, b: b.p, c: c.p, borda, ra: tendao ? -0.012 : 0.012, rb: 0.012, n: a.n.clone().add(b.n).add(c.n).normalize() }); };
  const linhas = [];
  const feixes = pa.cad.map((f) => f.map(([pt, r]) => ({ ...gr(pt), r: r * (pa.larg || 1.45) })));
  for (const f of feixes) { const ln = [f[0]]; linhas.push(ln);
    for (let k = 0; k < f.length - 1; k++) {
      const a = f[k], b = f[k + 1];
      if (k === f.length - 2 && pa.tend > 0) { // último trecho: carne e depois tendão
        const m = { p: a.p.clone().lerp(b.p, 1 - pa.tend), n: a.n.clone().lerp(b.n, 1 - pa.tend).normalize() }, rm = a.r + (b.r - a.r) * (1 - pa.tend);
        poe(a, m, a.r, rm, false); poe(m, b, rm * 0.55, b.r * 0.7, true); ln.push(m, b);
      } else { poe(a, b, a.r, b.r, false); ln.push(b); }
    } }
  if (pa.cheio !== false) for (let k = 0; k < linhas.length - 1; k++) { // faixa entre feixes vizinhos
    const A0 = linhas[k], A1 = linhas[k + 1]; if (A0.length !== A1.length) continue;
    const nj = A0.length - 1 - (pa.tend > 0 ? 1 : 0), ult = k + 1 === linhas.length - 1;
    for (let j = 0; j < nj; j++) { // lados: 1 = a-b, 2 = b-c, 4 = c-a
      tri(A0[j], A1[j], A1[j + 1], false, (j === 0 ? 1 : 0) | (ult ? 2 : 0));
      tri(A0[j], A1[j + 1], A0[j + 1], false, (j === nj - 1 ? 2 : 0) | (k === 0 ? 4 : 0)); } // tendão fica só no feixe, mais fino
  }
  for (const f of pa.tendoes || []) { const a = gr(f[0][0]), b = gr(f[1][0]); poe(a, b, f[0][1], f[1][1], true); }
  pa.I = pa.ins ? pa.ins.clone() : feixes[0][feixes[0].length - 1].p.clone();
  const orig = feixes.reduce((acc, f) => acc.add(f[0].p), V3()).multiplyScalar(1 / feixes.length);
  pa.X = pa.I.clone().sub(orig).normalize();
  const barriga = feixes[0][Math.floor((feixes[0].length - 1) / 2)].p.clone().lerp(feixes[0][Math.ceil((feixes[0].length - 1) / 2)].p, 0.5);
  pa.N = Math.min(90, pa.I.distanceTo(barriga) / 0.004); // ~4 mm entre fibras no meio do músculo
  const meio = feixes[0][Math.floor(feixes[0].length / 2)].p.clone().lerp(feixes[0][Math.max(0, Math.floor(feixes[0].length / 2) - 1)].p, 0.5);
  pa.vert = { l: gruda(meio), r: gruda(V3(-meio.x, meio.y, meio.z), [...Array(POS0.count).keys()].filter((i) => POS0.getX(i) < 0.002)) };
}
// ---------- corpo esculpido: cada músculo vira volume (barriga alta, borda baixa -> sulco entre vizinhos) ----------
// mesma distância do shader, no repouso, uma vez só; depois suaviza e refaz as normais
const T_ESC0 = performance.now();
(function esculpe() {
  const g = corpo.geometry, n = POS0.count, disp = new Float32Array(n), ss = (a, b, x) => { const k = Math.min(1, Math.max(0, (x - a) / (b - a))); return k * k * (3 - 2 * k); };
  const segs = [];
  for (const pa of Object.values(PARTES)) { if (pa.id === "soleo") continue;
    const amp = Math.min(0.024, pa.fundo * 0.42);
    for (const q of pa.seg) { const pts = q.c ? [q.a, q.b, q.c] : [q.a, q.b], ctr = pts.reduce((a, b) => a.add(b), V3()).multiplyScalar(1 / pts.length);
      const rad = Math.max(...pts.map((x) => x.distanceTo(ctr))) + Math.max(Math.abs(q.ra), q.rb) * 2 + pa.fundo;
      segs.push({ q, amp, ctr, r2: rad * rad, rd: pa.fundo }); } }
  const pt = V3(), nr = V3(), ab = V3(), d = V3(), tmp = V3();
  for (let i = 0; i < n; i++) {
    const x = POS0.getX(i); pt.set(Math.abs(x), POS0.getY(i), POS0.getZ(i)); nr.set(x < 0 ? -NRM0.getX(i) : NRM0.getX(i), NRM0.getY(i), NRM0.getZ(i));
    let best = 0;
    for (const sg of segs) {
      if (pt.distanceToSquared(sg.ctr) > sg.r2) continue;
      const q = sg.q, fac = Math.max(ss(-0.6, -0.15, nr.dot(q.n)), 0.05); let e, tt;
      ab.subVectors(q.b, q.a);
      if (q.c) { // triângulo: dentro = negativo (miolo), fora = distância até a borda
        const ac = V3().subVectors(q.c, q.a), nt = V3().crossVectors(ab, ac).normalize(), dn = tmp.subVectors(pt, q.a).dot(nt), qq = pt.clone().addScaledVector(nt, -dn);
        const P3 = [q.a, q.b, q.c]; let dentro = true, dmin = 9, db = 9;
        for (let k = 0; k < 3; k++) { const a0 = P3[k], a1 = P3[(k + 1) % 3], ed = V3().subVectors(a1, a0), qa = V3().subVectors(qq, a0);
          if (V3().crossVectors(ed, qa).dot(nt) < 0) dentro = false;
          const w = qa.clone().addScaledVector(ed, -Math.min(1, Math.max(0, qa.dot(ed) / ed.dot(ed)))).length();
          dmin = Math.min(dmin, w); if (q.borda & (1 << k)) db = Math.min(db, w); }
        const r = Math.abs(q.ra), zz = dn * dn / (sg.rd * sg.rd);
        e = dentro ? Math.sqrt(zz) - Math.min(db / r, 1) * 0.9 : Math.sqrt(dmin * dmin / (r * r) + zz); tt = 0.5;
      } else {
        tt = Math.min(1, Math.max(0, d.subVectors(pt, q.a).dot(ab) / Math.max(ab.dot(ab), 1e-6)));
        d.subVectors(pt, q.a).addScaledVector(ab, -tt); const dn = d.dot(q.n); d.addScaledVector(q.n, -dn);
        const r = Math.abs(q.ra) + (q.rb - Math.abs(q.ra)) * tt; e = Math.sqrt(d.lengthSq() / (r * r) + dn * dn / (sg.rd * sg.rd));
      }
      e /= fac; const ee = Math.max(e, 0);
      const v = q.ra < 0 ? sg.amp * 0.25 * ss(1.0, 0.4, ee) : sg.amp * (0.4 * ss(1.15, 0.55, ee) + 0.6 * Math.max(0, 1 - ee * ee) * Math.sin(Math.PI * (tt * 0.8 + 0.1)));
      if (v > best) best = v;
    }
    disp[i] = PELE_V.has(i) ? best : best * 0.55;
  }
  // suaviza (vizinhos pela malha; vértices na mesma posição andam juntos)
  const viz = [...Array(n)].map(() => []), idx = g.index.array;
  for (let k = 0; k < idx.length; k += 3) for (let m = 0; m < 3; m++) { const a = idx[k + m], b = idx[k + (m + 1) % 3]; viz[a].push(b); viz[b].push(a); }
  for (let it = 0; it < 2; it++) { const nv = disp.slice();
    for (let i = 0; i < n; i++) { const v = viz[i]; if (!v.length) continue; let sm = 0; for (const j of v) sm += disp[j]; nv[i] = disp[i] * 0.4 + 0.6 * sm / v.length; }
    disp.set(nv); }
  const pos2 = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) { pos2[i * 3] = POS0.getX(i) + NRM0.getX(i) * disp[i]; pos2[i * 3 + 1] = POS0.getY(i) + NRM0.getY(i) * disp[i]; pos2[i * 3 + 2] = POS0.getZ(i) + NRM0.getZ(i) * disp[i]; }
  const g2 = new THREE.BufferGeometry(); g2.setAttribute("position", new THREE.BufferAttribute(pos2, 3)); g2.setIndex(g.index); g2.computeVertexNormals();
  g.setAttribute("aEsc", new THREE.BufferAttribute(disp, 1)); g.setAttribute("aNrE", g2.attributes.normal);
})();
const T_ESC = performance.now() - T_ESC0;
// Intensidade relativa dentro de cada exercício (1 = quem mais trabalha), de EMG publicado — ver
// docs/prototipos/academia-3d/pesquisa-musculos.md (Saeterbakken 2011, Barnett 1995, Trebs 2010, Fenwick 2009,
// Escamilla 2002, Campos 2020...). Até 8 por exercício; o primeiro da lista é o da etiqueta.
const FOCOS = {
  supino: (p) => p.fechada ? [["triceps_lateral", 1], ["peitoral_med", 0.85], ["peitoral_sup", 0.8], ["deltoide_ant", 0.8], ["triceps_longa", 0.7], ["peitoral_inf", 0.7], ["serratil", 0.3], ["antebraco", 0.25]]
    : p.inclina ? [["peitoral_sup", 1], ["deltoide_ant", 0.9], ["peitoral_med", 0.75], ["triceps_lateral", p.halter ? 0.5 : 0.6], ["peitoral_inf", p.halter ? 0.45 : 0.5], ["triceps_longa", 0.4], ["serratil", 0.35], ...(p.halter ? [["biceps", 0.3]] : [])]
    : p.neutra ? [["peitoral_med", 1], ["peitoral_inf", 0.85], ["deltoide_ant", 0.8], ["peitoral_sup", 0.8], ["triceps_lateral", 0.65], ["triceps_longa", 0.45], ["biceps", 0.3], ["serratil", 0.3]]
    : p.halter ? [["peitoral_med", 1], ["peitoral_inf", 0.9], ["peitoral_sup", 0.8], ["deltoide_ant", 0.75], ["triceps_lateral", 0.5], ["triceps_longa", 0.35], ["biceps", 0.3], ["serratil", 0.3]]
    : [["peitoral_med", 1], ["peitoral_inf", 0.9], ["peitoral_sup", 0.8], ["deltoide_ant", 0.75], ["triceps_lateral", 0.65], ["triceps_longa", 0.45], ["serratil", 0.3], ["dorsal", 0.25]],
  crucifixo: (p) => p.inclina ? [["peitoral_sup", 1], ["peitoral_med", 0.8], ["deltoide_ant", 0.7], ["biceps", 0.35], ["peitoral_inf", 0.45], ["serratil", 0.25]]
    : [["peitoral_med", 1], ["peitoral_inf", 0.85], ["peitoral_sup", 0.8], ["deltoide_ant", 0.55], ["biceps", 0.35], ["serratil", 0.25]],
  agachamento: () => [["vasto_lateral", 1], ["vasto_medial", 1], ["gluteo_max", 0.75], ["adutores", 0.65], ["reto_femoral", 0.55], ["lombar", 0.55], ["gluteo_med", 0.35], ["isquio", 0.3]],
  terra: (p) => p.sumo ? [["vasto_lateral", 0.9], ["vasto_medial", 0.9], ["lombar", 0.9], ["gluteo_max", 0.85], ["adutores", 0.85], ["isquio", 0.65], ["gluteo_med", 0.4], ["antebraco", 0.4]]
    : p.romeno ? [["isquio", 1], ["gluteo_max", 0.75], ["lombar", 0.7], ["antebraco", 0.6], ["adutores", 0.55], ["trapezio_sup", 0.4]]
    : [["lombar", 1], ["gluteo_max", 0.85], ["isquio", 0.8], ["vasto_lateral", 0.75], ["vasto_medial", 0.7], ["antebraco", 0.7], ["adutores", 0.6], ["trapezio_sup", 0.6]],
  remada: (p) => p.supinada ? [["dorsal", 1], ["trapezio_med", 0.8], ["biceps", 0.7], ["deltoide_post", 0.65], ["braquial", 0.6], ["infraespinal", 0.6], ["lombar", 0.5]]
    : p.halter ? [["dorsal", 1], ["trapezio_med", 0.85], ["deltoide_post", 0.75], ["braquial", 0.6], ["braquiorradial", 0.55], ["biceps", 0.5], ["lombar", 0.5], ["infraespinal", 0.5]]
    : [["trapezio_med", 1], ["deltoide_post", 0.9], ["dorsal", 0.8], ["infraespinal", 0.7], ["braquiorradial", 0.6], ["braquial", 0.55], ["lombar", 0.55], ["biceps", 0.45]],
  rosca: (p) => p.martelo ? [["braquiorradial", 1], ["braquial", 0.9], ["biceps", 0.8], ["deltoide_ant", 0.3]]
    : p.inversa ? [["braquiorradial", 1], ["braquial", 0.9], ["biceps", 0.6], ["antebraco_ext", 0.45], ["deltoide_ant", 0.35]]
    : [["biceps", 1], ["braquial", 0.85], ["braquiorradial", 0.55], ["antebraco", 0.4], ["deltoide_ant", 0.25]],
  elevacao: (p) => p.frontal ? [["deltoide_ant", 1], ["peitoral_sup", 0.6], ["deltoide_lat", 0.5], ["serratil", 0.45], ["trapezio_sup", 0.45]]
    : [["deltoide_lat", 1], ["deltoide_post", 0.7], ["trapezio_sup", 0.6], ["deltoide_ant", 0.55], ["serratil", 0.4]],
  encolhimento: () => [["trapezio_sup", 1], ["antebraco", 0.6], ["trapezio_med", 0.4]],
  desenvolvimento: (p) => [["deltoide_ant", 1], ["deltoide_lat", 0.8], ["triceps_lateral", 0.7], ["trapezio_sup", 0.6], ["serratil", 0.55], ["triceps_longa", 0.45], ["deltoide_post", p.halter ? 0.45 : 0.35]],
  remadaAlta: () => [["deltoide_lat", 1], ["trapezio_sup", 0.9], ["deltoide_ant", 0.7], ["braquiorradial", 0.5], ["trapezio_med", 0.45], ["braquial", 0.45], ["biceps", 0.4]],
};
// câmera virada pro lado do músculo que trabalha (costas, glúteo: por trás de lado)
const VISTA = { remada: 232, terra: (p) => p.sumo ? null : 212, encolhimento: 238, rosca: 62 }; // 90 = de frente, 270 = de costas
const GRUPOS = ["peitoral", "deltoide", "triceps", "trapezio", "gluteo", "vasto"]; // partes do mesmo músculo: linha mais fraca
let focoAtual = [];
function poeFoco(lista) {
  focoAtual = lista.slice(0, NMUS).map(([id, k]) => ({ pa: PARTES[id], k }));
  let n = 0;
  focoAtual.forEach((f, j) => {
    FOCO.I[j].set(f.pa.I.x, f.pa.I.y, f.pa.I.z, f.pa.N); FOCO.X[j].set(f.pa.X.x, f.pa.X.y, f.pa.X.z, f.k);
    FOCO.G[j] = 1 + GRUPOS.indexOf(f.pa.id === "reto_femoral" ? "vasto" : f.pa.id.split("_")[0]);
    for (const g of f.pa.seg) {
      if (n >= NSEG) break;
      const o = (r) => (r * NSEG + n) * 4;
      SEGD.set([g.a.x, g.a.y, g.a.z, g.ra], o(0)); SEGD.set([g.b.x, g.b.y, g.b.z, g.rb], o(1)); SEGD.set([g.n.x, g.n.y, g.n.z, j + Math.min(0.99, f.pa.fundo)], o(2));
      SEGD.set(g.c ? [g.c.x, g.c.y, g.c.z, 1 + (g.borda || 0)] : [0, 0, 0, 0], o(3));
      n++;
    }
  });
  for (let j = 0; j < NMUS; j++) { FOCO.alvo[j] = focoAtual[j] ? focoAtual[j].k : 0; if (!focoAtual[j]) { FOCO.K[j] = 0; FOCO.X[j].w = 0; } }
  FOCO.nseg.value = n; SEGT.needsUpdate = true;
}
// etiqueta: ponto na parte principal (lado mais perto da câmera) + linha até a plaquinha
const etq = $("#etq"), guia = $("#guia"), _pt = V3();
const etqEst = { x: 0, y: 0, ok: false, lado: 0 };
function ancoraFoco() {
  const f = focoAtual[0]; if (!f) return null;
  let melhor = null, dm = 99;
  for (const l of ["l", "r"]) {
    const w = corpo.getVertexPosition(f.pa.vert[l], V3()).applyMatrix4(corpo.matrixWorld), d = w.distanceTo(camera.position);
    if (d < dm) { dm = d; melhor = w; }
  }
  return melhor;
}
function poeEtiqueta(forte) {
  if (!etq) return;
  const w = ancoraFoco(); if (!w) { etq.classList.remove("on"); guia.classList.remove("on"); return; }
  _pt.copy(w).project(camera);
  const W = palco.clientWidth, H = palco.clientHeight, x = (_pt.x * 0.5 + 0.5) * W, y = (-_pt.y * 0.5 + 0.5) * H;
  if (!W || !H || !Number.isFinite(x + y)) { etqEst.ok = false; return; } // palco recolhido
  if (!etqEst.ok) { etqEst.x = x; etqEst.y = y; etqEst.ok = true; }
  etqEst.x += (x - etqEst.x) * 0.35; etqEst.y += (y - etqEst.y) * 0.35;
  const lado = etqEst.x > W * 0.5 ? 0 : 1; // plaquinha do lado oposto ao ponto
  if (lado !== etqEst.lado) { etqEst.lado = lado; etq.classList.toggle("dir", lado === 1); }
  const r = etq.getBoundingClientRect(), pr = palco.getBoundingClientRect();
  const bx = lado === 1 ? r.left - pr.left : r.right - pr.left, by = r.top - pr.top + r.height / 2;
  guia.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const ln = guia.querySelector("path"), pt = guia.querySelector("circle"), halo = guia.querySelector(".halo");
  const mx = bx + (etqEst.x - bx) * 0.5;
  ln.setAttribute("d", `M${bx.toFixed(1)} ${by.toFixed(1)} C${mx.toFixed(1)} ${by.toFixed(1)} ${mx.toFixed(1)} ${etqEst.y.toFixed(1)} ${etqEst.x.toFixed(1)} ${etqEst.y.toFixed(1)}`);
  pt.setAttribute("cx", etqEst.x.toFixed(1)); pt.setAttribute("cy", etqEst.y.toFixed(1));
  halo.setAttribute("cx", etqEst.x.toFixed(1)); halo.setAttribute("cy", etqEst.y.toFixed(1));
  halo.style.opacity = (0.12 + 0.4 * forte).toFixed(2); halo.setAttribute("r", (5 + 5 * forte).toFixed(1));
  etq.classList.add("on"); guia.classList.add("on");
}

// ---------- montagem ----------
let tFixo = null, molde = null, equip = null, gira0 = 0, girando = false, lento = false, tocando = !reduz, relogio = 0, ultimo = performance.now(), repAnt = -1;
const NOME_M = { peitoral: "peitoral", deltoide: "deltoide anterior", biceps: "bíceps", triceps: "tríceps", antebraco: "antebraço", dorsal: "dorsal", trapezio: "trapézio", abdomen: "abdômen", lombar: "lombar", gluteo: "glúteo", quadriceps: "quadríceps", posterior: "posterior de coxa", panturrilha: "panturrilha", adutor: "adutores" };
function usa(id, nomeExibido, p = {}) {
  molde = MOLDES[id]; molde.id = id; molde.p = p; molde.musc0 = molde.musc0 || molde.musc; molde.musc = p.musc || molde.musc0;
  if (equip) cena.remove(equip);
  equip = new THREE.Group(); molde.cena(equip); cena.add(equip);
  $("#nome").textContent = nomeExibido || molde.nome;
  $("#dica").textContent = (p.dica || molde.dica);
  const foco = p.foco || (FOCOS[id] ? FOCOS[id](p) : []);
  poeFoco(foco); FOCO.K.fill(0); FOCO.esf.value = 0; etqEst.ok = false;
  const fp = focoAtual[0];
  if (etq && fp) { etq.querySelector("b").textContent = fp.pa.nome; etq.querySelector("span").textContent = fp.pa.det; }
  $("#chips").innerHTML = [...focoAtual].sort((a, b) => b.k - a.k).map((f, i) => `<span class="chip${i === 0 ? " m" : ""}" style="--forca:${f.k}" title="trabalha ${Math.round(f.k * 100)}% do principal"><i></i>${f.pa.nome}${i === 0 || f.pa.nome === "quadríceps" || f.pa.nome === "tríceps" ? ` <em>${f.pa.det.split(",")[0]}</em>` : ""}</span>`).join("")
    || Object.entries(molde.musc).map(([m, f]) => `<span class="chip${f >= 0.9 ? " m" : ""}">${m === "deltoide" && molde.deltoide ? molde.deltoide(p) : NOME_M[m]}</span>`).join("");
  musAlvo.fill(0); relogio = 0; repAnt = -1; gira0 = 0;
  chave.target.position.copy(molde.cam.alvo); chave.position.copy(molde.cam.alvo).add(V3(2.2, 3.6, 2.6));
  quadro(0);
}
let camExtra = null; // só pros testes: câmera livre
function poeCamera() {
  if (camExtra) { camera.position.copy(camExtra.de); camera.lookAt(camExtra.para); return; }
  const c = molde.cam, yaw = (((typeof VISTA[molde.id] === "function" ? VISTA[molde.id](molde.p) : VISTA[molde.id]) ?? c.yaw) + gira0) * Math.PI / 180, p = c.pitch * Math.PI / 180;
  camera.position.set(c.alvo.x + Math.sin(yaw) * Math.cos(p) * c.dist, c.alvo.y + Math.sin(p) * c.dist, c.alvo.z + Math.cos(yaw) * Math.cos(p) * c.dist);
  camera.lookAt(c.alvo);
}
const COR_PELE = new THREE.Color(0xc9a58c), COR_ATLAS = new THREE.Color(0xb3b0aa), SHEEN_PELE = new THREE.Color(0xffd9c2), SHEEN_ATLAS = new THREE.Color(0x9a9894);
function aplicaEstilo(dt) {
  const k = reduz || !dt ? 1 : Math.min(1, dt * 5);
  ESTILO.esc.value += (ESTILO.alvoEsc - ESTILO.esc.value) * k; ESTILO.atlas += (ESTILO.alvoAtlas - ESTILO.atlas) * k;
  pele.color.copy(COR_PELE).lerp(COR_ATLAS, ESTILO.atlas); pele.sheenColor.copy(SHEEN_PELE).lerp(SHEEN_ATLAS, ESTILO.atlas);
  pele.roughness = 0.55 + 0.1 * ESTILO.atlas;
  ESTILO.anim = Math.abs(ESTILO.alvoEsc - ESTILO.esc.value) + Math.abs(ESTILO.alvoAtlas - ESTILO.atlas) > 0.002;
}
function estilo(o) { if ("esculpido" in o) ESTILO.alvoEsc = o.esculpido ? 1 : 0; if ("atlas" in o) ESTILO.alvoAtlas = o.atlas ? 1 : 0; ESTILO.anim = true; if (reduz) quadro(0); }
function quadro(dt) {
  aplicaEstilo(dt);
  if (tocando) relogio += dt * (lento ? 0.4 : 1);
  if (girando) gira0 += dt * 9;
  const fz = tFixo !== null ? { t: tFixo, f: "foto", esforco: 1 } : reduz ? { t: 0.55, f: "meio do movimento", esforco: 0.8 } : molde.fase ? molde.fase(relogio) : fase(relogio);
  molde.pose(fz.t);
  // músculos: acendem no esforço, com transição suave
  musAlvo.fill(0);
  for (const [m, f] of Object.entries(molde.musc)) musAlvo[MUSC.indexOf(m)] = f * fz.esforco;
  for (let i = 0; i < 16; i++) musU[i] += (musAlvo[i] - musU[i]) * Math.min(1, dt * 6 || 1);
  const forte = 0.35 + 0.65 * fz.esforco, kk = Math.min(1, dt * 6 || 1);
  for (let i = 0; i < NMUS; i++) FOCO.K[i] += ((FOCO.alvo[i] > 0 ? 1 : 0) - FOCO.K[i]) * kk;
  FOCO.esf.value += (fz.esforco * fz.esforco - FOCO.esf.value) * Math.min(1, dt * 4 || 1);
  poeCamera();
  renderer.render(cena, camera);
  poeEtiqueta(FOCO.K[0] * forte);
  const rep = Math.floor(relogio / CICLO);
  if (rep !== repAnt) { repAnt = rep; $("#reps").textContent = Math.min(rep, 10); palco.dispatchEvent(new CustomEvent("rep", { detail: rep })); }
  $("#faseTxt").textContent = fz.f;
}
function tamanho() {
  const w = palco.clientWidth, h = palco.clientHeight;
  if (!w || !h) return;
  renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
}
new ResizeObserver(() => { tamanho(); quadro(0); }).observe(palco);
let visivel = true;
new IntersectionObserver((e) => { visivel = e[0].isIntersecting; }).observe(palco);
function laco(agora) {
  const dt = Math.min(0.05, (agora - ultimo) / 1000); ultimo = agora;
  if (visivel && !document.hidden && (tocando || girando || ESTILO.anim)) quadro(dt);
  requestAnimationFrame(laco);
}
// arrastar gira a câmera
let arrasto = null;
renderer.domElement.addEventListener("pointerdown", (e) => { arrasto = { x: e.clientX, g: gira0 }; });
addEventListener("pointermove", (e) => { if (arrasto) { gira0 = arrasto.g + (e.clientX - arrasto.x) * 0.35; if (!tocando) quadro(0); } });
addEventListener("pointerup", () => { arrasto = null; });
$("#btPlay").onclick = (e) => { tocando = !tocando; e.currentTarget.textContent = tocando ? "Pausar" : "Continuar"; e.currentTarget.classList.toggle("on", tocando); };
document.querySelectorAll(".chave").forEach((ch) => ch.querySelectorAll("button").forEach((b, i) => b.addEventListener("click", () => {
  ch.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x === b)); ch.style.setProperty("--i", i);
  estilo({ [ch.dataset.chave]: i === 1 });
})));
$("#btGira").onclick = (e) => { girando = !girando; e.currentTarget.classList.toggle("on", girando); };
$("#btLento").onclick = (e) => { lento = !lento; e.currentTarget.classList.toggle("on", lento); };
if (reduz) $("#btPlay").textContent = "Continuar", $("#btPlay").classList.remove("on");


// ---------- moldes extras (moldes/*.js, montados pelo build.py) ----------
// ===== moldes/00-kit.js =====
// ---------- kit de equipamento compartilhado pelos moldes extras (moldes/*.js) ----------
// Tudo em metros, Y pra cima. Mesmo material e acabamento do resto (M.quadro, M.aco, M.cromo, M.estofado, M.borracha).
const K = {};
const _yUp = V3(0, 1, 0);
K.caixa = (w, h, d, mat = M.quadro, raio = 0.01) => new THREE.Mesh(new RoundedBoxGeometry(w, h, d, 2, Math.min(raio, w / 2.2, h / 2.2, d / 2.2)), mat);
// cilindro de comprimento 1 no eixo Y; K.poe estica/gira entre dois pontos (serve pra cabo, tubo, corrente)
K.cilU = (r, mat = M.aco, seg = 16) => { const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, 1, seg), mat); m.castShadow = true; return m; };
K.poe = (m, a, b) => { const d = b.clone().sub(a), L = Math.max(d.length(), 1e-4); m.position.copy(a).add(b).multiplyScalar(0.5); m.scale.set(1, L, 1); m.quaternion.setFromUnitVectors(_yUp, d.multiplyScalar(1 / L)); return m; };
K.tubo = (a, b, r = 0.02, mat = M.quadro) => K.poe(K.cilU(r, mat, 20), a, b);
K.viga = (a, b, w = 0.06, mat = M.quadro, h = w) => { // perfil quadrado entre dois pontos
  const d = b.clone().sub(a), L = d.length(), m = K.caixa(w, L, h, mat, 0.008);
  m.position.copy(a).add(b).multiplyScalar(0.5); m.quaternion.setFromUnitVectors(_yUp, d.normalize()); return m;
};
K.cabo = () => K.cilU(0.0035, new THREE.MeshStandardMaterial({ color: 0x1b1c1f, roughness: 0.45, metalness: 0.3 }), 8);

// pilha de placas com pino e guias (fica dentro da torre/máquina); sobe = quanto a pilha levantou (m)
K.pilha = (n = 14) => {
  const g = new THREE.Group(), placas = new THREE.Group();
  for (let i = 0; i < n; i++) { const p = K.caixa(0.27, 0.021, 0.13, M.quadro, 0.004); p.position.y = 0.06 + i * 0.024; placas.add(p); }
  const pino = K.cilU(0.006, M.cromo); pino.scale.y = 0.16; pino.rotation.x = Math.PI / 2; pino.position.set(0, 0.06 + 6 * 0.024, 0.08); placas.add(pino);
  g.add(placas);
  for (const x of [-0.1, 0.1]) g.add(K.tubo(V3(x, 0, 0), V3(x, 0.06 + n * 0.024 + 0.75, 0), 0.008, M.cromo));
  g.userData.placas = placas;
  g.userData.sobe = (y) => { placas.position.y = Math.max(0, y); };
  return sombreia(g);
};

// torre de polia (crossover / polia alta / polia baixa): a polia fica na frente da coluna, na altura alt (m).
// A coluna fica atrás de +Z local; a saída do cabo aponta pra +Z local. Use t.saida() pra pegar o ponto no mundo
// e t.liga(pontoMundo) a cada quadro pra esticar o cabo até o pegador (a pilha sobe junto com o curso).
K.torre = ({ alt = 1.0, altura = 2.2 } = {}) => {
  const g = new THREE.Group();
  g.add(K.caixa(0.5, 0.04, 0.5, M.quadro, 0.01).translateY(0.02));
  for (const x of [-0.2, 0.2]) { const c = K.caixa(0.07, altura, 0.07); c.position.set(x, altura / 2, -0.12); g.add(c); }
  const topo = K.caixa(0.5, 0.07, 0.2); topo.position.set(0, altura, -0.08); g.add(topo);
  const tampa = K.caixa(0.36, altura * 0.75, 0.025, M.quadro, 0.006); tampa.position.set(0, altura * 0.42, -0.215); g.add(tampa);
  const pilha = K.pilha(); pilha.position.set(0, 0.04, -0.12); g.add(pilha);
  // trilho da polia + carrinho na altura alt
  g.add(K.tubo(V3(0, 0.12, 0.02), V3(0, altura - 0.1, 0.02), 0.018, M.aco));
  const carro = new THREE.Group(); carro.position.set(0, alt, 0.02);
  carro.add(K.caixa(0.09, 0.12, 0.06, M.quadro, 0.01));
  const roda = new THREE.Mesh(new THREE.TorusGeometry(0.038, 0.01, 10, 28), M.aco); roda.position.set(0, 0, 0.065); roda.rotation.y = Math.PI / 2; carro.add(roda);
  const eixo = K.cilU(0.012, M.cromo); eixo.scale.y = 0.06; eixo.rotation.z = Math.PI / 2; eixo.position.z = 0.065; carro.add(eixo);
  for (const s of [-1, 1]) { const ch = K.caixa(0.008, 0.11, 0.1, M.aco, 0.003); ch.position.set(s * 0.022, 0, 0.05); carro.add(ch); }
  g.add(carro);
  const cabo = K.cabo(); g.add(cabo); // no espaço local da torre
  const saidaL = V3(0, alt, 0.11);
  let L0 = null;
  const t = {
    g: sombreia(g), cabo,
    saida: () => { g.updateMatrixWorld(true); return g.localToWorld(saidaL.clone()); },
    liga(pontoMundo) {
      g.updateMatrixWorld(true);
      const pl = g.worldToLocal(pontoMundo.clone()); K.poe(cabo, saidaL, pl);
      const L = pl.distanceTo(saidaL); if (L0 === null) L0 = L;
      pilha.userData.sobe(Math.min(0.5, Math.max(0, (L - L0) * 0.5)));
    },
    zeraCurso() { L0 = null; },
  };
  return t;
};

// pegadores (centro da pegada na origem; eixo de pegar = X local; o cabo prende em +Y local quando faz sentido)
K.corda = () => { // corda de tríceps: argola + duas pontas com batente
  const g = new THREE.Group(), mat = new THREE.MeshStandardMaterial({ color: 0x15161a, roughness: 0.8 });
  const argola = new THREE.Mesh(new THREE.TorusGeometry(0.018, 0.005, 8, 20), M.aco); argola.position.y = 0.05; g.add(argola);
  g.userData.pontas = [];
  for (const s of [-1, 1]) {
    const fio = K.cilU(0.011, mat, 12); g.add(fio);
    const bat = new THREE.Mesh(new THREE.SphereGeometry(0.02, 16, 12), new THREE.MeshStandardMaterial({ color: 0x0d0d0f, roughness: 0.5 })); g.add(bat);
    g.userData.pontas.push({ fio, bat, s });
  }
  // abre(a, b): pontas da corda em a e b (mundo -> local do grupo); topo = onde prende no cabo
  g.userData.abre = (a, b) => { g.updateMatrixWorld(true); const top = V3(0, 0.04, 0);
    [a, b].forEach((p, i) => { const pl = g.worldToLocal(p.clone()); const { fio, bat } = g.userData.pontas[i]; K.poe(fio, top, pl); bat.position.copy(pl).add(pl.clone().sub(top).normalize().multiplyScalar(0.02)); }); };
  return sombreia(g);
};
K.barraReta = (comp = 0.5) => { const g = new THREE.Group(); const h = K.cilU(0.013, M.cromo); h.scale.y = comp; h.rotation.z = Math.PI / 2; g.add(h);
  for (const s of [-1, 1]) { const p = K.cilU(0.016, M.borracha); p.scale.y = 0.12; p.rotation.z = Math.PI / 2; p.position.x = s * (comp / 2 - 0.08); g.add(p); }
  const ar = new THREE.Mesh(new THREE.TorusGeometry(0.016, 0.005, 8, 18), M.aco); ar.position.y = 0.024; g.add(ar); return sombreia(g); };
K.barraV = () => { const g = new THREE.Group();
  for (const s of [-1, 1]) { const b = K.cilU(0.013, M.cromo); b.scale.y = 0.16; b.position.set(s * 0.065, -0.03, 0); b.rotation.z = s * 0.55; g.add(b);
    const p = K.cilU(0.016, M.borracha); p.scale.y = 0.1; p.position.set(s * 0.12, -0.07, 0); p.rotation.z = s * 0.55; g.add(p); }
  const ar = new THREE.Mesh(new THREE.TorusGeometry(0.016, 0.005, 8, 18), M.aco); ar.position.y = 0.04; g.add(ar); return sombreia(g); };
K.triangulo = () => { const g = new THREE.Group(); // pegador de remada (pegada neutra, mãos juntas)
  for (const s of [-1, 1]) { const p = K.cilU(0.014, M.borracha); p.scale.y = 0.11; p.rotation.x = Math.PI / 2; p.position.set(s * 0.045, 0, 0); g.add(p);
    g.add(K.tubo(V3(s * 0.045, 0, 0.06), V3(0, 0.12, 0), 0.008, M.cromo)); g.add(K.tubo(V3(s * 0.045, 0, -0.06), V3(0, 0.12, 0), 0.008, M.cromo)); }
  return sombreia(g); };
K.estribo = () => { const g = new THREE.Group(); // alça em D de uma mão
  const p = K.cilU(0.015, M.borracha); p.scale.y = 0.12; p.rotation.z = Math.PI / 2; g.add(p);
  const arco = new THREE.Mesh(new THREE.TorusGeometry(0.075, 0.006, 8, 24, Math.PI), M.cromo); arco.position.y = 0.0; g.add(arco); return sombreia(g); };
K.tornozeleira = () => { const g = new THREE.Group(); const b = new THREE.Mesh(new THREE.TorusGeometry(0.05, 0.016, 10, 24), M.estofado); b.rotation.x = Math.PI / 2; g.add(b);
  const ar = new THREE.Mesh(new THREE.TorusGeometry(0.014, 0.004, 8, 16), M.aco); ar.position.z = 0.065; g.add(ar); return sombreia(g); };
K.caneleira = () => { const g = new THREE.Group(); const b = new THREE.Mesh(new THREE.TorusGeometry(0.055, 0.025, 10, 24), new THREE.MeshStandardMaterial({ color: 0x2a2d35, roughness: 0.75 })); b.rotation.x = Math.PI / 2; g.add(b); return sombreia(g); };

// estofados
K.assento = (w = 0.36, d = 0.36, e = 0.08) => K.caixa(w, e, d, M.estofado, 0.03);
K.rolo = (comp = 0.36, r = 0.05) => { const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, comp, 24), M.estofado); m.rotation.z = Math.PI / 2; const g = new THREE.Group(); g.add(m); return sombreia(g); };

// banco ajustável: assento + encosto em ângulo (graus; 0 = reto, 45 = inclinado, -15 = declinado). Corpo deitado com a
// cabeça pra -X (como no supino). Retorna { g, encostoTopo, assentoCentro } em coordenadas locais do banco.
K.banco = ({ inclina = 0, comp = 1.18 } = {}) => {
  if (!inclina) return { g: banco(comp), assento: V3(0.2, 0.445, 0), encosto: V3(-0.25, 0.445, 0) };
  const g = new THREE.Group(), a = inclina * Math.PI / 180;
  const assento = K.caixa(0.42, 0.085, 0.29, M.estofado, 0.03); assento.position.set(0.22, 0.42, 0); assento.rotation.z = inclina < 0 ? -a * 0.6 : 0; g.add(assento);
  const enc = K.caixa(0.86, 0.085, 0.29, M.estofado, 0.03); const cab = V3(-Math.cos(a), Math.sin(a), 0);
  enc.position.copy(V3(0.02, 0.44, 0).add(cab.clone().multiplyScalar(0.43))); enc.rotation.z = -a; g.add(enc);
  g.add(K.viga(V3(0.22, 0.36, 0), V3(0.22, 0.04, 0), 0.06)); g.add(K.viga(enc.position.clone().add(V3(0, -0.06, 0)), V3(enc.position.x, 0.04, 0), 0.06));
  for (const x of [0.3, enc.position.x]) g.add(K.caixa(0.08, 0.05, 0.46, M.quadro, 0.015).translateX(x).translateY(0.025));
  if (inclina < 0) { const r = K.rolo(0.34, 0.045); r.position.set(0.55, 0.42, 0); r.rotation.y = Math.PI / 2; g.add(r); } // trava dos pés no declinado
  return { g: sombreia(g), assento: assento.position.clone(), encosto: enc.position.clone(), cab };
};

// Smith: duas guias verticais e a barra num carrinho; s.barra.position.y = altura da barra
K.smith = ({ alt = 2.15, larg = 1.25 } = {}) => {
  const g = new THREE.Group();
  for (const z of [-larg / 2, larg / 2]) {
    g.add(K.caixa(0.12, alt, 0.12).translateZ(z).translateY(alt / 2).translateX(-0.25));
    g.add(K.caixa(0.6, 0.05, 0.12).translateZ(z).translateY(0.025));
    g.add(K.tubo(V3(0, 0.05, z * 0.92), V3(0, alt - 0.05, z * 0.92), 0.016, M.cromo));
  }
  g.add(K.caixa(0.12, 0.08, larg + 0.12).translateY(alt).translateX(-0.25));
  const barraG = new THREE.Group(); const haste = K.cilU(0.014, M.cromo); haste.scale.y = larg * 1.3; haste.rotation.x = Math.PI / 2; barraG.add(haste);
  for (const s of [-1, 1]) { const c = K.caixa(0.07, 0.09, 0.06, M.aco, 0.01); c.position.z = s * larg * 0.46; barraG.add(c);
    const a = anilha(0.2, 0.04); a.rotation.x = Math.PI / 2; a.position.z = s * larg * 0.6; barraG.add(a); }
  g.add(barraG);
  return { g: sombreia(g), barra: barraG };
};
K.barraFixa = ({ alt = 2.3, larg = 1.2 } = {}) => { const g = new THREE.Group();
  for (const z of [-larg / 2, larg / 2]) { g.add(K.caixa(0.08, alt + 0.1, 0.08).translateZ(z).translateY((alt + 0.1) / 2).translateX(-0.12)); g.add(K.caixa(0.7, 0.04, 0.1).translateZ(z).translateY(0.02)); }
  const b = K.cilU(0.016, M.cromo); b.scale.y = larg; b.rotation.x = Math.PI / 2; b.position.set(0, alt, 0); g.add(b);
  for (const s of [-1, 1]) g.add(K.viga(V3(-0.12, alt, s * larg / 2), V3(0, alt, s * larg / 2), 0.05));
  return { g: sombreia(g), barra: V3(0, alt, 0) }; };
K.paralelas = ({ alt = 1.15, abre = 0.52, comp = 0.8 } = {}) => { const g = new THREE.Group();
  for (const s of [-1, 1]) { const z = s * abre / 2;
    const b = K.cilU(0.022, M.borracha); b.scale.y = comp; b.rotation.z = Math.PI / 2; b.position.set(0, alt, z); g.add(b);
    for (const x of [-comp / 2 + 0.06, comp / 2 - 0.06]) g.add(K.viga(V3(x, alt - 0.02, z), V3(x, 0.02, z), 0.06));
    g.add(K.caixa(comp, 0.04, 0.12).translateZ(z).translateY(0.02)); }
  return { g: sombreia(g), alt, abre }; };
K.colchonete = (comp = 1.8, larg = 0.6) => { const m = K.caixa(comp, 0.02, larg, new THREE.MeshStandardMaterial({ color: 0x2b3340, roughness: 0.85 }), 0.008); m.position.y = 0.01; m.receiveShadow = true; return m; };
K.step = (alt = 0.3) => sombreia(K.caixa(0.8, alt, 0.36, M.borracha, 0.03).translateY(alt / 2));
K.caixote = (alt = 0.5) => sombreia(K.caixa(0.6, alt, 0.5, new THREE.MeshStandardMaterial({ color: 0x5b4632, roughness: 0.7 }), 0.02).translateY(alt / 2));
K.kettlebell = (kg = 16) => { const g = new THREE.Group(), r = 0.075 + kg * 0.0015;
  const corpo = new THREE.Mesh(new THREE.SphereGeometry(r, 28, 20), M.borracha); corpo.scale.y = 0.92; g.add(corpo);
  const alca = new THREE.Mesh(new THREE.TorusGeometry(r * 0.62, 0.012, 10, 24, Math.PI), M.aco); alca.position.y = r * 0.75; g.add(alca);
  for (const s of [-1, 1]) g.add(K.tubo(V3(s * r * 0.62, r * 0.75, 0), V3(s * r * 0.55, r * 0.55, 0), 0.012, M.aco));
  return sombreia(g); }; // origem = centro da bola; a pegada fica em y ≈ r*1.35
K.bolaMed = (r = 0.12) => sombreia(new THREE.Group().add(new THREE.Mesh(new THREE.SphereGeometry(r, 32, 24), new THREE.MeshStandardMaterial({ color: 0x3a2f2a, roughness: 0.7 }))));
K.bolaSuica = (r = 0.32) => sombreia(new THREE.Group().add(new THREE.Mesh(new THREE.SphereGeometry(r, 40, 30), new THREE.MeshPhysicalMaterial({ color: 0x55606f, roughness: 0.4, clearcoat: 0.3 }))));
K.elastico = () => K.cilU(0.006, new THREE.MeshStandardMaterial({ color: 0x3f6fd8, roughness: 0.6 }), 10); // estica com K.poe(el, a, b)
K.anilhaMao = (r = 0.17) => { const a = anilha(r, 0.035); return sombreia(a); }; // anilha segurada (furo/pega no centro)
// piso emborrachado padrão pros moldes extras (mesmo do tablado, sem a madeira)
K.piso = (w = 2.4, d = 2.4) => { const m = K.caixa(w, 0.02, d, M.borracha, 0.006); m.position.y = -0.01; m.receiveShadow = true; return m; };

// ===== moldes/biceps.js =====
{ // moldes/biceps.js — rosca (bíceps): em pé, banco Scott, inclinado, spider, concentrada, polias

// ---------- ajudantes ----------
const bLU = COMP.upperarm_l, bLF = COMP.lowerarm_l;
const bU = (v) => v.clone().normalize();
const bOrt = (v, ref) => { const r = ref.clone().normalize(); return v.clone().sub(r.multiplyScalar(v.dot(r))).normalize(); }; // v sem a parte paralela a ref
const bFlex = (u, m, f) => u.clone().multiplyScalar(Math.cos(f)).add(m.clone().multiplyScalar(Math.sin(f))).normalize(); // antebraço: u (braço) girando pra m em f rad
const bSuave = (a, b, x) => { const k = Math.min(1, Math.max(0, (x - a) / (b - a))); return k * k * (3 - 2 * k); };
const bLado = (l) => (l === "l" ? 1 : -1);
// mão no antebraço a: o = lado de fora (unitário), s = +1 esquerda/-1 direita; sup 0 = neutra (martelo), 1 = supinada, -1 = pronada
function bMao(a, o, s, sup) {
  const h = bOrt(o, a), kN = a.clone().cross(h).multiplyScalar(s).normalize(), nN = h.clone().negate();
  const g = sup * Math.PI / 2, c = Math.cos(g), sn = Math.sin(g);
  return { k: kN.clone().multiplyScalar(c).add(h.clone().multiplyScalar(sn)), n: nN.clone().multiplyScalar(c).add(kN.clone().multiplyScalar(sn)) };
}
// braço em rosca: cotovelo preso no braço u (sai do ombro), antebraço dobrando de u pra m em f rad. Devolve o centro da pegada.
function bCurl(l, { u, m, f, sup = 1, R = 0.0135, o = null, k = null, n = null }) {
  const s = bLado(l), S = ondeEsta("upperarm_" + l);
  const a = bFlex(u, m, f), cot = S.clone().add(u.clone().multiplyScalar(bLU)), punho = cot.clone().add(a.clone().multiplyScalar(bLF));
  const ori = k && n ? { k, n } : bMao(a, o || esquerda(F0).multiplyScalar(s), s, sup);
  const O = agarra(l, { punho, eixo: ori.k, palma: ori.n, R, polo: u.clone() });
  return { O, cot, a, punho, S };
}
function bEmPe(incl = 0.02, dy = 0.015, pe = {}) {
  emPe(V3(0, ALT_QUADRIL - dy, 0), F0, incl);
  B.pelvis.updateMatrixWorld(true);
  pernas(F0, Object.assign({ abre: 0.13, fora: 0.2, poloFora: 0.2 }, pe));
}
const bBase = (x, y, z) => new THREE.Matrix4().makeBasis(x, y, z);
function bBarra(bar, Ol, Or, F) { // x local = da mão direita pra esquerda; z local = pra frente
  const x = bU(Ol.clone().sub(Or)), z = bOrt(F, x), y = z.clone().cross(x);
  bar.position.copy(Ol).add(Or).multiplyScalar(0.5); bar.quaternion.setFromRotationMatrix(bBase(x, y, z));
}
// barra W (EZ): o zigue-zague fica no plano XZ; as pegadas são as diagonais externas (centro em x = ±0.195, z = 0), a ponta de fora mais longe do corpo
function bBarraW(comp = 1.2, r = 0.11) {
  const g = new THREE.Group(), h = 0.02, mat = M.cromo;
  const P = [[-comp / 2, h], [-0.235, h], [-0.155, -h], [0, h], [0.155, -h], [0.235, h], [comp / 2, h]].map(([x, z]) => V3(x, 0, z));
  for (let i = 0; i < P.length - 1; i++) g.add(K.tubo(P[i], P[i + 1], 0.0125, mat));
  for (const p of P.slice(1, -1)) { const e = new THREE.Mesh(new THREE.SphereGeometry(0.0125, 14, 10), mat); e.position.copy(p); g.add(e); }
  for (const s of [-1, 1]) {
    for (let i = 0; i < 2; i++) { const a = anilha(r, 0.03); a.rotation.z = Math.PI / 2; a.position.set(s * (comp / 2 - 0.1 - i * 0.034), 0, h); g.add(a); }
    const t = cil(0.028, 0.02, M.faixa); t.rotation.z = Math.PI / 2; t.position.set(s * (comp / 2 - 0.1 - 2 * 0.034 - 0.005), 0, h); g.add(t);
  }
  return sombreia(g);
}
const BW_ANG = Math.atan2(0.04, 0.08); // inclinação da pegada na barra W (≈27°)
// tronco inclinado pra frente a partir do quadril (sentado): incl total em rad, repartida entre pelve e coluna; cabeça sempre olhando pra frente
function bTronco(P, incl, cab = 0.5) {
  emPe(P, F0, incl * 0.5);
  gira("spine_01", EX, incl * 0.12); gira("spine_02", EX, incl * 0.14); gira("spine_03", EX, incl * 0.14);
  gira("neck_01", EX, -incl * cab * 0.7); gira("head", EX, -incl * cab * 0.3);
  B.pelvis.updateMatrixWorld(true);
}
// pernas: tornozelos no chão em (x, ±z); joelho pra fora/cima (polo). Devolve nada; use ondeEsta("calf_x") pro joelho.
function bPernas(x, z, polo = V3(0.25, 1, 0.55), pe0 = 0.2) {
  for (const l of ["l", "r"]) {
    const s = bLado(l) * -1; // l = -Z
    perna(l, V3(x, ALT_TORN, s * z), V3(polo.x, polo.y, s * polo.z));
    pe(l, girarY(F0, -s * pe0));
  }
}

// ---------- moldes ----------
Object.assign(MOLDES, {
  // Rosca direta em pé com barra (reta curta ou W) — cotovelo colado, antebraço sobe.
  bi_rosca: {
    nome: "Rosca direta com barra W",
    musc: { biceps: 1, antebraco: 0.5, deltoide: 0.2 },
    dica: "Cotovelo colado nas costelas e parado; só o antebraço se move. Pega nas dobras da barra W (punho meio inclinado, mais confortável). Sobe sem balançar o tronco e desce controlando até quase esticar.",
    cam: { alvo: V3(0.05, 1.02, 0), dist: 3.7, yaw: 62, pitch: 12 },
    cena(g) { g.add(tablado()); this.bar = this.p.w ? bBarraW() : barraCurta(); g.add(this.bar); },
    pose(t) {
      zera(); bEmPe(0.02);
      const prog = 1 - t, f = 0.16 + prog * 2.3, E = esquerda(F0), w = !!this.p.w, pg = {};
      for (const l of ["l", "r"]) {
        const s = bLado(l), o = E.clone().multiplyScalar(s);
        const u = bU(V3(0.05 + 0.1 * prog, -1, 0).add(o.clone().multiplyScalar(0.01)));
        const m = bOrt(F0.clone().add(o.clone().multiplyScalar(-0.06)), u);
        const sup = 1, a0 = bFlex(u, m, f);
        const k = w ? o.clone().multiplyScalar(Math.cos(BW_ANG)).add(F0.clone().multiplyScalar(Math.sin(BW_ANG))) : o;
        const n = a0.clone().cross(E);
        pg[l] = bCurl(l, { u, m, f, k, n, R: 0.0135 }).O;
      }
      bBarra(this.bar, pg.l, pg.r, F0);
    },
  },
  // Rosca alternada: um braço por vez; começa com a palma pro corpo e vira pra cima durante a subida.
  bi_alternada: {
    nome: "Rosca alternada com halteres",
    musc: { biceps: 1, antebraco: 0.4, deltoide: 0.2 },
    dica: "Um braço de cada vez, cotovelo colado. Começa com a palma virada pra coxa e vai girando o punho pra cima enquanto sobe (supinação), que é o que acende o bíceps. O outro braço espera esticado.",
    cam: { alvo: V3(0.05, 1.02, 0), dist: 3.7, yaw: 70, pitch: 12 },
    cena(g) { g.add(tablado()); this.h = [halter(0.4), halter(0.4)]; g.add(...this.h); },
    fase(r) { this.lado = Math.floor(r / CICLO) % 2; return fase(r); },
    pose(t) {
      zera(); bEmPe(0.02);
      const quem = this.lado ? "l" : "r", prog = 1 - t, E = esquerda(F0);
      ["l", "r"].forEach((l, i) => {
        const s = bLado(l), o = E.clone().multiplyScalar(s), pr = l === quem ? prog : 0;
        const f = 0.14 + pr * 2.3, sup = bSuave(0.04, 0.55, pr);
        const u = bU(V3(0.03 + 0.1 * pr, -1, 0).add(o.clone().multiplyScalar(0.04 * (1 - pr))));
        bCurl(l, { u, m: bOrt(F0, u), f, sup, R: 0.016, o });
        seguraHalter(this.h[i], l);
      });
    },
  },
  // Martelo cruzada: pegada neutra, o halter atravessa o peito até o ombro do outro lado.
  bi_cruzada: {
    nome: "Rosca martelo cruzada",
    musc: { biceps: 0.7, antebraco: 0.5, deltoide: 0.3 },
    dica: "Pegada neutra (palma pro corpo), cotovelo colado. Em vez de subir reto, leva o halter na diagonal por cima do peito, em direção ao ombro do outro lado, e desce pelo mesmo caminho.",
    cam: { alvo: V3(0.05, 1.05, 0), dist: 3.4, yaw: 78, pitch: 12 },
    cena(g) { g.add(tablado()); this.h = [halter(0.4), halter(0.4)]; g.add(...this.h); },
    fase(r) { this.lado = Math.floor(r / CICLO) % 2; return fase(r); },
    pose(t) {
      zera(); bEmPe(0.02);
      const quem = this.lado ? "l" : "r", prog = 1 - t, E = esquerda(F0);
      ["l", "r"].forEach((l, i) => {
        const s = bLado(l), o = E.clone().multiplyScalar(s), pr = l === quem ? prog : 0, dentro = o.clone().negate();
        const f = 0.14 + pr * 2.15;
        const u = bU(V3(0.03 + 0.14 * pr, -1, 0).add(o.clone().multiplyScalar(0.04 * (1 - pr))).add(dentro.clone().multiplyScalar(0.1 * pr)));
        const m = bOrt(F0.clone().multiplyScalar(0.75).add(dentro.clone().multiplyScalar(0.65 * pr)), u);
        const oh = u.clone().cross(m).multiplyScalar(-s).normalize();
        bCurl(l, { u, m, f, sup: 0, R: 0.016, o: oh });
        seguraHalter(this.h[i], l);
      });
    },
  },
  // Concentrada: sentado no banco, pernas abertas, cotovelo apoiado na parte de dentro da coxa, braço pendurado vertical; só o antebraço sobe.
  bi_concentrada: {
    nome: "Rosca concentrada",
    musc: { biceps: 1, antebraco: 0.35, deltoide: 0.1 },
    dica: "Senta na ponta do banco com as pernas abertas, apoia a parte de trás do cotovelo na parte de dentro da coxa e deixa o braço pendurado. Sobe o halter até o ombro girando o punho pra cima, aperta o bíceps e desce até quase esticar.",
    cam: { alvo: V3(0.38, 0.72, 0), dist: 3.0, yaw: 122, pitch: 26 },
    cena(g) { g.add(tablado()); const b = banco(1.2); b.position.set(-0.46, 0, 0); g.add(b); this.h = halter(0.5); g.add(this.h); },
    pose(t) {
      zera();
      const quem = this.p.lado === "l" ? "l" : "r", outra = quem === "l" ? "r" : "l", lz = quem === "r" ? 1 : -1, prog = 1 - t;
      bTronco(V3(0, 0.575, 0), this.p.incl || 1.4);
      bPernas(0.46, 0.3, V3(0.2, 1, 0.5), 0.2);
      const S = ondeEsta("upperarm_" + quem), H = ondeEsta("thigh_" + quem), Kn = ondeEsta("calf_" + quem), dir = Kn.clone().sub(H);
      const rep = (lam) => H.clone().add(dir.clone().multiplyScalar(lam)).add(V3(0, 0, -lz * 0.085)).add(V3(0, 0.09, 0));
      let lo = 0.3, hi = 0.97; for (let i = 0; i < 30; i++) { const mid = (lo + hi) / 2; if (rep(mid).sub(S).length() > bLU) lo = mid; else hi = mid; }
      const lam = (lo + hi) / 2, Et = rep(lam), u = bU(Et.clone().sub(S));
      const m = bOrt(F0, u), f = 0.3 + prog * 2.1, sup = 0.45 + 0.55 * bSuave(0.1, 0.8, prog);
      bCurl(quem, { u, m, f, sup, R: 0.016, o: V3(0, 0, lz) });
      seguraHalter(this.h, quem);
      // mão livre: espalmada no joelho do outro lado
      const Ho = ondeEsta("thigh_" + outra), Ko = ondeEsta("calf_" + outra), alvo = Ho.clone().lerp(Ko, 0.72).add(V3(0, 0.1, 0));
      braco(outra, alvo, V3(-0.4, 0.3, -lz));
      mao(outra, F0.clone().add(V3(0, -0.2, 0)), V3(0, -1, 0));
    },
  },
});
// ---------- banco Scott: corpo sentado e apoio inclinado ----------
const BS = { beta: 50 * Math.PI / 180, seat: 0.5, pad: 0.058 };
const bSd = V3(Math.cos(BS.beta), -Math.sin(BS.beta), 0), bSn = V3(Math.sin(BS.beta), Math.cos(BS.beta), 0); // d = pra baixo e pra frente ao longo do apoio; n = normal pra fora do apoio
function bScottCorpo() { // posiciona o corpo sentado no Scott (sem braços); devolve o meio dos ombros
  zera();
  bTronco(V3(-0.04, BS.seat + 0.1215, 0), 0.3, 0.3);
  bPernas(0.5, 0.25, V3(0.2, 1, 0.4), 0.15);
  return ondeEsta("upperarm_l").add(ondeEsta("upperarm_r")).multiplyScalar(0.5);
}
function bScottBanco(g, SM, comp = 0.42) { // apoio estofado + coluna + assento + base; g = grupo do equipamento
  const Q = SM.clone().sub(bSn.clone().multiplyScalar(BS.pad)), s0 = -0.04, e = 0.075;
  const C = Q.clone().add(bSd.clone().multiplyScalar((s0 + comp) / 2)).sub(bSn.clone().multiplyScalar(e / 2));
  const pad = K.caixa(comp - s0, e, 0.5, M.estofado, 0.03); pad.position.copy(C); pad.rotation.z = -BS.beta; g.add(pad);
  const A = Q.clone().add(bSd.clone().multiplyScalar(0.22)).sub(bSn.clone().multiplyScalar(e + 0.01));
  g.add(K.viga(A, V3(A.x - 0.0, 0.05, 0), 0.075));
  g.add(K.viga(A.clone().add(bSd.clone().multiplyScalar(-0.04)), A.clone().add(bSd.clone().multiplyScalar(-0.2)).add(bSn.clone().multiplyScalar(-0.1)), 0.05));
  const assento = K.assento(0.36, 0.3, 0.07); assento.position.set(-0.07, BS.seat - 0.035, 0); g.add(assento);
  g.add(K.viga(V3(-0.12, BS.seat - 0.07, 0), V3(-0.12, 0.05, 0), 0.07));
  g.add(K.caixa(A.x + 0.55, 0.06, 0.1, M.quadro, 0.01).translateX((A.x - 0.12) / 2 + 0.2).translateY(0.03));
  for (const x of [-0.12, A.x]) g.add(K.caixa(0.09, 0.05, 0.62, M.quadro, 0.015).translateX(x).translateY(0.025));
  return { Q, A };
}
// Rosca Scott: braços apoiados no banco inclinado, só o antebraço mexe. Versões: barra, halter (um braço), máquina (alavanca com came e torre de placas).
Object.assign(MOLDES, {
  bi_scott: {
    nome: "Rosca Scott com barra",
    musc: { biceps: 1, antebraco: 0.35, deltoide: 0.1 },
    dica: "Axilas coladas no topo do apoio, braços inteiros deitados nele. Sobe até o antebraço ficar quase vertical e desce até quase esticar sem deixar o cotovelo sair do apoio. Não pula no fim da descida.",
    cam: { alvo: V3(0.3, 0.98, 0), dist: 3.1, yaw: 42, pitch: 14 },
    cena(g) {
      g.add(tablado()); const p = this.p, SM = bScottCorpo(); this.SM = SM;
      this.geo = bScottBanco(g, SM, 0.42);
      this.bar = null; this.h = null; this.lev = null;
      if (p.maquina) {
        const Em = SM.clone().add(bSd.clone().multiplyScalar(bLU)), ZL = 0.33, ZP = 0.42;
        this.Em = Em;
        for (const s of [-1, 1]) {
          g.add(K.caixa(0.08, Em.y, 0.07, M.quadro, 0.01).translateX(Em.x).translateY(Em.y / 2).translateZ(s * ZP));
          const cam = K.cilU(0.1, M.aco, 28); cam.scale.y = 0.02; cam.rotation.z = Math.PI / 2; cam.position.set(Em.x, Em.y, s * (ZL + 0.04)); g.add(cam);
        }
        g.add(K.caixa(0.1, 0.05, 0.95, M.quadro, 0.015).translateX(Em.x).translateY(0.025));
        const eixo = K.cilU(0.018, M.cromo); eixo.scale.y = 0.9; eixo.rotation.x = Math.PI / 2; eixo.position.copy(Em); g.add(eixo);
        const torre = K.torre({ alt: 0.9 }); torre.g.position.set(Em.x, 0, -0.98); g.add(torre.g); this.torre = torre;
        this.lev = { rod: [K.tubo(V3(), V3(0, 1, 0), 0.02, M.quadro), K.tubo(V3(), V3(0, 1, 0), 0.02, M.quadro)], pega: [K.cilU(0.017, M.borracha), K.cilU(0.017, M.borracha)], ponta: [K.cilU(0.016, M.cromo), K.cilU(0.016, M.cromo)] };
        for (const m of [...this.lev.rod, ...this.lev.pega, ...this.lev.ponta]) g.add(m);
        for (const m of this.lev.pega) { m.scale.y = 0.2; m.rotation.z = Math.PI / 2; }
        this.pose(1); torre.zeraCurso(); this.pose(1);
        return;
      }
      if (p.halter) { this.h = halter(0.5); g.add(this.h); } else { this.bar = barraCurta(0.13, 1.1); g.add(this.bar); }
    },
    pose(t) {
      const SM = bScottCorpo(), p = this.p, prog = 1 - t, E = esquerda(F0), pg = {};
      const quem = p.lado === "l" ? "l" : "r", f = 0.18 + prog * 2.0;
      ["l", "r"].forEach((l, i) => {
        const s = bLado(l), o = E.clone().multiplyScalar(s), u = bU(bSd.clone().add(o.clone().multiplyScalar(0.06)));
        if (p.halter && l !== quem) { // braço livre: deitado no apoio, mão aberta repousando nele
          const r = bCurl(l, { u, m: bSn.clone(), f: 0.25, sup: 0.5, R: 0.016, o });
          braco(l, r.punho, u); mao(l, r.a, bSn.clone().negate()); return;
        }
        pg[l] = bCurl(l, { u, m: bSn.clone(), f, sup: 1, R: p.halter ? 0.016 : 0.0135, o }).O;
        if (this.h) seguraHalter(this.h, l);
      });
      if (this.bar) bBarra(this.bar, pg.l, pg.r, F0);
      if (this.lev) {
        const Em = this.Em, ZL = 0.33, c = [];
        ["l", "r"].forEach((l, i) => {
          const z = bLado(l) * -ZL, O = pg[l], Pv = V3(Em.x, Em.y, z), Hd = V3(O.x, O.y, z);
          K.poe(this.lev.rod[i], Pv, Hd); K.poe(this.lev.ponta[i], Hd.clone().add(V3(0, 0, Math.sign(z) * 0.03)), Hd.clone().add(V3(0, 0, -Math.sign(z) * 0.0)));
          this.lev.ponta[i].scale.y = 0.06; this.lev.ponta[i].rotation.z = Math.PI / 2;
          this.lev.pega[i].position.set(O.x, O.y, Math.sign(z) * 0.23);
          this.lev.ponta[i].position.set(O.x, O.y, Math.sign(z) * 0.335);
          const e1 = Hd.clone().sub(Pv).normalize(); c[i] = Pv.clone().add(V3(-e1.y, e1.x, 0).multiplyScalar(0.1));
        });
        this.torre.liga(V3(c[0].x, c[0].y, -0.37 - 0.0).setZ(-0.37));
        this.torre.g.updateMatrixWorld(true);
      }
    },
  },
});
// ---------- polias ----------
function bTorre(g, saida, dir, alt) { // torre com a saída do cabo em 'saida' (mundo), apontando pra 'dir' (horizontal)
  const t = K.torre({ alt }); t.g.rotation.y = Math.atan2(dir.x, dir.z); t.g.position.set(0, 0, 0); t.g.updateMatrixWorld(true);
  const s0 = t.saida(); t.g.position.copy(saida).sub(s0); g.add(t.g); t.g.updateMatrixWorld(true); return t;
}
function bLivre(l, u, f) { // braço solto ao lado, mão aberta
  const S = ondeEsta("upperarm_" + l), a = bFlex(u, bOrt(F0, u), f), cot = S.clone().add(u.clone().multiplyScalar(bLU));
  braco(l, cot.clone().add(a.clone().multiplyScalar(bLF)), u); mao(l, a, esquerda(F0).multiplyScalar(-bLado(l)));
}
function bSpiderCorpo() { // prono no banco a 45°, devolve o meio dos ombros
  zera();
  const a = 45 * Math.PI / 180, c = V3(Math.cos(a), Math.sin(a), 0), ch = V3(Math.sin(a), -Math.cos(a), 0);
  corpoEm(V3(-0.36, 0.66, 0), c, ch);
  gira("neck_01", EX, -0.45); gira("head", EX, -0.25);
  B.pelvis.updateMatrixWorld(true);
  for (const l of ["l", "r"]) { const s = l === "l" ? -1 : 1; perna(l, V3(-1.06, ALT_TORN + 0.02, s * 0.15), V3(0, 1, s * 0.2)); pe(l, V3(-1, 0, 0), -0.25); }
  return ondeEsta("upperarm_l").add(ondeEsta("upperarm_r")).multiplyScalar(0.5);
}
Object.assign(MOLDES, {
  // Inclinada: sentado no banco a ~55°, braços pendurados atrás da linha do tronco (alonga a cabeça longa), sobe com halteres.
  bi_inclinada: {
    nome: "Rosca inclinada com halteres",
    musc: { biceps: 1, antebraco: 0.35, deltoide: 0.1 },
    dica: "Costas inteiras no encosto inclinado, braços soltos pendurados na vertical, ombros pra trás. Sobe girando o punho sem tirar o cotovelo do lugar e desce até esticar por completo: o bíceps fica bem alongado embaixo.",
    cam: { alvo: V3(0.12, 0.78, 0), dist: 3.4, yaw: 50, pitch: 12 },
    cena(g) { g.add(tablado()); this.bn = K.banco({ inclina: 55 }); g.add(this.bn.g); this.h = [halter(0.5), halter(0.5)]; g.add(...this.h); },
    pose(t) {
      zera();
      const a = 55 * Math.PI / 180, cab = V3(-Math.cos(a), Math.sin(a), 0), fr = V3(Math.sin(a), Math.cos(a), 0), prog = 1 - t, E = esquerda(F0);
      corpoEm(V3(0.02, 0.44, 0).add(cab.clone().multiplyScalar(0.05)).add(fr.clone().multiplyScalar(0.165)), cab, fr);
      gira("spine_02", EX, -0.07); gira("spine_03", EX, -0.06); gira("neck_01", EX, 0.5); gira("head", EX, 0.2);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { const s = l === "l" ? -1 : 1; perna(l, V3(0.62, ALT_TORN, s * 0.3), V3(0.3, 1, s * 0.25)); pe(l, V3(1, 0, s * 0.2)); }
      ["l", "r"].forEach((l, i) => {
        const s = bLado(l), o = E.clone().multiplyScalar(s);
        const u = bU(V3(-0.08 + 0.1 * prog, -1, 0).add(o.clone().multiplyScalar(0.05)));
        bCurl(l, { u, m: bOrt(F0, u), f: 0.1 + prog * 2.15, sup: 0.2 + 0.8 * bSuave(0.05, 0.5, prog), R: 0.016, o });
        seguraHalter(this.h[i], l);
      });
    },
  },
  // Spider: peito no banco inclinado de frente, braços pendurados na vertical por cima da borda, sobe com barra W.
  bi_spider: {
    nome: "Rosca spider",
    musc: { biceps: 1, antebraco: 0.35, deltoide: 0.05 },
    dica: "Deita de peito no banco inclinado, braços soltos na vertical por cima da borda. Sobe a barra sem balançar, aperta o bíceps no topo (ele fica encurtado) e desce até esticar. O banco impede qualquer roubo com o corpo.",
    cam: { alvo: V3(0.1, 0.78, 0), dist: 3.2, yaw: 40, pitch: 10 },
    cena(g) {
      g.add(tablado()); const a = 45 * Math.PI / 180, c = V3(Math.cos(a), Math.sin(a), 0), nO = V3(-Math.sin(a), Math.cos(a), 0);
      const S = bSpiderCorpo(); const Sp = S.clone().sub(nO.clone().multiplyScalar(0.12)), T = Sp.clone().sub(c.clone().multiplyScalar(0.24));
      const L = 0.95, pad = K.caixa(L, 0.085, 0.3, M.estofado, 0.03); pad.position.copy(T).sub(c.clone().multiplyScalar(L / 2)).sub(nO.clone().multiplyScalar(0.0425)); pad.rotation.z = a; g.add(pad);
      const baixo = (k) => T.clone().sub(c.clone().multiplyScalar(k)).sub(nO.clone().multiplyScalar(0.085));
      for (const k of [0.12, 0.8]) { const b = baixo(k); g.add(K.viga(b, V3(b.x, 0.05, 0), 0.06)); g.add(K.caixa(0.08, 0.05, 0.46, M.quadro, 0.015).translateX(b.x).translateY(0.025)); }
      this.bar = bBarraW(); g.add(this.bar);
    },
    pose(t) {
      bSpiderCorpo();
      const prog = 1 - t, E = esquerda(F0), pg = {};
      ["l", "r"].forEach((l) => {
        const s = bLado(l), o = E.clone().multiplyScalar(s), u = bU(V3(0.0, -1, 0).add(o.clone().multiplyScalar(0.03)));
        const k = o.clone().multiplyScalar(Math.cos(BW_ANG)).add(F0.clone().multiplyScalar(Math.sin(BW_ANG)));
        const f = 0.12 + prog * 2.1, a0 = bFlex(u, bOrt(F0, u), f);
        pg[l] = bCurl(l, { u, m: bOrt(F0, u), f, k, n: a0.clone().cross(E) }).O;
      });
      bBarra(this.bar, pg.l, pg.r, F0);
    },
  },
  // Polia baixa (barra reta) e polia com corda (martelo).
  bi_polia: {
    nome: "Rosca na polia baixa",
    musc: { biceps: 1, antebraco: 0.4, deltoide: 0.2 },
    dica: "De frente pra polia baixa, cotovelo colado. Como o cabo prende a carga o tempo todo, o bíceps trabalha até embaixo (na barra livre a tensão some no fim da descida). Sobe sem balançar e desce controlando.",
    cam: { alvo: V3(0.4, 1.0, 0), dist: 4.3, yaw: 12, pitch: 10 },
    cena(g) {
      g.add(tablado()); const p = this.p;
      this.t = bTorre(g, V3(0.95, 0.25, 0), V3(-1, 0, 0), 0.25);
      if (p.corda) { this.pg = K.corda(); g.add(this.pg); } else { this.bar = K.barraReta(0.5); g.add(this.bar); }
      this.t.liga(V3(0.3, 0.8, 0)); this.t.zeraCurso(); this.t.liga(V3(0.3, 0.8, 0));
    },
    pose(t) {
      zera(); bEmPe(0.03);
      const p = this.p, prog = 1 - t, f = 0.16 + prog * 2.3, E = esquerda(F0), sa = this.t.saida(), pg = {}, us = {}, ms = {};
      for (const l of ["l", "r"]) {
        const s = bLado(l), o = E.clone().multiplyScalar(s);
        const u = bU(V3(0.05 + 0.1 * prog, -1, 0).add(o.clone().multiplyScalar(0.01))); us[l] = u; ms[l] = bOrt(F0.clone().add(o.clone().multiplyScalar(-0.06)), u);
        pg[l] = bCurl(l, { u, m: ms[l], f, sup: p.corda ? 0 : 1, R: p.corda ? 0.012 : 0.0135, o }).O;
      }
      const mid = pg.l.clone().add(pg.r).multiplyScalar(0.5);
      if (p.corda) {
        const ring = mid.clone().add(sa.clone().sub(mid).normalize().multiplyScalar(0.24));
        const fim = {};
        for (const l of ["l", "r"]) {
          const s = bLado(l), o = E.clone().multiplyScalar(s), k = ring.clone().sub(pg[l]).normalize();
          const O = bCurl(l, { u: us[l], m: ms[l], f, k, n: o.clone().negate(), R: 0.012 }).O;
          fim[l] = O.clone().add(O.clone().sub(ring).normalize().multiplyScalar(0.05));
        }
        this.pg.position.copy(ring).sub(V3(0, 0.04, 0)); this.pg.updateMatrixWorld(true);
        this.pg.userData.abre(fim.l, fim.r); this.t.liga(ring.clone().add(V3(0, 0.07, 0)));
      } else {
        const x = bU(pg.l.clone().sub(pg.r)), y = bOrt(sa.clone().sub(mid), x), z = x.clone().cross(y);
        this.bar.position.copy(mid); this.bar.quaternion.setFromRotationMatrix(bBase(x, y, z)); this.bar.updateMatrixWorld(true);
        this.t.liga(this.bar.localToWorld(V3(0, 0.03, 0)));
      }
    },
  },
  // Bayesian: de costas pra polia, braço atrás do corpo; o cabo mantém o bíceps esticado no começo.
  bi_bayesian: {
    nome: "Rosca bayesian na polia",
    musc: { biceps: 1, antebraco: 0.4, deltoide: 0.15 },
    dica: "De costas pra polia baixa, um braço de cada vez, tronco levemente inclinado e cotovelo ficando atrás da linha do corpo. Sobe a mão em direção ao ombro sem trazer o cotovelo pra frente: o cabo alonga a cabeça longa do bíceps embaixo.",
    cam: { alvo: V3(-0.1, 1.05, 0), dist: 3.7, yaw: 28, pitch: 10 },
    cena(g) {
      g.add(tablado()); this.t = bTorre(g, V3(-0.95, 0.25, 0), V3(1, 0, 0), 0.25);
      this.al = K.estribo(); g.add(this.al); this.t.liga(V3(-0.3, 0.9, 0.2)); this.t.zeraCurso(); this.t.liga(V3(-0.3, 0.9, 0.2));
    },
    pose(t) {
      zera(); emPe(V3(0.0, ALT_QUADRIL - 0.03, 0), F0, 0.34); gira("spine_02", EX, 0.05); gira("neck_01", EX, -0.3); gira("head", EX, -0.1);
      B.pelvis.updateMatrixWorld(true); pernas(F0, { abre: 0.14, fora: 0.2, poloFora: 0.2 });
      const quem = this.p.lado === "l" ? "l" : "r", outra = quem === "l" ? "r" : "l", prog = 1 - t, E = esquerda(F0), s = bLado(quem), o = E.clone().multiplyScalar(s);
      const th = 0.6 - 0.35 * prog, u = bU(V3(-Math.sin(th), -Math.cos(th), 0).add(o.clone().multiplyScalar(0.03)));
      const r = bCurl(quem, { u, m: bOrt(F0, u), f: 0.12 + prog * 1.95, sup: 1, R: 0.016, o });
      bLivre(outra, bU(V3(0.03, -1, 0)), 0.15);
      const x = o.clone(), y = bOrt(this.t.saida().sub(r.O), x), z = x.clone().cross(y);
      this.al.position.copy(r.O); this.al.quaternion.setFromRotationMatrix(bBase(x, y, z)); this.al.updateMatrixWorld(true);
      this.t.liga(this.al.localToWorld(V3(0, 0.08, 0)));
    },
  },
});
// Rosca 21: 7 só da metade de baixo, 7 só da metade de cima, 7 completas (aqui 2 de cada pra demonstrar), barra reta.
MOLDES.bi_21 = Object.assign({}, MOLDES.bi_rosca, {
  nome: "Rosca 21",
  dica: "Três fases sem soltar a barra: 7 reps só da metade de baixo (do esticado até 90°), 7 só da metade de cima (de 90° até o topo) e 7 completas. Cotovelo colado o tempo todo; a carga é bem menor que na rosca normal.",
  fase(r) {
    const base = fase(r), k = Math.floor(r / CICLO) % 6 >> 1;
    const t = k === 0 ? 0.5 + 0.5 * base.t : k === 1 ? 0.5 * base.t : base.t;
    return { t, f: ["1ª fase · 7 reps só da metade de baixo", "2ª fase · 7 reps só da metade de cima", "3ª fase · 7 reps completas"][k], esforco: base.esforco };
  },
});
// EMG: Marcolin 2018 (PeerJ 5165: barra EZ >= reta > halter no bíceps e braquiorradial), Kleiber 2015 (Front Physiol: braquiorradial só muda na pronação),
// Oliveira 2009 (JSSM 8:24: rosca com halter chega a ~95% do RMS máximo na concêntrica). Os valores relativos entre músculos são estimativa em cima disso.
Object.assign(FOCOS, {
  bi_rosca: (p) => [["biceps", 1], ["braquial", 0.85], ["braquiorradial", p.w ? 0.65 : 0.55], ["antebraco", 0.4], ["deltoide_ant", 0.25]],
  bi_alternada: () => [["biceps", 1], ["braquial", 0.8], ["braquiorradial", 0.5], ["antebraco", 0.4], ["deltoide_ant", 0.2]],
  bi_cruzada: () => [["braquial", 1], ["braquiorradial", 0.95], ["biceps", 0.7], ["antebraco", 0.45], ["deltoide_ant", 0.35]], // neutra: estimativa (Kleiber 2015 + padrão do martelo do motor)
  bi_21: () => [["biceps", 1], ["braquial", 0.85], ["braquiorradial", 0.6], ["antebraco", 0.45], ["deltoide_ant", 0.3]],
  // ACE 2014 (Young, Porcari et al.): concentrada = maior ativação do bíceps de 8 exercícios; cabo em 2º; inclinada e Scott por último (braquiorradial menor); deltoide anterior menor na concentrada/inclinada
  bi_concentrada: () => [["biceps", 1], ["braquial", 0.8], ["braquiorradial", 0.5], ["antebraco", 0.35], ["deltoide_ant", 0.1]],
  // Oliveira 2009: Scott (halter) ativa alto só numa faixa curta de ângulo (~80% do RMS máx. vs 95% na rosca normal); braço apoiado = deltoide quase zero. Braquial relativo = estimativa
  bi_scott: (p) => [["biceps", 1], ["braquial", 0.9], ["braquiorradial", 0.45], ["antebraco", p.maquina ? 0.3 : 0.35], ["deltoide_ant", 0.08]],
  // Oliveira 2009: inclinada ~ rosca clássica (até ~95% do RMS); ACE 2014: braquiorradial menor que na barra EZ
  bi_inclinada: () => [["biceps", 1], ["braquial", 0.75], ["braquiorradial", 0.4], ["antebraco", 0.35], ["deltoide_ant", 0.1]],
  bi_spider: () => [["biceps", 1], ["braquial", 0.9], ["braquiorradial", 0.5], ["antebraco", 0.35], ["deltoide_ant", 0.08]], // sem EMG publicado: estimativa (análogo ao Scott)
  // ACE 2014: rosca no cabo ficou em 2º no bíceps; corda = pegada neutra (Kleiber 2015: braquiorradial não cai na neutra)
  bi_polia: (p) => p.corda ? [["braquiorradial", 1], ["braquial", 0.95], ["biceps", 0.8], ["antebraco", 0.45], ["deltoide_ant", 0.2]] : [["biceps", 1], ["braquial", 0.8], ["braquiorradial", 0.55], ["antebraco", 0.4], ["deltoide_ant", 0.25]],
  bi_bayesian: () => [["biceps", 1], ["braquial", 0.75], ["braquiorradial", 0.5], ["antebraco", 0.4], ["deltoide_ant", 0.15]], // sem EMG publicado: estimativa (ombro estendido alonga a cabeça longa)
});
Object.assign(VISTA, { bi_rosca: 62, bi_alternada: 70, bi_cruzada: 78, bi_21: 62, bi_concentrada: 122, bi_scott: 42, bi_inclinada: 50, bi_spider: 40, bi_polia: 12, bi_bayesian: 28 });
}

// ===== moldes/cardio.js =====
{ // moldes/cardio.js : panturrilha, cardio e funcional (prefixo pc_)
// ---------- ajudantes ----------
const rad = (g) => g * Math.PI / 180;
const cl = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const suave = (x) => { x = cl(x); return x * x * (3 - 2 * x); };
const FOOT_L = COMP.foot_l, BALLH = CAB.ball_l.y - CHAO_Y;                       // osso do pé (tornozelo -> bola) e altura da bola do pé
const A0 = Math.atan2(-DIR.foot_l.y, Math.hypot(DIR.foot_l.x, DIR.foot_l.z));   // queda natural do pé, ~28°
const BETA = Math.atan2(DIR.ball_l.y, Math.hypot(DIR.ball_l.x, DIR.ball_l.z));   // dedos ~7° acima da sola
const NZ = V3(0, 1, 0), lz = (l) => (l === "l" ? -1 : 1);                         // lado do personagem no eixo Z (esquerdo = -Z em pé de frente pra +X)
// sola = plano onde o pé está (t = direção da ponta do pé, n = normal pra cima da sola); alfa = queda do osso do pé em relação à sola
function sola(l, t, n, alfa = A0) {
  const h = n.clone().cross(t).normalize();
  mira("foot_" + l, t.clone().multiplyScalar(Math.cos(alfa)).addScaledVector(n, -Math.sin(alfa)), h, EX);
  mira("ball_" + l, t.clone().multiplyScalar(Math.cos(BETA)).addScaledVector(n, Math.sin(BETA)), h, EX);
}
// articulação do tornozelo quando a bola do pé está em S (ponto da sola sob a bola) e o pé fez ângulo alfa
const tornozeloDe = (S, t, n, alfa = A0) => S.clone().addScaledVector(n, BALLH + FOOT_L * Math.sin(alfa)).addScaledVector(t, -FOOT_L * Math.cos(alfa));
const rolo = (len, r, mat = M.estofado) => { const g = new THREE.Group(), m = K.cilU(r, mat, 24); m.scale.y = len; m.rotation.x = Math.PI / 2; g.add(m); return g; }; // eixo em Z
const discoZ = (r, e = 0.04) => { const a = anilha(r, e); a.rotation.x = Math.PI / 2; return a; };                                                              // anilha com eixo em Z
const ladoMeio = () => (ondeEsta("upperarm_l").add(ondeEsta("upperarm_r")).multiplyScalar(0.5));
const moveG = (o, x, y, z) => { o.position.set(x, y, z); return o; };
const preto = new THREE.MeshStandardMaterial({ color: 0x0d0e10, roughness: 0.8 });
const cinza = new THREE.MeshStandardMaterial({ color: 0x4a4f59, metalness: 0.5, roughness: 0.45 });
const laranja = new THREE.MeshStandardMaterial({ color: 0xd9622b, roughness: 0.5, metalness: 0.2 });
const parede = new THREE.MeshStandardMaterial({ color: 0x23262d, roughness: 0.9 });

// ================= PANTURRILHA =================
// Amplitude real: bola do pé fixa na beirada, calcanhar desce abaixo do degrau (t = 1) e sobe na ponta do pé (t = 0).
const ALFA_TOPO = A0 + rad(36), ALFA_BAIXO = A0 - rad(24);
const alfaPant = (t) => ALFA_TOPO + (ALFA_BAIXO - ALFA_TOPO) * t;
const PEL_DY = 0.935;      // da bola do tornozelo ao osso da pelve com joelho quase estendido
// pés + corpo em pé sobre a beirada (S = ponto da sola sob a bola); devolve os tornozelos
function pesPant(t, { xb = 0, yb = 0.13, zf = 0.13, fora = 0.14, uni = null, xp = null, incl = 0, polo = 1 }) {
  const al = alfaPant(t), tp = {}, ank = {};
  for (const l of ["l", "r"]) {
    tp[l] = girarY(F0, (l === "l" ? 1 : -1) * fora);
    ank[l] = tornozeloDe(V3(xb, yb, lz(l) * zf), tp[l], NZ, al);
  }
  const aY = uni ? ank[uni].y : (ank.l.y + ank.r.y) / 2;
  const pz = uni ? lz(uni) * (zf - 0.118) : 0;
  return { al, tp, ank, aY, pz, px: xp === null ? xb - 0.07 : xp };
}
function poePesPant(d, polo, solo) {
  for (const l of ["l", "r"]) { if (solo && l !== solo) continue; perna(l, d.ank[l], polo(l)); sola(l, d.tp[l], NZ, d.al); }
}

Object.assign(MOLDES, {
  // ---------- em pé na máquina (ombreiras) ----------
  pc_pant_pe: {
    nome: "Panturrilha em pé na máquina",
    musc: { panturrilha: 1 },
    dica: "Ombros sob as almofadas, joelhos quase estendidos e travados. Ponta do pé na beirada, calcanhar desce abaixo do degrau até alongar a panturrilha e sobe o mais alto que der, segurando um instante no topo.",
    cam: { alvo: V3(0.05, 0.85, 0), dist: 5.0, yaw: 238, pitch: 9 },
    cena(g) {
      g.add(moveG(K.caixa(1.35, 0.03, 0.95, M.quadro, 0.01), 0.22, 0.015, 0));
      g.add(moveG(K.caixa(0.34, 0.10, 0.62, M.borracha, 0.02), 0.16, 0.08, 0));
      g.add(moveG(K.caixa(0.14, 2.1, 0.58, M.quadro, 0.015), 0.66, 1.05, 0));
      const pil = K.pilha(); pil.position.set(0.84, 0.03, 0); g.add(pil); this.pilha = pil;
      const car = new THREE.Group(); g.add(car); this.car = car;               // origem = altura do centro das ombreiras
      car.add(moveG(K.caixa(0.12, 0.42, 0.46, M.quadro, 0.015), 0.52, 0.12, 0));
      for (const z of [-0.2, 0.2]) g.add(K.tubo(V3(0.585, 0.1, z), V3(0.585, 2.05, z), 0.012, M.cromo)); // trilhos do carro
      for (const z of [-0.27, 0.27]) {
        car.add(K.viga(V3(0.54, 0.16, z), V3(0.0, 0.16, z), 0.05));
        car.add(K.tubo(V3(-0.07, 0.16, z), V3(-0.07, 0.0, z * 0.5), 0.016, M.cromo));              // haste que desce até a almofada
        car.add(moveG(K.caixa(0.30, 0.085, 0.17, M.estofado, 0.035), -0.07, 0, z * 0.5));
        car.add(K.tubo(V3(0.30, 0.16, z), V3(0.30, -0.50, z), 0.014, M.cromo));                    // pega
        car.add(K.tubo(V3(0.30, -0.50, z), V3(0.04, -0.50, z), 0.014, M.cromo));
        car.add(K.tubo(V3(0.26, -0.50, z), V3(0.04, -0.50, z), 0.019, M.borracha));
      }
      sombreia(car);
    },
    pose(t) {
      zera();
      const d = pesPant(t, { yb: 0.13, xb: 0.015 });
      emPe(V3(d.px, d.aY + PEL_DY, 0), F0, 0);
      B.pelvis.updateMatrixWorld(true);
      poePesPant(d, () => V3(1, 0.1, 0));
      const sh = ladoMeio(), yp = sh.y + 0.105;
      this.car.position.y = yp;
      this.pilha.userData.sobe(yp - (ALT_QUADRIL + 0.49 + 0.105 - 0.0));
      for (const l of ["l", "r"]) {
        const z = lz(l);
        agarra(l, { ponto: V3(0.15, yp - 0.50, z * 0.27), eixo: F0.clone(), palma: V3(0, 0, -z), R: 0.019, polo: V3(-1, 0, z * 0.4) });
      }
    },
  },
});
// pé solto no ar: ponta pra baixo g rad em relação ao chão
function peSolto(l, F, g) {
  const t = F.clone().multiplyScalar(Math.cos(g)).addScaledVector(NZ, -Math.sin(g)), n = NZ.clone().multiplyScalar(Math.cos(g)).addScaledVector(F, Math.sin(g));
  sola(l, t, n, A0);
}
const ESQ = (l) => V3(0, 0, lz(l));
Object.assign(MOLDES, {
  // ---------- sentado (almofada na coxa) ----------
  pc_pant_sentado: {
    nome: "Panturrilha sentado",
    musc: { panturrilha: 0.6 },
    dica: "Almofada sobre as coxas, joelhos a 90°. Calcanhar desce abaixo da plataforma até alongar e sobe na ponta do pé. Com o joelho dobrado o gastrocnêmio fica encurtado: quem segura a carga é o sóleo, por baixo dele.",
    cam: { alvo: V3(0.3, 0.55, 0), dist: 4.6, yaw: 236, pitch: 10 },
    cena(g) {
      g.add(moveG(K.caixa(1.5, 0.04, 0.78, M.quadro, 0.01), 0.35, 0.02, 0));
      g.add(moveG(K.assento(0.46, 0.44, 0.09), -0.14, 0.455, 0));
      g.add(K.viga(V3(-0.20, 0.04, 0), V3(-0.20, 0.41, 0), 0.08));
      g.add(moveG(K.caixa(0.34, 0.15, 0.62, M.borracha, 0.02), 0.585, 0.115, 0));
      g.add(moveG(K.caixa(0.14, 1.35, 0.52, M.quadro, 0.015), 0.92, 0.715, 0));
      const pil = K.pilha(); pil.position.set(1.1, 0.04, 0); g.add(pil); this.pilha = pil;
      this.pad = moveG(rolo(0.46, 0.056), 0, 0, 0); this.arms = [-1, 1].map(() => K.cilU(0.022, M.quadro)); this.grips = [-1, 1].map(() => K.cilU(0.0155, M.borracha));
      g.add(this.pad, ...this.arms, ...this.grips);
      for (const z of [-0.23, 0.23]) { g.add(moveG(K.caixa(0.08, 0.1, 0.06, M.aco, 0.01), 0.86, 0.9, z)); }
    },
    pose(t) {
      zera();
      const d = pesPant(t, { yb: 0.19, xb: 0.43 });
      emPe(V3(-0.20, 0.616, 0), F0, 0);
      B.pelvis.updateMatrixWorld(true);
      poePesPant(d, (l) => V3(0.35, 1, lz(l) * 0.15));
      // almofada na coxa e braço da alavanca
      const quad = ondeEsta("thigh_l").add(ondeEsta("thigh_r")).multiplyScalar(0.5), dir = dirMundo("thigh_l");
      const up = V3(-dir.y, dir.x, 0).normalize(), pp = quad.clone().addScaledVector(dir, 0.40).addScaledVector(up, 0.135);
      this.pad.position.copy(pp);
      const piv = V3(0.86, 0.92, 0);
      for (const l of ["l", "r"]) {
        const z = lz(l), i = l === "l" ? 0 : 1, a = V3(pp.x, pp.y + 0.0, z * 0.23), dv = piv.clone().add(V3(0, 0, z * 0.23)).sub(a).normalize();
        K.poe(this.arms[i], a.clone().addScaledVector(dv, -0.30), piv.clone().add(V3(0, 0, z * 0.23)));
        const g0 = a.clone().addScaledVector(dv, -0.17);
        K.poe(this.grips[i], g0.clone().addScaledVector(dv, -0.07), g0.clone().addScaledVector(dv, 0.07));
        agarra(l, { ponto: g0, eixo: dv.clone(), palma: V3(0, 0, -z), R: 0.0185, polo: V3(-1, -0.3, z * 0.5) });
      }
      this.pilha.userData.sobe((pp.y - 0.74) * 1.0);
    },
  },
  // ---------- no leg press 45° ----------
  pc_pant_legpress: {
    nome: "Panturrilha no leg press",
    musc: { panturrilha: 1 },
    dica: "Só a ponta dos pés na beirada da plataforma, joelhos estendidos e quase travados (nunca bloqueie com força). Deixa o calcanhar descer e empurra a plataforma só com o tornozelo, sem mexer o joelho.",
    cam: { alvo: V3(0.45, 0.82, 0), dist: 4.5, yaw: 24, pitch: 8 },
    cena(g) {
      const f = rad(50), c = V3(-Math.cos(f), Math.sin(f), 0), fr = V3(Math.sin(f), Math.cos(f), 0), P = V3(-0.30, 0.50, 0);
      this.O = P.clone().addScaledVector(c, -0.026); this.c = c; this.fr = fr; this.P = P;
      const r = V3(Math.SQRT1_2, Math.SQRT1_2, 0), tt = V3(-Math.SQRT1_2, Math.SQRT1_2, 0);
      const at = (u, w, z = 0) => this.O.clone().addScaledVector(r, u).addScaledVector(tt, w).add(V3(0, 0, z));
      const encosto = K.caixa(0.72, 0.085, 0.46, M.estofado, 0.035); encosto.position.copy(P.clone().addScaledVector(c, 0.30).addScaledVector(fr, -0.16)); encosto.rotation.z = Math.PI - f; g.add(encosto);
      const assento = K.caixa(0.46, 0.085, 0.46, M.estofado, 0.035); assento.position.copy(P.clone().addScaledVector(fr, -0.14).add(V3(0.12, -0.02, 0))); assento.rotation.z = rad(12); g.add(assento);
      for (const z of [-0.30, 0.30]) {
        g.add(K.tubo(at(-0.35, -0.40, z), at(1.55, -0.40, z), 0.034, M.quadro));                    // trilhos a 45°
        g.add(K.viga(at(-0.35, -0.40, z), V3(at(-0.35, -0.40, z).x, 0.02, z), 0.07));
        g.add(K.viga(at(1.55, -0.40, z), V3(at(1.55, -0.40, z).x, 0.02, z), 0.07));
        g.add(K.viga(at(0.70, -0.40, z), V3(at(0.70, -0.40, z).x, 0.02, z), 0.06));
        g.add(K.viga(V3(-0.02, 0.05, z * 0.93), V3(-0.02, 0.62, z * 0.93), 0.05)); g.add(K.tubo(V3(-0.02, 0.62, z * 0.93), V3(-0.30, 0.62, z * 0.93), 0.017, M.cromo)); // pegas laterais
      }
      g.add(moveG(K.caixa(1.0, 0.05, 0.9, M.quadro, 0.01), 0.5, 0.025, 0));
      g.add(K.viga(P.clone().addScaledVector(fr, -0.30).add(V3(0, 0, 0.0)), V3(P.x - 0.55, 0.05, 0), 0.09));
      g.add(K.viga(P.clone().addScaledVector(c, 0.55).addScaledVector(fr, -0.30), V3(P.x - 0.55, 0.05, 0), 0.09));
      const sled = new THREE.Group(); sled.rotation.z = rad(45); g.add(sled); this.sled = sled;
      sled.add(moveG(K.caixa(0.05, 0.78, 0.66, M.quadro, 0.012), 0.025, 0.36, 0));
      sled.add(moveG(K.caixa(0.012, 0.62, 0.5, M.borracha, 0.004), -0.004, 0.40, 0));
      for (const z of [-0.30, 0.30]) { sled.add(K.viga(V3(0.03, 0.0, z), V3(0.03, -0.40, z), 0.06)); }
      for (const z of [-0.36, 0.36]) { sled.add(K.tubo(V3(0.05, 0.36, z), V3(0.36, 0.36, z), 0.025, M.cromo)); for (let i = 0; i < 3; i++) { const a = anilha(0.17, 0.045); a.rotation.z = Math.PI / 2; a.position.set(0.1 + i * 0.05, 0.36, z); sled.add(a); } }
      sombreia(sled);
    },
    pose(t) {
      zera();
      const f = rad(50), c = this.c, fr = this.fr, P = this.P, r = V3(Math.SQRT1_2, Math.SQRT1_2, 0), tt = V3(-Math.SQRT1_2, Math.SQRT1_2, 0), nn = r.clone().negate();
      corpoEm(P, c, fr);
      gira("spine_02", EX, 0.05); gira("neck_01", EX, 0.50); gira("head", EX, 0.12);
      B.pelvis.updateMatrixWorld(true);
      const al = alfaPant(t), O = this.O, wb = 0.10;
      const ankle = {}, ts = {};
      const aw = wb - FOOT_L * Math.cos(al), au = Math.sqrt(0.90 * 0.90 - aw * aw), p = au + BALLH + FOOT_L * Math.sin(al);
      for (const l of ["l", "r"]) { ts[l] = tt.clone().applyAxisAngle(r, 0); ankle[l] = O.clone().addScaledVector(r, au).addScaledVector(tt, aw).add(V3(0, 0, lz(l) * 0.14)); }
      this.sled.position.copy(O).addScaledVector(r, p);
      for (const l of ["l", "r"]) { perna(l, ankle[l], tt.clone().add(V3(0, 0, lz(l) * 0.3))); sola(l, tt, nn, al); }
      for (const l of ["l", "r"]) {
        const z = lz(l);
        agarra(l, { ponto: V3(-0.15, 0.62, z * 0.28), eixo: F0.clone(), palma: V3(0, 0, -z), R: 0.016, polo: V3(-0.2, -1, z * 0.5) });
      }
    },
  },
});
Object.assign(MOLDES, {
  // ---------- no Smith (barra nas costas, bloco sob a ponta do pé) ----------
  pc_pant_smith: {
    nome: "Panturrilha no Smith",
    musc: { panturrilha: 1 },
    dica: "Barra do Smith apoiada no trapézio, pega um pouco mais aberta que os ombros, ponta dos pés num bloco. Sobe o mais alto que der, segura um instante, e desce até o calcanhar passar da altura do bloco.",
    cam: { alvo: V3(0.0, 0.95, 0), dist: 5.6, yaw: 238, pitch: 9 },
    cena(g) {
      this.sm = K.smith({ alt: 2.15, larg: 1.25 }); g.add(this.sm.g);
      g.add(moveG(K.caixa(0.34, 0.10, 0.70, M.borracha, 0.02), 0.16, 0.05, 0));
      g.add(moveG(K.caixa(1.1, 0.02, 1.2, M.borracha, 0.006), 0.1, 0.01, 0));
    },
    pose(t) {
      zera();
      const d = pesPant(t, { yb: 0.10, xb: 0.015 });
      emPe(V3(d.px, d.aY + PEL_DY, 0), F0, 0);
      B.pelvis.updateMatrixWorld(true);
      poePesPant(d, () => V3(1, 0.1, 0));
      const c = quadroDe("spine_03"), pescoco = ondeEsta("neck_01");
      const bar = pescoco.clone().add(c.fr.clone().multiplyScalar(-0.1)).add(c.up.clone().multiplyScalar(-0.085));
      this.sm.g.position.x = bar.x; this.sm.barra.position.y = bar.y;
      for (const l of ["l", "r"]) {
        const s = l === "l" ? 1 : -1;
        agarra(l, { ponto: bar.clone().add(c.esq.clone().multiplyScalar(s * 0.40)), eixo: c.esq.clone().multiplyScalar(-s), palma: c.up.clone().add(c.fr.clone().multiplyScalar(0.9)),
          polo: c.up.clone().multiplyScalar(-1).add(c.fr.clone().multiplyScalar(-0.6)).add(c.esq.clone().multiplyScalar(s * 0.3)) });
      }
    },
  },
  // ---------- no degrau (peso do corpo) e unilateral com halter ----------
  pc_pant_degrau: {
    nome: "Panturrilha no degrau",
    musc: { panturrilha: 1 },
    dica: "Ponta dos pés na beirada do degrau, mão leve num apoio só pra equilíbrio. Desce o calcanhar abaixo do degrau e sobe na ponta, devagar, sem balançar o joelho.",
    cam: { alvo: V3(0.05, 0.9, 0), dist: 4.5, yaw: 240, pitch: 9 },
    cena(g) {
      g.add(moveG(K.caixa(0.40, 0.15, 0.80, new THREE.MeshStandardMaterial({ color: 0x5d6470, roughness: 0.6 }), 0.025), 0.19, 0.075, 0));
      g.add(moveG(K.caixa(1.3, 0.02, 1.2, M.borracha, 0.006), 0.1, 0.01, 0));
      for (const z of [-0.33, 0.33]) {                                         // apoios laterais (corrimão)
        g.add(K.viga(V3(0.40, 0.02, z), V3(0.40, 1.32, z), 0.05)); g.add(K.viga(V3(-0.15, 0.02, z), V3(-0.15, 1.32, z), 0.05));
        g.add(K.tubo(V3(-0.15, 1.30, z), V3(0.40, 1.30, z), 0.019, M.cromo));
      }
      if (this.p.halter) { this.h = halter(1.0); g.add(this.h); }
    },
    pose(t) {
      zera();
      const uni = this.p.uni ? "r" : null, yb = 0.15;
      const d = pesPant(t, { yb, xb: 0.025, uni, xp: -0.05 });
      emPe(V3(d.px, d.aY + PEL_DY, d.pz), F0, 0);
      B.pelvis.updateMatrixWorld(true);
      poePesPant(d, () => V3(1, 0.1, 0), uni);
      if (uni) {                                                               // perna de trás dobrada, pé solto (não encosta em nada)
        const pe0 = ondeEsta("thigh_l");
        perna("l", V3(d.px - 0.34, yb + 0.30 + 0.5 * (d.aY - (yb + 0.0798)), pe0.z + 0.06), V3(1, 0.2, -0.3));
        peSolto("l", F0, rad(40));
      }
      for (const l of ["l", "r"]) {
        const z = lz(l);
        if (this.h && l === "r") { agarra(l, { punho: ondeEsta("upperarm_r").add(V3(0.0, -(COMP.upperarm_l + COMP.lowerarm_l) * 0.97, 0.02)), eixo: F0.clone(), palma: V3(0, 0, -z), R: 0.016, polo: V3(-1, 0, 0.3) }); seguraHalter(this.h, l); continue; }
        agarra(l, { ponto: V3(0.12, 1.30, z * 0.33), eixo: F0.clone(), palma: V3(0, 0, -z), R: 0.019, polo: V3(-1, -0.4, z * 0.5) });
      }
    },
  },
  // ---------- burrinho (quadril na almofada, mãos no apoio) ----------
  pc_burrinho: {
    nome: "Panturrilha burrinho",
    musc: { panturrilha: 1 },
    dica: "Tronco paralelo ao chão, mãos firmes no apoio, almofada sobre a lombar/quadril. Joelhos estendidos, calcanhar desce abaixo do degrau e sobe na ponta do pé, com pausa no topo.",
    cam: { alvo: V3(0.05, 0.75, 0), dist: 5.0, yaw: 232, pitch: 10 },
    cena(g) {
      g.add(moveG(K.caixa(2.0, 0.03, 0.9, M.quadro, 0.01), 0.1, 0.015, 0));
      g.add(moveG(K.caixa(0.34, 0.10, 0.62, M.borracha, 0.02), 0.17, 0.08, 0));
      for (const z of [-0.36, 0.36]) g.add(K.viga(V3(1.05, 0.03, z), V3(1.05, 1.12, z), 0.06));
      g.add(K.tubo(V3(1.05, 1.1, -0.36), V3(1.05, 1.1, 0.36), 0.02, M.cromo));
      g.add(moveG(K.caixa(0.16, 1.5, 0.6, M.quadro, 0.015), -0.85, 0.78, 0));
      this.pad = rolo(0.38, 0.075); g.add(this.pad); this.arm = K.cilU(0.03, M.quadro); g.add(this.arm);
      this.pl = new THREE.Group(); g.add(this.pl);
      const horn = K.tubo(V3(0, 0, -0.34), V3(0, 0, 0.34), 0.026, M.cromo); this.pl.add(horn);
      for (const z of [-0.2, 0.2, -0.26, 0.26]) { const a = discoZ(0.225, 0.045); a.position.z = z; this.pl.add(a); }
      sombreia(this.pl);
    },
    pose(t) {
      zera();
      const d = pesPant(t, { yb: 0.13, xb: 0.015, xp: -0.04 });
      const incl = 1.50;
      emPe(V3(d.px, d.aY + PEL_DY, 0), F0, incl);
      gira("spine_03", EX, -0.04); gira("neck_01", EX, -0.30); gira("head", EX, -0.1);
      B.pelvis.updateMatrixWorld(true);
      poePesPant(d, () => V3(1, 0.1, 0));
      const qd = quadroDe("pelvis"), pv = ondeEsta("pelvis");
      const costa = pv.clone().addScaledVector(qd.fr, -0.125).addScaledVector(qd.up, -0.09);
      this.pad.position.copy(costa);
      const piv = V3(-0.85, 1.0, 0), dd = costa.clone().sub(piv).normalize();
      K.poe(this.arm, piv.clone().addScaledVector(dd, -0.45), costa.clone().addScaledVector(dd, -0.04));
      this.pl.position.copy(piv.clone().addScaledVector(dd, -0.45));
      for (const l of ["l", "r"]) {
        const z = lz(l);
        agarra(l, { ponto: V3(1.05, 1.1, z * 0.20), eixo: V3(0, 0, 1), palma: V3(0, -1, 0), R: 0.02, polo: V3(0, 0, z * 1) });
      }
    },
  },
  // ---------- elevação de ponta de pé (tibial anterior), costas na parede ----------
  pc_tibial: {
    nome: "Elevação de ponta de pé (tibial)",
    musc: { panturrilha: 0.2 },
    dica: "Costas na parede, pés a uns 30 cm à frente, calcanhares no chão. Levanta só a ponta dos pés o mais alto que der, segura um instante e desce devagar até a ponta tocar o chão.",
    cam: { alvo: V3(0.12, 0.62, 0), dist: 4.4, yaw: 60, pitch: 8 },
    cena(g) {
      g.add(moveG(K.caixa(0.08, 2.4, 1.8, parede, 0.01), -0.215, 1.2, 0));
      g.add(moveG(K.caixa(2.0, 0.02, 1.8, M.borracha, 0.006), 0.3, 0.01, 0));
      g.add(moveG(K.caixa(0.02, 1.1, 0.5, M.estofado, 0.008), -0.165, 1.15, 0));
    },
    pose(t) {
      zera();
      const th = rad(30) * (1 - t);                                            // ponta do pé acima do chão (t = 0 contraído)
      const px = -0.035, py = 0.93;
      emPe(V3(px, py, 0), F0, 0);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) {
        const f = girarY(F0, (l === "l" ? 1 : -1) * 0.2);
        const ts = f.clone().multiplyScalar(Math.cos(th)).addScaledVector(NZ, Math.sin(th)), ns = NZ.clone().multiplyScalar(Math.cos(th)).addScaledVector(f, -Math.sin(th));
        const heel = V3(0.27 - 0.06, 0, lz(l) * 0.13);                         // calcanhar parado no chão
        const a = heel.clone().addScaledVector(ts, 0.06).addScaledVector(ns, ALT_TORN);
        perna(l, a, V3(1, 0.1, 0)); sola(l, ts, ns, A0);
      }
      for (const l of ["l", "r"]) {
        const z = lz(l);
        const sh = ondeEsta("upperarm_" + l);
        agarra(l, { punho: sh.clone().add(V3(0.0, -(COMP.upperarm_l + COMP.lowerarm_l) * 0.96, z * 0.05)), eixo: F0.clone(), palma: V3(0, 0, -z), R: 0.012, polo: V3(-1, 0, z * 0.3) });
      }
    },
  },
});
// ================= CARDIO (movimento cíclico: t = fase 0..1 do ciclo, sem pausa de série) =================
const ciclo = (seg, f, esf = 0.7) => function (r) { return { t: (r / seg) % 1, f, esforco: esf }; };
const mod = (a, b) => ((a % b) + b) % b;
// braço solto balançando: ang = ângulo do braço pra frente (rad), flex = dobra do cotovelo (rad); mão fechada
function bracoSwing(l, ang, flex, polo) {
  const S = ondeEsta("upperarm_" + l), z = lz(l), u = V3(Math.sin(ang), -Math.cos(ang), 0), a2 = ang + flex, f = V3(Math.sin(a2), -Math.cos(a2), 0);
  const E = S.clone().addScaledVector(u, COMP.upperarm_l).add(V3(0, 0, z * 0.02));
  const H = E.clone().addScaledVector(f, COMP.lowerarm_l + 0.05).add(V3(0, 0, -z * 0.03));
  braco(l, H, polo || V3(-1, -0.2, z * 0.5)); fecha(l, 0.85);
}
Object.assign(MOLDES, {
  // ---------- esteira: corrida leve, a esteira corre sob os pés ----------
  pc_esteira: {
    nome: "Esteira",
    musc: { quadriceps: 0.8, gluteo: 0.7, panturrilha: 0.8, posterior: 0.6 },
    dica: "Tronco levemente inclinado, passada curta caindo sob o quadril, braços dobrados a 90° balançando junto. Olha pra frente e não segura no corrimão.",
    cam: { alvo: V3(0, 1.0, 0), dist: 5.0, yaw: 20, pitch: 8 },
    fase: ciclo(0.75, "corrida leve, 160 passos/min", 0.7),
    cena(g) {
      const deck = 0.15; g.add(moveG(K.caixa(1.9, 0.12, 0.66, M.quadro, 0.02), -0.05, 0.09, 0));
      const top = moveG(K.caixa(1.74, 0.012, 0.52, preto, 0.004), -0.05, deck - 0.006, 0); g.add(top);
      for (const z of [-0.34, 0.34]) g.add(moveG(K.caixa(1.9, 0.04, 0.08, M.borracha, 0.01), -0.05, 0.16, z));
      this.rip = [...Array(12)].map(() => { const m = K.caixa(0.018, 0.004, 0.52, new THREE.MeshStandardMaterial({ color: 0x6b7280, roughness: 0.7 }), 0.001); m.position.y = deck + 0.001; g.add(m); return m; });
      for (const z of [-0.36, 0.36]) { g.add(K.viga(V3(0.82, 0.12, z), V3(0.74, 1.18, z), 0.055)); g.add(K.tubo(V3(0.74, 1.05, z), V3(0.20, 1.0, z), 0.018, M.cromo)); }
      const con = K.caixa(0.14, 0.26, 0.78, M.quadro, 0.02); con.position.set(0.72, 1.24, 0); con.rotation.z = rad(-18); g.add(con);
      g.add(moveG(K.caixa(0.02, 0.2, 0.5, new THREE.MeshStandardMaterial({ color: 0x0b2a3a, emissive: 0x0a4a66, roughness: 0.3 }), 0.004), 0.645, 1.255, 0)); g.children[g.children.length - 1].rotation.z = rad(-18);
      sombreia(g);
    },
    pose(t) {
      zera();
      const s = 0.4, L = 0.5, xf = 0.2, deck = 0.15;
      emPe(V3(0.0, deck + ALT_QUADRIL - 0.075 - 0.035 * Math.cos(4 * Math.PI * (t - 0.2)), 0), F0, 0.13);
      gira("neck_01", EX, -0.1);
      B.pelvis.updateMatrixWorld(true);
      const alvo = (l) => {
        const p = mod(t + (l === "r" ? 0.5 : 0), 1), z = lz(l) * 0.1, f = girarY(F0, lz(l) * -0.05);
        const est = (u, extra = 0) => { const al = A0 + rad(36) * suave((u - 0.6) / 0.4); return { al, a: tornozeloDe(V3(xf + 0.136 - L * u, deck, z), f, NZ, al) }; };
        if (p < s) { const e = est(p / s); return { a: e.a, al: e.al, f }; }
        const v = (p - s) / (1 - s), e1 = est(1), e0 = est(0), k = suave(v);
        const a = e1.a.clone().lerp(e0.a, k); a.y += 0.30 * Math.pow(Math.sin(Math.PI * Math.min(1, v * 1.05)), 1.1) * (1 - 0.25 * v);
        return { a, al: lerp(e1.al, A0 - rad(8), suave(v * 1.2)), f };
      };
      for (const l of ["l", "r"]) { const o = alvo(l); perna(l, o.a, V3(1, 0.25, lz(l) * 0.05)); sola(l, o.f, NZ, o.al); }
      const sw = 0.62 * Math.cos(2 * Math.PI * t);
      bracoSwing("l", -sw, 1.45); bracoSwing("r", sw, 1.45);
      const k = t * 1.25;
      this.rip.forEach((m, i) => { m.position.x = -0.9 + mod(i * 0.125 - k, 1.5) + 0.0; });
    },
  },
  // ---------- bicicleta ergométrica vertical ----------
  pc_bike: {
    nome: "Bicicleta ergométrica",
    musc: { quadriceps: 1, gluteo: 0.7, posterior: 0.5, panturrilha: 0.5 },
    dica: "Banco na altura do quadril, joelho quase estendido embaixo. Pedala em círculo redondo, tronco levemente inclinado, mãos soltas no guidão e ombros relaxados.",
    cam: { alvo: V3(0.05, 0.75, 0), dist: 4.6, yaw: 25, pitch: 8 },
    fase: ciclo(0.75, "pedalada 80 rpm", 0.65),
    cena(g) {
      g.add(moveG(K.caixa(0.1, 0.05, 0.7, M.quadro, 0.015), 0.55, 0.025, 0)); g.add(moveG(K.caixa(0.1, 0.05, 0.7, M.quadro, 0.015), -0.5, 0.025, 0));
      g.add(K.viga(V3(-0.5, 0.05, 0), V3(0.55, 0.05, 0), 0.07));
      g.add(K.viga(V3(0.55, 0.05, 0), V3(0.40, 1.12, 0), 0.07));                     // coluna do guidão
      g.add(K.viga(V3(-0.5, 0.05, 0), V3(-0.14, 0.93, 0), 0.06));                    // canote do banco
      g.add(K.viga(V3(0.02, 0.33, 0), V3(-0.14, 0.9, 0), 0.05));
      const vol = K.cilU(0.21, M.quadro, 40); vol.scale.y = 0.1; vol.rotation.x = Math.PI / 2; vol.position.set(0.29, 0.33, 0); g.add(vol);
      const cub = K.cilU(0.12, M.aco, 32); cub.scale.y = 0.12; cub.rotation.x = Math.PI / 2; cub.position.set(0.29, 0.33, 0); g.add(cub);
      const eixo = K.cilU(0.022, M.cromo); eixo.scale.y = 0.3; eixo.rotation.x = Math.PI / 2; eixo.position.set(0, 0.33, 0); g.add(eixo);
      g.add(K.viga(V3(0.02, 0.33, 0), V3(0.29, 0.33, 0), 0.08));
      const ban = K.caixa(0.15, 0.07, 0.19, M.estofado, 0.03); ban.position.set(-0.17, 0.97, 0); g.add(ban);
      const nar = K.caixa(0.14, 0.055, 0.08, M.estofado, 0.02); nar.position.set(-0.02, 0.97, 0); g.add(nar);
      g.add(K.tubo(V3(0.40, 1.12, -0.22), V3(0.40, 1.12, 0.22), 0.016, M.cromo));
      for (const z of [-0.2, 0.2]) { const gr = K.cilU(0.019, M.borracha); gr.scale.y = 0.13; gr.rotation.z = Math.PI / 2; gr.position.set(0.40, 1.12, z); g.add(gr); }
      const con = K.caixa(0.05, 0.14, 0.2, M.quadro, 0.01); con.position.set(0.44, 1.22, 0); con.rotation.z = rad(-20); g.add(con);
      this.cr = [-1, 1].map(() => K.cilU(0.013, M.aco)); this.pd = [-1, 1].map(() => K.caixa(0.11, 0.025, 0.09, M.borracha, 0.008));
      g.add(...this.cr, ...this.pd); sombreia(g);
    },
    pose(t) {
      zera();
      const th = 2 * Math.PI * t, BB = V3(0, 0.33, 0);
      emPe(V3(-0.11, 1.095, 0), F0, 0.5);
      gira("spine_01", EX, 0.1); gira("neck_01", EX, -0.45); gira("head", EX, -0.15);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) {
        const z = lz(l), a = th + (l === "r" ? 0 : Math.PI), pd = V3(0.17 * Math.sin(a), 0.33 + 0.17 * Math.cos(a), z * 0.115);
        const i = l === "l" ? 0 : 1;
        K.poe(this.cr[i], V3(0, 0.33, z * 0.115), pd); this.pd[i].position.copy(pd).add(V3(0.0, 0.0, z * 0.0));
        const S = pd.clone().add(V3(0, 0.0125, 0)), al = A0 + 0.1 * Math.cos(a);
        perna(l, tornozeloDe(S, F0, NZ, al), V3(1, 0.1, z * 0.12)); sola(l, F0, NZ, al);
      }
      for (const l of ["l", "r"]) { const z = lz(l); agarra(l, { ponto: V3(0.40, 1.12, z * 0.2), eixo: V3(0, 0, 1), palma: V3(0.3, -1, 0), R: 0.019, polo: V3(-0.3, -1, z * 0.5) }); }
    },
  },
  // ---------- elíptico: pedais ligados a manivela e roldana, braços acompanham ----------
  pc_eliptico: {
    nome: "Elíptico",
    musc: { quadriceps: 0.8, gluteo: 0.8, posterior: 0.6, panturrilha: 0.5 },
    dica: "Pisa no pedal inteiro, tronco ereto e olhando à frente. Empurra o pedal pra trás e sobe com o outro, os braços puxam e empurram os cabos sem apoiar o peso neles.",
    cam: { alvo: V3(0.1, 1.0, 0), dist: 5.0, yaw: 25, pitch: 8 },
    fase: ciclo(1.1, "elíptico 55 rpm", 0.65),
    cena(g) {
      g.add(moveG(K.caixa(0.1, 0.05, 0.8, M.quadro, 0.015), 0.75, 0.025, 0)); g.add(moveG(K.caixa(0.1, 0.05, 0.8, M.quadro, 0.015), -0.62, 0.025, 0));
      g.add(K.viga(V3(-0.62, 0.05, 0), V3(0.75, 0.05, 0), 0.07));
      g.add(moveG(K.caixa(0.5, 0.42, 0.3, M.quadro, 0.04), 0.58, 0.31, 0));      // carcaça frontal
      g.add(K.viga(V3(0.75, 0.3, 0), V3(0.45, 1.9, 0), 0.08));                     // mastro
      const con = K.caixa(0.08, 0.26, 0.4, M.quadro, 0.02); con.position.set(0.43, 1.9, 0); con.rotation.z = rad(-12); g.add(con);
      g.add(moveG(K.caixa(0.12, 0.05, 0.62, M.quadro, 0.015), 0.27, 1.62, 0));
      const mc = K.cilU(0.03, M.cromo); mc.scale.y = 0.4; mc.rotation.x = Math.PI / 2; mc.position.set(0.55, 0.33, 0); g.add(mc);
      this.bie = [-1, 1].map(() => K.cilU(0.022, M.aco)); this.plt = [-1, 1].map(() => K.caixa(0.34, 0.045, 0.14, M.borracha, 0.012));
      this.rol = [-1, 1].map(() => { const r = K.cilU(0.04, M.quadro); r.scale.y = 0.09; r.rotation.x = Math.PI / 2; return r; });
      this.trilho = K.cilU(0.012, M.cromo); this.trilho.scale.y = 1.0; this.trilho.rotation.z = Math.PI / 2; this.trilho.position.set(-0.28, 0.1, 0); g.add(this.trilho);
      this.mao = [-1, 1].map(() => K.cilU(0.022, M.quadro)); this.pega = [-1, 1].map(() => K.cilU(0.0185, M.borracha));
      g.add(...this.bie, ...this.plt, ...this.rol, ...this.mao, ...this.pega); sombreia(g);
    },
    pose(t) {
      zera();
      const th = 2 * Math.PI * t, Cc = V3(0.55, 0.33, 0), Lr = 0.95, P = V3(0.36, 1.82, 0), Lh = 0.46;
      emPe(V3(-0.03, 1.2, 0), F0, 0.08);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) {
        const z = lz(l), i = l === "l" ? 0 : 1, a = th + (l === "r" ? 0 : Math.PI), zz = z * 0.12;
        const K0 = V3(Cc.x + 0.2 * Math.sin(a), Cc.y + 0.2 * Math.cos(a), zz), Rx = K0.x - Math.sqrt(Lr * Lr - (K0.y - 0.1) ** 2), R0 = V3(Rx, 0.1, zz);
        K.poe(this.bie[i], K0, R0); this.rol[i].position.copy(R0);
        const tt = K0.clone().sub(R0).normalize(), nn = V3(-tt.y, tt.x, 0), F = K0.clone().lerp(R0, 0.62).addScaledVector(nn, 0.0225);
        this.plt[i].position.copy(F); this.plt[i].quaternion.setFromUnitVectors(EX, tt);
        perna(l, tornozeloDe(F.clone().addScaledVector(tt, 0.1).addScaledVector(nn, 0.0225), tt, nn, A0), V3(1, 0.2, z * 0.1)); sola(l, tt, nn, A0);
        const psi = -0.36 * Math.sin(a), dh = V3(Math.sin(psi), -Math.cos(psi), 0), Pz = V3(P.x, P.y, z * 0.3), G = Pz.clone().addScaledVector(dh, Lh);
        K.poe(this.mao[i], Pz, G.clone().addScaledVector(dh, -0.1)); K.poe(this.pega[i], G.clone().addScaledVector(dh, -0.075), G.clone().addScaledVector(dh, 0.075));
        agarra(l, { ponto: G, eixo: dh.clone(), palma: V3(0, 0, -z), R: 0.0185, polo: V3(-1, -0.6, z * 0.5) });
      }
    },
  },
});
Object.assign(MOLDES, {
  // ---------- remo ergômetro: pernas, tronco, braços; volta na ordem inversa ----------
  pc_remo: {
    nome: "Remo ergômetro",
    musc: { quadriceps: 0.9, gluteo: 0.8, dorsal: 0.8, posterior: 0.6, biceps: 0.5 },
    dica: "Empurra com as pernas primeiro, depois inclina o tronco pra trás e só então puxa o cabo até as costelas. Na volta, estende os braços, inclina pra frente e só por último dobra os joelhos.",
    cam: { alvo: V3(0.15, 0.6, 0), dist: 5.2, yaw: 18, pitch: 10 },
    fase: ciclo(2.2, "remada: força 1 : volta 2", 0.8),
    cena(g) {
      g.add(K.viga(V3(-1.2, 0.30, 0), V3(1.0, 0.30, 0), 0.07, M.aco, 0.1));
      g.add(moveG(K.caixa(0.08, 0.04, 0.6, M.quadro, 0.01), -1.15, 0.02, 0)); g.add(K.viga(V3(-1.15, 0.04, 0), V3(-1.15, 0.28, 0), 0.06));
      g.add(moveG(K.caixa(0.08, 0.04, 0.7, M.quadro, 0.01), 0.95, 0.02, 0)); g.add(K.viga(V3(0.95, 0.04, 0), V3(0.95, 0.28, 0), 0.07));
      const vol = K.cilU(0.22, M.quadro, 40); vol.scale.y = 0.2; vol.rotation.x = Math.PI / 2; vol.position.set(1.12, 0.50, 0); g.add(vol);
      const cub = K.cilU(0.06, M.aco, 20); cub.scale.y = 0.26; cub.rotation.x = Math.PI / 2; cub.position.set(1.12, 0.50, 0); g.add(cub);
      g.add(K.viga(V3(1.0, 0.30, 0), V3(1.12, 0.5, 0), 0.1));
      for (const z of [-0.14, 0.14]) { const pl = K.caixa(0.03, 0.30, 0.13, M.quadro, 0.01); pl.position.set(0.70, 0.45, z); pl.rotation.z = rad(-40); g.add(pl); }
      g.add(K.tubo(V3(1.0, 0.32, 0), V3(1.05, 1.15, 0), 0.025, M.quadro));
      const con = K.caixa(0.05, 0.16, 0.26, M.quadro, 0.01); con.position.set(1.04, 1.2, 0); con.rotation.z = rad(25); g.add(con);
      this.banco = K.caixa(0.30, 0.07, 0.30, M.estofado, 0.03); this.carro = K.caixa(0.22, 0.08, 0.11, M.quadro, 0.01); g.add(this.banco, this.carro);
      this.cabo = K.cabo(); this.cabo.scale.x = this.cabo.scale.z = 1.6; g.add(this.cabo);
      this.pega = K.cilU(0.014, M.borracha); g.add(this.pega);
      sombreia(g);
    },
    pose(t) {
      zera();
      const e = (x) => suave(x);
      let Lg, Bt, Ar;
      if (t < 0.38) { const u = t / 0.38; Lg = e(u / 0.75); Bt = e((u - 0.25) / 0.75); Ar = e((u - 0.55) / 0.45); }
      else if (t < 0.43) { Lg = Bt = Ar = 1; }
      else { const v = (t - 0.43) / 0.57; Ar = 1 - e(v / 0.28); Bt = 1 - e((v - 0.15) / 0.45); Lg = 1 - e((v - 0.42) / 0.58); }
      const tp = V3(0.643, 0.766, 0), np = V3(-0.766, 0.643, 0), S0 = V3(0.78, 0.50, 0), seatTop = 0.43;
      const ank = {};
      for (const l of ["l", "r"]) ank[l] = tornozeloDe(S0.clone().add(V3(0, 0, lz(l) * 0.14)), tp, np, A0);
      const hy = seatTop + 0.095, D = 0.45 + 0.435 * Lg, hx = ank.l.x - Math.sqrt(D * D - (ank.l.y - hy) ** 2);
      const incl = lerp(0.62, -0.30, Bt);
      emPe(V3(hx, hy + 0.026, 0), F0, incl);
      gira("spine_02", EX, -0.1 * incl * 0.0); gira("neck_01", EX, -incl * 0.6); gira("head", EX, -0.05);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { perna(l, ank[l], V3(0.2, 1, lz(l) * 0.2)); sola(l, tp, np, A0); }
      this.banco.position.set(hx - 0.02, seatTop - 0.035, 0); this.carro.position.set(hx - 0.02, 0.37, 0);
      const sh = ladoMeio(), mao = sh.clone().add(V3(lerp(0.50, 0.13, Ar), lerp(-0.22, -0.37, Ar), 0));
      const pos = {};
      for (const l of ["l", "r"]) { const z = lz(l); pos[l] = agarra(l, { ponto: mao.clone().add(V3(0, 0, z * 0.22)), eixo: V3(0, 0, 1), palma: V3(0, -1, 0), R: 0.014, polo: V3(-0.6, -0.6, z * 0.8) }); }
      const H = pos.l.clone().add(pos.r).multiplyScalar(0.5);
      K.poe(this.pega, pos.l.clone().add(V3(0, 0, -0.04 * -1)), pos.r.clone().add(V3(0, 0, 0.04 * -1)));
      K.poe(this.cabo, V3(1.0, 0.48, 0), H);
    },
  },
  // ---------- escada rolante (StairMaster): degraus giram, os pés sobem um de cada vez ----------
  pc_escada: {
    nome: "Escada (stairmaster)",
    musc: { quadriceps: 0.9, gluteo: 1, panturrilha: 0.6, posterior: 0.6 },
    dica: "Sobe um degrau por vez, pé inteiro no degrau, tronco ereto e só um toque leve no corrimão. Empurra pelo calcanhar pra puxar o glúteo.",
    cam: { alvo: V3(0.1, 1.0, 0), dist: 5.6, yaw: 22, pitch: 8 },
    fase: ciclo(2.4, "subindo 1 degrau por passo", 0.75),
    cena(g) {
      const r = 0.17, d = 0.20; this.r = r; this.d = d;
      this.deg = [...Array(18)].map(() => { const m = K.caixa(d, 0.045, 0.72, new THREE.MeshStandardMaterial({ color: 0x3a3e46, metalness: 0.6, roughness: 0.4 }), 0.008); g.add(m); return m; });
      this.riser = [...Array(18)].map(() => { const m = K.caixa(0.012, r, 0.72, M.aco, 0.003); g.add(m); return m; });
      g.add(moveG(K.caixa(1.2, 0.5, 0.95, M.quadro, 0.03), -0.35, 0.25, 0));
      g.add(moveG(K.caixa(0.5, 2.0, 0.95, M.quadro, 0.03), 1.12, 1.0, 0));
      for (const z of [-0.45, 0.45]) { g.add(K.tubo(V3(-0.2, 1.22, z), V3(0.8, 1.22, z), 0.022, M.cromo)); g.add(K.viga(V3(0.6, 0.6, z), V3(0.6, 1.4, z), 0.05)); g.add(K.viga(V3(-0.2, 0.5, z), V3(-0.2, 1.22, z), 0.05)); }
      const con = K.caixa(0.1, 0.3, 0.9, M.quadro, 0.02); con.position.set(0.62, 1.45, 0); con.rotation.z = rad(-15); g.add(con);
      sombreia(g);
    },
    pose(t) {
      zera();
      const r = this.r, d = this.d, x0 = 0.16, y0 = 0.96, Pel = V3(0.0, 1.52, 0);
      emPe(Pel, F0, 0.1);
      gira("neck_01", EX, -0.1);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) {
        const p = mod(t + (l === "r" ? 0.5 : 0), 1), z = lz(l) * 0.115;
        let a, al = A0;
        if (p < 0.5) { const u = p / 0.5; a = V3(x0 - 2 * d * u, y0 - 2 * r * u, z); }
        else { const v = suave((p - 0.5) / 0.5); a = V3(x0 - 2 * d * (1 - v), y0 - 2 * r * (1 - v) + 0.14 * Math.sin(Math.PI * v), z); al = A0 + rad(18) * Math.sin(Math.PI * v); }
        perna(l, a, V3(1, 0.5, 0)); sola(l, F0, NZ, al);
      }
      for (const l of ["l", "r"]) { const z = lz(l); agarra(l, { ponto: V3(0.22, 1.22, z * 0.45), eixo: V3(0, 0, 1), palma: V3(0, -1, 0), R: 0.022, polo: V3(-1, -0.5, z * 0.4) }); }
      const off = 4 * t, ytop0 = y0 - 0.0798, xc0 = x0 + 0.05;
      this.deg.forEach((m, i) => { const k = i - 9, s = k - off; m.position.set(xc0 + s * d, ytop0 + s * r - 0.0225, 0); this.riser[i].position.set(xc0 + s * d - d / 2, ytop0 + s * r - r / 2 - 0.045, 0); const vis = m.position.y > 0.45 && m.position.x < 0.85 && m.position.y < 1.85; m.visible = this.riser[i].visible = vis; });
    },
  },
});
// ================= FUNCIONAL =================
// agachamento de base (copiado do molde 'agachamento' do motor, mais ereto): k = 0 em pé, 1 embaixo
function agachaBase(k, { prof = 0.43, incl = 0.5, recuo = 0.22, abre = 0.19 } = {}) {
  const alt = ALT_QUADRIL - 0.03 - k * (ALT_QUADRIL - prof), rec = 0.04 + k * recuo, inc = 0.05 + k * incl;
  emPe(V3(-rec, alt, 0), F0, inc * 0.55);
  gira("spine_01", EX, inc * 0.12); gira("spine_02", EX, inc * 0.12); gira("spine_03", EX, inc * 0.08);
  gira("neck_01", EX, -inc * 0.4); gira("head", EX, -inc * 0.1);
  B.pelvis.updateMatrixWorld(true);
  pernas(F0, { abre, fora: 0.45, poloFora: 0.6 });
}
const tabladoK = () => K.piso(2.6, 2.6);
Object.assign(MOLDES, {
  // ---------- pular corda ----------
  pc_corda: {
    nome: "Pular corda",
    musc: { panturrilha: 1, quadriceps: 0.4, deltoide: 0.3, antebraco: 0.4 },
    dica: "Pulos curtos, só a ponta dos pés sai do chão, cotovelos colados e o giro vem dos punhos. A corda passa quando tu está no ar; aterrissa macio nos dois pés.",
    cam: { alvo: V3(0, 0.95, 0), dist: 4.6, yaw: 35, pitch: 8 },
    fase: ciclo(0.5, "pulo simples, 120 giros/min", 0.75),
    cena(g) {
      g.add(tabladoK());
      this.seg = [...Array(26)].map(() => { const m = K.cilU(0.0065, laranja, 8); g.add(m); return m; });
      this.pg = [-1, 1].map(() => { const m = K.cilU(0.0165, M.borracha); m.scale.y = 0.14; g.add(m); return m; });
    },
    pose(t) {
      zera();
      const ar = 0.36, h = (t > 0.33 && t < 0.67) ? 0.11 * Math.sin(Math.PI * (t - 0.33) / 0.34) : 0, dip = 0.035 * (1 - Math.min(1, h / 0.03));
      const al = A0 + rad(26), ank = {};
      for (const l of ["l", "r"]) ank[l] = tornozeloDe(V3(0.02, h, lz(l) * 0.09), F0, NZ, al);
      const ay = ank.l.y;
      emPe(V3(-0.05, ay + 0.925 - dip, 0), F0, 0.05);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { perna(l, ank[l], V3(1, 0.1, lz(l) * 0.1)); sola(l, F0, NZ, al + (h > 0 ? rad(10) : 0)); }
      const psi = 2 * Math.PI * t, sh = ladoMeio(), yh = sh.y - 0.40, hands = {};
      for (const l of ["l", "r"]) {
        const z = lz(l);
        hands[l] = agarra(l, { ponto: V3(0.22 + 0.045 * Math.sin(psi), yh - 0.045 * Math.cos(psi), z * 0.34), eixo: V3(0, 0, 1), palma: V3(0.3, 0, -z), R: 0.0165, polo: V3(-0.4, -1, z * 0.6) });
      }
      const c = hands.l.clone().add(hands.r).multiplyScalar(0.5), Rm = c.y - 0.02;
      const pts = [];
      for (let i = 0; i <= 26; i++) { const q = i / 26, z = hands.l.z + (hands.r.z - hands.l.z) * q, r = Rm * Math.sin(Math.PI * q) * (0.98); pts.push(V3(c.x + r * Math.sin(psi), c.y + r * Math.cos(psi), z)); }
      for (let i = 0; i < 26; i++) K.poe(this.seg[i], pts[i], pts[i + 1]);
      this.pg.forEach((m, i) => { const hp = i === 0 ? hands.l : hands.r; m.position.copy(hp); m.rotation.set(0, 0, Math.PI / 2 * 0); m.quaternion.setFromUnitVectors(_yUp, V3(1, 0, 0)); });
    },
  },
  // ---------- burpee ----------
  pc_burpee: {
    nome: "Burpee",
    musc: { peitoral: 0.7, quadriceps: 0.8, gluteo: 0.7, triceps: 0.6, abdomen: 0.6 },
    dica: "Agacha, mãos no chão, joga os pés pra trás em prancha, desce o peito, volta os pés, salta com os braços pra cima e aterrissa macio.",
    cam: { alvo: V3(-0.25, 0.85, 0), dist: 5.6, yaw: 35, pitch: 10 },
    fase: ciclo(3.2, "burpee completo", 0.9),
    cena(g) { g.add(tabladoK()); },
    pose(t) {
      zera();
      // chaves: tempo, pelve(x,y), inclinação do tronco, tornozelo(x,y), pitch do pé (0 = sola no chão), mão(x,y) (null = braço solto), mão no chão?
      const Kf = [
        [0.00, -0.00, 0.998, 0.0, -0.05, 0.08, 0, [0.04, 0.72], 0],
        [0.14, -0.28, 0.46, 1.42, -0.05, 0.08, 0, [0.32, 0.05], 1],
        [0.27, -0.20, 0.41, 1.27, -1.05, 0.17, 0.6, [0.30, 0.05], 1],
        [0.37, -0.19, 0.27, 1.45, -1.05, 0.17, 0.6, [0.30, 0.05], 1],
        [0.46, -0.20, 0.41, 1.27, -1.05, 0.17, 0.6, [0.30, 0.05], 1],
        [0.56, -0.28, 0.46, 1.42, -0.05, 0.08, 0, [0.32, 0.05], 1],
        [0.68, -0.02, 1.38, 0.0, -0.05, 0.42, 0.7, [0.02, 2.15], 0],
        [0.79, -0.10, 0.80, 0.30, -0.05, 0.08, 0, [0.22, 1.15], 0],
        [1.00, -0.00, 0.998, 0.0, -0.05, 0.08, 0, [0.04, 0.72], 0],
      ];
      let i = 0; while (i < Kf.length - 2 && t >= Kf[i + 1][0]) i++;
      const a = Kf[i], b = Kf[i + 1], u = cl((t - a[0]) / (b[0] - a[0])), k = suave(u), m = (j) => lerp(a[j], b[j], k);
      const salto = (i === 1 || i === 4) ? 0.16 * Math.sin(Math.PI * u) : 0;
      const piv = m(6), incl = m(3), ax = m(4), ay = m(5) + salto;
      emPe(V3(m(1), m(2), 0), F0, incl);
      gira("neck_01", EX, -incl * 0.42); gira("head", EX, -0.1);
      B.pelvis.updateMatrixWorld(true);
      const al = A0 + rad(44) * piv;
      for (const l of ["l", "r"]) {
        const z = lz(l) * 0.12, S = V3(ax, ay - 0.0798 + (piv > 0 ? 0.0798 : 0.0), z);
        const an = V3(ax, ay, z);
        perna(l, an, V3(1, 0.4, lz(l) * 0.1)); sola(l, F0, NZ, al);
      }
      const ha = a[7], hb = b[7], hxy = [lerp(ha[0], hb[0], k), lerp(ha[1], hb[1], k)], ch = m(8);
      for (const l of ["l", "r"]) {
        const z = lz(l), W = V3(hxy[0], hxy[1] + 0.02, z * 0.2);
        braco(l, W, V3(-1, 0.3, z * 0.8));
        const fw = W.clone().sub(ondeEsta("lowerarm_" + l)).normalize();
        mao(l, fw, ch > 0.5 ? V3(0, -1, 0) : V3(0, 0, -z));
      }
    },
  },
  // ---------- polichinelo ----------
  pc_polichinelo: {
    nome: "Polichinelo",
    musc: { deltoide: 0.8, panturrilha: 0.7, gluteo: 0.5, adutor: 0.5 },
    dica: "Abre pernas e braços ao mesmo tempo, mãos se encontrando em cima da cabeça, e fecha voltando as mãos às coxas. Pulos leves, ponta do pé, joelho macio.",
    cam: { alvo: V3(0, 1.0, 0), dist: 4.6, yaw: 82, pitch: 6 },
    fase: ciclo(0.9, "polichinelo contínuo", 0.7),
    cena(g) { g.add(tabladoK()); },
    pose(t) {
      zera();
      const tm = mod(t, 0.5), ar = tm < 0.25, h = ar ? 0.08 * Math.sin(Math.PI * tm / 0.25) : 0;
      const o = t < 0.25 ? suave(t / 0.25) : t < 0.5 ? 1 : t < 0.75 ? 1 - suave((t - 0.5) / 0.25) : 0;
      const al = A0 + rad(ar ? 22 : 6), dip = ar ? 0 : 0.03 * Math.sin(Math.PI * (tm - 0.25) / 0.25);
      const ank = {}, ts = {};
      for (const l of ["l", "r"]) { ts[l] = girarY(F0, lz(l) * -0.0 + (l === "l" ? 1 : -1) * (0.15 + 0.3 * o)); ank[l] = tornozeloDe(V3(0.1, h, lz(l) * (0.11 + 0.27 * o)), ts[l], NZ, al); }
      emPe(V3(-0.03, ank.l.y + 0.915 - dip, 0), F0, 0.0);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { perna(l, ank[l], V3(1, 0.1, lz(l) * (0.15 + 0.6 * o))); sola(l, ts[l], NZ, al); }
      const phi = lerp(0.14, 2.8, o), RL = (COMP.upperarm_l + COMP.lowerarm_l) * 0.96;
      for (const l of ["l", "r"]) {
        const z = lz(l), S = ondeEsta("upperarm_" + l), W = S.clone().add(V3(0.04, -RL * Math.cos(phi), z * RL * Math.sin(phi)));
        braco(l, W, V3(-0.3, -0.2, z * 1)); const fw = W.clone().sub(ondeEsta("lowerarm_" + l)).normalize();
        mao(l, fw, V3(0.4, 0.0, -z));
      }
    },
  },
  // ---------- farmer walk: caminha com carga, o chão corre sob os pés ----------
  pc_farmer: {
    nome: "Farmer walk",
    musc: { trapezio: 0.9, antebraco: 1, abdomen: 0.5, gluteo: 0.5, lombar: 0.5 },
    dica: "Carga pesada nas duas mãos, ombros pra trás e pra baixo, abdômen firme. Passos curtos e firmes, sem balançar o tronco nem deixar os pesos batendo nas pernas.",
    cam: { alvo: V3(0, 0.95, 0), dist: 5.0, yaw: 28, pitch: 7 },
    fase: ciclo(1.1, "caminha com carga", 0.6),
    cena(g) {
      g.add(K.piso(2.8, 1.4));
      this.rip = [...Array(16)].map(() => { const m = K.caixa(0.03, 0.004, 1.2, new THREE.MeshStandardMaterial({ color: 0x59616e, roughness: 0.8 }), 0.001); m.position.y = 0.002; g.add(m); return m; });
      this.h = [halter(2.2), halter(2.2)]; g.add(...this.h);
    },
    pose(t) {
      zera();
      const s = 0.62, L = 0.50, xf = 0.22;
      emPe(V3(0.0, ALT_QUADRIL - 0.012 - 0.012 * Math.cos(4 * Math.PI * (t - 0.1)), 0), F0, 0.03);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) {
        const p = mod(t + (l === "r" ? 0.5 : 0), 1), z = lz(l) * 0.1, f = girarY(F0, (l === "l" ? 1 : -1) * 0.12);
        const est = (u) => { const al = A0 + rad(28) * suave((u - 0.7) / 0.3); return { al, a: tornozeloDe(V3(xf + 0.136 - L * u, 0, z), f, NZ, al) }; };
        let a, al;
        if (p < s) { const e = est(p / s); a = e.a; al = e.al; }
        else { const v = (p - s) / (1 - s), e1 = est(1), e0 = est(0); a = e1.a.clone().lerp(e0.a, suave(v)); a.y += 0.11 * Math.sin(Math.PI * v); al = lerp(e1.al, A0 - rad(8), suave(v)); }
        perna(l, a, V3(1, 0.2, lz(l) * 0.05)); sola(l, f, NZ, al);
      }
      ["l", "r"].forEach((l, i) => {
        const z = lz(l), S = ondeEsta("upperarm_" + l);
        agarra(l, { punho: S.clone().add(V3(0.0, -(COMP.upperarm_l + COMP.lowerarm_l) * 0.975, z * 0.025)), eixo: F0.clone(), palma: V3(0, 0, -z), R: 0.016, polo: V3(-1, 0, z * 0.3) });
        seguraHalter(this.h[i], l);
      });
      const k = (t / s) * L * 0 + t * (L / s) * 2;                  // 2 passos por ciclo; o chão anda o mesmo que o pé de apoio
      this.rip.forEach((m, i) => { m.position.x = -1.2 + mod(i * 0.1775 - t * (L / s), 2.84); });
    },
  },
  // ---------- battle rope ----------
  pc_battle: {
    nome: "Battle rope",
    musc: { deltoide: 1, trapezio: 0.5, abdomen: 0.5, antebraco: 0.6, quadriceps: 0.5 },
    dica: "Meio agachado, quadril atrás, abdômen firme. Sobe e desce os braços alternados em ondas rápidas, só os ombros trabalham, e o tronco fica parado.",
    cam: { alvo: V3(1.0, 0.95, 0), dist: 6.4, yaw: 38, pitch: 8 },
    fase: ciclo(0.6, "ondas alternadas", 0.9),
    cena(g) {
      g.add(K.piso(4.6, 2.0).translateX(1.1));
      g.add(K.caixa(0.4, 0.4, 0.4, M.quadro, 0.03).translateX(3.2).translateY(0.2)); g.add(K.tubo(V3(3.2, 0.3, 0), V3(3.2, 0.6, 0), 0.03, M.cromo));
      this.cord = [0, 1].map((k) => { const seg = [...Array(30)].map(() => { const m = K.cilU(0.021, k ? cinza : preto, 10); g.add(m); return m; }); return seg; });
    },
    pose(t) {
      zera();
      const phi = 2 * Math.PI * t * 1.0 * 2;
      emPe(V3(-0.1, 0.74 + 0.012 * Math.sin(phi * 2), 0), F0, 0.5);
      gira("neck_01", EX, -0.25); gira("head", EX, -0.1);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { perna(l, V3(0.05, ALT_TORN, lz(l) * 0.19), V3(1, 0.2, lz(l) * 0.4)); pe(l, girarY(F0, lz(l) * -0.0 + (l === "l" ? 1 : -1) * 0.3)); }
      const A = V3(3.2, 0.6, 0);
      for (const l of ["l", "r"]) {
        const z = lz(l), ph = phi + (l === "r" ? Math.PI : 0), H = V3(0.46, 1.08 + 0.2 * Math.sin(ph), z * 0.17);
        agarra(l, { ponto: H, eixo: F0.clone(), palma: V3(0, 0, -z), R: 0.021, polo: V3(-0.5, -1, z * 0.6) });
        const seg = this.cord[l === "l" ? 0 : 1], pts = [];
        const Hz = H.clone().add(V3(0, 0, z * 0.0)), Az = A.clone().add(V3(0, 0, z * 0.12));
        for (let i = 0; i <= 30; i++) { const q = i / 30, p = Hz.clone().lerp(Az, q); const sag = 0.35 * Math.sin(Math.PI * q) * -0.4; p.y += 0.2 * (1 - 0.55 * q) * Math.sin(ph - 9 * q) * (q > 0 ? 1 : 0) + sag * 0 + (1 - q) * (0.0); p.y = Math.max(0.03, p.y + (0.6 - Hz.y) * 0 ); pts.push(p); }
        for (let i = 0; i < 30; i++) K.poe(seg[i], pts[i], pts[i + 1]);
      }
    },
  },
  // ---------- kettlebell goblet squat ----------
  pc_goblet: {
    nome: "Kettlebell goblet squat",
    musc: { quadriceps: 1, gluteo: 0.8, adutor: 0.5, abdomen: 0.4 },
    dica: "Kettlebell colado ao peito, segurando pelas laterais da alça, cotovelos apontando pra baixo. Desce entre os joelhos, tronco alto e calcanhar no chão, e sobe empurrando o chão.",
    cam: { alvo: V3(0, 0.85, 0), dist: 4.3, yaw: 40, pitch: 10 },
    cena(g) { g.add(tablado()); this.kb = K.kettlebell(16); this.kb.rotation.y = Math.PI / 2; g.add(this.kb); },
    pose(t) {
      zera();
      agachaBase(t, { prof: 0.44, incl: 0.5, recuo: 0.22 });
      const c = quadroDe("spine_03"), p3 = ondeEsta("spine_03");
      const kc = p3.clone().addScaledVector(c.fr, 0.20).addScaledVector(c.up, -0.02);
      this.kb.position.copy(kc);
      for (const l of ["l", "r"]) {
        const z = lz(l);
        agarra(l, { ponto: kc.clone().add(V3(0, 0.105, z * 0.062)), eixo: c.up.clone(), palma: V3(0, 0, -z).addScaledVector(c.fr, 0.3), R: 0.013, polo: V3(-0.5, -1, z * 0.5) });
      }
    },
  },
  // ---------- arremesso de medicine ball (wall ball) ----------
  pc_arremesso: {
    nome: "Arremesso de medicine ball",
    musc: { deltoide: 0.9, peitoral: 0.7, triceps: 0.7, quadriceps: 0.7, gluteo: 0.6, abdomen: 0.5 },
    dica: "Agacha com a bola no peito, sobe explodindo com as pernas e solta a bola no alvo, acima da cabeça. Recebe com os braços já esticados e amortece descendo de novo.",
    cam: { alvo: V3(0.55, 1.3, 0), dist: 7.2, yaw: 35, pitch: 6 },
    fase: ciclo(3.0, "agacha, arremessa, recebe", 0.85),
    cena(g) {
      g.add(tabladoK());
      g.add(moveG(K.caixa(0.1, 3.4, 2.4, parede, 0.01), 1.55, 1.7, 0));
      const al = K.cilU(0.24, laranja, 40); al.scale.y = 0.01; al.rotation.z = Math.PI / 2; al.position.set(1.495, 2.55, 0); g.add(al);
      const al2 = K.cilU(0.13, parede, 40); al2.scale.y = 0.012; al2.rotation.z = Math.PI / 2; al2.position.set(1.493, 2.55, 0); g.add(al2);
      this.bola = K.bolaMed(0.125); this.bola.traverse((m) => { if (m.isMesh) m.material = new THREE.MeshStandardMaterial({ color: 0xb4602f, roughness: 0.6 }); }); g.add(this.bola);
    },
    pose(t) {
      zera();
      const q = t < 0.2 ? 1 - suave(t / 0.2) : t < 0.55 ? 0 : suave((t - 0.55) / 0.35);
      const hh = t < 0.2 ? suave(t / 0.2) : t < 0.55 ? 1 : 1 - suave((t - 0.55) / 0.35);
      agachaBase(q, { prof: 0.44, incl: 0.5, recuo: 0.22 });
      const c = quadroDe("spine_03"), p3 = ondeEsta("spine_03"), sh = ladoMeio();
      const peito = p3.clone().addScaledVector(c.fr, 0.2).addScaledVector(c.up, 0.0), topo = sh.clone().add(V3(0.2, 0.52, 0)), T = V3(1.38, 2.55, 0);
      let bp = peito.clone().lerp(topo, hh);
      if (t >= 0.2 && t < 0.35) { const s = (t - 0.2) / 0.15; bp = topo.clone().lerp(T, s); bp.y += 0.3 * Math.sin(Math.PI * s * 0.9); }
      else if (t >= 0.35 && t < 0.5) { const s = (t - 0.35) / 0.15; bp = T.clone().lerp(topo, s * s); }
      this.bola.position.copy(bp);
      const maos = (t >= 0.2 && t < 0.5) ? topo : bp;
      for (const l of ["l", "r"]) {
        const z = lz(l), W = maos.clone().add(V3(-0.01, 0, z * 0.135));
        braco(l, W, V3(-0.5, -0.3, z * 0.9)); const fw = V3(0.3, 1, 0).multiplyScalar(hh > 0.5 ? 1 : 0.3).add(V3(0.7, 0, 0));
        mao(l, fw.normalize(), V3(0, 0, -z));
      }
    },
  },
});
// @@FOCOS@@
Object.assign(FOCOS, {
  // PANTURRILHA. Riemann 2011 (J Strength Cond Res 25): gastrocnêmio medial x lateral no heel raise (pé aberto puxa o medial, pé fechado o lateral).
  // Signorile 2002 (J Strength Cond Res 16): gastrocnêmio rende mais com joelho estendido; com joelho a 90° (sentado) o sóleo assume (o sóleo não está mapeado aqui: sentado = panturrilha mais fraca).
  // Estabilizadores (trapézio segurando a barra/ombreira, glúteo médio no apoio unilateral, tibial em co-contração): estimativa.
  pc_pant_pe: () => [["panturrilha", 1], ["trapezio_sup", 0.2], ["tibial", 0.1]],
  pc_pant_sentado: () => [["panturrilha", 0.55], ["tibial", 0.08]],
  pc_pant_legpress: () => [["panturrilha", 1], ["tibial", 0.1]],
  pc_pant_smith: () => [["panturrilha", 1], ["trapezio_sup", 0.25], ["lombar", 0.2], ["tibial", 0.1]],
  pc_pant_degrau: (p) => p.uni ? [["panturrilha", 1], ["gluteo_med", 0.3], ["tibial", 0.12], ["antebraco", p.halter ? 0.3 : 0]].filter((x) => x[1] > 0)
    : [["panturrilha", 1], ["tibial", 0.1]],
  pc_burrinho: () => [["panturrilha", 1], ["lombar", 0.3], ["isquio", 0.15], ["gluteo_max", 0.15]],
  // CARDIO. Corrida (Gazendam & Hof 2007 Gait Posture; Kyröläinen 2005 J Sports Sci): gastrocnêmio no impulso, vastos e glúteo na recepção, isquiotibiais no fim da balançada.
  pc_esteira: () => [["panturrilha", 1], ["vasto_lateral", 0.8], ["vasto_medial", 0.8], ["gluteo_max", 0.75], ["isquio", 0.7], ["reto_femoral", 0.55], ["tibial", 0.5], ["gluteo_med", 0.4]],
  // Bike: Hug & Dorel 2009 (J Electromyogr Kinesiol 19) e Ericson 1986: vastos e glúteo na descida, isquio no fim, gastrocnêmio 90-270°.
  pc_bike: () => [["vasto_lateral", 1], ["vasto_medial", 1], ["gluteo_max", 0.75], ["reto_femoral", 0.6], ["isquio", 0.55], ["panturrilha", 0.5], ["tibial", 0.3]],
  // Elíptico: Damiano 2011 (Gait Posture) compara quadríceps/isquio com caminhada; valores relativos = estimativa.
  pc_eliptico: () => [["vasto_lateral", 0.8], ["vasto_medial", 0.8], ["gluteo_max", 0.8], ["isquio", 0.65], ["panturrilha", 0.5], ["reto_femoral", 0.5], ["deltoide_post", 0.25], ["biceps", 0.2]],
  // Remo: Janshen 2009 (J Appl Biomech), Pollock 2009 (Med Sci Sports Exerc), Guével 2011 (Int J Sports Med): vastos/glúteo na fase de força, dorsal e eretores no tronco. Relativos = estimativa.
  pc_remo: () => [["vasto_lateral", 1], ["vasto_medial", 1], ["gluteo_max", 0.85], ["dorsal", 0.8], ["isquio", 0.6], ["lombar", 0.6], ["biceps", 0.5], ["trapezio_med", 0.45]],
  // Escada: Lyons 1983 (Phys Ther) glúteo máximo/vastos na subida de degraus; relativos = estimativa.
  pc_escada: () => [["gluteo_max", 1], ["vasto_lateral", 0.9], ["vasto_medial", 0.9], ["reto_femoral", 0.6], ["panturrilha", 0.6], ["isquio", 0.5], ["gluteo_med", 0.5]],
  // Funcional: sem EMG publicado específico encontrado, tudo estimativa (exceto farmer: McGill 2009 J Strength Cond Res, tronco no carregamento; goblet: Escamilla 2001 / Caterisano 2002 no agachamento).
  pc_corda: () => [["panturrilha", 1], ["vasto_lateral", 0.45], ["vasto_medial", 0.45], ["tibial", 0.3], ["antebraco", 0.35], ["deltoide_lat", 0.25], ["abdomen", 0.3]],
  pc_burpee: () => [["vasto_lateral", 0.8], ["vasto_medial", 0.8], ["gluteo_max", 0.75], ["peitoral_med", 0.7], ["triceps_lateral", 0.65], ["deltoide_ant", 0.65], ["abdomen", 0.6], ["panturrilha", 0.4]],
  pc_polichinelo: () => [["panturrilha", 0.8], ["deltoide_lat", 0.8], ["gluteo_med", 0.6], ["adutores", 0.5], ["vasto_lateral", 0.4], ["trapezio_sup", 0.4], ["abdomen", 0.25]],
  pc_farmer: () => [["trapezio_sup", 1], ["antebraco", 0.95], ["obliquo", 0.6], ["lombar", 0.6], ["abdomen", 0.5], ["gluteo_med", 0.5], ["gluteo_max", 0.4], ["vasto_lateral", 0.35]],
  pc_battle: () => [["deltoide_ant", 1], ["deltoide_lat", 0.8], ["antebraco", 0.6], ["abdomen", 0.6], ["trapezio_sup", 0.55], ["gluteo_max", 0.5], ["vasto_lateral", 0.5], ["biceps", 0.35]],
  pc_goblet: () => [["vasto_lateral", 1], ["vasto_medial", 1], ["gluteo_max", 0.8], ["reto_femoral", 0.55], ["adutores", 0.55], ["abdomen", 0.4], ["deltoide_ant", 0.3], ["biceps", 0.3]],
  pc_arremesso: () => [["deltoide_ant", 1], ["peitoral_med", 0.85], ["triceps_lateral", 0.8], ["vasto_lateral", 0.7], ["vasto_medial", 0.7], ["gluteo_max", 0.65], ["abdomen", 0.5], ["serratil", 0.4]],
  // TIBIAL: não achei EMG publicado de elevação de ponta de pé na parede; o tibial anterior é o motor primário da dorsiflexão (estimativa para o resto).
  pc_tibial: () => [["tibial", 1], ["vasto_lateral", 0.12], ["vasto_medial", 0.12]],
});
Object.assign(VISTA, { pc_pant_degrau: (p) => p.uni ? 300 : 240, pc_tibial: 64 });
}

// ===== moldes/core.js =====
{ // moldes/core.js — Abdômen e core (prefixo ab_)
const ABY = 0.02; // topo do colchonete
const ab_tapete = (cx = 0.1, comp = 2.3, larg = 0.7) => { const m = K.colchonete(comp, larg); m.position.x = cx; return m; };
const ab_q = (n) => B[n].getWorldQuaternion(new THREE.Quaternion());
const ab_dedos = (l, curva = 0) => { for (const d of DEDOS) B[`${d}_01_${l}`].quaternion.copy(MAO0[l].alinha[d]); if (curva) fecha(l, curva); };
// mão aberta (apoio no chão, atrás da cabeça...): punho no ponto, dedos pra dir, palma pra palma; o giro do antebraço vai pro antebraço
function ab_mao(l, punho, polo, dir, palma, curva = 0.12) {
  braco(l, punho, polo, 0); mao(l, dir, palma);
  const rel = ab_q("lowerarm_" + l).invert().multiply(ab_q("hand_" + l)), a = DIR["lowerarm_" + l];
  const tw = 2 * Math.atan2(rel.x * a.x + rel.y * a.y + rel.z * a.z, rel.w);
  braco(l, punho, polo, Math.atan2(Math.sin(tw), Math.cos(tw)) * 0.9); mao(l, dir, palma);
  ab_dedos(l, curva);
}
// mãos de leve atrás das orelhas (cotovelo aberto); segue a cabeça, então enrola junto com o tronco
function ab_maosCabeca(abre = 1) {
  const hq = quadroDe("head"), hb = ondeEsta("head");
  for (const l of ["l", "r"]) {
    const sl = l === "l" ? 1 : -1;
    const w = hb.clone().add(hq.up.clone().multiplyScalar(0.055)).add(hq.esq.clone().multiplyScalar(sl * 0.15)).add(hq.fr.clone().multiplyScalar(0.03));
    const dir = hq.up.clone().multiplyScalar(0.85).add(hq.fr.clone().multiplyScalar(-0.15)).add(hq.esq.clone().multiplyScalar(-sl * 0.5));
    ab_mao(l, w, hq.esq.clone().multiplyScalar(sl * abre).add(hq.up.clone().multiplyScalar(0.25)), dir, hq.esq.clone().multiplyScalar(-sl));
  }
}
const ab_lado = (l) => (l === "l" ? -1 : 1); // lado em Z quando deitado/de frente pra +X (esquerdo = -Z)
// de costas no colchonete: pelve em (x, ABY+0.111), tronco no eixo -X. inc = inclinação da pelve (rad, cabeça pra cima),
// flex = enrolar do tronco (rad, total), pesc = flexão do pescoço. Deitado reto o dorso "assenta" (extensão leve pra encostar no chão).
function ab_costas(x, { inc = 0, flex = 0, pesc = 0.05, y = 0 } = {}) {
  const c = Math.cos(inc), s = Math.sin(inc);
  corpoEm(V3(x, ABY + 0.111 + y, 0), V3(-c, s, 0), V3(s, c, 0));
  const e = -0.1 * Math.max(0, 1 - flex / 0.25);
  gira("spine_01", EX, e * 0.2 + flex * 0.2); gira("spine_02", EX, e * 0.4 + flex * 0.35); gira("spine_03", EX, e * 0.4 + flex * 0.45);
  gira("neck_01", EX, pesc + flex * 0.3);
  B.pelvis.updateMatrixWorld(true);
}
// perna deitada de costas no plano (x, y): coxa a phi (rad, 0 = deitada pra frente (+X), pi/2 = vertical), joelho flexionado kap (rad)
// zf = quanto os tornozelos se aproximam do eixo. Devolve a posição do joelho e do tornozelo.
function ab_pernaSag(l, phi, kap, zf = 0.85) {
  const H = ondeEsta("thigh_" + l), k = Math.max(kap, 0.09);
  const J = H.clone().add(V3(Math.cos(phi), Math.sin(phi), 0).multiplyScalar(COMP.thigh_l));
  const A = J.clone().add(V3(Math.cos(phi - k), Math.sin(phi - k), 0).multiplyScalar(COMP.calf_l)); A.z = H.z * zf;
  perna(l, A, J.clone().sub(H));
  return { J, A };
}
// braço esticado a partir do ombro numa direção; palma pro meio (pegada neutra) ou pra palma
function ab_braco(l, dir, dist = 0.505, palma = null, polo = null) {
  const S = ondeEsta("upperarm_" + l), d = dir.clone().normalize(), w = S.clone().add(d.clone().multiplyScalar(dist));
  ab_mao(l, w, polo || V3(0, 0.5, 0).add(V3(0, 0, ab_lado(l) * 0.5)), d, palma || V3(0, 0, -ab_lado(l)));
  return w;
}
const ab_suave = (x) => { const k = Math.min(1, Math.max(0, x)); return k * k * (3 - 2 * k); };
// movimento alternado: t vai 0 -> 1 -> 0 em `per` s (suave). t = 0 e t = 1 são os dois lados, 0.5 = centro
function ab_alt(rel, per, tx0, tx1, tm, esf = 0.6) {
  const t = 0.5 - 0.5 * Math.cos(2 * Math.PI * rel / per);
  return { t, f: t < 0.18 ? tx0 : t > 0.82 ? tx1 : tm, esforco: esf + 0.3 * Math.abs(t - 0.5) * 2 };
}

const AB_BARRA = 2.45, AB_PARAL = 1.32;
// desloca a pelve até o meio dos ombros chegar em `alvo` (corpo pendurado/apoiado: o resto do corpo acompanha)
function ab_ancora(alvo) {
  const m = ondeEsta("upperarm_l").add(ondeEsta("upperarm_r")).multiplyScalar(0.5);
  B.pelvis.position.add(alvo.clone().sub(m)); B.pelvis.updateMatrixWorld(true);
}

// coxa e canela em direções (planos quaisquer), a partir do quadril real; polo = joelho
function ab_pernaDir(l, dC, dK) {
  const H = ondeEsta("thigh_" + l), J = H.clone().add(dC.clone().normalize().multiplyScalar(COMP.thigh_l)), A = J.clone().add(dK.clone().normalize().multiplyScalar(COMP.calf_l));
  perna(l, A, J.clone().sub(H));
  return { H, J, A };
}
// pé com os dedos pra d e o peito do pé pro lado de d × (esquerda do personagem em Z-)
function ab_pe(l, d, ded = 0) {
  mira("foot_" + l, d.clone().normalize(), V3(0, 0, -1), EX);
  if (ded) gira("ball_" + l, EX, ded);
}
// corpo de bruços (prancha): ombros no ponto S, altura do tornozelo Ay; a linha ombro-quadril-tornozelo fica reta (perna quase esticada).
// Devolve o tornozelo A (x calculado), a inclinação th e os eixos u (cabeça) e fr (peito, pra baixo).
function ab_prono(S, Ay, { Ld = 0.905, pesc = -0.2 } = {}) {
  const th = Math.asin((S.y - Ay) / (0.512 + Ld)), u = V3(Math.cos(th), Math.sin(th), 0), fr = V3(Math.sin(th), -Math.cos(th), 0);
  corpoEm(S.clone().sub(u.clone().multiplyScalar(0.486)).setZ(0), u, fr);
  gira("neck_01", EX, pesc);
  B.pelvis.updateMatrixWorld(true);
  ab_ancora(S);
  return { th, u, fr, A: V3(S.x - (0.512 + Ld) * Math.cos(th), Ay, 0) };
}
// mão no chão (palma pra baixo, dedos pra +X)
function ab_maoChao(l, W, polo = V3(-1, -0.5, 0), dir = V3(1, 0, 0), palma = V3(0, -1, 0)) { ab_mao(l, W, polo, dir, palma, 0.05); }

Object.assign(MOLDES, {
  ab_supra: {
    nome: "Abdominal supra no solo",
    musc: { abdomen: 1, lombar: 0.2 },
    dica: "Joelho dobrado, pé no chão, mãos de leve atrás da cabeça. Enrola o tronco tirando só as escápulas do chão, sem puxar o pescoço, e desce devagar.",
    cam: { alvo: V3(0.0, 0.28, 0), dist: 3.5, yaw: 30, pitch: 26 },
    cena(g) { g.add(ab_tapete()); },
    pose(t) {
      zera();
      const k = 1 - t, X0 = 0.12, tw = this.p.obliquo ? 0.6 * k : 0;
      ab_costas(X0, { flex: 0.62 * k });
      if (tw) { gira("spine_02", EY, tw * 0.4); gira("spine_03", EY, tw * 0.6); } // ombro direito sobe em direção ao joelho esquerdo
      for (const l of ["l", "r"]) {
        const s = ab_lado(l);
        perna(l, V3(X0 + 0.42, ABY + ALT_TORN, s * 0.14), V3(0.1, 1, s * 0.1));
        pe(l, V3(1, 0, s * 0.1));
      }
      ab_maosCabeca();
    },
  },
  ab_declinado: {
    nome: "Abdominal declinado",
    musc: { abdomen: 1, quadriceps: 0.3 },
    dica: "Tornozelo preso sob os roletes, cabeça mais baixa que o quadril. Sobe enrolando a coluna, sem puxar o pescoço, e desce controlando até quase tocar o banco.",
    cam: { alvo: V3(0.1, 0.7, 0), dist: 4.0, yaw: 30, pitch: 18 },
    cena(g) {
      const a = 0.3, fr = V3(-Math.sin(a), Math.cos(a), 0), cab = V3(-Math.cos(a), -Math.sin(a), 0), Q = V3(0.06, 0.72, 0).sub(fr.clone().multiplyScalar(0.115));
      g.add(K.piso(2.8, 2.0));
      const pad = K.caixa(1.5, 0.08, 0.3, M.estofado, 0.03); pad.rotation.z = a; pad.position.copy(Q).add(cab.clone().multiplyScalar(0.5)).sub(fr.clone().multiplyScalar(0.04)); g.add(pad);
      const sob = (s) => Q.clone().add(cab.clone().multiplyScalar(s)).sub(fr.clone().multiplyScalar(0.09));
      g.add(K.viga(sob(-0.2), sob(1.1), 0.06, M.quadro));
      for (const s of [-0.12, 1.0]) { const T = sob(s); g.add(K.viga(V3(T.x, 0.02, 0), T, 0.06, M.quadro)); g.add(K.caixa(0.08, 0.05, 0.5, M.quadro, 0.015).translateX(T.x).translateY(0.025)); }
      // roletes dos tornozelos: um por cima do peito do pé, outro por baixo (calcanhar), no mesmo mastro
      const px = 0.86;
      g.add(K.viga(V3(px, 0.02, 0), V3(px, 1.07, 0), 0.06, M.quadro)); g.add(K.caixa(0.08, 0.05, 0.5, M.quadro, 0.015).translateX(px).translateY(0.025));
      g.add(K.viga(V3(px, 0.02, 0), V3(px - 0.36, 0.02, 0), 0.05, M.quadro));
      for (const [x, y] of [[0.64, 0.87], [0.73, 0.67]]) {
        const r = K.rolo(0.38, 0.045); r.rotation.y = Math.PI / 2; r.position.set(x, y, 0); g.add(r);
        for (const z of [-0.19, 0.19]) g.add(K.tubo(V3(px, y, z * 0.95), V3(x, y, z * 0.95), 0.012, M.aco));
      }
    },
    pose(t) {
      zera();
      const k = 1 - t, a = 0.3;
      ab_costas(0.06, { inc: -a + 0.3 * k, flex: 1.0 * k, y: 0.72 - ABY - 0.111, pesc: 0.05 });
      for (const l of ["l", "r"]) {
        const s = ab_lado(l);
        perna(l, V3(0.62, 0.735, s * 0.16), V3(0.4, 1, s * 0.1));
      }
      ab_maosCabeca();
    },
  },
  ab_infra: {
    nome: "Elevação de pernas deitado",
    musc: { abdomen: 1, quadriceps: 0.45 },
    dica: "Lombar colada no chão, pernas juntas e quase retas. Sobe até a vertical e, no fim, enrola o quadril pra cima; desce devagar sem deixar a lombar arquear.",
    cam: { alvo: V3(0.25, 0.4, 0), dist: 4.1, yaw: 28, pitch: 20 },
    cena(g) { g.add(ab_tapete(0.2, 2.5)); },
    pose(t) {
      zera();
      const k = 1 - t, X0 = -0.05, rho = 0.42 * Math.pow(k, 2.2); // quadril enrola quando as pernas passam da vertical
      ab_costas(X0, { inc: -rho, flex: rho, y: 0.13 * Math.sin(rho / 0.42 * 1.4) });
      const phi = (7 + 88 * Math.pow(k, 0.85)) * Math.PI / 180;
      for (const l of ["l", "r"]) ab_pernaSag(l, phi - rho, 0.1);
      for (const l of ["l", "r"]) { // mãos espalmadas ao lado do quadril
        const sz = ab_lado(l), S = ondeEsta("upperarm_" + l);
        ab_mao(l, V3(S.x + 0.5, ABY + 0.05, sz * 0.2), V3(0, 0.3, sz), V3(1, 0, 0), V3(0, -1, 0));
      }
    },
  },
  ab_bicicleta: {
    nome: "Abdominal bicicleta",
    musc: { abdomen: 1, lombar: 0.15 },
    dica: "Mãos leves atrás da cabeça, cotovelos abertos. Gira o tronco levando o cotovelo ao joelho oposto enquanto a outra perna estica; não puxa a cabeça com as mãos.",
    cam: { alvo: V3(0.1, 0.35, 0), dist: 3.9, yaw: 38, pitch: 28 },
    cena(g) { g.add(ab_tapete(0.15, 2.4)); },
    fase(rel) { return ab_alt(rel, 2.4, "cotovelo esquerdo ao joelho direito", "cotovelo direito ao joelho esquerdo", "troca de lado", 0.7); },
    pose(t) {
      zera();
      const s = 2 * t - 1; // +1: tronco gira pra esquerda (ombro direito sobe), joelho esquerdo vem ao peito
      ab_costas(0.1, { flex: 0.8 });
      gira("spine_02", EY, 0.3 * s); gira("spine_03", EY, 0.4 * s);
      const fl = 0.5 + 0.5 * s, fr = 0.5 - 0.5 * s; // quanto cada perna está dobrada
      const perna1 = (l, f) => ab_pernaSag(l, (16 + 74 * f) * Math.PI / 180, (6 + 100 * f) * Math.PI / 180);
      perna1("l", fl); perna1("r", fr);
      ab_maosCabeca(1);
    },
  },
  ab_canivete: {
    nome: "Abdominal canivete",
    musc: { abdomen: 1, quadriceps: 0.5 },
    dica: "Deitado com braços esticados acima da cabeça. Sobe tronco e pernas retas ao mesmo tempo até formar um V, mãos indo em direção aos pés, e desce sem apoiar.",
    cam: { alvo: V3(0.05, 0.45, 0), dist: 4.1, yaw: 28, pitch: 20 },
    cena(g) { g.add(ab_tapete(0.1, 2.5)); },
    pose(t) {
      zera();
      const k = 1 - t, X0 = 0.1;
      ab_costas(X0, { inc: 0.32 * k, flex: 0.78 * k, y: 0.02 * k });
      const phi = (6 + 58 * k) * Math.PI / 180;
      for (const l of ["l", "r"]) ab_pernaSag(l, phi, 0.1);
      B.pelvis.updateMatrixWorld(true);
      // braços: acima da cabeça (deitado) -> alcançando os pés (V)
      const H = ondeEsta("thigh_l"), dirPe = V3(Math.cos(phi), Math.sin(phi), 0);
      const alvo = H.clone().add(dirPe.clone().multiplyScalar(0.85));
      for (const l of ["l", "r"]) {
        const S = ondeEsta("upperarm_" + l), sz = ab_lado(l);
        const vDeitado = V3(-1, 0.06, 0), vV = alvo.clone().sub(S).setZ(0).normalize();
        const d = vDeitado.clone().lerp(vV, ab_suave(k * 1.15)).normalize();
        ab_braco(l, d, 0.505, V3(0, 0, -sz), V3(0, 1, 0).add(V3(0, 0, sz * 0.3)));
      }
    },
  },
  ab_deadbug: {
    nome: "Dead bug",
    musc: { abdomen: 1, lombar: 0.1 },
    dica: "Lombar colada no chão, braços pro teto e joelhos a 90°. Estica o braço de um lado e a perna do outro sem deixar a lombar subir, volta ao centro e troca.",
    cam: { alvo: V3(0.05, 0.4, 0), dist: 4.2, yaw: 32, pitch: 24 },
    cena(g) { g.add(ab_tapete(0.1, 2.5)); },
    fase(rel) { return ab_alt(rel, 4.2, "braço esquerdo e perna direita estendem", "braço direito e perna esquerda estendem", "volta ao centro", 0.55); },
    pose(t) {
      zera();
      const s = 2 * t - 1, eR = ab_suave(Math.max(0, s)), eL = ab_suave(Math.max(0, -s)); // eR: braço direito + perna esquerda estendem
      ab_costas(0.12, { flex: 0.12, pesc: 0.22 });
      const perna1 = (l, e) => ab_pernaSag(l, (88 - 70 * e) * Math.PI / 180, (90 - 84 * e) * Math.PI / 180);
      perna1("l", eR); perna1("r", eL); // perna esquerda com braço direito
      for (const l of ["l", "r"]) {
        const e = l === "r" ? eR : eL, a = (e * 76) * Math.PI / 180; // 0 = pro teto, 76° = quase deitado acima da cabeça
        ab_braco(l, V3(-Math.sin(a), Math.cos(a), 0), 0.5, V3(0, 0, -ab_lado(l)), V3(0.3, 0.2, ab_lado(l)));
      }
    },
  },
  ab_hollow: {
    nome: "Hollow hold",
    musc: { abdomen: 1, quadriceps: 0.4 },
    dica: "Lombar pressionada no chão, ombros e pernas fora do chão, braços esticados atrás da cabeça. Corpo em forma de banana e respiração curta; se a lombar subir, dobra os joelhos.",
    cam: { alvo: V3(0.1, 0.3, 0), dist: 4.1, yaw: 30, pitch: 22 },
    cena(g) { g.add(ab_tapete(0.1, 2.6)); },
    fase(rel) { const w = Math.sin(rel * 1.4); return { t: 0.5 + 0.03 * w, f: "segura", esforco: 0.85 + 0.05 * w }; },
    pose(t) {
      zera();
      const b = t - 0.5;
      ab_costas(0.12, { inc: -0.1, flex: 0.45 + b * 0.6, y: 0.012, pesc: 0.2 });
      const phi = (21 + b * 20) * Math.PI / 180;
      for (const l of ["l", "r"]) ab_pernaSag(l, phi, 0.1, 0.55);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) ab_braco(l, V3(-Math.cos(0.33), Math.sin(0.33), 0), 0.505, V3(0, 0, -ab_lado(l)), V3(0, 1, 0));
    },
  },
  ab_barra: {
    nome: "Elevação de pernas na barra",
    musc: { abdomen: 1, antebraco: 0.5, quadriceps: 0.4 },
    dica: "Pendurado na barra, ombros firmes e sem balançar. Sobe as pernas retas até a linha do quadril ou mais e, no fim, enrola a pelve pra cima; desce devagar, sem embalo.",
    cam: { alvo: V3(0.2, 1.15, 0), dist: 5.2, yaw: 55, pitch: 8 },
    cena(g) { g.add(K.piso(3, 2.4)); g.add(K.barraFixa({ alt: AB_BARRA, larg: 1.2 }).g); },
    pose(t) {
      zera();
      const k = 1 - t, rho = 0.55 * k;
      corpoEm(V3(0, 1.2, 0), V3(-Math.sin(rho), Math.cos(rho), 0), V3(Math.cos(rho), Math.sin(rho), 0));
      gira("spine_01", EX, rho * 0.3); gira("spine_02", EX, rho * 0.35); gira("spine_03", EX, rho * 0.35); // tronco volta pra vertical
      B.pelvis.updateMatrixWorld(true);
      ab_ancora(V3(-0.02, AB_BARRA - 0.575, 0));
      const phi = (-86 + 100 * k) * Math.PI / 180;
      for (const l of ["l", "r"]) ab_pernaSag(l, phi, (8 + 6 * k) * Math.PI / 180, 0.8);
      for (const l of ["l", "r"]) agarra(l, { ponto: V3(0, AB_BARRA, ab_lado(l) * 0.22), eixo: V3(0, 0, -ab_lado(l)), palma: V3(1, 0, 0), R: 0.016, polo: V3(-1, -0.3, ab_lado(l) * 0.6) });
    },
  },
  ab_paralela: {
    nome: "Elevação de joelhos na paralela",
    musc: { abdomen: 1, antebraco: 0.3, quadriceps: 0.35 },
    dica: "Apoiado nas paralelas com os braços esticados e ombros pra baixo. Sobe os joelhos até o peito enrolando o quadril, sem balançar o tronco, e desce controlando.",
    cam: { alvo: V3(0.15, 1.0, 0), dist: 5.0, yaw: 50, pitch: 8 },
    cena(g) { g.add(K.piso(3, 2.4)); g.add(K.paralelas({ alt: AB_PARAL, abre: 0.52, comp: 0.9 }).g); },
    pose(t) {
      zera();
      const k = 1 - t, rho = 0.5 * k;
      corpoEm(V3(0, 1.2, 0), V3(-Math.sin(rho), Math.cos(rho), 0), V3(Math.cos(rho), Math.sin(rho), 0));
      gira("spine_01", EX, rho * 0.3); gira("spine_02", EX, rho * 0.35); gira("spine_03", EX, rho * 0.35);
      B.pelvis.updateMatrixWorld(true);
      ab_ancora(V3(0.0, AB_PARAL + 0.56, 0));
      const phi = (-84 + 120 * k) * Math.PI / 180;
      for (const l of ["l", "r"]) ab_pernaSag(l, phi, (14 + 96 * k) * Math.PI / 180, 0.8);
      for (const l of ["l", "r"]) agarra(l, { ponto: V3(0.02, AB_PARAL, ab_lado(l) * 0.26), eixo: V3(1, 0, 0), palma: V3(0, -1, ab_lado(l) * -0.35), R: 0.022, polo: V3(-0.2, -0.3, ab_lado(l) * 1) });
    },
  },
  ab_prancha: {
    nome: "Prancha frontal",
    musc: { abdomen: 1, lombar: 0.4, gluteo: 0.4, deltoide: 0.35 },
    dica: "Cotovelos sob os ombros, corpo em linha reta da cabeça aos calcanhares. Contrai abdômen e glúteo, sem deixar o quadril cair nem subir, e respira curto.",
    cam: { alvo: V3(0.25, 0.3, 0), dist: 4.0, yaw: 40, pitch: 8 },
    cena(g) { g.add(ab_tapete(0.15, 2.5, 0.9)); },
    fase(rel) { const w = Math.sin(rel * 1.6); return { t: 0.5 + 0.5 * w * 0.04, f: "segura", esforco: 0.8 + 0.06 * w }; },
    pose(t) {
      zera();
      const S = V3(0.72, 0.33 + (t - 0.5) * 0.04, 0), A = ab_prono(S, 0.236).A;
      for (const l of ["l", "r"]) {
        const s = ab_lado(l);
        perna(l, V3(A.x, A.y, s * 0.09), V3(0, -1, 0)); ab_pe(l, V3(0.15, -1, 0), -1.2);
        ab_mao(l, V3(S.x + 0.27, 0.05, s * 0.16), V3(-1, -0.6, 0), V3(1, 0, 0), V3(0, -1, 0), 0.05);
      }
    },
  },
  ab_prancha_lat: {
    nome: "Prancha lateral",
    musc: { obliquo: 1, abdomen: 0.6, gluteo: 0.5, deltoide: 0.4 },
    dica: "De lado, cotovelo sob o ombro e pés empilhados. Sobe o quadril até o corpo formar uma linha reta e segura, sem deixar o quadril girar pra frente nem cair.",
    cam: { alvo: V3(0.0, 0.3, 0), dist: 4.2, yaw: 12, pitch: 22 },
    cena(g) { g.add(ab_tapete(0.0, 2.5, 0.9)); },
    fase(rel) { const w = Math.sin(rel * 1.6); return { t: 0.5 + 0.5 * w * 0.04, f: "segura", esforco: 0.8 + 0.06 * w }; },
    pose(t) {
      zera();
      const Sl = V3(0.55, 0.335 + (t - 0.5) * 0.04, 0), Ay = 0.1, Ld = 0.905;
      const geo = (th) => { const x = V3(Math.sin(th), -Math.cos(th), 0), u = V3(Math.cos(th), Math.sin(th), 0);
        const Sm = Sl.clone().sub(x.clone().multiplyScalar(0.195)); return { x, u, Sm, Hl: Sm.clone().sub(u.clone().multiplyScalar(0.512)).add(x.clone().multiplyScalar(0.118)) }; };
      let lo = -0.3, hi = 0.9;
      for (let i = 0; i < 40; i++) { const m = (lo + hi) / 2; if (geo(m).Hl.y - Ay - Ld * Math.sin(m) > 0) lo = m; else hi = m; }
      const Ax = geo((lo + hi) / 2).Hl.x - Ld * Math.cos((lo + hi) / 2);
      const th = (lo + hi) / 2, g = geo(th);
      corpoEm(g.Sm.clone().sub(g.u.clone().multiplyScalar(0.486)), g.u, V3(0, 0, 1));
      B.pelvis.updateMatrixWorld(true);
      B.pelvis.position.add(Sl.clone().sub(ondeEsta("upperarm_l"))); B.pelvis.updateMatrixWorld(true);
      perna("l", V3(Ax, Ay, 0), V3(0, 0, 1)); perna("r", V3(Ax + 0.02, Ay + 0.1, 0), V3(0, 0, 1));
      ab_pe("l", V3(0, 0, 1)); ab_pe("r", V3(0, 0, 1));
      const E = V3(Sl.x, 0.065, 0);
      ab_mao("l", V3(E.x, 0.05, 0.26), V3(0, -1, 0), V3(0, 0, 1), V3(0, -1, 0), 0.05);
      ab_braco("r", V3(0.1, 1, 0.1), 0.505, V3(1, 0, 0), V3(-1, 0, 0));
    },
  },
  ab_prancha_toque: {
    nome: "Prancha com toque no ombro",
    musc: { abdomen: 1, obliquo: 0.7, deltoide: 0.5, peitoral: 0.4 },
    dica: "Prancha alta com os pés um pouco abertos. Tira uma mão do chão e toca o ombro oposto sem deixar o quadril balançar; troca de lado devagar.",
    cam: { alvo: V3(0.1, 0.35, 0), dist: 4.3, yaw: 45, pitch: 12 },
    cena(g) { g.add(ab_tapete(0.15, 2.6, 1.0)); },
    fase(rel) { return ab_alt(rel, 3.4, "toca o ombro esquerdo com a mão direita", "toca o ombro direito com a mão esquerda", "volta ao apoio", 0.7); },
    pose(t) {
      zera();
      const s = 2 * t - 1, eR = ab_suave(Math.max(0, s)), eL = ab_suave(Math.max(0, -s)); // eR: mão direita toca o ombro esquerdo
      const S = V3(0.7, 0.585, 0), A = ab_prono(S, 0.236).A;
      for (const l of ["l", "r"]) { const z = ab_lado(l); perna(l, V3(A.x, A.y, z * 0.14), V3(0, -1, 0)); ab_pe(l, V3(0.15, -1, 0), -1.2); }
      for (const l of ["l", "r"]) {
        const z = ab_lado(l), e = l === "r" ? eR : eL, ombroOp = ondeEsta("upperarm_" + (l === "r" ? "l" : "r"));
        const chao = V3(S.x + 0.02, 0.06, z * 0.2), toque = ombroOp.clone().add(V3(0.04, -0.06, 0));
        const W = chao.clone().lerp(toque, e);
        ab_mao(l, W, V3(-0.5, -0.5, z), V3(1, 0, 0).lerp(V3(0, 0, -z), e).normalize(), V3(0, -1, 0).lerp(V3(0, 0.2, 0.2 * z), e), 0.05);
      }
    },
  },
  ab_mountain: {
    nome: "Mountain climber",
    musc: { abdomen: 1, reto_femoral: 0.6, deltoide: 0.4, obliquo: 0.5 },
    dica: "Prancha alta, ombros sobre as mãos. Traz um joelho de cada vez em direção ao peito num ritmo constante, quadril baixo e abdômen firme.",
    cam: { alvo: V3(0.05, 0.35, 0), dist: 4.3, yaw: 35, pitch: 10 },
    cena(g) { g.add(ab_tapete(0.15, 2.6, 1.0)); },
    fase(rel) { return { t: 0.5 - 0.5 * Math.cos(2 * Math.PI * rel / 0.85), f: "alterna os joelhos", esforco: 0.85 }; },
    pose(t) {
      zera();
      const S = V3(0.7, 0.585, 0), A = ab_prono(S, 0.236).A;
      for (const l of ["l", "r"]) {
        const z = ab_lado(l), f = l === "l" ? t : 1 - t; // f = quanto o joelho está dentro
        const H = ondeEsta("thigh_" + l), ax = lerp(A.x, H.x + 0.14, f), ay = 0.236 + 0.05 * Math.sin(Math.PI * f) - 0.05 * f;
        perna(l, V3(ax, ay, z * 0.14), V3(1, -0.25, z * 0.1)); ab_pe(l, V3(0.15, -1, 0), -1.2);
        ab_maoChao(l, V3(S.x + 0.02, 0.06, z * 0.2));
      }
    },
  },
  ab_birddog: {
    nome: "Bird dog",
    musc: { lombar: 1, abdomen: 0.7, gluteo: 0.7, deltoide: 0.5 },
    dica: "Quatro apoios, mãos sob os ombros e joelhos sob o quadril. Estica o braço de um lado e a perna do lado oposto até a linha do tronco, sem girar o quadril; volta e troca.",
    cam: { alvo: V3(0.0, 0.4, 0), dist: 4.6, yaw: 35, pitch: 12 },
    cena(g) { g.add(ab_tapete(0.0, 2.8, 0.9)); },
    fase(rel) { return ab_alt(rel, 5.4, "braço esquerdo e perna direita estendidos", "braço direito e perna esquerda estendidos", "volta ao apoio", 0.55); },
    pose(t) {
      zera();
      const s = 2 * t - 1, eR = ab_suave(Math.max(0, s)), eL = ab_suave(Math.max(0, -s)); // eR: braço direito + perna esquerda
      const HY = 0.585, Kx = 0.0;
      corpoEm(V3(Kx + 0.026, HY, 0), V3(1, 0, 0), V3(0, -1, 0));
      gira("neck_01", EX, -0.25);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) {
        const z = ab_lado(l), eb = l === "r" ? eR : eL, ep = l === "r" ? eL : eR; // eb: braço dessa mão estendido; ep: perna desse lado estendida
        const a = ep * 86 * Math.PI / 180;
        ab_pernaDir(l, V3(-Math.sin(a), -Math.cos(a), 0), V3(-1, ep * 0.04, 0));
        ab_pe(l, V3(-1, -0.1, 0).lerp(V3(-0.1, -1, 0), ep).normalize());
        const b = eb * 88 * Math.PI / 180, d = V3(Math.sin(b), -Math.cos(b), 0);
        ab_braco(l, d, 0.515, V3(0, -1, 0).lerp(V3(0, 0, -z), eb), V3(-0.5, 0.2, z));
      }
    },
  },
  ab_roda: {
    nome: "Roda abdominal",
    musc: { abdomen: 1, dorsal: 0.5, lombar: 0.4, deltoide: 0.4 },
    dica: "De joelhos, mãos nos cabos e roda sob os ombros. Rola pra frente com o abdômen travado e a lombar neutra, até onde o corpo ficar quase reto, e volta puxando com o abdômen.",
    cam: { alvo: V3(0.75, 0.35, 0), dist: 5.0, yaw: 28, pitch: 14 },
    cena(g) {
      g.add(ab_tapete(0.75, 3.2, 0.9));
      const w = new THREE.Group(), r = 0.09;
      const rod = new THREE.Group(); // parte que gira
      const pneu = cil(r, 0.07, M.borracha, 40); pneu.rotation.x = Math.PI / 2; rod.add(pneu);
      const cubo = cil(0.05, 0.075, M.aco, 28); cubo.rotation.x = Math.PI / 2; rod.add(cubo);
      const marca = K.caixa(0.014, 0.034, 0.072, M.faixa, 0.004); marca.position.set(0, r - 0.017, 0); rod.add(marca);
      w.add(rod);
      const eixo = cil(0.012, 0.36, M.cromo, 14); eixo.rotation.x = Math.PI / 2; w.add(eixo);
      for (const s of [-1, 1]) { const pega = cil(0.019, 0.12, M.borracha, 18); pega.rotation.x = Math.PI / 2; pega.position.z = s * 0.165; w.add(pega); }
      this.roda = w; this.rod = rod; g.add(sombreia(w));
    },
    pose(t) {
      zera();
      const e = t, al = 78 * Math.pow(e, 1.25) * Math.PI / 180, be = (74 + 5 * e) * Math.PI / 180;
      const K0 = V3(0, 0.09, 0), Hh = K0.clone().add(V3(Math.sin(al), Math.cos(al), 0).multiplyScalar(COMP.thigh_l));
      const u = V3(Math.sin(be), Math.cos(be), 0), fr = V3(Math.cos(be), -Math.sin(be), 0);
      corpoEm(Hh.clone().add(u.clone().multiplyScalar(0.026)), u, fr);
      gira("neck_01", EX, -0.3);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { ab_pernaDir(l, V3(-Math.sin(al), -Math.cos(al), 0), V3(-1, 0, 0)); ab_pe(l, V3(-1, -0.15, 0)); }
      const Sm = ondeEsta("upperarm_l").add(ondeEsta("upperarm_r")).multiplyScalar(0.5), dy = Sm.y - 0.09;
      const xw = Sm.x + Math.sqrt(Math.max(0, 0.58 * 0.58 - dy * dy));
      this.roda.position.set(xw, 0.09, 0); this.rod.rotation.z = -xw / 0.09;
      for (const l of ["l", "r"]) agarra(l, { ponto: V3(xw, 0.09, ab_lado(l) * 0.165), eixo: V3(0, 0, -ab_lado(l)), palma: V3(0, -1, 0), R: 0.019, polo: V3(-0.3, 0.1, ab_lado(l)) });
    },
  },
  ab_flexlat: {
    nome: "Flexão lateral com halter",
    musc: { abdomen: 1, lombar: 0.4 },
    dica: "Em pé, halter na mão direita e mão esquerda atrás da cabeça. Inclina o tronco só pro lado, sem girar nem projetar o quadril, e volta contraindo o oblíquo do lado oposto.",
    cam: { alvo: V3(0, 1.0, 0), dist: 4.0, yaw: 90, pitch: 6 },
    cena(g) { g.add(tablado()); this.h = halter(0.8); g.add(this.h); },
    pose(t) {
      zera();
      const a = 0.42 * t;
      emPe(V3(0, ALT_QUADRIL - 0.015, 0), F0, 0.0);
      gira("spine_01", EZ, a * 0.3); gira("spine_02", EZ, a * 0.35); gira("spine_03", EZ, a * 0.35); gira("neck_01", EZ, -a * 0.25);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.13, fora: 0.2, poloFora: 0.2 });
      const E = esquerda(F0), S = ondeEsta("upperarm_r");
      agarra("r", { punho: S.clone().add(V3(0, -0.5, 0.02)), R: 0.016, eixo: F0.clone(), palma: E.clone(), polo: F0.clone().multiplyScalar(-1) });
      seguraHalter(this.h, "r");
      const hq = quadroDe("head"), hb = ondeEsta("head");
      ab_mao("l", hb.clone().add(hq.up.clone().multiplyScalar(0.05)).add(hq.esq.clone().multiplyScalar(0.15)).add(hq.fr.clone().multiplyScalar(0.03)), hq.esq.clone().add(hq.up.clone().multiplyScalar(0.2)),
        hq.up.clone().multiplyScalar(0.85).add(hq.fr.clone().multiplyScalar(-0.15)).add(hq.esq.clone().multiplyScalar(-0.5)), hq.esq.clone().multiplyScalar(-1));
    },
  },
  ab_pallof: {
    nome: "Pallof press",
    musc: { abdomen: 1, obliquo: 0.9 },
    dica: "De lado pra polia, na altura do peito. Empurra o pegador reto à frente e segura sem deixar o tronco girar pra dentro; volta devagar ao peito.",
    cam: { alvo: V3(0.3, 1.1, 0.4), dist: 4.6, yaw: 60, pitch: 10 },
    cena(g) {
      g.add(tablado());
      const T = K.torre({ alt: 1.25 }); T.g.position.set(0, 0, 1.5); T.g.rotation.y = Math.PI; g.add(T.g); this.T = T;
      const r = K.cilU(0.016, M.borracha); r.scale.y = 0.16; r.rotation.z = Math.PI / 2; g.add(r); this.pega = r;
    },
    fase(rel) {
      const c = 4.2, u = rel % c;
      if (u < 1.2) return { t: 1 - ab_suave(u / 1.2), f: "empurra à frente", esforco: 0.7 };
      if (u < 2.6) return { t: 0, f: "segura sem girar", esforco: 1 };
      if (u < 4.0) return { t: ab_suave((u - 2.6) / 1.4), f: "volta devagar", esforco: 0.7 };
      return { t: 1, f: "no peito", esforco: 0.4 };
    },
    pose(t) {
      zera();
      emPe(V3(0, ALT_QUADRIL - 0.015, 0), F0, 0.02);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.17, fora: 0.15, poloFora: 0.2 });
      const S = ondeEsta("upperarm_l").add(ondeEsta("upperarm_r")).multiplyScalar(0.5), hp = V3(0.2 + 0.42 * (1 - t), 1.25, 0.0);
      this.pega.position.copy(hp);
      for (const l of ["l", "r"]) agarra(l, { ponto: hp.clone().add(V3(0, 0, -ab_lado(l) * -0.0)).add(V3(ab_lado(l) * 0.0, 0, 0)), R: 0.016, eixo: F0.clone(), palma: V3(0, 0, -ab_lado(l)), polo: V3(-0.3, -1, ab_lado(l) * 0.5) });
      this.T.liga(hp.clone());
    },
  },
  ab_lenhador: {
    nome: "Lenhador na polia",
    musc: { obliquo: 1, abdomen: 0.8 },
    dica: "De lado pra polia alta. Puxa o pegador em diagonal, do ombro de cima até o joelho oposto, girando o tronco e o pé de apoio; braços firmes, o giro vem do core.",
    cam: { alvo: V3(0.1, 1.0, 0.3), dist: 4.8, yaw: 62, pitch: 10 },
    cena(g) {
      g.add(tablado());
      const T = K.torre({ alt: 1.95 }); T.g.position.set(0, 0, 1.6); T.g.rotation.y = Math.PI; g.add(T.g); this.T = T;
      const r = K.cilU(0.016, M.borracha); r.scale.y = 0.2; r.rotation.x = Math.PI / 2; g.add(r); this.pega = r;
    },
    pose(t) {
      zera();
      const k = t, tw = -0.55 + 1.1 * (1 - t); // t=1: girado pra polia (alto); t=0: fim da puxada
      emPe(V3(0, ALT_QUADRIL - 0.03 * (1 - t), 0), F0, 0.08 * (1 - t));
      gira("spine_01", EY, tw * 0.3); gira("spine_02", EY, tw * 0.35); gira("spine_03", EY, tw * 0.35); gira("spine_02", EX, 0.18 * (1 - t));
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.2, fora: 0.45, poloFora: 0.45 });
      const hp = V3(0.12, 1.62, 0.3).lerp(V3(0.3, 0.55, -0.28), 1 - k).add(V3(0.1 * Math.sin(Math.PI * (1 - k)), 0, 0.1 * Math.sin(Math.PI * (1 - k))));
      this.pega.position.copy(hp);
      for (const l of ["l", "r"]) agarra(l, { ponto: hp.clone().add(V3(ab_lado(l) * 0.0, 0, 0)).add(V3(0, 0, ab_lado(l) * 0.07)), R: 0.016, eixo: V3(1, 0, 0), palma: V3(0, -1, 0), polo: V3(-0.5, -0.5, ab_lado(l)) });
      this.T.liga(hp.clone());
    },
  },
  ab_russian: {
    nome: "Russian twist",
    musc: { obliquo: 1, abdomen: 0.8 },
    dica: "Sentado, tronco inclinado pra trás e pés fora do chão. Gira o tronco inteiro de um lado pro outro levando a bola ao lado do quadril, sem só balançar os braços.",
    cam: { alvo: V3(0.2, 0.55, 0), dist: 4.0, yaw: 40, pitch: 22 },
    cena(g) { g.add(ab_tapete(0.15, 2.0, 0.9)); this.bola = K.bolaMed(0.11); g.add(this.bola); },
    fase(rel) { return ab_alt(rel, 2.6, "bola ao lado esquerdo", "bola ao lado direito", "passa pelo centro", 0.7); },
    pose(t) {
      zera();
      const s = 2 * t - 1, b = 0.62, u = V3(-Math.sin(b), Math.cos(b), 0), fr = V3(Math.cos(b), Math.sin(b), 0);
      corpoEm(V3(0, ABY + 0.125, 0), u, fr);
      gira("spine_01", EX, 0.05); gira("spine_02", EX, 0.1); gira("neck_01", EX, -0.1);
      gira("spine_01", EY, -0.2 * s); gira("spine_02", EY, -0.3 * s); gira("spine_03", EY, -0.4 * s);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) ab_pernaDir(l, V3(0.78, 0.62, 0), V3(0.8, -0.55, 0));
      const c = quadroDe("spine_03"), P0 = ondeEsta("spine_03"), bp = P0.clone().add(c.up.clone().multiplyScalar(0.12)).add(c.fr.clone().multiplyScalar(0.3));
      this.bola.position.copy(bp);
      for (const l of ["l", "r"]) { const sl = l === "l" ? 1 : -1;
        ab_mao(l, bp.clone().add(c.esq.clone().multiplyScalar(sl * 0.13)).add(c.fr.clone().multiplyScalar(-0.1)), c.esq.clone().multiplyScalar(sl).add(c.up.clone().multiplyScalar(-0.3)), c.fr.clone(), c.esq.clone().multiplyScalar(-sl), 0.35); }
    },
  },
  ab_polia: {
    nome: "Abdominal na polia (crunch)",
    musc: { abdomen: 1, lombar: 0.2 },
    dica: "De joelhos de frente pra polia alta, corda ao lado da cabeça. Enrola a coluna levando os cotovelos aos joelhos, quadril parado; o movimento é do abdômen, não dos braços.",
    cam: { alvo: V3(0.5, 0.8, 0), dist: 4.8, yaw: 35, pitch: 12 },
    cena(g) {
      g.add(ab_tapete(0.4, 2.6, 0.9));
      const T = K.torre({ alt: 2.0 }); T.g.position.set(1.3, 0, 0); T.g.rotation.y = -Math.PI / 2; g.add(T.g); this.T = T;
      this.corda = K.corda(); g.add(this.corda);
    },
    pose(t) {
      zera();
      const k = 1 - t, b = 0.35 * k, u = V3(Math.sin(b), Math.cos(b), 0), fr = V3(Math.cos(b), -Math.sin(b), 0), Hh = V3(0, ABY + 0.075 + COMP.thigh_l, 0);
      corpoEm(Hh.clone().add(u.clone().multiplyScalar(0.026)), u, fr);
      gira("spine_01", EX, 0.3 * k); gira("spine_02", EX, 0.4 * k); gira("spine_03", EX, 0.4 * k); gira("neck_01", EX, 0.2 * k);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { ab_pernaDir(l, V3(0, -1, 0), V3(-1, 0, 0)); ab_pe(l, V3(-1, -0.15, 0)); }
      const hq = quadroDe("head"), hb = ondeEsta("head"), pts = [];
      for (const l of ["l", "r"]) { const sl = l === "l" ? 1 : -1;
        const pt = hb.clone().add(hq.up.clone().multiplyScalar(0.1)).add(hq.esq.clone().multiplyScalar(sl * 0.14)).add(hq.fr.clone().multiplyScalar(0.05));
        agarra(l, { ponto: pt, R: 0.012, eixo: hq.up.clone(), palma: hq.esq.clone().multiplyScalar(-sl), polo: hq.fr.clone().multiplyScalar(-0.3).add(V3(0, -1, 0)) }); pts.push(pt); }
      const top = pts[0].clone().add(pts[1]).multiplyScalar(0.5).add(V3(0.02, 0.1, 0));
      this.corda.position.copy(top).sub(V3(0, 0.04, 0));
      this.corda.userData.abre(pts[0], pts[1]);
      this.T.liga(top);
    },
  },
  ab_maquina: {
    nome: "Abdominal na máquina",
    musc: { abdomen: 1 },
    dica: "Sentado com as costas no encosto e pés firmes. Enrola o tronco pra frente empurrando o apoio do peito com o abdômen, sem puxar com os braços, e volta devagar.",
    cam: { alvo: V3(0, 0.8, 0), dist: 4.2, yaw: 55, pitch: 12 },
    cena(g) {
      g.add(K.piso(2.6, 2.0));
      g.add(K.caixa(1.3, 0.05, 0.6, M.quadro, 0.01).translateX(-0.2).translateY(0.025));
      const as = K.assento(0.42, 0.42, 0.09); as.position.set(0.05, 0.41, 0); g.add(as);
      g.add(K.viga(V3(0.05, 0.03, 0), V3(0.05, 0.37, 0), 0.08));
      const enc = K.caixa(0.1, 0.6, 0.36, M.estofado, 0.04); enc.position.set(-0.24, 0.8, 0); enc.rotation.z = -0.18; g.add(enc);
      g.add(K.viga(V3(-0.34, 0.03, 0), V3(-0.3, 1.25, 0), 0.08));
      for (const z of [-0.2, 0.2]) g.add(K.tubo(V3(-0.3, 1.2, z), V3(-0.3, 1.2, z * 1.5), 0.02, M.aco));
      const pil = K.pilha(); pil.position.set(-0.85, 0.03, 0); pil.rotation.y = Math.PI / 2; g.add(pil); this.pil = pil;
      this.pad = K.rolo(0.5, 0.07); g.add(this.pad); this.pad.rotation.y = Math.PI / 2;
      this.b1 = K.tubo(V3(), V3(0, 1, 0), 0.025, M.quadro); this.b2 = K.tubo(V3(), V3(0, 1, 0), 0.025, M.quadro); g.add(this.b1, this.b2);
      g.add(K.caixa(0.07, 0.07, 0.56, M.quadro, 0.02).translateX(-0.3).translateY(1.2));
      g.add(K.viga(V3(0.55, 0.03, -0.2), V3(0.55, 0.1, -0.2), 0.05)); g.add(K.rolo(0.45, 0.035).translateX(0.55).translateY(0.11));
    },
    pose(t) {
      zera();
      const k = 1 - t, b = -0.15 + 0.2 * k, u = V3(Math.sin(b), Math.cos(b), 0), fr = V3(Math.cos(b), -Math.sin(b), 0);
      corpoEm(V3(0.0, 0.56, 0), u, fr);
      gira("spine_01", EX, 0.2 * k); gira("spine_02", EX, 0.35 * k); gira("spine_03", EX, 0.4 * k); gira("neck_01", EX, 0.15 * k - 0.05);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { const s = ab_lado(l); perna(l, V3(0.5, ALT_TORN + 0.03, s * 0.17), V3(0.3, 1, 0)); pe(l, F0); }
      const c = quadroDe("spine_03"), P0 = ondeEsta("spine_03"), pp = P0.clone().add(c.fr.clone().multiplyScalar(0.16)).add(c.up.clone().multiplyScalar(0.1));
      this.pad.position.copy(pp);
      const pv = V3(-0.3, 1.2, 0);
      K.poe(this.b1, V3(pv.x, pv.y, -0.25), pp.clone().add(V3(0, 0, -0.25))); K.poe(this.b2, V3(pv.x, pv.y, 0.25), pp.clone().add(V3(0, 0, 0.25)));
      this.pil.userData.sobe(0.14 * k);
      for (const l of ["l", "r"]) { const sl = l === "l" ? 1 : -1;
        ab_mao(l, pp.clone().add(c.up.clone().multiplyScalar(0.09)).add(c.esq.clone().multiplyScalar(sl * 0.14)).add(c.fr.clone().multiplyScalar(-0.04)), c.esq.clone().multiplyScalar(sl).add(c.fr.clone().multiplyScalar(-1)), c.fr.clone().multiplyScalar(0.7).add(c.esq.clone().multiplyScalar(-sl * 0.5)), c.up.clone().multiplyScalar(-1), 0.3); }
    },
  },
});
Object.assign(FOCOS, {
  ab_supra: () => [["abdomen", 1], ["obliquo", 0.45], ["reto_femoral", 0.3], ["serratil", 0.2]],
  ab_declinado: () => [["abdomen", 1], ["obliquo", 0.5], ["reto_femoral", 0.6], ["serratil", 0.2]],
  ab_infra: () => [["abdomen", 1], ["reto_femoral", 0.6], ["obliquo", 0.4]],
  ab_bicicleta: () => [["abdomen", 1], ["obliquo", 0.9], ["reto_femoral", 0.35], ["serratil", 0.2]],
  ab_canivete: () => [["abdomen", 1], ["reto_femoral", 0.7], ["obliquo", 0.5]],
  ab_deadbug: () => [["abdomen", 1], ["obliquo", 0.5], ["reto_femoral", 0.3], ["serratil", 0.2]],
  ab_hollow: () => [["abdomen", 1], ["obliquo", 0.6], ["reto_femoral", 0.5], ["serratil", 0.2]],
  ab_barra: () => [["abdomen", 1], ["reto_femoral", 0.75], ["obliquo", 0.55], ["antebraco", 0.4], ["serratil", 0.3]],
  ab_paralela: () => [["abdomen", 1], ["reto_femoral", 0.6], ["obliquo", 0.5], ["serratil", 0.35]],
  ab_prancha: () => [["abdomen", 1], ["obliquo", 0.7], ["lombar", 0.4], ["gluteo_max", 0.45], ["serratil", 0.55], ["deltoide_ant", 0.4], ["reto_femoral", 0.35]],
  ab_prancha_lat: () => [["obliquo", 1], ["abdomen", 0.55], ["lombar", 0.75], ["gluteo_med", 0.6], ["deltoide_lat", 0.4], ["serratil", 0.35]],
  ab_prancha_toque: () => [["abdomen", 1], ["obliquo", 0.7], ["serratil", 0.6], ["deltoide_ant", 0.55], ["peitoral_med", 0.4], ["triceps_lateral", 0.35]],
  ab_mountain: () => [["abdomen", 1], ["reto_femoral", 0.7], ["obliquo", 0.55], ["serratil", 0.45], ["deltoide_ant", 0.4], ["gluteo_max", 0.3]],
  ab_birddog: () => [["lombar", 1], ["gluteo_max", 0.7], ["abdomen", 0.45], ["deltoide_ant", 0.5], ["obliquo", 0.35], ["isquio", 0.4]],
  ab_roda: () => [["abdomen", 1], ["obliquo", 0.6], ["serratil", 0.5], ["dorsal", 0.5], ["reto_femoral", 0.55], ["lombar", 0.4], ["deltoide_ant", 0.4]],
  ab_flexlat: () => [["obliquo", 1], ["abdomen", 0.45], ["lombar", 0.5], ["gluteo_med", 0.25], ["antebraco", 0.3]],
  ab_pallof: () => [["obliquo", 1], ["abdomen", 0.75], ["serratil", 0.4], ["deltoide_ant", 0.4], ["lombar", 0.3]],
  ab_lenhador: () => [["obliquo", 1], ["abdomen", 0.8], ["serratil", 0.4], ["deltoide_ant", 0.45], ["gluteo_med", 0.3], ["lombar", 0.3]],
  ab_russian: () => [["obliquo", 1], ["abdomen", 0.75], ["reto_femoral", 0.4], ["serratil", 0.3], ["lombar", 0.3]],
  ab_polia: () => [["abdomen", 1], ["obliquo", 0.55], ["reto_femoral", 0.3], ["serratil", 0.3]],
  ab_maquina: () => [["abdomen", 1], ["obliquo", 0.5], ["reto_femoral", 0.3]],
});
}

// ===== moldes/costas.js =====
{ // moldes/costas.js  (prefixo co_)
// ---------- ajudantes (só deste arquivo) ----------
const zc = (l) => (l === "l" ? -1 : 1);          // lado em Z (esquerdo = -Z)
const sc = (l) => (l === "l" ? 1 : -1);          // sinal 's' do motor (esquerdo = +1)
const un = (v) => v.clone().normalize();
const ALC = COMP.upperarm_l + COMP.lowerarm_l;   // ombro -> punho esticado
const ombrosC = () => ondeEsta("upperarm_l").add(ondeEsta("upperarm_r")).multiplyScalar(0.5);
const sm = (x) => { x = Math.min(1, Math.max(0, x)); return x * x * (3 - 2 * x); };
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
function recentra(alvo) { // translada o corpo todo: o centro dos ombros passa a ficar em alvo
  B.pelvis.updateMatrixWorld(true);
  B.pelvis.position.add(alvo.clone().sub(ombrosC())); B.pelvis.updateMatrixWorld(true);
}
// pilha da polia: mede o cabo nos dois extremos e deixa a pilha em repouso no mais curto
function prepCurso(m) {
  if (!m.torre || m.ref) return; m.ref = true;
  m.calc(0); const a = m.torre.cabo.scale.y; m.calc(1); const b = m.torre.cabo.scale.y;
  m.torre.zeraCurso(); m.calc(a < b ? 0 : 1);
}
// torre de polia em pé em (x, z) com a saída do cabo apontando pro -X (pro atleta)
function torreEm(g, { alt = 2.0, altura = 2.2, x = 0.6, z = 0 } = {}) {
  const t = K.torre({ alt, altura }); t.g.position.set(x, 0, z); t.g.rotation.y = -Math.PI / 2; g.add(t.g); return t;
}
// base de uma pega rígida: origem no centro da pegada, X = lateral, Y = pro cabo
function baseDe(obj, centro, lat, pro) {
  const X = un(lat), Y = un(pro.clone().sub(X.clone().multiplyScalar(pro.dot(X)))), Z = X.clone().cross(Y);
  obj.position.copy(centro); obj.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(X, Y, Z)); obj.updateMatrixWorld(true);
  return { X, Y, Z };
}
// rack de potência: 4 montantes, vigas de cima e barras de segurança (pinos) na altura pinY (topo do pino)
function racke(g, pinY) {
  const alt = 2.1, xs = [-0.55, 0.45], zs = [-0.62, 0.62];
  for (const x of xs) for (const z of zs) g.add(K.caixa(0.08, alt, 0.08).translateX(x).translateY(alt / 2).translateZ(z));
  for (const z of zs) { g.add(K.caixa(1.3, 0.05, 0.1).translateX(-0.05).translateY(0.025).translateZ(z)); g.add(K.caixa(1.0, 0.08, 0.08).translateX(-0.05).translateY(alt).translateZ(z)); }
  for (const x of xs) g.add(K.caixa(0.08, 0.08, 1.28).translateX(x).translateY(alt));
  for (const z of zs) {
    const pino = K.caixa(1.0, 0.04, 0.07, M.aco, 0.006); pino.position.set(-0.05, pinY - 0.02, z); g.add(pino);
    for (const x of xs) g.add(K.caixa(0.1, 0.12, 0.1, M.aco, 0.008).translateX(x).translateY(pinY - 0.04).translateZ(z));
  }
  return g;
}
// pé orientado por direção (dedos apontam pra dir); a dobradiça é o eixo lateral
function peDir(l, dir) { const d = un(dir), h = Math.hypot(d.x, d.z) || 1; mira("foot_" + l, d, V3(d.z / h, 0, -d.x / h), EX); }

// @@MOLDES
Object.assign(MOLDES, {
  // ================= Pendlay: barra no chão a cada repetição, tronco paralelo ao chão =================
  co_pendlay: {
    nome: "Remada Pendlay",
    musc: { dorsal: 1, trapezio: 0.9, biceps: 0.5, deltoide: 0.5, lombar: 0.6, antebraco: 0.45 },
    dica: "Tronco quase paralelo ao chão e coluna neutra, barra parada no chão a cada repetição. Puxa explosivo até a parte baixa do peito, cotovelo pra trás, e solta de volta até a barra encostar no chão.",
    cam: { alvo: V3(0.05, 0.62, 0), dist: 4.2, yaw: 20, pitch: 12 },
    cena(g) { g.add(tablado()); this.bar = barra(2); g.add(this.bar); },
    pose(t) {
      zera();
      const k = 1 - t, sk = sm(k);                   // 1 = barra no peito
      const incl = 1.42 - 0.12 * sk;                  // tronco ~15-20° acima do horizontal; sobe um tiquinho na puxada
      emPe(V3(-0.45 + 0.03 * sk, 0.70 + 0.03 * sk, 0), F0, incl * 0.82);
      gira("spine_01", EX, incl * 0.05); gira("spine_02", EX, incl * 0.07); gira("spine_03", EX, incl * 0.05); gira("neck_01", EX, -0.62); gira("head", EX, -0.1);
      for (const l of ["l", "r"]) gira("clavicle_" + l, EY, (l === "l" ? 1 : -1) * 0.14 * sk);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.15, fora: 0.22, poloFora: 0.3, recuo: 0 });
      const c = quadroDe("spine_03"), ombros = ombrosC();
      const solto = ombros.clone().add(V3(0, -(ALC * 0.985 + 0.065), 0)); solto.y = Math.max(0.225, solto.y);
      const peito = ondeEsta("spine_03").add(c.fr.clone().multiplyScalar(0.115));
      const bar = solto.clone().lerp(peito, sk);
      this.bar.position.copy(bar); this.bar.rotation.set(0, Math.PI / 2, 0);
      for (const l of ["l", "r"]) {
        const s = sc(l), E = esquerda(F0);
        agarra(l, { ponto: bar.clone().add(E.clone().multiplyScalar(s * 0.27)), R: 0.014, eixo: E.clone().multiplyScalar(-s), palma: F0.clone().multiplyScalar(-1),
          polo: V3(-1, 0.5, -zc(l) * 0.55) });
      }
    },
  },

  // ================= Good morning: barra nas costas, quadril vai pra trás, tronco desce quase paralelo =================
  co_goodmorning: {
    nome: "Good morning",
    musc: { lombar: 1, posterior: 0.9, gluteo: 0.85, trapezio: 0.3, abdomen: 0.3 },
    dica: "Barra apoiada no trapézio, joelho levemente dobrado e fixo. Empurra o quadril pra trás como quem fecha uma porta com a bunda, tronco desce reto até quase paralelo ao chão e sobe estendendo o quadril.",
    cam: { alvo: V3(0, 0.95, 0), dist: 4.4, yaw: 0, pitch: 10 },
    cena(g) { g.add(tablado()); this.bar = barra(2); g.add(this.bar); },
    pose(t) {
      zera();
      const e = sm(t), incl = 0.04 + e * 1.22, alt = ALT_QUADRIL - 0.02 - e * 0.075, recuo = 0.01 + e * 0.32;
      emPe(V3(-recuo, alt, 0), F0, incl * 0.86);
      gira("spine_02", EX, incl * 0.05); gira("spine_03", EX, incl * 0.05); gira("neck_01", EX, -incl * 0.28); gira("head", EX, -incl * 0.1);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.14, fora: 0.22, poloFora: 0.3 });
      const c = quadroDe("spine_03"), pescoco = ondeEsta("neck_01");
      const bar = pescoco.clone().add(c.fr.clone().multiplyScalar(-0.1)).add(c.up.clone().multiplyScalar(-0.085));
      this.bar.position.copy(bar); this.bar.quaternion.setFromUnitVectors(EX, c.esq);
      for (const l of ["l", "r"]) {
        const s = sc(l);
        agarra(l, { ponto: bar.clone().add(c.esq.clone().multiplyScalar(s * 0.36)), eixo: c.esq.clone().multiplyScalar(-s),
          palma: c.up.clone().add(c.fr.clone().multiplyScalar(0.9)),
          polo: c.up.clone().multiplyScalar(-1).add(c.fr.clone().multiplyScalar(-0.6)).add(c.esq.clone().multiplyScalar(s * 0.3)) });
      }
    },
  },
  // ================= Rack pull: terra parcial, barra sai dos pinos na altura do joelho =================
  co_rackpull: {
    nome: "Rack pull",
    musc: { dorsal: 0.6, trapezio: 1, lombar: 0.9, gluteo: 0.85, posterior: 0.7, antebraco: 0.6 },
    dica: "Barra nos pinos na altura do joelho. Coluna neutra, escápulas puxadas pra baixo e pra trás, empurra o chão e estende o quadril até travar em pé, trapézio e costas firmes. Desce a barra rente às coxas até pousar nos pinos.",
    cam: { alvo: V3(0, 0.85, 0), dist: 4.5, yaw: 0, pitch: 10 },
    PIN: 0.56,
    cena(g) { g.add(tablado()); racke(g, this.PIN); this.bar = barra(2); g.add(this.bar); },
    pose(t) {
      zera();
      const e = sm(t), incl = 0.03 + e * 1.17, alt = ALT_QUADRIL - 0.015 - e * 0.10, recuo = 0.01 + e * 0.37;
      emPe(V3(-recuo, alt, 0), F0, incl * 0.78);
      gira("spine_02", EX, incl * 0.07); gira("spine_03", EX, incl * 0.06); gira("neck_01", EX, -incl * 0.4); gira("head", EX, -incl * 0.06);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.15, fora: 0.2, poloFora: 0.25 });
      const ombros = ombrosC(), by = Math.max(this.PIN + 0.0135, ombros.y - (ALC * 0.985 + 0.07));
      const bar = V3(0.07 + 0.05 * (1 - e), by, 0);
      this.bar.position.copy(bar); this.bar.rotation.set(0, Math.PI / 2, 0);
      for (const l of ["l", "r"]) {
        const s = sc(l), E = esquerda(F0);
        agarra(l, { ponto: bar.clone().add(E.clone().multiplyScalar(s * 0.25)), R: 0.014, eixo: E.clone().multiplyScalar(-s), palma: F0.clone().multiplyScalar(-1),
          polo: F0.clone().multiplyScalar(-1).add(E.clone().multiplyScalar(s * 0.4)) });
      }
    },
  },

  // ================= Superman no solo: peito, braços e pernas saem do colchonete juntos =================
  co_superman: {
    nome: "Superman no solo",
    musc: { lombar: 1, gluteo: 0.7, trapezio: 0.55, posterior: 0.5, deltoide: 0.35 },
    dica: "Deitado de barriga pra baixo, braços esticados à frente. Sobe peito, braços e pernas juntos, olhando pro chão com o pescoço neutro, segura 2 s apertando lombar e glúteo e desce sem tombar.",
    cam: { alvo: V3(0.05, 0.22, 0), dist: 4.8, yaw: 28, pitch: 20 },
    cena(g) { g.add(K.piso(3.2, 2.0)); const c = K.colchonete(2.3, 0.75); c.position.set(0, 0.012, 0); g.add(c); },
    pose(t) {
      zera();
      const k = 1 - t, sk = sm(k), L = 0.02;        // k = 1: tudo no ar
      corpoEm(V3(-0.12, 0.155 + 0.02 * sk, 0), V3(1, 0.03 * sk, 0), V3(0, -1, 0.0));
      gira("spine_01", EX, -0.09 * sk); gira("spine_02", EX, -0.13 * sk); gira("spine_03", EX, -0.16 * sk);
      gira("neck_01", EX, -0.08 * sk); gira("head", EX, 0.03 * sk);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { // pernas esticadas pra trás, sobem com o glúteo
        const s = sc(l), q = ondeEsta("thigh_" + l);
        perna(l, V3(q.x - 0.905 * Math.cos(0.24 * sk), 0.115 + 0.905 * Math.sin(0.24 * sk) + 0.0, zc(l) * 0.1), V3(0, 1, 0));
        peDir(l, V3(-0.9, -0.3, 0));
      }
      // braços esticados à frente, um pouco abertos, palma pra baixo
      const ombros = ombrosC();
      for (const l of ["l", "r"]) {
        const S = ondeEsta("upperarm_" + l);
        const alvo = V3(S.x + ALC * 0.99, 0.1 + 0.2 * sk, zc(l) * 0.24);
        braco(l, alvo, V3(0, 1, zc(l) * 0.2));
        mao(l, V3(1, 0, 0), V3(0, -1, 0));
      }
    },
  },

  // ================= Hiperextensão lombar: banco romano 38°, quadril dobra e estende =================
  co_hiper: {
    nome: "Hiperextensão lombar",
    musc: { lombar: 1, gluteo: 0.8, posterior: 0.75, trapezio: 0.2 },
    dica: "Almofada na altura do quadril, calcanhar preso, braços cruzados no peito. Dobra só pelo quadril com a coluna reta, desce até o tronco ficar quase vertical e sobe até alinhar com as pernas, sem arquear mais que isso.",
    cam: { alvo: V3(0.0, 0.72, 0), dist: 4.5, yaw: 0, pitch: 12 },
    AL: 38 * Math.PI / 180, HIP: V3(-0.02, 0.9, 0),
    cena(g) {
      g.add(K.piso(3.0, 1.6).translateX(-0.2));
      const al = this.AL, u = V3(Math.cos(al), Math.sin(al), 0), nu = V3(-Math.sin(al), Math.cos(al), 0), fr = nu.clone().negate();
      const inc = new THREE.Group(); inc.position.copy(this.HIP).add(fr.clone().multiplyScalar(0.115)); inc.rotation.z = al; g.add(inc); inc.updateMatrixWorld(true);
      const pad = K.caixa(0.56, 0.1, 0.4, M.estofado, 0.035); pad.position.set(-0.22, -0.05, 0); inc.add(pad);
      for (const z of [-0.17, 0.17]) inc.add(K.viga(V3(-1.04, -0.17, z), V3(0.1, -0.17, z), 0.06));
      const placa = K.caixa(0.04, 0.4, 0.46, M.quadro, 0.01); placa.position.set(-1.0, 0.07, 0); inc.add(placa);
      const barraR = K.tubo(V3(-0.84, 0.215, -0.24), V3(-0.84, 0.215, 0.24), 0.014, M.aco); inc.add(barraR);
      for (const z of [-0.12, 0.12]) { const r = K.rolo(0.17, 0.042); r.position.set(-0.84, 0.215, z); r.rotation.y = Math.PI / 2; inc.add(r); }
      for (const z of [-0.24, 0.24]) inc.add(K.viga(V3(-0.84, 0.215, z), V3(-0.84, -0.17, z), 0.04));
      const w = (x, y, z) => inc.localToWorld(V3(x, y, z));
      for (const z of [-0.3, 0.3]) { // base no chão + pés
        g.add(K.viga(V3(-0.85, 0.03, z), V3(0.55, 0.03, z), 0.07)); g.add(K.viga(w(0.1, -0.17, z * 0.57), V3(w(0.1, -0.17, 0).x, 0.05, z), 0.06));
        g.add(K.viga(w(-0.9, -0.17, z * 0.57), V3(w(-0.9, -0.17, 0).x, 0.05, z), 0.05));
      }
      g.add(K.caixa(0.1, 0.1, 0.62, M.quadro).translateX(w(0.1, -0.17, 0).x).translateY(0.05));
      g.add(K.caixa(0.1, 0.1, 0.62, M.quadro).translateX(w(-0.9, -0.17, 0).x).translateY(0.05));
    },
    pose(t) {
      zera();
      const al = this.AL, k = sm(t), th = al - 1.38 * k, thP = al - 0.62 * k;   // ângulo do tronco / da pelve (do eixo +X, anti-horário)
      const dir = (a) => V3(Math.cos(a), Math.sin(a), 0), fr = (a) => V3(Math.sin(a), -Math.cos(a), 0);
      corpoEm(this.HIP.clone(), dir(thP), fr(thP));
      const resto = (thP - th) / 3;
      gira("spine_01", EX, resto); gira("spine_02", EX, resto * 1.05); gira("spine_03", EX, resto * 0.95);
      gira("neck_01", EX, -0.1 * k); gira("head", EX, -0.12 * k);
      B.pelvis.updateMatrixWorld(true);
      const u = dir(al);
      for (const l of ["l", "r"]) {
        const q = ondeEsta("thigh_" + l);
        perna(l, q.clone().add(u.clone().multiplyScalar(-0.9)), fr(al));
      }
      const c = quadroDe("spine_03"), P0 = ondeEsta("spine_03").add(c.up.clone().multiplyScalar(0.12)).add(c.fr.clone().multiplyScalar(0.13));
      for (const l of ["l", "r"]) { // braços cruzados no peito: mão esquerda no ombro direito e vice-versa
        const s = sc(l), alvo = P0.clone().add(c.esq.clone().multiplyScalar(-s * 0.1)).add(c.fr.clone().multiplyScalar(l === "l" ? 0 : 0.03));
        braco(l, alvo, c.fr.clone().multiplyScalar(-0.2).add(c.up.clone().multiplyScalar(-1)).add(c.esq.clone().multiplyScalar(s * 0.3)));
        mao(l, c.esq.clone().multiplyScalar(-s).add(c.up.clone().multiplyScalar(0.3)), c.fr.clone().multiplyScalar(-1));
      }
    },
  },
  // ================= Remada invertida: corpo reto sob a barra, calcanhar no chão =================
  co_invertida: {
    nome: "Remada invertida",
    musc: { dorsal: 1, trapezio: 0.85, biceps: 0.6, deltoide: 0.5, antebraco: 0.4, lombar: 0.3 },
    dica: "Corpo reto como uma prancha, calcanhar no chão e barra na altura do quadril ou um pouco mais alta. Puxa o peito até a barra juntando as escápulas, sem deixar o quadril cair, e desce até esticar o braço.",
    cam: { alvo: V3(0.5, 0.55, 0), dist: 4.8, yaw: 20, pitch: 4 },
    BAR: 1.05,
    cena(g) { g.add(K.piso(3.8, 2.0).translateX(0.45)); const bf = K.barraFixa({ alt: this.BAR, larg: 1.3 }); g.add(bf.g); },
    pose(t) {
      zera();
      const k = 1 - t, sk = sm(k), th = (14 + 22 * sk) * Math.PI / 180;
      const A = V3(1.1, 0.075, 0), u = V3(-Math.cos(th), Math.sin(th), 0), up = V3(Math.sin(th), Math.cos(th), 0);
      corpoEm(A.clone().add(u.clone().multiplyScalar(0.915)), u, up);
      gira("spine_02", EX, -0.04 * sk); gira("neck_01", EX, 0.05 * sk - 0.1 * (1 - sk)); gira("head", EX, -0.05);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { const q = ondeEsta("thigh_" + l); perna(l, V3(A.x, A.y, zc(l) * 0.1), up); }
      for (const l of ["l", "r"]) {
        agarra(l, { ponto: V3(0, this.BAR, zc(l) * 0.24), R: 0.016, eixo: V3(0, 0, sc(l)), palma: V3(1, 0, 0),
          polo: V3(0.2, -1, zc(l) * 0.7) });
      }
    },
  },

  // ================= Barra fixa: pronada, supinada, neutra (corpo pendurado, mão fechada na barra) e assistida (máquina) =================
  co_barrafixa: {
    nome: "Barra fixa",
    musc: { dorsal: 1, biceps: 0.7, trapezio: 0.6, deltoide: 0.4, antebraco: 0.5, abdomen: 0.25 },
    dica: "Pendura com o braço quase esticado e as escápulas ativas. Puxa os cotovelos pro bolso de trás até o queixo passar da barra, sem balançar, e desce controlando até esticar de novo.",
    cam: { alvo: V3(0.05, 1.55, 0), dist: 4.9, yaw: 20, pitch: 6 },
    ALT: 2.3,
    cena(g) {
      const p = this.p, alt = this.ALT, lg = 1.3;
      g.add(K.piso(2.6, 2.2).translateX(0.2));
      if (p.assistida) { this.cena_assistida(g); return; }
      const bf = K.barraFixa({ alt, larg: lg }); g.add(bf.g);
      if (p.pega === "neutra") for (const z of [-0.22, 0.22]) { // pegas paralelas saindo da barra (empunhadura neutra)
        g.add(K.tubo(V3(0, alt, z), V3(0.5, alt, z), 0.016, M.cromo));
        const emb = K.cilU(0.0185, M.borracha); emb.scale.y = 0.16; emb.rotation.z = Math.PI / 2; emb.position.set(0.19, alt, z); g.add(emb);
        g.add(K.viga(V3(0.5, alt, z), V3(0.5, alt - 0.05, z), 0.04));
      }
    },
    cena_assistida(g) { // máquina assistida (contrapeso): plataforma de joelho sobe e desce com o corpo, pilha atrás
      const alt = this.ALT, zs = [-0.42, 0.42];
      g.add(K.caixa(1.15, 0.06, 1.0, M.quadro, 0.012).translateX(-0.5).translateY(0.03));
      for (const z of zs) g.add(K.caixa(0.1, alt + 0.05, 0.1).translateX(-0.55).translateY((alt + 0.05) / 2).translateZ(z));
      g.add(K.caixa(0.12, 0.1, 1.0).translateX(-0.55).translateY(alt + 0.05));
      for (const z of zs) { g.add(K.viga(V3(-0.55, alt - 0.02, z), V3(0.02, alt - 0.02, z), 0.07));
        g.add(K.tubo(V3(0.0, alt, z), V3(0.5, alt, z), 0.016, M.cromo)); g.add(K.viga(V3(0.5, alt, z), V3(0.5, alt - 0.05, z), 0.04));
        const emb = K.cilU(0.0185, M.borracha); emb.scale.y = 0.16; emb.rotation.z = Math.PI / 2; emb.position.set(0.19, alt, z * 0.52); g.add(emb); }
      for (const z of zs) g.add(K.tubo(V3(0, alt, z), V3(0, alt, z * 0.15), 0.017, M.cromo));
      g.add(K.tubo(V3(0, alt, -0.42), V3(0, alt, 0.42), 0.017, M.cromo));
      for (const z of [-0.24, 0.24]) { g.add(K.tubo(V3(0, alt, z), V3(0.5, alt, z), 0.016, M.cromo)); }
      const pe = new THREE.Group(); // plataforma
      pe.add(K.caixa(0.62, 0.05, 0.5, M.quadro, 0.01).translateX(0.28).translateY(-0.085));
      const pad = K.assento(0.36, 0.52, 0.07); pad.position.set(0.18, -0.03, 0); pe.add(pad);
      const braco_ = K.caixa(0.5, 0.07, 0.16, M.quadro, 0.01); braco_.position.set(-0.28, -0.085, 0); pe.add(braco_);
      pe.add(K.caixa(0.1, 0.5, 0.16, M.aco, 0.01).translateX(-0.5).translateY(-0.06));
      this.pe = pe; g.add(sombreia(pe));
      const pil = K.pilha(); pil.position.set(-0.95, 0.04, 0); g.add(pil); this.pil = pil;
    },
    pose(t) {
      zera();
      const p = this.p, k = 1 - t, sk = sm(k), alt = this.ALT, pega = p.pega || "pronada", assist = !!p.assistida;
      const lean = 0.05 + 0.2 * sk;
      const W = pega === "supinada" ? 0.17 : pega === "neutra" ? 0.22 : 0.42, X0 = pega === "neutra" ? 0.19 : 0;
      corpoEm(V3(0, 0, 0), V3(-Math.sin(lean), Math.cos(lean), 0), V3(Math.cos(lean), Math.sin(lean), 0));
      gira("spine_01", EX, -0.03 * sk); gira("spine_02", EX, -0.08 * sk); gira("spine_03", EX, -0.06 * sk);
      gira("neck_01", EX, -0.3 * sk + 0.05 * (1 - sk)); gira("head", EX, -0.12 * sk);
      for (const l of ["l", "r"]) gira("clavicle_" + l, EZ, (l === "l" ? 1 : -1) * ENC_SINAL * 0.2 * (1 - sk));   // ombro sobe solto lá embaixo
      B.pelvis.updateMatrixWorld(true);
      recentra(V3(X0 - 0.02 - 0.12 * sk, alt - 0.58 + 0.395 * sk, 0));
      if (assist) { // ajoelhado na almofada, pernas pra trás
        const q = ondeEsta("pelvis"), jy = q.y - 0.5;
        for (const l of ["l", "r"]) { const th = ondeEsta("thigh_" + l); perna(l, V3(th.x + 0.03 - 0.43, jy - 0.02, zc(l) * 0.1), V3(1, 0, 0)); }
        peDir("l", V3(-0.9, -0.3, 0)); peDir("r", V3(-0.9, -0.3, 0));
        this.pe.position.set(0, jy - 0.02, 0);
        this.pil.userData.sobe((alt - 1.2 - jy) * 0.35);
      } else {
        for (const l of ["l", "r"]) { const th = ondeEsta("thigh_" + l);
          perna(l, V3(th.x - 0.3 + 0.02, th.y - 0.58 - (l === "l" ? 0.02 : 0), zc(l) * 0.05 * (l === "l" ? -1 : 1)), V3(1, 0, 0));
          peDir(l, V3(-0.7, -0.7, 0)); }
      }
      for (const l of ["l", "r"]) {
        const s = sc(l), ponto = V3(X0, alt, zc(l) * W);
        if (pega === "neutra") agarra(l, { ponto, R: 0.0185, eixo: V3(-1, 0, 0), palma: V3(0, 0, -zc(l)), polo: V3(0.3, -1, zc(l) * 0.4) });
        else agarra(l, { ponto, R: 0.016, eixo: V3(0, 0, pega === "supinada" ? -s : s), palma: V3(pega === "supinada" ? -1 : 1, 0, 0),
          polo: pega === "supinada" ? V3(0.5, -1, zc(l) * 0.15) : V3(-0.1, -1, zc(l) * 0.75) });
      }
    },
  },

  // ================= Puxada alta sentada (lat pulldown): barra aberta/fechada/supinada, triângulo, unilateral =================
  co_puxada: {
    nome: "Puxada frontal",
    musc: { dorsal: 1, biceps: 0.6, trapezio: 0.5, deltoide: 0.35, antebraco: 0.4 },
    dica: "Peito aberto, tronco levemente inclinado pra trás e coxas presas no rolo. Puxa a barra até a parte alta do peito levando os cotovelos pra baixo e pro bolso, sem balançar, e sobe devagar até esticar o braço.",
    cam: { alvo: V3(0.1, 1.15, 0), dist: 4.3, yaw: 20, pitch: 8 },
    XP: 0.17, YP: 2.15, XT: 1.4,
    cena(g) {
      const p = this.p, pega = p.pega || "aberta", { XP, YP, XT } = this;
      g.add(K.piso(3.4, 1.8).translateX(0.5));
      g.add(K.caixa(2.3, 0.06, 0.16).translateX(0.55).translateY(0.03));
      const altura = YP + 0.22;
      this.torre = torreEm(g, { alt: YP + 0.045, altura, x: XT }); this.torre.cabo.visible = false;
      g.add(K.viga(V3(XT + 0.12, altura - 0.05, 0), V3(XP + 0.02, altura - 0.05, 0), 0.1));
      g.add(K.tubo(V3(XP, altura - 0.05, 0), V3(XP, YP, 0), 0.014, M.aco));
      const roda = new THREE.Mesh(new THREE.TorusGeometry(0.045, 0.01, 10, 28), M.aco); roda.position.set(XP, YP, 0); g.add(roda);
      this.cB = K.cabo(); K.poe(this.cB, V3(XP, YP + 0.045, 0), V3(XT - 0.11, YP + 0.045, 0)); g.add(this.cB);
      this.cA = K.cabo(); g.add(this.cA);
      // assento e rolos de coxa
      g.add(K.assento(0.38, 0.4, 0.1).translateX(-0.06).translateY(0.41)); g.add(K.viga(V3(-0.06, 0.06, 0), V3(-0.06, 0.36, 0), 0.07));
      g.add(K.viga(V3(0.66, 0.06, 0), V3(0.66, 0.68, 0), 0.07)); g.add(K.viga(V3(0.66, 0.68, 0), V3(0.38, 0.68, 0), 0.05));
      g.add(K.tubo(V3(0.38, 0.68, -0.26), V3(0.38, 0.68, 0.26), 0.014, M.aco));
      for (const z of [-0.14, 0.14]) { const r = K.rolo(0.17, 0.05); r.position.set(0.38, 0.68, z); r.rotation.y = Math.PI / 2; g.add(r); }
      this.pg = pega === "triangulo" ? K.triangulo() : p.unilateral ? K.estribo() : K.barraReta(pega === "aberta" ? 1.0 : pega === "fechada" ? 0.44 : 0.5);
      g.add(this.pg);
    },
    pose(t) { prepCurso(this); this.calc(t); },
    calc(t) {
      zera();
      const p = this.p, pega = p.pega || "aberta", uni = !!p.unilateral, { XP, YP } = this;
      const k = 1 - t, sk = sm(k), lean = 0.05 + 0.25 * sk;
      corpoEm(V3(-0.06, 0.545, 0), V3(-Math.sin(lean), Math.cos(lean), 0), V3(Math.cos(lean), Math.sin(lean), 0));
      gira("spine_02", EX, -0.06 * sk); gira("neck_01", EX, lean * 0.7); gira("head", EX, lean * 0.2 - 0.1 * Math.sin(Math.PI * sk));
      for (const l of ["l", "r"]) gira("clavicle_" + l, EZ, (l === "l" ? 1 : -1) * ENC_SINAL * 0.22 * (1 - sk));
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { perna(l, V3(0.52, ALT_TORN, zc(l) * 0.2), V3(0.3, 1, zc(l) * 0.15)); pe(l, F0); }
      const W = uni ? 0.15 : { aberta: 0.42, fechada: 0.14, supinada: 0.17, triangulo: 0.045 }[pega];
      const c = quadroDe("spine_03"), C0 = ondeEsta("clavicle_l").add(ondeEsta("clavicle_r")).multiplyScalar(0.5).add(c.fr.clone().multiplyScalar(0.135)).add(c.up.clone().multiplyScalar(-0.05));
      const om = ombrosC(), pontos = {};
      const lados = uni ? ["r"] : ["l", "r"];
      for (const l of lados) {
        const zh = uni ? 0.15 : zc(l) * W, S = ondeEsta("upperarm_" + l), dz = zh - S.z, dx = 0.1;
        const h = Math.sqrt(Math.max(0.05, 0.575 * 0.575 - dz * dz - dx * dx));
        const T1 = V3(S.x + dx, S.y + h, zh), T0 = V3(C0.x, C0.y, zh);
        const P = T1.clone().lerp(T0, sk); P.x += 0.07 * Math.sin(Math.PI * sk); pontos[l] = P;
      }
      const centro = uni ? pontos.r.clone() : pontos.l.clone().add(pontos.r).multiplyScalar(0.5);
      const apexO = V3(XP - 0.045, YP, uni ? 0 : 0).sub(centro).normalize();
      const alto = pega === "triangulo" ? V3(0, 1, 0) : apexO;
      const { Y } = baseDe(this.pg, centro, uni ? V3(1, 0, 0) : V3(0, 0, 1), alto);
      const apex = centro.clone().add(Y.clone().multiplyScalar(pega === "triangulo" ? 0.12 : uni ? 0.075 : 0.024));
      K.poe(this.cA, V3(XP - 0.045, YP, 0), apex);
      this.torre.liga(this.torre.saida().add(V3(0, -V3(XP - 0.045, YP, 0).distanceTo(apex), 0)));
      for (const l of lados) {
        const s = sc(l), ponto = pontos[l], elb = V3(-0.3, -1, zc(l) * (pega === "aberta" ? 0.9 : 0.4));
        if (pega === "triangulo") agarra(l, { ponto, R: 0.014, eixo: V3(-1, 0, 0), palma: V3(0, 0, -zc(l)), polo: elb });
        else if (uni) agarra(l, { ponto, R: 0.015, eixo: V3(-1, 0, 0), palma: V3(0, 0, -zc(l)), polo: elb });
        else agarra(l, { ponto, R: 0.0135, eixo: V3(0, 0, pega === "supinada" ? -s : s), palma: V3(pega === "supinada" ? -1 : 1, 0, 0), polo: elb });
      }
      if (uni) { const th = ondeEsta("thigh_l"); braco("l", V3(th.x + 0.3, th.y + 0.16, th.z), V3(-0.5, -1, -0.5)); mao("l", F0, V3(0, -1, 0)); }
    },
  },

  // ================= Pulldown de braço esticado (corda / barra reta) na polia alta =================
  co_pulldown: {
    nome: "Pulldown na polia alta",
    musc: { dorsal: 1, triceps: 0.35, abdomen: 0.3, trapezio: 0.3, deltoide: 0.25 },
    dica: "Braço quase esticado o tempo todo, tronco inclinado uns 20° e joelho solto. Leva a barra em arco da frente da cabeça até a coxa, sentindo o dorsal fechar, e volta devagar sem dobrar o cotovelo.",
    cam: { alvo: V3(0.3, 1.2, 0), dist: 4.4, yaw: 20, pitch: 8 },
    cena(g) {
      g.add(K.piso(2.8, 2.0).translateX(0.4));
      this.torre = torreEm(g, { alt: 2.1, altura: 2.3, x: 1.15 });
      this.pg = this.p.corda ? K.corda() : K.barraReta(0.5); g.add(this.pg);
    },
    pose(t) { prepCurso(this); this.calc(t); },
    calc(t) {
      zera();
      const corda = !!this.p.corda, k = 1 - t, sk = sm(k), incl = 0.5 - 0.12 * sk;
      emPe(V3(-0.22, ALT_QUADRIL - 0.05, 0), F0, incl * 0.8);
      gira("spine_02", EX, incl * 0.1); gira("spine_03", EX, incl * 0.1); gira("neck_01", EX, -incl * 0.5);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.14, fora: 0.2, poloFora: 0.25, recuo: 0.0 });
      const om = ombrosC(), R = 0.565, ang = (46 - 136 * sk) * Math.PI / 180; // 46° acima da horizontal -> 90° pra baixo
      const d = V3(Math.cos(ang), Math.sin(ang), 0), n = V3(Math.sin(ang), -Math.cos(ang), 0);
      const W = corda ? 0.09 : 0.17, E = esquerda(F0);
      const mid = om.clone().add(d.clone().multiplyScalar(R));
      const pol = this.torre.saida(), dirC = pol.clone().sub(mid).normalize();
      this.pg.position.copy(mid).add(dirC.clone().multiplyScalar(corda ? 0.2 : 0.06));
      const pts = {};
      for (const l of ["l", "r"]) {
        const s = sc(l), S = ondeEsta("upperarm_" + l), v = d.clone().multiplyScalar(R).add(E.clone().multiplyScalar(s * (corda ? 0.0 : 0))); 
        pts[l] = S.clone().add(d.clone().multiplyScalar(R)).add(V3(0, 0, -zc(l) * (corda ? (0.19 - 0.09 - 0.19 * 0) * 0 : 0)));
        pts[l].z = zc(l) * W;
      }
      let anel;
      if (corda) {
        this.pg.quaternion.setFromUnitVectors(EY, dirC); this.pg.updateMatrixWorld(true);
        this.pg.userData.abre(pts.l, pts.r);
        anel = this.pg.localToWorld(V3(0, 0.05, 0));
      } else { baseDe(this.pg, mid.clone().add(V3(0, 0, 0)), V3(0, 0, 1), dirC); this.pg.position.copy(mid); this.pg.updateMatrixWorld(true); anel = this.pg.localToWorld(V3(0, 0.024, 0)); }
      this.torre.liga(anel);
      for (const l of ["l", "r"]) {
        const s = sc(l);
        if (corda) agarra(l, { ponto: pts[l], R: 0.012, eixo: V3(0, 0, -zc(l)).cross(d).multiplyScalar(s), palma: V3(0, 0, -zc(l)), polo: V3(-0.3, -1, zc(l) * 0.2) });
        else agarra(l, { ponto: pts[l], R: 0.0135, eixo: V3(0, 0, s), palma: n, polo: V3(-0.3, -1, zc(l) * 0.3) });
      }
    },
  },

  // ================= Remada baixa na polia: triângulo (pegada neutra) ou barra reta aberta =================
  co_remada_cabo: {
    nome: "Remada baixa na polia",
    musc: { dorsal: 1, trapezio: 0.85, biceps: 0.55, deltoide: 0.4, lombar: 0.4, antebraco: 0.4 },
    dica: "Sentado com o tronco firme, joelho levemente dobrado. Puxa a pegada até o umbigo levando o cotovelo pra trás e juntando as escápulas, segura um instante e volta esticando o braço sem arredondar a coluna.",
    cam: { alvo: V3(0.3, 0.85, 0), dist: 4.6, yaw: 20, pitch: 10 },
    cena(g) {
      const aberta = this.p.pega === "aberta";
      g.add(K.piso(4.0, 1.8).translateX(0.55));
      g.add(K.caixa(2.9, 0.07, 0.34).translateX(0.45).translateY(0.035));
      this.torre = torreEm(g, { alt: 0.78, altura: 1.9, x: 1.8 });
      g.add(K.assento(0.38, 0.36, 0.1).translateX(-0.33).translateY(0.41)); g.add(K.viga(V3(-0.33, 0.07, 0), V3(-0.33, 0.36, 0), 0.07));
      const pl = K.caixa(0.04, 0.36, 0.52, M.quadro, 0.01); pl.position.set(0.6, 0.27, 0); pl.rotation.z = -0.25; g.add(pl);
      for (const z of [-0.24, 0.24]) g.add(K.viga(V3(0.55, 0.07, z), V3(0.58, 0.2, z), 0.05));
      this.pg = aberta ? K.barraReta(0.8) : K.triangulo(); g.add(this.pg);
    },
    pose(t) { prepCurso(this); this.calc(t); },
    calc(t) {
      zera();
      const aberta = this.p.pega === "aberta", k = 1 - t, sk = sm(k), lean = 0.4 - 0.45 * sk;
      corpoEm(V3(-0.3, 0.55, 0), V3(Math.sin(lean * 0.7), Math.cos(lean * 0.7), 0), V3(Math.cos(lean * 0.7), -Math.sin(lean * 0.7), 0));
      gira("spine_01", EX, lean * 0.1); gira("spine_02", EX, lean * 0.1); gira("spine_03", EX, lean * 0.1); gira("neck_01", EX, -lean * 0.4);
      for (const l of ["l", "r"]) gira("clavicle_" + l, EY, (l === "l" ? 1 : -1) * (0.14 * sk - 0.06 * (1 - sk)));
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { perna(l, V3(0.5, 0.3, zc(l) * 0.21), V3(0.2, 1, zc(l) * 0.3)); peDir(l, V3(0.25, 0.97, 0)); }
      const c = quadroDe("spine_03"), om = ombrosC(), N = ondeEsta("spine_02").add(c.fr.clone().multiplyScalar(0.14));
      const W = aberta ? 0.32 : 0.045, R = 0.575, dz = Math.abs(W - 0.19), r2 = Math.sqrt(R * R - dz * dz);
      const H1 = om.clone().add(V3(Math.cos(0.4) * r2, -Math.sin(0.4) * r2, 0)).setZ(0);
      const mid = H1.clone().lerp(N.setZ(0), sk);
      const apexL = aberta ? 0.024 : 0.12;
      const { Y } = baseDe(this.pg, mid, V3(0, 0, 1), V3(1, 0, 0));
      this.torre.liga(mid.clone().add(Y.clone().multiplyScalar(apexL)));
      for (const l of ["l", "r"]) {
        const s = sc(l), ponto = mid.clone().add(V3(0, 0, zc(l) * W)), polo = V3(-1, -0.4, zc(l) * (aberta ? 0.8 : 0.25));
        if (aberta) agarra(l, { ponto, R: 0.0135, eixo: V3(0, 0, s), palma: V3(0, -1, 0), polo });
        else agarra(l, { ponto, R: 0.014, eixo: V3(0, 1, 0), palma: V3(0, 0, -zc(l)), polo });
      }
    },
  },
  // ================= Remada na máquina articulada (apoio de peito, alavancas independentes) =================
  co_remada_maq: {
    nome: "Remada na máquina articulada",
    musc: { dorsal: 1, trapezio: 0.85, deltoide: 0.5, biceps: 0.5, antebraco: 0.35 },
    dica: "Peito firme na almofada, ombros longe das orelhas. Puxa as duas alavancas juntando as escápulas, cotovelo rente ao corpo, e volta devagar alongando as costas sem soltar o peito do apoio.",
    cam: { alvo: V3(0.15, 0.95, 0), dist: 4.4, yaw: 20, pitch: 10 },
    PV: V3(0.25, 0.09, 0), RV: 0.9,
    cena(g) {
      g.add(K.piso(3.0, 1.8).translateX(0.3));
      g.add(K.caixa(1.9, 0.06, 0.5, M.quadro).translateX(0.1).translateY(0.03));
      g.add(K.assento(0.4, 0.4, 0.1).translateX(-0.2).translateY(0.41)); g.add(K.viga(V3(-0.2, 0.06, 0), V3(-0.2, 0.36, 0), 0.07));
      g.add(K.viga(V3(0.62, 0.06, 0), V3(0.62, 1.3, 0), 0.08)); this.pad = K.caixa(0.1, 0.4, 0.36, M.estofado, 0.035); g.add(this.pad);
      this.braPad = K.caixa(0.06, 1, 0.06, M.quadro, 0.01); g.add(this.braPad);
      this.al = {};
      for (const l of ["l", "r"]) {
        const z = zc(l), cx = K.caixa(0.12, 0.16, 0.1, M.quadro, 0.015); cx.position.set(this.PV.x, this.PV.y, z * 0.44); g.add(cx);
        const lev = K.caixa(0.06, 1, 0.06, M.quadro, 0.012); g.add(lev);
        const rod = K.cilU(0.0185, M.borracha); rod.scale.y = 0.14; g.add(rod);
        const cr = K.caixa(0.04, 1, 0.04, M.aco, 0.008); g.add(cr);
        g.add(K.tubo(V3(this.PV.x - 0.1, this.PV.y + 0.05, z * 0.44), V3(this.PV.x - 0.1, this.PV.y + 0.05, z * 0.74), 0.016, M.cromo));
        for (let i = 0; i < 2; i++) { const a = anilha(0.2, 0.045); a.rotation.x = Math.PI / 2; a.position.set(this.PV.x - 0.1, this.PV.y + 0.05, z * (0.54 + i * 0.06)); g.add(a); }
        this.al[l] = { lev, rod, cr };
      }
      sombreia(g);
    },
    pose(t) {
      zera();
      const k = 1 - t, sk = sm(k), P = this.PV, R = this.RV;
      corpoEm(V3(-0.2, 0.555, 0), V3(Math.sin(0.15), Math.cos(0.15), 0), V3(Math.cos(0.15), -Math.sin(0.15), 0));
      gira("spine_02", EX, 0.03); gira("neck_01", EX, -0.12);
      for (const l of ["l", "r"]) gira("clavicle_" + l, EY, (l === "l" ? 1 : -1) * (0.15 * sk - 0.05 * (1 - sk)));
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { perna(l, V3(0.45, ALT_TORN, zc(l) * 0.2), V3(0.3, 1, zc(l) * 0.15)); pe(l, F0); }
      const c = quadroDe("spine_03"), sp = ondeEsta("spine_03"), pc = sp.clone().add(c.fr.clone().multiplyScalar(0.17)).add(c.up.clone().multiplyScalar(0.07));
      this.pad.position.copy(pc); this.pad.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(c.fr.clone(), c.up, c.fr.clone().cross(c.up).negate()));
      K.poe(this.braPad, V3(0.62, pc.y, 0), pc.clone().setZ(0));
      const phi = (72.5 + 35 * sk) * Math.PI / 180, H = V3(P.x + R * Math.cos(phi), P.y + R * Math.sin(phi), 0);
      for (const l of ["l", "r"]) {
        const z = zc(l), h = H.clone().setZ(z * 0.29), a = this.al[l];
        K.poe(a.lev, V3(P.x, P.y, z * 0.44), V3(h.x, h.y + 0.12, z * 0.42)); K.poe(a.cr, V3(h.x, h.y + 0.1, z * 0.42), V3(h.x, h.y + 0.09, z * 0.29));
        a.rod.position.copy(h);
        agarra(l, { ponto: h, R: 0.0185, eixo: V3(0, 1, 0), palma: V3(0, 0, -z), polo: V3(-1, 0, z * 0.5) });
      }
    },
  },
  // ================= Puxada na máquina articulada (alavancas convergentes, rolo de coxa) =================
  co_puxada_maq: {
    nome: "Puxada na máquina articulada",
    musc: { dorsal: 1, biceps: 0.5, trapezio: 0.5, deltoide: 0.3, antebraco: 0.35 },
    dica: "Coxas presas no rolo, peito aberto. Puxa as duas alavancas em arco até a altura do peito, cotovelos pra baixo e pro bolso, e sobe devagar até o braço esticar sem levantar o quadril.",
    cam: { alvo: V3(0.2, 1.15, 0), dist: 4.4, yaw: 20, pitch: 8 },
    PV: V3(1.09, 1.4, 0), RV: 0.92,
    cena(g) {
      const P = this.PV;
      g.add(K.piso(3.2, 1.8).translateX(0.55)); g.add(K.caixa(2.0, 0.06, 0.2).translateX(0.45).translateY(0.03));
      g.add(K.assento(0.38, 0.4, 0.1).translateX(-0.06).translateY(0.41)); g.add(K.viga(V3(-0.06, 0.06, 0), V3(-0.06, 0.36, 0), 0.07));
      g.add(K.viga(V3(0.66, 0.06, 0), V3(0.66, 0.68, 0), 0.07)); g.add(K.viga(V3(0.66, 0.68, 0), V3(0.38, 0.68, 0), 0.05));
      g.add(K.tubo(V3(0.38, 0.68, -0.26), V3(0.38, 0.68, 0.26), 0.014, M.aco));
      for (const z of [-0.14, 0.14]) { const r = K.rolo(0.17, 0.05); r.position.set(0.38, 0.68, z); r.rotation.y = Math.PI / 2; g.add(r); }
      for (const z of [-0.56, 0.56]) g.add(K.caixa(0.1, 1.95, 0.1).translateX(1.3).translateY(0.975).translateZ(z));
      g.add(K.caixa(0.12, 0.1, 1.2).translateX(1.3).translateY(1.95)); g.add(K.caixa(0.7, 0.05, 1.2, M.quadro).translateX(1.3).translateY(0.025));
      this.al = {};
      for (const l of ["l", "r"]) {
        const z = zc(l), lev = K.caixa(0.06, 1, 0.06, M.quadro, 0.012), rod = K.cilU(0.0185, M.borracha), cr = K.caixa(0.04, 1, 0.04, M.aco, 0.008);
        rod.scale.y = 0.14; rod.rotation.z = Math.PI / 2; g.add(lev, rod, cr);
        g.add(K.tubo(V3(P.x, P.y, z * 0.5), V3(P.x + 0.4, P.y, z * 0.5), 0.02, M.cromo));
        for (let i = 0; i < 2; i++) { const a = anilha(0.2, 0.045); a.rotation.z = Math.PI / 2; a.position.set(P.x + 0.2 + i * 0.07, P.y, z * 0.5); g.add(a); }
        this.al[l] = { lev, rod, cr };
      }
      sombreia(g);
    },
    pose(t) {
      zera();
      const k = 1 - t, sk = sm(k), P = this.PV, R = this.RV, lean = 0.05 + 0.2 * sk;
      corpoEm(V3(-0.06, 0.545, 0), V3(-Math.sin(lean), Math.cos(lean), 0), V3(Math.cos(lean), Math.sin(lean), 0));
      gira("spine_02", EX, -0.05 * sk); gira("neck_01", EX, lean * 0.7); gira("head", EX, lean * 0.2);
      for (const l of ["l", "r"]) gira("clavicle_" + l, EZ, (l === "l" ? 1 : -1) * ENC_SINAL * 0.22 * (1 - sk));
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { perna(l, V3(0.52, ALT_TORN, zc(l) * 0.2), V3(0.3, 1, zc(l) * 0.15)); pe(l, F0); }
      const phi = (14 - 28 * sk) * Math.PI / 180, H = V3(P.x - R * Math.cos(phi), P.y + R * Math.sin(phi), 0);
      for (const l of ["l", "r"]) {
        const z = zc(l), h = H.clone().setZ(z * 0.28), a = this.al[l];
        K.poe(a.lev, V3(P.x, P.y, z * 0.5), V3(h.x - 0.07, h.y, z * 0.38)); K.poe(a.cr, V3(h.x - 0.07, h.y, z * 0.38), V3(h.x - 0.07, h.y, z * 0.28));
        a.rod.position.copy(h);
        agarra(l, { ponto: h, R: 0.0185, eixo: V3(-1, 0, 0), palma: V3(0, 0, -z), polo: V3(-0.3, -1, z * 0.5) });
      }
    },
  },

  // ================= Remada cavalinho (T-bar): barra articulada no chão à frente, pegada em V =================
  co_tbar: {
    nome: "Remada cavalinho (T-bar)",
    musc: { dorsal: 1, trapezio: 0.9, biceps: 0.5, deltoide: 0.5, lombar: 0.55, antebraco: 0.4 },
    dica: "Pés abertos dos dois lados da barra, joelho flexionado e tronco a uns 45° com a coluna neutra. Puxa a pegada em V até o peito levando os cotovelos pra trás e junta as escápulas, sem subir o tronco.",
    cam: { alvo: V3(0.4, 0.8, 0), dist: 4.5, yaw: 20, pitch: 10 },
    PV: V3(1.45, 0.14, 0), LB: 1.85,
    cena(g) {
      const P = this.PV;
      g.add(K.piso(3.4, 1.8).translateX(0.5));
      g.add(K.caixa(0.34, 0.12, 0.34, M.quadro, 0.02).translateX(P.x + 0.04).translateY(0.06));
      g.add(K.caixa(0.16, 0.16, 0.2, M.aco, 0.02).translateX(P.x).translateY(P.y));
      this.barraT = K.cilU(0.019, M.cromo, 20); g.add(this.barraT);
      this.plac = new THREE.Group(); for (let i = 0; i < 3; i++) { const a = anilha(0.19, 0.04); a.position.y = i * 0.045; this.plac.add(a); } g.add(this.plac);
      const v = new THREE.Group(); this.v = v;
      for (const z of [-0.09, 0.09]) { const e = K.cilU(0.0185, M.borracha); e.scale.y = 0.14; e.rotation.z = Math.PI / 2; e.position.set(0, 0, z); v.add(e);
        for (const x of [-0.075, 0.075]) v.add(K.tubo(V3(x, 0, z), V3(x, 0, 0), 0.01, M.cromo)); }
      v.add(K.tubo(V3(-0.075, 0, 0), V3(-0.075, -0.07, 0), 0.012, M.cromo));
      this.stem = K.cilU(0.01, M.cromo);
      g.add(sombreia(v)); g.add(this.stem);
    },
    pose(t) {
      zera();
      const k = 1 - t, sk = sm(k), P = this.PV, incl = 0.98 - 0.08 * sk;
      emPe(V3(-0.36 + 0.02 * sk, 0.84 + 0.03 * sk, 0), F0, incl * 0.8);
      gira("spine_01", EX, incl * 0.06); gira("spine_02", EX, incl * 0.07); gira("spine_03", EX, incl * 0.07); gira("neck_01", EX, -0.5);
      for (const l of ["l", "r"]) gira("clavicle_" + l, EY, (l === "l" ? 1 : -1) * 0.13 * sk);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { perna(l, V3(-0.02, ALT_TORN, zc(l) * 0.3), V3(0.6, 0.6, zc(l) * 0.4)); pe(l, V3(1, 0, zc(l) * 0.45)); }
      const c = quadroDe("spine_03"), om = ombrosC();
      const H1 = om.clone().add(V3(0.02, -(0.555), 0)), H0 = ondeEsta("spine_03").add(c.fr.clone().multiplyScalar(0.13)).add(c.up.clone().multiplyScalar(-0.04));
      const Hc = H1.clone().lerp(H0, sk).setZ(0);
      const dir = V3(P.x - Hc.x, P.y - Hc.y, 0).normalize(), Q = Hc.clone();
      K.poe(this.barraT, P, P.clone().add(dir.clone().multiplyScalar(-this.LB)));
      this.plac.position.copy(P).add(dir.clone().multiplyScalar(-this.LB + 0.08)); this.plac.quaternion.setFromUnitVectors(EY, dir.clone().multiplyScalar(-1)); this.plac.rotation.set(0, 0, 0); this.plac.quaternion.setFromUnitVectors(V3(0, -1, 0), dir.clone());
      this.v.position.copy(Hc).add(V3(0, 0.07, 0)); K.poe(this.stem, Hc, this.v.position.clone());
      for (const l of ["l", "r"]) {
        agarra(l, { ponto: this.v.position.clone().setZ(zc(l) * 0.09), R: 0.0185, eixo: V3(1, 0, 0), palma: V3(0, 0, -zc(l)), polo: V3(-1, 0.2, zc(l) * 0.6) });
      }
    },
  },
  // ================= Remada no Smith: barra presa na guia, sobe em linha reta =================
  co_remada_smith: {
    nome: "Remada no Smith",
    musc: { dorsal: 1, trapezio: 0.85, biceps: 0.5, deltoide: 0.45, lombar: 0.5, antebraco: 0.45 },
    dica: "Tronco a uns 45°, joelho flexionado e coluna neutra, barra sob os ombros. Destrava a barra e puxa em linha reta até o umbigo levando o cotovelo pra trás, depois desce controlando sem destravar o tronco.",
    cam: { alvo: V3(0.1, 0.9, 0), dist: 4.5, yaw: 20, pitch: 10 },
    XB: 0.0,
    cena(g) { g.add(tablado()); this.sm = K.smith({ alt: 2.15, larg: 1.25 }); this.sm.g.position.x = this.XB; g.add(this.sm.g); },
    pose(t) {
      zera();
      const k = 1 - t, sk = sm(k), incl = 0.92 - 0.2 * sk;
      emPe(V3(-0.38 + 0.1 * sk, 0.86 + 0.02 * sk, 0), F0, incl * 0.8);
      gira("spine_01", EX, incl * 0.06); gira("spine_02", EX, incl * 0.07); gira("spine_03", EX, incl * 0.07); gira("neck_01", EX, -0.5);
      for (const l of ["l", "r"]) gira("clavicle_" + l, EY, (l === "l" ? 1 : -1) * 0.13 * sk);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.15, fora: 0.2, poloFora: 0.25 });
      const c = quadroDe("spine_03"), om = ombrosC(), N = ondeEsta("spine_02").add(c.fr.clone().multiplyScalar(0.15));
      const y = lerp(om.y - (ALC * 0.985 + 0.065), N.y, sk);
      this.sm.barra.position.y = Math.max(0.25, y);
      for (const l of ["l", "r"]) {
        const s = sc(l), E = esquerda(F0);
        agarra(l, { ponto: V3(this.XB, this.sm.barra.position.y, 0).add(E.clone().multiplyScalar(s * 0.27)), R: 0.014, eixo: E.clone().multiplyScalar(-s), palma: F0.clone().multiplyScalar(-1), polo: V3(-1, 0.5, zc(l) * 0.4) });
      }
    },
  },
  // ================= Remada unilateral com halter (serrote): joelho e mão no banco =================
  co_serrote: {
    nome: "Remada unilateral com halter (serrote)",
    musc: { dorsal: 1, trapezio: 0.7, deltoide: 0.5, biceps: 0.55, antebraco: 0.45, lombar: 0.3 },
    dica: "Joelho e mão do mesmo lado no banco, tronco paralelo ao chão e coluna reta. Puxa o halter em direção ao quadril, cotovelo rente ao corpo, sem girar o tronco, e desce até esticar o braço.",
    cam: { alvo: V3(0.05, 0.75, 0), dist: 4.2, yaw: 20, pitch: 10 },
    cena(g) { g.add(tablado()); const b = banco(1.18); b.position.set(0, 0, -0.17); g.add(b); this.h = halter(1.2); g.add(this.h); },
    pose(t) {
      zera();
      const k = 1 - t, sk = sm(k), TOP = 0.4425;
      emPe(V3(-0.32, 0.92, 0), F0, 1.34);
      gira("spine_01", EX, 0.08); gira("spine_02", EX, 0.08); gira("spine_03", EX, 0.06); gira("neck_01", EX, -0.5);
      gira("clavicle_r", EY, -0.1 * sk);
      B.pelvis.updateMatrixWorld(true);
      const tl = ondeEsta("thigh_l");
      perna("l", V3(tl.x - 0.42, TOP + 0.1, -0.12), V3(1, -0.6, 0)); peDir("l", V3(-1, -0.2, 0));
      perna("r", V3(-0.1, ALT_TORN, 0.31), V3(0.8, 0.3, 0.2)); pe("r", V3(1, 0, 0.3));
      const SL = ondeEsta("upperarm_l");
      braco("l", V3(SL.x, TOP + 0.04, SL.z + 0.02), V3(-1, 0, -0.3)); mao("l", F0, V3(0, -1, 0));
      const SR = ondeEsta("upperarm_r"), hang = V3(SR.x + 0.04, SR.y - 0.56, SR.z + 0.04), alto = V3(SR.x - 0.3, SR.y - 0.24, SR.z + 0.05);
      const p = hang.clone().lerp(alto, sk);
      agarra("r", { ponto: p, R: 0.016, eixo: F0.clone(), palma: V3(0, 0, -1), polo: V3(-1, 0.3, 0.3) });
      seguraHalter(this.h, "r");
    },
  },
});
Object.assign(FOCOS, {
  // COSTAS. Fenwick 2009 (Eur J Appl Physiol 106): remada invertida deu a maior ativacao de dorsal entre as remadas testadas; remada curvada = maior carga lombar.
  // Lusk 2010 (J Strength Cond Res 24): puxada com pegada pronada ativa o dorsal igual ou mais que supinada, largura nao mudou o dorsal.
  // Youdas 2010 (J Strength Cond Res 24): barra fixa pronada x supinada sem diferenca no dorsal; supinada = biceps maior (confirmado em Dickie 2017: ~30% mais biceps no chin-up).
  // Pesos dos estabilizadores, antebraco e carga relativa entre variantes: estimativa.
  co_pendlay: () => [["dorsal", 1], ["trapezio_med", 0.85], ["lombar", 0.75], ["deltoide_post", 0.6], ["biceps", 0.5], ["isquio", 0.4], ["antebraco", 0.4], ["gluteo_max", 0.3]],
  co_goodmorning: () => [["lombar", 1], ["isquio", 0.85], ["gluteo_max", 0.8], ["trapezio_sup", 0.3], ["abdomen", 0.3]], // estimativa (padrao de dobradica de quadril)
  co_rackpull: () => [["lombar", 1], ["gluteo_max", 0.8], ["trapezio_sup", 0.75], ["trapezio_med", 0.6], ["isquio", 0.6], ["dorsal", 0.55], ["antebraco", 0.6]], // estimativa (terra parcial)
  co_superman: () => [["lombar", 1], ["gluteo_max", 0.65], ["trapezio_med", 0.4], ["deltoide_post", 0.35], ["isquio", 0.3]], // estimativa
  co_hiper: () => [["lombar", 1], ["gluteo_max", 0.8], ["isquio", 0.65], ["trapezio_med", 0.2]], // estimativa
  co_invertida: () => [["dorsal", 1], ["trapezio_med", 0.9], ["deltoide_post", 0.7], ["biceps", 0.6], ["infraespinal", 0.5], ["antebraco", 0.45], ["lombar", 0.3], ["abdomen", 0.3]], // Fenwick 2009
  co_barrafixa: (p) => p.assistida ? [["dorsal", 1], ["biceps", 0.7], ["braquiorradial", 0.5], ["trapezio_med", 0.5], ["antebraco", 0.4], ["deltoide_post", 0.35]]
    : p.pega === "supinada" ? [["dorsal", 1], ["biceps", 0.95], ["braquial", 0.6], ["trapezio_med", 0.45], ["antebraco", 0.5], ["deltoide_post", 0.4], ["abdomen", 0.3]]
    : p.pega === "neutra" ? [["dorsal", 1], ["biceps", 0.8], ["braquiorradial", 0.75], ["braquial", 0.6], ["trapezio_med", 0.5], ["antebraco", 0.5], ["deltoide_post", 0.4], ["abdomen", 0.3]]
    : [["dorsal", 1], ["trapezio_med", 0.6], ["biceps", 0.6], ["braquiorradial", 0.6], ["deltoide_post", 0.45], ["antebraco", 0.5], ["infraespinal", 0.4], ["abdomen", 0.3]],
  co_serrote: () => [["dorsal", 1], ["trapezio_med", 0.7], ["deltoide_post", 0.55], ["biceps", 0.55], ["antebraco", 0.45], ["lombar", 0.3]], // Fenwick 2009 (remada unilateral) + estimativa
  co_tbar: () => [["dorsal", 1], ["trapezio_med", 0.9], ["lombar", 0.55], ["deltoide_post", 0.55], ["biceps", 0.5], ["antebraco", 0.4]], // estimativa (similar a remada curvada)
  co_remada_cabo: (p) => p.pega === "aberta" ? [["trapezio_med", 1], ["deltoide_post", 0.8], ["dorsal", 0.85], ["infraespinal", 0.5], ["biceps", 0.4], ["lombar", 0.3]]
    : [["dorsal", 1], ["trapezio_med", 0.8], ["deltoide_post", 0.5], ["biceps", 0.55], ["lombar", 0.35], ["antebraco", 0.35]], // aberta puxa mais deltoide post/trapezio: estimativa
  co_remada_maq: () => [["dorsal", 1], ["trapezio_med", 0.8], ["deltoide_post", 0.55], ["biceps", 0.5], ["antebraco", 0.3]], // estimativa
  co_remada_smith: () => [["dorsal", 1], ["trapezio_med", 0.85], ["lombar", 0.5], ["deltoide_post", 0.5], ["biceps", 0.5], ["antebraco", 0.45]], // estimativa
  co_puxada: (p) => p.pega === "supinada" ? [["dorsal", 1], ["biceps", 0.85], ["braquial", 0.55], ["trapezio_med", 0.4], ["deltoide_post", 0.35]]
    : p.pega === "fechada" || p.pega === "triangulo" ? [["dorsal", 1], ["biceps", 0.7], ["braquiorradial", 0.6], ["trapezio_med", 0.45], ["deltoide_post", 0.35], ["antebraco", 0.35]]
    : [["dorsal", 1], ["trapezio_med", 0.55], ["biceps", 0.55], ["deltoide_post", 0.45], ["braquiorradial", 0.45], ["infraespinal", 0.35], ["antebraco", 0.3]], // Lusk 2010
  co_puxada_maq: () => [["dorsal", 1], ["biceps", 0.6], ["trapezio_med", 0.5], ["deltoide_post", 0.4], ["braquiorradial", 0.45], ["antebraco", 0.3]], // Lusk 2010 + estimativa
  co_pulldown: () => [["dorsal", 1], ["triceps_longa", 0.55], ["deltoide_post", 0.4], ["serratil", 0.3], ["abdomen", 0.3]], // estimativa (bracos estendidos: dorsal isolado, triceps longa como extensor do ombro)
});
Object.assign(VISTA, { co_pendlay: 232, co_goodmorning: 220, co_rackpull: 225, co_superman: 250, co_hiper: 250, co_invertida: 232, co_barrafixa: 245, co_serrote: 240, co_tbar: 235, co_remada_cabo: 235, co_remada_maq: 250, co_remada_smith: 235, co_puxada: 250, co_puxada_maq: 250, co_pulldown: 250 });
}

// ===== moldes/ombros.js =====
{ // moldes/ombros.js — ombros (om_) e antebraço
// ---------- apoio ----------
const ombroMeio = () => ondeEsta("upperarm_l").add(ondeEsta("upperarm_r")).multiplyScalar(0.5);
const sLado = (l) => (l === "l" ? 1 : -1);                    // mesmo "s" do motor: +1 = esquerda do personagem
const LAT = (l) => esquerda(F0).multiplyScalar(sLado(l));      // unitário pro lado de fora do braço l (esquerdo = -Z)
const ALC = () => COMP.upperarm_l + COMP.lowerarm_l;           // ombro -> punho, braço esticado
const suave = (a, b, x) => { const k = Math.min(1, Math.max(0, (x - a) / (b - a))); return k * k * (3 - 2 * k); };

// corpo sentado: quadril em pos (centro da articulação), tronco reclinado recl rad, pés no chão à frente
function sentaCorpo(pos, recl = 0.17, { abre = 0.15, dx = 0.4, fora = 0.15 } = {}) {
  corpoEm(pos, V3(-Math.sin(recl), Math.cos(recl), 0), V3(Math.cos(recl), Math.sin(recl), 0));
  B.pelvis.updateMatrixWorld(true);
  for (const l of ["l", "r"]) {
    const z = l === "l" ? -1 : 1;
    perna(l, V3(pos.x + dx, ALT_TORN, z * abre), V3(0.3, 1, z * 0.15));
    pe(l, V3(1, 0, z * fora));
  }
}
const eixoPega = (v, A, ang) => v.clone().applyAxisAngle(A, ang);
// braço que não trabalha: pendurado ao lado do corpo (sem isso ele fica aberto em T) ou com a mão na cintura
function bracoSolto(l, ab = 0.16, fr = 0.12) {
  const S = ondeEsta("upperarm_" + l), lat = LAT(l);
  const dir = V3(0, -Math.cos(ab), 0).add(lat.clone().multiplyScalar(Math.sin(ab))).add(F0.clone().multiplyScalar(fr)).normalize();
  braco(l, S.clone().add(dir.clone().multiplyScalar(ALC() * 0.95)), V3(0, 0.15, 0).add(F0.clone().multiplyScalar(-1)));
  mao(l, dir, lat.clone().multiplyScalar(-1)); fecha(l, 0.35);
}
function maoNaCintura(l) {
  const lat = LAT(l), P = ondeEsta("pelvis");
  braco(l, P.clone().add(lat.clone().multiplyScalar(0.235)).add(V3(0.015, 0.1, 0.0)), lat.clone().add(F0.clone().multiplyScalar(-0.5)));
  mao(l, F0.clone().multiplyScalar(0.55).add(V3(0, -0.7, 0)), lat.clone().multiplyScalar(-1).add(V3(0, 0.3, 0))); fecha(l, 0.3);
}
// cabo da torre em segmentos no mundo (passa por pontos intermediários); a pilha sobe com o cabo que sai (L0 = comprimento no t=1)
function criaCabo(g, torre, n = 1) {
  torre.cabo.visible = false;
  const o = { torre, cabos: [...Array(n)].map(() => g.add(K.cabo()) && g.children[g.children.length - 1]), L0: null, pilha: torre.g.children.find((c) => c.userData && c.userData.sobe) };
  return o;
}
function ligaCabo(o, pts) {
  const P = [o.torre.saida(), ...pts]; let L = 0;
  for (let i = 0; i < P.length - 1; i++) { K.poe(o.cabos[i], P[i], P[i + 1]); L += P[i].distanceTo(P[i + 1]); }
  if (o.L0 === null) o.L0 = L;
  o.pilha.userData.sobe(Math.min(0.5, Math.max(0, (L - o.L0) * 0.5)));
}
// aponta uma alça (eixo X local = k) com o "olho" (+Y local) pro lado de ate; devolve o ponto do olho no mundo
function alcaEm(obj, O, k, ate, olho = V3(0, 0.075, 0)) {
  const x = k.clone().normalize(), y = ate.clone().sub(O); y.sub(x.clone().multiplyScalar(y.dot(x))).normalize();
  obj.position.copy(O); obj.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(x, y, x.clone().cross(y))); obj.updateMatrixWorld(true);
  return obj.localToWorld(olho.clone());
}

// ---------- moldes ----------
Object.assign(MOLDES, {
  // Desenvolvimento com halteres sentado (+ Arnold: palmas pra ti embaixo, giram pra frente enquanto sobe)
  om_pressSent: {
    nome: "Desenvolvimento com halteres sentado",
    deltoide: () => "deltoides",
    musc: { deltoide: 1, triceps: 0.7, trapezio: 0.45 },
    dica: "Costas coladas no encosto, pés firmes. Halteres na altura do ombro, cotovelo um pouco à frente do tronco. Empurra pra cima até quase travar e desce controlando até a altura da orelha.",
    cam: { alvo: V3(0.05, 1.25, 0), dist: 4.2, yaw: 52, pitch: 10 },
    cena(g) {
      g.add(K.piso(2.6, 2.6)); const b = K.banco({ inclina: 80 }); g.add(b.g);
      this.h = [halter(0.7), halter(0.7)]; g.add(...this.h);
      if (this.p.arnold) this.dica0 = 1;
    },
    pose(t) {
      zera();
      const arn = this.p.arnold, recl = 0.17;
      sentaCorpo(V3(0.15, 0.575, 0), recl);
      gira("neck_01", EX, -recl * 0.7);
      B.pelvis.updateMatrixWorld(true);
      const om = ombroMeio(), alc = ALC() + 0.035, kk = 1 - t, sk = kk * kk * (3 - 2 * kk);
      ["l", "r"].forEach((l, i) => {
        const s = sLado(l), lat = LAT(l), S = ondeEsta("upperarm_" + l);
        const topo = om.clone().add(V3(0, alc * 0.975, -0.005)).add(lat.clone().multiplyScalar(0.2));
        let baixo, polo, k, n;
        if (!arn) {
          baixo = om.clone().add(V3(0, -0.015, 0)).add(F0.clone().multiplyScalar(0.05)).add(lat.clone().multiplyScalar(0.34));
          polo = V3(0, -1, 0).add(F0.clone().multiplyScalar(0.25)).add(lat.clone().multiplyScalar(0.9));
          k = lat.clone().multiplyScalar(-1); n = F0.clone().add(V3(0, 0.45, 0));
        } else {
          baixo = om.clone().add(V3(0, 0.07, 0)).add(F0.clone().multiplyScalar(0.19)).add(lat.clone().multiplyScalar(0.115));
          polo = V3(0, -1, 0).add(F0.clone().multiplyScalar(0.8)).add(lat.clone().multiplyScalar(0.25));
        }
        const pos = baixo.clone().lerp(topo, sk).add(F0.clone().multiplyScalar(arn ? 0.04 * Math.sin(Math.PI * sk) : 0.03 * Math.sin(Math.PI * sk)));
        if (arn) {
          const poloT = lat.clone().multiplyScalar(0.8).add(F0.clone().multiplyScalar(0.1)).add(V3(0, -0.4, 0));
          const pl = polo.clone().lerp(poloT, suave(0.1, 0.9, sk));
          const th = Math.PI * suave(0.04, 0.78, sk);               // 0 = palma pra ti, PI = palma pra frente
          const r = ik(S, pos, COMP.upperarm_l, COMP.lowerarm_l, pl), A = pos.clone().sub(r.E).normalize();
          k = eixoPega(lat.clone(), A, s * th); n = eixoPega(F0.clone().multiplyScalar(-0.85).add(V3(0, 0.5, 0)), A, s * th);
          agarra(l, { ponto: pos, eixo: k, palma: n, R: 0.016, polo: pl });
        } else agarra(l, { ponto: pos, eixo: k, palma: n, R: 0.016, polo });
        seguraHalter(this.h[i], l);
      });
    },
  },
  // Desenvolvimento no Smith, sentado (barra presa nas guias: só sobe e desce, reta)
  om_pressSmith: {
    nome: "Desenvolvimento no Smith",
    deltoide: () => "deltoides",
    musc: { deltoide: 1, triceps: 0.7, trapezio: 0.4 },
    dica: "Encosto quase em pé, banco alinhado pra barra descer rente ao rosto, até a altura do queixo. Empurra reto pra cima sem arquear a lombar e destrava o gancho antes de começar.",
    cam: { alvo: V3(0.1, 1.2, 0), dist: 4.3, yaw: 58, pitch: 9 },
    cena(g) {
      g.add(K.piso(2.8, 2.8)); const b = K.banco({ inclina: 80 }); g.add(b.g);
      this.sm = K.smith({ alt: 2.15, larg: 1.25 }); this.sm.g.rotation.y = Math.PI; g.add(this.sm.g);
    },
    pose(t) {
      zera();
      const recl = 0.17;
      sentaCorpo(V3(0.15, 0.575, 0), recl);
      B.pelvis.updateMatrixWorld(true);
      const kk = 1 - t, sk = kk * kk * (3 - 2 * kk);
      gira("neck_01", EX, -recl * 0.7 - 0.2 * Math.sin(Math.PI * Math.min(1, t * 1.25)));
      B.pelvis.updateMatrixWorld(true);
      const om = ombroMeio(), alc = ALC() + 0.035, barX = om.x + 0.14, lar = 0.28;
      const dx = barX - om.x, topo = om.y + Math.sqrt((alc * 0.975) ** 2 - dx * dx - (lar - 0.195) ** 2), baixo = om.y + 0.045;
      const y = lerp(baixo, topo, sk);
      this.sm.g.position.x = barX; this.sm.barra.position.y = y;
      for (const l of ["l", "r"]) {
        const lat = LAT(l);
        agarra(l, { ponto: V3(barX, y, 0).add(lat.clone().multiplyScalar(lar)), eixo: lat.clone().multiplyScalar(-1), R: 0.014, palma: F0.clone().add(V3(0, 0.45, 0)),
          polo: V3(0, -1, 0).add(F0.clone().multiplyScalar(0.12)).add(lat.clone().multiplyScalar(0.6)) });
      }
    },
  },

  // Desenvolvimento na máquina (articulada, pegada neutra, convergente)
  om_pressMaq: {
    nome: "Desenvolvimento na máquina",
    deltoide: () => "deltoides",
    musc: { deltoide: 1, triceps: 0.7, trapezio: 0.4 },
    dica: "Regula o banco pra o cabo ficar na altura do ombro. Costas coladas, empurra os dois puxadores juntos sem encolher o ombro e desce até a altura do queixo.",
    cam: { alvo: V3(0.0, 1.15, 0), dist: 4.3, yaw: 50, pitch: 10 },
    cena(g) {
      g.add(K.piso(2.8, 2.8));
      const m = new THREE.Group(), recl = 0.17, piv = V3(-0.36, 1.28, 0);
      for (const z of [-0.3, 0.3]) m.add(K.caixa(1.5, 0.06, 0.09, M.quadro, 0.015).translateX(0.05).translateY(0.03).translateZ(z));
      m.add(K.caixa(0.1, 0.06, 0.69, M.quadro, 0.015).translateX(0.74).translateY(0.03)); m.add(K.caixa(0.1, 0.06, 0.69, M.quadro, 0.015).translateX(-0.66).translateY(0.03));
      const seat = K.caixa(0.46, 0.09, 0.44, M.estofado, 0.035); seat.position.set(0.2, 0.42, 0); m.add(seat);
      m.add(K.viga(V3(0.22, 0.37, 0), V3(0.22, 0.06, 0), 0.07)); m.add(K.caixa(0.5, 0.05, 0.12, M.quadro, 0.01).translateX(0.22).translateY(0.085));
      const enc = K.caixa(0.075, 0.66, 0.5, M.estofado, 0.03); enc.position.set(-0.04, 0.8, 0); enc.rotation.z = recl; m.add(enc);
      m.add(K.viga(V3(-0.1, 0.56, 0), V3(-0.4, 0.56, 0), 0.06)); m.add(K.viga(V3(-0.1, 0.9, 0), V3(-0.4, 0.9, 0), 0.06));
      for (const z of [-0.3, 0.3]) { m.add(K.viga(V3(-0.42, 0.06, z), V3(-0.42, 1.5, z), 0.075));
        const hub = K.cilU(0.05, M.aco, 24); hub.rotation.x = Math.PI / 2; hub.scale.y = 0.1; hub.position.set(piv.x, piv.y, z * 1.12); m.add(hub); }
      m.add(K.viga(V3(-0.42, 1.5, -0.3), V3(-0.42, 1.5, 0.3), 0.07));
      const pil = K.pilha(); pil.rotation.y = Math.PI / 2; pil.position.set(-0.82, 0.04, 0); m.add(pil); this.pil = pil;
      m.add(K.caixa(0.04, 1.35, 0.4, M.quadro, 0.01).translateX(-0.93).translateY(0.7));
      this.arms = ["l", "r"].map(() => ({ braco: K.viga(V3(0, 0, 0), V3(0, 1, 0), 0.04, M.quadro), cruz: K.tubo(V3(0, 0, 0), V3(0, 1, 0), 0.016, M.cromo), pega: K.cilU(0.016, M.borracha) }));
      this.arms.forEach((a) => { m.add(a.braco, a.cruz, a.pega); });
      this.cabo = K.cabo(); m.add(this.cabo);
      const roldana = K.cilU(0.05, M.aco, 24); roldana.rotation.x = Math.PI / 2; roldana.scale.y = 0.05; roldana.position.set(-0.82, 1.5, 0); m.add(roldana);
      this.piv = piv; g.add(sombreia(m));
    },
    pose(t) {
      zera();
      const recl = 0.17; sentaCorpo(V3(0.15, 0.575, 0), recl); gira("neck_01", EX, -recl * 0.7);
      B.pelvis.updateMatrixWorld(true);
      const kk = 1 - t, sk = kk * kk * (3 - 2 * kk), R = 0.56, th = lerp(-0.49, 0.49, sk), piv = this.piv, d = V3(Math.cos(th), Math.sin(th), 0);
      ["l", "r"].forEach((l, i) => {
        const lat = LAT(l), z = lat.z, h = V3(piv.x + R * d.x, piv.y + R * d.y, z * 0.24), a = this.arms[i];
        agarra(l, { ponto: h, eixo: F0.clone().multiplyScalar(-1), palma: lat.clone().multiplyScalar(-1), R: 0.016, polo: V3(0, -1, 0).add(lat.clone().multiplyScalar(0.8)).add(F0.clone().multiplyScalar(0.2)) });
        const q = V3(h.x - 0.075, h.y, z * 0.33);
        K.poe(a.braco, V3(piv.x, piv.y, z * 0.33), q); K.poe(a.cruz, q, V3(q.x, q.y, z * 0.24));
        K.poe(a.pega, V3(h.x - 0.075, h.y, z * 0.24), V3(h.x + 0.075, h.y, z * 0.24));
      });
      const cola = V3(piv.x - 0.16 * d.x, piv.y - 0.16 * d.y, 0), topo = V3(-0.82, 1.5, 0);
      this.pil.userData.sobe(sk * 0.28); K.poe(this.cabo, cola, topo);
    },
  },

  // Push press: perna dá o impulso, braço termina (barra em pé; ritmo próprio: desce, agacha de leve, explode)
  om_pushPress: {
    nome: "Push press",
    deltoide: () => "deltoides",
    musc: { deltoide: 1, triceps: 0.8, quadriceps: 0.55, trapezio: 0.5 },
    dica: "Barra apoiada na frente do ombro. Dobra joelho e quadril uns 10 cm, mantendo o tronco reto, e explode pra cima: a perna lança a barra e o braço termina o movimento até travar em cima.",
    cam: { alvo: V3(0, 1.1, 0), dist: 4.6, yaw: 34, pitch: 8 },
    cena(g) { g.add(tablado()); this.bar = barra(1); g.add(this.bar); },
    fase(r) {
      let u = r % CICLO;
      if (u < 0.9) return { t: 0, f: "trava em cima", esforco: 0.3 };
      u -= 0.9; if (u < 1.9) return { t: sen(u / 1.9), f: "desce controlando até o ombro", esforco: 0.5 };
      u -= 1.9; if (u < 0.4) return { t: 1, f: "agacha de leve", esforco: 0.7 };
      u -= 0.4; return { t: 1 - sobeCurva(u / 0.85), f: "explode: perna e braço", esforco: 1 };
    },
    pose(t) {
      zera();
      const dip = 0.15 * suave(0.7, 1, t);
      emPe(V3(-dip * 0.5, ALT_QUADRIL - 0.015 - dip, 0), F0, -0.02 + dip * 1.4);
      gira("neck_01", EX, -0.22 * Math.sin(Math.PI * Math.min(1, t * 1.3)) - dip * 0.8); gira("head", EX, -0.08 * t);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.14, fora: 0.25, poloFora: 0.35 });
      const E = esquerda(F0), om = ombroMeio(), alc = ALC();
      const baixo = om.clone().add(V3(0, -0.01, 0)).add(F0.clone().multiplyScalar(0.15)), topo = om.clone().add(V3(0, alc * 0.96, 0)).add(F0.clone().multiplyScalar(-0.02));
      const kk = 1 - t, sk = kk * kk * (3 - 2 * kk), pos = baixo.clone().lerp(topo, sk).add(F0.clone().multiplyScalar(0.07 * Math.sin(Math.PI * sk)));
      this.bar.position.copy(pos); this.bar.rotation.set(0, Math.PI / 2, 0);
      ["l", "r"].forEach((l) => {
        const s = sLado(l);
        agarra(l, { ponto: pos.clone().add(E.clone().multiplyScalar(s * 0.27)), eixo: E.clone().multiplyScalar(-s), R: 0.014, palma: F0.clone().add(V3(0, 0.45, 0)),
          polo: V3(0, -1, 0).add(F0.clone().multiplyScalar(0.75)).add(E.clone().multiplyScalar(s * 0.35)) });
      });
    },
  },
  // Elevação lateral na polia baixa, unilateral: a polia fica do lado oposto e o cabo cruza na frente do corpo
  om_lateralPolia: {
    nome: "Elevação lateral na polia",
    deltoide: () => "deltoide lateral",
    musc: { deltoide: 1, trapezio: 0.4 },
    dica: "De lado pra polia baixa, mão de fora segurando o cabo que cruza na frente da coxa. Cotovelo levemente dobrado, sobe o braço pelo lado até a altura do ombro, sem balançar o tronco, e desce devagar.",
    cam: { alvo: V3(0.1, 1.05, 0.1), dist: 3.9, yaw: 38, pitch: 10 },
    cena(g) {
      g.add(K.piso(2.6, 2.6));
      this.torre = K.torre({ alt: 0.25 }); this.torre.g.position.set(0.5, 0, -1.0); g.add(this.torre.g);
      this.alca = K.estribo(); g.add(this.alca);
      this.cab = criaCabo(g, this.torre, 1); this.pose(1);
    },
    pose(t) {
      zera();
      emPe(V3(0, ALT_QUADRIL - 0.015, 0), F0, 0.04);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.12, fora: 0.2, poloFora: 0.2 });
      bracoSolto("l", 0.1, 0.05); maoNaCintura("l");
      const l = "r", s = sLado(l), lat = LAT(l), S = ondeEsta("upperarm_" + l);
      const ab = -0.32 + (1 - t) * 1.86, fr = lerp(0.2, 0.42, t * t);
      const dir = V3(0, -Math.cos(ab), 0).add(lat.clone().multiplyScalar(Math.sin(ab))).add(F0.clone().multiplyScalar(fr)).normalize();
      const n = V3(0, -1, 0).add(lat.clone().multiplyScalar(-0.4)).normalize();
      const O = agarra(l, { punho: S.clone().add(dir.multiplyScalar(ALC() * 0.95)), palma: n, R: 0.016, eixo: n.clone().cross(dir).multiplyScalar(s),
        polo: V3(0, 0.25, 0).add(F0.clone().multiplyScalar(-1)) });
      const olho = alcaEm(this.alca, O, n.clone().cross(dir).multiplyScalar(s), this.torre.saida());
      ligaCabo(this.cab, [olho]);
    },
  },

  // Elevação lateral inclinada: tronco inclinado pro lado oposto, segurando num poste (a mão livre faz o movimento)
  om_lateralInclinada: {
    nome: "Elevação lateral inclinada",
    deltoide: () => "deltoide lateral",
    musc: { deltoide: 1, trapezio: 0.4 },
    dica: "Segura num poste com a mão livre e inclina o corpo pro lado contrário. O halter parte afastado da coxa, então o deltoide trabalha já na posição mais alongada. Sobe até o braço ficar paralelo ao chão e desce devagar.",
    cam: { alvo: V3(0.05, 1.05, 0.15), dist: 3.9, yaw: 55, pitch: 10 },
    cena(g) {
      g.add(tablado());
      this.poste = new THREE.Group(); this.poste.add(K.tubo(V3(0, 0, 0), V3(0, 1.95, 0), 0.035, M.quadro), K.caixa(0.34, 0.04, 0.34, M.quadro, 0.01).translateY(0.02));
      sombreia(this.poste); g.add(this.poste);
      this.h = halter(0.6); g.add(this.h);
    },
    pose(t) {
      zera();
      const phi = 0.3;
      corpoEm(V3(0, 0.955, 0.2), V3(0, Math.cos(phi), Math.sin(phi)), F0);
      gira("neck_01", EX, 0.0);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { const z = l === "l" ? -1 : 1; perna(l, V3(0, ALT_TORN, z * 0.1), V3(1, 0.3, z * 0.3)); pe(l, V3(1, 0, z * 0.2)); }
      const Sl = ondeEsta("upperarm_l"); this.poste.position.set(0.02, 0, Sl.z - 0.38);
      braco("l", V3(0.03, Sl.y + 0.16, this.poste.position.z + 0.04), V3(0, -1, -0.4).add(F0.clone().multiplyScalar(-0.4)));
      mao("l", V3(0, 0, 1).add(V3(0, 0.8, 0)), F0.clone().multiplyScalar(-1)); fecha("l", 1.1);
      const l = "r", s = -1, lat = LAT(l), S = ondeEsta("upperarm_" + l);
      const ab = 0.05 + (1 - t) * 1.47;
      const dir = V3(0, -Math.cos(ab), 0).add(lat.clone().multiplyScalar(Math.sin(ab))).add(F0.clone().multiplyScalar(0.12)).normalize();
      const n = V3(0, -1, 0).add(lat.clone().multiplyScalar(-0.4)).normalize();
      agarra(l, { punho: S.clone().add(dir.multiplyScalar(ALC() * 0.95)), palma: n, R: 0.016, eixo: n.clone().cross(dir).multiplyScalar(s), polo: V3(0, 0.25, 0).add(F0.clone().multiplyScalar(-1)) });
      seguraHalter(this.h, l);
    },
  },

  // Elevação lateral na máquina: cotovelo a 90° apoiado nas almofadas, os dois braços sobem juntos
  om_lateralMaq: {
    nome: "Elevação lateral na máquina",
    deltoide: () => "deltoide lateral",
    musc: { deltoide: 1, trapezio: 0.35 },
    dica: "Costas coladas, cotovelos a 90° apoiados nas almofadas, na linha do ombro. Empurra os cotovelos pra fora e pra cima até a altura do ombro, sem encolher, e desce devagar.",
    cam: { alvo: V3(0.1, 1.0, 0), dist: 4.2, yaw: 62, pitch: 8 },
    cena(g) {
      g.add(K.piso(2.8, 2.8));
      const m = new THREE.Group(), recl = 0.05;
      for (const z of [-0.3, 0.3]) m.add(K.caixa(1.5, 0.06, 0.09, M.quadro, 0.015).translateX(0.0).translateY(0.03).translateZ(z));
      m.add(K.caixa(0.1, 0.06, 0.69, M.quadro, 0.015).translateX(0.7).translateY(0.03)); m.add(K.caixa(0.1, 0.06, 0.69, M.quadro, 0.015).translateX(-0.7).translateY(0.03));
      const seat = K.caixa(0.46, 0.09, 0.44, M.estofado, 0.035); seat.position.set(0.2, 0.42, 0); m.add(seat);
      m.add(K.viga(V3(0.22, 0.37, 0), V3(0.22, 0.06, 0), 0.07)); m.add(K.caixa(0.5, 0.05, 0.12, M.quadro, 0.01).translateX(0.22).translateY(0.085));
      const enc = K.caixa(0.075, 0.66, 0.46, M.estofado, 0.03); enc.position.set(-0.008, 0.837, 0); enc.rotation.z = recl; m.add(enc);
      m.add(K.viga(V3(-0.06, 0.56, 0), V3(-0.5, 0.56, 0), 0.06)); m.add(K.viga(V3(-0.06, 0.95, 0), V3(-0.5, 0.95, 0), 0.06));
      for (const z of [-0.3, 0.3]) m.add(K.viga(V3(-0.5, 0.06, z), V3(-0.5, 1.45, z), 0.075));
      m.add(K.viga(V3(-0.5, 1.45, -0.3), V3(-0.5, 1.45, 0.3), 0.07));
      const pil = K.pilha(); pil.rotation.y = Math.PI / 2; pil.position.set(-0.85, 0.04, 0); m.add(pil); this.pil = pil;
      m.add(K.caixa(0.04, 1.35, 0.4, M.quadro, 0.01).translateX(-0.96).translateY(0.7));
      this.lev = ["l", "r"].map(() => {
        const o = { hub: K.cilU(0.045, M.aco, 24), rad: K.viga(V3(0, 0, 0), V3(0, 1, 0), 0.04, M.quadro), fwd: K.viga(V3(0, 0, 0), V3(1, 0, 0), 0.04, M.quadro),
          cruz: K.tubo(V3(0, 0, 0), V3(0, 1, 0), 0.014, M.cromo), grip: K.cilU(0.016, M.borracha), pad: K.caixa(0.2, 0.05, 0.14, M.estofado, 0.02), mastro: K.tubo(V3(0, 0, 0), V3(0, 1, 0), 0.03, M.quadro) };
        o.hub.scale.y = 0.09; o.hub.rotation.z = Math.PI / 2; m.add(...Object.values(o)); return o;
      });
      g.add(sombreia(m));
    },
    pose(t) {
      zera();
      sentaCorpo(V3(0.15, 0.575, 0), 0.05); B.pelvis.updateMatrixWorld(true);
      const kk = 1 - t, sk = kk * kk * (3 - 2 * kk), th = 0.2 + sk * 1.28;
      ["l", "r"].forEach((l, i) => {
        const lat = LAT(l), z = lat.z, S = ondeEsta("upperarm_" + l), o = this.lev[i];
        const u = V3(0, -Math.cos(th), z * Math.sin(th)), w = V3(0, Math.sin(th), z * Math.cos(th));
        const cot = S.clone().add(u.clone().multiplyScalar(COMP.upperarm_l)), W = cot.clone().add(F0.clone().multiplyScalar(COMP.lowerarm_l * 0.98)).add(V3(0, 0.0, 0));
        const O = agarra(l, { punho: W, eixo: V3(0, 1, 0), palma: lat.clone().multiplyScalar(-1), R: 0.016, polo: u });
        const H = V3(S.x - 0.28, S.y, S.z), a = 0.095;
        const Pa = H.clone().add(w.clone().multiplyScalar(a)).add(u.clone().multiplyScalar(COMP.upperarm_l * 1.05));
        K.poe(o.hub, H.clone().add(V3(-0.04, 0, 0)), H.clone().add(V3(0.04, 0, 0)));
        K.poe(o.rad, H.clone().add(w.clone().multiplyScalar(a)).add(u.clone().multiplyScalar(0.05)), Pa);
        const Pb = V3(O.x + 0.0, Pa.y, Pa.z); K.poe(o.fwd, Pa, Pb);
        const topo = O.clone().add(V3(0, 0.055, 0)); K.poe(o.grip, O.clone().add(V3(0, -0.065, 0)), topo);
        K.poe(o.cruz, topo, V3(Pb.x, Pb.y, Pb.z));
        o.pad.position.copy(S).add(u.clone().multiplyScalar(COMP.upperarm_l * 0.98)).add(w.clone().multiplyScalar(0.07)).add(F0.clone().multiplyScalar(0.12));
        o.pad.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(F0, w, F0.clone().cross(w)));
        K.poe(o.mastro, V3(H.x - 0.04, H.y, H.z), V3(-0.5, H.y, z * 0.3));
      });
      this.pil.userData.sobe(sk * 0.25);
    },
  },

  // Elevação frontal com anilha: as duas mãos nas laterais da anilha, braço esticado sobe até a altura dos olhos
  om_frontalAnilha: {
    nome: "Elevação frontal com anilha",
    deltoide: () => "deltoide anterior",
    musc: { deltoide: 1, peitoral: 0.5, trapezio: 0.4 },
    dica: "Anilha pelas laterais, braços quase esticados na frente da coxa. Sobe até a altura dos olhos, sem balançar o tronco, e desce devagar sem deixar a anilha cair.",
    cam: { alvo: V3(0.15, 1.1, 0), dist: 3.7, yaw: 48, pitch: 8 },
    cena(g) { g.add(tablado()); this.pl = K.anilhaMao(0.2); const w = new THREE.Group(); this.pl.rotation.z = Math.PI / 2; w.add(this.pl); this.plG = w; g.add(w); },
    pose(t) {
      zera();
      emPe(V3(0, ALT_QUADRIL - 0.015, 0), F0, 0.03);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.13, fora: 0.2, poloFora: 0.2 });
      const om = ombroMeio(), ab = 0.32 + (1 - t) * 1.3, dir = V3(0, -Math.cos(ab), 0).add(F0.clone().multiplyScalar(Math.sin(ab))).normalize(), pos = {};
      for (const l of ["l", "r"]) {
        const lat = LAT(l), S = ondeEsta("upperarm_" + l);
        pos[l] = agarra(l, { ponto: S.clone().add(dir.clone().multiplyScalar(ALC() * 0.985 + 0.02)).add(lat.clone().multiplyScalar(0.0)), eixo: V3(0, 1, 0), palma: lat.clone().multiplyScalar(-1), R: 0.02,
          polo: V3(0, 0.1, 0).add(F0.clone().multiplyScalar(-1)).add(lat.clone().multiplyScalar(0.35)) });
      }
      this.plG.position.copy(pos.l).add(pos.r).multiplyScalar(0.5);
    },
  },

  // Elevação frontal na polia: de costas pra polia baixa, o cabo passa entre as pernas
  om_frontalPolia: {
    nome: "Elevação frontal na polia",
    deltoide: () => "deltoide anterior",
    musc: { deltoide: 1, peitoral: 0.5, trapezio: 0.4 },
    dica: "De costas pra polia baixa, o cabo passando entre as pernas. Braços quase esticados, sobe a barra até a altura dos olhos sem inclinar o tronco pra trás e desce com o cabo sempre tenso.",
    cam: { alvo: V3(0.0, 1.0, 0), dist: 4.4, yaw: 45, pitch: 8 },
    cena(g) {
      g.add(K.piso(2.8, 2.8));
      this.torre = K.torre({ alt: 0.2 }); this.torre.g.rotation.y = Math.PI / 2; this.torre.g.position.set(-0.95, 0, 0); g.add(this.torre.g);
      this.bar = K.barraReta(0.46); g.add(this.bar);
      this.cab = criaCabo(g, this.torre, 2); this.pose(1);
    },
    pose(t) {
      zera();
      emPe(V3(0, ALT_QUADRIL - 0.015, 0), F0, 0.02);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.14, fora: 0.2, poloFora: 0.2 });
      const ab = 0.12 + (1 - t) * 1.38, dir = V3(0, -Math.cos(ab), 0).add(F0.clone().multiplyScalar(Math.sin(ab))).normalize(), pos = {};
      for (const l of ["l", "r"]) {
        const lat = LAT(l), S = ondeEsta("upperarm_" + l);
        pos[l] = agarra(l, { ponto: S.clone().add(dir.clone().multiplyScalar(ALC() * 0.985 + 0.02)).add(lat.clone().multiplyScalar(0.025)), eixo: lat.clone().multiplyScalar(-1), R: 0.0135,
          palma: F0.clone().multiplyScalar(-Math.cos(ab)).add(V3(0, -Math.sin(ab), 0)),
          polo: V3(0, 0.1, 0).add(F0.clone().multiplyScalar(-1)).add(lat.clone().multiplyScalar(0.3)) });
      }
      const eixoB = pos.l.clone().sub(pos.r).normalize(), mid = pos.l.clone().add(pos.r).multiplyScalar(0.5);
      const olho = alcaEm(this.bar, mid, eixoB, V3(0, 0.74, 0), V3(0, 0.024, 0));
      ligaCabo(this.cab, [V3(0.0, 0.72, 0), olho]);
    },
  },
  // Crucifixo inverso com halteres: tronco quase paralelo ao chão, braços abrem pelos lados até a linha dos ombros
  om_invHalter: {
    nome: "Crucifixo inverso com halteres",
    deltoide: () => "deltoide posterior",
    musc: { deltoide: 1, trapezio: 0.6 },
    dica: "Quadril pra trás, tronco quase paralelo ao chão e coluna reta. Cotovelo levemente dobrado e fixo, abre os braços como asas até a linha dos ombros e junta as escápulas sem balançar.",
    cam: { alvo: V3(0, 0.95, 0), dist: 3.8, yaw: 235, pitch: 14 },
    cena(g) { g.add(tablado()); this.h = [halter(0.5), halter(0.5)]; g.add(...this.h); },
    pose(t) {
      zera();
      emPe(V3(-0.3, ALT_QUADRIL - 0.12, 0), F0, 1.05);
      gira("spine_02", EX, 0.1); gira("spine_03", EX, 0.08); gira("neck_01", EX, -0.75); gira("head", EX, -0.15);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.14, fora: 0.2, poloFora: 0.25 });
      const ab = 0.1 + (1 - t) * 1.4;
      ["l", "r"].forEach((l, i) => {
        const s = sLado(l), lat = LAT(l), S = ondeEsta("upperarm_" + l);
        const dir = V3(0, -Math.cos(ab), 0).add(lat.clone().multiplyScalar(Math.sin(ab))).add(F0.clone().multiplyScalar(0.08 * (1 - t) - 0.05)).normalize();
        const n = V3(0, -1, 0).add(lat.clone().multiplyScalar(-0.5)).normalize();
        agarra(l, { punho: S.clone().add(dir.multiplyScalar(ALC() * 0.94)), palma: n, R: 0.016, eixo: n.clone().cross(dir).multiplyScalar(s), polo: V3(0, 0.3, 0).add(F0.clone().multiplyScalar(-0.8)) });
        seguraHalter(this.h[i], l);
      });
    },
  },

  // Crucifixo inverso na máquina (peck deck invertido): peito no apoio, braços abrem pra trás
  om_invMaq: {
    nome: "Crucifixo inverso na máquina",
    deltoide: () => "deltoide posterior",
    musc: { deltoide: 1, trapezio: 0.6 },
    dica: "Peito apoiado na almofada, braços quase esticados na altura do ombro. Abre os puxadores pra trás em arco, juntando as escápulas, e volta devagar sem deixar a pilha encostar.",
    cam: { alvo: V3(0.2, 1.1, 0), dist: 4.2, yaw: 120, pitch: 10 },
    cena(g) {
      g.add(K.piso(2.8, 2.8));
      const m = new THREE.Group();
      for (const z of [-0.3, 0.3]) m.add(K.caixa(1.5, 0.06, 0.09, M.quadro, 0.015).translateX(0.45).translateY(0.03).translateZ(z));
      m.add(K.caixa(0.1, 0.06, 0.69, M.quadro, 0.015).translateX(1.15).translateY(0.03)); m.add(K.caixa(0.1, 0.06, 0.69, M.quadro, 0.015).translateX(-0.25).translateY(0.03));
      const seat = K.caixa(0.42, 0.09, 0.4, M.estofado, 0.035); seat.position.set(-0.05, 0.42, 0); m.add(seat);
      m.add(K.viga(V3(-0.05, 0.37, 0), V3(-0.05, 0.06, 0), 0.07));
      const pad = K.caixa(0.09, 0.55, 0.42, M.estofado, 0.035); pad.position.set(0.27, 1.02, 0); pad.rotation.z = -0.12; m.add(pad);
      m.add(K.viga(V3(0.45, 0.06, 0), V3(0.45, 1.58, 0), 0.1)); m.add(K.viga(V3(0.3, 0.8, 0), V3(0.45, 0.8, 0), 0.06));
      const pil = K.pilha(); pil.rotation.y = Math.PI / 2; pil.position.set(0.95, 0.04, 0); m.add(pil); this.pil = pil;
      m.add(K.caixa(0.04, 1.35, 0.4, M.quadro, 0.01).translateX(1.08).translateY(0.7));
      m.add(K.viga(V3(0.45, 1.58, 0), V3(0.95, 1.58, 0), 0.08));
      this.lev = ["l", "r"].map(() => {
        const o = { hub: K.cilU(0.05, M.aco, 24), hor: K.viga(V3(0, 0, 0), V3(0, 1, 0), 0.04, M.quadro), post: K.tubo(V3(0, 0, 0), V3(0, 1, 0), 0.016, M.cromo), grip: K.cilU(0.016, M.borracha) };
        m.add(...Object.values(o)); return o;
      });
      g.add(sombreia(m));
    },
    pose(t) {
      zera();
      corpoEm(V3(-0.05, 0.575, 0), V3(0.2, 0.98, 0), V3(0.98, -0.2, 0)); gira("neck_01", EX, -0.1);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { const z = l === "l" ? -1 : 1; perna(l, V3(-0.25, ALT_TORN, z * 0.2), V3(0.3, 1, z * 0.3)); pe(l, V3(1, 0, z * 0.15)); }
      const ph = 0.16 + (1 - t) * 1.12;
      ["l", "r"].forEach((l, i) => {
        const lat = LAT(l), S = ondeEsta("upperarm_" + l), o = this.lev[i];
        const dir = F0.clone().multiplyScalar(Math.cos(ph)).add(lat.clone().multiplyScalar(Math.sin(ph))).add(V3(0, -0.04, 0)).normalize();
        const O = agarra(l, { ponto: S.clone().add(dir.multiplyScalar(ALC() * 0.95)), eixo: V3(0, 1, 0), palma: lat.clone().multiplyScalar(-1), R: 0.016, polo: V3(0, 0.3, 0).add(lat.clone().multiplyScalar(0.3)).add(F0.clone().multiplyScalar(-0.6)) });
        const H = V3(S.x + 0.1, 1.58, S.z), top = V3(O.x, 1.58, O.z);
        K.poe(o.hub, H.clone().add(V3(0, -0.04, 0)), H.clone().add(V3(0, 0.04, 0)));
        K.poe(o.hor, H, top); K.poe(o.post, top, O.clone().add(V3(0, 0.07, 0))); K.poe(o.grip, O.clone().add(V3(0, -0.065, 0)), O.clone().add(V3(0, 0.065, 0)));
      });
      this.pil.userData.sobe((1 - t) * 0.25);
    },
  },

  // Crucifixo inverso na polia (crossover alto, cabos cruzados)
  om_invPolia: {
    nome: "Crucifixo inverso na polia",
    deltoide: () => "deltoide posterior",
    musc: { deltoide: 1, trapezio: 0.6 },
    dica: "Entre as duas polias na altura do ombro, cabos cruzados. Braços quase esticados, abre pra trás e pros lados como asas até a linha dos ombros, juntando as escápulas, e volta com o cabo sempre tenso.",
    cam: { alvo: V3(0.3, 1.2, 0), dist: 4.6, yaw: 100, pitch: 8 },
    cena(g) {
      g.add(K.piso(2.8, 2.8));
      this.tr = [-1, 1].map((z) => { const t = K.torre({ alt: 1.35 }); t.g.position.set(0.7, 0, z * 1.15); if (z > 0) t.g.rotation.y = Math.PI; g.add(t.g); return t; });
      this.al = [K.estribo(), K.estribo()]; g.add(...this.al);
      this.cabs = this.tr.map((t) => criaCabo(g, t, 1)); this.pose(1);
    },
    pose(t) {
      zera();
      emPe(V3(-0.05, ALT_QUADRIL - 0.015, 0), F0, 0.05);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.14, fora: 0.2, poloFora: 0.2 });
      const ph = -0.3 + (1 - t) * 1.62;
      ["l", "r"].forEach((l, i) => {
        const lat = LAT(l), S = ondeEsta("upperarm_" + l);
        const dir = F0.clone().multiplyScalar(Math.cos(ph)).add(lat.clone().multiplyScalar(Math.sin(ph))).add(V3(0, -0.02, 0)).normalize();
        const O = agarra(l, { ponto: S.clone().add(dir.multiplyScalar(ALC() * 0.95)), eixo: V3(0, 1, 0), palma: lat.clone().multiplyScalar(-1), R: 0.016, polo: V3(0, 0.3, 0).add(lat.clone().multiplyScalar(0.3)).add(F0.clone().multiplyScalar(-0.6)) });
        const k = l === "l" ? 1 : 0; // mão esquerda segura o cabo da torre direita (cruzado)
        const olho = alcaEm(this.al[i], O, V3(0, 1, 0), this.tr[k].saida());
        ligaCabo(this.cabs[k], [olho]);
      });
    },
  },

  // Y-raise no banco inclinado: de bruços, braços sobem em Y (trapézio inferior e deltoide posterior)
  om_yRaise: {
    nome: "Y-raise no banco inclinado",
    deltoide: () => "deltoide posterior",
    musc: { trapezio: 1, deltoide: 0.7 },
    dica: "De bruços no banco inclinado, peito apoiado. Braços pendurados, polegares pra cima, sobe os braços em Y na diagonal por cima da cabeça, sem usar impulso, e desce devagar.",
    cam: { alvo: V3(0.2, 1.0, 0), dist: 3.8, yaw: 235, pitch: 12 },
    cena(g) {
      g.add(K.piso(2.8, 2.8)); const m = new THREE.Group(), cab = V3(0.7, 0.7, 0).normalize(), fr = V3(0.7, -0.7, 0).normalize();
      const pad = K.caixa(0.95, 0.09, 0.4, M.estofado, 0.035), c = V3(-0.1, 0.62, 0).add(cab.clone().multiplyScalar(0.3)).add(fr.clone().multiplyScalar(0.13)); pad.position.copy(c);
      pad.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(cab, fr, cab.clone().cross(fr))); m.add(pad);
      m.add(K.viga(c.clone().add(V3(0.15, 0.05, 0)), V3(0.55, 0.06, 0), 0.06)); m.add(K.viga(c.clone().add(cab.clone().multiplyScalar(-0.3)).add(fr.clone().multiplyScalar(0.05)), V3(0.1, 0.06, 0), 0.06));
      for (const x of [0.55, 0.1]) m.add(K.caixa(0.08, 0.05, 0.5, M.quadro, 0.015).translateX(x).translateY(0.025));
      this.h = [halter(0.4), halter(0.4)]; g.add(sombreia(m), ...this.h);
    },
    pose(t) {
      zera();
      const cab = V3(0.7, 0.7, 0).normalize(), fr = V3(0.7, -0.7, 0).normalize();
      corpoEm(V3(-0.1, 0.62, 0), cab, fr); gira("neck_01", EX, 0.25); gira("head", EX, 0.2);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { const z = l === "l" ? -1 : 1; perna(l, V3(-0.55, ALT_TORN + 0.02, z * 0.2), V3(0.4, 1, z * 0.2)); pe(l, V3(1, 0, z * 0.1), 0.35); }
      const w = 1 - t;
      ["l", "r"].forEach((l, i) => {
        const lat = LAT(l), S = ondeEsta("upperarm_" + l);
        const yd = cab.clone().multiplyScalar(0.82).add(lat.clone().multiplyScalar(0.57)).normalize();
        const dir = V3(0, -1, 0).multiplyScalar(1 - w).add(yd.multiplyScalar(w)).add(lat.clone().multiplyScalar(0.5 * Math.sin(Math.PI * w))).normalize();
        agarra(l, { punho: S.clone().add(dir.multiplyScalar(ALC() * 0.94)), eixo: V3(0, 1, 0).lerp(cab.clone(), w).normalize(), palma: lat.clone().multiplyScalar(-1), R: 0.016, polo: V3(0, 0.4, 0).add(lat.clone().multiplyScalar(0.8)) });
        seguraHalter(this.h[i], l);
      });
    },
  },

  // Face pull na polia alta com corda: puxa na direção do rosto, cotovelos altos, rotação externa no fim
  om_facePull: {
    nome: "Face pull",
    deltoide: () => "deltoide posterior",
    musc: { deltoide: 1, trapezio: 0.8 },
    dica: "Polia na altura do rosto, corda com polegares pra ti. Puxa até as mãos ficarem ao lado das orelhas, cotovelos altos e abertos, girando o antebraço pra fora, e volta devagar.",
    cam: { alvo: V3(0.2, 1.4, 0), dist: 3.6, yaw: 60, pitch: 8 },
    cena(g) {
      g.add(K.piso(2.8, 2.8));
      this.torre = K.torre({ alt: 1.7 }); this.torre.g.rotation.y = -Math.PI / 2; this.torre.g.position.set(1.15, 0, 0); g.add(this.torre.g);
      this.corda = K.corda(); g.add(this.corda);
      this.cab = criaCabo(g, this.torre, 1); this.pose(1);
    },
    pose(t) {
      zera();
      emPe(V3(-0.05, ALT_QUADRIL - 0.015, 0), F0, -0.03); gira("neck_01", EX, 0.05);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.14, fora: 0.2, poloFora: 0.2 });
      const om = ombroMeio(), w = 1 - t, hs = {};
      ["l", "r"].forEach((l) => {
        const lat = LAT(l);
        const ini = om.clone().add(F0.clone().multiplyScalar(0.46)).add(V3(0, 0.08, 0)).add(lat.clone().multiplyScalar(0.12));
        const fim = om.clone().add(F0.clone().multiplyScalar(0.07)).add(V3(0, 0.2, 0)).add(lat.clone().multiplyScalar(0.27));
        const pos = ini.lerp(fim, suave(0, 1, w)).add(V3(0, 0.03 * Math.sin(Math.PI * w), 0));
        hs[l] = agarra(l, { ponto: pos, eixo: F0.clone().multiplyScalar(-1), palma: lat.clone().multiplyScalar(-1), R: 0.016,
          polo: V3(0, 0.3 + 0.4 * w, 0).add(lat.clone().multiplyScalar(0.9)).add(F0.clone().multiplyScalar(-0.2)) });
      });
      const mid = hs.l.clone().add(hs.r).multiplyScalar(0.5);
      this.corda.position.copy(mid).add(F0.clone().multiplyScalar(0.12)).add(V3(0, -0.05, 0)); this.corda.updateMatrixWorld(true);
      this.corda.userData.abre(hs.l, hs.r);
      ligaCabo(this.cab, [this.corda.localToWorld(V3(0, 0.07, 0))]);
    },
  },

  // Remada alta na polia baixa com barra reta
  om_remadaAltaPolia: {
    nome: "Remada alta na polia",
    deltoide: () => "deltoide lateral",
    musc: { deltoide: 1, trapezio: 0.85, biceps: 0.35 },
    dica: "De frente pra polia baixa, pegada um pouco mais fechada que os ombros. Puxa a barra rente ao corpo até o peito, cotovelo sempre acima do punho, e desce com o cabo tenso.",
    cam: { alvo: V3(0.05, 1.1, 0), dist: 3.9, yaw: 55, pitch: 8 },
    cena(g) {
      g.add(K.piso(2.8, 2.8));
      this.torre = K.torre({ alt: 0.2 }); this.torre.g.rotation.y = -Math.PI / 2; this.torre.g.position.set(1.1, 0, 0); g.add(this.torre.g);
      this.bar = K.barraReta(0.5); g.add(this.bar); this.cab = criaCabo(g, this.torre, 1); this.pose(1);
    },
    pose(t) {
      zera();
      emPe(V3(0, ALT_QUADRIL - 0.015, 0), F0, 0.03);
      for (const l of ["l", "r"]) gira("clavicle_" + l, EZ, (l === "l" ? 1 : -1) * ENC_SINAL * 0.12 * (1 - t));
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.13, fora: 0.2, poloFora: 0.2 });
      const E = esquerda(F0), om = ombroMeio(), reach = ALC();
      const solto = om.clone().add(V3(0, -reach * 0.95, 0)).add(F0.clone().multiplyScalar(0.11)), alto = om.clone().add(V3(0, -0.13, 0)).add(F0.clone().multiplyScalar(0.13));
      const kk = 1 - t, sk = kk * kk * (3 - 2 * kk), pos = solto.clone().lerp(alto, sk).add(F0.clone().multiplyScalar(0.06 * Math.sin(Math.PI * sk))), mo = {};
      ["l", "r"].forEach((l) => {
        const s = sLado(l);
        mo[l] = agarra(l, { ponto: pos.clone().add(E.clone().multiplyScalar(s * 0.12)), eixo: E.clone().multiplyScalar(-s), palma: F0.clone().multiplyScalar(-1), R: 0.0135,
          polo: E.clone().multiplyScalar(s).add(V3(0, 0.5, 0)).add(F0.clone().multiplyScalar(-0.15)) });
      });
      const mid = mo.l.clone().add(mo.r).multiplyScalar(0.5);
      const olho = alcaEm(this.bar, mid, mo.l.clone().sub(mo.r), this.torre.saida(), V3(0, 0.024, 0));
      ligaCabo(this.cab, [olho]);
    },
  },

  // Encolhimento no Smith: barra presa na frente das coxas, só os ombros sobem
  om_shrugSmith: {
    nome: "Encolhimento no Smith",
    deltoide: () => "trapézio",
    musc: { trapezio: 1, antebraco: 0.5 },
    dica: "Barra na frente das coxas, braços esticados e soltos. Sobe os ombros em direção às orelhas, segura um instante e desce até alongar, sem girar o ombro.",
    cam: { alvo: V3(0, 1.1, 0), dist: 3.8, yaw: 235, pitch: 10 },
    cena(g) { g.add(K.piso(2.8, 2.8)); this.sm = K.smith({ alt: 2.15, larg: 1.25 }); this.sm.g.rotation.y = Math.PI; this.sm.g.position.x = 0.1; g.add(this.sm.g); },
    pose(t) {
      zera();
      emPe(V3(-0.1, ALT_QUADRIL - 0.015, 0), F0, 0.02);
      const sobe = 1 - t;
      for (const l of ["l", "r"]) gira("clavicle_" + l, EZ, (l === "l" ? 1 : -1) * ENC_SINAL * 0.44 * sobe);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.13, fora: 0.2, poloFora: 0.2 });
      const om = ombroMeio(), bx = 0.1, lar = 0.24, d = ALC() * 0.965, dx = bx - om.x, y = om.y - Math.sqrt(d * d - dx * dx - (lar - 0.195) ** 2);
      this.sm.barra.position.y = y;
      for (const l of ["l", "r"]) { const lat = LAT(l);
        agarra(l, { ponto: V3(bx, y, 0).add(lat.clone().multiplyScalar(lar)), eixo: lat.clone().multiplyScalar(-1), R: 0.014, palma: F0.clone().multiplyScalar(-1), polo: F0.clone().multiplyScalar(-1).add(V3(0, 0.2, 0)) }); }
    },
  },

  // Rotação externa na polia: cotovelo colado na cintura a 90°, antebraço gira de dentro pra fora
  om_rotExt: {
    nome: "Rotação externa na polia",
    deltoide: () => "manguito rotador",
    musc: { deltoide: 0.4, trapezio: 0.3 },
    dica: "De lado pra polia na altura do cotovelo, cotovelo a 90° colado na cintura (toalha enrolada ajuda). Só o antebraço gira: parte de cruzado na barriga e abre pra fora, sem afastar o cotovelo.",
    cam: { alvo: V3(0.1, 1.15, 0.1), dist: 3.2, yaw: 40, pitch: 22 },
    cena(g) {
      g.add(K.piso(2.6, 2.6));
      this.torre = K.torre({ alt: 1.1 }); this.torre.g.position.set(0.3, 0, -1.1); g.add(this.torre.g);
      this.alca = K.estribo(); g.add(this.alca); this.cab = criaCabo(g, this.torre, 1); this.pose(1);
    },
    pose(t) {
      zera();
      emPe(V3(0, ALT_QUADRIL - 0.015, 0), F0, 0.02);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.12, fora: 0.2, poloFora: 0.2 });
      bracoSolto("l", 0.1, 0.05); maoNaCintura("l");
      const l = "r", lat = LAT(l), S = ondeEsta("upperarm_r"), th = lerp(0.45, -1.15, t);
      const cot = S.clone().add(V3(0, -COMP.upperarm_l, 0)).add(lat.clone().multiplyScalar(0.02)).add(F0.clone().multiplyScalar(0.02));
      const fd = F0.clone().multiplyScalar(Math.cos(th)).add(lat.clone().multiplyScalar(Math.sin(th))), perp = F0.clone().multiplyScalar(-Math.sin(th)).add(lat.clone().multiplyScalar(Math.cos(th)));
      const O = agarra(l, { punho: cot.clone().add(fd.multiplyScalar(COMP.lowerarm_l * 0.98)), eixo: V3(0, 1, 0), palma: perp.clone().multiplyScalar(-1), R: 0.016, polo: V3(0, -1, 0).add(lat.clone().multiplyScalar(0.3)) });
      const olho = alcaEm(this.alca, O, V3(0, 1, 0), this.torre.saida());
      ligaCabo(this.cab, [olho]);
    },
  },
  // Rosca de punho (flexores, palmas pra cima), inversa (extensores, palmas pra baixo) e atrás do corpo, todas com barra
  om_punho: {
    nome: "Rosca de punho com barra",
    deltoide: () => "antebraço",
    musc: { antebraco: 1 },
    dica: "Antebraços apoiados nas coxas, mãos pra fora do joelho, palmas pra cima. Deixa a barra rolar até a ponta dos dedos e fecha o punho subindo o máximo que der, sem tirar o antebraço do lugar.",
    cam: { alvo: V3(0.4, 0.7, 0), dist: 2.6, yaw: 50, pitch: 18 },
    cena(g) {
      g.add(K.piso(2.6, 2.6)); const p = this.p;
      if (!p.atras) { const bq = new THREE.Group(); bq.add(K.caixa(0.42, 0.09, 0.4, M.estofado, 0.035).translateY(0.42)); for (const z of [-0.15, 0.15]) bq.add(K.viga(V3(0, 0.37, z), V3(0, 0.0, z), 0.05)); bq.add(K.caixa(0.08, 0.04, 0.5, M.quadro, 0.01).translateY(0.02)); g.add(sombreia(bq)); }
      this.bar = barraCurta(0.1, 1.05); g.add(this.bar);
    },
    pose(t) {
      zera();
      const p = this.p, mo = {};
      let hand;
      if (p.atras) {
        emPe(V3(0, ALT_QUADRIL - 0.015, 0), F0, 0.0);
        B.pelvis.updateMatrixWorld(true); pernas(F0, { abre: 0.13, fora: 0.2, poloFora: 0.2 });
        const psi = lerp(0.85, -0.45, t);
        ["l", "r"].forEach((l) => {
          const lat = LAT(l), S = ondeEsta("upperarm_" + l), W = S.clone().add(V3(0, -1, 0).multiplyScalar(ALC() * 0.96)).add(F0.clone().multiplyScalar(-0.11)).add(lat.clone().multiplyScalar(0.04));
          const n = F0.clone().multiplyScalar(-Math.cos(psi)).add(V3(0, Math.sin(psi), 0));
          mo[l] = agarra(l, { punho: W, eixo: lat.clone().multiplyScalar(-1), palma: n, R: 0.0135, polo: V3(0, 0.1, 0).add(lat.clone().multiplyScalar(0.5)).add(F0.clone().multiplyScalar(-0.3)) });
        });
      } else {
        sentaCorpo(V3(0, 0.575, 0), -0.8, { dx: 0.42, abre: 0.17 }); gira("neck_01", EX, 0.5); gira("head", EX, 0.2);
        B.pelvis.updateMatrixWorld(true);
        const ext = !!p.inversa, psi = ext ? lerp(0.75, -0.95, t) : lerp(0.95, -0.7, t);
        ["l", "r"].forEach((l) => {
          const lat = LAT(l), z = lat.z, hip = ondeEsta("thigh_" + l), kn = ondeEsta("calf_" + l), fd = kn.clone().sub(hip).normalize();
          const W = kn.clone().add(fd.clone().multiplyScalar(0.07)).add(V3(0, 0.125, 0));
          const hd = fd.clone().multiplyScalar(Math.cos(psi)).add(V3(0, Math.sin(psi), 0)), nUp = fd.clone().multiplyScalar(-Math.sin(psi)).add(V3(0, Math.cos(psi), 0));
          mo[l] = agarra(l, { punho: W, eixo: lat.clone().multiplyScalar(ext ? -1 : 1), palma: nUp.multiplyScalar(ext ? -1 : 1), R: 0.0135, polo: V3(0, -1, 0).add(lat.clone().multiplyScalar(0.4)).add(F0.clone().multiplyScalar(-0.2)) });
        });
      }
      this.bar.position.copy(mo.l).add(mo.r).multiplyScalar(0.5); this.bar.quaternion.setFromUnitVectors(EX, mo.l.clone().sub(mo.r).normalize());
    },
  },

  // Rolo de punho: braços esticados na frente, o punho gira o bastão e enrola a corda que sobe a anilha
  om_rolo: {
    nome: "Rolo de punho",
    deltoide: () => "antebraço",
    musc: { antebraco: 1 },
    dica: "Em pé, braços esticados na frente na altura do ombro, mãos por cima do bastão. Gira o bastão só com os punhos, enrolando a corda até a anilha subir, e desenrola devagar.",
    cam: { alvo: V3(0.4, 1.1, 0), dist: 3.4, yaw: 58, pitch: 10 },
    cena(g) {
      g.add(tablado());
      this.rod = new THREE.Group(); const m = K.cilU(0.02, M.aco, 20); m.scale.y = 0.42; this.rodM = new THREE.Group(); this.rodM.add(m);
      for (const a of [0, 1.5708, 3.1416, 4.7124]) { const b = K.caixa(0.012, 0.28, 0.012, M.faixa, 0.002); b.position.set(Math.cos(a) * 0.022, 0, Math.sin(a) * 0.022); this.rodM.add(b); }
      this.rodM.rotation.x = Math.PI / 2; this.rodM.rotation.z = 0; this.rod.add(this.rodM); g.add(sombreia(this.rod));
      this.corda = K.cilU(0.004, new THREE.MeshStandardMaterial({ color: 0xd8c9a6, roughness: 0.9 }), 8); g.add(this.corda);
      this.anilha = anilha(0.11, 0.04); this.anilha.rotation.x = Math.PI / 2; this.anG = new THREE.Group(); this.anG.add(this.anilha); g.add(sombreia(this.anG));
    },
    fase(r) { const c = CICLO + 2; let u = r % c;
      if (u < 4.2) return { t: 1 - sen(u / 4.2), f: "enrola: o punho gira o bastão", esforco: 0.9 };
      u -= 4.2; if (u < 0.5) return { t: 0, f: "anilha no alto", esforco: 0.6 };
      u -= 0.5; if (u < 4.2) return { t: sen(u / 4.2), f: "desenrola devagar", esforco: 0.7 };
      return { t: 1, f: "pausa", esforco: 0.3 }; },
    pose(t) {
      zera();
      emPe(V3(0, ALT_QUADRIL - 0.015, 0), F0, 0.02);
      B.pelvis.updateMatrixWorld(true); pernas(F0, { abre: 0.13, fora: 0.2, poloFora: 0.2 });
      const u = 6 * (1 - t), f = u - Math.floor(u), fw = f < 0.72 ? suave(0, 0.72, f) : 1 - suave(0.72, 1, f), psi = lerp(-0.7, 0.7, fw), prog = Math.floor(u) + suave(0, 0.72, f);
      const mo = {};
      ["l", "r"].forEach((l) => {
        const lat = LAT(l), S = ondeEsta("upperarm_" + l), W = S.clone().add(F0.clone().multiplyScalar(ALC() * 0.95)).add(V3(0, -0.02, 0)).add(lat.clone().multiplyScalar(-0.03));
        const n = V3(0, -Math.cos(psi), 0).add(F0.clone().multiplyScalar(Math.sin(psi)));
        mo[l] = agarra(l, { punho: W, eixo: lat.clone().multiplyScalar(-1), palma: n, R: 0.02, polo: V3(0, -1, 0).add(lat.clone().multiplyScalar(0.3)) });
      });
      const mid = mo.l.clone().add(mo.r).multiplyScalar(0.5);
      this.rod.position.copy(mid); this.rod.quaternion.setFromUnitVectors(EX, V3(0, 0, 1)); this.rod.rotation.set(0, 0, 0);
      this.rodM.rotation.set(Math.PI / 2, 0, 0); this.rodM.children[0].rotation.y = 0; this.rodM.rotation.y = prog * 1.4;
      const L = 0.1 + 0.8 * t, top = mid.clone().add(V3(0, -0.02, 0)), fim = top.clone().add(V3(0, -L, 0));
      K.poe(this.corda, top, fim); this.anG.position.copy(fim).add(V3(0, -0.11, 0));
    },
  },

  // Pegada estática (farmer hold): segura dois halteres pesados em pé, isometria
  om_farmer: {
    nome: "Pegada estática (farmer hold)",
    deltoide: () => "antebraço",
    musc: { antebraco: 1, trapezio: 0.6 },
    dica: "Em pé, ombros pra trás e pra baixo, halteres pesados ao lado do corpo. Aperta a pegada com tudo e segura o tempo todo sem deixar os halteres balançarem nem os ombros subirem.",
    cam: { alvo: V3(0, 0.95, 0), dist: 3.6, yaw: 62, pitch: 8 },
    cena(g) { g.add(tablado()); this.h = [halter(3), halter(3)]; g.add(...this.h); },
    fase(r) { return { t: 0.5 + 0.02 * Math.sin(r * 1.3), f: "segura 30 s, aperta forte", esforco: 0.85 + 0.05 * Math.sin(r * 0.7) }; },
    pose(t) {
      zera();
      emPe(V3(0, ALT_QUADRIL - 0.015, 0), F0, 0.0);
      for (const l of ["l", "r"]) gira("clavicle_" + l, EZ, (l === "l" ? 1 : -1) * ENC_SINAL * -0.06);
      B.pelvis.updateMatrixWorld(true); pernas(F0, { abre: 0.14, fora: 0.2, poloFora: 0.2 });
      const E = esquerda(F0);
      ["l", "r"].forEach((l, i) => {
        const s = sLado(l), S = ondeEsta("upperarm_" + l), dir = V3(0, -1, 0).add(E.clone().multiplyScalar(s * 0.07)).normalize();
        agarra(l, { punho: S.clone().add(dir.multiplyScalar(ALC() * 0.965)), R: 0.016, eixo: F0.clone(), palma: E.clone().multiplyScalar(-s), polo: F0.clone().multiplyScalar(-1).add(V3(0, 0.2, 0)) });
        seguraHalter(this.h[i], l);
      });
    },
  },

  // Pronação e supinação com halter: antebraço apoiado na coxa, halter seguro por uma ponta, gira a palma de cima pra baixo
  om_pronSup: {
    nome: "Pronação e supinação com halter",
    deltoide: () => "antebraço",
    musc: { antebraco: 1 },
    dica: "Antebraço apoiado na coxa, punho pra fora do joelho, halter seguro numa ponta com o peso pra cima. Gira o antebraço até a palma olhar pra cima, depois pra baixo, só o antebraço se mexe.",
    cam: { alvo: V3(0.4, 0.75, 0.1), dist: 2.4, yaw: 50, pitch: 20 },
    cena(g) {
      g.add(K.piso(2.6, 2.6)); const bq = new THREE.Group(); bq.add(K.caixa(0.42, 0.09, 0.4, M.estofado, 0.035).translateY(0.42)); for (const z of [-0.15, 0.15]) bq.add(K.viga(V3(0, 0.37, z), V3(0, 0.0, z), 0.05)); bq.add(K.caixa(0.08, 0.04, 0.5, M.quadro, 0.01).translateY(0.02)); g.add(sombreia(bq));
      this.h = halter(0.4); g.add(this.h);
    },
    fase(r) { const c = 4.0, u = (r % c) / c; return { t: 0.5 - 0.5 * Math.cos(2 * Math.PI * u), f: u < 0.5 ? "gira a palma pra baixo" : "gira a palma pra cima", esforco: 0.7 }; },
    pose(t) {
      zera();
      sentaCorpo(V3(0, 0.575, 0), -0.8, { dx: 0.42, abre: 0.17 }); gira("neck_01", EX, 0.5); gira("head", EX, 0.2);
      B.pelvis.updateMatrixWorld(true);
      const th = lerp(-1.35, 1.35, 1 - t); // + = pronação
      {
        const l = "l", hip = ondeEsta("thigh_l"), kn = ondeEsta("calf_l");
        braco(l, kn.clone().add(V3(0.0, 0.14, 0)), V3(0, -1, 0).add(F0.clone().multiplyScalar(-0.2)));
        mao(l, F0.clone(), V3(0, -1, 0)); fecha(l, 0.25);
      }
      const l = "r", lat = LAT(l), s = sLado(l), hip = ondeEsta("thigh_r"), kn = ondeEsta("calf_r"), fd = kn.clone().sub(hip).normalize();
      const W = kn.clone().add(fd.clone().multiplyScalar(0.07)).add(V3(0, 0.125, 0));
      const k = V3(0, 1, 0).applyAxisAngle(fd, s * th), n = lat.clone().multiplyScalar(-1).applyAxisAngle(fd, s * th);
      agarra(l, { punho: W, eixo: k, palma: n, R: 0.016, polo: V3(0, -1, 0).add(lat.clone().multiplyScalar(0.4)).add(F0.clone().multiplyScalar(-0.2)) });
      seguraHalter(this.h, l); this.h.translateX(0.07);
    },
  },
  /*@@MOLDES@@*/
});

// EMG (conferido só no resumo/abstract de cada artigo; o resto é estimativa, marcada):
// - Campos 2020 (J Hum Kinet 75:5): desenvolvimento = deltoide anterior 33% e médio 28% da CIVM; elevação lateral = médio 30%, posterior 24% (daí lateral 1 / posterior 0.8).
// - Saeterbakken & Fimland 2013 (JSCR 27:1824): halter dá mais deltoide anterior que barra; sentado tem bem menos deltoide posterior que em pé (-25%); sentado halter tira ~15% do médio.
// - Ehlers Botton 2013 (Medicina Sportiva): desenvolvimento no Smith ~70% do anterior, peck deck inverso ativa o posterior forte (valores dos resumos secundários).
// - Reinold 2004 (JOSPT 34:385): rotação externa deitada de lado = infraespinal 62% e redondo menor 67%; horizontal prona com rotação = posterior 88%, médio 87%.
// - Andersen 2014 (scapular muscles): face pull NÃO estava no artigo; face pull, Y-raise, rolo, farmer, pronação e rosca de punho = estimativa por função do músculo.
Object.assign(FOCOS, {
  om_pressSent: (p) => [["deltoide_ant", 1], ["deltoide_lat", 0.85], ["triceps_lateral", 0.65], ["trapezio_sup", 0.55], ["serratil", 0.45], ["triceps_longa", 0.4], ["deltoide_post", 0.3]],
  om_pressSmith: () => [["deltoide_ant", 1], ["deltoide_lat", 0.8], ["triceps_lateral", 0.7], ["trapezio_sup", 0.6]],
  om_pressMaq: () => [["deltoide_ant", 1], ["deltoide_lat", 0.8], ["triceps_lateral", 0.7], ["trapezio_sup", 0.6]],
  om_pushPress: () => [["deltoide_ant", 1], ["deltoide_lat", 0.8], ["triceps_lateral", 0.7], ["vasto_lateral", 0.5], ["trapezio_sup", 0.6]],
  om_lateralPolia: () => [["deltoide_lat", 1], ["deltoide_post", 0.8], ["trapezio_sup", 0.55], ["deltoide_ant", 0.5], ["serratil", 0.4]],
  om_lateralInclinada: () => [["deltoide_lat", 1], ["deltoide_post", 0.8], ["trapezio_sup", 0.55], ["deltoide_ant", 0.5], ["serratil", 0.4]],
  om_lateralMaq: () => [["deltoide_lat", 1], ["deltoide_post", 0.75], ["trapezio_sup", 0.5], ["deltoide_ant", 0.5], ["serratil", 0.35]],
  om_frontalAnilha: () => [["deltoide_ant", 1], ["peitoral_sup", 0.6], ["deltoide_lat", 0.5], ["serratil", 0.45], ["trapezio_sup", 0.45]],
  om_frontalPolia: () => [["deltoide_ant", 1], ["peitoral_sup", 0.6], ["deltoide_lat", 0.5], ["serratil", 0.45], ["trapezio_sup", 0.45]],
  om_invHalter: () => [["deltoide_post", 1], ["trapezio_med", 0.8], ["infraespinal", 0.65], ["deltoide_lat", 0.6], ["trapezio_sup", 0.35]],
  om_invMaq: () => [["deltoide_post", 1], ["trapezio_med", 0.7], ["infraespinal", 0.65], ["deltoide_lat", 0.55], ["trapezio_sup", 0.3]],
  om_invPolia: () => [["deltoide_post", 1], ["trapezio_med", 0.7], ["infraespinal", 0.65], ["deltoide_lat", 0.55], ["trapezio_sup", 0.3]],
  om_yRaise: () => [["trapezio_med", 1], ["deltoide_post", 0.8], ["infraespinal", 0.6], ["trapezio_sup", 0.5], ["deltoide_lat", 0.5]],
  om_facePull: () => [["deltoide_post", 1], ["trapezio_med", 0.85], ["infraespinal", 0.8], ["trapezio_sup", 0.5], ["deltoide_lat", 0.5], ["biceps", 0.3]],
  om_remadaAltaPolia: () => [["deltoide_lat", 1], ["trapezio_sup", 0.9], ["deltoide_ant", 0.7], ["braquiorradial", 0.5], ["trapezio_med", 0.45], ["biceps", 0.4]],
  om_shrugSmith: () => [["trapezio_sup", 1], ["antebraco", 0.6], ["trapezio_med", 0.4]],
  om_rotExt: () => [["infraespinal", 1], ["deltoide_post", 0.55], ["trapezio_med", 0.3]],
  om_punho: (p) => p.inversa ? [["antebraco_ext", 1], ["braquiorradial", 0.4]] : p.atras ? [["antebraco", 1], ["braquiorradial", 0.3], ["antebraco_ext", 0.25]] : [["antebraco", 1], ["braquiorradial", 0.3], ["antebraco_ext", 0.2]],
  om_rolo: () => [["antebraco_ext", 1], ["antebraco", 0.9], ["braquiorradial", 0.5], ["deltoide_ant", 0.4]],
  om_farmer: () => [["antebraco", 1], ["antebraco_ext", 0.6], ["trapezio_sup", 0.6], ["braquiorradial", 0.4]],
  om_pronSup: () => [["antebraco", 0.9], ["braquiorradial", 0.7], ["antebraco_ext", 0.8], ["biceps", 0.5]],
  /*@@FOCOS@@*/
});
Object.assign(VISTA, {});
}

// ===== moldes/peito.js =====
{ // moldes/peito.js
// ===== helpers do grupo (tudo dentro deste bloco; ids com prefixo pe_) =====
const PE = {};
PE.tubo = (a, b, r, mat = M.cromo) => K.tubo(a, b, r, mat);
// rolo comprido (eixo Z) entre z=-w/2..w/2 no ponto (x, y)
PE.rolo = (x, y, w = 0.6, r = 0.045) => { const m = K.cilU(r, M.estofado, 24); m.scale.y = w; m.rotation.x = Math.PI / 2; m.position.set(x, y, 0); return m; };
// quadro de referência do corpo deitado no banco com ângulo a (rad): a>0 inclinado (cabeça alta), a<0 declinado (cabeça baixa)
PE.quadroDeitado = (a) => { const cab = V3(-Math.cos(a), Math.sin(a), 0), fr = V3(Math.sin(a), Math.cos(a), 0); return { cab, fr, pes: cab.clone().negate() }; };
// tronco + cabeça do corpo deitado (igual ao supino do motor)
PE.tronco = (P0, a, t, escap) => {
  const { cab, fr } = PE.quadroDeitado(a);
  corpoEm(P0, cab, fr);
  gira("spine_02", EX, -0.07); gira("spine_03", EX, -0.06); gira("neck_01", EX, 0.12 - a * 0.2 + (a > 0.6 ? (a - 0.6) * 1.2 : 0)); gira("head", EX, 0.04);
  for (const l of ["l", "r"]) gira("clavicle_" + l, EZ, (l === "l" ? -1 : 1) * escap);
  B.pelvis.updateMatrixWorld(true);
};

// ----- banco declinado com prendedor de pés (rolos), pad longo. P0 = pelve; a<0. Devolve { g, tornozelo(l) } -----
PE.bancoDecl = (P0, a, { rack = true } = {}) => {
  const g = new THREE.Group(), { cab, fr } = PE.quadroDeitado(a);
  const sup = (s, h = 0) => P0.clone().add(fr.clone().multiplyScalar(-0.165 - 0.0425 - h)).add(cab.clone().multiplyScalar(s)); // ponto na face de baixo do pad
  const pad = K.caixa(1.3, 0.085, 0.29, M.estofado, 0.03);
  pad.position.copy(P0.clone().add(fr.clone().multiplyScalar(-0.165)).add(cab.clone().multiplyScalar(0.33))); pad.rotation.z = -a; g.add(pad);
  // espinha de aço sob o pad + dois pés em H
  const q1 = sup(-0.2), q2 = sup(0.88);
  g.add(K.viga(sup(-0.28, 0.0), sup(0.9, 0.0), 0.05, M.quadro, 0.1));
  for (const q of [q1, q2]) {
    g.add(K.viga(V3(q.x, q.y - 0.02, 0), V3(q.x, 0.05, 0), 0.06));
    g.add(K.caixa(0.08, 0.05, 0.52, M.quadro, 0.015).translateX(q.x).translateY(0.025));
  }
  // prendedor de pés: dois rolos compridos (um por cima do pé, outro atrás da panturrilha) em dois montantes laterais
  const Ax = P0.x + 0.78, Ay = P0.y - 0.05;
  const sob = PE.rolo(Ax + 0.06, Ay + 0.09), atras = PE.rolo(Ax - 0.04, Ay - 0.075);
  g.add(sob, atras);
  for (const z of [-0.33, 0.33]) {
    g.add(K.viga(V3(Ax + 0.02, 0.05, z), V3(Ax + 0.02, Ay + 0.16, z), 0.055));
    g.add(K.caixa(0.5, 0.05, 0.06, M.quadro, 0.012).translateX(Ax - 0.15).translateY(0.025).translateZ(z));
    g.add(PE.tubo(V3(Ax + 0.06, Ay + 0.09, z * 0.92), V3(Ax + 0.02, Ay + 0.12, z), 0.012));
    g.add(PE.tubo(V3(Ax - 0.04, Ay - 0.075, z * 0.92), V3(Ax + 0.02, Ay - 0.075, z), 0.012));
  }
  g.add(K.viga(V3(Ax - 0.35, 0.05, 0.33), V3(Ax - 0.35, 0.05, -0.33), 0.045, M.quadro, 0.04));
  return { g: sombreia(g), alvoTornozelo: (s) => V3(Ax, Ay, s * 0.115) };
};

// ===== supino declinado (barra / halteres) =====
const A_DEC = -0.31, P_DEC = V3(0.16, 0.72, 0);
Object.assign(MOLDES, {
  pe_supino_decl: {
    nome: "Supino declinado com barra",
    musc: { peitoral: 1, triceps: 0.7, deltoide: 0.5 },
    dica: "Pés presos nos rolos, escápulas encaixadas. A barra desce até a parte baixa do peito, cotovelo a uns 45° do tronco, e sobe empurrando pra cima dos ombros.",
    cam: { alvo: V3(0.05, 0.85, 0), dist: 4.6, yaw: 52, pitch: 24 },
    cena(g) {
      const b = PE.bancoDecl(P_DEC, A_DEC); this.banco = b; g.add(b.g);
      if (!this.p.halter) g.add(suportes(-0.62, 1.32));
      if (this.p.halter) { this.h = [halter(0.8), halter(0.8)]; g.add(...this.h); this.bar = null; }
      else { this.bar = barra(1); g.add(this.bar); }
    },
    pose(t) {
      zera();
      const p = this.p, a = A_DEC, { cab, fr, pes } = PE.quadroDeitado(a);
      PE.tronco(P_DEC, a, t, 0.04 * t);
      for (const l of ["l", "r"]) { // pés presos: joelho dobrado, tornozelo entre os rolos
        const s = l === "l" ? -1 : 1, A = this.banco.alvoTornozelo(s);
        perna(l, A, V3(0.1, 1, s * 0.35));
        mira("foot_" + l, V3(0.9, 0.35, s * 0.05).normalize(), V3(0, 0, -1), EX);
      }
      const ombro = ondeEsta("upperarm_l").add(ondeEsta("upperarm_r")).multiplyScalar(0.5);
      const alcance = COMP.upperarm_l + COMP.lowerarm_l;
      const topo = ombro.clone().add(V3(0, alcance * 0.97 + 0.035, 0)).add(pes.clone().multiplyScalar(0.035));
      const baixo = ombro.clone().add(fr.clone().multiplyScalar(p.halter ? 0.14 : 0.085)).add(pes.clone().multiplyScalar(0.19 + (p.halter ? 0.02 : 0)));
      const d = baixo.clone().sub(topo), curva = Math.sin(t * Math.PI / 2);
      const pos = topo.clone().add(V3(0, d.y * t, 0)).add(V3(d.x, 0, d.z).multiplyScalar(curva));
      if (this.bar) { this.bar.position.copy(pos); this.bar.rotation.y = Math.PI / 2; }
      ["l", "r"].forEach((l, i) => {
        const s = l === "l" ? -1 : 1;
        const larg = p.halter ? lerp(0.17, 0.3, t) : 0.41;
        agarra(l, { ponto: pos.clone().add(V3(0, 0, s * larg)), R: this.h ? 0.016 : 0.014,
          eixo: V3(0, 0, -s), palma: pes.clone().multiplyScalar(0.8).add(fr.clone().multiplyScalar(0.55)),
          polo: pes.clone().multiplyScalar(0.55).add(fr.clone().multiplyScalar(-0.55)).add(V3(0, 0, s * 0.75)) });
        if (this.h) seguraHalter(this.h[i], l);
      });
    },
  },
});

// ===== banco inclinado (copiado do supino do motor: assento + encosto alinhado com as costas) =====
PE.bancoInc = (a) => {
  const ban = new THREE.Group(), { cab, fr } = PE.quadroDeitado(a);
  const assento = new THREE.Mesh(new RoundedBoxGeometry(0.42, 0.085, 0.29, 4, 0.03), M.estofado); assento.position.set(0.2, 0.4, 0); ban.add(assento);
  const centro = V3(0.16, 0.565, 0).add(fr.clone().multiplyScalar(-0.165)).add(cab.clone().multiplyScalar(0.36));
  const encosto = new THREE.Mesh(new RoundedBoxGeometry(0.88, 0.085, 0.29, 4, 0.03), M.estofado); encosto.position.copy(centro); encosto.rotation.z = -a; ban.add(encosto);
  const trilho = K.viga(V3(0.2, 0.34, 0), centro.clone().add(fr.clone().multiplyScalar(-0.07)).add(cab.clone().multiplyScalar(0.25)), 0.06);
  ban.add(trilho);
  for (const x of [0.32, -0.4]) {
    const pe2 = K.caixa(0.08, 0.05, 0.46, M.quadro, 0.015); pe2.position.set(x, 0.025, 0); ban.add(pe2);
    const perna2 = K.caixa(0.06, x > 0 ? 0.34 : 0.62, 0.06, M.quadro, 0.01); perna2.position.set(x, x > 0 ? 0.17 : 0.31, 0); ban.add(perna2);
  }
  return sombreia(ban);
};

// ===== supino no Smith (reto / inclinado) =====
Object.assign(MOLDES, {
  pe_smith: {
    nome: "Supino reto no Smith",
    musc: { peitoral: 1, triceps: 0.7, deltoide: 0.6 },
    dica: "A barra anda em trilho: pés um pouco à frente do banco pra fechar as escápulas. Destrava, desce até o peito e empurra reto pra cima; o trilho te dá liberdade pra focar só no peito.",
    cam: { alvo: V3(0.0, 0.9, 0), dist: 5.6, yaw: 50, pitch: 22 },
    cena(g) {
      const a = (this.p.inclina || 0) * Math.PI / 180;
      g.add(a ? PE.bancoInc(a) : banco());
      this.sm = K.smith({ alt: 2.15, larg: 1.25 }); g.add(this.sm.g);
    },
    pose(t) {
      zera();
      const p = this.p, a = (p.inclina || 0) * Math.PI / 180, { fr, pes } = PE.quadroDeitado(a);
      PE.tronco(V3(0.16, 0.565, 0), a, t, 0.03);
      for (const l of ["l", "r"]) { const s = l === "l" ? -1 : 1; perna(l, V3(0.6 - a * 0.25, ALT_TORN, s * 0.31), V3(0.3, 1, s * 0.22)); pe(l, V3(1, 0, s * 0.25)); }
      const ombro = ondeEsta("upperarm_l").add(ondeEsta("upperarm_r")).multiplyScalar(0.5), alcance = COMP.upperarm_l + COMP.lowerarm_l;
      const topo = ombro.clone().add(V3(0, alcance * 0.97 + 0.035, 0)).add(pes.clone().multiplyScalar(0.035));
      const baixo = ombro.clone().add(fr.clone().multiplyScalar(0.085)).add(pes.clone().multiplyScalar(a ? 0.11 : 0.165));
      const xs = (topo.x + baixo.x) / 2; // a barra anda reta: x fixo no meio do caminho
      const y = lerp(topo.y, baixo.y, t);
      this.sm.g.position.x = xs; this.sm.barra.position.y = y;
      ["l", "r"].forEach((l) => {
        const s = l === "l" ? -1 : 1;
        agarra(l, { ponto: V3(xs, y, s * 0.4), R: 0.014, eixo: V3(0, 0, -s), palma: pes.clone().multiplyScalar(0.8).add(fr.clone().multiplyScalar(0.55)),
          polo: pes.clone().multiplyScalar(0.55).add(fr.clone().multiplyScalar(-0.55)).add(V3(0, 0, s * 0.75)) });
      });
    },
  },
});

// ===== máquina de supino sentado (reto / inclinado): alavanca com pivô embaixo, empurra perpendicular à alavanca =====
const P_SENT = V3(0, 0.52, 0);
PE.maquinaSentada = (aEq, P0 = P_SENT) => {
  const g = new THREE.Group(), { cab, fr } = PE.quadroDeitado(aEq);
  const noPad = (s, h = 0) => P0.clone().add(fr.clone().multiplyScalar(-0.165 - 0.0425 - h)).add(cab.clone().multiplyScalar(s));
  const pad = K.caixa(0.95, 0.085, 0.4, M.estofado, 0.035);
  pad.position.copy(P0.clone().add(fr.clone().multiplyScalar(-0.165)).add(cab.clone().multiplyScalar(0.43))); pad.rotation.z = -aEq; g.add(pad);
  const assento = K.caixa(0.5, 0.09, 0.44, M.estofado, 0.035); assento.position.set(P0.x + 0.1, P0.y - 0.155, 0); g.add(assento);
  // coluna atrás do encosto, travessa do assento, base em duas longarinas
  const xc = noPad(0.2, 0.09).x - 0.1;
  g.add(K.caixa(0.14, 1.95, 0.5, M.quadro, 0.02).translateX(xc).translateY(0.975));
  g.add(K.viga(V3(xc + 0.07, 0.62, 0), noPad(0.22, 0.02), 0.05, M.quadro, 0.12));
  g.add(K.viga(V3(xc + 0.07, P0.y - 0.2, 0), V3(P0.x + 0.12, P0.y - 0.2, 0), 0.05, M.quadro, 0.12));
  for (const z of [-0.43, 0.43]) g.add(K.caixa(1.55, 0.05, 0.07, M.quadro, 0.012).translateX(xc + 0.7).translateY(0.025).translateZ(z));
  g.add(K.caixa(0.07, 0.05, 0.93, M.quadro, 0.012).translateX(xc + 0.04).translateY(0.025));
  // pilha de pesos atrás da coluna
  const pil = K.pilha(); pil.rotation.y = Math.PI / 2; pil.position.set(xc - 0.2, 0.04, 0); g.add(pil);
  g.add(K.caixa(0.06, 1.35, 0.34, M.quadro, 0.01).translateX(xc - 0.4).translateY(0.7));
  g.add(K.viga(V3(xc - 0.35, 0.04, 0), V3(xc, 0.04, 0), 0.07, M.quadro, 0.4));
  return sombreia(g);
};
Object.assign(MOLDES, {
  pe_maq_supino: {
    nome: "Supino máquina sentado",
    musc: { peitoral: 1, triceps: 0.7, deltoide: 0.6 },
    dica: "Regula o banco pra o cabo ficar na altura do peito, costas coladas no encosto. Empurra as duas pegas juntas sem tirar as escápulas do estofado e volta devagar até sentir o peito esticar.",
    cam: { alvo: V3(0.15, 0.95, 0), dist: 4.4, yaw: 50, pitch: 16 },
    cena(g) {
      this.aEq = (this.p.inclina ? 52 : 80) * Math.PI / 180;
      g.add(PE.maquinaSentada(this.aEq));
      this.cab = [0, 1].map(() => { const al = K.tubo(V3(), V3(0, 1, 0), 0.02, M.quadro), gr = K.cilU(0.016, M.borracha, 14); gr.scale.y = 0.15; gr.rotation.x = Math.PI / 2; g.add(al, gr); return { al, gr }; });
      this.piv = null; this.casa = [0, 1].map(() => { const c = K.caixa(0.15, 0.15, 0.12, M.quadro, 0.02); g.add(c); return c; });
    },
    pose(t) {
      zera();
      const p = this.p, a = this.aEq, { cab, fr, pes } = PE.quadroDeitado(a);
      PE.tronco(P_SENT, a, t, 0.04 * t - 0.02 * (1 - t));
      for (const l of ["l", "r"]) { const s = l === "l" ? -1 : 1; perna(l, V3(P_SENT.x + 0.52, ALT_TORN, s * 0.17), V3(1, 0.4, s * 0.15)); pe(l, V3(1, 0, s * 0.12)); }
      const ombro = ondeEsta("upperarm_l").add(ondeEsta("upperarm_r")).multiplyScalar(0.5), alcance = COMP.upperarm_l + COMP.lowerarm_l;
      const topo = ombro.clone().add(fr.clone().multiplyScalar(alcance * 0.96 + 0.03)).add(pes.clone().multiplyScalar(0.05));
      const baixo = ombro.clone().add(fr.clone().multiplyScalar(0.07)).add(pes.clone().multiplyScalar(0.15));
      const mid = topo.clone().lerp(baixo, 0.5), u = V3(-fr.y, fr.x, 0);
      if (!this.piv) this.piv = mid.clone().sub(u.clone().multiplyScalar(0.62));
      const pos = topo.clone().lerp(baixo, t);
      ["l", "r"].forEach((l, i) => {
        const s = l === "l" ? -1 : 1, larg = lerp(0.22, 0.27, t);
        const O = agarra(l, { ponto: pos.clone().add(V3(0, 0, s * larg)), R: 0.016, eixo: V3(0, 0, -s), palma: pes.clone().multiplyScalar(0.8).add(fr.clone().multiplyScalar(0.55)),
          polo: pes.clone().multiplyScalar(0.55).add(fr.clone().multiplyScalar(-0.55)).add(V3(0, 0, s * 0.75)) });
        const c = this.cab[i], pv = this.piv.clone().setZ(s * 0.44), fim = O.clone().add(V3(0, 0, s * 0.085));
        K.poe(c.gr, O.clone().add(V3(0, 0, s * 0.01)), fim.clone().add(V3(0, 0, s * 0.01))); c.gr.scale.x = c.gr.scale.z = 1;
        K.poe(c.al, fim, pv); this.casa[i].position.copy(pv);
      });
    },
  },
});

// ===== crucifixo declinado com halteres =====
Object.assign(MOLDES, {
  pe_crucifixo_decl: {
    nome: "Crucifixo declinado",
    musc: { peitoral: 1, deltoide: 0.5, biceps: 0.35 },
    dica: "Pés presos, cotovelo levemente dobrado e travado. Abre em arco até o peito alongar e fecha como num abraço, apontando os halteres pro meio do peito. O declive pega mais a parte de baixo.",
    cam: { alvo: V3(0.0, 0.85, 0), dist: 4.2, yaw: 58, pitch: 28 },
    cena(g) {
      const b = PE.bancoDecl(P_DEC, A_DEC); this.banco = b; g.add(b.g);
      this.h = [halter(0.8), halter(0.8)]; g.add(...this.h);
    },
    pose(t) {
      zera();
      const a = A_DEC, { cab, fr, pes } = PE.quadroDeitado(a);
      PE.tronco(P_DEC, a, t, 0.05 * t - 0.03 * (1 - t));
      for (const l of ["l", "r"]) {
        const s = l === "l" ? -1 : 1;
        perna(l, this.banco.alvoTornozelo(s), V3(0.1, 1, s * 0.35));
        mira("foot_" + l, V3(0.9, 0.35, s * 0.05).normalize(), V3(0, 0, -1), EX);
      }
      const R = (COMP.upperarm_l + COMP.lowerarm_l) * 0.9, fi = -0.16 + 1.5 * t;
      ["l", "r"].forEach((l, i) => {
        const s = l === "l" ? -1 : 1, O = ondeEsta("upperarm_" + l), lado = V3(0, 0, s);
        const dir = fr.clone().multiplyScalar(Math.cos(fi)).add(lado.clone().multiplyScalar(Math.sin(fi))).add(pes.clone().multiplyScalar(0.12)).normalize();
        const palma = lado.clone().multiplyScalar(-Math.cos(fi * 0.85)).add(fr.clone().multiplyScalar(Math.sin(fi * 0.85)));
        agarra(l, { punho: O.clone().add(dir.multiplyScalar(R)), R: 0.016, eixo: cab.clone(), palma,
          polo: lado.clone().add(fr.clone().multiplyScalar(-0.35)).add(pes.clone().multiplyScalar(0.25)) });
        seguraHalter(this.h[i], l);
      });
    },
  },
});

// ===== voador / peck deck: alavancas giram em torno de eixo vertical acima do ombro, pegas verticais =====
Object.assign(MOLDES, {
  pe_voador: {
    nome: "Voador (peck deck)",
    musc: { peitoral: 1, deltoide: 0.55 },
    dica: "Costas coladas no encosto, cotovelo levemente dobrado e travado. Abre até sentir o peito esticar, sem passar da linha do ombro, e fecha juntando as pegas na frente do peito, apertando um segundo.",
    cam: { alvo: V3(0.15, 1.0, 0), dist: 4.3, yaw: 62, pitch: 20 },
    cena(g) {
      this.aEq = 84 * Math.PI / 180;
      g.add(PE.maquinaSentada(this.aEq));
      this.pc = [0, 1].map(() => { const c = K.caixa(0.13, 0.13, 0.13, M.quadro, 0.02), al = K.tubo(V3(), V3(0, 1, 0), 0.022, M.quadro), ha = K.tubo(V3(), V3(0, 1, 0), 0.012, M.cromo), gr = K.cilU(0.016, M.borracha, 14); gr.scale.y = 0.15; g.add(c, al, ha, gr); return { c, al, ha, gr }; });
      this.ponte = [0, 1].map(() => { const v = K.viga(V3(0, 0, 0), V3(0, 1, 0), 0.07); g.add(v); return v; }); this.piv = null;
    },
    pose(t) {
      zera();
      const a = this.aEq, { cab, fr, pes } = PE.quadroDeitado(a);
      PE.tronco(P_SENT, a, t, 0.02);
      for (const l of ["l", "r"]) { const s = l === "l" ? -1 : 1; perna(l, V3(P_SENT.x + 0.52, ALT_TORN, s * 0.17), V3(1, 0.4, s * 0.15)); pe(l, V3(1, 0, s * 0.12)); }
      const r = (COMP.upperarm_l + COMP.lowerarm_l) * 0.95, fi = -0.3 + 1.65 * t;
      ["l", "r"].forEach((l, i) => {
        const s = l === "l" ? -1 : 1, Ob = ondeEsta("upperarm_" + l);
        if (!this.piv) this.piv = [Ob.clone(), Ob.clone()];
        const H = Ob.clone().add(V3(Math.cos(fi), -0.04, s * Math.sin(fi)).multiplyScalar(r)); H.y = Ob.y - 0.04 - 0 * fi;
        const p1 = V3(-Math.sin(fi), 0, s * Math.cos(fi)), polo = p1.clone().add(V3(0, -0.3, 0)), pal = p1.clone().negate();
        const O = agarra(l, { ponto: H, R: 0.016, eixo: V3(0, 1, 0), palma: pal, polo });
        const c = this.pc[i], ys = this.piv[i].y + 0.42, S = V3(this.piv[i].x, ys, this.piv[i].z), top = V3(O.x, ys, O.z);
        c.c.position.copy(S); K.poe(c.al, S, top);
        K.poe(c.ha, top, O.clone().add(V3(0, 0.075, 0))); K.poe(c.gr, O.clone().add(V3(0, -0.075, 0)), O.clone().add(V3(0, 0.075, 0)));
        const ponte = this.ponte[i], xc = S.x - 0.55, a0 = V3(xc, ys + 0.1, S.z), b0 = V3(S.x, ys + 0.1, S.z); K.poe(ponte, a0, b0); ponte.scale.x = ponte.scale.z = 1;
      });
    },
  },
});

// ===== pullover com halter: deitado no banco, halter vertical com as mãos apoiadas por baixo do disco de cima =====
PE.halterPull = () => { // eixo X local; discos hexagonais grandes nas pontas
  const g = new THREE.Group(), pega = cil(0.018, 0.16, M.aco); pega.rotation.z = Math.PI / 2; g.add(pega);
  for (const s of [-1, 1]) {
    const d = cil(0.088, 0.055, M.borracha, 6); d.rotation.z = Math.PI / 2; d.position.x = s * 0.1075; g.add(d);
    const cap = cil(0.03, 0.01, M.aco, 20); cap.rotation.z = Math.PI / 2; cap.position.x = s * 0.14; g.add(cap);
  }
  return sombreia(g);
};
Object.assign(MOLDES, {
  pe_pullover: {
    nome: "Pullover com halter",
    musc: { peitoral: 1, dorsal: 0.9, triceps: 0.6 },
    dica: "Deitado no banco, halter na vertical segurado por baixo do disco de cima, cotovelo levemente dobrado e fixo. Leva o peso em arco pra trás da cabeça até alongar o peito e as costas, e traz de volta sem dobrar mais o cotovelo.",
    cam: { alvo: V3(-0.3, 0.8, 0), dist: 4.0, yaw: 52, pitch: 24 },
    cena(g) { g.add(banco()); this.h = PE.halterPull(); g.add(this.h); },
    pose(t) {
      zera();
      PE.tronco(V3(0.16, 0.565, 0), 0, t, 0.0);
      for (const l of ["l", "r"]) { const s = l === "l" ? -1 : 1; perna(l, V3(0.6, ALT_TORN, s * 0.31), V3(0.3, 1, s * 0.22)); pe(l, V3(1, 0, s * 0.25)); }
      const ombro = ondeEsta("upperarm_l").add(ondeEsta("upperarm_r")).multiplyScalar(0.5);
      const th = 0.02 + 1.38 * t, d = V3(-Math.sin(th), Math.cos(th), 0), Lr = 0.5;
      const ctop = ombro.clone().add(d.clone().multiplyScalar(Lr));
      this.h.position.copy(ctop).add(d.clone().multiplyScalar(-0.0775 + 0.0)); this.h.quaternion.setFromUnitVectors(EX, d);
      // disco de cima: face de dentro em ctop; mãos de palma pra cima apoiando o disco, dedos pro meio
      ["l", "r"].forEach((l) => {
        const s = l === "l" ? -1 : 1;
        const punho = ctop.clone().add(d.clone().multiplyScalar(-0.012)).add(V3(0, 0, s * 0.125));
        braco(l, punho, V3(0, 0, s).add(V3(0.15, -0.5, 0)));
        mao(l, V3(0, 0, -s).add(d.clone().multiplyScalar(-0.15)), d);
        fecha(l, 0.45, 0.2);
      });
    },
  },
});

// ===== polias: torres nos dois lados, cabo ligado ao estribo (D) a cada quadro =====
// duas torres de frente uma pra outra (esquerda em z<0 e direita em z>0), saída do cabo na altura alt
PE.torres = (g, alt, xT = -0.15, zT = 1.15) => {
  const L = K.torre({ alt }), R = K.torre({ alt });
  L.g.position.set(xT, 0, -zT); R.g.position.set(xT, 0, zT); R.g.rotation.y = Math.PI;
  g.add(L.g, R.g); return [L, R];
};
// estribo posicionado em O: eixo da pega = X local; arco do D no lado das costas dos dedos (oposto da palma)
PE.poeEstribo = (est, O, eixo, palma) => {
  const X = eixo.clone().normalize(), Y = palma.clone().negate(); Y.sub(X.clone().multiplyScalar(Y.dot(X))).normalize();
  est.position.copy(O); est.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(X, Y, X.clone().cross(Y)));
  return O.clone().add(Y.clone().multiplyScalar(0.075));
};
// mão l segurando o estribo; a palma olha pra longe da polia (a tração do cabo empurra o estribo pra fora da mão)
PE.maoCabo = (l, { ponto = null, punho = null }, torre, est, polo, vies = null) => {
  const S = ondeEsta("upperarm_" + l);
  const Ho = ponto ? ponto.clone() : punho.clone().add(punho.clone().sub(S).normalize().multiplyScalar(0.09));
  const arm = Ho.clone().sub(S).normalize();
  const u = torre.saida().sub(Ho).normalize();
  const palma = u.clone().negate(); if (vies) palma.add(vies); palma.normalize();
  const eixo = palma.clone().cross(arm); if (eixo.lengthSq() < 1e-4) eixo.set(1, 0, 0); eixo.normalize();
  const args = ponto ? { ponto, eixo, palma, polo, R: 0.015 } : { punho, eixo, palma, polo, R: 0.015 };
  const O = agarra(l, args);
  const nn = palma.clone().sub(eixo.clone().multiplyScalar(palma.dot(eixo))).normalize();
  const att = PE.poeEstribo(est, O, eixo, nn);
  torre.liga(att);
  return O;
};
// estância escalonada em pé: esquerdo à frente
PE.passo = (frente = "l") => {
  for (const l of ["l", "r"]) {
    const s = l === "l" ? -1 : 1, f = l === frente ? 1 : -1;
    perna(l, V3(0.24 * f + 0.02, ALT_TORN, s * 0.13), V3(1, 0.3, s * 0.1)); pe(l, F0);
  }
};

const CRUZ = {
  alta:  { alt: 1.95, incl: 0.30, e0: -0.55, e1: 0.40, f1: 1.40, nome: "Crossover na polia alta",
    dica: "Polias lá em cima, tronco levemente inclinado, um pé na frente. Puxa as mãos em arco pra baixo e pra dentro até se encontrarem na frente do quadril, apertando o peito embaixo; volta devagar até o peito alongar." },
  media: { alt: 1.30, incl: 0.20, e0: -0.06, e1: 0.06, f1: 1.50, nome: "Crossover na polia média",
    dica: "Polias na altura do ombro. Cotovelo levemente dobrado e travado, fecha os braços na frente do peito como um abraço e segura um instante antes de abrir de volta." },
  baixa: { alt: 0.22, incl: 0.14, e0: 0.45, e1: -0.50, f1: 1.05, nome: "Crossover na polia baixa",
    dica: "Polias no chão. Parte com as mãos ao lado do quadril e sobe em arco, braços quase esticados, até as mãos se encontrarem na altura do queixo. Mira a parte de cima do peito." },
};
Object.assign(MOLDES, {
  pe_crossover: {
    nome: "Crossover na polia",
    musc: { peitoral: 1, deltoide: 0.5, biceps: 0.3 },
    dica: "",
    cam: { alvo: V3(0.05, 1.1, 0), dist: 4.6, yaw: 72, pitch: 12 },
    cena(g) {
      const c = CRUZ[this.p.altura || "media"]; this.dica = c.dica; this.nome = c.nome;
      this.T = PE.torres(g, c.alt); this.est = [K.estribo(), K.estribo()]; g.add(...this.est);
      this.pose(1); // fixa o curso da pilha na posição aberta
    },
    pose(t) {
      zera();
      const c = CRUZ[this.p.altura || "media"];
      emPe(V3(0.0, ALT_QUADRIL - 0.1, 0), F0, c.incl); gira("neck_01", EX, -c.incl * 0.5);
      B.pelvis.updateMatrixWorld(true);
      PE.passo("l");
      const r = (COMP.upperarm_l + COMP.lowerarm_l) * 0.92, fi = -0.25 + (c.f1 + 0.25) * t, ep = c.e0 + (c.e1 - c.e0) * t;
      ["l", "r"].forEach((l, i) => {
        const s = l === "l" ? -1 : 1, Sh = ondeEsta("upperarm_" + l);
        const d = V3(Math.cos(fi) * Math.cos(ep), Math.sin(ep), s * Math.sin(fi) * Math.cos(ep));
        const polo = V3(-Math.sin(fi), -0.3, s * Math.cos(fi));
        PE.maoCabo(l, { ponto: Sh.clone().add(d.multiplyScalar(r)) }, this.T[i], this.est[i], polo);
      });
    },
  },
});

// ===== crucifixo na polia deitado (polias baixas dos dois lados do banco) =====
Object.assign(MOLDES, {
  pe_crucifixo_polia: {
    nome: "Crucifixo na polia deitado",
    musc: { peitoral: 1, deltoide: 0.6, biceps: 0.35 },
    dica: "Deitado no banco reto entre as duas polias baixas. Cotovelo levemente dobrado e fixo, abre até o peito alongar e fecha em arco como num abraço; com o cabo a tensão não some no topo.",
    cam: { alvo: V3(-0.1, 0.7, 0), dist: 5.2, yaw: 85, pitch: 30 },
    cena(g) {
      g.add(banco());
      this.T = PE.torres(g, 0.22, -0.32, 1.0); this.est = [K.estribo(), K.estribo()]; g.add(...this.est);
      this.pose(1);
    },
    pose(t) {
      zera();
      const { cab, fr, pes } = PE.quadroDeitado(0);
      PE.tronco(V3(0.16, 0.565, 0), 0, t, 0.05 * t - 0.03 * (1 - t));
      for (const l of ["l", "r"]) { const s = l === "l" ? -1 : 1; perna(l, V3(0.6, ALT_TORN, s * 0.31), V3(0.3, 1, s * 0.22)); pe(l, V3(1, 0, s * 0.25)); }
      const R = (COMP.upperarm_l + COMP.lowerarm_l) * 0.9, fi = -0.16 + 1.5 * t;
      ["l", "r"].forEach((l, i) => {
        const s = l === "l" ? -1 : 1, O = ondeEsta("upperarm_" + l), lado = V3(0, 0, s);
        const dir = fr.clone().multiplyScalar(Math.cos(fi)).add(lado.clone().multiplyScalar(Math.sin(fi))).add(pes.clone().multiplyScalar(0.12)).normalize();
        PE.maoCabo(l, { punho: O.clone().add(dir.multiplyScalar(R)) }, this.T[i], this.est[i],
          lado.clone().add(fr.clone().multiplyScalar(-0.35)).add(pes.clone().multiplyScalar(0.25)));
      });
    },
  },
});

// ===== press de peito no cabo, um braço de cada vez, em pé, de costas pra torre =====
Object.assign(MOLDES, {
  pe_press_cabo: {
    nome: "Press de peito no cabo unilateral",
    musc: { peitoral: 1, triceps: 0.6, deltoide: 0.7 },
    dica: "De costas pra polia na altura do peito, um pé na frente e o tronco firme. Empurra a pegada pra frente girando só um pouco o ombro e estica o braço; o core segura pra não deixar o cabo te girar. Depois troca de lado.",
    cam: { alvo: V3(0.0, 1.15, 0.1), dist: 4.6, yaw: 62, pitch: 12 },
    cena(g) {
      const T = K.torre({ alt: 1.3 }); T.g.position.set(-1.0, 0, 0.5); T.g.rotation.y = Math.PI / 2; g.add(T.g); this.T = T;
      this.est = K.estribo(); g.add(this.est);
      this.pose(1);
    },
    pose(t) {
      zera();
      const tw = 0.24 * (1 - t) - 0.05 * t; // o tronco gira junto com o empurrão
      emPe(V3(0.02, ALT_QUADRIL - 0.1, 0), F0, 0.12); gira("neck_01", EX, -0.06);
      gira("spine_01", EY, tw * 0.3); gira("spine_02", EY, tw * 0.35); gira("spine_03", EY, tw * 0.35);
      B.pelvis.updateMatrixWorld(true);
      PE.passo("l"); // pé esquerdo à frente, braço direito trabalha
      const Sh = ondeEsta("upperarm_r");
      const frente = 0.5 - 0.27 * t, queda = 0.0 + 0.1 * t, med = 0.0 + 0.1 * t;
      PE.maoCabo("r", { ponto: Sh.clone().add(V3(frente, -queda, -med)) }, this.T, this.est, V3(-1, -0.3, 0.8));
      // braço esquerdo: mão na cintura
      const cint = ondeEsta("pelvis").add(V3(0.03, 0.09, -0.2));
      braco("l", cint, V3(-0.6, 0.1, -1));
      mao("l", V3(0.7, -0.5, 0.2), V3(0, 0, 1));
    },
  },
});

// ===== flexão de braço (normal / inclinada com mãos no banco / declinada com pés no banco / diamante) =====
// corpo em tábua: gira em volta da ponta dos pés; a altura do ombro manda no ângulo. Mãos fixas no chão (ou no banco).
Object.assign(MOLDES, {
  pe_flexao: {
    nome: "Flexão de braço",
    musc: { peitoral: 1, triceps: 0.7, deltoide: 0.7, abdomen: 0.4 },
    dica: "Corpo reto da cabeça aos calcanhares, abdômen e glúteo firmes. Desce até o peito quase tocar o chão com o cotovelo a uns 45° do tronco e empurra o chão de volta sem deixar o quadril cair.",
    cam: { alvo: V3(0.25, 0.35, 0), dist: 4.0, yaw: 72, pitch: 14 },
    cena(g) {
      const p = this.p; g.add(K.piso(2.6, 1.7));
      if (p.maosBanco) { const b = banco(); b.rotation.y = Math.PI / 2; b.position.set(0.9, 0, 0); g.add(b); } // 0.9 = x das mãos
      if (p.pesBanco) { const b = banco(); b.rotation.y = Math.PI / 2; b.position.set(-0.7, 0, 0); g.add(b); }
    },
    pose(t) {
      zera();
      const p = this.p, yh = p.maosBanco ? 0.4425 : 0, yT = p.pesBanco ? 0.4425 : 0;
      const xh = p.maosBanco ? 0.9 : 0.55, zw = p.diamante ? 0.045 : 0.27; // mãos
      const hsTop = yh + 0.5, hsBot = yh + 0.215, hs = lerp(hsTop, hsBot, t);
      const Ay = yT + 0.15, Lb = 0.905 + 0.49;
      const aT = Math.asin((hsTop - Ay) / Lb), xT = xh - 0.0 - Lb * Math.cos(aT) + (p.diamante ? 0 : 0);
      const al = Math.asin((hs - Ay) / Lb), u = V3(Math.cos(al), Math.sin(al), 0), fr = V3(Math.sin(al), -Math.cos(al), 0);
      const A = V3(xT, Ay, 0), P0 = A.clone().add(u.clone().multiplyScalar(0.912));
      corpoEm(P0, u, fr);
      gira("neck_01", EX, 0.15 + (al < 0 ? -al * 0.5 : 0)); gira("head", EX, 0.0);
      for (const l of ["l", "r"]) gira("clavicle_" + l, EZ, (l === "l" ? -1 : 1) * 0.06 * (1 - t));
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { // pernas retas, ponta dos pés plantada
        const s = l === "l" ? -1 : 1, tor = V3(xT, Ay, s * 0.1);
        perna(l, tor, V3(0, 1, s * 0.2));
        mira("foot_" + l, fr.clone().multiplyScalar(0.95).add(u.clone().multiplyScalar(-0.2)).normalize(), V3(0, 0, -1), EX);
      }
      ["l", "r"].forEach((l) => {
        const s = l === "l" ? -1 : 1;
        const punho = V3(xh, yh + 0.045, s * zw);
        const dedos = p.diamante ? V3(0.8, 0, -s * 0.6) : V3(1, 0, -s * 0.12);
        braco(l, punho, V3(-1, 0.1, s * (p.diamante ? 0.45 : 0.9)));
        mao(l, dedos, V3(0, -1, 0));
      });
    },
  },
});

// ===== mergulho nas paralelas (peito): tronco inclinado pra frente, cotovelo abre, desce fundo =====
Object.assign(MOLDES, {
  pe_mergulho: {
    nome: "Mergulho nas paralelas (peito)",
    musc: { peitoral: 1, triceps: 0.85, deltoide: 0.6 },
    dica: "Inclina o tronco pra frente e deixa o cotovelo abrir um pouco. Desce até o ombro passar da linha do cotovelo, sentindo o peito alongar, e sobe empurrando as barras sem travar de vez em cima.",
    cam: { alvo: V3(0.0, 1.2, 0), dist: 4.2, yaw: 62, pitch: 12 },
    cena(g) {
      g.add(K.piso(2.6, 2.6)); this.par = K.paralelas({ alt: 1.15, abre: 0.52, comp: 0.8 }); g.add(this.par.g);
    },
    pose(t) {
      zera();
      const ps = this.par, bar = ps.alt + 0.0;
      const incl = lerp(0.42, 0.62, t), Sx = lerp(0.03, 0.1, t), Sy = bar + lerp(0.545, 0.33, t);
      emPe(V3(0, Sy - 0.46, 0), F0, incl); // provisório, corrige pelo ombro
      B.pelvis.updateMatrixWorld(true);
      const om = ondeEsta("upperarm_l").add(ondeEsta("upperarm_r")).multiplyScalar(0.5);
      B.pelvis.position.add(V3(Sx, Sy, 0).sub(om)); B.pelvis.updateMatrixWorld(true);
      gira("neck_01", EX, -0.2 - incl * 0.3);
      for (const l of ["l", "r"]) { // joelhos dobrados, pés cruzados atrás
        const s = l === "l" ? -1 : 1, q = ondeEsta("thigh_" + l);
        perna(l, q.clone().add(V3(-0.32, -0.52, -s * 0.0 + s * 0.02)), V3(1, -0.2, s * 0.1));
        mira("foot_" + l, V3(-0.25, -0.95, 0).normalize(), V3(0, 0, -1), EX);
      }
      ["l", "r"].forEach((l) => {
        const s = l === "l" ? -1 : 1;
        agarra(l, { ponto: V3(0.0, bar, s * ps.abre / 2), R: 0.022, eixo: V3(1, 0, 0), palma: V3(0, -0.5, -s * 1),
          polo: V3(-1, 0.05, s * 0.4) });
      });
    },
  },
});

// ===== músculos (FOCOS) e vista =====
// EMG consultado (resumos/abstracts, não os PDFs inteiros), números relativos dentro de cada exercício são ESTIMATIVA:
//  Schanke 2012 (tese UW-La Crosse / ACE, 14 homens, peitoral maior, % do supino reto): pec deck 98, crossover inclinado 93, máquina de supino 79,
//   crucifixo inclinado 69, mergulho 69, flexão 61 (tabela conferida na página da ACE).
//  Marcolin 2015 J Athl Train 50(11) (flexões: base estreita ativa mais peitoral e tríceps; só significância, sem amplitude) - conferido.
//  Rodríguez-Ridao 2020 IJERPH 17(19):7339 (30° = pico do peitoral superior; 0° = médio/inferior; deltoide ant. sobe com a inclinação) - resumo conferido.
//  Glass & Armstrong 1997 JSCR 11(3):163 (declinado -15° vs inclinado +30°: peitoral inferior difere, superior não) - só fonte secundária.
//  Barnett 1995 (declinado: clavicular menos ativa) e Saeterbakken 2011 (Smith/barra/halter ~ iguais no peitoral) - citados via pesquisa-musculos.md.
//  Pullover: estudos pequenos (barra x halter iguais; peitoral ~ dorsal, %RMS 33,7 vs 35,8) - só resumo. Sem EMG achado: crossover alta/média/baixa,
//  crucifixo declinado, press no cabo unilateral, diferença flexão inclinada/declinada/diamante entre cabeças (tudo estimativa por mecânica).
Object.assign(FOCOS, {
  pe_supino_decl: (p) => [["peitoral_inf", 1], ["peitoral_med", 0.95], ["triceps_lateral", p.halter ? 0.55 : 0.7], ["peitoral_sup", 0.6], ["deltoide_ant", 0.5], ["triceps_longa", 0.4], ["serratil", 0.3], p.halter ? ["biceps", 0.3] : ["dorsal", 0.2]],
  pe_smith: (p) => p.inclina ? [["peitoral_sup", 1], ["deltoide_ant", 0.9], ["peitoral_med", 0.75], ["triceps_lateral", 0.55], ["peitoral_inf", 0.45], ["triceps_longa", 0.4], ["serratil", 0.3]]
    : [["peitoral_med", 1], ["peitoral_inf", 0.9], ["peitoral_sup", 0.8], ["deltoide_ant", 0.75], ["triceps_lateral", 0.65], ["triceps_longa", 0.45], ["serratil", 0.25]],
  pe_maq_supino: (p) => p.inclina ? [["peitoral_sup", 1], ["deltoide_ant", 0.85], ["peitoral_med", 0.75], ["triceps_lateral", 0.55], ["peitoral_inf", 0.4], ["serratil", 0.3]]
    : [["peitoral_med", 1], ["peitoral_inf", 0.85], ["peitoral_sup", 0.8], ["deltoide_ant", 0.7], ["triceps_lateral", 0.65], ["triceps_longa", 0.4], ["serratil", 0.3]],
  pe_crucifixo_decl: () => [["peitoral_inf", 1], ["peitoral_med", 0.9], ["peitoral_sup", 0.5], ["deltoide_ant", 0.45], ["biceps", 0.35], ["serratil", 0.25]],
  pe_voador: () => [["peitoral_med", 1], ["peitoral_sup", 0.9], ["peitoral_inf", 0.85], ["deltoide_ant", 0.6], ["serratil", 0.3], ["biceps", 0.2]],
  pe_crossover: (p) => p.altura === "alta" ? [["peitoral_inf", 1], ["peitoral_med", 0.95], ["peitoral_sup", 0.55], ["deltoide_ant", 0.5], ["serratil", 0.35], ["biceps", 0.3]]
    : p.altura === "baixa" ? [["peitoral_sup", 1], ["deltoide_ant", 0.85], ["peitoral_med", 0.85], ["peitoral_inf", 0.4], ["serratil", 0.4], ["biceps", 0.35]]
    : [["peitoral_med", 1], ["peitoral_inf", 0.8], ["peitoral_sup", 0.8], ["deltoide_ant", 0.55], ["serratil", 0.35], ["biceps", 0.3]],
  pe_crucifixo_polia: () => [["peitoral_med", 1], ["peitoral_sup", 0.85], ["peitoral_inf", 0.75], ["deltoide_ant", 0.6], ["biceps", 0.35], ["serratil", 0.3]],
  pe_pullover: () => [["peitoral_med", 1], ["dorsal", 0.95], ["peitoral_inf", 0.75], ["triceps_longa", 0.7], ["peitoral_sup", 0.5], ["serratil", 0.5], ["deltoide_post", 0.35]],
  pe_flexao: (p) => p.diamante ? [["triceps_lateral", 1], ["peitoral_med", 0.9], ["triceps_longa", 0.85], ["peitoral_sup", 0.8], ["deltoide_ant", 0.75], ["peitoral_inf", 0.7], ["serratil", 0.5]]
    : p.pesBanco ? [["peitoral_sup", 1], ["deltoide_ant", 0.9], ["peitoral_med", 0.9], ["peitoral_inf", 0.6], ["triceps_lateral", 0.7], ["serratil", 0.6], ["abdomen", 0.4]]
    : p.maosBanco ? [["peitoral_inf", 1], ["peitoral_med", 0.9], ["triceps_lateral", 0.6], ["deltoide_ant", 0.55], ["peitoral_sup", 0.5], ["serratil", 0.5], ["abdomen", 0.35]]
    : [["peitoral_med", 1], ["peitoral_inf", 0.9], ["peitoral_sup", 0.85], ["deltoide_ant", 0.8], ["triceps_lateral", 0.7], ["triceps_longa", 0.55], ["serratil", 0.6], ["abdomen", 0.4]],
  pe_mergulho: () => [["peitoral_inf", 1], ["peitoral_med", 0.9], ["triceps_lateral", 0.85], ["triceps_longa", 0.8], ["deltoide_ant", 0.65], ["peitoral_sup", 0.4], ["serratil", 0.3]],
  pe_press_cabo: () => [["peitoral_med", 1], ["peitoral_sup", 0.8], ["peitoral_inf", 0.8], ["deltoide_ant", 0.7], ["triceps_lateral", 0.6], ["serratil", 0.5], ["obliquo", 0.4], ["abdomen", 0.3]],
});
Object.assign(VISTA, { pe_crossover: 75, pe_press_cabo: 70, pe_voador: 70, pe_mergulho: 70, pe_flexao: 72 });
}

// ===== moldes/posterior.js =====
{ // moldes/posterior.js — posterior de coxa e glúteos (prefixo po_)
// ---------- ajudantes do grupo ----------
const PO = {};
PO.ANG_PE = Math.acos(DIR.calf_l.dot(DIR.foot_l)); // ângulo canela-pé em repouso
PO.espuma = new THREE.MeshStandardMaterial({ color: 0x23262d, roughness: 0.8 });
PO.verm = new THREE.MeshStandardMaterial({ color: 0xb3262b, roughness: 0.5, metalness: 0.2 });
PO.sg = (l) => (l === "l" ? 1 : -1);
// pé relativo à canela (r = retorno de perna()); plantar > 0 aponta a ponta do pé, < 0 puxa pra canela
PO.peAr = (l, r, plantar = 0) => {
  const n = r.alvo.clone().sub(r.E).normalize(), h = r.dob, f = n.clone().cross(h), ang = PO.ANG_PE - plantar;
  mira("foot_" + l, n.clone().multiplyScalar(Math.cos(ang)).add(f.multiplyScalar(Math.sin(ang))), h, EX);
};
// pé por direção da ponta e do peito do pé (dorso)
PO.peOri = (l, dir, dorso) => { const d = dir.clone().normalize(); mira("foot_" + l, d, dorso.clone().cross(d).normalize(), EX); };
// eixo (ao longo do osso até a ponta) -> cilindro entre dois pontos já existe: K.tubo. Marca de ponto (debug) não usada.
// alvo do pelve em relação a um ponto de contato C (costas apoiadas): a pelve gira em círculo em volta de C
PO.pelveApoio = (C, a, D, L) => {
  const cab = V3(-Math.cos(a), Math.sin(a), 0), fr = V3(Math.sin(a), Math.cos(a), 0);
  return { cab, fr, pos: C.clone().add(fr.clone().multiplyScalar(D)).sub(cab.clone().multiplyScalar(L)) };
};
PO.coluna = (mat, ...a) => { const g = new THREE.Group(); a.forEach((p) => g.add(p)); return g; };
// caixa de pilha de placas (torre de máquina), por trás do aparelho; x,z = posição; larg do painel
PO.pilhaCaixa = (x, z, rotY = 0) => {
  const g = new THREE.Group();
  const p = K.pilha(); p.position.set(0, 0.04, 0); g.add(p);
  g.add(K.caixa(0.36, 1.45, 0.025, M.quadro, 0.006).translateY(0.78).translateZ(0.12));
  g.add(K.caixa(0.36, 0.06, 0.26, M.quadro, 0.01).translateY(1.5));
  g.add(K.caixa(0.4, 0.04, 0.3, M.quadro, 0.01).translateY(0.02));
  for (const s of [-1, 1]) g.add(K.caixa(0.03, 1.45, 0.26, M.quadro, 0.006).translateY(0.78).translateX(s * 0.17));
  g.position.set(x, 0, z); g.rotation.y = rotY; return sombreia(g);
};
PO.piso = () => K.piso(3.2, 3.2);
PO.banco = (cx, larg = 0.9, prof = 0.34) => { // banco de elevação pélvica: topo estofado com a largura no eixo Z
  const g = new THREE.Group();
  g.add(K.caixa(prof, 0.085, larg, M.estofado, 0.03).translateX(cx).translateY(0.40));
  g.add(K.caixa(prof - 0.1, 0.03, larg - 0.2, M.quadro, 0.008).translateX(cx).translateY(0.345));
  for (const s of [-1, 1]) {
    g.add(K.viga(V3(cx, 0.34, s * (larg / 2 - 0.12)), V3(cx, 0.03, s * (larg / 2 - 0.12)), 0.06));
    g.add(K.caixa(0.46, 0.05, 0.08, M.quadro, 0.015).translateX(cx).translateY(0.025).translateZ(s * (larg / 2 - 0.12)));
  }
  return sombreia(g);
};
PO.rolo = (comp, r, mat = M.estofado) => { const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, comp, 28), mat); m.rotation.x = Math.PI / 2; m.castShadow = true; const g = new THREE.Group(); g.add(m); return g; }; // cilindro ao longo de Z
PO.anilhaZ = (r, e = 0.035) => { const a = anilha(r, e); a.rotation.x = Math.PI / 2; const g = new THREE.Group(); g.add(a); return sombreia(g); };
// pose comum da elevação pélvica (costas no apoio, pelve gira em volta do ponto de contato); devolve onde fica a barra/almofada
PO.hipThrust = (m, t, p) => {
  zera();
  const CX = m.CX, C = V3(CX, PO.TOPO_BANCO, 0);
  const a = lerp(0.02, 1.0, t), { cab, fr, pos } = PO.pelveApoio(C, a, PO.D_COSTAS, PO.L_COSTAS);
  corpoEm(pos, cab, fr);
  const beta = lerp(0.95, 0.22, t); gira("neck_01", EX, beta * 0.6); gira("head", EX, beta * 0.4);
  B.pelvis.updateMatrixWorld(true);
  const PEX = CX + PO.L_COSTAS + 0.44, yT = ALT_TORN + (m.alturaPe || 0);
  for (const l of ["l", "r"]) {
    const s = l === "l" ? -1 : 1;
    if (p.uni && l === "r") { // perna livre: joelho dobrado, no ar
      const H = ondeEsta("thigh_r");
      const r = perna("r", H.clone().add(V3(0.5, 0.33, 0.04)), V3(0.5, 1, 0.1)); PO.peAr("r", r, 0.3);
    } else {
      perna(l, V3(PEX, yT, p.uni ? s * 0.12 : s * 0.17), V3(0.25, 1, s * 0.3)); pe(l, V3(1, 0, s * 0.3), m.alturaPe ? DIR.foot_l.y : null);
    }
  }
  const bar = pos.clone().add(fr.clone().multiplyScalar(0.12)).add(cab.clone().multiplyScalar(-0.02));
  for (const l of ["l", "r"]) {
    const s = l === "l" ? -1 : 1;
    agarra(l, { ponto: bar.clone().add(V3(0, 0, s * (m.larg || 0.3))), R: 0.014, eixo: V3(0, 0, -s),
      palma: fr.clone().multiplyScalar(-1).add(cab.clone().multiplyScalar(-0.2)), polo: V3(0, 0, s).add(cab.clone().multiplyScalar(0.4)) });
  }
  return { pos, cab, fr, bar, a, C };
};
// alavanca de máquina de flexora: rolo no calcanhar, dois braços até o eixo (no joelho, de cada lado) e chifre com anilhas atrás do eixo
PO.alavancaCena = (m, g, ladoZ = 0.28) => {
  const Q = m.pivoG; m.lz = ladoZ;
  m.rolo = PO.rolo(0.5, 0.045); g.add(m.rolo);
  for (const s of [-1, 1]) {
    g.add(K.viga(V3(Q.x, 0.05, s * ladoZ), V3(Q.x, Q.y, s * ladoZ), 0.07)); g.add(K.caixa(0.1, 0.05, 0.12, M.quadro, 0.012).translateX(Q.x).translateY(0.025).translateZ(s * ladoZ));
    const ax = K.cilU(0.028, M.cromo); ax.scale.y = 0.1; ax.rotation.x = Math.PI / 2; ax.position.set(Q.x, Q.y, s * ladoZ); g.add(ax);
  }
  g.add(K.caixa(0.1, 0.05, ladoZ * 2 + 0.1, M.quadro, 0.012).translateX(Q.x).translateY(0.025));
  m.bracos = [-1, 1].map(() => { const x = K.tubo(V3(), V3(0, 1, 0), 0.022, M.quadro); g.add(x); return x; });
  m.horn = [-1, 1].map(() => { const x = K.cilU(0.022, M.cromo); x.scale.y = 0.3; x.rotation.x = Math.PI / 2; g.add(x); return x; });
  m.plates = [-1, 1].map(() => [0, 1].map(() => { const a = PO.anilhaZ(0.14, 0.034); g.add(a); return a; }));
};
PO.alavancaPose = (m, K0, u, n, ao, off) => {
  const Q = V3(K0.x, K0.y, 0), c = Q.clone().add(u.clone().multiplyScalar(ao)).add(n.clone().multiplyScalar(off)), R = Q.clone().sub(c.clone().sub(Q).normalize().multiplyScalar(0.28));
  m.rolo.position.copy(c);
  [-1, 1].forEach((s, i) => {
    K.poe(m.bracos[i], V3(Q.x, Q.y, s * m.lz), V3(c.x, c.y, s * m.lz));
    m.horn[i].position.set(R.x, R.y, s * (m.lz + 0.04));
    m.plates[i].forEach((a, k) => a.position.set(R.x, R.y, s * (m.lz + 0.01 + 0.045 * k)));
  });
};
PO.TOPO_BANCO = 0.4425; // y do estofado
PO.D_COSTAS = 0.1225;   // espessura: eixo da coluna até a superfície das costas (igual ao supino)
PO.L_COSTAS = 0.38;     // da pelve até o ponto do tronco que encosta no banco (borda da escápula)

Object.assign(MOLDES, {
  // ---------- elevação pélvica com barra (costas no banco) e unilateral ----------
  po_ht: {
    nome: "Elevação pélvica com barra",
    musc: { gluteo: 1, posterior: 0.6, quadriceps: 0.45, adutor: 0.4 },
    dica: "Escápulas apoiadas na borda do banco, canelas verticais lá em cima. Queixo no peito, sobe empurrando o calcanhar até a coxa alinhar com o tronco e segura um instante apertando o glúteo; desce sem encostar o quadril no chão.",
    cam: { alvo: V3(0.12, 0.42, 0), dist: 3.9, yaw: 8, pitch: 6 },
    cena(g) {
      const CX = -0.2; this.CX = CX;
      g.add(PO.piso()); g.add(PO.banco(CX - 0.17));
      this.bar = barra(1);
      const pad = cil(0.05, 0.3, PO.espuma, 24); pad.rotation.z = Math.PI / 2; this.bar.add(pad);
      g.add(this.bar);
    },
    pose(t) {
      const h = PO.hipThrust(this, t, this.p);
      this.bar.position.copy(h.bar); this.bar.rotation.set(0, Math.PI / 2, 0);
    },
  },
  // ---------- elevação pélvica na máquina (alavanca com carga de anilhas) ----------
  po_ht_maq: {
    nome: "Elevação pélvica na máquina",
    musc: { gluteo: 1, posterior: 0.6, quadriceps: 0.45, adutor: 0.4 },
    dica: "Costas no encosto, almofada sobre o quadril e pés na plataforma. Empurra o calcanhar, sobe o quadril até o tronco alinhar com a coxa e aperta o glúteo; desce devagar sem soltar a alavanca.",
    cam: { alvo: V3(0.15, 0.45, 0), dist: 4.0, yaw: 42, pitch: 12 },
    alturaPe: 0.03, larg: 0.285,
    cena(g) {
      const CX = -0.2; this.CX = CX;
      g.add(PO.piso()); g.add(PO.banco(CX - 0.18, 0.62, 0.36));
      for (const s of [-1, 1]) {
        g.add(K.caixa(2.0, 0.05, 0.07, M.quadro, 0.012).translateX(CX + 0.45).translateY(0.025).translateZ(s * 0.34));
        g.add(K.viga(V3(CX - 0.03, 0.05, s * 0.34), V3(CX - 0.03, PO.TOPO_BANCO + 0.02, s * 0.34), 0.07));
        const ax = K.cilU(0.03, M.cromo); ax.scale.y = 0.1; ax.rotation.x = Math.PI / 2; ax.position.set(CX, PO.TOPO_BANCO, s * 0.34); g.add(ax);
      }
      for (const x of [CX - 0.45, CX + 0.3, CX + 1.35]) g.add(K.caixa(0.08, 0.05, 0.74, M.quadro, 0.012).translateX(x).translateY(0.025));
      const plat = K.caixa(0.55, 0.03, 0.5, M.quadro, 0.01); plat.position.set(CX + 0.82, 0.015, 0); g.add(plat);
      const calc = K.caixa(0.05, 0.05, 0.5, M.aco, 0.01); calc.position.set(CX + 0.52, 0.055, 0); g.add(calc);
      this.pad = PO.rolo(0.44, 0.065); g.add(this.pad);
      this.stubs = [-1, 1].map((s) => { const c = K.cilU(0.016, M.cromo); c.scale.y = 0.2; c.rotation.x = Math.PI / 2; c.position.z = s * 0.285; this.pad.add(c); return c; });
      this.bracos = [-1, 1].map((s) => { const m = K.tubo(V3(), V3(0, 1, 0), 0.024, M.quadro); g.add(m); return m; });
      this.horn = [-1, 1].map((s) => { const m = K.cilU(0.024, M.cromo); m.scale.y = 0.34; m.rotation.x = Math.PI / 2; g.add(m); return m; });
      this.plates = [-1, 1].map((s) => [0, 1, 2].map((i) => { const a = PO.anilhaZ(0.16, 0.034); g.add(a); return a; }));
    },
    pose(t) {
      const h = PO.hipThrust(this, t, this.p), s3 = [-1, 1];
      this.pad.position.copy(h.bar);
      const u = h.bar.clone().sub(h.C).normalize(), R = h.C.clone().add(u.clone().multiplyScalar(-0.52));
      s3.forEach((s, i) => {
        K.poe(this.bracos[i], V3(R.x, R.y, s * 0.34), V3(h.bar.x, h.bar.y, s * 0.34));
        this.horn[i].position.set(R.x, R.y, s * 0.4);
        this.plates[i].forEach((a, k) => a.position.set(R.x, R.y, s * (0.34 + 0.045 * k + 0.02)));
      });
    },
  },
  // ---------- ponte de glúteo no solo e frog pump ----------
  po_ponte: {
    nome: "Ponte de glúteo no solo",
    musc: { gluteo: 1, posterior: 0.6, quadriceps: 0.35, adutor: 0.3 },
    dica: "Costas no chão, calcanhares perto do glúteo. Empurra o chão com os pés e sobe o quadril até o corpo formar uma linha do ombro ao joelho; aperta o glúteo em cima e desce sem apoiar totalmente.",
    cam: { alvo: V3(0.25, 0.3, 0), dist: 3.4, yaw: 50, pitch: 12 },
    cena(g) { g.add(PO.piso()); const tp = K.colchonete(1.9, 0.7); tp.position.x = 0.3; g.add(tp); this.CX = -0.2; },
    pose(t) {
      zera();
      const fg = !!this.p.frog, CX = this.CX, MAT = 0.02, C = V3(CX, MAT, 0);
      const a = lerp(fg ? -0.42 : -0.56, -0.02, t), { cab, fr, pos } = PO.pelveApoio(C, a, PO.D_COSTAS, PO.L_COSTAS);
      corpoEm(pos, cab, fr);
      gira("neck_01", EX, 0.18); B.pelvis.updateMatrixWorld(true);
      const Hx = pos.x;
      for (const l of ["l", "r"]) {
        const s = l === "l" ? -1 : 1;
        if (fg) { // sola com sola, joelhos abertos
          const r = perna(l, V3(Hx + 0.32, MAT + 0.1, s * 0.05), V3(0.0, 0.5, s * 1));
          PO.peOri(l, V3(0.9, 0.35, 0), V3(0, 0.45, s));
        } else {
          perna(l, V3(CX + 0.95, MAT + ALT_TORN, s * 0.16), V3(0.25, 1, s * 0.3)); pe(l, V3(1, 0, s * 0.25), DIR.foot_l.y);
        }
        const S = ondeEsta("upperarm_" + l);
        braco(l, V3(S.x + 0.46, MAT + 0.06, s * 0.32), V3(0, 0, s * 0.6).add(V3(0, 1, 0)));
        mao(l, V3(1, 0, 0), V3(0, -1, 0));
      }
    },
  },
  // ---------- mesa flexora (deitado de bruços) ----------
  po_flex_deit: {
    nome: "Mesa flexora",
    musc: { posterior: 1, panturrilha: 0.5, gluteo: 0.25 },
    dica: "Deitado de bruços, joelho na ponta do banco e o rolo logo acima do calcanhar. Puxa o calcanhar em direção ao glúteo sem tirar o quadril do banco e desce devagar até quase esticar.",
    cam: { alvo: V3(0.05, 0.62, 0), dist: 4.1, yaw: 40, pitch: 24 },
    cena(g) {
      const BT = 0.52; this.BT = BT; g.add(PO.piso());
      g.add(K.caixa(1.35, 0.09, 0.42, M.estofado, 0.035).translateX(-0.2).translateY(BT - 0.045));
      g.add(K.caixa(1.5, 0.06, 0.1, M.quadro, 0.012).translateX(-0.28).translateY(0.03));
      for (const x of [-0.78, 0.18]) { g.add(K.viga(V3(x, 0.05, 0), V3(x, BT - 0.09, 0), 0.09)); g.add(K.caixa(0.1, 0.05, 0.6, M.quadro, 0.012).translateX(x).translateY(0.025)); }
      // pegador na cabeceira
      for (const s of [-1, 1]) g.add(K.tubo(V3(-0.93, BT - 0.1, s * 0.27), V3(-0.93, BT + 0.02, s * 0.27), 0.02, M.quadro));
      g.add(K.tubo(V3(-0.93, BT + 0.02, -0.3), V3(-0.93, BT + 0.02, 0.3), 0.017, M.cromo));
      g.add(K.caixa(0.1, 0.05, 0.6, M.quadro, 0.012).translateX(-0.93).translateY(0.025)); g.add(K.viga(V3(-0.93, 0.05, 0.27), V3(-0.93, BT - 0.1, 0.27), 0.05)); g.add(K.viga(V3(-0.93, 0.05, -0.27), V3(-0.93, BT - 0.1, -0.27), 0.05));
      this.pivoG = V3(0.49, BT + 0.08, 0); PO.alavancaCena(this, g);
    },
    pose(t) {
      zera();
      const BT = this.BT, phi = lerp(1.7, 0.05, t), pelv = V3(0, BT + 0.125, 0);
      corpoEm(pelv, V3(-1, 0, 0), V3(0, -1, 0));
      gira("neck_01", EX, -0.5); gira("head", EX, -0.25);
      B.pelvis.updateMatrixWorld(true);
      const u = V3(Math.cos(phi), Math.sin(phi), 0), n = V3(-Math.sin(phi), Math.cos(phi), 0);
      let K0 = null;
      for (const l of ["l", "r"]) {
        const sz = l === "l" ? 1 : -1, H = ondeEsta("thigh_" + l);
        const K1 = H.clone().add(V3(Math.cos(0.09), -Math.sin(0.09), 0).multiplyScalar(COMP.thigh_l)); K0 = K1.clone().setZ(0);
        const r = perna(l, K1.clone().add(u.clone().multiplyScalar(COMP.calf_l)), V3(0.1, -1, 0)); PO.peAr(l, r, -0.35);
        agarra(l, { ponto: V3(-0.93, BT + 0.02, sz * 0.2), R: 0.017, eixo: V3(0, 0, -sz), palma: V3(0.3, -1, 0), polo: V3(0.2, 0.6, sz) });
      }
      PO.alavancaPose(this, K0, u, n, 0.37, 0.085);
    },
  },
  // ---------- cadeira flexora (sentado) ----------
  po_flex_sent: {
    nome: "Cadeira flexora",
    musc: { posterior: 1, panturrilha: 0.5, gluteo: 0.2 },
    dica: "Sentado com o encosto firme e a almofada travando a coxa. Puxa o calcanhar pra baixo e pra trás até o joelho passar dos 90° e volta controlando, sem levantar o quadril do assento.",
    cam: { alvo: V3(0.3, 0.55, 0), dist: 3.5, yaw: 35, pitch: 16 },
    cena(g) {
      const ST = 0.46; this.ST = ST; g.add(PO.piso());
      const r = 0.2, Py = ST + 0.1; this.pelv = V3(0, Py, 0);
      g.add(K.caixa(0.5, 0.09, 0.42, M.estofado, 0.035).translateX(0.05).translateY(ST - 0.045));
      g.add(K.viga(V3(-0.05, 0.05, 0), V3(-0.05, ST - 0.09, 0), 0.14)); g.add(K.caixa(0.8, 0.05, 0.55, M.quadro, 0.012).translateX(0.0).translateY(0.025));
      const enc = K.caixa(0.1, 0.62, 0.4, M.estofado, 0.04); enc.position.set(-0.2 - Math.sin(r) * 0.14, ST + 0.42, 0); enc.rotation.z = r; g.add(enc);
      g.add(K.viga(V3(-0.36, 0.05, 0), V3(-0.3, ST + 0.55, 0), 0.07));
      // almofada de travar a coxa
      this.coxa = PO.rolo(0.46, 0.055); this.coxa.position.set(0.3, Py + 0.145, 0); g.add(this.coxa);
      for (const s of [-1, 1]) { g.add(K.tubo(V3(0.3, Py + 0.145, s * 0.24), V3(0.24, Py + 0.3, s * 0.36), 0.02, M.quadro)); g.add(K.tubo(V3(0.24, Py + 0.3, s * 0.36), V3(-0.3, Py + 0.3, s * 0.36), 0.02, M.quadro)); }
      // pegadores laterais
      for (const s of [-1, 1]) { g.add(K.tubo(V3(-0.08, Py + 0.08, s * 0.29), V3(0.2, Py + 0.08, s * 0.29), 0.017, M.cromo)); g.add(K.tubo(V3(-0.08, ST, s * 0.29), V3(-0.08, Py + 0.08, s * 0.29), 0.02, M.quadro)); }
      this.pivoG = V3(0.5, Py - 0.01, 0); PO.alavancaCena(this, g, 0.3);
    },
    pose(t) {
      zera();
      const r = 0.2, Py = this.pelv.y, psi = lerp(1.72, 0.1, t);
      corpoEm(this.pelv, V3(-Math.sin(r), Math.cos(r), 0), V3(Math.cos(r), Math.sin(r), 0));
      gira("neck_01", EX, 0.0 - r * 0.0);
      B.pelvis.updateMatrixWorld(true);
      const u = V3(Math.cos(psi), -Math.sin(psi), 0), n = V3(-Math.sin(psi), -Math.cos(psi), 0); let K0 = null;
      for (const l of ["l", "r"]) {
        const sz = l === "l" ? -1 : 1, H = ondeEsta("thigh_" + l);
        const K1 = H.clone().add(V3(COMP.thigh_l, -0.01, 0)); K0 = K1.clone().setZ(0);
        const rr = perna(l, K1.clone().add(u.clone().multiplyScalar(COMP.calf_l)), V3(0, 1, 0)); PO.peAr(l, rr, -0.3);
        agarra(l, { ponto: V3(0.07, Py + 0.08, sz * 0.29), R: 0.017, eixo: V3(1, 0, 0), palma: V3(0, 0, -sz), polo: V3(-0.6, -0.5, sz) });
      }
      PO.alavancaPose(this, K0, u, n, 0.37, 0.085);
    },
  },
  // ---------- flexora em pé unilateral ----------
  po_flex_pe: {
    nome: "Flexora em pé unilateral",
    musc: { posterior: 1, panturrilha: 0.55, gluteo: 0.3 },
    dica: "Peito apoiado na almofada, joelho de apoio quase esticado e quadril alinhado. Flexiona só o joelho da perna de trabalho, calcanhar rumo ao glúteo, sem balançar o corpo, e desce devagar.",
    cam: { alvo: V3(0.1, 0.8, 0), dist: 3.4, yaw: 220, pitch: 10 },
    cena(g) {
      g.add(PO.piso()); const inc = 0.42; this.inc = inc;
      g.add(K.caixa(0.7, 0.05, 0.62, M.quadro, 0.012).translateX(0.28).translateY(0.025));
      // coluna da frente + almofada do peito
      g.add(K.viga(V3(0.68, 0.05, 0), V3(0.68, 1.55, 0), 0.12));
      const peito = K.caixa(0.1, 0.4, 0.4, M.estofado, 0.04); peito.position.set(0.3, 1.3, 0); peito.rotation.z = -inc; g.add(peito);
      g.add(K.tubo(V3(0.68, 1.4, 0), V3(0.4, 1.34, 0), 0.03, M.quadro));
      for (const s of [-1, 1]) { g.add(K.tubo(V3(0.68, 1.12, s * 0.25), V3(0.4, 1.12, s * 0.25), 0.017, M.cromo)); g.add(K.tubo(V3(0.68, 1.12, s * 0.25), V3(0.68, 1.12, s * 0.06), 0.02, M.quadro)); }
      this.pivoG = V3(-0.06, 0.55, 0); PO.alavancaCena(this, g, 0.3);
      // o pivô fica no joelho (posição conferida na pose); apoio do eixo preso na coluna por trás
      g.add(K.tubo(V3(0.68, 0.55, 0.3), V3(-0.06, 0.55, 0.3), 0.018, M.quadro)); g.add(K.tubo(V3(0.68, 0.55, -0.3), V3(-0.06, 0.55, -0.3), 0.018, M.quadro));
    },
    pose(t) {
      zera();
      const inc = this.inc, kap = lerp(1.75, 0.02, t);
      emPe(V3(-0.04, ALT_QUADRIL - 0.012, 0), F0, inc * 0.75);
      gira("spine_02", EX, inc * 0.1); gira("spine_03", EX, inc * 0.08); gira("neck_01", EX, -inc * 0.55);
      B.pelvis.updateMatrixWorld(true);
      // perna de apoio (direita) no chão; perna de trabalho (esquerda) com o joelho que dobra
      const Hr = ondeEsta("thigh_r"); perna("r", V3(0.0, ALT_TORN, -0.0 + 0.13), F0.clone().add(V3(0, 0.15, 0.05))); pe("r", V3(1, 0, 0.15));
      const H = ondeEsta("thigh_l"), K1 = H.clone().add(V3(-Math.sin(0.04), -Math.cos(0.04), 0).multiplyScalar(COMP.thigh_l));
      const s = V3(-Math.sin(kap), -Math.cos(kap), 0), n = V3(-Math.cos(kap), Math.sin(kap), 0);
      const r = perna("l", K1.clone().add(s.clone().multiplyScalar(COMP.calf_l)), V3(1, 0.1, 0)); PO.peAr("l", r, 0.1);
      this.pivoAtual = K1;
      PO.alavancaPose(this, K1.clone().setZ(0), s, n, 0.37, 0.085);
      for (const l of ["l", "r"]) {
        const sz = l === "l" ? -1 : 1;
        agarra(l, { ponto: V3(0.5, 1.12, sz * 0.25), R: 0.017, eixo: V3(1, 0, 0), palma: V3(0, 0, -sz), polo: V3(-0.5, -1, sz * 0.5) });
      }
    },
  },
  // ---------- flexão nórdica ----------
  po_nordica: {
    nome: "Flexão nórdica",
    musc: { posterior: 1, gluteo: 0.45, lombar: 0.35, panturrilha: 0.4 },
    dica: "De joelhos com os tornozelos presos sob a barra. Tronco e coxa em uma linha só: desce o corpo o mais devagar que conseguir, só com o posterior segurando, e usa as mãos pra amortecer e voltar.",
    cam: { alvo: V3(0.28, 0.55, 0), dist: 3.7, yaw: 215, pitch: 12 },
    cena(g) {
      g.add(PO.piso());
      g.add(K.caixa(1.0, 0.04, 0.5, M.estofado, 0.018).translateX(-0.3).translateY(0.02));
      for (const s of [-1, 1]) { g.add(K.caixa(1.5, 0.03, 0.06, M.quadro, 0.01).translateX(-0.18).translateY(0.0).translateZ(s * 0.32)); g.add(K.viga(V3(-0.4, 0.02, s * 0.3), V3(-0.4, 0.2, s * 0.3), 0.06)); }
      g.add(K.caixa(0.08, 0.05, 0.7, M.quadro, 0.012).translateX(-0.4).translateY(0.0));
      const rol = PO.rolo(0.54, 0.04); rol.position.set(-0.4, 0.17, 0); g.add(rol);
      g.add(K.tubo(V3(-0.4, 0.17, -0.3), V3(-0.4, 0.17, 0.3), 0.012, M.cromo));
    },
    pose(t) {
      zera();
      const K0 = V3(0, 0.095, 0), be = lerp(0.0, 1.33, t * t * (3 - 2 * t) * 0.35 + t * 0.65);
      const cab = V3(Math.sin(be), Math.cos(be), 0), fr = V3(Math.cos(be), -Math.sin(be), 0);
      const pelv = K0.clone().add(cab.clone().multiplyScalar(COMP.thigh_l));
      corpoEm(pelv, cab, fr);
      gira("neck_01", EX, -0.3 - be * 0.15); gira("head", EX, -0.1);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) {
        const sz = l === "l" ? -1 : 1;
        const r = perna(l, V3(-COMP.calf_l, 0.088, sz * 0.12 + sz * 0.0), V3(1, -0.8, 0));
        PO.peOri(l, V3(-1, -0.04, 0), V3(0, -1, 0));
      }
      // mãos: à frente do peito no começo, no chão amortecendo no fim
      const w = sen(Math.min(1, Math.max(0, (t - 0.3) / 0.65)));
      for (const l of ["l", "r"]) {
        const sz = l === "l" ? -1 : 1, S = ondeEsta("upperarm_" + l);
        const alto = S.clone().add(fr.clone().multiplyScalar(0.3)).add(cab.clone().multiplyScalar(-0.12)).add(V3(0, 0, sz * 0.03));
        const chao = V3(S.x + 0.26, 0.05, sz * 0.23);
        const P = alto.clone().lerp(chao, w); P.y = Math.max(P.y, 0.05);
        braco(l, P, V3(-0.3, 0.8, sz * 0.9));
        const dir = cab.clone().lerp(V3(1, 0, 0), w).normalize(), pal = fr.clone().lerp(V3(0, -1, 0), w).normalize();
        mao(l, dir, pal);
      }
    },
  },
  // ---------- flexão de joelho na bola ----------
  po_flex_bola: {
    nome: "Flexão de joelho na bola",
    musc: { posterior: 1, gluteo: 0.55, lombar: 0.4, panturrilha: 0.35 },
    dica: "Deitado de barriga pra cima, calcanhares na bola e o quadril alto, em ponte. Puxa a bola pra perto do glúteo dobrando os joelhos sem deixar o quadril cair, e estica devagar mantendo o corpo em linha.",
    cam: { alvo: V3(0.3, 0.38, 0), dist: 3.6, yaw: 20, pitch: 8 },
    cena(g) { g.add(PO.piso()); const tp = K.colchonete(2.0, 0.7); tp.position.x = 0.4; g.add(tp); this.CX = -0.25; this.bola = K.bolaSuica(0.26); g.add(this.bola); },
    pose(t) {
      zera();
      const CX = this.CX, MAT = 0.02, C = V3(CX, MAT, 0), a = -0.62 - 0.03 * Math.sin(Math.PI * t);
      const { cab, fr, pos } = PO.pelveApoio(C, a, PO.D_COSTAS, PO.L_COSTAS);
      corpoEm(pos, cab, fr); gira("neck_01", EX, 0.2); B.pelvis.updateMatrixWorld(true);
      const dx = lerp(0.5, 0.875, t), Ay = 0.575;
      for (const l of ["l", "r"]) {
        const s = l === "l" ? -1 : 1, H = ondeEsta("thigh_" + l);
        const r = perna(l, V3(pos.x + dx, Ay, s * 0.12), V3(0, 1, s * 0.15)); PO.peAr(l, r, 0.35);
        const S = ondeEsta("upperarm_" + l);
        braco(l, V3(S.x + 0.46, MAT + 0.06, s * 0.32), V3(0, 1, s * 0.6)); mao(l, V3(1, 0, 0), V3(0, -1, 0));
      }
      this.bola.position.set(pos.x + dx - 0.015, 0.255, 0);
    },
  },
  // ---------- stiff unilateral (apoio na esquerda, halter na mão direita) ----------
  po_stiff_uni: {
    nome: "Stiff unilateral",
    musc: { posterior: 1, gluteo: 0.9, lombar: 0.6, antebraco: 0.3 },
    dica: "Apoio num pé só com o joelho levemente solto. Quadril pra trás, tronco desce e a perna livre sobe junto, tudo numa linha; coluna reta e quadril quadrado, sem abrir pro lado. Sobe apertando o glúteo.",
    cam: { alvo: V3(0.05, 0.75, 0), dist: 3.7, yaw: 235, pitch: 10 },
    cena(g) { g.add(PO.piso()); this.h = halter(1); g.add(this.h); },
    pose(t) {
      zera();
      const incl = lerp(0.04, 1.3, t);
      emPe(V3(-0.02, ALT_QUADRIL - 0.012 - 0.04 * t, 0), F0, incl * 0.75);
      gira("spine_02", EX, incl * 0.1); gira("spine_03", EX, incl * 0.08); gira("neck_01", EX, -incl * 0.5);
      B.pelvis.updateMatrixWorld(true);
      perna("l", V3(0.0, ALT_TORN, -0.12), V3(1, 0.15, -0.1)); pe("l", V3(1, 0, -0.1));
      const H = ondeEsta("thigh_r"), th = lerp(0.12, 1.4, t), R = lerp(0.78, 0.905, t);
      const r = perna("r", H.clone().add(V3(-Math.sin(th), -Math.cos(th), 0).multiplyScalar(R)), V3(1, 0.1, 0)); PO.peAr("r", r, 0.4);
      const S = ondeEsta("upperarm_r");
      agarra("r", { punho: S.clone().add(V3(0.0, -0.495, 0)), R: 0.016, eixo: F0.clone(), palma: V3(0, 0, 1), polo: V3(-1, 0, 0.3) });
      seguraHalter(this.h, "r");
      const Sl = ondeEsta("upperarm_l"); braco("l", Sl.clone().add(V3(0.0, -0.49, -0.05)), V3(-1, 0, -0.3));
    },
  },
  // ---------- good morning com barra ----------
  po_gm: {
    nome: "Good morning com barra",
    musc: { posterior: 1, gluteo: 0.8, lombar: 0.9, adutor: 0.4 },
    dica: "Barra apoiada no trapézio, joelho levemente solto. Empurra o quadril pra trás até o tronco ficar quase paralelo ao chão, coluna reta, e volta estendendo o quadril.",
    cam: { alvo: V3(0, 0.85, 0), dist: 4.3, yaw: 225, pitch: 10 },
    cena(g) { g.add(tablado()); this.bar = barra(2); g.add(this.bar); },
    pose(t) {
      zera();
      const ease = t * t * (3 - 2 * t), incl = 0.03 + ease * 1.5, recuo = 0.02 + ease * 0.34, alt = ALT_QUADRIL - 0.02 - ease * 0.06;
      emPe(V3(-recuo, alt, 0), F0, incl * 0.7);
      gira("spine_02", EX, incl * 0.1); gira("spine_03", EX, incl * 0.08); gira("neck_01", EX, -incl * 0.45); gira("head", EX, -incl * 0.1);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.14, fora: 0.2, poloFora: 0.25 });
      const c = quadroDe("spine_03"), pescoco = ondeEsta("neck_01");
      const bar = pescoco.clone().add(c.fr.clone().multiplyScalar(-0.1)).add(c.up.clone().multiplyScalar(-0.085));
      this.bar.position.copy(bar); this.bar.quaternion.setFromUnitVectors(EX, c.esq);
      for (const l of ["l", "r"]) {
        const s = l === "l" ? 1 : -1;
        agarra(l, { ponto: bar.clone().add(c.esq.clone().multiplyScalar(s * 0.36)), eixo: c.esq.clone().multiplyScalar(-s),
          palma: c.up.clone().add(c.fr.clone().multiplyScalar(0.9)),
          polo: c.up.clone().multiplyScalar(-1).add(c.fr.clone().multiplyScalar(-0.6)).add(c.esq.clone().multiplyScalar(s * 0.3)) });
      }
    },
  },
  // ---------- agachamento sumô com barra (usa o molde do agachamento com sumo) ----------
  po_sumo: {
    nome: "Agachamento sumô com barra",
    musc: { gluteo: 1, adutor: 0.85, quadriceps: 0.8, posterior: 0.5, lombar: 0.45 },
    dica: "Pés bem abertos com a ponta pra fora e a barra no trapézio. Desce com o joelho seguindo a linha do pé e o tronco mais ereto, e sobe empurrando o chão pra fora, apertando glúteo e parte interna da coxa.",
    cam: { alvo: V3(0, 0.85, 0), dist: 4.2, yaw: 225, pitch: 12 },
    cena(g) { MOLDES.agachamento.cena.call(this, g); },
    pose(t) { MOLDES.agachamento.pose.call(this, t); },
  },
  // ---------- kettlebell swing (movimento cíclico) ----------
  po_swing: {
    nome: "Kettlebell swing",
    musc: { gluteo: 1, posterior: 0.85, lombar: 0.5, antebraco: 0.4, quadriceps: 0.3 },
    dica: "Dobradiça de quadril, não agachamento: o kettlebell vai pra trás entre as coxas e o quadril explode pra frente, jogando o peso até a altura do peito. Braço é só corda; no alto, glúteo e abdômen travados.",
    cam: { alvo: V3(0.1, 0.9, 0), dist: 4.4, yaw: 40, pitch: 8 },
    fase(r) { const tau = (r / 1.9) % 1, t = 0.5 - 0.5 * Math.cos(2 * Math.PI * tau); return { t, f: tau < 0.5 ? "deixa o peso voltar" : "quadril explode", esforco: tau < 0.5 ? 0.45 : 0.75 + 0.25 * Math.sin(Math.PI * (tau - 0.5) * 2) }; },
    cena(g) { g.add(tablado()); this.kb = K.kettlebell(16); g.add(this.kb); },
    pose(t) {
      zera();
      const incl = lerp(0.03, 1.0, t), recuo = lerp(0.0, 0.26, t), alt = ALT_QUADRIL - 0.012 - t * 0.17;
      emPe(V3(-recuo, alt, 0), F0, incl * 0.7);
      gira("spine_02", EX, incl * 0.1); gira("spine_03", EX, incl * 0.08); gira("neck_01", EX, -incl * 0.45);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.2, fora: 0.45, poloFora: 0.5 });
      const S = ondeEsta("upperarm_l").add(ondeEsta("upperarm_r")).multiplyScalar(0.5), al = lerp(1.35, -0.5, t);
      const dir = V3(Math.sin(al), -Math.cos(al), 0), mid = S.clone().add(dir.clone().multiplyScalar(0.49));
      const r = 0.075 + 16 * 0.0015;
      this.kb.position.copy(mid).add(dir.clone().multiplyScalar(r * 1.37));
      const yw = dir.clone().negate(), xw = V3(0, 0, 1), zw = xw.clone().cross(yw);
      this.kb.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(xw, yw, zw));
      for (const l of ["l", "r"]) {
        const s = l === "l" ? -1 : 1;
        agarra(l, { ponto: mid.clone().add(V3(0, 0, s * 0.04)), R: 0.014, eixo: V3(0, 0, -s), palma: dir.clone(), polo: V3(-0.3, 0, s) });
      }
    },
  },
  // ---------- glúteo na polia baixa (coice) e coice com elástico ----------
  po_coice: {
    nome: "Glúteo na polia (coice)",
    musc: { gluteo: 1, posterior: 0.6, lombar: 0.3 },
    dica: "Tornozeleira presa na polia baixa, apoio firme na estrutura e tronco inclinado. Leva o calcanhar pra trás e pra cima com a perna quase esticada até sentir o glúteo apertar, sem arquear a lombar; volta controlando.",
    cam: { alvo: V3(0.2, 0.8, 0), dist: 4.0, yaw: 215, pitch: 8 },
    cena(g) {
      g.add(PO.piso()); const Tx = 0.8, el = !!this.p.elastico; this.Tx = Tx;
      if (!el) { this.torre = K.torre({ alt: 0.22 }); this.torre.g.position.set(Tx, 0, 0); this.torre.g.rotation.y = -Math.PI / 2; g.add(this.torre.g); this.torre.zeraCurso(); this.cuff = K.tornozeleira(); g.add(this.cuff); }
      else { g.add(K.viga(V3(Tx, 0.0, 0.0), V3(Tx, 1.5, 0), 0.1)); g.add(K.caixa(0.5, 0.04, 0.6, M.quadro, 0.01).translateX(Tx).translateY(0.02)); this.el = K.elastico(); g.add(this.el); this.cuff = K.tornozeleira(); g.add(this.cuff); const gan = new THREE.Mesh(new THREE.TorusGeometry(0.02, 0.006, 8, 16), M.aco); gan.position.set(Tx - 0.06, 0.4, 0); gan.rotation.y = Math.PI / 2; g.add(gan); }
      const rx = Tx - 0.14; g.add(K.tubo(V3(rx, 1.05, -0.2), V3(rx, 1.05, 0.2), 0.017, M.cromo));
      for (const s of [-1, 1]) g.add(K.tubo(V3(rx, 1.05, s * 0.2), V3(Tx - 0.03, 1.05, s * 0.2), 0.02, M.quadro));
    },
    pose(t) {
      zera();
      const inc = 0.5;
      emPe(V3(-0.2, ALT_QUADRIL - 0.025, 0), F0, inc * 0.75);
      gira("spine_02", EX, inc * 0.1); gira("spine_03", EX, inc * 0.08); gira("neck_01", EX, -inc * 0.55);
      B.pelvis.updateMatrixWorld(true);
      perna("r", V3(-0.12, ALT_TORN, 0.13), V3(1, 0.1, 0.05)); pe("r", V3(1, 0, 0.12));
      const H = ondeEsta("thigh_l"), th = lerp(-0.55, 0.12, t), R = lerp(0.9, 0.83, t);
      const A = H.clone().add(V3(Math.sin(th), -Math.cos(th), 0).multiplyScalar(R));
      const r = perna("l", A, V3(1, 0.3, 0)); PO.peAr("l", r, 0.45);
      const sd = r.alvo.clone().sub(r.E).normalize(), cp = r.E.clone().lerp(r.alvo, 0.88);
      this.cuff.position.copy(cp); this.cuff.quaternion.setFromUnitVectors(EY, sd);
      if (this.torre) this.torre.liga(cp); else K.poe(this.el, V3(this.Tx - 0.06, 0.4, 0), cp);
      const rx = this.Tx - 0.14;
      for (const l of ["l", "r"]) {
        const sz = l === "l" ? -1 : 1;
        agarra(l, { ponto: V3(rx, 1.05, sz * 0.18), R: 0.017, eixo: V3(0, 0, -sz), palma: V3(0.3, -1, 0), polo: V3(-0.3, 0.7, sz) });
      }
    },
  },
  // ---------- glúteo na máquina (coice) ----------
  po_coice_maq: {
    nome: "Glúteo na máquina (coice)",
    musc: { gluteo: 1, posterior: 0.55, lombar: 0.3 },
    dica: "Peito na almofada, mãos nos pegadores e o pé da perna de trabalho no apoio. Empurra o pedal pra trás e pra cima com o glúteo, perna quase esticada, e volta devagar sem perder a posição do tronco.",
    cam: { alvo: V3(0.15, 0.75, 0), dist: 4.0, yaw: 215, pitch: 8 },
    cena(g) {
      g.add(PO.piso()); const inc = 0.5; this.inc = inc;
      g.add(K.caixa(0.7, 0.05, 0.7, M.quadro, 0.012).translateX(0.35).translateY(0.025));
      g.add(K.viga(V3(0.72, 0.05, 0), V3(0.72, 1.55, 0), 0.12));
      const peito = K.caixa(0.1, 0.4, 0.4, M.estofado, 0.04); peito.position.set(0.37, 1.28, 0); peito.rotation.z = -inc; g.add(peito);
      g.add(K.tubo(V3(0.72, 1.35, 0), V3(0.45, 1.3, 0), 0.03, M.quadro));
      for (const s of [-1, 1]) { g.add(K.tubo(V3(0.72, 1.1, s * 0.25), V3(0.46, 1.1, s * 0.25), 0.017, M.cromo)); g.add(K.tubo(V3(0.72, 1.1, s * 0.25), V3(0.72, 1.1, 0.0), 0.02, M.quadro)); }
      this.braco = K.tubo(V3(), V3(0, 1, 0), 0.022, M.quadro); g.add(this.braco);
      this.braco2 = K.tubo(V3(), V3(0, 1, 0), 0.022, M.quadro); g.add(this.braco2);
      this.pedal = K.caixa(0.3, 0.025, 0.26, M.aco, 0.008); g.add(this.pedal);
      this.pa = [0, 1].map(() => { const a = PO.anilhaZ(0.14, 0.034); g.add(a); return a; });
      const pv = K.cilU(0.03, M.cromo); pv.scale.y = 0.1; pv.rotation.x = Math.PI / 2; g.add(pv); this.pv = pv;
    },
    pose(t) {
      zera();
      const inc = this.inc;
      emPe(V3(-0.2, ALT_QUADRIL - 0.025, 0), F0, inc * 0.75);
      gira("spine_02", EX, inc * 0.1); gira("spine_03", EX, inc * 0.08); gira("neck_01", EX, -inc * 0.55);
      B.pelvis.updateMatrixWorld(true);
      perna("r", V3(-0.12, ALT_TORN, 0.13), V3(1, 0.1, 0.05)); pe("r", V3(1, 0, 0.12));
      const H = ondeEsta("thigh_l"), th = lerp(-0.6, 0.12, t), R = lerp(0.9, 0.84, t);
      const dL = V3(Math.sin(th), -Math.cos(th), 0), A = H.clone().add(dL.clone().multiplyScalar(R));
      const r = perna("l", A, V3(1, 0.3, 0)); PO.peAr("l", r, 0.3);
      const d = r.alvo.clone().sub(r.E).normalize(), h = r.dob, ft = d.clone().multiplyScalar(Math.cos(PO.ANG_PE - 0.3)).add(d.clone().cross(h).multiplyScalar(Math.sin(PO.ANG_PE - 0.3)));
      const sole = ft.clone().cross(h).negate().normalize();
      const pc = A.clone().add(sole.clone().multiplyScalar(0.045)).add(ft.clone().multiplyScalar(0.07));
      this.pedal.position.copy(pc); this.pedal.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(ft, sole, ft.clone().cross(sole)));
      const P = V3(H.x - 0.0, H.y, -0.32), Q = pc.clone().setZ(-0.32);
      this.pv.position.copy(P);
      K.poe(this.braco, P, Q); K.poe(this.braco2, Q, pc.clone().setZ(-0.12));
      this.pa.forEach((a, k) => a.position.copy(Q.clone().add(Q.clone().sub(P).normalize().multiplyScalar(0.12)).setZ(-0.4 - 0.045 * k)));
      for (const l of ["l", "r"]) {
        const sz = l === "l" ? -1 : 1;
        agarra(l, { ponto: V3(0.55, 1.1, sz * 0.25), R: 0.017, eixo: V3(1, 0, 0), palma: V3(0, 0, -sz), polo: V3(-0.5, -1, sz * 0.5) });
      }
    },
  },
  // ---------- glúteo em 4 apoios com caneleira (coice com joelho a 90°) ----------
  po_4apoios: {
    nome: "Glúteo 4 apoios com caneleira",
    musc: { gluteo: 1, posterior: 0.55, lombar: 0.3, abdomen: 0.3 },
    dica: "Mãos sob os ombros e joelhos sob o quadril, coluna reta. Com o joelho a 90°, empurra a sola do pé pro teto até a coxa ficar na linha do tronco, sem girar o quadril nem arquear a lombar.",
    cam: { alvo: V3(0.3, 0.45, 0), dist: 3.6, yaw: 215, pitch: 12 },
    cena(g) { g.add(PO.piso()); const m = K.colchonete(1.9, 0.8); m.position.x = 0.2; g.add(m); this.cn = K.caneleira(); g.add(this.cn); },
    pose(t) {
      zera();
      const K0 = 0.065 + 0.02, th = lerp(1.62, 0.02, t);
      corpoEm(V3(0, K0 + COMP.thigh_l, 0), V3(1, 0, 0), V3(0, -1, 0));
      gira("neck_01", EX, -0.35); gira("head", EX, -0.1);
      B.pelvis.updateMatrixWorld(true);
      // apoio: joelho direito no colchonete
      const rA = perna("r", V3(-COMP.calf_l, 0.1, 0.12), V3(1, -0.8, 0)); PO.peOri("r", V3(-1, -0.04, 0), V3(0, -1, 0));
      const H = ondeEsta("thigh_l"), td = V3(-Math.sin(th), -Math.cos(th), 0), K1 = H.clone().add(td.clone().multiplyScalar(COMP.thigh_l));
      const sd = V3(-Math.cos(th), Math.sin(th), 0), A = K1.clone().add(sd.clone().multiplyScalar(COMP.calf_l));
      const r = perna("l", A, K1.clone().sub(H.clone().add(A).multiplyScalar(0.5)).add(V3(0, 0, 0))); PO.peAr("l", r, -0.1);
      const cp = K1.clone().add(sd.clone().multiplyScalar(COMP.calf_l * 0.86));
      this.cn.position.copy(cp); this.cn.quaternion.setFromUnitVectors(EY, sd);
      for (const l of ["l", "r"]) {
        const sz = l === "l" ? -1 : 1, S = ondeEsta("upperarm_" + l);
        braco(l, V3(S.x + 0.02, 0.1, sz * 0.2), V3(-0.3, 0.2, sz)); mao(l, V3(1, 0, 0), V3(0, -1, 0));
      }
    },
  },
  // ---------- abdução na polia (de lado pra torre) ----------
  po_abd_polia: {
    nome: "Abdução na polia",
    musc: { gluteo: 1, adutor: 0.2 },
    dica: "De lado pra polia, tornozeleira na perna de fora e uma mão no apoio. Leva a perna pro lado com o joelho esticado e a ponta do pé pra frente, sem inclinar o tronco, e volta controlando sem encostar na outra.",
    cam: { alvo: V3(0.1, 0.75, 0), dist: 4.2, yaw: 285, pitch: 8 },
    cena(g) {
      g.add(PO.piso()); this.torre = K.torre({ alt: 0.22 }); this.torre.g.position.set(0.45, 0, -1.3); g.add(this.torre.g); this.torre.zeraCurso();
      this.cuff = K.tornozeleira(); g.add(this.cuff);
      g.add(K.viga(V3(0.25, 0.0, -0.45), V3(0.25, 1.3, -0.45), 0.06)); g.add(K.caixa(0.4, 0.04, 0.4, M.quadro, 0.01).translateX(0.25).translateZ(-0.45).translateY(0.02));
      g.add(K.caixa(0.1, 0.05, 0.9, M.quadro, 0.012).translateX(0.25).translateY(0.02).translateZ(-0.85));
    },
    pose(t) {
      zera();
      emPe(V3(0, ALT_QUADRIL - 0.015, 0), F0, 0.03);
      B.pelvis.updateMatrixWorld(true);
      perna("l", V3(0.0, ALT_TORN, -0.12), V3(1, 0.1, 0)); pe("l", V3(1, 0, -0.05));
      const H = ondeEsta("thigh_r"), ro = lerp(0.62, 0.0, t);
      const A = H.clone().add(V3(0, -Math.cos(ro), Math.sin(ro)).multiplyScalar(0.9));
      const r = perna("r", A, V3(1, 0, 0)); PO.peAr("r", r, 0.0);
      const sd = r.alvo.clone().sub(r.E).normalize(), cp = r.E.clone().lerp(r.alvo, 0.88);
      this.cuff.position.copy(cp); this.cuff.quaternion.setFromUnitVectors(EY, sd); this.torre.liga(cp);
      agarra("l", { ponto: V3(0.25, 1.12, -0.45), R: 0.03, eixo: V3(0, 1, 0), palma: V3(0, 0, 1), polo: V3(-0.5, -0.5, -1) });
      const Sr = ondeEsta("upperarm_r"); braco("r", H.clone().add(V3(0.0, 0.1, 0.12)), V3(-1, 0, 0.6));
    },
  },
  // ---------- pull-through na polia ----------
  po_pullthrough: {
    nome: "Pull-through na polia",
    musc: { gluteo: 1, posterior: 0.85, lombar: 0.4 },
    dica: "De costas pra polia, corda passando entre as pernas. Empurra o quadril pra trás com os braços soltos e a coluna reta até sentir o posterior alongar, depois estende o quadril apertando o glúteo.",
    cam: { alvo: V3(-0.1, 0.8, 0), dist: 4.2, yaw: 40, pitch: 8 },
    cena(g) {
      g.add(PO.piso()); this.torre = K.torre({ alt: 0.2 }); this.torre.g.position.set(-1.3, 0, 0); this.torre.g.rotation.y = Math.PI / 2; g.add(this.torre.g); this.torre.zeraCurso();
      this.corda = K.corda(); g.add(this.corda);
    },
    pose(t) {
      zera();
      const e = t * t * (3 - 2 * t), incl = lerp(0.04, 1.1, e), recuo = 0.04 + e * 0.3, alt = ALT_QUADRIL - 0.015 - e * 0.1;
      emPe(V3(-recuo, alt, 0), F0, incl * 0.7);
      gira("spine_02", EX, incl * 0.1); gira("spine_03", EX, incl * 0.08); gira("neck_01", EX, -incl * 0.5);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.2, fora: 0.3, poloFora: 0.45 });
      const pel = ondeEsta("pelvis"), hm = V3(pel.x + 0.13, lerp(pel.y - 0.2, pel.y - 0.3, e), 0);
      const sa = this.torre.saida(), dT = sa.clone().sub(hm).normalize(), top = hm.clone().add(dT.clone().multiplyScalar(0.22));
      this.corda.position.copy(top.clone().sub(dT.clone().multiplyScalar(0.04))); this.corda.quaternion.setFromUnitVectors(EY, dT); this.corda.updateMatrixWorld(true);
      const pts = [-1, 1].map((s) => hm.clone().add(V3(0, 0, s * 0.045)));
      this.corda.userData.abre(pts[0], pts[1]); this.torre.liga(top);
      ["l", "r"].forEach((l, i) => {
        const sz = l === "l" ? -1 : 1;
        agarra(l, { ponto: V3(hm.x, hm.y, sz * 0.045), R: 0.014, eixo: F0.clone(), palma: V3(0, 0, -sz), polo: V3(-0.4, 0, sz) });
      });
    },
  },
  // ---------- cadeira abdutora / adutora ----------
  po_abdutora: {
    nome: "Cadeira abdutora",
    musc: { gluteo: 1, adutor: 0.3 },
    dica: "Sentado com as costas coladas no encosto e as almofadas por fora dos joelhos. Abre as pernas empurrando as almofadas sem tirar o quadril do assento, segura um instante e volta devagar sem deixar a carga bater.",
    cam: { alvo: V3(0.3, 0.6, 0), dist: 3.6, yaw: 120, pitch: 22 },
    cena(g) {
      const ST = 0.46, r = 0.17, Py = ST + 0.1; this.ST = ST; this.pelv = V3(0, Py, 0); this.r = r; g.add(PO.piso());
      g.add(K.caixa(0.5, 0.09, 0.44, M.estofado, 0.035).translateX(0.05).translateY(ST - 0.045));
      g.add(K.viga(V3(-0.05, 0.05, 0), V3(-0.05, ST - 0.09, 0), 0.14)); g.add(K.caixa(0.9, 0.05, 0.6, M.quadro, 0.012).translateX(0.05).translateY(0.025));
      const enc = K.caixa(0.1, 0.62, 0.42, M.estofado, 0.04); enc.position.set(-0.2 - Math.sin(r) * 0.14, ST + 0.42, 0); enc.rotation.z = r; g.add(enc);
      g.add(K.viga(V3(-0.36, 0.05, 0), V3(-0.3, ST + 0.55, 0), 0.07));
      g.add(K.caixa(0.5, 0.07, 1.2, M.quadro, 0.012).translateX(0.45).translateY(0.035));
      g.add(K.caixa(0.5, 0.02, 1.2, M.borracha, 0.006).translateX(0.45).translateY(0.075));
      const Hy = Py + 0.3;
      this.pads = [-1, 1].map((s) => { const p = K.caixa(0.08, 0.26, 0.15, M.estofado, 0.03); g.add(p); return p; });
      this.arms = [-1, 1].map((s) => [0, 1].map(() => { const a = K.tubo(V3(), V3(0, 1, 0), 0.02, M.quadro); g.add(a); return a; }));
      for (const s of [-1, 1]) {
        g.add(K.viga(V3(-0.05, 0.05, s * 0.4), V3(-0.05, Hy, s * 0.4), 0.07)); g.add(K.caixa(0.1, 0.05, 0.14, M.quadro, 0.012).translateX(-0.05).translateY(0.025).translateZ(s * 0.4));
        g.add(K.tubo(V3(-0.1, Py + 0.2, s * 0.28), V3(0.12, Py + 0.2, s * 0.28), 0.017, M.cromo)); g.add(K.tubo(V3(-0.1, ST, s * 0.28), V3(-0.1, Py + 0.2, s * 0.28), 0.02, M.quadro));
      }
      g.add(PO.pilhaCaixa(-0.75, 0, Math.PI / 2));
    },
    pose(t) {
      zera();
      const ad = !!this.p.adutora, r = this.r, Py = this.pelv.y, ab = 0.72, fe = 0.2, phi = ad ? lerp(fe, ab, t) : lerp(ab, fe, t);
      corpoEm(this.pelv, V3(-Math.sin(r), Math.cos(r), 0), V3(Math.cos(r), Math.sin(r), 0));
      gira("neck_01", EX, 0.0);
      B.pelvis.updateMatrixWorld(true);
      const Hy = Py + 0.3;
      for (const l of ["l", "r"]) {
        const sz = l === "l" ? -1 : 1, i = l === "l" ? 0 : 1, H = ondeEsta("thigh_" + l);
        const d = V3(Math.cos(phi), 0.02, sz * Math.sin(phi)).normalize(), K1 = H.clone().add(d.clone().multiplyScalar(COMP.thigh_l));
        perna(l, V3(K1.x - 0.03, ALT_TORN + 0.075, K1.z + sz * 0.03), V3(0, 1, 0)); pe(l, V3(1, 0, sz * 0.35));
        let out = V3(-d.z, 0, d.x); if (out.dot(V3(0, 0, sz)) < 0) out.negate();
        const dz = out.clone().multiplyScalar(ad ? -1 : 1), pc = H.clone().add(d.clone().multiplyScalar(0.36)).add(dz.clone().multiplyScalar(0.13));
        this.pads[i].position.copy(pc); this.pads[i].rotation.set(0, Math.atan2(-dz.z, dz.x), 0);
        const post = V3(-0.05, ad ? Hy : pc.y, sz * 0.4);
        if (!ad) { K.poe(this.arms[i][0], pc.clone().add(dz.clone().multiplyScalar(0.04)), post); K.poe(this.arms[i][1], post, post.clone().add(V3(0, 0.001, 0))); }
        else { const up = V3(pc.x, Hy, pc.z); K.poe(this.arms[i][0], pc.clone().add(V3(0, 0.12, 0)), up); K.poe(this.arms[i][1], up, post); }
        agarra(l, { ponto: V3(0.12, Py + 0.2, sz * 0.28), R: 0.017, eixo: V3(1, 0, 0), palma: V3(0, 0, -sz), polo: V3(-0.6, -0.4, sz) });
      }
    },
  },
  // ---------- abdução deitado de lado com caneleira ----------
  po_abd_deit: {
    nome: "Abdução deitado com caneleira",
    musc: { gluteo: 1, adutor: 0.15 },
    dica: "Deitado de lado, perna de baixo dobrada pra firmar. Com a de cima esticada e a ponta do pé pra frente, sobe até uns 40° sem girar o quadril pra trás e desce devagar sem encostar na outra.",
    cam: { alvo: V3(0.2, 0.3, 0), dist: 3.5, yaw: 25, pitch: 20 },
    cena(g) { g.add(PO.piso()); const m = K.colchonete(2.1, 0.9); m.position.x = 0.2; g.add(m); this.cn = K.caneleira(); g.add(this.cn); },
    pose(t) {
      zera();
      const ro = lerp(0.72, 0.03, t), pelv = V3(0.0, 0.19, 0);
      corpoEm(pelv, V3(-1, 0, 0), V3(0, 0, -1));
      gira("neck_01", EX, 0.0); B.pelvis.updateMatrixWorld(true);
      // perna de baixo (esquerda): quadril a 45° e joelho a 90°, joelho pra frente
      const Hl = ondeEsta("thigh_l");
      const rl = perna("l", Hl.clone().add(V3(0.65, -0.0, -0.05)), V3(0, 0, -1)); PO.peAr("l", rl, 0.2);
      // perna de cima (direita): esticada, abre pra cima
      const Hr = ondeEsta("thigh_r"), A = Hr.clone().add(V3(Math.cos(ro), Math.sin(ro), -0.03).normalize().multiplyScalar(0.9));
      const rr = perna("r", A, V3(0, 0, -1)); PO.peAr("r", rr, 0.0);
      const sd = rr.alvo.clone().sub(rr.E).normalize(); this.cn.position.copy(rr.E.clone().lerp(rr.alvo, 0.86)); this.cn.quaternion.setFromUnitVectors(EY, sd);
      // braço de baixo sob a cabeça, de cima apoiado no chão à frente
      const Sl = ondeEsta("upperarm_l"), hd = ondeEsta("head");
      braco("l", hd.clone().add(V3(-0.05, -0.1, -0.02)), V3(0, 0.5, -1));
      const Sr = ondeEsta("upperarm_r"); braco("r", V3(Sr.x + 0.12, 0.05, -0.33), V3(0, 1, 0.3)); mao("r", V3(1, 0, 0), V3(0, -1, 0));
    },
  },
  // ---------- monster walk (passo lateral com elástico nos tornozelos) ----------
  po_monster: {
    nome: "Abdução com elástico (monster walk)",
    musc: { gluteo: 1, adutor: 0.2, quadriceps: 0.4 },
    dica: "Elástico nos tornozelos, joelhos semi-flexionados e tronco um pouco à frente. Dá passos largos de lado sem juntar os pés, mantendo tensão no elástico e o joelho alinhado com o pé o tempo todo.",
    cam: { alvo: V3(0.0, 0.75, 0.1), dist: 3.9, yaw: 255, pitch: 8 },
    fase(r) { const u = (r / 5) % 1; return { t: u, f: "passo lateral, elástico sempre esticado", esforco: 0.75 }; },
    cena(g) { g.add(PO.piso()); this.el = K.elastico(); g.add(this.el); },
    pose(u) {
      zera();
      const seg = Math.min(3, Math.floor(u * 4)), x = u * 4 - seg, e = sen(x), lift = Math.sin(Math.PI * x) * 0.07;
      let zl = -0.15, zr = 0.15, ll = 0, lr = 0;
      if (seg === 0) { zr = lerp(0.15, 0.35, e); lr = lift; }
      else if (seg === 1) { zr = 0.35; zl = lerp(-0.15, 0.05, e); ll = lift; }
      else if (seg === 2) { zr = 0.35; zl = lerp(0.05, -0.15, e); ll = lift; }
      else { zl = -0.15; zr = lerp(0.35, 0.15, e); lr = lift; }
      const zc = (zl + zr) / 2, inc = 0.32;
      emPe(V3(-0.1, ALT_QUADRIL - 0.17, zc - 0.0), F0, inc * 0.7);
      gira("spine_02", EX, inc * 0.1); gira("spine_03", EX, inc * 0.08); gira("neck_01", EX, -inc * 0.5);
      B.pelvis.updateMatrixWorld(true);
      const al = V3(0, ALT_TORN + ll, zl), ar = V3(0, ALT_TORN + lr, zr);
      perna("l", al, V3(1, 0.1, -0.35)); pe("l", V3(1, 0, -0.35)); perna("r", ar, V3(1, 0.1, 0.35)); pe("r", V3(1, 0, 0.35));
      K.poe(this.el, al.clone().add(V3(0, 0.035, 0)), ar.clone().add(V3(0, 0.035, 0)));
      for (const l of ["l", "r"]) {
        const sz = l === "l" ? -1 : 1, S = ondeEsta("upperarm_" + l);
        braco(l, S.clone().add(V3(0.3, -0.17, -sz * 0.08)), V3(-0.4, -0.5, sz)); fecha(l, 0.8);
      }
    },
  },
  // ===FIM-MOLDES===
});
// Intensidade relativa (1 = quem mais trabalha no exercício). Fontes CONFERIDAS na hora (resumo/abstract abertos):
//  Contreras 2015 (J Appl Biomech 31:452): hip thrust > agachamento; glúteo máx. superior ~70%, inferior ~87%, bíceps femoral ~41% CIVM.
//  McAllister 2014 (JSCR 28:105): isquios maximizados no terra romeno e glute-ham raise; mesa flexora também alta; good morning abaixo.
//  McCurdy 2018 (JSCR 32:594): stiff unilateral glúteo máx. 40,5% vs posterior 29,9% CIVM (glúteo/posterior ~1,35).
//  Distefano 2009 (JOSPT 39:532): abdução deitado de lado glúteo médio 81% / glúteo máx. 39% CIVM.
//  Boren 2011 (IJSPT 6:206): prancha lateral com abdução e agachamento unilateral >70% nos dois glúteos; prancha frontal com extensão de quadril: glúteo máx. 106%.
//  NÃO conferidos (valor de biomecânica, "estimativa"): flexão nórdica, flexora em pé/sentada, kettlebell swing (McGill 2012 não aberto),
//  good morning (Vigotsky 2015 não aberto), cadeira abdutora/adutora, monster walk, polia/máquina/elástico, pull-through, sumô, frog pump.
Object.assign(FOCOS, {
  po_ht: (p) => p.uni ? [["gluteo_max", 1], ["gluteo_med", 0.6], ["isquio", 0.5], ["adutores", 0.35], ["vasto_lateral", 0.35], ["lombar", 0.2]]
    : [["gluteo_max", 1], ["isquio", 0.5], ["adutores", 0.4], ["vasto_lateral", 0.4], ["gluteo_med", 0.4], ["reto_femoral", 0.3]], // Contreras 2015 (isquio ~41/87)
  po_ht_maq: () => [["gluteo_max", 1], ["isquio", 0.45], ["adutores", 0.4], ["vasto_lateral", 0.4], ["gluteo_med", 0.4], ["reto_femoral", 0.3]], // estimativa = hip thrust
  po_ponte: (p) => p.frog ? [["gluteo_max", 1], ["adutores", 0.6], ["gluteo_med", 0.45], ["isquio", 0.3], ["vasto_medial", 0.25]] // estimativa
    : [["gluteo_max", 1], ["isquio", 0.55], ["vasto_lateral", 0.4], ["adutores", 0.35], ["gluteo_med", 0.35], ["lombar", 0.2]], // estimativa (ponte < hip thrust)
  po_flex_deit: () => [["isquio", 1], ["panturrilha", 0.55], ["gluteo_max", 0.25], ["lombar", 0.15]], // McAllister 2014 + estimativa (gastrocnêmio ajuda a flexionar o joelho)
  po_flex_sent: () => [["isquio", 1], ["panturrilha", 0.55], ["gluteo_max", 0.15], ["adutores", 0.15]], // estimativa
  po_flex_pe: () => [["isquio", 1], ["panturrilha", 0.55], ["gluteo_max", 0.35], ["lombar", 0.2], ["abdomen", 0.15]], // estimativa
  po_nordica: () => [["isquio", 1], ["gluteo_max", 0.45], ["panturrilha", 0.4], ["lombar", 0.35], ["abdomen", 0.3]], // estimativa
  po_flex_bola: () => [["isquio", 1], ["gluteo_max", 0.6], ["panturrilha", 0.4], ["lombar", 0.4], ["abdomen", 0.2]], // estimativa
  po_stiff_uni: () => [["gluteo_max", 1], ["isquio", 0.75], ["gluteo_med", 0.6], ["lombar", 0.6], ["adutores", 0.3], ["antebraco", 0.25]], // McCurdy 2018 (glúteo 40,5 / posterior 29,9) + estimativa
  po_gm: () => [["isquio", 1], ["lombar", 0.9], ["gluteo_max", 0.8], ["adutores", 0.45], ["trapezio_sup", 0.3]], // McAllister 2014 (good morning < terra romeno) + estimativa
  po_swing: () => [["gluteo_max", 1], ["isquio", 0.85], ["lombar", 0.5], ["vasto_lateral", 0.35], ["antebraco", 0.4], ["abdomen", 0.3]], // estimativa
  po_sumo: () => [["gluteo_max", 1], ["adutores", 0.85], ["vasto_lateral", 0.8], ["vasto_medial", 0.8], ["isquio", 0.4], ["lombar", 0.4], ["gluteo_med", 0.4]], // estimativa (Escamilla 2002 p/ vastos)
  po_coice: (p) => p.elastico ? [["gluteo_max", 1], ["isquio", 0.5], ["gluteo_med", 0.4], ["lombar", 0.25]] : [["gluteo_max", 1], ["isquio", 0.55], ["gluteo_med", 0.4], ["lombar", 0.25]], // estimativa
  po_coice_maq: () => [["gluteo_max", 1], ["isquio", 0.5], ["gluteo_med", 0.35], ["lombar", 0.2]], // estimativa
  po_4apoios: () => [["gluteo_max", 1], ["isquio", 0.5], ["gluteo_med", 0.35], ["lombar", 0.3], ["abdomen", 0.3]], // estimativa (Boren 2011: extensão de quadril em apoio alto, glúteo máx. 106%)
  po_abd_polia: () => [["gluteo_med", 1], ["gluteo_max", 0.5], ["adutores", 0.15], ["abdomen", 0.2]], // Distefano 2009 (81/39) por analogia
  po_pullthrough: () => [["gluteo_max", 1], ["isquio", 0.85], ["lombar", 0.4], ["adutores", 0.3], ["antebraco", 0.2]], // estimativa
  po_abdutora: (p) => p.adutora ? [["adutores", 1], ["gluteo_max", 0.15], ["reto_femoral", 0.15], ["abdomen", 0.1]] // estimativa
    : [["gluteo_med", 1], ["gluteo_max", 0.6], ["adutores", 0.1], ["reto_femoral", 0.1]], // estimativa
  po_abd_deit: () => [["gluteo_med", 1], ["gluteo_max", 0.48], ["adutores", 0.12], ["abdomen", 0.2]], // Distefano 2009: 81% vs 39%
  po_monster: () => [["gluteo_med", 1], ["gluteo_max", 0.65], ["vasto_lateral", 0.4], ["adutores", 0.2], ["panturrilha", 0.2]], // estimativa (Boren 2011/Distefano p/ band walk não conferidos)
});
Object.assign(VISTA, { po_ht: 40, po_ht_maq: 42, po_ponte: 50, po_flex_deit: 40, po_flex_sent: 10, po_flex_pe: 220, po_nordica: 215, po_flex_bola: 20, po_stiff_uni: 235,
  po_gm: 225, po_sumo: 225, po_swing: 230, po_coice: 215, po_coice_maq: 215, po_4apoios: 215, po_abd_polia: 285, po_pullthrough: 330, po_abdutora: (p) => p.adutora ? 100 : 25, po_abd_deit: 25, po_monster: 255 });
}

// ===== moldes/quadriceps.js =====
{ // moldes/quadriceps.js — grupo Quadríceps (prefixo qu_)
const QU_L = COMP.thigh_l + COMP.calf_l;
const quLerp = (a, b, k) => a + (b - a) * k;
const quSl = (l) => (l === "l" ? 1 : -1);
const quClamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const quSuave = (x) => { const k = quClamp(x); return k * k * (3 - 2 * k); };
const QU_BOLA_Y = ALT_TORN + COMP.foot_l * DIR.foot_l.y; // altura da bola do pé com a sola no chão
// altura do quadril (articulação da coxa) pra perna ficar a `ext` esticada com o tornozelo a dh de distância na horizontal
const quAltTopo = (dh = 0, ext = 0.965) => ALT_TORN + 0.026 + Math.sqrt(Math.max(0, (QU_L * ext) ** 2 - dh * dh));

// pé com a sola paralela a um plano (normal n pra quem pisa); dedos apontando pra u (no plano); rot = abertura da ponta (rad)
function quPeNoPlano(l, n, u, rot = 0, inclina = null) {
  const nn = n.clone().normalize(), uu = u.clone().sub(nn.clone().multiplyScalar(u.dot(nn))).normalize().applyAxisAngle(nn, rot);
  const h = Math.hypot(DIR["foot_" + l].x, DIR["foot_" + l].z), dy = inclina === null ? DIR["foot_" + l].y : inclina;
  const d = uu.clone().multiplyScalar(h).add(nn.clone().multiplyScalar(dy)).normalize();
  mira("foot_" + l, d, nn.clone().cross(d).normalize(), EX);
  return d;
}
// tornozelo sobre um ponto de um plano (normal n)
const quTorn = (P, n) => P.clone().add(n.clone().normalize().multiplyScalar(ALT_TORN));

// ---------- agachamentos de pé (frontal, Smith, goblet, sumô com halter, com salto) ----------
// c = { alt0, alt1: altura da pelve em pé / embaixo; rc0, rc1: pelve pra trás; in0, in1: inclinação; abre, fora, polo: base; px: pés pra frente }
function quAgachaTronco(t, c, x0 = 0) {
  const alt = c.alt0 - t * (c.alt0 - c.alt1), recuo = c.rc0 + t * (c.rc1 - c.rc0), incl = c.in0 + t * (c.in1 - c.in0);
  emPe(V3(x0 - recuo, alt, 0), F0, incl * 0.55);
  gira("spine_01", EX, incl * 0.12); gira("spine_02", EX, incl * 0.12); gira("spine_03", EX, incl * 0.08);
  gira("neck_01", EX, -incl * 0.45); gira("head", EX, -incl * 0.15);
  B.pelvis.updateMatrixWorld(true);
  return incl;
}
function quAgachaPernas(c, solo = 0) {
  pernas(F0, { abre: c.abre, fora: c.fora, poloFora: c.polo, origem: V3(c.px || 0, solo, 0) });
}
// halter na vertical, comprido o bastante pras duas mãos (cabo 0,2 m)
function quHalterV(kg = 1.2) {
  const g = new THREE.Group(), cab = cil(0.016, 0.21, M.aco); g.add(cab);
  for (const s of [-1, 1]) { const c = cil(0.07 + kg * 0.01, 0.06, M.borracha, 6); c.position.y = s * 0.135; g.add(c); }
  return sombreia(g);
}

const QU_AGA = {
  frontal: { alt0: ALT_QUADRIL - 0.03, alt1: 0.47, rc0: 0.03, rc1: 0.14, in0: 0.04, in1: 0.4, abre: 0.17, fora: 0.36, polo: 0.5 },
  smith: { alt0: ALT_QUADRIL - 0.03, alt1: 0.5, rc0: 0.0, rc1: 0.0, in0: 0.04, in1: 0.3, abre: 0.17, fora: 0.36, polo: 0.5, px: 0.22 },
  goblet: { alt0: ALT_QUADRIL - 0.03, alt1: 0.43, rc0: 0.03, rc1: 0.12, in0: 0.04, in1: 0.3, abre: 0.2, fora: 0.55, polo: 0.85 },
  sumo: { alt0: ALT_QUADRIL - 0.03, alt1: 0.53, rc0: 0.02, rc1: 0.08, in0: 0.04, in1: 0.28, abre: 0.31, fora: 0.75, polo: 1.0 },
  salto: { alt0: ALT_QUADRIL - 0.03, alt1: 0.55, rc0: 0.03, rc1: 0.22, in0: 0.05, in1: 0.55, abre: 0.17, fora: 0.3, polo: 0.4 },
};

Object.assign(MOLDES, {
  qu_agacha: {
    nome: "Agachamento",
    musc: { quadriceps: 1, gluteo: 0.8, adutor: 0.5, lombar: 0.4, posterior: 0.3 },
    dica: "Pés na largura dos ombros, calcanhar no chão, joelho na linha do pé. Desce até a coxa passar da paralela e sobe empurrando o chão.",
    cam: { alvo: V3(0, 0.85, 0), dist: 4.4, yaw: 38, pitch: 12 },
    cena(g) {
      const m = this.p.modo;
      if (m === "smith") { g.add(K.piso(3, 3)); const s = K.smith(); g.add(s.g); this.sm = s; }
      else g.add(tablado());
      if (m === "frontal") { this.bar = barra(2); g.add(this.bar); }
      if (m === "goblet") { this.kb = K.kettlebell(16); g.add(this.kb); }
      if (m === "sumo") { this.hv = quHalterV(1.2); g.add(this.hv); }
    },
    pose(t) {
      zera();
      const m = this.p.modo, c = QU_AGA[m];
      let incl = quAgachaTronco(t, c);
      // ---- implementos e mãos ----
      if (m === "smith") {
        let q = quadroDe("spine_03"), bar = ondeEsta("neck_01").add(q.fr.clone().multiplyScalar(-0.1)).add(q.up.clone().multiplyScalar(-0.085));
        quAgachaTronco(t, c, -bar.x); // a barra anda na guia (x = 0): a pelve se ajusta
        q = quadroDe("spine_03"); bar = ondeEsta("neck_01").add(q.fr.clone().multiplyScalar(-0.1)).add(q.up.clone().multiplyScalar(-0.085));
        quAgachaPernas(c);
        this.sm.barra.position.set(0, bar.y, 0);
        for (const l of ["l", "r"]) { const s = quSl(l);
          agarra(l, { ponto: bar.clone().add(q.esq.clone().multiplyScalar(s * 0.36)), eixo: q.esq.clone().multiplyScalar(-s), palma: q.up.clone().add(q.fr.clone().multiplyScalar(0.9)),
            polo: q.up.clone().multiplyScalar(-1).add(q.fr.clone().multiplyScalar(-0.6)).add(q.esq.clone().multiplyScalar(s * 0.3)) }); }
        return;
      }
      quAgachaPernas(c);
      const q = quadroDe("spine_03"), pesc = ondeEsta("neck_01");
      if (m === "frontal") {
        const bar = pesc.clone().add(q.fr.clone().multiplyScalar(0.1)).add(q.up.clone().multiplyScalar(-0.06));
        this.bar.position.copy(bar); this.bar.quaternion.setFromUnitVectors(EX, q.esq);
        for (const l of ["l", "r"]) { const s = quSl(l);
          agarra(l, { ponto: bar.clone().add(q.esq.clone().multiplyScalar(s * 0.2)), eixo: q.esq.clone().multiplyScalar(-s), palma: q.up.clone(),
            polo: q.fr.clone().add(q.up.clone().multiplyScalar(-0.3)).add(q.esq.clone().multiplyScalar(s * 0.2)) }); }
      } else if (m === "goblet") {
        const kb = this.kb, r = 0.075 + 16 * 0.0015;
        const ctr = pesc.clone().add(q.fr.clone().multiplyScalar(0.15)).add(q.up.clone().multiplyScalar(-0.2));
        // alça no plano frontal: x local = esquerda/direita do tronco
        kb.position.copy(ctr); kb.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(q.esq, q.up, q.fr));
        for (const l of ["l", "r"]) { const s = quSl(l);
          const ponto = ctr.clone().add(q.up.clone().multiplyScalar(r * 0.8)).add(q.esq.clone().multiplyScalar(s * r * 0.62));
          agarra(l, { ponto, eixo: q.up.clone(), palma: q.esq.clone().multiplyScalar(-s), R: 0.012,
            polo: q.up.clone().multiplyScalar(-1).add(q.esq.clone().multiplyScalar(s * 0.5)).add(q.fr.clone().multiplyScalar(-0.2)) }); }
      } else if (m === "sumo") {
        const ombros = ondeEsta("upperarm_l").add(ondeEsta("upperarm_r")).multiplyScalar(0.5);
        const reach = (COMP.upperarm_l + COMP.lowerarm_l) * 0.97;
        const mao0 = ombros.clone().add(V3(0, -reach, 0)).add(V3(0.15 + 0.1 * t, 0, 0));
        this.hv.position.copy(mao0.clone().add(V3(0, 0.0, 0))); this.hv.quaternion.identity();
        for (const l of ["l", "r"]) { const s = quSl(l);
          const alto = l === "l" ? 0.045 : -0.045;
          agarra(l, { ponto: mao0.clone().add(V3(0, alto, 0)), eixo: V3(0, 1, 0), palma: q.fr.clone().multiplyScalar(-1), R: 0.016,
            polo: V3(0, 0, 0).add(q.esq.clone().multiplyScalar(s * 1)).add(q.fr.clone().multiplyScalar(-0.3)) }); }
      }
    },
  },
});

// ---------- avanços (frente, reverso, Smith) e búlgaro ----------
const QU_ANG0 = Math.asin(-DIR.foot_l.y); // queda do pé com a sola plana (~28°)
// pé só na ponta: bola em B, queda ang; devolve o tornozelo e a direção do pé
function quPonta(B, ang, f = F0) {
  const d = f.clone().multiplyScalar(Math.cos(ang)).add(V3(0, -Math.sin(ang), 0));
  return { A: B.clone().sub(d.clone().multiplyScalar(COMP.foot_l)), d };
}
function quPePonta(l, d, f = F0) { // orienta o pé (d = tornozelo->bola) e deita os dedos
  mira("foot_" + l, d, EY.clone().cross(d).normalize(), EX);
  const dd = f.clone().multiplyScalar(0.991).add(V3(0, 0.133, 0)).normalize();
  mira("ball_" + l, dd, EY.clone().cross(dd).normalize(), EX);
}
function quTronco(P, incl, k = 1) {
  emPe(P, F0, incl * 0.55);
  gira("spine_01", EX, incl * 0.12); gira("spine_02", EX, incl * 0.12); gira("spine_03", EX, incl * 0.08);
  gira("neck_01", EX, -incl * 0.45 * k); gira("head", EX, -incl * 0.15 * k);
  B.pelvis.updateMatrixWorld(true);
}
// halteres pendurados nas mãos (braço esticado, cabo na direção da frente)
function quHalteresSoltos(hs, reach = 0.985, pxF = 0) {
  const E = esquerda(F0);
  ["l", "r"].forEach((l, i) => { const s = quSl(l), S = ondeEsta("upperarm_" + l);
    agarra(l, { ponto: S.clone().add(V3(pxF, -((COMP.upperarm_l + COMP.lowerarm_l) * reach + 0.07), 0)), R: 0.016, eixo: F0.clone(), palma: E.clone().multiplyScalar(-s),
      polo: F0.clone().multiplyScalar(-1).add(E.clone().multiplyScalar(s * 0.4)) });
    seguraHalter(hs[i], l); });
}
// barra nas costas (mesmo encaixe do agachamento livre)
function quBarraCostas(bar) {
  const c = quadroDe("spine_03"), pesc = ondeEsta("neck_01"), pos = pesc.clone().add(c.fr.clone().multiplyScalar(-0.1)).add(c.up.clone().multiplyScalar(-0.085));
  return { c, pos };
}
function quMaosBarraCostas(c, pos) {
  for (const l of ["l", "r"]) { const s = quSl(l);
    agarra(l, { ponto: pos.clone().add(c.esq.clone().multiplyScalar(s * 0.36)), eixo: c.esq.clone().multiplyScalar(-s), palma: c.up.clone().add(c.fr.clone().multiplyScalar(0.9)),
      polo: c.up.clone().multiplyScalar(-1).add(c.fr.clone().multiplyScalar(-0.6)).add(c.esq.clone().multiplyScalar(s * 0.3)) }); }
}

// pé da frente (plano) e de trás (na ponta) de um avanço; l = lado, x = tornozelo
function quPeFrente(l, x, y = ALT_TORN, rot = 0.1) {
  const E = esquerda(F0);
  perna(l, V3(x, y, -quSl(l) * 0.11), F0.clone().add(E.clone().multiplyScalar(quSl(l) * 0.25)).add(V3(0, 0.1, 0)));
  pe(l, girarY(F0, quSl(l) * rot));
}
function quPeAtras(l, bx, by, ang) { // bola do pé em (bx, by); calcanhar levantado ang (rad)
  const E = esquerda(F0), { A, d } = quPonta(V3(bx, by, -quSl(l) * 0.11), ang);
  perna(l, A, V3(0.1, -1, 0).add(E.clone().multiplyScalar(quSl(l) * 0.15))); quPePonta(l, d);
}

Object.assign(MOLDES, {
  qu_avanco: {
    nome: "Avanço",
    musc: { quadriceps: 1, gluteo: 0.8, adutor: 0.4, posterior: 0.35, lombar: 0.3 },
    dica: "Tronco alto, passo largo. O joelho da frente fica sobre o pé e o de trás desce em direção ao chão; empurra o chão com a perna da frente pra voltar.",
    cam: { alvo: V3(0, 0.78, 0), dist: 4.7, yaw: 28, pitch: 11 },
    cena(g) {
      const p = this.p;
      g.add(tablado());
      if (p.smith) { const s = K.smith(); g.add(s.g); this.sm = s; }
      else if (p.barra) { this.bar = barra(2); g.add(this.bar); }
      else { this.h = [halter(1), halter(1)]; g.add(...this.h); }
    },
    pose(t) {
      zera();
      const p = this.p, rev = p.modo === "reverso", est = !!p.smith;
      const FR = 0.45, RE = -0.68, PY = 0.5, TOPO_Y = est ? 0.74 : ALT_QUADRIL - 0.03, ANG_T = 1.047;
      const dsc = quSuave(t / 0.95), hl = quSuave(t / 0.8);                 // descida da pelve; calcanhar de trás sobe
      const sP = quSuave(t / 0.58), arco = 0.14 * Math.sin(Math.PI * quClamp(t / 0.58)); // passo do pé que anda
      const xB = est ? 0.1 : rev ? -0.15 : 0.25;                             // x da pelve no fundo
      const frontX = xB + FR, rearBX = xB + RE + Math.cos(ANG_T) * COMP.foot_l;   // tornozelo da frente; bola do pé de trás
      const flatBX = rearBX - Math.cos(QU_ANG0) * COMP.foot_l * 0 ; // (bola do pé de trás, pé plano, é o mesmo ponto)
      let px, py = TOPO_Y - (TOPO_Y - PY) * dsc;
      const incl = 0.04 + 0.16 * dsc;
      if (est) px = xB; else if (rev) px = lerp(frontX - 0.02, xB, dsc); else px = lerp(rearBX - Math.cos(QU_ANG0) * COMP.foot_l + 0.04, xB, quSuave(t / 0.85));
      quTronco(V3(px, py, 0), incl);
      let q = null;
      if (est || p.barra) { q = quBarraCostas(); if (est) { const xs = -q.pos.x; quTronco(V3(px + xs, py, 0), incl); q = quBarraCostas(); } }
      const lf = "r", lr = "l"; // da frente = direita (mais perto da câmera)
      if (!rev) {
        quPeAtras(lr, rearBX, QU_BOLA_Y, lerp(QU_ANG0, ANG_T, hl));
        const x0 = rearBX - Math.cos(QU_ANG0) * COMP.foot_l;                // tornozelo do pé de trás, plano
        if (est) quPeFrente(lf, frontX); else quPeFrente(lf, lerp(x0, frontX, sP), ALT_TORN + arco);
      } else {
        quPeFrente(lf, frontX);
        const bola0 = frontX + Math.cos(QU_ANG0) * COMP.foot_l;              // pé junto, plano
        quPeAtras(lr, lerp(bola0, rearBX, sP), QU_BOLA_Y + arco, lerp(QU_ANG0, ANG_T, hl * (sP > 0.98 ? 1 : 0.0)));
      }
      if (est) { this.sm.barra.position.set(0, q.pos.y, 0); quMaosBarraCostas(q.c, q.pos); }
      else if (p.barra) { this.bar.position.copy(q.pos); this.bar.quaternion.setFromUnitVectors(EX, q.c.esq); quMaosBarraCostas(q.c, q.pos); }
      else quHalteresSoltos(this.h);
    },
  },
});

// ---------- ajudantes de pé livre / braços ----------
// pé de uma perna no ar: gira o pé do repouso (queda ~28°) junto com a canela, no plano sagital; flex = ponta do pé (rad, + = estica)
function quPeLivre(l, r, flex = 0) {
  const sh = r.alvo.clone().sub(r.E).normalize(), a = Math.atan2(sh.x, -sh.y) + flex, d0 = V3(Math.hypot(DIR["foot_" + l].x, DIR["foot_" + l].z), DIR["foot_" + l].y, 0);
  const d = V3(d0.x * Math.cos(a) - d0.y * Math.sin(a), d0.x * Math.sin(a) + d0.y * Math.cos(a), 0);
  mira("foot_" + l, d, V3(0, 0, -1), EX);
}
// braço solto apontando numa direção (mão fechada de leve): phi = ângulo a partir de "pra baixo", + pra frente
function quBracoLivre(l, phi, polo, k = 0.4, abre = 0.1) {
  const E = esquerda(F0), s = quSl(l), S = ondeEsta("upperarm_" + l), dir = V3(Math.sin(phi), -Math.cos(phi), 0).add(E.clone().multiplyScalar(s * abre)).normalize();
  braco(l, S.clone().add(dir.multiplyScalar((COMP.upperarm_l + COMP.lowerarm_l) * 0.97)), polo, 0);
  fecha(l, k);
}

Object.assign(MOLDES, {
  qu_bulgaro: {
    nome: "Agachamento búlgaro",
    musc: { quadriceps: 1, gluteo: 0.85, adutor: 0.4, posterior: 0.3 },
    dica: "Peito do pé de trás apoiado no banco, passo largo. Desce com o tronco levemente inclinado, joelho da frente sobre o pé e o de trás apontando pro chão; sobe empurrando o calcanhar da frente.",
    cam: { alvo: V3(-0.15, 0.75, 0), dist: 4.7, yaw: 28, pitch: 11 },
    cena(g) {
      g.add(tablado());
      const b = banco(1.18); b.rotation.y = Math.PI / 2; b.position.set(-0.74, 0, 0); g.add(b);
      this.h = [halter(1), halter(1)]; g.add(...this.h);
    },
    pose(t) {
      zera();
      const E = esquerda(F0), ez = quSuave(t), BT = 0.4425, py = lerp(0.9, 0.52, ez), px = lerp(0.04, 0.0, ez), incl = 0.04 + 0.2 * ez;
      quTronco(V3(px, py, 0), incl);
      // frente = direita (perto da câmera), pé plano; atrás = esquerda, peito do pé no banco
      quPeFrente("r", 0.34);
      const rl = perna("l", V3(-0.64, BT + 0.012, -0.11), V3(0.15, -1, 0).add(E.clone().multiplyScalar(0.1)));
      mira("foot_l", V3(-0.995, -0.1, 0).normalize(), V3(0, 0, -1), EX);
      quHalteresSoltos(this.h);
    },
  },
  qu_stepup: {
    nome: "Subida no banco (step-up)",
    musc: { quadriceps: 1, gluteo: 0.8, adutor: 0.3, posterior: 0.3, panturrilha: 0.3 },
    dica: "Pé inteiro no banco, empurra com a perna de cima sem se impulsionar com a de baixo. Sobe até esticar o quadril e desce devagar, sem despencar.",
    cam: { alvo: V3(0, 1.1, 0), dist: 5.5, yaw: 34, pitch: 9 },
    cena(g) {
      g.add(tablado());
      const b = banco(1.18); b.rotation.y = Math.PI / 2; b.position.set(0, 0, 0); g.add(b);
      this.h = [halter(1), halter(1)]; g.add(...this.h);
    },
    pose(t) {
      zera();
      const E = esquerda(F0), ez = quSuave(t), BT = 0.4425, py = lerp(BT + ALT_QUADRIL - 0.03, 1.09, ez), px = lerp(0.0, -0.12, ez), incl = 0.05 + 0.2 * ez;
      quTronco(V3(px, py, 0), incl);
      // perna de cima = direita, pé plano no banco; a outra sobe até o joelho a 90° e desce até quase tocar o chão atrás do banco
      perna("r", V3(0.03, BT + ALT_TORN, 0.11), F0.clone().add(E.clone().multiplyScalar(-0.25)).add(V3(0, 0.1, 0))); pe("r", F0);
      const sw = quSuave(1 - t);
      const hip = ondeEsta("thigh_l"), top = V3(hip.x + 0.46, hip.y - 0.4, -0.11), bot = V3(-0.34, 0.2, -0.11);
      const A = bot.clone().lerp(top, sw); A.y += 0.0;
      const rl = perna("l", A, F0.clone().add(V3(0, -0.25, 0)).add(E.clone().multiplyScalar(0.2)));
      quPeLivre("l", rl, -0.2 - 0.5 * (1 - sw));
      quHalteresSoltos(this.h);
    },
  },
});

// ---------- pistol, sissy, parede, salto ----------
Object.assign(MOLDES, {
  qu_pistol: {
    nome: "Agachamento pistol",
    musc: { quadriceps: 1, gluteo: 0.85, adutor: 0.4, posterior: 0.35, lombar: 0.3, panturrilha: 0.3 },
    dica: "Uma perna só: a outra fica esticada à frente, braços à frente de contrapeso. Desce com o calcanhar colado no chão e o joelho na linha do pé; sobe empurrando o chão.",
    cam: { alvo: V3(0.1, 0.8, 0.1), dist: 4.4, yaw: 35, pitch: 11 },
    cena(g) { g.add(tablado()); },
    pose(t) {
      zera();
      const E = esquerda(F0), ez = quSuave(t), ZP = 0.1, py = lerp(ALT_QUADRIL - 0.03, 0.37, ez), px = lerp(0.0, -0.2, ez), incl = lerp(0.05, 0.78, ez);
      quTronco(V3(px, py, ZP), incl);
      // perna de apoio = direita, tornozelo sob o quadril
      perna("r", V3(0.0, ALT_TORN, 0.2), F0.clone().add(V3(0, 0.1, 0)).add(E.clone().multiplyScalar(-0.15))); pe("r", girarY(F0, -0.12));
      // perna livre = esquerda, esticada à frente
      const hip = ondeEsta("thigh_l"), al = lerp(0.62, -0.02, ez), L = QU_L * 0.985;
      const A = hip.clone().add(V3(Math.cos(al) * L, -Math.sin(al) * L, -0.04));
      const rl = perna("l", A, V3(0, 1, 0));
      quPeLivre("l", rl, 0.0);
      // braços à frente, na altura do peito
      for (const l of ["l", "r"]) { const s = quSl(l), S = ondeEsta("upperarm_" + l);
        braco(l, S.clone().add(V3(0.46, lerp(-0.1, 0.0, ez), 0)).add(E.clone().multiplyScalar(-s * 0.04)), V3(0.1, -1, 0).add(E.clone().multiplyScalar(s * 0.8)), 0);
        fecha(l, 0.2); }
    },
  },
  qu_sissy: {
    nome: "Sissy squat",
    musc: { quadriceps: 1, panturrilha: 0.3, abdomen: 0.3 },
    dica: "Agarra o poste, sobe nas pontas dos pés e empurra os joelhos pra frente enquanto o tronco vai pra trás, tudo em uma linha dos joelhos à cabeça. Sobe usando só a coxa.",
    cam: { alvo: V3(0.05, 0.85, 0), dist: 4.4, yaw: 22, pitch: 10 },
    cena(g) {
      g.add(tablado());
      g.add(sombreia(K.tubo(V3(0.2, 0, 0), V3(0.2, 2.0, 0), 0.03, M.quadro)));
      g.add(K.caixa(0.34, 0.03, 0.34, M.quadro, 0.01).translateX(0.2).translateY(0.015));
    },
    pose(t) {
      zera();
      const E = esquerda(F0), ez = quSuave(t), ang = 1.15, bola = V3(0.16, QU_BOLA_Y, 0), A0 = quPonta(bola, ang).A;
      const py = lerp(quAltTopo(0.0, 0.97) + A0.y - ALT_TORN, 0.74, ez), incl = lerp(0.0, -0.72, ez), px = lerp(A0.x, A0.x - 0.04, ez);
      emPe(V3(px, py, 0), F0, incl);
      gira("neck_01", EX, -incl * 0.6); gira("head", EX, -incl * 0.3);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { const s = quSl(l), q2 = quPonta(V3(bola.x, QU_BOLA_Y, -s * 0.11), ang);
        perna(l, q2.A, F0.clone().add(E.clone().multiplyScalar(s * 0.2)).add(V3(0, -0.1, 0))); quPePonta(l, q2.d); }
      // mãos no poste (a esquerda um pouco mais baixa)
      for (const l of ["l", "r"]) { const s = quSl(l), S = ondeEsta("upperarm_" + l);
        const ponto = V3(0.2, S.y - 0.2 + (l === "l" ? -0.07 : 0.07), 0);
        agarra(l, { ponto, eixo: V3(0, 1, 0), palma: V3(1, 0, 0), R: 0.03, polo: V3(-0.3, -1, 0).add(E.clone().multiplyScalar(s * 0.8)) }); }
    },
  },
  qu_parede: {
    nome: "Agachamento na parede",
    musc: { quadriceps: 1, gluteo: 0.55, adutor: 0.3, panturrilha: 0.3 },
    dica: "Costas coladas na parede, coxa paralela ao chão e joelhos a 90° sobre os tornozelos. Segura sem se apoiar nas mãos e respira.",
    cam: { alvo: V3(0.1, 0.62, 0), dist: 4.0, yaw: 40, pitch: 9 },
    cena(g) {
      g.add(tablado());
      const w = K.caixa(0.1, 2.8, 3.4, new THREE.MeshStandardMaterial({ color: 0x343840, roughness: 0.85 }), 0.01); w.position.set(-0.29, 1.4, 0); w.receiveShadow = true; g.add(w);
      const rodape = K.caixa(0.03, 0.1, 3.4, M.quadro, 0.006); rodape.position.set(-0.225, 0.05, 0); g.add(rodape);
    },
    fase(r) { return { t: 0.985 + 0.015 * Math.sin(r * 1.3), f: "segura 45 s", esforco: 0.8 + 0.2 * Math.min(1, r / 20) }; },
    pose(t) {
      zera();
      const E = esquerda(F0), ez = quSuave(t), PX = -0.125, FX = 0.37;
      const py = lerp(0.84, ALT_TORN + COMP.calf_l + 0.026, ez);
      emPe(V3(PX, py, 0), F0, 0.0);
      gira("neck_01", EX, -0.04); B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { const s = quSl(l);
        perna(l, V3(FX, ALT_TORN, -s * 0.15), F0.clone().add(V3(0, 0.1, 0)).add(E.clone().multiplyScalar(s * 0.2))); pe(l, girarY(F0, s * 0.12)); }
      // mãos espalmadas na parede, ao lado do quadril
      for (const l of ["l", "r"]) { const s = quSl(l), S = ondeEsta("upperarm_" + l);
        braco(l, V3(-0.19, S.y - 0.48, -s * 0.27), V3(0.4, -0.3, 0).add(E.clone().multiplyScalar(s * 0.7)), 0);
        mao(l, V3(0, -1, 0), V3(-1, 0, 0)); }
    },
  },
  qu_salto: {
    nome: "Agachamento com salto",
    musc: { quadriceps: 1, gluteo: 0.85, panturrilha: 0.6, adutor: 0.3, posterior: 0.3 },
    dica: "Desce até a coxa ficar paralela, braços pra trás, e explode pra cima esticando tornozelo, joelho e quadril. Cai macio na ponta do pé e já amortece descendo de novo.",
    cam: { alvo: V3(0, 0.95, 0), dist: 5.0, yaw: 35, pitch: 9 },
    cena(g) { g.add(tablado()); },
    // ciclo de 2,7 s: em pé, desce, pausa, explode, voa, aterrissa amortecendo
    fase(r) {
      const T = 2.7, u = r % T;
      this.voo = 0; this.arm = 0.15;
      if (u < 0.45) return { t: 0, f: "pronto", esforco: 0.3 };
      if (u < 1.25) { const k = (u - 0.45) / 0.8; this.arm = lerp(0.15, -1.0, quSuave(k)); return { t: quSuave(k), f: "desce", esforco: 0.5 + 0.3 * k }; }
      if (u < 1.4) { this.arm = -1.0; return { t: 1, f: "pausa", esforco: 0.8 }; }
      if (u < 1.62) { const k = (u - 1.4) / 0.22; this.arm = lerp(-1.0, 2.5, quSuave(k)); return { t: 1 - quSuave(k), f: "explode", esforco: 1 }; }
      if (u < 2.05) { const k = (u - 1.62) / 0.43; this.voo = 0.3 * 4 * k * (1 - k); this.arm = lerp(2.5, 1.9, k); return { t: 0, f: "no ar", esforco: 0.6 }; }
      const k = (u - 2.05) / 0.65; this.arm = lerp(1.9, 0.15, quSuave(Math.min(1, k * 1.4)));
      return { t: 0.6 * Math.sin(Math.PI * Math.min(1, k * 1.1)) * (1 - 0.3 * k), f: "amortece", esforco: 0.6 };
    },
    pose(t) {
      zera();
      const c = QU_AGA.salto, E = esquerda(F0), voo = this.voo || 0, phi = this.arm === undefined ? lerp(0.15, -1.0, t) : this.arm;
      quAgachaTronco(t, Object.assign({}, c, { alt0: c.alt0 + voo, alt1: c.alt1 + voo }), 0);
      if (voo > 0.001) { // no ar: ponta do pé esticada, joelhos quase retos
        for (const l of ["l", "r"]) { const s = quSl(l), y = Math.max(ALT_QUADRIL - 0.03 + voo - QU_L * 0.95 - 0.026, ALT_TORN + voo * 0.9);
          perna(l, V3(0.0, y, -s * 0.15), F0.clone().add(V3(0, 0.1, 0))); pe(l, F0, -1.1); }
      } else quAgachaPernas(c);
      for (const l of ["l", "r"]) { const s = quSl(l), S = ondeEsta("upperarm_" + l);
        const dir = V3(Math.sin(phi), -Math.cos(phi), 0).add(E.clone().multiplyScalar(s * 0.12)).normalize();
        braco(l, S.clone().add(dir.multiplyScalar((COMP.upperarm_l + COMP.lowerarm_l) * 0.96)), V3(-0.4, -0.2, 0).add(E.clone().multiplyScalar(s * 0.9)), 0);
        fecha(l, 0.45); }
    },
  },
});

// ---------- avanço andando (ciclo: desce no passo, sobe trazendo o pé de trás; o chão tem listras no passo, a câmera segue a pelve) ----------
Object.assign(MOLDES, {
  qu_andando: {
    nome: "Avanço andando",
    musc: { quadriceps: 1, gluteo: 0.85, adutor: 0.4, posterior: 0.35, lombar: 0.3 },
    dica: "Passo largo, desce até o joelho de trás quase tocar o chão, empurra com a perna da frente e traz a de trás pra ficar em pé antes do próximo passo. Tronco alto.",
    cam: { alvo: V3(0.2, 0.78, 0), dist: 4.7, yaw: 28, pitch: 11 },
    cena(g) {
      this.cam.alvo = V3(0.2, 0.78, 0);
      g.add(K.piso(7, 3));
      this.fx = []; for (let i = -6; i <= 6; i++) { const f = K.caixa(0.04, 0.004, 2.4, M.faixa, 0.001); f.position.set(0, 0.002, 0); g.add(f); this.fx.push(f); }
      this.h = [halter(1), halter(1)]; g.add(...this.h);
    },
    fase(r) {
      const T = 3.2, u = r % T; this.par = Math.floor(r / T) % 2; this.up = 0;
      if (u < 1.3) { const k = u / 1.3; return { t: k, f: "desce no passo", esforco: 0.5 + 0.3 * k }; }
      if (u < 1.5) return { t: 1, f: "embaixo", esforco: 0.8 };
      if (u < 2.8) { const k = (u - 1.5) / 1.3; this.up = k; return { t: 1 - k * 0, f: "sobe e junta o pé", esforco: 1 }; }
      this.up = 1; return { t: 0, f: "em pé", esforco: 0.3 };
    },
    pose(t) {
      zera();
      const up = this.up || 0, FR = 0.45, RE = -0.68, PY = 0.5, TOPO = ALT_QUADRIL - 0.03, ANG_T = 1.047, xB = 0.25;
      const frontX = xB + FR, rearBX = xB + RE + Math.cos(ANG_T) * COMP.foot_l, x0 = rearBX - Math.cos(QU_ANG0) * COMP.foot_l, stride = frontX - x0;
      const lf = this.par ? "l" : "r", lr = this.par ? "r" : "l";
      const e = quSuave(up), dsc = quSuave(t / 0.95), sP = quSuave(t / 0.58), arco = 0.14 * Math.sin(Math.PI * quClamp(t / 0.58));
      let py, px, incl;
      if (up > 0) { py = lerp(PY, TOPO, e); px = lerp(xB, frontX - 0.02, e); incl = lerp(0.2, 0.04, e); }
      else { py = TOPO - (TOPO - PY) * dsc; px = lerp(x0 + 0.04, xB, quSuave(t / 0.85)); incl = 0.04 + 0.16 * dsc; }
      quTronco(V3(px, py, 0), incl);
      const ladoF = (l) => { const E = esquerda(F0); const rr = perna(l, V3(0, 0, 0), V3(1, 0, 0)); return rr; };
      if (up > 0) {
        quPeFrente(lf, frontX);
        const bola0 = frontX + Math.cos(QU_ANG0) * COMP.foot_l, s2 = quSuave(up / 0.8);
        quPeAtras(lr, lerp(rearBX, bola0, s2), QU_BOLA_Y + 0.14 * Math.sin(Math.PI * quClamp(up / 0.8)), lerp(ANG_T, QU_ANG0, quSuave(up / 0.6)));
      } else {
        quPeAtras(lr, rearBX, QU_BOLA_Y, lerp(QU_ANG0, ANG_T, quSuave(t / 0.8)));
        quPeFrente(lf, lerp(x0, frontX, sP), ALT_TORN + arco);
      }
      quHalteresSoltos(this.h);
      const cx = px; this.cam.alvo.x = cx;
      this.fx.forEach((f, i) => { f.position.x = x0 + (i - 6) * stride; });
    },
  },
});

// ---------- máquinas ----------
const QU_ACO = new THREE.MeshStandardMaterial({ color: 0x23262c, metalness: 0.6, roughness: 0.4 });
// plataforma de pé (placa) com normal n apontando pra quem pisa; centro P
function quPlaca(w = 0.7, h = 0.5) { const g = new THREE.Group(); const b = K.caixa(0.05, h, w, M.quadro, 0.01); g.add(b);
  const ant = K.caixa(0.012, h * 0.9, w * 0.9, M.aco, 0.004); ant.position.x = 0.03; g.add(ant); return sombreia(g); }
function quSobePlaca(gr, P, n) { gr.position.copy(P); gr.quaternion.setFromUnitVectors(EX, n.clone().normalize()); }
function quMaosBarraLateral(l, ponto, eixo, polo) { const s = quSl(l), E = esquerda(F0);
  agarra(l, { ponto: ponto.clone().add(V3(0, 0, -s * 0.0)), eixo, palma: E.clone().multiplyScalar(-s), R: 0.015, polo }); }

Object.assign(MOLDES, {
  qu_legpress: {
    nome: "Leg press",
    musc: { quadriceps: 1, gluteo: 0.8, adutor: 0.5, posterior: 0.35 },
    dica: "Costas e quadril grudados no banco, pés no meio da plataforma na largura dos ombros. Desce até uns 90° de joelho sem o quadril descolar e empurra sem travar o joelho.",
    cam: { alvo: V3(0.3, 0.75, 0), dist: 4.6, yaw: 22, pitch: 12 },
    cena(g) {
      const p = this.p, hor = p.modo === "horizontal";
      g.add(K.piso(3.6, 3));
      const mat = QU_ACO;
      this.pl = quPlaca(0.72, 0.52); g.add(this.pl);
      if (!hor) { // trenó a 45°
        const r = V3(Math.SQRT1_2, Math.SQRT1_2, 0), o = V3(0.05, 0.15, 0);
        for (const z of [-0.42, 0.42]) { g.add(K.viga(o.clone().add(V3(0, 0, z)), o.clone().add(r.clone().multiplyScalar(2.1)).add(V3(0, 0, z)), 0.07, mat));
          for (const k of [0.5, 1.9]) { const a = o.clone().add(r.clone().multiplyScalar(k)); g.add(K.viga(V3(a.x, a.y, z), V3(a.x, 0.02, z), 0.06, mat)); }
          g.add(K.caixa(0.9, 0.04, 0.1, mat, 0.01).translateX(a_x(o, r, 0.5)).translateY(0.02).translateZ(z)); }
        // banco: assento + encosto a 35°
        const as = K.assento(0.5, 0.46, 0.09); as.position.set(0.0, 0.3, 0); g.add(as);
        const enc = K.caixa(0.78, 0.09, 0.5, M.estofado, 0.03); const a = 35 * Math.PI / 180; enc.position.set(-0.07 - 0.39 * Math.cos(a), 0.34 + 0.39 * Math.sin(a), 0); enc.rotation.z = a; g.add(enc);
        g.add(K.viga(V3(0.0, 0.26, 0), V3(0.0, 0.02, 0), 0.08, mat)); g.add(K.caixa(0.1, 0.04, 0.6, mat).translateX(0.0).translateY(0.02));
        g.add(K.viga(V3(-0.1, 0.3, 0.0), V3(-0.62, 0.1, 0), 0.07, mat));
        for (const z of [-0.33, 0.33]) { g.add(K.tubo(V3(0.12, 0.5, z), V3(0.38, 0.62, z), 0.016, M.cromo)); g.add(K.viga(V3(0.0, 0.34, z), V3(0.12, 0.5, z), 0.03, mat)); }
        // anilhas nos pinos laterais do trenó
        this.ani = [];
        for (const z of [-1, 1]) { const pino = K.tubo(V3(-0.1, 0, z * 0.36), V3(-0.1, 0, z * 0.78), 0.025, M.cromo); pino.userData.z = z; this.pl.add(sombreia(pino));
          for (let i = 0; i < 4; i++) { const an = anilha(0.225, 0.045); an.rotation.x = Math.PI / 2; an.position.set(-0.1, 0, z * (0.5 + i * 0.05)); this.pl.add(an); } }
      } else { // horizontal: banco reclinado e placa em trilhos
        for (const z of [-0.32, 0.32]) { g.add(K.tubo(V3(0.2, 0.62, z), V3(1.5, 0.62, z), 0.025, M.cromo)); g.add(K.viga(V3(0.2, 0.0, z), V3(1.5, 0.0, z), 0.07, mat).translateY(0.035)); g.add(K.viga(V3(0.2, 0.62, z), V3(0.2, 0.0, z), 0.06, mat)); g.add(K.viga(V3(1.5, 0.62, z), V3(1.5, 0.0, z), 0.06, mat)); }
        const as = K.assento(0.5, 0.46, 0.09); as.position.set(-0.2, 0.34, 0); g.add(as);
        const enc = K.caixa(0.8, 0.09, 0.5, M.estofado, 0.03); const a = 70 * Math.PI / 180; enc.position.set(-0.45 - 0.4 * Math.cos(a), 0.4 + 0.4 * Math.sin(a), 0); enc.rotation.z = a; g.add(enc);
        g.add(K.viga(V3(-0.2, 0.3, 0), V3(-0.2, 0.02, 0), 0.08, mat)); g.add(K.caixa(0.1, 0.04, 0.6, mat).translateX(-0.2).translateY(0.02)); g.add(K.viga(V3(-0.5, 0.35, 0), V3(-0.6, 0.02, 0), 0.07, mat)); g.add(K.caixa(0.1, 0.04, 0.6, mat).translateX(-0.6).translateY(0.02));
        for (const z of [-0.33, 0.33]) g.add(K.tubo(V3(-0.1, 0.55, z), V3(0.18, 0.62, z), 0.016, M.cromo));
        const pi = K.pilha(); pi.position.set(1.85, 0, 0); pi.rotation.y = Math.PI / 2; g.add(pi); g.add(K.caixa(0.42, 1.3, 0.34, mat).translateX(1.85).translateY(0.7));
        g.add(K.tubo(V3(0.0, 0.62, 0), V3(1.7, 0.62, 0), 0.01, M.aco).translateY(0));
      }
      if (p.uni) { this.rep = K.caixa(0.34, 0.04, 0.2, mat, 0.01); g.add(this.rep); this.rep2 = K.viga(V3(0, 0, 0), V3(0, 0.1, 0), 0.05, mat); }
    },
    pose(t) {
      zera();
      const p = this.p, hor = p.modo === "horizontal", ez = quSuave(t), E = esquerda(F0), d = lerp(0.89, 0.6, ez);
      let H, cab, fr, n, u, rail;
      if (!hor) { const a = 35 * Math.PI / 180; cab = V3(-Math.cos(a), Math.sin(a), 0); fr = V3(Math.sin(a), Math.cos(a), 0); H = V3(0.02, 0.45, 0); n = V3(-Math.SQRT1_2, -Math.SQRT1_2, 0); u = V3(-Math.SQRT1_2, Math.SQRT1_2, 0); rail = V3(Math.SQRT1_2, Math.SQRT1_2, 0); }
      else { const a = 70 * Math.PI / 180; cab = V3(-Math.cos(a), Math.sin(a), 0); fr = V3(Math.sin(a), Math.cos(a), 0); H = V3(-0.17, 0.44, 0); n = V3(-1, 0, 0); u = V3(0, 1, 0); rail = V3(1, 0.12, 0).normalize(); }
      corpoEm(H, cab, fr);
      gira("spine_02", EX, -0.05); gira("neck_01", EX, 0.1); B.pelvis.updateMatrixWorld(true);
      const hm = ondeEsta("thigh_l").add(ondeEsta("thigh_r")).multiplyScalar(0.5);
      const Acenter = hm.clone().add(rail.clone().multiplyScalar(d));
      const P = Acenter.clone().sub(n.clone().multiplyScalar(ALT_TORN)).add(u.clone().multiplyScalar(0.1));
      quSobePlaca(this.pl, P, n);
      for (const l of ["l", "r"]) { const s = quSl(l), z = -s * 0.15;
        if (p.uni && l === "l") { // perna parada: pé apoiado no estribo ao lado
          const Ar = hm.clone().add(V3(hor ? 0.42 : 0.3, hor ? -0.05 : -0.12, 0)); Ar.z = z;
          perna(l, Ar, V3(0, 1, 0).add(E.clone().multiplyScalar(s * 0.3))); pe(l, F0);
          this.rep.position.set(Ar.x + 0.04, Ar.y - ALT_TORN - 0.02, z); continue; }
        const A = Acenter.clone(); A.z = p.uni ? 0.0 : z;
        perna(l, A, V3(0, 1, 0).add(E.clone().multiplyScalar(s * 0.35))); quPeNoPlano(l, n, u, s * 0.2); }
      for (const l of ["l", "r"]) { const s = quSl(l), pt = (hor ? V3(0.12, 0.62, -s * 0.33) : V3(0.25, 0.56, -s * 0.33));
        quMaosBarraLateral(l, pt, hor ? V3(1, 0.4, 0) : V3(1, 0.5, 0), V3(0, -1, 0).add(E.clone().multiplyScalar(s * 0.5)).add(V3(-0.3, 0, 0))); }
    },
  },
});
function a_x(o, r, k) { return o.x + r.x * k; }

Object.assign(MOLDES, {
  qu_hack: {
    nome: "Agachamento hack",
    musc: { quadriceps: 1, gluteo: 0.7, adutor: 0.4, posterior: 0.25 },
    dica: "Costas no encosto e ombros sob as almofadas, pés à frente na plataforma. Desce controlando até a coxa passar da paralela, calcanhar firme, e sobe sem travar o joelho.",
    cam: { alvo: V3(0.2, 0.85, 0), dist: 4.6, yaw: 28, pitch: 10 },
    cena(g) {
      g.add(K.piso(3.4, 3));
      const a = 25 * Math.PI / 180, pu = V3(-Math.sin(a), Math.cos(a), 0), nb = V3(Math.cos(a), Math.sin(a), 0), mat = QU_ACO;
      this.pu = pu; this.nb = nb;
      for (const z of [-0.3, 0.3]) { g.add(K.viga(V3(0.55, 0.0, z).add(pu.clone().multiplyScalar(-0.1)), V3(0.55, 0.0, z).add(pu.clone().multiplyScalar(2.1)), 0.07, mat).translateX(-0.45 + 0.0));
        g.add(K.caixa(0.9, 0.05, 0.1, mat).translateZ(z).translateX(0.1).translateY(0.025)); }
      const pf = K.caixa(0.62, 0.05, 0.7, M.quadro, 0.01); pf.position.set(0.5, 0.2, 0); pf.rotation.z = 20 * Math.PI / 180; g.add(pf);
      g.add(K.caixa(0.5, 0.17, 0.6, mat).translateX(0.5).translateY(0.09));
      this.sl = new THREE.Group(); g.add(this.sl); // trenó: origem na pelve
      const dorso = K.caixa(0.09, 0.95, 0.38, M.estofado, 0.035); dorso.position.copy(pu.clone().multiplyScalar(0.3).add(nb.clone().multiplyScalar(-0.1))); dorso.quaternion.setFromUnitVectors(EY, pu); this.sl.add(dorso);
      const base = K.caixa(0.1, 1.5, 0.74, mat); base.position.copy(pu.clone().multiplyScalar(0.3).add(nb.clone().multiplyScalar(-0.2))); base.quaternion.setFromUnitVectors(EY, pu); this.sl.add(base);
      for (const z of [-0.2, 0.2]) { const om = K.caixa(0.18, 0.1, 0.2, M.estofado, 0.04); om.position.copy(pu.clone().multiplyScalar(0.62).add(nb.clone().multiplyScalar(0.0))).add(V3(0, 0, z)); om.quaternion.setFromUnitVectors(EY, pu); this.sl.add(om); }
      for (const z of [-0.33, 0.33]) { this.sl.add(K.tubo(pu.clone().multiplyScalar(0.08).add(nb.clone().multiplyScalar(0.12)).add(V3(0, 0, z)), pu.clone().multiplyScalar(0.3).add(nb.clone().multiplyScalar(0.15)).add(V3(0, 0, z)), 0.016, M.cromo));
        const pino = K.tubo(V3(-0.1, 0, z * 1.0).add(pu.clone().multiplyScalar(0.2)).add(nb.clone().multiplyScalar(-0.3)), V3(-0.1, 0, z * 2.0).add(pu.clone().multiplyScalar(0.2)).add(nb.clone().multiplyScalar(-0.3)), 0.025, M.cromo); this.sl.add(pino);
        for (let i = 0; i < 3; i++) { const an = anilha(0.225, 0.045); an.rotation.x = Math.PI / 2; an.position.copy(V3(-0.1, 0, z * (1.0 + 0.2 + i * 0.05)).add(pu.clone().multiplyScalar(0.2)).add(nb.clone().multiplyScalar(-0.3))); this.sl.add(an); } }
      sombreia(this.sl);
    },
    pose(t) {
      zera();
      const ez = quSuave(t), E = esquerda(F0), pu = this.pu, nb = this.nb, a = 25 * Math.PI / 180;
      const H0 = V3(0.17, 1.12, 0), dn = pu.clone().multiplyScalar(-1), s = lerp(0, 0.42, ez), H = H0.clone().add(dn.clone().multiplyScalar(s));
      this.sl.position.copy(H);
      corpoEm(H, pu, nb);
      gira("neck_01", EX, 0.1); B.pelvis.updateMatrixWorld(true);
      const pn = V3(-Math.sin(20 * Math.PI / 180), Math.cos(20 * Math.PI / 180), 0), pu2 = V3(Math.cos(20 * Math.PI / 180), Math.sin(20 * Math.PI / 180), 0);
      for (const l of ["l", "r"]) { const sg = quSl(l), A = V3(0.5, 0.2, -sg * 0.17).add(pn.clone().multiplyScalar(ALT_TORN)).add(V3(0.0, 0, 0));
        perna(l, A, V3(1, 0, 0).add(E.clone().multiplyScalar(sg * 0.25))); quPeNoPlano(l, pn, pu2, sg * 0.2); }
      for (const l of ["l", "r"]) { const sg = quSl(l); const pt = H.clone().add(pu.clone().multiplyScalar(0.2)).add(nb.clone().multiplyScalar(0.12)).add(V3(0, 0, -sg * 0.33));
        quMaosBarraLateral(l, pt, nb.clone().cross(EZ).normalize(), V3(0, -1, 0).add(E.clone().multiplyScalar(sg * 0.6))); }
    },
  },
  qu_extensora: {
    nome: "Cadeira extensora",
    musc: { quadriceps: 1 },
    dica: "Joelho alinhado com o eixo da máquina e o rolo logo acima do tornozelo. Estende até quase travar, segura um instante e desce devagar sem deixar a placa bater.",
    cam: { alvo: V3(0.2, 0.7, 0), dist: 4.0, yaw: 30, pitch: 10 },
    cena(g) {
      const mat = QU_ACO; g.add(K.piso(3.2, 3));
      const as = K.assento(0.46, 0.44, 0.09); as.position.set(-0.05, 0.4, 0); g.add(as);
      const a = 12 * Math.PI / 180, enc = K.caixa(0.85, 0.09, 0.46, M.estofado, 0.03); enc.position.set(-0.3 - 0.43 * Math.sin(a), 0.5 + 0.43 * Math.cos(a), 0); enc.rotation.z = a - Math.PI / 2 * 0 + 0; enc.rotation.z = -(Math.PI / 2 - a) + Math.PI; enc.rotation.z = Math.PI / 2 + a; g.add(enc);
      g.add(K.viga(V3(0.0, 0.36, 0), V3(0.0, 0.02, 0), 0.09, mat)); g.add(K.caixa(1.0, 0.05, 0.7, mat).translateX(0.1).translateY(0.025));
      g.add(K.viga(V3(-0.35, 0.3, 0), V3(-0.55, 1.5, 0), 0.1, mat));
      const pi = K.pilha(); pi.position.set(-0.78, 0, 0); pi.rotation.y = Math.PI / 2; g.add(pi); g.add(K.caixa(0.4, 1.2, 0.36, mat).translateX(-0.78).translateY(0.65));
      for (const z of [-0.26, 0.26]) g.add(K.tubo(V3(0.0, 0.62, z), V3(0.3, 0.66, z), 0.016, M.cromo));
      this.pivo = V3(0.4, 0.34, 0);
      g.add(K.caixa(0.14, 0.14, 0.6, mat, 0.03).translateX(this.pivo.x).translateY(this.pivo.y));
      this.bracos = [K.tubo(V3(), V3(0, 1, 0), 0.022, mat), K.tubo(V3(), V3(0, 1, 0), 0.022, mat)]; this.bracos.forEach((b) => g.add(b));
      this.rol = K.rolo(0.46, 0.05); this.rol.rotation.y = Math.PI / 2; g.add(this.rol);
      this.coxa = K.rolo(0.46, 0.04); this.coxa.rotation.y = Math.PI / 2; g.add(this.coxa);
    },
    pose(t) {
      zera();
      const p = this.p, ez = quSuave(t), E = esquerda(F0), cab = V3(-Math.sin(12 * Math.PI / 180), Math.cos(12 * Math.PI / 180), 0), fr = V3(Math.cos(12 * Math.PI / 180), Math.sin(12 * Math.PI / 180), 0);
      corpoEm(V3(-0.17, 0.55, 0), cab, fr); gira("neck_01", EX, 0.08); B.pelvis.updateMatrixWorld(true);
      const rols = [];
      for (const l of ["l", "r"]) { const s = quSl(l), hip = ondeEsta("thigh_" + l), K_ = hip.clone().add(V3(Math.cos(0.05), -Math.sin(0.05), 0).multiplyScalar(COMP.thigh_l));
        const th = (p.uni && l === "l") ? -1.3 : lerp(0.12, -1.3, ez), sh = V3(Math.cos(th), Math.sin(th), 0), A = K_.clone().add(sh.clone().multiplyScalar(COMP.calf_l));
        const rr = perna(l, A, V3(0, 1, 0).add(E.clone().multiplyScalar(s * 0.15))); quPeLivre(l, rr, 0.2); rols.push(K_.clone().add(sh.clone().multiplyScalar(COMP.calf_l * 0.85)).add(V3(0, 0, 0))); this.kn = K_; }
      const R = (p.uni ? rols[1] : rols[0]).clone(); R.z = 0; this.rol.position.copy(R);
      this.coxa.position.set(this.kn.x - 0.12, this.kn.y + 0.1, 0);
      this.bracos.forEach((b, i) => { const z = i ? 0.26 : -0.26; const A = V3(this.pivo.x - 0.1, this.pivo.y, z), Bq = V3(R.x, R.y - 0.0, z); K.poe(b, A, Bq); });
      for (const l of ["l", "r"]) { const s = quSl(l);
        quMaosBarraLateral(l, V3(0.15, 0.64, -s * 0.26), V3(1, 0.1, 0), V3(0, -1, 0).add(E.clone().multiplyScalar(s * 0.5))); }
    },
  },
});

// ---------- intensidade dos músculos (0..1, 1 = quem mais trabalha) ----------
// CONFERIDO de verdade: revisão sistemática do leg press (PMC7369968): vastos lateral/medial > reto femoral; pé baixo na plataforma = mais reto femoral;
//   Stien 2021 (JSSM 20:56): leg press > extensora no vasto lateral, extensora > leg press no reto femoral.
// DE MEMÓRIA, NÃO CONFERIDO (tratar como estimativa guiada pela literatura): Escamilla 2001 (leg press x agachamento: vastos e reto, isquio e glúteo mais no agachamento),
//   Gullett 2009 (frontal ~ costas em quadríceps, frontal com menos lombar), Andersen 2014 (búlgaro: quadríceps e glúteo altos), Da Silva 2017, Escamilla 2000 (extensora: reto femoral alto).
// Pistol, sissy, salto, step-up, andando, Smith, hack, goblet, sumô e parede: ESTIMATIVA.
Object.assign(FOCOS, {
  qu_agacha: (p) => p.modo === "frontal" ? [["vasto_lateral", 1], ["vasto_medial", 1], ["reto_femoral", 0.6], ["gluteo_max", 0.55], ["adutores", 0.5], ["lombar", 0.4], ["abdomen", 0.4], ["isquio", 0.25]]
    : p.modo === "smith" ? [["vasto_lateral", 1], ["vasto_medial", 1], ["reto_femoral", 0.6], ["gluteo_max", 0.5], ["adutores", 0.45], ["panturrilha", 0.3], ["isquio", 0.2]]
    : p.modo === "goblet" ? [["vasto_lateral", 1], ["vasto_medial", 1], ["gluteo_max", 0.65], ["reto_femoral", 0.55], ["adutores", 0.6], ["abdomen", 0.4], ["lombar", 0.35]]
    : [["vasto_medial", 1], ["vasto_lateral", 0.95], ["adutores", 0.9], ["gluteo_max", 0.8], ["reto_femoral", 0.5], ["gluteo_med", 0.4], ["lombar", 0.3]],
  qu_salto: () => [["vasto_lateral", 1], ["vasto_medial", 1], ["gluteo_max", 0.8], ["reto_femoral", 0.6], ["panturrilha", 0.6], ["adutores", 0.4], ["isquio", 0.35]],
  qu_pistol: () => [["vasto_lateral", 1], ["vasto_medial", 1], ["gluteo_max", 0.85], ["gluteo_med", 0.65], ["reto_femoral", 0.55], ["adutores", 0.5], ["panturrilha", 0.4], ["lombar", 0.3]],
  qu_sissy: () => [["reto_femoral", 1], ["vasto_lateral", 0.95], ["vasto_medial", 0.9], ["panturrilha", 0.4], ["abdomen", 0.35]],
  qu_parede: () => [["vasto_lateral", 1], ["vasto_medial", 1], ["reto_femoral", 0.4], ["gluteo_max", 0.35], ["adutores", 0.3], ["panturrilha", 0.2]],
  qu_bulgaro: () => [["vasto_lateral", 1], ["vasto_medial", 0.95], ["gluteo_max", 0.9], ["gluteo_med", 0.6], ["reto_femoral", 0.5], ["adutores", 0.45], ["isquio", 0.4]],
  qu_avanco: (p) => [["vasto_lateral", 1], ["vasto_medial", 1], ["gluteo_max", p.modo === "reverso" ? 0.85 : 0.75], ["reto_femoral", 0.55], ["adutores", 0.5], ["gluteo_med", 0.45], ["isquio", 0.35]],
  qu_andando: () => [["vasto_lateral", 1], ["vasto_medial", 1], ["gluteo_max", 0.85], ["reto_femoral", 0.6], ["adutores", 0.5], ["gluteo_med", 0.5], ["isquio", 0.4]],
  qu_stepup: () => [["vasto_lateral", 1], ["vasto_medial", 1], ["gluteo_max", 0.8], ["gluteo_med", 0.55], ["reto_femoral", 0.5], ["panturrilha", 0.35], ["isquio", 0.3]],
  qu_legpress: (p) => p.modo === "horizontal" ? [["vasto_lateral", 1], ["vasto_medial", 1], ["reto_femoral", 0.65], ["gluteo_max", 0.5], ["adutores", 0.5], ["isquio", 0.3]]
    : [["vasto_lateral", 1], ["vasto_medial", 1], ["reto_femoral", 0.6], ["gluteo_max", 0.55], ["adutores", 0.5], ["isquio", 0.3], ["panturrilha", 0.2]],
  qu_hack: () => [["vasto_lateral", 1], ["vasto_medial", 1], ["reto_femoral", 0.6], ["gluteo_max", 0.5], ["adutores", 0.4], ["isquio", 0.25]],
  qu_extensora: () => [["reto_femoral", 1], ["vasto_lateral", 0.95], ["vasto_medial", 0.9]],
});
Object.assign(VISTA, { qu_agacha: 40, qu_avanco: 30, qu_andando: 30, qu_bulgaro: 30, qu_stepup: 36, qu_pistol: 38, qu_sissy: 32, qu_parede: 44, qu_salto: 38, qu_legpress: 25, qu_hack: 30, qu_extensora: 32 });
}

// ===== moldes/triceps.js =====
{ // moldes/triceps.js  (prefixo tr_)
// Tríceps: polia (corda/barra reta/V/invertida/unilateral), testa (barra W/halteres/polia/JM press), francês (halter/unilateral/polia),
// coice (halter/polia), mergulho no banco, paralelas, máquina. Cotovelo fixo = cotovelo calculado (ombro + úmero) e o antebraço gira em volta dele.

// ---------- ajudantes (só deste arquivo) ----------
const zs = (l) => (l === "l" ? -1 : 1);           // lado em Z (esquerdo = -Z, também deitado)
const sl_ = (l) => (l === "l" ? 1 : -1);
const dentro = (l) => V3(0, 0, -zs(l));           // pra onde fica a linha do meio do corpo
const unit = (v) => v.clone().normalize();
const clampN = (x, a, b) => Math.max(a, Math.min(b, x));
const media = (a, b) => a.clone().add(b).multiplyScalar(0.5);
function trG(l, k, n, R) { // deslocamento punho -> centro da pegada, igual ao que o agarra() calcula
  const m0 = MAO0[l], kk = unit(k), nn = unit(n.clone().sub(kk.clone().multiplyScalar(n.dot(kk))));
  const f = kk.clone().cross(nn).multiplyScalar(sl_(l));
  const q = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(f, kk, f.clone().cross(kk))).multiply(m0.qInv);
  return G0(l, R).applyQuaternion(q);
}
function trDirZ(E, d, zW) { // inclina o antebraço pro lado até o punho cair em z = zW (mantém o resto do plano XY)
  const lat = clampN((zW - E.z) / COMP.lowerarm_l, -0.8, 0.8), xy = Math.hypot(d.x, d.y) || 1, c = Math.sqrt(1 - lat * lat) / xy;
  return V3(d.x * c, d.y * c, lat);
}
// Antebraço de um braço com COTOVELO FIXO em E: o punho fica em E + dir*antebraço e a mão fecha na pega de eixo k.
// A palma sai sozinha (dedos seguindo o antebraço). zAlvo: se vier, a pegada cai nesse Z.
function trAnte(l, S, E, dir, k, R, zAlvo = null) {
  const L = COMP.lowerarm_l;
  const f0 = unit(dir.clone().sub(k.clone().multiplyScalar(dir.dot(k))));
  const n = f0.clone().cross(k).multiplyScalar(sl_(l)).normalize();
  let d = unit(dir);
  if (zAlvo !== null) d = trDirZ(E, d, zAlvo - trG(l, k, n, R).z);
  return agarra(l, { punho: E.clone().add(d.multiplyScalar(L)), eixo: k, palma: n, R, polo: E.clone().sub(S).add(V3(0, 0, 1e-4)) });
}
const cotovelo = (S, u) => S.clone().add(unit(u).multiplyScalar(COMP.upperarm_l)); // cotovelo = ombro + úmero
// Mão aberta (apoio / concha): punho em W, dedos pra dirD, palma pra palmaW; a torção do antebraço acompanha a da mão
function trMao(l, W, polo, dirD, palmaW, aperta = 0.15) {
  braco(l, W, polo, 0); mao(l, dirD, palmaW);
  const qf = B["lowerarm_" + l].getWorldQuaternion(new THREE.Quaternion()), qh = B["hand_" + l].getWorldQuaternion(new THREE.Quaternion());
  const rel = qf.invert().multiply(qh), a = DIR["lowerarm_" + l], tw = 2 * Math.atan2(rel.x * a.x + rel.y * a.y + rel.z * a.z, rel.w);
  braco(l, W, polo, Math.atan2(Math.sin(tw), Math.cos(tw)) * 0.9); mao(l, dirD, palmaW);
  if (aperta) fecha(l, aperta, 0.3);
}
// Pilha da polia sobe só quando o cabo alonga: mede o curso em t=0 e t=1 e zera na posição de repouso (cabo mais curto)
function trCurso(m) {
  if (!m.torre || m.ref) return; m.ref = true;
  m.calc(0); const a = m.torre.cabo.scale.y; m.calc(1); const b = m.torre.cabo.scale.y;
  m.torre.zeraCurso(); m.calc(a < b ? 0 : 1);
}
function trTorre(g, { alt = 2.0, x = 0.55, z = 0, ang = -Math.PI / 2 } = {}) { // ang -90° = saída do cabo apontando pro -X (pro atleta); +90° = pro +X
  const t = K.torre({ alt }); t.g.position.set(x, 0, z); t.g.rotation.y = ang; g.add(t.g); return t;
}
// base de uma pega rígida (barra reta / V / estribo): origem no centro, X = eixoLat, Y = pro cabo (tirando a parte ao longo de X)
function trBase(pega, centro, eixoLat, haciaCabo) {
  const X = unit(eixoLat), Y = unit(haciaCabo.clone().sub(X.clone().multiplyScalar(haciaCabo.dot(X)))), Z = X.clone().cross(Y);
  pega.position.copy(centro); pega.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(X, Y, Z)); pega.updateMatrixWorld(true);
  return { X, Y, Z };
}
// Barra W (EZ): zigue-zague no plano XY local (X = eixo da barra); as pegadas internas são os trechos inclinados em ±0.07
const W_PTS = [[-0.6, 0], [-0.22, 0], [-0.14, 0.04], [0, 0], [0.14, 0.04], [0.22, 0], [0.6, 0]];
function trBarraW() {
  const g = new THREE.Group();
  for (let i = 0; i < W_PTS.length - 1; i++) g.add(K.tubo(V3(W_PTS[i][0], W_PTS[i][1], 0), V3(W_PTS[i + 1][0], W_PTS[i + 1][1], 0), 0.0125, M.cromo));
  for (const [x, y] of W_PTS.slice(1, -1)) { const s = new THREE.Mesh(new THREE.SphereGeometry(0.0125, 12, 8), M.cromo); s.position.set(x, y, 0); g.add(s); }
  for (const s of [-1, 1]) {
    const a = anilha(0.1, 0.03); a.rotation.z = Math.PI / 2; a.position.x = s * 0.5; g.add(a);
    const c = cil(0.03, 0.02, M.faixa); c.rotation.z = Math.PI / 2; c.position.x = s * 0.535; g.add(c);
    const bo = K.cilU(0.016, M.borracha); bo.scale.y = 0.14; bo.rotation.z = Math.PI / 2; bo.position.set(s * 0.07, 0.02, 0); bo.rotation.z = Math.PI / 2 + s * 0.27; g.add(bo); // borracha das pegadas internas
  }
  return sombreia(g);
}
// banco com encosto quase em pé (francês sentado, máquina): assento + encosto inclinado + pés
function trBancoSentado(g, tilt = 0.12, ass = 0.46) {
  const seat = K.caixa(0.46, 0.08, 0.34, M.estofado, 0.03); seat.position.set(0.02, ass - 0.04, 0); g.add(seat);
  const enc = K.caixa(0.09, 0.62, 0.34, M.estofado, 0.035), up = V3(-Math.sin(tilt), Math.cos(tilt), 0);
  enc.position.copy(V3(-0.21, ass, 0).add(up.clone().multiplyScalar(0.32))); enc.rotation.z = tilt; g.add(enc);
  g.add(K.viga(V3(0.06, ass - 0.08, 0), V3(0.06, 0.04, 0), 0.06));
  g.add(K.viga(V3(-0.25, ass + 0.1, 0), V3(-0.36, 0.04, 0), 0.06));
  for (const x of [0.06, -0.36]) g.add(K.caixa(0.09, 0.05, 0.5, M.quadro, 0.015).translateX(x).translateY(0.025));
  return sombreia(g);
}
const ARC = 0.55; // inclinação dos cabos da barra V do kit (rotation.z = ±0.55)

Object.assign(MOLDES, {
  // ================= tríceps na polia alta: corda / barra reta / barra V / pegada invertida / unilateral =================
  tr_polia: {
    nome: "Tríceps na polia",
    musc: { triceps: 1, antebraco: 0.3 },
    dica: "Cotovelo colado nas costelas e parado: só o antebraço se mexe. Estica tudo embaixo, aperta o tríceps um instante e volta controlando até o antebraço ficar paralelo ao chão.",
    cam: { alvo: V3(0.18, 1.1, 0), dist: 3.7, yaw: 318, pitch: 10 },
    cena(g) {
      const pega = this.p.pega || "corda";
      this.h = null; this.bar = null; this.ref = false;
      g.add(K.piso(2.6, 2.6));
      this.torre = trTorre(g, { alt: 2.0, x: 0.58 });
      this.pg = pega === "corda" ? K.corda() : pega === "v" ? K.barraV() : pega === "estribo" ? K.estribo() : K.barraReta(0.5);
      g.add(this.pg);
    },
    calc(t) {
      zera();
      const p = this.p, pega = p.pega || "corda", uni = !!p.unilateral, inv = !!p.invertida;
      emPe(V3(0, ALT_QUADRIL - 0.02, 0), F0, 0.13);
      gira("neck_01", EX, -0.1); gira("head", EX, -0.08);
      B.pelvis.updateMatrixWorld(true);
      pernas(F0, { abre: 0.14, fora: 0.18, poloFora: 0.2, recuo: 0.02 });
      const th = 0.2 + 1.55 * t, ls = uni ? ["r"] : ["l", "r"], O = {}, S = {}, E = {}, dirs = {};
      for (const l of ["l", "r"]) { // cotovelo parado, encostado na costela, levemente à frente
        S[l] = ondeEsta("upperarm_" + l);
        E[l] = cotovelo(S[l], V3(0.2, -1, zs(l) * 0.04));
        dirs[l] = V3(Math.sin(th), -Math.cos(th), 0);
      }
      const saida = this.torre.saida();
      if (uni) { const l = "l"; braco(l, S[l].clone().add(V3(0.04, -0.47, zs(l) * 0.05)), V3(-0.3, -0.2, zs(l))); } // braço livre: pendurado
      if (pega === "corda") {
        const ch = {}; for (const l of ls) ch[l] = E[l].clone().add(dirs[l].clone().multiplyScalar(COMP.lowerarm_l + 0.085)); // chute da mão (só pra apontar a corda)
        const alvoZ = (l) => zs(l) * (0.075 + 0.09 * (1 - t)); // corda abre embaixo
        const meio = (src) => ls.length === 2 ? media(src.l, src.r) : src[ls[0]].clone().add(V3(0, 0, -zs(ls[0]) * 0.07));
        const folga = V3(0.05 * (1 - t) + 0.02, 0.3, 0);
        const topo = meio(ch).add(folga);
        for (const l of ls) O[l] = trAnte(l, S[l], E[l], dirs[l], unit(topo.clone().sub(ch[l])), 0.012, alvoZ(l));
        const T = meio(O).add(folga), dc = unit(saida.clone().sub(T));
        this.pg.position.copy(T); this.pg.quaternion.setFromUnitVectors(EY, dc); this.pg.updateMatrixWorld(true);
        if (uni) { const l = "r", livre = O[l].clone().add(V3(0, -0.04, -0.14)); this.pg.userData.abre(livre, O[l]); }
        else this.pg.userData.abre(O.l, O.r);
        this.torre.liga(T.clone().add(dc.multiplyScalar(0.05)));
        return;
      }
      if (pega === "estribo") { // alça D numa mão só, palma pra baixo
        const l = ls[0], k = dentro(l).multiplyScalar(inv ? -1 : 1);
        O[l] = trAnte(l, S[l], E[l], dirs[l], k, 0.015, null);
        trBase(this.pg, O[l], V3(0, 0, 1), unit(saida.clone().sub(O[l])));
        this.torre.liga(this.pg.localToWorld(V3(0, 0.075, 0)));
        return;
      }
      // barras rígidas: reta ou V (as duas mãos na mesma barra)
      const gz = pega === "v" ? 0.12 : 0.17;
      for (const l of ["l", "r"]) {
        const k = pega === "v" ? unit(V3(0, Math.cos(ARC), 0).add(dentro(l).multiplyScalar(Math.sin(ARC)))) : dentro(l).multiplyScalar(inv ? -1 : 1);
        O[l] = trAnte(l, S[l], E[l], dirs[l], k, pega === "v" ? 0.0165 : 0.0135, zs(l) * gz);
      }
      const mid = media(O.l, O.r), b = trBase(this.pg, mid, O.l.clone().sub(O.r), unit(saida.clone().sub(mid)));
      if (pega === "v") this.pg.position.add(b.Y.clone().multiplyScalar(0.07));
      this.pg.updateMatrixWorld(true);
      this.torre.liga(this.pg.localToWorld(V3(0, pega === "v" ? 0.04 : 0.024, 0)));
    },
    pose(t) { trCurso(this); this.calc(t); },
  },

  // ================= tríceps testa: barra W / halteres / polia (barra reta) / JM press =================
  tr_testa: {
    nome: "Tríceps testa",
    musc: { triceps: 1, antebraco: 0.3 },
    dica: "Deitado, braços quase verticais e cotovelos apontando pro teto, sem abrir. Só o antebraço dobra: leva a barra até a testa e estica de volta sem mexer o ombro.",
    cam: { alvo: V3(-0.2, 0.85, 0), dist: 3.4, yaw: 298, pitch: 22 },
    cena(g) {
      const tipo = this.p.tipo || "w";
      this.h = null; this.bar = null; this.torre = null; this.ref = false;
      g.add(K.piso(3.4, 2.2)); g.add(banco());
      if (tipo === "jm") { g.add(suportes(-0.62)); this.bar = barra(1); g.add(this.bar); }
      else if (tipo === "w") { this.bar = trBarraW(); g.add(this.bar); }
      else if (tipo === "halter") { this.h = [halter(0.8), halter(0.8)]; g.add(...this.h); }
      else { this.torre = trTorre(g, { alt: 0.28, x: -1.42, ang: Math.PI / 2 }); this.bar = K.barraReta(0.5); g.add(this.bar); }
    },
    calc(t) {
      zera();
      const tipo = this.p.tipo || "w", cab = V3(-1, 0, 0), fr = V3(0, 1, 0);
      corpoEm(V3(0.16, 0.565, 0), cab, fr);
      gira("spine_02", EX, -0.07); gira("spine_03", EX, -0.06); gira("neck_01", EX, 0.12); gira("head", EX, 0.04);
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { const s = zs(l); perna(l, V3(0.6, ALT_TORN, s * 0.31), V3(0.3, 1, s * 0.22)); pe(l, V3(1, 0, s * 0.25)); }
      const S = { l: ondeEsta("upperarm_l"), r: ondeEsta("upperarm_r") };
      if (tipo === "jm") return this.jm(t, S);
      const cfg = { w: { al: 0.22, f0: 0.18, f1: 1.85, gz: 0.07, in: 0.14 }, halter: { al: 0.18, f0: 0.14, f1: 1.9, gz: 0.17, in: 0.05 }, polia: { al: 0.4, f0: 0.36, f1: 2.1, gz: 0.17, in: 0.05 } }[tipo];
      const phi = cfg.f0 + (cfg.f1 - cfg.f0) * t, O = {}, E = {}, Fd = V3(-Math.sin(phi), Math.cos(phi), 0);
      for (const l of ["l", "r"]) E[l] = cotovelo(S[l], V3(-Math.sin(cfg.al), Math.cos(cfg.al), 0).add(dentro(l).multiplyScalar(cfg.in)));
      if (tipo === "w") {
        const X = V3(0, 0, -1), Y = unit(Fd); // X da barra: da mão direita pra esquerda
        const kl = X.clone().multiplyScalar(-0.96).add(Y.clone().multiplyScalar(-0.27)), kr = X.clone().multiplyScalar(0.96).add(Y.clone().multiplyScalar(-0.27));
        O.l = trAnte("l", S.l, E.l, Fd, kl, 0.0135, -0.07); O.r = trAnte("r", S.r, E.r, Fd, kr, 0.0135, 0.07);
        const c = media(O.l, O.r).sub(Y.clone().multiplyScalar(0.02));
        this.bar.position.copy(c); this.bar.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(X, Y, X.clone().cross(Y)));
      } else if (tipo === "halter") {
        const k = V3(-Math.cos(phi), -Math.sin(phi), 0);
        ["l", "r"].forEach((l, i) => { O[l] = trAnte(l, S[l], E[l], Fd, k, 0.016, zs(l) * cfg.gz); seguraHalter(this.h[i], l); });
      } else { // polia: barra reta, pegada por cima
        for (const l of ["l", "r"]) O[l] = trAnte(l, S[l], E[l], Fd, dentro(l), 0.0135, zs(l) * cfg.gz);
        const mid = media(O.l, O.r), sd = this.torre.saida();
        trBase(this.bar, mid, O.l.clone().sub(O.r), unit(sd.clone().sub(mid)));
        this.torre.liga(this.bar.localToWorld(V3(0, 0.024, 0)));
      }
    },
    jm(t, S) { // JM press: meio supino fechado, meio testa; o cotovelo viaja pra frente e a barra desce em arco até o queixo
      const ombro = media(S.l, S.r), alc = COMP.upperarm_l + COMP.lowerarm_l;
      const topo = ombro.clone().add(V3(0.035, alc * 0.97 + 0.035, 0)), baixo = ombro.clone().add(V3(-0.075, 0.2, 0));
      const pos = V3(lerp(topo.x, baixo.x, Math.sin(t * Math.PI / 2)), lerp(topo.y, baixo.y, t), 0);
      this.bar.position.copy(pos); this.bar.rotation.set(0, Math.PI / 2, 0);
      for (const l of ["l", "r"]) agarra(l, { ponto: pos.clone().add(V3(0, 0, zs(l) * 0.1)), R: 0.014, eixo: dentro(l), palma: V3(0.8, 0.55, 0), polo: V3(1, 0.15, zs(l) * 0.35) });
    },
    pose(t) { trCurso(this); this.calc(t); },
  },

  // ================= tríceps francês: halter (2 mãos) / unilateral / polia com corda =================
  tr_frances: {
    nome: "Tríceps francês",
    musc: { triceps: 1, antebraco: 0.25 },
    dica: "Cotovelos apontando pro teto, perto das orelhas e parados. Só o antebraço desce atrás da cabeça até alongar bem o tríceps; depois estica sem abrir os cotovelos.",
    cam: { alvo: V3(-0.05, 1.3, 0), dist: 3.4, yaw: 62, pitch: 10 },
    cena(g) {
      const tipo = this.p.tipo || "halter";
      this.h = null; this.bar = null; this.torre = null; this.ref = false;
      g.add(K.piso(3.0, 2.4));
      if (tipo === "polia") { this.torre = trTorre(g, { alt: 0.3, x: -0.95, ang: Math.PI / 2 }); this.pg = K.corda(); g.add(this.pg); }
      else { trBancoSentado(g); this.h = [halter(tipo === "uni" ? 0.9 : 1.2)]; g.add(this.h[0]); }
    },
    calc(t) {
      zera();
      const tipo = this.p.tipo || "halter", sentado = tipo !== "polia", S = {}, E = {}, O = {};
      if (sentado) {
        const a = 0.12, cab = V3(-Math.sin(a), Math.cos(a), 0), fr = V3(Math.cos(a), Math.sin(a), 0);
        corpoEm(V3(-0.06, 0.565, 0), cab, fr); gira("neck_01", EX, 0.03);
        B.pelvis.updateMatrixWorld(true);
        for (const l of ["l", "r"]) { const s = zs(l); perna(l, V3(0.42, ALT_TORN, s * 0.13), V3(0.5, 1, s * 0.1)); pe(l, F0); }
      } else {
        emPe(V3(0.0, ALT_QUADRIL - 0.03, 0), F0, 0.3); gira("neck_01", EX, -0.25); gira("head", EX, -0.1);
        B.pelvis.updateMatrixWorld(true);
        pernas(F0, { abre: 0.15, fora: 0.2, poloFora: 0.25, recuo: 0.1 });
      }
      for (const l of ["l", "r"]) S[l] = ondeEsta("upperarm_" + l);
      const phi = -0.1 + 2.65 * t, Fd = V3(-Math.sin(phi), Math.cos(phi), 0), ls = tipo === "halter" || tipo === "polia" ? ["l", "r"] : ["r"];
      for (const l of ["l", "r"]) E[l] = cotovelo(S[l], V3(0.1, 1, 0).add(dentro(l).multiplyScalar(tipo === "uni" ? 0.1 : 0.2)));
      if (tipo === "uni") { // mão livre apoiada na coxa
        const l = "l"; trMao(l, V3(0.17, 0.62, zs(l) * 0.17), V3(-0.4, 0.3, zs(l)), V3(1, 0, 0), V3(0, -1, 0));
        const k = V3(-Math.cos(phi), -Math.sin(phi), 0), r = "r";
        O[r] = trAnte(r, S[r], E[r], trDirZ(E[r], Fd, 0.045), k, 0.016, null); seguraHalter(this.h[0], r);
      } else if (tipo === "halter") { // as duas mãos em concha embaixo do disco de cima; o halter pende entre elas
        const pcs = {};
        for (const l of ["l", "r"]) {
          const d = trDirZ(E[l], Fd, zs(l) * 0.085), W = E[l].clone().add(d.multiplyScalar(COMP.lowerarm_l)), dedos = unit(dentro(l).multiplyScalar(1).add(V3(0.15, 0, 0)));
          trMao(l, W, E[l].clone().sub(S[l]).add(V3(0, 0, 1e-4)), dedos, V3(0, 1, 0), 0.1);
          pcs[l] = W.clone().add(dedos.multiplyScalar(0.06));
        }
        const c = media(pcs.l, pcs.r); this.h[0].position.copy(c).add(V3(0, 0.04 - 0.1, 0)); this.h[0].rotation.set(0, 0, Math.PI / 2);
      } else { // polia: corda atrás da cabeça, cabo sobe do pé da torre
        const sd = this.torre.saida(), ch = {};
        for (const l of ["l", "r"]) { const d = trDirZ(E[l], Fd, zs(l) * 0.07); ch[l] = E[l].clone().add(d.multiplyScalar(COMP.lowerarm_l + 0.085)); }
        const cm = media(ch.l, ch.r), dc0 = unit(sd.clone().sub(cm)), T0 = cm.clone().add(dc0.multiplyScalar(0.24));
        for (const l of ls) O[l] = trAnte(l, S[l], E[l], Fd, unit(T0.clone().sub(ch[l])), 0.012, zs(l) * 0.07);
        const m = media(O.l, O.r), dc = unit(sd.clone().sub(m)), T = m.clone().add(dc.clone().multiplyScalar(0.24));
        this.pg.position.copy(T); this.pg.quaternion.setFromUnitVectors(EY, unit(sd.clone().sub(T))); this.pg.updateMatrixWorld(true);
        this.pg.userData.abre(O.l, O.r);
        this.torre.liga(T.clone().add(unit(sd.clone().sub(T)).multiplyScalar(0.05)));
      }
    },
    pose(t) { trCurso(this); this.calc(t); },
  },

  // ================= coice: halter (apoiado no banco) / polia =================
  tr_coice: {
    nome: "Tríceps coice",
    musc: { triceps: 1, antebraco: 0.3 },
    dica: "Tronco inclinado quase paralelo ao chão, cotovelo alto e colado, braço paralelo ao tronco. Só o antebraço vai pra trás até esticar tudo; aperta e volta sem balançar o ombro.",
    cam: { alvo: V3(0.05, 0.85, 0), dist: 3.5, yaw: 318, pitch: 14 },
    cena(g) {
      const polia = !!this.p.polia;
      this.h = null; this.bar = null; this.torre = null; this.ref = false;
      g.add(K.piso(3.2, 2.4));
      if (polia) { this.torre = trTorre(g, { alt: 0.28, x: 1.5, ang: -Math.PI / 2 }); this.pg = K.estribo(); g.add(this.pg); }
      else { const b = banco(1.0); b.position.set(0.5, 0, -0.1); g.add(b); this.h = [halter(0.8)]; g.add(this.h[0]); }
    },
    calc(t) {
      zera();
      const polia = !!this.p.polia, r = "r", l = "l";
      emPe(V3(-0.1, ALT_QUADRIL - 0.2, 0), F0, 0.85); gira("spine_02", EX, 0.14); gira("spine_03", EX, 0.1); gira("neck_01", EX, -0.55); gira("head", EX, -0.1);
      B.pelvis.updateMatrixWorld(true);
      perna(l, V3(0.3, ALT_TORN, -0.15), V3(1, 0.3, -0.1)); pe(l, F0);
      perna(r, V3(-0.5, ALT_TORN, 0.15), V3(1, 0.3, 0.1)); pe(r, F0, 0.08);
      const c = quadroDe("spine_03"), Sr = ondeEsta("upperarm_r"), Sl = ondeEsta("upperarm_l");
      const u = unit(c.up.clone().multiplyScalar(-1).add(V3(0, 0.3, 0))), dn = unit(V3(0, -1, 0).sub(u.clone().multiplyScalar(-u.y)));
      const E = cotovelo(Sr, u), psi = 0.1 + 1.45 * t, Fd = u.clone().multiplyScalar(Math.cos(psi)).add(dn.clone().multiplyScalar(Math.sin(psi)));
      const k = unit(dentro(r).cross(Fd).multiplyScalar(sl_(r))); // pega neutra, palma pra dentro: k = sl*(n x f)
      if (polia) {
        const O = trAnte(r, Sr, E, Fd, k, 0.015, null), sd = this.torre.saida();
        trBase(this.pg, O, k, unit(sd.clone().sub(O))); this.torre.liga(this.pg.localToWorld(V3(0, 0.075, 0)));
        trMao(l, V3(0.28, 0.66, -0.12).add(V3(0, 0, 0)), V3(-0.3, 0.4, -1), V3(0.7, -0.4, 0.3), V3(0.2, 0.3, 1)); // mão livre no joelho da frente
      } else {
        trAnte(r, Sr, E, Fd, k, 0.016, null); seguraHalter(this.h[0], r);
        trMao(l, V3(Sl.x + 0.04, 0.5, Sl.z), V3(-0.5, 0.3, -1), V3(1, 0, 0), V3(0, -1, 0)); // mão livre no banco
      }
    },
    pose(t) { trCurso(this); this.calc(t); },
  },

  // ================= mergulho no banco (mãos no banco atrás, pernas à frente) =================
  tr_mergulho: {
    nome: "Mergulho no banco",
    musc: { triceps: 1, peitoral: 0.4, deltoide: 0.4 },
    dica: "Mãos no banco atrás do corpo, dedos pra frente, pernas à frente. Desce com o tronco rente ao banco até o cotovelo chegar perto de 90° e empurra até quase esticar, cotovelos apontando pra trás.",
    cam: { alvo: V3(-0.1, 0.7, 0), dist: 3.4, yaw: 328, pitch: 12 },
    cena(g) {
      this.h = null; this.bar = null; this.torre = null;
      g.add(K.piso(3.2, 2.2));
      const b = banco(1.18); b.rotation.y = Math.PI / 2; b.position.set(-0.4, 0, 0); g.add(b);
    },
    pose(t) {
      zera();
      const xf = -0.255, k = sen(t);
      const alvoOmbro = V3(xf + 0.09, lerp(0.93, 0.7, k), 0), lean = 0.06;
      const poeTronco = (p) => { zera(); corpoEm(p, V3(-Math.sin(lean), Math.cos(lean), 0), V3(Math.cos(lean), Math.sin(lean), 0)); gira("neck_01", EX, 0.05); };
      let pel = V3(xf + 0.2, alvoOmbro.y - 0.5, 0);
      for (let i = 0; i < 3; i++) { poeTronco(pel); B.pelvis.updateMatrixWorld(true); const m = media(ondeEsta("upperarm_l"), ondeEsta("upperarm_r")); pel.add(alvoOmbro.clone().sub(m)); }
      poeTronco(pel); B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { const s = zs(l); perna(l, V3(pel.x + 0.8, ALT_TORN, s * 0.1), V3(0, 1, s * 0.1)); pe(l, F0, 0.3); }
      for (const l of ["l", "r"]) {
        const W = V3(xf - 0.12, 0.475, zs(l) * 0.2);
        trMao(l, W, V3(-1, 0.1, zs(l) * 0.3), V3(1, 0, 0), V3(0, -1, 0), 0.1);
      }
    },
  },

  // ================= paralelas (tríceps: tronco em pé, cotovelo junto, pernas dobradas atrás) =================
  tr_paralelas: {
    nome: "Paralelas (tríceps)",
    musc: { triceps: 1, peitoral: 0.5, deltoide: 0.4 },
    dica: "Tronco ereto, cotovelos junto do corpo apontando pra trás, pernas dobradas atrás. Desce até o braço ficar paralelo ao chão e empurra até quase travar o cotovelo.",
    cam: { alvo: V3(0, 1.45, 0), dist: 4.0, yaw: 328, pitch: 8 },
    cena(g) {
      this.h = null; this.bar = null; this.torre = null;
      g.add(K.piso(2.6, 2.2)); this.par = K.paralelas({ alt: 1.25, abre: 0.52, comp: 0.8 }); g.add(this.par.g);
    },
    pose(t) {
      zera();
      const alt = 1.25, k = sen(t), alvoOmbro = V3(0.02, lerp(alt + 0.55, alt + 0.2, k), 0), lean = 0.1;
      const poeTronco = (p) => { zera(); corpoEm(p, V3(Math.sin(lean), Math.cos(lean), 0), V3(Math.cos(lean), -Math.sin(lean), 0)); gira("neck_01", EX, -0.1); };
      let pel = V3(-0.05, alvoOmbro.y - 0.5, 0);
      for (let i = 0; i < 3; i++) { poeTronco(pel); B.pelvis.updateMatrixWorld(true); const m = media(ondeEsta("upperarm_l"), ondeEsta("upperarm_r")); pel.add(alvoOmbro.clone().sub(m)); }
      poeTronco(pel); B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { const s = zs(l); perna(l, V3(pel.x - 0.32, pel.y - 0.58, s * 0.04), V3(1, 0, 0)); }
      for (const l of ["l", "r"]) {
        agarra(l, { ponto: V3(0.02, alt, zs(l) * 0.26), eixo: V3(-1, 0, 0), palma: V3(0, -1, 0).add(dentro(l).multiplyScalar(0.35)), R: 0.022,
          polo: V3(-1, 0.1, zs(l) * 0.5) });
      }
    },
  },

  // ================= tríceps na máquina (sentado, braço apoiado no suporte, alavanca) =================
  tr_maquina: {
    nome: "Tríceps na máquina",
    musc: { triceps: 1, antebraco: 0.3 },
    dica: "Costas no encosto, braços apoiados no suporte e cotovelo alinhado com o eixo da máquina. Empurra as alavancas pra baixo até esticar e volta devagar sem tirar o braço do apoio.",
    cam: { alvo: V3(0.1, 0.95, 0), dist: 3.6, yaw: 28, pitch: 12 },
    posCorpo() {
      const a = 0.06; zera();
      corpoEm(V3(-0.06, 0.565, 0), V3(-Math.sin(a), Math.cos(a), 0), V3(Math.cos(a), Math.sin(a), 0));
      B.pelvis.updateMatrixWorld(true);
      for (const l of ["l", "r"]) { const s = zs(l); perna(l, V3(0.42, ALT_TORN, s * 0.13), V3(0.5, 1, s * 0.1)); pe(l, F0); }
      const S = { l: ondeEsta("upperarm_l"), r: ondeEsta("upperarm_r") }, u = unit(V3(0.9, -0.44, 0)), E = {};
      for (const l of ["l", "r"]) E[l] = cotovelo(S[l], u.clone().add(dentro(l).multiplyScalar(0.06)));
      return { S, E, u };
    },
    cena(g) {
      this.h = null; this.bar = null; this.torre = null;
      g.add(K.piso(2.4, 1.8));
      trBancoSentado(g, 0.1);
      const { S, E, u } = this.posCorpo(), Em = media(E.l, E.r);
      // suporte do braço: almofada inclinada sob os úmeros + travessa e dois montantes laterais
      const ang = Math.atan2(u.y, u.x), pad = K.caixa(0.5, 0.07, 0.5, M.estofado, 0.03);
      pad.position.copy(media(media(S.l, S.r), Em)).add(V3(0.435 * 0.075, -0.9 * 0.075, 0)); pad.rotation.z = ang; g.add(pad);
      const pc = pad.position.clone().add(V3(0.0, -0.06, 0));
      g.add(K.viga(V3(pc.x, pc.y, -0.34), V3(pc.x, pc.y, 0.34), 0.06));
      for (const z of [-0.36, 0.36]) { g.add(K.viga(V3(pc.x, pc.y, z), V3(pc.x + 0.06, 0.04, z), 0.06)); g.add(K.caixa(0.5, 0.05, 0.1, M.quadro, 0.015).translateX(pc.x + 0.1).translateY(0.025).translateZ(z)); }
      // pilha de placas atrás do encosto
      const st = K.pilha(); st.position.set(-0.62, 0.04, 0); g.add(st); this.pilha = st;
      g.add(K.viga(V3(-0.36, 0.04, 0), V3(-0.55, 0.04, 0), 0.08));
      // alavancas: cubo no eixo do cotovelo, braço, haste até a pegada e a pegada de borracha
      this.lev = {};
      for (const l of ["l", "r"]) {
        const z = zs(l) * 0.3, hub = K.caixa(0.1, 0.1, 0.07, M.quadro, 0.02); hub.position.set(Em.x, Em.y, z); g.add(hub);
        g.add(K.tubo(V3(Em.x, Em.y, z * 0.9), V3(Em.x, Em.y, z * 1.2), 0.02, M.cromo));
        this.lev[l] = { z, beam: K.tubo(V3(), V3(0, 1, 0), 0.02, M.quadro), strut: K.tubo(V3(), V3(0, 1, 0), 0.012, M.cromo), grip: K.tubo(V3(), V3(0, 1, 0), 0.016, M.borracha) };
        g.add(this.lev[l].beam, this.lev[l].strut, this.lev[l].grip);
      }
      this.Em = Em;
    },
    pose(t) {
      const { S, E } = this.posCorpo(), th = 1.55 - 1.55 * (1 - t) * 1; // t=0 braço esticado, t=1 flexionado
      const ang = lerp(-0.5, 1.35, t); // antebraço: de pra frente-baixo (estendido) a pra cima-frente (flexionado)
      const Fd = V3(Math.cos(ang), Math.sin(ang), 0);
      for (const l of ["l", "r"]) {
        const k = unit(dentro(l).cross(Fd).multiplyScalar(sl_(l)));
        const O = trAnte(l, S[l], E[l], Fd, k, 0.016, zs(l) * 0.17), lv = this.lev[l];
        const a = O.clone().sub(k.clone().multiplyScalar(0.06)), b = O.clone().add(k.clone().multiplyScalar(0.06)), be = V3(a.x, a.y, lv.z);
        K.poe(lv.grip, a, b); K.poe(lv.strut, a, be); K.poe(lv.beam, V3(this.Em.x, this.Em.y, lv.z), be);
      }
      this.pilha.userData.sobe(0.14 * (1 - t));
    },
  },
});
Object.assign(FOCOS, {
  // EMG: ACE / Boehler, Porcari et al. 2011-12 (UW-La Crosse), eletrodos na cabeça longa e lateral, % do triangle push-up (conferido na página da ACE):
  //   kickback 88/87, dips (banco) 87/88, extensão overhead 81/72, corda 81/67, barra 75/59, testa deitado 70/55, supino fechado 61/63 (longa/lateral).
  //   Pegada supinada: cabeça longa 76% vs 69% pronada (dissertação USP 2023, lateral sem mudança). Kholinne 2018 (Acta Orthop Traumatol Turc): cabeça longa
  //   domina com o braço ao lado do corpo, a medial passa a dominar a partir de 90° de elevação do ombro (aqui a medial está junta da lateral).
  //   Maeo 2022 (Med Sci Sports Exerc): extensão overhead hipertrofia mais a cabeça longa que o pushdown. Valores = razão com a cabeça mais ativa (=1).
  //   Antebraço (pega), deltoide, peitoral, trapézio e lombar: ESTIMATIVA (sem número publicado por exercício).
  tr_polia: (p) => p.pega === "corda" ? [["triceps_longa", 1], ["triceps_lateral", 0.83], ["antebraco", 0.3], ["deltoide_post", 0.15]]
    : p.invertida ? [["triceps_longa", 1], ["triceps_lateral", 0.7], ["antebraco", 0.3], ["antebraco_ext", 0.2]]
    : p.unilateral ? [["triceps_longa", 1], ["triceps_lateral", 0.79], ["antebraco", 0.3], ["obliquo", 0.15]]
    : [["triceps_longa", 1], ["triceps_lateral", 0.79], ["antebraco", 0.3], ["deltoide_post", 0.15]],
  tr_testa: (p) => p.tipo === "jm" ? [["triceps_lateral", 1], ["triceps_longa", 0.9], ["peitoral_med", 0.45], ["deltoide_ant", 0.4], ["peitoral_sup", 0.3], ["antebraco", 0.25]]
    : p.tipo === "halter" ? [["triceps_longa", 1], ["triceps_lateral", 0.78], ["antebraco", 0.3], ["deltoide_ant", 0.2], ["biceps", 0.15]]
    : [["triceps_longa", 1], ["triceps_lateral", 0.79], ["antebraco", 0.3], ["deltoide_ant", 0.2]],
  tr_frances: (p) => [["triceps_longa", 1], ["triceps_lateral", 0.9], ["antebraco", 0.25], ["deltoide_ant", 0.3], ["serratil", 0.25], ["trapezio_sup", 0.2]],
  tr_coice: () => [["triceps_longa", 1], ["triceps_lateral", 0.99], ["deltoide_post", 0.5], ["trapezio_med", 0.35], ["lombar", 0.35], ["antebraco", 0.3]],
  tr_mergulho: () => [["triceps_lateral", 1], ["triceps_longa", 0.99], ["deltoide_ant", 0.55], ["peitoral_inf", 0.45], ["serratil", 0.3], ["antebraco", 0.25]],
  tr_paralelas: () => [["triceps_lateral", 1], ["triceps_longa", 0.95], ["peitoral_inf", 0.6], ["deltoide_ant", 0.5], ["peitoral_med", 0.4], ["serratil", 0.3], ["antebraco", 0.3]],
  tr_maquina: () => [["triceps_lateral", 1], ["triceps_longa", 0.9], ["antebraco", 0.3], ["deltoide_ant", 0.2]],
});
Object.assign(VISTA, { tr_polia: 318, tr_testa: 298, tr_frances: 62, tr_coice: 318, tr_mergulho: 328, tr_paralelas: 328, tr_maquina: 28 });
}


window.TREINO3D = { FOCOS, K, fase, RITMO, CICLO, estilo, vista: VISTA, cam: () => camera.position.toArray(), partes: PARTES, ancora: () => { const w = ancoraFoco(); return w ? [w.x, w.y, w.z] : null; }, foco: (l) => { poeFoco(l); for (let i = 0; i < NMUS; i++) FOCO.K[i] = FOCO.alvo[i] > 0 ? 1 : 0; FOCO.esf.value = 1; etqEst.ok = false; quadro(0); }, olha: (de, para) => { camExtra = de ? { de: V3(...de), para: V3(...para) } : null; quadro(0); }, encSinal: (v) => { ENC_SINAL = v; },  usa, MOLDES, quadro, cena, B, ondeEsta, fixa: (t) => { tFixo = t; for (let i = 0; i < 40; i++) quadro(0.05); } };
tamanho(); usa("supino");
$("#carregando").style.opacity = 0; setTimeout(() => { $("#carregando").hidden = true; }, 600);
requestAnimationFrame(laco);
Object.assign(window.TREINO3D, { palco, tamanho, toca: (on) => { tocando = !!on && !reduz; ultimo = performance.now(); quadro(0); } });
window.dispatchEvent(new Event("treino3d-pronto"));
