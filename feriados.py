"""Calendario brasileiro (2026-10-13, pedido do Alex: "ela saber quando e feriado").

Tudo CALCULADO em codigo - vale pra qualquer ano, nunca desatualiza e nao depende de API:
- feriados nacionais fixos (Lei 662/1949, 6.802/1980, 14.759/2023 - Consciencia Negra);
- moveis pela Pascoa (algoritmo de Meeus/Butcher): Sexta-feira Santa (feriado), Carnaval e
  Corpus Christi (ponto facultativo nacional - depende de decreto da cidade/empresa);
- Brusque: aniversario da cidade, 4 de agosto (feriado municipal);
- Santa Catarina: Data Magna (11/08) e transferida por lei pro domingo seguinte, entao entra
  so como data comemorativa (nao e folga).
Ponto facultativo vai marcado como tal: o assistente nunca diz "e feriado" pra ele.
"""

from __future__ import annotations

from datetime import date, timedelta

FERIADO = "feriado"
FACULTATIVO = "ponto facultativo"
COMEMORATIVA = "data comemorativa"

_FIXOS = [
    (1, 1, "Confraternização Universal (Ano-Novo)", FERIADO),
    (4, 21, "Tiradentes", FERIADO),
    (5, 1, "Dia do Trabalho", FERIADO),
    (9, 7, "Independência do Brasil", FERIADO),
    (10, 12, "Nossa Senhora Aparecida", FERIADO),
    (11, 2, "Finados", FERIADO),
    (11, 15, "Proclamação da República", FERIADO),
    (11, 20, "Dia da Consciência Negra", FERIADO),
    (12, 25, "Natal", FERIADO),
    (8, 4, "Aniversário de Brusque (feriado municipal)", FERIADO),
    (12, 24, "Véspera de Natal (meio expediente em muito lugar)", FACULTATIVO),
    (12, 31, "Véspera de Ano-Novo (meio expediente em muito lugar)", FACULTATIVO),
]


def pascoa(ano: int) -> date:
    """Domingo de Pascoa (algoritmo de Meeus/Jones/Butcher, calendario gregoriano)."""
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes, dia = divmod(h + l - 7 * m + 114, 31)
    return date(ano, mes, dia + 1)


def _data_magna_sc(ano: int) -> date:
    d = date(ano, 8, 11)
    return d if d.weekday() == 6 else d + timedelta(days=(6 - d.weekday()))


def do_ano(ano: int) -> list[dict]:
    """[{data, nome, tipo}] em ordem de data."""
    p = pascoa(ano)
    lista = [{"data": date(ano, m, d), "nome": nome, "tipo": tipo} for m, d, nome, tipo in _FIXOS]
    lista += [
        {"data": p - timedelta(days=48), "nome": "Carnaval (segunda)", "tipo": FACULTATIVO},
        {"data": p - timedelta(days=47), "nome": "Carnaval (terça)", "tipo": FACULTATIVO},
        {"data": p - timedelta(days=46), "nome": "Quarta-feira de Cinzas (até 14h)", "tipo": FACULTATIVO},
        {"data": p - timedelta(days=2), "nome": "Sexta-feira Santa", "tipo": FERIADO},
        {"data": p, "nome": "Páscoa", "tipo": COMEMORATIVA},
        {"data": p + timedelta(days=60), "nome": "Corpus Christi", "tipo": FACULTATIVO},
        {"data": _data_magna_sc(ano), "nome": "Data Magna de Santa Catarina (transferida pro domingo)", "tipo": COMEMORATIVA},
    ]
    return sorted(lista, key=lambda f: f["data"])


def do_dia(dia: date) -> list[dict]:
    return [f for f in do_ano(dia.year) if f["data"] == dia]


def proximos(desde: date, dias: int = 45) -> list[dict]:
    """Feriados e pontos facultativos de `desde` (inclusive) ate `dias` pra frente."""
    ate = desde + timedelta(days=dias)
    anos = {desde.year, ate.year}
    return [
        f for ano in sorted(anos) for f in do_ano(ano)
        if desde <= f["data"] <= ate and f["tipo"] != COMEMORATIVA
    ]


def emenda(f: dict) -> str | None:
    """'cai numa quinta - muita gente emenda a sexta' (so pra feriado de verdade)."""
    if f["tipo"] != FERIADO:
        return None
    dow = f["data"].weekday()
    if dow == 1:
        return "cai numa terça - muita gente emenda a segunda"
    if dow == 3:
        return "cai numa quinta - muita gente emenda a sexta"
    return None


_DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def linhas_contexto(hoje: date) -> list[str]:
    """Pro system prompt do chat: hoje (se for), amanha e os proximos ~45 dias."""
    linhas = []
    de_hoje = [f for f in do_dia(hoje) if f["tipo"] != COMEMORATIVA]
    if de_hoje:
        linhas.append("HOJE é " + "; ".join(f"{f['nome']} ({f['tipo']})" for f in de_hoje)
                      + " - comércio, banco e órgão público podem estar fechados ou em horário reduzido.")
    futuros = [f for f in proximos(hoje + timedelta(days=1)) if f["data"] != hoje]
    if futuros:
        partes = []
        for f in futuros[:5]:
            quando = "amanhã" if f["data"] == hoje + timedelta(days=1) else _DIAS[f["data"].weekday()]
            txt = f"{f['data']:%d/%m} ({quando}) {f['nome']} - {f['tipo']}"
            if emenda(f):
                txt += f", {emenda(f)}"
            partes.append(txt)
        linhas.append("Próximos feriados (Brasil + Brusque/SC): " + "; ".join(partes))
    return linhas
