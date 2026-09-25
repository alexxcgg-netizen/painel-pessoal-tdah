(window.DIRECOES = window.DIRECOES || {})[6] = {
  nome: "Orbital",
  ideia: "Sistema de órbitas: cada valor é uma órbita com um ponto percorrendo-a; centro mostra a hora.",
  acento: "#A78BFA",
  fontes: ["Space+Grotesk:wght@400;500;600", "JetBrains+Mono:wght@400;500"],
  render(root, D, ctx) {
    const AC = "#A78BFA";
    const fmt = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
    const fin = D.financas || {};
    const timers = [];
    const cleanups = [];

    const ICONS = {
      mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/><path d="M8 21h8"/></svg>',
      financas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="9"/><path d="M12 7v10M9 9.5c0-1.4 1.3-2 3-2s3 .8 3 2-1.3 1.8-3 2-3 .8-3 2 1.3 2 3 2 3-.6 3-2"/></svg>',
      vida: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="3"/><ellipse cx="12" cy="12" rx="9" ry="4"/><ellipse cx="12" cy="12" rx="9" ry="4" transform="rotate(60 12 12)"/></svg>',
      tarefas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 6h16M4 12h16M4 18h10"/><circle cx="20" cy="18" r="2"/></svg>',
      aviacao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2v20M4 9l16 4M6 20l6-3 6 3"/></svg>',
      chuva: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M7 15a4 4 0 0 1 .8-7.94A5 5 0 0 1 17.6 9.1 3.5 3.5 0 0 1 17 16H7z"/><path d="M8 19l-1 2M12 19l-1 2M16 19l-1 2"/></svg>',
      alerta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 3l10 18H2L12 3z"/><path d="M12 10v4M12 17h.01"/></svg>',
      seta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 6l6 6-6 6"/></svg>',
      enviar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 12l16-8-6 16-3-7-7-1z"/></svg>',
      fechar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M6 6l12 12M18 6L6 18"/></svg>'
    };

    root.innerHTML = `
    <style>
      :host, * { box-sizing: border-box; }
      .wrap { font-family: 'Space Grotesk', sans-serif; color: #d8d8d8; padding: 14px 14px 90px; min-height: 100%; position: relative; }
      .mono { font-family: 'JetBrains Mono', monospace; }
      .tab-title { font-size: 11px; letter-spacing: .28em; text-transform: uppercase; color: ${AC}; opacity: .85; margin: 0 0 10px 2px; }
      .aviso { display: flex; gap: 8px; align-items: center; border: 1px solid #3a2444; background: #12081a; color: #d3a0e0; font-size: 11.5px; padding: 8px 10px; border-radius: 4px; margin-bottom: 14px; }
      .aviso svg { width: 15px; height: 15px; flex-shrink: 0; color: #e08080; }
      .row { display: flex; align-items: center; gap: 10px; }
      .topbar { justify-content: space-between; margin-bottom: 6px; }
      .mic { width: 46px; height: 46px; border-radius: 50%; border: 1px solid #2a2a2a; background: #060608; color: ${AC}; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
      .mic svg { width: 20px; height: 20px; }
      .clima { text-align: right; font-size: 12px; color: #a8a8a8; }
      .clima svg { width: 16px; height: 16px; vertical-align: -3px; margin-right: 4px; color: ${AC}; }

      .orb-wrap { position: relative; width: 320px; height: 320px; margin: 4px auto 4px; }
      .orb-wrap svg { width: 100%; height: 100%; overflow: visible; }
      .orb-track { fill: none; stroke: #1c1c22; stroke-width: 1; stroke-dasharray: 2 4; }
      .orb-center { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
      .orb-center .hh { font-family: 'JetBrains Mono', monospace; font-size: 26px; color: #f0f0f0; font-variant-numeric: tabular-nums; }
      .orb-center .dd { font-size: 10px; color: #8a8a8a; letter-spacing: .12em; text-transform: uppercase; margin-top: 4px; }
      .orb-pt { filter: none; }
      .orb-label { font-size: 8.5px; fill: #7a7a86; font-family: 'JetBrains Mono', monospace; letter-spacing: .04em; }

      .leg-orbits { display: flex; flex-direction: column; gap: 10px; margin: 10px 0 18px; }
      .leg-o { display: flex; align-items: center; gap: 10px; font-size: 12px; border: 1px solid #1c1c22; border-radius: 6px; padding: 9px 11px; }
      .leg-o .dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
      .leg-o .nome { flex: 1; color: #b8b8c0; font-size: 10.5px; letter-spacing: .06em; text-transform: uppercase; }
      .leg-o .val { font-family: 'JetBrains Mono', monospace; color: #eee; font-variant-numeric: tabular-nums; font-size: 13px; }

      .foco { border: 1px solid #232330; border-radius: 4px; padding: 10px 12px; margin-bottom: 16px; background: linear-gradient(180deg, rgba(167,139,250,.05), transparent); }
      .foco .l1 { font-size: 10px; color: #7a7a86; letter-spacing: .1em; text-transform: uppercase; }
      .foco .l2 { margin-top: 4px; font-size: 14px; color: #f0f0f0; }

      .atalhos { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 18px; }
      .atalho { border: 1px solid #232330; border-radius: 6px; padding: 10px 4px; display: flex; flex-direction: column; align-items: center; gap: 6px; background: #050507; min-height: 44px; }
      .atalho svg { width: 18px; height: 18px; color: ${AC}; }
      .atalho span { font-size: 9.5px; color: #9a9aa4; letter-spacing: .04em; }

      .chatbar { position: absolute; left: 14px; right: 14px; bottom: 14px; display: flex; align-items: center; gap: 8px; border: 1px solid #262630; border-radius: 22px; padding: 5px 6px 5px 14px; background: #070709; }
      .chatbar input { flex: 1; background: transparent; border: none; outline: none; color: #ddd; font-family: 'Space Grotesk', sans-serif; font-size: 13px; }
      .chatbar input::placeholder { color: #555; }
      .chatbar button { width: 34px; height: 34px; border-radius: 50%; border: 1px solid #2a2a33; background: #0c0c10; color: ${AC}; display: flex; align-items: center; justify-content: center; }
      .chatbar button svg { width: 15px; height: 15px; }

      /* finanças: planetas */
      .planet-wrap { position: relative; width: 100%; height: 300px; margin: 4px auto 14px; }
      .planet-wrap svg { width: 100%; height: 100%; overflow: visible; }
      .planet-lbl { font-size: 8px; fill: #9a9aa6; font-family: 'JetBrains Mono', monospace; text-anchor: middle; }
      .planet-val { font-size: 9px; fill: #eee; font-family: 'JetBrains Mono', monospace; text-anchor: middle; font-weight: 600; }

      .card { border: 1px solid #1c1c22; border-radius: 6px; padding: 12px; margin-bottom: 12px; }
      .card .t1 { font-size: 10px; color: #7a7a86; letter-spacing: .12em; text-transform: uppercase; margin-bottom: 8px; }
      .fvsc { display: flex; gap: 12px; }
      .fvsc .item { flex: 1; text-align: center; padding: 10px 6px; border: 1px solid #1a1a20; border-radius: 5px; }
      .fvsc .n { font-family: 'JetBrains Mono', monospace; font-size: 15px; color: #eee; font-variant-numeric: tabular-nums; }
      .fvsc .s { font-size: 9.5px; color: #7a7a86; margin-top: 4px; }

      .lista { display: flex; flex-direction: column; }
      .li { display: flex; justify-content: space-between; align-items: center; padding: 9px 2px; border-bottom: 1px solid #17171c; font-size: 12.5px; }
      .li .d { color: #7a7a86; font-family: 'JetBrains Mono', monospace; font-size: 10.5px; width: 44px; flex-shrink: 0; }
      .li .n { flex: 1; color: #ccc; padding: 0 6px; }
      .li .v { font-family: 'JetBrains Mono', monospace; font-variant-numeric: tabular-nums; color: #e8e8e8; }
      .mais { width: 100%; text-align: center; padding: 10px; margin-top: 8px; border: 1px dashed #2a2a33; border-radius: 5px; color: #8a8a94; font-size: 11.5px; background: transparent; min-height: 44px; }

      .assin-toggle, .extrato-toggle { width: 100%; display: flex; justify-content: space-between; align-items: center; padding: 12px; border: 1px solid #1c1c22; border-radius: 6px; background: #050507; color: #ccc; font-size: 12.5px; margin-bottom: 10px; min-height: 44px; }
      .assin-toggle svg, .extrato-toggle svg { width: 14px; height: 14px; color: ${AC}; }
      .assin-list, .extrato-list { display: none; }
      .assin-list.open, .extrato-list.open { display: block; }
      .assin-row { display: flex; justify-content: space-between; padding: 8px 2px; font-size: 12px; border-bottom: 1px solid #15151a; color: #bbb; }

      /* vida: satélites em órbita horizontal */
      .sat-track { position: relative; height: 108px; margin-bottom: 14px; }
      .sat-line { position: absolute; left: 0; right: 0; top: 50%; height: 1px; background: repeating-linear-gradient(90deg, #262630 0 6px, transparent 6px 12px); }
      .sat-scroll { display: flex; gap: 18px; overflow-x: auto; padding: 20px 4px; scrollbar-width: none; position: relative; }
      .sat-scroll::-webkit-scrollbar { display: none; }
      .sat { flex-shrink: 0; width: 58px; display: flex; flex-direction: column; align-items: center; gap: 7px; }
      .sat .ico { width: 40px; height: 40px; border-radius: 50%; border: 1px solid #262630; display: flex; align-items: center; justify-content: center; background: #07070a; }
      .sat .ico svg { width: 16px; height: 16px; color: ${AC}; }
      .sat.on .ico { border-color: ${AC}; background: rgba(167,139,250,.08); }
      .sat span { font-size: 9px; color: #9a9aa4; text-align: center; line-height: 1.1; }

      .modal-bg { position: fixed; inset: 0; background: rgba(0,0,0,.7); display: none; align-items: flex-end; z-index: 5; }
      .modal-bg.open { display: flex; }
      .modal { width: 100%; background: #08080b; border-top: 1px solid #2a2a33; border-radius: 14px 14px 0 0; padding: 18px; position: relative; }
      .modal h3 { margin: 0 0 8px; font-size: 15px; color: #f0f0f0; font-weight: 500; }
      .modal p { margin: 4px 0; font-size: 12px; color: #999; line-height: 1.5; }
      .modal .x { position: absolute; top: 14px; right: 14px; width: 30px; height: 30px; border-radius: 50%; border: 1px solid #2a2a33; display: flex; align-items: center; justify-content: center; color: #999; }
      .modal .x svg { width: 14px; height: 14px; }
      .viagem-box { margin-top: 10px; border-top: 1px solid #1c1c22; padding-top: 10px; font-size: 11.5px; color: #9a9aa4; }
      .viagem-box b { color: ${AC}; }

      .navbar { position: absolute; left: 0; right: 0; bottom: 0; display: flex; border-top: 1px solid #1c1c22; background: #020204; }
      .navbtn { flex: 1; min-height: 54px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; background: transparent; border: none; color: #63636e; }
      .navbtn svg { width: 17px; height: 17px; }
      .navbtn.on { color: ${AC}; }
      .navbtn span { font-size: 9px; letter-spacing: .05em; text-transform: uppercase; }
    </style>
    <div class="wrap" id="wrap"></div>
    `;

    const wrap = root.getElementById("wrap");

    function telaHoje() {
      const clima = D.hoje.clima || {};
      const orbitDefs = [
        { key: "gasto", label: "Gasto do mês", val: fin.gasto_mes || 0, r: 145, speed: 0.09, color: AC },
        { key: "fatura", label: "Fatura", val: fin.fatura_atual || 0, r: 118, speed: -0.14, color: "#8a7ae0" },
        { key: "conta", label: "Saldo conta", val: fin.saldo_conta || 0, r: 92, speed: 0.2, color: "#c9a8f5" },
        { key: "foco", label: "Foco", val: null, r: 66, speed: -0.28, color: "#ffffff" }
      ];
      const cx = 160, cy = 160;
      const orbitsSvg = orbitDefs.map(o => `<circle class="orb-track" cx="${cx}" cy="${cy}" r="${o.r}"/>`).join("");
      const ptsSvg = orbitDefs.map(o => `<circle class="orb-pt" id="pt-${o.key}" r="${o.key === "foco" ? 5 : 4}" fill="${o.color}"/>`).join("");

      wrap.innerHTML = `
        ${D.aviso_critico ? `<div class="aviso">${ICONS.alerta}<span>${D.aviso_critico}</span></div>` : ""}
        <div class="row topbar">
          <button class="mic" id="mic">${ICONS.mic}</button>
          <div class="clima">${ICONS.chuva}${clima.temp}°C<br><span style="font-size:10px">${clima.cond}, ${clima.chuva_prob}%</span></div>
        </div>
        <div class="orb-wrap">
          <svg viewBox="0 0 320 320">
            ${orbitsSvg}
            ${ptsSvg}
          </svg>
          <div class="orb-center">
            <div class="hh mono" id="relogio">--:--</div>
            <div class="dd">${D.hoje.data}</div>
          </div>
        </div>
        <div class="leg-orbits">
          ${orbitDefs.map(o => `
            <div class="leg-o"><span class="dot" style="background:${o.color}"></span>
              <span class="nome">${o.label}</span>
              <span class="val mono">${o.key === "foco" ? "" : fmt(o.val)}</span></div>
          `).join("")}
        </div>
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
        el.textContent = new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
      }
      tick();
      if (!ctx.reduzido) timers.push(setInterval(tick, 1000 * 15));

      const angles = {};
      orbitDefs.forEach(o => angles[o.key] = Math.random() * 360);
      function place() {
        orbitDefs.forEach(o => {
          const a = angles[o.key] * Math.PI / 180;
          const x = cx + o.r * Math.cos(a);
          const y = cy + o.r * Math.sin(a);
          const el = root.getElementById("pt-" + o.key);
          if (el) { el.setAttribute("cx", x); el.setAttribute("cy", y); }
        });
      }
      place();
      if (!ctx.reduzido) {
        let raf;
        function anim() {
          orbitDefs.forEach(o => angles[o.key] = (angles[o.key] + o.speed) % 360);
          place();
          raf = requestAnimationFrame(anim);
        }
        raf = requestAnimationFrame(anim);
        cleanups.push(() => cancelAnimationFrame(raf));
      }
    }

    function telaFinancas() {
      const cats = (fin.por_categoria || []).slice().sort((a, b) => b.valor - a.valor);
      const maxV = Math.max(...cats.map(c => c.valor), 1);
      const cx = 160, cy = 150;
      const maxR = 130, minR = 34;
      const colors = cats.map((_, i) => {
        const t = i / Math.max(1, cats.length - 1);
        return `hsl(${262 - t * 40}, ${75 - t * 15}%, ${72 - t * 22}%)`;
      });
      const planets = cats.map((c, i) => {
        const r = minR + (c.valor / maxV) * (maxR - minR);
        const ang = (i / cats.length) * 2 * Math.PI - Math.PI / 2;
        const x = cx + r * Math.cos(ang);
        const y = cy + r * 0.62 * Math.sin(ang);
        const size = 5 + (c.valor / maxV) * 11;
        return { c, r, x, y, size, color: colors[i] };
      });
      const tracksSvg = [...new Set(planets.map(p => Math.round(p.r)))].map(r =>
        `<ellipse class="orb-track" cx="${cx}" cy="${cy}" rx="${r}" ry="${r * 0.62}"/>`).join("");
      const planetsSvg = planets.map((p, i) => `
        <circle cx="${p.x}" cy="${p.y}" r="${p.size}" fill="${p.color}"/>
        ${i < 4 ? `<text class="planet-lbl" x="${p.x}" y="${p.y - p.size - 6}">${p.c.categoria.length > 12 ? p.c.categoria.slice(0, 11) + "…" : p.c.categoria}</text>` : ""}
      `).join("");

      const dias = fin.ultimos_15_dias || [];
      const idShow = "listaDias";

      wrap.innerHTML = `
        <div class="tab-title">Finanças</div>
        <div class="planet-wrap">
          <svg viewBox="0 0 320 300">
            <circle cx="${cx}" cy="${cy}" r="8" fill="${AC}"/>
            ${tracksSvg}
            ${planetsSvg}
          </svg>
        </div>
        <div class="card">
          <div class="t1">Mês atual</div>
          <div class="fvsc">
            <div class="item"><div class="n mono">${fmt(fin.gasto_mes || 0)}</div><div class="s">gasto total</div></div>
            <div class="item"><div class="n mono">${fmt(fin.gasto_mes_anterior || 0)}</div><div class="s">mês anterior</div></div>
          </div>
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
          <div class="lista" id="${idShow}">${dias.slice(0, 6).map(li).join("")}</div>
          ${dias.length > 6 ? `<button class="mais" id="btnMais">carregar mais (${dias.length - 6})</button>` : ""}
        </div>
        <button class="assin-toggle" id="btnAssin"><span>Assinaturas (${(fin.assinaturas || []).length})</span>${ICONS.seta}</button>
        <div class="assin-list" id="assinList">
          ${(fin.assinaturas || []).map(a => `<div class="assin-row"><span>${a.nome}</span><span class="mono">${fmt(a.valor)}</span></div>`).join("")}
        </div>
        <button class="extrato-toggle" id="btnExtrato"><span>Extrato completo</span>${ICONS.seta}</button>
        <div class="extrato-list" id="extratoList">${dias.map(li).join("")}</div>
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
      const ICOSET = [ICONS.vida, ICONS.tarefas, ICONS.financas, ICONS.aviacao, ICONS.alerta, ICONS.chuva];
      wrap.innerHTML = `
        <div class="tab-title">Vida</div>
        <div class="sat-track">
          <div class="sat-line"></div>
          <div class="sat-scroll" id="satScroll">
            ${secs.map((s, i) => `
              <div class="sat" data-id="${s.id}">
                <div class="ico">${ICOSET[i % ICOSET.length]}</div>
                <span>${s.nome}</span>
              </div>`).join("")}
          </div>
        </div>
        <div class="modal-bg" id="modalBg">
          <div class="modal">
            <button class="x" id="modalClose">${ICONS.fechar}</button>
            <h3 id="modalTitulo"></h3>
            <p id="modalResumo"></p>
            <p>Última atualização registrada nesta seção.</p>
            <div id="modalViagem"></div>
          </div>
        </div>
      `;
      const bg = root.getElementById("modalBg");
      function abrir(id) {
        const s = secs.find(x => x.id === id);
        if (!s) return;
        root.getElementById("modalTitulo").textContent = s.nome;
        root.getElementById("modalResumo").textContent = s.resumo;
        root.getElementById("modalViagem").innerHTML = D.viagem
          ? `<div class="viagem-box">Próxima viagem: <b>${D.viagem.origem} → ${D.viagem.destino}</b> em ${D.viagem.dias_faltando} dias (${D.viagem.data})</div>` : "";
        bg.classList.add("open");
      }
      root.querySelectorAll(".sat").forEach(el => el.addEventListener("click", () => abrir(el.dataset.id)));
      root.getElementById("modalClose").addEventListener("click", () => bg.classList.remove("open"));
      bg.addEventListener("click", e => { if (e.target === bg) bg.classList.remove("open"); });
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
