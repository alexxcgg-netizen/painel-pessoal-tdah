"""Uma cobranca por tarefa a cada 48 h, de um tipo so (leva 07/11, frente B).

Tres caminhos cutucavam a mesma tarefa parada, as vezes no mesmo dia e de novo no seguinte: o push
`tarefa_parada` (app.verificar_e_notificar), o card "Essa travou?" (`travou`, conversa_proativa) e o
card "ja foi adiada 3 vezes" (`tarefa_adiada`, rotinas_esperto). Agora todos passam por aqui:

  - `pode(conn, task_id, tipo, agora)`: falso se qualquer um dos tres ja cutucou essa tarefa nas
    ultimas 48 h; e o `travou`/`tarefa_parada` cedem pro `tarefa_adiada` quando a tarefa foi adiada
    3+ vezes e ainda nao recebeu esse card (ele e o mais util: quebrar, mudar o dia ou apagar);
  - `registrar(conn, task_id, tipo, agora)`: anota a cutucada (config `cobranca_tarefas`, 30 dias).

Nao reduz aviso de outro assunto; so espaca a cobranca da MESMA tarefa.
"""

import json
from datetime import datetime, timedelta

import db

CONFIG = "cobranca_tarefas"
JANELA_H = 48
RETENCAO_DIAS = 30
TIPOS = ("tarefa_parada", "travou", "tarefa_adiada")
LIMITE_ADIADA = 3  # mesmo de rotinas_esperto.LIMITE_ADIADA


def _carregar(conn) -> dict:
    try:
        dado = json.loads(db.obter_configuracao(conn, CONFIG) or "{}")
    except (TypeError, ValueError):
        return {}
    return dado if isinstance(dado, dict) else {}


def ultima(conn, task_id: int) -> tuple[datetime, str] | None:
    item = _carregar(conn).get(str(task_id))
    if not isinstance(item, dict):
        return None
    try:
        return datetime.fromisoformat(item["em"]), str(item.get("tipo") or "")
    except (KeyError, TypeError, ValueError):
        return None


def _adiada_vai_cobrar(conn, task_id: int) -> bool:
    """A tarefa entra (ou ja entrou) no card `tarefa_adiada`: adiada 3+ vezes, sem recorrencia, ainda nao perguntada."""
    try:
        r = conn.execute(
            "SELECT t.recorrencia, t.extras, (SELECT COUNT(*) FROM tarefas_adiadas a WHERE a.task_id = t.id) AS n "
            "FROM tasks t WHERE t.id = ?", (task_id,)).fetchone()
    except Exception:  # banco sem a tabela (teste antigo)
        return False
    if not r or r["recorrencia"] or (r["n"] or 0) < LIMITE_ADIADA:
        return False
    try:
        ex = json.loads(r["extras"]) if r["extras"] else {}
    except (TypeError, ValueError):
        ex = {}
    return not (isinstance(ex, dict) and ex.get("adiada3"))


def pode(conn, task_id: int, tipo: str, agora: datetime | None = None) -> bool:
    agora = agora or datetime.now()
    u = ultima(conn, task_id)
    if u and agora - u[0] < timedelta(hours=JANELA_H):
        return False
    if tipo in ("travou", "tarefa_parada") and _adiada_vai_cobrar(conn, task_id):
        return False  # o card de adiada fala dela (e o mais util)
    return True


def registrar(conn, task_id: int, tipo: str, agora: datetime | None = None) -> None:
    agora = agora or datetime.now()
    dado = _carregar(conn)
    limite = agora - timedelta(days=RETENCAO_DIAS)
    limpo = {}
    for k, v in dado.items():
        try:
            if isinstance(v, dict) and datetime.fromisoformat(v["em"]) >= limite:
                limpo[k] = v
        except (KeyError, TypeError, ValueError):
            continue
    limpo[str(task_id)] = {"em": agora.isoformat(timespec="minutes"), "tipo": tipo}
    db.definir_configuracao(conn, CONFIG, json.dumps(limpo))
