(window.DIRECOES = window.DIRECOES || {})[3] = {
  nome: "Terminal",
  ideia: "Sessão de terminal: prompts $, barras ASCII, sparkline de blocos, tudo digitado.",
  acento: "#4ADE80",
  fontes: ["JetBrains+Mono:wght@400;500;700"],
  render(root, D, ctx) {
    const cur = D.financas;
    const brl = (v) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
    const timers = [];
    const rafs = [];

    const style = document.createElement("style");
    style.textContent = `
      :host, * { box-sizing: border-box; }
      .term {
        font-family: 'JetBrains Mono', monospace;
        color: #c9d6cf;
        background: #000;
        min-height: 100%;
        padding: 14px 12px 90px 12px;
        font-size: 13px;
        line-height: 1.55;
        -webkit-font-smoothing: antialiased;
      }
      .acc { color: #4ADE80; }
      .dim { color: #6b7a70; }
      .warn { color: #ff6b6b; }
      .row { display: flex; gap: 6px; white-space: pre-wrap; word-break: break-word; }
      .prompt { color: #4ADE80; flex: 0 0 auto; }
      .line { opacity: 0; animation: appear .18s forwards; }
      .bar { font-variant-numeric: tabular-nums; letter-spacing: -1px; }
      .tabular { font-variant-numeric: tabular-nums; }
      @keyframes appear { to { opacity: 1; } }
      .col { display: grid; grid-template-columns: 1fr auto; gap: 2px 10px; margin: 2px 0; }
      .col > div:nth-child(2n) { text-align: right; }
      .cat-row { display: flex; align-items: center; gap: 8px; white-space: nowrap; margin: 4px 0; opacity: 0; animation: appear .18s forwards; }
      .cat-row .name { width: 100px; overflow: hidden; text-overflow: ellipsis; color: #6b7a70; font-size: 12px; }
      .cat-row .bar { flex: 0 0 auto; letter-spacing: -1px; }
      .cat-row .val { flex: 1; text-align: right; }
      .cmd-btn {
        display: inline-block;
        border: 1px solid #21362a;
        color: #9fb3a6;
        background: #05100a;
        padding: 10px 12px;
        margin: 6px 6px 0 0;
        font-family: inherit;
        font-size: 12px;
        min-height: 44px;
        cursor: pointer;
      }
      .cmd-btn:active { border-color: #4ADE80; color: #4ADE80; }
      hr.rule { border: none; border-top: 1px solid #17251d; margin: 10px 0; }
      .out { padding-left: 14px; border-left: 1px solid #17251d; margin: 4px 0 10px 2px; }
      .sec-title { color: #4ADE80; }
      .footer {
        position: fixed; left: 0; right: 0; bottom: 0;
        background: #000; border-top: 1px solid #17251d;
        padding: 10px 12px calc(10px + env(safe-area-inset-bottom, 0px)) 12px;
        display: flex; gap: 8px; align-items: center;
        max-width: 430px; margin: 0 auto;
      }
      .chat-line { flex: 1; display: flex; align-items: center; gap: 6px; color: #c9d6cf; font-size: 13px; }
      .cursor { width: 8px; height: 15px; background: #4ADE80; display: inline-block; animation: blink 1s step-end infinite; }
      @keyframes blink { 50% { opacity: 0; } }
      .mic {
        width: 44px; height: 44px; border: 1px solid #21362a; background: #05100a;
        display: flex; align-items: center; justify-content: center; flex: 0 0 auto;
      }
      .collapsible { cursor: pointer; }
      .navbar {
        position: fixed; left: 0; right: 0; bottom: 46px;
        max-width: 430px; margin: 0 auto;
        display: none;
      }
      .expand { max-height: 0; overflow: hidden; transition: max-height .25s ease; }
      .expand.open { max-height: 800px; }
      .life-list div { padding: 6px 0; border-bottom: 1px solid #10190f; }
      .life-detail { padding: 8px 0 0 0; color: #9fb3a6; }
    `;

    const wrap = document.createElement("div");
    wrap.className = "term";
    root.appendChild(style);
    root.appendChild(wrap);

    // typed line rendering helper
    let delay = 0;
    function line(html, cls) {
      const d = document.createElement("div");
      d.className = "row line" + (cls ? " " + cls : "");
      d.style.animationDelay = ctx.reduzido ? "0s" : delay + "ms";
      d.innerHTML = html;
      if (ctx.reduzido) d.style.opacity = 1;
      delay += 35;
      return d;
    }
    function prompt(cmd) {
      const d = document.createElement("div");
      d.className = "row line";
      d.style.animationDelay = ctx.reduzido ? "0s" : delay + "ms";
      if (ctx.reduzido) d.style.opacity = 1;
      d.innerHTML = `<span class="prompt">$</span><span>${cmd}</span>`;
      delay += 35;
      return d;
    }
    function bar(pct, width = 20) {
      const filled = Math.round((pct / 100) * width);
      return "█".repeat(Math.max(0, Math.min(width, filled))) + "░".repeat(Math.max(0, width - filled));
    }
    function sparkline(vals) {
      const chars = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"];
      const max = Math.max(1, ...vals);
      return vals.map(v => chars[Math.min(chars.length - 1, Math.floor((v / max) * (chars.length - 1)))]).join("");
    }

    function screenHoje() {
      const now = new Date();
      wrap.appendChild(prompt("fin --hoje"));
      const out = document.createElement("div");
      out.className = "out";
      const hh = String(now.getHours()).padStart(2, "0");
      const mm = String(now.getMinutes()).padStart(2, "0");
      const timeSpan = document.createElement("span");
      timeSpan.className = "tabular";
      timeSpan.textContent = `${hh}:${mm}`;
      const l1 = line("");
      l1.appendChild(document.createTextNode(""));
      l1.innerHTML = `<span class="dim">local</span> `;
      l1.appendChild(timeSpan);
      l1.innerHTML += ` <span class="dim">· ${D.hoje.data} · ${D.hoje.cidade}</span>`;
      out.appendChild(l1);
      out.appendChild(line(`<span class="dim">clima</span> ${D.hoje.clima.cond}, ${D.hoje.clima.temp}°C, chuva ${D.hoje.clima.chuva_prob}%`));
      if (D.aviso_critico) {
        out.appendChild(line(`<span class="warn">! ${D.aviso_critico}</span>`));
      }
      wrap.appendChild(out);

      wrap.appendChild(prompt("fin --gasto-mes"));
      const out2 = document.createElement("div");
      out2.className = "out";
      const pctMes = Math.min(100, (cur.gasto_mes / (cur.orcamento_mes || cur.gasto_mes)) * 100);
      out2.appendChild(line(`<span class="bar acc">${bar(pctMes)}</span> <span class="tabular">${pctMes.toFixed(0)}%</span>`));
      out2.appendChild(line(`<span class="dim">total</span> <span class="acc tabular">${brl(cur.gasto_mes)}</span> <span class="dim">/ ${brl(cur.orcamento_mes)}</span>`));
      const spark = sparkline(cur.por_dia_mes.map(p => p.acumulado));
      out2.appendChild(line(`<span class="dim">curva</span> <span class="acc" style="letter-spacing:1px">${spark}</span>`));
      wrap.appendChild(out2);

      wrap.appendChild(prompt("fin --resumo"));
      const out3 = document.createElement("div");
      out3.className = "out col";
      out3.appendChild(Object.assign(document.createElement("div"), { className: "dim", textContent: "hoje" }));
      out3.appendChild(Object.assign(document.createElement("div"), { className: "tabular", textContent: brl(cur.gasto_hoje) }));
      out3.appendChild(Object.assign(document.createElement("div"), { className: "dim", textContent: "fatura" }));
      out3.appendChild(Object.assign(document.createElement("div"), { className: "tabular", textContent: brl(cur.fatura_atual) }));
      out3.appendChild(Object.assign(document.createElement("div"), { className: "dim", textContent: "conta" }));
      out3.appendChild(Object.assign(document.createElement("div"), { className: "tabular", textContent: brl(cur.saldo_conta) }));
      wrap.appendChild(out3);

      wrap.appendChild(prompt("tarefas --foco"));
      const out4 = document.createElement("div");
      out4.className = "out";
      out4.appendChild(line(`<span class="acc">›</span> ${D.tarefas.em_foco}`));
      wrap.appendChild(out4);

      const shortcuts = document.createElement("div");
      shortcuts.style.marginTop = "8px";
      ["Finanças", "Vida", "Tarefas", "Aviação"].forEach(name => {
        const b = document.createElement("button");
        b.className = "cmd-btn";
        b.textContent = "./" + name.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
        b.onclick = () => { if (name === "Finanças") ctx.irPara("financas"); else if (name === "Vida") ctx.irPara("vida"); };
        shortcuts.appendChild(b);
      });
      wrap.appendChild(shortcuts);
    }

    function screenFinancas() {
      wrap.appendChild(prompt("fin --extrato"));
      const out = document.createElement("div");
      out.className = "out";
      const dif = cur.gasto_mes - cur.gasto_mes_anterior;
      const sinal = dif <= 0 ? "▼" : "▲";
      out.appendChild(line(`<span class="dim">mes</span> <span class="acc tabular">${brl(cur.gasto_mes)}</span>`));
      out.appendChild(line(`<span class="dim">vs mes anterior</span> <span class="tabular">${sinal} ${brl(Math.abs(dif))}</span>`));
      out.appendChild(line(`<span class="dim">orcamento</span> <span class="tabular">${brl(cur.orcamento_mes)}</span>`));
      wrap.appendChild(out);

      wrap.appendChild(prompt("fin --categorias"));
      const out2 = document.createElement("div");
      out2.className = "out";
      const maxCat = Math.max(...cur.por_categoria.map(c => c.valor));
      cur.por_categoria.forEach((c, i) => {
        const pct = (c.valor / maxCat) * 100;
        const row = document.createElement("div");
        row.className = "cat-row";
        row.style.animationDelay = ctx.reduzido ? "0s" : (delay + i * 40) + "ms";
        if (ctx.reduzido) row.style.opacity = 1;
        row.innerHTML = `<span class="name">${c.categoria}</span><span class="acc bar">${bar(pct, 10)}</span><span class="tabular val">${brl(c.valor)}</span>`;
        out2.appendChild(row);
      });
      delay += cur.por_categoria.length * 40;
      wrap.appendChild(out2);

      wrap.appendChild(prompt("fin --fatura-conta"));
      const out3 = document.createElement("div");
      out3.className = "out";
      out3.appendChild(line(`<span class="dim">fatura atual</span> <span class="tabular">${brl(cur.fatura_atual)}</span>`));
      out3.appendChild(line(`<span class="dim">vence</span> <span class="tabular">${cur.fatura_vencimento}</span>`));
      out3.appendChild(line(`<span class="dim">saldo conta</span> <span class="tabular ${cur.saldo_conta < 100 ? 'warn' : ''}">${brl(cur.saldo_conta)}</span>`));
      wrap.appendChild(out3);

      wrap.appendChild(prompt("fin --ultimos-15 | head -6"));
      const out4 = document.createElement("div");
      out4.className = "out";
      const listEl = document.createElement("div");
      function renderList(items) {
        listEl.innerHTML = "";
        items.forEach(t => {
          listEl.appendChild(line(`<span class="dim tabular">${t.data.slice(5)}</span> ${t.descricao.slice(0, 20).padEnd(20, ".")} <span class="dim">${t.categoria.slice(0, 10)}</span> <span class="tabular">${brl(t.valor)}</span>`));
        });
      }
      renderList(cur.ultimos_15_dias.slice(0, 6));
      out4.appendChild(listEl);
      if (cur.ultimos_15_dias.length > 6) {
        const more = document.createElement("button");
        more.className = "cmd-btn";
        more.textContent = "carregar mais (--all)";
        more.onclick = () => { renderList(cur.ultimos_15_dias); more.remove(); };
        out4.appendChild(more);
      }
      wrap.appendChild(out4);

      wrap.appendChild(prompt("fin --assinaturas (toque p/ ver)"));
      const btnSub = document.createElement("button");
      btnSub.className = "cmd-btn";
      btnSub.textContent = "cat assinaturas.log";
      const subOut = document.createElement("div");
      subOut.className = "out expand";
      cur.assinaturas.forEach(s => {
        subOut.appendChild(line(`<span class="dim">${s.nome.padEnd(12, ".")}</span> <span class="tabular">${brl(s.valor)}</span> <span class="dim">prox ${s.proxima}</span>`));
      });
      btnSub.onclick = () => subOut.classList.toggle("open");
      wrap.appendChild(btnSub);
      wrap.appendChild(subOut);
    }

    function screenVida() {
      wrap.appendChild(prompt("ls vida/"));
      const grid = document.createElement("div");
      grid.className = "out";
      grid.style.display = "grid";
      grid.style.gridTemplateColumns = "repeat(2, 1fr)";
      grid.style.gap = "2px 10px";
      const detail = document.createElement("div");
      detail.className = "life-detail expand";
      const detailOut = document.createElement("div");
      detailOut.className = "out";
      D.vida_secoes.forEach(s => {
        const item = document.createElement("div");
        item.className = "collapsible tabular";
        item.innerHTML = `<span class="acc">·</span> ${s.id}/`;
        item.onclick = () => {
          detailOut.innerHTML = "";
          detailOut.appendChild(line(`<span class="acc">${s.nome}</span>`));
          detailOut.appendChild(line(`<span class="dim">${s.resumo}</span>`));
          if (s.id === "viagens" && D.viagem) {
            detailOut.appendChild(line(`<span class="dim">rota</span> ${D.viagem.origem} → ${D.viagem.destino}`));
            detailOut.appendChild(line(`<span class="dim">faltam</span> <span class="tabular">${D.viagem.dias_faltando}d</span> <span class="dim">(${D.viagem.data})</span>`));
          } else {
            detailOut.appendChild(line(`<span class="dim">itens</span> ${1 + (s.id.length % 4)} ativos`));
          }
          detail.classList.add("open");
        };
        grid.appendChild(item);
      });
      wrap.appendChild(grid);
      wrap.appendChild(prompt("cat <secao>"));
      detail.appendChild(detailOut);
      wrap.appendChild(detail);
    }

    if (ctx.tela === "hoje") screenHoje();
    else if (ctx.tela === "financas") screenFinancas();
    else screenVida();

    // footer chat + mic
    const footer = document.createElement("div");
    footer.className = "footer";
    const mic = document.createElement("div");
    mic.className = "mic";
    mic.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4ADE80" stroke-width="1.5"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/></svg>`;
    const chat = document.createElement("div");
    chat.className = "chat-line";
    chat.innerHTML = `<span class="prompt">$</span><span class="dim">falar com o painel...</span><span class="cursor"></span>`;
    footer.appendChild(mic);
    footer.appendChild(chat);
    root.appendChild(footer);

    return () => { timers.forEach(clearInterval); rafs.forEach(cancelAnimationFrame); };
  }
};
