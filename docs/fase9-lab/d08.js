(window.DIRECOES = window.DIRECOES || {})[8] = {
  nome: "Colmeia",
  ideia: "Módulos hexagonais com borda fina; favo de hexágonos para gastos, categorias e seções.",
  acento: "#2DD4BF",
  fontes: ["Chakra+Petch:wght@400;500;600", "JetBrains+Mono:wght@400;500"],
  render(root, D, ctx) {
    const AC = "#2DD4BF";
    const BRL = (v) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);
    const style = document.createElement("style");
    style.textContent = `
      :host, * { box-sizing: border-box; }
      .wrap {
        font-family: 'Chakra Petch', sans-serif;
        color: #d8d8d8;
        min-height: 100%;
        padding: 14px 14px 84px 14px;
      }
      .mono { font-family: 'JetBrains Mono', monospace; font-variant-numeric: tabular-nums; }
      .top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }
      .clock { font-size: 26px; font-weight: 600; }
      .date { font-size: 11px; color: #8a8a8a; margin-top: 2px; }
      .wx { text-align: right; font-size: 11px; color: #8a8a8a; }
      .wx b { color: #d8d8d8; font-size: 15px; display: block; }
      .alert { border: 1px solid #ff3b30; color: #ff8c85; font-size: 11px; padding: 6px 8px; margin-bottom: 10px; display: flex; align-items: center; gap: 6px; }
      .mic-row { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }
      .mic { width: 44px; height: 44px; border: 1px solid ${AC}; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex: none; background: transparent; }
      .mic svg { stroke: ${AC}; }
      .chat { flex: 1; border: 1px solid #2a2a2a; height: 44px; border-radius: 4px; display: flex; align-items: center; padding: 0 10px; color: #8a8a8a; font-size: 12px; }
      .sec-title { font-size: 10px; color: #8a8a8a; text-transform: uppercase; letter-spacing: 1px; margin: 14px 0 6px; }

      .honeycomb { display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; padding: 4px 0; }
      .hex {
        --s: 92px;
        width: var(--s); height: calc(var(--s) * 1.1547);
        clip-path: polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%);
        background: #050505;
        border: 1px solid #24312f;
        position: relative;
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        opacity: 0; transform: scale(.6);
        animation: hx-in .5s ease forwards;
        cursor: pointer;
        text-align: center; padding: 6px;
      }
      .hex.big { --s: 168px; }
      .hex .lbl { font-size: 8px; color: #8a8a8a; text-transform: uppercase; letter-spacing: .5px; max-width: 66%; line-height: 1.25; overflow-wrap: break-word; }
      .hex .val { font-size: 13px; font-weight: 600; margin-top: 3px; color: #d8d8d8; }
      .hex.big .val { font-size: 20px; }
      .hex .fill {
        position: absolute; left: 0; right: 0; bottom: 0;
        background: linear-gradient(180deg, rgba(45,212,191,0.05), rgba(45,212,191,0.22));
        height: 0%;
        transition: height 1s ease;
      }
      @keyframes hx-in { to { opacity: 1; transform: scale(1); } }

      .spark { width: 70%; height: 30px; margin-top: 4px; }

      .rd-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 12px; }
      .rd { border: 1px solid #1e2a28; padding: 8px 6px; text-align: center; clip-path: polygon(6% 0, 94% 0, 100% 50%, 94% 100%, 6% 100%, 0 50%); }
      .rd .k { font-size: 9px; color: #8a8a8a; text-transform: uppercase; letter-spacing: .5px; }
      .rd .v { font-size: 13px; margin-top: 4px; font-weight: 600; }

      .focus { border: 1px solid #1e2a28; padding: 8px 10px; margin-top: 12px; font-size: 12px; }
      .focus .k { font-size: 9px; color: #8a8a8a; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 3px; }

      .shortcuts { display: flex; gap: 8px; margin-top: 12px; }
      .sc { flex: 1; border: 1px solid #1e2a28; padding: 10px 4px; text-align: center; font-size: 10px; color: #b8b8b8; min-height: 44px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; }
      .sc svg { stroke: ${AC}; }

      .navbar { position: fixed; left: 0; right: 0; bottom: 0; height: 60px; border-top: 1px solid #1e2a28; background: #000; display: flex; }
      .navbar button { flex: 1; background: none; border: none; color: #8a8a8a; font-size: 10px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px; font-family: inherit; min-height: 44px; }
      .navbar button.on { color: ${AC}; }
      .navbar svg { stroke: currentColor; }

      .detail-panel { border: 1px solid ${AC}; padding: 10px; margin-top: 10px; font-size: 12px; }
      .detail-panel .t { color: ${AC}; font-weight: 600; margin-bottom: 4px; }

      .list { margin-top: 6px; }
      .row { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #14201d; padding: 8px 2px; font-size: 12px; min-height: 44px; }
      .row .sub { font-size: 10px; color: #8a8a8a; margin-top: 2px; }
      .btn-more { width: 100%; margin-top: 8px; border: 1px solid #1e2a28; background: none; color: #8a8a8a; padding: 10px; font-size: 11px; min-height: 44px; font-family: inherit; }
      details summary { cursor: pointer; font-size: 11px; color: #8a8a8a; margin-top: 10px; list-style: none; }
      details summary::-webkit-details-marker { display: none; }

      .mini-hive { display: flex; flex-wrap: wrap; gap: 4px; justify-content: center; }
      .mini-hex {
        --s: 52px; width: var(--s); height: calc(var(--s) * 1.1547);
        clip-path: polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%);
        background: #050505; border: 1px solid #24312f;
        display: flex; align-items: center; justify-content: center;
        cursor: pointer; min-width: 44px; min-height: 44px;
      }
      .mini-hex.sel { border-color: ${AC}; }
      .mini-hex svg { stroke: ${AC}; }
    `;
    root.appendChild(style);

    const wrap = document.createElement("div");
    wrap.className = "wrap";
    root.appendChild(wrap);

    const iconMic = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke-width="1.5"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/></svg>`;
    const iconWarn = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ff3b30" stroke-width="1.5"><path d="M12 3l10 18H2L12 3z"/><path d="M12 10v5"/><circle cx="12" cy="18" r="0.6" fill="#ff3b30"/></svg>`;
    const iconFin = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke-width="1.5"><circle cx="12" cy="12" r="9"/><path d="M12 7v10M8.5 9.5h5a2 2 0 1 1 0 4h-5a2 2 0 1 0 0 4h6"/></svg>`;
    const iconVida = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke-width="1.5"><path d="M12 2l3 7 7 3-7 1-3 9-3-9-7-1 7-3 3-7z"/></svg>`;
    const iconTarefa = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke-width="1.5"><path d="M4 6h16M4 12h16M4 18h10"/></svg>`;
    const iconAviacao = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke-width="1.5"><path d="M22 12l-8-3-5-8-2 1 3 7-7 1v2l7 1-3 7 2 1 5-8 8-3z"/></svg>`;
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
      const items = [["hoje", "Hoje", iconHoje], ["financas", "Finanças", iconFin], ["vida", "Vida", iconVida]];
      items.forEach(([id, label, icon]) => {
        const b = document.createElement("button");
        b.className = id === active ? "on" : "";
        b.innerHTML = icon + `<span>${label}</span>`;
        b.onclick = () => ctx.irPara(id);
        nav.appendChild(b);
      });
      return nav;
    }

    function drawSparkline(svgHost, serie, w, h) {
      const max = Math.max(...serie, 1);
      const pts = serie.map((v, i) => {
        const x = (i / (serie.length - 1)) * w;
        const y = h - (v / max) * h;
        return [x, y];
      });
      const d = pts.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", d);
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", AC);
      path.setAttribute("stroke-width", "1.5");
      if (!ctx.reduzido) {
        const len = 400;
        path.style.strokeDasharray = len;
        path.style.strokeDashoffset = len;
        path.style.transition = "stroke-dashoffset 1.4s ease";
        svgHost.appendChild(path);
        requestAnimationFrame(() => requestAnimationFrame(() => { path.style.strokeDashoffset = "0"; }));
      } else {
        svgHost.appendChild(path);
      }
    }

    function renderHoje() {
      wrap.innerHTML = "";
      const top = document.createElement("div");
      top.className = "top";
      top.innerHTML = `
        <div>
          <div class="clock mono" id="clk">--:--</div>
          <div class="date">${D.hoje.data} · ${D.hoje.cidade}</div>
        </div>
        <div class="wx"><b>${Math.round(D.hoje.clima.temp)}°C</b>${D.hoje.clima.cond}<br>chuva ${D.hoje.clima.chuva_prob}%</div>`;
      wrap.appendChild(top);
      everySec(() => {
        const el = top.querySelector("#clk");
        if (el) el.textContent = new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
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

      const comb = document.createElement("div");
      comb.className = "honeycomb";
      wrap.appendChild(comb);

      const big = document.createElement("div");
      big.className = "hex big";
      big.style.animationDelay = "0s";
      const serie = D.financas.por_dia_mes.map(d => d.acumulado);
      big.innerHTML = `
        <div class="fill"></div>
        <div class="lbl">Gasto do mês</div>
        <div class="val mono">${BRL(D.financas.gasto_mes)}</div>
        <svg class="spark" viewBox="0 0 100 30" preserveAspectRatio="none"></svg>`;
      comb.appendChild(big);
      const svgHost = big.querySelector("svg");
      drawSparkline(svgHost, serie, 100, 30);
      const pct = Math.min(100, (D.financas.gasto_mes / (D.financas.orcamento_mes || D.financas.gasto_mes)) * 100);
      requestAnimationFrame(() => requestAnimationFrame(() => { big.querySelector(".fill").style.height = pct + "%"; }));
      big.onclick = () => ctx.irPara("financas");

      const mini = [
        ["Hoje", BRL(D.financas.gasto_hoje)],
        ["Fatura", BRL(D.financas.fatura_atual)],
        ["Conta", BRL(D.financas.saldo_conta)],
      ];
      mini.forEach(([lbl, val], i) => {
        const h = document.createElement("div");
        h.className = "hex";
        h.style.animationDelay = (0.1 + i * 0.08) + "s";
        h.innerHTML = `<div class="lbl">${lbl}</div><div class="val mono">${val}</div>`;
        comb.appendChild(h);
      });

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
        <div class="sc">${iconAviacao}Aviação</div>`;
      sc.querySelectorAll("[data-go]").forEach(el => { el.onclick = () => ctx.irPara(el.getAttribute("data-go")); });
      wrap.appendChild(sc);

      wrap.appendChild(navbar("hoje"));
    }

    function renderFinancas() {
      wrap.innerHTML = "";
      const dif = D.financas.gasto_mes - D.financas.gasto_mes_anterior;
      const head = document.createElement("div");
      head.className = "sec-title";
      head.style.marginTop = "0";
      head.textContent = "Gasto do mês";
      wrap.appendChild(head);
      const headline = document.createElement("div");
      headline.innerHTML = `<div class="clock mono" style="font-size:24px">${BRL(D.financas.gasto_mes)}</div>
        <div class="date">${dif <= 0 ? "▼" : "▲"} ${BRL(Math.abs(dif))} vs. mês anterior · orçamento ${BRL(D.financas.orcamento_mes)}</div>`;
      wrap.appendChild(headline);

      const st = document.createElement("div");
      st.className = "sec-title";
      st.textContent = "Categorias";
      wrap.appendChild(st);

      const comb = document.createElement("div");
      comb.className = "honeycomb";
      wrap.appendChild(comb);

      const detail = document.createElement("div");
      wrap.appendChild(detail);

      const cats = D.financas.por_categoria;
      const maxV = Math.max(...cats.map(c => c.valor), 1);
      cats.forEach((c, i) => {
        const h = document.createElement("div");
        h.className = "hex";
        h.style.animationDelay = (i * 0.05) + "s";
        h.innerHTML = `<div class="fill"></div><div class="lbl">${c.categoria}</div><div class="val mono">${BRL(c.valor)}</div>`;
        const pct = (c.valor / maxV) * 100;
        requestAnimationFrame(() => requestAnimationFrame(() => { h.querySelector(".fill").style.height = pct + "%"; }));
        h.onclick = () => {
          detail.innerHTML = `<div class="detail-panel"><div class="t">${c.categoria}</div>
            <div>${BRL(c.valor)} este mês · ${((c.valor / D.financas.gasto_mes) * 100).toFixed(1)}% do total</div></div>`;
        };
        comb.appendChild(h);
      });

      const rd = document.createElement("div");
      rd.className = "rd-row";
      rd.innerHTML = `
        <div class="rd"><div class="k">Fatura</div><div class="v mono">${BRL(D.financas.fatura_atual)}</div></div>
        <div class="rd"><div class="k">Vence</div><div class="v mono">${D.financas.fatura_vencimento.slice(8,10)}/${D.financas.fatura_vencimento.slice(5,7)}</div></div>
        <div class="rd"><div class="k">Conta</div><div class="v mono">${BRL(D.financas.saldo_conta)}</div></div>`;
      wrap.appendChild(rd);

      const st2 = document.createElement("div");
      st2.className = "sec-title";
      st2.textContent = "Últimos 15 dias";
      wrap.appendChild(st2);

      const extList = document.createElement("div");
      extList.className = "list";
      const dias = D.financas.ultimos_15_dias;
      let shown = 6;
      function renderExt() {
        extList.innerHTML = "";
        dias.slice(0, shown).forEach(d => {
          const row = document.createElement("div");
          row.className = "row";
          row.innerHTML = `<div><div>${d.descricao}</div><div class="sub">${d.data.slice(8,10)}/${d.data.slice(5,7)} · ${d.categoria}</div></div><div class="mono">${BRL(d.valor)}</div>`;
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
      details.innerHTML = `<summary>▸ Assinaturas (${D.financas.assinaturas.length})</summary>`;
      const assList = document.createElement("div");
      assList.className = "list";
      D.financas.assinaturas.forEach(a => {
        const row = document.createElement("div");
        row.className = "row";
        row.innerHTML = `<div><div>${a.nome}</div><div class="sub">próx. ${a.proxima.slice(8,10)}/${a.proxima.slice(5,7)}</div></div><div class="mono">${BRL(a.valor)}</div>`;
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
      head.textContent = "Seções";
      wrap.appendChild(head);

      const hive = document.createElement("div");
      hive.className = "mini-hive";
      wrap.appendChild(hive);

      const detail = document.createElement("div");
      wrap.appendChild(detail);

      const iconGeneric = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke-width="1.5"><path d="M12 2l7 4v8l-7 4-7-4V6l7-4z"/></svg>`;

      D.vida_secoes.forEach(sec => {
        const h = document.createElement("div");
        h.className = "mini-hex";
        h.innerHTML = iconGeneric;
        h.onclick = () => {
          hive.querySelectorAll(".mini-hex").forEach(x => x.classList.remove("sel"));
          h.classList.add("sel");
          let extra = "";
          if (sec.id === "viagens" && D.viagem) {
            extra = `<div class="sub">${D.viagem.origem} → ${D.viagem.destino} · ${D.viagem.data} · faltam ${D.viagem.dias_faltando} dias</div>`;
          }
          detail.innerHTML = `<div class="detail-panel"><div class="t">${sec.nome}</div>
            <div>${sec.resumo}</div>
            <div class="sub">Sincronizado · sem pendências</div>
            ${extra}</div>`;
        };
        hive.appendChild(h);
      });

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
