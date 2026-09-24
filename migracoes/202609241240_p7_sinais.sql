-- Faixa P7 (Fase 7): sinais genericos mandados pelo app Atalhos do iPhone
-- (POST /api/sinal, ver rotas/p7_sinais.py e assistente/sinais.py). Cada
-- automacao pessoal (chegar/sair de local, alarme parado, Modo Sono,
-- carregador conectado) grava uma linha aqui.
--
-- Nao confundir com /api/atalho/local (app.py, ja existente): aquele e
-- especifico pra geofence casa/mercado e devolve uma MENSAGEM pro Atalho
-- mostrar na hora. Esta tabela e generica (qualquer tipo de sinal), nao
-- devolve mensagem de display e alimenta o motor de regras (faixa P4) via
-- assistente/sinais.py (ultimos_sinais/sinal_recente) e as reacoes simples
-- do proprio P7.
--
-- tipo: cheguei | sai | acordei | dormir | carregando (ver TIPOS_VALIDOS em
--   rotas/p7_sinais.py - fonte unica da validacao).
-- lugar: nome do lugar (geofence) quando fizer sentido (cheguei/sai);
--   NULL pros demais tipos (acordei/dormir/carregando).
-- quando: ISO 8601 (datetime) de quando o evento realmente aconteceu no
--   iPhone - pode vir do proprio Atalho ("quando" no corpo do POST) ou,
--   na falta dele, e preenchido com o horario de recebimento.
-- recebido_em: horario em que o painel recebeu o POST (pode diferir de
--   `quando` quando o Atalho manda atrasado, ex: sem internet na hora).
CREATE TABLE IF NOT EXISTS sinais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL CHECK (tipo IN ('cheguei', 'sai', 'acordei', 'dormir', 'carregando')),
    lugar TEXT,
    quando TEXT NOT NULL,
    recebido_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sinais_tipo_quando ON sinais(tipo, quando DESC);
