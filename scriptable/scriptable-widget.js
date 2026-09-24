// Widget universal do Painel Pessoal - via app Scriptable (App Store, gratis)
//
// Diferente dos scripts antigos (widget_painel.js / widget_lockscreen.js, que
// ficam no repo so como referencia historica - NAO editar), este script
// cobre os 4 tamanhos num arquivo so, escolhendo o layout certo sozinho via
// `config.widgetFamily`:
//   - "small"                -> tela inicial, widget pequeno
//   - "medium"                -> tela inicial, widget medio
//   - "accessoryCircular"     -> tela de bloqueio, circular
//   - "accessoryRectangular"  -> tela de bloqueio, retangular
// Qualquer outro valor (ex: "large", "accessoryInline") cai no layout de
// "small" por seguranca, pra nunca quebrar o widget.
//
// Busca em GET /api/widget (contrato fixo, ver docs/widget-scriptable.md) e
// guarda a ultima resposta boa em disco (FileManager) - se a rede falhar,
// mostra os dados salvos com "atualizado ha X" em vez de deixar o widget
// vazio ou travado.
//
// Como configurar:
// 1. Instala o Scriptable (App Store, gratis)
// 2. Cria um script novo, cola esse arquivo inteiro
// 3. Edita PAINEL_URL/TOKEN abaixo (ou usa o parametro do widget, ver docs)
// 4. Roda uma vez pra testar (mostra a previa)
// 5. Tela inicial: segura o dedo -> "+" -> "Scriptable" -> pequeno/medio
//    Tela de bloqueio: segura o dedo -> "Personalizar" -> widget abaixo do
//    relogio -> "+" -> "Scriptable" -> circular/retangular
//    Em ambos, na configuracao do widget que aparece, escolhe esse script.
//
// Guia completo (incluindo como gerar o token) em docs/widget-scriptable.md.

// ---- Configuracao (edita aqui, ou usa o parametro do widget) ----
const PAINEL_URL = "http://SEU-IP-OU-DOMINIO:5001"; // <- troca aqui
const TOKEN = ""; // <- troca aqui se configurou PAINEL_WIDGET_TOKEN no .env

// Paleta real do app (static/css/style.css: --bg, --surface, --text,
// --text-muted, --text-faint, --cor-painel, --danger) - nao inventar cor
// nova aqui, se o app mudar de paleta este script acompanha.
const COR_BG = "#000000";
const COR_SURFACE = "#121212";
const COR_TEXT = "#eceef3";
const COR_TEXT_MUTED = "#a7afbc";
const COR_TEXT_FAINT = "#788292";
const COR_ACCENT = "#41aa75"; // --cor-painel
const COR_DANGER = "#ff5c72"; // --danger

const CACHE_FILENAME = "painel_widget_cache.json";

const TEXTO_VAZIO_PADRAO = "Nada por enquanto — dia livre.";
const TEXTO_ERRO_PADRAO = "O painel sinalizou um erro. Abra o app.";
const TEXTO_SEM_CONEXAO = "Sem conexão com o painel e sem dados salvos.";

// ---- Config/URL/token ----

// Le URL e token do parametro do widget (formato "URL|TOKEN", configuravel
// por widget instalado, sem precisar editar o script) com fallback pras
// constantes fixas acima.
function resolverConfig() {
  let url = PAINEL_URL;
  let token = TOKEN;
  const parametro = (typeof args !== "undefined" && args && args.widgetParameter) || "";
  if (parametro) {
    const partes = String(parametro).split("|");
    if (partes[0]) url = partes[0].trim();
    if (partes[1] !== undefined) token = partes[1].trim();
  }
  return { url: String(url).replace(/\/+$/, ""), token };
}

function obterFamilia() {
  const familia = (typeof config !== "undefined" && config && config.widgetFamily) || "small";
  const validas = ["small", "medium", "accessoryCircular", "accessoryRectangular"];
  return validas.indexOf(familia) !== -1 ? familia : "small";
}

function ehTelaBloqueio(familia) {
  return familia === "accessoryCircular" || familia === "accessoryRectangular";
}

// ---- Busca de dados + cache ----

async function buscarDados(url, token) {
  const req = new Request(`${url}/api/widget`);
  req.headers = token ? { Authorization: `Bearer ${token}` } : {};
  req.timeoutInterval = 8;
  const dados = await req.loadJSON();
  if (req.response && typeof req.response.statusCode === "number" && req.response.statusCode >= 400) {
    throw new Error(`HTTP ${req.response.statusCode}`);
  }
  if (!dados || typeof dados !== "object" || !dados.estado) {
    throw new Error("payload invalido");
  }
  return dados;
}

function caminhoCache() {
  const fm = FileManager.local();
  return fm.joinPath(fm.documentsDirectory(), CACHE_FILENAME);
}

function lerCache() {
  try {
    const fm = FileManager.local();
    const caminho = caminhoCache();
    if (!fm.fileExists(caminho)) return null;
    const texto = fm.readString(caminho);
    const json = JSON.parse(texto);
    return json && typeof json === "object" ? json : null;
  } catch (e) {
    return null;
  }
}

function salvarCache(dados) {
  try {
    const fm = FileManager.local();
    fm.writeString(caminhoCache(), JSON.stringify(dados));
  } catch (e) {
    // cache e so um extra - falha ao salvar nunca derruba o widget
  }
}

// Busca ao vivo; se falhar (rede, timeout, HTTP 4xx/5xx, payload invalido),
// cai pro ultimo JSON bom salvo. So fica "sem dados" se nem isso existir.
async function obterDados() {
  const { url, token } = resolverConfig();
  try {
    const dados = await buscarDados(url, token);
    salvarCache(dados);
    return { dados, deCache: false, semDados: false };
  } catch (e) {
    const cache = lerCache();
    if (cache) {
      return { dados: cache, deCache: true, semDados: false };
    }
    return { dados: null, deCache: false, semDados: true };
  }
}

// ---- Formatacao ----

function formatarAtualizadoHaX(isoString, agora) {
  const data = new Date(isoString);
  const base = agora instanceof Date ? agora : new Date();
  if (Number.isNaN(data.getTime())) return "há um tempo";
  const diffMs = base.getTime() - data.getTime();
  if (diffMs < 0) return "agora";
  const diffSeg = Math.floor(diffMs / 1000);
  if (diffSeg < 60) return "agora";
  const diffMin = Math.floor(diffSeg / 60);
  if (diffMin < 60) return `há ${diffMin} min`;
  const diffHoras = Math.floor(diffMin / 60);
  if (diffHoras < 24) return `há ${diffHoras} h`;
  const diffDias = Math.floor(diffHoras / 24);
  return `há ${diffDias} d`;
}

function sufixoCache(dados, agora) {
  const quando = dados && dados.atualizado_em;
  if (!quando) return "atualizado há um tempo";
  return `atualizado ${formatarAtualizadoHaX(quando, agora)}`;
}

function seguro(obj, chave, padrao) {
  if (obj && obj[chave] !== undefined && obj[chave] !== null) return obj[chave];
  return padrao;
}

// As 4 linhas prontas que a API ja manda (`linhas`) sao a fonte primaria de
// texto - funciona pros 3 estados (normal/vazio/erro) sem o script precisar
// adivinhar o formato exato de cada estado. So monta na mao se faltar.
function linhasDeApoio(dados) {
  if (dados && Array.isArray(dados.linhas) && dados.linhas.length) return dados.linhas;
  const partes = [];
  if (dados && dados.foco && dados.foco.titulo) {
    partes.push(`Foco: ${dados.foco.titulo} em ${dados.foco.em_minutos} min`);
  }
  if (dados && dados.proxima_conta && dados.proxima_conta.nome) {
    partes.push(`Conta: ${dados.proxima_conta.nome} em ${dados.proxima_conta.em_dias} dias`);
  }
  if (dados && dados.habitos) {
    partes.push(`Hábitos: ${dados.habitos.feitos}/${dados.habitos.total}`);
  }
  if (dados && dados.custo_ia) {
    partes.push(`IA: ${dados.custo_ia.percentual_teto}% do teto`);
  }
  return partes.length ? partes : ["Sem dados no momento."];
}

// ---- Montagem visual ----

function corDe(hex) {
  return new Color(hex);
}

function aplicarFundoHome(widget) {
  widget.backgroundColor = corDe(COR_BG);
  widget.setPadding(14, 14, 14, 14);
}

function adicionarTile(stack, valor, rotulo) {
  const bloco = stack.addStack();
  bloco.layoutVertically();
  bloco.backgroundColor = corDe(COR_SURFACE);
  bloco.cornerRadius = 10;
  bloco.setPadding(8, 10, 8, 10);
  const v = bloco.addText(String(valor));
  v.textColor = corDe(COR_TEXT);
  v.font = Font.boldSystemFont(16);
  const r = bloco.addText(rotulo);
  r.textColor = corDe(COR_TEXT_MUTED);
  r.font = Font.systemFont(9);
}

// accessoryCircular/accessoryRectangular sao renderizados monocromaticos
// pelo proprio iOS (16+) - cor de texto/fundo customizada e ignorada ou fica
// errada nesses slots, entao aqui NUNCA se define textColor/backgroundColor
// (mesma regra ja seguida em widget_lockscreen.js).
function montarCircular(widget, numeroTexto, rotulo) {
  const pilha = widget.addStack();
  pilha.layoutVertically();
  pilha.addSpacer();
  const numero = pilha.addText(numeroTexto);
  numero.font = Font.boldSystemFont(18);
  numero.minimumScaleFactor = 0.6;
  numero.centerAlignText();
  const texto = pilha.addText(rotulo);
  texto.font = Font.systemFont(8);
  texto.centerAlignText();
  pilha.addSpacer();
}

function montarRectangular(widget, linha1Texto, linha2Texto) {
  const linha1 = widget.addText(linha1Texto || "Painel Pessoal");
  linha1.font = Font.boldSystemFont(13);
  linha1.minimumScaleFactor = 0.7;

  if (linha2Texto) {
    widget.addSpacer(2);
    const linha2 = widget.addText(linha2Texto);
    linha2.font = Font.systemFont(12);
    linha2.minimumScaleFactor = 0.6;
  }
}

function preencherNormal(widget, familia, dados, sufixo) {
  const linhas = linhasDeApoio(dados);

  if (ehTelaBloqueio(familia)) {
    if (familia === "accessoryCircular") {
      const numero = `${seguro(dados.habitos, "feitos", "-")}/${seguro(dados.habitos, "total", "-")}`;
      montarCircular(widget, numero, sufixo || "hábitos");
    } else {
      montarRectangular(widget, linhas[0], sufixo ? sufixo : linhas[1]);
    }
    return;
  }

  aplicarFundoHome(widget);
  const titulo = widget.addText("PAINEL");
  titulo.textColor = corDe(COR_ACCENT);
  titulo.font = Font.boldSystemFont(10);
  widget.addSpacer(8);

  const quantasLinhas = familia === "medium" ? linhas.length : Math.min(2, linhas.length);
  for (let i = 0; i < quantasLinhas; i++) {
    const linha = widget.addText(linhas[i]);
    linha.textColor = corDe(i === 0 ? COR_TEXT : COR_TEXT_MUTED);
    linha.font = Font.systemFont(familia === "medium" ? 12 : 11);
    linha.minimumScaleFactor = 0.7;
    if (i < quantasLinhas - 1) widget.addSpacer(6);
  }

  if (familia === "medium") {
    widget.addSpacer(10);
    const stats = widget.addStack();
    stats.layoutHorizontally();
    stats.spacing = 10;
    adicionarTile(stats, `${seguro(dados.habitos, "feitos", "-")}/${seguro(dados.habitos, "total", "-")}`, "hábitos");
    adicionarTile(stats, `${seguro(dados.custo_ia, "percentual_teto", "-")}%`, "IA do teto");
  }

  if (sufixo) {
    widget.addSpacer(8);
    const rodape = widget.addText(sufixo);
    rodape.textColor = corDe(COR_TEXT_FAINT);
    rodape.font = Font.systemFont(9);
  }
}

function preencherVazio(widget, familia, dados, sufixo) {
  const linhas = dados && Array.isArray(dados.linhas) && dados.linhas.length ? dados.linhas : [TEXTO_VAZIO_PADRAO];

  if (ehTelaBloqueio(familia)) {
    if (familia === "accessoryCircular") {
      montarCircular(widget, "—", sufixo || "livre");
    } else {
      montarRectangular(widget, linhas[0], sufixo ? sufixo : linhas[1]);
    }
    return;
  }

  aplicarFundoHome(widget);
  const titulo = widget.addText("PAINEL");
  titulo.textColor = corDe(COR_ACCENT);
  titulo.font = Font.boldSystemFont(10);
  widget.addSpacer(8);

  const msg = widget.addText(linhas[0]);
  msg.textColor = corDe(COR_TEXT_MUTED);
  msg.font = Font.systemFont(familia === "medium" ? 13 : 12);
  msg.minimumScaleFactor = 0.7;

  if (familia === "medium" && linhas[1]) {
    widget.addSpacer(6);
    const msg2 = widget.addText(linhas[1]);
    msg2.textColor = corDe(COR_TEXT_FAINT);
    msg2.font = Font.systemFont(11);
  }

  if (sufixo) {
    widget.addSpacer(8);
    const rodape = widget.addText(sufixo);
    rodape.textColor = corDe(COR_TEXT_FAINT);
    rodape.font = Font.systemFont(9);
  }
}

function preencherErroApi(widget, familia, dados, sufixo) {
  const linhas = dados && Array.isArray(dados.linhas) && dados.linhas.length ? dados.linhas : [TEXTO_ERRO_PADRAO];

  if (ehTelaBloqueio(familia)) {
    if (familia === "accessoryCircular") {
      montarCircular(widget, "!", sufixo || "erro");
    } else {
      montarRectangular(widget, linhas[0], sufixo ? sufixo : linhas[1]);
    }
    return;
  }

  aplicarFundoHome(widget);
  const titulo = widget.addText("PAINEL");
  titulo.textColor = corDe(COR_DANGER);
  titulo.font = Font.boldSystemFont(10);
  widget.addSpacer(8);

  const msg = widget.addText(linhas[0]);
  msg.textColor = corDe(COR_TEXT);
  msg.font = Font.systemFont(familia === "medium" ? 13 : 12);
  msg.minimumScaleFactor = 0.7;

  if (sufixo) {
    widget.addSpacer(8);
    const rodape = widget.addText(sufixo);
    rodape.textColor = corDe(COR_TEXT_FAINT);
    rodape.font = Font.systemFont(9);
  }
}

// Rede falhou E nao ha cache nenhum salvo ainda (ex: primeira instalacao
// sem internet) - unico caso em que o widget nao tem literalmente nada pra
// mostrar.
function preencherSemConexao(widget, familia) {
  if (ehTelaBloqueio(familia)) {
    if (familia === "accessoryCircular") {
      montarCircular(widget, "--", "sem dados");
    } else {
      montarRectangular(widget, TEXTO_SEM_CONEXAO, null);
    }
    return;
  }

  aplicarFundoHome(widget);
  const msg = widget.addText(TEXTO_SEM_CONEXAO);
  msg.textColor = corDe(COR_TEXT_MUTED);
  msg.font = Font.systemFont(12);
  msg.minimumScaleFactor = 0.7;
}

async function montarWidget() {
  const familia = obterFamilia();
  const widget = new ListWidget();
  const { dados, deCache, semDados } = await obterDados();

  if (semDados) {
    preencherSemConexao(widget, familia);
    return widget;
  }

  const estado = dados && dados.estado ? dados.estado : "normal";
  const sufixo = deCache ? sufixoCache(dados, new Date()) : null;

  if (estado === "erro") {
    preencherErroApi(widget, familia, dados, sufixo);
  } else if (estado === "vazio") {
    preencherVazio(widget, familia, dados, sufixo);
  } else {
    preencherNormal(widget, familia, dados, sufixo);
  }

  return widget;
}

// ---- Execucao ----

async function apresentarPreview(widget, familia) {
  if (familia === "medium" && widget.presentMedium) return widget.presentMedium();
  if (familia === "accessoryCircular" && widget.presentAccessoryCircular) {
    return widget.presentAccessoryCircular();
  }
  if (familia === "accessoryRectangular" && widget.presentAccessoryRectangular) {
    return widget.presentAccessoryRectangular();
  }
  if (widget.presentSmall) return widget.presentSmall();
}

async function main() {
  const familia = obterFamilia();
  const widget = await montarWidget();
  if (typeof config !== "undefined" && config && config.runsInWidget) {
    Script.setWidget(widget);
  } else {
    await apresentarPreview(widget, familia);
  }
  if (typeof Script !== "undefined" && Script.complete) Script.complete();
}

// Roda de verdade so dentro do Scriptable (globais reais). Em Node (testes),
// `module` existe e o script so exporta as funcoes puras, sem chamar main() -
// mesmo padrao usado em static/js/*.js (ver `typeof module !== "undefined"`).
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    resolverConfig,
    obterFamilia,
    buscarDados,
    obterDados,
    lerCache,
    salvarCache,
    formatarAtualizadoHaX,
    linhasDeApoio,
    montarWidget,
    main,
  };
} else {
  main();
}
