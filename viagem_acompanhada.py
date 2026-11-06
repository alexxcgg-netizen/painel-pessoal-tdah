"""GPS mais esperto do iPhone (leva 06/11 "painel mais esperto", frente 3 -
docs/briefings/2026-11-06-painel-esperto.md): cercas nos lugares, viagem acompanhada e o ao vivo da viagem.

Tres pecas, todas sem Flask (testaveis com relogio injetado):

  - `cercas(conn, agora)`: ate 20 lugares pro iPhone vigiar com CLCircularRegion (casa, os lugares das saidas
    de hoje e de amanha cedo, apelidos salvos mais visitados). Entrou/saiu vira visita normal
    (POST /api/localizacao/visita com `fonte: "cerca"`).
  - `acompanhamento(conn, agora)` + `guardar_posicao(...)`: a posicao do carro so e guardada enquanto ha
    viagem planejada em andamento (`viagem_planejada.plano_ativo`) ou um compromisso de saida no ao vivo
    (da hora de sair ate chegar). Fora disso o painel recusa e apaga. A viagem acabou (encerrada, chegou
    perto do destino, ou outro plano) -> as posicoes daquela viagem somem. Nunca fica o caminho guardado.
  - `ao_vivo(conn, agora)`: o kind `viagem` do /api/ao-vivo (destino, km que faltam, chegada refeita pela
    posicao, proximo posto, chuva a frente).

`viagem_planejada` e de outra frente (contrato: `plano_ativo(conn, agora) -> dict | None` e `encerrar(conn, id)`).
Sem o modulo = sem viagem (o resto segue igual).
"""

from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime, timedelta

# ------------------------------------------------------------------ regras
MAX_CERCAS = 20  # limite do iOS por app (CLLocationManager)
RAIO_CERCA_M = 150  # o mesmo "esta no lugar" das visitas (onde_estou.RAIO_M)
CERCA_DUPLICADA_M = 100  # dois lugares mais perto que isso viram uma cerca so
AMANHA_CEDO_ATE = "10:00"  # compromisso de amanha antes disso ja ganha cerca hoje a noite

POSICAO_RECENTE_MIN = 20  # "esta dirigindo": teve posicao nos ultimos 20 min
PARADO_DEPOIS_MIN = 10  # posicao mais velha que isso: ele parou (posto, almoco) e o relogio corre
SAIDA_ANTES_MIN = 15  # o ao vivo da viagem aparece 15 min antes da saida planejada
SAIDA_DEPOIS_MIN = 45  # e sem nenhuma posicao fica ate 45 min depois dela
ACOMPANHAR_ANTES_MIN = 30  # posicao aceita a partir de 30 min antes da saida planejada
ACOMPANHAR_DEPOIS_H = 6  # e no maximo 6 h depois da chegada planejada (seguranca: plano esquecido aberto)
DEPOIS_DA_CHEGADA_MIN = 30  # com posicao, fica ate 30 min depois da chegada refeita
CHEGOU_KM = 1.5  # posicao a menos disso do destino (ou faltando menos disso): chegou
GUARDAR_MAX_H = 24  # trava dura: nenhuma posicao vive mais que isso, aconteca o que acontecer
CASAS_COORD = 4  # ~11 m (igual as visitas)

CONFIG_CHEGOU = "viagem_gps_chegou"  # chave da viagem que ja chegou (nao volta a acompanhar)

# tipos de viagem_planejada._CHUVOSOS -> rotulo do quadrinho; os de agua dizem "chovendo" dentro do trecho
ROTULOS_TEMPO = {"chuva": "Chuva", "chuva_forte": "Chuva forte", "trovoada": "Trovoada", "granizo": "Granizo",
                 "neblina": "Neblina", "vento": "Vento"}
CHOVE = {"chuva", "chuva_forte", "trovoada", "granizo"}

COR_VIAGEM = "#8fd0ff"  # --viagem do prototipo
ICONE_VIAGEM = "car.fill"


# ------------------------------------------------------------------ utilidades
def _plano_ativo(conn, agora: datetime) -> dict | None:
    try:
        import viagem_planejada
    except ImportError:
        return None
    try:
        plano = viagem_planejada.plano_ativo(conn, agora)
    except Exception:
        return None
    return plano if isinstance(plano, dict) and plano.get("id") is not None else None


def _encerrar(conn, viagem_id) -> None:
    try:
        import viagem_planejada

        viagem_planejada.encerrar(conn, viagem_id)
    except Exception:
        pass


def _dt(valor) -> datetime | None:
    """ISO (com ou sem fuso) -> hora local sem fuso (o relogio do servidor)."""
    if isinstance(valor, datetime):
        dt = valor
    else:
        try:
            dt = datetime.fromisoformat(str(valor or "").strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt.replace(microsecond=0)


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).astimezone().isoformat(timespec="seconds")


def _num(valor) -> float | None:
    if isinstance(valor, bool):
        return None
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def _km_entre(a, b) -> float:
    """Distancia em km (haversine) entre (lat, lng)."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(min(1.0, math.sqrt(h)))


def _chave_viagem(plano: dict) -> str:
    return f"viagem-{plano['id']}"


# ------------------------------------------------------------------ cercas
def _id_cerca(apelido: str) -> str:
    if apelido == "casa":
        return "casa"
    return "c" + hashlib.sha1(apelido.encode("utf-8")).hexdigest()[:10]


def _nome_cerca(conn, lugar: dict, eh_apelido: bool) -> str:
    if lugar["apelido"] == "casa":
        return "Casa"
    if eh_apelido:
        a = lugar["apelido"]
        return (a[:1].upper() + a[1:])[:40]
    try:
        from rotas.ao_vivo import apelido_do_lugar

        return apelido_do_lugar(conn, lugar.get("endereco")) or "Lugar"
    except Exception:
        return "Lugar"


def _visitas_por_lugar(conn) -> dict[str, int]:
    try:
        return {r["lugar"]: r["n"] for r in conn.execute(
            "SELECT lugar, COUNT(*) AS n FROM visitas WHERE lugar IS NOT NULL GROUP BY lugar")}
    except Exception:
        return {}


def cercas(conn, agora: datetime) -> list[dict]:
    """Ate MAX_CERCAS `{id, nome, lat, lng, raio_m}`, na ordem de importancia: casa, lugares das saidas de
    hoje, de amanha cedo, apelidos salvos (os mais visitados primeiro). So o que ja tem coordenada."""
    import onde_estou
    import vida_assistente

    hoje = agora.date().isoformat()
    try:
        lugares = onde_estou.lugares_com_coordenada(conn, hoje)
    except Exception:
        lugares = []
    salvos = set(vida_assistente.apelidos(conn))

    # amanha cedo: so os lugares dos compromissos de sair antes das 10h (o resto entra amanha)
    amanha_cedo: list[dict] = []
    try:
        amanha = (agora.date() + timedelta(days=1)).isoformat()
        cedo = [s for s in onde_estou._saidas_de_hoje(conn, amanha) if (s.get("hora") or "99") < AMANHA_CEDO_ATE]
        if cedo:
            chaves = {vida_assistente._chave_apelido(t) for s in cedo for t in (s.get("local"), s.get("parada")) if t}
            amanha_cedo = [x for x in onde_estou.lugares_com_coordenada(conn, amanha) if x["apelido"] in chaves]
    except Exception:
        amanha_cedo = []

    visitas = _visitas_por_lugar(conn)
    casa = [x for x in lugares if x["apelido"] == "casa"]
    do_dia = [x for x in lugares if x["apelido"] != "casa" and x["apelido"] not in salvos]
    apelidos = sorted((x for x in lugares if x["apelido"] in salvos and x["apelido"] != "casa"),
                      key=lambda x: (-visitas.get(x["apelido"], 0), x["apelido"]))
    ordem = casa + do_dia + amanha_cedo + apelidos

    saida: list[dict] = []
    vistos: set[str] = set()
    for lugar in ordem:
        coord = lugar.get("coord")
        if not coord or lugar["apelido"] in vistos:
            continue
        lat, lng = _num(coord[0]), _num(coord[1])
        if lat is None or lng is None or not (-90 <= lat <= 90 and -180 <= lng <= 180):
            continue
        if any(_km_entre((lat, lng), (c["lat"], c["lng"])) * 1000 < CERCA_DUPLICADA_M for c in saida):
            continue
        vistos.add(lugar["apelido"])
        saida.append({
            "id": _id_cerca(lugar["apelido"]),
            "nome": _nome_cerca(conn, lugar, lugar["apelido"] in salvos),
            "lat": round(lat, 5),
            "lng": round(lng, 5),
            "raio_m": RAIO_CERCA_M,
        })
        if len(saida) >= MAX_CERCAS:
            break
    return saida


# ------------------------------------------------------------------ viagem: relogio planejado por km
def _pontos(plano: dict) -> list[tuple[float, float, float]]:
    saida = []
    for p in plano.get("pontos_km") or []:
        if not isinstance(p, (list, tuple)) or len(p) < 3:
            continue
        lat, lng, km = _num(p[0]), _num(p[1]), _num(p[2])
        if lat is None or lng is None or km is None:
            continue
        saida.append((lat, lng, km))
    saida.sort(key=lambda x: x[2])
    return saida


def _total_km(plano: dict, pontos) -> float:
    total = _num(plano.get("total_km"))
    if total and total > 0:
        return total
    return pontos[-1][2] if pontos else 0.0


def _ancoras(plano: dict, total: float) -> list[tuple[float, datetime]]:
    """(km, hora planejada) crescentes: saida, cada posto e a chegada. Base pra hora em qualquer km."""
    saida, chegada = _dt(plano.get("saida_em")), _dt(plano.get("chegada_em"))
    if not saida or not chegada or chegada <= saida or total <= 0:
        return []
    meio = []
    for p in plano.get("postos") or []:
        if not isinstance(p, dict):
            continue
        km, em = _num(p.get("km")), _dt(p.get("passa_em"))
        if km is not None and em is not None and 0 < km < total and saida < em < chegada:
            meio.append((km, em))
    meio.sort()
    ancoras = [(0.0, saida)]
    for km, em in meio:
        if km > ancoras[-1][0] and em > ancoras[-1][1]:
            ancoras.append((km, em))
    ancoras.append((total, chegada))
    return ancoras


def _hora_no_km(ancoras, km: float) -> datetime:
    km = min(max(km, ancoras[0][0]), ancoras[-1][0])
    for (k0, t0), (k1, t1) in zip(ancoras, ancoras[1:]):
        if k0 <= km <= k1:
            f = (km - k0) / (k1 - k0) if k1 > k0 else 0
            return t0 + (t1 - t0) * f
    return ancoras[-1][1]


def _km_na_hora(ancoras, quando: datetime) -> float:
    if quando <= ancoras[0][1]:
        return 0.0
    for (k0, t0), (k1, t1) in zip(ancoras, ancoras[1:]):
        if t0 <= quando <= t1:
            f = (quando - t0) / (t1 - t0) if t1 > t0 else 0
            return k0 + (k1 - k0) * f
    return ancoras[-1][0]


def projetar_km(pontos, lat: float, lng: float) -> tuple[float, float] | None:
    """(km acumulado do ponto da rota mais perto, distancia ate a rota em km). Projecao plana local
    (erro desprezivel no tamanho de um trecho entre dois pontos)."""
    if not pontos:
        return None
    if len(pontos) == 1:
        return pontos[0][2], _km_entre((lat, lng), pontos[0][:2])
    cos0 = math.cos(math.radians(lat))

    def xy(a, b):
        return ((b - lng) * 111.32 * cos0, (a - lat) * 110.57)

    melhor = None
    for (la0, lo0, k0), (la1, lo1, k1) in zip(pontos, pontos[1:]):
        ax, ay = xy(la0, lo0)
        bx, by = xy(la1, lo1)
        dx, dy = bx - ax, by - ay
        comp2 = dx * dx + dy * dy
        t = 0.0 if comp2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / comp2))
        px, py = ax + t * dx, ay + t * dy
        dist = math.hypot(px, py)
        if melhor is None or dist < melhor[1] - 1e-9:
            melhor = (k0 + (k1 - k0) * t, dist)
    return melhor


# ------------------------------------------------------------------ posicoes guardadas
def _ultima_posicao(conn, chave: str):
    try:
        return conn.execute("SELECT * FROM viagem_posicoes WHERE chave = ? ORDER BY em DESC, id DESC LIMIT 1",
                            (chave,)).fetchone()
    except Exception:
        return None


def limpar(conn, agora: datetime, chave_ativa: str | None) -> int:
    """Apaga tudo que nao e do acompanhamento de agora, e qualquer posicao velha (trava dura). Commita."""
    try:
        if chave_ativa:
            n = conn.execute("DELETE FROM viagem_posicoes WHERE chave != ?", (chave_ativa,)).rowcount
        else:
            n = conn.execute("DELETE FROM viagem_posicoes").rowcount
        n += conn.execute("DELETE FROM viagem_posicoes WHERE em < ?",
                          ((agora - timedelta(hours=GUARDAR_MAX_H)).isoformat(timespec="seconds"),)).rowcount
        conn.commit()
        return n
    except Exception:
        return 0


def apagar_viagem(conn, viagem_id) -> None:
    """Pra quem encerra a viagem (viagem_planejada.encerrar pode chamar): some o caminho dela na hora."""
    try:
        conn.execute("DELETE FROM viagem_posicoes WHERE chave = ?", (f"viagem-{viagem_id}",))
        conn.commit()
    except Exception:
        pass


def _ja_chegou(conn, chave: str) -> bool:
    try:
        import db

        return (db.obter_configuracao(conn, CONFIG_CHEGOU) or "") == chave
    except Exception:
        return False


def _marcar_chegou(conn, chave: str) -> None:
    try:
        import db

        db.definir_configuracao(conn, CONFIG_CHEGOU, chave)
        conn.commit()
    except Exception:
        pass


# ------------------------------------------------------------------ o que esta sendo acompanhado agora
def _viagem_em_janela(conn, plano: dict, agora: datetime) -> bool:
    saida, chegada = _dt(plano.get("saida_em")), _dt(plano.get("chegada_em"))
    if not saida or not chegada:
        return False
    if _ja_chegou(conn, _chave_viagem(plano)):
        return False
    return saida - timedelta(minutes=ACOMPANHAR_ANTES_MIN) <= agora <= chegada + timedelta(hours=ACOMPANHAR_DEPOIS_H)


def compromisso_saindo(resposta_compromisso: dict | None, agora: datetime) -> str | None:
    """id do compromisso do ao vivo que esta na fase de ir (da hora de sair ate o fim), ou None.
    Tarefa sem saida (um passo "hora") nao conta: ninguem dirige pra ela."""
    r = resposta_compromisso or {}
    if not r.get("ativo") or r.get("kind") == "viagem":
        return None
    passos = r.get("passos") or []
    sair = next((p for p in passos if p.get("chave") == "sair"), None)
    em, fim = _dt((sair or {}).get("em")), _dt(r.get("fim_em"))
    if not em or not fim:
        return None
    return r.get("id") if em - timedelta(minutes=SAIDA_ANTES_MIN) <= agora <= fim else None


def acompanhamento(conn, agora: datetime, resposta_compromisso: dict | None = None) -> dict | None:
    """{"chave", "plano"?} do que esta sendo acompanhado (viagem ganha), ou None. `resposta_compromisso` e o
    ao vivo sem viagem (rotas.ao_vivo._montar); sem ele, calcula aqui (sem rede)."""
    plano = _plano_ativo(conn, agora)
    if plano and _viagem_em_janela(conn, plano, agora):
        return {"chave": _chave_viagem(plano), "plano": plano}
    if resposta_compromisso is None:
        try:
            from rotas import ao_vivo

            resposta_compromisso = ao_vivo._montar(conn, agora, False, lambda _c: None,
                                                   ao_vivo._tarefas_com_hora(conn, agora))
        except Exception:
            resposta_compromisso = None
    chave = compromisso_saindo(resposta_compromisso, agora)
    return {"chave": chave, "plano": None} if chave else None


def validar_posicao(corpo, agora: datetime) -> dict | str:
    """Corpo do POST /api/localizacao/posicao -> dados limpos, ou o texto do erro (400)."""
    if not isinstance(corpo, dict):
        return "corpo invalido"
    lat, lng = _num(corpo.get("lat")), _num(corpo.get("lng", corpo.get("lon")))
    if lat is None or lng is None or not (-90 <= lat <= 90 and -180 <= lng <= 180) or (lat == 0 and lng == 0):
        return "lat/lng invalidos"
    em = _dt(corpo.get("em")) if corpo.get("em") else agora
    if em is None or em > agora + timedelta(minutes=5) or em < agora - timedelta(minutes=60):
        return "em fora da hora"
    vel = _num(corpo.get("velocidade"))
    prec = _num(corpo.get("precisao"))
    return {
        "lat": round(lat, CASAS_COORD), "lng": round(lng, CASAS_COORD),
        "velocidade": round(vel, 1) if vel is not None and 0 <= vel < 120 else None,  # m/s (< 430 km/h)
        "precisao": round(min(prec, 100000), 1) if prec is not None and prec >= 0 else None,
        "em": em,
    }


def guardar_posicao(conn, dados: dict, agora: datetime) -> dict:
    """Guarda a posicao se tiver algo sendo acompanhado; senao apaga tudo e diz pro app parar.
    Viagem que chegou perto do destino: encerra e apaga o caminho. Commita."""
    alvo = acompanhamento(conn, agora)
    if not alvo:
        limpar(conn, agora, None)
        return {"ok": True, "guardou": False, "acompanhar": False}
    chave = alvo["chave"]
    limpar(conn, agora, chave)
    if alvo["plano"] is None:
        # compromisso de saida: so a ultima posicao (pra quem calcula atraso), nada de caminho
        conn.execute("DELETE FROM viagem_posicoes WHERE chave = ?", (chave,))
    conn.execute(
        "INSERT INTO viagem_posicoes (chave, lat, lng, velocidade, precisao, em) VALUES (?, ?, ?, ?, ?, ?)",
        (chave, dados["lat"], dados["lng"], dados["velocidade"], dados["precisao"],
         dados["em"].isoformat(timespec="seconds")),
    )
    conn.commit()
    plano = alvo["plano"]
    if plano is not None:
        pontos = _pontos(plano)
        total = _total_km(plano, pontos)
        perto = pontos and _km_entre((dados["lat"], dados["lng"]), pontos[-1][:2]) <= CHEGOU_KM
        proj = projetar_km(pontos, dados["lat"], dados["lng"])
        falta = total - proj[0] if proj else None
        if perto or (falta is not None and proj[1] <= 5 and falta <= CHEGOU_KM):
            _marcar_chegou(conn, chave)
            apagar_viagem(conn, plano["id"])
            _encerrar(conn, plano["id"])
            return {"ok": True, "guardou": False, "acompanhar": False, "chegou": True}
    return {"ok": True, "guardou": True, "acompanhar": True}


def ultima_posicao(conn, agora: datetime) -> dict | None:
    """A ultima posicao do que esta sendo acompanhado agora (pra outras frentes: atraso, pra onde vou)."""
    alvo = acompanhamento(conn, agora)
    r = _ultima_posicao(conn, alvo["chave"]) if alvo else None
    if not r:
        return None
    return {"lat": r["lat"], "lng": r["lng"], "velocidade": r["velocidade"], "em": r["em"]}


# ------------------------------------------------------------------ ao vivo da viagem
def _min_texto(minutos: float) -> str:
    m = max(1, int(round(minutos)))
    if m < 60:
        return f"daqui {m} min"
    h, r = divmod(m, 60)
    return f"daqui {h} h" if r == 0 else f"daqui {h} h {r:02d}"


def _destino(conn, plano: dict) -> str:
    texto = plano.get("destino")
    try:
        from rotas.ao_vivo import apelido_do_lugar

        nome = apelido_do_lugar(conn, texto)
    except Exception:
        nome = None
    return nome or "Viagem"


def _chuva_a_frente(plano: dict, rodado: float, quando_no_km) -> tuple[str | None, str | None]:
    """("daqui 25 min" | "chovendo, mais 12 km" | None, rotulo do tile)."""
    trechos = []
    for c in plano.get("chuva") or []:
        if not isinstance(c, dict):
            continue
        de, ate = _num(c.get("de_km")), _num(c.get("ate_km"))
        if de is None or ate is None or ate <= de:
            continue
        trechos.append((de, ate, str(c.get("tipo") or "chuva").strip()[:20] or "chuva", c.get("inicio_em")))
    trechos.sort()
    for de, ate, tipo, inicio in trechos:
        if ate <= rodado:
            continue
        chave = tipo.lower()
        rotulo = ROTULOS_TEMPO.get(chave) or (tipo[:1].upper() + tipo[1:]).replace("_", " ")
        if de <= rodado:
            return f"{'chovendo' if chave in CHOVE else 'agora'}, mais {max(1, round(ate - rodado))} km", rotulo
        return quando_no_km(de, inicio), rotulo
    return None, None


def ao_vivo(conn, agora: datetime, alvo: dict | None = None) -> dict | None:
    """O JSON do kind `viagem` do /api/ao-vivo, ou None (sem viagem em andamento).

    Aparece com plano ativo e: posicao nos ultimos POSICAO_RECENTE_MIN, ou no horario de saida (15 min antes
    ate 45 min depois), ou ja com posicao desta viagem e ainda antes da chegada refeita + 30 min (parou no posto:
    o ao vivo nao some e volta, porque o iOS nao deixa ligar de novo com o app fechado)."""
    plano = (alvo or {}).get("plano") if alvo is not None else _plano_ativo(conn, agora)
    if not plano or not _viagem_em_janela(conn, plano, agora):
        return None
    pontos = _pontos(plano)
    total = _total_km(plano, pontos)
    ancoras = _ancoras(plano, total)
    if not ancoras:
        return None
    saida, chegada_plano = ancoras[0][1], ancoras[-1][1]
    chave = _chave_viagem(plano)
    pos = _ultima_posicao(conn, chave)
    pos_em = _dt(pos["em"]) if pos else None
    proj = projetar_km(pontos, pos["lat"], pos["lng"]) if pos else None

    if pos_em and proj:
        rodado = min(max(proj[0], 0.0), total)
        # parado ha mais de 10 min (posto, almoco): o relogio corre, a chegada empurra
        ref = pos_em if agora - pos_em <= timedelta(minutes=PARADO_DEPOIS_MIN) else agora
        atraso = ref - _hora_no_km(ancoras, rodado)
        chegada = chegada_plano + atraso
        recente = agora - pos_em <= timedelta(minutes=POSICAO_RECENTE_MIN)
        if not recente and agora > chegada + timedelta(minutes=DEPOIS_DA_CHEGADA_MIN):
            return None
    else:
        # sem posicao (ou sem rota pra projetar): pela hora, e so na hora da saida ou dirigindo agora
        dirigindo = pos_em is not None and agora - pos_em <= timedelta(minutes=POSICAO_RECENTE_MIN)
        na_saida = saida - timedelta(minutes=SAIDA_ANTES_MIN) <= agora <= saida + timedelta(minutes=SAIDA_DEPOIS_MIN)
        if not (dirigindo or na_saida):
            return None
        rodado = _km_na_hora(ancoras, agora)
        ref = agora
        atraso = timedelta(0)
        chegada = chegada_plano

    falta = max(0.0, total - rodado)
    frac = rodado / total if total > 0 else 0.0
    # comeco da barra tal que, na hora `ref`, ela esteja em `frac` e chegue cheia na chegada: anda sozinha
    # no iPhone (ProgressView timerInterval) e se acerta a cada posicao nova
    if pos_em and chegada > ref and frac < 0.99:
        barra_desde = ref - (chegada - ref) * (frac / (1 - frac))
    else:
        barra_desde = saida if chegada > saida else chegada - timedelta(hours=1)

    def quando_no_km(km, inicio_txt=None):
        em = _dt(inicio_txt) + atraso if _dt(inicio_txt) else _hora_no_km(ancoras, km) + atraso
        return _min_texto((em - ref).total_seconds() / 60) if em > ref else "daqui 1 min"

    posto = None
    for p in sorted((p for p in plano.get("postos") or [] if isinstance(p, dict) and _num(p.get("km")) is not None),
                    key=lambda p: _num(p["km"])):
        if _num(p["km"]) > rodado + 0.5:
            posto = p
            break
    posto_km = posto_em = posto_nome = None
    if posto:
        posto_km = max(1, round(_num(posto["km"]) - rodado))
        em = _dt(posto.get("passa_em")) or _hora_no_km(ancoras, _num(posto["km"]))
        posto_em = _iso(em + atraso)
        nome = re.sub(r"\s+", " ", str(posto.get("nome") or "")).strip()
        posto_nome = nome[:40] or None

    chuva, chuva_rotulo = _chuva_a_frente(plano, rodado, quando_no_km)
    destino = _destino(conn, plano)
    fim = max(chegada, agora) + timedelta(minutes=DEPOIS_DA_CHEGADA_MIN + 15)
    return {
        "ativo": True,
        "id": f"{chave}-{saida:%Y-%m-%d}",
        "titulo": destino,
        "kind": "viagem",
        "assunto": "viagem",
        "icone": ICONE_VIAGEM,
        "cor": COR_VIAGEM,
        "lugar": None,
        "passos": [{"chave": "sair", "rotulo": "Saída", "em": _iso(saida)},
                   {"chave": "chegar", "rotulo": destino, "em": _iso(chegada)}],
        "atual": 0 if agora >= saida else -1,
        "clima": None,
        "levar": [],
        "evento_em": _iso(chegada),
        "fim_em": _iso(fim),
        "gerado_em": _iso(agora),
        "viagem": {
            "falta_km": int(round(falta)),
            "total_km": int(round(total)),
            "barra_desde": _iso(barra_desde),
            "posto_km": posto_km,
            "posto_em": posto_em,
            "posto_nome": posto_nome,
            "chuva": chuva,
            "chuva_rotulo": chuva_rotulo,
            "posicao_em": _iso(pos_em) if pos_em else None,
        },
    }
