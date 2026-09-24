"""Classificacao de captura/intent, resumo do dia e escolha do essencial.
Dona futura: faixa A7 (Fase 7). Extraido de claude_client.py sem mudar
comportamento; claude_client.py reexporta estes nomes."""
from datetime import date

from ia.legado import HAIKU, _extract_json, _usage, client


CAPTURE_PROMPT = """Hoje e {hoje}. Classifique o texto do usuario como "tarefa", "gasto" ou "meta"
(meta financeira, tipo "quero juntar X ate Y" ou "economizar pra comprar Z") e extraia os campos.
Responda so com JSON, sem markdown, no formato:
{{"tipo": "tarefa" ou "gasto" ou "meta", "titulo": "...", "valor": numero ou null, "categoria": "..." ou null, "status": "real" ou "planejado" ou null, "quando": "..." ou null, "quando_data": "AAAA-MM-DD" ou null, "hora": "HH:MM" ou null, "prazo": "AAAA-MM-DD" ou null, "duvida": "..." ou null, "memoria": "..." ou null}}

Categorias de gasto: mercado, transporte, lazer, contas, saude, outros.

Se tipo="gasto": "status" e "real" quando o gasto ja aconteceu (ex: "gastei", "paguei",
"comprei", verbo no passado) e "planejado" quando e so uma possibilidade/intencao futura ainda
nao decidida (ex: "penso em comprar", "quero gastar", "talvez eu compre", "tô pensando em").
Na duvida, use "real" (e o caso mais comum). Deixe null se tipo nao for "gasto".

Se tipo="tarefa": "quando" e o prazo em texto livre, do jeito que a pessoa escreveu (ex:
"amanha", "sexta que vem"). "quando_data" e a MESMA informacao convertida pra AAAA-MM-DD, so
quando der pra calcular uma data concreta a partir de hoje ({hoje}) - se o texto nao tiver prazo
nenhum ou for vago demais pra virar data (tipo "quando der", "algum dia"), deixe "quando_data"
como null mesmo que "quando" tenha texto.

"hora" e o horario do compromisso em HH:MM (24h), SO quando o texto disser um horario especifico
tipo "as 14h", "as 22 horas", "9 da manha", "2 da tarde" - converta pra 24h (2 da tarde = 14:00).
Se houver "hora" mas nenhuma referencia de dia no texto (nem "hoje" nem outra data), assuma que
e hoje e preencha "quando_data" com {hoje} mesmo assim - uma pessoa que diz "tenho consulta as
14h" sem mais contexto normalmente esta falando de hoje. Se o texto nao mencionar horario
nenhum, deixe "hora" como null.

Se tipo="meta": "valor" e o valor total que a pessoa quer juntar, e "prazo" e a data limite no
formato AAAA-MM-DD - calcule a partir de hoje ({hoje}) se o texto disser algo relativo tipo
"ate dezembro" ou "em 6 meses". Se nao houver prazo claro no texto, deixe "prazo" como null.

Preencha "duvida" APENAS se o texto for realmente ambiguo demais pra classificar com confianca
(ex: nao da pra saber se e tarefa, gasto ou meta, ou um gasto/meta sem valor nenhum). Nesse caso
"duvida" deve ser uma pergunta curta e direta pra esclarecer, e os outros campos podem vir com o
melhor palpite. Se o texto for razoavelmente claro, deixe "duvida" como null - nao pergunte por
excesso de zelo.

Preencha "memoria" APENAS se o texto revelar um fato duravel sobre a pessoa que vale lembrar em
conversas futuras e que NAO e so o proprio item classificado - por exemplo uma preferencia
("prefere economizar pra viagem mais que pra moto"), rotina ("trabalha home office as quartas"),
relacao ("esposa se chama Ana") ou contexto recorrente. Escreva em terceira pessoa, uma frase
curta. Se o texto for so uma tarefa/gasto/meta pontual sem nada duravel por tras, deixe "memoria"
como null - a grande maioria dos textos nao tem nada pra lembrar aqui.

Aprendizado de correcao anterior (o Alex ja corrigiu manualmente uma captura parecida com essa no
passado, porque a classificacao automatica saiu errada) - use como pista forte de qual e o tipo/
categoria certos, mas ainda julgue pelo texto atual, o padrao pode nao se repetir sempre:
{contexto_correcao}

Texto: {text}"""

SUMMARY_PROMPT = """Escreva um resumo do dia em 2 a 3 frases. Tom neutro e factual, sem cobranca e sem elogio vazio.
Se houver compromissos na agenda, mencione quantos tem e se o dia esta cheio ou tranquilo -
sem repetir cada horario, so o suficiente pra dar uma nocao geral.

Coisas duraveis que voce sabe sobre a pessoa (use so se for relevante pro resumo, nao force):
{memorias}

Contexto de saude de hoje (mencione so se for notavel, tipo bem abaixo/acima da media - senao ignore):
{saude}

Resumo financeiro da construtora do Alex (mencione so se fizer sentido, nao force - isso e o
negocio dele, nao gasto pessoal):
{construtora}

Previsao de chuva hoje (mencione so se houver risco de chuva e parecer relevante pro dia - por
exemplo se tiver compromisso que pode ser afetado por chuva; se nao houver risco, ignore):
{clima}

Tarefas concluidas: {done}
Tarefas pendentes: {pending}
Gastos de hoje: {expenses}
Compromissos na agenda hoje: {eventos}"""


def classify_capture(text: str, contexto_correcao: str | None = None) -> tuple[dict, dict]:
    response = client.messages.create(
        model=HAIKU,
        max_tokens=250,
        messages=[
            {
                "role": "user",
                "content": CAPTURE_PROMPT.format(
                    text=text,
                    hoje=date.today().isoformat(),
                    contexto_correcao=contexto_correcao or "nenhuma correcao parecida no historico",
                ),
            }
        ],
    )
    return _extract_json(response.content[0].text), _usage(response)


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
    response = client.messages.create(
        model=HAIKU,
        max_tokens=200,
        messages=[
            {
                "role": "user",
                "content": SUMMARY_PROMPT.format(
                    done=done or "nenhuma",
                    pending=pending or "nenhuma",
                    expenses=expenses or "nenhum",
                    eventos=eventos or "nenhum (ou agenda nao conectada)",
                    memorias=memorias or "nenhuma ainda",
                    saude=saude or "sem dados de saude hoje",
                    construtora=construtora or "nao conectado",
                    clima=clima or "sem risco de chuva relevante (ou cidade padrao nao configurada)",
                ),
            }
        ],
    )
    return response.content[0].text.strip(), _usage(response)


ESSENCIAL_PROMPT = """Voce ajuda uma pessoa com TDAH num dia corrido: das tarefas abaixo, escolha
as 1 a 3 MAIS importantes pra hoje (menos e melhor - se so uma importa de verdade, escolha uma).
Criterio: o que tem consequencia real se nao for feito hoje (prazo vencido ou vencendo, hora
marcada, algo que trava outra coisa). Rotina repetitiva (remedio, academia) raramente e a escolha,
ela ja tem lembrete proprio. Hoje e {hoje}.

Tarefas (id | titulo | prazo | hora):
{tarefas}

Responda SO com JSON, sem markdown: [{{"id": <id>, "motivo": "<ate 8 palavras, sem cobranca>"}}]"""


def escolher_essencial(tarefas: list[dict]) -> tuple[list[dict], dict]:
    linhas = "\n".join(
        f"{t['id']} | {t['title']} | {t.get('due_date') or 'sem prazo'} | {t.get('hora') or '-'}"
        for t in tarefas
    )
    response = client.messages.create(
        model=HAIKU,
        max_tokens=250,
        messages=[
            {
                "role": "user",
                "content": ESSENCIAL_PROMPT.format(hoje=date.today().isoformat(), tarefas=linhas),
            }
        ],
    )
    return _extract_json(response.content[0].text), _usage(response)


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

INTENT_PROMPT = """Hoje e {hoje}. Classifique o comando de voz/texto do usuario numa das acoes
fechadas abaixo e extraia os parametros relevantes.

Acoes possiveis:
- registrar_tarefa: comando que descreve algo a fazer (ex: "lembra de ligar pro dentista").
- registrar_gasto: comando que descreve um gasto/despesa (ex: "gastei 50 reais no mercado").
- registrar_checkin: comando de check-in do dia - energia, sono ou humor (ex: "minha energia hoje ta boa").
- navegar_tela: pedido pra ir a uma tela/aba do painel (ex: "abre os gastos", "mostra minhas metas").
- consultar: pergunta sobre dado que ja existe, sem criar nada novo (ex: "quanto eu gastei esse mes").
- corrigir_ultimo: correcao do ultimo item capturado/classificado (ex: "nao, isso e gasto", "corrige pra tarefa").
- desconhecido: nao da pra classificar com confianca em nenhuma acao acima.

{contexto_correcao}

Responda SO com JSON, sem markdown, no formato:
{{"acao": "uma das acoes acima", "confianca": numero de 0.0 a 1.0, "parametros": {{}}}}

"confianca" reflete o quanto voce tem certeza da acao escolhida - use um numero baixo (abaixo de
0.6) quando o texto for ambiguo ou puder ser mais de uma acao. "parametros" e um objeto com os
campos relevantes extraidos pra essa acao (pode ficar vazio {{}} se nao houver nada especifico a
extrair) - por exemplo, pra registrar_tarefa/registrar_gasto pode conter "titulo"/"valor"/
"categoria"; pra navegar_tela pode conter "tela"; pra consultar pode conter "pergunta".

Texto do usuario: "{texto}\""""


def classify_intent(texto: str, contexto_correcao: str | None = None) -> tuple[dict, dict]:
    """Classifica um comando de voz/texto numa das ACOES_INTENT - contrato
    descrito em docs/INTENT.md. `contexto_correcao` (opcional) segue o mesmo
    espirito de classify_capture: uma correcao parecida que o Alex ja fez
    antes vira contexto extra no prompt, a decisao continua sendo da IA."""
    response = client.messages.create(
        model=HAIKU,
        max_tokens=200,
        messages=[
            {
                "role": "user",
                "content": INTENT_PROMPT.format(
                    texto=texto,
                    hoje=date.today().isoformat(),
                    contexto_correcao=contexto_correcao or "nenhuma correcao parecida no historico",
                ),
            }
        ],
    )
    parsed = _extract_json(response.content[0].text)

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
    return resultado, _usage(response)
