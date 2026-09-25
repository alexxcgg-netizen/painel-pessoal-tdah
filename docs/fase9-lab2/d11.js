(window.DIRECOES = window.DIRECOES || {})[11] = {
  nome: "Banco Digital",
  ideia: "Home de banco: saldo com olho, ações redondas, cartão com fatura, extrato por ícone.",
  acento: "#A259FF",
  fontes: ["Inter:wght@400;500;600;700;800"],
  render(root, D, ctx) {
    const AC = "#A259FF";
    const COLORS = ["#A259FF", "#8B5CF6", "#C084FC", "#7C3AED", "#D8B4FE", "#6D28D9"];
    const fmt = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
    const fmt0 = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(v);
    const fin = D.financas || {};
    const timers = [], cleanups = [];
    let saldoOculto = false;

    const ICONS = {
      mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/><path d="M8 21h8"/></svg>',
      olhoOn: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>',
      olhoOff: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 3l18 18"/><path d="M10.6 5.7C11 5.6 11.5 5.5 12 5.5c6.4 0 10 6.5 10 6.5a15 15 0 0 1-3.4 4.1M6.6 6.9A15.6 15.6 0 0 0 2 12s3.6 6.5 10 6.5c1.4 0 2.6-.3 3.7-.8"/><path d="M9.5 10a3 3 0 0 0 4.2 4.2"/></svg>',
      pix: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M8 4l5.5 5.5a3.5 3.5 0 0 0 5 0L21 7M8 20l5.5-5.5a3.5 3.5 0 0 1 5 0L21 17M3 12h3M18 12h3"/></svg>',
      pagar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18M7 15h4"/></svg>',
      fatura: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M6 3h9l3 3v15H6z"/><path d="M9 9h6M9 13h6M9 17h3"/></svg>',
      sync: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 12a8 8 0 0 1 13.6-5.7L20 8M20 12a8 8 0 0 1-13.6 5.7L4 16"/><path d="M20 4v4h-4M4 20v-4h4"/></svg>',
      financas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="8.5"/><path d="M12 8v8M9.3 10c0-1.2 1.2-1.8 2.7-1.8s2.7.7 2.7 1.8-1.2 1.6-2.7 1.8-2.7.7-2.7 1.9 1.2 1.8 2.7 1.8 2.7-.5 2.7-1.8"/></svg>',
      vida: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3.2" y="3.2" width="7" height="7" rx="1.4"/><rect x="13.8" y="3.2" width="7" height="7" rx="1.4"/><rect x="3.2" y="13.8" width="7" height="7" rx="1.4"/><rect x="13.8" y="13.8" width="7" height="7" rx="1.4"/></svg>',
      tarefas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4.5 12.2l4 4 11-11.4"/></svg>',
      aviacao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 2.5v19M4 9.3l16 4.4M6.2 20.3l5.8-3 5.8 3"/></svg>',
      alerta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 3.5l9.2 16H2.8L12 3.5z"/><path d="M12 10v4.2M12 17.2h.01"/></svg>',
      baixo: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M6 9l6 6 6-6"/></svg>',
      enviar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 12l16-8-6 16-3-7-7-1z"/></svg>',
      cart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="9" cy="20" r="1.4"/><circle cx="17" cy="20" r="1.4"/><path d="M2.5 3h2.4l2 12h11.3l1.8-8H6.4"/></svg>',
      wifi: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 8.5a15 15 0 0 1 18 0M6.3 12.3a10.4 10.4 0 0 1 11.4 0M9.8 16a5.8 5.8 0 0 1 4.4 0"/><circle cx="12" cy="19.2" r="1"/></svg>',
      bag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M6 8h12l1 12H5z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/></svg>',
      bolt: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M13 2 4 14h6l-1 8 9-12h-6z"/></svg>',
      dumb: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 9v6M20 9v6M7 7v10M17 7v10M9 12h6"/></svg>',
      cloud: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M7 17a4 4 0 0 1 .6-7.96A5 5 0 0 1 17.4 10.9 3.3 3.3 0 0 1 17 17H7z"/></svg>',
      fuel: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 21V6a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v15M4 21h10M15 9h2l3 3v6a1.5 1.5 0 0 1-3 0v-2h-2"/></svg>',
      cross: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 4v16M4 12h16"/></svg>',
      doc: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M6 3h9l3 3v15H6z"/><path d="M9 12h6M9 16h4"/></svg>'
    };
    const ICON_CAT = { "Mercado": ICONS.cart, "Telecomunicações": ICONS.wifi, "Compras": ICONS.bag, "Eletrônicos": ICONS.bolt, "Academia e bem-estar": ICONS.dumb, "Serviços digitais": ICONS.cloud, "Combustível": ICONS.fuel, "Farmácia": ICONS.cross, "Impostos": ICONS.doc };
    const iconCat = c => ICON_CAT[c] || ICONS.doc;
    const ICOSET = [ICONS.vida, ICONS.tarefas, ICONS.financas, ICONS.aviacao, ICONS.bag, ICONS.dumb, ICONS.cloud, ICONS.doc];

    root.innerHTML = `
    <style>
      :host,*{box-sizing:border-box}
      .app{font-family:'Inter',sans-serif;color:#f1eef5;position:relative;min-height:100%;padding-bottom:112px}
      .mono{font-variant-numeric:tabular-nums}
      .topo{display:flex;justify-content:space-between;align-items:center;padding:14px 18px 4px}
      .topo .info{font-size:11.5px;color:#8a8593}
      .mic{width:44px;height:44px;border-radius:50%;background:#171220;border:1px solid #2a2233;color:${AC};display:flex;align-items:center;justify-content:center}
      .mic svg{width:18px;height:18px}
      .aviso{display:flex;gap:9px;align-items:center;margin:10px 18px;padding:11px 12px;border-radius:14px;background:rgba(255,99,99,.1);border:1px solid rgba(255,99,99,.3);color:#ff9b9b;font-size:12.5px}
      .aviso svg{width:16px;height:16px;flex-shrink:0}
      .saldo{padding:10px 18px 6px}
      .saldo .lbl{display:flex;align-items:center;gap:7px;font-size:11.5px;color:#8a8593;letter-spacing:.03em}
      .saldo .lbl button{width:26px;height:26px;background:none;border:none;color:#8a8593;display:flex;align-items:center;justify-content:center}
      .saldo .lbl svg{width:14px;height:14px}
      .saldo .num{font-size:32px;font-weight:800;margin-top:6px;letter-spacing:-.02em}
      .acoes{display:flex;justify-content:space-between;padding:16px 18px 6px}
      .acoes button{background:none;border:none;color:inherit;display:flex;flex-direction:column;align-items:center;gap:7px;min-width:44px;min-height:44px}
      .acoes .ic{width:52px;height:52px;border-radius:50%;background:#171220;border:1px solid #2a2233;display:flex;align-items:center;justify-content:center}
      .acoes .ic svg{width:20px;height:20px;color:${AC}}
      .acoes span{font-size:10px;color:#c4bfd0}
      .chips{display:flex;gap:8px;padding:4px 18px 4px;overflow-x:auto;scrollbar-width:none}
      .chips::-webkit-scrollbar{display:none}
      .chip{flex-shrink:0;display:flex;align-items:center;gap:6px;background:#171220;border:1px solid #2a2233;border-radius:20px;padding:8px 13px;min-height:38px;color:#dcd7e4;font-size:11.5px}
      .chip svg{width:13px;height:13px;color:${AC}}
      .card{margin:12px 18px;background:#120e17;border:1px solid #241c2c;border-radius:18px;padding:16px}
      .cardhead{display:flex;justify-content:space-between;align-items:center;font-size:11px;color:#8a8593;letter-spacing:.04em;text-transform:uppercase}
      .cartao{background:linear-gradient(135deg,#1c1428,#0e0a14);border:1px solid #2c2138}
      .cartao .venc{font-size:11px;color:#8a8593;margin-top:2px}
      .cartao .num{font-size:25px;font-weight:800;margin-top:8px}
      .barra2{height:8px;border-radius:5px;background:#241c2c;margin-top:12px;position:relative;overflow:visible}
      .barra2 i{display:block;height:100%;border-radius:5px;background:${AC}}
      .barra2 b{position:absolute;top:-3px;width:2px;height:14px;background:#f1eef5}
      .barra2cap{font-size:11px;color:#9791a3;margin-top:8px;line-height:1.4}
      .gastocard .delta{font-size:11px;padding:3px 8px;border-radius:20px;background:rgba(162,89,255,.16);color:${AC};font-weight:600}
      .gastocard .num{font-size:23px;font-weight:800;margin-top:8px}
      .chartbox{margin-top:10px}
      .chartbox svg{width:100%;display:block}
      .foco{font-size:13px;color:#e9e6ef;margin-top:8px;font-weight:500}
      .txl{display:flex;flex-direction:column}
      .tx{display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid #201a28}
      .tx:last-child{border:none}
      .tx .ic{width:34px;height:34px;border-radius:50%;background:#1c1626;display:flex;align-items:center;justify-content:center;flex-shrink:0}
      .tx .ic svg{width:15px;height:15px;color:${AC}}
      .tx .mid{flex:1;min-width:0}
      .tx .mid .n{font-size:12.5px;color:#eee;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      .tx .mid .c{font-size:10.5px;color:#8a8593}
      .tx .v{font-size:12.5px;color:#eee;flex-shrink:0}
      .toggle{width:100%;background:#120e17;border:1px solid #241c2c;border-radius:16px;padding:13px 16px;display:flex;justify-content:space-between;align-items:center;color:#eee;font-size:12.5px;min-height:44px}
      .toggle svg{width:13px;height:13px;color:#8a8593;transition:transform .18s}
      .toggle.open svg{transform:rotate(180deg)}
      .lista{display:none;margin:-4px 18px 0;background:#0d0a11;border:1px solid #201a28;border-top:none;border-radius:0 0 16px 16px;padding:4px 14px}
      .lista.open{display:block}
      .row{display:flex;justify-content:space-between;padding:8px 0;font-size:12px;border-bottom:1px solid #1c1622;color:#c7c2d0}
      .row:last-child{border:none}
      .mais{width:100%;background:none;border:1px dashed #322842;border-radius:12px;padding:10px;color:#9791a3;font-size:11.5px;margin-top:10px;min-height:44px}
      .donutwrap{display:flex;align-items:center;gap:18px;margin-top:8px}
      .donutwrap .ctr{position:relative;flex-shrink:0}
      .donutctr{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}
      .donutctr .n{font-size:14px;font-weight:700}
      .donutctr .s{font-size:8.5px;color:#8a8593;text-transform:uppercase}
      .leg{flex:1;display:flex;flex-direction:column;gap:9px;min-width:0}
      .leg .li{display:flex;align-items:center;gap:7px;font-size:11px}
      .leg .dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
      .leg .nome{flex:1;color:#c7c2d0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      .leg .pct{color:#8a8593;width:32px;text-align:right;flex-shrink:0}
      .catbars{display:flex;flex-direction:column;gap:9px;margin-top:14px}
      .catbars .li{display:flex;align-items:center;gap:8px}
      .catbars .nm{width:106px;flex-shrink:0;font-size:11px;color:#c7c2d0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      .catbars svg{flex:1;height:9px}
      .catbars .vl{width:62px;text-align:right;font-size:10.5px;color:#eee;flex-shrink:0}
      .roundgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px 6px;padding:6px 18px}
      .rd{display:flex;flex-direction:column;align-items:center;gap:6px;background:none;border:none;color:inherit;min-height:44px}
      .rd .ic{width:54px;height:54px;border-radius:50%;background:#171220;border:1px solid #2a2233;display:flex;align-items:center;justify-content:center}
      .rd.on .ic{border-color:${AC}}
      .rd .ic svg{width:19px;height:19px;color:${AC}}
      .rd span{font-size:9px;color:#c4bfd0;text-align:center;max-width:66px;line-height:1.15}
      .painel h3{margin:0 0 6px;font-size:16px;font-weight:700}
      .painel p{margin:5px 0;font-size:12.5px;color:#b3adbe;line-height:1.5}
      .painel .ex{font-size:9.5px;color:#736c80;letter-spacing:.08em;text-transform:uppercase;margin:14px 0 6px}
      .chatpill{position:absolute;left:16px;right:16px;bottom:62px;display:flex;align-items:center;gap:8px;background:#171220;border:1px solid #2a2233;border-radius:22px;padding:5px 6px 5px 16px}
      .chatpill input{flex:1;background:none;border:none;outline:none;color:#eee;font-family:inherit;font-size:13px;min-width:0}
      .chatpill input::placeholder{color:#6a6474}
      .chatpill button{width:32px;height:32px;border-radius:50%;background:#241c2c;border:none;color:${AC};display:flex;align-items:center;justify-content:center;flex-shrink:0}
      .chatpill button svg{width:13px;height:13px}
      .dock{position:absolute;left:16px;right:16px;bottom:14px;height:40px;background:rgba(18,14,23,.96);border:1px solid #241c2c;border-radius:20px;display:flex}
      .dock button{flex:1;background:none;border:none;color:#8a8593;font-size:10px;font-weight:600}
      .dock button.on{color:${AC}}
      button{font:inherit;cursor:pointer}
    </style>
    <div class="app" id="app"></div>
    `;
    const app = root.getElementById("app");

    function eixoY(vals) { return Math.max(1, ...vals); }
    function chartLinha(dias, w, h, cor) {
      const max = eixoY(dias.map(d => d.acumulado)) * 1.1;
      const n = dias.length, padB = 15;
      const ih = h - padB;
      const X = i => (w * i) / Math.max(1, n - 1);
      const Y = v => ih - (ih * v) / max;
      const pts = dias.map((d, i) => [X(i), Y(d.acumulado)]);
      const line = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
      const area = line + ` L${pts[pts.length - 1][0]},${ih} L0,${ih} Z`;
      return `<svg viewBox="0 0 ${w} ${h}" style="width:100%;height:${h}px">
        <defs><linearGradient id="gd11" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${cor}" stop-opacity=".35"/><stop offset="1" stop-color="${cor}" stop-opacity="0"/></linearGradient></defs>
        <path d="${area}" fill="url(#gd11)"/><path d="${line}" fill="none" stroke="${cor}" stroke-width="2" stroke-linecap="round"/>
        <circle cx="${pts[n - 1][0].toFixed(1)}" cy="${pts[n - 1][1].toFixed(1)}" r="3" fill="${cor}"/>
        <text x="0" y="${h - 2}" font-size="8.5" fill="#736c80">dia 1</text>
        <text x="${w}" y="${h - 2}" font-size="8.5" fill="#736c80" text-anchor="end">dia ${dias[n - 1].dia}</text>
      </svg>`;
    }
    function donut(cats, size, sw) {
      const top = cats.slice(0, 6);
      const total = top.reduce((s, c) => s + c.valor, 0) || 1;
      const r = (size - sw) / 2, c = 2 * Math.PI * r;
      let acc = 0;
      const arcs = top.map((cat, i) => {
        const frac = cat.valor / total, len = frac * c, gap = top.length > 1 ? 2.5 : 0;
        const rot = -90 + (acc / c) * 360;
        acc += len;
        return `<circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="${COLORS[i]}" stroke-width="${sw}" stroke-dasharray="${Math.max(0, len - gap)} ${c}" transform="rotate(${rot} ${size / 2} ${size / 2})"/>`;
      }).join("");
      return `<svg viewBox="0 0 ${size} ${size}" style="width:${size}px;height:${size}px">${arcs}</svg>`;
    }
    function catBars(cats, w) {
      const max = eixoY(cats.map(c => c.valor));
      const bw = w - 178;
      return cats.slice(0, 6).map((c, i) => {
        const pw = Math.max(2, (bw * c.valor) / max);
        return `<div class="li"><span class="nm">${c.categoria}</span>
          <svg viewBox="0 0 ${bw} 9"><rect width="${bw}" height="9" rx="3" fill="#241c2c"/><rect width="${pw.toFixed(1)}" height="9" rx="3" fill="${COLORS[i]}"/></svg>
          <span class="vl mono">${fmt0(c.valor)}</span></div>`;
      }).join("");
    }
    function barraExemplo(vals, w, h, cor) {
      const max = eixoY(vals), n = vals.length, gap = 3, bw = (w - gap * (n - 1)) / n;
      return `<svg viewBox="0 0 ${w} ${h}" style="width:100%;height:${h}px">${vals.map((v, i) => {
        const bh = Math.max(2, (h * v) / max);
        return `<rect x="${(i * (bw + gap)).toFixed(1)}" y="${(h - bh).toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" rx="2" fill="${cor}" opacity="${.4 + .6 * (v / max)}"/>`;
      }).join("")}</svg>`;
    }

    function dock(tela) {
      return `<div class="dock">${["hoje", "financas", "vida"].map(t => `<button data-t="${t}" class="${tela === t ? "on" : ""}">${t === "hoje" ? "Início" : t === "financas" ? "Análise" : "Vida"}</button>`).join("")}</div>`;
    }
    function ligarDock() { app.querySelectorAll(".dock button").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.t))); }

    function telaHoje() {
      const clima = D.hoje.clima || {};
      const pctDelta = fin.gasto_mes_anterior ? (fin.gasto_mes / fin.gasto_mes_anterior - 1) * 100 : 0;
      const falta = Math.max(0, (fin.fatura_atual || 0) - (fin.saldo_conta || 0));
      const pctFat = Math.min(100, ((fin.saldo_conta || 0) / Math.max(1, fin.fatura_atual || 1)) * 100);
      app.innerHTML = `
        <div class="topo">
          <div><div class="info">${D.hoje.data.slice(8, 10)}/${D.hoje.data.slice(5, 7)} · ${D.hoje.cidade} · ${clima.temp}° ${clima.cond}</div></div>
          <button class="mic" id="mic">${ICONS.mic}</button>
        </div>
        ${D.aviso_critico ? `<div class="aviso">${ICONS.alerta}<span>${D.aviso_critico}</span></div>` : ""}
        <div class="saldo">
          <div class="lbl">SALDO EM CONTA <button id="olho">${ICONS.olhoOn}</button></div>
          <div class="num mono" id="saldoNum">${fmt(fin.saldo_conta || 0)}</div>
        </div>
        <div class="acoes">
          <button data-t="financas"><span class="ic">${ICONS.pix}</span><span>Pix</span></button>
          <button data-t="financas"><span class="ic">${ICONS.pagar}</span><span>Pagar</span></button>
          <button data-t="financas"><span class="ic">${ICONS.fatura}</span><span>Fatura</span></button>
          <button id="btnSync"><span class="ic">${ICONS.sync}</span><span>Sincronizar</span></button>
        </div>
        <div class="chips">
          <button class="chip" data-t="financas">${ICONS.financas}Finanças</button>
          <button class="chip" data-t="vida">${ICONS.vida}Vida</button>
          <button class="chip" data-t="vida">${ICONS.tarefas}Tarefas</button>
          <button class="chip" data-t="vida">${ICONS.aviacao}Aviação</button>
        </div>
        <div class="card cartao">
          <div class="cardhead"><span>Cartão de crédito</span><span>vence ${fin.fatura_vencimento ? fin.fatura_vencimento.slice(8, 10) + "/" + fin.fatura_vencimento.slice(5, 7) : "—"}</span></div>
          <div class="num mono">${fmt(fin.fatura_atual || 0)}</div>
          <div class="venc">fatura atual</div>
          <div class="barra2"><i style="width:${pctFat}%"></i><b style="left:${pctFat}%"></b></div>
          <div class="barra2cap">${falta > 0 ? `Saldo em conta cobre <b class="mono" style="color:#eee">${pctFat.toFixed(0)}%</b> da fatura · faltam <b class="mono" style="color:#eee">${fmt(falta)}</b>` : `Saldo em conta cobre a fatura inteira`}</div>
        </div>
        <div class="card gastocard">
          <div class="cardhead"><span>Gasto do mês</span><span class="delta">${pctDelta > 0 ? "+" : ""}${pctDelta.toFixed(0)}%</span></div>
          <div class="num mono">${fmt(fin.gasto_mes || 0)}</div>
          <div class="chartbox">${chartLinha(fin.por_dia_mes || [], 296, 90, AC)}</div>
        </div>
        <div class="card">
          <div class="cardhead"><span>Em foco agora</span></div>
          <div class="foco">${(D.tarefas && D.tarefas.em_foco) || "Nada no momento"}</div>
        </div>
        <div class="card">
          <div class="cardhead"><span>Últimas transações</span></div>
          <div class="txl">${(fin.ultimos_15_dias || []).slice(0, 5).map(tx).join("")}</div>
        </div>
        <div class="chatpill"><input placeholder="Fale com o assistente…"/><button>${ICONS.enviar}</button></div>
        ${dock("hoje")}
      `;
      function tx(d) { return `<div class="tx"><span class="ic">${iconCat(d.categoria)}</span><div class="mid"><div class="n">${d.descricao}</div><div class="c">${d.categoria}</div></div><span class="v mono">${fmt(Math.abs(d.valor))}</span></div>`; }
      app.querySelectorAll("[data-t]").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.t)));
      root.getElementById("olho").addEventListener("click", function () {
        saldoOculto = !saldoOculto;
        this.innerHTML = saldoOculto ? ICONS.olhoOff : ICONS.olhoOn;
        root.getElementById("saldoNum").textContent = saldoOculto ? "R$ ••••••" : fmt(fin.saldo_conta || 0);
      });
      const sync = root.getElementById("btnSync");
      sync.addEventListener("click", () => { sync.style.opacity = ".5"; setTimeout(() => sync.style.opacity = "1", ctx.reduzido ? 0 : 500); });
      ligarDock();
    }

    function telaFinancas() {
      const cats = fin.por_categoria || [];
      const total = cats.reduce((s, c) => s + c.valor, 0) || 1;
      const dias = fin.ultimos_15_dias || [];
      const pctDelta = fin.gasto_mes_anterior ? (fin.gasto_mes / fin.gasto_mes_anterior - 1) * 100 : 0;
      app.innerHTML = `
        <div class="topo"><div><div class="info" style="font-size:16px;color:#f1eef5;font-weight:700">Análise de gastos</div><div class="info">${fin.mes || ""} · ${fmt(fin.gasto_mes || 0)} · ${pctDelta > 0 ? "+" : ""}${pctDelta.toFixed(0)}% vs mês anterior</div></div></div>
        <div class="card">
          <div class="cardhead"><span>Gasto por categoria</span></div>
          <div class="donutwrap">
            <div class="ctr"><div>${donut(cats, 118, 17)}</div><div class="donutctr"><span class="n mono">${fmt0(fin.gasto_mes || 0)}</span><span class="s">total</span></div></div>
            <div class="leg">${cats.slice(0, 6).map((c, i) => `<div class="li"><span class="dot" style="background:${COLORS[i]}"></span><span class="nome">${c.categoria}</span><span class="pct mono">${((c.valor / total) * 100).toFixed(0)}%</span></div>`).join("")}</div>
          </div>
          <div class="catbars">${catBars(cats, 328)}</div>
        </div>
        <div class="card">
          <div class="cardhead"><span>Evolução no mês</span></div>
          <div class="chartbox">${chartLinha(fin.por_dia_mes || [], 296, 110, AC)}</div>
        </div>
        <div class="card">
          <div class="cardhead"><span>Fatura × Conta</span></div>
          <div style="display:flex;justify-content:space-between;margin-top:10px"><span style="font-size:11.5px;color:#c7c2d0">Fatura</span><span class="mono">${fmt(fin.fatura_atual || 0)}</span></div>
          <div class="barra2" style="margin-top:6px"><i style="width:100%;background:${AC}"></i></div>
          <div style="display:flex;justify-content:space-between;margin-top:14px"><span style="font-size:11.5px;color:#c7c2d0">Conta</span><span class="mono">${fmt(fin.saldo_conta || 0)}</span></div>
          <div class="barra2" style="margin-top:6px"><i style="width:${Math.min(100, ((fin.saldo_conta || 0) / Math.max(1, fin.fatura_atual || 1)) * 100)}%;background:#6d6d72"></i></div>
        </div>
        <div class="card">
          <div class="cardhead"><span>Últimos dias</span></div>
          <div class="txl" id="listaDias">${dias.slice(0, 6).map(tx).join("")}</div>
          ${dias.length > 6 ? `<button class="mais" id="btnMais">carregar mais (${dias.length - 6})</button>` : ""}
        </div>
        <button class="toggle" id="btnAssin"><span>Assinaturas (${(fin.assinaturas || []).length})</span>${ICONS.baixo}</button>
        <div class="lista" id="assinList">${(fin.assinaturas || []).map(a => `<div class="row"><span>${a.nome}</span><span class="mono">${fmt(a.valor)}</span></div>`).join("")}</div>
        <button class="toggle" id="btnExtrato" style="margin-top:10px">${`<span>Extrato completo</span>${ICONS.baixo}`}</button>
        <div class="lista" id="extratoList">${dias.map(li).join("")}</div>
        <div style="height:16px"></div>
        ${dock("financas")}
      `;
      function tx(d) { return `<div class="tx"><span class="ic">${iconCat(d.categoria)}</span><div class="mid"><div class="n">${d.descricao}</div><div class="c">${d.data.slice(8, 10)}/${d.data.slice(5, 7)}</div></div><span class="v mono">${fmt(Math.abs(d.valor))}</span></div>`; }
      function li(d) { return `<div class="row"><span>${d.data.slice(8, 10)}/${d.data.slice(5, 7)} · ${d.descricao}</span><span class="mono">${fmt(Math.abs(d.valor))}</span></div>`; }
      const btnMais = root.getElementById("btnMais");
      if (btnMais) btnMais.addEventListener("click", () => { root.getElementById("listaDias").innerHTML = dias.map(tx).join(""); btnMais.remove(); });
      root.getElementById("btnAssin").addEventListener("click", function () { this.classList.toggle("open"); root.getElementById("assinList").classList.toggle("open"); });
      root.getElementById("btnExtrato").addEventListener("click", function () { this.classList.toggle("open"); root.getElementById("extratoList").classList.toggle("open"); });
      ligarDock();
    }

    function telaVida() {
      const secs = D.vida_secoes || [];
      app.innerHTML = `
        <div class="topo"><div class="info" style="font-size:16px;color:#f1eef5;font-weight:700">Vida</div></div>
        <div class="roundgrid" id="grid">${secs.map((s, i) => `<button class="rd" data-id="${s.id}"><span class="ic">${ICOSET[i % ICOSET.length]}</span><span>${s.nome}</span></button>`).join("")}</div>
        <div class="card painel" id="painel"></div>
        ${dock("vida")}
      `;
      function seed(str) { let h = 0; for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0; return h; }
      function pintar(id) {
        const s = secs.find(x => x.id === id);
        root.querySelectorAll(".rd").forEach(b => b.classList.toggle("on", b.dataset.id === id));
        const sd = seed(s.id);
        const vals = Array.from({ length: 7 }, (_, i) => 15 + ((sd >> (i * 3)) % 85));
        root.getElementById("painel").innerHTML = `
          <h3>${s.nome}</h3><p>${s.resumo}</p>
          <p>Última atualização registrada nesta seção.</p>
          ${D.viagem && /viage/i.test(s.nome) ? `<p>Próxima viagem: <b>${D.viagem.origem} → ${D.viagem.destino}</b> em ${D.viagem.dias_faltando} dias (${D.viagem.data}).</p>` : ""}
          <div class="ex">progresso da semana (exemplo)</div>
          ${barraExemplo(vals, 296, 54, AC)}
        `;
      }
      root.querySelectorAll(".rd").forEach(b => b.addEventListener("click", () => pintar(b.dataset.id)));
      if (secs[0]) pintar(secs[0].id);
      ligarDock();
    }

    if (ctx.tela === "hoje") telaHoje();
    else if (ctx.tela === "financas") telaFinancas();
    else telaVida();

    return () => { timers.forEach(clearInterval); cleanups.forEach(fn => fn()); };
  }
};
