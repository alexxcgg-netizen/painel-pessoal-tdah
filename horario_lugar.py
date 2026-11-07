"""'Ta aberto?' (leva 07/11/2026, frente D - docs/briefings/2026-11-07-lugar-certo-e-avisos.md).

Le o horario que o Google devolve (maps_client.dados_horario: Places API New, `regularOpeningHours`,
`currentOpeningHours` e `businessStatus`) e responde se o lugar esta aberto numa hora:
aberto ate X, fecha em menos de 30 min, fechado (abre Y), fechado temporariamente, fechou de vez.

- `currentOpeningHours` (periodos com `date`) cobre feriado e horario especial dos proximos 7 dias -
  dentro dessa janela ele manda; fora dela vale o `regularOpeningHours` (semana tipica).
- Sem dado (cota, rede, Google sem horario) -> None: ninguem afirma nada.
- Horas sempre no fuso local (Brusque); o Google devolve no fuso do lugar, que e o mesmo.

Tambem faz o automatico: tarefa de hoje com lugar e hora confere o horario na hora de chegada
(uma consulta por tarefa por dia/chegada, guardada em tasks.extras["horario_lugar"]); fechado ou
fechando vira linha no card (cards.card_tarefas_criadas) e aviso `lugar_fechado` (app.verificar_e_notificar).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

FECHA_LOGO_MIN = 30  # chega com menos de 30 min antes de fechar = "fechando"
ESTADOS_ALERTA = ("fechado", "fechando", "fechado_temporariamente", "fechado_de_vez")
_DIAS = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")
_RE_HORA = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
# lugar que nao e comercio: nao vale perguntar horario ao Google
_SEM_HORARIO = {"casa", "minha casa", "em casa", "aqui", "trabalho", "obra"}


# ---------------------------------------------------------------- leitura dos periodos

def _int(v, padrao=0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return padrao


def _ponto_com_data(p) -> datetime | None:
    """Ponto do currentOpeningHours ({date:{year,month,day}, hour, minute}) -> datetime local."""
    if not isinstance(p, dict) or not isinstance(p.get("date"), dict):
        return None
    d = p["date"]
    try:
        base = datetime(int(d["year"]), int(d["month"]), int(d["day"]))
    except (KeyError, TypeError, ValueError):
        return None
    return base + timedelta(hours=_int(p.get("hour")), minutes=_int(p.get("minute")))


def _e_24h(periodos) -> bool:
    """Google: aberto sempre = um periodo so, abre domingo 00:00, sem `close`."""
    return any(isinstance(p, dict) and isinstance(p.get("open"), dict) and not p.get("close") for p in periodos)


def _juntar(faixas: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """Ordena e cola faixas que encostam (22:00-24:00 + 00:00-02:00 vira uma so)."""
    saida: list[list[datetime]] = []
    for ini, fim in sorted(faixas):
        if saida and ini <= saida[-1][1]:
            saida[-1][1] = max(saida[-1][1], fim)
        else:
            saida.append([ini, fim])
    return [(a, b) for a, b in saida]


def _faixas_atuais(periodos) -> list[tuple[datetime, datetime]] | None:
    """currentOpeningHours.periods -> faixas absolutas. None se algum ponto vier sem data."""
    faixas = []
    for p in periodos:
        if not isinstance(p, dict):
            continue
        ini, fim = _ponto_com_data(p.get("open")), _ponto_com_data(p.get("close"))
        if ini is None or fim is None:
            return None
        if fim <= ini:
            fim += timedelta(days=1)
        faixas.append((ini, fim))
    return _juntar(faixas)


def _faixas_semana(periodos, quando: datetime) -> list[tuple[datetime, datetime]]:
    """regularOpeningHours.periods (dia 0 = domingo) -> faixas absolutas da semana de `quando`,
    da anterior e da seguinte (pra pegar quem cruza a meia-noite e o 'abre segunda')."""
    domingo = datetime.combine(quando.date() - timedelta(days=(quando.weekday() + 1) % 7), datetime.min.time())
    faixas = []
    for semana in (-1, 0, 1):
        base = domingo + timedelta(weeks=semana)
        for p in periodos:
            if not isinstance(p, dict):
                continue
            ab, fe = p.get("open"), p.get("close")
            if not isinstance(ab, dict) or not isinstance(fe, dict):
                continue
            ini = base + timedelta(days=_int(ab.get("day")), hours=_int(ab.get("hour")), minutes=_int(ab.get("minute")))
            fim = base + timedelta(days=_int(fe.get("day")), hours=_int(fe.get("hour")), minutes=_int(fe.get("minute")))
            if fim <= ini:
                fim += timedelta(weeks=1)  # sabado de noite -> domingo de madrugada
            faixas.append((ini, fim))
    return _juntar(faixas)


def faixas_em(dados: dict, quando: datetime) -> list[tuple[datetime, datetime]] | str | None:
    """Faixas abertas em volta de `quando`; "24h" se nunca fecha; None se nao ha horario.
    Lista vazia = o Google diz que nao abre (nessa janela)."""
    atual, regular = dados.get("atual"), dados.get("regular")
    buscado = dados.get("buscado_em") or datetime.now()
    janela_ini = datetime.combine(buscado.date(), datetime.min.time())
    if isinstance(atual, list) and janela_ini <= quando < janela_ini + timedelta(days=7):
        if atual and _e_24h(atual):
            return "24h"
        faixas = _faixas_atuais(atual)
        if faixas is not None:
            if faixas or not regular:
                return faixas
            # vazio no atual mas a semana tipica tem horario: so confia se o lugar nao esta operando
            if dados.get("status") not in (None, "OPERATIONAL"):
                return faixas
    if isinstance(regular, list):
        if regular and _e_24h(regular):
            return "24h"
        return _faixas_semana(regular, quando)
    return None


# ---------------------------------------------------------------- frases

def hora_curta(m: datetime) -> str:
    """22:00 -> '22h'; 21:30 -> '21h30'; meia-noite -> '0h'."""
    return f"{m.hour}h" if m.minute == 0 else f"{m.hour}h{m.minute:02d}"


def _dia_relativo(alvo: date, base: date) -> str:
    dif = (alvo - base).days
    if dif == 0:
        return ""
    if dif == 1:
        return "amanhã "
    return f"{_DIAS[alvo.weekday()]} "


def situacao(dados: dict | None, quando: datetime) -> dict | None:
    """Aberto/fechado em `quando`. -> {"nome", "estado", "aberto", "frase", "curta",
    + "fecha_as"/"abre_as"/"abre_dia"/"fechou_as" quando fizer sentido}; None = nao sei."""
    if not dados:
        return None
    nome = dados.get("nome") or "o lugar"
    status = dados.get("status")
    if status == "CLOSED_PERMANENTLY":
        return {"nome": nome, "estado": "fechado_de_vez", "aberto": False,
                "frase": "fechou de vez, segundo o Google", "curta": "fechou de vez"}
    if status == "CLOSED_TEMPORARILY":
        return {"nome": nome, "estado": "fechado_temporariamente", "aberto": False,
                "frase": "está fechado temporariamente, segundo o Google", "curta": "fechado temporariamente"}
    faixas = faixas_em(dados, quando)
    if faixas is None:
        return None
    if faixas == "24h":
        return {"nome": nome, "estado": "aberto", "aberto": True, "24h": True,
                "frase": "aberto 24h", "curta": "aberto 24h"}
    for ini, fim in faixas:
        if ini <= quando < fim:
            falta = int((fim - quando).total_seconds() // 60)
            fecha = hora_curta(fim)
            if fim - quando >= timedelta(days=6):
                return {"nome": nome, "estado": "aberto", "aberto": True, "24h": True,
                        "frase": "aberto 24h", "curta": "aberto 24h"}
            base = {"nome": nome, "aberto": True, "fecha_as": fim.strftime("%H:%M")}
            if falta < FECHA_LOGO_MIN:
                return {**base, "estado": "fechando", "fecha_em_min": falta,
                        "frase": f"aberto, mas fecha às {fecha} (só {falta} min depois)",
                        "curta": f"fecha {fecha}, {falta} min depois"}
            dia = _dia_relativo(fim.date(), quando.date()) if fim.date() != quando.date() and fim.hour >= 6 else ""
            return {**base, "estado": "aberto", "frase": f"aberto até {dia}{fecha}".replace("  ", " "),
                    "curta": f"aberto até {fecha}"}
    proxima = next((ini for ini, _fim in faixas if ini > quando), None)
    anterior = max((fim for _ini, fim in faixas if fim <= quando), default=None)
    sit = {"nome": nome, "estado": "fechado", "aberto": False}
    if anterior is not None and anterior.date() == quando.date():
        sit["fechou_as"] = anterior.strftime("%H:%M")
    if proxima is None:
        sit.update(frase="fechado nessa hora", curta="fechado nessa hora")
        return sit
    abre = f"{_dia_relativo(proxima.date(), quando.date())}às {hora_curta(proxima)}"
    sit.update(abre_as=proxima.strftime("%H:%M"), abre_dia=proxima.date().isoformat(),
               frase=f"fechado nessa hora, abre {abre}", curta=f"fechado, abre {abre.replace('às ', '')}")
    return sit


def frase_chegada(sit: dict, chegada: datetime) -> tuple[str, str]:
    """A frase pensada na hora que ele CHEGA (card e aviso). -> (frase, curta)."""
    estado = sit.get("estado")
    tu_chega = hora_curta(chegada)
    if estado == "fechado" and sit.get("fechou_as"):
        fecha = hora_curta(datetime.strptime(sit["fechou_as"], "%H:%M"))
        if sit.get("abre_as") and sit.get("abre_dia") == chegada.date().isoformat():
            reabre = hora_curta(datetime.strptime(sit["abre_as"], "%H:%M"))
            return (f"Fecha das {fecha} às {reabre} e tu chega {tu_chega}.",
                    f"fechado {fecha}-{reabre}, tu chega {tu_chega}")
        return f"Fecha às {fecha} e tu chega {tu_chega}.", f"fecha {fecha}, tu chega {tu_chega}"
    if estado == "fechado":
        if sit.get("abre_as"):
            return (f"Fechado quando tu chega ({tu_chega}); {sit['frase'].split(', ', 1)[-1]}.",
                    sit["curta"])
        return f"Fechado quando tu chega ({tu_chega}).", "fechado na tua hora"
    if estado == "fechando":
        fecha = hora_curta(datetime.strptime(sit["fecha_as"], "%H:%M"))
        n = sit.get("fecha_em_min", 0)
        return (f"Fecha às {fecha}, só {n} min depois de tu chegar.", f"fecha {fecha}, {n} min depois de tu chegar")
    if estado == "fechado_temporariamente":
        return "O Google diz que está fechado temporariamente.", "fechado temporariamente"
    if estado == "fechado_de_vez":
        return "O Google diz que fechou de vez.", "fechou de vez"
    return sit.get("frase", ""), sit.get("curta", "")


def consultar(lugar: str, quando: datetime) -> dict | None:
    """Pergunta ao Google (cota `horario_lugar`, cache curto) e responde a situacao. None = nao sei."""
    import maps_client

    if not lugar or not maps_client.configurado() or maps_client.coordenada(lugar):
        return None
    try:
        dados = maps_client.dados_horario(lugar)
    except Exception:
        return None
    return situacao(dados, quando)


# ---------------------------------------------------------------- automatico (tarefas de hoje)

def _chegada(row, extras: dict, dia: date) -> datetime | None:
    m = _RE_HORA.match((row["hora"] or "").strip())
    if not m:
        return None
    hora = datetime.combine(dia, datetime.min.time()) + timedelta(hours=int(m.group(1)), minutes=int(m.group(2)))
    sai = "sai_na_hora" in row.keys() and bool(row["sai_na_hora"])
    if not sai:
        return hora  # a hora da tarefa e a de estar la
    saida = extras.get("saida") if isinstance(extras.get("saida"), dict) else {}
    mc = _RE_HORA.match(str(saida.get("chegada") or ""))
    if mc:
        return datetime.combine(dia, datetime.min.time()) + timedelta(hours=int(mc.group(1)), minutes=int(mc.group(2)))
    return hora + timedelta(minutes=15)  # sai na hora e o trajeto nao foi calculado: ~15 min em Brusque


def conferir_tarefa(conn, task_id: int, agora: datetime | None = None, chegada_hhmm: str | None = None) -> dict | None:
    """Tarefa de HOJE com lugar e hora: o lugar esta aberto quando ele chega? Consulta o Google uma vez
    por (dia, chegada, lugar) e guarda em extras["horario_lugar"]. `chegada_hhmm` = chegada ja calculada
    (sai_na_hora: hora + trajeto). -> o registro guardado ou None."""
    import db

    agora = agora or datetime.now()
    hoje = agora.date()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
    sel = "id, title, due_date, hora, local, completed_at, extras" + (", sai_na_hora" if "sai_na_hora" in cols else "")
    row = conn.execute(f"SELECT {sel} FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not row or row["completed_at"] or row["due_date"] != hoje.isoformat():
        return None
    lugar = " ".join((row["local"] or "").split())
    if not lugar or lugar.lower() in _SEM_HORARIO:
        return None
    extras = db.extras_tarefa(conn, task_id)
    mc = _RE_HORA.match(str(chegada_hhmm or ""))
    chegada = (datetime.combine(hoje, datetime.min.time()) + timedelta(hours=int(mc.group(1)), minutes=int(mc.group(2)))
               if mc else _chegada(row, extras, hoje))
    if chegada is None or chegada < agora - timedelta(minutes=10):
        return None
    guardado = extras.get("horario_lugar")
    if (isinstance(guardado, dict) and guardado.get("dia") == hoje.isoformat()
            and guardado.get("chegada") == chegada.strftime("%H:%M") and guardado.get("local") == lugar):
        return guardado
    sit = consultar(lugar, chegada)
    if not sit:
        return None
    frase, curta = frase_chegada(sit, chegada)
    registro = {"dia": hoje.isoformat(), "chegada": chegada.strftime("%H:%M"), "local": lugar,
                "nome": sit.get("nome") or lugar, "estado": sit["estado"], "frase": frase, "curta": curta,
                "fecha": sit.get("fecha_as"),
                "abre": sit.get("abre_as") if sit.get("abre_dia") == hoje.isoformat() else None}
    extras = db.extras_tarefa(conn, task_id)  # rele: outro passo pode ter gravado no meio
    extras["horario_lugar"] = registro
    db.salvar_extras_tarefa(conn, task_id, extras)
    return registro


def conferir_tarefas_de_hoje(conn, agora: datetime | None = None, limite: int = 12) -> int:
    """Passa em todas as tarefas de hoje com lugar e hora (scheduler, a cada 5 min - o que ja foi
    conferido pra mesma chegada nao gasta consulta). -> quantas tem registro de hoje."""
    agora = agora or datetime.now()
    ids = [r["id"] for r in conn.execute(
        "SELECT id FROM tasks WHERE due_date = ? AND completed_at IS NULL AND hora IS NOT NULL "
        "AND local IS NOT NULL AND TRIM(local) != '' ORDER BY hora LIMIT ?",
        (agora.date().isoformat(), limite),
    ).fetchall()]
    feitos = 0
    for task_id in ids:
        try:
            if conferir_tarefa(conn, task_id, agora):
                feitos += 1
        except Exception:  # nunca derruba o scheduler
            continue
    return feitos


def alerta_do_card(extras: dict, dia: str | None) -> dict | None:
    """O que o card da tarefa mostra: so fechado/fechando, so pro dia da tarefa."""
    r = extras.get("horario_lugar") if isinstance(extras, dict) else None
    if not isinstance(r, dict) or not dia or r.get("dia") != dia or r.get("estado") not in ESTADOS_ALERTA:
        return None
    return {"estado": r["estado"], "frase": r.get("frase") or "", "curta": r.get("curta") or "",
            "nome": r.get("nome") or ""}


def _nome_curto(nome: str, limite: int = 28) -> str:
    nome = " ".join((nome or "").split())
    if len(nome) <= limite:
        return nome
    corte = nome[:limite].rsplit(" ", 1)[0]
    return (corte or nome[:limite]).rstrip(" ,-") + "…"


def avisos_lugar_fechado(conn, agora: datetime | None = None) -> list[tuple[int, str, str]]:
    """Tarefas de hoje cujo lugar estara fechado/fechando na chegada (e a chegada ainda nao passou).
    -> [(task_id, titulo, corpo)]. O dedup (1x por tarefa por dia) fica com quem manda. Nunca levanta."""
    try:
        return _avisos_lugar_fechado(conn, agora)
    except Exception:
        return []


def _avisos_lugar_fechado(conn, agora: datetime | None = None) -> list[tuple[int, str, str]]:
    import db

    agora = agora or datetime.now()
    hoje = agora.date().isoformat()
    saida = []
    for r in conn.execute(
        "SELECT id FROM tasks WHERE due_date = ? AND completed_at IS NULL AND extras LIKE '%horario_lugar%'",
        (hoje,),
    ).fetchall():
        reg = db.extras_tarefa(conn, r["id"]).get("horario_lugar")
        alerta = alerta_do_card({"horario_lugar": reg}, hoje)
        if not alerta:
            continue
        m = _RE_HORA.match(str(reg.get("chegada") or ""))
        if m and datetime.combine(agora.date(), datetime.min.time()) + timedelta(
                hours=int(m.group(1)), minutes=int(m.group(2))) < agora:
            continue
        nome = _nome_curto(alerta["nome"])
        if alerta["estado"] == "fechando":
            titulo = f"{nome} fecha logo"
        elif alerta["estado"] == "fechado":
            titulo = f"{nome} vai estar fechado"
        else:
            titulo = f"{nome} não está abrindo"
        # texto proprio de proposito (07/11): a frase da chegada ("fecha as 22h e tu chega 22h10") e o nome no
        # titulo dizem mais que as variacoes de avisos_texto.lugar_fechado (que nem sempre trazem o lugar)
        corpo = alerta["frase"] + " Vale ir antes ou trocar o dia."
        saida.append((r["id"], titulo, corpo))
    return saida
