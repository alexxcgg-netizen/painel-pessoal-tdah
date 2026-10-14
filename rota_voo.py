"""Rota de um voo agendado (2026-10-14) - pernas, milhas nauticas e horarios estimados.

O Alex sempre sai de Blumenau (SSBL) quando nao diz outro lugar, e a navegacao pode ter
varias pernas ("vou pra Navegantes, depois Floripa e volto"). Aqui so conta em Python: a
distancia de cada perna e a ortodromica entre as coordenadas dos aerodromos conhecidos
(briefing_voo.AERODROMOS) - aerodromo fora da lista fica sem NM (nunca inventa coordenada).

Tempo de voo e ESTIMATIVA grosseira (cruzeiro ~90 kt de aviao de instrucao + subida/trafego
por perna + parada em cada escala) - o card mostra com "~" e o Alex corrige quando contar.
"""

from __future__ import annotations

import math
import re
import unicodedata
from datetime import datetime, timedelta

from briefing_voo import AERODROMOS

ORIGEM_PADRAO = "SSBL"
CRUZEIRO_KT = 90
MIN_POR_PERNA = 6  # subida + entrada no trafego
MIN_POR_ESCALA = 15  # no solo em cada escala (toque/pouso completo, taxi)

_RE_ICAO = re.compile(r"^[A-Z]{4}$")


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn").lower().strip()


# nome falado -> ICAO (so os da regiao que existem em AERODROMOS)
_APELIDOS = {
    "blumenau": "SSBL", "aeroclube": "SSBL", "aeroclube de blumenau": "SSBL", "quero-quero": "SSBL",
    "navegantes": "SBNF", "floripa": "SBFL", "florianopolis": "SBFL", "joinville": "SBJV",
    "curitiba": "SBCT", "afonso pena": "SBCT", "bacacheri": "SBBI", "jaguaruna": "SBJA",
    "chapeco": "SBCH", "lages": "SBLJ", "congonhas": "SBSP", "guarulhos": "SBGR",
}


def aerodromo(texto: str | None) -> str | None:
    """'Navegantes' / 'sbnf' / 'SBNF' -> 'SBNF'. Nome desconhecido volta como veio (curto)."""
    bruto = (texto or "").strip()
    if not bruto:
        return None
    if _RE_ICAO.match(bruto.upper()):
        return bruto.upper()
    return _APELIDOS.get(_sem_acento(bruto), bruto[:40])


def nome(icao: str) -> str:
    info = AERODROMOS.get(icao)
    return info[0] if info else icao


def nm_entre(a: str, b: str) -> float | None:
    pa, pb = AERODROMOS.get(a), AERODROMOS.get(b)
    if not pa or not pb:
        return None
    la1, lo1, la2, lo2 = map(math.radians, (pa[1], pa[2], pb[1], pb[2]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 3440.065 * 2 * math.asin(math.sqrt(h))


def escalas_texto(escalas) -> str | None:
    """Lista falada -> 'SBNF,SBFL' pra guardar na coluna voos.escalas."""
    if not isinstance(escalas, list):
        return None
    limpas = [a for a in (aerodromo(e) for e in escalas if isinstance(e, str)) if a]
    return ",".join(limpas[:8]) or None


def montar(origem: str | None, escalas: str | None, destino: str, hora: str | None) -> dict:
    """Paradas, pernas com NM (None quando nao da pra medir), total e horarios estimados."""
    paradas = [aerodromo(origem) or ORIGEM_PADRAO]
    paradas += [e for e in (escalas or "").split(",") if e]
    paradas.append(aerodromo(destino) or destino)
    pernas = []
    for a, b in zip(paradas, paradas[1:]):
        nm = nm_entre(a, b)
        pernas.append({"nm": round(nm) if nm is not None else None})
    # voo local (sai e volta pro mesmo lugar sem escala, o mais comum no curso): sem pernas
    local = len(paradas) == 2 and paradas[0] == paradas[1]
    if local:
        pernas = []
    medidas = [p["nm"] for p in pernas]
    total = sum(medidas) if medidas and all(m is not None for m in medidas) else None
    em_voo = None
    pouso = None
    saida = [{"icao": p, "nome": nome(p)} for p in paradas]
    if hora:
        saida[0]["decola"] = hora
    if total is not None:
        em_voo = round(sum(m / CRUZEIRO_KT * 60 + MIN_POR_PERNA for m in medidas))
        try:
            relogio = datetime.strptime(hora or "", "%H:%M")
        except ValueError:
            relogio = None
        if relogio is not None:
            # horario estimado de cada pouso/decolagem ao longo da rota
            for i, m in enumerate(medidas, start=1):
                relogio += timedelta(minutes=round(m / CRUZEIRO_KT * 60 + MIN_POR_PERNA))
                saida[i]["pousa"] = f"{relogio:%H:%M}"
                if i < len(medidas):
                    relogio += timedelta(minutes=MIN_POR_ESCALA)
                    saida[i]["decola"] = f"{relogio:%H:%M}"
            pouso = saida[-1]["pousa"]
    return {
        "paradas": saida,
        "local": local,
        "pernas": pernas,
        "total_nm": total,
        "em_voo_min": em_voo,
        "pouso": pouso,
    }


def menos_minutos(hora: str | None, minutos: int) -> str | None:
    try:
        return f"{datetime.strptime(hora or '', '%H:%M') - timedelta(minutes=minutos):%H:%M}"
    except ValueError:
        return None
