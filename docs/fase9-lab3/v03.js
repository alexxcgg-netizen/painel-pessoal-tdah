/* ===== Variante 3: Grupos ===== */
(function () {
  CONVERSA_BASE.registrar(3, "Grupos", "As 18 secoes reunidas em 4 grupos com cartao, contador e mini grafico; toca para abrir a lista.", function (app, H) {
    const secs = H.D.vida_secoes || [];
    const porId = id => secs.find(s => s.id === id);

    app.innerHTML = `
      <div class="vtitle">Conversas · Vida</div>
      <div class="thread" id="threadTop">
        <div class="msg"><div class="dot"></div><div class="bubble">
          <p class="lead">Organizei sua vida em 4 grupos.</p>
          <div class="grupogrid" id="grupogrid">${H.GRUPOS.map(g => `
            <button class="grupocard" data-g="${g.nome}">
              <div><div class="gc-nome">${g.nome}</div><div class="gc-num">${g.ids.length} secoes</div></div>
              <div class="gc-chart">${H.chartMini(g.nome, 140, 30)}</div>
            </button>`).join("")}</div>
        </div></div>
      </div>
      <div id="grupoThread"></div>
    `;
    const th = app.querySelector("#grupoThread");
    app.querySelectorAll(".grupocard").forEach(b => b.addEventListener("click", () => {
      const g = H.GRUPOS.find(x => x.nome === b.dataset.g);
      th.innerHTML = `
        <div class="thread">
          <div class="msg user"><div class="bubble user">O que tenho em ${g.nome.toLowerCase()}?</div></div>
          <div class="msg"><div class="dot"></div><div class="bubble">
            <p class="lead">${g.ids.length} secoes em ${g.nome}.</p>
            <div class="card"><div class="convlist" style="padding:0" id="listaGrupo">${g.ids.map(id => {
              const s = porId(id);
              return `<button class="gruporow" data-id="${id}"><span class="ic2">${H.ICONS.vida}</span><span class="gr-nome">${s ? s.nome : id}</span>${H.ICONS.chevron}</button>`;
            }).join("")}</div></div>
            <div id="detGrupo"></div>
          </div></div>
        </div>
      `;
      const det = th.querySelector("#detGrupo");
      th.querySelectorAll(".gruporow").forEach(r => r.addEventListener("click", () => {
        const s = porId(r.dataset.id);
        if (!s) return;
        det.innerHTML = `<div class="card">
          <div class="card-head"><span>${s.nome}</span></div>
          <p class="lead">${s.resumo}.</p>
          ${H.D.viagem && s.id === "viagens" ? `<p class="lead">Proxima viagem: <b>${H.D.viagem.origem} → ${H.D.viagem.destino}</b> em ${H.D.viagem.dias_faltando} dias.</p>` : ""}
          ${H.chartMini(s.id)}
          <div class="exemplo">Sequencia ilustrativa da semana (exemplo)</div>
        </div>`;
      }));
    }));
  });
})();
