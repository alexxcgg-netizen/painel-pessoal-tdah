(window.DIRECOES = window.DIRECOES || {})[4] = {
  nome: "Widgets",
  ideia: "Tela Hoje como a tela inicial do iPhone: grade de widgets pequenos, médios e grandes.",
  acento: "#30D158",
  fontes: ["Inter:wght@400;500;600;700;800"],
  render(root, D, ctx) {
    const AC = "#30D158";
    const fmt = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
    const fmt0 = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(v);
    const fin = D.financas || {};
    const timers = [], cleanups = [];

    const ICONS = {
      mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/><path d="M8 21h8"/></svg>',
      sol: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2.5M12 19v2.5M4.2 4.2l1.8 1.8M18 18l1.8 1.8M2.5 12H5M19 12h2.5M4.2 19.8L6 18M18 6l1.8-1.8"/></svg>',
      nuvem: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M7 17a4 4 0 0 1 .6-7.96A5 5 0 0 1 17.4 10.9 3.3 3.3 0 0 1 17 17H7z"/></svg>',
      alerta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 3.5l9.2 16H2.8L12 3.5z"/><path d="M12 10v4.2M12 17.2h.01"/></svg>',
      financas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="8.5"/><path d="M12 8v8M9.3 10c0-1.2 1.2-1.8 2.7-1.8s2.7.7 2.7 1.8-1.2 1.6-2.7 1.8-2.7.7-2.7 1.9 1.2 1.8 2.7 1.8 2.7-.5 2.7-1.8"/></svg>',
      vida: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3.2" y="3.2" width="7" height="7" rx="1.4"/><rect x="13.8" y="3.2" width="7" height="7" rx="1.4"/><rect x="3.2" y="13.8" width="7" height="7" rx="1.4"/><rect x="13.8" y="13.8" width="7" height="7" rx="1.4"/></svg>',
      tarefas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4.5 12.2l4 4 11-11.4"/></svg>',
      aviacao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 2.5v19M4 9.3l16 4.4M6.2 20.3l5.8-3 5.8 3"/></svg>',
      seta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M9 6l6 6-6 6"/></svg>',
      baixo: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M6 9l6 6 6-6"/></svg>',
      enviar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 12l16-8-6 16-3-7-7-1z"/></svg>',
      casa: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 11.5L12 4l8 7.5"/><path d="M6 10.5V20h12v-9.5"/></svg>',
      cifrao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 3v18M8 8c0-1.7 1.6-3 4-3s4 1 4 2.6-1.6 2.4-4 2.9-4 1-4 2.8S9.8 16 12 16s4-.7 4-2.6"/></svg>'
    };
    const ICOSET = [ICONS.vida, ICONS.tarefas, ICONS.financas, ICONS.aviacao, ICONS.casa, ICONS.cifrao];

    root.innerHTML = `
    <style>
      :host,*{box-sizing:border-box}
      .app{font-family:'Inter',sans-serif;color:#f2f2f4;position:relative;min-height:100%;padding-bottom:96px}
      .mono{font-variant-numeric:tabular-nums}
      .topo{display:flex;align-items:center;justify-content:space-between;padding:14px 16px 10px}
      .topo h1{margin:0;font-size:20px;font-weight:700;letter-spacing:-.01em}
      .topo .sub{margin:2px 0 0;font-size:12px;color:#8e8e93}
      .mic{width:44px;height:44px;border-radius:50%;border:none;background:#1c1c1e;color:${AC};display:flex;align-items:center;justify-content:center;flex-shrink:0}
      .mic svg{width:19px;height:19px}
      .aviso{display:flex;gap:9px;align-items:center;margin:2px 16px 12px;padding:11px 12px;border-radius:16px;background:rgba(255,99,99,.12);border:1px solid rgba(255,99,99,.32);color:#ff9b9b;font-size:12.5px}
      .aviso svg{width:16px;height:16px;flex-shrink:0}
      .grid{display:grid;grid-template-columns:repeat(4,1fr);grid-auto-rows:74px;gap:11px;padding:0 16px}
      .w{background:#1c1c1e;border-radius:20px;padding:13px 14px;position:relative;overflow:hidden;min-width:0}
      .w-sm{grid-column:span 2;grid-row:span 2}
      .w-md{grid-column:span 4;grid-row:span 2}
      .w-lg{grid-column:span 4;grid-row:span 4}
      .w-auto{grid-column:span 4;grid-row:auto;height:auto}
      .wl{font-size:10.5px;color:#9a9a9e;letter-spacing:.02em;display:flex;align-items:center;gap:5px}
      .wl svg{width:12px;height:12px;color:${AC}}
      .clockw .hh{font-size:25px;font-weight:700;margin-top:8px;letter-spacing:-.02em}
      .clockw .dd{font-size:10.5px;color:#9a9a9e;margin-top:1px}
      .clockw .clima{display:flex;align-items:center;gap:5px;margin-top:11px;font-size:12px;color:#d6d6da}
      .clockw .clima svg{width:14px;height:14px;color:${AC}}
      .focow .txt{font-size:13px;line-height:1.32;margin-top:9px;color:#eee;font-weight:500}
      .gastow .head{display:flex;justify-content:space-between;align-items:flex-start}
      .gastow .delta{font-size:11px;padding:3px 8px;border-radius:20px;background:rgba(48,209,88,.16);color:${AC};font-weight:600}
      .gastow .delta.up{background:rgba(255,159,10,.16);color:#ffb454}
      .gastow .num{font-size:29px;font-weight:800;margin-top:9px;letter-spacing:-.02em}
      .gastow .cmp{font-size:11px;color:#8e8e93;margin-top:2px}
      .chartbox{margin-top:12px}
      .chartbox svg{width:100%;display:block;overflow:visible}
      .statw{display:flex}
      .statw .it{flex:1;text-align:center}
      .statw .it+.it{border-left:1px solid #2c2c2e}
      .statw .n{font-size:15px;font-weight:700;margin-top:8px}
      .statw .s{font-size:9.5px;color:#8e8e93;margin-top:3px;text-transform:uppercase;letter-spacing:.05em}
      .atw{display:flex;justify-content:space-between;padding-top:6px}
      .atw button{background:none;border:none;color:inherit;display:flex;flex-direction:column;align-items:center;gap:6px;min-width:44px;min-height:44px}
      .atw .ic{width:38px;height:38px;border-radius:12px;background:#2c2c2e;display:flex;align-items:center;justify-content:center}
      .atw .ic svg{width:16px;height:16px;color:${AC}}
      .atw span{font-size:9.5px;color:#b8b8bc}
      .catw .li{display:flex;align-items:center;gap:9px;padding:8px 0}
      .catw .li .nome{width:104px;flex-shrink:0;font-size:11.5px;color:#d6d6da;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      .catw .li svg{flex:1;height:9px}
      .catw .li .val{width:64px;text-align:right;font-size:11px;color:#eee;flex-shrink:0}
      .fvcw{display:flex;gap:18px;margin-top:10px}
      .fvcw .it{flex:1}
      .fvcw .n{font-size:15px;font-weight:700;margin-top:6px}
      .fvcw .s{font-size:9.5px;color:#8e8e93;margin-top:2px}
      .toggle{width:100%;background:#1c1c1e;border:none;border-radius:16px;padding:13px 14px;display:flex;justify-content:space-between;align-items:center;color:#eee;font-size:12.5px;min-height:44px}
      .toggle svg{width:13px;height:13px;color:#8e8e93;transition:transform .18s}
      .toggle.open svg{transform:rotate(180deg)}
      .lista{display:none;background:#161618;border-radius:16px;margin-top:-8px;padding:6px 14px 4px}
      .lista.open{display:block}
      .row{display:flex;justify-content:space-between;padding:8px 0;font-size:12px;border-bottom:1px solid #232325;color:#c8c8cc}
      .row:last-child{border:none}
      .row .d{color:#7a7a7e;width:42px;flex-shrink:0}
      .row .n{flex:1;padding:0 6px;color:#dcdcdf}
      .mais{width:100%;background:none;border:1px dashed #3a3a3d;border-radius:12px;padding:10px;color:#9a9a9e;font-size:11.5px;margin-top:8px;min-height:44px}
      .stack{display:flex;flex-direction:column;gap:11px;padding:0 16px 8px}
      .secname{font-size:11px;color:#8e8e93;letter-spacing:.1em;text-transform:uppercase;margin:14px 16px 8px}
      .lifegrid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px 6px;padding:0 16px}
      .app-ic{display:flex;flex-direction:column;align-items:center;gap:6px;background:none;border:none;color:inherit;min-height:44px}
      .app-ic .box{width:52px;height:52px;border-radius:14px;background:#1c1c1e;display:flex;align-items:center;justify-content:center}
      .app-ic .box svg{width:21px;height:21px;color:${AC}}
      .app-ic span{font-size:9.5px;color:#c8c8cc;text-align:center;line-height:1.15;max-width:64px}
      .backdrop{position:absolute;inset:0;background:rgba(0,0,0,.55);opacity:0;pointer-events:none;transition:opacity .2s}
      .backdrop.on{opacity:1;pointer-events:auto}
      .sheet{position:absolute;left:0;right:0;bottom:0;background:#1c1c1e;border-radius:22px 22px 0 0;padding:10px 20px 26px;transform:translateY(102%);transition:transform .24s cubic-bezier(.2,.8,.2,1);max-height:78%;overflow-y:auto}
      .sheet.on{transform:translateY(0)}
      .sheet .handle{width:36px;height:4px;border-radius:3px;background:#48484a;margin:2px auto 14px}
      .sheet h3{margin:0;font-size:18px;font-weight:700}
      .sheet p{font-size:13px;color:#c4c4c8;line-height:1.55;margin:10px 0 0}
      .sheet .ex{font-size:9.5px;color:#7a7a7e;letter-spacing:.08em;text-transform:uppercase;margin:16px 0 6px}
      .chatpill{position:absolute;left:16px;right:16px;bottom:62px;display:flex;align-items:center;gap:8px;background:#1c1c1e;border-radius:22px;padding:5px 6px 5px 16px}
      .chatpill input{flex:1;background:none;border:none;outline:none;color:#eee;font-family:inherit;font-size:13px;min-width:0}
      .chatpill input::placeholder{color:#6a6a6e}
      .chatpill button{width:32px;height:32px;border-radius:50%;background:#2c2c2e;border:none;color:${AC};display:flex;align-items:center;justify-content:center;flex-shrink:0}
      .chatpill button svg{width:13px;height:13px}
      .dock{position:absolute;left:16px;right:16px;bottom:14px;height:40px;background:rgba(28,28,30,.94);border-radius:20px;display:flex}
      .dock button{flex:1;background:none;border:none;color:#8e8e93;font-size:10px;font-weight:600;display:flex;align-items:center;justify-content:center}
      .dock button.on{color:${AC}}
      button{font:inherit;cursor:pointer}
    </style>
    <div class="app" id="app"></div>
    `;
    const app = root.getElementById("app");

    function eixoY(vals) { return Math.max(1, ...vals); }
    function chartAcumulado(dias, w, h, refVal) {
      const max = Math.max(eixoY(dias.map(d => d.acumulado)), refVal || 0) * 1.08;
      const padL = 2, padR = 2, padT = 8, padB = 16;
      const iw = w - padL - padR, ih = h - padT - padB;
      const n = dias.length;
      const X = i => padL + (iw * i) / Math.max(1, n - 1);
      const Y = v => padT + ih - (ih * v) / max;
      const pts = dias.map((d, i) => [X(i), Y(d.acumulado)]);
      const line = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
      const area = line + ` L${pts[pts.length - 1][0]},${padT + ih} L${pts[0][0]},${padT + ih} Z`;
      const refY = refVal ? Y(refVal) : null;
      return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="height:${h}px">
        <defs><linearGradient id="ga4" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="${AC}" stop-opacity=".38"/><stop offset="1" stop-color="${AC}" stop-opacity="0"/>
        </linearGradient></defs>
        ${refY !== null ? `<line x1="${padL}" y1="${refY.toFixed(1)}" x2="${w - padR}" y2="${refY.toFixed(1)}" stroke="#5a5a5e" stroke-width="1" stroke-dasharray="3 3"/>` : ""}
        <path d="${area}" fill="url(#ga4)"/>
        <path d="${line}" fill="none" stroke="${AC}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
        <circle cx="${pts[pts.length - 1][0].toFixed(1)}" cy="${pts[pts.length - 1][1].toFixed(1)}" r="3" fill="${AC}"/>
        <text x="${padL}" y="${h - 3}" font-size="8.5" fill="#7a7a7e">dia 1</text>
        <text x="${w - padR}" y="${h - 3}" font-size="8.5" fill="#7a7a7e" text-anchor="end">dia ${dias[n - 1].dia}</text>
      </svg>`;
    }
    function barraCategoria(cats, w) {
      const max = eixoY(cats.map(c => c.valor));
      const bw = w - 178;
      return cats.slice(0, 6).map(c => {
        const pw = Math.max(2, (bw * c.valor) / max);
        return `<div class="li"><span class="nome">${c.categoria}</span>
          <svg viewBox="0 0 ${bw} 9" preserveAspectRatio="none"><rect x="0" y="0" width="${bw}" height="9" rx="3" fill="#2c2c2e"/><rect x="0" y="0" width="${pw.toFixed(1)}" height="9" rx="3" fill="${AC}"/></svg>
          <span class="val mono">${fmt0(c.valor)}</span></div>`;
      }).join("");
    }
    function barrasDelta(dias, w, h) {
      const deltas = dias.map((d, i) => Math.max(0, d.acumulado - (i ? dias[i - 1].acumulado : 0)));
      const max = eixoY(deltas);
      const n = deltas.length;
      const gap = 2, bw = (w - gap * (n - 1)) / n;
      const padB = 15, ih = h - padB;
      const bars = deltas.map((v, i) => {
        const bh = Math.max(v > 0 ? 2 : 0, (ih * v) / max);
        return `<rect x="${(i * (bw + gap)).toFixed(1)}" y="${(ih - bh).toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" rx="1.2" fill="${AC}" opacity="${i === n - 1 ? 1 : .55}"/>`;
      }).join("");
      return `<svg viewBox="0 0 ${w} ${h}" style="height:${h}px;width:100%">${bars}
        <text x="0" y="${h - 2}" font-size="8" fill="#7a7a7e">dia 1</text>
        <text x="${w}" y="${h - 2}" font-size="8" fill="#7a7a7e" text-anchor="end">dia ${n}</text>
      </svg>`;
    }
    function barraDupla(a, b, la, lb, w) {
      const max = Math.max(a, b, 1);
      const pa = (w * a) / max, pb = (w * b) / max;
      return `<svg viewBox="0 0 ${w} 34" style="width:100%;height:34px">
        <rect x="0" y="2" width="${w}" height="8" rx="4" fill="#2c2c2e"/><rect x="0" y="2" width="${pa.toFixed(1)}" height="8" rx="4" fill="${AC}"/>
        <rect x="0" y="24" width="${w}" height="8" rx="4" fill="#2c2c2e"/><rect x="0" y="24" width="${pb.toFixed(1)}" height="8" rx="4" fill="#6d6d72"/>
      </svg>`;
    }
    function barraExemplo(vals, w, h) {
      const max = eixoY(vals);
      const n = vals.length, gap = 3, bw = (w - gap * (n - 1)) / n;
      return `<svg viewBox="0 0 ${w} ${h}" style="width:100%;height:${h}px">${vals.map((v, i) => {
        const bh = Math.max(2, (h * v) / max);
        return `<rect x="${(i * (bw + gap)).toFixed(1)}" y="${(h - bh).toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" rx="2" fill="${AC}" opacity="${.4 + .6 * (v / max)}"/>`;
      }).join("")}</svg>`;
    }

    function dock(tela) {
      return `<div class="dock">
        ${["hoje", "financas", "vida"].map(t => `<button data-t="${t}" class="${tela === t ? "on" : ""}">${t === "hoje" ? "Hoje" : t === "financas" ? "Finanças" : "Vida"}</button>`).join("")}
      </div>`;
    }
    function ligarDock() {
      app.querySelectorAll(".dock button").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.t)));
    }

    function telaHoje() {
      const clima = D.hoje.clima || {};
      const pctDelta = fin.gasto_mes_anterior ? (fin.gasto_mes / fin.gasto_mes_anterior - 1) * 100 : 0;
      app.innerHTML = `
        <div class="topo">
          <div><h1>Hoje</h1><p class="sub">${D.hoje.data} · ${D.hoje.cidade}</p></div>
          <button class="mic" id="mic">${ICONS.mic}</button>
        </div>
        ${D.aviso_critico ? `<div class="aviso">${ICONS.alerta}<span>${D.aviso_critico}</span></div>` : ""}
        <div class="grid">
          <div class="w w-sm clockw">
            <div class="wl">RELÓGIO</div>
            <div class="hh mono" id="relogio">--:--</div>
            <div class="dd">${D.hoje.data.slice(8, 10)}/${D.hoje.data.slice(5, 7)}</div>
            <div class="clima">${clima.temp >= 22 ? ICONS.sol : ICONS.nuvem}<span>${clima.temp}° · ${clima.chuva_prob}% chuva</span></div>
          </div>
          <div class="w w-sm focow">
            <div class="wl">EM FOCO AGORA</div>
            <div class="txt">${(D.tarefas && D.tarefas.em_foco) || "Nada no momento"}</div>
          </div>
          <div class="w w-lg gastow">
            <div class="head">
              <div class="wl">${ICONS.financas} GASTO DO MÊS</div>
              <span class="delta ${pctDelta > 0 ? "up" : ""}">${pctDelta > 0 ? "+" : ""}${pctDelta.toFixed(0)}%</span>
            </div>
            <div class="num mono">${fmt(fin.gasto_mes || 0)}</div>
            <div class="cmp">mês anterior ${fmt(fin.gasto_mes_anterior || 0)}</div>
            <div class="chartbox">${chartAcumulado(fin.por_dia_mes || [], 296, 150, fin.gasto_mes_anterior)}</div>
          </div>
          <div class="w w-md statw">
            <div class="it"><div class="s">HOJE</div><div class="n mono">${fmt0(fin.gasto_hoje || 0)}</div></div>
            <div class="it"><div class="s">FATURA</div><div class="n mono">${fmt0(fin.fatura_atual || 0)}</div></div>
            <div class="it"><div class="s">CONTA</div><div class="n mono">${fmt0(fin.saldo_conta || 0)}</div></div>
          </div>
          <div class="w w-md atw">
            ${[["financas", ICONS.financas, "Finanças"], ["vida", ICONS.vida, "Vida"], ["vida", ICONS.tarefas, "Tarefas"], ["vida", ICONS.aviacao, "Aviação"]]
              .map(([t, ic, lb]) => `<button data-t="${t}"><span class="ic">${ic}</span><span>${lb}</span></button>`).join("")}
          </div>
        </div>
        <div class="chatpill"><input placeholder="Perguntar ao painel…"/><button>${ICONS.enviar}</button></div>
        ${dock("hoje")}
      `;
      app.querySelectorAll(".atw button").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.t)));
      ligarDock();
      const rel = root.getElementById("relogio");
      function tick() { rel.textContent = new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }); }
      tick();
      if (!ctx.reduzido) timers.push(setInterval(tick, 15000));
    }

    function telaFinancas() {
      const dias = fin.ultimos_15_dias || [];
      const pctDelta = fin.gasto_mes_anterior ? (fin.gasto_mes / fin.gasto_mes_anterior - 1) * 100 : 0;
      app.innerHTML = `
        <div class="secname">Finanças</div>
        <div class="stack">
          <div class="w w-auto gastow" style="grid-column:auto">
            <div class="head"><div class="wl">RESUMO DO MÊS</div><span class="delta ${pctDelta > 0 ? "up" : ""}">${pctDelta > 0 ? "+" : ""}${pctDelta.toFixed(0)}% vs ant.</span></div>
            <div class="num mono">${fmt(fin.gasto_mes || 0)}</div>
            <div class="cmp">mês anterior ${fmt(fin.gasto_mes_anterior || 0)}</div>
          </div>
          <div class="w w-auto catw">
            <div class="wl">GASTO POR CATEGORIA</div>
            <div style="margin-top:6px">${barraCategoria(fin.por_categoria || [], 328)}</div>
          </div>
          <div class="w w-auto">
            <div class="wl">EVOLUÇÃO POR DIA (gasto diário)</div>
            <div class="chartbox">${barrasDelta(fin.por_dia_mes || [], 328, 84)}</div>
          </div>
          <div class="w w-auto">
            <div class="wl">FATURA × CONTA</div>
            ${barraDupla(fin.fatura_atual || 0, fin.saldo_conta || 0, "Fatura", "Conta", 328)}
            <div class="fvcw"><div class="it"><div class="n mono">${fmt(fin.fatura_atual || 0)}</div><div class="s">fatura · vence ${fin.fatura_vencimento ? fin.fatura_vencimento.slice(8, 10) + "/" + fin.fatura_vencimento.slice(5, 7) : "—"}</div></div>
            <div class="it"><div class="n mono">${fmt(fin.saldo_conta || 0)}</div><div class="s">saldo em conta</div></div></div>
          </div>
          <div class="w w-auto">
            <div class="wl">ÚLTIMOS DIAS</div>
            <div id="listaDias">${dias.slice(0, 6).map(li).join("")}</div>
            ${dias.length > 6 ? `<button class="mais" id="btnMais">carregar mais (${dias.length - 6})</button>` : ""}
          </div>
          <button class="toggle" id="btnAssin"><span>Assinaturas (${(fin.assinaturas || []).length})</span>${ICONS.baixo}</button>
          <div class="lista" id="assinList">${(fin.assinaturas || []).map(a => `<div class="row"><span class="n">${a.nome}</span><span class="mono">${fmt(a.valor)}</span></div>`).join("")}</div>
          <button class="toggle" id="btnExtrato"><span>Extrato completo</span>${ICONS.baixo}</button>
          <div class="lista" id="extratoList">${dias.map(li).join("")}</div>
        </div>
        <div style="height:20px"></div>
        ${dock("financas")}
      `;
      function li(d) {
        return `<div class="row"><span class="d mono">${d.data.slice(8, 10)}/${d.data.slice(5, 7)}</span><span class="n">${d.descricao}</span><span class="mono">${fmt(Math.abs(d.valor))}</span></div>`;
      }
      const btnMais = root.getElementById("btnMais");
      if (btnMais) btnMais.addEventListener("click", () => { root.getElementById("listaDias").innerHTML = dias.map(li).join(""); btnMais.remove(); });
      root.getElementById("btnAssin").addEventListener("click", function () { this.classList.toggle("open"); root.getElementById("assinList").classList.toggle("open"); });
      root.getElementById("btnExtrato").addEventListener("click", function () { this.classList.toggle("open"); root.getElementById("extratoList").classList.toggle("open"); });
      ligarDock();
    }

    function telaVida() {
      const secs = D.vida_secoes || [];
      app.innerHTML = `
        <div class="secname">Vida</div>
        <div class="lifegrid" id="lifegrid">
          ${secs.map((s, i) => `<button class="app-ic" data-id="${s.id}"><span class="box">${ICOSET[i % ICOSET.length]}</span><span>${s.nome}</span></button>`).join("")}
        </div>
        <div class="backdrop" id="backdrop"></div>
        <div class="sheet" id="sheet">
          <div class="handle"></div>
          <h3 id="shTitulo"></h3>
          <p id="shResumo"></p>
          <p id="shExtra1"></p>
          <p id="shExtra2"></p>
          <div class="ex">progresso (exemplo)</div>
          <div id="shChart"></div>
        </div>
        ${dock("vida")}
      `;
      function seed(str) { let h = 0; for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0; return h; }
      function abrir(s) {
        root.getElementById("shTitulo").textContent = s.nome;
        root.getElementById("shResumo").textContent = s.resumo;
        root.getElementById("shExtra1").textContent = "Última atualização registrada nesta seção.";
        root.getElementById("shExtra2").textContent = D.viagem && /viage/i.test(s.nome) ? `Próxima viagem: ${D.viagem.origem} → ${D.viagem.destino} em ${D.viagem.dias_faltando} dias (${D.viagem.data}).` : "Toque no atalho de fechar para voltar à grade.";
        const sd = seed(s.id);
        const vals = Array.from({ length: 7 }, (_, i) => 20 + ((sd >> (i * 3)) % 80));
        root.getElementById("shChart").innerHTML = barraExemplo(vals, 296, 60);
        root.getElementById("backdrop").classList.add("on");
        root.getElementById("sheet").classList.add("on");
      }
      function fechar() { root.getElementById("backdrop").classList.remove("on"); root.getElementById("sheet").classList.remove("on"); }
      root.querySelectorAll(".app-ic").forEach(b => b.addEventListener("click", () => abrir(secs.find(s => s.id === b.dataset.id))));
      root.getElementById("backdrop").addEventListener("click", fechar);
      ligarDock();
    }

    if (ctx.tela === "hoje") telaHoje();
    else if (ctx.tela === "financas") telaFinancas();
    else telaVida();

    return () => { timers.forEach(clearInterval); cleanups.forEach(fn => fn()); };
  }
};
