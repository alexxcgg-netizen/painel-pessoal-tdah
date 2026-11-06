-- Leva 06/11 "painel mais esperto" (docs/briefings/2026-11-06-painel-esperto.md, frentes 4 e 7), onde_vou.py.
--
-- indo_pra: cada saida (visita/cerca do iPhone) que o painel ligou a um compromisso de hoje ("Indo pro date?").
--   Guarda de onde saiu (apelido), o destino (texto da tarefa + o ponto que o Maps devolveu, 4 casas), a hora
--   que o painel tinha mandado sair, a hora que saiu e a que chegou, o trajeto previsto, a resposta dele
--   (NULL = nao respondeu, 'sim', 'outro') e o atraso do ultimo recado mandado. Localizacao: some em 30 dias
--   junto com as visitas (onde_vou.RETENCAO_DIAS).
-- tempos_reais: as amostras que sobram disso, SEM lugar nenhum - 'saida' (minutos entre o aviso de sair e a
--   saida de casa) e 'trajeto' (minutos reais - minutos do Maps, por faixa do dia). So as ultimas 6 contam.
-- Tabelas novas, nenhum dado existente e tocado.
CREATE TABLE IF NOT EXISTS indo_pra (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dia TEXT NOT NULL,
    tarefa_id INTEGER NOT NULL,
    visita_id INTEGER,
    origem TEXT,
    destino TEXT,
    destino_lat REAL,
    destino_lon REAL,
    hora_evento TEXT NOT NULL,
    sair_aviso TEXT,
    saiu_em TEXT,
    previsto_min INTEGER,
    chegada_prevista TEXT,
    chegou_em TEXT,
    resposta TEXT,
    recado_min INTEGER,
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (dia, tarefa_id)
);
CREATE INDEX IF NOT EXISTS idx_indo_pra_visita ON indo_pra(visita_id);

CREATE TABLE IF NOT EXISTS tempos_reais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    faixa TEXT,
    valor_min INTEGER NOT NULL,
    dia TEXT NOT NULL,
    ref INTEGER,
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (tipo, ref)
);
CREATE INDEX IF NOT EXISTS idx_tempos_reais_tipo ON tempos_reais(tipo, id);
