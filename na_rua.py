""""Ele ja esta na rua" (leva 07/11, frente B): o card/plano/IA nao repete "sair de casa HH:MM" quando o
iPhone diz que ele nao esta em casa.

Base: as visitas do iPhone (`onde_estou`). Fora de casa quando
  - a visita aberta e de um lugar reconhecido que nao e casa;
  - a visita aberta nao tem lugar, mas a casa tem coordenada e o ponto fica fora do raio dela
    (`onde_estou.lugar_da_visita`, o mesmo raio do reconhecimento);
  - nao ha visita aberta e ele saiu de algum lugar ha menos de 2 h (esta no caminho).
Sem base (sem visita recente, casa sem coordenada) -> None: nao chuta, o plano de sempre fica.

`ajustar_plano` troca "sair_de_casa"/"comecar_a_se_arrumar" por "daqui ate la" (Maps do ponto atual,
se der) - so pra compromisso de HOJE que ainda nao passou e e daqui a no maximo HORIZONTE_H horas.
"""

import logging
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

SAIU_RECENTE_H = 2
NOTA_IA = ("ele já está na rua (pelo iPhone): não fala em sair de casa nem repete o horário antigo de sair; "
           "se falar de saída, é daqui até lá")


def _casa(conn) -> list[dict]:
    import onde_estou

    try:
        return [x for x in onde_estou.lugares_com_coordenada(conn) if x.get("apelido") == "casa" and x.get("coord")]
    except Exception:
        log.exception("na_rua: coordenada da casa falhou")
        return []


def estado(conn, agora: datetime | None = None) -> dict | None:
    """{"lugar", "onde" ("no mecânico" / "na rua"), "lat", "lon"} quando ele nao esta em casa; None em casa ou
    sem base pra dizer."""
    import onde_estou

    agora = agora or datetime.now()
    try:
        v = onde_estou.visita_atual(conn, agora)
        if v is None:
            v = conn.execute(
                "SELECT * FROM visitas WHERE saida IS NOT NULL AND saida <= ? AND saida >= ? "
                "ORDER BY saida DESC, id DESC LIMIT 1",
                ((agora + timedelta(minutes=10)).isoformat(timespec="seconds"),
                 (agora - timedelta(hours=SAIU_RECENTE_H)).isoformat(timespec="seconds")),
            ).fetchone()
            if v is None:
                return None
            # saiu e ainda nao chegou em lugar nenhum: no caminho
            return {"lugar": None, "onde": "na rua", "lat": v["lat"], "lon": v["lon"], "caminho": True}
    except Exception:  # banco velho sem a tabela visitas
        return None
    if v["lugar"] == "casa":
        return None
    if v["lugar"]:
        textos = [x for r in onde_estou._tarefas_de_hoje(conn, agora.date().isoformat())
                  for x in (r["title"], r["local"] or "")]  # o nome com acento (o apelido e sem)
        nome, genero = onde_estou.nome_e_genero(v["lugar"], textos)
        return {"lugar": v["lugar"], "onde": onde_estou._em(nome, genero), "lat": v["lat"], "lon": v["lon"]}
    casa = _casa(conn)
    if not casa:
        return None  # sem a casa no mapa nao da pra dizer que ta fora
    if onde_estou.lugar_da_visita(casa, v["lat"], v["lon"], v["precisao"]):
        return None
    return {"lugar": None, "onde": "na rua", "lat": v["lat"], "lon": v["lon"]}


def daqui_ate_la_min(conn, rua: dict, local: str | None) -> int | None:
    """Minutos de carro do ponto atual ate o lugar (Maps com cache, conta a cota la). None sem dado."""
    import onde_estou
    import vida_assistente

    if not local or not rua or rua.get("lat") is None or rua.get("lon") is None:
        return None
    try:
        minutos = onde_estou._trajeto_min((rua["lat"], rua["lon"]), vida_assistente.resolver_lugar(conn, local))
    except Exception:
        return None
    return minutos if isinstance(minutos, int) and minutos > 0 else None


# 08/11 (rodada com a IA de verdade): na rua as 7h30 com date as 20h virava "sai daqui 19h03" (57 min do ponto
# da manha) e o card perdia o "se arrumar". Longe assim ele passa em casa antes: so vale pro que e daqui a pouco.
HORIZONTE_H = 3


def _hoje_e_futuro(data_iso: str | None, hora: str | None, agora: datetime) -> bool:
    try:
        ev = datetime.fromisoformat(f"{data_iso}T{hora}")
    except (TypeError, ValueError):
        return False
    return ev.date() == agora.date() and agora < ev <= agora + timedelta(hours=HORIZONTE_H)


def ajustar_plano(conn, plano: dict, data_iso: str | None, hora: str | None, local: str | None,
                  agora: datetime | None = None) -> dict:
    """Plano com "sair_de_casa" -> sem ele quando ele ja esta na rua (compromisso de hoje, ainda por vir).
    Devolve um dict novo (o de entrada fica igual)."""
    agora = agora or datetime.now()
    if not plano or "sair_de_casa" not in plano or not _hoje_e_futuro(data_iso, hora, agora):
        return plano
    rua = estado(conn, agora)
    if not rua:
        return plano
    novo = {k: v for k, v in plano.items() if k not in ("sair_de_casa", "comecar_a_se_arrumar")}
    novo["ja_esta_na_rua"] = rua["onde"]
    novo["nota"] = NOTA_IA
    minutos = daqui_ate_la_min(conn, rua, local)
    if minutos:
        novo["daqui_ate_la_min"] = minutos
        try:
            sair = datetime.fromisoformat(f"{data_iso}T{hora}") - timedelta(minutes=minutos)
            novo["sair_daqui"] = f"{sair:%H:%M}"
        except (TypeError, ValueError):
            pass
    return novo


def linha_contexto(conn, agora: datetime | None = None) -> str | None:
    """Linha pro contexto do chat (a IA nao repete o "sair de casa" do plano velho)."""
    rua = estado(conn, agora)
    if not rua:
        return None
    return (f"Ele já está na rua agora ({rua['onde']}, pelo iPhone): {NOTA_IA}. Isso vale pro que é nas próximas "
            f"{HORIZONTE_H} h; compromisso mais tarde segue o plano de sempre (se arrumar e sair de casa).")
