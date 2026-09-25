-- Faixa M4 (uso diario): cache do resumo de IA do dia - antes o texto era
-- gerado de novo a cada GET /api/summary/today (todo load de pagina), agora
-- fica valido ate algo relevante mudar (tarefa de hoje/atrasada nova/concluida
-- hoje, gasto real grande novo hoje ou virar o dia). Ver app.py,
-- _impressao_resumo_dia/summary_today (~linha 2020-2095).
--
-- "Tarefa importante" = tarefa com data pra hoje ou atrasada (tasks nao tem
-- campo de prioridade; tarefa sem data ou pro futuro nao invalida o cache).

-- Uma linha por dia (`data` = date.today().isoformat(), chave primaria).
-- `impressao` e a fingerprint do que era relevante quando `resposta_json`
-- foi gerado; se bater com a impressao atual, devolve o cache sem chamar a
-- IA (e sem contar no teto de R$40/mes). Mesmo espirito de
-- `voo_status_cache` (cache de API externa por numero_voo+data).
CREATE TABLE IF NOT EXISTS resumo_dia_cache (
    data TEXT PRIMARY KEY,
    impressao TEXT NOT NULL,
    resposta_json TEXT NOT NULL,
    gerado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
