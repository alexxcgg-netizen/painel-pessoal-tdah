"""Diario do dia por lugar (leva 06/11 "painel mais esperto", frente 4 - docs/briefings/2026-11-06-painel-esperto.md).

Das visitas do iPhone (tabela `visitas`, onde_estou.py): por onde ele passou e quanto tempo ficou em cada lugar.
So o LUGAR e o TEMPO - nunca o caminho (nao existe trajeto guardado; as visitas somem em 30 dias e este
diario some junto, porque e calculado na hora, nada e copiado pro `diario_dias`).

  - lugar com apelido (casa, mecanico, academia...) -> o nome; sem apelido -> "Perto do <lugar salvo mais
    perto>" (ate 1 km, so com coordenada que ja esta no banco) ou "Lugar sem nome". Nunca chama API por isso.
  - estadia menor que 5 min some; a mesma estadia partida em duas (cerca + visita) junta.
  - card `diario_lugares` (barra do dia + lista lugar/hora/duracao), no pouso do dia (fechamento_dia) e na
    tool `consultar_diario` (app.exec_consultar_diario).
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime, time, timedelta

import cards

MIN_ESTADIA = 5
JUNTA_MIN = 15
PERTO_M = 1000
CORES = ("#8fd0ff", "#f0a58f", "#c4a1ff", "#7fd9d0", "#ffd36e", "#f5a3b8", "#b5e48c")
COR_CASA = "#8a8a94"
NOTA = "Só o lugar e o tempo que ficou, nunca o caminho. Some depois de 30 dias."


def _dt(txt) -> datetime | None:
    try:
        return datetime.fromisoformat(txt) if txt else None
    except (TypeError, ValueError):
        return None


def duracao(minutos: int) -> str:
    """'20 min' / '1 h' / '3 h 38'."""
    m = max(0, int(minutos))
    if m < 60:
        return f"{m} min"
    h, r = divmod(m, 60)
    return f"{h} h" if not r else f"{h} h {r:02d}"


def _pontos_salvos(conn) -> list[tuple[str, tuple[float, float]]]:
    """(nome, coordenada) de tudo que ja tem coordenada no banco: apelidos/casa geocodificados uma vez
    (onde_estou) e a tabela `lugares`. Zero rede."""
    import maps_client
    import onde_estou

    pontos = []
    for apelido, item in onde_estou._carregar_coords(conn).items():
        if isinstance(item, dict) and isinstance(item.get("lat"), (int, float)) and isinstance(item.get("lon"), (int, float)):
            pontos.append((apelido, (item["lat"], item["lon"])))
    casa = maps_client.coordenada(os.environ.get("ENDERECO_CASA", "").strip())
    if casa:
        pontos.append(("casa", casa))
    try:
        for r in conn.execute("SELECT nome, lat, lng FROM lugares WHERE lat IS NOT NULL AND lng IS NOT NULL"):
            pontos.append((r["nome"], (r["lat"], r["lng"])))
    except sqlite3.Error:
        pass
    return pontos


def _nome(conn, apelido: str | None, ponto: tuple[float, float], salvos: list, titulos: list[str]) -> tuple[str, bool]:
    """(nome pra mostrar, e_casa)."""
    import onde_estou

    if apelido == "casa":
        return "Casa", True
    if apelido:
        nome, _ = onde_estou.nome_e_genero(apelido, titulos)
        return nome[:1].upper() + nome[1:], False
    perto = sorted(((onde_estou._metros(ponto, c), n) for n, c in salvos), key=lambda x: x[0])
    if perto and perto[0][0] <= PERTO_M:
        n = perto[0][1]
        if n == "casa":
            return "Perto de casa", False
        nome, genero = onde_estou.nome_e_genero(n, titulos)
        return "Perto " + onde_estou._de(nome, genero), False
    return "Lugar sem nome", False


def _feitas(conn, ini: datetime, fim: datetime) -> list[tuple[datetime, str]]:
    """Tarefas concluidas entre ini e fim (hora local). completed_at e UTC."""
    import diario

    try:
        rows = conn.execute(
            "SELECT title, completed_at FROM tasks WHERE completed_at IS NOT NULL AND completed_at >= ? "
            "AND completed_at < ?",
            ((ini - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"), (fim + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")),
        ).fetchall()
    except sqlite3.Error:
        return []
    saida = []
    for r in rows:
        quando = diario.utc_para_local(r["completed_at"])
        if quando and ini <= quando < fim:
            saida.append((quando, r["title"]))
    return sorted(saida)


def estadias(conn, dia: date, agora: datetime | None = None) -> list[dict]:
    """[{lugar, hora, ate, min, casa, sub, ini, fim, apelido}] do dia, em ordem."""
    import onde_estou

    agora = agora or datetime.now()
    ini_dia = datetime.combine(dia, time(0, 0))
    fim_dia = ini_dia + timedelta(days=1)
    corte = min(fim_dia, agora) if dia == agora.date() else fim_dia
    if corte <= ini_dia:
        return []
    try:
        rows = conn.execute(
            "SELECT * FROM visitas WHERE COALESCE(chegada, saida) < ? AND COALESCE(saida, ?) >= ? "
            "AND COALESCE(chegada, saida) >= ? ORDER BY COALESCE(chegada, saida), id",
            (corte.isoformat(timespec="seconds"), "9999", ini_dia.isoformat(timespec="seconds"),
             (ini_dia - timedelta(days=2)).isoformat(timespec="seconds")),
        ).fetchall()
    except sqlite3.Error:
        return []
    brutas = []
    for i, r in enumerate(rows):
        chegada, saida = _dt(r["chegada"]), _dt(r["saida"])
        proxima = next((_dt(x["chegada"]) or _dt(x["saida"]) for x in rows[i + 1:]), None)
        inicio = chegada or (brutas[-1]["fim"] if brutas else ini_dia)
        if saida:
            fim = saida
        elif i == len(rows) - 1 and chegada and agora - chegada <= timedelta(hours=onde_estou.VISITA_ABERTA_MAX_H):
            fim = corte  # ainda esta la
        elif proxima:
            fim = proxima
        else:
            continue
        inicio_c, fim_c = max(inicio, ini_dia), min(fim, corte)
        if fim_c <= inicio_c:
            continue
        brutas.append({"apelido": r["lugar"], "ponto": (r["lat"], r["lon"]), "ini": inicio_c, "fim": fim_c,
                       "de_ontem": inicio < ini_dia, "aberta": not saida and fim_c == corte and dia == agora.date()})
    juntas: list[dict] = []
    for b in brutas:
        ant = juntas[-1] if juntas else None
        mesmo = ant and (b["apelido"] == ant["apelido"] if (b["apelido"] or ant["apelido"])
                         else onde_estou._metros(b["ponto"], ant["ponto"]) <= onde_estou.RAIO_M)
        if ant and mesmo and (b["ini"] - ant["fim"]) <= timedelta(minutes=JUNTA_MIN):
            ant["fim"] = max(ant["fim"], b["fim"])
            ant["aberta"] = b["aberta"]
            continue
        juntas.append(dict(b))
    juntas = [j for j in juntas if (j["fim"] - j["ini"]) >= timedelta(minutes=MIN_ESTADIA)]
    if not juntas:
        return []
    salvos = _pontos_salvos(conn)
    feitas = _feitas(conn, ini_dia, corte)
    titulos = [t for _, t in feitas]
    try:
        titulos += [r["title"] for r in conn.execute("SELECT title FROM tasks WHERE due_date = ?", (dia.isoformat(),))]
    except sqlite3.Error:
        pass
    saida = []
    for j in juntas:
        nome, e_casa = _nome(conn, j["apelido"], j["ponto"], salvos, titulos)
        ali = [onde_estou._titulo_frase(t) for q, t in feitas if j["ini"] <= q < j["fim"]]
        if ali:
            sub = f"feito: {ali[0][:40]}" + (f" e mais {len(ali) - 1}" if len(ali) > 1 else "")
        elif j["aberta"]:
            sub = "até agora"
        elif j["de_ontem"]:
            sub = f"desde ontem, saiu {j['fim']:%H:%M}"
        else:
            sub = f"saiu {j['fim']:%H:%M}"
        saida.append({
            "lugar": nome, "apelido": j["apelido"], "casa": e_casa, "hora": f"{j['ini']:%H:%M}",
            "ate": f"{j['fim']:%H:%M}", "min": round((j["fim"] - j["ini"]).total_seconds() / 60), "sub": sub,
            "ini": j["ini"], "fim": j["fim"],
        })
    return saida


def _cores(lista: list[dict]) -> None:
    mapa: dict[str, str] = {}
    for e in lista:
        if e["casa"]:
            e["cor"] = COR_CASA
            continue
        chave = e["lugar"]
        if chave not in mapa:
            mapa[chave] = CORES[len(mapa) % len(CORES)]
        e["cor"] = mapa[chave]


def dados(conn, dia: date, agora: datetime | None = None) -> dict | None:
    """data do card `diario_lugares`; None sem nenhuma estadia no dia."""
    import diario

    agora = agora or datetime.now()
    lista = estadias(conn, dia, agora)
    if not lista:
        return None
    _cores(lista)
    barra = []
    for i, e in enumerate(lista):
        if i and e["ini"] > lista[i - 1]["fim"]:
            barra.append({"min": round((e["ini"] - lista[i - 1]["fim"]).total_seconds() / 60), "vazio": True})
        barra.append({"min": e["min"], "cor": e["cor"], "casa": e["casa"]})
    janela = round((lista[-1]["fim"] - lista[0]["ini"]).total_seconds() / 60)
    fora = janela - sum(e["min"] for e in lista if e["casa"]) if any(e["casa"] for e in lista) else None
    rotulo = diario.rotulo_dia(dia, agora.date())
    rotulo = rotulo.split(" (")[0]
    titulo = "Teu dia, por onde passou" if dia == agora.date() else f"{rotulo[:1].upper()}{rotulo[1:]}, por onde passou"
    lugares_distintos = len({e["lugar"] for e in lista})
    return {
        "dia": dia.isoformat(), "titulo": titulo,
        "n_lugares": lugares_distintos, "fora_min": fora if fora and fora > 0 else None,
        "lugares": [{k: e[k] for k in ("lugar", "hora", "ate", "min", "casa", "sub", "cor")} for e in lista],
        "barra": barra, "nota": NOTA,
    }


def card(conn, dia: date, agora: datetime | None = None) -> dict | None:
    d = dados(conn, dia, agora)
    return cards.novo_card("diario_lugares", d) if d else None


def resumo(conn, dia: date, agora: datetime | None = None) -> list[str]:
    """Pra IA (consultar_diario): 'Casa 07:00-08:10 (1 h 10)'."""
    return [f"{e['lugar']} {e['hora']}-{e['ate']} ({duracao(e['min'])})" for e in estadias(conn, dia, agora)]


def no_consultar(conn, dia: date, resultado: dict, agora: datetime | None = None) -> dict:
    """Junta os lugares do dia no que a tool consultar_diario devolve, com o card. Sem visitas: igual."""
    if not isinstance(resultado, dict) or resultado.get("erro"):
        return resultado
    linhas = resumo(conn, dia, agora)
    if not linhas:
        return resultado
    return {**resultado, "lugares_do_dia": linhas,
            "_efeito": {"entidade": "diario_lugares", "dia": dia.isoformat(), "consulta": True}}
