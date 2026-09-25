(window.DIRECOES = window.DIRECOES || {})[12] = {
  nome: "Destaques",
  ideia: "Estilo app de saúde: cartões de destaque com frase em linguagem natural, mini gráfico e tendência com seta.",
  acento: "#FF375F",
  fontes: ["Inter:wght@400;500;600;700"],
  render(root, D, ctx) {
    const AC = "#FF375F";
    const fmt = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
    const fin = D.financas || {};
    const timers = [];
    const cleanups = [];

    const ICONS = {
      mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/><path d="M8 21h8"/></svg>',
      financas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="9"/><path d="M12 7v10M9 9.5c0-1.4 1.3-2 3-2s3 .8 3 2-1.3 1.8-3 2-3 .8-3 2 1.3 2 3 2 3-.6 3-2"/></svg>',
      vida: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>',
      tasks: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 6h16M4 12h16M4 18h10"/><circle cx="20" cy="18" r="2"/></svg>',
      aviacao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 2v20M4 9l16 4M6 20l6-3 6 3"/></svg>',
      chuva: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M7 15a4 4 0 0 1 .8-7.94A5 5 0 0 1 17.6 9.1 3.5 3.5 0 0 1 17 16H7z"/><path d="M8 19l-1 2M12 19l-1 2M16 19l-1 2"/></svg>',
      alerta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 3l10 18H2L12 3z"/><path d="M12 10v4M12 17h.01"/></svg>',
      chevron: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M9 6l6 6-6 6"/></svg>',
      up: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M6 15l6-6 6 6"/></svg>',
      down: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M6 9l6 6 6-6"/></svg>',
      enviar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 12l16-8-6 16-3-7-7-1z"/></svg>'
    };
    const ICOSET = [ICONS.vida, ICONS.tasks, ICONS.financas, ICONS.aviacao, ICONS.chuva, ICONS.mic];

    function sparkPath(vals, w, h, pad) {
      pad = pad || 3;
      const max = Math.max.apply(null, vals.concat([1]));
      const min = Math.min.apply(null, vals.concat([0]));
      const rng = (max - min) || 1;
      const n = vals.length;
      const pts = vals.map((v, i) => [(i / Math.max(1, n - 1)) * (w - 2 * pad) + pad, h - pad - ((v - min) / rng) * (h - 2 * pad)]);
      const line = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
      const area = line + ` L${pts[n - 1][0].toFixed(1)},${h - pad} L${pts[0][0].toFixed(1)},${h - pad} Z`;
      return { line, area, last: pts[n - 1] };
    }

    root.innerHTML = `
    <style>
      :host, * { box-sizing: border-box; }
      .wrap { font-family: 'Inter', sans-serif; color: #f0f0f0; background: #000; padding: 14px 14px 88px; min-height: 760px; position: relative; }
      .head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
      .head .data { font-size: 21px; font-weight: 700; letter-spacing: -.01em; }
      .head .sub { font-size: 11.5px; color: #8a8a8a; margin-top: 2px; }
      .head-right { display: flex; align-items: center; gap: 10px; }
      .clima-mini { font-size: 12px; color: #a8a8a8; text-align: right; }
      .clima-mini svg { width: 14px; height: 14px; vertical-align: -2px; margin-right: 3px; color: ${AC}; }
      .mic-btn { width: 44px; height: 44px; border-radius: 50%; border: 1px solid #2a2a2a; background: #0d0d0d; color: ${AC}; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
      .mic-btn svg { width: 18px; height: 18px; }
      .aviso { display: flex; gap: 8px; align-items: center; background: rgba(255,55,95,.12); border: 1px solid rgba(255,55,95,.35); color: #ff8fa3; font-size: 12px; padding: 10px 12px; border-radius: 14px; margin-bottom: 12px; }
      .aviso svg { width: 15px; height: 15px; flex-shrink: 0; }
      .sec-title { font-size: 12px; font-weight: 700; color: #8a8a8a; text-transform: uppercase; letter-spacing: .05em; margin: 18px 2px 8px; }
      .sec-title:first-of-type { margin-top: 0; }
      .card { background: #111; border-radius: 18px; padding: 16px; margin-bottom: 10px; }
      .card-icon { width: 30px; height: 30px; border-radius: 9px; background: rgba(255,55,95,.16); color: ${AC}; display: flex; align-items: center; justify-content: center; margin-bottom: 10px; }
      .card-icon svg { width: 15px; height: 15px; }
      .card .frase { font-size: 15.5px; font-weight: 600; line-height: 1.35; }
      .card .frase b { color: ${AC}; }
      .card-row { display: flex; align-items: flex-end; justify-content: space-between; margin-top: 10px; }
      .card .num { font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums; }
      .trend { display: flex; align-items: center; gap: 3px; font-size: 12.5px; font-weight: 700; color: ${AC}; }
      .trend svg { width: 13px; height: 13px; }
      .spark { display: block; }
      .rank { display: flex; flex-direction: column; gap: 2px; }
      .rank-row { display: flex; align-items: center; gap: 10px; padding: 9px 2px; border-bottom: 1px solid #1a1a1a; }
      .rank-row:last-child { border-bottom: none; }
      .rank-n { width: 16px; font-size: 11px; color: #7a7a7a; font-weight: 700; flex-shrink: 0; }
      .rank-info { flex: 1; min-width: 0; }
      .rank-nome { font-size: 13px; font-weight: 600; color: #eee; }
      .rank-bar-track { height: 5px; border-radius: 3px; background: #1e1e1e; margin-top: 5px; overflow: hidden; }
      .rank-bar-fill { height: 100%; border-radius: 3px; background: ${AC}; }
      .rank-val { font-size: 12.5px; font-weight: 700; font-variant-numeric: tabular-nums; color: #fff; flex-shrink: 0; }
      .lista { display: flex; flex-direction: column; }
      .li { display: flex; justify-content: space-between; align-items: center; padding: 10px 2px; border-bottom: 1px solid #1a1a1a; font-size: 13px; }
      .li .d { color: #7a7a7a; font-variant-numeric: tabular-nums; font-size: 11px; width: 44px; flex-shrink: 0; }
      .li .n { flex: 1; color: #ddd; padding: 0 6px; }
      .li .c { color: #7a7a7a; font-size: 10.5px; }
      .li .v { font-variant-numeric: tabular-nums; color: #f2f2f2; font-weight: 600; }
      .mais { width: 100%; text-align: center; padding: 12px; margin-top: 4px; border: none; border-radius: 14px; color: #ccc; font-size: 12.5px; background: #111; min-height: 44px; }
      .toggle-btn { width: 100%; display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; border: none; border-radius: 18px; background: #111; color: #eee; font-size: 13px; font-weight: 600; margin-bottom: 10px; min-height: 44px; }
      .toggle-btn svg { width: 15px; height: 15px; color: #8a8a8a; transition: transform .2s; }
      .toggle-btn.open svg { transform: rotate(90deg); }
      .panel-list { display: none; background: #0b0b0b; border-radius: 16px; padding: 4px 14px; margin: -4px 0 10px; }
      .panel-list.open { display: block; }
      .assin-row { display: flex; justify-content: space-between; padding: 10px 2px; font-size: 12.5px; border-bottom: 1px solid #1a1a1a; color: #ccc; }
      .assin-row:last-child { border-bottom: none; }
      .foco-card { display: flex; gap: 12px; align-items: center; }
      .atalhos { display: flex; gap: 8px; margin-bottom: 10px; }
      .pill { flex: 1; display: flex; align-items: center; justify-content: center; gap: 7px; padding: 12px; border-radius: 14px; background: #111; border: none; color: #ddd; font-size: 12.5px; font-weight: 600; min-height: 44px; }
      .pill svg { width: 15px; height: 15px; color: ${AC}; }
      .chatbar { display: flex; align-items: center; gap: 8px; border-radius: 24px; padding: 6px 6px 6px 16px; background: #111; }
      .chatbar input { flex: 1; background: transparent; border: none; outline: none; color: #ddd; font-family: inherit; font-size: 13.5px; min-width: 0; }
      .chatbar input::placeholder { color: #555; }
      .chatbar button { width: 36px; height: 36px; border-radius: 50%; border: none; background: ${AC}; color: #fff; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
      .chatbar button svg { width: 15px; height: 15px; }

      /* vida lista */
      .area-row { background: #111; border-radius: 16px; margin-bottom: 8px; overflow: hidden; }
      .area-head { display: flex; align-items: center; gap: 12px; padding: 13px 14px; min-height: 44px; }
      .area-ico { width: 32px; height: 32px; border-radius: 9px; background: #1a1a1a; color: ${AC}; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
      .area-ico svg { width: 15px; height: 15px; }
      .area-info { flex: 1; min-width: 0; }
      .area-nome { font-size: 13.5px; font-weight: 600; color: #f0f0f0; }
      .area-resumo { font-size: 11.5px; color: #8a8a8a; margin-top: 1px; }
      .area-chev svg { width: 14px; height: 14px; color: #666; transition: transform .2s; }
      .area-row.open .area-chev svg { transform: rotate(90deg); }
      .area-detail { display: none; padding: 0 14px 14px 58px; font-size: 12px; color: #999; line-height: 1.55; }
      .area-row.open .area-detail { display: block; }
      .area-detail b { color: ${AC}; }

      .navbar { position: absolute; left: 0; right: 0; bottom: 0; display: flex; gap: 8px; padding: 10px 14px; background: linear-gradient(0deg,#000 60%,transparent); }
      .navbtn { flex: 1; min-height: 50px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px; background: #111; border: none; border-radius: 16px; color: #777; }
      .navbtn svg { width: 16px; height: 16px; }
      .navbtn.on { background: ${AC}; color: #fff; }
      .navbtn span { font-size: 9px; font-weight: 600; letter-spacing: .02em; }
    </style>
    <div class="wrap" id="wrap"></div>
    `;
    const wrap = root.getElementById("wrap");

    function head() {
      const clima = D.hoje.clima || {};
      return `
        <div class="head">
          <div>
            <div class="data" id="relogio">--:--</div>
            <div class="sub">${D.hoje.data.split("-").reverse().join("/")} · ${D.hoje.cidade}</div>
          </div>
          <div class="head-right">
            <div class="clima-mini">${ICONS.chuva}${clima.temp}°C<br><span>${clima.cond}</span></div>
            <button class="mic-btn" id="mic" aria-label="Comando de voz">${ICONS.mic}</button>
          </div>
        </div>`;
    }

    function telaHoje() {
      const dias = fin.por_dia_mes || [];
      const spark = sparkPath(dias.map(d => d.acumulado), 300, 70, 4);
      const delta = fin.gasto_mes_anterior ? Math.round((1 - fin.gasto_mes / fin.gasto_mes_anterior) * 100) : 0;
      const cobre = fin.fatura_atual ? Math.round((fin.saldo_conta || 0) / fin.fatura_atual * 100) : 0;
      wrap.innerHTML = `
        ${head()}
        ${D.aviso_critico ? `<div class="aviso">${ICONS.alerta}<span>${D.aviso_critico}</span></div>` : ""}
        <div class="card">
          <div class="card-icon">${ICONS.financas}</div>
          <div class="frase">Você já gastou <b>${fmt(fin.gasto_mes || 0)}</b> este mês.</div>
          <svg class="spark" viewBox="0 0 300 70" preserveAspectRatio="none" style="width:100%;height:70px;margin-top:10px">
            <path d="${spark.area}" fill="${AC}" opacity=".14"/>
            <path d="${spark.line}" fill="none" stroke="${AC}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <div class="card-row">
            <span style="font-size:11.5px;color:#8a8a8a">vs ${fmt(fin.gasto_mes_anterior || 0)} no mês anterior</span>
            <span class="trend">${delta >= 0 ? ICONS.down : ICONS.up}${Math.abs(delta)}%</span>
          </div>
        </div>
        <div class="card">
          <div class="card-icon">${ICONS.alerta}</div>
          <div class="frase">Sua conta tem <b>${fmt(fin.saldo_conta || 0)}</b> e a fatura é <b>${fmt(fin.fatura_atual || 0)}</b> — o saldo cobre ${cobre}% dela.</div>
        </div>
        <div class="card foco-card">
          <div class="card-icon" style="margin-bottom:0">${ICONS.tasks}</div>
          <div>
            <div style="font-size:11px;color:#8a8a8a;text-transform:uppercase;letter-spacing:.05em">Em foco agora</div>
            <div style="font-size:14px;font-weight:600;margin-top:3px">${(D.tarefas && D.tarefas.em_foco) || "—"}</div>
          </div>
        </div>
        <div class="atalhos">
          <button class="pill" data-t="financas">${ICONS.financas}Finanças</button>
          <button class="pill" data-t="vida">${ICONS.vida}Vida</button>
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
    }

    function telaFinancas() {
      const cats = (fin.por_categoria || []).slice().sort((a, b) => b.valor - a.valor);
      const total = cats.reduce((s, c) => s + c.valor, 0) || 1;
      const totalMes = fin.gasto_mes || total;
      const dias = fin.por_dia_mes || [];
      const ultimos = fin.ultimos_15_dias || [];
      const delta = fin.gasto_mes_anterior ? Math.round((1 - fin.gasto_mes / fin.gasto_mes_anterior) * 100) : 0;
      const top = cats[0] || { categoria: "—", valor: 0 };
      const topPct = Math.round((top.valor / totalMes) * 100);
      const spark = sparkPath(dias.map(d => d.acumulado), 300, 70, 4);
      const venc = fin.fatura_vencimento ? fin.fatura_vencimento.slice(8, 10) + "/" + fin.fatura_vencimento.slice(5, 7) : "—";
      const cobre = fin.fatura_atual ? Math.round((fin.saldo_conta || 0) / fin.fatura_atual * 100) : 0;

      function catSpark(cat) {
        // curva derivada dos dados reais: acumulado do mês escalado pela participação real da categoria
        const vals = dias.map(d => d.acumulado * (cat.valor / totalMes));
        const s = sparkPath(vals, 96, 32, 2);
        return `<svg viewBox="0 0 96 32" style="width:96px;height:32px;flex-shrink:0"><path d="${s.line}" fill="none" stroke="${AC}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
      }

      wrap.innerHTML = `
        <div class="sec-title">Destaques</div>
        <div class="card">
          <div class="card-icon">${ICONS.financas}</div>
          <div class="frase">Você gastou <b>${Math.abs(delta)}% ${delta >= 0 ? "menos" : "a mais"}</b> que o mês anterior até agora.</div>
          <svg class="spark" viewBox="0 0 300 70" preserveAspectRatio="none" style="width:100%;height:70px;margin-top:10px">
            <path d="${spark.area}" fill="${AC}" opacity=".14"/>
            <path d="${spark.line}" fill="none" stroke="${AC}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <div class="card-row">
            <span style="font-size:11.5px;color:#8a8a8a">${fmt(fin.gasto_mes || 0)} de ${fmt(fin.gasto_mes_anterior || 0)}</span>
            <span class="trend">${delta >= 0 ? ICONS.down : ICONS.up}${Math.abs(delta)}%</span>
          </div>
        </div>
        <div class="card">
          <div class="card-icon">${ICONS.alerta}</div>
          <div class="frase" style="display:flex;justify-content:space-between;align-items:center;gap:10px">
            <span><b>${top.categoria}</b> é sua maior categoria, ${topPct}% do total.</span>
            ${catSpark(top)}
          </div>
          <div class="card-row"><span style="font-size:11.5px;color:#8a8a8a">${fmt(top.valor)} em ${D.hoje.data.slice(0, 7).split("-").reverse().join("/")}</span></div>
        </div>
        <div class="sec-title">Ranking de categorias</div>
        <div class="card">
          <div class="rank">
            ${cats.map((c, i) => `
              <div class="rank-row">
                <span class="rank-n">${i + 1}</span>
                <div class="rank-info">
                  <div class="rank-nome">${c.categoria}</div>
                  <div class="rank-bar-track"><div class="rank-bar-fill" style="width:${Math.max(3, Math.round(c.valor / (cats[0].valor || 1) * 100))}%"></div></div>
                </div>
                <span class="rank-val">${fmt(c.valor)}</span>
              </div>`).join("")}
          </div>
        </div>
        <div class="sec-title">Fatura × conta</div>
        <div class="card">
          <div class="frase" style="font-size:14px">A fatura de <b>${fmt(fin.fatura_atual || 0)}</b> vence em ${venc}. O saldo em conta cobre ${cobre}% dela.</div>
          <svg viewBox="0 0 300 64" style="width:100%;height:64px;display:block;margin-top:10px">
            <text x="0" y="14" font-size="10.5" fill="#aaa" font-family="Inter" font-weight="600">Fatura</text>
            <rect x="60" y="4" width="${300 - 60}" height="14" rx="7" fill="#1e1e1e"/>
            <rect x="60" y="4" width="${300 - 60}" height="14" rx="7" fill="${AC}"/>
            <text x="0" y="46" font-size="10.5" fill="#aaa" font-family="Inter" font-weight="600">Conta</text>
            <rect x="60" y="36" width="${300 - 60}" height="14" rx="7" fill="#1e1e1e"/>
            <rect x="60" y="36" width="${Math.max(6, Math.min(300 - 60, (fin.saldo_conta || 0) / (fin.fatura_atual || 1) * (300 - 60)))}" height="14" rx="7" fill="#555"/>
          </svg>
        </div>
        <div class="sec-title">Últimos 15 dias</div>
        <div class="card">
          <div class="lista" id="listaDias">${ultimos.slice(0, 6).map(li).join("")}</div>
          ${ultimos.length > 6 ? `<button class="mais" id="btnMais">carregar mais (${ultimos.length - 6})</button>` : ""}
        </div>
        <button class="toggle-btn" id="btnAssin"><span>Assinaturas (${(fin.assinaturas || []).length})</span>${ICONS.chevron}</button>
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
      wrap.innerHTML = `
        <div class="sec-title">Suas áreas</div>
        <div id="lista"></div>
      `;
      const lista = root.getElementById("lista");
      lista.innerHTML = secs.map((s, i) => `
        <div class="area-row" data-id="${s.id}">
          <div class="area-head">
            <div class="area-ico">${ICOSET[i % ICOSET.length]}</div>
            <div class="area-info">
              <div class="area-nome">${s.nome}</div>
              <div class="area-resumo">${s.resumo}</div>
            </div>
            <div class="area-chev">${ICONS.chevron}</div>
          </div>
          <div class="area-detail">
            <p>Última atualização registrada nesta seção.</p>
            ${s.id === "viagens" && D.viagem ? `<p>Próxima viagem: <b>${D.viagem.origem} → ${D.viagem.destino}</b> em ${D.viagem.dias_faltando} dias (${D.viagem.data.split("-").reverse().join("/")}).</p>` : ""}
            <svg viewBox="0 0 200 40" style="width:200px;max-width:100%;height:40px;display:block;margin-top:6px">
              ${(() => {
          const vals = seedVals(s.id, 6);
          const bw = 26, gap = 7;
          return vals.map((v, i) => `<rect x="${i * (bw + gap)}" y="${40 - v * 40}" width="${bw}" height="${v * 40}" rx="3" fill="${i === vals.length - 1 ? AC : '#2a2a2a'}"/>`).join("");
        })()}
            </svg>
            <p style="font-size:10.5px;color:#666;margin-top:4px">progresso das últimas semanas · dado de exemplo</p>
          </div>
        </div>`).join("");
      lista.querySelectorAll(".area-row").forEach(el => el.querySelector(".area-head").addEventListener("click", () => el.classList.toggle("open")));
    }

    function nav() {
      const tabs = [["hoje", ICONS.mic, "Hoje"], ["financas", ICONS.financas, "Finanças"], ["vida", ICONS.vida, "Vida"]];
      const bar = document.createElement("div");
      bar.className = "navbar";
      bar.innerHTML = tabs.map(([t, ic, lb]) => `<button class="navbtn ${ctx.tela === t ? "on" : ""}" data-t="${t}">${ic}<span>${lb}</span></button>`).join("");
      wrap.style.paddingBottom = "78px";
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
