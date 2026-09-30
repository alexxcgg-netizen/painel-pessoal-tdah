// static/js/secoes/vida/habitos.js - Secao vida > habitos (HTML: templates/secoes/vida/habitos.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo vida.js 698-790.
// Fase 7 (V3-organizacao): botao "Novo hábito" abre o formulario num bottom-sheet
// (contrato: docs/agentes/fase7-visual.md). Usa window.abrirBottomSheet/fecharBottomSheet
// (faixa V0d) quando existir; se a faixa ainda nao chegou nesta branch, cai no fallback de
// so alternar o atributo hidden do painel.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

function abrirPainelHabito() {
  const sheet = $("#habito-sheet");
  if (typeof window.abrirBottomSheet === "function") window.abrirBottomSheet(sheet);
  else sheet.hidden = false;
}

function fecharPainelHabito() {
  const sheet = $("#habito-sheet");
  if (typeof window.fecharBottomSheet === "function") window.fecharBottomSheet(sheet);
  else sheet.hidden = true;
}

$("#habito-abrir-btn").addEventListener("click", abrirPainelHabito);
$("#habito-cancelar-btn").addEventListener("click", () => {
  $("#habito-form").reset();
  atualizarCamposFrequenciaHabito();
  fecharPainelHabito();
});

function atualizarCamposFrequenciaHabito() {
  const tipo = $("#habito-frequencia-tipo").value;
  $("#habito-dias-semana-campo").hidden = tipo !== "dias_semana";
  $("#habito-vezes-semana").hidden = tipo !== "n_vezes_semana";
}
$("#habito-frequencia-tipo").addEventListener("change", atualizarCamposFrequenciaHabito);

function renderHabitoSemana(ultimos7) {
  const wrap = criarEl("div", "habito-semana");
  ultimos7.forEach((dia) => {
    const classe = ["habito-circulo", dia.feito ? "feito" : "", dia.hoje ? "hoje" : ""].filter(Boolean).join(" ");
    const c = criarEl("span", classe, dia.letra);
    c.title = fmtDataBr(dia.data);
    wrap.appendChild(c);
  });
  return wrap;
}

async function loadHabitos() {
  const data = await apiFetch("/api/habitos");
  if (!data) return;
  const lista = $("#lista-habitos");
  lista.innerHTML = "";
  $("#habitos-vazio").hidden = data.habitos.length > 0;
  data.habitos.forEach((h) => {
    const detalhes = [h.meta, h.horario ? `lembrete ${h.horario}` : null].filter(Boolean);
    const li = itemSimples(
      h.nome,
      detalhes,
      [
        // Vel A2b: marcar habito otimista - texto do botao e o circulo de
        // "hoje" mudam na hora do toque, sem esperar o POST; desfaz em erro
        // (mostrarErro ja vem do apiFetch/jsonPost).
        (li) => {
          const btn = criarEl("button", "btn-com-icone");
          const marcarPendente = () => {
            btn.className = "primario btn-com-icone";
            btn.innerHTML = `${ICONE_CHECK}marcar hoje`;
          };
          const marcarFeito = () => {
            btn.className = "btn-com-icone";
            btn.textContent = "feito hoje";
          };
          (h.feito_hoje ? marcarFeito : marcarPendente)();
          btn.addEventListener("click", async () => {
            if (btn.disabled) return; // evita duplo toque
            btn.disabled = true;
            const circuloHoje = li.querySelector(".habito-circulo.hoje");
            const tinhaFeito = Boolean(circuloHoje && circuloHoje.classList.contains("feito"));
            const estadoAnterior = h.feito_hoje;
            h.feito_hoje = true;
            marcarFeito();
            if (circuloHoje) {
              circuloHoje.classList.add("feito");
              animarCheck(circuloHoje);
            }

            const r = await jsonPost(`/api/habitos/${h.id}/marcar`);
            btn.disabled = false;
            if (!r) {
              h.feito_hoje = estadoAnterior;
              (estadoAnterior ? marcarFeito : marcarPendente)();
              if (circuloHoje && !tinhaFeito) circuloHoje.classList.remove("feito");
            }
          });
          return btn;
        },
        (el) => botaoApagar(`/api/habitos/${h.id}`, el),
      ],
      h.passou_batido ? "item-atencao" : ""
    );
    li.classList.add("lista-item");
    li.querySelectorAll(".item-quando").forEach((el) => el.classList.add("chip", "chip--compacto"));
    li.appendChild(renderHabitoSemana(h.ultimos_7));
    li.dataset.entidade = "habito"; // destino do link de card (Fase 6, US-E7)
    li.dataset.id = h.id;
    lista.appendChild(li);
  });
}

ligarForm(
  "#habito-form",
  "#habito-btn",
  "Salvar hábito",
  () => {
    const nome = $("#habito-nome").value.trim();
    if (!nome) return null;
    const frequencia_tipo = $("#habito-frequencia-tipo").value;
    const corpo = {
      nome,
      meta: $("#habito-meta").value.trim() || null,
      frequencia_tipo,
      horario: $("#habito-horario").value || null,
    };
    if (frequencia_tipo === "dias_semana") {
      corpo.dias_semana = Array.from($("#habito-dias-semana-campo").querySelectorAll("input:checked")).map((c) => Number(c.value));
      if (!corpo.dias_semana.length) {
        mostrarErro("Marca pelo menos um dia da semana.");
        return null;
      }
    } else if (frequencia_tipo === "n_vezes_semana") {
      corpo.vezes_por_semana = Number($("#habito-vezes-semana").value);
      if (!(corpo.vezes_por_semana >= 1 && corpo.vezes_por_semana <= 7)) {
        mostrarErro("Informa quantas vezes por semana (1 a 7).");
        return null;
      }
    }
    return corpo;
  },
  "/api/habitos",
  () => {
    $("#habito-dias-semana-campo")
      .querySelectorAll("input")
      .forEach((c) => (c.checked = false));
    atualizarCamposFrequenciaHabito();
    fecharPainelHabito();
    loadHabitos();
  }
);

// ---- Fase 6 (US-E13): Projetos (generico - Viagens NAO migra pra ca, ver
// loadViagens abaixo; o card de viagem so reaproveita esse mesmo formato
// visual via /api/viagens/<id>/como-projeto quando precisar) ----
