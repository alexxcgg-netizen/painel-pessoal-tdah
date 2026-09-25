(window.DIRECOES = window.DIRECOES || {})[17] = {
  nome: "Vidro",
  ideia: "Placas de vidro translúcido (blur) sobre fundo em gradiente petróleo→grafite; tipografia grande, sóbria, sem neon.",
  acento: "#FFFFFF",
  fontes: ["Inter:wght@400;500;600;700;800"],
  render(root, D, ctx) {
    const F = D.financas, T = D.tarefas;
    const brl = (v) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);
    const brl0 = (v) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(v || 0);
    const timers = [];

    const ICONS = {
      mic: '<rect x="9.3" y="2.5" width="5.4" height="11" rx="2.7"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0"/><path d="M12 17.5v3.3"/>',
      alerta: '<path d="M12 3.2 22 20.5H2z"/><path d="M12 9v5"/><circle cx="12" cy="17" r=".15" fill="currentColor"/>',
      chevron: '<path d="M6 9l6 6 6-6"/>',
      seta: '<path d="M5 12h14"/><path d="M13 6l6 6-6 6"/>',
      chat: '<path d="M4 5h16v11H8l-4 4z"/>',
      casa: '<path d="M4 11.5 12 4l8 7.5"/><path d="M6 10v9h12v-9"/>',
      cartao: '<rect x="2.7" y="6" width="18.6" height="12" rx="2.4"/><path d="M2.7 10.3h18.6"/>',
      vida: '<path d="M12 20.5s-7.8-4.6-7.8-10A4.6 4.6 0 0 1 12 7.4 4.6 4.6 0 0 1 19.8 10.5c0 5.4-7.8 10-7.8 10z"/>'
    };
    const svg = (name, size = 18, sw = 1.6) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ""}</svg>`;

    const style = document.createElement("style");
    style.textContent = `
      :host, * { box-sizing:border-box; }
      .fundo { position:absolute; inset:0; overflow:hidden;
               background: linear-gradient(160deg, #08161b 0%, #0f2028 30%, #182428 62%, #222528 100%); }
      .mancha { position:absolute; border-radius:50%; filter: blur(70px); opacity:.55; }
      .m1 { width:340px; height:340px; background:#2f6478; top:-90px; left:-90px; }
      .m2 { width:300px; height:300px; background:#37464f; bottom:40px; right:-110px; }
      .m3 { width:260px; height:260px; background:#1c3a45; bottom:-120px; left:20%; }
      .app { position:relative; min-height:760px; font-family:-apple-system,BlinkMacSystemFont,'Inter',system-ui,sans-serif;
             color:#f2f5f6; padding:18px 16px 148px; -webkit-font-smoothing:antialiased; }
      .num { font-variant-numeric:tabular-nums; letter-spacing:-.01em; }
      .fraco { color:rgba(242,245,246,.58); }
      .maisfraco { color:rgba(242,245,246,.4); }
      .vidro { background:rgba(255,255,255,.06); backdrop-filter:blur(22px) saturate(150%); -webkit-backdrop-filter:blur(22px) saturate(150%);
               border:1px solid rgba(255,255,255,.14); border-radius:24px; }
      .top { display:flex; align-items:center; gap:10px; margin-bottom:14px; }
      .top-info { flex:1; }
      .hora { font-size:32px; font-weight:800; line-height:1; letter-spacing:-.02em; }
      .data { font-size:13px; color:rgba(242,245,246,.58); margin-top:4px; }
      .clima { font-size:12.5px; color:rgba(242,245,246,.7); text-align:right; line-height:1.4; }
      .mic { width:46px; height:46px; border-radius:23px; display:flex; align-items:center; justify-content:center; color:#f2f5f6; flex:0 0 auto; cursor:pointer; }
      .aviso { display:flex; gap:10px; align-items:flex-start; padding:14px 16px; margin-bottom:16px; border-color:rgba(255,255,255,.2); }
      .aviso svg { color:#e8a37e; flex:0 0 auto; margin-top:1px; }
      .aviso b { display:block; font-size:11px; text-transform:uppercase; letter-spacing:.08em; color:#e8a37e; margin-bottom:3px; }
      .cartao-grande { padding:22px 20px; margin-bottom:16px; }
      .rot { font-size:12px; text-transform:uppercase; letter-spacing:.09em; color:rgba(242,245,246,.5); }
      .valor-grande { font-size:36px; font-weight:800; margin-top:8px; letter-spacing:-.02em; }
      .comp { font-size:13px; margin-top:6px; color:rgba(242,245,246,.6); }
      .up { color:#e8a37e; } .down { color:#8fd6c1; }
      .grafico-legenda { display:flex; justify-content:space-between; font-size:9.5px; color:rgba(242,245,246,.42); margin-top:2px; }
      .chip3-row { display:flex; gap:10px; margin-top:16px; }
      .chip3 { flex:1; min-width:0; border-radius:16px; padding:11px 10px; background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.1); }
      .chip3 .r { font-size:10px; color:rgba(242,245,246,.5); text-transform:uppercase; letter-spacing:.05em; white-space:nowrap; }
      .chip3 .v { font-size:13.5px; font-weight:700; margin-top:4px; white-space:nowrap; }
      .secao-titulo { font-size:12px; text-transform:uppercase; letter-spacing:.09em; color:rgba(242,245,246,.5); margin:20px 2px 10px; }
      .foco-card { padding:14px 16px; margin-top:2px; }
      .pill-row { display:flex; gap:10px; flex-wrap:wrap; margin-top:14px; }
      .pill { display:flex; align-items:center; gap:7px; padding:12px 16px; border-radius:18px; font-size:13.5px; color:#f2f5f6;
              background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.14); min-height:44px; cursor:pointer; }
      .chat-fixo { position:fixed; left:0; right:0; bottom:66px; max-width:430px; margin:0 auto; padding:0 16px; }
      .chat-in { display:flex; align-items:center; gap:10px; padding:9px 9px 9px 16px; border-radius:26px; min-height:46px; }
      .chat-in span { flex:1; color:rgba(242,245,246,.5); font-size:13.5px; }
      .chat-in .cursor { width:1.5px; height:14px; background:#f2f5f6; animation:blink 1s step-end infinite; }
      @keyframes blink { 50% { opacity:0; } }
      .navbar { position:fixed; left:0; right:0; bottom:0; max-width:430px; margin:0 auto; display:flex; gap:4px;
                padding:9px 12px calc(9px + env(safe-area-inset-bottom,0px)); border-radius:0; border-left:0; border-right:0; border-bottom:0; }
      .navbar button { flex:1; min-height:46px; background:transparent; border:0; color:rgba(242,245,246,.45); font:inherit; font-size:10.5px;
                        display:flex; flex-direction:column; align-items:center; justify-content:center; gap:4px; cursor:pointer; }
      .navbar button[aria-current="true"] { color:#f2f5f6; }
      /* Finanças */
      .stack-bar { height:30px; border-radius:15px; overflow:hidden; display:flex; margin-top:14px; background:rgba(255,255,255,.05); }
      .stack-bar > i { display:block; height:100%; }
      .legenda-grid { display:grid; grid-template-columns:1fr 1fr; gap:9px 14px; margin-top:16px; }
      .leg-item { display:flex; align-items:center; gap:8px; font-size:12px; min-width:0; }
      .leg-dot { width:9px; height:9px; border-radius:3px; flex:0 0 auto; }
      .leg-nome { flex:1; color:rgba(242,245,246,.75); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
      .leg-val { color:rgba(242,245,246,.5); }
      .fx-plate { padding:18px; margin-bottom:16px; }
      .fx-line { display:flex; justify-content:space-between; align-items:baseline; margin-top:14px; }
      .fx-line:first-child { margin-top:0; }
      .fx-bar { height:11px; border-radius:6px; background:rgba(255,255,255,.06); overflow:hidden; margin-top:6px; }
      .fx-bar > i { display:block; height:100%; border-radius:6px; }
      .extrato-plate { padding:6px 18px 18px; margin-bottom:16px; }
      .ex-item { display:flex; align-items:center; gap:10px; padding:12px 0; border-bottom:1px solid rgba(255,255,255,.08); font-size:13.5px; }
      .ex-item:last-child { border-bottom:0; }
      .ex-info { flex:1; min-width:0; }
      .ex-desc { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
      .ex-meta { color:rgba(242,245,246,.45); font-size:11.5px; margin-top:2px; }
      .cta3 { display:block; width:100%; text-align:center; margin-top:8px; padding:12px; border-radius:14px; background:rgba(255,255,255,.08);
              border:1px solid rgba(255,255,255,.14); color:#f2f5f6; font:inherit; font-size:13px; min-height:44px; cursor:pointer; }
      .acc-card { margin-bottom:16px; overflow:hidden; cursor:pointer; }
      .acc-head { display:flex; align-items:center; gap:12px; padding:16px 18px; }
      .acc-ico { width:38px; height:38px; border-radius:12px; background:rgba(255,255,255,.08); display:flex; align-items:center; justify-content:center; flex:0 0 auto; }
      .acc-info { flex:1; }
      .acc-titulo { font-size:14px; font-weight:600; }
      .acc-sub { font-size:11.5px; color:rgba(242,245,246,.5); margin-top:1px; }
      .acc-valor { font-size:15px; font-weight:700; }
      .acc-chev { transition:transform .25s ease; color:rgba(242,245,246,.5); }
      .acc-card[data-aberto="true"] .acc-chev { transform:rotate(180deg); }
      .acc-det { max-height:0; overflow:hidden; transition:max-height .28s ease; }
      .acc-card[data-aberto="true"] .acc-det { max-height:420px; }
      .acc-det-in { padding:0 18px 16px; }
      .kv { display:flex; justify-content:space-between; padding:9px 0; font-size:13px; border-top:1px solid rgba(255,255,255,.08); }
      /* Vida */
      .secoes-row { display:flex; gap:12px; overflow-x:auto; padding:2px 2px 6px; scrollbar-width:none; margin-bottom:6px; }
      .secoes-row::-webkit-scrollbar { display:none; }
      .sec-btn { display:flex; flex-direction:column; align-items:center; gap:6px; flex:0 0 auto; cursor:pointer; background:none; border:0; color:inherit; font:inherit; }
      .sec-circ { width:52px; height:52px; border-radius:26px; display:flex; align-items:center; justify-content:center; font-size:14px; font-weight:700; background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.14); }
      .sec-btn[data-atual="true"] .sec-circ { background:rgba(255,255,255,.16); border-color:rgba(255,255,255,.3); }
      .sec-btn span.lbl { font-size:9.5px; color:rgba(242,245,246,.5); max-width:56px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
      .vida-detalhe { padding:20px; margin-top:8px; }
      .vida-detalhe .titulo { font-size:19px; font-weight:700; }
      .vida-detalhe p { font-size:13.5px; line-height:1.5; margin-top:8px; color:rgba(242,245,246,.7); }
      .mini-chart { margin-top:14px; }
      .legenda2 { font-size:10.5px; color:rgba(242,245,246,.42); margin-top:6px; }
    `;
    root.appendChild(style);
    const fundo = document.createElement("div");
    fundo.className = "fundo";
    fundo.innerHTML = `<div class="mancha m1"></div><div class="mancha m2"></div><div class="mancha m3"></div>`;
    root.appendChild(fundo);
    const wrap = document.createElement("div");
    wrap.className = "app";
    root.appendChild(wrap);

    function fmtData(iso) { if (!iso) return "—"; const d = new Date(iso + "T12:00:00"); return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" }); }
    function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
    function iniciais(nome) { return nome.split(" ").map(w => w[0]).slice(0, 2).join("").toUpperCase(); }
    function seedNum(str) { let h = 0; for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0; return h; }

    const catPalette = ["#9FD8E8", "#7FB6D6", "#6294B7", "#8C97A6", "#B6BFC7", "#4F636C"];
    function categoriasAgrupadas() {
      const lista = [...F.por_categoria].sort((a, b) => b.valor - a.valor);
      if (lista.length <= 6) return lista;
      const top = lista.slice(0, 5);
      const outras = lista.slice(5).reduce((s, c) => s + c.valor, 0);
      top.push({ categoria: "Outras", valor: outras });
      return top;
    }

    function lineChartSVG(dias, refValor, refLabel, gid) {
      const w = 294, h = 96, padL = 2, padR = 2, padT = 12, padB = 2;
      const vals = dias.map(d => d.acumulado);
      const max = Math.max(1, ...vals, refValor || 0);
      const n = vals.length;
      const x = i => padL + (n > 1 ? (i / (n - 1)) * (w - padL - padR) : 0);
      const y = v => padT + (1 - v / max) * (h - padT - padB);
      const pts = vals.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
      const area = `${x(0).toFixed(1)},${y(0).toFixed(1)} ${pts} ${x(n - 1).toFixed(1)},${y(0).toFixed(1)}`;
      const refY = refValor ? y(Math.min(refValor, max)).toFixed(1) : null;
      return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="none">
        <defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff" stop-opacity=".5"/><stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient></defs>
        <text x="${padL}" y="10" font-size="9" fill="rgba(242,245,246,.45)">${brl0(max)}</text>
        ${refY ? `<line x1="${padL}" y1="${refY}" x2="${w - padR}" y2="${refY}" stroke="rgba(242,245,246,.35)" stroke-width="1" stroke-dasharray="3 3"/>
        <text x="${w - padR}" y="${(+refY - 4).toFixed(1)}" text-anchor="end" font-size="9" fill="rgba(242,245,246,.5)">${refLabel}</text>` : ""}
        <polygon points="${area}" fill="url(#${gid})"/>
        <polyline points="${pts}" fill="none" stroke="#f2f5f6" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>
        <circle cx="${x(n - 1).toFixed(1)}" cy="${y(vals[n - 1]).toFixed(1)}" r="3.2" fill="#f2f5f6"/>
      </svg><div class="grafico-legenda"><span>dia 1</span><span>dia ${n}</span></div>`;
    }
    function miniBarSVG(vals) {
      const w = 220, h = 40, gap = 3, n = vals.length, barW = (w - gap * (n - 1)) / n;
      const max = Math.max(1, ...vals);
      const bars = vals.map((v, i) => { const bh = Math.max(2, (v / max) * h); const x = i * (barW + gap); return `<rect x="${x.toFixed(1)}" y="${(h - bh).toFixed(1)}" width="${barW.toFixed(1)}" height="${bh.toFixed(1)}" rx="2" fill="rgba(242,245,246,.55)"/>`; }).join("");
      return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}">${bars}</svg>`;
    }
    function stackBarHTML(cats, total) {
      return `<div class="stack-bar">${cats.map((c, i) => `<i style="width:${Math.max(1, (c.valor / total) * 100)}%;background:${catPalette[i % catPalette.length]}"></i>`).join("")}</div>`;
    }

    function montarChatENav(tela) {
      const chat = document.createElement("div");
      chat.className = "chat-fixo";
      chat.innerHTML = `<div class="chat-in vidro">${svg("chat", 16)}<span>Falar com o painel…</span><span class="cursor"></span></div>`;
      wrap.appendChild(chat);
      const nav = document.createElement("div");
      nav.className = "navbar vidro";
      const itens = [["hoje", "Hoje", "casa"], ["financas", "Finanças", "cartao"], ["vida", "Vida", "vida"]];
      nav.innerHTML = itens.map(([t, label, ic]) => `<button data-t="${t}" aria-current="${t === tela}">${svg(ic, 19)}${label}</button>`).join("");
      wrap.appendChild(nav);
      nav.querySelectorAll("button").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.t)));
    }

    function telaHoje() {
      const now = new Date();
      const hh = String(now.getHours()).padStart(2, "0"), mm = String(now.getMinutes()).padStart(2, "0");
      const dataFmt = cap(new Date(D.hoje.data + "T12:00:00").toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "short" }));
      const dif = F.gasto_mes - F.gasto_mes_anterior;
      wrap.innerHTML = `
        <div class="top">
          <div class="top-info"><div class="hora num">${hh}:${mm}</div><div class="data">${dataFmt} · ${D.hoje.cidade}</div></div>
          <div class="clima">${D.hoje.clima.cond}<br><span class="num">${D.hoje.clima.temp}°C</span> · chuva ${D.hoje.clima.chuva_prob}%</div>
          <button class="mic vidro" aria-label="Comando de voz">${svg("mic", 18)}</button>
        </div>
        ${D.aviso_critico ? `<div class="vidro aviso">${svg("alerta", 20)}<div><b>Aviso</b>${D.aviso_critico}</div></div>` : ""}
        <div class="vidro cartao-grande">
          <div class="rot">Gasto do mês · ${F.mes}</div>
          <div class="valor-grande num">${brl(F.gasto_mes)}</div>
          <div class="comp ${dif <= 0 ? "down" : "up"}">${dif <= 0 ? "▼" : "▲"} ${brl0(Math.abs(dif))} vs. mês anterior</div>
          ${lineChartSVG(F.por_dia_mes, F.gasto_mes_anterior, "mês ant. " + brl0(F.gasto_mes_anterior), "gA")}
          <div class="chip3-row">
            <div class="chip3"><div class="r">Hoje</div><div class="v num">${brl(F.gasto_hoje)}</div></div>
            <div class="chip3"><div class="r">Fatura</div><div class="v num">${brl(F.fatura_atual)}</div></div>
            <div class="chip3"><div class="r">Conta</div><div class="v num">${brl(F.saldo_conta)}</div></div>
          </div>
        </div>
        <div class="secao-titulo">Em foco agora</div>
        <div class="vidro foco-card">${T.em_foco}</div>
        <div class="pill-row">
          <button class="pill" data-ir="financas">${svg("cartao", 16)} Finanças</button>
          <button class="pill" data-ir="vida">${svg("vida", 16)} Vida</button>
        </div>`;
      wrap.querySelectorAll("[data-ir]").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.ir)));
      montarChatENav("hoje");
    }

    function telaFinancas() {
      const cats = categoriasAgrupadas();
      const total = cats.reduce((s, c) => s + c.valor, 0) || 1;
      const dif = F.gasto_mes - F.gasto_mes_anterior;
      const maxFC = Math.max(F.fatura_atual, F.saldo_conta, 1);
      const pFat = Math.max(3, (F.fatura_atual / maxFC) * 100), pConta = Math.max(3, (F.saldo_conta / maxFC) * 100);
      const critico = F.saldo_conta < F.fatura_atual * 0.15;
      const assinTotal = F.assinaturas.reduce((s, a) => s + a.valor, 0);
      wrap.innerHTML = `
        <div class="vidro cartao-grande">
          <div class="rot">Gasto do mês · ${F.mes}</div>
          <div class="valor-grande num">${brl(F.gasto_mes)}</div>
          <div class="comp ${dif <= 0 ? "down" : "up"}">${dif <= 0 ? "▼" : "▲"} ${brl0(Math.abs(dif))} vs. ${brl0(F.gasto_mes_anterior)}</div>
        </div>
        <div class="secao-titulo">Gasto por categoria</div>
        <div class="vidro cartao-grande">
          ${stackBarHTML(cats, total)}
          <div class="legenda-grid">${cats.map((c, i) => `<div class="leg-item"><span class="leg-dot" style="background:${catPalette[i % catPalette.length]}"></span><span class="leg-nome">${c.categoria}</span><span class="leg-val num">${brl0(c.valor)}</span></div>`).join("")}</div>
        </div>
        <div class="secao-titulo">Evolução do mês</div>
        <div class="vidro cartao-grande">${lineChartSVG(F.por_dia_mes, F.gasto_mes_anterior, "mês ant. " + brl0(F.gasto_mes_anterior), "gB")}</div>
        <div class="secao-titulo">Fatura x conta</div>
        <div class="vidro fx-plate">
          <div class="fx-line"><span class="fraco">Fatura · vence ${fmtData(F.fatura_vencimento)}</span><span class="num" style="font-weight:700">${brl(F.fatura_atual)}</span></div>
          <div class="fx-bar"><i style="width:${pFat}%;background:#f2f5f6"></i></div>
          <div class="fx-line"><span class="fraco">Saldo em conta</span><span class="num" style="font-weight:700;color:${critico ? "#e8a37e" : "#f2f5f6"}">${brl(F.saldo_conta)}</span></div>
          <div class="fx-bar"><i style="width:${pConta}%;background:${critico ? "#e8a37e" : "#8fd6c1"}"></i></div>
        </div>
        <div class="secao-titulo">Últimos 15 dias</div>
        <div class="vidro extrato-plate"><div id="lista-extrato"></div>
          <button class="cta3" id="btn-mais">Ver todo o extrato</button>
        </div>
        <div class="secao-titulo">Assinaturas</div>
        <div class="vidro acc-card" data-aberto="false">
          <div class="acc-head"><div class="acc-ico">${svg("cartao", 18)}</div>
            <div class="acc-info"><div class="acc-titulo">Assinaturas ativas</div><div class="acc-sub">${F.assinaturas.length} recorrências</div></div>
            <div class="acc-valor num">${brl(assinTotal)}</div><div class="acc-chev">${svg("chevron", 16)}</div></div>
          <div class="acc-det"><div class="acc-det-in">${F.assinaturas.map(a => `<div class="kv"><span class="fraco">${a.nome} · próx. ${fmtData(a.proxima)}</span><span class="num">${brl(a.valor)}</span></div>`).join("")}</div></div>
        </div>`;
      function renderExtrato(qtd) {
        wrap.querySelector("#lista-extrato").innerHTML = F.ultimos_15_dias.slice(0, qtd).map(t => `
          <div class="ex-item"><div class="ex-info"><div class="ex-desc">${t.descricao}</div><div class="ex-meta">${fmtData(t.data)} · ${t.categoria}</div></div>
          <div class="num" style="font-weight:600">${brl(t.valor)}</div></div>`).join("");
      }
      renderExtrato(6);
      const btnMais = wrap.querySelector("#btn-mais");
      if (F.ultimos_15_dias.length > 6) { btnMais.addEventListener("click", () => { renderExtrato(F.ultimos_15_dias.length); btnMais.remove(); }); }
      else btnMais.remove();
      const acc = wrap.querySelector(".acc-card");
      acc.querySelector(".acc-head").addEventListener("click", () => acc.setAttribute("data-aberto", acc.getAttribute("data-aberto") === "true" ? "false" : "true"));
      montarChatENav("financas");
    }

    function telaVida() {
      wrap.innerHTML = `
        <div class="secao-titulo" style="margin-top:2px">Vida · ${D.vida_secoes.length} seções</div>
        <div class="secoes-row" id="secoes"></div>
        <div class="vidro vida-detalhe" id="detalhe"></div>`;
      const row = wrap.querySelector("#secoes");
      let atual = 0;
      D.vida_secoes.forEach((s, i) => {
        const b = document.createElement("button");
        b.className = "sec-btn"; b.dataset.i = i; b.setAttribute("data-atual", i === 0);
        b.innerHTML = `<div class="sec-circ">${iniciais(s.nome)}</div><span class="lbl">${s.nome}</span>`;
        b.addEventListener("click", () => abrir(i));
        row.appendChild(b);
      });
      function abrir(i) {
        atual = i;
        row.querySelectorAll(".sec-btn").forEach(el => el.setAttribute("data-atual", String(Number(el.dataset.i) === i)));
        const s = D.vida_secoes[i];
        let extra = `<p>${1 + (s.id.length % 4)} itens ativos nesta seção.</p>`;
        let chart;
        if (s.id === "viagens" && D.viagem) {
          extra = `<p>Próxima viagem: ${D.viagem.origem} → ${D.viagem.destino} (${fmtData(D.viagem.data)}).</p>`;
          const pct = Math.max(6, 100 - Math.min(100, (D.viagem.dias_faltando / 30) * 100));
          chart = `<div class="mini-chart"><div class="fx-bar"><i style="width:${pct}%;background:#f2f5f6"></i></div><div class="legenda2">${D.viagem.dias_faltando} dias até o embarque</div></div>`;
        } else {
          const seed = seedNum(s.id);
          const vals = Array.from({ length: 7 }, (_, k) => 2 + ((seed >> (k * 3)) % 9));
          chart = `<div class="mini-chart">${miniBarSVG(vals)}<div class="legenda2">Atividade da semana (exemplo) · seg–dom</div></div>`;
        }
        const det = wrap.querySelector("#detalhe");
        det.innerHTML = `<div class="titulo">${s.nome}</div><p class="fraco">${s.resumo}</p>${extra}${chart}`;
      }
      abrir(0);
      montarChatENav("vida");
    }

    if (ctx.tela === "hoje") telaHoje();
    else if (ctx.tela === "financas") telaFinancas();
    else telaVida();

    return () => { timers.forEach(clearInterval); };
  }
};
