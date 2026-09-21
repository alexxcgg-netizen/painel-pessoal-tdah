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
