(window.DIRECOES = window.DIRECOES || {})[10] = {
  nome: "Histórias",
  ideia: "Tela cheia estilo stories: barrinhas de progresso no topo, toca à direita avança / esquerda volta.",
  acento: "#FF9F0A",
  fontes: ["Manrope:wght@500;700;800", "Inter:wght@400;500;600"],
  render(root, D, ctx) {
    const F = D.financas, T = D.tarefas;
    const brl = (v) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);
    const brl0 = (v) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(v || 0);
    let timeoutId = null;

    const ICONS = {
      mic: '<rect x="9.3" y="2.5" width="5.4" height="11" rx="2.7"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0"/><path d="M12 17.5v3.3"/>',
      alerta: '<path d="M12 3.5 22 20.5H2z"/><path d="M12 9.5v5.2"/><circle cx="12" cy="17.6" r=".2" fill="currentColor"/>',
      alvo: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.4"/>',
      seta: '<path d="M9 6l6 6-6 6"/>',
      chat: '<path d="M4 5h16v11H8l-4 4z"/>',
      plus: '<path d="M12 5v14M5 12h14"/>'
    };
    const svg = (name, size = 18) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ""}</svg>`;

    const style = document.createElement("style");
    style.textContent = `
      :host, * { box-sizing:border-box; }
      .app { position:relative; min-height:760px; background:#050403; color:#fbf3ea; font-family:'Inter',system-ui,sans-serif;
             overflow:hidden; -webkit-font-smoothing:antialiased; }
      .num { font-family:'Manrope',sans-serif; font-variant-numeric:tabular-nums; }
      .fraco { color:#a89a86; }
      .telasel { position:absolute; top:10px; right:12px; z-index:6; display:flex; gap:4px; background:#0000; }
      .telasel button { border:1px solid #3a2f22; background:#150f09cc; color:#c9b8a1; font:inherit; font-size:10.5px;
                         padding:7px 9px; min-height:30px; border-radius:20px; cursor:pointer; letter-spacing:.02em; }
      .telasel button[aria-current="true"] { background:#FF9F0A; color:#1a1000; border-color:#FF9F0A; font-weight:700; }
      .barras { position:absolute; top:10px; left:10px; right:66px; display:flex; gap:4px; z-index:6; }
      .pbar { flex:1; height:3px; border-radius:2px; background:#3a2f2299; overflow:hidden; }
      .pbar > i { display:block; height:100%; width:0%; background:#FF9F0A; }
      .cabecalho { position:absolute; top:22px; left:12px; right:12px; z-index:5; display:flex; align-items:center; justify-content:space-between; }
      .titulo-mini { font-size:11px; text-transform:uppercase; letter-spacing:.12em; color:#c9b8a1; }
      .palco-stories { position:absolute; inset:0; }
      .conteudo { position:absolute; top:58px; left:0; right:0; bottom:0; padding:14px 20px 90px; overflow-y:auto; z-index:4; cursor:pointer; }
      .slide { min-height:100%; display:flex; flex-direction:column; justify-content:center; gap:14px; animation:in .35s ease; }
      @keyframes in { from{opacity:0; transform:translateY(6px);} to{opacity:1; transform:translateY(0);} }
      .rot { font-size:12px; color:#c9b8a1; text-transform:uppercase; letter-spacing:.1em; }
      .grande { font-size:44px; font-weight:800; line-height:1.02; letter-spacing:-.01em; }
      .grande.md { font-size:34px; }
      .linha2 { font-size:14px; color:#c9b8a1; }
      .relogio { font-size:64px; font-weight:800; letter-spacing:-.02em; }
      .data-lbl { font-size:14px; color:#c9b8a1; margin-top:2px; }
      .clima-box { display:flex; align-items:center; gap:10px; margin-top:16px; font-size:14px; color:#e8dcc9; }
      .mic-btn { width:52px; height:52px; border-radius:26px; background:#FF9F0A; color:#1a1000; display:flex; align-items:center;
                 justify-content:center; margin-top:18px; border:0; cursor:pointer; }
      .aviso-card { border:1px solid #4a2a12; background:#1c0f06; border-radius:18px; padding:18px; display:flex; gap:12px; align-items:flex-start; }
      .aviso-card svg { color:#ff9d5a; flex:0 0 auto; margin-top:2px; }
      .aviso-ok { border:1px solid #2c2318; background:#120e08; border-radius:18px; padding:18px; }
      .stat-row { display:flex; gap:10px; margin-top:6px; }
      .stat { flex:1; border:1px solid #2c2318; border-radius:14px; padding:11px 12px; background:#120e08cc; }
      .stat .r { font-size:10px; color:#a89a86; text-transform:uppercase; letter-spacing:.06em; }
      .stat .v { font-size:15px; font-weight:700; margin-top:4px; }
      .grafico-legenda { display:flex; justify-content:space-between; font-size:9.5px; color:#a89a86; margin-top:2px; }
      .barra-vs { height:11px; border-radius:6px; background:#241a0f; overflow:hidden; margin-top:12px; }
      .barra-vs > i { display:block; height:100%; border-radius:6px; background:#FF9F0A; }
      .cat-tag { display:inline-block; font-size:11px; color:#a89a86; border:1px solid #3a2f22; border-radius:20px; padding:5px 11px; align-self:flex-start; }
      .pend-list { display:flex; flex-direction:column; gap:8px; margin-top:6px; }
      .pend-item { font-size:13px; color:#e8dcc9; display:flex; justify-content:space-between; border-bottom:1px solid #221a11; padding-bottom:8px; }
      .pend-item span.q { color:#a89a86; font-size:11.5px; }
      .chip-row2 { display:flex; gap:10px; flex-wrap:wrap; margin-top:6px; }
      .chip2 { border:1px solid #3a2f22; background:#120e08; color:#f0e6d6; border-radius:14px; padding:12px 16px; font-size:13px;
               min-height:44px; display:flex; align-items:center; cursor:pointer; }
      .chatfield { display:flex; align-items:center; gap:10px; border:1px solid #3a2f22; background:#120e08; border-radius:24px;
                   padding:8px 8px 8px 16px; margin-top:14px; min-height:44px; }
      .chatfield span { flex:1; color:#a89a86; font-size:13px; }
      .chatfield .cursor { width:1.5px; height:14px; background:#ffb84d; animation:blink 1s step-end infinite; }
      @keyframes blink { 50% { opacity:0; } }
      .cta2 { border:1px solid #3a2f22; background:#150f09; color:#f0e6d6; border-radius:12px; padding:11px 14px; font-size:12.5px;
              min-height:44px; align-self:flex-start; cursor:pointer; margin-top:4px; }
      .lista15 { display:flex; flex-direction:column; gap:0; margin-top:4px; }
      .item15 { display:flex; justify-content:space-between; gap:10px; padding:10px 0; border-bottom:1px solid #221a11; font-size:13px; }
      .item15 .d { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
      .item15 .m { color:#a89a86; font-size:11px; }
      .assin-item { display:flex; justify-content:space-between; padding:10px 0; border-bottom:1px solid #221a11; font-size:13.5px; }
      .storycircles { position:absolute; top:56px; left:0; right:0; padding:0 12px; display:flex; gap:10px; overflow-x:auto;
                      scrollbar-width:none; z-index:5; }
      .storycircles::-webkit-scrollbar { display:none; }
      .sc-item { display:flex; flex-direction:column; align-items:center; gap:5px; flex:0 0 auto; cursor:pointer; }
      .sc-ring { width:48px; height:48px; border-radius:50%; border:2px solid #3a2f22; display:flex; align-items:center;
                 justify-content:center; font-size:14px; font-weight:700; color:#e8dcc9; background:#120e08; }
      .sc-item[data-atual="true"] .sc-ring { border-color:#FF9F0A; }
      .sc-item span.lbl { font-size:9px; color:#a89a86; max-width:52px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
      .conteudo-vida { top:118px; }
      .mini-chart-wrap { margin-top:8px; }
      .legenda2 { font-size:10.5px; color:#a89a86; margin-top:4px; }
    `;
    root.appendChild(style);
    const wrap = document.createElement("div");
    wrap.className = "app";
    root.appendChild(wrap);

    function fmtData(iso) { if (!iso) return "—"; const d = new Date(iso + "T12:00:00"); return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" }); }
    function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
    function iniciais(nome) { return nome.split(" ").map(w => w[0]).slice(0, 2).join("").toUpperCase(); }
    function seedNum(str) { let h = 0; for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0; return h; }

    function lineChartSVG(dias, refValor, refLabel, gid, cor) {
      const w = 294, h = 108, padL = 4, padR = 4, padT = 14, padB = 4;
      const vals = dias.map(d => d.acumulado);
      const max = Math.max(1, ...vals, refValor || 0);
      const n = vals.length;
      const x = i => padL + (n > 1 ? (i / (n - 1)) * (w - padL - padR) : 0);
      const y = v => padT + (1 - v / max) * (h - padT - padB);
      const pts = vals.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
      const area = `${x(0).toFixed(1)},${y(0).toFixed(1)} ${pts} ${x(n - 1).toFixed(1)},${y(0).toFixed(1)}`;
      const refY = refValor ? y(Math.min(refValor, max)).toFixed(1) : null;
      return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="none">
        <defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${cor}"/><stop offset="1" stop-color="${cor}" stop-opacity="0"/></linearGradient></defs>
        <text x="${padL}" y="10" font-size="9" fill="#a89a86">${brl0(max)}</text>
        ${refY ? `<line x1="${padL}" y1="${refY}" x2="${w - padR}" y2="${refY}" stroke="#7a6c56" stroke-width="1" stroke-dasharray="3 3"/>
        <text x="${w - padR}" y="${(+refY - 4).toFixed(1)}" text-anchor="end" font-size="9" fill="#a89a86">${refLabel}</text>` : ""}
        <polygon points="${area}" fill="url(#${gid})" opacity=".45"/>
        <polyline points="${pts}" fill="none" stroke="${cor}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>
        <circle cx="${x(n - 1).toFixed(1)}" cy="${y(vals[n - 1]).toFixed(1)}" r="3.4" fill="${cor}"/>
      </svg><div class="grafico-legenda"><span>dia 1</span><span>dia ${n}</span></div>`;
    }
    function miniBarSVG(vals, cor) {
      const w = 200, h = 40, gap = 3, n = vals.length, barW = (w - gap * (n - 1)) / n;
      const max = Math.max(1, ...vals);
      const bars = vals.map((v, i) => { const bh = Math.max(2, (v / max) * h); const x = i * (barW + gap); return `<rect x="${x.toFixed(1)}" y="${(h - bh).toFixed(1)}" width="${barW.toFixed(1)}" height="${bh.toFixed(1)}" rx="1.5" fill="${cor}"/>`; }).join("");
      return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}">${bars}</svg>`;
    }

    // ---------- construção das listas de slides por tela ----------
    function slidesHoje() {
      const now = new Date();
      const hh = String(now.getHours()).padStart(2, "0"), mm = String(now.getMinutes()).padStart(2, "0");
      const dataFmt = cap(new Date(D.hoje.data + "T12:00:00").toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "long" }));
      const dif = F.gasto_mes - F.gasto_mes_anterior;
      return [
        { tit: "Agora", html: () => `
          <div class="slide">
            <div class="relogio num">${hh}:${mm}</div>
            <div class="data-lbl">${dataFmt} · ${D.hoje.cidade}</div>
            <div class="clima-box">${D.hoje.clima.cond} · <span class="num">${D.hoje.clima.temp}°C</span> · chuva ${D.hoje.clima.chuva_prob}%</div>
            <button class="mic-btn" data-stop="1" aria-label="Comando de voz">${svg("mic", 22)}</button>
          </div>` },
        { tit: "Aviso", html: () => D.aviso_critico ? `
          <div class="slide">
            <div class="aviso-card">${svg("alerta", 26)}<div><div class="rot" style="color:#ff9d5a">Aviso importante</div>
              <div style="font-size:17px;margin-top:6px;line-height:1.4">${D.aviso_critico}</div></div></div>
          </div>` : `<div class="slide"><div class="aviso-ok"><div class="rot">Tudo em ordem</div>
              <div style="font-size:17px;margin-top:6px">Nenhum aviso crítico agora.</div></div></div>` },
        { tit: "Gasto do mês", html: () => `
          <div class="slide">
            <div class="rot">Gasto do mês · ${F.mes}</div>
            <div class="grande num">${brl(F.gasto_mes)}</div>
            <div class="linha2 ${dif <= 0 ? "" : ""}">${dif <= 0 ? "▼" : "▲"} ${brl0(Math.abs(dif))} vs. mês anterior</div>
            <div>${lineChartSVG(F.por_dia_mes, F.gasto_mes_anterior, "mês ant. " + brl0(F.gasto_mes_anterior), "gh1", "#FF9F0A")}</div>
            <div class="stat-row">
              <div class="stat"><div class="r">Hoje</div><div class="v num">${brl(F.gasto_hoje)}</div></div>
              <div class="stat"><div class="r">Fatura</div><div class="v num">${brl(F.fatura_atual)}</div></div>
              <div class="stat"><div class="r">Conta</div><div class="v num">${brl(F.saldo_conta)}</div></div>
            </div>
          </div>` },
        { tit: "Em foco", html: () => `
          <div class="slide">
            <div class="rot">Em foco agora</div>
            <div class="grande md">${T.em_foco}</div>
            <div class="pend-list">${T.pendentes.slice(0, 3).map(p => `<div class="pend-item"><span>${p.titulo}</span><span class="q">${p.quando}</span></div>`).join("")}</div>
          </div>` },
        { tit: "Agenda", html: () => `
          <div class="slide">
            <div class="rot">Atalhos</div>
            <div class="chip-row2">
              <button class="chip2" data-stop="1" data-ir="financas">Finanças ${svg("seta", 14)}</button>
              <button class="chip2" data-stop="1" data-ir="vida">Vida ${svg("seta", 14)}</button>
            </div>
            <div class="chatfield" data-stop="1">${svg("chat", 16)}<span>Falar com o painel…</span><span class="cursor"></span></div>
          </div>` }
      ];
    }

    function slidesFinancas() {
      const dif = F.gasto_mes - F.gasto_mes_anterior;
      const cats = [...F.por_categoria].sort((a, b) => b.valor - a.valor);
      const totalCat = cats.reduce((s, c) => s + c.valor, 0) || 1;
      const catPalette = ["#FF9F0A", "#FFC069", "#E88A1F", "#D97706", "#B45309", "#FFD699", "#8A5A1E", "#C77F19"];
      const slides = [
        { tit: "Resumo", html: () => `
          <div class="slide">
            <div class="rot">Gasto do mês · ${F.mes}</div>
            <div class="grande num">${brl(F.gasto_mes)}</div>
            <div class="linha2">${dif <= 0 ? "▼" : "▲"} ${brl0(Math.abs(dif))} vs. ${brl0(F.gasto_mes_anterior)} do mês anterior</div>
            ${F.orcamento_mes ? `<div class="linha2">Orçamento: ${brl0(F.orcamento_mes)}</div>` : ""}
          </div>` },
        { tit: "Evolução", html: () => `
          <div class="slide">
            <div class="rot">Evolução do mês, dia a dia</div>
            <div>${lineChartSVG(F.por_dia_mes, F.gasto_mes_anterior, "mês ant. " + brl0(F.gasto_mes_anterior), "gh2", "#FF9F0A")}</div>
          </div>` }
      ];
      cats.forEach((c, i) => {
        const pct = (c.valor / totalCat) * 100;
        slides.push({ tit: c.categoria, html: () => `
          <div class="slide">
            <span class="cat-tag">Categoria ${i + 1} de ${cats.length}</span>
            <div class="rot">${c.categoria}</div>
            <div class="grande num" style="color:${catPalette[i % catPalette.length]}">${brl(c.valor)}</div>
            <div class="linha2">${pct.toFixed(1)}% do total categorizado (${brl0(totalCat)})</div>
            <div class="barra-vs"><i style="width:${pct}%;background:${catPalette[i % catPalette.length]}"></i></div>
          </div>` });
      });
      slides.push({ tit: "Fatura x conta", html: () => {
        const max = Math.max(F.fatura_atual, F.saldo_conta, 1);
        const pFat = Math.max(3, (F.fatura_atual / max) * 100), pConta = Math.max(3, (F.saldo_conta / max) * 100);
        const critico = F.saldo_conta < F.fatura_atual * 0.15;
        return `<div class="slide">
          <div class="rot">Fatura x conta</div>
          <div class="linha2">Fatura · vence ${fmtData(F.fatura_vencimento)}</div>
          <div class="grande md num">${brl(F.fatura_atual)}</div>
          <div class="barra-vs"><i style="width:${pFat}%"></i></div>
          <div class="linha2" style="margin-top:14px">Saldo em conta</div>
          <div class="grande md num" style="color:${critico ? "#ff9d5a" : "#fbf3ea"}">${brl(F.saldo_conta)}</div>
          <div class="barra-vs"><i style="width:${pConta}%;background:${critico ? "#ff8a4a" : "#FF9F0A"}"></i></div>
        </div>`; } });
      slides.push({ tit: "Últimos 15 dias", html: (elC) => {
        setTimeout(() => {
          const btn = elC.querySelector("#mais15");
          if (btn) btn.addEventListener("click", (e) => { e.stopPropagation();
            elC.querySelector("#l15").innerHTML = itens15(F.ultimos_15_dias); btn.remove(); });
        }, 0);
        return `<div class="slide">
          <div class="rot">Últimos 15 dias</div>
          <div class="lista15" id="l15">${itens15(F.ultimos_15_dias.slice(0, 6))}</div>
          ${F.ultimos_15_dias.length > 6 ? `<button class="cta2" id="mais15" data-stop="1">Carregar mais (${F.ultimos_15_dias.length - 6})</button>` : ""}
        </div>`; } });
      slides.push({ tit: "Assinaturas", html: () => `
        <div class="slide">
          <div class="rot">Assinaturas ativas</div>
          <div class="grande md num">${brl(F.assinaturas.reduce((s, a) => s + a.valor, 0))}<span style="font-size:14px;color:#a89a86"> /mês</span></div>
          <div>${F.assinaturas.map(a => `<div class="assin-item"><span>${a.nome} · próx. ${fmtData(a.proxima)}</span><span class="num">${brl(a.valor)}</span></div>`).join("")}</div>
        </div>` });
      return slides;
      function itens15(arr) { return arr.map(t => `<div class="item15"><div class="d">${t.descricao}<div class="m">${fmtData(t.data)} · ${t.categoria}</div></div><div class="num">${brl(t.valor)}</div></div>`).join(""); }
    }

    function slidesVida() {
      return D.vida_secoes.map(s => ({
        tit: s.nome, sec: s,
        html: () => {
          let extra = `<div class="linha2">${1 + (s.id.length % 4)} itens ativos nesta seção.</div>`;
          let chart;
          if (s.id === "viagens" && D.viagem) {
            extra = `<div class="linha2">Próxima viagem: ${D.viagem.origem} → ${D.viagem.destino}</div>`;
            const pct = Math.max(6, 100 - Math.min(100, (D.viagem.dias_faltando / 30) * 100));
            chart = `<div class="mini-chart-wrap"><div class="barra-vs" style="height:9px"><i style="width:${pct}%"></i></div>
              <div class="legenda2">${D.viagem.dias_faltando} dias até o embarque · ${fmtData(D.viagem.data)}</div></div>`;
          } else {
            const seed = seedNum(s.id);
            const vals = Array.from({ length: 7 }, (_, i) => 2 + ((seed >> (i * 3)) % 9));
            chart = `<div class="mini-chart-wrap">${miniBarSVG(vals, "#FF9F0A")}<div class="legenda2">Atividade da semana (exemplo) · seg–dom</div></div>`;
          }
          return `<div class="slide">
            <div class="rot">${s.nome}</div>
            <div class="grande md">${s.resumo}</div>
            ${extra}
            ${chart}
          </div>`;
        }
      }));
    }

    // ---------- motor de stories ----------
    let tela = ctx.tela, idx = 0;
    const barrasEl = document.createElement("div"); barrasEl.className = "barras";
    const cabecalhoEl = document.createElement("div"); cabecalhoEl.className = "cabecalho";
    const telaselEl = document.createElement("div"); telaselEl.className = "telasel";
    telaselEl.innerHTML = ["hoje", "financas", "vida"].map(t => `<button data-t="${t}" aria-current="${t === tela}">${t === "hoje" ? "Hoje" : t === "financas" ? "Fin." : "Vida"}</button>`).join("");
    const scEl = document.createElement("div"); scEl.className = "storycircles";
    const conteudoEl = document.createElement("div"); conteudoEl.className = "conteudo";
    conteudoEl.setAttribute("aria-label", "Toque à direita para avançar, à esquerda para voltar");
    wrap.append(barrasEl, cabecalhoEl, telaselEl, scEl, conteudoEl);
    conteudoEl.addEventListener("click", (e) => {
      const rect = wrap.getBoundingClientRect();
      const x = e.clientX - rect.left;
      avancar(x < rect.width * 0.4 ? -1 : 1);
    });
    cabecalhoEl.innerHTML = `<span class="titulo-mini" id="tit-atual"></span><span></span>`;

    function slidesAtuais() { return tela === "hoje" ? slidesHoje() : tela === "financas" ? slidesFinancas() : slidesVida(); }

    function montarBarras() {
      const n = slidesAtuais().length;
      barrasEl.innerHTML = Array.from({ length: n }, (_, i) => `<div class="pbar"><i id="pbar-${i}"></i></div>`).join("");
    }
    function montarCirculos() {
      if (tela !== "vida") { scEl.style.display = "none"; conteudoEl.classList.remove("conteudo-vida"); return; }
      scEl.style.display = "flex"; conteudoEl.classList.add("conteudo-vida");
      scEl.innerHTML = D.vida_secoes.map((s, i) => `<div class="sc-item" data-i="${i}" data-atual="${i === idx}">
        <div class="sc-ring">${iniciais(s.nome)}</div><span class="lbl">${s.nome}</span></div>`).join("");
      scEl.querySelectorAll(".sc-item").forEach(el => el.addEventListener("click", (e) => { e.stopPropagation(); ir(Number(el.dataset.i)); }));
    }
    function atualizarBarras() {
      const bars = barrasEl.querySelectorAll(".pbar > i");
      bars.forEach((el, i) => {
        el.style.transition = "none";
        el.style.width = i < idx ? "100%" : i > idx ? "0%" : (ctx.reduzido ? "100%" : "0%");
      });
      if (!ctx.reduzido) {
        requestAnimationFrame(() => {
          const cur = bars[idx];
          if (cur) { cur.style.transition = "width 5000ms linear"; cur.style.width = "100%"; }
        });
      }
    }
    function desenharSlide() {
      const slides = slidesAtuais();
      if (barrasEl.childElementCount !== slides.length) montarBarras();
      idx = Math.max(0, Math.min(idx, slides.length - 1));
      const s = slides[idx];
      const titEl = wrap.querySelector("#tit-atual");
      if (titEl) titEl.textContent = (idx + 1) + " / " + slides.length + " · " + s.tit;
      conteudoEl.innerHTML = "";
      const div = document.createElement("div");
      conteudoEl.appendChild(div);
      div.innerHTML = s.html(div);
      wrap.querySelectorAll("[data-ir]").forEach(b => b.addEventListener("click", (e) => { e.stopPropagation(); ctx.irPara(b.dataset.ir); }));
      wrap.querySelectorAll("[data-stop]").forEach(b => b.addEventListener("click", (e) => e.stopPropagation()));
      montarCirculos();
      atualizarBarras();
      if (timeoutId) clearTimeout(timeoutId);
      if (!ctx.reduzido) {
        timeoutId = setTimeout(() => { avancar(1); }, 5000);
      }
    }
    function ir(novo) { idx = novo; desenharSlide(); }
    function avancar(delta) {
      const n = slidesAtuais().length;
      let novo = idx + delta;
      if (novo < 0) novo = 0;
      if (novo >= n) novo = n - 1;
      idx = novo;
      desenharSlide();
    }
    telaselEl.querySelectorAll("button").forEach(b => b.addEventListener("click", (e) => { e.stopPropagation(); ctx.irPara(b.dataset.t); }));

    desenharSlide();

    return () => { if (timeoutId) clearTimeout(timeoutId); };
  }
};
