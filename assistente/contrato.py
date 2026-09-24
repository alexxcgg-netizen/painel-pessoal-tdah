# assistente/contrato.py — contrato da Etapa 0. As funcoes delegam pra implementacao real
# (assistente/caixa.py da P1a, assistente/avisos.py da P8), entao importar daqui ou de la da no mesmo.


def enfileirar(tipo: str, titulo: str, corpo: str = "", *, opcoes: list | None = None,
               origem: str = "", chave_unica: str = "", repetir: dict | None = None,
               vence_em: str | None = None) -> str:
    """Cria um item na Caixa e devolve o id. tipo: pergunta | aviso | sugestao |
    briefing | proposta_memoria. chave_unica evita duplicar o mesmo item.
    repetir: {"apos_minutos": [120, 240], "max_por_dia": 3}. Implementado na P1a."""
    from assistente import caixa
    return caixa.enfileirar(tipo, titulo, corpo, opcoes=opcoes, origem=origem,
                            chave_unica=chave_unica, repetir=repetir, vence_em=vence_em)


def resolver(item_id: str, resposta: str, texto: str = "") -> None:
    """Registra a resposta (ex.: 'sim', 'nao', 'adiar', 'aceitar', 'recusar') e
    encerra ou adia o item. Implementado na P1a."""
    from assistente import caixa
    return caixa.resolver(item_id, resposta, texto)


def aviso_permitido(tipo: str) -> bool:
    """False se o tipo esta desligado ou dentro do horario de silencio.
    Implementado na P8. Todo mundo consulta antes de enviar push."""
    from assistente import avisos
    return avisos.aviso_permitido(tipo)
