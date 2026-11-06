"""Carro e combustivel (leva "painel mais esperto", 2026-11-06, docs/briefings/2026-11-06-painel-esperto.md,
frente 1).

O Alex fala "enchi o tanque", "abasteci 30 L por 180" ou manda a foto da nota do posto -> a ferramenta
`registrar_abastecimento` grava em `abastecimentos`. Daqui sai:

  - consumo REAL (`consumo_real`): de tanque cheio a tanque cheio, km pelo hodometro dos dois / litros
    colocados no caminho (o do cheio de chegada incluso). Precisa dos dois hodometros e de todos os litros -
    sem isso nao inventa: fica o consumo de partida da tabela `veiculo` (13 km/l estrada, 10 cidade, XC40);
  - quanto sobra no tanque (`estimativa_tanque`): ultimo tanque cheio - km rodados desde entao (hodometro
    quando ele falar; senao as viagens planejadas pelo painel + a media de km por dia que o hodometro ja
    ensinou) + litros dos abastecimentos parciais. SEMPRE estimativa, com a margem escrita junto.

Nada de rede aqui. Dinheiro (valor, preco do litro) e pessoal: entra em cards.CAMPOS_SENSIVEIS.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta

# padrao se a tabela ainda nao existir (banco sem a migracao) - mesmo valor da migracao
PADRAO = {"nome": "Volvo XC40 T5 Twin Engine 2020", "tanque_l": 49.0, "tanque_conferido": 0,
          "consumo_estrada": 13.0, "consumo_cidade": 10.0, "reserva_km": 60.0}
CONSUMO_MIN, CONSUMO_MAX = 4.0, 30.0  # km/l fora disso = conta errada (hodometro digitado errado)
MARGEM_FRACAO = 0.10  # margem da estimativa do tanque: 10% do tanque
MAX_TANQUES_MEDIA = 3
DIAS_MIN_MEDIA_DIA = 7  # media de km por dia so com hodometros com 7+ dias de distancia

TANQUE_TEXTO = {"cheio": 1.0, "3/4": 0.75, "meio": 0.5, "metade": 0.5, "1/2": 0.5, "1/4": 0.25}


def _num(v) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    try:
        n = float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return n if n == n and n not in (float("inf"), float("-inf")) else None


def veiculo(conn) -> dict:
    try:
        row = conn.execute("SELECT * FROM veiculo WHERE id = 1").fetchone()
    except sqlite3.Error:
        row = None
    v = dict(PADRAO)
    if row:
        v.update({k: row[k] for k in row.keys() if k in PADRAO and row[k] is not None})
    v["tanque_l"] = float(v["tanque_l"])
    return v


def _linhas(conn) -> list[dict]:
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM abastecimentos ORDER BY data, id").fetchall()]
    except sqlite3.Error:
        return []


def validar(litros=None, valor=None, hodometro_km=None, tanque_l: float = 49.0) -> tuple[dict, str | None]:
    """Entrada da ferramenta -> (valores limpos, erro). Litros ate 1,5x o tanque (bomba que passa um
    pouco do nominal), valor ate R$ 3.000, hodometro ate 2 milhoes de km."""
    limpo = {}
    l = _num(litros)
    if litros not in (None, "") and (l is None or not 0 < l <= tanque_l * 1.5):
        return {}, f"litros fora do normal ({litros}) - o tanque e de uns {tanque_l:g} L"
    v = _num(valor)
    if valor not in (None, "") and (v is None or not 0 < v <= 3000):
        return {}, f"valor fora do normal ({valor})"
    h = _num(hodometro_km)
    if hodometro_km not in (None, "") and (h is None or not 0 < h < 2_000_000):
        return {}, f"hodometro fora do normal ({hodometro_km})"
    limpo["litros"] = round(l, 2) if l else None
    limpo["valor"] = round(v, 2) if v else None
    limpo["hodometro_km"] = round(h, 1) if h else None
    return limpo, None


def registrar(conn, quando: datetime, *, litros=None, valor=None, cheio: bool = False, hodometro_km=None,
              lugar: str | None = None) -> dict:
    """Grava um abastecimento (sem commit de fora: faz o proprio). -> {"id"} ou {"erro"}."""
    v = veiculo(conn)
    limpo, erro = validar(litros, valor, hodometro_km, v["tanque_l"])
    if erro:
        return {"erro": erro}
    if not cheio and not limpo["litros"] and not limpo["valor"]:
        return {"erro": "preciso dos litros, do valor ou saber se encheu o tanque"}
    lugar = (lugar or "").strip()[:120] or None
    cur = conn.execute(
        "INSERT INTO abastecimentos (data, hodometro_km, litros, valor, cheio, lugar) VALUES (?, ?, ?, ?, ?, ?)",
        (quando.strftime("%Y-%m-%dT%H:%M"), limpo["hodometro_km"], limpo["litros"], limpo["valor"],
         1 if cheio else 0, lugar),
    )
    conn.commit()
    return {"id": cur.lastrowid}


def consumo_real(conn) -> dict | None:
    """Media (ponderada pelos km) dos ultimos ate 3 trechos de tanque cheio a tanque cheio que tem os
    DOIS hodometros e todos os litros. None ate ter um trecho assim (2 tanques cheios registrados)."""
    linhas = _linhas(conn)
    cheios = [i for i, r in enumerate(linhas) if r["cheio"]]
    trechos = []
    for a, b in zip(cheios, cheios[1:]):
        ra, rb = linhas[a], linhas[b]
        if not (ra["hodometro_km"] and rb["hodometro_km"]):
            continue
        km = rb["hodometro_km"] - ra["hodometro_km"]
        litros = [linhas[i]["litros"] for i in range(a + 1, b + 1)]
        if km <= 0 or any(not x for x in litros):
            continue
        kml = km / sum(litros)
        if CONSUMO_MIN <= kml <= CONSUMO_MAX:
            trechos.append((km, sum(litros)))
    if not trechos:
        return None
    usados = trechos[-MAX_TANQUES_MEDIA:]
    km = sum(t[0] for t in usados)
    return {"km_l": round(km / sum(t[1] for t in usados), 1), "tanques": len(usados), "km": round(km)}


def consumo(conn, tipo: str = "estrada") -> dict:
    """km/l pra conta: o real (misto - na estrada da folga, nunca falta) ou o de partida do carro."""
    real = consumo_real(conn)
    if real:
        return {"km_l": real["km_l"], "fonte": "real", "tanques": real["tanques"]}
    v = veiculo(conn)
    return {"km_l": float(v["consumo_cidade" if tipo == "cidade" else "consumo_estrada"]), "fonte": "padrao"}


def media_km_dia(conn) -> float | None:
    """Quanto ele roda por dia, pelo hodometro (primeira e ultima leitura com 7+ dias entre elas)."""
    com_hod = [r for r in _linhas(conn) if r["hodometro_km"]]
    if len(com_hod) < 2:
        return None
    a, b = com_hod[0], com_hod[-1]
    try:
        dias = (datetime.fromisoformat(b["data"]) - datetime.fromisoformat(a["data"])).total_seconds() / 86400
    except ValueError:
        return None
    km = b["hodometro_km"] - a["hodometro_km"]
    if dias < DIAS_MIN_MEDIA_DIA or km <= 0:
        return None
    return round(km / dias, 1)


def km_viagens_desde(conn, desde: datetime, agora: datetime) -> float:
    """km das viagens planejadas pelo painel entre `desde` e `agora` (a que esta em andamento conta
    pela fracao do tempo que ja passou). Viagem cancelada antes de sair nao conta."""
    try:
        rows = conn.execute(
            "SELECT saida_em, chegada_em, plano_json, encerrada_em FROM viagens_planejadas WHERE saida_em >= ? AND saida_em <= ?",
            (desde.strftime("%Y-%m-%dT%H:%M"), agora.isoformat()),
        ).fetchall()
    except sqlite3.Error:
        return 0.0
    total = 0.0
    for r in rows:
        try:
            saida, chegada = datetime.fromisoformat(r["saida_em"]), datetime.fromisoformat(r["chegada_em"])
            km = float(json.loads(r["plano_json"]).get("total_km") or 0)
        except (ValueError, TypeError, AttributeError):
            continue
        fim = agora
        if r["encerrada_em"]:
            try:
                fim = min(agora, datetime.fromisoformat(r["encerrada_em"]))
            except ValueError:
                pass
        if fim <= saida:
            continue
        dur = max(1.0, (chegada - saida).total_seconds())
        total += km * min(1.0, (fim - saida).total_seconds() / dur)
    return round(total, 1)


def estimativa_tanque(conn, agora: datetime) -> dict | None:
    """Quanto sobra no tanque, estimado. None = nenhum tanque cheio registrado ainda."""
    linhas = _linhas(conn)
    idx = max((i for i, r in enumerate(linhas) if r["cheio"]), default=None)
    if idx is None:
        return None
    v = veiculo(conn)
    cheio = linhas[idx]
    depois = linhas[idx + 1:]
    try:
        desde = datetime.fromisoformat(cheio["data"])
    except ValueError:
        return None
    parciais = sum(r["litros"] or 0 for r in depois)
    sem_litros = sum(1 for r in depois if not r["litros"])
    estrada, cidade = consumo(conn, "estrada"), consumo(conn, "cidade")
    hod = [r for r in depois if r["hodometro_km"]]
    obs = []
    if cheio["hodometro_km"] and hod:
        km = hod[-1]["hodometro_km"] - cheio["hodometro_km"]
        gastos = max(0.0, km) / cidade["km_l"]
        base = "hodometro"
        ultimo = datetime.fromisoformat(hod[-1]["data"])
        km_viagem = km_viagens_desde(conn, ultimo, agora)
        gastos += km_viagem / estrada["km_l"]
        km += km_viagem
    else:
        km_viagem = km_viagens_desde(conn, desde, agora)
        dias = max(0.0, (agora - desde).total_seconds() / 86400)
        por_dia = media_km_dia(conn)
        km_dia = (por_dia or 0) * dias
        km = km_viagem + km_dia
        gastos = km_viagem / estrada["km_l"] + km_dia / cidade["km_l"]
        base = "viagens"
        if por_dia is None and dias >= 1:
            obs.append("não sei quanto tu rodou na cidade desde que encheu - diz o hodômetro quando abastecer")
    litros = max(0.0, min(v["tanque_l"], v["tanque_l"] - gastos + parciais))
    if sem_litros:
        obs.append("teve abastecimento sem os litros")
    margem = round(v["tanque_l"] * MARGEM_FRACAO, 1)
    return {
        "estimativa": True,
        "litros": round(litros, 1),
        "fracao": round(litros / v["tanque_l"], 2),
        "tanque_l": v["tanque_l"],
        "tanque_conferido": bool(v["tanque_conferido"]),
        "autonomia_km": round(litros * estrada["km_l"]),
        "margem_l": margem,
        "km_desde": round(km),
        "desde": cheio["data"],
        "base": base,
        "obs": obs,
    }


def litros_do_texto(texto, conn) -> float | None:
    """'cheio' / '3/4' / 'meio' / '1/4' / 'reserva' / fracao 0-1 -> litros no tanque. None = nao entendi."""
    v = veiculo(conn)
    if isinstance(texto, (int, float)) and not isinstance(texto, bool):
        return round(v["tanque_l"] * texto, 1) if 0 <= texto <= 1 else None
    t = str(texto or "").strip().lower()
    if t in TANQUE_TEXTO:
        return round(v["tanque_l"] * TANQUE_TEXTO[t], 1)
    if t in ("reserva", "na reserva", "luz acesa"):
        return round(v["reserva_km"] / consumo(conn, "cidade")["km_l"], 1)
    n = _num(t)
    if n is not None and 0 <= n <= 1:
        return round(v["tanque_l"] * n, 1)
    return None


def preco_litro_recente(conn, agora: datetime, dias: int = 60) -> float | None:
    """Preco do litro do ultimo abastecimento com litros e valor nos ultimos `dias` dias."""
    limite = (agora - timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M")
    for r in reversed(_linhas(conn)):
        if r["data"] >= limite and r["litros"] and r["valor"]:
            return round(r["valor"] / r["litros"], 2)
    return None


def texto_tanque(est: dict | None, consumo_info: dict, v: dict) -> str:
    """Frase curta e honesta do tanque pro card/IA."""
    tanque = f"{v['tanque_l']:g} L" + ("" if v.get("tanque_conferido") else " (a confirmar)")
    fonte = (f"teu consumo real, média de {consumo_info.get('tanques')} tanque(s)" if consumo_info.get("fonte") == "real"
             else "consumo de partida do carro, até ter 2 tanques cheios com hodômetro")
    if not est:
        return f"Estimativa: tanque de {tanque} a ~{consumo_info['km_l']:g} km/l ({fonte})."
    return (f"Estimativa: ~{est['litros']:g} L de {tanque}, uns {est['autonomia_km']} km a "
            f"~{consumo_info['km_l']:g} km/l ({fonte}). Margem de ±{est['margem_l']:g} L.")


def card(conn, id_: int, actions_extra=None, agora: datetime | None = None) -> dict | None:
    """Card `abastecimento`: o que entrou + consumo + o tanque estimado depois."""
    import cards

    try:
        row = conn.execute("SELECT * FROM abastecimentos WHERE id = ?", (id_,)).fetchone()
    except sqlite3.Error:
        row = None
    if not row:
        return None
    r = dict(row)
    agora = agora or datetime.now()
    v = veiculo(conn)
    est = estimativa_tanque(conn, agora)
    real = consumo_real(conn)
    data = {
        "data": r["data"],
        "litros": r["litros"],
        "valor": r["valor"],
        "preco_litro": round(r["valor"] / r["litros"], 2) if r["litros"] and r["valor"] else None,
        "cheio": bool(r["cheio"]),
        "lugar": r["lugar"],
        "hodometro_km": r["hodometro_km"],
        "carro": v["nome"],
        "consumo": {"km_l": real["km_l"], "tanques": real["tanques"]} if real else None,
        "consumo_padrao": {"estrada": v["consumo_estrada"], "cidade": v["consumo_cidade"]},
        "tanque": {k: est[k] for k in ("litros", "fracao", "tanque_l", "tanque_conferido", "autonomia_km", "margem_l")}
        if est else None,
        "reserva_fracao": round(min(1.0, v["reserva_km"] / v["consumo_cidade"] / v["tanque_l"]), 2),
        "dica": None if real else ("Diz o hodômetro quando encher o tanque: com 2 tanques cheios eu aprendo "
                                   "o teu consumo de verdade."),
    }
    return cards.novo_card("abastecimento", data, list(actions_extra or []))


def executar(conn, entrada: dict, agora: datetime | None = None) -> dict:
    """registrar_abastecimento: grava e devolve pra IA o que entrou + o tanque estimado depois."""
    agora = agora or datetime.now()
    quando = agora
    data_txt = str(entrada.get("data") or "").strip()
    if data_txt:
        try:
            quando = datetime.fromisoformat(data_txt.replace(" ", "T")[:16]) if len(data_txt) > 10 \
                else datetime.fromisoformat(data_txt[:10]).replace(hour=agora.hour, minute=agora.minute)
        except ValueError:
            return {"erro": "nao entendi a data - use 'AAAA-MM-DD' ou 'AAAA-MM-DD HH:MM'"}
        if quando > agora + timedelta(minutes=5) or quando < agora - timedelta(days=60):
            return {"erro": "data fora do normal pra um abastecimento"}
    r = registrar(conn, quando, litros=entrada.get("litros"), valor=entrada.get("valor"),
                  cheio=bool(entrada.get("cheio")), hodometro_km=entrada.get("hodometro_km"), lugar=entrada.get("lugar"))
    if r.get("erro"):
        return r
    v = veiculo(conn)
    est = estimativa_tanque(conn, agora)
    real = consumo_real(conn)
    resposta = {
        "ok": True,
        "tanque": texto_tanque(est, consumo(conn, "estrada"), v),
        "consumo_real_km_l": real["km_l"] if real else None,
        "obs": None if real else "consumo real so depois de 2 tanques cheios com hodometro - se ele nao disse o "
                                 "hodometro, pode lembrar (sem insistir)",
        "_efeito": {"entidade": "abastecimento", "id": r["id"]},
    }
    return resposta
