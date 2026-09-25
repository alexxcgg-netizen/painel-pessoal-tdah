(window.DIRECOES = window.DIRECOES || {})[7] = {
  nome: "Mínimo",
  ideia: "Números gigantes e finos, réguas horizontais, nada de caixas — índice tipográfico puro.",
  acento: "#FFFFFF",
  fontes: ["Sora:wght@200;300;500"],
  render(root, D, ctx) {
    const cur = D.financas;
    const brl = (v) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
    const rafs = [];
    const timers = [];

    const style = document.createElement("style");
    style.textContent = `
      :host, * { box-sizing: border-box; }
      .min {
        font-family: 'Sora', sans-serif;
        color: #fff;
        background: #000;
        min-height: 100%;
        padding: 22px 20px 100px 20px;
      }
      .eyebrow { font-size: 11px; letter-spacing: .18em; text-transform: uppercase; color: #7a7a7a; font-weight: 300; margin-bottom: 4px; }
      .huge {
        font-weight: 200; font-variant-numeric: tabular-nums;
        font-size: 58px; line-height: 1.02; letter-spacing: -0.02em;
        margin: 2px 0 14px 0; word-break: break-word;
      }
      .rule { border: none; border-top: 1px solid #262626; margin: 16px 0; }
      .rule.thick { border-top: 1px solid #3a3a3a; }
      .row { display: flex; justify-content: space-between; align-items: baseline; padding: 10px 0; }
      .row .l { color: #b8b8b8; font-weight: 300; font-size: 14px; }
      .row .v { font-weight: 300; font-variant-numeric: tabular-nums; font-size: 16px; }
      .quiet { color: #666; font-size: 12px; font-weight: 300; margin-top: -8px; margin-bottom: 8px; }
      .warn { color: #fff; }
      .warn::before { content: "— "; }
      .mic {
        width: 44px; height: 44px; border: none; background: transparent;
        display: flex; align-items: center; justify-content: center;
        border-bottom: 1px solid #333;
      }
      .top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 18px; }
      .clock { font-size: 15px; font-weight: 300; font-variant-numeric: tabular-nums; }
      .date { color: #7a7a7a; font-size: 12px; font-weight: 300; margin-top: 2px; }
      svg.line-chart { display: block; width: 100%; height: 56px; margin: 10px 0 4px 0; }
      .cat-name { width: 40%; }
      .cat-bar-wrap { flex: 1; height: 1px; background: #262626; margin: 0 12px; position: relative; top: -1px; }
      .cat-bar { height: 1px; background: #fff; }
      .cat-row { display: flex; align-items: center; padding: 12px 0; }
      .cat-val { font-variant-numeric: tabular-nums; font-size: 13px; color: #d0d0d0; width: 90px; text-align: right; }
      .idx-item { padding: 14px 0; border-top: 1px solid #262626; cursor: pointer; }
      .idx-item:first-child { border-top: none; }
      .idx-name { font-size: 20px; font-weight: 300; }
      .idx-detail { max-height: 0; overflow: hidden; transition: max-height .22s ease; }
      .idx-detail.open { max-height: 300px; }
      .idx-detail p { color: #8a8a8a; font-size: 13px; font-weight: 300; margin: 8px 0 0 0; line-height: 1.5; }
      .footer {
        position: fixed; left: 0; right: 0; bottom: 0;
        background: #000; border-top: 1px solid #262626;
        padding: 12px 20px calc(12px + env(safe-area-inset-bottom, 0px)) 20px;
        display: flex; gap: 10px; align-items: center;
        max-width: 430px; margin: 0 auto;
      }
      .footer input-fake { flex: 1; }
      .chat-ph { flex: 1; color: #555; font-size: 14px; font-weight: 300; border-bottom: 1px solid #333; padding-bottom: 8px; }
      .shortcuts { display: flex; gap: 20px; margin-top: 20px; flex-wrap: wrap; }
      .shortcuts span { font-size: 12px; color: #b8b8b8; font-weight: 300; text-decoration: underline; text-underline-offset: 4px; text-decoration-color: #333; cursor: pointer; min-height: 44px; display: flex; align-items: center; }
      .more { color: #7a7a7a; font-size: 12px; font-weight: 300; text-decoration: underline; text-underline-offset: 3px; cursor: pointer; padding: 10px 0; display: inline-block; min-height: 24px; }
      .extract-row { display: flex; justify-content: space-between; padding: 9px 0; border-top: 1px solid #1c1c1c; font-size: 12px; }
      .extract-row .d { color: #666; width: 70px; }
      .extract-row .n { flex: 1; color: #b8b8b8; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; padding-right: 8px; }
      .extract-row .v { color: #d0d0d0; font-variant-numeric: tabular-nums; }
    `;

    const wrap = document.createElement("div");
    wrap.className = "min";
    root.appendChild(style);
    root.appendChild(wrap);

    function top() {
      const now = new Date();
      const hh = String(now.getHours()).padStart(2, "0");
      const mm = String(now.getMinutes()).padStart(2, "0");
      const t = document.createElement("div");
      t.className = "top";
      t.innerHTML = `
        <div>
          <div class="clock">${hh}:${mm}</div>
          <div class="date">${D.hoje.cidade} · ${D.hoje.clima.temp}°C, ${D.hoje.clima.cond.toLowerCase()}</div>
        </div>
        <div class="mic"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.3"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/></svg></div>
      `;
      wrap.appendChild(t);
      if (D.aviso_critico) {
        const w = document.createElement("div");
        w.className = "warn";
        w.style.fontSize = "13px";
        w.style.fontWeight = "300";
        w.style.margin = "0 0 18px 0";
        w.textContent = D.aviso_critico;
        wrap.appendChild(w);
      }
    }

    function lineChart(points, w = 350, h = 56) {
      const max = Math.max(1, ...points);
      const stepX = w / (points.length - 1);
      const path = points.map((v, i) => `${i === 0 ? "M" : "L"}${(i * stepX).toFixed(1)},${(h - (v / max) * (h - 4) - 2).toFixed(1)}`).join(" ");
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
      svg.classList.add("line-chart");
      const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
      p.setAttribute("d", path);
      p.setAttribute("fill", "none");
      p.setAttribute("stroke", "#fff");
      p.setAttribute("stroke-width", "1.2");
      const len = points.length * 8;
      p.style.strokeDasharray = String(len);
      p.style.strokeDashoffset = ctx.reduzido ? "0" : String(len);
      svg.appendChild(p);
      if (!ctx.reduzido) {
        requestAnimationFrame(() => {
          p.style.transition = "stroke-dashoffset 1.1s ease";
          p.style.strokeDashoffset = "0";
        });
      }
      return svg;
    }

    function screenHoje() {
      top();
      const eb = document.createElement("div");
      eb.className = "eyebrow";
      eb.textContent = "gasto do mês";
      wrap.appendChild(eb);
      const huge = document.createElement("div");
      huge.className = "huge";
      huge.textContent = brl(cur.gasto_mes);
      wrap.appendChild(huge);
      wrap.appendChild(lineChart(cur.por_dia_mes.map(p => p.acumulado)));
      const q = document.createElement("div");
      q.className = "quiet";
      const pct = Math.min(100, (cur.gasto_mes / (cur.orcamento_mes || 1)) * 100);
      q.textContent = `${pct.toFixed(0)}% de ${brl(cur.orcamento_mes)}`;
      wrap.appendChild(q);

      const hr = document.createElement("hr");
      hr.className = "rule thick";
      wrap.appendChild(hr);

      [
        ["hoje", cur.gasto_hoje],
        ["fatura", cur.fatura_atual],
        ["conta", cur.saldo_conta],
      ].forEach(([l, v]) => {
        const r = document.createElement("div");
        r.className = "row";
        r.innerHTML = `<span class="l">${l}</span><span class="v">${brl(v)}</span>`;
        wrap.appendChild(r);
      });

      const hr2 = document.createElement("hr");
      hr2.className = "rule";
      wrap.appendChild(hr2);

      const foco = document.createElement("div");
      foco.className = "eyebrow";
      foco.textContent = "em foco agora";
      wrap.appendChild(foco);
      const focoV = document.createElement("div");
      focoV.style.fontSize = "16px";
      focoV.style.fontWeight = "300";
      focoV.style.margin = "4px 0 4px 0";
      focoV.textContent = D.tarefas.em_foco;
      wrap.appendChild(focoV);

      const sc = document.createElement("div");
      sc.className = "shortcuts";
      ["Finanças", "Vida", "Tarefas", "Aviação"].forEach(name => {
        const s = document.createElement("span");
        s.textContent = name;
        s.onclick = () => { if (name === "Finanças") ctx.irPara("financas"); else if (name === "Vida") ctx.irPara("vida"); };
        sc.appendChild(s);
      });
      wrap.appendChild(sc);
    }

    function screenFinancas() {
      const eb = document.createElement("div");
      eb.className = "eyebrow";
      eb.textContent = "gasto do mês";
      wrap.appendChild(eb);
      const huge = document.createElement("div");
      huge.className = "huge";
      huge.style.fontSize = "44px";
      huge.textContent = brl(cur.gasto_mes);
      wrap.appendChild(huge);
      const dif = cur.gasto_mes - cur.gasto_mes_anterior;
      const q = document.createElement("div");
      q.className = "quiet";
      q.textContent = `${dif <= 0 ? "queda" : "alta"} de ${brl(Math.abs(dif))} vs mês anterior · orçamento ${brl(cur.orcamento_mes)}`;
      wrap.appendChild(q);

      const hr = document.createElement("hr");
      hr.className = "rule thick";
      wrap.appendChild(hr);

      const ebc = document.createElement("div");
      ebc.className = "eyebrow";
      ebc.textContent = "categorias";
      wrap.appendChild(ebc);
      const maxCat = Math.max(...cur.por_categoria.map(c => c.valor));
      cur.por_categoria.forEach(c => {
        const row = document.createElement("div");
        row.className = "cat-row";
        const pct = (c.valor / maxCat) * 100;
        row.innerHTML = `
          <span class="l cat-name">${c.categoria}</span>
          <span class="cat-bar-wrap"><span class="cat-bar" style="width:${pct}%"></span></span>
          <span class="cat-val">${brl(c.valor)}</span>
        `;
        wrap.appendChild(row);
      });

      const hr2 = document.createElement("hr");
      hr2.className = "rule";
      wrap.appendChild(hr2);

      [["fatura atual", cur.fatura_atual + " · vence " + cur.fatura_vencimento], ["saldo conta", brl(cur.saldo_conta)]].forEach(([l, v], i) => {
        const r = document.createElement("div");
        r.className = "row";
        r.innerHTML = `<span class="l">${l}</span><span class="v">${i === 0 ? brl(cur.fatura_atual) + " · " + cur.fatura_vencimento.slice(5) : v}</span>`;
        wrap.appendChild(r);
      });

      const hr3 = document.createElement("hr");
      hr3.className = "rule";
      wrap.appendChild(hr3);

      const ebe = document.createElement("div");
      ebe.className = "eyebrow";
      ebe.textContent = "últimos 15 dias";
      wrap.appendChild(ebe);
      const listEl = document.createElement("div");
      function renderList(items) {
        listEl.innerHTML = "";
        items.forEach(t => {
          const r = document.createElement("div");
          r.className = "extract-row";
          r.innerHTML = `<span class="d">${t.data.slice(5)}</span><span class="n">${t.descricao}</span><span class="v">${brl(t.valor)}</span>`;
          listEl.appendChild(r);
        });
      }
      renderList(cur.ultimos_15_dias.slice(0, 6));
      wrap.appendChild(listEl);
      if (cur.ultimos_15_dias.length > 6) {
        const more = document.createElement("span");
        more.className = "more";
        more.textContent = "carregar mais";
        more.onclick = () => { renderList(cur.ultimos_15_dias); more.remove(); };
        wrap.appendChild(more);
      }

      const hr4 = document.createElement("hr");
      hr4.className = "rule";
      wrap.appendChild(hr4);

      const subToggle = document.createElement("span");
      subToggle.className = "more";
      subToggle.textContent = "assinaturas";
      const subBox = document.createElement("div");
      subBox.className = "idx-detail";
      const subInner = document.createElement("div");
      subInner.style.padding = "8px 0";
      cur.assinaturas.forEach(s => {
        const r = document.createElement("div");
        r.className = "row";
        r.innerHTML = `<span class="l">${s.nome}</span><span class="v">${brl(s.valor)}</span>`;
        subInner.appendChild(r);
      });
      subBox.appendChild(subInner);
      subToggle.onclick = () => subBox.classList.toggle("open");
      wrap.appendChild(subToggle);
      wrap.appendChild(subBox);
    }

    function screenVida() {
      const eb = document.createElement("div");
      eb.className = "eyebrow";
      eb.textContent = "índice";
      wrap.appendChild(eb);
      D.vida_secoes.forEach(s => {
        const item = document.createElement("div");
        item.className = "idx-item";
        const name = document.createElement("div");
        name.className = "idx-name";
        name.textContent = s.nome;
        const detail = document.createElement("div");
        detail.className = "idx-detail";
        const p1 = document.createElement("p");
        p1.textContent = s.resumo;
        detail.appendChild(p1);
        if (s.id === "viagens" && D.viagem) {
          const p2 = document.createElement("p");
          p2.textContent = `${D.viagem.origem} → ${D.viagem.destino} · faltam ${D.viagem.dias_faltando} dias (${D.viagem.data})`;
          detail.appendChild(p2);
        } else {
          const p2 = document.createElement("p");
          p2.textContent = `${1 + (s.id.length % 4)} itens ativos`;
          detail.appendChild(p2);
        }
        item.appendChild(name);
        item.appendChild(detail);
        item.onclick = () => detail.classList.toggle("open");
        wrap.appendChild(item);
      });
    }

    if (ctx.tela === "hoje") screenHoje();
    else if (ctx.tela === "financas") screenFinancas();
    else screenVida();

    const footer = document.createElement("div");
    footer.className = "footer";
    footer.innerHTML = `<div class="chat-ph">falar com o painel</div>`;
    root.appendChild(footer);

    return () => { timers.forEach(clearInterval); rafs.forEach(cancelAnimationFrame); };
  }
};
