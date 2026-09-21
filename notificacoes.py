"""Verificacoes proativas - cada funcao decide sozinha, em Python puro (sem
IA), se ha algo notavel o bastante pra mandar uma notificacao push. A
orquestracao (deduplicar por dia, mandar o push, marcar como enviado) fica
em app.py."""

from datetime import date, datetime, timedelta


def tarefas_atrasadas(conn) -> str | None:
    hoje = date.today().isoformat()
    n = conn.execute(
        """SELECT COUNT(*) AS n FROM tasks
           WHERE completed_at IS NULL AND due_date IS NOT NULL AND due_date < ?""",
        (hoje,),
    ).fetchone()["n"]
    if n == 0:
        return None
    if n == 1:
        return "Voce tem 1 tarefa atrasada."
    return f"Voce tem {n} tarefas atrasadas."


def tarefas_com_horario_chegando(conn, agora: datetime | None = None) -> list[tuple[int, str]]:
    """Tarefas pendentes com horario marcado pra hoje cujo horario ja
    chegou (ou passou) - pra virar um lembrete de verdade (push) na hora
    certa, nao so aparecer numa lista que precisa abrir o app pra ver."""
    agora = agora or datetime.now()
    hoje = agora.date().isoformat()
    hora_atual = agora.strftime("%H:%M")
    rows = conn.execute(
        """SELECT id, title, hora FROM tasks
           WHERE completed_at IS NULL AND due_date = ? AND hora IS NOT NULL AND hora <= ?""",
        (hoje, hora_atual),
    ).fetchall()
    return [(r["id"], f"\"{r['title']}\" - {r['hora']}.") for r in rows]


def metas_fora_do_ritmo(conn, tolerancia: float = 0.7) -> list[tuple[int, str]]:
    """Compara o quanto ja devia ter guardado (proporcional ao tempo passado
    desde a criacao ate o prazo) com o que realmente guardou. So considera
    metas com prazo definido."""
    hoje = date.today()
    avisos = []
    metas = conn.execute("SELECT * FROM goals WHERE prazo IS NOT NULL").fetchall()
    for m in metas:
        prazo = date.fromisoformat(m["prazo"])
        criado = datetime.fromisoformat(m["criado_em"]).date()
        total_dias = (prazo - criado).days
        dias_passados = (hoje - criado).days
        if total_dias <= 0 or dias_passados <= 0 or hoje >= prazo:
            continue
        fracao = min(dias_passados / total_dias, 1)
        esperado = m["valor_alvo"] * fracao
        if esperado > 0 and m["valor_guardado"] < esperado * tolerancia:
            avisos.append(
                (m["id"], f"Meta \"{m['titulo']}\" esta atras do ritmo pra bater o prazo.")
            )
    return avisos


def _total_gasto_entre(conn, inicio: date, fim: date) -> float:
    """So conta gasto 'real' (ja aconteceu) - um gasto so cogitado/planejado
    nao deveria disparar alerta de "gastou demais essa semana", ja que pode
    nem chegar a acontecer."""
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses "
        "WHERE date(created_at) BETWEEN ? AND ? AND tipo = 'real'",
        (inicio.isoformat(), fim.isoformat()),
    ).fetchone()
    return row["total"]


def gasto_semana_elevado(conn, limiar: float = 1.4) -> str | None:
    """Compara o gasto da semana atual (ate hoje) com a media das 3 semanas
    anteriores completas."""
    hoje = date.today()
    inicio_semana_atual = hoje - timedelta(days=hoje.weekday())
    total_atual = _total_gasto_entre(conn, inicio_semana_atual, hoje)

    totais_anteriores = []
    for i in range(1, 4):
        fim = inicio_semana_atual - timedelta(days=1 + 7 * (i - 1))
        inicio = fim - timedelta(days=6)
        totais_anteriores.append(_total_gasto_entre(conn, inicio, fim))

    media = sum(totais_anteriores) / len(totais_anteriores) if totais_anteriores else 0
    if media <= 0 or total_atual < limiar * media:
        return None
    return (
        f"Gasto dessa semana ja esta em R$ {total_atual:.2f}, "
        f"acima da media das ultimas semanas (R$ {media:.2f})."
    )


def _proxima_ocorrencia(data_base: date, recorrente: bool, hoje: date) -> date:
    """Pra lembrete unico, a proxima ocorrencia e a propria data. Pra
    recorrente (anual - tipo validade de licenca, exame medico, seguro),
    acha o proximo aniversario dessa data a partir de hoje."""
    if not recorrente:
        return data_base
    for ano in (hoje.year, hoje.year + 1):
        try:
            candidata = date(ano, data_base.month, data_base.day)
        except ValueError:
            candidata = date(ano, data_base.month, 28)  # 29 de fevereiro em ano nao bissexto
        if candidata >= hoje:
            return candidata
    return data_base


def lembretes_proximos(conn, dias: int = 7) -> list[tuple[int, str]]:
    """Lembretes (unicos ou recorrentes) cuja proxima ocorrencia cai dentro
    da janela de `dias` a partir de hoje."""
    hoje = date.today()
    avisos = []
    for row in conn.execute("SELECT * FROM lembretes").fetchall():
        data_base = date.fromisoformat(row["data"])
        proxima = _proxima_ocorrencia(data_base, bool(row["recorrente"]), hoje)
        dias_restantes = (proxima - hoje).days
        if not (0 <= dias_restantes <= dias):
            continue
        if dias_restantes == 0:
            quando = "e hoje"
        elif dias_restantes == 1:
            quando = "e amanha"
        else:
            quando = f"e em {dias_restantes} dias"
        avisos.append(
            (row["id"], f"\"{row['titulo']}\" {quando} ({proxima.strftime('%d/%m')}).")
        )
    return avisos


def planejamento_semanal_devido(agora: datetime | None = None) -> bool:
    """Verdadeiro na janela de 5min em torno de domingo as 20:30 - o momento
    que o Alex escolheu pra parar e pensar na semana que comeca, puxando um
    push que pergunta se ele ja sabe a agenda da semana. A deduplicacao por
    dia (ja_notificou_hoje, em app.py) garante que so dispara uma vez mesmo
    rodando a cada 5min dentro dessa janela."""
    agora = agora or datetime.now()
    if agora.weekday() != 6:  # segunda=0 ... domingo=6
        return False
    alvo = agora.replace(hour=20, minute=30, second=0, microsecond=0)
    return alvo <= agora < alvo + timedelta(minutes=5)


def voos_de_hoje_com_horario(conn, hoje: date | None = None) -> list[dict]:
    """Voos de hoje com horario marcado que ainda nao aconteceram (sem
    'horas' voadas registradas ainda) - candidatos pra calcular a hora de
    sair de casa. So identifica QUAIS voos checar; o calculo em si (trajeto
    via Maps, que pede rede) e a decisao de "esta perto o bastante pra
    avisar" ficam em app.py (verificar_e_notificar), pra esta funcao
    continuar pura e testavel so com SQLite, como as outras deste modulo."""
    hoje = hoje or date.today()
    rows = conn.execute(
        "SELECT id, destino, data, hora FROM voos WHERE data = ? AND hora IS NOT NULL AND horas IS NULL",
        (hoje.isoformat(),),
    ).fetchall()
    return [dict(r) for r in rows]
