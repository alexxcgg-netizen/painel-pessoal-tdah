(window.DIRECOES = window.DIRECOES || {})[10] = {
  nome: "Rota",
  ideia: "Linha do tempo como rota de voo: waypoints estilo aviação, avião animado, gasto como combustível consumido.",
  acento: "#A5D8FF",
  fontes: ["Chakra+Petch:wght@400;500;600", "IBM+Plex+Mono:wght@400;500"],
  render(root, D, ctx) {
    const fmt = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
    const ac = "#A5D8FF";

    const style = `
      <style>
        :host, .l10 { box-sizing: border-box; }
        .l10 * { box-sizing: border-box; }
        .l10 {
          --ac: ${ac};
          --linha: #262626;
          --texto: #e4ecf2;
          --fraco: #8a9199;
          font-family: "Chakra Petch", sans-serif;
          color: var(--texto);
          background: #000;
          min-height: 760px;
          position: relative;
          padding: 18px 16px 82px;
          background-image:
            linear-gradient(var(--linha) 1px, transparent 1px),
            linear-gradient(90deg, var(--linha) 1px, transparent 1px);
          background-size: 28px 28px;
          background-position: -1px -1px;
        }
        .l10 .mono { font-family: "IBM Plex Mono", monospace; }
        .l10 .topo {
          display: flex; justify-content: space-between; align-items: flex-start;
          border: 1px solid var(--linha); padding: 10px 12px; margin-bottom: 12px;
          background: #000;
        }
        .l10 .topo .rotulo { font-size: 9px; letter-spacing: .2em; text-transform: uppercase; color: var(--fraco); }
        .l10 .topo .hora { font-size: 30px; font-variant-numeric: tabular-nums; line-height: 1; margin-top: 4px; }
        .l10 .topo .data { font-size: 11px; color: var(--fraco); text-transform: capitalize; margin-top: 2px; }
        .l10 .topo .clima { text-align: right; font-size: 11px; color: var(--fraco); }
        .l10 .topo .clima b { color: var(--texto); font-size: 20px; display: block; font-variant-numeric: tabular-nums; }
        .l10 .aviso {
          display: flex; align-items: center; gap: 8px;
          border: 1px solid #7a3a2a; color: #e08a6a; background: #000;
          padding: 8px 10px; font-size: 11px; margin-bottom: 14px;
        }
        .l10 .aviso svg { stroke: #e08a6a; flex: none; }
        .l10 .mic {
          position: absolute; top: 18px; right: 16px;
          width: 44px; height: 44px; border-radius: 50%;
          border: 1px solid var(--ac); background: #000;
          display: flex; align-items: center; justify-content: center; cursor: pointer;
        }
        .l10 .mic svg { stroke: var(--ac); }

        .l10 .painel { border: 1px solid var(--linha); background: #000; padding: 14px 14px 16px; margin-bottom: 14px; }
        .l10 .painel .cab { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px; }
        .l10 .painel .cab .rotulo { font-size: 9px; letter-spacing: .18em; text-transform: uppercase; color: var(--fraco); }
        .l10 .painel .cab .valor { font-size: 26px; font-variant-numeric: tabular-nums; }

        /* rota do dia */
        .l10 .rotaDia { position: relative; height: 88px; margin: 8px 4px 0; }
        .l10 .rotaDia svg { overflow: visible; }
        .l10 .wp { font-family: "IBM Plex Mono", monospace; }
        .l10 .wp-label { font-size: 9px; fill: var(--fraco); letter-spacing: .04em; }
        .l10 .wp-hora { font-size: 8px; fill: #5f666d; }

        .l10 .trio { display: flex; justify-content: space-between; margin-top: 6px; }
        .l10 .trio div { flex: 1; text-align: center; }
        .l10 .trio .rotulo { font-size: 9px; letter-spacing: .1em; text-transform: uppercase; color: var(--fraco); }
        .l10 .trio .v { font-size: 16px; font-variant-numeric: tabular-nums; margin-top: 2px; }

        /* viagem grande */
        .l10 .viagem { border: 1px solid var(--ac); padding: 16px 14px; margin-bottom: 14px; }
        .l10 .viagem .cab { display: flex; justify-content: space-between; font-size: 10px; letter-spacing: .18em; text-transform: uppercase; color: var(--fraco); margin-bottom: 10px; }
        .l10 .viagem .codigos { display: flex; justify-content: space-between; font-size: 26px; font-family: "IBM Plex Mono", monospace; }
        .l10 .viagem .codigos span:last-child { color: var(--ac); }
        .l10 .viagem .barra { position: relative; height: 30px; margin: 10px 0 6px; }
        .l10 .viagem .info { display: flex; justify-content: space-between; font-size: 11px; color: var(--fraco); }
        .l10 .viagem .dias { color: var(--ac); font-size: 15px; }

        /* combustivel/gasto perfil */
        .l10 .perfil svg { display: block; }
        .l10 .cats { list-style: none; margin: 10px 0 0; padding: 0; }
        .l10 .cats li { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--linha); font-size: 13px; }
        .l10 .cats li .barra { flex: 1; height: 3px; background: var(--linha); margin: 0 10px; position: relative; }
        .l10 .cats li .barra i { position: absolute; left: 0; top: 0; bottom: 0; background: var(--ac); }
        .l10 .cats li .val { font-family: "IBM Plex Mono", monospace; font-size: 11px; width: 70px; text-align: right; font-variant-numeric: tabular-nums; }

        .l10 .extrato-toggle, .l10 .assin-toggle {
          width: 100%; text-align: left; background: #000; border: 1px solid var(--linha);
          color: var(--texto); font-family: "IBM Plex Mono", monospace; font-size: 10px;
          letter-spacing: .08em; text-transform: uppercase; padding: 11px 12px; min-height: 44px;
          cursor: pointer; margin-bottom: 8px;
        }
        .l10 .extrato { display: none; margin-bottom: 8px; }
        .l10 .extrato.aberto { display: block; }
        .l10 .extrato .item { display: flex; justify-content: space-between; padding: 7px 0; border-bottom: 1px solid var(--linha); font-size: 12px; }
        .l10 .extrato .item span:first-child { color: var(--fraco); font-family: "IBM Plex Mono", monospace; font-size: 9px; width: 50px; flex: none; }
        .l10 .maisBtn { background: #000; border: 1px solid var(--linha); color: var(--fraco); font-family: "IBM Plex Mono", monospace; font-size: 9px; letter-spacing: .08em; text-transform: uppercase; padding: 9px; width: 100%; min-height: 44px; cursor: pointer; margin-bottom: 8px; }

        .l10 .foco { border: 1px solid var(--linha); padding: 12px 14px; margin-bottom: 14px; display: flex; align-items: center; gap: 10px; }
        .l10 .foco svg { stroke: var(--ac); flex: none; }
        .l10 .foco .txt .rotulo { font-size: 9px; letter-spacing: .16em; text-transform: uppercase; color: var(--fraco); }
        .l10 .foco .txt .v { font-size: 15px; margin-top: 2px; }

        .l10 .atalhos { display: grid; grid-template-columns: repeat(4,1fr); gap: 8px; margin-bottom: 8px; }
        .l10 .atalhos button { background: #000; border: 1px solid var(--linha); color: var(--fraco); font-family: "IBM Plex Mono", monospace; font-size: 9px; letter-spacing: .04em; text-transform: uppercase; padding: 10px 2px; min-height: 44px; cursor: pointer; }

        /* vida - waypoints rota horizontal */
        .l10 .rotaVida { position: relative; overflow-x: auto; padding: 16px 8px 20px; margin-bottom: 8px; scrollbar-width: none; }
        .l10 .rotaVida::-webkit-scrollbar { display: none; }
        .l10 .rotaVidaInner { position: relative; height: 70px; }
        .l10 .rotaVidaInner svg { position: absolute; top: 0; left: 0; }
        .l10 .wpv { position: absolute; top: 0; width: 64px; text-align: center; transform: translateX(-50%); cursor: pointer; background: transparent; border: 0; }
        .l10 .wpv .dot { width: 12px; height: 12px; border: 1.5px solid var(--fraco); border-radius: 50%; margin: 0 auto 6px; background: #000; }
        .l10 .wpv[aria-current="true"] .dot { border-color: var(--ac); background: var(--ac); }
        .l10 .wpv .cod { font-family: "IBM Plex Mono", monospace; font-size: 10px; color: var(--fraco); letter-spacing: .04em; }
        .l10 .wpv[aria-current="true"] .cod { color: var(--texto); }
        .l10 .secaoConteudo { border: 1px solid var(--ac); padding: 16px; }
        .l10 .secaoConteudo h3 { font-weight: 500; font-size: 20px; margin: 0 0 6px; }
        .l10 .secaoConteudo p { color: var(--fraco); font-size: 13px; margin: 4px 0; line-height: 1.5; }

        .l10 .rodape-nav {
          position: absolute; left: 0; right: 0; bottom: 0;
          display: flex; border-top: 1px solid var(--linha); background: #000;
        }
        .l10 .rodape-nav button {
          flex: 1; background: transparent; border: 0; border-right: 1px solid var(--linha);
          color: var(--fraco); font-family: "IBM Plex Mono", monospace; font-size: 9px;
          letter-spacing: .1em; text-transform: uppercase; min-height: 46px; cursor: pointer;
        }
        .l10 .rodape-nav button:last-child { border-right: 0; }
        .l10 .rodape-nav button[aria-current="true"] { color: var(--ac); }
        .l10 .chat {
          position: absolute; left: 16px; right: 16px; bottom: 56px;
          border: 1px solid var(--linha); display: flex; align-items: center; gap: 8px;
          padding: 0 12px; height: 44px; background: #000;
        }
        .l10 .chat input { flex: 1; background: transparent; border: 0; color: var(--texto); font-family: "Chakra Petch", sans-serif; font-size: 14px; outline: none; }
        .l10 .chat svg { stroke: var(--ac); flex: none; }
      </style>
    `;

    const svgMic = `<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke-width="1.5"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><line x1="12" y1="18" x2="12" y2="22"/></svg>`;
    const svgAlerta = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke-width="1.5"><path d="M12 3l10 18H2z"/><line x1="12" y1="9" x2="12" y2="14"/><circle cx="12" cy="17" r=".5"/></svg>`;
    const svgEnviar = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke-width="1.5"><line x1="4" y1="12" x2="20" y2="12"/><polyline points="13,5 20,12 13,19"/></svg>`;
    const svgFoco = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke-width="1.5"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/></svg>`;
    const svgAviao = (rot) => `<svg width="18" height="18" viewBox="0 0 24 24" fill="#000" stroke="${ac}" stroke-width="1.5" style="transform:rotate(${rot}deg);overflow:visible"><path d="M12 2l3 8 7 4-7 1-1 5-2-4-2 4-1-5-7-1 7-4z"/></svg>`;

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

    // gera 5 waypoints ficticios de codigo estilo aviacao para o dia, com progresso baseado na hora atual
    function waypointsDia() {
      const agora = new Date();
      const minutosAgora = agora.getHours() * 60 + agora.getMinutes();
      const F = D.financas, T = D.tarefas;
      const pontos = [
        { cod: "ALFHA", hora: "06:00", min: 6 * 60, label: "Início" },
        { cod: "TASKX", hora: "09:30", min: 9 * 60 + 30, label: T.em_foco.slice(0, 14) },
        { cod: "MIDAY", hora: "13:00", min: 13 * 60, label: "Almoço" },
        { cod: "GASTO", hora: "16:00", min: 16 * 60, label: fmt.format(F.gasto_hoje) },
        { cod: "FINAL", hora: "21:00", min: 21 * 60, label: "Fim do dia" }
      ];
      return { pontos, minutosAgora };
    }

    function rotaDiaSVG() {
      const { pontos, minutosAgora } = waypointsDia();
      const w = 300, h = 60, pad = 14;
      const minMin = pontos[0].min, maxMin = pontos[pontos.length - 1].min;
      const x = m => pad + ((m - minMin) / (maxMin - minMin)) * (w - pad * 2);
      const y = h / 2;
      const prog = Math.max(0, Math.min(1, (minutosAgora - minMin) / (maxMin - minMin)));
      const avX = pad + prog * (w - pad * 2);
      const wps = pontos.map(p => {
        const passou = p.min <= minutosAgora;
        return `<g>
          <circle cx="${x(p.min)}" cy="${y}" r="3.2" fill="${passou ? ac : '#000'}" stroke="${passou ? ac : '#5f666d'}" stroke-width="1.2"/>
          <text x="${x(p.min)}" y="${y - 12}" text-anchor="middle" class="wp wp-label">${p.cod}</text>
          <text x="${x(p.min)}" y="${y + 18}" text-anchor="middle" class="wp wp-hora">${p.hora}</text>
        </g>`;
      }).join("");
      return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}">
        <line x1="${pad}" y1="${y}" x2="${w - pad}" y2="${y}" stroke="#333" stroke-width="1"/>
        <line x1="${pad}" y1="${y}" x2="${avX}" y2="${y}" stroke="${ac}" stroke-width="1.2"/>
        ${wps}
        <g id="l10-aviaoDia" style="transform:translate(${avX}px,${y - 9}px)">${svgAviao(-90)}</g>
      </svg>`;
    }

    function viagemBarraSVG() {
      const v = D.viagem;
      const w = 300, h = 24, pad = 4;
      // proporcional: usamos dias_faltando sobre uma janela plausivel (ex: 30 dias antes -> agora)
      const janela = Math.max(v.dias_faltando + 5, 30);
      const prog = Math.max(0, Math.min(1, 1 - v.dias_faltando / janela));
      const avX = pad + prog * (w - pad * 2);
      return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" style="overflow:visible">
        <line x1="${pad}" y1="${h/2}" x2="${w-pad}" y2="${h/2}" stroke="#333" stroke-width="1"/>
        <line x1="${pad}" y1="${h/2}" x2="${avX}" y2="${h/2}" stroke="${ac}" stroke-width="1.5"/>
        <circle cx="${pad}" cy="${h/2}" r="3" fill="#000" stroke="${ac}" stroke-width="1.2"/>
        <circle cx="${w-pad}" cy="${h/2}" r="3" fill="#000" stroke="${ac}" stroke-width="1.2"/>
        <g id="l10-aviaoViagem" style="transform:translate(${avX}px,${h/2-9}px)">${svgAviao(-90)}</g>
      </svg>`;
    }

    // perfil de combustivel consumido ao longo do mes (por_dia_mes), com area preenchida
    function perfilSVG() {
      const dados = D.financas.por_dia_mes;
      const max = Math.max(...dados.map(d => d.acumulado), 1);
      const w = 300, h = 90;
      const step = w / (dados.length - 1 || 1);
      const pts = dados.map((d, i) => [i * step, h - (d.acumulado / max) * h]);
      const linha = pts.map(p => p.join(",")).join(" ");
      const area = `0,${h} ` + linha + ` ${w},${h}`;
      return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="none">
        <polygon points="${area}" fill="${ac}" opacity=".12"/>
        <polyline points="${linha}" fill="none" stroke="${ac}" stroke-width="1.2"/>
        <line x1="0" y1="${h}" x2="${w}" y2="${h}" stroke="#333" stroke-width="1"/>
      </svg>`;
    }

    function horaData() {
      const d = new Date();
      const h = d.getHours().toString().padStart(2, "0");
      const m = d.getMinutes().toString().padStart(2, "0");
      return { hora: `${h}:${m}`, data: new Intl.DateTimeFormat("pt-BR", { weekday: "short", day: "2-digit", month: "short" }).format(d) };
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
            <div class="hora" id="l10-hora">${hora}</div>
            <div class="data">${data}</div>
          </div>
          <div class="clima"><b>${D.hoje.clima.temp}°</b>${D.hoje.clima.cond}<br>chuva ${D.hoje.clima.chuva_prob}%</div>
        </div>
        <div class="aviso">${svgAlerta}<span>${D.aviso_critico}</span></div>

        <div class="painel">
          <div class="cab"><span class="rotulo mono">Rota do dia</span><span class="valor mono" style="font-size:12px;color:var(--fraco)">05 WP</span></div>
          <div class="rotaDia">${rotaDiaSVG()}</div>
          <div class="trio">
            <div><div class="rotulo">Hoje</div><div class="v">${fmt.format(F.gasto_hoje)}</div></div>
            <div><div class="rotulo">Fatura</div><div class="v">${fmt.format(F.fatura_atual)}</div></div>
            <div><div class="rotulo">Conta</div><div class="v">${fmt.format(F.saldo_conta)}</div></div>
          </div>
        </div>

        <div class="painel">
          <div class="cab"><span class="rotulo mono">Combustível consumido (mês)</span><span class="valor mono" style="font-size:16px">${fmt.format(F.gasto_mes)}</span></div>
          <div class="perfil">${perfilSVG()}</div>
        </div>

        <div class="foco">${svgFoco}<div class="txt"><div class="rotulo">Em foco agora</div><div class="v">${D.tarefas.em_foco}</div></div></div>

        <div class="atalhos">
          <button data-ir="financas">Finanças</button>
          <button data-ir="vida">Vida</button>
          <button data-vai>Tarefas</button>
          <button data-vai>Aviação</button>
        </div>
        <button class="mic" aria-label="Comando de voz">${svgMic}</button>
        <div class="chat"><input placeholder="Perguntar algo..." />${svgEnviar}</div>
      `;
    }

    function telaFinancas() {
      const F = D.financas;
      const dif = F.gasto_mes - F.gasto_mes_anterior;
      const pct = F.gasto_mes_anterior ? Math.round((dif / F.gasto_mes_anterior) * 100) : 0;
      const maxCat = Math.max(...F.por_categoria.map(c => c.valor), 1);
      const cats = F.por_categoria.map(c => `<li><span>${c.categoria}</span><span class="barra"><i style="width:${(c.valor / maxCat * 100).toFixed(0)}%"></i></span><span class="val">${fmt.format(c.valor)}</span></li>`).join("");
      const ext = F.ultimos_15_dias.map((it, i) => `<div class="item" style="${i >= 6 ? 'display:none' : ''}" data-idx="${i}"><span>${it.data.slice(8, 10)}/${it.data.slice(5, 7)}</span><span style="flex:1;padding:0 8px">${it.descricao}</span><span>${fmt.format(it.valor)}</span></div>`).join("");
      const assin = F.assinaturas.map(a => `<div class="item"><span></span><span style="flex:1;padding:0 8px">${a.nome} · ${a.proxima}</span><span>${fmt.format(a.valor)}</span></div>`).join("");
      return `
        <div class="painel">
          <div class="cab"><span class="rotulo mono">Combustível consumido · ${F.mes}</span><span class="valor mono" style="font-size:22px">${fmt.format(F.gasto_mes)}</span></div>
          <div class="perfil">${perfilSVG()}</div>
          <div class="trio" style="margin-top:8px">
            <div><div class="rotulo">vs. anterior</div><div class="v">${pct <= 0 ? "" : "+"}${pct}%</div></div>
            <div><div class="rotulo">Fatura</div><div class="v">${fmt.format(F.fatura_atual)}</div></div>
            <div><div class="rotulo">Conta</div><div class="v">${fmt.format(F.saldo_conta)}</div></div>
          </div>
        </div>
        <div class="painel">
          <div class="cab"><span class="rotulo mono">Consumo por categoria</span></div>
          <ul class="cats">${cats}</ul>
        </div>
        <button class="extrato-toggle" id="l10-extToggle">Extrato · últimos 15 dias ▾</button>
        <div class="extrato" id="l10-ext">
          ${ext}
          <button class="maisBtn" id="l10-mais" style="${F.ultimos_15_dias.length <= 6 ? 'display:none' : ''}">Carregar mais</button>
        </div>
        <button class="extrato-toggle" id="l10-assinToggle">Assinaturas (${F.assinaturas.length}) ▾</button>
        <div class="extrato" id="l10-assin">${assin}</div>
      `;
    }

    function telaVida() {
      const secoes = D.vida_secoes;
      const n = secoes.length;
      const w = Math.max(n * 74, 300);
      const y = 12;
      const linha = `<svg width="${w}" height="70"><line x1="32" y1="${y}" x2="${w - 32}" y2="${y}" stroke="#333" stroke-width="1"/></svg>`;
      const wps = secoes.map((s, i) => `
        <button class="wpv" style="left:${32 + i * 74}px" data-sec="${i}" aria-current="${i === 0}">
          <span class="dot"></span>
          <span class="cod">${s.id.slice(0, 5).toUpperCase()}</span>
        </button>`).join("");
      const viagem = D.viagem ? `
        <div class="painel">
          <div class="cab"><span class="rotulo mono">Próxima viagem</span><span class="valor mono" style="font-size:14px;color:var(--ac)">${D.viagem.dias_faltando} dias</span></div>
          <div class="rota" style="display:flex;justify-content:space-between;font-family:'IBM Plex Mono',monospace;font-size:20px;margin-bottom:6px">
            <span>${D.viagem.origem}</span><span style="color:var(--ac)">${D.viagem.destino}</span>
          </div>
          ${viagemBarraSVG()}
          <div class="info" style="margin-top:4px;display:flex;justify-content:space-between"><span>Hoje</span><span>${D.viagem.data}</span></div>
        </div>` : "";
      return `
        ${viagem}
        <div class="rotaVida" id="l10-faixa">
          <div class="rotaVidaInner" style="width:${w}px">
            ${linha}
            ${wps}
          </div>
        </div>
        <div class="secaoConteudo" id="l10-secConteudo"></div>
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
      const icone = ICONES[s.id] || '<circle cx="12" cy="12" r="8"/>';
      return `<h3><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="${ac}" stroke-width="1.5" style="vertical-align:-3px;margin-right:6px">${icone}</svg>${s.nome}</h3><p>${s.resumo}</p>${linhas.map(l => `<p>· ${l}</p>`).join("")}`;
    }

    function nav() {
      const telas = [["hoje", "Hoje"], ["financas", "Finanças"], ["vida", "Vida"]];
      return `<div class="rodape-nav">${telas.map(([id, l]) => `<button data-nav="${id}" aria-current="${ctx.tela === id}">${l}</button>`).join("")}</div>`;
    }

    function montar() {
      const wrap = root.getElementById("l10-wrap");
      let corpo = "";
      if (ctx.tela === "hoje") corpo = telaHoje();
      else if (ctx.tela === "financas") corpo = telaFinancas();
      else corpo = telaVida();
      wrap.innerHTML = corpo + nav();

      wrap.querySelectorAll("[data-ir]").forEach(b => b.onclick = () => ctx.irPara(b.dataset.ir));
      wrap.querySelectorAll("[data-nav]").forEach(b => b.onclick = () => ctx.irPara(b.dataset.nav));
      wrap.querySelectorAll("[data-vai]").forEach(b => b.onclick = () => ctx.irPara("vida"));

      if (ctx.tela === "hoje" && !ctx.reduzido) {
        timers.push(setInterval(() => {
          const h = wrap.querySelector("#l10-hora");
          if (h) h.textContent = horaData().hora;
          const av = wrap.querySelector("#l10-aviaoDia");
          if (av) {
            const { pontos, minutosAgora } = waypointsDia();
            const w = 300, pad = 14;
            const minMin = pontos[0].min, maxMin = pontos[pontos.length - 1].min;
            const prog = Math.max(0, Math.min(1, (minutosAgora - minMin) / (maxMin - minMin)));
            const avX = pad + prog * (w - pad * 2);
            av.style.transform = `translate(${avX}px, ${30 - 9}px)`;
          }
        }, 1000 * 30));
      }

      if (ctx.tela === "financas") {
        const extToggle = wrap.querySelector("#l10-extToggle");
        const ext = wrap.querySelector("#l10-ext");
        extToggle.onclick = () => ext.classList.toggle("aberto");
        const assinToggle = wrap.querySelector("#l10-assinToggle");
        const assin = wrap.querySelector("#l10-assin");
        assinToggle.onclick = () => assin.classList.toggle("aberto");
        const mais = wrap.querySelector("#l10-mais");
        if (mais) mais.onclick = () => {
          ext.querySelectorAll(".item[data-idx]").forEach(el => el.style.display = "flex");
          mais.style.display = "none";
        };
      }

      if (ctx.tela === "vida") {
        const faixa = wrap.querySelector("#l10-faixa");
        const conteudo = wrap.querySelector("#l10-secConteudo");
        let sel = 0;
        const render = () => { conteudo.innerHTML = conteudoSecao(sel); };
        render();
        faixa.querySelectorAll(".wpv").forEach((b, i) => {
          b.onclick = () => {
            sel = i;
            faixa.querySelectorAll(".wpv").forEach((x, j) => x.setAttribute("aria-current", j === i));
            render();
          };
        });
      }
    }

    root.innerHTML = style + '<div class="l10" id="l10-wrap"></div>';
    montar();

    return () => { limparTimers(); };
  }
};
