(window.DIRECOES = window.DIRECOES || {})[5] = {
  nome: "Radar",
  ideia: "Radar circular com varredura girando; categorias de gasto viram alvos por distância.",
  acento: "#FF8A00",
  fontes: ["Chakra+Petch:wght@400;500;600", "JetBrains+Mono:wght@400;500"],
  render(root, D, ctx) {
    const AC = "#FF8A00";
    const BRL = (v) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);
    const style = document.createElement("style");
    style.textContent = `
      :host, * { box-sizing: border-box; }
      .wrap {
        font-family: 'Chakra Petch', sans-serif;
        color: #d8d8d8;
        min-height: 100%;
        padding: 14px 14px 84px 14px;
        position: relative;
      }
      .mono { font-family: 'JetBrains Mono', monospace; font-variant-numeric: tabular-nums; }
      .top {
        display: flex; justify-content: space-between; align-items: flex-start;
        margin-bottom: 10px;
      }
      .clock { font-size: 26px; font-weight: 600; letter-spacing: 1px; }
      .date { font-size: 11px; color: #8a8a8a; margin-top: 2px; }
      .wx { text-align: right; font-size: 11px; color: #8a8a8a; }
      .wx b { color: #d8d8d8; font-size: 15px; display:block; }
      .alert {
        border: 1px solid #ff3b30; color: #ff8c85; font-size: 11px;
        padding: 6px 8px; margin-bottom: 10px; display: flex; align-items: center; gap: 6px;
      }
      .alert svg { flex: none; }
      .mic-row { display: flex; gap: 8px; align-items: center; margin-bottom: 10px; }
      .mic {
        width: 44px; height: 44px; border: 1px solid ${AC}; border-radius: 50%;
        display: flex; align-items: center; justify-content: center; flex: none; background: transparent;
      }
      .mic svg { stroke: ${AC}; }
      .chat {
        flex: 1; border: 1px solid #2a2a2a; height: 44px; border-radius: 4px;
        display: flex; align-items: center; padding: 0 10px; color: #8a8a8a; font-size: 12px;
      }
      .scope {
        position: relative; width: 100%; aspect-ratio: 1 / 1; max-width: 380px; margin: 6px auto 8px;
      }
      canvas { width: 100%; height: 100%; display: block; }
      .label {
        position: absolute; transform: translate(-50%, -50%); font-size: 9px;
        color: #cfcfcf; pointer-events: none; white-space: nowrap; text-align: center;
        opacity: 0.35; transition: opacity .15s linear;
      }
      .label b { display: block; font-size: 9px; color: ${AC}; font-weight: 500; }
      .readouts {
        display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 4px;
      }
      .rd {
        border: 1px solid #262626; padding: 8px 6px; text-align: center;
      }
      .rd .k { font-size: 9px; color: #8a8a8a; letter-spacing: .5px; text-transform: uppercase; }
      .rd .v { font-size: 14px; margin-top: 3px; font-weight: 600; }
      .focus {
        border: 1px solid #262626; padding: 8px 10px; margin-top: 10px; font-size: 12px;
      }
      .focus .k { font-size: 9px; color: #8a8a8a; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 3px; }
      .shortcuts { display: flex; gap: 8px; margin-top: 10px; }
      .sc {
        flex: 1; border: 1px solid #262626; padding: 10px 4px; text-align: center; font-size: 10px;
        color: #b8b8b8; min-height: 44px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px;
      }
      .sc svg { stroke: ${AC}; }
      .navbar {
        position: fixed; left: 0; right: 0; bottom: 0; height: 60px;
        border-top: 1px solid #262626; background: #000;
        display: flex;
      }
      .navbar button {
        flex: 1; background: none; border: none; color: #8a8a8a; font-size: 10px;
        display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px;
        font-family: inherit; min-height: 44px;
      }
      .navbar button.on { color: ${AC}; }
      .navbar svg { stroke: currentColor; }
      .cat-list { margin-top: 10px; }
      .cat-row {
        display: flex; justify-content: space-between; align-items: center;
        border-bottom: 1px solid #1c1c1c; padding: 8px 2px; font-size: 12px; min-height: 44px;
      }
      .cat-row .name { color: #d8d8d8; }
      .cat-row .sub { font-size: 10px; color: #8a8a8a; margin-top: 2px; }
      .cat-row .val { font-family: 'JetBrains Mono', monospace; }
      .sec-title { font-size: 10px; color: #8a8a8a; text-transform: uppercase; letter-spacing: 1px; margin: 14px 0 4px; }
      .lock-panel {
        border: 1px solid ${AC}; padding: 10px; margin-top: 10px; font-size: 12px;
      }
      .lock-panel .name { color: ${AC}; font-weight: 600; margin-bottom: 4px; }
      .vida-strip { display: flex; overflow-x: auto; gap: 8px; padding: 4px 0 10px; -webkit-overflow-scrolling: touch; }
      .vida-item {
        flex: none; width: 64px; height: 64px; border: 1px solid #262626; border-radius: 50%;
        display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px;
        font-size: 8px; color: #8a8a8a; text-align: center; padding: 4px;
      }
      .vida-item.sel { border-color: ${AC}; color: ${AC}; }
      .vida-detail { border: 1px solid #262626; padding: 10px; font-size: 12px; margin-top: 4px; }
      .vida-detail .t { color: ${AC}; font-weight: 600; margin-bottom: 4px; }
      .vida-detail .l { color: #a8a8a8; margin-top: 4px; font-size: 11px; }
      .collapsible summary { cursor: pointer; font-size: 11px; color: #8a8a8a; margin-top: 10px; list-style: none; }
      .collapsible summary::-webkit-details-marker { display: none; }
      .btn-more {
        width: 100%; margin-top: 8px; border: 1px solid #262626; background: none; color: #8a8a8a;
        padding: 10px; font-size: 11px; min-height: 44px; font-family: inherit;
      }
    `;
    root.appendChild(style);

    const wrap = document.createElement("div");
    wrap.className = "wrap";
    root.appendChild(wrap);

    const iconMic = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke-width="1.5"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/></svg>`;
    const iconWarn = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ff3b30" stroke-width="1.5"><path d="M12 3l10 18H2L12 3z"/><path d="M12 10v5"/><circle cx="12" cy="18" r="0.6" fill="#ff3b30"/></svg>`;
    const iconFin = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke-width="1.5"><circle cx="12" cy="12" r="9"/><path d="M12 7v10M8.5 9.5h5a2 2 0 1 1 0 4h-5a2 2 0 1 0 0 4h6"/></svg>`;
    const iconVida = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke-width="1.5"><rect x="4" y="4" width="7" height="7"/><rect x="13" y="4" width="7" height="7"/><rect x="4" y="13" width="7" height="7"/><rect x="13" y="13" width="7" height="7"/></svg>`;
    const iconTarefa = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke-width="1.5"><path d="M4 6h16M4 12h16M4 18h10"/></svg>`;
    const iconAviacao = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke-width="1.5"><path d="M12 2l3 7 7 3-7 1-3 9-3-9-7-1 7-3 3-7z"/></svg>`;
    const iconHoje = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke-width="1.5"><circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/></svg>`;

    let timers = [];
    function everySec(fn) { fn(); const id = setInterval(fn, 1000); timers.push(id); return id; }
    function raf(fn) {
      let id;
      function loop(t) { fn(t); id = requestAnimationFrame(loop); }
      id = requestAnimationFrame(loop);
      timers.push({ cancel: () => cancelAnimationFrame(id) });
    }
    function cleanupAll() {
      timers.forEach(t => { if (typeof t === "number") clearInterval(t); else if (t && t.cancel) t.cancel(); });
      timers = [];
    }

    function navbar(active) {
      const nav = document.createElement("div");
      nav.className = "navbar";
      const items = [
        ["hoje", "Hoje", iconHoje],
        ["financas", "Finanças", iconFin],
        ["vida", "Vida", iconVida],
      ];
      items.forEach(([id, label, icon]) => {
        const b = document.createElement("button");
        b.className = id === active ? "on" : "";
        b.innerHTML = icon + `<span>${label}</span>`;
        b.onclick = () => ctx.irPara(id);
        nav.appendChild(b);
      });
      return nav;
    }

    function renderHoje() {
      wrap.innerHTML = "";
      const top = document.createElement("div");
      top.className = "top";
      const now = new Date();
      top.innerHTML = `
        <div>
          <div class="clock mono" id="clk">--:--</div>
          <div class="date">${D.hoje.data} · ${D.hoje.cidade}</div>
        </div>
        <div class="wx">
          <b>${Math.round(D.hoje.clima.temp)}°C</b>
          ${D.hoje.clima.cond}<br>chuva ${D.hoje.clima.chuva_prob}%
        </div>`;
      wrap.appendChild(top);

      const clk = top.querySelector("#clk");
      everySec(() => {
        const d = new Date();
        clk.textContent = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
      });

      if (D.aviso_critico) {
        const al = document.createElement("div");
        al.className = "alert";
        al.innerHTML = iconWarn + `<span>${D.aviso_critico}</span>`;
        wrap.appendChild(al);
      }

      const micRow = document.createElement("div");
      micRow.className = "mic-row";
      micRow.innerHTML = `<button class="mic">${iconMic}</button><div class="chat">Falar com o painel…</div>`;
      wrap.appendChild(micRow);

      const scope = document.createElement("div");
      scope.className = "scope";
      scope.innerHTML = `<canvas></canvas>`;
      wrap.appendChild(scope);
      const labelsHost = document.createElement("div");
      scope.appendChild(labelsHost);

      const cv = scope.querySelector("canvas");
      const cats = D.financas.por_categoria.slice(0, 6);
      const maxV = Math.max(...cats.map(c => c.valor), 1);

      let dpr = Math.min(window.devicePixelRatio || 1, 2);
      function resize() {
        const r = scope.getBoundingClientRect();
        cv.width = r.width * dpr;
        cv.height = r.height * dpr;
      }
      resize();

      // place labels once around ring positions
      const angleStep = (Math.PI * 2) / cats.length;
      const labelEls = cats.map((c, i) => {
        const el = document.createElement("div");
        el.className = "label";
        el.innerHTML = `<b>${BRL(c.valor)}</b>${c.categoria}`;
        labelsHost.appendChild(el);
        return el;
      });

      let sweep = 0;
      const rMax = 0.44;
      function draw() {
        const w = cv.width, h = cv.height;
        const cx = w / 2, cy = h / 2;
        const R = Math.min(w, h) * rMax;
        const g = cv.getContext("2d");
        g.clearRect(0, 0, w, h);
        g.strokeStyle = "#2a2016";
        g.lineWidth = 1 * dpr;
        for (let i = 1; i <= 4; i++) {
          g.beginPath();
          g.arc(cx, cy, (R * i) / 4, 0, Math.PI * 2);
          g.stroke();
        }
        g.beginPath();
        g.moveTo(cx - R, cy); g.lineTo(cx + R, cy);
        g.moveTo(cx, cy - R); g.lineTo(cx, cy + R);
        g.stroke();

        // sweep gradient
        const grad = g.createConic ? null : null;
        g.save();
        g.translate(cx, cy);
        g.rotate(sweep);
        const sweepGrad = g.createLinearGradient(0, 0, R, 0);
        sweepGrad.addColorStop(0, "rgba(255,138,0,0.35)");
        sweepGrad.addColorStop(1, "rgba(255,138,0,0)");
        g.beginPath();
        g.moveTo(0, 0);
        g.arc(0, 0, R, -0.18, 0.02);
        g.closePath();
        g.fillStyle = sweepGrad;
        g.fill();
        g.restore();

        // targets
        cats.forEach((c, i) => {
          const ang = -Math.PI / 2 + i * angleStep;
          const dist = 0.28 + 0.72 * (c.valor / maxV);
          const rr = R * dist;
          const x = cx + Math.cos(ang) * rr;
          const y = cy + Math.sin(ang) * rr;
          let diff = ((ang - sweep) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2);
          const near = diff < 0.28 || diff > Math.PI * 2 - 0.28;
          g.beginPath();
          g.arc(x, y, 3.5 * dpr, 0, Math.PI * 2);
          g.strokeStyle = near ? "rgba(255,138,0,0.95)" : "rgba(255,138,0,0.35)";
          g.lineWidth = 1.5 * dpr;
          g.stroke();

          const lx = (x / w) * 100, ly = (y / h) * 100;
          const el = labelEls[i];
          el.style.left = lx + "%";
          el.style.top = ly + "%";
          el.style.opacity = near ? "0.95" : "0.35";
        });

        // center dot
        g.beginPath();
        g.arc(cx, cy, 2 * dpr, 0, Math.PI * 2);
        g.fillStyle = "#8a8a8a";
        g.fill();
      }

      if (ctx.reduzido) {
        draw();
      } else {
        raf(() => {
          sweep += 0.018;
          draw();
        });
      }

      const rd = document.createElement("div");
      rd.className = "readouts";
      rd.innerHTML = `
        <div class="rd"><div class="k">Hoje</div><div class="v mono">${BRL(D.financas.gasto_hoje)}</div></div>
        <div class="rd"><div class="k">Fatura</div><div class="v mono">${BRL(D.financas.fatura_atual)}</div></div>
        <div class="rd"><div class="k">Conta</div><div class="v mono">${BRL(D.financas.saldo_conta)}</div></div>
      `;
      wrap.appendChild(rd);

      const foc = document.createElement("div");
      foc.className = "focus";
      foc.innerHTML = `<div class="k">Em foco agora</div><div>${D.tarefas.em_foco}</div>`;
      wrap.appendChild(foc);

      const sc = document.createElement("div");
      sc.className = "shortcuts";
      sc.innerHTML = `
        <div class="sc" data-go="financas">${iconFin}Finanças</div>
        <div class="sc" data-go="vida">${iconVida}Vida</div>
        <div class="sc">${iconTarefa}Tarefas</div>
        <div class="sc">${iconAviacao}Aviação</div>
      `;
      sc.querySelectorAll("[data-go]").forEach(el => {
        el.onclick = () => ctx.irPara(el.getAttribute("data-go"));
      });
      wrap.appendChild(sc);

      wrap.appendChild(navbar("hoje"));
    }

    function renderFinancas() {
      wrap.innerHTML = "";
      const head = document.createElement("div");
      head.className = "top";
      const dif = D.financas.gasto_mes - D.financas.gasto_mes_anterior;
      head.innerHTML = `
        <div>
          <div class="sec-title" style="margin-top:0">Gasto do mês</div>
          <div class="clock mono" style="font-size:24px">${BRL(D.financas.gasto_mes)}</div>
          <div class="date">${dif <= 0 ? "▼" : "▲"} ${BRL(Math.abs(dif))} vs. mês anterior</div>
        </div>`;
      wrap.appendChild(head);

      const scope = document.createElement("div");
      scope.className = "scope";
      scope.style.maxWidth = "420px";
      scope.innerHTML = `<canvas></canvas>`;
      wrap.appendChild(scope);
      const labelsHost = document.createElement("div");
      scope.appendChild(labelsHost);
      const cv = scope.querySelector("canvas");

      const cats = D.financas.por_categoria;
      const maxV = Math.max(...cats.map(c => c.valor), 1);
      let dpr = Math.min(window.devicePixelRatio || 1, 2);
      function resize() { const r = scope.getBoundingClientRect(); cv.width = r.width * dpr; cv.height = r.height * dpr; }
      resize();

      const angleStep = (Math.PI * 2) / cats.length;
      const labelEls = cats.map(c => {
        const el = document.createElement("div");
        el.className = "label";
        el.innerHTML = `<b>${BRL(c.valor)}</b>${c.categoria}`;
        labelsHost.appendChild(el);
        return el;
      });

      let sweep = 0;
      const rMax = 0.44;
      function draw() {
        const w = cv.width, h = cv.height, cx = w / 2, cy = h / 2, R = Math.min(w, h) * rMax;
        const g = cv.getContext("2d");
        g.clearRect(0, 0, w, h);
        g.strokeStyle = "#2a2016";
        g.lineWidth = 1 * dpr;
        for (let i = 1; i <= 4; i++) { g.beginPath(); g.arc(cx, cy, (R * i) / 4, 0, Math.PI * 2); g.stroke(); }
        g.save();
        g.translate(cx, cy);
        g.rotate(sweep);
        const sweepGrad = g.createLinearGradient(0, 0, R, 0);
        sweepGrad.addColorStop(0, "rgba(255,138,0,0.35)");
        sweepGrad.addColorStop(1, "rgba(255,138,0,0)");
        g.beginPath(); g.moveTo(0, 0); g.arc(0, 0, R, -0.18, 0.02); g.closePath();
        g.fillStyle = sweepGrad; g.fill();
        g.restore();

        cats.forEach((c, i) => {
          const ang = -Math.PI / 2 + i * angleStep;
          const dist = 0.25 + 0.75 * (c.valor / maxV);
          const rr = R * dist;
          const x = cx + Math.cos(ang) * rr, y = cy + Math.sin(ang) * rr;
          let diff = ((ang - sweep) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2);
          const near = diff < 0.28 || diff > Math.PI * 2 - 0.28;
          g.beginPath(); g.arc(x, y, 3.5 * dpr, 0, Math.PI * 2);
          g.strokeStyle = near ? "rgba(255,138,0,0.95)" : "rgba(255,138,0,0.35)";
          g.lineWidth = 1.5 * dpr; g.stroke();
          const el = labelEls[i];
          el.style.left = (x / w * 100) + "%";
          el.style.top = (y / h * 100) + "%";
          el.style.opacity = near ? "0.95" : "0.35";
        });
        g.beginPath(); g.arc(cx, cy, 2 * dpr, 0, Math.PI * 2); g.fillStyle = "#8a8a8a"; g.fill();
      }
      if (ctx.reduzido) draw(); else raf(() => { sweep += 0.015; draw(); });

      const rd = document.createElement("div");
      rd.className = "readouts";
      rd.innerHTML = `
        <div class="rd"><div class="k">Fatura</div><div class="v mono">${BRL(D.financas.fatura_atual)}</div></div>
        <div class="rd"><div class="k">Vence</div><div class="v mono">${D.financas.fatura_vencimento.slice(8,10)}/${D.financas.fatura_vencimento.slice(5,7)}</div></div>
        <div class="rd"><div class="k">Conta</div><div class="v mono">${BRL(D.financas.saldo_conta)}</div></div>
      `;
      wrap.appendChild(rd);

      const st = document.createElement("div");
      st.className = "sec-title";
      st.textContent = "Contatos (categorias) · rumo/distância";
      wrap.appendChild(st);

      const list = document.createElement("div");
      list.className = "cat-list";
      cats.forEach((c, i) => {
        const ang = Math.round(((i * (360 / cats.length)) % 360));
        const row = document.createElement("div");
        row.className = "cat-row";
        row.innerHTML = `<div><div class="name">${c.categoria}</div><div class="sub">rumo ${String(ang).padStart(3,"0")}°</div></div><div class="val">${BRL(c.valor)}</div>`;
        list.appendChild(row);
      });
      wrap.appendChild(list);

      const st2 = document.createElement("div");
      st2.className = "sec-title";
      st2.textContent = "Últimos 15 dias";
      wrap.appendChild(st2);

      const extList = document.createElement("div");
      extList.className = "cat-list";
      const dias = D.financas.ultimos_15_dias;
      let shown = 6;
      function renderExt() {
        extList.innerHTML = "";
        dias.slice(0, shown).forEach(d => {
          const row = document.createElement("div");
          row.className = "cat-row";
          row.innerHTML = `<div><div class="name">${d.descricao}</div><div class="sub">${d.data.slice(8,10)}/${d.data.slice(5,7)} · ${d.categoria}</div></div><div class="val">${BRL(d.valor)}</div>`;
          extList.appendChild(row);
        });
      }
      renderExt();
      wrap.appendChild(extList);

      if (dias.length > shown) {
        const more = document.createElement("button");
        more.className = "btn-more";
        more.textContent = "Carregar mais";
        more.onclick = () => { shown = dias.length; renderExt(); more.remove(); };
        wrap.appendChild(more);
      }

      const details = document.createElement("details");
      details.className = "collapsible";
      details.innerHTML = `<summary>▸ Assinaturas (${D.financas.assinaturas.length})</summary>`;
      const assList = document.createElement("div");
      assList.className = "cat-list";
      D.financas.assinaturas.forEach(a => {
        const row = document.createElement("div");
        row.className = "cat-row";
        row.innerHTML = `<div><div class="name">${a.nome}</div><div class="sub">próx. ${a.proxima.slice(8,10)}/${a.proxima.slice(5,7)}</div></div><div class="val">${BRL(a.valor)}</div>`;
        assList.appendChild(row);
      });
      details.appendChild(assList);
      wrap.appendChild(details);

      wrap.appendChild(navbar("financas"));
    }

    function renderVida() {
      wrap.innerHTML = "";
      const head = document.createElement("div");
      head.className = "sec-title";
      head.style.marginTop = "0";
      head.textContent = "Contatos rastreados";
      wrap.appendChild(head);

      const strip = document.createElement("div");
      strip.className = "vida-strip";
      wrap.appendChild(strip);

      const detail = document.createElement("div");
      wrap.appendChild(detail);

      let selected = null;
      D.vida_secoes.forEach(sec => {
        const item = document.createElement("div");
        item.className = "vida-item";
        item.innerHTML = `<div class="mono">${sec.nome.slice(0,3).toUpperCase()}</div>`;
        item.onclick = () => {
          strip.querySelectorAll(".vida-item").forEach(x => x.classList.remove("sel"));
          item.classList.add("sel");
          selected = sec;
          renderDetail();
        };
        strip.appendChild(item);
      });

      function renderDetail() {
        if (!selected) { detail.innerHTML = ""; return; }
        let extra = "";
        if (selected.id === "viagens" && D.viagem) {
          extra = `<div class="l">${D.viagem.origem} → ${D.viagem.destino} · ${D.viagem.data} · faltam ${D.viagem.dias_faltando} dias</div>`;
        }
        detail.innerHTML = `
          <div class="vida-detail">
            <div class="t">${selected.nome} · travado</div>
            <div>${selected.resumo}</div>
            <div class="l">Sinal estável · sem pendências críticas</div>
            ${extra}
          </div>`;
      }

      wrap.appendChild(navbar("vida"));
    }

    function renderCurrent() {
      cleanupAll();
      if (ctx.tela === "financas") renderFinancas();
      else if (ctx.tela === "vida") renderVida();
      else renderHoje();
    }

    renderCurrent();
    return () => cleanupAll();
  }
};
