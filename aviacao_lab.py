"""Laboratorio v4, Grupo F (Aviacao) - 30/10/2026 (docs/briefings/2026-10-30-lab-v4-aviacao.md).

Seis ideias que ele votou "quero", todas em cima do que o painel ja guarda (voos, diario de bordo, quiz):
radar de validades, previsao do cheque, banca por caderno, voo de cadeira, vento na pista e passaporte.
Conta pura em Python, nunca pela IA.

REGRA FORTE do Alex: termo/regra de aviacao so com fonte conferida. O que NAO foi conferido fica
configuravel e marcado "nao conferido", nunca inventado:
  - validade do CMA (RBAC 67): ele digita a data impressa no CMA, o painel nao calcula;
  - pista de SSBL: cabeceiras 01/19 (o Alex confirmou em 04/11/2026); a declinacao magnetica (~20,6 W) vem de
    fonte de terceiros e, enquanto ele nao confirmar, a pista segue marcada como
    "nao conferido" ate ele confirmar no AISWEB/ROTAER (ou corrigir os numeros);
  - tempo de prova dos cadernos da banca: so Navegacao (100 min) esta conferido;
  - "horas em comando" do RBAC 61.101: o painel nao sabe a funcao a bordo de cada hora, entao nao projeta.
Conferido (briefing 2026-10-28, secao 3): 150 h no curso homologado, 20 h de navegacao (uma de 300 NM, 2 pousos
completos fora da origem), 10 h de instrumentos (ate 5 em simulador), 5 h noturnas; endosso pro cheque 30 dias;
licenca provisoria 90 dias; banca 5 cadernos x 20 questoes, 70% em cada, segunda epoca em ate 90 dias;
inscricao na FGV cai se nao agendar em 60 dias; vento do METAR em graus verdadeiros, pista em magneticos.
"""

from __future__ import annotations

import json
import math
import re
import time
from datetime import date, timedelta

import db
import diario_bordo
import rota_voo

DIAS_MES = 30.4375
MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def _json_config(conn, chave, padrao):
    try:
        v = json.loads(db.obter_configuracao(conn, chave) or "")
    except (TypeError, ValueError):
        return padrao
    return v if isinstance(v, type(padrao)) else padrao


def _mes_ano(d: date) -> str:
    return f"{MESES[d.month - 1]}/{d.year}"


def _num_config(conn, chave) -> float | None:
    try:
        v = float(db.obter_configuracao(conn, chave) or "")
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


# ============================================================================ radar de validades
# chave, nome, modo (vence = a data digitada JA e o vencimento; inicio = vencimento = data + dias), dias, verbo, ajuda
PRAZOS = (
    ("cma", "CMA", "vence", None, "vence",
     "A data de validade que está impressa no teu CMA. A regra de validade por idade (RBAC 67) eu não conferi, "
     "por isso o painel não calcula: tu digita a data."),
    ("habilitacao", "Habilitação", "vence", None, "vence",
     "A data de validade da habilitação como está na tua licença ou na CIV."),
    ("endosso", "Endosso pro cheque", "inicio", 30, "vale até",
     "Data do último voo de preparação com o endosso do instrutor. O endosso vale 30 dias."),
    ("provisoria", "Licença provisória", "inicio", 90, "vale até",
     "Data em que saiu a licença provisória. Ela vale 90 dias."),
    ("fgv", "Inscrição FGV: agendar a prova", "inicio", 60, "cai em",
     "Data da inscrição na FGV. A inscrição cai se tu não agendar a prova em 60 dias."),
    ("segunda_epoca", "Segunda época da banca", "inicio", 90, "vale até",
     "Data em que tu não passou na banca. A segunda época é uma vez só, em até 90 dias."),
)
CIV_JANELA_DIAS = 14


def prazos_salvos(conn) -> dict:
    bruto = _json_config(conn, "aviacao_prazos", {})
    saida = {}
    for chave, *_ in PRAZOS:
        v = bruto.get(chave)
        try:
            saida[chave] = date.fromisoformat(v).isoformat() if v else None
        except (TypeError, ValueError):
            saida[chave] = None
    return saida


def salvar_prazo(conn, chave: str, valor) -> dict:
    """`valor` = 'AAAA-MM-DD' ou None/'' pra apagar. Levanta ValueError (mensagem pro 400)."""
    if chave not in {p[0] for p in PRAZOS}:
        raise ValueError("prazo desconhecido")
    atual = prazos_salvos(conn)
    if valor in (None, ""):
        atual[chave] = None
    else:
        try:
            atual[chave] = date.fromisoformat(str(valor)).isoformat()
        except ValueError:
            raise ValueError("data precisa estar em formato AAAA-MM-DD") from None
    db.definir_configuracao(conn, "aviacao_prazos", json.dumps({k: v for k, v in atual.items() if v}))
    return atual


def _tom_prazo(dias: int) -> str:
    return "perigo" if dias <= 7 else "alerta" if dias <= 30 else "ok"


def civ_pendentes(conn, hoje: date) -> list[dict]:
    """Voos dos ultimos dias que ele ainda nao confirmou na CIV (o instrutor lanca; sem a confirmacao dele no
    Super App o voo nao conta). Voo importado da propria CIV ja esta confirmado."""
    return [dict(r) for r in conn.execute(
        "SELECT id, data FROM voos WHERE horas IS NOT NULL AND COALESCE(tipo, '') != 'simulador' "
        "AND COALESCE(fonte, '') != 'civ' AND civ_confirmada IS NULL AND data <= ? AND data >= ? "
        "ORDER BY data DESC, id DESC LIMIT 5",
        (hoje.isoformat(), (hoje - timedelta(days=CIV_JANELA_DIAS)).isoformat()),
    ).fetchall()]


def confirmar_civ(conn, voo_id: int, confirmada: bool = True) -> bool:
    if not conn.execute("SELECT 1 FROM voos WHERE id = ?", (voo_id,)).fetchone():
        return False
    conn.execute("UPDATE voos SET civ_confirmada = ? WHERE id = ?", (1 if confirmada else None, voo_id))
    return True


def radar(conn, hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    salvos = prazos_salvos(conn)
    itens = []
    for chave, nome, modo, dias_prazo, verbo, _ajuda in PRAZOS:
        d = salvos.get(chave)
        if not d:
            continue
        base = date.fromisoformat(d)
        vence = base if modo == "vence" else base + timedelta(days=dias_prazo)
        n = (vence - hoje).days
        if n < 0:
            detalhe = f"{'venceu' if verbo == 'vence' else 'acabou'} em {vence.strftime('%d/%m/%Y')}"
        else:
            detalhe = f"{verbo} {vence.strftime('%d/%m/%Y')}"
        itens.append({"chave": chave, "nome": nome, "vence": vence.isoformat(), "dias": n, "detalhe": detalhe,
                      "tom": _tom_prazo(n), "pendente": False, "voo_id": None, "verbo": verbo})
    for v in civ_pendentes(conn, hoje):
        dia = date.fromisoformat(v["data"])
        itens.append({"chave": f"civ{v['id']}", "nome": f"Confirmar o voo de {dia.strftime('%d/%m')} na CIV",
                      "vence": None, "dias": 0, "detalhe": "o instrutor lançou? Confirma no Super App",
                      "tom": "perigo", "pendente": True, "voo_id": v["id"], "verbo": None})
    itens.sort(key=lambda i: (not i["pendente"], i["dias"]))
    campos = [{"chave": c, "nome": n, "modo": m, "dias": d, "ajuda": a, "valor": salvos.get(c)}
              for c, n, m, d, _v, a in PRAZOS]
    return {"hoje": hoje.isoformat(), "itens": itens, "campos": campos,
            "fonte": "RBAC 61 Emenda 16 (61.13, 61.19, 61.99); IS 00-003 Rev. H; manual do Super App"}


def card_radar(conn, hoje: date | None = None) -> dict:
    import cards

    return cards.novo_card("radar_validades", radar(conn, hoje), [cards.acao_abrir_aba("aviacao", "Abrir Aviação")])


def avisos_prazos(conn, agora) -> list[tuple[str, str, str]]:
    """60/30/7 dias de cada prazo que ele digitou: card no chat + push, uma vez por marco por vencimento."""
    import cards
    import conversa_proativa as cp
    import vida

    saida = []
    if not cp._na_janela(agora, cp.JANELA_DIA):
        return saida
    hoje = agora.date()
    r = radar(conn, hoje)
    for it in r["itens"]:
        if it["pendente"]:
            continue
        marco = cards.marco_documento(it["dias"])
        if marco is None:
            continue
        ref = vida.id_estavel("prazo_aviacao", it["chave"], it["vence"], marco)
        if db.ja_notificado_alguma_vez(conn, "prazo_aviacao", ref):
            continue
        db.marcar_notificado(conn, "prazo_aviacao", ref)
        quando = "hoje" if it["dias"] == 0 else "amanhã" if it["dias"] == 1 else f"em {it['dias']} dias"
        texto = f"{it['nome']}: {it['detalhe']} ({quando})."
        cp.publicar(conn, "prazo_aviacao_chat", texto, [cards.novo_card("radar_validades", r, [
            cards.acao_abrir_aba("aviacao", "Abrir Aviação")])])
        saida.append(("prazo_aviacao", "Prazo de aviação", texto))
    conn.commit()
    return saida


# ============================================================================ previsao do cheque
JANELA_RITMO_DIAS = 28
ORDEM_REQ = ("total", "navegacao", "instrumentos", "noturno")


def _horas_janela(conn, desde: date, ate: date) -> dict:
    """Horas REAIS (simulador fora) por categoria nas ultimas semanas - mesma classificacao do diario."""
    rows = conn.execute(
        "SELECT origem, destino, escalas, horas, tipo, natureza, noturno FROM voos "
        "WHERE horas IS NOT NULL AND data >= ? AND data <= ?",
        (desde.isoformat(), ate.isoformat()),
    ).fetchall()
    reais = [r for r in rows if (r["tipo"] or "") != "simulador"]
    return {
        "total": sum(float(r["horas"]) for r in reais),
        "navegacao": sum(float(r["horas"]) for r in reais if diario_bordo._eh_navegacao(r)),
        "noturno": sum(float(r["horas"]) for r in reais if r["noturno"]),
        "instrumentos": sum(float(r["horas"]) for r in reais if r["natureza"] == "instrumentos"),
    }


def previsao_cheque(conn, hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    prog = diario_bordo.progresso(conn, hoje)
    cats = {c["chave"]: c for c in prog["cats"]}
    janela = _horas_janela(conn, hoje - timedelta(days=JANELA_RITMO_DIAS - 1), hoje)
    reqs = []
    for k in ORDEM_REQ:
        c = cats[k]
        falta = round(max(0.0, c["meta"] - c["h"]), 1)
        ritmo = round(janela[k] / JANELA_RITMO_DIAS * DIAS_MES, 1)
        data = None
        if falta > 0 and ritmo > 0:
            data = hoje + timedelta(days=math.ceil(falta / ritmo * DIAS_MES))
        reqs.append({
            "chave": k, "nome": "Totais" if k == "total" else c["nome"], "h": c["h"], "meta": c["meta"],
            "falta": falta, "ritmo_mes": ritmo, "fechou": falta <= 0,
            "data": data.isoformat() if data else None, "rotulo": _mes_ano(data) if data else None,
        })
    abertos = [r for r in reqs if not r["fechou"]]
    sem_ritmo = [r for r in abertos if r["data"] is None]
    gargalo = None
    if sem_ritmo:
        gargalo = max(sem_ritmo, key=lambda r: r["falta"] / r["meta"])
    elif abertos:
        gargalo = max(abertos, key=lambda r: r["data"])
    outras = [r for r in abertos if r is not gargalo]
    datas_outras = [r["data"] for r in outras if r["data"]]
    data_sem_gargalo = max(datas_outras) if datas_outras and len(datas_outras) == len(outras) else (
        hoje.isoformat() if not outras else None)
    data_cheque = None
    if abertos and not sem_ritmo:
        data_cheque = max(r["data"] for r in abertos)
    valor_hora = _num_config(conn, "aviacao_valor_hora")
    horas_a_voar = round(max((r["falta"] for r in reqs), default=0.0), 1)
    sim = None
    noturno = next(r for r in reqs if r["chave"] == "noturno")
    if not noturno["fechou"]:
        outras_abertas = [r for r in abertos if r is not noturno]
        datas = [r["data"] for r in outras_abertas if r["data"]]
        sim = {"falta": noturno["falta"], "atual_mes": noturno["ritmo_mes"],
               "outras_sem_ritmo": any(r["data"] is None for r in outras_abertas),
               "outras_max": max(datas) if datas else None}
    ritmo_total = reqs[0]["ritmo_mes"]
    return {
        "hoje": hoje.isoformat(), "dias_mes": DIAS_MES, "ritmo_mes": ritmo_total, "janela_dias": JANELA_RITMO_DIAS,
        "requisitos": reqs, "gargalo": gargalo["chave"] if gargalo else None,
        "gargalo_sem_ritmo": bool(gargalo and gargalo["data"] is None),
        "data_cheque": data_cheque, "rotulo_cheque": _mes_ano(date.fromisoformat(data_cheque)) if data_cheque else None,
        "rotulo_sem_gargalo": _mes_ano(date.fromisoformat(data_sem_gargalo)) if data_sem_gargalo else None,
        "tudo_fechado": not abertos, "sem_ritmo_total": ritmo_total <= 0 and not reqs[0]["fechou"],
        "simulacao_noturno": sim, "horas_a_voar": horas_a_voar, "valor_hora": valor_hora,
        "custo": round(horas_a_voar * valor_hora, 2) if valor_hora else None,
        "lembrete_navegacao": "A navegação de 20 h inclui uma de 300 NM, com 2 pousos completos fora da origem.",
        "fonte": "RBAC 61.101 (Emenda 16), curso homologado. Em comando: o painel não sabe a função a bordo, confere na CIV.",
    }


def salvar_valor_hora(conn, valor) -> float | None:
    if valor in (None, ""):
        db.definir_configuracao(conn, "aviacao_valor_hora", "")
        return None
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not 0 < valor <= 100000:
        raise ValueError("valor da hora precisa ser um número positivo")
    db.definir_configuracao(conn, "aviacao_valor_hora", str(round(float(valor), 2)))
    return round(float(valor), 2)


def card_previsao_cheque(conn, hoje: date | None = None) -> dict:
    import cards

    return cards.novo_card("previsao_cheque", previsao_cheque(conn, hoje), [cards.acao_abrir_aba("aviacao", "Abrir Aviação")])


# ============================================================================ banca por caderno
# sigla, nome, tema do quiz que alimenta as revisoes (so existem 3 temas no quiz de hoje)
CADERNOS = (
    ("REG", "Regulamentos", "Regulamentacao (RBAC/RBHA)"),
    ("MET", "Meteorologia", "Meteorologia aeronautica"),
    ("NAV", "Navegação", "Navegacao"),
    ("TV", "Teoria de voo", None),
    ("CTA", "Conhecimentos técnicos", None),
)
QUESTOES_PROVA = 20
MINIMO_PCT = 70
PRONTO_PCT = 80
PRONTO_SEGUIDOS = 3
TEMPO_CONFERIDO = {"NAV": 100}  # IS 00-003 Rev. H: so a navegacao tem o tempo conferido
REVISOES_POR_VEZ = 3


def tempos_banca(conn) -> dict:
    """Tempo de prova por caderno: 100 min de Navegacao (conferido) + o que ele mesmo digitou."""
    extra = _json_config(conn, "aviacao_banca_tempos", {})
    saida = {}
    for sigla, *_ in CADERNOS:
        if sigla in TEMPO_CONFERIDO:
            saida[sigla] = {"min": TEMPO_CONFERIDO[sigla], "conferido": True}
        elif isinstance(extra.get(sigla), int) and 0 < extra[sigla] <= 600:
            saida[sigla] = {"min": extra[sigla], "conferido": False}
        else:
            saida[sigla] = {"min": None, "conferido": False}
    return saida


def salvar_tempo_banca(conn, sigla: str, minutos) -> None:
    if sigla not in {c[0] for c in CADERNOS} or sigla in TEMPO_CONFERIDO:
        raise ValueError("caderno inválido (o tempo da Navegação já está conferido)")
    extra = _json_config(conn, "aviacao_banca_tempos", {})
    if minutos in (None, ""):
        extra.pop(sigla, None)
    else:
        if isinstance(minutos, bool) or not isinstance(minutos, int) or not 0 < minutos <= 600:
            raise ValueError("minutos precisa ser um inteiro entre 1 e 600")
        extra[sigla] = minutos
    db.definir_configuracao(conn, "aviacao_banca_tempos", json.dumps(extra))


def registrar_simulado(conn, sigla: str, acertos, hoje: date | None = None) -> int:
    if sigla not in {c[0] for c in CADERNOS}:
        raise ValueError("caderno inválido")
    if isinstance(acertos, bool) or not isinstance(acertos, int) or not 0 <= acertos <= QUESTOES_PROVA:
        raise ValueError(f"acertos precisa ser um inteiro entre 0 e {QUESTOES_PROVA}")
    hoje = hoje or date.today()
    cur = conn.execute("INSERT INTO banca_simulados (caderno, data, acertos, total) VALUES (?, ?, ?, ?)",
                       (sigla, hoje.isoformat(), acertos, QUESTOES_PROVA))
    return cur.lastrowid


def apagar_simulado(conn, simulado_id: int) -> bool:
    return conn.execute("DELETE FROM banca_simulados WHERE id = ?", (simulado_id,)).rowcount > 0


def _revisoes_vencidas(conn, hoje: date) -> tuple[list[dict], int]:
    """As perguntas do quiz que voltam hoje (Leitner: erro volta amanha, acerto em 3, 7, 14... dias). Leitura
    pura: nao marca nada como perguntada."""
    import estudo_quiz

    estudo_quiz.criar_tabela(conn)
    total = conn.execute("SELECT COUNT(*) n FROM estudo_perguntas WHERE proxima_revisao IS NOT NULL "
                         "AND proxima_revisao <= ?", (hoje.isoformat(),)).fetchone()["n"]
    ids = [r["id"] for r in conn.execute(
        "SELECT id FROM estudo_perguntas WHERE proxima_revisao IS NOT NULL AND proxima_revisao <= ? "
        "ORDER BY proxima_revisao, caixa, id LIMIT ?", (hoje.isoformat(), REVISOES_POR_VEZ)).fetchall()]
    saida = []
    for i in ids:
        p = estudo_quiz._linha(conn, i)
        if not p or not p["alternativas"]:
            continue
        sigla = next((c[0] for c in CADERNOS if c[2] == p["tema"]), None)
        dia = (p.get("respondida_em") or "")[:10]
        saida.append({
            "id": p["id"], "sigla": sigla, "enunciado": p["enunciado"],
            "resposta": p["alternativas"][p["correta"]] if 0 <= p["correta"] < len(p["alternativas"]) else "",
            "explicacao": p["explicacao"], "errou_em": dia if (p.get("ultimo_acerto") == 0 and dia) else None,
        })
    return saida, total


def revisar(conn, pergunta_id: int, acertou: bool, hoje: date | None = None) -> dict:
    import estudo_quiz

    hoje = hoje or date.today()
    p = estudo_quiz._linha(conn, pergunta_id)
    if not p:
        raise ValueError("não achei essa pergunta")
    caixa, proxima = estudo_quiz.agendar(p["caixa"], bool(acertou), hoje)
    conn.execute(
        "UPDATE estudo_perguntas SET caixa = ?, proxima_revisao = ?, acertos = acertos + ?, erros = erros + ?, "
        "ultimo_acerto = ?, respondida_em = ? WHERE id = ?",
        (caixa, proxima.isoformat(), int(bool(acertou)), int(not acertou), int(bool(acertou)), estudo_quiz._agora(),
         p["id"]),
    )
    dias = (proxima - hoje).days
    return {"proxima_revisao": proxima.isoformat(), "dias": dias,
            "texto": "Volta amanhã." if dias == 1 else f"Volta daqui a {dias} dias."}


def banca(conn, hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    tempos = tempos_banca(conn)
    cads = []
    for sigla, nome, tema in CADERNOS:
        rows = conn.execute(
            "SELECT id, acertos, total, data FROM banca_simulados WHERE caderno = ? ORDER BY data DESC, id DESC LIMIT ?",
            (sigla, PRONTO_SEGUIDOS),
        ).fetchall()
        pcts = [round(100 * r["acertos"] / (r["total"] or QUESTOES_PROVA)) for r in reversed(rows)]
        ultimo = pcts[-1] if pcts else None
        cads.append({
            "sigla": sigla, "nome": nome, "tempo_min": tempos[sigla]["min"], "tempo_conferido": tempos[sigla]["conferido"],
            "ultimos": pcts, "ultimo": ultimo, "ultimo_id": rows[0]["id"] if rows else None,
            "pronto": len(pcts) >= PRONTO_SEGUIDOS and all(p >= PRONTO_PCT for p in pcts),
            "risco": ultimo is not None and ultimo < MINIMO_PCT, "tem_quiz": tema is not None,
        })
    revisao, vencidas = _revisoes_vencidas(conn, hoje)
    # o caderno com menos folga em cima do 70% (ou sem nenhum simulado) vem pro destaque
    foco = next((c["sigla"] for c in sorted(
        cads, key=lambda c: (c["ultimo"] is None, c["ultimo"] if c["ultimo"] is not None else 0)) if c["ultimo"] is not None
        and not c["pronto"]), None)
    return {
        "hoje": hoje.isoformat(), "cadernos": cads, "revisao": revisao, "vencidas": vencidas,
        "foco": foco, "questoes": QUESTOES_PROVA, "minimo": MINIMO_PCT, "pronto_pct": PRONTO_PCT,
        "pronto_seguidos": PRONTO_SEGUIDOS,
        "fonte": "IS 00-003 Rev. H: 5 cadernos de 20 questões, 70% em cada. Só o tempo da Navegação (100 min) está conferido.",
    }


def card_banca(conn, hoje: date | None = None) -> dict:
    import cards

    return cards.novo_card("banca", banca(conn, hoje), [cards.acao_abrir_aba("aviacao", "Abrir Aviação")])


# ============================================================================ voo de cadeira
PASSOS_PADRAO = (
    ("Antes de entrar na pista",
     "Fala o briefing de decolagem: pista em uso, vento e o que tu faz se o motor falhar antes da rotação."),
    ("Rolagem", "Fala os callouts da corrida de decolagem, na ordem em que tu faz."),
    ("Subida", "Faz o flow depois da decolagem, item por item."),
    ("Saída do circuito", "Fala a chamada de rádio de saída, do jeito que tu diria no ar."),
)
ROTEIRO_MAX_PASSOS = 8
NADA_TRAVOU = "Nada, foi liso"


def roteiro(conn) -> tuple[list[dict], bool]:
    """(passos, personalizado). Os textos padrao so mandam ele FALAR cada etapa (sem afirmar procedimento): o
    conteudo certo e o do instrutor/manual da aeronave, que ele pode escrever aqui."""
    proprio = _json_config(conn, "aviacao_chair_roteiro", [])
    passos = [{"titulo": str(p.get("titulo") or "")[:60], "texto": str(p.get("texto") or "")[:400]}
              for p in proprio if isinstance(p, dict) and p.get("titulo") and p.get("texto")][:ROTEIRO_MAX_PASSOS]
    if passos:
        return passos, True
    return [{"titulo": t, "texto": x} for t, x in PASSOS_PADRAO], False


def salvar_roteiro(conn, passos) -> int:
    if not isinstance(passos, list) or len(passos) > ROTEIRO_MAX_PASSOS:
        raise ValueError(f"manda uma lista de até {ROTEIRO_MAX_PASSOS} passos")
    limpos = []
    for p in passos:
        if not isinstance(p, dict):
            raise ValueError("cada passo precisa de título e texto")
        titulo, texto = str(p.get("titulo") or "").strip(), str(p.get("texto") or "").strip()
        if not titulo or not texto:
            raise ValueError("cada passo precisa de título e texto")
        limpos.append({"titulo": titulo[:60], "texto": texto[:400]})
    db.definir_configuracao(conn, "aviacao_chair_roteiro", json.dumps(limpos, ensure_ascii=False))
    return len(limpos)


def _travou_ultimo(conn) -> list[str]:
    r = conn.execute("SELECT travou FROM chair_flying ORDER BY id DESC LIMIT 1").fetchone()
    if not r:
        return []
    try:
        v = json.loads(r["travou"])
    except (TypeError, ValueError):
        return []
    return [str(x) for x in v if isinstance(x, str) and x != NADA_TRAVOU]


def _proximo_voo(conn, hoje: date) -> dict | None:
    r = conn.execute(
        "SELECT id, data, hora, origem, destino, escalas FROM voos WHERE data >= ? AND horas IS NULL "
        "AND COALESCE(tipo, '') != 'simulador' ORDER BY data, COALESCE(hora, ''), id LIMIT 1",
        (hoje.isoformat(),),
    ).fetchone()
    return dict(r) if r else None


def chair_flying(conn, hoje: date | None = None, voo_id: int | None = None) -> dict:
    hoje = hoje or date.today()
    passos, proprio = roteiro(conn)
    travou = _travou_ultimo(conn)
    # onde travou da ultima vez vem primeiro (a ordem do resto nao muda)
    primeiros = [p for p in passos if p["titulo"] in travou]
    passos = primeiros + [p for p in passos if p["titulo"] not in travou]
    v = None
    if voo_id is not None:
        r = conn.execute("SELECT id, data, hora, origem, destino, escalas FROM voos WHERE id = ?", (voo_id,)).fetchone()
        v = dict(r) if r else None
    v = v or _proximo_voo(conn, hoje)
    voo = None
    if v:
        rota = rota_voo.montar(v["origem"], v["escalas"], v["destino"], v["hora"])
        voo = {"id": v["id"], "data": v["data"], "hora": v["hora"], "icao": rota["paradas"][0]["icao"],
               "rota": None if rota["local"] else " → ".join(p["icao"] for p in rota["paradas"])}
    return {
        "hoje": hoje.isoformat(), "voo": voo, "passos": passos, "personalizado": proprio,
        "comeca_por": [p["titulo"] for p in primeiros], "chips": [p["titulo"] for p in passos] + [NADA_TRAVOU],
        "nada": NADA_TRAVOU,
    }


def registrar_chair(conn, voo_id, travou, hoje: date | None = None) -> int:
    passos, _ = roteiro(conn)
    validos = {p["titulo"] for p in passos}
    if not isinstance(travou, list) or len(travou) > ROTEIRO_MAX_PASSOS + 1:
        raise ValueError("travou precisa ser uma lista")
    limpo = []
    for t in travou:
        if t == NADA_TRAVOU:
            continue
        if t not in validos:
            raise ValueError("passo desconhecido")
        if t not in limpo:
            limpo.append(t)
    cur = conn.execute("INSERT INTO chair_flying (voo_id, data, travou) VALUES (?, ?, ?)",
                       (voo_id if isinstance(voo_id, int) else None, (hoje or date.today()).isoformat(),
                        json.dumps(limpo, ensure_ascii=False)))
    return cur.lastrowid


def card_chair(conn, hoje: date | None = None, voo_id: int | None = None) -> dict:
    import cards

    return cards.novo_card("chair_flying", chair_flying(conn, hoje, voo_id), [cards.acao_abrir_aba("aviacao", "Abrir Aviação")])


def chair_da_vespera(conn, agora) -> list[tuple[str, str, str]]:
    """Depois das 21h da vespera de voo com hora: o chat convida pro voo de cadeira (uma vez por voo)."""
    import conversa_proativa as cp

    saida = []
    if not cp._na_janela(agora, (agora.replace(hour=21, minute=0).time(), cp.JANELA_VESPERA[1])):
        return saida
    for v in cp._voos_com_hora(conn, agora.date() + timedelta(days=1)):
        if db.ja_notificado_alguma_vez(conn, "chair_flying_chat", v["id"]):
            continue
        db.marcar_notificado(conn, "chair_flying_chat", v["id"])
        card = card_chair(conn, agora.date(), v["id"])
        d = card["data"]
        por = f" Começa por {d['comeca_por'][0].lower()}, que travou da última vez." if d["comeca_por"] else ""
        texto = f"Antes de dormir: 3 minutinhos de voo de cadeira pro voo das {v['hora']}.{por}"
        cp.publicar(conn, "chair_flying_chat", texto, [card])
        saida.append(("chair_flying", "Voo de cadeira", "3 minutos de olho fechado pra fixar o voo de amanhã."))
    conn.commit()
    return saida


# ============================================================================ vento na pista
# Cabeceiras 01/19 de SSBL: o Alex confirmou em 04/11/2026 (o padrao antigo 18/36 era de fonte de terceiros e estava
# errado). Declinacao ~20,6 W: fonte de TERCEIROS (flightplandatabase), NAO conferida no AISWEB/ROTAER.
# Comecam marcadas como "nao conferido"; ele confere, corrige se precisar e confirma no card.
PISTA_PADRAO = {"cabeceiras": [1, 19], "decl_w": 20.6, "conferido": False}
LIMITE_TRAVES_PADRAO = 10  # kt - limite PESSOAL dele (a demo usava 10); ele ajusta, nao e regra de manual
AERODROMO_VENTO = "SSBL"


def pista_config(conn) -> dict:
    c = _json_config(conn, "aviacao_pista_ssbl", {})
    cab = c.get("cabeceiras")
    ok_cab = (isinstance(cab, list) and len(cab) == 2 and all(isinstance(x, int) and 1 <= x <= 36 for x in cab)
              and abs(cab[0] - cab[1]) == 18)
    decl = c.get("decl_w")
    ok_decl = isinstance(decl, (int, float)) and not isinstance(decl, bool) and -40 <= decl <= 40
    lim = c.get("limite_kt")
    ok_lim = isinstance(lim, int) and not isinstance(lim, bool) and 1 <= lim <= 40
    return {
        "cabeceiras": cab if ok_cab else list(PISTA_PADRAO["cabeceiras"]),
        "decl_w": float(decl) if ok_decl else PISTA_PADRAO["decl_w"],
        "conferido": bool(c.get("conferido")) and ok_cab and ok_decl,
        "limite_kt": lim if ok_lim else LIMITE_TRAVES_PADRAO,
        "padrao_de_terceiros": not (ok_cab and ok_decl),
    }


def salvar_pista(conn, corpo: dict) -> dict:
    atual = pista_config(conn)
    novo = {k: atual[k] for k in ("cabeceiras", "decl_w", "limite_kt")}
    novo["conferido"] = atual["conferido"]
    mudou_numero = False
    if "cabeceiras" in corpo:
        cab = corpo["cabeceiras"]
        if not (isinstance(cab, list) and len(cab) == 2 and all(isinstance(x, int) and not isinstance(x, bool)
                                                              and 1 <= x <= 36 for x in cab) and abs(cab[0] - cab[1]) == 18):
            raise ValueError("cabeceiras: duas, opostas (ex.: 18 e 36)")
        mudou_numero = mudou_numero or cab != novo["cabeceiras"]
        novo["cabeceiras"] = cab
    if "decl_w" in corpo:
        d = corpo["decl_w"]
        if isinstance(d, bool) or not isinstance(d, (int, float)) or not -40 <= d <= 40:
            raise ValueError("declinação em graus, entre -40 e 40 (oeste positivo)")
        mudou_numero = mudou_numero or float(d) != novo["decl_w"]
        novo["decl_w"] = float(d)
    if "limite_kt" in corpo:
        lim = corpo["limite_kt"]
        if isinstance(lim, bool) or not isinstance(lim, int) or not 1 <= lim <= 40:
            raise ValueError("limite de través em nós, entre 1 e 40")
        novo["limite_kt"] = lim
    if "conferido" in corpo:
        novo["conferido"] = bool(corpo["conferido"])
    elif mudou_numero:
        novo["conferido"] = False  # mexeu no numero: precisa confirmar de novo
    db.definir_configuracao(conn, "aviacao_pista_ssbl", json.dumps(novo))
    return pista_config(conn)


def calcular_vento(direcao_verdadeira, velocidade, pista: dict, rajada=None, corrigir: bool = True) -> dict:
    """Proa e traves contra a cabeceira com mais vento de proa. O vento do METAR vem em graus VERDADEIROS e a
    pista e MAGNETICA: com declinacao oeste, magnetico = verdadeiro + declinacao. `corrigir=False` mostra a
    conta errada (so pra comparar)."""
    if direcao_verdadeira is None:
        return {"variavel": True}
    v = float(velocidade or 0)
    dm = (float(direcao_verdadeira) + (pista["decl_w"] if corrigir else 0.0)) % 360

    def lado(rw_cab: int, vel: float):
        th = math.radians(dm - (rw_cab * 10) % 360)
        return vel * math.cos(th), abs(vel * math.sin(th))

    melhor = max(pista["cabeceiras"], key=lambda c: lado(c, v)[0])
    proa, trav = lado(melhor, v)
    trav_raj = lado(melhor, float(rajada))[1] if rajada else None
    maior = max(trav, trav_raj or 0.0)
    lim = pista["limite_kt"]
    tom = "ok" if round(maior) <= lim * 0.7 else "alerta" if round(maior) <= lim else "perigo"
    return {"variavel": False, "cabeceira": melhor, "proa": round(proa), "traves": round(trav),
            "traves_rajada": round(trav_raj) if trav_raj is not None else None, "tom": tom,
            "direcao_magnetica": round(dm)}


_CACHE_METAR: dict = {}
CACHE_METAR_S = 10 * 60


def _metar_cache(icao: str):
    import metar

    agora = time.monotonic()
    g = _CACHE_METAR.get(icao)
    if g and agora - g[0] < CACHE_METAR_S:
        return g[1]
    bruto = metar.buscar_metar_taf(icao)
    _CACHE_METAR[icao] = (agora, bruto)
    return bruto


_RE_HORA_METAR = re.compile(r"\b\d{2}(\d{2})(\d{2})Z\b")


def vento_pista(conn, icao: str = AERODROMO_VENTO, buscar=None) -> dict:
    """Dados do card. `buscar(icao)` devolve o dict de metar.buscar_metar_taf (injetavel nos testes)."""
    pista = pista_config(conn)
    try:
        bruto = (buscar or _metar_cache)(icao)
    except Exception:
        bruto = {}
    dec = (bruto or {}).get("metar_decodificado") or {}
    v = dec.get("vento") or {}
    texto = (bruto or {}).get("metar")
    m = _RE_HORA_METAR.search(texto or "")
    medido = bool(v)
    direcao = v.get("direcao") if medido and not v.get("variavel") else None
    return {
        "icao": icao, "metar": texto, "hora_z": f"{m.group(1)}{m.group(2)}Z" if m else None,
        "medido": medido, "variavel": bool(v.get("variavel")), "direcao": direcao,
        "velocidade": v.get("velocidade_kt") if medido else None, "rajada": v.get("rajada_kt") if medido else None,
        "pista": {k: pista[k] for k in ("cabeceiras", "decl_w", "conferido", "padrao_de_terceiros")},
        "limite_kt": pista["limite_kt"],
        "conta": calcular_vento(direcao, v.get("velocidade_kt"), pista, v.get("rajada_kt")) if medido else None,
        "fonte": "Cabeceiras 01/19 de SSBL confirmadas por ti; a declinação ~20,6° W vem de fonte de terceiros: confere no AISWEB/ROTAER.",
    }


def card_vento(conn, icao: str = AERODROMO_VENTO, buscar=None) -> dict:
    import cards

    return cards.novo_card("vento_pista", vento_pista(conn, icao, buscar), [cards.acao_abrir_aba("aviacao", "Abrir Aviação")])


def linha_vento(conn, icao: str | None, vento: dict | None) -> str | None:
    """Uma frase pro "bom dia" do voo ("Vento: través 9 kt na 36, teu limite é 10."), a partir do vento que o
    briefing ja trouxe. So SSBL (e a unica pista configurada) e so com vento medido e direcao."""
    if (icao or AERODROMO_VENTO) != AERODROMO_VENTO or not vento or vento.get("variavel") or vento.get("direcao") is None:
        return None
    pista = pista_config(conn)
    c = calcular_vento(vento["direcao"], vento.get("velocidade_kt"), pista, vento.get("rajada_kt"))
    if c.get("variavel"):
        return None
    t = c["traves_rajada"] if (c["traves_rajada"] or 0) > c["traves"] else c["traves"]
    nota = "" if pista["conferido"] else " (pista e declinação ainda não conferidas)"
    return f"Vento: través {t} kt na {c['cabeceira']:02d}, teu limite é {pista['limite_kt']}{nota}."


# ============================================================================ passaporte
_RE_ICAO = re.compile(r"^[A-Z]{4}$")
NOVO_CARIMBO_DIAS = 14


def passaporte(conn, hoje: date | None = None) -> dict:
    """Um carimbo por aerodromo onde ele pousou (destino e escalas de voo REAL, simulador fora), com a data do
    primeiro pouso. Tudo do diario de bordo."""
    hoje = hoje or date.today()
    rows = conn.execute(
        "SELECT data, origem, destino, escalas, horas, aeronave FROM voos WHERE horas IS NOT NULL AND data <= ? "
        "AND COALESCE(tipo, '') != 'simulador' ORDER BY data, id",
        (hoje.isoformat(),),
    ).fetchall()
    por: dict = {}
    aeronaves = set()
    total = 0.0
    for r in rows:
        total += float(r["horas"])
        if r["aeronave"] and str(r["aeronave"]).strip():
            aeronaves.add(str(r["aeronave"]).strip().upper())
        pousos = [rota_voo.aerodromo(e) for e in (r["escalas"] or "").split(",") if e.strip()]
        pousos.append(rota_voo.aerodromo(r["destino"]))
        for icao in pousos:
            if not icao or not _RE_ICAO.match(icao):
                continue
            c = por.setdefault(icao, {"icao": icao, "primeiro": r["data"], "voos": 0})
            c["voos"] += 1
    carimbos = sorted(por.values(), key=lambda c: c["primeiro"])  # estavel: no mesmo dia, na ordem da rota
    for c in carimbos:
        c["nome"] = rota_voo.nome(c["icao"]) if rota_voo.nome(c["icao"]) != c["icao"] else None
        c["novo"] = (hoje - date.fromisoformat(c["primeiro"])).days <= NOVO_CARIMBO_DIAS
    return {"hoje": hoje.isoformat(), "carimbos": carimbos, "horas": round(total, 1), "aeronaves": len(aeronaves),
            "voos": len(rows), "fonte": "diário de bordo do painel (voos reais; simulador não conta)"}


def card_passaporte(conn, hoje: date | None = None) -> dict:
    import cards

    return cards.novo_card("passaporte", passaporte(conn, hoje), [cards.acao_abrir_aba("aviacao", "Abrir Aviação")])


# ============================================================================ tudo da aba
def todos_os_cards(conn, hoje: date | None = None, buscar_vento=None) -> list[dict]:
    """Os cards da Aviacao na ordem da aba (cada um isolado: um que quebra nao derruba os outros)."""
    montadores = (
        lambda: card_radar(conn, hoje), lambda: card_previsao_cheque(conn, hoje), lambda: card_banca(conn, hoje),
        lambda: card_chair(conn, hoje), lambda: card_vento(conn, AERODROMO_VENTO, buscar_vento),
        lambda: card_passaporte(conn, hoje),
    )
    saida = []
    for m in montadores:
        try:
            saida.append(m())
        except Exception:
            import logging

            logging.getLogger(__name__).exception("aviacao_lab: card falhou")
    return saida
