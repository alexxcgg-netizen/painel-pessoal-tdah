(window.DIRECOES = window.DIRECOES || {})[16] = {
  nome: "Colunas",
  ideia: "Quadro Kanban: colunas horizontais com scroll-snap, uma por área; pontinhos indicam a página.",
  acento: "#BF5AF2",
  fontes: ["Inter:wght@400;500;600;700"],
  render(root, D, ctx) {
    const F = D.financas;
    const brl = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
    const brl0 = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(v);
    const esc = s => String(s).replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
    const AC = "#BF5AF2";
    const CATC = ["#5AC8FA", "#FF9F0A", "#32D74B", "#FF453A", "#FFD60A", "#64D2FF"];

    function mulberry32(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
    function seedOf(str) { let h = 0; for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0; return h; }

    const style = document.createElement("style");
    style.textContent = `
      :host, * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
      :host { display:block; height:760px; }
      .app { font-family: Inter, system-ui, sans-serif; background:#000; color:#fff; height:100%; position:relative; overflow:hidden; display:flex; flex-direction:column; }
      .hdr { display:flex; align-items:center; justify-content:space-between; padding:14px 16px 10px; flex:none; }
      .hdr h1 { font-size:20px; font-weight:700; margin:0; letter-spacing:-.01em; }
      .mic { width:44px; height:44px; border-radius:22px; background:#17171A; border:1px solid #2A2A2E; display:flex; align-items:center; justify-content:center; flex:none; }
      .mic svg { stroke:${AC}; }
      .alertbar { margin:0 16px 10px; padding:10px 12px; background:#2A1420; border:1px solid #4A1F32; border-radius:10px; display:flex; align-items:center; gap:8px; font-size:13px; color:#FF9FC0; flex:none; }
      .board { display:flex; gap:12px; overflow-x:auto; scroll-snap-type:x mandatory; -webkit-overflow-scrolling:touch; padding:2px 16px 10px; flex:1; align-items:flex-start; min-height:0; }
      .board::-webkit-scrollbar { display:none; }
      .col { flex:0 0 80%; max-width:300px; scroll-snap-align:start; background:#17171A; border:1px solid #262629; border-radius:16px; padding:14px; display:flex; flex-direction:column; max-height:100%; }
      .colHead { flex:none; margin-bottom:10px; }
      .colHead .lbl { font-size:11px; text-transform:uppercase; letter-spacing:.08em; color:#8E8E93; font-weight:600; }
      .colHead .big { font-size:22px; font-weight:700; font-variant-numeric:tabular-nums; margin-top:2px; }
      .colHead .topbar { height:5px; border-radius:3px; background:#242428; margin-top:8px; overflow:hidden; }
      .colHead .topbar i { display:block; height:100%; border-radius:3px; }
      .colBody { flex:1; overflow-y:auto; display:flex; flex-direction:column; gap:8px; min-height:0; }
      .cardline { background:#1F1F23; border-radius:10px; padding:10px 11px; }
      .cardline .t { font-size:13.5px; font-weight:500; }
      .cardline .s { font-size:11.5px; color:#8E8E93; margin-top:2px; }
      .cardline .v { font-size:13px; font-variant-numeric:tabular-nums; color:#D9D9DE; margin-top:4px; }
      .rowmini { display:flex; justify-content:space-between; align-items:center; font-size:12.5px; padding:7px 0; border-top:1px solid #232327; }
      .rowmini:first-child { border-top:none; }
      .rowmini .k { color:#8E8E93; }
      .rowmini .v { font-variant-numeric:tabular-nums; font-weight:600; }
      .pill { display:inline-flex; align-items:center; justify-content:center; gap:6px; background:${AC}; color:#1a0b22; font-weight:600; font-size:13px; border:none; border-radius:20px; padding:0 14px; height:38px; margin-top:4px; }
      .dots { display:flex; justify-content:center; gap:5px; padding:2px 0 10px; flex:none; flex-wrap:wrap; }
      .dot { width:5px; height:5px; border-radius:50%; background:#3A3A3E; }
      .dot.on { background:${AC}; width:14px; border-radius:3px; }
      .navtab { display:flex; background:#000; border-top:1px solid #1C1C1E; flex:none; }
      .navtab button { flex:1; border:none; background:transparent; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:2px; color:#8E8E93; font:inherit; min-height:52px; }
      .navtab button.on { color:${AC}; }
      .navtab svg { width:20px; height:20px; }
      .navtab .l { font-size:10px; }
      .legend { display:flex; flex-wrap:wrap; gap:6px 10px; margin-top:8px; }
      .legend .li { display:flex; align-items:center; gap:4px; font-size:10.5px; color:#8E8E93; }
      .dotc { width:7px; height:7px; border-radius:50%; flex:none; }
      .bars { display:flex; flex-direction:column; gap:6px; }
      .brow { display:flex; align-items:center; gap:6px; }
      .brow .n { width:74px; flex:none; font-size:11px; color:#C7C7CC; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
      .brow .tk { display:block; flex:1; height:10px; background:#242428; border-radius:3px; overflow:hidden; }
      .brow .fl { display:block; height:100%; border-radius:3px; }
      .brow .val { width:58px; text-align:right; flex:none; font-size:10.5px; color:#8E8E93; font-variant-numeric:tabular-nums; }
      .expand { max-height:0; overflow:hidden; transition:max-height .25s ease; }
      .expand.open { max-height:400px; margin-top:8px; }
      .exemplo { font-size:10px; color:#636366; margin-top:4px; }
      .toggle { background:#1F1F23; border:none; color:${AC}; font:inherit; font-size:12.5px; font-weight:600; border-radius:10px; padding:10px 11px; text-align:left; }
    `;
    const wrap = document.createElement("div"); wrap.className = "app";
    root.append(style, wrap);

    function lineChart(vals, w, h, color) {
      const pad = { l: 24, r: 4, t: 6, b: 14 };
      const iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;
      const max = Math.max(1, ...vals) * 1.1;
      const n = vals.length;
      const pts = vals.map((v, i) => [pad.l + (n === 1 ? 0 : (i / (n - 1)) * iw), pad.t + ih - (v / max) * ih]);
      const line = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
      const area = line + ` L${pts[pts.length - 1][0].toFixed(1)},${pad.t + ih} L${pts[0][0].toFixed(1)},${pad.t + ih} Z`;
      const gid = "lg" + Math.random().toString(36).slice(2, 8);
      const last = pts[pts.length - 1];
      return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
        <defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="${color}" stop-opacity=".3"/><stop offset="100%" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
        <text x="0" y="${pad.t + 5}" font-size="9" fill="#8E8E93">${brl0(max)}</text>
        <line x1="${pad.l}" y1="${pad.t}" x2="${w - pad.r}" y2="${pad.t}" stroke="#242428" stroke-width="1"/>
        <path d="${area}" fill="url(#${gid})"/>
        <path d="${line}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
        <circle cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="3" fill="${color}"/>
        <text x="${pad.l}" y="${h}" font-size="9" fill="#8E8E93">1</text>
        <text x="${w - pad.r}" y="${h}" font-size="9" fill="#8E8E93" text-anchor="end">${n}</text>
      </svg>`;
    }
    function sparkBars(vals, w, h, color) {
      const n = vals.length, gap = w / n, bw = gap * 0.62;
      const max = Math.max(1, ...vals);
      let s = "";
      vals.forEach((v, i) => { const bh = Math.max(2, (v / max) * h); s += `<rect x="${(i * gap + (gap - bw) / 2).toFixed(1)}" y="${(h - bh).toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" rx="1.5" fill="${color}"/>`; });
      return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">${s}</svg>`;
    }
    function compareBars(a, b, la, lb, ca, cb, w) {
      const max = Math.max(a, b, 1);
      const row = (lbl, val, col) => `<div class="rowmini" style="display:block;padding:8px 0"><div style="display:flex;justify-content:space-between;font-size:11.5px;color:#8E8E93;margin-bottom:4px"><span>${lbl}</span><span class="num">${brl(val)}</span></div><div class="brow"><div class="tk" style="flex:1"><div class="fl" style="width:${(val / max * 100).toFixed(1)}%;background:${col}"></div></div></div></div>`;
      return row(la, a, ca) + row(lb, b, cb);
    }

    const iconMic = `<svg viewBox="0 0 24 24" fill="none" stroke="${AC}" stroke-width="1.8"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/></svg>`;
    const iconWarn = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#FF6FA5" stroke-width="1.8"><path d="M12 3l9 16H3l9-16z"/><path d="M12 10v4"/><circle cx="12" cy="17" r=".6" fill="#FF6FA5"/></svg>`;

    function boardEl(cols) {
      const board = document.createElement("div"); board.className = "board";
      const dots = document.createElement("div"); dots.className = "dots";
      cols.forEach((c, i) => {
        const col = document.createElement("div"); col.className = "col";
        col.appendChild(c);
        board.appendChild(col);
        const d = document.createElement("div"); d.className = "dot" + (i === 0 ? " on" : ""); dots.appendChild(d);
      });
      let raf = null;
      board.addEventListener("scroll", () => {
        if (raf) return;
        raf = requestAnimationFrame(() => {
          raf = null;
          const cw = board.firstChild ? board.firstChild.getBoundingClientRect().width + 12 : 1;
          const idx = Math.round(board.scrollLeft / cw);
          dots.querySelectorAll(".dot").forEach((d, i) => d.classList.toggle("on", i === idx));
        });
      }, { passive: true });
      return { board, dots };
    }
    function colHead(label, big, pct, color) {
      const h = document.createElement("div"); h.className = "colHead";
      h.innerHTML = `<div class="lbl">${esc(label)}</div><div class="big">${big}</div>` + (pct !== undefined ? `<div class="topbar"><i style="width:${Math.max(4, pct)}%;background:${color}"></i></div>` : "");
      return h;
    }
    function body() { const b = document.createElement("div"); b.className = "colBody"; return b; }

    function tabbar(active) {
      const tb = document.createElement("div"); tb.className = "navtab";
      const defs = [["hoje", "Hoje", `<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>`],
      ["financas", "Finanças", `<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8"><path d="M4 19h16M6 19V10M11 19V5M16 19v-7"/></svg>`],
      ["vida", "Vida", `<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8"><rect x="4" y="4" width="7" height="7" rx="1"/><rect x="13" y="4" width="7" height="7" rx="1"/><rect x="4" y="13" width="7" height="7" rx="1"/><rect x="13" y="13" width="7" height="7" rx="1"/></svg>`]];
      defs.forEach(([id, label, svg]) => {
        const b = document.createElement("button"); if (id === active) b.classList.add("on");
        b.innerHTML = svg + `<span class="l">${label}</span>`;
        b.onclick = () => ctx.irPara(id);
        tb.appendChild(b);
      });
      wrap.appendChild(tb);
    }
    function header(title, mic) {
      const h = document.createElement("div"); h.className = "hdr";
      h.innerHTML = `<h1>${title}</h1>`;
      if (mic) { const m = document.createElement("button"); m.className = "mic"; m.setAttribute("aria-label", "Falar"); m.innerHTML = iconMic; h.appendChild(m); }
      wrap.appendChild(h);
    }

    function screenHoje() {
      header("Hoje", true);
      if (D.aviso_critico) {
        const al = document.createElement("div"); al.className = "alertbar"; al.innerHTML = iconWarn + esc(D.aviso_critico);
        wrap.appendChild(al);
      }
      const now = new Date(); const hh = String(now.getHours()).padStart(2, "0"), mm = String(now.getMinutes()).padStart(2, "0");
      const dataFmt = new Date(D.hoje.data + "T00:00:00").toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });

      const cAgora = colHead("agora", hh + ":" + mm);
      const bAgora = body();
      bAgora.innerHTML = `<div class="cardline"><div class="t">${esc(dataFmt)}</div><div class="s">${esc(D.hoje.cidade)}</div></div>
        <div class="cardline"><div class="t">${esc(D.hoje.clima.cond)}, ${D.hoje.clima.temp}°C</div><div class="s">chuva ${D.hoje.clima.chuva_prob}%</div></div>`;
      const colAgoraWrap = document.createElement("div"); colAgoraWrap.append(cAgora, bAgora);

      const cDin = colHead("dinheiro", brl(F.gasto_mes));
      const bDin = body();
      const dias = F.por_dia_mes.map(p => p.acumulado);
      bDin.innerHTML = `<div class="cardline">${lineChart(dias, 240, 76, AC)}<div class="s">acumulado do mês</div></div>
        <div class="cardline">
          <div class="rowmini"><span class="k">hoje</span><span class="v">${brl(F.gasto_hoje)}</span></div>
          <div class="rowmini"><span class="k">fatura</span><span class="v">${brl(F.fatura_atual)}</span></div>
          <div class="rowmini"><span class="k">conta</span><span class="v">${brl(F.saldo_conta)}</span></div>
        </div>`;
      const btnFin = document.createElement("button"); btnFin.className = "pill"; btnFin.textContent = "abrir finanças →"; btnFin.onclick = () => ctx.irPara("financas");
      const colDinWrap = document.createElement("div"); colDinWrap.append(cDin, bDin, btnFin);

      const cTar = colHead("tarefas", esc(D.tarefas.em_foco).length > 16 ? "" : "");
      cTar.querySelector(".big").style.fontSize = "15px"; cTar.querySelector(".big").textContent = D.tarefas.em_foco;
      const bTar = body();
      bTar.innerHTML = (D.tarefas.pendentes || []).map(p => `<div class="cardline"><div class="t">${esc(p.titulo)}</div><div class="s">${esc(p.quando)}</div></div>`).join("");
      const colTarWrap = document.createElement("div"); colTarWrap.append(cTar, bTar);

      const cVida = colHead("vida", D.vida_secoes.length + " seções");
      const bVida = body();
      bVida.innerHTML = D.vida_secoes.slice(0, 3).map(s => `<div class="cardline"><div class="t">${esc(s.nome)}</div><div class="s">${esc(s.resumo)}</div></div>`).join("");
      const btnVida = document.createElement("button"); btnVida.className = "pill"; btnVida.textContent = "abrir vida →"; btnVida.onclick = () => ctx.irPara("vida");
      const colVidaWrap = document.createElement("div"); colVidaWrap.append(cVida, bVida, btnVida);

      const { board, dots } = boardEl([colAgoraWrap, colDinWrap, colTarWrap, colVidaWrap]);
      wrap.append(board, dots);
      tabbar("hoje");
    }

    function screenFinancas() {
      header("Finanças", false);
      const cols = [];

      const cRes = colHead("resumo", brl(F.gasto_mes));
      const dif = F.gasto_mes - F.gasto_mes_anterior;
      const bRes = body();
      const dias = F.por_dia_mes.map(p => p.acumulado);
      const maxCat = Math.max(...F.por_categoria.map(c => c.valor));
      bRes.innerHTML = `<div class="cardline"><div class="s" style="color:${dif <= 0 ? "#32D74B" : "#FF453A"}">${dif <= 0 ? "▼" : "▲"} ${brl0(Math.abs(dif))} vs mês anterior</div><div class="s">${F.orcamento_mes ? "orçamento " + brl0(F.orcamento_mes) : "sem orçamento definido"}</div></div>
        <div class="cardline"><div class="t" style="margin-bottom:4px">evolução do mês</div>${lineChart(dias, 240, 70, AC)}</div>
        <div class="cardline"><div class="t" style="margin-bottom:6px">por categoria</div><div class="bars">${F.por_categoria.slice(0, 6).map((c, i) => {
        const pct = Math.max(4, c.valor / maxCat * 100); const col = CATC[i % CATC.length];
        return `<div class="brow"><span class="n">${esc(c.categoria)}</span><span class="tk"><span class="fl" style="width:${pct.toFixed(1)}%;background:${col}"></span></span><span class="val">${brl0(c.valor)}</span></div>`;
      }).join("")}</div></div>
        <div class="cardline"><div class="t" style="margin-bottom:2px">fatura x conta</div>${compareBars(F.fatura_atual, F.saldo_conta, "fatura", "conta", "#FF9F0A", F.saldo_conta < F.fatura_atual ? "#FF453A" : "#32D74B", 240)}</div>`;
      const wrapRes = document.createElement("div"); wrapRes.append(cRes, bRes); cols.push(wrapRes);

      F.por_categoria.forEach((c, i) => {
        const pct = Math.max(4, c.valor / maxCat * 100);
        const col = CATC[i % CATC.length];
        const h = colHead(c.categoria, brl(c.valor), pct, col);
        const b = body();
        const compras = F.ultimos_15_dias.filter(t => t.categoria === c.categoria);
        b.innerHTML = compras.length
          ? compras.map(t => `<div class="cardline"><div class="t">${esc(t.descricao)}</div><div class="s">${t.data.slice(5).split("-").reverse().join("/")}</div><div class="v">${brl(t.valor)}</div></div>`).join("")
          : `<div class="cardline"><div class="s">sem compras recentes nesta categoria</div></div>`;
        const w = document.createElement("div"); w.append(h, b); cols.push(w);
      });

      const cExt = colHead("extrato", F.ultimos_15_dias.length + " lançamentos");
      const bExt = body();
      function renderExt(items) { bExt.innerHTML = items.map(t => `<div class="cardline"><div class="t">${esc(t.descricao)}</div><div class="s">${t.data.slice(5).split("-").reverse().join("/")} · ${esc(t.categoria)}</div><div class="v">${brl(t.valor)}</div></div>`).join(""); }
      renderExt(F.ultimos_15_dias.slice(0, 6));
      const wExt = document.createElement("div"); wExt.append(cExt, bExt);
      if (F.ultimos_15_dias.length > 6) {
        const more = document.createElement("button"); more.className = "pill"; more.style.background = "#1F1F23"; more.style.color = AC; more.textContent = "carregar mais";
        more.onclick = () => { renderExt(F.ultimos_15_dias); more.remove(); };
        wExt.appendChild(more);
      }
      cols.push(wExt);

      const cSub = colHead("assinaturas", F.assinaturas.length + " ativas");
      const bSub = body();
      const toggle = document.createElement("button"); toggle.className = "toggle"; toggle.textContent = "toque para ver";
      const list = document.createElement("div"); list.className = "expand";
      list.innerHTML = F.assinaturas.map(s => `<div class="cardline"><div class="t">${esc(s.nome)}</div><div class="s">próxima ${s.proxima}</div><div class="v">${brl(s.valor)}</div></div>`).join("");
      toggle.onclick = () => list.classList.toggle("open");
      bSub.append(toggle, list);
      const wSub = document.createElement("div"); wSub.append(cSub, bSub); cols.push(wSub);

      const { board, dots } = boardEl(cols);
      wrap.append(board, dots);
      tabbar("financas");
    }

    function screenVida() {
      header("Vida", false);
      const cols = [];
      D.vida_secoes.forEach(s => {
        const h = colHead(s.nome, "");
        h.querySelector(".big").remove();
        const b = body();
        const rnd = mulberry32(seedOf(s.id));
        const vals = Array.from({ length: 7 }, () => 0.2 + rnd() * 0.8);
        let extra = "";
        if (s.id === "viagens" && D.viagem) extra = `<div class="cardline"><div class="t">${esc(D.viagem.origem)} → ${esc(D.viagem.destino)}</div><div class="s">faltam ${D.viagem.dias_faltando}d · ${D.viagem.data}</div></div>`;
        b.innerHTML = `<div class="cardline"><div class="s">${esc(s.resumo)}</div>${extra}
          <div class="s" style="margin-top:8px">progresso (exemplo)</div>${sparkBars(vals, 220, 34, AC)}
          <div class="exemplo">dado de exemplo — sem histórico real</div></div>`;
        const w = document.createElement("div"); w.append(h, b); cols.push(w);
      });
      const { board, dots } = boardEl(cols);
      wrap.append(board, dots);
      tabbar("vida");
    }

    if (ctx.tela === "hoje") screenHoje();
    else if (ctx.tela === "financas") screenFinancas();
    else screenVida();

    return () => {};
  }
};
