"""Revisor da resposta do chat (leva "agentes", 2026-11-05).

Lendo 30 dias de conversa, os erros que mais voltaram eram de conta, e o modelo maior não errou menos:
- hora de sair diferente da que a ferramenta calculou (o card dizia uma coisa, o texto outra);
- "sai às 14h" quando já eram 15h;
- "das 14h às 16h (3 h)": conta de intervalo errada;
- "leva 20 min de carro" quando a rota dava 45;
- "anotei"/"marquei" sem ter chamado nenhuma ferramenta que grava.

Tudo aqui é código, sem IA: compara o texto com o que as ferramentas devolveram NESTA resposta e com o
relógio. Achou erro: `ia.funcoes.chat.chat` devolve uma nota curta pro modelo e ele refaz a resposta
UMA vez (o achado diz o certo, então a correção não precisa de modelo maior). Frase de robô no fim
("Se quiser, ...", "Espero ter ajudado") sai direto no código, sem nova chamada.

Regra do revisor: na dúvida, não acusa. Um falso alarme custa uma rodada a mais (~3 s); deixar
passar custa o que já custava antes.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime

# Ferramentas que só leem ou calculam. Qualquer outra chamada sem "erro" conta como "gravou algo".
_PREFIXOS_SO_LEITURA = ("consultar_", "sugerir_", "estimar_", "calcular_", "comparar_")
_SO_LEITURA = {"briefing_meteo_voo", "fazer_pergunta_aviacao", "revisar_pergunta_aviacao"}

_HORA = r"(\d{1,2})(?:[:h](\d{2})|h)(?![\d])"
_RE_SAIR = re.compile(
    r"\b(?:sai|sair|saia|saindo|sa[ií]da)\b(?:\s+de\s+casa)?\s+(?:(?:[aà]s?|por\s+volta\s+das|l[aá]\s+pelas|umas)\s+)?"
    + _HORA, re.IGNORECASE)
_RE_ARRUMAR = re.compile(
    r"\barrumar\b[^.!?\n]{0,25}?\b(?:[aà]s?|umas)\s+" + _HORA, re.IGNORECASE)
_RE_PASSADO_ANTES = re.compile(
    r"(?:devia|deveria|tinha\s+que|era\s+pra|ia|teria\s+que|j[aá])\s+(?:ter\s+)?$", re.IGNORECASE)
_RE_OUTRO_DIA = re.compile(
    r"\b(amanh[aã]|depois\s+de\s+amanh[aã]|segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo|"
    r"semana\s+que\s+vem|pr[oó]xima\s+semana|dia\s+\d{1,2})\b", re.IGNORECASE)
_RE_INTERVALO = re.compile(
    r"\bd[ae]s?\s+" + _HORA + r"\s+(?:[aà]s?|at[eé])\s+" + _HORA
    + r"[^.!?\n]{0,20}?\(?\s*(?:s[aã]o\s+|d[aá]\s+|=\s*|,\s*)?(\d{1,2})\s*(h|horas?|min(?:utos)?)(?:\s*e\s*(\d{1,2})\s*min)?",
    re.IGNORECASE)
_RE_TRAJETO = re.compile(
    r"(?:\bleva\s+(?:uns\s+|cerca\s+de\s+|mais\s+ou\s+menos\s+)?|\b)(\d{1,3})\s*(?:min(?:utos)?|h(?:oras?)?(?:\s*e?\s*(\d{1,2})\s*(?:min)?)?)"
    r"\s+(?:de\s+)?(?:carro|viagem|estrada|trajeto|caminho|dirigindo)\b", re.IGNORECASE)
_RE_AFIRMOU = re.compile(
    r"\b(anotei|registrei|marquei|agendei|salvei|coloquei|lancei|criei|adicionei|botei|guardei|"
    r"atualizei|mudei|troquei|movi|remarquei|conclu[ií]|desmarquei|"
    # leva 08/11 (item B6): os outros jeitos de dizer que fez
    r"ajustei|empurrei|risquei|apaguei|cancelei|anotad[oa]s?|riscad[oa]s?|"
    # 3a rodada: passei/deixei só com destino ("passei pra sexta", "deixei o dentista pras 10h"); "passei o olho
    # na tua agenda" e "deixei como tava" não gravam nada
    r"(?:passei|deixei)(?!\s+(?:o|um)\s+olho\b)"
    r"(?=(?:\s+[^\s.!?,;:]+){0,3}?\s+(?:pra|para|pro|pros|pras|[aà]s|no\s+dia)\b))\b", re.IGNORECASE)
# particípio ("tá anotado", "tá riscado") descreve o estado: vale sem gravar se ele perguntou ou se a resposta
# conferiu (consultar_*) - é o "já tá: ..." da mensagem reenviada
_RE_PARTICIPIO = re.compile(r"(?:anotad|riscad)[oa]s?$", re.IGNORECASE)
# "Tá anotado, sexta 10h" = o "já tá" do reenvio (estado, não ação de agora)
_RE_TA_ANTES = re.compile(r"\b(?:t[aá]|est[aá]|segue|continua)\s+$", re.IGNORECASE)
# atravessa vírgula/ponto e vírgula/dois pontos: "Não mexi, deixei como tava"
_RE_NEGACAO_ANTES = re.compile(r"\b(n[aã]o|nunca|ainda\s+n[aã]o|nem)\s+(?:\w+[,;:]?\s+){0,1}$", re.IGNORECASE)
# "já tá anotado", "já anotei", "tava anotado": coisa feita antes (reenvio), não agora
_RE_JA_ANTES = re.compile(r"(?:\bj[aá]\s+(?:\w+\s+){0,2}|\b(?:tava|estava|tinha)\s+(?:\w+\s+){0,1})$", re.IGNORECASE)

# Falar do sistema (item B3): "o card mostra", "a ferramenta de rota", "o painel calculou", nome de função.
_RE_SISTEMA = re.compile(
    r"\bcards?\b"
    r"|\b(?:usei|chamei|uso|usar|chamar|rodei|rodar)\s+(?:a\s+|uma\s+)?ferramenta\b"
    r"|\bferramenta\s+d[eoa]s?\s+(?:rota|trajeto|clima|agenda|tarefas?|busca|hor[aá]rios?|mapa|c[aá]lculo|consulta|registro)\b"
    r"|\b(?:a|essa|esta)\s+ferramenta\s+(?:calcul|mostr|devolv|deu|retorn|ach|diz|diss|n[aã]o)\w*"
    # 3a rodada: "painel" também é o do avião ("no 152 o painel mostra a velocidade em nós"): só verbo que só o
    # app faz
    r"|\bo\s+painel\s+(?:sugeriu|calculou|registrou|gravou|estimou)\b"
    r"|\bbanco\s+de\s+dados\b|\bmodo\s+visitante\b"
    r"|\b(?:registrei|anotei|salvei|gravei|lancei|coloquei|consta)\s+(?:no|do)\s+sistema\b"
    r"|\b(?:registrar|consultar|ajustar|estimar|sugerir|agendar|planejar|calcular|definir|mover|apagar|buscar|"
    r"salvar|comecar|atualizar|propor|ver)_[a-z_]+\b",
    re.IGNORECASE)
_RE_FALA_DO_SISTEMA = re.compile(r"\b(?:cards?|ferramentas?|painel|sistema|app|aplicativo)\b", re.IGNORECASE)

# "você" com o Alex (item B1): com ele é sempre "tu". Texto entre aspas (recado pra outra pessoa) não conta.
# 3a rodada: "vocês" é o plural de "tu" ("vocês saem 19h40", ele e a Ana) - só o singular conta
_RE_VOCE = re.compile(r"\b(?:voc[eê]|vc)\b", re.IGNORECASE)
# aspas retas, curvas, angulares e simples (reta e curva): recado pra outra pessoa
_RE_ENTRE_ASPAS = re.compile(
    r'"[^"\n]*"|\u201c[^\u201d\n]*\u201d|«[^»\n]*»|\u2018[^\u2019\n]*\u2019|(?<!\w)\'[^\'\n]+\'(?!\w)')
# "Manda pra ela: Oi Ana, você me espera?" / "Escreve assim: ..." - do dois-pontos pra frente é o recado
_RE_RECADO_DEPOIS = re.compile(
    r"\b(?:manda|mande|envia|escreve|fala|diz|responde)\b[^:\n.!?]{0,25}:|\bassim\s*:", re.IGNORECASE)
_RE_PEDIU_RECADO = re.compile(
    r"\b(?:mensagem|msg|recado|texto|escreve|escrever|redige|redigir|responde|responder|resposta|whats|zap|"
    r"e-?mail|manda(?:r)? pr[ao]|cobra(?:r)?|avisa(?:r)?|fala(?:r)? pr[ao]|diz(?:er)? pr[ao]|"
    r"pergunta(?:r)? pr[ao]|desculpas?|dizer\s+n[aã]o)\b", re.IGNORECASE)

# Abertura igual à da resposta anterior (item B2). Solta ("Beleza, ...", "Fechado. ...") sai no código; verbo de
# confirmação colado no resto ("Anotei o dentista...") pede refazer.
_RE_ABERTURA_SOLTA = re.compile(r"^\s*([^\W\d_]+(?:\s+[^\W\d_]+){0,2})\s*(?:[,.!…:;]+|\s[-–—]\s)\s*")
_CONFIRMACOES = frozenset((
    "anotei", "anotado", "marquei", "registrei", "salvei", "botei", "coloquei", "agendei", "ajustei", "deixei",
    "passei", "mudei", "troquei", "fechado", "beleza", "pronto", "feito", "show", "certo", "combinado", "boa",
    "perfeito", "ok", "blz", "tranquilo", "massa", "top", "demorou", "fechou",
))

# Oferta no fim (item B2): "é só falar", "me fala que eu ajusto", "se não for essa, me fala" em QUALQUER ponto da
# última frase - sai a oração da oferta, fica o resto.
# 3a rodada: "é só falar/avisar" só é oferta se a frase acaba ali ou segue com "se/que" ("é só falar se quiser");
# "é só avisar a Ana que ela espera" e "é só falar do orçamento" são instrução, ficam
_RE_OFERTA = re.compile(
    r"\b(?:[eé]\s+)?s[oó]\s+(?:me\s+)?(?:falar|avisar|pedir|dizer)\b(?=\s*(?:[.!?…]|$|,?\s*(?:se|que)\b))"
    r"|\bme\s+(?:fala|avisa|diz|chama)\s+(?:que|q)\s+(?:eu\s+)?(?:ajusto|mudo|troco|arrumo|corrijo|acerto|remarco|"
    r"mexo|altero|refa[cç]o|ajeito|recalculo|atualizo)\b"
    r"|\bse\s+n[aã]o\s+for\s+(?:ess[ae]|isso|o\s+lugar|o\s+certo|a\s+certa)\b[^.!?…]*\bme\s+(?:fala|avisa|diz)\b"
    r"|\bmuda\s+o\s+que\s+quiser\b"
    r"|\bse\s+quiser,?\s+(?:eu\s+)?(?:outr[oa]|mudar|trocar|ajustar|mexer|mudo|troco|ajusto|mexo)\b",
    re.IGNORECASE)
_RE_INICIO_OFERTA = re.compile(
    r"(?:e\s+|mas\s+|a[ií]\s+)?(?:se\b|caso\b|qualquer\s+coisa|quiser\b|[eé]\s+s[oó]\b|s[oó]\s+(?:me\s+)?"
    r"(?:falar|avisar|pedir|dizer)\b|me\s+(?:fala|avisa|diz|chama)\b|muda\s+o\s+que)",
    re.IGNORECASE)
def _inicio_ultima_frase(s: str) -> int:
    """Onde começa a última frase. Ponto entre dígitos ("R$ 1.250") não separa; 08/11: reticências dentro de
    parênteses ("(carro, viagem...)") também não - o corte deixava "Se for pra alguma coisa (... )." solto."""
    inicio, nivel = 0, 0
    for i, c in enumerate(s):
        if c == "(":
            nivel += 1
        elif c == ")":
            nivel = max(0, nivel - 1)
        elif nivel == 0 and (c in "!?…\n" or (
                c == "." and not (0 < i < len(s) - 1 and s[i - 1].isdigit() and s[i + 1].isdigit()))):
            inicio = i + 1
    return inicio
_RE_CORTE_OFERTA = re.compile(r"\s*(?:[,;:]|\s[-–—])\s*|\s(?=(?:e\s+)?(?:se|caso|qualquer\s+coisa)\b)", re.IGNORECASE)

# fecho de robô (o prompt já proíbe; quando escapa, sai aqui). Só a ÚLTIMA frase, e só se sobrar texto.
_RE_FECHO_ROBO = re.compile(
    r"(?:^|(?<=[.!?…\n]))\s*(?:"
    # 08/11 (rodada com a IA de verdade): oferta genérica no fim ("Quer que eu mexa em mais alguma coisa?", "Quer
    # que eu encaixe alguma delas?"). Pergunta de ação concreta ("Quer que eu crie o hábito?") continua.
    r"(?:quer\s+que\s+eu|posso)\b[^.!?…]*\b(?:mais\s+alguma\s+coisa|algo\s+mais|alguma\s+outra\s+coisa|"
    r"alguma\s+coisa|alguma\s+delas|algum\s+deles)\b[^.!?…]*\?|"
    r"se\s+quiser\b|se\s+precisar\b|qualquer\s+coisa,?\s+(?:[eé]\s+s[oó]|me)\b|"
    r"estou\s+aqui\b|t[oô]\s+aqui\s+(?:pra|para)\b|fico\s+[aà]\s+disposi[cç][aã]o|espero\s+ter\s+ajudado|"
    r"espero\s+que\s+(?:isso\s+)?ajude)[^.!?…]*[.!?…]*\s*$",
    re.IGNORECASE)


def _minutos(h: str, m: str | None) -> int | None:
    hora, minuto = int(h), int(m or 0)
    if hora > 23 or minuto > 59:
        return None
    return hora * 60 + minuto


def _hhmm(total: int) -> str:
    return f"{total // 60:02d}:{total % 60:02d}"


def _hora_de(valor) -> int | None:
    if not isinstance(valor, str):
        return None
    achou = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", valor)
    return _minutos(achou.group(1), achou.group(2)) if achou else None


def _valores(obj, chave_pai=""):
    """Todos os (chave, valor) folha de um resultado de ferramenta (dict/list aninhados)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _valores(v, str(k))
    elif isinstance(obj, list):
        for v in obj:
            yield from _valores(v, chave_pai)
    else:
        yield chave_pai, obj


def _gravou(chamadas) -> bool:
    for nome, _entrada, resultado in chamadas:
        if nome in _SO_LEITURA or nome.startswith(_PREFIXOS_SO_LEITURA):
            continue
        if isinstance(resultado, dict) and resultado.get("erro"):
            continue
        return True
    return False


def _frase_em_volta(texto: str, inicio: int, fim: int) -> str:
    a = max(texto.rfind(c, 0, inicio) for c in ".!?\n")
    candidatos = [i for i in (texto.find(c, fim) for c in ".!?\n") if i >= 0]
    return texto[a + 1: min(candidatos) if candidatos else len(texto)]


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn").lower()


def _primeira_palavra(texto: str) -> str:
    achou = re.match(r"\s*([^\W\d_]+)", texto or "")
    return _sem_acento(achou.group(1)) if achou else ""


def _abertura_solta(texto: str):
    """Match da abertura curta e separada do resto ("Beleza,", "Fechado.", "Show -") ou None."""
    m = _RE_ABERTURA_SOLTA.match(texto or "")
    return m if m and m.end() < len(texto.rstrip()) else None


def _mesma_abertura(texto: str, anterior: str | None) -> str | None:
    """A abertura solta de `texto` quando ela repete a da resposta anterior (ou a 1a palavra dela)."""
    if not anterior:
        return None
    m = _abertura_solta(texto)
    if not m:
        return None
    nova = _sem_acento(m.group(1))
    if nova not in _CONFIRMACOES:  # 3a rodada: "Amanhã:", "Dentista:", "Sexta," são conteúdo, não abertura
        return None
    m_ant = _abertura_solta(anterior)
    if nova in {_sem_acento(m_ant.group(1)) if m_ant else "", _primeira_palavra(anterior)}:
        return m.group(0)
    return None


def _consultou(chamadas) -> bool:
    return any(nome.startswith("consultar_") for nome, _e, _r in chamadas)


def revisar(texto: str, chamadas: list, agora: datetime | None = None, *,
            anterior: str | None = None, mensagem: str | None = None) -> list[dict]:
    """Confere `texto` contra `chamadas` [(ferramenta, entrada, resultado_que_a_IA_viu)] e o relógio.
    `anterior` = resposta anterior do assistente (abertura repetida); `mensagem` = o que o Alex mandou agora.
    Devolve os achados [{"codigo", "detalhe"}] - cada `detalhe` já diz o certo, pronto pra nota."""
    agora = agora or datetime.now()
    texto = texto or ""
    mensagem = mensagem if isinstance(mensagem, str) else ""
    achados: list[dict] = []

    # 1) disse que gravou sem ter gravado nada nesta resposta
    if not _gravou(chamadas):
        perguntou = mensagem.rstrip().endswith("?")
        for m in _RE_AFIRMOU.finditer(texto):
            antes = texto[max(0, m.start() - 25): m.start()]
            if _RE_NEGACAO_ANTES.search(antes[-20:]) or _RE_JA_ANTES.search(antes):
                continue
            if _RE_PARTICIPIO.search(m.group(1)) and (perguntou or _consultou(chamadas) or _RE_TA_ANTES.search(antes)):
                continue
            # 3a rodada: num reenvio "chama a ferramenta agora" duplicava a tarefa - confere antes
            achados.append({"codigo": "afirmou_sem_fazer", "detalhe": (
                f'tu escreveu "{m.group(1)}", mas nesta resposta nenhuma ferramenta gravou nada. Se a mensagem '
                "dele parece repetida, confere primeiro (consultar_agenda/consultar_tarefas): se já existe, diz "
                '"já tá: ..." e não grava de novo. Se não existe e ele pediu pra gravar, chama a ferramenta certa; '
                "se não dá, diz que ainda não ficou anotado.")})
            break

    # horas que as ferramentas calcularam nesta resposta
    saidas, arrumar, duracoes = set(), set(), []
    for _nome, _entrada, resultado in chamadas:
        for chave, valor in _valores(resultado):
            if chave == "sair_de_casa" and _hora_de(valor) is not None:
                saidas.add(_hora_de(valor))
            elif chave == "comecar_a_se_arrumar" and _hora_de(valor) is not None:
                arrumar.add(_hora_de(valor))
            elif isinstance(valor, (int, float)) and not isinstance(valor, bool) and (
                    "min" in chave or "duracao" in chave):
                duracoes.append(float(valor))

    # 2) hora de sair diferente da calculada / 3) hora de sair que já passou
    for m in _RE_SAIR.finditer(texto):
        dita = _minutos(m.group(1), m.group(2))
        if dita is None:
            continue
        if saidas and dita not in saidas and all(abs(dita - s) > 2 for s in saidas):
            certas = " ou ".join(_hhmm(s) for s in sorted(saidas))
            achados.append({"codigo": "saida_diferente_do_calculo", "detalhe": (
                f"tu escreveu sair às {_hhmm(dita)}, mas o trajeto calculado deu sair às {certas}. "
                "Usa a hora calculada (é a mesma do card).")})
            continue
        if _RE_PASSADO_ANTES.search(texto[max(0, m.start() - 25): m.start()]):
            continue
        frase = _frase_em_volta(texto, m.start(), m.end())
        if _RE_OUTRO_DIA.search(frase) or _RE_OUTRO_DIA.search(texto[:m.start()][-120:]):
            continue
        agora_min = agora.hour * 60 + agora.minute
        if dita < agora_min - 5 and agora_min - dita < 12 * 60 and not saidas:
            achados.append({"codigo": "saida_no_passado", "detalhe": (
                f"tu mandou sair às {_hhmm(dita)}, mas agora já são {_hhmm(agora_min)}. Se é pra hoje, a saída "
                "tem que ser daqui pra frente (ou diz que já passou da hora e o que dá pra fazer agora).")})

    for m in _RE_ARRUMAR.finditer(texto):
        dita = _minutos(m.group(1), m.group(2))
        if dita is not None and arrumar and all(abs(dita - a) > 2 for a in arrumar):
            certas = " ou ".join(_hhmm(a) for a in sorted(arrumar))
            achados.append({"codigo": "arrumar_diferente_do_calculo", "detalhe": (
                f"tu escreveu começar a se arrumar às {_hhmm(dita)}, mas o cálculo deu {certas}.")})

    # 4) conta de intervalo: "das 14h às 16h (3 h)"
    for m in _RE_INTERVALO.finditer(texto):
        ini, fim = _minutos(m.group(1), m.group(2)), _minutos(m.group(3), m.group(4))
        if ini is None or fim is None:
            continue
        real = (fim - ini) % (24 * 60)
        n, unidade, extra = int(m.group(5)), m.group(6).lower(), int(m.group(7) or 0)
        dito = n * 60 + extra if unidade.startswith("h") else n
        if real and abs(dito - real) > 5:
            achados.append({"codigo": "conta_de_intervalo", "detalhe": (
                f"das {_hhmm(ini)} às {_hhmm(fim)} são {real // 60} h"
                + (f" {real % 60} min" if real % 60 else "") + f", não o que tu escreveu (\"{m.group(0).strip()}\").")})

    # 5) tempo de trajeto diferente do que a rota deu (só quando teve rota nesta resposta)
    if any(nome == "estimar_trajeto" for nome, _e, _r in chamadas) and duracoes:
        for m in _RE_TRAJETO.finditer(texto):
            numero = int(m.group(1))
            trecho = _sem_acento(m.group(0))
            dito = numero * 60 + int(m.group(2) or 0) if re.search(r"\d\s*h", trecho) else numero
            if dito and all(abs(dito - d) > max(5, 0.2 * d) for d in duracoes):
                perto = min(duracoes, key=lambda d: abs(d - dito))
                achados.append({"codigo": "trajeto_diferente", "detalhe": (
                    f"tu escreveu {m.group(0).strip()!r}, mas a rota calculada deu {round(perto)} min.")})
                break

    # 6) falou do sistema (o Alex não perguntou do app): fala como gente
    sistema = _RE_SISTEMA.search(texto)
    if sistema and not _RE_FALA_DO_SISTEMA.search(mensagem):
        achados.append({"codigo": "falou_do_sistema", "detalhe": (
            f'tu escreveu "{sistema.group(0)}": não fala do sistema (card, ferramenta, "o painel calculou", nome de '
            'função). Diz o resultado como gente ("sai 19h40", "dá 25 min até lá").')})

    # 7) "você" com o Alex: sempre "tu"
    if not _RE_PEDIU_RECADO.search(mensagem):
        alvo = _RE_ENTRE_ASPAS.sub(" ", texto)
        recado = _RE_RECADO_DEPOIS.search(alvo)
        if recado:  # "Manda pra ela: ..." - o resto é o recado (na dúvida, não acusa)
            alvo = alvo[:recado.end()]
        voce = _RE_VOCE.search(alvo)
        if voce:
            achados.append({"codigo": "falou_voce", "detalhe": (
                f'tu escreveu "{voce.group(0)}": com o Alex é sempre "tu" (tu, te, teu, tua, contigo), nunca '
                "você/seu/sua.")})

    # 8) começou igual à resposta anterior com verbo de confirmação colado ("Anotei o X" duas vezes seguidas).
    # Abertura solta repetida ("Beleza, ...") não volta pro modelo: sai em limpar().
    primeira = _primeira_palavra(texto)
    if (anterior and primeira in _CONFIRMACOES and primeira == _primeira_palavra(anterior)
            and len(texto.split()) >= 4 and not _abertura_solta(texto)):
        achados.append({"codigo": "abertura_repetida", "detalhe": (
            f'tu começou com "{primeira}" de novo, igual à resposta anterior. Começa de outro jeito, direto pelo '
            'que ficou (ex.: "Dentista sexta 10h.").')})
    return achados


def nota_de_correcao(achados: list[dict]) -> str:
    """O que vai pro modelo refazer a resposta (uma vez)."""
    linhas = "\n".join(f"- {a['detalhe']}" for a in achados)
    so_texto = all(a["codigo"] != "afirmou_sem_fazer" for a in achados)
    return (
        "[revisão automática do painel - o Alex NÃO vê esta mensagem]\n"
        "A resposta acima tem erro de conta, de fato ou de jeito de falar:\n" + linhas + "\n"
        + ("Não chama ferramenta de novo (o que tinha que ser feito já foi). " if so_texto else "")
        + "Escreve a resposta inteira de novo, corrigida, no mesmo tom e tamanho, sem mencionar esta revisão."
    )


def limpar_fecho(texto: str) -> str:
    """Tira a última frase se ela for fecho de robô ("Se quiser, ...", "Espero ter ajudado") e sobrar texto;
    e a oferta ("é só falar", "me fala que eu ajusto") em qualquer ponto da última frase."""
    if not texto:
        return texto
    m = _RE_FECHO_ROBO.search(texto)
    if m:
        resto = texto[:m.start()].rstrip()
        if len(resto) >= 15:
            texto = resto
    return _cortar_oferta(texto)


_RE_SUBORDINADA = re.compile(
    r"^(?:e\s+|mas\s+)?(?:se|caso|como|quando|j[aá]\s+que|porque|pois|assim\s+que|enquanto|pra|para|embora)\b",
    re.IGNORECASE)


_RE_CONTINUA_SUBORDINADA = re.compile(r"(?:que|onde|quando|cujo|cuja|o\s+que|a\s+qual|o\s+qual)\b", re.IGNORECASE)


def _so_subordinada(trecho: str) -> bool:
    """O que sobrou do corte é só a oração que dependia da oferta: começa com se/como/quando/já que... e o que vem
    depois de cada vírgula (fora de parênteses) também é subordinado ("Se era do Venvanse, que era às 7h30").
    Oração principal depois da vírgula fica: "Como tu pediu, marquei às 9h"; "Se chover, leva guarda-chuva"."""
    if not _RE_SUBORDINADA.match(trecho):
        return False
    partes = [p.strip() for p in re.sub(r"\([^)]*\)", "", trecho).split(",")]
    return all(_RE_CONTINUA_SUBORDINADA.match(p) for p in partes[1:] if p)


# "então" só depois de vírgula ("fica pra amanhã então." é o jeito dele de fechar, não sobra); "aí"/"daí" ficam
# ("o carro tá aí")
_RE_CONECTOR_FINAL = re.compile(
    r"(?:(?:^|,\s*)ent[aã]o|(?:^|(?<=[\s,;]))(?:e|mas|pois|porque|que|ou|s[oó]\s+que))\s*$", re.IGNORECASE)


def _cortar_oferta(texto: str) -> str:
    corpo = texto.rstrip()
    sem_ponto = corpo.rstrip(".!?… ")
    # 3a rodada: ponto entre dígitos ("R$ 1.250") não separa frase
    inicio = _inicio_ultima_frase(sem_ponto)
    frase = corpo[inicio:]
    oferta = _RE_OFERTA.search(frase)
    if not oferta:
        return texto
    # pontos de corte antes da oferta (vírgula, ponto e vírgula, travessão, " e se", " se", " qualquer coisa"),
    # do mais perto pro mais longe: vale o mais longe enquanto o pedaço que sobra ainda é oferta/condição
    cortes = [(c.start(), c.end()) for c in _RE_CORTE_OFERTA.finditer(frase) if c.start() < oferta.start()]
    cortes.append((0, 0))
    escolhido = None
    for ini_sep, fim_sep in sorted(cortes, reverse=True):
        if not _RE_INICIO_OFERTA.match(frase[fim_sep:].lstrip()):
            break
        escolhido = ini_sep
    if escolhido is None:
        return texto
    antes = texto[:inicio].rstrip()
    resto_frase = frase[:escolhido].strip().rstrip(",;:-–— ")
    # 4a rodada: "continua onde estava, então, se quiser eu..." sobrava "continua onde estava, então." -
    # conector solto no fim (então/e/mas/aí/porque/que...) sai junto com a oferta
    while True:
        sem_conector = _RE_CONECTOR_FINAL.sub("", resto_frase).rstrip(",;:-–— ")
        if sem_conector == resto_frase:
            break
        resto_frase = sem_conector
    # 08/11 (rodada com a IA de verdade): sobrar só a oração de condição/causa ("Como cai num domingo.",
    # "Se for pra alguma coisa específica (...).") é pior que tirar a frase inteira
    if not resto_frase or _so_subordinada(resto_frase):  # a frase inteira era oferta
        return antes if len(antes) >= 6 else texto
    final = "." if not resto_frase.endswith((".", "!", "?", "…")) else ""
    novo = ((antes + " ") if antes else "") + resto_frase + final
    return novo if len(novo.strip()) >= 6 else texto


def limpar_abertura(texto: str, anterior: str | None) -> str:
    """Tira a abertura solta ("Beleza,", "Fechado.") quando ela repete a da resposta anterior."""
    if not texto:
        return texto
    repetida = _mesma_abertura(texto, anterior)
    if not repetida:
        return texto
    resto = texto[len(repetida):].lstrip()
    if len(resto) < 15:
        return texto
    return resto[0].upper() + resto[1:]


# 08/11 (rodada com a IA de verdade): "agendado pras 07h31" - o jeito dele (e o da voz) é "7h31"
_RE_HORA_ZERO = re.compile(r"(?<![\d:/.,])0(\d)h(\d{2})?\b")
# "ta"/"Ta" solto sem acento (o prompt é escrito sem acento e o modelo copia): "ta quase limpo" -> "tá"
_RE_TA = re.compile(r"(?<![\w'-])([Tt])a(?![\w'-])")
# reenvio: "Não precisei criar de novo, então não duplicou nada." é falar do sistema - sai a frase inteira
_RE_FRASE_DUPLICOU = re.compile(
    r"(?:^|(?<=[.!?…]))\s*[^.!?…]*\b(?:n[aã]o\s+precisei\s+(?:criar|anotar|marcar)\s+de\s+novo|"
    r"n[aã]o\s+duplic(?:ou|uei|ar)|sem\s+duplicar)\b[^.!?…]*[.!?…]?", re.IGNORECASE)


def limpar(texto: str, anterior: str | None = None) -> str:
    """O que sai no código, sem nova chamada: abertura repetida, fecho/oferta de robô, "07h31" -> "7h31",
    "ta" -> "tá" e a frase de "não duplicou"."""
    texto = limpar_fecho(limpar_abertura(texto, anterior))
    if not texto:
        return texto
    sem_dup = _RE_FRASE_DUPLICOU.sub("", texto).strip()
    if len(sem_dup) >= 15:
        texto = sem_dup
    texto = _RE_HORA_ZERO.sub(lambda m: f"{m.group(1)}h{m.group(2) or ''}", texto)
    return _RE_TA.sub(lambda m: m.group(1) + "á", texto)
