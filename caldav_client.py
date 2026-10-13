"""Calendario da Apple/iCloud via CalDAV - leitura de todos os calendarios
(pro resumo do dia) + escrita (Fase 6, US-E14) restrita a UM calendario
proprio do painel.

So fica ativo quando ICLOUD_USERNAME e ICLOUD_APP_PASSWORD existem no
.env. A senha tem que ser uma "senha especifica de app" gerada em
appleid.apple.com (Seguranca > Senhas de app) - a senha normal da sua
Apple ID NAO funciona aqui por causa do 2FA.

Uso pretendido: mostrar os compromissos de hoje no resumo do dia, evitar
mandar notificacao push bem na hora de um compromisso, e (US-E14) criar/
apagar evento no calendario "Painel" a pedido do Alex (chat ou tela) -
decisao dele, registrada aqui: o painel NUNCA cria/edita/apaga nada em
qualquer outro calendario do iCloud (trabalho, familia etc), e so apaga um
evento do calendario "Painel" se o UID estiver registrado na tabela local
`eventos_criados` (db.py) como tendo sido criado pelo proprio painel -
quem decide isso e app.py, ANTES de chamar apagar_evento aqui.
"""

import os
import uuid
from datetime import date, datetime, time, timedelta

import caldav

ICLOUD_URL = "https://caldav.icloud.com/"
CALENDARIO_PAINEL_NOME = "Painel"


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


class NaoConfiguradoError(RuntimeError):
    """iCloud nao configurado (ICLOUD_USERNAME/ICLOUD_APP_PASSWORD ausentes) -
    quem chama (app.py) converte isso num 'erro' de resposta em vez de deixar
    a rota quebrar com 500."""


def _calendario_painel(client: caldav.DAVClient) -> caldav.Calendar:
    """Acha o calendario 'Painel' do principal pelo nome de exibicao; cria se
    ainda nao existir (primeira vez que o app tenta escrever algo). NUNCA
    devolve outro calendario - se o Alex tiver renomeado o "Painel" fora do
    app, um calendario novo com esse nome e criado (melhor um calendario
    novo do que escrever sem querer no calendario errado)."""
    principal = client.principal()
    for calendario in principal.calendars():
        try:
            nome = calendario.get_display_name()
        except Exception:
            continue
        if nome == CALENDARIO_PAINEL_NOME:
            return calendario
    return principal.make_calendar(name=CALENDARIO_PAINEL_NOME)


def criar_evento(titulo: str, inicio: datetime, fim: datetime, lembrar_min_antes: int | None = None) -> dict:
    """Cria um evento NOVO no calendario 'Painel' (cria o calendario se for
    a primeira vez) e devolve {"uid", "titulo", "inicio", "fim"} - quem
    chama (app.py) grava esse uid em `eventos_criados` (db.py), a unica
    fonte de verdade de "o painel pode desfazer isso". O uid e gerado aqui
    (nao deixa o servidor CalDAV escolher) pra ficar garantido de bater com
    o que sera gravado localmente."""
    if not configurado():
        raise NaoConfiguradoError("Agenda do iCloud não configurada (ICLOUD_USERNAME/ICLOUD_APP_PASSWORD).")
    uid = str(uuid.uuid4())
    alarm_kwargs = {}
    if lembrar_min_antes is not None and lembrar_min_antes >= 0:
        alarm_kwargs = {
            "alarm_trigger": timedelta(minutes=-lembrar_min_antes),
            "alarm_action": "DISPLAY",
            "alarm_description": "Lembrete",
        }
    with _client() as client:
        calendario = _calendario_painel(client)
        calendario.add_event(uid=uid, dtstart=inicio, dtend=fim, summary=titulo, **alarm_kwargs)
    return {"uid": uid, "titulo": titulo, "inicio": inicio.isoformat(), "fim": fim.isoformat()}


def apagar_evento(uid: str) -> bool:
    """Apaga o evento de UID `uid` do calendario 'Painel', se existir la.
    So a MECANICA de apagar mora aqui - a decisao de "esse uid pode ser
    apagado porque foi o painel que criou" e responsabilidade de quem chama
    (ver exec_apagar_evento/apagar_evento_rota em app.py, que confere
    `eventos_criados` no banco local ANTES de chegar aqui). Devolve False
    se o evento ja nao existir mais no calendario (idempotente - apagar de
    novo nao e erro)."""
    if not configurado():
        raise NaoConfiguradoError("Agenda do iCloud não configurada (ICLOUD_USERNAME/ICLOUD_APP_PASSWORD).")
    with _client() as client:
        calendario = _calendario_painel(client)
        evento = _achar_por_uid(calendario, uid)
        if evento is None:
            return False
        evento.delete()
    return True


def _achar_por_uid(calendario, uid: str):
    """iCloud recusa a busca por UID do caldav (`event_by_uid` -> REPORT com filtro de UID ->
    "412 Precondition Failed", visto em 2026-10-13 no primeiro teste real). Tenta ela primeiro
    (servidor que aceita), depois o endereco direto - `add_event(uid=...)` grava em
    `<calendario>/<uid>.ics` - e por ultimo varre o calendario 'Painel' (so tem o que o painel
    criou). Sempre confere o UID antes de devolver: nunca apaga outro evento."""
    def _uid_de(ev):
        try:
            return str(ev.icalendar_component.get("UID"))
        except Exception:
            return None

    try:
        return calendario.event_by_uid(uid)
    except Exception:
        pass
    try:
        ev = calendario.event_by_url(calendario.url.join(f"{uid}.ics"))
        ev.load()
        if _uid_de(ev) == uid:
            return ev
    except Exception:
        pass
    try:
        for ev in calendario.events():
            if _uid_de(ev) == uid:
                return ev
    except Exception:
        pass
    return None
