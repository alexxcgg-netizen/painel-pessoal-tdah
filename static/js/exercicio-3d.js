/* Exercicio em 3/4 de cima ("outro nivel", skill treino-ao-vivo): um corpo 3D so pra todos os exercicios.
   Tronco = aneis elipticos ligados por casco convexo (volume de verdade em qualquer angulo), membros = capsulas
   afinando, cotovelo/joelho por cinematica de 2 segmentos com vetor de polo. Cada quadro monta a lista de pecas e
   desenha de tras pra frente (profundidade da camera). O musculo trabalhado acende no empurrao.
   Cada exercicio = pose(t) + cena (equipamento) + m (musculos). t=0 e a posicao contraida, t=1 o fim da descida.
   Ritmo de serie: desce 2 s, pausa, sobe 1 s, segura em cima. Exercicio fora da lista -> tipo() devolve null. */
var Exercicio = (function () {
  var reduz = typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var GR = Math.PI / 180, cY = Math.cos(-40 * GR), sY = Math.sin(-40 * GR), cP = Math.cos(38 * GR), sP = Math.sin(38 * GR);
  var VC = [-sY * cP, cY * cP, sP]; // aponta pra camera
  var cam = { esc: 1, ox: 0, oy: 0 }, moldura = null, naoMede = false, inst = 0;
  function proj(p) {
    var x = p[0] * cY + p[1] * sY, y = -p[0] * sY + p[1] * cY;
    return [cam.ox + x * cam.esc, cam.oy + (y * sP - p[2] * cP) * cam.esc, y * cP + p[2] * sP];
  }
  function marca(q, r) {
    if (!moldura || naoMede) return; r = r || 0;
    moldura[0] = Math.min(moldura[0], q[0] - r); moldura[1] = Math.min(moldura[1], q[1] - r);
    moldura[2] = Math.max(moldura[2], q[0] + r); moldura[3] = Math.max(moldura[3], q[1] + r);
  }
  // vetores
  function sub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function soma() { var r = [0, 0, 0]; for (var i = 0; i < arguments.length; i++) { r[0] += arguments[i][0]; r[1] += arguments[i][1]; r[2] += arguments[i][2]; } return r; }
  function mul(a, k) { return [a[0] * k, a[1] * k, a[2] * k]; }
  function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function cross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
  function nor(a) { var l = Math.hypot(a[0], a[1], a[2]) || 1; return mul(a, 1 / l); }
  function mix(a, b, k) { return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k]; }
  function arco(a, b, k) { // gira a ate b (direcoes), velocidade angular constante
    var w = Math.acos(Math.max(-1, Math.min(1, dot(a, b)))), s = Math.sin(w);
    return s < 1e-4 ? a : nor(soma(mul(a, Math.sin((1 - k) * w) / s), mul(b, Math.sin(k * w) / s)));
  }
  function lados(fn) { return [fn(-1, 0), fn(1, 1)]; }
  function chao(ang) { return [Math.cos(ang * GR), Math.sin(ang * GR), 0]; }
  var Z = [0, 0, 1], BAIXO = [0, 0, -1];
  function ik(S, H, l1, l2, polo) {
    var v = sub(H, S), d = Math.min(Math.hypot(v[0], v[1], v[2]), l1 + l2 - 0.01), n = nor(v);
    var a = (l1 * l1 - l2 * l2 + d * d) / (2 * d), h = Math.sqrt(Math.max(0, l1 * l1 - a * a));
    var P = nor(sub(polo, mul(n, dot(polo, n))));
    return soma(S, mul(n, a), mul(P, h));
  }
  var f1 = function (v) { return v.toFixed(1); };
  function circulo2(q, R) { return "M" + f1(q[0] - R) + " " + f1(q[1]) + "a" + f1(R) + " " + f1(R) + " 0 1 0 " + f1(2 * R) + " 0a" + f1(R) + " " + f1(R) + " 0 1 0 " + f1(-2 * R) + " 0Z"; }
  function capsula(A, B, r1, r2) {
    var a = proj(A), b = proj(B), dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy), R1 = r1 * cam.esc, R2 = r2 * cam.esc;
    marca(a, R1); marca(b, R2);
    if (l < Math.abs(R1 - R2) + 0.4) return l < 0.01 || R1 >= R2 ? circulo2(a, R1) : circulo2(b, R2);
    var nx = -dy / l, ny = dx / l;
    return "M" + f1(a[0] + nx * R1) + " " + f1(a[1] + ny * R1) + "L" + f1(b[0] + nx * R2) + " " + f1(b[1] + ny * R2) +
      "A" + f1(R2) + " " + f1(R2) + " 0 0 0 " + f1(b[0] - nx * R2) + " " + f1(b[1] - ny * R2) +
      "L" + f1(a[0] - nx * R1) + " " + f1(a[1] - ny * R1) + "A" + f1(R1) + " " + f1(R1) + " 0 0 0 " + f1(a[0] + nx * R1) + " " + f1(a[1] + ny * R1) + "Z";
  }
  function suave2(p) { // contorno fechado suave pelos pontos medios (2D)
    var n = p.length, m = function (i) { var a = p[i % n], b = p[(i + 1) % n]; return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]; };
    var s = "M" + f1(m(0)[0]) + " " + f1(m(0)[1]);
    for (var i = 1; i <= n; i++) { var c = p[i % n], q = m(i); s += "Q" + f1(c[0]) + " " + f1(c[1]) + " " + f1(q[0]) + " " + f1(q[1]); }
    return s + "Z";
  }
  function suave(pts3) { var p = pts3.map(proj); p.forEach(function (q) { marca(q); }); return suave2(p); }
  function poli(pts3) { return "M" + pts3.map(function (p) { var q = proj(p); marca(q); return f1(q[0]) + " " + f1(q[1]); }).join("L") + "Z"; }
  function casco(p) { // casco convexo 2D (cadeia monotona)
    p = p.slice().sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
    var x = function (o, a, b) { return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]); }, lo = [], hi = [];
    p.forEach(function (q) { while (lo.length > 1 && x(lo[lo.length - 2], lo[lo.length - 1], q) <= 0) lo.pop(); lo.push(q); });
    for (var i = p.length - 1; i >= 0; i--) { var q = p[i]; while (hi.length > 1 && x(hi[hi.length - 2], hi[hi.length - 1], q) <= 0) hi.pop(); hi.push(q); }
    lo.pop(); hi.pop(); return lo.concat(hi);
  }
  function base(n) { var a = nor(cross(n, Math.abs(n[2]) < 0.9 ? Z : [1, 0, 0])); return [a, cross(n, a)]; }
  function disco(C, r, n) { var b = base(n), pts = []; for (var i = 0; i < 24; i++) { var a = i / 24 * Math.PI * 2; pts.push(soma(C, mul(b[0], Math.cos(a) * r), mul(b[1], Math.sin(a) * r))); } return poli(pts); }
  function anel(C, R, F, w, d) { var p = []; for (var i = 0; i < 18; i++) { var a = i / 18 * Math.PI * 2; p.push(proj(soma(C, mul(R, Math.cos(a) * w), mul(F, Math.sin(a) * d)))); } p.forEach(function (q) { marca(q); }); return p; }
  var prof = function (p) { return proj(p)[2]; };

  // ---- equipamento ----
  function banco(L, g, A, B, W, T) { // banco reto: A->B no chao (x,y), estofado em T
    var a = nor(sub(B, A)), w = mul(nor([-a[1], a[0], 0]), W), up = [0, 0, T], dn = [0, 0, T - 7];
    var c = [soma(A, w), soma(B, w), sub(B, w), sub(A, w)];
    var pes = [mix(A, B, 0.1), mix(A, B, 0.88)], s = "";
    pes.forEach(function (p) { [-0.7, 0.7].forEach(function (k) { var q = soma(p, mul(w, k)); s += '<path d="' + capsula(q, soma(q, [0, 0, T - 7]), 2.2, 2.2) + '"/>'; }); });
    s += '<path d="' + capsula(soma(pes[0], [0, 0, 3]), soma(pes[1], [0, 0, 3]), 1.8, 1.8) + '"/>';
    L.fundo.push('<g fill="#262c33">' + s + "</g>");
    var lado = prof(c[0]) > prof(c[3]) ? [c[0], c[1]] : [c[3], c[2]], fim = prof(B) > prof(A) ? [c[1], c[2]] : [c[0], c[3]];
    L.fundo.push('<path fill="#15191e" d="' + poli([soma(lado[0], up), soma(lado[1], up), soma(lado[1], dn), soma(lado[0], dn)]) + '"/>');
    L.fundo.push('<path fill="#101317" d="' + poli([soma(fim[0], up), soma(fim[1], up), soma(fim[1], dn), soma(fim[0], dn)]) + '"/>');
    L.fundo.push('<path fill="url(#gEst' + g + ')" d="' + suave(c.map(function (p) { return soma(p, up); })) + '"/>');
    L.chao.push(c[0], c[1], c[2], c[3]);
  }
  function encosto(L, g, P0, U, len, R, W, Fn) { // estofado inclinado
    var t = [soma(P0, mul(R, W)), soma(P0, mul(U, len), mul(R, W)), soma(P0, mul(U, len), mul(R, -W)), soma(P0, mul(R, -W))];
    var b = t.map(function (p) { return sub(p, mul(Fn, 7)); });
    L.fundo.push('<path fill="#262c33" d="' + capsula(soma(P0, mul(U, len * 0.55), mul(Fn, -7)), [P0[0] + U[0] * len * 0.3, 0, 3], 2.4, 2.4) + '"/>');
    var k = prof(t[0]) > prof(t[3]) ? [0, 1] : [3, 2];
    L.fundo.push('<path fill="#15191e" d="' + poli([t[k[0]], t[k[1]], b[k[1]], b[k[0]]]) + '"/>');
    L.fundo.push('<path fill="#101317" d="' + poli([t[1], t[2], b[2], b[1]]) + '"/>');
    L.fundo.push('<path fill="url(#gEst' + g + ')" d="' + suave(t) + '"/>');
  }
  // bloco orientado (assento, encosto, plataforma, step): C centro, a/b/c meios-eixos; a face +c e o estofado
  function caixa(L, g, C, a, b, c, frente) {
    var s = "", eixos = [a, b, c];
    for (var i = 0; i < 3; i++) for (var sg = -1; sg <= 1; sg += 2) {
      var n = mul(eixos[i], sg), u = eixos[(i + 1) % 3], w = eixos[(i + 2) % 3], vn = dot(nor(n), VC);
      if (vn <= 0.01) continue;
      var F0 = soma(C, n), cor = i === 2 && sg > 0 ? "url(#gEst" + g + ")" : vn > 0.55 ? "#1d232a" : "#13171c";
      s += '<path fill="' + cor + '" d="' + poli([soma(F0, u, w), soma(F0, u, mul(w, -1)), soma(F0, mul(u, -1), mul(w, -1)), soma(F0, mul(u, -1), w)]) + '"/>';
    }
    if (frente) L.add(prof(C), s); else L.fundo.push(s);
    [-1, 1].forEach(function (p) { [-1, 1].forEach(function (q) { L.chao.push(soma(C, mul(a, p), mul(b, q), mul(c, -1))); }); });
  }
  function rolo(L, A, B, r) { L.add(prof(mix(A, B, 0.5)), '<path fill="#1b2026" stroke="#323a44" stroke-width=".8" d="' + capsula(A, B, r, r) + '"/>'); }
  function haste(L, A, B, r, fundo) { var h = '<path fill="#262c33" d="' + capsula(A, B, r || 2, r || 2) + '"/>'; if (fundo) L.fundo.push(h); else L.add(prof(mix(A, B, 0.5)), h); }
  function torre(L, P, h) { // coluna da polia (nao entra no enquadramento)
    naoMede = true;
    L.fundo.push('<path fill="#1f252b" d="' + capsula(P, soma(P, [0, 0, h]), 4.2, 4.2) + '"/><path fill="#2d343c" d="' + capsula(soma(P, [0, 0, h - 6]), soma(P, [0, 0, h - 1]), 6, 6) + '"/>');
    naoMede = false;
  }
  function anilha(L, g, C, n, r) {
    var a = soma(C, mul(n, -1.4)), b = soma(C, mul(n, 1.4)), pa = prof(a), pb = prof(b), fr = pa > pb ? a : b, tr = pa > pb ? b : a;
    L.add(prof(C), '<path fill="#14181d" d="' + disco(tr, r, n) + '"/><path fill="#252c34" stroke="#76818b" stroke-width=".9" d="' + disco(fr, r, n) + '"/><path fill="url(#gMetal' + g + ')" d="' + disco(fr, r * 0.22, n) + '"/>');
  }
  function barra(L, g, A, B, r) { L.add(prof(mix(A, B, 0.5)), '<path fill="url(#gMetal' + g + ')" d="' + capsula(A, B, r || 1.5, r || 1.5) + '"/>'); }
  // barra com anilhas: C meio, e eixo, w meia-pegada (corta a barra ali pra ordenar certo com as maos)
  function barraAnilhas(L, g, C, e, w, r, fim) {
    r = r || 21; fim = fim || 64;
    [[-fim, -w], [-w, w], [w, fim]].forEach(function (s) { barra(L, g, soma(C, mul(e, s[0])), soma(C, mul(e, s[1])), 1.5); });
    var p1 = fim - 18, p2 = fim - 13;
    [-1, 1].forEach(function (s) { anilha(L, g, soma(C, mul(e, s * p1)), e, r); anilha(L, g, soma(C, mul(e, s * p2)), e, r * 0.76); });
  }
  function halter(L, g, C, e, meio, r) {
    barra(L, g, soma(C, mul(e, -meio - 3)), soma(C, mul(e, meio + 3)), 1.5);
    anilha(L, g, soma(C, mul(e, meio)), e, r); anilha(L, g, soma(C, mul(e, -meio)), e, r);
  }
  function cabo(L, A, B) { L.add(prof(mix(A, B, 0.5)) - 0.5, '<path d="M' + f1(proj(A)[0]) + " " + f1(proj(A)[1]) + "L" + f1(proj(B)[0]) + " " + f1(proj(B)[1]) + '" stroke="#cfd8df" stroke-opacity=".5" stroke-width=".9" fill="none"/>'); }
  function meio(j) { return mix(j.mao[0], j.mao[1], 0.5); }
  function halteres(L, g, j, e, r) { j.mao.forEach(function (m) { halter(L, g, m, e, 5.5, r || 6.5); }); }
  function assento(L, g, j, frente, larg) { caixa(L, g, soma([j.H[0], j.H[1], j.H[2] - 13.5], mul(j.f, frente || 10)), mul(j.f, larg || 20), mul(j.R, 16), [0, 0, 4]); haste(L, [j.H[0], j.H[1], j.H[2] - 17], [j.H[0], j.H[1], 0], 2.6, true); }
  function costas(L, g, j, alto) { caixa(L, g, soma(j.H, mul(j.U, alto || 30), mul(j.F, -14.5)), mul(j.U, alto || 30), mul(j.R, 15), mul(j.F, 4)); }
  function colchonete(L, g, j, ini, fim) { var c = (ini + fim) / 2; caixa(L, g, soma([j.H[0], j.H[1], 0.8], mul(j.f, c)), mul(j.f, (fim - ini) / 2), mul(j.R, 19), [0, 0, 0.8]); }

  // ---- corpo ----
  var TRONCO = [[-0.05, 14.5, 9.5, 0], [0.36, 13, 9, 0.6], [0.7, 17, 11, 2], [0.92, 17.5, 8.6, 0.3], [1.02, 8, 6.4, 0]];
  // musculo do tronco que acende: [altura no tronco, frente(+)/costas(-), raio lateral, raio vertical, lado da pele]
  var BLOCO = { peito: [0.74, 12.5, 15, 8, 1], abdomen: [0.3, 10, 8.5, 13, 1], costas: [0.6, -9.5, 16, 14, -1], trapezio: [0.95, -5.5, 12, 6, -1], gluteo: [0.02, -8.5, 12.5, 8, -1] };
  function figura(L, j, g, br) {
    var H = j.H, U = j.U, F = j.F, R = j.R, C = j.L || 54;
    var an = TRONCO.map(function (a) { return anel(soma(H, mul(U, C * a[0]), mul(F, a[3])), R, F, a[1], a[2]); });
    var dT = prof(soma(H, mul(U, C * 0.5))), s = "";
    for (var i = 0; i < 4; i++) s += '<path d="' + suave2(casco(an[i].concat(an[i + 1]))) + '"/>';
    L.add(dT, '<g fill="url(#gCorpo' + g + ')">' + s + "</g>");
    Object.keys(BLOCO).forEach(function (k) {
      var b = BLOCO[k], v = br[k] || 0;
      if (v < 0.01) return;
      var ve = dot(mul(F, b[4]), VC) > -0.2;
      if (!ve && !br.atraves) return;
      var cp = soma(H, mul(U, C * b[0]), mul(F, b[1])), pp = [];
      for (var q = 0; q < 10; q++) { var a = q / 10 * Math.PI * 2; pp.push(soma(cp, mul(R, b[2] * Math.cos(a)), mul(U, b[3] * Math.sin(a)), mul(F, -3 * b[4] * Math.cos(a) * Math.cos(a)))); }
      L.add(dT + 0.5, '<path fill="url(#gPeito' + g + ')" opacity="' + (v * (ve ? 1 : 0.55)).toFixed(2) + '" d="' + suave(pp) + '"/>');
    });
    var pele = "url(#gPele" + g + ")", longe = "url(#gLonge" + g + ")", est = ' stroke="rgba(4,8,12,.38)" stroke-width=".7"';
    var tom = function (d) { return d < dT - 3 ? longe : pele; };
    var acende = function (v, A, B, r1, r2) { return v > 0.01 ? '<path fill="url(#gTri' + g + ')" opacity="' + v.toFixed(2) + '" d="' + capsula(A, B, r1, r2) + '"/>' : ""; };
    var nb = soma(H, mul(U, C)), cab = j.cabeca;
    L.add(prof(mix(nb, cab, 0.4)), '<path fill="' + pele + '" d="' + capsula(nb, mix(nb, cab, 0.6), 5.4, 4.8) + '"/>');
    L.add(prof(cab), '<path fill="' + pele + '"' + est + ' d="' + capsula(soma(cab, mul(U, -2.2)), soma(cab, mul(U, 2)), 7.4, 8.6) + '"/>');
    for (var sd = 0; sd < 2; sd++) {
      var on = br.lado == null || br.lado === sd, v = function (k) { return on ? br[k] || 0 : 0; };
      var o = j.ombro[sd], c = j.cot[sd], m = j.mao[sd];
      var d1 = prof(mix(o, c, 0.5)), d2 = prof(mix(c, m, 0.5)), ax = j.eixoMao ? j.eixoMao[sd] : nor(sub(m, c));
      L.add(d1, '<path fill="' + tom(d1) + '"' + est + ' d="' + capsula(o, c, 6, 4.6) + '"/>' +
        acende(Math.max(v("triceps"), v("biceps")), mix(o, c, 0.28), mix(o, c, 0.92), 4.4, 3.6));
      L.add(prof(o) - 0.2, '<path fill="' + tom(d1) + '" d="' + capsula(soma(o, mul(U, -2)), soma(o, mul(U, 1)), 6.6, 6.2) + '"/>' +
        acende(v("ombro"), soma(o, mul(U, -2.5)), soma(o, mul(U, 0.6)), 6.2, 5.6));
      L.add(d2, '<path fill="' + tom(d2) + '"' + est + ' d="' + capsula(c, m, 4.6, 3.5) + '"/>');
      L.add(prof(m) + 3, '<path fill="' + tom(d2) + '"' + est + ' d="' + capsula(soma(m, mul(ax, -3.2)), soma(m, mul(ax, 3.2)), 3.9, 3.9) + '"/>');
      var qd = j.quadril[sd], jo = j.joelho[sd], tz = j.tornozelo[sd], pt = j.ponta[sd];
      var d3 = prof(mix(qd, jo, 0.5)), d4 = prof(mix(jo, tz, 0.5));
      L.add(d3, '<path fill="' + tom(d3) + '"' + est + ' d="' + capsula(qd, jo, 8, 5.6) + '"/>' +
        acende(Math.max(v("quadriceps"), v("posterior")), mix(qd, jo, 0.2), mix(qd, jo, 0.85), 6.6, 4.6) +
        acende(v("abdutor"), mix(qd, jo, 0.02), mix(qd, jo, 0.45), 7.2, 6));
      L.add(d4, '<path fill="' + tom(d4) + '"' + est + ' d="' + capsula(jo, tz, 5.4, 3.8) + '"/>' +
        acende(v("panturrilha"), mix(jo, tz, 0.08), mix(jo, tz, 0.55), 4.8, 3.6));
      L.add(prof(mix(tz, pt, 0.5)), '<path fill="' + tom(d4) + '"' + est + ' d="' + capsula(tz, pt, 3.6, 3) + '"/>');
    }
    L.chao.push(H, cab, j.ombro[0], j.ombro[1], j.mao[0], j.mao[1], j.tornozelo[0], j.tornozelo[1], j.ponta[0], j.ponta[1]);
  }

  // ---- montagem do corpo ----
  // corpo em qualquer orientacao: H quadril, U pra cima do tronco, F pra frente do peito (lado 0 = -R, lado 1 = +R)
  function corpo(H, U, F) {
    U = nor(U); F = nor(sub(F, mul(U, dot(F, U))));
    var R = cross(F, U);
    return { H: H, U: U, F: F, R: R, L: 54, cabeca: soma(H, mul(U, 66), mul(F, 1.5)),
      ombro: [soma(H, mul(U, 48.5), mul(R, -17)), soma(H, mul(U, 48.5), mul(R, 17))], quadril: [soma(H, mul(R, -9)), soma(H, mul(R, 9))] };
  }
  function deitado() { // de costas no banco, cabeca pra -x
    return { H: [58, 0, 56], U: [-1, 0, 0], F: [0, 0, 1], R: [0, 1, 0], f: [1, 0, 0], L: 54, cabeca: [-8, 0, 57],
      ombro: [[9, -17, 58], [9, 17, 58]], quadril: [[58, -9, 55], [58, 9, 55]], joelho: [[97, -15, 50], [97, 15, 50]],
      tornozelo: [[101, -19, 5], [101, 19, 5]], ponta: [[112, -20, 2.5], [112, 20, 2.5]] };
  }
  // em pe/sentado virado pro angulo (graus no chao), tronco inclinado pra frente, quadril recuado
  function emPe(ang, inclina, alt, recua) {
    var f = chao(ang), j = corpo(soma([0, 0, alt], mul(f, recua || 0)), soma(Z, mul(f, Math.tan(inclina * GR))), f);
    j.f = f; return j;
  }
  // de barriga pra baixo, reto do tornozelo (base) ao ombro, th graus acima do chao
  function prono(th, ang, base) {
    var f = chao(ang), c = Math.cos(th * GR), s = Math.sin(th * GR);
    var U = soma(mul(f, c), [0, 0, s]), F = soma(mul(f, s), [0, 0, -c]), j = corpo(soma(base, mul(U, 88.5)), U, F);
    j.f = f;
    pernas(j, lados(function (sd) { return soma(base, mul(j.R, sd * 8)); }), F, nor(soma(F, mul(U, -0.3))));
    return j;
  }
  // de costas no chao/no banco: tronco th graus acima da horizontal, cabeca pra -f
  function supino(ang, th, H) {
    var f = chao(ang), c = Math.cos(th * GR), s = Math.sin(th * GR), j = corpo(H, soma(mul(f, -c), [0, 0, s]), soma(mul(f, s), [0, 0, c]));
    j.f = f; return j;
  }
  function pernas(j, pes, polo, pe) { // pes = tornozelos; polo = pra onde o joelho aponta; pe = pra onde os dedos apontam
    j.tornozelo = pes;
    j.joelho = pes.map(function (p, i) { return ik(j.quadril[i], p, 44, 45, typeof polo === "function" ? polo(i ? 1 : -1) : polo); });
    j.ponta = pes.map(function (p, i) { var d = Array.isArray(pe) && Array.isArray(pe[0]) ? pe[i] : pe || nor(soma(j.f, [0, 0, -0.23])); return soma(p, mul(d, 11.3)); });
    return j;
  }
  function emPeNoChao(j, abre, frente) { return pernas(j, lados(function (s) { return soma([j.H[0], j.H[1], 5], mul(j.f, frente || 0), mul(j.R, s * (abre || 13))); }), function (s) { return soma(j.f, mul(j.R, s * 0.2)); }); }
  function sentado(j, abre) { // coxas pra frente na altura do quadril, canelas descendo pro chao
    var a = abre || 0;
    j.joelho = lados(function (s) { return soma(j.H, mul(j.f, 40), mul(j.R, s * (11 + a)), [0, 0, -5]); });
    j.tornozelo = lados(function (s) { return soma([j.H[0], j.H[1], 5], mul(j.f, 46), mul(j.R, s * (13 + a))); });
    j.ponta = j.tornozelo.map(function (p) { return soma(p, mul(j.f, 11), [0, 0, -2.5]); });
    return j;
  }
  function bracos(j, maos, polo, eixo) {
    j.mao = maos;
    j.cot = maos.map(function (m, i) { return ik(j.ombro[i], m, 29, 27, typeof polo === "function" ? polo(i ? 1 : -1) : polo); });
    if (eixo) j.eixoMao = [eixo, eixo];
    return j;
  }
  function ombros(j) { return mix(j.ombro[0], j.ombro[1], 0.5); }
  // braco pendurado reto (terra, stiff, encolhimento, avanco...)
  function pendura(j, abre, frente) { return bracos(j, lados(function (s, i) { return soma(j.ombro[i], [0, 0, -53], mul(j.R, s * (abre || 3)), mul(j.f, frente || 1)); }), function (s) { return soma(mul(j.f, -1), mul(j.R, s * 0.4)); }, j.f); }
  // levantamento (terra/stiff/agachamento): t interpola inclinacao, altura e recuo do quadril
  function levanta(t, ang, a, z, r) { return emPe(ang, a[0] + (a[1] - a[0]) * t, z[0] + (z[1] - z[0]) * t, r[0] + (r[1] - r[0]) * t); }

  // ---- exercicios ----
  var EX = {
    // peito
    supino_barra: { m: ["peito", "triceps"],
      pose: function (t) {
        var j = deitado(), bx = 10 + t * 12, bz = 116 - t * 45;
        j.mao = [[bx, -30, bz], [bx, 30, bz]]; j.eixoMao = [[0, 1, 0], [0, 1, 0]];
        j.cot = [ik(j.ombro[0], j.mao[0], 29, 27, [0.45, -1, -0.8]), ik(j.ombro[1], j.mao[1], 29, 27, [0.45, 1, -0.8])];
        return j;
      },
      cena: function (L, j, g) { banco(L, g, [-24, 0, 0], [66, 0, 0], 12, 47); barraAnilhas(L, g, meio(j), [0, 1, 0], 30); } },
    supino_inclinado: { m: ["peito", "ombro"],
      pose: function (t) {
        var U = nor([-0.788, 0, 0.616]), F = nor([0.616, 0, 0.788]), R = [0, 1, 0], H = [60, 0, 56];
        var j = { H: H, U: U, F: F, R: R, f: [1, 0, 0], L: 54, cabeca: soma(H, mul(U, 66)), ombro: [soma(H, mul(U, 48.5), mul(R, -17)), soma(H, mul(U, 48.5), mul(R, 17))],
          quadril: [[60, -9, 55], [60, 9, 55]], joelho: [[100, -14, 53], [100, 14, 53]], tornozelo: [[104, -18, 5], [104, 18, 5]], ponta: [[115, -19, 2.5], [115, 19, 2.5]] };
        var dir = nor(soma(mul(F, 0.55), [0, 0, 0.45]));
        j.mao = [-1, 1].map(function (s, i) { var o = j.ombro[i]; return mix(soma(o, mul(dir, 53), [0, -s * 6, 0]), soma(o, mul(dir, 9), [0, s * 8, 0]), t); });
        j.cot = [-1, 1].map(function (s, i) { return ik(j.ombro[i], j.mao[i], 29, 27, soma(mul(R, s), mul(F, -0.7), mul(U, -0.3))); });
        j.eixoMao = [R, R]; return j;
      },
      cena: function (L, j, g) {
        banco(L, g, [44, 0, 0], [80, 0, 0], 12, 47);
        encosto(L, g, soma(j.H, mul(j.F, -10), mul(j.U, -6)), j.U, 66, j.R, 12, j.F);
        halteres(L, g, j, [0, 1, 0], 7);
      } },
    supino_halter: { m: ["peito", "triceps"],
      pose: function (t) {
        return bracos(deitado(), lados(function (s) { return [12 + t * 3, s * (20 + t * 14), 110 - t * 44]; }), function (s) { return [0.3, s, -0.8]; }, [0, 1, 0]);
      },
      cena: function (L, j, g) { banco(L, g, [-24, 0, 0], [66, 0, 0], 12, 47); halteres(L, g, j, [0, 1, 0], 7); } },
    supino_declinado: { m: ["peito", "triceps"],
      pose: function (t) {
        var j = corpo([58, 0, 60], [-0.954, 0, -0.3], [-0.3, 0, 0.954]); j.f = [1, 0, 0];
        pernas(j, lados(function (s) { return soma([98, 0, 30], mul(j.R, s * 12)); }), [0.4, 0, 1], nor([0.6, 0, -0.8]));
        var c = [15 + t * 5, 0, 96 - t * 32];
        return bracos(j, lados(function (s) { return soma(c, mul(j.R, s * 30)); }), function (s) { return soma(mul(j.R, s), [0.3, 0, -0.6]); }, j.R);
      },
      cena: function (L, j, g) {
        caixa(L, g, soma(j.H, mul(j.U, 26), mul(j.F, -13)), mul(j.U, 40), mul(j.R, 12), mul(j.F, 3.5));
        haste(L, soma(j.H, mul(j.U, 22), mul(j.F, -17)), [36, 0, 0], 2.6, true);
        haste(L, [104, 0, 33], [104, 0, 0], 2.4, true);
        rolo(L, [104, -18, 37], [104, 18, 37], 5);
        barraAnilhas(L, g, meio(j), j.R, 30);
      } },
    crucifixo: { m: ["peito"],
      pose: function (t) {
        var j = deitado(), th = (-10 + t * 86) * GR;
        j.mao = [-1, 1].map(function (s) { return [15, s * (17 + 50 * Math.sin(th)), 58 + 50 * Math.cos(th)]; });
        j.cot = [-1, 1].map(function (s, i) { return ik(j.ombro[i], j.mao[i], 29, 27, [0.2, s * 0.3, -1]); });
        j.eixoMao = [[1, 0, 0], [1, 0, 0]]; return j;
      },
      cena: function (L, j, g) { banco(L, g, [-24, 0, 0], [66, 0, 0], 12, 47); j.mao.forEach(function (m) { halter(L, g, m, [1, 0, 0], 6, 6.5); }); } },
    crossover: { m: ["peito"],
      pose: function (t) {
        var j = emPe(82, 14, 92), f = j.f, R = j.R;
        pernas(j, [soma(mul(R, -11), mul(f, 14), [0, 0, 5]), soma(mul(R, 11), mul(f, -14), [0, 0, 5])], f);
        j.mao = [-1, 1].map(function (s, i) {
          var aberta = soma(j.ombro[i], mul(R, s * 44), mul(j.U, 10), mul(f, 8)), fechada = soma(j.H, mul(j.U, 24), mul(f, 42), mul(R, s * 4));
          return soma(mix(fechada, aberta, t), mul(f, Math.sin(Math.PI * t) * 8));
        });
        j.cot = [-1, 1].map(function (s, i) { return ik(j.ombro[i], j.mao[i], 29, 27, soma(mul(R, s), mul(f, -0.6), [0, 0, -0.2])); });
        j.eixoMao = [Z, Z]; j.polia = [-1, 1].map(function (s) { return soma(mul(R, s * 80), mul(f, -16), [0, 0, 196]); });
        return j;
      },
      cena: function (L, j, g) {
        [-1, 1].forEach(function (s, i) { torre(L, soma(mul(j.R, s * 84), mul(j.f, -18)), 206); cabo(L, j.polia[i], j.mao[i]); });
      } },
    peck_deck: { m: ["peito"],
      pose: function (t) {
        var j = sentado(emPe(70, -4, 57)), ph = (-18 + t * 112) * GR;
        j.cot = lados(function (s, i) { return soma(j.ombro[i], mul(nor(soma(mul(j.F, Math.cos(ph)), mul(j.R, s * Math.sin(ph)), mul(j.U, -0.08))), 29)); });
        j.mao = j.cot.map(function (c) { return soma(c, mul(j.U, 24), mul(j.F, 3)); });
        j.empurra = lados(function (s) { return nor(soma(mul(j.F, Math.sin(ph)), mul(j.R, -s * Math.cos(ph)))); });
        j.eixoMao = [j.F, j.F]; return j;
      },
      cena: function (L, j, g) {
        costas(L, g, j); assento(L, g, j);
        j.cot.forEach(function (c, i) { var e = j.empurra[i]; rolo(L, soma(c, mul(e, 5.5), mul(j.U, -3)), soma(j.mao[i], mul(e, 5.5), mul(j.U, -2)), 4.4); });
      } },
    flexao: { m: ["peito", "triceps"], atraves: true,
      pose: function (t) {
        var j = prono(20 - 15 * t, 140, [0, 0, 9]), P = soma([0, 0, 4], mul(j.f, 126));
        return bracos(j, lados(function (s) { return soma(P, mul(j.R, s * 24)); }), function (s) { return soma(mul(j.R, s), mul(j.U, -0.7), [0, 0, 0.3]); }, j.f);
      },
      cena: function (L, j, g) { colchonete(L, g, { H: [0, 0, 0], f: j.f, R: j.R }, -10, 150); } },
    // triceps
    triceps_corda: { m: ["triceps"],
      pose: function (t) {
        var j = emPe(130, 16, 92), f = j.f, R = j.R, U = j.U, F = j.F;
        pernas(j, [soma(mul(R, -10), mul(f, 8), [0, 0, 5]), soma(mul(R, 10), mul(f, -6), [0, 0, 5])], f);
        j.cot = [-1, 1].map(function (s, i) { return soma(j.ombro[i], mul(nor(soma(mul(U, -1), mul(f, 0.18), mul(R, -s * 0.1))), 29)); });
        var ph = (10 + t * 102) * GR, dir = soma(mul(U, -Math.cos(ph)), mul(F, Math.sin(ph)));
        j.mao = [-1, 1].map(function (s, i) { return soma(j.cot[i], mul(dir, 27), mul(R, s * (1 - t) * 4)); });
        j.eixoMao = [Z, Z]; j.polia = soma(mul(f, 52), [0, 0, 198]); return j;
      },
      cena: function (L, j, g) {
        torre(L, mul(j.f, 58), 206);
        var m = meio(j), n = soma(m, mul(nor(sub(j.polia, m)), 10));
        cabo(L, j.polia, n);
        j.mao.forEach(function (mo) { L.add(prof(mix(mo, n, 0.5)) + 1, '<path fill="#d8c79a" d="' + capsula(n, mo, 1.5, 1.8) + '"/>'); });
      } },
    triceps_testa: { m: ["triceps"],
      pose: function (t) {
        var j = deitado(), al = Math.atan2(-0.22, 1), ph = al - t * 118 * GR, d = [Math.sin(ph), 0, Math.cos(ph)];
        j.cot = [-1, 1].map(function (s, i) { return soma(j.ombro[i], mul(nor([-0.22, -s * 0.14, 1]), 29)); });
        j.mao = j.cot.map(function (c) { return soma(c, mul(d, 26)); });
        j.eixoMao = [[0, 1, 0], [0, 1, 0]]; return j;
      },
      cena: function (L, j, g) { banco(L, g, [-24, 0, 0], [66, 0, 0], 12, 47); barraAnilhas(L, g, meio(j), [0, 1, 0], 13, 12, 27); } },
    triceps_frances: { m: ["triceps"],
      pose: function (t) {
        var j = sentado(emPe(130, -5, 57)), f = j.f, R = j.R, U = j.U, F = j.F;
        j.cot = [-1, 1].map(function (s, i) { return soma(j.ombro[i], mul(nor(soma(U, mul(f, 0.1), mul(R, -s * 0.28))), 29)); });
        var ph = (8 + t * 138) * GR, dir = soma(mul(U, Math.cos(ph)), mul(F, -Math.sin(ph))), C = soma(mix(j.cot[0], j.cot[1], 0.5), mul(dir, 25));
        j.mao = [soma(C, mul(R, -2.6)), soma(C, mul(R, 2.6))]; j.eixoMao = [R, R]; j.peso = C; return j;
      },
      cena: function (L, j, g) {
        banco(L, g, mul(j.f, -28), mul(j.f, 22), 12, 47);
        barra(L, g, soma(j.peso, [0, 0, 2]), soma(j.peso, [0, 0, -16]), 1.6);
        anilha(L, g, soma(j.peso, [0, 0, 3]), Z, 8.5); anilha(L, g, soma(j.peso, [0, 0, -17]), Z, 8.5);
      } },
    mergulho: { m: ["triceps", "peito"],
      pose: function (t) {
        var inc = 10 + 8 * t, zO = 162 - 34 * t, j = emPe(140, inc, zO - 48.5 * Math.cos(inc * GR), -48.5 * Math.sin(inc * GR));
        pernas(j, lados(function (s) { return soma(j.H, mul(j.f, -22), mul(j.R, s * 4), [0, 0, -72]); }), j.f, nor(soma(mul(j.f, -0.3), BAIXO)));
        return bracos(j, lados(function (s) { return soma(mul(j.R, s * 24), mul(j.f, 2), [0, 0, 110]); }), function (s) { return soma(mul(j.f, -1), [0, 0, 0.2], mul(j.R, s * 0.25)); }, j.f);
      },
      cena: function (L, j, g) {
        lados(function (s) {
          var a = soma(mul(j.R, s * 25), mul(j.f, -34), [0, 0, 107]), b = soma(mul(j.R, s * 25), mul(j.f, 30), [0, 0, 107]);
          barra(L, g, a, b, 2.2); haste(L, soma(a, mul(j.f, 4)), [a[0], a[1], 0], 2.6); haste(L, soma(b, mul(j.f, -4)), [b[0], b[1], 0], 2.6);
        });
      } },
    coice: { m: ["triceps"],
      pose: function (t) {
        var j = emPeNoChao(emPe(140, 62, 80, -10), 13, 4), up = nor(soma(mul(j.U, -1), mul(j.F, -0.38)));
        j.cot = lados(function (s, i) { return soma(j.ombro[i], mul(up, 29), mul(j.R, s * 2)); });
        var dir = arco(up, BAIXO, t);
        j.mao = j.cot.map(function (c) { return soma(c, mul(dir, 27)); });
        var e = nor(cross(j.R, dir)); j.eixoMao = [e, e]; return j;
      },
      cena: function (L, j, g) { halteres(L, g, j, j.eixoMao[0], 6); } },
    // costas
    puxada: { m: ["costas", "biceps"],
      pose: function (t) {
        var j = sentado(emPe(262, -12, 57));
        return bracos(j, lados(function (s, i) { return mix(soma(j.ombro[i], mul(j.R, s * 18), mul(j.U, 5), mul(j.F, 9)), soma(j.ombro[i], mul(j.R, s * 16), mul(j.U, 51), mul(j.F, 6)), t); }),
          function (s) { return soma(mul(j.R, s), [0, 0, -0.6], mul(j.F, -0.5)); }, j.R);
      },
      cena: function (L, j, g) {
        var m = meio(j), e = nor(sub(j.mao[1], j.mao[0]));
        torre(L, [j.H[0] + j.f[0] * 26, j.H[1] + j.f[1] * 26, 0], 222);
        cabo(L, m, soma([j.H[0], j.H[1], 214], mul(j.f, 14)));
        barraAnilhas(L, g, m, e, 34, 0.01, 46);
        assento(L, g, j, 4, 16);
        rolo(L, soma(mix(j.joelho[0], j.joelho[1], 0.5), mul(j.f, -10), mul(j.R, -20), [0, 0, 9]), soma(mix(j.joelho[0], j.joelho[1], 0.5), mul(j.f, -10), mul(j.R, 20), [0, 0, 9]), 4.8);
      } },
    barra_fixa: { m: ["costas", "biceps"],
      pose: function (t) {
        var zO = 180 - 34 * t, j = emPe(245, -6, zO - 48.2, 5);
        pernas(j, lados(function (s) { return soma(j.H, mul(j.f, -16), mul(j.R, s * 5), [0, 0, -74]); }), j.f, nor(soma(mul(j.f, -0.3), BAIXO)));
        return bracos(j, lados(function (s) { return soma(mul(j.R, s * 27), mul(j.f, 6), [0, 0, 200]); }), function (s) { return soma(mul(j.R, s), [0, 0, -0.7], mul(j.F, -0.3)); }, j.R);
      },
      cena: function (L, j, g) {
        var c = soma(mul(j.f, 6), [0, 0, 200]);
        barraAnilhas(L, g, c, j.R, 27, 0.01, 56);
        lados(function (s) { torre(L, soma(mul(j.R, s * 58), mul(j.f, 6)), 204); });
      } },
    remada_curvada: { m: ["costas"],
      pose: function (t) {
        var j = emPeNoChao(emPe(140, 52, 84, -12), 13, 6), oM = ombros(j);
        return bracos(j, lados(function (s) { return mix(soma(j.H, mul(j.U, 16), mul(j.F, 11), mul(j.R, s * 22)), soma(oM, [0, 0, -53], mul(j.f, 2), mul(j.R, s * 22)), t); }),
          function (s) { return soma(Z, mul(j.U, -0.6), mul(j.R, s * 0.4)); }, j.R);
      },
      cena: function (L, j, g) { barraAnilhas(L, g, meio(j), j.R, 22); } },
    remada_baixa: { m: ["costas"],
      pose: function (t) {
        var j = emPe(140, -8 + 22 * t, 44), oM = ombros(j);
        pernas(j, lados(function (s) { return soma([0, 0, 22], mul(j.f, 74), mul(j.R, s * 10)); }), Z, nor(soma(Z, mul(j.f, 0.25))));
        return bracos(j, lados(function (s) { return mix(soma(j.H, mul(j.U, 18), mul(j.F, 14), mul(j.R, s * 4)), soma(oM, mul(j.f, 50), [0, 0, -12], mul(j.R, s * 4)), t); }),
          function (s) { return soma(mul(j.f, -1), mul(j.R, s * 0.5), [0, 0, -0.2]); }, Z);
      },
      cena: function (L, j, g) {
        caixa(L, g, soma([0, 0, 30], mul(j.f, 18)), mul(j.f, 42), mul(j.R, 14), [0, 0, 4]);
        caixa(L, g, soma([0, 0, 24], mul(j.f, 82)), mul(j.R, 22), [0, 0, 16], mul(j.f, -2.5));
        caixa(L, g, soma([0, 0, 46], mul(j.f, 98)), mul(j.R, 14), [0, 0, 46], mul(j.f, -6));
        var m = meio(j); barra(L, g, j.mao[0], j.mao[1], 1.6); cabo(L, m, soma([0, 0, 26], mul(j.f, 92)));
      } },
    serrote: { m: ["costas"], lado: 1,
      pose: function (t) {
        var f = chao(140), j = corpo([0, 0, 92], soma(f, [0, 0, 0.22]), soma(mul(f, 0.22), BAIXO)); j.f = f;
        j.joelho = [soma(j.quadril[0], mul(f, -2), [0, 0, -44]), null];
        j.tornozelo = [soma(j.joelho[0], mul(f, -43), [0, 0, 2]), soma([0, 0, 5], mul(j.R, 15), mul(f, -6))];
        j.joelho[1] = ik(j.quadril[1], j.tornozelo[1], 44, 45, f);
        j.ponta = [soma(j.tornozelo[0], mul(nor(soma(mul(f, -1), [0, 0, -0.7])), 10)), soma(j.tornozelo[1], mul(nor(soma(f, [0, 0, -0.23])), 11.3))];
        var apoio = soma([j.ombro[0][0], j.ombro[0][1], 50], mul(f, 4));
        var rema = mix(soma(j.ombro[1], mul(f, -16), [0, 0, -22], mul(j.R, 2)), soma(j.ombro[1], [0, 0, -52], mul(f, 3)), t);
        return bracos(j, [apoio, rema], function (s) { return s < 0 ? soma(mul(j.R, -1), mul(f, -0.3)) : soma(Z, mul(f, -0.8)); }, f);
      },
      cena: function (L, j, g) { banco(L, g, soma(mul(j.R, -12), mul(j.f, -58)), soma(mul(j.R, -12), mul(j.f, 62)), 12, 43); halter(L, g, j.mao[1], j.f, 5.5, 7); } },
    terra: { m: ["posterior", "gluteo", "costas"],
      pose: function (t) { return pendura(emPeNoChao(levanta(t, 140, [3, 62], [92, 56], [-2, -30])), 4, 1); },
      cena: function (L, j, g) { barraAnilhas(L, g, meio(j), j.R, 21); } },
    pullover: { m: ["costas", "peito"],
      pose: function (t) {
        var ph = (-8 + t * 102) * GR, d = [-Math.sin(ph), 0, Math.cos(ph)];
        return bracos(deitado(), lados(function (s) { return soma([9, s * 4, 58], mul(d, 51)); }), function (s) { return [0.2, s, -0.3]; }, d);
      },
      cena: function (L, j, g) { banco(L, g, [-20, 0, 0], [66, 0, 0], 12, 47); var d = j.eixoMao[0]; halter(L, g, soma(meio(j), mul(d, 2)), d, 6.5, 7.5); } },
    // ombro
    desenvolvimento_halter: { m: ["ombro", "triceps"],
      pose: function (t) {
        var j = sentado(emPe(60, -4, 57));
        return bracos(j, lados(function (s, i) { return mix(soma(j.ombro[i], mul(j.U, 52), mul(j.R, -s * 6), mul(j.F, 3)), soma(j.ombro[i], mul(j.R, s * 23), mul(j.U, 6), mul(j.F, 4)), t); }),
          function (s) { return soma(mul(j.R, s), mul(j.U, -0.5)); }, j.R);
      },
      cena: function (L, j, g) { costas(L, g, j, 34); assento(L, g, j); halteres(L, g, j, j.R, 7); } },
    desenvolvimento_barra: { m: ["ombro", "triceps"],
      pose: function (t) {
        var j = emPeNoChao(emPe(100, 0, 92), 14), oM = ombros(j);
        return bracos(j, lados(function (s) { return mix(soma(oM, mul(j.U, 54), mul(j.R, s * 24), mul(j.F, -2)), soma(oM, mul(j.U, 4), mul(j.F, 13), mul(j.R, s * 24)), t); }),
          function (s) { return soma(mul(j.F, 0.9), mul(j.U, -0.8), mul(j.R, s * 0.4)); }, j.R);
      },
      cena: function (L, j, g) { barraAnilhas(L, g, meio(j), j.R, 24, 17); } },
    elevacao_lateral: { m: ["ombro"],
      pose: function (t) {
        var j = emPeNoChao(emPe(55, 0, 92)), ph = (85 - t * 77) * GR;
        return bracos(j, lados(function (s, i) { return soma(j.ombro[i], mul(soma(mul(j.U, -Math.cos(ph)), mul(j.R, s * Math.sin(ph))), 53), mul(j.F, 5)); }),
          function () { return soma(mul(j.F, -1), mul(j.U, 0.4)); }, j.F);
      },
      cena: function (L, j, g) { halteres(L, g, j, j.F); } },
    elevacao_frontal: { m: ["ombro"],
      pose: function (t) {
        var j = emPeNoChao(emPe(140, 0, 92)), ph = (85 - t * 80) * GR;
        return bracos(j, lados(function (s, i) { return soma(j.ombro[i], mul(soma(mul(j.U, -Math.cos(ph)), mul(j.F, Math.sin(ph))), 53), mul(j.R, -s * 3)); }),
          function (s) { return soma(mul(j.R, s), [0, 0, -0.3]); }, j.R);
      },
      cena: function (L, j, g) { halteres(L, g, j, j.R); } },
    crucifixo_inverso: { m: ["ombro", "costas"],
      pose: function (t) {
        var j = emPeNoChao(emPe(70, 60, 84, -10), 13, 6), ph = (82 - t * 74) * GR;
        return bracos(j, lados(function (s, i) { return soma(j.ombro[i], mul(soma(mul(BAIXO, Math.cos(ph)), mul(j.R, s * Math.sin(ph))), 52)); }),
          function (s) { return soma([0, 0, 0.6], mul(j.R, s * 0.6), mul(j.f, -0.4)); }, j.f);
      },
      cena: function (L, j, g) { halteres(L, g, j, j.f); } },
    encolhimento: { m: ["trapezio"],
      pose: function (t) {
        var j = emPeNoChao(emPe(235, 0, 92)), sobe = 5 * (1 - t);
        j.ombro = j.ombro.map(function (o) { return soma(o, mul(j.U, sobe)); });
        return pendura(j, 3, 1);
      },
      cena: function (L, j, g) { halteres(L, g, j, j.f); } },
    // biceps
    rosca_direta: { m: ["biceps"],
      pose: function (t) { return rosca(emPeNoChao(emPe(140, 0, 92)), t); },
      cena: function (L, j, g) { barraAnilhas(L, g, meio(j), j.R, 20, 13, 50); } },
    rosca_martelo: { m: ["biceps"],
      pose: function (t) { var j = rosca(emPeNoChao(emPe(140, 0, 92)), t), e = nor(cross(j.R, sub(j.mao[0], j.cot[0]))); j.eixoMao = [e, e]; return j; },
      cena: function (L, j, g) { halteres(L, g, j, j.eixoMao[0]); } },
    rosca_scott: { m: ["biceps"],
      pose: function (t) {
        var j = sentado(emPe(140, 12, 57)), au = nor(soma(mul(j.F, 0.72), mul(j.U, -0.69))), a = (78 - t * 112) * GR, dir = soma(mul(j.F, Math.cos(a)), mul(j.U, Math.sin(a)));
        j.cot = lados(function (s, i) { return soma(j.ombro[i], mul(au, 29), mul(j.R, -s * 3)); });
        j.mao = j.cot.map(function (c) { return soma(c, mul(dir, 27)); });
        j.eixoMao = [j.R, j.R]; j.apoio = au; return j;
      },
      cena: function (L, j, g) {
        var n = nor(soma(mul(j.F, 0.69), mul(j.U, 0.72))), c = soma(mix(ombros(j), mix(j.cot[0], j.cot[1], 0.5), 0.6), mul(n, -9.5));
        caixa(L, g, c, mul(j.apoio, 17), mul(j.R, 22), mul(n, 3));
        haste(L, soma(c, mul(n, -3)), [c[0], c[1], 0], 2.6, true);
        assento(L, g, j, 0, 14);
        barraAnilhas(L, g, meio(j), j.R, 14, 11, 32);
      } },
    rosca_concentrada: { m: ["biceps"], lado: 1,
      pose: function (t) {
        var j = sentado(emPe(140, 55, 57), 11);
        var c1 = soma(mix(j.quadril[1], j.joelho[1], 0.8), mul(j.R, -7), [0, 0, 7]);
        var d0 = nor(soma(sub(j.ombro[1], c1), mul(j.f, -8))), dir = arco(d0, nor(soma(BAIXO, mul(j.f, 0.12))), t);
        var m0 = soma(j.joelho[0], [0, 0, 7], mul(j.f, -3));
        j.mao = [m0, soma(c1, mul(dir, 27))];
        j.cot = [ik(j.ombro[0], m0, 29, 27, soma(mul(j.R, -1), [0, 0, -0.3])), c1];
        j.eixoMao = [j.f, j.R]; return j;
      },
      cena: function (L, j, g) { assento(L, g, j, 0, 16); halter(L, g, j.mao[1], j.R, 5.5, 6.5); } },
    // perna
    agachamento: { m: ["quadriceps", "gluteo"],
      pose: function (t) {
        var j = levanta(t, 140, [8, 42], [92, 52], [-2, -22]), oM = ombros(j), b = soma(oM, mul(j.U, 3), mul(j.F, -6));
        pernas(j, lados(function (s) { return soma(mul(j.R, s * 15), [0, 0, 5]); }), function (s) { return soma(j.f, mul(j.R, s * 0.35)); });
        return bracos(j, lados(function (s) { return soma(b, mul(j.R, s * 30)); }), function (s) { return soma(mul(j.U, -1), mul(j.F, -0.6), mul(j.R, s * 0.4)); }, j.R);
      },
      cena: function (L, j, g) { barraAnilhas(L, g, meio(j), j.R, 30); } },
    leg_press: { m: ["quadriceps", "gluteo"],
      pose: function (t) {
        var f = chao(140), j = corpo([0, 0, 46], soma(mul(f, -1), [0, 0, 0.75]), soma(mul(f, 0.75), Z)), sd = nor(soma(f, Z)), p = nor(soma(mul(f, -1), Z)), D = 84 - 44 * t;
        j.f = f;
        pernas(j, lados(function (s) { return soma(j.H, mul(sd, D), mul(j.R, s * 14)); }), function (s) { return soma(p, mul(j.R, s * 0.25)); }, p);
        j.plat = soma(j.H, mul(sd, D + 6)); j.sd = sd; j.p = p;
        return bracos(j, lados(function (s, i) { return soma(j.quadril[i], mul(j.R, s * 12), mul(f, 6), [0, 0, -3]); }), function (s) { return soma(mul(j.R, s), [0, 0, 0.3]); }, f);
      },
      cena: function (L, j, g) {
        caixa(L, g, soma(j.H, mul(j.U, 28), mul(j.F, -13)), mul(j.U, 34), mul(j.R, 15), mul(j.F, 3.5));
        caixa(L, g, soma([0, 0, 31], mul(j.f, -2)), mul(j.f, 14), mul(j.R, 15), [0, 0, 3]);
        caixa(L, g, soma([0, 0, 8], mul(j.f, 34)), mul(j.f, 52), mul(j.R, 18), [0, 0, 8]);
        lados(function (s) { haste(L, soma(j.H, mul(j.sd, 24), mul(j.R, s * 30), [0, 0, -14]), soma(j.H, mul(j.sd, 128), mul(j.R, s * 30), [0, 0, -14]), 2.4, true); });
        caixa(L, g, j.plat, mul(j.R, 26), mul(j.p, 22), mul(j.sd, -2.5));
      } },
    extensora: { m: ["quadriceps"],
      pose: function (t) {
        var j = emPe(140, -8, 57), b = (-4 - 91 * t) * GR, dir = soma(mul(j.f, Math.cos(b)), [0, 0, Math.sin(b)]), pe = soma(mul(j.f, Math.cos(b + 1.45)), [0, 0, Math.sin(b + 1.45)]);
        j.joelho = lados(function (s) { return soma(j.H, mul(j.f, 42), mul(j.R, s * 10), [0, 0, -1]); });
        j.tornozelo = j.joelho.map(function (k) { return soma(k, mul(dir, 44)); });
        j.ponta = j.tornozelo.map(function (a) { return soma(a, mul(pe, 11)); });
        j.pad = soma(mix(j.tornozelo[0], j.tornozelo[1], 0.5), mul(pe, 6), mul(dir, -4));
        return bracos(j, lados(function (s, i) { return soma(j.quadril[i], mul(j.R, s * 14), [0, 0, -6], mul(j.f, 4)); }), function (s) { return soma(mul(j.R, s), [0, 0, 0.3]); }, j.f);
      },
      cena: function (L, j, g) {
        costas(L, g, j); assento(L, g, j, 16, 24);
        rolo(L, soma(j.pad, mul(j.R, -20)), soma(j.pad, mul(j.R, 20)), 5);
        var piv = soma(mix(j.joelho[0], j.joelho[1], 0.5), mul(j.R, 22));
        haste(L, piv, soma(j.pad, mul(j.R, 21)), 1.8);
      } },
    flexora: { m: ["posterior"],
      pose: function (t) {
        var f = chao(140), j = corpo([0, 0, 57], mul(f, -1), BAIXO), y = (112 - 107 * t) * GR, dir = soma(mul(f, Math.cos(y)), [0, 0, Math.sin(y)]), pp = soma(mul(f, -Math.sin(y)), [0, 0, Math.cos(y)]);
        j.f = f;
        j.joelho = j.quadril.map(function (q) { return soma(q, mul(f, 44), [0, 0, -1]); });
        j.tornozelo = j.joelho.map(function (k) { return soma(k, mul(dir, 45)); });
        j.ponta = j.tornozelo.map(function (a) { return soma(a, mul(pp, -9), mul(dir, 3)); });
        j.pad = soma(mix(j.tornozelo[0], j.tornozelo[1], 0.5), mul(pp, 6));
        return bracos(j, lados(function (s, i) { return soma(j.ombro[i], mul(j.U, 14), [0, 0, -16]); }), function (s) { return soma(mul(j.R, s), [0, 0, 0.3]); }, j.R);
      },
      cena: function (L, j, g) {
        banco(L, g, mul(j.f, -56), mul(j.f, 40), 12, 47);
        rolo(L, soma(j.pad, mul(j.R, -20)), soma(j.pad, mul(j.R, 20)), 5);
        var piv = soma(mix(j.joelho[0], j.joelho[1], 0.5), mul(j.R, 22));
        haste(L, piv, soma(j.pad, mul(j.R, 21)), 1.8);
      } },
    stiff: { m: ["posterior", "gluteo"],
      pose: function (t) { return pendura(emPeNoChao(levanta(t, 140, [3, 65], [92, 84], [-2, -30])), 4, 1); },
      cena: function (L, j, g) { barraAnilhas(L, g, meio(j), j.R, 21); } },
    avanco: { m: ["quadriceps", "gluteo"],
      pose: function (t) {
        var j = emPe(140, 2, 86 - 30 * t, -3);
        pernas(j, [soma(mul(j.f, -36), mul(j.R, -10), [0, 0, 9]), soma(mul(j.f, 28), mul(j.R, 10), [0, 0, 5])], j.f, [nor(soma(j.f, [0, 0, -0.95])), nor(soma(j.f, [0, 0, -0.23]))]);
        return pendura(j, 2, 1);
      },
      cena: function (L, j, g) { halteres(L, g, j, j.f); } },
    bulgaro: { m: ["quadriceps", "gluteo"],
      pose: function (t) {
        var j = emPe(140, 4, 86 - 30 * t, -3);
        pernas(j, [soma(mul(j.f, -48), mul(j.R, -9), [0, 0, 50]), soma(mul(j.f, 26), mul(j.R, 10), [0, 0, 5])], function (s) { return s < 0 ? soma(j.f, BAIXO) : j.f; },
          [nor(soma(mul(j.f, -1), [0, 0, -0.35])), nor(soma(j.f, [0, 0, -0.23]))]);
        return pendura(j, 2, 1);
      },
      cena: function (L, j, g) { banco(L, g, soma(mul(j.f, -56), mul(j.R, -34)), soma(mul(j.f, -56), mul(j.R, 22)), 11, 45); halteres(L, g, j, j.f); } },
    panturrilha: { m: ["panturrilha"],
      pose: function (t) {
        var dz = 9 - 15 * t, k = Math.sqrt(Math.max(0, 127.7 - dz * dz)), az = 11 + dz, j = emPe(140, 0, az + 87.5, -k);
        pernas(j, lados(function (s) { return soma(mul(j.f, -k), mul(j.R, s * 11), [0, 0, az]); }), j.f);
        j.ponta = lados(function (s) { return soma(mul(j.R, s * 11), [0, 0, 11]); });
        return pendura(j, 3, 1);
      },
      cena: function (L, j, g) { caixa(L, g, soma(mul(j.f, 8), [0, 0, 5.5]), mul(j.f, 11), mul(j.R, 30), [0, 0, 5.5]); halteres(L, g, j, j.f); } },
    elevacao_pelvica: { m: ["gluteo", "posterior"],
      pose: function (t) {
        var th = 38 * t, f = chao(140), c = Math.cos(th * GR), s = Math.sin(th * GR), U = soma(mul(f, -c), [0, 0, s]);
        var j = supino(140, th, sub([0, 0, 54], mul(U, 48.5))), b = soma(j.H, mul(j.F, 12), mul(j.U, 3));
        pernas(j, lados(function (sd) { return soma(mul(f, 82), mul(j.R, sd * 14), [0, 0, 5]); }), Z);
        j.barra = b;
        return bracos(j, lados(function (sd) { return soma(b, mul(j.R, sd * 22)); }), function (sd) { return soma(j.U, [0, 0, -0.4], mul(j.R, sd * 0.4)); }, j.R);
      },
      cena: function (L, j, g) { banco(L, g, soma(mul(j.f, -12), mul(j.R, -38)), soma(mul(j.f, -12), mul(j.R, 38)), 10, 47); barraAnilhas(L, g, j.barra, j.R, 22); } },
    abdutora: { m: ["abdutor"],
      pose: function (t) {
        var j = emPe(50, -14, 57), ph = (38 - 32 * t) * GR;
        j.joelho = lados(function (s, i) { return soma(j.quadril[i], mul(soma(mul(j.f, Math.cos(ph)), mul(j.R, s * Math.sin(ph))), 43), [0, 0, -3]); });
        j.tornozelo = j.joelho.map(function (k) { return soma(k, mul(j.f, 4), [0, 0, -36]); });
        j.ponta = j.tornozelo.map(function (a) { return soma(a, mul(j.f, 11), [0, 0, -2]); });
        j.fora = lados(function (s) { return soma(mul(j.f, -Math.sin(ph)), mul(j.R, s * Math.cos(ph))); });
        return bracos(j, lados(function (s, i) { return soma(j.quadril[i], mul(j.R, s * 15), mul(j.f, 6), [0, 0, -4]); }), function (s) { return mul(j.R, s); }, j.f);
      },
      cena: function (L, j, g) {
        costas(L, g, j); assento(L, g, j, 12, 22);
        j.joelho.forEach(function (k, i) { var c = soma(k, mul(j.fora[i], 9.5)); rolo(L, soma(c, [0, 0, -9]), soma(c, [0, 0, 7]), 4.6); });
      } },
    // abdomen
    abdominal: { m: ["abdomen"],
      pose: function (t) {
        var j = supino(140, 34 - 30 * t, [0, 0, 11]);
        pernas(j, lados(function (s) { return soma(mul(j.f, 62), mul(j.R, s * 12), [0, 0, 5]); }), Z);
        return bracos(j, lados(function (s) { return soma(j.cabeca, mul(j.R, s * 8), mul(j.F, -4), mul(j.U, -3)); }), function (s) { return soma(mul(j.R, s), mul(j.U, 0.3)); }, j.U);
      },
      cena: function (L, j, g) { colchonete(L, g, { H: [0, 0, 0], f: j.f, R: j.R }, -80, 80); } },
    prancha: { m: ["abdomen"], atraves: true,
      pose: function (t) {
        var j = prono(10 + 1.6 * (1 - t), 140, [0, 0, 9]);
        j.cot = j.ombro.map(function (o) { return [o[0], o[1], 5]; });
        j.mao = lados(function (s, i) { return soma(j.cot[i], mul(j.f, 24), mul(j.R, -s * 6), [0, 0, -1]); });
        j.eixoMao = [j.f, j.f]; return j;
      },
      cena: function (L, j, g) { colchonete(L, g, { H: [0, 0, 0], f: j.f, R: j.R }, -10, 150); } },
    elevacao_pernas: { m: ["abdomen"],
      pose: function (t) {
        var j = supino(140, 0, [0, 0, 11]), f = j.f, ph = (82 - 70 * t) * GR, dir = soma(mul(f, Math.cos(ph)), [0, 0, Math.sin(ph)]), pp = soma(mul(f, -Math.sin(ph)), [0, 0, Math.cos(ph)]);
        j.joelho = lados(function (s, i) { return soma(j.quadril[i], mul(dir, 44), mul(j.R, -s)); });
        j.tornozelo = lados(function (s, i) { return soma(j.quadril[i], mul(dir, 88), mul(j.R, -s * 2)); });
        j.ponta = j.tornozelo.map(function (a) { return soma(a, mul(dir, 8), mul(pp, 4)); });
        return bracos(j, lados(function (s, i) { return soma(j.quadril[i], mul(j.R, s * 9), mul(f, 4), [0, 0, -6]); }), Z, f);
      },
      cena: function (L, j, g) { colchonete(L, g, { H: [0, 0, 0], f: j.f, R: j.R }, -80, 60); } }
  };
  // rosca em pe: braco colado no corpo, antebraco sobe na frente
  function rosca(j, t) {
    var psi = (140 - t * 132) * GR, dir = soma(mul(j.U, -Math.cos(psi)), mul(j.F, Math.sin(psi)));
    j.cot = lados(function (s, i) { return soma(j.ombro[i], mul(j.U, -29), mul(j.F, 3), mul(j.R, s)); });
    j.mao = j.cot.map(function (c, i) { return soma(c, mul(dir, 27), mul(j.R, i ? 2 : -2)); });
    j.eixoMao = [j.R, j.R]; return j;
  }

  // nome do exercicio (texto livre da ficha) -> tipo; o mais especifico primeiro. Sem acento e minusculo.
  var MAPA = [
    [/remada alta|adut/, null],
    [/testa/, "triceps_testa"], [/frances/, "triceps_frances"], [/coice|kickback/, "coice"],
    [/mergulho|paralela|\bdips?\b/, "mergulho"], [/triceps/, "triceps_corda"],
    [/flexora|leg curl|mesa/, "flexora"], [/extensora|leg extension/, "extensora"],
    [/inverso|invertido|reverse|deltoide posterior|posterior de ombro/, "crucifixo_inverso"],
    [/supino.*inclinad|inclinad.*supino/, "supino_inclinado"], [/declinad/, "supino_declinado"],
    [/supino.*halter|halter.*supino/, "supino_halter"], [/supino|bench/, "supino_barra"],
    [/peck|voador|fly machine/, "peck_deck"], [/crucifixo|\bfly\b/, "crucifixo"], [/cross/, "crossover"],
    [/flexao|push.?up/, "flexao"],
    [/puxada|pulldown|pulley (frente|costas)/, "puxada"], [/barra fixa|pull.?up|chin.?up/, "barra_fixa"],
    [/serrote|unilateral/, "serrote"], [/remada.*(baixa|sentad|cabo|triangulo)/, "remada_baixa"], [/remada|row/, "remada_curvada"],
    [/stiff|romeno|rdl/, "stiff"], [/terra|deadlift/, "terra"], [/pullover/, "pullover"],
    [/desenvolvimento|militar|shoulder press|arnold/, "desenvolvimento"],
    [/elevacao (de )?pernas|leg raise/, "elevacao_pernas"], [/pelvica|hip thrust|ponte/, "elevacao_pelvica"],
    [/lateral/, "elevacao_lateral"], [/frontal/, "elevacao_frontal"], [/encolhimento|shrug/, "encolhimento"],
    [/scott/, "rosca_scott"], [/concentrad/, "rosca_concentrada"], [/martelo|hammer/, "rosca_martelo"], [/rosca|biceps|curl/, "rosca_direta"],
    [/leg ?press|leg 45|prensa/, "leg_press"], [/bulgaro/, "bulgaro"], [/avanco|afundo|passada|lunge/, "avanco"],
    [/panturrilha|gemeos|calf|soleo/, "panturrilha"], [/abdu/, "abdutora"],
    [/prancha|plank/, "prancha"], [/abdominal|crunch|abdomen/, "abdominal"],
    [/agachament|squat|hack|smith/, "agachamento"]
  ];
  function tipo(nome) {
    var n = String(nome || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
    for (var i = 0; i < MAPA.length; i++) {
      if (!MAPA[i][0].test(n)) continue;
      var tp = MAPA[i][1];
      if (tp === "desenvolvimento") tp = /barra|militar/.test(n) ? "desenvolvimento_barra" : "desenvolvimento_halter";
      return tp;
    }
    return null;
  }

  function quadro(ex, t, brilho, g) {
    var itens = [], L = { fundo: [], chao: [], add: function (d, h) { itens.push([d, h]); } };
    var j = ex.pose(t), br = { lado: ex.lado, atraves: ex.atraves };
    ex.m.forEach(function (k) { br[k] = brilho; });
    ex.cena(L, j, g);
    figura(L, j, g, br);
    var sombra = casco(L.chao.map(function (p) { var q = proj([p[0], p[1], 0]); return [q[0], q[1]]; }));
    itens.sort(function (a, b) { return a[0] - b[0]; });
    return '<path fill="#000" opacity=".5" filter="url(#fSombra' + g + ')" d="' + suave2(sombra) + '"/>' + L.fundo.join("") + itens.map(function (x) { return x[1]; }).join("");
  }
  function defs(g) {
    return '<defs>' +
      '<linearGradient id="gPele' + g + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#eef4f8"/><stop offset="1" stop-color="#9fb1bf"/></linearGradient>' +
      '<linearGradient id="gLonge' + g + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#a3b1bc"/><stop offset="1" stop-color="#5a6873"/></linearGradient>' +
      '<linearGradient id="gCorpo' + g + '" gradientUnits="userSpaceOnUse" x1="0" y1="20" x2="0" y2="190"><stop offset="0" stop-color="#f1f6f9"/><stop offset="1" stop-color="#8d9fad"/></linearGradient>' +
      '<linearGradient id="gEst' + g + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a424c"/><stop offset="1" stop-color="#1c2128"/></linearGradient>' +
      '<linearGradient id="gMetal' + g + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f2f5f7"/><stop offset=".5" stop-color="#8d969d"/><stop offset="1" stop-color="#4b5258"/></linearGradient>' +
      '<radialGradient id="gPeito' + g + '"><stop offset="0" stop-color="#c9d1ff" stop-opacity=".95"/><stop offset="1" stop-color="#9aa8f0" stop-opacity="0"/></radialGradient>' +
      '<radialGradient id="gTri' + g + '"><stop offset="0" stop-color="#c9d1ff" stop-opacity=".95"/><stop offset="1" stop-color="#9aa8f0" stop-opacity=".1"/></radialGradient>' +
      '<radialGradient id="gChao' + g + '"><stop offset="0" stop-color="#9aa8f0" stop-opacity=".10"/><stop offset="1" stop-color="#9aa8f0" stop-opacity="0"/></radialGradient>' +
      '<filter id="fSombra' + g + '" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="5"/></filter></defs>';
  }
  // enquadra: mede o exercicio inteiro (sem as colunas da polia) e centraliza no viewBox 240x200
  function enquadra(ex, g) {
    cam = { esc: 1, ox: 0, oy: 0 }; moldura = [1e9, 1e9, -1e9, -1e9];
    [0, 0.5, 1].forEach(function (t) { quadro(ex, t, 0, g); });
    var b = moldura; moldura = null;
    var esc = Math.min(216 / (b[2] - b[0]), 172 / (b[3] - b[1]));
    return { esc: esc, ox: 120 - (b[0] + b[2]) / 2 * esc, oy: 104 - (b[1] + b[3]) / 2 * esc };
  }
  var CHAO = function (g) { return '<ellipse cx="120" cy="178" rx="120" ry="26" fill="url(#gChao' + g + ')"/>'; };
  // SVG parado (sem DOM): historico, prefers-reduced-motion e testes
  function desenhar(tp, t, brilho) {
    var ex = EX[tp]; if (!ex) return "";
    var g = "e" + (++inst), meu = enquadra(ex, g); cam = meu;
    return defs(g) + CHAO(g) + "<g>" + quadro(ex, t == null ? 0.45 : t, brilho == null ? 0.4 : brilho, g) + "</g>";
  }
  // ciclo de 4 s: desce 2 s, pausa .35, sobe 1 s, segura em cima
  var PER = 4000, ease = function (x) { return x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2; };
  function pose(ms) {
    var s = (ms % PER) / 1000;
    if (s < 2) return [ease(s / 2), 0.12];
    if (s < 2.35) return [1, 0.12];
    if (s < 3.35) { var k = s - 2.35; return [Math.pow(1 - k, 3), 0.15 + 0.75 * Math.sin(k * Math.PI)]; }
    return [0, Math.max(0.12, 0.5 - (s - 3.35) * 1.2)];
  }
  // anima no <svg>; fixo = t parado (sem laco). Devolve a funcao que para. Dispara "rep" a cada repeticao.
  function montar(svg, tp, fixo) {
    var ex = EX[tp];
    svg.setAttribute("viewBox", "0 0 240 200");
    if (!ex) { svg.innerHTML = ""; return function () {}; }
    if (fixo != null || reduz) { svg.innerHTML = desenhar(tp, fixo == null ? 0.45 : fixo, fixo == null ? 0.4 : 0.6); return function () {}; }
    var g = "e" + (++inst), meu = enquadra(ex, g);
    svg.innerHTML = defs(g) + CHAO(g) + "<g></g>";
    var palco = svg.lastChild, vivo = true, t0 = performance.now(), ultimo = 0;
    (function laco(agora) {
      if (!vivo || (!svg.isConnected && agora - t0 > 1500)) return;
      var p = pose(agora - t0); cam = meu; palco.innerHTML = quadro(ex, p[0], p[1], g);
      var n = Math.floor((agora - t0 + 650) / PER); if (n !== ultimo) { ultimo = n; svg.dispatchEvent(new CustomEvent("rep", { detail: n })); }
      requestAnimationFrame(laco);
    })(t0);
    return function () { vivo = false; };
  }
  return { montar: montar, desenhar: desenhar, tipo: tipo, lista: Object.keys(EX) };
})();
if (typeof module !== "undefined" && module.exports) module.exports = Exercicio;
