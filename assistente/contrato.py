# assistente/contrato.py — copiado na Etapa 0, so a P1a implementa, compativel com isto


def enfileirar(tipo: str, titulo: str, corpo: str = "", *, opcoes: list | None = None,
               origem: str = "", chave_unica: str = "", repetir: dict | None = None,
               vence_em: str | None = None) -> str:
    """Cria um item na Caixa e devolve o id. tipo: pergunta | aviso | sugestao |
    briefing | proposta_memoria. chave_unica evita duplicar o mesmo item.
    repetir: {"apos_minutos": [120, 240], "max_por_dia": 3}. Implementado na P1a."""
    raise NotImplementedError


def resolver(item_id: str, resposta: str, texto: str = "") -> None:
    """Registra a resposta (ex.: 'sim', 'nao', 'adiar', 'aceitar', 'recusar') e
    encerra ou adia o item. Implementado na P1a."""
    raise NotImplementedError


def aviso_permitido(tipo: str) -> bool:
    """False se o tipo esta desligado ou dentro do horario de silencio.
    Implementado na P8. Todo mundo consulta antes de enviar push."""
    raise NotImplementedError
