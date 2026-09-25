(window.DIRECOES = window.DIRECOES || {})[13] = {
  nome: "Brutalista",
  ideia: "Branco puro, preto e azul elétrico: tipografia enorme, bordas grossas, zero decoração.",
  acento: "#0000FF",
  fontes: ["Archivo+Black", "Space+Mono:wght@400;700"],
  render(root, D, ctx) {
    const AC = "#0000FF";
    const fmt = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);
    const fmtInt = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(v || 0);
    const fin = D.financas || {};
    const timers = [], cleanups = [];

    const ICONS = {
      mic: '<svg viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="2.2"><rect x="9" y="2" width="6" height="12"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/><path d="M8 21h8"/></svg>',
      seta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
      chuva: '<svg viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="2.2"><path d="M7 15a4 4 0 0 1 .8-7.94A5 5 0 0 1 17.6 9.1 3.5 3.5 0 0 1 17 16H7z"/></svg>',
      alerta: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2"><path d="M12 3l10 18H2L12 3z"/><path d="M12 10v4M12 17h.01"/></svg>',
      enviar: '<svg viewBox="0 0 24 24" fill="#fff" stroke="none"><path d="M4 12l16-8-6 16-3-7-7-1z"/></svg>'
    };

    function chartBarras(w, h, dias, refVal, refLabel) {
      const vals = dias.map(d => d.acumulado);
      const maxV = Math.max(...vals, refVal || 0, 1);
      const n = dias.length, gap = 2, bw = (w - gap * (n - 1)) / n;
      const bars = dias.map((d, i) => {
        const bh = Math.max(1.5, (d.acumulado / maxV) * (h - 16));
        const x = i * (bw + gap), y = h - 16 - bh;
        return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" fill="${i === n - 1 ? AC : '#000'}"/>`;
      }).join("");
      const refY = refVal ? (h - 16 - (refVal / maxV) * (h - 16)) : null;
      return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="none">
        ${bars}
        ${refVal ? `<line x1="0" y1="${refY.toFixed(1)}" x2="${w}" y2="${refY.toFixed(1)}" stroke="${AC}" stroke-width="2"/><text x="${w}" y="${(refY - 5).toFixed(1)}" text-anchor="end" class="chlbl">${refLabel}</text>` : ""}
        <text x="0" y="${h - 16 - 4}" class="chlbl">${fmtInt(maxV)}</text>
        <text x="0" y="${h - 3}" class="chlbl-fr">DIA 1</text>
        <text x="${w}" y="${h - 3}" text-anchor="end" class="chlbl-fr">DIA ${dias[dias.length - 1].dia}</text>
      </svg>`;
    }
    function chartComparativo(fatura, conta) {
      const maxV = Math.max(fatura, conta, 1);
      const wFat = Math.max(3, (fatura / maxV) * 100), wCon = Math.max(3, (conta / maxV) * 100);
      return `
        <div class="comp-r"><div class="comp-t"><span>FATURA</span><b>${fmt(fatura)}</b></div><div class="comp-bg"><div class="comp-fg" style="width:${wFat}%"></div></div></div>
        <div class="comp-r"><div class="comp-t"><span>CONTA</span><b>${fmt(conta)}</b></div><div class="comp-bg"><div class="comp-fg alt" style="width:${wCon}%"></div></div></div>
      `;
    }
    function seqExemplo(id) {
      let h = 0; for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
      const arr = []; for (let i = 0; i < 8; i++) { h = (h * 1103515245 + 12345) >>> 0; arr.push(15 + (h % 85)); }
      return arr;
    }
    function chartSeq(vals) {
      const maxV = Math.max(...vals, 1);
      return `<div class="seq-lbl">SEQUÊNCIA (EXEMPLO)</div><div class="seq-bars">${vals.map(v => `<i style="height:${Math.max(8, (v / maxV) * 100)}%"></i>`).join("")}</div>`;
    }

    root.innerHTML = `
    <style>
      :host, * { box-sizing: border-box; }
      :host { color-scheme: light; }
      button, input { font-family: inherit; color: #000; background: #fff; -webkit-appearance: none; appearance: none; border-radius: 0; }
      input::placeholder { color: #777; opacity: 1; }
      .wrap { font-family: 'Space Mono', monospace; color: #000; background: #fff; padding: 0 0 78px; min-height: 100%; position: relative; color-scheme: light; }
      .big { font-family: 'Archivo Black', sans-serif; font-weight: 400; line-height: .96; letter-spacing: -.01em; }
      .num { font-variant-numeric: tabular-nums; }
      .u { text-decoration: underline; text-underline-offset: 3px; }
      .lbl { font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; }
      .blk { border-bottom: 3px solid #000; padding: 14px 16px; }
      .row2 { display: flex; }
      .row2 > * { flex: 1; }
      .row2 > * + * { border-left: 3px solid #000; }

      .top { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
      .clock { font-size: 32px; }
      .datestr { font-size: 11px; margin-top: 4px; }
      .clima-b { text-align: right; font-size: 11px; }
      .clima-b svg { width: 16px; height: 16px; }
      .mic-b { width: 52px; height: 52px; border: 3px solid #000; display: flex; align-items: center; justify-content: center; margin-top: 6px; background: #fff; flex-shrink: 0; }
      .mic-b svg { width: 22px; height: 22px; }

      .aviso { background: ${AC}; color: #fff; padding: 12px 16px; display: flex; align-items: center; gap: 10px; border-bottom: 3px solid #000; }
      .aviso svg { width: 20px; height: 20px; flex-shrink: 0; }
      .aviso b { font-size: 12.5px; font-weight: 700; }

      .gasto-num { font-size: 42px; margin-top: 4px; }
      .chlbl { font-size: 8px; fill: #000; font-family: 'Space Mono', monospace; font-weight: 700; }
      .chlbl-fr { font-size: 7.5px; fill: #555; font-family: 'Space Mono', monospace; }

      .stat3 .c { padding: 12px 10px; }
      .stat3 .v { font-size: 19px; font-weight: 700; margin-top: 4px; }
      .stat3 .s { font-size: 9px; margin-top: 3px; color: #444; }

      .foco-t { font-size: 15px; font-weight: 700; margin-top: 6px; line-height: 1.3; }

      .link-row { display: flex; justify-content: space-between; align-items: center; padding: 16px; border-bottom: 3px solid #000; font-size: 16px; font-weight: 700; text-transform: uppercase; letter-spacing: .01em; min-height: 44px; background: #fff; width: 100%; text-align: left; color: #000; }
      .link-row svg { width: 18px; height: 18px; flex-shrink: 0; }
      .link-row.blue { background: ${AC}; color: #fff; }
      .link-row.blue svg { color: #fff; }

      .chat-b { display: flex; gap: 0; border: 3px solid #000; margin: 14px 16px 0; }
      .chat-b input { flex: 1; border: none; outline: none; padding: 12px; font-family: 'Space Mono', monospace; font-size: 13px; min-height: 44px; }
      .chat-b input::placeholder { color: #777; }
      .chat-b button { width: 50px; background: ${AC}; border: none; border-left: 3px solid #000; display: flex; align-items: center; justify-content: center; }
      .chat-b button svg { width: 16px; height: 16px; }

      .fin-head { padding: 16px; }
      .fin-head .big { font-size: 26px; }
      .resumo2 .box { padding: 14px 12px; }
      .resumo2 .box .v { font-size: 20px; font-weight: 700; }
      .resumo2 .box .s { font-size: 9.5px; margin-top: 4px; color: #444; }

      .cat-total { display: flex; justify-content: space-between; align-items: center; background: #000; color: #fff; padding: 12px 16px; }
      .cat-total .v { font-family: 'Archivo Black', sans-serif; font-size: 20px; }
      .cat-list { padding: 14px 16px; }
      .cat-row { margin-bottom: 14px; }
      .cat-row:last-child { margin-bottom: 0; }
      .cat-top { display: flex; justify-content: space-between; font-size: 12px; font-weight: 700; text-transform: uppercase; margin-bottom: 5px; }
      .cat-bar-bg { height: 22px; background: #eee; border: 2px solid #000; }
      .cat-bar { height: 100%; background: #000; }
      .cat-row:nth-child(even) .cat-bar { background: ${AC}; }

      .comp-r + .comp-r { margin-top: 12px; }
      .comp-t { display: flex; justify-content: space-between; font-size: 11px; font-weight: 700; margin-bottom: 5px; }
      .comp-t span { letter-spacing: .05em; }
      .comp-bg { height: 20px; background: #eee; border: 2px solid #000; }
      .comp-fg { height: 100%; background: #000; }
      .comp-fg.alt { background: ${AC}; }

      .li { display: flex; justify-content: space-between; align-items: center; padding: 11px 16px; border-bottom: 2px solid #000; gap: 8px; }
      .li .d { font-size: 10px; font-weight: 700; width: 34px; flex-shrink: 0; }
      .li .n { flex: 1; font-size: 12px; font-weight: 700; text-transform: uppercase; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .li .v { font-size: 13px; font-weight: 700; }

      .toggle-b { display: flex; justify-content: space-between; align-items: center; width: 100%; padding: 15px 16px; border: none; border-bottom: 3px solid #000; background: #fff; font-size: 13px; font-weight: 700; text-transform: uppercase; min-height: 44px; }
      .toggle-b svg { width: 14px; height: 14px; transition: transform .15s; }
      .toggle-b.open svg { transform: rotate(90deg); }
      .sub { display: none; }
      .sub.open { display: block; }
      .sub-row { display: flex; justify-content: space-between; padding: 10px 16px; border-bottom: 2px solid #ccc; font-size: 12px; }

      .proj-row { display: flex; justify-content: space-between; align-items: center; width: 100%; padding: 16px; border: none; border-bottom: 3px solid #000; background: #fff; text-align: left; min-height: 44px; }
      .proj-row .nm { font-size: 17px; font-weight: 700; text-transform: uppercase; }
      .proj-row svg { width: 16px; height: 16px; transition: transform .15s; flex-shrink: 0; }
      .proj-row.open svg { transform: rotate(90deg); }
      .proj-detail { display: none; padding: 4px 16px 18px; border-bottom: 3px solid #000; }
      .proj-detail.open { display: block; }
      .proj-detail p { font-size: 12.5px; line-height: 1.6; margin: 0 0 10px; }
      .proj-detail b { color: ${AC}; }
      .seq-lbl { font-size: 9.5px; font-weight: 700; letter-spacing: .05em; margin-bottom: 6px; }
      .seq-bars { display: flex; gap: 3px; align-items: flex-end; height: 32px; }
      .seq-bars i { flex: 1; background: ${AC}; display: block; }

      .navbar { display: flex; position: absolute; left: 0; right: 0; bottom: 0; border-top: 3px solid #000; }
      .navbtn { flex: 1; min-height: 56px; border: none; background: #fff; color: #000; font-family: 'Space Mono', monospace; font-size: 11.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; }
      .navbtn + .navbtn { border-left: 3px solid #000; }
      .navbtn.on { background: ${AC}; color: #fff; }
    </style>
    <div class="wrap" id="wrap"></div>
    `;
    const wrap = root.getElementById("wrap");

    function telaHoje() {
      const clima = D.hoje.clima || {};
      const dias = fin.por_dia_mes || [];
      wrap.innerHTML = `
        <div class="blk top">
          <div><div class="lbl">Hoje</div><div class="clock big num">${new Date().toLocaleTimeString("pt-BR",{hour:"2-digit",minute:"2-digit"})}</div><div class="datestr">${D.hoje.data} · ${D.hoje.cidade}</div></div>
          <div style="text-align:right">
            <div class="clima-b">${ICONS.chuva}<div>${clima.temp}°C</div><div>${clima.chuva_prob}% CHUVA</div></div>
            <button class="mic-b" id="mic">${ICONS.mic}</button>
          </div>
        </div>
        ${D.aviso_critico ? `<div class="aviso">${ICONS.alerta}<b>${D.aviso_critico.toUpperCase()}</b></div>` : ""}
        <div class="blk">
          <div class="lbl u">Gasto do mês</div>
          <div class="gasto-num big num">${fmt(fin.gasto_mes)}</div>
          <div style="margin-top:12px">${chartBarras(328, 78, dias, fin.gasto_mes_anterior, "ANTERIOR " + fmtInt(fin.gasto_mes_anterior))}</div>
        </div>
        <div class="row2 stat3 blk" style="padding:0">
          <div class="c"><div class="lbl">Hoje</div><div class="v num">${fmt(fin.gasto_hoje)}</div></div>
          <div class="c"><div class="lbl">Fatura</div><div class="v num">${fmt(fin.fatura_atual)}</div><div class="s">VENCE ${(fin.fatura_vencimento||"").slice(8,10)}/${(fin.fatura_vencimento||"").slice(5,7)}</div></div>
          <div class="c"><div class="lbl">Conta</div><div class="v num">${fmt(fin.saldo_conta)}</div></div>
        </div>
        <div class="blk">
          <div class="lbl u">Em foco agora</div>
          <div class="foco-t">${(D.tarefas && D.tarefas.em_foco) || "—"}</div>
        </div>
        <button class="link-row blue" data-t="financas"><span>Finanças</span>${ICONS.seta}</button>
        <button class="link-row" data-t="vida"><span>Vida</span>${ICONS.seta}</button>
        <button class="link-row" data-t="vida"><span>Tarefas</span>${ICONS.seta}</button>
        <button class="link-row" data-t="vida"><span>Aviação</span>${ICONS.seta}</button>
        <div class="chat-b"><input placeholder="ESCREVER…"/><button>${ICONS.enviar}</button></div>
      `;
      wrap.querySelectorAll("[data-t]").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.t)));
    }

    function telaFinancas() {
      const cats = (fin.por_categoria || []).slice().sort((a, b) => b.valor - a.valor);
      const totalCat = cats.reduce((s, c) => s + c.valor, 0) || 1;
      const maxV = Math.max(...cats.map(c => c.valor), 1);
      const delta = fin.gasto_mes_anterior ? ((fin.gasto_mes - fin.gasto_mes_anterior) / fin.gasto_mes_anterior) * 100 : 0;
      const dias15 = fin.ultimos_15_dias || [];
      function li(d) {
        const dd = d.data.slice(8, 10) + "/" + d.data.slice(5, 7);
        return `<div class="li"><span class="d num">${dd}</span><span class="n">${d.descricao}</span><span class="v num">${fmt(Math.abs(d.valor))}</span></div>`;
      }
      wrap.innerHTML = `
        <div class="fin-head blk"><div class="big">FINANÇAS</div><div style="font-size:11px;margin-top:4px">${fin.mes}</div></div>
        <div class="row2 resumo2 blk" style="padding:0">
          <div class="box"><div class="v num">${fmt(fin.gasto_mes)}</div><div class="s">GASTO ESTE MÊS</div></div>
          <div class="box"><div class="v num">${fmt(fin.gasto_mes_anterior)}</div><div class="s">ANTERIOR · ${delta>0?"+":""}${delta.toFixed(0)}%</div></div>
        </div>
        <div class="cat-total"><span class="lbl" style="color:#fff">Por categoria</span><span class="v num">${fmt(totalCat)}</span></div>
        <div class="cat-list blk">
          ${cats.map(c => `
            <div class="cat-row">
              <div class="cat-top"><span>${c.categoria}</span><span class="num">${fmt(c.valor)}</span></div>
              <div class="cat-bar-bg"><div class="cat-bar" style="width:${(c.valor / maxV) * 100}%"></div></div>
            </div>`).join("")}
        </div>
        <div class="blk">
          <div class="lbl u">Evolução do mês</div>
          <div style="margin-top:12px">${chartBarras(328, 76, fin.por_dia_mes || [], fin.gasto_mes_anterior, "ANTERIOR " + fmtInt(fin.gasto_mes_anterior))}</div>
        </div>
        <div class="blk">
          <div class="lbl u" style="margin-bottom:10px">Fatura × Conta</div>
          ${chartComparativo(fin.fatura_atual || 0, fin.saldo_conta || 0)}
        </div>
        <div class="blk" style="padding-bottom:0">
          <div class="lbl u" style="padding:2px 0 0">Últimos 15 dias</div>
        </div>
        <div id="listaDias">${dias15.slice(0, 6).map(li).join("")}</div>
        ${dias15.length > 6 ? `<button class="link-row" id="btnMais"><span>CARREGAR MAIS (${dias15.length - 6})</span>${ICONS.seta}</button>` : ""}
        <button class="toggle-b" id="btnAssin"><span>ASSINATURAS (${(fin.assinaturas||[]).length})</span>${ICONS.seta}</button>
        <div class="sub" id="assinList">${(fin.assinaturas||[]).map(a => `<div class="sub-row"><span>${a.nome.toUpperCase()}</span><span class="num">${fmt(a.valor)}</span></div>`).join("")}</div>
        <button class="toggle-b" id="btnExtrato"><span>EXTRATO COMPLETO (${dias15.length})</span>${ICONS.seta}</button>
        <div class="sub" id="extratoList">${dias15.map(li).join("")}</div>
      `;
      const btnMais = root.getElementById("btnMais");
      if (btnMais) btnMais.addEventListener("click", () => { root.getElementById("listaDias").innerHTML = dias15.map(li).join(""); btnMais.remove(); });
      root.getElementById("btnAssin").addEventListener("click", function () { this.classList.toggle("open"); root.getElementById("assinList").classList.toggle("open"); });
      root.getElementById("btnExtrato").addEventListener("click", function () { this.classList.toggle("open"); root.getElementById("extratoList").classList.toggle("open"); });
    }

    function telaVida() {
      const secs = D.vida_secoes || [];
      wrap.innerHTML = `
        <div class="fin-head blk"><div class="big">VIDA</div><div style="font-size:11px;margin-top:4px">${secs.length} SEÇÕES</div></div>
        <div id="projList">
          ${secs.map(s => `
            <button class="proj-row" data-id="${s.id}"><span class="nm">${s.nome}</span>${ICONS.seta}</button>
            <div class="proj-detail" id="det-${s.id}">
              <p>${s.resumo}. Sem itens pendentes visíveis agora.
              ${(s.id === "viagens" && D.viagem) ? `<br><b>${D.viagem.origem} → ${D.viagem.destino}</b> em ${D.viagem.dias_faltando} DIAS (${D.viagem.data})` : ""}</p>
              ${chartSeq(seqExemplo(s.id))}
            </div>`).join("")}
        </div>
      `;
      root.querySelectorAll(".proj-row").forEach(el => el.addEventListener("click", () => {
        const open = el.classList.toggle("open");
        root.getElementById("det-" + el.dataset.id).classList.toggle("open", open);
      }));
    }

    function nav() {
      const tabs = [["hoje", "Hoje"], ["financas", "Finanças"], ["vida", "Vida"]];
      const bar = document.createElement("div");
      bar.className = "navbar";
      bar.innerHTML = tabs.map(([t, lb]) => `<button class="navbtn ${ctx.tela === t ? "on" : ""}" data-t="${t}">${lb}</button>`).join("");
      wrap.appendChild(bar);
      bar.querySelectorAll("button").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.t)));
    }

    if (ctx.tela === "hoje") telaHoje();
    else if (ctx.tela === "financas") telaFinancas();
    else telaVida();
    nav();

    return () => { timers.forEach(clearInterval); cleanups.forEach(fn => fn()); };
  }
};
