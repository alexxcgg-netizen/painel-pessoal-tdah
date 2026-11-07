"""Leva 06/11 "painel mais esperto" (docs/briefings/2026-11-06-painel-esperto.md, frentes 4 e 7).

Tres coisas que nascem do mesmo momento - ele SAIU de um lugar (visita ou cerca do iPhone, onde_estou.py):

  1. Pra onde vou: saiu perto da hora de sair de uma tarefa de hoje com lugar (janela de 40 min) -> o painel
     assume o destino, mede a chegada com o transito daquele ponto (Maps, que ja conta a cota) e pergunta
     "Indo pro date?" com o trajeto (card `indo_pra`, botoes "E isso" / "Vou pra outro lugar"). Outro lugar:
     nao insiste (nem recado, nem amostra).
  2. Aprende teus tempos reais: a hora que o painel mandou sair x a hora que ele saiu de casa ('saida'), e o
     trajeto real x o do Maps por faixa do dia ('trajeto'). Com 3+ amostras (as ultimas 6), a conta da saida
     (notificacoes.plano_se_arrumar e tempo.compromissos, via notificacoes.meu_tempo_min) avisa antes, e o
     card `meu_tempo` diz de onde veio ("tu costuma sair 10 min depois do aviso"). "Meu tempo / Padrao" fica
     na config `tempos_reais_usar`. Sem amostra: igual a antes. So ADIANTA aviso, nunca atrasa.
  3. Atrasado? Recado pronto: a chegada estimada passa da hora -> aviso cedo + card `recado_atraso` com o
     texto pronto, chips 10/15/20 min e o botao que abre o WhatsApp (wa.me, ele escolhe o contato; o painel
     NUNCA manda sozinho). Uma vez por compromisso; de novo so se o atraso crescer mais de 10 min.

Texto por template (zero IA). Localizacao some em 30 dias (como as visitas); as amostras nao tem lugar.
"""

from __future__ import annotations

import json
import logging
import math
import os
import sqlite3
import statistics
import time as _time
from datetime import date, datetime, time, timedelta

import cards
import db
import maps_client
import notificacoes

log = logging.getLogger(__name__)

TIPO_INDO = "indo_pra"
TIPO_RECADO = "atraso_recado"
TIPO_CARD_MEU_TEMPO = "meu_tempo_card"  # so trava (1 card por compromisso por dia), nao e aviso
JANELA_SAIDA_MIN = 40
ATRASO_TOLERANCIA_MIN = 3  # chegada estimada passou da hora por mais que isso = vai atrasar
RECADO_CRESCE_MIN = 10
FOLGA_MIN = 15  # mesma folga do aviso "hora de sair" sem Maps
RETENCAO_DIAS = 30
MIN_AMOSTRAS = 3
MAX_AMOSTRAS = 6
GUARDA_AMOSTRAS = 60
AJUSTE_MAX_MIN = 30
AMOSTRA_SAIDA_MAX_MIN = 90  # saiu 2 h depois do aviso: nao e "o jeito dele", e outra coisa
CHUVA_LEVAR_PCT = 40
CONFIG_USAR = "tempos_reais_usar"
WHATSAPP = "https://wa.me/?text="

COR_DATE, COR_BALADA, COR_TAREFA = "#f5a3b8", "#c4a1ff", "#f0a58f"


# ------------------------------------------------------------------ utilidades


def _iso(dt: datetime | None) -> str | None:
    return dt.replace(microsecond=0).isoformat(timespec="seconds") if dt else None


def _dt(txt) -> datetime | None:
    try:
        return datetime.fromisoformat(txt) if txt else None
    except (TypeError, ValueError):
        return None


def _hm(dt: datetime) -> str:
    return f"{dt:%H:%M}"


def _evento(dia: date, hora: str | None) -> datetime | None:
    try:
        return datetime.combine(dia, datetime.strptime(hora or "", "%H:%M").time())
    except ValueError:
        return None


def _min(a: datetime, b: datetime) -> int:
    """Minutos de a ate b (arredondado)."""
    return round((b - a).total_seconds() / 60)


def _app():
    try:
        from rotas._base import app_modulo

        return app_modulo()
    except Exception:
        return None


def _coluna(r, nome: str):
    return r[nome] if nome in r.keys() else None


def _cor(estilo) -> str:
    return {"date": COR_DATE, "balada": COR_BALADA}.get(estilo or "", COR_TAREFA)


def faixa(dt: datetime) -> str:
    h = dt.hour
    if h < 6:
        return "madrugada"
    if h < 10:
        return "manha"
    if h < 16:
        return "dia"
    if h < 20:
        return "tarde"
    return "noite"


# ------------------------------------------------------------------ 2. tempos reais


def preferencia(conn) -> str:
    try:
        v = (db.obter_configuracao(conn, CONFIG_USAR) or "").strip()
    except Exception:
        return "meu"
    return "padrao" if v == "padrao" else "meu"


def definir_preferencia(conn, usar: str) -> str:
    usar = "padrao" if usar == "padrao" else "meu"
    db.definir_configuracao(conn, CONFIG_USAR, usar)
    conn.commit()
    return usar


def _amostras(conn, tipo: str, faixa_: str | None = None) -> list[int]:
    """As ultimas 6 (mais nova primeiro)."""
    sql = "SELECT valor_min FROM tempos_reais WHERE tipo = ?" + (" AND faixa = ?" if faixa_ else "")
    try:
        rows = conn.execute(sql + " ORDER BY id DESC LIMIT ?",
                            (tipo, faixa_, MAX_AMOSTRAS) if faixa_ else (tipo, MAX_AMOSTRAS)).fetchall()
    except sqlite3.Error:  # banco velho de teste sem a tabela
        return []
    return [int(r[0]) for r in rows]


def _aprendido(valores: list[int]) -> int:
    if len(valores) < MIN_AMOSTRAS:
        return 0
    return max(0, min(AJUSTE_MAX_MIN, round(statistics.median(valores))))


def frase_ajuste(saida_min: int, trajeto_min: int) -> str:
    partes = []
    if saida_min:
        partes.append(f"tu costuma sair {saida_min} min depois do aviso")
    if trajeto_min:
        partes.append(f"nesse horário o caminho leva uns {trajeto_min} min a mais que o Maps diz")
    return " e ".join(partes)


def ajuste(conn, evento: datetime | None = None, so_saida: bool = False) -> dict:
    """Quanto adiantar a saida pelo jeito dele. `min` ja respeita "Meu tempo / Padrao" (padrao = 0);
    `aprendido` e o que ele teria. `so_saida`: a hora dita ja e a de sair (tasks.sai_na_hora), o trajeto
    nao muda quando ele tem que sair."""
    saidas = _amostras(conn, "saida")
    s = _aprendido(saidas)
    t = 0
    if not so_saida and evento is not None:
        t = _aprendido(_amostras(conn, "trajeto", faixa(evento - timedelta(minutes=30))))
    total = min(AJUSTE_MAX_MIN, s + t)
    usar = preferencia(conn)
    return {
        "min": total if usar == "meu" else 0, "aprendido": total, "saida_min": s, "trajeto_min": t,
        "usar": usar, "amostras": list(reversed(saidas)), "frase": frase_ajuste(s, t),
    }


def _guardar_amostra(conn, tipo: str, valor: int, dia: str, ref: int, faixa_: str | None = None) -> bool:
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO tempos_reais (tipo, faixa, valor_min, dia, ref) VALUES (?, ?, ?, ?, ?)",
            (tipo, faixa_, int(valor), dia, ref),
        )
        conn.execute(
            "DELETE FROM tempos_reais WHERE tipo = ? AND id NOT IN "
            "(SELECT id FROM tempos_reais WHERE tipo = ? ORDER BY id DESC LIMIT ?)",
            (tipo, tipo, GUARDA_AMOSTRAS),
        )
        conn.commit()
        return cur.rowcount == 1
    except sqlite3.Error:
        return False


def _amostra_de_saida(conn, row) -> bool:
    """Saiu de CASA pra um compromisso com hora de sair mandada pelo painel: saiu - aviso."""
    if row["origem"] != "casa" or not row["sair_aviso"] or not row["saiu_em"] or row["resposta"] == "outro":
        return False
    saiu = _dt(row["saiu_em"])
    aviso = _evento(saiu.date(), row["sair_aviso"]) if saiu else None
    if not aviso:
        return False
    dif = _min(aviso, saiu)
    if abs(dif) > AMOSTRA_SAIDA_MAX_MIN:
        return False
    return _guardar_amostra(conn, "saida", dif, row["dia"], row["id"])


def _amostra_de_trajeto(conn, row) -> bool:
    saiu, chegou = _dt(row["saiu_em"]), _dt(row["chegou_em"])
    previsto = row["previsto_min"]
    if not saiu or not chegou or not isinstance(previsto, int) or previsto <= 0 or row["resposta"] == "outro":
        return False
    real = _min(saiu, chegou)
    if real <= 0 or real > previsto * 3 + 30:  # parou no caminho: nao e o trajeto
        return False
    return _guardar_amostra(conn, "trajeto", real - previsto, row["dia"], row["id"], faixa(saiu))


# ------------------------------------------------------------------ 1. pra onde vou


def _tarefas_com_lugar(conn, dia: date) -> list:
    try:
        return conn.execute(
            "SELECT * FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL AND due_date = ? "
            "AND hora IS NOT NULL ORDER BY hora, id", (dia.isoformat(),),
        ).fetchall()
    except sqlite3.Error:
        return []


def _destino_da_tarefa(conn, t, lugares: list[dict]) -> tuple[str | None, str | None]:
    """(texto pro card, endereco pro Maps). `local` da tarefa; senao um apelido no titulo (nunca casa)."""
    import onde_estou
    import vida_assistente

    local = (t["local"] or "").strip()
    if local:
        return local, vida_assistente.resolver_lugar(conn, local)
    for x in lugares:
        if x["apelido"] != "casa" and onde_estou._bate(x["apelido"], t["title"]):
            return x["apelido"], x["endereco"]
    return None, None


def _planos(conn, agora: datetime) -> dict[int, dict]:
    """plano_se_arrumar com o mesmo trajeto (cache de 1 h do app) dos avisos."""
    import vida_assistente

    app = _app()
    kw = {}
    if app is not None:
        kw = {
            "trajeto_min": lambda local: app._trajeto_min_aviso(vida_assistente.resolver_lugar(conn, local)),
            "trajeto_parada": lambda parada, local: app._trajetos_parada_aviso(conn, parada, local),
        }
    try:
        planos = notificacoes.plano_se_arrumar(conn, agora, vida_assistente.se_arrumar_min(conn), **kw)
    except Exception:
        log.exception("onde_vou: plano da saida falhou")
        return {}
    return {p["id"]: p for p in planos}


def _palpite(conn, visita, saiu: datetime) -> dict | None:
    """A tarefa de hoje com lugar cuja hora de sair fica mais perto da saida (ate 40 min)."""
    import onde_estou

    dia = saiu.date()
    lugares = onde_estou._lugares(conn, dia.isoformat())
    planos = _planos(conn, saiu - timedelta(minutes=1))
    melhor = None
    for t in _tarefas_com_lugar(conn, dia):
        ev = _evento(dia, t["hora"])
        if not ev or ev < saiu - timedelta(minutes=5):
            continue
        texto, endereco = _destino_da_tarefa(conn, t, lugares)
        if not endereco:
            continue
        # saiu do proprio lugar da tarefa: nao e "indo pra la"
        if visita["lugar"] and (visita["lugar"] == texto or onde_estou._e_o_lugar(
                conn, visita["lugar"], next((x for x in lugares if x["apelido"] == visita["lugar"]), None), texto, False)):
            continue
        p = planos.get(t["id"])
        sai_hora = bool(_coluna(t, "sai_na_hora"))
        if p:
            sair = p["saida"]
        elif sai_hora:
            sair = ev
        else:
            sair = ev - timedelta(minutes=FOLGA_MIN)
        dif = abs((saiu - sair).total_seconds()) / 60
        if dif > JANELA_SAIDA_MIN:
            continue
        if melhor is None or dif < melhor["dif"]:
            melhor = {"t": t, "evento": ev, "sair": sair if p else None, "texto": texto, "endereco": endereco,
                      "dif": dif, "sai_na_hora": sai_hora}
    return melhor


def _via(viagem: dict) -> str | None:
    """'BR-470, Gaspar' -> 'BR-470' (a rua/rodovia do pior trecho lento com nome)."""
    for x in viagem.get("lentidao") or []:
        if isinstance(x, dict) and x.get("nome"):
            return str(x["nome"]).split(",")[0].strip()[:40] or None
    return None


def _trajeto(origem: tuple[float, float], endereco: str) -> dict:
    """Maps com transito e trechos lentos daquele ponto (conta a cota no maps_client). {} sem Maps/rede."""
    if not maps_client.configurado():
        return {}
    try:
        v = maps_client.tempo_de_viagem(f"{origem[0]},{origem[1]}", endereco, lentidao=True)
    except Exception:  # rede, cota, sem rota: segue sem a chegada
        return {}
    return v if isinstance(v, dict) and isinstance(v.get("duracao_minutos"), (int, float)) else {}


def _clima_chegada(chegada: datetime) -> int | None:
    app = _app()
    if app is None:
        return None
    try:
        c = app._clima_aviso(chegada.date().isoformat(), f"{chegada:%H}:00")
        pct = c.get("chuva_pct") if isinstance(c, dict) else None
        return int(round(pct)) if isinstance(pct, (int, float)) and not isinstance(pct, bool) else None
    except Exception:
        return None


def _frase_chegada(chegada: datetime, ev: datetime) -> tuple[str, bool]:
    dif = _min(chegada, ev)
    if dif >= 2:
        return (f"{dif} min antes, com folga" if dif >= 10 else f"{dif} min antes"), False
    if dif >= -ATRASO_TOLERANCIA_MIN:
        return "bem na hora", False
    return f"{-dif} min depois das {_hm(ev)}", True


def dados_indo(conn, row, t, viagem: dict, agora: datetime) -> dict:
    """data do card `indo_pra` (estado final; nada de rede aqui)."""
    import nome_curto
    import onde_estou

    saiu = _dt(row["saiu_em"])
    ev = _evento(saiu.date(), row["hora_evento"])
    titulos = [t["title"]]
    eventos = []
    origem = row["origem"]
    if origem:
        nome, genero = onde_estou.nome_e_genero(origem, titulos)
        de = onde_estou._de(nome, genero)
    else:
        de = "de onde tava"
    sub_saiu = f"perto da hora de sair ({row['sair_aviso']})" if row["sair_aviso"] else "perto da hora do compromisso"
    eventos.append({"hora": _hm(saiu), "titulo": f"Saiu {de}", "sub": sub_saiu, "tipo": "saiu"})
    previsto = row["previsto_min"]
    chegada = _dt(row["chegada_prevista"])
    lento = next((x for x in viagem.get("lentidao") or [] if isinstance(x, dict) and x.get("nivel")), None)
    if lento and isinstance(previsto, int) and previsto > 0:
        dist = viagem.get("distancia_km")
        frac = (lento.get("de_km") or 0) / dist if isinstance(dist, (int, float)) and dist > 0 else 0.5
        quando = saiu + timedelta(minutes=round(previsto * max(0.0, min(1.0, frac))))
        transito = viagem.get("transito_min")
        sub = f"+{transito} min, já contado" if isinstance(transito, int) and transito >= 3 else "já contado"
        eventos.append({"hora": _hm(quando), "titulo": maps_client.frase_trecho(lento).split(" - ")[0],
                        "sub": sub, "tipo": "lento"})
    chuva = _clima_chegada(chegada) if chegada else None
    if chegada and chuva is not None and chuva >= CHUVA_LEVAR_PCT:
        eventos.append({"hora": _hm(chegada), "titulo": "Chuva na chegada",
                        "sub": f"{chuva}% de chance, leva o guarda-chuva", "tipo": "chuva"})
    atrasa = False
    if chegada and ev:
        frase, atrasa = _frase_chegada(chegada, ev)
        eventos.append({"hora": _hm(chegada), "titulo": f"Chega {onde_estou._em_texto(row['destino'], titulos)}",
                        "sub": frase, "tipo": "alerta" if atrasa else "fim"})
    return {
        "id": row["id"], "tarefa_id": row["tarefa_id"],
        # 07/11: nome curto do lugar ("Indo pro mecânico?"), corte em palavra inteira (nome_curto.py)
        "titulo": nome_curto.titulo_indo(conn, {**dict(t), "local": t["local"] or row["destino"]}),
        "destino": row["destino"], "hora": row["hora_evento"], "estilo": _coluna(t, "estilo"),
        "chega": _hm(chegada) if chegada else None,
        "chega_s": int((chegada - agora).total_seconds()) if chegada else None,
        "gerado_ts": int(_time.time()),
        "eventos": eventos, "atrasa": atrasa, "resposta": row["resposta"],
    }


def card_indo(conn, row, t, viagem: dict, agora: datetime) -> dict:
    return cards.novo_card("indo_pra", dados_indo(conn, row, t, viagem, agora))


def _coord_salva(conn, texto: str) -> tuple[float, float] | None:
    """Coordenada ja geocodificada de um apelido (cache do onde_estou) - sem chamar API."""
    import onde_estou
    import vida_assistente

    item = onde_estou._carregar_coords(conn).get(vida_assistente._chave_apelido(texto or ""))
    if isinstance(item, dict) and isinstance(item.get("lat"), (int, float)) and isinstance(item.get("lon"), (int, float)):
        return item["lat"], item["lon"]
    return None


def _ja_tratou_visita(conn, visita_id: int) -> bool:
    try:
        return conn.execute("SELECT 1 FROM indo_pra WHERE visita_id = ?", (visita_id,)).fetchone() is not None
    except sqlite3.Error:
        return True  # sem a tabela: nao faz nada


def _limpar(conn, agora: datetime) -> None:
    conn.execute("DELETE FROM indo_pra WHERE dia < ?", ((agora.date() - timedelta(days=RETENCAO_DIAS)).isoformat(),))


def na_saida(conn, visita, agora: datetime) -> list[str]:
    """Saiu de um lugar (visita com `saida`): adivinha pra onde vai, pergunta, e avisa se vai atrasar.
    Uma vez por visita e uma por tarefa por dia. Devolve o que fez (teste/log)."""
    import onde_estou

    saiu = _dt(visita["saida"])
    if not saiu or _ja_tratou_visita(conn, visita["id"]):
        return []
    palpite = _palpite(conn, visita, saiu)
    if not palpite:
        return []
    t, ev = palpite["t"], palpite["evento"]
    dia = saiu.date().isoformat()
    if conn.execute("SELECT 1 FROM indo_pra WHERE dia = ? AND tarefa_id = ?", (dia, t["id"])).fetchone():
        return []
    viagem = _trajeto((visita["lat"], visita["lon"]), palpite["endereco"])
    previsto = int(round(viagem["duracao_minutos"])) if viagem else None
    chegada = saiu + timedelta(minutes=previsto) if previsto is not None else None
    ll = viagem.get("destino_ll") if viagem else None
    if not (isinstance(ll, (list, tuple)) and len(ll) == 2):
        ll = maps_client.coordenada(palpite["endereco"]) or _coord_salva(conn, palpite["texto"])
    lat, lon = (round(float(ll[0]), 4), round(float(ll[1]), 4)) if ll else (None, None)
    cur = conn.execute(
        "INSERT OR IGNORE INTO indo_pra (dia, tarefa_id, visita_id, origem, destino, destino_lat, destino_lon, "
        "hora_evento, sair_aviso, saiu_em, previsto_min, chegada_prevista) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (dia, t["id"], visita["id"], visita["lugar"], palpite["texto"][:120], lat, lon, t["hora"],
         _hm(palpite["sair"]) if palpite["sair"] else None, _iso(saiu), previsto, _iso(chegada)),
    )
    _limpar(conn, agora)
    conn.commit()
    if cur.rowcount != 1:
        return []
    row = conn.execute("SELECT * FROM indo_pra WHERE id = ?", (cur.lastrowid,)).fetchone()
    feito = ["indo"]
    card = card_indo(conn, row, t, viagem, agora)
    d = card["data"]
    texto = f"{d['titulo']} " + (f"Chega {d['chega']}." if d["chega"] else "Te acompanho daqui.")
    onde_estou._publicar(conn, texto, [card])
    atraso = _min(ev, chegada) if chegada else None
    if atraso is not None and atraso > ATRASO_TOLERANCIA_MIN and not palpite["sai_na_hora"]:
        # vai atrasar: o aviso que importa e o do recado (um push so, nao dois juntos)
        if recado(conn, row, t, atraso, agora, via=_via(viagem),
                  transito=bool(viagem.get("transito_min") and viagem["transito_min"] >= 3), chegada=chegada):
            feito.append("recado")
        return feito
    corpo = (f"Chega {d['chega']} {onde_estou._em_texto(row['destino'], [t['title']])}." if d["chega"]
             else f"{row['destino']} às {t['hora']}.")
    # push + aviso local do app do iPhone pela fila de hora_certa (frente 7, 06/11), sem chegar dois
    import hora_certa

    hora_certa.avisar_evento(conn, TIPO_INDO, d["titulo"], corpo, agora, ref_legado=row["id"])
    return feito


def responder(conn, indo_id: int, resposta: str) -> dict | None:
    """"E isso" (sim) / "Vou pra outro lugar" (outro). Outro: para de insistir nessa tarefa hoje."""
    if resposta not in ("sim", "outro"):
        return None
    row = conn.execute("SELECT * FROM indo_pra WHERE id = ?", (indo_id,)).fetchone()
    if not row:
        return None
    conn.execute("UPDATE indo_pra SET resposta = ? WHERE id = ?", (resposta, indo_id))
    conn.commit()
    row = conn.execute("SELECT * FROM indo_pra WHERE id = ?", (indo_id,)).fetchone()
    if resposta == "sim":
        _amostra_de_saida(conn, row)
    else:
        conn.execute("DELETE FROM tempos_reais WHERE ref = ?", (indo_id,))
        conn.commit()
    return {"ok": True, "resposta": resposta}


def na_chegada(conn, visita, agora: datetime) -> list[str]:
    """Chegou num lugar: se e o destino de uma saida de hoje, fecha o trajeto e guarda as amostras."""
    import onde_estou

    chegou = _dt(visita["chegada"])
    if not chegou:
        return []
    try:
        rows = conn.execute(
            "SELECT * FROM indo_pra WHERE dia = ? AND chegou_em IS NULL AND saiu_em IS NOT NULL "
            "AND COALESCE(resposta, '') != 'outro' AND saiu_em < ? ORDER BY id DESC",
            (chegou.date().isoformat(), _iso(chegou)),
        ).fetchall()
    except sqlite3.Error:
        return []
    import vida_assistente

    for r in rows:
        perto = (r["destino_lat"] is not None and onde_estou._metros(
            (visita["lat"], visita["lon"]), (r["destino_lat"], r["destino_lon"])) <= onde_estou.RAIO_MAX_M)
        mesmo_nome = bool(visita["lugar"]) and visita["lugar"] == vida_assistente._chave_apelido(r["destino"] or "")
        if not (perto or mesmo_nome):
            continue
        conn.execute("UPDATE indo_pra SET chegou_em = ? WHERE id = ?", (_iso(chegou), r["id"]))
        conn.commit()
        r = conn.execute("SELECT * FROM indo_pra WHERE id = ?", (r["id"],)).fetchone()
        feito = ["chegou"]
        if _amostra_de_saida(conn, r):
            feito.append("amostra_saida")
        if _amostra_de_trajeto(conn, r):
            feito.append("amostra_trajeto")
        return feito
    return []


# ------------------------------------------------------------------ 4. atrasado? recado pronto


def arredonda_atraso(minutos: int) -> int:
    return max(5, int(math.ceil(minutos / 5) * 5))


def opcoes_atraso(n: int) -> list[int]:
    return [5, 10, 15] if n <= 5 else [n - 5, n, n + 5]


def texto_recado(modelo: str, minutos: int, via: str | None = None) -> str:
    """Mesmo texto do front (cards-onde.js textoRecado) - os chips trocam so o numero."""
    if modelo == "transito":
        onde = f" na {via}" if via else ""
        return f"Oi! Peguei trânsito{onde}, chego uns {minutos} min atrasado. Já tô a caminho."
    if modelo == "saindo":
        return f"Oi! Vou chegar uns {minutos} min atrasado. Já já tô saindo."
    return f"Oi! Vou chegar uns {minutos} min atrasado. Já tô a caminho."


def link_whatsapp(texto: str) -> str:
    from urllib.parse import quote

    return WHATSAPP + quote(texto, safe="")


def dados_recado(t, atraso: int, chegada: datetime | None, modelo: str, via: str | None, indo_id: int | None) -> dict:
    import nome_curto
    import onde_estou

    n = arredonda_atraso(atraso)
    texto = texto_recado(modelo, n, via)
    nome = nome_curto.cortar(onde_estou._titulo_frase(t["title"]), 40)
    return {
        "tarefa_id": t["id"], "indo_id": indo_id, "titulo": nome, "hora": t["hora"],
        "chega": _hm(chegada) if chegada else None, "atraso_min": int(atraso), "escolhido": n,
        "opcoes": opcoes_atraso(n), "modelo": modelo, "via": via, "texto": texto,
        "whatsapp": link_whatsapp(texto), "estilo": _coluna(t, "estilo"),
    }


def recado(conn, row, t, atraso: int, agora: datetime, via: str | None = None, transito: bool = False,
           chegada: datetime | None = None, parado: bool = False, cartoes: list | None = None) -> bool:
    """Publica o card do recado + aviso cedo. Uma vez por compromisso; de novo so se crescer > 10 min.
    `cartoes` (07/11): em vez de uma mensagem nova no chat, o card entra nessa lista (quem chamou publica
    junto com a sua - atraso + recado numa mensagem so)."""
    import onde_estou

    if row is not None and row["resposta"] == "outro":
        return False
    if row is not None and row["recado_min"] is not None and atraso <= row["recado_min"] + RECADO_CRESCE_MIN:
        return False
    if row is None:
        dia = agora.date().isoformat()
        conn.execute("INSERT OR IGNORE INTO indo_pra (dia, tarefa_id, destino, hora_evento) VALUES (?, ?, ?, ?)",
                     (dia, t["id"], (t["local"] or "")[:120] or None, t["hora"]))
        row = conn.execute("SELECT * FROM indo_pra WHERE dia = ? AND tarefa_id = ?", (dia, t["id"])).fetchone()
        if row["resposta"] == "outro" or (row["recado_min"] is not None
                                          and atraso <= row["recado_min"] + RECADO_CRESCE_MIN):
            return False
    conn.execute("UPDATE indo_pra SET recado_min = ? WHERE id = ?", (int(atraso), row["id"]))
    conn.commit()
    modelo = "saindo" if parado else ("transito" if (via or transito) else "caminho")
    d = dados_recado(t, atraso, chegada, modelo, via, row["id"])
    nome = d["titulo"]
    if d["chega"]:
        titulo_aviso = f"Vai chegar {d['chega']}, {nome} é {t['hora']}"
    else:
        titulo_aviso = f"Vai atrasar uns {d['escolhido']} min"
    if len(titulo_aviso) > notificacoes.TITULO_MAX:
        titulo_aviso = f"Vai chegar {d['chega']}" if d["chega"] else titulo_aviso[: notificacoes.TITULO_MAX]
    motivo = f"Lento na {via}. " if via else ("Trânsito no caminho. " if transito else "")
    corpo = f"{motivo}Quer mandar um recado? O texto tá pronto."
    card = cards.novo_card("recado_atraso", d)
    if cartoes is not None:
        cartoes.append(card)
    else:
        onde_estou._publicar(conn, f"{titulo_aviso}. Deixei o recado pronto, quem manda é tu.", [card])
    import hora_certa  # push + aviso local do app (o link do WhatsApp fica no card; o toque abre o chat)

    hora_certa.avisar_evento(conn, TIPO_RECADO, titulo_aviso, corpo, agora, ref_legado=row["id"])
    return True


def recado_parado(conn, r: dict, agora: datetime, cartoes: list | None = None) -> bool:
    """Do onde_estou.checar_atraso (parado num lugar e nao chega a tempo): so compromisso de sair/com lugar,
    que e onde tem alguem esperando."""
    tid = r.get("tarefa_id")
    if not isinstance(tid, int) or not isinstance(r.get("atraso_min"), (int, float)):
        return False
    t = conn.execute("SELECT * FROM tasks WHERE id = ?", (tid,)).fetchone()
    if not t:
        return False
    sair = (t["estilo"] in ("date", "balada") or notificacoes.e_compromisso_de_sair(t["title"])
            or (t["local"] or "").strip())
    if not sair or _coluna(t, "sai_na_hora"):
        return False
    hora_original = r.get("hora_original") or t["hora"]
    t = {**dict(t), "hora": hora_original}
    row = conn.execute("SELECT * FROM indo_pra WHERE dia = ? AND tarefa_id = ?",
                       (agora.date().isoformat(), tid)).fetchone()
    return recado(conn, row, t, int(r["atraso_min"]), agora, parado=True, cartoes=cartoes)


def atualizar_posicao(conn, lat: float, lon: float, agora: datetime) -> list[str]:
    """Pra viagem acompanhada (posicao do iPhone no caminho, frente 3 - outra rota chama): reconfere a chegada
    das saidas de hoje ainda sem chegada e manda o recado se passou da hora (ou se cresceu > 10 min)."""
    import onde_estou

    feito = []
    try:
        rows = conn.execute(
            "SELECT * FROM indo_pra WHERE dia = ? AND saiu_em IS NOT NULL AND chegou_em IS NULL "
            "AND COALESCE(resposta, '') != 'outro'", (agora.date().isoformat(),),
        ).fetchall()
    except sqlite3.Error:
        return feito
    for row in rows:
        t = conn.execute("SELECT * FROM tasks WHERE id = ?", (row["tarefa_id"],)).fetchone()
        ev = _evento(agora.date(), row["hora_evento"])
        if not t or not ev or t["completed_at"] or agora > ev + timedelta(minutes=60) or _coluna(t, "sai_na_hora"):
            continue
        import vida_assistente

        destino = vida_assistente.resolver_lugar(conn, row["destino"]) if row["destino"] else None
        minutos = onde_estou._trajeto_min((lat, lon), destino)
        if not minutos:
            continue
        chegada = agora + timedelta(minutes=minutos)
        conn.execute("UPDATE indo_pra SET chegada_prevista = ? WHERE id = ?", (_iso(chegada), row["id"]))
        conn.commit()
        atraso = _min(ev, chegada)
        if atraso > ATRASO_TOLERANCIA_MIN and recado(conn, row, t, atraso, agora, chegada=chegada, transito=True):
            feito.append("recado")
    return feito


POSICAO_FRESCA_MIN = 10
SEGUIR_A_CADA_MIN = 10


def _seguir_no_caminho(conn, agora: datetime) -> list[str]:
    """Tick de 5 min: com saida de hoje a caminho (sem chegada) e posicao recente do iPhone
    (viagem_acompanhada.ultima_posicao), reconfere a chegada - no maximo a cada 10 min (cota do Maps)."""
    try:
        aberta = conn.execute(
            "SELECT 1 FROM indo_pra WHERE dia = ? AND saiu_em IS NOT NULL AND chegou_em IS NULL "
            "AND COALESCE(resposta, '') != 'outro' LIMIT 1", (agora.date().isoformat(),),
        ).fetchone()
    except sqlite3.Error:
        return []
    if not aberta:
        return []
    try:
        import viagem_acompanhada

        pos = viagem_acompanhada.ultima_posicao(conn, agora)
    except Exception:
        return []
    em = pos.get("em") if pos else None
    em = em if isinstance(em, datetime) else _dt(em)
    if em is not None and em.tzinfo is not None:  # gravada com fuso; o agora daqui e local sem fuso
        em = em.astimezone().replace(tzinfo=None) if agora.tzinfo is None else em
    if not pos or not em or not (timedelta(0) <= agora - em <= timedelta(minutes=POSICAO_FRESCA_MIN)):
        return []
    ref = int(agora.timestamp() // (SEGUIR_A_CADA_MIN * 60))
    if db.ja_notificou_hoje(conn, "indo_pra_seguir", ref):
        return []
    db.marcar_notificado(conn, "indo_pra_seguir", ref)
    return atualizar_posicao(conn, float(pos["lat"]), float(pos["lng"]), agora)


# ------------------------------------------------------------------ card "Sai as X" (meu tempo)


def dados_meu_tempo(conn, p: dict, agora: datetime, a: dict | None = None) -> dict:
    a = a or ajuste(conn, p["evento"], bool(p.get("sai_na_hora")))
    sair = p["saida"]
    meu = int(p.get("meu_tempo_min") or 0)
    padrao = sair + timedelta(minutes=meu)
    sair_meu = padrao - timedelta(minutes=a["aprendido"])
    return {
        "tarefa_id": p["id"], "titulo": str(p["titulo"])[:48], "hora": p["hora"], "estilo": p.get("estilo"),
        "sair_meu": _hm(sair_meu), "sair_padrao": _hm(padrao),
        "sair_meu_s": int((sair_meu - agora).total_seconds()), "sair_padrao_s": int((padrao - agora).total_seconds()),
        "gerado_ts": int(_time.time()), "ajuste_min": a["aprendido"], "saida_min": a["saida_min"],
        "trajeto_min": a["trajeto_min"], "amostras": a["amostras"], "frase": a["frase"], "usar": a["usar"],
    }


def verificar(conn, agora: datetime) -> list:
    """Tick de 5 min (onde_estou.verificar): na hora de comecar a se arrumar de um compromisso em que o
    jeito dele mudou a saida, o card "Sai as X" vai pro chat explicando de onde veio. So o card: o aviso
    de se arrumar/sair ja sai pelo caminho de sempre, com a hora nova."""
    import onde_estou

    _seguir_no_caminho(conn, agora)
    for p in _planos(conn, agora).values():
        if int(p.get("meu_tempo_min") or 0) <= 0:
            continue
        if not (p["comecar"] - timedelta(minutes=4) <= agora < p["saida"]):
            continue
        if db.ja_notificou_hoje(conn, TIPO_CARD_MEU_TEMPO, p["id"]):
            continue
        db.marcar_notificado(conn, TIPO_CARD_MEU_TEMPO, p["id"])
        d = dados_meu_tempo(conn, p, agora)
        texto = f"Sai às {d['sair_meu']}: {d['frase']}, então já te aviso antes."
        onde_estou._publicar(conn, texto, [cards.novo_card("meu_tempo", d)])
    return []
