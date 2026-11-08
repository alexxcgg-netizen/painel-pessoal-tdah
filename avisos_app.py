"""avisos_app.py - avisos que o app nativo do iPhone agenda sozinho (leva 06/11/2026,
docs/briefings/2026-11-06-avisos-app.md).

A conta gratis da Apple nao tem push remoto (APNs), mas o app pode agendar aviso LOCAL: o iPhone toca
na hora certa mesmo com o app fechado e o PC desligado. Entao o app pergunta ao painel
(`GET /api/app/avisos`) quais avisos de hora conhecida vem por ai, agenda tudo e conta de volta o que
ficou agendado (`POST /api/app/avisos/agendados`). Na hora, o servidor pula o push do navegador desse
aviso (`coberto`) pra nao chegar dois. A insistencia continua igual, pelo navegador.

Hora conhecida = compromisso de saida (se arrumar, hora de sair, "daqui 15 min", "5 min pra sair"),
tarefa com hora ("faltam 30 min", "daqui a pouco", e "e agora" na hora exata - `tarefa_agora`, que so o app
manda, leva 06/11 docs/briefings/2026-11-06-ao-vivo-tarefa.md) e a saida pro voo. Mesma conta e mesmo texto do
servidor (notificacoes.plano_se_arrumar / avisos_se_arrumar, tempo.passos_da_saida). Na duvida, nao
agenda: o push do navegador continua cobrindo.

Este arquivo nao fala com rede nem com Flask: quem chama passa as funcoes de trajeto/clima/voo.
"""
from __future__ import annotations

import json
from datetime import datetime, time, timedelta

import notificacoes

CHAVE = "avisos_app_agendados"
TOLERANCIA_MIN = 6  # o tick do servidor e de 5 min; o app agenda no minuto da conta
VALIDADE_H = 36  # agendado ha mais tempo que isso: o app pode ter sumido, o navegador volta a avisar
MAX_ITENS = 40  # o iPhone guarda ate 64 avisos pendentes por app
HORAS_A_FRENTE = 36

# quanto antes da hora o servidor manda cada um (pra o aviso local cair no mesmo minuto)
PREPARO_TAREFA_MIN = 30  # notificacoes.tarefas_preparo: janela 15-34 min, o tick pega ~30-34
CHEGANDO_TAREFA_MIN = 10  # notificacoes.tarefas_com_horario_chegando: a partir de 10 min antes
PREPARO_SAIDA_MIN = 15  # tempo.PREPARO_JANELA_MIN (10, 16]: "daqui 15 min comeca a se arrumar"
PORTA_SAIDA_MIN = 5  # tempo.PORTA_JANELA_MIN (4, 9]: "5 min pra sair"
VOO_ANTES_MIN = 22  # _aviso_voo_sair avisa dentro dos 25 min antes da hora de sair

# tipos que passam pelo hiperfoco no servidor (vida.CRITICOS_HIPERFOCO); o resto fica de fora do
# agendamento se o foco cobre a hora
_CRITICOS_PADRAO = frozenset({"tarefa_horario", "voo_sair"})
# so o app manda (o servidor nao tem esse aviso): segue a regra do aviso de tarefa que ele estende
_SEGUE_O_CRITICO = {"tarefa_agora": "tarefa_horario"}


CATEGORIA_DO_TIPO = {"casa_tarefa": "casa", "chegou_casa": "casa"}

# 07/11 (frente C): botoes por assunto no aviso local (UNNotificationCategory no app, AvisosLocais.swift).
#   "hora"   = Feito / +15 min / Amanha  (tarefa com hora: o aviso de agora, os de antes)
#   "saida"  = Abrir rota / +15 min      (hora de sair, voo, indo pra: so com `rota`; sem rota vira "soneca")
#   "soneca" = +15 min                   (se arrumar, passo a passo, aviso da IA...)
# "+15 min" = soneca: o app avisa de novo daqui 15 min com o mesmo texto; o servidor so para a insistencia.
# App antigo nao conhece a categoria: cai no `acoes` (Feito / Adiar 1 h) como antes.
CATEGORIAS_APP = ("tarefa", "casa", "hora", "saida", "soneca")
_CATEGORIA_NOVA = {
    "tarefa_preparo": "hora", "tarefa_horario": "hora", "tarefa_agora": "hora", "tarefa_horario_passou": "hora",
    "tarefa_inegociavel": "hora",
    "hora_de_sair": "saida", "saida_porta": "saida", "voo_sair": "saida", "indo_pra": "saida",
    "atraso_recado": "soneca", "transito_piorou": "saida", "lugar_fechado": "soneca",
    "se_arrumar": "soneca", "saida_preparo": "soneca", "agua_pausa": "soneca", "aviso_ia": "soneca",
    "saida_previsao": "soneca", "compromisso_chegando": "saida",
}


def categoria(tipo: str, de_uma_tarefa=frozenset(), rota: str | None = None) -> str:
    cat = _CATEGORIA_NOVA.get(tipo)
    if cat == "saida" and not rota:
        cat = "soneca"
    if cat:
        return cat
    return "tarefa" if tipo in de_uma_tarefa else CATEGORIA_DO_TIPO.get(tipo, "")


def link_rota(local) -> str | None:
    """Waze ja navegando pro endereco em texto (sem rede aqui; o Waze resolve o endereco)."""
    from urllib.parse import quote

    if not isinstance(local, str) or not local.strip():
        return None
    return f"https://waze.com/ul?q={quote(local.strip()[:200])}&navigate=yes"


def _item(tipo: str, ref: int, quando: datetime, titulo: str, corpo: str, url_do_aviso, de_uma_tarefa,
          rota: str | None = None, conn=None) -> dict:
    tag = f"{tipo}-{ref}"
    if conn is not None:  # titulo generico (voo, agua...) ganha variacao do catalogo, estavel por aviso/dia
        import avisos_texto

        titulo, corpo = avisos_texto.variar_titulo(conn, tipo, titulo, corpo, chave=f"{tag}-{quando:%Y-%m-%d}")
    return {
        "id": f"painel-{tag}-{quando:%Y%m%d}",
        "tag": tag,
        "tipo": tipo,
        "quando": quando.isoformat(timespec="minutes"),
        "quando_ts": int(quando.timestamp()),
        "titulo": notificacoes.com_emoji(tipo, titulo),
        "corpo": corpo,
        "acoes": tipo in de_uma_tarefa,
        # categoria do aviso no app (06/11, frente 7): "tarefa" = Feito / Adiar 1 h; "casa" = Feito / Amanha
        # (hora_certa.py); "" = sem botao (o toque abre o card). App antigo ignora e segue so com `acoes`.
        # 07/11: "hora" / "saida" / "soneca" (botoes novos, ver CATEGORIAS_APP)
        "categoria": categoria(tipo, de_uma_tarefa, rota),
        "rota": rota or "",
        "url": url_do_aviso(tipo, tag) if url_do_aviso else "/",
    }


def _do_tipo(avisos, tipo):
    return [a for a in avisos if a[0] == tipo]


def _hora_do_dia(dia, hora: str) -> datetime | None:
    try:
        return datetime.combine(dia, datetime.strptime(hora, "%H:%M").time())
    except (TypeError, ValueError):
        return None


def montar(conn, agora: datetime, *, minutos_arrumar: int = 40, trajeto_min=None, trajeto_parada=None,
           clima=None, saida_voo=None, ligado=None, ja_notificou=None, segurar_ate: datetime | None = None,
           criticos=_CRITICOS_PADRAO, url_do_aviso=None, de_uma_tarefa=frozenset(),
           agendados: dict | None = None) -> list[dict]:
    """Avisos de hora conhecida de hoje e de amanha, em ordem de hora, no maximo MAX_ITENS.

    - `trajeto_min(local)` / `trajeto_parada(parada, local)` / `clima(data_iso, hora)`: so pra hoje
      (amanha usa a folga, e o app sincroniza de novo antes);
    - `saida_voo(voo) -> {"sair_ate", "texto"} | None`: so pros voos de hoje;
    - `ligado(tipo)`: Assistente > Avisos; `ja_notificou(tipo, ref)`: ja saiu hoje;
    - `agendados` (carregar_agendados): o que o app ja tem agendado. "Ja saiu hoje" que na verdade e o
      servidor contando como mandado o aviso que o APP vai tocar (coberto, ate 6 min antes) continua na
      lista - senao a proxima sincronizada do app apagava o aviso antes da hora e nao tocava nada (06/11);
    - `segurar_ate`: hiperfoco/modo foco ate essa hora - tipo nao critico antes disso nao entra.
    """
    import tempo

    ligado = ligado or (lambda tipo: True)
    ja_notificou = ja_notificou or (lambda tipo, ref: False)
    limite = agora + timedelta(hours=HORAS_A_FRENTE)
    candidatos: list[tuple[str, int, datetime, str, str]] = []
    rotas: dict[tuple[str, int], str | None] = {}  # (tipo, ref) -> link do Waze (botao "Abrir rota", 07/11)

    amanha = datetime.combine(agora.date() + timedelta(days=1), time(0, 0))
    for inicio in (agora, amanha):
        hoje = inicio is agora
        dia = inicio.date()
        planos = notificacoes.plano_se_arrumar(
            conn, inicio, minutos_arrumar,
            trajeto_min=trajeto_min if hoje else None,
            trajeto_parada=trajeto_parada if hoje else None,
        )
        ids_sair = {p["id"] for p in planos}
        for p in planos:
            for tipo, ref, titulo, corpo in _do_tipo(notificacoes.avisos_se_arrumar([p], p["comecar"], conn=conn), "se_arrumar"):
                candidatos.append((tipo, ref, p["comecar"], titulo, corpo))
            for tipo, ref, titulo, corpo in _do_tipo(notificacoes.avisos_se_arrumar([p], p["saida"], conn=conn), "hora_de_sair"):
                candidatos.append((tipo, ref, p["saida"], titulo, corpo))
            if p.get("local") and not p.get("parada"):
                rotas[("hora_de_sair", p["id"])] = rotas[("saida_porta", p["id"])] = link_rota(p["local"])
            quando_preparo = p["comecar"] - timedelta(minutes=PREPARO_SAIDA_MIN)
            quando_porta = p["saida"] - timedelta(minutes=PORTA_SAIDA_MIN)
            clima_dia = clima if hoje else None
            try:
                for tipo, ref, titulo, corpo in _do_tipo(tempo.passos_da_saida(conn, [p], quando_preparo, clima=clima_dia), "saida_preparo"):
                    candidatos.append((tipo, ref, quando_preparo, titulo, corpo))
                for tipo, ref, titulo, corpo in _do_tipo(tempo.passos_da_saida(conn, [p], quando_porta, clima=clima_dia), "saida_porta"):
                    candidatos.append((tipo, ref, quando_porta, titulo, corpo))
            except Exception:  # noqa: BLE001 - passo a passo e extra; sem ele o servidor avisa pelo navegador
                pass

        # SELECT *: o "e agora" olha a linha inteira (estilo, local, parada, extras) pra saber se e de sair
        rows = conn.execute(
            "SELECT * FROM tasks WHERE completed_at IS NULL AND due_date = ? AND hora IS NOT NULL",
            (dia.isoformat(),),
        ).fetchall()
        for r in rows:
            if r["id"] in ids_sair:
                continue
            evento = _hora_do_dia(dia, r["hora"])
            if evento is None:
                continue
            # leva 08/11: o contexto do texto (hora, fim de semana, "sequencia" de feitas) e o da hora do PROPRIO
            # aviso, nao o de agora - as 22h, com 3 feitas, o das 07:00 de amanha dizia "boa sequencia hoje".
            quando_chegando = evento - timedelta(minutes=CHEGANDO_TAREFA_MIN)
            quando_preparo = evento - timedelta(minutes=PREPARO_TAREFA_MIN)
            if notificacoes.e_refeicao(r["title"]):
                titulo, corpo = notificacoes.TITULO_REFEICAO, notificacoes.texto_refeicao(r["title"])
            else:
                titulo = notificacoes.titulo_tarefa(r["title"])
                # 07/11 (frente C): mesma chave do tick do servidor -> mesmo texto nos dois caminhos
                corpo = notificacoes.texto_tarefa_chegando(r["hora"], antes=True, conn=conn, agora=quando_chegando,
                                                           chave=f"tarefa_horario-{r['id']}-{dia.isoformat()}")
                candidatos.append(("tarefa_preparo", r["id"], quando_preparo, titulo,
                                   notificacoes.texto_tarefa_preparo(r["hora"], PREPARO_TAREFA_MIN, conn=conn,
                                                                     agora=quando_preparo,
                                                                     chave=f"tarefa_preparo-{r['id']}-{dia.isoformat()}")))
            candidatos.append(("tarefa_horario", r["id"], quando_chegando, titulo, corpo))
            if not notificacoes.e_refeicao(r["title"]):
                # leva 08/11: compromisso de sair ganha texto de sair na hora exata (nunca "toca em Feito")
                candidatos.append(("tarefa_agora", r["id"], evento, titulo, notificacoes.texto_agora_da_tarefa(
                    r, conn=conn, agora=evento, chave=f"tarefa_agora-{r['id']}-{dia.isoformat()}")))

    if saida_voo:
        for voo in notificacoes.voos_de_hoje_com_horario(conn, agora.date()):
            try:
                s = saida_voo(voo)
            except Exception:  # noqa: BLE001 - Maps fora: o servidor tenta de novo no tick
                s = None
            if s and s.get("sair_ate"):
                candidatos.append(("voo_sair", voo["id"], s["sair_ate"] - timedelta(minutes=VOO_ANTES_MIN),
                                   notificacoes.TITULO_VOO_SAIR, s["texto"]))

    try:  # painel esperto, frente 7 (06/11): avisos de evento (chegou em casa, academia, voo, rotina)
        import hora_certa

        candidatos.extend(hora_certa.para_app(conn, agora, agendados or {}))
    except Exception:  # noqa: BLE001 - extra, nunca derruba a lista do app
        import logging

        logging.getLogger(__name__).exception("hora_certa: para_app falhou")

    itens, vistos = [], set()
    for tipo, ref, quando, titulo, corpo in sorted(candidatos, key=lambda c: c[2]):
        quando = quando.replace(second=0, microsecond=0)
        if quando <= agora + timedelta(seconds=20) or quando > limite:
            continue
        chave = (tipo, ref, quando.date())
        if chave in vistos:
            continue
        if not ligado(tipo):
            continue
        if quando.date() == agora.date() and ja_notificou(tipo, ref) \
                and not coberto(agendados or {}, f"{tipo}-{ref}", quando):
            continue
        if segurar_ate and quando < segurar_ate and tipo not in criticos \
                and _SEGUE_O_CRITICO.get(tipo) not in criticos:
            continue
        vistos.add(chave)
        itens.append(_item(tipo, ref, quando, titulo, corpo, url_do_aviso, de_uma_tarefa,
                           rota=rotas.get((tipo, ref)), conn=conn))
        if len(itens) >= MAX_ITENS:
            break
    return itens


# ---------------------------------------------------------------- o que o app conta que agendou

def gravar_agendados(conn, itens, agora: datetime) -> int:
    """Guarda a lista inteira (o app apaga e agenda tudo de novo a cada sincronizada). Ignora item torto."""
    limpos = []
    for it in itens if isinstance(itens, list) else []:
        if not isinstance(it, dict):
            continue
        tag, ts = it.get("tag"), it.get("quando_ts")
        if not isinstance(tag, str) or not tag.strip() or len(tag) > 120:
            continue
        if isinstance(ts, bool) or not isinstance(ts, (int, float)):
            continue
        limpos.append([tag.strip(), int(ts)])
        if len(limpos) >= 64:
            break
    from db import definir_configuracao

    definir_configuracao(conn, CHAVE, json.dumps({"em": int(agora.timestamp()), "itens": limpos}))
    conn.commit()
    return len(limpos)


def carregar_agendados(conn, agora: datetime) -> dict[str, list[int]]:
    """tag -> [quando_ts...] do que o app agendou. Vazio se o app nao sincroniza faz VALIDADE_H."""
    try:
        from db import obter_configuracao

        bruto = obter_configuracao(conn, CHAVE)
        dados = json.loads(bruto) if bruto else None
        if not isinstance(dados, dict):
            return {}
        if agora.timestamp() - float(dados.get("em") or 0) > VALIDADE_H * 3600:
            return {}
        saida: dict[str, list[int]] = {}
        for tag, ts in dados.get("itens") or []:
            saida.setdefault(str(tag), []).append(int(ts))
        return saida
    except (TypeError, ValueError):
        return {}


def coberto(agendados: dict[str, list[int]], tag: str, agora: datetime, tolerancia_min: int = TOLERANCIA_MIN) -> bool:
    """O app agendou este aviso pra (perto de) agora? Entao ele toca por la e o navegador fica quieto."""
    agora_ts = agora.timestamp()
    return any(abs(agora_ts - ts) <= tolerancia_min * 60 for ts in agendados.get(tag, ()))
