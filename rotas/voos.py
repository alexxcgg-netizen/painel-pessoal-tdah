"""Blueprint voos - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

import time
from datetime import datetime, timedelta

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import create_voo, delete_voo, get_db, list_voos
import voos as voos_module

bp = Blueprint("voos", __name__)

@bp.route("/api/voos", methods=["GET"])
def voos():
    conn = get_db()
    resultado = list_voos(conn)
    conn.close()
    return jsonify(resultado)

@bp.route("/api/voos", methods=["POST"])
def criar_voo():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _marcar_atividade = app._marcar_atividade
    _normalizar_hora = app._normalizar_hora
    date = app.date
    body = _corpo_json()
    data_str = (body.get("data") or "").strip()
    destino = (body.get("destino") or "").strip()
    origem = (body.get("origem") or "").strip() or None
    observacao = (body.get("observacao") or "").strip() or None
    horas = body.get("horas")
    hora = _normalizar_hora(body.get("hora"))

    if not destino:
        return jsonify({"error": "informe o destino"}), 400
    try:
        date.fromisoformat(data_str)
    except (ValueError, TypeError):
        return jsonify({"error": "data precisa estar em formato AAAA-MM-DD"}), 400
    if horas is not None:
        if not isinstance(horas, (int, float)) or horas <= 0:
            return jsonify({"error": "horas precisa ser um número positivo, ou omitido pra voo agendado"}), 400

    conn = get_db()
    voo_id = create_voo(conn, data_str, destino, origem, horas, observacao, hora)
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"id": voo_id, "ok": True}), 201

@bp.route("/api/voos/<int:voo_id>", methods=["DELETE"])
def apagar_voo(voo_id):
    conn = get_db()
    delete_voo(conn, voo_id)
    conn.close()
    return jsonify({"ok": True})

@bp.route("/api/voos/resumo", methods=["GET"])
def voos_resumo():
    app = app_modulo()
    _voo_com_clima = app._voo_com_clima
    date = app.date
    conn = get_db()
    todos = list_voos(conn)
    conn.close()
    hoje = date.today()
    resumo = voos_module.resumo_horas(todos, hoje)
    proximos = [_voo_com_clima(v) for v in voos_module.proximos_voos(todos, hoje)]
    dias_sem_voar = voos_module.dias_desde_ultimo_voo(todos, hoje)
    return jsonify({**resumo, "proximos": proximos, "dias_desde_ultimo_voo": dias_sem_voar})

@bp.route("/api/voos/historico", methods=["GET"])
def voos_historico():
    app = app_modulo()
    date = app.date
    conn = get_db()
    todos = list_voos(conn)
    conn.close()
    return jsonify(voos_module.historico_horas_acumuladas(todos, date.today()))


# ---- 3a leva (2026-10-14): tempo na hora do voo + horas com 1 toque ------------------------
JANELA_TAF_H = 30  # TAF cobre ~24-30 h; mais longe que isso nao tem previsao oficial
_CACHE_TAF: dict = {}
CACHE_TAF_S = 20 * 60


def _buscar_com_cache(icao: str):
    import metar

    agora = time.monotonic()
    guardado = _CACHE_TAF.get(icao)
    if guardado and agora - guardado[0] < CACHE_TAF_S:
        return guardado[1]
    bruto = metar.buscar_metar_taf(icao)
    _CACHE_TAF[icao] = (agora, bruto)
    return bruto


@bp.route("/api/voos/<int:voo_id>/tempo", methods=["GET"])
def tempo_do_voo(voo_id):
    """Vento/teto/categoria do TAF NA HORA do voo (card do voo agendado pede sozinho). Fora da
    janela do TAF, voo ja voado ou sem hora: previsao None - nunca inventa."""
    import briefing_voo

    app = app_modulo()
    conn = get_db()
    try:
        v = conn.execute("SELECT id, data, hora, origem, horas FROM voos WHERE id = ?", (voo_id,)).fetchone()
    finally:
        conn.close()
    if not v:
        return jsonify({"error": "voo não encontrado"}), 404
    if v["horas"] is not None or not v["hora"]:
        return jsonify({"ok": True, "previsao": None, "motivo": "sem_hora"})
    quando = datetime.fromisoformat(f"{v['data']}T{v['hora']}")
    agora = app._agora_brasilia().replace(tzinfo=None)
    if quando < agora - timedelta(hours=1) or quando > agora + timedelta(hours=JANELA_TAF_H):
        return jsonify({"ok": True, "previsao": None, "motivo": "fora_da_janela"})
    prev = briefing_voo.previsao_na_hora(v["origem"] or "SSBL", quando, buscar=_buscar_com_cache)
    return jsonify({"ok": True, "previsao": prev, "motivo": None if prev else "sem_taf"})


@bp.route("/api/voos/<int:voo_id>/horas", methods=["POST"])
def horas_do_voo(voo_id):
    """Chip do card "quanto deu?" - grava as horas do voo (pode trocar depois) e devolve o total
    do curso pra barra andar na hora."""
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    horas = app._corpo_json().get("horas")
    if not isinstance(horas, (int, float)) or isinstance(horas, bool) or not 0 < horas <= 12:
        return jsonify({"error": "horas precisa ser entre 0,1 e 12"}), 400
    horas = round(float(horas), 1)
    conn = get_db()
    try:
        if not conn.execute("SELECT 1 FROM voos WHERE id = ?", (voo_id,)).fetchone():
            return jsonify({"error": "voo não encontrado"}), 404
        conn.execute("UPDATE voos SET horas = ? WHERE id = ?", (horas, voo_id))
        app._marcar_atividade(conn)
        conn.commit()
        total = conn.execute(
            "SELECT COALESCE(SUM(horas), 0) t FROM voos WHERE horas IS NOT NULL AND COALESCE(tipo, '') != 'simulador'"
        ).fetchone()["t"]
    finally:
        conn.close()
    return jsonify({"ok": True, "horas": horas, "horas_min": int(round(float(total) * 60))})
