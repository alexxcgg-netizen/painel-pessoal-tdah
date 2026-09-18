import json
import os
from datetime import date, datetime

from anthropic import Anthropic

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-5"

# USD por 1M tokens (input, output)
PRICING = {
    HAIKU: (1.00, 5.00),
    SONNET: (2.00, 10.00),
}

CAPTURE_PROMPT = """Hoje e {hoje}. Classifique o texto do usuario como "tarefa", "gasto" ou "meta"
(meta financeira, tipo "quero juntar X ate Y" ou "economizar pra comprar Z") e extraia os campos.
Responda so com JSON, sem markdown, no formato:
{{"tipo": "tarefa" ou "gasto" ou "meta", "titulo": "...", "valor": numero ou null, "categoria": "..." ou null, "quando": "..." ou null, "quando_data": "AAAA-MM-DD" ou null, "prazo": "AAAA-MM-DD" ou null, "duvida": "..." ou null, "memoria": "..." ou null}}

Categorias de gasto: mercado, transporte, lazer, contas, saude, outros.

Se tipo="tarefa": "quando" e o prazo em texto livre, do jeito que a pessoa escreveu (ex:
"amanha", "sexta que vem"). "quando_data" e a MESMA informacao convertida pra AAAA-MM-DD, so
quando der pra calcular uma data concreta a partir de hoje ({hoje}) - se o texto nao tiver prazo
nenhum ou for vago demais pra virar data (tipo "quando der", "algum dia"), deixe "quando_data"
como null mesmo que "quando" tenha texto.

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

Texto: {text}"""

BREAKDOWN_PROMPT = """Quebre esta tarefa em 3 a 6 passos pequenos e concretos, cada um algo que da pra fazer de uma vez.
Responda so com um JSON de lista de strings, sem markdown.

Tarefa: {title}"""

SUMMARY_PROMPT = """Escreva um resumo do dia em 2 a 3 frases. Tom neutro e factual, sem cobranca e sem elogio vazio.
Se houver compromissos na agenda, mencione quantos tem e se o dia esta cheio ou tranquilo -
sem repetir cada horario, so o suficiente pra dar uma nocao geral.

Coisas duraveis que voce sabe sobre a pessoa (use so se for relevante pro resumo, nao force):
{memorias}

Contexto de saude de hoje (mencione so se for notavel, tipo bem abaixo/acima da media - senao ignore):
{saude}

Tarefas concluidas: {done}
Tarefas pendentes: {pending}
Gastos de hoje: {expenses}
Compromissos na agenda hoje: {eventos}"""

CHAT_SYSTEM_PROMPT = """Voce e o assistente pessoal do Alex, dentro do painel pessoal dele
(um app que so ele usa). Ele tem TDAH - seja direto e curto, sem enrolacao, tom de colega que
ajuda e nao de atendente corporativo. Sem emoji em excesso.

Voce pode registrar tarefas, gastos e metas financeiras e gerar o plano do dia diretamente
usando as ferramentas disponiveis, sem precisar confirmar antes se o pedido ja veio claro. So
pergunte de volta (em texto, sem usar ferramenta nenhuma) se faltar uma informacao essencial,
tipo o valor de um gasto.

Contexto de agora:
{contexto}

Coisas duraveis que voce sabe sobre o Alex:
{memorias}"""

CHAT_TOOLS = [
    {
        "name": "registrar_tarefa",
        "description": "Registra uma nova tarefa pendente pro Alex.",
        "input_schema": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string"},
                "quando": {
                    "type": "string",
                    "description": "prazo em texto livre (ex: 'amanha', 'sexta') - omita se nao houver",
                },
            },
            "required": ["titulo"],
        },
    },
    {
        "name": "registrar_gasto",
        "description": "Registra um gasto do Alex.",
        "input_schema": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string"},
                "valor": {"type": "number"},
                "categoria": {
                    "type": "string",
                    "enum": ["mercado", "transporte", "lazer", "contas", "saude", "outros"],
                },
            },
            "required": ["titulo", "valor"],
        },
    },
    {
        "name": "registrar_meta",
        "description": "Cria uma meta financeira (algo que o Alex quer juntar dinheiro pra comprar/fazer).",
        "input_schema": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string"},
                "valor": {"type": "number"},
                "prazo": {"type": "string", "description": "data limite AAAA-MM-DD - omita se nao houver"},
            },
            "required": ["titulo", "valor"],
        },
    },
    {
        "name": "gerar_plano_do_dia",
        "description": "Olha as tarefas pendentes e a agenda de hoje do Alex e sugere a melhor ordem pra fazer as coisas.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "registrar_lembrete",
        "description": (
            "Registra uma data importante pra avisar com antecedencia mais perto do dia - "
            "coisas como validade de licenca/exame medico de piloto, vencimento de seguro, "
            "revisao de veiculo, aniversario de alguem. Diferente de tarefa: isso e uma data "
            "que se repete ou que so importa mesmo quando estiver perto, nao algo pra fazer agora."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string"},
                "data": {"type": "string", "description": "AAAA-MM-DD da proxima ocorrencia"},
                "recorrente": {
                    "type": "boolean",
                    "description": "true se repete todo ano nessa mesma data (ex: aniversario, validade anual) - false se for so uma vez",
                },
            },
            "required": ["titulo", "data"],
        },
    },
]


def chat(
    historico: list[dict], contexto: str, memorias: list[str], executores: dict
) -> tuple[str, list[str], dict]:
    """Roda o loop de tool-use: manda o historico + ferramentas, se a IA
    pedir pra usar uma ferramenta, chama o executor correspondente (que
    mexe no banco, em app.py) e devolve o resultado pra IA continuar, ate
    ela responder so com texto (ou ate um limite de rodadas, pra nunca
    ficar preso num loop)."""
    system = CHAT_SYSTEM_PROMPT.format(
        contexto=contexto, memorias="\n".join(f"- {m}" for m in memorias) or "nenhuma ainda"
    )
    mensagens = list(historico)
    acoes: list[str] = []
    usage_total = {"model": SONNET, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

    for _ in range(4):
        response = client.messages.create(
            model=SONNET,
            max_tokens=600,
            system=system,
            tools=CHAT_TOOLS,
            messages=mensagens,
        )
        u = _usage(response)
        usage_total["input_tokens"] += u["input_tokens"]
        usage_total["output_tokens"] += u["output_tokens"]
        usage_total["cost_usd"] += u["cost_usd"]

        if response.stop_reason != "tool_use":
            texto = "".join(b.text for b in response.content if b.type == "text").strip()
            return texto or "Beleza.", acoes, usage_total

        mensagens.append({"role": "assistant", "content": response.content})
        resultados = []
        for bloco in response.content:
            if bloco.type != "tool_use":
                continue
            executor = executores.get(bloco.name)
            resultado = executor(bloco.input) if executor else {"erro": "ferramenta desconhecida"}
            if executor:
                acoes.append(bloco.name)
            resultados.append(
                {
                    "type": "tool_result",
                    "tool_use_id": bloco.id,
                    "content": json.dumps(resultado, ensure_ascii=False),
                }
            )
        mensagens.append({"role": "user", "content": resultados})

    return (
        "Isso ficou complicado demais pra eu processar de uma vez - tenta pedir uma coisa por vez.",
        acoes,
        usage_total,
    )


PLANO_PROMPT = """Voce ajuda uma pessoa com TDAH a organizar o resto do dia. Agora sao {agora}.

Os compromissos da agenda abaixo tem horario FIXO e nao podem mudar - use como ancoras.
As tarefas pendentes NAO tem horario marcado - sugira em que ordem encaixa-las ao longo do
dia (antes, entre ou depois dos compromissos), pensando em coisas como: tarefa rapida
antes de sair de casa, tarefa que depende de estar em algum lugar perto de um compromisso
que ja leva pra la, tarefa urgente primeiro se nao houver pista de prioridade.

Coisas duraveis que voce sabe sobre a pessoa (use so se ajudar a ordenar melhor, nao force):
{memorias}

Responda em lista numerada curta (maximo 6 itens), cada item uma linha, direto ao ponto.
Tom neutro, sem cobranca. Se nao houver tarefa nem compromisso nenhum, diga isso em uma frase.

Compromissos de hoje (hora fixa): {eventos}
Tarefas pendentes (sem hora fixa): {tarefas}"""


def _extract_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def _usage(response) -> dict:
    input_price, output_price = PRICING[response.model]
    cost = (response.usage.input_tokens / 1_000_000) * input_price + (
        response.usage.output_tokens / 1_000_000
    ) * output_price
    return {
        "model": response.model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cost_usd": cost,
    }


def classify_capture(text: str) -> tuple[dict, dict]:
    response = client.messages.create(
        model=HAIKU,
        max_tokens=250,
        messages=[
            {
                "role": "user",
                "content": CAPTURE_PROMPT.format(text=text, hoje=date.today().isoformat()),
            }
        ],
    )
    return _extract_json(response.content[0].text), _usage(response)


def break_down_task(title: str) -> tuple[list[str], dict]:
    response = client.messages.create(
        model=SONNET,
        max_tokens=300,
        messages=[{"role": "user", "content": BREAKDOWN_PROMPT.format(title=title)}],
    )
    return _extract_json(response.content[0].text), _usage(response)


def summarize_day(
    done: list[str],
    pending: list[str],
    expenses: list[dict],
    eventos: list[str] | None = None,
    memorias: list[str] | None = None,
    saude: str | None = None,
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
                ),
            }
        ],
    )
    return response.content[0].text.strip(), _usage(response)


def plano_do_dia(
    tarefas: list[str], eventos: list[dict], memorias: list[str] | None = None
) -> tuple[str, dict]:
    eventos_fmt = [
        f"{e['titulo']} as {e['inicio'][11:16]}" for e in eventos if not e.get("dia_inteiro")
    ]
    response = client.messages.create(
        model=SONNET,
        max_tokens=400,
        messages=[
            {
                "role": "user",
                "content": PLANO_PROMPT.format(
                    agora=datetime.now().strftime("%H:%M"),
                    eventos=eventos_fmt or "nenhum",
                    tarefas=tarefas or "nenhuma",
                    memorias=memorias or "nenhuma ainda",
                ),
            }
        ],
    )
    return response.content[0].text.strip(), _usage(response)
