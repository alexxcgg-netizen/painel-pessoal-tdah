(window.DIRECOES = window.DIRECOES || {})[7] = {
  nome: "Documento",
  ideia: "Página de documento estilo Notion: blocos, callouts, toggles, checklist, tabela.",
  acento: "#2383E2",
  fontes: ["Inter:wght@400;500;600;700"],
  render(root, D, ctx) {
    const brl = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v == null ? 0 : v);
    const fin = D.financas;
    const rafs = [];
    const AC = "#2383E2";

    const ICONS = {
      sun: '<circle cx="12" cy="12" r="4.2"/><path d="M12 3v2.3M12 18.7V21M4.6 4.6l1.6 1.6M17.8 17.8l1.6 1.6M3 12h2.3M18.7 12H21M4.6 19.4l1.6-1.6M17.8 6.2l1.6-1.6"/>',
      chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
      sparkle: '<path d="M12 3l1.6 4.9L18 9.5l-4.4 1.6L12 16l-1.6-4.9L6 9.5l4.4-1.6L12 3Z"/><path d="M5 18l.7 2.1L8 21l-2.3.9L5 24l-.7-2.1L2 21l2.3-.9L5 18Z"/>',
      clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
      cloud: '<path d="M7 18.5a4.5 4.5 0 0 1-.4-9c.6-2.6 2.9-4.5 5.6-4.5 2.9 0 5.3 2.1 5.7 4.9a4 4 0 0 1-.9 7.9H7.2Z"/>',
      mic: '<rect x="9.3" y="3" width="5.4" height="10" rx="2.7"/><path d="M6 11a6 6 0 0 0 12 0M12 17v3.3"/>',
      pin: '<path d="M12 2.8c2.9 0 5.2 2.3 5.2 5.3 0 3.9-5.2 9.7-5.2 9.7S6.8 12 6.8 8.1c0-3 2.3-5.3 5.2-5.3Z"/><circle cx="12" cy="8.1" r="1.9"/>',
      page: '<path d="M6.5 2.5h8l3 3v16h-11Z"/><path d="M14.5 2.5V6h3"/>',
      send: '<path d="M20.5 3.5 3 10.6l6.8 2.6L20.5 3.5Z"/><path d="M9.8 13.2l2.6 6.8 8.1-16.5Z"/>',
      check: '<path d="M5 12.5l4.2 4.2L19 6.5"/>',
      caret: '<path d="M9 6l6 6-6 6"/>',
      chev: '<path d="M6 9l6 6 6-6"/>',
      home: '<path d="M4 11.5 12 4l8 7.5"/><path d="M6 10v10h12V10"/>',
      plane: '<path d="M3 13.5 21 6l-4.5 15-3.4-6.4L3 13.5Z"/><path d="M13.1 14.6 8 12"/>',
      route: '<circle cx="6" cy="6" r="2.3"/><circle cx="18" cy="18" r="2.3"/><path d="M8 6h6a4 4 0 0 1 4 4v.5a4 4 0 0 1-4 4H8"/>'
    };
    const svgIcon = (name, size = 15, stroke = "currentColor", sw = 1.8) =>
      `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="${stroke}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ""}</svg>`;

    const style = document.createElement("style");
    style.textContent = `
      :host, .page * { box-sizing: border-box; }
      .page {
        --bg: #FFFFFF; --soft: #F7F6F3; --text: #37352F; --sub: #5F5E5B;
        --line: #E9E9E7; --ac: ${AC}; --acsoft: rgba(35,131,226,.10); --acsoft2: rgba(35,131,226,.35);
        --warnbg: #FDECEA; --warntx: #96291D; --warnborder: #F6C6C0;
        font-family: 'Inter', system-ui, sans-serif; background: var(--bg); color: var(--text);
        min-height: 100%; padding: 20px 18px 84px; -webkit-font-smoothing: antialiased;
      }
      .topbar { display: flex; justify-content: flex-end; margin-bottom: 4px; }
      .micbtn {
        width: 40px; height: 40px; min-width: 44px; min-height: 44px; border-radius: 8px; border: 1px solid var(--line);
        background: var(--bg); color: var(--sub); display: flex; align-items: center; justify-content: center; cursor: pointer;
      }
      .micbtn:active { background: var(--soft); }
      .icon-badge {
        width: 46px; height: 46px; border-radius: 10px; background: var(--ac); color: #fff;
        display: flex; align-items: center; justify-content: center; margin-bottom: 10px;
      }
      h1.title { font-size: 26px; font-weight: 700; letter-spacing: -.01em; margin: 0 0 12px; line-height: 1.2; }
      .props { display: grid; gap: 7px; margin-bottom: 16px; }
      .prop { display: flex; align-items: center; gap: 9px; font-size: 13px; color: var(--sub); }
      .prop .k { width: 78px; flex: 0 0 auto; display: flex; align-items: center; gap: 6px; color: var(--sub); }
      .prop .v { color: var(--text); font-weight: 500; }
      .prop .v.tabular { font-variant-numeric: tabular-nums; }
      .divider { height: 1px; background: var(--line); margin: 16px 0; border: none; }
      .callout {
        display: flex; gap: 10px; padding: 12px 13px; border-radius: 7px; background: var(--warnbg);
        border: 1px solid var(--warnborder); color: var(--warntx); font-size: 13px; line-height: 1.5; margin-bottom: 16px;
      }
      .callout.info { background: var(--acsoft); border-color: var(--acsoft2); color: #1a5a9e; }
      .callout .ic { flex: 0 0 auto; margin-top: 1px; }
      .toggle-head {
        display: flex; align-items: center; gap: 7px; padding: 9px 2px; cursor: pointer; user-select: none;
        min-height: 44px; font-size: 14.5px; font-weight: 600;
      }
      .toggle-head .car { transition: transform .16s ease; color: var(--sub); display: flex; }
      .toggle-head[data-open="true"] .car { transform: rotate(90deg); }
      .toggle-body { max-height: 0; overflow: hidden; transition: max-height .2s ease; padding-left: 20px; }
      .toggle-body.open { max-height: 1400px; }
      .toggle-body .inner { padding: 2px 2px 14px; }
      .reduced .toggle-body { transition: none; }
      .bignum { font-size: 30px; font-weight: 700; font-variant-numeric: tabular-nums; letter-spacing: -.01em; }
      .delta { font-size: 12.5px; color: var(--sub); margin-top: 2px; }
      .delta b { color: var(--text); font-variant-numeric: tabular-nums; font-weight: 600; }
      .chart-wrap { margin: 12px 0 6px; }
      .chart-cap { font-size: 11px; color: var(--sub); display: flex; justify-content: space-between; margin-top: 4px; }
      .mtable { display: grid; grid-template-columns: 1fr auto; border-top: 1px solid var(--line); margin-top: 10px; }
      .mtable .r { display: contents; }
      .mtable .c { padding: 9px 2px; border-bottom: 1px solid var(--line); font-size: 13px; }
      .mtable .c.k { color: var(--sub); }
      .mtable .c.v { text-align: right; font-variant-numeric: tabular-nums; font-weight: 500; }
      .checklist { display: grid; gap: 2px; }
      .citem { display: flex; align-items: center; gap: 10px; padding: 8px 2px; min-height: 44px; cursor: pointer; }
      .cbox { width: 18px; height: 18px; border-radius: 4px; border: 1.6px solid #C7C6C3; flex: 0 0 auto; display: flex; align-items: center; justify-content: center; color: #fff; }
      .citem.done .cbox { background: var(--ac); border-color: var(--ac); }
      .citem .ct { font-size: 13.5px; flex: 1; }
      .citem.done .ct { color: var(--sub); text-decoration: line-through; }
      .tag { font-size: 10.5px; color: var(--sub); background: var(--soft); border-radius: 4px; padding: 2px 7px; flex: 0 0 auto; }
      .catrow { display: grid; grid-template-columns: 98px 1fr 66px; align-items: center; gap: 8px; padding: 7px 0; }
      .catrow .nm { font-size: 12px; color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .track { height: 8px; border-radius: 4px; background: var(--soft); overflow: hidden; }
      .fill { height: 100%; background: var(--ac); border-radius: 4px; width: 0; transition: width .5s cubic-bezier(.2,.7,.2,1); }
      .catrow .vv { font-size: 12px; text-align: right; font-variant-numeric: tabular-nums; color: var(--sub); }
      .fcbars { display: grid; gap: 10px; margin: 10px 0 4px; }
      .fcrow .lbl { display: flex; justify-content: space-between; font-size: 12px; color: var(--sub); margin-bottom: 4px; }
      .fcrow .lbl b { color: var(--text); font-variant-numeric: tabular-nums; font-weight: 600; }
      .fctrack { height: 20px; border-radius: 5px; background: var(--soft); overflow: hidden; }
      .fcfill { height: 100%; border-radius: 5px; width: 0; transition: width .6s cubic-bezier(.2,.7,.2,1); }
      table.doctable { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 4px; }
      table.doctable th { text-align: left; color: var(--sub); font-weight: 500; font-size: 11px; padding: 6px 4px; border-bottom: 1px solid var(--line); }
      table.doctable td { padding: 7px 4px; border-bottom: 1px solid var(--line); vertical-align: top; }
      table.doctable td.desc { max-width: 132px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      table.doctable td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
      .linkbtn { border: none; background: none; color: var(--ac); font-size: 12.5px; font-weight: 500; padding: 9px 2px; min-height: 44px; cursor: pointer; }
      .sublist { display: grid; gap: 1px; }
      .subrow { display: flex; align-items: center; gap: 10px; padding: 10px 2px; min-height: 44px; cursor: pointer; border-radius: 6px; }
      .subrow:active { background: var(--soft); }
      .subrow .si { width: 26px; height: 26px; border-radius: 6px; background: var(--soft); color: var(--ac); display: flex; align-items: center; justify-content: center; flex: 0 0 auto; }
      .subrow .sn { font-size: 13.5px; font-weight: 500; flex: 1; }
      .subrow .car { color: var(--sub); transition: transform .16s ease; }
      .subrow[data-open="true"] .car { transform: rotate(90deg); }
      .subbody { max-height: 0; overflow: hidden; transition: max-height .2s ease; padding-left: 36px; }
      .subbody.open { max-height: 600px; }
      .subbody .inner { padding: 2px 4px 16px; font-size: 12.5px; color: var(--sub); line-height: 1.6; }
      .subbody .inner .rt { color: var(--text); font-weight: 500; margin-bottom: 4px; }
      .expill { display: inline-block; font-size: 9.5px; letter-spacing: .04em; text-transform: uppercase; color: var(--sub); background: var(--soft); border-radius: 3px; padding: 1px 6px; margin-left: 6px; }
      .shortcuts { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 4px; }
      .schip { display: flex; align-items: center; gap: 6px; border: 1px solid var(--line); border-radius: 7px; padding: 8px 12px; font-size: 12.5px; color: var(--text); background: var(--bg); min-height: 44px; cursor: pointer; }
      .schip:active { background: var(--soft); }
      .askbar {
        position: fixed; left: 0; right: 0; bottom: 46px; max-width: 430px; margin: 0 auto;
        display: flex; align-items: center; gap: 8px; padding: 8px 10px; background: #fff;
        border-top: 1px solid var(--line);
      }
      .askbar .aic { color: var(--ac); flex: 0 0 auto; }
      .askbar .atx { flex: 1; font-size: 13px; color: var(--sub); }
      .askbar .send { width: 30px; height: 30px; border-radius: 7px; background: var(--soft); color: var(--sub); display: flex; align-items: center; justify-content: center; flex: 0 0 auto; }
      .navbar {
        position: fixed; left: 0; right: 0; bottom: 0; max-width: 430px; margin: 0 auto;
        display: grid; grid-template-columns: repeat(3,1fr); background: #fff; border-top: 1px solid var(--line);
      }
      .navbtn { border: none; background: none; min-height: 46px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px; color: var(--sub); font-size: 10px; cursor: pointer; }
      .navbtn[aria-current="true"] { color: var(--ac); }
      .cursor { width: 6px; height: 13px; background: var(--sub); display: inline-block; animation: blink 1s step-end infinite; opacity: .5; }
      @keyframes blink { 50% { opacity: 0; } }
    `;
    root.appendChild(style);

    const wrap = document.createElement("div");
    wrap.className = "page" + (ctx.reduzido ? " reduced" : "");
    root.appendChild(wrap);

    // ---- chart helpers ----
    function areaChart(vals, { w = 292, h = 96, pad = 6, refVal = null, refLabel = "" } = {}) {
      const n = vals.length;
      const domMax = Math.max(...vals, refVal || 0) * 1.08 || 1;
      const x = i => pad + (i * (w - 2 * pad)) / (n - 1);
      const y = v => h - pad - (v / domMax) * (h - 2 * pad - 12) - 2;
      const pts = vals.map((v, i) => [x(i), y(v)]);
      const line = "M" + pts.map(p => p.join(",")).join(" L ");
      const area = line + ` L ${x(n - 1)},${h - pad} L ${x(0)},${h - pad} Z`;
      let refSvg = "";
      if (refVal && refVal <= domMax) {
        const ry = y(refVal);
        refSvg = `<line x1="${pad}" y1="${ry}" x2="${w - pad}" y2="${ry}" stroke="#B9B8B4" stroke-width="1" stroke-dasharray="3,3"/>
          <text x="${w - pad}" y="${ry - 4}" text-anchor="end" font-size="9" fill="#8a8985">${refLabel}</text>`;
      }
      const last = pts[pts.length - 1];
      return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="none" style="overflow:visible">
        <path d="${area}" fill="${AC}" fill-opacity=".10" stroke="none"/>
        <path d="${line}" fill="none" stroke="${AC}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
        ${refSvg}
        <circle cx="${last[0]}" cy="${last[1]}" r="3" fill="${AC}"/>
      </svg>`;
    }
    function miniBars(vals, { w = 130, h = 40, gap = 3, color = AC, dim = 1 } = {}) {
      const n = vals.length;
      const bw = (w - gap * (n - 1)) / n;
      const max = Math.max(...vals, 1);
      let bars = "";
      vals.forEach((v, i) => {
        const bh = Math.max(2, (v / max) * (h - 4));
        bars += `<rect x="${i * (bw + gap)}" y="${h - bh}" width="${bw}" height="${bh}" rx="1.5" fill="${color}" fill-opacity="${dim}"/>`;
      });
      return `<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}">${bars}</svg>`;
    }
    function seedNums(id, n) {
      let s = 0; for (let i = 0; i < id.length; i++) s = (s * 31 + id.charCodeAt(i)) % 997;
      const out = [];
      for (let i = 0; i < n; i++) { s = (s * 197 + 13) % 89; out.push(2 + (s % 9)); }
      return out;
    }
    function countUp(el, target, isCurrency) {
      if (ctx.reduzido) { el.textContent = isCurrency ? brl(target) : String(target); return; }
      const t0 = performance.now(), dur = 550;
      function step(t) {
        const p = Math.min(1, (t - t0) / dur);
        const e = 1 - Math.pow(1 - p, 3);
        const v = target * e;
        el.textContent = isCurrency ? brl(v) : String(Math.round(v));
        if (p < 1) rafs.push(requestAnimationFrame(step));
      }
      rafs.push(requestAnimationFrame(step));
    }
    function growBars(container) {
      const run = () => container.querySelectorAll("[data-w]").forEach(b => { b.style.width = b.dataset.w; });
      if (ctx.reduzido) run(); else requestAnimationFrame(() => requestAnimationFrame(run));
    }

    function pageHead(icon, title) {
      const h = document.createElement("div");
      h.innerHTML = `<div class="icon-badge">${svgIcon(icon, 22, "#fff", 1.7)}</div><h1 class="title">${title}</h1>`;
      return h;
    }
    function toggle(label, buildInner) {
      const box = document.createElement("div");
      const head = document.createElement("div");
      head.className = "toggle-head"; head.setAttribute("data-open", "false");
      head.innerHTML = `<span class="car">${svgIcon("caret", 13)}</span><span>${label}</span>`;
      const body = document.createElement("div"); body.className = "toggle-body";
      const inner = document.createElement("div"); inner.className = "inner";
      body.appendChild(inner);
      let built = false;
      head.onclick = () => {
        const open = head.getAttribute("data-open") !== "true";
        head.setAttribute("data-open", String(open));
        body.classList.toggle("open", open);
        if (open && !built) { built = true; buildInner(inner); }
      };
      box.append(head, body);
      return box;
    }
    function divider() { const d = document.createElement("hr"); d.className = "divider"; return d; }

    function propsBlock() {
      const now = new Date();
      const hh = String(now.getHours()).padStart(2, "0"), mm = String(now.getMinutes()).padStart(2, "0");
      const dt = new Date(D.hoje.data + "T12:00:00");
      let dataStr = dt.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });
      dataStr = dataStr.charAt(0).toUpperCase() + dataStr.slice(1);
      const p = document.createElement("div"); p.className = "props";
      p.innerHTML = `
        <div class="prop"><span class="k">${svgIcon("clock", 14)} Hora</span><span class="v tabular">${hh}:${mm} · ${D.hoje.cidade}</span></div>
        <div class="prop"><span class="k">${svgIcon("cloud", 14)} Clima</span><span class="v">${D.hoje.clima.cond}, ${D.hoje.clima.temp}°C · chuva ${D.hoje.clima.chuva_prob}%</span></div>
        <div class="prop"><span class="k">${svgIcon("sun", 14)} Data</span><span class="v">${dataStr}</span></div>
      `;
      return p;
    }

    function screenHoje() {
      const top = document.createElement("div"); top.className = "topbar";
      const mic = document.createElement("button"); mic.className = "micbtn"; mic.setAttribute("aria-label", "Comando de voz");
      mic.innerHTML = svgIcon("mic", 17); top.appendChild(mic);
      wrap.appendChild(top);
      wrap.appendChild(pageHead("sun", "Hoje"));
      wrap.appendChild(propsBlock());
      if (D.aviso_critico) {
        const c = document.createElement("div"); c.className = "callout";
        c.innerHTML = `<span class="ic">${svgIcon("pin", 16)}</span><span>${D.aviso_critico}</span>`;
        wrap.appendChild(c);
      }
      wrap.appendChild(divider());

      const tgGasto = toggle("Gasto do mês", inner => {
        const num = document.createElement("div"); num.className = "bignum tabular"; inner.appendChild(num);
        countUp(num, fin.gasto_mes, true);
        const dif = fin.gasto_mes - fin.gasto_mes_anterior;
        const delta = document.createElement("div"); delta.className = "delta";
        delta.innerHTML = `${dif <= 0 ? "▼" : "▲"} <b>${brl(Math.abs(dif))}</b> vs mês anterior (${brl(fin.gasto_mes_anterior)})`;
        inner.appendChild(delta);
        const cw = document.createElement("div"); cw.className = "chart-wrap";
        cw.innerHTML = areaChart(fin.por_dia_mes.map(p => p.acumulado), { refVal: fin.gasto_mes_anterior, refLabel: "mês anterior" });
        inner.appendChild(cw);
        const cap = document.createElement("div"); cap.className = "chart-cap";
        cap.innerHTML = `<span>dia 1</span><span>dia ${fin.por_dia_mes[fin.por_dia_mes.length - 1].dia}</span>`;
        inner.appendChild(cap);
        const mt = document.createElement("div"); mt.className = "mtable";
        [["Hoje", fin.gasto_hoje], ["Fatura atual", fin.fatura_atual], ["Saldo em conta", fin.saldo_conta]].forEach(([k, v]) => {
          mt.innerHTML += `<div class="c k">${k}</div><div class="c v">${brl(v)}</div>`;
        });
        inner.appendChild(mt);
      });
      // open by default
      tgGasto.querySelector(".toggle-head").click();
      wrap.appendChild(tgGasto);

      const foco = document.createElement("div"); foco.className = "callout info";
      foco.innerHTML = `<span class="ic">${svgIcon("pin", 16, "#1a5a9e")}</span><span><b style="font-weight:600">Em foco agora ·</b> ${D.tarefas.em_foco}</span>`;
      wrap.appendChild(foco);

      wrap.appendChild(toggle(`Tarefas pendentes (${D.tarefas.pendentes.length})`, inner => {
        const list = document.createElement("div"); list.className = "checklist";
        D.tarefas.pendentes.forEach(t => {
          const it = document.createElement("div"); it.className = "citem";
          it.innerHTML = `<span class="cbox">${svgIcon("check", 11, "#fff", 2.4)}</span><span class="ct">${t.titulo}</span><span class="tag">${t.quando}</span>`;
          it.onclick = () => it.classList.toggle("done");
          list.appendChild(it);
        });
        inner.appendChild(list);
      }));

      wrap.appendChild(divider());
      const sc = document.createElement("div");
      sc.innerHTML = `<div style="font-size:12px;color:var(--sub);margin-bottom:6px">Atalhos</div>`;
      const chips = document.createElement("div"); chips.className = "shortcuts";
      [["chart", "Finanças", "financas"], ["sparkle", "Vida", "vida"], ["pin", "Tarefas", null], ["plane", "Aviação", "vida"]].forEach(([ic, nm, tela]) => {
        const b = document.createElement("button"); b.className = "schip";
        b.innerHTML = `${svgIcon(ic, 14)} ${nm}`;
        b.onclick = () => { if (tela) ctx.irPara(tela); };
        chips.appendChild(b);
      });
      sc.appendChild(chips);
      wrap.appendChild(sc);

      const ask = document.createElement("div"); ask.className = "askbar";
      ask.innerHTML = `<span class="aic">${svgIcon("send", 15)}</span><span class="atx">Pergunte algo ao painel<span class="cursor"></span></span><span class="send">${svgIcon("chev", 13)}</span>`;
      root.appendChild(ask);

      requestAnimationFrame(() => growBars(wrap));
    }

    function screenFinancas() {
      const top = document.createElement("div"); top.className = "topbar";
      const mic = document.createElement("button"); mic.className = "micbtn"; mic.setAttribute("aria-label", "Comando de voz");
      mic.innerHTML = svgIcon("mic", 17); top.appendChild(mic);
      wrap.appendChild(top);
      wrap.appendChild(pageHead("chart", "Finanças"));

      const num = document.createElement("div"); num.className = "bignum tabular"; wrap.appendChild(num);
      countUp(num, fin.gasto_mes, true);
      const dif = fin.gasto_mes - fin.gasto_mes_anterior;
      const delta = document.createElement("div"); delta.className = "delta";
      delta.innerHTML = `${dif <= 0 ? "▼" : "▲"} <b>${brl(Math.abs(dif))}</b> vs mês anterior · ${fin.orcamento_mes ? "orçamento " + brl(fin.orcamento_mes) : "sem orçamento definido"}`;
      wrap.appendChild(delta);
      wrap.appendChild(divider());

      const catTitle = document.createElement("div");
      catTitle.style.cssText = "font-size:14.5px;font-weight:600;margin-bottom:4px";
      catTitle.textContent = "Gasto por categoria";
      wrap.appendChild(catTitle);
      const maxCat = Math.max(...fin.por_categoria.map(c => c.valor));
      const catBox = document.createElement("div");
      fin.por_categoria.forEach(c => {
        const pct = Math.round((c.valor / maxCat) * 100);
        const row = document.createElement("div"); row.className = "catrow";
        row.innerHTML = `<span class="nm">${c.categoria}</span><span class="track"><span class="fill" data-w="${pct}%"></span></span><span class="vv">${brl(c.valor)}</span>`;
        catBox.appendChild(row);
      });
      wrap.appendChild(catBox);
      wrap.appendChild(divider());

      const evTitle = document.createElement("div");
      evTitle.style.cssText = "font-size:14.5px;font-weight:600;margin-bottom:2px";
      evTitle.textContent = "Evolução do mês";
      wrap.appendChild(evTitle);
      const cw = document.createElement("div"); cw.className = "chart-wrap";
      cw.innerHTML = areaChart(fin.por_dia_mes.map(p => p.acumulado), { refVal: fin.gasto_mes_anterior, refLabel: "mês anterior" });
      wrap.appendChild(cw);
      const cap = document.createElement("div"); cap.className = "chart-cap";
      cap.innerHTML = `<span>dia 1</span><span>dia ${fin.por_dia_mes[fin.por_dia_mes.length - 1].dia} · ${brl(fin.gasto_mes)}</span>`;
      wrap.appendChild(cap);
      wrap.appendChild(divider());

      const fcTitle = document.createElement("div");
      fcTitle.style.cssText = "font-size:14.5px;font-weight:600;margin-bottom:2px";
      fcTitle.textContent = "Fatura x conta";
      wrap.appendChild(fcTitle);
      const fcMax = Math.max(fin.fatura_atual, fin.saldo_conta) * 1.05 || 1;
      const fc = document.createElement("div"); fc.className = "fcbars";
      fc.innerHTML = `
        <div class="fcrow"><div class="lbl"><span>Fatura atual · vence ${fin.fatura_vencimento.slice(8, 10)}/${fin.fatura_vencimento.slice(5, 7)}</span><b>${brl(fin.fatura_atual)}</b></div>
          <div class="fctrack"><div class="fcfill" data-w="${(fin.fatura_atual / fcMax) * 100}%" style="background:${AC}"></div></div></div>
        <div class="fcrow"><div class="lbl"><span>Saldo em conta</span><b>${brl(fin.saldo_conta)}</b></div>
          <div class="fctrack"><div class="fcfill" data-w="${(fin.saldo_conta / fcMax) * 100}%" style="background:${AC};opacity:.35"></div></div></div>
      `;
      wrap.appendChild(fc);
      wrap.appendChild(divider());

      wrap.appendChild(toggle("Extrato · últimos dias", inner => {
        const table = document.createElement("table"); table.className = "doctable";
        table.innerHTML = `<thead><tr><th>Data</th><th>Descrição</th><th>Valor</th></tr></thead><tbody></tbody>`;
        const tbody = table.querySelector("tbody");
        function fill(list) {
          tbody.innerHTML = "";
          list.forEach(t => {
            const tr = document.createElement("tr");
            tr.innerHTML = `<td class="num">${t.data.slice(8, 10)}/${t.data.slice(5, 7)}</td><td class="desc">${t.descricao}</td><td class="num">${brl(t.valor)}</td>`;
            tbody.appendChild(tr);
          });
        }
        fill(fin.ultimos_15_dias.slice(0, 6));
        inner.appendChild(table);
        if (fin.ultimos_15_dias.length > 6) {
          const more = document.createElement("button"); more.className = "linkbtn";
          more.textContent = `Carregar mais (${fin.ultimos_15_dias.length - 6})`;
          more.onclick = () => { fill(fin.ultimos_15_dias); more.remove(); };
          inner.appendChild(more);
        }
      }));

      wrap.appendChild(toggle(`Assinaturas (${fin.assinaturas.length})`, inner => {
        const mt = document.createElement("div"); mt.className = "mtable";
        fin.assinaturas.forEach(s => {
          mt.innerHTML += `<div class="c k">${s.nome} <span style="color:var(--sub)">· prox. ${s.proxima.slice(8, 10)}/${s.proxima.slice(5, 7)}</span></div><div class="c v">${brl(s.valor)}</div>`;
        });
        inner.appendChild(mt);
      }));

      requestAnimationFrame(() => growBars(wrap));
    }

    function screenVida() {
      wrap.appendChild(pageHead("sparkle", "Vida"));
      const p = document.createElement("div"); p.style.cssText = "font-size:13px;color:var(--sub);margin-bottom:14px";
      p.textContent = "18 páginas internas — toque para abrir.";
      wrap.appendChild(p);

      const list = document.createElement("div"); list.className = "sublist";
      let openRow = null, openBody = null;
      D.vida_secoes.forEach(s => {
        const row = document.createElement("div"); row.className = "subrow"; row.setAttribute("data-open", "false");
        row.innerHTML = `<span class="si">${svgIcon(s.id === "viagens" ? "plane" : "page", 14)}</span><span class="sn">${s.nome}</span><span class="car">${svgIcon("chev", 14)}</span>`;
        const body = document.createElement("div"); body.className = "subbody";
        const inner = document.createElement("div"); inner.className = "inner"; body.appendChild(inner);
        let built = false;
        row.onclick = () => {
          const wasOpen = row.getAttribute("data-open") === "true";
          if (openRow && openRow !== row) { openRow.setAttribute("data-open", "false"); openBody.classList.remove("open"); }
          const openNow = !wasOpen;
          row.setAttribute("data-open", String(openNow));
          body.classList.toggle("open", openNow);
          openRow = openNow ? row : null; openBody = openNow ? body : null;
          if (openNow && !built) {
            built = true;
            if (s.id === "viagens" && D.viagem) {
              const v = D.viagem;
              inner.innerHTML = `<div class="rt">${s.resumo}</div><div>Rota ${v.origem} → ${v.destino}</div><div>Faltam <b style="color:var(--text)">${v.dias_faltando} dias</b> · ${v.data.slice(8,10)}/${v.data.slice(5,7)}</div>`;
              const gaugeMax = 60;
              const pct = Math.max(0, Math.min(100, 100 - (v.dias_faltando / gaugeMax) * 100));
              const g = document.createElement("div"); g.style.marginTop = "8px";
              g.innerHTML = `<div class="track" style="height:8px;width:150px"><span class="fill" data-w="${pct}%" style="transition:none;width:${pct}%"></span></div>`;
              inner.appendChild(g);
            } else {
              const nums = seedNums(s.id, 7);
              inner.innerHTML = `<div class="rt">${s.resumo}</div><div>Última atualização há ${1 + (s.id.length % 5)} dias.</div><div>${2 + (s.id.length % 4)} itens ativos nesta seção.</div>`;
              const cw = document.createElement("div"); cw.style.marginTop = "8px";
              cw.innerHTML = miniBars(nums, { dim: .55 }) + `<span class="expill">exemplo</span>`;
              inner.appendChild(cw);
            }
          }
        };
        list.appendChild(row); list.appendChild(body);
      });
      wrap.appendChild(list);
    }

    if (ctx.tela === "hoje") screenHoje();
    else if (ctx.tela === "financas") screenFinancas();
    else screenVida();

    const nav = document.createElement("div"); nav.className = "navbar";
    [["home", "Hoje", "hoje"], ["chart", "Finanças", "financas"], ["sparkle", "Vida", "vida"]].forEach(([ic, nm, tl]) => {
      const b = document.createElement("button"); b.className = "navbtn";
      b.setAttribute("aria-current", String(ctx.tela === tl));
      b.innerHTML = `${svgIcon(ic, 17)}<span>${nm}</span>`;
      b.onclick = () => ctx.irPara(tl);
      nav.appendChild(b);
    });
    root.appendChild(nav);

    return () => { rafs.forEach(cancelAnimationFrame); };
  }
};
