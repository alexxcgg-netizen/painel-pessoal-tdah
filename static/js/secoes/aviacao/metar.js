// static/js/secoes/aviacao/metar.js - Secao aviacao > metar (HTML: templates/secoes/aviacao/metar.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 3746-3851, app.js 3868-3875, app.js 3902-3937.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

// US-F15: rotulo/cor por categoria VFR/MVFR/IFR/LIFR - MESMAS cores padrao
// de carta aeronautica (verde/azul/vermelho/magenta), nunca inventadas.
// `metar.categoria_voo` (Python) e a UNICA fonte da classificacao em si -
// isso aqui so escolhe rotulo/classe CSS pro que o servidor ja decidiu.
const CATEGORIA_VOO_INFO = {
  VFR: { rotulo: "VFR", classe: "cat-vfr" },
  MVFR: { rotulo: "MVFR", classe: "cat-mvfr" },
  IFR: { rotulo: "IFR", classe: "cat-ifr" },
  LIFR: { rotulo: "LIFR", classe: "cat-lifr" },
};

function criarChipCategoriaVoo(categoria) {
  const info = CATEGORIA_VOO_INFO[categoria];
  if (!info) return null;
  const chip = document.createElement("span");
  chip.className = `metar-chip-categoria ${info.classe}`;
  chip.textContent = info.rotulo;
  chip.title = "Classificacao padrao FAA/AIM de teto e visibilidade - confira sempre antes de voar.";
  return chip;
}

// Seta de vento (SVG) apontando na direcao de onde o vento vem (convencao
// de manga de vento) - rotacionada pelo grau decodificado. VRB (variavel)
// mostra um icone circular em vez de seta (nao ha uma direcao pra apontar).
function criarIconeVento(vento) {
  const wrap = document.createElement("span");
  wrap.className = "metar-vento-icone";
  if (!vento || vento.variavel) {
    wrap.innerHTML =
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="7"/><path d="M12 8v8M8 12h8"/></svg>';
    return wrap;
  }
  wrap.innerHTML =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v14"/><path d="M7 8l5-5 5 5"/></svg>';
  wrap.style.transform = `rotate(${vento.direcao}deg)`;
  return wrap;
}

function renderCamposMeteo(container, decodificado, categoria) {
  container.innerHTML = "";
  if (!decodificado) return;

  const chip = criarChipCategoriaVoo(categoria);
  if (chip) container.appendChild(chip);

  const linhas = [];
  if (decodificado.vento) {
    const v = decodificado.vento;
    let txt = v.variavel
      ? `variável, ${v.velocidade_kt}kt`
      : `${String(v.direcao).padStart(3, "0")}° / ${v.velocidade_kt}kt`;
    if (v.rajada_kt) txt += `, rajada ${v.rajada_kt}kt`;
    linhas.push(["Vento", txt, false, criarIconeVento(v)]);
  }
  if (decodificado.visibilidade_m != null) {
    const txt = decodificado.visibilidade_m >= 9999 ? "10km+" : `${decodificado.visibilidade_m}m`;
    linhas.push(["Vis.", txt, false, null]);
  }
  if (decodificado.teto_ft != null) {
    linhas.push(["Teto", `${decodificado.teto_ft} ft`, true, null]);
  } else if (decodificado.nuvens && decodificado.nuvens.length === 0) {
    linhas.push(["Nuvens", "céu limpo", false, null]);
  }
  if (decodificado.temp != null) {
    const orv = decodificado.ponto_orvalho != null ? ` / ${decodificado.ponto_orvalho}°C` : "";
    linhas.push(["Temp.", `${decodificado.temp}°C${orv}`, false, null]);
  }
  if (decodificado.qnh_hpa) {
    linhas.push(["QNH", `${decodificado.qnh_hpa} hPa`, false, null]);
  }
  linhas.forEach(([rotulo, valor, destaque, icone]) => {
    const linha = document.createElement("div");
    linha.className = "metar-campo-linha";
    if (icone) linha.appendChild(icone);
    const r = document.createElement("span");
    r.className = "metar-campo-rotulo";
    r.textContent = rotulo;
    const val = document.createElement("span");
    val.className = "metar-campo-valor" + (destaque ? " teto" : "");
    val.textContent = valor;
    linha.appendChild(r);
    linha.appendChild(val);
    container.appendChild(linha);
  });
}

function renderSegmentosTaf(container, segmentos) {
  container.innerHTML = "";
  if (!segmentos) return;
  segmentos.forEach((seg) => {
    const bloco = document.createElement("div");
    bloco.className = "taf-segmento";
    const titulo = document.createElement("div");
    titulo.className = "taf-segmento-titulo";
    titulo.textContent = seg.periodo ? `${seg.tipo} (${seg.periodo})` : seg.tipo;
    bloco.appendChild(titulo);
    const campos = document.createElement("div");
    renderCamposMeteo(campos, seg.decodificado, seg.categoria_voo);
    bloco.appendChild(campos);
    container.appendChild(bloco);
  });
}

let metarFaladoAtual = null;
let tafFaladoAtual = null;

if ("speechSynthesis" in window) {
  $("#metar-ouvir").addEventListener("click", () => falarTexto($("#metar-ouvir"), metarFaladoAtual));
  $("#taf-ouvir").addEventListener("click", () => falarTexto($("#taf-ouvir"), tafFaladoAtual));
} else {
  $("#metar-ouvir").hidden = true;
  $("#taf-ouvir").hidden = true;
}

$("#metar-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#metar-btn");
  const icao = $("#metar-icao").value.trim().toUpperCase();
  if (!icao) return;

  setBotaoCarregando(btn, true, "buscando...");
  $("#metar-resultado").hidden = true;
  const data = await apiFetch(`/api/clima/metar?icao=${encodeURIComponent(icao)}`);
  setBotaoCarregando(btn, false, "Consultar");
  if (!data) return;

  if (!data.metar && !data.taf) {
    mostrarErro(data.erro || "não encontrei dado nenhum pra esse código.");
    return;
  }
  $("#metar-texto").textContent = data.metar || "sem METAR disponível agora.";
  $("#taf-texto").textContent = data.taf || "sem TAF disponível agora.";
  renderCamposMeteo($("#metar-campos"), data.metar_decodificado, data.metar_categoria);
  renderSegmentosTaf($("#taf-segmentos"), data.taf_segmentos);
  metarFaladoAtual = data.metar_falado;
  tafFaladoAtual = data.taf_falado;
  if ("speechSynthesis" in window) {
    $("#metar-ouvir").hidden = !metarFaladoAtual;
    $("#taf-ouvir").hidden = !tafFaladoAtual;
  }
  $("#metar-resultado").hidden = false;
  // reinicia a animacao de entrada a cada consulta nova (mesmo padrao de
  // pulsarSucesso: remove, forca reflow, adiciona de novo)
  document.querySelectorAll("#metar-resultado .metar-bloco").forEach((bloco) => {
    bloco.classList.remove("metar-anim");
    void bloco.offsetWidth;
    bloco.classList.add("metar-anim");
  });
});
