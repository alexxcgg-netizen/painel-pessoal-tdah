(window.DIRECOES = window.DIRECOES || {})[3] = {
  nome: "Carteira",
  ideia: "Cartões físicos empilhados (Conta, Cartão, Assinaturas, Metas); tocar puxa o cartão pra cima e abre os detalhes.",
  acento: "#8A05BE",
  fontes: ["Inter:wght@400;500;600;700", "Manrope:wght@700;800"],
  render(root, D, ctx) {
    const F = D.financas, T = D.tarefas;
    const brl = (v) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);
    const brl0 = (v) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(v || 0);
    const timers = [];

    const ICONS = {
      banco: '<path d="M3 10.5 12 4l9 6.5"/><path d="M4.5 10.5v8M9.5 10.5v8M14.5 10.5v8M19.5 10.5v8"/><path d="M3 20.5h18"/>',
      cartao: '<rect x="2.5" y="5.5" width="19" height="13" rx="2.2"/><path d="M2.5 10h19"/><path d="M6 14.5h4"/>',
      repetir: '<path d="M4 12a8 8 0 0 1 13.9-5.4L20 8.5"/><path d="M20 4v4.5h-4.5"/><path d="M20 12a8 8 0 0 1-13.9 5.4L4 15.5"/><path d="M4 20v-4.5h4.5"/>',
      alvo: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.8"/><circle cx="12" cy="12" r="1.1" fill="currentColor" stroke="none"/>',
      mic: '<rect x="9.3" y="2.5" width="5.4" height="11" rx="2.7"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0"/><path d="M12 17.5v3.3"/>',
      chevron: '<path d="M6 9l6 6 6-6"/>',
      seta: '<path d="M5 12h14"/><path d="M13 6l6 6-6 6"/>',
      aviao: '<path d="M3.5 12.8 20 6.2c1-.4 1.9.5 1.5 1.5l-6.6 16.5-3-7-7-3z" transform="scale(.85) translate(1.5,-.3)"/>'
    };
    const svg = (name, size = 18) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ""}</svg>`;

    const style = document.createElement("style");
    style.textContent = `
      :host, * { box-sizing: border-box; }
      .app { font-family: 'Inter', system-ui, sans-serif; background:#000; color:#f1eef4; min-height:100%;
             padding: 16px 16px 132px; -webkit-font-smoothing:antialiased; }
      .num { font-family:'Manrope',sans-serif; font-variant-numeric: tabular-nums; letter-spacing:-.01em; }
      .fraco { color:#9a94a3; }
      .top { display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:12px; }
      .hora { font-size:28px; font-weight:800; font-family:'Manrope',sans-serif; line-height:1; }
      .data { font-size:12.5px; color:#9a94a3; margin-top:3px; }
      .clima { font-size:12.5px; color:#c9c3d2; text-align:right; }
      .mic { width:44px; height:44px; border-radius:22px; background:#17131c; border:1px solid #2b2433;
             display:flex; align-items:center; justify-content:center; color:#e7dff0; flex:0 0 auto; }
      .aviso { display:flex; align-items:center; gap:8px; background:#241019; border:1px solid #4a1c2b; color:#ff9db3;
               border-radius:14px; padding:10px 12px; font-size:12.5px; margin-bottom:14px; }
      .aviso b { color:#ff8fa8; }
      .resumo-dia { border:1px solid #241d2c; border-radius:18px; padding:14px 16px; margin-bottom:22px; background:#0b0910; }
      .resumo-dia .rot { font-size:11.5px; text-transform:uppercase; letter-spacing:.08em; color:#9a94a3; margin-bottom:6px; }
      .resumo-dia .valor { font-size:26px; font-weight:800; }
      .resumo-dia .comp { font-size:12.5px; color:#9a94a3; margin-top:2px; }
      .grafico-linha { margin-top:10px; }
      .grafico-legenda { display:flex; justify-content:space-between; font-size:9.5px; color:#7d7686; margin-top:2px; }
      .secao-titulo { font-size:12px; text-transform:uppercase; letter-spacing:.1em; color:#7d7686; margin: 4px 0 10px 2px; }
      .pilha { display:flex; flex-direction:column; }
      .cartao { position:relative; margin-bottom:20px; border-radius:20px; border:1px solid #241d2c; background:#0d0b12;
                overflow:hidden; cursor:pointer; transition: border-color .2s ease, background .2s ease; }
      .cartao::before, .cartao::after { content:""; position:absolute; left:0; right:0; height:12px; border:1px solid #201a27;
             background:#0a0810; z-index:-1; border-radius:0 0 16px 16px; }
      .cartao::before { bottom:-7px; left:9px; right:9px; opacity:.85; }
      .cartao::after { bottom:-13px; left:18px; right:18px; opacity:.55; }
      .cartao[data-aberto="true"] { border-color:#8A05BE; background:#140f1c; }
      .c-head { display:flex; align-items:center; gap:12px; padding:15px 16px; min-height:44px; }
      .c-ico { width:38px; height:38px; border-radius:11px; background:#1e1626; color:#c58fe8; display:flex;
               align-items:center; justify-content:center; flex:0 0 auto; }
      .cartao[data-aberto="true"] .c-ico { background:#8A05BE; color:#fff; }
      .c-info { flex:1; min-width:0; }
      .c-titulo { font-size:14.5px; font-weight:600; }
      .c-sub { font-size:12px; color:#9a94a3; margin-top:1px; }
      .c-valor { font-size:16.5px; font-weight:700; white-space:nowrap; }
      .c-chevron { color:#6b6474; transition: transform .25s ease; flex:0 0 auto; }
      .cartao[data-aberto="true"] .c-chevron { transform: rotate(180deg); color:#c58fe8; }
      .c-detalhe { max-height:0; overflow:hidden; transition: max-height .28s ease; }
      .cartao[data-aberto="true"] .c-detalhe { max-height:520px; }
      .c-detalhe-in { padding:0 16px 16px; border-top:1px solid #221b2a; }
      .linha-kv { display:flex; justify-content:space-between; align-items:center; padding:9px 0; font-size:13px; border-bottom:1px solid #1a1520; }
      .linha-kv:last-child { border-bottom:0; }
      .linha-kv .k { color:#9a94a3; }
      .barra-mini { height:6px; border-radius:3px; background:#1e1826; overflow:hidden; margin-top:10px; }
      .barra-mini > i { display:block; height:100%; background:linear-gradient(90deg,#8A05BE,#c15be8); border-radius:3px; }
      .cta { display:block; width:100%; text-align:center; margin-top:10px; padding:11px; border-radius:12px; border:1px solid #2b2433;
             background:transparent; color:#e7dff0; font:inherit; font-size:13px; min-height:44px; cursor:pointer; }
      /* Finanças screen */
      .fin-resumo { border:1px solid #241d2c; border-radius:20px; padding:18px; margin-bottom:18px; background:#0d0b12; }
      .fin-resumo .rot { font-size:12px; color:#9a94a3; text-transform:uppercase; letter-spacing:.08em; }
      .fin-resumo .valor { font-size:32px; font-weight:800; margin-top:6px; }
      .fin-resumo .comp { font-size:13px; margin-top:6px; }
      .up { color:#ff9db3; } .down { color:#8fe0b0; }
      .card-aberto { border:1px solid #8A05BE; border-radius:22px; background:#140f1c; padding:20px 18px; margin-bottom:18px; }
      .card-aberto .cab { display:flex; align-items:center; gap:10px; margin-bottom:16px; }
      .card-aberto .cab .c-ico { background:#8A05BE; color:#fff; }
      .card-aberto .cab b { font-size:15px; }
      .rosca-wrap { display:flex; align-items:center; gap:18px; margin-bottom:14px; }
      .rosca-total { position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; }
      .rosca-total b { font-size:15px; font-weight:800; }
      .rosca-total span { font-size:9.5px; color:#9a94a3; text-transform:uppercase; letter-spacing:.06em; }
      .rosca-box { position:relative; width:112px; height:112px; flex:0 0 auto; }
      .legenda { flex:1; display:flex; flex-direction:column; gap:7px; min-width:0; }
      .leg-item { display:flex; align-items:center; gap:8px; font-size:12px; }
      .leg-dot { width:8px; height:8px; border-radius:50%; flex:0 0 auto; }
      .leg-nome { flex:1; color:#c9c3d2; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
      .leg-val { color:#9a94a3; font-family:'Manrope',sans-serif; }
      .cat-lista { display:flex; flex-direction:column; gap:11px; margin-top:4px; }
      .cat-row2 { display:grid; grid-template-columns: 100px 1fr auto; gap:10px; align-items:center; font-size:12.5px; }
      .cat-row2 .nome { color:#c9c3d2; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
      .cat-row2 .barra { height:7px; border-radius:4px; background:#1e1826; overflow:hidden; }
      .cat-row2 .barra i { display:block; height:100%; background:#8A05BE; border-radius:4px; }
      .cat-row2 .val { color:#e7dff0; font-family:'Manrope',sans-serif; }
      .fx-compare { border:1px solid #241d2c; border-radius:18px; padding:16px; margin-bottom:18px; background:#0d0b12; }
      .fx-row2 { display:flex; justify-content:space-between; align-items:baseline; }
      .fx-label { font-size:12px; color:#9a94a3; }
      .fx-val { font-size:15.5px; font-weight:700; }
      .fx-bar { height:10px; border-radius:5px; background:#1e1826; overflow:hidden; margin-top:5px; }
      .fx-bar > i { display:block; height:100%; border-radius:5px; }
      .mini-chart { margin-top:10px; }
      .mini-chart .legenda2 { font-size:10.5px; color:#7d7686; margin-top:4px; }
      .extrato-item { display:flex; align-items:center; gap:10px; padding:10px 0; border-bottom:1px solid #1a1520; font-size:13px; }
      .extrato-item:last-child { border-bottom:0; }
      .ex-info { flex:1; min-width:0; }
      .ex-desc { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
      .ex-meta { color:#9a94a3; font-size:11.5px; margin-top:1px; }
      .ex-val { font-family:'Manrope',sans-serif; font-weight:600; white-space:nowrap; }
      /* Vida passes */
      .passe { position:relative; margin-bottom:12px; border-radius:16px; border:1px solid #241d2c; background:#0d0b12; overflow:hidden; cursor:pointer; }
      .passe::before { content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:#8A05BE; }
      .passe-head { display:flex; align-items:center; gap:12px; padding:13px 14px 13px 18px; min-height:44px; }
      .passe-head b { font-size:13.5px; font-weight:600; flex:1; }
      .passe-head span { font-size:11.5px; color:#9a94a3; }
      .passe-det { max-height:0; overflow:hidden; transition:max-height .25s ease; }
      .passe[data-aberto="true"] .passe-det { max-height:220px; }
      .passe[data-aberto="true"] { border-color:#4a3357; }
      .passe-det-in { padding:0 18px 14px; font-size:12.5px; color:#c9c3d2; line-height:1.55; }
      .navbar { position:fixed; left:0; right:0; bottom:0; max-width:430px; margin:0 auto; display:flex;
                background:#0a0810; border-top:1px solid #201a27; padding:8px 10px calc(8px + env(safe-area-inset-bottom,0px)); gap:4px; }
      .navbar button { flex:1; min-height:46px; background:transparent; border:0; color:#7d7686; font:inherit; font-size:11px;
                        display:flex; flex-direction:column; align-items:center; justify-content:center; gap:3px; cursor:pointer; }
      .navbar button[aria-current="true"] { color:#e7dff0; }
      .navbar .dotp { width:5px; height:5px; border-radius:50%; background:transparent; margin-bottom:1px; }
      .navbar button[aria-current="true"] .dotp { background:#8A05BE; }
      .chip-row { display:flex; gap:8px; margin:16px 0 6px; flex-wrap:wrap; }
      .chip { border:1px solid #2b2433; border-radius:12px; padding:9px 13px; font-size:12.5px; color:#e7dff0; background:#120e18; min-height:44px; cursor:pointer; }
      .foco { border:1px solid #241d2c; border-radius:16px; padding:12px 14px; margin-top:14px; font-size:13px; background:#0d0b12; }
      .foco .rot { font-size:11px; color:#9a94a3; text-transform:uppercase; letter-spacing:.06em; margin-bottom:4px; }
      .chat { position:fixed; left:0; right:0; bottom:64px; max-width:430px; margin:0 auto; padding:0 16px; }
      .chat-in { display:flex; align-items:center; gap:8px; background:#120e18; border:1px solid #2b2433; border-radius:22px; padding:6px 6px 6px 14px; min-height:44px; }
      .chat-in span { flex:1; color:#7d7686; font-size:13px; }
      .chat-in .cursor { width:1.5px; height:14px; background:#c58fe8; animation:blink 1s step-end infinite; }
      @keyframes blink { 50% { opacity:0; } }
      .scr-hoje, .scr-fin, .scr-vida { padding-bottom: 8px; }
    `;
    root.appendChild(style);
    const wrap = document.createElement("div");
    wrap.className = "app";
    root.appendChild(wrap);

    const catColors = ["#8A05BE", "#FF9F45", "#33C2A0", "#4C8DFF", "#E4568C", "#6b6474"];
    function categoriasAgrupadas() {
      const lista = [...F.por_categoria].sort((a, b) => b.valor - a.valor);
      if (lista.length <= 6) return lista;
      const top = lista.slice(0, 5);
      const outras = lista.slice(5).reduce((s, c) => s + c.valor, 0);
      top.push({ categoria: "Outras", valor: outras });
      return top;
    }

    function roscaSVG(cats) {
      const total = cats.reduce((s, c) => s + c.valor, 0) || 1;
      const r = 48, cx = 56, cy = 56, circ = 2 * Math.PI * r;
      let acc = 0;
      const segs = cats.map((c, i) => {
        const frac = c.valor / total;
        const dash = Math.max(frac * circ - 2, 0);
        const off = -acc * circ;
        acc += frac;
        return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${catColors[i % catColors.length]}" stroke-width="14"
                 stroke-dasharray="${dash} ${circ - dash}" stroke-dashoffset="${off}" transform="rotate(-90 ${cx} ${cy})" stroke-linecap="butt"/>`;
      }).join("");
      return `<svg width="112" height="112" viewBox="0 0 112 112">${segs}</svg>`;
    }

    function diaChartSVG(dias, refValor, refLabel, gid) {
      const w = 294, h = 96, padL = 4, padR = 4, padT = 12, padB = 4;
      const vals = dias.map(d => d.acumulado);
      const max = Math.max(1, ...vals, refValor || 0);
      const n = vals.length;
      const x = i => padL + (n > 1 ? (i / (n - 1)) * (w - padL - padR) : 0);
      const y = v => padT + (1 - v / max) * (h - padT - padB);
      const pts = vals.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
      const area = `${x(0).toFixed(1)},${y(0).toFixed(1)} ${pts} ${x(n - 1).toFixed(1)},${y(0).toFixed(1)}`;
      const refY = refValor ? y(Math.min(refValor, max)).toFixed(1) : null;
      return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="none" role="img" aria-label="gasto acumulado no mês">
        <defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8A05BE"/><stop offset="1" stop-color="#8A05BE" stop-opacity="0"/></linearGradient></defs>
        <text x="${padL}" y="9" font-size="8.5" fill="#7d7686">${brl0(max)}</text>
        ${refY ? `<line x1="${padL}" y1="${refY}" x2="${w - padR}" y2="${refY}" stroke="#5a5164" stroke-width="1" stroke-dasharray="3 3"/>
        <text x="${w - padR}" y="${(+refY - 4).toFixed(1)}" text-anchor="end" font-size="8.5" fill="#9a94a3">${refLabel} ${brl0(refValor)}</text>` : ""}
        <polygon points="${area}" fill="url(#${gid})" opacity=".4"/>
        <polyline points="${pts}" fill="none" stroke="#c58fe8" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
        <circle cx="${x(n - 1).toFixed(1)}" cy="${y(vals[n - 1]).toFixed(1)}" r="3" fill="#c58fe8"/>
      </svg>
      <div class="grafico-legenda"><span>dia 1</span><span>dia ${n}</span></div>`;
    }

    function fxCompareHTML() {
      const max = Math.max(F.fatura_atual, F.saldo_conta, 1);
      const pFat = Math.max(2, (F.fatura_atual / max) * 100);
      const pConta = Math.max(2, (F.saldo_conta / max) * 100);
      const critico = F.saldo_conta < F.fatura_atual * 0.15;
      return `<div class="fx-compare">
        <div class="fx-row2"><span class="fx-label">Fatura · vence ${fmtData(F.fatura_vencimento)}</span><span class="fx-val num">${brl(F.fatura_atual)}</span></div>
        <div class="fx-bar"><i style="width:${pFat}%;background:#c58fe8"></i></div>
        <div class="fx-row2" style="margin-top:12px"><span class="fx-label">Saldo em conta</span><span class="fx-val num" style="color:${critico ? "#ff9db3" : "#f1eef4"}">${brl(F.saldo_conta)}</span></div>
        <div class="fx-bar"><i style="width:${pConta}%;background:${critico ? "#ff6b81" : "#8fe0b0"}"></i></div>
      </div>`;
    }

    function seedNum(str) { let h = 0; for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0; return h; }
    function miniBarSVG(vals) {
      const w = 168, h = 36, gap = 3, n = vals.length, barW = (w - gap * (n - 1)) / n;
      const max = Math.max(1, ...vals);
      const bars = vals.map((v, i) => { const bh = Math.max(2, (v / max) * h); const x = i * (barW + gap); return `<rect x="${x.toFixed(1)}" y="${(h - bh).toFixed(1)}" width="${barW.toFixed(1)}" height="${bh.toFixed(1)}" rx="1.5" fill="#a44bd1"/>`; }).join("");
      return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}">${bars}</svg>`;
    }
    function vidaMiniChart(s) {
      if (s.id === "viagens" && D.viagem) {
        const pct = Math.max(6, 100 - Math.min(100, (D.viagem.dias_faltando / 30) * 100));
        return `<div class="mini-chart"><div class="fx-bar"><i style="width:${pct}%;background:#c58fe8"></i></div>
          <div class="legenda2">${D.viagem.dias_faltando} dias até ${D.viagem.destino}</div></div>`;
      }
      const seed = seedNum(s.id);
      const vals = Array.from({ length: 7 }, (_, i) => 2 + ((seed >> (i * 3)) % 9));
      return `<div class="mini-chart">${miniBarSVG(vals)}<div class="legenda2">Atividade da semana (exemplo) · seg–dom</div></div>`;
    }

    function telaHoje() {
      const now = new Date();
      const hh = String(now.getHours()).padStart(2, "0"), mm = String(now.getMinutes()).padStart(2, "0");
      const dataFmt = new Date(D.hoje.data + "T12:00:00").toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "short" });
      const economia = F.gasto_mes_anterior - F.gasto_mes;
      const assinTotal = F.assinaturas.reduce((s, a) => s + a.valor, 0);
      const cards = [
        { id: "conta", titulo: "Conta", sub: "Saldo disponível", valor: brl(F.saldo_conta), icone: "banco",
          det: `<div class="linha-kv"><span class="k">Saldo disponível</span><span class="num">${brl(F.saldo_conta)}</span></div>
                <div class="linha-kv"><span class="k">Gasto hoje</span><span class="num">${brl(F.gasto_hoje)}</span></div>` },
        { id: "cartao", titulo: "Cartão de crédito", sub: "Fatura de " + fmtData(F.fatura_vencimento), valor: brl(F.fatura_atual), icone: "cartao",
          det: `<div class="linha-kv"><span class="k">Fatura atual</span><span class="num">${brl(F.fatura_atual)}</span></div>
                <div class="linha-kv"><span class="k">Vencimento</span><span>${fmtData(F.fatura_vencimento)}</span></div>
                <button class="cta" data-ir="financas">Ver categorias e extrato</button>` },
        { id: "assin", titulo: "Assinaturas", sub: F.assinaturas.length + " ativas", valor: brl(assinTotal), icone: "repetir",
          det: F.assinaturas.map(a => `<div class="linha-kv"><span class="k">${a.nome} · próx. ${fmtData(a.proxima)}</span><span class="num">${brl(a.valor)}</span></div>`).join("") },
        { id: "metas", titulo: "Metas", sub: "Economia do mês", valor: (economia >= 0 ? "+" : "") + brl(economia), icone: "alvo",
          det: `<div class="linha-kv"><span class="k">Gasto este mês</span><span class="num">${brl(F.gasto_mes)}</span></div>
                <div class="linha-kv"><span class="k">Mês anterior</span><span class="num">${brl(F.gasto_mes_anterior)}</span></div>
                <div class="barra-mini"><i style="width:${Math.min(100, (F.gasto_mes / Math.max(F.gasto_mes, F.gasto_mes_anterior)) * 100)}%"></i></div>` }
      ];
      wrap.innerHTML = `
        <div class="scr-hoje">
          <div class="top">
            <div><div class="hora num">${hh}:${mm}</div><div class="data">${cap(dataFmt)} · ${D.hoje.cidade}</div></div>
            <div class="clima">${D.hoje.clima.cond}<br><span class="num">${D.hoje.clima.temp}°C</span> · chuva ${D.hoje.clima.chuva_prob}%</div>
            <button class="mic" aria-label="Comando de voz">${svg("mic", 18)}</button>
          </div>
          ${D.aviso_critico ? `<div class="aviso">⚠ <span><b>Aviso</b> — ${D.aviso_critico}</span></div>` : ""}
          <div class="resumo-dia">
            <div class="rot">Gasto do mês</div>
            <div class="valor num">${brl(F.gasto_mes)}</div>
            <div class="comp">vs. mês anterior ${brl(F.gasto_mes_anterior)}</div>
            <div class="grafico-linha">${diaChartSVG(F.por_dia_mes, F.gasto_mes_anterior, "mês ant.", "gradHoje")}</div>
          </div>
          <div class="secao-titulo">Seus cartões</div>
          <div class="pilha">
            ${cards.map(c => cartaoHTML(c)).join("")}
          </div>
          <div class="foco"><div class="rot">Em foco agora</div>${T.em_foco}</div>
          <div class="chip-row">
            <button class="chip" data-ir="financas">${svg("cartao", 15)} Finanças</button>
            <button class="chip" data-ir="vida">${svg("repetir", 15)} Vida</button>
          </div>
        </div>`;
      montarChatENav("hoje");
      ligarCartoes();
    }

    function cartaoHTML(c) {
      return `<div class="cartao" data-id="${c.id}" data-aberto="false">
        <div class="c-head">
          <div class="c-ico">${svg(c.icone, 19)}</div>
          <div class="c-info"><div class="c-titulo">${c.titulo}</div><div class="c-sub">${c.sub}</div></div>
          <div class="c-valor num">${c.valor}</div>
          <div class="c-chevron">${svg("chevron", 16)}</div>
        </div>
        <div class="c-detalhe"><div class="c-detalhe-in">${c.det}</div></div>
      </div>`;
    }

    function ligarCartoes() {
      wrap.querySelectorAll(".cartao").forEach(el => {
        const head = el.querySelector(".c-head");
        if (!head) return;
        head.addEventListener("click", () => {
          const aberto = el.getAttribute("data-aberto") === "true";
          wrap.querySelectorAll(".cartao").forEach(o => o.setAttribute("data-aberto", "false"));
          el.setAttribute("data-aberto", aberto ? "false" : "true");
        });
      });
      wrap.querySelectorAll("[data-ir]").forEach(b => b.addEventListener("click", (e) => { e.stopPropagation(); ctx.irPara(b.dataset.ir); }));
    }

    function telaFinancas() {
      const cats = categoriasAgrupadas();
      const dif = F.gasto_mes - F.gasto_mes_anterior;
      const total = cats.reduce((s, c) => s + c.valor, 0) || 1;
      const maxCat = Math.max(...F.por_categoria.map(c => c.valor));
      let expandido = false;
      wrap.innerHTML = `
        <div class="scr-fin">
          <div class="fin-resumo">
            <div class="rot">Gasto do mês · ${F.mes}</div>
            <div class="valor num">${brl(F.gasto_mes)}</div>
            <div class="comp ${dif <= 0 ? "down" : "up"}">${dif <= 0 ? "▼" : "▲"} ${brl0(Math.abs(dif))} vs. mês anterior</div>
          </div>
          <div class="card-aberto">
            <div class="cab"><div class="c-ico">${svg("cartao", 18)}</div><b>Cartão de crédito · gasto por categoria</b></div>
            <div class="rosca-wrap">
              <div class="rosca-box">${roscaSVG(cats)}<div class="rosca-total"><b class="num">${brl0(total)}</b><span>total</span></div></div>
              <div class="legenda">${cats.map((c, i) => `<div class="leg-item"><span class="leg-dot" style="background:${catColors[i % catColors.length]}"></span><span class="leg-nome">${c.categoria}</span><span class="leg-val num">${brl0(c.valor)}</span></div>`).join("")}</div>
            </div>
            <div class="secao-titulo" style="margin-top:16px">Todas as categorias</div>
            <div class="cat-lista">
              ${F.por_categoria.slice().sort((a, b) => b.valor - a.valor).map(c => `
                <div class="cat-row2"><span class="nome">${c.categoria}</span><span class="barra"><i style="width:${(c.valor / maxCat) * 100}%"></i></span><span class="val">${brl0(c.valor)}</span></div>
              `).join("")}
            </div>
          </div>
          <div class="secao-titulo">Evolução do mês</div>
          <div class="fx-compare">
            <div class="grafico-linha">${diaChartSVG(F.por_dia_mes, F.gasto_mes_anterior, "mês ant.", "gradFin")}</div>
          </div>
          <div class="secao-titulo">Fatura x conta</div>
          ${fxCompareHTML()}
          <div class="secao-titulo">Últimos 15 dias</div>
          <div class="cartao cartao-lista" style="cursor:default">
            <div id="lista-extrato"></div>
            <div style="padding:0 16px 16px">
              <button class="cta" id="btn-mais">Ver todo o extrato</button>
            </div>
          </div>
          <div class="secao-titulo">Assinaturas</div>
          <div class="cartao" data-id="assin-fin" data-aberto="false">
            <div class="c-head"><div class="c-ico">${svg("repetir", 19)}</div>
              <div class="c-info"><div class="c-titulo">Assinaturas ativas</div><div class="c-sub">${F.assinaturas.length} recorrências</div></div>
              <div class="c-valor num">${brl(F.assinaturas.reduce((s, a) => s + a.valor, 0))}</div>
              <div class="c-chevron">${svg("chevron", 16)}</div></div>
            <div class="c-detalhe"><div class="c-detalhe-in">${F.assinaturas.map(a => `<div class="linha-kv"><span class="k">${a.nome} · próx. ${fmtData(a.proxima)}</span><span class="num">${brl(a.valor)}</span></div>`).join("")}</div></div>
          </div>
        </div>`;
      function renderExtrato(qtd) {
        const el = wrap.querySelector("#lista-extrato");
        el.innerHTML = F.ultimos_15_dias.slice(0, qtd).map(t => `
          <div class="extrato-item" style="padding-left:16px;padding-right:16px">
            <div class="ex-info"><div class="ex-desc">${t.descricao}</div><div class="ex-meta">${fmtData(t.data)} · ${t.categoria}</div></div>
            <div class="ex-val num">${brl(t.valor)}</div>
          </div>`).join("");
      }
      renderExtrato(6);
      const btn = wrap.querySelector("#btn-mais");
      btn.addEventListener("click", () => { renderExtrato(F.ultimos_15_dias.length); btn.remove(); });
      ligarCartoes();
      montarChatENav("financas");
    }

    function telaVida() {
      wrap.innerHTML = `<div class="scr-vida">
        <div class="secao-titulo">Vida · ${D.vida_secoes.length} seções</div>
        <div class="pilha" id="passes"></div>
      </div>`;
      const cont = wrap.querySelector("#passes");
      D.vida_secoes.forEach(s => {
        const div = document.createElement("div");
        div.className = "passe"; div.setAttribute("data-aberto", "false");
        let extra = `<p>${1 + (s.id.length % 4)} itens ativos nesta seção.</p>`;
        if (s.id === "viagens" && D.viagem) {
          extra = `<p>Próxima viagem: ${D.viagem.origem} → ${D.viagem.destino}, em ${D.viagem.dias_faltando} dias (${fmtData(D.viagem.data)}).</p>`;
        }
        div.innerHTML = `<div class="passe-head"><b>${s.nome}</b><span>${svg("chevron", 15)}</span></div>
          <div class="passe-det"><div class="passe-det-in"><p class="fraco">${s.resumo}</p>${extra}${vidaMiniChart(s)}</div></div>`;
        div.querySelector(".passe-head").addEventListener("click", () => {
          const aberto = div.getAttribute("data-aberto") === "true";
          div.setAttribute("data-aberto", aberto ? "false" : "true");
        });
        cont.appendChild(div);
      });
      montarChatENav("vida");
    }

    function montarChatENav(tela) {
      const chat = document.createElement("div");
      chat.className = "chat";
      chat.innerHTML = `<div class="chat-in">${svg("mic", 16)}<span>Falar com o painel…</span><span class="cursor"></span></div>`;
      wrap.appendChild(chat);
      const nav = document.createElement("div");
      nav.className = "navbar";
      nav.innerHTML = ["hoje", "financas", "vida"].map(t => {
        const label = t === "hoje" ? "Hoje" : t === "financas" ? "Finanças" : "Vida";
        return `<button data-t="${t}" aria-current="${t === tela}"><span class="dotp"></span>${label}</button>`;
      }).join("");
      wrap.appendChild(nav);
      nav.querySelectorAll("button").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.t)));
    }

    function fmtData(iso) { if (!iso) return "—"; const d = new Date(iso + "T12:00:00"); return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" }); }
    function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

    if (ctx.tela === "hoje") telaHoje();
    else if (ctx.tela === "financas") telaFinancas();
    else telaVida();

    return () => { timers.forEach(clearInterval); };
  }
};
