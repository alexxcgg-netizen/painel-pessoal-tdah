"""Bom dia ao parar o alarme (leva Lab v4, ideia "bom-dia", 30/10/2026).

Tu acorda, pega o celular e se perde no Instagram antes de saber o que tem no dia. Uma automacao do Atalhos
("Alarme" -> "Parado", Executar Imediatamente) chama `GET|POST /api/atalho/bom-dia` (token dos Atalhos) mandando o sono
que leu do app Saude; o painel devolve em ~20 segundos de fala:

    Sono           6h40 . dormiu 23:50        (barra: fracao das 8 h, meta do Alex)
    Agenda         Voo 9:00 . academia 18:30
    Tempo          Ceu limpo, vento 8 kt . VFR  (com voo hoje: METAR do aerodromo; senao o clima da cidade)
    Primeiro passo Cafe e mochila: sair as 8:05

e o mesmo vira o card `bom_dia` no chat (1x por dia). O que mais acontece quando o alarme para:
  - o sono vai pra `saude_dados` (resolve o "sono automatico" que ficou pra depois: 1 campo no Atalho);
  - "acordou agora" (`vida_assistente.registrar_acordou`) alimenta a meta de comida e o "primeira refeicao ate";
  - o sinal `acordei` (P7) e o gatilho `acordar` dos combinados "se-entao" disparam.
A voz e a do ElevenLabs que ja existe (`voz_premium`), pelo `audio_url` da resposta; sem chave/limite o Atalho cai no
"Falar texto" do iPhone com o campo `fala`. Passo a passo do Atalho: `docs/briefings/2026-10-30-lab-v4-avisos.md`.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

META_SONO_H = 8.0  # CARDS.md: "Sono: 8 h" aprovado pelo Alex
SONO_MIN_H, SONO_MAX_H = 0.5, 16.0
MAX_FALA = 600


def _num(v) -> float | None:
    """'6.7', '6,7', 6.7 -> 6.7; '6h40' -> 6.667; lixo -> None."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    t = str(v).strip().lower().replace(",", ".")
    m = re.fullmatch(r"(\d{1,2})\s*h\s*(\d{1,2})?\s*(?:min)?", t)
    if m:
        return int(m.group(1)) + (int(m.group(2)) / 60 if m.group(2) else 0)
    try:
        return float(t)
    except ValueError:
        return None


def _hora_min(v) -> int | None:
    """Minuto do dia de '23:50', '2026-10-29T23:50:00-03:00' ou '29/10/2026 23:50'."""
    if not isinstance(v, str):
        return None
    m = re.search(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)", v)
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))


def ler_sono(corpo: dict) -> tuple[float | None, str | None]:
    """(horas dormidas, 'HH:MM' que foi dormir) a partir do que o Atalho mandou. Aceita `sono_horas` direto, ou
    `dormiu` + `acordou` (a duracao e a diferenca, atravessando a meia-noite). Fora de 0,5-16 h = ignora."""
    dormiu = None
    m = _hora_min(corpo.get("dormiu"))
    if m is not None:
        dormiu = f"{m // 60:02d}:{m % 60:02d}"
    horas = _num(corpo.get("sono_horas"))
    if horas is None and m is not None:
        a = _hora_min(corpo.get("acordou"))
        if a is not None:
            horas = ((a - m) % 1440) / 60
    if horas is not None and not (SONO_MIN_H <= horas <= SONO_MAX_H):
        horas = None
    return (round(horas, 2) if horas is not None else None), dormiu


def horas_texto(h: float) -> str:
    """6.67 -> '6h40'"""
    total = int(round(h * 60))
    return f"{total // 60}h{total % 60:02d}"


def _hora_curta(hora: str) -> str:
    h, _, m = hora.partition(":")
    return f"{int(h)}:{m}"


def linha_sono(horas: float | None, dormiu: str | None) -> dict | None:
    if horas is None:
        return None
    texto = horas_texto(horas) + (f" · dormiu {dormiu}" if dormiu else "")
    return {"rot": "Sono", "valor": texto, "trilho": round(min(1.0, horas / META_SONO_H), 3)}


def linha_agenda(eventos: list[dict], voos: list[dict], sem_hora: int) -> dict:
    itens = []
    for v in voos:
        if v.get("hora"):
            itens.append((v["hora"], "Voo"))
    for e in eventos:
        if e.get("dia_inteiro") or e.get("concluido") or not e.get("inicio"):
            continue
        hora = str(e["inicio"])[11:16]
        if re.fullmatch(r"\d{2}:\d{2}", hora):
            itens.append((hora, " ".join(str(e.get("titulo") or "").split())[:24] or "Compromisso"))
    itens = sorted(set(itens))[:3]
    if itens:
        texto = " · ".join(f"{t} {_hora_curta(h)}" for h, t in itens)
    elif sem_hora:
        texto = f"Nada com hora · {sem_hora} {'tarefa' if sem_hora == 1 else 'tarefas'} no dia"
    else:
        texto = "Nada marcado hoje"
    return {"rot": "Agenda", "valor": texto}


def linha_tempo(tempo: str | None) -> dict | None:
    return {"rot": "Tempo", "valor": tempo} if tempo else None


def linha_passo(primeiro: dict | None, tarefa: str | None) -> dict | None:
    if primeiro and primeiro.get("sair"):
        return {"rot": "Primeiro passo", "valor": f"Levanta e se arruma: sair às {_hora_curta(primeiro['sair'])}"}
    if tarefa:
        return {"rot": "Primeiro passo", "valor": tarefa[:60]}
    return None


# ----------------------------------------------------------------- fala


def _hora_falada(hhmm: str) -> str:
    h, _, m = hhmm.partition(":")
    return f"{int(h)}h" if m in ("", "00") else f"{int(h)}h{m}"


def montar_fala(linhas: list[dict], saudacao: str, nome: str = "Alex") -> str:
    """O mesmo conteudo do card, em frases curtas pra ouvir (~20 s). Horas viram '9h' / '18h30'."""
    partes = [f"{saudacao}, {nome}!"]
    for l in linhas:
        v = l["valor"]
        if l["rot"] == "Sono":
            h = re.match(r"(\d+)h(\d{2})", v)
            partes.append(f"Tu dormiu {int(h.group(1))} horas e {int(h.group(2))} minutos." if h and h.group(2) != "00"
                          else f"Tu dormiu {int(h.group(1))} horas." if h else "")
        elif l["rot"] == "Agenda":
            if v.startswith("Nada"):
                partes.append(v.split(" · ")[0].rstrip(".") + ".")
            else:
                itens = [re.sub(r"(\d{1,2}):(\d{2})$", lambda m: _hora_falada(f"{m.group(1)}:{m.group(2)}"), x.strip()) for x in v.split(" · ")]
                itens = [re.sub(r"^(.+?) (\d+h(?:\d{2})?)$", r"\1 às \2", x) for x in itens]
                partes.append("Hoje: " + " e ".join(itens) + ".")
        elif l["rot"] == "Tempo":
            partes.append(v.rstrip(".") + ".")
        else:
            m = re.search(r"sair às (\d{1,2}:\d{2})", v)
            partes.append(f"Primeiro passo: levanta e se arruma, sai às {_hora_falada(m.group(1))}." if m else f"Primeiro passo: {v}.")
    fala = " ".join(p for p in partes if p)
    return fala[:MAX_FALA]


def montar(*, agora: datetime, corpo: dict, eventos: list[dict], voos: list[dict], sem_hora: int, tempo: str | None,
           primeiro: dict | None, tarefa_primeira: str | None, sono_salvo: float | None = None) -> dict:
    """Tudo que o bom dia mostra e fala. Puro (a rota busca agenda/tempo e passa pronto)."""
    horas, dormiu = ler_sono(corpo)
    veio_do_atalho = horas is not None
    if horas is None:
        horas = sono_salvo  # ja tinha vindo do Saude (/api/saude/importar) hoje
    linhas = [l for l in (linha_sono(horas, dormiu), linha_agenda(eventos, voos, sem_hora), linha_tempo(tempo),
                          linha_passo(primeiro, tarefa_primeira)) if l]
    from voz_premium import saudacao_da_hora

    return {
        "hora": f"{agora:%H:%M}",
        "sono_horas": horas,
        "sono_do_atalho": veio_do_atalho,
        "linhas": linhas,
        "fala": montar_fala(linhas, saudacao_da_hora(agora.hour)),
    }


def tempo_da_manha(cidade_clima, voo_hoje_icao: str | None, buscar_metar=None, buscar_clima=None) -> str | None:
    """Linha 'Tempo'. Com voo hoje: METAR do aerodromo de origem (categoria + vento), que e o que interessa pra ele;
    senao o clima da cidade. Rede falhou = None (a linha some, o resto do bom dia segue)."""
    if voo_hoje_icao:
        try:
            if buscar_metar is None:
                import metar

                buscar_metar = metar.buscar_metar_taf
            r = buscar_metar(voo_hoje_icao)
            dec = r.get("metar_decodificado") or {}
            partes = []
            v = dec.get("vento")
            if v:
                partes.append(f"vento {v['velocidade_kt']} kt")
            if r.get("metar_categoria"):
                partes.append(str(r["metar_categoria"]))
            if partes:
                return f"{voo_hoje_icao}: " + " · ".join(partes)
        except Exception:  # noqa: BLE001 - rede
            pass
    try:
        if buscar_clima is None:
            return None
        c = buscar_clima(cidade_clima)
        if not c:
            return None
        txt = str(c.get("condicao") or "").capitalize()
        if c.get("temperatura") is not None:
            txt += f", {round(c['temperatura'])}°"
        return txt or None
    except Exception:  # noqa: BLE001
        return None
