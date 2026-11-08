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
from datetime import date, datetime, timedelta

import requests

import db
import fala_ptbr

log = logging.getLogger(__name__)

URL_DIALOGO = "https://api.elevenlabs.io/v1/text-to-dialogue"
URL_TTS = "https://api.elevenlabs.io/v1/text-to-speech/{voz}"
# 2026-10-10: flash v2.5 gera ~231 caracteres em ~0,9 s; o v4 turbo levava ~3,5 s (medido) -
# na conversa por voz isso era a "demora" da Roberta. Mesmo custo (0,5 credito/caractere).
# v4/v3 so funcionam pelo text-to-dialogue; o resto usa o text-to-speech normal.
MODELO_PADRAO = "eleven_flash_v2_5"
# 2026-10-13: escolhida pelo Alex entre amostras A/B (amostra "B" da rodada 1,
# https://claude.ai/artifact/DWRJQMHLCnoXYKh12rvgJe): mesma voz e modelo, mais solta (estabilidade
# 0.35 em vez do padrao da voz) e audio com o dobro de qualidade - "parecia robo". So vale pro
# text-to-speech (v3/v4 pelo text-to-dialogue nao aceitam esses ajustes). Mudar aqui = mudar
# AJUSTES_VERSAO, senao o cache devolve o audio velho.
AJUSTES_VOZ = {"stability": 0.35, "similarity_boost": 0.8, "use_speaker_boost": True, "speed": 1.0}
AJUSTES_VERSAO = "b1"
FORMATO_AUDIO = "mp3_44100_128"
LIMITE_MES_PADRAO = 9000
MAX_CARACTERES = 700  # resposta falada inteira (modo conversa: 2-4 frases)
TIMEOUT_S = 10
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


def saudacao_da_hora(hora: int) -> str:
    """Mesma regra do titulo do Inicio (saudacaoDaHora, static/js/secoes/hoje/saudacao.js)."""
    if hora < 5:
        return "Boa noite"
    if hora < 12:
        return "Bom dia"
    if hora < 18:
        return "Boa tarde"
    return "Boa noite"


def frase_curta_manha(conn, hoje: date | None = None, nome: str = NOME_PADRAO, agora: datetime | None = None) -> str:
    """Botao "Ouvir" do Inicio. Antes dava "Bom dia" sempre (bug do Alex, 2026-10-13): a
    saudacao segue a hora e, depois do meio-dia, fala do que AINDA falta e da proxima."""
    agora = agora or datetime.now()
    hoje = hoje or agora.date()
    # exclamacao como na amostra escolhida pelo Alex: entonacao mais viva que o ponto
    saudacao = f"{saudacao_da_hora(agora.hour)}, {nome}!"
    tarefas = conn.execute(
        "SELECT title, hora FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL "
        "AND due_date = ? ORDER BY hora IS NULL, hora, id",
        (hoje.isoformat(),),
    ).fetchall()
    manha = 5 <= agora.hour < 12
    if not tarefas:
        if manha:
            return f"{saudacao} Nada marcado pra hoje. Dá uma olhada no painel."
        return f"{saudacao} Nada pendente pra hoje."
    if manha:
        primeira = tarefas[0]
        titulo = _titulo_curto(primeira["title"])
        hora = _hora_falada(primeira["hora"])
        if len(tarefas) == 1:
            return f"{saudacao} Hoje é só 1 tarefa: {titulo}{hora}. Dá uma olhada no painel."
        return (
            f"{saudacao} Hoje são {len(tarefas)} tarefas, a primeira é {titulo}{hora}. "
            "O resto tá no painel."
        )
    # tarde/noite: a proxima e a primeira com horario ainda pela frente (senao a primeira da lista)
    agora_hm = agora.strftime("%H:%M")
    proxima = next((t for t in tarefas if (t["hora"] or "") >= agora_hm and _hora_falada(t["hora"])), tarefas[0])
    titulo = _titulo_curto(proxima["title"])
    hora = _hora_falada(proxima["hora"])
    if len(tarefas) == 1:
        return f"{saudacao} Ainda falta 1 tarefa hoje: {titulo}{hora}."
    return f"{saudacao} Ainda faltam {len(tarefas)} tarefas hoje, a próxima é {titulo}{hora}."


def frase_curta_noite(conn, hoje: date | None = None) -> str:
    hoje = hoje or date.today()
    concluidas = conn.execute(
        f"SELECT COUNT(*) AS n FROM tasks WHERE {db.dia_local_sql('completed_at')} = ?", (hoje.isoformat(),)
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
    base = f"{_modelo()}\x00{_voz()}\x00{AJUSTES_VERSAO}\x00{texto}"
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
    # "14:30", "R$ 1.250,90", "180g", "TDAH"... viram fala de gente antes do
    # TTS (o flash_v2_5 nao normaliza pt-BR sozinho). A cota conta o texto
    # que realmente vai pra ElevenLabs.
    texto = fala_ptbr.normalizar(texto) or texto

    chave = _chave_cache(texto)
    row = conn.execute("SELECT audio FROM voz_cache WHERE chave = ?", (chave,)).fetchone()
    if row and row["audio"]:
        return bytes(row["audio"])

    mes = mes_atual()
    if uso_do_mes(conn, mes) + len(texto) > limite_mes():
        return None

    modelo = _modelo()
    if modelo.startswith(("eleven_v4", "eleven_v3")):
        url, corpo = URL_DIALOGO, {"inputs": [{"text": texto, "voice_id": _voz()}], "model_id": modelo}
    else:
        url, corpo = URL_TTS.format(voz=_voz()), {
            "text": texto, "model_id": modelo, "language_code": "pt", "voice_settings": AJUSTES_VOZ,
        }
    try:
        resp = requests.post(
            url,
            params={"output_format": FORMATO_AUDIO},
            headers={"xi-api-key": _chave()},
            json=corpo,
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
