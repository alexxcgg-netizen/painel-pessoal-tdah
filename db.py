import sqlite3
from datetime import date
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
            due_date TEXT,
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

        CREATE TABLE IF NOT EXISTS goal_deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id INTEGER NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
            valor REAL NOT NULL,
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

        CREATE TABLE IF NOT EXISTS notificacoes_enviadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            referencia_id INTEGER NOT NULL DEFAULT 0,
            data TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(tipo, referencia_id, data)
        );

        CREATE TABLE IF NOT EXISTS chat_mensagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            papel TEXT NOT NULL CHECK (papel IN ('user', 'assistant')),
            texto TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS lembretes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            data TEXT NOT NULL,
            recorrente INTEGER NOT NULL DEFAULT 0,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS atividade_dias (
            dia TEXT PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS voos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            origem TEXT,
            destino TEXT NOT NULL,
            horas REAL,
            observacao TEXT,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS configuracoes (
            chave TEXT PRIMARY KEY,
            valor TEXT
        );

        CREATE TABLE IF NOT EXISTS login_tentativas (
            ip TEXT PRIMARY KEY,
            tentativas INTEGER NOT NULL DEFAULT 0,
            bloqueado_ate REAL NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS uber_pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origem TEXT,
            destino TEXT NOT NULL,
            origem_lat REAL,
            origem_lng REAL,
            destino_lat REAL,
            destino_lng REAL,
            product_id TEXT,
            disparar_em TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'aguardando',
            fare_id TEXT,
            preco_texto TEXT,
            request_id TEXT,
            erro TEXT,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS cotacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS cotacoes_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cotacao_id INTEGER NOT NULL REFERENCES cotacoes(id) ON DELETE CASCADE,
            fornecedor TEXT,
            valor REAL,
            prazo_texto TEXT,
            observacao TEXT,
            origem TEXT NOT NULL DEFAULT 'texto',
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    conn.commit()
    _garantir_coluna(conn, "tasks", "due_date", "TEXT")
    _garantir_coluna(conn, "tasks", "hora", "TEXT")
    _garantir_coluna(conn, "tasks", "depende_do_tempo", "INTEGER NOT NULL DEFAULT 0")
    _garantir_coluna(conn, "voos", "hora", "TEXT")
    _garantir_coluna(conn, "expenses", "tipo", "TEXT NOT NULL DEFAULT 'real'")
    _garantir_indices(conn)
    _seed_perfil_inicial(conn)
    conn.close()


def _garantir_indices(conn):
    """Indices nas colunas mais filtradas/ordenadas pelo app - rodado depois das
    migracoes de coluna acima, pra nunca tentar indexar uma coluna que ainda nao
    existe num banco antigo. Banco e pequeno (uso pessoal), entao isso e mais
    sobre nao regredir conforme o historico cresce do que sobre um problema de
    performance que exista hoje."""
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_tasks_completed_at ON tasks(completed_at);
        CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
        CREATE INDEX IF NOT EXISTS idx_subtasks_task_id ON subtasks(task_id);
        CREATE INDEX IF NOT EXISTS idx_expenses_created_at ON expenses(created_at);
        CREATE INDEX IF NOT EXISTS idx_expenses_tipo ON expenses(tipo);
        CREATE INDEX IF NOT EXISTS idx_bank_transactions_bank_account_id ON bank_transactions(bank_account_id);
        CREATE INDEX IF NOT EXISTS idx_goal_deposits_goal_id ON goal_deposits(goal_id);
        CREATE INDEX IF NOT EXISTS idx_cotacoes_itens_cotacao_id ON cotacoes_itens(cotacao_id);
        CREATE INDEX IF NOT EXISTS idx_voos_data ON voos(data);
        """
    )
    conn.commit()


def _garantir_coluna(conn, tabela: str, coluna: str, tipo: str):
    """Adiciona uma coluna nova numa tabela que ja existe de uma versao anterior
    do app - CREATE TABLE IF NOT EXISTS nao faz isso sozinho."""
    colunas = [r["name"] for r in conn.execute(f"PRAGMA table_info({tabela})").fetchall()]
    if coluna not in colunas:
        conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
        conn.commit()


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
    conn.execute("INSERT INTO goal_deposits (goal_id, valor) VALUES (?, ?)", (goal_id, valor))
    conn.commit()


def list_goal_deposits(conn, goal_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT valor, criado_em FROM goal_deposits WHERE goal_id = ? ORDER BY criado_em",
        (goal_id,),
    ).fetchall()
    return [dict(r) for r in rows]


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


def ja_notificou_hoje(conn, tipo: str, referencia_id: int = 0) -> bool:
    row = conn.execute(
        "SELECT 1 FROM notificacoes_enviadas WHERE tipo = ? AND referencia_id = ? AND data = ?",
        (tipo, referencia_id, date.today().isoformat()),
    ).fetchone()
    return row is not None


def marcar_notificado(conn, tipo: str, referencia_id: int = 0):
    conn.execute(
        "INSERT OR IGNORE INTO notificacoes_enviadas (tipo, referencia_id, data) VALUES (?, ?, ?)",
        (tipo, referencia_id, date.today().isoformat()),
    )
    conn.commit()


def obter_configuracao(conn, chave: str) -> str | None:
    row = conn.execute("SELECT valor FROM configuracoes WHERE chave = ?", (chave,)).fetchone()
    return row["valor"] if row else None


def definir_configuracao(conn, chave: str, valor: str):
    conn.execute(
        "INSERT INTO configuracoes (chave, valor) VALUES (?, ?) "
        "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
        (chave, valor),
    )
    conn.commit()


def salvar_mensagem_chat(conn, papel: str, texto: str):
    conn.execute("INSERT INTO chat_mensagens (papel, texto) VALUES (?, ?)", (papel, texto))
    conn.commit()


def list_chat_mensagens(conn, limit: int = 20) -> list[dict]:
    """Mais recentes primeiro (pra LIMIT pegar as ultimas N) - quem usa pra
    montar historico de conversa deve inverter a ordem antes de mandar pra IA."""
    rows = conn.execute(
        "SELECT * FROM chat_mensagens ORDER BY criado_em DESC, id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def create_lembrete(conn, titulo: str, data_str: str, recorrente: bool = False) -> int:
    cur = conn.execute(
        "INSERT INTO lembretes (titulo, data, recorrente) VALUES (?, ?, ?)",
        (titulo, data_str, int(recorrente)),
    )
    conn.commit()
    return cur.lastrowid


def list_lembretes(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM lembretes ORDER BY data").fetchall()
    return [dict(r) for r in rows]


def delete_lembrete(conn, lembrete_id: int):
    conn.execute("DELETE FROM lembretes WHERE id = ?", (lembrete_id,))
    conn.commit()


def registrar_atividade(conn, dia_iso: str) -> None:
    conn.execute("INSERT OR IGNORE INTO atividade_dias (dia) VALUES (?)", (dia_iso,))
    conn.commit()


def list_dias_ativos(conn) -> set[str]:
    rows = conn.execute("SELECT dia FROM atividade_dias").fetchall()
    return {r["dia"] for r in rows}


def create_voo(
    conn, data_str: str, destino: str, origem: str | None = None, horas: float | None = None,
    observacao: str | None = None, hora: str | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO voos (data, origem, destino, horas, observacao, hora) VALUES (?, ?, ?, ?, ?, ?)",
        (data_str, origem, destino, horas, observacao, hora),
    )
    conn.commit()
    return cur.lastrowid


def list_voos(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM voos ORDER BY data DESC").fetchall()
    return [dict(r) for r in rows]


def delete_voo(conn, voo_id: int):
    conn.execute("DELETE FROM voos WHERE id = ?", (voo_id,))
    conn.commit()


def criar_uber_pedido(conn, origem: str | None, destino: str, disparar_em: str) -> int:
    cur = conn.execute(
        "INSERT INTO uber_pedidos (origem, destino, disparar_em) VALUES (?, ?, ?)",
        (origem, destino, disparar_em),
    )
    conn.commit()
    return cur.lastrowid


def uber_pedidos_para_disparar(conn, agora_iso: str) -> list[dict]:
    """Pedidos ainda 'aguardando' (contagem regressiva rodando) cujo horario
    de disparar a estimativa ja chegou."""
    rows = conn.execute(
        "SELECT * FROM uber_pedidos WHERE status = 'aguardando' AND disparar_em <= ?",
        (agora_iso,),
    ).fetchall()
    return [dict(r) for r in rows]


def uber_pedido(conn, pedido_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM uber_pedidos WHERE id = ?", (pedido_id,)).fetchone()
    return dict(row) if row else None


def uber_pedidos_aguardando_confirmacao(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM uber_pedidos WHERE status = 'aguardando_confirmacao' ORDER BY criado_em"
    ).fetchall()
    return [dict(r) for r in rows]


_UBER_PEDIDO_COLUNAS = {
    "origem_lat", "origem_lng", "destino_lat", "destino_lng", "product_id",
    "status", "fare_id", "preco_texto", "request_id", "erro",
}


def atualizar_uber_pedido(conn, pedido_id: int, **campos):
    """Atualiza so os campos passados. As chaves de 'campos' sao sempre
    literais escritas no proprio codigo (nunca vem de input externo), mas
    a whitelist evita que um nome de campo errado vire SQL invalido calado."""
    invalidos = set(campos) - _UBER_PEDIDO_COLUNAS
    if invalidos:
        raise ValueError(f"campo(s) invalido(s) pra uber_pedidos: {invalidos}")
    if not campos:
        return
    colunas = ", ".join(f"{c} = ?" for c in campos)
    conn.execute(
        f"UPDATE uber_pedidos SET {colunas} WHERE id = ?", (*campos.values(), pedido_id)
    )
    conn.commit()


def criar_cotacao(conn, titulo: str) -> int:
    cur = conn.execute("INSERT INTO cotacoes (titulo) VALUES (?)", (titulo,))
    conn.commit()
    return cur.lastrowid


def cotacao_por_titulo_aproximado(conn, titulo: str) -> dict | None:
    """Acha uma cotacao existente cujo titulo bate (sem diferenciar
    maiusculas/minusculas, por substring nos dois sentidos) - pra
    'fornecedor tal, R$500, pra cotacao de ferro' cair na mesma cotacao de
    'abrir cotacao de ferro' mesmo sem repetir o titulo palavra por
    palavra. Se houver mais de uma, pega a mais recente."""
    titulo_norm = (titulo or "").strip().lower()
    if not titulo_norm:
        return None
    rows = conn.execute("SELECT * FROM cotacoes ORDER BY criado_em DESC").fetchall()
    for r in rows:
        existente = r["titulo"].strip().lower()
        if titulo_norm in existente or existente in titulo_norm:
            return dict(r)
    return None


def get_cotacao(conn, cotacao_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM cotacoes WHERE id = ?", (cotacao_id,)).fetchone()
    return dict(row) if row else None


def list_cotacoes(conn) -> list[dict]:
    """Cada cotacao com quantos itens tem e o menor valor entre eles (NULL
    se nenhum item ainda tem valor) - o essencial pra listar sem precisar
    buscar os itens de cada uma."""
    rows = conn.execute(
        """SELECT c.*, COUNT(i.id) AS total_itens, MIN(i.valor) AS menor_valor
           FROM cotacoes c LEFT JOIN cotacoes_itens i ON i.cotacao_id = c.id
           GROUP BY c.id ORDER BY c.criado_em DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


def criar_item_cotacao(
    conn,
    cotacao_id: int,
    fornecedor: str | None,
    valor: float | None,
    prazo_texto: str | None = None,
    observacao: str | None = None,
    origem: str = "texto",
) -> int:
    cur = conn.execute(
        """INSERT INTO cotacoes_itens (cotacao_id, fornecedor, valor, prazo_texto, observacao, origem)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (cotacao_id, fornecedor, valor, prazo_texto, observacao, origem),
    )
    conn.commit()
    return cur.lastrowid


def list_itens_cotacao(conn, cotacao_id: int) -> list[dict]:
    """Itens da cotacao, mais barato primeiro - itens sem valor (ex: PDF que
    nao deu pra extrair) ficam por ultimo, nao desaparecem."""
    rows = conn.execute(
        """SELECT * FROM cotacoes_itens WHERE cotacao_id = ?
           ORDER BY (valor IS NULL), valor, criado_em""",
        (cotacao_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def delete_cotacao(conn, cotacao_id: int):
    """Apaga a cotacao e os itens dela - sem depender de ON DELETE CASCADE
    do SQLite (que so funciona com PRAGMA foreign_keys ligado, nao ligado
    aqui), apaga os itens primeiro explicitamente."""
    conn.execute("DELETE FROM cotacoes_itens WHERE cotacao_id = ?", (cotacao_id,))
    conn.execute("DELETE FROM cotacoes WHERE id = ?", (cotacao_id,))
    conn.commit()


def delete_item_cotacao(conn, item_id: int):
    conn.execute("DELETE FROM cotacoes_itens WHERE id = ?", (item_id,))
    conn.commit()
