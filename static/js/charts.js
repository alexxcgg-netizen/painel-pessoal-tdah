const SVG_NS = "http://www.w3.org/2000/svg";

function criarSvg(atributos) {
  const el = document.createElementNS(SVG_NS, "svg");
  for (const [k, v] of Object.entries(atributos)) el.setAttribute(k, v);
  return el;
}

function el(tag, atributos) {
  const e = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(atributos)) e.setAttribute(k, v);
  return e;
}

function fmtDataCurta(iso) {
  const [, m, d] = iso.split("-");
  return `${d}/${m}`;
}

function mostrarTooltip(container, texto, x, y) {
  let tip = container.querySelector(".grafico-tooltip");
  if (!tip) {
    tip = document.createElement("div");
    tip.className = "grafico-tooltip";
    container.appendChild(tip);
  }
  tip.textContent = texto;
  tip.style.left = `${x}px`;
  tip.style.top = `${y}px`;
  tip.hidden = false;
}

function esconderTooltip(container) {
  const tip = container.querySelector(".grafico-tooltip");
  if (tip) tip.hidden = true;
}

/**
 * Grafico de barras finas - uso: evolucao de gasto diario. Uma serie so
 * (a cor da propria secao), sem legenda (regra: 1 serie nao precisa).
 * dados: [{data: "AAAA-MM-DD", total: numero}]
 */
function desenharGraficoBarras(container, dados, opcoes) {
  container.innerHTML = "";
  esconderTooltip(container);
  if (!dados.length || dados.every((d) => d.total === 0)) {
    container.innerHTML = '<p class="grafico-vazio">Sem gasto registrado nesse periodo.</p>';
    return;
  }

  const largura = container.clientWidth || 320;
  const altura = opcoes.altura || 90;
  const padInferior = 16;
  const maxValor = Math.max(...dados.map((d) => d.total), 1);
  const n = dados.length;
  const gap = 2;
  const larguraBarra = Math.min(24, (largura - gap * (n - 1)) / n);
  const offsetX = (largura - (larguraBarra * n + gap * (n - 1))) / 2;

  const svg = criarSvg({
    viewBox: `0 0 ${largura} ${altura}`,
    width: "100%",
    height: altura,
    role: "img",
    "aria-label": opcoes.rotulo || "Grafico de gasto diario",
  });

  svg.appendChild(
    el("line", {
      x1: 0,
      y1: altura - padInferior,
      x2: largura,
      y2: altura - padInferior,
      stroke: "var(--border)",
      "stroke-width": 1,
    })
  );

  const indiceMax = dados.reduce((m, d, i) => (d.total > dados[m].total ? i : m), 0);

  dados.forEach((d, i) => {
    const x = offsetX + i * (larguraBarra + gap);
    const alturaBarra = Math.max((d.total / maxValor) * (altura - padInferior - 10), d.total > 0 ? 3 : 0);
    const y = altura - padInferior - alturaBarra;
    const rect = el("rect", {
      x,
      y,
      width: larguraBarra,
      height: Math.max(alturaBarra, 1),
      rx: 4,
      fill: d.total > 0 ? "var(--barra-cor, var(--accent))" : "var(--border)",
      class: "grafico-barra",
    });
    rect.style.cursor = "pointer";
    const alvo = d.total > 0 ? rect : el("rect", { x, y: altura - padInferior - 6, width: larguraBarra, height: 6, fill: "transparent" });
    if (d.total === 0) svg.appendChild(alvo);
    svg.appendChild(rect);

    const mostrar = () => {
      const rectContainer = container.getBoundingClientRect();
      mostrarTooltip(
        container,
        `${fmtDataCurta(d.data)}: ${opcoes.formatarValor(d.total)}`,
        x + larguraBarra / 2,
        y - 6
      );
    };
    rect.addEventListener("pointerenter", mostrar);
    rect.addEventListener("pointerdown", mostrar);
    if (d.total === 0) {
      alvo.addEventListener("pointerenter", mostrar);
      alvo.addEventListener("pointerdown", mostrar);
    }

    if (i === indiceMax && d.total > 0) {
      svg.appendChild(
        el("text", {
          x: x + larguraBarra / 2,
          y: y - 4,
          "text-anchor": "middle",
          class: "grafico-rotulo-topo",
        })
      ).textContent = opcoes.formatarValor(d.total);
    }
  });

  svg.addEventListener("pointerleave", () => esconderTooltip(container));
  container.style.setProperty("--barra-cor", opcoes.cor || "var(--accent)");
  container.appendChild(svg);
}

/**
 * Grafico de linha com area - uso: evolucao de meta guardada (com linha de
 * alvo tracejada) e horas de voo acumuladas. Uma serie so, ponto final
 * rotulado (regra: rotula so o extremo/ultimo ponto).
 * pontos: [{data: "AAAA-MM-DD", acumulado: numero}]
 */
function desenharGraficoLinha(container, pontos, opcoes) {
  container.innerHTML = "";
  esconderTooltip(container);
  if (pontos.length < 2) {
    container.innerHTML = '<p class="grafico-vazio">Ainda sem historico suficiente.</p>';
    return;
  }

  const largura = container.clientWidth || 320;
  const altura = opcoes.altura || 90;
  const padX = 6;
  const padTopo = 14;
  const padBase = 16;
  const valorAlvo = opcoes.valorAlvo || 0;
  const maxValor = Math.max(...pontos.map((p) => p.acumulado), valorAlvo, 1);

  const n = pontos.length;
  const x = (i) => padX + (i / (n - 1)) * (largura - padX * 2);
  const y = (v) => altura - padBase - (v / maxValor) * (altura - padTopo - padBase);

  const svg = criarSvg({
    viewBox: `0 0 ${largura} ${altura}`,
    width: "100%",
    height: altura,
    role: "img",
    "aria-label": opcoes.rotulo || "Grafico de evolucao",
  });

  if (valorAlvo > 0) {
    const yAlvo = y(valorAlvo);
    const linhaAlvo = el("line", {
      x1: padX,
      y1: yAlvo,
      x2: largura - padX,
      y2: yAlvo,
      stroke: "var(--text-faint)",
      "stroke-width": 1,
      "stroke-dasharray": "3,3",
    });
    svg.appendChild(linhaAlvo);
  }

  let d = `M ${x(0)} ${y(pontos[0].acumulado)}`;
  for (let i = 1; i < n; i++) d += ` L ${x(i)} ${y(pontos[i].acumulado)}`;
  const areaD = `${d} L ${x(n - 1)} ${altura - padBase} L ${x(0)} ${altura - padBase} Z`;

  svg.appendChild(el("path", { d: areaD, fill: opcoes.cor || "var(--accent)", "fill-opacity": 0.1 }));
  svg.appendChild(
    el("path", {
      d,
      fill: "none",
      stroke: opcoes.cor || "var(--accent)",
      "stroke-width": 2,
      "stroke-linejoin": "round",
      "stroke-linecap": "round",
    })
  );

  pontos.forEach((p, i) => {
    const cx = x(i);
    const cy = y(p.acumulado);
    const hit = el("circle", { cx, cy, r: 12, fill: "transparent", style: "cursor:pointer" });
    hit.addEventListener("pointerenter", () =>
      mostrarTooltip(container, `${fmtDataCurta(p.data)}: ${opcoes.formatarValor(p.acumulado)}`, cx, cy - 10)
    );
    hit.addEventListener("pointerdown", () =>
      mostrarTooltip(container, `${fmtDataCurta(p.data)}: ${opcoes.formatarValor(p.acumulado)}`, cx, cy - 10)
    );
    svg.appendChild(hit);
  });

  const ultimo = pontos[n - 1];
  const cxUltimo = x(n - 1);
  const cyUltimo = y(ultimo.acumulado);
  svg.appendChild(el("circle", { cx: cxUltimo, cy: cyUltimo, r: 5, fill: "var(--surface)" }));
  svg.appendChild(
    el("circle", { cx: cxUltimo, cy: cyUltimo, r: 4, fill: opcoes.cor || "var(--accent)" })
  );
  const rotuloFinal = el("text", {
    x: Math.min(cxUltimo, largura - 4),
    y: Math.max(cyUltimo - 8, 10),
    "text-anchor": "end",
    class: "grafico-rotulo-topo",
  });
  rotuloFinal.textContent = opcoes.formatarValor(ultimo.acumulado);
  svg.appendChild(rotuloFinal);

  svg.addEventListener("pointerleave", () => esconderTooltip(container));
  container.appendChild(svg);
}
