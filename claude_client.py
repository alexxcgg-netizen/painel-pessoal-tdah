import json
import os
from datetime import date

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
{{"tipo": "tarefa" ou "gasto" ou "meta", "titulo": "...", "valor": numero ou null, "categoria": "..." ou null, "quando": "..." ou null, "prazo": "AAAA-MM-DD" ou null, "duvida": "..." ou null}}

Categorias de gasto: mercado, transporte, lazer, contas, saude, outros.

Se tipo="meta": "valor" e o valor total que a pessoa quer juntar, e "prazo" e a data limite no
formato AAAA-MM-DD - calcule a partir de hoje ({hoje}) se o texto disser algo relativo tipo
"ate dezembro" ou "em 6 meses". Se nao houver prazo claro no texto, deixe "prazo" como null.

Preencha "duvida" APENAS se o texto for realmente ambiguo demais pra classificar com confianca
(ex: nao da pra saber se e tarefa, gasto ou meta, ou um gasto/meta sem valor nenhum). Nesse caso
"duvida" deve ser uma pergunta curta e direta pra esclarecer, e os outros campos podem vir com o
melhor palpite. Se o texto for razoavelmente claro, deixe "duvida" como null - nao pergunte por
excesso de zelo.

Texto: {text}"""

BREAKDOWN_PROMPT = """Quebre esta tarefa em 3 a 6 passos pequenos e concretos, cada um algo que da pra fazer de uma vez.
Responda so com um JSON de lista de strings, sem markdown.

Tarefa: {title}"""

SUMMARY_PROMPT = """Escreva um resumo do dia em 2 a 3 frases. Tom neutro e factual, sem cobranca e sem elogio vazio.
Se houver compromissos na agenda, mencione quantos tem e se o dia esta cheio ou tranquilo -
sem repetir cada horario, so o suficiente pra dar uma nocao geral.

Tarefas concluidas: {done}
Tarefas pendentes: {pending}
Gastos de hoje: {expenses}
Compromissos na agenda hoje: {eventos}"""


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
    done: list[str], pending: list[str], expenses: list[dict], eventos: list[str] | None = None
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
                ),
            }
        ],
    )
    return response.content[0].text.strip(), _usage(response)
