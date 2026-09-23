"""Logica pura das funcionalidades do BRIEFING.md (assistente de vida):
check-in, rotina guiada, hiperfoco, "so o essencial", tarefa empacada, contas
pessoais, pessoas. Sem banco e sem rede aqui - quem le/grava e o app.py/db.py,
este modulo so decide (e por isso e testavel isolado)."""

import hashlib
import unicodedata
from calendar import monthrange
from datetime import date, datetime, timedelta

ESCALA_CHECKIN = {"ruim": 1, "ok": 2, "bom": 3}
ROTULO_CHECKIN = {v: k for k, v in ESCALA_CHECKIN.items()}
CAMPOS_CHECKIN = ("energia", "sono", "humor")

# Durante o hiperfoco so passa o que perde o sentido se atrasar: tarefa com
# hora marcada (inclui remedio, que vira tarefa recorrente com hora),
# compromisso chegando e hora de sair pro voo.
CRITICOS_HIPERFOCO = {"tarefa_horario", "compromisso_chegando", "voo_sair", "hiperfoco_fim"}
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
        if alvo in cadastrado.split() or cadastrado in alvo.split() or cadastrado.startswith(alvo):
            return p
    return None


def sugestao_acao_data(titulo: str | None) -> str | None:
    texto = normalizar_nome(titulo)
    if any(palavra in texto for palavra in _PALAVRAS_DATA_SOCIAL):
        return "Ja pensou em mandar uma mensagem ou algo?"
    return None


def momento_rotina(agora: datetime) -> str:
    return "manha" if 4 <= agora.hour < 15 else "noite"


def rotina_manha_devida(agora: datetime, hora: str = "07:00") -> bool:
    """Janela de 5 min (o scheduler roda a cada 5) em torno do horario."""
    try:
        h, m = (int(x) for x in hora.split(":"))
    except ValueError:
        h, m = 7, 0
    alvo = agora.replace(hour=h, minute=m, second=0, microsecond=0)
    return alvo <= agora < alvo + timedelta(minutes=5)
