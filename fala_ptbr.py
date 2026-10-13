"""Texto escrito -> texto falavel em pt-BR, antes de mandar pro TTS.

O modelo rapido da ElevenLabs (eleven_flash_v2_5) le o texto cru: "14:30",
"R$ 1.250,90", "180g", "TDAH", "SBMT" e "2ª" saem errados ou em ingles, e a
normalizacao automatica deles nesse modelo e so do plano Enterprise. Aqui
cada coisa vira a forma que uma pessoa falaria ("catorze e trinta", "mil
duzentos e cinquenta reais e noventa centavos", "cento e oitenta gramas",
"tê dê á agá"...).

Sem dependencia nova: o numero por extenso e feito aqui mesmo. Nunca levanta
excecao - texto estranho volta do jeito que veio (o pior caso e a voz ler
como antes).
"""

from __future__ import annotations

import re

# ------------------------------------------------------------ numero por extenso

_UNIDADES = ["zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove",
             "dez", "onze", "doze", "treze", "catorze", "quinze", "dezesseis", "dezessete",
             "dezoito", "dezenove"]
_DEZENAS = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta",
            "oitenta", "noventa"]
_CENTENAS = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos",
             "seiscentos", "setecentos", "oitocentos", "novecentos"]


def _unidade(n: int, fem: bool) -> str:
    if fem and n == 1:
        return "uma"
    if fem and n == 2:
        return "duas"
    return _UNIDADES[n]


def _ate_999(n: int, fem: bool) -> str:
    if n == 100:
        return "cem"
    partes = []
    c, r = divmod(n, 100)
    if c:
        cent = _CENTENAS[c]
        partes.append(cent[:-2] + "as" if fem and c > 1 else cent)
    if r:
        if r < 20:
            partes.append(_unidade(r, fem))
        else:
            d, u = divmod(r, 10)
            partes.append(_DEZENAS[d])
            if u:
                partes.append(_unidade(u, fem))
    return " e ".join(partes)


def por_extenso(n: int, fem: bool = False) -> str:
    """Inteiro por extenso ("1234" -> "mil duzentos e trinta e quatro"); fem=True
    concorda com substantivo feminino ("duas horas", "duzentas calorias")."""
    if n < 0:
        return "menos " + por_extenso(-n, fem)
    if n == 0:
        return "zero"
    if n >= 10 ** 12:
        return " ".join(_UNIDADES[int(d)] for d in str(n))
    grupos = []  # (valor, texto)
    bi, resto = divmod(n, 10 ** 9)
    mi, resto = divmod(resto, 10 ** 6)
    mil, un = divmod(resto, 1000)
    if bi:
        grupos.append((bi, "um bilhão" if bi == 1 else _ate_999(bi, False) + " bilhões"))
    if mi:
        grupos.append((mi, "um milhão" if mi == 1 else _ate_999(mi, False) + " milhões"))
    if mil:
        grupos.append((mil, "mil" if mil == 1 else _ate_999(mil, fem) + " mil"))
    if un:
        grupos.append((un, _ate_999(un, fem)))
    texto = grupos[0][1]
    for i, (valor, parte) in enumerate(grupos[1:], start=1):
        ultimo = i == len(grupos) - 1
        # "mil e cem", "dois mil e cinquenta", mas "mil duzentos e trinta"
        junta = " e " if ultimo and (valor < 100 or valor % 100 == 0) else " "
        texto += junta + parte
    return texto


def _digitos(s: str) -> str:
    return " ".join(_UNIDADES[int(d)] for d in s if d.isdigit())


_ORD_UN = ["", "primeir", "segund", "terceir", "quart", "quint", "sext", "sétim", "oitav", "non"]
_ORD_DEZ = ["", "décim", "vigésim", "trigésim", "quadragésim", "quinquagésim", "sexagésim",
            "septuagésim", "octogésim", "nonagésim"]


def ordinal(n: int, fem: bool = False) -> str:
    if not 1 <= n <= 99:
        return por_extenso(n, fem)
    fim = "a" if fem else "o"
    d, u = divmod(n, 10)
    partes = []
    if d:
        partes.append(_ORD_DEZ[d] + fim)
    if u:
        partes.append(_ORD_UN[u] + fim)
    return " ".join(partes)


# ------------------------------------------------------------ genero da palavra seguinte

_MASCULINAS_EM_A = {
    "dia", "dias", "programa", "programas", "problema", "problemas", "sistema", "sistemas",
    "tema", "temas", "mapa", "mapas", "clima", "planeta", "planetas", "idioma", "idiomas",
    "grama", "gramas", "quilograma", "quilogramas", "miligrama", "miligramas", "cinema",
    "esquema", "esquemas", "telefonema", "pijama", "drama", "diploma", "diplomas", "poema",
}
_FEMININAS_SOLTAS = {
    "vez", "vezes", "mão", "mãos", "noite", "noites", "tarde", "tardes", "parte", "partes",
    "refeição", "refeições", "lição", "lições", "questão", "questões", "unidade", "unidades",
    "milha", "milhas", "libra", "libras", "série", "séries", "rep", "reps", "kcal",
}


def _feminino(palavra: str | None) -> bool:
    if not palavra:
        return False
    p = palavra.lower()
    if p in _MASCULINAS_EM_A:
        return False
    if p in _FEMININAS_SOLTAS:
        return True
    return p.endswith(("a", "as", "ção", "ções", "dade", "dades", "agem", "agens"))


# ------------------------------------------------------------ siglas e palavras dificeis

_LETRAS = {
    "A": "á", "B": "bê", "C": "cê", "D": "dê", "E": "é", "F": "éfe", "G": "gê", "H": "agá",
    "I": "i", "J": "jota", "K": "cá", "L": "éle", "M": "ême", "N": "ene", "O": "ó", "P": "pê",
    "Q": "quê", "R": "érre", "S": "ésse", "T": "tê", "U": "u", "V": "vê", "W": "dáblio",
    "X": "xis", "Y": "ípsilon", "Z": "zê",
}


def soletrar(sigla: str) -> str:
    return " ".join(_LETRAS.get(c.upper(), c) for c in sigla if c.isalnum())


# Siglas que se falam letra por letra.
_SOLETRADAS = {
    "TDAH", "IA", "IFR", "VFR", "IMC", "VMC", "QNH", "QNE", "ATC", "VOR", "ILS", "NDB", "ADF",
    "DME", "GPS", "CMA", "CHT", "PP", "PC", "PLA", "INVA", "MLTE", "MNTE", "CIV", "ATIS", "TWR",
    "APP", "CPF", "CNH", "RG", "CEP", "PDF", "API", "URL", "PWA", "SQL", "TTS", "USB", "ONG",
    "SUS", "INSS", "IPVA", "IPTU", "FGTS", "CLT", "PJ", "MEI", "CNPJ", "TI", "RH", "DJ", "TV",
    "PS", "UTC", "BR", "SP", "RJ", "SC", "PR", "MG", "RS",
}
# Siglas/palavras que se falam como palavra, com a grafia que o TTS acerta.
_COMO_PALAVRA = {
    "METAR": "métar", "TAF": "táfi", "NOTAM": "nôtam", "ANAC": "Anác", "DECEA": "Decéa",
    "AISWEB": "ais uéb", "SIGMET": "sigmét", "AIRMET": "érmét", "CAVOK": "cavoqui",
    "OK": "ó quêi", "Ok": "ó quêi", "ok": "ó quêi", "PIX": "pix", "Pix": "pix",
    "iOS": "ai ó ésse", "iPhone": "aifône", "WhatsApp": "uátsap", "app": "aplicativo", "apps": "aplicativos",
    "kcal": "calorias", "vs": "versus", "etc": "etcétera", "obs": "observação",
    "Obs": "Observação", "aprox": "aproximadamente", "hPa": "hectopascais",
}

_RE_SOLETRADA = re.compile(r"\b(" + "|".join(sorted(_SOLETRADAS, key=len, reverse=True)) + r")\b")
_RE_COMO_PALAVRA = re.compile(
    r"(?<![\w.])(" + "|".join(sorted(map(re.escape, _COMO_PALAVRA), key=len, reverse=True)) + r")(?!\w)"
)
_RE_ICAO = re.compile(r"\bS[BDNSW][A-Z]{2}\b")  # aerodromos brasileiros: SBSP, SDCO, SNxx, SSBL, SWxx
_RE_NIVEL = re.compile(r"\bFL\s?(\d{2,3})\b")
_RE_PISTA = re.compile(r"\b(?:pista|RWY)\s?(\d{2})([LRC])?\b", re.IGNORECASE)

# ------------------------------------------------------------ limpeza

_RE_URL = re.compile(r"https?://\S+|www\.\S+")
_RE_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF‍️←-⇿⬀-⯿]"
)
_RE_MARKDOWN = re.compile(r"[*_#`>|]+")

# ------------------------------------------------------------ numeros com contexto

_NUM = r"\d{1,3}(?:\.\d{3})+|\d+"  # 1.250 / 1250
_MESES = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
          "setembro", "outubro", "novembro", "dezembro"]


def _int(s: str) -> int:
    return int(s.replace(".", ""))


def _num_decimal(inteiro: str, decimal: str | None, fem: bool = False) -> str:
    base = por_extenso(_int(inteiro), fem)
    if not decimal:
        return base
    dec = decimal.rstrip("0") or "0"
    falado = _digitos(dec) if dec.startswith("0") or len(dec) > 3 else por_extenso(int(dec))
    return f"{base} vírgula {falado}"


def _dinheiro(m: re.Match) -> str:
    sinal, inteiro, centavos, escala = m.group("sinal"), m.group("int"), m.group("cent"), m.group("escala")
    pre = "menos " if sinal else ""
    if escala:
        valor = _num_decimal(inteiro, centavos)
        esc = escala.lower()
        esc = {"mi": "milhões", "bi": "bilhões", "k": "mil"}.get(esc, esc)
        if esc in ("milhão", "milhões") and _int(inteiro) == 1 and not centavos:
            esc = "milhão"
        de = "" if esc == "mil" else " de"
        return f"{pre}{valor} {esc}{de} reais"
    reais = _int(inteiro)
    cent = int((centavos or "0").ljust(2, "0")[:2])
    partes = []
    if reais or not cent:
        de = " de" if reais >= 10 ** 6 and reais % 10 ** 6 == 0 else ""
        partes.append(f"{por_extenso(reais)}{de} {'real' if reais == 1 else 'reais'}")
    if cent:
        partes.append(f"{por_extenso(cent)} {'centavo' if cent == 1 else 'centavos'}")
    return pre + " e ".join(partes)


def _hora(h: int, mi: int) -> str:
    nome = {0: "meia-noite", 12: "meio-dia"}.get(h)
    if mi == 0:
        return nome or f"{por_extenso(h, True)} {'hora' if h == 1 else 'horas'}"
    return f"{nome or por_extenso(h, True)} e {por_extenso(mi)}"


def _relogio(m: re.Match) -> str:
    grupos = m.groups()
    h, mi = int(grupos[0]), int(grupos[1] or 0) if len(grupos) > 1 else 0
    return _hora(h, mi)


def _duracao(m: re.Match) -> str:
    h, mi = int(m.group(1)), int(m.group(2))
    hs = f"{por_extenso(h, True)} {'hora' if h == 1 else 'horas'}"
    return f"{hs} e {por_extenso(mi)} {'minuto' if mi == 1 else 'minutos'}"


def _data(m: re.Match) -> str:
    d, mes, ano = int(m.group(1)), int(m.group(2)), m.group(3)
    if not (1 <= d <= 31 and 1 <= mes <= 12):
        return m.group(0)
    dia = "primeiro" if d == 1 else por_extenso(d)
    texto = f"{dia} de {_MESES[mes]}"
    if ano:
        a = int(ano)
        if len(ano) == 2:
            a += 2000
        texto += f" de {por_extenso(a)}"
    return texto


# unidade -> (singular, plural, feminino)
_UNIDADES_MEDIDA = {
    "kcal": ("caloria", "calorias", True),
    "cal": ("caloria", "calorias", True),
    "mg": ("miligrama", "miligramas", False),
    "kg": ("quilo", "quilos", False),
    "g": ("grama", "gramas", False),
    "ml": ("mililitro", "mililitros", False),
    "km/h": ("quilômetro por hora", "quilômetros por hora", False),
    "km": ("quilômetro", "quilômetros", False),
    "kt": ("nó", "nós", False),
    "kts": ("nó", "nós", False),
    "KT": ("nó", "nós", False),
    "ft": ("pé", "pés", False),
    "NM": ("milha náutica", "milhas náuticas", True),
    "nm": ("milha náutica", "milhas náuticas", True),
    "hPa": ("hectopascal", "hectopascais", False),
    "°C": ("grau", "graus", False),
    "ºC": ("grau", "graus", False),
    "°": ("grau", "graus", False),
    "min": ("minuto", "minutos", False),
}
_RE_UNIDADE = re.compile(
    r"(?<![\w,.])(?P<int>" + _NUM + r")(?:,(?P<dec>\d+))?\s?(?P<u>"
    + "|".join(sorted(map(re.escape, _UNIDADES_MEDIDA), key=len, reverse=True))
    + r")(?![\w/])"
)


def _unidade_medida(m: re.Match) -> str:
    sing, plur, fem = _UNIDADES_MEDIDA[m.group("u")]
    valor = _num_decimal(m.group("int"), m.group("dec"), fem)
    um = _int(m.group("int")) == 1 and not m.group("dec")
    return f"{valor} {sing if um else plur}"


def _numero_solto(m: re.Match) -> str:
    inteiro, dec, seguinte = m.group("int"), m.group("dec"), m.group("seg")
    bruto = inteiro.replace(".", "")
    if dec is None and len(bruto) > 1 and bruto.startswith("0"):
        falado = _digitos(bruto)  # "007", "0800" - le digito a digito
    elif dec is None and len(bruto) > 9:
        falado = _digitos(bruto)  # telefone, codigo
    else:
        falado = _num_decimal(inteiro, dec, _feminino(seguinte))
    return falado + (m.group("mil") or "") + (m.group("resto") or "")


# "2 mil calorias": o "mil" fica no meio, o genero vem da palavra depois dele.
_RE_NUMERO = re.compile(
    r"(?<![\w])(?P<int>" + _NUM + r")(?:[,.](?P<dec>\d+))?(?![\w])"
    r"(?P<mil>\s+mil\b)?(?P<resto>\s+(?P<seg>[^\W\d_]+))?"
)
_RE_MESES = "|".join(_MESES[1:])


def normalizar(texto: str) -> str:
    """Texto pronto pra ser falado. Ordem importa: do padrao mais especifico
    (dinheiro, hora, data, unidade) pro numero solto no fim."""
    if not isinstance(texto, str) or not texto.strip():
        return texto if isinstance(texto, str) else ""
    try:
        return _normalizar(texto)
    except Exception:  # nunca derruba a fala por causa de um texto estranho
        return texto


def _normalizar(t: str) -> str:
    t = _RE_URL.sub("", t)
    t = t.replace("->", ", ").replace("→", ", ").replace("•", ",")
    t = _RE_EMOJI.sub("", t)
    t = _RE_MARKDOWN.sub("", t)
    t = t.replace("…", "...").replace("–", "-").replace("—", ", ")

    # simbolos soltos
    t = re.sub(r"\s&\s", " e ", t)
    t = re.sub(r"(?<=\s)\+(?=\s?\d)", "mais ", t)
    t = re.sub(r"~\s?(?=\d)", "cerca de ", t)
    t = re.sub(r"(?<=\s)=(?=\s)", "igual a", t)

    # aviacao: nivel de voo, ajuste de altimetro, pista, aerodromo
    t = _RE_NIVEL.sub(lambda m: "nível " + _digitos(m.group(1)), t)
    t = re.sub(r"\b(QNH|QNE)\s?(\d{4})\b", lambda m: f"{m.group(1)} {_digitos(m.group(2))}", t)
    t = _RE_PISTA.sub(
        lambda m: "pista " + _digitos(m.group(1))
        + {"L": " esquerda", "R": " direita", "C": " central"}.get((m.group(2) or "").upper(), ""),
        t,
    )
    t = _RE_ICAO.sub(lambda m: soletrar(m.group(0)), t)

    # dinheiro: R$ 1.250,90 / R$ 2 mil / -R$ 30
    t = re.sub(
        r"(?P<sinal>-\s?)?R\$\s?(?P<int>" + _NUM + r")(?:,(?P<cent>\d{1,2}))?"
        r"(?:\s?(?P<escala>mil|milhão|milhões|mi|bi|k)\b)?",
        _dinheiro, t,
    )

    # horario: 1h30min (duracao), 14:30, 14h30, 14h, 9 h
    t = re.sub(r"\b(\d{1,2})h(\d{1,2})\s?min\b", _duracao, t)
    t = re.sub(r"\b([01]?\d|2[0-3])(?::|h)([0-5]\d)\b", _relogio, t)
    t = re.sub(r"\b([01]?\d|2[0-3])\s?h\b(?!\w)", _relogio, t)
    t = re.sub(r"\b(\d{1,3})\s?h\b(?!\w)", lambda m: f"{por_extenso(int(m.group(1)), True)} horas", t)

    # data: 2026-10-13, 13/10, 13/10/2026, "1 de outubro"
    t = re.sub(r"\b(\d{4})-(\d{2})-(\d{2})\b",
               lambda m: _data(re.match(r"(\d+)/(\d+)/(\d+)", f"{m.group(3)}/{m.group(2)}/{m.group(1)}")), t)
    t = re.sub(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{4}|\d{2}))?\b", _data, t)
    t = re.sub(r"\b1º?(?=\s+de\s+(?:" + _RE_MESES + r")\b)", "primeiro", t, flags=re.IGNORECASE)

    # ordinal: 1º, 2ª, 3o lugar ("25°" fica pra unidade, e grau)
    t = re.sub(r"\b(\d{1,2})[ºo](?![\w])", lambda m: ordinal(int(m.group(1))), t)
    t = re.sub(r"\b(\d{1,2})[ªa](?![\w])", lambda m: ordinal(int(m.group(1)), True), t)

    # vezes: 3x, 2x por semana (mas "3 x 4" e "por")
    t = re.sub(r"\b(\d{1,3})x\b", lambda m: f"{por_extenso(int(m.group(1)), True)} "
               + ("vez" if m.group(1) == "1" else "vezes"), t)
    t = re.sub(r"(?<=\d)\s[xX]\s(?=\d)", " por ", t)

    # porcentagem
    t = re.sub(
        r"(?<![\w,.])(" + _NUM + r")(?:,(\d+))?\s?%",
        lambda m: _num_decimal(m.group(1), m.group(2)) + " por cento", t,
    )

    # unidades: 180g, 2.000 kcal, 15 kt, 3x
    t = _RE_UNIDADE.sub(_unidade_medida, t)

    # intervalo: 10-12 -> 10 a 12
    t = re.sub(r"\b(\d{1,3})\s?-\s?(\d{1,3})\b", r"\1 a \2", t)

    # siglas
    t = _RE_COMO_PALAVRA.sub(lambda m: _COMO_PALAVRA[m.group(1)], t)
    t = _RE_SOLETRADA.sub(lambda m: soletrar(m.group(1)), t)

    # numero solto (com genero pela palavra seguinte)
    t = _RE_NUMERO.sub(_numero_solto, t)

    # acabamento
    t = re.sub(r"\s*\n+\s*", ". ", t)
    t = re.sub(r"\s+([,.!?])", r"\1", t)
    t = re.sub(r"([,.])\1+", r"\1", t)
    t = re.sub(r",\s*\.", ".", t)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()
