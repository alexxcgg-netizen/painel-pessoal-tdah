-- Leva "onde eu estou" (2026-11-04, docs/briefings/2026-11-04-onde-eu-estou.md): visitas que o app
-- iOS manda (CLLocationManager.startMonitoringVisits). Localizacao e dado sensivel: fica so neste
-- banco, 30 dias (onde_estou.RETENCAO_DIAS apaga o resto a cada visita nova), lat/lon arredondadas a
-- 4 casas (~11 m) antes de gravar. Horarios em hora local de Brasilia ("AAAA-MM-DDTHH:MM:SS").
-- lugar = apelido reconhecido ("casa", "mecanico") ou NULL. avisou_chegada = a mensagem de
-- chegada ja saiu (uma por visita). Tabela nova, nenhum dado existente e tocado.
CREATE TABLE IF NOT EXISTS visitas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    precisao REAL,
    chegada TEXT,
    saida TEXT,
    lugar TEXT,
    avisou_chegada INTEGER NOT NULL DEFAULT 0,
    recebida_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_visitas_chegada ON visitas(chegada);
CREATE INDEX IF NOT EXISTS idx_visitas_recebida ON visitas(recebida_em);
