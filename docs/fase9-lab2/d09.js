(window.DIRECOES = window.DIRECOES || {})[9] = {
  nome: "Caderno",
  ideia: "Bullet journal de verdade: letra manuscrita, papel pontilhado, categorias marca-texto, abas na lateral.",
  acento: "#E8B400",
  fontes: ["Kalam:wght@400;700", "Inter:wght@400;600;700"],
  render(root, D, ctx) {
    const F = D.financas;
    const brl = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
    const brl0 = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(v);
    const esc = s => String(s).replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
    const INK = "#1D2B53", INKFADE = "#5b6b91", PAPER = "#FBF6EA", MARK = "#FFD60A";
    const MARKERS = ["#FFD966", "#FF9EB5", "#9BE39D", "#8FD3F4", "#FFC08A", "#C7A6F7"];

    function mulberry32(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
    function seedOf(str) { let h = 0; for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0; return h; }
    function jaggedPoly(x, y, w, h, seed) {
      const rnd = mulberry32(seed); const j = () => (rnd() - 0.5) * 4;
      const pts = [[x + j(), y + j()], [x + w + j(), y + j()], [x + w + j(), y + h + j()], [x + j(), y + h + j()]];
      return pts.map(p => `${p[0].toFixed(1)}px ${p[1].toFixed(1)}px`).join(",");
    }

    const style = document.createElement("style");
    style.textContent = `
      :host, * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
      :host { display:block; height:760px; }
      .app { height:100%; position:relative; background:${PAPER};
        background-image: radial-gradient(circle, rgba(29,43,83,.16) 1px, transparent 1px);
        background-size: 18px 18px; color:${INK}; font-family:'Kalam', cursive; overflow:hidden; }
      .margin { position:absolute; top:0; bottom:0; left:40px; width:1.5px; background:rgba(200,60,70,.35); }
      .holes { position:absolute; top:0; bottom:0; left:14px; width:10px; display:flex; flex-direction:column; justify-content:space-evenly; padding:40px 0; }
      .holes i { width:9px; height:9px; border-radius:50%; background:${PAPER}; border:1.5px solid rgba(29,43,83,.25); box-shadow: inset 0 0 0 3px ${PAPER}; }
      .scroll { position:absolute; inset:0; overflow-y:auto; -webkit-overflow-scrolling:touch; padding:18px 16px 108px 50px; }
      .scroll.withtabs { padding-right:56px; }
      h1.pg { font-family:'Kalam'; font-weight:700; font-size:26px; margin:0 0 2px; color:${INK}; transform:rotate(-0.6deg); }
      .datehead { font-family:'Inter'; font-size:12px; color:${INKFADE}; margin-bottom:14px; display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
      .datehead b { color:${INK}; font-weight:600; }
      .mic { width:44px; height:44px; border-radius:50%; background:transparent; border:2px solid ${INK}; display:flex; align-items:center; justify-content:center; flex:none; margin-left:auto; }
      .sticky { background:#FFF3B0; border:1px solid rgba(29,43,83,.15); padding:10px 12px 10px 14px; margin:0 0 16px; transform:rotate(-1.1deg); font-family:'Inter'; font-size:13.5px; color:#5c4a00; position:relative; box-shadow:1px 2px 0 rgba(29,43,83,.08); }
      .sticky:before { content:""; position:absolute; top:-7px; left:20px; width:34px; height:14px; background:rgba(180,190,255,.55); transform:rotate(-3deg); }
      .card { background:rgba(255,255,255,.35); border:1.5px solid rgba(29,43,83,.18); border-radius:2px; padding:14px; margin-bottom:18px; position:relative; }
      .cardTitle { font-family:'Kalam'; font-weight:700; font-size:18px; margin:0 0 10px; color:${INK}; }
      .num { font-family:'Inter'; font-variant-numeric:tabular-nums; }
      .heroNum { font-family:'Inter'; font-weight:700; font-size:28px; font-variant-numeric:tabular-nums; color:${INK}; }
      .heroDelta { font-family:'Inter'; font-size:13px; font-weight:600; }
      .up { color:#B23A48; } .down { color:#2E7D46; }
      .capline { font-family:'Inter'; font-size:12px; color:${INKFADE}; margin-top:4px; }
      .rapid { list-style:none; margin:0; padding:0; }
      .rapid li { display:flex; align-items:baseline; gap:8px; padding:6px 0; border-bottom:1px dashed rgba(29,43,83,.22); font-family:'Inter'; font-size:13.5px; }
      .rapid li:last-child { border-bottom:none; }
      .bul { font-family:'Kalam'; font-weight:700; width:14px; flex:none; color:${INK}; font-size:16px; }
      .rapid .txt { flex:1; }
      .rapid .val { font-variant-numeric:tabular-nums; color:${INKFADE}; }
      .table3 { font-family:'Inter'; font-size:13.5px; }
      .t3row { display:flex; justify-content:space-between; padding:7px 0; border-bottom:1px dashed rgba(29,43,83,.25); }
      .t3row:last-child { border-bottom:none; }
      .t3row b { font-weight:600; }
      .catrow { margin-bottom:10px; }
      .catlabel { font-family:'Kalam'; font-size:14.5px; margin-bottom:2px; display:flex; justify-content:space-between; }
      .catlabel .v { font-family:'Inter'; font-weight:700; font-size:12.5px; }
      .markbar { height:16px; position:relative; }
      .markfill { position:absolute; left:0; top:2px; height:12px; }
      .shortcuts { display:flex; gap:10px; margin-bottom:6px; flex-wrap:wrap; }
      .scbtn { border:2px solid ${INK}; background:transparent; border-radius:50%; width:56px; height:56px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:2px; font-family:'Kalam'; font-size:10.5px; color:${INK}; }
      .chatbar { position:absolute; left:0; right:0; bottom:52px; padding:8px 14px; display:flex; align-items:center; gap:8px; background:${PAPER}; border-top:1.5px dashed rgba(29,43,83,.3); }
      .chatinput { flex:1; height:34px; border:1.5px solid ${INK}; border-radius:3px; display:flex; align-items:center; padding:0 12px; color:${INKFADE}; font-family:'Kalam'; font-size:14px; background:#fff8e6; }
      .pencil { width:34px; height:34px; border-radius:50%; border:1.5px solid ${INK}; display:flex; align-items:center; justify-content:center; background:transparent; flex:none; }
      .navtab { position:absolute; left:0; right:0; bottom:0; height:52px; display:flex; background:${PAPER}; border-top:1.5px solid ${INK}; }
      .navtab button { flex:1; border:none; background:transparent; font-family:'Kalam'; font-weight:700; font-size:14px; color:${INKFADE}; min-height:44px; }
      .navtab button.on { color:${INK}; text-decoration:underline wavy ${MARK} 2px; text-underline-offset:4px; }
      .washi { display:flex; flex-direction:column; gap:10px; }
      .wrow { display:flex; align-items:center; gap:10px; }
      .wlbl { width:64px; flex:none; font-family:'Kalam'; font-size:14.5px; }
      .wbar { flex:1; height:22px; background:repeating-linear-gradient(45deg, rgba(255,255,255,.5) 0 6px, rgba(255,255,255,.15) 6px 12px); border:1.5px solid rgba(29,43,83,.3); position:relative; }
      .wval { width:88px; text-align:right; flex:none; font-family:'Inter'; font-size:12.5px; font-variant-numeric:tabular-nums; }
      .more { font-family:'Kalam'; font-weight:700; color:${INK}; background:none; border:none; font-size:15px; padding:8px 0; }
      .foldtab { font-family:'Kalam'; font-weight:700; font-size:15px; display:flex; justify-content:space-between; align-items:center; cursor:pointer; }
      .expand { max-height:0; overflow:hidden; transition:max-height .25s ease; }
      .expand.open { max-height:600px; margin-top:8px; }
      .sublist { font-family:'Inter'; font-size:13px; }
      .sublist div { display:flex; justify-content:space-between; padding:5px 0; border-bottom:1px dotted rgba(29,43,83,.25); }
      .sidetabs { position:absolute; top:0; right:0; bottom:52px; width:44px; overflow-y:auto; display:flex; flex-direction:column; padding-top:14px; gap:6px; -webkit-overflow-scrolling:touch; }
      .sidetabs::-webkit-scrollbar { display:none; }
      .tab { flex:none; min-height:38px; border:none; border-radius:6px 0 0 6px; display:flex; align-items:center; justify-content:center; padding:6px 4px; font-family:'Kalam'; font-weight:700; font-size:10px; color:#3a2d00; writing-mode:vertical-rl; text-orientation:mixed; white-space:nowrap; }
      .tab.on { outline:2px solid ${INK}; outline-offset:-2px; }
      .vidaMain { padding-right:6px; }
      .arrow { color:${INKFADE}; font-family:'Kalam'; font-size:14px; }
      .habitrow { display:flex; gap:5px; margin-top:8px; }
      .hsq { width:22px; height:22px; border:1.5px solid ${INK}; border-radius:3px; }
      .exemplo { font-family:'Inter'; font-size:10.5px; color:${INKFADE}; margin-top:6px; font-style:italic; }
    `;
    const wrap = document.createElement("div");
    wrap.className = "app";
    wrap.innerHTML = `<div class="margin"></div><div class="holes"><i></i><i></i><i></i><i></i><i></i></div>`;
    root.append(style, wrap);

    function wobblePath(pts, rnd, amt) {
      const j = () => (rnd() - 0.5) * 2 * amt;
      const wp = pts.map(p => [p[0] + j(), p[1] + j()]);
      return wp.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
    }
    function sketchLine(vals, w, h, seedStr, opts) {
      opts = opts || {};
      const pad = { l: 22, r: 6, t: 8, b: 18 };
      const iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;
      const max = Math.max(1, ...vals) * 1.1;
      const n = vals.length;
      const pts = vals.map((v, i) => [pad.l + (n === 1 ? 0 : (i / (n - 1)) * iw), pad.t + ih - (v / max) * ih]);
      const r1 = mulberry32(seedOf(seedStr + "a")), r2 = mulberry32(seedOf(seedStr + "b"));
      const p1 = wobblePath(pts, r1, opts.amt || 1.4), p2 = wobblePath(pts, r2, opts.amt || 1.4);
      let grid = "";
      if (opts.grid) {
        for (let i = 0; i <= 4; i++) { const y = pad.t + ih * i / 4; grid += `<line x1="${pad.l}" y1="${y.toFixed(1)}" x2="${w - pad.r}" y2="${y.toFixed(1)}" stroke="rgba(29,43,83,.12)" stroke-width="1"/>`; }
        grid += `<text x="0" y="${pad.t + 4}" font-size="9" font-family="Inter" fill="${INKFADE}">${brl0(max)}</text>`;
      }
      const last = pts[pts.length - 1];
      return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
        ${grid}
        <path d="${p1}" fill="none" stroke="${INK}" stroke-width="1.6" stroke-opacity=".55" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="${p2}" fill="none" stroke="${INK}" stroke-width="1.6" stroke-opacity=".85" stroke-linecap="round" stroke-linejoin="round"/>
        ${pts.map(p => `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="2" fill="${MARK}" stroke="${INK}" stroke-width="1"/>`).join("")}
        <circle cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="3.4" fill="${INK}"/>
        <text x="${pad.l}" y="${h}" font-size="9.5" font-family="Inter" fill="${INKFADE}">1</text>
        <text x="${w - pad.r}" y="${h}" font-size="9.5" font-family="Inter" fill="${INKFADE}" text-anchor="end">${n}</text>
      </svg>`;
    }

    const iconMic = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="${INK}" stroke-width="1.8"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/></svg>`;
    const iconSun = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="${INK}" stroke-width="1.6"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>`;
    const iconPencil = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="${INK}" stroke-width="1.8"><path d="M4 20l1-4L16 5l3 3L8 19l-4 1z"/></svg>`;

    function pageShell(title) {
      const scroll = document.createElement("div"); scroll.className = "scroll";
      const h1 = document.createElement("h1"); h1.className = "pg"; h1.textContent = title;
      scroll.appendChild(h1);
      wrap.appendChild(scroll);
      return scroll;
    }
    function tabbar(active) {
      const tb = document.createElement("div"); tb.className = "navtab";
      [["hoje", "hoje"], ["financas", "finanças"], ["vida", "vida"]].forEach(([id, label]) => {
        const b = document.createElement("button"); b.textContent = label;
        if (id === active) b.classList.add("on");
        b.onclick = () => ctx.irPara(id);
        tb.appendChild(b);
      });
      wrap.appendChild(tb);
    }

    function screenHoje() {
      const scroll = pageShell(D.hoje.data.split("-").reverse().join("/"));
      const dataFmt = new Date(D.hoje.data + "T00:00:00").toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });
      const now = new Date(); const hh = String(now.getHours()).padStart(2, "0"), mm = String(now.getMinutes()).padStart(2, "0");
      const dh = document.createElement("div"); dh.className = "datehead";
      dh.innerHTML = `<b>${esc(dataFmt)}</b> · <span class="num">${hh}:${mm}</span> · ${iconSun} ${D.hoje.clima.temp}°C, ${esc(D.hoje.clima.cond)} (${D.hoje.clima.chuva_prob}% chuva) · ${esc(D.hoje.cidade)}`;
      const mic = document.createElement("button"); mic.className = "mic"; mic.setAttribute("aria-label", "Falar"); mic.innerHTML = iconMic; dh.appendChild(mic);
      scroll.appendChild(dh);

      if (D.aviso_critico) {
        const s = document.createElement("div"); s.className = "sticky"; s.textContent = "⚠ " + D.aviso_critico;
        scroll.appendChild(s);
      }

      const dias = F.por_dia_mes.map(p => p.acumulado);
      const gc = document.createElement("div"); gc.className = "card";
      gc.innerHTML = `<div class="cardTitle">gastos do mês</div><div class="heroNum">${brl(F.gasto_mes)}</div>` + sketchLine(dias, 300, 70, "hoje-mes", {});
      scroll.appendChild(gc);

      const t3 = document.createElement("div"); t3.className = "card table3";
      t3.innerHTML = `<div class="cardTitle" style="margin-bottom:6px">hoje · fatura · conta</div>
        <div class="t3row"><span>gasto hoje</span><b>${brl(F.gasto_hoje)}</b></div>
        <div class="t3row"><span>fatura (${F.fatura_vencimento})</span><b>${brl(F.fatura_atual)}</b></div>
        <div class="t3row"><span>saldo em conta</span><b>${brl(F.saldo_conta)}</b></div>`;
      scroll.appendChild(t3);

      const foco = document.createElement("div"); foco.className = "card";
      const pend = (D.tarefas.pendentes || []).slice(0, 2);
      foco.innerHTML = `<div class="cardTitle">rapid log</div><ul class="rapid">
        <li><span class="bul">&gt;</span><span class="txt">${esc(D.tarefas.em_foco)}</span><span class="val">foco</span></li>
        ${pend.map(p => `<li><span class="bul">•</span><span class="txt">${esc(p.titulo)}</span><span class="val">${esc(p.quando)}</span></li>`).join("")}
      </ul>`;
      scroll.appendChild(foco);

      const scTitle = document.createElement("div"); scTitle.style.cssText = "font-family:'Kalam';font-weight:700;font-size:15px;margin:0 0 8px";
      scTitle.textContent = "atalhos";
      scroll.appendChild(scTitle);
      const scGrid = document.createElement("div"); scGrid.className = "shortcuts";
      [["finanças", () => ctx.irPara("financas")], ["vida", () => ctx.irPara("vida")], ["tarefas", null], ["aviação", null]].forEach(([label, fn]) => {
        const b = document.createElement("button"); b.className = "scbtn"; b.textContent = label;
        if (fn) b.onclick = fn;
        scGrid.appendChild(b);
      });
      scroll.appendChild(scGrid);

      const chat = document.createElement("div"); chat.className = "chatbar";
      chat.innerHTML = `<div class="chatinput">anota aí…</div><button class="pencil">${iconPencil}</button>`;
      wrap.appendChild(chat);
      tabbar("hoje");
    }

    function screenFinancas() {
      const scroll = pageShell("financeiro do mês");
      const dif = F.gasto_mes - F.gasto_mes_anterior;
      const resumo = document.createElement("div"); resumo.className = "card";
      resumo.innerHTML = `<div class="cardTitle">resumo</div><div class="heroNum">${brl(F.gasto_mes)}</div>
        <div class="heroDelta ${dif <= 0 ? "down" : "up"}">${dif <= 0 ? "↓" : "↑"} ${brl0(Math.abs(dif))} vs mês passado (${brl0(F.gasto_mes_anterior)})</div>
        <div class="capline">${F.orcamento_mes ? "orçamento: " + brl0(F.orcamento_mes) : "sem orçamento definido ainda"}</div>`;
      scroll.appendChild(resumo);

      const dias = F.por_dia_mes.map(p => p.acumulado);
      const evo = document.createElement("div"); evo.className = "card";
      evo.innerHTML = `<div class="cardTitle">evolução por dia</div>` + sketchLine(dias, 300, 110, "fin-evo", { grid: true, amt: 1.1 });
      scroll.appendChild(evo);

      const maxCat = Math.max(...F.por_categoria.map(c => c.valor));
      const cat = document.createElement("div"); cat.className = "card";
      cat.innerHTML = `<div class="cardTitle">gasto por categoria</div>` + F.por_categoria.map((c, i) => {
        const pct = Math.max(6, (c.valor / maxCat) * 100);
        const col = MARKERS[i % MARKERS.length];
        const clip = jaggedPoly(0, 0, pct, 12, seedOf(c.categoria));
        return `<div class="catrow"><div class="catlabel"><span>${esc(c.categoria)}</span><span class="v">${brl(c.valor)}</span></div>
          <div class="markbar"><div class="markfill" style="width:${pct.toFixed(1)}%;background:${col};clip-path:polygon(${clip});opacity:.75"></div></div></div>`;
      }).join("");
      scroll.appendChild(cat);

      const maxFC = Math.max(F.fatura_atual, F.saldo_conta, 1);
      const washi = document.createElement("div"); washi.className = "card";
      washi.innerHTML = `<div class="cardTitle">fatura x conta</div><div class="washi">
        <div class="wrow"><span class="wlbl">fatura</span><div class="wbar"><div style="position:absolute;inset:0;width:${(F.fatura_atual / maxFC * 100).toFixed(1)}%;background:${MARKERS[4]};opacity:.8"></div></div><span class="wval">${brl(F.fatura_atual)}</span></div>
        <div class="wrow"><span class="wlbl">conta</span><div class="wbar"><div style="position:absolute;inset:0;width:${(F.saldo_conta / maxFC * 100).toFixed(1)}%;background:${F.saldo_conta < F.fatura_atual ? "#E86A6A" : MARKERS[2]};opacity:.85"></div></div><span class="wval">${brl(F.saldo_conta)}</span></div>
      </div>`;
      scroll.appendChild(washi);

      const ult = document.createElement("div"); ult.className = "card";
      ult.innerHTML = `<div class="cardTitle">últimos 15 dias</div>`;
      const list = document.createElement("ul"); list.className = "rapid"; ult.appendChild(list); scroll.appendChild(ult);
      function renderList(items) {
        list.innerHTML = items.map(t => `<li><span class="bul">•</span><span class="txt">${esc(t.descricao)} <span style="color:${INKFADE}">· ${esc(t.categoria)}</span></span><span class="val">${brl(t.valor)}</span></li>`).join("");
      }
      renderList(F.ultimos_15_dias.slice(0, 6));
      if (F.ultimos_15_dias.length > 6) {
        const more = document.createElement("button"); more.className = "more"; more.textContent = "ver mais ↓";
        more.onclick = () => { renderList(F.ultimos_15_dias); more.remove(); };
        ult.appendChild(more);
      }

      const sub = document.createElement("div"); sub.className = "card";
      const fold = document.createElement("div"); fold.className = "foldtab";
      fold.innerHTML = `<span>assinaturas (${F.assinaturas.length})</span><span class="arrow">toque ▾</span>`;
      const subBody = document.createElement("div"); subBody.className = "expand sublist";
      subBody.innerHTML = F.assinaturas.map(s => `<div><span>${esc(s.nome)}</span><span class="num">${brl(s.valor)} · ${s.proxima}</span></div>`).join("");
      fold.onclick = () => subBody.classList.toggle("open");
      sub.append(fold, subBody); scroll.appendChild(sub);

      tabbar("financas");
    }

    function screenVida() {
      const scroll = pageShell("vida");
      scroll.classList.add("withtabs");
      const main = document.createElement("div"); main.className = "vidaMain card";
      main.innerHTML = `<div class="cardTitle" style="margin-bottom:6px">toque numa aba <span class="arrow">→</span></div><div class="capline">18 seções da vida, cada uma numa aba colorida ao lado.</div>`;
      scroll.appendChild(main);

      const tabs = document.createElement("div"); tabs.className = "sidetabs";
      wrap.appendChild(tabs);
      D.vida_secoes.forEach((s, i) => {
        const t = document.createElement("button"); t.className = "tab";
        t.style.background = MARKERS[i % MARKERS.length];
        t.textContent = s.nome;
        t.onclick = () => {
          tabs.querySelectorAll(".tab").forEach(x => x.classList.remove("on"));
          t.classList.add("on");
          const rnd = mulberry32(seedOf(s.id));
          const filled = Array.from({ length: 7 }, () => rnd() > 0.4);
          let extra = "";
          if (s.id === "viagens" && D.viagem) extra = `<div class="capline"><b>${esc(D.viagem.origem)} → ${esc(D.viagem.destino)}</b> · faltam ${D.viagem.dias_faltando}d (${D.viagem.data})</div>`;
          main.innerHTML = `<div class="cardTitle" style="margin-bottom:4px">${esc(s.nome)}</div><div class="capline" style="font-size:13.5px">${esc(s.resumo)}</div>${extra}
            <div class="capline" style="margin-top:10px">sequência (exemplo)</div>
            <div class="habitrow">${filled.map(f => `<div class="hsq" style="background:${f ? MARKERS[i % MARKERS.length] : "transparent"}"></div>`).join("")}</div>
            <div class="exemplo">dado de exemplo — sem histórico real desta seção</div>`;
        };
        tabs.appendChild(t);
      });
      tabbar("vida");
    }

    if (ctx.tela === "hoje") screenHoje();
    else if (ctx.tela === "financas") screenFinancas();
    else screenVida();

    return () => {};
  }
};
