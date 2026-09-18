from datetime import date, timedelta


def calcular_streak(dias_ativos: set, hoje: date) -> int:
    """Conta dias consecutivos de atividade terminando hoje ou ontem.

    Se ainda nao teve atividade hoje mas teve ontem, a sequencia continua
    valendo (so quebra depois de um dia inteiro sem uso) - evita punir o
    usuario as 00h01 por ainda nao ter aberto o app.
    """
    cursor = hoje
    if cursor.isoformat() not in dias_ativos:
        cursor -= timedelta(days=1)
        if cursor.isoformat() not in dias_ativos:
            return 0

    streak = 0
    while cursor.isoformat() in dias_ativos:
        streak += 1
        cursor -= timedelta(days=1)
    return streak
