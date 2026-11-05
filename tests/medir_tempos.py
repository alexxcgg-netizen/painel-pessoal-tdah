"""Mede o tempo de resposta de cada rota GET do painel com o volume de dado de verdade (2026-11-05).

Nao e teste da suite (o nome nao comeca com test_): roda so quando chamado de proposito:

    .venv/Scripts/python.exe -m pytest tests/medir_tempos.py -q -s

Copia `data/painel.db` (aberto SO LEITURA, pela API de backup do SQLite) pra uma pasta temporaria, aponta o
app pra copia e chama cada rota GET sem parametro, 3 vezes (fria + 2 quentes). Roda dentro do isolamento do
tests/conftest.py: nada sai da maquina (IA, iCloud, Maps e tempo falham na hora), entao o numero e o custo do
NOSSO codigo (SQL, montagem, render). Imprime so caminho, status, tamanho e milissegundos - nenhum dado.
A copia some no fim. Rotas que chamam a IA aparecem com ~1 s (a IA falsa do conftest derruba a conexao).
"""

import sqlite3
import statistics
import tempfile
import time
from pathlib import Path

import pytest

import db

REAL = Path(__file__).resolve().parent.parent / "data" / "painel.db"

# streaming, download pesado ou que espera evento - nao medem resposta
PULAR = ("/api/chat/stream", "/api/eventos", "/static/", "/service-worker.js", "/api/backup", "/api/exportar")


@pytest.mark.skipif(not REAL.exists(), reason="sem data/painel.db nesta maquina")
def test_medir_tempos():
    with tempfile.TemporaryDirectory() as pasta:
        copia = Path(pasta) / "painel.db"
        origem = sqlite3.connect(f"file:{REAL.as_posix()}?mode=ro", uri=True)
        destino = sqlite3.connect(copia)
        origem.backup(destino)
        origem.close()
        destino.close()

        db.DB_PATH = copia
        db.garantir_banco_nao_producao()
        import app as app_mod

        app_mod.db.init_db()
        cliente = app_mod.app.test_client()
        with cliente.session_transaction() as s:
            s["autenticado"] = True

        rotas = sorted({
            r.rule for r in app_mod.app.url_map.iter_rules()
            if "GET" in r.methods and not r.arguments and not r.rule.startswith(PULAR)
        })
        linhas = []
        for rota in rotas:
            tempos = []
            status = tamanho = 0
            for _ in range(3):
                t0 = time.perf_counter()
                try:
                    r = cliente.get(rota)
                    status, tamanho = r.status_code, len(r.data)
                except Exception as e:  # noqa: BLE001 - medicao: anota e segue
                    status, tamanho = f"erro {type(e).__name__}", 0
                tempos.append((time.perf_counter() - t0) * 1000)
            linhas.append((tempos[0], statistics.median(tempos[1:]), rota, status, tamanho))

        linhas.sort(key=lambda x: -x[1])
        print(f"\n{'fria ms':>8} {'quente ms':>9}  status  {'bytes':>8}  rota")
        for fria, quente, rota, status, tamanho in linhas:
            print(f"{fria:8.0f} {quente:9.0f}  {str(status):6}  {tamanho:8d}  {rota}")
        print(f"\n{len(linhas)} rotas; soma quente {sum(x[1] for x in linhas):.0f} ms")
