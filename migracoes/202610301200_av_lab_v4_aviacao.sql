-- Laboratorio v4, Grupo F (Aviacao) - 30/10/2026, docs/briefings/2026-10-30-lab-v4-aviacao.md.
-- civ_confirmada: 1 = ele confirmou no Super App que o instrutor lancou o voo na CIV (NULL = pendente/nao perguntado).
-- Coluna nova nullable, sem UPDATE em dado existente.
ALTER TABLE voos ADD COLUMN civ_confirmada INTEGER;

-- Simulados da banca (caderno = sigla REG/MET/NAV/TV/CTA, 20 questoes por prova).
CREATE TABLE IF NOT EXISTS banca_simulados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    caderno TEXT NOT NULL,
    data TEXT NOT NULL,
    acertos INTEGER NOT NULL,
    total INTEGER NOT NULL DEFAULT 20,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_banca_simulados_caderno ON banca_simulados(caderno, data);

-- Voo de cadeira da vespera: onde ele travou (JSON com os titulos dos passos), pra proxima vespera comecar por ali.
CREATE TABLE IF NOT EXISTS chair_flying (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    voo_id INTEGER,
    data TEXT NOT NULL,
    travou TEXT NOT NULL DEFAULT '[]',
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
