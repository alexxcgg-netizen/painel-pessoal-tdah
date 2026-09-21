// Widget de tela inicial do Painel Pessoal - via app Scriptable (App Store, gratis)
//
// Como configurar:
// 1. Instala o Scriptable (App Store)
// 2. Cria um script novo, cola esse arquivo inteiro
// 3. Edita as duas constantes abaixo (URL e TOKEN)
// 4. Roda uma vez pra testar (mostra a previa do widget)
// 5. Na tela inicial, segura o dedo -> "+" -> procura "Scriptable" -> escolhe
//    o tamanho pequeno/medio -> na configuracao do widget, escolhe esse script
//
// O widget busca /api/atalho/resumo (token-gated, sem IA, so leitura rapida)
// a cada atualizacao - o iOS decide o intervalo de refresh sozinho (o app nao
// controla isso, e assim que o sistema de widgets do iOS funciona).

const PAINEL_URL = "http://SEU-IP-OU-DOMINIO:5001"; // <- troca aqui
const TOKEN = ""; // <- troca aqui se configurou PAINEL_ATALHOS_TOKEN no .env

// paleta "joia" do painel - mesmas cores do app de verdade
const COR_BG = new Color("#09090d");
const COR_SURFACE = new Color("#1c1f28");
const COR_TEXTO = new Color("#eceef3");
const COR_TEXTO_MUTED = new Color("#a7afbc");
const COR_ACCENT = new Color("#b85ec9");

async function buscarResumo() {
  const req = new Request(`${PAINEL_URL}/api/atalho/resumo`);
  if (TOKEN) req.headers = { "X-Webhook-Token": TOKEN };
  req.timeoutInterval = 8;
  return await req.loadJSON();
}

function fmtMoeda(valor) {
  return `R$ ${Number(valor).toFixed(2).replace(".", ",")}`;
}

async function criarWidget() {
  const widget = new ListWidget();
  widget.backgroundColor = COR_BG;
  widget.setPadding(14, 14, 14, 14);

  let dados;
  try {
    dados = await buscarResumo();
  } catch (e) {
    const erro = widget.addText("Nao consegui falar com o painel agora.");
    erro.textColor = COR_TEXTO_MUTED;
    erro.font = Font.systemFont(12);
    return widget;
  }

  if (dados.error) {
    const erro = widget.addText("Token invalido - confere PAINEL_ATALHOS_TOKEN.");
    erro.textColor = COR_TEXTO_MUTED;
    erro.font = Font.systemFont(12);
    return widget;
  }

  const titulo = widget.addText("PAINEL PESSOAL");
  titulo.textColor = COR_ACCENT;
  titulo.font = Font.boldSystemFont(10);

  widget.addSpacer(8);

  const linhaStats = widget.addStack();
  linhaStats.layoutHorizontally();
  linhaStats.spacing = 10;

  const blocoTarefas = linhaStats.addStack();
  blocoTarefas.layoutVertically();
  blocoTarefas.backgroundColor = COR_SURFACE;
  blocoTarefas.cornerRadius = 10;
  blocoTarefas.setPadding(8, 10, 8, 10);
  const valorTarefas = blocoTarefas.addText(String(dados.tarefas_pendentes));
  valorTarefas.textColor = COR_TEXTO;
  valorTarefas.font = Font.boldSystemFont(20);
  const labelTarefas = blocoTarefas.addText("tarefas");
  labelTarefas.textColor = COR_TEXTO_MUTED;
  labelTarefas.font = Font.systemFont(9);

  const blocoGasto = linhaStats.addStack();
  blocoGasto.layoutVertically();
  blocoGasto.backgroundColor = COR_SURFACE;
  blocoGasto.cornerRadius = 10;
  blocoGasto.setPadding(8, 10, 8, 10);
  const valorGasto = blocoGasto.addText(fmtMoeda(dados.gasto_hoje));
  valorGasto.textColor = COR_TEXTO;
  valorGasto.font = Font.boldSystemFont(16);
  const labelGasto = blocoGasto.addText("gasto hoje");
  labelGasto.textColor = COR_TEXTO_MUTED;
  labelGasto.font = Font.systemFont(9);

  widget.addSpacer(10);

  if (dados.proximo_titulo) {
    const labelProximo = widget.addText("PROXIMO");
    labelProximo.textColor = COR_TEXTO_MUTED;
    labelProximo.font = Font.boldSystemFont(8);
    widget.addSpacer(2);
    const proximo = widget.addText(`${dados.proximo_hora} · ${dados.proximo_titulo}`);
    proximo.textColor = COR_TEXTO;
    proximo.font = Font.systemFont(12);
  } else {
    const semCompromisso = widget.addText("Nada marcado no resto do dia.");
    semCompromisso.textColor = COR_TEXTO_MUTED;
    semCompromisso.font = Font.systemFont(11);
  }

  return widget;
}

const widget = await criarWidget();
if (config.runsInWidget) {
  Script.setWidget(widget);
} else {
  await widget.presentSmall();
}
Script.complete();
