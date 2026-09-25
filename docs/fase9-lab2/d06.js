(window.DIRECOES = window.DIRECOES || {})[6] = {
  nome: "Produtividade",
  ideia: "Denso e preciso como um app de tarefas de dev: linhas, anéis de status, chips de atalho.",
  acento: "#5E6AD2",
  fontes: ["Inter:wght@400;500;600;700", "JetBrains+Mono:wght@400;500;600"],
  render(root, D, ctx) {
    const AC = "#5E6AD2";
    const fmt = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);
    const fmtPct = v => (v > 0 ? "+" : "") + v.toFixed(0) + "%";
    const fin = D.financas || {};
    const timers = [], cleanups = [];

    const ICONS = {
      mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/><path d="M8 21h8"/></svg>',
      financas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 19V10M10 19V5M16 19v-7M22 19H2"/></svg>',
      vida: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>',
      hoje: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
      seta: '<svg class="ico-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M9 6l6 6-6 6"/></svg>',
      baixo: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 9l6 6 6-6"/></svg>',
      cima: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 15l6-6 6 6"/></svg>',
      alerta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 3l10 18H2L12 3z"/><path d="M12 10v4M12 17h.01"/></svg>',
      chuva: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M7 15a4 4 0 0 1 .8-7.94A5 5 0 0 1 17.6 9.1 3.5 3.5 0 0 1 17 16H7z"/><path d="M8 19l-1 2M12 19l-1 2M16 19l-1 2"/></svg>',
      enviar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 12l16-8-6 16-3-7-7-1z"/></svg>',
      fechar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 6l12 12M18 6L6 18"/></svg>',
      tarefas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 6h16M4 12h16M4 18h10"/></svg>',
      aviacao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 2v20M4 9l16 4M6 20l6-3 6 3"/></svg>',
      pasta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 6h6l2 2h10v11H3z"/></svg>',
      tag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M20 12l-8 8-9-9V3h8z"/><circle cx="7.5" cy="7.5" r="1.2" fill="currentColor" stroke="none"/></svg>',
      calend: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="5" width="18" height="16" rx="1"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>',
      pessoa: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="8" r="3.4"/><path d="M5 20c1.2-3.8 4-5.6 7-5.6s5.8 1.8 7 5.6"/></svg>',
      mala: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="8" width="18" height="12" rx="1.5"/><path d="M9 8V5.5A1.5 1.5 0 0 1 10.5 4h3A1.5 1.5 0 0 1 15 5.5V8"/></svg>',
      estrela: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 3l2.6 5.9 6.4.6-4.8 4.3 1.4 6.3L12 16.9l-5.6 3.2 1.4-6.3-4.8-4.3 6.4-.6z"/></svg>'
    };
    const iconCiclo = [ICONS.tag, ICONS.pasta, ICONS.calend, ICONS.pessoa, ICONS.mala, ICONS.estrela];

    function chartLinha(w, h, dias, refVal, refLabel, color) {
      const vals = dias.map(d => d.acumulado);
      const maxV = Math.max(...vals, refVal || 0, 1);
      const padT = 14, padB = 4, baseline = h - padB, innerH = h - padT - padB, n = dias.length;
      const X = i => n <= 1 ? 0 : (i / (n - 1)) * w;
      const Y = v => padT + innerH - (v / maxV) * innerH;
      const pts = dias.map((d, i) => `${X(i).toFixed(1)},${Y(d.acumulado).toFixed(1)}`);
      const path = "M" + pts.join(" L");
      const area = `M0,${baseline} L${pts.join(" L")} L${w},${baseline} Z`;
      const last = dias[dias.length - 1];
      const refY = refVal ? Y(refVal).toFixed(1) : null;
      return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="none">
        <path d="${area}" fill="${color}" opacity=".14"/>
        ${refVal ? `<line x1="0" y1="${refY}" x2="${w}" y2="${refY}" stroke="#4c4c54" stroke-width="1" stroke-dasharray="3 3"/><text x="${w}" y="${Number(refY) - 4}" text-anchor="end" class="ch-lbl">${refLabel}</text>` : ""}
        <path d="${path}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
        <circle cx="${X(dias.length - 1)}" cy="${Y(last.acumulado)}" r="3" fill="${color}"/>
        <text x="0" y="${padT - 4}" class="ch-lbl">${fmt(maxV)}</text>
        <text x="0" y="${h - 1}" class="ch-lbl-fraco">dia 1</text>
        <text x="${w}" y="${h - 1}" text-anchor="end" class="ch-lbl-fraco">dia ${last.dia}</text>
      </svg>`;
    }
    function chartComparativo(fatura, conta) {
      const maxV = Math.max(fatura, conta, 1);
      const wFat = Math.max(2, (fatura / maxV) * 100), wCon = Math.max(2, (conta / maxV) * 100);
      return `<div class="comp-chart">
        <div class="comp-row"><span class="comp-lbl">Fatura</span><div class="comp-bar-bg"><div class="comp-bar" style="width:${wFat}%"></div></div><span class="comp-val num">${fmt(fatura)}</span></div>
        <div class="comp-row"><span class="comp-lbl">Conta</span><div class="comp-bar-bg"><div class="comp-bar alt" style="width:${wCon}%"></div></div><span class="comp-val num">${fmt(conta)}</span></div>
      </div>`;
    }
    function seqExemplo(id) {
      let h = 0; for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
      const arr = []; for (let i = 0; i < 7; i++) { h = (h * 1103515245 + 12345) >>> 0; arr.push(18 + (h % 82)); }
      return arr;
    }
    function chartSeq(vals) {
      const maxV = Math.max(...vals, 1);
      return `<div class="seq-chart"><div class="seq-lbl">Sequência (exemplo)</div><div class="seq-bars">${vals.map(v => `<i style="height:${Math.max(10, (v / maxV) * 100)}%"></i>`).join("")}</div></div>`;
    }
    function ring(pct, sz) {
      sz = sz || 15;
      const r = sz / 2 - 1.6, circ = 2 * Math.PI * r;
      const off = circ * (1 - Math.max(0, Math.min(1, pct)));
      return `<svg width="${sz}" height="${sz}" viewBox="0 0 ${sz} ${sz}" class="ring">
        <circle cx="${sz/2}" cy="${sz/2}" r="${r}" fill="none" stroke="#2a2a30" stroke-width="2"/>
        <circle cx="${sz/2}" cy="${sz/2}" r="${r}" fill="none" stroke="${AC}" stroke-width="2" stroke-dasharray="${circ}" stroke-dashoffset="${off}" stroke-linecap="round" transform="rotate(-90 ${sz/2} ${sz/2})"/>
      </svg>`;
    }

    root.innerHTML = `
    <style>
      :host, * { box-sizing: border-box; }
      .wrap { font-family: 'Inter', sans-serif; color: #e9e9ea; padding: 14px 14px 88px; min-height: 100%; position: relative; -webkit-font-smoothing: antialiased; }
      .mono { font-family: 'JetBrains Mono', monospace; }
      .num { font-variant-numeric: tabular-nums; font-family: 'JetBrains Mono', monospace; }
      .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
      .header .tit { font-size: 15px; font-weight: 600; color: #f2f2f3; }
      .header .sub { font-size: 11.5px; color: #6f6f76; margin-top: 1px; }
      .hdr-right { display: flex; align-items: center; gap: 8px; }
      .clima-chip { display: flex; align-items: center; gap: 5px; font-size: 12px; color: #a4a4ab; border: 1px solid #1e1e22; border-radius: 7px; padding: 6px 9px; min-height: 44px; }
      .clima-chip svg { width: 14px; height: 14px; color: ${AC}; }
      .mic-btn { width: 44px; height: 44px; border-radius: 8px; border: 1px solid #1e1e22; background: #0a0a0c; color: ${AC}; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
      .mic-btn svg { width: 18px; height: 18px; }

      .aviso { display: flex; gap: 9px; align-items: center; border: 1px solid #3a1f24; background: #150c0e; color: #e7a7ae; font-size: 12px; padding: 10px 12px; border-radius: 8px; margin-bottom: 14px; }
      .aviso svg { width: 15px; height: 15px; flex-shrink: 0; color: #e2707c; }

      .card { border: 1px solid #1c1c20; border-radius: 10px; padding: 13px 14px; margin-bottom: 10px; background: #060607; }
      .lbl { font-size: 10.5px; color: #75757d; letter-spacing: .04em; text-transform: uppercase; font-weight: 600; }
      .cnt { font-size: 11px; color: #6a6a71; font-weight: 500; }

      .gasto-top { display: flex; justify-content: space-between; align-items: flex-start; }
      .gasto-val { font-size: 27px; font-weight: 700; color: #f5f5f6; margin-top: 3px; }
      .delta { display: flex; align-items: center; gap: 3px; font-size: 11.5px; color: #9797a0; border: 1px solid #232328; border-radius: 6px; padding: 4px 7px; margin-top: 3px; }
      .delta svg { width: 11px; height: 11px; color: ${AC}; }
      .ch-lbl { font-size: 8px; fill: #9a9aa1; font-family: 'JetBrains Mono', monospace; }
      .ch-lbl-fraco { font-size: 7.5px; fill: #55555c; font-family: 'JetBrains Mono', monospace; }
      .chart-box { margin-top: 12px; }
      .comp-chart { display: flex; flex-direction: column; gap: 9px; margin-top: 2px; }
      .comp-row { display: flex; align-items: center; gap: 8px; }
      .comp-lbl { font-size: 10px; color: #75757d; width: 38px; flex-shrink: 0; }
      .comp-bar-bg { flex: 1; height: 10px; border-radius: 3px; background: #17171b; overflow: hidden; }
      .comp-bar { height: 100%; background: ${AC}; border-radius: 3px; }
      .comp-bar.alt { background: #55555f; }
      .comp-val { font-size: 11px; color: #eee; width: 76px; text-align: right; flex-shrink: 0; }
      .seq-chart { margin-top: 10px; }
      .seq-lbl { font-size: 9.5px; color: #55555c; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 5px; }
      .seq-bars { display: flex; gap: 3px; align-items: flex-end; height: 26px; }
      .seq-bars i { flex: 1; background: ${AC}; opacity: .55; border-radius: 1px; display: block; }

      .stat3 { display: flex; border: 1px solid #1c1c20; border-radius: 10px; margin-bottom: 10px; overflow: hidden; }
      .stat3 .c { flex: 1; padding: 11px 10px; }
      .stat3 .c + .c { border-left: 1px solid #1c1c20; }
      .stat3 .top { display: flex; align-items: center; gap: 5px; margin-bottom: 6px; }
      .stat3 .v { font-size: 14.5px; font-weight: 600; color: #eee; }
      .stat3 .s { font-size: 10px; color: #6f6f76; margin-top: 2px; }

      .row-issue { display: flex; align-items: center; gap: 10px; border: 1px solid #1c1c20; border-radius: 10px; padding: 12px 13px; margin-bottom: 14px; min-height: 44px; }
      .row-issue .t { flex: 1; font-size: 13px; color: #e4e4e6; }
      svg.ico-chevron { width: 13px; height: 13px; color: #55555c; flex-shrink: 0; display: inline-block; vertical-align: middle; }

      .chips { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 16px; }
      .chip { display: flex; align-items: center; gap: 9px; border: 1px solid #1c1c20; border-radius: 9px; padding: 8px 10px; background: #060607; min-height: 46px; }
      .chip .key { width: 24px; height: 24px; border: 1px solid #2b2b32; border-bottom-width: 2px; border-radius: 5px; background: #131316; display: flex; align-items: center; justify-content: center; font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 700; color: ${AC}; flex-shrink: 0; }
      .chip .lb { font-size: 12px; color: #c7c7cb; }

      .chatbar { display: flex; align-items: center; gap: 8px; border: 1px solid #1e1e22; border-radius: 10px; padding: 5px 6px 5px 13px; background: #060607; }
      .chatbar input { flex: 1; background: transparent; border: none; outline: none; color: #ddd; font-family: 'Inter', sans-serif; font-size: 13px; min-height: 34px; }
      .chatbar input::placeholder { color: #55555c; }
      .chatbar button { width: 34px; height: 34px; border-radius: 7px; border: 1px solid #24242a; background: #101013; color: ${AC}; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
      .chatbar button svg { width: 14px; height: 14px; }

      /* finanças */
      .filtro { display: flex; border: 1px solid #1c1c20; border-radius: 8px; overflow: hidden; }
      .filtro button { padding: 7px 11px; font-size: 11px; color: #82828a; background: transparent; border: none; min-height: 30px; }
      .filtro button + button { border-left: 1px solid #1c1c20; }
      .filtro button.on { background: rgba(94,106,210,.16); color: #b7bdf2; }

      .resumo2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px; }
      .resumo2 .box { border: 1px solid #1c1c20; border-radius: 10px; padding: 12px 13px; }
      .resumo2 .v { font-size: 17px; font-weight: 700; color: #eee; }
      .resumo2 .s { font-size: 10.5px; color: #75757d; margin-top: 3px; }

      .cat-row { padding: 9px 0; }
      .cat-top { display: flex; justify-content: space-between; font-size: 12.5px; margin-bottom: 6px; }
      .cat-top .n { color: #d4d4d7; }
      .cat-top .v { color: #eee; }
      .cat-bar-bg { height: 5px; border-radius: 3px; background: #17171b; overflow: hidden; }
      .cat-bar { height: 100%; background: ${AC}; border-radius: 3px; }
      .cat-total { display: flex; justify-content: space-between; align-items: baseline; padding: 4px 0 12px; border-bottom: 1px solid #1c1c20; margin-bottom: 6px; }
      .cat-total .n { font-size: 11px; color: #75757d; text-transform: uppercase; letter-spacing: .04em; font-weight: 600; }
      .cat-total .v { font-size: 18px; font-weight: 700; color: #f2f2f3; }

      .grp-lbl { font-size: 10.5px; color: #6a6a71; text-transform: uppercase; letter-spacing: .05em; font-weight: 600; margin: 14px 0 6px; display: flex; justify-content: space-between; }
      .li { display: flex; align-items: center; gap: 9px; padding: 9px 2px; border-bottom: 1px solid #151518; }
      .li .d { font-size: 10px; color: #6a6a71; width: 30px; flex-shrink: 0; }
      .li .n { flex: 1; font-size: 12.5px; color: #d1d1d5; }
      .li .cat { font-size: 10px; color: #6a6a71; }
      .li .v { font-size: 12.5px; color: #eee; }
      .mais { width: 100%; text-align: center; padding: 11px; margin-top: 8px; border: 1px solid #1c1c20; border-radius: 8px; color: #9797a0; font-size: 11.5px; background: transparent; min-height: 44px; }

      .toggle { width: 100%; display: flex; justify-content: space-between; align-items: center; padding: 12px 13px; border: 1px solid #1c1c20; border-radius: 10px; background: #060607; color: #c7c7cb; font-size: 12.5px; margin-bottom: 8px; min-height: 44px; }
      .toggle svg { width: 13px; height: 13px; color: #6a6a71; transition: transform .15s; }
      .toggle.open svg { transform: rotate(90deg); }
      .sub-list { display: none; padding: 2px 2px 8px; }
      .sub-list.open { display: block; }
      .sub-row { display: flex; justify-content: space-between; padding: 8px 2px; font-size: 12px; color: #b8b8bd; border-bottom: 1px solid #131316; }

      /* vida: sidebar de projetos */
      .proj-list { display: flex; flex-direction: column; margin-bottom: 6px; }
      .proj { display: flex; align-items: center; gap: 11px; padding: 11px 4px; border-bottom: 1px solid #151518; min-height: 44px; }
      .proj .ic { width: 26px; height: 26px; border-radius: 6px; background: #101013; border: 1px solid #1e1e22; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
      .proj .ic svg { width: 13px; height: 13px; color: ${AC}; }
      .proj .body { flex: 1; min-width: 0; }
      .proj .nm { font-size: 13px; color: #e4e4e6; }
      .proj .rs { font-size: 11px; color: #6f6f76; margin-top: 1px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .proj svg.ico-chevron { width: 12px; height: 12px; color: #4a4a50; flex-shrink: 0; transition: transform .15s; }
      .proj.open svg.ico-chevron { transform: rotate(90deg); }
      .proj-detail { display: none; padding: 2px 4px 14px 41px; font-size: 12px; color: #9c9ca3; line-height: 1.6; }
      .proj-detail.open { display: block; }
      .proj-detail b { color: ${AC}; }

      .navbar { display: flex; border-top: 1px solid #1c1c20; margin-top: 18px; padding-top: 2px; position: absolute; left: 14px; right: 14px; bottom: 0; }
      .navbtn { flex: 1; min-height: 52px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; background: transparent; border: none; color: #5c5c63; }
      .navbtn span { font-size: 10px; letter-spacing: .02em; }
      .navbtn.on { color: #f0f0f2; }
      .navbtn .dot { width: 6px; height: 6px; border-radius: 50%; background: #38383e; }
      .navbtn.on .dot { background: ${AC}; }
    </style>
    <div class="wrap" id="wrap"></div>
    `;
    const wrap = root.getElementById("wrap");

    function telaHoje() {
      const clima = D.hoje.clima || {};
      const dias = fin.por_dia_mes || [];
      const delta = fin.gasto_mes_anterior ? ((fin.gasto_mes - fin.gasto_mes_anterior) / fin.gasto_mes_anterior) * 100 : 0;
      wrap.innerHTML = `
        <div class="header">
          <div><div class="tit">Hoje</div><div class="sub">${D.hoje.data}</div></div>
          <div class="hdr-right">
            <div class="clima-chip">${ICONS.chuva}<span>${clima.temp}° · ${clima.chuva_prob}%</span></div>
            <button class="mic-btn" id="mic">${ICONS.mic}</button>
          </div>
        </div>
        ${D.aviso_critico ? `<div class="aviso">${ICONS.alerta}<span>${D.aviso_critico}</span></div>` : ""}
        <div class="card">
          <div class="gasto-top">
            <div><div class="lbl">Gasto do mês</div><div class="gasto-val num">${fmt(fin.gasto_mes)}</div></div>
            <div class="delta">${delta <= 0 ? ICONS.baixo : ICONS.cima}<span class="num">${fmtPct(delta)}</span></div>
          </div>
          <div class="chart-box">${chartLinha(300, 70, dias, fin.gasto_mes_anterior, "mês ant. " + fmt(fin.gasto_mes_anterior), AC)}</div>
        </div>
        <div class="stat3">
          <div class="c"><div class="top">${ring(fin.gasto_hoje > 0 ? 1 : 0)}<span class="lbl">Hoje</span></div><div class="v num">${fmt(fin.gasto_hoje)}</div></div>
          <div class="c"><div class="top">${ring(Math.min(1, fin.fatura_atual / (fin.gasto_mes_anterior || 1)))}<span class="lbl">Fatura</span></div><div class="v num">${fmt(fin.fatura_atual)}</div><div class="s">vence ${(fin.fatura_vencimento||"").slice(8,10)}/${(fin.fatura_vencimento||"").slice(5,7)}</div></div>
          <div class="c"><div class="top">${ring(1)}<span class="lbl">Conta</span></div><div class="v num">${fmt(fin.saldo_conta)}</div></div>
        </div>
        <div class="row-issue">${ring(0.5, 16)}<span class="t">${(D.tarefas && D.tarefas.em_foco) || "—"}</span>${ICONS.seta}</div>
        <div class="chips">
          <button class="chip" data-t="financas"><span class="key">F</span><span class="lb">Finanças</span></button>
          <button class="chip" data-t="vida"><span class="key">V</span><span class="lb">Vida</span></button>
          <button class="chip" data-t="vida"><span class="key">T</span><span class="lb">Tarefas</span></button>
          <button class="chip" data-t="vida"><span class="key">A</span><span class="lb">Aviação</span></button>
        </div>
        <div class="chatbar"><input placeholder="Perguntar algo…" />${ICONS.enviar ? `<button>${ICONS.enviar}</button>` : ""}</div>
      `;
      wrap.querySelectorAll(".chip").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.t)));
    }

    function telaFinancas() {
      const cats = (fin.por_categoria || []).slice().sort((a, b) => b.valor - a.valor);
      const totalCat = cats.reduce((s, c) => s + c.valor, 0) || 1;
      const maxV = Math.max(...cats.map(c => c.valor), 1);
      const delta = fin.gasto_mes_anterior ? ((fin.gasto_mes - fin.gasto_mes_anterior) / fin.gasto_mes_anterior) * 100 : 0;

      const hoje = new Date(D.hoje.data + "T00:00:00");
      const dias = (fin.ultimos_15_dias || []).map(d => {
        const dt = new Date(d.data + "T00:00:00");
        const diff = Math.round((hoje - dt) / 86400000);
        return Object.assign({ grupo: diff <= 7 ? "Esta semana" : "Este mês" }, d);
      });

      function li(d) {
        const dd = d.data.slice(8, 10) + "/" + d.data.slice(5, 7);
        return `<div class="li"><span class="d num">${dd}</span><span class="n">${d.descricao}<div class="cat">${d.categoria}</div></span><span class="v num">${fmt(Math.abs(d.valor))}</span></div>`;
      }
      function renderLista(showAll) {
        const visiveis = showAll ? dias : dias.slice(0, 6);
        let out = "", grpAtual = null;
        visiveis.forEach(d => {
          if (d.grupo !== grpAtual) { grpAtual = d.grupo; out += `<div class="grp-lbl"><span>${grpAtual}</span></div>`; }
          out += li(d);
        });
        return out;
      }
      const idLista = "listaDias";

      wrap.innerHTML = `
        <div class="header">
          <div><div class="tit">Finanças</div><div class="sub">${fin.mes}</div></div>
          <div class="filtro"><button class="on">Semana</button><button>Mês</button></div>
        </div>
        <div class="resumo2">
          <div class="box"><div class="v num">${fmt(fin.gasto_mes)}</div><div class="s">gasto este mês</div></div>
          <div class="box"><div class="v num" style="color:#a4a4ab">${fmt(fin.gasto_mes_anterior)}</div><div class="s">mês anterior · ${fmtPct(delta)}</div></div>
        </div>
        <div class="card">
          <div class="cat-total"><span class="n">Evolução do mês</span><span class="v num" style="font-size:13px;font-weight:600">${fmt(fin.gasto_mes)}</span></div>
          <div class="chart-box">${chartLinha(300, 66, fin.por_dia_mes || [], fin.gasto_mes_anterior, "mês ant. " + fmt(fin.gasto_mes_anterior), AC)}</div>
        </div>
        <div class="card">
          <div class="cat-total" style="border-bottom:none;margin-bottom:2px;padding-bottom:0"><span class="n">Fatura × Conta</span></div>
          ${chartComparativo(fin.fatura_atual || 0, fin.saldo_conta || 0)}
          <div class="s" style="margin-top:8px;color:#75757d;font-size:10.5px">Fatura vence ${(fin.fatura_vencimento||"").slice(8,10)}/${(fin.fatura_vencimento||"").slice(5,7)}</div>
        </div>
        <div class="card">
          <div class="cat-total"><span class="n">Por categoria</span><span class="v num">${fmt(totalCat)}</span></div>
          ${cats.map(c => `
            <div class="cat-row">
              <div class="cat-top"><span class="n">${c.categoria}</span><span class="v num">${fmt(c.valor)}</span></div>
              <div class="cat-bar-bg"><div class="cat-bar" style="width:${(c.valor / maxV) * 100}%"></div></div>
            </div>`).join("")}
        </div>
        <div class="grp-header" style="display:flex;justify-content:space-between;align-items:baseline;margin:16px 0 4px"><span class="lbl">Últimos dias</span><span class="cnt">${dias.length}</span></div>
        <div id="${idLista}">${renderLista(false)}</div>
        ${dias.length > 6 ? `<button class="mais" id="btnMais">Carregar mais (${dias.length - 6})</button>` : ""}
        <div style="margin-top:14px">
          <button class="toggle" id="btnAssin"><span>Assinaturas</span><span class="cnt">${(fin.assinaturas||[]).length} ${ICONS.seta}</span></button>
          <div class="sub-list" id="assinList">${(fin.assinaturas||[]).map(a => `<div class="sub-row"><span>${a.nome}</span><span class="num">${fmt(a.valor)}</span></div>`).join("")}</div>
          <button class="toggle" id="btnExtrato"><span>Extrato completo</span><span class="cnt">${dias.length} ${ICONS.seta}</span></button>
          <div class="sub-list" id="extratoList">${dias.map(li).join("")}</div>
        </div>
      `;
      const btnMais = root.getElementById("btnMais");
      if (btnMais) btnMais.addEventListener("click", () => { root.getElementById(idLista).innerHTML = renderLista(true); btnMais.remove(); });
      root.getElementById("btnAssin").addEventListener("click", function () { this.classList.toggle("open"); root.getElementById("assinList").classList.toggle("open"); });
      root.getElementById("btnExtrato").addEventListener("click", function () { this.classList.toggle("open"); root.getElementById("extratoList").classList.toggle("open"); });
    }

    function telaVida() {
      const secs = D.vida_secoes || [];
      wrap.innerHTML = `
        <div class="header">
          <div><div class="tit">Vida</div><div class="sub">projetos</div></div>
          <span class="cnt">${secs.length} ativos</span>
        </div>
        <div class="proj-list" id="projList">
          ${secs.map((s, i) => `
            <div>
              <div class="proj" data-id="${s.id}">
                <div class="ic">${iconCiclo[i % iconCiclo.length]}</div>
                <div class="body"><div class="nm">${s.nome}</div><div class="rs">${s.resumo}</div></div>
                ${ICONS.seta}
              </div>
              <div class="proj-detail" id="det-${s.id}">
                ${s.resumo}. Sem itens pendentes visíveis agora.
                ${(s.id === "viagens" && D.viagem) ? `<br><b>${D.viagem.origem} → ${D.viagem.destino}</b> em ${D.viagem.dias_faltando} dias (${D.viagem.data})` : ""}
                ${chartSeq(seqExemplo(s.id))}
              </div>
            </div>`).join("")}
        </div>
      `;
      root.querySelectorAll(".proj").forEach(el => el.addEventListener("click", () => {
        const open = el.classList.toggle("open");
        root.getElementById("det-" + el.dataset.id).classList.toggle("open", open);
      }));
    }

    function nav() {
      const tabs = [["hoje", "Hoje"], ["financas", "Finanças"], ["vida", "Vida"]];
      const bar = document.createElement("div");
      bar.className = "navbar";
      bar.innerHTML = tabs.map(([t, lb]) => `<button class="navbtn ${ctx.tela === t ? "on" : ""}" data-t="${t}"><span class="dot"></span><span>${lb}</span></button>`).join("");
      wrap.style.paddingBottom = "70px";
      wrap.appendChild(bar);
      bar.querySelectorAll("button").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.t)));
    }

    if (ctx.tela === "hoje") telaHoje();
    else if (ctx.tela === "financas") telaFinancas();
    else telaVida();
    nav();

    return () => { timers.forEach(clearInterval); cleanups.forEach(fn => fn()); };
  }
};
