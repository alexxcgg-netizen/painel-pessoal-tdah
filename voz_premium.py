"""Voz natural (ElevenLabs Eleven v4 Turbo) so pra frases CURTAS.

O plano gratis tem ~10 mil creditos/mes (~10 mil caracteres), entao so frases
curtas e deterministicas (sem IA) passam por aqui: resumo da manha, fechamento
da noite e a primeira frase de uma resposta do chat. Tudo que nao der (sem
chave, limite do mes, erro, offline) devolve None e o front cai sozinho na voz
do iPhone (falarTexto/SpeechSynthesis).

O v4 SO funciona pelo endpoint text-to-dialogue (o text-to-speech normal
recusa). Cache em `voz_cache` (mesma frase nao gasta credito de novo) e
contagem mensal em `voz_uso`. Nunca loga a chave da API.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import date, timedelta

import requests

log = logging.getLogger(__name__)

URL_DIALOGO = "https://api.elevenlabs.io/v1/text-to-dialogue"
MODELO_PADRAO = "eleven_v4_turbo"
LIMITE_MES_PADRAO = 9000
MAX_CARACTERES = 700  # resposta falada inteira (modo conversa: 2-4 frases)
TIMEOUT_S = 15
NOME_PADRAO = "Alex"
MAX_TITULO = 60


def _chave() -> str:
    return (os.environ.get("ELEVENLABS_API_KEY") or "").strip()


def _voz() -> str:
    return (os.environ.get("ELEVENLABS_VOICE_ID") or "").strip()


def _modelo() -> str:
    return (os.environ.get("ELEVENLABS_MODELO") or "").strip() or MODELO_PADRAO


def configurado() -> bool:
    return bool(_chave() and _voz())


def limite_mes() -> int:
    try:
        v = int(os.environ.get("ELEVENLABS_LIMITE_MES", LIMITE_MES_PADRAO))
        return v if v >= 0 else LIMITE_MES_PADRAO
    except (TypeError, ValueError):
        return LIMITE_MES_PADRAO


def mes_atual(hoje: date | None = None) -> str:
    return (hoje or date.today()).strftime("%Y-%m")


def uso_do_mes(conn, mes: str | None = None) -> int:
    row = conn.execute("SELECT caracteres FROM voz_uso WHERE mes = ?", (mes or mes_atual(),)).fetchone()
    return int(row["caracteres"]) if row else 0


def _somar_uso(conn, caracteres: int, mes: str | None = None) -> None:
    conn.execute(
        "INSERT INTO voz_uso (mes, caracteres) VALUES (?, ?) "
        "ON CONFLICT(mes) DO UPDATE SET caracteres = caracteres + excluded.caracteres",
        (mes or mes_atual(), caracteres),
    )
    conn.commit()


# ---------------------------------------------------------------- frases

def _titulo_curto(titulo) -> str:
    t = " ".join(str(titulo or "").split())
    return t[:MAX_TITULO].rstrip()


def _hora_falada(hora) -> str:
    """'09:00' -> 'as 9h', '14:30' -> 'as 14h30'. Formato invalido -> ''."""
    try:
        h, m = str(hora).split(":")[:2]
        h, m = int(h), int(m)
        if not (0 <= h < 24 and 0 <= m < 60):
            return ""
    except (ValueError, TypeError):
        return ""
    return f" às {h}h" if m == 0 else f" às {h}h{m:02d}"


def frase_curta_manha(conn, hoje: date | None = None, nome: str = NOME_PADRAO) -> str:
    hoje = hoje or date.today()
    tarefas = conn.execute(
        "SELECT title, hora FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL "
        "AND due_date = ? ORDER BY hora IS NULL, hora, id",
        (hoje.isoformat(),),
    ).fetchall()
    if not tarefas:
        return f"Bom dia, {nome}. Nada marcado pra hoje. Dá uma olhada no painel."
    primeira = tarefas[0]
    titulo = _titulo_curto(primeira["title"])
    hora = _hora_falada(primeira["hora"])
    if len(tarefas) == 1:
        return f"Bom dia, {nome}. Hoje é só 1 tarefa: {titulo}{hora}. Dá uma olhada no painel."
    return (
        f"Bom dia, {nome}. Hoje são {len(tarefas)} tarefas, a primeira é {titulo}{hora}. "
        "O resto tá no painel."
    )


def frase_curta_noite(conn, hoje: date | None = None) -> str:
    hoje = hoje or date.today()
    concluidas = conn.execute(
        "SELECT COUNT(*) AS n FROM tasks WHERE date(completed_at) = ?", (hoje.isoformat(),)
    ).fetchone()["n"]
    pendentes = conn.execute(
        "SELECT COUNT(*) AS n FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL AND due_date = ?",
        (hoje.isoformat(),),
    ).fetchone()["n"]
    total = concluidas + pendentes
    amanha = conn.execute(
        "SELECT title FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL AND due_date = ? "
        "ORDER BY hora IS NULL, hora, id LIMIT 1",
        ((hoje + timedelta(days=1)).isoformat(),),
    ).fetchone()
    if total == 0:
        partes = ["Hoje não tinha nada marcado."]
    else:
        partes = [f"Fechou {concluidas} de {total} hoje."]
    if amanha:
        partes.append(f"Amanhã começa com {_titulo_curto(amanha['title'])}.")
    partes.append("O resto tá no painel.")
    return " ".join(partes)


# ------------------------------------------------------------ sintetizar

def _chave_cache(texto: str) -> str:
    base = f"{_modelo()}\x00{_voz()}\x00{texto}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def sintetizar(conn, texto) -> bytes | None:
    """Audio mp3 da frase, ou None (sem chave, limite, erro, texto invalido)."""
    if not configurado():
        return None
    if not isinstance(texto, str):
        return None
    texto = texto.strip()
    if not texto or len(texto) > MAX_CARACTERES:
        return None

    chave = _chave_cache(texto)
    row = conn.execute("SELECT audio FROM voz_cache WHERE chave = ?", (chave,)).fetchone()
    if row and row["audio"]:
        return bytes(row["audio"])

    mes = mes_atual()
    if uso_do_mes(conn, mes) + len(texto) > limite_mes():
        return None

    try:
        resp = requests.post(
            URL_DIALOGO,
            params={"output_format": "mp3_44100_64"},
            headers={"xi-api-key": _chave()},
            json={"inputs": [{"text": texto, "voice_id": _voz()}], "model_id": _modelo()},
            timeout=TIMEOUT_S,
        )
    except Exception as exc:  # rede, timeout, SSL... nunca derruba a rota
        log.warning("voz premium: falha de rede (%s)", type(exc).__name__)
        return None
    if resp.status_code != 200:
        log.warning("voz premium: ElevenLabs respondeu status %s", resp.status_code)
        return None
    audio = resp.content
    if not audio:
        log.warning("voz premium: ElevenLabs devolveu audio vazio")
        return None

    try:
        _somar_uso(conn, len(texto), mes)
        conn.execute(
            "INSERT OR REPLACE INTO voz_cache (chave, audio, criado_em) VALUES (?, ?, datetime('now'))",
            (chave, audio),
        )
        conn.commit()
    except Exception as exc:  # o audio ja veio: entrega mesmo se o cache falhar
        log.warning("voz premium: nao gravou cache/uso (%s)", type(exc).__name__)
    return audio
