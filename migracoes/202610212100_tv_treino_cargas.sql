-- Treino ao vivo (2026-10-21): historico da carga de cada exercicio da ficha - base do grafico
-- "quando subiu / baixou" no card da troca de carga. Uma linha por mudanca (exercicio = nome
-- normalizado, sem acento/caixa; carga_num so quando a carga e em kg). Tabela nova.
CREATE TABLE IF NOT EXISTS treino_cargas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ficha_id INTEGER NOT NULL,
    exercicio TEXT NOT NULL,
    nome TEXT NOT NULL,
    carga TEXT NOT NULL,
    carga_num REAL NOT NULL,
    data TEXT NOT NULL,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_treino_cargas_ficha_ex ON treino_cargas(ficha_id, exercicio, data);
