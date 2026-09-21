from datetime import date, timedelta


def inicio_da_semana(hoje: date) -> date:
    """Segunda-feira da semana de 'hoje'."""
    return hoje - timedelta(days=hoje.weekday())


def resumo_horas(voos: list[dict], hoje: date) -> dict:
    """Soma horas voadas (campo 'horas', ja realizado) na semana e no mes
    atuais e no total - pura conta em Python, nunca pela IA. 'voos' e uma
    lista de dicts com pelo menos 'data' (AAAA-MM-DD) e 'horas' (float ou
    None - None significa voo agendado, ainda nao realizado)."""
    inicio_semana = inicio_da_semana(hoje).isoformat()
    inicio_mes = hoje.replace(day=1).isoformat()
    hoje_iso = hoje.isoformat()

    realizados = [v for v in voos if v.get("horas") is not None and v["data"] <= hoje_iso]

    horas_semana = sum(v["horas"] for v in realizados if v["data"] >= inicio_semana)
    horas_mes = sum(v["horas"] for v in realizados if v["data"] >= inicio_mes)
    horas_total = sum(v["horas"] for v in realizados)

    return {
        "horas_semana": round(horas_semana, 2),
        "horas_mes": round(horas_mes, 2),
        "horas_total": round(horas_total, 2),
    }


def historico_horas_acumuladas(voos: list[dict], hoje: date) -> list[dict]:
    """Horas voadas acumuladas ao longo do tempo, so dos voos ja realizados
    (mesma regra do resumo: precisa ter 'horas' e a data nao pode ser
    futura) - pra desenhar um grafico de evolucao das horas de curso."""
    hoje_iso = hoje.isoformat()
    realizados = sorted(
        (v for v in voos if v.get("horas") is not None and v["data"] <= hoje_iso),
        key=lambda v: v["data"],
    )
    acumulado = 0.0
    historico = []
    for v in realizados:
        acumulado += v["horas"]
        historico.append({"data": v["data"], "acumulado": round(acumulado, 2)})
    return historico


def proximos_voos(voos: list[dict], hoje: date) -> list[dict]:
    """Voos agendados a partir de hoje (inclusive), em ordem cronologica -
    tanto os que ainda nao tem horas (compromisso futuro) quanto um voo de
    hoje mesmo que ja tenha horas registradas."""
    hoje_iso = hoje.isoformat()
    futuros = [v for v in voos if v["data"] >= hoje_iso]
    return sorted(futuros, key=lambda v: v["data"])


def dias_desde_ultimo_voo(voos: list[dict], hoje: date) -> int | None:
    """Quantos dias se passaram desde o voo REALIZADO mais recente (tem que
    ter 'horas' preenchido - um voo so agendado nao conta como ter voado).
    None se nunca voou ainda (sem voo realizado no historico)."""
    hoje_iso = hoje.isoformat()
    realizados = [v for v in voos if v.get("horas") is not None and v["data"] <= hoje_iso]
    if not realizados:
        return None
    ultima_data = max(v["data"] for v in realizados)
    return (hoje - date.fromisoformat(ultima_data)).days
