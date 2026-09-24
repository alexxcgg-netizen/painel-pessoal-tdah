"""Faixa P3 - gatilho periodico (POST /api/tick, faixa P1a) que monta e
enfileira os dois briefings do dia (manha e noite) na Caixa do assistente,
uma vez por dia, dentro de uma janela curta em torno do horario configurado
(assistente/briefing.py). `agora` e sempre injetado pelo chamador - nunca
datetime.now() aqui, pra dar pra testar virada de dia/horario editado sem
esperar o relogio de verdade.

Idempotente: chave_unica="p3_manha:<data>"/"p3_noite:<data>" garante que,
mesmo se o tick rodar duas vezes na mesma janela de 5min (ou o processo
reiniciar no meio), a P1a (assistente/caixa.py) nao duplica o item.
"""

from datetime import datetime, timedelta

from assistente import briefing

# Janela em que o gatilho considera "e agora" pro horario configurado - mesma
# ideia do notificacoes.fechamento_noturno_devido (Fase 6), so que o horario
# aqui vem de configuracoes em vez de fixo.
JANELA_MINUTOS = 5


def _dentro_da_janela(agora: datetime, horario: str) -> bool:
    if not briefing.horario_valido(horario):
        return False
    hh, mm = (int(p) for p in horario.split(":"))
    alvo = agora.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return alvo <= agora < alvo + timedelta(minutes=JANELA_MINUTOS)


def executar(conn, agora: datetime) -> None:
    if not briefing.ativo(conn):
        return

    from assistente.caixa import enfileirar  # tardio (contrato: implementado na P1a)

    hoje = agora.date()
    hoje_iso = hoje.isoformat()

    if _dentro_da_janela(agora, briefing.horario_manha(conn)):
        dados = briefing.montar_manha(conn, hoje)
        enfileirar(
            tipo="briefing",
            titulo=dados["titulo"],
            corpo=dados["corpo"],
            origem=f"p3_briefing:manha:{hoje_iso}",
            chave_unica=f"p3_manha:{hoje_iso}",
        )

    if _dentro_da_janela(agora, briefing.horario_noite(conn)):
        dados = briefing.montar_noite(conn, hoje)
        enfileirar(
            tipo="briefing",
            titulo=dados["titulo"],
            corpo=dados["corpo"],
            opcoes=dados["opcoes"],
            origem=f"p3_briefing:noite:{hoje_iso}",
            chave_unica=f"p3_noite:{hoje_iso}",
        )


def ao_resolver(conn, item, resposta, texto="") -> None:
    """Chamado pela P1a quando o Alex responde um item da Caixa cuja origem
    comeca com o prefixo deste gatilho (contrato em
    docs/agentes/fase7-assistente.md). So o fechamento da noite tem acao
    real: a resposta de 'Como foi o dia?' vira checkins.humor do dia (mesma
    escala 1-5 que o resto do painel ja usa, db.salvar_checkin)."""
    try:
        origem = item["origem"] or ""
    except (KeyError, TypeError, IndexError):
        origem = ""

    # C1: origem = "p3_briefing:noite:<data>" (prefixo = nome deste arquivo,
    # regra do integrador - so assim a P1a acha este ao_resolver). O formato
    # antigo "p3_briefing_noite:<data>" continua aceito pra itens ja criados.
    if not (origem.startswith("p3_briefing:noite:") or origem.startswith("p3_briefing_noite:")):
        return

    humor = briefing.humor_da_resposta(resposta)
    if humor is None:
        return

    data = origem.rsplit(":", 1)[1]  # a data e sempre o ultimo campo (nos 2 formatos)

    import db  # tardio, so pra manter o padrao de import tardio deste modulo

    db.salvar_checkin(conn, data, {"humor": humor})
