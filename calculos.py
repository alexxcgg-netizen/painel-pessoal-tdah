"""calculos.py - conta deterministica, sem IA (Faixa A13, Fase 7).

Regra de ouro desta faixa: o modelo de IA nunca deve fazer conta (juros,
parcela, saldo, projecao, percentual de meta, total, parcelas restantes,
"em N dias"...). O modelo so interpreta texto (classifica, extrai campos em
texto livre, explica um resultado em portugues); toda conta mora aqui, em
codigo puro, testado e determinismo. Ver docs/calculos.md pro inventario de
onde isso e violado hoje e qual funcao daqui deve substituir cada caso.

Convencoes:
- Toda funcao aqui e pura: sem banco, sem rede, sem `date.today()`/`datetime.now()`
  implicito - quem chama passa "hoje"/"agora" explicitamente, do jeito que o
  resto do repo ja faz (ex: vida.hiperfoco_ativo), pra dar pra testar com
  qualquer data sem mockar relogio.
- Dinheiro e sempre Decimal. Valores de entrada podem chegar como int, float,
  str ou Decimal (o que vier do banco/JSON/IA) - a conversao usa `_dec()`,
  que passa por `str()` antes de criar o Decimal pra nao herdar a imprecisao
  binaria de um float (Decimal(0.1) != Decimal("0.1")).
- Arredondamento monetario: SEMPRE 2 casas decimais com ROUND_HALF_EVEN
  (arredondamento bancario - "banker's rounding": 0.125 -> 0.12, 0.135 ->
  0.14, cada um arredonda pro vizinho par, entao o erro nao se acumula
  sistematicamente numa direcao ao longo de muitas parcelas/lancamentos,
  diferente do ROUND_HALF_UP que sempre puxa pra cima no empate). Ver
  `_money()`/`DUAS_CASAS` abaixo. Percentual tambem sai com 2 casas, pelo
  mesmo motivo de nao acumular erro em contas encadeadas.
- Entrada invalida (data que nao parseia, numero de parcelas <= 0, taxa que
  quebra a formula) sempre vira `ValueError` com mensagem clara em
  portugues - nunca um `ZeroDivisionError`/`TypeError`/`OverflowError` cru,
  e nunca um numero errado calado. Divisao por zero que faz sentido de
  negocio (ex: meta com alvo 0) tem um resultado neutro documentado na
  propria funcao, em vez de excecao.
"""

from calendar import monthrange
from datetime import date, datetime
from decimal import ROUND_CEILING, ROUND_HALF_EVEN, Decimal, InvalidOperation

DUAS_CASAS = Decimal("0.01")
ZERO = Decimal("0")
CEM = Decimal("100")

Numero = int | float | str | Decimal


# --------------------------------------------------------------------------
# Helpers internos
# --------------------------------------------------------------------------


def _dec(valor: Numero, campo: str = "valor") -> Decimal:
    """Converte pra Decimal sem herdar imprecisao binaria de float (passa
    por str primeiro). Levanta ValueError com o nome do campo se nao der
    pra converter (None, string vazia, "abc", NaN, infinito...)."""
    if isinstance(valor, Decimal):
        d = valor
    elif isinstance(valor, bool):
        # bool e subclasse de int em Python - nunca faz sentido aqui, e um
        # None/objeto errado que passaria batido pra Decimal(int(True)) = 1.
        raise ValueError(f"{campo} invalido: {valor!r} (booleano nao e numero)")
    elif isinstance(valor, (int, float)):
        d = Decimal(str(valor))
    elif isinstance(valor, str):
        texto = valor.strip().replace(",", ".") if valor.count(",") == 1 and "." not in valor else valor.strip()
        try:
            d = Decimal(texto)
        except InvalidOperation:
            raise ValueError(f"{campo} invalido: {valor!r} nao e um numero")
    else:
        raise ValueError(f"{campo} invalido: {valor!r} (tipo {type(valor).__name__})")
    if not d.is_finite():
        raise ValueError(f"{campo} invalido: {valor!r} (nao e um numero finito)")
    return d


def _money(valor: Decimal) -> Decimal:
    """Arredonda pra 2 casas com ROUND_HALF_EVEN (bancario) - ver docstring
    do modulo."""
    return valor.quantize(DUAS_CASAS, rounding=ROUND_HALF_EVEN)


def _pct(valor: Decimal) -> Decimal:
    """Mesmo arredondamento bancario, 2 casas, pra percentuais."""
    return valor.quantize(DUAS_CASAS, rounding=ROUND_HALF_EVEN)


def _inteiro_positivo(valor, campo: str) -> int:
    """Converte pra int >= 1 (numero de parcelas/periodos). Aceita float
    "redondo" (12.0), rejeita fracionario, zero, negativo e nao-numero."""
    try:
        d = _dec(valor, campo)
    except ValueError:
        raise
    if d != d.to_integral_value():
        raise ValueError(f"{campo} invalido: {valor!r} precisa ser um numero inteiro")
    n = int(d)
    if n < 1:
        raise ValueError(f"{campo} invalido: {valor!r} precisa ser >= 1")
    return n


def _inteiro_nao_negativo(valor, campo: str) -> int:
    d = _dec(valor, campo)
    if d != d.to_integral_value():
        raise ValueError(f"{campo} invalido: {valor!r} precisa ser um numero inteiro")
    n = int(d)
    if n < 0:
        raise ValueError(f"{campo} invalido: {valor!r} nao pode ser negativo")
    return n


def _para_data(valor, campo: str = "data") -> date:
    """Aceita date, datetime (vira so a data) ou string ISO 'AAAA-MM-DD'
    (tambem aceita datetime ISO completo, so pega a parte da data).
    ValueError claro em qualquer outra coisa - nunca deixa um
    string.split() ou fromisoformat cru estourar TypeError/ValueError
    generico sem contexto."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        texto = valor.strip()
        try:
            return date.fromisoformat(texto[:10])
        except ValueError:
            raise ValueError(f"{campo} invalida: {valor!r} nao e uma data AAAA-MM-DD valida")
    raise ValueError(f"{campo} invalida: {valor!r} (tipo {type(valor).__name__})")


def _somar_meses(base: date, meses: int) -> date:
    """Soma N meses a uma data, comprimindo o dia quando o mes de destino
    for mais curto (ex: 31/01 + 1 mes = 28/02 ou 29/02 em bissexto, nunca
    "31/02" nem estoura pro mes seguinte)."""
    total_meses = base.month - 1 + meses
    ano = base.year + total_meses // 12
    mes = total_meses % 12 + 1
    ultimo_dia_do_mes = monthrange(ano, mes)[1]
    dia = min(base.day, ultimo_dia_do_mes)
    return date(ano, mes, dia)


# --------------------------------------------------------------------------
# Metas e projecoes
# --------------------------------------------------------------------------


def percentual_meta(atual: Numero, alvo: Numero) -> Decimal:
    """Quanto (%) de uma meta ja foi atingido, com 2 casas (ROUND_HALF_EVEN).

    Sempre fica entre 0.00 e 100.00: um `atual` negativo (ex: divida) conta
    como 0%, e passar do alvo trava em 100% (nao interessa "180% da meta"
    pra exibicao - se precisar do excedente exato, calcule
    `atual - alvo` a parte). `alvo` <= 0 e uma meta sem sentido matematico
    (dividir por zero, ou por um alvo negativo) - devolve 0.00 em vez de
    levantar excecao, porque uma meta mal cadastrada nao deveria derrubar a
    tela que so quer mostrar uma barra de progresso.
    """
    return _pct(_percentual_meta_bruto(atual, alvo))


def _percentual_meta_bruto(atual: Numero, alvo: Numero) -> Decimal:
    """Percentual sem arredondar, ja travado entre 0 e 100 (regras de
    `percentual_meta`)."""
    alvo_d = _dec(alvo, "alvo")
    if alvo_d <= ZERO:
        return ZERO
    atual_d = _dec(atual, "atual")
    if atual_d <= ZERO:
        return ZERO
    pct = atual_d / alvo_d * CEM
    return CEM if pct > CEM else pct


UMA_CASA = Decimal("0.1")


def percentual_meta_exibicao(atual, alvo) -> float:
    """Percentual de meta pra TELA/CHAT (Fase 7, faixa C1): a funcao unica
    que cards.py (card_meta), app.py (_consultar_meta, /api/progresso) usam -
    antes cada um arredondava de um jeito (1 casa, 0 casas, round() de
    float). Float com 1 casa (ROUND_HALF_EVEN, direto do valor bruto - sem
    arredondar duas vezes), entre 0.0 e 100.0. Tolerante de proposito:
    `None`/texto/NaN (meta mal cadastrada) vira 0.0 em vez de derrubar a
    tela - a conta estrita continua em `percentual_meta`."""
    try:
        bruto = _percentual_meta_bruto(0 if atual is None else atual, 0 if alvo is None else alvo)
    except (ValueError, TypeError):
        return 0.0
    return float(bruto.quantize(UMA_CASA, rounding=ROUND_HALF_EVEN))


def projecao_meta(
    atual: Numero, alvo: Numero, aporte_mensal: Numero, hoje: Numero
) -> dict:
    """Projeta quando uma meta financeira e atingida guardando um valor
    fixo por mes, a partir de hoje.

    Devolve:
    - `falta`: Decimal, quanto ainda falta (0.00 se ja bateu ou passou).
    - `atingivel`: bool - False so quando falta > 0 e aporte_mensal <= 0
      (nunca vai chegar la nesse ritmo).
    - `meses_necessarios`: int ou None (None quando nao atingivel). 0
      quando a meta ja foi batida.
    - `data_prevista`: date ou None (mesma regra de meses_necessarios).

    `aporte_mensal` <= 0 com a meta ja batida ainda devolve atingivel=True
    (nao precisa mais guardar nada). Meta invalida (alvo <= 0) e tratada
    como ja atingida (falta=0), pelo mesmo motivo de percentual_meta: nao
    e responsabilidade desta funcao validar cadastro de meta.
    """
    hoje_d = _para_data(hoje, "hoje")
    alvo_d = _dec(alvo, "alvo")
    atual_d = _dec(atual, "atual")
    aporte_d = _dec(aporte_mensal, "aporte_mensal")

    falta = alvo_d - atual_d
    if alvo_d <= ZERO or falta <= ZERO:
        return {
            "falta": Decimal("0.00"),
            "atingivel": True,
            "meses_necessarios": 0,
            "data_prevista": hoje_d,
        }

    if aporte_d <= ZERO:
        return {
            "falta": _money(falta),
            "atingivel": False,
            "meses_necessarios": None,
            "data_prevista": None,
        }

    # quantos aportes inteiros ate cobrir 'falta' (arredonda pra cima: o
    # ultimo mes pode aportar menos que o fixo e ainda bater a meta).
    meses = int((falta / aporte_d).to_integral_value(rounding=ROUND_CEILING))
    return {
        "falta": _money(falta),
        "atingivel": True,
        "meses_necessarios": meses,
        "data_prevista": _somar_meses(hoje_d, meses),
    }


# --------------------------------------------------------------------------
# Emprestimo / financiamento
# --------------------------------------------------------------------------


def parcela_price(valor: Numero, taxa_mensal: Numero, n: Numero) -> Decimal:
    """Valor da parcela fixa (Tabela Price) de um financiamento.

    `taxa_mensal` e fracao ao mes (2% a.m. = 0.02, NUNCA "2"). `n` e o
    numero de parcelas (>= 1, inteiro). Com `taxa_mensal` == 0 vira divisao
    simples (valor/n, sem juros). `valor` == 0 devolve parcela 0.00.

    Levanta ValueError se `n` nao for inteiro >= 1, ou se `taxa_mensal`
    tornar a formula indefinida (taxa <= -100%, ou seja (1 + taxa) <= 0 -
    matematicamente nao existe "taxa de -150% ao mes" nesta formula).
    """
    n_int = _inteiro_positivo(n, "n")
    valor_d = _dec(valor, "valor")
    taxa_d = _dec(taxa_mensal, "taxa_mensal")

    if taxa_d == ZERO:
        return _money(valor_d / n_int)

    base = Decimal(1) + taxa_d
    if base <= ZERO:
        raise ValueError(
            f"taxa_mensal invalida: {taxa_mensal!r} faz (1 + taxa) <= 0, "
            "a formula da Tabela Price nao existe pra essa taxa"
        )
    fator = base ** (-n_int)
    denominador = Decimal(1) - fator
    if denominador == ZERO:
        raise ValueError(f"taxa_mensal invalida: {taxa_mensal!r} zera o denominador da formula")
    parcela = valor_d * taxa_d / denominador
    return _money(parcela)


def tabela_amortizacao(
    valor: Numero, taxa_mensal: Numero, n: Numero, sistema: str = "price"
) -> list[dict]:
    """Tabela de amortizacao completa, parcela a parcela.

    `sistema`: "price" (parcela fixa, padrao) ou "sac" (amortizacao fixa,
    parcela decrescente). Cada linha: `parcela` (numero 1..n), `valor_parcela`,
    `juros`, `amortizacao`, `saldo_devedor` (todos Decimal, 2 casas).

    O ultimo saldo_devedor e sempre exatamente 0.00 - a ultima parcela
    absorve a diferenca de centavos que o arredondamento acumulado das
    parcelas anteriores deixaria sobrando (senao a soma das amortizacoes
    poderia fechar em R$ 0,03 a mais/menos que o valor financiado).

    Levanta ValueError nos mesmos casos de `parcela_price`, mais
    `sistema` desconhecido.
    """
    if not isinstance(sistema, str):
        raise ValueError(f"sistema invalido: {sistema!r} (use 'price' ou 'sac')")
    sistema_norm = sistema.strip().lower()
    if sistema_norm not in ("price", "sac"):
        raise ValueError(f"sistema invalido: {sistema!r} (use 'price' ou 'sac')")

    n_int = _inteiro_positivo(n, "n")
    valor_d = _dec(valor, "valor")
    taxa_d = _dec(taxa_mensal, "taxa_mensal")
    if taxa_d != ZERO and (Decimal(1) + taxa_d) <= ZERO:
        raise ValueError(
            f"taxa_mensal invalida: {taxa_mensal!r} faz (1 + taxa) <= 0, "
            "a formula de amortizacao nao existe pra essa taxa"
        )

    linhas: list[dict] = []
    saldo = valor_d

    if sistema_norm == "price":
        parcela_fixa = parcela_price(valor_d, taxa_d, n_int)
        for i in range(1, n_int + 1):
            juros = _money(saldo * taxa_d)
            if i < n_int:
                amortizacao = _money(parcela_fixa - juros)
                saldo = _money(saldo - amortizacao)
                valor_parcela = parcela_fixa
            else:
                # ultima parcela: zera o saldo exatamente, absorvendo o
                # arredondamento acumulado.
                amortizacao = saldo
                valor_parcela = _money(amortizacao + juros)
                saldo = Decimal("0.00")
            linhas.append(
                {
                    "parcela": i,
                    "valor_parcela": valor_parcela,
                    "juros": juros,
                    "amortizacao": amortizacao,
                    "saldo_devedor": saldo,
                }
            )
    else:  # sac
        amortizacao_fixa = _money(valor_d / n_int)
        for i in range(1, n_int + 1):
            juros = _money(saldo * taxa_d)
            if i < n_int:
                amortizacao = amortizacao_fixa
                saldo = _money(saldo - amortizacao)
            else:
                amortizacao = saldo
                saldo = Decimal("0.00")
            valor_parcela = _money(amortizacao + juros)
            linhas.append(
                {
                    "parcela": i,
                    "valor_parcela": valor_parcela,
                    "juros": juros,
                    "amortizacao": amortizacao,
                    "saldo_devedor": saldo,
                }
            )

    return linhas


def juros_compostos(
    principal: Numero, taxa_periodo: Numero, n_periodos: Numero, aporte_periodico: Numero = 0
) -> dict:
    """Evolucao de um saldo com juros compostos, com aporte fixo opcional
    no fim de cada periodo (convencao "postecipado", igual poupanca/CDB
    com deposito mensal).

    `n_periodos` == 0 devolve o principal sem alteracao (nenhum periodo se
    passou). `taxa_periodo` negativa e aceita (saldo encolhendo, ex:
    inflacao/perda) - so `n_periodos` negativo e invalido.

    Devolve `saldo_final`, `total_aportado` (principal + soma dos aportes)
    e `total_juros` (saldo_final - total_aportado, pode ser negativo se a
    taxa for negativa).
    """
    n_int = _inteiro_nao_negativo(n_periodos, "n_periodos")
    principal_d = _dec(principal, "principal")
    taxa_d = _dec(taxa_periodo, "taxa_periodo")
    aporte_d = _dec(aporte_periodico, "aporte_periodico")

    saldo = principal_d
    total_aportado = principal_d
    for _ in range(n_int):
        saldo = saldo * (Decimal(1) + taxa_d) + aporte_d
        total_aportado += aporte_d

    saldo = _money(saldo)
    total_aportado = _money(total_aportado)
    return {
        "saldo_final": saldo,
        "total_aportado": total_aportado,
        "total_juros": _money(saldo - total_aportado),
    }


# --------------------------------------------------------------------------
# Totais, saldo e parcelas
# --------------------------------------------------------------------------


def total_por_categoria(itens: list[dict]) -> dict[str, Decimal]:
    """Soma `valor` por `categoria` de uma lista de itens (gasto, renda,
    cotacao...). Cada item precisa ter uma chave "valor" numerica; a chave
    "categoria" e opcional - item sem categoria (ou com string vazia) cai
    em "outros". Devolve {categoria: Decimal total (2 casas)}, so com as
    categorias que apareceram (lista vazia -> dict vazio).
    """
    totais: dict[str, Decimal] = {}
    for i, item in enumerate(itens):
        if not isinstance(item, dict):
            raise ValueError(f"itens[{i}] invalido: {item!r} (esperava um dict com 'valor')")
        if "valor" not in item:
            raise ValueError(f"itens[{i}] invalido: falta a chave 'valor'")
        categoria = item.get("categoria") or "outros"
        if not isinstance(categoria, str):
            raise ValueError(f"itens[{i}].categoria invalida: {categoria!r}")
        categoria = categoria.strip() or "outros"
        valor = _dec(item["valor"], f"itens[{i}].valor")
        totais[categoria] = totais.get(categoria, ZERO) + valor
    return {cat: _money(total) for cat, total in totais.items()}


def saldo_apos(saldo: Numero, lancamentos: list[dict]) -> Decimal:
    """Saldo depois de aplicar uma lista de lancamentos, em ordem.

    Cada lancamento e um dict com "valor" (numerico) e, opcionalmente,
    "tipo": "entrada" ou "saida" - quando presente, o SINAL de "valor" e
    ignorado e o tipo manda (assim quem chama pode sempre passar valor
    positivo e dizer o tipo, sem se preocupar em inverter o sinal na mao).
    Sem "tipo", o proprio sinal de "valor" decide (positivo = credito,
    negativo = debito) - util pra lancamento ja vindo com sinal do banco/
    extrato.
    """
    total = _dec(saldo, "saldo")
    for i, lanc in enumerate(lancamentos):
        if not isinstance(lanc, dict) or "valor" not in lanc:
            raise ValueError(f"lancamentos[{i}] invalido: {lanc!r} (esperava um dict com 'valor')")
        valor = _dec(lanc["valor"], f"lancamentos[{i}].valor")
        tipo = lanc.get("tipo")
        if tipo is not None:
            if tipo not in ("entrada", "saida"):
                raise ValueError(f"lancamentos[{i}].tipo invalido: {tipo!r} (use 'entrada' ou 'saida')")
            valor = abs(valor) if tipo == "entrada" else -abs(valor)
        total += valor
    return _money(total)


def parcelas_restantes(n_total: Numero, parcela_atual: Numero) -> int:
    """Quantas parcelas ainda faltam pagar. `parcela_atual` e o numero da
    ultima parcela JA PAGA (0 = nenhuma paga ainda). Nunca fica negativo:
    se `parcela_atual` >= `n_total` (financiamento quitado, ou dado
    incoerente), devolve 0 em vez de um numero negativo sem sentido.
    """
    n_int = _inteiro_positivo(n_total, "n_total")
    atual_int = _inteiro_nao_negativo(parcela_atual, "parcela_atual")
    return max(n_int - atual_int, 0)


def data_ultima_parcela(primeira: Numero, n: Numero) -> date:
    """Data da ultima parcela, dado o vencimento da primeira e o total de
    parcelas (>= 1). Com n=1, a "ultima" e a propria primeira. Preserva o
    dia do vencimento todo mes, comprimindo em meses mais curtos (ver
    `_somar_meses`) - ex: primeira em 31/01 com 2 parcelas -> ultima em
    28/02 (ou 29/02 em ano bissexto), nunca "31/02".
    """
    n_int = _inteiro_positivo(n, "n")
    primeira_d = _para_data(primeira, "primeira")
    return _somar_meses(primeira_d, n_int - 1)


def dias_ate(data: Numero, hoje: Numero) -> int:
    """Quantos dias faltam de `hoje` ate `data` (negativo se `data` ja
    passou, 0 se for hoje mesmo). Aceita date/datetime/string 'AAAA-MM-DD'
    nos dois parametros; ValueError claro se qualquer um nao parsear.
    """
    data_d = _para_data(data, "data")
    hoje_d = _para_data(hoje, "hoje")
    return (data_d - hoje_d).days


def comprometido_mensal(assinaturas: list, parcelas: list) -> Decimal:
    """Quanto do orcamento mensal ja esta comprometido, somando
    assinaturas/gastos fixos recorrentes com parcelamentos ainda em
    andamento.

    `assinaturas`: lista de numeros (valor mensal) OU dicts com "valor" -
    todas entram na soma (assinatura recorrente nao "acaba sozinha").

    `parcelas`: lista de dicts com "valor_parcela" e, opcionalmente,
    "parcelas_restantes" - se essa chave existir e for <= 0, a parcela ja
    quitada NAO entra na soma (nao esta mais comprometendo o mes); se a
    chave nao existir, assume que a parcela ainda esta ativa.
    """
    total = ZERO

    for i, item in enumerate(assinaturas):
        if isinstance(item, dict):
            if "valor" not in item:
                raise ValueError(f"assinaturas[{i}] invalido: falta a chave 'valor'")
            valor = item["valor"]
        else:
            valor = item
        total += _dec(valor, f"assinaturas[{i}]")

    for i, item in enumerate(parcelas):
        if not isinstance(item, dict) or "valor_parcela" not in item:
            raise ValueError(f"parcelas[{i}] invalido: {item!r} (esperava um dict com 'valor_parcela')")
        restantes = item.get("parcelas_restantes")
        if restantes is not None and _dec(restantes, f"parcelas[{i}].parcelas_restantes") <= ZERO:
            continue
        total += _dec(item["valor_parcela"], f"parcelas[{i}].valor_parcela")

    return _money(total)
