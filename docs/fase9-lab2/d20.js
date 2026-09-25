(window.DIRECOES = window.DIRECOES || {})[20] = {
  nome: "Carro",
  ideia: "Painel de carro: barra lateral fixa, cartões enormes em 2 colunas, alvos de toque gigantes.",
  acento: "#A3E635",
  fontes: ["Sora:wght@500;600;700;800"],
  render(root, D, ctx) {
    const AC = "#A3E635";
    const fmt = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);
    const fmtInt = v => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(v || 0);
    const fin = D.financas || {};
    const timers = [], cleanups = [];

    const ICONS = {
      mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/><path d="M8 21h8"/></svg>',
      hoje: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
      financas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 19V10M10 19V5M16 19v-7M22 19H2"/></svg>',
      vida: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>',
      chuva: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M7 15a4 4 0 0 1 .8-7.94A5 5 0 0 1 17.6 9.1 3.5 3.5 0 0 1 17 16H7z"/><path d="M8 19l-1 2M12 19l-1 2M16 19l-1 2"/></svg>',
      alerta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 3l10 18H2L12 3z"/><path d="M12 10v4M12 17h.01"/></svg>',
      seta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M9 6l6 6-6 6"/></svg>',
      fechar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M6 6l12 12M18 6L6 18"/></svg>',
      enviar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 12l16-8-6 16-3-7-7-1z"/></svg>',
      tarefas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 6h16M4 12h16M4 18h10"/></svg>',
      aviacao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 2v20M4 9l16 4M6 20l6-3 6 3"/></svg>',
      tag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M20 12l-8 8-9-9V3h8z"/><circle cx="7.5" cy="7.5" r="1.3" fill="currentColor" stroke="none"/></svg>',
      pasta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 6h6l2 2h10v11H3z"/></svg>',
      calend: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="5" width="18" height="16" rx="1.5"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>',
      pessoa: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="8" r="3.4"/><path d="M5 20c1.2-3.8 4-5.6 7-5.6s5.8 1.8 7 5.6"/></svg>',
      mala: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="8" width="18" height="12" rx="1.5"/><path d="M9 8V5.5A1.5 1.5 0 0 1 10.5 4h3A1.5 1.5 0 0 1 15 5.5V8"/></svg>',
      estrela: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 3l2.6 5.9 6.4.6-4.8 4.3 1.4 6.3L12 16.9l-5.6 3.2 1.4-6.3-4.8-4.3 6.4-.6z"/></svg>'
    };
    const iconCiclo = [ICONS.tag, ICONS.pasta, ICONS.calend, ICONS.pessoa, ICONS.mala, ICONS.estrela];

    function chartArea(w, h, dias, refVal, refLabel) {
      const vals = dias.map(d => d.acumulado);
      const maxV = Math.max(...vals, refVal || 0, 1);
      const padT = 20, padB = 18, baseline = h - padB, innerH = h - padT - padB, n = dias.length;
      const X = i => n <= 1 ? 0 : (i / (n - 1)) * w;
      const Y = v => padT + innerH - (v / maxV) * innerH;
      const pts = dias.map((d, i) => `${X(i).toFixed(1)},${Y(d.acumulado).toFixed(1)}`);
      const path = "M" + pts.join(" L");
      const area = `M0,${baseline} L${pts.join(" L")} L${w},${baseline} Z`;
      const last = dias[dias.length - 1];
      const refY = refVal ? Y(refVal).toFixed(1) : null;
      return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="none">
        <path d="${area}" fill="${AC}" opacity=".16"/>
        ${refVal ? `<line x1="0" y1="${refY}" x2="${w}" y2="${refY}" stroke="#666" stroke-width="1.5" stroke-dasharray="4 4"/><text x="${w}" y="${Number(refY) - 6}" text-anchor="end" class="chlbl-fr">${refLabel}</text>` : ""}
        <path d="${path}" fill="none" stroke="${AC}" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>
        <circle cx="${X(dias.length - 1)}" cy="${Y(last.acumulado)}" r="5" fill="${AC}"/>
        <text x="0" y="${padT - 6}" class="chlbl">${fmtInt(maxV)}</text>
        <text x="0" y="${h - 3}" class="chlbl-fr">DIA 1</text>
        <text x="${w}" y="${h - 3}" text-anchor="end" class="chlbl-fr">DIA ${last.dia}</text>
      </svg>`;
    }
    function chartTop5(cats) {
      const top5 = cats.slice().sort((a, b) => b.valor - a.valor).slice(0, 5);
      const maxV = Math.max(...top5.map(c => c.valor), 1);
      return top5.map(c => `
        <div class="bar-row">
          <div class="bar-top"><span class="bar-nm">${c.categoria}</span><span class="bar-v num">${fmt(c.valor)}</span></div>
          <div class="bar-bg"><div class="bar-fg" style="width:${Math.max(3, (c.valor / maxV) * 100)}%"></div></div>
        </div>`).join("");
    }
    function chartComparativo(fatura, conta) {
      const maxV = Math.max(fatura, conta, 1);
      return `
        <div class="bar-row"><div class="bar-top"><span class="bar-nm">FATURA</span><span class="bar-v num">${fmt(fatura)}</span></div><div class="bar-bg"><div class="bar-fg" style="width:${Math.max(3,(fatura/maxV)*100)}%"></div></div></div>
        <div class="bar-row"><div class="bar-top"><span class="bar-nm">CONTA</span><span class="bar-v num">${fmt(conta)}</span></div><div class="bar-bg"><div class="bar-fg alt" style="width:${Math.max(3,(conta/maxV)*100)}%"></div></div></div>
      `;
    }
    function seqExemplo(id) {
      let h = 0; for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
      const arr = []; for (let i = 0; i < 7; i++) { h = (h * 1103515245 + 12345) >>> 0; arr.push(18 + (h % 82)); }
      return arr;
    }
    function chartSeq(vals) {
      const maxV = Math.max(...vals, 1);
      return `<div class="seq-lbl">Sequência (exemplo)</div><div class="seq-bars">${vals.map(v => `<i style="height:${Math.max(10, (v / maxV) * 100)}%"></i>`).join("")}</div>`;
    }

    root.innerHTML = `
    <style>
      :host, * { box-sizing: border-box; }
      .wrap { font-family: 'Sora', sans-serif; color: #eee; background: #000; height: 760px; display: flex; position: relative; overflow: hidden; }
      .num { font-variant-numeric: tabular-nums; }
      .sidebar { width: 76px; flex-shrink: 0; height: 100%; display: flex; flex-direction: column; align-items: center; gap: 10px; padding-top: 16px; border-right: 1px solid #1c1c1c; background: #030303; }
      .navbtn { width: 64px; height: 64px; border-radius: 16px; border: 1px solid #1c1c1c; background: #0a0a0a; color: #6b6b6b; display: flex; align-items: center; justify-content: center; }
      .navbtn svg { width: 26px; height: 26px; }
      .navbtn.on { background: rgba(163,230,53,.14); border-color: ${AC}; color: ${AC}; }
      .content { flex: 1; min-width: 0; height: 100%; overflow-y: auto; -webkit-overflow-scrolling: touch; padding: 14px 12px 26px; }

      .hd { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
      .hd .tit { font-size: 22px; font-weight: 800; color: #fff; }
      .hd .sub { font-size: 12px; color: #8a8a8a; margin-top: 2px; }
      .clima-c { display: flex; align-items: center; gap: 6px; font-size: 15px; font-weight: 700; color: #d8d8d8; }
      .clima-c svg { width: 20px; height: 20px; color: ${AC}; }

      .mic-row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
      .mic-big { width: 64px; height: 64px; border-radius: 18px; background: ${AC}; color: #000; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
      .mic-big svg { width: 28px; height: 28px; }
      .mic-txt { font-size: 13px; color: #9a9a9a; }

      .aviso { display: flex; align-items: center; gap: 10px; background: #1c1206; border: 1px solid #4a3410; color: #f0c674; border-radius: 16px; padding: 14px 16px; min-height: 64px; margin-bottom: 12px; font-size: 14px; font-weight: 700; }
      .aviso svg { width: 22px; height: 22px; flex-shrink: 0; color: #e2b23d; }

      .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 10px; }
      .card { background: #0a0a0a; border: 1px solid #1c1c1c; border-radius: 18px; padding: 14px 15px; }
      .card.span2 { grid-column: 1 / -1; }
      .card .lbl { font-size: 11.5px; color: #8a8a8a; text-transform: uppercase; letter-spacing: .04em; font-weight: 700; }
      .card .v { font-size: 24px; font-weight: 800; color: #fff; margin-top: 6px; }
      .card .v.mid { font-size: 19px; }
      .card .s { font-size: 11px; color: #7a7a7a; margin-top: 4px; }
      .chlbl { font-size: 10px; fill: #aaa; font-family: 'Sora', sans-serif; font-weight: 700; }
      .chlbl-fr { font-size: 9.5px; fill: #666; font-family: 'Sora', sans-serif; }

      .btn-card { min-height: 64px; display: flex; align-items: center; gap: 10px; background: #0a0a0a; border: 1px solid #1c1c1c; border-radius: 18px; padding: 12px 14px; color: #eee; }
      .btn-card svg { width: 24px; height: 24px; color: ${AC}; flex-shrink: 0; }
      .btn-card span { font-size: 14px; font-weight: 700; }

      .chat-c { display: flex; align-items: center; gap: 8px; background: #0a0a0a; border: 1px solid #1c1c1c; border-radius: 16px; padding: 6px 6px 6px 16px; min-height: 64px; margin-top: 4px; }
      .chat-c input { flex: 1; background: transparent; border: none; outline: none; color: #eee; font-family: 'Sora', sans-serif; font-size: 14px; }
      .chat-c input::placeholder { color: #666; }
      .chat-c button { width: 48px; height: 48px; border-radius: 12px; background: ${AC}; color: #000; border: none; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
      .chat-c button svg { width: 18px; height: 18px; }

      .bar-row { margin-bottom: 16px; }
      .bar-row:last-child { margin-bottom: 0; }
      .bar-top { display: flex; justify-content: space-between; font-size: 13.5px; font-weight: 700; margin-bottom: 6px; color: #ddd; }
      .bar-bg { height: 18px; border-radius: 9px; background: #17170f; overflow: hidden; }
      .bar-fg { height: 100%; background: ${AC}; border-radius: 9px; }
      .bar-fg.alt { background: #555; }

      .li { display: flex; align-items: center; gap: 10px; padding: 13px 2px; border-bottom: 1px solid #161616; min-height: 44px; }
      .li .d { font-size: 11px; color: #7a7a7a; width: 34px; flex-shrink: 0; }
      .li .n { flex: 1; font-size: 13.5px; color: #ddd; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .li .v { font-size: 13.5px; font-weight: 700; color: #fff; }
      .mais { width: 100%; min-height: 64px; border-radius: 16px; border: 1px solid #1c1c1c; background: #0a0a0a; color: ${AC}; font-size: 14px; font-weight: 700; margin-top: 10px; }

      .toggle { width: 100%; min-height: 64px; display: flex; justify-content: space-between; align-items: center; padding: 0 16px; border-radius: 16px; border: 1px solid #1c1c1c; background: #0a0a0a; color: #ddd; font-size: 14px; font-weight: 700; margin-bottom: 10px; }
      .toggle svg { width: 16px; height: 16px; color: #7a7a7a; transition: transform .15s; }
      .toggle.open svg { transform: rotate(90deg); }
      .sub-list { display: none; }
      .sub-list.open { display: block; }
      .sub-row { display: flex; justify-content: space-between; padding: 11px 4px; font-size: 13px; color: #bbb; border-bottom: 1px solid #151515; }

      .g18 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
      .g18 button { min-height: 78px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; background: #0a0a0a; border: 1px solid #1c1c1c; border-radius: 16px; color: #ccc; padding: 6px 4px; }
      .g18 button svg { width: 22px; height: 22px; color: ${AC}; }
      .g18 button span { font-size: 10.5px; font-weight: 700; text-align: center; line-height: 1.2; }

      .modal-bg { position: absolute; inset: 0; background: rgba(0,0,0,.86); display: none; align-items: flex-end; z-index: 5; }
      .modal-bg.open { display: flex; }
      .modal { width: 100%; background: #0a0a0a; border-top: 1px solid #262626; border-radius: 20px 20px 0 0; padding: 20px; }
      .modal h3 { margin: 0 0 8px; font-size: 19px; color: #fff; font-weight: 800; }
      .modal p { margin: 0 0 12px; font-size: 13.5px; color: #aaa; line-height: 1.55; }
      .modal .x { width: 64px; height: 44px; border-radius: 12px; border: 1px solid #262626; background: #111; color: #ccc; display: flex; align-items: center; justify-content: center; float: right; }
      .modal .x svg { width: 18px; height: 18px; }
      .seq-lbl { font-size: 11px; color: #7a7a7a; font-weight: 700; text-transform: uppercase; margin-bottom: 8px; clear: both; }
      .seq-bars { display: flex; gap: 4px; align-items: flex-end; height: 36px; }
      .seq-bars i { flex: 1; background: ${AC}; opacity: .6; border-radius: 2px; display: block; }
      .viagem-box { margin-top: 4px; font-size: 12.5px; color: #9a9a9a; }
      .viagem-box b { color: ${AC}; }
    </style>
    <div class="wrap" id="wrap">
      <div class="sidebar" id="sidebar"></div>
      <div class="content" id="content"></div>
    </div>
    `;
    const content = root.getElementById("content");
    const sidebar = root.getElementById("sidebar");

    function telaHoje() {
      const clima = D.hoje.clima || {};
      const dias = fin.por_dia_mes || [];
      content.innerHTML = `
        <div class="hd"><div><div class="tit">${new Date().toLocaleTimeString("pt-BR",{hour:"2-digit",minute:"2-digit"})}</div><div class="sub">${D.hoje.data}</div></div><div class="clima-c">${ICONS.chuva}${clima.temp}°C</div></div>
        ${D.aviso_critico ? `<div class="aviso">${ICONS.alerta}<span>${D.aviso_critico}</span></div>` : ""}
        <div class="mic-row"><button class="mic-big" id="mic">${ICONS.mic}</button><span class="mic-txt">Toque e fale um comando</span></div>
        <div class="grid2">
          <div class="card span2">
            <div class="lbl">Gasto do mês</div>
            <div class="v num">${fmt(fin.gasto_mes)}</div>
            <div style="margin-top:10px">${chartArea(300, 92, dias, fin.gasto_mes_anterior, "MÊS ANT. " + fmtInt(fin.gasto_mes_anterior))}</div>
          </div>
          <div class="card"><div class="lbl">Hoje</div><div class="v mid num">${fmt(fin.gasto_hoje)}</div></div>
          <div class="card"><div class="lbl">Conta</div><div class="v mid num">${fmt(fin.saldo_conta)}</div></div>
          <div class="card span2"><div class="lbl">Fatura · vence ${(fin.fatura_vencimento||"").slice(8,10)}/${(fin.fatura_vencimento||"").slice(5,7)}</div><div class="v num">${fmt(fin.fatura_atual)}</div></div>
          <div class="card span2"><div class="lbl">Em foco agora</div><div class="v mid" style="font-size:16px">${(D.tarefas && D.tarefas.em_foco) || "—"}</div></div>
          <button class="btn-card" data-t="vida">${ICONS.tarefas}<span>Tarefas</span></button>
          <button class="btn-card" data-t="vida">${ICONS.aviacao}<span>Aviação</span></button>
        </div>
        <div class="chat-c"><input placeholder="Falar com o painel…"/><button>${ICONS.enviar}</button></div>
      `;
      content.querySelectorAll("[data-t]").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.t)));
    }

    function telaFinancas() {
      const cats = fin.por_categoria || [];
      const dias15 = fin.ultimos_15_dias || [];
      function li(d) {
        const dd = d.data.slice(8, 10) + "/" + d.data.slice(5, 7);
        return `<div class="li"><span class="d num">${dd}</span><span class="n">${d.descricao}</span><span class="v num">${fmt(Math.abs(d.valor))}</span></div>`;
      }
      content.innerHTML = `
        <div class="hd"><div class="tit">Finanças</div></div>
        <div class="card" style="margin-bottom:10px"><div class="lbl">Maiores categorias</div><div style="margin-top:10px">${chartTop5(cats)}</div></div>
        <div class="grid2">
          <div class="card"><div class="lbl">Gasto do mês</div><div class="v mid num">${fmt(fin.gasto_mes)}</div><div class="s">ant. ${fmt(fin.gasto_mes_anterior)}</div></div>
          <div class="card"><div class="lbl">Saldo em conta</div><div class="v mid num">${fmt(fin.saldo_conta)}</div></div>
        </div>
        <div class="card" style="margin-bottom:10px"><div class="lbl">Evolução por dia</div><div style="margin-top:10px">${chartArea(300, 88, fin.por_dia_mes || [], fin.gasto_mes_anterior, "MÊS ANT. " + fmtInt(fin.gasto_mes_anterior))}</div></div>
        <div class="card" style="margin-bottom:10px"><div class="lbl">Fatura × Conta</div><div style="margin-top:10px">${chartComparativo(fin.fatura_atual || 0, fin.saldo_conta || 0)}</div></div>
        <div class="card" style="margin-bottom:10px">
          <div class="lbl">Últimos dias</div>
          <div id="listaDias">${dias15.slice(0, 6).map(li).join("")}</div>
          ${dias15.length > 6 ? `<button class="mais" id="btnMais">Carregar mais (${dias15.length - 6})</button>` : ""}
        </div>
        <button class="toggle" id="btnAssin"><span>Assinaturas (${(fin.assinaturas||[]).length})</span>${ICONS.seta}</button>
        <div class="sub-list" id="assinList">${(fin.assinaturas||[]).map(a => `<div class="sub-row"><span>${a.nome}</span><span class="num">${fmt(a.valor)}</span></div>`).join("")}</div>
        <button class="toggle" id="btnExtrato"><span>Extrato completo</span>${ICONS.seta}</button>
        <div class="sub-list" id="extratoList">${dias15.map(li).join("")}</div>
      `;
      const btnMais = content.querySelector("#btnMais");
      if (btnMais) btnMais.addEventListener("click", () => { content.querySelector("#listaDias").innerHTML = dias15.map(li).join(""); btnMais.remove(); });
      content.querySelector("#btnAssin").addEventListener("click", function () { this.classList.toggle("open"); content.querySelector("#assinList").classList.toggle("open"); });
      content.querySelector("#btnExtrato").addEventListener("click", function () { this.classList.toggle("open"); content.querySelector("#extratoList").classList.toggle("open"); });
    }

    function telaVida() {
      const secs = D.vida_secoes || [];
      content.innerHTML = `
        <div class="hd"><div class="tit">Vida</div><div class="sub">${secs.length} seções</div></div>
        <div class="g18" id="g18">
          ${secs.map((s, i) => `<button data-id="${s.id}">${iconCiclo[i % iconCiclo.length]}<span>${s.nome}</span></button>`).join("")}
        </div>
        <div class="modal-bg" id="modalBg">
          <div class="modal">
            <button class="x" id="modalClose">${ICONS.fechar}</button>
            <h3 id="modalTit"></h3>
            <p id="modalRes"></p>
            <div id="modalViagem"></div>
            <div id="modalChart"></div>
          </div>
        </div>
      `;
      const bg = content.querySelector("#modalBg");
      function abrir(id) {
        const s = secs.find(x => x.id === id);
        if (!s) return;
        content.querySelector("#modalTit").textContent = s.nome;
        content.querySelector("#modalRes").textContent = s.resumo + ". Sem itens pendentes visíveis agora.";
        content.querySelector("#modalViagem").innerHTML = (s.id === "viagens" && D.viagem)
          ? `<div class="viagem-box">Próxima viagem: <b>${D.viagem.origem} → ${D.viagem.destino}</b> em ${D.viagem.dias_faltando} dias</div>` : "";
        content.querySelector("#modalChart").innerHTML = chartSeq(seqExemplo(s.id));
        bg.classList.add("open");
      }
      content.querySelectorAll("#g18 button").forEach(el => el.addEventListener("click", () => abrir(el.dataset.id)));
      content.querySelector("#modalClose").addEventListener("click", () => bg.classList.remove("open"));
      bg.addEventListener("click", e => { if (e.target === bg) bg.classList.remove("open"); });
    }

    function nav() {
      const tabs = [["hoje", ICONS.hoje], ["financas", ICONS.financas], ["vida", ICONS.vida]];
      sidebar.innerHTML = tabs.map(([t, ic]) => `<button class="navbtn ${ctx.tela === t ? "on" : ""}" data-t="${t}">${ic}</button>`).join("");
      sidebar.querySelectorAll("button").forEach(b => b.addEventListener("click", () => ctx.irPara(b.dataset.t)));
    }

    if (ctx.tela === "hoje") telaHoje();
    else if (ctx.tela === "financas") telaFinancas();
    else telaVida();
    nav();

    return () => { timers.forEach(clearInterval); cleanups.forEach(fn => fn()); };
  }
};
