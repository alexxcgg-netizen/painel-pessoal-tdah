"""Diario de bordo (leva 22/10, ideia 1): depois do voo o painel pergunta so 3 coisas (tipo, dia/noite,
tempo; no TGL os toques) e mostra quanto falta em cada categoria pra licenca de piloto comercial.

Os minimos sao do RBAC 61.101(a)(1) (PC aviao, curso homologado pela ANAC), conferido no texto da
Emenda 00 em 22/10/2026: 150 h no total, 20 h de navegacao, 10 h de instrucao por instrumentos (ate 5 h
podem ser em simulador) e 5 h de voo noturno. Navegacao e noturno contam "como piloto em comando" -
o painel nao sabe a funcao a bordo de cada hora, entao soma o que ele registrou e o rodape manda
conferir na CIV. "TGL" (toque e arremetida) nao e categoria do regulamento: so conta os toques.

Conta pura do historico em Python, nunca pela IA. Simulador nao soma no total (igual a CIV e ao resto
do app); entra so em instrumentos, ate o limite de 5 h."""
from datetime import date

import db

NATUREZAS = ("navegacao", "tgl", "instrumentos")
NOME = {"navegacao": "navegação", "tgl": "TGL", "instrumentos": "instrumentos"}
REQUISITOS = (("navegacao", "Navegação", 20), ("noturno", "Noturno", 5), ("instrumentos", "Instrumentos", 10))
SIMULADOR_MAX_INSTRUMENTOS = 5
FONTE = "RBAC 61.101"
TOQUES_MAX = 30


def _meta_total(conn) -> int:
    cfg = db.obter_configuracao(conn, "aviacao_meta_horas")
    return int(cfg) if cfg and cfg.isdigit() else 150


def _eh_navegacao(r) -> bool:
    """Respondido vale o que ele disse; voo antigo sem resposta (CIV) conta como navegacao quando
    saiu de um lugar e pousou em outro (ou teve escala)."""
    if r["natureza"]:
        return r["natureza"] == "navegacao"
    origem, destino = (r["origem"] or "").strip().upper(), (r["destino"] or "").strip().upper()
    return bool(r["escalas"]) or bool(origem and destino and origem != destino)


def progresso(conn, hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    rows = conn.execute(
        "SELECT origem, destino, escalas, horas, tipo, natureza, noturno, toques FROM voos "
        "WHERE horas IS NOT NULL AND data <= ?",
        (hoje.isoformat(),),
    ).fetchall()
    reais = [r for r in rows if (r["tipo"] or "") != "simulador"]
    sim = sum(float(r["horas"]) for r in rows if (r["tipo"] or "") == "simulador")
    soma = {
        "navegacao": sum(float(r["horas"]) for r in reais if _eh_navegacao(r)),
        "noturno": sum(float(r["horas"]) for r in reais if r["noturno"]),
        "instrumentos": sum(float(r["horas"]) for r in reais if r["natureza"] == "instrumentos")
        + min(SIMULADOR_MAX_INSTRUMENTOS, sim),
    }
    meta = _meta_total(conn)
    cats = [{"chave": "total", "nome": "Total", "h": round(sum(float(r["horas"]) for r in reais), 1), "meta": meta}]
    cats += [{"chave": k, "nome": n, "h": round(soma[k], 1), "meta": m} for k, n, m in REQUISITOS]
    abertas = [c for c in cats[1:] if c["h"] < c["meta"]]
    pior = min(abertas, key=lambda c: c["h"] / c["meta"])["chave"] if abertas else None
    return {
        "cats": cats,
        "pior": pior,
        "toques_curso": sum(int(r["toques"] or 0) for r in reais),
        "fonte": FONTE,
    }


def card(conn, voo_id: int, hoje: date | None = None) -> dict | None:
    """Card `diario_bordo`: o tempo ja vem do que foi gravado ou da estimativa da rota (horario de
    motor); se o voo ja foi respondido abre registrado, com o Desfazer."""
    import cards

    v = conn.execute(
        "SELECT id, data, origem, destino, horas, natureza, noturno, toques FROM voos WHERE id = ?", (voo_id,)
    ).fetchone()
    if not v:
        return None
    hoje = hoje or date.today()
    base = cards.card_voo_horas(conn, voo_id, hoje)
    bd = base["data"] if base else {}
    horas = float(v["horas"]) if v["horas"] is not None else (bd.get("estimativa") or 1.0)
    return cards.novo_card(
        "diario_bordo",
        {
            "id": v["id"],
            "data": v["data"],
            "rota": bd.get("rota") or (f"{bd['icao']} → {bd['icao']}" if bd.get("icao") else None),
            "horas": round(horas, 1),
            "estimado": v["horas"] is None and bool(bd.get("estimativa")),
            "natureza": v["natureza"],
            "noturno": bool(v["noturno"]),
            "toques": int(v["toques"]) if v["toques"] else 4,
            "registrado": bool(v["natureza"]) and v["horas"] is not None,
            # como o voo esta gravado agora - o Desfazer devolve isto
            "salvo": {"horas": v["horas"], "natureza": v["natureza"], "noturno": bool(v["noturno"]),
                      "toques": v["toques"]},
            **progresso(conn, hoje),
        },
        [cards.acao_abrir_aba("aviacao", "Abrir Aviação")],
    )


def registrar(conn, voo_id: int, horas, natureza, noturno, toques) -> dict:
    """Grava as 3 respostas. `horas=None` + `natureza=None` desfaz (volta como estava antes - o front
    manda o estado anterior). Levanta ValueError com a mensagem pro 400."""
    if natureza is not None and natureza not in NATUREZAS:
        raise ValueError("tipo precisa ser navegação, TGL ou instrumentos")
    if horas is not None:
        if not isinstance(horas, (int, float)) or isinstance(horas, bool) or not 0 < horas <= 12:
            raise ValueError("horas precisa ser entre 0,1 e 12")
        horas = round(float(horas), 1)
    if natureza == "tgl":
        if not isinstance(toques, int) or isinstance(toques, bool) or not 1 <= toques <= TOQUES_MAX:
            raise ValueError(f"toques precisa ser entre 1 e {TOQUES_MAX}")
    else:
        toques = None
    conn.execute(
        "UPDATE voos SET horas = ?, natureza = ?, noturno = ?, toques = ? WHERE id = ?",
        (horas, natureza, 1 if noturno else 0, toques, voo_id),
    )
    return {"horas": horas, "natureza": natureza, "noturno": bool(noturno), "toques": toques}


def voo_de_hoje(conn, hoje: date) -> int | None:
    """"Acabei de voar": o voo de hoje (o ultimo marcado), senao o mais recente ainda sem horas."""
    r = conn.execute(
        "SELECT id FROM voos WHERE data = ? AND COALESCE(tipo, '') != 'simulador' ORDER BY COALESCE(hora, '') DESC, id DESC",
        (hoje.isoformat(),),
    ).fetchone() or conn.execute(
        "SELECT id FROM voos WHERE data <= ? AND horas IS NULL AND COALESCE(tipo, '') != 'simulador' ORDER BY data DESC, id DESC",
        (hoje.isoformat(),),
    ).fetchone()
    return r["id"] if r else None
