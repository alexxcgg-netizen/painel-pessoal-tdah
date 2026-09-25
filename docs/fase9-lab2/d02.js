(window.DIRECOES = window.DIRECOES || {})[2] = {
  nome: "iOS Nativo",
  ideia: "Ajustes/Saúde: título grande que encolhe, listas agrupadas, gráficos de barras do app Saúde.",
  acento: "#0A84FF",
  fontes: ["Inter:wght@400;500;600;700"],
  render(root, D, ctx) {
    const F = D.financas;
    const brl = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
    const brl0 = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(v);
    const esc = s => String(s).replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
    const AC = "#0A84FF";
    const CATC = ["#0A84FF", "#FF9F0A", "#32D74B", "#FF453A", "#BF5AF2", "#64D2FF"];
    const cleanups = [];

    function mulberry32(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
    function seedOf(str) { let h = 0; for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0; return h; }

    const style = document.createElement("style");
    style.textContent = `
      :host, * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
      :host { display:block; height:760px; }
      .app { font-family: -apple-system, "SF Pro", Inter, system-ui, sans-serif; background:#000; color:#fff; height:100%; position:relative; overflow:hidden; }
      .navbar { position:absolute; top:0; left:0; right:0; height:44px; display:flex; align-items:center; justify-content:center; font-size:17px; font-weight:600; z-index:5; opacity:0; transition:opacity .15s ease; border-bottom:0.5px solid transparent; background:rgba(0,0,0,.86); backdrop-filter:saturate(150%) blur(14px); }
      .navbar.show { opacity:1; border-bottom-color:#38383A; }
      .scroll { position:absolute; inset:0; overflow-y:auto; -webkit-overflow-scrolling:touch; padding:52px 16px 110px; }
      .largeTitle { font-size:34px; font-weight:700; letter-spacing:-.02em; padding:2px 0 14px; transition:opacity .15s ease, transform .15s ease; }
      .sub { color:#8E8E93; font-size:13px; margin:-8px 0 16px; }
      .card { background:#1C1C1E; border-radius:14px; margin-bottom:14px; overflow:hidden; }
      .card + .cardTitle, .cardTitle { font-size:13px; text-transform:uppercase; letter-spacing:.02em; color:#8E8E93; margin:18px 4px 6px; font-weight:600; }
      .cardTitle:first-child { margin-top:0; }
      .row { display:flex; align-items:center; gap:11px; padding:10px 14px; min-height:44px; }
      .row + .row { border-top:0.5px solid #38383A; margin-left:14px; padding-left:0; }
      .row.tap { cursor:pointer; }
      .row.tap:active { background:#2C2C2E; }
      .ico { width:29px; height:29px; border-radius:7px; display:flex; align-items:center; justify-content:center; flex:none; }
      .ico svg { width:16px; height:16px; }
      .rowtext { flex:1; min-width:0; }
      .rowtitle { font-size:16px; line-height:1.25; }
      .rowsub { font-size:12.5px; color:#8E8E93; margin-top:1px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
      .rowval { font-size:15px; color:#8E8E93; font-variant-numeric:tabular-nums; white-space:nowrap; }
      .chev { color:#3A3A3C; font-size:16px; }
      .hero { padding:16px 16px 10px; }
      .heroTop { display:flex; align-items:baseline; justify-content:space-between; }
      .heroNum { font-size:30px; font-weight:700; font-variant-numeric:tabular-nums; }
      .heroDelta { font-size:13px; font-weight:600; font-variant-numeric:tabular-nums; }
      .up { color:#FF453A; } .down { color:#32D74B; }
      .heroCap { font-size:12.5px; color:#8E8E93; margin-top:2px; }
      .alert { display:flex; align-items:center; gap:10px; background:#3A1414; border:0.5px solid #5A1F1F; border-radius:14px; padding:12px 14px; margin-bottom:14px; }
      .alert svg { flex:none; }
      .alert span { font-size:14px; color:#FF9A9A; font-weight:500; }
      .topbar { display:flex; align-items:center; justify-content:space-between; padding-bottom:6px; }
      .clock { font-size:15px; font-variant-numeric:tabular-nums; color:#EBEBF5; }
      .mic { width:44px; height:44px; border-radius:22px; background:#1C1C1E; display:flex; align-items:center; justify-content:center; flex:none; border:none; }
      .mic svg { stroke:${AC}; }
      .seg { display:flex; background:#2C2C2E; border-radius:9px; padding:2px; gap:2px; }
      .seg button { flex:1; border:none; background:transparent; color:#8E8E93; font:inherit; font-size:12.5px; font-weight:600; padding:7px 0; border-radius:7px; min-height:28px; }
      .seg button[aria-selected="true"] { background:#48484A; color:#fff; }
      .chartCard { padding:16px 14px 14px; }
      .chartHead { display:flex; align-items:baseline; justify-content:space-between; margin-bottom:8px; }
      .chartHead b { font-size:15px; font-weight:600; }
      .legend { display:flex; flex-wrap:wrap; gap:8px 14px; margin-top:10px; }
      .legend .li { display:flex; align-items:center; gap:5px; font-size:11.5px; color:#8E8E93; }
      .dot { width:8px; height:8px; border-radius:50%; flex:none; }
      .barsCat .brow { display:flex; align-items:center; gap:8px; padding:5px 0; }
      .brow .name { width:96px; flex:none; font-size:12.5px; color:#EBEBF5; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
      .brow .track { flex:1; height:16px; background:#2C2C2E; border-radius:4px; overflow:hidden; }
      .brow .fill { display:block; height:100%; border-radius:4px; }
      .brow .val { width:66px; text-align:right; flex:none; font-size:12.5px; font-variant-numeric:tabular-nums; color:#8E8E93; }
      .grid2 { display:grid; grid-template-columns:1fr 1fr; }
      .grid2 .cell { padding:14px; text-align:center; }
      .grid2 .cell + .cell { border-left:0.5px solid #38383A; }
      .cell .k { font-size:11.5px; color:#8E8E93; text-transform:uppercase; letter-spacing:.03em; }
      .cell .v { font-size:19px; font-weight:700; font-variant-numeric:tabular-nums; margin-top:4px; }
      .cmpwrap { padding:14px; }
      .cmprow { display:flex; align-items:center; gap:8px; margin-bottom:10px; }
      .cmprow .lbl { width:70px; flex:none; font-size:12.5px; color:#8E8E93; }
      .cmprow .track { flex:1; height:20px; background:#2C2C2E; border-radius:5px; overflow:hidden; }
      .cmprow .fill { display:block; height:100%; border-radius:5px; }
      .cmprow .num { width:88px; text-align:right; flex:none; font-size:13px; font-variant-numeric:tabular-nums; }
      .shortcuts { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:14px; }
      .sc { background:#1C1C1E; border-radius:14px; padding:14px; display:flex; align-items:center; gap:10px; border:none; color:#fff; font:inherit; min-height:44px; }
      .sc svg { stroke:${AC}; flex:none; }
      .sc span { font-size:14px; font-weight:500; }
      .chatbar { position:absolute; left:0; right:0; bottom:56px; padding:8px 12px; display:flex; align-items:center; gap:8px; background:rgba(0,0,0,.9); backdrop-filter:blur(14px); border-top:0.5px solid #262628; }
      .chatinput { flex:1; height:36px; background:#1C1C1E; border-radius:18px; display:flex; align-items:center; padding:0 14px; color:#636366; font-size:14px; }
      .chatmic { width:36px; height:36px; border-radius:18px; background:#1C1C1E; border:none; display:flex; align-items:center; justify-content:center; }
      .chatmic svg { stroke:${AC}; }
      .navtab { position:absolute; left:0; right:0; bottom:0; height:56px; display:flex; background:rgba(0,0,0,.92); backdrop-filter:blur(14px); border-top:0.5px solid #262628; }
      .navtab button { flex:1; border:none; background:transparent; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:2px; color:#8E8E93; font:inherit; min-height:44px; }
      .navtab button.on { color:${AC}; }
      .navtab svg { width:22px; height:22px; }
      .navtab .lbl { font-size:10px; }
      .expand { max-height:0; overflow:hidden; transition:max-height .25s ease; }
      .expand.open { max-height:900px; }
      .life18 { display:grid; grid-template-columns:repeat(6,1fr); gap:8px; margin-bottom:16px; }
      .life18 .chip { display:flex; flex-direction:column; align-items:center; gap:5px; background:transparent; border:none; color:#8E8E93; font:inherit; min-height:44px; padding:4px 0; }
      .life18 .chip .ico { width:34px; height:34px; }
      .life18 .chip .t { font-size:9.5px; text-align:center; line-height:1.1; }
      .life18 .chip.on .t { color:#fff; font-weight:600; }
      .detail { padding:14px; }
      .detail p { font-size:13.5px; color:#c8c8cc; margin:0 0 8px; line-height:1.4; }
      .exemplo { font-size:10.5px; color:#636366; margin-top:6px; }
      .spark { display:block; margin-top:8px; }
    `;
    const wrap = document.createElement("div");
    wrap.className = "app";
    root.append(style, wrap);

    // ---------- chart builders ----------
    function areaChart(vals, w, h, opts) {
      opts = opts || {};
      const pad = { l: 2, r: 2, t: 10, b: 16 };
      const iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;
      const max = Math.max(1, ...vals) * 1.12;
      const n = vals.length;
      const pts = vals.map((v, i) => [pad.l + (n === 1 ? 0 : (i / (n - 1)) * iw), pad.t + ih - (v / max) * ih]);
      const line = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
      const area = line + ` L${pts[pts.length - 1][0].toFixed(1)},${pad.t + ih} L${pts[0][0].toFixed(1)},${pad.t + ih} Z`;
      const refY = opts.ref ? pad.t + ih - (Math.min(opts.ref, max) / max) * ih : null;
      const last = pts[pts.length - 1];
      const gid = "g" + Math.random().toString(36).slice(2, 8);
      return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" style="overflow:visible">
        <defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${AC}" stop-opacity=".35"/><stop offset="100%" stop-color="${AC}" stop-opacity="0"/>
        </linearGradient></defs>
        ${refY !== null ? `<line x1="${pad.l}" y1="${refY.toFixed(1)}" x2="${w - pad.r}" y2="${refY.toFixed(1)}" stroke="#48484A" stroke-width="1" stroke-dasharray="3,3"/>` : ""}
        <path d="${area}" fill="url(#${gid})"/>
        <path d="${line}" fill="none" stroke="${AC}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
        <circle cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="3.2" fill="${AC}"/>
        <text x="${pad.l}" y="${h}" font-size="10" fill="#8E8E93" font-family="Inter">1</text>
        <text x="${w - pad.r}" y="${h}" font-size="10" fill="#8E8E93" text-anchor="end" font-family="Inter">${n}</text>
      </svg>`;
    }
    function dayBars(vals, labels, w, h) {
      const pad = { l: 2, r: 2, t: 8, b: 16 };
      const iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;
      const max = Math.max(1, ...vals) * 1.15;
      const n = vals.length;
      const bw = iw / n * 0.55, gap = iw / n;
      let bars = "", labs = "";
      vals.forEach((v, i) => {
        const bh = Math.max(2, (v / max) * ih);
        const x = pad.l + i * gap + (gap - bw) / 2;
        bars += `<rect x="${x.toFixed(1)}" y="${(pad.t + ih - bh).toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" rx="2.5" fill="${AC}"/>`;
        labs += `<text x="${(x + bw / 2).toFixed(1)}" y="${h}" font-size="9.5" fill="#8E8E93" text-anchor="middle" font-family="Inter">${labels[i]}</text>`;
      });
      return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">${bars}${labs}</svg>`;
    }
    function sparkBars(vals, w, h, color) {
      const n = vals.length, gap = w / n, bw = gap * 0.6;
      const max = Math.max(1, ...vals);
      let s = "";
      vals.forEach((v, i) => {
        const bh = Math.max(2, (v / max) * h);
        s += `<rect x="${(i * gap + (gap - bw) / 2).toFixed(1)}" y="${(h - bh).toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" rx="1.5" fill="${color}"/>`;
      });
      return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">${s}</svg>`;
    }

    const iconMic = `<svg viewBox="0 0 24 24" fill="none" stroke="${AC}" stroke-width="1.8"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/></svg>`;
    const iconWarn = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#FF453A" stroke-width="1.8"><path d="M12 3l9 16H3l9-16z"/><path d="M12 10v4"/><circle cx="12" cy="17" r=".6" fill="#FF453A"/></svg>`;
    const iconSun = `<svg viewBox="0 0 24 24" fill="none" stroke="#FF9F0A" stroke-width="1.8"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>`;
    const iconCard = `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8"><rect x="3" y="6" width="18" height="12" rx="2"/><path d="M3 10h18"/></svg>`;
    const iconBank = `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8"><path d="M4 10l8-6 8 6"/><path d="M5 10v9M19 10v9M9 10v9M15 10v9"/><path d="M3 19h18"/></svg>`;
    const iconCash = `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8"><circle cx="12" cy="12" r="8"/><path d="M12 8v8M9.5 10a2 2 0 0 1 2.5-2h.3a2 2 0 1 1 0 4h-1a2 2 0 1 0 0 4h.3a2 2 0 0 0 2.5-2"/></svg>`;
    const iconCheck = `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.5 2.5L16 9.5"/></svg>`;
    const iconFin = `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8"><path d="M4 19h16M6 19V10M11 19V5M16 19v-7"/></svg>`;
    const iconVida = `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8"><rect x="4" y="4" width="7" height="7" rx="1"/><rect x="13" y="4" width="7" height="7" rx="1"/><rect x="4" y="13" width="7" height="7" rx="1"/><rect x="13" y="13" width="7" height="7" rx="1"/></svg>`;
    const iconTaref = `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8"><path d="M4 6h16M4 12h16M4 18h10"/></svg>`;
    const iconAv = `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8"><path d="M12 2l3 7 7 3-7 1-3 9-3-9-7-1 7-3 3-7z"/></svg>`;
    const iconChev = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#3A3A3C" stroke-width="2.2"><path d="M9 6l6 6-6 6"/></svg>`;
    const lifeIcons = ["habitos:M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM12 6v6l4 2", "projetos:M4 5h16v14H4zM4 9h16", "agenda:M4 5h16v15H4zM4 9h16M8 3v4M16 3v4",
      "compras:M6 8h12l-1 12H7L6 8zM9 8V6a3 3 0 1 1 6 0v2", "pessoas:M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM3 20c0-3 3-5 6-5M17 11a3 3 0 1 0 0-6M15 20c0-3 3-5 6-5",
      "treino:M6 8v8M18 8v8M2 11h4M18 11h4M6 12h12", "contas:M5 11V8a7 7 0 0 1 14 0v3M4 11h16v9H4z", "manutencao:M12 3l1.5 3 3.5.5-2.5 2.5.5 3.5L12 11l-3 1.5.5-3.5L7 6.5 10.5 6z",
      "garantia:M12 3l7 3v6c0 4-3 7-7 8-4-1-7-4-7-8V6z", "viagens:M12 2l3 7 7 3-7 1-3 9-3-9-7-1 7-3z", "lugares:M12 3a7 7 0 0 1 7 7c0 5-7 11-7 11S5 15 5 10a7 7 0 0 1 7-7zM12 7a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
      "presentes:M4 9h16v11H4zM12 9v11M4 9V6a2 2 0 0 1 2-2h2a2 2 0 0 1 0 4M12 4a2 2 0 0 1 2-2h2a2 2 0 0 1 0 4",
      "aprender:M4 6l8-3 8 3-8 3-8-3zM4 6v6l8 3 8-3V6", "salvos:M6 3h12v18l-6-4-6 4z", "mensagem:M4 4h16v13H7l-3 3z",
      "vale_a_pena:M4 12l5 5L20 6", "progresso:M4 19V9M11 19V5M18 19v-7", "revisao:M5 5h14v14H5zM8 9h8M8 13h8M8 17h5"];
    function lifeIcon(id) { const e = lifeIcons.find(s => s.startsWith(id + ":")); const p = e ? e.split(":")[1] : "M4 12h16"; return `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.7"><path d="${p}"/></svg>`; }

    function largeTitleScreen(title) {
      const nav = document.createElement("div"); nav.className = "navbar"; nav.textContent = title;
      const scroll = document.createElement("div"); scroll.className = "scroll";
      const lt = document.createElement("div"); lt.className = "largeTitle"; lt.textContent = title;
      scroll.appendChild(lt);
      scroll.addEventListener("scroll", () => {
        const y = scroll.scrollTop;
        nav.classList.toggle("show", y > 28);
        if (!ctx.reduzido) { lt.style.opacity = Math.max(0, 1 - y / 26); lt.style.transform = `translateY(${-Math.min(y, 26) * 0.4}px)`; }
      }, { passive: true });
      wrap.append(nav, scroll);
      return scroll;
    }

    function tabbar(active) {
      const tb = document.createElement("div"); tb.className = "navtab";
      const defs = [["hoje", "Hoje", `<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>`],
      ["financas", "Finanças", iconFin.replace('stroke="#fff"', 'stroke-width="1.8"')],
      ["vida", "Vida", iconVida.replace('stroke="#fff"', 'stroke-width="1.8"')]];
      defs.forEach(([id, label, svg]) => {
        const b = document.createElement("button");
        if (id === active) b.classList.add("on");
        b.innerHTML = svg + `<span class="lbl">${label}</span>`;
        b.onclick = () => ctx.irPara(id);
        tb.appendChild(b);
      });
      wrap.appendChild(tb);
    }

    function screenHoje() {
      const scroll = largeTitleScreen("Hoje");
      const now = new Date();
      const hh = String(now.getHours()).padStart(2, "0"), mm = String(now.getMinutes()).padStart(2, "0");
      const dataFmt = new Date(D.hoje.data + "T00:00:00").toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });

      const top = document.createElement("div"); top.className = "topbar";
      top.innerHTML = `<div><div class="clock">${hh}:${mm}</div><div class="sub" style="margin:0">${esc(dataFmt)}</div></div>`;
      const micBtn = document.createElement("button"); micBtn.className = "mic"; micBtn.setAttribute("aria-label", "Falar com o painel"); micBtn.innerHTML = iconMic;
      top.appendChild(micBtn);
      scroll.appendChild(top);

      const clima = document.createElement("div"); clima.className = "card row";
      clima.innerHTML = `<div class="ico" style="background:#3A2C0F">${iconSun}</div><div class="rowtext"><div class="rowtitle">${esc(D.hoje.clima.cond)}</div><div class="rowsub">${esc(D.hoje.cidade)} · chuva ${D.hoje.clima.chuva_prob}%</div></div><div class="rowval">${D.hoje.clima.temp}°C</div>`;
      scroll.appendChild(clima);

      if (D.aviso_critico) {
        const al = document.createElement("div"); al.className = "alert";
        al.innerHTML = iconWarn + `<span>${esc(D.aviso_critico)}</span>`;
        scroll.appendChild(al);
      }

      const dias = F.por_dia_mes.map(p => p.acumulado);
      const chartCard = document.createElement("div"); chartCard.className = "card chartCard";
      chartCard.innerHTML = `<div class="chartHead"><b>Gasto do mês</b><span class="rowval" style="color:#fff;font-size:17px;font-weight:700">${brl(F.gasto_mes)}</span></div>` +
        areaChart(dias, 320, 90, { ref: F.gasto_mes_anterior <= dias[dias.length - 1] * 1.3 ? F.gasto_mes_anterior : null }) +
        `<div class="sub" style="margin:6px 0 0">acumulado por dia · linha tracejada = mês anterior (${brl0(F.gasto_mes_anterior)})</div>`;
      scroll.appendChild(chartCard);

      const grouped = document.createElement("div"); grouped.className = "card";
      grouped.innerHTML = `
        <div class="row"><div class="ico" style="background:#0F3A1E">${iconCash}</div><div class="rowtext"><div class="rowtitle">Hoje</div></div><div class="rowval">${brl(F.gasto_hoje)}</div></div>
        <div class="row"><div class="ico" style="background:#3A2C0F">${iconCard}</div><div class="rowtext"><div class="rowtitle">Fatura</div><div class="rowsub">vence ${F.fatura_vencimento}</div></div><div class="rowval">${brl(F.fatura_atual)}</div></div>
        <div class="row"><div class="ico" style="background:#0F1E3A">${iconBank}</div><div class="rowtext"><div class="rowtitle">Conta</div></div><div class="rowval">${brl(F.saldo_conta)}</div></div>`;
      scroll.appendChild(grouped);

      const foco = document.createElement("div"); foco.className = "card row";
      foco.innerHTML = `<div class="ico" style="background:#2C0F3A">${iconCheck}</div><div class="rowtext"><div class="rowsub" style="margin:0">Em foco agora</div><div class="rowtitle">${esc(D.tarefas.em_foco)}</div></div>`;
      scroll.appendChild(foco);

      const scTitle = document.createElement("div"); scTitle.className = "cardTitle"; scTitle.textContent = "Atalhos";
      scroll.appendChild(scTitle);
      const scGrid = document.createElement("div"); scGrid.className = "shortcuts";
      [["Finanças", iconFin, () => ctx.irPara("financas")], ["Vida", iconVida, () => ctx.irPara("vida")],
      ["Tarefas", iconTaref, null], ["Aviação", iconAv, null]].forEach(([label, svg, fn]) => {
        const b = document.createElement("button"); b.className = "sc"; b.innerHTML = svg + `<span>${label}</span>`;
        if (fn) b.onclick = fn;
        scGrid.appendChild(b);
      });
      scroll.appendChild(scGrid);

      const chat = document.createElement("div"); chat.className = "chatbar";
      chat.innerHTML = `<div class="chatinput">Perguntar ao painel…</div><button class="chatmic">${iconMic}</button>`;
      wrap.appendChild(chat);
      tabbar("hoje");
    }

    function screenFinancas() {
      const scroll = largeTitleScreen("Finanças");

      const dif = F.gasto_mes - F.gasto_mes_anterior;
      const hero = document.createElement("div"); hero.className = "card hero";
      hero.innerHTML = `<div class="heroTop"><span class="heroNum">${brl(F.gasto_mes)}</span><span class="heroDelta ${dif <= 0 ? "down" : "up"}">${dif <= 0 ? "▼" : "▲"} ${brl0(Math.abs(dif))}</span></div><div class="heroCap">vs. mês anterior ${brl0(F.gasto_mes_anterior)}${F.orcamento_mes ? " · orçamento " + brl0(F.orcamento_mes) : ""}</div>`;
      scroll.appendChild(hero);

      const dias = F.por_dia_mes.map(p => p.acumulado);
      const evo = document.createElement("div"); evo.className = "card chartCard";
      evo.innerHTML = `<div class="chartHead"><b>Evolução do mês</b><span class="sub" style="margin:0">dia ${F.por_dia_mes[F.por_dia_mes.length - 1].dia}</span></div>` + areaChart(dias, 320, 84, {});
      scroll.appendChild(evo);

      const maxCat = Math.max(...F.por_categoria.map(c => c.valor));
      const deltas = F.por_dia_mes.map((p, i) => Math.max(0, p.acumulado - (i ? F.por_dia_mes[i - 1].acumulado : 0)));
      const last7 = F.por_dia_mes.slice(-7).map((p, i) => deltas[deltas.length - 7 + i] ?? deltas[i]);
      const labels7 = F.por_dia_mes.slice(-7).map(p => { const dt = new Date(F.mes + "-" + String(p.dia).padStart(2, "0") + "T00:00:00"); return dt.toLocaleDateString("pt-BR", { weekday: "narrow" }); });

      const catCard = document.createElement("div"); catCard.className = "card";
      const catHead = document.createElement("div"); catHead.style.padding = "14px 14px 4px";
      catHead.innerHTML = `<div class="chartHead" style="margin-bottom:10px"><b>Gasto por categoria</b></div>
        <div class="seg" role="tablist"><button id="segS" aria-selected="false">7 dias</button><button id="segM" aria-selected="true">Mês</button></div>`;
      catCard.appendChild(catHead);
      const catBody = document.createElement("div"); catBody.style.padding = "12px 14px 16px";
      catCard.appendChild(catBody);
      scroll.appendChild(catCard);

      function drawMes() {
        catBody.innerHTML = `<div class="barsCat">` + F.por_categoria.map((c, i) => {
          const pct = Math.max(3, (c.valor / maxCat) * 100);
          const col = CATC[i % CATC.length];
          return `<div class="brow"><span class="name">${esc(c.categoria)}</span><span class="track"><span class="fill" style="width:${pct.toFixed(1)}%;background:${col}"></span></span><span class="val">${brl(c.valor)}</span></div>`;
        }).join("") + `</div>`;
      }
      function drawSemana() {
        catBody.innerHTML = `<div class="sub" style="margin:0 0 8px">últimos 7 dias (gasto diário)</div>` + dayBars(last7, labels7, 320, 78);
      }
      catHead.querySelector("#segM").onclick = () => { catHead.querySelector("#segM").setAttribute("aria-selected", "true"); catHead.querySelector("#segS").setAttribute("aria-selected", "false"); drawMes(); };
      catHead.querySelector("#segS").onclick = () => { catHead.querySelector("#segS").setAttribute("aria-selected", "true"); catHead.querySelector("#segM").setAttribute("aria-selected", "false"); drawSemana(); };
      drawMes();

      const maxFC = Math.max(F.fatura_atual, F.saldo_conta, 1);
      const cmp = document.createElement("div"); cmp.className = "card";
      cmp.innerHTML = `<div class="cardTitle" style="margin:14px 14px 0">Fatura x conta</div><div class="cmpwrap">
        <div class="cmprow"><span class="lbl">Fatura</span><span class="track"><span class="fill" style="width:${(F.fatura_atual / maxFC * 100).toFixed(1)}%;background:#FF9F0A"></span></span><span class="num">${brl(F.fatura_atual)}</span></div>
        <div class="cmprow"><span class="lbl">Conta</span><span class="track"><span class="fill" style="width:${(F.saldo_conta / maxFC * 100).toFixed(1)}%;background:${F.saldo_conta < F.fatura_atual ? "#FF453A" : "#32D74B"}"></span></span><span class="num">${brl(F.saldo_conta)}</span></div>
      </div>`;
      scroll.appendChild(cmp);

      const extTitle = document.createElement("div"); extTitle.className = "cardTitle"; extTitle.textContent = "Últimos 15 dias";
      scroll.appendChild(extTitle);
      const extCard = document.createElement("div"); extCard.className = "card";
      scroll.appendChild(extCard);
      function renderExt(items) {
        extCard.innerHTML = items.map(t => `<div class="row"><div class="rowtext"><div class="rowtitle" style="font-size:14.5px">${esc(t.descricao)}</div><div class="rowsub">${t.data.slice(5).split("-").reverse().join("/")} · ${esc(t.categoria)}</div></div><div class="rowval">${brl(t.valor)}</div></div>`).join("");
      }
      renderExt(F.ultimos_15_dias.slice(0, 6));
      if (F.ultimos_15_dias.length > 6) {
        const more = document.createElement("button"); more.className = "row tap"; more.style.cssText = "width:100%;border:none;background:transparent;color:#0A84FF;font:inherit;font-size:14.5px;justify-content:center";
        more.textContent = "Carregar mais";
        more.onclick = () => { renderExt(F.ultimos_15_dias); more.remove(); };
        scroll.appendChild(more);
      }

      const subTitle = document.createElement("div"); subTitle.className = "cardTitle"; subTitle.textContent = "Assinaturas";
      scroll.appendChild(subTitle);
      const subToggle = document.createElement("div"); subToggle.className = "card row tap";
      subToggle.innerHTML = `<div class="rowtext"><div class="rowtitle">${F.assinaturas.length} assinaturas ativas</div><div class="rowsub">toque para ver</div></div><span class="chev">${iconChev}</span>`;
      const subBody = document.createElement("div"); subBody.className = "card expand";
      subBody.innerHTML = F.assinaturas.map(s => `<div class="row"><div class="rowtext"><div class="rowtitle" style="font-size:14.5px">${esc(s.nome)}</div><div class="rowsub">próxima ${s.proxima}</div></div><div class="rowval">${brl(s.valor)}</div></div>`).join("");
      subToggle.onclick = () => subBody.classList.toggle("open");
      scroll.append(subToggle, subBody);

      tabbar("financas");
    }

    function screenVida() {
      const scroll = largeTitleScreen("Vida");
      const grid = document.createElement("div"); grid.className = "life18";
      const detail = document.createElement("div"); detail.className = "card expand";
      const detailBody = document.createElement("div"); detailBody.className = "detail";
      detail.appendChild(detailBody);
      let openId = null;
      D.vida_secoes.forEach(s => {
        const chip = document.createElement("button"); chip.className = "chip";
        chip.innerHTML = `<span class="ico" style="background:#1C1C1E">${lifeIcon(s.id)}</span><span class="t">${esc(s.nome)}</span>`;
        chip.onclick = () => {
          openId = s.id;
          grid.querySelectorAll(".chip").forEach(c => c.classList.remove("on"));
          chip.classList.add("on");
          const rnd = mulberry32(seedOf(s.id));
          const vals = Array.from({ length: 7 }, () => 0.25 + rnd() * 0.75);
          let extra = "";
          if (s.id === "viagens" && D.viagem) {
            extra = `<p><b>${esc(D.viagem.origem)} → ${esc(D.viagem.destino)}</b> · faltam ${D.viagem.dias_faltando} dias (${D.viagem.data})</p>`;
          }
          detailBody.innerHTML = `<p style="font-size:16px;font-weight:600;color:#fff">${esc(s.nome)}</p><p>${esc(s.resumo)}</p>${extra}
            <div class="sub" style="margin:6px 0 0">sequência das últimas 7 semanas</div>
            <div class="spark">${sparkBars(vals, 300, 44, AC)}</div>
            <div class="exemplo">dado de exemplo — sem histórico real desta seção</div>`;
          detail.classList.add("open");
        };
        grid.appendChild(chip);
      });
      scroll.append(grid, detail);
      tabbar("vida");
    }

    if (ctx.tela === "hoje") screenHoje();
    else if (ctx.tela === "financas") screenFinancas();
    else screenVida();

    return () => cleanups.forEach(fn => fn());
  }
};
