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
// 2026-10-13 (widget "proximo + comida"): mesmos tokens do app de hoje (static/css/ui/tokens.css)
const COR_DESTAQUE = "#bfe6ff"; // --cor-destaque
const COR_COMIDA = "#9fdcb0"; // --cor-cat-7 (card refeicao do chat)
const COR_TRILHO = "#1f272e"; // --cor-borda

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
  const ehConfig = /\|/.test(String(parametro)) || /^\s*https?:/i.test(String(parametro));
  if (parametro && ehConfig) {
    const partes = String(parametro).split("|");
    if (partes[0]) url = partes[0].trim();
    if (partes[1] !== undefined) token = partes[1].trim();
  }
  return { url: String(url).replace(/\/+$/, ""), token };
}

function obterFamilia() {
  const familia = (typeof config !== "undefined" && config && config.widgetFamily) || "small";
  const validas = ["small", "medium", "large", "accessoryCircular", "accessoryRectangular", "accessoryInline"];
  return validas.indexOf(familia) !== -1 ? familia : "small";
}

function ehTelaBloqueio(familia) {
  return familia === "accessoryCircular" || familia === "accessoryRectangular" || familia === "accessoryInline";
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

// ---- Proximo compromisso + comida do dia (2026-10-13) ----

const milhar = (n) => Math.round(Number(n) || 0).toLocaleString("pt-BR");

// 0 -> "agora", 25 -> "em 25 min", 80 -> "em 1h20", 120 -> "em 2h"
function quandoTexto(minutos) {
  const m = Math.max(0, Math.round(Number(minutos) || 0));
  if (m === 0) return "agora";
  if (m < 60) return `em ${m} min`;
  const h = Math.floor(m / 60);
  const resto = m % 60;
  return resto ? `em ${h}h${String(resto).padStart(2, "0")}` : `em ${h}h`;
}

// O "proximo" que o widget mostra: o 1o item pendente da agenda de hoje (inclui compromisso do
// iCloud, que o `foco` da API deixa de fora por nao ter check de concluir); sem agenda (API antiga
// ou cache velho), cai no `foco`. Sempre no formato {titulo, em_minutos, hora, tipo}.
function proximoDe(dados) {
  const agenda = dados && Array.isArray(dados.agenda) ? dados.agenda : [];
  const item = agenda.find((i) => i && i.titulo && !i.concluido);
  if (item) return { titulo: item.titulo, em_minutos: item.em_minutos, hora: item.hora, tipo: item.tipo };
  const foco = dados && dados.foco;
  return foco && foco.titulo ? { titulo: foco.titulo, em_minutos: foco.em_minutos, hora: foco.hora, tipo: "tarefa" } : null;
}

// itens da agenda ainda por vir (sem os concluidos), no maximo `n`
function agendaPendente(dados, n) {
  const agenda = dados && Array.isArray(dados.agenda) ? dados.agenda : [];
  return agenda.filter((i) => i && i.titulo && !i.concluido).slice(0, n || 5);
}

// simbolo da Apple por tipo de item da agenda
function simboloDoTipo(tipo) {
  if (tipo === "compromisso") return "calendar";
  if (tipo === "habito") return "repeat";
  return "checkmark.circle";
}

// fracao 0..1 do dia contra a meta (null sem meta)
function fracaoMeta(valor, meta) {
  if (!meta || !(Number(meta) > 0)) return null;
  return Math.max(0, Math.min(1, (Number(valor) || 0) / Number(meta)));
}

// "1.066 / 2.550 kcal" (ou "1.066 kcal" sem meta)
function comidaKcalTexto(comida) {
  if (!comida) return "";
  return comida.meta_kcal ? `${milhar(comida.kcal)} / ${milhar(comida.meta_kcal)} kcal` : `${milhar(comida.kcal)} kcal`;
}

function comidaProteinaTexto(comida) {
  if (!comida) return "";
  return comida.meta_proteina_g
    ? `Proteína ${milhar(comida.proteina_g)} / ${milhar(comida.meta_proteina_g)} g`
    : `Proteína ${milhar(comida.proteina_g)} g`;
}

// ---- Tela de inicio redesenhada (2026-10-13, "vai fundo, deixa cada vez mais bonito") ----
// Escolhas do Alex: fundo que muda com a hora do dia, cards de vidro, widget grande com agenda +
// comida (aneis e macros) + habitos + proxima conta. Widget do iOS nao anima (o iOS tira uma
// "foto" e mostra parada) - o "vivo" vem do fundo/saudacao acompanhando a hora, dos aneis
// enchendo e do refreshAfterDate perto do proximo compromisso.

const COR_PROTEINA = "#ffc98a";
const COR_CARBO = "#bfe6ff";
const COR_GORDURA = "#e7b6ff";
const COR_META_BATIDA = "#ffd76a";
const COR_HABITO = "#41aa75"; // --cor-painel
const tom = (alfa) => new Color("#ffffff", alfa);
const corA = (hex, alfa) => new Color(hex, alfa === undefined ? 1 : alfa);

// fundo por periodo: gradiente (topo -> base) + dois brilhos suaves (cor, alfa, posicao relativa)
const PALETAS = [
  { ate: 5, nome: "madrugada", saudacao: "Boa noite", simbolo: "moon.stars.fill", cores: ["#090e1d", "#17133a"], brilhos: [["#3f45a8", 0.42, 0.88, 0.08], ["#1b5574", 0.32, 0.1, 1]] },
  { ate: 12, nome: "manha", saudacao: "Bom dia", simbolo: "sun.horizon.fill", cores: ["#123a69", "#2f78ad"], brilhos: [["#ffd59a", 0.38, 0.9, 0.05], ["#63bdf0", 0.3, 0.05, 1]] },
  { ate: 16, nome: "tarde", saudacao: "Boa tarde", simbolo: "sun.max.fill", cores: ["#0e3a56", "#1f7086"], brilhos: [["#9ef0d8", 0.3, 0.92, 0.05], ["#2c63b0", 0.34, 0.05, 1]] },
  { ate: 19, nome: "por do sol", saudacao: "Boa tarde", simbolo: "sunset.fill", cores: ["#281b47", "#9b4a48"], brilhos: [["#ff9a5c", 0.48, 0.9, 0.12], ["#6c3d94", 0.38, 0.05, 1]] },
  { ate: 24, nome: "noite", saudacao: "Boa noite", simbolo: "moon.stars.fill", cores: ["#0a1124", "#1d1940"], brilhos: [["#5b4bb8", 0.38, 0.9, 0.05], ["#1c4f6e", 0.3, 0.05, 1]] },
];

function paletaDoHorario(data) {
  const h = (data instanceof Date ? data : new Date()).getHours();
  return PALETAS.find((p) => h < p.ate) || PALETAS[PALETAS.length - 1];
}

// tamanho (pt) de cada familia no iPhone grande (17 Pro Max); o iOS escala o fundo pra preencher
const TAMANHO_FAMILIA = { small: [170, 170], medium: [364, 170], large: [364, 382] };

function misturarHex(a, b, t) {
  const pa = parseInt(a.slice(1), 16);
  const pb = parseInt(b.slice(1), 16);
  const canal = (n, s) => (n >> s) & 255;
  const m = (s) => Math.round(canal(pa, s) + (canal(pb, s) - canal(pa, s)) * t);
  return `#${[16, 8, 0].map((s) => m(s).toString(16).padStart(2, "0")).join("")}`;
}

function imagemFundo(paleta, familia) {
  const [W, H] = TAMANHO_FAMILIA[familia] || TAMANHO_FAMILIA.small;
  const d = new DrawContext();
  d.size = new Size(W, H);
  d.opaque = true;
  d.respectScreenScale = false;
  // gradiente diagonal suave em faixas finas (DrawContext nao tem gradiente nativo)
  const faixas = 64;
  for (let i = 0; i < faixas; i++) {
    d.setFillColor(new Color(misturarHex(paleta.cores[0], paleta.cores[1], i / (faixas - 1))));
    d.fillRect(new Rect(0, Math.floor((i * H) / faixas), W, Math.ceil(H / faixas) + 1));
  }
  // brilhos: circulos concentricos de alfa baixo somando um halo macio
  const R = Math.max(W, H) * 0.62;
  paleta.brilhos.forEach(([hex, alfa, px, py], idx) => {
    const raio = idx === 0 ? R : R * 0.7;
    const camadas = 14;
    for (let k = 0; k < camadas; k++) {
      const r = raio * (1 - k / camadas);
      d.setFillColor(new Color(hex, alfa / camadas));
      d.fillEllipse(new Rect(W * px - r, H * py - r, 2 * r, 2 * r));
    }
  });
  return d.getImage();
}

function aplicarFundoHome(widget, familia) {
  const paleta = paletaDoHorario(new Date());
  widget.backgroundColor = new Color(paleta.cores[1]); // reserva se o resto falhar
  try {
    const g = new LinearGradient();
    g.colors = paleta.cores.map((c) => new Color(c));
    g.locations = [0, 1];
    g.startPoint = new Point(0, 0);
    g.endPoint = new Point(1, 1);
    widget.backgroundGradient = g;
  } catch (e) {
    // so o fundo liso
  }
  try {
    widget.backgroundImage = imagemFundo(paleta, familia || "small");
  } catch (e) {
    // fica o gradiente
  }
  const p = familia === "large" ? 16 : 14;
  widget.setPadding(p, p, p, p);
  return paleta;
}

function textoHome(pai, s, fonte, cor, linhas) {
  const t = pai.addText(String(s));
  t.font = fonte;
  t.textColor = cor || tom(1);
  t.lineLimit = linhas || 1;
  t.minimumScaleFactor = 0.72;
  return t;
}

// card de vidro: branco translucido + borda fina, cantos 16 (mesma linguagem do Liquid Glass do app)
function cartao(pai, padding) {
  const c = pai.addStack();
  c.layoutVertically();
  c.backgroundColor = tom(0.1);
  c.borderColor = tom(0.16);
  c.borderWidth = 1;
  c.cornerRadius = 16;
  const p = padding === undefined ? 10 : padding;
  c.setPadding(p, p, p, p);
  return c;
}

function pilula(pai, s, destaque) {
  const p = pai.addStack();
  p.backgroundColor = destaque ? corA(COR_DESTAQUE, 0.22) : tom(0.16);
  p.cornerRadius = 8;
  p.setPadding(2, 7, 2, 7);
  textoHome(p, s, Font.semiboldRoundedSystemFont(10), destaque ? corA(COR_DESTAQUE) : tom(0.92));
  return p;
}

// cabecalho pequeno: simbolo + ROTULO na cor do bloco
function cabecalho(pai, nomeSimbolo, rotulo, cor) {
  const linha = pai.addStack();
  linha.layoutHorizontally();
  linha.centerAlignContent();
  if (adicionarSimbolo(linha, nomeSimbolo, 10, corA(cor))) linha.addSpacer(4);
  textoHome(linha, rotulo, Font.boldSystemFont(10), corA(cor));
  return linha;
}

// barra fina de progresso feita de stacks: trilho com o preenchido dentro
function adicionarBarra(pai, fracao, largura, cor, altura) {
  const a = altura || 5;
  const trilho = pai.addStack();
  trilho.layoutHorizontally();
  trilho.size = new Size(largura, a);
  trilho.backgroundColor = tom(0.14);
  trilho.cornerRadius = a / 2;
  const f = Math.max(0, Math.min(1, Number(fracao) || 0));
  if (f > 0) {
    const cheio = trilho.addStack();
    cheio.size = new Size(Math.max(a, Math.round(largura * f)), a);
    cheio.backgroundColor = corA(cor);
    cheio.cornerRadius = a / 2;
  }
  trilho.addSpacer();
  return trilho;
}

// aneis da comida: kcal por fora, proteina por dentro; dourado quando bate a meta de kcal
function imagemAneisComida(comida, comCentro) {
  const fk = fracaoMeta(comida.kcal, comida.meta_kcal);
  const fp = fracaoMeta(comida.proteina_g, comida.meta_proteina_g);
  const corK = fk !== null && fk >= 1 ? COR_META_BATIDA : COR_COMIDA;
  const aneis = [{ frac: fk === null ? 0 : fk, cor: corA(corK), trilho: corA(corK, 0.2) }];
  if (fp !== null) aneis.push({ frac: fp, cor: corA(COR_PROTEINA), trilho: corA(COR_PROTEINA, 0.2) });
  let centro = null;
  if (comCentro) centro = fk !== null ? `${Math.round((Number(comida.kcal) / Number(comida.meta_kcal)) * 100)}%` : milhar(comida.kcal);
  // com o numero no meio os aneis ficam mais finos, pra sobrar miolo pro texto
  const espessura = comCentro ? 11 : 15;
  return imagemAneis(aneis, { tamanho: 120, espessura, vao: 3, centro, rotulo: comCentro ? "kcal" : null, fonteCentro: 25, fonteRotulo: 11 });
}

function adicionarAneisComida(pai, comida, tamanho, comCentro) {
  const img = pai.addImage(imagemAneisComida(comida, comCentro));
  img.imageSize = new Size(tamanho, tamanho);
  return img;
}

// pontinhos dos habitos (feito = cheio verde, falta = trilho)
function imagemPontosHabitos(feitos, total, diametro) {
  const n = Math.max(1, Math.min(10, Number(total) || 0));
  const dm = diametro || 10;
  const vao = Math.round(dm * 0.55);
  const esc = 3;
  const d = new DrawContext();
  d.size = new Size((n * dm + (n - 1) * vao) * esc, dm * esc);
  d.opaque = false;
  d.respectScreenScale = false;
  for (let i = 0; i < n; i++) {
    d.setFillColor(i < feitos ? corA(COR_HABITO) : tom(0.2));
    d.fillEllipse(new Rect(i * (dm + vao) * esc, 0, dm * esc, dm * esc));
  }
  return d.getImage();
}

// "terça, 13 out" sem depender de Intl
const DIAS_SEMANA = ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"];
const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
function dataCurta(data) {
  const d = data instanceof Date ? data : new Date();
  return `${DIAS_SEMANA[d.getDay()]}, ${d.getDate()} ${MESES[d.getMonth()]}`;
}

// ---- blocos da tela de inicio ----

// PRÓXIMO: simbolo + rotulo + "em X" em pilula, hora grande, titulo
function blocoProximo(pai, prox, opcoes) {
  const o = opcoes || {};
  const topo = pai.addStack();
  topo.layoutHorizontally();
  topo.centerAlignContent();
  cabecalho(topo, prox ? simboloDoTipo(prox.tipo) : "calendar", "PRÓXIMO", COR_DESTAQUE);
  if (prox && o.pilulaNoTopo !== false) {
    topo.addSpacer();
    pilula(topo, quandoTexto(prox.em_minutos), prox.em_minutos <= 30);
  }
  pai.addSpacer(o.compacto ? 3 : 5);
  if (!prox) {
    textoHome(pai, "Dia livre", Font.boldRoundedSystemFont(o.tamanhoHora ? Math.round(o.tamanhoHora * 0.75) : 20));
    textoHome(pai, "nada marcado agora", Font.mediumSystemFont(11), tom(0.65));
    return;
  }
  if (prox.hora) textoHome(pai, prox.hora, Font.boldRoundedSystemFont(o.tamanhoHora || 28));
  textoHome(pai, prox.titulo, Font.semiboldSystemFont(o.tamanhoTitulo || 14), tom(0.95), o.linhasTitulo || 1);
}

// COMIDA compacta: aneis pequenos + kcal grande + meta e proteina
function blocoComidaLinha(pai, comida, tamanhoAnel, comMacros) {
  const linha = pai.addStack();
  linha.layoutHorizontally();
  linha.centerAlignContent();
  if (!comida) {
    adicionarSimbolo(linha, "camera.fill", 13, corA(COR_COMIDA));
    linha.addSpacer(6);
    textoHome(linha, "manda a foto do prato", Font.mediumSystemFont(11), tom(0.75));
    return linha;
  }
  adicionarAneisComida(linha, comida, tamanhoAnel || 40, false);
  linha.addSpacer(8);
  const col = linha.addStack();
  col.layoutVertically();
  const kc = col.addStack();
  kc.layoutHorizontally();
  kc.bottomAlignContent();
  textoHome(kc, milhar(comida.kcal), Font.boldRoundedSystemFont(17));
  kc.addSpacer(3);
  textoHome(kc, comida.meta_kcal ? `/ ${milhar(comida.meta_kcal)} kcal` : "kcal", Font.mediumRoundedSystemFont(10), tom(0.65));
  const prot = comida.meta_proteina_g
    ? `P ${milhar(comida.proteina_g)} / ${milhar(comida.meta_proteina_g)} g`
    : `P ${milhar(comida.proteina_g)} g`;
  textoHome(col, prot, Font.semiboldRoundedSystemFont(11), corA(COR_PROTEINA));
  if (comMacros && (comida.carbo_g !== undefined || comida.gordura_g !== undefined)) {
    textoHome(col, `C ${milhar(comida.carbo_g)} g · G ${milhar(comida.gordura_g)} g`, Font.mediumRoundedSystemFont(10), tom(0.6));
  }
  return linha;
}

// barras P/C/G: proteina contra a meta; carbo e gordura pela fatia de energia do dia
function blocoMacros(pai, comida, largura) {
  const p = Number(comida.proteina_g) || 0;
  const c = Number(comida.carbo_g) || 0;
  const g = Number(comida.gordura_g) || 0;
  const energia = p * 4 + c * 4 + g * 9 || 1;
  const fp = fracaoMeta(p, comida.meta_proteina_g);
  const linhas = [
    ["Proteína", p, fp !== null ? fp : (p * 4) / energia, COR_PROTEINA],
    ["Carbo", c, (c * 4) / energia, COR_CARBO],
    ["Gordura", g, (g * 9) / energia, COR_GORDURA],
  ];
  linhas.forEach(([nome, gramas, frac, cor], i) => {
    if (i) pai.addSpacer(5);
    const topo = pai.addStack();
    topo.layoutHorizontally();
    textoHome(topo, nome, Font.semiboldSystemFont(10), tom(0.75));
    topo.addSpacer();
    textoHome(topo, `${milhar(gramas)} g`, Font.semiboldRoundedSystemFont(10), corA(cor));
    pai.addSpacer(2);
    adicionarBarra(pai, frac, largura, cor, 4);
  });
}

// lista da agenda: simbolo + hora + titulo (+ "em X" a direita)
function blocoAgenda(pai, itens, opcoes) {
  const o = opcoes || {};
  itens.forEach((item, i) => {
    if (i) pai.addSpacer(o.espaco === undefined ? 5 : o.espaco);
    const linha = pai.addStack();
    linha.layoutHorizontally();
    linha.centerAlignContent();
    const feito = !!item.concluido;
    const opac = feito ? 0.45 : 1;
    adicionarSimbolo(linha, feito ? "checkmark.circle.fill" : simboloDoTipo(item.tipo), 11, feito ? corA(COR_HABITO) : corA(COR_DESTAQUE, 0.9));
    linha.addSpacer(6);
    const hora = linha.addStack();
    hora.size = new Size(o.larguraHora || 38, 0);
    textoHome(hora, item.hora || "", Font.semiboldRoundedSystemFont(12), tom(0.95 * opac));
    textoHome(linha, item.titulo, Font.mediumSystemFont(12), tom(0.9 * opac));
    if (o.comQuando && !feito) {
      linha.addSpacer();
      textoHome(linha, quandoTexto(item.em_minutos).replace("em ", ""), Font.mediumRoundedSystemFont(10), tom(0.55));
    } else {
      linha.addSpacer();
    }
  });
}

function blocoHabitos(pai, habitos) {
  cabecalho(pai, "repeat", "HÁBITOS", COR_HABITO);
  pai.addSpacer(4);
  if (!habitos || !habitos.total) {
    textoHome(pai, "nada pra hoje", Font.mediumSystemFont(11), tom(0.65));
    return;
  }
  const linha = pai.addStack();
  linha.layoutHorizontally();
  linha.bottomAlignContent();
  textoHome(linha, `${habitos.feitos}`, Font.boldRoundedSystemFont(22));
  textoHome(linha, ` / ${habitos.total}`, Font.semiboldRoundedSystemFont(13), tom(0.6));
  pai.addSpacer(4);
  if (habitos.total <= 10) {
    const n = Math.min(10, habitos.total);
    const dm = n > 7 ? 8 : 10;
    const img = pai.addImage(imagemPontosHabitos(habitos.feitos, habitos.total, dm));
    img.imageSize = new Size(n * dm + (n - 1) * Math.round(dm * 0.55), dm);
  }
}

function linhaConta(pai, conta) {
  if (!conta || !conta.nome) return;
  const linha = pai.addStack();
  linha.layoutHorizontally();
  linha.centerAlignContent();
  adicionarSimbolo(linha, "creditcard.fill", 10, tom(0.7));
  linha.addSpacer(4);
  const quando = conta.em_dias === 0 ? "vence hoje" : conta.em_dias === 1 ? "vence amanhã" : conta.em_dias < 0 ? "venceu" : `em ${conta.em_dias} dias`;
  textoHome(linha, `${conta.nome} · ${quando}`, Font.mediumSystemFont(10), conta.em_dias <= 1 ? corA(COR_PROTEINA) : tom(0.7));
}

function adicionarRodape(pai, sufixo) {
  if (!sufixo) return;
  pai.addSpacer(4);
  textoHome(pai, sufixo, Font.mediumSystemFont(9), tom(0.55));
}

// o que a tela de inicio prioriza, pelo Parameter (mesmo campo da tela de bloqueio)
// (le o Parameter direto: os modos da tela de bloqueio sao mais finos que isto)
function focoHome() {
  const bruto = (typeof args !== "undefined" && args && args.widgetParameter) || "";
  const m = String(bruto).trim().toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  if (!m || m.indexOf("|") !== -1 || /^https?:/.test(m)) return "ambos";
  if (/^(comida|kcal|aneis|proteina|macros)/.test(m)) return "comida";
  if (/^(agenda|prox|dia|contagem|tempo)/.test(m)) return "agenda";
  return "ambos";
}

// ---- layouts por tamanho ----

function homePequeno(widget, dados, sufixo) {
  const prox = proximoDe(dados);
  const comida = dados && dados.comida;
  const foco = focoHome();

  if (foco === "comida") {
    cabecalho(widget, "fork.knife", "COMIDA HOJE", COR_COMIDA);
    widget.addSpacer();
    const meio = widget.addStack();
    meio.layoutHorizontally();
    meio.addSpacer();
    if (comida) adicionarAneisComida(meio, comida, 86, true);
    else textoHome(meio, "manda a foto do prato", Font.mediumSystemFont(12), tom(0.75), 2);
    meio.addSpacer();
    widget.addSpacer();
    if (comida) {
      const base = widget.addStack();
      base.layoutHorizontally();
      base.addSpacer();
      textoHome(base, comidaKcalTexto(comida), Font.semiboldRoundedSystemFont(11), tom(0.85));
      base.addSpacer();
    }
    adicionarRodape(widget, sufixo);
    return;
  }

  if (foco === "agenda") {
    cabecalho(widget, "calendar", `HOJE · ${dataCurta().split(",")[0].toUpperCase()}`, COR_DESTAQUE);
    widget.addSpacer(8);
    const itens = agendaPendente(dados, 4);
    if (itens.length) blocoAgenda(widget, itens, { espaco: 6 });
    else blocoProximo(widget, prox, { tamanhoHora: 24 });
    widget.addSpacer();
    adicionarRodape(widget, sufixo);
    return;
  }

  blocoProximo(widget, prox, { tamanhoHora: 28, tamanhoTitulo: 13 });
  widget.addSpacer();
  if (comida) {
    blocoComidaLinha(widget, comida, 38, false);
  } else {
    const depois = agendaPendente(dados, 2)[1];
    if (depois) textoHome(widget, `depois · ${depois.hora} ${depois.titulo}`, Font.mediumSystemFont(10), tom(0.65));
  }
  adicionarRodape(widget, sufixo);
}

function homeMedio(widget, dados, sufixo) {
  const prox = proximoDe(dados);
  const comida = dados && dados.comida;
  const foco = focoHome();
  const colunas = widget.addStack();
  colunas.layoutHorizontally();
  colunas.topAlignContent();

  // esquerda: o proximo num card de vidro
  const esq = cartao(colunas, 10);
  esq.size = new Size(162, 0);
  blocoProximo(esq, prox, { tamanhoHora: 30, tamanhoTitulo: 14, linhasTitulo: 2 });
  const depois = agendaPendente(dados, 2)[1];
  if (depois) {
    esq.addSpacer();
    textoHome(esq, `depois · ${depois.hora} ${depois.titulo}`, Font.mediumSystemFont(10), tom(0.62));
  } else {
    esq.addSpacer();
  }
  colunas.addSpacer(12);

  const dir = colunas.addStack();
  dir.layoutVertically();
  if (foco === "agenda" || (!comida && foco !== "comida")) {
    cabecalho(dir, "calendar", "DEPOIS", COR_DESTAQUE);
    dir.addSpacer(6);
    const itens = agendaPendente(dados, 4).slice(1);
    if (itens.length) blocoAgenda(dir, itens, { espaco: 6, larguraHora: 36 });
    else textoHome(dir, "resto do dia livre", Font.mediumSystemFont(11), tom(0.65));
  } else if (foco === "comida" && comida) {
    cabecalho(dir, "fork.knife", "COMIDA HOJE", COR_COMIDA);
    dir.addSpacer(6);
    blocoMacros(dir, comida, 140);
  } else {
    cabecalho(dir, "fork.knife", "COMIDA HOJE", COR_COMIDA);
    dir.addSpacer(8);
    blocoComidaLinha(dir, comida, 58, true);
    if (dados && dados.habitos && dados.habitos.total) {
      dir.addSpacer(8);
      const h = dir.addStack();
      h.layoutHorizontally();
      h.centerAlignContent();
      adicionarSimbolo(h, "repeat", 10, corA(COR_HABITO));
      h.addSpacer(4);
      textoHome(h, `${dados.habitos.feitos}/${dados.habitos.total} hábitos`, Font.semiboldRoundedSystemFont(10), tom(0.8));
    }
  }
  dir.addSpacer();
  adicionarRodape(dir, sufixo);
}

function homeGrande(widget, dados, sufixo, paleta) {
  const prox = proximoDe(dados);
  const comida = dados && dados.comida;

  // saudacao + data + simbolo do periodo
  const topo = widget.addStack();
  topo.layoutHorizontally();
  topo.centerAlignContent();
  const ola = topo.addStack();
  ola.layoutVertically();
  textoHome(ola, `${paleta.saudacao}, Alex`, Font.boldRoundedSystemFont(19));
  textoHome(ola, dataCurta(), Font.mediumSystemFont(11), tom(0.65));
  topo.addSpacer();
  adicionarSimbolo(topo, paleta.simbolo, 22, corA(COR_META_BATIDA, 0.95));
  widget.addSpacer(10);

  // destaque: o proximo
  const hero = cartao(widget, 12);
  blocoProximo(hero, prox, { tamanhoHora: 34, tamanhoTitulo: 16 });
  widget.addSpacer(8);

  // agenda do resto do dia
  const resto = agendaPendente(dados, 4).slice(1);
  const ag = cartao(widget, 10);
  cabecalho(ag, "list.bullet", "DEPOIS", COR_DESTAQUE);
  ag.addSpacer(6);
  if (resto.length) blocoAgenda(ag, resto, { espaco: 5, comQuando: true });
  else textoHome(ag, "resto do dia livre", Font.mediumSystemFont(12), tom(0.65));
  widget.addSpacer(8);

  // comida | habitos + conta
  const base = widget.addStack();
  base.layoutHorizontally();
  base.topAlignContent();
  // os dois cards de baixo com a mesma altura (alturas diferentes lado a lado ficam desleixadas)
  const ALTURA_BASE = 92;
  const cc = cartao(base, 10);
  cc.size = new Size(186, ALTURA_BASE);
  cabecalho(cc, "fork.knife", "COMIDA HOJE", COR_COMIDA);
  cc.addSpacer(6);
  blocoComidaLinha(cc, comida, 50, true);
  cc.addSpacer();
  base.addSpacer(8);
  const ch = cartao(base, 10);
  ch.size = new Size(0, ALTURA_BASE); // 0 = largura livre: ocupa o resto da fileira
  blocoHabitos(ch, dados && dados.habitos);
  if (dados && dados.proxima_conta) {
    ch.addSpacer(6);
    linhaConta(ch, dados.proxima_conta);
  }
  ch.addSpacer();
  const enche = ch.addStack(); // stack com espacador = card estica ate a borda
  enche.addSpacer();
  widget.addSpacer();
  adicionarRodape(widget, sufixo);
}

// pede pro iOS atualizar perto do proximo compromisso (ele decide, mas costuma respeitar)
function agendarAtualizacao(widget, dados) {
  const prox = proximoDe(dados);
  let minutos = 15;
  if (prox && Number(prox.em_minutos) > 0) minutos = Math.max(1, Math.min(15, Number(prox.em_minutos)));
  widget.refreshAfterDate = new Date(Date.now() + minutos * 60000);
}

// ---- Tela de bloqueio desenhada (2026-10-13, Alex: "algo mais bonito ou maior, fica muito pequeno") ----
// O iOS nao deixa widget de tela de bloqueio maior que redondo/retangular/linha - entao o espaco e
// aproveitado: anel de progresso (estilo anel de Atividade) no redondo, numero grande + barra
// desenhada no retangular, e o retangular pode mostrar SO uma coisa (parametro "comida" ou
// "proximo") pra dois lado a lado ocuparem a linha inteira com letra grande.
// Tudo monocromatico: o iOS pinta a tela de bloqueio com "vibrancy" - branco opaco = cheio,
// branco transparente = trilho. Por isso desenho em DrawContext e so textOpacity nos textos
// (cor de texto/fundo e ignorada ou distorce nesses slots).

const branco = (alfa) => new Color("#ffffff", alfa);

// O que o widget de bloqueio mostra, escolhido pelo parametro do widget (sem acento, sem
// diferenca de maiuscula, vale o comeco da palavra). Redondo: (nada)=anel de kcal, aneis,
// proteina, contagem/tempo, habitos, proximo, comida. Retangular: (nada)=os dois, proximo, comida,
// agenda, dia, habitos, macros. Linha: o texto equivalente. Modo que nao existe numa familia cai
// no parecido (ver modoParaFamilia). Parametro com "|" ou comecando com http e configuracao
// (URL|TOKEN), nao modo.
const PREFIXOS_MODO = [
  ["comida", "comida"],
  ["kcal", "comida"],
  ["prox", "proximo"],
  ["aneis", "aneis"],
  ["anel", "aneis"],
  ["prot", "proteina"],
  ["cont", "contagem"],
  ["temp", "contagem"],
  ["hab", "habitos"],
  ["agen", "agenda"],
  ["dia", "dia"],
  ["macro", "macros"],
];

function modoDoWidget() {
  const bruto = (typeof args !== "undefined" && args && args.widgetParameter) || "";
  const m = String(bruto)
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .trim()
    .toLowerCase();
  if (!m || m.indexOf("|") !== -1 || /^https?:/.test(m)) return "ambos";
  const achado = PREFIXOS_MODO.find(([prefixo]) => m.indexOf(prefixo) === 0);
  return achado ? achado[1] : "ambos";
}

// Modo que so existe em outra familia vira o mais parecido (o mesmo parametro serve pros tres
// widgets da mesma pessoa sem ficar vazio).
function modoParaFamilia(modo, familia) {
  const trocas = {
    accessoryCircular: { agenda: "proximo", dia: "contagem", macros: "aneis" },
    accessoryRectangular: { aneis: "comida", proteina: "comida", contagem: "proximo" },
    accessoryInline: { aneis: "comida", proteina: "comida", dia: "contagem" },
  };
  const t = trocas[familia] || {};
  return t[modo] || modo;
}

// ---- Numeros e textos puros do widget de bloqueio ----

// numero finito ou null (nunca NaN: payload velho ou cache sem o campo nao pode virar "NaN")
function numeroOuNulo(v) {
  if (v === null || v === undefined || v === "" || typeof v === "boolean") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

// minutos compactos pro miolo do anel: 0 -> "agora", 25 -> "25m", 95 -> "1h35", 120 -> "2h"
function tempoCompacto(minutos) {
  const m = Math.max(0, Math.round(Number(minutos) || 0));
  if (m === 0) return "agora";
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  const resto = m % 60;
  return resto ? `${h}h${String(resto).padStart(2, "0")}` : `${h}h`;
}

// o anel da contagem esvazia conforme o compromisso chega: cheio a partir de 2h, vazio na hora
const JANELA_CONTAGEM_MIN = 120;
function fracaoContagem(minutos) {
  const m = numeroOuNulo(minutos);
  if (m === null) return 0;
  return Math.max(0, Math.min(1, m / JANELA_CONTAGEM_MIN));
}

// {feitos, total} dos habitos de hoje, ou null sem habito (ou payload sem o campo)
function habitosDe(dados) {
  const h = dados && dados.habitos;
  const total = numeroOuNulo(h && h.total);
  if (total === null || !(total > 0)) return null;
  const feitos = Math.max(0, Math.min(total, numeroOuNulo(h.feitos) || 0));
  return { feitos, total };
}

// P/C/G com a fatia de energia de cada um (P*4, C*4, G*9 sobre a soma); null se faltar algum dos
// tres (payload velho so tinha proteina) - ai o widget cai na comida simples.
function macrosDe(comida) {
  if (!comida) return null;
  const p = numeroOuNulo(comida.proteina_g);
  const c = numeroOuNulo(comida.carbo_g);
  const g = numeroOuNulo(comida.gordura_g);
  if (p === null || c === null || g === null) return null;
  const energia = [p * 4, c * 4, g * 9];
  const soma = energia[0] + energia[1] + energia[2];
  const fatia = (e) => (soma > 0 ? e / soma : 0);
  const meta = numeroOuNulo(comida.meta_proteina_g);
  return [
    { letra: "P", gramas: p, frac: fatia(energia[0]), meta: meta !== null && meta > 0 ? meta : null },
    { letra: "C", gramas: c, frac: fatia(energia[1]), meta: null },
    { letra: "G", gramas: g, frac: fatia(energia[2]), meta: null },
  ];
}

function gramasTexto(macro) {
  return macro.meta ? `${milhar(macro.gramas)}/${milhar(macro.meta)} g` : `${milhar(macro.gramas)} g`;
}

function truncar(texto, max) {
  const t = String(texto === undefined || texto === null ? "" : texto);
  return t.length > max ? `${t.slice(0, Math.max(1, max - 1)).trimEnd()}…` : t;
}

// o que ainda falta hoje: agenda pendente; sem agenda (payload velho) cai no foco
function itensDoDia(dados, foco) {
  const pend = agendaPendente(dados, 99);
  if (pend.length) return pend;
  return foco && foco.titulo ? [foco] : [];
}

// "14:30 Dentista · em 25 min" - o titulo encolhe pra o "em 25 min" nunca ser cortado
function linhaDoProximo(item, largura) {
  const m = numeroOuNulo(item.em_minutos);
  const fim = m === null ? "" : ` · ${quandoTexto(m)}`;
  const inicio = item.hora ? `${item.hora} ` : "";
  const orcamento = Math.max(6, (largura || 27) - inicio.length - fim.length);
  return `${inicio}${truncar(item.titulo, orcamento)}${fim}`;
}

// linha do tempo do resto do dia: vai ate o ultimo item (entre 1h e 6h a frente)
function horizonteDoDia(itens) {
  const ms = (itens || []).map((i) => numeroOuNulo(i && i.em_minutos)).filter((m) => m !== null && m >= 0);
  const ultimo = ms.length ? Math.max.apply(null, ms) : 0;
  return Math.max(60, Math.min(360, ultimo));
}

// posicao (0..1) de cada item que cabe na linha do tempo; indice e o do item na lista
function posicoesDoDia(itens, horizonte) {
  const out = [];
  (itens || []).forEach((item, indice) => {
    const m = numeroOuNulo(item && item.em_minutos);
    if (m === null || m < 0 || m > horizonte) return;
    out.push({ indice, frac: m / horizonte });
  });
  return out;
}

// bolinhas de habito: raio e passo conforme a quantidade (ate 16; acima disso o widget usa barra)
function geometriaPontos(total, largura, altura) {
  const n = Math.max(1, total);
  const raio = Math.max(2, Math.min(7, altura / 2 - 1.5, largura / n / 2 - 1.5));
  const passo = Math.min(largura / n, 2 * raio + 6);
  return { raio, passo, x0: raio + 1 };
}

function pontoNoCirculo(c, r, frac) {
  const a = -Math.PI / 2 + 2 * Math.PI * frac;
  return new Point(c + r * Math.cos(a), c + r * Math.sin(a));
}

function caminhoArco(c, r, frac) {
  const p = new Path();
  const passos = Math.max(2, Math.ceil(96 * frac));
  p.move(pontoNoCirculo(c, r, 0));
  for (let i = 1; i <= passos; i++) p.addLine(pontoNoCirculo(c, r, (frac * i) / passos));
  return p;
}

// Aneis concentricos estilo Atividade (compartilhado: tela de bloqueio e tela de inicio).
// aneis: [{frac 0..1, cor: Color, trilho: Color}], o 1o e o de fora. Desenhado grande (o iOS
// reduz e fica nitido). opcoes: {tamanho, espessura, vao, centro, rotulo, corTexto, corRotulo,
// fonteCentro, fonteRotulo}.
function imagemAneis(aneis, opcoes) {
  const o = opcoes || {};
  const T = o.tamanho || 120;
  const espessura = o.espessura || 12;
  const vao = o.vao === undefined ? 3 : o.vao;
  const c = T / 2;
  const d = new DrawContext();
  d.size = new Size(T, T);
  d.opaque = false;
  d.respectScreenScale = true;
  d.setLineWidth(espessura);
  (aneis || []).forEach((anel, i) => {
    const r = (T - espessura) / 2 - 1 - i * (espessura + vao);
    if (r <= espessura) return;
    const circulo = new Rect(c - r, c - r, 2 * r, 2 * r);
    d.setStrokeColor(anel.trilho || branco(0.22));
    d.strokeEllipse(circulo); // trilho fechado, sem emenda no topo
    const f = Math.max(0, Math.min(1, Number(anel.frac) || 0));
    const cor = anel.cor || branco(1);
    if (f >= 1) {
      d.setStrokeColor(cor);
      d.strokeEllipse(circulo);
    } else if (f > 0) {
      d.setStrokeColor(cor);
      d.addPath(caminhoArco(c, r, f));
      d.strokePath();
      // pontas arredondadas, como os aneis da Apple
      d.setFillColor(cor);
      [pontoNoCirculo(c, r, 0), pontoNoCirculo(c, r, f)].forEach((q) =>
        d.fillEllipse(new Rect(q.x - espessura / 2, q.y - espessura / 2, espessura, espessura))
      );
    }
  });
  if (o.centro !== undefined && o.centro !== null && o.centro !== "") {
    const centro = String(o.centro);
    const rotulo = o.rotulo;
    d.setTextAlignedCenter();
    d.setTextColor(o.corTexto || branco(1));
    // o slot redondo tem ~72pt: 120 desenhado vira ~0,6x - fonte 36 aqui = ~22 na tela
    const n = centro.length;
    const base = o.fonteCentro || 36;
    const tam = n <= 3 ? base : n === 4 ? Math.round(base * 0.83) : Math.round(base * 0.67);
    d.setFont(Font.boldRoundedSystemFont(tam));
    const altura = Math.round(tam * 1.22);
    d.drawTextInRect(centro, new Rect(0, rotulo ? c - altura * 0.62 : c - altura / 2, T, altura));
    if (rotulo) {
      const tr = o.fonteRotulo || 14;
      d.setTextColor(o.corRotulo || branco(0.7));
      d.setFont(Font.semiboldRoundedSystemFont(tr));
      d.drawTextInRect(rotulo, new Rect(0, c + altura * 0.3, T, Math.round(tr * 1.4)));
    }
  }
  return d.getImage();
}

// anel unico monocromatico (tela de bloqueio) com o numero no meio
function imagemAnel(frac, centro, rotulo) {
  return imagemAneis([{ frac }], { centro, rotulo });
}

// Simbolo da Apple (SF Symbols) como imagem; null se o nome nao existir (nunca quebra o widget)
function simbolo(nome, tamanho) {
  try {
    if (typeof SFSymbol === "undefined") return null;
    const s = SFSymbol.named(nome);
    if (!s) return null;
    if (tamanho && s.applyFont) s.applyFont(Font.semiboldSystemFont(tamanho));
    return s.image || null;
  } catch (e) {
    return null;
  }
}

// adiciona o simbolo num stack (tamanho em pt); cor so na tela de inicio (bloqueio e monocromatico)
function adicionarSimbolo(pai, nome, tamanho, cor, opacidade) {
  const img = simbolo(nome, tamanho);
  if (!img) return null;
  const w = pai.addImage(img);
  w.imageSize = new Size(tamanho, tamanho);
  if (cor) w.tintColor = cor;
  if (opacidade !== undefined) w.imageOpacity = opacidade;
  return w;
}

// barra arredondada (trilho translucido + preenchido opaco)
function imagemBarra(frac, largura, altura) {
  const esc = 3; // desenha em 3x pra borda ficar lisa
  const W = largura * esc;
  const H = altura * esc;
  const d = new DrawContext();
  d.size = new Size(W, H);
  d.opaque = false;
  d.respectScreenScale = false;
  const trilho = new Path();
  trilho.addRoundedRect(new Rect(0, 0, W, H), H / 2, H / 2);
  d.addPath(trilho);
  d.setFillColor(branco(0.25));
  d.fillPath();
  const f = Math.max(0, Math.min(1, Number(frac) || 0));
  if (f > 0) {
    const cheio = new Path();
    cheio.addRoundedRect(new Rect(0, 0, Math.max(H, W * f), H), H / 2, H / 2);
    d.addPath(cheio);
    d.setFillColor(branco(1));
    d.fillPath();
  }
  return d.getImage();
}

function adicionarBarraBloqueio(pai, frac, largura, altura) {
  const img = pai.addImage(imagemBarra(frac, largura, altura));
  img.imageSize = new Size(largura, altura);
  return img;
}

function textoBloqueio(pai, texto, fonte, opacidade) {
  const t = pai.addText(texto);
  t.font = fonte;
  if (opacidade !== undefined) t.textOpacity = opacidade;
  t.lineLimit = 1;
  t.minimumScaleFactor = 0.7;
  return t;
}

// linha do tempo do resto do dia (desenhada em 3x): trilho, marcador "agora" (anel vazado) a
// esquerda, o trecho ate o proximo item mais forte, bolinha por item (a do proximo maior, com
// halo). posicoes = posicoesDoDia(...): so o que cabe no horizonte.
function imagemLinhaDoDia(posicoes, largura, altura) {
  const esc = 3;
  const W = largura * esc;
  const H = altura * esc;
  const cy = H / 2;
  const d = new DrawContext();
  d.size = new Size(W, H);
  d.opaque = false;
  d.respectScreenScale = false;
  const margem = 7 * esc;
  const x0 = margem + 9 * esc; // onde comeca o futuro (depois do marcador de agora)
  const x1 = W - margem - 2 * esc; // folga pro halo da ultima bolinha nao ser cortado
  const grossura = 4 * esc;
  const trilho = new Path();
  trilho.addRoundedRect(new Rect(margem, cy - grossura / 2, W - 2 * margem, grossura), grossura / 2, grossura / 2);
  d.addPath(trilho);
  d.setFillColor(branco(0.25));
  d.fillPath();
  const xs = (posicoes || []).map((p) => x0 + p.frac * (x1 - x0));
  if (xs.length) {
    // espera ate o proximo: trecho do "agora" ate a 1a bolinha
    const espera = new Path();
    espera.addRoundedRect(new Rect(margem, cy - grossura / 2, Math.max(grossura, xs[0] - margem), grossura), grossura / 2, grossura / 2);
    d.addPath(espera);
    d.setFillColor(branco(0.85));
    d.fillPath();
  }
  // marcador de agora
  d.setLineWidth(2 * esc);
  d.setStrokeColor(branco(1));
  const ra = 5 * esc;
  d.strokeEllipse(new Rect(margem - ra + 1 * esc, cy - ra, 2 * ra, 2 * ra));
  xs.forEach((x, i) => {
    const proximo = i === 0;
    const r = (proximo ? 5 : 3.5) * esc;
    d.setFillColor(branco(proximo ? 1 : 0.9));
    d.fillEllipse(new Rect(x - r, cy - r, 2 * r, 2 * r));
    if (proximo) {
      const rh = 8.5 * esc;
      d.setLineWidth(1.5 * esc);
      d.setStrokeColor(branco(0.45));
      d.strokeEllipse(new Rect(x - rh, cy - rh, 2 * rh, 2 * rh));
    }
  });
  return d.getImage();
}

// bolinhas de habito: cheia = feito, so contorno = falta
function imagemPontos(feitos, total, largura, altura) {
  const esc = 3;
  const g = geometriaPontos(total, largura, altura);
  const d = new DrawContext();
  d.size = new Size(largura * esc, altura * esc);
  d.opaque = false;
  d.respectScreenScale = false;
  d.setLineWidth(1.6 * esc);
  const cy = (altura * esc) / 2;
  for (let i = 0; i < total; i++) {
    const cx = (g.x0 + i * g.passo) * esc;
    const r = g.raio * esc;
    if (i < feitos) {
      d.setFillColor(branco(1));
      d.fillEllipse(new Rect(cx - r, cy - r, 2 * r, 2 * r));
    } else {
      d.setStrokeColor(branco(0.4));
      // contorno por dentro do mesmo raio das cheias
      const ri = r - 0.8 * esc;
      d.strokeEllipse(new Rect(cx - ri, cy - ri, 2 * ri, 2 * ri));
    }
  }
  return d.getImage();
}

function adicionarImagemBloqueio(pai, imagem, largura, altura) {
  const img = pai.addImage(imagem);
  img.imageSize = new Size(largura, altura);
  return img;
}

// cabecalho pequeno: simbolo da Apple + rotulo em letra miuda (so o texto se o simbolo faltar)
function cabecalhoBloqueio(pai, nomeSimbolo, texto, opacidade) {
  const linha = pai.addStack();
  linha.layoutHorizontally();
  linha.centerAlignContent();
  if (adicionarSimbolo(linha, nomeSimbolo, 11, branco(1), 0.8)) linha.addSpacer(4);
  return textoBloqueio(linha, texto, Font.semiboldSystemFont(11), opacidade === undefined ? 0.7 : opacidade);
}

// ---- Redondo (~72pt) ----

function bloqueioCircular(widget, foco, comida, modo, sufixo, dados) {
  widget.setPadding(0, 0, 0, 0);
  modo = modoParaFamilia(modo, "accessoryCircular");
  const rot = (padrao) => (sufixo ? "salvo" : padrao); // dado do cache: nao finge estar ao vivo
  const fk = comida ? fracaoMeta(comida.kcal, comida.meta_kcal) : null;
  let img = null;

  if (modo === "aneis" && fk !== null) {
    // fora = kcal, dentro = proteina (so desenha o de dentro se houver meta de proteina)
    const fp = fracaoMeta(comida.proteina_g, comida.meta_proteina_g);
    const aneis = [{ frac: fk }];
    if (fp !== null) aneis.push({ frac: fp, cor: branco(0.7), trilho: branco(0.14) });
    img = imagemAneis(aneis, { centro: `${Math.round(fk * 100)}%`, espessura: 10, vao: 3, fonteCentro: 23 });
  } else if (modo === "proteina") {
    const gramas = comida ? numeroOuNulo(comida.proteina_g) : null;
    if (gramas === null) img = imagemAnel(0, "—", rot("prot"));
    else img = imagemAnel(fracaoMeta(gramas, comida.meta_proteina_g) || 0, `${milhar(gramas)}g`, rot("prot"));
  } else if (modo === "contagem") {
    const m = foco && foco.titulo ? numeroOuNulo(foco.em_minutos) : null;
    if (!foco || !foco.titulo) img = imagemAnel(0, "—", rot("livre"));
    else if (m === null) img = imagemAnel(0, "—", rot(foco.hora || ""));
    else img = imagemAnel(fracaoContagem(m), tempoCompacto(m), rot(foco.hora || ""));
  } else if (modo === "habitos") {
    const h = habitosDe(dados);
    img = h ? imagemAnel(h.feitos / h.total, `${h.feitos}/${h.total}`, rot("hábitos")) : imagemAnel(0, "—", rot("hábitos"));
  }

  if (!img) {
    // anel de kcal (padrao), ou a hora do proximo
    if (modo !== "proximo" && fk !== null) img = imagemAnel(fk, `${Math.round(fk * 100)}%`, sufixo ? "salvo" : "kcal");
    else if (modo !== "proximo" && comida) img = imagemAnel(0, milhar(comida.kcal), "kcal");
    else if (foco && foco.hora) img = imagemAnel(0, foco.hora, quandoTexto(foco.em_minutos).replace("em ", ""));
    else img = imagemAnel(0, "—", "livre");
  }
  const im = widget.addImage(img);
  im.centerAlignImage();
}

// ---- Retangular (~160x72pt) ----

// comida: kcal grande + barra de kcal + proteina (com barra) - o "comida" e o "ambos" sem foco
function retanguloComida(widget, comida, sufixo, largura) {
  if (!comida) {
    cabecalhoBloqueio(widget, "fork.knife", "Comida hoje");
    textoBloqueio(widget, "manda a foto do prato", Font.mediumSystemFont(13));
    return;
  }
  const topo = widget.addStack();
  topo.layoutHorizontally();
  topo.bottomAlignContent();
  textoBloqueio(topo, milhar(comida.kcal), Font.boldRoundedSystemFont(26));
  topo.addSpacer(4);
  textoBloqueio(topo, comida.meta_kcal ? `/ ${milhar(comida.meta_kcal)} kcal` : "kcal", Font.semiboldRoundedSystemFont(12), 0.7);
  const fk = fracaoMeta(comida.kcal, comida.meta_kcal);
  if (fk !== null) {
    widget.addSpacer(3);
    adicionarBarraBloqueio(widget, fk, largura, 7);
  }
  widget.addSpacer(5);
  const linhaProt = widget.addStack();
  linhaProt.layoutHorizontally();
  linhaProt.centerAlignContent();
  if (adicionarSimbolo(linhaProt, "fork.knife", 10, branco(1), 0.8)) linhaProt.addSpacer(4);
  textoBloqueio(linhaProt, sufixo || comidaProteinaTexto(comida), Font.semiboldSystemFont(11), 0.8);
  const fp = fracaoMeta(comida.proteina_g, comida.meta_proteina_g);
  if (fp !== null && !sufixo) {
    widget.addSpacer(3);
    adicionarBarraBloqueio(widget, fp, largura, 5);
  }
}

// proximo: so o compromisso, hora grande
function retanguloProximo(widget, foco, sufixo) {
  if (!foco || !foco.titulo) {
    cabecalhoBloqueio(widget, "calendar", "PRÓXIMO");
    textoBloqueio(widget, "Nada marcado agora", Font.semiboldSystemFont(15));
    if (sufixo) textoBloqueio(widget, sufixo, Font.mediumSystemFont(10), 0.7);
    return;
  }
  cabecalhoBloqueio(widget, simboloDoTipo(foco.tipo), `PRÓXIMO · ${quandoTexto(foco.em_minutos)}`);
  if (foco.hora) textoBloqueio(widget, foco.hora, Font.boldRoundedSystemFont(26));
  const t = textoBloqueio(widget, foco.titulo, Font.semiboldSystemFont(14));
  t.lineLimit = foco.hora ? 1 : 2;
  if (sufixo) textoBloqueio(widget, sufixo, Font.mediumSystemFont(10), 0.7);
}

// agenda: os proximos 3 pendentes, um por linha (o 1o maior), "+N" se tiver mais
function retanguloAgenda(widget, foco, dados, sufixo) {
  const todos = itensDoDia(dados, foco);
  if (!todos.length) {
    cabecalhoBloqueio(widget, "calendar", "AGENDA");
    textoBloqueio(widget, "Dia livre", Font.semiboldSystemFont(15));
    if (sufixo) textoBloqueio(widget, sufixo, Font.mediumSystemFont(10), 0.7);
    return;
  }
  const mostrados = todos.slice(0, 3);
  const extra = todos.length - mostrados.length;
  mostrados.forEach((item, i) => {
    const grande = i === 0;
    const linha = widget.addStack();
    linha.layoutHorizontally();
    linha.centerAlignContent();
    if (item.hora) {
      textoBloqueio(linha, item.hora, grande ? Font.boldRoundedSystemFont(16) : Font.semiboldRoundedSystemFont(12), grande ? undefined : 0.85);
      linha.addSpacer(5);
    }
    textoBloqueio(linha, item.titulo, grande ? Font.semiboldSystemFont(14) : Font.mediumSystemFont(12), grande ? undefined : 0.85);
    if (extra > 0 && i === mostrados.length - 1) {
      linha.addSpacer(4);
      textoBloqueio(linha, `+${extra}`, Font.semiboldRoundedSystemFont(11), 0.6);
    }
    if (i < mostrados.length - 1) widget.addSpacer(2);
  });
  if (sufixo) textoBloqueio(widget, sufixo, Font.mediumSystemFont(9), 0.7);
}

// dia: linha do tempo desenhada do resto de hoje, com o proximo em cima
function retanguloDia(widget, foco, dados, sufixo) {
  const largura = 148;
  const altura = 20;
  const itens = itensDoDia(dados, foco);
  if (!itens.length) {
    cabecalhoBloqueio(widget, "calendar", "RESTO DO DIA");
    textoBloqueio(widget, "Dia livre", Font.semiboldSystemFont(15));
    widget.addSpacer(3);
    adicionarImagemBloqueio(widget, imagemLinhaDoDia([], largura, altura), largura, altura);
    return;
  }
  const topo = widget.addStack();
  topo.layoutHorizontally();
  topo.centerAlignContent();
  const nomeSimbolo = simboloDoTipo(itens[0].tipo);
  const temSimbolo = !!adicionarSimbolo(topo, nomeSimbolo, 12, branco(1), 0.9);
  if (temSimbolo) topo.addSpacer(4);
  textoBloqueio(topo, linhaDoProximo(itens[0], temSimbolo ? 26 : 28), Font.semiboldSystemFont(12));
  widget.addSpacer(3);
  const pos = posicoesDoDia(itens, horizonteDoDia(itens));
  adicionarImagemBloqueio(widget, imagemLinhaDoDia(pos, largura, altura), largura, altura);
  widget.addSpacer(1);
  const rodape = widget.addStack();
  rodape.layoutHorizontally();
  textoBloqueio(rodape, sufixo || "agora", Font.mediumSystemFont(9), 0.6);
  const ultimo = pos.length ? itens[pos[pos.length - 1].indice] : null;
  if (ultimo && ultimo.hora && !sufixo) {
    rodape.addSpacer();
    textoBloqueio(rodape, ultimo.hora, Font.mediumSystemFont(9), 0.6);
  }
}

// habitos: "3/5" grande + uma bolinha por habito (cheia = feito)
function retanguloHabitos(widget, dados, sufixo) {
  const h = habitosDe(dados);
  if (!h) {
    cabecalhoBloqueio(widget, "checkmark.circle", "HÁBITOS");
    textoBloqueio(widget, "Nenhum hábito hoje", Font.semiboldSystemFont(15));
    if (sufixo) textoBloqueio(widget, sufixo, Font.mediumSystemFont(10), 0.7);
    return;
  }
  const largura = 148;
  const topo = widget.addStack();
  topo.layoutHorizontally();
  topo.bottomAlignContent();
  textoBloqueio(topo, `${h.feitos}/${h.total}`, Font.boldRoundedSystemFont(26));
  topo.addSpacer(5);
  if (adicionarSimbolo(topo, "checkmark.circle", 11, branco(1), 0.8)) topo.addSpacer(3);
  textoBloqueio(topo, "hábitos hoje", Font.semiboldRoundedSystemFont(12), 0.7);
  widget.addSpacer(5);
  if (h.total <= 16) {
    adicionarImagemBloqueio(widget, imagemPontos(h.feitos, h.total, largura, 16), largura, 16);
  } else {
    adicionarBarraBloqueio(widget, h.feitos / h.total, largura, 7);
  }
  if (sufixo) {
    widget.addSpacer(3);
    textoBloqueio(widget, sufixo, Font.mediumSystemFont(9), 0.7);
  }
}

// macros: tres barras finas P / C / G - o tamanho de cada uma e a fatia de energia
function retanguloMacros(widget, comida, sufixo) {
  const macros = macrosDe(comida);
  if (!macros) {
    retanguloComida(widget, comida, sufixo, 140); // payload velho: sem carbo/gordura, mostra a comida simples
    return;
  }
  cabecalhoBloqueio(widget, "fork.knife", sufixo || `${milhar(comida.kcal)} kcal`);
  widget.addSpacer(3);
  macros.forEach((macro, i) => {
    const linha = widget.addStack();
    linha.layoutHorizontally();
    linha.centerAlignContent();
    const letra = linha.addStack();
    letra.size = new Size(13, 0);
    textoBloqueio(letra, macro.letra, Font.boldRoundedSystemFont(12));
    linha.addSpacer(3);
    adicionarBarraBloqueio(linha, macro.frac, 76, 6);
    linha.addSpacer(6);
    textoBloqueio(linha, gramasTexto(macro), Font.semiboldRoundedSystemFont(11), 0.85);
    if (i < macros.length - 1) widget.addSpacer(3);
  });
}

function bloqueioRetangular(widget, foco, comida, modo, sufixo, dados) {
  widget.setPadding(0, 0, 0, 0);
  modo = modoParaFamilia(modo, "accessoryRectangular");
  const temFoco = !!(foco && foco.titulo);
  const largura = 140; // o slot retangular tem ~155-170pt conforme o iPhone

  if (modo === "agenda") return retanguloAgenda(widget, foco, dados, sufixo);
  if (modo === "dia") return retanguloDia(widget, foco, dados, sufixo);
  if (modo === "habitos") return retanguloHabitos(widget, dados, sufixo);
  if (modo === "macros") return retanguloMacros(widget, comida, sufixo);
  if (modo === "comida" || (modo === "ambos" && !temFoco && comida)) return retanguloComida(widget, comida, sufixo, largura);
  if (!temFoco || modo === "proximo" || !comida) return retanguloProximo(widget, foco, sufixo);

  // os dois: hora grande + quando, titulo, barra de kcal com o numero
  const topo = widget.addStack();
  topo.layoutHorizontally();
  topo.bottomAlignContent();
  if (adicionarSimbolo(topo, simboloDoTipo(foco.tipo), 13, branco(1), 0.8)) topo.addSpacer(4);
  if (foco.hora) {
    textoBloqueio(topo, foco.hora, Font.boldRoundedSystemFont(19));
    topo.addSpacer(5);
  }
  textoBloqueio(topo, quandoTexto(foco.em_minutos), Font.semiboldSystemFont(11), 0.7);
  textoBloqueio(widget, foco.titulo, Font.semiboldSystemFont(14));
  widget.addSpacer(4);
  const linha = widget.addStack();
  linha.layoutHorizontally();
  linha.centerAlignContent();
  if (adicionarSimbolo(linha, "fork.knife", 10, branco(1), 0.8)) linha.addSpacer(4);
  const fk = fracaoMeta(comida.kcal, comida.meta_kcal);
  if (fk !== null) {
    adicionarBarraBloqueio(linha, fk, 70, 6);
    linha.addSpacer(6);
  }
  textoBloqueio(linha, sufixo || `${milhar(comida.kcal)} kcal`, Font.semiboldRoundedSystemFont(11), 0.8);
}

// ---- Linha (acima do relogio): um simbolo da Apple + um texto so ----

function bloqueioLinha(widget, foco, comida, modo, dados) {
  modo = modoParaFamilia(modo, "accessoryInline");
  const temFoco = !!(foco && foco.titulo);
  const doFoco = temFoco ? `${foco.hora ? `${foco.hora} ` : ""}${foco.titulo}` : "";
  const m = temFoco ? numeroOuNulo(foco.em_minutos) : null;
  let nome = "calendar";
  let texto;

  if (modo === "comida") {
    nome = "fork.knife";
    texto = comida ? comidaKcalTexto(comida) : "manda a foto do prato";
  } else if (modo === "macros") {
    nome = "fork.knife";
    const macros = macrosDe(comida);
    texto = macros
      ? macros.map((x) => `${x.letra} ${milhar(x.gramas)}g`).join(" · ")
      : comida
        ? comidaKcalTexto(comida)
        : "manda a foto do prato";
  } else if (modo === "habitos") {
    nome = "checkmark.circle";
    const h = habitosDe(dados);
    texto = h ? `${h.feitos}/${h.total} hábitos` : "Sem hábitos hoje";
  } else if (modo === "agenda") {
    const todos = itensDoDia(dados, foco);
    texto = todos.length
      ? `${todos[0].hora ? `${todos[0].hora} ` : ""}${todos[0].titulo}${todos.length > 1 ? ` +${todos.length - 1}` : ""}`
      : "Dia livre";
    if (todos.length) nome = simboloDoTipo(todos[0].tipo);
  } else if (modo === "contagem") {
    texto = temFoco ? `${m === null ? "" : `${quandoTexto(m)} · `}${foco.titulo}` : "Nada marcado agora";
    if (temFoco) nome = simboloDoTipo(foco.tipo);
  } else {
    // ambos / proximo
    const partes = [];
    if (modo !== "comida" && temFoco) partes.push(doFoco);
    if (modo !== "proximo" && comida) partes.push(comidaKcalTexto(comida));
    texto = partes.join(" · ") || "Nada marcado agora";
    if (modo !== "proximo" && !temFoco && comida) nome = "fork.knife";
    else if (temFoco) nome = simboloDoTipo(foco.tipo);
  }
  adicionarSimbolo(widget, nome, 12, branco(1));
  widget.addText(texto);
}

// ---- Montagem visual ----

function corDe(hex) {
  return new Color(hex);
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
// vazio/erro/sem dados usam o mesmo anel (trilho vazio) - o redondo fica com a mesma cara sempre
function montarCircular(widget, numeroTexto, rotulo) {
  widget.setPadding(0, 0, 0, 0);
  widget.addImage(imagemAnel(0, numeroTexto, rotulo)).centerAlignImage();
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

// 2026-10-13: o Alex escolheu o que aparece - proximo compromisso/tarefa + comida do dia. Conta,
// habitos e IA continuam no JSON (linhas), so nao ocupam mais o widget.
function preencherNormal(widget, familia, dados, sufixo) {
  const foco = proximoDe(dados);
  const comida = dados && dados.comida;

  if (ehTelaBloqueio(familia)) {
    const modo = modoDoWidget();
    if (familia === "accessoryCircular") bloqueioCircular(widget, foco, comida, modo, sufixo, dados);
    else if (familia === "accessoryInline") bloqueioLinha(widget, foco, comida, modo, dados);
    else bloqueioRetangular(widget, foco, comida, modo, sufixo, dados);
    return;
  }

  const paleta = aplicarFundoHome(widget, familia);
  agendarAtualizacao(widget, dados);
  if (familia === "large") homeGrande(widget, dados, sufixo, paleta);
  else if (familia === "medium") homeMedio(widget, dados, sufixo);
  else homePequeno(widget, dados, sufixo); // small (e qualquer familia desconhecida)
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

  aplicarFundoHome(widget, familia);
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

  aplicarFundoHome(widget, familia);
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

  aplicarFundoHome(widget, familia);
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
  // tocar no widget abre o painel ja na tela da IA (chat). No iPhone isso abre no Safari (iOS nao
  // deixa link abrir o app da tela de inicio) - o login por PIN de la dura ~1 mes.
  const { url } = resolverConfig();
  if (url && /^https?:\/\//.test(url)) widget.url = `${url}/?aba=assistente`;

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
  if (familia === "large" && widget.presentLarge) return widget.presentLarge();
  if (familia === "accessoryCircular" && widget.presentAccessoryCircular) {
    return widget.presentAccessoryCircular();
  }
  if (familia === "accessoryRectangular" && widget.presentAccessoryRectangular) {
    return widget.presentAccessoryRectangular();
  }
  if (familia === "accessoryInline" && widget.presentAccessoryInline) {
    return widget.presentAccessoryInline();
  }
  if (widget.presentSmall) return widget.presentSmall();
}

// Diagnostico (2026-10-13): qualquer erro aparece NA TELA (previa/widget) e vai pro painel
// (POST /api/widget/erro -> data/widget.log no PC), em vez de o script morrer calado.
function textoDoErro(e) {
  const msg = (e && (e.message || String(e))) || "erro desconhecido";
  const linha = e && (e.line || e.lineNumber);
  return linha ? `${msg} (linha ${linha})` : msg;
}

async function reportarErro(etapa, e) {
  try {
    const { url, token } = resolverConfig();
    if (!/^https?:\/\//.test(url)) return;
    const req = new Request(`${url}/api/widget/erro`);
    req.method = "POST";
    req.headers = token
      ? { "Content-Type": "application/json", Authorization: `Bearer ${token}` }
      : { "Content-Type": "application/json" };
    req.body = JSON.stringify({ etapa, erro: textoDoErro(e), familia: obterFamilia() });
    req.timeoutInterval = 5;
    await req.loadString();
  } catch (_) {
    // sem rede pra avisar: o erro ainda aparece na tela
  }
}

function widgetDeErro(etapa, e) {
  const w = new ListWidget();
  const t = w.addText(`Widget do painel deu erro (${etapa}): ${textoDoErro(e)}`);
  t.font = Font.systemFont(11);
  t.minimumScaleFactor = 0.6;
  return w;
}

async function main() {
  const familia = obterFamilia();
  let widget;
  try {
    widget = await montarWidget();
  } catch (e) {
    console.error(`montar: ${textoDoErro(e)}`);
    await reportarErro("montar", e);
    widget = widgetDeErro("montar", e);
  }
  try {
    if (typeof config !== "undefined" && config && config.runsInWidget) {
      Script.setWidget(widget);
    } else {
      await apresentarPreview(widget, familia);
    }
  } catch (e) {
    console.error(`mostrar: ${textoDoErro(e)}`);
    await reportarErro("mostrar", e);
  }
  if (typeof Script !== "undefined" && Script.complete) Script.complete();
}

// Roda de verdade so dentro do Scriptable (globais reais). Em Node (testes),
// `module` existe e o script so exporta as funcoes puras, sem chamar main() -
// mesmo padrao usado em static/js/*.js (ver `typeof module !== "undefined"`).
// ATENCAO (2026-10-13, 1o teste no iPhone real): o Scriptable TAMBEM tem `module` (cada script e um
// modulo) - testar so `module` fazia o script nunca chamar main() no app (sem previa, widget
// vazio). Node se reconhece por `process.versions.node`, que o Scriptable nao tem.
const EM_NODE = typeof process !== "undefined" && !!(process.versions && process.versions.node);
if (EM_NODE && typeof module !== "undefined" && module.exports) {
  module.exports = {
    resolverConfig,
    obterFamilia,
    buscarDados,
    obterDados,
    lerCache,
    salvarCache,
    formatarAtualizadoHaX,
    linhasDeApoio,
    quandoTexto,
    comidaKcalTexto,
    modoDoWidget,
    imagemAneis,
    simbolo,
    proximoDe,
    agendaPendente,
    paletaDoHorario,
    misturarHex,
    dataCurta,
    montarWidget,
    main,
    modoParaFamilia,
    tempoCompacto,
    fracaoContagem,
    habitosDe,
    macrosDe,
    truncar,
    itensDoDia,
    linhaDoProximo,
    horizonteDoDia,
    posicoesDoDia,
    geometriaPontos,
  };
} else {
  main().catch((e) => console.error(`main: ${textoDoErro(e)}`));
}
