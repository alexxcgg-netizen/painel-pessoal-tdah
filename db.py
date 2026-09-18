import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "painel.db"


def get_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            source_text TEXT,
            due_at TEXT,
            completed_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS subtasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            completed_at TEXT,
            position INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            source_text TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS api_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model TEXT NOT NULL,
            input_tokens INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,
            cost_usd REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS bank_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            banco TEXT NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'conta',
            criado_em TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(banco, tipo)
        );

        CREATE TABLE IF NOT EXISTS bank_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_account_id INTEGER NOT NULL REFERENCES bank_accounts(id) ON DELETE CASCADE,
            data TEXT NOT NULL,
            descricao TEXT,
            valor REAL NOT NULL,
            external_id TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(bank_account_id, external_id)
        );

        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            valor_alvo REAL NOT NULL,
            prazo TEXT,
            valor_guardado REAL NOT NULL DEFAULT 0,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS push_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            endpoint TEXT NOT NULL UNIQUE,
            subscription_json TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS memorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            texto TEXT NOT NULL,
            source_text TEXT,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS saude_dados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL UNIQUE,
            passos INTEGER,
            distancia_km REAL,
            sono_horas REAL,
            andares_subidos INTEGER,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    conn.commit()
    _seed_perfil_inicial(conn)
    conn.close()


PERFIL_INICIAL = [
    "Se chama Alex, tem 20 anos (nasceu em 8 de dezembro de 2005).",
    "E piloto de aviao.",
    "Tem uma construtora - constroi predios e casas.",
]


def _seed_perfil_inicial(conn):
    """Poe os fatos basicos do perfil como memoria logo na primeira vez que o
    banco e criado, pra ele ja "conhecer" a pessoa desde o primeiro uso em vez
    de aprender tudo do zero. So roda uma vez (marca pelo source_text)."""
    ja_existe = conn.execute(
        "SELECT 1 FROM memorias WHERE source_text = 'perfil-inicial' LIMIT 1"
    ).fetchone()
    if ja_existe:
        return
    for texto in PERFIL_INICIAL:
        conn.execute(
            "INSERT INTO memorias (texto, source_text) VALUES (?, ?)", (texto, "perfil-inicial")
        )
    conn.commit()


def save_push_subscription(conn, endpoint: str, subscription_json: str):
    conn.execute(
        "INSERT OR REPLACE INTO push_subscriptions (endpoint, subscription_json) VALUES (?, ?)",
        (endpoint, subscription_json),
    )
    conn.commit()


def list_push_subscriptions(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM push_subscriptions").fetchall()]


def delete_push_subscription(conn, endpoint: str):
    conn.execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,))
    conn.commit()


def get_or_create_bank_account(conn, banco: str, tipo: str = "conta") -> int:
    row = conn.execute(
        "SELECT id FROM bank_accounts WHERE banco = ? AND tipo = ?", (banco, tipo)
    ).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO bank_accounts (banco, tipo) VALUES (?, ?)", (banco, tipo))
    conn.commit()
    return cur.lastrowid


def insert_bank_transactions(conn, bank_account_id: int, transactions: list[dict]) -> int:
    """Insere transacoes ignorando duplicatas (mesmo external_id). Retorna quantas foram novas."""
    novas = 0
    for t in transactions:
        cur = conn.execute(
            """INSERT OR IGNORE INTO bank_transactions
               (bank_account_id, data, descricao, valor, external_id)
               VALUES (?, ?, ?, ?, ?)""",
            (bank_account_id, t["data"], t["descricao"], t["valor"], t["external_id"]),
        )
        if cur.rowcount:
            novas += 1
    conn.commit()
    return novas


def create_goal(conn, titulo: str, valor_alvo: float, prazo: str | None) -> int:
    cur = conn.execute(
        "INSERT INTO goals (titulo, valor_alvo, prazo) VALUES (?, ?, ?)",
        (titulo, valor_alvo, prazo),
    )
    conn.commit()
    return cur.lastrowid


def add_to_goal(conn, goal_id: int, valor: float):
    conn.execute(
        "UPDATE goals SET valor_guardado = valor_guardado + ? WHERE id = ?", (valor, goal_id)
    )
    conn.commit()


def list_goals(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM goals ORDER BY criado_em DESC").fetchall()
    return [dict(r) for r in rows]


def record_usage(conn, model: str, input_tokens: int, output_tokens: int, cost_usd: float):
    conn.execute(
        "INSERT INTO api_usage (model, input_tokens, output_tokens, cost_usd) VALUES (?, ?, ?, ?)",
        (model, input_tokens, output_tokens, cost_usd),
    )
    conn.commit()


def total_cost_usd(conn) -> float:
    row = conn.execute("SELECT COALESCE(SUM(cost_usd), 0) AS total FROM api_usage").fetchone()
    return row["total"]


def create_memoria(conn, texto: str, source_text: str | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO memorias (texto, source_text) VALUES (?, ?)", (texto, source_text)
    )
    conn.commit()
    return cur.lastrowid


def list_memorias(conn, limit: int = 30) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM memorias ORDER BY criado_em DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def delete_memoria(conn, memoria_id: int):
    conn.execute("DELETE FROM memorias WHERE id = ?", (memoria_id,))
    conn.commit()


CAMPOS_SAUDE = ("passos", "distancia_km", "sono_horas", "andares_subidos")


def upsert_saude_dia(conn, data: str, campos: dict):
    """Grava (ou atualiza, se o dia ja existir) os campos de saude informados
    pra aquele dia - so mexe nos campos presentes em `campos`, preserva o
    resto (o Atalho do iPhone pode mandar so passos numa chamada e sono
    noutra, por exemplo)."""
    existente = conn.execute("SELECT * FROM saude_dados WHERE data = ?", (data,)).fetchone()
    valores = {campo: campos.get(campo) for campo in CAMPOS_SAUDE}
    if existente:
        for campo in CAMPOS_SAUDE:
            if valores[campo] is None:
                valores[campo] = existente[campo]
        conn.execute(
            """UPDATE saude_dados SET passos = ?, distancia_km = ?, sono_horas = ?,
               andares_subidos = ? WHERE data = ?""",
            (*[valores[c] for c in CAMPOS_SAUDE], data),
        )
    else:
        conn.execute(
            """INSERT INTO saude_dados (data, passos, distancia_km, sono_horas, andares_subidos)
               VALUES (?, ?, ?, ?, ?)""",
            (data, *[valores[c] for c in CAMPOS_SAUDE]),
        )
    conn.commit()


def get_saude_dia(conn, data: str) -> dict | None:
    row = conn.execute("SELECT * FROM saude_dados WHERE data = ?", (data,)).fetchone()
    return dict(row) if row else None


def media_passos_ultimos_dias(conn, antes_de: str, dias: int = 7) -> float | None:
    row = conn.execute(
        """SELECT AVG(passos) AS media FROM saude_dados
           WHERE data < ? AND data >= date(?, ?) AND passos IS NOT NULL""",
        (antes_de, antes_de, f"-{dias} days"),
    ).fetchone()
    return row["media"]
