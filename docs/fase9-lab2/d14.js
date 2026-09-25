(window.DIRECOES = window.DIRECOES || {})[14] = {
  nome: "Linha do Dia",
  ideia: "Agenda vertical de calendário: eixo de horas, linha do agora, blocos no horário.",
  acento: "#64D2FF",
  fontes: ["Inter:wght@400;500;600;700", "Roboto+Mono:wght@400;500"],
  render(root, D, ctx) {
    const brl = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v == null ? 0 : v);
    const fin = D.financas;
    const AC = "#64D2FF";
    const timers = [], rafs = [];

    const ICONS = {
      mic: '<rect x="9.3" y="3" width="5.4" height="10" rx="2.7"/><path d="M6 11a6 6 0 0 0 12 0M12 17v3.3"/>',
      cloud: '<path d="M7 18.5a4.5 4.5 0 0 1-.4-9c.6-2.6 2.9-4.5 5.6-4.5 2.9 0 5.3 2.1 5.7 4.9a4 4 0 0 1-.9 7.9H7.2Z"/>',
      alert: '<path d="M12 3.5 2.5 20h19L12 3.5Z"/><path d="M12 9.5v5M12 17.5v.1"/>',
      chev: '<path d="M9 6l6 6-6 6"/>',
      home: '<path d="M4 11.5 12 4l8 7.5"/><path d="M6 10v10h12V10"/>',
      chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
      grid: '<rect x="3" y="3" width="7" height="7" rx="1.4"/><rect x="14" y="3" width="7" height="7" rx="1.4"/><rect x="3" y="14" width="7" height="7" rx="1.4"/><rect x="14" y="14" width="7" height="7" rx="1.4"/>',
      plane: '<path d="M3 13.5 21 6l-4.5 15-3.4-6.4L3 13.5Z"/><path d="M13.1 14.6 8 12"/>',
      send: '<path d="M20.5 3.5 3 10.6l6.8 2.6L20.5 3.5Z"/><path d="M9.8 13.2l2.6 6.8 8.1-16.5Z"/>',
      pin: '<path d="M12 2.8c2.9 0 5.2 2.3 5.2 5.3 0 3.9-5.2 9.7-5.2 9.7S6.8 12 6.8 8.1c0-3 2.3-5.3 5.2-5.3Z"/><circle cx="12" cy="8.1" r="1.9"/>',
      card: '<rect x="2.5" y="5.5" width="19" height="13" rx="2"/><path d="M2.5 10h19"/>'
    };
    const svgIcon = (name, size = 15, stroke = "currentColor", sw = 1.8) =>
      `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="${stroke}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ""}</svg>`;

    const style = document.createElement("style");
    style.textContent = `
      :host, .page * { box-sizing: border-box; }
      .page {
        --bg: #000; --card: #0B0B0D; --card2: #111114; --line: #232326; --text: #F2F2F3; --sub: #8E8E93;
        --ac: ${AC}; --acsoft: rgba(100,210,255,.14); --warnbg: #2A1512; --warntx: #FF8A80; --warnline: #4a2420;
        font-family: 'Inter', system-ui, sans-serif; background: var(--bg); color: var(--text);
        min-height: 100%; padding: 16px 14px 96px; -webkit-font-smoothing: antialiased;
      }
      .hdr { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; margin-bottom: 10px; }
      .hdr .tm { font-size: 30px; font-weight: 700; font-variant-numeric: tabular-nums; letter-spacing: -.01em; line-height: 1; }
      .hdr .dt { font-size: 12px; color: var(--sub); margin-top: 4px; }
      .hdr .wt { display: flex; align-items: center; gap: 5px; font-size: 12px; color: var(--sub); margin-top: 4px; }
      .hdr .wt svg { color: var(--ac); }
      .mic {
        width: 44px; height: 44px; border-radius: 50%; border: 1px solid var(--line); background: var(--card);
        display: flex; align-items: center; justify-content: center; color: var(--ac); flex: 0 0 auto; cursor: pointer;
      }
      .alertbar {
        display: flex; gap: 9px; align-items: flex-start; background: var(--warnbg); border: 1px solid var(--warnline);
        color: var(--warntx); border-radius: 10px; padding: 10px 12px; font-size: 12.5px; line-height: 1.4; margin-bottom: 12px;
      }
      .card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 13px 14px; margin-bottom: 12px; }
      .card .ttl { font-size: 11.5px; color: var(--sub); text-transform: uppercase; letter-spacing: .05em; margin-bottom: 8px; }
      .bignum { font-size: 27px; font-weight: 700; font-variant-numeric: tabular-nums; letter-spacing: -.01em; }
      .delta { font-size: 12px; color: var(--sub); margin-top: 3px; }
      .delta b { color: var(--text); font-variant-numeric: tabular-nums; font-weight: 600; }
      .stats3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-top: 10px; }
      .stat { background: var(--card2); border-radius: 8px; padding: 8px; }
      .stat .k { font-size: 10px; color: var(--sub); margin-bottom: 3px; }
      .stat .v { font-size: 12.5px; font-weight: 600; font-variant-numeric: tabular-nums; }
      .chart-cap { display: flex; justify-content: space-between; font-size: 10.5px; color: var(--sub); margin-top: 3px; }
      .chips { display: flex; gap: 8px; margin-bottom: 12px; overflow-x: auto; scrollbar-width: none; }
      .chips::-webkit-scrollbar { display: none; }
      .chip { flex: 0 0 auto; display: flex; align-items: center; gap: 6px; border: 1px solid var(--line); background: var(--card);
        border-radius: 20px; padding: 9px 13px; font-size: 12px; color: var(--text); min-height: 40px; cursor: pointer; }
      .chip:active { border-color: var(--ac); }
      .tl-wrap { position: relative; background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 10px 10px 10px 0; overflow: hidden; }
      .tl-scroll { position: relative; max-height: 430px; overflow-y: auto; }
      .tl-inner { position: relative; }
      .tl-row { position: relative; display: flex; height: 50px; border-top: 1px solid var(--line); }
      .tl-row:first-child { border-top: none; }
      .tl-hour { width: 46px; flex: 0 0 auto; font-size: 10.5px; color: var(--sub); font-variant-numeric: tabular-nums; padding: 3px 6px; text-align: right; }
      .tl-lane { flex: 1; position: relative; }
      .now-line { position: absolute; left: 46px; right: 6px; height: 1px; background: var(--ac); z-index: 3; }
      .now-line::before { content: ""; position: absolute; left: -4px; top: -3.5px; width: 7px; height: 7px; border-radius: 50%; background: var(--ac); }
      .now-tag { position: absolute; left: 50px; top: -17px; font-size: 9.5px; color: var(--ac); font-variant-numeric: tabular-nums; background: #000; padding: 0 4px; }
      .ev { position: absolute; left: 4px; right: 6px; border-radius: 7px; padding: 5px 8px; font-size: 11.5px; line-height: 1.3; overflow: hidden; z-index: 2; }
      .ev.foco { background: var(--acsoft); border-left: 3px solid var(--ac); color: var(--text); }
      .ev.tarefa { background: #1a1a1d; border-left: 3px solid #58585c; color: var(--text); }
      .ev b { display: block; font-weight: 600; font-size: 11.5px; }
      .ev span.sub { color: var(--sub); font-size: 10px; }
      .tick { position: absolute; width: 8px; height: 8px; border-radius: 50%; background: var(--ac); right: 4px; z-index: 2; cursor: pointer; box-shadow: 0 0 0 2px #000; }
      .tick-note { font-size: 10.5px; color: var(--sub); padding: 6px 10px; }
      .agenda2 { display: grid; gap: 6px; margin-top: 4px; }
      .agenda2 .row { display: flex; align-items: center; gap: 8px; font-size: 12px; padding: 8px 0; border-top: 1px solid var(--line); }
      .agenda2 .row .d { width: 54px; color: var(--sub); font-size: 10.5px; flex: 0 0 auto; }
      .agenda2 .row .t { flex: 1; }
      .catrow { display: grid; grid-template-columns: 96px 1fr 64px; align-items: center; gap: 8px; padding: 6px 0; }
      .catrow .nm { font-size: 11.5px; color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .track { height: 7px; border-radius: 4px; background: var(--card2); overflow: hidden; }
      .fill { height: 100%; background: var(--ac); border-radius: 4px; width: 0; transition: width .55s cubic-bezier(.2,.7,.2,1); }
      .catrow .vv { font-size: 11px; text-align: right; font-variant-numeric: tabular-nums; color: var(--sub); }
      .fcrow .lbl { display: flex; justify-content: space-between; font-size: 11.5px; color: var(--sub); margin-bottom: 4px; }
      .fcrow .lbl b { color: var(--text); font-variant-numeric: tabular-nums; font-weight: 600; }
      .fctrack { height: 18px; border-radius: 5px; background: var(--card2); overflow: hidden; margin-bottom: 10px; }
      .fcfill { height: 100%; border-radius: 5px; width: 0; transition: width .6s cubic-bezier(.2,.7,.2,1); }
      .cal-grid { display: grid; grid-template-columns: repeat(7,1fr); gap: 4px; margin-top: 4px; }
      .cal-wd { font-size: 9.5px; color: var(--sub); text-align: center; padding-bottom: 3px; }
      .cal-day { aspect-ratio: 1; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 10.5px;
        font-variant-numeric: tabular-nums; color: var(--text); background: var(--card2); position: relative; cursor: pointer; }
      .cal-day.empty { background: none; visibility: hidden; }
      .cal-day.today { box-shadow: inset 0 0 0 1.4px var(--ac); }
      .cal-day.sel { box-shadow: inset 0 0 0 1.4px #fff; }
      .cal-legend { display: flex; align-items: center; gap: 6px; font-size: 10px; color: var(--sub); margin-top: 8px; }
      .cal-legend .sq { width: 10px; height: 10px; border-radius: 3px; background: var(--ac); }
      .cal-info { font-size: 11.5px; color: var(--sub); margin-top: 8px; min-height: 16px; }
      .cal-info b { color: var(--text); font-variant-numeric: tabular-nums; }
      table.tt { width: 100%; border-collapse: collapse; font-size: 11.5px; }
      table.tt td { padding: 7px 2px; border-top: 1px solid var(--line); vertical-align: top; }
      table.tt td.desc { max-width: 130px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text); }
      table.tt td.dt2 { color: var(--sub); white-space: nowrap; }
      table.tt td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
      .expand-head { display: flex; align-items: center; justify-content: space-between; cursor: pointer; min-height: 44px; }
      .expand-head .car { color: var(--sub); transition: transform .16s ease; }
      .expand-head[data-open="true"] .car { transform: rotate(90deg); }
      .expand-body { max-height: 0; overflow: hidden; transition: max-height .2s ease; }
      .expand-body.open { max-height: 900px; margin-top: 6px; }
      .reduced .expand-body, .reduced .fill, .reduced .fcfill { transition: none; }
      .linkbtn { border: none; background: none; color: var(--ac); font-size: 12px; font-weight: 500; padding: 9px 0; min-height: 44px; cursor: pointer; }
      .evbar { display: grid; grid-template-columns: repeat(7, 1fr); gap: 5px; align-items: end; height: 46px; margin-top: 6px; }
      .evbar div { background: var(--ac); border-radius: 3px 3px 0 0; }
      .expill { display: inline-block; font-size: 9px; letter-spacing: .04em; text-transform: uppercase; color: var(--sub); background: var(--card2); border-radius: 3px; padding: 1px 6px; margin-left: 6px; }
      .lifecard { border-left: 3px solid var(--ac); padding-left: 10px; }
      .lifecard .rt { font-size: 12px; color: var(--sub); line-height: 1.5; margin-bottom: 8px; }
      .askbar { position: fixed; left: 0; right: 0; bottom: 46px; max-width: 430px; margin: 0 auto; display: flex; align-items: center;
        gap: 8px; padding: 8px 12px; background: #050505; border-top: 1px solid var(--line); }
      .askbar .atx { flex: 1; font-size: 12.5px; color: var(--sub); }
      .askbar .send { width: 30px; height: 30px; border-radius: 8px; background: var(--card2); color: var(--ac); display: flex; align-items: center; justify-content: center; flex: 0 0 auto; }
      .navbar { position: fixed; left: 0; right: 0; bottom: 0; max-width: 430px; margin: 0 auto; display: grid;
        grid-template-columns: repeat(3,1fr); background: #050505; border-top: 1px solid var(--line); }
      .navbtn { border: none; background: none; min-height: 46px; display: flex; flex-direction: column; align-items: center; justify-content: center;
        gap: 2px; color: var(--sub); font-size: 10px; cursor: pointer; }
      .navbtn[aria-current="true"] { color: var(--ac); }
      .cursor { width: 6px; height: 12px; background: var(--sub); display: inline-block; animation: blink 1s step-end infinite; opacity: .6; }
      @keyframes blink { 50% { opacity: 0; } }
    `;
    root.appendChild(style);

    const wrap = document.createElement("div");
    wrap.className = "page" + (ctx.reduzido ? " reduced" : "");
    root.appendChild(wrap);

    function areaChart(vals, { w = 300, h = 84, pad = 4, refVal = null, refLabel = "" } = {}) {
      const n = vals.length;
      const domMax = Math.max(...vals, refVal || 0) * 1.08 || 1;
      const x = i => pad + (i * (w - 2 * pad)) / (n - 1);
      const y = v => h - pad - (v / domMax) * (h - 2 * pad - 10) - 2;
      const pts = vals.map((v, i) => [x(i), y(v)]);
      const line = "M" + pts.map(p => p.join(",")).join(" L ");
      const area = line + ` L ${x(n - 1)},${h - pad} L ${x(0)},${h - pad} Z`;
      let refSvg = "";
      if (refVal && refVal <= domMax) {
        const ry = y(refVal);
        refSvg = `<line x1="${pad}" y1="${ry}" x2="${w - pad}" y2="${ry}" stroke="#3a3a3d" stroke-width="1" stroke-dasharray="3,3"/>
          <text x="${w - pad}" y="${ry - 4}" text-anchor="end" font-size="9" fill="#7d7d80">${refLabel}</text>`;
      }
      const last = pts[pts.length - 1];
      return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="none" style="overflow:visible">
        <path d="${area}" fill="${AC}" fill-opacity=".14" stroke="none"/>
        <path d="${line}" fill="none" stroke="${AC}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
        ${refSvg}<circle cx="${last[0]}" cy="${last[1]}" r="3" fill="${AC}"/>
      </svg>`;
    }
    function seedNums(id, n, lo = 2, span = 9) {
      let s = 0; for (let i = 0; i < id.length; i++) s = (s * 31 + id.charCodeAt(i)) % 997;
      const out = [];
      for (let i = 0; i < n; i++) { s = (s * 197 + 13) % 89; out.push(lo + (s % span)); }
      return out;
    }
    function growBars() {
      const run = () => wrap.querySelectorAll("[data-w]").forEach(b => { b.style.width = b.dataset.w; });
      if (ctx.reduzido) run(); else requestAnimationFrame(() => requestAnimationFrame(run));
    }
    function countUp(el, target) {
      if (ctx.reduzido) { el.textContent = brl(target); return; }
      const t0 = performance.now(), dur = 550;
      function step(t) {
        const p = Math.min(1, (t - t0) / dur);
        const v = target * (1 - Math.pow(1 - p, 3));
        el.textContent = brl(v);
        if (p < 1) rafs.push(requestAnimationFrame(step));
      }
      rafs.push(requestAnimationFrame(step));
    }

    function header(showMic) {
      const now = new Date();
      const h = document.createElement("div"); h.className = "hdr";
      const dt = new Date(D.hoje.data + "T12:00:00");
      let dataStr = dt.toLocaleDateString("pt-BR", { weekday: "short", day: "numeric", month: "short" });
      dataStr = dataStr.charAt(0).toUpperCase() + dataStr.slice(1);
      h.innerHTML = `<div>
          <div class="tm tabular" id="clockNow">--:--</div>
          <div class="dt">${dataStr} · ${D.hoje.cidade}</div>
          <div class="wt">${svgIcon("cloud", 13)}<span>${D.hoje.clima.cond}, ${D.hoje.clima.temp}°C · chuva ${D.hoje.clima.chuva_prob}%</span></div>
        </div>`;
      if (showMic) {
        const mic = document.createElement("button"); mic.className = "mic"; mic.setAttribute("aria-label", "Comando de voz");
        mic.innerHTML = svgIcon("mic", 18); h.appendChild(mic);
      }
      wrap.appendChild(h);
      const clockEl = h.querySelector("#clockNow");
      const tick = () => {
        const n = new Date();
        clockEl.textContent = String(n.getHours()).padStart(2, "0") + ":" + String(n.getMinutes()).padStart(2, "0");
      };
      tick();
      if (!ctx.reduzido) timers.push(setInterval(tick, 15000));
    }
    function alertBar() {
      if (!D.aviso_critico) return;
      const a = document.createElement("div"); a.className = "alertbar";
      a.innerHTML = `<span>${svgIcon("alert", 15)}</span><span>${D.aviso_critico}</span>`;
      wrap.appendChild(a);
    }

    function screenHoje() {
      header(true);
      alertBar();

      const gc = document.createElement("div"); gc.className = "card";
      gc.innerHTML = `<div class="ttl">Gasto do mês</div>`;
      const num = document.createElement("div"); num.className = "bignum"; gc.appendChild(num);
      countUp(num, fin.gasto_mes);
      const dif = fin.gasto_mes - fin.gasto_mes_anterior;
      const delta = document.createElement("div"); delta.className = "delta";
      delta.innerHTML = `${dif <= 0 ? "▼" : "▲"} <b>${brl(Math.abs(dif))}</b> vs mês anterior`;
      gc.appendChild(delta);
      const cw = document.createElement("div"); cw.style.marginTop = "8px";
      cw.innerHTML = areaChart(fin.por_dia_mes.map(p => p.acumulado), { refVal: fin.gasto_mes_anterior, refLabel: "mês ant." });
      gc.appendChild(cw);
      const cap = document.createElement("div"); cap.className = "chart-cap";
      cap.innerHTML = `<span>dia 1</span><span>dia ${fin.por_dia_mes[fin.por_dia_mes.length - 1].dia}</span>`;
      gc.appendChild(cap);
      const st = document.createElement("div"); st.className = "stats3";
      st.innerHTML = `<div class="stat"><div class="k">Hoje</div><div class="v">${brl(fin.gasto_hoje)}</div></div>
        <div class="stat"><div class="k">Fatura</div><div class="v">${brl(fin.fatura_atual)}</div></div>
        <div class="stat"><div class="k">Conta</div><div class="v">${brl(fin.saldo_conta)}</div></div>`;
      gc.appendChild(st);
      wrap.appendChild(gc);

      const chips = document.createElement("div"); chips.className = "chips";
      [["chart", "Finanças", "financas"], ["grid", "Vida", "vida"]].forEach(([ic, nm, tl]) => {
        const c = document.createElement("button"); c.className = "chip";
        c.innerHTML = `${svgIcon(ic, 14)} ${nm}`; c.onclick = () => ctx.irPara(tl);
        chips.appendChild(c);
      });
      wrap.appendChild(chips);

      // ---- vertical timeline (dia completo, 00-24h) ----
      const HSTART = 0, HEND = 24, ROWH = 46;
      const now = new Date();
      const nowHourFloat = now.getHours() + now.getMinutes() / 60;
      const nowFrac = Math.max(0, Math.min(1, (nowHourFloat - HSTART) / (HEND - HSTART)));
      const totalH = (HEND - HSTART) * ROWH;

      const tlWrap = document.createElement("div"); tlWrap.className = "tl-wrap";
      const tlScroll = document.createElement("div"); tlScroll.className = "tl-scroll";
      const tlInner = document.createElement("div"); tlInner.className = "tl-inner"; tlInner.style.height = totalH + "px";
      for (let hh = HSTART; hh < HEND; hh++) {
        const row = document.createElement("div"); row.className = "tl-row"; row.style.height = ROWH + "px";
        row.innerHTML = `<div class="tl-hour">${String(hh).padStart(2, "0")}:00</div><div class="tl-lane"></div>`;
        tlInner.appendChild(row);
      }
      // linha do agora
      const nl = document.createElement("div"); nl.className = "now-line"; nl.style.top = (nowFrac * totalH) + "px";
      const tag = document.createElement("div"); tag.className = "now-tag"; tag.style.top = (nowFrac * totalH) + "px";
      tag.textContent = String(now.getHours()).padStart(2, "0") + ":" + String(now.getMinutes()).padStart(2, "0") + " agora";
      tlInner.appendChild(nl); tlInner.appendChild(tag);

      function place(hourFloat, durH, cls, title, sub) {
        const h0 = Math.max(HSTART, Math.min(HEND - durH, hourFloat));
        const top = ((h0 - HSTART) / (HEND - HSTART)) * totalH;
        const height = (durH / (HEND - HSTART)) * totalH - 3;
        const ev = document.createElement("div"); ev.className = "ev " + cls;
        ev.style.top = top + "px"; ev.style.height = Math.max(30, height) + "px"; ev.style.left = "50px";
        ev.innerHTML = `<b>${title}</b>${sub ? `<span class="sub">${sub}</span>` : ""}`;
        tlInner.appendChild(ev);
        return h0 + durH;
      }
      // foco agora, depois tarefas de hoje em sequência (sem sobrepor)
      let cursor = place(Math.max(HSTART, nowHourFloat - .25), 1.5, "foco", D.tarefas.em_foco, "Em foco agora");
      const hojeTasks = D.tarefas.pendentes.filter(t => t.quando === "Hoje");
      hojeTasks.forEach(t => { cursor = place(cursor + .25, 1, "tarefa", t.titulo, t.quando) + 0; });
      // expense ticks for today
      const hojeGastos = fin.ultimos_15_dias.filter(t => t.data === D.hoje.data);
      hojeGastos.forEach(t => {
        let s = 0; for (let i = 0; i < t.descricao.length; i++) s += t.descricao.charCodeAt(i);
        const hourF = HSTART + 1 + (s % ((HEND - HSTART) - 2));
        const top = ((hourF - HSTART) / (HEND - HSTART)) * totalH;
        const tk = document.createElement("div"); tk.className = "tick"; tk.style.top = (top - 4) + "px";
        tk.title = t.descricao + " · " + brl(t.valor);
        tk.onclick = () => { note.textContent = t.descricao + " — " + brl(t.valor); };
        tlInner.appendChild(tk);
      });
      tlScroll.appendChild(tlInner);
      tlWrap.appendChild(tlScroll);
      wrap.appendChild(tlWrap);
      const note = document.createElement("div"); note.className = "tick-note";
      note.textContent = hojeGastos.length ? "Toque em um ponto para ver o gasto." : "Sem gastos hoje até agora.";
      wrap.appendChild(note);
      // scroll timeline to now
      requestAnimationFrame(() => { tlScroll.scrollTop = Math.max(0, (nowFrac * totalH) - 120); });

      const outros = D.tarefas.pendentes.filter(t => t.quando !== "Hoje");
      if (outros.length) {
        const ag = document.createElement("div"); ag.className = "card"; ag.style.marginTop = "12px";
        ag.innerHTML = `<div class="ttl">Próximos dias</div>`;
        const list = document.createElement("div"); list.className = "agenda2";
        outros.forEach(t => { list.innerHTML += `<div class="row"><span class="d">${t.quando}</span><span class="t">${t.titulo}</span></div>`; });
        ag.appendChild(list);
        wrap.appendChild(ag);
      }

      const ask = document.createElement("div"); ask.className = "askbar";
      ask.innerHTML = `<span style="color:var(--ac)">${svgIcon("send", 15)}</span><span class="atx">Falar com o painel<span class="cursor"></span></span><span class="send">${svgIcon("chev", 13)}</span>`;
      root.appendChild(ask);
    }

    function screenFinancas() {
      header(false);
      const rc = document.createElement("div"); rc.className = "card";
      rc.innerHTML = `<div class="ttl">Resumo do mês</div>`;
      const num = document.createElement("div"); num.className = "bignum"; rc.appendChild(num);
      countUp(num, fin.gasto_mes);
      const dif = fin.gasto_mes - fin.gasto_mes_anterior;
      const delta = document.createElement("div"); delta.className = "delta";
      delta.innerHTML = `${dif <= 0 ? "▼" : "▲"} <b>${brl(Math.abs(dif))}</b> vs mês anterior · ${fin.orcamento_mes ? "orçamento " + brl(fin.orcamento_mes) : "sem orçamento"}`;
      rc.appendChild(delta);
      wrap.appendChild(rc);

      // calendar heatmap
      const [year, month] = fin.mes.split("-").map(Number);
      const daysInMonth = new Date(year, month, 0).getDate();
      const firstDow = new Date(year, month - 1, 1).getDay();
      const deltas = {};
      let prevAc = 0;
      fin.por_dia_mes.forEach(p => { deltas[p.dia] = Math.max(0, +(p.acumulado - prevAc).toFixed(2)); prevAc = p.acumulado; });
      const maxDelta = Math.max(...Object.values(deltas), 1);
      const todayDay = Number(D.hoje.data.slice(8, 10));

      const cc = document.createElement("div"); cc.className = "card";
      cc.innerHTML = `<div class="ttl">Calendário de gastos</div>`;
      const grid = document.createElement("div"); grid.className = "cal-grid";
      ["D", "S", "T", "Q", "Q", "S", "S"].forEach(w => { grid.innerHTML += `<div class="cal-wd">${w}</div>`; });
      for (let i = 0; i < firstDow; i++) grid.innerHTML += `<div class="cal-day empty"></div>`;
      const info = document.createElement("div"); info.className = "cal-info";
      info.textContent = "Toque em um dia para ver o gasto.";
      for (let d = 1; d <= daysInMonth; d++) {
        const val = deltas[d];
        const cell = document.createElement("div");
        cell.className = "cal-day" + (d === todayDay ? " today" : "");
        cell.textContent = String(d);
        if (val != null) {
          const op = 0.14 + (val / maxDelta) * 0.72;
          cell.style.background = `rgba(100,210,255,${op.toFixed(2)})`;
          cell.style.color = op > 0.55 ? "#00171f" : "var(--text)";
        }
        cell.onclick = () => {
          grid.querySelectorAll(".cal-day.sel").forEach(x => x.classList.remove("sel"));
          cell.classList.add("sel");
          info.innerHTML = val != null ? `Dia <b>${d}</b>: <b>${brl(val)}</b> gastos` : `Dia <b>${d}</b>: sem dado ainda`;
        };
        grid.appendChild(cell);
      }
      cc.appendChild(grid);
      const leg = document.createElement("div"); leg.className = "cal-legend";
      leg.innerHTML = `<span class="sq" style="opacity:.2"></span><span>menos</span><span class="sq"></span><span>mais gasto</span>`;
      cc.appendChild(leg);
      cc.appendChild(info);
      wrap.appendChild(cc);

      const catc = document.createElement("div"); catc.className = "card";
      catc.innerHTML = `<div class="ttl">Gasto por categoria</div>`;
      const maxCat = Math.max(...fin.por_categoria.map(c => c.valor));
      fin.por_categoria.forEach(c => {
        const pct = Math.round((c.valor / maxCat) * 100);
        const row = document.createElement("div"); row.className = "catrow";
        row.innerHTML = `<span class="nm">${c.categoria}</span><span class="track"><span class="fill" data-w="${pct}%"></span></span><span class="vv">${brl(c.valor)}</span>`;
        catc.appendChild(row);
      });
      wrap.appendChild(catc);

      const fc = document.createElement("div"); fc.className = "card";
      fc.innerHTML = `<div class="ttl">Fatura x conta</div>`;
      const fcMax = Math.max(fin.fatura_atual, fin.saldo_conta) * 1.05 || 1;
      fc.innerHTML += `
        <div class="fcrow"><div class="lbl"><span>Fatura · vence ${fin.fatura_vencimento.slice(8, 10)}/${fin.fatura_vencimento.slice(5, 7)}</span><b>${brl(fin.fatura_atual)}</b></div>
          <div class="fctrack"><div class="fcfill" data-w="${(fin.fatura_atual / fcMax) * 100}%" style="background:${AC}"></div></div></div>
        <div class="fcrow"><div class="lbl"><span>Saldo em conta</span><b>${brl(fin.saldo_conta)}</b></div>
          <div class="fctrack"><div class="fcfill" data-w="${(fin.saldo_conta / fcMax) * 100}%" style="background:${AC};opacity:.35"></div></div></div>`;
      wrap.appendChild(fc);

      const ec = document.createElement("div"); ec.className = "card";
      const eh = document.createElement("div"); eh.className = "expand-head"; eh.setAttribute("data-open", "false");
      eh.innerHTML = `<span class="ttl" style="margin:0">Últimos 15 dias</span><span class="car">${svgIcon("chev", 15)}</span>`;
      const eb = document.createElement("div"); eb.className = "expand-body";
      const table = document.createElement("table"); table.className = "tt"; table.innerHTML = `<tbody></tbody>`;
      const tbody = table.querySelector("tbody");
      function fillRows(list) {
        tbody.innerHTML = "";
        list.forEach(t => {
          const tr = document.createElement("tr");
          tr.innerHTML = `<td class="dt2">${t.data.slice(8, 10)}/${t.data.slice(5, 7)}</td><td class="desc">${t.descricao}</td><td class="num">${brl(t.valor)}</td>`;
          tbody.appendChild(tr);
        });
      }
      fillRows(fin.ultimos_15_dias.slice(0, 6));
      eb.appendChild(table);
      if (fin.ultimos_15_dias.length > 6) {
        const more = document.createElement("button"); more.className = "linkbtn";
        more.textContent = `Carregar mais (${fin.ultimos_15_dias.length - 6})`;
        more.onclick = () => { fillRows(fin.ultimos_15_dias); more.remove(); };
        eb.appendChild(more);
      }
      let ebBuilt = true;
      eh.onclick = () => { const o = eh.getAttribute("data-open") !== "true"; eh.setAttribute("data-open", String(o)); eb.classList.toggle("open", o); };
      ec.append(eh, eb); wrap.appendChild(ec);

      const ac2 = document.createElement("div"); ac2.className = "card";
      const ah = document.createElement("div"); ah.className = "expand-head"; ah.setAttribute("data-open", "false");
      ah.innerHTML = `<span class="ttl" style="margin:0">Assinaturas (${fin.assinaturas.length})</span><span class="car">${svgIcon("chev", 15)}</span>`;
      const ab = document.createElement("div"); ab.className = "expand-body";
      const subList = document.createElement("div"); subList.className = "agenda2";
      fin.assinaturas.forEach(s => { subList.innerHTML += `<div class="row"><span class="d">${s.proxima.slice(8, 10)}/${s.proxima.slice(5, 7)}</span><span class="t">${s.nome}</span><b class="tabular">${brl(s.valor)}</b></div>`; });
      ab.appendChild(subList);
      ah.onclick = () => { const o = ah.getAttribute("data-open") !== "true"; ah.setAttribute("data-open", String(o)); ab.classList.toggle("open", o); };
      ac2.append(ah, ab); wrap.appendChild(ac2);

      requestAnimationFrame(growBars);
    }

    function screenVida() {
      header(false);
      const chips = document.createElement("div"); chips.className = "chips";
      let selectedId = null;
      const detail = document.createElement("div");
      D.vida_secoes.forEach(s => {
        const c = document.createElement("button"); c.className = "chip";
        c.innerHTML = `${s.nome}`;
        c.onclick = () => {
          chips.querySelectorAll(".chip").forEach(x => x.style.borderColor = "var(--line)");
          c.style.borderColor = "var(--ac)";
          selectedId = s.id; renderDetail(s);
        };
        chips.appendChild(c);
      });
      wrap.appendChild(chips);
      wrap.appendChild(detail);

      function renderDetail(s) {
        detail.innerHTML = "";
        const card = document.createElement("div"); card.className = "card lifecard";
        if (s.id === "viagens" && D.viagem) {
          const v = D.viagem;
          card.innerHTML = `<div class="ttl">${s.nome}</div><div class="rt">${s.resumo}<br>Rota ${v.origem} → ${v.destino} · ${v.data.slice(8,10)}/${v.data.slice(5,7)}</div>`;
          const big = document.createElement("div"); big.className = "bignum"; big.textContent = v.dias_faltando + " dias";
          card.appendChild(big);
          const gaugeMax = 60, pct = Math.max(4, Math.min(100, 100 - (v.dias_faltando / gaugeMax) * 100));
          const g = document.createElement("div"); g.className = "track"; g.style.marginTop = "8px";
          g.innerHTML = `<div class="fill" style="width:${pct}%;transition:none"></div>`;
          card.appendChild(g);
        } else {
          const nums = seedNums(s.id, 7);
          card.innerHTML = `<div class="ttl">${s.nome} <span class="expill">exemplo</span></div>
            <div class="rt">${s.resumo}<br>${2 + (s.id.length % 4)} itens ativos · atualizado há ${1 + (s.id.length % 5)}d</div>`;
          const bars = document.createElement("div"); bars.className = "evbar";
          const mx = Math.max(...nums);
          nums.forEach(n => { const d = document.createElement("div"); d.style.height = Math.round((n / mx) * 100) + "%"; bars.appendChild(d); });
          card.appendChild(bars);
        }
        detail.appendChild(card);
      }
      renderDetail(D.vida_secoes[0]);
      chips.firstChild.style.borderColor = "var(--ac)";
    }

    if (ctx.tela === "hoje") screenHoje();
    else if (ctx.tela === "financas") screenFinancas();
    else screenVida();

    const nav = document.createElement("div"); nav.className = "navbar";
    [["home", "Hoje", "hoje"], ["chart", "Finanças", "financas"], ["grid", "Vida", "vida"]].forEach(([ic, nm, tl]) => {
      const b = document.createElement("button"); b.className = "navbtn";
      b.setAttribute("aria-current", String(ctx.tela === tl));
      b.innerHTML = `${svgIcon(ic, 17)}<span>${nm}</span>`;
      b.onclick = () => ctx.irPara(tl);
      nav.appendChild(b);
    });
    root.appendChild(nav);

    return () => { timers.forEach(clearInterval); rafs.forEach(cancelAnimationFrame); };
  }
};
