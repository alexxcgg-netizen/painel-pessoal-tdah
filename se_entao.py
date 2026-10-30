"""Se isso, entao aquilo (leva Lab v4, ideia "se-entao", 30/10/2026).

"Quero beber mais agua", "quero estudar todo dia": a intencao existe, mas nunca vira acao. Quando ele fala uma meta
vaga, o chat (ferramenta `propor_se_entao`) devolve um card  **Quando ___, eu ___**  pra ele escolher o gatilho com 1
toque (acordar, sentar pra estudar, chegar em casa, voltar do treino, ou uma hora) e a acao. **Ativar** grava o
combinado; o aviso dispara NO GATILHO, nao num horario aleatorio:

  acordar         <- Atalho "Bom dia" (alarme parado) -> /api/atalho/bom-dia, ou um sinal "acordei" (/api/sinal)
  chegar_casa     <- o Atalho de localizacao que ja existe (/api/atalho/local, evento "chegou" em "casa")
  voltar_treino   <- treino registrado (POST /api/treino, "treino feito" no chat, ficha concluida)
  sentar_estudar  <- /api/atalho/gatilho {"evento": "sentar_estudar"} (uma automacao do Atalhos, ex.: abrir o app de estudo)
  hora            <- o tick de 5 em 5 min (HH:MM do combinado; vale ate 3 h depois se o PC estava desligado)

O aviso e um push com o botao **Feito** (conta "+1 no teu dia") e no maximo UM por combinado por dia. Nao e o motor de
regras em texto livre (`assistente/regras.py`, "todo dia as 18h me lembra de X"): este e o caminho guiado, por
gatilho de rotina, com o card. Os dois convivem.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta

import db

log = logging.getLogger(__name__)

GATILHOS = {
    "acordar": {"rotulo": "acordar", "titulo": "Tu acordou"},
    "sentar_estudar": {"rotulo": "sentar pra estudar", "titulo": "Tu sentou pra estudar"},
    "chegar_casa": {"rotulo": "chegar em casa", "titulo": "Tu chegou em casa"},
    "voltar_treino": {"rotulo": "voltar do treino", "titulo": "Tu voltou do treino"},
    "hora": {"rotulo": "numa hora", "titulo": "Hora do combinado"},
}
GATILHOS_DE_EVENTO = tuple(g for g in GATILHOS if g != "hora")
MAX_ATIVOS = 12
TOLERANCIA_HORA = timedelta(hours=3)


def criar_tabelas(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS se_entao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meta TEXT NOT NULL,
            gatilho TEXT NOT NULL,
            hora TEXT,
            acao TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL DEFAULT (datetime('now')),
            ultimo_disparo TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS se_entao_disparos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            regra_id INTEGER NOT NULL,
            dia TEXT NOT NULL,
            disparado_em TEXT NOT NULL,
            feito_em TEXT
        )
        """
    )


def _ligado(conn) -> bool:
    """Tela Assistente > Avisos: o tipo 'se_entao' pode ser desligado sem apagar os combinados."""
    from assistente import avisos as avisos_assistente

    return avisos_assistente.esta_ligado("se_entao", conn=conn)


def _curto(valor, maximo: int) -> str:
    return " ".join(str(valor or "").split())[:maximo]


def hora_ok(h) -> str | None:
    if not isinstance(h, str) or ":" not in h:
        return None
    try:
        hh, mm = h.strip().split(":")[:2]
        hh, mm = int(hh), int(mm)
    except ValueError:
        return None
    return f"{hh:02d}:{mm:02d}" if 0 <= hh <= 23 and 0 <= mm <= 59 else None


def proposta(meta, gatilhos, acoes) -> dict | None:
    """Limpa o que a IA mandou pra montar o card (ate 4 gatilhos de evento, ate 3 acoes curtas). None = nada util."""
    meta = _curto(meta, 120)
    gs = [g for g in (gatilhos or []) if g in GATILHOS_DE_EVENTO] if isinstance(gatilhos, list) else []
    gs = list(dict.fromkeys(gs)) or list(GATILHOS_DE_EVENTO)
    ac = [_curto(a, 80) for a in (acoes or []) if _curto(a, 80)] if isinstance(acoes, list) else []
    if not meta or not ac:
        return None
    return {"meta": meta, "gatilhos": [{"id": g, "rotulo": GATILHOS[g]["rotulo"]} for g in gs[:4]], "acoes": ac[:3]}


def ativar(conn, meta, gatilho, hora, acao) -> tuple[dict | None, str | None]:
    """Grava o combinado. (regra, None) ou (None, motivo)."""
    criar_tabelas(conn)
    meta, acao = _curto(meta, 120), _curto(acao, 80)
    if gatilho not in GATILHOS or not acao:
        return None, "faltou o gatilho ou a ação"
    h = None
    if gatilho == "hora":
        h = hora_ok(hora)
        if not h:
            return None, "escolhe a hora (HH:MM)"
    if conn.execute("SELECT COUNT(*) n FROM se_entao WHERE ativo = 1").fetchone()["n"] >= MAX_ATIVOS:
        return None, f"já são {MAX_ATIVOS} combinados ativos - desliga algum antes"
    # mesmo combinado de novo = reativa o que existe, em vez de duplicar
    antigo = conn.execute(
        "SELECT id FROM se_entao WHERE gatilho = ? AND COALESCE(hora, '') = ? AND acao = ?", (gatilho, h or "", acao)).fetchone()
    if antigo:
        conn.execute("UPDATE se_entao SET ativo = 1, meta = ? WHERE id = ?", (meta, antigo["id"]))
        rid = antigo["id"]
    else:
        rid = conn.execute("INSERT INTO se_entao (meta, gatilho, hora, acao) VALUES (?, ?, ?, ?)", (meta, gatilho, h, acao)).lastrowid
    conn.commit()
    return obter(conn, rid), None


def obter(conn, regra_id: int) -> dict | None:
    criar_tabelas(conn)
    r = conn.execute("SELECT * FROM se_entao WHERE id = ?", (regra_id,)).fetchone()
    return _dict(r) if r else None


def _dict(r) -> dict:
    d = dict(r)
    d["ativo"] = bool(d["ativo"])
    d["gatilho_rotulo"] = GATILHOS.get(d["gatilho"], {}).get("rotulo", d["gatilho"])
    d["frase"] = frase(d)
    return d


def frase(r: dict) -> str:
    g = f"às {r['hora']}" if r.get("gatilho") == "hora" and r.get("hora") else GATILHOS.get(r.get("gatilho"), {}).get("rotulo", "")
    return f"Quando {g}, eu {r.get('acao', '')}".strip()


def listar(conn, so_ativos: bool = True) -> list[dict]:
    criar_tabelas(conn)
    sql = "SELECT * FROM se_entao" + (" WHERE ativo = 1" if so_ativos else "") + " ORDER BY id"
    return [_dict(r) for r in conn.execute(sql).fetchall()]


def desativar(conn, regra_id: int) -> bool:
    criar_tabelas(conn)
    n = conn.execute("UPDATE se_entao SET ativo = 0 WHERE id = ?", (regra_id,)).rowcount
    conn.commit()
    return n > 0


# ------------------------------------------------------------------ disparo


def _titulo_e_corpo(r: dict) -> tuple[str, str]:
    return GATILHOS.get(r["gatilho"], {}).get("titulo", "Combinado"), f"Combinado: {r['acao']}."


def _avisar(conn, r: dict, agora: datetime) -> bool:
    """Push com o botao Feito. Sem push configurado/sem inscricao -> False (nao conta como disparado)."""
    import push_client

    if not push_client.configurado():
        return False
    subs = db.list_push_subscriptions(conn)
    if not subs:
        return False
    titulo, corpo = _titulo_e_corpo(r)
    tag = f"se_entao-{r['id']}"
    enviou = False
    for s in subs:
        ok = push_client.enviar(json.loads(s["subscription_json"]), titulo, corpo, url="/?aba=hoje", tag=tag,
                                acoes=[{"action": "feito", "title": "Feito"}])
        if ok:
            enviou = True
        else:
            db.delete_push_subscription(conn, s["endpoint"])
    return enviou


def _registrar_disparo(conn, r: dict, agora: datetime) -> int:
    conn.execute("UPDATE se_entao SET ultimo_disparo = ? WHERE id = ?", (agora.isoformat(timespec="seconds"), r["id"]))
    rid = conn.execute(
        "INSERT INTO se_entao_disparos (regra_id, dia, disparado_em) VALUES (?, ?, ?)",
        (r["id"], agora.date().isoformat(), agora.isoformat(timespec="seconds"))).lastrowid
    conn.commit()
    return rid


def _ja_disparou_hoje(r: dict, hoje: date) -> bool:
    return str(r.get("ultimo_disparo") or "")[:10] == hoje.isoformat()


def disparar(conn, evento: str, agora: datetime | None = None, avisar=None) -> list[dict]:
    """Aconteceu `evento` (acordar, chegar_casa, voltar_treino, sentar_estudar): dispara os combinados dele, 1x por dia
    cada. Devolve os que dispararam. Nunca levanta (gatilho e extra do fluxo que o chamou)."""
    if evento not in GATILHOS_DE_EVENTO:
        return []
    try:
        agora = agora or datetime.now()
        criar_tabelas(conn)
        saida = []
        for r in listar(conn):
            if r["gatilho"] != evento or _ja_disparou_hoje(r, agora.date()):
                continue
            if not _ligado(conn):
                break
            if (avisar or _avisar)(conn, r, agora):
                _registrar_disparo(conn, r, agora)
                saida.append(r)
        return saida
    except Exception:  # noqa: BLE001
        log.exception("se_entao: disparar(%s) falhou", evento)
        return []


def verificar(conn, agora: datetime, avisar=None) -> list[tuple[str, str, str]]:
    """Tick: combinados com HORA. Dispara quando passou da hora (ate 3 h; o PC pode ter ficado desligado)."""
    try:
        criar_tabelas(conn)
        if not _ligado(conn):
            return []
        for r in listar(conn):
            if r["gatilho"] != "hora" or not r["hora"] or _ja_disparou_hoje(r, agora.date()):
                continue
            h, m = r["hora"].split(":")
            alvo = agora.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
            if alvo <= agora <= alvo + TOLERANCIA_HORA and (avisar or _avisar)(conn, r, agora):
                _registrar_disparo(conn, r, agora)
    except Exception:  # noqa: BLE001
        log.exception("se_entao: verificar falhou")
    return []


def testar(conn, regra_id: int, agora: datetime | None = None, avisar=None) -> bool:
    """Botao 'Testar': manda o aviso agora pra ele ver como chega (nao conta no dia)."""
    r = obter(conn, regra_id)
    return bool(r and (avisar or _avisar)(conn, r, agora or datetime.now()))


def marcar_feito(conn, regra_id: int, agora: datetime | None = None) -> dict | None:
    """Tocou em Feito no aviso. Devolve {titulo, feitos_hoje} pra mensagem 'Boa. +1 no teu dia.'"""
    r = obter(conn, regra_id)
    if not r:
        return None
    agora = agora or datetime.now()
    d = conn.execute(
        "SELECT id, feito_em FROM se_entao_disparos WHERE regra_id = ? AND dia = ? ORDER BY id DESC LIMIT 1",
        (regra_id, agora.date().isoformat())).fetchone()
    if d and not d["feito_em"]:
        conn.execute("UPDATE se_entao_disparos SET feito_em = ? WHERE id = ?", (agora.isoformat(timespec="seconds"), d["id"]))
        conn.commit()
    return {"titulo": r["frase"], "feitos_hoje": feitos_no_dia(conn, agora.date())}


def feitos_no_dia(conn, dia: date) -> int:
    criar_tabelas(conn)
    return conn.execute("SELECT COUNT(*) n FROM se_entao_disparos WHERE dia = ? AND feito_em IS NOT NULL", (dia.isoformat(),)).fetchone()["n"]
