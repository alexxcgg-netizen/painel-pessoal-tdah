"""Parceiro de foco (leva 22/10, ideia 2 do prototipo aprovado "Ideias do Painel" -
docs/briefings/2026-10-22-leva-ideias-v3.md).

Quando ele comeca uma tarefa, o painel fica por perto: um primeiro passo de 2 min, um relogio de 10 min (15 ou
25 se ele pedir), uma pergunta no meio ("ainda nisso?") e o fecho junto. Uma sessao por vez, guardada em
`configuracoes` (chave `foco_sessao`), relogio na hora local do servidor (igual ao hiperfoco).

  - No meio o relogio ESPERA a resposta (igual ao prototipo): ainda nisso -> segue; travei -> o passo encolhe
    (`passo_menor`, que a IA ja escreveu ao abrir a sessao) em vez de cobrar; terminei -> conclui a tarefa e
    guarda quanto levou (`tasks.extras.foco_s`).
  - O aviso do meio e 1 notificacao so (`foco_meio`), nunca insiste.
  - Enquanto o relogio corre, so passa aviso critico/inegociavel (`segurando_avisos`, mesmo filtro do hiperfoco).
  - Acabou o tempo: NAO marca a tarefa sozinho (tempo cumprido nao e tarefa feita) - pergunta Terminei / Mais.
"""

from __future__ import annotations

import json
from datetime import datetime

import db

CONFIG = "foco_sessao"
PADRAO_MIN = 10
MINUTOS_OK = (10, 15, 25)
PASSO_MENOR_PADRAO = "Faz só a primeira parte disso, por 2 minutos. Mais nada."
FASES_SEGURAM = ("rodando",)


def _ler(conn) -> dict | None:
    try:
        s = json.loads(db.obter_configuracao(conn, CONFIG) or "null")
    except ValueError:
        return None
    return s if isinstance(s, dict) and s.get("id") else None


def _gravar(conn, s: dict):
    db.definir_configuracao(conn, CONFIG, json.dumps(s, ensure_ascii=False))


def _dt(texto):
    try:
        return datetime.fromisoformat(texto) if texto else None
    except (TypeError, ValueError):
        return None


def _decorrido(s: dict, agora: datetime) -> int:
    d = int(s.get("acumulado_s") or 0)
    desde = _dt(s.get("desde"))
    if desde:
        d += max(0, int((agora - desde).total_seconds()))
    if not s.get("meio_respondido"):
        d = min(d, s["total_s"] // 2)
    return min(d, s["total_s"])


def _fase(s: dict, d: int) -> str:
    if s.get("fim"):
        return s["fim"]  # "feito" | "largado"
    if not s.get("meio_respondido") and d >= s["total_s"] // 2:
        return "meio"
    if d >= s["total_s"]:
        return "acabou"
    if s.get("desde"):
        return "rodando"
    return "pausado" if d > 0 else "pronto"


def estado(conn, agora: datetime, s: dict | None = None) -> dict | None:
    s = s or _ler(conn)
    if not s:
        return None
    d = _decorrido(s, agora)
    fase = _fase(s, d)
    return {
        "id": s["id"], "task_id": s.get("task_id"), "titulo": s.get("titulo") or "",
        "passo": s.get("passo_menor") if s.get("travei") else s.get("passo") or "",
        "travei": bool(s.get("travei")), "meio_ok": bool(s.get("meio_respondido")), "total_s": s["total_s"], "decorrido_s": d,
        "fase": fase, "levou_s": s.get("levou_s"),
    }


def abrir(conn, agora: datetime, titulo: str, passo: str, passo_menor: str | None = None,
          minutos: int = PADRAO_MIN, task_id: int | None = None) -> dict:
    """A IA abre a sessao (ferramenta `parceiro_foco`); o relogio so corre no "Comecar"."""
    if minutos not in MINUTOS_OK:
        minutos = PADRAO_MIN
    s = {
        "id": int(agora.timestamp()), "task_id": task_id, "titulo": titulo.strip()[:140],
        "passo": (passo or "").strip()[:200], "passo_menor": (passo_menor or PASSO_MENOR_PADRAO).strip()[:200],
        "total_s": minutos * 60, "acumulado_s": 0, "desde": None, "meio_respondido": False, "meio_avisado": False,
        "travei": False, "fim": None, "levou_s": None,
    }
    if task_id:  # calibrador (Grupo B, Tempo): o palpite dele sobre quanto a tarefa leva, se ele deu
        try:
            import tempo

            s["estimativa_min"] = tempo.palpite_da_tarefa(conn, task_id)
        except Exception:
            s["estimativa_min"] = None
    _gravar(conn, s)
    return estado(conn, agora, s)


def _sessao(conn, sessao_id) -> dict | None:
    s = _ler(conn)
    return s if s and (sessao_id is None or s["id"] == sessao_id) else None


def comecar(conn, agora: datetime, sessao_id=None) -> dict | None:
    s = _sessao(conn, sessao_id)
    if not s or s.get("fim"):
        return None
    d = _decorrido(s, agora)
    if _fase(s, d) in ("meio", "acabou"):
        return estado(conn, agora, s)
    if not s.get("desde"):
        s["acumulado_s"] = d
        s["desde"] = agora.isoformat(timespec="seconds")
        _gravar(conn, s)
    return estado(conn, agora, s)


def pausar(conn, agora: datetime, sessao_id=None) -> dict | None:
    s = _sessao(conn, sessao_id)
    if not s or s.get("fim"):
        return None
    s["acumulado_s"] = _decorrido(s, agora)
    s["desde"] = None
    _gravar(conn, s)
    return estado(conn, agora, s)


def responder(conn, agora: datetime, resposta: str, sessao_id=None, minutos_mais: int = 5) -> dict | None:
    """ainda | travei | fim (terminei) | mais (acabou o tempo e quer mais) | largar."""
    s = _sessao(conn, sessao_id)
    if not s or s.get("fim"):
        return None
    d = _decorrido(s, agora)
    s["acumulado_s"], s["desde"] = d, None
    if resposta in ("ainda", "travei"):
        s["meio_respondido"] = True
        if resposta == "travei":
            s["travei"] = True  # o passo encolhe; o relogio espera o Continuar
            _gravar(conn, s)
            return estado(conn, agora, s)
        s["desde"] = agora.isoformat(timespec="seconds")
    elif resposta == "mais":
        s["meio_respondido"] = True
        s["total_s"] = max(s["total_s"], d) + minutos_mais * 60
        s["desde"] = agora.isoformat(timespec="seconds")
    elif resposta == "fim":
        s["fim"], s["levou_s"] = "feito", d
        if s.get("estimativa_min"):
            try:
                import tempo

                tempo.registrar_calibragem(conn, s.get("titulo"), s["estimativa_min"], d, agora)
            except Exception:
                pass
        if s.get("task_id"):
            _concluir_tarefa(conn, s["task_id"], d)
    elif resposta == "largar":
        s["fim"] = "largado"
    else:
        return None
    _gravar(conn, s)
    return estado(conn, agora, s)


def _concluir_tarefa(conn, task_id: int, segundos: int):
    t = conn.execute("SELECT extras FROM tasks WHERE id = ? AND completed_at IS NULL", (task_id,)).fetchone()
    if not t:
        return
    try:
        extras = json.loads(t["extras"]) if t["extras"] else {}
    except (TypeError, ValueError):
        extras = {}
    if not isinstance(extras, dict):
        extras = {}
    extras["foco_s"] = segundos
    conn.execute("UPDATE tasks SET completed_at = datetime('now'), extras = ? WHERE id = ?",
                 (json.dumps(extras, ensure_ascii=False), task_id))
    conn.commit()


def segurando_avisos(conn, agora: datetime) -> bool:
    """Relogio correndo = modo foco: so passa aviso critico (mesmo filtro do hiperfoco)."""
    e = estado(conn, agora)
    return bool(e and e["fase"] in FASES_SEGURAM)


def aviso_do_meio(conn, agora: datetime) -> list[tuple[str, str, str]]:
    """1 notificacao no meio, nunca insiste (conversa_proativa chama a cada tick)."""
    s = _ler(conn)
    if not s or s.get("meio_avisado") or s.get("fim"):
        return []
    if _fase(s, _decorrido(s, agora)) != "meio":
        return []
    s["meio_avisado"] = True
    _gravar(conn, s)
    return [("foco_meio", "Passou metade", f"Ainda em \"{s['titulo']}\"? Um toque responde.")]


def card(conn, agora: datetime) -> dict | None:
    import cards

    e = estado(conn, agora)
    return cards.novo_card("foco", e) if e else None
