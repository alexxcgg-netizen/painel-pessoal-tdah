(window.DIRECOES = window.DIRECOES || {})[1] = {
  nome: "Reator",
  ideia: "Anel central grande com o gasto do mês; anéis concêntricos girando em velocidades diferentes.",
  acento: "#22D3EE",
  fontes: ["Chakra+Petch:wght@400;500;600", "JetBrains+Mono:wght@400;500"],
  render(root, D, ctx) {
    const AC = "#22D3EE";
    const fmt = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
    const fin = D.financas || {};
    const timers = [];
    const cleanups = [];

    const ICONS = {
      mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/><path d="M8 21h8"/></svg>',
      financas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="9"/><path d="M12 7v10M9 9.5c0-1.4 1.3-2 3-2s3 .8 3 2-1.3 1.8-3 2-3 .8-3 2 1.3 2 3 2 3-.6 3-2"/></svg>',
      vida: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>',
      tarefas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 6h16M4 12h16M4 18h10"/><circle cx="20" cy="18" r="2"/></svg>',
      aviacao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2v20M4 9l16 4M6 20l6-3 6 3"/></svg>',
      chuva: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M7 15a4 4 0 0 1 .8-7.94A5 5 0 0 1 17.6 9.1 3.5 3.5 0 0 1 17 16H7z"/><path d="M8 19l-1 2M12 19l-1 2M16 19l-1 2"/></svg>',
      alerta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 3l10 18H2L12 3z"/><path d="M12 10v4M12 17h.01"/></svg>',
      seta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 6l6 6-6 6"/></svg>',
      enviar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 12l16-8-6 16-3-7-7-1z"/></svg>'
    };

    root.innerHTML = `
    <style>
      :host, * { box-sizing: border-box; }
      .wrap { font-family: 'Chakra Petch', sans-serif; color: #d8d8d8; padding: 14px 14px 90px; min-height: 100%; position: relative; }
      .mono { font-family: 'JetBrains Mono', monospace; }
      .tab-title { font-size: 11px; letter-spacing: .28em; text-transform: uppercase; color: ${AC}; opacity: .8; margin: 0 0 10px 2px; }
      .row { display: flex; align-items: center; gap: 10px; }
      .topbar { justify-content: space-between; margin-bottom: 14px; }
      .clock { font-family: 'JetBrains Mono', monospace; }
      .clock .hh { font-size: 30px; font-weight: 500; letter-spacing: .02em; font-variant-numeric: tabular-nums; }
      .clock .dd { font-size: 11px; color: #8a8a8a; text-transform: uppercase; letter-spacing: .1em; }
      .clima { text-align: right; font-size: 12px; color: #a8a8a8; }
      .clima svg { width: 16px; height: 16px; vertical-align: -3px; margin-right: 4px; color: ${AC}; }
      .mic { width: 46px; height: 46px; border-radius: 50%; border: 1px solid #333; background: #060606; color: ${AC}; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
      .mic svg { width: 20px; height: 20px; }
      .aviso { display: flex; gap: 8px; align-items: center; border: 1px solid #4a2020; background: #140808; color: #e08080; font-size: 11.5px; padding: 8px 10px; border-radius: 4px; margin-bottom: 16px; }
      .aviso svg { width: 15px; height: 15px; flex-shrink: 0; }
      .reator { position: relative; width: 272px; height: 272px; margin: 6px auto 6px; }
      .reator svg { width: 100%; height: 100%; }
      .ring-track { fill: none; stroke: #1c1c1c; }
      .ring-val { fill: none; stroke: ${AC}; stroke-linecap: round; }
      .spin { transform-origin: 136px 136px; }
      .center { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }
      .center .lbl { font-size: 10px; letter-spacing: .2em; text-transform: uppercase; color: #8a8a8a; margin-bottom: 6px; }
      .center .num { font-family: 'JetBrains Mono', monospace; font-size: 27px; font-variant-numeric: tabular-nums; color: #f2f2f2; }
      .center .cmp { font-size: 10.5px; margin-top: 6px; color: #8a8a8a; }
      .center .cmp b { color: ${AC}; font-weight: 500; }
      .leituras { display: flex; justify-content: space-between; margin: 14px 4px 20px; }
      .leitura { text-align: center; flex: 1; }
      .leitura .l1 { font-size: 9.5px; letter-spacing: .14em; text-transform: uppercase; color: #7a7a7a; }
      .leitura .l2 { font-family: 'JetBrains Mono', monospace; font-size: 13.5px; margin-top: 4px; font-variant-numeric: tabular-nums; color: #eaeaea; }
      .divider { height: 1px; background: linear-gradient(90deg, transparent, #2a2a2a, transparent); margin: 14px 0; }
      .foco { border: 1px solid #232323; border-radius: 4px; padding: 10px 12px; margin-bottom: 16px; }
      .foco .l1 { font-size: 10px; color: #7a7a7a; letter-spacing: .1em; text-transform: uppercase; }
      .foco .l2 { margin-top: 4px; font-size: 14px; color: #f0f0f0; }
      .atalhos { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 18px; }
      .atalho { border: 1px solid #232323; border-radius: 6px; padding: 10px 4px; display: flex; flex-direction: column; align-items: center; gap: 6px; background: #050505; min-height: 44px; }
      .atalho svg { width: 18px; height: 18px; color: ${AC}; }
      .atalho span { font-size: 9.5px; color: #9a9a9a; letter-spacing: .04em; }
      .chatbar { position: absolute; left: 14px; right: 14px; bottom: 14px; display: flex; align-items: center; gap: 8px; border: 1px solid #262626; border-radius: 22px; padding: 5px 6px 5px 14px; background: #070707; }
      .chatbar input { flex: 1; background: transparent; border: none; outline: none; color: #ddd; font-family: 'Chakra Petch', sans-serif; font-size: 13px; }
      .chatbar input::placeholder { color: #555; }
      .chatbar button { width: 34px; height: 34px; border-radius: 50%; border: 1px solid #2a2a2a; background: #0c0c0c; color: ${AC}; display: flex; align-items: center; justify-content: center; }
      .chatbar button svg { width: 15px; height: 15px; }

      /* categoria arcos */
      .cat-ring { width: 260px; height: 260px; margin: 6px auto 10px; position: relative; }
      .cat-ring svg { width: 100%; height: 100%; }
      .cat-center { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
      .cat-center .num { font-family: 'JetBrains Mono', monospace; font-size: 22px; color: #f2f2f2; }
      .cat-center .lbl { font-size: 9.5px; color: #7a7a7a; letter-spacing: .16em; text-transform: uppercase; margin-top: 4px; }
      .legenda { display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px; }
      .leg-item { display: flex; align-items: center; gap: 8px; font-size: 12px; }
      .leg-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
      .leg-nome { flex: 1; color: #c8c8c8; }
      .leg-val { font-family: 'JetBrains Mono', monospace; color: #eee; font-variant-numeric: tabular-nums; }

      .card { border: 1px solid #202020; border-radius: 6px; padding: 12px; margin-bottom: 12px; }
      .card .t1 { font-size: 10px; color: #7a7a7a; letter-spacing: .12em; text-transform: uppercase; margin-bottom: 8px; }
      .fvsc { display: flex; gap: 12px; }
      .fvsc .item { flex: 1; text-align: center; padding: 10px 6px; border: 1px solid #1c1c1c; border-radius: 5px; }
      .fvsc .n { font-family: 'JetBrains Mono', monospace; font-size: 15px; color: #eee; font-variant-numeric: tabular-nums; }
      .fvsc .s { font-size: 9.5px; color: #7a7a7a; margin-top: 4px; }

      .lista { display: flex; flex-direction: column; }
      .li { display: flex; justify-content: space-between; align-items: center; padding: 9px 2px; border-bottom: 1px solid #181818; font-size: 12.5px; }
      .li .d { color: #7a7a7a; font-family: 'JetBrains Mono', monospace; font-size: 10.5px; width: 44px; flex-shrink: 0; }
      .li .n { flex: 1; color: #ccc; padding: 0 6px; }
      .li .v { font-family: 'JetBrains Mono', monospace; font-variant-numeric: tabular-nums; color: #e8e8e8; }
      .mais { width: 100%; text-align: center; padding: 10px; margin-top: 8px; border: 1px dashed #2a2a2a; border-radius: 5px; color: #8a8a8a; font-size: 11.5px; background: transparent; min-height: 44px; }

      .assin-toggle, .extrato-toggle { width: 100%; display: flex; justify-content: space-between; align-items: center; padding: 12px; border: 1px solid #202020; border-radius: 6px; background: #050505; color: #ccc; font-size: 12.5px; margin-bottom: 10px; min-height: 44px; }
      .assin-toggle svg, .extrato-toggle svg { width: 14px; height: 14px; color: ${AC}; }
      .assin-list, .extrato-list { display: none; }
      .assin-list.open, .extrato-list.open { display: block; }
      .assin-row { display: flex; justify-content: space-between; padding: 8px 2px; font-size: 12px; border-bottom: 1px solid #161616; color: #bbb; }

      /* vida */
      .faixa { display: flex; gap: 10px; overflow-x: auto; padding: 4px 2px 14px; scrollbar-width: none; }
      .faixa::-webkit-scrollbar { display: none; }
      .sec { flex-shrink: 0; width: 66px; display: flex; flex-direction: column; align-items: center; gap: 7px; }
      .sec .ico { width: 46px; height: 46px; border-radius: 50%; border: 1px solid #262626; display: flex; align-items: center; justify-content: center; background: #060606; }
      .sec .ico svg { width: 18px; height: 18px; color: ${AC}; }
      .sec.on .ico { border-color: ${AC}; }
      .sec span { font-size: 9.5px; color: #9a9a9a; text-align: center; line-height: 1.15; }
      .painel-vida { border: 1px solid #202020; border-radius: 6px; padding: 14px; }
      .painel-vida h3 { margin: 0 0 6px; font-size: 14px; color: #f0f0f0; font-weight: 500; }
      .painel-vida p { margin: 4px 0; font-size: 12px; color: #999; line-height: 1.5; }
      .viagem-box { margin-top: 12px; border-top: 1px solid #1c1c1c; padding-top: 10px; font-size: 11.5px; color: #9a9a9a; }
      .viagem-box b { color: ${AC}; }

      .navbar { position: absolute; left: 0; right: 0; bottom: 0; display: flex; border-top: 1px solid #1c1c1c; background: #020202; }
      .navbtn { flex: 1; min-height: 54px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; background: transparent; border: none; color: #666; }
      .navbtn svg { width: 17px; height: 17px; }
      .navbtn.on { color: ${AC}; }
      .navbtn span { font-size: 9px; letter-spacing: .05em; text-transform: uppercase; }
    </style>
    <div class="wrap" id="wrap"></div>
    `;

    const wrap = root.getElementById("wrap");

    function svgArc(cx, cy, r, pct, color, w) {
      pct = Math.max(0, Math.min(1, pct));
      const c = 2 * Math.PI * r;
      return `<circle class="ring-val" cx="${cx}" cy="${cy}" r="${r}" stroke-width="${w}"
        stroke-dasharray="${c}" stroke-dashoffset="${c * (1 - pct)}"
        transform="rotate(-90 ${cx} ${cy})" style="stroke:${color}"/>`;
    }
    function svgTrack(cx, cy, r, w) {
      return `<circle class="ring-track" cx="${cx}" cy="${cy}" r="${r}" stroke-width="${w}"/>`;
    }

    function telaHoje() {
      const clima = D.hoje.clima || {};
      const pctMes = fin.gasto_mes_anterior ? fin.gasto_mes / fin.gasto_mes_anterior : 0.5;
      wrap.innerHTML = `
        ${D.aviso_critico ? `<div class="aviso">${ICONS.alerta}<span>${D.aviso_critico}</span></div>` : ""}
        <div class="row topbar">
          <button class="mic" id="mic">${ICONS.mic}</button>
          <div class="clock">
            <div class="hh mono" id="relogio">--:--</div>
            <div class="dd">${D.hoje.data} · ${D.hoje.cidade}</div>
          </div>
          <div class="clima">${ICONS.chuva}${clima.temp}°C<br><span style="font-size:10px">${clima.cond}, ${clima.chuva_prob}%</span></div>
        </div>
        <div class="reator">
          <svg viewBox="0 0 272 272">
            ${svgTrack(136, 136, 122, 1)}${svgTrack(136, 136, 104, 6)}${svgTrack(136, 136, 88, 1)}
            <g class="spin" id="ringOuter">${svgArc(136, 136, 122, 1, "#333", 1)}</g>
            <g id="ringMain">${svgArc(136, 136, 104, 0, AC, 6)}</g>
            <g class="spin" id="ringInner">${svgArc(136, 136, 88, 1, "#333", 1)}</g>
          </svg>
          <div class="center">
            <div class="lbl">Gasto do mês</div>
            <div class="num mono" id="numGasto">R$ 0,00</div>
            <div class="cmp">vs mês anterior <b>${fmt(fin.gasto_mes_anterior || 0)}</b></div>
          </div>
        </div>
        <div class="leituras">
          <div class="leitura"><div class="l1">Hoje</div><div class="l2">${fmt(fin.gasto_hoje || 0)}</div></div>
          <div class="leitura"><div class="l1">Fatura</div><div class="l2">${fmt(fin.fatura_atual || 0)}</div></div>
          <div class="leitura"><div class="l1">Conta</div><div class="l2">${fmt(fin.saldo_conta || 0)}</div></div>
        </div>
        <div class="divider"></div>
        <div class="foco">
          <div class="l1">Em foco agora</div>
          <div class="l2">${(D.tarefas && D.tarefas.em_foco) || "—"}</div>
        </div>
        <div class="atalhos">
          <button class="atalho" data-t="financas">${ICONS.financas}<span>Finanças</span></button>
          <button class="atalho" data-t="vida">${ICONS.vida}<span>Vida</span></button>
          <button class="atalho" data-t="vida">${ICONS.tarefas}<span>Tarefas</span></button>
          <button class="atalho" data-t="vida">${ICONS.aviacao}<span>Aviação</span></button>
        </div>
        <div class="chatbar">
          <input placeholder="Falar com o painel…" />
          <button>${ICONS.enviar}</button>
        </div>
      `;
      wrap.querySelectorAll(".atalho").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.t)));

      function tick() {
        const el = root.getElementById("relogio");
        if (!el) return;
        const now = new Date();
        el.textContent = now.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
      }
      tick();
      if (!ctx.reduzido) timers.push(setInterval(tick, 1000 * 15));

      // count-up + arc fill
      const numEl = root.getElementById("numGasto");
      const target = fin.gasto_mes || 0;
      const dur = ctx.reduzido ? 0 : 900;
      const t0 = performance.now();
      function step(t) {
        const p = dur ? Math.min(1, (t - t0) / dur) : 1;
        const eased = 1 - Math.pow(1 - p, 3);
        numEl.textContent = fmt(target * eased);
        const arc = root.getElementById("ringMain");
        if (arc) arc.innerHTML = svgArc(136, 136, 104, eased * Math.min(1, pctMes), AC, 6).match(/stroke-dasharray[^\/]+/)[0]
          ? svgArc(136, 136, 104, eased * Math.min(1, pctMes), AC, 6) : "";
        if (arc) arc.innerHTML = svgArc(136, 136, 104, eased * Math.min(1, pctMes), AC, 6);
        if (p < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);

      if (!ctx.reduzido) {
        let a1 = 0, a2 = 0;
        function spin() {
          a1 = (a1 + 0.15) % 360; a2 = (a2 - 0.22) % 360;
          const o = root.getElementById("ringOuter"), i = root.getElementById("ringInner");
          if (o) o.style.transform = `rotate(${a1}deg)`;
          if (i) i.style.transform = `rotate(${a2}deg)`;
          raf = requestAnimationFrame(spin);
        }
        let raf = requestAnimationFrame(spin);
        cleanups.push(() => cancelAnimationFrame(raf));
      }
    }

    function telaFinancas() {
      const cats = fin.por_categoria || [];
      const total = cats.reduce((s, c) => s + c.valor, 0) || 1;
      const colors = cats.map((_, i) => {
        const t = i / Math.max(1, cats.length - 1);
        return `hsl(${188 - t * 40}, ${70 - t * 20}%, ${58 - t * 18}%)`;
      });
      let acc = 0;
      const c = 2 * Math.PI * 108;
      const gap = 3;
      const arcs = cats.map((cat, i) => {
        const frac = cat.valor / total;
        const len = Math.max(0, frac * c - gap);
        const off = acc;
        acc += frac * c;
        const r = 108 - i * 13;
        const cc = 2 * Math.PI * r;
        const l2 = Math.max(0, frac * cc - gap);
        return `<circle class="ring-val" cx="130" cy="130" r="${r}" stroke-width="9"
          stroke-dasharray="${l2} ${cc}" stroke-dashoffset="${cc * 0.25}"
          style="stroke:${colors[i]}" transform="rotate(${(acc - frac * c) / c * 360 * 0} 130 130)"/>`;
      });
      // simpler: independent concentric arcs each showing its own share of that ring (proportion of max)
      const maxCat = Math.max(...cats.map(c => c.valor), 1);
      const ringsHtml = cats.slice(0, 6).map((cat, i) => {
        const r = 118 - i * 15;
        const pct = cat.valor / maxCat;
        return svgTrack(130, 130, r, 8) + svgArc(130, 130, r, pct, colors[i], 8);
      }).join("");

      const dias = fin.ultimos_15_dias || [];
      const idShow = "listaDias";

      wrap.innerHTML = `
        <div class="tab-title">Finanças</div>
        <div class="cat-ring">
          <svg viewBox="0 0 260 260">${ringsHtml}</svg>
          <div class="cat-center">
            <div class="num mono">${fmt(fin.gasto_mes || 0)}</div>
            <div class="lbl">mês atual</div>
          </div>
        </div>
        <div class="legenda">
          ${cats.slice(0, 6).map((cat, i) => `
            <div class="leg-item"><span class="leg-dot" style="background:${colors[i]}"></span>
            <span class="leg-nome">${cat.categoria}</span><span class="leg-val mono">${fmt(cat.valor)}</span></div>
          `).join("")}
        </div>
        <div class="card">
          <div class="t1">Fatura × Conta</div>
          <div class="fvsc">
            <div class="item"><div class="n mono">${fmt(fin.fatura_atual || 0)}</div><div class="s">fatura · vence ${fin.fatura_vencimento ? fin.fatura_vencimento.slice(8, 10) + "/" + fin.fatura_vencimento.slice(5, 7) : "—"}</div></div>
            <div class="item"><div class="n mono">${fmt(fin.saldo_conta || 0)}</div><div class="s">saldo em conta</div></div>
          </div>
        </div>
        <div class="card">
          <div class="t1">Últimos dias</div>
          <div class="lista" id="${idShow}">
            ${dias.slice(0, 6).map(li).join("")}
          </div>
          ${dias.length > 6 ? `<button class="mais" id="btnMais">carregar mais (${dias.length - 6})</button>` : ""}
        </div>
        <button class="assin-toggle" id="btnAssin"><span>Assinaturas (${(fin.assinaturas || []).length})</span>${ICONS.seta}</button>
        <div class="assin-list" id="assinList">
          ${(fin.assinaturas || []).map(a => `<div class="assin-row"><span>${a.nome}</span><span class="mono">${fmt(a.valor)}</span></div>`).join("")}
        </div>
        <button class="extrato-toggle" id="btnExtrato"><span>Extrato completo</span>${ICONS.seta}</button>
        <div class="extrato-list" id="extratoList">
          ${dias.map(li).join("")}
        </div>
      `;

      function li(d) {
        const dd = d.data.slice(8, 10) + "/" + d.data.slice(5, 7);
        return `<div class="li"><span class="d mono">${dd}</span><span class="n">${d.descricao}</span><span class="v">${fmt(Math.abs(d.valor))}</span></div>`;
      }

      const btnMais = root.getElementById("btnMais");
      if (btnMais) btnMais.addEventListener("click", () => {
        root.getElementById(idShow).innerHTML = dias.map(li).join("");
        btnMais.remove();
      });
      root.getElementById("btnAssin").addEventListener("click", () => root.getElementById("assinList").classList.toggle("open"));
      root.getElementById("btnExtrato").addEventListener("click", () => root.getElementById("extratoList").classList.toggle("open"));
    }

    function telaVida() {
      const secs = D.vida_secoes || [];
      let atual = secs[0] ? secs[0].id : null;
      wrap.innerHTML = `
        <div class="tab-title">Vida</div>
        <div class="faixa" id="faixa"></div>
        <div class="painel-vida" id="painel"></div>
      `;
      const ICOSET = [ICONS.vida, ICONS.tarefas, ICONS.financas, ICONS.aviacao, ICONS.alerta, ICONS.chuva];
      const faixa = root.getElementById("faixa");
      faixa.innerHTML = secs.map((s, i) => `
        <div class="sec ${s.id === atual ? "on" : ""}" data-id="${s.id}">
          <div class="ico">${ICOSET[i % ICOSET.length]}</div>
          <span>${s.nome}</span>
        </div>`).join("");

      function painel(id) {
        const s = secs.find(x => x.id === id);
        if (!s) return;
        const p = root.getElementById("painel");
        p.innerHTML = `
          <h3>${s.nome}</h3>
          <p>${s.resumo}</p>
          <p>Última atualização registrada nesta seção.</p>
          <p>Toque em outro ícone acima para trocar de contexto.</p>
          ${D.viagem ? `<div class="viagem-box">Próxima viagem: <b>${D.viagem.origem} → ${D.viagem.destino}</b> em ${D.viagem.dias_faltando} dias (${D.viagem.data})</div>` : ""}
        `;
      }
      painel(atual);
      faixa.querySelectorAll(".sec").forEach(el => el.addEventListener("click", () => {
        atual = el.dataset.id;
        faixa.querySelectorAll(".sec").forEach(x => x.classList.toggle("on", x.dataset.id === atual));
        painel(atual);
      }));
    }

    function nav() {
      const tabs = [["hoje", ICONS.mic, "Hoje"], ["financas", ICONS.financas, "Finanças"], ["vida", ICONS.vida, "Vida"]];
      const bar = document.createElement("div");
      bar.className = "navbar";
      bar.innerHTML = tabs.map(([t, ic, lb]) => `<button class="navbtn ${ctx.tela === t ? "on" : ""}" data-t="${t}">${ic}<span>${lb}</span></button>`).join("");
      wrap.style.paddingBottom = "76px";
      wrap.after(bar);
      bar.querySelectorAll("button").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.t)));
      cleanups.push(() => bar.remove());
    }

    if (ctx.tela === "hoje") telaHoje();
    else if (ctx.tela === "financas") telaFinancas();
    else telaVida();
    nav();

    return () => {
      timers.forEach(clearInterval);
      cleanups.forEach(fn => fn());
    };
  }
};
