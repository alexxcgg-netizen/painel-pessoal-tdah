// static/js/secoes/hoje/saudacao.js - Secao hoje > saudacao (HTML: templates/secoes/hoje/saudacao.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 10-23, app.js 762-856, app.js 3876-3901.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

function mostrarSaudacao() {
  const agora = new Date();
  const hora = agora.getHours();
  const saudacao = hora < 5 ? "Boa noite" : hora < 12 ? "Bom dia" : hora < 18 ? "Boa tarde" : "Boa noite";
  $("#saudacao-texto").textContent = `${saudacao}, ${NOME_USUARIO.split(" ")[0]}`;
  const dataFormatada = agora.toLocaleDateString("pt-BR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
  $("#saudacao-data").textContent = dataFormatada.charAt(0).toUpperCase() + dataFormatada.slice(1);
  $("#avatar-usuario").textContent = NOME_USUARIO.charAt(0).toUpperCase();
}

async function loadStreak() {
  const data = await apiFetch("/api/streak");
  const chip = $("#streak-chip");
  if (!data || data.dias < 1) {
    chip.hidden = true;
    return;
  }
  $("#streak-texto").textContent =
    data.dias === 1 ? "1 dia seguido usando o painel" : `${data.dias} dias seguidos usando o painel`;
  chip.hidden = false;
}

let climaUltimoLoad = 0;

async function loadClimaHoje() {
  climaUltimoLoad = Date.now();
  const data = await apiFetch("/api/clima/hoje");
  const chip = $("#clima-chip");
  if (!data || !data.configurado || data.erro) {
    chip.hidden = true;
    return;
  }
  chip.classList.toggle("alerta", Boolean(data.alerta));
  const prefixo = data.chovendo_agora ? "Chovendo agora - " : "";
  $("#clima-texto").textContent = `${prefixo}${data.cidade}: ${data.texto}`;
  chip.hidden = false;
}

// a previsao so e buscada de novo (a) a cada 20min, pra acompanhar a hora
// "agora" avancando sem precisar recarregar a pagina, e (b) quando volta
// pra aba depois de um tempo longe - assim um PWA deixado aberto o dia
// inteiro nao fica mostrando a janela de chuva calculada de manha
setInterval(loadClimaHoje, 20 * 60 * 1000);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && Date.now() - climaUltimoLoad > 5 * 60 * 1000) {
    loadClimaHoje();
  }
  if (document.visibilityState === "visible") loadUberPendentes();
});

async function loadUberPendentes() {
  const data = await apiFetch("/api/uber/pedidos");
  const box = $("#uber-pendentes");
  box.innerHTML = "";
  if (!data || data.length === 0) return;

  data.forEach((p) => {
    const card = document.createElement("div");
    card.className = "uber-pendente-card";

    const titulo = document.createElement("p");
    titulo.className = "uber-pendente-titulo";
    titulo.textContent = `Uber pra ${p.destino}`;
    card.appendChild(titulo);

    const preco = document.createElement("p");
    preco.className = "uber-pendente-preco";
    preco.textContent = p.preco_texto || "preço não disponível";
    card.appendChild(preco);

    const acoes = document.createElement("div");
    acoes.className = "uber-pendente-acoes";

    const btnConfirmar = document.createElement("button");
    btnConfirmar.className = "uber-btn-confirmar";
    btnConfirmar.textContent = "Confirmar";
    btnConfirmar.addEventListener("click", async () => {
      btnConfirmar.disabled = true;
      btnCancelar.disabled = true;
      const r = await apiFetch(`/api/uber/pedidos/${p.id}/confirmar`, { method: "POST" });
      if (r && r.ok) {
        loadUberPendentes();
      } else {
        btnConfirmar.disabled = false;
        btnCancelar.disabled = false;
      }
    });

    const btnCancelar = document.createElement("button");
    btnCancelar.className = "uber-btn-cancelar";
    btnCancelar.textContent = "Cancelar";
    btnCancelar.addEventListener("click", async () => {
      btnConfirmar.disabled = true;
      btnCancelar.disabled = true;
      await apiFetch(`/api/uber/pedidos/${p.id}/cancelar`, { method: "POST" });
      loadUberPendentes();
    });

    acoes.appendChild(btnConfirmar);
    acoes.appendChild(btnCancelar);
    card.appendChild(acoes);
    box.appendChild(card);
  });
}

// Resumo falado da manha (US-C11) - texto vem pronto do servidor
// (/api/resumo-manha, agenda + gasto de ontem + pendentes), o TTS em si
// reaproveita o mesmo falarTexto/SpeechSynthesis ja usado no METAR/TAF e no
// chat, nada novo do lado do audio.
const resumoManhaBtn = $("#resumo-manha-btn");
if (resumoManhaBtn) {
  if (!("speechSynthesis" in window)) {
    resumoManhaBtn.hidden = true;
  } else {
    resumoManhaBtn.addEventListener("click", async () => {
      // falando de novo (mesmo botao) -> cancela, mesmo comportamento de
      // metar-ouvir/taf-ouvir - nunca busca de novo enquanto ja esta falando.
      if (window.speechSynthesis.speaking) {
        window.speechSynthesis.cancel();
        resumoManhaBtn.classList.remove("falando");
        return;
      }
      setBotaoCarregando(resumoManhaBtn, true, "Preparando...");
      const data = await apiFetch("/api/resumo-manha");
      setBotaoCarregando(resumoManhaBtn, false, "Ouvir resumo da manha");
      if (!data) return;
      falarTexto(resumoManhaBtn, data.texto);
    });
  }
}
