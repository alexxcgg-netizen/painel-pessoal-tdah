"""Aprendizado de padrao pessoal - estatistica pura em cima do seu proprio
historico (SQLite), sem IA/rede neural: cada limiar "fixo" (dias pra cobrar
tarefa parada, dias pra cobrar espera) vira personalizado com base no que
voce realmente costuma fazer, assim que houver historico suficiente pra
confiar nisso. Enquanto nao houver, usa o padrao conservador de sempre."""

from datetime import date, datetime


def _mediana(amostras: list[float]) -> float:
    ordenada = sorted(amostras)
    n = len(ordenada)
    meio = n // 2
    if n % 2 == 1:
        return ordenada[meio]
    return (ordenada[meio - 1] + ordenada[meio]) / 2


def limiar_personalizado(
    amostras: list[float],
    padrao: int,
    minimo_amostras: int = 5,
    piso: int = 1,
    teto: int = 14,
) -> tuple[int, dict]:
    """Decide o limiar (em dias) a usar: se ainda nao houver historico
    suficiente (`minimo_amostras`), fica no `padrao` conservador de sempre.
    Com historico suficiente, usa a MEDIANA das amostras (robusta a um
    unico caso fora da curva, ao contrario da media) arredondada e limitada
    a [`piso`, `teto`] - nunca deixa um historico estranho empurrar o
    limiar pra 0 dias (cutuca cedo demais) nem pra um numero absurdo alto
    (nunca mais cutuca). O segundo item retornado documenta a decisao -
    quantas amostras, de onde veio o valor, se foi limitado - pra ficar
    auditavel em vez de caixa preta."""
    if len(amostras) < minimo_amostras:
        return padrao, {
            "fonte": "padrao",
            "amostras": len(amostras),
            "motivo": f"historico insuficiente (precisa de pelo menos {minimo_amostras})",
        }
    valor = round(_mediana(amostras))
    valor_limitado = max(piso, min(valor, teto))
    return valor_limitado, {
        "fonte": "aprendido",
        "amostras": len(amostras),
        "mediana_bruta": valor,
        "limitado": valor_limitado != valor,
    }


def dias_atraso_historico_tarefas(conn) -> list[int]:
    """Quantos dias de atraso cada tarefa concluida levou entre o prazo
    (due_date) e a conclusao de fato (completed_at) - so entram tarefas com
    as duas datas preenchidas, e so as que realmente atrasaram (concluir no
    prazo ou antes nao ensina nada sobre atraso, entao nao entra na
    amostra)."""
    rows = conn.execute(
        "SELECT due_date, completed_at FROM tasks "
        "WHERE due_date IS NOT NULL AND completed_at IS NOT NULL"
    ).fetchall()
    dias_atraso = []
    for r in rows:
        due = date.fromisoformat(r["due_date"])
        concluida = datetime.fromisoformat(r["completed_at"]).date()
        dias = (concluida - due).days
        if dias > 0:
            dias_atraso.append(dias)
    return dias_atraso


def dias_espera_historico(conn) -> list[int]:
    """Quantos dias cada espera resolvida levou entre ser criada e ser
    marcada como resolvida - so entram as ja resolvidas (uma espera ainda
    em aberto nao tem duracao final pra ensinar nada ainda)."""
    rows = conn.execute(
        "SELECT criado_em, resolvido_em FROM esperas WHERE resolvido_em IS NOT NULL"
    ).fetchall()
    dias_espera = []
    for r in rows:
        criada = datetime.fromisoformat(r["criado_em"]).date()
        resolvida = datetime.fromisoformat(r["resolvido_em"]).date()
        dias = (resolvida - criada).days
        if dias >= 0:
            dias_espera.append(dias)
    return dias_espera


def latencia_media_horas(latencias: list[float]) -> float | None:
    """Media simples (nao mediana) das horas entre a cutucada (notificacao
    enviada) e a resolucao (tarefa concluida / espera resolvida). Aqui,
    diferente do limiar de disparo, um caso incomum (muito rapido ou muito
    lento) ainda e sinal real sobre o quanto a cutucada esta funcionando,
    nao ruido pra filtrar - por isso media, nao mediana. None se ainda nao
    houver nenhuma latencia registrada."""
    if not latencias:
        return None
    return sum(latencias) / len(latencias)
