// static/js/nucleo/formatos.js - Nucleo compartilhado: formatadores e mascaras (moeda, horas, data, fmtDataBr, hojeIsoLocal, formatarPrazoTarefa).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 92-162, app.js 1602-1629.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

const fmtMoeda = (valor) =>
  Number(valor).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

// api_usage.cost_usd (db.py) e sempre USD, nunca convertido pra BRL - fmtMoeda
// formataria como R$ por engano (moeda errada, nao so casas decimais).
const fmtUSD = (valor) =>
  Number(valor).toLocaleString("en-US", { style: "currency", currency: "USD" });

const fmtHoras = (h) =>
  `${Number(h).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 2 })}h`;

// Horas nao tem a complexidade de moeda (sem milhar, poucas casas decimais)
// entao aceita virgula ou ponto direto, sem mascara "digito a digito".
function parseHoras(texto) {
  const limpo = (texto || "").trim().replace(",", ".");
  if (!limpo) return null;
  const n = parseFloat(limpo);
  return Number.isFinite(n) && n > 0 ? n : null;
}

// Mascara de moeda BR no estilo "digito da direita pra esquerda" (o mesmo
// dos apps de banco): o campo so guarda digitos, os 2 ultimos viram
// centavos, e o texto e sempre reconstruido do zero a cada tecla - por
// isso apagar nunca desorganiza a pontuacao nem o cursor (ele so encolhe
// a string de digitos e redesenha).
function aplicarMascaraMoeda(input) {
  input.addEventListener("input", () => {
    let digitos = input.value.replace(/\D/g, "").replace(/^0+(?=\d)/, "");
    if (!digitos) {
      input.value = "";
      return;
    }
    digitos = digitos.padStart(3, "0");
    const inteiro = digitos.slice(0, -2).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    const centavos = digitos.slice(-2);
    input.value = `${inteiro},${centavos}`;
  });
}

function valorMascaraParaNumero(texto) {
  const limpo = texto.replace(/\./g, "").replace(",", ".");
  const n = parseFloat(limpo);
  return Number.isFinite(n) ? n : 0;
}

// Mesma logica de digito-a-digito pra data: so digitos, barras entram
// sozinhas conforme a posicao - apagar so encolhe os digitos, nunca deixa
// barra sobrando nem quebra o cursor.
function aplicarMascaraData(input) {
  input.addEventListener("input", () => {
    const digitos = input.value.replace(/\D/g, "").slice(0, 8);
    const partes = [];
    if (digitos.length > 0) partes.push(digitos.slice(0, 2));
    if (digitos.length > 2) partes.push(digitos.slice(2, 4));
    if (digitos.length > 4) partes.push(digitos.slice(4, 8));
    input.value = partes.join("/");
  });
}

function mascaraDataParaIso(texto) {
  const m = texto.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (!m) return null;
  const dia = Number(m[1]);
  const mes = Number(m[2]);
  const ano = Number(m[3]);
  if (mes < 1 || mes > 12) return null;
  const diasNoMes = new Date(ano, mes, 0).getDate();
  if (dia < 1 || dia > diasNoMes) return null;
  return `${String(ano).padStart(4, "0")}-${String(mes).padStart(2, "0")}-${String(dia).padStart(2, "0")}`;
}

function fmtDataBr(isoDate) {
  const [ano, mes, dia] = isoDate.split("-");
  return `${dia}/${mes}/${ano}`;
}

// Fase 6 (US-F10): "hoje" em AAAA-MM-DD no fuso LOCAL do navegador - nao usa
// toISOString() (que e UTC: perto da meia-noite no fuso do Brasil, UTC ja
// virou o dia seguinte e a comparacao com due_date ficaria 1 dia adiantada).
function hojeIsoLocal() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// Fase 6 (US-F10): rotulo curto pra due_date sozinho (hoje/amanha/dd-mm),
// usado quando a tarefa nao tem due_at (texto livre "amanha"/"sexta" que
// so o chat preenche) - o formulario direto novo (#nova-tarefa-form) so
// grava due_date (data de verdade, sem passar pela IA), entao criarItemTarefa
// precisa saber mostrar isso tambem, nao so due_at/hora.
function formatarPrazoTarefa(dueDateIso) {
  const hoje = hojeIsoLocal();
  if (dueDateIso === hoje) return "hoje";
  const d = new Date();
  d.setDate(d.getDate() + 1);
  const amanhaIso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  if (dueDateIso === amanhaIso) return "amanha";
  return fmtDataBr(dueDateIso);
}
