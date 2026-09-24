"""Quebra/requebra de tarefa, plano do dia, mala de viagem e resumo de link.
Dona futura: faixa A8 (Fase 7). Extraido de claude_client.py sem mudar
comportamento; claude_client.py reexporta estes nomes."""
from datetime import datetime

from ia.legado import HAIKU, SONNET, _extract_json, _usage, client


BREAKDOWN_PROMPT = """Quebre esta tarefa em 3 a 6 passos pequenos e concretos, cada um algo que da pra fazer de uma vez.
Responda so com um JSON de lista de strings, sem markdown.

Tarefa: {title}"""


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


def break_down_task(title: str) -> tuple[list[str], dict]:
    response = client.messages.create(
        model=SONNET,
        max_tokens=300,
        messages=[{"role": "user", "content": BREAKDOWN_PROMPT.format(title=title)}],
    )
    return _extract_json(response.content[0].text), _usage(response)


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


REQUEBRAR_PROMPT = """A tarefa abaixo esta travada ha {dias} dias - a pessoa tem TDAH e o jeito
que ela estava quebrada nao funcionou. Proponha um jeito DIFERENTE de atacar, em 3 a 5 passos.
O primeiro passo tem que ser ridiculamente facil, de 2 a 5 minutos (abrir o arquivo, mandar uma
mensagem de uma linha, separar o material) - o objetivo e so comecar. Sem repetir os passos
antigos do mesmo jeito.

Tarefa: {titulo}
Passos antigos que nao andaram: {passos}

Responda so com um JSON de lista de strings, sem markdown."""


def requebrar_tarefa(titulo: str, dias: int, passos_antigos: list[str]) -> tuple[list[str], dict]:
    response = client.messages.create(
        model=SONNET,
        max_tokens=350,
        messages=[
            {
                "role": "user",
                "content": REQUEBRAR_PROMPT.format(
                    titulo=titulo, dias=dias, passos="; ".join(passos_antigos) or "nenhum"
                ),
            }
        ],
    )
    return _extract_json(response.content[0].text), _usage(response)


MALA_PROMPT = """Monte um checklist de mala CURTO e pratico pra uma viagem. A pessoa tem TDAH:
itens concretos, sem obviedade tipo "roupas" solto - diga quantidade quando fizer sentido.
Maximo 15 itens. Inclua documento se for voo/viagem longa.

Destino: {destino}
Dias: {dias}
Motivo: {motivo}
Clima previsto: {clima}

Responda so com um JSON de lista de strings, sem markdown."""


def gerar_mala(destino: str, dias: int, motivo: str | None, clima_texto: str | None) -> tuple[list[str], dict]:
    response = client.messages.create(
        model=HAIKU,
        max_tokens=400,
        messages=[
            {
                "role": "user",
                "content": MALA_PROMPT.format(
                    destino=destino, dias=dias, motivo=motivo or "nao informado", clima=clima_texto or "sem previsao"
                ),
            }
        ],
    )
    return _extract_json(response.content[0].text), _usage(response)


RESUMO_LINK_PROMPT = """Resuma pra uma pessoa com TDAH decidir se vale ler/ver agora: 3 a 5
pontos curtos com o que importa de verdade, em portugues do Brasil. Se o texto for so pagina de
login/cookie/erro sem conteudo, diga isso numa frase. Nao invente o que nao esta no texto.

Titulo: {titulo}
Texto (pode estar cortado):
{texto}

Responda so com o resumo em topicos comecando com "- ", sem introducao."""


def resumir_link(titulo: str | None, texto: str) -> tuple[str, dict]:
    response = client.messages.create(
        model=HAIKU,
        max_tokens=400,
        messages=[{"role": "user", "content": RESUMO_LINK_PROMPT.format(titulo=titulo or "sem titulo", texto=texto)}],
    )
    return response.content[0].text.strip(), _usage(response)
