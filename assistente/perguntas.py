"""Fase 7, faixa P2 (Perguntas de acompanhamento) - logica pura, sem banco e
sem relogio real (a data de referencia sempre vem por parametro). Usado por
assistente/gatilhos/p2_perguntas.py.

Ver docs/agentes/fase7-assistente.md (contrato comum das faixas P) e
docs/agentes/fase7-regras-faixa.md (regras da faixa).
"""

from datetime import date, datetime, timedelta

import vida

# Vida amorosa/relacionamento nunca vira aviso, pergunta nem proposta de
# memoria (decisao do Alex, ja documentada em db.py MEMORIAS_INICIAIS_FASE6
# -> "fora_do_painel"). Lista enxuta de propósito: so bloqueia o que e
# claramente do dominio "vida amorosa", pra nao apagar evento/tarefa/nota
# legitima so por citar uma palavra parecida.
PALAVRAS_RELACIONAMENTO = (
    "namorad",
    "namoro",
    "paquera",
    "crush",
    "romantico",
    "vida amorosa",
    "relacionamento amoroso",
    "pedido de casamento",
    "aniversario de namoro",
)


def eh_relacionamento(texto: str | None) -> bool:
    """True se o texto tocar em vida amorosa/relacionamento - esse assunto
    nunca vira pergunta da Caixa."""
    if not texto:
        return False
    normalizado = vida.normalizar_nome(texto)
    return any(palavra in normalizado for palavra in PALAVRAS_RELACIONAMENTO)


def texto_pergunta_conta(nome: str) -> str:
    return f'Pagou "{nome}"?'


def texto_pergunta_evento(titulo: str) -> str:
    return f'Como foi "{titulo}"? Algo a anotar?'


def texto_pergunta_tarefa(titulo: str) -> str:
    return f'Fez "{titulo}"?'


def texto_pergunta_lembrete(titulo: str) -> str:
    return f'"{titulo}" - já resolveu isso?'


def texto_pergunta_espera(quem: str, sobre: str) -> str:
    return f'Ainda esperando {quem} sobre "{sobre}"?'


def parse_data_livre(texto: str | None, hoje: date) -> date | None:
    """Aceita ISO (2026-10-01), BR (01/10/2026 ou 01-10-2026) ou so dia/mes
    (01/10, assume o ano de `hoje` ou o proximo se a data ja passou).
    None se nao der pra entender."""
    texto = (texto or "").strip()
    if not texto:
        return None
    try:
        return date.fromisoformat(texto)
    except ValueError:
        pass
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    partes = texto.replace("-", "/").split("/")
    if len(partes) == 2:
        try:
            dia, mes = int(partes[0]), int(partes[1])
            candidata = date(hoje.year, mes, dia)
            if candidata < hoje:
                candidata = date(hoje.year + 1, mes, dia)
            return candidata
        except ValueError:
            return None
    return None


def data_adiar_tarefa(opcao: str, hoje: date, texto: str = "") -> date | None:
    """Traduz a opcao escolhida em 'Adiar pra quando?' numa data. None se a
    opcao nao for reconhecida ou a data livre nao der pra entender."""
    if opcao == "amanha":
        return hoje + timedelta(days=1)
    if opcao == "proxima_semana":
        return hoje + timedelta(days=7)
    if opcao == "escolher_data":
        return parse_data_livre(texto, hoje)
    if opcao == "adiar":
        # resposta generica de "adiar" sem sub-escolha (ex.: front antigo) -
        # cai no mesmo padrao de "amanha".
        return hoje + timedelta(days=1)
    return None


def limiar_espera_dias(valor_config: str | None, padrao: int = 3) -> int:
    """Le a configuracao 'assistente.p2.espera_dias' (texto) e devolve um
    inteiro positivo, caindo pro padrao se estiver vazia/invalida/<= 0."""
    if valor_config is None:
        return padrao
    try:
        numero = int(str(valor_config).strip())
    except (TypeError, ValueError):
        return padrao
    return numero if numero > 0 else padrao


def flag_ativa(valor_config: str | None) -> bool:
    """Le a configuracao 'assistente.p2.ativo' - padrao ligado (None ou
    qualquer valor que nao seja um jeito claro de dizer 'nao')."""
    if valor_config is None:
        return True
    return str(valor_config).strip().lower() not in ("0", "false", "nao", "não", "off")
