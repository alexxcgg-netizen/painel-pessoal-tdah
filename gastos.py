from datetime import date, timedelta


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
