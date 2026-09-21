import re
from collections import Counter
from datetime import date, timedelta

_PALAVRAS_IGNORADAS = {"de", "da", "do", "em", "no", "na", "para", "com", "e", "a", "o", "ltda", "sa"}


def _tokenizar(texto: str) -> set[str]:
    """Palavras relevantes de um texto de gasto (descricao de transacao ou
    texto capturado) - minusculas, sem preposicao/artigo, sem palavra curta
    demais pra virar ruido (ex: numero de agencia isolado)."""
    if not texto:
        return set()
    palavras = re.findall(r"[a-zà-ú0-9]+", texto.lower())
    return {p for p in palavras if p not in _PALAVRAS_IGNORADAS and len(p) > 2}


def sugerir_categoria(descricao: str, expenses_categorizados: list[dict]) -> str | None:
    """Decide uma categoria sozinho pra uma transacao importada, com base no
    historico de gastos que voce ja categorizou manualmente (captura por
    texto/voz) - sem perguntar toda vez. So decide quando o padrao e claro
    (pelo menos 2 gastos passados batendo, com folga sobre as outras
    categorias que tambem bateram) - se ficar ambiguo, prefere deixar sem
    categoria a arriscar um palpite errado. 'expenses_categorizados' e uma
    lista de dicts com 'category' e 'description' (ou 'source_text')."""
    tokens_novos = _tokenizar(descricao)
    if not tokens_novos:
        return None

    # Voto por REGISTRO historico que bate (nao por palavra sobreposta) - uma
    # unica descricao longa com varias palavras em comum nao deveria contar
    # como "2 gastos concordando"; precisa ser duas ocorrencias de verdade.
    votos = Counter()
    for e in expenses_categorizados:
        categoria = e.get("category")
        texto_base = e.get("description") or e.get("source_text") or ""
        if not categoria or not texto_base:
            continue
        if tokens_novos & _tokenizar(texto_base):
            votos[categoria] += 1

    if not votos:
        return None
    total = sum(votos.values())
    categoria_top, votos_top = votos.most_common(1)[0]
    if votos_top < 2 or votos_top / total < 0.6:
        return None
    return categoria_top


def _normalizar_descricao(texto: str | None) -> str:
    return (texto or "").strip().lower()


# Trechos que identificam uma cobranca "generica" no extrato bancario - o
# texto sozinho nao diz qual assinatura e (ex: "APPLE.COM/BILL" pode ser
# iCloud, Apple Music, ou um app qualquer) - lista simples de proposito, faz
# so uma coisa (reconhecer o padrao), sem inventar antecipadamente outras
# empresas que ninguem pediu ainda.
PADROES_COBRANCA_GENERICA = ["apple.com"]


def e_cobranca_generica(descricao: str | None) -> bool:
    descricao_norm = _normalizar_descricao(descricao)
    return any(padrao in descricao_norm for padrao in PADROES_COBRANCA_GENERICA)


def aplicar_apelidos(gastos_reais: list[dict], apelidos: dict[tuple[str, float], str]) -> list[dict]:
    """Troca a descricao de cada gasto pelo apelido conhecido (chave:
    descricao normalizada + valor exato) ANTES de agrupar recorrencia -
    assim "APPLE.COM/BILL R$14,90" e "APPLE.COM/BILL R$21,90" (duas
    assinaturas diferentes, mesmo texto de cobranca) viram "iCloud" e
    "Apple Music" antes mesmo de detectar_gastos_recorrentes ver o dado,
    entao agrupam certo (cada apelido e seu proprio grupo) sem precisar
    mudar nada na logica de agrupamento em si. Gasto sem apelido conhecido
    passa direto, sem alteracao."""
    resultado = []
    for gasto in gastos_reais:
        descricao_original = gasto.get("description") or gasto.get("source_text") or ""
        chave = (_normalizar_descricao(descricao_original), gasto["amount"])
        apelido = apelidos.get(chave)
        if apelido:
            gasto = {**gasto, "description": apelido}
        resultado.append(gasto)
    return resultado


def detectar_gastos_recorrentes(
    expenses: list[dict],
    hoje: date,
    meses_analise: int = 3,
    tolerancia: float = 0.15,
    minimo_meses: int = 2,
) -> list[dict]:
    """Identifica gastos fixos/assinaturas: a mesma descricao (comparada por
    igualdade normalizada, nao por palavra em comum - grupo errado aqui e
    pior que nao agrupar) aparecendo em pelo menos `minimo_meses` dos
    ultimos `meses_analise` meses, sempre com valor parecido (dentro de
    `tolerancia` fracionaria da media do grupo - um gasto pontual que por
    acaso repetiu o valor uma vez nao conta, mas Netflix/academia/aluguel
    sim). So passe gastos REAIS pra `expenses` (filtrar 'tipo' e
    responsabilidade de quem chama, como no resto do modulo). Cada dict de
    'expenses' precisa ter 'amount', 'category', 'description' (ou
    'source_text') e 'created_at'. Retorna ordenado do maior valor medio
    pro menor: [{"descricao", "categoria", "valor_medio",
    "meses_confirmados"}, ...]."""
    limite = (hoje - timedelta(days=31 * meses_analise)).isoformat()
    grupos: dict[tuple[str, str], list[dict]] = {}
    for e in expenses:
        dia = e["created_at"][:10]
        if dia < limite:
            continue
        descricao = e.get("description") or e.get("source_text") or ""
        chave_desc = _normalizar_descricao(descricao)
        if not chave_desc:
            continue
        categoria = e.get("category") or "outros"
        grupos.setdefault((categoria, chave_desc), []).append(e)

    recorrentes = []
    for (categoria, _chave_desc), itens in grupos.items():
        meses_distintos = {i["created_at"][:7] for i in itens}
        if len(meses_distintos) < minimo_meses:
            continue
        valores = [i["amount"] for i in itens]
        media = sum(valores) / len(valores)
        if media <= 0 or any(abs(v - media) / media > tolerancia for v in valores):
            continue
        descricao_original = itens[-1].get("description") or itens[-1].get("source_text") or ""
        recorrentes.append(
            {
                "descricao": descricao_original,
                "categoria": categoria,
                "valor_medio": round(media, 2),
                "meses_confirmados": len(meses_distintos),
            }
        )
    recorrentes.sort(key=lambda r: r["valor_medio"], reverse=True)
    return recorrentes


def total_gasto_fixo_mensal(recorrentes: list[dict]) -> float:
    return round(sum(r["valor_medio"] for r in recorrentes), 2)


def sobra_do_mes(renda_mes: float, gasto_real_mes: float, gasto_planejado_mes: float) -> dict:
    """Saldo do mes ATE AGORA: renda que ja entrou menos o que ja foi
    gasto de verdade - retrospectivo (nao tenta adivinhar gasto futuro que
    ainda nao aconteceu, seria so achismo), mas mostra tambem o quanto ja
    esta cogitado/planejado (pode ou nao virar gasto real) como um aviso a
    parte, reaproveitando o que o app.js ja separa (status 'real' vs
    'planejado') sem duplicar esse conceito."""
    sobra = round(renda_mes - gasto_real_mes, 2)
    return {
        "renda_mes": round(renda_mes, 2),
        "gasto_mes": round(gasto_real_mes, 2),
        "sobra": sobra,
        "gasto_planejado_mes": round(gasto_planejado_mes, 2),
        "sobra_considerando_planejado": round(sobra - gasto_planejado_mes, 2),
    }


def historico_diario(expenses: list[dict], dias: int, hoje: date) -> list[dict]:
    """Total gasto por dia nos ultimos `dias` dias (incluindo hoje), com
    zero nos dias sem nenhum gasto - pura conta em Python, pra desenhar um
    grafico continuo sem buraco. 'expenses' e uma lista de dicts com pelo
    menos 'amount' (float) e 'created_at' (timestamp ISO, "AAAA-MM-DD..." )."""
    inicio = hoje - timedelta(days=dias - 1)
    totais_por_dia = {}
    for e in expenses:
        dia = e["created_at"][:10]
        if dia < inicio.isoformat() or dia > hoje.isoformat():
            continue
        totais_por_dia[dia] = totais_por_dia.get(dia, 0.0) + e["amount"]

    historico = []
    for i in range(dias):
        dia = (inicio + timedelta(days=i)).isoformat()
        historico.append({"data": dia, "total": round(totais_por_dia.get(dia, 0.0), 2)})
    return historico


def resumo_semanal(expenses: list[dict], hoje: date) -> dict:
    """Compara o total gasto nos ultimos 7 dias (incluindo hoje) com os 7
    dias anteriores, e aponta a categoria que mais pesou na semana atual -
    pura conta em Python, direto dos gastos reais. 'expenses' e uma lista
    de dicts com 'amount', 'category' e 'created_at'."""
    inicio_atual = hoje - timedelta(days=6)
    fim_anterior = inicio_atual - timedelta(days=1)
    inicio_anterior = fim_anterior - timedelta(days=6)

    total_atual = 0.0
    total_anterior = 0.0
    por_categoria: dict[str, float] = {}
    for e in expenses:
        dia = e["created_at"][:10]
        if inicio_atual.isoformat() <= dia <= hoje.isoformat():
            total_atual += e["amount"]
            cat = e.get("category") or "outros"
            por_categoria[cat] = por_categoria.get(cat, 0.0) + e["amount"]
        elif inicio_anterior.isoformat() <= dia <= fim_anterior.isoformat():
            total_anterior += e["amount"]

    categoria_top = max(por_categoria, key=por_categoria.get) if por_categoria else None
    variacao_pct = None
    if total_anterior > 0:
        variacao_pct = round((total_atual - total_anterior) / total_anterior * 100)

    return {
        "total_semana": round(total_atual, 2),
        "total_semana_anterior": round(total_anterior, 2),
        "variacao_pct": variacao_pct,
        "categoria_top": categoria_top,
        "categoria_top_valor": round(por_categoria[categoria_top], 2) if categoria_top else None,
    }
