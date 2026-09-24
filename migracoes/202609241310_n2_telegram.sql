-- Fase 7, faixa N2 (captura por Telegram) - idempotencia de updates do
-- webhook novo (rotas/n2_telegram.py, POST /api/telegram/webhook).
--
-- O Telegram reenvia um update que nao recebeu 200 a tempo (o site pode
-- estar dormindo/acordando num free tier, por exemplo) - sem controle, a
-- mesma foto/audio/texto/link processaria (e gravaria) duas vezes.
--
-- Aplicada automaticamente (uma vez por banco, via migracoes_aplicadas) pelo
-- runner de migracoes/ (db.init_db() -> db.aplicar_migracoes()). rotas/
-- n2_telegram.py tambem tem um fallback local (`_garantir_tabela`, mesmo
-- CREATE TABLE/INDEX abaixo) pra um banco que por algum motivo ainda nao
-- rodou init_db() com esta migracao - redundancia segura (IF NOT EXISTS),
-- os dois schemas nunca devem divergir.
CREATE TABLE IF NOT EXISTS telegram_updates_processados (
    update_id INTEGER PRIMARY KEY,
    processado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_telegram_updates_processado_em
    ON telegram_updates_processados(processado_em);
