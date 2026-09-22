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


def proximos_n_dias(a_partir_de: date, n: int) -> list[date]:
    """Pool de dias candidatos a partir de (e incluindo) 'a_partir_de' - usada
    por distribuir_tarefas_na_semana, que precisa de um pool maior que
    dias_ate_o_fim_da_semana (essa so vai ate domingo, pensada pra sugerir
    UMA tarefa dentro da semana atual)."""
    return [a_partir_de + timedelta(days=i) for i in range(n)]


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


# Horarios candidatos pra distribuir_tarefas_na_semana - pula almoco
# (12h-14h) e janta (18h-20h) de proposito (pedido implicito do Alex: "tem
# que lembrar que as vezes tem que tomar cafe, comer, almocar").
HORARIOS_SUGERIDOS_DIA = ["09:00", "10:30", "15:00", "16:30", "20:30"]


def distribuir_tarefas_na_semana(
    carga_por_dia: dict[str, int],
    dias_candidatos: list[date],
    titulos: list[str],
    produtividade_por_dia_semana: dict[int, float] | None = None,
) -> list[dict]:
    """Pedido explicito do Alex (TDAH, "assistente de vida" de verdade): quando
    ele despeja varias tarefas soltas de uma vez (tipo domingo listando a
    semana inteira), sugere dia+horario pra CADA uma - nao so uma. Reusa
    sugerir_dia_menos_corrido item a item, atualizando uma carga SIMULADA a
    cada escolha (carga_simulada[dia] += 1) pra nao empilhar tudo no dia que
    comecou mais vazio; o horario dentro do dia vem de
    HORARIOS_SUGERIDOS_DIA, andando pra frente a cada item novo que cai
    naquele mesmo dia (1o item do dia pega o 1o horario, 2o item pega o 2o,
    etc) - nunca dois itens novos no mesmo horario do mesmo dia.

    So MONTA a lista de propostas, nunca escreve no banco - quem decide
    quando (e se) isso vira tarefa de verdade e o codigo que chama esta
    funcao (ver confirmar_plano_semana em app.py), depois que o Alex
    confirmar explicitamente o plano."""
    carga_simulada = dict(carga_por_dia)
    usados_no_dia: dict[str, int] = {}
    propostas = []
    for titulo in titulos:
        escolhido = sugerir_dia_menos_corrido(carga_simulada, dias_candidatos, produtividade_por_dia_semana)
        dia_iso = escolhido["data"]
        indice_horario = usados_no_dia.get(dia_iso, 0)
        hora = HORARIOS_SUGERIDOS_DIA[indice_horario % len(HORARIOS_SUGERIDOS_DIA)]
        propostas.append({"titulo": titulo, "dia": dia_iso, "hora": hora})
        carga_simulada[dia_iso] = carga_simulada.get(dia_iso, 0) + 1
        usados_no_dia[dia_iso] = indice_horario + 1
    return propostas


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
