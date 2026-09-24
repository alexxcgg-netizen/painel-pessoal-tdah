// static/js/secoes/painel/medicamentos.js - Secao painel > medicamentos (HTML: templates/secoes/painel/medicamentos.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 1759-1872.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

// Fase 6 (US-F7): "todo dia as HH:MM" sozinho obriga a fazer conta de
// cabeca pra saber se e daqui a pouco ou so a noite - devolve quanto falta
// pra proxima dose (ou "ha Xh, foi hoje" se ja passou o horario de hoje,
// ja que o medicamento e diario e a proxima dose de verdade so vem amanha
// nesse caso). So calculo de apresentacao (relogio do navegador), nao mexe
// em nenhum aviso/push real (isso continua 100% no backend).
function proximaDoseTexto(horario) {
  const partes = String(horario || "").match(/^(\d{2}):(\d{2})/);
  if (!partes) return null;
  const alvo = new Date();
  alvo.setHours(Number(partes[1]), Number(partes[2]), 0, 0);
  const agora = new Date();
  let diffMin = Math.round((alvo - agora) / 60000);
  if (diffMin < -1) return `foi ha ${formatarDuracaoMin(-diffMin)}`;
  if (diffMin <= 1) return "agora";
  return `em ${formatarDuracaoMin(diffMin)}`;
}

function formatarDuracaoMin(min) {
  if (min < 60) return `${min}min`;
  const horas = Math.floor(min / 60);
  const resto = min % 60;
  return resto ? `${horas}h${resto}min` : `${horas}h`;
}

async function loadMedicamentos() {
  const medicamentos = await apiFetch("/api/medicamentos");
  if (!medicamentos) return;

  const list = $("#lista-medicamentos");
  list.innerHTML = "";
  $("#medicamentos-vazio").hidden = medicamentos.length > 0;

  medicamentos.forEach((m) => {
    const li = document.createElement("li");
    li.className = "item";

    const linha = document.createElement("div");
    linha.className = "item-linha";

    const tituloWrap = document.createElement("div");
    const titulo = document.createElement("span");
    titulo.className = "item-titulo";
    titulo.textContent = m.dosagem ? `${m.nome} - ${m.dosagem}` : m.nome;
    tituloWrap.appendChild(titulo);
    const quando = document.createElement("span");
    quando.className = "item-quando";
    quando.textContent = `todo dia as ${m.horario}`;
    tituloWrap.appendChild(quando);
    const proxima = proximaDoseTexto(m.horario);
    if (proxima) {
      const proximaEl = document.createElement("span");
      proximaEl.className = "item-quando medicamento-proxima-dose";
      proximaEl.textContent = proxima;
      tituloWrap.appendChild(proximaEl);
    }
    linha.appendChild(tituloWrap);

    const acoes = document.createElement("div");
    acoes.className = "item-acoes";
    const apagarBtn = document.createElement("button");
    apagarBtn.className = "btn-com-icone";
    apagarBtn.innerHTML = `${ICONE_TRASH}Apagar`;
    apagarBtn.addEventListener("click", async () => {
      apagarBtn.disabled = true;
      const ok = await apiFetch(`/api/medicamentos/${m.id}`, { method: "DELETE" });
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

$("#medicamento-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#medicamento-btn");
  const nomeInput = $("#medicamento-nome");
  const dosagemInput = $("#medicamento-dosagem");
  const horarioInput = $("#medicamento-horario");
  const nome = nomeInput.value.trim();
  const horario = horarioInput.value.trim();
  if (!nome || !horario) {
    mostrarErro("Confere o nome e o horario do remedio.");
    return;
  }

  setBotaoCarregando(btn, true, "salvando...");
  const data = await apiFetch("/api/medicamentos", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      nome,
      dosagem: dosagemInput.value.trim(),
      horario,
    }),
  });
  setBotaoCarregando(btn, false, "Adicionar");
  if (!data) return;

  nomeInput.value = "";
  dosagemInput.value = "";
  horarioInput.value = "";
  pulsarSucesso(nomeInput);
  loadMedicamentos();
});
