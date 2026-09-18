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
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE date(created_at) BETWEEN ? AND ?",
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
