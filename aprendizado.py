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
from datetime import date, timedelta

import db
from diario import utc_para_local

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


def media_e_desvio_padrao(amostras: list[float]) -> tuple[float, float]:
    """Media e desvio-padrao populacional simples (sem libs externas - a
    amostra aqui e sempre pequena, uso pessoal). Usado pelo alerta de gasto
    fora do padrao dentro da categoria (Fase 5, US-C17) - desvio 0.0 quando
    houver menos de 2 amostras, ja que desvio-padrao nao faz sentido com 0/1
    ponto."""
    if not amostras:
        return 0.0, 0.0
    media = sum(amostras) / len(amostras)
    if len(amostras) < 2:
        return media, 0.0
    variancia = sum((v - media) ** 2 for v in amostras) / len(amostras)
    return media, variancia ** 0.5


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
            "motivo": f"histórico insuficiente (precisa de pelo menos {minimo_amostras})",
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
        # 08/11: completed_at e UTC - feita depois das 21h contava 1 dia de atraso
        concluida_dt = utc_para_local(r["completed_at"])
        if concluida_dt is None:
            continue
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
        criada_dt = utc_para_local(r["criado_em"])  # as duas colunas sao datetime('now') = UTC
        resolvida_dt = utc_para_local(r["resolvido_em"])
        if criada_dt is None or resolvida_dt is None:
            continue
        dias = (resolvida_dt.date() - criada_dt.date()).days
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
        concluida = utc_para_local(r["completed_at"])
        if concluida and concluida.date() <= devido:
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
            concluida = utc_para_local(t["completed_at"])
            if concluida and concluida.date() == dia:
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
    # com o Alex e sempre "tu" (leva 08/11): teu humor, tua energia
    possessivo = {"humor": "teu", "energia": "tua"}
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
        dono = possessivo[campo]
        if alto == baixo:
            partes.append(f"{dono} {campo} fica melhor depois de {melhor} de sono do que depois de {pior}")
        else:
            partes.append(
                f"{dono} {campo} fica mais pra '{alto}' depois de {melhor} de sono e mais pra '{baixo}' depois de {pior}"
            )
    if not partes:
        return None
    return "Pelo teu check-in, " + "; ".join(partes) + "."


# ---- Banco "pergunta -> onde buscar" (Fase 6, US-E7) -----------------------
# Segunda camada local do classificador de intent (depois do padrao aprendido
# por repeticao, antes da IA): consultas de formato conhecido ("me mostra o
# projeto da viagem e a meta", "como foram meus treinos nos ultimos 7 dias?",
# "como encaixo meu treino hoje?") e o registro trivial de agua ("tomei um
# copo de agua") resolvem SEM chamar API nenhuma. Quem chama isto e SO
# app._classificar_intent (fonte unica da classificacao) - nunca chamar
# direto de uma rota. O banco cresce sozinho: quando a IA do chat responde
# uma pergunta usando so ferramentas de consulta, app.py grava o par
# (texto -> fontes) via confirmar_padrao_intent (padroes_intent_aprendidos) e,
# depois de LIMIAR_CONFIRMACOES_PADRAO_INTENT vezes, aquela frase exata
# tambem passa a resolver local, mesmo que nenhuma regra abaixo a reconheca.
#
# Formato devolvido (mesmo contrato de docs/INTENT.md):
#   {"acao": "consultar", "parametros": {"fontes": [{"fonte": "projeto", "termo": "viagem"},
#                                                    {"fonte": "meta"}]}}
#   {"acao": "registrar_checkin", "parametros": {"campo": "hidratacao"}}
# Fontes conhecidas: FONTES_CONSULTA.

FONTES_CONSULTA = ("projeto", "meta", "treinos", "habitos", "saude_dia", "sugestao")

# So e consulta se COMECA com um jeito de perguntar/pedir pra ver, ou termina
# com "?" - "quero uma meta de 5 mil" nunca vira consulta de meta.
_GATILHO_CONSULTA = re.compile(
    r"^(?:(?:me |pode me |quero |queria |preciso )?(?:mostra|mostre|mostrar|ver|ve|veja|abre|abrir|lista|listar)\b"
    r"|como\b|qual\b|quais\b|quanto|quanta|cade\b|onde (?:ta|esta)\b|resumo\b|status\b)"
    r"|\?$"
)
# Qualquer verbo de criar/mudar dado derruba o caminho local (a mensagem e
# uma acao, ou mistura acao + pergunta - a IA decide).
_VERBO_ACAO = re.compile(
    r"\b(cria|criar|crie|adiciona|adicionar|adicione|registra|registrar|registre|anota|anotar|anote|"
    r"novo|nova|marca|marcar|marque|conclui|concluir|terminei|apaga|apagar|deleta|deletar|remove|remover|"
    r"gastei|paguei|comprei|recebi|entrou|lembra|lembrar|agenda|agendar|muda|mudar|troca|trocar)\b"
)
# Assunto que o banco local NAO cobre - se aparecer junto, a pergunta e
# maior do que as fontes conhecidas e a IA responde (nunca responder so
# metade da pergunta).
_FORA_DO_BANCO = re.compile(
    r"\b(gast\w*|pag\w*|saldo|dinheiro|conta|contas|fatura|cartao|sobr\w*|orcamento|reais|r\$|"
    r"tarefas?|lembretes?|voos?|remedios?|compras?|notas?|noticias?|clima|tempo|construtora|banco|"
    r"email|e-mail|uber|cotac\w*|plano|carro|moto|lav\w+|jogar|joga|molh\w*|chuv\w*|chov\w*|date|"
    # 08/11 (leva "conversa inteira"): trajeto, lugar, horario de funcionamento, clima e preco. "que horas vou
    # chegar em casa?" virava o card de horario livre; "onde fica a academia?"/"quanto custa a academia?" o
    # card de treinos. Nada disso o banco local responde.
    r"cheg\w*|sai|sair|saio|saida|saindo|volt\w*|busc\w*|pegar|pego|levar|levo|deixar|deixo|trajeto|rota|"
    r"caminho|km|distancia|longe|perto|transito|estrada|demor\w*|abert[oa]|abre|"
    r"funciona\w*|onde fica|onde e|endereco|mapa|localiza\w*|aeroporto|aeroclube|voar|viajar|frio|calor|"
    r"graus|temperatura|previsao|vento|umidade|cust\w*|preco|precos|mensalidade)\b"
)
# 08/11 (3a rodada): atraso/fechar sao de trajeto/lugar ("vou chegar atrasado?", "a academia fecha que horas?"),
# mas "to atrasado nos habitos?" e "quanto falta pra fechar a meta?" sao do banco local: com habito/treino/meta
# na frase essas palavras nao derrubam o atalho (academia e lugar, nao conta como contexto).
_FORA_SEM_CONTEXTO = re.compile(r"\b(atras\w*|fecha\w*)\b")
_RE_CONTEXTO_LOCAL = re.compile(r"\b(habitos?|treinos?|treinei|metas?)\b")
_ATRASO_FECHO_DE_ESTADO = re.compile(r"^(?:atrasad[oa]s?|atrasos?|fechar|fechei|fechou|fechad[oa]s?)$")
# melhor/pior/preciso com contexto local so sao consulta quando falam DO DELE ("qual foi meu melhor treino?",
# "qual habito ta pior?", "preciso ver meus habitos"); "qual o melhor treino pra perder peso?" e conselho (IA)
_RE_DO_DELE = re.compile(r"\b(meu|minha|meus|minhas|foi|foram|ta|tao|esta|estao|to|tou|estou)\b")
_RE_MELHOR_PIOR = re.compile(r"\b(?:melhor|pior)\b")
_RE_PRECISO = re.compile(r"\bprecis\w*")
_RE_PRECISO_VER = re.compile(r"\bprecis\w* (?:ver|olhar|conferir|saber)\b")
_RE_PROJETO = re.compile(r"\bprojetos?\b")
_RE_PROJETO_TERMO = re.compile(r"\bprojetos? (?:(?:d[aeo]s?|de|pra|para) )?([a-z0-9][a-z0-9 ]*?)(?: e | com |,|\?|$)")
_RE_VIAGEM = re.compile(r"\bviage(?:m|ns)\b")
_RE_META = re.compile(r"\bmetas?\b")
_RE_TREINO = re.compile(r"\b(treinos?|treinei|treinando|academia|exercicios?)\b")
_RE_HABITO = re.compile(r"\bhabitos?\b")
# "agua" so e saude quando e a que ele BEBE (copos, bebi, hidratacao...). "jogar uma agua no carro" nao e
# (07/11: o chat respondia o card "Sua saude hoje" a uma duvida sobre lavar o carro).
_RE_SAUDE = re.compile(
    r"\b(hidratacao|saude)\b"
    r"|\bagua\b.*\b(copos?|bebi|bebido|beber|bebendo|tomei|tomar)\b"
    r"|\b(copos?|bebi|bebido|beber|bebendo|tomei|tomar|quanta|quantos|quanto)\b.*\bagua\b"
)
_RE_DIAS = re.compile(r"\bultim[oa]s? (\d{1,3}) dias?\b")
# Card de horario livre (sugerir_horario_livre) so pra pergunta de ENCAIXAR uma atividade dele sem hora.
# 08/11: o padrao antigo pegava "como|quando|que horas" + "vou|faco|posso" + qualquer coisa - "que horas vou
# chegar em casa?", "quando vou buscar a menina?", "como faco pra estudar meteorologia?" viravam um horario
# livre que ninguem pediu. Agora sao quatro formas, e o que sobra de titulo passa pelo _RE_SUG_NAO.
_ARTIGOS_SUG = r"(?: (?:o|a|os|as|meu|minha|meus|minhas|um|uma))*"
_FIM_SUG = r"(?: hoje| agora| ainda hoje)?\??$"
_RE_SUG_ENCAIXE = re.compile(  # "como encaixo meu treino hoje?", "quando da pra encaixar a corrida?"
    r"^(?:como|quando|que horas|a que horas) (?:eu )?(?:(?:posso|consigo|da pra) )?(?:encaixo|encaixar|encaixa)"
    + _ARTIGOS_SUG + r" ([a-z][a-z ]{1,38}?)" + _FIM_SUG
)
_RE_SUG_QUANDO = re.compile(  # "quando consigo estudar hoje?", "que horas faco o treino?"
    r"^(?:quando|que horas|a que horas) (?:eu )?(?:faco|fazer|(?:posso|consigo|da pra)(?: fazer)?)"
    + _ARTIGOS_SUG + r" ([a-z][a-z ]{1,38}?)" + _FIM_SUG
)
# "que horas eu vou pra academia hoje?": com "vou", so atividade sem hora fixa (o resto e plano/trajeto: IA)
_ATIVIDADES_SEM_HORA = (
    r"(?:academia|treino|treinar|malhar|musculacao|estudar|estudo|correr|corrida|caminhar|caminhada|pedalar|"
    r"bike|nadar|natacao|ler|leitura|meditar|alongar|alongamento|yoga|pilates|crossfit|funcional|esteira|"
    r"cardio|simulador)"
)
_RE_SUG_VOU = re.compile(
    r"^(?:quando|que horas|a que horas) (?:eu )?vou(?: (?:pra|para|na|no|a|o|fazer|meu|minha))* ("
    + _ATIVIDADES_SEM_HORA + r"(?: (?:de )?[a-z]+){0,3}?)" + _FIM_SUG
)
_RE_SUG_HORARIO = re.compile(  # "qual o melhor horario pra estudar?"
    r"^(?:qual|que) (?:e )?(?:o )?(?:melhor )?horario (?:pra|para) (?:eu )?(?:(?:fazer|encaixar) )?"
    r"(?:(?:o|a|meu|minha|na|no) )*([a-z][a-z ]{1,38}?)" + _FIM_SUG
)
_RES_SUGESTAO = (_RE_SUG_ENCAIXE, _RE_SUG_QUANDO, _RE_SUG_VOU, _RE_SUG_HORARIO)
# 08/11 (3a rodada): "que horas vou treinar amanha?" virava horario livre de HOJE (o titulo engolia o dia). O
# plano local (app._plano_local_chat) so manda titulo+duracao pro sugerir_horario_livre, sem dia: com dia que
# nao e hoje, a IA responde.
_RE_SUG_OUTRO_DIA = re.compile(
    r"\b(?:amanha|depois de amanha|ontem|segunda|terca|quarta|quinta|sexta|sabado|domingo|dia \d{1,2}|"
    r"semana que vem|proxima semana|fim de semana|final de semana|mes que vem)\b"
)
# titulo que nao e atividade dele sem hora: ir a um lugar, gente, comida, dormir/acordar, se arrumar
_RE_SUG_NAO = re.compile(
    r"\b(?:ir|vou|casa|com|ver|visitar|encontrar|ligar|falar|cobrar|mandar|responder|almocar|almoco|jantar|"
    r"janta|comer|lanchar|lanche|cafe|dormir|deitar|acordar|levantar|banho|se arrumar|me arrumar|trabalho|trabalhar|obra|"
    r"escritorio|shopping|mercado|farmacia|centro)\b"
)
_RE_IR_PRA_ATIVIDADE = re.compile(r"^ir (?:pra|para|pro|na|no|a|ao) (" + _ATIVIDADES_SEM_HORA + r"\b.*)$")
# Pergunta que o banco local NAO responde mesmo citando treino/meta/projeto/habito/saude (08/11):
# - futuro/horario de compromisso ("que horas e o treino?", "quando e a viagem?", "vai ser");
# - conselho/decisao/porque ("devo beber mais agua?", "vale a pena ir na academia?", "por que meus treinos...").
# _RE_QUAL_TREINO: qual treino fazer agora ("hoje e qual treino?" = comecar_treino, nao o historico).
_RE_PERGUNTA_FORA = re.compile(
    r"\bvai (?:ser|ficar|estar|dar|ter|rolar)\b|\bamanha\b|\bsemana que vem\b|\bproxim[oa]s?\b|\bque dia\b"
    r"|\bque horas?\b|\bhorarios?\b|\bquando (?:e|eh|vai|vou|tenho|sera|comeca)\b"
    r"|\b(?:devo|deveria|vale|compensa|sera que|faz (?:mal|bem)|e (?:bom|ruim)|tenho que"
    r"|por ?que|pq|pra que|para que|acha|dicas?|conselho)\b|^e se\b|\bse eu\b"
)
_RE_QUAL_TREINO = re.compile(r"\b(?:qual|que)(?: (?:e|vai ser|sera))?(?: (?:o|a|meu|minha))? (?:treino|exercicio|ficha)\b")
_RE_PASSADO_TREINO = re.compile(r"\b(?:foi|foram|fiz|fizeram|ultim\w*|passad\w*|treinei)\b")
# "como" so e consulta de estado ("como estao meus habitos?", "como foi o treino?"); "como manter um habito?",
# "como melhorar meu treino?" e "como faco o treino de peito?" sao pergunta de como fazer (IA).
_COMO_ESTADO_PROXIMA = frozenset(
    ("esta", "estao", "ta", "tao", "anda", "andam", "andou", "vai", "vao", "foi", "foram", "ficou", "ficaram",
     "to", "tou", "estou", "tem", "o", "a", "os", "as", "meu", "minha", "meus", "minhas")
)
_RE_COMO_ESTADO = re.compile(
    r"\b(?:esta|estao|ta|tao|anda|andam|andou|vai|vao|foi|foram|ficou|ficaram|to|tou|estou|tem ido)\b"
)
_RE_COMO_INICIO = re.compile(r"^(?:e |e ai,? |entao )?como (\w+)")
# meta de agua/proteina/passos/sono nao e a meta financeira que consultar_meta mostra
_RE_META_NAO_FINANCEIRA = re.compile(
    r"\bmetas? (?:de |da |do )?(?:agua|copos?|hidratacao|proteina|comida|calorias?|kcal|passos|sono|dormir|peso|"
    r"massa|leitura|ler|livros?|estudo|estudar|treinos?|academia|horas|corrida|km)\b"
)
_RE_AGUA = re.compile(
    r"^(?:tomei|bebi)(?: mais)?(?: (?:um|1|uma|meio))?(?: (?:copo|copinho|garrafa|garrafinha|caneca))?"
    r"(?: (?:d[e']|da))? ?agua(?: agora| hoje| ja)?[!.]*$"
)


def normalizar_consulta(texto: str) -> str:
    """Normalizacao mais agressiva que a do padrao aprendido (so pra casar
    regra): minusculo, sem acento, espacos colapsados."""
    import unicodedata

    if not isinstance(texto, str):
        return ""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", sem_acento).strip()


def _dias_da_consulta(t: str) -> int:
    m = _RE_DIAS.search(t)
    if m:
        return max(1, min(int(m.group(1)), 90))
    if re.search(r"\bmes\b", t):
        return 30
    if re.search(r"\bhoje\b", t):
        return 1
    return 7


def exige_ia(texto: str) -> bool:
    """True quando a frase tem verbo de acao (_VERBO_ACAO) ou assunto fora
    do banco local (_FORA_DO_BANCO) - o chat nunca responde isso so com
    consulta local, nem por padrao aprendido (revisao da Fase 6, ver
    app._plano_local_chat). Texto invalido/vazio -> False."""
    t = normalizar_consulta(texto)
    return bool(t) and bool(_VERBO_ACAO.search(t) or _fora_do_banco(t))


def _fora_do_banco(t: str) -> bool:
    """Assunto que o banco local nao cobre (_FORA_DO_BANCO). Atraso/fechar so ficam com o banco local quando ha
    habito/treino/meta na frase E a palavra e de estado ("atrasado", "fechar a meta") - "vou me atrasar pro
    treino?" continua trajeto (IA)."""
    if _FORA_DO_BANCO.search(t):
        return True
    palavras = [m.group(1) for m in _FORA_SEM_CONTEXTO.finditer(t)]
    if not palavras:
        return False
    return not (_RE_CONTEXTO_LOCAL.search(t) and all(_ATRASO_FECHO_DE_ESTADO.match(p) for p in palavras))


def _conselho_ou_comparacao(t: str) -> bool:
    """melhor/pior/preciso: conselho (IA), salvo quando e o estado DELE num habito/treino/meta."""
    do_dele = bool(_RE_CONTEXTO_LOCAL.search(t) and _RE_DO_DELE.search(t))
    if _RE_MELHOR_PIOR.search(t) and not do_dele:
        return True
    return bool(_RE_PRECISO.search(t) and not (do_dele and _RE_PRECISO_VER.search(t)))


def _consulta_de_estado(t: str) -> bool:
    """True quando a pergunta (ja normalizada) quer VER o estado de algo que o banco local mostra - nao como
    fazer, nao conselho, nao futuro/horario de compromisso, nao meta de saude (_RE_PERGUNTA_FORA e cia)."""
    como = _RE_COMO_INICIO.match(t)
    if como and (como.group(1) not in _COMO_ESTADO_PROXIMA or not _RE_COMO_ESTADO.search(t)):
        return False
    if _RE_PERGUNTA_FORA.search(t) or _RE_META_NAO_FINANCEIRA.search(t) or _conselho_ou_comparacao(t):
        return False
    # "hoje e qual treino?" e o treino de agora (comecar_treino); "qual foi meu ultimo treino?" e historico
    return not (_RE_QUAL_TREINO.search(t) and not _RE_PASSADO_TREINO.search(t))


def consulta_conhecida(texto: str) -> dict | None:
    """Regra do banco "pergunta -> onde buscar" que casa com o texto, ou
    None (cai pro proximo passo do classificador). Nunca levanta excecao."""
    t = normalizar_consulta(texto)
    if not t or len(t) > 160:
        return None

    if _RE_AGUA.match(t):
        return {"acao": "registrar_checkin", "parametros": {"campo": "hidratacao"}}

    if _VERBO_ACAO.search(t) or _fora_do_banco(t):
        return None

    for regra in _RES_SUGESTAO:
        sugestao = regra.match(t)
        if not sugestao:
            continue
        if _RE_SUG_OUTRO_DIA.search(t):
            return None  # horario livre de outro dia: o plano local so faz o de hoje
        titulo = (sugestao.group(1) or "").strip()
        ir_pra = _RE_IR_PRA_ATIVIDADE.match(titulo)  # "quando posso ir pra academia?" = encaixar a academia
        if ir_pra:
            titulo = ir_pra.group(1)
        if (titulo and not _RE_PROJETO.search(titulo) and not _RE_META.search(titulo)
                and not _RE_SUG_NAO.search(titulo)):
            return {"acao": "consultar", "parametros": {"fontes": [{"fonte": "sugestao", "titulo": titulo}]}}
        return None  # pergunta de horario que nao e encaixe de atividade: a IA responde

    if not _GATILHO_CONSULTA.search(t) or not _consulta_de_estado(t):
        return None

    fontes: list[dict] = []
    if _RE_PROJETO.search(t) or _RE_VIAGEM.search(t):
        m = _RE_PROJETO_TERMO.search(t)
        termo = m.group(1).strip() if m else ("viagem" if _RE_VIAGEM.search(t) else None)
        fonte = {"fonte": "projeto"}
        if termo and termo not in ("meu", "minha", "meus", "minhas", "o", "a", "os", "as"):
            fonte["termo"] = termo
        fontes.append(fonte)
    if _RE_META.search(t):
        fontes.append({"fonte": "meta"})
    if _RE_TREINO.search(t):
        fontes.append({"fonte": "treinos", "dias": _dias_da_consulta(t)})
    if _RE_HABITO.search(t):
        fontes.append({"fonte": "habitos"})
    if _RE_SAUDE.search(t) and not any(f["fonte"] == "treinos" for f in fontes):
        fontes.append({"fonte": "saude_dia"})
    if not fontes:
        return None
    return {"acao": "consultar", "parametros": {"fontes": fontes}}


def fontes_validas(parametros) -> list[dict]:
    """Filtra `parametros["fontes"]` (vindo do banco local OU de um padrao
    aprendido gravado antes) pra so fontes conhecidas - lista vazia = o
    padrao nao diz onde buscar (ex: gravado pela IA de voz com
    {"pergunta": ...}) e o chamador deve cair pra IA."""
    if not isinstance(parametros, dict) or not isinstance(parametros.get("fontes"), list):
        return []
    return [f for f in parametros["fontes"] if isinstance(f, dict) and f.get("fonte") in FONTES_CONSULTA][:6]
