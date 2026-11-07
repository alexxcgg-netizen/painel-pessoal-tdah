"""avisos_pendentes.py - fila de avisos que o app do iPhone busca e mostra como aviso LOCAL; o push do
navegador vira reserva (leva 07/11/2026, frente C, docs/briefings/2026-11-07-lugar-certo-e-avisos.md).

Sem APNs (conta gratis da Apple), o app nao recebe nada sozinho: ele so pega o que o painel tem quando
acorda (abrir, voltar, visita do GPS, BGAppRefreshTask, posicao de viagem). Entao:
  - aviso SEM hora conhecida (atraso, indo pra, insistencia, os da IA, tarefa parada, gasto...) entra aqui
    (`enfileirar`) em vez de sair na hora pelo navegador;
  - o app busca (`GET /api/app/avisos/pendentes` -> `para_app`), mostra/agenda como aviso local e conta de
    volta o que pegou (`POST /api/app/avisos/pendentes/entregues` -> `marcar_entregues`);
  - o que o app nao pegou em PRAZO_CRITICO_MIN (critico) / PRAZO_MIN (resto) sai pelo navegador no tick
    (`mandar_vencidos`). Se o app nao fala com o painel ha VIVO_H horas, nem espera: push na hora.
  - aviso da IA (`agendar_aviso` no chat) tem hora: o app agenda pra hora certa; sem app, o push sai na hora.

Os de hora conhecida (HORA_CONHECIDA) continuam no caminho de 06/11 (avisos_app.py: o app agenda antes, o
navegador pula o que o app cobriu) e os da fila de evento de hora_certa.py (JA_TEM_FILA) ja tiveram a chance
do app. Nada aqui reduz aviso: so troca QUEM entrega. Na duvida, sai pelo navegador.

Tabela propria criada aqui (`_tabela`), sem mexer em db.py.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

CHAVE_CONTATO = "avisos_app_contato_em"
VIVO_H = 36  # o app sumiu ha mais que isso: o navegador volta a ser o caminho principal
PRAZO_CRITICO_MIN = 3
PRAZO_MIN = 15
VALIDADE_H = 6  # nao entregue e ja passou disso da hora: aviso velho nao ajuda, sai da fila sem mandar
HORAS_A_FRENTE = 36
MAX_PARA_APP = 20
LIMITE_IA_DIA = 20  # sanidade dos avisos que a IA agenda (por dia do aviso)

# o app agenda esses sozinho com antecedencia (avisos_app.montar): o tick manda direto o que ele nao cobriu
HORA_CONHECIDA = frozenset({"se_arrumar", "hora_de_sair", "saida_preparo", "saida_porta", "tarefa_preparo",
                            "tarefa_horario", "tarefa_agora", "voo_sair"})
# fila de evento de hora_certa.py: o app ja teve 3 min pra pegar antes do tick ver o aviso
JA_TEM_FILA = frozenset({"casa_tarefa", "treino_pergunta", "voo_decisao", "rotina_descoberta", "tarefa_adiada",
                         "indo_pra", "atraso_recado"})
CRITICOS = frozenset({
    "tarefa_horario", "compromisso_chegando", "voo_sair", "hiperfoco_fim", "adiado_hiperfoco",
    "adiado_hiperfoco_leve", "tarefa_inegociavel", "foco_meio", "disjuntor", "espera_chama",
    "se_arrumar", "hora_de_sair", "saida_porta", "saida_previsao", "saida_chegou", "saida_parada", "tarefa_agora",
    "atraso_recado", "indo_pra", "lugar_fechado", "transito_piorou", "voo_decisao",
})


def _tabela(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS avisos_pendentes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag TEXT NOT NULL,
            tipo TEXT NOT NULL,
            ref INTEGER NOT NULL DEFAULT 0,
            titulo TEXT NOT NULL,
            corpo TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL DEFAULT '/',
            categoria TEXT NOT NULL DEFAULT '',
            rota TEXT NOT NULL DEFAULT '',
            origem TEXT NOT NULL DEFAULT 'tick',
            critico INTEGER NOT NULL DEFAULT 0,
            criado_em TEXT NOT NULL,
            quando TEXT NOT NULL,
            prazo_push TEXT NOT NULL,
            entregue_app_em TEXT,
            push_em TEXT,
            cancelado_em TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_avisos_pendentes_abertos ON avisos_pendentes (entregue_app_em, push_em, cancelado_em)")


def _iso(d: datetime) -> str:
    return d.replace(microsecond=0).isoformat(timespec="seconds")


def _dt(v) -> datetime | None:
    try:
        return datetime.fromisoformat(v) if v else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- app vivo

def marcar_contato(conn, agora: datetime) -> None:
    """Toda rota do app (/api/app/avisos*) chama: e o "o app esta vivo" das 36 h."""
    from db import definir_configuracao

    definir_configuracao(conn, CHAVE_CONTATO, _iso(agora))
    conn.commit()


def ultimo_contato(conn) -> datetime | None:
    from db import obter_configuracao

    contato = _dt(obter_configuracao(conn, CHAVE_CONTATO))
    try:  # app de 06/11 (antes desta leva) so conta o que agendou: vale como contato tambem
        import json

        import avisos_app

        dados = json.loads(obter_configuracao(conn, avisos_app.CHAVE) or "null")
        if isinstance(dados, dict) and dados.get("em"):
            em = datetime.fromtimestamp(float(dados["em"]))
            contato = max(contato, em) if contato else em
    except (TypeError, ValueError, OSError):
        pass
    return contato


def app_vivo(conn, agora: datetime) -> bool:
    c = ultimo_contato(conn)
    return bool(c and agora - c <= timedelta(hours=VIVO_H))


def vai_pra_fila(conn, tipo: str, agora: datetime, insistencia: bool = False) -> bool:
    """O tick do servidor deve deixar este aviso pro app (em vez de mandar o push agora)? A repeticao
    (insistencia) de qualquer tipo vai: o app so agenda o 1o aviso dos de hora conhecida."""
    if not tipo or (not insistencia and (tipo in HORA_CONHECIDA or tipo in JA_TEM_FILA)):
        return False
    try:
        return app_vivo(conn, agora)
    except Exception:  # noqa: BLE001 - na duvida, o push sai
        log.exception("avisos_pendentes: app_vivo falhou")
        return False


# ---------------------------------------------------------------- fila

def enfileirar(conn, *, tipo: str, ref: int, titulo: str, corpo: str, agora: datetime, quando: datetime | None = None,
               url: str = "/", categoria: str = "", rota: str = "", origem: str = "tick", critico: bool | None = None,
               tag: str | None = None) -> int:
    """Guarda o aviso (titulo ja com emoji) pro app. O mesmo aviso (tag) ainda esperando e trocado pelo novo
    (insistencia: a repeticao substitui a anterior, igual no navegador). Devolve o id."""
    _tabela(conn)
    quando = (quando or agora).replace(microsecond=0)
    critico = (tipo in CRITICOS) if critico is None else bool(critico)
    base = max(quando, agora)
    if app_vivo(conn, agora):
        prazo = base + timedelta(minutes=PRAZO_CRITICO_MIN if critico else PRAZO_MIN)
    else:
        prazo = base  # app sumido: o navegador manda na hora (ou na hora marcada)
    tag = tag or f"{tipo}-{int(ref)}"
    conn.execute(
        "UPDATE avisos_pendentes SET cancelado_em = ? WHERE tag = ? AND entregue_app_em IS NULL AND push_em IS NULL "
        "AND cancelado_em IS NULL", (_iso(agora), tag))
    cur = conn.execute(
        "INSERT INTO avisos_pendentes (tag, tipo, ref, titulo, corpo, url, categoria, rota, origem, critico, criado_em, "
        "quando, prazo_push) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (tag, tipo, int(ref), (titulo or "")[:120], (corpo or "")[:400], url or "/", categoria or "", rota or "",
         origem, int(critico), _iso(agora), _iso(quando), _iso(prazo)))
    conn.commit()
    return cur.lastrowid


def entregar(conn, *, tipo: str, ref: int, titulo: str, corpo: str, agora: datetime, enviar_push,
             url: str = "/", categoria: str = "", rota: str = "", origem: str = "evento", critico: bool | None = None) -> str:
    """Aviso que nasce fora do tick (onde_estou, frente D...): app vivo -> fila (o navegador e reserva);
    app sumido -> `enviar_push()` na hora, como antes. Devolve "fila" ou "push"."""
    try:
        if app_vivo(conn, agora):
            enfileirar(conn, tipo=tipo, ref=ref, titulo=titulo, corpo=corpo, agora=agora, url=url, categoria=categoria,
                       rota=rota, origem=origem, critico=critico)
            return "fila"
    except Exception:  # noqa: BLE001 - fila quebrada nunca come o aviso
        log.exception("avisos_pendentes: fila falhou, vai pelo navegador")
    enviar_push()
    return "push"


# ref = id da tarefa: tarefa concluida enquanto o aviso esperava sai da fila (nem app nem navegador)
TIPOS_DE_TAREFA = frozenset({"tarefa_horario", "tarefa_preparo", "tarefa_horario_passou", "tarefa_parada", "se_arrumar",
                             "hora_de_sair", "tarefa_inegociavel", "tarefa_agora", "lugar_fechado", "transito_piorou",
                             "chegou_casa"})


def _abertos(conn, agora: datetime | None = None):
    _tabela(conn)
    linhas = conn.execute(
        "SELECT * FROM avisos_pendentes WHERE entregue_app_em IS NULL AND push_em IS NULL AND cancelado_em IS NULL "
        "ORDER BY quando, id").fetchall()
    vivas = []
    for r in linhas:
        if r["tipo"] in TIPOS_DE_TAREFA and r["ref"]:
            t = conn.execute("SELECT completed_at FROM tasks WHERE id = ?", (r["ref"],)).fetchone()
            if t is not None and t["completed_at"]:
                conn.execute("UPDATE avisos_pendentes SET cancelado_em = ? WHERE id = ?",
                             (_iso(agora or datetime.now()), r["id"]))
                continue
        vivas.append(r)
    if len(vivas) != len(linhas):
        conn.commit()
    return vivas


def para_app(conn, agora: datetime) -> list[dict]:
    """O que o app ainda nao pegou (e o navegador ainda nao mandou), ate 36 h pra frente."""
    import notificacoes

    saida = []
    limite = agora + timedelta(hours=HORAS_A_FRENTE)
    velho = agora - timedelta(hours=VALIDADE_H)
    for r in _abertos(conn, agora):
        quando = _dt(r["quando"])
        if not quando or quando > limite or quando < velho:
            continue
        saida.append({
            "id": r["id"],
            "ident": f"fila-{r['id']}",
            "tag": r["tag"],
            "tipo": r["tipo"],
            # o da IA ja vem com o emoji que ela escolheu; o resto ganha o do assunto (nunca dobra)
            "titulo": r["titulo"] if r["origem"] == "ia" else notificacoes.com_emoji(r["tipo"], r["titulo"]),
            "corpo": r["corpo"],
            "quando_ts": int(quando.timestamp()),
            "categoria": r["categoria"] or "",
            "rota": r["rota"] or "",
            "url": r["url"] or "/",
            "critico": bool(r["critico"]),
        })
        if len(saida) >= MAX_PARA_APP:
            break
    return saida


def marcar_entregues(conn, ids, agora: datetime) -> int:
    """O app mostrou (ou agendou pra hora certa) estes: o navegador nao manda mais."""
    _tabela(conn)
    limpos = [int(i) for i in (ids if isinstance(ids, list) else [])
              if isinstance(i, (int, str)) and not isinstance(i, bool) and str(i).isdigit()][:100]
    if not limpos:
        return 0
    marcas = ",".join("?" * len(limpos))
    cur = conn.execute(
        f"UPDATE avisos_pendentes SET entregue_app_em = ? WHERE id IN ({marcas}) AND entregue_app_em IS NULL "
        "AND push_em IS NULL AND cancelado_em IS NULL", (_iso(agora), *limpos))
    conn.commit()
    return cur.rowcount


def vencidos(conn, agora: datetime) -> list:
    """Prazo do app passou: vai pelo navegador. O que ficou velho demais sai da fila sem mandar."""
    saida = []
    velho = agora - timedelta(hours=VALIDADE_H)
    for r in _abertos(conn, agora):
        quando, prazo = _dt(r["quando"]), _dt(r["prazo_push"])
        if not quando or not prazo:
            continue
        if quando < velho:
            conn.execute("UPDATE avisos_pendentes SET cancelado_em = ? WHERE id = ?", (_iso(agora), r["id"]))
            continue
        if prazo <= agora:
            saida.append(r)
    conn.commit()
    return saida


def mandar_vencidos(conn, agora: datetime, enviar) -> int:
    """Tick do servidor: `enviar(linha) -> bool` manda pelo navegador (e Telegram, se for o caso)."""
    n = 0
    for r in vencidos(conn, agora):
        try:
            enviar(r)
        except Exception:  # noqa: BLE001
            log.exception("avisos_pendentes: push da fila falhou (%s)", r["tag"])
        conn.execute("UPDATE avisos_pendentes SET push_em = ? WHERE id = ?", (_iso(agora), r["id"]))
        n += 1
    conn.commit()
    return n


def cancelar(conn, tag: str, agora: datetime) -> int:
    """Aviso que perdeu o sentido (tarefa feita, toque no aviso pelo navegador)."""
    _tabela(conn)
    cur = conn.execute(
        "UPDATE avisos_pendentes SET cancelado_em = ? WHERE tag = ? AND entregue_app_em IS NULL AND push_em IS NULL "
        "AND cancelado_em IS NULL", (_iso(agora), tag))
    conn.commit()
    return cur.rowcount


def resumo(conn, agora: datetime, dias: int = 7) -> dict:
    """Diagnostico: quem entregou nos ultimos `dias` (app x navegador), o que espera e o contato do app."""
    _tabela(conn)
    desde = _iso(agora - timedelta(days=dias))
    r = conn.execute(
        "SELECT SUM(entregue_app_em IS NOT NULL) app, SUM(push_em IS NOT NULL) nav, "
        "SUM(cancelado_em IS NOT NULL) cancelados, "
        "SUM(entregue_app_em IS NULL AND push_em IS NULL AND cancelado_em IS NULL) esperando, "
        "SUM(origem = 'ia') ia FROM avisos_pendentes WHERE criado_em >= ?", (desde,)).fetchone()
    contato = ultimo_contato(conn)
    return {"dias": dias, "pelo_app": int(r["app"] or 0), "pelo_navegador": int(r["nav"] or 0),
            "cancelados": int(r["cancelados"] or 0), "esperando": int(r["esperando"] or 0), "da_ia": int(r["ia"] or 0),
            "app_contato": contato.isoformat(timespec="minutes") if contato else None,
            "app_vivo": app_vivo(conn, agora)}


# ---------------------------------------------------------------- aviso da IA (ferramenta agendar_aviso)

def avisos_ia_do_dia(conn, dia: str) -> int:
    _tabela(conn)
    return conn.execute(
        "SELECT COUNT(*) FROM avisos_pendentes WHERE origem = 'ia' AND substr(quando, 1, 10) = ? AND cancelado_em IS NULL",
        (dia,)).fetchone()[0]


def agendar_ia(conn, *, titulo: str, corpo: str, quando: datetime, agora: datetime, assunto: str = "lembrete") -> dict:
    """Aviso que a IA agenda pelo chat. Quem chama ja validou texto/hora/silencio. Limite de LIMITE_IA_DIA."""
    import avisos_texto

    dia = quando.date().isoformat()
    if avisos_ia_do_dia(conn, dia) >= LIMITE_IA_DIA:
        return {"erro": f"ja tem {LIMITE_IA_DIA} avisos teus agendados pra esse dia (limite de sanidade)"}
    emoji = avisos_texto.EMOJI_DA_IA.get(assunto, avisos_texto.EMOJI_DA_IA["lembrete"])
    _tabela(conn)
    aviso_id = enfileirar(conn, tipo="aviso_ia", ref=0, titulo=f"{emoji} {titulo}", corpo=corpo, agora=agora,
                          quando=quando, url="/?aba=assistente", categoria="soneca", origem="ia", critico=False,
                          tag=f"aviso_ia-tmp-{secrets.token_hex(6)}")
    conn.execute("UPDATE avisos_pendentes SET tag = ?, ref = ? WHERE id = ?", (f"aviso_ia-{aviso_id}", aviso_id, aviso_id))
    conn.commit()
    return {"ok": True, "id": aviso_id, "quando": quando.isoformat(timespec="minutes"), "titulo": f"{emoji} {titulo}",
            "corpo": corpo, "pelo_app": app_vivo(conn, agora)}


TITULO_IA_MAX = 40
CORPO_IA_MAX = 90
DIAS_IA_MAX = 30


def _sem_emoji_na_frente(t: str) -> str:
    t = (t or "").strip()
    while t and not t[0].isalnum() and t[0] not in "\"'(¿¡":
        t = t[1:].lstrip()
    return t


def agendar_pelo_chat(conn, entrada: dict, agora: datetime) -> dict:
    """Ferramenta `agendar_aviso` do chat: valida (texto curto com "tu", hora no futuro, limite do dia, silencio)
    e agenda. `agora` = hora local sem fuso (a mesma do tick)."""
    import re
    from datetime import date

    import avisos_texto
    import db
    import notificacoes

    if not isinstance(entrada, dict):
        return {"erro": "entrada invalida"}
    titulo = _sem_emoji_na_frente(" ".join(str(entrada.get("titulo") or "").split()))
    corpo = " ".join(str(entrada.get("corpo") or "").split())
    if not titulo:
        return {"erro": "falta o titulo (1 linha curta, sem emoji)"}
    if len(titulo) > TITULO_IA_MAX:
        return {"erro": f"titulo com {len(titulo)} letras: no maximo {TITULO_IA_MAX} (1 linha da tela bloqueada)"}
    if len(corpo) > CORPO_IA_MAX:
        return {"erro": f"corpo com {len(corpo)} letras: no maximo {CORPO_IA_MAX} (2 linhas da tela bloqueada)"}
    if re.search(r"\bvoc[eê]s?\b", f"{titulo} {corpo}", re.I):
        return {"erro": "reescreva com 'tu' (nunca 'voce'), no estilo leve de sempre"}
    assunto = entrada.get("assunto") if entrada.get("assunto") in avisos_texto.EMOJI_DA_IA else "lembrete"

    em = entrada.get("em_minutos")
    if em not in (None, "") and not isinstance(em, bool):
        try:
            em = int(float(em))
        except (TypeError, ValueError):
            return {"erro": "em_minutos invalido"}
        if not 1 <= em <= 24 * 60:
            return {"erro": "em_minutos fora do razoavel (1 a 1440)"}
        quando = agora.replace(second=0, microsecond=0) + timedelta(minutes=em)
    else:
        hora = str(entrada.get("hora") or "").strip()
        m = re.fullmatch(r"(\d{1,2})[:hH]?(\d{2})?", hora)
        if not m or int(m.group(1)) > 23 or int(m.group(2) or 0) > 59:
            return {"erro": f"hora invalida: {entrada.get('hora')!r} (use HH:MM ou em_minutos)"}
        try:
            dia = date.fromisoformat(entrada["quando_data"]) if entrada.get("quando_data") else agora.date()
        except (TypeError, ValueError):
            return {"erro": f"data invalida: {entrada.get('quando_data')!r}"}
        quando = datetime.combine(dia, datetime.min.time()).replace(hour=int(m.group(1)), minute=int(m.group(2) or 0))
    if quando <= agora:
        return {"erro": f"{quando:%d/%m %H:%M} ja passou - confirme com o Alex quando ele quis dizer"}
    if quando > agora + timedelta(days=DIAS_IA_MAX):
        return {"erro": f"longe demais (mais de {DIAS_IA_MAX} dias): use registrar_lembrete pra isso"}
    if not entrada.get("mesmo_no_silencio") and notificacoes.dentro_do_horario_silencioso(
            quando, db.obter_configuracao(conn, "silencio_inicio") or "22:00",
            db.obter_configuracao(conn, "silencio_fim") or "07:00"):
        return {"erro": (f"{quando:%H:%M} cai no horario silencioso dele. So agende se ele PEDIU aviso nessa hora "
                         "(ai mande mesmo_no_silencio=true); senao proponha outro horario.")}
    r = agendar_ia(conn, titulo=titulo, corpo=corpo, quando=quando, agora=agora, assunto=assunto)
    if r.get("ok"):
        r["obs"] = ("aviso agendado: chega como notificacao do app do iPhone na hora (ou pelo navegador, se o app "
                    "nao pegar). Confirme em UMA frase curta, com a hora.")
    return r
