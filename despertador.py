"""Despertador pedido pelo Alex no chat ("amanha quero acordar as 7").

O painel NAO consegue tocar o alarme do iPhone sozinho (a Apple so deixa o app Atalhos criar
alarme). Entao o pedido fica guardado aqui e o Atalho "Despertador do Painel" o busca em
`GET /api/atalho/despertador` (automacao das 22h, ou um toque no botao do card do chat, que abre
o Atalho na hora). Um pedido vale para UMA data; se um compromisso do mesmo dia exigir acordar
antes, o endpoint devolve o mais cedo (acordar atrasado perde o voo; a IA avisa o Alex).
"""

from __future__ import annotations

import json
import re
from datetime import date

import db

CHAVE = "despertador_pedido"
NOME_ATALHO = "Despertador do Painel"


_HORA = re.compile(r"^\s*(\d{1,2})\s*(?:[:h]\s*(\d{2})?)?\s*(?:h|horas?)?\s*$", re.IGNORECASE)


def normalizar_hora(texto) -> str | None:
    """"07:00", "7:00", "7h", "7h30", "7" -> "HH:MM"; qualquer outra coisa -> None (nunca chuta)."""
    m = _HORA.match(texto) if isinstance(texto, str) else None
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    return f"{h:02d}:{mi:02d}" if 0 <= h <= 23 and 0 <= mi <= 59 else None


def guardar(conn, hora: str, dia: str) -> None:
    db.definir_configuracao(conn, CHAVE, json.dumps({"data": dia, "hora": hora}))


def cancelar(conn) -> bool:
    existia = db.obter_configuracao(conn, CHAVE) not in (None, "")
    db.definir_configuracao(conn, CHAVE, "")
    return existia


def pedido(conn, dia: str) -> str | None:
    """Hora (HH:MM) que o Alex pediu pra `dia` (AAAA-MM-DD), ou None."""
    try:
        dado = json.loads(db.obter_configuracao(conn, CHAVE) or "{}")
    except ValueError:
        return None
    if not isinstance(dado, dict) or dado.get("data") != dia:
        return None
    hora = dado.get("hora")
    return hora if isinstance(hora, str) and len(hora) == 5 else None


def mais_cedo(pedida: str | None, do_compromisso: str | None) -> str | None:
    """HH:MM comparam como texto. O que exigir acordar antes ganha."""
    opcoes = [h for h in (pedida, do_compromisso) if h]
    return min(opcoes) if opcoes else None


def dia_alvo(agora, quando_data: str | None) -> str:
    """Sem data: "amanha" - a nao ser que ja seja madrugada (antes das 4h), quando "acordar as 7"
    e o proprio dia, igual ao endpoint do Atalho."""
    if quando_data:
        return quando_data
    return (agora.date() if agora.hour < 4 else date.fromordinal(agora.date().toordinal() + 1)).isoformat()
