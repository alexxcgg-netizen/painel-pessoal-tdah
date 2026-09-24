# assistente/regras.py — faixa P4 (Fase 7): motor PURO das regras em
# portugues que o Alex cria no chat/captura ("me avisa se gastar mais de 300
# com mercado na semana", "todo dia as 18h me lembra de tomar o remedio").
#
# Este arquivo faz 3 coisas, nesta ordem de preferencia (mais barato primeiro):
#   1. interpretar_regra_local(texto): parser determinístico (regex) pros
#      formatos mais comuns - sem gastar IA nenhuma.
#   2. interpretar_regra(texto): tenta o parser local; se nao bater, chama
#      ia.core.chamar_ia("interpretar_regra", ...) com schema JSON. Nunca
#      levanta - qualquer falha (parser, IA, validacao) vira
#      {"ok": False, "erro": "..."}.
#   3. normalizar_regra(bruto): valida/normaliza o dict (local OU da IA) pro
#      formato canonico {gatilho, condicao, acao, texto} - a MESMA validacao
#      roda nos dois casos, entao um dict aceito aqui e sempre seguro pros
#      avaliadores abaixo.
#
# avaliar_regra(conn, regra, agora, ultima_vez) e os avaliadores por gatilho
# sao puros o bastante pra testar sem mockar nada alem do `conn` (SQLite de
# teste) - `agora` e sempre injetado pelo chamador (nunca datetime.now()
# aqui dentro, ver docs/agentes/fase7-assistente.md).
#
# "Fora do escopo" (docs/agentes/fase7-assistente.md): regra sobre vida
# amorosa/relacionamento nunca e criada - fora_de_escopo() filtra por
# palavra-chave ANTES de gastar uma chamada de IA, e normalizar_regra()
# recusa de novo (defesa em profundidade, cobre tambem regra digitada direto
# via rotas/p4_regras.py:confirmar).
from __future__ import annotations

import logging
import re
import sqlite3
import unicodedata
from datetime import date, datetime, timedelta

from ia import core

log = logging.getLogger(__name__)

try:
    import vida
except ImportError:  # so pra deixar os testes puros do parser/schema rodarem
    vida = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Vocabulario valido do contrato {gatilho, condicao, acao, texto}
# ---------------------------------------------------------------------------

GATILHOS_VALIDOS = {
    "horario", "gasto_categoria", "habito_nao_feito_ate", "tarefa_vencida", "sinal_iphone",
}
_TIPOS_HORARIO = {"diario", "semanal", "data"}
_PERIODOS = {"semana", "mes", "dia"}
_TIPOS_SINAL = {"cheguei", "sai", "acordei", "dormir", "carregando"}
_NOME_DIA_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]

FUNCAO_IA_INTERPRETAR_REGRA = "interpretar_regra"


# ---------------------------------------------------------------------------
# Fora de escopo (vida amorosa/relacionamento nunca vira regra - decisao do
# Alex, ver docs/agentes/fase7-assistente.md)
# ---------------------------------------------------------------------------

_PALAVRAS_FORA_DE_ESCOPO = (
    "namorad", "namoro", "esposa", "esposo", "marido", "noivad", "noivo", "noiva",
    "casamento", "casad", "relacionamento", "romance", "romantic", "paquera",
    "paquerar", "affair", "amante", "crush", "ciume", "flerte", "flertar",
    "traicao", "trair", "separacao", "divorcio", "ex-namorad", "meu ex",
    "minha ex", "ficante", "ficar com",
)


def _sem_acento(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def fora_de_escopo(texto: str) -> bool:
    """True se o texto fala de vida amorosa/relacionamento - essas regras
    nunca sao criadas (nem local, nem via IA)."""
    t = _sem_acento(texto)
    return any(p in t for p in _PALAVRAS_FORA_DE_ESCOPO)


# ---------------------------------------------------------------------------
# Parser local (sem IA) - so os formatos simples e bem determinados
# ---------------------------------------------------------------------------

_DIAS_SEMANA_TXT = {
    "segunda": 0, "segunda-feira": 0,
    "terca": 1, "terça": 1, "terca-feira": 1, "terça-feira": 1,
    "quarta": 2, "quarta-feira": 2,
    "quinta": 3, "quinta-feira": 3,
    "sexta": 4, "sexta-feira": 4,
    "sabado": 5, "sábado": 5, "sabado-feira": 5,
    "domingo": 6,
}

_RE_DIARIO = re.compile(
    r"^\s*todo(?:s)?\s+(?:os\s+)?dias?\s+(?:às|as|a)\s+(\d{1,2})(?:[:h](\d{2}))?h?\s+"
    r"(?:me\s+)?lembr\w*\s+de\s+(.+?)\s*[.!]?\s*$",
    re.IGNORECASE,
)

_RE_SEMANAL = re.compile(
    # "toda segunda"/"todas as sextas"/"todo sábado"/"todo domingo" - o artigo
    # (feminino p/ segunda..sexta-feira, masculino p/ sábado/domingo) varia,
    # entao aceita "tod[ao](s)?" solto em vez de exigir concordancia certa.
    r"^\s*tod[ao](?:s)?\s+(?:a|as|o|os)?\s*"
    r"(segunda(?:-feira)?|ter[cç]a(?:-feira)?|quarta(?:-feira)?|quinta(?:-feira)?|"
    r"sexta(?:-feira)?|s[aá]bado|domingo)\s+(?:às|as|a)\s+(\d{1,2})(?:[:h](\d{2}))?h?\s+"
    r"(?:me\s+)?lembr\w*\s+de\s+(.+?)\s*[.!]?\s*$",
    re.IGNORECASE,
)

_RE_GASTO = re.compile(
    r"^\s*me\s+avisa(?:r)?\s+se\s+(?:eu\s+)?gast(?:ar|ei|o)\s+mais\s+de\s+"
    r"(?:r\$\s*)?(\d+(?:[.,]\d{1,2})?)\s+"
    r"(?:com|em|no|na)\s+([a-zà-úçãõ]+(?:\s+[a-zà-úçãõ]+)*?)"
    r"(?:\s+(?:na|nessa|essa|por)\s+semana"
    r"|\s+(?:no|nesse|esse|por)\s+m[eê]s"
    r"|\s+hoje)?"
    r"\s*[.!?]?\s*$",
    re.IGNORECASE,
)


def _valor_para_float(bruto: str) -> float:
    return float(bruto.replace(",", "."))


def interpretar_regra_local(texto: str) -> dict | None:
    """Parser deterministico (regex), sem IA nenhuma, pros formatos mais
    comuns: lembrete diario/semanal com hora fixa, e limite de gasto por
    categoria/periodo. Devolve o dict BRUTO (ainda vai passar por
    normalizar_regra) ou None quando o texto nao bate em nenhum formato
    simples - nesse caso quem chama cai pra IA."""
    texto = (texto or "").strip()
    if not texto:
        return None

    m = _RE_DIARIO.match(texto)
    if m:
        hora = f"{int(m.group(1)):02d}:{int(m.group(2) or 0):02d}"
        mensagem = m.group(3).strip()
        return {
            "gatilho": "horario",
            "condicao": {"tipo": "diario", "hora": hora},
            "acao": {"mensagem": mensagem},
            "texto": texto,
        }

    m = _RE_SEMANAL.match(texto)
    if m:
        dia_txt = _sem_acento(m.group(1)).replace("á", "a")
        dia_semana = _DIAS_SEMANA_TXT.get(dia_txt)
        if dia_semana is None:
            return None
        hora = f"{int(m.group(2)):02d}:{int(m.group(3) or 0):02d}"
        mensagem = m.group(4).strip()
        return {
            "gatilho": "horario",
            "condicao": {"tipo": "semanal", "dia_semana": dia_semana, "hora": hora},
            "acao": {"mensagem": mensagem},
            "texto": texto,
        }

    m = _RE_GASTO.match(texto)
    if m:
        valor = _valor_para_float(m.group(1))
        categoria = m.group(2).strip()
        if re.search(r"\bm[eê]s\b|\bsemana\b|\bhoje\b", categoria, re.IGNORECASE):
            # Frase com o periodo ANTES da categoria (ex: "...no mes com
            # farmacia") - fora do formato simples suportado local, cai pra IA.
            return None
        if "semana" in texto.lower():
            periodo = "semana"
        elif re.search(r"m[eê]s", texto, re.IGNORECASE):
            periodo = "mes"
        elif "hoje" in texto.lower():
            periodo = "dia"
        else:
            periodo = "mes"
        return {
            "gatilho": "gasto_categoria",
            "condicao": {"categoria": categoria, "periodo": periodo, "valor_limite": valor},
            "acao": {},
            "texto": texto,
        }

    return None


# ---------------------------------------------------------------------------
# Validacao/normalizacao (roda tanto no resultado do parser local quanto no
# JSON que a IA devolveu - so existe UM caminho de validacao)
# ---------------------------------------------------------------------------

_RE_HORA_NORM = re.compile(r"^\s*([01]?\d|2[0-3])\s*[:h]\s*([0-5]\d)?\s*h?\s*$", re.IGNORECASE)


def _validar_hora(hora) -> str:
    """Aceita 'HH:MM', 'HHhMM' e 'HHh' (sem minuto = :00); qualquer outra
    coisa (AM/PM, hora fora de 0-23, minuto fora de 0-59...) e invalida."""
    if not isinstance(hora, str) or not hora.strip():
        raise ValueError(f"hora invalida: {hora!r} (use 'HH:MM')")
    m = _RE_HORA_NORM.match(hora)
    if not m:
        raise ValueError(f"hora invalida: {hora!r} (use 'HH:MM')")
    h = int(m.group(1))
    minuto = int(m.group(2)) if m.group(2) else 0
    if not (0 <= h <= 23 and 0 <= minuto <= 59):
        raise ValueError(f"hora fora do intervalo: {hora!r}")
    return f"{h:02d}:{minuto:02d}"


def normalizar_regra(bruto) -> dict:
    """Valida e normaliza um dict {gatilho, condicao, acao, texto} (vindo do
    parser local OU da IA). Levanta ValueError com mensagem em portugues
    pronta pra mostrar/logar quando algo estiver invalido - nunca devolve
    dado parcialmente normalizado."""
    if not isinstance(bruto, dict):
        raise ValueError("regra precisa ser um objeto")

    gatilho = bruto.get("gatilho")
    if gatilho not in GATILHOS_VALIDOS:
        raise ValueError(f"gatilho invalido: {gatilho!r}")

    condicao = bruto.get("condicao")
    if not isinstance(condicao, dict):
        raise ValueError("condicao precisa ser um objeto")

    acao = bruto.get("acao")
    if acao is None:
        acao = {}
    if not isinstance(acao, dict):
        raise ValueError("acao precisa ser um objeto")

    texto = bruto.get("texto")
    if not isinstance(texto, str) or not texto.strip():
        raise ValueError("texto vazio")
    texto = texto.strip()[:400]

    if fora_de_escopo(texto):
        raise ValueError(
            "Isso e sobre vida amorosa/relacionamento - o assistente nao cria regra pra isso."
        )

    condicao_norm: dict = {}
    acao_norm: dict = {}

    if gatilho == "horario":
        tipo = condicao.get("tipo", "diario")
        if tipo not in _TIPOS_HORARIO:
            raise ValueError(f"tipo de horario invalido: {tipo!r}")
        condicao_norm["tipo"] = tipo
        condicao_norm["hora"] = _validar_hora(condicao.get("hora"))
        if tipo == "semanal":
            dia = condicao.get("dia_semana")
            try:
                dia = int(dia)
            except (TypeError, ValueError):
                raise ValueError(f"dia_semana invalido: {condicao.get('dia_semana')!r}") from None
            if not 0 <= dia <= 6:
                raise ValueError(f"dia_semana fora do intervalo 0-6: {dia}")
            condicao_norm["dia_semana"] = dia
        if tipo == "data":
            data_txt = condicao.get("data")
            try:
                datetime.strptime(str(data_txt), "%Y-%m-%d")
            except (TypeError, ValueError):
                raise ValueError(f"data invalida: {data_txt!r} (use AAAA-MM-DD)") from None
            condicao_norm["data"] = str(data_txt)
        mensagem = acao.get("mensagem") or texto
        acao_norm["mensagem"] = str(mensagem).strip()[:400]

    elif gatilho == "gasto_categoria":
        categoria = condicao.get("categoria")
        if not isinstance(categoria, str) or not categoria.strip():
            raise ValueError("categoria vazia")
        condicao_norm["categoria"] = categoria.strip().lower()
        periodo = condicao.get("periodo", "mes")
        if periodo not in _PERIODOS:
            raise ValueError(f"periodo invalido: {periodo!r}")
        condicao_norm["periodo"] = periodo
        try:
            valor = float(condicao.get("valor_limite"))
        except (TypeError, ValueError):
            raise ValueError(f"valor_limite invalido: {condicao.get('valor_limite')!r}") from None
        if not (valor > 0):
            raise ValueError("valor_limite precisa ser maior que zero")
        condicao_norm["valor_limite"] = round(valor, 2)

    elif gatilho == "habito_nao_feito_ate":
        nome = condicao.get("habito_nome") or condicao.get("habito")
        if not isinstance(nome, str) or not nome.strip():
            raise ValueError("habito_nome vazio")
        condicao_norm["habito_nome"] = nome.strip()
        if condicao.get("habito_id") is not None:
            try:
                condicao_norm["habito_id"] = int(condicao["habito_id"])
            except (TypeError, ValueError):
                raise ValueError(f"habito_id invalido: {condicao.get('habito_id')!r}") from None
        if condicao.get("hora") not in (None, ""):
            condicao_norm["hora"] = _validar_hora(condicao.get("hora"))

    elif gatilho == "tarefa_vencida":
        pass  # condicao vazia de proposito - "qualquer tarefa vencida"

    elif gatilho == "sinal_iphone":
        tipo_sinal = condicao.get("tipo")
        if tipo_sinal not in _TIPOS_SINAL:
            raise ValueError(f"tipo de sinal invalido: {tipo_sinal!r}")
        condicao_norm["tipo"] = tipo_sinal
        lugar = condicao.get("lugar")
        if lugar not in (None, ""):
            condicao_norm["lugar"] = str(lugar).strip()
        mensagem = acao.get("mensagem")
        if mensagem:
            acao_norm["mensagem"] = str(mensagem).strip()[:400]

    return {"gatilho": gatilho, "condicao": condicao_norm, "acao": acao_norm, "texto": texto}


# ---------------------------------------------------------------------------
# Interpretacao (local primeiro, IA so pro resto)
# ---------------------------------------------------------------------------

SCHEMA_INTERPRETAR_REGRA = {
    "type": "object",
    "required": ["gatilho", "condicao", "acao", "texto"],
    "additionalProperties": False,
    "properties": {
        "gatilho": {"type": "string", "enum": sorted(GATILHOS_VALIDOS)},
        "condicao": {"type": "object"},
        "acao": {"type": "object"},
        "texto": {"type": "string", "minLength": 1, "maxLength": 400},
    },
}

_SISTEMA_INTERPRETAR_REGRA = (
    "Voce transforma um pedido em portugues do Alex numa regra estruturada do "
    "assistente do painel pessoal dele (TDAH). Devolva SOMENTE um objeto JSON "
    "com os campos gatilho, condicao, acao e texto (texto = o pedido original, "
    "ate 400 caracteres).\n\n"
    "gatilho e um destes 5 valores, cada um com o formato de condicao/acao:\n"
    "- horario: condicao = {tipo: 'diario'|'semanal'|'data', hora: 'HH:MM', "
    "dia_semana (0=segunda..6=domingo, so no tipo semanal), data ('AAAA-MM-DD', "
    "so no tipo data)}. acao = {mensagem: texto curto do lembrete}.\n"
    "- gasto_categoria: condicao = {categoria: string, periodo: 'semana'|'mes'|'dia', "
    "valor_limite: numero}. acao = {}.\n"
    "- habito_nao_feito_ate: condicao = {habito_nome: string, hora: 'HH:MM' opcional}. "
    "acao = {}.\n"
    "- tarefa_vencida: condicao = {}. acao = {}.\n"
    "- sinal_iphone: condicao = {tipo: 'cheguei'|'sai'|'acordei'|'dormir'|'carregando', "
    "lugar: string opcional}. acao = {mensagem opcional}.\n\n"
    "Escolha o gatilho que melhor combina com o pedido. Nunca invente campo fora "
    "desse formato."
)


def interpretar_regra(texto: str) -> dict:
    """Ponto de entrada da interpretacao: parser local primeiro (sem custo),
    IA so se o local nao bater. Nunca levanta - qualquer problema (texto
    vazio, fora de escopo, parser/IA/validacao) vira
    {"ok": False, "erro": "..."}. Devolve sempre este formato:
    {"ok": bool, "regra": dict|None, "fonte": "local"|"ia"|None, "erro": str|None}
    """
    texto_original = (texto or "").strip()
    if not texto_original:
        return {"ok": False, "regra": None, "fonte": None, "erro": "texto vazio"}

    if fora_de_escopo(texto_original):
        return {
            "ok": False, "regra": None, "fonte": None,
            "erro": "Isso e sobre vida amorosa/relacionamento - o assistente nao mexe nisso.",
        }

    bruto = interpretar_regra_local(texto_original)
    fonte = "local"
    if bruto is None:
        fonte = "ia"
        resp = core.chamar_ia(
            FUNCAO_IA_INTERPRETAR_REGRA,
            [{"role": "user", "content": texto_original}],
            sistema=_SISTEMA_INTERPRETAR_REGRA,
            schema=SCHEMA_INTERPRETAR_REGRA,
        )
        if not resp.ok:
            return {"ok": False, "regra": None, "fonte": "ia", "erro": resp.erro or "IA nao respondeu"}
        bruto = resp.dados

    try:
        regra = normalizar_regra(bruto)
    except ValueError as e:
        log.warning("p4_regra: interpretacao (%s) produziu regra invalida: %s", fonte, e)
        return {"ok": False, "regra": None, "fonte": fonte, "erro": str(e)}
    return {"ok": True, "regra": regra, "fonte": fonte, "erro": None}


# ---------------------------------------------------------------------------
# Resumo em portugues (confirmacao + corpo do aviso)
# ---------------------------------------------------------------------------

_NOME_PERIODO = {"semana": "por semana", "mes": "por mes", "dia": "por dia"}
_NOME_SINAL = {
    "cheguei": "voce chegar", "sai": "voce sair", "acordei": "voce acordar",
    "dormir": "voce dormir", "carregando": "seu iPhone comecar a carregar",
}


def montar_resumo_regra(regra: dict) -> str:
    """Frase curta em portugues pro card de confirmacao (e pro resumo_texto
    que acompanha ele) - descreve o que a regra vai fazer."""
    gatilho = regra.get("gatilho")
    condicao = regra.get("condicao") or {}
    acao = regra.get("acao") or {}

    if gatilho == "horario":
        tipo = condicao.get("tipo", "diario")
        hora = condicao.get("hora", "")
        mensagem = acao.get("mensagem") or regra.get("texto", "")
        if tipo == "diario":
            quando = f"todo dia às {hora}"
        elif tipo == "semanal":
            dia = _NOME_DIA_SEMANA[condicao.get("dia_semana", 0)]
            quando = f"toda {dia} às {hora}"
        else:
            quando = f"em {condicao.get('data', '?')} às {hora}"
        return f'Vou te lembrar {quando}: "{mensagem}".'

    if gatilho == "gasto_categoria":
        categoria = condicao.get("categoria", "?")
        limite = condicao.get("valor_limite", 0)
        periodo = _NOME_PERIODO.get(condicao.get("periodo", "mes"), "por mes")
        return (
            f'Vou te avisar quando o gasto em "{categoria}" passar de '
            f"R$ {limite:.2f} {periodo}."
        )

    if gatilho == "habito_nao_feito_ate":
        nome = condicao.get("habito_nome", "?")
        hora = condicao.get("hora")
        if hora:
            return f'Vou te avisar se "{nome}" ainda nao estiver marcado até as {hora}.'
        return f'Vou te avisar quando "{nome}" passar do horário e ainda nao estiver marcado.'

    if gatilho == "tarefa_vencida":
        return "Vou te avisar quando alguma tarefa vencer."

    if gatilho == "sinal_iphone":
        tipo = condicao.get("tipo", "?")
        lugar = condicao.get("lugar")
        base = _NOME_SINAL.get(tipo, tipo)
        if lugar:
            return f"Vou te avisar quando {base} em {lugar}."
        return f"Vou te avisar quando {base}."

    return "Regra criada."


# ---------------------------------------------------------------------------
# Avaliacao (motor do tick - assistente/gatilhos/p4_regras.py chama isto)
# ---------------------------------------------------------------------------

def periodo_intervalo(hoje: date, periodo: str) -> tuple[date, date]:
    """Devolve (inicio, fim) INCLUSIVE do periodo que contem `hoje`."""
    if periodo == "dia":
        return hoje, hoje
    if periodo == "semana":
        inicio = hoje - timedelta(days=hoje.weekday())  # segunda
        return inicio, inicio + timedelta(days=6)
    if periodo == "mes":
        inicio = hoje.replace(day=1)
        if hoje.month == 12:
            prox = hoje.replace(year=hoje.year + 1, month=1, day=1)
        else:
            prox = hoje.replace(month=hoje.month + 1, day=1)
        return inicio, prox - timedelta(days=1)
    raise ValueError(f"periodo desconhecido: {periodo!r}")


def total_gasto_periodo(conn, categoria: str, inicio: date, fim: date) -> float:
    """Soma dos gastos REAIS (tipo='real') de uma categoria entre inicio e
    fim (inclusive). Consulta direta em `expenses` (mesma tabela de
    db.gasto_mes_por_categoria, que so cobre mes calendario - aqui precisa
    tambem de semana/dia, por isso nao reusa aquela funcao)."""
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses "
        "WHERE tipo = 'real' AND lower(category) = lower(?) "
        "AND date(created_at) BETWEEN date(?) AND date(?)",
        (categoria, inicio.isoformat(), fim.isoformat()),
    ).fetchone()
    return float(row["total"] or 0.0)


def avaliar_gasto_categoria(conn, condicao: dict, agora: datetime,
                             ultima_vez: datetime | None) -> tuple[bool, float]:
    periodo = condicao.get("periodo", "mes")
    inicio, fim = periodo_intervalo(agora.date(), periodo)
    total = total_gasto_periodo(conn, condicao["categoria"], inicio, fim)
    ja_disparou_no_periodo = ultima_vez is not None and inicio <= ultima_vez.date() <= fim
    deve = total > float(condicao["valor_limite"]) and not ja_disparou_no_periodo
    return deve, total


def avaliar_horario(condicao: dict, agora: datetime, ultima_vez: datetime | None) -> bool:
    tipo = condicao.get("tipo", "diario")
    h, m = (int(p) for p in condicao["hora"].split(":"))
    alvo_hoje = agora.replace(hour=h, minute=m, second=0, microsecond=0)
    if agora < alvo_hoje:
        return False
    if tipo == "semanal" and agora.weekday() != int(condicao["dia_semana"]):
        return False
    if tipo == "data":
        data_alvo = datetime.strptime(condicao["data"], "%Y-%m-%d").date()
        if agora.date() != data_alvo:
            return False
    if ultima_vez is not None and ultima_vez.date() == agora.date():
        return False
    return True


def _buscar_habito(conn, condicao: dict) -> dict | None:
    import db  # import tardio: so precisa de banco de verdade em producao/teste com db

    habito_id = condicao.get("habito_id")
    if habito_id is not None:
        habito = db.get_habito(conn, habito_id)
        if habito:
            return habito
    nome = condicao.get("habito_nome")
    if nome:
        return db.buscar_habito_por_nome(conn, nome)
    return None


def avaliar_habito_nao_feito_ate(conn, condicao: dict, agora: datetime,
                                  ultima_vez: datetime | None) -> tuple[bool, dict | None]:
    import db  # import tardio (ver _buscar_habito)

    habito = _buscar_habito(conn, condicao)
    if habito is None:
        return False, None
    if ultima_vez is not None and ultima_vez.date() == agora.date():
        return False, habito

    hoje_iso = agora.date().isoformat()
    marcado_hoje = db.habito_marcado(conn, hoje_iso, habito["id"])
    if marcado_hoje:
        return False, habito

    hora_limite = condicao.get("hora")
    if hora_limite:
        h, m = (int(p) for p in hora_limite.split(":"))
        limite = agora.replace(hour=h, minute=m, second=0, microsecond=0)
        return agora >= limite, habito

    # Sem hora explicita na regra: usa o horario do proprio habito (mesma
    # regra de "passou batido" da proatividade, vida.habito_passou_batido).
    if vida is None:
        return False, habito
    vezes = 0
    if habito.get("frequencia_tipo") == "n_vezes_semana":
        inicio_semana, fim_semana = periodo_intervalo(agora.date(), "semana")
        vezes = len(db.marcacoes_habito_no_periodo(
            conn, habito["id"], inicio_semana.isoformat(), fim_semana.isoformat()))
    return vida.habito_passou_batido(habito, agora, marcado_hoje, vezes), habito


def avaliar_tarefa_vencida(conn, condicao: dict, agora: datetime,
                            ultima_vez: datetime | None) -> tuple[bool, list[dict]]:
    if ultima_vez is not None and ultima_vez.date() == agora.date():
        return False, []
    agora_iso = agora.strftime("%Y-%m-%d %H:%M:%S")
    hoje_iso = agora.date().isoformat()
    linhas = conn.execute(
        "SELECT id, title, due_at, due_date FROM tasks WHERE completed_at IS NULL "
        "AND ((due_at IS NOT NULL AND due_at != '' AND due_at < ?) "
        "OR (due_date IS NOT NULL AND due_date != '' AND due_date < ?))",
        (agora_iso, hoje_iso),
    ).fetchall()
    tarefas = [dict(r) for r in linhas]
    return bool(tarefas), tarefas


def _avaliar_sinal_iphone_fallback(conn, tipo: str, lugar: str | None,
                                    desde: datetime) -> tuple[bool, dict | None]:
    """Consulta direta em `sinais` (migracoes/202609241240_p7_sinais.sql),
    usada so quando assistente.sinais (faixa P7) nao pode ser importado -
    DEFENSIVO: essa faixa roda em paralelo e a tabela pode nao existir ainda.
    Sem tabela = sem sinal, nunca quebra o tick."""
    query = "SELECT id, tipo, lugar, quando FROM sinais WHERE tipo = ? AND quando >= ?"
    params: list = [tipo, desde.isoformat()]
    if lugar:
        query += " AND lugar = ?"
        params.append(lugar)
    query += " ORDER BY quando DESC, id DESC LIMIT 1"
    try:
        linha = conn.execute(query, params).fetchone()
    except sqlite3.OperationalError:
        return False, None
    if linha is None:
        return False, None
    return True, dict(linha)


def avaliar_sinal_iphone(conn, condicao: dict, agora: datetime,
                          ultima_vez: datetime | None) -> tuple[bool, dict | None]:
    """Sinal mais recente do tipo/lugar pedido, gravado DEPOIS de
    `ultima_vez` (faixa P7, tabela `sinais`) - usa assistente.sinais quando
    disponivel (import tardio: P7 roda em paralelo, pode nao existir ainda
    nesta integracao), com fallback pra consulta direta e defensiva."""
    tipo = condicao.get("tipo")
    lugar = condicao.get("lugar")
    desde = ultima_vez or datetime(1970, 1, 1)

    try:
        from assistente.sinais import ultimos_sinais
    except ImportError:
        return _avaliar_sinal_iphone_fallback(conn, tipo, lugar, desde)

    try:
        sinais = ultimos_sinais(conn, tipo=tipo, desde=desde)
    except sqlite3.OperationalError:
        return False, None
    if lugar:
        sinais = [s for s in sinais if (s.get("lugar") or "") == lugar]
    if not sinais:
        return False, None
    return True, sinais[0]  # ultimos_sinais ja vem ordenado por `quando` DESC


def avaliar_regra(conn, regra: dict, agora: datetime,
                   ultima_vez: datetime | None) -> tuple[bool, str, dict]:
    """Dispatcher por tipo de gatilho. Devolve (deve_disparar, mensagem,
    detalhe); detalhe traz pelo menos 'titulo' (titulo do aviso) e 'janela'
    (parte da chave_unica, pra idempotencia - ver assistente/gatilhos/p4_regras.py).
    deve_disparar=False -> mensagem="" e detalhe={}."""
    gatilho = regra.get("gatilho")
    condicao = regra.get("condicao") or {}
    acao = regra.get("acao") or {}

    if gatilho == "horario":
        if not avaliar_horario(condicao, agora, ultima_vez):
            return False, "", {}
        mensagem = acao.get("mensagem") or regra.get("texto") or "Lembrete."
        return True, mensagem, {"titulo": "Lembrete", "janela": agora.date().isoformat()}

    if gatilho == "gasto_categoria":
        deve, total = avaliar_gasto_categoria(conn, condicao, agora, ultima_vez)
        if not deve:
            return False, "", {}
        categoria = condicao["categoria"]
        limite = float(condicao["valor_limite"])
        periodo = condicao.get("periodo", "mes")
        periodo_txt = {"semana": "essa semana", "mes": "esse mes", "dia": "hoje"}.get(periodo, "esse periodo")
        mensagem = (
            f"Voce ja gastou R$ {total:.2f} com {categoria} {periodo_txt} "
            f"(limite: R$ {limite:.2f})."
        )
        return True, mensagem, {
            "titulo": "Gasto acima do combinado",
            "janela": f"{periodo}:{agora.date().isoformat()}",
        }

    if gatilho == "habito_nao_feito_ate":
        deve, habito = avaliar_habito_nao_feito_ate(conn, condicao, agora, ultima_vez)
        if not deve:
            return False, "", {}
        nome = habito["nome"] if habito else condicao.get("habito_nome", "seu habito")
        mensagem = f'Voce ainda nao marcou "{nome}" hoje.'
        return True, mensagem, {"titulo": "Habito pendente", "janela": agora.date().isoformat()}

    if gatilho == "tarefa_vencida":
        deve, tarefas = avaliar_tarefa_vencida(conn, condicao, agora, ultima_vez)
        if not deve:
            return False, "", {}
        if len(tarefas) == 1:
            mensagem = f'A tarefa "{tarefas[0]["title"]}" está vencida.'
        else:
            mensagem = f"Você tem {len(tarefas)} tarefas vencidas."
        return True, mensagem, {"titulo": "Tarefa vencida", "janela": agora.date().isoformat()}

    if gatilho == "sinal_iphone":
        deve, sinal = avaliar_sinal_iphone(conn, condicao, agora, ultima_vez)
        if not deve:
            return False, "", {}
        mensagem = acao.get("mensagem") or regra.get("texto") or "Sinal recebido."
        janela = str(sinal["id"]) if sinal else agora.isoformat()
        return True, mensagem, {"titulo": "Aviso", "janela": janela}

    raise ValueError(f"gatilho desconhecido: {gatilho!r}")
