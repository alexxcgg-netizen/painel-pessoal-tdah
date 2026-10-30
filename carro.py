"""Partida no carro (leva Lab v4, ideia "carro", 30/10/2026).

Tu entra no carro e nao lembra o que era pra resolver no caminho. Quando o iPhone conecta no Bluetooth do carro (ou
CarPlay), uma automacao do Atalhos ("Bluetooth" ou "CarPlay" -> "Conecta", Executar Imediatamente) chama
`GET|POST /api/atalho/carro` (token dos Atalhos). O painel responde EM VOZ ALTA (campo `fala`, o Atalho usa "Falar
texto"): o proximo compromisso COM LUGAR, quando tu chega, o recado que cai no caminho e o link do Waze ja pronto.

    "Academia as 18h30, tu chega 18h12. No caminho: posto Shell da avenida, pra calibrar o pneu."

De onde vem cada coisa (nada inventado):
  - compromisso com lugar = tarefa de hoje com hora E `local` preenchido, ou voo de hoje (aerodromo de origem);
  - "chega" = Google Maps com transito (origem = `lat`/`lon` que o Atalho manda, senao ENDERECO_CASA);
  - "no caminho" = recado de hoje com lugar (ou "posto/abastecer/calibrar" sem lugar -> posto no meio do caminho,
    `maps_client.posto_no_meio_do_caminho`) que custa NO MAXIMO 10 min a mais no trajeto (Maps, ida passando pela
    parada menos ida direta). Sem Maps configurado nao existe "no caminho": a fala so diz o compromisso e a hora;
  - o link do Waze vai pra parada (o Waze nao aceita varias paradas); sem parada, pro compromisso.
O mesmo texto vira o card `carro` no chat (nao repete a mesma fala em 3 h).
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta

EXTRA_MAX_MIN = 10  # parada so conta como "no caminho" se atrasar ate isso
MAX_PARADAS_TESTADAS = 2
_RE_POSTO = re.compile(r"\b(posto|abastec\w*|gasolina|calibrar|calibra[gç]\w*)\b", re.IGNORECASE)


def _hora_falada(hhmm: str) -> str:
    h, _, m = (hhmm or "").partition(":")
    return f"{int(h)}h" if m in ("", "00") else f"{int(h)}h{m}"


def _min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _hhmm(minutos: int) -> str:
    minutos %= 1440
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def parse_origem(corpo: dict, args=None) -> str | None:
    """'lat,lon' do Atalho (campos lat/lon ou localizacao) ou ENDERECO_CASA."""
    args = args or {}
    lat = corpo.get("lat", args.get("lat"))
    lon = corpo.get("lon", args.get("lon"))
    loc = corpo.get("localizacao") or args.get("localizacao")
    try:
        if lat not in (None, "") and lon not in (None, ""):
            la, lo = float(str(lat).replace(",", ".")), float(str(lon).replace(",", "."))
        elif isinstance(loc, str) and "," in loc:
            la, lo = (float(x.strip()) for x in loc.split(",")[:2])
        else:
            la = lo = None
    except ValueError:
        la = lo = None
    if la is not None and -90 <= la <= 90 and -180 <= lo <= 180:
        return f"{la:.5f},{lo:.5f}"
    return os.environ.get("ENDERECO_CASA", "").strip() or None


def compromissos_com_lugar(conn, hoje: date, agora: datetime, voo_antes_min: int = 45, resolver_lugar=None) -> list[dict]:
    """Os de hoje que ainda nao passaram (15 min de tolerancia), do mais cedo pro mais tarde pelo horario de CHEGAR."""
    saida = []
    for t in conn.execute(
        "SELECT id, title, hora, local FROM tasks WHERE completed_at IS NULL AND due_date = ? AND hora IS NOT NULL "
        "AND local IS NOT NULL AND TRIM(local) != '' ORDER BY hora", (hoje.isoformat(),)
    ).fetchall():
        saida.append({"titulo": t["title"], "hora": t["hora"], "lugar": t["local"].strip(), "chegar_ate": t["hora"], "origem": "tarefa", "id": t["id"]})
    for v in conn.execute(
        "SELECT id, origem, hora FROM voos WHERE data = ? AND hora IS NOT NULL AND horas IS NULL "
        "AND COALESCE(tipo, '') != 'simulador' ORDER BY hora", (hoje.isoformat(),)
    ).fetchall():
        import rota_voo

        icao = v["origem"] or rota_voo.ORIGEM_PADRAO
        lugar = (resolver_lugar(icao) if resolver_lugar else icao) or icao
        saida.append({"titulo": "Voo", "hora": v["hora"], "lugar": lugar, "chegar_ate": _hhmm(_min(v["hora"]) - voo_antes_min),
                      "origem": "voo", "id": v["id"]})
    limite = _min(f"{agora:%H:%M}") - 15
    saida = [c for c in saida if _min(c["chegar_ate"]) >= limite]
    return sorted(saida, key=lambda c: _min(c["chegar_ate"]))


def recados_com_lugar(conn, hoje: date, ignorar_id: int | None = None) -> list[dict]:
    """Tarefas de hoje (ou atrasadas) SEM hora: com `local` = recado de lugar; sem `local` mas pedindo posto = posto."""
    saida = []
    for t in conn.execute(
        "SELECT id, title, local FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL AND due_date IS NOT NULL "
        "AND due_date != '' AND due_date <= ? AND (hora IS NULL OR hora = '') ORDER BY due_date DESC, id LIMIT 30", (hoje.isoformat(),)
    ).fetchall():
        if t["id"] == ignorar_id:
            continue
        lugar = (t["local"] or "").strip()
        if lugar:
            saida.append({"titulo": t["title"], "lugar": lugar, "tipo": "lugar", "id": t["id"]})
        elif _RE_POSTO.search(t["title"] or ""):
            saida.append({"titulo": t["title"], "lugar": None, "tipo": "posto", "id": t["id"]})
    return saida[:MAX_PARADAS_TESTADAS * 2]


def _minutos(maps, origem: str, destino: str, partida: datetime) -> int | None:
    try:
        return int(maps.tempo_de_viagem(origem, destino, partida=partida)["duracao_minutos"])
    except Exception:  # noqa: BLE001 - rede / cota / sem rota
        return None


def melhor_parada(maps, origem: str, destino: str, recados: list[dict], direto_min: int, partida: datetime) -> dict | None:
    """O recado que custa menos de EXTRA_MAX_MIN minutos a mais. Mede de verdade (Maps), nao chuta."""
    melhor = None
    for r in recados[:MAX_PARADAS_TESTADAS]:
        lugar = r["lugar"]
        nome = None
        if r["tipo"] == "posto":
            try:
                p = maps.posto_no_meio_do_caminho(origem, destino)
            except Exception:  # noqa: BLE001
                p = None
            if not p:
                continue
            lugar, nome = p["endereco"] or p["nome"], p["nome"]
        ida = _minutos(maps, origem, lugar, partida)
        volta = _minutos(maps, lugar, destino, partida + timedelta(minutes=ida or 0)) if ida is not None else None
        if ida is None or volta is None:
            continue
        extra = ida + volta - direto_min
        if extra <= EXTRA_MAX_MIN and (melhor is None or extra < melhor["extra_min"]):
            melhor = {"titulo": r["titulo"], "lugar": lugar, "nome": nome or lugar, "extra_min": max(0, extra), "ida_min": ida,
                      "tipo": r["tipo"], "id": r["id"]}
    return melhor


def montar(conn, hoje: date, agora: datetime, origem: str | None, maps=None, resolver_lugar=None, voo_antes_min: int = 45) -> dict:
    """Resposta completa de /api/atalho/carro. `maps` = modulo tipo maps_client (None = sem Maps)."""
    comps = compromissos_com_lugar(conn, hoje, agora, voo_antes_min, resolver_lugar)
    if not comps:
        return {"tem": False, "fala": "", "mensagem": "Nada com lugar marcado pra hoje."}
    c = comps[0]
    base = {"tem": True, "titulo": c["titulo"], "hora": c["hora"], "lugar": c["lugar"], "origem_do_compromisso": c["origem"]}
    trajeto = parada = waze = None
    waze_para = c["lugar"]
    if maps is not None and origem:
        partida = agora
        trajeto = _minutos(maps, origem, c["lugar"], partida)
        if trajeto is not None:
            parada = melhor_parada(maps, origem, c["lugar"], recados_com_lugar(conn, hoje, c["id"] if c["origem"] == "tarefa" else None),
                                   trajeto, partida)
        try:
            alvo = parada["lugar"] if parada else c["lugar"]
            waze_para = parada["nome"] if parada else c["lugar"]
            waze = maps.link_waze(maps.coordenada(alvo), alvo)
        except Exception:  # noqa: BLE001
            waze = None
    partes = [f"{c['titulo']} às {_hora_falada(c['hora'])}"]
    chega = None
    if trajeto is not None:
        chega = _hhmm(_min(f"{agora:%H:%M}") + trajeto + (parada["extra_min"] if parada else 0))
        partes[0] += f", tu chega {_hora_falada(chega)}"
    else:
        falta = _min(c["hora"]) - _min(f"{agora:%H:%M}")
        if 0 < falta < 600:
            partes[0] += f", faltam {falta // 60}h{falta % 60:02d}" if falta >= 60 else f", faltam {falta} minutos"
    fala = partes[0] + "."
    if parada:
        quem = parada["nome"] if parada["tipo"] == "posto" else parada["lugar"]
        fala += f" No caminho: {quem}, pra {_acao_do_recado(parada['titulo'])}."
    base.update({"fala": fala, "chega_as": chega, "trajeto_min": trajeto, "parada": parada, "waze": waze, "waze_para": waze_para})
    return base


def _acao_do_recado(titulo: str) -> str:
    t = " ".join((titulo or "").split()).rstrip(".").strip()
    return (t[:1].lower() + t[1:]) if t else "resolver aquilo"


def card(r: dict, agora: datetime) -> dict | None:
    import cards

    if not r.get("tem") or not r.get("fala"):
        return None
    acoes = []
    a = cards.acao_waze(r.get("waze"), r.get("waze_para") if r.get("parada") else None)
    if a:
        acoes.append(a)
    p = r.get("parada") or {}
    return cards.novo_card("carro", {
        "hora": f"{agora:%H:%M}", "titulo": r["titulo"], "hora_compromisso": r["hora"], "chega_as": r.get("chega_as"),
        "fala": r["fala"], "extra_min": p.get("extra_min"), "parada": (p.get("nome") if p else None),
    }, acoes)
