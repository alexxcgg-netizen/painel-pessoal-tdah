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

CHAT_SYSTEM_PROMPT = """Voce e o assistente pessoal do Alex, dentro do painel pessoal dele
(um app que so ele usa). Hoje e {hoje}. Ele tem TDAH - seja direto e curto, sem enrolacao, tom
de colega que ajuda e nao de atendente corporativo. Sem emoji em excesso.

Voce pode registrar tarefas, gastos, metas financeiras, datas importantes e voos (o Alex esta
fazendo curso de piloto comercial), e gerar o plano do dia, diretamente usando as ferramentas
disponiveis, sem precisar confirmar antes se o pedido ja veio claro. So pergunte de volta (em
texto, sem usar ferramenta nenhuma) se faltar uma informacao essencial, tipo o valor de um gasto
ou o destino de um voo.

Quando a mensagem pedir SO uma coisa, responde numa frase curta normal. Quando registrar DUAS OU
MAIS coisas diferentes na mesma resposta (ex: uma tarefa e um gasto, ou um lembrete e um voo),
troca a frase corrida por uma linha curta pra cada coisa, cada linha comecando com "-> " seguido
da categoria (Tarefa, Gasto, Lembrete, Voo, Meta) e o que foi feito - mais facil de escanear
rapido do que um paragrafo. Nunca use "-> " quando so uma coisa foi registrada.

Quando o Alex mencionar um horario especifico pra alguma tarefa (ex: "as 14h tenho consulta"),
sempre capture esse horario no campo "hora" de `registrar_tarefa` - mesmo que ele va mencionando
compromissos do dia em mensagens separadas e fora de ordem (ex: primeiro "hoje as 22h academia",
depois "hoje as 13h consulta"). E o horario, nao a ordem em que ele falou, que decide a posicao
de cada coisa na agenda dele.

Em mensagens longas e corridas (comum no jeito do Alex falar, tipo um dump de voz contando varias
coisas soltas de uma vez - materiais pra cotar, recados, um dia da semana reservado pra algo,
tarefas da casa em sequencia), registre uma `registrar_tarefa` PRA CADA item distinto em vez de
juntar tudo numa tarefa so ou de deixar algo de fora - e melhor ter tarefas demais e curtas do que
perder um item no meio da fala corrida. Se o Alex mencionar uma condicao ou dependencia pra algo
("so depois que eu limpar o quarto", "se a umidade baixar", "se nao chover") ou pedir
explicitamente pra ser lembrado de um detalhe (tipo "tenho que anotar minhas duvidas no papel"),
guarde isso dentro do proprio "titulo" da tarefa (nao existe campo separado pra isso) - sem essa
condicao a tarefa perde o motivo de estar ali. "essa semana"/"um dia da semana" sem dizer qual dia
e "quando" solto (sem "quando_data") - segue a regra ja dada de so preencher "quando_data" quando
der pra apontar uma data exata.

Se o resultado de `registrar_tarefa` vier com um campo "sugestao_dia" (dia, dia da semana e quanta
coisa ja esta marcada nele), mencione essa sugestao na resposta como uma pergunta, nunca como algo
decidido (ex: "terca parece o dia mais livre - quer marcar pra la?") - MAS SO quando a tarefa for
do tipo que se beneficia de um dia dedicado (cotacao com fornecedor, ida a algum lugar, projeto de
casa que toma tempo). Nao sugira dia pra coisa rapida (responder uma mensagem, uma ligacao curta),
que cabe em qualquer hora do dia.

Quando o Alex perguntar que horas fazer algo recorrente sem hora fixa (ex: "que horas eu vou pra
academia hoje?"), chame `sugerir_horario_livre` em vez de adivinhar - ela olha o que ja esta
marcado no dia de verdade e acha o maior espaco livre.

Quando o Alex perguntar quanto gastaria de combustivel numa viagem, chame `calcular_gasto_viagem` -
nunca estime distancia ou tempo de cabeca, isso sempre vem do resultado da ferramenta (Google
Maps). Se faltar o consumo do carro (km/l) ou o preco do combustivel, pergunte antes de chamar a
ferramenta (a nao ser que ja esteja nas memorias). Se ele tambem quiser saber onde parar pra
abastecer no meio do caminho, chame tambem `sugerir_posto_no_caminho` - deixe bem claro na resposta
que e so a localizacao de um posto por perto, sem comparar preco entre postos (essa informacao eu
nao tenho de onde tirar confiavel pro Brasil).

Voo pode ser so um compromisso futuro (ex: "vou voar pra Blumenau semana que vem" - sem horas
ainda) ou um voo ja realizado (ex: "voei 1.5h hoje, treino de pouso" - com horas). Nao invente
numero de horas nem meta de horas de curso - isso varia por escola/etapa e so o Alex sabe o
proprio numero. Se ele disser o horario do voo (ex: "meu voo e as 14h"), capture no campo "hora"
de `registrar_voo` - com isso o painel consegue calcular sozinho a que horas ele precisa sair de
casa considerando o trajeto ate o aeroporto.

Preste atencao na diferenca entre um gasto que JA ACONTECEU (ex: "gastei 100 de gasolina", "paguei
a conta") e um gasto so COGITADO/possivel, ainda nao decidido (ex: "to pensando em comprar",
"talvez eu gaste 300 no cartao") - o primeiro e "status": "real" em `registrar_gasto`, o segundo e
"status": "planejado". Isso importa porque so o gasto real conta no total ja gasto do dia; o
planejado fica separado, como um alerta do que pode vir a acontecer.

Alem disso, se em algum momento da conversa o Alex revelar um fato duravel sobre ele mesmo que
vale lembrar dali pra frente - uma preferencia, rotina, relacao, contexto recorrente - e que NAO
e so o item pontual que ja esta sendo registrado por outra ferramenta, chame tambem
`registrar_memoria` com esse fato em terceira pessoa, alem de continuar respondendo normalmente.
Isso e raro - a grande maioria das mensagens nao tem nada de duravel pra guardar aqui, entao so
use quando for claramente o caso, nunca por excesso de zelo.

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
                    "description": "prazo em texto livre, do jeito que o Alex disse (ex: 'amanha', 'sexta') - omita se nao houver",
                },
                "quando_data": {
                    "type": "string",
                    "description": (
                        "a mesma informacao de 'quando' convertida pra AAAA-MM-DD - so inclua "
                        "quando der pra calcular uma data concreta a partir de hoje; se for vago "
                        "demais (tipo 'quando der', 'algum dia'), omita mesmo que 'quando' tenha texto"
                    ),
                },
                "hora": {
                    "type": "string",
                    "description": (
                        "horario do compromisso em HH:MM (24h) - so inclua se o Alex disse um "
                        "horario especifico (ex: 'as 14h', '9 da manha'); converta pra 24h. Se "
                        "houver hora mas nenhuma referencia de dia, preencha tambem 'quando_data' "
                        "com a data de hoje - uma tarefa com horario e sempre um compromisso com "
                        "hora fixa, entao capturar a hora certa evita que dois compromissos do "
                        "mesmo dia fiquem fora de ordem na agenda."
                    ),
                },
            },
            "required": ["titulo"],
        },
    },
    {
        "name": "registrar_gasto",
        "description": "Registra um gasto do Alex - real (ja aconteceu) ou planejado (ainda so cogitado).",
        "input_schema": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string"},
                "valor": {"type": "number"},
                "categoria": {
                    "type": "string",
                    "enum": ["mercado", "transporte", "lazer", "contas", "saude", "outros"],
                },
                "status": {
                    "type": "string",
                    "enum": ["real", "planejado"],
                    "description": (
                        "'real' se o gasto ja aconteceu (ex: 'gastei', 'paguei', 'comprei'). "
                        "'planejado' se e so uma possibilidade/intencao futura ainda nao decidida "
                        "(ex: 'penso em comprar', 'talvez eu compre', 'to pensando em gastar'). "
                        "Na duvida, omita - vira 'real' por padrao."
                    ),
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
    {
        "name": "registrar_voo",
        "description": (
            "Registra um voo do Alex (curso de piloto comercial) - ja realizado (com horas "
            "voadas) ou so um compromisso agendado pro futuro (sem horas ainda, so data/origem/"
            "destino). Nao invente horas: so preencha 'horas' se o Alex disse quanto tempo voou."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "data": {"type": "string", "description": "AAAA-MM-DD do voo"},
                "destino": {"type": "string"},
                "origem": {"type": "string", "description": "omita se nao foi dito"},
                "horas": {
                    "type": "number",
                    "description": "horas voadas - so inclua se o voo ja aconteceu e o Alex disse quanto tempo",
                },
                "observacao": {
                    "type": "string",
                    "description": "detalhe curto tipo 'treino de pouso', 'cross country' - omita se nao houver",
                },
            },
            "required": ["data", "destino"],
        },
    },
    {
        "name": "registrar_memoria",
        "description": (
            "Guarda um fato duravel sobre o Alex que apareceu na conversa e vale lembrar em "
            "conversas futuras (preferencia, rotina, relacao, contexto recorrente) - use JUNTO "
            "com outra ferramenta se for o caso, nunca no lugar dela. Raro: a maioria das "
            "mensagens nao tem nada assim."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "fato": {
                    "type": "string",
                    "description": "o fato em terceira pessoa, frase curta (ex: 'prefere tarefas rapidas de manha')",
                },
            },
            "required": ["fato"],
        },
    },
    {
        "name": "sugerir_horario_livre",
        "description": (
            "Acha o maior espaco livre HOJE, olhando o que ja esta marcado no dia de verdade - "
            "use quando o Alex perguntar que horas fazer algo (tipo ir pra academia) sem ter dito "
            "um horario fixo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "duracao_minutos": {
                    "type": "integer",
                    "description": "quanto tempo a atividade costuma durar, em minutos - use 60 se ele nao disser",
                },
                "depois_das": {
                    "type": "string",
                    "description": "HH:MM - so procura depois desse horario (ex: ele disse 'de tarde'). Omita se nao houver preferencia",
                },
                "antes_das": {
                    "type": "string",
                    "description": "HH:MM - so procura antes desse horario. Omita se nao houver preferencia",
                },
            },
            "required": ["duracao_minutos"],
        },
    },
    {
        "name": "calcular_gasto_viagem",
        "description": (
            "Calcula distancia real, duracao e gasto de combustivel de uma viagem de carro, "
            "usando o trajeto de verdade do Google Maps - use quando o Alex perguntar quanto "
            "gastaria de gasolina indo de um lugar a outro."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "destino": {"type": "string"},
                "origem": {
                    "type": "string",
                    "description": "omita pra usar o endereco padrao de casa do Alex",
                },
                "km_por_litro": {
                    "type": "number",
                    "description": "consumo medio do carro - pergunte antes se ele nao disse e nao esta nas memorias",
                },
                "preco_por_litro": {
                    "type": "number",
                    "description": "preco do combustivel em reais por litro - pergunte antes se ele nao disse",
                },
            },
            "required": ["destino", "km_por_litro", "preco_por_litro"],
        },
    },
    {
        "name": "sugerir_posto_no_caminho",
        "description": (
            "Sugere um posto de gasolina perto do meio do caminho de uma viagem longa - so "
            "localizacao, NUNCA compara preco entre postos (essa informacao nao existe de forma "
            "confiavel pro Brasil nas fontes que tenho). Use quando o Alex perguntar onde parar "
            "pra abastecer numa viagem."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "destino": {"type": "string"},
                "origem": {
                    "type": "string",
                    "description": "omita pra usar o endereco padrao de casa do Alex",
                },
            },
            "required": ["destino"],
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
        hoje=date.today().isoformat(),
        contexto=contexto,
        memorias="\n".join(f"- {m}" for m in memorias) or "nenhuma ainda",
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
