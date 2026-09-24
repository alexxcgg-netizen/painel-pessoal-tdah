# ia/migracao_uso_ia.py — faixa A4 (medicao e teto)
#
# Migracao SQL da tabela `uso_ia`, guardada como arquivo NOVO e separada da
# migracao existente em `db.py` (nunca editamos a migracao existente -
# AGENTS.md, regra de escopo da faixa A4). `db.py` neste projeto NAO tem uma
# pasta `migrations/`: o padrao real e um `init_db()` unico e idempotente
# (`CREATE TABLE IF NOT EXISTS` + `_garantir_coluna` pra coluna nova em banco
# antigo, ver `db.py`). Seguimos o MESMO padrao aqui, só que num arquivo
# proprio: `garantir_tabela(conn)` e chamada sozinha (lazy) por
# `ia/medicao.py`/`ia/teto.py` antes de ler ou escrever `uso_ia`, exatamente
# como `db.init_db()` roda `CREATE TABLE IF NOT EXISTS` em toda inicializacao
# sem duplicar dado nem quebrar se já existir.
#
# `uso_ia` guarda SO METADADOS de uso de IA (tokens, custo, latencia, funcao,
# provedor, modelo) - nunca o conteudo de nenhum prompt/resposta, por decisao
# explicita da tarefa desta faixa.
#
# Por que isso NAO precisa tocar `db.py`/`app.py`: `sqlite3.Connection` aceita
# `CREATE TABLE IF NOT EXISTS` a qualquer momento, entao o schema pode nascer
# na primeira chamada de `registrar_uso`/`gasto_mes_atual`/`teto_permite`,
# sem depender de `db.init_db()` ter rodado essa tabela especifica primeiro.
# Isso mantem o diff desta faixa fora de `db.py`/`app.py` (arquivos
# compartilhados com outras faixas em paralelo).

SQL_CRIAR_TABELA = """
CREATE TABLE IF NOT EXISTS uso_ia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    funcao TEXT NOT NULL,
    provedor TEXT NOT NULL,
    modelo TEXT NOT NULL,
    tokens_in INTEGER NOT NULL DEFAULT 0,
    tokens_out INTEGER NOT NULL DEFAULT 0,
    tokens_cache_lido INTEGER NOT NULL DEFAULT 0,
    tokens_cache_escrito INTEGER NOT NULL DEFAULT 0,
    custo_usd REAL NOT NULL DEFAULT 0.0,
    latencia_ms INTEGER NOT NULL DEFAULT 0,
    ok INTEGER NOT NULL DEFAULT 1
);
"""

SQL_CRIAR_INDICE = """
CREATE INDEX IF NOT EXISTS idx_uso_ia_criado_em ON uso_ia(criado_em);
"""


def garantir_tabela(conn) -> None:
    """Idempotente - chamar sempre antes de ler/gravar `uso_ia` (mesmo padrao
    de `db._garantir_coluna`/`db.init_db`: seguro rodar em toda chamada, nunca
    duplica nem apaga dado existente)."""
    conn.executescript(SQL_CRIAR_TABELA + SQL_CRIAR_INDICE)
    conn.commit()
