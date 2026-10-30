"""Coincidencias que tu nao viu (Laboratorio v4, Grupo D, 2026-10-30): uma vez por semana um card
cruza o que o painel ja tem (sono, treino, tarefas, gastos) e mostra um padrao com os numeros do
proprio Alex: "Nas noites com menos de 6 h, tu fechou 40% menos tarefas".

Regras (da demo aprovada):
- janela dos ultimos 30 dias (ate ontem);
- so aparece com pelo menos 3 dias de CADA lado;
- so mostra a linha em que a diferenca e relevante (>= 25% e um minimo absoluto);
- SEMPRE diz que e coincidencia nos dados, nao prova de causa;
- "Nao ligo pra isso" esconde aquele tipo de padrao pra sempre (configuracao `coincidencias_ocultas`).
Zero IA e zero chamada de rede: so conta. Nada daqui vai pra Claude, a nao ser que ele peca pelo chat
(ai o resultado da ferramenta leva so os numeros agregados, sem texto livre).
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta

import cards
import db

JANELA_DIAS = 30
MIN_DIAS_POR_LADO = 3
MIN_DIFERENCA_REL = 0.25
SONO_CURTO_H = 6.0
SONO_BOM_H = 7.0
MIN_DIF_TAREFAS = 0.5
MIN_DIF_REAIS = 10.0
CHAVE_OCULTAS = "coincidencias_ocultas"

JANELA_SEMANA = (time(9, 0), time(21, 0))  # sabado
DIA_DA_SEMANA = 5

AVISO = "É coincidência nos teus dados ({n_bom} {r_bom} × {n_ruim} {r_ruim}), não prova de causa."

TIPOS = {
    "sono": {"titulo_pior": "Noite curta pesa no teu dia.", "titulo_neutro": "O que muda no dia depois de uma noite curta.",
             "rot_bom": "7 h+", "rot_ruim": "< 6 h", "plural_bom": "noites boas", "plural_ruim": "noites curtas"},
    "treino": {"titulo_pior": "Dia sem treino rende menos.", "titulo_neutro": "O que muda nos dias em que tu treina.",
               "rot_bom": "Treinou", "rot_ruim": "Sem treino", "plural_bom": "dias de treino", "plural_ruim": "dias sem treino"},
}


def _media(v: list[float]) -> float:
    return sum(v) / len(v) if v else 0.0


def ocultas(conn) -> list[str]:
    try:
        v = json.loads(db.obter_configuracao(conn, CHAVE_OCULTAS) or "[]")
    except ValueError:
        return []
    return [x for x in v if isinstance(x, str)] if isinstance(v, list) else []


def ocultar(conn, tipo: str) -> bool:
    if tipo not in TIPOS:
        return False
    atuais = ocultas(conn)
    if tipo not in atuais:
        atuais.append(tipo)
        db.definir_configuracao(conn, CHAVE_OCULTAS, json.dumps(atuais))
    return True


def _dias(conn, hoje: date) -> dict[str, dict]:
    """Um dicionario por dia dos ultimos 30 (ate ontem): sono, treinou, tarefas, delivery, ativo."""
    ate = hoje - timedelta(days=1)
    de = hoje - timedelta(days=JANELA_DIAS)
    dias = {
        (de + timedelta(days=i)).isoformat(): {"sono": None, "treinou": False, "tarefas": 0, "delivery": 0.0}
        for i in range((ate - de).days + 1)
    }
    for r in db.list_saude_dados(conn, de.isoformat(), hoje.isoformat()):  # `ate` do db e exclusivo
        d = dias.get(r.get("data"))
        h = r.get("sono_horas")
        if d is not None and isinstance(h, (int, float)) and h > 0:
            d["sono"] = float(h)
    for r in conn.execute("SELECT DISTINCT data FROM treinos WHERE data >= ? AND data <= ?", (de.isoformat(), ate.isoformat())):
        if r["data"] in dias:
            dias[r["data"]]["treinou"] = True
    for r in conn.execute(
        "SELECT date(completed_at, '-3 hours') dia, COUNT(*) n FROM tasks "
        "WHERE completed_at IS NOT NULL AND recorrencia IS NULL AND date(completed_at, '-3 hours') BETWEEN ? AND ? "
        "GROUP BY dia",
        (de.isoformat(), ate.isoformat()),
    ):
        if r["dia"] in dias:
            dias[r["dia"]]["tarefas"] = r["n"]
    for r in conn.execute(
        "SELECT date(created_at, '-3 hours') dia, SUM(amount) v FROM expenses "
        "WHERE tipo = 'real' AND lower(category) = 'delivery' AND date(created_at, '-3 hours') BETWEEN ? AND ? GROUP BY dia",
        (de.isoformat(), ate.isoformat()),
    ):
        if r["dia"] in dias:
            dias[r["dia"]]["delivery"] = float(r["v"] or 0)
    for d in dias.values():
        d["ativo"] = bool(d["tarefas"] or d["treinou"] or d["delivery"] or d["sono"] is not None)
    return dias


def _lado(dias: dict[str, dict], tipo: str) -> tuple[list[str], list[str]]:
    """(dias do lado bom, dias do lado ruim) do tipo de padrao."""
    if tipo == "sono":
        bom = [k for k, d in dias.items() if d["sono"] is not None and d["sono"] >= SONO_BOM_H]
        ruim = [k for k, d in dias.items() if d["sono"] is not None and d["sono"] < SONO_CURTO_H]
    else:
        ativos = {k: d for k, d in dias.items() if d["ativo"]}
        bom = [k for k, d in ativos.items() if d["treinou"]]
        ruim = [k for k, d in ativos.items() if not d["treinou"]]
    return bom, ruim


def _linha(rotulo, campo, unidade, minimo, dias, bom, ruim):
    mb, mr = _media([dias[k][campo] for k in bom]), _media([dias[k][campo] for k in ruim])
    base = max(mb, mr)
    if base <= 0 or abs(mb - mr) < minimo or abs(mb - mr) / base < MIN_DIFERENCA_REL:
        return None
    return {"rotulo": rotulo, "bom": round(mb, 1), "ruim": round(mr, 1), "unidade": unidade,
            "forca": abs(mb - mr) / base, "pior_no_ruim": (mr < mb) if campo == "tarefas" else (mr > mb)}


def padroes(conn, hoje: date, incluir_ocultos: bool = False) -> list[dict]:
    """Padroes que passam nas regras, o mais forte primeiro."""
    dias = _dias(conn, hoje)
    escondidos = [] if incluir_ocultos else ocultas(conn)
    saida = []
    for tipo, t in TIPOS.items():
        if tipo in escondidos:
            continue
        bom, ruim = _lado(dias, tipo)
        if len(bom) < MIN_DIAS_POR_LADO or len(ruim) < MIN_DIAS_POR_LADO:
            continue
        linhas = [
            l for l in (
                _linha("Tarefas fechadas", "tarefas", "", MIN_DIF_TAREFAS, dias, bom, ruim),
                _linha("Delivery", "delivery", "R$ ", MIN_DIF_REAIS, dias, bom, ruim),
            ) if l
        ]
        if not linhas:
            continue
        # dia a dia (so os ultimos 14 dos dois lados) pro "Quero ver mais"
        recorte = sorted(bom + ruim)[-14:]
        detalhe = [
            {"dia": k, "lado": "bom" if k in bom else "ruim", "sono": dias[k]["sono"], "treinou": dias[k]["treinou"],
             "tarefas": dias[k]["tarefas"], "delivery": round(dias[k]["delivery"], 2)}
            for k in recorte
        ]
        tarefas = next((l for l in linhas if l["rotulo"] == "Tarefas fechadas"), None)
        pior = bool(tarefas and tarefas["pior_no_ruim"])
        saida.append({
            "tipo": tipo,
            "titulo": t["titulo_pior"] if pior else t["titulo_neutro"],
            "rot_bom": t["rot_bom"], "rot_ruim": t["rot_ruim"],
            "n_bom": len(bom), "n_ruim": len(ruim),
            "linhas": [{k: v for k, v in l.items() if k not in ("forca", "pior_no_ruim")} for l in linhas],
            "aviso": AVISO.format(n_bom=len(bom), r_bom=t["plural_bom"], n_ruim=len(ruim), r_ruim=t["plural_ruim"]),
            "detalhe": detalhe,
            "_forca": max(l["forca"] for l in linhas),
        })
    saida.sort(key=lambda p: p["_forca"], reverse=True)
    for p in saida:
        p.pop("_forca", None)
    return saida


def card(conn, hoje: date | None = None, tipo: str | None = None):
    hoje = hoje or date.today()
    ps = padroes(conn, hoje)
    if tipo:
        ps = [p for p in ps if p["tipo"] == tipo]
    if not ps:
        return None
    return cards.novo_card("coincidencia", {**ps[0], "periodo": f"últimos {JANELA_DIAS} dias"})


# ------------------------------------------------------------------ chat proativo (1x por semana)

def na_semana(conn, agora: datetime):
    """Sabado, 1x: o padrao mais forte que ainda nao foi escondido. Sem push (nao e urgencia)."""
    if agora.weekday() != DIA_DA_SEMANA or not (JANELA_SEMANA[0] <= agora.time() <= JANELA_SEMANA[1]):
        return []
    if db.ja_notificou_hoje(conn, "coincidencia_chat"):
        return []
    db.marcar_notificado(conn, "coincidencia_chat")
    c = card(conn, agora.date())
    if not c:
        return []
    import conversa_proativa

    conversa_proativa.publicar(conn, "coincidencia_chat", "Achei uma coincidência nos teus números dessa semana.", [c])
    return []


def executar_consulta(conn, hoje: date) -> dict:
    """Ferramenta do chat: so numeros agregados (nenhum texto livre do Alex)."""
    ps = padroes(conn, hoje)
    if not ps:
        return {"padroes": [], "obs": "sem dados suficientes (precisa de pelo menos 3 dias de cada lado nos ultimos 30); diga isso"}
    return {
        "padroes": [{k: p[k] for k in ("titulo", "rot_bom", "rot_ruim", "n_bom", "n_ruim", "linhas", "aviso")} for p in ps],
        "obs": "sempre diga que e coincidencia nos dados, nao prova de causa",
        "_efeito": {"entidade": "coincidencia", "consulta": True},
    }
