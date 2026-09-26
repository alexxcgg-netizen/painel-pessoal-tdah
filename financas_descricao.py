"""Modulo puro para gerar descricao de exibicao amigavel para transacoes financeiras
vindas do Nubank/Pluggy. Sem Flask, sem banco, sem chamadas de rede/IA.

Contrato principal: descrever(tx, por_external_id) -> dict
"""
import re
import unicodedata

# ---------------------------------------------------------------------------
# Normalizacao auxiliar
# ---------------------------------------------------------------------------


def _normalizar(s):
    """Remove acentos, baixa caixa, colapsa espacos. Sempre retorna string."""
    if s is None:
        return ""
    if not isinstance(s, str):
        try:
            s = str(s)
        except Exception:
            return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


# ---------------------------------------------------------------------------
# Prefixos de adquirente/gateway a remover
# ---------------------------------------------------------------------------

_PREFIXOS_ADQUIRENTE = [
    r"^ifd\*",
    r"^pag\*",
    r"^mp\*",
    r"^mercadopago\*",
    r"^picpay\*",
    r"^ebanx\*",
    r"^paypal\s*\*",
    r"^dl\*",
    r"^ec\s*\*",
    r"^rapp\*",
    r"^stone\*",
    r"^getnet\*",
    r"^cielo\*",
    r"^vero\*",
    r"^zoop\*",
    r"^pagseguro\*",
    r"^ame\*",
]

_SUFIXO_UF = re.compile(r"\s+[A-Z]{2}$")
_SUFIXO_PARCELA = re.compile(r"\s*[-/]?\s*(?:parc(?:ela)?\.?\s*)?(\d{1,2})\s*[/xX]\s*(\d{1,2})\s*$")
_SUFIXO_NUMEROS_SOLTOS = re.compile(r"\s+\d{4,}$")
_SUFIXO_CIDADE_TRUNCADA = re.compile(r"\s+[A-Z][a-z]{3,6}$")  # Palavras de 5-7 chars que parecem cidades truncadas

_SIGLAS_CURTAS = {
    "bk", "kfc", "cia", "sa", "ltda", "ne", "sp", "rj", "mg", "df", "pr", "sc", "rs",
    "usa", "uk", "tv", "app", "99", "c&a",
}

_PREPOSICOES_BAIXAS = {
    "de", "da", "do", "di", "du", "em", "em", "por", "para", "com", "sem", "sob", "e", "ou",
}


def _remover_prefixo_adquirente(s):
    for pat in _PREFIXOS_ADQUIRENTE:
        novo = re.sub(pat, "", s, flags=re.IGNORECASE)
        if novo != s:
            return novo.strip(" *-")
    return s


def _extrair_parcela(s):
    """Retorna (texto_sem_parcela, sufixo_parcela_ou_None)."""
    m = _SUFIXO_PARCELA.search(s)
    if m:
        parte = int(m.group(1))
        total = int(m.group(2))
        if 1 <= parte <= 99 and 1 <= total <= 99 and parte <= total:
            resto = s[: m.start()].strip()
            return resto, f"({parte}/{total})"
    return s, None


def _titulo(s):
    """Normaliza caixa para Titulo, preservando siglas curtas em maiusculo quando
    ja vinham em maiusculo (heuristica simples), e sem alterar tokens com digitos.
    Preposicoes ficam em minuscula (exceto primeira palavra)."""
    if not s:
        return s
    palavras = s.split(" ")
    resultado = []
    for i, p in enumerate(palavras):
        if not p:
            continue
        p_lower = p.lower()
        p_norm = _normalizar(p)
        if p_norm in _SIGLAS_CURTAS or (len(p) <= 3 and p.isupper() and p.isalpha()):
            resultado.append(p.upper())
        elif any(c.isdigit() for c in p):
            resultado.append(p)
        elif i > 0 and p_norm in _PREPOSICOES_BAIXAS:
            # Preposicoes ficam em minuscula (exceto na primeira posicao)
            resultado.append(p_lower)
        else:
            resultado.append(p_lower.capitalize())
    return " ".join(resultado)


def limpar_texto(bruto):
    """Limpa um texto cru de estabelecimento/descricao. Retorna (texto_limpo, parcela)."""
    s = bruto
    if s is None:
        return "", None
    if not isinstance(s, str):
        try:
            s = str(s)
        except Exception:
            return "", None
    s = s.strip()
    if not s:
        return "", None

    s = _remover_prefixo_adquirente(s)
    s, parcela = _extrair_parcela(s)
    # remove sufixo de cidade/UF tipo "RESTAURANTE X SAO PAULO SP"
    s = _SUFIXO_UF.sub("", s).strip()
    # remove numeros longos soltos no fim (codigos de terminal etc.)
    s = _SUFIXO_NUMEROS_SOLTOS.sub("", s).strip()
    # Para "Posto" entries, remove sufixo de cidade truncada
    if s.upper().startswith("POSTO"):
        s = _SUFIXO_CIDADE_TRUNCADA.sub("", s).strip()
    s = re.sub(r"\s+", " ", s).strip(" *-")

    s_titulo = _titulo(s)
    return s_titulo, parcela


# ---------------------------------------------------------------------------
# Tabela local: nome cru (normalizado, casamento por "contem") -> nome conhecido
# valor pode ser (nome, categoria_sugerida) ou apenas nome (str)
# ---------------------------------------------------------------------------

TABELA_ESTABELECIMENTOS = {
    "arcos dourados": ("McDonald's", "Alimentação"),
    "mcdonalds": ("McDonald's", "Alimentação"),
    "bk brasil": ("Burger King", "Alimentação"),
    "burger king": ("Burger King", "Alimentação"),
    "ifood": ("iFood", "Delivery"),
    "uber eats": ("Uber Eats", "Delivery"),
    "uber \\*trip": ("Uber", "Transporte"),
    "uber trip": ("Uber", "Transporte"),
    "uber": ("Uber", "Transporte"),
    "99app": ("99", "Transporte"),
    "99 tecnologia": ("99", "Transporte"),
    "raia": ("Droga Raia", "Farmácia"),
    "raia drogasil": ("Droga Raia", "Farmácia"),
    "drogasil": ("Droga Raia", "Farmácia"),
    "drogaraia": ("Droga Raia", "Farmácia"),
    "carrefour": ("Carrefour", "Mercado"),
    "assai": ("Assaí", "Mercado"),
    "atacadao": ("Atacadão", "Mercado"),
    "cia brasileira de distribuicao": ("Pão de Açúcar", "Mercado"),
    "pao de acucar": ("Pão de Açúcar", "Mercado"),
    "ebazar": ("Mercado Livre", "Compras Online"),
    "mercado livre": ("Mercado Livre", "Compras Online"),
    "amazon": ("Amazon", "Compras Online"),
    "netflix": ("Netflix", "Streaming"),
    "spotify": ("Spotify", "Streaming"),
    "apple": ("Apple", "Assinaturas"),
    "apple.com/bill": ("Apple", "Assinaturas"),
    "apple com bill": ("Apple", "Assinaturas"),
    "anthropic": ("Claude", "Serviços Digitais"),
    "claude": ("Claude", "Serviços Digitais"),
    "google": ("Google", "Serviços"),
    "shell": ("Shell", "Combustível"),
    "raizen": ("Raízen", "Combustível"),
    "ipiranga": ("Ipiranga", "Combustível"),
    "petrobras": ("Petrobras", "Combustível"),
    "br distribuidora": ("Petrobras", "Combustível"),
    "starbucks": ("Starbucks", "Alimentação"),
    "southrock": ("Starbucks", "Alimentação"),
    "subway": ("Subway", "Alimentação"),
    "outback": ("Outback", "Alimentação"),
    "bloomin": ("Outback", "Alimentação"),
    "madero": ("Madero", "Alimentação"),
    "localiza": ("Localiza", "Viagem"),
    "latam": ("Latam", "Viagem"),
    "gol linhas": ("Gol", "Viagem"),
    "azul linhas": ("Azul", "Viagem"),
    "smiles": ("Smiles", "Viagem"),
    "decolar": ("Decolar", "Viagem"),
    "booking": ("Booking", "Viagem"),
    "airbnb": ("Airbnb", "Viagem"),
    "lojas renner": ("Renner", "Compras"),
    "renner": ("Renner", "Compras"),
    "c&a": ("C&A", "Compras"),
    "guararapes": ("Riachuelo", "Compras"),
    "riachuelo": ("Riachuelo", "Compras"),
    "magazine luiza": ("Magalu", "Compras Online"),
    "magalu": ("Magalu", "Compras Online"),
    "via varejo": ("Casas Bahia", "Compras"),
    "grupo casas bahia": ("Casas Bahia", "Compras"),
    "casas bahia": ("Casas Bahia", "Compras"),
    "kalunga": ("Kalunga", "Compras"),
    "leroy merlin": ("Leroy Merlin", "Casa"),
    "decathlon": ("Decathlon", "Esporte"),
    "sbf comercio": ("Centauro", "Esporte"),
    "centauro": ("Centauro", "Esporte"),
    "smart fit": ("Smart Fit", "Saúde"),
    "smartfit": ("Smart Fit", "Saúde"),
    "telefonica": ("Vivo", "Telecomunicações"),
    "vivo": ("Vivo", "Telecomunicações"),
    "claro": ("Claro", "Telecomunicações"),
    "tim ": ("TIM", "Telecomunicações"),
    "sem parar": ("Sem Parar", "Transporte"),
    "veloe": ("Veloe", "Transporte"),
    "conectcar": ("ConectCar", "Transporte"),
    "rappi": ("Rappi", "Delivery"),
    "ze delivery": ("Zé Delivery", "Delivery"),
    "sodexo": ("Sodexo", "Benefícios"),
    "pluxee": ("Pluxee", "Benefícios"),
    "alelo": ("Alelo", "Benefícios"),
    "nu pagamentos": ("Nubank", "Serviços Financeiros"),
    "nubank": ("Nubank", "Serviços Financeiros"),
    "pix": ("Pix", "Transferência"),
    "drogaria pacheco": ("Drogaria Pacheco", "Farmácia"),
    "drogaria sp": ("Drogaria São Paulo", "Farmácia"),
    "extra hipermercado": ("Extra", "Mercado"),
    "pao de acucar delivery": ("Pão de Açúcar", "Mercado"),
    "posto ipiranga": ("Ipiranga", "Combustível"),
    "vivara": ("Vivara", "Compras"),
}

# Chaves cujo nome final deve preservar quem enviou/recebeu (Pix, TED, DOC...).
_CHAVES_TRANSFERENCIA = {"pix"}

_PALAVRAS_FILTRAR_TRANSFERENCIA = {
    "pix", "ted", "doc", "transferencia", "enviado", "enviada", "recebido",
    "recebida", "via", "pelo", "pela",
} | _PREPOSICOES_BAIXAS


def _extrair_nome_transferencia(texto):
    """Remove o rotulo (Pix/TED/...) e palavras de preenchimento, mantendo o
    nome de quem enviou/recebeu quando houver."""
    if not texto:
        return None
    palavras = [p for p in texto.split(" ") if p]
    restantes = [p for p in palavras if _normalizar(p) not in _PALAVRAS_FILTRAR_TRANSFERENCIA]
    nome = " ".join(restantes).strip(" -:")
    return nome or None


def _compilar_padrao_chave(chave):
    """Casamento por palavra inteira: a chave so "bate" quando nao esta colada a
    outras letras (digitos, espacos e pontuacao contam como limite de palavra).
    Isso vale tanto para chaves de uma palavra quanto para frases - so as bordas
    da chave inteira importam, entao chaves "coladas" (ex.: "drogaraia",
    "apple.com/bill") continuam funcionando sem tratamento especial."""
    return re.compile(r"(?<![a-z])" + re.escape(chave) + r"(?![a-z])")


_TABELA_ITENS_ORDENADOS = sorted(TABELA_ESTABELECIMENTOS.items(), key=lambda kv: -len(kv[0]))
_TABELA_COMPILADA = [
    (chave, _compilar_padrao_chave(chave), valor) for chave, valor in _TABELA_ITENS_ORDENADOS
]


def _buscar_na_tabela(texto_normalizado):
    for chave, padrao, valor in _TABELA_COMPILADA:
        if padrao.search(texto_normalizado):
            return chave, valor
    return None


# ---------------------------------------------------------------------------
# Categorias Pluggy -> portugues curto
# ---------------------------------------------------------------------------

MAPA_CATEGORIAS_PLUGGY = {
    "food and drinks": "Alimentação",
    "eating out": "Alimentação",
    "groceries": "Mercado",
    "transportation": "Transporte",
    "gas stations": "Combustível",
    "taxi and ride-hailing": "Transporte",
    "shopping": "Compras",
    "online shopping": "Compras Online",
    "health": "Saúde",
    "pharmacy": "Farmácia",
    "entertainment": "Entretenimento",
    "streaming": "Streaming",
    "travel": "Viagem",
    "airport and airlines": "Viagem",
    "accommodation": "Hospedagem",
    "telecommunications": "Telecomunicações",
    "services": "Serviços",
    "transfers": "Transferência",
    "credit card payment": "Pagamento de Fatura",
    "investments": "Investimentos",
    "taxes": "Impostos",
    "education": "Educação",
    "electronics": "Eletrônicos",
    "wellness and fitness": "Academia e bem-estar",
    "digital services": "Serviços digitais",
    "tax on financial operations": "Impostos",
}


def _traduzir_categoria(categoria):
    if categoria is None:
        return None
    if not isinstance(categoria, str):
        try:
            categoria = str(categoria)
        except Exception:
            return None
    chave = categoria.strip().lower()
    return MAPA_CATEGORIAS_PLUGGY.get(chave, categoria)


# Categorias internas do gasto manual/chat (enum de ia/funcoes/chat.py:
# mercado, transporte, lazer, contas, saude, outros) -> mesmo rotulo que a
# categoria Pluggy traduzida usa, pra os dois somarem na mesma barra de
# "gasto por categoria" (antes "Mercado" do Nubank e "mercado" do chat viravam
# duas categorias).
ROTULOS_CATEGORIA_MANUAL = {
    "mercado": "Mercado",
    "transporte": "Transporte",
    "lazer": "Lazer",
    "contas": "Contas",
    "saude": "Saúde",
    "outros": "Outros",
}


def rotulo_categoria_manual(categoria):
    if not isinstance(categoria, str) or not categoria.strip():
        return "Outros"
    chave = categoria.strip().lower()
    return ROTULOS_CATEGORIA_MANUAL.get(chave) or chave[:1].upper() + chave[1:]

# ---------------------------------------------------------------------------
# Deteccao de estorno
# ---------------------------------------------------------------------------

_PALAVRAS_ESTORNO = ("estorno", "reembolso", "chargeback", "reversal", "refund")
_PALAVRAS_ESTORNO_GENERICAS = re.compile(
    r"\b(estorno|de|da|do|compra|reembolso|chargeback|reversal|refund)\b",
    re.IGNORECASE,
)


def _eh_estorno(tx, texto_normalizado_origem):
    tipo_operacao = tx.get("tipo_operacao")
    tipo_norm = _normalizar(tipo_operacao)
    for palavra in _PALAVRAS_ESTORNO:
        if palavra in tipo_norm or palavra in texto_normalizado_origem:
            return True
    return False


# ---------------------------------------------------------------------------
# Funcao principal
# ---------------------------------------------------------------------------


def _texto_base(tx):
    estabelecimento = tx.get("estabelecimento")
    if isinstance(estabelecimento, str) and estabelecimento.strip():
        return estabelecimento
    descricao_original = tx.get("descricao_original")
    if isinstance(descricao_original, str) and descricao_original.strip():
        return descricao_original
    return None


def _tem_como_dict(v):
    return isinstance(v, dict)


def descrever(tx, por_external_id=None):
    """Decide o texto de exibicao para uma transacao. Nunca levanta excecao."""
    try:
        if not isinstance(tx, dict):
            return {"descricao": "Sem descricao", "categoria": None, "estorno_de": None}
        if not _tem_como_dict(por_external_id):
            por_external_id = {}

        bruto = _texto_base(tx)
        texto_origem_norm = _normalizar(bruto) + " " + _normalizar(tx.get("descricao_original"))

        categoria_pluggy = _traduzir_categoria(tx.get("categoria"))

        if bruto is None:
            limpo, parcela = "", None
        else:
            limpo, parcela = limpar_texto(bruto)

        nome_tabela = None
        categoria_tabela = None
        chave_tabela = None
        if limpo:
            achado = _buscar_na_tabela(_normalizar(limpo))
            if achado:
                chave_tabela, (nome_tabela, categoria_tabela) = achado
        elif bruto:
            achado = _buscar_na_tabela(_normalizar(bruto))
            if achado:
                chave_tabela, (nome_tabela, categoria_tabela) = achado

        if chave_tabela in _CHAVES_TRANSFERENCIA and nome_tabela:
            nome_pessoa = _extrair_nome_transferencia(limpo or bruto)
            if nome_pessoa:
                nome_tabela = f"{nome_tabela} · {nome_pessoa}"

        nome_final = nome_tabela if nome_tabela else limpo
        if parcela and nome_final:
            nome_final = f"{nome_final} {parcela}"

        categoria_final = categoria_pluggy if categoria_pluggy else categoria_tabela

        eh_estorno = _eh_estorno(tx, texto_origem_norm)

        if eh_estorno:
            estorno_de_id = tx.get("estorno_de_external_id")
            origem_tx = None
            if estorno_de_id is not None and estorno_de_id in por_external_id:
                origem_tx = por_external_id.get(estorno_de_id)
            if isinstance(origem_tx, dict):
                sub = descrever(origem_tx, por_external_id={})
                desc_origem = sub.get("descricao")
                if desc_origem and desc_origem != "Sem descricao":
                    return {
                        "descricao": f"Estorno: {desc_origem}",
                        "categoria": categoria_final if categoria_final else sub.get("categoria"),
                        "estorno_de": desc_origem,
                    }
            nome_sem_genericas = None
            if nome_final:
                resto = _PALAVRAS_ESTORNO_GENERICAS.sub("", nome_final).strip()
                resto = re.sub(r"\s+", " ", resto)
                if resto:
                    nome_sem_genericas = resto
            if nome_sem_genericas:
                return {
                    "descricao": f"Estorno {nome_sem_genericas}",
                    "categoria": categoria_final,
                    "estorno_de": None,
                }
            return {"descricao": "Estorno", "categoria": categoria_final, "estorno_de": None}

        if nome_final:
            return {"descricao": nome_final, "categoria": categoria_final, "estorno_de": None}

        return {"descricao": "Sem descricao", "categoria": categoria_final, "estorno_de": None}
    except Exception:
        return {"descricao": "Sem descricao", "categoria": None, "estorno_de": None}


def precisa_ia(tx):
    """True somente quando nada nas regras locais produziu um nome legivel."""
    try:
        resultado = descrever(tx, {})
        descricao = resultado.get("descricao")
        if not descricao or descricao == "Sem descricao":
            return True
        # sobrou so codigo/numeral: sem nenhuma letra
        if not re.search(r"[A-Za-zÀ-ÿ]", descricao):
            return True
        return False
    except Exception:
        return True
