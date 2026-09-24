# ia/medicao.py — faixa A4 (medicao e teto)
#
# Implementa `registrar_uso`/`gasto_mes_atual*` do contrato (`ia/contrato.py`,
# NAO alterado aqui - so a faixa A1 mexe nele). Grava e le `uso_ia`
# (`ia/migracao_uso_ia.py`) - SO metadados de uso (tokens/custo/latencia),
# nunca conteudo de prompt/resposta.
#
# Mesma assinatura de `ia.contrato.registrar_uso`:
#   registrar_uso(funcao, provedor, modelo, *, tokens_in=0, tokens_out=0,
#                 tokens_cache_lido=0, tokens_cache_escrito=0, custo_usd=0.0,
#                 latencia_ms=0, ok=True) -> None

import json
from datetime import datetime, timezone
from pathlib import Path

import db
from ia.migracao_uso_ia import garantir_tabela

CAMINHO_PRECOS = Path(__file__).parent / "precos.json"

# Cambio de fallback se `ia/precos.json` nao existir/estiver corrompido -
# mesmo valor "fixo" combinado com o Alex pra Fase 7 (ver ia/teto.py).
CAMBIO_USD_BRL_PADRAO = 5.50


def _carregar_precos() -> dict:
    """Le ia/precos.json. Corpo malformado/arquivo ausente nunca deve
    derrubar quem chama `registrar_uso`/`gasto_mes_atual_brl` - cai pro
    cambio padrao e um dict vazio de modelos (custo em USD, ja calculado por
    quem chamou `registrar_uso`, nao depende disso pra gravar)."""
    try:
        with open(CAMINHO_PRECOS, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def cambio_usd_brl() -> float:
    """Cambio USD->BRL fixo configurado em ia/precos.json (`cambio_usd_brl`) -
    fixo de proposito (decisao do Alex pra Fase 7, nao busca cotacao real).
    Valor ausente/invalido cai pro padrao (5.50)."""
    precos = _carregar_precos()
    valor = precos.get("cambio_usd_brl")
    if not isinstance(valor, (int, float)) or valor <= 0:
        return CAMBIO_USD_BRL_PADRAO
    return float(valor)


def registrar_uso(
    funcao: str,
    provedor: str,
    modelo: str,
    *,
    tokens_in: int = 0,
    tokens_out: int = 0,
    tokens_cache_lido: int = 0,
    tokens_cache_escrito: int = 0,
    custo_usd: float = 0.0,
    latencia_ms: int = 0,
    ok: bool = True,
) -> None:
    """Grava uma linha de uso em `uso_ia` (sem conteudo de prompt nenhum -
    so metadados). Mesma assinatura de `ia.contrato.registrar_uso` - serve
    tanto chamadas que passaram por `ia.core.chamar_ia` quanto qualquer
    caminho que meça uso por fora dele."""
    conn = db.get_db()
    try:
        garantir_tabela(conn)
        conn.execute(
            "INSERT INTO uso_ia "
            "(funcao, provedor, modelo, tokens_in, tokens_out, tokens_cache_lido, "
            "tokens_cache_escrito, custo_usd, latencia_ms, ok) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                funcao,
                provedor,
                modelo,
                int(tokens_in or 0),
                int(tokens_out or 0),
                int(tokens_cache_lido or 0),
                int(tokens_cache_escrito or 0),
                float(custo_usd or 0.0),
                int(latencia_ms or 0),
                1 if ok else 0,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _limite_utc_inicio_mes() -> str:
    """`uso_ia.criado_em` e gravado com `datetime('now')` do SQLite (UTC, sem
    tzinfo) - mesma convencao de `api_usage.created_at`/`db._limite_utc`. O
    inicio do mes precisa ser calculado no horario LOCAL (dia 1 00:00) e so
    depois convertido pra UTC, senao a virada de mes fica errada em ate ~12h
    dependendo do fuso (mesma pegadinha ja documentada em `db._limite_utc`)."""
    agora_local = datetime.now().astimezone()
    inicio_mes_local = agora_local.replace(hour=0, minute=0, second=0, microsecond=0, day=1)
    return inicio_mes_local.astimezone(timezone.utc).replace(tzinfo=None).isoformat(sep=" ", timespec="seconds")


def _gasto_legado_antes_da_medicao(conn, inicio_mes: str) -> float:
    """Custo em `api_usage` (tabela antiga, gravada por `app._log_usage`) do
    mes corrente que aconteceu ANTES da primeira linha de `uso_ia` do mes.

    Fase 7, faixa C1 - fonte unica do gasto do mes: desde a C1 toda chamada
    de IA do app entra em `uso_ia` exatamente uma vez (ia.core.chamar_ia, o
    chat com `medir_uso=True` e o caminho direto de `_chamar_json`). O
    `api_usage` continua recebendo a copia antiga (card antigo/historico),
    entao somar as duas tabelas contaria a mesma chamada 2 vezes. So o que a
    medicao nova ainda NAO via (mes da virada pro deploy da Fase 7, ou teste
    que so grava a tabela antiga) entra aqui - por construcao nunca se
    sobrepoe a uma linha de `uso_ia` (a linha nova e gravada antes da antiga
    em toda chamada). Tabela antiga ausente -> 0."""
    try:
        primeira = conn.execute(
            "SELECT MIN(criado_em) AS primeira FROM uso_ia WHERE criado_em >= ?",
            (inicio_mes,),
        ).fetchone()["primeira"]
        if primeira is None:
            row = conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) AS total FROM api_usage WHERE created_at >= ?",
                (inicio_mes,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) AS total FROM api_usage "
                "WHERE created_at >= ? AND created_at < ?",
                (inicio_mes, primeira),
            ).fetchone()
        return float(row["total"] or 0.0)
    except Exception:  # noqa: BLE001 - tabela antiga ausente/estranha nunca derruba o teto
        return 0.0


def gasto_mes_atual() -> float:
    """Gasto de IA do mes corrente (calendario local), em USD - a FONTE UNICA
    que o teto (ia/teto.py) e o card de custo usam: soma de `uso_ia` mais o
    legado de `api_usage` anterior a medicao nova (ver
    `_gasto_legado_antes_da_medicao`). Cada chamada conta uma vez so."""
    conn = db.get_db()
    try:
        garantir_tabela(conn)
        inicio_mes = _limite_utc_inicio_mes()
        row = conn.execute(
            "SELECT COALESCE(SUM(custo_usd), 0) AS total FROM uso_ia WHERE criado_em >= ?",
            (inicio_mes,),
        ).fetchone()
        return float(row["total"]) + _gasto_legado_antes_da_medicao(conn, inicio_mes)
    finally:
        conn.close()


def gasto_mes_atual_brl() -> float:
    """`gasto_mes_atual()` convertido pro cambio fixo de `ia/precos.json`."""
    return gasto_mes_atual() * cambio_usd_brl()
