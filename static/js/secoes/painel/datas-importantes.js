// static/js/secoes/painel/datas-importantes.js - Secao painel > datas-importantes (HTML: templates/secoes/painel/datas-importantes.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 1630-1758.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

async function loadLembretes() {
  const lembretes = await apiFetch("/api/lembretes");
  if (!lembretes) return;

  const list = $("#lista-lembretes");
  list.innerHTML = "";
  $("#lembretes-vazio").hidden = lembretes.length > 0;

  // Fase 6 (US-F7): o mais perto de vencer primeiro - o backend ja devolve
  // dias_restantes calculado (proxima_ocorrencia, inclusive pra recorrente),
  // o /api/lembretes so nao ordena por ele (a query SQL ordena por "data"
  // crua, que pra um lembrete recorrente e o ano de CRIACAO, nao o proximo
  // aniversario). Ordenar aqui evita duplicar aquele calculo so pra
  // reordenar no servidor.
  const ordenados = [...lembretes].sort((a, b) => a.dias_restantes - b.dias_restantes);

  ordenados.forEach((l) => {
    const li = document.createElement("li");
    li.className = "item";
    li.dataset.entidade = "lembrete"; // destino do link de card (Fase 6)
    li.dataset.id = l.id;

    const linha = document.createElement("div");
    linha.className = "item-linha";

    const tituloWrap = document.createElement("div");
    const titulo = document.createElement("span");
    titulo.className = "item-titulo";
    titulo.textContent = l.titulo;
    tituloWrap.appendChild(titulo);
    const quando = document.createElement("span");
    quando.className = "item-quando";
    // proxima_ocorrencia (calculada no backend) em vez de l.data crua - pra
    // um lembrete recorrente mostrar o PROXIMO aniversario da data, nao o
    // ano em que ele foi cadastrado originalmente.
    const dataMostrada = l.proxima_ocorrencia || l.data;
    quando.textContent = l.recorrente ? `${fmtDataBr(dataMostrada)} - todo ano` : fmtDataBr(dataMostrada);
    tituloWrap.appendChild(quando);

    if (typeof l.dias_restantes === "number") {
      const contagem = document.createElement("span");
      const urgente = l.dias_restantes <= 7;
      const vencido = l.dias_restantes < 0;
      // Fase 6 (US-F7): virou selo (pill), nao so texto colorido solto -
      // 2 niveis: "vencendo" (ate 7 dias, cor da propria secao - a mesma
      // janela em que o push avisa) e "vencido" (ja passou, ai sim usa
      // --danger, unico caso aqui que e mesmo um problema, nao so prazo
      // apertado).
      contagem.className = urgente
        ? `item-quando lembrete-contagem-urgente${vencido ? " lembrete-contagem-vencido" : ""}`
        : "item-quando";
      contagem.textContent =
        l.dias_restantes < 0
          ? `venceu ha ${Math.abs(l.dias_restantes)} dia(s)`
          : l.dias_restantes === 0
          ? "e hoje"
          : l.dias_restantes === 1
          ? "e amanha"
          : `faltam ${l.dias_restantes} dias`;
      tituloWrap.appendChild(contagem);
    }
    if (l.sugestao && typeof l.dias_restantes === "number" && l.dias_restantes <= 7) {
      const sugestao = document.createElement("span");
      sugestao.className = "item-quando lembrete-sugestao";
      sugestao.textContent = l.sugestao;
      tituloWrap.appendChild(sugestao);
    }
    linha.appendChild(tituloWrap);

    const acoes = document.createElement("div");
    acoes.className = "item-acoes";
    const apagarBtn = document.createElement("button");
    apagarBtn.className = "btn-com-icone";
    apagarBtn.innerHTML = `${ICONE_TRASH}Apagar`;
    apagarBtn.addEventListener("click", async () => {
      apagarBtn.disabled = true;
      const ok = await apiFetch(`/api/lembretes/${l.id}`, { method: "DELETE" });
      if (ok) {
        li.classList.add("saindo");
        setTimeout(() => li.remove(), 250);
      } else {
        apagarBtn.disabled = false;
      }
    });
    acoes.appendChild(apagarBtn);
    linha.appendChild(acoes);

    li.appendChild(linha);
    list.appendChild(li);
  });
}

$("#lembrete-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#lembrete-btn");
  const tituloInput = $("#lembrete-titulo");
  const dataInput = $("#lembrete-data");
  const titulo = tituloInput.value.trim();
  // Fase 6 (US-F7): input virou type="date" (seletor nativo) - o value ja
  // vem em AAAA-MM-DD direto do navegador, sem precisar da mascara
  // dd/mm/aaaa (mascaraDataParaIso continua existindo pra #voo-data, que
  // nao mudou nesta historia).
  const dataIso = dataInput.value;
  if (!titulo || !dataIso) {
    mostrarErro("Confere o titulo e a data de vencimento.");
    return;
  }

  setBotaoCarregando(btn, true, "salvando...");
  const data = await apiFetch("/api/lembretes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      titulo,
      data: dataIso,
      recorrente: $("#lembrete-recorrente").checked,
    }),
  });
  setBotaoCarregando(btn, false, "Adicionar");
  if (!data) return;

  tituloInput.value = "";
  dataInput.value = "";
  $("#lembrete-recorrente").checked = false;
  pulsarSucesso(tituloInput);
  loadLembretes();
  loadStreak();
});
