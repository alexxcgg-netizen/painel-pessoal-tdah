"""Fase 8, faixa F3 - avisa 3/2/1 dia antes de uma assinatura cobrar de
novo, so pra quem tem o interruptor `assinatura.avisar_antes_cobrar` ligado
(migracoes/202609251200_f8_assinatura_aviso.sql, DESLIGADO por padrao -
nenhuma assinatura avisa sozinha).

A data da proxima cobranca vem de
`financas_recorrentes.proxima_cobranca_assinatura` (a mesma conta que a
rota GET /api/financas/assinaturas ja usa) - nao reimplementada aqui.

Idempotente pela `chave_unica` que `assistente.contrato.enfileirar` recebe:
inclui a data ISO da cobranca-alvo + a contagem de dias, entao rodar o tick
varias vezes no mesmo dia (ou em dias diferentes, enquanto a cobranca-alvo
nao mudar) nunca duplica o aviso, e o mesmo aviso nunca repete 2x pro mesmo
ciclo de cobranca.

Nao mistura com o aviso de teto de gasto (`valor_para_aviso_custos_fixos`/
tipo "orcamento") nem chama IA - so texto fixo com nome e prazo.
"""

from datetime import datetime

import financas_recorrentes as fr

PREFIXO = "f8_aviso_cobranca"  # nome deste arquivo sem .py
DIAS_AVISO = (3, 2, 1)


def _enfileirar(**kwargs):
    # Late import de proposito - mesmo padrao dos outros gatilhos
    # (assistente/gatilhos/p2_perguntas.py), assistente.contrato pode nao
    # estar pronto quando este modulo e importado.
    from assistente.contrato import enfileirar

    return enfileirar(**kwargs)


def _texto_prazo(dias: int) -> str:
    return "amanha" if dias == 1 else f"em {dias} dias"


def executar(conn, agora: datetime) -> dict:
    hoje = agora.date()
    criados = 0
    for assinatura in fr.listar_assinaturas(conn, apenas_ativas=True):
        if not assinatura.get("avisar_antes_cobrar"):
            continue
        proxima = fr.proxima_cobranca_assinatura(assinatura, hoje)
        if proxima is None:
            continue
        dias = (proxima - hoje).days
        if dias not in DIAS_AVISO:
            continue

        nome = (assinatura.get("nome") or "Assinatura").strip()
        valor = assinatura.get("valor")
        prazo = _texto_prazo(dias)
        titulo = f"{nome} cobra de novo {prazo}"
        corpo = f"Cobranca de R$ {valor:.2f} prevista para {proxima.isoformat()}." if isinstance(valor, (int, float)) else ""

        _enfileirar(
            tipo="aviso",
            titulo=titulo,
            corpo=corpo,
            origem=f"{PREFIXO}:assinatura",
            chave_unica=f"{PREFIXO}:assinatura:{assinatura['id']}:{proxima.isoformat()}:{dias}",
        )
        criados += 1
    return {"avisos_criados": criados}
