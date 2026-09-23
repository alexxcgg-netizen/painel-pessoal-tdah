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
from datetime import date, datetime, timedelta

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


def contagem_itens_semana(conn, inicio: date, fim: date) -> int:
    """Quantos itens (tarefas/compromissos com prazo) caem numa semana
    [inicio, fim] (inclusive) - a mesma nocao de "carga da semana" usada
    tanto pro historico quanto pra proxima semana (US-C13), pra comparar
    maca com maca. Tarefa-modelo recorrente (recorrencia IS NOT NULL,
    due_date sempre NULL) nunca conta aqui - so instancia de verdade."""
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM tasks WHERE due_date BETWEEN ? AND ? AND recorrencia IS NULL",
        (inicio.isoformat(), fim.isoformat()),
    ).fetchone()
    return row["n"]


def carga_semanal_historica(conn, hoje: date, semanas: int = 8) -> list[int]:
    """Contagem de itens de cada uma das ultimas `semanas` semanas
    COMPLETAS (segunda a domingo, terminando antes da semana atual) -
    amostras pra comparar a proxima semana com o padrao real do proprio
    usuario, nunca com um numero fixo arbitrario."""
    inicio_semana_atual = hoje - timedelta(days=hoje.weekday())
    amostras = []
    for i in range(1, semanas + 1):
        fim = inicio_semana_atual - timedelta(days=1 + 7 * (i - 1))
        inicio = fim - timedelta(days=6)
        amostras.append(contagem_itens_semana(conn, inicio, fim))
    return amostras


def semana_pesada(
    contagem_proxima: int,
    historico: list[int],
    minimo_amostras: int = 3,
    multiplicador: float = 1.5,
) -> dict:
    """Decide se a proxima semana esta sobrecarregada comparando com a
    MEDIANA do historico de semanas anteriores (estatistica pura, robusta a
    uma unica semana fora da curva - mesmo espirito de limiar_personalizado
    acima). So considera semanas historicas com pelo menos 1 item (uma
    semana vazia nao ensina nada sobre "carga normal"). Sem amostras
    suficientes, NUNCA acusa sobrecarga - dado de menos e pior que um alarme
    falso. Pra contar como pesada, a proxima semana precisa passar tanto do
    multiplicador (`multiplicador`x a mediana) quanto de uma diferenca
    minima absoluta de 2 itens - evita marcar como "pesada" um salto
    pequeno (1 pra 2 itens ja e 2x, mas nao e sobrecarga de verdade)."""
    amostras_validas = [a for a in historico if a > 0]
    if len(amostras_validas) < minimo_amostras:
        return {
            "sobrecarregada": False,
            "contagem_proxima": contagem_proxima,
            "mediana_historica": None,
            "amostras": len(amostras_validas),
        }
    mediana = _mediana(amostras_validas)
    sobrecarregada = (
        mediana > 0
        and contagem_proxima >= mediana * multiplicador
        and contagem_proxima - mediana >= 2
    )
    return {
        "sobrecarregada": sobrecarregada,
        "contagem_proxima": contagem_proxima,
        "mediana_historica": mediana,
        "amostras": len(amostras_validas),
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


# Quantas palavras relevantes em comum com uma correcao anterior ja contam
# como "parecido o suficiente" pra dar de pista pra proxima classificacao -
# criterio simples de proposito (mesmo espirito do resto do modulo): duas
# palavras batendo (ex: "netflix" e "assinatura") ja e sinal forte o
# bastante pra nao ser coincidencia de artigo/preposicao comum, sem exigir
# frase quase identica.
LIMIAR_TOKENS_CORRECAO = 2


def correcao_semelhante(conn, texto: str) -> dict | None:
    """Procura, entre as correcoes de classificacao que o Alex ja fez
    (tabela correcoes_classificacao, gravada quando ele corrige uma captura
    que a IA classificou errado), uma cujo texto original compartilhe pelo
    menos LIMIAR_TOKENS_CORRECAO palavras relevantes com o texto novo -
    mesmo criterio de dias_atraso_por_titulo_semelhante acima, so que aqui o
    resultado nao e um numero, e o proprio veredito (tipo/categoria certos)
    que o Alex deu da ultima vez que corrigiu algo parecido. Com mais de uma
    correcao parecida, fica com a que tiver mais palavras em comum
    (desempate: a mais recente, ja que list_correcoes_classificacao volta
    ordenado por criado_em DESC). None se nao houver nenhuma parecida o
    suficiente - o caso mais comum, ja que a maioria das capturas nao tem
    historico de correcao nenhum."""
    tokens = _tokenizar(texto)
    if not tokens:
        return None
    melhor = None
    melhor_pontos = 0
    for correcao in db.list_correcoes_classificacao(conn):
        comuns = tokens & _tokenizar(correcao["texto_original"])
        if len(comuns) >= LIMIAR_TOKENS_CORRECAO and len(comuns) > melhor_pontos:
            melhor_pontos = len(comuns)
            melhor = correcao
    return melhor


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
    # sono_horas e criptografado em repouso - db.list_saude_dados ja devolve
    # descriptografado, entao o "IS NOT NULL" que era filtro de SQL agora e
    # feito aqui.
    dias_com_sono = [l for l in db.list_saude_dados(conn) if l["sono_horas"] is not None]
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
    # sono_horas e criptografado - o JOIN+WHERE que filtrava no SQL vira um
    # join manual em Python entre saude_dados (ja descriptografado por
    # db.list_saude_dados) e checkins, por data.
    sono_por_dia = {
        l["data"]: l["sono_horas"] for l in db.list_saude_dados(conn) if l["sono_horas"] is not None
    }
    checkins_rows = conn.execute(
        f"SELECT data, {campo} AS valor FROM checkins WHERE {campo} IS NOT NULL"
    ).fetchall()
    soma = Counter()
    total = Counter()
    for r in checkins_rows:
        sono_horas = sono_por_dia.get(r["data"])
        if sono_horas is None:
            continue
        faixa = _bucket_sono(sono_horas)
        soma[faixa] += r["valor"]
        total[faixa] += 1
    return {f: soma[f] / total[f] for f in total if total[f] >= minimo_amostras}


# ---- Padrao aprendido de intent (Fase 5, US-A3/US-A4) ---------------------
# Camada "robo" antes da IA no classificador de intent (US-A2): comando
# repetido/parecido o suficiente resolve localmente, sem gastar chamada de
# API. Mesmo principio do resto do modulo: estatistica pura de repeticao
# (nao semantica - texto diferente nunca bate), e nunca comunica ao usuario
# que "aprendeu" algo - o efeito e so a IA nao ser chamada de novo.
#
# normalizar_texto_intent/LIMIAR_CONFIRMACOES_PADRAO_INTENT moram de verdade
# em db.py (db.registrar_correcao_classificacao, US-A4, precisa deles sem
# importar este modulo - import circular). Reexportados aqui pra quem ja usa
# aprendizado.* continuar funcionando igual.
normalizar_texto_intent = db.normalizar_texto_intent
LIMIAR_CONFIRMACOES_PADRAO_INTENT = db.LIMIAR_CONFIRMACOES_PADRAO_INTENT

# Confianca fixa devolvida quando um padrao aprendido resolve localmente -
# ele so chega aqui depois de LIMIAR_CONFIRMACOES_PADRAO_INTENT confirmacoes
# reais (da IA ou de uma correcao manual), entao a confianca e alta por
# definicao; nunca precisa_confirmacao nesse caminho.
CONFIANCA_PADRAO_INTENT = 0.95


def padrao_intent_confiavel(conn, texto: str) -> dict | None:
    """Devolve o padrao aprendido pra esse texto SE ja tiver confirmacoes
    suficientes (LIMIAR_CONFIRMACOES_PADRAO_INTENT) - None no caso mais
    comum (primeira vez, ou ainda nao confirmado o bastante), sinalizando
    pro chamador (app.py) cair pra API."""
    normalizado = normalizar_texto_intent(texto)
    if not normalizado:
        return None
    padrao = db.buscar_padrao_intent(conn, normalizado)
    if not padrao or padrao["vezes_confirmado"] < LIMIAR_CONFIRMACOES_PADRAO_INTENT:
        return None
    return padrao


def confirmar_padrao_intent(
    conn, texto: str, acao: str, parametros: dict, forcar_confianca_alta: bool = False
) -> None:
    """Registra silenciosamente que esse texto (normalizado) resultou nessa
    acao - repetir o mesmo par (texto, acao) LIMIAR_CONFIRMACOES_PADRAO_INTENT
    vezes destrava o atalho local (padrao_intent_confiavel). Uma acao
    diferente da ja registrada reinicia a contagem (autocorretivo: nao fica
    preso reforcando um padrao que mudou). `forcar_confianca_alta` pula
    direto pro limiar - usado pela correcao manual (US-A4): o Alex corrigindo
    uma vez ja deve valer como sinal forte, sem exigir repetir o erro
    LIMIAR_CONFIRMACOES_PADRAO_INTENT vezes."""
    normalizado = normalizar_texto_intent(texto)
    if not normalizado:
        return
    existente = db.buscar_padrao_intent(conn, normalizado)
    if forcar_confianca_alta:
        vezes = LIMIAR_CONFIRMACOES_PADRAO_INTENT
    elif existente and existente["acao"] == acao:
        vezes = existente["vezes_confirmado"] + 1
    else:
        vezes = 1
    db.upsert_padrao_intent(conn, normalizado, acao, parametros, vezes)


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
