"""rotas/widget_ios.py - widgets nativos do iPhone (leva 05/11/2026, docs/briefings/2026-11-05-widgets-ios.md).

Tres coisas:

1. **Parear o widget por codigo.** A assinatura gratis do Sideloadly corta o App Group, entao o widget
   nao enxerga o token que o app guardou (era o "Configure a URL do painel no app"). O widget pede um
   codigo de 4 numeros aqui (`POST /api/widget/parear`, sem token), mostra o codigo na tela de inicio e
   fica perguntando (`GET /api/widget/parear/<id>`). O app, que tem o token, ve o pedido
   (`GET /api/widget/parear/pendentes`), pergunta "Liberar este widget?" com o mesmo codigo e libera
   (`POST /api/widget/parear/liberar`). Na proxima pergunta o widget recebe o token UMA vez.
   Pedido vale 10 min, no maximo 3 abertos e 12 por hora; fica so na memoria do servidor.
2. **Toque dentro do widget** (iOS 17+): marcar tarefa feita / desfazer e +1 copo d'agua.
3. **Dados novos do `/api/widget`** (agua, horas de voo, tarefas de hoje, proximo voo) - funcoes de
   coleta usadas por `rotas/n3a_widget.coletar_resumo`.

Nada aqui devolve endereco nem valor em dinheiro. O token so sai pro widget que o Alex liberou.
"""
from __future__ import annotations

import re
import secrets
import threading
import time
from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request

import db

bp = Blueprint("widget_ios", __name__)

ROTAS_COM_TOKEN = {"/api/widget/agua"}
# cada rota abaixo checa o proprio token (ou nenhum, no caso do pedido de pareamento)
PREFIXOS_COM_TOKEN = ("/api/widget/parear", "/api/widget/tarefa/")

PAR_VALIDADE_S = 10 * 60
PAR_MAX_ABERTOS = 3
PAR_MAX_POR_HORA = 12
_RE_ID = re.compile(r"^[A-Za-z0-9-]{16,64}$")
_RE_CODIGO = re.compile(r"^\d{4}$")

_trava = threading.Lock()
_pares: dict[str, dict] = {}  # id do widget -> {"codigo", "criado", "liberado"}
_inicios: list[float] = []


def _token_ok() -> bool:
    from rotas.n3a_widget import _token_widget_valido

    return _token_widget_valido()


def _corpo() -> dict:
    corpo = request.get_json(silent=True)
    return corpo if isinstance(corpo, dict) else {}


def _limpar(agora: float) -> None:
    for chave in [k for k, p in _pares.items() if agora - p["criado"] > PAR_VALIDADE_S]:
        del _pares[chave]
    _inicios[:] = [t for t in _inicios if agora - t < 3600]


def zerar_pareamentos() -> None:
    """Pros testes."""
    with _trava:
        _pares.clear()
        _inicios.clear()


@bp.route("/api/widget/parear", methods=["POST"])
def parear_pedir():
    ident = _corpo().get("id")
    if not isinstance(ident, str) or not _RE_ID.match(ident):
        return jsonify({"error": "id invalido"}), 400
    agora = time.monotonic()
    with _trava:
        _limpar(agora)
        par = _pares.get(ident)
        if par and not par["liberado"]:
            return jsonify({"codigo": par["codigo"], "expira_em_s": int(PAR_VALIDADE_S - (agora - par["criado"]))})
        abertos = [p for p in _pares.values() if not p["liberado"]]
        if len(_inicios) >= PAR_MAX_POR_HORA or len(abertos) >= PAR_MAX_ABERTOS:
            return jsonify({"error": "muitos pedidos, tenta daqui a pouco"}), 429
        usados = {p["codigo"] for p in abertos}
        codigo = f"{secrets.randbelow(10000):04d}"
        while codigo in usados:
            codigo = f"{secrets.randbelow(10000):04d}"
        _pares[ident] = {"codigo": codigo, "criado": agora, "liberado": False}
        _inicios.append(agora)
    return jsonify({"codigo": codigo, "expira_em_s": PAR_VALIDADE_S})


@bp.route("/api/widget/parear/pendentes", methods=["GET"])
def parear_pendentes():
    if not _token_ok():
        return jsonify({"error": "token invalido"}), 401
    agora = time.monotonic()
    with _trava:
        _limpar(agora)
        abertos = sorted((p for p in _pares.values() if not p["liberado"]), key=lambda p: -p["criado"])
        lista = [{"codigo": p["codigo"], "ha_s": int(agora - p["criado"])} for p in abertos]
    return jsonify({"pendentes": lista})


@bp.route("/api/widget/parear/liberar", methods=["POST"])
def parear_liberar():
    if not _token_ok():
        return jsonify({"error": "token invalido"}), 401
    codigo = _corpo().get("codigo")
    if not isinstance(codigo, str) or not _RE_CODIGO.match(codigo):
        return jsonify({"error": "codigo invalido"}), 400
    with _trava:
        _limpar(time.monotonic())
        par = next((p for p in _pares.values() if p["codigo"] == codigo and not p["liberado"]), None)
        if not par:
            return jsonify({"error": "esse codigo nao esta esperando"}), 404
        par["liberado"] = True
    return jsonify({"ok": True})


@bp.route("/api/widget/parear/<ident>", methods=["GET"])
def parear_situacao(ident):
    if not _RE_ID.match(ident or ""):
        return jsonify({"error": "id invalido"}), 400
    from rotas.n3a_widget import _token_widget_esperado

    with _trava:
        _limpar(time.monotonic())
        par = _pares.get(ident)
        if not par:
            return jsonify({"estado": "expirado"})
        if not par["liberado"]:
            return jsonify({"estado": "esperando", "codigo": par["codigo"]})
        token = _token_widget_esperado()
        if not token:
            return jsonify({"estado": "sem_token"})
        del _pares[ident]  # o token sai uma vez so
    return jsonify({"estado": "liberado", "token": token})


# --------------------------------------------------------------------------
# Toque dentro do widget (iOS 17+)
# --------------------------------------------------------------------------


@bp.route("/api/widget/tarefa/<int:task_id>", methods=["POST"])
def widget_tarefa(task_id):
    """Bolinha da lista "Hoje": {"feita": true} conclui (igual ao /api/tasks/<id>/complete), false reabre."""
    if not _token_ok():
        return jsonify({"error": "token invalido"}), 401
    feita = _corpo().get("feita")
    if not isinstance(feita, bool):
        return jsonify({"error": "feita precisa ser true ou false"}), 400
    from rotas._base import app_modulo

    app = app_modulo()
    conn = db.get_db()
    try:
        row = conn.execute("SELECT completed_at FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            return jsonify({"error": "tarefa não encontrada"}), 404
        if feita and not row["completed_at"]:
            db.complete_task(conn, task_id)
            app._marcar_atividade(conn)
            conn.commit()
        elif not feita and row["completed_at"]:
            db.reabrir_tarefa(conn, task_id)
    finally:
        conn.close()
    return jsonify({"ok": True, "feita": feita})


@bp.route("/api/widget/agua", methods=["POST"])
def widget_agua():
    """O "+" do widget da agua: um copo, o mesmo registro do resto do app."""
    if not _token_ok():
        return jsonify({"error": "token invalido"}), 401
    from rotas._base import app_modulo

    hoje = app_modulo()._agora_brasilia().date()
    conn = db.get_db()
    try:
        copos = db.registrar_hidratacao(conn, hoje.isoformat())
        return jsonify({"ok": True, "copos": copos, "meta": meta_agua(conn)})
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Coleta pro /api/widget
# --------------------------------------------------------------------------

HOJE_MAX_ITENS = 7
VOO_DIAS = 7
VOO_HORAS_FAIXA = 6


def meta_agua(conn) -> int:
    m = db.obter_configuracao(conn, "agua_meta_copos")
    return int(m) if m and str(m).isdigit() and int(m) > 0 else 8


def coletar_agua(conn, hoje: date) -> dict:
    return {"copos": db.contar_hidratacao_dia(conn, hoje.isoformat()), "meta": meta_agua(conn)}


def coletar_horas_voo(conn, hoje: date) -> dict | None:
    """Total do curso contra a meta (diario_bordo.progresso faz a conta). None sem nenhum voo com horas."""
    if not conn.execute("SELECT 1 FROM voos WHERE horas IS NOT NULL LIMIT 1").fetchone():
        return None
    import diario_bordo

    total = diario_bordo.progresso(conn, hoje)["cats"][0]
    return {"total": total["h"], "meta": total["meta"]}


def coletar_hoje(conn, hoje: date) -> list[dict]:
    """Lista "Hoje" do widget grande: tarefas de hoje (abertas e as feitas hoje) mais as atrasadas abertas.
    Modelo de tarefa repetida e tarefa arquivada ficam de fora. Ordem por hora (sem hora no fim); se
    passar do limite, sai primeiro o que ja foi feito."""
    rows = conn.execute(
        "SELECT id, title, hora, due_date, completed_at FROM tasks "
        "WHERE recorrencia IS NULL AND arquivada_em IS NULL AND ("
        " (due_date = ? AND (completed_at IS NULL OR date(completed_at, '-3 hours') = ?))"
        " OR (due_date < ? AND completed_at IS NULL))",
        (hoje.isoformat(), hoje.isoformat(), hoje.isoformat()),
    ).fetchall()
    itens = [
        {
            "id": r["id"],
            "titulo": str(r["title"] or "").strip()[:60],
            "hora": r["hora"] if r["hora"] and re.match(r"^\d{2}:\d{2}$", r["hora"]) else None,
            "feita": bool(r["completed_at"]),
            "atrasada": r["due_date"] < hoje.isoformat(),
        }
        for r in rows
    ]
    while len(itens) > HOJE_MAX_ITENS:
        feitas = [i for i in itens if i["feita"]]
        itens.remove(feitas[-1] if feitas else itens[-1])
    itens.sort(key=lambda i: (not i["atrasada"], i["hora"] or "99:99", i["id"]))
    return itens


_DIAS = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")


def _rotulo_dia(dia: date, hoje: date) -> str:
    if dia == hoje:
        return "hoje"
    if dia == hoje + timedelta(days=1):
        return "amanhã"
    return _DIAS[dia.weekday()]


def coletar_voo(conn, agora: datetime, buscar_vento=None) -> dict | None:
    """Proximo voo marcado nos proximos 7 dias. Ate 2 dias antes, entra o tempo de hora em hora no aerodromo
    de saida (Open-Meteo, clima.vento_horario): condicao e vento na hora do voo e uma faixa de 6 horas.
    Sem hora marcada ou sem previsao, so a rota e o dia."""
    import briefing_voo
    import clima

    hoje = agora.date()
    r = conn.execute(
        "SELECT id, data, hora, origem, destino FROM voos WHERE data >= ? AND data <= ? AND horas IS NULL "
        "AND COALESCE(tipo, '') != 'simulador' ORDER BY data, COALESCE(hora, '99:99'), id LIMIT 1",
        (hoje.isoformat(), (hoje + timedelta(days=VOO_DIAS)).isoformat()),
    ).fetchone()
    if not r:
        return None
    try:
        dia = date.fromisoformat(r["data"])
    except (TypeError, ValueError):
        return None
    origem = (r["origem"] or "SSBL").strip().upper()[:4] or "SSBL"
    destino = (r["destino"] or "").strip().upper()[:4] or None
    hora = r["hora"] if r["hora"] and re.match(r"^\d{2}:\d{2}$", r["hora"]) else None
    voo = {"data": r["data"], "hora": hora, "dia": _rotulo_dia(dia, hoje), "origem": origem,
           "destino": destino if destino != origem else None, "condicao": None, "codigo": None, "vento": None, "horas": []}
    if not hora or (dia - hoje).days > 2:
        return voo
    lat_lon = briefing_voo.AERODROMOS.get(origem) or briefing_voo.AERODROMOS["SSBL"]
    horas = (buscar_vento or clima.vento_horario)(lat_lon[1], lat_lon[2], dias=(dia - hoje).days + 1)
    if not horas:
        return voo
    inicio = datetime.combine(dia, datetime.strptime(hora, "%H:%M").time()).replace(minute=0)
    por_hora = {h["quando"]: h for h in horas}
    no_voo = por_hora.get(inicio.strftime("%Y-%m-%dT%H:%M"))
    if no_voo:
        voo["condicao"] = clima.descricao_codigo(no_voo["codigo"])
        voo["codigo"] = no_voo["codigo"]  # o widget escolhe o desenho do tempo por ele
        voo["vento"] = f"{no_voo['vento_dir'] // 10 * 10:03d}° {no_voo['vento_kt']} kt"
    faixa = inicio - timedelta(hours=1)
    for n in range(VOO_HORAS_FAIXA):
        h = por_hora.get((faixa + timedelta(hours=n)).strftime("%Y-%m-%dT%H:%M"))
        if h:
            voo["horas"].append({"hora": f"{(faixa + timedelta(hours=n)).hour}h", "codigo": h["codigo"],
                                 "vento_kt": h["vento_kt"]})
    return voo
