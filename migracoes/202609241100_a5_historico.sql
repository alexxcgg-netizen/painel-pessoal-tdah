-- Faixa A5 (Fase 7): estado do "resumo fixo" do historico do chat (ver
-- ia/historico.py). Linha unica (id=1, forcado pelo CHECK): o resumo atual,
-- ate onde ele cobre (ultimo_mensagem_id, id de chat_mensagens) e o dia em
-- que foi gerado (dia, formato AAAA-MM-DD - usado pra saber quando a virada
-- de dia forca reconstrucao mesmo sem o historico ter crescido muito).
--
-- As mensagens originais continuam intactas em chat_mensagens - esta tabela
-- e so o resumo derivado delas, reconstruivel a qualquer momento.
CREATE TABLE IF NOT EXISTS chat_resumo_historico (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    resumo TEXT NOT NULL DEFAULT '',
    ultimo_mensagem_id INTEGER NOT NULL DEFAULT 0,
    dia TEXT NOT NULL DEFAULT '',
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
