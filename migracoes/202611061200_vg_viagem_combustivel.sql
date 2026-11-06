-- Leva "painel mais esperto" (2026-11-06, docs/briefings/2026-11-06-painel-esperto.md, frentes 1 e 2):
-- carro + abastecimentos (combustivel.py) e viagem planejada (viagem_planejada.py).
-- Tabelas novas, nenhum dado existente e tocado. O INSERT so preenche a tabela nova `veiculo`.
--
-- veiculo: um carro so (id fixo = 1). Padrao = XC40 T5 Twin Engine 2020 do Alex. tanque_l 48 e
-- PROVAVEL, nao conferido em fonte oficial (tanque_conferido = 0 -> o card escreve "a confirmar").
-- Consumo de partida 13 km/l estrada / 10 cidade: vale ate existirem 2 tanques cheios registrados,
-- depois o consumo real (combustivel.consumo_real) passa na frente. reserva_km = folga de 60 km.
CREATE TABLE IF NOT EXISTS veiculo (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    nome TEXT NOT NULL,
    tanque_l REAL NOT NULL,
    tanque_conferido INTEGER NOT NULL DEFAULT 0,
    consumo_estrada REAL NOT NULL,
    consumo_cidade REAL NOT NULL,
    reserva_km REAL NOT NULL DEFAULT 60,
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT OR IGNORE INTO veiculo (id, nome, tanque_l, tanque_conferido, consumo_estrada, consumo_cidade, reserva_km)
VALUES (1, 'Volvo XC40 T5 Twin Engine 2020', 48, 0, 13, 10, 60);

-- abastecimentos: "enchi o tanque", "abasteci 30 L por 180", foto da nota do posto.
-- data = hora local de Brasilia 'AAAA-MM-DDTHH:MM'. litros/valor/hodometro podem faltar (ele nem
-- sempre diz); cheio = 1 quando encheu o tanque (e o que permite medir o consumo real).
CREATE TABLE IF NOT EXISTS abastecimentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    hodometro_km REAL,
    litros REAL,
    valor REAL,
    cheio INTEGER NOT NULL DEFAULT 0,
    lugar TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_abastecimentos_data ON abastecimentos(data);

-- viagens_planejadas: o plano que a ferramenta planejar_viagem montou (rota, postos, chuva, 3 saidas).
-- saida_em/chegada_em = hora local de Brasilia ISO ('AAAA-MM-DDTHH:MM:SS') da saida ESCOLHIDA.
-- O GPS/ao vivo do iPhone le pelo viagem_planejada.plano_ativo (contrato fixo). encerrada_em = fim.
CREATE TABLE IF NOT EXISTS viagens_planejadas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    destino TEXT NOT NULL,
    saida_em TEXT NOT NULL,
    chegada_em TEXT NOT NULL,
    plano_json TEXT NOT NULL,
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    encerrada_em TEXT
);
CREATE INDEX IF NOT EXISTS idx_viagens_planejadas_saida ON viagens_planejadas(saida_em);
