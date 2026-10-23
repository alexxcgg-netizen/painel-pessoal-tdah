"""A IA propoe o horario (leva 22/10, item 9): em vez de so devolver o maior buraco do dia, escolhe UM horario
olhando a agenda, a rotina e o sono - o Alex quer que a IA escolha e ele ajusta (memoria chat-app-como-alex-usa).

Regras (todas conta pura, nunca pela IA):
- agenda: evento do iCloud, tarefa com hora (ocupa TAREFA_MIN) e voo (do briefing ao debriefing) ocupam o dia;
- folga: comeca FOLGA_MIN depois do compromisso anterior (ele pediu "deixa mais tempo entre as tarefas");
- costume: se ele ja fez coisa parecida com hora marcada (>= 2 vezes nos ultimos 90 dias), fica perto da hora
  de costume; senao o maior espaco livre;
- sono: dormiu pouco (saude < SONO_CURTO_H ou check-in de sono 1) -> nada depois de FIM_SONO_CURTO, pra ele dormir
  mais cedo."""
from datetime import date, timedelta
from statistics import median

FOLGA_MIN = 15
TAREFA_MIN = 30
SONO_CURTO_H = 6.0
FIM_DIA = "22:00"  # hora que ele escolheu pra desacelerar (notificacoes.hora_de_dormir_devida)
FIM_SONO_CURTO = "21:00"
INICIO_DIA = "06:00"
COSTUME_DIAS = 90


def _m(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _hhmm(minutos: int) -> str:
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def escolher(ocupados: list[tuple[str, str, str]], inicio_dia: str, fim_dia: str, duracao: int,
             costume: str | None = None, folga: int = FOLGA_MIN) -> dict | None:
    """ocupados = [(inicio, fim, titulo)] em HH:MM. Devolve {inicio, fim, janela, depois_de, no_costume} ou None.
    A janela livre comeca `folga` min depois do fim de um compromisso (nao no comeco do dia/agora)."""
    ini_d, fim_d = _m(inicio_dia), _m(fim_dia)
    blocos = sorted((max(_m(i), ini_d), min(_m(f), fim_d), t) for i, f, t in ocupados if _m(f) > ini_d and _m(i) < fim_d)
    livres, cursor, anterior = [], ini_d, None
    for ini, fim, titulo in blocos:
        comeco = cursor + (folga if anterior else 0)
        if ini - comeco >= duracao:
            livres.append((comeco, ini, anterior))
        if fim >= cursor:  # o que termina por ultimo e de quem vem a folga
            cursor, anterior = fim, titulo
    comeco = cursor + (folga if anterior else 0)
    if fim_d - comeco >= duracao:
        livres.append((comeco, fim_d, anterior))
    if not livres:
        return None
    no_costume = False
    if costume:
        alvo = _m(costume)

        def distancia(j):
            inicio = min(max(alvo, j[0]), j[1] - duracao)
            return abs(inicio - alvo), j[0]

        janela = min(livres, key=distancia)
        inicio = min(max(alvo, janela[0]), janela[1] - duracao)
        no_costume = abs(inicio - alvo) <= 60
    else:
        janela = max(livres, key=lambda j: j[1] - j[0])
        inicio = janela[0]
    inicio = -(-inicio // 5) * 5  # minuto redondo de gente
    if inicio + duracao > janela[1]:
        inicio = janela[1] - duracao
    return {
        "inicio": _hhmm(inicio),
        "fim": _hhmm(inicio + duracao),
        "janela": {"inicio": _hhmm(janela[0]), "fim": _hhmm(janela[1])},
        "depois_de": janela[2] if janela[2] and inicio == janela[0] else None,
        "no_costume": no_costume,
    }


def hora_de_costume(conn, titulo: str | None, hoje: date) -> str | None:
    """Mediana da hora das tarefas parecidas que ele fez com hora marcada (>= 2 nos ultimos 90 dias)."""
    import aprendizado

    palavras = [p for p in aprendizado.normalizar_consulta(titulo or "").split() if len(p) >= 4]
    if not palavras:
        return None
    rows = conn.execute(
        "SELECT title, hora FROM tasks WHERE hora IS NOT NULL AND completed_at IS NOT NULL AND due_date >= ?",
        ((hoje - timedelta(days=COSTUME_DIAS)).isoformat(),),
    ).fetchall()
    horas = [_m(r["hora"]) for r in rows
             if any(p[:5] in aprendizado.normalizar_consulta(r["title"]) for p in palavras) and ":" in (r["hora"] or "")]
    if len(horas) < 2:
        return None
    return _hhmm(int(round(median(horas) / 15) * 15))


def sono_curto(conn, dia: date) -> float | None:
    """Horas de sono da noite (saude do iPhone) quando foi curta; check-in de sono 1 sem dado do relogio = 0."""
    import db

    r = conn.execute("SELECT sono_horas FROM saude_dados WHERE data = ?", (dia.isoformat(),)).fetchone()
    try:
        h = float(db._dnum(r["sono_horas"], float)) if r and r["sono_horas"] is not None else None
    except (TypeError, ValueError, AttributeError):
        h = None
    if h is not None:
        return h if 0 < h < SONO_CURTO_H else None
    ck = db.get_checkin(conn, dia.isoformat()) or {}
    return 0.0 if ck.get("sono") == 1 else None


def ocupados_do_dia(conn, dia: date, eventos: list[dict]) -> list[tuple[str, str, str]]:
    """Eventos (formato do caldav_client) + tarefas com hora + voos do dia, em (inicio, fim, titulo)."""
    import vida_assistente

    out = []
    for e in eventos:
        if e.get("dia_inteiro") or e.get("origem") == "tarefa":
            continue
        out.append((e["inicio"][11:16], e["fim"][11:16], e.get("titulo") or "compromisso"))
    for r in conn.execute(
        "SELECT title, hora FROM tasks WHERE completed_at IS NULL AND due_date = ? AND hora IS NOT NULL", (dia.isoformat(),)
    ).fetchall():
        if ":" in (r["hora"] or ""):
            out.append((r["hora"], _hhmm(min(_m(r["hora"]) + TAREFA_MIN, 24 * 60 - 1)), r["title"]))
    antes, depois = vida_assistente.voo_briefing_min(conn), vida_assistente.voo_debriefing_min(conn)
    for r in conn.execute(
        "SELECT hora FROM voos WHERE data = ? AND hora IS NOT NULL AND horas IS NULL", (dia.isoformat(),)
    ).fetchall():
        h = _m(r["hora"])
        out.append((_hhmm(max(0, h - antes)), _hhmm(min(h + 120 + depois, 24 * 60 - 1)), "voo"))
    return out
