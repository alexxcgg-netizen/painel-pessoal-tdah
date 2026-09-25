(window.DIRECOES = window.DIRECOES || {})[15] = {
  nome: "Busca",
  ideia: "Tudo começa por um campo de comando gigante; resultados agrupados expandem inline ao toque.",
  acento: "#0A84FF",
  fontes: ["Inter:wght@400;500;600;700", "JetBrains+Mono:wght@400;500;600"],
  render(root, D, ctx) {
    const AC = "#0A84FF";
    const fmt = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);
    const fin = D.financas || {};
    const timers = [], cleanups = [];

    function seedRand(str) {
      let h = 0;
      for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0;
      return () => { h = (h * 1664525 + 1013904223) >>> 0; return (h >>> 8) / 16777216; };
    }

    const ICONS = {
      busca: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>',
      mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/><path d="M8 21h8"/></svg>',
      alerta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 3l10 18H2L12 3z"/><path d="M12 10v4M12 17h.01"/></svg>',
      chuva: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M7 15a4 4 0 0 1 .8-7.94A5 5 0 0 1 17.6 9.1 3.5 3.5 0 0 1 17 16H7z"/><path d="M8 19l-1 2M12 19l-1 2M16 19l-1 2"/></svg>',
      chevron: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M9 6l6 6-6 6"/></svg>',
      chart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 20V10M9 20V4M15 20v-7M21 20V8"/></svg>',
      alvo: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3.5"/></svg>',
      cartao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/></svg>',
      carteira: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 7a2 2 0 0 1 2-2h13a1 1 0 0 1 1 1v3M3 7v11a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-6a1 1 0 0 0-1-1h-5a2 2 0 0 0 0 4h6"/></svg>',
      repetir: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 12a9 9 0 0 1 15-6.7L21 8M21 4v4h-4M21 12a9 9 0 0 1-15 6.7L3 16M3 20v-4h4"/></svg>',
      recibo: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3z"/><path d="M9 8h6M9 12h6"/></svg>',
      seta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
      hoje: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
      vida: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>',
      voltar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M15 6l-6 6 6 6"/></svg>'
    };

    root.innerHTML = `
    <style>
      :host,*{box-sizing:border-box}
      .app{font-family:Inter,system-ui,sans-serif;color:#eaecef;background:#0a0b0d;min-height:100%;position:relative;padding-bottom:66px}
      .mono{font-family:'JetBrains Mono',monospace}
      .searchwrap{padding:14px 14px 8px}
      .searchbar{display:flex;align-items:center;gap:10px;border:1px solid #24262b;background:#141519;border-radius:14px;padding:0 14px;min-height:52px}
      .searchbar svg{width:19px;height:19px;color:#6b7078;flex-shrink:0}
      .searchbar .txt{flex:1;font-size:15px;color:#eaecef}
      .searchbar .txt .cursor{display:inline-block;width:2px;height:16px;background:${AC};vertical-align:-3px;margin-left:1px}
      .anim .cursor{animation:blink 1s step-end infinite}
      @keyframes blink{50%{opacity:0}}
      .mic{width:34px;height:34px;border-radius:50%;background:#1c1e24;color:${AC};display:flex;align-items:center;justify-content:center;flex-shrink:0}
      .mic svg{width:16px;height:16px}
      .metarow{display:flex;justify-content:space-between;align-items:baseline;padding:10px 4px 0;font-size:11.5px;color:#8b909a;gap:8px}
      .metarow .hh{color:#c7cad0;font-weight:600;flex-shrink:0}
      .metarow2{padding:3px 4px 4px;font-size:11.5px;color:#8b909a}
      .metarow2 svg{width:13px;height:13px;vertical-align:-2px;margin-right:3px;color:${AC}}
      .grupo{padding:10px 14px 4px}
      .gruponome{font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:#6b7078;font-weight:600;padding:6px 2px}
      .painel{border:1px solid #1c1e23;border-radius:12px;overflow:hidden;background:#111318}
      .row{display:flex;align-items:center;gap:11px;min-height:52px;padding:0 12px;background:transparent;border:none;width:100%;text-align:left;color:inherit;font-family:inherit;border-bottom:1px solid #1a1c21}
      .painel .row:last-child{border-bottom:none}
      .row .ico{width:30px;height:30px;border-radius:8px;background:#1a1c22;display:flex;align-items:center;justify-content:center;flex-shrink:0;color:${AC}}
      .row .ico svg{width:15px;height:15px}
      .row.critico .ico{background:rgba(224,90,84,.14);color:#e05a54}
      .row .txt2{flex:1;min-width:0;display:flex;flex-direction:column;gap:1px}
      .row .t1{font-size:13.5px;color:#eef0f3}
      .row .t2{font-size:11.5px;color:#8b909a;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-top:1px}
      .row .meta{font-size:12.5px;color:#c7cad0;font-variant-numeric:tabular-nums;flex-shrink:0}
      .row .chev{width:13px;height:13px;color:#4a4e57;flex-shrink:0;transition:transform .15s;display:inline-flex}
      .row .chev svg{width:100%;height:100%;display:block}
      .row[aria-expanded="true"] .chev{transform:rotate(90deg)}
      .detalhe{display:none;padding:14px 14px 16px;border-top:1px solid #1a1c21}
      .detalhe.open{display:block}
      .valor{font-size:24px;font-weight:700;font-variant-numeric:tabular-nums;color:#fafbfc;margin-bottom:8px}
      .chart-linha{width:100%;display:block}
      .chart-linha .area{fill:${AC};opacity:.15}
      .chart-linha .linha{fill:none;stroke:${AC};stroke-width:2}
      .chart-linha .ponto{fill:${AC}}
      .chart-linha .grid{stroke:#20232a}
      .chart-linha .ref{stroke:#4a4e57;stroke-dasharray:3 3}
      .chart-linha text{font-family:Inter;font-size:8.5px;fill:#6b7078}
      .chart-linha text.reflbl{fill:#9aa0aa}
      .mini-row{display:flex;gap:8px;margin-top:12px}
      .mini{flex:1;text-align:center;border:1px solid #1c1e23;border-radius:9px;padding:8px 4px}
      .mini .l{display:block;font-size:9.5px;color:#8b909a;letter-spacing:.05em;text-transform:uppercase}
      .mini .v{display:block;margin-top:3px;font-size:13px;font-variant-numeric:tabular-nums;color:#eaecef}
      .pendlist{margin-top:4px}
      .pend{display:flex;justify-content:space-between;padding:7px 0;font-size:12.5px;border-bottom:1px solid #1a1c21;color:#c7cad0}
      .catlist{display:flex;flex-direction:column;gap:9px}
      .catrow{display:grid;grid-template-columns:98px 1fr auto;gap:8px;align-items:center}
      .catnome{font-size:11.5px;color:#c7cad0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      .catbarwrap{height:9px;border-radius:5px;background:#1a1c21;overflow:hidden}
      .catbar{height:100%;border-radius:5px}
      .catval{font-size:11.5px;font-variant-numeric:tabular-nums;color:#eaecef;min-width:64px;text-align:right}
      .fvcbars{display:flex;flex-direction:column;gap:10px}
      .fvcrow .lbl{display:flex;justify-content:space-between;font-size:11.5px;color:#c7cad0;margin-bottom:5px}
      .fvcrow .lbl b{color:#eaecef;font-variant-numeric:tabular-nums}
      .fvctrack{height:12px;border-radius:6px;background:#1a1c21;overflow:hidden}
      .fvcfill{height:100%;border-radius:6px;background:${AC}}
      .fvcfill.dim{background:#4a4e57}
      .li{display:flex;justify-content:space-between;gap:8px;padding:7px 0;border-bottom:1px solid #1a1c21;font-size:12px}
      .li .d{color:#6b7078;width:38px;flex-shrink:0;font-variant-numeric:tabular-nums}
      .li .n{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#c7cad0}
      .li .v{font-variant-numeric:tabular-nums;color:#eaecef}
      .mais{width:100%;min-height:44px;border:1px dashed #2a2d33;border-radius:9px;color:#9aa0aa;font-size:12px;background:transparent;margin-top:8px;font-family:inherit}
      .assinrow{display:flex;justify-content:space-between;padding:7px 0;font-size:12px;color:#c7cad0;border-bottom:1px solid #1a1c21}
      .shortcut{font-size:10px;color:#6b7078;border:1px solid #262930;border-radius:5px;padding:2px 6px;flex-shrink:0}
      .minichart{width:100%;display:block;margin-top:8px}
      .exemplo{font-size:10px;color:#6b7078;margin-top:5px;font-style:italic}
      .backrow{display:flex;align-items:center;gap:8px;min-height:44px;padding:8px 14px 0;color:#c7cad0;font-size:13px}
      .backrow svg{width:15px;height:15px}
      .navbar{position:absolute;left:0;right:0;bottom:0;display:flex;border-top:1px solid #1a1c21;background:#0a0b0d}
      .navbtn{flex:1;min-height:54px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;background:transparent;border:none;color:#6b7078;font-family:inherit}
      .navbtn svg{width:18px;height:18px}
      .navbtn.on{color:${AC}}
      .navbtn span{font-size:9.5px;letter-spacing:.03em}
    </style>
    <div class="app ${ctx.reduzido ? "" : "anim"}" id="app"></div>
    `;
    const app = root.getElementById("app");

    function chartLinha(dias, refValor, w, h) {
      w = w || 300; h = h || 100;
      const padB = 16;
      const vals = dias.map(d => d.acumulado);
      const maxVal = Math.max.apply(null, vals.concat([refValor || 0, 1]));
      const n = dias.length;
      const stepX = n > 1 ? w / (n - 1) : 0;
      const scaleY = v => (h - padB) - (v / maxVal) * (h - padB - 8);
      const pts = dias.map((d, i) => [i * stepX, scaleY(d.acumulado)]);
      const path = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
      const area = path + ` L${pts[n - 1][0].toFixed(1)},${(h - padB).toFixed(1)} L0,${(h - padB).toFixed(1)} Z`;
      const showRef = refValor && refValor <= maxVal;
      const refY = scaleY(refValor || 0);
      const last = pts[n - 1];
      let grid = "";
      for (let g = 1; g <= 3; g++) { const gy = (h - padB) - (g / 4) * (h - padB - 8); grid += `<line x1="0" y1="${gy.toFixed(1)}" x2="${w}" y2="${gy.toFixed(1)}" class="grid"/>`; }
      return `<svg viewBox="0 0 ${w} ${h}" class="chart-linha" role="img" aria-label="Gasto acumulado do mês, dia a dia">
        ${grid}
        ${showRef ? `<line x1="0" y1="${refY.toFixed(1)}" x2="${w}" y2="${refY.toFixed(1)}" class="ref"/><text x="${w}" y="${(refY - 4).toFixed(1)}" text-anchor="end" class="reflbl">mês anterior ${fmt(refValor)}</text>` : ""}
        <path d="${area}" class="area"/>
        <path d="${path}" class="linha"/>
        <circle cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="3" class="ponto"/>
        <text x="0" y="${h}">dia 1</text>
        <text x="${w}" y="${h}" text-anchor="end">dia ${n}</text>
      </svg>`;
    }

    function chartMini(seed, w, h) {
      w = w || 150; h = h || 40;
      const r = seedRand("vida-" + seed);
      const n = 7;
      const bw = w / n - 3;
      let out = "";
      for (let i = 0; i < n; i++) {
        const v = 0.25 + r() * 0.75;
        const bh = v * (h - 4);
        out += `<rect x="${(i * (w / n)).toFixed(1)}" y="${(h - bh).toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" rx="2" fill="${AC}" opacity="${(0.35 + v * 0.5).toFixed(2)}"/>`;
      }
      return `<svg viewBox="0 0 ${w} ${h}" class="minichart" role="img" aria-label="Progresso ilustrativo da semana">${out}</svg>`;
    }

    function catColor(i) {
      const shades = ["#8FC7FF", "#63AEFF", "#3C95FF", "#1F82FF", "#0A84FF", "#0868CC"];
      return shades[i % shades.length];
    }

    function catBars() {
      const cats = (fin.por_categoria || []).slice().sort((a, b) => b.valor - a.valor).slice(0, 6);
      const max = Math.max.apply(null, cats.map(c => c.valor).concat([1]));
      return `<div class="catlist">${cats.map((c, i) => `
        <div class="catrow">
          <span class="catnome">${c.categoria}</span>
          <div class="catbarwrap"><div class="catbar" style="width:${(c.valor / max * 100).toFixed(1)}%;background:${catColor(i)}"></div></div>
          <span class="catval">${fmt(c.valor)}</span>
        </div>`).join("")}</div>`;
    }

    function row({ icon, t1, t2, meta, critico, expandId, shortcut }) {
      return `<button class="row${critico ? " critico" : ""}" ${expandId ? `data-x="${expandId}" aria-expanded="false"` : ""}>
        <span class="ico">${icon}</span>
        <span class="txt2"><span class="t1">${t1}</span>${t2 ? `<span class="t2">${t2}</span>` : ""}</span>
        ${meta ? `<span class="meta">${meta}</span>` : ""}
        ${shortcut ? `<span class="shortcut">${shortcut}</span>` : ""}
        ${expandId ? `<span class="chev">${ICONS.chevron}</span>` : ""}
      </button>`;
    }

    function wireExpand(container) {
      container.querySelectorAll("[data-x]").forEach(b => {
        b.addEventListener("click", () => {
          const panel = container.querySelector('[data-panel="' + b.dataset.x + '"]');
          if (!panel) return;
          const open = panel.classList.toggle("open");
          b.setAttribute("aria-expanded", String(open));
        });
      });
    }

    function telaHoje() {
      const clima = D.hoje.clima || {};
      const dt = D.hoje.data.split("-").reverse().join("/");
      app.innerHTML = `
        <div class="searchwrap">
          <div class="searchbar">${ICONS.busca}<span class="txt">Buscar ou perguntar<span class="cursor"></span></span><span class="mic">${ICONS.mic}</span></div>
          <div class="metarow"><span>${dt} · ${D.hoje.cidade}</span><span class="hh mono" id="relogio">--:--</span></div>
          <div class="metarow2">${ICONS.chuva}${clima.temp}°C, ${clima.cond}</div>
        </div>
        <div class="grupo"><div class="gruponome">Agora</div><div class="painel" id="painelAgora"></div></div>
        <div class="grupo"><div class="gruponome">Atalhos</div><div class="painel" id="painelAtalhos">
          ${row({ icon: ICONS.chart, t1: "Abrir Finanças", t2: "resumo, categorias, extrato", shortcut: "→" })}
          ${row({ icon: ICONS.vida, t1: "Abrir Vida", t2: "18 seções", shortcut: "→" })}
        </div></div>
      `;
      const painel = root.getElementById("painelAgora");
      const rows = [];
      if (D.aviso_critico) rows.push(row({ icon: ICONS.alerta, t1: D.aviso_critico, t2: "Aviso crítico", critico: true }));
      const delta = fin.gasto_mes_anterior ? ((fin.gasto_mes - fin.gasto_mes_anterior) / fin.gasto_mes_anterior * 100) : 0;
      rows.push(row({ icon: ICONS.chart, t1: "Gasto do mês", t2: (delta >= 0 ? "▲" : "▼") + " " + Math.abs(delta).toFixed(0) + "% vs mês anterior", meta: fmt(fin.gasto_mes), expandId: "gasto" }));
      rows.push(row({ icon: ICONS.alvo, t1: "Em foco agora", t2: (D.tarefas && D.tarefas.em_foco) || "—", expandId: "foco" }));
      painel.innerHTML = rows.join("") + `
        <div class="detalhe" data-panel="gasto">
          <div class="valor" id="numGasto">R$ 0,00</div>
          ${chartLinha(fin.por_dia_mes || [], fin.gasto_mes_anterior)}
          <div class="mini-row">
            <div class="mini"><span class="l">Hoje</span><span class="v">${fmt(fin.gasto_hoje)}</span></div>
            <div class="mini"><span class="l">Fatura</span><span class="v">${fmt(fin.fatura_atual)}</span></div>
            <div class="mini"><span class="l">Conta</span><span class="v">${fmt(fin.saldo_conta)}</span></div>
          </div>
        </div>
        <div class="detalhe" data-panel="foco">
          <div class="pendlist">${((D.tarefas && D.tarefas.pendentes) || []).map(p => `<div class="pend"><span>${p.titulo}</span><span>${p.quando}</span></div>`).join("")}</div>
        </div>
      `;
      wireExpand(painel);
      root.getElementById("painelAtalhos").querySelectorAll(".row").forEach((b, i) => b.addEventListener("click", () => ctx.irPara(i === 0 ? "financas" : "vida")));

      const numEl = root.getElementById("numGasto");
      const target = fin.gasto_mes || 0;
      const dur = ctx.reduzido ? 0 : 700;
      const t0 = performance.now();
      function step(t) {
        const p = dur ? Math.min(1, (t - t0) / dur) : 1;
        numEl.textContent = fmt(target * (1 - Math.pow(1 - p, 3)));
        if (p < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);

      function tick() {
        const el = root.getElementById("relogio");
        if (!el) return;
        el.textContent = new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
      }
      tick();
      if (!ctx.reduzido) timers.push(setInterval(tick, 15000));
    }

    function telaFinancas() {
      const dias = fin.ultimos_15_dias || [];
      const f = fin.fatura_atual || 0, c = fin.saldo_conta || 0;
      const maxfc = Math.max(f, c, 1);
      function li(d) {
        const dd = d.data.slice(8, 10) + "/" + d.data.slice(5, 7);
        return `<div class="li"><span class="d mono">${dd}</span><span class="n">${d.descricao}</span><span class="v mono">${fmt(Math.abs(d.valor))}</span></div>`;
      }
      app.innerHTML = `
        <div class="searchwrap"><div class="searchbar">${ICONS.busca}<span class="txt">gastos por categoria<span class="cursor"></span></span></div></div>
        <div class="grupo"><div class="gruponome">Finanças</div><div class="painel" id="painel"></div></div>
      `;
      const painel = root.getElementById("painel");
      const orcTxt = fin.orcamento_mes ? `, de orçamento de ${fmt(fin.orcamento_mes)}` : "";
      painel.innerHTML = [
        row({ icon: ICONS.chart, t1: "Resumo do mês", t2: fmt(fin.gasto_mes) + orcTxt, expandId: "resumo" }),
        row({ icon: ICONS.chart, t1: "Gastos por categoria", t2: "top " + Math.min(6, (fin.por_categoria || []).length), expandId: "cats" }),
        row({ icon: ICONS.chart, t1: "Evolução do mês", t2: "por dia", expandId: "evol" }),
        row({ icon: ICONS.cartao, t1: "Fatura × Conta", t2: fmt(f) + " · " + fmt(c), expandId: "fvc" }),
        row({ icon: ICONS.recibo, t1: "Últimos 15 dias", t2: dias.length + " lançamentos", expandId: "dias" }),
        row({ icon: ICONS.repetir, t1: "Assinaturas", t2: (fin.assinaturas || []).length + " ativas", expandId: "assin" }),
        row({ icon: ICONS.carteira, t1: "Extrato completo", t2: "todas as transações", expandId: "extrato" })
      ].join("") + `
        <div class="detalhe" data-panel="resumo">
          <p style="font-size:13px;color:#c7cad0;line-height:1.5;margin:0">Você gastou ${fmt(fin.gasto_mes)} até agora${orcTxt}, contra ${fmt(fin.gasto_mes_anterior)} no mês passado.</p>
        </div>
        <div class="detalhe open" data-panel="cats">${catBars()}</div>
        <div class="detalhe" data-panel="evol">${chartLinha(fin.por_dia_mes || [], fin.gasto_mes_anterior)}</div>
        <div class="detalhe" data-panel="fvc">
          <div class="fvcbars">
            <div class="fvcrow"><div class="lbl"><span>Fatura atual</span><b>${fmt(f)}</b></div><div class="fvctrack"><div class="fvcfill" style="width:${(f / maxfc * 100).toFixed(1)}%"></div></div></div>
            <div class="fvcrow"><div class="lbl"><span>Saldo em conta</span><b>${fmt(c)}</b></div><div class="fvctrack"><div class="fvcfill dim" style="width:${(c / maxfc * 100).toFixed(1)}%"></div></div></div>
          </div>
        </div>
        <div class="detalhe" data-panel="dias">
          <div id="lista15">${dias.slice(0, 6).map(li).join("")}</div>
          ${dias.length > 6 ? `<button class="mais" id="btnMais">carregar mais (${dias.length - 6})</button>` : ""}
        </div>
        <div class="detalhe" data-panel="assin">${(fin.assinaturas || []).map(a => `<div class="assinrow"><span>${a.nome}</span><span class="mono">${fmt(a.valor)}</span></div>`).join("")}</div>
        <div class="detalhe" data-panel="extrato">${dias.map(li).join("")}</div>
      `;
      painel.querySelector('[data-x="cats"]').setAttribute("aria-expanded", "true");
      wireExpand(painel);
      const btnMais = root.getElementById("btnMais");
      if (btnMais) btnMais.addEventListener("click", () => { root.getElementById("lista15").innerHTML = dias.map(li).join(""); btnMais.remove(); });
    }

    function telaVida() {
      const secs = D.vida_secoes || [];
      app.innerHTML = `
        <div class="searchwrap"><div class="searchbar">${ICONS.busca}<span class="txt">seções da vida<span class="cursor"></span></span></div></div>
        <div class="grupo"><div class="gruponome">Comandos · Vida</div><div class="painel" id="painel"></div></div>
      `;
      const painel = root.getElementById("painel");
      const ICOSET = [ICONS.vida, ICONS.alvo, ICONS.chart, ICONS.repetir, ICONS.recibo, ICONS.carteira];
      painel.innerHTML = secs.map((s, i) => row({ icon: ICOSET[i % ICOSET.length], t1: s.nome, t2: s.resumo, expandId: "v-" + s.id })).join("") +
        secs.map(s => `<div class="detalhe" data-panel="v-${s.id}">
            <p style="font-size:12.5px;color:#c7cad0;line-height:1.5;margin:0 0 4px">${s.resumo}. Última atualização registrada nesta seção.</p>
            ${D.viagem && s.id === "viagens" ? `<p style="font-size:12.5px;color:#c7cad0;line-height:1.5;margin:0 0 4px">Próxima viagem: <b>${D.viagem.origem} → ${D.viagem.destino}</b> em ${D.viagem.dias_faltando} dias (${D.viagem.data}).</p>` : ""}
            ${chartMini(s.id)}
            <div class="exemplo">Progresso ilustrativo da semana (exemplo)</div>
          </div>`).join("");
      wireExpand(painel);
    }

    function nav() {
      const tabs = [["hoje", ICONS.hoje, "Hoje"], ["financas", ICONS.chart, "Finanças"], ["vida", ICONS.vida, "Vida"]];
      const bar = document.createElement("div");
      bar.className = "navbar";
      bar.innerHTML = tabs.map(([t, ic, lb]) => `<button class="navbtn ${ctx.tela === t ? "on" : ""}" data-t="${t}">${ic}<span>${lb}</span></button>`).join("");
      app.appendChild(bar);
      bar.querySelectorAll("button").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.t)));
      cleanups.push(() => bar.remove());
    }

    if (ctx.tela === "financas") telaFinancas();
    else if (ctx.tela === "vida") telaVida();
    else telaHoje();
    nav();

    return () => {
      timers.forEach(clearInterval);
      cleanups.forEach(fn => fn());
    };
  }
};
