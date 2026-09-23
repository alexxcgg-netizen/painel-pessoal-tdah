"""Logica pura das funcionalidades do BRIEFING.md (assistente de vida):
check-in, rotina guiada, hiperfoco, "so o essencial", tarefa empacada, contas
pessoais, pessoas. Sem banco e sem rede aqui - quem le/grava e o app.py/db.py,
este modulo so decide (e por isso e testavel isolado)."""

import hashlib
import re
import unicodedata
from calendar import monthrange
from datetime import date, datetime, timedelta

ESCALA_CHECKIN = {"ruim": 1, "ok": 2, "bom": 3}
ROTULO_CHECKIN = {v: k for k, v in ESCALA_CHECKIN.items()}
CAMPOS_CHECKIN = ("energia", "sono", "humor")

# Durante o hiperfoco so passa o que perde o sentido se atrasar: tarefa com
# hora marcada (inclui remedio, que vira tarefa recorrente com hora),
# compromisso chegando e hora de sair pro voo.
CRITICOS_HIPERFOCO = {"tarefa_horario", "compromisso_chegando", "voo_sair", "hiperfoco_fim", "adiado_hiperfoco",
                      "adiado_hiperfoco_leve"}

# Avisos que so disparam numa janela curta de horario (22h, 21h, 7h...) - se o
# hiperfoco segurar, a janela passa e eles sumiriam do dia. Esses ficam
# guardados e saem quando o foco acaba. Agua/pausa fica de fora de proposito:
# o Alex pediu que ela SUMA durante o foco, nao que acumule.
AVISOS_JANELA_CURTA = {
    "hora_de_dormir", "fechamento_noturno", "planejamento_semanal", "rotina_manha", "clima_compromisso",
}
DURACOES_HIPERFOCO = (25, 50, 90)

ITENS_ROTINA_PADRAO = {
    "manha": [
        "Beber um copo de agua",
        "Remedio (se tiver hoje)",
        "Check-in rapido: energia, sono e humor",
        "Olhar as 1-3 coisas essenciais do dia",
    ],
    "noite": [
        "Fechamento do dia (o que foi feito)",
        "Separar o que precisa pra amanha",
        "Celular longe da cama",
    ],
}

# Palavras que indicam data "de gente" (aniversario, casamento...) - ai vale
# sugerir uma acao, nao so avisar a data.
_PALAVRAS_DATA_SOCIAL = (
    "aniversario", "aniver", "niver", "casamento", "bodas", "formatura",
    "dia das maes", "dia dos pais", "namoro", "noivado", "cha de bebe",
)


def normalizar_nome(texto: str | None) -> str:
    if not texto:
        return ""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(sem_acento.lower().split())


def id_estavel(*partes) -> int:
    """Id numerico estavel pra dedup em notificacoes_enviadas quando a coisa
    avisada nao tem um id proprio (ex: conta + mes)."""
    chave = "|".join(str(p) for p in partes)
    digest = hashlib.sha1(chave.encode("utf-8")).digest()[:8]
    return int.from_bytes(digest, "big") % (2**62)


def valor_checkin(valor) -> int | None:
    """Aceita 'ruim'/'ok'/'bom' ou 1/2/3. None pra qualquer outra coisa."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor if valor in ROTULO_CHECKIN else None
    if isinstance(valor, str):
        return ESCALA_CHECKIN.get(normalizar_nome(valor))
    return None


def hiperfoco_ativo(ate_iso: str | None, agora: datetime) -> bool:
    if not ate_iso:
        return False
    try:
        return datetime.fromisoformat(ate_iso) > agora
    except ValueError:
        return False


def minutos_restantes_hiperfoco(ate_iso: str | None, agora: datetime) -> int:
    if not hiperfoco_ativo(ate_iso, agora):
        return 0
    segundos = (datetime.fromisoformat(ate_iso) - agora).total_seconds()
    return max(1, int(segundos // 60) + (1 if segundos % 60 else 0))


def pontuar_tarefa_essencial(tarefa: dict, hoje: date) -> float:
    """Heuristica de importancia (fallback quando a IA nao responde, e ordem
    pra repor quando o Alex troca uma escolhida). Maior = mais importante."""
    pontos = 0.0
    due = tarefa.get("due_date")
    if due:
        try:
            dias = (hoje - date.fromisoformat(due)).days
        except ValueError:
            dias = None
        if dias is not None:
            if dias > 0:
                pontos += 50 + min(dias, 10) * 2
            elif dias == 0:
                pontos += 40
            else:
                pontos += max(0, 20 + dias * 5)
    else:
        pontos += 10
    if tarefa.get("hora") and due == hoje.isoformat():
        pontos += 30
    if tarefa.get("recorrente_origem_id"):
        pontos -= 15  # rotina ja tem aviso proprio, raramente e a "coisa importante" do dia
    return pontos


def escolher_essencial_heuristica(tarefas: list[dict], hoje: date, n: int = 3) -> list[int]:
    ordenadas = sorted(tarefas, key=lambda t: (-pontuar_tarefa_essencial(t, hoje), t["id"]))
    return [t["id"] for t in ordenadas[:n]]


def dias_empacada(tarefa: dict, subtasks: list[dict], hoje: date) -> int | None:
    """Quantos dias a tarefa esta travada, ou None se nao estiver.
    Com prazo: travada a partir de 3 dias de atraso. Sem prazo: 7 dias desde
    que foi criada sem nenhum passo concluido nesse periodo."""
    if tarefa.get("completed_at") or tarefa.get("recorrente_origem_id"):
        return None
    due = tarefa.get("due_date")
    if due:
        try:
            atraso = (hoje - date.fromisoformat(due)).days
        except ValueError:
            return None
        return atraso if atraso >= 3 else None
    criado = tarefa.get("created_at")
    if not criado:
        return None
    try:
        criado_dia = datetime.fromisoformat(criado).date()
    except ValueError:
        return None
    parado = (hoje - criado_dia).days
    if parado < 7:
        return None
    limite = hoje - timedelta(days=7)
    for s in subtasks:
        feito = s.get("completed_at")
        if feito:
            try:
                if datetime.fromisoformat(feito).date() >= limite:
                    return None
            except ValueError:
                continue
    return parado


def proximo_vencimento(dia_vencimento: int, hoje: date) -> date:
    """Proxima data (>= hoje) em que a conta vence. Dia 31 em mes de 30 dias
    vira dia 30 (ultimo dia do mes), igual banco faz."""
    def no_mes(ano: int, mes: int) -> date:
        return date(ano, mes, min(dia_vencimento, monthrange(ano, mes)[1]))

    este_mes = no_mes(hoje.year, hoje.month)
    if este_mes >= hoje:
        return este_mes
    ano, mes = (hoje.year + 1, 1) if hoje.month == 12 else (hoje.year, hoje.month + 1)
    return no_mes(ano, mes)


def vencimento_anterior(dia_vencimento: int, hoje: date) -> date:
    """Ultima data (<= hoje) em que a conta venceu."""
    def no_mes(ano: int, mes: int) -> date:
        return date(ano, mes, min(dia_vencimento, monthrange(ano, mes)[1]))

    este_mes = no_mes(hoje.year, hoje.month)
    if este_mes <= hoje:
        return este_mes
    ano, mes = (hoje.year - 1, 12) if hoje.month == 1 else (hoje.year, hoje.month - 1)
    return no_mes(ano, mes)


def pessoas_sem_contato(pessoas: list[dict], hoje: date) -> list[tuple[dict, int]]:
    """Pessoas cuja frequencia desejada de contato ja passou. Base: ultimo
    contato registrado, ou a data de cadastro se nunca registrou nenhum."""
    atrasadas = []
    for p in pessoas:
        base_txt = p.get("ultimo_contato") or (p.get("criado_em") or "")[:10]
        try:
            base = date.fromisoformat(base_txt)
        except ValueError:
            continue
        dias = (hoje - base).days
        if dias >= p.get("frequencia_dias", 14):
            atrasadas.append((p, dias))
    atrasadas.sort(key=lambda par: par[1] - par[0].get("frequencia_dias", 14), reverse=True)
    return atrasadas


def achar_pessoa(pessoas: list[dict], nome: str) -> dict | None:
    """Casa o nome falado com a lista cadastrada: igual (sem acento/caixa)
    primeiro, depois um contendo o outro ("mae" casa com "Mae", "Joao" casa
    com "Joao Pedro")."""
    alvo = normalizar_nome(nome)
    if not alvo:
        return None
    for p in pessoas:
        if normalizar_nome(p["nome"]) == alvo:
            return p
    for p in pessoas:
        cadastrado = normalizar_nome(p["nome"])
        if alvo in cadastrado.split() or cadastrado in alvo.split():
            return p
    return None


def sugestao_acao_data(titulo: str | None) -> str | None:
    texto = normalizar_nome(titulo)
    if any(palavra in texto for palavra in _PALAVRAS_DATA_SOCIAL):
        return "Ja pensou em mandar uma mensagem ou algo?"
    return None


def momento_rotina(agora: datetime) -> str:
    return "manha" if 4 <= agora.hour < 15 else "noite"


def dia_da_rotina(momento: str, agora: datetime) -> date:
    """A rotina da noite que passa da meia-noite continua sendo a do dia
    anterior - senao o checklist feito as 23h40 aparece zerado as 00h30."""
    if momento == "noite" and agora.hour < 4:
        return agora.date() - timedelta(days=1)
    return agora.date()


def rotina_manha_devida(agora: datetime, hora: str = "07:00") -> bool:
    """Janela de 5 min (o scheduler roda a cada 5) em torno do horario."""
    try:
        h, m = (int(x) for x in hora.split(":"))
    except ValueError:
        h, m = 7, 0
    alvo = agora.replace(hour=h, minute=m, second=0, microsecond=0)
    return alvo <= agora < alvo + timedelta(minutes=5)


# ---- Fase 2 ----

HORAS_AGUA_PAUSA = (9, 11, 13, 15, 17)

CHECKLIST_PRE_VOO = [
    "Fone (headset)",
    "Carta WAC",
    "Cartas dos aerodromos",
    "Plano de voo",
    "Peso e balanceamento",
]

LIMITE_SONO_RUIM_HORAS = 6


def slot_agua_pausa(agora: datetime) -> int | None:
    """Hora do lembrete de agua/pausa se estiver na janela de 5 min de um
    deles (dia util, 9h-17h a cada 2h), senao None."""
    if agora.weekday() >= 5 or agora.hour not in HORAS_AGUA_PAUSA or agora.minute >= 5:
        return None
    return agora.hour


def sequencia_noites_ruins(
    sono_por_dia: dict[str, float], checkin_sono_por_dia: dict[str, int], hoje: date
) -> tuple[int, date | None]:
    """(quantas noites ruins seguidas, primeira noite da sequencia), terminando
    hoje (ou ontem, se hoje ainda nao tem dado). Ruim = menos de 6h no Saude OU
    'ruim' no check-in. A primeira noite nao muda quando o dado de hoje chega
    depois - e ela que identifica a sequencia (um aviso por sequencia)."""
    def ruim(dia: date) -> bool | None:
        iso = dia.isoformat()
        horas = sono_por_dia.get(iso)
        checkin = checkin_sono_por_dia.get(iso)
        if horas is None and checkin is None:
            return None
        return (horas is not None and horas < LIMITE_SONO_RUIM_HORAS) or checkin == ESCALA_CHECKIN["ruim"]

    dia = hoje
    if ruim(dia) is None:
        dia = hoje - timedelta(days=1)
    seguidas = 0
    while ruim(dia):
        seguidas += 1
        dia -= timedelta(days=1)
    return seguidas, (dia + timedelta(days=1) if seguidas else None)


def noites_ruins_seguidas(sono_por_dia: dict[str, float], checkin_sono_por_dia: dict[str, int], hoje: date) -> int:
    return sequencia_noites_ruins(sono_por_dia, checkin_sono_por_dia, hoje)[0]


def compromissos_na_chuva(eventos: list[dict], resumo_chuva: dict | None) -> list[dict]:
    """Compromissos de hoje (com hora) que caem dentro da janela de chuva
    prevista (resumo de clima.resumo_chuva_do_dia)."""
    if not resumo_chuva or not resumo_chuva.get("alerta"):
        return []
    inicio, fim = resumo_chuva["hora_inicio"], resumo_chuva["hora_fim"]
    afetados = []
    for e in eventos:
        if e.get("dia_inteiro"):
            continue
        try:
            hora = datetime.fromisoformat(e["inicio"]).hour
        except (KeyError, TypeError, ValueError):
            continue
        if inicio <= hora < fim:
            afetados.append(e)
    return afetados


_PALAVRAS_TREINO = {"treino", "academia", "musculacao", "treinar", "malhar"}
# "treino de pouso", "treino de voo": o Alex e aluno piloto - nao e academia.
_PALAVRAS_AVIACAO = {"voo", "pouso", "pousos", "decolagem", "navegacao", "solo", "simulador", "aeroclube"}


def _palavras(texto: str | None) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalizar_nome(texto))


def _contem_sequencia(palavras: list[str], trecho: list[str]) -> bool:
    n = len(trecho)
    return n > 0 and any(palavras[i:i + n] == trecho for i in range(len(palavras) - n + 1))


def ficha_para_titulo(fichas: list[dict], titulo: str | None) -> list[dict]:
    """Fichas de treino que batem com o titulo da tarefa: pelo nome do grupo
    como palavra(s) inteira(s) ("Treino peito" -> ficha "Peito"; "abraco" nao
    casa com "Braco"). Titulo generico de treino/academia sem grupo nenhum
    mostra todas. Treino de aviacao nao e academia."""
    palavras = _palavras(titulo)
    if not palavras or _PALAVRAS_AVIACAO & set(palavras):
        return []
    achadas = [f for f in fichas if _contem_sequencia(palavras, _palavras(f["grupo"]))]
    if achadas:
        return achadas
    if _PALAVRAS_TREINO & set(palavras):
        return list(fichas)
    return []


def mesma_cidade(cidade: str | None, destino: str | None) -> bool:
    """Lugar curtido vale pra viagem se a cidade aparece no destino como
    palavra(s) inteira(s) ("Floripa" casa com "Floripa, SC"; "Sal" nao casa
    com "Salvador"; cidade so de emoji nao casa com tudo)."""
    return _contem_sequencia(_palavras(destino), _palavras(cidade))


def eh_dia_de_academia(titulos_hoje: list[str]) -> bool:
    for t in titulos_hoje:
        palavras = set(_palavras(t))
        if palavras & _PALAVRAS_TREINO and not palavras & _PALAVRAS_AVIACAO:
            return True
    return False


def checklist_saida(agora: datetime, bateria: int | None, academia_hoje: bool, saida_noite: bool) -> list[str]:
    """O que levar/fazer antes de sair de casa (pedido do Alex): carteira
    sempre; carregador com bateria abaixo de 50%; fone e garrafa em dia de
    academia; bigode e cavanhaque em sexta/sabado a noite se vai sair."""
    itens = ["carteira"]
    if bateria is not None and bateria < 50:
        itens.append(f"carregador (bateria em {bateria}%)")
    if academia_hoje:
        itens.append("fone e garrafa de agua (academia hoje)")
    if saida_noite and agora.weekday() in (4, 5) and agora.hour >= 16:
        itens.append("fazer bigode e cavanhaque antes de sair")
    return itens


def mensagem_chegou_casa(agora: datetime, proximo: dict | None, pendentes: list[str]) -> str | None:
    """Chegar em casa depende do momento: se ainda tem compromisso hoje,
    lembra dele e de quando sair de novo; a noite, sem mais nada, mostra o
    que ficou pendente. Meio do dia sem nada marcado: nao fala nada."""
    if proximo:
        try:
            inicio = datetime.fromisoformat(proximo["inicio"])
        except (KeyError, TypeError, ValueError):
            inicio = None
        if inicio and inicio > agora:
            sair = inicio - timedelta(minutes=30)
            quando = "ja" if sair <= agora else f"ate {sair.strftime('%H:%M')}"
            return f"Proximo: {proximo['titulo']} as {inicio.strftime('%H:%M')} - sai {quando}."
    if agora.hour >= 18:
        if pendentes:
            lista = ", ".join(pendentes[:3])
            resto = f" e mais {len(pendentes) - 3}" if len(pendentes) > 3 else ""
            return f"Chegou. Ficou pendente hoje: {lista}{resto}. Sem culpa - vai pra amanha."
        return "Chegou. Nada pendente pra hoje - descansa."
    return None


def somar_meses(base: date, meses: int) -> date:
    """Soma N meses a uma data, cravando no ultimo dia do mes de destino
    quando o dia original nao existir la (ex: 31/01 + 1 mes = 28 ou 29/02)."""
    mes_total = base.month - 1 + meses
    ano, mes = base.year + mes_total // 12, mes_total % 12 + 1
    return date(ano, mes, min(base.day, monthrange(ano, mes)[1]))


def proxima_data_manutencao(ultima_vez: str | None, intervalo_meses: int, criado_em: str | None, hoje: date) -> date:
    """Proxima vez que a manutencao vence. Sem registro de ultima vez, conta
    a partir do cadastro."""
    base_txt = ultima_vez or (criado_em or "")[:10] or hoje.isoformat()
    try:
        base = date.fromisoformat(base_txt)
    except ValueError:
        base = hoje
    return somar_meses(base, intervalo_meses)


_PREFIXO_ACABOU = re.compile(r"^\s*(acab(ou|aram))\b\s*((o|a|os|as)\b\s*)?", re.IGNORECASE)


def limpar_item_compra(texto: str) -> str:
    """'Acabou o Cafe.' -> 'Cafe' (mantem acento/caixa pra exibir bonito)."""
    return _PREFIXO_ACABOU.sub("", texto).strip(" .,!;")


def normalizar_item_compra(texto: str | None) -> str:
    """'acabou o cafe' / 'Cafe.' -> 'cafe' (pra nao duplicar na lista)."""
    return normalizar_nome(limpar_item_compra(texto or "")).strip(" .,!;")


# ---- Fase 3 ----

_PALAVRAS_BUROCRACIA = {
    "cnh", "passaporte", "irpf", "licenca", "cma", "habilitacao", "rg", "ipva", "licenciamento",
    "certificado",
}
_FRASES_BUROCRACIA = (
    "visto americano", "visto de turista", "visto de trabalho", "visto de estudante", "renovar visto",
    "renovacao do visto",
    "imposto de renda", "declaracao do ir", "declaracao de ir", "exame medico", "titulo de eleitor",
)


def eh_burocracia(titulo: str | None) -> bool:
    """Prazo de documento/imposto: vale avisar com 30 dias (da tempo de agendar),
    nao so na ultima semana como uma data qualquer. Palavra inteira ("rg" nao
    casa com "Jorge", e "ir" sozinho nao entra - e verbo)."""
    texto = normalizar_nome(titulo)
    palavras = set(re.findall(r"[a-z0-9]+", texto))
    return bool(palavras & _PALAVRAS_BUROCRACIA) or any(f in texto for f in _FRASES_BUROCRACIA)


def projecao_fim_do_mes(renda_mes: float, gasto_real_mes: float, contas_pendentes: float, hoje: date) -> dict:
    """Quanto deve sobrar no fim do mes se o ritmo de gasto ate agora continuar,
    ja descontando as contas pessoais que ainda vao vencer no mes. Estimativa
    simples e explicada, nao previsao magica."""
    dias_no_mes = monthrange(hoje.year, hoje.month)[1]
    dias_passados = hoje.day
    dias_restantes = dias_no_mes - dias_passados
    ritmo_diario = gasto_real_mes / dias_passados if dias_passados else 0.0
    gasto_projetado = gasto_real_mes + ritmo_diario * dias_restantes + contas_pendentes
    return {
        "ritmo_diario": round(ritmo_diario, 2),
        "dias_restantes": dias_restantes,
        "contas_pendentes": round(contas_pendentes, 2),
        "gasto_projetado": round(gasto_projetado, 2),
        "sobra_projetada": round(renda_mes - gasto_projetado, 2),
    }


def previsao_meta(valor_alvo: float, valor_guardado: float, depositos: list[dict], hoje: date) -> dict | None:
    """Quando a meta bate no ritmo dos depositos dos ultimos 90 dias. None se
    nao da pra dizer (sem deposito recente, ou ja bateu)."""
    falta = valor_alvo - valor_guardado
    if falta <= 0:
        return None
    inicio = hoje - timedelta(days=90)
    total = 0.0
    primeiro = None
    for d in depositos:
        try:
            quando = datetime.fromisoformat(d["criado_em"]).date()
        except (KeyError, TypeError, ValueError):
            continue
        if quando < inicio or d.get("valor", 0) <= 0:
            continue
        total += d["valor"]
        primeiro = quando if primeiro is None or quando < primeiro else primeiro
    if total <= 0 or primeiro is None:
        return None
    dias_janela = max((hoje - primeiro).days, 30)
    por_dia = total / dias_janela
    dias_ate = int(falta / por_dia) + 1
    if dias_ate > 365 * 50:  # deposito simbolico: "daqui 800 anos" nao ajuda ninguem
        return None
    return {"ritmo_mensal": round(por_dia * 30, 2), "data_prevista": (hoje + timedelta(days=dias_ate)).isoformat()}


def uso_de_apps(eventos: list[dict], limite_sessao_min: int = 180) -> dict[str, int]:
    """Minutos por app a partir dos eventos 'abriu'/'fechou' do Atalhos (em
    ordem de tempo). Abriu sem fechou, ou sessao absurda (> 3h, provavelmente
    um 'fechou' perdido), nao conta - melhor subestimar do que inventar."""
    abertos: dict[str, datetime] = {}
    total: dict[str, float] = {}
    for e in sorted(eventos, key=lambda x: x["em"]):
        try:
            quando = datetime.fromisoformat(e["em"])
        except (KeyError, TypeError, ValueError):
            continue
        app = e.get("app")
        if not app:
            continue
        if e.get("evento") == "abriu":
            abertos[app] = quando
        elif e.get("evento") == "fechou" and app in abertos:
            minutos = (quando - abertos.pop(app)).total_seconds() / 60
            if 0 <= minutos <= limite_sessao_min:
                total[app] = total.get(app, 0) + minutos
    return {app: round(m) for app, m in sorted(total.items(), key=lambda kv: -kv[1]) if round(m) > 0}


def formatar_minutos(minutos: int) -> str:
    horas, resto = divmod(int(minutos), 60)
    if horas and resto:
        return f"{horas}h{resto:02d}"
    return f"{horas}h" if horas else f"{resto}min"


def taxa(feitos: int, total: int) -> int | None:
    return round(100 * feitos / total) if total else None


def mes_anterior(hoje: date) -> tuple[date, date]:
    """(primeiro dia, ultimo dia) do mes anterior a `hoje`."""
    ultimo = hoje.replace(day=1) - timedelta(days=1)
    return ultimo.replace(day=1), ultimo


def intervalo_trimestre(ano: int, trimestre: int) -> tuple[date, date]:
    """(primeiro dia, ultimo dia) do trimestre (1-4) do ano informado - Fase
    5 (US-C3, revisao trimestral/anual). Trimestre invalido levanta
    ValueError (a rota decide o 400)."""
    if trimestre not in (1, 2, 3, 4):
        raise ValueError(f"trimestre invalido: {trimestre!r}")
    primeiro_mes = 3 * (trimestre - 1) + 1
    primeiro = date(ano, primeiro_mes, 1)
    ultimo_mes = primeiro_mes + 2
    ultimo = date(ano, ultimo_mes, monthrange(ano, ultimo_mes)[1])
    return primeiro, ultimo


def intervalo_ano(ano: int) -> tuple[date, date]:
    """(primeiro dia, ultimo dia) do ano informado."""
    return date(ano, 1, 1), date(ano, 12, 31)


def trimestre_de(hoje: date) -> int:
    return (hoje.month - 1) // 3 + 1


NOMES_MES = (
    "janeiro", "fevereiro", "marco", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def resumo_curto_lockscreen(tarefas_pendentes: int, gasto_hoje: float) -> str:
    """Uma linha so, o bastante pra caber num widget de tela de bloqueio
    (accessoryInline no Scriptable so mostra uma linha, sem quebra) -
    ver /api/atalho/resumo e scriptable/widget_lockscreen.js."""
    plural = "tarefa" if tarefas_pendentes == 1 else "tarefas"
    texto = f"{tarefas_pendentes} {plural}"
    if gasto_hoje:
        texto += f" · R$ {gasto_hoje:.2f} hoje"
    return texto


def priorizar_esperas(esperas: list[dict], hoje: date) -> list[dict]:
    """Ordena esperas pendentes por quem deveria ser respondido/cobrado
    primeiro - combina tempo parado (dias desde `criado_em`) com a marcacao
    de importancia (coluna `importante`, 0/1). O peso de 5 dias abaixo e o
    que decide o equilibrio entre os dois fatores: uma espera importante
    "pula a fila" na frente de uma mais antiga porem sem importancia
    marcada, mas nao apaga o tempo parado - uma espera SUPER antiga ainda
    sobe pro topo, mesmo sem importancia nenhuma. Devolve copias dos dicts
    de entrada com `dias_parado`/`prioridade_score` adicionados, da mais
    prioritaria pra menos."""
    PESO_IMPORTANTE_EM_DIAS = 5

    def _dias(espera: dict) -> int:
        criado = espera["criado_em"]
        data_criado = datetime.fromisoformat(criado).date() if isinstance(criado, str) else criado
        return (hoje - data_criado).days

    enriquecidas = []
    for espera in esperas:
        item = dict(espera)
        dias = _dias(espera)
        bonus = PESO_IMPORTANTE_EM_DIAS if espera.get("importante") else 0
        item["dias_parado"] = dias
        item["prioridade_score"] = dias + bonus
        enriquecidas.append(item)
    return sorted(enriquecidas, key=lambda i: i["prioridade_score"], reverse=True)


NIVEIS_ENERGIA = {"baixa": 1, "media": 2, "alta": 3}


def tarefas_compativeis_com_energia(tasks: list[dict], nivel: str) -> list[dict]:
    """Filtra tarefas pendentes compativeis com o nivel de energia atual
    informado (baixa/media/alta) - uma tarefa de esforco 'alta' so aparece
    quando a energia tambem for 'alta'; uma tarefa 'baixa' cabe em
    qualquer nivel. Tarefa sem esforco definido (nunca classificada) e
    tratada como 'media' - nem escondida na energia baixa por padrao, nem
    despejada ali igual as leves de verdade. Nivel invalido devolve lista
    vazia em vez de quebrar (a rota decide o 400)."""
    nivel_num = NIVEIS_ENERGIA.get(nivel)
    if nivel_num is None:
        return []
    compativeis = []
    for tarefa in tasks:
        esforco = tarefa.get("esforco") or "media"
        esforco_num = NIVEIS_ENERGIA.get(esforco, NIVEIS_ENERGIA["media"])
        if esforco_num <= nivel_num:
            compativeis.append(tarefa)
    return compativeis
