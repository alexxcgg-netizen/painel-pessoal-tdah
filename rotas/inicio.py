"""Blueprint inicio - R2 (reformulação, etapa 2): uma rota agregadora pro Início.

GET /api/inicio junta, numa ida só, os dados BARATOS que a tela Início (e os
subtítulos da tela Mais) mostram: resumo de 1 linha + estado (atrasadas / tudo
em dia), o item "Agora", os 3 números (tarefas de hoje, gasto hoje, copos
d'água) e os subtítulos do "Acesso rápido".

Regras desta rota (de propósito):
- SEM IA (nada de claude_client) e SEM rede: a agenda do iCloud (CalDAV) fica de
  fora - ela é lenta/instável e a Visão do dia já a busca. "Agenda" aqui conta só
  o que é local (tarefas com horário + eventos criados pelo painel).
- Modo visitante: gasto, água e remédio saem como None (mesma regra de
  /api/summary/today e /api/saude/hoje).
- Só lê o banco (nunca grava), menos a materialização de recorrentes que toda
  rota de tarefas já faz.
"""

from __future__ import annotations

from datetime import date as _date_cls, datetime as _datetime_cls

from flask import Blueprint, jsonify

import db
import vida
from rotas._base import app_modulo

bp = Blueprint("inicio", __name__)

META_COPOS = 8


def _hora_curta(hhmm: str | None) -> str | None:
    """'09:00' -> '9h', '14:30' -> '14h30' (como se fala)."""
    if not hhmm or ":" not in hhmm:
        return None
    try:
        h, m = (int(x) for x in hhmm.split(":")[:2])
    except ValueError:
        return None
    return f"{h}h" if m == 0 else f"{h}h{m:02d}"


def montar_resumo(pendentes_hoje: int, feitas_hoje: int, proxima_hora: str | None, alguma_passou: bool) -> str:
    """Linha de resumo do hero - só fatos, frase curta."""
    total = pendentes_hoje + feitas_hoje
    if total == 0:
        return "Nada marcado pra hoje."
    if pendentes_hoje == 0:
        return f"Tudo feito hoje: {feitas_hoje} de {total}."
    frase = "1 tarefa hoje." if pendentes_hoje == 1 else f"{pendentes_hoje} tarefas hoje."
    hora = _hora_curta(proxima_hora)
    if hora:
        palavra = "A próxima" if (feitas_hoje or alguma_passou) else "A primeira"
        frase += f" {palavra} é às {hora}."
    return frase


def _itens_com_horario(conn, app, hoje: _date_cls) -> list[dict]:
    """Tarefas pendentes com horário hoje + hábitos com horário devidos hoje e
    ainda não marcados (mesmas funções da Visão do dia, sem o iCloud)."""
    itens = [dict(i) for i in app._tarefas_com_horario_hoje(conn)]
    itens += [h for h in app._habitos_do_dia_com_horario(conn, hoje) if not h.get("concluido")]
    itens.sort(key=lambda i: i["inicio"])
    return itens


def _escolher_agora(conn, itens: list[dict], agora: _datetime_cls, hoje_iso: str) -> dict | None:
    """O próximo item com horário (ou, sem nenhum futuro, o que passou mais
    recentemente - mesmo critério de _proximo_item_em_foco). Sem item com
    horário, cai na primeira tarefa pendente de hoje sem horário."""
    if itens:
        futuros = [i for i in itens if _datetime_cls.fromisoformat(i["inicio"]) >= agora]
        escolhido = futuros[0] if futuros else itens[-1]
        inicio = _datetime_cls.fromisoformat(escolhido["inicio"])
        em_texto = vida.formatar_em_quanto_tempo(inicio, agora)
        tipo = "Hábito" if escolhido["origem"] == "habito" else "Tarefa"
        return {
            "origem": escolhido["origem"],
            "id": escolhido["id"],
            "titulo": escolhido["titulo"],
            "hora": inicio.strftime("%H:%M"),
            "subtitulo": f"{tipo} · {em_texto}",
            "atrasada": em_texto == "atrasada",
        }
    row = conn.execute(
        "SELECT id, title FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL "
        "AND due_date = ? AND hora IS NULL ORDER BY created_at, id LIMIT 1",
        (hoje_iso,),
    ).fetchone()
    if row is None:
        return None
    return {
        "origem": "tarefa",
        "id": row["id"],
        "titulo": row["title"],
        "hora": None,
        "subtitulo": "Tarefa pra hoje",
        "atrasada": False,
    }


def _habitos_de_hoje(conn, app, hoje: _date_cls) -> dict:
    """'x de y hoje' - mesma conta de hábitos devidos/marcados de _contagem_dia."""
    hoje_iso = hoje.isoformat()
    ini_semana, fim_semana = app._semana_de(hoje)
    total = feitos = 0
    for h in db.list_habitos(conn):
        vezes = len(db.marcacoes_habito_no_periodo(conn, h["id"], ini_semana, fim_semana))
        if not vida.habito_devido_em(h, hoje, vezes):
            continue
        total += 1
        if db.habito_marcado(conn, hoje_iso, h["id"]):
            feitos += 1
    return {"feitos": feitos, "total": total}


def _proximo_remedio(conn, agora: _datetime_cls) -> str | None:
    # list_medicamentos_ativos descriptografa e ordena (o horario e cifrado no banco).
    agora_hhmm = agora.strftime("%H:%M")
    for m in db.list_medicamentos_ativos(conn):
        if (m["horario"] or "") >= agora_hhmm:
            return m["horario"]
    return None


def _remedios_de_hoje(conn, hoje_iso: str) -> dict:
    """'x de y hoje' (R4 - Tomei): remedios que caem hoje x instancias concluidas."""
    total = tomados = 0
    for m in db.list_medicamentos_ativos(conn):
        inst = db.instancia_do_dia_do_medicamento(conn, m, hoje_iso)
        if inst:
            total += 1
            tomados += 1 if inst["completed_at"] else 0
    return {"tomados": tomados, "total": total}


@bp.route("/api/inicio", methods=["GET"])
def inicio():
    app = app_modulo()
    hoje = app.date.today()
    agora = app.datetime.now()
    hoje_iso = hoje.isoformat()
    visitante = app._modo_visitante_ativo()
    conn = db.get_db()
    try:
        app.materializar_tarefas_recorrentes(conn)
        pendentes_hoje = conn.execute(
            "SELECT COUNT(*) AS n FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL AND due_date = ?",
            (hoje_iso,),
        ).fetchone()["n"]
        feitas_hoje = conn.execute(
            "SELECT COUNT(*) AS n FROM tasks WHERE completed_at IS NOT NULL AND recorrencia IS NULL AND due_date = ?",
            (hoje_iso,),
        ).fetchone()["n"]
        atrasadas = conn.execute(
            "SELECT COUNT(*) AS n FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL "
            "AND due_date IS NOT NULL AND due_date < ?",
            (hoje_iso,),
        ).fetchone()["n"]
        pendentes_total = conn.execute(
            "SELECT COUNT(*) AS n FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL"
        ).fetchone()["n"]

        itens = _itens_com_horario(conn, app, hoje)
        tarefas_com_hora = [i for i in itens if i["origem"] == "tarefa"]
        futuras = [i for i in tarefas_com_hora if _datetime_cls.fromisoformat(i["inicio"]) >= agora]
        proxima_hora = futuras[0]["inicio"][11:16] if futuras else None
        alguma_passou = len(futuras) < len(tarefas_com_hora)

        eventos_locais = conn.execute(
            "SELECT COUNT(*) AS n FROM eventos_criados WHERE date(inicio) = ?", (hoje_iso,)
        ).fetchone()["n"]

        gasto_hoje = gasto_mes = agua = remedio = remedios_hoje = None
        if not visitante:
            gasto_hoje = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS t FROM expenses WHERE date(created_at) = ? AND tipo = 'real'",
                (hoje_iso,),
            ).fetchone()["t"]
            gasto_mes = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS t FROM expenses WHERE substr(created_at, 1, 7) = ? AND tipo = 'real'",
                (hoje_iso[:7],),
            ).fetchone()["t"]
            agua = db.contar_hidratacao_dia(conn, hoje_iso)
            remedio = _proximo_remedio(conn, agora)
            remedios_hoje = _remedios_de_hoje(conn, hoje_iso)

        voos_futuros = conn.execute(
            "SELECT data, destino FROM voos WHERE data >= ? ORDER BY data LIMIT 1", (hoje_iso,)
        ).fetchone()
        notas = conn.execute("SELECT COUNT(*) AS n FROM notas").fetchone()["n"]

        dados = {
            "resumo": montar_resumo(pendentes_hoje, feitas_hoje, proxima_hora, alguma_passou),
            "atrasadas": atrasadas,
            "agora": _escolher_agora(conn, itens, agora, hoje_iso),
            "tarefas_hoje": {"feitas": feitas_hoje, "total": pendentes_hoje + feitas_hoje},
            "tarefas_pendentes": pendentes_total,
            "gasto_hoje": gasto_hoje,
            "gasto_mes": gasto_mes,
            "agua": None if agua is None else {"copos": agua, "meta": META_COPOS},
            "compromissos_hoje": len(tarefas_com_hora) + eventos_locais,
            "habitos": _habitos_de_hoje(conn, app, hoje),
            "proximo_remedio": remedio,
            "remedios_hoje": remedios_hoje,
            "proximo_voo": dict(voos_futuros) if voos_futuros else None,
            "notas": notas,
            "visitante": visitante,
        }
    finally:
        conn.close()
    return jsonify(dados)
