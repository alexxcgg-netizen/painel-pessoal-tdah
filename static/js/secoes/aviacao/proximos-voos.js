// static/js/secoes/aviacao/proximos-voos.js - Secao aviacao > proximos-voos (HTML: templates/secoes/aviacao/proximos-voos.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 3526-3644.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

// US-F15: icone de status (agendado vs realizado) - so decoracao visual,
// a logica de "o que e realizado" continua 100% em voos.py (v.horas != null),
// nunca reimplementada aqui.
function criarIconeStatusVoo(realizado) {
  const wrap = document.createElement("span");
  wrap.className = "voo-status-icone" + (realizado ? " realizado" : " agendado");
  wrap.title = realizado ? "Voo realizado" : "Voo agendado";
  wrap.innerHTML = realizado
    ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>'
    : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>';
  return wrap;
}

function criarItemVoo(v) {
  const li = document.createElement("li");
  li.className = "item";

  const linha = document.createElement("div");
  linha.className = "item-linha";

  const tituloWrap = document.createElement("div");
  const titulo = document.createElement("span");
  titulo.className = "item-titulo item-titulo-com-icone";
  titulo.appendChild(criarIconeStatusVoo(v.horas != null));
  titulo.appendChild(document.createTextNode(v.origem ? `${v.origem} → ${v.destino}` : v.destino));
  tituloWrap.appendChild(titulo);

  const quando = document.createElement("span");
  quando.className = "item-quando";
  let quandoTxt = fmtDataBr(v.data);
  if (v.hora) quandoTxt += ` as ${v.hora}`;
  if (v.horas) quandoTxt += ` - ${fmtHoras(v.horas)} voadas`;
  quando.textContent = quandoTxt;
  tituloWrap.appendChild(quando);

  const saidaResultado = document.createElement("p");
  saidaResultado.className = "resumo-texto voo-saida-resultado";
  saidaResultado.hidden = true;
  tituloWrap.appendChild(saidaResultado);

  if (v.clima) {
    const climaEl = document.createElement("span");
    climaEl.className = "voo-clima" + (v.clima.alerta_chuva ? " alerta" : "");
    climaEl.textContent =
      `${Math.round(v.clima.chuva_pct)}% chance de chuva, ` +
      `${Math.round(v.clima.temp_min)}–${Math.round(v.clima.temp_max)}°C em ${v.clima.cidade}`;
    tituloWrap.appendChild(climaEl);
  }

  linha.appendChild(tituloWrap);

  const acoes = document.createElement("div");
  acoes.className = "item-acoes";

  if (v.clima) {
    const windyBtn = document.createElement("a");
    windyBtn.className = "btn-com-icone";
    windyBtn.href = `https://www.windy.com/?cbase,${v.clima.lat},${v.clima.lon},9`;
    windyBtn.target = "_blank";
    windyBtn.rel = "noopener";
    windyBtn.textContent = "Windy";
    acoes.appendChild(windyBtn);
  }

  if (v.hora) {
    const sairBtn = document.createElement("button");
    sairBtn.className = "btn-com-icone";
    sairBtn.textContent = "Quando sair?";
    sairBtn.addEventListener("click", async () => {
      setBotaoCarregando(sairBtn, true, "calculando...");
      const data = await apiFetch("/api/viagem/quando-sair", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          destino: v.destino,
          chegar_ate: `${v.data}T${v.hora}`,
          margem_minutos: 60,
        }),
      });
      setBotaoCarregando(sairBtn, false, "Quando sair?");
      if (!data) return;
      const sairEm = new Date(data.sair_ate);
      const horaTxt = sairEm.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
      saidaResultado.textContent =
        `Saia até as ${horaTxt} (viagem de ${data.duracao_minutos}min, ${data.distancia_km}km, ` +
        `com ${data.margem_minutos}min de margem pro voo)`;
      saidaResultado.hidden = false;
    });
    acoes.appendChild(sairBtn);
  }

  const apagarBtn = document.createElement("button");
  apagarBtn.className = "btn-com-icone";
  apagarBtn.innerHTML = `${ICONE_TRASH}Apagar`;
  apagarBtn.addEventListener("click", async () => {
    apagarBtn.disabled = true;
    const ok = await apiFetch(`/api/voos/${v.id}`, { method: "DELETE" });
    if (ok) {
      li.classList.add("saindo");
      setTimeout(() => loadVoosResumo(), 220);
    } else {
      apagarBtn.disabled = false;
    }
  });
  acoes.appendChild(apagarBtn);

  linha.appendChild(acoes);
  li.appendChild(linha);

  if (v.observacao) {
    const diario = document.createElement("p");
    diario.className = "voo-diario";
    diario.textContent = v.observacao;
    li.appendChild(diario);
  }

  return li;
}
