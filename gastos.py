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
