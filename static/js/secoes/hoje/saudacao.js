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
// R2: a mesma ação mora em dois botões - "Ouvir resumo da manha" (#resumo-manha-btn, tela
// Painel) e "Ouvir" do hero do Início (#inicio-ouvir). Uma função só, cada botão com o
// próprio rótulo de volta (setBotaoCarregando restaura o HTML original do botão).
async function ouvirResumoDaManha(btn) {
  // falando de novo (mesmo botao) -> cancela, mesmo comportamento de
  // metar-ouvir/taf-ouvir - nunca busca de novo enquanto ja esta falando.
  if (vozTocando()) {
    pararVoz();
    return;
  }
  desbloquearAudioPremium(); // ainda dentro do toque (iOS) - antes de qualquer await
  setBotaoCarregando(btn, true, "Preparando...");
  // Voz premium: frase curta (/api/voz/frase) -> falarPremium (cai na voz do
  // iPhone sozinha). Se a rota nova falhar, o caminho antigo de sempre.
  let frase = await apiFetch("/api/voz/frase?momento=manha");
  if (!frase || !frase.texto) frase = await apiFetch("/api/resumo-manha");
  setBotaoCarregando(btn, false, "Ouvir");
  if (!frase || !frase.texto) return;
  falarPremium(btn, frase.texto);
}

["#resumo-manha-btn", "#inicio-ouvir"].forEach((seletor) => {
  const btn = $(seletor);
  if (!btn) return;
  if (!("speechSynthesis" in window)) {
    btn.hidden = true;
    return;
  }
  btn.addEventListener("click", () => ouvirResumoDaManha(btn));
});

// ---- R2 (reformulação, etapa 2): Início ----
// Hero (saudação + resumo de 1 linha + chip de estado), "Agora", 3 números e subtítulos do
// "Acesso rápido" (e de algumas linhas do Mais) - tudo de UMA ida a GET /api/inicio
// (rotas/inicio.py: sem IA, sem rede). Recarrega ao voltar pro Início (init.js, com o cache
// curto de abaPrecisaCarregar) e depois de concluir pelo "Agora".

function saudacaoDaHora(hora) {
  return hora < 5 ? "Boa noite" : hora < 12 ? "Bom dia" : hora < 18 ? "Boa tarde" : "Boa noite";
}

function mostrarSaudacaoInicio() {
  const el = document.getElementById("inicio-saudacao");
  if (!el) return;
  const nome = (typeof NOME_USUARIO === "string" && NOME_USUARIO.trim().split(" ")[0]) || "";
  el.textContent = nome ? `${saudacaoDaHora(new Date().getHours())}, ${nome}!` : `${saudacaoDaHora(new Date().getHours())}!`;
}

// "R$ 42" / "R$ 1,2 mil": cabe no tile de 1/3 da largura (o fmtMoeda completo tem centavos).
function fmtMoedaCurta(v) {
  const n = Number(v) || 0;
  if (Math.abs(n) >= 10000) return `R$ ${(n / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 0 })} mil`;
  if (Math.abs(n) >= 1000) return `R$ ${(n / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mil`;
  return `R$ ${Math.round(n).toLocaleString("pt-BR")}`;
}

// "2026-10-03" -> "sáb, 3/10" (hoje/amanhã por extenso).
function fmtDiaCurto(iso) {
  if (!iso) return "";
  const [a, m, d] = iso.split("-").map(Number);
  const dia = new Date(a, m - 1, d);
  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);
  const dif = Math.round((dia - hoje) / 86400000);
  if (dif === 0) return "hoje";
  if (dif === 1) return "amanhã";
  const sem = dia.toLocaleDateString("pt-BR", { weekday: "short" }).replace(".", "");
  return `${sem}, ${d}/${m}`;
}

function horaFalada(hhmm) {
  if (!hhmm) return "";
  const [h, m] = hhmm.split(":").map(Number);
  return m ? `${h}h${String(m).padStart(2, "0")}` : `${h}h`;
}

function plural(n, um, varios) {
  return `${n} ${n === 1 ? um : varios}`;
}

// Subtítulo com dado real; sem dado, volta pro texto fixo do HTML (guardado no 1º uso).
function definirSub(id, texto) {
  const el = document.getElementById(id);
  if (!el) return;
  if (el.dataset.fixo === undefined) el.dataset.fixo = el.textContent;
  el.textContent = texto || el.dataset.fixo;
}

let _inicioAgoraAtual = null;

function renderAgoraInicio(agora) {
  const card = document.getElementById("inicio-agora");
  const vazio = document.getElementById("inicio-agora-vazio");
  if (!card || !vazio) return;
  _inicioAgoraAtual = agora || null;
  if (!agora) {
    card.hidden = true;
    vazio.hidden = false;
    return;
  }
  const hora = document.getElementById("inicio-agora-hora");
  hora.textContent = agora.hora ? agora.hora.replace(/^0/, "") : "Hoje";
  hora.classList.toggle("sem-hora", !agora.hora);
  card.classList.toggle("atrasada", Boolean(agora.atrasada));
  document.getElementById("inicio-agora-titulo").textContent = agora.titulo;
  document.getElementById("inicio-agora-sub").textContent = agora.subtitulo || "";
  const ok = document.getElementById("inicio-agora-ok");
  ok.disabled = false;
  ok.setAttribute("aria-label", `Concluir: ${agora.titulo}`);
  card.classList.remove("saindo");
  card.hidden = false;
  vazio.hidden = true;
}

function renderInicio(d) {
  const resumo = document.getElementById("inicio-resumo");
  if (resumo) resumo.textContent = d.resumo;
  const chip = document.getElementById("inicio-chip");
  if (chip) {
    const atrasadas = Number(d.atrasadas) || 0;
    chip.classList.toggle("alerta", atrasadas > 0);
    chip.classList.toggle("ok", atrasadas === 0);
    document.getElementById("inicio-chip-texto").textContent =
      atrasadas > 0 ? plural(atrasadas, "atrasada", "atrasadas") : "Tudo em dia";
    const uso = chip.querySelector("svg");
    if (uso) {
      uso.innerHTML =
        atrasadas > 0
          ? '<path d="M12 4 3 19.5h18z"/><path d="M12 10v4.5M12 17.2v.1"/>'
          : '<circle cx="12" cy="12" r="9"/><path d="m8 12.5 3 3 5-6"/>';
    }
    chip.hidden = false;
  }
  renderAgoraInicio(d.agora);

  const th = d.tarefas_hoje || { feitas: 0, total: 0 };
  const elT = document.getElementById("inicio-num-tarefas");
  if (elT) animarNumero(elT, th.feitas, (v) => `${Math.round(v)}/${th.total}`);
  const elG = document.getElementById("inicio-num-gasto");
  if (elG) {
    if (d.gasto_hoje === null || d.gasto_hoje === undefined) elG.textContent = "—";
    else animarNumero(elG, d.gasto_hoje, fmtMoedaCurta);
  }
  const elA = document.getElementById("inicio-num-agua");
  if (elA) {
    if (!d.agua) elA.textContent = "—";
    else animarNumero(elA, d.agua.copos, (v) => `${Math.round(v)}/${d.agua.meta}`);
  }

  // Acesso rápido (sem dado barato -> texto fixo do HTML)
  const pend = Number(d.tarefas_pendentes) || 0;
  const pendHoje = th.total - th.feitas;
  definirSub(
    "inicio-sub-tarefas",
    pendHoje > 0 ? `${pendHoje} pra hoje` : pend > 0 ? plural(pend, "pendente", "pendentes") : "Tudo feito"
  );
  definirSub(
    "inicio-sub-agenda",
    d.compromissos_hoje > 0 ? plural(d.compromissos_hoje, "compromisso", "compromissos") : ""
  );
  definirSub("inicio-sub-financas", d.gasto_mes > 0 ? `${fmtMoedaCurta(d.gasto_mes)} no mês` : "");
  const hab = d.habitos || { feitos: 0, total: 0 };
  const txtHab = hab.total > 0 ? `${hab.feitos} de ${hab.total} feitos` : "";
  definirSub("inicio-sub-habitos", txtHab);
  const txtRemedio = d.proximo_remedio ? `Remédio às ${horaFalada(d.proximo_remedio)}` : "";
  definirSub("inicio-sub-saude", txtRemedio);
  const voo = d.proximo_voo;
  const txtVoo = voo ? `Voo ${fmtDiaCurto(voo.data)}${voo.destino ? ` · ${voo.destino}` : ""}` : "";
  definirSub("inicio-sub-aviacao", txtVoo);
  const txtNotas = d.notas > 0 ? plural(d.notas, "nota", "notas") : "";
  definirSub("inicio-sub-notas", txtNotas);

  // Tela Mais: mesmos dados, mesmas regras (sem dado -> descrição fixa)
  definirSub("mais-sub-habitos", hab.total > 0 ? `${hab.feitos} de ${hab.total} hoje` : "");
  definirSub("mais-sub-notas", txtNotas);
  definirSub("mais-sub-aviacao", voo ? `Próximo voo: ${fmtDiaCurto(voo.data)}${voo.destino ? ` · ${voo.destino}` : ""}` : "");
  definirSub("mais-sub-saude", txtRemedio);
  definirSub(
    "mais-sub-painel",
    th.total > 0 ? `${th.feitas} de ${th.total} tarefas de hoje feitas` : ""
  );
}

async function loadInicio() {
  mostrarSaudacaoInicio();
  const d = await apiFetch("/api/inicio");
  if (!d) {
    const resumo = document.getElementById("inicio-resumo");
    if (resumo && resumo.textContent === "Carregando o seu dia…") resumo.textContent = "Não consegui carregar o resumo agora.";
    ["inicio-num-tarefas", "inicio-num-gasto", "inicio-num-agua"].forEach((id) => {
      const el = document.getElementById(id);
      if (el && el.textContent === "–") el.textContent = "—";
    });
    return;
  }
  renderInicio(d);
}

// "Agora" › concluir: otimista como em Tarefas (Vel A2b) - marca, anima e sai na hora do
// toque; a gravação vai por trás e, se falhar, o card volta (mostrarErro vem do apiFetch).
(function ligarAgoraInicio() {
  const ok = document.getElementById("inicio-agora-ok");
  const card = document.getElementById("inicio-agora");
  if (!ok || !card) return;
  ok.addEventListener("click", async () => {
    const item = _inicioAgoraAtual;
    if (ok.disabled || !item || !item.id) return;
    ok.disabled = true;
    if (typeof explodirConcluido === "function") explodirConcluido(ok);
    if (typeof vibrar === "function") vibrar(30);
    if (typeof tocarSomConcluido === "function") tocarSomConcluido();
    card.classList.add("saindo");
    const rota =
      item.origem === "habito" ? `/api/habitos/${item.id}/marcar` : `/api/tasks/${item.id}/complete`;
    const r = await apiFetch(rota, { method: "POST" });
    if (r) {
      loadInicio();
      if (typeof loadSummary === "function" && !$("#tab-painel").hidden) loadSummary();
      if (typeof loadStreak === "function") loadStreak();
      if (typeof window.loadVisaoDiaHoje === "function") window.loadVisaoDiaHoje();
      if (typeof loadEssencial === "function") loadEssencial();
    } else {
      card.classList.remove("saindo");
      ok.disabled = false;
    }
  });
})();

// "Planejar o dia" (estado vazio do "Agora"): abre a IA com a sugestão já no campo - quem
// envia é o Alex (nenhuma chamada de IA sai sozinha daqui).
(function ligarPlanejarDia() {
  const btn = document.getElementById("inicio-planejar");
  if (!btn) return;
  btn.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "instant" });
    showTab("assistente");
    const input = document.getElementById("chat-input");
    if (input) {
      input.value = "Me ajuda a planejar o dia";
      try {
        input.focus({ preventScroll: true });
      } catch (e) {
        input.focus();
      }
    }
  });
})();
