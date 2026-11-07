"""Nome curto de um compromisso pra caber num titulo de card (leva 07/11, frente B).

"Indo pro mecânico?" em vez de "Indo pro levar o carro no mecânico antes d" (titulo cru cortado em 48 letras);
"depois vem o dentista às 10h" em vez de juntar o titulo inteiro. Ordem: date/balada -> apelido salvo
(nome com acento pelo `onde_estou.nome_e_genero`) -> `local` curto -> lugar dito no titulo ("no mecânico",
"na casa da vó") -> o proprio titulo como frase. Corte so em palavra inteira, com "…". Zero IA, zero rede.

Genero: 'm' / 'f' / 'casa' / 'verbo' ("levar o carro": "Indo levar o carro?", "depois tu vai levar o carro").
"""

import re
import unicodedata

RETICENCIAS = "…"
_PEQUENAS = {"a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "com", "no", "na", "nos", "nas", "pra",
             "pro", "em", "às", "ao", "aos", "um", "uma", "para", "pelo", "pela", "que", "à", "até", "ate"}
_ARTIGO = {"o": "m", "a": "f", "os": "m", "as": "f", "no": "m", "na": "f", "do": "m", "da": "f", "pro": "m",
           "pra": "f"}
# preposicao + artigo -> genero do lugar que vem depois ("às" fica de fora: e hora)
_RE_LUGAR = re.compile(
    r"(?<!\w)(para o|para a|ao|aos|no|nos|na|nas|à|pro|pra|pelo|pela)\s+([^\W\d_][\w'’-]*)"
    r"((?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\w'’-]*){0,2})?"
    r"(\s+d[aoe]s?\s+[^\W\d_][\w'’-]*)?",
)
_GENERO_PREP = {"para o": "m", "ao": "m", "aos": "m", "no": "m", "nos": "m", "pro": "m", "pelo": "m",
                "para a": "f", "na": "f", "nas": "f", "à": "f", "pra": "f", "pela": "f"}
# "na hora", "pra amanhã"... nao sao lugar
_NAO_LUGAR = {"hora", "horas", "horario", "vez", "volta", "rua", "frente", "mesma", "mesmo", "boa", "real",
              "manha", "tarde", "noite", "semana", "amanha", "hoje", "ontem", "fila", "minha", "meu", "sua", "seu",
              "verdade", "boa", "certa", "certo", "proxima", "proximo", "ultima", "ultimo", "agenda", "lista"}
_RE_ATE = re.compile(r"\((at[eé]) (\d{1,2}):(\d{2})\)")


def _sem_acento(texto: str) -> str:
    base = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in base if not unicodedata.combining(c)).strip()


def cortar(texto: str, maximo: int) -> str:
    """Corta em palavra inteira com "…" (nunca "Sta às 2…" no meio da palavra, nem terminando em "de"/"o")."""
    t = " ".join((texto or "").split())
    if len(t) <= maximo:
        return t
    limite = max(1, maximo - 1)  # lugar do "…"
    fica: list[str] = []
    for p in t.split(" "):
        if len(" ".join(fica + [p])) > limite:
            break
        fica.append(p)
    while len(fica) > 1 and _sem_acento(fica[-1]) in _PEQUENAS:
        fica.pop()
    if not fica:  # uma palavra so, enorme
        return t[:limite] + RETICENCIAS
    return " ".join(fica).rstrip(" ,;:-—–.(/") + RETICENCIAS


def _frase(titulo: str) -> str:
    """'Levar o carro (até 09:00)' -> 'levar o carro' (maiuscula de comeco de frase cai; 'Sta' no meio fica)."""
    t = _RE_ATE.sub("", titulo or "").strip().rstrip(".")
    if len(t) > 1 and t[0].isupper() and not t[1].isupper():
        t = t[0].lower() + t[1:]
    return t


def _e_verbo(palavra: str) -> bool:
    p = _sem_acento(palavra)
    return len(p) > 3 and p.endswith(("ar", "er", "ir", "or")) and p not in ("lugar", "bar", "mar", "par", "jantar",
                                                                           "almocar", "colher", "mulher", "shopping")


def _genero_palavra(palavra: str) -> str:
    p = _sem_acento(palavra)
    if p.endswith(("ista", "ema")) or p in ("mapa", "sofa", "clima", "planeta"):
        return "m"  # "o dentista", "o problema"
    return "f" if p.endswith("a") else "m"


def _de_texto_livre(texto: str) -> tuple[str, str] | None:
    """'o mecânico' / 'Viva Beach' / 'Shopping Neumarkt' -> (nome, genero). So texto curto (endereco nao)."""
    palavras = (texto or "").split()
    if not palavras or len(palavras) > 4 or len(texto) > 30 or re.search(r"\d", texto):
        return None
    genero = None
    if len(palavras) > 1 and _sem_acento(palavras[0]) in _ARTIGO:
        genero = _ARTIGO[_sem_acento(palavras[0])]
        palavras = palavras[1:]
    nome = " ".join(palavras)
    if _sem_acento(nome) == "casa":
        return "casa", "casa"
    return nome, genero or _genero_palavra(palavras[0])


def _lugar_do_titulo(titulo: str) -> tuple[str, str] | None:
    for m in _RE_LUGAR.finditer(titulo or ""):
        prep, primeira, proprios, complemento = m.group(1), m.group(2), m.group(3) or "", m.group(4) or ""
        if _sem_acento(primeira) in _NAO_LUGAR or _e_verbo(primeira):
            continue
        prep = prep.lower()
        if _sem_acento(primeira) == "casa" and not complemento:
            return "casa", "casa"
        if primeira[:1].isupper():
            nome = primeira + proprios  # "no Shopping Neumarkt"
        else:
            nome = primeira
            if complemento and _sem_acento(complemento.split()[-1]) not in _NAO_LUGAR:
                nome += complemento  # "na casa da vó"
        return nome.strip(), _GENERO_PREP.get(prep, _genero_palavra(primeira))
    return None


def _campo(t, chave: str):
    try:
        return t[chave]
    except (KeyError, IndexError, TypeError):
        return None


def nome_e_genero(conn, t, maximo: int = 32) -> tuple[str, str]:
    """(nome curto, genero) de uma tarefa (Row ou dict com title/local/estilo)."""
    import onde_estou
    import vida_assistente

    titulo = (_campo(t, "title") or _campo(t, "titulo") or "").strip()
    local = (_campo(t, "local") or "").strip()
    estilo = _campo(t, "estilo")
    frase = _frase(titulo)
    if estilo in ("date", "balada"):
        if _sem_acento(frase).startswith(("date", "balada", "festa")):
            return cortar(frase, maximo), "f" if _sem_acento(frase).startswith(("balada", "festa")) else "m"
        return (estilo, "m" if estilo == "date" else "f")
    apelido = None
    if conn is not None:
        apelido = (vida_assistente.apelido_dentro(conn, local) if local else None) or \
            vida_assistente.apelido_dentro(conn, titulo)
    if apelido:
        nome, genero = onde_estou.nome_e_genero(apelido, [titulo, local])
        return cortar(nome, maximo), genero
    livre = _de_texto_livre(local) if local else None
    if livre:
        return cortar(livre[0], maximo), livre[1]
    do_titulo = _lugar_do_titulo(titulo)
    if do_titulo:
        return cortar(do_titulo[0], maximo), do_titulo[1]
    if not frase:
        return "", "m"
    primeira = frase.split()[0]
    return cortar(frase, maximo), "verbo" if _e_verbo(primeira) else _genero_palavra(primeira)


def pra(nome: str, genero: str) -> str:
    """Destino: 'pro mecânico', 'pra obra', 'pra casa', 'levar o carro' (verbo vai sem preposicao)."""
    if genero == "verbo":
        return nome
    if genero == "casa":
        return "pra casa"
    return f"{'pra' if genero == 'f' else 'pro'} {nome}"


def com_artigo(nome: str, genero: str) -> str:
    if genero in ("verbo", "casa"):
        return nome
    return f"{'a' if genero == 'f' else 'o'} {nome}"


def depois_vem(nome: str, genero: str) -> str:
    """'depois vem o dentista' / 'depois tu vai levar o carro' / 'depois é em casa'."""
    if genero == "verbo":
        return f"depois tu vai {nome}"
    if genero == "casa":
        return "depois é em casa"
    return f"depois vem {com_artigo(nome, genero)}"


def titulo_indo(conn, t, maximo: int = 48) -> str:
    """'Indo pro mecânico?' / 'Indo levar o carro?' - sempre <= maximo letras."""
    nome, genero = nome_e_genero(conn, t, maximo=maximo - 7)  # "Indo " + "?" + folga do "pro "
    base = pra(nome, genero)
    if len(base) + 6 > maximo:
        base = cortar(base, maximo - 6)
    return f"Indo {base}?"
