"""Verificacoes proativas - cada funcao decide sozinha, em Python puro (sem
IA), se ha algo notavel o bastante pra mandar uma notificacao push. A
orquestracao (deduplicar por dia, mandar o push, marcar como enviado) fica
em app.py."""

import json
import re
import unicodedata
from datetime import date, datetime, timedelta

import aprendizado
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
        return "Você tem 1 tarefa atrasada."
    return f"Você tem {n} tarefas atrasadas."


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
                f"Ainda esperando resposta de {r['quem']} sobre \"{r['sobre']}\" - já fazem {dias} dias.",
            )
        )
    return avisos


# Avisos importantes que INSISTEM (2026-10-13, pedido do Alex: "avisa uma ou duas vezes so e
# se eu nao ver passa em branco"). Minutos depois do 1o envio em que cada repeticao sai, se ele
# nao tocou na notificacao (aberto_em) e o aviso ainda vale (tarefa nao concluida). O resto dos
# avisos continua indo uma vez so - insistir em tudo vira barulho.
INSISTENCIA = {
    "tarefa_horario": (10, 30),
    "compromisso_chegando": (5,),
    "se_arrumar": (10,),
    "hora_de_sair": (5,),
    "voo_sair": (5, 15),
    "conta_a_vencer": (180,),
    "conta_pessoal": (180,),
}
# tipos cujo ref_id e o id da tarefa: concluiu = para de insistir
INSISTENCIA_DE_TAREFA = {"tarefa_horario", "se_arrumar", "hora_de_sair"}


def repeticoes_devidas(pendentes: list[dict], agora: datetime) -> tuple[list[dict], list[dict]]:
    """(repetir_agora, encerrar) a partir das linhas abertas de avisos_insistentes. Puro.
    Encerra o que e de outro dia, de tipo que nao insiste mais ou que ja usou todas as
    repeticoes; repete o que chegou na hora da proxima."""
    repetir, encerrar = [], []
    hoje = agora.date().isoformat()
    for a in pendentes:
        passos = INSISTENCIA.get(a["tipo"])
        feitas = int(a.get("tentativas") or 1) - 1  # tentativas conta o 1o envio
        if not passos or a.get("data") != hoje or feitas >= len(passos):
            encerrar.append(a)
            continue
        try:
            enviado = datetime.fromisoformat(a["enviado_em"])
        except (TypeError, ValueError):
            encerrar.append(a)
            continue
        if agora >= enviado + timedelta(minutes=passos[feitas]):
            repetir.append(a)
    return repetir, encerrar


def texto_repeticao(tipo: str, titulo: str, corpo: str, repeticao: int) -> tuple[str, str]:
    """Repeticao `repeticao` (1, 2...) do aviso: mesmo assunto, tom um pouco mais direto na
    ultima. Sem cobranca nem drama (mesmo espirito de tarefas_horario_passou)."""
    ultima = repeticao >= len(INSISTENCIA.get(tipo, ()))
    prefixo = "Última chamada" if ultima else "De novo"
    return f"{prefixo} · {titulo}", corpo


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
                (r["id"], f"Daqui a pouco, às {r['hora']}: {r['title']}. Vai fechando o que tá fazendo.")
            )
        else:
            avisos.append((r["id"], f"{r['title']} - é agora ({r['hora']}). Toca aqui pra marcar quando fizer."))
    return avisos


# Compromisso de SAIR (date, festa...) - o Alex leva bem mais tempo pra se arrumar pra
# esses (pedido dele, 2026-10-11: "demoro 40 minutos pra me arrumar" pra date/festa).
_PALAVRAS_SAIR = re.compile(
    r"\b(date|encontro|jantar|janta|festa|festinha|balada|aniversario|niver|casamento|formatura|"
    r"show|churrasco|happy hour|boate|role|barzinho|bar|pub|sair com|saida com)\b"
)
_ARRUMAR = re.compile(r"\b(se arrumar|me arrumar|arrumar pra|banho e arrumar)\b")


def _sem_acento(texto: str) -> str:
    base = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in base if not unicodedata.combining(c))


def e_refeicao(titulo: str) -> bool:
    """Bloco de comida do planejar_dia ("Comer: almoco - arroz, feijao, frango")."""
    return _sem_acento(titulo).startswith("comer")


def e_compromisso_de_sair(titulo: str) -> bool:
    return not e_refeicao(titulo) and bool(_PALAVRAS_SAIR.search(_sem_acento(titulo)))


PARADA_MIN = 5  # parado na parada do caminho ("passo na casa do guri antes"), briefing 04/11
ADIANTAR_MAX_MIN = 60


def _min_valido(v) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else None


def caminho_com_parada(trajeto, folga: int, parada: str | None = None, ate_parada=None, parada_destino=None):
    """Minutos de casa ate o destino e o dado da parada (contrato do card de saida, briefing 04/11):
    (caminho_min, {"nome", "min_ate"} | None). Sem parada: o trajeto (ou a folga). Com parada:
    casa -> parada + 5 min parado + parada -> destino; cada perna sem resposta do Maps usa a folga."""
    parada = (parada or "").strip()
    if not parada:
        t = _min_valido(trajeto)
        return (t if t is not None else folga), None
    ate = _min_valido(ate_parada)
    ate = ate if ate is not None else folga
    resto = _min_valido(parada_destino)
    resto = resto if resto is not None else folga
    return ate + PARADA_MIN + resto, {"nome": parada[:60], "min_ate": ate}


def adiantar_min(extras_json) -> int:
    """Quanto a saida ja foi adiantada (previsao que piorou, tempo.previsao_que_piora). 0 sem nada."""
    try:
        e = json.loads(extras_json) if extras_json else {}
    except (TypeError, ValueError):
        return 0
    v = e.get("adiantar_min") if isinstance(e, dict) else None
    return v if isinstance(v, int) and not isinstance(v, bool) and 0 < v <= ADIANTAR_MAX_MIN else 0


def _coluna(r, nome: str):
    return r[nome] if nome in r.keys() else None


def plano_se_arrumar(
    conn, agora: datetime | None = None, minutos_arrumar: int = 40, trajeto_min=None, folga_sem_trajeto: int = 15,
    trajeto_parada=None,
) -> list[dict]:
    """Compromissos de sair de HOJE (pendentes, com hora, ainda nao comecados) com a conta
    de tras pra frente: evento - trajeto = saida; saida - tempo de se arrumar = comecar.
    `trajeto_min(local) -> int | None` vem de fora (rede) pra esta funcao continuar pura;
    sem local/sem resposta usa `folga_sem_trajeto` (Brusque e pequena). Se o Alex ja tem
    uma tarefa "se arrumar" marcada hoje, o aviso de se arrumar fica com ela (nao duplica).
    Parada no caminho (04/11): `trajeto_parada(parada, local) -> (casa->parada, parada->destino)`
    e a conta vira casa -> parada -> destino (caminho_com_parada). Saida adiantada pela previsao
    (extras.adiantar_min) entra aqui tambem, pra todos os avisos baterem."""
    agora = agora or datetime.now()
    hoje = agora.date().isoformat()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE due_date = ? AND hora IS NOT NULL",
        (hoje,),
    ).fetchall()
    ja_tem_arrumar = any(_ARRUMAR.search(_sem_acento(r["title"])) for r in rows)
    planos = []
    for r in rows:
        # date/balada (card proprio, 2026-10-14) sao saida mesmo sem a palavra no titulo
        if r["completed_at"] or not (e_compromisso_de_sair(r["title"]) or r["estilo"] in ("date", "balada")):
            continue
        try:
            evento = datetime.combine(agora.date(), datetime.strptime(r["hora"], "%H:%M").time())
        except ValueError:
            continue
        if evento <= agora:
            continue
        trajeto = None
        perto = (evento - agora) <= timedelta(hours=4)
        parada = (_coluna(r, "parada") or "").strip()
        ate = resto = None
        if parada:
            if trajeto_parada and perto:
                ate, resto = trajeto_parada(parada, r["local"])
        elif r["local"] and trajeto_min and perto:
            trajeto = trajeto_min(r["local"])
        caminho, info_parada = caminho_com_parada(trajeto, folga_sem_trajeto, parada, ate, resto)
        adiantado = adiantar_min(_coluna(r, "extras"))
        saida = evento - timedelta(minutes=caminho + adiantado)
        planos.append({
            "id": r["id"], "titulo": r["title"], "hora": r["hora"], "local": r["local"],
            "trajeto_min": trajeto if _min_valido(trajeto) is not None else None, "caminho_min": caminho,
            "evento": evento, "saida": saida, "comecar": saida - timedelta(minutes=minutos_arrumar),
            "minutos_arrumar": minutos_arrumar, "ja_tem_tarefa_arrumar": ja_tem_arrumar,
            "parada": info_parada, "adiantado_min": adiantado, "estilo": r["estilo"],
        })
    return planos


def avisos_se_arrumar(planos: list[dict], agora: datetime | None = None) -> list[tuple[str, int, str, str]]:
    """(tipo, id, titulo, corpo) - 'se_arrumar' ~na hora de comecar e 'hora_de_sair' ~na hora
    de sair. Tick de 5 min: dispara a partir de 4 min antes (nunca atrasa mais que o tick)."""
    agora = agora or datetime.now()
    margem = timedelta(minutes=4)
    avisos = []
    for p in planos:
        nome, hora = p["titulo"], p["hora"]
        sai = p["saida"].strftime("%H:%M")
        if not p["ja_tem_tarefa_arrumar"] and p["comecar"] - margem <= agora < p["saida"]:
            atrasado = agora > p["comecar"] + timedelta(minutes=10)
            corpo = (
                f"{nome} às {hora}. "
                + ("Já passou da hora de começar - " if atrasado else "Começa agora: ")
                + f"{p['minutos_arrumar']} min pra ficar pronto e sair às {sai}."
            )
            avisos.append(("se_arrumar", p["id"], "Hora de se arrumar", corpo))
        if p["saida"] - margem <= agora < p["evento"]:
            if p.get("parada"):
                # briefing 04/11: "Hora de sair. 10 min até a casa do guri."
                corpo = f"{p['parada']['min_ate']} min até {p['parada']['nome']}. Depois {nome} às {hora}."
            elif p["trajeto_min"] is not None:
                corpo = f"{nome} às {hora} - {p['trajeto_min']} min até lá. Saindo agora você chega na hora."
            else:
                corpo = f"{nome} às {hora} - hora de ir saindo pra chegar com folga."
            avisos.append(("hora_de_sair", p["id"], "Hora de sair", corpo))
    return avisos


def tarefas_preparo(
    conn, agora: datetime | None = None, de_min: int = 15, ate_min: int = 34, ignorar: set | None = None,
) -> list[tuple[int, str]]:
    """Aviso ANTES do 'daqui a pouco' de 10 min (TDAH: 10 min e pouco pra largar o que esta
    fazendo): tarefa de hoje com hora entre 15 e ~30 min a frente. Compromisso de sair fica
    de fora (`ignorar`) - esses ja tem 'se arrumar' e 'hora de sair'."""
    agora = agora or datetime.now()
    ignorar = ignorar or set()
    rows = conn.execute(
        "SELECT id, title, hora FROM tasks WHERE completed_at IS NULL AND due_date = ? AND hora IS NOT NULL",
        (agora.date().isoformat(),),
    ).fetchall()
    avisos = []
    for r in rows:
        if r["id"] in ignorar or e_refeicao(r["title"]):  # comer: o aviso na hora basta
            continue
        try:
            quando = datetime.combine(agora.date(), datetime.strptime(r["hora"], "%H:%M").time())
        except ValueError:
            continue
        falta = (quando - agora).total_seconds() / 60
        if de_min <= falta < ate_min:
            avisos.append((r["id"], f"{r['title']} às {r['hora']} - faltam {round(falta)} min. Dá tempo de fechar o que tá fazendo com calma."))
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
                f"Você já passou do orçamento de {categoria} esse mês: "
                f"R$ {gasto:.2f} de um limite de R$ {limite:.2f}.",
            ))
        elif fracao >= 0.9:
            avisos.append((
                categoria,
                "quase",
                f"Você já gastou R$ {gasto:.2f} em {categoria} esse mês - "
                f"perto do limite de R$ {limite:.2f}.",
            ))
    return avisos


def teto_ia_perto_ou_estourado(conn) -> tuple[str, str] | None:
    """US-A6 (Fase 5): compara o gasto do mes com a API da Anthropic
    (db.resumo_custo_api) contra o teto configurado (db.obter_teto_mensal_ia)
    - devolve (nivel, mensagem) quando passar de 80% ("quase") ou 100%+
    ("estourado"), None sem teto configurado ou dentro dos 80%. Mesma
    logica de orcamentos_perto_ou_estourados (dedup por mes+nivel fica em
    app.py)."""
    resumo = db.resumo_custo_api(conn)
    teto = resumo["teto_mensal_usd"]
    if not teto:
        return None
    gasto = resumo["mes_atual_usd"]
    if resumo["teto_estourado"]:
        return (
            "estourado",
            f"Você já passou do teto mensal de IA: ${gasto:.2f} de um limite de ${teto:.2f}. "
            "O classificador de intent vai preferir resolver por padrao aprendido (sem "
            "chamar a API) até o mês virar.",
        )
    if resumo["teto_perto"]:
        return (
            "quase",
            f"Você já gastou ${gasto:.2f} com a API da IA esse mês - perto do teto de ${teto:.2f}.",
        )
    return None


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
            f"Cobrança de R$ {valor:.2f} em \"{descricao_original}\" - qual assinatura e essa?",
        ))
    return avisos


def _gastos_reais_unificados_para_deteccao(conn) -> list[dict]:
    """Mesma unificacao de expenses (digitado no chat) + bank_transactions
    (extrato sincronizado) que app.py._gastos_reais_unificados ja usa pra
    detectar_gastos_recorrentes - reaproveitada aqui pra nao ter dois
    conceitos diferentes de "todo gasto real" no projeto. Fica em
    notificacoes.py (nao importa de app.py, que importa notificacoes - ver
    de fato o mesmo formato de dict que gastos.py espera)."""
    repetidos = db.gastos_chat_repetidos_no_banco(conn)
    expenses_reais = conn.execute(
        "SELECT id, amount, category, description, source_text, created_at FROM expenses WHERE tipo = 'real'"
    ).fetchall()
    unificado = [
        {k: r[k] for k in ("amount", "category", "description", "source_text", "created_at")}
        for r in expenses_reais
        if r["id"] not in repetidos
    ]
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
        f"Gasto dessa semana já esta em R$ {total_atual:.2f}, "
        f"acima da media das últimas semanas (R$ {media:.2f})."
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


def gastos_fora_do_padrao_categoria(
    conn, hoje: date | None = None, meses_historico: int = 3, desvios: float = 2.0, minimo_amostras: int = 5
) -> list[tuple[int, str]]:
    """Fase 5 (US-C17): extensao de gasto_dia_semana_atipico (mesmo mecanismo
    - "isso hoje esta fora do padrao?" - so que olhando por outro angulo).
    Em vez do TOTAL do dia vs o mesmo dia da semana, compara CADA gasto
    individual registrado hoje com a media + desvio-padrao (aprendizado.py)
    dos gastos historicos da MESMA categoria - pega um gasto pontual fora do
    normal mesmo quando o dia inteiro nao chama atencao (ex: 1 gasto de
    R$800 em "mercado", categoria que raramente passa de R$150). Categoria
    com historico curto demais (`minimo_amostras`) e ignorada - sem dado
    suficiente pra saber o que e "normal" ainda."""
    hoje = hoje or date.today()
    inicio_historico = (hoje - timedelta(days=30 * meses_historico)).isoformat()
    gastos_hoje = conn.execute(
        "SELECT id, category, amount FROM expenses WHERE tipo = 'real' AND date(created_at) = ?",
        (hoje.isoformat(),),
    ).fetchall()
    avisos = []
    for g in gastos_hoje:
        historico = conn.execute(
            """SELECT amount FROM expenses
               WHERE tipo = 'real' AND category = ? AND id != ?
                 AND date(created_at) >= ? AND date(created_at) < ?""",
            (g["category"], g["id"], inicio_historico, hoje.isoformat()),
        ).fetchall()
        valores = [h["amount"] for h in historico]
        if len(valores) < minimo_amostras:
            continue
        media, desvio_padrao = aprendizado.media_e_desvio_padrao(valores)
        # Categoria sem variacao historica (ex: sempre a mesma assinatura de
        # R$30) tem desvio-padrao 0 - "X desvios acima da media" nao faz
        # sentido nesse caso (qualquer valor diferente seria "infinitos
        # desvios"), entao usa 50% acima da media constante como limiar.
        limiar = media + desvios * desvio_padrao if desvio_padrao > 0 else media * 1.5
        if g["amount"] <= limiar:
            continue
        avisos.append(
            (
                g["id"],
                f"Gasto de R$ {g['amount']:.2f} em \"{g['category']}\" esta bem acima do "
                f"normal pra essa categoria (media de R$ {media:.2f}).",
            )
        )
    return avisos


def garantias_vencendo(conn, hoje: date | None = None, dias_aviso: int = 15) -> list[tuple[int, str]]:
    """Fase 5 (US-C18): garantia cujo prazo vence em ate `dias_aviso` dias (ou
    ja venceu). Dedup e pela propria coluna `notificado` da garantia (nao
    pela tabela generica notificacoes_enviadas) - o pedido explicito da
    historia e um flag por garantia, entao so filtra o que ainda nao foi
    avisado; quem chama marca `notificado=1` depois de mandar de verdade."""
    hoje = hoje or date.today()
    avisos = []
    for g in db.list_garantias(conn):
        if g["notificado"]:
            continue
        compra = date.fromisoformat(g["data_compra"])
        vencimento = vida.somar_meses(compra, g["prazo_garantia_meses"])
        dias_ate = (vencimento - hoje).days
        if dias_ate > dias_aviso:
            continue
        quando = f"venceu ha {-dias_ate} dia(s)" if dias_ate < 0 else "vence hoje" if dias_ate == 0 else f"vence em {dias_ate} dia(s)"
        avisos.append((g["id"], f"Garantia de \"{g['produto']}\" {quando} ({vencimento.strftime('%d/%m/%Y')})."))
    return avisos


def sinal_sobrecarga(tarefas_atrasadas: int, sono_ruim: bool, semana_pesada: bool) -> dict:
    """Fase 5 (US-C22): combina sinais independentes numa pontuacao simples
    de sobrecarga - 1 ponto por sinal presente. `tarefas_atrasadas` so conta
    como sinal a partir de 3 (uma unica tarefa atrasada e vida normal, nao
    sobrecarga). Limiar padrao de "sobrecarregado" e 2 de 3 sinais - um
    sinal isolado ainda e dia normal, dois ou mais juntos que indicam
    sobrecarga de verdade.

    `semana_pesada` e o sinal de deteccao de "semana que vem esta cheia"
    (US-C13, historia de outro agente do mesmo grupo/leva - nao integrada
    neste branch ainda). O chamador passa False ate isso ser mesclado; ver
    a nota em progress-grupo-c.txt. Quando integrado, o score passa a valer
    com os 3 sinais automaticamente, sem mudar nada aqui."""
    sinais = []
    if tarefas_atrasadas >= 3:
        sinais.append("tarefas atrasadas")
    if sono_ruim:
        sinais.append("sono ruim")
    if semana_pesada:
        sinais.append("semana pesada")
    pontuacao = len(sinais)
    return {"pontuacao": pontuacao, "sinais": sinais, "sobrecarregado": pontuacao >= 2}


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
            quando = "e amanhã"
        else:
            quando = f"e em {dias_restantes} dias"
        msg = f"\"{row['titulo']}\" {quando} ({proxima.strftime('%d/%m')})."
        sugestao = vida.sugestao_acao_data(row["titulo"])
        if sugestao:
            msg = f"{msg} {sugestao}"
        avisos.append((row["id"], msg))
    return avisos


HORA_PADRAO_DESPERTAR = "09:00"


def lembretes_para_despertar(conn, agora: datetime | None = None) -> list[tuple[int, str]]:
    """Fase 6 (US-E3): lembretes com "Desperta voce" ligado (coluna
    `despertar`) cuja proxima ocorrencia e HOJE e cujo horario (coluna `hora`
    se existir, senao HORA_PADRAO_DESPERTAR) ja chegou. A deduplicacao por
    dia fica com quem chama (ja_notificou_hoje)."""
    agora = agora or datetime.now()
    hoje = agora.date()
    avisos = []
    for row in conn.execute("SELECT * FROM lembretes WHERE despertar = 1").fetchall():
        try:
            base = date.fromisoformat(row["data"])
        except (TypeError, ValueError):
            continue
        if proxima_ocorrencia_lembrete(base, bool(row["recorrente"]), hoje) != hoje:
            continue
        hora_txt = (row["hora"] if "hora" in row.keys() else None) or HORA_PADRAO_DESPERTAR
        try:
            h, m = (int(x) for x in str(hora_txt).split(":")[:2])
        except ValueError:
            h, m = 9, 0
        if (agora.hour, agora.minute) < (h, m):
            continue
        avisos.append((row["id"], f"Hoje: \"{row['titulo']}\"."))
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


def semana_pesada_aviso(conn, hoje: date | None = None) -> str | None:
    """US-C13: compara quantos itens a proxima semana ja tem marcados com a
    mediana das ultimas semanas do proprio usuario (aprendizado.
    semana_pesada - estatistica pura sobre o historico, reaproveitada em vez
    de um numero fixo arbitrario). Pensado pra disparar junto do
    planejamento semanal de domingo (planejamento_semanal_devido acima,
    TODO #15) - app.py decide O QUANDO, essa funcao so decide O QUE dizer."""
    hoje = hoje or date.today()
    inicio_proxima = hoje - timedelta(days=hoje.weekday()) + timedelta(days=7)
    fim_proxima = inicio_proxima + timedelta(days=6)
    contagem_proxima = aprendizado.contagem_itens_semana(conn, inicio_proxima, fim_proxima)
    historico = aprendizado.carga_semanal_historica(conn, hoje)
    resultado = aprendizado.semana_pesada(contagem_proxima, historico)
    if not resultado["sobrecarregada"]:
        return None
    return (
        f"A semana que vem já esta com {contagem_proxima} compromisso(s)/tarefa(s) marcado(s), "
        f"bem acima do seu normal (mediana de {resultado['mediana_historica']:.0f} nas últimas "
        f"{resultado['amostras']} semanas). Vale se planejar com folga."
    )


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


def resumo_manha_gastos_pendentes(conn, hoje: date | None = None) -> str:
    """Parte do resumo falado da manha (US-C11, TTS ja existente no chat -
    ver falarTexto em app.js) que NAO depende de rede - gasto de ontem +
    quantas tarefas ficaram pendentes. A parte de agenda (iCloud via CalDAV,
    instavel) fica em app.py, que ja tem o padrao de buscar com seguranca
    (_eventos_de_hoje_com_seguranca) - notificacoes.py de proposito nunca
    faz chamada de rede, pra ficar testavel isolado como o resto do modulo."""
    hoje = hoje or date.today()
    ontem = hoje - timedelta(days=1)
    gasto_ontem = _total_gasto_dia(conn, ontem)
    pendentes = conn.execute(
        "SELECT COUNT(*) AS n FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL"
    ).fetchone()["n"]

    partes = []
    if gasto_ontem > 0:
        partes.append(f"Ontem você gastou R$ {gasto_ontem:.2f}.")
    else:
        partes.append("Ontem você não registrou gasto nenhum.")
    if pendentes == 0:
        partes.append("Nenhuma tarefa pendente.")
    elif pendentes == 1:
        partes.append("1 tarefa ainda pendente.")
    else:
        partes.append(f"{pendentes} tarefas ainda pendentes.")
    return " ".join(partes)


def currency_voo_baixa(conn, limiar_dias: int = 21) -> str | None:
    """Faz tempo demais desde o ultimo voo REALIZADO (com horas registradas -
    um voo so agendado nao conta) - um lembrete gentil pra nao perder o
    ritmo do curso. None se nunca voou ainda ou se ainda esta dentro do
    limiar."""
    hoje = date.today()
    ultima = conn.execute(
        "SELECT MAX(data) AS ultima FROM voos WHERE horas IS NOT NULL AND data <= ? "
        "AND COALESCE(tipo, '') <> 'simulador'",
        (hoje.isoformat(),),
    ).fetchone()["ultima"]
    if not ultima:
        return None
    dias = (hoje - date.fromisoformat(ultima)).days
    if dias < limiar_dias:
        return None
    return f"Faz {dias} dias que você não voa - pode ser hora de marcar um voo pra não perder o ritmo."


def montar_mensagem_agrupada(itens: list[tuple[str, str]]) -> tuple[str, str]:
    """Fase 5 (US-C4): junta varios avisos (titulo, corpo) numa unica
    mensagem - usado pelo modo de notificacao agrupada (nao-urgentes numa
    janela curta viram um push/Telegram so, em vez de um por aviso), pra nao
    virar 5 notificacoes separadas em 2 minutos. Com um item so, devolve ele
    sem alterar (mesmo formato de sempre - a rota so agrupa de verdade
    quando ha mais de um pra juntar)."""
    if not itens:
        return "", ""
    if len(itens) == 1:
        return itens[0]
    titulo = f"{len(itens)} avisos"
    corpo = "\n".join(f"• {t}: {c}" for t, c in itens)
    return titulo, corpo


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


# ---- Fase 6, US-E8: proatividade unificada ---------------------------------
# Cada checagem abaixo reusa o MESMO calculo que a tela/API correspondente ja
# usa (vida.habito_passou_batido, vida.fracao_limite_cartao,
# vida.calcular_projeto) - nunca recalcula do zero. app.py so decide dedup
# (ja_notificado_alguma_vez/ja_notificou_hoje) e despacha pelo pipeline
# unico de verificar_e_notificar (silencioso/hiperfoco/viagem/agrupamento) -
# nenhum caminho paralelo de envio.

def habitos_passaram_batido(conn, agora: datetime | None = None) -> list[tuple[int, str]]:
    """Usa vida.habito_passou_batido (mesmo calculo que /api/habitos ja
    expoe em 'passou_batido' por habito) pra achar habitos com horario
    definido que passaram 1h do horario sem serem marcados hoje. So
    identifica e monta o texto - dedup (uma vez por dia) fica com quem
    chama (ja_notificou_hoje)."""
    agora = agora or datetime.now()
    hoje = agora.date()
    hoje_iso = hoje.isoformat()
    inicio_semana = (hoje - timedelta(days=hoje.weekday())).isoformat()
    fim_semana = (hoje + timedelta(days=6 - hoje.weekday())).isoformat()
    avisos = []
    for row in db.list_habitos(conn):
        habito = dict(row)
        marcado_hoje = db.habito_marcado(conn, hoje_iso, habito["id"])
        vezes_feitas_semana = len(db.marcacoes_habito_no_periodo(conn, habito["id"], inicio_semana, fim_semana))
        if not vida.habito_passou_batido(habito, agora, marcado_hoje, vezes_feitas_semana):
            continue
        avisos.append(
            (habito["id"], f"{habito['horario']} já foi e o hábito {habito['nome']} segue intocado.")
        )
    return avisos


def tarefas_horario_passou(conn, agora: datetime | None = None, minutos_depois: int = 30) -> list[tuple[int, str]]:
    """Complementa tarefas_com_horario_chegando (aviso ANTES/na hora): um
    segundo aviso, `minutos_depois` apos o horario marcado, se a tarefa
    continuar pendente - so constata o fato (ainda da tempo hoje), sem
    cobranca nem diminutivo. O titulo entra entre aspas no comeco do corpo
    (mesmo padrao de tarefas_paradas acima) - o exemplo do PRD ("a tarefa
    era 14:00...") fica intacto depois das aspas, so identifica QUAL tarefa
    quando ha mais de uma pendente. Dedup (uma vez por dia) fica com quem
    chama."""
    agora = agora or datetime.now()
    hoje = agora.date().isoformat()
    limite = (agora - timedelta(minutes=minutos_depois)).strftime("%H:%M")
    rows = conn.execute(
        """SELECT id, title, hora FROM tasks
           WHERE completed_at IS NULL AND due_date = ? AND hora IS NOT NULL AND hora <= ?""",
        (hoje, limite),
    ).fetchall()
    return [
        (r["id"], f"\"{r['title']}\" - a tarefa era {r['hora']}, ainda dá tempo de resolver hoje.")
        for r in rows
    ]


def cartoes_perto_ou_estourados(conn, hoje: date | None = None) -> list[tuple[int, str, str, str]]:
    """US-E15: reusa vida.fracao_limite_cartao (o MESMO calculo que
    /api/bancos ja expoe em 'limite_info') pra achar cartao perto (>=90%)
    ou ja estourando (>=100%) do limite manual. So cartoes com limite
    configurado entram - sem limite, fracao_limite_cartao ja devolve None
    (nunca inventa um limite). Devolve (conta_id, nivel, titulo, corpo)."""
    hoje = hoje or date.today()
    ano_mes = hoje.strftime("%Y-%m")
    avisos = []
    for c in db.list_bank_accounts(conn):
        if c["tipo"] != "cartao":
            continue
        gasto_ciclo = db.gasto_mes_conta(conn, c["id"], ano_mes)
        info = vida.fracao_limite_cartao(gasto_ciclo, c.get("limite"))
        if not info:
            continue
        if info["fracao"] >= 1:
            nivel, titulo = "estourado", "Cartão estourou o limite"
        elif info["fracao"] >= 0.9:
            pct = round(info["fracao"] * 100)
            nivel, titulo = "quase", f"Cartão em {pct}% do limite"
        else:
            continue
        if info["sobra"] >= 0:
            corpo = f"{c['banco']}: sobram R$ {info['sobra']:.2f}."
        else:
            corpo = f"{c['banco']}: passou R$ {-info['sobra']:.2f} do limite."
        avisos.append((c["id"], nivel, titulo, corpo))
    return avisos


def renda_perto_de_acabar(conn, hoje: date | None = None, limiar: float = 0.7) -> tuple[str, str, str] | None:
    """Fracao da renda do mes ja gasta (mesma soma de expenses reais +
    extrato bancario que _sobra_do_mes/app.py ja usa) - avisa a partir de
    70% comprometido (nivel 'atencao') ou 100%+ ('estourado'). Sem renda
    registrada no mes, None - nao ha base pra calcular fracao nenhuma."""
    hoje = hoje or date.today()
    ano_mes = hoje.strftime("%Y-%m")
    renda_mes = db.total_incomes_mes(conn, ano_mes)
    if renda_mes <= 0:
        return None
    gasto_mes = db.total_gasto_real_mes(conn, ano_mes)
    fracao = gasto_mes / renda_mes
    if fracao < limiar:
        return None
    pct = round(fracao * 100)
    sobra = renda_mes - gasto_mes
    nivel = "estourado" if fracao >= 1 else "atencao"
    titulo = f"{pct}% da renda já foi"
    corpo = f"sobram R$ {sobra:.2f}." if sobra >= 0 else f"passou R$ {-sobra:.2f} da renda."
    return (nivel, titulo, corpo)


def projetos_juntando_poeira(conn, hoje: date | None = None, dias_aviso: int = 21) -> list[tuple[int, str, str]]:
    """US-E13: projeto ativo (nao pausado, nao concluido) sem NENHUM toque
    ha `dias_aviso` dias ou mais - reusa vida.calcular_projeto (mesmo
    'dias_sem_toque' que /api/projetos ja expoe). Projeto que nunca teve
    etapa concluida usa a propria data de criacao como referencia
    (calcular_projeto devolve None nesse caso - sem esse fallback, um
    projeto criado e esquecido nunca avisaria). O ref de dedup muda quando
    o projeto e tocado de novo (referencia = data do ultimo toque ou
    criacao), entao volta a valer sozinho se ficar parado de novo depois.
    Devolve (ref_dedup, titulo, corpo)."""
    hoje = hoje or date.today()
    avisos = []
    for p in db.list_projetos(conn):
        etapas = db.list_etapas_projeto(conn, p["id"])
        calculo = vida.calcular_projeto(etapas, p["prazo_final"], p["criado_em"], hoje)
        status = vida.status_projeto_calculado(p["status"], p["prazo_final"], calculo["percentual"], hoje)
        if status == "pausado" or calculo["percentual"] >= 100:
            continue
        dias = calculo["dias_sem_toque"]
        if dias is None:
            try:
                referencia = date.fromisoformat((p["criado_em"] or "")[:10])
            except ValueError:
                continue
            dias = (hoje - referencia).days
        else:
            datas_feitas = [e["feita_em"] for e in etapas if e.get("feita_em")]
            try:
                referencia = max(date.fromisoformat(d[:10]) for d in datas_feitas)
            except ValueError:
                continue
        if dias < dias_aviso:
            continue
        ref = vida.id_estavel("projeto_poeira", p["id"], referencia.isoformat())
        avisos.append(
            (
                ref,
                "Tem projeto criando poeira",
                f"\"{p['nome']}\": {dias} dias sem um toque, abre e derruba a menor etapa.",
            )
        )
    return avisos


def _renda_media_mensal(conn, hoje: date, meses: int = 3) -> float:
    """Media da renda registrada nos ultimos `meses` meses fechados - so
    entram meses com renda > 0 (mes sem nenhum lancamento pode so estar
    sem digitar ainda, nao vale puxar a media pra baixo por isso)."""
    valores = []
    for i in range(1, meses + 1):
        ref = vida.somar_meses(hoje.replace(day=1), -i)
        total = db.total_incomes_mes(conn, ref.strftime("%Y-%m"))
        if total > 0:
            valores.append(total)
    return sum(valores) / len(valores) if valores else 0.0


def projecao_mes_seguinte_devida(hoje: date | None = None) -> bool:
    """Verdadeiro nos ultimos 3 dias do mes - a janela em que faz sentido
    projetar como o mes que vem chega, perto o bastante pra reagir (revisar
    assinatura, adiar compra) mas nao cedo demais pro dado do mes atual
    ainda estar mudando muito."""
    hoje = hoje or date.today()
    ultimo_dia_mes = vida.somar_meses(hoje.replace(day=1), 1) - timedelta(days=1)
    return hoje >= ultimo_dia_mes - timedelta(days=2)


def mes_seguinte_apertado(conn, hoje: date | None = None, limiar: float = 0.8) -> tuple[str, float] | None:
    """Projeta o mes seguinte comparando os custos fixos ja conhecidos
    (mesma deteccao de gastos.detectar_gastos_recorrentes que a aba Gastos
    usa) com a media de renda dos ultimos 3 meses - sem renda OU sem custo
    fixo identificado ainda, nao ha base pra projetar nada (None). `limiar`
    e a fracao (custos_fixos/renda_media) a partir da qual vale avisar
    (0.8 = 80% comprometido)."""
    hoje = hoje or date.today()
    renda_media = _renda_media_mensal(conn, hoje)
    if renda_media <= 0:
        return None
    recorrentes = gastos.detectar_gastos_recorrentes(_gastos_reais_unificados_para_deteccao(conn), hoje)
    custos_fixos = gastos.total_gasto_fixo_mensal(recorrentes)
    if custos_fixos <= 0:
        return None
    fracao = custos_fixos / renda_media
    if fracao < limiar:
        return None
    proximo_mes = vida.somar_meses(hoje.replace(day=1), 1)
    nome_mes = vida.NOMES_MES[proximo_mes.month - 1].capitalize()
    return (nome_mes, round(fracao, 4))
