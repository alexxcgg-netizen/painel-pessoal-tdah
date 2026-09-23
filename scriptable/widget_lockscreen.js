// Widget de TELA DE BLOQUEIO do Painel Pessoal - via app Scriptable (App Store, gratis)
//
// Diferente do widget_painel.js (tela inicial, colorido, mais espaco), este
// script e pensado pro widget de tela de BLOQUEIO do iOS 16+ (familias
// accessoryInline/accessoryCircular/accessoryRectangular) - ali o espaco e
// minimo (uma ou duas linhas de texto) e o sistema renderiza tudo
// monocromatico sozinho, entao NAO define cor de texto/fundo (o iOS ignora
// ou distorce cor customizada nesses slots).
//
// Como configurar:
// 1. Instala o Scriptable (App Store), se ainda nao tiver
// 2. Cria um script novo, cola esse arquivo inteiro
// 3. Edita as duas constantes abaixo (URL e TOKEN)
// 4. Roda uma vez pra testar (mostra a previa em accessoryRectangular)
// 5. Na TELA DE BLOQUEIO, segura o dedo -> "Personalizar" -> toca no widget
//    abaixo do relogio -> "+" -> procura "Scriptable" -> escolhe o tamanho
//    (retangular mostra 2 linhas; circular so o numero de tarefas; inline
//    fica na linha ao lado da data) -> na configuracao do widget, escolhe
//    esse script
//
// O widget busca /api/atalho/resumo (token-gated, sem IA, so leitura rapida)
// a cada atualizacao - o iOS decide o intervalo de refresh sozinho (o app
// nao controla isso, e assim que o sistema de widgets do iOS funciona).

const PAINEL_URL = "http://SEU-IP-OU-DOMINIO:5001"; // <- troca aqui
const TOKEN = ""; // <- troca aqui se configurou PAINEL_ATALHOS_TOKEN no .env

async function buscarResumo() {
  const req = new Request(`${PAINEL_URL}/api/atalho/resumo`);
  if (TOKEN) req.headers = { "X-Webhook-Token": TOKEN };
  req.timeoutInterval = 8;
  return await req.loadJSON();
}

async function criarWidget() {
  const widget = new ListWidget();

  let dados;
  try {
    dados = await buscarResumo();
  } catch (e) {
    widget.addText("Sem conexao com o painel");
    return widget;
  }

  if (dados.error) {
    widget.addText("Token invalido");
    return widget;
  }

  const familia = config.widgetFamily;

  if (familia === "accessoryCircular") {
    const pilha = widget.addStack();
    pilha.layoutVertically();
    pilha.addSpacer();
    const numero = pilha.addText(String(dados.tarefas_pendentes));
    numero.font = Font.boldSystemFont(20);
    numero.centerAlignText();
    const rotulo = pilha.addText("tarefas");
    rotulo.font = Font.systemFont(9);
    rotulo.centerAlignText();
    pilha.addSpacer();
    return widget;
  }

  if (familia === "accessoryInline") {
    // uma linha so, sem opcao de segunda linha - o texto mais compacto que
    // o endpoint ja monta pronto (ver vida.resumo_curto_lockscreen).
    widget.addText(dados.resumo_curto || "Painel Pessoal");
    return widget;
  }

  // accessoryRectangular (o padrao/mais comum na tela de bloqueio) - cabem
  // duas linhas curtas confortavelmente.
  const linha1 = widget.addText(dados.resumo_curto || "Painel Pessoal");
  linha1.font = Font.boldSystemFont(13);
  linha1.minimumScaleFactor = 0.7;

  if (dados.linha_extra) {
    widget.addSpacer(2);
    const linha2 = widget.addText(dados.linha_extra);
    linha2.font = Font.systemFont(12);
    linha2.minimumScaleFactor = 0.7;
  }

  return widget;
}

const widget = await criarWidget();
if (config.runsInWidget) {
  Script.setWidget(widget);
} else {
  // fora do widget (rodando manual pra testar), mostra a previa no formato
  // retangular - accessoryCircular/Inline so tem preview real na tela de
  // bloqueio de verdade.
  await widget.presentAccessoryRectangular();
}
Script.complete();
