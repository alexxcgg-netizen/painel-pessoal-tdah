(window.DIRECOES = window.DIRECOES || {})[9] = {
  nome: "Cockpit",
  ideia: "Fitas verticais de PFD (velocidade de gasto / altitude de saldo) com bugs magenta, horizonte central e alertas estilo EICAS.",
  acento: "#FF3DCB",
  fontes: ["B612:wght@400;700", "B612+Mono:wght@400;700"],
  render(root, D, ctx) {
    const A = "#FF3DCB";
    const AMBAR = "#E8A33D";
    const fmtR = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

    const style = document.createElement("style");
    style.textContent = `
      :host, * { box-sizing: border-box; }
      .wrap {
        font-family: "B612", sans-serif;
        color: #cfd3d6;
        padding-bottom: 78px;
        --linha: #3a3a3a;
        --fraco: #8a8a8a;
      }
      .mono { font-family: "B612 Mono", monospace; }
      .tabnums { font-variant-numeric: tabular-nums; }

      .eicas {
        background: #1c1204;
        border-top: 1px solid ${AMBAR};
        border-bottom: 1px solid ${AMBAR};
        color: ${AMBAR};
        padding: 7px 12px;
        font-family: "B612 Mono", monospace;
        font-size: 11px;
        letter-spacing: .03em;
        display: flex;
        gap: 8px;
        align-items: center;
      }
      .eicas .tag { border: 1px solid ${AMBAR}; padding: 1px 5px; font-size: 9px; }

      .cabecalho {
        display: flex; justify-content: space-between; align-items: center;
        padding: 10px 14px 0;
        font-family: "B612 Mono", monospace;
        font-size: 10px; color: var(--fraco); letter-spacing: .08em; text-transform: uppercase;
      }
      .cabecalho b { color: #cfd3d6; }

      .mic {
        position: absolute; right: 14px; top: 46px;
        min-width: 44px; min-height: 44px;
        border: 1px solid var(--linha); border-radius: 50%;
        background: transparent; color: ${A};
        display: flex; align-items: center; justify-content: center;
      }

      .pfd {
        position: relative;
        display: flex;
        margin: 10px 14px 0;
        height: 280px;
        border: 1px solid var(--linha);
      }
      .fita {
        width: 78px; flex: none; position: relative; overflow: hidden;
        border-right: 1px solid var(--linha);
      }
      .fita.direita { border-right: none; border-left: 1px solid var(--linha); }
      .fita-titulo {
        position: absolute; top: 4px; left: 0; right: 0; text-align: center;
        font-family: "B612 Mono", monospace; font-size: 8px; color: var(--fraco);
        letter-spacing: .06em; text-transform: uppercase; z-index: 2;
      }
      .fita-track { position: absolute; inset: 0; }
      .fita-marca {
        position: absolute; left: 0; right: 0; display: flex; align-items: center; justify-content: center;
        font-family: "B612 Mono", monospace; font-size: 10px; color: var(--fraco); height: 1px;
      }
      .fita-marca:before, .fita-marca:after { content:""; position:absolute; top:0; width:6px; height:1px; background: var(--linha); }
      .fita-marca:before { left: 0; }
      .fita-marca:after { right: 0; }

      .fita-central {
        position: absolute; left: 0; right: 0; top: 50%; transform: translateY(-50%);
        background: #000; border-top: 1px solid #fff; border-bottom: 1px solid #fff;
        padding: 3px 0; text-align: center; z-index: 3;
      }
      .fita-central b { font-family: "B612 Mono", monospace; font-size: 15px; color: #fff; }

      .bug {
        position: absolute; left: 0; right: 0; height: 1px; background: ${A}; z-index: 2;
      }
      .bug:after {
        content: attr(data-lbl);
        position: absolute; right: 2px; top: -7px; font-family: "B612 Mono", monospace;
        font-size: 8px; color: ${A}; background: #000; padding: 0 2px;
      }
      .fita.esquerda .bug:after { right: auto; left: 2px; }

      .horizonte {
        flex: 1; position: relative;
        display: flex; flex-direction: column; align-items: center; justify-content: center;
      }
      .horizonte svg { display: block; }
      .horizonte .hora {
        margin-top: 10px; font-family: "B612 Mono", monospace; font-size: 22px; color: #fff;
      }
      .horizonte .data {
        font-family: "B612 Mono", monospace; font-size: 9px; color: var(--fraco); letter-spacing: .08em; text-transform: uppercase; margin-top: 2px;
      }
      .horizonte .clima {
        font-family: "B612 Mono", monospace; font-size: 9px; color: var(--fraco); margin-top: 6px; text-align: center;
      }

      .foco-box {
        margin: 10px 14px 0; padding: 10px 12px; border: 1px solid var(--linha);
        display: flex; align-items: center; gap: 8px;
      }
      .foco-box .diamante { width: 8px; height: 8px; border: 1.5px solid ${A}; transform: rotate(45deg); flex: none; }
      .foco-box .txt { font-size: 12px; flex: 1; }
      .foco-box .lbl { font-family: "B612 Mono", monospace; font-size: 9px; color: var(--fraco); text-transform: uppercase; margin-right: 6px; }

      .lsk-row { display: flex; gap: 8px; margin: 10px 14px 0; }
      .lsk-row button {
        flex: 1; min-height: 44px; background: transparent; border: 1px solid var(--linha); color: #cfd3d6;
        font-family: "B612 Mono", monospace; font-size: 10px; text-transform: uppercase; letter-spacing: .04em;
      }
      .lsk-row button:active { border-color: ${A}; color: ${A}; }

      .scratchpad {
        margin: 10px 14px 0; display: flex; border: 1px solid var(--linha); align-items: center;
      }
      .scratchpad span { padding: 0 8px; color: ${A}; font-family: "B612 Mono", monospace; }
      .scratchpad input {
        flex: 1; background: transparent; border: 0; color: #cfd3d6; padding: 12px 0; font-family: "B612 Mono", monospace; font-size: 12px;
      }
      .scratchpad input::placeholder { color: var(--fraco); }

      /* financas FMS style */
      .fms-page { margin: 10px 14px 0; border: 1px solid var(--linha); padding: 10px 12px; }
      .fms-titulo {
        font-family: "B612 Mono", monospace; font-size: 10px; color: ${A}; letter-spacing: .1em;
        text-transform: uppercase; text-align: center; margin-bottom: 8px; border-bottom: 1px solid var(--linha); padding-bottom: 6px;
      }
      .fms-row {
        display: flex; justify-content: space-between; padding: 6px 0; font-family: "B612 Mono", monospace; font-size: 12px;
        border-top: 1px solid #262626;
      }
      .fms-row:first-child { border-top: none; }
      .fms-row .k { color: var(--fraco); }
      .fms-row .v { color: #cfd3d6; }
      .fms-row .v.mag { color: ${A}; }

      .fms-list-item {
        display: flex; align-items: baseline; padding: 6px 0; border-top: 1px solid #262626; font-size: 11px;
      }
      .fms-list-item:first-child { border-top: none; }
      .prompt { color: ${A}; font-family: "B612 Mono", monospace; margin-right: 6px; }
      .prompt.right { margin-left: auto; margin-right: 0; }
      .fms-list-item .d { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .fms-list-item .m { color: var(--fraco); font-family: "B612 Mono", monospace; font-size: 9px; margin-left: 6px; }
      .fms-list-item .val { font-family: "B612 Mono", monospace; margin-left: 8px; }

      .cat-bar-row { display: flex; align-items: center; gap: 6px; padding: 5px 0; font-family: "B612 Mono", monospace; font-size: 10px; }
      .cat-bar-nome { width: 88px; flex: none; text-transform: uppercase; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--fraco); }
      .cat-bar-track { flex: 1; height: 8px; background: #1c1c1c; position: relative; }
      .cat-bar-track i { position: absolute; left: 0; top: 0; bottom: 0; background: ${A}; }
      .cat-bar-val { width: 60px; text-align: right; flex: none; }

      .fms-more { width: 100%; min-height: 40px; background: transparent; border: 1px dashed var(--linha); color: ${A}; font-family: "B612 Mono", monospace; font-size: 10px; text-transform: uppercase; margin-top: 8px; }

      .cdu-head { display: flex; justify-content: space-between; align-items: center; min-height: 44px; cursor: pointer; }
      .cdu-head .plus { color: ${A}; font-family: "B612 Mono", monospace; }
      .cdu-body { display: none; }
      .cdu-body.on { display: block; }

      /* vida MCDU */
      .mcdu {
        margin: 10px 14px 0; border: 1px solid var(--linha); min-height: 380px; display: flex;
      }
      .lsk-col { width: 34px; flex: none; display: flex; flex-direction: column; }
      .lsk-col button {
        flex: 1; background: transparent; border: 0; border-bottom: 1px solid #262626; color: ${A};
        font-family: "B612 Mono", monospace; font-size: 14px;
      }
      .lsk-col button:last-child { border-bottom: none; }
      .mcdu-mid { flex: 1; padding: 10px; }
      .mcdu-titulo {
        text-align: center; font-family: "B612 Mono", monospace; font-size: 10px; color: ${A};
        letter-spacing: .1em; text-transform: uppercase; margin-bottom: 10px;
      }
      .mcdu-linha { display: flex; align-items: center; gap: 6px; font-size: 10px; color: var(--fraco); font-family: "B612 Mono", monospace; padding: 4px 0; text-transform: uppercase; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
      .mcdu-cols { display: flex; gap: 6px; }
      .mcdu-cols > div { flex: 1; min-width: 0; }
      .mcdu-cols .mcdu-linha.dir { justify-content: flex-end; text-align: right; }
      .mcdu-corpo { font-family: "B612 Mono", monospace; font-size: 11px; color: #cfd3d6; line-height: 1.8; margin-top: 8px; }
      .mcdu-placeholder { text-align: center; color: var(--fraco); font-family: "B612 Mono", monospace; font-size: 10px; margin-top: 140px; letter-spacing: .08em; }

      .navb {
        position: fixed; left: 0; right: 0; bottom: 0; display: flex; background: #000;
        border-top: 1px solid var(--linha);
      }
      .navb button {
        flex: 1; min-height: 50px; background: transparent; border: 0; color: var(--fraco);
        font-family: "B612 Mono", monospace; font-size: 9px; text-transform: uppercase; letter-spacing: .06em;
      }
      .navb button.on { color: ${A}; border-top: 1.5px solid ${A}; margin-top: -1.5px; }
    `;

    const svgMic = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><line x1="12" y1="18" x2="12" y2="22"/></svg>`;
    const iconFor = (id) => {
      const s = 'width="14" height="14" viewBox="0 0 24 24" fill="none" stroke-width="1.5"';
      const m = {
        habitos: `<path d="M4 12l5 5L20 6"/>`, projetos: `<rect x="3" y="4" width="18" height="16"/><line x1="3" y1="9" x2="21" y2="9"/>`,
        agenda: `<rect x="3" y="5" width="18" height="15"/><line x1="3" y1="10" x2="21" y2="10"/>`,
        compras: `<circle cx="9" cy="20" r="1.4"/><circle cx="17" cy="20" r="1.4"/><path d="M3 4h2l2.4 11h10.2L20 8H6.2"/>`,
        pessoas: `<circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/>`,
        treino: `<path d="M4 12h2M18 12h2M6 8v8M18 8v8M6 12h12"/>`,
        contas: `<rect x="4" y="9" width="16" height="11"/><path d="M8 9V6a4 4 0 0 1 8 0v3"/>`,
        manutencao: `<path d="M14 3l-3 3 1 1 3-3 1 1-8 8-1-1 8-8zM7 13l-4 4 4 4 4-4"/>`,
        garantia: `<path d="M12 3l7 3v6c0 5-3.5 7.5-7 9-3.5-1.5-7-4-7-9V6z"/>`,
        viagens: `<path d="M3 12l18-7-7 18-3-8-8-3z"/>`,
        lugares: `<path d="M12 21s-7-6-7-11a7 7 0 0 1 14 0c0 5-7 11-7 11z"/>`,
        presentes: `<rect x="3" y="9" width="18" height="12"/><path d="M3 9V6h18v3M12 6v15"/>`,
        aprender: `<path d="M2 6l10-4 10 4-10 4-10-4zM6 10v6c2 2 10 2 12 0v-6"/>`,
        salvos: `<path d="M6 3h12v18l-6-4-6 4z"/>`,
        mensagem: `<rect x="3" y="5" width="18" height="12"/><path d="M3 5l9 7 9-7"/>`,
        vale_a_pena: `<path d="M4 20V10M12 20V4M20 20v-7"/>`,
        progresso: `<circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/>`,
        revisao: `<rect x="4" y="4" width="16" height="16"/><path d="M8 10l2 2 4-4"/>`
      };
      return `<svg ${s}>${m[id] || `<circle cx="12" cy="12" r="8"/>`}</svg>`;
    };

    const navHtml = `
      <div class="navb">
        <button data-t="hoje">Hoje</button>
        <button data-t="financas">Fin</button>
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

    // builds a vertical tape: value scaled to range, with a magenta "bug" marking bugValue
    function fita(valor, bugValor, unidade, min, max, lado) {
      const H = 280;
      const clamp = v => Math.max(min, Math.min(max, v));
      const yFor = v => H - ((clamp(v) - min) / (max - min)) * H;
      const passos = 6;
      let marcasHtml = "";
      for (let i = 0; i <= passos; i++) {
        const v = min + (i / passos) * (max - min);
        const y = yFor(v);
        marcasHtml += `<div class="fita-marca" style="top:${y}px">${Math.round(v)}</div>`;
      }
      const bugY = yFor(bugValor);
      return `
        <div class="fita ${lado}">
          <div class="fita-titulo">${unidade}</div>
          <div class="fita-track">${marcasHtml}</div>
          <div class="bug" style="top:${bugY}px" data-lbl="${Math.round(bugValor)}"></div>
          <div class="fita-central"><b class="tabnums">${Math.round(valor)}</b></div>
        </div>`;
    }

    if (ctx.tela === "hoje") {
      const F = D.financas;
      const maxGasto = Math.max(F.orcamento_mes, F.gasto_mes, F.gasto_mes_anterior) * 1.1;
      const maxAlt = Math.max(F.fatura_atual, F.saldo_conta * 20, 3000) * 1.1;

      wrap.innerHTML = `
        <div class="eicas"><span class="tag">ALERTA</span><span>${D.aviso_critico}</span></div>
        <div class="cabecalho">
          <span>${D.hoje.cidade}</span>
          <b>${new Date(D.hoje.data + "T00:00:00").toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "short" }).toUpperCase()}</b>
        </div>
        <button class="mic" aria-label="comando de voz">${svgMic}</button>
        <div class="pfd">
          ${fita(F.gasto_mes, F.gasto_mes_anterior, "GASTO R$", 0, maxGasto, "esquerda")}
          <div class="horizonte">
            <svg width="120" height="70" viewBox="0 0 120 70">
              <line x1="10" y1="35" x2="45" y2="35" stroke="#cfd3d6" stroke-width="1.5"/>
              <line x1="75" y1="35" x2="110" y2="35" stroke="#cfd3d6" stroke-width="1.5"/>
              <polygon points="60,28 66,38 54,38" fill="${A}"/>
              <circle cx="60" cy="35" r="30" fill="none" stroke="#3a3a3a" stroke-width="1"/>
            </svg>
            <div class="hora tabnums" id="hora">--:--:--</div>
            <div class="data">${D.hoje.data.slice(8,10)}/${D.hoje.data.slice(5,7)}/${D.hoje.data.slice(0,4)}</div>
            <div class="clima">${D.hoje.clima.temp}° · ${D.hoje.clima.cond} · CHUVA ${D.hoje.clima.chuva_prob}%</div>
          </div>
          ${fita(F.saldo_conta, F.fatura_atual, "SALDO R$", 0, maxAlt, "direita")}
        </div>

        <div class="foco-box">
          <div class="diamante"></div>
          <div class="txt"><span class="lbl">FOCO</span>${D.tarefas.em_foco}</div>
        </div>

        <div class="lsk-row">
          <button data-t="financas">◂ FIN</button>
          <button data-t="vida">VIDA ▸</button>
        </div>
        <div class="lsk-row">
          <button data-t="vida">◂ TAREFAS</button>
          <button data-t="vida">AVIAÇÃO ▸</button>
        </div>

        <div class="scratchpad">
          <span>></span>
          <input type="text" placeholder="scratchpad / comando..." />
        </div>
        ${navHtml}
      `;
      wrap.querySelectorAll(".lsk-row button").forEach(b => b.onclick = () => ctx.irPara(b.dataset.t));
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
      const maxCat = Math.max(...F.por_categoria.map(c => c.valor), 1);
      const visiveis = F.ultimos_15_dias.slice(0, 6);
      const resto = F.ultimos_15_dias.slice(6);

      const linhaExtrato = it => `
        <div class="fms-list-item">
          <span class="prompt">&lt;</span>
          <div class="d">${it.descricao}</div>
          <span class="m">${it.data.slice(8,10)}/${it.data.slice(5,7)}</span>
          <span class="val tabnums">${fmtR.format(it.valor)}</span>
        </div>`;

      wrap.innerHTML = `
        <div class="eicas"><span class="tag">ALERTA</span><span>${D.aviso_critico}</span></div>
        <div class="fms-page">
          <div class="fms-titulo">RESUMO DO MÊS</div>
          <div class="fms-row"><span class="k">GASTO</span><span class="v mag tabnums">${fmtR.format(F.gasto_mes)}</span></div>
          <div class="fms-row"><span class="k">MÊS ANT.</span><span class="v tabnums">${fmtR.format(F.gasto_mes_anterior)}</span></div>
          <div class="fms-row"><span class="k">VARIAÇÃO</span><span class="v tabnums">${diff <= 0 ? "↓" : "↑"} ${fmtR.format(Math.abs(diff))}</span></div>
          <div class="fms-row"><span class="k">ORÇAMENTO</span><span class="v tabnums">${fmtR.format(F.orcamento_mes)}</span></div>
          <div class="fms-row"><span class="k">FATURA</span><span class="v tabnums">${fmtR.format(F.fatura_atual)}</span></div>
          <div class="fms-row"><span class="k">CONTA</span><span class="v tabnums">${fmtR.format(F.saldo_conta)}</span></div>
        </div>

        <div class="fms-page">
          <div class="fms-titulo">POR CATEGORIA</div>
          ${F.por_categoria.map(c => `
            <div class="cat-bar-row">
              <div class="cat-bar-nome">${c.categoria}</div>
              <div class="cat-bar-track"><i style="width:${(c.valor / maxCat * 100).toFixed(1)}%"></i></div>
              <div class="cat-bar-val tabnums">${fmtR.format(c.valor)}</div>
            </div>`).join("")}
        </div>

        <div class="fms-page">
          <div class="fms-titulo">ÚLTIMOS 15 DIAS</div>
          <div id="lista15">${visiveis.map(linhaExtrato).join("")}</div>
          ${resto.length ? `<button class="fms-more" id="mais">MAIS ▾ (${resto.length})</button>` : ""}
        </div>

        <div class="fms-page">
          <div class="cdu-head" id="head-assin">
            <div class="fms-titulo" style="margin-bottom:0">ASSINATURAS</div>
            <span class="plus" id="plus-assin">+</span>
          </div>
          <div class="cdu-body" id="corpo-assin">
            ${F.assinaturas.map(a => `<div class="fms-row"><span class="k">${a.nome}</span><span class="v tabnums">${fmtR.format(a.valor)} · ${a.proxima.slice(8,10)}/${a.proxima.slice(5,7)}</span></div>`).join("")}
          </div>
        </div>
        ${navHtml}
      `;

      const btnMais = wrap.querySelector("#mais");
      if (btnMais) btnMais.onclick = () => {
        wrap.querySelector("#lista15").insertAdjacentHTML("beforeend", resto.map(linhaExtrato).join(""));
        btnMais.remove();
      };
      const headAssin = wrap.querySelector("#head-assin");
      headAssin.onclick = () => {
        const corpo = wrap.querySelector("#corpo-assin");
        corpo.classList.toggle("on");
        wrap.querySelector("#plus-assin").textContent = corpo.classList.contains("on") ? "−" : "+";
      };
      montarNav("financas");
    }

    else if (ctx.tela === "vida") {
      const secoes = D.vida_secoes;
      const metade = Math.ceil(secoes.length / 2);
      const esquerda = secoes.slice(0, metade);
      const direita = secoes.slice(metade);

      wrap.innerHTML = `
        <div class="eicas"><span class="tag">ALERTA</span><span>${D.aviso_critico}</span></div>
        <div class="mcdu">
          <div class="lsk-col" id="col-esq">
            ${esquerda.map((s, i) => `<button data-id="${s.id}">${i + 1}◂</button>`).join("")}
          </div>
          <div class="mcdu-mid">
            <div class="mcdu-titulo">SELECIONE UMA PÁGINA</div>
            <div id="lista-nomes" class="mcdu-cols">
              <div>${esquerda.map((s, i) => `<div class="mcdu-linha">${i + 1} ${s.nome}</div>`).join("")}</div>
              <div>${direita.map((s, i) => `<div class="mcdu-linha dir">${s.nome} ${i + 1}</div>`).join("")}</div>
            </div>
            <div id="conteudo"></div>
          </div>
          <div class="lsk-col" id="col-dir">
            ${direita.map((s, i) => `<button data-id="${s.id}">▸${i + 1}</button>`).join("")}
          </div>
        </div>
        ${navHtml}
      `;

      const conteudo = wrap.querySelector("#conteudo");
      const listaNomes = wrap.querySelector("#lista-nomes");
      function abrir(id) {
        const s = secoes.find(x => x.id === id);
        listaNomes.style.display = "none";
        let linhas = [s.resumo];
        if (s.id === "viagens" && D.viagem) {
          linhas = [
            `${D.viagem.origem} → ${D.viagem.destino}`,
            `DATA ${D.viagem.data.slice(8,10)}/${D.viagem.data.slice(5,7)}/${D.viagem.data.slice(0,4)}`,
            `FALTAM ${D.viagem.dias_faltando} DIAS`
          ];
        } else {
          linhas.push("STATUS: EM DIA");
          linhas.push("ATUALIZADO: HOJE");
        }
        conteudo.innerHTML = `
          <div class="mcdu-titulo" style="margin-top:14px">${s.nome.toUpperCase()}</div>
          <div class="mcdu-corpo">${linhas.map(l => `<div>${iconFor(s.id)} <span style="vertical-align:middle;margin-left:4px">${l}</span></div>`).join("")}</div>
        `;
      }
      wrap.querySelectorAll(".lsk-col button").forEach(b => b.onclick = () => {
        wrap.querySelectorAll(".lsk-col button").forEach(x => x.style.color = "");
        b.style.color = A;
        abrir(b.dataset.id);
      });
      montarNav("vida");
    }

    return () => { cleanupFns.forEach(f => f()); };
  }
};
