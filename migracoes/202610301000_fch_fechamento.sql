-- Grupo G (lab v4, 2026-10-30): fechamento e recompensa. Tabelas novas, nenhum dado existente muda.
--
-- feito_extra: o que ele fez FORA do plano ("lavei a louca", "liguei pro banco") - alimenta o
-- "Placar do feito" junto com o que o painel ja sabe (tarefa concluida, treino, voo).
CREATE TABLE IF NOT EXISTS feito_extra (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    texto TEXT NOT NULL,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_feito_extra_data ON feito_extra(data);

-- treino_marcas: uma linha por exercicio marcado no treino ao vivo, com a carga e as reps NA HORA
-- (a ficha muda depois) e o 1RM estimado (Epley). Base da "Medalha na hora" (recorde = rm_est maior
-- que o de todas as marcas anteriores do mesmo exercicio) e dos "quilos levantados" da Retrospectiva.
-- Desmarcar o exercicio apaga a linha (marcar de novo reavalia o recorde).
CREATE TABLE IF NOT EXISTS treino_marcas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sessao_id INTEGER NOT NULL,
    idx INTEGER NOT NULL,
    ficha_id INTEGER NOT NULL,
    exercicio TEXT NOT NULL,
    nome TEXT NOT NULL,
    data TEXT NOT NULL,
    carga_kg REAL NOT NULL,
    series INTEGER,
    reps INTEGER NOT NULL,
    volume_kg REAL NOT NULL,
    rm_est REAL NOT NULL,
    rm_anterior REAL,
    recorde INTEGER NOT NULL DEFAULT 0,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_treino_marcas_sessao_idx ON treino_marcas(sessao_id, idx);
CREATE INDEX IF NOT EXISTS idx_treino_marcas_ex ON treino_marcas(exercicio, data);
