import time

import pytest

from financas_descricao import descrever, precisa_ia, limpar_texto, TABELA_ESTABELECIMENTOS


# ---------------------------------------------------------------------------
# Tabela local
# ---------------------------------------------------------------------------

def test_tabela_tem_pelo_menos_60_entradas():
    assert len(TABELA_ESTABELECIMENTOS) >= 60


@pytest.mark.parametrize("bruto,esperado", [
    ("ARCOS DOURADOS COM ALIMENTOS SAO PAULO", "McDonald's"),
    ("BK BRASIL LTDA", "Burger King"),
    ("IFD*IFOOD SAO PAULO", "iFood"),
    ("UBER *TRIP", "Uber"),
    ("UBER EATS", "Uber Eats"),
    ("RAIA DROGASIL SA", "Droga Raia"),
    ("CARREFOUR COM E IND LTDA", "Carrefour"),
    ("ASSAI ATACADISTA", "Assaí"),
    ("ATACADAO SA", "Atacadão"),
    ("CIA BRASILEIRA DE DISTRIBUICAO", "Pão de Açúcar"),
    ("EBAZAR COM ONLINE LTDA", "Mercado Livre"),
    ("AMAZON BR", "Amazon"),
    ("NETFLIX.COM", "Netflix"),
    ("SPOTIFY AB", "Spotify"),
    ("APPLE.COM/BILL", "Apple"),
    ("GOOGLE *SERVICES", "Google"),
    ("SHELL BOX", "Shell"),
    ("RAIZEN COMBUSTIVEIS", "Raízen"),
    ("IPIRANGA POSTO", "Ipiranga"),
    ("PETROBRAS DISTRIBUIDORA", "Petrobras"),
    ("STARBUCKS SOUTHROCK", "Starbucks"),
    ("SUBWAY LANCHES", "Subway"),
    ("OUTBACK STEAKHOUSE", "Outback"),
    ("MADERO STEAK HOUSE", "Madero"),
    ("LOCALIZA RENT A CAR", "Localiza"),
    ("LATAM AIRLINES", "Latam"),
    ("GOL LINHAS AEREAS", "Gol"),
    ("AZUL LINHAS AEREAS", "Azul"),
    ("SMILES FIDELIDADE", "Smiles"),
    ("DECOLAR.COM", "Decolar"),
    ("BOOKING.COM", "Booking"),
    ("AIRBNB * HMXYZ", "Airbnb"),
    ("LOJAS RENNER SA", "Renner"),
    ("C&A MODAS", "C&A"),
    ("GUARARAPES CONFECCOES", "Riachuelo"),
    ("MAGAZINE LUIZA SA", "Magalu"),
    ("VIA VAREJO SA", "Casas Bahia"),
    ("KALUNGA COM E SERV", "Kalunga"),
    ("LEROY MERLIN", "Leroy Merlin"),
    ("DECATHLON ESPORTES", "Decathlon"),
    ("SBF COMERCIO DE ARTIGOS", "Centauro"),
    ("SMART FIT ACADEMIA", "Smart Fit"),
    ("TELEFONICA BRASIL", "Vivo"),
    ("CLARO S.A.", "Claro"),
    ("SEM PARAR TAG", "Sem Parar"),
    ("VELOE PEDAGIO", "Veloe"),
    ("CONECTCAR SA", "ConectCar"),
    ("RAPPI BRASIL", "Rappi"),
    ("ZE DELIVERY BEBIDAS", "Zé Delivery"),
    ("SODEXO PASS", "Sodexo"),
    ("PLUXEE BENEFICIOS", "Pluxee"),
    ("ALELO REFEICAO", "Alelo"),
    ("NU PAGAMENTOS SA", "Nubank"),
])
def test_tabela_resolve_nomes_conhecidos(bruto, esperado):
    resultado = descrever({"descricao_original": bruto})
    assert resultado["descricao"] == esperado


# ---------------------------------------------------------------------------
# Prefixos de adquirente / limpeza
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bruto", [
    "IFD*RESTAURANTE DO ZE",
    "PAG*LOJA XYZ",
    "MP*ALGUMA LOJA",
    "MERCADOPAGO*OUTRA LOJA",
    "PICPAY*BARBEARIA",
    "EBANX*STORE",
    "PAYPAL *DIGITALSERVICE",
    "DL*ESTACIONAMENTO",
    "EC *PADARIA CENTRAL",
])
def test_remove_prefixo_adquirente(bruto):
    limpo, _ = limpar_texto(bruto)
    limpo_norm = limpo.lower()
    for prefixo in ["ifd*", "pag*", "mp*", "mercadopago*", "picpay*", "ebanx*", "paypal *", "dl*", "ec *"]:
        assert not limpo_norm.startswith(prefixo)


def test_remove_sufixo_cidade_uf():
    limpo, _ = limpar_texto("RESTAURANTE BOM SABOR SAO PAULO SP")
    assert not limpo.upper().endswith(" SP")


def test_parcela_detectada_no_final():
    resultado = descrever({"descricao_original": "LOJA DE MOVEIS XYZ 2/10"})
    assert "(2/10)" in resultado["descricao"]


def test_parcela_com_hifen():
    limpo, parcela = limpar_texto("LOJA ELETRO 03/12")
    assert parcela == "(3/12)"


def test_normalizacao_de_caixa_titulo():
    resultado = descrever({"descricao_original": "restaurante bom sabor"})
    assert resultado["descricao"] == "Restaurante Bom Sabor"


# ---------------------------------------------------------------------------
# Estabelecimento tem prioridade sobre descricao_original
# ---------------------------------------------------------------------------

def test_estabelecimento_tem_prioridade():
    resultado = descrever({
        "estabelecimento": "Netflix.com",
        "descricao_original": "IFD*ALGO ESTRANHO",
    })
    assert resultado["descricao"] == "Netflix"


def test_usa_descricao_original_quando_sem_estabelecimento():
    resultado = descrever({"estabelecimento": None, "descricao_original": "SPOTIFY AB"})
    assert resultado["descricao"] == "Spotify"


def test_estabelecimento_string_vazia_cai_para_descricao_original():
    resultado = descrever({"estabelecimento": "", "descricao_original": "AMAZON BR"})
    assert resultado["descricao"] == "Amazon"


# ---------------------------------------------------------------------------
# Categorias Pluggy
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("categoria_pluggy,esperado", [
    ("Food and drinks", "Alimentação"),
    ("Eating out", "Alimentação"),
    ("Groceries", "Mercado"),
    ("Transportation", "Transporte"),
    ("Gas stations", "Combustível"),
    ("Taxi and ride-hailing", "Transporte"),
    ("Shopping", "Compras"),
    ("Online shopping", "Compras Online"),
    ("Health", "Saúde"),
    ("Pharmacy", "Farmácia"),
    ("Entertainment", "Entretenimento"),
    ("Streaming", "Streaming"),
    ("Travel", "Viagem"),
    ("Airport and airlines", "Viagem"),
    ("Accommodation", "Hospedagem"),
    ("Telecommunications", "Telecomunicações"),
    ("Services", "Serviços"),
    ("Transfers", "Transferência"),
    ("Credit card payment", "Pagamento de Fatura"),
    ("Investments", "Investimentos"),
    ("Taxes", "Impostos"),
    ("Education", "Educação"),
    ("Electronics", "Eletrônicos"),
    ("Wellness and fitness", "Academia e bem-estar"),
    ("Digital services", "Serviços digitais"),
    ("Tax on financial operations", "Impostos"),
])
def test_categoria_pluggy_traduzida(categoria_pluggy, esperado):
    resultado = descrever({"descricao_original": "LOJA QUALQUER", "categoria": categoria_pluggy})
    assert resultado["categoria"] == esperado


def test_categoria_desconhecida_retorna_original():
    resultado = descrever({"descricao_original": "LOJA X", "categoria": "Categoria Bizarra Nova"})
    assert resultado["categoria"] == "Categoria Bizarra Nova"


def test_categoria_none_retorna_none():
    resultado = descrever({"descricao_original": "LOJA SEM CATEGORIA CONHECIDA XPTO123"})
    assert resultado["categoria"] is None


def test_categoria_sugerida_pela_tabela_quando_pluggy_ausente():
    resultado = descrever({"descricao_original": "IFD*IFOOD"})
    assert resultado["categoria"] == "Delivery"


# ---------------------------------------------------------------------------
# Casos especificos - descrição e categorias
# ---------------------------------------------------------------------------

def test_raia_seguida_de_numero_eh_droga_raia():
    """Caso 1: Raia362 deve ser reconhecido como Droga Raia"""
    resultado = descrever({"descricao_original": "Raia362"})
    assert resultado["descricao"] == "Droga Raia"
    assert resultado["categoria"] == "Farmácia"


def test_raia_maiuscula_com_numero():
    """Caso 1b: RAIA 123 deve ser Droga Raia"""
    resultado = descrever({"descricao_original": "RAIA 123"})
    assert resultado["descricao"] == "Droga Raia"


def test_drogaraia_palavra_unica():
    """Caso 1c: DROGARAIA deve ser Droga Raia"""
    resultado = descrever({"descricao_original": "DROGARAIA"})
    assert resultado["descricao"] == "Droga Raia"


def test_apple_computer_brasil_ltda():
    """Caso 2: Apple Computer Brasil LTDA deve ser simplesmente Apple"""
    resultado = descrever({"descricao_original": "Apple Computer Brasil LTDA"})
    assert resultado["descricao"] == "Apple"


def test_apple_com_bill():
    """Caso 2b: APPLE.COM/BILL deve ser Apple"""
    resultado = descrever({"descricao_original": "APPLE.COM/BILL"})
    assert resultado["descricao"] == "Apple"


def test_anthropic_claude_sub():
    """Caso 3: Anthropic* Claude Sub deve ser reconhecido como Claude"""
    resultado = descrever({"descricao_original": "Anthropic* Claude Sub"})
    assert resultado["descricao"] == "Claude"


def test_claude_ai():
    """Caso 3b: CLAUDE.AI deve ser reconhecido como Claude"""
    resultado = descrever({"descricao_original": "CLAUDE.AI"})
    assert resultado["descricao"] == "Claude"


def test_iof_de_compra_internacional():
    """Caso 4: IOF de compra internacional deve limpar para IOF compra internacional"""
    resultado = descrever({"descricao_original": "IOF de compra internacional"})
    # Deve remover "de" quando em minúsculas
    assert "IOF" in resultado["descricao"]
    # Não deve ter "De" em maiúsculas
    assert "De Compra" not in resultado["descricao"]


def test_posto_sonho_meu_truncado():
    """Caso 5: Posto Sonho Meu Brusqu (com cidade truncada) deve ser Posto Sonho Meu"""
    resultado = descrever({"descricao_original": "Posto Sonho Meu Brusqu"})
    assert resultado["descricao"] == "Posto Sonho Meu"


# ---------------------------------------------------------------------------
# Estorno
# ---------------------------------------------------------------------------

def test_estorno_com_vinculo_encontrado():
    por_external_id = {
        "tx-original-1": {
            "descricao_original": "ARCOS DOURADOS COM ALIMENTOS",
            "estabelecimento": None,
        }
    }
    tx_estorno = {
        "descricao_original": "Estorno de compra",
        "tipo_operacao": "estorno",
        "estorno_de_external_id": "tx-original-1",
        "external_id": "tx-estorno-1",
    }
    resultado = descrever(tx_estorno, por_external_id)
    assert resultado["descricao"] == "Estorno: McDonald's"
    assert resultado["estorno_de"] == "McDonald's"


def test_estorno_sem_vinculo_mas_com_nome():
    tx_estorno = {
        "descricao_original": "Estorno IFD*IFOOD",
        "tipo_operacao": "estorno",
        "estorno_de_external_id": "id-nao-existe",
    }
    resultado = descrever(tx_estorno, {})
    assert resultado["descricao"].startswith("Estorno")
    assert resultado["estorno_de"] is None


def test_estorno_sem_vinculo_sem_nome():
    tx_estorno = {
        "descricao_original": "Estorno de compra",
        "tipo_operacao": "estorno",
    }
    resultado = descrever(tx_estorno, {})
    assert resultado["descricao"] == "Estorno"
    assert resultado["estorno_de"] is None


def test_estorno_detectado_pela_palavra_reembolso():
    tx_estorno = {"descricao_original": "REEMBOLSO NETFLIX"}
    resultado = descrever(tx_estorno, {})
    assert "Estorno" in resultado["descricao"]


def test_estorno_detectado_por_chargeback():
    tx_estorno = {"descricao_original": "CHARGEBACK LOJA X"}
    resultado = descrever(tx_estorno, {})
    assert "Estorno" in resultado["descricao"]


def test_estorno_por_external_id_none_nao_quebra():
    tx_estorno = {
        "descricao_original": "Estorno de compra",
        "tipo_operacao": "estorno",
        "estorno_de_external_id": None,
    }
    resultado = descrever(tx_estorno, None)
    assert resultado["descricao"] == "Estorno"


# ---------------------------------------------------------------------------
# precisa_ia
# ---------------------------------------------------------------------------

def test_precisa_ia_true_quando_so_sobra_codigo():
    assert precisa_ia({"descricao_original": "123456789"}) is True


def test_precisa_ia_true_quando_vazio():
    assert precisa_ia({}) is True
    assert precisa_ia({"descricao_original": None, "estabelecimento": None}) is True


def test_precisa_ia_false_quando_tabela_resolve():
    assert precisa_ia({"descricao_original": "NETFLIX.COM"}) is False


def test_precisa_ia_false_quando_limpeza_produz_nome_legivel():
    assert precisa_ia({"descricao_original": "RESTAURANTE BOM SABOR"}) is False


# ---------------------------------------------------------------------------
# Entradas malformadas -- nunca deve levantar excecao
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tx", [
    None,
    {},
    {"descricao_original": None, "estabelecimento": None},
    {"descricao_original": 12345},
    {"descricao_original": ["lista", "nao", "string"]},
    {"descricao_original": {"chave": "valor"}},
    {"descricao_original": "X" * 100000},
    {"estabelecimento": "\x00\x01\x02 controle"},
    {"descricao_original": "café ação São João"},
    {"categoria": 999},
    {"categoria": ["nao", "eh", "string"]},
    {"tipo_operacao": None},
    {"valor": float("nan")},
    {"valor": float("inf")},
    {"estorno_de_external_id": 12345},
    {"external_id": None},
    "isso nao e um dict",
    12345,
    [1, 2, 3],
    {"descricao_original": ""},
    {"descricao_original": "   "},
    {"descricao_original": "😀🎉 emoji loja"},
])
def test_entradas_malformadas_nao_levantam_excecao(tx):
    resultado = descrever(tx)
    assert isinstance(resultado, dict)
    assert "descricao" in resultado
    assert isinstance(resultado["descricao"], str)
    assert resultado["descricao"] != ""


def test_por_external_id_malformado_nao_quebra():
    resultado = descrever({"descricao_original": "Estorno de compra", "tipo_operacao": "estorno",
                            "estorno_de_external_id": "abc"}, por_external_id="nao eh dict")
    assert isinstance(resultado, dict)


def test_por_external_id_aponta_para_nao_dict_nao_quebra():
    resultado = descrever(
        {"descricao_original": "Estorno de compra", "tipo_operacao": "estorno",
         "estorno_de_external_id": "abc"},
        por_external_id={"abc": "nao eh dict"},
    )
    assert isinstance(resultado, dict)
    assert resultado["descricao"] == "Estorno"


def test_precisa_ia_nao_levanta_excecao_com_entrada_invalida():
    assert precisa_ia(None) is True
    assert precisa_ia("string") is True
    assert precisa_ia(12345) is True


# ---------------------------------------------------------------------------
# Desempenho
# ---------------------------------------------------------------------------

def test_desempenho_5000_descricoes_menos_de_1_segundo():
    txs = []
    exemplos = [
        {"descricao_original": "IFD*IFOOD SAO PAULO"},
        {"descricao_original": "ARCOS DOURADOS COM ALIMENTOS"},
        {"estabelecimento": "NETFLIX.COM"},
        {"descricao_original": "Estorno de compra", "tipo_operacao": "estorno"},
        {"descricao_original": "LOJA QUALQUER 2/10", "categoria": "Shopping"},
    ]
    for i in range(5000):
        txs.append(exemplos[i % len(exemplos)])

    inicio = time.perf_counter()
    for tx in txs:
        descrever(tx)
    duracao = time.perf_counter() - inicio
    assert duracao < 1.0
