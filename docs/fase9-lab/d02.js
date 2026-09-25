(window.DIRECOES = window.DIRECOES || {})[2] = {
  nome: "Tático",
  ideia: "Cantoneiras marcam cada bloco, barra de orçamento segmentada e faixa de alerta listrada no topo, tudo em códigos curtos.",
  acento: "#FF3B3B",
  fontes: ["Chakra+Petch:wght@400;500;600", "JetBrains+Mono:wght@400;500"],
  render(root, D, ctx) {
    const A = "#FF3B3B";
    const fmtR = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
    const fmtN = new Intl.NumberFormat("pt-BR");

    const style = document.createElement("style");
    style.textContent = `
      :host, * { box-sizing: border-box; }
      .wrap {
        font-family: "Chakra Petch", sans-serif;
        color: #d8d8d8;
        padding-bottom: 78px;
        --linha: #3a3a3a;
        --fraco: #8a8a8a;
      }
      .mono { font-family: "JetBrains Mono", monospace; }
      .tabnums { font-variant-numeric: tabular-nums; }

      .alerta-faixa {
        background: repeating-linear-gradient(135deg, ${A} 0 6px, #1a0808 6px 16px);
        color: #fff;
        padding: 8px 12px;
        font-size: 11px;
        letter-spacing: .08em;
        text-transform: uppercase;
        display: flex;
        align-items: center;
        gap: 8px;
        font-family: "JetBrains Mono", monospace;
        font-weight: 500;
      }
      .alerta-faixa .caixa { background: #000; padding: 2px 6px; border: 1px solid #fff; }

      .topo {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        padding: 12px 14px 6px;
      }
      .topo .hora { font-size: 30px; font-weight: 600; font-family: "JetBrains Mono", monospace; letter-spacing: -.02em; }
      .topo .data { font-size: 11px; color: var(--fraco); letter-spacing: .08em; text-transform: uppercase; margin-top: 2px; }
      .topo .clima { text-align: right; font-size: 11px; color: var(--fraco); }
      .topo .clima b { color: #d8d8d8; font-size: 16px; display: block; font-family: "JetBrains Mono", monospace; }

      .mic {
        min-width: 44px; min-height: 44px;
        border: 1px solid var(--linha);
        background: transparent;
        color: ${A};
        display: flex; align-items: center; justify-content: center;
        margin: 4px 14px 10px;
        position: relative;
      }
      .mic:before, .mic:after { content: ""; position: absolute; width: 8px; height: 8px; border-color: ${A}; }
      .mic:before { top: -1px; left: -1px; border-top: 1.5px solid; border-left: 1.5px solid; }
      .mic:after { bottom: -1px; right: -1px; border-bottom: 1.5px solid; border-right: 1.5px solid; }

      .bloco {
        position: relative;
        margin: 14px 14px 0;
        padding: 12px;
        border: 1px solid var(--linha);
      }
      .bloco .ang { position: absolute; width: 9px; height: 9px; border-color: ${A}; }
      .bloco .ang.tl { top: -1px; left: -1px; border-top: 1.5px solid; border-left: 1.5px solid; }
      .bloco .ang.tr { top: -1px; right: -1px; border-top: 1.5px solid; border-right: 1.5px solid; }
      .bloco .ang.bl { bottom: -1px; left: -1px; border-bottom: 1.5px solid; border-left: 1.5px solid; }
      .bloco .ang.br { bottom: -1px; right: -1px; border-bottom: 1.5px solid; border-right: 1.5px solid; }

      .rotulo {
        font-family: "JetBrains Mono", monospace;
        font-size: 10px;
        letter-spacing: .1em;
        color: var(--fraco);
        text-transform: uppercase;
        margin-bottom: 8px;
        display: flex;
        justify-content: space-between;
      }
      .rotulo .cod { color: ${A}; }

      .gasto-grande { font-size: 26px; font-weight: 600; font-family: "JetBrains Mono", monospace; }
      .gasto-sub { font-size: 11px; color: var(--fraco); margin-top: 2px; }

      .barra-seg {
        display: flex; gap: 2px; margin-top: 10px; height: 14px;
      }
      .barra-seg i {
        flex: 1; background: #1c1c1c; border: 1px solid var(--linha); display: block;
      }
      .barra-seg i.on { background: ${A}; border-color: ${A}; }
      .barra-seg i.ant { border-color: #6a6a6a; }

      .linha3 { display: flex; margin-top: 12px; border-top: 1px solid var(--linha); }
      .linha3 > div { flex: 1; padding: 8px 4px 0; text-align: center; border-left: 1px solid var(--linha); }
      .linha3 > div:first-child { border-left: none; }
      .linha3 .lbl { font-size: 9px; color: var(--fraco); text-transform: uppercase; letter-spacing: .08em; }
      .linha3 .val { font-family: "JetBrains Mono", monospace; font-size: 14px; margin-top: 3px; }

      .foco-linha { display: flex; align-items: center; gap: 8px; }
      .foco-linha .marca { width: 8px; height: 8px; border: 1.5px solid ${A}; flex: none; transform: rotate(45deg); }
      .foco-txt { font-size: 13px; }

      .atalhos { display: flex; gap: 8px; margin: 14px 14px 0; }
      .atalhos button {
        flex: 1; min-height: 44px; background: transparent; border: 1px solid var(--linha);
        color: #d8d8d8; font-family: "JetBrains Mono", monospace; font-size: 10px; letter-spacing: .06em;
        text-transform: uppercase; cursor: pointer;
      }
      .atalhos button:active { border-color: ${A}; color: ${A}; }

      .chat {
        margin: 14px 14px 0; display: flex; gap: 0; border: 1px solid var(--linha);
      }
      .chat input {
        flex: 1; background: transparent; border: 0; color: #d8d8d8; padding: 12px; font-family: "JetBrains Mono", monospace; font-size: 12px;
      }
      .chat input::placeholder { color: var(--fraco); }
      .chat .env { width: 44px; border-left: 1px solid var(--linha); color: ${A}; background: transparent; display: flex; align-items: center; justify-content: center; }

      /* categoria table */
      .cat-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-top: 1px solid #262626; }
      .cat-row:first-child { border-top: none; }
      .cat-nome { width: 92px; flex: none; font-size: 10px; text-transform: uppercase; letter-spacing: .04em; color: #c8c8c8; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .cat-barra { flex: 1; height: 10px; background: #1c1c1c; border: 1px solid var(--linha); position: relative; }
      .cat-barra i { position: absolute; left: 0; top: 0; bottom: 0; background: ${A}; }
      .cat-valor { width: 66px; flex: none; text-align: right; font-family: "JetBrains Mono", monospace; font-size: 11px; }

      .extrato-item { display: flex; justify-content: space-between; padding: 7px 0; border-top: 1px solid #262626; font-size: 12px; }
      .extrato-item:first-child { border-top: none; }
      .extrato-desc { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; padding-right: 8px; }
      .extrato-meta { color: var(--fraco); font-size: 10px; text-transform: uppercase; }
      .extrato-val { font-family: "JetBrains Mono", monospace; flex: none; }

      .mais-btn {
        width: 100%; min-height: 40px; background: transparent; border: 1px dashed var(--linha);
        color: ${A}; font-family: "JetBrains Mono", monospace; font-size: 10px; letter-spacing: .08em; text-transform: uppercase;
        margin-top: 10px; cursor: pointer;
      }

      .recolhivel-head {
        display: flex; justify-content: space-between; align-items: center; cursor: pointer; min-height: 44px;
      }
      .recolhivel-head .seta { color: ${A}; font-family: "JetBrains Mono", monospace; }
      .recolhivel-corpo { display: none; margin-top: 8px; }
      .recolhivel-corpo.aberto { display: block; }
      .sub-row { display: flex; justify-content: space-between; font-size: 11px; padding: 5px 0; border-top: 1px solid #262626; }
      .sub-row:first-child { border-top: none; }

      /* vida */
      .mod-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 14px 14px 0; }
      .mod {
        position: relative; border: 1px solid var(--linha); padding: 10px 6px; text-align: center; min-height: 66px;
        display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; cursor: pointer;
      }
      .mod .ang { position: absolute; width: 7px; height: 7px; border-color: ${A}; opacity: .8; }
      .mod .ang.tl { top: -1px; left: -1px; border-top: 1.5px solid; border-left: 1.5px solid; }
      .mod .ang.br { bottom: -1px; right: -1px; border-bottom: 1.5px solid; border-right: 1.5px solid; }
      .mod span { font-size: 9px; text-transform: uppercase; letter-spacing: .04em; color: #c8c8c8; }
      .mod.sel { border-color: ${A}; }
      .mod svg { stroke: ${A}; }

      .navb {
        position: fixed; left: 0; right: 0; bottom: 0; display: flex; background: #000;
        border-top: 1px solid var(--linha);
      }
      .navb button {
        flex: 1; min-height: 50px; background: transparent; border: 0; color: var(--fraco);
        font-family: "JetBrains Mono", monospace; font-size: 9px; text-transform: uppercase; letter-spacing: .06em;
      }
      .navb button.on { color: ${A}; border-top: 1.5px solid ${A}; margin-top: -1.5px; }
    `;

    const svgMic = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><line x1="12" y1="18" x2="12" y2="22"/></svg>`;
    const iconFor = (id) => {
      const s = 'width="16" height="16" viewBox="0 0 24 24" fill="none" stroke-width="1.5"';
      const m = {
        habitos: `<path d="M4 12l5 5L20 6"/>`,
        projetos: `<rect x="3" y="4" width="18" height="16"/><line x1="3" y1="9" x2="21" y2="9"/>`,
        agenda: `<rect x="3" y="5" width="18" height="15"/><line x1="3" y1="10" x2="21" y2="10"/><line x1="7" y1="3" x2="7" y2="7"/><line x1="17" y1="3" x2="17" y2="7"/>`,
        compras: `<circle cx="9" cy="20" r="1.4"/><circle cx="17" cy="20" r="1.4"/><path d="M3 4h2l2.4 11h10.2L20 8H6.2"/>`,
        pessoas: `<circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><circle cx="17" cy="9" r="2.4"/><path d="M15.5 14a5 5 0 0 1 5.5 5"/>`,
        treino: `<path d="M4 12h2M18 12h2M6 8v8M18 8v8M6 12h12"/>`,
        contas: `<rect x="4" y="9" width="16" height="11"/><path d="M8 9V6a4 4 0 0 1 8 0v3"/>`,
        manutencao: `<path d="M14 3l-3 3 1 1 3-3 1 1-8 8-1-1 8-8zM7 13l-4 4 4 4 4-4"/>`,
        garantia: `<path d="M12 3l7 3v6c0 5-3.5 7.5-7 9-3.5-1.5-7-4-7-9V6z"/>`,
        viagens: `<path d="M3 12l18-7-7 18-3-8-8-3z"/>`,
        lugares: `<path d="M12 21s-7-6-7-11a7 7 0 0 1 14 0c0 5-7 11-7 11z"/><circle cx="12" cy="10" r="2.2"/>`,
        presentes: `<rect x="3" y="9" width="18" height="12"/><path d="M3 9V6h18v3M12 6v15M8 6a2.5 2.5 0 0 1 0-5c2 0 4 5 4 5M16 6a2.5 2.5 0 0 0 0-5c-2 0-4 5-4 5"/>`,
        aprender: `<path d="M2 6l10-4 10 4-10 4-10-4zM6 10v6c2 2 10 2 12 0v-6"/>`,
        salvos: `<path d="M6 3h12v18l-6-4-6 4z"/>`,
        mensagem: `<rect x="3" y="5" width="18" height="12"/><path d="M3 5l9 7 9-7"/>`,
        vale_a_pena: `<path d="M4 20V10M12 20V4M20 20v-7"/>`,
        progresso: `<circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/>`,
        revisao: `<rect x="4" y="4" width="16" height="16"/><path d="M8 10l2 2 4-4"/><line x1="8" y1="16" x2="16" y2="16"/>`
      };
      return `<svg ${s}>${m[id] || `<circle cx="12" cy="12" r="8"/>`}</svg>`;
    };

    const navHtml = `
      <div class="navb">
        <button data-t="hoje">Hoje</button>
        <button data-t="financas">Fin-01</button>
        <button data-t="vida">Vida</button>
      </div>`;

    let cleanupFns = [];
    const wrap = document.createElement("div");
    wrap.className = "wrap";
    root.append(style, wrap);

    function montarNav(telaAtual) {
      const nav = wrap.querySelector(".navb");
      if (!nav) return;
      nav.querySelectorAll("button").forEach(b => {
        b.classList.toggle("on", b.dataset.t === telaAtual);
        b.onclick = () => ctx.irPara(b.dataset.t);
      });
    }

    if (ctx.tela === "hoje") {
      const F = D.financas, dias = F.por_dia_mes;
      const max = Math.max(...dias.map(d => d.acumulado), 1);
      const w = 300, h = 46;
      const pts = dias.map((d, i) => `${(i / (dias.length - 1)) * w},${h - (d.acumulado / max) * h}`).join(" ");
      wrap.innerHTML = `
        <div class="alerta-faixa"><div class="caixa">ALERTA</div><div>${D.aviso_critico}</div></div>
        <div class="topo">
          <div>
            <div class="hora tabnums" id="hora">--:--:--</div>
            <div class="data">${new Date(D.hoje.data + "T00:00:00").toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "long" })}</div>
          </div>
          <div class="clima">
            <b class="tabnums">${D.hoje.clima.temp}°</b>
            ${D.hoje.clima.cond}<br>chuva ${D.hoje.clima.chuva_prob}%
          </div>
        </div>
        <button class="mic" aria-label="comando de voz">${svgMic}</button>

        <div class="bloco">
          <i class="ang tl"></i><i class="ang tr"></i><i class="ang bl"></i><i class="ang br"></i>
          <div class="rotulo"><span>Gasto do mês</span><span class="cod">FIN-01</span></div>
          <div class="gasto-grande tabnums">${fmtR.format(F.gasto_mes)}</div>
          <div class="gasto-sub">de ${fmtR.format(F.orcamento_mes)} orçado</div>
          <svg width="100%" height="46" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="margin-top:8px;display:block">
            <polyline points="${pts}" fill="none" stroke="${A}" stroke-width="1.5"/>
          </svg>
          <div class="linha3">
            <div><div class="lbl">Hoje</div><div class="val tabnums">${fmtR.format(F.gasto_hoje)}</div></div>
            <div><div class="lbl">Fatura</div><div class="val tabnums">${fmtR.format(F.fatura_atual)}</div></div>
            <div><div class="lbl">Conta</div><div class="val tabnums">${fmtR.format(F.saldo_conta)}</div></div>
          </div>
        </div>

        <div class="bloco">
          <i class="ang tl"></i><i class="ang tr"></i><i class="ang bl"></i><i class="ang br"></i>
          <div class="rotulo"><span>Em foco agora</span><span class="cod">TSK-01</span></div>
          <div class="foco-linha"><div class="marca"></div><div class="foco-txt">${D.tarefas.em_foco}</div></div>
        </div>

        <div class="atalhos">
          <button data-t="financas">Finanças</button>
          <button data-t="vida">Vida</button>
        </div>
        <div class="atalhos">
          <button data-t="vida">Tarefas</button>
          <button data-t="vida">Aviação</button>
        </div>

        <div class="chat">
          <input type="text" placeholder="MSG > digitar comando..." />
          <div class="env">></div>
        </div>
        ${navHtml}
      `;
      wrap.querySelectorAll(".atalhos button").forEach(b => b.onclick = () => ctx.irPara(b.dataset.t));
      montarNav("hoje");

      const horaEl = wrap.querySelector("#hora");
      const tick = () => { horaEl.textContent = new Date().toLocaleTimeString("pt-BR"); };
      tick();
      if (!ctx.reduzido) {
        const iv = setInterval(tick, 1000);
        cleanupFns.push(() => clearInterval(iv));
      }
    }

    else if (ctx.tela === "financas") {
      const F = D.financas;
      const diff = F.gasto_mes - F.gasto_mes_anterior;
      const pctOrc = Math.min(1, F.gasto_mes / F.orcamento_mes);
      const segTotal = 20;
      const segOn = Math.round(pctOrc * segTotal);
      const pctAnt = Math.min(1, F.gasto_mes_anterior / F.orcamento_mes);
      const segAnt = Math.round(pctAnt * segTotal);
      const maxCat = Math.max(...F.por_categoria.map(c => c.valor), 1);

      const visiveis = F.ultimos_15_dias.slice(0, 6);
      const resto = F.ultimos_15_dias.slice(6);

      wrap.innerHTML = `
        <div class="alerta-faixa"><div class="caixa">ALERTA</div><div>${D.aviso_critico}</div></div>
        <div class="bloco" style="margin-top:14px">
          <i class="ang tl"></i><i class="ang tr"></i><i class="ang bl"></i><i class="ang br"></i>
          <div class="rotulo"><span>Orçamento do mês</span><span class="cod">FIN-01</span></div>
          <div class="gasto-grande tabnums">${fmtR.format(F.gasto_mes)}</div>
          <div class="gasto-sub">${diff <= 0 ? "▼" : "▲"} ${fmtR.format(Math.abs(diff))} vs mês anterior · orçamento ${fmtR.format(F.orcamento_mes)}</div>
          <div class="barra-seg">
            ${Array.from({ length: segTotal }, (_, i) => `<i class="${i < segOn ? "on" : ""} ${i === segAnt - 1 ? "ant" : ""}"></i>`).join("")}
          </div>
          <div class="linha3">
            <div><div class="lbl">Fatura</div><div class="val tabnums">${fmtR.format(F.fatura_atual)}</div></div>
            <div><div class="lbl">Vence</div><div class="val">${F.fatura_vencimento.slice(8, 10)}/${F.fatura_vencimento.slice(5, 7)}</div></div>
            <div><div class="lbl">Conta</div><div class="val tabnums">${fmtR.format(F.saldo_conta)}</div></div>
          </div>
        </div>

        <div class="bloco">
          <i class="ang tl"></i><i class="ang tr"></i><i class="ang bl"></i><i class="ang br"></i>
          <div class="rotulo"><span>Por categoria</span><span class="cod">FIN-02</span></div>
          ${F.por_categoria.map(c => `
            <div class="cat-row">
              <div class="cat-nome">${c.categoria}</div>
              <div class="cat-barra"><i style="width:${(c.valor / maxCat * 100).toFixed(1)}%"></i></div>
              <div class="cat-valor tabnums">${fmtR.format(c.valor)}</div>
            </div>`).join("")}
        </div>

        <div class="bloco">
          <i class="ang tl"></i><i class="ang tr"></i><i class="ang bl"></i><i class="ang br"></i>
          <div class="rotulo"><span>Últimos 15 dias</span><span class="cod">FIN-03</span></div>
          <div id="lista15">
            ${visiveis.map(it => linhaExtrato(it)).join("")}
          </div>
          ${resto.length ? `<button class="mais-btn" id="mais">Carregar mais (${resto.length})</button>` : ""}
        </div>

        <div class="bloco">
          <div class="recolhivel-head" id="head-assin">
            <div class="rotulo" style="margin-bottom:0"><span>Assinaturas</span><span class="cod">FIN-04</span></div>
            <span class="seta">+</span>
          </div>
          <div class="recolhivel-corpo" id="corpo-assin">
            ${F.assinaturas.map(a => `<div class="sub-row"><span>${a.nome}</span><span class="tabnums">${fmtR.format(a.valor)} · ${a.proxima.slice(8,10)}/${a.proxima.slice(5,7)}</span></div>`).join("")}
          </div>
        </div>
        ${navHtml}
      `;

      function linhaExtrato(it) {
        return `<div class="extrato-item">
          <div style="flex:1;min-width:0">
            <div class="extrato-desc">${it.descricao}</div>
            <div class="extrato-meta">${it.categoria} · ${it.data.slice(8,10)}/${it.data.slice(5,7)}</div>
          </div>
          <div class="extrato-val tabnums">${fmtR.format(it.valor)}</div>
        </div>`;
      }

      const btnMais = wrap.querySelector("#mais");
      if (btnMais) btnMais.onclick = () => {
        wrap.querySelector("#lista15").insertAdjacentHTML("beforeend", resto.map(linhaExtrato).join(""));
        btnMais.remove();
      };
      const headAssin = wrap.querySelector("#head-assin");
      headAssin.onclick = () => {
        const corpo = wrap.querySelector("#corpo-assin");
        const s = headAssin.querySelector(".seta");
        corpo.classList.toggle("aberto");
        s.textContent = corpo.classList.contains("aberto") ? "−" : "+";
      };
      montarNav("financas");
    }

    else if (ctx.tela === "vida") {
      let selId = null;
      wrap.innerHTML = `
        <div class="alerta-faixa"><div class="caixa">ALERTA</div><div>${D.aviso_critico}</div></div>
        <div class="rotulo" style="margin:14px 14px 0"><span>Módulos</span><span class="cod">VID-00</span></div>
        <div class="mod-grid">
          ${D.vida_secoes.map(s => `
            <div class="mod" data-id="${s.id}">
              <i class="ang tl"></i><i class="ang br"></i>
              ${iconFor(s.id)}
              <span>${s.nome}</span>
            </div>`).join("")}
        </div>
        <div class="bloco" id="conteudo" style="display:none">
          <i class="ang tl"></i><i class="ang tr"></i><i class="ang bl"></i><i class="ang br"></i>
          <div class="rotulo"><span id="conteudo-titulo"></span><span class="cod" id="conteudo-cod"></span></div>
          <div id="conteudo-corpo" style="font-size:12px;color:#c8c8c8;line-height:1.7"></div>
        </div>
        ${navHtml}
      `;
      const mods = wrap.querySelectorAll(".mod");
      const caixa = wrap.querySelector("#conteudo");
      mods.forEach(m => m.onclick = () => {
        const id = m.dataset.id;
        const s = D.vida_secoes.find(x => x.id === id);
        mods.forEach(x => x.classList.toggle("sel", x === m));
        caixa.style.display = "block";
        wrap.querySelector("#conteudo-titulo").textContent = s.nome;
        wrap.querySelector("#conteudo-cod").textContent = "VID-" + String(D.vida_secoes.indexOf(s) + 1).padStart(2, "0");
        let linhas = [s.resumo];
        if (s.id === "viagens" && D.viagem) {
          linhas = [
            `${D.viagem.origem} → ${D.viagem.destino}`,
            `Data: ${D.viagem.data.slice(8,10)}/${D.viagem.data.slice(5,7)}/${D.viagem.data.slice(0,4)}`,
            `Faltam ${D.viagem.dias_faltando} dias`
          ];
        } else {
          linhas.push("Status: em dia");
          linhas.push("Última atualização: hoje");
        }
        wrap.querySelector("#conteudo-corpo").innerHTML = linhas.map(l => `<div>${l}</div>`).join("");
      });
      montarNav("vida");
    }

    return () => { cleanupFns.forEach(f => f()); };
  }
};
