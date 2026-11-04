"""Atividade ao vivo do iPhone (Dynamic Island, tela bloqueada) e widgets do proximo compromisso -
leva "Cards ao vivo" de 04/11/2026 (docs/briefings/2026-11-04-cards-ao-vivo.md, frente 3).

`GET /api/ao-vivo` (token Bearer do widget, `PAINEL_WIDGET_TOKEN`; rota de maquina, sem PIN):
o proximo compromisso de SAIDA ou VOO das proximas ~6 h, ja com os passos
Arrumar -> Sair -> (Parada) -> Chegar em ISO local com fuso. O app iOS (native/ios/App/AoVivo.swift)
liga/atualiza/encerra a Live Activity com isso, e o widget (native/widgetkit) desenha a contagem.

Regras:
  - Nada de calculo novo de horario: tudo vem de `tempo.compromissos` (Maps/iCloud/folga ja la).
  - Nunca o endereco: `lugar` e so o apelido (o que ele escreveu, ou o ICAO do voo). Texto com cara de
    endereco (numero, "Rua ...") vira None.
  - Erro por dentro vira 500 com JSON curto, sem traceback; o app nao mexe na atividade quando nao e 200.
  - Habito e tarefa solta nao viram atividade (decisao do briefing): so `tem_saida` ou voo.
"""

from __future__ import annotations

import hmac
import os
import re
import time as _time
import unicodedata
from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify, request

import tempo

bp = Blueprint("ao_vivo", __name__)

ROTAS_COM_TOKEN = {"/api/ao-vivo"}

JANELA_H = 6  # so compromisso que comeca nas proximas 6 h
DEPOIS_DE_CHEGAR_MIN = 10  # a atividade fica 10 min mostrando "chegou" e some
LEVAR_MAX = 4
CHUVA_GUARDA_CHUVA = 40  # mesma regra do card de saida (briefing): >= 40% leva guarda-chuva
FRIO_CASACO = 17  # <= 17 graus leva casaco

# Cor e icone (SF Symbol) por assunto - as mesmas cores dos cards D (static/css, --card-cor).
ASSUNTOS = {
    "date": {"cor": "#f5a3b8", "icone": "heart.fill"},
    "balada": {"cor": "#c4a1ff", "icone": "music.note"},
    "voo": {"cor": "#8fd0ff", "icone": "airplane"},
    "tarefa": {"cor": "#f0a58f", "icone": "mappin.and.ellipse"},
    "agenda": {"cor": "#f0a58f", "icone": "calendar"},
}

ROTULOS = {"arrumar": "Arrumar", "sair": "Sair", "chegar": "Chegar"}


# ------------------------------------------------------------------ token (so header, nunca ?token=)
def _token_valido() -> bool:
    esperado = os.environ.get("PAINEL_WIDGET_TOKEN") or ""
    cabecalho = request.headers.get("Authorization") or ""
    if not esperado or not cabecalho.lower().startswith("bearer "):
        return False
    enviado = cabecalho[len("Bearer "):].strip()
    return bool(enviado) and hmac.compare_digest(enviado.encode("utf-8"), esperado.encode("utf-8"))


# ------------------------------------------------------------------ utilidades
def _sem_acento(texto: str) -> str:
    base = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in base if not unicodedata.combining(c))


def _iso(dt: datetime) -> str:
    """Hora local do servidor (naive) -> ISO com o fuso local, sem fracao (o Swift le direto)."""
    return dt.replace(microsecond=0).astimezone().isoformat(timespec="seconds")


_CARA_DE_ENDERECO = re.compile(
    r"^(rua|r\.|av\b|av\.|avenida|rod\b|rod\.|rodovia|travessa|tv\.|estrada|alameda|al\.|servidao|praca|br-|sc-)"
)


def apelido_do_lugar(conn, texto) -> str | None:
    """O apelido que ele usa ("oficina", "Viva Beach", "casa do guri"), nunca o endereco. Apelido salvo
    devolve o proprio texto dele; senao so o pedaco antes da virgula, e so se nao tiver cara de endereco."""
    bruto = re.sub(r"\s+", " ", str(texto or "")).strip()
    if not bruto:
        return None
    try:
        import vida_assistente

        if vida_assistente._chave_apelido(bruto) in vida_assistente.apelidos(conn):
            return (bruto[:1].upper() + bruto[1:])[:40]
    except Exception:
        pass
    primeiro = bruto.split(",")[0].split(" - ")[0].strip()
    if not primeiro or re.search(r"\d", primeiro) or _CARA_DE_ENDERECO.search(_sem_acento(primeiro)):
        return None
    return (primeiro[:1].upper() + primeiro[1:])[:40]


def _linha_tarefa(conn, ref):
    try:
        return conn.execute("SELECT estilo, local FROM tasks WHERE id = ?", (ref,)).fetchone()
    except Exception:
        return None


def _origem_voo(conn, ref) -> str | None:
    try:
        r = conn.execute("SELECT origem FROM voos WHERE id = ?", (ref,)).fetchone()
    except Exception:
        return None
    origem = (r["origem"] or "").strip().upper() if r else ""
    return origem if re.fullmatch(r"[A-Z]{4}", origem) else None


_CACHE_CLIMA: dict = {}


def _clima_na_chegada(chegar: datetime) -> dict | None:
    """{"temp", "chuva"} na hora da chegada (cidade padrao, mesma fonte do card de saida). Cache de 20 min:
    o app pergunta a cada abertura/visita."""
    chave = (chegar.date().isoformat(), chegar.hour)
    agora = _time.monotonic()
    ent = _CACHE_CLIMA.get(chave)
    if ent and agora - ent[0] < 1200:
        return ent[1]
    valor = None
    try:
        from rotas._base import app_modulo

        prev = app_modulo()._clima_na_hora(chegar.date().isoformat(), f"{chegar:%H:%M}")
        if prev and prev.get("temp") is not None:
            chuva = prev.get("chuva_pct")
            valor = {"temp": round(prev["temp"]), "chuva": round(chuva) if chuva is not None else None}
    except Exception:
        valor = None
    _CACHE_CLIMA[chave] = (agora, valor)
    return valor


def _levar(conn, lugar_lista: str | None, clima: dict | None) -> list[str]:
    itens: list[str] = []
    if clima:
        if (clima.get("chuva") or 0) >= CHUVA_GUARDA_CHUVA:
            itens.append("Guarda-chuva")
        if clima.get("temp") is not None and clima["temp"] <= FRIO_CASACO:
            itens.append("Casaco")
    if lugar_lista in tempo.LUGARES:
        try:
            ls = tempo.listas(conn)[lugar_lista]
            itens += ls["base"] + ls["extras"]
        except Exception:
            pass
    vistos, saida = set(), []
    for i in itens:
        if isinstance(i, str) and i.strip() and i.lower() not in vistos:
            vistos.add(i.lower())
            saida.append(i.strip()[:30])
    return saida[:LEVAR_MAX]


# ------------------------------------------------------------------ montagem
def _assunto(item: dict, estilo: str | None) -> str:
    if item["kind"] == "voo":
        return "voo"
    if estilo in ("date", "balada"):
        return estilo
    return "agenda" if item["kind"] == "agenda" else "tarefa"


def _passos(conn, item: dict) -> list[dict]:
    evento, sair, comecar = item["evento"], item["sair"], item["comecar"]
    chegar = evento
    if item["kind"] == "voo":
        antes = item.get("chegar_min")
        if isinstance(antes, int) and antes > 0 and evento - timedelta(minutes=antes) > sair:
            chegar = evento - timedelta(minutes=antes)  # chegar no aeroclube pro briefing
    passos = []
    if comecar < sair:
        passos.append(("arrumar", ROTULOS["arrumar"], comecar))
    passos.append(("sair", ROTULOS["sair"], sair))
    parada = item.get("parada")
    if isinstance(parada, dict):
        min_ate = parada.get("min_ate")
        if isinstance(min_ate, (int, float)) and not isinstance(min_ate, bool) and min_ate >= 0:
            em = sair + timedelta(minutes=round(min_ate))
            if sair <= em < chegar:
                nome = apelido_do_lugar(conn, parada.get("nome")) or "Parada"
                passos.append(("parada", nome, em))
    passos.append(("chegar", ROTULOS["chegar"], chegar))
    return [{"chave": c, "rotulo": r, "em": em} for c, r, em in passos]


def _candidato(item: dict) -> bool:
    return item.get("kind") == "voo" or (item.get("kind") != "habito" and bool(item.get("tem_saida")))


def montar(conn, agora: datetime, rede: bool = True, clima_fn=None) -> dict:
    """O JSON de `/api/ao-vivo`. Funcao sem Flask (testavel com relogio injetado). `rede=False` pula
    Maps/iCloud/clima."""
    clima_fn = clima_fn or _clima_na_chegada
    escolhido = None
    for item in tempo.compromissos(conn, agora, rede):
        if not _candidato(item) or item["evento"] - agora > timedelta(hours=JANELA_H):
            continue
        passos = _passos(conn, item)
        chegar = passos[-1]["em"]
        fim = max(chegar + timedelta(minutes=DEPOIS_DE_CHEGAR_MIN), item["evento"])
        if fim <= agora:
            continue
        escolhido = (item, passos, fim)
        if chegar > agora:  # o proximo que ainda nao chegou ganha de um que acabou de chegar
            break
    if escolhido is None:
        return {"ativo": False}

    item, passos, fim = escolhido
    estilo, lugar = None, None
    if item["kind"] == "tarefa":
        linha = _linha_tarefa(conn, item["ref"])
        if linha is not None:
            estilo = linha["estilo"]
            lugar = apelido_do_lugar(conn, linha["local"])
    elif item["kind"] == "voo":
        lugar = _origem_voo(conn, item["ref"])
    lugar = lugar or item.get("lugar")
    assunto = _assunto(item, estilo)
    clima = clima_fn(passos[-1]["em"]) if rede else None
    atual = -1
    for i, p in enumerate(passos):
        if p["em"] <= agora:
            atual = i
    return {
        "ativo": True,
        "id": f"{item['kind']}-{item['ref']}-{item['evento']:%Y-%m-%d}",
        "titulo": str(item.get("titulo") or "Compromisso").strip()[:40],
        "kind": item["kind"],
        "assunto": assunto,
        "icone": ASSUNTOS[assunto]["icone"],
        "cor": ASSUNTOS[assunto]["cor"],
        "lugar": lugar,
        "passos": [{"chave": p["chave"], "rotulo": p["rotulo"], "em": _iso(p["em"])} for p in passos],
        "atual": atual,
        "clima": clima,
        "levar": _levar(conn, item.get("lugar"), clima),
        "evento_em": _iso(item["evento"]),
        "fim_em": _iso(fim),
        "gerado_em": _iso(agora),
    }


def _agora() -> datetime:
    return datetime.now()


def _rede() -> bool:
    return True


@bp.route("/api/ao-vivo", methods=["GET"])
def ao_vivo():
    if not _token_valido():
        return jsonify({"error": "token invalido"}), 401
    try:
        import db

        conn = db.get_db()
        try:
            return jsonify(montar(conn, _agora(), rede=_rede()))
        finally:
            conn.close()
    except Exception:
        current_app.logger.exception("ao-vivo: falhou ao montar")
        return jsonify({"error": "falhou ao montar"}), 500
