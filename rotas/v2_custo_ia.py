"""Rotas da faixa V2 (Painel): card "Custo de IA" (`painel/custo-ia`).
Sessao (PIN normal - autenticacao ja e GLOBAL em app.py, sem decorator).

- GET /api/ia/uso/resumo -> gasto do mes (BRL), por funcao, projecao ate o
  fim do mes e % do teto, pra alimentar o card `templates/secoes/painel/
  custo-ia.html` (`static/js/secoes/painel/custo-ia.js`).
- GET /api/ia/uso.csv    -> mesmas linhas de `uso_ia` do mes corrente, em CSV
  (exportar).

Regra de ouro do projeto (nao duplicar calculo): este arquivo NUNCA reimplementa
cambio/teto/soma do mes - sempre chama `ia.medicao`/`ia.teto` (fonte unica ja
existente, faixa A4). Ja existia `/api/ia/custo` (app.py) pro card financeiro
antigo, baseado em `api_usage`/`resumo_custo_api` (so Anthropic) - continua
existindo, nao mexemos nele. Este endpoint novo le a tabela hibrida `uso_ia`
(Anthropic + OpenAI, ver `ia/migracao_uso_ia.py`), que e a fonte usada pelo
teto/alerta atuais (`ia/teto.py`).
"""

from __future__ import annotations

import calendar
import csv
import io
from datetime import datetime, timezone

from flask import Blueprint, Response, jsonify

import db
import ia.teto as teto
from ia.medicao import cambio_usd_brl, gasto_mes_atual_brl
from ia.migracao_uso_ia import garantir_tabela

bp = Blueprint("v2_custo_ia", __name__)


def _limite_utc_inicio_mes() -> str:
    """Mesma conta de `ia.medicao._limite_utc_inicio_mes` (privada la, sem
    reexport) - copiada aqui so pro filtro SQL local (dia 1 00:00 local,
    convertido pra UTC antes de comparar com `uso_ia.criado_em`, que e UTC
    naive). NAO reimplementa nada financeiro (cambio/soma/teto), so o mesmo
    limite de data que `gasto_mes_atual_brl()` ja usa por baixo - manter os
    dois iguais e so uma questao de nao divergir o INICIO DA JANELA que a
    query abaixo usa pra agrupar por funcao/dia, o gasto_brl em si vem sempre
    de `ia.medicao`/`ia.teto`."""
    agora_local = datetime.now().astimezone()
    inicio_mes_local = agora_local.replace(hour=0, minute=0, second=0, microsecond=0, day=1)
    return inicio_mes_local.astimezone(timezone.utc).replace(tzinfo=None).isoformat(sep=" ", timespec="seconds")


def _dias_passados_e_total_mes() -> tuple[int, int]:
    """(dias corridos do mes local ate hoje incluso, total de dias do mes
    local) - usado so pra projecao linear (gasto/dias_passados*dias_total),
    nunca pra decidir gasto/teto (isso e sempre `ia.medicao`/`ia.teto`)."""
    hoje_local = datetime.now().astimezone()
    dias_passados = hoje_local.day
    dias_total = calendar.monthrange(hoje_local.year, hoje_local.month)[1]
    return dias_passados, dias_total


def _linhas_uso_mes(conn):
    garantir_tabela(conn)
    limite = _limite_utc_inicio_mes()
    return conn.execute(
        "SELECT id, criado_em, funcao, provedor, modelo, tokens_in, tokens_out, "
        "tokens_cache_lido, tokens_cache_escrito, custo_usd, latencia_ms, ok "
        "FROM uso_ia WHERE criado_em >= ? ORDER BY criado_em ASC",
        (limite,),
    ).fetchall()


def _resumo_uso_ia() -> dict:
    conn = db.get_db()
    try:
        linhas = [dict(r) for r in _linhas_uso_mes(conn)]
        cambio = cambio_usd_brl()
        gasto_brl = gasto_mes_atual_brl()
        # Reaproveita a MESMA funcao que o teto/alerta ja usam (ia.teto),
        # nunca recalcula teto/fracao aqui (regra de nao duplicar calculo).
        teto_brl = teto._teto_mensal_brl()
        nivel = teto.nivel_alerta()
        fracao = (gasto_brl / teto_brl) if teto_brl > 0 else 0.0

        dias_passados, dias_total = _dias_passados_e_total_mes()
        projecao_brl = (gasto_brl / dias_passados) * dias_total if dias_passados > 0 else gasto_brl

        por_funcao: dict[str, dict] = {}
        por_dia: dict[str, float] = {}
        for linha in linhas:
            funcao = linha["funcao"] or "desconhecida"
            grupo = por_funcao.setdefault(
                funcao, {"funcao": funcao, "chamadas": 0, "tokens_in": 0, "tokens_out": 0, "custo_usd": 0.0}
            )
            grupo["chamadas"] += 1
            grupo["tokens_in"] += int(linha["tokens_in"] or 0)
            grupo["tokens_out"] += int(linha["tokens_out"] or 0)
            grupo["custo_usd"] += float(linha["custo_usd"] or 0.0)

            dia = (linha["criado_em"] or "")[:10]
            if dia:
                por_dia[dia] = por_dia.get(dia, 0.0) + float(linha["custo_usd"] or 0.0)

        lista_funcoes = sorted(
            (
                {
                    "funcao": g["funcao"],
                    "chamadas": g["chamadas"],
                    "tokens_in": g["tokens_in"],
                    "tokens_out": g["tokens_out"],
                    "gasto_brl": round(g["custo_usd"] * cambio, 4),
                }
                for g in por_funcao.values()
            ),
            key=lambda g: g["gasto_brl"],
            reverse=True,
        )
        lista_dias = [
            {"data": dia, "gasto_brl": round(total * cambio, 4)} for dia, total in sorted(por_dia.items())
        ]

        hoje_local = datetime.now().astimezone()
        return {
            "mes": hoje_local.strftime("%Y-%m"),
            "gasto_brl": round(gasto_brl, 4),
            "teto_brl": round(teto_brl, 4),
            "fracao_teto": round(fracao, 4),
            "nivel_alerta": nivel,
            "projecao_fim_mes_brl": round(projecao_brl, 4),
            "cambio_usd_brl": cambio,
            "total_chamadas": len(linhas),
            "por_funcao": lista_funcoes,
            "por_dia": lista_dias,
        }
    finally:
        conn.close()


@bp.route("/api/ia/uso/resumo", methods=["GET"])
def uso_ia_resumo():
    return jsonify(_resumo_uso_ia())


@bp.route("/api/ia/uso.csv", methods=["GET"])
def uso_ia_csv():
    conn = db.get_db()
    try:
        linhas = [dict(r) for r in _linhas_uso_mes(conn)]
        cambio = cambio_usd_brl()
    finally:
        conn.close()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "criado_em_utc",
            "funcao",
            "provedor",
            "modelo",
            "tokens_in",
            "tokens_out",
            "tokens_cache_lido",
            "tokens_cache_escrito",
            "custo_usd",
            "custo_brl",
            "latencia_ms",
            "ok",
        ]
    )
    for linha in linhas:
        custo_usd = float(linha["custo_usd"] or 0.0)
        writer.writerow(
            [
                linha["criado_em"],
                linha["funcao"],
                linha["provedor"],
                linha["modelo"],
                linha["tokens_in"],
                linha["tokens_out"],
                linha["tokens_cache_lido"],
                linha["tokens_cache_escrito"],
                f"{custo_usd:.6f}",
                f"{custo_usd * cambio:.6f}",
                linha["latencia_ms"],
                linha["ok"],
            ]
        )

    hoje_local = datetime.now().astimezone()
    nome_arquivo = f"uso-ia-{hoje_local.strftime('%Y-%m')}.csv"
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={nome_arquivo}"},
    )
