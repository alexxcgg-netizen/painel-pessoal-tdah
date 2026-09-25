(window.DIRECOES = window.DIRECOES || {})[8] = {
  nome: "Jornal",
  ideia: "O dia como a capa de um diário pessoal: manchete, colunas finas, gráficos de caderno de economia e cotações.",
  acento: "#AE2A22",
  fontes: ["Newsreader:ital,wght@0,400;0,500;0,600;0,700;1,400", "Source+Sans+3:wght@500;600;700"],
  render(root, D, ctx) {
    const AC = "#AE2A22";
    const fmt = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);
    const fin = D.financas || {};
    const timers = [], cleanups = [];

    function seedRand(str) {
      let h = 0;
      for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0;
      return () => { h = (h * 1664525 + 1013904223) >>> 0; return (h >>> 8) / 16777216; };
    }
    function diaSemana(iso) {
      const d = new Date(iso + "T12:00:00");
      return ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"][d.getDay()];
    }

    const ICONS = {
      mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/><path d="M8 21h8"/></svg>',
      alerta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 3l10 18H2L12 3z"/><path d="M12 10v4M12 17h.01"/></svg>',
      chuva: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M7 15a4 4 0 0 1 .8-7.94A5 5 0 0 1 17.6 9.1 3.5 3.5 0 0 1 17 16H7z"/><path d="M8 19l-1 2M12 19l-1 2M16 19l-1 2"/></svg>',
      chevron: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 6l6 6-6 6"/></svg>',
      hoje: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="5" width="18" height="16" rx="1"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>',
      financas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 20V10M9 20V4M15 20v-7M21 20V8"/></svg>',
      vida: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 19V5a1 1 0 0 1 1-1h11l4 4v11a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1z"/><path d="M8 8h8M8 12h8M8 16h5"/></svg>',
      voltar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M15 6l-6 6 6 6"/></svg>'
    };

    root.innerHTML = `
    <style>
      :host,*{box-sizing:border-box}
      .app{font-family:'Source Sans 3',sans-serif;color:#1a1a1a;background:#F7F4EE;min-height:100%;position:relative;padding-bottom:64px}
      .serif{font-family:'Newsreader',serif}
      .masthead{padding:16px 16px 10px;text-align:center;border-bottom:3px solid #1a1a1a}
      .masthead .titulo{font-family:'Newsreader',serif;font-weight:700;font-size:30px;letter-spacing:.01em}
      .masthead .sub{display:flex;justify-content:space-between;align-items:center;margin-top:6px;font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:#5a564d}
      .masthead .sub .hh{font-variant-numeric:tabular-nums;font-weight:600;color:#1a1a1a}
      .mic{width:44px;height:44px;border-radius:50%;border:1.5px solid #1a1a1a;background:transparent;color:#1a1a1a;display:flex;align-items:center;justify-content:center}
      .mic svg{width:18px;height:18px}
      .col{padding:14px 16px 8px}
      .kicker{font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:${AC};font-weight:700;display:flex;align-items:center;gap:6px}
      .kicker svg{width:13px;height:13px}
      .manchete{font-family:'Newsreader',serif;font-size:25px;line-height:1.18;font-weight:600;margin:6px 0 8px;color:#161616}
      .deck{font-family:'Newsreader',serif;font-style:italic;font-size:14px;color:#4a473f;line-height:1.4;margin:0 0 10px}
      .rule{height:1px;background:#1a1a1a;margin:12px 0}
      .rule.fina{background:#cdc6b4}
      .cols2{display:flex;gap:16px}
      .cols2>div{flex:1}
      .miniart .lbl{font-size:9.5px;letter-spacing:.1em;text-transform:uppercase;color:#8a8578;margin-bottom:3px}
      .miniart .val{font-family:'Newsreader',serif;font-size:15px;font-weight:600;font-variant-numeric:tabular-nums}
      .miniart p{font-size:11.5px;color:#4a473f;line-height:1.4;margin:2px 0 0}
      .secnome{font-family:'Newsreader',serif;font-weight:700;font-size:16px;margin:0 0 8px}
      .chart-bars{width:100%;display:block}
      .chart-bars rect.barra{fill:#1a1a1a}
      .chart-bars line.ref{stroke:${AC};stroke-dasharray:3 3;stroke-width:1}
      .chart-bars text{font-family:'Source Sans 3',sans-serif;font-size:8.5px;fill:#6b6656}
      .chart-bars text.reflbl{fill:${AC}}
      .chart-line{width:100%;display:block}
      .chart-line .linha{fill:none;stroke:#1a1a1a;stroke-width:1.4}
      .chart-line .ponto{fill:${AC}}
      .chart-line .eixo{stroke:#cdc6b4}
      .chart-line text{font-family:'Source Sans 3',sans-serif;font-size:8.5px;fill:#6b6656}
      .cotacoes{width:100%;border-collapse:collapse;color:#1a1a1a}
      .cotacoes th{font-size:9.5px;letter-spacing:.08em;text-transform:uppercase;color:#8a8578;text-align:left;font-weight:600;padding-bottom:6px;border-bottom:1px solid #1a1a1a}
      .cotacoes th.num{text-align:right}
      .cotacoes td{padding:7px 0;border-bottom:1px solid #ddd7c8;font-size:12.5px;vertical-align:middle}
      .cotacoes td.nome{font-family:'Newsreader',serif}
      .cotacoes td.num{text-align:right;font-variant-numeric:tabular-nums;font-weight:600}
      .barmini{display:inline-block;height:6px;background:#1a1a1a;vertical-align:middle;margin-right:2px}
      .fvcgrid{display:flex;gap:14px;margin:8px 0 4px}
      .fvccol{flex:1;text-align:center}
      .fvccol .barw{height:64px;display:flex;align-items:flex-end;justify-content:center;border-bottom:1px solid #1a1a1a}
      .fvccol .bar{width:34px;background:#1a1a1a}
      .fvccol.conta .bar{background:${AC}}
      .fvccol .lbl{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:#5a564d;margin-top:6px}
      .fvccol .val{font-family:'Newsreader',serif;font-weight:600;font-size:13px;margin-top:2px;font-variant-numeric:tabular-nums}
      .lista{display:flex;flex-direction:column}
      .li{display:flex;justify-content:space-between;gap:8px;padding:7px 0;border-bottom:1px solid #ddd7c8;font-size:12px}
      .li .d{color:#8a8578;width:34px;flex-shrink:0;font-variant-numeric:tabular-nums}
      .li .n{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      .li .v{font-variant-numeric:tabular-nums;font-weight:600}
      .mais,.toggle{width:100%;min-height:44px;text-align:center;border:1px solid #1a1a1a;background:transparent;color:#1a1a1a;font-family:'Source Sans 3',sans-serif;font-size:12px;margin-top:10px;letter-spacing:.04em}
      .toggle{display:flex;justify-content:space-between;align-items:center;padding:0 12px}
      .toggle svg{width:13px;height:13px;transition:transform .15s}
      .toggle[aria-expanded="true"] svg{transform:rotate(90deg)}
      .subpanel{display:none;padding-top:8px}
      .subpanel.open{display:block}
      .assinrow{display:flex;justify-content:space-between;padding:6px 0;font-size:12px;border-bottom:1px solid #ddd7c8}
      .indice{display:flex;flex-direction:column}
      .indrow{display:flex;align-items:baseline;gap:10px;padding:12px 4px;border-bottom:1px solid #cdc6b4;background:transparent;border-left:none;border-right:none;border-top:none;text-align:left;width:100%;font-family:inherit;min-height:44px;color:inherit}
      .indrow .n{font-family:'Newsreader',serif;font-size:11px;color:${AC};font-weight:700;width:26px;flex-shrink:0}
      .indrow .t{flex:1}
      .indrow .nome{font-family:'Newsreader',serif;font-weight:600;font-size:14.5px}
      .indrow .resumo{font-size:11px;color:#5a564d;margin-top:1px}
      .backbtn{display:flex;align-items:center;gap:6px;min-height:44px;padding:12px 16px 0;color:#1a1a1a;font-size:13px;background:transparent;border:none;font-family:'Source Sans 3',sans-serif}
      .backbtn svg{width:15px;height:15px}
      .exemplo{font-size:10px;color:#8a8578;font-style:italic;margin-top:6px}
      .navbar{position:absolute;left:0;right:0;bottom:0;display:flex;border-top:2px solid #1a1a1a;background:#F7F4EE}
      .navbtn{flex:1;min-height:52px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;background:transparent;border:none;color:#8a8578;font-family:'Source Sans 3',sans-serif}
      .navbtn svg{width:16px;height:16px}
      .navbtn.on{color:${AC}}
      .navbtn span{font-size:9.5px;letter-spacing:.1em;text-transform:uppercase}
      .navbtn+.navbtn{border-left:1px solid #cdc6b4}
    </style>
    <div class="app" id="app"></div>
    `;
    const app = root.getElementById("app");

    function chartBars(dias, refValor, w, h) {
      w = w || 320; h = h || 96;
      const padB = 14, padT = 12;
      const usable = h - padB - padT;
      const vals = dias.map(d => d.acumulado);
      const max = Math.max.apply(null, vals.concat([refValor || 0, 1]));
      const n = dias.length;
      const bw = Math.max(1.6, w / n - 1.4);
      const showRef = refValor && refValor <= max;
      const refY = (h - padB) - (refValor / max) * usable;
      let bars = "";
      for (let i = 0; i < n; i++) {
        const bh = (dias[i].acumulado / max) * usable;
        bars += `<rect class="barra" x="${(i * (w / n)).toFixed(1)}" y="${(h - padB - bh).toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}"/>`;
      }
      return `<svg viewBox="0 0 ${w} ${h}" class="chart-bars" role="img" aria-label="Gasto acumulado do mês em barras">
        ${bars}
        ${showRef ? `<line x1="0" y1="${refY.toFixed(1)}" x2="${w}" y2="${refY.toFixed(1)}" class="ref"/><text x="${w}" y="${Math.max(8, refY - 3).toFixed(1)}" text-anchor="end" class="reflbl">mês anterior ${fmt(refValor)}</text>` : ""}
        <text x="0" y="${h}">dia 1</text>
        <text x="${w}" y="${h}" text-anchor="end">dia ${n}</text>
      </svg>`;
    }

    function chartLine(dias, w, h) {
      w = w || 320; h = h || 78;
      const padB = 14;
      const vals = dias.map(d => d.acumulado);
      const max = Math.max.apply(null, vals.concat([1]));
      const n = dias.length;
      const stepX = n > 1 ? w / (n - 1) : 0;
      const scaleY = v => (h - padB) - (v / max) * (h - padB - 8);
      const pts = dias.map((d, i) => [i * stepX, scaleY(d.acumulado)]);
      const path = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
      const last = pts[n - 1];
      return `<svg viewBox="0 0 ${w} ${h}" class="chart-line" role="img" aria-label="Evolução do gasto no mês, dia a dia">
        <line x1="0" y1="${(h - padB).toFixed(1)}" x2="${w}" y2="${(h - padB).toFixed(1)}" class="eixo"/>
        <path d="${path}" class="linha"/>
        <circle cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="2.6" class="ponto"/>
        <text x="0" y="${h}">dia 1</text>
        <text x="${w}" y="${h}" text-anchor="end">dia ${n} · ${fmt(vals[n - 1])}</text>
      </svg>`;
    }

    function chartMini(seed, w, h) {
      w = w || 130; h = h || 34;
      const r = seedRand("vida-" + seed);
      const n = 7;
      let out = "";
      for (let i = 0; i < n; i++) {
        const v = 0.25 + r() * 0.75;
        const bh = v * (h - 4);
        out += `<rect x="${(i * (w / n)).toFixed(1)}" y="${(h - bh).toFixed(1)}" width="${(w / n - 3).toFixed(1)}" height="${bh.toFixed(1)}" fill="${AC}" opacity="${(0.4 + v * 0.5).toFixed(2)}"/>`;
      }
      return `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Progresso ilustrativo da semana">${out}</svg>`;
    }

    function tabelaCotacoes() {
      const cats = (fin.por_categoria || []).slice().sort((a, b) => b.valor - a.valor).slice(0, 6);
      const total = cats.reduce((s, c) => s + c.valor, 0) || 1;
      const max = Math.max.apply(null, cats.map(c => c.valor).concat([1]));
      return `<table class="cotacoes">
        <thead><tr><th>Categoria</th><th class="num">Peso</th><th class="num">Valor</th></tr></thead>
        <tbody>${cats.map(c => `<tr>
          <td class="nome">${c.categoria}</td>
          <td class="num"><span class="barmini" style="width:${Math.max(2, c.valor / max * 32).toFixed(0)}px"></span>${(c.valor / total * 100).toFixed(0)}%</td>
          <td class="num">${fmt(c.valor)}</td>
        </tr>`).join("")}</tbody>
      </table>`;
    }

    function telaHoje() {
      const clima = D.hoje.clima || {};
      const dt = new Date(D.hoje.data + "T12:00:00");
      const dataFmt = dt.toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "long" });
      app.innerHTML = `
        <div class="masthead">
          <div class="titulo">O Diário</div>
          <div class="sub"><span>${dataFmt} · ${D.hoje.cidade}</span><span class="hh" id="relogio">--:--</span></div>
          <div class="sub" style="margin-top:8px"><span>${ICONS.chuva.replace("<svg", '<svg style="width:12px;height:12px;vertical-align:-2px;margin-right:3px"')}${clima.temp}°C, ${clima.cond}</span><button class="mic" aria-label="Ouvir edição em áudio">${ICONS.mic}</button></div>
        </div>
        <div class="col">
          ${D.aviso_critico ? `<div class="kicker">${ICONS.alerta} Última hora</div><div class="manchete">${D.aviso_critico}</div>` : ""}
          <div class="deck">Gasto do mês soma ${fmt(fin.gasto_mes)}, contra ${fmt(fin.gasto_mes_anterior)} no mês anterior.</div>
          <div class="rule fina"></div>
          <div class="kicker" style="color:#1a1a1a">Caderno de economia</div>
          <div style="margin-top:8px">${chartBars(fin.por_dia_mes || [], fin.gasto_mes_anterior)}</div>
          <div class="rule fina"></div>
          <div class="cols2">
            <div class="miniart"><div class="lbl">Hoje</div><div class="val">${fmt(fin.gasto_hoje)}</div></div>
            <div class="miniart"><div class="lbl">Fatura</div><div class="val">${fmt(fin.fatura_atual)}</div></div>
            <div class="miniart"><div class="lbl">Conta</div><div class="val">${fmt(fin.saldo_conta)}</div></div>
          </div>
          <div class="rule fina"></div>
          <div class="kicker" style="color:#1a1a1a">Em pauta hoje</div>
          <p class="deck" style="margin-top:4px">${(D.tarefas && D.tarefas.em_foco) || "—"}</p>
          <div class="rule"></div>
          <div class="kicker" style="color:#1a1a1a">Nesta edição</div>
          <div class="cols2" style="margin-top:8px">
            <button class="mais" data-t="financas" style="min-height:56px">Finanças</button>
            <button class="mais" data-t="vida" style="min-height:56px">Vida</button>
          </div>
        </div>
      `;
      app.querySelectorAll("[data-t]").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.t)));
      function tick() {
        const el = root.getElementById("relogio");
        if (!el) return;
        el.textContent = new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
      }
      tick();
      if (!ctx.reduzido) timers.push(setInterval(tick, 15000));
    }

    function telaFinancas() {
      const dias = fin.ultimos_15_dias || [];
      const f = fin.fatura_atual || 0, c = fin.saldo_conta || 0;
      const maxfc = Math.max(f, c, 1);
      function li(d) {
        const dd = d.data.slice(8, 10) + "/" + d.data.slice(5, 7);
        return `<div class="li"><span class="d">${dd} ${diaSemana(d.data)}</span><span class="n">${d.descricao}</span><span class="v">${fmt(Math.abs(d.valor))}</span></div>`;
      }
      app.innerHTML = `
        <div class="masthead"><div class="titulo" style="font-size:24px">Caderno de Finanças</div><div class="sub"><span>${fin.mes}</span></div></div>
        <div class="col">
          <div class="manchete" style="font-size:20px">Balanço do mês</div>
          <div class="deck">${fmt(fin.gasto_mes)} gastos até agora${fin.orcamento_mes ? `, de orçamento de ${fmt(fin.orcamento_mes)}` : ""}; ${fmt(fin.gasto_mes_anterior)} no mês anterior.</div>
          <div class="rule fina"></div>
          <div class="kicker" style="color:#1a1a1a">Cotações do mês · por categoria</div>
          <div style="margin-top:8px">${tabelaCotacoes()}</div>
          <div class="rule fina"></div>
          <div class="kicker" style="color:#1a1a1a">Evolução do mês, dia a dia</div>
          <div style="margin-top:8px">${chartLine(fin.por_dia_mes || [])}</div>
          <div class="rule fina"></div>
          <div class="kicker" style="color:#1a1a1a">Fatura × Conta</div>
          <div class="fvcgrid">
            <div class="fvccol"><div class="barw"><div class="bar" style="height:${Math.max(2, f / maxfc * 60).toFixed(0)}px"></div></div><div class="lbl">Fatura</div><div class="val">${fmt(f)}</div></div>
            <div class="fvccol conta"><div class="barw"><div class="bar" style="height:${Math.max(2, c / maxfc * 60).toFixed(0)}px"></div></div><div class="lbl">Conta</div><div class="val">${fmt(c)}</div></div>
          </div>
          <div class="rule"></div>
          <div class="kicker" style="color:#1a1a1a">Últimos 15 dias</div>
          <div class="lista" id="lista15" style="margin-top:6px">${dias.slice(0, 6).map(li).join("")}</div>
          ${dias.length > 6 ? `<button class="mais" id="btnMais">carregar mais (${dias.length - 6})</button>` : ""}
          <button class="toggle" id="btnAssin" aria-expanded="false"><span>Assinaturas (${(fin.assinaturas || []).length})</span>${ICONS.chevron}</button>
          <div class="subpanel" id="painelAssin">${(fin.assinaturas || []).map(a => `<div class="assinrow"><span>${a.nome}</span><span>${fmt(a.valor)}</span></div>`).join("")}</div>
          <button class="toggle" id="btnExtrato" aria-expanded="false"><span>Extrato completo</span>${ICONS.chevron}</button>
          <div class="subpanel" id="painelExtrato">${dias.map(li).join("")}</div>
        </div>
      `;
      const btnMais = root.getElementById("btnMais");
      if (btnMais) btnMais.addEventListener("click", () => { root.getElementById("lista15").innerHTML = dias.map(li).join(""); btnMais.remove(); });
      const wireToggle = (btnId, panelId) => {
        const b = root.getElementById(btnId), p = root.getElementById(panelId);
        b.addEventListener("click", () => { const open = p.classList.toggle("open"); b.setAttribute("aria-expanded", String(open)); });
      };
      wireToggle("btnAssin", "painelAssin");
      wireToggle("btnExtrato", "painelExtrato");
    }

    function telaVida() {
      const secs = D.vida_secoes || [];
      app.innerHTML = `
        <div class="masthead"><div class="titulo" style="font-size:24px">Índice de Cadernos</div><div class="sub"><span>${secs.length} seções</span></div></div>
        <div class="indice" id="indice"></div>
        <div id="artigo"></div>
      `;
      const ind = root.getElementById("indice");
      ind.innerHTML = secs.map((s, i) => `<button class="indrow" data-id="${s.id}">
          <span class="n">${String(i + 1).padStart(2, "0")}</span>
          <span class="t"><span class="nome">${s.nome}</span><div class="resumo">${s.resumo}</div></span>
        </button>`).join("");
      ind.querySelectorAll(".indrow").forEach(el => el.addEventListener("click", () => abrir(el.dataset.id)));

      function abrir(id) {
        const s = secs.find(x => x.id === id);
        if (!s) return;
        ind.style.display = "none";
        const art = root.getElementById("artigo");
        art.innerHTML = `
          <button class="backbtn" id="voltar">${ICONS.voltar}<span>Índice</span></button>
          <div class="col">
            <div class="manchete" style="font-size:21px">${s.nome}</div>
            <div class="deck">${s.resumo}.</div>
            <div class="rule fina"></div>
            <p style="font-size:12.5px;color:#4a473f;line-height:1.5">Esta é a última edição registrada para esta seção. Toque em índice para voltar às demais.</p>
            ${D.viagem && id === "viagens" ? `<p style="font-size:12.5px;color:#4a473f;line-height:1.5">Próxima viagem: <b>${D.viagem.origem} → ${D.viagem.destino}</b> em ${D.viagem.dias_faltando} dias (${D.viagem.data}).</p>` : ""}
            <div class="kicker" style="color:#1a1a1a;margin-top:6px">Progresso da semana</div>
            ${chartMini(id)}
            <div class="exemplo">Dado ilustrativo, não medido</div>
          </div>
        `;
        root.getElementById("voltar").addEventListener("click", () => { art.innerHTML = ""; ind.style.display = ""; });
      }
    }

    function nav() {
      const tabs = [["hoje", ICONS.hoje, "Hoje"], ["financas", ICONS.financas, "Finanças"], ["vida", ICONS.vida, "Vida"]];
      const bar = document.createElement("div");
      bar.className = "navbar";
      bar.innerHTML = tabs.map(([t, ic, lb]) => `<button class="navbtn ${ctx.tela === t ? "on" : ""}" data-t="${t}">${ic}<span>${lb}</span></button>`).join("");
      app.appendChild(bar);
      bar.querySelectorAll("button").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.t)));
      cleanups.push(() => bar.remove());
    }

    if (ctx.tela === "financas") telaFinancas();
    else if (ctx.tela === "vida") telaVida();
    else telaHoje();
    nav();

    return () => {
      timers.forEach(clearInterval);
      cleanups.forEach(fn => fn());
    };
  }
};
