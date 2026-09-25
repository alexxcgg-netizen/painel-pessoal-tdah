(window.DIRECOES = window.DIRECOES || {})[1] = {
  nome: "Conversa",
  ideia: "O app é um chat de verdade: mensagens do assistente trazem cartões ricos com gráficos embutidos.",
  acento: "#159C82",
  fontes: ["Inter:wght@400;500;600;700"],
  render(root, D, ctx) {
    const AC = "#159C82";
    const fmt = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);
    const fin = D.financas || {};
    const timers = [], toclear = [], cleanups = [];

    function seedRand(str) {
      let h = 0;
      for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0;
      return () => { h = (h * 1664525 + 1013904223) >>> 0; return (h >>> 8) / 16777216; };
    }

    const ICONS = {
      mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/><path d="M8 21h8"/></svg>',
      send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 12l16-8-6 16-3-7-7-1z"/></svg>',
      alerta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 3l10 18H2L12 3z"/><path d="M12 10v4M12 17h.01"/></svg>',
      chuva: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M7 15a4 4 0 0 1 .8-7.94A5 5 0 0 1 17.6 9.1 3.5 3.5 0 0 1 17 16H7z"/><path d="M8 19l-1 2M12 19l-1 2M16 19l-1 2"/></svg>',
      chevron: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M9 6l6 6-6 6"/></svg>',
      financas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="9"/><path d="M12 7v10M9 9.5c0-1.4 1.3-2 3-2s3 .8 3 2-1.3 1.8-3 2-3 .8-3 2 1.3 2 3 2 3-.6 3-2"/></svg>',
      vida: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>',
      tarefas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 6h16M4 12h16M4 18h10"/><circle cx="20" cy="18" r="2"/></svg>',
      aviacao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 2v20M4 9l16 4M6 20l6-3 6 3"/></svg>',
      bolha: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M21 11.5a8.4 8.4 0 0 1-9 8.4A8.9 8.9 0 0 1 3 13a8.4 8.4 0 0 1 8.5-8.5A8.5 8.5 0 0 1 21 11.5z"/></svg>',
      lista: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>',
      voltar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M15 6l-6 6 6 6"/></svg>'
    };

    root.innerHTML = `
    <style>
      :host,*{box-sizing:border-box}
      .app{font-family:Inter,system-ui,sans-serif;color:#ececec;min-height:100%;position:relative;padding-bottom:66px}
      .top{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px 14px;border-bottom:1px solid #1d1f1e}
      .tclock .hh{font-size:19px;font-weight:600;font-variant-numeric:tabular-nums}
      .tclock .dd{font-size:11px;color:#8f9390;margin-top:1px}
      .tright{display:flex;align-items:center;gap:10px}
      .clima{font-size:11.5px;color:#a9adaa;text-align:right;line-height:1.3}
      .clima svg{width:14px;height:14px;vertical-align:-2px;margin-right:3px;color:${AC}}
      .mic{width:44px;height:44px;border-radius:50%;border:1px solid #232523;background:#0e0f0e;color:${AC};display:flex;align-items:center;justify-content:center;flex-shrink:0}
      .mic svg{width:19px;height:19px}
      .thread{padding:16px 14px 8px;display:flex;flex-direction:column;gap:16px}
      .msg{display:flex;gap:10px;align-items:flex-start}
      .msg.user{justify-content:flex-end}
      .dot{width:22px;height:22px;border-radius:50%;background:#0e0f0e;border:1px solid ${AC};flex-shrink:0;margin-top:2px;display:flex;align-items:center;justify-content:center}
      .dot::after{content:"";width:7px;height:7px;border-radius:50%;background:${AC}}
      .bubble{flex:1;min-width:0;font-size:14px;line-height:1.5;color:#d8dad9}
      .bubble.user{flex:0 1 auto;background:#1a1c1b;border:1px solid #262a28;border-radius:14px 14px 3px 14px;padding:9px 13px;color:#e6e6e6;max-width:80%}
      .lead{margin:0 0 10px;color:#c7cac8}
      .card{border:1px solid #22241f;background:#111312;border-radius:14px;padding:14px;margin-top:2px}
      .card+.card{margin-top:10px}
      .card-head{display:flex;align-items:center;justify-content:space-between;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:#8f9390;margin-bottom:10px}
      .pill{font-size:11px;font-weight:600;padding:2px 8px;border-radius:99px;font-variant-numeric:tabular-nums}
      .pill.down{color:${AC};background:rgba(21,156,130,.15)}
      .pill.up{color:#e8918f;background:rgba(232,145,143,.12)}
      .valor{font-size:26px;font-weight:700;font-variant-numeric:tabular-nums;color:#fafafa;margin-bottom:8px}
      .chart-acum{width:100%;display:block;overflow:visible}
      .chart-acum .area{fill:${AC};opacity:.16}
      .chart-acum .linha{fill:none;stroke:${AC};stroke-width:2}
      .chart-acum .ponto{fill:${AC}}
      .chart-acum .eixo{stroke:#26302c}
      .chart-acum .ref{stroke:#5a5e5b;stroke-dasharray:3 3}
      .chart-acum .ref-lbl{fill:#7d817e;font-size:8.5px;font-family:Inter}
      .chart-acum .eixo-lbl{fill:#6b6f6c;font-size:8.5px;font-family:Inter}
      .mini-row{display:flex;gap:8px;margin-top:12px}
      .mini{flex:1;text-align:center;border:1px solid #1f211f;border-radius:9px;padding:8px 4px}
      .mini .l{display:block;font-size:9.5px;color:#8a8e8b;letter-spacing:.05em;text-transform:uppercase}
      .mini .v{display:block;margin-top:3px;font-size:13px;font-variant-numeric:tabular-nums;color:#ececec}
      .foco-txt{font-size:14.5px;color:#f0f0f0}
      .aviso{border-color:#3a201f;background:#180f0e}
      .aviso .card-head{color:#e0928f}
      .aviso-txt{display:flex;gap:8px;align-items:flex-start;font-size:13.5px;color:#f0d6d4}
      .aviso-txt svg{width:16px;height:16px;color:#e0928f;flex-shrink:0;margin-top:1px}
      .catlist{display:flex;flex-direction:column;gap:9px}
      .catrow{display:grid;grid-template-columns:96px 1fr auto;gap:8px;align-items:center}
      .catnome{font-size:11.5px;color:#c2c5c3;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      .catbarwrap{height:9px;border-radius:5px;background:#1a1c1b;overflow:hidden}
      .catbar{height:100%;border-radius:5px}
      .catval{font-size:11.5px;font-variant-numeric:tabular-nums;color:#e6e6e6;min-width:64px;text-align:right}
      .fvcbars{display:flex;flex-direction:column;gap:10px}
      .fvcrow .lbl{display:flex;justify-content:space-between;font-size:11.5px;color:#c2c5c3;margin-bottom:5px}
      .fvcrow .lbl b{color:#ececec;font-variant-numeric:tabular-nums;font-weight:600}
      .fvctrack{height:12px;border-radius:6px;background:#1a1c1b;overflow:hidden}
      .fvcfill{height:100%;border-radius:6px;background:${AC}}
      .fvcfill.dim{background:#4d5451}
      .lista{display:flex;flex-direction:column}
      .li{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid #191b1a;font-size:12.5px}
      .li .d{color:#7d817e;font-variant-numeric:tabular-nums;width:40px;flex-shrink:0}
      .li .n{flex:1;color:#cfd1cf;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      .li .v{font-variant-numeric:tabular-nums;color:#e8e8e8}
      .mais,.toggle{width:100%;min-height:44px;text-align:center;border:1px dashed #262a28;border-radius:9px;color:#9a9e9b;font-size:12px;background:transparent;margin-top:8px;font-family:inherit}
      .toggle{display:flex;justify-content:space-between;align-items:center;padding:0 12px;border-style:solid}
      .toggle svg{width:14px;height:14px;transition:transform .15s}
      .toggle[aria-expanded="true"] svg{transform:rotate(90deg)}
      .subpanel{display:none;padding-top:10px}
      .subpanel.open{display:block}
      .assinrow{display:flex;justify-content:space-between;padding:7px 0;font-size:12px;color:#c2c5c3;border-bottom:1px solid #191b1a}
      .atalhos{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
      .atalho{min-height:56px;border:1px solid #22241f;border-radius:11px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:5px;background:#0e0f0e;color:#c2c5c3;font-family:inherit}
      .atalho svg{width:17px;height:17px;color:${AC}}
      .atalho span{font-size:9.5px}
      .typing .bubble{display:flex;gap:4px;align-items:center;padding:10px 0}
      .tdot{width:6px;height:6px;border-radius:50%;background:#7d817e}
      .anim .typing .tdot{animation:tpulse 1.1s infinite ease-in-out}
      .anim .typing .tdot:nth-child(2){animation-delay:.15s}
      .anim .typing .tdot:nth-child(3){animation-delay:.3s}
      @keyframes tpulse{0%,60%,100%{opacity:.25;transform:translateY(0)}30%{opacity:1;transform:translateY(-2px)}}
      .chips{display:flex;gap:7px;overflow-x:auto;padding:2px 14px 10px;scrollbar-width:none}
      .chips::-webkit-scrollbar{display:none}
      .chip{flex-shrink:0;min-height:34px;padding:0 13px;border-radius:99px;border:1px solid #262a28;background:#0e0f0e;color:#c2c5c3;font-size:12px;font-family:inherit;display:flex;align-items:center}
      .inputbar{display:flex;flex-direction:column;gap:8px;margin:0 14px 10px;border:1px solid #242624;border-radius:18px;background:#0e0f0e;padding:12px 14px}
      .inputbar .ph{font-size:13.5px;color:#6b6f6c}
      .inputrow{display:flex;justify-content:flex-end}
      .inputrow .mic2{width:36px;height:36px;border-radius:50%;background:${AC};color:#08120e;display:flex;align-items:center;justify-content:center}
      .inputrow .mic2 svg{width:16px;height:16px}
      .navbar{position:absolute;left:0;right:0;bottom:0;display:flex;border-top:1px solid #1d1f1e;background:#0a0b0a}
      .navbtn{flex:1;min-height:54px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;background:transparent;border:none;color:#6b6f6c;font-family:inherit}
      .navbtn svg{width:18px;height:18px}
      .navbtn.on{color:${AC}}
      .navbtn span{font-size:9.5px;letter-spacing:.03em}
      .vtitle{padding:14px 14px 4px;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#8a8e8b}
      .convlist{display:flex;flex-direction:column;padding:4px 10px}
      .convrow{display:flex;align-items:center;gap:11px;padding:11px 4px;border-bottom:1px solid #17181a;min-height:44px;background:transparent;border-left:none;border-right:none;border-top:none;text-align:left;font-family:inherit;width:100%;color:inherit}
      .convico{width:38px;height:38px;border-radius:50%;background:#111312;border:1px solid #22241f;display:flex;align-items:center;justify-content:center;flex-shrink:0}
      .convico svg{width:16px;height:16px;color:${AC}}
      .convbody{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px}
      .convnome{font-size:13.5px;color:#ececec;font-weight:500}
      .convprev{font-size:11.5px;color:#8a8e8b;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-top:1px}
      .convrow>svg{width:14px;height:14px;color:#5a5e5b;flex-shrink:0}
      .backbtn{display:flex;align-items:center;gap:6px;min-height:44px;padding:0 14px;color:#c2c5c3;font-size:13px;background:transparent;border:none;font-family:inherit}
      .backbtn svg{width:16px;height:16px}
      .vsecname{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:${AC};margin-bottom:4px}
      .minichart{width:100%;display:block;margin-top:10px}
      .minichart rect{fill:${AC}}
      .exemplo{font-size:10px;color:#6b6f6c;margin-top:5px;font-style:italic}
    </style>
    <div class="app ${ctx.reduzido ? "" : "anim"}" id="app"></div>
    `;
    const app = root.getElementById("app");

    function chartAcumulado(dias, refValor, w, h) {
      w = w || 300; h = h || 92;
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
      return `<svg viewBox="0 0 ${w} ${h}" class="chart-acum" role="img" aria-label="Gasto acumulado do mês, dia a dia">
        <line x1="0" y1="${(h - padB).toFixed(1)}" x2="${w}" y2="${(h - padB).toFixed(1)}" class="eixo"/>
        ${showRef ? `<line x1="0" y1="${refY.toFixed(1)}" x2="${w}" y2="${refY.toFixed(1)}" class="ref"/><text x="${w}" y="${(refY - 4).toFixed(1)}" class="ref-lbl" text-anchor="end">mês anterior ${fmt(refValor)}</text>` : ""}
        <path d="${area}"/>
        <path d="${path}" class="linha"/>
        <circle cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="3" class="ponto"/>
        <text x="0" y="${h}" class="eixo-lbl">dia 1</text>
        <text x="${w}" y="${h}" class="eixo-lbl" text-anchor="end">dia ${n}</text>
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
        out += `<rect x="${(i * (w / n)).toFixed(1)}" y="${(h - bh).toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" rx="2" opacity="${(0.35 + v * 0.5).toFixed(2)}"/>`;
      }
      return `<svg viewBox="0 0 ${w} ${h}" class="minichart" role="img" aria-label="Sequência ilustrativa da semana">${out}</svg>`;
    }

    function catColor(i) {
      const shades = ["#7FE0C8", "#5CD3B4", "#38C69E", "#1FB790", "#159C82", "#0F7E69"];
      return shades[i % shades.length];
    }

    function cardCategorias() {
      const cats = (fin.por_categoria || []).slice().sort((a, b) => b.valor - a.valor).slice(0, 6);
      const max = Math.max.apply(null, cats.map(c => c.valor).concat([1]));
      return `<div class="card">
        <div class="card-head"><span>Gasto por categoria</span></div>
        <div class="catlist">${cats.map((c, i) => `
          <div class="catrow">
            <span class="catnome">${c.categoria}</span>
            <div class="catbarwrap"><div class="catbar" style="width:${(c.valor / max * 100).toFixed(1)}%;background:${catColor(i)}"></div></div>
            <span class="catval">${fmt(c.valor)}</span>
          </div>`).join("")}
        </div>
      </div>`;
    }

    function cardEvolucao() {
      return `<div class="card">
        <div class="card-head"><span>Evolução do mês</span></div>
        ${chartAcumulado(fin.por_dia_mes || [], fin.gasto_mes_anterior, 300, 100)}
      </div>`;
    }

    function cardFaturaConta() {
      const f = fin.fatura_atual || 0, c = fin.saldo_conta || 0;
      const max = Math.max(f, c, 1);
      return `<div class="card">
        <div class="card-head"><span>Fatura × Conta</span></div>
        <div class="fvcbars">
          <div class="fvcrow"><div class="lbl"><span>Fatura atual</span><b>${fmt(f)}</b></div><div class="fvctrack"><div class="fvcfill" style="width:${(f / max * 100).toFixed(1)}%"></div></div></div>
          <div class="fvcrow"><div class="lbl"><span>Saldo em conta</span><b>${fmt(c)}</b></div><div class="fvctrack"><div class="fvcfill dim" style="width:${(c / max * 100).toFixed(1)}%"></div></div></div>
        </div>
      </div>`;
    }

    function telaHoje() {
      const clima = D.hoje.clima || {};
      app.innerHTML = `
        <div class="top">
          <div class="tclock"><div class="hh" id="relogio">--:--</div><div class="dd">${D.hoje.data} · ${D.hoje.cidade}</div></div>
          <div class="tright">
            <div class="clima">${ICONS.chuva}${clima.temp}°C<br>${clima.cond}</div>
            <button class="mic" aria-label="Falar com o assistente">${ICONS.mic}</button>
          </div>
        </div>
        <div class="thread" id="thread">
          <div class="msg"><div class="dot"></div><div class="bubble typing"><span class="tdot"></span><span class="tdot"></span><span class="tdot"></span></div></div>
        </div>
        <div class="chips">
          <button class="chip" data-t="financas">Quanto gastei hoje?</button>
          <button class="chip" data-t="vida">O que tenho agora?</button>
          <button class="chip" data-t="financas">Ver categorias</button>
          <button class="chip" data-t="vida">Seções da vida</button>
        </div>
        <div class="inputbar">
          <span class="ph">Mensagem…</span>
          <div class="inputrow"><span class="mic2">${ICONS.mic}</span></div>
        </div>
      `;
      const thread = root.getElementById("thread");
      function reveal() {
        const msgs = [];
        if (D.aviso_critico) msgs.push(`<div class="msg"><div class="dot"></div><div class="bubble"><p class="lead">Antes de mais nada:</p><div class="card aviso"><div class="card-head"><span>Aviso</span></div><div class="aviso-txt">${ICONS.alerta}<span>${D.aviso_critico}</span></div></div></div></div>`);
        const delta = fin.gasto_mes_anterior ? ((fin.gasto_mes - fin.gasto_mes_anterior) / fin.gasto_mes_anterior * 100) : 0;
        const subiu = delta >= 0;
        msgs.push(`<div class="msg"><div class="dot"></div><div class="bubble"><p class="lead">Bom dia. Aqui está o resumo de ${D.hoje.data.split("-").reverse().join("/")}.</p>
          <div class="card">
            <div class="card-head"><span>Gasto do mês</span><span class="pill ${subiu ? "up" : "down"}">${subiu ? "▲" : "▼"} ${Math.abs(delta).toFixed(0)}%</span></div>
            <div class="valor" id="numGasto">R$ 0,00</div>
            ${chartAcumulado(fin.por_dia_mes || [], fin.gasto_mes_anterior)}
            <div class="mini-row">
              <div class="mini"><span class="l">Hoje</span><span class="v">${fmt(fin.gasto_hoje)}</span></div>
              <div class="mini"><span class="l">Fatura</span><span class="v">${fmt(fin.fatura_atual)}</span></div>
              <div class="mini"><span class="l">Conta</span><span class="v">${fmt(fin.saldo_conta)}</span></div>
            </div>
          </div></div></div>`);
        msgs.push(`<div class="msg"><div class="dot"></div><div class="bubble"><div class="card"><div class="card-head"><span>Em foco agora</span></div><div class="foco-txt">${(D.tarefas && D.tarefas.em_foco) || "—"}</div></div></div></div>`);
        msgs.push(`<div class="msg"><div class="dot"></div><div class="bubble"><div class="card"><div class="card-head"><span>Atalhos</span></div>
          <div class="atalhos">
            <button class="atalho" data-t="financas">${ICONS.financas}<span>Finanças</span></button>
            <button class="atalho" data-t="vida">${ICONS.vida}<span>Vida</span></button>
            <button class="atalho" data-t="vida">${ICONS.tarefas}<span>Tarefas</span></button>
            <button class="atalho" data-t="vida">${ICONS.aviacao}<span>Aviação</span></button>
          </div></div></div></div>`);
        thread.innerHTML = msgs.join("");
        thread.querySelectorAll("[data-t]").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.t)));
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
      }
      if (ctx.reduzido) reveal();
      else toclear.push(setTimeout(reveal, 550));
      app.querySelectorAll(".chip").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.t)));

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
      const orcTxt = fin.orcamento_mes ? ` de orçamento de ${fmt(fin.orcamento_mes)}` : "";
      app.innerHTML = `
        <div class="top"><div class="tclock"><div class="hh">Finanças</div><div class="dd">${fin.mes}</div></div></div>
        <div class="thread" id="thread">
          <div class="msg user"><div class="bubble user">Como estão minhas finanças esse mês?</div></div>
          <div class="msg"><div class="dot"></div><div class="bubble typing"><span class="tdot"></span><span class="tdot"></span><span class="tdot"></span></div></div>
        </div>
      `;
      const thread = root.getElementById("thread");
      function reveal() {
        let html = `<div class="msg user"><div class="bubble user">Como estão minhas finanças esse mês?</div></div>`;
        html += `<div class="msg"><div class="dot"></div><div class="bubble">
          <p class="lead">Você gastou ${fmt(fin.gasto_mes)} até agora${orcTxt}, contra ${fmt(fin.gasto_mes_anterior)} no mês passado.</p>
          ${cardCategorias()}
          ${cardEvolucao()}
          ${cardFaturaConta()}
          <div class="card">
            <div class="card-head"><span>Últimos 15 dias</span></div>
            <div class="lista" id="lista15">${dias.slice(0, 6).map(li).join("")}</div>
            ${dias.length > 6 ? `<button class="mais" id="btnMais">carregar mais (${dias.length - 6})</button>` : ""}
          </div>
          <button class="toggle" id="btnAssin" aria-expanded="false"><span>Assinaturas (${(fin.assinaturas || []).length})</span>${ICONS.chevron}</button>
          <div class="subpanel" id="painelAssin">${(fin.assinaturas || []).map(a => `<div class="assinrow"><span>${a.nome}</span><span>${fmt(a.valor)}</span></div>`).join("")}</div>
          <button class="toggle" id="btnExtrato" aria-expanded="false"><span>Extrato completo</span>${ICONS.chevron}</button>
          <div class="subpanel" id="painelExtrato">${dias.map(li).join("")}</div>
        </div></div>`;
        thread.innerHTML = html;
        const btnMais = root.getElementById("btnMais");
        if (btnMais) btnMais.addEventListener("click", () => { root.getElementById("lista15").innerHTML = dias.map(li).join(""); btnMais.remove(); });
        const wireToggle = (btnId, panelId) => {
          const b = root.getElementById(btnId), p = root.getElementById(panelId);
          b.addEventListener("click", () => { const open = p.classList.toggle("open"); b.setAttribute("aria-expanded", String(open)); });
        };
        wireToggle("btnAssin", "painelAssin");
        wireToggle("btnExtrato", "painelExtrato");
      }
      function li(d) {
        const dd = d.data.slice(8, 10) + "/" + d.data.slice(5, 7);
        return `<div class="li"><span class="d">${dd}</span><span class="n">${d.descricao}</span><span class="v">${fmt(Math.abs(d.valor))}</span></div>`;
      }
      if (ctx.reduzido) reveal();
      else toclear.push(setTimeout(reveal, 450));
    }

    function telaVida() {
      const secs = D.vida_secoes || [];
      app.innerHTML = `
        <div class="vtitle">Conversas · Vida</div>
        <div class="convlist" id="convlist"></div>
        <div id="convthread"></div>
      `;
      const ICOSET = [ICONS.vida, ICONS.tarefas, ICONS.financas, ICONS.aviacao, ICONS.bolha, ICONS.lista];
      const list = root.getElementById("convlist");
      list.innerHTML = secs.map((s, i) => `<button class="convrow" data-id="${s.id}">
          <span class="convico">${ICOSET[i % ICOSET.length]}</span>
          <span class="convbody"><span class="convnome">${s.nome}</span><span class="convprev">${s.resumo}</span></span>
          ${ICONS.chevron}
        </button>`).join("");
      list.querySelectorAll(".convrow").forEach(el => el.addEventListener("click", () => abrir(el.dataset.id)));

      function abrir(id) {
        const s = secs.find(x => x.id === id);
        if (!s) return;
        list.style.display = "none";
        const th = root.getElementById("convthread");
        th.innerHTML = `
          <button class="backbtn" id="voltar">${ICONS.voltar}<span>Vida</span></button>
          <div class="thread">
            <div class="msg user"><div class="bubble user">O que tenho em ${s.nome.toLowerCase()}?</div></div>
            <div class="msg"><div class="dot"></div><div class="bubble">
              <div class="vsecname">${s.nome}</div>
              <p class="lead">${s.resumo}. Última atualização registrada nesta seção.</p>
              <p class="lead">Toque em voltar para trocar de conversa.</p>
              ${D.viagem && id === "viagens" ? `<p class="lead">Próxima viagem: <b>${D.viagem.origem} → ${D.viagem.destino}</b> em ${D.viagem.dias_faltando} dias (${D.viagem.data}).</p>` : ""}
              ${chartMini(id)}
              <div class="exemplo">Sequência ilustrativa da semana (exemplo)</div>
            </div></div>
          </div>
        `;
        root.getElementById("voltar").addEventListener("click", () => { th.innerHTML = ""; list.style.display = ""; });
      }
    }

    function nav() {
      const tabs = [["hoje", ICONS.bolha, "Hoje"], ["financas", ICONS.financas, "Finanças"], ["vida", ICONS.vida, "Vida"]];
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
      toclear.forEach(clearTimeout);
      cleanups.forEach(fn => fn());
    };
  }
};
