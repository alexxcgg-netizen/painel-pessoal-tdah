"""Cupom vira itens (Laboratorio v4, ideia "cupom", 30/10/2026): le a NFC-e pelo link do QR code.

O QR do cupom fiscal aponta pra consulta publica da SEFAZ do estado (host *.gov.br). O iPhone le o QR
com a camera nativa (o Safari nao tem BarcodeDetector e nao ha biblioteca de QR no projeto): o Alex
manda o LINK pro painel (colando no chat ou por um Atalho -> /api/atalho/capturar) e daqui sai o resto:

  texto -> link/chave (`extrair`) -> HTML da SEFAZ (`buscar_html`, so https + *.gov.br, timeout curto,
  tamanho limitado) -> itens/total/estabelecimento (`interpretar`) -> categoria por palavra-chave
  (`categorizar`, local, sem IA) -> tabela `cupons` (`salvar`).

Honestidade sobre o leitor: cada estado tem a propria pagina. `interpretar` entende o layout mais usado
(tabela `tabResult` com `txtTit`/`Rqtd`/`RUN`/`valor` e total em `totalNumb`); pagina de outro layout
levanta `NfceErro("layout")` e o card diz que nao deu, em vez de chutar. So a chave de acesso (44
digitos) NAO basta: a consulta por chave pede captcha, entao o painel pede o link do QR.

Dinheiro PESSOAL do Alex. Nunca toca o banco nem a API da construtora.
"""

from __future__ import annotations

import html as _html
import json
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT_S = 8
TAMANHO_MAX = 1_500_000  # bytes de HTML lidos da SEFAZ
MAX_ITENS = 300

CATEGORIAS = ("Comida", "Besteira", "Limpeza", "Suplemento", "Outros")
# cores do protótipo (var(--c-grana)/perigo/c-tempo/c-saude no app viram tokens do card)
COR_CATEGORIA = {"Comida": "#b5e48c", "Besteira": "#f47671", "Limpeza": "#8fd0ff", "Suplemento": "#c4a1ff", "Outros": "#8a94a3"}


class NfceErro(Exception):
    """`codigo`: link | rede | layout | vazio. `args[0]` = frase pro Alex."""

    def __init__(self, mensagem: str, codigo: str = "rede"):
        super().__init__(mensagem)
        self.codigo = codigo


_RE_URL = re.compile(r"https?://[^\s<>\"']+", re.I)
_RE_CHAVE = re.compile(r"(?<!\d)(?:\d[\s.]?){43}\d(?!\d)")


def _so_digitos(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def _host_ok(host: str | None) -> bool:
    h = (host or "").lower().rstrip(".")
    return bool(h) and (h == "gov.br" or h.endswith(".gov.br"))


def _chave_do_link(url: str) -> str | None:
    q = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(q.query)
    for nome in ("chNFe", "chnfe", "p", "chave"):
        for v in params.get(nome, []):
            m = re.match(r"\s*(\d{44})", v)
            if m:
                return m.group(1)
    m = re.search(r"(?<!\d)(\d{44})(?!\d)", url)
    return m.group(1) if m else None


def extrair(texto) -> dict | None:
    """Acha no texto livre o link do QR de uma NFC-e (https + *.gov.br) e/ou a chave de acesso.
    Devolve {"url": str|None, "chave": str|None} ou None se nao ha nada com cara de cupom.
    Sem rede, sem banco - e a mesma funcao que a regra local usa pra decidir se a frase e dele."""
    if not isinstance(texto, str) or not texto.strip():
        return None
    for m in _RE_URL.finditer(texto):
        url = m.group(0).rstrip(".,;)")
        p = urllib.parse.urlparse(url)
        if p.scheme != "https" or not _host_ok(p.hostname):
            continue
        chave = _chave_do_link(url)
        # link *.gov.br qualquer (ex.: noticia) nao e cupom: precisa carregar a chave ou ter cara de NFC-e
        if chave or re.search(r"nfce|nfe|qrcode|fazenda|sefaz", url, re.I):
            return {"url": url, "chave": chave}
    m = _RE_CHAVE.search(texto)
    if m:
        d = _so_digitos(m.group(0))
        if len(d) == 44:
            return {"url": None, "chave": d}
    return None


# ---------------------------------------------------------------- rede


class _SemRedirForaDeGov(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        p = urllib.parse.urlparse(newurl)
        if p.scheme != "https" or not _host_ok(p.hostname):
            raise NfceErro("A SEFAZ me mandou pra um endereço que não é do governo — parei por segurança.", "link")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def buscar_html(url: str) -> str:
    """GET no link do QR. So https e host *.gov.br (inclusive nos redirects), timeout curto, corpo
    limitado. Qualquer falha de rede vira NfceErro com frase pronta (nunca stack trace pro card)."""
    p = urllib.parse.urlparse(url or "")
    if p.scheme != "https" or not _host_ok(p.hostname):
        raise NfceErro("Esse link não é de uma consulta da SEFAZ (precisa ser https e terminar em .gov.br).", "link")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (painel-pessoal)", "Accept": "text/html"})
    opener = urllib.request.build_opener(_SemRedirForaDeGov)
    try:
        with opener.open(req, timeout=TIMEOUT_S) as r:
            bruto = r.read(TAMANHO_MAX + 1)
            carga = r.headers.get_content_charset() or "utf-8"
    except NfceErro:
        raise
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise NfceErro("A SEFAZ não respondeu agora. Tenta o mesmo link de novo daqui a pouco.", "rede") from None
    if len(bruto) > TAMANHO_MAX:
        raise NfceErro("A página da nota veio grande demais — não li.", "layout")
    try:
        return bruto.decode(carga, errors="replace")
    except LookupError:
        return bruto.decode("utf-8", errors="replace")


# ---------------------------------------------------------------- leitura do HTML


def _limpa(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", _html.unescape(s)).strip()


def _num(s: str | None) -> float | None:
    if not s:
        return None
    t = s.strip().replace("\xa0", "").replace(" ", "")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        v = float(t)
    except ValueError:
        return None
    return v if v == v and abs(v) < 1e9 else None


def interpretar(html: str) -> dict:
    """HTML da NFC-e -> {estabelecimento, emitido_em ISO|None, total, itens:[{nome, qtd, un, valor,
    categoria}]}. Levanta NfceErro("layout") se nao reconhecer a pagina."""
    if not isinstance(html, str) or "txtTit" not in html:
        raise NfceErro("Não reconheci o layout dessa nota (cada estado tem o seu). Me avisa o estado que eu ensino.", "layout")
    itens = []
    for linha in re.split(r"<tr\b", html, flags=re.I)[1:]:
        m_nome = re.search(r"class=\"txtTit[^\"]*\"[^>]*>(.*?)</span>", linha, re.I | re.S)
        m_val = re.search(r"class=\"valor\"[^>]*>(.*?)</span>", linha, re.I | re.S)
        if not m_nome or not m_val:
            continue
        nome = _limpa(m_nome.group(1))
        valor = _num(_limpa(m_val.group(1)))
        if not nome or valor is None or valor < 0:
            continue
        m_q = re.search(r"class=\"Rqtd\"[^>]*>(.*?)</span>", linha, re.I | re.S)
        m_u = re.search(r"class=\"RUN\"[^>]*>(.*?)</span>", linha, re.I | re.S)
        qtd = _num(re.sub(r"^[^\d-]*", "", _limpa(m_q.group(1)))) if m_q else None
        un = re.sub(r"^[^A-Za-z]*", "", _limpa(m_u.group(1))) if m_u else ""
        itens.append({"nome": nome[:80], "qtd": qtd, "un": un[:6], "valor": round(valor, 2), "categoria": categorizar(nome)})
        if len(itens) >= MAX_ITENS:
            break
    if not itens:
        raise NfceErro("A nota abriu, mas não achei os itens nela.", "vazio")
    m_tot = re.search(r"class=\"totalNumb[^\"]*\"[^>]*>(.*?)</span>", html, re.I | re.S)
    total = _num(_limpa(m_tot.group(1))) if m_tot else None
    soma = round(sum(i["valor"] for i in itens), 2)
    # `totalNumb` aparece varias vezes (itens, desconto, a pagar); o primeiro e o total dos itens
    if total is None or total <= 0:
        total = soma
    m_est = re.search(r"class=\"txtTopo\"[^>]*>(.*?)</div>", html, re.I | re.S)
    estab = _limpa(m_est.group(1)) if m_est else ""
    return {
        "estabelecimento": (estab or "Cupom fiscal")[:80],
        "emitido_em": _data_emissao(html),
        "total": round(total, 2),
        "itens": itens,
    }


def _data_emissao(html: str) -> str | None:
    texto = _limpa(html)
    m = re.search(r"Emiss[aã]o:?\s*(\d{2})/(\d{2})/(\d{4})(?:\s+(\d{2}):(\d{2}))?", texto)
    if not m:
        return None
    d, mes, a, hh, mm = m.groups()
    try:
        import datetime as _dt
        _dt.date(int(a), int(mes), int(d))
    except ValueError:
        return None
    return f"{a}-{mes}-{d}" + (f"T{hh}:{mm}" if hh else "")


# ---------------------------------------------------------------- categorias (local, sem IA)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


_PALAVRAS = (
    ("Suplemento", ("whey", "creatina", "bcaa", "suplemento", "pre treino", "pre-treino", "albumina", "hipercalorico",
                    "glutamina", "termogenico", "barra de proteina", "proteina em po", "isolate", "colageno")),
    ("Limpeza", ("detergente", "sabao", "amaciante", "desinfetante", "agua sanitaria", "esponja", "papel higienico",
                 "papel toalha", "saco de lixo", "lava roupa", "lava-roupa", "limpador", "multiuso", "desengordurante",
                 "shampoo", "condicionador", "sabonete", "creme dental", "pasta de dente", "escova dental", "fio dental",
                 "desodorante", "absorvente", "cloro", "inseticida", "vassoura", "rodo", "pano de chao", "lenco umedecido")),
    ("Besteira", ("refrigerante", "coca", "guarana", "fanta", "sprite", "pepsi", "salgadinho", "doritos", "ruffles",
                  "cheetos", "chips", "biscoito recheado", "bolacha recheada", "oreo", "negresco", "trakinas",
                  "chocolate", "bombom", "bis ", "sorvete", "picole", "doce", "bala ", "balas", "chiclete", "pirulito",
                  "paçoca", "pacoca", "cerveja", "vodka", "energetico", "red bull", "monster", "pizza congelada",
                  "nuggets", "nutella", "refresco", "pipoca", "wafer", "bolinho", "rosquinha", "gelatina", "pudim",
                  "achocolatado", "snack")),
    ("Comida", ("arroz", "feijao", "frango", "carne", "bife", "patinho", "alcatra", "acem", "linguica", "salsicha",
                "peixe", "tilapia", "atum", "sardinha", "ovo", "leite", "queijo", "mussarela", "presunto", "iogurte",
                "manteiga", "margarina", "pao", "banana", "maca", "laranja", "limao", "mamao", "uva", "melancia",
                "abacaxi", "tomate", "cebola", "alho", "batata", "cenoura", "alface", "brocolis", "abobrinha",
                "pepino", "macarrao", "massa", "farinha", "aveia", "cafe", "acucar", "sal ", "oleo", "azeite",
                "molho", "extrato de tomate", "milho", "ervilha", "agua mineral", "agua ", "suco", "tapioca",
                "mandioca", "inhame", "batata doce", "pasta de amendoim", "castanha", "amendoim", "granola",
                "cuscuz", "fruta", "verdura", "legume", "hortifruti", "peito", "coxa", "file", "tempero", "vinagre")),
)


def categorizar(nome: str) -> str:
    n = " " + _norm(nome) + " "
    for cat, palavras in _PALAVRAS:
        for p in palavras:
            # inicio de palavra ("ovo" nao casa com "novo"), mas aceita plural/sufixo ("ovos", "bananas")
            if re.search(r"(?<![a-z])" + re.escape(_norm(p)), n):
                return cat
    return "Outros"


def por_categoria(itens: list[dict]) -> list[dict]:
    """[{nome, valor, itens, cor}] ordenado do maior pro menor; so categorias com valor."""
    soma: dict[str, list] = {}
    for i in itens:
        c = i.get("categoria") if i.get("categoria") in CATEGORIAS else "Outros"
        s = soma.setdefault(c, [0.0, 0])
        s[0] += float(i.get("valor") or 0)
        s[1] += 1
    return [
        {"nome": c, "valor": round(v, 2), "itens": n, "cor": COR_CATEGORIA[c]}
        for c, (v, n) in sorted(soma.items(), key=lambda kv: -kv[1][0])
        if v > 0
    ]


# ---------------------------------------------------------------- banco


def _linha_para_dict(r) -> dict:
    itens = json.loads(r["itens_json"] or "[]")
    return {
        "id": r["id"], "chave": r["chave"], "estabelecimento": r["estabelecimento"], "emitido_em": r["emitido_em"],
        "total": r["total"], "itens": itens, "gasto_id": r["gasto_id"], "criado_em": r["criado_em"],
    }


def buscar_salvo(conn, chave: str) -> dict | None:
    r = conn.execute("SELECT * FROM cupons WHERE chave = ?", (chave,)).fetchone()
    return _linha_para_dict(r) if r else None


def obter(conn, cupom_id: int) -> dict | None:
    r = conn.execute("SELECT * FROM cupons WHERE id = ?", (cupom_id,)).fetchone()
    return _linha_para_dict(r) if r else None


def salvar(conn, chave: str, lido: dict) -> dict:
    conn.execute(
        "INSERT OR IGNORE INTO cupons (chave, estabelecimento, emitido_em, total, itens_json) VALUES (?, ?, ?, ?, ?)",
        (chave, lido["estabelecimento"], lido.get("emitido_em"), lido["total"], json.dumps(lido["itens"], ensure_ascii=False)),
    )
    conn.commit()
    return buscar_salvo(conn, chave)  # type: ignore[return-value]


def ler_do_texto(conn, texto: str, buscar=None) -> dict:
    """Fluxo inteiro: texto livre -> cupom salvo (ou o que ja estava salvo). `buscar` e injetavel (teste).
    Levanta NfceErro com frase pronta."""
    achou = extrair(texto)
    if not achou:
        raise NfceErro("Não achei um link de cupom fiscal nisso.", "link")
    chave = achou["chave"]
    if chave:
        ja = buscar_salvo(conn, chave)
        if ja:
            return ja
    if not achou["url"]:
        raise NfceErro(
            "Só a chave não dá: a consulta por chave pede captcha. Aponta a câmera pro QR do cupom e me manda o link que abre.",
            "link",
        )
    lido = interpretar((buscar or buscar_html)(achou["url"]))
    # sem chave no link (alguns estados): a url inteira identifica a nota
    return salvar(conn, chave or "url:" + achou["url"][:300], lido)


def registrar_gasto(conn, cupom_id: int, hoje_iso: str) -> dict | None:
    """Vira linha em `expenses` (categoria 'mercado'). Se ja existe gasto do MESMO valor nos ultimos 3 dias
    (ex.: "gastei 312 no mercado" falado antes), so vincula - nunca duplica. Idempotente."""
    c = obter(conn, cupom_id)
    if not c:
        return None
    if c["gasto_id"]:
        return {"gasto_id": c["gasto_id"], "vinculado": True, "ja_estava": True}
    igual = conn.execute(
        "SELECT id FROM expenses WHERE ABS(amount - ?) < 0.005 AND tipo = 'real' AND date(created_at) >= date(?, '-3 day') "
        "ORDER BY id DESC LIMIT 1",
        (c["total"], hoje_iso),
    ).fetchone()
    if igual:
        gasto_id, vinculado = igual["id"], True
    else:
        from db import criar_gasto_de_brain_dump

        gasto_id = criar_gasto_de_brain_dump(conn, c["total"], "mercado", c["estabelecimento"], "cupom fiscal (NFC-e)")
        vinculado = False
    conn.execute("UPDATE cupons SET gasto_id = ? WHERE id = ?", (gasto_id, cupom_id))
    conn.commit()
    return {"gasto_id": gasto_id, "vinculado": vinculado, "ja_estava": False}


def total_por_categoria(conn, categoria: str, dias: int = 30) -> dict:
    """Quanto saiu em `categoria` nos cupons dos ultimos `dias` (pergunta "quanto eu gasto com besteira?")."""
    dias = max(1, min(int(dias), 366))
    soma, itens, cupons = 0.0, 0, 0
    for r in conn.execute("SELECT itens_json FROM cupons WHERE date(criado_em) >= date('now', ?)", (f"-{dias} day",)):
        achou = False
        for i in json.loads(r["itens_json"] or "[]"):
            if i.get("categoria") == categoria:
                soma += float(i.get("valor") or 0)
                itens += 1
                achou = True
        cupons += 1 if achou else 0
    return {"categoria": categoria, "total": round(soma, 2), "itens": itens, "cupons": cupons, "dias": dias}
