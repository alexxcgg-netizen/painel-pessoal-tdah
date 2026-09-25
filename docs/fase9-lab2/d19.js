(window.DIRECOES = window.DIRECOES || {})[19] = {
  nome: "Braun",
  ideia: "Objeto industrial anos 60: mostradores, escalas com marcas finas, botões físicos redondos/retangulares, grade rigorosa.",
  acento: "#FF6A13",
  fontes: ["Inter+Tight:wght@400;500;600;700"],
  render(root, D, ctx) {
    const AC = "#FF6A13";
    const fmt = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
    const fin = D.financas || {};
    const timers = [];
    const cleanups = [];

    const ICONS = {
      mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/><path d="M8 21h8"/></svg>',
      financas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="9"/><path d="M12 7v10M9 9.5c0-1.4 1.3-2 3-2s3 .8 3 2-1.3 1.8-3 2-3 .8-3 2 1.3 2 3 2 3-.6 3-2"/></svg>',
      vida: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>',
      alerta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 3l10 18H2L12 3z"/><path d="M12 10v4M12 17h.01"/></svg>',
      chevron: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6"/></svg>',
      enviar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 12l16-8-6 16-3-7-7-1z"/></svg>'
    };

    function areaChart(dias, w, h, pad) {
      pad = pad || 4;
      const vals = dias.map(d => d.acumulado);
      const max = Math.max.apply(null, vals.concat([1]));
      const n = vals.length;
      const pts = vals.map((v, i) => [(i / (n - 1)) * (w - 2 * pad) + pad, h - pad - (v / max) * (h - 2 * pad)]);
      const line = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
      return { line, x0: pts[0][0], x1: pts[n - 1][0] };
    }

    root.innerHTML = `
    <style>
      :host, * { box-sizing: border-box; }
      .wrap { font-family: 'Inter Tight', sans-serif; color: #1c1a17; background: #EDEBE6; padding: 14px 14px 92px; min-height: 760px; position: relative; }
      .lbl { font-size: 9.5px; color: #6b675f; text-transform: uppercase; letter-spacing: .1em; font-weight: 600; }
      .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
      .win { background: #26241f; border-radius: 6px; padding: 10px 12px; }
      .win .lbl { color: #8a867c; }
      .win .val { color: ${AC}; font-size: 20px; font-weight: 700; font-variant-numeric: tabular-nums; margin-top: 3px; }
      .win .sub { color: #b9b6ac; font-size: 10.5px; margin-top: 3px; }
      .plate { background: #E3E0D7; border: 1px solid #c9c5b8; border-radius: 8px; padding: 12px 14px; }
      .aviso-strip { display: flex; align-items: center; gap: 8px; background: #1c1a17; color: #EDEBE6; padding: 9px 12px; border-radius: 6px; margin-bottom: 10px; font-size: 11.5px; font-weight: 600; }
      .aviso-strip svg { width: 15px; height: 15px; color: ${AC}; flex-shrink: 0; }
      .divider { height: 1px; background: #c9c5b8; margin: 16px 0; }
      .grp-lbl { font-size: 10px; color: #6b675f; text-transform: uppercase; letter-spacing: .12em; font-weight: 700; margin: 0 0 8px 2px; }

      .dial-wrap { display: flex; flex-direction: column; align-items: center; margin: 4px 0 14px; }
      .dial-wrap svg { width: 220px; height: 140px; }
      .dial-readout { text-align: center; margin-top: -6px; }
      .dial-readout .val { font-size: 26px; font-weight: 700; font-variant-numeric: tabular-nums; letter-spacing: -.01em; }
      .dial-readout .sub { font-size: 11px; color: #6b675f; margin-top: 2px; }

      .key-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 10px; }
      .key { background: #E3E0D7; border: 1px solid #c9c5b8; border-radius: 8px; padding: 10px 8px; text-align: center; min-height: 54px; }
      .key .v { font-size: 14px; font-weight: 700; font-variant-numeric: tabular-nums; color: #1c1a17; }
      .key .l { font-size: 8.5px; color: #6b675f; text-transform: uppercase; letter-spacing: .06em; margin-top: 4px; font-weight: 600; }

      .btnrow { display: flex; gap: 10px; align-items: center; margin-bottom: 12px; }
      .round-btn { width: 52px; height: 52px; border-radius: 50%; background: #E3E0D7; border: 1px solid #c9c5b8; box-shadow: 0 1.5px 0 #c9c5b8; color: #1c1a17; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
      .round-btn svg { width: 20px; height: 20px; }
      .rect-btn { flex: 1; display: flex; align-items: center; justify-content: center; gap: 7px; height: 52px; border-radius: 8px; background: #E3E0D7; border: 1px solid #c9c5b8; box-shadow: 0 1.5px 0 #c9c5b8; color: #1c1a17; font-size: 12px; font-weight: 600; }
      .rect-btn svg { width: 15px; height: 15px; color: #1c1a17; }

      .foco-plate { display: flex; flex-direction: column; gap: 3px; margin-bottom: 12px; }
      .foco-plate .v { font-size: 14px; font-weight: 600; margin-top: 2px; }

      .chatbar { display: flex; align-items: center; gap: 8px; border-radius: 8px; padding: 5px 5px 5px 14px; background: #E3E0D7; border: 1px solid #c9c5b8; }
      .chatbar input { flex: 1; background: transparent; border: none; outline: none; color: #1c1a17; font-family: inherit; font-size: 13px; min-width: 0; }
      .chatbar input::placeholder { color: #918d82; }
      .chatbar button { width: 38px; height: 38px; border-radius: 6px; border: 1px solid #c9c5b8; background: ${AC}; color: #1c1a17; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
      .chatbar button svg { width: 15px; height: 15px; }

      /* financas */
      .scale-row { margin-bottom: 14px; }
      .scale-row .top { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px; }
      .scale-row .nome { font-size: 12px; font-weight: 600; }
      .scale-row .val { font-size: 12px; font-variant-numeric: tabular-nums; font-weight: 700; color: #1c1a17; }
      .scale-row svg { width: 100%; height: 22px; display: block; }

      .fvsc-plate { margin-bottom: 14px; }
      .fvsc-plate svg { width: 100%; height: 70px; display: block; }

      .lista { display: flex; flex-direction: column; }
      .li { display: flex; justify-content: space-between; align-items: center; padding: 9px 2px; border-bottom: 1px solid #d6d3c8; font-size: 12.5px; }
      .li .d { color: #6b675f; font-variant-numeric: tabular-nums; font-size: 10.5px; width: 42px; flex-shrink: 0; }
      .li .n { flex: 1; color: #1c1a17; padding: 0 6px; }
      .li .c { color: #918d82; font-size: 10px; }
      .li .v { font-variant-numeric: tabular-nums; color: #1c1a17; font-weight: 700; }
      .mais { width: 100%; text-align: center; padding: 11px; margin-top: 6px; border: 1px dashed #b7b3a6; border-radius: 8px; color: #6b675f; font-size: 11.5px; background: transparent; min-height: 44px; font-family: inherit; }
      .toggle-btn { width: 100%; display: flex; justify-content: space-between; align-items: center; padding: 13px 14px; border: 1px solid #c9c5b8; border-radius: 8px; background: #E3E0D7; color: #1c1a17; font-size: 12.5px; font-weight: 600; margin-bottom: 10px; min-height: 44px; font-family: inherit; }
      .toggle-btn svg { width: 14px; height: 14px; color: #6b675f; transition: transform .2s; }
      .toggle-btn.open svg { transform: rotate(90deg); }
      .panel-list { display: none; background: #E3E0D7; border: 1px solid #c9c5b8; border-radius: 8px; padding: 4px 14px; margin: -4px 0 10px; }
      .panel-list.open { display: block; }
      .assin-row { display: flex; justify-content: space-between; padding: 10px 2px; font-size: 12px; border-bottom: 1px solid #d6d3c8; color: #333; }
      .assin-row:last-child { border-bottom: none; }

      /* vida */
      .keypad { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 12px; }
      .keypad button { background: #E3E0D7; border: 1px solid #c9c5b8; box-shadow: 0 1.5px 0 #c9c5b8; border-radius: 8px; padding: 10px 6px; min-height: 50px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px; font-family: inherit; }
      .keypad button .code { font-size: 13px; font-weight: 700; color: #1c1a17; }
      .keypad button .nm { font-size: 8px; color: #4a4740; text-transform: uppercase; letter-spacing: .03em; text-align: center; line-height: 1.1; font-weight: 600; }
      .keypad button.on { background: #1c1a17; border-color: #1c1a17; }
      .keypad button.on .code { color: ${AC}; }
      .keypad button.on .nm { color: #EDEBE6; }
      .readout-plate { background: #26241f; border-radius: 8px; padding: 14px; margin-bottom: 14px; }
      .readout-plate h3 { margin: 0; font-size: 14px; font-weight: 700; color: #EDEBE6; }
      .readout-plate p { margin: 6px 0 0; font-size: 11.5px; color: #b9b6ac; line-height: 1.5; }
      .readout-plate b { color: ${AC}; }
      .readout-plate svg { display: block; margin-top: 8px; }

      .navbar { position: absolute; left: 0; right: 0; bottom: 0; display: flex; gap: 8px; padding: 10px 14px; background: linear-gradient(0deg,#EDEBE6 65%,transparent); }
      .navbtn { flex: 1; min-height: 48px; display: flex; align-items: center; justify-content: center; gap: 6px; background: #E3E0D7; border: 1px solid #c9c5b8; box-shadow: 0 1.5px 0 #c9c5b8; border-radius: 8px; color: #4a4740; font-family: inherit; }
      .navbtn svg { width: 14px; height: 14px; }
      .navbtn.on { background: #1c1a17; border-color: #1c1a17; color: ${AC}; box-shadow: none; }
      .navbtn span { font-size: 10px; font-weight: 700; letter-spacing: .03em; text-transform: uppercase; }
    </style>
    <div class="wrap" id="wrap"></div>
    `;
    const wrap = root.getElementById("wrap");

    function ticks(n) {
      let s = "";
      const w = 220;
      for (let i = 0; i <= n; i++) {
        const x = (i / n) * w;
        const major = i % 5 === 0;
        s += `<line x1="${x}" y1="0" x2="${x}" y2="${major ? 8 : 4}" stroke="#918d82" stroke-width="1"/>`;
      }
      return s;
    }

    function telaHoje() {
      const clima = D.hoje.clima || {};
      const dias = fin.por_dia_mes || [];
      const max = Math.max(fin.gasto_mes_anterior || 0, fin.gasto_mes || 0, 1);
      const pct = Math.max(0, Math.min(1, (fin.gasto_mes || 0) / max));
      const ang = -90 + pct * 180;
      const cx = 110, cy = 118, r = 92;
      const rad = (ang) * Math.PI / 180;
      const nx = cx + r * 0.82 * Math.cos(rad), ny = cy + r * 0.82 * Math.sin(rad);
      const ch = areaChart(dias, 210, 40, 2);
      const venc = fin.fatura_vencimento ? fin.fatura_vencimento.slice(8, 10) + "/" + fin.fatura_vencimento.slice(5, 7) : "—";

      function arcPath(pFrom, pTo, radius) {
        const a0 = -180 + pFrom * 180, a1 = -180 + pTo * 180;
        const r0 = a0 * Math.PI / 180, r1 = a1 * Math.PI / 180;
        const x0 = cx + radius * Math.cos(r0), y0 = cy + radius * Math.sin(r0);
        const x1 = cx + radius * Math.cos(r1), y1 = cy + radius * Math.sin(r1);
        return `M${x0.toFixed(1)},${y0.toFixed(1)} A${radius},${radius} 0 0 1 ${x1.toFixed(1)},${y1.toFixed(1)}`;
      }
      const majorTicks = [];
      for (let i = 0; i <= 10; i++) {
        const a = -180 + (i / 10) * 180, rad2 = a * Math.PI / 180;
        const r1 = 92, r2 = i % 5 === 0 ? 82 : 87;
        majorTicks.push(`<line x1="${(cx + r1 * Math.cos(rad2)).toFixed(1)}" y1="${(cy + r1 * Math.sin(rad2)).toFixed(1)}" x2="${(cx + r2 * Math.cos(rad2)).toFixed(1)}" y2="${(cy + r2 * Math.sin(rad2)).toFixed(1)}" stroke="#918d82" stroke-width="${i % 5 === 0 ? 1.6 : 1}"/>`);
      }

      wrap.innerHTML = `
        ${D.aviso_critico ? `<div class="aviso-strip">${ICONS.alerta}<span>${D.aviso_critico}</span></div>` : ""}
        <div class="grid2">
          <div class="win">
            <div class="lbl">Hora / data</div>
            <div class="val" id="relogio">--:--</div>
            <div class="sub">${D.hoje.data.split("-").reverse().join("/")} · ${D.hoje.cidade}</div>
          </div>
          <div class="win">
            <div class="lbl">Clima</div>
            <div class="val">${clima.temp}°C</div>
            <div class="sub">${clima.cond} · ${clima.chuva_prob}% chuva</div>
          </div>
        </div>
        <div class="divider"></div>
        <div class="grp-lbl">Gasto do mês</div>
        <div class="dial-wrap">
          <svg viewBox="0 0 220 128">
            <path d="${arcPath(0, 1, 92)}" fill="none" stroke="#c9c5b8" stroke-width="2"/>
            <path d="${arcPath(0, Math.min(1, pct), 92)}" fill="none" stroke="${AC}" stroke-width="3"/>
            ${majorTicks.join("")}
            <line x1="${cx}" y1="${cy}" x2="${nx.toFixed(1)}" y2="${ny.toFixed(1)}" stroke="#1c1a17" stroke-width="2" stroke-linecap="round" id="needle"/>
            <circle cx="${cx}" cy="${cy}" r="4" fill="#1c1a17"/>
          </svg>
          <div class="dial-readout">
            <div class="val" id="numGasto">R$ 0,00</div>
            <div class="sub">escala até ${fmt(max)} · mês anterior ${fmt(fin.gasto_mes_anterior || 0)}</div>
          </div>
        </div>
        <div class="key-row">
          <div class="key"><div class="v">${fmt(fin.gasto_hoje || 0)}</div><div class="l">Hoje</div></div>
          <div class="key"><div class="v">${fmt(fin.fatura_atual || 0)}</div><div class="l">Fatura · ${venc}</div></div>
          <div class="key"><div class="v">${fmt(fin.saldo_conta || 0)}</div><div class="l">Conta</div></div>
        </div>
        <div class="plate foco-plate">
          <div class="lbl">Em foco agora</div>
          <div class="v">${(D.tarefas && D.tarefas.em_foco) || "—"}</div>
        </div>
        <div class="btnrow">
          <button class="round-btn" id="mic" aria-label="Comando de voz">${ICONS.mic}</button>
          <button class="rect-btn" data-t="financas">${ICONS.financas}Finanças</button>
          <button class="rect-btn" data-t="vida">${ICONS.vida}Vida</button>
        </div>
        <div class="chatbar">
          <input placeholder="Pergunte algo…" />
          <button>${ICONS.enviar}</button>
        </div>
      `;
      wrap.querySelectorAll("[data-t]").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.t)));

      function tick() {
        const el = root.getElementById("relogio");
        if (el) el.textContent = new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
      }
      tick();
      timers.push(setInterval(tick, 15000));

      const numEl = root.getElementById("numGasto");
      const needle = root.getElementById("needle");
      const target = fin.gasto_mes || 0;
      const dur = ctx.reduzido ? 0 : 650;
      const t0 = performance.now();
      (function step(t) {
        const p = dur ? Math.min(1, (t - t0) / dur) : 1;
        const eased = 1 - Math.pow(1 - p, 3);
        numEl.textContent = fmt(target * eased);
        const a = -180 + Math.min(1, pct * eased) * 180, rad2 = a * Math.PI / 180;
        const nx2 = cx + r * 0.82 * Math.cos(rad2), ny2 = cy + r * 0.82 * Math.sin(rad2);
        if (needle) { needle.setAttribute("x2", nx2.toFixed(1)); needle.setAttribute("y2", ny2.toFixed(1)); }
        if (p < 1) requestAnimationFrame(step);
      })(t0);
    }

    function telaFinancas() {
      const cats = (fin.por_categoria || []).slice().sort((a, b) => b.valor - a.valor);
      const maxCat = cats[0] ? cats[0].valor : 1;
      const dias = fin.por_dia_mes || [];
      const ultimos = fin.ultimos_15_dias || [];
      const delta = fin.gasto_mes_anterior ? Math.round((1 - fin.gasto_mes / fin.gasto_mes_anterior) * 100) : 0;
      const venc = fin.fatura_vencimento ? fin.fatura_vencimento.slice(8, 10) + "/" + fin.fatura_vencimento.slice(5, 7) : "—";
      const ch = areaChart(dias, 300, 90, 6);

      function scaleRow(cat) {
        const pct = Math.max(0.02, cat.valor / maxCat);
        const w = 300;
        const nx = 6 + pct * (w - 12);
        return `
        <div class="scale-row">
          <div class="top"><span class="nome">${cat.categoria}</span><span class="val">${fmt(cat.valor)}</span></div>
          <svg viewBox="0 0 ${w} 22">
            <line x1="6" y1="16" x2="${w - 6}" y2="16" stroke="#c9c5b8" stroke-width="1.5"/>
            ${Array.from({ length: 11 }, (_, i) => {
          const x = 6 + (i / 10) * (w - 12);
          return `<line x1="${x}" y1="${i % 5 === 0 ? 10 : 13}" x2="${x}" y2="16" stroke="#918d82" stroke-width="1"/>`;
        }).join("")}
            <line x1="6" y1="16" x2="${nx.toFixed(1)}" y2="16" stroke="${AC}" stroke-width="3" stroke-linecap="round"/>
            <path d="M${nx.toFixed(1)},4 l5,8 h-10 z" fill="#1c1a17"/>
          </svg>
        </div>`;
      }

      wrap.innerHTML = `
        <div class="grid2">
          <div class="win">
            <div class="lbl">Gasto do mês</div>
            <div class="val">${fmt(fin.gasto_mes || 0)}</div>
            <div class="sub">${delta >= 0 ? "▼" : "▲"} ${Math.abs(delta)}% vs anterior</div>
          </div>
          <div class="win">
            <div class="lbl">Orçamento</div>
            <div class="val" style="font-size:14px">${fin.orcamento_mes ? fmt(fin.orcamento_mes) : "não def."}</div>
            <div class="sub">mês ${fin.mes || ""}</div>
          </div>
        </div>
        <div class="divider"></div>
        <div class="grp-lbl">Evolução do mês por dia</div>
        <div class="fvsc-plate">
          <svg viewBox="0 0 300 90">
            <line x1="6" y1="84" x2="294" y2="84" stroke="#c9c5b8" stroke-width="1"/>
            <line x1="6" y1="45" x2="294" y2="45" stroke="#d6d3c8" stroke-width="1"/>
            <path d="${ch.line}" fill="none" stroke="#1c1a17" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="${ch.line}" fill="none" stroke="${AC}" stroke-width="1" stroke-dasharray="1 3" stroke-linecap="round"/>
            <text x="6" y="14" font-size="9" fill="#6b675f" font-family="Inter Tight">R$ 0</text>
            <text x="6" y="96" font-size="9" fill="#6b675f" font-family="Inter Tight">dia 1</text>
            <text x="294" y="96" text-anchor="end" font-size="9" fill="#6b675f" font-family="Inter Tight">dia ${dias.length} · ${fmt(fin.gasto_mes || 0)}</text>
          </svg>
        </div>
        <div class="grp-lbl">Gasto por categoria — escala linear</div>
        ${cats.map(scaleRow).join("")}
        <div class="divider"></div>
        <div class="grp-lbl">Fatura × conta</div>
        <div class="key-row" style="grid-template-columns:1fr 1fr">
          <div class="key"><div class="v">${fmt(fin.fatura_atual || 0)}</div><div class="l">Fatura · vence ${venc}</div></div>
          <div class="key"><div class="v">${fmt(fin.saldo_conta || 0)}</div><div class="l">Saldo em conta</div></div>
        </div>
        <div class="fvsc-plate" style="margin-top:10px">
          <svg viewBox="0 0 300 40">
            <rect x="0" y="4" width="300" height="12" rx="6" fill="#d6d3c8"/>
            <rect x="0" y="4" width="300" height="12" rx="6" fill="${AC}"/>
            <rect x="0" y="24" width="300" height="12" rx="6" fill="#d6d3c8"/>
            <rect x="0" y="24" width="${Math.max(8, Math.min(300, (fin.saldo_conta || 0) / (fin.fatura_atual || 1) * 300))}" height="12" rx="6" fill="#1c1a17"/>
          </svg>
        </div>
        <div class="grp-lbl" style="margin-top:14px">Últimos 15 dias</div>
        <div class="lista" id="listaDias">${ultimos.slice(0, 6).map(li).join("")}</div>
        ${ultimos.length > 6 ? `<button class="mais" id="btnMais">mostrar mais (${ultimos.length - 6})</button>` : ""}
        <button class="toggle-btn" id="btnAssin" style="margin-top:14px"><span>Assinaturas (${(fin.assinaturas || []).length})</span>${ICONS.chevron}</button>
        <div class="panel-list" id="assinList">
          ${(fin.assinaturas || []).map(a => `<div class="assin-row"><span>${a.nome}</span><span>${fmt(a.valor)}</span></div>`).join("")}
        </div>
        <button class="toggle-btn" id="btnExtrato"><span>Extrato completo</span>${ICONS.chevron}</button>
        <div class="panel-list" id="extratoList">${ultimos.map(li).join("")}</div>
      `;
      function li(d) {
        const dd = d.data.slice(8, 10) + "/" + d.data.slice(5, 7);
        return `<div class="li"><span class="d">${dd}</span><span class="n">${d.descricao}<br><span class="c">${d.categoria}</span></span><span class="v">${fmt(Math.abs(d.valor))}</span></div>`;
      }
      const btnMais = root.getElementById("btnMais");
      if (btnMais) btnMais.addEventListener("click", () => { root.getElementById("listaDias").innerHTML = ultimos.map(li).join(""); btnMais.remove(); });
      root.getElementById("btnAssin").addEventListener("click", (e) => { e.currentTarget.classList.toggle("open"); root.getElementById("assinList").classList.toggle("open"); });
      root.getElementById("btnExtrato").addEventListener("click", (e) => { e.currentTarget.classList.toggle("open"); root.getElementById("extratoList").classList.toggle("open"); });
    }

    function seedVals(id, n) {
      let h = 0; for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
      const arr = [];
      for (let i = 0; i < n; i++) { h = (h * 1103515245 + 12345) >>> 0; arr.push(0.15 + (h % 100) / 100 * 0.82); }
      return arr;
    }

    function telaVida() {
      const secs = D.vida_secoes || [];
      let atual = secs[0] ? secs[0].id : null;
      wrap.innerHTML = `
        <div class="readout-plate" id="readout"></div>
        <div class="grp-lbl">Teclado de seções</div>
        <div class="keypad" id="keypad"></div>
      `;
      const codes = secs.map(s => s.nome.replace(/[^A-Za-zÀ-ú]/g, "").slice(0, 2).toUpperCase());
      const keypad = root.getElementById("keypad");
      keypad.innerHTML = secs.map((s, i) => `
        <button class="${s.id === atual ? "on" : ""}" data-id="${s.id}">
          <span class="code">${codes[i]}</span><span class="nm">${s.nome}</span>
        </button>`).join("");
      function readout(id) {
        const s = secs.find(x => x.id === id);
        if (!s) return;
        const vals = seedVals(s.id, 8);
        const w = 220, h = 34, bw = 20, gap = 6.9;
        const bars = vals.map((v, i) => `<rect x="${(i * (bw + gap)).toFixed(1)}" y="${(h - v * h).toFixed(1)}" width="${bw}" height="${(v * h).toFixed(1)}" fill="${i === vals.length - 1 ? AC : '#4a4740'}"/>`).join("");
        root.getElementById("readout").innerHTML = `
          <h3>${s.nome}</h3>
          <p>${s.resumo}</p>
          ${s.id === "viagens" && D.viagem ? `<p>Próxima viagem: <b>${D.viagem.origem} → ${D.viagem.destino}</b> em ${D.viagem.dias_faltando} dias.</p>` : ""}
          <svg viewBox="0 0 ${w} ${h}" style="width:${w}px;max-width:100%;height:${h}px">${bars}</svg>
          <p style="font-size:9.5px;color:#8a867c">progresso · dado de exemplo</p>
        `;
      }
      readout(atual);
      keypad.querySelectorAll("button").forEach(b => b.addEventListener("click", () => {
        atual = b.dataset.id;
        keypad.querySelectorAll("button").forEach(x => x.classList.toggle("on", x.dataset.id === atual));
        readout(atual);
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

    return () => { timers.forEach(clearInterval); cleanups.forEach(fn => fn()); };
  }
};
