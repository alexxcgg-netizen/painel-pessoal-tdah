# assistente/gatilhos/p4_regras.py — faixa P4 (Fase 7): tarefa periodica do
# tick (POST /api/tick -> assistente.gatilhos.executar_todos, ver
# docs/agentes/fase7-assistente.md). Le a tabela p4_regras (migracoes/
# 202609241230_p4_regras.sql), avalia cada regra ativa com o motor puro
# (assistente/regras.py) e, quando a condicao bate, enfileira um aviso.
#
# Idempotencia: cada regra guarda `ultima_vez` (ISO datetime do ultimo
# disparo) e assistente.regras.avaliar_regra() so devolve deve_disparar=True
# quando a janela atual (dia/semana/mes/data, conforme o gatilho) ainda nao
# foi atendida - ver o modulo pra detalhe por tipo. Isso ja e suficiente pra
# nao duplicar mesmo se o tick rodar 2x no mesmo minuto (a segunda vez le o
# `ultima_vez` que a primeira acabou de gravar). A `chave_unica` passada pra
# `enfileirar` e uma segunda camada de seguranca (idempotencia do lado da
# Caixa, faixa P1a).
from __future__ import annotations

import json
import logging
from datetime import datetime

from assistente import regras as motor

log = logging.getLogger(__name__)

TABELA = "p4_regras"


def _enfileirar(*args, **kwargs):
    """Import tardio do contrato da Caixa (assistente/caixa.py, faixa P1a) -
    ver docs/agentes/fase7-assistente.md ("importam de forma tardia... nos
    testes usam unittest.mock.patch"). Enquanto a P1a nao existir, cai no
    stub de assistente/contrato.py (levanta NotImplementedError - nunca
    silencioso)."""
    try:
        from assistente.caixa import enfileirar
    except ImportError:
        from assistente.contrato import enfileirar
    return enfileirar(*args, **kwargs)


def _parse_datetime(valor: str | None) -> datetime | None:
    if not valor:
        return None
    texto = str(valor).strip()
    if not texto:
        return None
    try:
        return datetime.fromisoformat(texto)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(texto, fmt)
            except ValueError:
                continue
        log.warning("p4_regras: nao consegui interpretar data/hora %r", valor)
        return None


def executar(conn, agora: datetime) -> None:
    """Chamado pelo tick (assistente.gatilhos.executar_todos). Silencioso se
    a tabela ainda nao existir (infra de migracao da Etapa 0 nao chegou) -
    nunca derruba o tick por causa disso."""
    try:
        linhas = conn.execute(
            f"SELECT id, texto_original, json, ativa, pausada_ate, ultima_vez FROM {TABELA} "
            "WHERE ativa = 1"
        ).fetchall()
    except Exception:
        log.debug("p4_regras: tabela %s indisponivel, tick pulado", TABELA)
        return

    for linha in linhas:
        try:
            _processar_regra(conn, dict(linha), agora)
        except Exception:  # uma regra com problema nunca derruba as outras
            log.exception("p4_regras: falha ao processar a regra %s", linha["id"])


def _processar_regra(conn, linha: dict, agora: datetime) -> None:
    regra_id = linha["id"]

    pausada_ate = _parse_datetime(linha.get("pausada_ate"))
    if pausada_ate is not None and agora < pausada_ate:
        return

    try:
        regra = json.loads(linha["json"])
    except (TypeError, ValueError):
        log.warning("p4_regras: json invalido na regra %s, ignorando", regra_id)
        return

    ultima_vez = _parse_datetime(linha.get("ultima_vez"))
    deve_disparar, mensagem, detalhe = motor.avaliar_regra(conn, regra, agora, ultima_vez)
    if not deve_disparar:
        return

    # origem: "<nome do arquivo deste gatilho sem .py>:<resto>" (definicao do
    # integrador) - a P1a despacha ao_resolver dividindo no PRIMEIRO ":" e
    # importando assistente/gatilhos/<esse nome>.py. Este arquivo se chama
    # "p4_regras.py", entao o prefixo tem que ser exatamente "p4_regras".
    origem = f"p4_regras:{regra_id}"
    chave_unica = f"{origem}:{detalhe.get('janela', agora.isoformat())}"
    _enfileirar(
        "aviso",
        detalhe.get("titulo") or "Lembrete",
        mensagem,
        origem=origem,
        chave_unica=chave_unica,
    )

    agora_txt = agora.strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(f"UPDATE {TABELA} SET ultima_vez = ? WHERE id = ?", (agora_txt, regra_id))
    # Regra de data unica (nao diaria/semanal): ja cumpriu o proposito, nao
    # precisa continuar ativa disparando de novo (avaliar_horario ja evita
    # duplicar no mesmo dia, mas desativar deixa a lista de regras limpa).
    condicao = regra.get("condicao") or {}
    if regra.get("gatilho") == "horario" and condicao.get("tipo") == "data":
        conn.execute(f"UPDATE {TABELA} SET ativa = 0 WHERE id = ?", (regra_id,))
    conn.commit()
