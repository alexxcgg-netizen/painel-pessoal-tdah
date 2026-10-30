"""Quebra/requebra de tarefa, plano do dia, mala de viagem e resumo de link.
Dona: faixa A8 (Fase 7, Migracao 2). Migrado de chamada direta ao SDK Anthropic
(ia/legado.py) pra ia.core.chamar_ia (ia/config.d/<funcao>.json escolhe o
modelo). claude_client.py continua reexportando estes nomes.

Assinatura e retorno de cada funcao publica sao IDENTICOS aos de antes da
migracao: tupla (resultado, usage), com `usage` no formato que app.py espera
(app.py:359 `_log_usage` le usage["model"/"input_tokens"/"output_tokens"/
"cost_usd"]) - ver `_usage_de` abaixo.

Prompt fixo (instrucao que nunca muda) vai em `contexto_fixo`; os dados que
mudam a cada chamada (titulo da tarefa, destino, texto da pagina...) vao nas
`mensagens`, como manda ia/config.d/README.md - isso deixa o prefixo estavel
pronto pro cache de prompt do provedor, mesmo com `cache.ativo: false` hoje.

Erro (rede, provedor, teto mensal estourado, JSON fora do schema) nunca sobe
de ia.core.chamar_ia - vira Resposta(ok=False, erro=...). Pra nao mudar o
contrato de app.py:_call_claude (so pega anthropic.APIError e
(ValueError, KeyError)), toda falha aqui vira ValueError - ver `_falhar`. Isso
inclui teto_ia_estourado, que antes da migracao NENHUMA destas 5 funcoes
verificava (so classify_capture/classify_intent, ver app.py:869); com
chamar_ia isso passa a valer de graca pra estas 5 tambem (resolve a pendencia
"mala e PDF de cotacao fora do teto" da Fase 6 - PDF de cotacao e da faixa
A9/ia/funcoes/visao.py, fora do escopo A8)."""
from datetime import datetime

from ia import core
from ia.contrato import Resposta

# --------------------------------------------------------------------------
# Helpers compartilhados pelas 5 funcoes desta faixa
# --------------------------------------------------------------------------


def _usage_de(resp: Resposta) -> dict:
    """Usage no formato que app.py espera (app.py:359 _log_usage)."""
    return {
        "model": resp.modelo,
        "input_tokens": resp.tokens_in,
        "output_tokens": resp.tokens_out,
        "cost_usd": resp.custo_usd,
    }


def _falhar(funcao: str, resp: Resposta) -> None:
    """Levanta ValueError com a mensagem de erro do nucleo. app.py:411
    (_call_claude) so pega anthropic.APIError e (ValueError, KeyError) - com
    chamar_ia nunca mais sobe anthropic.APIError (o nucleo absorve o erro do
    provedor e devolve Resposta(ok=False)), entao toda falha (rede, provedor,
    JSON fora do schema, teto) cai no mesmo bucket ValueError -> 502
    CLAUDE_FORMAT_ERROR_MSG. Antes da migracao havia 2 mensagens diferentes
    (CLAUDE_ERROR_MSG pra erro de rede/provedor, CLAUDE_FORMAT_ERROR_MSG pra
    JSON invalido) - a distincao se perde aqui. Anotado em
    scripts/ralph-a8-migracao2/progress.txt pro integrador avaliar se vale
    a pena app.py reconhecer resp.erro == "teto_ia_estourado" (nao editamos
    app.py, fora da lista de arquivos desta faixa)."""
    # C1: excecao dedicada (subclasse de ValueError): teto -> TetoEstourado,
    # rede/provedor -> ErroProvedor, JSON/schema -> RespostaInvalida.
    raise core.excecao_de_resposta(funcao, resp)


# --------------------------------------------------------------------------
# break_down_task
# --------------------------------------------------------------------------

FUNCAO_BREAKDOWN = "break_down_task"

BREAKDOWN_PROMPT = """Quebre a tarefa em 3 a 6 passos pequenos e concretos, cada um algo que da pra
fazer de uma vez. Responda so com o JSON pedido, sem explicacao, sem markdown."""

SCHEMA_BREAKDOWN = {
    "type": "object",
    "properties": {
        "passos": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 6},
    },
    "required": ["passos"],
    "additionalProperties": False,
}


def break_down_task(title: str) -> tuple[list[str], dict]:
    resp = core.chamar_ia(
        FUNCAO_BREAKDOWN,
        [{"role": "user", "content": f"Tarefa: {title}"}],
        contexto_fixo=BREAKDOWN_PROMPT,
        schema=SCHEMA_BREAKDOWN,
    )
    if not resp.ok:
        _falhar(FUNCAO_BREAKDOWN, resp)
    return resp.dados["passos"], _usage_de(resp)


# --------------------------------------------------------------------------
# requebrar_tarefa
# --------------------------------------------------------------------------

FUNCAO_REQUEBRAR = "requebrar_tarefa"

REQUEBRAR_PROMPT = """A tarefa esta travada ha alguns dias - a pessoa tem TDAH e o jeito que ela
estava quebrada nao funcionou. Proponha um jeito DIFERENTE de atacar, em 3 a 5 passos. O primeiro
passo tem que ser ridiculamente facil, de 2 a 5 minutos (abrir o arquivo, mandar uma mensagem de
uma linha, separar o material) - o objetivo e so comecar. Sem repetir os passos antigos do mesmo
jeito. Responda so com o JSON pedido, sem explicacao, sem markdown."""

SCHEMA_REQUEBRAR = {
    "type": "object",
    "properties": {
        "passos": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 5},
    },
    "required": ["passos"],
    "additionalProperties": False,
}


def requebrar_tarefa(titulo: str, dias: int, passos_antigos: list[str]) -> tuple[list[str], dict]:
    conteudo = (
        f"Tarefa: {titulo}\n"
        f"Dias travada: {dias}\n"
        f"Passos antigos que nao andaram: {'; '.join(passos_antigos) or 'nenhum'}"
    )
    resp = core.chamar_ia(
        FUNCAO_REQUEBRAR,
        [{"role": "user", "content": conteudo}],
        contexto_fixo=REQUEBRAR_PROMPT,
        schema=SCHEMA_REQUEBRAR,
    )
    if not resp.ok:
        _falhar(FUNCAO_REQUEBRAR, resp)
    return resp.dados["passos"], _usage_de(resp)


# --------------------------------------------------------------------------
# remedio_travou (Grupo A do Laboratorio v4, 30/10/2026: "Por que travou?")
# --------------------------------------------------------------------------

FUNCAO_REMEDIO_TRAVOU = "remedio_travou"

REMEDIO_TRAVOU_PROMPT = """A pessoa tem TDAH e empurrou esta tarefa varias vezes. Ela disse por que travou. Fale com ela
por "tu", direto, sem bronca e sem enrolacao. Responda conforme o motivo:
- dificil: "texto" = UM passo de 2 minutos, concreto e fisico (abrir, achar, salvar), que NAO resolve a tarefa, so comeca. "lista" = [].
- medo: "texto" = "" e "lista" = o roteiro de 3 falas curtas, prontas pra ela dizer ou escrever (primeira pessoa, educada, sem enfeite).
- sem_rumo: "texto" = o PRIMEIRO passo, de ate 5 minutos (ex.: descobrir como se faz). "lista" = 3 ou 4 passos curtos na ordem, o primeiro ridiculamente facil.
Nao invente fatos (preco, prazo, telefone, site). Responda so com o JSON pedido, sem markdown."""

SCHEMA_REMEDIO_TRAVOU = {
    "type": "object",
    "properties": {
        "texto": {"type": "string"},
        "lista": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
    },
    "required": ["texto", "lista"],
    "additionalProperties": False,
}


def remedio_travou(titulo: str, motivo: str) -> tuple[dict, dict]:
    resp = core.chamar_ia(
        FUNCAO_REMEDIO_TRAVOU,
        [{"role": "user", "content": f"Tarefa: {titulo}\nMotivo: {motivo}"}],
        contexto_fixo=REMEDIO_TRAVOU_PROMPT,
        schema=SCHEMA_REMEDIO_TRAVOU,
    )
    if not resp.ok:
        _falhar(FUNCAO_REMEDIO_TRAVOU, resp)
    return resp.dados, _usage_de(resp)


# --------------------------------------------------------------------------
# gerar_mala
# --------------------------------------------------------------------------

FUNCAO_MALA = "gerar_mala"

MALA_PROMPT = """Monte um checklist de mala CURTO e pratico pra uma viagem. A pessoa tem TDAH: itens
concretos, sem obviedade tipo "roupas" solto - diga quantidade quando fizer sentido. Maximo 15
itens. Inclua documento se for voo/viagem longa. Responda so com o JSON pedido, sem explicacao,
sem markdown."""

SCHEMA_MALA = {
    "type": "object",
    "properties": {
        "itens": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 15},
    },
    "required": ["itens"],
    "additionalProperties": False,
}


def gerar_mala(destino: str, dias: int, motivo: str | None, clima_texto: str | None) -> tuple[list[str], dict]:
    conteudo = (
        f"Destino: {destino}\n"
        f"Dias: {dias}\n"
        f"Motivo: {motivo or 'nao informado'}\n"
        f"Clima previsto: {clima_texto or 'sem previsao'}"
    )
    resp = core.chamar_ia(
        FUNCAO_MALA,
        [{"role": "user", "content": conteudo}],
        contexto_fixo=MALA_PROMPT,
        schema=SCHEMA_MALA,
    )
    if not resp.ok:
        _falhar(FUNCAO_MALA, resp)
    return resp.dados["itens"], _usage_de(resp)


# --------------------------------------------------------------------------
# resumir_link
# --------------------------------------------------------------------------

FUNCAO_RESUMO_LINK = "resumir_link"

# Texto da pagina e truncado ANTES de mandar pro modelo (custo/teto): 12.000
# caracteres, cortando no fim de frase mais proximo do limite (". ", "! ",
# "? ") pra nao mandar uma sentenca pela metade. Se nao achar um fim de frase
# a menos de metade do limite de distancia, corta seco mesmo (texto sem
# pontuacao reconhecivel, ex.: paginas so com listas/tabelas).
LIMITE_TEXTO_RESUMO_LINK = 12_000

RESUMO_LINK_PROMPT = """Resuma pra uma pessoa com TDAH decidir se vale ler/ver agora: 3 a 5 pontos
curtos com o que importa de verdade, em portugues do Brasil. Se o texto for so pagina de
login/cookie/erro sem conteudo, diga isso numa frase. Nao invente o que nao esta no texto.
Responda so com o resumo em topicos comecando com "- ", sem introducao."""


def _truncar_para_resumo(texto: str, limite: int = LIMITE_TEXTO_RESUMO_LINK) -> str:
    """Corta `texto` em ate `limite` caracteres. Prefere parar no fim de uma frase
    (". ", "! ", "? ", ou as mesmas seguidas de quebra de linha) mais proximo do
    limite, contanto que isso nao jogue fora mais da metade do trecho; senao corta
    seco no limite mesmo."""
    if len(texto) <= limite:
        return texto
    cortado = texto[:limite]
    melhor = -1
    for marca in (". ", "! ", "? ", ".\n", "!\n", "?\n"):
        pos = cortado.rfind(marca)
        if pos > melhor:
            melhor = pos
    if melhor >= limite // 2:
        return cortado[: melhor + 1].rstrip()
    return cortado.rstrip()


def resumir_link(titulo: str | None, texto: str) -> tuple[str, dict]:
    texto_truncado = _truncar_para_resumo(texto)
    conteudo = f"Titulo: {titulo or 'sem titulo'}\nTexto (pode estar cortado):\n{texto_truncado}"
    resp = core.chamar_ia(
        FUNCAO_RESUMO_LINK,
        [{"role": "user", "content": conteudo}],
        contexto_fixo=RESUMO_LINK_PROMPT,
    )
    if not resp.ok:
        _falhar(FUNCAO_RESUMO_LINK, resp)
    return (resp.texto or "").strip(), _usage_de(resp)


# --------------------------------------------------------------------------
# plano_do_dia
# --------------------------------------------------------------------------

FUNCAO_PLANO_DO_DIA = "plano_do_dia"

PLANO_PROMPT = """Voce ajuda uma pessoa com TDAH a organizar o resto do dia.

Os compromissos da agenda tem horario FIXO e nao podem mudar - use como ancoras. As tarefas
pendentes NAO tem horario marcado - sugira em que ordem encaixa-las ao longo do dia (antes, entre
ou depois dos compromissos), pensando em coisas como: tarefa rapida antes de sair de casa, tarefa
que depende de estar em algum lugar perto de um compromisso que ja leva pra la, tarefa urgente
primeiro se nao houver pista de prioridade.

Coisas duraveis que voce sabe sobre a pessoa servem so se ajudarem a ordenar melhor - nao force.

Responda em lista numerada curta (maximo 6 itens), cada item uma linha, direto ao ponto. Tom
neutro, sem cobranca. Se nao houver tarefa nem compromisso nenhum, diga isso em uma frase."""


def plano_do_dia(
    tarefas: list[str], eventos: list[dict], memorias: list[str] | None = None
) -> tuple[str, dict]:
    eventos_fmt = [
        f"{e['titulo']} as {e['inicio'][11:16]}" for e in eventos if not e.get("dia_inteiro")
    ]
    conteudo = (
        f"Agora sao {datetime.now().strftime('%H:%M')}.\n"
        f"Compromissos de hoje (hora fixa): {eventos_fmt or 'nenhum'}\n"
        f"Tarefas pendentes (sem hora fixa): {tarefas or 'nenhuma'}\n"
        f"Coisas duraveis sobre a pessoa: {memorias or 'nenhuma ainda'}"
    )
    resp = core.chamar_ia(
        FUNCAO_PLANO_DO_DIA,
        [{"role": "user", "content": conteudo}],
        contexto_fixo=PLANO_PROMPT,
    )
    if not resp.ok:
        _falhar(FUNCAO_PLANO_DO_DIA, resp)
    return (resp.texto or "").strip(), _usage_de(resp)
