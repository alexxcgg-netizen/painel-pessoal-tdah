(window.DIRECOES = window.DIRECOES || {})[18] = {
  nome: "Planilha",
  ideia: "Tudo como uma planilha clara: cabeçalhos fixos, células alinhadas, abas embaixo, barra de fórmula.",
  acento: "#1D6F42",
  fontes: ["Inter:wght@400;500;600;700", "Roboto+Mono:wght@400;500;700"],
  render(root, D, ctx) {
    const AC = "#1D6F42";
    const fmt = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
    const fmt0 = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(v);
    const fin = D.financas || {};
    const timers = [], cleanups = [];

    const ICONS = {
      mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/><path d="M8 21h8"/></svg>',
      fx: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M8 4c-3 0-3 3-3 5v6c0 2 0 5-3 5M8 20c3 0 3-3 3-5v-6c0-2 0-5 3-5M13 10h6M15 6l4 8M19 6l-4 8"/></svg>',
      alerta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 3.5l9.2 16H2.8L12 3.5z"/><path d="M12 10v4.2M12 17.2h.01"/></svg>',
      sol: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2.5M12 19v2.5M4.2 4.2l1.8 1.8M18 18l1.8 1.8M2.5 12H5M19 12h2.5M4.2 19.8L6 18M18 6l1.8-1.8"/></svg>',
      nuvem: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M7 17a4 4 0 0 1 .6-7.96A5 5 0 0 1 17.4 10.9 3.3 3.3 0 0 1 17 17H7z"/></svg>',
      financas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="8.5"/><path d="M12 8v8M9.3 10c0-1.2 1.2-1.8 2.7-1.8s2.7.7 2.7 1.8-1.2 1.6-2.7 1.8-2.7.7-2.7 1.9 1.2 1.8 2.7 1.8 2.7-.5 2.7-1.8"/></svg>',
      vida: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3.2" y="3.2" width="7" height="7" rx="1.4"/><rect x="13.8" y="3.2" width="7" height="7" rx="1.4"/><rect x="3.2" y="13.8" width="7" height="7" rx="1.4"/><rect x="13.8" y="13.8" width="7" height="7" rx="1.4"/></svg>',
      tarefas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4.5 12.2l4 4 11-11.4"/></svg>',
      aviacao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 2.5v19M4 9.3l16 4.4M6.2 20.3l5.8-3 5.8 3"/></svg>',
      baixo: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"><path d="M6 9l6 6 6-6"/></svg>',
      enviar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 12l16-8-6 16-3-7-7-1z"/></svg>'
    };

    root.innerHTML = `
    <style>
      :host,*{box-sizing:border-box}
      .app{font-family:'Inter',sans-serif;color:#1f2328;background:#fff;position:relative;min-height:760px;padding-bottom:108px}
      .mono{font-family:'Roboto Mono',monospace;font-variant-numeric:tabular-nums}
      .toolbar{display:flex;align-items:center;gap:8px;padding:10px 12px;border-bottom:1px solid #d7dbe0;background:#f6f7f9;position:sticky;top:0;z-index:3}
      .toolbar .ref{font-family:'Roboto Mono',monospace;font-size:11.5px;font-weight:700;color:${AC};background:#fff;border:1px solid #d7dbe0;border-radius:4px;padding:5px 9px;min-width:34px;text-align:center}
      .toolbar .fxi{width:16px;height:16px;color:#8a939c;flex-shrink:0;display:inline-flex}
      .toolbar .fxi svg{width:16px;height:16px;display:block}
      .toolbar .fbar{flex:1;font-family:'Roboto Mono',monospace;font-size:11px;color:#3a4048;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;background:#fff;border:1px solid #d7dbe0;border-radius:4px;padding:7px 10px;min-height:30px;display:flex;align-items:center}
      .mic{width:40px;height:40px;border-radius:6px;border:1px solid #d7dbe0;background:#fff;color:${AC};display:flex;align-items:center;justify-content:center;flex-shrink:0}
      .mic svg{width:17px;height:17px}
      .aviso{display:flex;gap:8px;align-items:center;margin:0;padding:10px 14px;background:#fdeceb;border-bottom:1px solid #f3c6c2;color:#b42318;font-size:12px;font-weight:500}
      .aviso svg{width:15px;height:15px;flex-shrink:0}
      .hd{display:grid;grid-template-columns:30px 1fr 100px 40px;position:sticky;top:45px;z-index:2;background:#eef0f2;border-bottom:1px solid #d7dbe0}
      .hd span{font-family:'Roboto Mono',monospace;font-size:10px;color:#6b7280;text-align:center;padding:6px 4px;border-right:1px solid #e1e4e8}
      .rows{padding-bottom:6px}
      .r{display:grid;grid-template-columns:30px 1fr 100px 40px;border-bottom:1px solid #e9ebed;min-height:38px}
      .r.tap{cursor:pointer}
      .r.tap:active{background:#f6f9f7}
      .rn{background:#f6f7f9;color:#9099a1;font-family:'Roboto Mono',monospace;font-size:10px;display:flex;align-items:center;justify-content:center;border-right:1px solid #e1e4e8}
      .c{padding:8px 9px;font-size:12px;display:flex;align-items:center;border-right:1px solid #eef0f2;min-width:0}
      .c:last-child{border-right:none}
      .c1{color:#1f2328;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      .c2{justify-content:flex-end;font-family:'Roboto Mono',monospace;color:#1f2328;font-weight:500}
      .c3{justify-content:center;color:#8a939c;font-size:9.5px}
      .lbl{color:#5c6470}
      .sel{outline:2px solid ${AC};outline-offset:-2px;background:#f2f8f4}
      .big{font-size:15px;font-weight:700;color:${AC}}
      .merge{grid-column:2/5;padding:10px 10px 12px;display:block}
      .merge .cap{font-size:9.5px;color:#8a939c;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px}
      .merge svg{width:100%;display:block}
      .databar{position:relative}
      .databar i{position:absolute;left:0;top:2px;bottom:2px;background:rgba(29,111,66,.16);z-index:0}
      .databar span{position:relative;z-index:1}
      .atrow{display:flex;gap:6px;padding:8px 9px}
      .atbtn{flex:1;display:flex;flex-direction:column;align-items:center;gap:4px;border:1px solid #d7dbe0;border-radius:6px;background:#fff;padding:8px 2px;min-height:44px;color:#3a4048}
      .atbtn svg{width:15px;height:15px;color:${AC}}
      .atbtn span{font-size:8.5px;color:#5c6470}
      .toggle{display:flex;justify-content:space-between;align-items:center;padding:11px 12px;border-bottom:1px solid #e9ebed;color:#1f2328;font-size:12.5px;font-weight:500;min-height:44px}
      .toggle svg{width:13px;height:13px;color:#8a939c;transition:transform .18s}
      .toggle.open svg{transform:rotate(180deg)}
      .sub{display:none}
      .sub.open{display:block}
      .mais{width:100%;text-align:center;padding:10px;border-bottom:1px solid #e9ebed;color:${AC};font-size:11.5px;font-weight:600;background:#f6f9f7;min-height:44px}
      .painel{padding:12px 14px 4px}
      .painel h3{margin:0 0 4px;font-size:14.5px;font-weight:700}
      .painel p{margin:4px 0;font-size:12px;color:#5c6470;line-height:1.5}
      .painel .cap{font-size:9.5px;color:#8a939c;text-transform:uppercase;letter-spacing:.05em;margin:12px 0 6px}
      .chatbar{position:absolute;left:0;right:0;bottom:40px;display:flex;align-items:center;gap:8px;border-top:1px solid #d7dbe0;background:#f6f7f9;padding:8px 12px}
      .chatbar input{flex:1;background:#fff;border:1px solid #d7dbe0;border-radius:5px;padding:8px 10px;font-family:'Roboto Mono',monospace;font-size:11.5px;color:#1f2328;outline:none;min-width:0}
      .chatbar input::placeholder{color:#9099a1}
      .chatbar button{width:34px;height:34px;border-radius:5px;border:1px solid #d7dbe0;background:#fff;color:${AC};display:flex;align-items:center;justify-content:center;flex-shrink:0}
      .chatbar button svg{width:14px;height:14px}
      .tabs{position:absolute;left:0;right:0;bottom:0;display:flex;background:#e4e7ea;border-top:1px solid #d7dbe0;height:40px}
      .tabs button{flex:1;border:none;background:transparent;color:#6b7280;font-size:11px;font-weight:600;border-right:1px solid #d7dbe0}
      .tabs button.on{background:#fff;color:${AC};border-top:2px solid ${AC};margin-top:-1px}
      button{font:inherit;cursor:pointer}
    </style>
    <div class="app" id="app"></div>
    `;
    const app = root.getElementById("app");
    let refCell = "A1", fbar = "Toque numa linha para ver o detalhe.";

    function eixoY(vals) { return Math.max(1, ...vals); }
    function linhaChart(dias, w, h) {
      const max = eixoY(dias.map(d => d.acumulado)) * 1.08;
      const n = dias.length, padB = 14;
      const ih = h - padB;
      const X = i => (w * i) / Math.max(1, n - 1);
      const Y = v => ih - (ih * v) / max;
      const pts = dias.map((d, i) => [X(i), Y(d.acumulado)]);
      const line = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
      const area = line + ` L${pts[pts.length - 1][0]},${ih} L0,${ih} Z`;
      return `<svg viewBox="0 0 ${w} ${h}" style="height:${h}px">
        <defs><linearGradient id="gs18" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${AC}" stop-opacity=".22"/><stop offset="1" stop-color="${AC}" stop-opacity="0"/></linearGradient></defs>
        ${[0.25, 0.5, 0.75].map(f => `<line x1="0" y1="${(ih * f).toFixed(1)}" x2="${w}" y2="${(ih * f).toFixed(1)}" stroke="#eef0f2" stroke-width="1"/>`).join("")}
        <path d="${area}" fill="url(#gs18)"/><path d="${line}" fill="none" stroke="${AC}" stroke-width="1.8" stroke-linecap="round"/>
        <circle cx="${pts[n - 1][0].toFixed(1)}" cy="${pts[n - 1][1].toFixed(1)}" r="2.6" fill="${AC}"/>
        <text x="0" y="${h - 2}" font-size="8" fill="#9099a1" font-family="Roboto Mono">dia 1</text>
        <text x="${w}" y="${h - 2}" font-size="8" fill="#9099a1" font-family="Roboto Mono" text-anchor="end">dia ${dias[n - 1].dia}</text>
      </svg>`;
    }
    function barrasChart(dias, w, h) {
      const deltas = dias.map((d, i) => Math.max(0, d.acumulado - (i ? dias[i - 1].acumulado : 0)));
      const max = eixoY(deltas), n = deltas.length, gap = 2, bw = (w - gap * (n - 1)) / n, padB = 14, ih = h - padB;
      return `<svg viewBox="0 0 ${w} ${h}" style="height:${h}px">
        ${deltas.map((v, i) => `<rect x="${(i * (bw + gap)).toFixed(1)}" y="${(ih - Math.max(v > 0 ? 1.5 : 0, (ih * v) / max)).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(v > 0 ? 1.5 : 0, (ih * v) / max).toFixed(1)}" fill="${AC}" opacity="${i === n - 1 ? 1 : .5}"/>`).join("")}
        <text x="0" y="${h - 2}" font-size="8" fill="#9099a1" font-family="Roboto Mono">dia 1</text>
        <text x="${w}" y="${h - 2}" font-size="8" fill="#9099a1" font-family="Roboto Mono" text-anchor="end">dia ${n}</text>
      </svg>`;
    }
    function barraExemplo(vals, w, h) {
      const max = eixoY(vals), n = vals.length, gap = 3, bw = (w - gap * (n - 1)) / n;
      return `<svg viewBox="0 0 ${w} ${h}" style="width:100%;height:${h}px">${vals.map((v, i) => {
        const bh = Math.max(2, (h * v) / max);
        return `<rect x="${(i * (bw + gap)).toFixed(1)}" y="${(h - bh).toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" rx="1.5" fill="${AC}" opacity="${.35 + .65 * (v / max)}"/>`;
      }).join("")}</svg>`;
    }
    function dataBarCell(val, max, texto) {
      const pw = Math.min(100, (val / max) * 100);
      return `<span class="c c2 databar"><i style="width:${pw.toFixed(1)}%"></i><span>${texto}</span></span>`;
    }

    function toolbar(refDefault) {
      return `<div class="toolbar"><span class="ref" id="ref">${refDefault}</span><span class="fxi">${ICONS.fx}</span><span class="fbar" id="fbar">${fbar}</span><button class="mic" id="mic">${ICONS.mic}</button></div>`;
    }
    function tabs(tela) {
      return `<div class="tabs">${["hoje", "financas", "vida"].map(t => `<button data-t="${t}" class="${tela === t ? "on" : ""}">${t === "hoje" ? "Hoje" : t === "financas" ? "Finanças" : "Vida"}</button>`).join("")}</div>`;
    }
    function ligarTabs() { app.querySelectorAll(".tabs button").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.t))); }
    function selecionar(ref, texto, cellEl) {
      app.querySelectorAll(".sel").forEach(e => e.classList.remove("sel"));
      if (cellEl) cellEl.classList.add("sel");
      root.getElementById("ref").textContent = ref;
      root.getElementById("fbar").textContent = texto;
    }

    function telaHoje() {
      const clima = D.hoje.clima || {};
      let rn = 1;
      const row = (a, b, c, opts = {}) => {
        rn++;
        return `<div class="r ${opts.tap ? "tap" : ""}" ${opts.ref ? `data-ref="A${rn}" data-txt="${opts.txt || ""}"` : ""}>
          <span class="rn">${rn - 1}</span>
          <span class="c c1 lbl">${a}</span>
          <span class="c c2 ${opts.big ? "big" : ""}">${b}</span>
          <span class="c c3">${c || ""}</span>
        </div>`;
      };
      const merge = (cap, html, opts = {}) => {
        rn++;
        return `<div class="r"><span class="rn">${rn - 1}</span><div class="merge" ${opts.pad ? `style="padding-top:8px"` : ""}><div class="cap">${cap}</div>${html}</div></div>`;
      };
      app.innerHTML = `
        ${toolbar("B2")}
        ${D.aviso_critico ? `<div class="aviso">${ICONS.alerta}<span>${D.aviso_critico}</span></div>` : ""}
        <div class="hd"><span></span><span>A</span><span>B</span><span>C</span></div>
        <div class="rows" id="rows">
          ${row("Data", D.hoje.data.slice(8, 10) + "/" + D.hoje.data.slice(5, 7) + "/" + D.hoje.data.slice(0, 4), D.hoje.cidade)}
          ${row("Hora", `<span id="relogio" class="mono">--:--</span>`, "ao vivo")}
          ${row("Clima", clima.temp + "°C", (clima.chuva_prob != null ? clima.chuva_prob + "%" : ""), { tap: true, ref: true, txt: `${clima.cond}, ${clima.chuva_prob}% de chance de chuva` })}
          ${row("Gasto do mês", fmt(fin.gasto_mes || 0), (fin.gasto_mes_anterior ? ((fin.gasto_mes / fin.gasto_mes_anterior - 1) * 100).toFixed(0) + "%" : ""), { big: true, tap: true, ref: true, txt: `Gasto do mês ${fmt(fin.gasto_mes || 0)} · mês anterior ${fmt(fin.gasto_mes_anterior || 0)}` })}
          ${merge("Acumulado no mês — por_dia_mes", linhaChart(fin.por_dia_mes || [], 328, 92))}
          ${row("Hoje", fmt(fin.gasto_hoje || 0))}
          ${row("Fatura", fmt(fin.fatura_atual || 0), fin.fatura_vencimento ? "vence " + fin.fatura_vencimento.slice(8, 10) + "/" + fin.fatura_vencimento.slice(5, 7) : "", { tap: true, ref: true, txt: `Fatura atual ${fmt(fin.fatura_atual || 0)}, vencimento ${fin.fatura_vencimento || "—"}` })}
          ${row("Conta", fmt(fin.saldo_conta || 0))}
          ${row("Em foco agora", (D.tarefas && D.tarefas.em_foco) || "—", "", { tap: true, ref: true, txt: `Em foco agora: ${(D.tarefas && D.tarefas.em_foco) || "nada no momento"}` })}
          ${merge("Atalhos", `<div class="atrow">
              <button class="atbtn" data-t="financas">${ICONS.financas}<span>Finanças</span></button>
              <button class="atbtn" data-t="vida">${ICONS.vida}<span>Vida</span></button>
              <button class="atbtn" data-t="vida">${ICONS.tarefas}<span>Tarefas</span></button>
              <button class="atbtn" data-t="vida">${ICONS.aviacao}<span>Aviação</span></button>
            </div>`, { pad: true })}
        </div>
        <div class="chatbar"><input placeholder="=PERGUNTAR(&quot;ao painel…&quot;)"/><button>${ICONS.enviar}</button></div>
        ${tabs("hoje")}
      `;
      app.querySelectorAll("[data-ref]").forEach(el => el.addEventListener("click", () => selecionar(el.dataset.ref, el.dataset.txt, el.querySelector(".c2"))));
      app.querySelectorAll("[data-t]").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.t)));
      const rel = root.getElementById("relogio");
      function tick() { rel.textContent = new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }); }
      tick();
      if (!ctx.reduzido) timers.push(setInterval(tick, 15000));
    }

    function telaFinancas() {
      const cats = fin.por_categoria || [];
      const maxCat = eixoY(cats.map(c => c.valor));
      const totalCat = cats.reduce((s, c) => s + c.valor, 0) || 1;
      const dias = fin.ultimos_15_dias || [];
      const pctDelta = fin.gasto_mes_anterior ? (fin.gasto_mes / fin.gasto_mes_anterior - 1) * 100 : 0;
      app.innerHTML = `
        ${toolbar("B2")}
        <div class="hd"><span></span><span>A</span><span>B</span><span>C</span></div>
        <div class="rows" id="rows">
          <div class="r tap" data-ref="B2" data-txt="Gasto do mês ${fmt(fin.gasto_mes || 0)} (${pctDelta > 0 ? "+" : ""}${pctDelta.toFixed(0)}% vs mês anterior)"><span class="rn">1</span><span class="c c1 lbl">Gasto do mês</span><span class="c c2 big">${fmt(fin.gasto_mes || 0)}</span><span class="c c3">${pctDelta > 0 ? "+" : ""}${pctDelta.toFixed(0)}%</span></div>
          <div class="r"><span class="rn">2</span><span class="c c1 lbl" style="font-weight:600">Categoria</span><span class="c c2" style="font-weight:600">Valor</span><span class="c c3" style="font-weight:600">%</span></div>
          ${cats.map((c, i) => `<div class="r tap" data-ref="B${i + 3}" data-txt="${c.categoria}: ${fmt(c.valor)} (${((c.valor / totalCat) * 100).toFixed(0)}% do mês)"><span class="rn">${i + 3}</span><span class="c c1">${c.categoria}</span>${dataBarCell(c.valor, maxCat, fmt0(c.valor))}<span class="c c3">${((c.valor / totalCat) * 100).toFixed(0)}%</span></div>`).join("")}
          <div class="r"><span class="rn">${cats.length + 3}</span><div class="merge"><div class="cap">Evolução por dia (gasto diário) — por_dia_mes</div>${barrasChart(fin.por_dia_mes || [], 328, 84)}</div></div>
          <div class="r"><span class="rn">${cats.length + 4}</span><span class="c c1 lbl">Fatura</span>${dataBarCell(fin.fatura_atual || 0, Math.max(fin.fatura_atual || 0, fin.saldo_conta || 0, 1), fmt0(fin.fatura_atual || 0))}<span class="c c3">${fin.fatura_vencimento ? fin.fatura_vencimento.slice(8, 10) + "/" + fin.fatura_vencimento.slice(5, 7) : ""}</span></div>
          <div class="r"><span class="rn">${cats.length + 5}</span><span class="c c1 lbl">Conta</span>${dataBarCell(fin.saldo_conta || 0, Math.max(fin.fatura_atual || 0, fin.saldo_conta || 0, 1), fmt0(fin.saldo_conta || 0))}<span class="c c3"></span></div>
          <div class="r"><span class="rn">${cats.length + 6}</span><span class="c c1" style="font-weight:600">Data</span><span class="c c2" style="font-weight:600">Descrição</span><span class="c c3" style="font-weight:600">Valor</span></div>
          <div id="listaDias">${dias.slice(0, 6).map((d, i) => li(d, cats.length + 7 + i)).join("")}</div>
          ${dias.length > 6 ? `<button class="mais" id="btnMais">+ ${dias.length - 6} linhas ocultas · toque para expandir</button>` : ""}
        </div>
        <div class="toggle" id="btnAssin"><span>Assinaturas (${(fin.assinaturas || []).length})</span>${ICONS.baixo}</div>
        <div class="sub" id="assinList">${(fin.assinaturas || []).map((a, i) => `<div class="r"><span class="rn">A${i + 1}</span><span class="c c1">${a.nome}</span><span class="c c2 mono">${fmt(a.valor)}</span><span class="c c3"></span></div>`).join("")}</div>
        <div class="toggle" id="btnExtrato"><span>Extrato completo</span>${ICONS.baixo}</div>
        <div class="sub" id="extratoList">${dias.map((d, i) => li(d, "E" + i)).join("")}</div>
        <div style="height:40px"></div>
        ${tabs("financas")}
      `;
      function li(d, rowN) {
        return `<div class="r tap" data-ref="B${rowN}" data-txt="${d.data.slice(8, 10)}/${d.data.slice(5, 7)} · ${d.descricao} (${d.categoria}): ${fmt(Math.abs(d.valor))}"><span class="rn">${rowN}</span><span class="c c1">${d.data.slice(8, 10)}/${d.data.slice(5, 7)} · ${d.descricao}</span><span class="c c2 mono">${fmt(Math.abs(d.valor))}</span><span class="c c3"></span></div>`;
      }
      const btnMais = root.getElementById("btnMais");
      if (btnMais) btnMais.addEventListener("click", () => { root.getElementById("listaDias").innerHTML = dias.map((d, i) => li(d, cats.length + 7 + i)).join(""); btnMais.remove(); app.querySelectorAll("[data-ref]").forEach(el => el.onclick || el.addEventListener("click", () => selecionar(el.dataset.ref, el.dataset.txt, el.querySelector(".c2")))); });
      root.getElementById("btnAssin").addEventListener("click", function () { this.classList.toggle("open"); root.getElementById("assinList").classList.toggle("open"); });
      root.getElementById("btnExtrato").addEventListener("click", function () { this.classList.toggle("open"); root.getElementById("extratoList").classList.toggle("open"); });
      app.querySelectorAll("[data-ref]").forEach(el => el.addEventListener("click", () => selecionar(el.dataset.ref, el.dataset.txt, el.querySelector(".c2"))));
    }

    function telaVida() {
      const secs = D.vida_secoes || [];
      app.innerHTML = `
        ${toolbar("B2")}
        <div class="hd"><span></span><span>A</span><span>B</span><span>C</span></div>
        <div class="rows" id="rows">
          <div class="r"><span class="rn">1</span><span class="c c1" style="font-weight:600">Seção</span><span class="c c2" style="font-weight:600;justify-content:flex-start">Resumo</span><span class="c c3"></span></div>
          ${secs.map((s, i) => `<div class="r tap" data-id="${s.id}" data-ref="B${i + 2}"><span class="rn">${i + 2}</span><span class="c c1">${s.nome}</span><span class="c c2" style="justify-content:flex-start;font-weight:400;color:#5c6470">${s.resumo}</span><span class="c c3"></span></div>`).join("")}
        </div>
        <div class="painel" id="painel"></div>
        <div style="height:40px"></div>
        ${tabs("vida")}
      `;
      function seed(str) { let h = 0; for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0; return h; }
      function abrir(id, ref, rowEl) {
        const s = secs.find(x => x.id === id);
        selecionar(ref, `${s.nome}: ${s.resumo}`, rowEl.querySelector(".c2"));
        const sd = seed(s.id);
        const vals = Array.from({ length: 7 }, (_, i) => 15 + ((sd >> (i * 3)) % 85));
        root.getElementById("painel").innerHTML = `
          <h3>${s.nome}</h3><p>${s.resumo}</p>
          <p>Última atualização registrada nesta seção.</p>
          ${D.viagem && /viage/i.test(s.nome) ? `<p>Próxima viagem: <b>${D.viagem.origem} → ${D.viagem.destino}</b> em ${D.viagem.dias_faltando} dias (${D.viagem.data}).</p>` : ""}
          <div class="cap">Progresso da semana (exemplo)</div>
          ${barraExemplo(vals, 328, 54)}
        `;
      }
      app.querySelectorAll("[data-id]").forEach(el => el.addEventListener("click", () => abrir(el.dataset.id, el.dataset.ref, el)));
      if (secs[0]) abrir(secs[0].id, "B2", app.querySelector("[data-id]"));
      ligarTabs();
    }
    if (ctx.tela === "hoje") telaHoje();
    else if (ctx.tela === "financas") telaFinancas();
    else telaVida();
    if (ctx.tela !== "vida") ligarTabs();

    return () => { timers.forEach(clearInterval); cleanups.forEach(fn => fn()); };
  }
};
