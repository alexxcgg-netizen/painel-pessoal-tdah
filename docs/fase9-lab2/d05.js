(window.DIRECOES = window.DIRECOES || {})[5] = {
  nome: "Bento",
  ideia: "Grade bento assimétrica de blocos arredondados, como página de produto: um bloco grande de gasto, médios de fatura/conta/foco, pequenos de clima/hora/voz.",
  acento: "#FFD60A",
  fontes: ["Inter:wght@400;500;600;700"],
  render(root, D, ctx) {
    const AC = "#FFD60A";
    const fmt = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
    const fin = D.financas || {};
    const timers = [];
    const cleanups = [];

    const ICONS = {
      mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/><path d="M8 21h8"/></svg>',
      financas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="9"/><path d="M12 7v10M9 9.5c0-1.4 1.3-2 3-2s3 .8 3 2-1.3 1.8-3 2-3 .8-3 2 1.3 2 3 2 3-.6 3-2"/></svg>',
      vida: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>',
      tasks: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 6h16M4 12h16M4 18h10"/><circle cx="20" cy="18" r="2"/></svg>',
      aviacao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 2v20M4 9l16 4M6 20l6-3 6 3"/></svg>',
      chuva: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M7 15a4 4 0 0 1 .8-7.94A5 5 0 0 1 17.6 9.1 3.5 3.5 0 0 1 17 16H7z"/><path d="M8 19l-1 2M12 19l-1 2M16 19l-1 2"/></svg>',
      alerta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 3l10 18H2L12 3z"/><path d="M12 10v4M12 17h.01"/></svg>',
      chevron: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M9 6l6 6-6 6"/></svg>',
      enviar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 12l16-8-6 16-3-7-7-1z"/></svg>'
    };
    const ICOSET = [ICONS.vida, ICONS.tasks, ICONS.financas, ICONS.aviacao, ICONS.chuva, ICONS.mic];

    function areaChart(dias, w, h, pad, refVal) {
      pad = pad || 4;
      const vals = dias.map(d => d.acumulado);
      const max = Math.max.apply(null, vals.concat([1, refVal || 0]));
      const n = vals.length;
      const pts = vals.map((v, i) => [(i / (n - 1)) * (w - 2 * pad) + pad, h - pad - (v / max) * (h - 2 * pad)]);
      const line = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
      const area = line + ` L${pts[n - 1][0].toFixed(1)},${h - pad} L${pts[0][0].toFixed(1)},${h - pad} Z`;
      let refY = null;
      if (refVal) refY = h - pad - (refVal / max) * (h - 2 * pad);
      return { line, area, refY, x0: pts[0][0], x1: pts[n - 1][0], max };
    }

    function lerp(a, b, t) {
      const pa = parseInt(a.slice(1), 16), pb = parseInt(b.slice(1), 16);
      const ar = (pa >> 16) & 255, ag = (pa >> 8) & 255, ab = pa & 255;
      const br = (pb >> 16) & 255, bg = (pb >> 8) & 255, bb = pb & 255;
      const rr = Math.round(ar + (br - ar) * t), rg = Math.round(ag + (bg - ag) * t), rb = Math.round(ab + (bb - ab) * t);
      return { css: `rgb(${rr},${rg},${rb})`, lum: (0.299 * rr + 0.587 * rg + 0.114 * rb) / 255 };
    }

    // squarified treemap
    function treemap(items, x0, y0, w0, h0) {
      const total = items.reduce((s, d) => s + d.value, 0) || 1;
      const data = items.map(d => ({ ...d, area: (d.value / total) * w0 * h0 }));
      const rects = [];
      function worst(row, len) {
        const sum = row.reduce((s, i) => s + i.area, 0) || 0.001;
        const max = Math.max.apply(null, row.map(i => i.area));
        const min = Math.min.apply(null, row.map(i => i.area));
        return Math.max((len * len * max) / (sum * sum), (sum * sum) / (len * len * min));
      }
      function layoutRow(row, x, y, w, h, vertical) {
        const sum = row.reduce((s, i) => s + i.area, 0);
        if (vertical) {
          const rh = Math.min(h, sum / w || h);
          let cx = x;
          row.forEach(i => { const rw = i.area / (rh || 1); rects.push({ ...i, x: cx, y, w: rw, h: rh }); cx += rw; });
          return { x, y: y + rh, w, h: h - rh };
        } else {
          const rw = Math.min(w, sum / h || w);
          let cy = y;
          row.forEach(i => { const rh = i.area / (rw || 1); rects.push({ ...i, x, y: cy, w: rw, h: rh }); cy += rh; });
          return { x: x + rw, y, w: w - rw, h };
        }
      }
      let remaining = data.slice();
      let cx = x0, cy = y0, cw = w0, ch = h0;
      let guard = 0;
      while (remaining.length && guard++ < 40) {
        const vertical = cw >= ch;
        const side = Math.max(1, Math.min(cw, ch));
        let row = [remaining[0]], i = 1;
        while (i < remaining.length) {
          const testRow = row.concat([remaining[i]]);
          if (worst(testRow, side) <= worst(row, side)) { row = testRow; i++; } else break;
        }
        const res = layoutRow(row, cx, cy, cw, ch, vertical);
        remaining = remaining.slice(row.length);
        cx = res.x; cy = res.y; cw = Math.max(0, res.w); ch = Math.max(0, res.h);
        if (cw <= 0 || ch <= 0) break;
      }
      return rects;
    }

    root.innerHTML = `
    <style>
      :host, * { box-sizing: border-box; }
      .wrap { font-family: 'Inter', sans-serif; color: #f2f2f2; background: #000; padding: 14px 14px 90px; min-height: 760px; position: relative; }
      .tab-title { font-size: 20px; font-weight: 700; letter-spacing: -.01em; margin: 2px 2px 12px; }
      .aviso { display: flex; gap: 8px; align-items: center; background: #1a1210; border: 1px solid #3a2318; color: #ff9d7a; font-size: 12px; padding: 10px 12px; border-radius: 16px; margin-bottom: 10px; }
      .aviso svg { width: 15px; height: 15px; flex-shrink: 0; }
      .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
      .tile { background: #141414; border-radius: 22px; padding: 14px; position: relative; overflow: hidden; min-height: 44px; }
      .tile.tap { cursor: pointer; }
      .lbl { font-size: 11px; color: #8a8a8a; font-weight: 500; letter-spacing: .01em; }
      .num { font-size: 15px; font-weight: 600; font-variant-numeric: tabular-nums; margin-top: 2px; color: #fff; }
      .g-topbar { grid-column: 1/5; display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; padding: 2px 2px 8px; }
      .g-topbar .relogio { font-size: 26px; font-weight: 700; font-variant-numeric: tabular-nums; letter-spacing: -.02em; }
      .g-topbar .data { font-size: 11.5px; color: #8a8a8a; margin-top: 1px; }
      .mic-btn { width: 46px; height: 46px; border-radius: 50%; border: none; background: ${AC}; color: #000; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
      .mic-btn svg { width: 20px; height: 20px; }
      .g-gasto { grid-column: 1/5; }
      .g-gasto .lbl { color: #9a9a9a; }
      .g-gasto .big { font-size: 34px; font-weight: 700; letter-spacing: -.02em; font-variant-numeric: tabular-nums; margin-top: 4px; }
      .g-gasto .cmp { font-size: 12.5px; color: #9a9a9a; margin-top: 4px; }
      .g-gasto .cmp b { color: ${AC}; font-weight: 600; }
      .g-gasto svg { width: 100%; height: 92px; margin-top: 8px; display: block; }
      .g-fatura { grid-column: 1/3; }
      .g-conta { grid-column: 3/5; }
      .g-foco { grid-column: 1/5; }
      .g-foco .txt { font-size: 14.5px; font-weight: 600; margin-top: 4px; line-height: 1.3; }
      .g-foco .sub { font-size: 11.5px; color: #7a7a7a; margin-top: 6px; }
      .g-clima { grid-column: 1/2; align-items: center; text-align: center; }
      .g-clima svg { width: 18px; height: 18px; color: ${AC}; margin: 0 auto 4px; }
      .g-clima .num { font-size: 16px; }
      .g-hora { grid-column: 2/3; align-items: center; text-align: center; justify-content: center; }
      .g-hora .num { font-size: 13px; }
      .g-voz { grid-column: 3/5; display: flex; align-items: center; justify-content: center; gap: 10px; flex-direction: row; }
      .g-voz span { font-size: 12px; color: #c8c8c8; font-weight: 500; }
      .g-atalho { grid-column: span 2; display: flex; align-items: center; gap: 10px; flex-direction: row; }
      .g-atalho svg { width: 18px; height: 18px; color: ${AC}; }
      .g-atalho span { font-size: 13px; font-weight: 600; }
      .g-chat { grid-column: 1/5; flex-direction: row; align-items: center; gap: 8px; border-radius: 26px; padding: 6px 6px 6px 16px; }
      .g-chat input { flex: 1; background: transparent; border: none; outline: none; color: #ddd; font-family: inherit; font-size: 13.5px; min-width: 0; }
      .g-chat input::placeholder { color: #555; }
      .g-chat button { width: 36px; height: 36px; border-radius: 50%; border: none; background: ${AC}; color: #000; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
      .g-chat button svg { width: 15px; height: 15px; }

      /* financas */
      .resumo-top { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 14px; }
      .resumo-top .big { font-size: 30px; font-weight: 700; font-variant-numeric: tabular-nums; letter-spacing: -.02em; }
      .resumo-top .cmp { font-size: 12px; color: #9a9a9a; margin-top: 4px; }
      .resumo-top .cmp b { color: ${AC}; font-weight: 600; }
      .resumo-top .orc { text-align: right; font-size: 11px; color: #7a7a7a; max-width: 120px; }
      .tmap { position: relative; width: 100%; height: 280px; margin-bottom: 14px; }
      .tmap-cell { position: absolute; border-radius: 14px; padding: 9px 10px; overflow: hidden; }
      .tmap-cell .n { font-size: 11.5px; font-weight: 600; line-height: 1.2; }
      .tmap-cell .v { font-size: 12.5px; font-weight: 700; margin-top: 3px; font-variant-numeric: tabular-nums; }
      .fvsc { display: flex; gap: 10px; margin-bottom: 12px; }
      .fvsc .tile { flex: 1; }
      .lista { display: flex; flex-direction: column; }
      .li { display: flex; justify-content: space-between; align-items: center; padding: 10px 2px; border-bottom: 1px solid #1c1c1c; font-size: 13px; }
      .li .d { color: #7a7a7a; font-variant-numeric: tabular-nums; font-size: 11px; width: 44px; flex-shrink: 0; }
      .li .n { flex: 1; color: #ddd; padding: 0 6px; }
      .li .c { color: #7a7a7a; font-size: 10.5px; }
      .li .v { font-variant-numeric: tabular-nums; color: #f2f2f2; font-weight: 600; }
      .mais { width: 100%; text-align: center; padding: 12px; margin-top: 6px; border: none; border-radius: 14px; color: #ccc; font-size: 12.5px; background: #141414; min-height: 44px; }
      .toggle-btn { width: 100%; display: flex; justify-content: space-between; align-items: center; padding: 14px; border: none; border-radius: 18px; background: #141414; color: #eee; font-size: 13px; font-weight: 600; margin-bottom: 10px; min-height: 44px; }
      .toggle-btn svg { width: 15px; height: 15px; color: #8a8a8a; transition: transform .2s; }
      .toggle-btn.open svg { transform: rotate(90deg); }
      .panel-list { display: none; background: #0c0c0c; border-radius: 16px; padding: 4px 12px; margin: -4px 0 10px; }
      .panel-list.open { display: block; }
      .assin-row { display: flex; justify-content: space-between; padding: 10px 2px; font-size: 12.5px; border-bottom: 1px solid #1c1c1c; color: #ccc; }
      .assin-row:last-child { border-bottom: none; }
      .card-h { font-size: 12px; color: #8a8a8a; font-weight: 600; margin: 0 2px 8px; text-transform: uppercase; letter-spacing: .04em; }

      /* vida */
      .vgrid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 14px; }
      .vtile { background: #141414; border-radius: 16px; padding: 10px 6px; display: flex; flex-direction: column; align-items: center; gap: 6px; min-height: 64px; justify-content: center; }
      .vtile svg { width: 17px; height: 17px; color: #9a9a9a; }
      .vtile span { font-size: 9px; color: #9a9a9a; text-align: center; line-height: 1.15; font-weight: 500; }
      .vtile.on { background: ${AC}; }
      .vtile.on svg, .vtile.on span { color: #000; }
      .painel-vida { background: #141414; border-radius: 20px; padding: 16px; }
      .painel-vida h3 { margin: 0 0 6px; font-size: 15px; font-weight: 700; color: #fff; }
      .painel-vida p { margin: 4px 0; font-size: 12.5px; color: #9a9a9a; line-height: 1.5; }
      .painel-vida b { color: ${AC}; }

      .navbar { position: absolute; left: 0; right: 0; bottom: 0; display: flex; gap: 8px; padding: 10px 14px; background: linear-gradient(0deg,#000 60%,transparent); }
      .navbtn { flex: 1; min-height: 50px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px; background: #141414; border: none; border-radius: 16px; color: #777; }
      .navbtn svg { width: 16px; height: 16px; }
      .navbtn.on { background: ${AC}; color: #000; }
      .navbtn span { font-size: 9px; font-weight: 600; letter-spacing: .02em; }
    </style>
    <div class="wrap" id="wrap"></div>
    `;
    const wrap = root.getElementById("wrap");

    function topbar() {
      return `
        <div class="g-topbar">
          <div>
            <div class="relogio" id="relogio">--:--</div>
            <div class="data">${D.hoje.data.split("-").reverse().join("/")} · ${D.hoje.cidade}</div>
          </div>
          <button class="mic-btn" id="mic" aria-label="Comando de voz">${ICONS.mic}</button>
        </div>`;
    }

    function telaHoje() {
      const clima = D.hoje.clima || {};
      const pctMes = fin.gasto_mes_anterior ? fin.gasto_mes / fin.gasto_mes_anterior : 0;
      const delta = fin.gasto_mes_anterior ? Math.round((1 - fin.gasto_mes / fin.gasto_mes_anterior) * 100) : 0;
      const dias = fin.por_dia_mes || [];
      const chart = areaChart(dias, 300, 84, 4, fin.gasto_mes_anterior);
      const venc = fin.fatura_vencimento ? fin.fatura_vencimento.slice(8, 10) + "/" + fin.fatura_vencimento.slice(5, 7) : "—";
      wrap.innerHTML = `
        ${D.aviso_critico ? `<div class="aviso">${ICONS.alerta}<span>${D.aviso_critico}</span></div>` : ""}
        <div class="grid">
          ${topbar()}
          <div class="tile g-gasto">
            <div class="lbl">Gasto do mês</div>
            <div class="big" id="numGasto">R$ 0,00</div>
            <div class="cmp">vs mês anterior ${fmt(fin.gasto_mes_anterior || 0)} <b>${delta >= 0 ? "▼" : "▲"} ${Math.abs(delta)}%</b></div>
            <svg viewBox="0 0 300 90" preserveAspectRatio="none">
              <path d="${chart.area}" fill="${AC}" opacity=".16"/>
              ${chart.refY != null ? `<line x1="${chart.x0}" y1="${chart.refY.toFixed(1)}" x2="${chart.x1}" y2="${chart.refY.toFixed(1)}" stroke="#666" stroke-width="1" stroke-dasharray="3 3"/>
              <text x="${chart.x1}" y="${(chart.refY - 4).toFixed(1)}" text-anchor="end" font-size="8" fill="#8a8a8a" font-family="Inter">mês ant. ${fmt(fin.gasto_mes_anterior)}</text>` : ""}
              <path d="${chart.line}" fill="none" stroke="${AC}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" id="areaLine" />
              <text x="${chart.x0}" y="88" font-size="8" fill="#666" font-family="Inter">dia 1</text>
              <text x="${chart.x1}" y="88" text-anchor="end" font-size="8" fill="#666" font-family="Inter">dia ${dias.length}</text>
            </svg>
          </div>
          <div class="tile g-fatura">
            <div class="lbl">Fatura</div>
            <div class="num">${fmt(fin.fatura_atual || 0)}</div>
            <div class="lbl" style="margin-top:6px">vence ${venc}</div>
          </div>
          <div class="tile g-conta">
            <div class="lbl">Saldo em conta</div>
            <div class="num">${fmt(fin.saldo_conta || 0)}</div>
            <div class="lbl" style="margin-top:6px">hoje ${fmt(fin.gasto_hoje || 0)}</div>
          </div>
          <div class="tile g-foco">
            <div class="lbl">Em foco agora</div>
            <div class="txt">${(D.tarefas && D.tarefas.em_foco) || "—"}</div>
            <div class="sub">${D.tarefas && D.tarefas.pendentes ? D.tarefas.pendentes.length + " tarefas pendentes" : ""}</div>
          </div>
          <div class="tile g-clima">
            ${ICONS.chuva}
            <div class="num">${clima.temp}°</div>
            <div class="lbl">${clima.chuva_prob}% chuva</div>
          </div>
          <div class="tile g-hora">
            <div class="lbl">Agora</div>
            <div class="num" id="relogio2">--:--</div>
          </div>
          <div class="tile g-voz tap" id="btnVoz">${ICONS.mic}<span>Falar com o painel</span></div>
          <button class="tile g-atalho tap" data-t="financas">${ICONS.financas}<span>Finanças</span></button>
          <button class="tile g-atalho tap" data-t="vida">${ICONS.vida}<span>Vida</span></button>
          <div class="tile g-chat">
            <input placeholder="Pergunte algo…" />
            <button>${ICONS.enviar}</button>
          </div>
        </div>
      `;
      wrap.querySelectorAll("[data-t]").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.t)));

      function tick() {
        const now = new Date();
        const hh = now.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
        const a = root.getElementById("relogio"), b = root.getElementById("relogio2");
        if (a) a.textContent = hh; if (b) b.textContent = hh;
      }
      tick();
      timers.push(setInterval(tick, 15000));

      const numEl = root.getElementById("numGasto");
      const target = fin.gasto_mes || 0;
      const dur = ctx.reduzido ? 0 : 700;
      const t0 = performance.now();
      (function step(t) {
        const p = dur ? Math.min(1, (t - t0) / dur) : 1;
        numEl.textContent = fmt(target * (1 - Math.pow(1 - p, 3)));
        if (p < 1) requestAnimationFrame(step);
      })(t0);
    }

    function telaFinancas() {
      const cats = (fin.por_categoria || []).slice().sort((a, b) => b.valor - a.valor);
      const total = cats.reduce((s, c) => s + c.valor, 0) || 1;
      const diasMes = fin.por_dia_mes || [];
      const ultimos = (fin.ultimos_15_dias || []);
      const delta = fin.gasto_mes_anterior ? Math.round((1 - fin.gasto_mes / fin.gasto_mes_anterior) * 100) : 0;
      const venc = fin.fatura_vencimento ? fin.fatura_vencimento.slice(8, 10) + "/" + fin.fatura_vencimento.slice(5, 7) : "—";

      function evoChart() {
        const w = 300, h = 110, pad = 6;
        const ch = areaChart(diasMes, w, h, pad);
        const midIdx = Math.floor((diasMes.length - 1) / 2);
        return `<div class="lbl" style="margin-bottom:6px">Acumulado por dia · ${diasMes.length} dias</div>
        <svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="width:100%;height:${h}px;display:block">
          <line x1="${pad}" y1="${h - pad}" x2="${w - pad}" y2="${h - pad}" stroke="#262626" stroke-width="1"/>
          <line x1="${pad}" y1="${(h - pad) / 2}" x2="${w - pad}" y2="${(h - pad) / 2}" stroke="#1c1c1c" stroke-width="1"/>
          <path d="${ch.area}" fill="${AC}" opacity=".14"/>
          <path d="${ch.line}" fill="none" stroke="${AC}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
          <text x="${pad}" y="${h - pad + 9}" font-size="8" fill="#666" font-family="Inter">dia 1 · R$ 0</text>
          <text x="${(w - pad + pad) / 2}" y="9" text-anchor="middle" font-size="8" fill="#666" font-family="Inter">dia ${diasMes[midIdx] ? diasMes[midIdx].dia : ""} · ${fmt(diasMes[midIdx] ? diasMes[midIdx].acumulado : 0)}</text>
          <text x="${w - pad}" y="${h - pad + 9}" text-anchor="end" font-size="8" fill="#666" font-family="Inter">dia ${diasMes[diasMes.length - 1] ? diasMes[diasMes.length - 1].dia : ""} · ${fmt(fin.gasto_mes || 0)}</text>
        </svg>`;
      }
      function fvscChart() {
        const w = 300, h = 86, pad = 6, barH = 20, gap = 14;
        const max = Math.max(fin.fatura_atual || 0, fin.saldo_conta || 0, 1);
        const bw = w - pad * 2 - 92;
        const fw = (fin.fatura_atual || 0) / max * bw;
        const cw = (fin.saldo_conta || 0) / max * bw;
        const y1 = 10, y2 = y1 + barH + gap;
        return `<svg viewBox="0 0 ${w} ${h}" style="width:100%;height:${h}px;display:block">
          <text x="0" y="${y1 + barH / 2 + 3}" font-size="10.5" fill="#c8c8c8" font-family="Inter" font-weight="600">Fatura</text>
          <rect x="70" y="${y1}" width="${bw}" height="${barH}" rx="6" fill="#1c1c1c"/>
          <rect x="70" y="${y1}" width="${fw}" height="${barH}" rx="6" fill="${AC}"/>
          <text x="${70 + bw + 8}" y="${y1 + barH / 2 + 3}" font-size="10.5" fill="#fff" font-weight="700" font-family="Inter">${fmt(fin.fatura_atual || 0)}</text>
          <text x="0" y="${y2 + barH / 2 + 3}" font-size="10.5" fill="#c8c8c8" font-family="Inter" font-weight="600">Conta</text>
          <rect x="70" y="${y2}" width="${bw}" height="${barH}" rx="6" fill="#1c1c1c"/>
          <rect x="70" y="${y2}" width="${Math.max(2, cw)}" height="${barH}" rx="6" fill="#666"/>
          <text x="${70 + bw + 8}" y="${y2 + barH / 2 + 3}" font-size="10.5" fill="#fff" font-weight="700" font-family="Inter">${fmt(fin.saldo_conta || 0)}</text>
        </svg>
        <div class="lbl" style="margin-top:2px">vence ${venc} · saldo cobre ${fin.fatura_atual ? Math.round((fin.saldo_conta || 0) / fin.fatura_atual * 100) : 0}% da fatura</div>`;
      }

      wrap.innerHTML = `
        <div class="tab-title">Finanças</div>
        <div class="resumo-top">
          <div>
            <div class="lbl">Gasto do mês</div>
            <div class="big">${fmt(fin.gasto_mes || 0)}</div>
            <div class="cmp">vs anterior <b>${delta >= 0 ? "▼" : "▲"} ${Math.abs(delta)}%</b></div>
          </div>
          <div class="orc">${fin.orcamento_mes ? "orçamento " + fmt(fin.orcamento_mes) : "sem orçamento definido"}</div>
        </div>
        <div class="card-h">Gasto por categoria</div>
        <div class="tmap" id="tmap"></div>
        <div class="card-h">Evolução do mês</div>
        <div class="tile" style="margin-bottom:12px">${evoChart()}</div>
        <div class="card-h">Fatura × conta</div>
        <div class="tile" style="margin-bottom:12px">${fvscChart()}</div>
        <div class="card-h">Últimos 15 dias</div>
        <div class="lista" id="listaDias">${ultimos.slice(0, 6).map(li).join("")}</div>
        ${ultimos.length > 6 ? `<button class="mais" id="btnMais">carregar mais (${ultimos.length - 6})</button>` : ""}
        <button class="toggle-btn" id="btnAssin" style="margin-top:14px"><span>Assinaturas (${(fin.assinaturas || []).length})</span>${ICONS.chevron}</button>
        <div class="panel-list" id="assinList">
          ${(fin.assinaturas || []).map(a => `<div class="assin-row"><span>${a.nome}</span><span>${fmt(a.valor)}</span></div>`).join("")}
        </div>
        <button class="toggle-btn" id="btnExtrato"><span>Extrato completo</span>${ICONS.chevron}</button>
        <div class="panel-list" id="extratoList">${ultimos.map(li).join("")}</div>
      `;
      function li(d) {
        const dd = d.data.slice(8, 10) + "/" + d.data.slice(5, 7);
        return `<div class="li"><span class="d">${dd}</span><span class="n">${d.descricao}<br><span class="c">${d.categoria}</span></span><span class="v">${fmt(Math.abs(d.valor))}</span></div>`;
      }

      const tmapEl = root.getElementById("tmap");
      const tmapW = tmapEl.clientWidth || 328;
      const rects = treemap(cats.map(c => ({ value: c.valor, categoria: c.categoria })), 0, 0, tmapW, 280);
      tmapEl.innerHTML = rects.map((r, i) => {
        const t = i / Math.max(1, cats.length - 1);
        const col = lerp(AC, "#141414", 0.15 + t * 0.65);
        const small = r.w < 60 || r.h < 40;
        return `<div class="tmap-cell" style="left:${r.x.toFixed(1)}px;top:${r.y.toFixed(1)}px;width:${r.w.toFixed(1)}px;height:${r.h.toFixed(1)}px;background:${col.css};color:${col.lum > 0.55 ? "#0a0a0a" : "#fff"}">
          <div class="n">${r.categoria}</div>
          ${small ? "" : `<div class="v">${fmt(r.value)}</div>`}
        </div>`;
      }).join("");

      const btnMais = root.getElementById("btnMais");
      if (btnMais) btnMais.addEventListener("click", () => { root.getElementById("listaDias").innerHTML = ultimos.map(li).join(""); btnMais.remove(); });
      root.getElementById("btnAssin").addEventListener("click", (e) => { e.currentTarget.classList.toggle("open"); root.getElementById("assinList").classList.toggle("open"); });
      root.getElementById("btnExtrato").addEventListener("click", (e) => { e.currentTarget.classList.toggle("open"); root.getElementById("extratoList").classList.toggle("open"); });
    }

    function telaVida() {
      const secs = D.vida_secoes || [];
      let atual = secs[0] ? secs[0].id : null;
      wrap.innerHTML = `
        <div class="tab-title">Vida</div>
        <div class="vgrid" id="vgrid"></div>
        <div class="painel-vida" id="painel"></div>
      `;
      const vgrid = root.getElementById("vgrid");
      vgrid.innerHTML = secs.map((s, i) => `
        <button class="vtile ${s.id === atual ? "on" : ""}" data-id="${s.id}">
          ${ICOSET[i % ICOSET.length]}<span>${s.nome}</span>
        </button>`).join("");
      function seedBars(id, n) {
        let h = 0; for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
        const arr = [];
        for (let i = 0; i < n; i++) { h = (h * 1103515245 + 12345) >>> 0; arr.push(0.18 + (h % 100) / 100 * 0.8); }
        return arr;
      }
      function miniChart(id) {
        const vals = seedBars(id, 7);
        const w = 220, h = 46, bw = 18, gap = 8;
        const bars = vals.map((v, i) => {
          const x = i * (bw + gap);
          const bh = v * h;
          return `<rect x="${x}" y="${h - bh}" width="${bw}" height="${bh}" rx="4" fill="${i === vals.length - 1 ? AC : '#2a2a2a'}"/>`;
        }).join("");
        return `<svg viewBox="0 0 ${w} ${h}" style="width:100%;max-width:${w}px;height:${h}px;display:block;margin-top:8px">${bars}</svg>
        <div class="lbl" style="margin-top:4px">Atividade dos últimos 7 dias · dado de exemplo</div>`;
      }
      function painel(id) {
        const s = secs.find(x => x.id === id);
        if (!s) return;
        root.getElementById("painel").innerHTML = `
          <h3>${s.nome}</h3>
          <p>${s.resumo}</p>
          <p>Última atualização registrada nesta seção.</p>
          ${s.id === "viagens" && D.viagem ? `<p>Próxima viagem: <b>${D.viagem.origem} → ${D.viagem.destino}</b> em ${D.viagem.dias_faltando} dias (${D.viagem.data.split("-").reverse().join("/")}).</p>` : ""}
          ${miniChart(id)}
        `;
      }
      painel(atual);
      vgrid.querySelectorAll(".vtile").forEach(el => el.addEventListener("click", () => {
        atual = el.dataset.id;
        vgrid.querySelectorAll(".vtile").forEach(x => x.classList.toggle("on", x.dataset.id === atual));
        painel(atual);
      }));
    }

    function nav() {
      const tabs = [["hoje", ICONS.mic, "Hoje"], ["financas", ICONS.financas, "Finanças"], ["vida", ICONS.vida, "Vida"]];
      const bar = document.createElement("div");
      bar.className = "navbar";
      bar.innerHTML = tabs.map(([t, ic, lb]) => `<button class="navbtn ${ctx.tela === t ? "on" : ""}" data-t="${t}">${ic}<span>${lb}</span></button>`).join("");
      wrap.style.paddingBottom = "78px";
      wrap.after(bar);
      bar.querySelectorAll("button").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.t)));
      cleanups.push(() => bar.remove());
    }

    if (ctx.tela === "hoje") telaHoje();
    else if (ctx.tela === "financas") telaFinancas();
    else telaVida();
    nav();

    return () => { timers.forEach(clearInterval); cleanups.forEach(fn => fn()); };
  }
};
