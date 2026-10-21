-- Treino ao vivo (2026-10-21): "vou treinar peito" abre a ficha no chat com uma caixinha por
-- exercicio. Uma sessao por ficha por dia; `feitos` = JSON com os indices marcados;
-- `concluido_em` (UTC) quando o ultimo foi marcado; `treino_id` = o registro em `treinos`
-- que a conclusao criou (origem 'sessao'). Tabela nova, sem mexer em dado existente.
CREATE TABLE IF NOT EXISTS treino_sessoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ficha_id INTEGER NOT NULL,
    data TEXT NOT NULL,
    feitos TEXT NOT NULL DEFAULT '[]',
    concluido_em TEXT,
    treino_id INTEGER,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_treino_sessoes_ficha_dia ON treino_sessoes(ficha_id, data);
