-- Grupo D do Laboratorio v4 (2026-10-30), "Onde guardei": objeto + lugar onde o Alex guardou
-- ("passaporte na gaveta azul do quarto"). Um registro por objeto (guardar de novo atualiza o lugar).
-- chave = nome normalizado (sem acento/caixa) pra achar "passaporte" mesmo escrito "Passaporte".
-- Tabela nova, nenhum dado existente e tocado.
CREATE TABLE IF NOT EXISTS guardados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chave TEXT NOT NULL UNIQUE,
    objeto TEXT NOT NULL,
    lugar TEXT NOT NULL,
    lugar_anterior TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
