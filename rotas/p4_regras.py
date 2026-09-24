# rotas/p4_regras.py — faixa P4 (Fase 7): CRUD de regras (sessao/PIN, sem
# token - a autenticacao ja roda em app.before_request pra toda rota
# registrada em `app`, blueprint incluso; ver docs/agentes/fase7-regras-faixa.md).
#
# - GET    /api/p4_regras                listar
# - POST   /api/p4_regras/confirmar       cria a regra a partir do JSON do card
#            (classificador_local/regras/p4_regra.py) - so aqui a regra
#            realmente entra na tabela; o card em si nao cria nada.
# - POST   /api/p4_regras/<id>/pausar     pausa (body opcional {"ate": ISO} ou
#            {"dias": N}; sem nenhum dos dois, pausa por tempo indeterminado)
# - POST   /api/p4_regras/<id>/retomar    reativa (limpa pausada_ate)
# - DELETE /api/p4_regras/<id>            apaga
#
# Registro do blueprint (`bp`) e automatico quando a infra da Etapa 0 (X1)
# chegar na integracao - ate la este arquivo fica pronto mas nao "plugado"
# em app.py (que esta fora dos arquivos desta faixa).
from __future__ import annotations

import json
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

import db
from assistente import regras as motor

bp = Blueprint("p4_regras", __name__)

_PAUSA_INDETERMINADA = "9999-12-31 00:00:00"


def _linha_para_dict(linha) -> dict:
    d = dict(linha)
    try:
        d["json"] = json.loads(d["json"]) if d.get("json") else None
    except (TypeError, ValueError):
        d["json"] = None
    d["ativa"] = bool(d.get("ativa"))
    return d


@bp.route("/api/p4_regras", methods=["GET"])
def listar():
    conn = db.get_db()
    try:
        linhas = conn.execute(
            "SELECT id, texto_original, json, ativa, pausada_ate, criada_em, ultima_vez "
            "FROM p4_regras ORDER BY criada_em DESC, id DESC"
        ).fetchall()
        return jsonify({"regras": [_linha_para_dict(r) for r in linhas]})
    finally:
        conn.close()


@bp.route("/api/p4_regras/confirmar", methods=["POST"])
def confirmar():
    corpo = request.get_json(silent=True) or {}
    texto_original = (corpo.get("texto_original") or "").strip()
    bruto = corpo.get("json")
    if bruto is None:
        bruto = corpo.get("regra")
    if not texto_original:
        return jsonify({"error": "texto_original e obrigatorio"}), 400
    if not isinstance(bruto, dict):
        return jsonify({"error": "json (a regra interpretada) e obrigatorio"}), 400

    try:
        regra = motor.normalizar_regra(bruto)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    conn = db.get_db()
    try:
        cur = conn.execute(
            "INSERT INTO p4_regras (texto_original, json, ativa) VALUES (?, ?, 1)",
            (texto_original, json.dumps(regra, ensure_ascii=False)),
        )
        conn.commit()
        return jsonify({"ok": True, "id": cur.lastrowid}), 201
    finally:
        conn.close()


def _regra_existe(conn, regra_id: int) -> bool:
    return conn.execute("SELECT 1 FROM p4_regras WHERE id = ?", (regra_id,)).fetchone() is not None


@bp.route("/api/p4_regras/<int:regra_id>/pausar", methods=["POST"])
def pausar(regra_id):
    corpo = request.get_json(silent=True) or {}
    conn = db.get_db()
    try:
        if not _regra_existe(conn, regra_id):
            return jsonify({"error": "regra nao encontrada"}), 404

        ate = corpo.get("ate")
        if ate:
            try:
                datetime.fromisoformat(str(ate))
            except ValueError:
                return jsonify({"error": "'ate' invalido (use ISO, ex: 2026-10-01)"}), 400
            pausada_ate = str(ate)
        elif corpo.get("dias") is not None:
            try:
                dias = int(corpo["dias"])
            except (TypeError, ValueError):
                return jsonify({"error": "'dias' precisa ser inteiro"}), 400
            if dias <= 0:
                return jsonify({"error": "'dias' precisa ser maior que zero"}), 400
            pausada_ate = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            pausada_ate = _PAUSA_INDETERMINADA

        conn.execute("UPDATE p4_regras SET pausada_ate = ? WHERE id = ?", (pausada_ate, regra_id))
        conn.commit()
        return jsonify({"ok": True, "pausada_ate": pausada_ate})
    finally:
        conn.close()


@bp.route("/api/p4_regras/<int:regra_id>/retomar", methods=["POST"])
def retomar(regra_id):
    conn = db.get_db()
    try:
        if not _regra_existe(conn, regra_id):
            return jsonify({"error": "regra nao encontrada"}), 404
        conn.execute(
            "UPDATE p4_regras SET pausada_ate = NULL, ativa = 1 WHERE id = ?", (regra_id,)
        )
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@bp.route("/api/p4_regras/<int:regra_id>", methods=["DELETE"])
def apagar(regra_id):
    conn = db.get_db()
    try:
        cur = conn.execute("DELETE FROM p4_regras WHERE id = ?", (regra_id,))
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "regra nao encontrada"}), 404
        return jsonify({"ok": True})
    finally:
        conn.close()
