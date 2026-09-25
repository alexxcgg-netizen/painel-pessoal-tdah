(window.DIRECOES = window.DIRECOES || {})[4] = {
  nome: "Luxo",
  ideia: "Livro-razão elegante: serifa fina para números grandes, linhas douradas finas, muito espaço vazio.",
  acento: "#D4AF37",
  fontes: ["Cormorant+Garamond:wght@300;400;500", "IBM+Plex+Mono:wght@400;500"],
  render(root, D, ctx) {
    const fmt = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
    const fmt0 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
    const ac = "#D4AF37";
    const style = `
      <style>
        :host, .l4 { box-sizing: border-box; }
        .l4 * { box-sizing: border-box; }
        .l4 {
          --ac: ${ac};
          --linha: rgba(212,175,55,.28);
          --texto: #ece6d6;
          --fraco: #9a9488;
          font-family: "Cormorant Garamond", serif;
          color: var(--texto);
          background: #000;
          min-height: 760px;
          display: flex;
          flex-direction: column;
          position: relative;
          padding: 22px 20px 78px;
        }
        .l4 .rotulo {
          font-family: "IBM Plex Mono", monospace;
          font-size: 10px;
          letter-spacing: .28em;
          text-transform: uppercase;
          color: var(--fraco);
        }
        .l4 .topo {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          border-bottom: 1px solid var(--linha);
          padding-bottom: 14px;
          margin-bottom: 18px;
        }
        .l4 .topo .data {
          font-size: 15px;
          font-weight: 400;
          letter-spacing: .02em;
        }
        .l4 .topo .hora {
          font-size: 34px;
          font-weight: 300;
          font-variant-numeric: tabular-nums;
          line-height: 1;
          margin-top: 4px;
        }
        .l4 .topo .clima { text-align: right; font-size: 13px; color: var(--fraco); }
        .l4 .topo .clima b { color: var(--texto); font-weight: 400; font-size: 22px; display: block; font-variant-numeric: tabular-nums; }
        .l4 .mic {
          flex: none;
          width: 40px; height: 40px;
          border: 1px solid #d98a6a;
          border-radius: 50%;
          display: flex; align-items: center; justify-content: center;
          background: transparent;
          cursor: pointer;
        }
        .l4 .mic svg { stroke: var(--ac); }
        .l4 .aviso {
          margin: 0 0 18px;
          font-family: "IBM Plex Mono", monospace;
          font-size: 11px;
          letter-spacing: .04em;
          color: #d98a6a;
          border: 1px solid rgba(217,138,106,.35);
          padding: 8px 10px;
          display: flex; align-items: center; gap: 8px;
        }
        .l4 .aviso svg { flex: none; stroke: #d98a6a; }
        .l4 .aviso span { flex: 1; }
        .l4 .grande {
          text-align: center;
          margin: 6px 0 4px;
        }
        .l4 .grande .rotulo { margin-bottom: 6px; }
        .l4 .grande .valor {
          font-size: 56px;
          font-weight: 300;
          letter-spacing: .01em;
          font-variant-numeric: tabular-nums;
          opacity: 0;
          transform: translateY(6px);
          animation: assentar .9s ease forwards .15s;
        }
        .l4.reduz .grande .valor { opacity: 1; transform: none; animation: none; }
        @keyframes assentar { to { opacity: 1; transform: none; } }
        .l4 .linhaOuro {
          height: 1px; background: var(--ac);
          width: 0; margin: 14px auto 18px;
          animation: crescer 1.1s ease forwards .3s;
        }
        .l4.reduz .linhaOuro { width: 70%; animation: none; }
        @keyframes crescer { to { width: 70%; } }
        .l4 .trio {
          display: flex;
          justify-content: space-between;
          text-align: center;
          margin-bottom: 22px;
        }
        .l4 .trio div { flex: 1; }
        .l4 .trio .v { font-size: 19px; font-variant-numeric: tabular-nums; margin-top: 4px; }
        .l4 .trio + .separador, .l4 .separador {
          border: 0; border-top: 1px solid var(--linha); margin: 0 0 18px;
        }
        .l4 .foco {
          border: 1px solid var(--linha);
          padding: 14px 16px;
          margin-bottom: 18px;
        }
        .l4 .foco .rotulo { margin-bottom: 8px; }
        .l4 .foco .txt { font-size: 18px; }
        .l4 .grafico { margin-bottom: 20px; }
        .l4 .grafico .rotulo { margin-bottom: 8px; }
        .l4 .capitulos {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 10px;
          margin-top: auto;
        }
        .l4 .capitulos button {
          background: transparent;
          border: 1px solid var(--linha);
          color: var(--fraco);
          font-family: "IBM Plex Mono", monospace;
          font-size: 10px;
          letter-spacing: .08em;
          text-transform: uppercase;
          padding: 10px 4px;
          min-height: 44px;
          cursor: pointer;
        }
        .l4 .capitulos button:active { border-color: var(--ac); color: var(--texto); }
        .l4 .rodape-nav {
          position: absolute;
          left: 0; right: 0; bottom: 0;
          display: flex;
          border-top: 1px solid var(--linha);
          background: #000;
        }
        .l4 .rodape-nav button {
          flex: 1;
          background: transparent;
          border: 0;
          border-right: 1px solid var(--linha);
          color: var(--fraco);
          font-family: "IBM Plex Mono", monospace;
          font-size: 9px;
          letter-spacing: .1em;
          text-transform: uppercase;
          min-height: 46px;
          cursor: pointer;
        }
        .l4 .rodape-nav button:last-child { border-right: 0; }
        .l4 .rodape-nav button[aria-current="true"] { color: var(--ac); }
        .l4 .chat {
          position: absolute; left: 16px; right: 16px; bottom: 56px;
          border: 1px solid var(--linha);
          display: flex; align-items: center; gap: 8px;
          padding: 0 12px;
          height: 44px;
          background: #000;
        }
        .l4 .chat input {
          flex: 1; background: transparent; border: 0; color: var(--texto);
          font-family: "Cormorant Garamond", serif; font-size: 15px; outline: none;
        }
        .l4 .chat svg { stroke: var(--ac); flex: none; }

        /* financas */
        .l4 .resumoLinha { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px; }
        .l4 .resumoLinha .valor { font-size: 40px; font-weight: 300; font-variant-numeric: tabular-nums; }
        .l4 .comp { font-family: "IBM Plex Mono", monospace; font-size: 11px; color: var(--fraco); margin-bottom: 16px; }
        .l4 .comp b { color: #8faa8a; font-weight: 500; }
        .l4 .cats { list-style: none; padding: 0; margin: 0 0 18px; }
        .l4 .cats li {
          display: flex; justify-content: space-between; align-items: baseline;
          padding: 9px 0; border-bottom: 1px solid var(--linha); font-size: 16px;
        }
        .l4 .cats li span:last-child { font-variant-numeric: tabular-nums; }
        .l4 .barrafat { display: flex; justify-content: space-between; margin-bottom: 18px; }
        .l4 .barrafat div { flex: 1; text-align: center; }
        .l4 .extrato-toggle, .l4 .assin-toggle {
          width: 100%; text-align: left; background: transparent; border: 1px solid var(--linha);
          color: var(--texto); font-family: "IBM Plex Mono", monospace; font-size: 11px;
          letter-spacing: .08em; text-transform: uppercase; padding: 12px 14px; min-height: 44px;
          cursor: pointer; margin-bottom: 10px;
        }
        .l4 .extrato { display: none; margin-bottom: 10px; }
        .l4 .extrato.aberto { display: block; }
        .l4 .extrato .item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--linha); font-size: 14px; }
        .l4 .extrato .item span:first-child { color: var(--fraco); font-family: "IBM Plex Mono", monospace; font-size: 10px; width: 58px; flex: none; }
        .l4 .maisBtn { background: transparent; border: 1px solid var(--linha); color: var(--fraco); font-family: "IBM Plex Mono", monospace; font-size: 10px; letter-spacing: .08em; text-transform: uppercase; padding: 10px; width: 100%; min-height: 44px; cursor: pointer; margin-bottom: 10px; }

        /* vida */
        .l4 .faixa { display: flex; gap: 14px; overflow-x: auto; padding-bottom: 12px; margin-bottom: 16px; border-bottom: 1px solid var(--linha); scrollbar-width: none; }
        .l4 .faixa::-webkit-scrollbar { display: none; }
        .l4 .faixa button { flex: none; width: 60px; background: transparent; border: 0; color: var(--fraco); font-family: "IBM Plex Mono", monospace; font-size: 9px; letter-spacing: .04em; text-align: center; cursor: pointer; }
        .l4 .faixa button .ic { width: 30px; height: 30px; margin: 0 auto 6px; border: 1px solid var(--linha); border-radius: 50%; display: flex; align-items: center; justify-content: center; }
        .l4 .faixa button svg { stroke: var(--fraco); width: 15px; height: 15px; }
        .l4 .faixa button[aria-current="true"] .ic { border-color: var(--ac); }
        .l4 .faixa button[aria-current="true"] svg { stroke: var(--ac); }
        .l4 .faixa button[aria-current="true"] { color: var(--texto); }
        .l4 .secaoConteudo { border: 1px solid var(--linha); padding: 16px; }
        .l4 .secaoConteudo h3 { font-weight: 400; font-size: 24px; margin: 0 0 6px; }
        .l4 .secaoConteudo p { color: var(--fraco); font-size: 14px; margin: 4px 0; line-height: 1.5; }
        .l4 .viagemCard { border: 1px solid var(--linha); padding: 16px; margin-bottom: 16px; text-align: center; }
        .l4 .viagemCard .rota { font-size: 22px; margin: 6px 0; }
        .l4 .viagemCard .dias { font-size: 34px; font-weight: 300; font-variant-numeric: tabular-nums; }
      </style>
    `;

    const svgMic = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke-width="1.5"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><line x1="12" y1="18" x2="12" y2="22"/></svg>`;
    const svgAlerta = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke-width="1.5"><path d="M12 3l10 18H2z"/><line x1="12" y1="9" x2="12" y2="14"/><circle cx="12" cy="17" r=".5"/></svg>`;
    const svgEnviar = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke-width="1.5"><line x1="4" y1="12" x2="20" y2="12"/><polyline points="13,5 20,12 13,19"/></svg>`;
    const ICONES = {
      habitos: `<circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 3"/>`,
      projetos: `<rect x="4" y="5" width="16" height="14" rx="1"/><line x1="4" y1="10" x2="20" y2="10"/>`,
      agenda: `<rect x="4" y="5" width="16" height="15" rx="1"/><line x1="8" y1="3" x2="8" y2="7"/><line x1="16" y1="3" x2="16" y2="7"/>`,
      compras: `<circle cx="9" cy="20" r="1"/><circle cx="17" cy="20" r="1"/><path d="M3 4h2l2.4 11.5a2 2 0 0 0 2 1.5h7.2a2 2 0 0 0 2-1.6L20 8H6"/>`,
      pessoas: `<circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><circle cx="17" cy="9" r="2.4"/><path d="M15 20c.2-2.4 2-4.4 4-4.7"/>`,
      treino: `<path d="M4 12h4M16 12h4M8 12v0M8 7v10M16 7v10"/>`,
      contas: `<rect x="5" y="10" width="14" height="10" rx="1"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>`,
      manutencao: `<path d="M14 6a4 4 0 1 0-4 6l-6 6 2 2 6-6a4 4 0 0 0 6-4l-3 3-2-2 3-3z"/>`,
      garantia: `<path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/>`,
      viagens: `<path d="M2 16l20-7-7 20-3-8-8-3z"/>`,
      lugares: `<path d="M12 21s7-6.5 7-11.5A7 7 0 0 0 5 9.5C5 14.5 12 21 12 21z"/><circle cx="12" cy="9.5" r="2"/>`,
      presentes: `<rect x="4" y="9" width="16" height="11"/><line x1="4" y1="13" x2="20" y2="13"/><path d="M12 9v11M8 9a2.5 2.5 0 0 1 0-5c2 0 4 5 4 5M16 9a2.5 2.5 0 0 0 0-5c-2 0-4 5-4 5"/>`,
      aprender: `<path d="M3 6l9-3 9 3-9 3-9-3z"/><path d="M6 8v6c0 1.5 2.5 3 6 3s6-1.5 6-3V8"/>`,
      salvos: `<path d="M6 3h12v18l-6-4-6 4z"/>`,
      mensagem: `<path d="M4 5h16v11H8l-4 4z"/>`,
      vale_a_pena: `<path d="M9 12l2 2 4-4"/><circle cx="12" cy="12" r="9"/>`,
      progresso: `<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>`,
      revisao: `<path d="M4 4h16v16H4z"/><path d="M8 9h8M8 13h8M8 17h5"/>`
    };

    function barSVG(dados, w, h) {
      const max = Math.max(...dados.map(d => d.acumulado), 1);
      const step = w / (dados.length - 1 || 1);
      const pts = dados.map((d, i) => `${(i * step).toFixed(1)},${(h - (d.acumulado / max) * h).toFixed(1)}`).join(" ");
      return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="none" style="overflow:visible">
        <polyline points="${pts}" fill="none" stroke="${ac}" stroke-width="1" />
        <line x1="0" y1="${h}" x2="${w}" y2="${h}" stroke="var(--linha,#333)" stroke-width="1" />
      </svg>`;
    }

    function horaData() {
      const d = new Date();
      const h = d.getHours().toString().padStart(2, "0");
      const m = d.getMinutes().toString().padStart(2, "0");
      return { hora: `${h}:${m}`, data: new Intl.DateTimeFormat("pt-BR", { weekday: "long", day: "2-digit", month: "long" }).format(d) };
    }

    let timers = [];
    function limparTimers() { timers.forEach(clearInterval); timers = []; }

    function telaHoje() {
      const { hora, data } = horaData();
      const F = D.financas;
      return `
        <div class="topo">
          <div>
            <div class="rotulo">${D.hoje.cidade}</div>
            <div class="data">${data}</div>
            <div class="hora" id="l4-hora">${hora}</div>
          </div>
          <div class="clima">
            <b>${D.hoje.clima.temp}°</b>
            ${D.hoje.clima.cond}<br>chuva ${D.hoje.clima.chuva_prob}%
          </div>
        </div>
        <div class="aviso">${svgAlerta}<span>${D.aviso_critico}</span><button class="mic" aria-label="Comando de voz">${svgMic}</button></div>
        <div class="grande">
          <div class="rotulo">Gasto do mês</div>
          <div class="valor">${fmt.format(F.gasto_mes)}</div>
        </div>
        <div class="linhaOuro"></div>
        ${barSVG(F.por_dia_mes, 300, 40)}
        <div class="trio" style="margin-top:14px">
          <div><div class="rotulo">Hoje</div><div class="v">${fmt.format(F.gasto_hoje)}</div></div>
          <div><div class="rotulo">Fatura</div><div class="v">${fmt.format(F.fatura_atual)}</div></div>
          <div><div class="rotulo">Conta</div><div class="v">${fmt.format(F.saldo_conta)}</div></div>
        </div>
        <hr class="separador">
        <div class="foco">
          <div class="rotulo">Em foco agora</div>
          <div class="txt">${D.tarefas.em_foco}</div>
        </div>
        <div class="capitulos">
          <button data-ir="financas">Finanças</button>
          <button data-ir="vida">Vida</button>
          <button data-vai-tarefas>Tarefas</button>
          <button data-vai-aviacao>Aviação</button>
        </div>
        <div class="chat"><input placeholder="Perguntar algo..." />${svgEnviar}</div>
      `;
    }

    function telaFinancas() {
      const F = D.financas;
      const dif = F.gasto_mes - F.gasto_mes_anterior;
      const pct = F.gasto_mes_anterior ? Math.round((dif / F.gasto_mes_anterior) * 100) : 0;
      const cats = F.por_categoria.map(c => `<li><span>${c.categoria}</span><span>${fmt.format(c.valor)}</span></li>`).join("");
      const ext = F.ultimos_15_dias.map((it, i) => `<div class="item" style="${i >= 6 ? 'display:none' : ''}" data-idx="${i}"><span>${it.data.slice(8, 10)}/${it.data.slice(5, 7)}</span><span style="flex:1;padding:0 8px">${it.descricao}</span><span>${fmt.format(it.valor)}</span></div>`).join("");
      const assin = F.assinaturas.map(a => `<div class="item"><span></span><span style="flex:1;padding:0 8px">${a.nome} · ${a.proxima}</span><span>${fmt.format(a.valor)}</span></div>`).join("");
      return `
        <div class="rotulo">Resumo do mês · ${F.mes}</div>
        <div class="resumoLinha"><div class="valor">${fmt.format(F.gasto_mes)}</div></div>
        <div class="comp">vs. mês anterior <b>${pct <= 0 ? "" : "+"}${pct}%</b> (${fmt.format(F.gasto_mes_anterior)})${F.orcamento_mes ? " · orçamento " + fmt.format(F.orcamento_mes) : ""}</div>
        <div class="rotulo" style="margin-bottom:8px">Por categoria</div>
        <ul class="cats">${cats}</ul>
        <div class="barrafat">
          <div><div class="rotulo">Fatura atual</div><div class="v" style="font-size:18px">${fmt.format(F.fatura_atual)}</div></div>
          <div><div class="rotulo">Saldo conta</div><div class="v" style="font-size:18px">${fmt.format(F.saldo_conta)}</div></div>
        </div>
        <button class="extrato-toggle" id="l4-extToggle">Extrato · últimos 15 dias ▾</button>
        <div class="extrato" id="l4-ext">
          ${ext}
          <button class="maisBtn" id="l4-mais" style="${F.ultimos_15_dias.length <= 6 ? 'display:none' : ''}">Carregar mais</button>
        </div>
        <button class="extrato-toggle" id="l4-assinToggle">Assinaturas (${F.assinaturas.length}) ▾</button>
        <div class="extrato" id="l4-assin">${assin}</div>
      `;
    }

    function telaVida() {
      const secoes = D.vida_secoes.map((s, i) => `
        <button data-sec="${i}" aria-current="${i === 0}">
          <span class="ic"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke-width="1.5">${ICONES[s.id] || '<circle cx="12" cy="12" r="8"/>'}</svg></span>
          ${s.nome}
        </button>`).join("");
      const viagem = D.viagem ? `
        <div class="viagemCard">
          <div class="rotulo">Próxima viagem</div>
          <div class="rota">${D.viagem.origem} — ${D.viagem.destino}</div>
          <div class="dias">${D.viagem.dias_faltando}</div>
          <div class="rotulo">dias · ${D.viagem.data}</div>
        </div>` : "";
      return `
        ${viagem}
        <div class="faixa" id="l4-faixa">${secoes}</div>
        <div class="secaoConteudo" id="l4-secConteudo"></div>
      `;
    }

    function conteudoSecao(i) {
      const s = D.vida_secoes[i];
      const linhas = {
        habitos: ["Água · 6/8 copos", "Sono · 7h20"],
        projetos: ["App pessoal · em andamento", "Revisão financeira · pendente"],
        agenda: ["Consulta médica · sexta", "Aniversário · próxima semana"],
        compras: ["Filtro de café", "Pilha AA"],
        pessoas: ["Contato pendente: retornar ligação", "Aniversário próximo: Marina"],
        treino: ["Perna · segunda", "Cardio · quarta"],
        contas: ["3 credenciais salvas"],
        manutencao: ["Revisão do carro · outubro"],
        garantia: ["Notebook até 2027"],
        viagens: [D.viagem ? `${D.viagem.origem} → ${D.viagem.destino} em ${D.viagem.dias_faltando} dias` : "Nenhuma viagem planejada"],
        lugares: ["Restaurante novo no centro"],
        presentes: ["Ideia para o pai: livro"],
        aprender: ["Inglês técnico de aviação"],
        salvos: ["4 links salvos"],
        mensagem: ["Rascunho pendente de revisão"],
        vale_a_pena: ["Trocar de carro? análise em aberto"],
        progresso: ["Meta do mês: 60% concluída"],
        revisao: ["Checklist Q3 pendente"]
      }[s.id] || [];
      return `<h3>${s.nome}</h3><p>${s.resumo}</p>${linhas.map(l => `<p>· ${l}</p>`).join("")}`;
    }

    function nav() {
      const telas = [["hoje", "Hoje"], ["financas", "Finanças"], ["vida", "Vida"]];
      return `<div class="rodape-nav">${telas.map(([id, l]) => `<button data-nav="${id}" aria-current="${ctx.tela === id}">${l}</button>`).join("")}</div>`;
    }

    function montar() {
      const wrap = root.getElementById("l4-wrap");
      wrap.className = "l4" + (ctx.reduzido ? " reduz" : "");
      let corpo = "";
      if (ctx.tela === "hoje") corpo = telaHoje();
      else if (ctx.tela === "financas") corpo = telaFinancas();
      else corpo = telaVida();
      wrap.innerHTML = corpo + nav();

      wrap.querySelectorAll("[data-ir]").forEach(b => b.onclick = () => ctx.irPara(b.dataset.ir));
      wrap.querySelectorAll("[data-nav]").forEach(b => b.onclick = () => ctx.irPara(b.dataset.nav));
      wrap.querySelectorAll("[data-vai-tarefas],[data-vai-aviacao]").forEach(b => b.onclick = () => ctx.irPara("vida"));

      if (ctx.tela === "hoje" && !ctx.reduzido) {
        timers.push(setInterval(() => {
          const h = wrap.querySelector("#l4-hora");
          if (h) h.textContent = horaData().hora;
        }, 1000 * 15));
      }

      if (ctx.tela === "financas") {
        const extToggle = wrap.querySelector("#l4-extToggle");
        const ext = wrap.querySelector("#l4-ext");
        extToggle.onclick = () => ext.classList.toggle("aberto");
        const assinToggle = wrap.querySelector("#l4-assinToggle");
        const assin = wrap.querySelector("#l4-assin");
        assinToggle.onclick = () => assin.classList.toggle("aberto");
        const mais = wrap.querySelector("#l4-mais");
        if (mais) mais.onclick = () => {
          ext.querySelectorAll(".item[data-idx]").forEach(el => el.style.display = "flex");
          mais.style.display = "none";
        };
      }

      if (ctx.tela === "vida") {
        const faixa = wrap.querySelector("#l4-faixa");
        const conteudo = wrap.querySelector("#l4-secConteudo");
        let sel = 0;
        const render = () => { conteudo.innerHTML = conteudoSecao(sel); };
        render();
        faixa.querySelectorAll("button").forEach((b, i) => {
          b.onclick = () => {
            sel = i;
            faixa.querySelectorAll("button").forEach((x, j) => x.setAttribute("aria-current", j === i));
            render();
          };
        });
      }
    }

    root.innerHTML = style + '<div class="l4" id="l4-wrap"></div>';
    montar();

    return () => { limparTimers(); };
  }
};
