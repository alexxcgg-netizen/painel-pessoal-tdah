"""Blueprint aprendizado - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import get_db
import aprendizado

bp = Blueprint("aprendizado", __name__)


@bp.route("/api/aprendizado", methods=["GET"])
def aprendizado_status():
    """Transparencia do que o painel aprendeu do seu historico - pra nunca
    virar caixa preta: mostra o limiar em uso hoje pra cada tipo de
    cutucada, se veio do padrao ou foi aprendido, quantas amostras
    embasaram isso, e o quanto (em media) voce demora pra resolver depois
    de ser cutucado."""
    conn = get_db()
    # titulo/quem vazio nao bate com nenhum historico especifico (nenhum
    # token pra comparar), entao cai direto no caminho global - o mesmo
    # limiar_tarefa/limiar_espera usados de verdade em cada cobranca, so que
    # aqui mostrando o valor "base" (sem o ajuste fino por titulo/quem
    # especifico de uma tarefa em particular).
    dias_tarefa, info_tarefa = aprendizado.limiar_tarefa(conn, "")
    dias_espera, info_espera = aprendizado.limiar_espera(conn, "")
    conn.close()
    return jsonify(
        {
            "tarefa_parada": {"dias_atual": dias_tarefa, **info_tarefa},
            "espera_parada": {"dias_atual": dias_espera, **info_espera},
        }
    )
