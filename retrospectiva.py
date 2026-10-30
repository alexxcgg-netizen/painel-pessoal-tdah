"""Retrospectiva do mes (lab v4, 2026-10-30, Grupo G): no comeco do mes, uma historia em tela cheia
(formato stories) com o mes que fechou. Tudo agregado do que o painel JA guarda, nada inventado:

  tarefas fechadas (e a diferenca pro mes anterior) | quilos levantados no treino ao vivo |
  horas voadas (e aerodromos novos) | recorde do mes (1RM estimado, Medalha na hora) |
  o gasto que mais cresceu | e a ultima tela pede UMA meta pro mes novo.

Cada tela so existe se tem dado de verdade (mes sem treino ao vivo = sem tela de quilos). O front
monta as telas a partir destes campos (static/js/cards-fechamento.js). Gasto e dinheiro: sai no modo
visitante (cards.CAMPOS_SENSIVEIS).

Fora de proposito: "a frase mais engracada que tu disse no chat" (pede ler e julgar o chat - nao e
fato calculado) e a narracao com a voz do ElevenLabs (gasta credito; opcional na ideia).
"""

from __future__ import annotations

import math
from datetime import date, datetime, time

import cards
import conversa_proativa as cp
import db

MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro")
JANELA_DIA1 = (time(9, 0), time(21, 0))
DIAS_DA_JANELA = 3  # PC desligado no dia 1: ainda publica ate o dia 3
GASTO_MIN_AUMENTO = 30.0  # R$: abaixo disso nao e "o gasto que mais cresceu", e variacao normal

_DIA_CONCLUSAO = "date(completed_at, '-3 hours')"


def chave_mes(ano: int, mes: int) -> str:
    return f"{ano:04d}-{mes:02d}"


def mes_anterior(ano: int, mes: int) -> tuple[int, int]:
    return (ano - 1, 12) if mes == 1 else (ano, mes - 1)


def mes_seguinte(ano: int, mes: int) -> tuple[int, int]:
    return (ano + 1, 1) if mes == 12 else (ano, mes + 1)


def _limites(ano: int, mes: int) -> tuple[str, str]:
    """[primeiro dia, ultimo dia] ISO do mes."""
    ay, am = mes_seguinte(ano, mes)
    ultimo = date(ay, am, 1).toordinal() - 1
    return date(ano, mes, 1).isoformat(), date.fromordinal(ultimo).isoformat()


def parse_mes(texto) -> tuple[int, int] | None:
    try:
        d = datetime.strptime(str(texto), "%Y-%m")
    except ValueError:
        return None
    return (d.year, d.month) if 2000 <= d.year <= 2100 else None


def mes_padrao(hoje: date) -> tuple[int, int]:
    """Pedido no chat sem dizer o mes: dia 25 em diante o mes que esta acabando; antes disso o que fechou."""
    return (hoje.year, hoje.month) if hoje.day >= 25 else mes_anterior(hoje.year, hoje.month)


def _tarefas(conn, ano: int, mes: int) -> int:
    ini, fim = _limites(ano, mes)
    return conn.execute(
        f"SELECT COUNT(*) n FROM tasks WHERE completed_at IS NOT NULL AND {_DIA_CONCLUSAO} BETWEEN ? AND ?", (ini, fim)
    ).fetchone()["n"]


def _treino(conn, ano: int, mes: int) -> dict:
    ini, fim = _limites(ano, mes)
    r = conn.execute(
        "SELECT COALESCE(SUM(volume_kg), 0) kg, COUNT(DISTINCT sessao_id) sessoes FROM treino_marcas "
        "WHERE data BETWEEN ? AND ?", (ini, fim)
    ).fetchone()
    rec = conn.execute(
        "SELECT nome, rm_est FROM treino_marcas WHERE recorde = 1 AND data BETWEEN ? AND ? "
        "ORDER BY rm_est DESC LIMIT 1", (ini, fim)
    ).fetchone()
    n_rec = conn.execute(
        "SELECT COUNT(*) n FROM treino_marcas WHERE recorde = 1 AND data BETWEEN ? AND ?", (ini, fim)
    ).fetchone()["n"]
    return {"kg": round(float(r["kg"] or 0)), "sessoes": r["sessoes"],
            "recorde": {"nome": rec["nome"], "rm": rec["rm_est"], "total": n_rec} if rec else None}


def _lugares(conn, ate_exclusivo: str | None, ini: str | None = None, fim: str | None = None) -> set[str]:
    onde, args = [], []
    if ate_exclusivo:
        onde.append("data < ?")
        args.append(ate_exclusivo)
    if ini and fim:
        onde.append("data BETWEEN ? AND ?")
        args += [ini, fim]
    sql = "SELECT origem, destino FROM voos" + (" WHERE " + " AND ".join(onde) if onde else "")
    lugares = set()
    for r in conn.execute(sql, args):
        for v in (r["origem"], r["destino"]):
            v = (v or "").strip().upper()
            if v:
                lugares.add(v)
    return lugares


def _voo(conn, ano: int, mes: int) -> dict:
    ini, fim = _limites(ano, mes)
    r = conn.execute(
        "SELECT COALESCE(SUM(horas), 0) h, COUNT(*) n FROM voos WHERE data BETWEEN ? AND ? AND horas > 0", (ini, fim)
    ).fetchone()
    novos = _lugares(conn, None, ini, fim) - _lugares(conn, ini)
    return {"horas": round(float(r["h"] or 0), 1), "voos": r["n"], "aerodromos_novos": len(novos)}


def _gasto_que_cresceu(conn, ano: int, mes: int) -> dict | None:
    def por_categoria(a, m):
        ini, fim = _limites(a, m)
        return {
            r["c"]: float(r["t"] or 0)
            for r in conn.execute(
                "SELECT category c, SUM(amount) t FROM expenses WHERE date(created_at) BETWEEN ? AND ? "
                "AND tipo = 'real' GROUP BY category", (ini, fim)
            )
        }

    atual = por_categoria(ano, mes)
    antes = por_categoria(*mes_anterior(ano, mes))
    melhor = None
    for cat, total in atual.items():
        aumento = total - antes.get(cat, 0.0)
        if aumento >= GASTO_MIN_AUMENTO and (melhor is None or aumento > melhor[1]):
            melhor = (cat, aumento, total)
    if not melhor:
        return None
    return {"categoria": str(melhor[0]), "mais": round(melhor[1]), "total": round(melhor[2])}


def metas_sugeridas(dados: dict, atrasadas: int) -> list[str]:
    """Ate 3 chips pra ultima tela, saidos do que o mes mostrou (nada generico se ha dado)."""
    m: list[str] = []
    if dados["voo"]["horas"] > 0:
        m.append(f"Voar {max(2, math.ceil(dados['voo']['horas'] * 1.2))} h")
    if atrasadas > 0:
        m.append("Zerar atrasados")
    elif dados["tarefas"] > 0:
        m.append(f"Passar de {dados['tarefas']} tarefas fechadas")
    if dados["treino"]["kg"] > 0:
        m.append("Bater um recorde no treino")
    m.append("Dormir 7 h+")
    return m[:3]


def meta_do_mes(conn, ano: int, mes: int) -> str | None:
    """A meta que ele escolheu NA retrospectiva que fechou o mes anterior a (ano, mes)."""
    return db.obter_configuracao(conn, f"meta_mes_{chave_mes(ano, mes)}") or None


def dados(conn, ano: int, mes: int, hoje: date | None = None) -> dict | None:
    """Os numeros do mes. None quando o mes nao teve NADA pra contar."""
    hoje = hoje or date.today()
    tarefas, tarefas_ant = _tarefas(conn, ano, mes), _tarefas(conn, *mes_anterior(ano, mes))
    treino, voo, gasto = _treino(conn, ano, mes), _voo(conn, ano, mes), _gasto_que_cresceu(conn, ano, mes)
    if not (tarefas or treino["kg"] or voo["horas"] or gasto):
        return None
    ay, am = mes_seguinte(ano, mes)
    base = {"tarefas": tarefas, "treino": treino, "voo": voo}
    atrasadas = sum(1 for p in cp.pendentes_ate(conn, hoje) if p["atrasada"])
    return {
        "mes": chave_mes(ano, mes), "mes_nome": MESES[mes - 1],
        "proximo_mes": chave_mes(ay, am), "proximo_nome": MESES[am - 1],
        "anterior_nome": MESES[mes_anterior(ano, mes)[1] - 1],
        "tarefas": tarefas, "tarefas_ant": tarefas_ant,
        "kg": treino["kg"], "treinos": treino["sessoes"], "recorde": treino["recorde"],
        "voo_horas": voo["horas"], "voos": voo["voos"], "aerodromos_novos": voo["aerodromos_novos"],
        "gasto_cresceu": gasto,
        "metas": metas_sugeridas(base, atrasadas),
        "meta_escolhida": meta_do_mes(conn, ay, am),
    }


def card(conn, ano: int, mes: int, hoje: date | None = None) -> dict | None:
    d = dados(conn, ano, mes, hoje)
    return cards.novo_card("retrospectiva", d) if d else None


def escolher_meta(conn, ano: int, mes: int, texto) -> str | None:
    """Grava a meta do mes SEGUINTE a (ano, mes). So aceita um dos chips que o mes ofereceu ou um
    texto curto digitado (ate 60 caracteres). Devolve o texto gravado."""
    t = " ".join(str(texto or "").split())[:60]
    if not t:
        return None
    ay, am = mes_seguinte(ano, mes)
    db.definir_configuracao(conn, f"meta_mes_{chave_mes(ay, am)}", t)
    return t


# ------------------------------------------------------------------ aviso no chat (dia 1)


def _na_janela(agora: datetime) -> bool:
    if agora.day > DIAS_DA_JANELA or agora.time() > JANELA_DIA1[1]:
        return False
    return agora.day != 1 or agora.time() >= JANELA_DIA1[0]


def avisar_mes(conn, agora: datetime) -> list[tuple[str, str, str]]:
    """Publica a retrospectiva do mes que fechou, uma vez por mes (dia 1; se o PC estava desligado,
    ate o dia 3). Devolve [(tipo, titulo, corpo)] pro push (tipo `padroes_semana`: mesmo interruptor
    do resumo da semana)."""
    if not _na_janela(agora):
        return []
    ano, mes = mes_anterior(agora.year, agora.month)
    ref = ano * 100 + mes
    if db.ja_notificado_alguma_vez(conn, "retrospectiva_chat", ref):
        return []
    c = card(conn, ano, mes, agora.date())
    db.marcar_notificado(conn, "retrospectiva_chat", ref)
    if not c:
        return []
    d = c["data"]
    texto = (f"{d['mes_nome'].capitalize()} fechou. Montei a retrospectiva do mês com o que o painel guardou: "
             "toca no card pra ver.")
    cp.publicar(conn, "retrospectiva_chat", texto, [c])
    pedacos = []
    if d["tarefas"]:
        pedacos.append(f"{d['tarefas']} {'tarefa fechada' if d['tarefas'] == 1 else 'tarefas fechadas'}")
    if d["voo_horas"]:
        pedacos.append(f"{str(d['voo_horas']).replace('.', ',')} h voadas")
    corpo = (", ".join(pedacos) + ". Toca pra ver.") if pedacos else "Toca pra ver teu mês em números."
    return [("padroes_semana", f"Retrospectiva de {d['mes_nome']}", corpo)]
