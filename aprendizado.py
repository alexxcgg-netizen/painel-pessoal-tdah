"""Aprendizado de padrao pessoal - estatistica pura em cima do seu proprio
historico (SQLite), sem IA/rede neural: cada limiar "fixo" (dias pra cobrar
tarefa parada, dias pra cobrar espera) vira personalizado com base no que
voce realmente costuma fazer, assim que houver historico suficiente pra
confiar nisso. Enquanto nao houver, usa o padrao conservador de sempre.

Tudo aqui roda por tras das cameras: nenhuma funcao deste modulo gera texto
pra tela ou pro chat dizendo "eu aprendi isso" - o efeito aparece so no
COMPORTAMENTO (quando cutuca, que dia sugere), nunca como uma frase
explicando a si mesmo. GET /api/aprendizado existe so como auditoria tecnica
(nao e chamado por nenhuma tela do painel)."""

import re
from collections import Counter
from datetime import date, datetime

import db

# Quantas amostras mais recentes entram na conta do limiar GLOBAL (nao no
# especifico por titulo/quem, que ja costuma ter poucas amostras de qualquer
# jeito) - da mais peso pro que voce fez ultimamente do que pro que fazia ha
# muito tempo, sem descartar de vez o historico antigo (ainda entra se nao
# houver 20 amostras recentes).
JANELA_RECENTE = 20

_PALAVRAS_IGNORADAS = {"de", "da", "do", "em", "no", "na", "para", "com", "e", "a", "o"}


def _tokenizar(texto: str) -> set[str]:
    """Palavras relevantes de um titulo/nome - minusculas, sem
    preposicao/artigo, sem palavra curta demais pra virar ruido. Mesmo
    espirito do tokenizador de gastos.py, mas mantido separado aqui (texto
    de titulo de tarefa e bem mais curto que descricao de transacao, nao
    vale acoplar os dois modulos por uma funcao de 5 linhas)."""
    if not texto:
        return set()
    palavras = re.findall(r"[a-zà-ú0-9]+", texto.lower())
    return {p for p in palavras if p not in _PALAVRAS_IGNORADAS and len(p) > 2}


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


def _tarefas_atrasadas_detalhe(conn) -> list[dict]:
    """Cada tarefa concluida que realmente atrasou (devido e concluida, com
    dias > 0), com id/titulo/quantos dias - ordenado da mais recente pra
    mais antiga (por conclusao), pra quem quiser so uma janela recente."""
    rows = conn.execute(
        "SELECT id, title, due_date, completed_at FROM tasks "
        "WHERE due_date IS NOT NULL AND completed_at IS NOT NULL"
    ).fetchall()
    detalhe = []
    for r in rows:
        due = date.fromisoformat(r["due_date"])
        concluida_dt = datetime.fromisoformat(r["completed_at"])
        dias = (concluida_dt.date() - due).days
        if dias > 0:
            detalhe.append({"id": r["id"], "titulo": r["title"], "dias": dias, "quando": concluida_dt})
    detalhe.sort(key=lambda d: d["quando"], reverse=True)
    return detalhe


def _esperas_resolvidas_detalhe(conn) -> list[dict]:
    """Mesma ideia de _tarefas_atrasadas_detalhe, mas pra esperas resolvidas
    (id/quem/dias que levou), mais recente primeiro."""
    rows = conn.execute(
        "SELECT id, quem, criado_em, resolvido_em FROM esperas WHERE resolvido_em IS NOT NULL"
    ).fetchall()
    detalhe = []
    for r in rows:
        criada = datetime.fromisoformat(r["criado_em"]).date()
        resolvida_dt = datetime.fromisoformat(r["resolvido_em"])
        dias = (resolvida_dt.date() - criada).days
        if dias >= 0:
            detalhe.append({"id": r["id"], "quem": r["quem"], "dias": dias, "quando": resolvida_dt})
    detalhe.sort(key=lambda d: d["quando"], reverse=True)
    return detalhe


def dias_atraso_historico_tarefas(conn, janela: int | None = None) -> list[int]:
    """Quantos dias de atraso cada tarefa concluida levou entre o prazo
    (due_date) e a conclusao de fato (completed_at) - so entram tarefas com
    as duas datas preenchidas, e so as que realmente atrasaram (concluir no
    prazo ou antes nao ensina nada sobre atraso, entao nao entra na
    amostra). Com `janela`, usa so as N mais recentes (por data de
    conclusao) - da mais peso ao comportamento atual sem jogar fora o
    historico antigo quando ainda nao ha N amostras novas."""
    detalhe = _tarefas_atrasadas_detalhe(conn)
    if janela is not None:
        detalhe = detalhe[:janela]
    return [d["dias"] for d in detalhe]


def dias_espera_historico(conn, janela: int | None = None) -> list[int]:
    """Quantos dias cada espera resolvida levou entre ser criada e ser
    marcada como resolvida - so entram as ja resolvidas (uma espera ainda
    em aberto nao tem duracao final pra ensinar nada ainda). `janela` tem o
    mesmo efeito de recencia que em dias_atraso_historico_tarefas."""
    detalhe = _esperas_resolvidas_detalhe(conn)
    if janela is not None:
        detalhe = detalhe[:janela]
    return [d["dias"] for d in detalhe]


def dias_atraso_por_titulo_semelhante(conn, titulo: str, excluir_id: int | None = None) -> list[int]:
    """Mesma amostra de dias_atraso_historico_tarefas, mas filtrada as
    tarefas cujo titulo compartilha alguma palavra relevante com `titulo` -
    "cotar portas com fornecedor" e "cotar vasos com fornecedor" aprendem
    juntas, sem precisar de um campo de categoria que ninguem preenche.
    `excluir_id` tira a propria tarefa da amostra (nao faz sentido ela
    aprender com o proprio atraso, mesmo que ja tivesse dado entrada aqui)."""
    tokens = _tokenizar(titulo)
    if not tokens:
        return []
    return [
        d["dias"]
        for d in _tarefas_atrasadas_detalhe(conn)
        if d["id"] != excluir_id and tokens & _tokenizar(d["titulo"])
    ]


def dias_espera_por_quem_semelhante(conn, quem: str, excluir_id: int | None = None) -> list[int]:
    """Mesma ideia de dias_atraso_por_titulo_semelhante, mas por quem esta
    do outro lado da espera - fornecedores/pessoas diferentes tem ritmos de
    resposta bem diferentes entre si; agrupar por nome (aproximado, mesma
    logica de token que o resto do painel usa) aprende isso sem precisar de
    cadastro de fornecedor."""
    tokens = _tokenizar(quem)
    if not tokens:
        return []
    return [
        d["dias"]
        for d in _esperas_resolvidas_detalhe(conn)
        if d["id"] != excluir_id and tokens & _tokenizar(d["quem"])
    ]


def _ajustar_pela_eficacia(limiar: int, latencia_media_h: float | None, piso: int) -> int:
    """Usa a latencia de resposta APOS ser cutucado (nao antes) como sinal
    de o quanto a cutucada realmente ajuda: se, historicamente, voce resolve
    rapido (em ate 24h) depois de avisado, a cutucada esta funcionando bem -
    vale a pena avisar um pouco mais cedo da proxima vez (reduz 1 dia, nunca
    abaixo do piso). Se demora mesmo depois de avisado, cutucar mais cedo
    nao ajudaria em nada - mantem o limiar como estava."""
    if latencia_media_h is not None and latencia_media_h <= 24:
        return max(piso, limiar - 1)
    return limiar


def limiar_tarefa(
    conn, titulo: str, task_id: int | None = None, padrao: int = 3, teto: int = 14
) -> tuple[int, dict]:
    """Decisao final de quantos dias esperar antes de cobrar ESSA tarefa
    especifica: tenta primeiro o historico de tarefas com titulo parecido
    (mais preciso, quando ha amostra); sem isso, cai pro aprendizado GLOBAL
    (janela recente); sem isso, cai pro padrao fixo. Em qualquer um dos
    tres casos, ainda ajusta pela eficacia da cutucada (ve _ajustar_pela_eficacia)."""
    piso = 1
    especificas = dias_atraso_por_titulo_semelhante(conn, titulo, excluir_id=task_id)
    valor, info = limiar_personalizado(especificas, padrao=padrao, teto=teto, piso=piso)
    if info["fonte"] == "aprendido":
        info["fonte"] = "aprendido_especifico"
    else:
        globais = dias_atraso_historico_tarefas(conn, janela=JANELA_RECENTE)
        valor, info = limiar_personalizado(globais, padrao=padrao, teto=teto, piso=piso)
        if info["fonte"] == "aprendido":
            info["fonte"] = "aprendido_global"

    latencia = latencia_media_horas(db.latencias_resolvidas(conn, "tarefa_parada"))
    valor_ajustado = _ajustar_pela_eficacia(valor, latencia, piso)
    info["latencia_media_horas"] = latencia
    info["ajustado_pela_eficacia"] = valor_ajustado != valor
    return valor_ajustado, info


def limiar_espera(
    conn, quem: str, espera_id: int | None = None, padrao: int = 5, teto: int = 21
) -> tuple[int, dict]:
    """Mesma logica de limiar_tarefa, mas pro lado das esperas de
    terceiros: especifico por quem -> global (janela recente) -> padrao,
    tambem ajustado pela eficacia da cutucada."""
    piso = 1
    especificas = dias_espera_por_quem_semelhante(conn, quem, excluir_id=espera_id)
    valor, info = limiar_personalizado(especificas, padrao=padrao, teto=teto, piso=piso)
    if info["fonte"] == "aprendido":
        info["fonte"] = "aprendido_especifico"
    else:
        globais = dias_espera_historico(conn, janela=JANELA_RECENTE)
        valor, info = limiar_personalizado(globais, padrao=padrao, teto=teto, piso=piso)
        if info["fonte"] == "aprendido":
            info["fonte"] = "aprendido_global"

    latencia = latencia_media_horas(db.latencias_resolvidas(conn, "espera_parada"))
    valor_ajustado = _ajustar_pela_eficacia(valor, latencia, piso)
    info["latencia_media_horas"] = latencia
    info["ajustado_pela_eficacia"] = valor_ajustado != valor
    return valor_ajustado, info


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


def produtividade_por_dia_semana(conn, minimo_amostras: int = 3) -> dict[int, float]:
    """Taxa de tarefas concluidas NO PRAZO, agrupada pelo dia da semana em
    que o prazo caia (devido, nao a data de conclusao - a pergunta e "tarefas
    que deviam terminar numa segunda, costumam mesmo terminar no prazo?").
    So considera tarefas cujo prazo ja passou (senao "ainda nao venceu"
    contaria como fracasso injustamente). Dias com menos de
    `minimo_amostras` tarefas vencidas ficam de fora do dict (ausencia de
    dado e tratada como neutra, nunca como dia ruim)."""
    hoje = date.today()
    rows = conn.execute("SELECT due_date, completed_at FROM tasks WHERE due_date IS NOT NULL").fetchall()
    total_por_dia = Counter()
    no_prazo_por_dia = Counter()
    for r in rows:
        devido = date.fromisoformat(r["due_date"])
        if devido > hoje:
            continue
        dia_semana = devido.weekday()
        total_por_dia[dia_semana] += 1
        if r["completed_at"] and datetime.fromisoformat(r["completed_at"]).date() <= devido:
            no_prazo_por_dia[dia_semana] += 1
    return {
        dia: no_prazo_por_dia[dia] / total_por_dia[dia]
        for dia in total_por_dia
        if total_por_dia[dia] >= minimo_amostras
    }


_ORDEM_BUCKETS_SONO = ["<6h", "6-7h", "7-8h", "8h+"]


def _bucket_sono(horas: float) -> str:
    if horas < 6:
        return "<6h"
    if horas < 7:
        return "6-7h"
    if horas < 8:
        return "7-8h"
    return "8h+"


def correlacao_sono_produtividade(conn, minimo_amostras: int = 3) -> dict[str, float]:
    """Taxa de tarefas concluidas NO DIA (devidas nesse dia, concluidas nesse
    mesmo dia), agrupada pela faixa de horas de sono da noite anterior
    (`saude_dados.sono_horas`, ja gravado via Atalho do iPhone). Mesmo
    principio de `produtividade_por_dia_semana`: faixa com menos de
    `minimo_amostras` tarefas fica de fora (ausencia de dado e neutra, nunca
    dia ruim)."""
    dias_com_sono = conn.execute(
        "SELECT data, sono_horas FROM saude_dados WHERE sono_horas IS NOT NULL"
    ).fetchall()
    total_por_bucket = Counter()
    no_prazo_por_bucket = Counter()
    for d in dias_com_sono:
        tarefas_do_dia = conn.execute(
            "SELECT completed_at FROM tasks WHERE due_date = ?", (d["data"],)
        ).fetchall()
        if not tarefas_do_dia:
            continue
        bucket = _bucket_sono(d["sono_horas"])
        dia = date.fromisoformat(d["data"])
        for t in tarefas_do_dia:
            total_por_bucket[bucket] += 1
            if t["completed_at"] and datetime.fromisoformat(t["completed_at"]).date() == dia:
                no_prazo_por_bucket[bucket] += 1
    return {
        b: no_prazo_por_bucket[b] / total_por_bucket[b]
        for b in total_por_bucket
        if total_por_bucket[b] >= minimo_amostras
    }


def dica_sono_produtividade(conn, minimo_amostras: int = 3, diferenca_minima: float = 0.15) -> str | None:
    """Frase pronta pra tela, so quando houver dado suficiente E uma diferenca
    real entre a melhor e a pior faixa de sono (senao fica ruido, nao dica).
    None quando nao da pra dizer nada confiavel ainda."""
    correlacao = correlacao_sono_produtividade(conn, minimo_amostras)
    if len(correlacao) < 2:
        return None
    melhor = max(correlacao, key=correlacao.get)
    pior = min(correlacao, key=correlacao.get)
    if melhor == pior or correlacao[melhor] - correlacao[pior] < diferenca_minima:
        return None
    melhor_pct = round(correlacao[melhor] * 100)
    pior_pct = round(correlacao[pior] * 100)
    sugestao = ""
    if _ORDEM_BUCKETS_SONO.index(melhor) > _ORDEM_BUCKETS_SONO.index(pior):
        sugestao = " Vale tentar dormir mais nos dias que tem tarefa importante."
    return (
        f"Nos dias com {melhor} de sono, {melhor_pct}% das tarefas do dia saem no prazo - "
        f"nos dias com {pior}, so {pior_pct}%.{sugestao}"
    )


def media_checkin_por_faixa_sono(conn, campo: str, minimo_amostras: int = 3) -> dict[str, float]:
    """Media do check-in do dia (energia ou humor, 1=ruim 3=bom) agrupada pela
    faixa de horas de sono da noite (saude_dados.sono_horas). Mesma regra das
    outras correlacoes: faixa com poucas amostras fica de fora."""
    if campo not in ("energia", "humor"):
        raise ValueError(campo)
    rows = conn.execute(
        f"SELECT s.sono_horas, c.{campo} AS valor FROM saude_dados s "
        f"JOIN checkins c ON c.data = s.data "
        f"WHERE s.sono_horas IS NOT NULL AND c.{campo} IS NOT NULL"
    ).fetchall()
    soma = Counter()
    total = Counter()
    for r in rows:
        faixa = _bucket_sono(r["sono_horas"])
        soma[faixa] += r["valor"]
        total[faixa] += 1
    return {f: soma[f] / total[f] for f in total if total[f] >= minimo_amostras}


def dica_sono_humor(conn, minimo_amostras: int = 3, diferenca_minima: float = 0.5) -> str | None:
    """Frase so quando a diferenca entre a melhor e a pior faixa de sono for
    real (meio ponto na escala de 1 a 3) - senao e ruido."""
    rotulo = {1: "ruim", 2: "ok", 3: "bom"}
    partes = []
    for campo in ("humor", "energia"):
        medias = media_checkin_por_faixa_sono(conn, campo, minimo_amostras)
        if len(medias) < 2:
            continue
        melhor = max(medias, key=medias.get)
        pior = min(medias, key=medias.get)
        if medias[melhor] - medias[pior] < diferenca_minima:
            continue
        alto, baixo = rotulo[round(medias[melhor])], rotulo[round(medias[pior])]
        if alto == baixo:
            partes.append(f"seu {campo} fica melhor depois de {melhor} de sono do que depois de {pior}")
        else:
            partes.append(
                f"seu {campo} fica mais pra '{alto}' depois de {melhor} de sono e mais pra '{baixo}' depois de {pior}"
            )
    if not partes:
        return None
    return "Pelo seu check-in, " + "; ".join(partes) + "."
