"""Quando comprar passagem e reservar hotel pra uma viagem - Python puro, sem rede.

Janelas tiradas de pesquisas de preco (conferidas em 2026-10-09, ver CHANGELOG):
- voo nacional: mais barato de 3 a 8 semanas antes; comprar na ultima semana sai ~52% mais caro
  (Viajala via Folha PE, Skyscanner, Santander);
- voo nacional em feriado/alta temporada (Carnaval, fim de ano): 90 a 120 dias antes;
- voo internacional: 2 a 8 meses antes; alta temporada 4 a 10 meses (Going, Google Flights);
- hotel: alta temporada 3 a 6 meses antes, de preferencia com cancelamento gratis; fora dela,
  1 a 3 meses (comprar cedo demais nem sempre e mais barato).
Sao TENDENCIAS de pesquisa, nunca garantia de preco - o texto do card diz isso.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

# (inicio, fim) em dias ANTES da viagem - inicio > fim
JANELAS = {
    ("passagem", "nacional", False): (56, 21),
    ("passagem", "nacional", True): (120, 90),
    ("passagem", "internacional", False): (240, 60),
    ("passagem", "internacional", True): (300, 120),
    ("hotel", "nacional", False): (90, 30),
    ("hotel", "nacional", True): (180, 90),
    ("hotel", "internacional", False): (120, 45),
    ("hotel", "internacional", True): (180, 90),
}

FONTES = [
    "Viajala/Folha PE e Skyscanner (voo nacional)",
    "Going e Google Flights (voo internacional)",
    "guias de hospedagem (hotel em alta temporada)",
]


def pascoa(ano: int) -> date:
    """Domingo de Pascoa (algoritmo de Meeus/Jones/Butcher)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    mes = (h + l_ - 7 * m + 114) // 31
    dia = ((h + l_ - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


def periodos_de_alta(ano: int) -> list[tuple[date, date, str]]:
    """Periodos de alta demanda no Brasil num ano (inclusivo)."""
    p = pascoa(ano)
    terca_carnaval = p - timedelta(days=47)
    return [
        (date(ano, 1, 1), date(ano, 1, 6), "Réveillon"),
        (terca_carnaval - timedelta(days=3), terca_carnaval + timedelta(days=1), "Carnaval"),
        (p - timedelta(days=3), p, "Semana Santa"),
        (date(ano, 7, 1), date(ano, 7, 31), "férias de julho"),
        (date(ano, 12, 20), date(ano, 12, 31), "Natal e fim de ano"),
    ]


def alta_temporada(dia: date) -> tuple[date, date, str] | None:
    for ini, fim, nome in periodos_de_alta(dia.year):
        if ini <= dia <= fim:
            return ini, fim, nome
    return None


def _status(hoje: date, ini: date, fim: date) -> dict:
    if hoje > fim:
        return {"status": "passou", "dias": (hoje - fim).days}
    if hoje >= ini:
        return {"status": "agora", "dias": (fim - hoje).days}
    return {"status": "em_breve", "dias": (ini - hoje).days}


def _janelas(ida: date, hoje: date, internacional: bool, alta: bool) -> list[dict]:
    escopo = "internacional" if internacional else "nacional"
    saida = []
    for item in ("passagem", "hotel"):
        antes_ini, antes_fim = JANELAS[(item, escopo, alta)]
        ini, fim = ida - timedelta(days=antes_ini), ida - timedelta(days=antes_fim)
        saida.append({"item": item, "inicio": ini.isoformat(), "fim": fim.isoformat(), **_status(hoje, ini, fim)})
    return saida


def planejar(ida: date | None = None, mes: str | None = None, internacional: bool = False,
             hoje: date | None = None) -> dict:
    """`ida` (dia exato) ou `mes` ('AAAA-MM', dia ainda indefinido). Com so o mes e um
    periodo de alta dentro dele (ex: Carnaval em fevereiro), devolve os DOIS cenarios
    - no feriado e fora dele - pro Alex decidir."""
    hoje = hoje or date.today()
    if ida is None:
        if not mes:
            raise ValueError("informe a data da ida ou o mes")
        ano, m = (int(x) for x in mes.split("-")[:2])
        ultimo = calendar.monthrange(ano, m)[1]
        altas = [(i, f, n) for i, f, n in periodos_de_alta(ano) if i.month == m or f.month == m]
        # dia de referencia fora do feriado: dia 15 (ou 5 se o feriado pega o meio do mes)
        ref = date(ano, m, 15)
        if any(i <= ref <= f for i, f, _ in altas):
            ref = date(ano, m, 5) if not any(i <= date(ano, m, 5) <= f for i, f, _ in altas) else date(ano, m, ultimo)
        cenarios = {"fora": {"ida": ref.isoformat(), "alta": None, "janelas": _janelas(ref, hoje, internacional, False)}}
        if altas:
            ini, fim, nome = altas[0]
            dia_feriado = max(ini, date(ano, m, 1))
            cenarios["no_feriado"] = {
                "ida": dia_feriado.isoformat(),
                "alta": {"nome": nome, "de": ini.isoformat(), "ate": fim.isoformat()},
                "janelas": _janelas(dia_feriado, hoje, internacional, True),
            }
        return {"mes": f"{ano:04d}-{m:02d}", "dia_definido": False, "internacional": internacional,
                "cenarios": cenarios, "fontes": FONTES}

    alta = alta_temporada(ida)
    cenario = {
        "ida": ida.isoformat(),
        "alta": {"nome": alta[2], "de": alta[0].isoformat(), "ate": alta[1].isoformat()} if alta else None,
        "janelas": _janelas(ida, hoje, internacional, bool(alta)),
    }
    return {"mes": ida.strftime("%Y-%m"), "dia_definido": True, "internacional": internacional,
            "cenarios": {"no_feriado" if alta else "fora": cenario}, "fontes": FONTES}
