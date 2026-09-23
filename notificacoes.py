"""Verificacoes proativas - cada funcao decide sozinha, em Python puro (sem
IA), se ha algo notavel o bastante pra mandar uma notificacao push. A
orquestracao (deduplicar por dia, mandar o push, marcar como enviado) fica
em app.py."""

from datetime import date, datetime, timedelta

import db
import gastos
import vida


def dentro_do_horario_silencioso(agora: datetime, inicio: str, fim: str) -> bool:
    """Janela de horario em que os avisos "soft" (nao urgentes) ficam
    represados em vez de tocar o celular - respeita o timing de quem esta do
    outro lado em vez de cutucar em qualquer hora so porque a condicao ficou
    verdadeira. 'inicio'/'fim' no formato 'HH:MM'; lida com a janela cruzando
    a meia-noite (ex: 22:00-07:00). inicio == fim desativa (nunca silencioso)."""
    if inicio == fim:
        return False
    hora_atual = agora.strftime("%H:%M")
    if inicio < fim:
        return inicio <= hora_atual < fim
    return hora_atual >= inicio or hora_atual < fim


def tarefas_aguardando_bom_tempo(conn) -> list[dict]:
    """Tarefas pendentes marcadas como 'depende do tempo' (ex: 'limpar o
    quarto se nao chover') - so identifica QUAIS tarefas checar; buscar a
    previsao de verdade (que pede rede) e decidir se ja tem um dia bom fica
    em app.py, pra esta funcao continuar pura e testavel so com SQLite."""
    rows = conn.execute(
        "SELECT id, title FROM tasks WHERE completed_at IS NULL AND depende_do_tempo = 1 "
        "AND recorrencia IS NULL"
    ).fetchall()
    return [dict(r) for r in rows]


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


def tarefas_paradas(conn, dias_minimo: int = 3, hoje: date | None = None) -> list[tuple[int, str]]:
    """Cobranca por tarefa (nao so a contagem generica de tarefas_atrasadas): uma
    tarefa parada ha `dias_minimo` dias ou mais vira um check-in pelo nome, uma vez
    so (a deduplicacao fica em app.py via ja_notificado_alguma_vez, nao
    ja_notificou_hoje - senao voltaria a cobrar todo santo dia enquanto continuar
    atrasada, o que vira ruido em vez de ajuda)."""
    hoje = hoje or date.today()
    limite = (hoje - timedelta(days=dias_minimo)).isoformat()
    rows = conn.execute(
        """SELECT id, title, due_date FROM tasks
           WHERE completed_at IS NULL AND due_date IS NOT NULL AND due_date <= ?""",
        (limite,),
    ).fetchall()
    avisos = []
    for r in rows:
        dias = (hoje - date.fromisoformat(r["due_date"])).days
        avisos.append(
            (r["id"], f"\"{r['title']}\" esta parada ha {dias} dias. Ainda precisa fazer isso?")
        )
    return avisos


def esperas_paradas(conn, dias_minimo: int = 5, hoje: date | None = None) -> list[tuple[int, str]]:
    """Cobranca de resposta pendente de TERCEIROS (fornecedor, corretora,
    quem for) - diferente de tarefas_paradas, que cobra voce mesmo de volta,
    essa acompanha quem ainda nao te respondeu. Mesma logica de disparo unico
    (ver ja_notificado_alguma_vez em app.py): nao vale cobrar todo dia
    enquanto a espera continuar em aberto."""
    hoje = hoje or date.today()
    avisos = []
    rows = conn.execute(
        "SELECT id, quem, sobre, criado_em FROM esperas WHERE resolvido_em IS NULL"
    ).fetchall()
    for r in rows:
        criado = datetime.fromisoformat(r["criado_em"]).date()
        dias = (hoje - criado).days
        if dias < dias_minimo:
            continue
        avisos.append(
            (
                r["id"],
                f"Ainda esperando resposta de {r['quem']} sobre \"{r['sobre']}\" - ja fazem {dias} dias.",
            )
        )
    return avisos


def tarefas_com_horario_chegando(
    conn, agora: datetime | None = None, antecedencia_minutos: int = 10
) -> list[tuple[int, str]]:
    """Tarefas pendentes com horario marcado pra hoje que estao chegando -
    pedido explicito do Alex (TDAH): avisar ANTES ("daqui 10 minutos voce tem
    que fazer tal coisa, ja va se arrumando"), nao so bem na hora, pra dar
    tempo de reagir em vez de so registrar que passou. A janela cobre de
    `antecedencia_minutos` antes ate a propria hora (inclusive) - quem ja
    passou do horario (ex: scheduler ficou fora do ar um tempo) ainda cai
    aqui com a mensagem "na hora", nunca fica sem aviso nenhum so porque o
    tick certo de heads-up foi perdido. A deduplicacao (uma vez por tarefa
    por dia, em app.py) garante que so um dos dois formatos de mensagem sai,
    mesmo com varios ticks do scheduler caindo dentro da janela."""
    agora = agora or datetime.now()
    hoje = agora.date().isoformat()
    hora_atual = agora.strftime("%H:%M")
    limite_futuro = (agora + timedelta(minutes=antecedencia_minutos)).strftime("%H:%M")
    rows = conn.execute(
        """SELECT id, title, hora FROM tasks
           WHERE completed_at IS NULL AND due_date = ? AND hora IS NOT NULL AND hora <= ?""",
        (hoje, limite_futuro),
    ).fetchall()
    avisos = []
    for r in rows:
        if r["hora"] > hora_atual:
            avisos.append(
                (r["id"], f"Daqui a pouco: \"{r['title']}\" as {r['hora']} - ja va se preparando.")
            )
        else:
            avisos.append((r["id"], f"\"{r['title']}\" - {r['hora']}."))
    return avisos


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


def orcamentos_perto_ou_estourados(conn, hoje: date | None = None) -> list[tuple[str, str, str]]:
    """Pra cada categoria com orcamento definido (`orcamentos`), compara o
    gasto REAL do mes atual com o limite - devolve (categoria, nivel,
    mensagem) pra cada categoria que bateu 90% ("quase") ou 100%+
    ("estourado") do limite agora. So gastos ja acontecidos contam (mesma
    regra de _total_gasto_entre - gasto planejado nao deveria disparar
    alerta de orcamento, pode nem vir a acontecer). A deduplicacao
    (uma vez por categoria+mes+nivel) fica em app.py."""
    hoje = hoje or date.today()
    ano_mes = hoje.strftime("%Y-%m")
    avisos = []
    for orc in conn.execute("SELECT categoria, valor_limite FROM orcamentos").fetchall():
        categoria = orc["categoria"]
        limite = orc["valor_limite"]
        if limite <= 0:
            continue
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses "
            "WHERE category = ? AND tipo = 'real' AND strftime('%Y-%m', created_at) = ?",
            (categoria, ano_mes),
        ).fetchone()
        gasto = row["total"]
        if gasto <= 0:
            continue
        fracao = gasto / limite
        if fracao >= 1:
            avisos.append((
                categoria,
                "estourado",
                f"Voce ja passou do orcamento de {categoria} esse mes: "
                f"R$ {gasto:.2f} de um limite de R$ {limite:.2f}.",
            ))
        elif fracao >= 0.9:
            avisos.append((
                categoria,
                "quase",
                f"Voce ja gastou R$ {gasto:.2f} em {categoria} esse mes - "
                f"perto do limite de R$ {limite:.2f}.",
            ))
    return avisos


def cobrancas_genericas_sem_rotulo(conn) -> list[tuple[str, float, str]]:
    """Acha cobrancas com padrao generico (ex: "apple.com/bill") - tanto no
    que foi digitado no chat quanto no extrato bancario sincronizado - que
    ainda nao tem apelido definido (apelidos_gasto), candidatas a perguntar
    pro Alex o que cada uma e (zero custo de IA - so reconhecimento de
    texto). Devolve (descricao_normalizada, valor, mensagem) unicos - mesma
    descricao+valor nao repete, mesmo aparecendo varias vezes no
    historico."""
    ja_com_apelido = {
        (a["descricao_normalizada"], a["valor"])
        for a in conn.execute("SELECT descricao_normalizada, valor FROM apelidos_gasto").fetchall()
    }

    candidatos: dict[tuple[str, float], str] = {}

    rows_expenses = conn.execute(
        "SELECT amount AS valor, description, source_text FROM expenses WHERE tipo = 'real'"
    ).fetchall()
    for r in rows_expenses:
        descricao = (r["description"] or r["source_text"] or "").strip()
        if gastos.e_cobranca_generica(descricao):
            chave = (descricao.lower(), r["valor"])
            if chave not in ja_com_apelido:
                candidatos[chave] = descricao

    # valor/descricao sao criptografados em repouso - db.list_all_bank_transactions
    # ja descriptografa; o filtro "valor < 0" (antes no SQL) fica em Python.
    for r in db.list_all_bank_transactions(conn):
        if r["valor"] is None or r["valor"] >= 0:
            continue
        valor = -r["valor"]
        descricao = (r["descricao"] or "").strip()
        if gastos.e_cobranca_generica(descricao):
            chave = (descricao.lower(), valor)
            if chave not in ja_com_apelido:
                candidatos[chave] = descricao

    avisos = []
    for (descricao_norm, valor), descricao_original in candidatos.items():
        avisos.append((
            descricao_norm,
            valor,
            f"Cobranca de R$ {valor:.2f} em \"{descricao_original}\" - qual assinatura e essa?",
        ))
    return avisos


def _gastos_reais_unificados_para_deteccao(conn) -> list[dict]:
    """Mesma unificacao de expenses (digitado no chat) + bank_transactions
    (extrato sincronizado) que app.py._gastos_reais_unificados ja usa pra
    detectar_gastos_recorrentes - reaproveitada aqui pra nao ter dois
    conceitos diferentes de "todo gasto real" no projeto. Fica em
    notificacoes.py (nao importa de app.py, que importa notificacoes - ver
    de fato o mesmo formato de dict que gastos.py espera)."""
    expenses_reais = conn.execute(
        "SELECT amount, category, description, source_text, created_at FROM expenses WHERE tipo = 'real'"
    ).fetchall()
    unificado = [dict(r) for r in expenses_reais]
    for r in db.list_all_bank_transactions(conn):
        if r["valor"] is None or r["valor"] >= 0:
            continue
        unificado.append(
            {
                "amount": -r["valor"],
                "category": r["categoria"] or "outros",
                "description": r["descricao"],
                "source_text": None,
                "created_at": r["data"],
            }
        )
    apelidos = {(a["descricao_normalizada"], a["valor"]): a["apelido"] for a in db.list_apelidos_gasto(conn)}
    return gastos.aplicar_apelidos(unificado, apelidos)


def assinaturas_aumento_preco(conn, hoje: date | None = None) -> list[tuple[str, float, str]]:
    """Reaproveita gastos.detectar_aumento_assinatura (que por sua vez
    reaproveita o mesmo agrupamento de detectar_gastos_recorrentes, ja usado
    na aba Gastos pra achar assinaturas fixas) - so acrescenta o aviso
    quando uma assinatura ja conhecida vier com o valor mais recente bem
    acima do que sempre foi. Devolve (descricao_normalizada, valor_novo,
    mensagem) - mesma forma de cobrancas_genericas_sem_rotulo, pra app.py
    deduplicar por descricao+valor (um aumento novo, com valor diferente do
    ultimo aviso, vira um aviso novo sozinho se a assinatura subir de novo)."""
    hoje = hoje or date.today()
    unificado = _gastos_reais_unificados_para_deteccao(conn)

    avisos = []
    for a in gastos.detectar_aumento_assinatura(unificado, hoje):
        msg = (
            f"\"{a['descricao']}\" ficou mais cara: de R$ {a['valor_anterior_medio']:.2f} pra "
            f"R$ {a['valor_novo']:.2f} ({a['aumento_pct']:.0f}% a mais)."
        )
        avisos.append((a["descricao"].strip().lower(), a["valor_novo"], msg))
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


_DIA_SEMANA_COM_ARTIGO = {
    0: "numa segunda-feira",
    1: "numa terca-feira",
    2: "numa quarta-feira",
    3: "numa quinta-feira",
    4: "numa sexta-feira",
    5: "num sabado",
    6: "num domingo",
}


def gasto_dia_semana_atipico(
    conn, hoje: date | None = None, semanas: int = 4, limiar: float = 1.6
) -> str | None:
    """Pega um padrao que o total da semana (gasto_semana_elevado) esconde:
    uma semana pode fechar dentro da media e ainda assim ter um dia
    especifico bem fora do normal - ex: sexta sempre foi baixa e hoje veio
    3x mais alta, mesmo que o resto da semana compense. Compara o gasto de
    hoje com a media do MESMO dia da semana nas ultimas `semanas`
    ocorrencias (nao com a semana inteira)."""
    hoje = hoje or date.today()
    total_hoje = _total_gasto_entre(conn, hoje, hoje)
    if total_hoje <= 0:
        return None

    amostras = []
    for i in range(1, semanas + 1):
        dia = hoje - timedelta(days=7 * i)
        total_dia = _total_gasto_entre(conn, dia, dia)
        if total_dia > 0:
            amostras.append(total_dia)
    if len(amostras) < 2:
        return None  # historico curto demais desse dia da semana pra comparar direito

    media = sum(amostras) / len(amostras)
    if media <= 0 or total_hoje < limiar * media:
        return None

    dia_semana = _DIA_SEMANA_COM_ARTIGO[hoje.weekday()]
    return (
        f"Gasto de hoje (R$ {total_hoje:.2f}) esta bem acima do que costuma ser "
        f"{dia_semana} (media de R$ {media:.2f})."
    )


def proxima_ocorrencia_lembrete(data_base: date, recorrente: bool, hoje: date) -> date:
    """Pra lembrete unico, a proxima ocorrencia e a propria data. Pra
    recorrente (anual - tipo validade de licenca, exame medico, seguro),
    acha o proximo aniversario dessa data a partir de hoje. Publica (nao so
    interna) porque /api/lembretes tambem usa pra mostrar a proxima data +
    dias restantes na tela, nao so lembretes_proximos aqui embaixo."""
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
        proxima = proxima_ocorrencia_lembrete(data_base, bool(row["recorrente"]), hoje)
        dias_restantes = (proxima - hoje).days
        if not (0 <= dias_restantes <= dias):
            continue
        if dias_restantes == 0:
            quando = "e hoje"
        elif dias_restantes == 1:
            quando = "e amanha"
        else:
            quando = f"e em {dias_restantes} dias"
        msg = f"\"{row['titulo']}\" {quando} ({proxima.strftime('%d/%m')})."
        sugestao = vida.sugestao_acao_data(row["titulo"])
        if sugestao:
            msg = f"{msg} {sugestao}"
        avisos.append((row["id"], msg))
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


def hora_de_dormir_devida(agora: datetime | None = None) -> bool:
    """Verdadeiro na janela de 5min em torno das 22h - o horario que o Alex
    escolheu pra comecar a desacelerar pro sono, todo dia."""
    agora = agora or datetime.now()
    alvo = agora.replace(hour=22, minute=0, second=0, microsecond=0)
    return alvo <= agora < alvo + timedelta(minutes=5)


def fechamento_noturno_devido(agora: datetime | None = None) -> bool:
    """Verdadeiro na janela de 5min em torno das 21h - fecha o dia de forma
    ATIVA (manda push sozinho) em vez de esperar o Alex abrir a aba Painel
    pra ver o fechamento. Uma hora antes da hora_de_dormir de proposito, pra
    nao empilhar dois avisos no mesmo minuto."""
    agora = agora or datetime.now()
    alvo = agora.replace(hour=21, minute=0, second=0, microsecond=0)
    return alvo <= agora < alvo + timedelta(minutes=5)


def _total_gasto_dia(conn, dia: date) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE date(created_at) = ? AND tipo = 'real'",
        (dia.isoformat(),),
    ).fetchone()
    return row["total"]


def mensagem_fechamento_noturno(conn, hoje: date | None = None) -> str:
    """Monta o texto do fechamento ativo - deterministico, sem IA (roda
    sozinho todo dia, nao vale gastar chamada de IA nisso). O mesmo par
    concluidas/pendentes que a aba Painel ja mostra, mais o gasto do dia,
    resumido numa mensagem so."""
    hoje = hoje or date.today()
    concluidas = conn.execute(
        "SELECT COUNT(*) AS n FROM tasks WHERE date(completed_at) = ?", (hoje.isoformat(),)
    ).fetchone()["n"]
    pendentes = conn.execute(
        "SELECT title FROM tasks WHERE completed_at IS NULL AND due_date = ? "
        "ORDER BY hora IS NULL, hora",
        (hoje.isoformat(),),
    ).fetchall()
    gasto = _total_gasto_dia(conn, hoje)

    partes = []
    if concluidas == 0:
        partes.append("Nenhuma tarefa concluida hoje.")
    elif concluidas == 1:
        partes.append("1 tarefa concluida hoje.")
    else:
        partes.append(f"{concluidas} tarefas concluidas hoje.")

    if pendentes:
        titulos = ", ".join(r["title"] for r in pendentes)
        partes.append(f"Ficou pendente: {titulos}.")

    if gasto > 0:
        partes.append(f"Gasto do dia: R$ {gasto:.2f}.")

    return " ".join(partes)


def currency_voo_baixa(conn, limiar_dias: int = 21) -> str | None:
    """Faz tempo demais desde o ultimo voo REALIZADO (com horas registradas -
    um voo so agendado nao conta) - um lembrete gentil pra nao perder o
    ritmo do curso. None se nunca voou ainda ou se ainda esta dentro do
    limiar."""
    hoje = date.today()
    ultima = conn.execute(
        "SELECT MAX(data) AS ultima FROM voos WHERE horas IS NOT NULL AND data <= ?",
        (hoje.isoformat(),),
    ).fetchone()["ultima"]
    if not ultima:
        return None
    dias = (hoje - date.fromisoformat(ultima)).days
    if dias < limiar_dias:
        return None
    return f"Faz {dias} dias que voce nao voa - pode ser hora de marcar um voo pra nao perder o ritmo."


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
