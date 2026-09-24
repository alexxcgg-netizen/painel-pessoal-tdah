"""Classificacao de captura/intent, resumo do dia e escolha do essencial.
Dona: faixa A7 (Fase 7, "Migracao 1"). As 4 funcoes chamam ia.core.chamar_ia
(nucleo hibrido da faixa A1) em vez do SDK Anthropic direto - troca de
modelo/fornecedor agora e so editar ia/config.d/<funcao>.json, sem tocar
neste arquivo. claude_client.py continua reexportando estes nomes (inclusive
os *_PROMPT, que ficaram como alias do *_CONTEXTO_FIXO de cada funcao, pra
nao quebrar quem importa `claude_client.CAPTURE_PROMPT` etc.).

Nenhuma das 4 funcoes calcula data relativa mais - ver `resolver_data`
abaixo (o modelo so devolve a pista em texto livre, ex: "sexta que vem";
quem resolve pra AAAA-MM-DD e codigo puro, testado. Ver docs/calculos.md,
secao 1.1, pra o inventario da violacao antiga)."""
import calendar
import re
import unicodedata
from datetime import date, timedelta
from typing import Optional

import calculos
from ia.contrato import Resposta
from ia.core import chamar_ia
# Reaproveitado da faixa A6 (ia/funcoes/chat.py) por pedido do integrador -
# nao duplicar: faz o adapter "anthropic" do ia.core usar o MESMO cliente
# (ia.legado.client == claude_client.client) que testes antigos de outras
# faixas ja mockam com patch.object(claude_client.client.messages, "create")
# (ex: tests/test_claude_client.py::ClassifyIntentTestCase, escrito quando
# classify_intent ainda chamava o SDK Anthropic direto). Sem isso,
# ia.adapters.anthropic.AdapterAnthropic criaria seu proprio cliente e esse
# mock pararia de interceptar qualquer chamada (ver
# scripts/ralph-a7-migracao1/progress.txt).
from ia.funcoes.chat import _garantir_adapter_anthropic_legado


class ErroIA(ValueError):
    """Levantada quando chamar_ia devolve Resposta(ok=False, ...) (rede,
    provedor, JSON fora do schema, teto mensal estourado - chamar_ia nunca
    levanta excecao, so devolve ok=False, entao quem chama decide o que
    fazer com a falha).

    E uma subclasse de ValueError de proposito: app.py:_call_claude (faixa
    dona) so pega `anthropic.APIError` e `(ValueError, KeyError)` ao redor
    da chamada - antes da migracao, uma falha de rede vinha como
    anthropic.APIError (mensagem CLAUDE_ERROR_MSG) e uma falha de parse
    como ValueError (CLAUDE_FORMAT_ERROR_MSG). Como chamar_ia nunca deixa
    excecao do provedor subir, as duas causas colapsam aqui numa unica
    ValueError -> app.py sempre devolve CLAUDE_FORMAT_ERROR_MSG agora,
    nunca mais CLAUDE_ERROR_MSG, pras 4 funcoes desta faixa. Nao e uma
    regressao de comportamento visivel (ainda vira erro 502 controlado,
    nunca 500 cru), so uma mensagem menos precisa - anotado em
    scripts/ralph-a7-migracao1/progress.txt (app.py:411-418) pra quem for
    dono de app.py decidir se vale distinguir de novo."""


def _usage_de(resp: Resposta) -> dict:
    """Resposta (ia/contrato.py) -> dict de usage no formato que app.py
    espera (_log_usage em app.py:359-362): model/input_tokens/output_tokens/
    cost_usd. custo_usd ja vem calculado pelo adapter (ia/precos.py), entao
    aqui e so remapear nomes."""
    return {
        "model": resp.modelo,
        "input_tokens": resp.tokens_in,
        "output_tokens": resp.tokens_out,
        "cost_usd": resp.custo_usd,
    }


def _chamar(funcao: str, *, contexto_fixo: str, mensagem: str, schema: Optional[dict]) -> Resposta:
    _garantir_adapter_anthropic_legado()
    resp = chamar_ia(
        funcao,
        [{"role": "user", "content": mensagem}],
        contexto_fixo=contexto_fixo,
        schema=schema,
    )
    if not resp.ok:
        raise ErroIA(resp.erro or f"falha ao chamar IA ({funcao})")
    return resp


# --------------------------------------------------------------------------
# resolver_data - conversao de pista textual (pt-BR) pra data absoluta.
# Puro, sem IA: o modelo so extrai a pista ("amanha", "sexta que vem", "dia
# 15", "em 6 meses", "ate dezembro"...), isto aqui resolve pra AAAA-MM-DD.
# --------------------------------------------------------------------------

_MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11,
    "dezembro": 12,
}

# date.weekday(): segunda=0 ... domingo=6
_DIAS_SEMANA = {
    "segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4,
    "sabado": 5, "domingo": 6,
}

_UNIDADES = {"dia": "dia", "dias": "dia", "semana": "semana", "semanas": "semana",
             "mes": "mes", "meses": "mes", "ano": "ano", "anos": "ano"}

_RE_DEPOIS_DE_AMANHA = re.compile(r"\bdepois de amanha\b")
_RE_AMANHA = re.compile(r"\bamanha\b")
_RE_HOJE = re.compile(r"\bhoje\b")
_RE_DIA_N = re.compile(r"\bdia\s+(\d{1,2})\b")
_RE_EM_N_UNIDADE = re.compile(
    r"\b(?:em|daqui(?:\s+a)?)\s+(\d+)\s+(dia|dias|semana|semanas|mes|meses|ano|anos)\b"
)
_RE_SEMANA_QUE_VEM = re.compile(r"\b(semana que vem|proxima semana|na proxima semana)\b")
_RE_MES_QUE_VEM = re.compile(r"\b(mes que vem|proximo mes|no proximo mes)\b")
_RE_ATE_MES = re.compile(r"\bate\s+([a-z]+)(?:\s+de\s+(\d{4}))?\b")


def _sem_acento(texto: str) -> str:
    """Remove acento/cedilha (NFKD + descarta marcas combinantes) pra
    comparar palavra por palavra sem depender de o texto vir acentuado."""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _proximo_dia_do_mes(hoje: date, dia: int) -> Optional[date]:
    """"Dia 15": tenta o mes atual; se o dia ja passou (ou nao existir nesse
    mes, ex: dia 31 em fevereiro), tenta os proximos meses, ate 1 ano a
    frente. None se `dia` nunca for um dia valido de mes nenhum (>31)."""
    if not (1 <= dia <= 31):
        return None
    ano, mes = hoje.year, hoje.month
    for _ in range(13):
        ultimo_dia = calendar.monthrange(ano, mes)[1]
        if dia <= ultimo_dia:
            candidata = date(ano, mes, dia)
            if candidata >= hoje:
                return candidata
        mes += 1
        if mes > 12:
            mes = 1
            ano += 1
    return None


def _somar_anos(base: date, anos: int) -> date:
    ano = base.year + anos
    ultimo_dia = calendar.monthrange(ano, base.month)[1]
    return date(ano, base.month, min(base.day, ultimo_dia))


def _somar_unidade(hoje: date, qtd: int, unidade: str) -> Optional[date]:
    if qtd <= 0:
        return None
    unidade = _UNIDADES.get(unidade)
    if unidade == "dia":
        return hoje + timedelta(days=qtd)
    if unidade == "semana":
        return hoje + timedelta(weeks=qtd)
    if unidade == "mes":
        # calculos.data_ultima_parcela(primeira, n) = primeira + (n-1) meses,
        # com o mesmo comprimento de mes que uma parcela de financiamento
        # (dia comprimido em mes mais curto) - reaproveita em vez de
        # duplicar a aritmetica de mes (docs/calculos.md secao 1.3, item 4).
        return calculos.data_ultima_parcela(hoje, qtd + 1)
    if unidade == "ano":
        return _somar_anos(hoje, qtd)
    return None


def _proximo_dia_semana(hoje: date, indice_alvo: int, pular_essa_semana: bool) -> date:
    """Proxima ocorrencia do dia da semana `indice_alvo` (segunda=0).

    Sem "que vem"/"proximo(a)": pode ser hoje mesmo, se hoje ja for esse dia
    da semana (ex: "sexta" dito numa sexta-feira = hoje).
    Com "que vem"/"proximo(a)": nunca hoje - se hoje ja for esse dia, pula
    pra semana seguinte (e assim que a expressao costuma ser entendida em
    pt-BR: "sexta que vem" dito numa sexta nao quer dizer hoje)."""
    dias_ate = (indice_alvo - hoje.weekday()) % 7
    if dias_ate == 0 and pular_essa_semana:
        dias_ate = 7
    return hoje + timedelta(days=dias_ate)


def resolver_data(texto: Optional[str], hoje: date) -> Optional[str]:
    """Resolve uma pista textual de data relativa (pt-BR, do jeito que uma
    pessoa escreve - "amanha", "sexta que vem", "dia 15", "em 6 meses",
    "ate dezembro", "semana que vem", "hoje as 14h"...) pra uma data
    absoluta 'AAAA-MM-DD', ancorada em `hoje`. Nunca chama IA nem faz
    conta financeira - so interpretacao de calendario, com stdlib +
    `calculos.data_ultima_parcela` pra soma de mes.

    Devolve None quando o texto nao tem (ou nao e possivel reconhecer)
    nenhuma pista de data - nunca levanta excecao, um texto esquisito so
    vira "sem data" (o campo correspondente fica null, do jeito que o
    prompt antigo ja deixava quando "nao dava pra calcular")."""
    if not texto or not isinstance(texto, str):
        return None
    t = _sem_acento(texto.strip().lower())
    if not t:
        return None

    # "depois de amanha" contem "amanha" - tem que checar antes.
    if _RE_DEPOIS_DE_AMANHA.search(t):
        return (hoje + timedelta(days=2)).isoformat()
    if _RE_AMANHA.search(t):
        return (hoje + timedelta(days=1)).isoformat()
    if _RE_HOJE.search(t):
        return hoje.isoformat()

    if _RE_SEMANA_QUE_VEM.search(t):
        return (hoje + timedelta(days=7)).isoformat()
    if _RE_MES_QUE_VEM.search(t):
        candidata = _somar_unidade(hoje, 1, "mes")
        return candidata.isoformat() if candidata else None

    for nome, indice in _DIAS_SEMANA.items():
        if re.search(rf"\b{nome}(-feira)?\s+que\s+vem\b", t) or \
           re.search(rf"\bproxim[ao]\s+{nome}\b", t):
            return _proximo_dia_semana(hoje, indice, pular_essa_semana=True).isoformat()
    for nome, indice in _DIAS_SEMANA.items():
        if re.search(rf"\b{nome}(-feira)?\b", t):
            return _proximo_dia_semana(hoje, indice, pular_essa_semana=False).isoformat()

    m = _RE_EM_N_UNIDADE.search(t)
    if m:
        candidata = _somar_unidade(hoje, int(m.group(1)), m.group(2))
        return candidata.isoformat() if candidata else None

    m = _RE_DIA_N.search(t)
    if m:
        candidata = _proximo_dia_do_mes(hoje, int(m.group(1)))
        return candidata.isoformat() if candidata else None

    m = _RE_ATE_MES.search(t)
    if m and m.group(1) in _MESES:
        mes = _MESES[m.group(1)]
        ano = int(m.group(2)) if m.group(2) else hoje.year
        if not m.group(2) and mes < hoje.month:
            ano += 1
        # "ate dezembro" = prazo-limite = ultimo dia do mes.
        ultimo_dia = calendar.monthrange(ano, mes)[1]
        return date(ano, mes, ultimo_dia).isoformat()

    return None


# --------------------------------------------------------------------------
# classify_capture
# --------------------------------------------------------------------------

CAPTURE_CONTEXTO_FIXO = """Classifique o texto do usuario como "tarefa", "gasto" ou "meta" (meta
financeira, tipo "quero juntar X" ou "economizar pra Y") e extraia os campos. Responda so com
JSON, sem markdown, com exatamente estes campos:
{"tipo": "tarefa" ou "gasto" ou "meta", "titulo": "...", "valor": numero ou null, "categoria": "..." ou null, "status": "real" ou "planejado" ou null, "quando": "..." ou null, "hora": "HH:MM" ou null, "duvida": "..." ou null, "memoria": "..." ou null}

Categorias de gasto: mercado, transporte, lazer, contas, saude, outros.

Se tipo="gasto": "status" e "real" quando ja aconteceu (verbo no passado: "gastei", "paguei",
"comprei") e "planejado" quando e so intencao futura ainda nao decidida ("penso em comprar",
"quero gastar", "talvez eu compre"). Na duvida, use "real" (e o caso mais comum). Null se tipo
nao for "gasto".

"quando" e a referencia de tempo em TEXTO LIVRE, exatamente como a pessoa escreveu (ex: "amanha",
"sexta que vem", "dia 15", "em 6 meses", "ate dezembro") - NUNCA calcule uma data, so copie (ou
resuma) a pista textual. Serve tanto pro prazo de uma tarefa quanto pro prazo/meta financeira.
Null se o texto nao tiver nenhuma referencia de tempo.

"hora" e o horario do compromisso em HH:MM (24h), SO quando o texto disser um horario especifico
("as 14h", "as 22 horas", "9 da manha" = "09:00", "2 da tarde" = "14:00"). Null se nao houver
horario nenhum no texto.

Preencha "duvida" APENAS se o texto for realmente ambiguo demais pra classificar com confianca
(nao da pra saber se e tarefa/gasto/meta, ou um gasto/meta sem valor nenhum) - nesse caso uma
pergunta curta e direta pra esclarecer, com os outros campos vindo com o melhor palpite. Se o
texto for razoavelmente claro, null - nao pergunte por excesso de zelo.

Preencha "memoria" APENAS se o texto revelar um fato duravel sobre a pessoa que vale lembrar
depois (preferencia, rotina, relacao, contexto recorrente) e que NAO seja so o proprio item
classificado. Terceira pessoa, uma frase curta. Null na grande maioria dos textos.

Exemplo: texto "gastei 40 no mercado ontem" -> {"tipo": "gasto", "titulo": "Mercado", "valor": 40, "categoria": "mercado", "status": "real", "quando": null, "hora": null, "duvida": null, "memoria": null}"""

CAPTURE_PROMPT = CAPTURE_CONTEXTO_FIXO  # alias p/ compat (claude_client.py reexporta este nome)

CAPTURE_SCHEMA = {
    "type": "object",
    "required": ["tipo", "titulo", "valor", "categoria", "status", "quando", "hora", "duvida", "memoria"],
    "additionalProperties": False,
    "properties": {
        "tipo": {"type": "string", "minLength": 1},
        "titulo": {"type": "string"},
        "valor": {"type": ["number", "null"]},
        "categoria": {"type": ["string", "null"]},
        "status": {"type": ["string", "null"]},
        "quando": {"type": ["string", "null"]},
        "hora": {"type": ["string", "null"]},
        "duvida": {"type": ["string", "null"]},
        "memoria": {"type": ["string", "null"]},
    },
}


def classify_capture(text: str, contexto_correcao: str | None = None) -> tuple[dict, dict]:
    hoje = date.today()
    mensagem = (
        f'Hoje e {hoje.isoformat()}.\n\n'
        f"Aprendizado de correcao anterior (o Alex ja corrigiu manualmente uma captura parecida "
        f"com essa no passado, porque a classificacao automatica saiu errada) - use como pista "
        f"forte de qual e o tipo/categoria certos, mas ainda julgue pelo texto atual, o padrao "
        f"pode nao se repetir sempre:\n"
        f"{contexto_correcao or 'nenhuma correcao parecida no historico'}\n\n"
        f"Texto: {text}"
    )
    resp = _chamar("classify_capture", contexto_fixo=CAPTURE_CONTEXTO_FIXO, mensagem=mensagem,
                    schema=CAPTURE_SCHEMA)
    parsed = dict(resp.dados)

    pista = parsed.get("quando")
    if parsed.get("tipo") == "meta":
        parsed["quando_data"] = None
        parsed["prazo"] = resolver_data(pista, hoje)
    else:
        parsed["prazo"] = None
        quando_data = resolver_data(pista, hoje)
        if not quando_data and parsed.get("hora"):
            # Ha hora mas nenhuma referencia de dia no texto -> assume hoje
            # (uma pessoa que diz "tenho consulta as 14h" sem mais contexto
            # normalmente esta falando de hoje).
            quando_data = hoje.isoformat()
        parsed["quando_data"] = quando_data

    return parsed, _usage_de(resp)


# --------------------------------------------------------------------------
# summarize_day
# --------------------------------------------------------------------------

SUMMARY_CONTEXTO_FIXO = """Escreva um resumo do dia em 2 a 3 frases. Tom neutro e factual, sem
cobranca e sem elogio vazio. Se houver compromissos na agenda, mencione quantos tem e se o dia
esta cheio ou tranquilo - sem repetir cada horario, so o suficiente pra dar uma nocao geral.

Coisas duraveis sobre a pessoa: mencione so se for relevante pro resumo, nao force.
Saude de hoje: mencione so se for notavel (bem abaixo/acima da media) - senao ignore.
Resumo financeiro da construtora do Alex: mencione so se fizer sentido, nao force - e o
negocio dele, nao gasto pessoal.
Previsao de chuva: mencione so se houver risco relevante pro dia (ex: compromisso que pode ser
afetado) - se nao houver risco, ignore.

Responda so com o resumo em texto corrido, sem JSON e sem markdown."""

SUMMARY_PROMPT = SUMMARY_CONTEXTO_FIXO  # alias p/ compat


def summarize_day(
    done: list[str],
    pending: list[str],
    expenses: list[dict],
    eventos: list[str] | None = None,
    memorias: list[str] | None = None,
    saude: str | None = None,
    construtora: str | None = None,
    clima: str | None = None,
) -> tuple[str, dict]:
    mensagem = (
        f"Tarefas concluidas: {done or 'nenhuma'}\n"
        f"Tarefas pendentes: {pending or 'nenhuma'}\n"
        f"Gastos de hoje: {expenses or 'nenhum'}\n"
        f"Compromissos na agenda hoje: {eventos or 'nenhum (ou agenda nao conectada)'}\n"
        f"Coisas duraveis que voce sabe sobre a pessoa: {memorias or 'nenhuma ainda'}\n"
        f"Contexto de saude de hoje: {saude or 'sem dados de saude hoje'}\n"
        f"Resumo financeiro da construtora: {construtora or 'nao conectado'}\n"
        f"Previsao de chuva hoje: {clima or 'sem risco de chuva relevante (ou cidade padrao nao configurada)'}"
    )
    resp = _chamar("summarize_day", contexto_fixo=SUMMARY_CONTEXTO_FIXO, mensagem=mensagem,
                    schema=None)
    return (resp.texto or "").strip(), _usage_de(resp)


# --------------------------------------------------------------------------
# escolher_essencial
# --------------------------------------------------------------------------

ESSENCIAL_CONTEXTO_FIXO = """Voce ajuda uma pessoa com TDAH num dia corrido: das tarefas dadas,
escolha as 1 a 3 MAIS importantes pra hoje (menos e melhor - se so uma importa de verdade,
escolha uma). Criterio: o que tem consequencia real se nao for feito hoje (prazo vencido ou
vencendo, hora marcada, algo que trava outra coisa). Rotina repetitiva (remedio, academia)
raramente e a escolha, ela ja tem lembrete proprio.

Responda so com JSON, sem markdown, no formato:
{"escolhas": [{"id": <id da tarefa>, "motivo": "<ate 8 palavras, sem cobranca>"}]}

No maximo 3 itens em "escolhas". Se nenhuma tarefa tiver consequencia real hoje, "escolhas" pode
vir vazio []."""

ESSENCIAL_PROMPT = ESSENCIAL_CONTEXTO_FIXO  # alias p/ compat

ESSENCIAL_SCHEMA = {
    "type": "object",
    "required": ["escolhas"],
    "additionalProperties": False,
    "properties": {
        "escolhas": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "required": ["id", "motivo"],
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "integer"},
                    "motivo": {"type": "string", "maxLength": 120},
                },
            },
        },
    },
}


def escolher_essencial(tarefas: list[dict]) -> tuple[list[dict], dict]:
    linhas = "\n".join(
        f"{t['id']} | {t['title']} | {t.get('due_date') or 'sem prazo'} | {t.get('hora') or '-'}"
        for t in tarefas
    )
    mensagem = f"Hoje e {date.today().isoformat()}.\n\nTarefas (id | titulo | prazo | hora):\n{linhas}"
    resp = _chamar("escolher_essencial", contexto_fixo=ESSENCIAL_CONTEXTO_FIXO, mensagem=mensagem,
                    schema=ESSENCIAL_SCHEMA)
    escolhas = resp.dados.get("escolhas")
    return escolhas if isinstance(escolhas, list) else [], _usage_de(resp)


# ---- Classificador de intent (Fase 5, US-A2 - contrato em docs/INTENT.md) --

# Lista fechada de acoes - contrato estavel com quem consome /api/intent/classificar
# (Grupo B, navegacao por voz). So pode crescer (adicionar valor novo), nunca
# renomear/remover um existente.
ACOES_INTENT = (
    "registrar_tarefa",
    "registrar_gasto",
    "registrar_checkin",
    "navegar_tela",
    "consultar",
    "corrigir_ultimo",
    "desconhecido",
)

# Abaixo disso, precisa_confirmacao=True em vez de deixar quem chamou executar
# direto - ver docs/INTENT.md.
CONFIANCA_MINIMA_INTENT = 0.6

INTENT_CONTEXTO_FIXO = """Classifique o comando de voz/texto do usuario numa das acoes fechadas
abaixo e extraia os parametros relevantes.

Acoes possiveis:
- registrar_tarefa: descreve algo a fazer (ex: "lembra de ligar pro dentista")
- registrar_gasto: descreve um gasto/despesa (ex: "gastei 50 reais no mercado")
- registrar_checkin: check-in do dia - energia, sono ou humor (ex: "minha energia hoje ta boa")
- navegar_tela: pedido pra ir a uma tela/aba do painel (ex: "abre os gastos", "mostra minhas metas")
- consultar: pergunta sobre dado que ja existe, sem criar nada novo (ex: "quanto eu gastei esse mes")
- corrigir_ultimo: correcao do ultimo item capturado/classificado (ex: "nao, isso e gasto")
- desconhecido: nao da pra classificar com confianca em nenhuma acao acima

Responda so com JSON, sem markdown, no formato:
{"acao": "uma das acoes acima", "confianca": numero de 0.0 a 1.0, "parametros": {}}

"confianca" reflete o quanto voce tem certeza da acao escolhida - use um numero baixo (abaixo de
0.6) quando o texto for ambiguo ou puder ser mais de uma acao. "parametros" e um objeto com os
campos relevantes extraidos pra essa acao (pode ficar vazio {} se nao houver nada especifico a
extrair) - por exemplo, pra registrar_tarefa/registrar_gasto pode conter "titulo"/"valor"/
"categoria"; pra navegar_tela pode conter "tela"; pra consultar pode conter "pergunta".

Exemplo: texto "abre os gastos" -> {"acao": "navegar_tela", "confianca": 0.9, "parametros": {"tela": "gastos"}}"""

INTENT_PROMPT = INTENT_CONTEXTO_FIXO  # alias p/ compat

INTENT_SCHEMA = {
    # De proposito SEM "required" e sem "type" em confianca/parametros: o
    # codigo abaixo (nao o schema) tolera acao desconhecida, confianca
    # ausente/tipo errado e parametros fora do tipo dict - sempre virando um
    # palpite seguro (desconhecido/0.0/{}) em vez de estourar a chamada
    # inteira. As "properties" ficam so como guia de formato pro modelo (o
    # adapter injeta json.dumps(schema) no prompt) - ver
    # tests/test_claude_client.py::ClassifyIntentTestCase (anterior a esta
    # migracao) pra esse contrato de tolerancia.
    "type": "object",
    "properties": {
        "acao": {},
        "confianca": {},
        "parametros": {},
    },
}


def classify_intent(texto: str, contexto_correcao: str | None = None) -> tuple[dict, dict]:
    """Classifica um comando de voz/texto numa das ACOES_INTENT - contrato
    descrito em docs/INTENT.md. `contexto_correcao` (opcional) segue o mesmo
    espirito de classify_capture: uma correcao parecida que o Alex ja fez
    antes vira contexto extra no prompt, a decisao continua sendo da IA."""
    mensagem = (
        f"Hoje e {date.today().isoformat()}.\n"
        f"{contexto_correcao or 'nenhuma correcao parecida no historico'}\n\n"
        f'Texto do usuario: "{texto}"'
    )
    resp = _chamar("classify_intent", contexto_fixo=INTENT_CONTEXTO_FIXO, mensagem=mensagem,
                    schema=INTENT_SCHEMA)
    parsed = resp.dados

    acao = parsed.get("acao")
    if acao not in ACOES_INTENT:
        acao = "desconhecido"

    confianca = parsed.get("confianca")
    if not isinstance(confianca, (int, float)) or isinstance(confianca, bool):
        confianca = 0.0
    confianca = max(0.0, min(1.0, float(confianca)))

    parametros = parsed.get("parametros")
    if not isinstance(parametros, dict):
        parametros = {}

    resultado = {
        "acao": acao,
        "confianca": confianca,
        "parametros": parametros,
        "precisa_confirmacao": confianca < CONFIANCA_MINIMA_INTENT,
    }
    return resultado, _usage_de(resp)
