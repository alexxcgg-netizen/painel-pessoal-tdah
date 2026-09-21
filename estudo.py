"""Rotina de estudo (pura, sem IA) - sugere UM tema por vez de uma lista
fixa que o proprio Alex definiu (pra nao se dispersar com assunto que nao
pediu), sempre o proximo da fila (round-robin). Ajustar a lista aqui exige
mexer no codigo de proposito - isso nao e um campo livre pra IA preencher."""

TEMAS = [
    "Regulamentacao (RBAC/RBHA)",
    "Meteorologia aeronautica",
    "Navegacao",
]


def proximo_tema(indice_atual: int) -> tuple[str, int]:
    """Devolve (tema, proximo_indice) - o tema no indice atual (com volta
    ao inicio se passar do fim da lista) e o indice que deve ser guardado
    pra proxima chamada continuar de onde parou."""
    indice = indice_atual % len(TEMAS)
    proximo_indice = (indice + 1) % len(TEMAS)
    return TEMAS[indice], proximo_indice
