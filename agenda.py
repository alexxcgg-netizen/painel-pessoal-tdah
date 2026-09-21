"""Funcoes puras (sem IA, sem rede) pra ajudar a distribuir tarefas soltas
ao longo da semana e achar horario livre no dia - usadas pelo chat quando
o Alex pede uma sugestao de dia/horario em vez de escolher ele mesmo."""

from datetime import date, timedelta

DIAS_SEMANA_PT = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]


def dias_ate_o_fim_da_semana(hoje: date) -> list[date]:
    """De hoje ate domingo (fim da semana atual) - a semana comeca na
    segunda (weekday 0) e termina no domingo (weekday 6)."""
    dias_restantes = 6 - hoje.weekday()
    return [hoje + timedelta(days=i) for i in range(dias_restantes + 1)]


def sugerir_dia_menos_corrido(
    carga_por_dia: dict[str, int],
    dias_candidatos: list[date],
    produtividade_por_dia_semana: dict[int, float] | None = None,
) -> dict:
    """Escolhe, entre os dias candidatos, o que tem menos compromissos ja
    marcados - empate resolve pro dia mais proximo, pra nao arriscar
    empurrar de mais e esquecer. 'carga_por_dia' e um dict data-ISO ->
    quantidade de compromissos naquele dia (dias sem entrada valem 0).

    'produtividade_por_dia_semana' (opcional) e um dict dia-da-semana (0-6)
    -> taxa historica de concluir tarefas no prazo nesse dia - quando
    presente, um dia em que voce historicamente da conta melhor ganha um
    pequeno desconto na carga (pode empatar/vencer um dia com carga um
    pouco menor mas onde voce historicamente rende menos), sem nunca
    overridar completamente a carga real."""
    produtividade_por_dia_semana = produtividade_por_dia_semana or {}

    def pontuacao(d: date) -> tuple[float, date]:
        carga = carga_por_dia.get(d.isoformat(), 0)
        bonus = produtividade_por_dia_semana.get(d.weekday(), 0.0) * 0.5
        return (carga - bonus, d)

    escolhido = min(dias_candidatos, key=pontuacao)
    return {
        "data": escolhido.isoformat(),
        "dia_semana": DIAS_SEMANA_PT[escolhido.weekday()],
        "carga": carga_por_dia.get(escolhido.isoformat(), 0),
    }


def _para_minutos(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _para_hhmm(minutos: int) -> str:
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def maior_janela_livre(
    compromissos: list[tuple[str, str]], inicio_dia: str, fim_dia: str, duracao_minutos: int
) -> dict | None:
    """Acha o maior intervalo livre entre 'inicio_dia' e 'fim_dia' (ambos
    "HH:MM") considerando os compromissos ja ocupados (lista de tuplas
    (inicio, fim), tambem em "HH:MM"). Devolve o maior intervalo se ele
    comportar pelo menos 'duracao_minutos', senao None (dia cheio demais
    ou nenhuma folga grande o bastante)."""
    inicio_min = _para_minutos(inicio_dia)
    fim_min = _para_minutos(fim_dia)
    ocupados = sorted(
        (max(_para_minutos(i), inicio_min), min(_para_minutos(f), fim_min))
        for i, f in compromissos
        if _para_minutos(f) > inicio_min and _para_minutos(i) < fim_min
    )

    livres = []
    cursor = inicio_min
    for ini, fim in ocupados:
        if ini > cursor:
            livres.append((cursor, ini))
        cursor = max(cursor, fim)
    if cursor < fim_min:
        livres.append((cursor, fim_min))

    if not livres:
        return None
    melhor = max(livres, key=lambda janela: janela[1] - janela[0])
    if melhor[1] - melhor[0] < duracao_minutos:
        return None
    return {
        "inicio": _para_hhmm(melhor[0]),
        "fim": _para_hhmm(melhor[1]),
        "minutos": melhor[1] - melhor[0],
    }
