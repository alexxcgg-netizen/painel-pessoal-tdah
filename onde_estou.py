"""Leva "onde eu estou" (2026-11-04, docs/briefings/2026-11-04-onde-eu-estou.md).

O app iOS manda as visitas do iPhone (CLLocationManager.startMonitoringVisits: chegou num lugar
e ficou / saiu dele) pra `POST /api/localizacao/visita` (rotas/onde_estou.py). Aqui:

  - grava a visita (tabela `visitas`, 30 dias, lat/lon com 4 casas) e junta "chegou" com o
    "saiu" da mesma visita;
  - reconhece o lugar: apelidos de `vida_assistente.apelidos` + casa (ENDERECO_CASA),
    geocodificados UMA vez e guardados na config `lugares_coordenadas`; raio de 150 m;
  - chegou num lugar conhecido: mensagem no chat + push/Telegram, uma por visita
    ("Chegou no mecânico. Agora é: levar o carro. Depois: imprimir as contas às 11h.");
  - atrasou: se agora + trajeto ate a proxima tarefa com hora passa da hora dela por mais de
    10 min, empurra ela e as seguintes de hoje (arredondado pra 5 min), com Desfazer (card
    `edicao` + acoes_desfazer, o mesmo do chat). Inegociavel e voo sao parede: nao mexe neles
    nem no que vem depois. Uma vez por tarefa por dia (notificacoes_enviadas);
  - contexto do chat: "Agora (pelo iPhone): no mecânico desde 07:20".

Texto por template (zero IA). Nunca da baixa em tarefa sozinho.
"""

import json
import logging
import math
import os
import re
import threading
import time as _time
import unicodedata
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import cards
import db
import maps_client
import notificacoes
import vida_assistente

log = logging.getLogger(__name__)

FUSO = ZoneInfo("America/Sao_Paulo")
RETENCAO_DIAS = 30
CASAS_COORD = 4  # ~11 m
RAIO_M = 150  # "esta no lugar"
RAIO_MAX_M = 250  # visita imprecisa estica o raio ate aqui, nunca mais
MESMA_VISITA_M = 300  # "chegou" e "saiu" da mesma visita (o iOS pode mexer um pouco no ponto)
MESMA_VISITA_S = 120
MESMA_ENTRADA_S = 30 * 60  # entrada pela cerca e pela visita do iOS no mesmo lugar ainda aberto
ATRASO_MIN = 10  # tolerancia antes de empurrar
ARREDONDA_MIN = 5
JANELA_TRAJETO_MIN = 120  # so consulta trajeto (cota do Maps) pra tarefa que comeca em ate 2 h
TAREFA_VELHA_MIN = 60  # tarefa que passou da hora ha mais de 1 h nao e mais "a proxima"
VISITA_ABERTA_MAX_H = 18  # visita sem "saiu" mais velha que isso: o iOS perdeu a saida
SAIU_RECENTE_H = 2  # contexto do chat: "saiu de casa as 07:05" so ate 2 h depois
CHEGADA_RECENTE_MIN = 45  # visita que chega atrasada (fila offline) nao gera "chegou" velho
SAIDA_RECENTE_MIN = 30  # idem pro atraso calculado na saida
TRAJETO_CACHE_S = 20 * 60
CONFIG_COORDS = "lugares_coordenadas"
TIPO_CHEGADA = "chegou_lugar"
TIPO_ATRASO = "atraso_lugar"
URL_CHAT = "/?aba=assistente"

# Testes desligam pra reacao rodar na mesma thread (deterministico).
REAGIR_EM_THREAD = True

_RE_VOO = re.compile(r"\b(voo|simulador)\b")
_RE_ATE = re.compile(r"\((at[eé]) (\d{1,2}):(\d{2})\)")
_cache_trajeto: dict[tuple[str, str], tuple[float, int]] = {}


def _sem_acento(texto: str) -> str:
    base = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in base if not unicodedata.combining(c)).strip()


def _metros(a, b) -> float:
    return maps_client._km(a, b) * 1000


# ------------------------------------------------------------------ entrada (validacao)


def ler_horario(valor) -> datetime | None:
    """ISO 8601 do iPhone ('2026-11-04T10:20:00Z', com fuso ou sem) -> hora local de Brasilia
    sem fuso. Qualquer coisa estranha (inclusive o distantPast/distantFuture do iOS) -> None."""
    if not isinstance(valor, str) or not valor.strip() or len(valor) > 40:
        return None
    txt = valor.strip()
    if txt.endswith(("Z", "z")):
        txt = txt[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError:
        return None
    if dt.tzinfo:
        dt = dt.astimezone(FUSO).replace(tzinfo=None)
    if not 2020 <= dt.year <= 2100:
        return None
    return dt.replace(microsecond=0)


def validar(corpo, agora: datetime) -> dict | str:
    """Corpo do POST -> dados limpos, ou o texto do erro (400)."""
    if not isinstance(corpo, dict):
        return "corpo invalido"
    try:
        lat, lon = float(corpo.get("lat")), float(corpo.get("lon"))
    except (TypeError, ValueError):
        return "lat/lon invalidos"
    if not (math.isfinite(lat) and math.isfinite(lon)) or not (-90 <= lat <= 90 and -180 <= lon <= 180) \
            or (lat == 0 and lon == 0):
        return "lat/lon invalidos"
    try:
        precisao = float(corpo["precisao"]) if corpo.get("precisao") is not None else None
    except (TypeError, ValueError):
        precisao = None
    if precisao is not None and (not math.isfinite(precisao) or precisao < 0):
        precisao = None
    chegada, saida = ler_horario(corpo.get("chegada")), ler_horario(corpo.get("saida"))
    if not chegada and not saida:
        return "falta chegada ou saida"
    limite = agora + timedelta(minutes=10)
    if (chegada and chegada > limite) or (saida and saida > limite):
        return "horario no futuro"
    if chegada and saida and saida < chegada:
        return "saida antes da chegada"
    # cerca do iPhone (06/11, GPS mais esperto): mesma rota, `fonte: "cerca"` e o apelido do lugar da cerca
    lugar = corpo.get("lugar")
    lugar = vida_assistente._chave_apelido(lugar) if isinstance(lugar, str) and len(lugar) <= 120 else None
    cerca = corpo.get("cerca")  # id da cerca (viagem_acompanhada._id_cerca): "casa" ou "c" + 10 hex
    cerca = cerca if isinstance(cerca, str) and re.fullmatch(r"[a-z0-9]{1,20}", cerca) else None
    return {
        "lat": round(lat, CASAS_COORD), "lon": round(lon, CASAS_COORD),
        "precisao": round(min(precisao, 100000), 1) if precisao is not None else None,
        "chegada": chegada, "saida": saida,
        "fonte": "cerca" if corpo.get("fonte") == "cerca" else "visita", "lugar": lugar or None,
        "cerca": cerca,
    }


# ------------------------------------------------------------------ lugares conhecidos


def _lugares(conn, dia: str | None = None) -> list[dict]:
    lista = [{"apelido": k, "endereco": v} for k, v in sorted(vida_assistente.apelidos(conn).items())]
    casa = os.environ.get("ENDERECO_CASA", "").strip()
    if casa:
        lista.append({"apelido": "casa", "endereco": casa})
    else:  # 07/11: sem ENDERECO_CASA, a casa aprendida pelo GPS (onde ele dorme) vale como endereco
        item = _carregar_coords(conn).get("casa")
        if isinstance(item, dict) and item.get("origem") == "gps" and not item.get("endereco") \
                and isinstance(item.get("lat"), (int, float)) and isinstance(item.get("lon"), (int, float)):
            lista.append({"apelido": "casa", "endereco": f"{item['lat']},{item['lon']}"})
    # assistente passo a passo (04/11): a parada e o destino dos compromissos de sair de hoje viram lugar
    # reconhecivel mesmo sem apelido salvo (geocodifica uma vez, igual aos apelidos)
    ja = {x["apelido"] for x in lista}
    for t in _saidas_de_hoje(conn, dia or datetime.now().date().isoformat()):
        for texto, e_parada in ((t["parada"], True), (t["local"], False)):
            texto = (texto or "").strip()
            chave = vida_assistente._chave_apelido(texto)
            if not chave or chave in ja or (e_parada and vida_assistente.apelido_dentro(conn, texto)):
                continue
            lista.append({"apelido": chave, "endereco": texto})
            ja.add(chave)
    return lista


def _carregar_coords(conn) -> dict:
    try:
        dado = json.loads(db.obter_configuracao(conn, CONFIG_COORDS) or "{}")
    except ValueError:
        return {}
    return dado if isinstance(dado, dict) else {}


def _coordenada(conn, lugar: dict, cache: dict, hoje: str) -> tuple[float, float] | None:
    """Endereco -> (lat, lon). 'lat,lon' direto; senao maps_client.localizar (Places Text Search;
    a Geocoding esta bloqueada desde sempre - 07/11) uma vez so por endereco (guardado em `cache`,
    que quem chama grava). Falha fica marcada no dia: tenta de novo amanha, nao a cada visita.
    A casa sem coordenada cai na casa aprendida pelo GPS (casa_pelo_gps)."""
    endereco = lugar["endereco"]
    direto = maps_client.coordenada(endereco)
    if direto:
        return direto
    apelido = lugar["apelido"]
    item = cache.get(apelido)
    if isinstance(item, dict) and item.get("endereco") == endereco:
        if isinstance(item.get("lat"), (int, float)) and isinstance(item.get("lon"), (int, float)):
            return (item["lat"], item["lon"])
        if item.get("falhou") == hoje:
            return _casa_gps(conn, cache, endereco) if apelido == "casa" else None
    if maps_client.configurado():
        try:
            lat, lon = maps_client.localizar(endereco)  # conta a propria cota (lugar_busca / Geocoding)
            cache[apelido] = {"endereco": endereco, "lat": round(float(lat), 5), "lon": round(float(lon), 5)}
            return (cache[apelido]["lat"], cache[apelido]["lon"])
        except Exception:  # rede, endereco nao achado, cota, resposta estranha: so nao reconhece
            cache[apelido] = {"endereco": endereco, "falhou": hoje}
    return _casa_gps(conn, cache, endereco) if apelido == "casa" else None


CASA_NOITES_MIN = 3  # casa pelo GPS: 3+ noites dormindo no mesmo ponto
CASA_MADRUGADA = (time(3, 0), time(5, 0))  # a visita tem que cobrir esse trecho inteiro


def casa_pelo_gps(conn, agora: datetime | None = None) -> tuple[float, float] | None:
    """Casa aprendida pelo GPS (07/11, reserva quando o endereco nao da coordenada): visita que cobre
    03:00-05:00 inteira, em CASA_NOITES_MIN+ noites diferentes, no mesmo ponto (RAIO_M). Devolve a
    media dos pontos do grupo com mais noites, ou None. So le `visitas` (ultimos RETENCAO_DIAS)."""
    agora = agora or datetime.now()
    try:
        linhas = conn.execute(
            "SELECT lat, lon, chegada, saida, lugar FROM visitas WHERE chegada IS NOT NULL AND chegada >= ?",
            (_iso(agora - timedelta(days=RETENCAO_DIAS)),),
        ).fetchall()
    except Exception:  # tabela ainda nao existe (banco velho de teste)
        return None
    pontos = []  # (noite, (lat, lon))
    for r in linhas:
        if r["lugar"] and r["lugar"] != "casa":
            continue  # hotel/obra reconhecidos nao sao casa
        ini = _dt(r["chegada"])
        if not ini:
            continue
        fim = _dt(r["saida"]) or min(agora, ini + timedelta(hours=VISITA_ABERTA_MAX_H))
        noite = ini.date() if ini.time() <= CASA_MADRUGADA[0] else ini.date() + timedelta(days=1)
        while datetime.combine(noite, CASA_MADRUGADA[1]) <= fim:
            if datetime.combine(noite, CASA_MADRUGADA[0]) >= ini:
                pontos.append((noite, (r["lat"], r["lon"])))
            noite += timedelta(days=1)
    melhor: list = []
    melhor_noites = 0
    for _, p in pontos:
        grupo = [(n, q) for n, q in pontos if _metros(p, q) <= RAIO_M]
        noites = len({n for n, _ in grupo})
        if noites >= CASA_NOITES_MIN and noites > melhor_noites:
            melhor, melhor_noites = grupo, noites
    if not melhor:
        return None
    lat = sum(q[0] for _, q in melhor) / len(melhor)
    lon = sum(q[1] for _, q in melhor) / len(melhor)
    return (round(lat, 5), round(lon, 5))


def _casa_gps(conn, cache: dict, endereco: str) -> tuple[float, float] | None:
    c = casa_pelo_gps(conn)
    if c:
        cache["casa"] = {"endereco": endereco, "lat": c[0], "lon": c[1], "origem": "gps"}
    return c


def reconhecer_visitas(conn, lugares: list[dict], agora: datetime | None = None) -> int:
    """Visita gravada com `lugar` NULL (coordenada ainda nao existia) e que agora bate com um lugar:
    preenche (07/11 - pra o dia de hoje ja funcionar quando a coordenada aparece). So as abertas ou
    das ultimas 48 h. Devolve quantas reconheceu. Commita se mudou algo."""
    if not any(x.get("coord") for x in lugares):
        return 0
    agora = agora or datetime.now()
    try:
        linhas = conn.execute(
            "SELECT id, lat, lon, precisao FROM visitas WHERE lugar IS NULL AND "
            "(saida IS NULL OR COALESCE(saida, chegada) >= ?)",
            (_iso(agora - timedelta(hours=48)),),
        ).fetchall()
    except Exception:
        return 0
    n = 0
    for r in linhas:
        lugar = lugar_da_visita(lugares, r["lat"], r["lon"], r["precisao"])
        if lugar:
            conn.execute("UPDATE visitas SET lugar = ? WHERE id = ? AND lugar IS NULL", (lugar["apelido"], r["id"]))
            n += 1
    if n:
        conn.commit()
    return n


def lugares_com_coordenada(conn, hoje: str | None = None) -> list[dict]:
    hoje = hoje or datetime.now().date().isoformat()
    cache = _carregar_coords(conn)
    antes = json.dumps(cache, sort_keys=True)
    saida = []
    for lugar in _lugares(conn, hoje):
        c = _coordenada(conn, lugar, cache, hoje)
        saida.append({**lugar, "coord": c})
    if not any(x["apelido"] == "casa" for x in saida) and not os.environ.get("ENDERECO_CASA", "").strip():
        c = _casa_gps(conn, cache, "")  # sem endereco nenhum: a casa so pelo GPS
        if c:
            saida.append({"apelido": "casa", "endereco": f"{c[0]},{c[1]}", "coord": c})
    if json.dumps(cache, sort_keys=True) != antes:
        db.definir_configuracao(conn, CONFIG_COORDS, json.dumps(cache, ensure_ascii=False))
        reconhecer_visitas(conn, saida)  # coordenada nova: as visitas sem lugar de hoje ganham o lugar
    return saida


def garantir_coordenada(conn, apelido: str) -> bool:
    """Chamado ao salvar um apelido (`salvar_lugar_apelido` do chat): geocodifica ja."""
    lugar = next((x for x in lugares_com_coordenada(conn) if x["apelido"] == apelido), None)
    return bool(lugar and lugar["coord"])


def lugar_da_visita(lugares: list[dict], lat: float, lon: float, precisao: float | None) -> dict | None:
    raio = max(RAIO_M, min(precisao or 0, RAIO_MAX_M))
    perto = [(_metros((lat, lon), x["coord"]), x) for x in lugares if x.get("coord")]
    perto = [p for p in perto if p[0] <= raio]
    return min(perto, key=lambda p: p[0])[1] if perto else None


# ------------------------------------------------------------------ gravar a visita


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") if dt else None


def _dt(txt) -> datetime | None:
    try:
        return datetime.fromisoformat(txt) if txt else None
    except ValueError:
        return None


def registrar(conn, dados: dict, agora: datetime) -> tuple[int, bool]:
    """Grava (ou completa) a visita. Devolve (id, nova). "Saiu" junta com o "chegou" da mesma
    visita (mesma chegada, ponto perto); "chegou" repetido (fila do iPhone mandando de novo)
    nao duplica. Commita."""
    ponto = (dados["lat"], dados["lon"])
    chegada, saida = dados["chegada"], dados["saida"]
    corte = _iso((chegada or saida) - timedelta(days=2))
    recentes = conn.execute(
        "SELECT * FROM visitas WHERE COALESCE(chegada, saida) >= ? ORDER BY id DESC LIMIT 50", (corte,)
    ).fetchall()
    existente = None
    for r in recentes:
        if _metros(ponto, (r["lat"], r["lon"])) > MESMA_VISITA_M:
            continue
        rc = _dt(r["chegada"])
        if chegada and rc and abs((rc - chegada).total_seconds()) <= MESMA_VISITA_S:
            existente = r
            break
        # cerca + visita do mesmo lugar (06/11): a cerca chega antes, a visita do iOS minutos depois - uma so
        if chegada and rc and not r["saida"] and abs((rc - chegada).total_seconds()) <= MESMA_ENTRADA_S:
            if chegada < rc:
                conn.execute("UPDATE visitas SET chegada = ? WHERE id = ?", (_iso(chegada), r["id"]))
                conn.commit()
            existente = r
            break
        # cerca e visita do iOS ja fecharam a mesma estadia (a visita chega atrasada): nao vira outra
        rs = _dt(r["saida"])
        if chegada and rc and rs and abs((rc - chegada).total_seconds()) <= MESMA_ENTRADA_S                 and chegada <= rs + timedelta(minutes=2):
            if chegada < rc:
                conn.execute("UPDATE visitas SET chegada = ? WHERE id = ?", (_iso(chegada), r["id"]))
                conn.commit()
            existente = r
            break
        if not chegada and not r["saida"]:  # "saiu" sem a chegada (o iOS nao sabia): fecha a aberta ali
            existente = r
            break
        # a outra saida (cerca ou visita) do mesmo lugar ja fechou ela: a saida conta uma vez so
        if not chegada and rs and saida and abs((rs - saida).total_seconds()) <= MESMA_ENTRADA_S:
            existente = r
            break
    if existente:
        if saida and not existente["saida"]:
            conn.execute("UPDATE visitas SET saida = ? WHERE id = ?", (_iso(saida), existente["id"]))
            conn.commit()
        elif saida and _dt(existente["saida"]) and saida < _dt(existente["saida"]):  # fica a saida mais cedo
            conn.execute("UPDATE visitas SET saida = ? WHERE id = ?", (_iso(saida), existente["id"]))
            conn.commit()
        return existente["id"], False

    lugares = lugares_com_coordenada(conn, agora.date().isoformat())
    lugar = lugar_da_visita(lugares, *ponto, dados["precisao"])
    if not lugar and dados.get("lugar"):  # a cerca ja diz qual e (so vale apelido conhecido)
        lugar = next((x for x in lugares if x["apelido"] == dados["lugar"]), None)
    if not lugar and dados.get("cerca"):  # ...ou pelo id da cerca que o app vigia
        try:
            from viagem_acompanhada import _id_cerca

            lugar = next((x for x in lugares if _id_cerca(x["apelido"]) == dados["cerca"]), None)
        except Exception:
            lugar = None
    cur = conn.execute(
        "INSERT INTO visitas (lat, lon, precisao, chegada, saida, lugar) VALUES (?, ?, ?, ?, ?, ?)",
        (dados["lat"], dados["lon"], dados["precisao"], _iso(chegada), _iso(saida),
         lugar["apelido"] if lugar else None),
    )
    vid = cur.lastrowid
    if chegada:
        # visita mais velha ainda "aberta": o iOS perdeu a saida - ele saiu de la antes de chegar aqui
        conn.execute(
            "UPDATE visitas SET saida = ? WHERE saida IS NULL AND id != ? AND chegada IS NOT NULL AND chegada < ?",
            (_iso(chegada), vid, _iso(chegada)),
        )
    conn.execute(
        "DELETE FROM visitas WHERE COALESCE(saida, chegada) < ?",
        (_iso(agora - timedelta(days=RETENCAO_DIAS)),),
    )
    conn.commit()
    return vid, True


def visita_atual(conn, agora: datetime):
    """A visita aberta (chegou e nao saiu) de agora, se for recente."""
    return conn.execute(
        "SELECT * FROM visitas WHERE saida IS NULL AND chegada IS NOT NULL AND chegada >= ? AND chegada <= ? "
        "ORDER BY chegada DESC, id DESC LIMIT 1",
        (_iso(agora - timedelta(hours=VISITA_ABERTA_MAX_H)), _iso(agora + timedelta(minutes=10))),
    ).fetchone()


# ------------------------------------------------------------------ texto


def _hora_fala(hhmm: str) -> str:
    h, m = hhmm.split(":")
    return f"{int(h)}h" if m == "00" else f"{int(h)}h{m}"


def _titulo_frase(titulo: str) -> str:
    """'Levar o carro (até 09:00)' -> 'levar o carro' (no meio da frase)."""
    t = _RE_ATE.sub("", titulo or "").strip().rstrip(".")
    if len(t) > 1 and t[0].isupper() and not t[1].isupper():
        t = t[0].lower() + t[1:]
    return t


def _bate(apelido: str, texto: str) -> bool:
    return bool(apelido) and re.search(rf"(?<!\w){re.escape(apelido)}(?!\w)", _sem_acento(texto)) is not None


_MASC = {"no", "do", "ao", "pro", "o", "pelo", "nesse", "neste"}
_FEM = {"na", "da", "a", "pra", "pela", "nessa", "nesta"}


def nome_e_genero(apelido: str, textos: list[str]) -> tuple[str, str]:
    """Nome com acento (achado nos titulos das tarefas, o apelido e guardado sem acento) e o
    genero ('m'/'f'/'casa') pra frase sair "no mecânico" / "na obra" / "em casa"."""
    if apelido == "casa":
        return "casa", "casa"
    alvo = apelido.split()
    for texto in textos:
        palavras = re.findall(r"\w+", texto or "")
        for i in range(len(palavras) - len(alvo) + 1):
            janela = palavras[i:i + len(alvo)]
            if [_sem_acento(p) for p in janela] == alvo:
                antes = _sem_acento(palavras[i - 1]) if i else ""
                genero = "f" if antes in _FEM else "m" if antes in _MASC else ("f" if apelido.endswith("a") else "m")
                return " ".join(p.lower() for p in janela), genero
    return apelido, "f" if apelido.endswith("a") else "m"


def _em(nome: str, genero: str) -> str:
    return {"casa": "em casa", "f": f"na {nome}"}.get(genero, f"no {nome}")


def _de(nome: str, genero: str) -> str:
    return {"casa": "de casa", "f": f"da {nome}"}.get(genero, f"do {nome}")


# ------------------------------------------------------------------ tarefas


def _tarefas_de_hoje(conn, dia: str):
    return conn.execute(
        "SELECT id, title, hora, local, COALESCE(inegociavel, 0) AS inegociavel, "
        "COALESCE(sai_na_hora, 0) AS sai_na_hora, recorrente_origem_id FROM tasks "
        "WHERE completed_at IS NULL AND recorrencia IS NULL AND due_date = ? "
        "ORDER BY (hora IS NULL OR hora = ''), hora, id",
        (dia,),
    ).fetchall()


def tarefas_do_lugar(tarefas, lugar: dict) -> list:
    endereco = _sem_acento(lugar["endereco"])
    return [
        t for t in tarefas
        if _bate(lugar["apelido"], t["title"]) or _bate(lugar["apelido"], t["local"] or "")
        or (t["local"] and _sem_acento(t["local"]) == endereco)
    ]


def _com_hora(t) -> bool:
    return bool(t["hora"]) and re.fullmatch(r"\d{2}:\d{2}", t["hora"] or "") is not None


def mensagem_chegada(conn, visita, agora: datetime) -> tuple[str, str, str] | None:
    """(texto do chat, titulo do push, corpo do push) ou None (nada util pra dizer)."""
    lugares = {x["apelido"]: x for x in _lugares(conn, agora.date().isoformat())}
    lugar = lugares.get(visita["lugar"])
    if not lugar:
        return None
    tarefas = _tarefas_de_hoje(conn, agora.date().isoformat())
    do_lugar = tarefas_do_lugar(tarefas, lugar)
    ids = {t["id"] for t in do_lugar}
    agora_hm = agora.strftime("%H:%M")
    proxima = next((t for t in tarefas if t["id"] not in ids and _com_hora(t) and t["hora"] > agora_hm), None)
    if not do_lugar and not proxima:
        return None
    nome, genero = nome_e_genero(lugar["apelido"], [t["title"] for t in tarefas] + [t["local"] or "" for t in tarefas])
    titulo = f"Chegou {_em(nome, genero)}"
    partes = []
    if do_lugar:
        partes.append(f"Agora é: {_titulo_frase(do_lugar[0]['title'])}.")
    if proxima:
        rotulo = "Depois" if do_lugar else "Próxima"
        partes.append(f"{rotulo}: {_titulo_frase(proxima['title'])} às {_hora_fala(proxima['hora'])}.")
    corpo = " ".join(partes)
    return f"{titulo}. {corpo}", titulo, corpo


# ------------------------------------------- chegada num compromisso de sair (04/11)
# Passo 5 do assistente passo a passo (tempo.py): "Chegou na casa do guri. Saindo 18:48 tu chega 19:00."
# ou "Chegou na Viva Beach." Um de cada por compromisso por dia (notificacoes_enviadas) + o da visita.
TIPO_CHEGOU_PARADA = "saida_parada"
TIPO_CHEGOU_DESTINO = "saida_chegou"
PARADA_ANTES_MAX_H = 4
DESTINO_JANELA_H = 2
_ARTIGO = {"o": "m", "a": "f", "no": "m", "na": "f", "do": "m", "da": "f", "pro": "m", "pra": "f"}


def _saidas_de_hoje(conn, dia: str) -> list[dict]:
    """Compromissos de sair de hoje (date/balada/festa... ou com parada) que tem parada ou lugar."""
    try:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL AND due_date = ? "
            "AND hora IS NOT NULL ORDER BY hora, id", (dia,),
        ).fetchall()
    except Exception:  # banco velho de teste
        return []
    saida = []
    for r in rows:
        parada = (r["parada"] if "parada" in r.keys() else None) or ""
        local = r["local"] or ""
        sair = parada.strip() or r["estilo"] in ("date", "balada") or notificacoes.e_compromisso_de_sair(r["title"])
        if sair and (parada.strip() or local.strip()) and _com_hora(r):
            saida.append({"id": r["id"], "title": r["title"], "hora": r["hora"], "local": local.strip() or None,
                          "parada": parada.strip() or None, "source_text": r["source_text"] or ""})
    return saida


def _em_texto(texto: str, contexto=()) -> str:
    """'casa do guri' -> 'na casa do guri'; 'Viva Beach' -> 'na Viva Beach' ("a Viva Beach" no que ele
    disse); artigo dito na frente ganha. Maiuscula so de comeco de frase cai."""
    palavras = (texto or "").split()
    if not palavras:
        return ""
    genero = None
    if len(palavras) > 1 and _sem_acento(palavras[0]) in _ARTIGO:
        genero = _ARTIGO[_sem_acento(palavras[0])]
        palavras = palavras[1:]
    nome = " ".join(palavras)
    if genero is None:
        alvo = re.escape(_sem_acento(nome))
        for c in contexto:
            m = re.search(rf"(?<!\w)(\w+)\s+{alvo}(?!\w)", _sem_acento(c or ""))
            if m and m.group(1) in _ARTIGO:
                genero = _ARTIGO[m.group(1)]
                break
    if genero is None:
        genero = "f" if _sem_acento(palavras[0]).endswith("a") else "m"
    if len(palavras) > 1 and palavras[0][:1].isupper() and all(p.islower() for p in palavras[1:]):
        nome = nome[:1].lower() + nome[1:]
    return _em(nome, genero)


def _e_o_lugar(conn, visita_lugar: str, lugar: dict | None, texto: str | None, parada: bool) -> bool:
    if not texto:
        return False
    chaves = {vida_assistente._chave_apelido(texto)}
    if parada:
        chaves.add(vida_assistente.apelido_dentro(conn, texto))
    if visita_lugar in chaves:
        return True
    resolvido = vida_assistente.resolver_parada(conn, texto) if parada else vida_assistente.resolver_lugar(conn, texto)
    return bool(lugar) and _sem_acento(lugar["endereco"]) == _sem_acento(resolvido)


def mensagem_chegada_saida(conn, visita, agora: datetime) -> tuple[str, str, str, str, int] | None:
    """(texto do chat, titulo, corpo, tipo, id da tarefa) quando a visita e a parada ou o destino de um
    compromisso de sair de hoje; None se nao e (cai no "chegou" normal)."""
    if not visita["lugar"]:
        return None
    import tempo

    dia = agora.date().isoformat()
    lugar = next((x for x in _lugares(conn, dia) if x["apelido"] == visita["lugar"]), None)
    for t in _saidas_de_hoje(conn, dia):
        ev = datetime.combine(agora.date(), time(*map(int, t["hora"].split(":"))))
        contexto = [t["title"], t["source_text"]]
        if (t["parada"] and agora < ev <= agora + timedelta(hours=PARADA_ANTES_MAX_H)
                and _e_o_lugar(conn, visita["lugar"], lugar, t["parada"], True)
                and not db.ja_notificou_hoje(conn, TIPO_CHEGOU_PARADA, t["id"])):
            destino = vida_assistente.resolver_lugar(conn, t["local"]) if t["local"] else None
            resto = _trajeto_min((visita["lat"], visita["lon"]), destino) if destino else 0
            resto = resto or tempo.FOLGA_MIN
            saindo = max(ev - timedelta(minutes=resto),
                         agora + timedelta(minutes=notificacoes.PARADA_MIN)).replace(second=0, microsecond=0)
            titulo = f"Chegou {_em_texto(t['parada'], contexto)}"
            corpo = f"Saindo {saindo:%H:%M} tu chega {saindo + timedelta(minutes=resto):%H:%M}."
            return f"{titulo}. {corpo}", titulo, corpo, TIPO_CHEGOU_PARADA, t["id"]
        if (t["local"] and ev - timedelta(hours=DESTINO_JANELA_H) <= agora <= ev + timedelta(hours=DESTINO_JANELA_H)
                and _e_o_lugar(conn, visita["lugar"], lugar, t["local"], False)
                and not db.ja_notificou_hoje(conn, TIPO_CHEGOU_DESTINO, t["id"])):
            titulo = f"Chegou {_em_texto(t['local'], contexto)}"
            dif = round((agora - ev).total_seconds() / 60)
            hora = _hora_fala(t["hora"])
            corpo = ("Bem na hora." if abs(dif) <= 2 else
                     f"{-dif} min antes das {hora}." if dif < 0 else f"{dif} min depois das {hora}.")
            return f"{titulo}.", titulo, corpo, TIPO_CHEGOU_DESTINO, t["id"]
    return None


# ------------------------------------------------------------------ atraso


def _destino(tarefa, lugares: list[dict]) -> tuple[str | None, tuple | None]:
    """Onde a tarefa acontece: o `local` dela; senao um apelido no titulo; senao (None, None).
    07/11: tarefa sem lugar NAO e "em casa" - nao tem destino (o atraso das 7h43 empurrou remedio e
    4 tarefas soltas porque contava casa como destino)."""
    local = (tarefa["local"] or "").strip()
    if local:
        lugar = next((x for x in lugares if _sem_acento(x["endereco"]) == _sem_acento(local)
                      or x["apelido"] == vida_assistente._chave_apelido(local)), None)
        return local, (lugar["coord"] if lugar else maps_client.coordenada(local))
    for x in lugares:
        if x["apelido"] != "casa" and _bate(x["apelido"], tarefa["title"]):
            return x["endereco"], x["coord"]
    return None, None


_RE_REMEDIO = re.compile(r"\b(remedio|remedios|medicamento|medicamentos|vitamina|comprimido|dose)\b")


def _e_remedio(conn, t) -> bool:
    """Remedio nunca e empurrado pelo atraso (07/11): a dose do medicamento cadastrado (instancia da
    tarefa recorrente "Tomar X", a mesma fonte do botao Tomei - db.instancia_do_dia_do_medicamento)
    ou titulo que fala de remedio."""
    if _RE_REMEDIO.search(_sem_acento(t["title"])):
        return True
    origem = t["recorrente_origem_id"] if "recorrente_origem_id" in t.keys() else None
    if not origem:
        return False
    try:
        return conn.execute("SELECT 1 FROM medicamentos WHERE tarefa_modelo_id = ?", (origem,)).fetchone() is not None
    except Exception:
        return False


def _trajeto_min(origem: tuple[float, float], destino: str | None) -> int:
    """Minutos de carro com transito, com cache de 20 min. Sem Maps/sem cota/rede: 0."""
    if not destino or not maps_client.configurado():
        return 0
    chave = (f"{origem[0]:.3f},{origem[1]:.3f}", destino)
    agora = _time.time()
    hit = _cache_trajeto.get(chave)
    if hit and agora - hit[0] < TRAJETO_CACHE_S:
        return hit[1]
    try:
        minutos = int(maps_client.tempo_de_viagem(f"{origem[0]},{origem[1]}", destino)["duracao_minutos"])
    except Exception:
        minutos = 0
    _cache_trajeto[chave] = (agora, max(0, minutos))
    return max(0, minutos)


def _fixa(t) -> bool:
    return bool(t["inegociavel"]) or _RE_VOO.search(_sem_acento(t["title"])) is not None


def _somar(hhmm: str, minutos: int) -> str | None:
    h, m = map(int, hhmm.split(":"))
    total = h * 60 + m + minutos
    return None if total >= 24 * 60 else f"{total // 60:02d}:{total % 60:02d}"


def _titulo_empurrado(titulo: str, minutos: int) -> str:
    """'(até 11:30)' no titulo anda junto com a hora."""
    def troca(m):
        novo = _somar(f"{int(m.group(2)):02d}:{m.group(3)}", minutos)
        return f"({m.group(1)} {novo})" if novo else m.group(0)
    return _RE_ATE.sub(troca, titulo)


def checar_atraso(conn, agora: datetime, visita) -> dict | None:
    """Empurra a proxima tarefa com hora (e as seguintes de hoje) se ele nao chega a tempo
    saindo de onde a visita diz. Devolve {"texto", "titulo", "corpo", "card"} ou None."""
    if not visita:
        return None
    hoje = agora.date().isoformat()
    tarefas = _tarefas_de_hoje(conn, hoje)
    lugares = lugares_com_coordenada(conn, hoje)
    apelido_visita = visita["lugar"]
    if not apelido_visita:  # gravada antes da coordenada existir: reconhece agora (07/11)
        achado = lugar_da_visita(lugares, visita["lat"], visita["lon"], visita["precisao"])
        if achado:
            apelido_visita = achado["apelido"]
            conn.execute("UPDATE visitas SET lugar = ? WHERE id = ? AND lugar IS NULL", (apelido_visita, visita["id"]))
            conn.commit()
    lugar_atual = next((x for x in lugares if x["apelido"] == apelido_visita), None)
    casa = next((x for x in lugares if x["apelido"] == "casa"), None)
    if not lugar_atual and not (casa and casa.get("coord")):
        return None  # 07/11 (d): nao sabe onde ele esta nem onde e casa - sem base, nao chuta
    ids_do_lugar = {t["id"] for t in tarefas_do_lugar(tarefas, lugar_atual)} if lugar_atual else set()
    minimo = (agora - timedelta(minutes=TAREFA_VELHA_MIN)).strftime("%H:%M")
    com_hora = [t for t in tarefas if _com_hora(t)]
    destinos = {}

    def empurravel(t) -> bool:
        """07/11 (a)(b): so tarefa com destino real (local ou apelido no titulo) e nunca remedio."""
        if t["id"] not in destinos:
            destinos[t["id"]] = None if _e_remedio(conn, t) else _destino(t, lugares)
        return bool(destinos[t["id"]] and destinos[t["id"]][0])

    alvo = None
    for t in com_hora:
        if t["hora"] < minimo or t["id"] in ids_do_lugar or db.ja_notificou_hoje(conn, TIPO_ATRASO, t["id"]):
            continue
        if _fixa(t):
            return None  # a proxima e inegociavel/voo: nao mexe nela nem no que vem depois
        if not empurravel(t):
            continue
        alvo = t
        break
    if not alvo:
        return None
    hora_alvo = datetime.combine(agora.date(), time(*map(int, alvo["hora"].split(":"))))
    if (hora_alvo - agora).total_seconds() / 60 > JANELA_TRAJETO_MIN:
        return None
    origem = (visita["lat"], visita["lon"])
    destino, coord_destino = destinos[alvo["id"]]
    if coord_destino and _metros(origem, coord_destino) <= RAIO_M:
        return None  # ja esta onde a tarefa acontece
    if alvo["sai_na_hora"]:
        # 07/11 (c): a hora e a de SAIR (app._saida_na_hora). Atrasado so se ainda nao saiu e agora + 5 min
        # ja passa da hora de sair - sem trajeto (nao gasta cota). Saiu (visita fechada) = esta indo.
        if visita["saida"]:
            return None
        atraso = (agora + timedelta(minutes=ARREDONDA_MIN) - hora_alvo).total_seconds() / 60
        if atraso <= 0:
            return None
    else:
        trajeto = _trajeto_min(origem, destino)
        atraso = (agora + timedelta(minutes=trajeto) - hora_alvo).total_seconds() / 60
        if atraso <= ATRASO_MIN:
            return None
    delta = int(math.ceil(atraso / ARREDONDA_MIN) * ARREDONDA_MIN)

    efeitos = []
    for t in com_hora:
        if t["hora"] < alvo["hora"] or t["id"] in ids_do_lugar:
            continue
        if _fixa(t):
            break
        if db.ja_notificou_hoje(conn, TIPO_ATRASO, t["id"]) or not empurravel(t):
            continue
        nova = _somar(t["hora"], delta)
        if not nova:
            break  # passaria da meia-noite: deixa como esta
        novos = {"hora": nova}
        titulo_novo = _titulo_empurrado(t["title"], delta)
        if titulo_novo != t["title"]:
            novos["title"] = titulo_novo
        antes = {"hora": t["hora"], **({"title": t["title"]} if "title" in novos else {})}
        conn.execute(f"UPDATE tasks SET {', '.join(c + ' = ?' for c in novos)} WHERE id = ?", [*novos.values(), t["id"]])
        efeitos.append({"entidade": "edicao", "tabela": "tasks", "id": t["id"], "rotulo": "Tarefa",
                        "titulo": t["title"], "antes": antes, "depois": novos})
    if not efeitos:
        return None
    conn.commit()
    for ef in efeitos:
        db.marcar_notificado(conn, TIPO_ATRASO, ef["id"])
    token = db.criar_acao_desfazer(conn, efeitos)
    card = cards.card_edicao(efeitos, [cards.acao_desfazer(token, efeitos)] if token else [])

    primeira = efeitos[0]
    nome_alvo = _titulo_frase(alvo["title"])
    hora_nova = _hora_fala(primeira["depois"]["hora"])
    if lugar_atual:
        nome, genero = nome_e_genero(lugar_atual["apelido"], [t["title"] for t in tarefas])
        titulo = f"Atrasou {_em(nome, genero)}"
    else:
        titulo = "Tá atrasado"
    corpo = f"Empurrei {nome_alvo} pras {hora_nova}"
    if len(efeitos) > 1:
        corpo += f" (e mais {len(efeitos) - 1} depois)" if len(efeitos) > 2 else " (e a seguinte também)"
    corpo += "."
    texto = f"{titulo}: {corpo[0].lower()}{corpo[1:]}"
    # tarefa_id/atraso_min/hora_original: pro recado pronto (onde_vou.recado_parado, 06/11)
    return {"texto": texto, "titulo": titulo, "corpo": corpo, "card": card,
            "tarefa_id": alvo["id"], "atraso_min": int(round(atraso)), "hora_original": alvo["hora"]}


# ------------------------------------------------------------------ chat + push


def _publicar(conn, texto: str, lista_cards: list[dict]) -> None:
    env = cards.envelope([c for c in lista_cards if c], texto, [])
    db.salvar_mensagem_chat(conn, "assistant", texto, env["cards"])


def _avisar(conn, tipo: str, ref: int, titulo: str, corpo: str, agora: datetime) -> bool:
    """Push + Telegram, pelo mesmo caminho dos outros avisos (push_client/telegram_bot). Respeita
    o liga/desliga do tipo e o horario silencioso (o chat recebe de qualquer jeito)."""
    try:
        import push_client
        import telegram_bot
        from assistente import avisos as avisos_assistente

        if not avisos_assistente.esta_ligado(tipo, conn=conn):
            return False
        if notificacoes.dentro_do_horario_silencioso(
            agora, db.obter_configuracao(conn, "silencio_inicio") or "22:00",
            db.obter_configuracao(conn, "silencio_fim") or "07:00",
        ):
            return False
        enviou = False

        def _push():
            nonlocal enviou
            for s in db.list_push_subscriptions(conn):
                ok = push_client.enviar(json.loads(s["subscription_json"]), titulo, corpo, url=URL_CHAT,
                                        tag=f"{tipo}-{ref}")
                if ok:
                    enviou = True
                else:
                    db.delete_push_subscription(conn, s["endpoint"])

        if push_client.configurado():
            # frente C (07/11): app do iPhone vivo -> fila dele (aviso local); o navegador so se ele nao pegar
            import avisos_pendentes

            if avisos_pendentes.entregar(conn, tipo=tipo, ref=ref, titulo=titulo, corpo=corpo, agora=agora,
                                         enviar_push=_push, url=URL_CHAT) == "fila":
                enviou = True
        if telegram_bot.configurado():
            telegram_bot.enviar_mensagem(f"{titulo}\n{corpo}")
            enviou = True
        return enviou
    except Exception:
        log.exception("onde_estou: aviso falhou")
        return False


def reagir(conn, visita_id: int, agora: datetime) -> list[str]:
    """Depois de gravar uma visita (e a cada 5 min pela visita aberta): mensagem de chegada
    (uma por visita) e o atraso. Devolve o que fez (pra teste/log)."""
    feito = []
    v = conn.execute("SELECT * FROM visitas WHERE id = ?", (visita_id,)).fetchone()
    if not v:
        return feito
    chegada, saida = _dt(v["chegada"]), _dt(v["saida"])
    recente = chegada and timedelta(0) <= agora - chegada <= timedelta(minutes=CHEGADA_RECENTE_MIN)
    if not v["lugar"] and saida is None:  # 07/11: a coordenada pode ter aparecido depois de gravar
        reconhecer_visitas(conn, lugares_com_coordenada(conn, agora.date().isoformat()), agora)
        v = conn.execute("SELECT * FROM visitas WHERE id = ?", (visita_id,)).fetchone()
    if not v["avisou_chegada"] and saida is None and recente and v["lugar"]:
        # trava antes de mandar: dois POSTs iguais ao mesmo tempo nao avisam duas vezes
        if conn.execute("UPDATE visitas SET avisou_chegada = 1 WHERE id = ? AND avisou_chegada = 0",
                        (visita_id,)).rowcount == 1:
            conn.commit()
            msg_saida = mensagem_chegada_saida(conn, v, agora)
            msg = None if msg_saida else mensagem_chegada(conn, v, agora)
            if msg_saida:
                texto, titulo, corpo, tipo, ref = msg_saida
                db.marcar_notificado(conn, tipo, ref)
                _publicar(conn, texto, [])
                _avisar(conn, tipo, ref, titulo, corpo, agora)
                feito.append("chegada_saida")
            elif msg:
                _publicar(conn, msg[0], [])
                _avisar(conn, TIPO_CHEGADA, visita_id, msg[1], msg[2], agora)
                feito.append("chegada")
    if recente and saida is None and v["lugar"] == "casa":
        # leva 07/11 (2): voltou pra casa depois de >= 30 min fora com tarefa de fora aberta -> "marca o que fez"
        try:
            import avisos_novos

            if avisos_novos.chegou_casa(conn, visita_id, agora):
                feito.append("chegou_casa")
        except Exception:
            log.exception("onde_estou: chegou_casa falhou")
    if recente and saida is None:
        feito += _onde_vou("na_chegada", conn, v, agora)  # fecha o trajeto "indo pra" e aprende o tempo (06/11)
    aberta = saida is None and chegada and agora - chegada <= timedelta(hours=VISITA_ABERTA_MAX_H)
    saiu_agora = saida is not None and timedelta(0) <= agora - saida <= timedelta(minutes=SAIDA_RECENTE_MIN)
    if saiu_agora:
        feito += _onde_vou("na_saida", conn, v, agora)  # "Indo pro X?" (06/11) - antes do atraso de parado
    if aberta or saiu_agora:
        r = checar_atraso(conn, agora, v)
        if r:
            # 07/11: atraso + recado pronto numa mensagem so (o card do recado vai junto do card do empurrao)
            extras = []
            recado = bool(aberta and _onde_vou("recado_parado", conn, r, agora, extras))
            texto = r["texto"] + (" Deixei o recado pronto, quem manda é tu." if extras else "")
            _publicar(conn, texto, [r["card"], *extras])
            _avisar(conn, TIPO_ATRASO, visita_id, r["titulo"], r["corpo"], agora)
            feito.append("atraso")
            if recado:
                feito.append("recado")
    return feito


def _onde_vou(nome: str, *args):
    """onde_vou.py (06/11) isolado: uma falha la nunca derruba a chegada/atraso daqui."""
    try:
        import onde_vou

        return getattr(onde_vou, nome)(*args)
    except Exception:
        log.exception("onde_estou: onde_vou.%s falhou", nome)
        return [] if nome != "recado_parado" else False


def reagir_depois(visita_id: int) -> None:
    """A rota responde ja (o iOS da poucos segundos em segundo plano); a reacao (Maps, push,
    Telegram) roda numa thread com conexao propria."""
    def rodar():
        conn = db.get_db()
        try:
            reagir(conn, visita_id, datetime.now())
        except Exception:
            log.exception("onde_estou: reacao a visita %s falhou", visita_id)
        finally:
            conn.close()

    if REAGIR_EM_THREAD:
        threading.Thread(target=rodar, daemon=True, name="onde-estou").start()
    else:
        rodar()


def verificar(conn, agora: datetime) -> list:
    """Passo de 5 em 5 min (conversa_proativa.verificar): parado num lugar e ficando atrasado.
    Publica e avisa por conta propria (o push dos avisos_conversa so sai 1x por tipo por dia)."""
    v = visita_atual(conn, agora)
    if v:
        reagir(conn, v["id"], agora)
    _onde_vou("verificar", conn, agora)  # card "Sai as X" na hora de se arrumar, quando o jeito dele mudou (06/11)
    return []


# ------------------------------------------------------------------ contexto do chat


def linha_contexto(conn, agora: datetime) -> str | None:
    """"Agora (pelo iPhone): no mecânico desde 07:20" / "saiu de casa às 07:05" (ate 2 h)."""
    try:
        v = visita_atual(conn, agora)
        if not v:
            v = conn.execute(
                "SELECT * FROM visitas WHERE saida IS NOT NULL AND saida <= ? AND saida >= ? "
                "ORDER BY saida DESC, id DESC LIMIT 1",
                (_iso(agora + timedelta(minutes=10)), _iso(agora - timedelta(hours=SAIU_RECENTE_H))),
            ).fetchone()
    except Exception:  # tabela ainda nao existe (banco velho de teste)
        return None
    if not v:
        return None
    titulos = [r["title"] for r in _tarefas_de_hoje(conn, agora.date().isoformat())]
    if v["lugar"]:
        nome, genero = nome_e_genero(v["lugar"], titulos)
    else:
        nome, genero = None, None

    def quando(dt: datetime) -> str:
        if dt.date() == agora.date():
            return f"{dt:%H:%M}"
        if dt.date() == agora.date() - timedelta(days=1):
            return f"ontem {dt:%H:%M}"
        return f"{dt:%d/%m %H:%M}"

    if v["saida"] is None:
        onde = _em(nome, genero) if nome else "parado num lugar sem apelido salvo"
        return f"Agora (pelo iPhone): {onde} desde {quando(_dt(v['chegada']))}"
    de = _de(nome, genero) if nome else "de um lugar sem apelido salvo"
    saida = _dt(v["saida"])
    return f"Agora (pelo iPhone): saiu {de} às {quando(saida)}"
