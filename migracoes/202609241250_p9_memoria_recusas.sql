-- Faixa P9 (Fase 7, memoria viva): guarda a proposta pendente (pra aplicar
-- so quando o Alex aceitar - ver assistente/gatilhos/p9_memoria.py) e a
-- recusa (pra nunca repropor a mesma coisa nas 8 semanas seguintes).
--
-- Nota: a infra que aplica migracoes/*.sql sozinha (Etapa 0) ainda nao
-- estava integrada quando esta faixa rodou, entao assistente/gatilhos/
-- p9_memoria.py tambem cria estas 2 tabelas sob demanda (CREATE TABLE IF
-- NOT EXISTS, identico ao daqui). Rodar este arquivo depois e inofensivo.
CREATE TABLE IF NOT EXISTS p9_memoria_propostas (
    chave TEXT PRIMARY KEY,
    acao TEXT NOT NULL,
    memoria_id INTEGER,
    texto TEXT NOT NULL,
    categoria TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS p9_memoria_recusas (
    chave TEXT PRIMARY KEY,
    texto TEXT,
    recusado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
