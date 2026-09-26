"""Blueprint progresso - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from rotas._base import app_modulo
from datetime import timedelta
from db import get_db, list_diario_decisoes, list_dias_ativos, list_goals, total_cost_usd
import calculos
import streak
import vida

bp = Blueprint("progresso", __name__)

@bp.route("/api/streak", methods=["GET"])
def streak_atual():
    app = app_modulo()
    date = app.date
    conn = get_db()
    dias_ativos = list_dias_ativos(conn)
    conn.close()
    hoje = date.today()
    dias = streak.calcular_streak(dias_ativos, hoje)
    return jsonify({"dias": dias, "ativo_hoje": hoje.isoformat() in dias_ativos})

@bp.route("/api/progresso", methods=["GET"])
def progresso():
    app = app_modulo()
    _fatos_periodo = app._fatos_periodo
    date = app.date
    dias = min(max(request.args.get("dias", default=30, type=int), 7), 90)
    hoje = date.today()
    conn = get_db()
    fatos = _fatos_periodo(conn, hoje - timedelta(days=dias - 1), hoje)
    metas_lista = [
        {"titulo": g["titulo"], "pct": calculos.percentual_meta_exibicao(g["valor_guardado"], g["valor_alvo"])}
        for g in list_goals(conn)
    ]
    conn.close()
    return jsonify({**fatos, "metas": metas_lista})

@bp.route("/api/revisao-mensal", methods=["GET"])
def revisao_mensal():
    app = app_modulo()
    _revisao_do_mes = app._revisao_do_mes
    date = app.date
    mes = request.args.get("mes")
    if mes:
        try:
            primeiro = date.fromisoformat(f"{mes}-01")
            if not 2000 <= primeiro.year <= 2100:
                raise ValueError
        except ValueError:
            return jsonify({"error": "mes deve ser AAAA-MM"}), 400
        proximo = date(primeiro.year + (primeiro.month == 12), primeiro.month % 12 + 1, 1)
        ultimo = proximo - timedelta(days=1)
    else:
        primeiro, ultimo = vida.mes_anterior(date.today())
    conn = get_db()
    resultado = _revisao_do_mes(conn, primeiro, ultimo)
    conn.close()
    return jsonify(resultado)

@bp.route("/api/revisao-periodo", methods=["GET"])
def revisao_periodo():
    """Fase 5 (US-C3): revisao trimestral/anual - agrega financeiro, tarefas
    concluidas e saude reaproveitando _fatos_periodo (a mesma funcao ja usada
    pela revisao mensal em /api/revisao-mensal e por /api/progresso, nao
    duplica calculo), mais as decisoes do diario (US-C2) registradas no
    periodo."""
    app = app_modulo()
    _fatos_periodo = app._fatos_periodo
    date = app.date
    tipo = request.args.get("tipo", "trimestre")
    if tipo not in ("trimestre", "ano"):
        return jsonify({"error": "tipo precisa ser trimestre ou ano"}), 400

    hoje = date.today()
    try:
        ano = int(request.args.get("ano", hoje.year))
        if tipo == "trimestre":
            trimestre = int(request.args.get("trimestre", vida.trimestre_de(hoje)))
            primeiro, ultimo = vida.intervalo_trimestre(ano, trimestre)
        else:
            trimestre = None
            primeiro, ultimo = vida.intervalo_ano(ano)
        if not 2000 <= ano <= 2100:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "ano/trimestre invalidos"}), 400

    conn = get_db()
    fatos = _fatos_periodo(conn, primeiro, ultimo)
    decisoes_periodo = [
        d for d in list_diario_decisoes(conn) if primeiro.isoformat() <= d["data"] <= ultimo.isoformat()
    ]
    conn.close()

    return jsonify(
        {
            "tipo": tipo,
            "ano": ano,
            "trimestre": trimestre,
            "inicio": primeiro.isoformat(),
            "fim": ultimo.isoformat(),
            **fatos,
            "decisoes": decisoes_periodo,
            "decisoes_com_resultado": sum(1 for d in decisoes_periodo if d["resultado"]),
        }
    )

@bp.route("/api/uso-apps", methods=["GET"])
def uso_apps():
    app = app_modulo()
    _uso_apps = app._uso_apps
    dias = min(max(request.args.get("dias", default=7, type=int), 1), 30)
    conn = get_db()
    resultado = _uso_apps(conn, dias)
    conn.close()
    return jsonify(resultado)

@bp.route("/api/uso/total", methods=["GET"])
def uso_total():
    conn = get_db()
    total = total_cost_usd(conn)
    conn.close()
    return jsonify({"custo_usd": round(total, 4)})
