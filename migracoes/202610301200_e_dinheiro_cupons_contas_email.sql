-- Grupo E (Dinheiro) do Laboratorio v4, 30/10/2026. Dinheiro PESSOAL do Alex (nada da construtora).
-- `cupons`: nota fiscal (NFC-e) lida pelo QR/link - itens e categorias; a chave de acesso (44 digitos)
--   e unica, entao mandar o mesmo cupom duas vezes devolve o que ja foi lido. `gasto_id` = linha de
--   `expenses` criada/vinculada quando ele toca "Registrar como gasto" (NULL = so lido).
-- `contas_email`: boleto/PIX/fatura/rastreio achado na caixa de entrada (IMAP so leitura).
--   `msg_id` (Message-ID do e-mail) e unico. `status`: nova | paga | ignorada.
-- `email_vistos`: Message-ID ja lido (achou conta ou nao), pra nao reler a mesma mensagem a cada varredura.
CREATE TABLE IF NOT EXISTS cupons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chave TEXT NOT NULL UNIQUE,
    estabelecimento TEXT NOT NULL,
    emitido_em TEXT,
    total REAL NOT NULL,
    itens_json TEXT NOT NULL,
    gasto_id INTEGER,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS contas_email (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_id TEXT NOT NULL UNIQUE,
    remetente TEXT NOT NULL,
    assunto TEXT,
    tipo TEXT NOT NULL,
    valor REAL,
    vencimento TEXT,
    codigo TEXT,
    status TEXT NOT NULL DEFAULT 'nova',
    tarefa_id INTEGER,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS email_vistos (
    msg_id TEXT PRIMARY KEY,
    visto_em TEXT NOT NULL DEFAULT (datetime('now'))
);
