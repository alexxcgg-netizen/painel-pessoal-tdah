"""Leitura do Calendario da Apple/iCloud via CalDAV - so pra saber o que
esta na sua agenda, nao mexe em nada la (so leitura).

So fica ativo quando ICLOUD_USERNAME e ICLOUD_APP_PASSWORD existem no
.env. A senha tem que ser uma "senha especifica de app" gerada em
appleid.apple.com (Seguranca > Senhas de app) - a senha normal da sua
Apple ID NAO funciona aqui por causa do 2FA.

Uso pretendido: mostrar os compromissos de hoje no resumo do dia, e no
futuro (quando tiver um agendador rodando - ver README) evitar mandar
notificacao push bem na hora de um compromisso.
"""

import os
from datetime import date, datetime, time

import caldav

ICLOUD_URL = "https://caldav.icloud.com/"


def configurado() -> bool:
    return bool(os.environ.get("ICLOUD_USERNAME") and os.environ.get("ICLOUD_APP_PASSWORD"))


def _client() -> caldav.DAVClient:
    return caldav.DAVClient(
        url=ICLOUD_URL,
        username=os.environ["ICLOUD_USERNAME"],
        password=os.environ["ICLOUD_APP_PASSWORD"],
    )


def _extrair_evento(obj) -> dict | None:
    comp = obj.icalendar_component
    if "DTSTART" not in comp:
        return None
    inicio = comp["DTSTART"].dt
    fim = comp["DTEND"].dt if "DTEND" in comp else inicio
    dia_inteiro = not isinstance(inicio, datetime)
    # iCloud manda horario com fuso (TZID); o resto do app trabalha com hora
    # local sem fuso - comparar os dois estoura TypeError. Converte uma vez aqui.
    if isinstance(inicio, datetime) and inicio.tzinfo is not None:
        inicio = inicio.astimezone().replace(tzinfo=None)
    if isinstance(fim, datetime) and fim.tzinfo is not None:
        fim = fim.astimezone().replace(tzinfo=None)
    return {
        "titulo": str(comp.get("SUMMARY", "Sem titulo")),
        "inicio": inicio.isoformat(),
        "fim": fim.isoformat(),
        "dia_inteiro": dia_inteiro,
    }


def eventos_do_dia(dia: date) -> list[dict]:
    """Busca eventos de todos os calendarios do dia informado. Se algum
    calendario individual falhar (iCloud e instavel via CalDAV as vezes),
    pula ele e continua com os outros em vez de quebrar tudo."""
    inicio = datetime.combine(dia, time.min)
    fim = datetime.combine(dia, time.max)

    eventos = []
    with _client() as client:
        principal = client.principal()
        for calendario in principal.calendars():
            try:
                resultados = calendario.search(start=inicio, end=fim, event=True, expand=True)
            except Exception:
                continue
            for r in resultados:
                try:
                    evento = _extrair_evento(r)
                except Exception:
                    evento = None
                if evento:
                    eventos.append(evento)

    eventos.sort(key=lambda e: e["inicio"])
    return eventos


def horario_ocupado(inicio: datetime, fim: datetime) -> bool:
    """Confere se ha algum evento no calendario que se sobrepoe ao intervalo
    dado. Pensado pro futuro agendador de notificacoes usar antes de mandar
    um push - ainda nao esta plugado em nada automatico (ver README)."""
    for evento in eventos_do_dia(inicio.date()):
        if evento["dia_inteiro"]:
            continue
        ev_inicio = datetime.fromisoformat(evento["inicio"])
        ev_fim = datetime.fromisoformat(evento["fim"])
        if inicio < ev_fim and fim > ev_inicio:
            return True
    return False
