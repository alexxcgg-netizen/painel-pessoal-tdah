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

// barra fina de progresso feita de stacks (sem DrawContext): trilho com o preenchido dentro
function adicionarBarra(pai, fracao, largura, cor) {
  const altura = 5;
  const trilho = pai.addStack();
  trilho.layoutHorizontally();
  trilho.size = new Size(largura, altura);
  trilho.backgroundColor = corDe(COR_TRILHO);
  trilho.cornerRadius = altura / 2;
  const f = Math.max(0, Math.min(1, Number(fracao) || 0));
  if (f > 0) {
    const cheio = trilho.addStack();
    cheio.size = new Size(Math.max(altura, Math.round(largura * f)), altura);
    cheio.backgroundColor = corDe(cor);
    cheio.cornerRadius = altura / 2;
  }
  trilho.addSpacer();
}

function adicionarRotulo(pai, texto, cor) {
  const t = pai.addText(texto);
  t.textColor = corDe(cor);
  t.font = Font.boldSystemFont(10);
  return t;
}

// bloco "PRÓXIMO": hora grande + "em 25 min", titulo embaixo
function blocoProximo(pai, foco, compacto) {
  adicionarRotulo(pai, "PRÓXIMO", COR_DESTAQUE);
  pai.addSpacer(4);
  if (!foco || !foco.titulo) {
    const livre = pai.addText("Nada marcado agora");
    livre.textColor = corDe(COR_TEXT_MUTED);
    livre.font = Font.systemFont(13);
    livre.minimumScaleFactor = 0.8;
    return;
  }
  const linha = pai.addStack();
  linha.layoutHorizontally();
  if (linha.bottomAlignContent) linha.bottomAlignContent();
  if (foco.hora) {
    const hora = linha.addText(foco.hora);
    hora.textColor = corDe(COR_TEXT);
    hora.font = Font.boldSystemFont(compacto ? 20 : 24);
    linha.addSpacer(6);
  }
  const quando = linha.addText(quandoTexto(foco.em_minutos));
  quando.textColor = corDe(COR_TEXT_MUTED);
  quando.font = Font.systemFont(11);
  pai.addSpacer(2);
  const titulo = pai.addText(foco.titulo);
  titulo.textColor = corDe(COR_TEXT);
  titulo.font = Font.systemFont(compacto ? 13 : 14);
  titulo.lineLimit = 2;
  titulo.minimumScaleFactor = 0.8;
}

// bloco "COMIDA HOJE": kcal contra a meta + barra; no medio tambem proteina + barra
function blocoComida(pai, comida, largura, completo) {
  adicionarRotulo(pai, "COMIDA HOJE", COR_COMIDA);
  pai.addSpacer(4);
  const kcal = pai.addText(comidaKcalTexto(comida));
  kcal.textColor = corDe(COR_TEXT);
  kcal.font = Font.boldSystemFont(completo ? 15 : 12);
  kcal.minimumScaleFactor = 0.7;
  kcal.lineLimit = 1;
  const fk = fracaoMeta(comida.kcal, comida.meta_kcal);
  if (fk !== null) {
    pai.addSpacer(4);
    adicionarBarra(pai, fk, largura, COR_COMIDA);
  }
  if (!completo) return;
  pai.addSpacer(8);
  const prot = pai.addText(comidaProteinaTexto(comida));
  prot.textColor = corDe(COR_TEXT_MUTED);
  prot.font = Font.systemFont(11);
  prot.minimumScaleFactor = 0.7;
  prot.lineLimit = 1;
  const fp = fracaoMeta(comida.proteina_g, comida.meta_proteina_g);
  if (fp !== null) {
    pai.addSpacer(4);
    adicionarBarra(pai, fp, largura, COR_COMIDA);
  }
  pai.addSpacer(6);
  const n = Number(comida.refeicoes) || 0;
  const ref = pai.addText(n ? `${n} ${n === 1 ? "refeição" : "refeições"} pela foto` : "manda a foto do prato no chat");
  ref.textColor = corDe(COR_TEXT_FAINT);
  ref.font = Font.systemFont(9);
}

function adicionarRodape(pai, sufixo) {
  if (!sufixo) return;
  pai.addSpacer(6);
  const rodape = pai.addText(sufixo);
  rodape.textColor = corDe(COR_TEXT_FAINT);
  rodape.font = Font.systemFont(9);
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

// O que o widget de bloqueio mostra: parametro "comida", "proximo" ou nada (os dois).
// Parametro com "|" ou comecando com http e configuracao (URL|TOKEN), nao modo.
function modoDoWidget() {
  const bruto = (typeof args !== "undefined" && args && args.widgetParameter) || "";
  const m = String(bruto).trim().toLowerCase();
  if (!m || m.indexOf("|") !== -1 || /^https?:/.test(m)) return "ambos";
  if (m.indexOf("comida") === 0 || m.indexOf("kcal") === 0) return "comida";
  if (m.indexOf("prox") === 0 || m.indexOf("próx") === 0) return "proximo";
  return "ambos";
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
function adicionarSimbolo(pai, nome, tamanho, cor) {
  const img = simbolo(nome, tamanho);
  if (!img) return null;
  const w = pai.addImage(img);
  w.imageSize = new Size(tamanho, tamanho);
  if (cor) w.tintColor = cor;
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

function bloqueioCircular(widget, foco, comida, modo, sufixo) {
  widget.setPadding(0, 0, 0, 0);
  let img;
  const fk = comida ? fracaoMeta(comida.kcal, comida.meta_kcal) : null;
  if (modo !== "proximo" && fk !== null) img = imagemAnel(fk, `${Math.round(fk * 100)}%`, sufixo ? "salvo" : "kcal");
  else if (modo !== "proximo" && comida) img = imagemAnel(0, milhar(comida.kcal), "kcal");
  else if (foco && foco.hora) img = imagemAnel(0, foco.hora, quandoTexto(foco.em_minutos).replace("em ", ""));
  else img = imagemAnel(0, "—", "livre");
  const im = widget.addImage(img);
  im.centerAlignImage();
}

function bloqueioRetangular(widget, foco, comida, modo, sufixo) {
  widget.setPadding(0, 0, 0, 0);
  const temFoco = !!(foco && foco.titulo);
  const largura = 140; // o slot retangular tem ~155-170pt conforme o iPhone

  if (modo === "comida" || (modo === "ambos" && !temFoco && comida)) {
    if (!comida) {
      textoBloqueio(widget, "Comida hoje", Font.semiboldSystemFont(12), 0.7);
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
    textoBloqueio(widget, sufixo || comidaProteinaTexto(comida), Font.semiboldSystemFont(11), 0.8);
    const fp = fracaoMeta(comida.proteina_g, comida.meta_proteina_g);
    if (fp !== null && !sufixo) {
      widget.addSpacer(3);
      adicionarBarraBloqueio(widget, fp, largura, 5);
    }
    return;
  }

  if (!temFoco) {
    textoBloqueio(widget, "PRÓXIMO", Font.semiboldSystemFont(11), 0.7);
    textoBloqueio(widget, "Nada marcado agora", Font.semiboldSystemFont(15));
    if (sufixo) textoBloqueio(widget, sufixo, Font.mediumSystemFont(10), 0.7);
    return;
  }

  if (modo === "proximo" || !comida) {
    textoBloqueio(widget, `PRÓXIMO · ${quandoTexto(foco.em_minutos)}`, Font.semiboldSystemFont(11), 0.7);
    if (foco.hora) textoBloqueio(widget, foco.hora, Font.boldRoundedSystemFont(26));
    const t = textoBloqueio(widget, foco.titulo, Font.semiboldSystemFont(14));
    t.lineLimit = foco.hora ? 1 : 2;
    if (sufixo) textoBloqueio(widget, sufixo, Font.mediumSystemFont(10), 0.7);
    return;
  }

  // os dois: hora grande + quando, titulo, barra de kcal com o numero
  const topo = widget.addStack();
  topo.layoutHorizontally();
  topo.bottomAlignContent();
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
  const fk = fracaoMeta(comida.kcal, comida.meta_kcal);
  if (fk !== null) {
    adicionarBarraBloqueio(linha, fk, 70, 6);
    linha.addSpacer(6);
  }
  textoBloqueio(linha, sufixo || `${milhar(comida.kcal)} kcal`, Font.semiboldRoundedSystemFont(11), 0.8);
}

// linha em cima do relogio: so um texto (o iOS usa o primeiro)
function bloqueioLinha(widget, foco, comida, modo) {
  const partes = [];
  if (modo !== "comida" && foco && foco.titulo) partes.push(`${foco.hora ? `${foco.hora} ` : ""}${foco.titulo}`);
  if (modo !== "proximo" && comida) partes.push(comidaKcalTexto(comida));
  widget.addText(partes.join(" · ") || "Nada marcado agora");
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
    if (familia === "accessoryCircular") bloqueioCircular(widget, foco, comida, modo, sufixo);
    else if (familia === "accessoryInline") bloqueioLinha(widget, foco, comida, modo);
    else bloqueioRetangular(widget, foco, comida, modo, sufixo);
    return;
  }

  aplicarFundoHome(widget);
  if (familia === "medium") {
    const colunas = widget.addStack();
    colunas.layoutHorizontally();
    if (colunas.topAlignContent) colunas.topAlignContent();
    const esquerda = colunas.addStack();
    esquerda.layoutVertically();
    // 0 = altura livre (Scriptable); largura fixa so com as duas colunas, pra titulo longo nao
    // espremer a comida
    if (comida) esquerda.size = new Size(150, 0);
    blocoProximo(esquerda, foco, false);
    if (comida) {
      colunas.addSpacer(16);
      const direita = colunas.addStack();
      direita.layoutVertically();
      blocoComida(direita, comida, 150, true);
    } else {
      colunas.addSpacer();
    }
    widget.addSpacer();
    adicionarRodape(widget, sufixo);
    return;
  }

  // small (e qualquer familia desconhecida)
  blocoProximo(widget, foco, true);
  widget.addSpacer();
  if (comida) blocoComida(widget, comida, 126, false);
  adicionarRodape(widget, sufixo);
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
    montarWidget,
    main,
  };
} else {
  main().catch((e) => console.error(`main: ${textoDoErro(e)}`));
}
