import json
import os

from anthropic import Anthropic

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-5"

CAPTURE_PROMPT = """Classifique o texto do usuario como "tarefa" ou "gasto" e extraia os campos.
Responda so com JSON, sem markdown, no formato:
{{"tipo": "tarefa" ou "gasto", "titulo": "...", "valor": numero ou null, "categoria": "..." ou null, "quando": "..." ou null}}

Categorias de gasto: mercado, transporte, lazer, contas, saude, outros.

Texto: {text}"""

BREAKDOWN_PROMPT = """Quebre esta tarefa em 3 a 6 passos pequenos e concretos, cada um algo que da pra fazer de uma vez.
Responda so com um JSON de lista de strings, sem markdown.

Tarefa: {title}"""

SUMMARY_PROMPT = """Escreva um resumo do dia em 2 a 3 frases. Tom neutro e factual, sem cobranca e sem elogio vazio.

Tarefas concluidas: {done}
Tarefas pendentes: {pending}
Gastos de hoje: {expenses}"""


def _extract_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def classify_capture(text: str) -> dict:
    response = client.messages.create(
        model=HAIKU,
        max_tokens=200,
        messages=[{"role": "user", "content": CAPTURE_PROMPT.format(text=text)}],
    )
    return _extract_json(response.content[0].text)


def break_down_task(title: str) -> list[str]:
    response = client.messages.create(
        model=SONNET,
        max_tokens=300,
        messages=[{"role": "user", "content": BREAKDOWN_PROMPT.format(title=title)}],
    )
    return _extract_json(response.content[0].text)


def summarize_day(done: list[str], pending: list[str], expenses: list[dict]) -> str:
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
                ),
            }
        ],
    )
    return response.content[0].text.strip()
