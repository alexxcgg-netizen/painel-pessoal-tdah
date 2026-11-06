-- Leva 06/11 "painel mais esperto", frente 3 (docs/briefings/2026-11-06-painel-esperto.md): viagem
-- acompanhada. Posicao do carro que o app iOS manda (POST /api/localizacao/posicao) SO enquanto ha viagem
-- planejada em andamento ou compromisso de saida no ao vivo. Dado sensivel e passageiro:
--   - `chave` = "viagem-<id>" (viagem_planejada) ou o id do compromisso do ao vivo;
--   - viagem_acompanhada.limpar apaga tudo que nao e do acompanhamento de agora (viagem encerrada, chegou
--     perto do destino, outro plano) e qualquer linha com mais de 24 h - nunca fica o caminho guardado;
--   - lat/lng arredondadas a 4 casas (~11 m); `em` em hora local ("AAAA-MM-DDTHH:MM:SS"); velocidade em m/s.
-- Tabela nova, nenhum dado existente e tocado.
CREATE TABLE IF NOT EXISTS viagem_posicoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chave TEXT NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    velocidade REAL,
    precisao REAL,
    em TEXT NOT NULL,
    recebida_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_viagem_posicoes_chave ON viagem_posicoes(chave, em);
